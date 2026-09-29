"""Configurable campaign rewards, public measurements and objective transfer."""
from copy import deepcopy
from dataclasses import asdict, replace
from functools import partial
import hashlib
import json

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.gym_env import EnvironmentFailure
from game.agent.headless import HeadlessAdapter
from game.agent.headless.combat_summary import CombatSummary
from game.agent.recording import load_trajectory
from game.agent.training.checkpoint import load_policy, restore_ppo, save_ppo_checkpoint
from game.agent.training.config import TrainingConfig, RUN_SCENARIO_SET
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.ppo_run import run_ppo
from game.agent.training.rewards import RewardError, RewardSpec, measure_full_run, ShapedRunRewardComponents
from game.agent.training.run_evaluation import evaluate_full_run
from game.agent.training.run_task import FullRunTrainingEnv
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from .test_combat_training import act, fixture
from .test_full_run_training import architect, bundles
from .test_ppo import comparable
from .test_training_model import cpu_threads


def shaped(**weights):
    return RewardSpec.shaped_full_run(weights)


def experiment(reward=None, **settings):
    return PPOExperiment(TrainingConfig('full_run', RUN_SCENARIO_SET, reward or shaped(run_defeat=-1)),
        PPOConfig(rollout_steps=4, episode_decisions=16, epochs=1, batch_size=2, **settings),
        ('overgrowth','underdocks'), RUN_SCENARIO_SET)


def defeat_environment(*, encounter, reward_spec, **kwargs):
    return FullRunTrainingEnv(reward_spec=reward_spec,
        engine_factory=partial(fixture,hp=1,cards=(),enemy_hp=100,relics=()), **kwargs)


def instant_environment(*, encounter, reward_spec, **kwargs):
    return FullRunTrainingEnv(reward_spec=reward_spec,engine_factory=instant_campaign,**kwargs)


def instant_campaign(seed):
    graph = MapGraph((MapNode('first','combat',('second',),'overgrowth_nibbit',row=1,column=0),
                     MapNode('second','combat',('exit',),'overgrowth_nibbit',row=2,column=0),
                     MapNode('exit','slice_end',(),row=3,column=0)), 'first')
    run = RunEngine(seed=seed,graph=graph,card_ids=('strike',),hp=40,
                    rng_profile='native',config=RunConfig())
    # Real entry effects: marked enemies start at 1 HP; Hourglass kills them
    # before the first combat decision. No forced win or post-attachment edit.
    for name in ('burning_blood','fur_coat','mercury_hourglass'):
        run.obtain_relic(name)
    return run


def test_versioned_objective_defaults_identity_and_all_hand_calculated_components():
    spec = shaped(combat_win=2,combat_loss=-2,win_hp_fraction=.25,end_turn_action=-.01,
                  potion_use_action=-.02,run_victory=10,run_defeat=-3,run_abandoned=-4)
    assert spec.task == 'full_run' and len(spec.components)==8
    assert RewardSpec.from_dict(spec.to_dict()) == spec
    assert spec.identity == RewardSpec(dict(reversed(spec.weights)),spec.schema).identity
    assert shaped().identity != RewardSpec.full_run().identity
    assert dict(shaped().weights)['run_victory']==1 and dict(shaped().weights)['combat_win']==0
    assert spec.evaluate(ShapedRunRewardComponents(1,0,.5,0,1,0,0,0))==pytest.approx(2.105)
    assert spec.evaluate(ShapedRunRewardComponents(0,1,0,1,0,0,1,0))==pytest.approx(-5.01)
    assert spec.evaluate(ShapedRunRewardComponents(0,0,0,0,0,1,0,0))==10
    assert spec.evaluate(ShapedRunRewardComponents(0,0,0,0,0,0,0,1))==-4
    assert TrainingConfig.from_dict(TrainingConfig('full_run',RUN_SCENARIO_SET,spec).to_dict()).reward==spec
    with pytest.raises(RewardError): RewardSpec({'combat_win':1},RewardSpec.full_run().schema)
    with pytest.raises(RewardError): spec.evaluate({'run_victory':0})


