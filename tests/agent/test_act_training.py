"""Act 1 task success, public progress rewards and campaign record separation."""
from copy import deepcopy
from dataclasses import asdict, replace
from functools import partial
import json
import threading

import pytest

torch = pytest.importorskip('torch')
gym = pytest.importorskip('gymnasium')
from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.headless import HeadlessAdapter
from game.agent.progress import completed_act
from game.agent.recording import load_trajectory
from game.agent.runner import RunConfig, run_episode, RunFailure
from game.agent.training.checkpoint import load_policy, restore_ppo, save_ppo_checkpoint
from game.agent.training.config import TrainingConfig, RUN_SCENARIO_SET
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.ppo_run import run_ppo
from game.agent.training.rewards import RewardSpec, RewardError, ACT_RUN_SCHEMA, measure_act_run
from game.agent.training.run_demonstrations import describe
from game.agent.training.run_evaluation import evaluate_full_run, summarize, compare
from game.agent.training.run_task import FullRunTrainingEnv
from game.agent.gym_env import EnvironmentFailure
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase
from game.headless.run.actions import LeaveRewards, ChooseRewardCard, ClaimGold, ClaimPotion, DiscardPotion
from game.headless.encounters.catalog import ENCOUNTERS
from .test_combat_training import act, fixture as fight
from .test_training_model import cpu_threads
from .test_full_run_training import bundles, architect


def objective(*, goal='act1', amount=3):
    return RewardSpec.with_act_rewards({'run_victory':0, 'act_cleared':amount}, goal=goal)


def boss_rewards(seed=0, *, act_number=1, ascension=0, resolve=False):
    """Controlled assisted prefix; measured reward exit uses actual game rules."""
    from tests.headless.test_act2_run import win
    from game.cli.headless_play import choose_demo_action
    run = RunEngine.campaign(seed=4, ascension=ascension)
    run.state.hp = run.state.max_hp = 10000
    for _ in range(650):
        if run.combat:
            win(run)
        if (run.state.phase is RunPhase.REWARD and run.state.act_index == act_number-1 and
                ENCOUNTERS[run.state.pending['encounter_id']].room_kind == 'boss'):
            break
        run.apply(choose_demo_action(run, rest_choice='rest', path='left'))
    else:
        raise AssertionError('Controlled boss prefix exceeded its bound')
    if resolve:
        # Resolve/forfeit reward choices and discard held potions through legal
        # commands so the final decision has only LeaveRewards, also in workers.
        for _ in range(30):
            actions = run.legal_actions()
            if actions == (LeaveRewards(),):
                break
            choice = next((a for a in actions if isinstance(a, ChooseRewardCard) and a.definition_id is None), None)
            choice = choice or next((a for a in actions if isinstance(a, (ClaimGold, DiscardPotion, ClaimPotion))), None)
            assert choice is not None, actions
            run.apply(choice)
        else:
            raise AssertionError('Reward resolution exceeded its bound')
    return run


def boss_environment(*, encounter, reward_spec, **settings):
    return FullRunTrainingEnv(reward_spec=reward_spec,
                              engine_factory=partial(boss_rewards, resolve=True), **settings)


def settings(spec=None):
    return PPOExperiment(TrainingConfig('full_run',RUN_SCENARIO_SET,spec or objective()),
        PPOConfig(rollout_steps=2,episode_decisions=1,batch_size=2,epochs=1),
        ('overgrowth','underdocks'),RUN_SCENARIO_SET)


def test_goal_and_reward_are_versioned_together_without_changing_old_serialization():
    spec = objective()
    assert spec.schema == ACT_RUN_SCHEMA and spec.episode_goal == 'act1' and spec.task == 'full_run'
    assert RewardSpec.from_dict(spec.to_dict()) == spec
    assert spec.identity != objective(goal='full_run').identity
    assert 'goal' not in RewardSpec.full_run().to_dict()
    assert 'act_cleared' not in dict(RewardSpec.shaped_full_run().weights)
    with pytest.raises(RewardError): RewardSpec.from_dict({k:v for k,v in spec.to_dict().items() if k!='goal'})
    with pytest.raises(RewardError): RewardSpec.with_act_rewards(goal='act2')
    with pytest.raises(RewardError): RewardSpec.with_act_rewards({'act_cleared':True})
    with pytest.raises(RewardError): RewardSpec.shaped_full_run({'act_cleared':1})
    assert PPOExperiment.from_dict(settings().to_dict()) == settings()


