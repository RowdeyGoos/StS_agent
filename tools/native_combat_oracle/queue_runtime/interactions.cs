using System.Reflection;

internal static class InteractionOracle
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
        C(target,"SetMaxHpInternal",500m);C(target,"SetCurrentHpInternal",500m);
        object? played=null;object? exhausted=null;
        object source=Items(P(player,"Relics"))[0];
        if(subject=="Scrape")
        {
            var pool=scenario=="sly" ? new[]{"Reflex","Tactician","StrikeIronclad","DefendIronclad","DefendIronclad","Anger"} : new[]{"StrikeIronclad","DefendIronclad","StrikeIronclad","DefendIronclad","DefendIronclad","Anger"};
            foreach(var n in pool)Card(n,scenario=="direct" ? "DrawPile" : "DiscardPile");
            Power("HellraiserPower",1);played=Card("Scrape","Hand");
            if(variant){C(played,"UpgradeInternal");C(played,"FinalizeUpgradeInternal");}
        }
        else if(subject=="DrumOfBattle")
        {
            foreach(var n in new[]{"StrikeIronclad","DefendIronclad","Anger"})Card(n,"DiscardPile");
            exhausted=Card("DrumOfBattle","Hand");
            if(variant){C(exhausted,"UpgradeInternal");C(exhausted,"FinalizeUpgradeInternal");}
            foreach(var n in variant ? new[]{"FeelNoPainPower","DarkEmbracePower"} : new[]{"DarkEmbracePower","FeelNoPainPower"})Power(n,n=="FeelNoPainPower" ? 3 : 1);
            if(scenario=="duplication")Power("DuplicationPower",1);
            if(scenario=="burst")Power("BurstPower",1);
            if(scenario=="axe")Relic("ThrowingAxe");
            if(scenario=="ashes")Relic("CharonsAshes");
        }
        else
        {
            foreach(var n in (scenario=="slither" ? new[]{"KinglyKick","KinglyPunch","DefendIronclad","StrikeIronclad","Anger","Whirlwind"} : scenario=="binding" ? new[]{"Dazed","DefendIronclad","StrikeIronclad","Anger","DefendIronclad","Anger"} : new[]{"Void","Wound","StrikeIronclad","Whirlwind","DefendIronclad","Anger"}))Card(n,physical.Count==0 ? "DrawPile" : "DiscardPile");
            if(scenario=="slither")foreach(var card in physical.Take(2))
            {
                var enchantment=C(Get("Enchantment","Enchantments.Slither"),"ToMutable");
                T("Commands.CardCmd").GetMethods().Single(m=>m.Name=="Enchant"&&!m.IsGenericMethodDefinition).Invoke(null,new[]{enchantment,card,1m});
            }
            string[] powers=scenario=="removed" ? new[]{"PagestormPower","CorrosiveWavePower"} : scenario=="slither" ? new[]{"ConfusedPower"} : scenario=="binding" ? new[]{"ChainsOfBindingPower","PagestormPower"} : scenario=="iteration" ? new[]{"PagestormPower","IterationPower"} : scenario=="automation" ? new[]{"PagestormPower","AutomationPower"} : new[]{"PagestormPower","ConfusedPower","SpeedsterPower","CorrosiveWavePower"};
            foreach(var n in variant ? powers.Reverse() : powers)Power(n,scenario=="binding" ? 3 : 1);
        }
        C(pcs,"GainEnergy",3m);
        string Label(object card)=>"card."+physical.IndexOf(card);
        string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(Label).ToArray();
        int Amount(string name)=>Items(P(pc,"Powers")).Where(p=>p.GetType().Name==name).Select(p=>Convert.ToInt32(P(p,"Amount"))).FirstOrDefault();
        object State()=>new{hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),play=Pile("PlayPile"),exhaust=Pile("ExhaustPile"),energy=P(pcs,"Energy"),block=P(pc,"Block"),enemyHp=P(target,"CurrentHp"),poison=Items(P(target,"Powers")).Where(x=>x.GetType().Name=="PoisonPower").Select(x=>Convert.ToInt32(P(x,"Amount"))).FirstOrDefault(),duplication=Amount("DuplicationPower"),burst=Amount("BurstPower"),automation=Items(P(pc,"Powers")).Where(x=>x.GetType().Name=="AutomationPower").Select(x=>P(x,"DisplayAmount")).FirstOrDefault(),bound=physical.Select(c=>P(c,"Affliction")?.GetType().Name=="Bound").ToArray(),costs=physical.Select(c=>C(P(c,"EnergyCost"),"GetWithModifiers",Enum.Parse(T("Entities.Cards.CostModifiers"),"Local"))).ToArray()};
        var players=Array.CreateInstance(player.GetType(),1);players.SetValue(player,0);
        C(T("GameActions.Multiplayer.NetCombatCardDb").GetProperty("Instance")!.GetValue(null)!,"StartCombat",players);
        var before=State();object? action=null;Task? work=null;
        if(played!=null)action=Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{played,target})!;
        else
        {
            var hook=Activator.CreateInstance(T("GameActions.Multiplayer.HookPlayerChoiceContext"),new[]{source,0UL,combat,Enum.Parse(T("Entities.Multiplayer.GameActionType"),"CombatPlayPhaseOnly")})!;
            work=exhausted!=null
                ? (Task)T("Commands.CardCmd").GetMethod("Exhaust")!.Invoke(null,new object?[]{hook,exhausted,false,true})!
                : (Task)T("Commands.CardPileCmd").GetMethods().Single(m=>m.Name=="Draw"&&m.GetParameters().Length==4).Invoke(null,new object?[]{hook,3m,player,false})!;
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
            if(scenario=="removed" && choice==0)
            {
                // Controlled lifetime probe: remove a captured native listener.
                var removed=Items(P(pc,"Powers")).Single(x=>x.GetType().Name=="CorrosiveWavePower");
                await ((Task)T("Commands.PowerCmd").GetMethods().Single(m=>m.Name=="Remove"&&!m.IsGenericMethodDefinition).Invoke(null,new[]{removed})!);
            }
            var available=Items(P(P(pcs,"DrawPile"),"Cards"));
            int count=1;
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
        var history=Items(P(P(manager,"History"),"Entries"));
        var draws=history.Where(e=>e.GetType().Name=="CardDrawnEntry").Select(e=>Label(P(e,"Card"))).ToArray();
        var plays=history.Where(e=>e.GetType().Name=="CardPlayFinishedEntry").Select(e=>Label(P(P(e,"CardPlay"),"Card"))).ToArray();
        object Stream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
        return new{seed,subject,scenario,variant,definitions,before,checkpoint,moved,answers,after=State(),draws,plays,discards=history.Where(e=>e.GetType().Name=="CardDiscardedEntry").Select(e=>Label(P(e,"Card"))).ToArray(),
            shuffle=Stream("Shuffle"),targets=Stream("CombatTargets"),energyCosts=Stream("CombatEnergyCosts"),selection=Stream("CombatCardSelection"),niche=Stream("Niche"),ai=Stream("MonsterAi")};
    }
}
