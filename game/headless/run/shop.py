"""Repeatable purchases and cancelable removal from one owned merchant inventory."""

from game.headless.core.rng import GameRandomService
from game.headless.run.actions import BuyShopItem, BeginShopRemoval, ChooseShopRemoval, LeaveShop
from game.headless.run.deck import add_card, remove_card
from game.headless.run.inventory import add_potion, add_relic
from game.headless.run.state import RunPhase
from game.headless.shops.catalog import SHOP_ID, SLOTS, price
from game.headless.relics.run_rules import has, modify_new_card
from game.headless.relics.pools import shop_items


def begin(state, cards):
    from copy import deepcopy
    before = deepcopy(state)
    try:
        _begin(state, cards)
        start_parasol(state, cards)
    except Exception:
        state.__dict__.clear()
        state.__dict__.update(before.__dict__)
        raise


def _begin(state, cards):
    state.require_room_entry("shop")
    if state.pending is None:
        from game.headless.relics.run_rules import entered_room
        entered_room(state, "shop")
    # Build on an isolated RNG; missing content must not consume a visit or draws.
    from game.headless.core.rng import from_snapshot
    rng = from_snapshot(state.rng.snapshot())
    if getattr(rng,"native",False):
        from copy import deepcopy
        from game.headless.generation.merchant import populate
        trial=deepcopy(state);trial.rng=rng
        offers=populate(trial,cards)
        trial.pending={"kind":"shop","catalog_id":SHOP_ID,"shop_id":trial.next_shop_id,"stage":"browse","offers":offers,"removal_used":False,"removals_on_entry":trial.shop_removals_used}
        trial.next_shop_id+=1;trial.phase=RunPhase.ROOM
        state.__dict__.clear();state.__dict__.update(trial.__dict__)
        return
    owned = {r.definition_id for r in state.relics}
    offers = []
    sale_slot = rng.choice("shop.stock", [i for i, s in enumerate(SLOTS) if s.kind == "card" and s.sale_eligible])
    for index, slot in enumerate(SLOTS):
        pool = [(name, cost) for name, cost in shop_items(state, slot) if slot.kind != "relic" or name not in owned]
        if not pool:
            continue
        definition_id, base_cost = stock_choice(state, slot, pool, rng)
        if slot.kind == "card":
            cards.definition(definition_id)
        scale = rng.randint("shop.prices", 10000 - slot.variation * 100, 10000 + slot.variation * 100)
        on_sale = index == sale_slot
        offers.append({"offer_id": f"shop.{state.next_shop_id}.offer.{index}", "slot": index,
                       "definition_id": definition_id, "kind": slot.kind, "on_sale": on_sale,
                       "base_price": price(base_cost, scale, on_sale), "price": discounted(state, price(base_cost, scale, on_sale)), "sold": False,
                       "generation": 0, "upgrade_level": 0, "enchantment": None})
    for offer in offers:
        modify_offer(state, cards, offer)
    pending = {"kind": "shop", "catalog_id": SHOP_ID, "shop_id": state.next_shop_id,
               "stage": "browse", "offers": offers, "removal_used": False,
               "removals_on_entry": state.shop_removals_used}
    state.rng = rng
    state.next_shop_id += 1
    state.pending, state.phase = pending, RunPhase.ROOM


def _pending(state, stage="browse"):
    if (state.phase is not RunPhase.ROOM or not state.pending
            or state.pending.get("kind") != "shop" or state.pending.get("stage") != stage):
        raise ValueError("Shop action is unavailable.")
    return state.pending


def removal_price(state):
    return discounted(state, 75 + 25 * state.shop_removals_used)


def eligible_removals(state):
    # Greed and future Eternal cards are excluded by the shared keyword.
    return tuple(c.instance_id for c in state.deck if not c.spec.eternal)


def can_buy(state, offer, *, ignore_cost=False):
    from game.headless.relics.base import RELICS
    return (not offer["sold"] and (ignore_cost or state.gold >= offer["price"])
            and (offer["kind"] != "potion" or None in state.potions)
            and (offer["kind"] != "relic" or RELICS[offer["definition_id"]].stackable or RELICS[offer["definition_id"]].allow_duplicates or not any(r.definition_id == offer["definition_id"] for r in state.relics)))


def legal_actions(state):
    pending = state.pending
    if pending["stage"] == "remove":
        return tuple(ChooseShopRemoval(c) for c in pending["eligible"]) + (() if pending.get("parasol_free_removal") else (ChooseShopRemoval(None),))
    actions = [BuyShopItem(o["offer_id"]) for o in pending["offers"] if can_buy(state, o)]
    if not pending["removal_used"] and state.gold >= removal_price(state) and eligible_removals(state):
        actions.append(BeginShopRemoval())
    return (*actions, LeaveShop())


