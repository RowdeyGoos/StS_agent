using System;
using System.Linq;
using System.Threading.Tasks;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
namespace MegaCrit.Sts2.Core.Models.Relics {
    public sealed class DollysMirror:RelicModel {
        public DollysMirror(){Id.Entry="DOLLYS_MIRROR";}
        private bool Filter(CardModel card)=>card.Type!=6;
        [MethodImpl(MethodImplOptions.NoInlining)]
        public override async Task AfterObtained(){var cards=await CardSelectCmd.FromDeckGeneric(Owner!,new CardSelectorPrefs(1,1),Filter);var original=cards.FirstOrDefault();if(original is not null)Owner!.Deck.Cards.Add(((MegaCrit.Sts2.Core.Runs.RunState)Owner.RunState).CloneCard(original));}
    }
    internal static class FixtureEnchantPickup {
        internal static async Task Apply(RelicModel relic,string key,int maximum,int amount){
            var effect=new EnchantmentModel();effect.Id.Entry=key;
            var prefs=new CardSelectorPrefs(maximum==1?1:0,maximum){Cancelable=false,RequireManualConfirmation=maximum>1};
            var cards=await CardSelectCmd.FromDeckForEnchantment(relic.Owner!.Deck.Cards.Where(c=>effect.CanEnchant(c)).ToArray(),effect,amount,prefs);
            foreach(var card in cards){var enchantment=new EnchantmentModel{Card=card,Amount=amount};enchantment.Id.Entry=key;card.Enchantment=enchantment;}
        }
    }
    public sealed class GnarledHammer:RelicModel {[MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained()=>FixtureEnchantPickup.Apply(this,"SHARP",3,3);}
    public sealed class Kifuda:RelicModel {[MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained()=>FixtureEnchantPickup.Apply(this,"ADROIT",3,3);}
    public sealed class PunchDagger:RelicModel {[MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained()=>FixtureEnchantPickup.Apply(this,"MOMENTUM",1,5);}
    public sealed class RoyalStamp:RelicModel {[MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained()=>FixtureEnchantPickup.Apply(this,"ROYALLY_APPROVED",1,1);}
}
namespace MegaCrit.Sts2.Core.Models.Potions {
    public sealed class FoulPotion:PotionModel {
        public bool Legal=true;
        public bool PassesCustomUsabilityCheck=>Legal;
        public FoulPotion(){Id.Entry="FOUL_POTION";}
        internal Task Use()=>((MegaCrit.Sts2.Core.Models.Events.FakeMerchant)((MegaCrit.Sts2.Core.Rooms.EventRoom)Owner!.RunState.CurrentRoom!).LocalMutableEvent!).FoulPotionThrown(this);
    }
}
namespace MegaCrit.Sts2.Core.GameActions {
    public class UsePotionAction:GameAction {
        public MegaCrit.Sts2.Core.Entities.Players.Player Player {get;}
        public int PotionIndex {get;}
        public bool WasEnqueuedInCombat=>false;
        public UsePotionAction(PotionModel potion){Player=potion.Owner!;PotionIndex=Player.PotionSlots.IndexOf(potion);}
        [MethodImpl(MethodImplOptions.NoInlining)]
        protected virtual async Task ExecuteAction(){var potion=(MegaCrit.Sts2.Core.Models.Potions.FoulPotion)Player.PotionSlots[PotionIndex]!;Player.PotionSlots[PotionIndex]=null;potion.HasBeenRemovedFromState=true;await potion.Use();}
        public async Task Execute(){Start();try{await ExecuteAction();Finish();}catch(Exception ex){Exception=ex;Completion.TrySetException(ex);}}
    }
}
namespace MegaCrit.Sts2.Core.Models.Encounters {public sealed class FakeMerchantEventEncounter:EncounterModel {}}
