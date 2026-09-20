"""Content bindings from native monster properties to executable intent fields."""
from types import MappingProxyType

MOVES = MappingProxyType({
    'TheForgotten': MappingProxyType({
        'Dread': (('attack_damage', 'DreadDamage'),),
    }),
    'DevotedSculptor': MappingProxyType({
        'Savage': (('attack_damage', 'SavageDamage'),),
    }),
    'FrogKnight': MappingProxyType({
        'Strike Down Evil': (('attack_damage', 'StrikeDownEvilDamage'),),
        'Tongue Lash': (('attack_damage', 'TongueLashDamage'),),
        'Beetle Charge': (('attack_damage', 'BeetleChargeDamage'),),
    }),
    'GlobeHead': MappingProxyType({
        'Thunder Strike': (('attack_damage', 'ThunderStrikeDamage'),),
        'Shocking Slap': (('attack_damage', 'ShockingSlapDamage'),),
        'Galvanic Burst': (('attack_damage', 'GalvanicBurstDamage'),),
    }),
    'OwlMagistrate': MappingProxyType({
        'Verdict': (('attack_damage', 'VerdictDamage'),),
        'Magistrate Scrutiny': (('attack_damage', 'ScrutinyDamage'),),
    }),
    'ScrollOfBiting': MappingProxyType({
        'Chomp': (('attack_damage', 'ChompDamage'),),
        'Chew': (('attack_damage', 'ChewDamage'),),
    }),
    'SlimedBerserker': MappingProxyType({
        'Smother': (('attack_damage', 'SmotherDamage'),),
        'Furious Pummeling': (('attack_damage', 'PummelingDamage'),),
    }),
    'TheLost': MappingProxyType({
        'Eye Lasers': (('attack_damage', 'EyeLasersDamage'),),
    }),
    'LivingShield': MappingProxyType({
        'Smash': (('attack_damage', 'SmashDamage'),),
    }),
    'Axebot': MappingProxyType({
        'Boot Up': (('block_gain', 'BootUpBlock'),),
        'One Two': (('attack_damage', 'OneTwoDamage'),),
        'Hammer Uppercut': (('attack_damage', 'HammerUppercutDamage'),),
    }),
    'Fabricator': MappingProxyType({
        'Fabricating Strike': (('attack_damage', 'FabricatingStrikeDamage'),),
        'Disintegrate': (('attack_damage', 'DisintegrateDamage'),),
    }),
    'Zapbot': MappingProxyType({
        'Zap': (('attack_damage', 'ZapDamage'),),
    }),
    'Stabbot': MappingProxyType({
        'Stab': (('attack_damage', 'StabDamage'),),
    }),
    'FlailKnight': MappingProxyType({
        'Flail': (('attack_damage', 'FlailDamage'),),
        'Ram': (('attack_damage', 'RamDamage'),),
    }),
    'SpectralKnight': MappingProxyType({
        'Soul Slash': (('attack_damage', 'SoulSlashDamage'),),
        'Soul Flame': (('attack_damage', 'SoulFlameDamage'),),
    }),
    'MagiKnight': MappingProxyType({
        'Prep': (('block_gain', 'PowerShieldBlock'),),
        'Power Shield': (('attack_damage', 'PowerShieldDamage'), ('block_gain', 'PowerShieldBlock')),
        'Ram': (('attack_damage', 'SpearDamage'),),
        'Magic Bomb': (('attack_damage', 'BombDamage'),),
    }),
    'MechaKnight': MappingProxyType({
        'Charge': (('attack_damage', 'ChargeDamage'),),
        'Heavy Cleave': (('attack_damage', 'HeavyCleaveDamage'),),
    }),
    'SoulNexus': MappingProxyType({
        'Soul Burn': (('attack_damage', 'SoulBurnDamage'),),
        'Maelstrom': (('attack_damage', 'MaelstromDamage'),),
        'Drain Life': (('attack_damage', 'DrainLifeDamage'),),
    }),
    'Aeonglass': MappingProxyType({
        'Ebb': (('attack_damage', 'EbbDamage'),),
        'Eye Lasers': (('attack_damage', 'EyeLasersDamage'),),
    }),
    'Queen': MappingProxyType({
        'Off With Your Head': (('attack_damage', 'OffWithYourHeadDamage'),),
        'Execution': (('attack_damage', 'ExecutionDamage'),),
    }),
    'TorchHeadAmalgam': MappingProxyType({
        'Tackle': (('attack_damage', 'TackleDamage'),),
        'Tackle 2': (('attack_damage', 'TackleDamage'),),
        'Tackle 3': (('attack_damage', 'WeakTackleDamage'),),
        'Tackle 4': (('attack_damage', 'WeakTackleDamage'),),
    }),
    'TestSubject': MappingProxyType({
        'Bite': (('attack_damage', 'BiteDamage'),),
        'Skull Bash': (('attack_damage', 'SkullBashDamage'),),
        'Multi Claw': (('attack_damage', 'MultiClawDamage'),),
        'Phase3 Lacerate': (('attack_damage', 'Phase3LacerateDamage'),),
        'Burning Growl': (('strength_gain', 'BurningGrowlStrengthGain'), ('discard_cards', 'BurningGrowlBurnCount')),
    }),
    'BowlbugEgg': MappingProxyType({
        'Bite': (('attack_damage', 'BiteDamage'), ('block_gain', 'ProtectBlock')),
    }),
    'BowlbugNectar': MappingProxyType({
        'Buff': (('strength_gain', 'BuffStrengthGain'),),
    }),
    'BowlbugRock': MappingProxyType({
        'Headbutt': (('attack_damage', 'HeadbuttDamage'),),
    }),
    'BowlbugSilk': MappingProxyType({
        'Thrash': (('attack_damage', 'ThrashDamage'),),
    }),
    'Chomper': MappingProxyType({
        'Clamp': (('attack_damage', 'ClampDamage'),),
    }),
    'Exoskeleton': MappingProxyType({
        'Mandibles': (('attack_damage', 'MandiblesDamage'),),
        'Skitter': (('attack_count', 'SkitterRepeats'),),
    }),
    'HunterKiller': MappingProxyType({
        'Bite': (('attack_damage', 'BiteDamage'),),
        'Puncture': (('attack_damage', 'PunctureDamage'),),
    }),
    'LouseProgenitor': MappingProxyType({
        'Pounce': (('attack_damage', 'PounceDamage'),),
        'Web Cannon': (('attack_damage', 'WebDamage'),),
        'Curl and Grow': (('block_gain', 'CurlBlock'),),
    }),
    'Myte': MappingProxyType({
        'Bite': (('attack_damage', 'BiteDamage'),),
        'Suck': (('attack_damage', 'SuckDamage'), ('strength_gain', 'SuckStrength')),
    }),
    'SlumberingBeetle': MappingProxyType({
        'Roll Out': (('attack_damage', 'RolloutDamage'),),
    }),
    'Tunneler': MappingProxyType({
        'Bite': (('attack_damage', 'BiteDamage'),),
        'Below': (('attack_damage', 'BelowDamage'),),
        'Burrow': (('block_gain', 'BlockGain'),),
    }),
    'Ovicopter': MappingProxyType({
        'Smash': (('attack_damage', 'SmashDamage'),),
        'Tenderizer': (('attack_damage', 'TenderizerDamage'),),
        'Nutritional Paste': (('strength_gain', 'NutritionalPasteStrengthAmount'),),
    }),
    'ToughEgg': MappingProxyType({
        'Nibble': (('attack_damage', 'NibbleDamage'),),
    }),
    'TheObscura': MappingProxyType({
        'Piercing Gaze': (('attack_damage', 'PiercingGazeDamage'),),
        'Hardening Strike': (('attack_damage', 'HardeningStrikeDamage'), ('block_gain', 'HardeningStrikeBlock')),
    }),
    'Parafright': MappingProxyType({
        'Slam': (('attack_damage', 'SlamDamage'),),
    }),
    'Entomancer': MappingProxyType({
        'Bees': (('attack_count', 'BeesRepeat'),),
        'Spear': (('attack_damage', 'SpearMoveDamage'),),
    }),
    'InfestedPrism': MappingProxyType({
        'Jab': (('attack_damage', 'JabDamage'),),
        'Pulsate': (('attack_damage', 'PulsateDamage'), ('block_gain', 'PulsateBlock')),
        'Radiate': (('attack_damage', 'RadiateDamage'), ('block_gain', 'RadiateBlock')),
        'Whirlwind': (('attack_damage', 'WhirlwindDamage'),),
    }),
    'DecimillipedeSegmentFront': MappingProxyType({
        'Writhe': (('attack_damage', 'WritheDamage'),),
        'Constrict': (('attack_damage', 'ConstrictDamage'),),
        'Bulk': (('attack_damage', 'BulkDamage'),),
    }),
    'DecimillipedeSegmentMiddle': MappingProxyType({
        'Writhe': (('attack_damage', 'WritheDamage'),),
        'Constrict': (('attack_damage', 'ConstrictDamage'),),
        'Bulk': (('attack_damage', 'BulkDamage'),),
    }),
    'DecimillipedeSegmentBack': MappingProxyType({
        'Writhe': (('attack_damage', 'WritheDamage'),),
        'Constrict': (('attack_damage', 'ConstrictDamage'),),
        'Bulk': (('attack_damage', 'BulkDamage'),),
    }),
    'Crusher': MappingProxyType({
        'Thrash': (('attack_damage', 'ThrashDamage'),),
        'Bug Sting': (('attack_damage', 'BugStingDamage'),),
        'Adapt': (('strength_gain', 'AdaptStrengthGain'),),
        'Guarded Strike': (('attack_damage', 'GuardedStrikeDamage'),),
    }),
    'Rocket': MappingProxyType({
        'Targeting Reticle': (('attack_damage', 'TargetingReticleDamage'),),
        'Precision Beam': (('attack_damage', 'PrecisionBeamDamage'),),
        'Laser': (('attack_damage', 'LaserDamage'),),
        'Charge Up': (('strength_gain', 'ChargeUpStrengthGain'),),
    }),
    'KnowledgeDemon': MappingProxyType({
        'Slap': (('attack_damage', 'SlapDamage'),),
        'Ponder': (('attack_damage', 'PonderDamage'), ('strength_gain', 'PonderStrength')),
        'Knowledge Overwhelming': (('attack_damage', 'KnowledgeOverwhelmingDamage'),),
    }),
    'TheInsatiable': MappingProxyType({
        'Thrash': (('attack_damage', 'ThrashDamage'),),
        'Salivate': (('strength_gain', 'SalivateStrength'),),
        'Lunging Bite': (('attack_damage', 'BiteDamage'),),
    }),
    'ThievingHopper': MappingProxyType({
        'Hat Trick': (('attack_damage', 'HatTrickDamage'),),
        'Nab': (('attack_damage', 'NabDamage'),),
        'Thievery': (('attack_damage', 'TheftDamage'),),
    }),
    'CorpseSlug': MappingProxyType({
        'Glomp': (('attack_damage', 'GlompDamage'),),
    }),
    'CalcifiedCultist': MappingProxyType({
        'Dark Strike': (('attack_damage', 'DarkStrikeDamage'),),
    }),
    'DampCultist': MappingProxyType({
        'Dark Strike': (('attack_damage', 'DarkStrikeDamage'),),
    }),
    'FossilStalker': MappingProxyType({
        'Tackle': (('attack_damage', 'TackleDamage'),),
        'Latch': (('attack_damage', 'LatchDamage'),),
        'Lash': (('attack_damage', 'LashDamage'),),
    }),
    'HauntedShip': MappingProxyType({
        'Swipe': (('attack_damage', 'SwipeDamage'),),
        'Stomp': (('attack_damage', 'StompDamage'),),
    }),
    'Seapunk': MappingProxyType({
        'Sea Kick': (('attack_damage', 'SeaKickDamage'),),
        'Bubble Burp': (('block_gain', 'BubbleBlock'), ('strength_gain', 'BubbleStr')),
    }),
    'SewerClam': MappingProxyType({
        'Jet': (('attack_damage', 'JetDamage'),),
    }),
    'SludgeSpinner': MappingProxyType({
        'Oil Spray': (('attack_damage', 'OilSprayDamage'),),
        'Slam': (('attack_damage', 'SlamDamage'),),
        'Rage': (('attack_damage', 'RageDamage'),),
    }),
    'Toadpole': MappingProxyType({
        'Spike Spit': (('attack_damage', 'SpikeSpitDamage'),),
        'Whirl': (('attack_damage', 'WhirlDamage'),),
    }),
    'TwoTailedRat': MappingProxyType({
        'Scratch': (('attack_damage', 'ScratchDamage'),),
        'Disease Bite': (('attack_damage', 'DiseaseBiteDamage'),),
    }),
    'GremlinMerc': MappingProxyType({
        'Gimme': (('attack_damage', 'GimmeDamage'),),
        'Double Smash': (('attack_damage', 'DoubleSmashDamage'),),
        'Hehe': (('attack_damage', 'HeheDamage'),),
    }),
    'SneakyGremlin': MappingProxyType({
        'Tackle': (('attack_damage', 'TackleDamage'),),
    }),
    'LivingFog': MappingProxyType({
        'Advanced Gas': (('attack_damage', 'AdvancedGasDamage'),),
        'Bloat': (('attack_damage', 'BloatDamage'),),
        'Super Gas Blast': (('attack_damage', 'SuperGasBlastDamage'),),
    }),
    'GasBomb': MappingProxyType({
        'Explode': (('attack_damage', 'ExplodeDamage'),),
    }),
    'SkulkingColony': MappingProxyType({
        'Inertia': (('attack_damage', 'InertiaDamage'), ('strength_gain', 'InertiaStrengthGain')),
        'Zoom': (('attack_damage', 'ZoomDamage'),),
        'Piercing Stabs': (('attack_damage', 'PiercingStabsDamage'),),
    }),
    'TerrorEel': MappingProxyType({
        'Crash': (('attack_damage', 'CrashDamage'),),
        'Thrash': (('attack_damage', 'ThrashDamage'),),
    }),
    'LagavulinMatriarch': MappingProxyType({
        'Slash': (('attack_damage', 'SlashDamage'),),
        'Disembowel': (('attack_damage', 'DisembowelDamage'),),
        'Slash and Guard': (('attack_damage', 'Slash2Damage'), ('block_gain', 'Slash2Block')),
    }),
    'SoulFysh': MappingProxyType({
        'De-Gas': (('attack_damage', 'DeGasDamage'),),
        'Scream': (('attack_damage', 'ScreamDamage'),),
        'Gaze': (('attack_damage', 'GazeDamage'),),
    }),
    'WaterfallGiant': MappingProxyType({
        'Siphon': (('value', 'SiphonHeal'),),
        'Stomp': (('attack_damage', 'StompDamage'),),
        'Ram': (('attack_damage', 'RamDamage'),),
        'Pressure Up': (('attack_damage', 'PressureUpDamage'),),
    }),
    'PunchConstruct': MappingProxyType({
        'Strong Punch': (('attack_damage', 'StrongPunchDamage'),),
        'Fast Punch': (('attack_damage', 'FastPunchDamage'),),
    }),
    'FakeMerchantMonster': MappingProxyType({
        'Swipe': (('attack_damage', 'SwipeDamage'),),
        'Throw Relic': (('attack_damage', 'ThrowRelicDamage'),),
    }),
    'Nibbit': MappingProxyType({
        'Butt': (('attack_damage', 'ButtDamage'),),
        'Hiss': (('strength_gain', 'HissStrengthGain'),),
        'Hesitant Slice': (('attack_damage', 'SliceDamage'), ('block_gain', 'SliceBlock')),
    }),
    'ShrinkerBeetle': MappingProxyType({
        'Chomp': (('attack_damage', 'ChompDamage'),),
        'Stomp': (('attack_damage', 'StompDamage'),),
    }),
    'FuzzyWurmCrawler': MappingProxyType({
        'Acid Goop': (('attack_damage', 'AcidGoopDamage'),),
    }),
    'Mawler': MappingProxyType({
        'Rip and Tear': (('attack_damage', 'RipAndTearDamage'),),
        'Claw': (('attack_damage', 'ClawDamage'),),
    }),
    'Byrdonis': MappingProxyType({
        'Peck': (('attack_damage', 'PeckDamage'),),
        'Swoop': (('attack_damage', 'SwoopDamage'),),
    }),
    'Vantom': MappingProxyType({
        'Ink Blot': (('attack_damage', 'InkBlotDamage'),),
        'Inky Lance': (('attack_damage', 'InkyLanceDamage'),),
        'Dismember': (('attack_damage', 'DismemberDamage'),),
    }),
    'VineShambler': MappingProxyType({
        'Grasping Vines': (('attack_damage', 'GraspingVinesDamage'),),
        'Swipe': (('attack_damage', 'SwipeDamage'),),
        'Chomp': (('attack_damage', 'ChompDamage'),),
    }),
    'SlitheringStrangler': MappingProxyType({
        'Thwack': (('attack_damage', 'ThwackDamage'),),
        'Lash': (('attack_damage', 'LashDamage'),),
    }),
    'Inklet': MappingProxyType({
        'Jab': (('attack_damage', 'JabDamage'),),
        'Whirlwind': (('attack_damage', 'WhirlwindDamage'),),
        'Piercing Gaze': (('attack_damage', 'PiercingGazeDamage'),),
    }),
    'Flyconid': MappingProxyType({
        'Smash': (('attack_damage', 'SmashDamage'),),
        'Frail Spores': (('attack_damage', 'SporeDamage'),),
    }),
    'AssassinRubyRaider': MappingProxyType({
        'Killshot': (('attack_damage', 'KillshotDamage'),),
    }),
    'AxeRubyRaider': MappingProxyType({
        'Swing': (('attack_damage', 'SwingDamage'), ('block_gain', 'SwingBlock')),
        'Big Swing': (('attack_damage', 'BigSwingDamage'),),
    }),
    'BruteRubyRaider': MappingProxyType({
        'Beat': (('attack_damage', 'BeatDamage'),),
    }),
    'CrossbowRubyRaider': MappingProxyType({
        'Fire': (('attack_damage', 'FireDamage'),),
    }),
    'TrackerRubyRaider': MappingProxyType({
        'Hounds': (('attack_count', 'HoundsRepeat'),),
    }),
    'BygoneEffigy': MappingProxyType({
        'Slash': (('attack_damage', 'SlashDamage'),),
    }),
    'CeremonialBeast': MappingProxyType({
        'Plow': (('attack_damage', 'PlowDamage'),),
        'Stomp': (('attack_damage', 'StompDamage'),),
        'Crush': (('attack_damage', 'CrushDamage'), ('strength_gain', 'CrushStrength')),
    }),
    'KinFollower': MappingProxyType({
        'Dance': (('strength_gain', 'DanceStrength'),),
    }),
    'KinPriest': MappingProxyType({
        'Orb of Frailty': (('attack_damage', 'OrbOfFrailtyDamage'),),
        'Orb of Weakness': (('attack_damage', 'OrbOfWeaknessDamage'),),
        'Ritual': (('strength_gain', 'RitualStrength'),),
    }),
    'PhrogParasite': MappingProxyType({
        'Lash': (('attack_damage', 'LashDamage'),),
    }),
    'Wriggler': MappingProxyType({
        'Bite': (('attack_damage', 'BiteDamage'),),
    }),
    'Fogmog': MappingProxyType({
        'Swipe': (('attack_damage', 'SwipeDamage'),),
        'Headbutt': (('attack_damage', 'HeadbuttDamage'),),
    }),
    'LeafSlimeSmall': MappingProxyType({
        'Tackle': (('attack_damage', 'TackleDamage'),),
    }),
    'TwigSlimeSmall': MappingProxyType({
        'Tackle': (('attack_damage', 'TackleDamage'),),
    }),
    'SpinyToad': MappingProxyType({
        'Tongue Lash': (('attack_damage', 'LashDamage'),),
        'Spike Explosion': (('attack_damage', 'ExplosionDamage'),),
    }),
    'CubexConstruct': MappingProxyType({
        'Repeater Blast': (('attack_damage', 'BlastDamage'),),
        'Expel Blast': (('attack_damage', 'ExpelDamage'),),
    }),
    'SnappingJaxfruit': MappingProxyType({
        'Energy Orb': (('attack_damage', 'EnergyDamage'),),
    }),
    'LeafSlimeMedium': MappingProxyType({
        'Clump Shot': (('attack_damage', 'ClumpDamage'),),
    }),
    'TwigSlimeMedium': MappingProxyType({
        'Chomp': (('attack_damage', 'ClumpDamage'),),
    }),
    'TurretOperator': MappingProxyType({
        'Unload': (('attack_damage', 'FireDamage'),),
        'Unload 2': (('attack_damage', 'FireDamage'),),
    }),
    'PhantasmalGardener': MappingProxyType({
        'Enlarge': (('strength_gain', 'EnlargeStr'),),
    }),
})