@pytest.mark.parametrize('weights', [dict(combat_win=True),dict(run_defeat=float('inf')),
    dict(damage_prevented=0),dict(run_abandoned='-1'),(('combat_win',1),('combat_win',2))])
def test_invalid_full_run_weights_reject(weights):
    with pytest.raises(RewardError): RewardSpec.shaped_full_run(weights)


def test_full_run_measurement_rejects_unreconciled_missing_and_reopened_fights():
    action = f.Candidate('action:0','end_turn')
    report = c.ExecutionReport('sts_execution_report_v1','reconciled','applied','none')
    before = CombatSummary('combat:0','ongoing',40,80,1)
    after = replace(before,outcome='victory',hp=46)
    cutoff = c.RunOutcome('sts_run_outcome_v1','truncated','decision_budget')
    assert measure_full_run(action,report,cutoff,before,after).combat_win==1
    assert measure_full_run(action,report,cutoff,after,after).combat_win==0
    for previous,current in ((before,None),(before,replace(after,combat_ref='combat:1')),(after,before)):
        with pytest.raises(RewardError): measure_full_run(action,report,cutoff,previous,current)
    with pytest.raises(RewardError):
        measure_full_run(action,replace(report,status='rejected',mutation='none',reason='invalid_action'),cutoff,before,after)
    with pytest.raises(RewardError):
        ShapedRunRewardComponents(0,1,0,0,0,0,0,0)
    with pytest.raises(RewardError):
        ShapedRunRewardComponents(0,0,0,0,0,1,1,0)


@pytest.mark.parametrize('cutoff',[False,True])
def test_combat_victory_pays_after_hooks_and_keeps_campaign_boundary(cutoff):
    spec = shaped(combat_win=2,win_hp_fraction=.25)
    with FullRunTrainingEnv(reward_spec=spec,engine_factory=fixture,max_decisions=1 if cutoff else 10) as env:
        _,info=env.reset(seed=0)
        assert info['training_reward'] is None
        _,reward,done,cut,info=act(env,'play_card')
        assert reward==pytest.approx(2+.25*46/80) and not done and cut==cutoff
        assert env.public_state.context.kind=='rewards'
        values=info['training_reward']['components']
        assert values['combat_win']==1 and values['run_victory']==0
        assert info['training_reward']['context']['after_combat']['hp']==46
        if not cutoff:
            info['training_reward']['components']['combat_win']=999
            assert env._info()['training_reward']['components']['combat_win']==1
            assert env.step(-1)[1:4]==(0.,False,False)
            assert env._info()['training_reward'] is None
            _,reward,done,cut,info=act(env,'claim_gold')
            assert reward==0 and info['training_reward']['components']['combat_win']==0


def test_two_instant_entry_wins_are_measured_once_each_with_distinct_owners():
    with FullRunTrainingEnv(reward_spec=shaped(combat_win=1),engine_factory=instant_campaign,max_decisions=80) as env:
        env.reset(seed=3)
        paid=[]
        for _ in range(80):
            choice=choose_action(env.public_state)
            _,reward,done,cut,info=env.step(env.public_state.candidates.index(choice))
            parts=info['training_reward']['components']
            if parts['combat_win']:
                assert choice.kind=='choose_map_node'
                context=info['training_reward']['context']
                assert context['before_combat'] is None
                paid.append(context['after_combat']['combat_ref'])
            assert reward==parts['combat_win'] and parts['run_victory']==0
            if done or cut: break
        assert len(paid)==len(set(paid))==2
        assert cut and not done and info['outcome']['reason']=='slice_complete'


