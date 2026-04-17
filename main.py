"""Demo script for running a single combat episode."""

from __future__ import annotations

from game import CombatAction, CombatEnv, choose_heuristic_action


def describe_action(action: CombatAction, observation: dict[str, object]) -> str:
    """Render an action in a human-friendly format."""
    if action[0] == "end_turn":
        return "end turn"

    hand = observation["hand"]
    enemies = observation.get("enemies", [observation["enemy"]])
    assert isinstance(hand, list)
    assert isinstance(enemies, list)
    hand_index = action[1]
    if len(action) == 2:
        return f"play hand[{hand_index}] -> {hand[hand_index]}"

    target_index = action[2]
    target_enemy = enemies[target_index]
    assert isinstance(target_enemy, dict)
    return (
        f"play hand[{hand_index}] -> {hand[hand_index]} "
        f"on enemy[{target_index}] {target_enemy['name']}"
    )


def format_observation(observation: dict[str, object]) -> str:
    """Format an observation for line-based demo output."""
    player = observation["player"]
    enemies = observation.get("enemies", [observation["enemy"]])
    hand = observation["hand"]
    assert isinstance(player, dict)
    assert isinstance(enemies, list)
    assert isinstance(hand, list)
    player_statuses = player["statuses"]
    assert isinstance(player_statuses, dict)

    enemy_lines: list[str] = []
    for enemy_index, enemy in enumerate(enemies):
        assert isinstance(enemy, dict)
        intent = enemy["intent"]
        enemy_statuses = enemy["statuses"]
        assert isinstance(intent, dict)
        assert isinstance(enemy_statuses, dict)
        enemy_lines.append(
            f"  Enemy {enemy_index}: {enemy['name']} | "
            f"HP {enemy['hp']}/{enemy['max_hp']} | Block {enemy['block']} | "
            f"Str {enemy.get('strength', 0)} | Status {enemy_statuses} | "
            f"Intent {intent['move_name']} ({intent['kind']} {intent['value']})"
        )
    enemy_summary = "\n".join(enemy_lines)

    return (
        f"Turn {observation['turn']}\n"
        f"  Player: HP {player['hp']}/{player['max_hp']} | "
        f"Block {player['block']} | Energy {player['energy']} | "
        f"Str {player.get('strength', 0)} | Status {player_statuses}\n"
        f"{enemy_summary}\n"
        f"  Hand:   {list(enumerate(hand))}\n"
        f"  Piles:  draw={observation['draw_pile_size']} "
        f"discard={observation['discard_pile_size']} "
        f"exhaust={observation['exhaust_pile_size']}"
    )


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
