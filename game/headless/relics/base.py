"""Immutable relic definitions and serializable run-owned instances."""

from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class RelicDefinition:
    definition_id: str
    victory_heal: int = 0
    pickup_max_hp: int = 0
    stackable: bool = False
    pickup_gold: int = 0
    combat_strength: int = 0
    evolve_after_elites: int = 0
    evolves_into: str | None = None
    allow_duplicates: bool = False
    adds_pet: bool = False
    pickup_transform: tuple[str, str] | None = None
    rarity: str = "event"
    counter_limit: int = 0

    def after_obtained(self, state, *, cards=None) -> None:
        if self.pickup_transform is not None:
            from game.headless.run.deck import replace_card
            source, target = self.pickup_transform
            definition = cards.definition(target)
            for card in tuple(state.deck):
                if card.definition.definition_id == source:
                    replace_card(state, card.instance_id, definition)
        from game.headless.relics.run_rules import gain_gold, max_hp
        if self.pickup_gold:
            gain_gold(state, self.pickup_gold)
        if self.pickup_max_hp:
            max_hp(state, self.pickup_max_hp)

    def after_combat_victory(self, state) -> int:
        if state.hp <= 0:
            return 0
        amount = min(self.victory_heal, state.max_hp - state.hp)
        state.hp += amount
        return amount


@dataclass(frozen=True, slots=True)
class RelicInstance:
    definition_id: str
    instance_id: str
    counter: int = 0
    data: dict[str, object] = field(default_factory=dict)


from game.headless.relics.ancient_content import definitions as ancient_definitions