@pytest.mark.parametrize('revival',[None,'fairy_in_a_bottle','lizard_tail'])
def test_combat_loss_and_run_defeat_stack_only_on_real_defeat(revival):
    make=partial(fixture,hp=1,enemy_hp=40,relics=('lizard_tail',) if revival=='lizard_tail' else (),
                 potions=('fairy_in_a_bottle',) if revival=='fairy_in_a_bottle' else ())
    with FullRunTrainingEnv(reward_spec=shaped(combat_loss=-2,run_defeat=-3,potion_use_action=-.5),engine_factory=make) as env:
        env.reset(seed=0)
        _,reward,done,cut,info=act(env,'end_turn')
        parts=info['training_reward']['components']
        assert parts['potion_use_action']==0 and not cut
        assert reward==(0 if revival else -5) and done==(revival is None)
        assert parts['run_defeat']==parts['combat_loss']==int(revival is None)


def test_nested_potion_selection_costs_once_and_turn_cost_is_separate():
    make=partial(fixture,cards=('strike','defend'),enemy_hp=80,potions=('gamblers_brew',))
    with FullRunTrainingEnv(reward_spec=shaped(potion_use_action=-.2,end_turn_action=-.1),engine_factory=make) as env:
        env.reset(seed=0)
        assert act(env,'use_potion')[1]==-.2
        assert act(env,'select_card')[1]==0
        assert act(env,'confirm_selection')[1]==0
        assert act(env,'end_turn')[1]==-.1


def test_noncombat_potion_and_abandonment_are_distinct_from_combat():
    from game.headless.run import events
    from game.headless.run.inventory import add_potion
    run=RunEngine(config=RunConfig(),hp=40)
    events.begin(run.state,'trial',cards=run.cards)
    add_potion(run.state,'blood_potion')
    with FullRunTrainingEnv(reward_spec=shaped(potion_use_action=-.2,run_abandoned=-4,run_defeat=-2),
                            engine_factory=lambda seed:run) as env:
        env.reset(seed=0)
        _,reward,done,cut,info=act(env,'use_potion')
        assert reward==-.2 and not done and info['training_reward']['context']['after_combat'] is None
        for label in ('reject','double_down'):
            decision=env.public_state
            nodes={n.ref:n for n in f.walk(decision.context) if n.ref}
            choice=next(a for a in decision.candidates if a.kind=='choose_event_option' and nodes[a.subject].definition_id==label)
            assert env.step(decision.candidates.index(choice))[1]==0
        _,reward,done,cut,info=act(env,'abandon_run')
        assert (reward,done,cut)==(-4.,True,False)
        assert info['training_reward']['components']['run_defeat']==info['training_reward']['components']['combat_loss']==0


def test_actual_architect_ending_uses_configured_victory_reward(architect):
    with FullRunTrainingEnv(reward_spec=shaped(run_victory=7),engine_factory=lambda seed:deepcopy(architect)) as env:
        env.reset(seed=0)
        _,reward,done,cut,info=act(env,'choose_event_option')
        assert (reward,done,cut)==(7.,True,False)
        assert info['outcome']['kind']=='victory' and info['training_reward']['components']['combat_win']==0


@pytest.mark.parametrize('fight',[False,True])
def test_event_death_and_event_combat_use_their_own_boundaries(fight):
    from game.headless.run import events
    run=RunEngine(config=RunConfig(),hp=40 if fight else 1,card_ids=('whirlwind',))
    run.upgrade_card(run.state.deck[0].instance_id)
    run.obtain_relic('burning_blood')
    events.begin(run.state,'dense_vegetation')
    with FullRunTrainingEnv(reward_spec=shaped(combat_win=2,run_defeat=-3,combat_loss=-5),
                            engine_factory=lambda seed:run) as env:
        env.reset(seed=0)
        for label in (('rest','fight') if fight else ('trudge_on',)):
            decision=env.public_state
            nodes={n.ref:n for n in f.walk(decision.context) if n.ref}
            choice=next(a for a in decision.candidates if a.kind=='choose_event_option' and nodes[a.subject].definition_id==label)
            _,reward,done,cut,info=env.step(decision.candidates.index(choice))
        if fight:
            assert reward==0 and not done and not cut
            assert act(env,'play_card')[1]==2 and env.public_state.context.kind=='rewards'
            assert env._info()['training_reward']['context']['after_combat']['hp']==70
            assert act(env,'claim_gold')[1]==0
        else:
            assert (reward,done,cut)==(-3.,True,False)
            assert info['training_reward']['components']['combat_loss']==0


