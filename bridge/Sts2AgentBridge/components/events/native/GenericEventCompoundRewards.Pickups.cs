using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Items.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed partial class GenericEventCompoundRewards
{
    private readonly List<PickupEffect> _effects=new();
    private readonly Dictionary<PinnedRelicPickupChain.Frame,PinnedAutomaticRelicEffects.State> _expected=new();
    private readonly Dictionary<PinnedRelicPickupChain.Frame,PinnedAutomaticRelicEffects> _automatic=new();
    private readonly List<PinnedRelicPickupChain> _chains=new();
    private PinnedRelicPickupChain? _chain;
    private PinnedRelicPickupChain.Frame? NativePickup=>_chain?.NativeFrame;
    private static bool Named(RelicModel relic,params string[] names)=>relic.GetType().Assembly==typeof(RelicModel).Assembly&&
        relic.GetType().Namespace=="MegaCrit.Sts2.Core.Models.Relics"&&names.Contains(relic.GetType().Name);
    private bool CanOpenRewards(PinnedRelicPickupChain.Frame frame)=>Named(frame.Relic,"Kaleidoscope","LostCoffer","SmallCapsule")&&
        !_frames.Any(f=>ReferenceEquals(f.Pickup,frame));
    private PinnedAutomaticRelicEffects.State Expected(PinnedRelicPickupChain.Frame frame)=>_expected[frame];
    private IPinnedRelicRewardEffect? Effect(RewardFrame frame,Reward reward)=>reward is RelicReward relic?new PickupEffect(this,frame,relic):null;
    private sealed class PickupEffect:IPinnedRelicRewardEffect
    {
        private readonly GenericEventCompoundRewards _owner;
        internal readonly RewardFrame RewardFrame;
        private readonly RelicReward _reward;
        private readonly RelicModel _relic;
        private readonly PinnedAutomaticRelicEffects.State _before;
        private PinnedRelicPickupChain? _chain;
        private bool _disposed,_settled,_released;
        internal bool Invoked {get;private set;}
        private PinnedRelicPickupChain.Frame? Frame=>_chain?.Frames.SingleOrDefault(f=>ReferenceEquals(f.Relic,_relic));
        internal PickupEffect(GenericEventCompoundRewards owner,RewardFrame frame,RelicReward reward)
        {
            _owner=owner;RewardFrame=frame;_reward=reward;_relic=reward.Relic??throw new InvalidOperationException("compound_reward_unpopulated");_before=new(reward.Player);
            owner.Require(owner.Context()&&_relic is not null&&_relic.Owner is null&&
                (PinnedAutomaticRelicEffects.Supports(_relic)||Named(_relic,"Kaleidoscope","LostCoffer","SmallCapsule")||OfferRelic(_relic)||AutomaticNeow(_relic)||DeckRelic(_relic)||Named(_relic,"LargeCapsule","PhialHolster")));
        }
        public void Invoke(Action input)
        {
            _owner.Require(!Invoked&&!_disposed&&Valid(false)&&ReferenceEquals(_owner.CurrentFrame(),RewardFrame));
            Invoked=true;_owner._effects.Add(this);
            if(RewardFrame.Pickup is {} parent) {
                _chain=_owner._chain;_owner.Require(_chain is not null&&ReferenceEquals(parent.Owner,_chain));
                _chain!.InvokeChildInput(parent,input);
            } else {
                _owner.Require(_owner._chain is null);
                _chain=new(_owner._binding.Player,_relic,_owner.Context,_owner.AllowChild,_owner.EnterPickupEffects,
                    _owner.PickupEffectsValid,_owner.CleanupPickupEffects,_owner.PickupCertified);
                _owner._chain=_chain;_owner._chains.Add(_chain);_chain.Invoke(input);
            }
        }
        public bool Valid(bool inserted)
        {
            if(_disposed||!_owner.Context()||!ReferenceEquals(_reward.Relic,_relic)||!ReferenceEquals(_reward.Player,_before.Player))return false;
            if(!Invoked)return !inserted&&_before.Same(new(_before.Player));
            if(Frame is not {} frame)return !inserted&&_before.Same(new(_before.Player));
            if(!inserted)return false;
            return frame.Certificate is {} certificate?certificate.Same(new(_before.Player)):_owner.PickupEffectsValid(frame);
        }
        public bool Completed=>Invoked&&!_disposed&&Frame is {} frame&&_chain!.TryCertify(frame);
        public bool MatchesPlayer(PublicRewardPlayer before,PublicRewardPlayer after)=>Completed&&Frame?.Certificate is {} certificate&&
            before==new PublicRewardPlayer(_before.Hp,_before.MaxHp,_before.Gold,_before.Deck.Length)&&
            after==new PublicRewardPlayer(certificate.Hp,certificate.MaxHp,certificate.Gold,certificate.Deck.Length);
        public void Dispose()
        {
            if(_disposed){_owner.Require(_settled);return;}
            if(!Invoked){_disposed=true;_settled=true;return;}
            _owner.Require(Completed);
            _settled=true;_disposed=true;
        }
        internal bool Active=>Invoked&&!_disposed;
        internal void Release()
        {
            if(!_disposed||!Invoked||_released||!ReferenceEquals(Frame,_chain!.Root))return;
            _chain.Dispose();_owner.Require(ReferenceEquals(_owner._chain,_chain));_owner._chain=null;_released=true;
        }
    }
    private bool AllowChild(PinnedRelicPickupChain.Frame parent,RelicModel child)
    {
        if(_alternatives.Values.SingleOrDefault(a=>ReferenceEquals(a.Parent,parent)) is {} alternative)return alternative.Allow(child);
        if(Named(parent.Relic,"LargeCapsule"))return PinnedAutomaticRelicEffects.Supports(child);
        if(!Named(parent.Relic,"SmallCapsule"))return false;
        var frame=Native.Value;
        return frame is not null&&ReferenceEquals(frame.Pickup,parent)&&frame.Pending is not null&&
            frame.Controller.Reader?.InteractionSession.Pending?.ParentTarget?.Reward is RelicReward reward&&ReferenceEquals(reward.Relic,child);
    }
    private IDisposable EnterPickupEffects(PinnedRelicPickupChain.Frame frame)
    {
        Require(Context()&&(frame.Parent is null||Expected(frame.Parent).Same(frame.Before)));
        _expected.Add(frame,new(_binding.Player));
        if(Named(frame.Relic,"LargeCapsule")){var capsule=new CapsulePickup(this,frame);_capsules.Add(frame,capsule);return capsule.Enter();}
        if(Named(frame.Relic,"PhialHolster")){var phial=new PhialPickup(this,frame);_phials.Add(frame,phial);return phial.Enter();}
        if(DeckRelic(frame.Relic)){var deck=new DeckLeaf(this,CurrentFrame(),frame);_decks.Add(deck);return deck.Enter();}
        if(AutomaticNeow(frame.Relic)){var automatic=new AutomaticPickup(this,frame);_neowAutomatic.Add(frame,automatic);return automatic.Enter();}
        if(!PinnedAutomaticRelicEffects.Supports(frame.Relic))return new Lease(()=>{});
        var effect=new PinnedAutomaticRelicEffects(_binding.Player,frame.Relic,Context);_automatic.Add(frame,effect);
        var previous=effect.Enter();return new Lease(()=>PinnedAutomaticRelicEffects.Exit(previous));
    }
    private void BeforePickupAdvance(PinnedRelicPickupChain.Frame frame)=>frame.Owner.BeforeAdvance(frame);
    private bool PickupEffectsValid(PinnedRelicPickupChain.Frame frame)=>Context()&&
        (_capsules.TryGetValue(frame,out var capsule)?capsule.Valid():_phials.TryGetValue(frame,out var phial)?phial.Valid():
        _decks.SingleOrDefault(d=>ReferenceEquals(d.Pickup,frame)) is {} deck?deck.Validate():
        _automatic.TryGetValue(frame,out var observer)?observer.Valid():
        _neowAutomatic.TryGetValue(frame,out var automatic)?automatic.Valid():
        _offers.SingleOrDefault(o=>ReferenceEquals(o.Pickup,frame)) is {} offer?offer.Validate():Expected(frame).Same(new(_binding.Player)));
    private void CleanupPickupEffects(PinnedRelicPickupChain.Frame frame)
    {if(_automatic.TryGetValue(frame,out var effect)){effect.Dispose();_automatic.Remove(frame);}
        _offers.SingleOrDefault(o=>ReferenceEquals(o.Pickup,frame))?.CleanupEffects();
        _decks.SingleOrDefault(d=>ReferenceEquals(d.Pickup,frame))?.CleanupEffects();
        if(_neowAutomatic.TryGetValue(frame,out var automatic))automatic.Dispose();
        if(_capsules.TryGetValue(frame,out var capsule))capsule.Dispose();
        if(_phials.TryGetValue(frame,out var phial))phial.Dispose();}
    private void PickupCertified(PinnedRelicPickupChain.Frame frame)
    {if(frame.Parent is {} parent)_expected[parent]=frame.Certificate!;}
    private void AcceptRewardCertificate(PinnedRelicPickupChain.Frame pickup,RewardFrame frame)
    {Require(ReferenceEquals(frame.Pickup,pickup)&&frame.Controller.EffectCertified&&frame.Certificate is not null);_expected[pickup]=frame.Certificate!;}
    private void DisposePickups()
    {
        Exception? failure=null;
        foreach(var chain in _chains)try{chain.Dispose();}catch(Exception error){failure??=error;}
        foreach(var effect in _neowAutomatic.Values)try{effect.Dispose();}catch(Exception error){failure??=error;}
        foreach(var effect in _capsules.Values)try{effect.Dispose();}catch(Exception error){failure??=error;}
        foreach(var effect in _phials.Values)try{effect.Dispose();}catch(Exception error){failure??=error;}
        if(failure is not null)throw new InvalidOperationException("compound_pickup_cleanup",failure);
    }
    private void ReleaseSettledPickups(){foreach(var effect in _effects)effect.Release();}
    private PinnedCardAddJournal? _tailAdds;
    private PinnedAutomaticRelicEffects? _tailEffects;
    private RelicModel? _tailRelic;
    private void PrepareParentTail()
    {
        if(_binding.Option.Relic is not {} relic||!Named(relic,"NeowsBones"))return;
        Require(_tailAdds is null&&Root.Certificate is not null&&ReferenceEquals(relic.Owner,_binding.Player)&&
            _binding.Player.Relics.Count(r=>ReferenceEquals(r,relic))==1&&relic.DynamicVars["Curses"].IntValue==1&&
            Root.Set.DisallowSkipping&&Root.Set.Rewards.Count==2&&Root.Set.Rewards.All(r=>r is RelicReward&&r.SuccessfullySelected));
        _tailRelic=relic;
        _tailEffects=new(_binding.Player,Context,c=>_tailAdds?.OwnsAddedCard(c)==true,()=>_tailAdds?.InModification==true);
        _tailAdds=new(_binding.Player,Context,cards=>
            GenericEventV7Hooks.InChosenScope(_binding)&&ReferenceEquals(_binding.Option.Relic,_tailRelic)&&
            NativePickup is null&&_binding.ChosenTask?.IsCompleted!=true&&_tailEffects.Valid()&&
            _tailAdds!.Operations.Count==0&&cards.Count==1&&(int)cards[0].Type==5,
            _tailEffects.CertifyDeckAppend,_tailEffects.EnterLease);
    }
    private bool ParentTailComplete()
    {
        if(_tailAdds is null){Require(Root.Certificate is {} certificate&&certificate.Same(new(_binding.Player)));return true;}
        Require(ReferenceEquals(_binding.Option.Relic,_tailRelic)&&_tailAdds.Operations.Count==1&&_tailAdds.Completed&&_tailEffects!.CardEffectsCompleted);
        return true;
    }
}
