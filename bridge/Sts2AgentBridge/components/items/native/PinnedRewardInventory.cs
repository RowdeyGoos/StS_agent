using System;
using System.Linq;
using MegaCrit.Sts2.Core.Entities.Players;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Items.Native;

// The full producer retains physical inventory across reward decisions. Legacy
// readers retain their original semantics. Mutating item/alternative actions
// already have separate exact native effect proofs in the shared reader.
internal sealed class PinnedRewardInventory : IPinnedRewardInventory
{
    private readonly Player _player;
    private PinnedAutomaticRelicEffects.State _before;
    internal PinnedRewardInventory(Player player){_player=player;_before=new(player);}
    public bool Valid(PinnedPublicRewardPendingMutation? pending)
    {
        var now=new PinnedAutomaticRelicEffects.State(_player);
        if(pending is null)return _before.Same(now);
        if(pending.Kind is PublicRewardActionKind.CollectItem or PublicRewardActionKind.DiscardPotion or
            PublicRewardActionKind.Sacrifice or PublicRewardActionKind.Reroll)return true;
        if(pending.Kind==PublicRewardActionKind.ClaimSpecialCard)
            return ReferenceEquals(now.Run,_before.Run)&&now.Gold==_before.Gold&&now.Hp==_before.Hp&&now.MaxHp==_before.MaxHp&&
                now.Relics.SequenceEqual(_before.Relics)&&now.Potions.SequenceEqual(_before.Potions);
        if(pending.Kind==PublicRewardActionKind.ChooseCard) {
            if(_before.Same(now))return true;
            return ReferenceEquals(now.Run,_before.Run)&&now.Gold==_before.Gold&&now.Hp==_before.Hp&&now.MaxHp==_before.MaxHp&&
                now.Relics.SequenceEqual(_before.Relics)&&now.Potions.SequenceEqual(_before.Potions)&&
                now.Deck.Length==_before.Deck.Length+1&&now.Deck.Take(_before.Deck.Length).SequenceEqual(_before.Deck)&&
                ReferenceEquals(now.Deck[^1].Model,pending.CardTarget?.Model);
        }
        if(pending.Kind==PublicRewardActionKind.ClaimGold)
            return ReferenceEquals(now.Run,_before.Run)&&now.Deck.SequenceEqual(_before.Deck)&&now.Relics.SequenceEqual(_before.Relics)&&now.Potions.SequenceEqual(_before.Potions);
        return _before.Same(now);
    }
    public void Accept()=>_before=new(_player);
}