def test_positive_combat_reward_bootstraps_at_a_run_collection_cutoff():
    from game.agent.training.rollout import advantages
    settings=experiment(shaped(combat_win=2,win_hp_fraction=.25))
    with PPOLearner(ActorCritic(Vocabulary(()),Architecture(16,1)),settings,
                    env_factory=instant_environment) as learner:
        batch=learner.collect(decisions=1)
        step=batch.steps[0]
        assert step.reward==pytest.approx(2+.25*46/80)
        assert step.truncated and not step.terminated and step.next_value!=0
        assert step.components['run_victory']==0 and step.components['combat_win']==1
        _,targets=advantages(batch.steps)
        assert targets[0].item()==pytest.approx(step.reward+step.next_value)


def test_timeout_after_victory_cannot_repay_cached_measurement(monkeypatch):
    with FullRunTrainingEnv(reward_spec=shaped(combat_win=1,run_defeat=-1),engine_factory=fixture) as env:
        env.reset(seed=0)
        assert act(env,'play_card')[1]==1
        monkeypatch.setattr(env,'_time_expired',lambda:True)
        _,reward,done,cut,info=env.step(0)
        assert (reward,done,cut)==(0.,False,True)
        assert info['execution'] is info['training_reward'] is None


def test_invalid_stale_and_uncertain_actions_do_not_publish_rewards(monkeypatch):
    from game.agent.headless import AdapterFault
    with FullRunTrainingEnv(reward_spec=shaped(end_turn_action=-1),engine_factory=fixture) as env:
        env.reset(seed=0)
        _,reward,_,_,info=env.step(-1)
        assert reward==0 and info['training_reward'] is None
        env._adapter._engine.combat.player.energy += 1
        _,reward,_,_,info=env.step(0)
        assert reward==0 and info['execution']['reason']=='stale_decision' and info['training_reward'] is None
        env.reset(seed=0)
        def fail(command): raise RuntimeError('uncertain test dispatch')
        monkeypatch.setattr(env._adapter._engine,'apply',fail)
        with pytest.raises(AdapterFault): env.step(0)
        with pytest.raises(EnvironmentFailure): env.step(0)
        assert env._reward_measurement is None


