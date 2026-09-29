"""Skip truly empty learning batches without losing collection/resume progress."""
from dataclasses import replace
import io
import threading

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.runner import RunCancelled
from game.agent.training.checkpoint import (save_ppo_checkpoint, restore_ppo, publish, _state_digest)
from game.agent.training.ppo import UPDATE_POLICY
from game.agent.training.ppo_config import PPOConfig
from game.agent.training.ppo_run import run_ppo
from game.agent.training.rollout import advantages, fingerprint
from .test_ppo import owner, long_env, comparable
from .test_training_model import cpu_threads


def make(*, workers=1, gamma=1.):
    return owner(env_factory=long_env, workers=workers,
                 config=PPOConfig(rollout_steps=4, episode_decisions=1,
                                  batch_size=2, epochs=2, gamma=gamma))


def constant_critic(learner, value=0.):
    with torch.no_grad():
        learner.model.value[-1].weight.zero_()
        learner.model.value[-1].bias.fill_(value)


@pytest.mark.parametrize('workers',[1,2])
@pytest.mark.parametrize('warm_adam',[False,True])
def test_zero_signal_preserves_weights_adam_rng_and_resumes(tmp_path,workers,warm_adam):
    with make(workers=workers) as a:
        if warm_adam:
            constant_critic(a, .2)
            # Terminal-free one-step episodes can learn from discounted values.
            old=a.experiment
            a.experiment=replace(old,ppo=replace(old.ppo,gamma=.9))
            a.config=a.experiment.ppo
            assert a.update(a.collect())['status']=='updated'
            a.experiment=old
            a.config=old.ppo
            if a.collector is not None:
                a.collector.close()
                a.collector=None
        constant_critic(a)
        rollout=a.collect()
        assert all(s.reward==s.value==s.next_value==0 for s in rollout.steps)
        before=fingerprint(a.model)
        optimizer=_state_digest(a.optimizer.state_dict())
        update_rng=a.update_generator.get_state().clone()
        action_rng=a.action_generator.get_state().clone()
        global_rng=torch.get_rng_state().clone()
        count=a.updates
        result=a.update(rollout)
        assert result['status']=='skipped' and result['skip_reason']=='zero_advantages_and_value_errors'
        assert result['signal']==dict(policy=UPDATE_POLICY,nonzero_advantages=0,nonzero_returns=0,
                                     nonzero_rewards=0,replayed_nonzero_value_errors=0)
        assert result['optimizer_steps']==result['epochs']==0 and result['after']['entropy']>0
        assert result['mean_update']=={} and a.skipped_iterations==1 and a.updates==count
        assert a.phase=='boundary' and a.pending is None and a.episode_cursor==rollout.next_episode
        assert fingerprint(a.model)==before and _state_digest(a.optimizer.state_dict())==optimizer
        assert torch.equal(a.update_generator.get_state(),update_rng)
        assert torch.equal(a.action_generator.get_state(),action_rng) and torch.equal(torch.get_rng_state(),global_rng)
        bundle,state=tmp_path/'public/model.sts-model',tmp_path/'private/model.resume.pt'
        save_ppo_checkpoint(bundle,a,resume_path=state)
        with restore_ppo(bundle,state,env_factory=long_env) as b:
            assert b.skipped_iterations==1 and b.updates==count
            left,right=a.collect(),b.collect()
            assert comparable(left)==comparable(right) and left.next_episode>rollout.next_episode
            for learner,batch in ((a,left),(b,right)):
                assert learner.update(batch)['status']=='skipped'
            assert a.skipped_iterations==b.skipped_iterations==2
            assert fingerprint(a.model)==fingerprint(b.model)==before
            assert _state_digest(a.optimizer.state_dict())==_state_digest(b.optimizer.state_dict())==optimizer


def test_zero_immediate_reward_with_bootstrap_signal_still_updates():
    with make(gamma=.9) as learner:
        constant_critic(learner,.2)
        rollout=learner.collect()
        assert all(s.reward==0 and s.truncated for s in rollout.steps)
        before=fingerprint(learner.model)
        result=learner.update(rollout)
        assert result['status']=='updated' and result['signal']['nonzero_advantages']==4
        assert result['signal']['replayed_nonzero_value_errors'] is None
        assert learner.skipped_iterations==0 and fingerprint(learner.model)!=before


