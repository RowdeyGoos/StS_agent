using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2AgentBridge.Adapters.Public;

// Standard terminal reward collection shares the core reward owner. It cannot
// open a standalone item session while that owner's action is pending.
internal sealed class PinnedPublicItemRewardClaim
{
    internal static object? Model(Reward reward) => reward.GetType() == typeof(PotionReward)
        ? ((PotionReward)reward).Potion : reward.GetType() == typeof(RelicReward) ? ((RelicReward)reward).Relic : null;
    internal static string? Key(object? model) => model is PotionModel potion ? potion.Id.Entry : model is RelicModel relic ? relic.Id.Entry : null;
    internal static bool ValidKey(string? key) => key is {Length: >=1 and <=128} && key.All(c=>char.IsAsciiLetterOrDigit(c)||c=='_');
    internal static bool Slots(Player player, out PotionModel?[] slots)
    {
        slots=Array.Empty<PotionModel?>();
        if(player.MaxPotionCount is <0 or >8 || player.PotionSlots.Count!=player.MaxPotionCount)return false;
        slots=player.PotionSlots.ToArray();
        return slots.Where(p=>p is not null).All(p=>ValidKey(Key(p))) && slots.Where(p=>p is not null).Distinct(ReferenceEqualityComparer.Instance).Count()==slots.Count(p=>p is not null);
    }
    internal static int CapacityGain(Reward reward)=>Sts2AgentBridge.Items.Native.PinnedPotionCapacity.Gain(Model(reward));
    internal int PotionCapacityGain {get;}
    internal int ResultCapacity=>_potions.Length+PotionCapacityGain;
    private int _settledCapacity;
    private readonly Reward _reward;
    private readonly Player _player;
    private readonly object _run, _node, _model;
    private readonly string _key;
    private readonly PotionModel?[] _potions;
    private readonly string?[] _potionKeys;
    private readonly RelicModel[] _relics;
    private readonly string[] _relicKeys;
    private readonly (CardModel Card,string Key,int Level,object? Enchantment,int Amount)[] _deck;
    private int _settledSlot=-1;
    internal PinnedPublicItemRewardClaim(Reward reward)
    {
        _reward=reward;_player=reward.Player;_run=_player.RunState;
        _node=NRun.Instance??throw new InvalidOperationException("Item reward run unavailable.");
        _model=Model(reward)??throw new InvalidOperationException("Item reward unpopulated.");
        _key=Key(_model)!;PotionCapacityGain=CapacityGain(reward);
        if(_model is RelicModel {Owner:not null})throw new InvalidOperationException("Offered relic already owned.");
        if(!ValidKey(_key)||!Slots(_player,out _potions)||_player.Relics.Count>512||_player.Deck.Cards.Count>512)
            throw new InvalidOperationException("Item reward baseline unavailable.");
        _potionKeys=_potions.Select(Key).ToArray();_relics=_player.Relics.ToArray();_relicKeys=_relics.Select(r=>r.Id.Entry).ToArray();
        if(_potions.Any(p=>ReferenceEquals(p,_model))||_relics.Any(r=>ReferenceEquals(r,_model))||
            _relics.Distinct(ReferenceEqualityComparer.Instance).Count()!=_relics.Length||_relicKeys.Any(k=>!ValidKey(k)))
            throw new InvalidOperationException("Item reward already owned or inventory invalid.");
        _deck=_player.Deck.Cards.Select(c=>(c,c.Id.Entry,c.CurrentUpgradeLevel,(object?)c.Enchantment,c.Enchantment?.Amount??0)).ToArray();
        if(!Valid(false))throw new InvalidOperationException("Item reward ownership unavailable.");
    }
    internal bool HasCapacity => _model is PotionModel ? _potions.Any(p=>p is null) : ResultCapacity<=8;
    private bool Identity() => ReferenceEquals(NRun.Instance,_node)&&ReferenceEquals(RunManager.Instance?.DebugOnlyGetState(),_run)&&
        ReferenceEquals(_player.RunState,_run)&&ReferenceEquals(_reward.Player,_player)&&ReferenceEquals(Model(_reward),_model)&&Key(_model)==_key&&
        _reward.ParentRewardSet is null&&CardSelectCmd.Selector is null&&CapacityGain(_reward)==PotionCapacityGain&&
        (_model is not RelicModel relic||relic.Owner is null||ReferenceEquals(relic.Owner,_player));
    private object? Claimed => _reward is PotionReward p?p.ClaimedPotion:((RelicReward)_reward).ClaimedRelic;
    internal bool Valid(bool inserted, int discardedSlot = -1)
    {
        if(!Identity()||!Slots(_player,out var potions)||potions.Length!=_potions.Length+(inserted?PotionCapacityGain:0)||_player.Deck.Cards.Count!=_deck.Length)return false;
        for(int i=0;i<_deck.Length;i++) {
            var old=_deck[i];var card=_player.Deck.Cards[i];
            if(!ReferenceEquals(card,old.Card)||card.Id.Entry!=old.Key||card.CurrentUpgradeLevel!=old.Level||
                !ReferenceEquals(card.Enchantment,old.Enchantment)||(card.Enchantment?.Amount??0)!=old.Amount||
                !ReferenceEquals(card.Owner,_player)||!ReferenceEquals(card.RunState,_run))return false;
        }
        int additions=0;
        if(inserted&&potions.Skip(_potions.Length).Any(p=>p is not null))return false;
        for(int i=0;i<_potions.Length;i++) {
            if(i==discardedSlot && _potions[i] is not null && potions[i] is null)continue;
            if(i==discardedSlot)return false;
            if(inserted&&_model is PotionModel&&_potions[i] is null&&ReferenceEquals(potions[i],_model)&&Key(potions[i])==_key){additions++;continue;}
            if(!ReferenceEquals(potions[i],_potions[i])||Key(potions[i])!=_potionKeys[i])return false;
        }
        if(additions!=(inserted&&_model is PotionModel?1:0))return false;
        var relics=_player.Relics;
        if(relics.Count!=_relics.Length+(inserted&&_model is RelicModel?1:0))return false;
        int index=0,granted=0;
        foreach(var relic in relics) {
            if(inserted&&ReferenceEquals(relic,_model)){if(!ReferenceEquals(relic.Owner,_player))return false;granted++;continue;}
            if(index>=_relics.Length||!ReferenceEquals(relic,_relics[index])||relic.Id.Entry!=_relicKeys[index]||!ReferenceEquals(relic.Owner,_player))return false;
            index++;
        }
        return index==_relics.Length&&granted==(inserted&&_model is RelicModel?1:0);
    }
    internal bool UnclaimedAfterDiscard(int slot) => !_reward.SuccessfullySelected && Claimed is null && Valid(false,slot);
    internal bool Unclaimed => !_reward.SuccessfullySelected && Claimed is null && Valid(false);
    internal bool Completed => _reward.SuccessfullySelected&&ReferenceEquals(Claimed,_model)&&Valid(true);
    internal void Settle()
    {
        if(!Completed)throw new InvalidOperationException("Item reward not reconciled.");
        _settledCapacity=_player.MaxPotionCount;
        if(_model is PotionModel)_settledSlot=Array.FindIndex(_player.PotionSlots.ToArray(),p=>ReferenceEquals(p,_model));
    }
    internal void AcceptCapacity(int capacity) { _settledCapacity=capacity; }
    internal bool SettledValid(int pendingCapacity=-1) => Identity()&&_reward.SuccessfullySelected&&ReferenceEquals(Claimed,_model)&&
        (_player.MaxPotionCount==_settledCapacity||_player.MaxPotionCount==pendingCapacity)&&_player.PotionSlots.Count==_player.MaxPotionCount&&
        (_model is PotionModel ?
            _settledSlot>=0&&ReferenceEquals(_player.PotionSlots[_settledSlot],_model) :
            _player.Relics.Count(r=>ReferenceEquals(r,_model))==1&&ReferenceEquals(((RelicModel)_model).Owner,_player));
}
