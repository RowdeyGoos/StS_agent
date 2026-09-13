"""Owned chest entry, gold on opening, optional relic pickup and room exit."""

from game.headless.core.rng import GameRandomService
from game.headless.relics.base import RELICS
from game.headless.run.actions import OpenChest, ClaimTreasureRelic, LeaveTreasure
from game.headless.run.inventory import add_relic
from game.headless.run.state import RunPhase
from game.headless.treasure.catalog import ORDINARY_CHEST


def eligible_relics(state):
    excluded = {r.definition_id for r in state.relics} | set(state.treasure_relics_drawn)
    return tuple(r for r in ORDINARY_CHEST.relic_pool if r not in excluded)


def begin(state):
    state.require_room_entry("treasure")
    pool = eligible_relics(state)
    rng = GameRandomService(state.seed)
    rng.restore(state.rng.snapshot())
    relic_id = rng.choice("treasure.relic", pool) if pool else ORDINARY_CHEST.fallback_relic
    if relic_id not in RELICS:
        raise ValueError("Unsupported treasure relic.")
    pending = {"kind": "treasure", "definition_id": ORDINARY_CHEST.definition_id,
               "treasure_id": state.next_treasure_id, "stage": "closed", "relic_id": relic_id,
               "gold": None, "claimed_instance_id": None}
    # Like a native grab-bag pull, an offered relic is consumed even if skipped.
    # This restricted pool is owned by treasure; native cross-source bags are open work.
    if pool:
        state.treasure_relics_drawn.append(relic_id)
    state.rng = rng
    state.next_treasure_id += 1
    state.pending, state.phase = pending, RunPhase.ROOM


def _pending(state, stage=None):
    if (state.phase is not RunPhase.ROOM or not state.pending or state.pending.get("kind") != "treasure"
            or (stage is not None and state.pending.get("stage") != stage)):
        raise ValueError("Treasure action is unavailable.")
    return state.pending


def legal_actions(state):
    pending = _pending(state)
    if pending["stage"] == "closed":
        return (OpenChest(), LeaveTreasure())
    if pending["stage"] == "open":
        return (ClaimTreasureRelic(pending["treasure_id"]), LeaveTreasure())
    return (LeaveTreasure(),)


def open_chest(state):
    pending = _pending(state, "closed")
    gold = state.rng.randint("treasure.gold", *ORDINARY_CHEST.gold_range)
    state.gold += gold
    pending["gold"], pending["stage"] = gold, "open"
    return gold


def claim_relic(state, treasure_id, *, cards=None):
    pending = _pending(state, "open")
    if type(treasure_id) is not int or treasure_id != pending["treasure_id"]:
        raise ValueError("Stale treasure claim.")
    relic = add_relic(state, pending["relic_id"], cards=cards)
    pending["claimed_instance_id"], pending["stage"] = relic.instance_id, "claimed"
    return relic


def leave(state):
    _pending(state)
    state.pending, state.phase = None, RunPhase.ROUTE
