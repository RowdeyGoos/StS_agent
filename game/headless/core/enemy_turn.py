"""Resume enemy-side work after a reactive draw interrupts an individual hit."""

from dataclasses import asdict
from game.headless.monsters.base import Intent
from game.headless.core.resolution import drain


def paused(p):
    return p.pending_play is not None or p.rules.selection is not None


def execute(enemy, player, continuation):
    if not player.is_alive or not enemy.can_take_turn or player.combat_is_ending:
        continuation["stage"] = "done"
        return
    current = Intent(**continuation["intent"])
    if enemy.stunned:
        enemy.stunned = False
        continuation["stage"] = "done"
        return
    while continuation["stage"] == "hits" and continuation["hit"] < current.attack_count:
        continuation["hit"] += 1
        enemy.execute_hit(player, current)
        drain(player)
        if paused(player):
            return
        if not player.is_alive or not enemy.is_alive:
            continuation["stage"] = "done"
            return
    if continuation["stage"] == "hits":
        continuation["stage"] = "advance"
        enemy.execute_after_hits(player, current)
        drain(player)
        if paused(player):
            return
    if continuation["stage"] == "advance":
        enemy.advance_intent()
        continuation["stage"] = "done"


def begin(enemy):
    return {"intent": asdict(enemy.intent), "hit": 0, "stage": "hits"}


def validate(record, player):
    if record is None:
        return
    if not isinstance(record, dict) or set(record) - {"poison_start", "started", "doom_end"} != {"limit", "slot", "move", "actions"}:
        raise ValueError("Invalid enemy-side continuation.")
    if player.rules.player_side or any(type(record[k]) is not int for k in ("limit", "slot")):
        raise ValueError("Invalid enemy-side ownership.")
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
        or move["stage"] not in ("hits", "advance")
    ):
        raise ValueError("Invalid enemy hit cursor.")
    if asdict(player.combat_enemies[record["slot"]].intent) != asdict(intent):
        raise ValueError("Enemy continuation differs from its current move.")
    if move["stage"] == "advance" and move["hit"] != intent.attack_count:
        raise ValueError("Enemy continuation skips unfinished hits.")
    if not isinstance(record["actions"], list) or len(record["actions"]) > record["slot"]:
        raise ValueError("Invalid completed enemy actions.")
