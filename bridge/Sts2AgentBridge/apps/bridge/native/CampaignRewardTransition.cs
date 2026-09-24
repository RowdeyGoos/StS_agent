using System;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Unified;

// Observes the game's reward Proceed control. It never calls EnterNextAct or
// manufactures a vote, and cannot certify victory (the event terminal owns that).
internal sealed class CampaignRewardTransition : IPublicRewardTransition
{
    private static CampaignRewardTransition? _owner;
    private static readonly MethodInfo Queue = typeof(ActionQueueSynchronizer).GetMethod("RequestEnqueue", new[]{typeof(GameAction)})!;
    private static readonly MethodInfo Next = typeof(RunManager).GetMethod("EnterNextAct", Type.EmptyTypes)!;
    private static readonly MethodInfo Proceed = typeof(RunManager).GetMethod("ProceedFromTerminalRewardsScreen", Type.EmptyTypes)!;
    private static readonly FieldInfo VotePlayer = typeof(VoteToMoveToNextActAction).GetField("_player", BindingFlags.Instance|BindingFlags.NonPublic)!;
    private static readonly FieldInfo PickPlayer = typeof(PickRelicAction).GetField("_player", BindingFlags.Instance|BindingFlags.NonPublic)!;
    private static readonly FieldInfo PickIndex = typeof(PickRelicAction).GetField("_relicIndex", BindingFlags.Instance|BindingFlags.NonPublic)!;
    private static readonly FieldInfo Execution = typeof(GameAction).GetField("_executionTask", BindingFlags.Instance|BindingFlags.NonPublic)!;
    private static readonly FieldInfo TerminalScreen = typeof(NRewardsScreen).GetField("_isTerminal", BindingFlags.Instance|BindingFlags.NonPublic)!;
    private static readonly FieldInfo ScreenRun = typeof(NRewardsScreen).GetField("_runState", BindingFlags.Instance|BindingFlags.NonPublic)!;
#if CAMPAIGN_TEST_SEAM
    internal static Action? BeforeCleanupForTest;
#endif
    private readonly Harmony _harmony = new("sts2.agent.campaign.reward."+Guid.NewGuid().ToString("N"));
    private readonly Control _screen;
    private readonly bool _treasure;
    private readonly Func<bool>? _treasureContext;
    private readonly NProceedButton _button;
    private readonly NRun _node;
    private readonly RunManager _manager;
    private readonly ActionQueueSynchronizer _queue;
    private readonly RunState _run;
    private readonly AbstractRoom _room;
    private readonly Player _player;
    private readonly int _act, _thread = System.Environment.CurrentManagedThreadId;
    private readonly bool _nextAct;
    private readonly long _deadline = System.Environment.TickCount64+30000;
    private GameAction? _vote;
    private Task? _task;
    private bool _dispatching, _started, _complete, _disposed, _failed, _cleanupFailed;

