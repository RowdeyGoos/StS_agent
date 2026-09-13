"""Restricted authored route milestones; not procedural Act 1 or full-run endings."""

from types import MappingProxyType
from dataclasses import replace

from game.headless.map.graph import MapGraph, MapNode


def first_slice_map():
    return MapGraph((
        MapNode("fight_1", "combat", ("camp",), encounter_id="overgrowth_nibbit"),
        MapNode("camp", "rest", ("fight_2",)),
        MapNode("fight_2", "combat", ("slice_end",), encounter_id="overgrowth_slimes"),
        MapNode("slice_end", "slice_end", ()),
    ), "fight_1")


def overgrowth_route_map():
    """Three easy fights in two orders, a rest, then a normal-encounter fork."""
    return MapGraph((
        MapNode("fight_1", "combat", ("slimes", "fuzzy"), "overgrowth_nibbit"),
        MapNode("slimes", "combat", ("fuzzy_after_slimes",), "overgrowth_slimes"),
        MapNode("fuzzy_after_slimes", "combat", ("camp",), "overgrowth_fuzzy"),
        MapNode("fuzzy", "combat", ("slimes_after_fuzzy",), "overgrowth_fuzzy"),
        MapNode("slimes_after_fuzzy", "combat", ("camp",), "overgrowth_slimes"),
        MapNode("camp", "rest", ("mawler", "nibbits", "byrdonis")),
        MapNode("mawler", "combat", ("slice_end",), "overgrowth_mawler"),
        MapNode("nibbits", "combat", ("slice_end",), "overgrowth_nibbits"),
        MapNode("byrdonis", "elite", ("slice_end",), "overgrowth_byrdonis"),
        MapNode("slice_end", "slice_end", ()),
    ), "fight_1")


def overgrowth_act1_map():
    nodes = tuple(replace(n, next_node_ids=("merchant", "boss_camp")) if n.next_node_ids == ("slice_end",) else n
                  for n in overgrowth_route_map().nodes if n.node_id != "slice_end")
    nodes = tuple(replace(n, next_node_ids=("treasure",)) if n.next_node_ids == ("camp",) else n for n in nodes)
    nodes = tuple(replace(n, next_node_ids=("jungle_maze",)) if n.next_node_ids == ("treasure",) else n for n in nodes)
    return MapGraph((*nodes,
                     MapNode("jungle_maze", "event", ("treasure",), event_id="jungle_maze_adventure"),
                     MapNode("treasure", "treasure", ("camp",)),
                     MapNode("merchant", "shop", ("boss_camp",)),
                     MapNode("boss_camp", "rest", ("vantom",)),
                     MapNode("vantom", "boss", (), "overgrowth_vantom")), "fight_1")


ROUTES = MappingProxyType({"first-slice": first_slice_map, "overgrowth": overgrowth_route_map,
                          "overgrowth-act1": overgrowth_act1_map})
