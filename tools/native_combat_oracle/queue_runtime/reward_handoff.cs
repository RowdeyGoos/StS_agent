using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Real native run/reward objects under TestMode and explicit in-memory saves.
internal static class RewardHandoffOracle
{
    public static async Task<string> Run(Assembly asm,string digest)
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
        var eventText=new Dictionary<string,string>();
        foreach(var setting in new[]{"SETTING_1","SETTING_2","SETTING_3"})foreach(var suffix in new[]{"title","description"})eventText["BATTLEWORN_DUMMY.pages.INITIAL.options."+setting+"."+suffix]=setting;
        tables.Add("events",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"events",eventText,null})!);
        tables.Add("characters",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"characters",new[]{"title","titleObject","possessiveAdjective","pronounObject","pronounPossessive","pronounSubject"}.ToDictionary(k=>"IRONCLAD."+k,k=>"Ironclad"),null})!);
        F(loc,"_tables",tables);C(loc,"LoadLocFormatters");loc.GetType().GetProperty("CultureInfo",flags)!.SetValue(loc,System.Globalization.CultureInfo.InvariantCulture);loc.GetType().GetProperty("Instance",flags)!.SetValue(null,loc);
        var rows=new List<object>();
        foreach(string seed in new[]{"0","2","42"})
        foreach(string scenario in new[]{"first","last","leave","cancel_then_first","MoltenEgg","ToxicEgg","FrozenEgg","WingCharm","SilverCrucible","SilkenTress","LastingCandy","FresnelLens","dummy_upgrade","dummy_timeout","act_1","act_2"})
        {
            var store=Activator.CreateInstance(T("Saves.Test.MockGodotFileIo"),new object[]{"user://isolated-fixture"})!;
            var saves=Activator.CreateInstance(T("Saves.SaveManager"),new object[]{store,true})!;F(saves,"_currentProfileId",0);C(T("Saves.SaveManager"),"MockInstanceForTesting",saves);
            C(saves,"InitPrefsDataForTest");
            P(saves,"PrefsSave").GetType().GetProperty("UploadData")!.SetValue(P(saves,"PrefsSave"),false);
            T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);
            var player=C(T("Entities.Players.Player"),"CreateForNewRun",Get("Character","Characters.Ironclad"),T("Unlocks.UnlockState").GetField("all")!.GetValue(null),0UL);
            var state=C(T("Runs.RunState"),"CreateForTest",Typed(new[]{player},player.GetType()),null,null,Enum.Parse(T("Runs.GameMode"),"Standard"),0,seed);
            var manager=T("Runs.RunManager").GetProperty("Instance")!.GetValue(null)!;
            var replay=Activator.CreateInstance(T("Multiplayer.NetReplayGameService"),new object[]{0UL})!;
            C(manager,"SetUpTest",state,replay,true,false);
            try
            {
            Require(!(bool)P(manager,"ShouldSave") && !(bool)P(P(saves,"PrefsSave"),"UploadData"),"Persistence and metrics must be disabled.");
            if(scenario.StartsWith("dummy_"))
            {
                var canonical=Get("Event","Events.BattlewornDummy");
                var parent=Activator.CreateInstance(T("Rooms.EventRoom"),new[]{canonical})!;
                C(state,"PushRoom",parent);
                C(P(manager,"EventSynchronizer"),"BeginEvent",canonical,false,null);
                var model=C(P(manager,"EventSynchronizer"),"GetLocalEvent");
                Require(Items(P(model,"CurrentOptions")).Length==3,"Dummy initialization failed.");
                var dummy=C(Get("Encounter","Encounters.BattlewornDummyEventEncounter"),"ToMutable");
                dummy.GetType().GetProperty("Setting")!.SetValue(dummy,Enum.Parse(dummy.GetType().GetNestedType("DummySetting")!,"Setting2"));
                dummy.GetType().GetProperty("RanOutOfTime")!.SetValue(dummy,scenario=="dummy_timeout");
                var child=Activator.CreateInstance(T("Rooms.CombatRoom"),new[]{dummy,state})!;
                child.GetType().GetProperty("ShouldResumeParentEventAfterCombat")!.SetValue(child,true);
                C(child,"MarkPreFinished");C(state,"PushRoom",child);
                await Await(C(manager,"ProceedFromTerminalRewardsScreen"));
                Require((bool)P(model,"IsFinished"),"Dummy resume did not finish.");
                var eventRng=P(model,"Rng");
                rows.Add(new{seed,scenario,rooms=P(state,"CurrentRoomCount"),room=P(P(state,"CurrentRoom"),"RoomType").ToString(),
                    deck=Items(P(P(player,"Deck"),"Cards")).Select(c=>new{id=P(P(c,"Id"),"Entry").ToString(),upgrade=P(c,"CurrentUpgradeLevel")}).ToArray(),
                    eventCounter=P(eventRng,"Counter"),eventSuffix=C(eventRng,"NextDouble")});
                continue;
            }
            if(scenario.StartsWith("act_"))
            {
                C(manager,"GenerateRooms");
                int from=int.Parse(scenario[^1..])-1;
                state.GetType().GetProperty("CurrentActIndex")!.SetValue(state,from);
                C(P(player,"Creature"),"SetCurrentHpInternal",31m);
                var boss=C(P(P(state,"Act"),"BossEncounter"),"ToMutable");
                var child=Activator.CreateInstance(T("Rooms.CombatRoom"),new[]{boss,state})!;
                C(child,"MarkPreFinished");C(state,"PushRoom",child);
                // Invoke the awaited transition reached by the solo act-change vote.
                // UI voting/executor scheduling are outside this fixture.
                await Await(C(manager,"EnterNextAct"));
                rows.Add(new{seed,scenario,act=P(state,"CurrentActIndex"),hp=P(P(player,"Creature"),"CurrentHp"),
                    floor=P(state,"ActFloor"),rooms=P(state,"CurrentRoomCount"),room=P(P(state,"CurrentRoom"),"RoomType").ToString(),hasMap=P(state,"Map") is not null});
                continue;
            }
            var encounter=C(Get("Encounter","Encounters.ToadpolesWeak"),"ToMutable");
            var room=Activator.CreateInstance(T("Rooms.CombatRoom"),new[]{encounter,state})!;C(room,"MarkPreFinished");C(state,"PushRoom",room);
            var history=Activator.CreateInstance(T("Runs.History.MapPointHistoryEntry"),new[]{Enum.Parse(T("Map.MapPointType"),"Monster"),state})!;
            var list=(System.Collections.IList)state.GetType().GetField("_mapPointHistory",flags)!.GetValue(state)!;
            var actHistory=(System.Collections.IList)Activator.CreateInstance(list.GetType().GetGenericArguments()[0])!;actHistory.Add(history);list.Add(actHistory);
            var task=(Task)C(T("Commands.RewardsCmd"),"GenerateForRoomEnd",player,room);await Await(task);var set=P(task,"Result");
            var generated=Items(P(set,"Rewards"));
            var gold=generated.Single(r=>r.GetType().Name=="GoldReward");
            var cards=generated.Single(r=>r.GetType().Name=="CardReward");
            object Card(object c)=>new {id=P(P(c,"Id"),"Entry").ToString(),upgrade=P(c,"CurrentUpgradeLevel"),enchantment=P(c,"Enchantment") is object e?P(P(e,"Id"),"Entry").ToString():null};
            object[] Offers()=>Items(P(cards,"Cards")).Select(Card).ToArray();
            var before=Offers();
            object? relic=null;
            object? relicReward=null;
            if(char.IsUpper(scenario[0]))
            {
                relic=C(Get("Relic","Relics."+scenario),"ToMutable");
                relicReward=Activator.CreateInstance(T("Rewards.RelicReward"),new[]{relic,player})!;
                ((System.Collections.IList)P(set,"Rewards")).Add(relicReward);
            }
            T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,null);
            var offered=(Task)C(set,"Offer");
            var sync=P(manager,"RewardsSetSynchronizer");
            if(relicReward is not null)await Await(C(sync,"SelectLocalReward",relicReward));
            var after=Offers();
            async Task Pick(int? index)
            {
                var selection=(Task)C(sync,"SelectLocalReward",cards);
                var choices=P(manager,"PlayerChoiceSynchronizer");
                var waiting=Items(choices.GetType().GetField("_receivedChoices",flags)!.GetValue(choices)!);
                Require(waiting.Length==1,"Expected one replay choice waiter.");
                uint id=(uint)waiting[0].GetType().GetField("choiceId")!.GetValue(waiting[0])!;
                var answer=C(T("GameActions.PlayerChoiceResult"),"FromIndex",index);
                C(choices,"ReceiveReplayChoice",player,id,C(answer,"ToNetData"));await Await(selection);
            }
            bool canceledStillOpen=false;
            if(scenario=="cancel_then_first")
            {
                await Pick(null);
                canceledStillOpen=!(bool)P(cards,"SuccessfullySelected")&&!offered.IsCompleted;
                Require(canceledStillOpen,"Cancel consumed the card reward.");
            }
            if(scenario!="leave")
            {
                await Await(C(sync,"SelectLocalReward",gold));
                await Pick(scenario=="last"?2:0);
                foreach(var potion in generated.Where(r=>r.GetType().Name=="PotionReward"))await Await(C(sync,"SelectLocalReward",potion));
            }
            if(!offered.IsCompleted)C(sync,"SkipLocalRewardsSet");
            await Await(offered);
            C(saves,"InitPrefsDataForTest");
            P(saves,"PrefsSave").GetType().GetProperty("UploadData")!.SetValue(P(saves,"PrefsSave"),false);
            T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);
            await Await(C(manager,"ProceedFromTerminalRewardsScreen"));
            var roomsAfterProceed=P(state,"CurrentRoomCount");
            await Await(C(manager,"EnterRoom",Activator.CreateInstance(T("Rooms.MapRoom"))!));
            var rewardsRng=P(P(player,"PlayerRng"),"Rewards");
            rows.Add(new{seed,scenario,before,after,canceledStillOpen,gold=P(player,"Gold"),
                deck=Items(P(P(player,"Deck"),"Cards")).Select(Card).ToArray(),
                potions=Items(P(player,"Potions")).Select(p=>P(P(p,"Id"),"Entry").ToString()).ToArray(),
                roomsAfterProceed,rooms=P(state,"CurrentRoomCount"),room=P(P(state,"CurrentRoom"),"RoomType").ToString(),
                rewardsCounter=P(rewardsRng,"Counter"),rewardsSuffix=C(rewardsRng,"NextDouble"),
                nicheCounter=P(P(P(state,"Rng"),"Niche"),"Counter"),nicheSuffix=C(P(P(state,"Rng"),"Niche"),"NextDouble"),
                relicCounter=relic is null?null:relic.GetType().GetProperty(scenario=="SilverCrucible"?"TimesUsed":"IsUsed",flags)?.GetValue(relic),
                selected=generated.Select(r=>new{kind=r.GetType().Name,selected=P(r,"SuccessfullySelected")}).ToArray()});
            }
            finally { C(manager,"CleanUp",true); }

        }
        return JsonSerializer.Serialize(new{source="Actual native reward selection and run handoff in test run, mock persistence, replay choices, no UI",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true});
    }
}
