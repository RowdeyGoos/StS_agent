"""Repeatable purchases and cancelable removal from one owned merchant inventory."""

from game.headless.core.rng import GameRandomService
from game.headless.run.actions import BuyShopItem, BeginShopRemoval, ChooseShopRemoval, LeaveShop
from game.headless.run.deck import add_card, remove_card
from game.headless.run.inventory import add_potion, add_relic
from game.headless.run.state import RunPhase
from game.headless.shops.catalog import SHOP_ID, SLOTS, price


def begin(state, cards):
    state.require_room_entry("shop")
    # Build on an isolated RNG; missing content must not consume a visit or draws.
    rng = GameRandomService(state.seed)
    rng.restore(state.rng.snapshot())
    owned = {r.definition_id for r in state.relics}
    offers = []
    sale_slot = rng.choice("shop.stock", [i for i, s in enumerate(SLOTS) if s.kind == "card" and s.sale_eligible])
    for index, slot in enumerate(SLOTS):
        pool = [(name, cost) for name, cost in slot.items if slot.kind != "relic" or name not in owned]
        if not pool:
            continue
        definition_id, base_cost = rng.choice("shop.stock", pool)
        if slot.kind == "card":
            cards.definition(definition_id)
        scale = rng.randint("shop.prices", 10000 - slot.variation * 100, 10000 + slot.variation * 100)
        on_sale = index == sale_slot
        offers.append({"offer_id": f"shop.{state.next_shop_id}.offer.{index}", "slot": index,
                       "definition_id": definition_id, "kind": slot.kind, "on_sale": on_sale,
                       "price": price(base_cost, scale, on_sale), "sold": False})
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
    return 75 + 25 * state.shop_removals_used


def eligible_removals(state):
    # Native removal excludes the Eternal keyword. No supported card has it;
    # add its content rule here when Eternal cards are introduced.
    return tuple(c.instance_id for c in state.deck)


def can_buy(state, offer):
    return (not offer["sold"] and state.gold >= offer["price"]
            and (offer["kind"] != "potion" or None in state.potions)
            and (offer["kind"] != "relic" or not any(r.definition_id == offer["definition_id"] for r in state.relics)))


def legal_actions(state):
    pending = state.pending
    if pending["stage"] == "remove":
        return tuple(ChooseShopRemoval(c) for c in pending["eligible"]) + (ChooseShopRemoval(None),)
    actions = [BuyShopItem(o["offer_id"]) for o in pending["offers"] if can_buy(state, o)]
    if not pending["removal_used"] and state.gold >= removal_price(state) and eligible_removals(state):
        actions.append(BeginShopRemoval())
    return (*actions, LeaveShop())


def buy(state, cards, offer_id):
    pending = _pending(state)
    offer = next((o for o in pending["offers"] if o["offer_id"] == offer_id), None)
    if offer is None or not can_buy(state, offer):
        raise ValueError("Shop offer cannot be purchased.")
    # Shared acquisition rules validate before allocating or modifying ownership.
    if offer["kind"] == "card":
        result = add_card(state, cards.definition(offer["definition_id"]))
    elif offer["kind"] == "potion":
        result = add_potion(state, offer["definition_id"])
    else:
        result = add_relic(state, offer["definition_id"], cards=cards)
    state.gold -= offer["price"]
    offer["sold"] = True
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
    if instance_id is not None:
        if (pending["removal_used"] or state.gold < removal_price(state)
                or instance_id not in pending["eligible"] or instance_id not in eligible_removals(state)):
            raise ValueError("Card is not eligible for shop removal.")
        result = remove_card(state, instance_id)
        state.gold -= removal_price(state)
        state.shop_removals_used += 1
        pending["removal_used"] = True
    pending.pop("eligible")
    pending["stage"] = "browse"
    return result


def leave(state):
    _pending(state)
    state.pending, state.phase = None, RunPhase.ROUTE
