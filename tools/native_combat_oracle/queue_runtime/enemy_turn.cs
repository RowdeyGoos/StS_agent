using System.Reflection;

// Enemy work is deliberately allowed to finish before replay supplies a choice.
// This exercises the real turn manager, not the live executor's frame schedule.
internal static class EnemyTurnOracle
{
    public static async Task<object> Run(Assembly asm, object player, object pcs, object pc,
        object combat, object manager, object runManager, object queue, object sync,
        object executor, object choices, object rng, List<object> physical,
        string seed, int fillers, bool answerLast, bool withTools)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        void Require(bool b,string text){if(!b)throw new InvalidOperationException(text);}
        string Label(object card)=>"card."+physical.IndexOf(card);
        string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(Label).ToArray();
        object State()=>new{hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),energy=P(pcs,"Energy"),block=P(pc,"Block"),hp=P(pc,"CurrentHp"),side=P(combat,"CurrentSide").ToString(),turn=P(pcs,"TurnNumber")};
        object[] Enemies()=>Items(P(combat,"Enemies")).Select(c=>(object)new{slot=P(c,"SlotName"),hp=P(c,"CurrentHp"),maxHp=P(c,"MaxHp"),move=P(P(P(c,"Monster"),"NextMove"),"Id")}).ToArray();
        combat.GetType().GetProperty("CurrentSide")!.SetValue(combat,Enum.Parse(T("Combat.CombatSide"),"Enemy"));
        C(sync,"SetCombatState",Enum.Parse(T("Entities.Multiplayer.ActionSynchronizerCombatState"),"NotPlayPhase"));
        F(executor,"_logger",queue.GetType().GetField("_logger",flags)!.GetValue(queue));
        var checksum=Activator.CreateInstance(T("Multiplayer.Game.ChecksumTracker"),new[]{P(runManager,"NetService"),P(player,"RunState")})!;
        checksum.GetType().GetProperty("IsEnabled")!.SetValue(checksum,false);
        runManager.GetType().GetProperty("ChecksumTracker",flags)!.SetValue(runManager,checksum);
        foreach(var creature in Items(P(combat,"Creatures")))C(creature,"OnSideSwitch");
        foreach(var enemy in Items(P(combat,"Enemies")))C(enemy,"PrepareForNextTurn",P(combat,"PlayerCreatures"),true);
        var before=State();var enemiesBefore=Enemies();
        await ((Task)C(manager,"ExecuteEnemyTurn",new object?[]{null})).WaitAsync(TimeSpan.FromSeconds(3));
        Require(!(bool)P(manager,"IsEnding"),"Unexpected combat end.");
        Require(P(combat,"CurrentSide").ToString()=="Player" && (int)P(pcs,"TurnNumber")==2,"Next player turn did not begin.");
        var pending=Items(sync.GetType().GetField("_hookActions",flags)!.GetValue(sync)!);
        Require(pending.Length==(fillers==1 ? 0 : withTools ? 2 : 1),"Unexpected deferred hook count.");
        var checkpoint=State();var enemiesCheckpoint=Enemies();
        var answers=new List<object>();
        foreach(var action in pending)C(queue,"EnqueueWithoutSynchronizing",action);
        uint choiceId=0;
        foreach(var action in pending)
        {
            Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Hook not ready.");
            F(executor,"<CurrentlyRunningAction>k__BackingField",action);
            await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
            Require(P(action,"State").ToString()=="GatheringPlayerChoice","Selector did not pause.");
            var pile=choiceId==0 ? "DrawPile" : "Hand";
            var available=Items(P(P(pcs,pile),"Cards"));
            var selected=available.Length==0 ? Array.Empty<object>() : new[]{answerLast ? available[^1] : available[0]};
            var cards=Array.CreateInstance(T("Models.CardModel"),selected.Length);Array.Copy(selected,cards,selected.Length);
            answers.Add(new{pile,options=available.Select(Label).ToArray(),selected=selected.Select(Label).ToArray(),state=State()});
            var result=T("GameActions.PlayerChoiceResult").GetMethod("FromMutableCombatCards")!.Invoke(null,new[]{cards})!;
            C(choices,"ReceiveReplayChoice",player,choiceId++,C(result,"ToNetData"));
            C(queue,"ResumeActionWithoutSynchronizing",P(action,"Id"));
            await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
            Require(P(action,"State").ToString()=="Finished","Horn did not finish.");
        }
        Require((bool)P(queue,"IsEmpty"),"Queue not empty.");
        Require(new[]{"Hand","DrawPile","DiscardPile"}.SelectMany(Pile).OrderBy(x=>x).SequenceEqual(Enumerable.Range(0,fillers).Select(i=>"card."+i)),"Physical cards lost or duplicated.");
        var history=Items(P(P(manager,"History"),"Entries"));
        var hits=history.Where(e=>e.GetType().Name=="DamageReceivedEntry").Select(e=>new{slot=(bool)P(P(e,"Receiver"),"IsPlayer") ? "player" : P(P(e,"Receiver"),"SlotName"),damage=P(P(e,"Result"),"UnblockedDamage"),blocked=P(P(e,"Result"),"BlockedDamage")}).ToArray();
        Require(history.Count(e=>e.GetType().Name=="MonsterPerformedMoveEntry")==2,"Both monsters did not finish their moves.");
        object Stream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
        ((IDisposable)checksum).Dispose();
        return new{seed,fillers,answerLast,withTools,before,enemiesBefore,checkpoint,enemiesCheckpoint,answers,after=State(),enemiesAfter=Enemies(),hits,
            shuffle=Stream("Shuffle"),targets=Stream("CombatTargets"),niche=Stream("Niche"),ai=Stream("MonsterAi")};
    }
}
