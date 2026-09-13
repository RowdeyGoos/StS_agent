"""A rest-site action grants Byrdpip and replaces all owned eggs in place."""

from copy import deepcopy
from game.headless.core.snapshots import card_record, restore_card
from game.headless.run.inventory import add_relic
from game.headless.enchantments.base import validate as validate_enchantment


def eggs(state):
    return tuple(c.instance_id for c in state.deck if c.definition.definition_id == "byrdonis_egg")


def hatch(state, cards):
    from game.headless.run.rest_site import _pending
    _pending(state, "options")
    if not eggs(state):
        raise ValueError("Hatching requires a Byrdonis Egg.")
    trial = deepcopy(state)
    originals = [card_record(c) for c in state.deck]
    original_relic_ids = [r.instance_id for r in state.relics]
    relic = add_relic(trial, "byrdpip", cards=cards)
    state.deck, state.next_card_id = trial.deck, trial.next_card_id
    state.relics, state.next_item_id = trial.relics, trial.next_item_id
    state.pending = {"kind": "rest_site", "stage": "hatched", "originals": originals,
                     "relic_id": relic.instance_id, "original_relic_ids": original_relic_ids}
    return relic


def validate(state, cards):
    pending = state.pending
    if set(pending) != {"kind", "stage", "originals", "relic_id", "original_relic_ids"} or not isinstance(pending["originals"], list):
        raise ValueError("Invalid hatched rest-site state.")
    originals = [restore_card(row, cards) for row in pending["originals"]]
    for card in originals:
        validate_enchantment(card, permanent=True)
    ids = [c.instance_id for c in originals]
    if len(ids) != len(set(ids)) or not any(c.definition.definition_id == "byrdonis_egg" for c in originals):
        raise ValueError("Hatch requires original eggs.")
    previous = pending["original_relic_ids"]
    if (not isinstance(previous, list) or any(not isinstance(i, str) for i in previous)
            or len(previous) != len(set(previous)) or pending["relic_id"] in previous
            or [r.instance_id for r in state.relics] != [*previous, pending["relic_id"]]):
        raise ValueError("Hatch must grant its own new relic.")
    relic = next((r for r in state.relics if r.instance_id == pending["relic_id"]), None)
    if relic is None or relic.definition_id != "byrdpip":
        raise ValueError("Hatch has no owned Byrdpip.")
    if len(originals) != len(state.deck):
        raise ValueError("Hatch changed deck size.")
    for original, current in zip(originals, state.deck):
        if original.definition.definition_id == "byrdonis_egg":
            if (current.instance_id in ids or current.definition.definition_id != "byrd_swoop"
                    or current.upgrade_level or current.combats_seen or current.enchantment is not None):
                raise ValueError("Egg did not become a fresh base Byrd Swoop.")
        elif card_record(current) != card_record(original):
            raise ValueError("Hatch changed an unrelated card.")
