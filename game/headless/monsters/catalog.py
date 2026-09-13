"""Explicit monster types supported by private state restoration."""

from types import MappingProxyType
from game.headless.monsters.byrdonis import Byrdonis
from game.headless.monsters.vantom import Vantom
from game.headless.monsters.overgrowth import (
    SimpleEnemy, Nibbit, ShrinkerBeetle, FuzzyWurmCrawler, Mawler,
    LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium,
)

from game.headless.monsters.overgrowth_normal import CubexConstruct, SnappingJaxfruit, VineShambler, SlitheringStrangler, Inklet, Flyconid
from game.headless.monsters.ruby_raiders import AssassinRubyRaider, AxeRubyRaider, BruteRubyRaider, CrossbowRubyRaider, TrackerRubyRaider
from game.headless.monsters.bygone_effigy import BygoneEffigy
from game.headless.monsters.ceremonial_beast import CeremonialBeast
from game.headless.monsters.kin import KinFollower, KinPriest
from game.headless.monsters.phrog_parasite import PhrogParasite, Wriggler
from game.headless.monsters.fogmog import Fogmog, EyeWithTeeth

DEFAULT_MONSTERS = MappingProxyType({kind.__name__: kind for kind in (
    SimpleEnemy, Nibbit, ShrinkerBeetle, FuzzyWurmCrawler, Mawler, Byrdonis, Vantom,
    CubexConstruct, SnappingJaxfruit, VineShambler, SlitheringStrangler, Inklet, Flyconid,
    AssassinRubyRaider, AxeRubyRaider, BruteRubyRaider, CrossbowRubyRaider, TrackerRubyRaider,
    BygoneEffigy, CeremonialBeast, KinFollower, KinPriest, PhrogParasite, Wriggler, Fogmog, EyeWithTeeth,
    LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium,
)})
