using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Items.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed partial class GenericEventCompoundRewards
{
    // The request, native pickup, generated models and UI stay with one leaf.
    // Only its mutation observers retire before the parent's next native effect.
    internal sealed class OfferLeaf
    {
        internal readonly GenericEventCompoundRewards Owner;
        internal readonly RewardFrame Reward;
        internal readonly PinnedRelicPickupChain.Frame Pickup;
        internal readonly List<(Receipt Outer,string Decision,string Action)> Inputs=new();
        internal GenericEventV7OfferAdapter Adapter=null!;
        internal GenericEventV7OfferSession Session=null!;
        internal GenericEventV7RewardRead? View;
        internal PinnedAutomaticRelicEffects? Effects;
        internal PinnedCardAddJournal? Adds;
        internal bool Cleaned;
        internal OfferLeaf(GenericEventCompoundRewards owner,RewardFrame reward,PinnedRelicPickupChain.Frame pickup)
        {Owner=owner;Reward=reward;Pickup=pickup;}
        internal void Initialize(object domain,IReadOnlyList<CardModel>[] offers,bool bundle,bool canSkip)
        {
            Adapter=new(Owner._binding.Player,Owner._binding.Overlays,Owner.Context,()=>Pickup.AfterTask,Owner.Fail,
                domain,offers,bundle,canSkip,Owner.Path(Reward).Select(f=>(Control)f.Screen!).ToArray(),DeckProof);
            Effects=new(Owner._binding.Player,Owner.Context,c=>Adds?.OwnsAddedCard(c)==true,()=>Adds?.InModification==true);
            Adds=new(Owner._binding.Player,Owner.Context,Authorize,Effects.CertifyDeckAppend,Effects.EnterLease);
            Session=new(Owner._binding.Nonce,bundle,offers.Length,Adapter,canSkip);
        }
        private bool Hefty=>Named(Pickup.Relic,"HeftyTablet");
        private bool Authorize(IReadOnlyList<CardModel> cards)
        {
            if(!ReferenceEquals(Owner.NativePickup,Pickup)||!Adapter.Submitted||!Effects!.Valid())return false;
            var chosen=Adapter.SelectedOriginals;
            if(Hefty)return Adds!.Operations.Count==0&&cards.Count==chosen.Count+1&&
                cards.Take(chosen.Count).SequenceEqual(chosen,ReferenceEqualityComparer.Instance)&&
                cards[^1].GetType().Assembly==typeof(CardModel).Assembly&&cards[^1].GetType().Namespace=="MegaCrit.Sts2.Core.Models.Cards"&&
                cards[^1].GetType().Name=="Injury"&&(int)cards[^1].Type==5;
            int next=Adds!.Operations.Count;
            return cards.Count==1&&next<chosen.Count&&ReferenceEquals(cards[0],chosen[next]);
        }
        private bool DeckProof(bool complete)
        {
            if(Cleaned)return Adapter.EffectCertified;
            if(Adds is null||Effects is null||!Adds.Valid()||!Effects.Valid())return false;
            if(!complete)return true;
            int expected=Adapter.SelectedOriginals.Count+(Hefty?1:0);
            return Adapter.Submitted&&Adds.Operations.Sum(o=>o.Entries.Length)==expected&&
                (expected==0||Adds.Completed)&&Effects.CardEffectsCompleted;
        }
        internal bool Validate()
        {
            if(Adapter.EffectCertified)return Cleaned||DeckProof(true);
            if(!DeckProof(false))return false;
            if(Pickup.AfterTask?.IsCompletedSuccessfully==true&&Pickup.ObtainTask?.IsCompletedSuccessfully==true) {
                Adapter.CertifyNativeEffect();Owner._expected[Pickup]=new(Owner._binding.Player);
            }
            return true;
        }
        internal void CleanupEffects()
        {
            if(Cleaned)return;
            Owner.Require(Adapter.EffectCertified&&DeckProof(true));
            DisposeEffects();Cleaned=true;
        }
        internal void DisposeEffects()
        {
            Exception? failure=null;
            try{Adds?.Dispose();}catch(Exception error){failure=error;}
            try{Effects?.Dispose();}catch(Exception error){failure??=error;}
            if(failure is not null)throw new InvalidOperationException("compound_offer_effect_cleanup",failure);
        }
        internal void Read()
        {
            Owner.Require(Session is not null);
            if(!Adapter.EffectCertified&&Pickup.AfterTask?.IsCompletedSuccessfully==true&&Pickup.ObtainTask?.IsCompletedSuccessfully==true)
                Owner.Require(Pickup.Owner.TryCertify(Pickup));
            View=Session.Read();Owner.Require(View.Status!="unsupported"&&View.PriorResults.Count<=Inputs.Count);
            for(int i=0;i<View.PriorResults.Count;i++) {
                var result=View.PriorResults[i];var input=Inputs[i];
                Owner.Require(result.DecisionId==input.Decision&&result.ActionId==input.Action&&result.Result is "previewed" or "collected" or "skipped");
                input.Outer.Done=true;
            }
        }
    }
    private readonly List<OfferLeaf> _offers=new();
    private OfferLeaf? _publishedOffer;
    private static bool OfferRelic(RelicModel relic)=>Named(relic,"LeadPaperweight","MassiveScroll","HeftyTablet","ScrollBoxes");
    internal OfferLeaf EnterCardOffer(Player player,object domain,bool bundle,bool canSkip,bool legal)
    {
        var pickup=NativePickup;var reward=CurrentFrame();
        Require(legal&&ReferenceEquals(player,_binding.Player)&&pickup is not null&&OfferRelic(pickup.Relic)&&
            (bundle?Named(pickup!.Relic,"ScrollBoxes")&&!canSkip:!Named(pickup!.Relic,"ScrollBoxes")&&canSkip)&&
            reward.Pending is not null&&reward.Screen is not null&&_offers.Count<5&&_offers.All(o=>!ReferenceEquals(o.Pickup,pickup)));
        BeforePickupAdvance(pickup!);Require(Expected(pickup!).Same(new(_binding.Player)));
        IReadOnlyList<CardModel>[] offers;
        if(bundle){Require(domain is IReadOnlyList<IReadOnlyList<CardModel>> lists&&lists.Count is >=1 and <=5&&lists.All(o=>o is not null&&o.Count is >=1 and <=8));offers=((IReadOnlyList<IReadOnlyList<CardModel>>)domain).ToArray();}
        else {Require(domain is IReadOnlyList<CardModel> cards&&cards.Count is >=1 and <=3);offers=((IReadOnlyList<CardModel>)domain).Select(c=>(IReadOnlyList<CardModel>)new[]{c}).ToArray();}
        var leaf=new OfferLeaf(this,reward,pickup!);_offers.Add(leaf);leaf.Initialize(domain,offers,bundle,canSkip);return leaf;
    }
    internal OfferLeaf CardOfferScreen(object domain,bool bundle,bool canSkip)
    {
        var leaf=_offers.LastOrDefault();Require(Context()&&leaf is not null&&ReferenceEquals(leaf.Pickup,NativePickup)&&
            ReferenceEquals(leaf.Reward,CurrentFrame())&&leaf.Adapter.Bundle==bundle);
        leaf!.Adapter.EnterScreen(domain,canSkip);return leaf;
    }
    private void ReadOffers(){foreach(var leaf in _offers)leaf.Read();}
    private GenericEventV7RewardRead? ReadLeaf()
    {
        var leaf=_offers.LastOrDefault(o=>o.View?.Status!="resolved");if(leaf is null)return ReadDeckLeaf();
        Require(leaf.View is not null);if(leaf.View.Status=="waiting")return Value("waiting","waiting");
        Require(leaf.View.Status=="ready");Publish(leaf.Reward,"offer:"+_offers.IndexOf(leaf)+":"+leaf.View.DecisionId);_publishedOffer=leaf;
        return Value("ready",leaf.Adapter.Bundle?(leaf.View.Phase=="preview"?"bundle_preview":"bundle_offer"):"card_offer",leaf.View.LegalActions);
    }
    private bool ApplyLeaf(string decision,string action)
    {
        if(_publishedOffer is not {} leaf)return ApplyDeckLeaf(decision,action);
        Require(leaf.View?.Status=="ready"&&leaf.Reward.Pending is not null);
        var receipt=new Receipt(decision,action,0,leaf.Reward);_receipts.Add(receipt);leaf.Inputs.Add((receipt,leaf.View!.DecisionId,action));
        Native.Value=leaf.Reward;
        try {leaf.Pickup.Owner.InvokeChildInput(leaf.Pickup,()=>Require(leaf.Session.Apply(leaf.View.DecisionId,action).Outcome=="accepted"));}
        finally{Native.Value=null;}
        ReleaseSettledPickups();return true;
    }
    private IEnumerable<IPinnedClosingOverlay> ClosingOffers(RewardFrame frame)=>_offers.Where(o=>o.View?.Status!="resolved"&&o.Adapter is not null&&o.Adapter.EffectCertified&&
        Path(o.Reward).Contains(frame)&&o.Adapter.Screen is {} screen&&!o.Adapter.Ancestors.Closed(screen)).Select(o=>(IPinnedClosingOverlay)o.Adapter);
    private void DisposeOffers()
    {
        Exception? failure=null;
        foreach(var leaf in _offers.AsEnumerable().Reverse()) {
            try{if(!leaf.Cleaned)leaf.DisposeEffects();}catch(Exception error){failure??=error;}
            try{leaf.Session?.Dispose();leaf.Adapter?.Dispose();}catch(Exception error){failure??=error;}
        }
        if(failure is not null)throw new InvalidOperationException("compound_offer_cleanup",failure);
    }
}
