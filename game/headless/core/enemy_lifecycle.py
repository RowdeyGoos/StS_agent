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


def attack_boundary(player, card, *, before):
    if any(e.TRACKS_CARD_ATTACKS for e in player.combat_enemies or ()):
        return [['begin_card_attack' if before else 'end_card_attack', card.instance_id]]
    return []


def attack_tasks(player, card, tasks):
    return attack_boundary(player, card, before=True) + tasks + attack_boundary(player, card, before=False)


def finish_card_attack(player, frame):
    for enemy in tuple(player.combat_enemies or ()):
        enemy.after_card_attack(frame)
    frame.pop('enemy_attack', None)
