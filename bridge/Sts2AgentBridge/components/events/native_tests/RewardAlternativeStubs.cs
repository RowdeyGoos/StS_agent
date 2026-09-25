using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Models;

namespace MegaCrit.Sts2.Core.Entities.Players {
    public sealed partial class Creature {
        [MethodImpl(MethodImplOptions.NoInlining)]public void SetCurrentHpInternal(decimal amount)=>CurrentHp=(int)amount;
        [MethodImpl(MethodImplOptions.NoInlining)]public void SetMaxHpInternal(decimal amount)=>MaxHp=(int)amount;
    }
    public sealed partial class Player {
        [MethodImpl(MethodImplOptions.NoInlining)]public void AddToMaxPotionCount(int count){for(int i=0;i<count;i++)PotionSlots.Add(null);MaxPotionCount=PotionSlots.Count;}
    }
}
namespace MegaCrit.Sts2.Core.Commands {
    public static partial class CardCmd {
        public static void Upgrade(CardModel card,MegaCrit.Sts2.Core.Nodes.CommonUi.CardPreviewStyle style=default)=>Upgrade(new[]{card},style);
        [MethodImpl(MethodImplOptions.NoInlining)]public static void Upgrade(IEnumerable<CardModel> cards,MegaCrit.Sts2.Core.Nodes.CommonUi.CardPreviewStyle style)
        {foreach(var card in cards)if(card.IsUpgradable)card.UpgradeInternal();}
    }
    public static class RelicCmd {
        [MethodImpl(MethodImplOptions.NoInlining)]public static async Task<RelicModel> Obtain(RelicModel relic,MegaCrit.Sts2.Core.Entities.Players.Player player,int index=-1)
        {relic.Owner=player;player.Relics.Add(relic);await relic.AfterObtained();return relic;}
    }
}
namespace MegaCrit.Sts2.Core.Models.Relics {
    public sealed class PaelsWing:RelicModel {
        public int RewardsSacrificed;
        public RelicModel Grant=new OldCoin();
        public PaelsWing(){Id.Entry="PAELS_WING";DynamicVars["Sacrifices"]=new(){IntValue=2};}
        [MethodImpl(MethodImplOptions.NoInlining)]public async Task OnSacrifice(){RewardsSacrificed++;if(RewardsSacrificed%2==0)await MegaCrit.Sts2.Core.Commands.RelicCmd.Obtain(Grant,Owner!);}
    }
    public sealed class OldCoin:RelicModel {
        public Task Gate=Task.CompletedTask;
        public OldCoin(){Id.Entry="OLD_COIN";}
        [MethodImpl(MethodImplOptions.NoInlining)]public override async Task AfterObtained(){Owner!.Gold+=300;foreach(var fruit in Owner.Relics.OfType<DragonFruit>())await fruit.AfterGoldGained(Owner);await Gate;}
    }
    public sealed class DragonFruit:RelicModel {
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterGoldGained(MegaCrit.Sts2.Core.Entities.Players.Player player){player.Creature.SetMaxHpInternal(player.Creature.MaxHp+1);player.Creature.SetCurrentHpInternal(player.Creature.CurrentHp+1);return Task.CompletedTask;}
    }
    public sealed partial class PotionBelt {
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained(){Owner!.AddToMaxPotionCount(2);return Task.CompletedTask;}
    }
    public sealed class WarPaint:RelicModel {
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained(){foreach(var card in Owner!.Deck.Cards.Take(2))MegaCrit.Sts2.Core.Commands.CardCmd.Upgrade(card);return Task.CompletedTask;}
    }
    public sealed class Whetstone:RelicModel {
        // The native single-card command can be inlined into this caller. Keep
        // the actual enumerable-command -> model-mutation path in the fixture.
        public Whetstone(){Id.Entry="WHETSTONE";}
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained(){foreach(var card in Owner!.Deck.Cards.Where(c=>c.IsUpgradable).Take(2))MegaCrit.Sts2.Core.Commands.CardCmd.Upgrade(new[]{card},default);return Task.CompletedTask;}
    }
    public sealed class Mango:RelicModel {
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained(){Owner!.Creature.SetMaxHpInternal(Owner.Creature.MaxHp+14);Owner.Creature.SetCurrentHpInternal(Owner.Creature.CurrentHp+14);return Task.CompletedTask;}
    }
    public sealed class Pear:RelicModel {}
    public sealed class LeesWaffle:RelicModel {}
    public sealed class BeltBuckle:RelicModel {}
    public sealed class Cauldron:RelicModel {
        public Func<Task> Handler=()=>Task.CompletedTask;
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained()=>Handler();
    }
    public sealed class Orrery:RelicModel {
        public Func<Task> Handler=()=>Task.CompletedTask;
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained()=>Handler();
    }
}
namespace MegaCrit.Sts2.Core.Rewards {
    public partial class CardReward {
        public bool CanReroll;
        public Action? RerollHandler;
        [MethodImpl(MethodImplOptions.NoInlining)]public void Reroll(){CanReroll=false;RerollHandler!();}
        [MethodImpl(MethodImplOptions.NoInlining)]public Task RerollCallback(){Reroll();return Task.CompletedTask;}
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection {
    using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
    using MegaCrit.Sts2.Core.Entities.Cards;
    public partial class NCardRewardSelectionScreen {
        private Godot.Control _rewardAlternativesContainer=new();
        public Godot.Control AlternativeButtons=>_rewardAlternativesContainer;
        public void BindAlternatives(IReadOnlyList<CardCreationResult> cards,IReadOnlyList<CardRewardAlternative> alternatives)
        {
            _options=cards;_extraOptions=alternatives;
            if(!Children.Contains(_rewardAlternativesContainer))Children.Add(_rewardAlternativesContainer);
            _rewardAlternativesContainer.Children.Clear();
            for(int i=0;i<alternatives.Count;i++){int index=i;_rewardAlternativesContainer.Children.Add(new NCardRewardAlternativeButton{Clicked=()=>Complete(_options.Count+index)});}
        }
    }
}
