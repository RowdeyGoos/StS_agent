"""Public policy restrictions, real selector completion and frozen PPO masks."""
from dataclasses import replace
import json
import zipfile

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.action_policy import ALL_LEGAL, COMMIT_SINGLE_CARD, COMMIT_CARD_SELECTION, COMMIT_DECISIONS, action_mask
from game.agent.contracts import full as f
from game.agent.headless import HeadlessAdapter
from game.agent.full_policy import choose_action
from game.agent.recording import load_trajectory
from game.agent.runner import RunConfig, run_episode
from game.agent.training.checkpoint import (CheckpointPolicy, load_policy, save_checkpoint,
    save_ppo_checkpoint, restore_ppo, restore_learner)
from game.agent.training.config import RUN_SCENARIO_SET, TrainingConfig
from game.agent.training.features import FeatureEncoder, Vocabulary
from game.agent.training.learner import Corpus, Example, ImitationLearner, evaluate_imitation
from game.agent.training.model import ActorCritic, Architecture, collate, policy_statistics
from game.agent.training.ppo import PPOLearner, replay_batch
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.ppo_run import run_ppo, _rollout_record
from game.agent.training.rewards import RewardSpec
from game.agent.training.run_corpus import load_run_corpus
from game.agent.training.run_task import FullRunTrainingEnv
from game.headless.run.engine import RunEngine
from .test_combat_training import fixture
from .test_training_model import cpu_threads, decision
from .test_ppo import comparable


def selector_run(seed, relic='new_leaf'):
    run = RunEngine.campaign(seed=seed)
    run.obtain_relic(relic)
    return run


def selector_env(*, encounter, reward_spec, **settings):
    return FullRunTrainingEnv(reward_spec=reward_spec, engine_factory=selector_run, **settings)


def step(adapter, kind):
    frame = adapter.observe()
    choice = next(a for a in frame.decision.candidates if a.kind == kind)
    assert adapter.step(frame.binding, choice.ref).status == 'reconciled'
    return adapter.observe().decision


def policy(mode=COMMIT_SINGLE_CARD):
    # Deliberately prefer undo. This models the observed failure independently
    # of local research artifacts or incidental random network preferences.
    model = ActorCritic(Vocabulary(()), Architecture(8, 1), action_policy=mode)
    with torch.no_grad():
        for p in model.parameters(): p.zero_()
        for kind in ('choose_relic_card', 'deselect_relic_card'):
            model.action.weight[f.ACTIONS.index(kind), 0] = 3
        model.scorer[0].weight[0, 8] = 1
        model.scorer[-1].weight[0, 0] = 1
    return CheckpointPolicy(model, RewardSpec.full_run(), 'controlled-policy', {})


def experiment(mode=COMMIT_SINGLE_CARD):
    return PPOExperiment(TrainingConfig('full_run', RUN_SCENARIO_SET, RewardSpec.shaped_full_run(),
        mode), PPOConfig(rollout_steps=4, episode_decisions=2, batch_size=2, epochs=1),
        ('overgrowth',), RUN_SCENARIO_SET, 'sts_ppo_experiment_v2')


@pytest.mark.parametrize('relic', ['new_leaf', 'dollys_mirror', 'pomander', 'precise_scissors',
                                  'punch_dagger', 'royal_stamp'])
def test_singleton_commits_only_after_a_public_select_and_does_not_mutate(relic):
    run = selector_run(4, relic)
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    assert all(action_mask(adapter.observe().decision, COMMIT_SINGLE_CARD))
    selected = step(adapter, 'choose_relic_card')
    before = run.snapshot()
    mask = action_mask(selected, COMMIT_SINGLE_CARD)
    assert [a.kind for a, ok in zip(selected.candidates, mask) if ok] == ['confirm_relic_selection']
    assert run.snapshot() == before
    assert all(action_mask(selected, ALL_LEGAL))
    # A new attachment to an existing selection retains the ability to revise it.
    attached = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    assert all(action_mask(attached, COMMIT_SINGLE_CARD))
    result = step(adapter, 'confirm_relic_selection')
    assert result.context.kind != 'relic_choice'


