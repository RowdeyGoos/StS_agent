"""JSON continuation for owned combat state, independent of any public protocol.

Definitions are supplied by the caller's catalog. RNG aliases are explicit, so
monsters sharing the deck RNG still share it after restoration. Decoding does
not import arbitrary modules or deserialize callables.
"""

from dataclasses import asdict
from random import Random

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.core.selection import PendingCardPlay
from game.headless.cards.effects import SelectHandCard
from game.headless.monsters.base import Intent
from game.headless.monsters.catalog import DEFAULT_MONSTERS
from game.headless.powers.status import StatusCollection

SCHEMA = "headless_combat_state_v5"
PILES = ("draw_pile", "discard_pile", "exhaust_pile", "hand", "in_play")
PLAYER_FIELDS = ("max_hp", "hp", "block", "energy_per_turn", "energy", "strength")


def card_record(card) -> dict:
    return {"definition_id": card.definition.definition_id,
            "instance_id": card.instance_id, "upgrade_level": card.upgrade_level}


def restore_card(record, cards=DEFAULT_CARDS):
    if set(record) != {"definition_id", "instance_id", "upgrade_level"}:
        raise ValueError("Invalid card state fields.")
    if not isinstance(record["instance_id"], str) or not record["instance_id"]:
        raise ValueError("Invalid card instance ID.")
    return cards.create(record["definition_id"], instance_id=record["instance_id"], upgrade_level=record["upgrade_level"])


def _tuple_tree(value):
    return tuple(_tuple_tree(item) for item in value) if isinstance(value, (list, tuple)) else value


def _json_value(value):
    if isinstance(value, Intent):
        return {"intent": asdict(value)}
    if value is None or type(value) in (bool, int, str):
        return value
    raise ValueError(f"Unsupported monster state value: {type(value).__name__}.")


def capture_combat(engine, *, cards=None, monsters=None) -> dict:
    engine._ensure_ready()
    cards = DEFAULT_CARDS if cards is None else cards
    monsters = DEFAULT_MONSTERS if monsters is None else monsters
    rngs = []
    rng_indices = {}
    def rng_ref(rng):
        if id(rng) not in rng_indices:
            rng_indices[id(rng)] = len(rngs)
            rngs.append(rng.getstate())
        return rng_indices[id(rng)]
    enemy_rows = []
    for enemy in engine.enemies:
        kind = type(enemy).__name__
        if monsters.get(kind) is not type(enemy):
            raise ValueError(f"Monster type is not in the supplied catalog: {kind}.")
        enemy_rows.append({
            "type": kind, "rng": rng_ref(enemy.rng), "statuses": dict(enemy.statuses._counts),
            "skip_status_tick": sorted(enemy.statuses._skip_next_tick),
            "state": {name: _json_value(value) for name, value in vars(enemy).items() if name not in ("rng", "statuses", "combat_player")},
        })
    deck = engine.player.deck
    pile_rows = {pile: [card_record(card) for card in getattr(deck, pile)] for pile in PILES}
    for pile in PILES:
        for card in getattr(deck, pile):
            if cards.definition(card.definition.definition_id) != card.definition:
                raise ValueError("Card definition does not match the supplied catalog.")
    return {
        "schema": SCHEMA, "cards": cards.snapshot_fingerprint(), "rngs": rngs, "combat_rng": rng_ref(engine.rng),
        "pending_play": None if engine.player.pending_play is None else asdict(engine.player.pending_play),
        "turn": engine.turn, "done": engine.done, "winner": engine.winner,
        "config": {"player_max_hp": engine.player_max_hp, "energy_per_turn": engine.energy_per_turn, "cards_per_turn": engine.cards_per_turn},
        "player": {**{name: getattr(engine.player, name) for name in PLAYER_FIELDS}, "statuses": dict(engine.player.statuses._counts),
                   "skip_status_tick": sorted(engine.player.statuses._skip_next_tick),
                   "cards_played_this_turn": engine.player.cards_played_this_turn, "power_sources": dict(engine.player.power_sources)},
        "deck": {"rng": rng_ref(deck.rng), "selection_rng": rng_ref(deck.selection_rng), "target_rng": rng_ref(deck.target_rng), "next_instance_id": deck._next_instance_id,
                 "allocated_ids": sorted(deck._allocated_ids), "piles": pile_rows},
        "enemies": enemy_rows,
    }


