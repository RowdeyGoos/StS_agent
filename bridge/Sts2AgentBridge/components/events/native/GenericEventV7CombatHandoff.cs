using System;
using System.Collections.Generic;
using System.Reflection;
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
    internal GenericEventV7CombatHandoff(GenericEventV7Binding binding, EncounterModel encounter,
        IReadOnlyList<Reward> rewards, bool resume)
    {
        if(resume || rewards.Count!=0 || encounter is null || !binding.ContextValid(false) ||
            binding.Option.IsProceed || binding.RequestSeen || binding.Item is not null ||
            binding.Offer is not null || binding.Results is not null)
            throw new InvalidOperationException("Unsupported event combat entry.");
        _binding=binding;_encounter=encounter;
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
            room.ShouldResumeParentEventAfterCombat||!Equals(room.ParentEventId,_binding.EventModel.Id)||
            state.Players.Count!=1||!ReferenceEquals(state.Players[0],_binding.Player))return "unsupported";
        if(_room is null){
            var node=NCombatRoom.Instance;
            if(node is null)return "waiting";
            _room=room;_state=state;_node=node;
        }
        if(!SameCombat())return "unsupported";
        return CombatManager.Instance!.IsInProgress&&!CombatManager.Instance.IsOverOrEnding?"combat":"waiting";
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
            ReferenceEquals(_state.RunState,run)&&ReferenceEquals(_binding.Player.RunState,run)&&ReferenceEquals(_state.Encounter,_encounter)&&
            !_room.ShouldResumeParentEventAfterCombat&&Equals(_room.ParentEventId,_binding.EventModel.Id)&&
            _state.Players.Count==1&&ReferenceEquals(_state.Players[0],_binding.Player);
    }
}
