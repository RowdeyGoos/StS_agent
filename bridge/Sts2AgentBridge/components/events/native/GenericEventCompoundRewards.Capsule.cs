using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Items.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed partial class GenericEventCompoundRewards
{
    private readonly Dictionary<PinnedRelicPickupChain.Frame,CapsulePickup> _capsules=new();
    // Large Capsule's two automatic relics finish before its two card additions.
    // The first real Add is the boundary that certifies and retires the last
    // child observer; no continuation or generated result is manufactured.
    private sealed class CapsulePickup
    {
        internal readonly GenericEventCompoundRewards Owner;
        internal readonly PinnedRelicPickupChain.Frame Frame;
        internal PinnedCardAddJournal? Adds;
        internal PinnedAutomaticRelicEffects? Effects;
        private bool _cleaned;
        internal CapsulePickup(GenericEventCompoundRewards owner,PinnedRelicPickupChain.Frame frame){Owner=owner;Frame=frame;}
        internal IDisposable Enter()
        {
            Owner.Require(Frame.Relic.DynamicVars["Relics"].IntValue==2);
            Adds=new(Owner._binding.Player,Owner.Context,Authorize,(before,after)=>Effects!.CertifyDeckAppend(before,after),()=>Effects!.EnterLease(),Prepare);
            return new Lease(()=>{});
        }
        private void Prepare()
        {
            Owner.Require(ReferenceEquals(Owner.NativePickup,Frame)&&Frame.Children.Count==2);
            if(Effects is not null){Owner.Require(Effects.Valid());return;}
            Owner.BeforePickupAdvance(Frame);
            var certificate=Owner.Expected(Frame);Owner.Require(certificate.Same(new(Owner._binding.Player)));
            Adds!.ContinueFrom(certificate);
            Effects=new(Owner._binding.Player,Owner.Context,c=>Adds.OwnsAddedCard(c),()=>Adds.InModification);
        }
        private bool Authorize(IReadOnlyList<CardModel> cards)=>ReferenceEquals(Owner.NativePickup,Frame)&&Effects!.Valid()&&cards.Count==1&&
            Adds!.Operations.Count<2&&Rarity(cards[0])=="Basic"&&Tagged(cards[0],Adds.Operations.Count==0?"Strike":"Defend");
        internal bool Valid()
        {
            if(_cleaned)return Frame.Certificate?.Same(new(Owner._binding.Player))==true;
            if(Effects is null) {
                if(Frame.AfterTask?.IsCompleted==true)return false;
                var child=Frame.Children.LastOrDefault();
                return child is null?Owner.Expected(Frame).Same(new(Owner._binding.Player)):
                    child.AfterTask?.IsFaulted!=true&&child.AfterTask?.IsCanceled!=true&&child.ObtainTask?.IsFaulted!=true&&child.ObtainTask?.IsCanceled!=true&&
                    (child.Certificate is {} certificate?certificate.Same(new(Owner._binding.Player)):Owner.PickupEffectsValid(child));
            }
            if(!Effects.Valid()||!Adds!.Valid())return false;
            return Frame.AfterTask?.IsCompletedSuccessfully!=true||Frame.ObtainTask?.IsCompletedSuccessfully!=true||
                Frame.Children.Count==2&&Frame.Children.All(c=>c.Certificate is not null)&&Adds.Operations.Count==2&&Adds.Completed&&Effects.CardEffectsCompleted;
        }
        internal void Dispose()
        {
            if(_cleaned)return;
            Exception? failure=null;
            try{Adds?.Dispose();}catch(Exception error){failure=error;}
            try{Effects?.Dispose();}catch(Exception error){failure??=error;}
            if(failure is not null)throw new InvalidOperationException("compound_capsule_cleanup",failure);
            _cleaned=true;
        }
    }
}