def test_real_combat_singleton_confirmation_and_optional_selection_support():
    run = fixture(2, cards=('dual_wield','strike','bash'), enemy_hp=200)
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    frame = adapter.observe()
    cards = {n.ref:n.definition_id for n in f.walk(frame.decision.context) if n.kind == 'card'}
    choice = next(a for a in frame.decision.candidates if a.kind=='play_card' and cards[a.subject]=='dual_wield')
    assert adapter.step(frame.binding, choice.ref).status=='reconciled'
    selected = step(adapter, 'select_card')
    assert [a.kind for a, ok in zip(selected.candidates, action_mask(selected, COMMIT_SINGLE_CARD)) if ok] == ['confirm_selection']
    step(adapter, 'confirm_selection')
    assert run.combat.player.rules.selection is None
    # Kifuda allows zero to three: one selected card must retain all choices.
    adapter = HeadlessAdapter(selector_run(2,'kifuda'), decision_profile='full_run_v2')
    assert all(action_mask(step(adapter,'choose_relic_card'), COMMIT_SINGLE_CARD))


@pytest.mark.parametrize('change', ['missing_history','wrong_subject','wrong_family','optional','multiple',
                                  'immediate','unknown','extra_action','boolean_bound'])
def test_unproven_public_shapes_keep_all_legal_choices(change):
    adapter = HeadlessAdapter(selector_run(4), decision_profile='full_run_v2')
    public = step(adapter, 'choose_relic_card')
    wire = f.to_dict(public)
    history = next(n for n in wire['run']['children'] if n['kind']=='history')
    if change == 'missing_history': history['children'].clear()
    if change == 'wrong_subject': history['children'][-1]['links'][0]['targets'].clear()
    if change == 'wrong_family': history['children'][-1]['definition_id']='select_card'
    if change in ('optional','multiple'):
        key, value = ('minimum',0) if change=='optional' else ('maximum',2)
        next(v for v in wire['context']['fields'] if v['key']==key)['value']=value
    if change == 'immediate': wire['context']['fields'].append({'key':'manual_confirmation','value':False})
    if change == 'unknown': wire['context']['definition_id']='unknown_selector'
    if change == 'boolean_bound': next(v for v in wire['context']['fields'] if v['key']=='minimum')['value']=True
    if change == 'extra_action': wire['candidates'].append({'ref':'action:999','kind':'abandon_run','subject':None,'target':None})
    assert all(action_mask(f.from_dict(wire), COMMIT_SINGLE_CARD))


def test_reference_renaming_candidate_permutation_and_lossless_legal_graph():
    adapter = HeadlessAdapter(selector_run(4), decision_profile='full_run_v2')
    public = step(adapter, 'choose_relic_card')
    wire = f.to_dict(public)
    def rename(value):
        if type(value) is str and ':' in value and value.split(':')[0] in f.NAMESPACES+('action',):
            prefix, ordinal=value.split(':')
            return prefix+':'+str(int(ordinal)+100)
        if type(value) is list: return [rename(v) for v in value]
        if type(value) is dict: return {k:rename(v) for k,v in value.items()}
        return value
    changed=rename(wire)
    changed['candidates'].reverse()
    public2=f.from_dict(changed)
    assert [a.kind for a,ok in zip(public2.candidates,action_mask(public2,COMMIT_SINGLE_CARD)) if ok]==['confirm_relic_selection']
    encoded=FeatureEncoder(Vocabulary(()),action_policy=COMMIT_SINGLE_CARD).encode(public2)
    assert all(encoded.graph.observation['action_mask']) and len(encoded.graph.candidate_refs)==2
    assert sum(encoded.policy_mask)==1
    batch=collate([encoded],vocabulary=Vocabulary(()))
    assert batch['mask'].sum()==1


