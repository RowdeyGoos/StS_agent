using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Items.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed partial class GenericEventCompoundRewards
{
    private static bool AutomaticNeow(RelicModel relic)=>Named(relic,"GoldenPearl","NutritiousOyster","SilkenTress",
        "ArcaneScroll","NeowsTorment","CursedPearl","NeowsTalisman");
    private static bool CardNamed(CardModel card,string name)=>card.GetType().Assembly==typeof(CardModel).Assembly&&
        card.GetType().Namespace=="MegaCrit.Sts2.Core.Models.Cards"&&card.GetType().Name==name;
    // Public native metadata classifies the generated result; it never samples
    // the pool, evaluates a selector predicate or predicts a random outcome.
    private static string? Rarity(CardModel card)=>typeof(CardModel).GetProperty("Rarity")?.GetValue(card)?.ToString();
    private static bool Tagged(CardModel card,string tag)=>typeof(CardModel).GetProperty("Tags")?.GetValue(card) is IEnumerable tags&&
        tags.Cast<object>().Any(t=>t.ToString()==tag);
    private readonly Dictionary<PinnedRelicPickupChain.Frame,AutomaticPickup> _neowAutomatic=new();
    private sealed class AutomaticPickup
    {
        internal readonly GenericEventCompoundRewards Owner;
        internal readonly PinnedRelicPickupChain.Frame Frame;
        internal PinnedAutomaticRelicEffects? Effects;
        internal PinnedCardAddJournal? Adds;
        private readonly (CardModel Card,int Level,bool Upgradable)[] _upgrades;
        private readonly HashSet<CardModel> _upgraded=new(ReferenceEqualityComparer.Instance);
        private bool _cleaned;
        internal AutomaticPickup(GenericEventCompoundRewards owner,PinnedRelicPickupChain.Frame frame)
        {
            Owner=owner;Frame=frame;
            var deck=frame.Before.Deck.Select(c=>c.Model).Where(c=>Rarity(c)=="Basic").ToArray();
            _upgrades=Named(frame.Relic,"NeowsTalisman")?new[]{deck.LastOrDefault(c=>Tagged(c,"Strike")),deck.LastOrDefault(c=>Tagged(c,"Defend"))}
                .Where(c=>c is not null).Cast<CardModel>().Distinct<CardModel>(ReferenceEqualityComparer.Instance).Select(c=>(c,c.CurrentUpgradeLevel,c.IsUpgradable)).ToArray():Array.Empty<(CardModel,int,bool)>();
        }
        internal IDisposable Enter()
        {
            Owner.Require(AutomaticNeow(Frame.Relic));
            var policy=new PinnedAutomaticRelicEffects.CompoundPolicy {
                Authority=()=>ReferenceEquals(Owner.NativePickup,Frame)&&Frame.Certificate is null,
                GainGold=Named(Frame.Relic,"GoldenPearl","CursedPearl"),LoseGold=Named(Frame.Relic,"SilkenTress"),Hp=Named(Frame.Relic,"NutritiousOyster"),
                Added=c=>Adds?.OwnsAddedCard(c)==true,Modifying=()=>Adds?.InModification==true,
                Upgrade=c=>_upgrades.Any(t=>ReferenceEquals(t.Card,c)&&t.Upgradable)&&_upgraded.Add(c),
                BeforeMutation=()=>{if(Adds is not null&&!Adds.InNativeScope&&Adds.Operations.Count>0)Owner.Require(Adds.Completed);}
            };
            Effects=new(Owner._binding.Player,Frame.Relic,Owner.Context,policy);
            if(Named(Frame.Relic,"ArcaneScroll","NeowsTorment","CursedPearl"))
                Adds=new(Owner._binding.Player,Owner.Context,Authorize,Effects.CertifyDeckAppend,Effects.EnterLease);
            // CardFactory may upgrade detached generated options through an
            // Egg before Add. Their first owned inventory boundary is the
            // actual Add input; existing inventory must still match there.
            return Named(Frame.Relic,"ArcaneScroll","NeowsTorment")?new Lease(()=>{}):Effects.EnterLease();
        }
        private bool Authorize(IReadOnlyList<CardModel> cards)
        {
            if(!ReferenceEquals(Owner.NativePickup,Frame)||Adds!.Operations.Count!=0||cards.Count!=1||!Effects!.Valid())return false;
            var card=cards[0];
            return Named(Frame.Relic,"ArcaneScroll")?Rarity(card)=="Rare":Named(Frame.Relic,"NeowsTorment")?CardNamed(card,"NeowsFury"):
                Named(Frame.Relic,"CursedPearl")&&CardNamed(card,"Greed")&&(int)card.Type==5;
        }
        internal bool Valid()
        {
            if(_cleaned)return Frame.Certificate?.Same(new(Owner._binding.Player))==true;
            if(Effects?.Valid()!=true||Adds is not null&&!Adds.Valid())return false;
            if(Frame.AfterTask?.IsCompletedSuccessfully!=true||Frame.ObtainTask?.IsCompletedSuccessfully!=true)return true;
            Owner.Require(Effects.CardEffectsCompleted);
            if(Adds is not null)Owner.Require((Named(Frame.Relic,"ArcaneScroll")&&Adds.Operations.Count==0)||Adds.Operations.Count==1&&Adds.Completed);
            Owner.Require(_upgrades.All(t=>t.Card.CurrentUpgradeLevel==t.Level+(t.Upgradable?1:0)));
            return true;
        }
        internal void Dispose()
        {
            if(_cleaned)return;
            Exception? failure=null;
            try{Adds?.Dispose();}catch(Exception error){failure=error;}
            try{Effects?.Dispose();}catch(Exception error){failure??=error;}
            if(failure is not null)throw new InvalidOperationException("compound_automatic_cleanup",failure);
            _cleaned=true;
        }
    }
}
