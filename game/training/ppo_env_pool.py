"""Persistent process-parallel environment slots for CPU PPO collection."""

from __future__ import annotations

import atexit
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import multiprocessing
from multiprocessing.connection import Connection
from multiprocessing.shared_memory import SharedMemory
import pickle
from time import process_time
import traceback
from typing import Any

import numpy as np

from ..simulation.core import CombatEnv, Observation
from ..simulation.trajectory import EpisodeSummary


@dataclass(frozen=True, slots=True)
class ParallelStepBatch:
    """Results for one batch of process-parallel environment steps."""

    next_states: np.ndarray
    rewards: np.ndarray
    dones: np.ndarray
    summaries: tuple[EpisodeSummary | None, ...]


class ParallelPPOEnvPool:
    """Own persistent simulator workers backed by shared numeric buffers."""

    def __init__(
        self,
        env_factory: Callable[[], CombatEnv],
        *,
        num_envs: int,
        num_workers: int,
        observation_size: int,
        action_space_size: int,
        action_feature_size: int,
        start_method: str = "spawn",
    ) -> None:
        if num_envs <= 0:
            raise ValueError("num_envs must be positive.")
        if num_workers <= 0:
            raise ValueError("num_workers must be positive.")
        if num_workers > num_envs:
            raise ValueError("num_workers cannot exceed num_envs.")
        try:
            pickle.dumps(env_factory)
        except (AttributeError, pickle.PicklingError, TypeError) as exc:
            raise ValueError(
                "Parallel PPO requires a pickle-friendly env_factory. "
                "Use game.env_factory.CombatEnvFactory or a top-level callable."
            ) from exc

        self.num_envs = num_envs
        self.num_workers = num_workers
        self._closed = False
        self._worker_cpu_seconds = [0.0] * num_workers
        self._shared_memory: list[SharedMemory] = []
        self._connections: list[Connection] = []
        self._processes: list[multiprocessing.Process] = []
        self._worker_slots: list[tuple[int, ...]] = []
        self._states = self._create_array(
            (num_envs, observation_size), np.dtype(np.float32)
        )
        self._action_masks = self._create_array(
            (num_envs, action_space_size), np.dtype(np.bool_)
        )
        self._action_features = self._create_array(
            (num_envs, action_space_size, action_feature_size),
            np.dtype(np.float32),
        )
        self._actions = self._create_array((num_envs,), np.dtype(np.int64))
        self._rewards = self._create_array((num_envs,), np.dtype(np.float64))
        self._dones = self._create_array((num_envs,), np.dtype(np.bool_))
        self._summary_valid = self._create_array((num_envs,), np.dtype(np.bool_))
        self._summary_total_reward = self._create_array(
            (num_envs,), np.dtype(np.float64)
        )
        self._summary_steps = self._create_array((num_envs,), np.dtype(np.int32))
        self._summary_turn = self._create_array((num_envs,), np.dtype(np.int32))
        self._summary_winner = self._create_array((num_envs,), np.dtype(np.int8))
        self._summary_player_hp = self._create_array(
            (num_envs,), np.dtype(np.int32)
        )
        self._summary_enemy_hp = self._create_array(
            (num_envs,), np.dtype(np.int32)
        )

        array_specs = self._array_specs()
        context = multiprocessing.get_context(start_method)
        for worker_index in range(num_workers):
            slots = tuple(range(worker_index, num_envs, num_workers))
            parent_connection, child_connection = context.Pipe()
            process = context.Process(
                target=_environment_worker_main,
                args=(
                    child_connection,
                    env_factory,
                    slots,
                    array_specs,
                    worker_index,
                ),
                name=f"ppo-env-worker-{worker_index}",
                daemon=True,
            )
            try:
                process.start()
            except BaseException:
                parent_connection.close()
                child_connection.close()
                self.close()
                raise
            child_connection.close()
            self._connections.append(parent_connection)
            self._processes.append(process)
            self._worker_slots.append(slots)

        try:
            self._receive_all(range(num_workers), expected="ready")
        except BaseException:
            self.close()
            raise
        atexit.register(self.close)

    @property
    def worker_cpu_seconds(self) -> float:
        """Return CPU seconds reported by all persistent workers."""
        return sum(self._worker_cpu_seconds)

    def reset(self, assignments: Mapping[int, int | None]) -> None:
        """Reset selected slots with explicit deterministic episode seeds."""
        grouped: list[list[tuple[int, int | None]]] = [
            [] for _ in range(self.num_workers)
        ]
        for slot, episode_seed in assignments.items():
            grouped[slot % self.num_workers].append((slot, episode_seed))
        active_workers = []
        for worker_index, worker_assignments in enumerate(grouped):
            if not worker_assignments:
                continue
            self._connections[worker_index].send(("reset", worker_assignments))
            active_workers.append(worker_index)
        self._receive_all(active_workers, expected="reset")

    def policy_inputs(
        self,
        slots: Sequence[int],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Copy current numeric policy inputs for selected environment slots."""
        indices = np.asarray(slots, dtype=np.int64)
        return (
            np.array(self._states[indices], copy=True),
            np.array(self._action_masks[indices], copy=True),
            np.array(self._action_features[indices], copy=True),
        )

    def states(self, slots: Sequence[int]) -> np.ndarray:
        """Copy current encoded states for selected slots."""
        return np.array(self._states[np.asarray(slots, dtype=np.int64)], copy=True)

    def step(
        self,
        slots: Sequence[int],
        actions: Sequence[int],
    ) -> ParallelStepBatch:
        """Advance selected slots concurrently and return their numeric results."""
        if len(slots) != len(actions):
            raise ValueError("slots and actions must have equal lengths.")
        grouped: list[list[int]] = [[] for _ in range(self.num_workers)]
        for slot, action in zip(slots, actions):
            self._actions[slot] = action
            self._summary_valid[slot] = False
            grouped[slot % self.num_workers].append(slot)
        active_workers = []
        for worker_index, worker_slots in enumerate(grouped):
            if not worker_slots:
                continue
            self._connections[worker_index].send(("step", worker_slots))
            active_workers.append(worker_index)
        self._receive_all(active_workers, expected="step")

        indices = np.asarray(slots, dtype=np.int64)
        summaries = tuple(self._summary_for_slot(slot) for slot in slots)
        return ParallelStepBatch(
            next_states=np.array(self._states[indices], copy=True),
            rewards=np.array(self._rewards[indices], copy=True),
            dones=np.array(self._dones[indices], copy=True),
            summaries=summaries,
        )

    def close(self) -> None:
        """Stop workers and release all shared-memory segments."""
        if self._closed:
            return
        self._closed = True
        for connection in self._connections:
            try:
                connection.send(("close", None))
            except (BrokenPipeError, EOFError, OSError):
                pass

        for worker_index, connection in enumerate(self._connections):
            try:
                if connection.poll(2.0):
                    message = connection.recv()
                    if message[0] == "closed":
                        self._worker_cpu_seconds[worker_index] = float(message[1])
            except (BrokenPipeError, EOFError, OSError):
                pass
            connection.close()
        for process in self._processes:
            process.join(timeout=5.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
        for shared_memory in self._shared_memory:
            shared_memory.close()
            try:
                shared_memory.unlink()
            except FileNotFoundError:
                pass

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass

    def _create_array(self, shape: tuple[int, ...], dtype: np.dtype[Any]) -> np.ndarray:
        item_count = int(np.prod(shape))
        shared_memory = SharedMemory(create=True, size=item_count * dtype.itemsize)
        self._shared_memory.append(shared_memory)
        array = np.ndarray(shape, dtype=dtype, buffer=shared_memory.buf)
        array.fill(0)
        return array

    def _array_specs(self) -> tuple[tuple[str, tuple[int, ...], str], ...]:
        arrays = (
            self._states,
            self._action_masks,
            self._action_features,
            self._actions,
            self._rewards,
            self._dones,
            self._summary_valid,
            self._summary_total_reward,
            self._summary_steps,
            self._summary_turn,
            self._summary_winner,
            self._summary_player_hp,
            self._summary_enemy_hp,
        )
        return tuple(
            (shared_memory.name, array.shape, array.dtype.str)
            for shared_memory, array in zip(self._shared_memory, arrays)
        )

    def _receive_all(self, worker_indices: Sequence[int], *, expected: str) -> None:
        for worker_index in worker_indices:
            message = self._connections[worker_index].recv()
            self._record_worker_message(worker_index, message, expected=expected)

    def _record_worker_message(
        self,
        worker_index: int,
        message: tuple[str, float | str],
        *,
        expected: str,
    ) -> None:
        status, payload = message
        if status == "error":
            raise RuntimeError(
                f"PPO environment worker {worker_index} failed:\n{payload}"
            )
        if status != expected:
            raise RuntimeError(
                f"PPO environment worker {worker_index} returned {status!r}; "
                f"expected {expected!r}."
            )
        self._worker_cpu_seconds[worker_index] = float(payload)

    def _summary_for_slot(self, slot: int) -> EpisodeSummary | None:
        if not self._summary_valid[slot]:
            return None
        winner_code = int(self._summary_winner[slot])
        winner = (
            "player"
            if winner_code == 1
            else "enemy" if winner_code == -1 else None
        )
        return EpisodeSummary(
            total_reward=float(self._summary_total_reward[slot]),
            steps=int(self._summary_steps[slot]),
            final_turn=int(self._summary_turn[slot]),
            winner=winner,
            player_hp=int(self._summary_player_hp[slot]),
            enemy_hp=int(self._summary_enemy_hp[slot]),
        )


def _environment_worker_main(
    connection: Connection,
    env_factory: Callable[[], CombatEnv],
    slots: tuple[int, ...],
    array_specs: tuple[tuple[str, tuple[int, ...], str], ...],
    worker_index: int,
) -> None:
    del worker_index
    shared_memory: list[SharedMemory] = []
    try:
        arrays = []
        for name, shape, dtype_string in array_specs:
            segment = SharedMemory(name=name)
            shared_memory.append(segment)
            arrays.append(
                np.ndarray(shape, dtype=np.dtype(dtype_string), buffer=segment.buf)
            )
        (
            states,
            action_masks,
            action_features,
            actions,
            rewards,
            dones,
            summary_valid,
            summary_total_reward,
            summary_steps,
            summary_turn,
            summary_winner,
            summary_player_hp,
            summary_enemy_hp,
        ) = arrays
        environments = {slot: env_factory() for slot in slots}
        connection.send(("ready", process_time()))

        while True:
            command, payload = connection.recv()
            if command == "close":
                connection.send(("closed", process_time()))
                return
            if command == "reset":
                for slot, episode_seed in payload:
                    observation = environments[slot].reset(seed=episode_seed)
                    _write_policy_state(
                        environments[slot],
                        observation,
                        slot,
                        states,
                        action_masks,
                        action_features,
                    )
                connection.send(("reset", process_time()))
                continue
            if command != "step":
                raise ValueError(f"Unknown PPO worker command: {command!r}")

            for slot in payload:
                environment = environments[slot]
                next_observation, reward, done, _info = environment.step_discrete(
                    int(actions[slot])
                )
                rewards[slot] = reward
                dones[slot] = done
                states[slot] = environment.encode_observation(next_observation)
                if done:
                    action_masks[slot].fill(False)
                    action_features[slot].fill(0.0)
                    summary = environment.get_episode_summary()
                    summary_valid[slot] = True
                    summary_total_reward[slot] = summary.total_reward
                    summary_steps[slot] = summary.steps
                    summary_turn[slot] = summary.final_turn
                    summary_winner[slot] = (
                        1
                        if summary.winner == "player"
                        else -1 if summary.winner == "enemy" else 0
                    )
                    summary_player_hp[slot] = summary.player_hp
                    summary_enemy_hp[slot] = summary.enemy_hp
                else:
                    summary_valid[slot] = False
                    action_mask, features = environment.encode_policy_inputs(
                        next_observation
                    )
                    action_masks[slot] = action_mask
                    action_features[slot] = features
            connection.send(("step", process_time()))
    except BaseException:
        try:
            connection.send(("error", traceback.format_exc()))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()
        for segment in shared_memory:
            segment.close()


def _write_policy_state(
    environment: CombatEnv,
    observation: Observation,
    slot: int,
    states: np.ndarray,
    action_masks: np.ndarray,
    action_features: np.ndarray,
) -> None:
    states[slot] = environment.encode_observation(observation)
    action_mask, features = environment.encode_policy_inputs(observation)
    action_masks[slot] = action_mask
    action_features[slot] = features
