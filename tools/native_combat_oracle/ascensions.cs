using System.Reflection;
using System.Text.Json;
using System.Runtime.CompilerServices;

internal static class AscensionOracle
{
    public static void Run(Assembly asm, string digest)
    {
        const BindingFlags flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        object Get(string kind,string name)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==kind&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+name)).Invoke(null,null)!;
        var manager=T("Runs.RunManager").GetProperty("Instance")!.GetValue(null)!;
        var state=T("Runs.RunManager").GetProperty("State",flags)!;
        var asc=T("Runs.RunManager").GetProperty("AscensionManager",flags)!;
        if(state.GetValue(manager) is not null)throw new InvalidOperationException("Fixture requires an unused process.");
        var oldAsc=asc.GetValue(manager);
        var selection=new Dictionary<string,string[]> {
            ["Aeonglass"] = new[]{"MinInitialHp","MaxInitialHp","EbbDamage","EyeLasersDamage","IncreasingIntensityBaseStrength","WitherAmount"},
            ["AssassinRubyRaider"] = new[]{"MinInitialHp","MaxInitialHp","KillshotDamage"},
            ["AxeRubyRaider"] = new[]{"MinInitialHp","MaxInitialHp","SwingDamage","SwingBlock","BigSwingDamage"},
            ["Axebot"] = new[]{"MinInitialHp","MaxInitialHp","BootUpBlock","OneTwoDamage","BootUpStrGain","HammerUppercutDamage"},
            ["BowlbugEgg"] = new[]{"MinInitialHp","MaxInitialHp","BiteDamage","ProtectBlock"},
            ["BowlbugNectar"] = new[]{"MinInitialHp","MaxInitialHp","BuffStrengthGain"},
            ["BowlbugRock"] = new[]{"MinInitialHp","MaxInitialHp","HeadbuttDamage"},
            ["BowlbugSilk"] = new[]{"MinInitialHp","MaxInitialHp","ThrashDamage"},
            ["BruteRubyRaider"] = new[]{"MinInitialHp","MaxInitialHp","BeatDamage"},
            ["BygoneEffigy"] = new[]{"MinInitialHp","MaxInitialHp","SlashDamage"},
            ["Byrdonis"] = new[]{"MinInitialHp","MaxInitialHp","PeckDamage","PeckRepeat","SwoopDamage"},
            ["CalcifiedCultist"] = new[]{"MinInitialHp","MaxInitialHp","DarkStrikeDamage"},
            ["CeremonialBeast"] = new[]{"MinInitialHp","MaxInitialHp","PlowAmount","PlowDamage","StompDamage","CrushDamage","CrushStrength"},
            ["Chomper"] = new[]{"MinInitialHp","MaxInitialHp","ClampDamage"},
            ["CorpseSlug"] = new[]{"MinInitialHp","MaxInitialHp","GlompDamage","RavenousStr"},
            ["CrossbowRubyRaider"] = new[]{"MinInitialHp","MaxInitialHp","FireDamage"},
            ["Crusher"] = new[]{"MinInitialHp","MaxInitialHp","ThrashDamage","EnlargingStrikeDamage","BugStingDamage","AdaptStrengthGain","GuardedStrikeDamage"},
            ["CubexConstruct"] = new[]{"MinInitialHp","MaxInitialHp","BlastDamage","ExpelDamage"},
            ["DampCultist"] = new[]{"MinInitialHp","MaxInitialHp","DarkStrikeDamage","IncantationAmount"},
            ["DecimillipedeSegment"] = new[]{"MinInitialHp","MaxInitialHp","WritheDamage","ConstrictDamage","BulkDamage"},
            ["DevotedSculptor"] = new[]{"MinInitialHp","MaxInitialHp","SavageDamage"},
            ["Entomancer"] = new[]{"MinInitialHp","MaxInitialHp","SpearMoveDamage","BeesRepeat","BeesDamage"},
            ["Exoskeleton"] = new[]{"MinInitialHp","MaxInitialHp","SkitterRepeats","MandiblesDamage"},
            ["Fabricator"] = new[]{"MinInitialHp","MaxInitialHp","FabricatingStrikeDamage","DisintegrateDamage"},
            ["FakeMerchantMonster"] = new[]{"MinInitialHp","MaxInitialHp","SwipeDamage","ThrowRelicDamage"},
            ["FatGremlin"] = new[]{"MinInitialHp","MaxInitialHp"},
            ["FlailKnight"] = new[]{"MinInitialHp","MaxInitialHp","FlailDamage","RamDamage"},
            ["Flyconid"] = new[]{"MinInitialHp","MaxInitialHp","SmashDamage","SporeDamage"},
            ["Fogmog"] = new[]{"MinInitialHp","MaxInitialHp","SwipeDamage","HeadbuttDamage"},
            ["FossilStalker"] = new[]{"MinInitialHp","MaxInitialHp","TackleDamage","LatchDamage","LashDamage"},
            ["FrogKnight"] = new[]{"MinInitialHp","MaxInitialHp","StrikeDownEvilDamage","TongueLashDamage","BeetleChargeDamage","PlatingAmount"},
            ["FuzzyWurmCrawler"] = new[]{"MinInitialHp","MaxInitialHp","AcidGoopDamage"},
            ["GasBomb"] = new[]{"MinInitialHp","MaxInitialHp","ExplodeDamage"},
            ["GlobeHead"] = new[]{"MinInitialHp","MaxInitialHp","ThunderStrikeDamage","ShockingSlapDamage","GalvanicBurstDamage"},
            ["GremlinMerc"] = new[]{"MinInitialHp","MaxInitialHp","GimmeDamage","DoubleSmashDamage","HeheDamage"},
            ["Guardbot"] = new[]{"MinInitialHp","MaxInitialHp"},
            ["HauntedShip"] = new[]{"MinInitialHp","MaxInitialHp","SwipeDamage","StompDamage"},
            ["HunterKiller"] = new[]{"MinInitialHp","MaxInitialHp","BiteDamage","PunctureDamage"},
            ["InfestedPrism"] = new[]{"MinInitialHp","MaxInitialHp","JabDamage","VitalSparkAmount","PulsateDamage","PulsateBlock","RadiateDamage","RadiateBlock","WhirlwindDamage"},
            ["Inklet"] = new[]{"MinInitialHp","MaxInitialHp","JabDamage","WhirlwindDamage","PiercingGazeDamage"},
            ["KinFollower"] = new[]{"MinInitialHp","MaxInitialHp","QuickSlashDamage","BoomerangDamage","DanceStrength"},
            ["KinPriest"] = new[]{"MinInitialHp","MaxInitialHp","OrbOfFrailtyDamage","OrbOfWeaknessDamage","BeamDamage","RitualStrength"},
            ["KnowledgeDemon"] = new[]{"MinInitialHp","MaxInitialHp","SlapDamage","PonderDamage","KnowledgeOverwhelmingDamage","PonderStrength"},
            ["LagavulinMatriarch"] = new[]{"MinInitialHp","MaxInitialHp","SlashDamage","Slash2Damage","Slash2Block","DisembowelDamage"},
            ["LeafSlimeM"] = new[]{"MinInitialHp","MaxInitialHp","ClumpDamage"},
            ["LeafSlimeS"] = new[]{"MinInitialHp","MaxInitialHp","TackleDamage"},
            ["LivingFog"] = new[]{"MinInitialHp","MaxInitialHp","AdvancedGasDamage","BloatDamage","SuperGasBlastDamage"},
            ["LivingShield"] = new[]{"MinInitialHp","MaxInitialHp","SmashDamage"},
            ["LouseProgenitor"] = new[]{"MinInitialHp","MaxInitialHp","WebDamage","PounceDamage","CurlBlock"},
            ["MagiKnight"] = new[]{"MinInitialHp","MaxInitialHp","PowerShieldDamage","PowerShieldBlock","SpearDamage","BombDamage"},
            ["Mawler"] = new[]{"MinInitialHp","MaxInitialHp","RipAndTearDamage","ClawDamage"},
            ["MechaKnight"] = new[]{"MinInitialHp","MaxInitialHp","ChargeDamage","HeavyCleaveDamage"},
            ["Myte"] = new[]{"MinInitialHp","MaxInitialHp","BiteDamage","SuckDamage","SuckStrength"},
            ["Nibbit"] = new[]{"MinInitialHp","MaxInitialHp","ButtDamage","SliceBlock","SliceDamage","HissStrengthGain"},
            ["Noisebot"] = new[]{"MinInitialHp","MaxInitialHp"},
            ["Ovicopter"] = new[]{"MinInitialHp","MaxInitialHp","SmashDamage","TenderizerDamage","NutritionalPasteStrengthAmount"},
            ["OwlMagistrate"] = new[]{"MinInitialHp","MaxInitialHp","VerdictDamage","ScrutinyDamage","PeckAssaultDamage"},
            ["Parafright"] = new[]{"MinInitialHp","MaxInitialHp","SlamDamage"},
            ["PhantasmalGardener"] = new[]{"MinInitialHp","MaxInitialHp","BiteDamage","LashDamage","FlailRepeat","EnlargeStr","SkittishAmount"},
            ["PhrogParasite"] = new[]{"MinInitialHp","MaxInitialHp","LashDamage"},
            ["PunchConstruct"] = new[]{"MinInitialHp","MaxInitialHp","StrongPunchDamage","FastPunchDamage"},
            ["Queen"] = new[]{"MinInitialHp","MaxInitialHp","OffWithYourHeadDamage","ExecutionDamage"},
            ["Rocket"] = new[]{"MinInitialHp","MaxInitialHp","TargetingReticleDamage","PrecisionBeamDamage","LaserDamage","ChargeUpStrengthGain"},
            ["ScrollOfBiting"] = new[]{"MinInitialHp","MaxInitialHp","ChompDamage","ChewDamage"},
            ["Seapunk"] = new[]{"MinInitialHp","MaxInitialHp","SeaKickDamage","BubbleBlock","BubbleStr"},
            ["SewerClam"] = new[]{"MinInitialHp","MaxInitialHp","JetDamage"},
            ["ShrinkerBeetle"] = new[]{"MinInitialHp","MaxInitialHp","ChompDamage","StompDamage"},
            ["SkulkingColony"] = new[]{"MinInitialHp","MaxInitialHp","InertiaDamage","ZoomDamage","PiercingStabsDamage","InertiaStrengthGain"},
            ["SlimedBerserker"] = new[]{"MinInitialHp","MaxInitialHp","PummelingDamage","SmotherDamage"},
            ["SlitheringStrangler"] = new[]{"MinInitialHp","MaxInitialHp","ThwackDamage","LashDamage"},
            ["SludgeSpinner"] = new[]{"MinInitialHp","MaxInitialHp","OilSprayDamage","SlamDamage","RageDamage"},
            ["SlumberingBeetle"] = new[]{"MinInitialHp","MaxInitialHp","RolloutDamage","PlatingAmount"},
            ["SnappingJaxfruit"] = new[]{"MinInitialHp","MaxInitialHp","EnergyDamage"},
            ["SneakyGremlin"] = new[]{"MinInitialHp","MaxInitialHp","TackleDamage"},
            ["SoulFysh"] = new[]{"MinInitialHp","MaxInitialHp","DeGasDamage","ScreamDamage","GazeDamage"},
            ["SoulNexus"] = new[]{"MinInitialHp","MaxInitialHp","SoulBurnDamage","MaelstromDamage","MaelstromRepeat","DrainLifeDamage"},
            ["SpectralKnight"] = new[]{"MinInitialHp","MaxInitialHp","SoulSlashDamage","SoulFlameDamage"},
            ["SpinyToad"] = new[]{"MinInitialHp","MaxInitialHp","LashDamage","ExplosionDamage"},
            ["Stabbot"] = new[]{"MinInitialHp","MaxInitialHp","StabDamage"},
            ["TerrorEel"] = new[]{"MinInitialHp","MaxInitialHp","ShriekAmount","CrashDamage","ThrashDamage"},
            ["TestSubject"] = new[]{"MinInitialHp","MaxInitialHp","FirstFormHp","SecondFormHp","ThirdFormHp","EnrageAmount","BiteDamage","SkullBashDamage","MultiClawDamage","Phase3LacerateDamage","BurningGrowlBurnCount","BurningGrowlStrengthGain"},
            ["TheAdversaryMkThree"] = new[]{"MinInitialHp","MaxInitialHp"},
            ["TheAdversaryMkTwo"] = new[]{"MinInitialHp","MaxInitialHp"},
            ["TheForgotten"] = new[]{"MinInitialHp","MaxInitialHp","DebilitatingSmogDexStealAmount","DreadDamage"},
            ["TheInsatiable"] = new[]{"MinInitialHp","MaxInitialHp","ThrashDamage","BiteDamage","SalivateStrength"},
            ["TheLost"] = new[]{"MinInitialHp","MaxInitialHp","EyeLasersDamage","DebilitatingSmogStrengthStealAmount"},
            ["TheObscura"] = new[]{"MinInitialHp","MaxInitialHp","PiercingGazeDamage","HardeningStrikeDamage","HardeningStrikeBlock"},
            ["ThievingHopper"] = new[]{"MinInitialHp","MaxInitialHp","TheftDamage","HatTrickDamage","NabDamage"},
            ["Toadpole"] = new[]{"MinInitialHp","MaxInitialHp","SpikeSpitDamage","WhirlDamage"},
            ["TorchHeadAmalgam"] = new[]{"MinInitialHp","MaxInitialHp","TackleDamage","WeakTackleDamage","SoulBeamDamage"},
            ["ToughEgg"] = new[]{"MinInitialHp","MaxInitialHp","HatchlingMinHp","HatchlingMaxHp","NibbleDamage"},
            ["TrackerRubyRaider"] = new[]{"MinInitialHp","MaxInitialHp","HoundsDamage","HoundsRepeat"},
            ["Tunneler"] = new[]{"MinInitialHp","MaxInitialHp","BiteDamage","BlockGain","BelowDamage"},
            ["TurretOperator"] = new[]{"MinInitialHp","MaxInitialHp","FireDamage"},
            ["TwigSlimeM"] = new[]{"MinInitialHp","MaxInitialHp","ClumpDamage"},
            ["TwigSlimeS"] = new[]{"MinInitialHp","MaxInitialHp","TackleDamage"},
            ["TwoTailedRat"] = new[]{"MinInitialHp","MaxInitialHp","ScratchDamage","DiseaseBiteDamage"},
            ["Vantom"] = new[]{"MinInitialHp","MaxInitialHp","SlipperyAmt","InkBlotDamage","InkyLanceDamage","DismemberDamage"},
            ["VineShambler"] = new[]{"MinInitialHp","MaxInitialHp","GraspingVinesDamage","SwipeDamage","ChompDamage"},
            ["WaterfallGiant"] = new[]{"MinInitialHp","MaxInitialHp","SiphonHeal","PressurizeAmount","StompDamage","RamDamage","PressureUpDamage","BasePressureGunDamage"},
            ["Wriggler"] = new[]{"MinInitialHp","MaxInitialHp","BiteDamage"},
            ["Zapbot"] = new[]{"MinInitialHp","MaxInitialHp","ZapDamage"},
        };
        var rows=new List<object>();
        try {
            // Constructor-free, process-local context. No RunManager initialization,
            // save manager, profile, history, user directory or game engine launch.
            state.SetValue(manager,RuntimeHelpers.GetUninitializedObject(T("Runs.RunState")));
            foreach(int level in Enumerable.Range(0,11)) {
                asc.SetValue(manager,Activator.CreateInstance(T("Entities.Ascension.AscensionManager"),new object[]{level}));
                var monsters=new List<object>();
                foreach(var pair in selection) {
                    var modelType=T("Models.Monsters."+pair.Key);
                    var concrete=modelType.IsAbstract?asm.GetTypes().First(t=>!t.IsAbstract&&t.IsSubclassOf(modelType)).Name:pair.Key;
                    var monster=C(Get("Monster","Monsters."+concrete),"ToMutable");
                    Activator.CreateInstance(T("Entities.Creatures.Creature"),new object?[]{monster,Enum.Parse(T("Combat.CombatSide"),"Enemy"),null});
                    var values=pair.Value.ToDictionary(n=>n,n=>Convert.ToInt32(modelType.GetProperty(n,flags)!.GetValue(monster)));
                    monsters.Add(new{type=pair.Key,values});
                }
                var odds=Activator.CreateInstance(T("Odds.CardRarityOdds"),new[]{Activator.CreateInstance(T("Random.Rng"),new object[]{42u,0})!})!;
                var rarity=T("Odds.CardRarityOdds");
                var removal=T("Entities.Merchant.MerchantCardRemovalEntry");
                var encounters=new[]{"NibbitsWeak","ByrdonisElite","VantomBoss","FakeMerchantEventEncounter"}.Select(n=>{var e=Get("Encounter","Encounters."+n);return new{type=n,min=P(e,"MinGoldReward"),max=P(e,"MaxGoldReward")};}).ToArray();
                rows.Add(new{ascension=level,monsters,encounters,elites=P(Activator.CreateInstance(T("Map.MapPointTypeCounts"),new object[]{12,5})!,"NumOfElites"),
                    removalBase=removal.GetProperty("BaseCost",flags)!.GetValue(null),removalIncrement=removal.GetProperty("PriceIncrease",flags)!.GetValue(null),
                    rarityGrowth=P(odds,"RarityGrowth"),rareCombat=rarity.GetProperty("RegularRareOdds")!.GetValue(null),rareElite=rarity.GetProperty("EliteRareOdds")!.GetValue(null),rareShop=rarity.GetProperty("ShopRareOdds")!.GetValue(null)});
            }
        } finally {state.SetValue(manager,null);asc.SetValue(manager,oldAsc);}
        Console.Write(JsonSerializer.Serialize(new{source="Pinned ascension getters and in-memory monster/creature construction, no native combat or campaign execution",assemblySha256=digest,contextCleared=state.GetValue(manager) is null,rows},new JsonSerializerOptions{WriteIndented=true}));
    }
}
