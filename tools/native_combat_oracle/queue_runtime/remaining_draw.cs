using System.Reflection;

internal static class RemainingDrawOracle
{
    public static async Task<object> Run(Assembly asm, object player, object pcs, object pc,
        object combat, object target, object manager, object queue, object executor, object choices,
        object rng, string seed, string subject, string scenario, bool variant)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        void Require(bool b,string text){if(!b)throw new InvalidOperationException(text);}
        object Get(string method,string name)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+name)).Invoke(null,null)!;
        object Relic(string name){var r=C(Get("Relic","Relics."+name),"ToMutable");r.GetType().GetProperty("Owner")!.SetValue(r,player);((System.Collections.IList)P(player,"Relics")).Add(r);return r;}
        object Power(string name,int amount){var p=C(Get("Power","Powers."+name),"ToMutable",0);C(p,"ApplyInternal",pc,(decimal)amount,true);return p;}
        var physical=new List<object>();var definitions=new List<string>();
        object Card(string name,string pile){var c=C(combat,"CreateCard",Get("Card","Cards."+name),player);physical.Add(c);definitions.Add(name);C(P(pcs,pile),"AddInternal",c,-1,true);return c;}
        string[] pool=scenario=="auto-all" ? new[]{"StrikeIronclad","DefendIronclad"} : scenario=="empty" ? Array.Empty<string>() : scenario=="singleton" ? new[]{"DefendIronclad"} : scenario=="innate" && subject=="ToastyMittens" ? new[]{"Backstab","DefendIronclad","Backstab"} : new[]{"StrikeIronclad","DefendIronclad","Anger","Whirlwind","Wound","Backstab"};
        bool direct=scenario=="auto-all" || scenario=="innate" && subject=="ToastyMittens";
        for(int i=0;i<pool.Length;i++)Card(pool[i],direct || scenario=="capacity" && i==0 ? "DrawPile" : "DiscardPile");
        if(scenario is "full" or "capacity")for(int i=0;i<(subject=="Scrape" ? 9 : 10);i++)Card("DefendIronclad","Hand");
        object? played=null;object? source=null;
        if(subject=="Scrape"){played=Card("Scrape","Hand");if(variant){C(played,"UpgradeInternal");C(played,"FinalizeUpgradeInternal");}}
        else if(subject=="ToastyMittens"){source=Relic(subject);if(variant)C(pcs,"IncrementTurnNumber");}
        else source=Power("ForegoneConclusionPower",variant ? 3 : 2);
        C(pcs,"GainEnergy",3m);
        if(scenario=="fiddle")Relic("Fiddle");
        if(scenario=="no-draw")Power("NoDrawPower",1);
        string Label(object card)=>"card."+physical.IndexOf(card);
        string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(Label).ToArray();
        int Amount(string name)=>Items(P(pc,"Powers")).Where(p=>p.GetType().Name==name).Select(p=>Convert.ToInt32(P(p,"Amount"))).FirstOrDefault();
        object State()=>new{hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),play=Pile("PlayPile"),exhaust=Pile("ExhaustPile"),energy=P(pcs,"Energy"),block=P(pc,"Block"),enemyHp=P(target,"CurrentHp"),strength=Amount("StrengthPower"),foregone=Amount("ForegoneConclusionPower")};
        var players=Array.CreateInstance(player.GetType(),1);players.SetValue(player,0);
        C(T("GameActions.Multiplayer.NetCombatCardDb").GetProperty("Instance")!.GetValue(null)!,"StartCombat",players);
        var before=State();object? action=null;Task? work=null;
        if(played!=null)action=Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{played,target})!;
        else
        {
            var hook=Activator.CreateInstance(T("GameActions.Multiplayer.HookPlayerChoiceContext"),new[]{source!,0UL,combat,Enum.Parse(T("Entities.Multiplayer.GameActionType"),"CombatPlayPhaseOnly")})!;
            work=(Task)C(source!,"BeforeHandDraw",player,hook,combat);
            bool completed=await ((Task<bool>)C(hook,"AssignTaskAndWaitForPauseOrCompletion",work)).WaitAsync(TimeSpan.FromSeconds(3));
            if(!completed)action=P(hook,"GameAction");
        }
        if(action!=null)
        {
            C(queue,"EnqueueWithoutSynchronizing",action);Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Draw work not ready.");
            F(executor,"<CurrentlyRunningAction>k__BackingField",action);
            await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
        }
        var checkpoint=State();var answers=new List<object>();var moved=new List<string>();uint choice=0;
        while(action!=null && P(action,"State").ToString()=="GatheringPlayerChoice")
        {
            Require(choice<4,"Unexpected repeated shuffle.");
            if(scenario=="drain" && choice==0)
            {
                // Controlled interference, not a claimed live executor schedule.
                foreach(var card in Items(P(P(pcs,"DrawPile"),"Cards")).Skip(1))
                {
                    moved.Add(Label(card));
                    var add=T("Commands.CardPileCmd").GetMethods().Single(m=>m.Name=="Add"&&m.GetParameters().Length==5&&m.GetParameters()[0].ParameterType==T("Models.CardModel")&&m.GetParameters()[1].ParameterType==T("Entities.Cards.PileType"));
                    await ((Task)add.Invoke(null,new object?[]{card,Enum.Parse(T("Entities.Cards.PileType"),"Discard"),Enum.Parse(T("Entities.Cards.CardPilePosition"),"Bottom"),null,true})!).WaitAsync(TimeSpan.FromSeconds(3));
                }
            }
            var available=Items(P(P(pcs,"DrawPile"),"Cards"));
            int count=subject=="ForegoneConclusion" && (choice>0 || scenario=="capacity") ? (variant ? 3 : 2) : 1;
            var selected=(variant ? available.Reverse() : available).Take(count).ToArray();
            answers.Add(new{options=available.Select(Label).ToArray(),selected=selected.Select(Label).ToArray(),state=State()});
            var typed=Array.CreateInstance(T("Models.CardModel"),selected.Length);Array.Copy(selected,typed,selected.Length);
            var result=T("GameActions.PlayerChoiceResult").GetMethod("FromMutableCombatCards")!.Invoke(null,new[]{typed})!;
            C(choices,"ReceiveReplayChoice",player,choice++,C(result,"ToNetData"));C(queue,"ResumeActionWithoutSynchronizing",P(action,"Id"));
            await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
        }
        if(work!=null)await work.WaitAsync(TimeSpan.FromSeconds(3));
        Require((action==null || P(action,"State").ToString()=="Finished") && (bool)P(queue,"IsEmpty"),"Draw work did not finish.");
        Require(Pile("PlayPile").Length==0,"Active card left in play.");
        Require(new[]{"Hand","DrawPile","DiscardPile","ExhaustPile"}.SelectMany(Pile).OrderBy(x=>x).SequenceEqual(physical.Select(Label).OrderBy(x=>x)),"Physical card ownership mismatch.");
        if(subject=="ForegoneConclusion")Require(Amount("ForegoneConclusionPower")==0,"Foregone was not removed.");
        if(subject=="ToastyMittens")Require(Amount("StrengthPower")==1,"Mittens did not grant strength.");
        var history=Items(P(P(manager,"History"),"Entries"));
        var draws=history.Where(e=>e.GetType().Name=="CardDrawnEntry").Select(e=>Label(P(e,"Card"))).ToArray();
        var plays=history.Where(e=>e.GetType().Name=="CardPlayFinishedEntry").Select(e=>Label(P(P(e,"CardPlay"),"Card"))).ToArray();
        object Stream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
        return new{seed,subject,scenario,variant,definitions,before,checkpoint,moved,answers,after=State(),draws,plays,
            shuffle=Stream("Shuffle"),targets=Stream("CombatTargets"),selection=Stream("CombatCardSelection"),niche=Stream("Niche"),ai=Stream("MonsterAi")};
    }
}
