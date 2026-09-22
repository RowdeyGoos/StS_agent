"""Winged Boots permits another point on the next row, consuming one owned use."""

from game.headless.relics.run_rules import owned, counter


def alternatives(graph, previous):
    if previous is None:
        return ()
    current = graph.node(previous)
    if current.row is None:
        return ()
    return tuple(
        n.node_id for n in graph.nodes if n.row == current.row + 1 and n.kind not in ("terminal", "slice_end")
    )


def available(state, graph):
    ordinary = graph.available_nodes(state.current_node_id)
    boots = owned(state, "winged_boots")
    if boots is None or boots.counter >= 3:
        return ordinary
    return tuple(dict.fromkeys((*ordinary, *alternatives(graph, state.current_node_id))))


def entered(state, graph, previous, node_id):
    if node_id in graph.available_nodes(previous):
        return
    boots = owned(state, "winged_boots")
    if boots is None or boots.counter >= 3 or node_id not in alternatives(graph, previous):
        raise ValueError("Unavailable Winged Boots travel.")
    counter(state, boots, boots.counter + 1)
    state.free_travels.append({"source": boots.instance_id, "node_id": node_id})


def validate(state, graph):
    records = state.free_travels
    if not isinstance(records, list):
        raise ValueError("Invalid free-travel history.")
    destinations = {}
    counts = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"source", "node_id"}:
            raise ValueError("Invalid free-travel record.")
        identity, node = record["source"], record["node_id"]
        if (
            not isinstance(identity, str)
            or not identity.startswith("run.item.")
            or not identity.removeprefix("run.item.").isdigit()
            or int(identity.removeprefix("run.item.")) >= state.next_item_id
        ):
            raise ValueError("Unallocated free-travel source.")
        if not isinstance(node, str) or node in destinations:
            raise ValueError("Duplicate free-travel destination.")
        destinations[node] = identity
        counts[identity] = counts.get(identity, 0) + 1
        if counts[identity] > 3:
            raise ValueError("Exhausted Winged Boots travel.")
    from game.headless.run.campaign import journeys
    consumed = set()
    for owner, layout in journeys(state, graph):
        previous = None
        for node in owner.visited_nodes:
            if node not in layout.available_nodes(previous):
                if node not in destinations or node not in alternatives(layout, previous):
                    raise ValueError("Invalid visited map path.")
                consumed.add(node)
            previous = node
    if consumed != set(destinations):
        raise ValueError("Free travel differs from visited path.")
    for relic in state.relics:
        if relic.instance_id in counts and (
            relic.definition_id != "winged_boots" or relic.counter != counts[relic.instance_id]
        ):
            raise ValueError("Winged Boots counter differs from travel history.")
