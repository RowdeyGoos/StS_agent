"""Explicit native event definitions; legacy primitive events stay separate."""

from dataclasses import asdict
from types import MappingProxyType

from game.headless.events.aroma_of_chaos import AromaOfChaos
from game.headless.events.jungle_maze import JungleMazeAdventure
from game.headless.events.morphic_grove import MorphicGrove
from game.headless.events.tablet_of_truth import TabletOfTruth

from game.headless.events.whispering_hollow import WhisperingHollow
from game.headless.events.wellspring import Wellspring
from game.headless.events.slippery_bridge import SlipperyBridge
from game.headless.events.sunken_statue import SunkenStatue
from game.headless.events.dense_vegetation import DenseVegetation
from game.headless.events.sapphire_seed import SapphireSeed
from game.headless.events.byrdonis_nest import ByrdonisNest

EVENTS = MappingProxyType({
    "jungle_maze_adventure": JungleMazeAdventure(), "aroma_of_chaos": AromaOfChaos(),
    "morphic_grove": MorphicGrove(), "tablet_of_truth": TabletOfTruth(),
    "whispering_hollow": WhisperingHollow(), "wellspring": Wellspring(),
    "slippery_bridge": SlipperyBridge(), "sunken_statue": SunkenStatue(),
    "dense_vegetation": DenseVegetation(), "sapphire_seed": SapphireSeed(), "byrdonis_nest": ByrdonisNest(),
})


def fingerprint():
    # JSON normalization retains immutable tuple fields in content definitions.
    import json
    return json.loads(json.dumps([asdict(event) for event in EVENTS.values()]))
