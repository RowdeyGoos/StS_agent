using System;
using System.Collections.Generic;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Nodes;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// An entry callback is not a completed combat. This lease certifies only the
// exact combat requested by the event and any owned resume-time item child.
internal sealed class GenericEventV7CombatHandoff
{
    private readonly GenericEventV7Binding _binding;
    private readonly EncounterModel _encounter;
    private CombatRoom? _room;
    private CombatState? _state;
    private NCombatRoom? _node;
    internal bool Returned;
    internal readonly bool Resumes;
    private readonly EventRoom? _eventRoom;
    private Task? _resumeTask;
    private bool _resumeSeen;
    private NEventRoom? _resumedNode;
    private IGenericEventV7ItemChildSession? _item;
    private bool _itemResolved;
    private GenericEventV7ItemCompletion? _settledCompletion;
    private Sts2AgentBridge.Successors.ItemV1.ItemV1PotionSlotBinding[]? _settledSlots;
    private int _settledCapacity;
    private void SettleItem() {
        _settledCompletion=_itemCompletion!();
        if(!GenericEventV7ItemAdapter.Slots(_binding.Player,out _settledCapacity,out var slots))throw new InvalidOperationException("Settled inventory unavailable.");
        _settledSlots=slots.ToArray();_itemResolved=true;
    }
    private bool SettlementValid(GenericEventV7ItemCompletion now) {
        if(_settledCompletion is not {} old||!ReferenceEquals(now.Collection?.Identity,old.Collection?.Identity)||
            !ReferenceEquals(now.Offer?.Identity,old.Offer?.Identity)||!ReferenceEquals(now.Chosen?.Identity,old.Chosen?.Identity)||
            !GenericEventV7ItemAdapter.Slots(_binding.Player,out int capacity,out var slots)||capacity!=_settledCapacity||slots.Count!=_settledSlots!.Length)return false;
        for(int i=0;i<slots.Count;i++)if(!ReferenceEquals(slots[i].ModelIdentity,_settledSlots[i].ModelIdentity)||slots[i].StableKey!=_settledSlots[i].StableKey)return false;
        return true;
    }
    private Func<GenericEventV7ItemCompletion>? _itemCompletion;
    internal GenericEventV7Binding Binding=>_binding;
    internal bool Started=>_resumeSeen;
    internal Task? ResumeTask=>_resumeTask;
    internal bool Owns(GenericEventV7Binding binding)=>_resumeSeen&&ReferenceEquals(binding,_binding);
    internal bool ItemContextValid() {
        var run=RunManager.Instance?.DebugOnlyGetState();
        return _resumeSeen&&!_binding.Failed&&ReferenceEquals(run,_binding.RunState)&&ReferenceEquals(NRun.Instance,_binding.Run)&&
            (ReferenceEquals(run!.CurrentRoom,_eventRoom)||ReferenceEquals(run.CurrentRoom,_room))&&
            ReferenceEquals(_binding.EventModel.Owner,_binding.Player)&&ReferenceEquals(_binding.Player.RunState,run)&&
            ReferenceEquals(_eventRoom!.LocalMutableEvent,_binding.EventModel)&&
            GodotObject.IsInstanceValid(_binding.Run)&&GodotObject.IsInstanceValid(_binding.Map)&&GodotObject.IsInstanceValid(_binding.Overlays)&&
            ReferenceEquals(MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen.Instance,_binding.Map)&&
            ReferenceEquals(_binding.Run.GlobalUi?.Overlays,_binding.Overlays)&&ReferenceEquals(_binding.Run.GlobalUi?.MapScreen,_binding.Map)&&
            !_binding.Map.IsOpen&&!_binding.Map.IsTraveling&&!_binding.Map.IsTravelEnabled&&GenericEventV7Binding.CapstoneReady()&&
            MegaCrit.Sts2.Core.Commands.CardSelectCmd.Selector is null&&
            (_resumeTask is null||!_resumeTask.IsFaulted&&!_resumeTask.IsCanceled)&&
            (_resumedNode is null||ReferenceEquals(NEventRoom.Instance,_resumedNode)&&ReferenceEquals(_binding.Run.EventRoom,_resumedNode)&&
                ReferenceEquals(_binding.EventModel.Node,_resumedNode)&&GodotObject.IsInstanceValid(_resumedNode)&&_resumedNode.CustomEventNode is null);
    }
    internal object ReadItem() {
        if(ResumeStatus()!="item"||_item is null)throw new InvalidOperationException("Resume item unavailable.");
        var value=_item.Read();
        if(value is Sts2AgentBridge.Successors.ItemV1.ItemV1ResolvedResult||value is GenericEventV7ItemSetRead {Status:"resolved"})SettleItem();
        return value;
    }
    internal object ApplyItem(string? decision,string? action) {
        if(ResumeStatus()!="item"||_item is null||_itemResolved)throw new InvalidOperationException("Resume item unavailable.");
        return _item.Apply(decision,action);
    }
    internal void DisposeItem(){_item?.Dispose();_item=null;}