def test_recorded_execution_breaks_the_loop_with_two_separate_commands(tmp_path):
    config=RunConfig(seed=4,split='validation',max_decisions=2,evidence='controlled_fixture',
                     scenario=RUN_SCENARIO_SET+':selector')
    result=run_episode(config,output_dir=tmp_path/'public',audit_dir=tmp_path/'private',
                       engine_factory=selector_run,policy=policy(),policy_identity='controlled_selector:'+COMMIT_SINGLE_CARD)
    episode=load_trajectory(result.trajectory,split='validation')
    assert [s.action.kind for s in episode.transitions]==['choose_relic_card','confirm_relic_selection']
    selected=episode.transitions[1].observation
    assert policy(ALL_LEGAL)(selected).kind=='deselect_relic_card'
    assert policy()(selected).kind=='confirm_relic_selection'
    assert episode.transitions[-1].successor.context.kind!='relic_choice'
    assert result.outcome.kind=='truncated' and len(episode.transitions)==2
    # A one-action limit stops after selection, without a hidden confirmation.
    result=run_episode(replace(config,max_decisions=1),output_dir=tmp_path/'cut',audit_dir=tmp_path/'cut-private',
                       engine_factory=selector_run,policy=policy(),policy_identity='controlled_selector:'+COMMIT_SINGLE_CARD)
    episode=load_trajectory(result.trajectory,split='validation')
    assert len(episode.transitions)==1 and episode.transitions[-1].successor.context.kind=='relic_choice'


@pytest.mark.parametrize('workers',[1,2])
def test_ppo_mask_likelihoods_records_and_exact_resume(tmp_path,workers):
    exp=experiment()
    model=ActorCritic(Vocabulary(()),Architecture(8,1),action_policy=COMMIT_SINGLE_CARD)
    with PPOLearner(model,exp,env_factory=selector_env,workers=workers) as owner:
        rollout=owner.collect(output_dir=tmp_path/'records',audit_dir=tmp_path/'audit')
        forced=[s for s in rollout.steps if not all(s.mask)]
        assert len(forced)==2
        for s in forced:
            assert s.old_log_probability==0 and sum(s.mask)==1
            assert all(s.state.graph.observation['action_mask'])
            batch=replay_batch([s],model.vocabulary,action_policy=COMMIT_SINGLE_CARD)
            with torch.inference_mode():
                logits,_=model(batch)
                logp,entropy=policy_statistics(logits,batch['mask'],torch.tensor([s.action]))
            assert logp.item()==entropy.item()==0
        for entry in rollout.progress['episodes']:
            trajectory=load_trajectory(tmp_path/'records'/entry['trajectory'],split='train')
            assert [t.action.kind for t in trajectory.transitions]==['choose_relic_card','confirm_relic_selection']
        record=_rollout_record(rollout,exp)
        assert record['schema']=='sts_ppo_rollout_v3' and record['action_policy']==COMMIT_SINGLE_CARD
        assert all(all(row['legal_mask']) for row in record['steps'])
        assert sum(not all(row['policy_mask']) for row in record['steps'])==2
        with pytest.raises(ValueError): replay_batch([replace(forced[0],mask=(True,True))],model.vocabulary)
        with pytest.raises(ValueError): replay_batch(forced,model.vocabulary,action_policy=ALL_LEGAL)
        owner.update(rollout)
        bundle,state=tmp_path/'saved/model.sts-model',tmp_path/'saved-private/model.resume.pt'
        save_ppo_checkpoint(bundle,owner,resume_path=state)
        loaded=load_policy(bundle)
        assert loaded.model.action_policy==COMMIT_SINGLE_CARD and loaded.manifest['schema']=='sts_inference_bundle_v3'
        with restore_ppo(bundle,state,env_factory=selector_env) as restored:
            left,right=owner.collect(),restored.collect()
            assert comparable(left)==comparable(right)
            owner.update(left); restored.update(right)
            assert all(torch.equal(v,restored.model.state_dict()[k]) for k,v in model.state_dict().items())