@pytest.mark.parametrize('target',[.2,1e-25])
def test_zero_advantage_requires_actual_value_error_check_even_if_mse_underflows(target):
    with make() as learner:
        constant_critic(learner)
        collected=learner.collect()
        # Controlled stale/rounded behavior values: zero GAE does not prove that
        # the actual current critic already predicts the target.
        rollout=replace(collected,steps=tuple(replace(s,value=target,next_value=target) for s in collected.steps))
        learner.pending=rollout
        adv,returns=advantages(rollout.steps)
        assert not adv.any() and returns.any()
        result=learner.update(rollout)
        assert result['status']=='updated' and result['signal']['replayed_nonzero_value_errors']==4
        assert result['optimizer_steps']>0 and learner.skipped_iterations==0


def test_tiny_nonzero_advantages_are_not_thresholded_away():
    with make() as learner:
        constant_critic(learner)
        collected=learner.collect()
        rollout=replace(collected,steps=tuple(replace(s,reward=1e-25) for s in collected.steps))
        learner.pending=rollout
        result=learner.update(rollout)
        assert result['status']=='updated' and result['signal']['nonzero_advantages']==4


def test_no_signal_still_validates_original_masks():
    with make() as learner:
        constant_critic(learner)
        original=learner.collect()
        bad=replace(original.steps[-1],mask=(False,)*len(original.steps[-1].mask))
        rollout=replace(original,steps=(*original.steps[:-1],bad))
        learner.pending=rollout
        with pytest.raises(ValueError,match='Corrupt'):
            learner.update(rollout)
        assert learner.phase=='failed' and learner.iterations==learner.skipped_iterations==learner.updates==0


@pytest.mark.parametrize('expired',[False,True])
def test_cancellation_or_timeout_at_skip_measurement_cannot_commit(monkeypatch,expired):
    from game.agent.training import ppo
    with make() as learner:
        constant_critic(learner)
        rollout=learner.collect()
        stopped,now=threading.Event(),[0.]
        measure=learner._measure
        def crossing(*args,**kwargs):
            result=measure(*args,**kwargs)
            if expired: now[0]=2.
            else: stopped.set()
            return result
        monkeypatch.setattr(learner,'_measure',crossing)
        monkeypatch.setattr(ppo.time,'monotonic',lambda:now[0])
        with pytest.raises(TimeoutError if expired else RunCancelled):
            learner.update(rollout,cancel=stopped,deadline=1.)
        assert learner.phase=='failed' and learner.iterations==learner.skipped_iterations==learner.updates==0


@pytest.mark.parametrize('change',[-1,True,2,0,'old_schema','unknown_policy'])
def test_resume_rejects_invalid_skip_accounting_before_digest_check(tmp_path,change):
    with make() as learner:
        constant_critic(learner)
        learner.update(learner.collect())
        bundle,state=tmp_path/'public/model.sts-model',tmp_path/'private/model.resume.pt'
        save_ppo_checkpoint(bundle,learner,resume_path=state)
    saved=torch.load(state,weights_only=True)
    if change=='old_schema':
        saved['schema']='sts_ppo_resume_v2'
        del saved['skipped_iterations'],saved['update_policy']
    elif change=='unknown_policy': saved['update_policy']='unknown'
    else: saved['skipped_iterations']=change
    data=io.BytesIO();torch.save(saved,data)
    altered=state.parent/'changed.resume.pt'
    publish(altered,data.getvalue(),private=True)
    with pytest.raises(ValueError,match='Incompatible PPO resume|Unsupported PPO update'):
        restore_ppo(bundle,altered,env_factory=long_env)


def test_skipped_batches_publish_resume_and_separate_processed_from_trained_decisions(tmp_path):
    with make() as learner:
        constant_critic(learner)
        bundle,state=tmp_path/'source/model.sts-model',tmp_path/'source-private/model.resume.pt'
        save_ppo_checkpoint(bundle,learner,resume_path=state)
        _,report=run_ppo(checkpoint=bundle,experiment=learner.experiment,output_dir=tmp_path/'run',
                         decisions=6,env_factory=long_env)
    assert report['status']=='complete' and report['update_policy']==UPDATE_POLICY
    summary=report['summary']
    assert summary['accepted_decisions']==summary['processed_decisions']==summary['skipped_decisions']==6
    assert summary['trained_decisions']==0 and summary['skipped_updates']==2
    with restore_ppo(tmp_path/'run/final.sts-model',tmp_path/'run-private/final.resume.pt',env_factory=long_env) as b:
        assert b.iterations==b.skipped_iterations==2 and b.decisions==6 and b.updates==0
