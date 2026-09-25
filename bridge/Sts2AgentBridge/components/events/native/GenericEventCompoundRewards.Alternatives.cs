using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using Sts2AgentBridge.Items.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed partial class GenericEventCompoundRewards
{
    private readonly Dictionary<RewardFrame,AlternativePickup> _alternatives=new();
    private sealed class AlternativePickup:IPinnedAlternativePickup
    {
        private static readonly AsyncLocal<AlternativePickup?> Scope=new();
        private readonly GenericEventCompoundRewards _owner;
        private readonly RewardFrame _reward;
        internal readonly PinnedRelicPickupChain.Frame Parent;
        private readonly PinnedAutomaticRelicEffects.State _before;
        private readonly int _children;
        private RelicModel? _relic;
        private bool _entered,_complete,_disposed;
        internal AlternativePickup(GenericEventCompoundRewards owner,RewardFrame reward)
        {
            _owner=owner;_reward=reward;Parent=reward.Pickup!;_before=new(owner._binding.Player);
            owner.Require(owner.Context()&&Parent is not null&&ReferenceEquals(Parent.Owner,owner._chain)&&
                reward.Pending?.Action=="sacrifice"&&!owner._alternatives.ContainsKey(reward));
            _children=Parent.Children.Count;owner._alternatives.Add(reward,this);
        }
        public IDisposable EnterCallback()
        {
            _owner.Require(!_entered&&!_disposed&&_owner.Context()&&Scope.Value is null&&
                ReferenceEquals(Native.Value,_reward)&&_reward.Pending?.Action=="sacrifice"&&
                _before.Same(new(_owner._binding.Player)));
            var continuation=Parent.Owner.EnterChildContinuation(Parent);
            _entered=true;Scope.Value=this;
            return new Lease(()=>{try{continuation.Dispose();}finally{Scope.Value=null;}});
        }
        internal bool Allow(RelicModel relic)
        {
            bool allowed=_entered&&!_disposed&&!_complete&&ReferenceEquals(Scope.Value,this)&&
                ReferenceEquals(Native.Value,_reward)&&_reward.Pending?.Action=="sacrifice"&&
                _relic is null&&Parent.Children.Count==_children&&_before.Same(new(_owner._binding.Player))&&
                PinnedAutomaticRelicEffects.Supports(relic);
            if(allowed)_relic=relic;return allowed;
        }
        private PinnedRelicPickupChain.Frame? Child=>Parent.Children.Skip(_children).SingleOrDefault();
        public int CertifiedCapacity {
            get {
                if(!_entered||_disposed||!_owner.Context()||_relic is not PotionBelt||Child is not {} child||
                    !ReferenceEquals(child.Relic,_relic))return -1;
                return (child.Certificate is {} certificate?certificate.Same(new(_owner._binding.Player)):_owner.PickupEffectsValid(child))
                    ?_owner._binding.Player.PotionSlots.Count:-1;
            }
        }
        public bool Complete(bool expectsRelic)
        {
            _owner.Require(_entered&&!_disposed&&_owner.Context()&&Parent.Children.Count==_children+(expectsRelic?1:0));
            if(expectsRelic) {
                var child=Child;
                _owner.Require(child is not null&&ReferenceEquals(child.Relic,_relic)&&_before.Same(child.Before)&&
                    Parent.Owner.TryCertify(child)&&child.Certificate!.Same(new(_owner._binding.Player)));
            } else _owner.Require(_relic is null&&_before.Same(new(_owner._binding.Player)));
            _complete=true;return true;
        }
        public void Dispose()
        {
            if(_disposed){_owner.Require(_complete);return;}_disposed=true;
            _owner._alternatives.Remove(_reward);_owner.Require(_complete);
        }
    }
}
