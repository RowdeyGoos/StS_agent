using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Real native run/reward objects under TestMode and explicit in-memory saves.
internal static class CampaignOracle
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
        tables.Add("ancients",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"ancients",new Dictionary<string,string>{{"THE_ARCHITECT.talk.IRONCLAD.0-0.next","Continue"},{"PROCEED.title","Proceed"},{"PROCEED.description","Finished"}},null})!);
        tables.Add("characters",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"characters",new[]{"title","titleObject","possessiveAdjective","pronounObject","pronounPossessive","pronounSubject"}.ToDictionary(k=>"IRONCLAD."+k,k=>"Ironclad"),null})!);
        F(loc,"_tables",tables);C(loc,"LoadLocFormatters");loc.GetType().GetProperty("CultureInfo",flags)!.SetValue(loc,System.Globalization.CultureInfo.InvariantCulture);loc.GetType().GetProperty("Instance",flags)!.SetValue(null,loc);
        var rows=new List<object>();
        foreach(string seed in new[]{"0","2","42"})
        foreach(string loadout in new[]{"plain","maw_bank","wongo","both"})
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
                if(loadout is "maw_bank" or "both")await Await(C(T("Commands.RelicCmd"),"Obtain",C(Get("Relic","Relics.MawBank"),"ToMutable"),player,-1));
                if(loadout is "wongo" or "both")
                {
                    var ticket=C(Get("Relic","Relics.WongosMysteryTicket"),"ToMutable");
                    await Await(C(T("Commands.RelicCmd"),"Obtain",ticket,player,-1));
                    ticket.GetType().GetProperty("CombatsFinished",flags)!.SetValue(ticket,5);
                }
                C(manager,"GenerateRooms");
                await Await(C(manager,"EnterAct",2,false));
                C(P(player,"Creature"),"SetCurrentHpInternal",31m);
                var boss=C(P(P(state,"Act"),"BossEncounter"),"ToMutable");
                var child=Activator.CreateInstance(T("Rooms.CombatRoom"),new[]{boss,state})!;
                C(child,"MarkPreFinished");C(state,"PopCurrentRoom");C(state,"PushRoom",child);
                var rewardsTask=(Task)C(T("Commands.RewardsCmd"),"GenerateForRoomEnd",player,child);await Await(rewardsTask);
                var rewards=P(rewardsTask,"Result");
                var rewardRows=Items(P(rewards,"Rewards")).Select(r=>new{kind=r.GetType().Name,relic=r.GetType().Name=="RelicReward"?P(P(P(r,"Relic"),"Id"),"Entry").ToString():null}).ToArray();
                var goldBefore=P(player,"Gold");
                var nicheBefore=P(P(P(state,"Rng"),"Niche"),"Counter");
                var floorBefore=P(state,"TotalFloor");
                await Await(C(manager,"EnterNextAct"));
                var room=P(state,"CurrentRoom");
                var architect=C(P(manager,"EventSynchronizer"),"GetLocalEvent");
                Require(architect.GetType().Name=="TheArchitect","Missing Architect ending.");
                Require(Items(P(architect,"CurrentOptions")).Length==1,"Architect initialization failed.");
                var entryHp=P(P(player,"Creature"),"CurrentHp");
                var eventRng=P(architect,"Rng");
                var eventCounter=P(eventRng,"Counter");
                var niche=P(P(state,"Rng"),"Niche");
                var nicheCounter=P(niche,"Counter");
                // Record the same serialization boundary used by OnEnded, before
                // native victory disposes of player creatures.
                var winning=C(manager,"ToSave",(object?)null);
                await Await(C(manager,"EnterNextAct"));
                rows.Add(new{seed,loadout,rewardRows,goldBefore,goldAfter=P(player,"Gold"),nicheBefore,floorBefore,floorAfter=P(state,"TotalFloor"),entryHp,
                    savedHp=P(Items(P(winning,"Players"))[0],"CurrentHp"),disposedHp=P(P(player,"Creature"),"CurrentHp"),
                    room=P(room,"RoomType").ToString(),isVictoryRoom=P(room,"IsVictoryRoom"),
                    eventCounter,eventSuffix=C(eventRng,"NextDouble"),nicheCounter,nicheSuffix=C(niche,"NextDouble"),uploadsDisabled=!(bool)P(P(saves,"PrefsSave"),"UploadData"),savingDisabled=!(bool)P(manager,"ShouldSave"),mockCalls=Items(P(store,"Calls")).Length,
                    recorded=(bool)manager.GetType().GetField("_runHistoryWasUploaded",flags)!.GetValue(manager)!});
            }
            finally { C(manager,"CleanUp",true); }
        }
        return JsonSerializer.Serialize(new{source="Actual native final boss to Architect and WinRun under TestMode; authored finished boss, mock saves, no UI or profiles",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true});
    }
}
