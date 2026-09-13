"""Black-box characterization of the legacy ``combat_v0`` environment.

These tests intentionally exercise only the existing ``CombatEnv`` and
``CombatEnvFactory`` interfaces.  They are regression evidence for the Python
simulator (``combat_v0``), not evidence of target-game parity or a policy-input
contract for a future live backend.
"""

from __future__ import annotations

from copy import deepcopy

from pytest import approx

from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy
from game.simulation.env_factory import CombatEnvFactory


def _combat_summary(observation: dict[str, object]) -> dict[str, object]:
    """Keep golden assertions readable while retaining structured API fields."""
    player = observation["player"]
    enemies = observation["enemies"]
    assert isinstance(player, dict)
    assert isinstance(enemies, list)
    return {
        "turn": observation["turn"],
        "player": player,
        "enemy_count": observation["enemy_count"],
        "living_enemy_count": observation["living_enemy_count"],
        "hand": observation["hand"],
        "pile_sizes": (
            observation["draw_pile_size"],
            observation["discard_pile_size"],
            observation["exhaust_pile_size"],
        ),
        "enemies": [
            {
                "name": enemy["name"],
                "hp": enemy["hp"],
                "max_hp": enemy["max_hp"],
                "block": enemy["block"],
                "strength": enemy["strength"],
                "statuses": enemy["statuses"],
                "intent": enemy["intent"],
                "behavior_state": enemy["behavior_state"],
                "alive": enemy["alive"],
            }
            for enemy in enemies
        ],
        "card_counts": observation["card_counts"],
    }


def test_combat_v0_fixed_seed_single_enemy_trace_and_shaped_diagnostics() -> None:
    """``combat_v0``: freeze one public, fixed-seed single-enemy trace."""
    env = CombatEnv(
        seed=17,
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        incoming_damage_shaping_scale=0.5,
    )

    initial = env.reset()

    assert _combat_summary(initial) == {
        "turn": 1,
        "player": {
            "hp": 80,
            "max_hp": 80,
            "block": 0,
            "energy": 3,
            "energy_per_turn": 3,
            "strength": 0,
            "statuses": {"shrink": 0, "vulnerable": 0},
        },
        "enemy_count": 1,
        "living_enemy_count": 1,
        "hand": ["Defend", "Defend", "Strike", "Strike", "Bash"],
        "pile_sizes": (5, 0, 0),
        "enemies": [
            {
                "name": "SimpleEnemy",
                "hp": 20,
                "max_hp": 20,
                "block": 0,
                "strength": 0,
                "statuses": {"shrink": 0, "vulnerable": 0},
                "intent": {
                    "kind": "attack",
                    "value": 6,
                    "move_name": "Strike",
                    "attack_damage": 6,
                    "attack_count": 1,
                    "block_gain": 0,
                    "strength_gain": 0,
                    "status_name": None,
                    "status_stacks": 0,
                    "slimed_added": 0,
                },
                "behavior_state": {
                    "phase_index": 0,
                    "phase_count": 3,
                    "possible_next_move_names": ["Defend"],
                },
                "alive": True,
            }
        ],
        "card_counts": {
            "hand": {"Bash": 1, "Defend": 2, "Strike": 2},
            "draw_pile": {"Defend": 2, "Strike": 3},
            "discard_pile": {},
            "exhaust_pile": {},
        },
    }
    assert env.get_legal_actions() == [
        ("end_turn",),
        ("play", 0),
        ("play", 1),
        ("play", 2),
        ("play", 3),
        ("play", 4),
    ]

    next_observation, reward, done, info = env.step(("play", 0))

    assert not done
    assert reward == approx(0.03125)
    assert next_observation["player"]["block"] == 5
    assert next_observation["player"]["energy"] == 2
    assert next_observation["hand"] == ["Defend", "Strike", "Strike", "Bash"]
    assert next_observation["discard_pile_size"] == 1
    assert info == {
        "played_card": "Defend",
        "target_enemy_index": 0,
        "target_enemy_name": "SimpleEnemy",
        "player_hp_lost": 0,
        "hp_loss_penalty": 0.0,
        "raw_hp_loss_penalty": 0.0,
        "projected_incoming_hp_loss_before": 6,
        "projected_incoming_hp_loss_after": 1,
        "incoming_damage_reduction_bonus": 0.03125,
        "action_mask": (1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0),
    }


def test_combat_v0_fixed_seed_multi_enemy_actions_are_complete_and_canonical() -> None:
    """Regress public actions against the shared engine's corrected slime layout.

    The September 13 source check corrected small/medium/small slots and move
    sampling. This current regression is not a repin of historical artifacts.
    """
    env = CombatEnvFactory(
        encounter_set="slimes",
        incoming_damage_shaping_scale=0.5,
        record_trajectory=False,
    )()

    observation = env.reset(seed=17)

    assert [enemy["name"] for enemy in observation["enemies"]] == [
        "Leaf Slime (S)",
        "Twig Slime (M)",
        "Twig Slime (S)",
    ]
    assert [enemy["hp"] for enemy in observation["enemies"]] == [13, 27, 10]
    assert [enemy["intent"]["move_name"] for enemy in observation["enemies"]] == [
        "Goop",
        "Sticky Shot",
        "Tackle",
    ]
    # Non-targeted Defend is canonicalized to the first living target; attacks
    # appear once for each living stable enemy slot.
    assert env.get_legal_actions() == [
        ("end_turn",),
        ("play", 0, 0),
        ("play", 1, 0),
        ("play", 2, 0),
        ("play", 2, 1),
        ("play", 2, 2),
        ("play", 3, 0),
        ("play", 3, 1),
        ("play", 3, 2),
        ("play", 4, 0),
        ("play", 4, 1),
        ("play", 4, 2),
    ]

    next_observation, reward, done, info = env.step(("play", 0, 0))

    assert not done
    assert reward == approx(0.025)
    assert next_observation["player"]["block"] == 5
    assert info["projected_incoming_hp_loss_before"] == 4
    assert info["projected_incoming_hp_loss_after"] == 0
    assert info["incoming_damage_reduction_bonus"] == approx(0.025)
    assert info["action_mask"] == (
        1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )


