"""Demo script for running a single combat episode."""

from __future__ import annotations

from game import CombatEnv, choose_heuristic_action
from game.render import describe_action, format_observation


def run_demo(seed: int = 7) -> None:
    """Run a single combat episode and print each transition."""
    env = CombatEnv(seed=seed)
    observation = env.reset()
    done = False

    print(f"Combat demo seed={seed}")
    print(
        f"RL interface: observation_size={env.observation_size} "
        f"action_space_size={env.action_space_size}"
    )
    print(f"Initial action mask: {env.get_action_mask()}")
    print(format_observation(observation))

    while not done:
        action_index = choose_heuristic_action(env, observation, env.get_action_mask())
        action = env.decode_action(action_index)
        print(f"\nAction: {describe_action(action, observation)}")
        observation, reward, done, info = env.step(action)

        if "played_card" in info:
            print(f"  Played: {info['played_card']}")
        if "enemy_actions" in info:
            for enemy_action in info["enemy_actions"]:
                intent = enemy_action["intent"]
                print(
                    "  Enemy turn: "
                    f"enemy[{enemy_action['enemy_index']}] {enemy_action['enemy_name']} -> "
                    f"{intent['move_name']} ({intent['kind']} {intent['value']})"
                )
        print(f"  Next action mask: {info['action_mask']}")

        print(format_observation(observation))

        if done:
            outcome = "win" if reward > 0 else "loss"
            print(f"\nCombat finished with a {outcome}. Reward={reward:.1f}")
            print(f"Episode summary: {env.get_episode_summary().as_dict()}")


if __name__ == "__main__":
    run_demo()