RELICS = MappingProxyType({
    **ancient_definitions(RelicDefinition),
    "byrdpip": RelicDefinition("byrdpip", adds_pet=True, allow_duplicates=True, pickup_transform=("byrdonis_egg", "byrd_swoop")),
    "sword_of_stone": RelicDefinition("sword_of_stone", evolve_after_elites=5, evolves_into="sword_of_jade", allow_duplicates=True),
    "sword_of_jade": RelicDefinition("sword_of_jade", combat_strength=3, allow_duplicates=True),
    "golden_pearl": RelicDefinition("golden_pearl", pickup_gold=150, rarity="ancient"),
    "nutritious_oyster": RelicDefinition("nutritious_oyster", pickup_max_hp=11, rarity="ancient"),
    "circlet": RelicDefinition("circlet", stackable=True),
    "burning_blood": RelicDefinition("burning_blood", victory_heal=6, rarity="starter"),
    "strawberry": RelicDefinition("strawberry", pickup_max_hp=7, rarity="common"),
    "pear": RelicDefinition("pear", pickup_max_hp=10, rarity="uncommon"),
    "mango": RelicDefinition("mango", pickup_max_hp=14, rarity="rare"),
    "akabeko": RelicDefinition("akabeko", rarity="uncommon"),
    "anchor": RelicDefinition("anchor", rarity="common"),
    "art_of_war": RelicDefinition("art_of_war", rarity="rare"),
    "bag_of_marbles": RelicDefinition("bag_of_marbles", rarity="common"),
    "bag_of_preparation": RelicDefinition("bag_of_preparation", rarity="common"),
    "beating_remnant": RelicDefinition("beating_remnant", rarity="rare"),
    "bellows": RelicDefinition("bellows", rarity="rare"),
    "belt_buckle": RelicDefinition("belt_buckle", rarity="shop"),
    "blood_vial": RelicDefinition("blood_vial", rarity="common"),
    "bread": RelicDefinition("bread", rarity="shop"),
    "bronze_scales": RelicDefinition("bronze_scales", rarity="common"),
    "burning_sticks": RelicDefinition("burning_sticks", rarity="shop"),
    "candelabra": RelicDefinition("candelabra", rarity="uncommon"),
    "captains_wheel": RelicDefinition("captains_wheel", rarity="rare"),
    "centennial_puzzle": RelicDefinition("centennial_puzzle", rarity="common"),
    "chandelier": RelicDefinition("chandelier", rarity="rare"),
    "chemical_x": RelicDefinition("chemical_x", rarity="shop"),
    "cloak_clasp": RelicDefinition("cloak_clasp", rarity="rare"),
    "festive_popper": RelicDefinition("festive_popper", rarity="common"),
    "gambling_chip": RelicDefinition("gambling_chip", rarity="rare"),
    "game_piece": RelicDefinition("game_piece", rarity="rare"),
    "ghost_seed": RelicDefinition("ghost_seed", rarity="shop"),
    "girya": RelicDefinition("girya", rarity="rare", counter_limit=3),
    "gorget": RelicDefinition("gorget", rarity="common"),
    "gremlin_horn": RelicDefinition("gremlin_horn", rarity="uncommon"),
    "happy_flower": RelicDefinition("happy_flower", rarity="common", counter_limit=2),
    "horn_cleat": RelicDefinition("horn_cleat", rarity="uncommon"),
    "ice_cream": RelicDefinition("ice_cream", rarity="rare"),
    "intimidating_helmet": RelicDefinition("intimidating_helmet", rarity="rare"),
    "joss_paper": RelicDefinition("joss_paper", rarity="uncommon", counter_limit=4),
    "kunai": RelicDefinition("kunai", rarity="rare"),
    "kusarigama": RelicDefinition("kusarigama", rarity="uncommon"),
    "lantern": RelicDefinition("lantern", rarity="common"),
    "lava_lamp": RelicDefinition("lava_lamp", rarity="shop"),
    "letter_opener": RelicDefinition("letter_opener", rarity="uncommon"),
    "lizard_tail": RelicDefinition("lizard_tail", rarity="rare", counter_limit=1),
    "mercury_hourglass": RelicDefinition("mercury_hourglass", rarity="uncommon"),
    "miniature_cannon": RelicDefinition("miniature_cannon", rarity="uncommon"),
    "mummified_hand": RelicDefinition("mummified_hand", rarity="rare"),
    "mystic_lighter": RelicDefinition("mystic_lighter", rarity="shop"),
    "nunchaku": RelicDefinition("nunchaku", rarity="uncommon", counter_limit=9),
    "oddly_smooth_stone": RelicDefinition("oddly_smooth_stone", rarity="common"),
    "orichalcum": RelicDefinition("orichalcum", rarity="uncommon"),
    "ornamental_fan": RelicDefinition("ornamental_fan", rarity="uncommon"),
    "parrying_shield": RelicDefinition("parrying_shield", rarity="uncommon"),
    "pen_nib": RelicDefinition("pen_nib", rarity="uncommon", counter_limit=9),
    "pendulum": RelicDefinition("pendulum", rarity="common"),
    "permafrost": RelicDefinition("permafrost", rarity="uncommon"),
    "pocketwatch": RelicDefinition("pocketwatch", rarity="rare"),
    "rainbow_ring": RelicDefinition("rainbow_ring", rarity="rare"),
    "razor_tooth": RelicDefinition("razor_tooth", rarity="rare"),
    "red_mask": RelicDefinition("red_mask", rarity="common"),
    "reptile_trinket": RelicDefinition("reptile_trinket", rarity="uncommon"),
    "ringing_triangle": RelicDefinition("ringing_triangle", rarity="shop"),
    "ripple_basin": RelicDefinition("ripple_basin", rarity="uncommon"),
    "screaming_flagon": RelicDefinition("screaming_flagon", rarity="shop"),
    "shuriken": RelicDefinition("shuriken", rarity="rare"),
    "sling_of_courage": RelicDefinition("sling_of_courage", rarity="shop"),
    "sparkling_rouge": RelicDefinition("sparkling_rouge", rarity="uncommon"),
    "stone_calendar": RelicDefinition("stone_calendar", rarity="rare"),
    "stone_cracker": RelicDefinition("stone_cracker", rarity="uncommon"),
    "strike_dummy": RelicDefinition("strike_dummy", rarity="common"),
    "sturdy_clamp": RelicDefinition("sturdy_clamp", rarity="rare"),
    "the_abacus": RelicDefinition("the_abacus", rarity="shop"),
    "toolbox": RelicDefinition("toolbox", rarity="shop"),
    "tungsten_rod": RelicDefinition("tungsten_rod", rarity="rare"),
    "tuning_fork": RelicDefinition("tuning_fork", rarity="uncommon", counter_limit=9),
    "unceasing_top": RelicDefinition("unceasing_top", rarity="rare"),
    "unsettling_lamp": RelicDefinition("unsettling_lamp", rarity="rare"),
    "vajra": RelicDefinition("vajra", rarity="common"),
    "vambrace": RelicDefinition("vambrace", rarity="uncommon"),
    "venerable_tea_set": RelicDefinition("venerable_tea_set", rarity="common", counter_limit=1),
    "very_hot_cocoa": RelicDefinition("very_hot_cocoa", rarity="ancient"),
    "vexing_puzzlebox": RelicDefinition("vexing_puzzlebox", rarity="rare"),
    "brimstone": RelicDefinition("brimstone", rarity="shop"),
    "charons_ashes": RelicDefinition("charons_ashes", rarity="rare"),
    "demon_tongue": RelicDefinition("demon_tongue", rarity="rare"),
    "paper_phrog": RelicDefinition("paper_phrog", rarity="uncommon"),
    "red_skull": RelicDefinition("red_skull", rarity="common"),
    "ruined_helmet": RelicDefinition("ruined_helmet", rarity="rare"),
    "self_forming_clay": RelicDefinition("self_forming_clay", rarity="uncommon"),
    "amethyst_aubergine": RelicDefinition("amethyst_aubergine", rarity="common"),
    "book_of_five_rings": RelicDefinition("book_of_five_rings", rarity="common", counter_limit=4),
    "bowler_hat": RelicDefinition("bowler_hat", rarity="uncommon"),
    "cauldron": RelicDefinition("cauldron", rarity="shop"),
    "dingy_rug": RelicDefinition("dingy_rug", rarity="shop"),
    "dollys_mirror": RelicDefinition("dollys_mirror", rarity="shop"),
    "dragon_fruit": RelicDefinition("dragon_fruit", rarity="shop"),
    "eternal_feather": RelicDefinition("eternal_feather", rarity="uncommon"),
    "fresnel_lens": RelicDefinition("fresnel_lens", rarity="event"),
    "frozen_egg": RelicDefinition("frozen_egg", rarity="rare"),
    "gnarled_hammer": RelicDefinition("gnarled_hammer", rarity="shop"),
    "juzu_bracelet": RelicDefinition("juzu_bracelet", rarity="common"),
    "kifuda": RelicDefinition("kifuda", rarity="shop"),
    "lasting_candy": RelicDefinition("lasting_candy", rarity="uncommon", counter_limit=1),
    "lees_waffle": RelicDefinition("lees_waffle", rarity="shop", pickup_max_hp=7),
    "looming_fruit": RelicDefinition("looming_fruit", rarity="ancient", pickup_max_hp=31),
    "lucky_fysh": RelicDefinition("lucky_fysh", rarity="uncommon"),
    "meal_ticket": RelicDefinition("meal_ticket", rarity="common"),
    "meat_on_the_bone": RelicDefinition("meat_on_the_bone", rarity="rare"),
    "membership_card": RelicDefinition("membership_card", rarity="shop"),
    "miniature_tent": RelicDefinition("miniature_tent", rarity="shop"),
    "molten_egg": RelicDefinition("molten_egg", rarity="rare"),
    "old_coin": RelicDefinition("old_coin", rarity="rare", pickup_gold=300),
    "orrery": RelicDefinition("orrery", rarity="shop"),
    "pantograph": RelicDefinition("pantograph", rarity="uncommon"),
    "petrified_toad": RelicDefinition("petrified_toad", rarity="uncommon"),
    "planisphere": RelicDefinition("planisphere", rarity="uncommon"),
    "potion_belt": RelicDefinition("potion_belt", rarity="common"),
    "prayer_wheel": RelicDefinition("prayer_wheel", rarity="rare"),
    "punch_dagger": RelicDefinition("punch_dagger", rarity="shop"),
    "regal_pillow": RelicDefinition("regal_pillow", rarity="common"),
    "royal_stamp": RelicDefinition("royal_stamp", rarity="shop"),
    "shovel": RelicDefinition("shovel", rarity="rare"),
    "the_courier": RelicDefinition("the_courier", rarity="rare"),
    "tiny_mailbox": RelicDefinition("tiny_mailbox", rarity="uncommon"),
    "toxic_egg": RelicDefinition("toxic_egg", rarity="rare"),
    "war_paint": RelicDefinition("war_paint", rarity="common"),
    "whetstone": RelicDefinition("whetstone", rarity="common"),
    "white_beast_statue": RelicDefinition("white_beast_statue", rarity="rare"),
    "white_star": RelicDefinition("white_star", rarity="rare"),
    "wing_charm": RelicDefinition("wing_charm", rarity="shop"),
    "arcane_scroll": RelicDefinition("arcane_scroll", rarity="ancient"),
    "booming_conch": RelicDefinition("booming_conch", rarity="ancient"),
    "cursed_pearl": RelicDefinition("cursed_pearl", rarity="ancient"),
    "fishing_rod": RelicDefinition("fishing_rod", rarity="ancient", counter_limit=2),
    "hefty_tablet": RelicDefinition("hefty_tablet", rarity="ancient"),
    "kaleidoscope": RelicDefinition("kaleidoscope", rarity="ancient"),
    "large_capsule": RelicDefinition("large_capsule", rarity="ancient"),
    "lava_rock": RelicDefinition("lava_rock", rarity="ancient", counter_limit=1),
    "lead_paperweight": RelicDefinition("lead_paperweight", rarity="ancient"),
    "leafy_poultice": RelicDefinition("leafy_poultice", rarity="ancient"),
    "lost_coffer": RelicDefinition("lost_coffer", rarity="ancient"),
    "neows_bones": RelicDefinition("neows_bones", rarity="ancient"),
    "neows_talisman": RelicDefinition("neows_talisman", rarity="ancient"),
    "neows_torment": RelicDefinition("neows_torment", rarity="ancient"),
    "new_leaf": RelicDefinition("new_leaf", rarity="ancient"),
    "phial_holster": RelicDefinition("phial_holster", rarity="ancient"),
    "pomander": RelicDefinition("pomander", rarity="ancient"),
    "precarious_shears": RelicDefinition("precarious_shears", rarity="ancient"),
    "precise_scissors": RelicDefinition("precise_scissors", rarity="ancient"),
    "scroll_boxes": RelicDefinition("scroll_boxes", rarity="ancient"),
    "silken_tress": RelicDefinition("silken_tress", rarity="ancient", counter_limit=1),
    "silver_crucible": RelicDefinition("silver_crucible", rarity="ancient", counter_limit=3),
    "small_capsule": RelicDefinition("small_capsule", rarity="ancient"),
    "stone_humidifier": RelicDefinition("stone_humidifier", rarity="ancient"),
    "winged_boots": RelicDefinition("winged_boots", rarity="ancient", counter_limit=3),
    "chosen_cheese": RelicDefinition("chosen_cheese", allow_duplicates=True, rarity="event"),
    "bone_tea": RelicDefinition("bone_tea", allow_duplicates=True, rarity="event", counter_limit=1),
    "ember_tea": RelicDefinition("ember_tea", allow_duplicates=True, rarity="event", counter_limit=5),
    "tea_of_discourtesy": RelicDefinition("tea_of_discourtesy", allow_duplicates=True, rarity="event", counter_limit=1),
})
