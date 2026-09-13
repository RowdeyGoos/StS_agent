"""Validate exact chest continuation without rerolling or reapplying rewards."""

from game.headless.run.unknown_rooms import room_node

from game.headless.run.state import RunPhase
from game.headless.treasure.catalog import ORDINARY_CHEST
from game.headless.relics.pools import treasure_pool


def validate_treasure(state, graph):
    pending = state.pending
    if set(pending) != {"kind", "definition_id", "treasure_id", "stage", "relic_id", "gold", "claimed_instance_id"}:
        raise ValueError("Invalid treasure state fields.")
    if (state.phase is not RunPhase.ROOM or pending["stage"] not in ("closed", "open", "claimed", "empty")
            or pending["definition_id"] != ORDINARY_CHEST.definition_id):
        raise ValueError("Invalid treasure phase or content.")
    if (type(pending["treasure_id"]) is not int or pending["treasure_id"] < 0
            or pending["treasure_id"] != state.next_treasure_id - 1):
        raise ValueError("Invalid owned treasure identity.")
    if graph is not None and (state.current_node_id is None or room_node(state, graph, state.current_node_id).kind != "treasure"):
        raise ValueError("Treasure differs from its room.")
    if pending["stage"] == "empty":
        from game.headless.relics.run_rules import owned
        relic = owned(state, "silver_crucible")
        if relic is None or relic.data["treasures"] != 1 or pending["relic_id"] is not None or pending["gold"] != 0 or pending["claimed_instance_id"] is not None:
            raise ValueError("Invalid Silver Crucible empty treasure.")
        return
    relic_id = pending["relic_id"]
    if relic_id == ORDINARY_CHEST.fallback_relic:
        from game.headless.run.treasure import eligible_relics
        if eligible_relics(state):
            raise ValueError("Treasure fallback requires an exhausted pool.")
    elif (relic_id not in treasure_pool(state) or not state.treasure_relics_drawn
            or state.treasure_relics_drawn[-1] != relic_id):
        raise ValueError("Treasure offer differs from its depleted pool.")
    if pending["stage"] == "closed":
        if pending["gold"] is not None:
            raise ValueError("Closed chest cannot have granted gold.")
    elif type(pending["gold"]) is not int or not ORDINARY_CHEST.gold_range[0] <= pending["gold"] <= ORDINARY_CHEST.gold_range[1]:
        raise ValueError("Invalid treasure gold.")
    if pending["stage"] == "claimed":
        if not any(r.instance_id == pending["claimed_instance_id"] and r.definition_id == relic_id for r in state.relics):
            raise ValueError("Claimed treasure relic is not owned.")
    elif pending["claimed_instance_id"] is not None or (relic_id != ORDINARY_CHEST.fallback_relic and any(r.definition_id == relic_id for r in state.relics)):
        raise ValueError("Invalid unclaimed treasure relic.")
