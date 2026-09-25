using System;
using System.Text.Json;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Unified;

internal static class Program
{
    private static int _checks;
    private static void Check(bool value,string name){_checks++;if(!value)throw new Exception(name);}
    private static bool Throws(Action action){try{action();return false;}catch(InvalidOperationException){return true;}}
    private sealed class Fixture
    {
        internal readonly RunState Run=new();
        internal readonly NRun Node=new();
        internal readonly NRewardsScreen Screen=new(){Button=new()};
        internal readonly RunManager Manager=new();
        internal readonly Player Player=new();
        internal Fixture(int act=0,bool boss=true) {
            Run.CurrentActIndex=act;Run.Players.Add(Player);Run.CurrentRoom=new AbstractRoom{RoomType=boss?RoomType.Boss:RoomType.Monster};
            Manager.State=Run;RunManager.Instance=Manager;NRun.Instance=Node;Node.GlobalUi.Overlays.Screens.Add(Screen);
            Screen.Bind(Run);
            Screen.Button!.Released=()=>{if(boss)Manager.ActionQueueSynchronizer.RequestEnqueue(new VoteToMoveToNextActAction(Player));else _=Manager.ProceedFromTerminalRewardsScreen();};
            Manager.Next=()=>{Advance();return Task.CompletedTask;};
            // Native ProceedFromTerminalRewardsScreen retains terminal rewards
            // beneath the map; travel clears the previous room's screens.
            Manager.Proceed=()=>{Node.GlobalUi.MapScreen.IsOpen=Node.GlobalUi.MapScreen.IsTravelEnabled=true;return Task.CompletedTask;};
        }
        internal void Advance() {
            Node.GlobalUi.Overlays.Screens.Clear();
            if(Run.CurrentActIndex==2) {Run.CurrentRoom=new EventRoom{IsVictoryRoom=true};Node.EventRoom=new();}
            else {Run.CurrentActIndex++;Run.CurrentRoom=new MapRoom();Node.MapRoom=new();Node.GlobalUi.MapScreen.IsOpen=Node.GlobalUi.MapScreen.IsTravelEnabled=true;}
        }
    }
    private static void Transitions() {
        foreach(var mode in new[]{"map","act","ending","delayed_vote","delayed_task","vote_only","wrong_player","wrong_destination","fault","cancel","dispose_pending","dispose_task","second_boss"}) {
            var f=new Fixture(mode=="ending"?2:0,mode!="map"&&mode!="second_boss");
            if(mode=="second_boss") {f.Run.CurrentRoom!.RoomType=RoomType.Boss;f.Run.Map.SecondBossMapPoint=new();f.Run.CurrentMapCoord=f.Run.Map.BossMapPoint.coord;}
            GameAction? queued=null;var gate=new TaskCompletionSource();
            if(mode is "delayed_vote" or "dispose_pending" or "cancel")f.Manager.ActionQueueSynchronizer.Enqueue=a=>queued=a;
            if(mode is "delayed_task" or "dispose_task")f.Manager.Next=()=>{f.Advance();return gate.Task;};
            if(mode=="vote_only")f.Manager.ActionQueueSynchronizer.Enqueue=a=>{queued=a;a.Completion.SetResult();};
            if(mode=="wrong_player")f.Screen.Button!.Released=()=>f.Manager.ActionQueueSynchronizer.RequestEnqueue(new VoteToMoveToNextActAction(new()));
            if(mode=="wrong_destination")f.Manager.Next=()=>{f.Advance();f.Run.CurrentRoom=new EventRoom();return Task.CompletedTask;};
            if(mode=="fault")f.Manager.Next=()=>Task.FromException(new InvalidOperationException());
            var transition=new CampaignRewardTransition(f.Screen);
            bool success=mode is "map" or "act" or "ending" or "delayed_vote" or "delayed_task" or "second_boss";
            try {
                if(mode=="wrong_player"){Check(Throws(transition.Dispatch),"foreign player never queued");continue;}
                transition.Dispatch();
                if(mode is "delayed_vote" or "delayed_task" or "vote_only" or "dispose_pending" or "dispose_task" or "cancel")
                    Check(transition.Poll()=="waiting","receipt or visible destination is not completion: "+mode);
                if(mode=="delayed_vote")queued!.Execute();
                if(mode=="delayed_task")gate.SetResult();
                if(mode=="cancel")queued!.Cancel();
                if(mode is "dispose_pending" or "dispose_task") {
                    Check(Throws(transition.Dispose)&&Throws(transition.Dispose),"uncertain disposal stays failed");
                    if(mode=="dispose_pending")Check(Throws(()=>queued!.Execute())&&f.Run.CurrentActIndex==0,"disposed queued vote remains revoked");
                    else gate.SetResult();
                    continue;
                }
                if(success)Check(transition.Poll()==(mode is "map" or "second_boss"?"map":mode=="ending"?"ending":"act"),"exact destination: "+mode);
                else if(mode!="vote_only")Check(Throws(()=>transition.Poll()),"failed native transition: "+mode);
            }finally {
                bool rejected=Throws(transition.Dispose);Check(rejected!=success,"cleanup result: "+mode);
                if(success)Check(!Throws(transition.Dispose),"successful cleanup idempotent");
            }
        }
    }
    private static void Admission() {
        foreach(var mode in new[]{"network","modal","wrong_overlay","disabled","hidden","debug_override","victory_room","non_terminal","foreign_screen_run"}) {
            var f=new Fixture();
            if(mode=="network")f.Manager.NetService.Type=2;
            if(mode=="modal")NModalContainer.Instance=new(){OpenModal=new()};
            if(mode=="wrong_overlay")f.Node.GlobalUi.Overlays.Screens.Add(new());
            if(mode=="disabled")f.Screen.Button!.IsEnabled=false;
            if(mode=="hidden")f.Screen.Button!.Visible=false;
            if(mode=="debug_override")f.Manager.debugAfterCombatRewardsOverride=()=>{};
            if(mode=="victory_room")f.Run.CurrentRoom!.IsVictoryRoom=true;
            if(mode=="non_terminal")f.Screen.Bind(f.Run,false);
            if(mode=="foreign_screen_run")f.Screen.Bind(new());
            Check(Throws(()=>_=new CampaignRewardTransition(f.Screen)),"reject before input: "+mode);
            NModalContainer.Instance=null;
        }
    }
    private static void Navigation() {
        var f=new Fixture();f.Node.GlobalUi.Overlays.Screens.Clear();
        f.Run.CurrentRoom=new TreasureRoom();f.Node.TreasureRoom=new();
        f.Node.TreasureRoom.Bind(f.Run);
        using var nav=new CampaignNavigation();
        var read=nav.Handle(new(false));using var doc=JsonDocument.Parse(read.Body);
        string id=doc.RootElement.GetProperty("decision_id").GetString()!;
        Check(doc.RootElement.GetProperty("surface").GetString()=="treasure","visible treasure admitted");
        Check(doc.RootElement.GetProperty("legal_actions")[0].GetString()=="open_chest"&&!f.Node.TreasureRoom.ProceedButton.Visible,"closed chest never advertises hidden Proceed");
        Check(!nav.Handle(new(true,id,"open_chest")).Terminal&&nav.Active,"chest Open receipt retains ownership");
        using var waiting=JsonDocument.Parse(nav.Handle(new(false)).Body);
        Check(waiting.RootElement.GetProperty("status").GetString()=="waiting"&&f.Node.TreasureRoom.Skips==0,"reads do not bypass native Skip delay");
        f.Node.TreasureRoom.ShowSkip();
        using var skip=JsonDocument.Parse(nav.Handle(new(false)).Body);
        string skipId=skip.RootElement.GetProperty("decision_id").GetString()!;
        Check(skip.RootElement.GetProperty("completed_decision_id").GetString()==id&&skipId!=id&&nav.Active,"Open reconciles but native task remains owned");
        Check(skip.RootElement.GetProperty("legal_actions")[0].GetString()=="skip_relic","native enabled Skip advertised");
        Check(!nav.Handle(new(true,skipId,"skip_relic")).Terminal&&nav.Active,"Skip receipt is not map completion");
        var done=nav.Handle(new(false));using var observed=JsonDocument.Parse(done.Body);
        Check(!nav.Active&&observed.RootElement.GetProperty("completed_decision_id").GetString()==skipId&&observed.RootElement.GetProperty("surface").GetString()=="map","both treasure native tasks and map reconciled");
        Check(f.Node.TreasureRoom.Opens==1&&f.Node.TreasureRoom.Skips==1,"one native input per POST");
        f.Manager.State=new();Check(nav.Handle(new(false)).Terminal,"another run cannot be adopted");
    }
    private static void TreasureOwnership() {
        foreach(var mode in new[]{"hidden","disabled","opened","foreign_room","foreign_run","modal","capstone"}) {
            var f=new Fixture();f.Node.GlobalUi.Overlays.Screens.Clear();f.Run.CurrentRoom=new TreasureRoom();
            var chest=new NTreasureRoom();f.Node.TreasureRoom=chest;chest.Bind(f.Run);
            if(mode=="hidden")chest.ChestButton.Visible=false;
            if(mode=="disabled")chest.ChestButton.IsEnabled=false;
            if(mode=="opened")chest.MarkOpened();
            if(mode=="foreign_room")f.Run.CurrentRoom=new TreasureRoom();
            if(mode=="foreign_run")chest.Bind(new RunState{CurrentRoom=new TreasureRoom()});
            if(mode=="modal")NModalContainer.Instance=new(){OpenModal=new()};
            if(mode=="capstone")MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance=new(){InUse=true};
            Check(Throws(()=>_=new CampaignTreasureTransition(chest))&&chest.Opens==0,"treasure admission before input: "+mode);
            NModalContainer.Instance=null;MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance=null;
        }
        foreach(var mode in new[]{"native_dormant","delayed_skip","delayed_proceed","failed_open","failed_delay","pending_ftue","extra_rewards","modal_after_open","owner_lost","queue_lost","duplicate_open","skip_disabled","dispose_pending","foreign_player","non_null_pick","foreign_synchronizer","completed_open","picking_began","dispose_state_changed","dispose_queued","queued_foreign_sync","queued_collection_began","queued_capstone"}) {
            var f=new Fixture();f.Node.GlobalUi.Overlays.Screens.Clear();f.Run.CurrentRoom=new TreasureRoom();
            var chest=new NTreasureRoom();f.Node.TreasureRoom=chest;chest.Bind(f.Run);
            var gate=new TaskCompletionSource();
            GameAction? queued=null;
            if(mode=="pending_ftue")chest.FtueTask=gate.Task;
            var t=new CampaignTreasureTransition(chest);t.Apply("open_chest");
            if(mode=="failed_open")chest.OpenGate.SetException(new InvalidOperationException());
            if(mode=="failed_delay")chest.DelayGate.SetException(new InvalidOperationException());
            else chest.ShowSkip();
            if(mode=="extra_rewards")f.Node.GlobalUi.Overlays.Screens.Add(new NRewardsScreen());
            if(mode=="modal_after_open")NModalContainer.Instance=new(){OpenModal=new()};
            if(mode=="owner_lost")f.Run.CurrentRoom=new TreasureRoom();
            if(mode=="queue_lost")f.Manager.ActionQueueSynchronizer=new();
            bool success=mode is "native_dormant" or "delayed_skip" or "delayed_proceed";
            if(mode=="duplicate_open")Check(Throws(()=>t.Apply("open_chest"))&&chest.Opens==1,"Open never retried");
            else if(mode=="skip_disabled") {chest.ProceedButton.IsEnabled=false;Check(Throws(()=>t.Apply("skip_relic"))&&chest.Skips==0,"Skip legality rechecked");}
            else if(mode is "failed_open" or "failed_delay" or "extra_rewards" or "modal_after_open" or "owner_lost" or "queue_lost")Check(Throws(()=>t.Read())&&chest.Skips==0,"treasure fails closed: "+mode);
            else if(mode=="pending_ftue")Check(t.Read()=="waiting"&&chest.Skips==0,"tutorial task completion required");
            else if(mode is "foreign_player" or "non_null_pick" or "foreign_synchronizer") {
                chest.SkipAction=()=>new PickRelicAction(mode=="foreign_player"?new():f.Player,mode=="non_null_pick"?0:null){TestSynchronizer=mode=="foreign_synchronizer"?new():null};
                Check(Throws(()=>t.Apply("skip_relic"))&&!f.Manager.TreasureRoomRelicSynchronizer.Skipped,"exact native null-pick only: "+mode);
            }
            else if(mode is "completed_open" or "picking_began" or "dispose_state_changed") {
                if(mode=="completed_open")chest.CompleteOpenOnSkip=true;
                t.Apply("skip_relic");
                if(mode=="picking_began")chest.Collection.Began.SetResult();
                if(mode=="dispose_state_changed") {Check(t.Read()=="map","skip settled before cleanup");chest.Collection.Began.SetResult();}
                else Check(Throws(()=>t.Read()),"foreign native progression cannot be a settled Skip: "+mode);
            }
            else if(mode=="dispose_queued") {
                f.Manager.ActionQueueSynchronizer.Enqueue=a=>queued=a;t.Apply("skip_relic");
                Check(t.Read()=="waiting","map does not certify queued Skip");
                Check(Throws(t.Dispose),"queued Skip disposal fails");
                Check(Throws(()=>queued!.Execute())&&!f.Manager.TreasureRoomRelicSynchronizer.Skipped,"disposed delayed Skip is revoked");
            }
            else if(mode.StartsWith("queued_",StringComparison.Ordinal)) {
                f.Manager.ActionQueueSynchronizer.Enqueue=a=>queued=a;t.Apply("skip_relic");
                if(mode=="queued_foreign_sync")f.Manager.TreasureRoomRelicSynchronizer=new();
                if(mode=="queued_collection_began")chest.Collection.Began.SetResult();
                if(mode=="queued_capstone")MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance=new(){InUse=true};
                Check(Throws(()=>queued!.Execute())&&!f.Manager.TreasureRoomRelicSynchronizer.Skipped,"delayed Skip revalidates full treasure owner before mutation: "+mode);
            }
            else if(success) {
                if(mode=="delayed_proceed")f.Manager.Proceed=()=>{f.Node.GlobalUi.MapScreen.IsOpen=f.Node.GlobalUi.MapScreen.IsTravelEnabled=true;return gate.Task;};
                if(mode=="delayed_skip")f.Manager.ActionQueueSynchronizer.Enqueue=a=>queued=a;
                t.Apply("skip_relic");
                if(mode!="native_dormant")Check(t.Read()=="waiting"&&t.Active,"visible map waits for Skip and Proceed: "+mode);
                if(mode=="delayed_skip")queued!.Execute();else if(mode=="delayed_proceed")gate.SetResult();
                Check(t.Read()=="map"&&!t.Active&&!chest.OpenGate.Task.IsCompleted&&chest.IsChoosing,"exact dormant native Open wait reconciled: "+mode);
            }
            Check(Throws(t.Dispose)!=success,"treasure cleanup result: "+mode);
            Check(Throws(t.Dispose)!=success,"treasure cleanup stays resolved or failed: "+mode);
            NModalContainer.Instance=null;
            MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance=null;
        }
    }
    private static void TreasureClaims() {
        foreach(string mode in new[]{"empty_list","empty_null","empty_foreign_sync","empty_inventory","empty_pending"}) {
            var f=new Fixture();f.Node.GlobalUi.Overlays.Screens.Clear();f.Run.CurrentRoom=new TreasureRoom();
            f.Manager.TreasureRoomRelicSynchronizer.CurrentRelics=mode=="empty_null"?null:new();
            var chest=new NTreasureRoom();f.Node.TreasureRoom=chest;chest.Bind(f.Run);
            var transition=new CampaignTreasureTransition(chest,true);transition.Apply("open_chest");
            Check(transition.Read()=="waiting","empty chest waits for native animation");
            if(mode=="empty_foreign_sync")f.Manager.TreasureRoomRelicSynchronizer=new();
            if(mode=="empty_inventory")f.Player.Relics.Add(new());
            if(mode is "empty_list" or "empty_null") {
                f.Manager.TreasureRoomRelicSynchronizer.CompleteWithNoRelics();
                Check(chest.DelayGate.Task.IsCanceled,"native empty animation cancels unfinished Skip delay");
                Check(transition.Read()=="proceed"&&f.Player.Relics.Count==0,"empty chest exposes native Proceed without a claim");
                transition.Apply("proceed");Check(transition.Read()=="map","empty chest returns to map without skip vote");
                transition.Dispose();transition.Dispose();
            } else {
                if(mode!="empty_pending")Check(Throws(()=>transition.Read()),"empty chest rejects changed ownership or inventory");
                Check(Throws(transition.Dispose)&&Throws(transition.Dispose),"unresolved empty chest cannot hand off");
            }
        }
        foreach(string mode in new[]{"success","pending_effect","foreign_holder","foreign_model","modal","queued_owner_lost","queued_synchronizer","queued_holder","cancelled_action","foreign_result"}) {
            var f=new Fixture();f.Node.GlobalUi.Overlays.Screens.Clear();f.Run.CurrentRoom=new TreasureRoom();
            var chest=new NTreasureRoom();f.Node.TreasureRoom=chest;chest.Bind(f.Run);
            var effect=new TaskCompletionSource();if(mode=="pending_effect")f.Manager.TreasureRoomRelicSynchronizer.CurrentRelics![0].Effect=()=>effect.Task;
            var t=new CampaignTreasureTransition(chest,true);t.Apply("open_chest");chest.ShowSkip();Check(t.Read()=="relic","full chest offers claim");
            GameAction? queued=null;bool success=mode is "success" or "pending_effect";
            if(mode=="foreign_holder")chest.Collection.SingleplayerRelicHolder=new();
            if(mode=="foreign_model")chest.Collection.SingleplayerRelicHolder.Relic.Model=new();
            if(mode=="modal")NModalContainer.Instance=new(){OpenModal=new()};
            if(mode is "foreign_holder" or "foreign_model" or "modal") Check(Throws(()=>t.Apply("claim_relic"))&&f.Player.Relics.Count==0,"changed claim target rejected before mutation");
            else {
                if(!success)f.Manager.ActionQueueSynchronizer.Enqueue=a=>queued=a;
                t.Apply("claim_relic");
                if(mode=="pending_effect"){Check(t.Read()=="waiting"&&chest.OpenGate.Task.IsCompleted,"chest animation cannot certify pending relic effect");effect.SetResult();}
                if(mode=="queued_owner_lost"){f.Run.CurrentRoom=new TreasureRoom();Check(Throws(()=>queued!.Execute())&&f.Player.Relics.Count==0,"queued claim rechecks room");}
                if(mode=="queued_synchronizer"){((PickRelicAction)queued!).TestSynchronizer=new();Check(Throws(()=>queued.Execute())&&f.Player.Relics.Count==0,"foreign queued synchronizer rejected");}
                if(mode=="queued_holder"){chest.Collection.SingleplayerRelicHolder=new();Check(Throws(()=>queued!.Execute())&&f.Player.Relics.Count==0,"replaced queued holder rejected");}
                if(mode=="cancelled_action"){queued!.Cancel();Check(Throws(()=>t.Read()),"cancelled claim stays failed");}
                if(mode=="foreign_result"){f.Manager.TreasureRoomRelicSynchronizer.CurrentRelics![0]=new();Check(Throws(()=>queued!.Execute()),"queued offer model rechecked");Check(Throws(()=>t.Read())&&f.Player.Relics.Count==0,"foreign native award rejected");}
                if(success){Check(t.Read()=="proceed"&&f.Player.Relics.Count==1,"exact claim and obtain finish");t.Apply("proceed");Check(t.Read()=="map","claim leaves without skip vote");}
            }
            Check(Throws(t.Dispose)!=success,"claim cleanup reflects settlement");NModalContainer.Instance=null;
        }
    }
    private static void CleanupFailure() {
        var chestFixture=new Fixture();chestFixture.Node.GlobalUi.Overlays.Screens.Clear();chestFixture.Run.CurrentRoom=new TreasureRoom();
        var chest=new NTreasureRoom();chestFixture.Node.TreasureRoom=chest;chest.Bind(chestFixture.Run);
        var treasure=new CampaignTreasureTransition(chest);treasure.Apply("open_chest");chest.ShowSkip();treasure.Apply("skip_relic");
        Check(treasure.Read()=="map"&&chest.IsChoosing&&!chest.OpenGate.Task.IsCompleted,"treasure cleanup fixture retains native dormant wait");
        CampaignTreasureTransition.BeforeCleanupForTest=()=>throw new InvalidOperationException("fixture cleanup failure");
        Check(Throws(treasure.Dispose),"treasure unpatch failure reported");
        CampaignTreasureTransition.BeforeCleanupForTest=null;
        Check(Throws(treasure.Dispose),"treasure cleanup failure remains sticky after completion");
        var f=new Fixture();var transition=new CampaignRewardTransition(f.Screen);
        transition.Dispatch();Check(transition.Poll()=="act","cleanup fixture completed");
        CampaignRewardTransition.BeforeCleanupForTest=()=>throw new InvalidOperationException("fixture cleanup failure");
        Check(Throws(transition.Dispose),"unpatch failure reported");
        CampaignRewardTransition.BeforeCleanupForTest=null;
        Check(Throws(transition.Dispose),"unpatch failure stays failed after completion");
    }
    private static void RewardMapRouting() {
        foreach(var mode in new[]{"map","closed","disabled","traveling","foreign_overlay","nested_overlay","modal","capstone"}) {
            var f=new Fixture(boss:false);
            using(var transition=new CampaignRewardTransition(f.Screen)) {
                transition.Dispatch();Check(transition.Poll()=="map","native reward Proceed completes");
            }
            Check(ReferenceEquals(f.Node.GlobalUi.Overlays.Peek(),f.Screen),"reward overlay remains under map");
            if(mode=="closed")f.Node.GlobalUi.MapScreen.IsOpen=false;
            if(mode=="disabled")f.Node.GlobalUi.MapScreen.IsTravelEnabled=false;
            if(mode=="traveling")f.Node.GlobalUi.MapScreen.IsTraveling=true;
            if(mode=="foreign_overlay"){f.Node.GlobalUi.Overlays.Screens.Clear();f.Node.GlobalUi.Overlays.Screens.Add(new());}
            if(mode=="nested_overlay")f.Node.GlobalUi.Overlays.Screens.Add(new());
            if(mode=="modal")NModalContainer.Instance=new(){OpenModal=new()};
            if(mode=="capstone")MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance=new(){InUse=true};
            using var nav=new CampaignNavigation();using var view=JsonDocument.Parse(nav.Handle(new(false)).Body);
            string expectedStatus=mode is "foreign_overlay" or "nested_overlay" or "modal" or "capstone"?"unsupported":
                mode is "disabled" or "traveling"?"waiting":"ready";
            string expectedSurface=expectedStatus=="unsupported"?"overlay":mode=="closed"?"rewards":mode=="traveling"?"unknown":"map";
            Check(view.RootElement.GetProperty("status").GetString()==expectedStatus&&
                view.RootElement.GetProperty("surface").GetString()==expectedSurface,"reward/map foreground routing: "+mode);
            NModalContainer.Instance=null;MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance=null;
        }
    }
    private static void MapIdentity() {
        var f=new Fixture();var map=f.Node.GlobalUi.MapScreen;
        map.IsOpen=map.IsTravelEnabled=true;
        static MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapPoint Point()=>new() {
            State=MegaCrit.Sts2.Core.Map.MapPointState.Travelable,
            Point=new(){coord=(2,1),PointType=MegaCrit.Sts2.Core.Map.MapPointType.Monster}};
        map.Children.Add(Point());
        var reader=new Sts2AgentBridge.Adapters.Public.PinnedPublicMapDecisionReader();
        var before=reader.Read();
        Check(before.Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Ready,"map ready");
        Check(reader.Read().DecisionId==before.DecisionId,"repeated map observation preserves decision identity");
        map.Children.Clear();map.Children.Add(Point());
        var after=reader.Read();
        Check(before.Candidates[0]==after.Candidates[0]&&before.DecisionId!=after.DecisionId,
            "identical coordinates in a new act cannot reuse an earlier decision");
        Check(reader.Read().DecisionId==after.DecisionId,"new act observation stable");
    }
    private static void Shops() {
        foreach(var mode in new[]{"ok","owner_lost","opened","gold","pending"}) {
            var f=new MultiplePurchaseFixture(0){Closed=true};bool owner=true;
            var transition=new CampaignShopTransition(new string('a',32),f,()=>owner);
            if(mode=="owner_lost")owner=false;
            if(mode=="opened")f.Closed=false;
            if(mode is "owner_lost" or "opened") {
                Check(Throws(transition.Dispatch)&&f.Leaves==0,"closed shop revalidates before input");
            } else {
                transition.Dispatch();Check(f.Leaves==1&&f.Closes==0&&f.Purchases==0,"closed shop only leaves");
                if(mode=="gold")f.Gold++;
                if(mode=="pending")f.MapOpen=false;
                if(mode=="ok")Check(transition.Poll()=="map","owned shop leave reconciled");
                if(mode=="gold")Check(Throws(()=>transition.Poll()),"shop inventory changes cannot reconcile");
                if(mode=="pending")Check(transition.Poll()=="waiting","shop waits for actionable map");
            }
            Check(Throws(transition.Dispose)==(mode!="ok"),"shop unresolved disposal fails");
            Check(Throws(transition.Dispose)==(mode!="ok"),"shop repeated disposal preserves failure");
        }
        var entry=new Fixture();entry.Node.GlobalUi.Overlays.Screens.Clear();
        entry.Run.CurrentRoom=new MerchantRoom();entry.Node.MerchantRoom=new();
        var shop=new MultiplePurchaseFixture(0){Closed=true};
        Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native.PinnedShopV1NativeAdapter.Current=shop;
        using var nav=new CampaignNavigation();
        using var read=JsonDocument.Parse(nav.Handle(new(false)).Body);
        string id=read.RootElement.GetProperty("decision_id").GetString()!;
        Check(read.RootElement.GetProperty("surface").GetString()=="shop","closed shop advertises campaign proceed");
        Check(!nav.Handle(new(true,id,"proceed")).Terminal&&nav.Active,"closed shop receipt retains ownership");
        entry.Node.GlobalUi.MapScreen.IsOpen=entry.Node.GlobalUi.MapScreen.IsTravelEnabled=true;
        using var done=JsonDocument.Parse(nav.Handle(new(false)).Body);
        Check(done.RootElement.GetProperty("completed_decision_id").GetString()==id&&!nav.Active,"closed shop completes through campaign navigation");
        foreach(var guard in new[]{"modal","capstone","tutorial"}) {
            var blocked=new Fixture();blocked.Node.GlobalUi.Overlays.Screens.Clear();
            blocked.Run.CurrentRoom=new MerchantRoom();blocked.Node.MerchantRoom=new();
            var merchant=new MultiplePurchaseFixture(0){Closed=true};
            Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native.PinnedShopV1NativeAdapter.Current=merchant;
            var guarded=new CampaignNavigation();
            using var initial=JsonDocument.Parse(guarded.Handle(new(false)).Body);
            string choice=initial.RootElement.GetProperty("decision_id").GetString()!;
            if(guard=="tutorial")Check(!guarded.Handle(new(true,choice,"proceed")).Terminal,"tutorial starts after input");
            if(guard=="capstone")MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance=new(){InUse=true};
            else NModalContainer.Instance=new(){OpenModal=new()};
            Check(guarded.Handle(guard=="tutorial"?new(false):new(true,choice,"proceed")).Terminal,"shop foreground revalidated: "+guard);
            Check(merchant.Leaves==(guard=="tutorial"?1:0),"no input beneath another foreground owner");
            NModalContainer.Instance=null;MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance=null;
            Check(Throws(guarded.Dispose)==(guard=="tutorial"),"tutorial cannot certify cleanup");
            if(guard=="tutorial")Check(Throws(guarded.Dispose),"tutorial unresolved cleanup remains failed");
        }
    }
    private static void Main(){Transitions();Admission();Navigation();TreasureOwnership();MapIdentity();Shops();RewardMapRouting();TreasureClaims();CleanupFailure();Console.WriteLine("campaign native checks: "+_checks);}
}
