using System;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2AgentBridge.Adapters.Public;

// Use the same queue action as the native potion popup. Its slot lookup happens
// after BeforeExecuted, so retain an exact, expiring guard until execution.
internal sealed class PinnedPublicPotionDiscard
{
    private static readonly FieldInfo? NetField=typeof(ActionQueueSynchronizer).GetField("_netService",BindingFlags.Instance|BindingFlags.NonPublic);
    internal static bool SingleplayerQueue() => RunManager.Instance?.ActionQueueSynchronizer is {} queue &&
        NetField?.GetValue(queue) is INetGameService net && (int)net.Type==1;
    private readonly PinnedPublicRewardParentTarget _target;
    private readonly Player _player;
    private readonly PotionModel _potion;
    private readonly PinnedPublicItemRewardClaim _baseline;
    private readonly NRun _run;
    private readonly ActionQueueSynchronizer _queue;
    private readonly object _net;
    private readonly DiscardPotionGameAction _action;
    private readonly Task _completion;
    private readonly int _slot, _thread=System.Environment.CurrentManagedThreadId;
    private readonly Func<double> _clock;
    private readonly double _deadline;
    private readonly PublicRewardPlayerState _public;
    private bool _failed, _entered, _removed, _dispatched;
    internal NRewardsScreen Screen {get;}
    internal PinnedPublicPotionDiscard(PinnedPublicRewardParentTarget target,NRewardsScreen screen,int slot,Func<double>? clock=null)
    {
        _target=target;Screen=screen;_slot=slot;_player=target.Reward.Player;
        _clock=clock??(()=>Stopwatch.GetTimestamp()/(double)Stopwatch.Frequency);_deadline=_clock()+5;
        _run=NRun.Instance??throw new InvalidOperationException("Discard run unavailable.");
        _queue=RunManager.Instance!.ActionQueueSynchronizer;_net=NetField?.GetValue(_queue)??throw new InvalidOperationException("Discard queue unavailable.");
        if(!SingleplayerQueue()||!PinnedPublicItemRewardClaim.Slots(_player,out var slots)||slots.Length==0||slots.Any(p=>p is null)||slot<0||slot>=slots.Length)
            throw new InvalidOperationException("Discard requires a full local inventory.");
        _potion=slots[slot]!;_baseline=new(target.Reward);
        _public=new(_player);_action=new(_player,(uint)slot,false);_completion=_action.CompletionTask;
        if(!BeforeValid())throw new InvalidOperationException("Discard target unavailable.");
    }
    private bool Context() => !_failed&&System.Environment.CurrentManagedThreadId==_thread&&_clock()<=_deadline&&
        ReferenceEquals(NRun.Instance,_run)&&GodotObject.IsInstanceValid(_run)&&GodotObject.IsInstanceValid(Screen)&&Screen.IsVisibleInTree()&&
        _run.GlobalUi.Overlays.ScreenCount==1&&ReferenceEquals(_run.GlobalUi.Overlays.Peek(),Screen)&&!_run.GlobalUi.MapScreen.IsOpen&&
        !_run.GlobalUi.MapScreen.IsTraveling&&CombatManager.Instance?.IsInProgress==false&&
        ReferenceEquals(RunManager.Instance?.ActionQueueSynchronizer,_queue)&&ReferenceEquals(NetField?.GetValue(_queue),_net)&&SingleplayerQueue()&&
        _player.CanRemovePotions&&ReferenceEquals(_potion.Owner,_player)&&!_potion.IsQueued&&_public.Matches(_player)&&
        GodotObject.IsInstanceValid(_target.Button)&&_target.Button.IsVisibleInTree()&&_target.Button.IsEnabled&&
        PinnedPublicRewardDecisionReader.ContainsNode(Screen,_target.Button)&&ReferenceEquals(_target.Button.Reward,_target.Reward);
    private bool BeforeValid()=>Context()&&!_potion.HasBeenRemovedFromState&&_baseline.Unclaimed;
    internal void Dispatch()
    {
        if(_dispatched||!BeforeValid())throw new InvalidOperationException("Stale discard.");
        _dispatched=true;_action.BeforeExecuted+=BeforeExecute;
        try{_queue.RequestEnqueue(_action);}catch{_failed=true;throw;}
    }
    private void BeforeExecute(GameAction action)
    {
        if(!ReferenceEquals(action,_action)||_entered||!BeforeValid()) {
            _failed=true;throw new InvalidOperationException("Discard execution identity changed.");
        }
        _entered=true;
        _action.BeforeExecuted-=BeforeExecute;
    }
    // -1: fail closed, 0: waiting, 1: exact native removal completed.
    internal int Read()
    {
        if(!_dispatched||!Context()||!ReferenceEquals(_action.CompletionTask,_completion)||_action.Exception is not null||_completion.IsFaulted||_completion.IsCanceled)return Stop();
        bool removed=_entered&&_potion.HasBeenRemovedFromState&&_baseline.UnclaimedAfterDiscard(_slot);
        if(_removed&&!removed)return Stop();
        if(!removed&&!BeforeValid())return Stop();
        _removed|=removed;
        if(_completion.IsCompleted)return removed&&(int)_action.State==5?1:Stop();
        // Waiting/Executing only. Paused selectors and cancellation are unsupported.
        return (int)_action.State is >=0 and <=2?0:Stop();
    }
    internal void Abort()=>_failed=true;
    private int Stop(){Abort();return -1;}
    private readonly record struct PublicRewardPlayerState(int Hp,int MaxHp,int Gold,int DeckCount)
    {
        internal PublicRewardPlayerState(Player player):this(player.Creature.CurrentHp,player.Creature.MaxHp,player.Gold,player.Deck.Cards.Count){}
        internal bool Matches(Player p)=>p.Creature.CurrentHp==Hp&&p.Creature.MaxHp==MaxHp&&p.Gold==Gold&&p.Deck.Cards.Count==DeckCount;
    }
}
