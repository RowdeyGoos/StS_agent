"""Run task isolation, genuine pairing, transfer, cutoffs and all-family scoring."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import threading

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.gym_env import FullRunEnv
from game.agent.headless import HeadlessAdapter
from game.agent.recording import load_trajectory
from game.agent.runner import RunConfig, run_episode
from game.agent.training.checkpoint import load_policy, save_checkpoint, save_ppo_checkpoint, restore_ppo
from game.agent.training.config import TrainingConfig, RUN_SCENARIO_SET
from game.agent.training.features import Vocabulary
from game.agent.training.learner import ImitationLearner
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.rewards import RewardSpec, RewardError, RunRewardComponents, measure_run
from game.agent.training.run_corpus import load_run_corpus, transfer_combat
from game.agent.training.run_demonstrations import fixture as room_fixture
from game.agent.training.run_evaluation import evaluate_full_run, summarize
from game.agent.training.run_task import campaign_seed
from .test_combat_training import fixture, act
from .test_training_model import cpu_threads, tiny_corpus
from .test_ppo import comparable


def experiment(**settings):
    return PPOExperiment(TrainingConfig.full_run(), PPOConfig(rollout_steps=4, episode_decisions=3,
        epochs=1, batch_size=2, **settings), ('overgrowth','underdocks'), RUN_SCENARIO_SET)


def owner(*, env_factory=None):
    return PPOLearner(ActorCritic(Vocabulary(()), Architecture(16,1), seed=17), experiment(),
                      seed=5, env_factory=env_factory)


@pytest.fixture
def bundles(tmp_path):
    combat = ImitationLearner(ActorCritic(tiny_corpus().vocabulary, Architecture(16,1)), tiny_corpus())
    combat_path = tmp_path/'combat.sts-model'
    save_checkpoint(combat_path, combat)
    run_path = tmp_path/'public/run.sts-model'
    save_ppo_checkpoint(run_path, owner(), resume_path=tmp_path/'private/run.resume.pt')
    return combat_path, run_path


def test_run_reward_preserves_combat_serialization_and_rejects_cross_task_components():
    combat = RewardSpec()
    assert combat.to_dict() == {'schema':'sts_training_reward_v1','weights':{
        'combat_win':1.,'combat_loss':0.,'win_hp_fraction':0.,'end_turn_action':0.,'potion_use_action':0.}}
    run = RewardSpec.full_run()
    assert run.task=='full_run' and run != combat and run.identity != combat.identity
    assert RewardSpec.from_dict(run.to_dict()) == run
    for kind in ('victory','defeat','abandoned','truncated'):
        outcome = c.RunOutcome('sts_run_outcome_v1',kind,'external_stop' if kind=='truncated' else 'none')
        assert run.evaluate(measure_run(outcome)) == int(kind=='victory')
    with pytest.raises(RewardError): combat.evaluate(RunRewardComponents(1))
    with pytest.raises(RewardError): run.evaluate({'combat_win':1})
    with pytest.raises(RewardError): RewardSpec({'combat_win':1}, run.schema)
    with pytest.raises(RewardError): TrainingConfig(reward=run)
    with pytest.raises(ValueError): experiment(gamma=.99)


def test_gym_and_runner_use_the_same_genuine_start_for_comparisons(tmp_path):
    from game.agent.training.scenarios import episode_seed
    for region in ('overgrowth','underdocks'):
        with FullRunEnv(first_act=region) as env:
            env.reset(seed=episode_seed('test',2))
            public = env.public_state
        result = run_episode(RunConfig(seed=campaign_seed('test',2),first_act=region,split='test',max_decisions=1),
            output_dir=tmp_path/region, audit_dir=tmp_path/(region+'-private'))
        assert load_trajectory(result.trajectory, split='test').initial == public
    assert len({campaign_seed(split,i) for split in ('train','validation','test') for i in range(8)}) == 24


def test_run_collection_quota_records_canonical_bootstrap_and_exact_resume(tmp_path):
    a = owner()
    rollout = a.collect(output_dir=tmp_path/'records',audit_dir=tmp_path/'audit')
    assert len(rollout.steps)==4 and all(s.reward==0 for s in rollout.steps)
    assert all(set(s.components)=={'run_victory'} for s in rollout.steps)
    for row in rollout.progress['episodes']:
        assert row['evidence']=='headless_rollout' and 'training' not in row
        trajectory = load_trajectory(tmp_path/'records'/row['trajectory'],split='train')
        assert trajectory.sha256 == row['trajectory_sha256']
        assert isinstance(trajectory.transitions[-1].successor,f.PublicDecision)
    assert rollout.steps[-1].truncated and not rollout.steps[-1].terminated
    assert rollout.steps[-1].next_value != 0
    a.update(rollout)
    public, private = tmp_path/'model/model.sts-model',tmp_path/'resume/model.resume.pt'
    save_ppo_checkpoint(public,a,resume_path=private)
    b = restore_ppo(public,private)
    for _ in range(2):
        left,right = a.collect(),b.collect()
        assert comparable(left)==comparable(right)
        a.update(left); b.update(right)
        assert all(torch.equal(v,b.model.state_dict()[k]) for k,v in a.model.state_dict().items())
    assert a.episode_cursor==b.episode_cursor
    assert torch.equal(a.action_generator.get_state(),b.action_generator.get_state())


def test_combat_win_is_zero_nonterminal_in_the_full_run_task():
    with FullRunEnv(engine_factory=lambda seed:fixture(seed),max_decisions=2) as env:
        env.reset(seed=0)
        _, reward, terminated, truncated, _ = act(env,'play_card')
        assert (reward,terminated,truncated)==(0.,False,False)
        assert env.public_state.context.kind=='rewards'


@pytest.fixture(scope='module')
def architect():
    from tests.headless.test_act2_run import win
    from game.headless.run.engine import RunEngine
    run = RunEngine.campaign(seed=4)
    run.state.hp = run.state.max_hp = 10000  # Explicit assisted test prefix.
    adapter = HeadlessAdapter(run,decision_profile=f.PROFILE)
    for _ in range(650):
        frame = adapter.observe()
        if frame.decision.context.definition_id=='the_architect':
            return run
        if run.combat:
            win(run)
            adapter = HeadlessAdapter(run,decision_profile=f.PROFILE)
        else:
            assert adapter.step(frame.binding,choose_action(frame.decision).ref).status=='reconciled'
    pytest.fail('Controlled Architect prefix exceeded its bound')


@pytest.mark.parametrize('ending',['victory','defeat'])
def test_true_run_endings_have_correct_reward_zero_bootstrap_and_terminal_masks(ending,architect,tmp_path):
    def make(**settings):
        settings.pop('encounter'); settings.pop('reward_spec')
        return FullRunEnv(engine_factory=lambda seed:deepcopy(architect) if ending=='victory' else
            fixture(seed,hp=1,cards=(),enemy_hp=100,relics=()),**settings)
    learner = owner(env_factory=make)
    rollout = learner.collect(decisions=1,output_dir=tmp_path/'records',audit_dir=tmp_path/'audit')
    step = rollout.steps[0]
    assert step.terminated and not step.truncated and step.next_value==0
    assert step.reward == int(ending=='victory')
    assert step.components=={'run_victory':int(ending=='victory')}
    row = rollout.progress['episodes'][0]
    assert row['evidence']=='controlled_fixture' and row['outcome']['kind']==ending
    corpus = load_run_corpus([tmp_path/'records'/row['trajectory']],split='train')
    assert all(e.value_target is None for e in corpus.examples)


@pytest.mark.parametrize('after_one',[False,True])
def test_full_run_action_free_timeout_does_not_invent_a_transition(after_one,tmp_path):
    class TimeoutEnv(FullRunEnv):
        expired = False
        def _time_expired(self): return self.expired
        def step(self,action):
            if not after_one: self.expired=True
            result=super().step(action)
            self.expired=True
            return result
    def make(**settings):
        region=settings.pop('encounter'); settings.pop('reward_spec')
        return TimeoutEnv(first_act=region,**settings)
    rollout = owner(env_factory=make).collect(output_dir=tmp_path/'records',audit_dir=tmp_path/'audit')
    assert len(rollout.steps)==int(after_one) and rollout.next_episode==1
    assert rollout.progress['stop_reason']=='time_budget'
    row=rollout.progress['episodes'][0]
    episode=load_trajectory(tmp_path/'records'/row['trajectory'],split='train')
    assert len(episode.transitions)==int(after_one) and episode.outcome.kind=='truncated'


def test_corpus_cutoffs_split_freezing_and_transfer_name_remapping(tmp_path,bundles):
    result = run_episode(RunConfig(seed=campaign_seed('train',5),scenario=RUN_SCENARIO_SET+':overgrowth',max_decisions=2),
        output_dir=tmp_path/'records',audit_dir=tmp_path/'audit')
    policy=load_policy(bundles[0],task='combat')
    corpus=load_run_corpus([result.trajectory],split='train',base_vocabulary=policy.model.vocabulary)
    assert all(e.value_target is None for e in corpus.examples)
    assert set(policy.model.vocabulary.names) < set(corpus.vocabulary.names)
    with pytest.raises(ValueError): load_run_corpus([result.trajectory],split='validation')
    with pytest.raises(ValueError): load_run_corpus([result.trajectory],split='validation',vocabulary=corpus.vocabulary)
    with pytest.raises(ValueError): load_run_corpus([result.trajectory,result.trajectory],split='train')
    model,lineage=transfer_combat(policy,corpus.vocabulary,seed=3)
    assert lineage['new_train_names']>0
    assert torch.equal(model.name.weight[0],policy.model.name.weight[0])
    for i,name in enumerate(policy.model.vocabulary.names,1):
        assert torch.equal(model.name.weight[corpus.vocabulary.names.index(name)+1],policy.model.name.weight[i])
    for key,value in policy.model.state_dict().items():
        if key!='name.weight' and not key.startswith('value.'):
            assert torch.equal(value,model.state_dict()[key])
    assert not model.value[-1].weight.any() and not model.value[-1].bias.any()
    learner=ImitationLearner(model,corpus)
    assert not learner.optimizer.state and learner.updates==0
    learner.step()
    with pytest.raises(ValueError): transfer_combat(load_policy(bundles[1]),corpus.vocabulary)


def test_cross_task_checkpoint_and_hybrid_initialization_reject(bundles,tmp_path):
    from game.agent.training.hybrid import evaluate_hybrid
    from game.agent.training.ppo_run import run_ppo
    with pytest.raises(ValueError,match='task'): load_policy(bundles[0],task='full_run')
    with pytest.raises(ValueError,match='task'): load_policy(bundles[1],task='combat')
    with pytest.raises(ValueError,match='task'): evaluate_hybrid(checkpoint=bundles[1],output_dir=tmp_path/'bad')
    with pytest.raises(ValueError,match='objective'):
        run_ppo(checkpoint=bundles[0],experiment=experiment(),output_dir=tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_full_run_evaluation_pairs_every_planned_case_and_retains_failures(bundles,tmp_path):
    path,report=evaluate_full_run(checkpoint=bundles[1],combat_checkpoint=bundles[0],
        output_dir=tmp_path/'eval',cases=2,split='test',max_decisions=1)
    assert report['status']=='complete' and len(report['episodes'])==6
    assert all(s['planned']==2 and s['cutoffs']==2 for s in report['summary'].values())
    plan=json.loads(path.with_name('full-run-plan.json').read_text())
    assert all(r['status']=='unattempted' for r in plan['episodes'])
    for case in {r['case_id'] for r in report['episodes']}:
        initial=[load_trajectory(path.parent/r['trajectory'],split='test').initial
                 for r in report['episodes'] if r['case_id']==case]
        assert initial[0]==initial[1]==initial[2]
    stopped=threading.Event(); stopped.set()
    _,failed=evaluate_full_run(checkpoint=bundles[1],combat_checkpoint=bundles[0],
        output_dir=tmp_path/'stopped',cases=2,cancel=stopped)
    assert failed['status']=='interrupted' and len(failed['episodes'])==6
    assert failed['summary']['heuristic']['failures']==1
    assert failed['summary']['learned']['unattempted']==2
    assert failed['paired_vs_heuristic']['learned']['conclusion']=='incomplete'


def test_full_run_model_propagates_to_spawned_worker(bundles,tmp_path):
    from game.agent.workers import run_batch
    batch=run_batch(RunConfig(max_decisions=1),output_dir=tmp_path/'play',audit_dir=tmp_path/'private-play',
        run_checkpoint=bundles[1])
    trajectory=load_trajectory(batch.episodes[0].trajectory,split='train')
    assert trajectory.metadata.policy==load_policy(bundles[1]).identity
    with pytest.raises(ValueError):
        run_batch(RunConfig(),output_dir=tmp_path/'bad',audit_dir=tmp_path/'bad-private',combat_checkpoint=bundles[1])


def test_every_native_decision_family_reaches_learned_scoring(monkeypatch,architect):
    from . import test_full_profile as native
    from game.agent.training.checkpoint import CheckpointPolicy
    model=ActorCritic(Vocabulary(()),Architecture(16,1))
    policy=CheckpointPolicy(model,RewardSpec.full_run(),'controlled-test',{})
    contexts,kinds=set(),set()
    original=HeadlessAdapter.observe
    frames={}
    def score(public):
        probabilities,value=policy.probabilities(public)
        assert set(probabilities)=={a.ref for a in public.candidates}
        assert sum(probabilities.values())==pytest.approx(1,abs=1e-6)
        assert policy(public) in public.candidates
        contexts.add(public.context.kind)
        kinds.update(a.kind for a in public.candidates)
    def observe(adapter):
        frame=original(adapter)
        if hasattr(frame,'decision') and id(frame) not in frames:
            frames[id(frame)]=frame
            score(frame.decision)
        return frame
    monkeypatch.setattr(HeadlessAdapter,'observe',observe)
    native.test_all_command_classes_have_real_dispatch_fixtures()
    native.test_trial_confirmation_reports_abandonment()
    HeadlessAdapter(deepcopy(architect),decision_profile=f.PROFILE).observe()
    assert contexts=={'ancient','map','combat','rewards','rest','shop','treasure','event','relic_choice','act_transition'}
    assert set(native.COMMANDS.values()) <= kinds
    assert {'select_card','confirm_selection','choose_event_card','continue_act','open_reward','close_reward',
        'choose_relic_card','choose_cook_card','buy_shop_item'} <= kinds


@pytest.mark.parametrize('name',['rewards','shop','rest','event','treasure','relic','assisted_campaign'])
def test_assisted_demonstration_starts_and_continuations_are_valid_and_public(name,tmp_path):
    run=room_fixture(name)(3)
    decision=HeadlessAdapter(run,decision_profile=f.PROFILE).observe().decision
    assert choose_action(decision) in decision.candidates
    if name=='assisted_campaign':
        assert decision.run.get('hp')==10000
        assert len(run.state.deck)==5
    result=run_episode(RunConfig(seed=3,evidence='controlled_fixture',max_decisions=8),
        output_dir=tmp_path/'records',audit_dir=tmp_path/'audit',engine_factory=room_fixture(name))
    assert result.timings.steps==8 and result.outcome.kind=='truncated'


def test_collected_run_manifest_round_trips_all_assisted_starts(tmp_path):
    from game.cli.agent_train import main
    from game.agent.training.run_demonstrations import corpus_paths
    root=tmp_path/'records'
    assert main(['collect-run','--output-dir',str(root),'--cases','1','--include-fixtures',
                 '--max-decisions','3','--time-limit','10'])==0
    paths=corpus_paths(root,split='train')
    assert len(paths)==8
    corpus=load_run_corpus(paths,split='train')
    assert len(corpus.examples)==24 and all(e.value_target is None for e in corpus.examples)


@pytest.fixture
def small_run_manifest(tmp_path):
    from game.agent.training.run_demonstrations import collect_run_demonstrations
    path, report = collect_run_demonstrations(output_dir=tmp_path/'records', cases=1,
                                            max_decisions=2, time_limit_seconds=10)
    assert report['status'] == 'complete'
    return path


def test_corpus_retention_is_one_use_split_bound_and_independent_of_later_disk_changes(small_run_manifest, monkeypatch):
    from game.agent.training import run_corpus, run_demonstrations
    paths = run_demonstrations.corpus_paths(small_run_manifest.parent, split='train')
    calls, load = [], run_corpus.load_trajectory
    def counted(path, **kwargs):
        calls.append(path)
        return load(path, **kwargs)
    monkeypatch.setattr(run_corpus, 'load_trajectory', counted)
    expected = load_run_corpus(paths, split='train')
    assert calls == paths  # Vocabulary and feature preparation share each load.
    retained = run_demonstrations.corpus_paths(small_run_manifest.parent, split='train', retain=True)
    assert retained.paths == tuple(paths)
    with pytest.raises(ValueError, match='split'):
        load_run_corpus(retained, split='validation', vocabulary=expected.vocabulary)
    paths[0].write_text('malformed replacement\n')
    calls.clear()
    actual = load_run_corpus(retained, split='train')
    assert not calls and actual.identity == expected.identity
    assert actual.vocabulary == expected.vocabulary and actual.reward_spec == expected.reward_spec
    assert len(actual.examples) == len(expected.examples)
    for a, b in zip(actual.examples, expected.examples):
        assert a.action == b.action and a.value_target == b.value_target
        for key in a.state.graph.observation:
            assert (a.state.graph.observation[key] == b.state.graph.observation[key]).all()
        for key in ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links', 'link_positions', 'candidates'):
            assert (getattr(a.state, key) == getattr(b.state, key)).all()
    with pytest.raises(ValueError, match='consumed'):
        load_run_corpus(retained, split='train')
    with pytest.raises(ValueError):
        load_run_corpus(paths, split='train')
    with pytest.raises(ValueError):
        run_demonstrations.corpus_paths(small_run_manifest.parent, split='train', retain=True)


@pytest.mark.parametrize('change', ('hash', 'scenario', 'evidence', 'split', 'duplicate'))
def test_retained_manifest_keeps_binding_split_and_duplicate_checks(small_run_manifest, change):
    from game.agent.training.run_demonstrations import corpus_paths
    manifest = json.loads(small_run_manifest.read_text())
    row = manifest['episodes'][0]
    if change == 'hash':
        row['trajectory_sha256'] = '0'*64
    elif change == 'scenario':
        row['scenario'] = 'shop'
    elif change == 'evidence':
        row['evidence'] = 'controlled_fixture'
    elif change == 'split':
        manifest['split'] = 'validation'
    else:
        manifest['episodes'].append(dict(row))
    small_run_manifest.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_run_corpus(corpus_paths(small_run_manifest.parent, split='train', retain=True), split='train')


def test_abandonment_is_a_real_zero_reward_ending_even_at_the_decision_limit():
    from game.headless.run.engine import RunEngine
    from game.headless.run.config import RunConfig as NativeConfig
    from game.headless.run import events
    from game.headless.run.actions import ChooseEventOption
    run=RunEngine(config=NativeConfig())
    events.begin(run.state,'trial',cards=run.cards)
    for name in ('reject','double_down'):
        run.apply(next(a for a in run.legal_actions() if isinstance(a,ChooseEventOption) and a.option_id==name))
    with FullRunEnv(engine_factory=lambda seed:run,max_decisions=1) as env:
        env.reset(seed=0)
        observation,reward,terminated,truncated,info=act(env,'abandon_run')
        assert (reward,terminated,truncated)==(0.,True,False)
        assert info['outcome']['kind']=='abandoned' and not observation['action_mask'].any()