def test_explicit_objective_change_records_rewards_and_keeps_canonical_trajectory(bundles,tmp_path):
    source=bundles[1]
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    settings=experiment(shaped(run_defeat=-1,combat_loss=-2,end_turn_action=-.01))
    with pytest.raises(ValueError,match='objective'):
        run_ppo(checkpoint=source,experiment=settings,output_dir=tmp_path/'reject',decisions=4)
    with pytest.raises(ValueError,match='resume'):
        run_ppo(checkpoint=source,experiment=settings,output_dir=tmp_path/'reject',decisions=4,
                reset_objective=True,resume_state='unused.resume.pt')
    with pytest.raises(ValueError,match='full-run'):
        run_ppo(checkpoint=bundles[0],experiment=settings,output_dir=tmp_path/'reject',decisions=4,reset_objective=True)
    assert not (tmp_path/'reject').exists()
    path,report=run_ppo(checkpoint=source,experiment=settings,output_dir=tmp_path/'ppo',decisions=4,
                        reset_objective=True,seed=17,env_factory=defeat_environment)
    assert report['status']=='complete' and report['summary']['task_return']==pytest.approx(-12.04)
    assert report['summary']['losses']==4 and report['summary']['wins']==0
    assert report['initialization']['objective_transfer']['value_head']=='fresh_hidden_zero_output'
    old,initial=load_policy(source),load_policy(path.parent/'initial.sts-model')
    for name,value in old.model.state_dict().items():
        if not name.startswith('value.'):
            assert torch.equal(value,initial.model.state_dict()[name])
    assert not initial.model.value[-1].weight.any() and not initial.model.value[-1].bias.any()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
    final=load_policy(path.parent/'final.sts-model',task='full_run',reward_spec=settings.training.reward)
    assert final.reward_spec==settings.training.reward
    entry=report['iterations'][0]
    recorded=json.loads((path.parent/entry['rollout']).read_text())
    assert recorded['schema']=='sts_ppo_rollout_v2' and recorded['reward_spec']==settings.training.reward.to_dict()
    assert all(abs(s['advantage'])>0 for s in recorded['steps'])
    by_id={e['episode_id']:e for e in entry['collection']['episodes']}
    for step in recorded['steps']:
        episode=load_trajectory(path.parent/by_id[step['episode_id']]['trajectory'],split='train')
        transition=episode.transitions[step['episode_step']]
        assert transition.reward==0 and episode.outcome.kind=='defeat'
        context=step['reward_context']
        measured=measure_full_run(transition.action,transition.execution,transition.successor,
            context['before_combat'],context['after_combat'])
        assert asdict(measured)==step['components'] and settings.training.reward.evaluate(measured)==step['reward']
        assert shaped(combat_loss=-10,run_victory=0).evaluate(measured)==-10  # Explicit offline rescore.


@pytest.mark.parametrize('workers',[1,2])
def test_shaped_collection_exact_resume_and_worker_totals(tmp_path,workers):
    settings=experiment(shaped(run_defeat=-1,end_turn_action=-.1))
    with PPOLearner(ActorCritic(Vocabulary(()),Architecture(16,1)),settings,
                    workers=workers,env_factory=defeat_environment) as left:
        batch=left.collect()
        assert all(s.reward==-1.1 and s.reward_context is not None for s in batch.steps)
        assert batch.progress['components']['combat_loss']==batch.progress['components']['run_defeat']==4
        left.update(batch)
        public,private=tmp_path/'public/m.sts-model',tmp_path/'private/m.resume.pt'
        save_ppo_checkpoint(public,left,resume_path=private)
        with restore_ppo(public,private,env_factory=defeat_environment) as right:
            a,b=left.collect(),right.collect()
            assert comparable(a)==comparable(b)
            assert [s.components for s in a.steps]==[s.components for s in b.steps]
            assert [s.reward_context for s in a.steps]==[s.reward_context for s in b.steps]
            left.update(a); right.update(b)
            assert all(torch.equal(v,right.model.state_dict()[k]) for k,v in left.model.state_dict().items())
        with pytest.raises(ValueError,match='experiment'):
            restore_ppo(public,private,experiment=experiment(shaped(run_defeat=-2)),env_factory=defeat_environment)


def test_shaped_checkpoint_evaluation_still_scores_actual_run_wins(tmp_path,bundles):
    settings=experiment(shaped(combat_win=100,run_defeat=-10))
    path=tmp_path/'model/full.sts-model'
    with PPOLearner(ActorCritic(Vocabulary(()),Architecture(16,1)),settings) as learner:
        save_ppo_checkpoint(path,learner,resume_path=tmp_path/'private/full.resume.pt')
    _,report=evaluate_full_run(checkpoint=path,combat_checkpoint=bundles[0],output_dir=tmp_path/'eval',
                                cases=1,split='validation',max_decisions=1)
    assert report['status']=='complete'
    assert report['reward_spec']==RewardSpec.full_run().to_dict()
    assert report['training_reward_spec']==settings.training.reward.to_dict()
    assert all(s['wins']==0 and s['win_rate']==0 and s['cutoffs']==1 for s in report['summary'].values())
