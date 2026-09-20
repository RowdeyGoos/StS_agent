using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Real native run/reward objects under TestMode and explicit in-memory saves.
internal static class GeneratedStartOracle
{
    public static async Task<string> Run(Assembly asm,string digest,bool campaign=false,bool boosted=false)
    {
        const BindingFlags flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a){var t=o as Type??o.GetType();return t.GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o is Type?null:o,a)!;}
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        Array Typed(IEnumerable<object> source,Type t){var v=source.ToArray();var result=Array.CreateInstance(t,v.Length);Array.Copy(v,result,v.Length);return result;}
        void Require(bool value,string message){if(!value)throw new InvalidOperationException(message);}
        async Task Await(object task)=>await ((Task)task).WaitAsync(TimeSpan.FromSeconds(3));
        object Get(string method,string suffix)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+suffix)).Invoke(null,null)!;
        T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,true);
        // Native TestMode initialization exits before inspecting mod directories.
        await Await(C(T("Modding.ModManager"),"Initialize",null,null,null));
        foreach(var t in asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.AbstractModel"))&&t.Namespace!.StartsWith("MegaCrit.Sts2.Core.Models.")))C(T("Models.ModelDb"),"Inject",t);
        var loc=RuntimeHelpers.GetUninitializedObject(T("Localization.LocManager"));
        var tables=(System.Collections.IDictionary)Activator.CreateInstance(typeof(Dictionary<,>).MakeGenericType(typeof(string),T("Localization.LocTable")))!;
        tables.Add("ancients",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"ancients",new Dictionary<string,string>{{"THE_ARCHITECT.talk.IRONCLAD.0-0.next","Continue"},{"PROCEED.title","Proceed"},{"PROCEED.description","Finished"}},null})!);
        tables.Add("characters",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"characters",new[]{"title","titleObject","possessiveAdjective","pronounObject","pronounPossessive","pronounSubject"}.ToDictionary(k=>"IRONCLAD."+k,k=>"Ironclad"),null})!);
        F(loc,"_tables",tables);C(loc,"LoadLocFormatters");loc.GetType().GetProperty("CultureInfo",flags)!.SetValue(loc,System.Globalization.CultureInfo.InvariantCulture);loc.GetType().GetProperty("Instance",flags)!.SetValue(null,loc);
        var cache=T("Assets.PreloadManager").GetProperty("Cache")!.GetValue(null)!;
        var assets=cache.GetType().GetField("_cache",flags)!.GetValue(cache)!;
        C(assets,"TryAdd","res://images/enchantments/missing_enchantment.png",new Godot.CompressedTexture2D());
        C(assets,"TryAdd","res://images/atlases/ui_atlas.sprites/card/energy_ironclad.tres",new Godot.AtlasTexture());
        var rows=new List<object>();
        foreach(string seed in new[]{"0"})
        {
            var store=Activator.CreateInstance(T("Saves.Test.MockGodotFileIo"),new object[]{"user://isolated-fixture"})!;
            var saves=Activator.CreateInstance(T("Saves.SaveManager"),new object[]{store,true})!;F(saves,"_currentProfileId",0);C(T("Saves.SaveManager"),"MockInstanceForTesting",saves);
            C(saves,"InitPrefsDataForTest");
            P(saves,"PrefsSave").GetType().GetProperty("UploadData")!.SetValue(P(saves,"PrefsSave"),false);
            Require(!(bool)P(P(saves,"PrefsSave"),"UploadData"),"Metrics uploads must be disabled.");
            T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);
            var player=C(T("Entities.Players.Player"),"CreateForNewRun",Get("Character","Characters.Ironclad"),T("Unlocks.UnlockState").GetField("all")!.GetValue(null),0UL);
            var state=C(T("Runs.RunState"),"CreateForTest",Typed(new[]{player},player.GetType()),null,null,Enum.Parse(T("Runs.GameMode"),"Standard"),0,seed);
            var manager=T("Runs.RunManager").GetProperty("Instance")!.GetValue(null)!;
            var replay=Activator.CreateInstance(T("Multiplayer.NetReplayGameService"),new object[]{0UL})!;
            C(manager,"SetUpTest",state,replay,true,false);
            try
            {
                Require(!(bool)P(manager,"ShouldSave"),"Persistent saving must be disabled.");
                const int boostedHp=1000000;
                if(boosted){C(P(player,"Creature"),"SetMaxHpInternal",(decimal)boostedHp);C(P(player,"Creature"),"SetCurrentHpInternal",(decimal)boostedHp);}
                var relicText=new Dictionary<string,string>();
                foreach(var relic in Items(T("Models.ModelDb").GetProperty("AllRelics")!.GetValue(null)!))foreach(var suffix in new[]{"title","description","eventDescription","selectionScreenPrompt"})relicText[P(P(relic,"Id"),"Entry")+"."+suffix]=P(P(relic,"Id"),"Entry").ToString()!;
                if(!tables.Contains("relics"))tables.Add("relics",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"relics",relicText,null})!);
                if(!tables.Contains("events"))tables.Add("events",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"events",new Dictionary<string,string>(),null})!);
                foreach(var tableName in new[]{"card_keywords","cards","static_hover_tips","powers","enchantments","afflictions","monsters"})
                {
                    var texts=new Dictionary<string,string>();
                    var names=tableName=="afflictions"?asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.AfflictionModel"))).Select(t=>C(T("Helpers.StringHelper"),"Slugify",t.Name).ToString()!):
                        tableName=="card_keywords"?Enum.GetNames(T("Entities.Cards.CardKeyword")).Select(n=>C(T("Helpers.StringHelper"),"Slugify",n).ToString()!):
                        tableName=="static_hover_tips"?Enum.GetNames(T("HoverTips.StaticHoverTip")).Select(n=>C(T("Helpers.StringHelper"),"Slugify",n).ToString()!):
                        tableName=="monsters"?asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.MonsterModel"))).Select(t=>C(T("Helpers.StringHelper"),"Slugify",t.Name).ToString()!):
                        tableName=="enchantments"?asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.EnchantmentModel"))).Select(t=>C(T("Helpers.StringHelper"),"Slugify",t.Name).ToString()!):
                        tableName=="cards"?Items(T("Models.ModelDb").GetProperty("AllCards")!.GetValue(null)!).Select(c=>P(P(c,"Id"),"Entry").ToString()!):
                        new[]{"BLOCK","POWER","STRENGTH","VULNERABLE","WEAK","DEXTERITY","DAMAGE","ENERGY","CARD_REWARD"};
                    foreach(var name in names)foreach(var suffix in new[]{"name","title","description","upgradeDescription","selectionScreenPrompt"})texts[name+"."+suffix]=name;
                    if(tableName=="powers")texts["DAMPEN_POWER.banter"]="Dampen";
                    if(tableName=="monsters")foreach(var key in new[]{"BYGONE_EFFIGY.moves.SLEEP.speakLine1","BYGONE_EFFIGY.moves.SLEEP.speakLine2","HATCHLING.name","CHOMPER.moves.SCREECH.title","KNOWLEDGE_DEMON.moves.CURSE_OF_KNOWLEDGE.startLine","KNOWLEDGE_DEMON.moves.CURSE_OF_KNOWLEDGE.doneLine","DEVOTED_SCULPTOR.moves.FORBIDDEN_INCANTATION.banter","CALCIFIED_CULTIST.moves.INCANTATION.banter","DAMP_CULTIST.moves.INCANTATION.banter"})texts[key]="Sleep";
                    if(!tables.Contains(tableName))tables.Add(tableName,Activator.CreateInstance(T("Localization.LocTable"),new object?[]{tableName,texts,null})!);
                }
                var selector=Activator.CreateInstance(T("TestSupport.TestCardSelector"))!;
                using var selected=(IDisposable)C(T("Commands.CardSelectCmd"),"UseSelector",selector);
                C(manager,"GenerateRooms");
                await Await(C(manager,"EnterAct",0,false));
                var neow=C(P(manager,"EventSynchronizer"),"GetLocalEvent");
                var options=Items(P(neow,"CurrentOptions"));
                Require(options.Length==3,"Expected three Neow offers.");
                // Fixed policy: choose the second offered relic (native positive group).
                var option=options[1];
                var offers=options.Select(o=>P(P(P(o,"Relic"),"Id"),"Entry").ToString()).ToArray();
                var choice=P(P(P(option,"Relic"),"Id"),"Entry").ToString();
                await Await(C(option,"Chosen"));
                Require((bool)P(neow,"IsFinished"),"Neow did not finish.");
                var rewardsAfterNeow=P(P(P(player,"PlayerRng"),"Rewards"),"Counter");
                object point=P(P(state,"Map"),"StartingMapPoint");
                object Coord(object p)=>p.GetType().GetField("coord")!.GetValue(p)!;
                int Row(object p)=>(int)Coord(p).GetType().GetField("row")!.GetValue(Coord(p))!;
                int Col(object p)=>(int)Coord(p).GetType().GetField("col")!.GetValue(Coord(p))!;
                object RunBoundary()
                {
                    var result=new Dictionary<string,object?> {
                        ["hp"]=P(P(player,"Creature"),"CurrentHp"),["gold"]=P(player,"Gold"),
                        ["relics"]=Items(P(player,"Relics")).Select(r=>P(P(r,"Id"),"Entry").ToString()).ToArray(),
                        ["deck"]=Items(P(P(player,"Deck"),"Cards")).Select(c=>new{id=P(P(c,"Id"),"Entry").ToString(),upgrade=P(c,"CurrentUpgradeLevel")}).ToArray(),
                        ["rewardsCounter"]=P(P(P(player,"PlayerRng"),"Rewards"),"Counter"),["nicheCounter"]=P(P(P(state,"Rng"),"Niche"),"Counter"),["shuffleCounter"]=P(P(P(state,"Rng"),"Shuffle"),"Counter")};
                    if(boosted)result["maxHp"]=P(P(player,"Creature"),"MaxHp");
                    return result;
                }
                async Task<object> Rewards(object rewardRoom)
                {
                    var generated=(Task)C(T("Commands.RewardsCmd"),"GenerateForRoomEnd",player,rewardRoom);await Await(generated);
                    var set=P(generated,"Result");var rewards=Items(P(set,"Rewards"));
                    T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,null);
                    var offered=(Task)C(set,"Offer");var sync=P(manager,"RewardsSetSynchronizer");var claimed=new List<object>();
                    foreach(var reward in rewards)
                    {
                        var kind=reward.GetType().Name;
                        if(kind=="GoldReward") { var amount=P(reward,"Amount");await Await(C(sync,"SelectLocalReward",reward));claimed.Add(new{kind,amount}); }
                        else if(kind=="RelicReward") { var relic=P(P(P(reward,"Relic"),"Id"),"Entry").ToString();await Await(C(sync,"SelectLocalReward",reward));claimed.Add(new{kind,relic}); }
                        else if(kind=="CardReward")
                        {
                            var offeredCards=Items(P(reward,"Cards"));
                            var safe=new[]{"PERFECTED_STRIKE","POMMEL_STRIKE","SHRUG_IT_OFF","ANGER","IRON_WAVE","TWIN_STRIKE","SWORD_BOOMERANG","BATTLE_TRANCE","INFLAME","METALLICIZE","THUNDERCLAP"};
                            int index=Enumerable.Range(0,offeredCards.Length).Where(i=>safe.Contains(P(P(offeredCards[i],"Id"),"Entry").ToString())).OrderBy(i=>Array.IndexOf(safe,P(P(offeredCards[i],"Id"),"Entry").ToString())).DefaultIfEmpty(-1).First();
                            if(index>=0)
                            {
                                var selection=(Task)C(sync,"SelectLocalReward",reward);var choices=P(manager,"PlayerChoiceSynchronizer");
                                var waiting=Items(choices.GetType().GetField("_receivedChoices",flags)!.GetValue(choices)!);Require(waiting.Length==1,"Expected one replay reward choice.");
                                uint id=(uint)waiting[0].GetType().GetField("choiceId")!.GetValue(waiting[0])!;
                                var answer=C(T("GameActions.PlayerChoiceResult"),"FromIndex",index);
                                C(choices,"ReceiveReplayChoice",player,id,C(answer,"ToNetData"));await Await(selection);
                            }
                            claimed.Add(new{kind,index,cards=offeredCards.Select(c=>new{id=P(P(c,"Id"),"Entry").ToString(),upgrade=P(c,"CurrentUpgradeLevel")}).ToArray()});
                        }
                    }
                    if(!offered.IsCompleted)C(sync,"SkipLocalRewardsSet");await Await(offered);
                    T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);
                    await Await(C(manager,"ProceedFromTerminalRewardsScreen"));
                    return new{claims=claimed,state=RunBoundary()};
                }
                var route=new List<object>();
                void AddRoom(object room)=>route.Add(boosted?(object)new{actIndex=P(state,"CurrentActIndex"),room}:room);
                object? winningState=null;
                bool completed=false;
                var costs=new Dictionary<object,int>();
                int RouteCost(object p)
                {
                    if(costs.TryGetValue(p,out int found))return found;
                    int own=P(p,"PointType").ToString() switch {"Unknown"=>1000,"Elite"=>100,"Monster"=>5,_=>0};
                    var children=Items(P(p,"Children"));return costs[p]=own+(children.Length==0?0:children.Min(RouteCost));
                }
                for(int floor=0;floor<(campaign?60:1);floor++)
                {
                var children=Items(P(point,"Children"));Require(children.Length>0,"No next map point.");
                var next=campaign?children.OrderBy(RouteCost).ThenBy(Col).First():children.OrderBy(Col).First();
                point=next;
                await Await(C(manager,"EnterMapCoord",Coord(next)));
                var room=P(state,"CurrentRoom");
                var entry=RunBoundary();
                if(room.GetType().Name!="CombatRoom")
                {
                    string kind=room.GetType().Name;
                    if(kind=="RestSiteRoom")await Await(C(Items(P(room,"Options")).Single(o=>P(o,"OptionId").ToString()=="HEAL"),"OnSelect"));
                    else Require(kind is "TreasureRoom" or "MerchantRoom","Unsupported generated room: "+kind);
                    if(boosted && kind=="TreasureRoom")
                    {
                        await Await(C(room,"DoNormalRewards"));await Await(C(room,"DoExtraRewardsIfNeeded"));
                        // Same completed solo skip action as the opened chest UI.
                        var skip=Activator.CreateInstance(T("GameActions.PickRelicAction"),new object?[]{player,null})!;
                        C(P(manager,"ActionQueueSet"),"EnqueueWithoutSynchronizing",skip);
                        await Await(C(P(manager,"ActionExecutor"),"FinishedExecutingActions"));
                        Require(P(skip,"State").ToString()=="Finished","Chest skip did not finish.");
                    }
                    // Both leaving a shop without buying and leaving a closed chest are legal.
                    AddRoom(new{row=Row(next),col=Col(next),kind,entry,state=RunBoundary()});
                    continue;
                }
                var combatManager=T("Combat.CombatManager").GetProperty("Instance")!.GetValue(null)!;

                var combat=P(room,"CombatState");
                var clock=System.Diagnostics.Stopwatch.StartNew();
                while(P(P(manager,"ActionQueueSynchronizer"),"CombatState").ToString()!="PlayPhase"){Require(clock.ElapsedMilliseconds<3000,"Combat start timed out.");await Task.Yield();}
                var actions=new List<object>();
                object Card(object c)=>new{id=P(P(c,"Id"),"Entry").ToString(),upgrade=P(c,"CurrentUpgradeLevel")};
                object Boundary()
                {
                    var result=new Dictionary<string,object?> {
                        ["hp"]=P(P(player,"Creature"),"CurrentHp"),["block"]=P(P(player,"Creature"),"Block"),["energy"]=P(P(player,"PlayerCombatState"),"Energy"),
                        ["hand"]=Items(P(P(P(player,"PlayerCombatState"),"Hand"),"Cards")).Select(Card).ToArray(),
                        ["enemies"]=Items(P(combat,"Enemies")).Select(c=>boosted?(object)new{combatId=P(c,"CombatId"),id=P(P(P(c,"Monster"),"Id"),"Entry").ToString(),hp=P(c,"CurrentHp"),block=P(c,"Block")}:new{id=P(P(P(c,"Monster"),"Id"),"Entry").ToString(),hp=P(c,"CurrentHp"),block=P(c,"Block")}).ToArray()};
                    if(boosted)result["maxHp"]=P(P(player,"Creature"),"MaxHp");
                    return result;
                }
                var initial=Boundary();
                for(int n=0;n<300 && (bool)P(combatManager,"IsInProgress");n++)
                {
                    var pcs=P(player,"PlayerCombatState");
                    var enemies=Items(P(combat,"Enemies"));
                    var living=enemies.Where(e=>(bool)P(e,"IsAlive"));
                    var target=campaign?living.OrderBy(e=>Convert.ToDecimal(P(e,"CurrentHp"))).FirstOrDefault():living.FirstOrDefault();
                    var hand=Items(P(P(pcs,"Hand"),"Cards"));
                    var playable=hand.Where(c=>(bool)C(c,"CanPlayTargeting",P(c,"TargetType").ToString()=="AnyEnemy"?target:null));
                    var priorities=new[]{"INFLAME","BATTLE_TRANCE","PERFECTED_STRIKE","ANGER","POMMEL_STRIKE","SWORD_BOOMERANG","TWIN_STRIKE","BASH","THUNDERCLAP","IRON_WAVE","STRIKE_IRONCLAD","SHRUG_IT_OFF","DEFEND_IRONCLAD"};
                    int incoming=campaign?living.Sum(e=>Items(P(P(P(e,"Monster"),"NextMove"),"Intents")).Where(i=>T("MonsterMoves.Intents.AttackIntent").IsInstanceOfType(i)).Sum(i=>(int)C(i,"GetTotalDamage",Typed(new[]{P(player,"Creature")},T("Entities.Creatures.Creature")),e))):0;
                    bool slippery=target is not null && Items(P(target,"Powers")).Any(p=>P(P(p,"Id"),"Entry").ToString()=="SLIPPERY_POWER");
                    int Priority(object c){string id=P(P(c,"Id"),"Entry").ToString()!;if(slippery && id=="SWORD_BOOMERANG")return -1;if(slippery && id=="PERFECTED_STRIKE")return 90;if(incoming>Convert.ToInt32(P(P(player,"Creature"),"Block")) && id is "SHRUG_IT_OFF" or "DEFEND_IRONCLAD")return 4;int rank=Array.IndexOf(priorities,id);return rank<0?99:rank;}
                    var card=campaign?playable.OrderBy(Priority).FirstOrDefault():playable.FirstOrDefault();
                    if(card is not null)
                    {
                        int index=Array.IndexOf(hand,card);
                        var play=Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{card,P(card,"TargetType").ToString()=="AnyEnemy"?target:null})!;
                        var queue=P(manager,"ActionQueueSet");var executor=P(manager,"ActionExecutor");
                        C(queue,"EnqueueWithoutSynchronizing",play);
                        await Await(C(executor,"FinishedExecutingActions"));
                        Require(P(play,"State").ToString()=="Finished","Card action paused unexpectedly.");
                        await Await(C(combatManager,"CheckWinCondition"));
                        actions.Add(boosted?(object)new{kind="play",index,targetCombatId=target is null?null:P(target,"CombatId"),card=Card(card),state=(bool)P(combatManager,"IsInProgress")?Boundary():null}:campaign?(object)new{kind="play",index,targetIndex=Array.IndexOf(enemies,target),card=Card(card),state=(bool)P(combatManager,"IsInProgress")?Boundary():null}:new{kind="play",index,card=Card(card),state=(bool)P(combatManager,"IsInProgress")?Boundary():null});
                    }
                    else
                    {
                        bool curse=boosted && living.Any(e=>P(P(e,"Monster"),"Id").ToString()=="MONSTER.KNOWLEDGE_DEMON" && P(P(P(e,"Monster"),"NextMove"),"Id").ToString()=="CURSE_OF_KNOWLEDGE_MOVE");
                        if(curse)C(selector,"PrepareToSelect",new[]{0});
                        await Await(C(combatManager,"EndPlayerTurnPhaseOneInternal"));
                        if((bool)P(combatManager,"IsInProgress"))await Await(C(combatManager,"EndPlayerTurnPhaseTwoInternal"));
                        if((bool)P(combatManager,"IsInProgress"))await Await(C(combatManager,"SwitchFromPlayerToEnemySide",(object?)null));
                        if(curse)Require(Items(selector.GetType().GetField("_indicesToSelectTaskQueue",flags)!.GetValue(selector)!).Length==0,"Curse answer was not consumed.");
                        actions.Add(boosted?(object)new{kind="end",choiceIndices=curse?new[]{0}:Array.Empty<int>(),state=(bool)P(combatManager,"IsInProgress")?Boundary():null}:new{kind="end",state=(bool)P(combatManager,"IsInProgress")?Boundary():null});
                    }
                }
                Require(!(bool)P(combatManager,"IsInProgress"),"Combat action budget exhausted.");
                var trace=new{seed,offers,choice,rewardsAfterNeow,row=Row(next),col=Col(next),encounter=P(P(P(room,"Encounter"),"Id"),"Entry").ToString(),initial,actions,hp=P(P(player,"Creature"),"CurrentHp")};
                if(!campaign)rows.Add(trace);
                else
                {
                    bool alive=(bool)P(P(player,"Creature"),"IsAlive");
                    var rewards=alive?await Rewards(room):null;
                    AddRoom(new{row=Row(next),col=Col(next),kind="CombatRoom",entry,combat=trace,rewards,state=RunBoundary()});
                    if(!alive)break;
                    if(P(room,"RoomType").ToString()=="Boss")
                    {
                        if(!boosted){completed=true;break;}
                        await Await(C(manager,"EnterNextAct"));
                        if((bool)P(P(state,"CurrentRoom"),"IsVictoryRoom"))
                        {
                            var ending=C(P(manager,"EventSynchronizer"),"GetLocalEvent");
                            Require(ending.GetType().Name=="TheArchitect","Expected Architect.");
                            winningState=RunBoundary();
                            var saved=C(manager,"ToSave",(object?)null);
                            await Await(C(manager,"EnterNextAct"));
                            bool recorded=(bool)manager.GetType().GetField("_runHistoryWasUploaded",flags)!.GetValue(manager)!;
                            Require(recorded && Convert.ToInt32(P(Items(P(saved,"Players"))[0],"CurrentHp"))>0 && Convert.ToInt32(P(P(player,"Creature"),"CurrentHp"))==0,"Native victory was not recorded before disposal.");
                            AddRoom(new{kind="Victory",recorded,entry=winningState,savedHp=P(Items(P(saved,"Players"))[0],"CurrentHp"),disposedHp=P(P(player,"Creature"),"CurrentHp"),state=winningState});
                            completed=true;break;
                        }
                        point=P(P(state,"Map"),"StartingMapPoint");costs.Clear();
                        var transition=RunBoundary();
                        await Await(C(manager,"EnterMapCoord",Coord(point)));
                        var ancient=C(P(manager,"EventSynchronizer"),"GetLocalEvent");
                        var ancientEntry=RunBoundary();
                        var ancientOptions=Items(P(ancient,"CurrentOptions"));
                        Require(ancientOptions.Length==3,"Expected Ancient offers.");
                        var ancientOffers=ancientOptions.Select(o=>P(P(P(o,"Relic"),"Id"),"Entry").ToString()).ToArray();
                        var avoided=new[]{"PAELS_TOOTH","PAELS_CLAW","BEAUTIFUL_BRACELET","JEWELRY_BOX","FUR_COAT"};
                        var chosen=ancientOptions.First(o=>!avoided.Contains(P(P(P(o,"Relic"),"Id"),"Entry").ToString()));
                        var ancientChoice=P(P(P(chosen,"Relic"),"Id"),"Entry").ToString();
                        await Await(C(chosen,"Chosen"));Require((bool)P(ancient,"IsFinished"),"Ancient did not finish.");
                        AddRoom(new{kind="ActTransition",ancient=P(P(ancient,"Id"),"Entry").ToString(),row=Row(point),col=Col(point),transition,entry=ancientEntry,offers=ancientOffers,choice=ancientChoice,state=RunBoundary()});
                    }
                }
                }
                if(boosted)
                {
                    Require(completed && winningState is not null,"Boosted campaign did not win within room/action budgets.");
                    rows.Add(new{seed,offers,choice,rewardsAfterNeow,startingHp=boostedHp,startingMaxHp=boostedHp,route,state=winningState,outcome="victory"});
                }
                else if(campaign)rows.Add(new{seed,offers,choice,rewardsAfterNeow,route,state=RunBoundary(),outcome=(bool)P(P(player,"Creature"),"IsAlive")?"act_complete":"defeat"});
            }
            finally{C(manager,"CleanUp",true);}
        }
        return JsonSerializer.Serialize(new{source=boosted?"Native continuous three-act campaign with explicitly authored 1000000 starting/current max HP; real card actions, rewards and boss wins; manual turn phases and mock persistence; not an ordinary winning run":campaign?"Native generated continuous route with real card actions and rewards, manual turn phases, optional chest/shop skips, mock saves and uploads disabled; no synthetic victories":"Native generated Neow and first combat only; real card action executor, manually invoked end-turn phases, UI-only mock localization/textures, mock saves and uploads disabled; no synthetic victories",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true});
    }
}