def test_combat_v0_reset_is_deterministic_and_fresh_observations_are_detached() -> None:
    """``combat_v0``: fresh ``get_observation()`` snapshots cannot mutate state."""
    env = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)()
    first = env.reset(seed=29)
    second = env.reset(seed=29)
    assert second == first

    baseline = env.get_observation()
    mutated = env.get_observation()
    mutated["player"]["hp"] = -1
    mutated["enemies"][0]["intent"]["move_name"] = "tampered"
    mutated["enemies"][0]["behavior_state"]["possible_next_move_names"].append(
        "tampered"
    )
    mutated["card_counts"]["hand"].clear()

    assert env.get_observation() == baseline


def test_combat_v0_reset_and_step_returns_alias_last_observation_diagnostics() -> None:
    """``combat_v0`` legacy ambiguity: returned transition observations alias history.

    This records existing simulator behavior, not a desired public/headless
    boundary: mutations do not change authoritative combat state, but they do
    change the ``last_observation`` used by subsequent reward diagnostics.
    """
    reset_env = CombatEnv(
        seed=17,
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        incoming_damage_shaping_scale=0.5,
    )
    reset_observation = reset_env.reset()
    reset_observation["player"]["block"] = 6

    # Authoritative mutable state remains unchanged, while the aliased reset
    # observation changes the diagnostic baseline consumed by ``step``.
    assert reset_env.get_observation()["player"]["block"] == 0
    _next_observation, reset_reward, reset_done, reset_info = reset_env.step(
        ("play", 0)
    )
    assert not reset_done
    assert reset_reward == approx(-0.00625)
    assert reset_info["projected_incoming_hp_loss_before"] == 0
    assert reset_info["projected_incoming_hp_loss_after"] == 1
    assert reset_info["incoming_damage_reduction_bonus"] == approx(-0.00625)

    step_env = CombatEnv(
        seed=17,
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        incoming_damage_shaping_scale=0.5,
    )
    step_env.reset()
    step_observation, _reward, _done, _info = step_env.step(("play", 0))
    step_observation["player"]["hp"] = 70

    assert step_env.get_observation()["player"]["hp"] == 80
    next_observation, step_reward, step_done, step_info = step_env.step(("end_turn",))
    assert not step_done
    assert next_observation["player"]["hp"] == 79
    assert step_reward == 0.0
    assert step_info["player_hp_lost"] == 0
    assert step_info["hp_loss_penalty"] == 0.0


def test_combat_v0_terminal_victory_and_defeat_summaries() -> None:
    """``combat_v0``: terminal reward and public episode-summary diagnostics."""
    victory_env = CombatEnv(
        seed=3,
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        record_trajectory=True,
    )
    victory_env.reset()
    _victory_observation, victory_reward, victory_done, victory_info = victory_env.step(
        ("play", 0)
    )
    assert victory_done
    assert victory_reward == 1.0
    assert victory_info["episode_summary"] == {
        "total_reward": 1.0,
        "steps": 1,
        "final_turn": 1,
        "winner": "player",
        "player_hp": 80,
        "enemy_hp": 0,
    }

    defeat_env = CombatEnv(
        seed=3,
        player_max_hp=6,
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        record_trajectory=True,
    )
    defeat_env.reset()
    _defeat_observation, defeat_reward, defeat_done, defeat_info = defeat_env.step(
        ("end_turn",)
    )
    assert defeat_done
    assert defeat_reward == -2.0
    assert defeat_info["player_hp_lost"] == 6
    assert defeat_info["hp_loss_penalty"] == -1.0
    assert defeat_info["episode_summary"] == {
        "total_reward": -2.0,
        "steps": 1,
        "final_turn": 1,
        "winner": "enemy",
        "player_hp": 0,
        "enemy_hp": 20,
    }


def test_combat_v0_legacy_field_inventory_is_not_a_policy_input_claim() -> None:
    """``combat_v0`` legacy-field audit: behavior state is simulator diagnostic data.

    ``behavior_state`` (script phase and possible next moves), the compatibility
    ``enemy`` alias, aggregate ``card_counts``, and shaped-reward diagnostics in
    step info are retained here only as legacy simulator behavior.  This test
    does not assert that any of them are deployable policy inputs.
    """
    env = CombatEnv(seed=17, enemy_factory=lambda: SimpleEnemy(max_hp=20))
    observation = env.reset()
    expected = deepcopy(observation)

    assert observation["enemy"] == observation["enemies"][0]
    assert set(observation["enemies"][0]["behavior_state"]) == {
        "phase_index",
        "phase_count",
        "possible_next_move_names",
    }
    assert set(observation["card_counts"]) == {
        "hand",
        "draw_pile",
        "discard_pile",
        "exhaust_pile",
    }
    assert env.get_observation() == expected