def restore_combat(snapshot, *, cards=None, monsters=None) -> dict:
    cards = DEFAULT_CARDS if cards is None else cards
    monsters = DEFAULT_MONSTERS if monsters is None else monsters
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        raise ValueError("Incompatible combat snapshot.")
    if snapshot.get("cards") != cards.snapshot_fingerprint():
        raise ValueError("Combat snapshot card definitions are incompatible.")
    try:
        rngs = []
        for state in snapshot["rngs"]:
            rng = Random(0)
            rng.setstate(_tuple_tree(state))
            rngs.append(rng)
        def rng_at(index):
            if type(index) is not int or not 0 <= index < len(rngs):
                raise ValueError("Invalid RNG reference.")
            return rngs[index]
        def statuses(values, skipped):
            result = StatusCollection()
            for name, count in values.items():
                if type(count) is not int or count < 0:
                    raise ValueError("Invalid status count.")
                result.add(name, count)
            if not isinstance(skipped, list) or len(set(skipped)) != len(skipped) or any(
                name not in ("weak", "vulnerable", "frail") or not result.get(name) for name in skipped
            ):
                raise ValueError("Invalid power duration flags.")
            result._skip_next_tick = set(skipped)
            return result
        deck = Deck.__new__(Deck)
        source_deck = snapshot["deck"]
        deck.rng = rng_at(source_deck["rng"])
        deck.selection_rng = rng_at(source_deck["selection_rng"])
        deck.target_rng = rng_at(source_deck["target_rng"])
        deck._next_instance_id = source_deck["next_instance_id"]
        if type(deck._next_instance_id) is not int or deck._next_instance_id < 0:
            raise ValueError("Invalid card allocator.")
        deck._allocated_ids = set(source_deck["allocated_ids"])
        ids = []
        for pile in PILES:
            restored = [restore_card(item, cards) for item in source_deck["piles"][pile]]
            setattr(deck, pile, restored)
            ids.extend(card.instance_id for card in restored)
        if len(ids) != len(set(ids)) or not set(ids) <= deck._allocated_ids:
            raise ValueError("Duplicate or unallocated card IDs in snapshot.")
        player = Player(deck)
        for name in PLAYER_FIELDS:
            value = snapshot["player"][name]
            if type(value) is not int or value < 0:
                raise ValueError("Invalid player state.")
            setattr(player, name, value)
        if not 0 <= player.hp <= player.max_hp or player.max_hp == 0:
            raise ValueError("Invalid player HP.")
        player.statuses = statuses(snapshot["player"]["statuses"], snapshot["player"]["skip_status_tick"])
        enemies = []
        for row in snapshot["enemies"]:
            kind = monsters[row["type"]]
            # Registered constructors define their own state layout. A snapshot
            # can fill those values; it cannot replace methods or inject fields.
            template = kind(rng=Random(0))
            fields = {name: value for name, value in vars(template).items() if name not in ("rng", "statuses", "combat_player")}
            if set(row["state"]) != set(fields):
                raise ValueError("Monster snapshot fields do not match the registered type.")
            enemy = kind.__new__(kind)
            for name, expected in fields.items():
                value = row["state"][name]
                if isinstance(expected, Intent):
                    if not isinstance(value, dict) or set(value) != {"intent"}:
                        raise ValueError("Invalid monster intent state.")
                    value = Intent(**value["intent"])
                elif type(value) not in kind.SNAPSHOT_FIELD_TYPES.get(name, (type(expected),)) or type(value) not in (bool, int, str, type(None)):
                    raise ValueError("Invalid monster state value type.")
                if name in ("block", "_intent_index", "_post_opening_index") and value < 0:
                    raise ValueError("Invalid negative monster state value.")
                setattr(enemy, name, value)
            enemy.rng = rng_at(row["rng"])
            enemy.statuses = statuses(row["statuses"], row["skip_status_tick"])
            if type(enemy.hp) is not int or not 0 <= enemy.hp <= enemy.max_hp or enemy.max_hp <= 0:
                raise ValueError("Invalid enemy HP.")
            enemy.intent  # Verify required behavior fields before installation.
            enemies.append(enemy)
        if not enemies or type(snapshot["turn"]) is not int or snapshot["turn"] < 1:
            raise ValueError("Invalid combat state.")
        winner = "player" if not any(e.is_alive for e in enemies) else "enemy" if not player.is_alive else None
        if type(snapshot["done"]) is not bool or snapshot["done"] != (winner is not None) or snapshot["winner"] != winner:
            raise ValueError("Invalid terminal state.")
        config = snapshot["config"]
        if set(config) != {"player_max_hp", "energy_per_turn", "cards_per_turn"} or any(type(v) is not int or v < 0 for v in config.values()) or config["player_max_hp"] <= 0:
            raise ValueError("Invalid combat configuration.")
        if player.max_hp != config["player_max_hp"]:
            raise ValueError("Player maximum HP differs from the combat configuration.")
        player.combat_enemies = enemies
        count = snapshot["player"]["cards_played_this_turn"]
        if type(count) is not int or count < 0:
            raise ValueError("Invalid card play counter.")
        player.cards_played_this_turn = count
        sources = snapshot["player"]["power_sources"]
        if not isinstance(sources, dict) or any(name not in ("shrink", "constrict") or
                type(slot) is not int or not 0 <= slot < len(enemies) or not enemies[slot].is_alive or
                not player.statuses.get(name) or name not in enemies[slot].APPLIED_PLAYER_POWERS for name, slot in sources.items()):
            raise ValueError("Invalid source-owned power.")
        player.power_sources = dict(sources)
        for enemy in enemies:
            enemy.combat_player = player
            enemy.validate_combat_context(player)
        pending = snapshot["pending_play"]
        if pending is None:
            if deck.in_play:
                raise ValueError("In-play cards require a pending continuation.")
        else:
            if not isinstance(pending, dict) or set(pending) != {"effect_index", "target_slot"}:
                raise ValueError("Invalid pending card play fields.")
            if winner is not None or len(deck.in_play) != 1:
                raise ValueError("Pending choice requires one resolving card in active combat.")
            card = deck.in_play[0]
            index, slot = pending["effect_index"], pending["target_slot"]
            if type(index) is not int or not 0 <= index < len(card.definition.effects):
                raise ValueError("Invalid pending effect index.")
            if card.spec.uses_target:
                if type(slot) is not int or not 0 <= slot < len(enemies):
                    raise ValueError("Invalid pending target slot.")
            elif slot is not None:
                raise ValueError("Untargeted pending play cannot have a target.")
            effect = card.definition.effects[index]
            if not isinstance(effect, SelectHandCard) or effect.mode_for(card) != "choose" or len(effect.eligible(player)) <= 1:
                raise ValueError("Pending effect does not require a hand choice.")
            player.pending_play = PendingCardPlay(index, slot)
        return {**config, "rng": rng_at(snapshot["combat_rng"]), "player": player,
                "enemies": enemies, "turn": snapshot["turn"], "done": snapshot["done"], "winner": winner}
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError("Invalid combat snapshot.") from error
