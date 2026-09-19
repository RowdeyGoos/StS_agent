"""Validation of private merchant continuation data, separate from execution."""

from game.headless.run.unknown_rooms import room_node
from game.headless.relics.pools import shop_items

from game.headless.run.shop import eligible_removals, removal_price, discounted
from game.headless.run.state import RunPhase
from game.headless.shops.catalog import SHOP_ID, SLOTS, price


def validate_shop(state, cards, graph):
    from game.headless.generation.merchant import slots_for
    SLOTS = slots_for(state)
    pending = state.pending
    expected = {"kind", "catalog_id", "shop_id", "stage", "offers", "removal_used", "removals_on_entry"}
    if pending.get("stage") == "remove":
        expected.add("eligible")
    if 'parasol_cursor' in pending:
        from game.headless.relics.run_rules import has
        if not has(state, 'lords_parasol') or type(pending['parasol_cursor']) is not int or not 0 <= pending['parasol_cursor'] <= len(pending['offers']) + 1:
            raise ValueError('Invalid Lord’s Parasol cursor.')
        expected.add('parasol_cursor')
    if 'parasol_free_removal' in pending:
        if pending['parasol_free_removal'] is not True or pending['stage'] != 'remove' or pending.get('parasol_cursor') != len(pending['offers']) + 1:
            raise ValueError('Invalid Lord’s Parasol removal.')
        expected.add('parasol_free_removal')
    if set(pending) != expected or pending["catalog_id"] != SHOP_ID:
        raise ValueError("Invalid shop state fields or catalog.")
    if state.phase is not RunPhase.ROOM or pending["stage"] not in ("browse", "remove"):
        raise ValueError("Invalid shop phase.")
    if (type(pending["shop_id"]) is not int or pending["shop_id"] < 0
            or pending["shop_id"] != state.next_shop_id - 1):
        raise ValueError("Invalid owned shop identity.")
    if graph is not None and (state.current_node_id is None or room_node(state, graph, state.current_node_id).kind != "shop"):
        raise ValueError("Shop differs from its selected room.")
    if (type(pending["removal_used"]) is not bool or type(pending["removals_on_entry"]) is not int
            or not 0 <= pending["removals_on_entry"] <= pending["shop_id"]
            or state.shop_removals_used != pending["removals_on_entry"] + int(pending["removal_used"])):
        raise ValueError("Invalid shop removal history.")
    offers = pending["offers"]
    if not isinstance(offers, list) or len(offers) not in (len(SLOTS), len(SLOTS) - 1):
        raise ValueError("Invalid shop inventory.")
    slots, sales = [], 0
    for offer in offers:
        if not isinstance(offer, dict) or set(offer) != {"offer_id", "slot", "definition_id", "kind", "on_sale", "price", "sold", "base_price", "generation", "upgrade_level", "enchantment"}:
            raise ValueError("Invalid shop offer fields.")
        index = offer["slot"]
        if type(index) is not int or not 0 <= index < len(SLOTS):
            raise ValueError("Unknown shop slot.")
        slot = SLOTS[index]
        generation = offer["generation"]
        if type(generation) is not int or generation < 0:
            raise ValueError("Invalid shop refill generation.")
        expected_id = f"shop.{pending['shop_id']}.offer.{index}" + (f".refill.{generation}" if generation else "")
        if offer["offer_id"] != expected_id or offer["kind"] != slot.kind:
            raise ValueError("Invalid shop offer identity.")
        if type(offer["sold"]) is not bool or type(offer["on_sale"]) is not bool or (offer["on_sale"] and (slot.kind != "card" or not slot.sale_eligible)):
            raise ValueError("Invalid shop offer flags.")
        base = dict(shop_items(state, slot)).get(offer["definition_id"])
        if base is None and getattr(state.rng,"native",False):
            if slot.kind=="relic" and offer["definition_id"]=="circlet":base=175
        if base is None:
            raise ValueError("Unknown shop item.")
        if slot.kind == "card":
            card = cards.create(offer["definition_id"], upgrade_level=offer["upgrade_level"])
            from game.headless.enchantments.base import restore, validate
            card.enchantment = restore(offer["enchantment"])
            validate(card, permanent=True)
        elif offer["upgrade_level"] != 0 or offer["enchantment"] is not None:
            raise ValueError("Non-card shop offer has card metadata.")
        if (type(offer["price"]) is not int or offer["price"] != discounted(state, offer["base_price"]) or type(offer["base_price"]) is not int or not
                price(base, 10000 - slot.variation * 100, offer["on_sale"]) <= offer["base_price"] <=
                price(base, 10000 + slot.variation * 100, offer["on_sale"])):
            raise ValueError("Invalid shop price.")
        if slot.kind == "relic" and offer["sold"] and not any(r.definition_id == offer["definition_id"] for r in state.relics):
            raise ValueError("Purchased shop relic is not owned.")
        slots.append(index)
        sales += int(offer["on_sale"])
    required = [i for i, s in enumerate(SLOTS) if s.kind != "relic"]
    if slots != sorted(set(slots)) or not set(required) <= set(slots) or sales > 1 or (sales != 1 and not any(o["generation"] for o in offers)):
        raise ValueError("Invalid shop stock composition.")
    for index, slot in enumerate(SLOTS):
        if slot.kind == "relic" and index not in slots:
            if not all(any(r.definition_id == name for r in state.relics) for name, _ in shop_items(state, slot)):
                raise ValueError("Available relic stock is missing.")
    if pending["stage"] == "remove":
        if (pending["removal_used"] or (not pending.get("parasol_free_removal") and state.gold < removal_price(state)) or not pending["eligible"]
                or pending["eligible"] != list(eligible_removals(state))):
            raise ValueError("Invalid shop card selection.")