def buy(state, cards, offer_id, *, ignore_cost=False):
    pending = _pending(state)
    offer = next((o for o in pending["offers"] if o["offer_id"] == offer_id), None)
    if offer is None or not can_buy(state, offer, ignore_cost=ignore_cost):
        raise ValueError("Shop offer cannot be purchased.")
    paid = 0 if ignore_cost else offer["price"]
    # Shared acquisition rules validate before allocating or modifying ownership.
    if offer["kind"] == "card":
        result = add_card(state, cards.definition(offer["definition_id"]), upgrade_level=offer["upgrade_level"])
        if offer["enchantment"] is not None:
            from game.headless.enchantments.base import restore
            result.enchantment = restore(offer["enchantment"])
    elif offer["kind"] == "potion":
        result = add_potion(state, offer["definition_id"])
    else:
        result = add_relic(state, offer["definition_id"], cards=cards)
    state.gold -= paid
    offer["sold"] = True
    if has(state, "the_courier"):
        refill(state, cards, offer)
    for remaining in pending["offers"]:
        remaining["price"] = discounted(state, remaining["base_price"])
    return result


def begin_removal(state):
    pending = _pending(state)
    if pending["removal_used"] or state.gold < removal_price(state) or not eligible_removals(state):
        raise ValueError("Shop removal is unavailable.")
    pending["stage"] = "remove"
    pending["eligible"] = list(eligible_removals(state))


def choose_removal(state, instance_id):
    pending = _pending(state, "remove")
    result = None
    free = pending.get("parasol_free_removal", False)
    if instance_id is None and free:
        raise ValueError("Lord’s Parasol removal cannot be canceled.")
    if instance_id is not None:
        if (pending["removal_used"] or (not free and state.gold < removal_price(state))
                or instance_id not in pending["eligible"] or instance_id not in eligible_removals(state)):
            raise ValueError("Card is not eligible for shop removal.")
        result = remove_card(state, instance_id)
        state.gold -= 0 if free else removal_price(state)
        state.shop_removals_used += 1
        pending["removal_used"] = True
    pending.pop("eligible")
    pending.pop("parasol_free_removal", None)
    pending["stage"] = "browse"
    return result


def leave(state):
    _pending(state)
    state.pending, state.phase = None, RunPhase.ROUTE


def discounted(state, amount):
    numerator, denominator = 1, 1
    if has(state, "membership_card"):
        denominator *= 2
    if has(state, "the_courier"):
        numerator *= 4
        denominator *= 5
    return amount * numerator // denominator


def modify_offer(state, cards, offer):
    if offer['kind'] == 'card':
        from game.headless.enchantments.base import record
        card = modify_new_card(state, cards.create(offer['definition_id']))
        offer['upgrade_level'], offer['enchantment'] = card.upgrade_level, record(card)


def refill(state, cards, offer):
    if getattr(state.rng,"native",False):
        from game.headless.generation.merchant import restock
        return restock(state,cards,offer)
    slot = SLOTS[offer['slot']]
    pool = [(name, cost) for name, cost in shop_items(state, slot) if slot.kind != 'relic' or not has(state, name)]
    if not pool:
        return
    name, base = stock_choice(state, slot, pool, state.rng, restock=True)
    scale = state.rng.randint('shop.prices', 10000-slot.variation*100, 10000+slot.variation*100)
    generation = offer['generation'] + 1
    offer.update(definition_id=name, sold=False, on_sale=False, generation=generation,
                 offer_id=f"shop.{state.pending['shop_id']}.offer.{offer['slot']}.refill.{generation}",
                 base_price=price(base, scale), price=discounted(state, price(base, scale)), upgrade_level=0, enchantment=None)
    modify_offer(state, cards, offer)


def stock_choice(state, slot, pool, rng, *, restock=False):
    from game.headless.potions.pools import ORDINARY_POTIONS, generate
    if slot.kind != 'potion' or state.config is None or state.config.reward_potions != ORDINARY_POTIONS:
        return rng.choice('shop.stock', pool)
    blacklist = {o['definition_id'] for o in state.pending['offers'] if o['kind'] == 'potion' and not o['sold']} if restock else set()
    name = generate(ORDINARY_POTIONS, rng, stream='shop.stock', blacklist=blacklist)
    return name, dict(pool)[name]


def start_parasol(state, cards):
    if has(state, 'lords_parasol') and 'parasol_cursor' not in state.pending:
        state.pending['parasol_cursor'] = 0
        resume_parasol(state, cards)


def resume_parasol(state, cards):
    pending = state.pending
    if not pending or pending.get('kind') != 'shop' or 'parasol_cursor' not in pending or state.relic_work:
        return
    offers = pending['offers']
    # Freeze slot order, buying each original entry once even with Courier.
    while pending['parasol_cursor'] < len(offers):
        index = pending['parasol_cursor']
        pending['parasol_cursor'] += 1
        offer = offers[index]
        if offer['kind'] != 'potion' or None in state.potions or has(state, 'sozu'):
            if can_buy(state, offer, ignore_cost=True):
                buy(state, cards, offer['offer_id'], ignore_cost=True)
        if state.relic_work:
            return
    if pending['parasol_cursor'] == len(offers):
        pending['parasol_cursor'] += 1
        eligible = list(eligible_removals(state))
        if eligible and not pending['removal_used']:
            pending.update(stage='remove', eligible=eligible, parasol_free_removal=True)
