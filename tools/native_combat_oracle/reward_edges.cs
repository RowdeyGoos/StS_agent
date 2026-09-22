using System.Reflection;
using System.Text.Json;

internal static class RewardEdgeOracle
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
        var unlock=T("Unlocks.UnlockState").GetField("all")!.GetValue(null)!;
        var constraint=Enum.Parse(T("Entities.Cards.CardMultiplayerConstraint"),"SingleplayerOnly");
        var cardType=T("Models.CardModel");
        var rows=new List<object>();
        foreach(string seed in new[]{"0","1","2","42","ABC123"}) foreach(int act in new[]{0,1,2})
        foreach(string mode in new[]{"candy","silver_crucible","wing_charm"})
        foreach(string poolMode in new[]{"duplicates","unseen","no_power"})
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
            ctx.Values["get_Rng"]=rng;ctx.Values["get_Players"]=Typed(new[]{player},T("Entities.Players.Player"));ctx.Values["get_CurrentActIndex"]=act;ctx.Values["get_AscensionLevel"]=0;ctx.Values["get_CardMultiplayerConstraint"]=constraint;ctx.Values["get_CurrentMapPointHistoryEntry"]=null;
            var candy=Call(Get("Relic","Relics.LastingCandy"),"ToMutable");
            candy.GetType().GetProperty("Owner")!.SetValue(candy,player);candy.GetType().GetProperty("CombatsSeen")!.SetValue(candy,2);
            var relics=new List<object>{candy};
            if(mode!="candy") {var r=Call(Get("Relic",mode=="silver_crucible"?"Relics.SilverCrucible":"Relics.WingCharm"),"ToMutable");r.GetType().GetProperty("Owner")!.SetValue(r,player);relics.Add(r);}
            ctx.Values["IterateHookListeners"]=Typed(relics,T("Models.AbstractModel"));
            ctx.CreateOwned=(card,owner,clone)=>{var c=Call(card,clone?"ClonePreservingMutability":"ToMutable");if(!clone){c.GetType().GetProperty("Owner")!.SetValue(c,owner);Call(c,"AfterCreated");}return c;};
            var allowed=poolMode switch {"duplicates"=>new[]{"inflame","barricade","rupture"},"unseen"=>new[]{"inflame","metallicize","rupture","barricade"},_=>new[]{"anger","uppercut","pommel_strike"}};
            var pool=Items(Call(Get("CardPool","CardPools.IroncladCardPool"),"GetUnlockedCards",unlock,constraint)).Where(c=>(poolMode=="unseen" || allowed.Contains(Id(c))) && new[]{"Common","Uncommon","Rare"}.Contains(Prop(c,"Rarity").ToString())).ToArray();
            var options=Activator.CreateInstance(T("Runs.CardCreationOptions"),new object[]{Typed(pool,cardType),Enum.Parse(T("Runs.CardCreationSource"),"Encounter"),Enum.Parse(T("Runs.CardRarityOddsType"),"RegularEncounter")})!;
            Call(options,"WithFlags",Enum.Parse(T("Runs.CardCreationFlags"),"IsCardReward"));
            // Changing-odds logging requires Godot. Execute the unlogged base-odds
            // factory and then the actual encounter option hooks in isolation.
            var initial=Activator.CreateInstance(T("Runs.CardCreationOptions"),new object[]{Typed(pool,cardType),Enum.Parse(T("Runs.CardCreationSource"),"Other"),Enum.Parse(T("Runs.CardRarityOddsType"),"RegularEncounter")})!;
            Call(initial,"WithFlags",Enum.Parse(T("Runs.CardCreationFlags"),"NoModifyHooks, IsCardReward"));
            var generated=Items(T("Factories.CardFactory").GetMethod("CreateForReward",new[]{T("Entities.Players.Player"),typeof(int),T("Runs.CardCreationOptions")})!.Invoke(null,new[]{player,(object)3,initial})!);
            var results=(System.Collections.IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(T("Entities.Cards.CardCreationResult")))!;
            foreach(var result in generated)results.Add(result);
            object?[] hookArgs={context,player,results,options,null};
            T("Hooks.Hook").GetMethod("TryModifyCardRewardOptions")!.Invoke(null,hookArgs);
            generated=Items(results);
            var rewards=Prop(playerRng,"Rewards");var niche=Prop(rng,"Niche");
            var offers=generated.Select(x=> {var c=Prop(x,"Card");var e=Prop(c,"Enchantment");return new{id=Id(c),upgrade=Prop(c,"CurrentUpgradeLevel"),enchantment=e is null?null:Id(e)};}).ToArray();
            rows.Add(new{seed,act,mode,pool=pool.Select(Id),poolMode,offers,counter=Prop(rewards,"Counter"),suffix=Call(rewards,"NextDouble"),offset=(double)(float)Prop(Prop(playerOdds,"CardRarity"),"CurrentValue"),nicheCounter=Prop(niche,"Counter"),nicheSuffix=Call(niche,"NextDouble")});
        }
        Console.Write(JsonSerializer.Serialize(new{source="Actual base-odds CardFactory.CreateForReward followed by encounter LastingCandy/relic hooks in explicit solo A0 contexts; excludes changing-odds orchestration and run/profile/UI",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true}));
    }
}
