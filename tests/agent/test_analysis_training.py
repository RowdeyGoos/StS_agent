"""Real PPO artifacts join public decisions; comparison uses exactly that state."""
from copy import deepcopy

import pytest

torch=pytest.importorskip('torch')
pytest.importorskip('gymnasium')

from game.agent.contracts import full as f
from game.agent.analysis.report import build_report
from game.agent.analysis.server import AnalysisStore
from game.agent.analysis.sources import collect_metadata, discover, validate_overlay
from game.agent.recording import load_trajectory
from game.agent.training.checkpoint import save_ppo_checkpoint, load_policy
from game.agent.training.config import TrainingConfig, RUN_SCENARIO_SET
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.ppo_run import run_ppo
from game.agent.training.rewards import RewardSpec
from .test_training_model import cpu_threads


@pytest.fixture
def collected(tmp_path):
    spec=RewardSpec.with_act_rewards({'run_victory':0,'act_cleared':1,'end_turn_action':-.001},goal='act1')
    experiment=PPOExperiment(TrainingConfig('full_run',RUN_SCENARIO_SET,spec),
        PPOConfig(rollout_steps=4,episode_decisions=2,batch_size=2,epochs=1),
        ('overgrowth','underdocks'),RUN_SCENARIO_SET)
    with PPOLearner(ActorCritic(Vocabulary(()),Architecture(16,1),seed=9),experiment,seed=5) as learner:
        checkpoint=tmp_path/'source/initial.sts-model'
        save_ppo_checkpoint(checkpoint,learner,resume_path=tmp_path/'source-private/initial.resume.pt')
    output=tmp_path/'learner'
    _,report=run_ppo(checkpoint=checkpoint,experiment=experiment,output_dir=output,decisions=4)
    assert report['status']=='complete'
    return output,report


def test_real_ppo_diagnostics_and_checkpoint_preferences_share_exact_recorded_state(collected,tmp_path):
    output,training=collected
    report=build_report([output],tmp_path/'report',goal='act1')
    assert sum(r['steps'] for r in report['runs'])==4
    assert sum(r['training']['return'] for r in report['runs'])==pytest.approx(training['summary']['task_return'])
    assert report['training'][0]['iterations'][0]['decisions']==4
    store=AnalysisStore(tmp_path/'report',[('initial',output/'initial.sts-model'),('final',output/'final.sts-model')])
    row=report['runs'][0];detail=store.decision(row['id'],0);result=store.compare(row['id'],0)
    assert result['state_sha256']==detail['state_sha256']
    initial=load_policy(output/'initial.sts-model')
    probabilities,critic=initial.probabilities(f.from_dict(detail['observation']))
    model=result['models'][0]
    assert {r['ref']:r['probability'] for r in model['probabilities']}==probabilities
    assert model['value']==critic and model['matches_recorded_policy']
    assert sum(r['probability'] for r in model['probabilities'])==pytest.approx(1,abs=1e-6)
    recorded=detail['training'];assert recorded['chosen_probability']==pytest.approx(probabilities[detail['action']['ref']],abs=1e-6)
    assert len(result['models'])==2 and all(r['allowed'] for r in model['probabilities'])
    assert row['canonical_return']==0 and detail['canonical_reward']==0


@pytest.mark.parametrize('edit',[
    lambda o:o['episode'].update(trajectory_sha256='0'*64),
    lambda o:o['steps'][0].update(action_ref='action:999'),
    lambda o:o['steps'][0].update(episode_step=True),
    lambda o:o['steps'][0].update(legal_mask=[1]*len(o['steps'][0]['legal_mask'])),
    lambda o:o['steps'][0].update(old_log_probability=1),
    lambda o:o['steps'][0].update(value=float('nan')),
    lambda o:o['steps'][0].update(reward=10),
    lambda o:o['steps'][0]['components'].update(act_cleared=1),
    lambda o:o['steps'][0].update(terminated=True,truncated=False,next_value=0),
    lambda o:o.update(behavior='sts_policy_state_v1:'+'0'*64),
])
def test_ppo_semantic_joins_reject_inconsistent_public_and_learner_records(collected,edit):
    output,_=collected
    _,overlays,_,_,_=collect_metadata(discover([output]))
    key,overlay=next(iter(overlays.items()));trajectory=load_trajectory(output/(key+'.trajectory.jsonl'))
    assert validate_overlay(trajectory,overlay)
    changed=deepcopy(overlay);edit(changed)
    with pytest.raises(ValueError):validate_overlay(trajectory,changed)


def test_inspector_distinguishes_native_legal_undo_from_policy_forced_confirmation(tmp_path):
    from game.agent.headless import HeadlessAdapter
    from .test_action_policy import selector_run, step, policy, experiment
    from .test_analysis import record
    adapter=HeadlessAdapter(selector_run(4),decision_profile=f.PROFILE)
    selected=step(adapter,'choose_relic_card')
    action=next(a for a in selected.candidates if a.kind=='confirm_relic_selection')
    successor=step(adapter,'confirm_relic_selection')
    path=record(tmp_path/'input',start=selected,choices=[(action,successor)])
    build_report([path],tmp_path/'report')
    checkpoint=tmp_path/'model/forced.sts-model'
    with PPOLearner(policy().model,experiment()) as learner:
        save_ppo_checkpoint(checkpoint,learner,resume_path=tmp_path/'model-private/forced.resume.pt')
    store=AnalysisStore(tmp_path/'report',[('forced',checkpoint)])
    value=store.decision('1'*32,0);compared=store.compare('1'*32,0)['models'][0]
    assert len(value['candidates'])==2
    by_ref={a['ref']:a['kind'] for a in value['candidates']}
    permissions={by_ref[p['ref']]:(p['allowed'],p['probability']) for p in compared['probabilities']}
    assert permissions=={'confirm_relic_selection':(True,1.),'deselect_relic_card':(False,0.)}
