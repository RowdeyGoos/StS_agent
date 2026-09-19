using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Actual draw/shuffle/power/relic commands. The test selector supplies the
// UI's choice signal and answer; no card screen, player action or run is launched.
internal static class DeathDrawOracle
{
    public static async Task<string> Run(Assembly asm, string digest)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        Array Typed(IEnumerable<object> values,Type t){var v=values.ToArray();var a=Array.CreateInstance(t,v.Length);Array.Copy(v,a,v.Length);return a;}
        void Require(bool b,string text){if(!b)throw new InvalidOperationException(text);}
        async Task Until(Func<bool> condition)
        {
            var deadline = System.Diagnostics.Stopwatch.StartNew();
            while(!condition())
            {
                Require(deadline.Elapsed < TimeSpan.FromSeconds(3), "Native continuation timed out.");
                await Task.Yield();
            }
        }
        var db=T("Models.ModelDb");
        foreach(var t in asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.AbstractModel"))&&t.Namespace is "MegaCrit.Sts2.Core.Models.Characters" or "MegaCrit.Sts2.Core.Models.Cards" or "MegaCrit.Sts2.Core.Models.CardPools" or "MegaCrit.Sts2.Core.Models.Monsters" or "MegaCrit.Sts2.Core.Models.Powers" or "MegaCrit.Sts2.Core.Models.Relics" or "MegaCrit.Sts2.Core.Models.Encounters"))db.GetMethod("Inject")!.Invoke(null,new object[]{t});
        object Get(string method,string name)=>db.GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+name)).Invoke(null,null)!;
        T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,true);
        T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);
        // Only presence of the selection prompt is required. No localization
        // initialization (which reads settings/overrides) occurs.
        var loc=RuntimeHelpers.GetUninitializedObject(T("Localization.LocManager"));
        var tables=(System.Collections.IDictionary)Activator.CreateInstance(typeof(Dictionary<,>).MakeGenericType(typeof(string),T("Localization.LocTable")))!;
        tables.Add("powers",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"powers",new Dictionary<string,string>{{"STRATAGEM_POWER.selectionScreenPrompt","Choose"}},null})!);
        tables.Add("combat_messages",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"combat_messages",new Dictionary<string,string>{{"NO_DRAW","No draw"},{"HAND_FULL","Hand full"}},null})!);
        F(loc,"_tables",tables);C(loc,"LoadLocFormatters");T("Localization.LocManager").GetProperty("CultureInfo",flags)!.SetValue(loc,System.Globalization.CultureInfo.InvariantCulture);T("Localization.LocManager").GetProperty("Instance",flags)!.SetValue(null,loc);
        var rows=new List<object>();
        foreach(string seed in new[]{"0","2","42"})foreach(int fillers in new[]{1,3})
        {
            var player=RuntimeHelpers.GetUninitializedObject(T("Entities.Players.Player"));
            F(player,"<Character>k__BackingField",Get("Character","Characters.Ironclad"));
            F(player,"<ExtraFields>k__BackingField",Activator.CreateInstance(T("Entities.Players.ExtraPlayerFields"))!);
            F(player,"<Deck>k__BackingField",Activator.CreateInstance(T("Entities.Cards.CardPile"),new[]{Enum.Parse(T("Entities.Cards.PileType"),"Deck")})!);
            foreach(string n in new[]{"_relics","_potionSlots"}){var f=player.GetType().GetField(n,flags)!;f.SetValue(player,Activator.CreateInstance(f.FieldType));}
            var ctx=DispatchProxy.Create(T("Runs.IRunState"),typeof(DeathDrawContext));var d=(DeathDrawContext)ctx;
            var rng=Activator.CreateInstance(T("Runs.RunRngSet"),new object[]{seed})!;
            d.Values["get_Rng"]=rng;d.Values["get_Players"]=Typed(new[]{player},player.GetType());d.Values["get_AscensionLevel"]=0;d.Values["get_CurrentMapPointHistoryEntry"]=null;
            d.Values["get_CurrentActIndex"]=0;d.Values["get_TotalFloor"]=2;
            d.Values["get_CurrentMapCoord"]=Activator.CreateInstance(T("Map.MapCoord"),new object[]{3,2})!;
            F(player,"_runState",ctx);
            var encounter=C(Get("Encounter","Encounters.VantomBoss"),"MutableClone");
            var combat=Activator.CreateInstance(T("Combat.CombatState"),new object?[]{encounter,ctx,null,null,null})!;
            var pc=Activator.CreateInstance(T("Entities.Creatures.Creature"),new object[]{player,80,80})!;
            F(player,"<Creature>k__BackingField",pc);C(combat,"AddPlayer",player);
            var manager=T("Combat.CombatManager").GetProperty("Instance")!.GetValue(null)!;
            F(manager,"_state",combat);F(manager,"<IsInProgress>k__BackingField",true);C(P(manager,"History"),"Clear");
            var pcs=Activator.CreateInstance(T("Entities.Players.PlayerCombatState"),new[]{player})!;
            F(player,"<PlayerCombatState>k__BackingField",pcs);F(player,"<IsActiveForHooks>k__BackingField",true);
            var monster=C(Get("Monster","Monsters.Vantom"),"ToMutable");
            var target=C(combat,"CreateCreature",monster,Enum.Parse(T("Combat.CombatSide"),"Enemy"),"enemy");C(combat,"AddCreature",target);
            d.Listeners=()=>C(combat,"IterateHookListeners");
            var abacus=C(Get("Relic","Relics.TheAbacus"),"ToMutable");abacus.GetType().GetProperty("Owner")!.SetValue(abacus,player);
            ((System.Collections.IList)P(player,"Relics")).Add(abacus);
            var power=C(Get("Power","Powers.StratagemPower"),"ToMutable",0);C(power,"ApplyInternal",pc,1m,true);
            var horn=C(Get("Relic","Relics.GremlinHorn"),"ToMutable");horn.GetType().GetProperty("Owner")!.SetValue(horn,player);
            var physical=new List<object>();
            for(int i=0;i<fillers;i++){var c=C(combat,"CreateCard",Get("Card","Cards.DefendIronclad"),player);physical.Add(c);C(P(pcs,"DiscardPile"),"AddInternal",c,-1,true);}
            string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(c=>"card."+physical.IndexOf(c)).ToArray();
            object State()=>new{hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),energy=P(pcs,"Energy"),block=P(pc,"Block")};
            var queue=Activator.CreateInstance(T("GameActions.Multiplayer.ActionQueueSet"),new object[]{Typed(new[]{player},player.GetType())})!;C(queue,"CombatStarted");
            var sync=RuntimeHelpers.GetUninitializedObject(T("GameActions.Multiplayer.ActionQueueSynchronizer"));F(sync,"_actionQueueSet",queue);F(sync,"_logger",queue.GetType().GetField("_logger",flags)!.GetValue(queue));
            foreach(var n in new[]{"_hookActions","_requestedActionsWaitingForPlayerTurn"}){var f=sync.GetType().GetField(n,flags)!;f.SetValue(sync,Activator.CreateInstance(f.FieldType));}
            var net=DispatchProxy.Create(T("Multiplayer.Game.INetGameService"),typeof(PausedHookNetProxy));((PausedHookNetProxy)net).Singleplayer=Enum.Parse(T("Multiplayer.Game.NetGameType"),"Singleplayer");F(sync,"_netService",net);
            var executor=RuntimeHelpers.GetUninitializedObject(T("GameActions.ActionExecutor"));
            var hook=Activator.CreateInstance(T("GameActions.Multiplayer.HookPlayerChoiceContext"),new[]{player,(object)0UL,Enum.Parse(T("Entities.Multiplayer.GameActionType"),"Combat")})!;
            C(hook,"MockDependenciesForTest",sync,queue,executor);
            var selector=DispatchProxy.Create(T("TestSupport.ICardSelector"),typeof(DeathDrawSelector));var chooser=(DeathDrawSelector)selector;
            chooser.Begun=()=> (Task)C(hook,"SignalPlayerChoiceBegun",Enum.ToObject(T("Entities.Multiplayer.PlayerChoiceOptions"),0));
            chooser.Ended=()=> (Task)C(hook,"SignalPlayerChoiceEnded");
            using var scope=(IDisposable)T("Commands.CardSelectCmd").GetMethod("UseSelector")!.Invoke(null,new[]{selector})!;
            var before=State();
            var work=(Task)C(horn,"AfterDeath",hook,target,false,0f);
            var completed=await ((Task<bool>)C(hook,"AssignTaskAndWaitForPauseOrCompletion",work)).WaitAsync(TimeSpan.FromSeconds(3));
            var paused=State();
            Require(completed == (fillers == 1), "Unexpected automatic/detached selection path.");
            if(!completed){
                var action=P(hook,"GameAction");Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Hook not queued.");
                F(executor,"<CurrentlyRunningAction>k__BackingField",action);await (Task)C(action,"Execute");
                await Until(()=>chooser.Visible);
                Require((int)P(pc,"Block")==0,"Abacus ran before the paused Stratagem finished.");
                chooser.Answer.SetResult();await Until(()=>P(action,"State").ToString()=="ReadyToResumeExecuting");
                await (Task)C(action,"Execute");await work;
            }
            Require((bool)P(queue,"IsEmpty"),"Hook did not finish.");
            Require(chooser.Calls == (fillers == 1 ? 0 : 1), "Unexpected selector count.");
            Require((int)P(pcs,"Energy") == 1 && (int)P(pc,"Block") == 6, "Horn/Abacus results missing.");
            Require(Pile("Hand").Length == (fillers == 1 ? 1 : 2), "Incorrect selected plus drawn hand.");
            var remaining = new[]{"Hand", "DrawPile", "DiscardPile"}.SelectMany(Pile).OrderBy(x=>x);
            Require(remaining.SequenceEqual(Enumerable.Range(0,fillers).Select(i=>"card."+i)), "Physical cards lost or duplicated.");
            var shuffle=P(rng,"Shuffle");
            rows.Add(new{seed,fillers,before,paused,after=State(),detached=!completed,selectorCalls=chooser.Calls,options=chooser.Options.Select(c=>"card."+physical.IndexOf(c)),shuffleCounter=P(shuffle,"Counter"),shuffleSuffix=C(shuffle,"NextDouble")});
        }
        return JsonSerializer.Serialize(new{source="Actual GremlinHorn.AfterDeath, CardPileCmd.Draw/Shuffle, StratagemPower, TheAbacus and native hook queue; test selector supplies UI signals/answer; explicit death callback invocation, no death dispatcher/attack/UI/run",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true});
    }
}
public class DeathDrawContext:DispatchProxy
{
    public Dictionary<string,object?> Values=new();public Func<object>? Listeners;
    protected override object? Invoke(MethodInfo? m,object?[]? args)=>m!.Name=="IterateHookListeners"?Listeners!():Values.TryGetValue(m.Name,out var v)?v:throw new InvalidOperationException("Unexpected native context: "+m.Name);
}
public class DeathDrawSelector:DispatchProxy
{
    public Func<Task> Begun=null!,Ended=null!;public bool Visible;public int Calls;public object[] Options=Array.Empty<object>();public TaskCompletionSource Answer=new();
    protected override object? Invoke(MethodInfo? m,object?[]? args)
    {
        if(m!.Name!="GetSelectedCards")throw new InvalidOperationException("Unexpected selector: "+m.Name);
        return GetType().GetMethod(nameof(Choose))!.MakeGenericMethod(m.ReturnType.GetGenericArguments()[0].GetGenericArguments()[0]).Invoke(this,args);
    }
    public async Task<IEnumerable<T>> Choose<T>(IEnumerable<T> options,int min,int max)
    {Calls++;Options=options.Cast<object>().ToArray();await Begun();Visible=true;await Answer.Task;await Ended();return options.Take(min).ToArray();}
}
