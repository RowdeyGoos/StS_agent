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
from game.headless.cards.operations import ChoosePileCard
from game.headless.core.card_state import CardState
from game.headless.monsters.base import Intent
from game.headless.monsters.catalog import DEFAULT_MONSTERS
from game.headless.powers.status import StatusCollection

from game.headless.enchantments import base as enchantments

SCHEMA = "headless_combat_state_v37"
PILES = ("draw_pile", "discard_pile", "exhaust_pile", "hand", "in_play", "powers", "offered", "sequestered")
PLAYER_FIELDS = ("max_hp", "hp", "block", "energy_per_turn", "energy", "strength")


def card_record(card) -> dict:
    enchantments.validate(card)
    from copy import deepcopy
    return {**({"event_data": deepcopy(card.event_data)} if card.definition.definition_id == "mad_science" else {}), "definition_id": card.definition.definition_id,
            "instance_id": card.instance_id, "upgrade_level": card.upgrade_level, "combats_seen": card.combats_seen,
            "permanent_damage": card.permanent_damage, "permanent_block": card.permanent_block, "enchantment": enchantments.record(card), "combat_state": asdict(card.combat_state)}


def restore_card(record, cards=DEFAULT_CARDS):
    if set(record) - ({"event_data"} if record.get("definition_id") == "mad_science" else set()) != {"definition_id", "instance_id", "upgrade_level", "combats_seen", "permanent_damage", "permanent_block", "enchantment", "combat_state"}:
        raise ValueError("Invalid card state fields.")
    if not isinstance(record["instance_id"], str) or not record["instance_id"]:
        raise ValueError("Invalid card instance ID.")
    card = cards.create(record["definition_id"], instance_id=record["instance_id"], upgrade_level=record["upgrade_level"])
    if card.definition.definition_id == "mad_science":
        from game.headless.cards.extended_events import RIDERS
        from copy import deepcopy
        data = record.get("event_data")
        if not isinstance(data, dict) or set(data) != {"kind", "rider"} or data["kind"] not in RIDERS or data["rider"] not in RIDERS[data["kind"]]:
            raise ValueError("Invalid Mad Science configuration.")
        card.event_data = deepcopy(data)
    count = record["combats_seen"]
    if type(count) is not int or not 0 <= count < max(1, card.definition.combat_lifetime):
        raise ValueError("Invalid card combat lifetime.")
    card.combats_seen = count
    growth = record['permanent_damage']
    if type(growth) is not int or growth < 0 or (growth and card.definition.definition_id != 'the_scythe'):
        raise ValueError('Invalid permanent card damage.')
    card.permanent_damage = growth
    growth = record['permanent_block']
    if type(growth) is not int or growth < 0 or (growth and card.definition.definition_id != 'genetic_algorithm'):
        raise ValueError('Invalid permanent card block.')
    card.permanent_block = growth
    values = record["combat_state"]
    if not isinstance(values, dict) or set(values) != set(asdict(CardState())) or type(values['extra_damage']) is not int or values['extra_damage'] < 0 or type(values['cost_change']) is not int or type(values['turn_cost_change']) is not int or type(values['combat_cost_change']) is not int or any(type(values[k]) is not bool for k in ('galvanized', 'hexed', 'bound', 'tainted', 'smog', 'is_dupe', 'free_this_turn', 'star_free_this_turn', 'free_this_combat', 'free_until_played', 'return_next_turn', 'sly_this_turn', 'sly_this_combat', 'retain_this_turn', 'retain_this_combat', 'all_enemies', 'ethereal_this_combat', 'turn_cost_until_played')) or type(values['replay_count']) is not int or values['replay_count'] < 0:
        raise ValueError('Invalid transient card state.')
    if any(type(values[k]) is not int for k in ('override_turn_baseline', 'override_combat_baseline', 'combat_override_baseline')):
        raise ValueError('Invalid cost override baselines.')
    if values['turn_cost_override'] is not None and (type(values['turn_cost_override']) is not int or not 0 <= values['turn_cost_override'] <= 3):
        raise ValueError('Invalid temporary cost override.')
    if values["combat_cost_override"] is not None and (type(values["combat_cost_override"]) is not int or not 0 <= values["combat_cost_override"] <= 3):
        raise ValueError("Invalid combat cost override.")
    from game.headless.core.card_costs import validate as validate_costs
    validate_costs(values)
    if any(type(values[k]) is not int or values[k] < 0 for k in ('wither_level', 'dampened_levels')):
        raise ValueError('Invalid Glory card counters.')
    card.combat_state = CardState(**values)
    card.enchantment = enchantments.restore(record["enchantment"])
    enchantments.validate(card)
    return card


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
                   "rules": asdict(engine.player.rules), "cards_played_this_turn": engine.player.cards_played_this_turn, "power_sources": dict(engine.player.power_sources)},
        "deck": {"rng": rng_ref(deck.rng), "niche_rng": rng_ref(deck.niche_rng), "selection_rng": rng_ref(deck.selection_rng), "target_rng": rng_ref(deck.target_rng), "generation_rng": rng_ref(deck.generation_rng), "potion_rng": rng_ref(deck.potion_rng), "energy_rng": rng_ref(deck.energy_rng), "orb_rng": rng_ref(deck.orb_rng), "original_ids": sorted(deck.original_ids), "next_instance_id": deck._next_instance_id,
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
            if isinstance(state, dict):
                from game.headless.core.native_rng import NativeRng
                rng = NativeRng(0)
                rng.setstate(state)
            else:
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
        deck.niche_rng = rng_at(source_deck["niche_rng"])
        deck.selection_rng = rng_at(source_deck["selection_rng"])
        deck.target_rng = rng_at(source_deck["target_rng"])
        deck.generation_rng = rng_at(source_deck["generation_rng"])
        deck.potion_rng = rng_at(source_deck["potion_rng"])
        deck.energy_rng = rng_at(source_deck["energy_rng"])
        deck.orb_rng = rng_at(source_deck["orb_rng"])
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
        deck.original_ids = set(source_deck["original_ids"])
        if (not isinstance(source_deck["original_ids"], list) or len(deck.original_ids) != len(source_deck["original_ids"])
                or not deck.original_ids <= deck._allocated_ids):
            raise ValueError("Invalid original card identities.")
        player = Player(deck)
        for name in PLAYER_FIELDS:
            value = snapshot["player"][name]
            if type(value) is not int or (value < 0 and name != "strength"):
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
        winner = "player" if not any(e.is_alive or e.prevents_combat_end for e in enemies) else "enemy" if not player.is_alive else None
        if type(snapshot["done"]) is not bool or snapshot["done"] != (winner is not None) or snapshot["winner"] != winner:
            raise ValueError("Invalid terminal state.")
        config = snapshot["config"]
        if set(config) != {"player_max_hp", "energy_per_turn", "cards_per_turn"} or any(type(v) is not int or v < 0 for v in config.values()) or config["player_max_hp"] <= 0:
            raise ValueError("Invalid combat configuration.")
        if player.max_hp != config["player_max_hp"] + snapshot["player"]["rules"]["max_hp_gained"]:
            raise ValueError("Player maximum HP differs from the combat configuration.")
        if any(c.spec.kind != 'power' for c in deck.powers):
            raise ValueError('Only played power cards belong in the powers pile.')
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
        from game.headless.core.rule_snapshots import restore_rules
        player.catalog = cards
        restore_rules(snapshot["player"]["rules"], player)
        from game.headless.encounters.theft import validate_combat
        validate_combat(player)
        for enemy in enemies:
            enemy.validate_combat_context(player)
        from game.headless.powers.glory import validate as validate_glory
        validate_glory(player)
        player.catalog = cards
        pending = snapshot["pending_play"]
        if ((player.rules.active_hook or player.rules.deferred_hooks)
                and pending is None and player.rules.selection is None):
            raise ValueError("Saved hook work requires an active decision.")
        if pending is None:
            if deck.in_play and player.rules.selection is None:
                raise ValueError("In-play cards require a pending continuation.")
        else:
            if player.rules.selection is not None:
                raise ValueError("Multiple simultaneous selectors.")
            if not isinstance(pending, dict) or set(pending) != {"effect_index", "target_slot"}:
                raise ValueError("Invalid pending card play fields.")
            if winner is not None or not deck.in_play:
                raise ValueError("Pending choice requires one resolving card in active combat.")
            card = player.current_card
            if card is None:
                raise ValueError("Pending choice has no active card.")
            index, slot = pending["effect_index"], pending["target_slot"]
            if type(index) is not int or not 0 <= index < len(card.definition.effects):
                raise ValueError("Invalid pending effect index.")
            if card.spec.uses_target:
                if type(slot) is not int or not 0 <= slot < len(enemies):
                    raise ValueError("Invalid pending target slot.")
            elif slot is not None:
                raise ValueError("Untargeted pending play cannot have a target.")
            if player.rules.plays[card.instance_id]['effect_index'] != index:
                raise ValueError('Pending effect differs from its play.')
            if player.rules.plays[card.instance_id]['target'] != slot:
                raise ValueError('Pending target differs from its play.')
            effect = card.definition.effects[index]
            if not isinstance(effect, (SelectHandCard, ChoosePileCard)) or effect.mode_for(card) != "choose" or len(effect.eligible(player)) < (1 if player.rules.active_hook else 2):
                raise ValueError("Pending effect does not require a hand choice.")
            player.pending_play = PendingCardPlay(index, slot)
        return {**config, "rng": rng_at(snapshot["combat_rng"]), "player": player,
                "enemies": enemies, "turn": snapshot["turn"], "done": snapshot["done"], "winner": winner}
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError("Invalid combat snapshot.") from error
