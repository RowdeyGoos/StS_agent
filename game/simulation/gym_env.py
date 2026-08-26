"""Optional Gymnasium wrapper for the combat environment."""

from __future__ import annotations

from typing import Any

from .core import CombatEnv

try:
    import gymnasium as gym
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - depends on optional dependency
    gym = None
    np = None


if gym is not None and np is not None:

    class GymCombatEnv(gym.Env):
        """Gymnasium-compatible wrapper around :class:`CombatEnv`."""

        metadata = {"render_modes": ["ansi"]}

        def __init__(
            self,
            combat_env: CombatEnv | None = None,
            **combat_env_kwargs: Any,
        ) -> None:
            super().__init__()
            if combat_env is not None and combat_env_kwargs:
                raise ValueError(
                    "Provide either an existing CombatEnv or keyword arguments, not both."
                )

            self.combat_env = combat_env or CombatEnv(**combat_env_kwargs)
            self.action_space = gym.spaces.Discrete(self.combat_env.action_space_size)
            self.observation_space = gym.spaces.Box(
                low=np.zeros(self.combat_env.observation_size, dtype=np.float32),
                high=np.full(self.combat_env.observation_size, np.inf, dtype=np.float32),
                dtype=np.float32,
            )

        def reset(
            self,
            *,
            seed: int | None = None,
            options: dict[str, Any] | None = None,
        ) -> tuple["np.ndarray", dict[str, Any]]:
            del options
            raw_observation = self.combat_env.reset(seed=seed)
            encoded_observation = np.asarray(
                self.combat_env.encode_observation(raw_observation),
                dtype=np.float32,
            )
            info = {
                "action_mask": np.asarray(
                    self.combat_env.get_action_mask(),
                    dtype=np.int8,
                ),
                "raw_observation": raw_observation,
            }
            return encoded_observation, info

        def step(
            self, action: int
        ) -> tuple["np.ndarray", float, bool, bool, dict[str, Any]]:
            raw_observation, reward, done, info = self.combat_env.step_discrete(action)
            encoded_observation = np.asarray(
                self.combat_env.encode_observation(raw_observation),
                dtype=np.float32,
            )

            gym_info = dict(info)
            gym_info["action_mask"] = np.asarray(info["action_mask"], dtype=np.int8)
            gym_info["raw_observation"] = raw_observation
            if done and "episode_summary" in info:
                gym_info["episode"] = dict(info["episode_summary"])

            return encoded_observation, reward, done, False, gym_info

        def render(self) -> str:
            """Return a compact ANSI-friendly text rendering."""
            observation = self.combat_env.get_observation()
            player = observation["player"]
            enemies = observation.get("enemies", [observation["enemy"]])
            enemy_fragments = []
            for enemy in enemies:
                assert isinstance(enemy, dict)
                intent = enemy["intent"]
                enemy_fragments.append(
                    f"{enemy['name']} HP {enemy['hp']}/{enemy['max_hp']} "
                    f"Block {enemy['block']} Intent {intent['move_name']} ({intent['kind']} {intent['value']})"
                )
            return (
                f"Turn {observation['turn']} | "
                f"Player HP {player['hp']}/{player['max_hp']} "
                f"Block {player['block']} Energy {player['energy']} | "
                f"Enemies: {' ; '.join(enemy_fragments)}"
            )

        def close(self) -> None:
            """Close the wrapper. Included for Gymnasium parity."""

else:

    class GymCombatEnv:
        """Placeholder wrapper that raises a helpful error without Gymnasium installed."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "GymCombatEnv requires the optional dependencies 'gymnasium' and 'numpy'. "
                "Install them with `pip install -r requirements.txt` or `pip install -e .[rl]`."
            )
