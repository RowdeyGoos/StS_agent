"""Immediate creature reactions and source cleanup between individual effects."""


def settle_enemies(player):
    enemies = player.combat_enemies
    if enemies is None:
        return
    for enemy in tuple(enemies):
        enemy.combat_player = player
        enemy.on_combat_state_changed(player)
    for name, slot in tuple(player.power_sources.items()):
        if not enemies[slot].is_alive:
            player.statuses.decrement(name, player.statuses.get(name))
            del player.power_sources[name]
    if not any((e.is_alive and not e.statuses.get("minion")) or
               e.prevents_combat_end for e in enemies):
        for enemy in enemies:
            if enemy.statuses.get("minion"):
                enemy.hp = 0
    # Compatibility fixtures can apply Shrink without a recorded native source.
    if "shrink" not in player.power_sources and not any(
            e.is_alive and e.name == "Shrinker Beetle" for e in enemies):
        player.statuses.decrement("shrink", player.statuses.get("shrink"))
