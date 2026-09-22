"""Pinned immutable room-generation inputs, including saved future-act queues."""

from types import MappingProxyType

ACT_POOLS = (
    (
        "overgrowth",
        15,
        3,
        (
            "aroma_of_chaos",
            "byrdonis_nest",
            "dense_vegetation",
            "jungle_maze_adventure",
            "luminous_choir",
            "morphic_grove",
            "sapphire_seed",
            "sunken_statue",
            "tablet_of_truth",
            "unrest_site",
            "wellspring",
            "whispering_hollow",
            "wood_carvings",
        ),
        ("neow",),
        (
            ("FuzzyWurmCrawlerWeak", "NibbitsWeak", "ShrinkerBeetleWeak", "SlimesWeak"),
            (
                "CubexConstructNormal",
                "FlyconidNormal",
                "FogmogNormal",
                "InkletsNormal",
                "MawlerNormal",
                "NibbitsNormal",
                "OvergrowthCrawlers",
                "RubyRaidersNormal",
                "SlimesNormal",
                "SlitheringStranglerNormal",
                "SnappingJaxfruitNormal",
                "VineShamblerNormal",
            ),
            ("BygoneEffigyElite", "ByrdonisElite", "PhrogParasiteElite"),
            ("CeremonialBeastBoss", "TheKinBoss", "VantomBoss"),
        ),
    ),
    (
        "hive",
        14,
        2,
        (
            "amalgamator",
            "bugslayer",
            "colorful_philosophers",
            "colossal_flower",
            "field_of_man_sized_holes",
            "infested_automaton",
            "lost_wisp",
            "spirit_grafter",
            "the_lantern_key",
            "zen_weaver",
        ),
        ("orobas", "pael", "tezcatara"),
        (
            ("BowlbugsWeak", "ExoskeletonsWeak", "ThievingHopperWeak", "TunnelerWeak"),
            (
                "BowlbugsNormal",
                "ChompersNormal",
                "ExoskeletonsNormal",
                "HunterKillerNormal",
                "LouseProgenitorNormal",
                "MytesNormal",
                "OvicopterNormal",
                "SlumberingBeetleNormal",
                "SpinyToadNormal",
                "TheObscuraNormal",
            ),
            ("DecimillipedeElite", "EntomancerElite", "InfestedPrismsElite"),
            ("KaiserCrabBoss", "KnowledgeDemonBoss", "TheInsatiableBoss"),
        ),
    ),
    (
        "glory",
        13,
        2,
        (
            "battleworn_dummy",
            "grave_of_the_forgotten",
            "hungry_for_mushrooms",
            "reflections",
            "round_tea_party",
            "trial",
            "tinker_time",
        ),
        ("nonupeipe", "tanx", "vakuu"),
        (
            ("DevotedSculptorWeak", "ScrollsOfBitingWeak", "TurretOperatorWeak"),
            (
                "AxebotsNormal",
                "ConstructMenagerieNormal",
                "FabricatorNormal",
                "FrogKnightNormal",
                "GlobeHeadNormal",
                "OwlMagistrateNormal",
                "ScrollsOfBitingNormal",
                "SlimedBerserkerNormal",
                "TheLostAndForgottenNormal",
            ),
            ("KnightsElite", "MechaKnightElite", "SoulNexusElite"),
            ("AeonglassBoss", "QueenBoss", "TestSubjectBoss"),
        ),
    ),
)

SHARED_EVENTS = (
    "brain_leech",
    "crystal_sphere",
    "doll_room",
    "fake_merchant",
    "potion_courier",
    "ranwid_the_elder",
    "relic_trader",
    "room_full_of_cheese",
    "self_help_book",
    "slippery_bridge",
    "stone_of_all_time",
    "symbiote",
    "tea_master",
    "the_future_of_potions",
    "the_legends_were_true",
    "this_or_that",
    "war_historian_repy",
    "welcome_to_wongos",
)

SHARED_ANCIENTS = ("darv",)

ENCOUNTER_TAGS = MappingProxyType(
    {
        "CorpseSlugsNormal": (13,),
        "CorpseSlugsWeak": (13,),
        "SeapunkNormal": (12,),
        "SeapunkWeak": (12,),
        "FlyconidNormal": (9, 5),
        "FuzzyWurmCrawlerWeak": (8,),
        "NibbitsWeak": (3,),
        "OvergrowthCrawlers": (4, 8),
        "ShrinkerBeetleWeak": (4,),
        "SlimesNormal": (5,),
        "SlimesWeak": (5,),
        "SnappingJaxfruitNormal": (9,),
        "BowlbugsNormal": (7,),
        "BowlbugsWeak": (7,),
        "ChompersNormal": (2,),
        "ExoskeletonsNormal": (14,),
        "ExoskeletonsWeak": (14,),
        "SlumberingBeetleNormal": (7,),
        "ThievingHopperWeak": (6,),
        "TunnelerWeak": (1,),
        "KnightsElite": (10,),
        "ScrollsOfBitingNormal": (11,),
        "ScrollsOfBitingWeak": (11,),
    }
)


# Native Act-1 eligibility exclusions; retained in the shuffled room queue.
ACT1_INELIGIBLE_EVENTS = (
    "crystal_sphere",
    "doll_room",
    "fake_merchant",
    "potion_courier",
    "ranwid_the_elder",
    "relic_trader",
    "stone_of_all_time",
    "symbiote",
    "welcome_to_wongos",
    "war_historian_repy",
)


UNDERDOCKS = (
    'underdocks', 15, 3,
    ('abyssal_baths', 'drowning_beacon', 'endless_conveyor', 'punch_off',
     'spiraling_whirlpool', 'sunken_statue', 'sunken_treasury',
     'doors_of_light_and_dark', 'trash_heap', 'waterlogged_scriptorium'),
    ('neow',),
    (
        ('CorpseSlugsWeak', 'SeapunkWeak', 'SludgeSpinnerWeak', 'ToadpolesWeak'),
        ('CorpseSlugsNormal', 'CultistsNormal', 'FossilStalkerNormal',
         'GremlinMercNormal', 'HauntedShipNormal', 'LivingFogNormal',
         'PunchConstructNormal', 'SeapunkNormal', 'SewerClamNormal', 'TwoTailedRatsNormal'),
        ('PhantasmalGardenersElite', 'SkulkingColonyElite', 'TerrorEelElite'),
        ('LagavulinMatriarchBoss', 'SoulFyshBoss', 'WaterfallGiantBoss'),
    ),
)
ACT1_POOLS = MappingProxyType({'overgrowth': ACT_POOLS[0], 'underdocks': UNDERDOCKS})
REGION_POOLS = MappingProxyType({**{a[0]: a for a in ACT_POOLS}, 'underdocks': UNDERDOCKS})


def campaign_pools(first_act):
    if first_act not in ACT1_POOLS:
        raise ValueError('Unsupported Act 1 location.')
    return (ACT1_POOLS[first_act], *ACT_POOLS[1:])