@pytest.mark.parametrize('mode', [COMMIT_SINGLE_CARD,COMMIT_CARD_SELECTION,COMMIT_DECISIONS])
def test_imitation_masks_checkpoint_and_resume_bind_the_same_policy(tmp_path,mode):
    result=run_episode(RunConfig(seed=4,split='train',max_decisions=2,evidence='controlled_fixture',
        scenario=RUN_SCENARIO_SET+':selector'),output_dir=tmp_path/'data',audit_dir=tmp_path/'data-private',
        engine_factory=selector_run)
    corpus=load_run_corpus([result.trajectory],split='train',action_policy=mode)
    legacy=load_run_corpus([result.trajectory],split='train')
    assert corpus.identity!=legacy.identity and corpus.vocabulary==legacy.vocabulary
    owner=ImitationLearner(ActorCritic(corpus.vocabulary,Architecture(8,1),action_policy=mode),corpus)
    owner.step()
    assert evaluate_imitation(owner.model,corpus)['decisions']==2
    bundle,state=tmp_path/'saved/model.sts-model',tmp_path/'saved-private/model.resume.pt'
    save_checkpoint(bundle,owner,resume_path=state)
    restored=restore_learner(bundle,state,corpus)
    owner.step(); restored.step()
    assert all(torch.equal(v,restored.model.state_dict()[k]) for k,v in owner.model.state_dict().items())
    selected=load_trajectory(result.trajectory,split='train').transitions[1].observation
    assert load_policy(bundle)(selected).kind=='confirm_relic_selection'
    with pytest.raises(ValueError): restore_learner(bundle,state,legacy)
    with pytest.raises(ValueError): evaluate_imitation(owner.model,legacy)
    # A human/legacy demonstration that undoes its selection is incompatible,
    # rather than being silently relabelled or dropped from the corpus.
    loop=run_episode(RunConfig(seed=4,split='train',max_decisions=2,evidence='controlled_fixture',
        scenario=RUN_SCENARIO_SET+':selector'),output_dir=tmp_path/'loop',audit_dir=tmp_path/'loop-private',
        engine_factory=selector_run,policy=policy(ALL_LEGAL),policy_identity='controlled_selector:'+ALL_LEGAL)
    with pytest.raises(ValueError,match='excluded'):
        load_run_corpus([loop.trajectory],split='train',action_policy=mode)


@pytest.mark.parametrize('origin,target', [(ALL_LEGAL,COMMIT_SINGLE_CARD),(COMMIT_SINGLE_CARD,COMMIT_CARD_SELECTION),
                                        (COMMIT_CARD_SELECTION,COMMIT_DECISIONS)])
