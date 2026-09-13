"""Pinned solo Ironclad potion content; immutable definitions and run-owned items."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class PotionDefinition:
    definition_id: str
    rarity: str
    usage: str
    targeted: bool
    in_combat_generation: bool
    effects: tuple[tuple, ...]

    @property
    def damage(self):
        return next((e[1] for e in self.effects if e[0] == "damage"), 0)

    @property
    def block(self):
        return next((e[1] for e in self.effects if e[0] == "block"), 0)


@dataclass(frozen=True, slots=True)
class PotionInstance:
    definition_id: str
    instance_id: str


_DEFINITIONS = (
    PotionDefinition("blood_potion", "common", "anytime", False, True, (("heal_percent", 20),)),
    PotionDefinition("soldiers_stew", "rare", "combat", False, True, (("replay_strikes",),)),
    PotionDefinition("ashwater", "uncommon", "combat", False, True, (("select", "ashwater"),)),
    PotionDefinition("attack_potion", "common", "combat", False, True, (("offer", "attack"),)),
    PotionDefinition("beetle_juice", "rare", "combat", True, True, (("status", "shrink", 4),)),
    PotionDefinition("blessing_of_the_forge", "uncommon", "combat", False, True, (("upgrade_hand",),)),
    PotionDefinition("block_potion", "common", "combat", False, True, (("block", 12),)),
    PotionDefinition("bottled_potential", "rare", "combat", False, True, (("shuffle_hand",), ("draw", 5))),
    PotionDefinition("clarity", "uncommon", "combat", False, True, (("draw", 1), ("power", "clarity", 3))),
    PotionDefinition("colorless_potion", "common", "combat", False, True, (("offer", "colorless"),)),
    PotionDefinition("cure_all", "uncommon", "combat", False, True, (("energy", 1), ("draw", 2))),
    PotionDefinition("dexterity_potion", "common", "combat", False, True, (("power", "dexterity", 2),)),
    PotionDefinition("distilled_chaos", "rare", "combat", False, True, (("autoplay", 3),)),
    PotionDefinition(
        "droplet_of_precognition", "rare", "combat", False, True, (("select", "droplet_of_precognition"),)
    ),
    PotionDefinition("duplicator", "uncommon", "combat", False, True, (("power", "duplication", 1),)),
    PotionDefinition("energy_potion", "common", "combat", False, True, (("energy", 2),)),
    PotionDefinition("entropic_brew", "rare", "anytime", False, True, (("fill",),)),
    PotionDefinition("explosive_ampoule", "common", "combat", False, True, (("area", 10),)),
    PotionDefinition("fairy_in_a_bottle", "rare", "automatic", False, False, (("heal_percent", 30),)),
    PotionDefinition("fire_potion", "common", "combat", True, True, (("damage", 20),)),
    PotionDefinition("flex_potion", "common", "combat", False, True, (("temporary", "strength", 5),)),
    PotionDefinition("fortifier", "uncommon", "combat", False, True, (("fortify",),)),
    PotionDefinition("fruit_juice", "rare", "anytime", False, False, (("max_hp", 5),)),
    PotionDefinition(
        "fysh_oil", "uncommon", "combat", False, True, (("power", "strength", 1), ("power", "dexterity", 1))
    ),
    PotionDefinition("gamblers_brew", "uncommon", "combat", False, True, (("select", "gamblers_brew"),)),
    PotionDefinition(
        "gigantification_potion", "rare", "combat", False, True, (("power", "gigantification", 1),)
    ),
    PotionDefinition("heart_of_iron", "uncommon", "combat", False, True, (("power", "plating", 7),)),
    PotionDefinition("liquid_bronze", "uncommon", "combat", False, True, (("power", "thorns", 3),)),
    PotionDefinition("liquid_memories", "rare", "combat", False, True, (("select", "liquid_memories"),)),
    PotionDefinition("lucky_tonic", "rare", "combat", False, True, (("power", "buffer", 1),)),
    PotionDefinition("mazaleths_gift", "rare", "combat", False, True, (("power", "ritual", 1),)),
    PotionDefinition("orobic_acid", "rare", "combat", False, True, (("generate_types",),)),
    PotionDefinition(
        "potion_of_binding",
        "uncommon",
        "combat",
        False,
        True,
        (("all_status", "weak", 1), ("all_status", "vulnerable", 1)),
    ),
    PotionDefinition("powdered_demise", "uncommon", "combat", True, True, (("status", "demise", 9),)),
    PotionDefinition("power_potion", "common", "combat", False, True, (("offer", "power"),)),
    PotionDefinition(
        "radiant_tincture", "uncommon", "combat", False, True, (("energy", 1), ("power", "radiance", 3))
    ),
    PotionDefinition("regen_potion", "uncommon", "combat", False, False, (("power", "regen", 5),)),
    PotionDefinition(
        "shackling_potion", "rare", "combat", False, True, (("all_status", "dark_shackles", 7),)
    ),
    PotionDefinition(
        "ship_in_a_bottle", "rare", "combat", False, True, (("block", 10), ("power", "block_next_turn", 10))
    ),
    PotionDefinition("skill_potion", "common", "combat", False, True, (("offer", "skill"),)),
    PotionDefinition("snecko_oil", "rare", "combat", False, True, (("draw", 7), ("random_costs",))),
    PotionDefinition("speed_potion", "common", "combat", False, True, (("temporary", "dexterity", 5),)),
    PotionDefinition("stable_serum", "uncommon", "combat", False, True, (("power", "retain_hand", 2),)),
    PotionDefinition("strength_potion", "common", "combat", False, True, (("power", "strength", 2),)),
    PotionDefinition("swift_potion", "common", "combat", False, True, (("draw", 3),)),
    PotionDefinition(
        "touch_of_insanity", "uncommon", "combat", False, True, (("select", "touch_of_insanity"),)
    ),
    PotionDefinition("vulnerable_potion", "common", "combat", True, True, (("status", "vulnerable", 3),)),
    PotionDefinition("weak_potion", "common", "combat", True, True, (("status", "weak", 3),)),
    PotionDefinition("foul_potion", "event", "anytime", False, True, (("damage_all_creatures", 12),)),
    PotionDefinition("glowwater_potion", "event", "combat", False, True, (("exhaust_hand",), ("draw", 10))),
    PotionDefinition("potion_shaped_rock", "token", "combat", True, True, (("damage", 15),)),
)
POTIONS = MappingProxyType({d.definition_id: d for d in _DEFINITIONS})
