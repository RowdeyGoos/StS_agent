"""Explicit monster types supported by private state restoration."""

from types import MappingProxyType
from game.headless.monsters.byrdonis import Byrdonis
from game.headless.monsters.vantom import Vantom
from game.headless.monsters.overgrowth import (
    SimpleEnemy, Nibbit, ShrinkerBeetle, FuzzyWurmCrawler, Mawler,
    LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium,
)

DEFAULT_MONSTERS = MappingProxyType({kind.__name__: kind for kind in (
    SimpleEnemy, Nibbit, ShrinkerBeetle, FuzzyWurmCrawler, Mawler, Byrdonis, Vantom,
    LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium,
)})
