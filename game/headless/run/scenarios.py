"""Authored two-combat milestone; not procedural Act 1 or a full-run ending."""

from game.headless.map.graph import MapGraph, MapNode


def first_slice_map():
    return MapGraph((
        MapNode("fight_1", "combat", ("camp",), encounter_id="overgrowth_nibbit"),
        MapNode("camp", "rest", ("fight_2",)),
        MapNode("fight_2", "combat", ("slice_end",), encounter_id="overgrowth_slimes"),
        MapNode("slice_end", "slice_end", ()),
    ), "fight_1")
