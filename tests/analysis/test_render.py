"""Human-readable combat rendering tests."""

from game.analysis.render import describe_intent, format_observation
from game.simulation.core import CombatEnv
from game.simulation.enemy import Mawler


def test_multi_hit_intent_rendering_preserves_per_hit_damage() -> None:
    env = CombatEnv(
        seed=0,
        encounter_factory=lambda rng: [Mawler(rng)],
        max_enemy_count=3,
    )
    observation = env.reset()
    intent = observation["enemy"]["intent"]

    assert describe_intent(intent) == "Claw (attack 4 x 2)"
    assert "Intent Claw (attack 4 x 2)" in format_observation(observation)