@pytest.mark.parametrize('amount', [0, .25, 7])
def test_act1_exit_is_task_success_with_configurable_reward_and_retained_public_boundary(amount):
    run=boss_rewards()
    with FullRunTrainingEnv(reward_spec=objective(amount=amount),engine_factory=lambda seed:run,max_decisions=1) as env:
        env.reset(seed=0)
        assert env._info()['training_reward'] is None
        assert env.step(-1)[1:4] == (0.,False,False)
        obs,reward,done,cut,info=act(env,'leave_rewards')
        assert (reward,done,cut)==(amount,True,False)
        decoded=env.encoder.decode(obs)
        assert completed_act(env.public_state)==completed_act(decoded)==1
        # The encoder gives attachment references canonical local numbering.
        assert decoded.context==env.public_state.context and decoded.run.fields==env.public_state.run.fields
        assert info['act1_cleared'] and info['goal']=='act1'
        assert info['outcome']==c.to_dict(c.RunOutcome('sts_run_outcome_v1','truncated','external_stop'))
        assert info['training_reward']['components']['act_cleared']==1
        assert info['training_reward']['components']['run_victory']==0
        assert run.state.act_index==0 and run.state.phase is RunPhase.ACT_COMPLETE
        with pytest.raises(gym.error.ResetNeeded): env.step(0)


def test_completion_wins_over_post_dispatch_time_limit_and_action_free_timeout_pays_nothing(monkeypatch):
    with FullRunTrainingEnv(reward_spec=objective(),engine_factory=boss_rewards) as env:
        env.reset(seed=0)
        dispatch=env._dispatch
        def expired_after_dispatch(ref):
            result=dispatch(ref)
            monkeypatch.setattr(env,'_time_expired',lambda:True)
            return result
        monkeypatch.setattr(env,'_dispatch',expired_after_dispatch)
        assert act(env,'leave_rewards')[1:4]==(3.,True,False)
    with FullRunTrainingEnv(reward_spec=objective(),engine_factory=boss_rewards) as env:
        env.reset(seed=0)
        monkeypatch.setattr(env,'_time_expired',lambda:True)
        _,reward,done,cut,info=env.step(0)
        assert (reward,done,cut)==(0.,False,True)
        assert info['training_reward'] is None and info['execution'] is None and not info['act1_cleared']


@pytest.mark.parametrize('act_number',[1,2,3])
def test_full_campaign_act_bonus_pays_before_continue_and_never_on_continue(act_number):
    run=boss_rewards(act_number=act_number)
    with FullRunTrainingEnv(reward_spec=objective(goal='full_run'),engine_factory=lambda seed:run) as env:
        env.reset(seed=0)
        _,reward,done,cut,info=act(env,'leave_rewards')
        assert (reward,done,cut)==(3.,False,False)
        assert completed_act(env.public_state)==act_number
        assert act(env,'continue_act')[1:4]==(0.,False,False)
        assert env._info()['training_reward']['components']['act_cleared']==0


def test_first_a10_glory_boss_is_not_an_act_clear():
    run=boss_rewards(act_number=3,ascension=10)
    with FullRunTrainingEnv(reward_spec=objective(goal='full_run'),engine_factory=lambda seed:run) as env:
        env.reset(seed=0)
        _,reward,done,cut,info=act(env,'leave_rewards')
        assert (reward,done,cut)==(0.,False,False)
        assert completed_act(env.public_state) is None and run.state.phase is RunPhase.ROUTE
        assert info['training_reward']['components']['act_cleared']==0


def test_architect_victory_has_its_own_reward_and_no_act_bonus(architect):
    spec=RewardSpec.with_act_rewards({'run_victory':5,'act_cleared':2})
    with FullRunTrainingEnv(reward_spec=spec,engine_factory=lambda seed:deepcopy(architect)) as env:
        env.reset(seed=0)
        _,reward,done,cut,info=act(env,'choose_event_option')
        assert (reward,done,cut)==(5.,True,False)
        assert info['training_reward']['components']['act_cleared']==0


def test_reset_at_completed_act_never_grants_success_and_repeated_public_marker_never_repays(tmp_path):
    run=boss_rewards();run.apply(LeaveRewards())
    decision=HeadlessAdapter(run,decision_profile='full_run_v2').observe().decision
    execution=c.ExecutionReport('sts_execution_report_v1','reconciled','none','none')
    parts=measure_act_run(decision.candidates[0],execution,decision,None,None,1)
    assert parts.act_cleared==0
    with FullRunTrainingEnv(reward_spec=objective(),engine_factory=lambda seed:deepcopy(run)) as env:
        with pytest.raises(EnvironmentFailure,match='unfinished_act1'): env.reset(seed=0)
    with pytest.raises(RunFailure,match='unfinished Act 1'):
        run_episode(RunConfig(goal='act1',evidence='controlled_fixture'),engine_factory=lambda seed:deepcopy(run),
                    output_dir=tmp_path/'public',audit_dir=tmp_path/'private')


def test_defeat_and_nonterminal_quota_are_not_act_success():
    with FullRunTrainingEnv(reward_spec=objective(),engine_factory=partial(fight,hp=1,cards=(),enemy_hp=100,relics=())) as env:
        env.reset(seed=0)
        _,_,done,cut,info=act(env,'end_turn')
        assert done and not cut and not info['act1_cleared'] and info['outcome']['kind']=='defeat'
    with FullRunTrainingEnv(reward_spec=objective(),max_decisions=1) as env:
        env.reset(seed=0)
        _,_,done,cut,info=env.step(0)
        assert not done and cut and not info['act1_cleared']


