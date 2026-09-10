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
// exact non-resuming combat that the owned event requested.
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
        if(_binding.Overlays.ScreenCount!=0||!GenericEventV7Binding.CapstoneReady())return "unsupported";
        if(!_resumeTask.IsCompletedSuccessfully)return "waiting";
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
        return "resumed";
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
