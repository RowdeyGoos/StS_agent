"""Resume enemy-side work after a reactive draw interrupts an individual hit."""

from dataclasses import asdict
from game.headless.monsters.base import Intent
from game.headless.core.resolution import drain


def paused(p):
    return p.pending_play is not None or p.rules.selection is not None


def turn_order(enemies):
    """Native slot execution order without moving stable targeting indices."""
    return sorted(range(len(enemies)), key=lambda i: getattr(enemies[i], 'turn_order', i))


def action_details(actions):
    """Keep private roll receipts out of the existing action-result contract."""
    return [{k: v for k, v in action.items() if k != "roll_next"} for action in actions]


def current_slot(record):
    return record.get('order', range(record['limit']))[record['slot']]


def execute(enemy, player, continuation):
    current = Intent(**continuation["intent"])
    if enemy.stunned and current.kind == "stun" and continuation["hit"] == 0:
        enemy.stunned = False
        continuation["stage"] = "done"
        return
    # A dead attacker still completes its captured AfterAttack listeners. Its
    # remaining hits and move effects are skipped after that command boundary.
    while (continuation["stage"] == "hits" and continuation["hit"] < current.attack_count
           and player.is_alive and enemy.is_alive and not player.combat_is_ending):
        continuation["hit"] += 1
        enemy.execute_hit(player, current)
        drain(player)
        if paused(player): return
    if continuation["stage"] == "hits":
        continuation["stage"] = "effects"
        if current.attack_count and continuation['hit']:
            enemy.after_attack(player, current)
            drain(player)
            if paused(player): return
    if not player.is_alive or not enemy.can_take_turn or player.combat_is_ending or (not enemy.is_alive and current.attack_count):
        continuation['stage'] = 'done'
        return
    if continuation["stage"] == "effects":
        continuation["stage"] = "advance"
        enemy.execute_after_hits(player, current)
        drain(player)
        if paused(player): return
    if continuation["stage"] == "advance":
        from game.headless.monsters.scripted import DeferredMoveEnemy
        if isinstance(enemy, DeferredMoveEnemy) or getattr(enemy, 'move_interrupted', False):
            # Existing roster rolls retain their owned pending flag. Forced state
            # changes must consume their interrupted-move marker before cleanup.
            enemy.advance_intent()
            continuation["stage"] = "done"
        else:
            enemy.turn_roll_pending = True
            continuation["stage"] = "deferred"


def begin(enemy):
    if not enemy.stunned:
        enemy.before_move(enemy.combat_player)
    return {"intent": asdict(enemy.intent), "hit": 0, "stage": "hits"}


def validate(record, player):
    if record is None:
        if any(e.turn_roll_pending for e in player.combat_enemies):
            raise ValueError('Unowned enemy move roll.')
        return
    if not isinstance(record, dict) or set(record) - {"poison_start", "started", "doom_end", "order"} != {"limit", "slot", "move", "actions"}:
        raise ValueError("Invalid enemy-side continuation.")
    if player.rules.player_side or any(type(record[k]) is not int for k in ("limit", "slot")):
        raise ValueError("Invalid enemy-side ownership.")
    order = record.get('order')
    expected = turn_order(player.combat_enemies[:record['limit']])
    if (order is not None and (not isinstance(order, list) or any(type(i) is not int for i in order))) or (order if order is not None else list(range(record['limit']))) != expected:
        raise ValueError('Invalid enemy execution order.')
    actions = record['actions']
    if (not isinstance(actions, list) or len(actions) > record['slot']
            or any(not isinstance(a, dict) or set(a) != {'enemy_index', 'enemy_name', 'intent', 'roll_next'}
                   or type(a['roll_next']) is not bool or type(a['enemy_index']) is not int
                   or a['enemy_index'] not in expected[:record['slot']] for a in actions)
            or len({a['enemy_index'] for a in actions}) != len(actions)):
        raise ValueError('Invalid completed enemy actions.')
    rolls = {a['enemy_index'] for a in actions if a['roll_next']}
    if any(e.turn_roll_pending != (i in rolls) for i, e in enumerate(player.combat_enemies)):
        raise ValueError('Enemy move roll differs from its completed action.')
    if record.get('doom_end') is True:
        if record['slot'] != record['limit'] or not 0 < record['limit'] <= len(player.combat_enemies) or record['move'] is not None or not isinstance(record['actions'], list):
            raise ValueError('Invalid enemy Doom boundary.')
        return
    if 'doom_end' in record:
        raise ValueError('Invalid enemy Doom marker.')
    if not 0 <= record["slot"] < record["limit"] <= len(player.combat_enemies):
        raise ValueError("Invalid enemy-side cursor.")
    if "started" in record and record["started"] is not True:
        raise ValueError("Invalid side-start marker.")
    if "poison_start" in record:
        if record["poison_start"] is not True or record.get("started") is not True or record["slot"] != 0 or record["move"] is not None or record["actions"]:
            raise ValueError("Invalid poison side-start continuation.")
        return
    move = record["move"]
    if not isinstance(move, dict) or set(move) != {"intent", "hit", "stage"}:
        raise ValueError("Invalid enemy move continuation.")
    intent = Intent(**move["intent"])
    if (
        type(move["hit"]) is not int
        or not 0 <= move["hit"] <= intent.attack_count
        or move["stage"] not in ("hits", "effects", "advance")
    ):
        raise ValueError("Invalid enemy hit cursor.")
    if asdict(player.combat_enemies[current_slot(record)].continuation_intent()) != asdict(intent):
        raise ValueError("Enemy continuation differs from its current move.")
    if move["stage"] in ("effects", "advance") and move["hit"] != intent.attack_count and player.combat_enemies[current_slot(record)].is_alive:
        raise ValueError("Enemy continuation skips unfinished hits.")