    internal CampaignRewardTransition(NRewardsScreen screen):this(screen,screen.GetNodeOrNull<NProceedButton>("ProceedButton")!,false) { }
    internal static IPublicRewardTransition Legacy(NRewardsScreen screen) {
        var transition=new CampaignRewardTransition(screen);
        // The original completion contract can only describe an actionable map.
        // Reject before installing hooks or dispatching if the native UI advances acts.
        if(transition._nextAct)throw new InvalidOperationException("Act handoff requires reward-v2.");
        return transition;
    }
    internal CampaignRewardTransition(NTreasureRoom room,Func<bool> ownerContext):this(room,room.ProceedButton,true,ownerContext) { }
    private CampaignRewardTransition(Control screen,NProceedButton button,bool treasure,Func<bool>? ownerContext=null)
    {
        _treasure=treasure;_treasureContext=ownerContext;
        _screen=screen;_manager=RunManager.Instance;_run=_manager.DebugOnlyGetState()??throw new InvalidOperationException("Missing run.");_node=NRun.Instance??throw new InvalidOperationException("Missing run node.");
        _queue=_manager.ActionQueueSynchronizer;
        if(_run is null||_node is null||_run.Players.Count!=1)throw new InvalidOperationException("Campaign run unavailable.");
        _player=_run.Players[0];_room=_run.CurrentRoom!;_act=_run.CurrentActIndex;
        if(_room is null||_room.IsVictoryRoom||_act is <0 or >2||_manager.IsAbandoned||
            (int)_manager.NetService.Type!=1||_manager.debugAfterCombatRewardsOverride is not null||treasure&&_room is not TreasureRoom)
            throw new InvalidOperationException("Campaign reward context unsupported.");
        _nextAct=_room.RoomType==RoomType.Boss && !(_run.Map.SecondBossMapPoint is not null && _run.CurrentMapCoord==_run.Map.BossMapPoint.coord);
        _button=button;
        if(!Context()||_button is null||!GodotObject.IsInstanceValid(_button)||!_button.IsVisibleInTree()||!_button.IsEnabled)
            throw new InvalidOperationException("Reward Proceed unavailable.");
        if(!treasure&&(screen.GetType()!=typeof(NRewardsScreen)||TerminalScreen.GetValue(screen) is not true||!ReferenceEquals(ScreenRun.GetValue(screen),_run)))
            throw new InvalidOperationException("Terminal reward screen not owned.");
    }
    private bool Context()=>!_disposed&&!_failed&&System.Environment.CurrentManagedThreadId==_thread&&System.Environment.TickCount64<_deadline&&
        (!_treasure||_treasureContext is not null&&_treasureContext())&&
        ReferenceEquals(NRun.Instance,_node)&&ReferenceEquals(RunManager.Instance,_manager)&&ReferenceEquals(_manager.DebugOnlyGetState(),_run)&&
        ReferenceEquals(_manager.ActionQueueSynchronizer,_queue)&&(int)_manager.NetService.Type==1&&!_manager.IsAbandoned&&_player.Creature.CurrentHp>0&&
        ReferenceEquals(_run.CurrentRoom,_room)&&_run.CurrentActIndex==_act&&_run.Players.Count==1&&ReferenceEquals(_run.Players[0],_player)&&
        (_treasure?_node.GlobalUi.Overlays.ScreenCount==0&&ReferenceEquals(_node.TreasureRoom,_screen):
            _node.GlobalUi.Overlays.ScreenCount==1&&ReferenceEquals(_node.GlobalUi.Overlays.Peek(),_screen))&&
        NModalContainer.Instance?.OpenModal is null&&GodotObject.IsInstanceValid(_screen);
    private void Require(bool valid) {if(!valid){_failed=true;throw new InvalidOperationException("Campaign reward ownership lost.");}}
    public void Dispatch()
    {
        Require(_owner is null&&Context()&&!_dispatching&&_vote is null&&_task is null);
        foreach(var target in new[]{Queue,Next,Proceed})Require(target is not null&&!(Harmony.GetPatchInfo(target)?.Owners.Any()??false));
        _owner=this;
        try {
            Patch(Queue,nameof(BeforeQueue));Patch(Next,nameof(BeforeNext),nameof(AfterTask));Patch(Proceed,nameof(BeforeProceed),nameof(AfterTask));
            _dispatching=true;
            Require(_button.EmitSignal(NClickableControl.SignalName.Released,_button)==Error.Ok);
        } catch {_failed=true;throw;} finally {_dispatching=false;}
        Require(_nextAct?_vote is not null:_task is not null&&(!_treasure||_vote is not null));
    }
    private void Patch(MethodInfo target,string prefix,string? postfix=null)=>_harmony.Patch(target,
        new HarmonyMethod(typeof(CampaignRewardTransition).GetMethod(prefix,BindingFlags.Static|BindingFlags.NonPublic)),
        postfix is null?null:new HarmonyMethod(typeof(CampaignRewardTransition).GetMethod(postfix,BindingFlags.Static|BindingFlags.NonPublic)));
    private static void BeforeQueue(ActionQueueSynchronizer __instance,GameAction action)
    {
        var o=_owner!;o.Require(o._dispatching&&o.Context()&&o._vote is null&&ReferenceEquals(__instance,o._manager.ActionQueueSynchronizer));
        if(o._treasure)o.Require(!o._nextAct&&action.GetType()==typeof(PickRelicAction)&&
            ReferenceEquals(PickPlayer.GetValue(action),o._player)&&PickIndex.GetValue(action) is null&&((PickRelicAction)action).TestSynchronizer is null);
        else o.Require(o._nextAct&&action.GetType()==typeof(VoteToMoveToNextActAction)&&ReferenceEquals(VotePlayer.GetValue(action),o._player));
        o._vote=action;action.BeforeExecuted+=o.BeforeVote;action.BeforeCancelled+=o.CancelVote;
    }
    private void BeforeVote(GameAction action) {Require(ReferenceEquals(action,_vote)&&Context()&&!_started);_started=true;}
    private void CancelVote(GameAction _) { _failed=true; }
    private static void BeforeNext(RunManager __instance) {
        var o=_owner!;o.Require(o._nextAct&&o._started&&o.Context()&&o._task is null&&ReferenceEquals(__instance,o._manager));
    }
    private static void BeforeProceed(RunManager __instance) {
        var o=_owner!;o.Require(!o._nextAct&&o._dispatching&&o.Context()&&o._task is null&&ReferenceEquals(__instance,o._manager));
    }
    private static void AfterTask(Task __result) {var o=_owner!;o.Require(__result is not null&&o._task is null);o._task=__result;}
    public string Poll()
    {
        Require(!_disposed&&!_failed&&ReferenceEquals(_owner,this)&&System.Environment.CurrentManagedThreadId==_thread&&System.Environment.TickCount64<_deadline&&
            ReferenceEquals(_manager,RunManager.Instance)&&ReferenceEquals(_run,_manager.DebugOnlyGetState())&&!_manager.IsAbandoned&&
            ReferenceEquals(NRun.Instance,_node)&&ReferenceEquals(_manager.ActionQueueSynchronizer,_queue)&&(int)_manager.NetService.Type==1&&
            _run.Players.Count==1&&ReferenceEquals(_player,_run.Players[0])&&_player.Creature.CurrentHp>0);
        Require(_task?.IsFaulted!=true&&_task?.IsCanceled!=true&&_vote?.Exception is null);
        if(_task?.IsCompletedSuccessfully!=true||_vote is not null&&!_vote.CompletionTask.IsCompleted)return "waiting";
        if(_vote is not null)Require(_started&&_vote.CompletionTask.IsCompletedSuccessfully&&Execution.GetValue(_vote) is Task {IsCompletedSuccessfully:true});
        string destination;
        if(!_nextAct) {
            Require(ReferenceEquals(_run.CurrentRoom,_room)&&_run.CurrentActIndex==_act);
            if(!_node.GlobalUi.MapScreen.IsOpen||!_node.GlobalUi.MapScreen.IsTravelEnabled||_node.GlobalUi.MapScreen.IsTraveling)return "waiting";
            destination="map";
        } else if(_act<2) {
            Require(_run.CurrentActIndex==_act+1&&_run.CurrentRoom is MapRoom&&!ReferenceEquals(_run.CurrentRoom,_room));
            if(_node.GlobalUi.Overlays.ScreenCount!=0||_node.MapRoom is null||!_node.MapRoom.IsVisibleInTree()||
                !_node.GlobalUi.MapScreen.IsOpen||!_node.GlobalUi.MapScreen.IsTravelEnabled||_node.GlobalUi.MapScreen.IsTraveling)return "waiting";
            destination="act";
        } else {
            Require(_run.CurrentActIndex==_act&&_run.CurrentRoom is EventRoom {IsVictoryRoom:true}&&!ReferenceEquals(_run.CurrentRoom,_room));
            if(_node.GlobalUi.Overlays.ScreenCount!=0||_node.EventRoom is null||!_node.EventRoom.IsVisibleInTree())return "waiting";
            destination="ending";
        }
        _complete=true;return destination;
    }
    public void Dispose()
    {
        if(_disposed) {
            if(!_complete||_cleanupFailed)throw new InvalidOperationException("Campaign reward cleanup remains unresolved.");
            return;
        }
        _disposed=true;
        // Revoke delayed dispatch before removing only our patches. An unresolved
        // native task makes disposal fail and stops the host's capability handoff.
        // A queued vote keeps its revocation guard if cleanup is uncertain. Its
        // eventual BeforeExecuted must still reject the disposed owner.
        try {
#if CAMPAIGN_TEST_SEAM
            BeforeCleanupForTest?.Invoke();
#endif
            foreach(var target in new[]{Queue,Next,Proceed})if(target is not null)_harmony.Unpatch(target,HarmonyPatchType.All,_harmony.Id);
            foreach(var target in new[]{Queue,Next,Proceed})
                if(Harmony.GetPatchInfo(target)?.Owners.Contains(_harmony.Id)==true)throw new InvalidOperationException("Campaign reward patch remains.");
            if(_complete&&_vote is not null){_vote.BeforeExecuted-=BeforeVote;_vote.BeforeCancelled-=CancelVote;}
            if(ReferenceEquals(_owner,this))_owner=null;
        } catch {_cleanupFailed=true;throw;}
        if(!_complete)throw new InvalidOperationException("Campaign reward did not reconcile.");
    }
}