    internal MethodInfo ResumeMethod {
        get {
            var method=_binding.EventModel.GetType().GetMethod("Resume",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,
                null,new[]{typeof(AbstractRoom)},null)??throw new InvalidOperationException("Resume callback unavailable.");
            // Harmony requires the declaration, not an inherited reflected handle.
            return method.DeclaringType!.GetMethod("Resume",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.DeclaredOnly,
                null,new[]{typeof(AbstractRoom)},null)!;
        }
    }
    internal GenericEventV7CombatHandoff(GenericEventV7Binding binding, EncounterModel encounter,
        IReadOnlyList<Reward> rewards, bool resume)
    {
        if(rewards.Count!=0 || encounter is null || !binding.ContextValid(false) ||
            binding.Option.IsProceed || binding.RequestSeen || binding.Item is not null ||
            binding.Offer is not null || binding.Results is not null)
            throw new InvalidOperationException("Unsupported event combat entry.");
        _binding=binding;_encounter=encounter;Resumes=resume;
        if(resume) {
            _eventRoom=RunManager.Instance?.DebugOnlyGetState()?.CurrentRoom as EventRoom;
            if(_eventRoom is null||!ReferenceEquals(_eventRoom.LocalMutableEvent,binding.EventModel)||
                ResumeMethod.IsStatic||ResumeMethod.IsGenericMethod||ResumeMethod.ReturnType!=typeof(Task))
                throw new InvalidOperationException("Exact event resume callback unavailable.");
        }
    }
    internal string Capture()
    {
        if(!Returned || _binding.ChosenTask is null)return "waiting";
        if(_binding.ChosenTask.IsFaulted||_binding.ChosenTask.IsCanceled||_binding.Failed)return "unsupported";
        if(!_binding.ChosenTask.IsCompletedSuccessfully)return "waiting";
        var run=RunManager.Instance?.DebugOnlyGetState();
        var state=CombatManager.Instance?.DebugOnlyGetState();
        if(run is null || !ReferenceEquals(run,_binding.RunState) || !ReferenceEquals(NRun.Instance,_binding.Run))return "unsupported";
        if(run.CurrentRoom is not CombatRoom room || state is null)return "waiting";
        if(!ReferenceEquals(room.Encounter,_encounter)||!ReferenceEquals(room.CombatState,state)||
            !ReferenceEquals(state.Encounter,_encounter)||!ReferenceEquals(state.RunState,run)||
            room.ShouldResumeParentEventAfterCombat!=Resumes||!Equals(room.ParentEventId,_binding.EventModel.Id)||
            state.Players.Count!=1||!ReferenceEquals(state.Players[0],_binding.Player))return "unsupported";
        if(_room is null){
            var node=NCombatRoom.Instance;
            if(node is null)return "waiting";
            _room=room;_state=state;_node=node;
        }
        if(!SameCombat())return "unsupported";
        return CombatManager.Instance!.IsInProgress&&!CombatManager.Instance.IsOverOrEnding?(Resumes?"combat_resume":"combat"):"waiting";
    }
    internal void EnterResume(EventModel model, AbstractRoom room)
    {
        if(!Resumes||_resumeSeen||!ReferenceEquals(model,_binding.EventModel)||!ReferenceEquals(room,_room)||
            _state is null||!ReferenceEquals(RunManager.Instance?.DebugOnlyGetState(),_binding.RunState)||
            !ReferenceEquals(_binding.Player.RunState,_binding.RunState)||!ReferenceEquals(_state.RunState,_binding.RunState)||
            _state.Players.Count!=1||!ReferenceEquals(_state.Players[0],_binding.Player)||!ReferenceEquals(_room!.CombatState,_state)||!ReferenceEquals(_room.Encounter,_encounter)||
            !_room.ShouldResumeParentEventAfterCombat||!Equals(_room.ParentEventId,model.Id))
            throw new InvalidOperationException("Unexpected event resume invocation.");
        _resumeSeen=true;
    }
    internal void CaptureResumeTask(Task task)
    {
        if(!_resumeSeen||task is null||_resumeTask is not null)throw new InvalidOperationException("Resume task replaced.");
        _resumeTask=task;
    }
    internal void FailResume()=>_binding.Failed=true;
    internal string ResumeStatus()
    {
        if(!Resumes||_binding.Failed)return "unsupported";
        var run=RunManager.Instance?.DebugOnlyGetState();
        if(!ReferenceEquals(run,_binding.RunState)||!ReferenceEquals(NRun.Instance,_binding.Run)||
            !ReferenceEquals(_binding.Player.RunState,run)||!ReferenceEquals(_binding.EventModel.Owner,_binding.Player))return "unsupported";
        if(!_resumeSeen) {
            if(SameCombat())return CombatManager.Instance!.IsInProgress&&!CombatManager.Instance.IsOverOrEnding?"combat":"waiting";
            return ReferenceEquals(run!.CurrentRoom,_eventRoom)?"waiting":"unsupported";
        }
        if(_resumeTask is null||_resumeTask.IsFaulted||_resumeTask.IsCanceled)return "unsupported";
        if(!ItemContextValid())return "unsupported";
        if(_binding.Item is {} reward) {
            if(!reward.Overlay()||reward.FailedTask)return "unsupported";
            if(_item is null) {
                if(!reward.Ready)return "waiting";
                if(!reward.Domain()||reward.HasCards)return "unsupported";
                string nodeStatus=NodeStatus();
                if(nodeStatus!="resumed")return nodeStatus;
                if(reward.OfferCount>1) {
                    var adapter=new GenericEventV7ItemSetAdapter(reward);
                    _item=new GenericEventV7ItemSetSession(_binding.Nonce,adapter);
                    _itemCompletion=()=>adapter.CaptureCompletion(reward.OfferCount-1);
                }else {
                    var adapter=new GenericEventV7ItemAdapter(reward);
                    _item=new GenericEventV7ItemChildSession(_binding.Nonce,adapter);_itemCompletion=adapter.CaptureCompletion;
                }
            }
            if(!_itemResolved)return "item";
            // A resolved child remains subject to its inventory/task/context evidence until handoff.
            var completion=_itemCompletion!();
            if(!SettlementValid(completion)||!completion.OwnershipValid||!completion.EffectStillValid||!completion.ScreenClosed||
                completion.Collection?.State!=GenericEventV7ItemTaskState.Succeeded||completion.Offer?.State!=GenericEventV7ItemTaskState.Succeeded||
                completion.Chosen?.State!=GenericEventV7ItemTaskState.Succeeded)return "unsupported";
        } else if(_binding.Overlays.ScreenCount!=0)return "unsupported";
        if(!_resumeTask.IsCompletedSuccessfully)return "waiting";
        if(_binding.Overlays.ScreenCount!=0)return "unsupported";
        return NodeStatus();
    }
    private string NodeStatus() {
        var run=RunManager.Instance?.DebugOnlyGetState();
        var node=NEventRoom.Instance;
        if(!ReferenceEquals(run!.CurrentRoom,_eventRoom))return ReferenceEquals(run.CurrentRoom,_room)?"waiting":"unsupported";
        if(node is null||ReferenceEquals(node,_binding.Room))return "waiting";
        if(node.GetType()!=typeof(NEventRoom)||!GodotObject.IsInstanceValid(node)||!ReferenceEquals(_binding.Run.EventRoom,node)||
            !ReferenceEquals(_binding.EventModel.Node,node)||!ReferenceEquals(_eventRoom!.LocalMutableEvent,_binding.EventModel)||
            !node.IsVisibleInTree()||node.CustomEventNode is not null||!GenericEventV7Binding.CombatLayoutReady(node)||
            !GodotObject.IsInstanceValid(_binding.Run)||!GodotObject.IsInstanceValid(_binding.Map)||!GodotObject.IsInstanceValid(_binding.Overlays)||
            !ReferenceEquals(MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen.Instance,_binding.Map)||
            !ReferenceEquals(_binding.Run.GlobalUi?.Overlays,_binding.Overlays)||!ReferenceEquals(_binding.Run.GlobalUi?.MapScreen,_binding.Map)||
            _binding.Map.IsOpen||_binding.Map.IsTraveling||_binding.Map.IsTravelEnabled)return "unsupported";
        if(_resumedNode is not null&&!ReferenceEquals(_resumedNode,node))return "unsupported";
        _resumedNode=node;return "resumed";
    }
    internal bool SameCombat()
    {
        var run=RunManager.Instance?.DebugOnlyGetState();
        return _room is not null && _state is not null && _node is not null &&
            _node.GetType()==typeof(NCombatRoom)&&GodotObject.IsInstanceValid(_node)&&ReferenceEquals(NCombatRoom.Instance,_node)&&
            ReferenceEquals(typeof(NCombatRoom).GetField("_visuals",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(_node),_room)&& ReferenceEquals(NRun.Instance,_binding.Run)&&
            ReferenceEquals(run,_binding.RunState)&&ReferenceEquals(run!.CurrentRoom,_room)&&
            ReferenceEquals(CombatManager.Instance?.DebugOnlyGetState(),_state)&&
            ReferenceEquals(_room.CombatState,_state)&&ReferenceEquals(_room.Encounter,_encounter)&&
            ReferenceEquals(_state.RunState,run)&&ReferenceEquals(_binding.EventModel.Owner,_binding.Player)&&ReferenceEquals(_binding.Player.RunState,run)&&ReferenceEquals(_state.Encounter,_encounter)&&
            _room.ShouldResumeParentEventAfterCombat==Resumes&&Equals(_room.ParentEventId,_binding.EventModel.Id)&&
            _state.Players.Count==1&&ReferenceEquals(_state.Players[0],_binding.Player);
    }
}