def test_explicit_policy_adoption_preserves_weights_and_rejects_resume_changes(tmp_path,origin,target):
    exp=experiment(target)
    old_exp=replace(exp,training=replace(exp.training,action_policy=origin),
                    schema='sts_ppo_experiment_v1' if origin==ALL_LEGAL else 'sts_ppo_experiment_v2')
    with PPOLearner(ActorCritic(Vocabulary(()),Architecture(8,1),action_policy=origin),old_exp,env_factory=selector_env) as owner:
        bundle,state=tmp_path/'old/model.sts-model',tmp_path/'old-private/model.resume.pt'
        save_ppo_checkpoint(bundle,owner,resume_path=state)
    old=load_policy(bundle)
    assert old.model.action_policy==origin
    assert old.manifest['schema']==('sts_inference_bundle_v2' if origin==ALL_LEGAL else 'sts_inference_bundle_v3')
    assert ('action_policy' in old_exp.to_dict()['training'])==(origin!=ALL_LEGAL)
    for settings in ({},{'reset_action_policy':True,'resume_state':state}):
        with pytest.raises(ValueError):
            run_ppo(checkpoint=bundle,experiment=exp,output_dir=tmp_path/'rejected',decisions=2,
                    env_factory=selector_env,**settings)
        assert not (tmp_path/'rejected').exists()
    _,report=run_ppo(checkpoint=bundle,experiment=exp,output_dir=tmp_path/'new',decisions=4,
                     env_factory=selector_env,reset_action_policy=True)
    assert report['status']=='complete'
    initial=load_policy(tmp_path/'new/initial.sts-model')
    assert initial.model.action_policy==target
    assert all(torch.equal(v,initial.model.state_dict()[k]) for k,v in old.model.state_dict().items())
    assert report['initialization']['action_policy_transfer']['actor_weights_retained']
    assert report['initialization']['action_policy_transfer']['critic_weights_retained']
    assert load_policy(bundle).identity==old.identity
    with pytest.raises(ValueError):
        restore_ppo(tmp_path/'new/final.sts-model',tmp_path/'new-private/final.resume.pt',
                    experiment=old_exp,env_factory=selector_env)


@pytest.mark.parametrize('change',['unknown','legacy_tag','unrestricted_v3','config_mismatch'])
def test_bundle_rejects_mismatched_policy_versions(tmp_path,change):
    exp=experiment()
    with PPOLearner(ActorCritic(Vocabulary(()),Architecture(8,1),action_policy=COMMIT_SINGLE_CARD),
                   exp,env_factory=selector_env) as owner:
        bundle=tmp_path/'public/model.sts-model'
        save_ppo_checkpoint(bundle,owner,resume_path=tmp_path/'private/model.resume.pt')
    with zipfile.ZipFile(bundle) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        weights=archive.read('weights.pt')
    if change=='unknown': manifest['action_policy']='future_policy'
    if change=='legacy_tag': manifest['schema']='sts_inference_bundle_v2'
    if change=='unrestricted_v3': manifest['action_policy']=ALL_LEGAL
    if change=='config_mismatch':
        manifest['learner_config']['schema']='sts_ppo_experiment_v1'
        manifest['learner_config']['training'].pop('action_policy')
    altered=tmp_path/'altered.sts-model'
    with zipfile.ZipFile(altered,'w') as archive:
        archive.writestr('manifest.json',json.dumps(manifest))
        archive.writestr('weights.pt',weights)
    with pytest.raises(ValueError): load_policy(altered)


def test_restricted_combat_checkpoint_carries_its_policy_through_curriculum(tmp_path):
    from game.agent.training.curriculum_run import CurriculumConfig, run_curriculum
    public=decision()
    vocab=Vocabulary.fit([public],split='train')
    state=FeatureEncoder(vocab,action_policy=COMMIT_SINGLE_CARD).encode(public)
    example=Example(state,state.graph.candidate_refs.index(choose_action(public).ref),None)
    corpus=Corpus((example,),vocab,RewardSpec(),'controlled-corpus','train',1,0,COMMIT_SINGLE_CARD)
    owner=ImitationLearner(ActorCritic(vocab,Architecture(8,1),action_policy=COMMIT_SINGLE_CARD),corpus)
    bundle=tmp_path/'input.sts-model'
    save_checkpoint(bundle,owner)
    config=CurriculumConfig((1,1,1,1,1),PPOConfig(rollout_steps=1,batch_size=1,epochs=1),30.)
    _,report=run_curriculum(checkpoint=bundle,config=config,output_dir=tmp_path/'curriculum')
    assert report['status']=='complete' and report['action_policy']==COMMIT_SINGLE_CARD
    assert len(report['replicates'])==3
    for row in report['replicates']:
        assert len(row['stages'])==5
        assert load_policy(row['checkpoint']).model.action_policy==COMMIT_SINGLE_CARD
