using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Runs;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// Observe the native ready -> queued vote -> next-act -> victory chain. Neither
// the dialogue callback nor the vote's completion alone establishes a win.
internal sealed class GenericEventV7Terminal : IDisposable
{
    private const string Owner="sts2agent.generic_event_v7.terminal";
    private static GenericEventV7Terminal? _active;
    private readonly GenericEventV7Binding _binding;
    private readonly RunManager _manager;
    private readonly ActionQueueSynchronizer _queue;
    private readonly object _synchronizer,_room;
    private readonly Harmony _harmony=new(Owner);
    private readonly List<MethodInfo> _methods=new();
    private readonly Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1DeckCard[] _deck;
    private readonly object?[] _potions,_relics;
    private readonly int _gold,_hp,_maxHp,_thread=Environment.CurrentManagedThreadId;
    private readonly long _deadline=Stopwatch.GetTimestamp()+30*Stopwatch.Frequency;
    private GameAction? _vote;
    private Task? _voteCompletion,_executeTask,_nextTask,_winTask;
    private bool _ready=true,_entered,_executing,_nextEntering,_winEntered,_disposed,_cleanupFailed;
    private volatile bool _failed;
    internal GenericEventV7Terminal(GenericEventV7Binding binding,object synchronizer) {
        _binding=binding;_manager=RunManager.Instance!;_queue=_manager.ActionQueueSynchronizer;
        _synchronizer=synchronizer;_room=binding.RunState.CurrentRoom??throw new InvalidOperationException("Terminal room unavailable.");
        if(_active is not null||binding.RequestSeen||!binding.ContextValid(false)||!Context()||!VictoryRoom())throw new InvalidOperationException("Terminal progression unavailable.");
        _deck=GenericEventV7Binding.CopyDeck(binding.Player);_potions=binding.Player.PotionSlots.Cast<object?>().ToArray();_relics=binding.Player.Relics.Cast<object?>().ToArray();
        _gold=binding.Player.Gold;_hp=binding.Player.Creature.CurrentHp;_maxHp=binding.Player.Creature.MaxHp;
        _active=this;
        try {
            var voteType=typeof(GameAction).Assembly.GetType("MegaCrit.Sts2.Core.GameActions.VoteToMoveToNextActAction")??throw new InvalidOperationException("Vote type unavailable.");
            Install(typeof(ActionQueueSynchronizer).GetMethod("RequestEnqueue",new[]{typeof(GameAction)})!,"Enqueue");
            Install(voteType.GetMethod("ExecuteAction",BindingFlags.Instance|BindingFlags.NonPublic)!,"Vote");
            Install(typeof(RunManager).GetMethod("EnterNextAct",Type.EmptyTypes)!,"Next");
            Install(typeof(RunManager).GetMethod("WinRun",BindingFlags.Instance|BindingFlags.NonPublic)!,"Win");
        } catch { _failed=true;Cleanup();throw; }
    }
    private bool VictoryRoom()=>_room.GetType().GetProperty("IsVictoryRoom")?.GetValue(_room) is true;
    private bool Context()=>!_failed&&Environment.CurrentManagedThreadId==_thread&&Stopwatch.GetTimestamp()<=_deadline&&
        ReferenceEquals(RunManager.Instance,_manager)&&ReferenceEquals(_manager.DebugOnlyGetState(),_binding.RunState)&&
        ReferenceEquals(_manager.ActionQueueSynchronizer,_queue)&&ReferenceEquals(_manager.ActChangeSynchronizer,_synchronizer)&&
        (int)_manager.NetService.Type==1&&!_manager.IsAbandoned&&ReferenceEquals(_binding.RunState.CurrentRoom,_room)&&
        ReferenceEquals(_binding.Player.RunState,_binding.RunState)&&ReferenceEquals(_binding.EventModel.Owner,_binding.Player)&&
        ReferenceEquals(MegaCrit.Sts2.Core.Nodes.NRun.Instance,_binding.Run)&&!_binding.Failed && GenericEventV7Hooks.Owns(_binding) && (_active is null || ReferenceEquals(_active,this));
    private bool Inventory() {
        var deck=GenericEventV7Binding.CopyDeck(_binding.Player);
        return _binding.Player.Gold==_gold&&_binding.Player.Creature.MaxHp==_maxHp&&deck.Length==_deck.Length&&
            deck.Select((c,i)=>GenericEventV7Binding.SameDeckCard(c,_deck[i])).All(x=>x)&&
            _binding.Player.PotionSlots.Cast<object?>().SequenceEqual(_potions,ReferenceEqualityComparer.Instance)&&
            _binding.Player.Relics.Cast<object?>().SequenceEqual(_relics,ReferenceEqualityComparer.Instance);
    }
    private void Install(MethodInfo target,string name) {
        if(target is null||target.IsStatic||target.IsGenericMethod||Harmony.GetPatchInfo(target)?.Owners.Count>0)throw new InvalidOperationException("Terminal hook unavailable.");
        _methods.Add(target);
        MethodInfo Hook(string suffix)=>typeof(GenericEventV7Terminal).GetMethod(name+suffix,BindingFlags.Static|BindingFlags.NonPublic)!;
        _harmony.Patch(target,new HarmonyMethod(Hook("Prefix")),new HarmonyMethod(Hook("Postfix")),finalizer:new HarmonyMethod(typeof(GenericEventV7Terminal).GetMethod(nameof(Finalizer),BindingFlags.Static|BindingFlags.NonPublic)!));
    }
    internal void ReadyReturned(){_ready=false;if(_vote is null)_failed=true;}
    internal void Abort()=>_failed=true;
    private static void EnqueuePrefix(ActionQueueSynchronizer __instance,GameAction __0) {
        var t=_active;if(t is null)return;
        try {
            if(!t._ready||!t.Context()||!t.Inventory()||t._vote is not null||!ReferenceEquals(__instance,t._queue)||
                __0.GetType().FullName!="MegaCrit.Sts2.Core.GameActions.VoteToMoveToNextActAction"||
                !ReferenceEquals(__0.GetType().GetField("_player",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(__0),t._binding.Player))throw new InvalidOperationException("Unowned terminal vote.");
            t._vote=__0;t._voteCompletion=__0.CompletionTask;__0.BeforeExecuted+=t.BeforeExecute;
        }catch{t.Abort();throw;}
    }
    private static void EnqueuePostfix(){}
    private void BeforeExecute(GameAction action) {
        if(!ReferenceEquals(action,_vote)||_entered||!Context()||!Inventory()||!_binding.ContextValid(false)||!VictoryRoom()||
            _room is not MegaCrit.Sts2.Core.Rooms.EventRoom eventRoom||!ReferenceEquals(eventRoom.LocalMutableEvent,_binding.EventModel)||
            !ReferenceEquals(_binding.EventModel.Node,_binding.Layout)||_binding.Player.Creature.CurrentHp!=_hp){Abort();throw new InvalidOperationException("Terminal vote expired or changed.");}
        _entered=true;action.BeforeExecuted-=BeforeExecute;
    }
    private static void VotePrefix(GameAction __instance) {
        var t=_active;if(t is null)return;
        if(!ReferenceEquals(t._vote,__instance)||!t._entered||t._executing||!t.Context()||!t.Inventory()){t.Abort();throw new InvalidOperationException("Terminal vote execution changed.");}
        t._executing=true;
    }
    private static void VotePostfix(Task __result) {
        var t=_active;if(t is null)return;
        if(!t._executing||t._executeTask is not null||__result is null||t._nextTask is null||t._winTask is null)t.Abort();
        t._executeTask=__result;t._executing=false;
    }
    private static void NextPrefix(RunManager __instance) {
        var t=_active;if(t is null)return;
        if(!t._executing||t._nextEntering||t._nextTask is not null||!ReferenceEquals(__instance,t._manager)||!t.Context()){t.Abort();throw new InvalidOperationException("Unowned next-act task.");}
        t._nextEntering=true;
    }
    private static void NextPostfix(Task __result) {
        var t=_active;if(t is null)return;
        if(!t._nextEntering||__result is null)t.Abort();t._nextTask=__result;t._nextEntering=false;
    }
    private static void WinPrefix(RunManager __instance) {
        var t=_active;if(t is null)return;
        if(!t._nextEntering||t._winEntered||!ReferenceEquals(__instance,t._manager)||!t.Context()||!t.Inventory()||!t.VictoryRoom()){t.Abort();throw new InvalidOperationException("Unowned native victory.");}
        t._winEntered=true;
    }
    private static void WinPostfix(Task __result) {
        var t=_active;if(t is null)return;
        if(!t._winEntered||t._winTask is not null||__result is null)t.Abort();t._winTask=__result;
    }
    private static void Finalizer(Exception? __exception){if(__exception is not null)_active?.Abort();}
    internal string Capture() {
        if(_disposed||!Context()||!Inventory()||_ready||_vote is null||
            !ReferenceEquals(_vote.CompletionTask,_voteCompletion)||_vote.Exception is not null)return "unsupported";
        if(!_entered)return _voteCompletion is {IsCompleted:false}?"waiting":"unsupported";
        if(!_winEntered)return "unsupported";
        var tasks=new[]{_binding.ChosenTask,_voteCompletion,_executeTask,_nextTask,_winTask};
        if(tasks.Any(t=>t is null||t.IsFaulted||t.IsCanceled))return "unsupported";
        if(tasks.Any(t=>!t!.IsCompletedSuccessfully))return "waiting";
        return (int)_vote.State==5&&_binding.Player.Creature.CurrentHp==0?"run_won":"unsupported";
    }
    private void Cleanup() {
        try {
            foreach(var method in _methods)_harmony.Unpatch(method,HarmonyPatchType.All,Owner);
            if(_methods.Any(m=>Harmony.GetPatchInfo(m)?.Owners.Contains(Owner)==true))throw new InvalidOperationException("Terminal hooks retained.");
            if(ReferenceEquals(_active,this))_active=null;
        } catch {_cleanupFailed=true;Abort();throw;}
    }
    public void Dispose() {
        if(_disposed){if(_cleanupFailed)throw new InvalidOperationException("Uncertain terminal cleanup.");return;}
        bool complete=false;try{complete=Capture()=="run_won";}finally{_disposed=true;if(!complete){Abort();_cleanupFailed=true;}Cleanup();}
        if(!complete)throw new InvalidOperationException("Terminal progression unresolved.");
        _vote!.BeforeExecuted-=BeforeExecute;
    }
}
