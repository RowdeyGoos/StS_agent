using System.Reflection;

// Real OnPlay/AttackCommand/FromCombatPile/CardPileCmd.Add on authored state.
// A test selector records the requested bounds and supplies physical cards.
// This does not execute the card-play wrapper, live selector UI or full combat end.
internal static class NeowsFuryOracle
{
    public static async Task<object> Run(Assembly asm, object player, object pcs,
        object combat, object target, object manager, object rng, string seed,
        string scenario, bool upgraded)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a){var t=o as Type??o.GetType();return t.GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o is Type?null:o,a)!;}
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        object Get(string method,string name)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+name)).Invoke(null,null)!;
        var loc=T("Localization.LocManager").GetProperty("Instance",flags)!.GetValue(null)!;
        var tables=(System.Collections.IDictionary)loc.GetType().GetField("_tables",flags)!.GetValue(loc)!;
        if(!tables.Contains("cards"))tables.Add("cards",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"cards",new Dictionary<string,string>{{"NEOWS_FURY.selectionScreenPrompt","Choose"}},null})!);
        ((System.Collections.IList)P(player,"Relics")).Clear();
        C(P(target,"Monster"),"SetUpForCombat");C(target,"SetMaxHpInternal",100m);C(target,"SetCurrentHpInternal",scenario=="lethal"?1m:100m);
        var physical=new List<object>();
        object Card(string name,string pile){var c=C(combat,"CreateCard",Get("Card","Cards."+name),player);physical.Add(c);C(P(pcs,pile),"AddInternal",c,-1,true);return c;}
        int count=scenario=="empty"?0:scenario=="singleton"?1:4;
        for(int i=0;i<count;i++)Card(i%2==0?"StrikeIronclad":"DefendIronclad","DiscardPile");
        int handCount=scenario=="one-space"?9:scenario=="full"?10:0;
        for(int i=0;i<handCount;i++)Card("DefendIronclad","Hand");
        var card=Card("NeowsFury","PlayPile");
        if(upgraded){C(card,"UpgradeInternal");C(card,"FinalizeUpgradeInternal");}
        string Label(object c)=>"card."+physical.IndexOf(c);
        string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(Label).ToArray();
        object State()=>new{hand=Pile("Hand"),discard=Pile("DiscardPile"),play=Pile("PlayPile"),enemyHp=P(target,"CurrentHp"),ending=P(manager,"IsEnding"),selectionCounter=P(P(rng,"CombatCardSelection"),"Counter")};
        var before=State();
        var selector=DispatchProxy.Create(T("TestSupport.ICardSelector"),typeof(NeowsFurySelector));
        var chooser=(NeowsFurySelector)selector;
        chooser.Zero=scenario=="zero"||(scenario=="singleton"&&!upgraded);
        using((IDisposable)C(T("Commands.CardSelectCmd"),"UseSelector",selector))
        {
            var play=Activator.CreateInstance(T("Entities.Cards.CardPlay"))!;
            foreach(var pair in new[]{("Card",card),("Target",target)})play.GetType().GetProperty(pair.Item1)!.SetValue(play,pair.Item2);
            var context=Activator.CreateInstance(T("GameActions.Multiplayer.ThrowingPlayerChoiceContext"))!;
            await ((Task)C(card,"OnPlay",context,play)).WaitAsync(TimeSpan.FromSeconds(3));
        }
        var selection=P(rng,"CombatCardSelection");
        return new{seed,scenario,upgraded,count,handCount,before,after=State(),
            calls=chooser.Calls,minimum=chooser.Minimum,maximum=chooser.Maximum,
            options=chooser.Options.Select(Label).ToArray(),selected=chooser.Selected.Select(Label).ToArray(),
            selectionCounter=P(selection,"Counter"),selectionSuffix=C(selection,"NextDouble")};
    }
}

public class NeowsFurySelector : DispatchProxy
{
    public bool Zero;
    public int Calls, Minimum, Maximum;
    public object[] Options=Array.Empty<object>(), Selected=Array.Empty<object>();
    protected override object? Invoke(MethodInfo? method,object?[]? args)
    {
        if(method!.Name!="GetSelectedCards")throw new InvalidOperationException("Unexpected selector call.");
        return GetType().GetMethod(nameof(Choose))!.MakeGenericMethod(method.ReturnType.GetGenericArguments()[0].GetGenericArguments()[0]).Invoke(this,args);
    }
    public Task<IEnumerable<T>> Choose<T>(IEnumerable<T> options,int minimum,int maximum)
    {
        Calls++;Minimum=minimum;Maximum=maximum;Options=options.Cast<object>().ToArray();
        var selected=Zero?Array.Empty<T>():options.Reverse().Take(maximum).ToArray();
        Selected=selected.Cast<object>().ToArray();
        return Task.FromResult<IEnumerable<T>>(selected);
    }
}
