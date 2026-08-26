"""Tests for process-parallel PPO environment collection."""

from __future__ import annotations

import numpy as np

from game.simulation.env_factory import CombatEnvFactory
from game.training.ppo_env_pool import ParallelPPOEnvPool


def test_parallel_pool_matches_local_seeded_environment() -> None:
    factory = CombatEnvFactory(
        encounter_set="simple",
        enemy_hp=6,
        cards_per_turn=1,
        record_trajectory=False,
    )
    local_env = factory()
    local_observation = local_env.reset(seed=7)
    expected_state = local_env.encode_observation(local_observation)
    expected_mask, expected_features = local_env.encode_policy_inputs(
        local_observation
    )

    try:
        pool = ParallelPPOEnvPool(
            factory,
            num_envs=2,
            num_workers=2,
            observation_size=local_env.observation_size,
            action_space_size=local_env.action_space_size,
            action_feature_size=local_env.action_feature_size,
            start_method="fork",
        )
    except PermissionError:
        # Some restricted test sandboxes prohibit POSIX shared memory.
        return

    try:
        pool.reset({0: 7, 1: 8})
        states, masks, features = pool.policy_inputs((0,))
        np.testing.assert_allclose(states[0], expected_state)
        assert tuple(masks[0]) == tuple(bool(value) for value in expected_mask)
        np.testing.assert_allclose(features[0], expected_features)

        action = next(index for index, is_legal in enumerate(expected_mask) if index)
        expected_next_observation, expected_reward, expected_done, _info = (
            local_env.step_discrete(action)
        )
        step_batch = pool.step((0,), (action,))

        np.testing.assert_allclose(
            step_batch.next_states[0],
            local_env.encode_observation(expected_next_observation),
        )
        assert float(step_batch.rewards[0]) == expected_reward
        assert bool(step_batch.dones[0]) is expected_done
        assert (step_batch.summaries[0] is not None) is expected_done
    finally:
        pool.close()


def test_parallel_pool_rejects_unpickleable_factory() -> None:
    try:
        ParallelPPOEnvPool(
            lambda: CombatEnvFactory(encounter_set="simple")(),
            num_envs=2,
            num_workers=1,
            observation_size=1,
            action_space_size=1,
            action_feature_size=1,
        )
    except ValueError as exc:
        assert "pickle-friendly" in str(exc)
    else:
        raise AssertionError("Expected an unpickleable env_factory to be rejected.")
