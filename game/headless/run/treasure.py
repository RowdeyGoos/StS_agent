"""Owned chest entry, gold on opening, optional relic pickup and room exit."""

from game.headless.core.rng import GameRandomService
from game.headless.relics.base import RELICS
from game.headless.run.actions import OpenChest, ClaimTreasureRelic, LeaveTreasure
from game.headless.run.inventory import add_relic
from game.headless.run.state import RunPhase
from game.headless.treasure.catalog import ORDINARY_CHEST
from game.headless.relics.pools import treasure_pool


def eligible_relics(state):
    excluded = {r.definition_id for r in state.relics} | set(state.treasure_relics_drawn)
    return tuple(r for r in treasure_pool(state) if r not in excluded)


def begin(state):
    state.require_room_entry("treasure")
    from game.headless.relics.run_rules import owned
    crucible = owned(state, "silver_crucible")
    if crucible is not None:
        crucible.data["treasures"] += 1
        if crucible.data["treasures"] == 1:
            state.pending = {"kind": "treasure", "definition_id": ORDINARY_CHEST.definition_id, "treasure_id": state.next_treasure_id, "stage": "empty", "relic_id": None, "gold": 0, "claimed_instance_id": None, "item_id_on_entry": state.next_item_id}
            state.next_treasure_id += 1
            state.phase = RunPhase.ROOM
            return
    pool = eligible_relics(state)
    from game.headless.core.rng import from_snapshot
    rng = from_snapshot(state.rng.snapshot())
    if getattr(rng,"native",False):
        from copy import deepcopy
        from game.headless.generation.relics import pull
        trial=deepcopy(state);trial.rng=rng
        relic_id=pull(trial,stream="treasure_room_relics",allowed=treasure_pool(state),owner="shared")
        state.relic_bags=trial.relic_bags
    else:
        relic_id = rng.choice("treasure.relic", pool) if pool else ORDINARY_CHEST.fallback_relic
    if relic_id not in RELICS:
        raise ValueError("Unsupported treasure relic.")
    pending = {"kind": "treasure", "definition_id": ORDINARY_CHEST.definition_id,
               "treasure_id": state.next_treasure_id, "stage": "closed", "relic_id": relic_id,
               "gold": None, "claimed_instance_id": None, "item_id_on_entry": state.next_item_id}
    # Like a native grab-bag pull, an offered relic is consumed even if skipped.
    # Fixture profiles also retain their original treasure-specific draw history.
    if relic_id != ORDINARY_CHEST.fallback_relic:
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
    from game.headless.core.ascension import level
    if level(state) >= 3:
        gold = gold * 3 // 4
    from game.headless.relics.run_rules import gain_gold
    gain_gold(state, gold)
    from game.headless.run.spoils_map import complete
    complete(state)
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
