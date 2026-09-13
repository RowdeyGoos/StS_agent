"""Explicit native event definitions; legacy primitive events stay separate."""

from dataclasses import asdict
from types import MappingProxyType

from game.headless.events.aroma_of_chaos import AromaOfChaos
from game.headless.events.jungle_maze import JungleMazeAdventure

EVENTS = MappingProxyType({"jungle_maze_adventure": JungleMazeAdventure(), "aroma_of_chaos": AromaOfChaos()})


def fingerprint():
    # JSON normalization retains immutable tuple fields in content definitions.
    import json
    return json.loads(json.dumps([asdict(event) for event in EVENTS.values()]))