@pytest.mark.parametrize('workers',[1,2])
def test_act1_ppo_zero_bootstrap_canonical_zero_reward_parallel_resume_and_reports(workers,tmp_path,bundles):
    path,report=run_ppo(checkpoint=bundles[1],experiment=settings(),output_dir=tmp_path/'ppo',decisions=2,
                        workers=workers,env_factory=boss_environment,reset_objective=True)
    assert report['status']=='complete', report.get('failure')
    summary=report['summary']
    assert summary['goal']=='act1' and summary['act1_clears']==2 and summary['act1_clear_rate']==1
    assert summary['wins']==summary['cutoffs']==0 and summary['task_return']==6
    record=json.loads((path.parent/report['iterations'][0]['rollout']).read_text())
    assert record['schema']=='sts_ppo_rollout_v4' and record['reward_spec']==objective().to_dict()
    for step in record['steps']:
        assert step['terminated'] and not step['truncated'] and step['next_value']==0
        assert step['reward']==step['return']==3 and step['components']['act_cleared']==1
    for row in report['iterations'][0]['collection']['episodes']:
        assert row['status']=='terminated' and row['act1_cleared'] and row['evidence']=='controlled_fixture'
        trajectory=load_trajectory(path.parent/row['trajectory'],split='train')
        assert trajectory.outcome.kind=='truncated' and trajectory.outcome.reason=='external_stop'
        assert sum(t.reward for t in trajectory.transitions)==0
        assert completed_act(trajectory.transitions[-1].successor)==1
    with restore_ppo(path.parent/'final.sts-model',tmp_path/'ppo-private/final.resume.pt',env_factory=boss_environment) as learner:
        assert learner.experiment.training.reward.episode_goal=='act1'
        assert learner.collection_settings['workers']==workers
        resumed=learner.collect(decisions=1)
        assert resumed.steps[0].terminated and resumed.steps[0].next_value==0
    changed=settings(objective(goal='full_run'))
    with pytest.raises(ValueError,match='objective'):
        run_ppo(checkpoint=path.parent/'final.sts-model',experiment=changed,output_dir=tmp_path/'bad',decisions=1)


def test_runner_and_evaluation_count_act_completion_without_claiming_campaign_win(tmp_path):
    result=run_episode(RunConfig(goal='act1',evidence='controlled_fixture',max_decisions=1),
        engine_factory=partial(boss_rewards,resolve=True),output_dir=tmp_path/'public',audit_dir=tmp_path/'private')
    row=describe(result,split='train',goal='act1')
    assert row['status']=='terminated' and row['act1_cleared']
    assert row['task_return']==1 and row['canonical_return']==0 and row['outcome']['kind']=='truncated'
    rows=[dict(row,case_id='same',source_group='same',policy=p) for p in ('heuristic','reference','learned')]
    rows[2].update(status='failed',act1_cleared=False)
    summary,paired=summarize(rows,goal='act1')
    assert summary['reference']['act1_clear_rate']==1 and summary['reference']['cutoffs']==0
    assert summary['reference']['run_wins']==0 and summary['learned']['act1_clear_rate']==0
    assert paired['learned']['conclusion']=='incomplete'
    assert compare([rows[2]],[rows[1]],goal='act1',baseline_name='reference')['act1_clears_only_reference']==1


def test_genuine_act1_evaluation_pairs_initializer_and_retains_cutoffs_and_cancellation(bundles,tmp_path):
    path,report=evaluate_full_run(checkpoint=bundles[1],reference_checkpoint=bundles[1],goal='act1',
        output_dir=tmp_path/'eval',cases=2,split='validation',max_decisions=1)
    assert report['status']=='complete' and report['primary_metric']=='act1_clear_rate' and path.name=='act1.json'
    assert report['paired_vs_reference']['act1_clear_rate_difference']==0
    for stats in report['summary'].values():
        assert stats['planned']==2 and stats['act1_clears']==0 and stats['cutoffs']==2
    for case in {r['case_id'] for r in report['episodes']}:
        initial=[load_trajectory(path.parent/r['trajectory'],split='validation').initial
                 for r in report['episodes'] if r['case_id']==case]
        assert initial[0]==initial[1]==initial[2]
    stopped=threading.Event();stopped.set()
    _,report=evaluate_full_run(checkpoint=bundles[1],reference_checkpoint=bundles[1],goal='act1',
        output_dir=tmp_path/'cancelled',cases=2,cancel=stopped)
    assert report['status']=='interrupted' and report['paired_vs_reference']['conclusion']=='incomplete'
    assert report['summary']['learned']['planned']==report['summary']['learned']['unattempted']==2
