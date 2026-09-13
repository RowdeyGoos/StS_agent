"""Restricted authored route milestones; not procedural Act 1 or full-run endings."""

from types import MappingProxyType

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
        MapNode("camp", "rest", ("mawler", "nibbits")),
        MapNode("mawler", "combat", ("slice_end",), "overgrowth_mawler"),
        MapNode("nibbits", "combat", ("slice_end",), "overgrowth_nibbits"),
        MapNode("slice_end", "slice_end", ()),
    ), "fight_1")


ROUTES = MappingProxyType({"first-slice": first_slice_map, "overgrowth": overgrowth_route_map})
