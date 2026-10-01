"""Lethal retaliation is a measured defeat across adapter, Gym and PPO boundaries."""
from dataclasses import replace

import pytest

pytest.importorskip('gymnasium')
torch = pytest.importorskip('torch')

from game.agent.training.config import TrainingConfig
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.rewards import RewardSpec
from game.agent.training.run_task import FullRunTrainingEnv
from game.agent.recording import load_trajectory
from tests.headless.test_terminal_outcomes import retaliation_run


def objective():
    return RewardSpec.with_act_rewards({'run_victory': 0., 'run_defeat': -1.,
        'combat_win': .1, 'combat_loss': 0., 'act_cleared': 1., 'end_turn_action': -.001}, goal='act1')


def test_simultaneous_death_is_terminal_defeat_and_never_combat_win_reward():
    with FullRunTrainingEnv(reward_spec=objective(), engine_factory=lambda _: retaliation_run(),
                            max_decisions=1) as env:
        env.reset(seed=2)
        ref = next(a.ref for a in env.public_state.candidates if a.kind == 'end_turn')
        obs, reward, terminated, truncated, info = env.step(env._encoded.candidate_refs.index(ref))
        assert info['execution']['status'] == 'reconciled'
        assert terminated and not truncated and not obs['action_mask'].any()
        assert info['outcome']['kind'] == 'defeat' and not info['act1_cleared']
        assert env._adapter.combat_summary.outcome == 'defeat'
        assert env._adapter.combat_summary.hp == 0
        measured = info['training_reward']['components']
        assert measured['combat_loss'] == measured['run_defeat'] == 1.
        assert measured['combat_win'] == measured['win_hp_fraction'] == measured['act_cleared'] == 0.
        assert reward == pytest.approx(-1.001)


def test_ppo_records_terminal_loss_with_zero_bootstrap(tmp_path):
    reward = objective()
    config = PPOExperiment(replace(TrainingConfig.full_run(), reward=reward),
        PPOConfig(rollout_steps=1, episode_decisions=1, epochs=1, batch_size=1),
        ('underdocks',), 'ironclad_a0_full_run_v1')
    def environment(**kwargs):
        kwargs.pop('encounter')
        return FullRunTrainingEnv(engine_factory=lambda _: retaliation_run(), **kwargs)
    model = ActorCritic(Vocabulary(()), Architecture(16, 1), seed=7)
    with PPOLearner(model, config, seed=5, env_factory=environment) as learner:
        rollout = learner.collect(output_dir=tmp_path/'public', audit_dir=tmp_path/'private')
        assert len(rollout.steps) == 1
        step = rollout.steps[0]
        assert step.terminated and not step.truncated and step.next_value == 0.
        assert step.reward == pytest.approx(-1.001)
        episode, = rollout.progress['episodes']
        assert episode['status'] == 'terminated' and not episode['act1_cleared']
        recorded = load_trajectory(tmp_path/'public'/episode['trajectory'], split='train')
        assert recorded.outcome.kind == 'defeat'
        assert recorded.transitions[0].reward == 0.  # Canonical full-campaign utility.
