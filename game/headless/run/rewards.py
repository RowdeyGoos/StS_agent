"""Reduced reward game rules, callable without a protocol adapter."""

from game.headless.run.deck import add_card
from game.headless.run.state import RunPhase


def begin_reward(state, cards, *, gold: int, card_ids, offer_count: int = 3) -> None:
    state.require_between_rooms()
    if type(gold) is not int or gold < 0 or type(offer_count) is not int or offer_count <= 0:
        raise ValueError("Invalid reward parameters.")
    pool = list(card_ids)
    if len(pool) != len(set(pool)) or not pool:
        raise ValueError("Reward cards must be a nonempty distinct pool.")
    for card_id in pool:
        cards.definition(card_id)
    # Project-authored sampling, explicitly not a claim of native reward RNG.
    state.rng.shuffle("reward_offer", pool)
    state.pending = {"kind": "reward", "gold": gold, "gold_claimed": False,
                     "offers": pool[:offer_count], "card_resolved": False}
    state.phase = RunPhase.REWARD


def claim_gold(state) -> int:
    reward = _reward(state)
    if reward["gold_claimed"]:
        raise ValueError("Gold reward was already claimed.")
    state.gold += reward["gold"]
    reward["gold_claimed"] = True
    return reward["gold"]


def choose_card(state, cards, definition_id: str | None):
    reward = _reward(state)
    if reward["card_resolved"] or (definition_id is not None and definition_id not in reward["offers"]):
        raise ValueError("Card reward choice is unavailable.")
    card = None if definition_id is None else add_card(state, cards.definition(definition_id))
    reward["card_resolved"] = True
    return card


def finish_reward(state) -> None:
    reward = _reward(state)
    if not reward["gold_claimed"] or not reward["card_resolved"]:
        raise ValueError("Resolve rewards before proceeding.")
    state.pending = None
    state.phase = RunPhase.ROUTE


def _reward(state):
    if state.phase is not RunPhase.REWARD or not state.pending or state.pending.get("kind") != "reward":
        raise ValueError("No reward is active.")
    return state.pending
