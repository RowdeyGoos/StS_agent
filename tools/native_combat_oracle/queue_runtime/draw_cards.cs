using System.Reflection;

internal static class DrawCardsOracle
{
    public static async Task<object> Run(Assembly asm, object player, object pcs, object pc,
        object combat, object target, object manager, object queue, object executor, object choices,
        object rng, string seed, string cardName, string scenario, bool upgraded)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        void Require(bool b,string text){if(!b)throw new InvalidOperationException(text);}
        object Get(string method,string name)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+name)).Invoke(null,null)!;
        var physical=new List<object>();
        object Card(string name,string pile){var c=C(combat,"CreateCard",Get("Card","Cards."+name),player);physical.Add(c);C(P(pcs,pile),"AddInternal",c,-1,true);return c;}
        int fillers=scenario=="empty" ? 0 : scenario=="singleton" ? 1 : 3;
        for(int i=0;i<fillers;i++)Card(scenario=="attacks" || fillers==3 && i!=1 ? "StrikeIronclad" : "DefendIronclad","DiscardPile");
        if(scenario=="full")for(int i=0;i<9;i++)Card("DefendIronclad","Hand");
        var played=Card(cardName,"Hand");
        if(upgraded){C(played,"UpgradeInternal");C(played,"FinalizeUpgradeInternal");}
        C(pcs,"GainEnergy",3m);
        if(scenario=="fiddle")
        {
            var relic=C(Get("Relic","Relics.Fiddle"),"ToMutable");relic.GetType().GetProperty("Owner")!.SetValue(relic,player);
            ((System.Collections.IList)P(player,"Relics")).Add(relic);
        }
        if(scenario=="no-draw"){var power=C(Get("Power","Powers.NoDrawPower"),"ToMutable",0);C(power,"ApplyInternal",pc,1m,true);}
        string Label(object card)=>"card."+physical.IndexOf(card);
        string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(Label).ToArray();
        object State()=>new{hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),play=Pile("PlayPile"),exhaust=Pile("ExhaustPile"),energy=P(pcs,"Energy"),block=P(pc,"Block"),enemyHp=P(target,"CurrentHp")};
        var players=Array.CreateInstance(player.GetType(),1);players.SetValue(player,0);
        C(T("GameActions.Multiplayer.NetCombatCardDb").GetProperty("Instance")!.GetValue(null)!,"StartCombat",players);
        var before=State();
        var action=Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{played,cardName=="Pillage" ? target : null})!;
        C(queue,"EnqueueWithoutSynchronizing",action);Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Draw card not ready.");
        F(executor,"<CurrentlyRunningAction>k__BackingField",action);
        await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
        var checkpoint=State();var answers=new List<object>();var moved=new List<string>();
        uint choice=0;
        while(P(action,"State").ToString()=="GatheringPlayerChoice")
        {
            Require(choice<3,"Unexpected repeated shuffle.");
            if(scenario=="drain" && choice==0)
            {
                // Controlled interference, not a claimed live executor schedule.
                // Use actual native pile commands; leave one valid replay choice.
                foreach(var card in Items(P(P(pcs,"DrawPile"),"Cards")).Skip(1))
                {
                    moved.Add(Label(card));
                    var add=T("Commands.CardPileCmd").GetMethods().Single(m=>m.Name=="Add"&&m.GetParameters().Length==5&&m.GetParameters()[0].ParameterType==T("Models.CardModel")&&m.GetParameters()[1].ParameterType==T("Entities.Cards.PileType"));
                    await ((Task)add.Invoke(null,new object?[]{card,Enum.Parse(T("Entities.Cards.PileType"),"Discard"),Enum.Parse(T("Entities.Cards.CardPilePosition"),"Bottom"),null,true})!).WaitAsync(TimeSpan.FromSeconds(3));
                }
            }
            var available=Items(P(P(pcs,"DrawPile"),"Cards"));Require(available.Length>0,"Missing replay choice.");
            var selected=upgraded ? available[^1] : available[0];
            answers.Add(new{options=available.Select(Label).ToArray(),selected=Label(selected),state=State()});
            var result=T("GameActions.PlayerChoiceResult").GetMethod("FromMutableCombatCard")!.Invoke(null,new[]{selected})!;
            C(choices,"ReceiveReplayChoice",player,choice++,C(result,"ToNetData"));C(queue,"ResumeActionWithoutSynchronizing",P(action,"Id"));
            await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
        }
        Require(P(action,"State").ToString()=="Finished" && (bool)P(queue,"IsEmpty"),"Draw card did not finish cleanly.");
        Require(Pile("PlayPile").Length==0 && Pile("DiscardPile").Contains(Label(played)),"Draw card was not discarded.");
        Require(new[]{"Hand","DrawPile","DiscardPile","ExhaustPile"}.SelectMany(Pile).OrderBy(x=>x).SequenceEqual(physical.Select(Label).OrderBy(x=>x)),"Physical card ownership mismatch.");
        var history=Items(P(P(manager,"History"),"Entries"));
        var draws=history.Where(e=>e.GetType().Name=="CardDrawnEntry").Select(e=>Label(P(e,"Card"))).ToArray();
        var plays=history.Where(e=>e.GetType().Name=="CardPlayFinishedEntry").Select(e=>Label(P(P(e,"CardPlay"),"Card"))).ToArray();
        Require(plays.SequenceEqual(new[]{Label(played)}),"Wrong played-card history.");
        if(scenario is "empty" or "singleton" or "full" or "fiddle" or "no-draw" or "drain")Require(draws.Length==0,"Prevented/empty draw returned a card.");
        object Stream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
        return new{seed,cardName,scenario,upgraded,fillers,before,checkpoint,moved,answers,after=State(),draws,plays,
            shuffle=Stream("Shuffle"),targets=Stream("CombatTargets"),selection=Stream("CombatCardSelection"),niche=Stream("Niche"),ai=Stream("MonsterAi")};
    }
}
