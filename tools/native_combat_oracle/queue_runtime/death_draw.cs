using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Shared explicit combat setup for callbacks, card plays and enemy turns.
// Callback mode uses a test selector; attack mode delivers native replay choices.
// No mode starts a run, live card screen or executor frame loop.
internal static class DeathDrawOracle
{
    public static async Task<string> Run(Assembly asm, string digest, bool attackMode = false, bool multipleDeaths = false, bool enemyTurn = false, bool autoplay = false, bool flak = false, bool drawCards = false)
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
        if(drawCards)tables.Add("monsters",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"monsters",new Dictionary<string,string>{{"CHOMPER.name","Chomper"}},null})!);
        if(enemyTurn)tables.Add("card_selection",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"card_selection",new Dictionary<string,string>{{"TO_DISCARD","Discard"}},null})!);
        var rows=new List<object>();
        foreach(string seed in new[]{"0","2","42"})foreach(int fillers in drawCards ? new[]{0} : flak ? new[]{6} : enemyTurn ? new[]{1,3,8} : multipleDeaths ? new[]{3,8} : new[]{1,3})
        foreach(bool upgraded in attackMode ? new[]{false,true} : new[]{false})
        foreach(bool terminal in multipleDeaths ? new[]{false,true} : new[]{false})
        foreach(bool withTools in enemyTurn ? new[]{false,true} : new[]{false})
        foreach(int autoplayCount in flak ? new[]{3} : autoplay ? new[]{1,3} : new[]{0})
        foreach(bool drawFirst in (autoplay && !flak) ? new[]{false,true} : new[]{false})
        foreach(bool withStratagem in (autoplay && !flak) ? new[]{false,true} : new[]{true})
        foreach(bool darkEmbrace in flak ? new[]{false,true} : new[]{false})
        foreach(string drawCard in drawCards ? new[]{"Pillage","EscapePlan"} : new[]{""})
        foreach(string drawCase in drawCards ? new[]{"mixed","singleton","attacks","full","empty","fiddle","no-draw","drain"} : new[]{""})
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
            var monster=C(Get("Monster",(enemyTurn || autoplay || drawCards) ? "Monsters.Chomper" : attackMode ? "Monsters.PhrogParasite" : "Monsters.Vantom"),"ToMutable");
            var target=C(combat,"CreateCreature",monster,Enum.Parse(T("Combat.CombatSide"),"Enemy"),"enemy");C(combat,"AddCreature",target);
            if (attackMode && !autoplay && !drawCards)
            {
                C(monster,"SetUpForCombat");C(target,"SetCurrentHpInternal",1m);
                if(!enemyTurn){var infested=C(Get("Power","Powers.InfestedPower"),"ToMutable",0);C(infested,"ApplyInternal",target,1m,true);}
                else
                {
                    var second=C(Get("Monster","Monsters.Chomper"),"ToMutable");
                    var survivor=C(combat,"CreateCreature",second,Enum.Parse(T("Combat.CombatSide"),"Enemy"),"second");
                    C(combat,"AddCreature",survivor);C(second,"SetUpForCombat");
                    var thorns=C(Get("Power","Powers.ThornsPower"),"ToMutable",0);C(thorns,"ApplyInternal",pc,1m,true);
                    F(player,"<MaxEnergy>k__BackingField",3);
                    if(withTools){var tools=C(Get("Power","Powers.ToolsOfTheTradePower"),"ToMutable",0);C(tools,"ApplyInternal",pc,1m,true);}
                }
            }
            d.Listeners=()=>C(combat,"IterateHookListeners");
            var abacus=C(Get("Relic","Relics.TheAbacus"),"ToMutable");abacus.GetType().GetProperty("Owner")!.SetValue(abacus,player);
            ((System.Collections.IList)P(player,"Relics")).Add(abacus);
            if(withStratagem){var power=C(Get("Power","Powers.StratagemPower"),"ToMutable",0);C(power,"ApplyInternal",pc,1m,true);}
            if(multipleDeaths)
            {
                var strength=C(Get("Power","Powers.StrengthPower"),"ToMutable",0);C(strength,"ApplyInternal",pc,100m,true);
                if(terminal){var duplication=C(Get("Power","Powers.DuplicationPower"),"ToMutable",0);C(duplication,"ApplyInternal",pc,1m,true);}
            }
            var horn=C(Get("Relic","Relics.GremlinHorn"),"ToMutable");horn.GetType().GetProperty("Owner")!.SetValue(horn,player);
            if (attackMode && !autoplay && !drawCards) ((System.Collections.IList)P(player,"Relics")).Add(horn);
            var physical=new List<object>();
            for(int i=0;i<fillers;i++){var c=C(combat,"CreateCard",Get("Card",flak && i<3 ? new[]{"Cards.FlakCannon","Cards.Slimed","Cards.Wound"}[i] : "Cards.DefendIronclad"),player);physical.Add(c);C(P(pcs,"DiscardPile"),"AddInternal",c,-1,true);}
            object? attackCard=null;
            if (attackMode && !enemyTurn && !autoplay && !drawCards)
            {
                attackCard=C(combat,"CreateCard",Get("Card","Cards.SwordBoomerang"),player);
                if(upgraded){C(attackCard,"UpgradeInternal");C(attackCard,"FinalizeUpgradeInternal");}
                physical.Add(attackCard);C(P(pcs,"Hand"),"AddInternal",attackCard,-1,true);
                C(pcs,"GainEnergy",1m);
            }
            string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(c=>"card."+physical.IndexOf(c)).ToArray();
            object State()=>new{hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),energy=P(pcs,"Energy"),block=P(pc,"Block")};
            var queue=Activator.CreateInstance(T("GameActions.Multiplayer.ActionQueueSet"),new object[]{Typed(new[]{player},player.GetType())})!;C(queue,"CombatStarted");
            var sync=RuntimeHelpers.GetUninitializedObject(T("GameActions.Multiplayer.ActionQueueSynchronizer"));F(sync,"_actionQueueSet",queue);F(sync,"_logger",queue.GetType().GetField("_logger",flags)!.GetValue(queue));
            foreach(var n in new[]{"_hookActions","_requestedActionsWaitingForPlayerTurn"}){var f=sync.GetType().GetField(n,flags)!;f.SetValue(sync,Activator.CreateInstance(f.FieldType));}
            var net=DispatchProxy.Create(T("Multiplayer.Game.INetGameService"),typeof(PausedHookNetProxy));((PausedHookNetProxy)net).Singleplayer=Enum.Parse(T("Multiplayer.Game.NetGameType"),"Singleplayer");F(sync,"_netService",net);
            var executor=RuntimeHelpers.GetUninitializedObject(T("GameActions.ActionExecutor"));
            if (attackMode)
            {
                // Native replay delivers the same enqueue/choice/resume events as
                // NMultiplayerTest. No ICardSelector, UI or method patches are used.
                var replay=Activator.CreateInstance(T("Multiplayer.NetReplayGameService"),new object[]{0UL})!;
                F(sync,"_netService",replay);
                var choices=Activator.CreateInstance(T("GameActions.Multiplayer.PlayerChoiceSynchronizer"),new[]{replay,ctx})!;
                d.Values["GetPlayerSlotIndex"]=0;d.Values["GetPlayer"]=player;
                var runManager=T("Runs.RunManager").GetProperty("Instance")!.GetValue(null)!;
                foreach(var pair in new[]{("NetService",replay),("ActionQueueSet",queue),("ActionQueueSynchronizer",sync),("ActionExecutor",executor),("PlayerChoiceSynchronizer",choices)})
                    runManager.GetType().GetProperty(pair.Item1,flags)!.SetValue(runManager,pair.Item2);
                var cardDb=T("GameActions.Multiplayer.NetCombatCardDb").GetProperty("Instance")!.GetValue(null)!;
                if(!drawCards)C(cardDb,"StartCombat",Typed(new[]{player},player.GetType()));
                object[] Enemies()=>Items(P(combat,"Enemies")).Select(c=>(object)new {
                    type=P(c,"Monster").GetType().Name,slot=P(c,"SlotName"),hp=P(c,"CurrentHp"),maxHp=P(c,"MaxHp"),block=P(c,"Block"),
                    powers=Items(P(c,"Powers")).Select(power=>new{id=P(P(power,"Id"),"Entry").ToString()!.ToLowerInvariant(),amount=P(power,"Amount")}).ToArray()
                }).ToArray();
                if(drawCards)
                {
                    rows.Add(await DrawCardsOracle.Run(asm, player, pcs, pc, combat, target, manager, queue, executor, choices, rng, seed, drawCard, drawCase, upgraded));
                    C(cardDb,"OnCombatEnded",new object?[]{null});((IDisposable)choices).Dispose();
                    continue;
                }
                if(autoplay)
                {
                    var mayhem=C(Get("Power","Powers.MayhemPower"),"ToMutable",0);C(mayhem,"ApplyInternal",pc,(decimal)autoplayCount,true);
                    if(darkEmbrace){var de=C(Get("Power","Powers.DarkEmbracePower"),"ToMutable",0);C(de,"ApplyInternal",pc,1m,true);}
                    rows.Add(await AutoplayOracle.Run(asm, player, pcs, pc, manager, queue, sync, executor, choices, rng, physical, mayhem, seed, fillers, autoplayCount, drawFirst, withStratagem, upgraded, flak, darkEmbrace));
                    C(cardDb,"OnCombatEnded",new object?[]{null});((IDisposable)choices).Dispose();
                    continue;
                }
                if(enemyTurn)
                {
                    rows.Add(await EnemyTurnOracle.Run(asm, player, pcs, pc, combat, manager, runManager, queue, sync, executor, choices, rng, physical, seed, fillers, upgraded, withTools));
                    C(cardDb,"OnCombatEnded",new object?[]{null});((IDisposable)choices).Dispose();
                    continue;
                }
                if(multipleDeaths)C(sync,"SetCombatState",Enum.Parse(T("Entities.Multiplayer.ActionSynchronizerCombatState"),"PlayPhase"));
                object MultipleState()=>new{hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),play=Pile("PlayPile"),energy=P(pcs,"Energy"),block=P(pc,"Block")};
                var multipleBefore=MultipleState();
                var attackBefore=State();var enemiesBefore=Enemies();
                var play=Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{attackCard,null})!;
                C(queue,"EnqueueWithoutSynchronizing",play);
                Require(ReferenceEquals(C(queue,"GetReadyAction"),play),"Card play not ready.");
                F(executor,"<CurrentlyRunningAction>k__BackingField",play);
                await ((Task)C(play,"Execute")).WaitAsync(TimeSpan.FromSeconds(5));
                Require(P(play,"State").ToString()=="Finished","Outer card play did not finish.");
                if(multipleDeaths)
                {
                    // Check the native terminal guard before delivering the same
                    // cancellation step EndCombatInternal invokes. Do not run its
                    // separate reward/profile/room cleanup lifecycle.
                    Require((bool)P(manager,"IsEnding")==terminal,"Wrong native terminal boundary.");
                    int deaths=terminal ? 5 : upgraded ? 4 : 3;
                    var pending=Items(sync.GetType().GetField("_hookActions",flags)!.GetValue(sync)!);
                    Require(pending.Length==1,"Expected one paused Horn while later kills draw automatically.");
                    Require(Items(P(combat,"Enemies")).Length==5-deaths,"Wrong surviving child count.");
                    Require((int)P(pcs,"Energy")== (terminal ? 4 : deaths),"Final death must not grant energy.");
                    Require((int)P(pc,"Block")==0,"Abacus ran before paused Stratagem.");
                    Require(Pile("Hand").Length==(terminal ? 3 : deaths-1),"Later Horn draws did not finish before choice activation.");
                    Require(Pile(terminal ? "PlayPile" : "DiscardPile").Contains("card."+fillers),"Unexpected outer card pile.");
                    var checkpoint=MultipleState();var surviving=Enemies();
                    var answers=new List<object>();
                    object MultiStream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
                    string Counters()=>string.Join(",",new[]{"Shuffle","CombatTargets","Niche","MonsterAi"}.Select(n=>P(P(rng,n),"Counter")));
                    foreach(var action in pending) C(queue,"EnqueueWithoutSynchronizing",action);
                    var beforeCancelCounters=Counters();
                    if(terminal)
                    {
                        C(sync,"SetCombatState",Enum.Parse(T("Entities.Multiplayer.ActionSynchronizerCombatState"),"NotInCombat"));
                        Require(pending.All(a=>P(a,"State").ToString()=="Canceled"),"Terminal hooks were not canceled.");
                        Require(pending.All(a=>!((Task)P(P(a,"ChoiceContext"),"Task")).IsCompleted),"Canceled native coroutine unexpectedly resumed.");
                        Require(JsonSerializer.Serialize(checkpoint)==JsonSerializer.Serialize(MultipleState()),"Cancellation changed resources or piles.");
                        Require(beforeCancelCounters==Counters(),"Cancellation consumed RNG.");
                    }
                    else
                    {
                        var action=pending[0];
                        Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"First detached Horn not ready.");
                        F(executor,"<CurrentlyRunningAction>k__BackingField",action);
                        await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
                        int choice=0;
                        while(P(action,"State").ToString()=="GatheringPlayerChoice")
                        {
                            Require(choice<3,"Unexpected repeated-choice loop.");
                            var available=Items(P(P(pcs,"DrawPile"),"Cards"));
                            // Replay supplies an empty answer for an empty live
                            // pile, matching the UI's source-backed empty result.
                            var selectedCards=available.Length==0 ? Array.Empty<object>() : new[]{upgraded ? available[^1] : available[0]};
                            answers.Add(new{options=available.Select(c=>"card."+physical.IndexOf(c)).ToArray(),selected=selectedCards.Select(c=>"card."+physical.IndexOf(c)).ToArray(),state=MultipleState()});
                            var result=T("GameActions.PlayerChoiceResult").GetMethod("FromMutableCombatCards")!.Invoke(null,new[]{Typed(selectedCards,T("Models.CardModel"))})!;
                            C(choices,"ReceiveReplayChoice",player,(uint)choice,C(result,"ToNetData"));
                            C(queue,"ResumeActionWithoutSynchronizing",P(action,"Id"));
                            await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));choice++;
                        }
                        Require(P(action,"State").ToString()=="Finished","Deferred Horn did not finish.");
                        Require(answers.Count==1,"Expected one live-pile answer.");
                        Require((int)P(pc,"Block")== 6,"Resuming an already-shuffled draw must not shuffle again.");
                    }
                    Require((bool)P(queue,"IsEmpty") && C(queue,"GetReadyAction") is null,"Hook remained actionable.");
                    Require(new[]{"Hand","DrawPile","DiscardPile","PlayPile"}.SelectMany(Pile).OrderBy(x=>x).SequenceEqual(Enumerable.Range(0,fillers+1).Select(i=>"card."+i)),"Physical cards lost or duplicated.");
                    var multiHistory=Items(P(P(manager,"History"),"Entries"));
                    var multiHits=multiHistory.Where(e=>e.GetType().Name=="DamageReceivedEntry").Select(e=>new{slot=P(P(e,"Receiver"),"SlotName"),damage=P(P(e,"Result"),"UnblockedDamage"),blocked=P(P(e,"Result"),"BlockedDamage")}).ToArray();
                    // Native multiHistory intentionally omits the combat-ending hit.
                    Require(multiHits.Length==(terminal ? 4 : deaths),"Wrong native damage multiHistory length.");
                    Require((int)P(P(rng,"CombatTargets"),"Counter")==deaths,"Wrong target RNG count.");
                    rows.Add(new{seed,fillers,upgraded,terminal,deaths,hits=multiHits,before=multipleBefore,enemiesBefore,checkpoint,enemiesCheckpoint=surviving,answers,after=MultipleState(),enemiesAfter=Enemies(),
                        canceled=terminal,pendingStates=pending.Select(a=>P(a,"State").ToString()).ToArray(),
                        shuffle=MultiStream("Shuffle"),targets=MultiStream("CombatTargets"),niche=MultiStream("Niche"),ai=MultiStream("MonsterAi")});
                    C(cardDb,"OnCombatEnded",new object?[]{null});((IDisposable)choices).Dispose();
                    continue;
                }
                Require(Pile("DiscardPile").Contains("card."+fillers),"Outer card was not discarded.");
                var attackPaused=State();var enemiesPaused=Enemies();
                var generated=Items(sync.GetType().GetField("_hookActions",flags)!.GetValue(sync)!);
                Require(generated.Length==(fillers==1 ? 0 : 1),"Incorrect number of detached Horn hooks.");
                Require(Items(P(combat,"Enemies")).Length==4,"Infested did not create four surviving children.");
                Require(Items(P(combat,"Enemies")).Sum(c=>(int)P(c,"MaxHp")-(int)P(c,"CurrentHp"))==(upgraded ? 9 : 6),"Remaining Sword Boomerang hits did not reach children.");
                Require((int)P(pc,"Block")== (fillers==1 ? 6 : 0),"Abacus ordering mismatch.");
                string? selected=null;
                if(generated.Length==1)
                {
                    var action=generated[0];C(queue,"EnqueueWithoutSynchronizing",action);
                    Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Deferred Horn hook not ready.");
                    F(executor,"<CurrentlyRunningAction>k__BackingField",action);
                    await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
                    Require(P(action,"State").ToString()=="GatheringPlayerChoice","Native selector did not pause.");
                    Require(Items(P(choices,"ChoiceIds")).Select(Convert.ToUInt32).SequenceEqual(new[]{1u}),"Unexpected reserved choice IDs.");
                    var available=Items(P(P(pcs,"DrawPile"),"Cards"));
                    var card=upgraded ? available[^1] : available[0];selected="card."+physical.IndexOf(card);
                    var result=T("GameActions.PlayerChoiceResult").GetMethod("FromMutableCombatCard")!.Invoke(null,new[]{card})!;
                    C(choices,"ReceiveReplayChoice",player,0u,C(result,"ToNetData"));
                    C(queue,"ResumeActionWithoutSynchronizing",P(action,"Id"));
                    await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
                    Require(P(action,"State").ToString()=="Finished","Horn hook did not finish.");
                }
                Require((bool)P(queue,"IsEmpty"),"Replay queue did not drain.");
                Require((int)P(pcs,"Energy")==1 && (int)P(pc,"Block")==6,"Horn/Abacus result missing.");
                Require(Pile("Hand").Length==(fillers==1 ? 1 : 2),"Wrong final hand.");
                Require(new[]{"Hand","DrawPile","DiscardPile"}.SelectMany(Pile).OrderBy(x=>x).SequenceEqual(Enumerable.Range(0,fillers+1).Select(i=>"card."+i)),"Lost or duplicated physical card.");
                object Stream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
                var history=Items(P(P(manager,"History"),"Entries"));
                var hits=history.Where(e=>e.GetType().Name=="DamageReceivedEntry").Select(e=>new {
                    slot=P(P(e,"Receiver"),"SlotName"),damage=P(P(e,"Result"),"UnblockedDamage"),blocked=P(P(e,"Result"),"BlockedDamage")
                }).ToArray();
                Require(hits.Length==(upgraded ? 4 : 3),"Incorrect native damage history length.");
                Require(history.Count(e=>e.GetType().Name=="CardPlayFinishedEntry")==1,"Card play history not completed.");
                rows.Add(new{seed,fillers,upgraded,hits,before=attackBefore,enemiesBefore,paused=attackPaused,enemiesPaused,after=State(),enemiesAfter=Enemies(),detached=generated.Length==1,selected,
                    shuffle=Stream("Shuffle"),targets=Stream("CombatTargets"),niche=Stream("Niche"),ai=Stream("MonsterAi")});
                C(cardDb,"OnCombatEnded",new object?[]{null});((IDisposable)choices).Dispose();
                continue;
            }
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
        return JsonSerializer.Serialize(new{source=drawCards ? "Actual PlayCardAction for Pillage/EscapePlan with Stratagem/Abacus; blocked/limited draws and controlled native draw-to-discard moves during a paused choice; no live UI/executor loop" : flak ? "Actual Mayhem/FlakCannon with queued Slimed/Wound, optional DarkEmbrace, Stratagem/Abacus and replay choices; explicit callback, no turn manager/UI/executor loop" : autoplay ? "Actual MayhemPower.AfterAutoPrePlayPhaseEntered and CardPileCmd.AutoPlayFromDrawPile, Stratagem/Abacus and replay choices; explicit native hook callback, no turn manager/UI/executor loop" : enemyTurn ? "Actual CombatManager.ExecuteEnemyTurn through next player setup, two Chomper moves with Thorns/Horn/Stratagem/Abacus and optional ToolsOfTheTrade; checksums disabled, native replay answers after enemy work, no UI or executor frame loop" : multipleDeaths ? "Actual PlayCardAction/SwordBoomerang with Strength100 and optional Duplication, death/Horn/Infested and replay choices; explicit native SetCombatState(NotInCombat) cancellation at IsEnding; no full EndCombatInternal, UI or executor loop" : attackMode ? "Actual PlayCardAction/SwordBoomerang, death dispatcher, Horn/Stratagem/Abacus and Infested; in-memory native replay choice, manually driven queue, no UI/executor loop/run" : "Actual GremlinHorn.AfterDeath, CardPileCmd.Draw/Shuffle, StratagemPower, TheAbacus and native hook queue; test selector supplies UI signals/answer; explicit death callback invocation, no death dispatcher/attack/UI/run",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true});
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
