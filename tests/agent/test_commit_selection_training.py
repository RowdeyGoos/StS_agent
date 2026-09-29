"""The broader no-undo mask is identical in collection, learning and playback."""
from dataclasses import replace

import pytest

torch=pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.action_policy import COMMIT_SINGLE_CARD, COMMIT_CARD_SELECTION, action_mask
from game.agent.contracts import full as f
from game.agent.recording import load_trajectory
from game.agent.training.checkpoint import load_policy, save_ppo_checkpoint, restore_ppo
from game.agent.training.config import RUN_SCENARIO_SET, TrainingConfig
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture, policy_statistics
from game.agent.training.ppo import PPOLearner, replay_batch
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.ppo_run import _rollout_record
from game.agent.training.rewards import RewardSpec
from game.agent.training.run_task import FullRunTrainingEnv
from .test_commit_selection import fury_run
from .test_ppo import comparable
from .test_training_model import cpu_threads


def fury_env(*, encounter, reward_spec, **settings):
    return FullRunTrainingEnv(reward_spec=reward_spec,engine_factory=fury_run,**settings)


@pytest.mark.parametrize('workers',[1,2])
def test_optional_selection_finishes_in_ppo_with_frozen_masks_and_exact_resume(tmp_path,workers):
    experiment=PPOExperiment(TrainingConfig('full_run',RUN_SCENARIO_SET,RewardSpec.shaped_full_run(),COMMIT_CARD_SELECTION),
        PPOConfig(rollout_steps=6,episode_decisions=3,batch_size=2,epochs=1),('overgrowth',),RUN_SCENARIO_SET,'sts_ppo_experiment_v2')
    model=ActorCritic(Vocabulary(()),Architecture(8,1),action_policy=COMMIT_CARD_SELECTION)
    # Prefer undo over pick and pick overwhelmingly over confirm. Completion
    # must come from the policy restriction, not learning incidental logits.
    with torch.no_grad():
        for parameter in model.parameters():parameter.zero_()
        model.action.weight[f.ACTIONS.index('select_card'),0]=3
        model.action.weight[f.ACTIONS.index('deselect_card'),0]=6
        model.scorer[0].weight[0,8]=1
        model.scorer[-1].weight[0,0]=100
    with PPOLearner(model,experiment,env_factory=fury_env,workers=workers) as owner:
        rollout=owner.collect(output_dir=tmp_path/'records',audit_dir=tmp_path/'audit')
        assert len(rollout.steps)==6
        for entry in rollout.progress['episodes']:
            trace=load_trajectory(tmp_path/'records'/entry['trajectory'],split='train')
            assert [t.action.kind for t in trace.transitions]==['select_card','select_card','confirm_selection']
            assert not any(n.kind=='selection' for n in f.walk(trace.transitions[-1].successor.context))
            for transition,recorded in zip(trace.transitions,[s for s in rollout.steps if s.episode_id==trace.metadata.episode_id]):
                assert recorded.mask==action_mask(transition.observation,COMMIT_CARD_SELECTION)
        assert sum(not all(s.mask) for s in rollout.steps)==4
        forced=[s for s in rollout.steps if sum(s.mask)==1]
        assert len(forced)==2 and all(s.old_log_probability==0 for s in forced)
        for state in forced:
            batch=replay_batch([state],model.vocabulary,action_policy=COMMIT_CARD_SELECTION)
            with torch.inference_mode():
                logits,_=model(batch)
                logp,entropy=policy_statistics(logits,batch['mask'],torch.tensor([state.action]))
            assert logp.item()==entropy.item()==0
        with pytest.raises(ValueError):replay_batch(forced,model.vocabulary,action_policy=COMMIT_SINGLE_CARD)
        record=_rollout_record(rollout,experiment)
        assert record['action_policy']==COMMIT_CARD_SELECTION
        assert all(all(s['legal_mask']) for s in record['steps'])
        assert [s['policy_mask'] for s in record['steps']]==[list(s.mask) for s in rollout.steps]
        owner.update(rollout)
        bundle,state=tmp_path/'saved/model.sts-model',tmp_path/'saved-private/model.resume.pt'
        save_ppo_checkpoint(bundle,owner,resume_path=state)
        loaded=load_policy(bundle)
        assert loaded.model.action_policy==COMMIT_CARD_SELECTION
        assert loaded.manifest['schema']=='sts_inference_bundle_v3'
        selected=trace.transitions[1].observation
        assert loaded(selected).kind=='select_card'
        assert loaded(trace.transitions[2].observation).kind=='confirm_selection'
        with restore_ppo(bundle,state,env_factory=fury_env) as restored:
            left,right=owner.collect(),restored.collect()
            assert comparable(left)==comparable(right)
        with pytest.raises(ValueError):
            restore_ppo(bundle,state,env_factory=fury_env,
                experiment=replace(experiment,training=replace(experiment.training,action_policy=COMMIT_SINGLE_CARD)))
