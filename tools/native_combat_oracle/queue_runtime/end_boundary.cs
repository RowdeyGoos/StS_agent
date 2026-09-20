using System.Reflection;

// Prepared combat, real native ending. All persistence goes to MockGodotFileIo.
internal static class EndBoundaryOracle
{
    public static async Task<object> Run(Assembly asm, object player, object pcs, object pc,
        object combat, object manager, object runManager, object queue, object sync,
        object executor, object rng, DeathDrawContext ctx, object attack, string seed,
        int hp, string scenario, string loadout)
    {
        const BindingFlags flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        object Get(string method,string name)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+name)).Invoke(null,null)!;
        void Require(bool value,string message){if(!value)throw new InvalidOperationException(message);}
        async Task Await(object task)=>await ((Task)task).WaitAsync(TimeSpan.FromSeconds(3));
        var store=Activator.CreateInstance(T("Saves.Test.MockGodotFileIo"),new object[]{"user://isolated-fixture"})!;
        var saves=Activator.CreateInstance(T("Saves.SaveManager"),new object[]{store,true})!;
        F(saves,"_currentProfileId",0);
        T("Saves.SaveManager").GetMethod("MockInstanceForTesting")!.Invoke(null,new[]{saves});
        var discovered=player.GetType().GetField("<DiscoveredEnemies>k__BackingField",flags)!;discovered.SetValue(player,Activator.CreateInstance(discovered.FieldType));
        F(executor,"_logger",queue.GetType().GetField("_logger",flags)!.GetValue(queue));
        var room=Activator.CreateInstance(T("Rooms.CombatRoom"),new[]{combat})!;
        ctx.Values["get_CurrentRoom"]=room;
        ctx.Values["get_Map"]=T("Map.NullActMap").GetProperty("Instance")!.GetValue(null)!;
        ctx.Values["get_Act"]=null;
        var hash=(int)T("Helpers.StringHelper").GetMethod("GetDeterministicHashCode")!.Invoke(null,new object[]{seed})!;
        var playerRng=Activator.CreateInstance(T("Random.PlayerRngSet"),new object[]{unchecked((uint)hash)})!;
        F(player,"<PlayerRng>k__BackingField",playerRng);
        F(player,"<PlayerOdds>k__BackingField",Activator.CreateInstance(T("Odds.PlayerOddsSet"),new[]{playerRng})!);
        F(player,"<UnlockState>k__BackingField",T("Unlocks.UnlockState").GetField("all")!.GetValue(null));
        runManager.GetType().GetProperty("AscensionManager")!.SetValue(runManager,Activator.CreateInstance(T("Entities.Ascension.AscensionManager"),new object[]{0}));
        ctx.Values["get_CardMultiplayerConstraint"]=Enum.Parse(T("Entities.Cards.CardMultiplayerConstraint"),"SingleplayerOnly");
        ctx.CreateOwned=(card,owner,clone)=>{var c=C(card,clone?"ClonePreservingMutability":"ToMutable");if(!clone){c.GetType().GetProperty("Owner")!.SetValue(c,owner);C(c,"AfterCreated");}return c;};
        C(pc,"SetCurrentHpInternal",(decimal)hp);
        C(pc,"GainBlockInternal",7m);
        object Relic(string name){var r=C(Get("Relic","Relics."+name),"ToMutable");r.GetType().GetProperty("Owner")!.SetValue(r,player);((System.Collections.IList)P(player,"Relics")).Add(r);return r;}
        Relic("BurningBlood");Relic("MeatOnTheBone");
        var candle=Relic("PumpkinCandle");candle.GetType().GetProperty("KindleCount")!.SetValue(candle,2);
        var guilty=C(Get("Card","Cards.Guilty"),"ToMutable");guilty.GetType().GetProperty("Owner")!.SetValue(guilty,player);guilty.GetType().GetProperty("CombatsSeen")!.SetValue(guilty,4);
        C(P(player,"Deck"),"AddInternal",guilty,-1,true);
        object? cheese=null, toy=null, rod=null;
        if(loadout=="wax_after")toy=Relic("ToyBox");
        if(loadout is "cheese" or "wax_before" or "wax_after")cheese=Relic("ChosenCheese");
        if(loadout=="wax_before")toy=Relic("ToyBox");
        if(toy!=null){toy.GetType().GetProperty("CombatsSeen")!.SetValue(toy,2);cheese!.GetType().GetProperty("IsWax")!.SetValue(cheese,true);}
        if(loadout=="fishing")
        {
            rod=Relic("FishingRod");rod.GetType().GetProperty("CombatsSeen")!.SetValue(rod,2);
            foreach(string name in new[]{"StrikeIronclad","DefendIronclad","Bash"})
            {var card=C(Get("Card","Cards."+name),"ToMutable");card.GetType().GetProperty("Owner")!.SetValue(card,player);C(P(player,"Deck"),"AddInternal",card,-1,true);}
        }
        // Persistent cards are already exhausted in this authored combat;
        // the lethal play and draw fillers are combat-only instances.
        foreach(var original in Items(P(P(player,"Deck"),"Cards")))
            C(P(pcs,"ExhaustPile"),"AddInternal",C(combat,"CloneCard",original),-1,true);
        var originalListeners=ctx.Listeners!;
        ctx.Listeners=()=>{var all=Items(P(P(player,"Deck"),"Cards")).Concat(Items(originalListeners())).ToArray();var typed=Array.CreateInstance(T("Models.AbstractModel"),all.Length);Array.Copy(all,typed,all.Length);return typed;};
        if(scenario=="victory")
            C(pc,"RemoveAllPowersInternalExcept",Array.CreateInstance(T("Models.PowerModel"),0));
        // Reapply damage/replay setup if the plain case removed Stratagem.
        if(scenario=="victory")
        {
            foreach(var (name,amount) in new[]{("StrengthPower",100m),("DuplicationPower",1m)})
                C(C(Get("Power","Powers."+name),"ToMutable",0),"ApplyInternal",pc,amount,true);
        }
        int won=0,ended=0;
        var events=new List<string>();
        // Reflection creates typed native event delegates without replacing methods.
        Action<object> onWon=_=>{won++;events.Add("won");};
        Action<object> onEnded=_=>{ended++;events.Add("ended");};
        var wonEvent=manager.GetType().GetEvent("CombatWon")!;
        var endEvent=manager.GetType().GetEvent("CombatEnded")!;
        var wonHandler=Delegate.CreateDelegate(wonEvent.EventHandlerType!,onWon.Target,onWon.Method);
        var endHandler=Delegate.CreateDelegate(endEvent.EventHandlerType!,onEnded.Target,onEnded.Method);
        wonEvent.AddEventHandler(manager,wonHandler);endEvent.AddEventHandler(manager,endHandler);
        try
        {
            C(sync,"SetCombatState",Enum.Parse(T("Entities.Multiplayer.ActionSynchronizerCombatState"),"PlayPhase"));
            if(scenario=="defeat")
                await Await(T("Commands.CreatureCmd").GetMethod("Kill",new[]{T("Entities.Creatures.Creature"),typeof(bool)})!.Invoke(null,new object[]{pc,false})!);
            else
            {
                var action=Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{attack,null})!;
                C(queue,"EnqueueWithoutSynchronizing",action);Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Lethal action unavailable.");
                F(executor,"<CurrentlyRunningAction>k__BackingField",action);
                await Await(C(action,"Execute"));Require(P(action,"State").ToString()=="Finished","Lethal action did not finish.");
            }
            var hooks=Items(sync.GetType().GetField("_hookActions",flags)!.GetValue(sync)!);
            int pending=hooks.Length;
            // Replay scheduling: enqueue detached hooks behind the finished
            // lethal action, without executing a selection before the win check.
            foreach(var hook in hooks)C(queue,"EnqueueWithoutSynchronizing",hook);
            Require(pending==(scenario=="pending"?1:0),"Unexpected pending death choices.");
            Require((bool)P(manager,"IsEnding"),"Wrong ending condition.");
            var check=(Task<bool>)C(manager,"CheckWinCondition");Require(await check.WaitAsync(TimeSpan.FromSeconds(3)),"Ending not processed.");
            Require(hooks.All(h=>P(h,"State").ToString()=="Canceled"),"End did not cancel queued hooks.");
            Require(C(queue,"GetReadyAction") is null,"Runnable combat work survived ending.");
            object[] rewards=Array.Empty<object>();
            if(scenario!="defeat")
            {
                var task=(Task)T("Commands.RewardsCmd").GetMethod("GenerateForRoomEnd")!.Invoke(null,new[]{player,room})!;
                await Await(task);var set=P(task,"Result");
                rewards=Items(P(set,"Rewards")).Select(r=>(object)(r.GetType().Name switch {
                    "GoldReward" => new {kind="gold",value=P(r,"Amount")},
                    "PotionReward" => new {kind="potion",value=P(P(P(r,"Potion"),"Id"),"Entry")},
                    "CardReward" => new {kind="cards",value=(object)Items(P(r,"Cards")).Select(c=>new{id=P(P(c,"Id"),"Entry"),upgrade=P(c,"CurrentUpgradeLevel")}).ToArray()},
                    _=>throw new InvalidOperationException("Unexpected reward "+r.GetType().Name)
                })).ToArray();
                // Generation must be idempotent at the room reward boundary.
                var count=P(P(playerRng,"Rewards"),"Counter");await Await(C(set,"GenerateWithoutOffering"));
                Require(Equals(count,P(P(playerRng,"Rewards"),"Counter")),"Rewards regenerated.");
            }
            var result=new{seed,scenario,loadout,rewards,rewardsCounter=P(P(playerRng,"Rewards"),"Counter"),rewardsSuffix=C(P(playerRng,"Rewards"),"NextDouble"),potionOdds=P(P(P(player,"PlayerOdds"),"PotionReward"),"CurrentValue"),cardOdds=P(P(P(player,"PlayerOdds"),"CardRarity"),"CurrentValue"),hpBefore=hp,maxHp=P(pc,"MaxHp"),cheeseMelted=cheese is null?false:P(cheese,"IsMelted"),toyCounter=toy is null?0:P(toy,"CombatsSeen"),rodCounter=rod is null?0:P(rod,"CombatsSeen"),deck=Items(P(P(player,"Deck"),"Cards")).Select(c=>new{id=P(P(c,"Id"),"Entry"),upgrade=P(c,"CurrentUpgradeLevel")}).ToArray(),nicheCounter=P(P(rng,"Niche"),"Counter"),nicheSuffix=C(P(rng,"Niche"),"NextDouble"),hpAfter=P(pc,"CurrentHp"),block=P(pc,"Block"),candle=P(candle,"KindleCount"),guiltyCount=P(guilty,"CombatsSeen"),deckCount=Items(P(P(player,"Deck"),"Cards")).Length,
                hookStates=hooks.Select(h=>P(h,"State").ToString()).ToArray(),pendingBefore=pending,pendingAfter=Items(sync.GetType().GetField("_hookActions",flags)!.GetValue(sync)!).Length,
                powers=Items(P(pc,"Powers")).Length,pileCards=new[]{"Hand","DrawPile","DiscardPile","ExhaustPile","PlayPile"}.Sum(n=>Items(P(P(pcs,n),"Cards")).Length),
                preFinished=P(room,"IsPreFinished"),inProgress=P(manager,"IsInProgress"),won,ended,events,goldProportion=P(room,"GoldProportion"),mockSaveCalls=Items(P(store,"Calls")).Length};
            Require(!(bool)P(manager,"IsInProgress"),"Combat stayed active.");
            return result;
        }
        finally {wonEvent.RemoveEventHandler(manager,wonHandler);endEvent.RemoveEventHandler(manager,endHandler);}
    }
}
