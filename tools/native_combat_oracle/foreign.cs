using System.Reflection;
using System.Text.Json;

internal static class ForeignOracle
{
    public static void Run(Assembly asm, string digest)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n) => asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object Prop(object o,string n) => o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object Call(object o,string n,params object?[] a) => o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        object[] Items(object o) => ((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        string Id(object o) => Prop(Prop(o,"Id"),"Entry").ToString()!.ToLowerInvariant();
        object Get(string method,string suffix) => T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+suffix)).Invoke(null,null)!;
        Array Typed(IEnumerable<object> v,Type t) { var values=v.ToArray();var a=Array.CreateInstance(t,values.Length);Array.Copy(values,a,values.Length);return a; }
        void Field(object o,string n,object value) => o.GetType().GetField(n,flags)!.SetValue(o,value);
        T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,true);
        foreach(var t in asm.GetTypes().Where(t=>!t.IsAbstract && t.IsSubclassOf(T("Models.AbstractModel")) && t.Namespace=="MegaCrit.Sts2.Core.Models.Enchantments"))
            T("Models.ModelDb").GetMethod("Inject")!.Invoke(null,new object[]{t});
        string Family(object pool) => pool.GetType().Name.Replace("CardPool", "").ToLowerInvariant();
        var unlock=T("Unlocks.UnlockState").GetField("all")!.GetValue(null)!;
        var allPools=Items(Prop(unlock,"CharacterCardPools"));
        var constraint=Enum.Parse(T("Entities.Cards.CardMultiplayerConstraint"),"SingleplayerOnly");
        var cardType=T("Models.CardModel");var poolType=T("Models.CardPoolModel");var factory=T("Factories.CardFactory");
        var foreign=allPools.Where(p=>Family(p)!="ironclad").ToArray();
        var rows=new List<object>();var transforms=new List<object>();
        foreach(string seed in new[]{"0","1","2","42","ABC123"}) foreach(string mode in new[]{"plain","wing_charm","silver_crucible","silken_tress","eggs","combined"})
        {
            var player=System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(T("Entities.Players.Player"));
            var context=DispatchProxy.Create(T("Runs.IRunState"),typeof(ForeignContext));var ctx=(ForeignContext)context;
            var rng=Activator.CreateInstance(T("Runs.RunRngSet"),new object[]{seed})!;
            var hash=(int)T("Helpers.StringHelper").GetMethod("GetDeterministicHashCode")!.Invoke(null,new object[]{seed})!;
            var playerRng=Activator.CreateInstance(T("Random.PlayerRngSet"),new object[]{unchecked((uint)hash)})!;
            var playerOdds=Activator.CreateInstance(T("Odds.PlayerOddsSet"),new[]{playerRng})!;
            Field(player,"<Character>k__BackingField",Get("Character","Characters.Ironclad"));Field(player,"<UnlockState>k__BackingField",unlock);
            Field(player,"<Creature>k__BackingField",Activator.CreateInstance(T("Entities.Creatures.Creature"),new object[]{player,80,80})!);
            Field(player,"_runState",context);Field(player,"<PlayerRng>k__BackingField",playerRng);Field(player,"<PlayerOdds>k__BackingField",playerOdds);
            Field(player,"<Deck>k__BackingField",Activator.CreateInstance(T("Entities.Cards.CardPile"),new[]{Enum.Parse(T("Entities.Cards.PileType"),"Deck")})!);
            ctx.Values["get_Rng"]=rng;ctx.Values["get_Players"]=Typed(new[]{player},T("Entities.Players.Player"));ctx.Values["get_CurrentActIndex"]=0;ctx.Values["get_AscensionLevel"]=0;ctx.Values["get_CardMultiplayerConstraint"]=constraint;ctx.Values["get_CurrentMapPointHistoryEntry"]=null;
            var relics=new List<object>();
            var names=mode switch {"wing_charm"=>new[]{"WingCharm"},"silver_crucible"=>new[]{"SilverCrucible"},"silken_tress"=>new[]{"SilkenTress"},"eggs"=>new[]{"MoltenEgg","ToxicEgg","FrozenEgg"},"combined"=>new[]{"WingCharm","SilverCrucible","SilkenTress","MoltenEgg"},_=>Array.Empty<string>()};
            foreach(var name in names) {var r=Call(Get("Relic","Relics."+name),"ToMutable");r.GetType().GetProperty("Owner")!.SetValue(r,player);relics.Add(r);}
            ctx.Values["IterateHookListeners"]=Typed(relics,T("Models.AbstractModel"));
            ctx.CreateOwned=(card,owner,clone)=>{var c=Call(card,clone?"ClonePreservingMutability":"ToMutable");if(!clone){c.GetType().GetProperty("Owner")!.SetValue(c,owner);Call(c,"AfterCreated");}return c;};
            if(seed=="0" && mode=="plain") foreach(string name in new[]{"DeadlyPoison","CosmicIndifference","Reap","GeneticAlgorithm","StrikeSilent","StrikeRegent","StrikeNecrobinder","StrikeDefect"}) foreach(bool inCombat in new[]{false,true}) {
                var original=Call(Get("Card","Cards."+name),"ToMutable");original.GetType().GetProperty("Owner")!.SetValue(original,player);
                var options=Items(factory.GetMethod("GetDefaultTransformationOptions")!.Invoke(null,new[]{original,(object)inCombat})!);
                var samples=new List<object>();
                foreach(uint localSeed in new uint[]{0,1,42}) {
                    var local=Activator.CreateInstance(T("Random.Rng"),new object[]{localSeed,0})!;
                    var replacement=factory.GetMethods().Single(m=>m.Name=="CreateRandomCardForTransform" && m.GetParameters().Length==3).Invoke(null,new[]{original,(object)inCombat,local})!;
                    samples.Add(new{seed=localSeed,selected=Id(replacement),counter=Prop(local,"Counter"),suffix=Call(local,"NextDouble")});
                }
                transforms.Add(new{original=Id(original),inCombat,options=options.Select(Id),samples});
            }
            var rewards=Prop(playerRng,"Rewards");var niche=Prop(rng,"Niche");var sets=new List<object>();var raw=new List<object[]>();
            for(int round=0;round<2;round++) {
                var list=(System.Collections.IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(poolType))!;foreach(var p in foreign)list.Add(p);
                T("Extensions.ListExtensions").GetMethod("StableShuffle")!.MakeGenericMethod(poolType).Invoke(null,new object[]{list,niche});
                var chosen=new List<object>();
                foreach(var pool in Items(list).Take(3)) {
                    var options=Activator.CreateInstance(T("Runs.CardCreationOptions"),new object?[]{Typed(new[]{pool},poolType),Enum.Parse(T("Runs.CardCreationSource"),"Other"),Enum.Parse(T("Runs.CardRarityOddsType"),"RegularEncounter"),null})!;
                    Call(options,"WithFlags",Enum.Parse(T("Runs.CardCreationFlags"),"NoCardPoolModifications"));
                    var result=Items(factory.GetMethods().Single(m=>m.Name=="CreateForReward"&&m.IsPublic).Invoke(null,new object[]{player,1,options})!);
                    chosen.Add(Prop(result[0],"Card"));
                }
                raw.Add(chosen.ToArray());
            }
            foreach(var group in raw) {
                var results=(System.Collections.IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(T("Entities.Cards.CardCreationResult")))!;
                foreach(var c in group)results.Add(Activator.CreateInstance(T("Entities.Cards.CardCreationResult"),new[]{c})!);
                var options=Activator.CreateInstance(T("Runs.CardCreationOptions"),new object[]{Typed(Array.Empty<object>(),cardType),Enum.Parse(T("Runs.CardCreationSource"),"Other"),Enum.Parse(T("Runs.CardRarityOddsType"),"Uniform")})!;
                Call(options,"WithFlags",Enum.Parse(T("Runs.CardCreationFlags"),"NoCardPoolModifications, NoCardModelModifications, IsCardReward"));
                object?[] a={context,player,results,options,null};T("Hooks.Hook").GetMethod("TryModifyCardRewardOptions")!.Invoke(null,a);
                foreach(var m in Items(a[4]!))((Task)Call(m,"AfterModifyingCardRewardOptions")).GetAwaiter().GetResult();
                sets.Add(Items(results).Select(x=>Describe(Prop(x,"Card"))).ToArray());
            }
            object Describe(object c) {var enchant=Prop(c,"Enchantment");return new{id=Id(c),pool=Family(Prop(c,"Pool")),upgrade=Prop(c,"CurrentUpgradeLevel"),enchantment=enchant is null?null:Id(enchant)};}
            rows.Add(new{seed,mode,sets,rewardsCounter=Prop(rewards,"Counter"),rewardsSuffix=Call(rewards,"NextDouble"),nicheCounter=Prop(niche,"Counter"),nicheSuffix=Call(niche,"NextDouble"),offset=Prop(Prop(playerOdds,"CardRarity"),"CurrentValue")});
        }
        var splash=new List<object>();
        foreach(string seed in new[]{"0","1","2","42","ABC123"}) foreach(bool upgraded in new[]{false,true}) {
            var player=System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(T("Entities.Players.Player"));
            var context=DispatchProxy.Create(T("Runs.IRunState"),typeof(ForeignContext));var ctx=(ForeignContext)context;var rng=Activator.CreateInstance(T("Runs.RunRngSet"),new object[]{seed})!;
            Field(player,"<Character>k__BackingField",Get("Character","Characters.Ironclad"));Field(player,"_runState",context);Field(player,"<UnlockState>k__BackingField",unlock);
            ctx.Values["get_Rng"]=rng;ctx.Values["get_Players"]=Typed(new[]{player},T("Entities.Players.Player"));ctx.Values["get_CardMultiplayerConstraint"]=constraint;ctx.Values["get_AscensionLevel"]=0;
            var encounter=Call(Get("Encounter","Encounters.VantomBoss"),"MutableClone");var combat=Activator.CreateInstance(T("Combat.CombatState"),new object?[]{encounter,context,null,null,null})!;
            var creature=Activator.CreateInstance(T("Entities.Creatures.Creature"),new object[]{player,80,80})!;Field(player,"<Creature>k__BackingField",creature);Call(combat,"AddPlayer",player);
            Field(player,"<Deck>k__BackingField",Activator.CreateInstance(T("Entities.Cards.CardPile"),new[]{Enum.Parse(T("Entities.Cards.PileType"),"Deck")})!);
            var options=foreign.SelectMany(p=>Items(Call(p,"GetUnlockedCards",unlock,constraint))).Where(c=>Prop(c,"Type").ToString()=="Attack").ToArray();var crng=Prop(rng,"CombatCardGeneration");
            var generated=Items(factory.GetMethod("GetDistinctForCombat")!.Invoke(null,new object[]{player,Typed(options,cardType),3,crng})!);
            if(upgraded)foreach(var c in generated){Call(c,"UpgradeInternal");Call(c,"FinalizeUpgradeInternal");}
            var eligible=Items(factory.GetMethod("FilterForCombat")!.Invoke(null,new[]{Typed(options,cardType)})!);
            splash.Add(new{seed,upgraded,eligible=eligible.Select(Id),selected=generated.Select(Id),levels=generated.Select(c=>Prop(c,"CurrentUpgradeLevel")),counter=Prop(crng,"Counter"),suffix=Call(crng,"NextDouble")});
        }
        Console.Write(JsonSerializer.Serialize(new{source="Pinned native StableShuffle, reward/combat factories and reward hooks in explicit all-unlocked A0 contexts; source-reproduced acquisition orchestration, no UI/profile/run",assemblySha256=digest,families=foreign.Select(Family),rows,splash,transforms},new JsonSerializerOptions{WriteIndented=true}));
    }
}
public class ForeignContext:DispatchProxy
{
    public Dictionary<string,object?> Values=new();
    public Func<object,object,bool,object>? CreateOwned;
    protected override object? Invoke(MethodInfo? m,object?[]? args) {
        if(m!.Name=="CreateCard")return CreateOwned!(args![0]!,args[1]!,false);
        if(m.Name=="CloneCard")return CreateOwned!(args![0]!,args[0]!.GetType().GetProperty("Owner")!.GetValue(args[0])!,true);
        return Values.TryGetValue(m.Name,out var value)?value:throw new InvalidOperationException("Unexpected native context access: "+m.Name);
    }
}
