using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Runs;
namespace Sts2AgentBridge.Items.Native;

// A caller supplies its retained surface certificate. The queued action rechecks
// the exact original belt immediately before the native slot lookup executes.
internal sealed class PinnedPotionDiscard : IDisposable
{
    private static readonly FieldInfo? NetField=typeof(ActionQueueSynchronizer).GetField("_netService",BindingFlags.Instance|BindingFlags.NonPublic);
    internal static bool Eligible(Player player,int slot)=>RunManager.Instance?.ActionQueueSynchronizer is {} queue &&
        NetField?.GetValue(queue) is INetGameService net && (int)net.Type==1 && player.CanRemovePotions &&
        player.MaxPotionCount is >0 and <=8 && player.PotionSlots.Count==player.MaxPotionCount &&
        player.PotionSlots.All(p=>p is not null) && slot>=0 && slot<player.MaxPotionCount &&
        player.PotionSlots[slot] is {} potion && ReferenceEquals(potion.Owner,player) && !potion.IsQueued && !potion.HasBeenRemovedFromState;
    private readonly Player _player;
    private readonly Func<bool> _context;
    private readonly ActionQueueSynchronizer _queue;
    private readonly object _net;
    private readonly PotionModel _target;
    private readonly PotionModel?[] _slots;
    private readonly string?[] _keys;
    private readonly CardModel[] _deck;
    private readonly int[] _levels;
    private readonly string[] _deckKeys,_relicKeys;
    private readonly string?[] _enchantmentKeys;
    private readonly int[] _amounts;
    private readonly object?[] _enchantments;
    private readonly RelicModel[] _relics;
    private readonly DiscardPotionGameAction _action;
    private readonly Task _completion;
    private readonly int _slot,_gold,_hp,_maxHp,_capacity,_thread=Environment.CurrentManagedThreadId;
    private readonly long _deadline=Stopwatch.GetTimestamp()+5*Stopwatch.Frequency;
    private bool _dispatched,_entered,_removed,_disposed;
    private volatile bool _failed;
    internal PinnedPotionDiscard(Player player,int slot,Func<bool> context) {
        if(!Eligible(player,slot)||!context())throw new InvalidOperationException("Discard target unavailable.");
        _player=player;_slot=slot;_context=context;_queue=RunManager.Instance!.ActionQueueSynchronizer;_net=NetField!.GetValue(_queue)!;
        _slots=player.PotionSlots.ToArray();_keys=_slots.Select(p=>p?.Id.Entry).ToArray();_target=_slots[slot]!;
        _deck=player.Deck.Cards.ToArray();_levels=_deck.Select(c=>c.CurrentUpgradeLevel).ToArray();_enchantments=_deck.Select(c=>(object?)c.Enchantment).ToArray();
        _deckKeys=_deck.Select(c=>c.Id.Entry).ToArray();_enchantmentKeys=_deck.Select(c=>c.Enchantment?.Id.Entry).ToArray();_amounts=_deck.Select(c=>c.Enchantment?.Amount??0).ToArray();
        _relics=player.Relics.ToArray();_relicKeys=_relics.Select(r=>r.Id.Entry).ToArray();_gold=player.Gold;_hp=player.Creature.CurrentHp;_maxHp=player.Creature.MaxHp;_capacity=player.MaxPotionCount;
        _action=new(player,(uint)slot,false);_completion=_action.CompletionTask;
    }
    private bool Context()=>!_failed&&!_disposed&&Environment.CurrentManagedThreadId==_thread&&Stopwatch.GetTimestamp()<=_deadline&&_context()&&
        ReferenceEquals(RunManager.Instance?.ActionQueueSynchronizer,_queue)&&ReferenceEquals(NetField?.GetValue(_queue),_net)&&
        _net is INetGameService net&&(int)net.Type==1&&_player.CanRemovePotions&&!_target.IsQueued&&ReferenceEquals(_target.Owner,_player)&&
        MegaCrit.Sts2.Core.Combat.CombatManager.Instance?.IsInProgress==false&&
        _player.Gold==_gold&&_player.Creature.CurrentHp==_hp&&_player.Creature.MaxHp==_maxHp&&_player.MaxPotionCount==_capacity&&
        _player.Deck.Cards.SequenceEqual(_deck,ReferenceEqualityComparer.Instance)&&_player.Relics.SequenceEqual(_relics,ReferenceEqualityComparer.Instance)&&
        _deck.Select((c,i)=>c.Id.Entry==_deckKeys[i]&&c.Enchantment?.Id.Entry==_enchantmentKeys[i]&&(c.Enchantment?.Amount??0)==_amounts[i]&&ReferenceEquals(c.RunState,_player.RunState)&&c.CurrentUpgradeLevel==_levels[i]&&ReferenceEquals(c.Enchantment,_enchantments[i])&&ReferenceEquals(c.Owner,_player)).All(x=>x)&&_relics.Select((r,i)=>ReferenceEquals(r.Owner,_player)&&r.Id.Entry==_relicKeys[i]).All(x=>x);
    private bool Belt(bool removed) {
        var slots=_player.PotionSlots;if(slots.Count!=_slots.Length)return false;
        for(int i=0;i<slots.Count;i++) {
            if(removed&&i==_slot){if(slots[i] is not null)return false;}
            else if(!ReferenceEquals(slots[i],_slots[i])||slots[i]?.Id.Entry!=_keys[i]||slots[i] is {} p&&!ReferenceEquals(p.Owner,_player))return false;
        }
        return true;
    }
    internal void Dispatch() {
        if(_dispatched||!Context()||!Belt(false)||_target.HasBeenRemovedFromState)throw new InvalidOperationException("Stale potion discard.");
        _dispatched=true;_action.BeforeExecuted+=BeforeExecute;
        try{_queue.RequestEnqueue(_action);}catch{_failed=true;throw;}
    }
    private void BeforeExecute(GameAction action) {
        if(!ReferenceEquals(action,_action)||_entered||!Context()||!Belt(false)||_target.HasBeenRemovedFromState){_failed=true;throw new InvalidOperationException("Discard execution changed.");}
        _entered=true;_action.BeforeExecuted-=BeforeExecute;
    }
    internal int Read() {
        if(!_dispatched||!Context()||!ReferenceEquals(_action.CompletionTask,_completion)||_action.Exception is not null||_completion.IsFaulted||_completion.IsCanceled)return Stop();
        bool removed=_entered&&_target.HasBeenRemovedFromState&&Belt(true);
        if(_removed&&!removed||!removed&&(!Belt(false)||_target.HasBeenRemovedFromState))return Stop();
        _removed|=removed;
        if(_completion.IsCompleted)return removed&&(int)_action.State==5?1:Stop();
        return (int)_action.State is >=0 and <=2?0:Stop();
    }
    internal void Abort()=>_failed=true;
    private int Stop(){Abort();return -1;}
    public void Dispose() {
        if(_disposed){if(_failed)throw new InvalidOperationException("Uncertain discard cleanup.");return;}
        bool complete=false;
        try{complete=!_dispatched||Read()==1;}finally{_disposed=true;if(!complete)_failed=true;}
        // Retain the failing BeforeExecuted guard on an unresolved queued action.
        if(_failed)throw new InvalidOperationException("Unresolved native potion discard.");
        _action.BeforeExecuted-=BeforeExecute;
    }
}
