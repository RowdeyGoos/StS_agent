using System;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Items.Native;

internal sealed class PinnedRelicRewardEffect : IPinnedRelicRewardEffect
{
    private static readonly AsyncLocal<PinnedRelicRewardEffect?> Scope=new();
    private readonly RelicReward _reward;
    private readonly RelicModel _relic;
    private readonly PinnedAutomaticRelicEffects.State _before;
    private readonly RunManager _manager;
    private readonly NRun _node;
    private readonly object _room;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private readonly Harmony _hooks=new("sts.bridge.reward.relic."+Guid.NewGuid().ToString("N"));
    private readonly MethodInfo _target;
    private PinnedAutomaticRelicEffects? _effects;
    private Task? _effectTask;
    private long _deadline;
    private bool _invoked,_entered,_failed,_disposed;
    internal static IPinnedRelicRewardEffect? Create(Reward reward) => reward is RelicReward relic?new PinnedRelicRewardEffect(relic):null;
    private PinnedRelicRewardEffect(RelicReward reward)
    {
        _reward=reward;_relic=reward.Relic??throw new InvalidOperationException("reward_relic_missing");_before=new(reward.Player);_room=reward.Player.RunState.CurrentRoom!;
        _manager=RunManager.Instance!;_node=NRun.Instance!;_target=_relic.GetType().GetMethod("AfterObtained",Type.EmptyTypes)!;
        Require(PinnedAutomaticRelicEffects.Supports(_relic)&&_relic.Owner is null&&Owner());
    }
    private bool Owner()=>!_failed&&!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&ReferenceEquals(_manager,RunManager.Instance)&&
        ReferenceEquals(_node,NRun.Instance)&&ReferenceEquals(_before.Run,_manager.DebugOnlyGetState())&&ReferenceEquals(_before.Player.RunState,_before.Run)&&
        ReferenceEquals(_before.Player.RunState.CurrentRoom,_room)&&ReferenceEquals(_reward.Player,_before.Player)&&ReferenceEquals(_reward.Relic,_relic)&&
        (_deadline==0||System.Environment.TickCount64<=_deadline);
    public void Invoke(Action input)
    {
        Require(!_invoked&&Valid(false)&&Scope.Value is null&&!(Harmony.GetPatchInfo(_target)?.Owners.Any()??false));
        _invoked=true;_deadline=System.Environment.TickCount64+15000;
        try {
            _hooks.Patch(_target,new HarmonyMethod(typeof(PinnedRelicRewardEffect),nameof(Prefix)),new HarmonyMethod(typeof(PinnedRelicRewardEffect),nameof(Postfix)));
            Scope.Value=this;try{input();}finally{Scope.Value=null;}
            Require(!_failed);
        }catch{_failed=true;throw;}
    }
    private static void Prefix(RelicModel __instance,out PinnedAutomaticRelicEffects? __state)
    {
        __state=null;var s=Scope.Value;if(s is null)return;
        s.Require(s.Owner()&&!s._entered&&ReferenceEquals(__instance,s._relic)&&s._before.AddedRelic(new(s._before.Player),s._relic));
        s._entered=true;s._effects=new(s._before.Player,s._relic,s.Owner);__state=s._effects.Enter();
    }
    private static void Postfix(Task __result,PinnedAutomaticRelicEffects? __state)
    {var s=Scope.Value;if(s is null)return;PinnedAutomaticRelicEffects.Exit(__state);s.Require(__result is not null);s._effectTask=__result;}
    public bool Valid(bool inserted)
    {
        if(!Owner()||_effectTask?.IsFaulted==true||_effectTask?.IsCanceled==true)return false;
        if(!_invoked)return !inserted&&_before.Same(new(_before.Player));
        if(Harmony.GetPatchInfo(_target) is not {} p||p.Owners.Count!=1||!p.Owners.Contains(_hooks.Id))return false;
        if(_effects is not null)return inserted&&_effects.Valid();
        var current=new PinnedAutomaticRelicEffects.State(_before.Player);
        return inserted?_before.AddedRelic(current,_relic):_before.Same(current);
    }
    public bool Completed=>_invoked&&_entered&&_effectTask?.IsCompletedSuccessfully==true&&Valid(true);
    public bool MatchesPlayer(PublicRewardPlayer before,PublicRewardPlayer after)=>Completed&&
        before==new PublicRewardPlayer(_before.Hp,_before.MaxHp,_before.Gold,_before.Deck.Length)&&
        after==new PublicRewardPlayer(_before.Player.Creature.CurrentHp,_before.Player.Creature.MaxHp,_before.Player.Gold,_before.Player.Deck.Cards.Count);
    private void Require(bool value){if(!value){_failed=true;throw new InvalidOperationException("reward_relic_effect");}}
    public void Dispose()
    {
        if(_disposed){Require(!_failed);return;}
        try {
            bool complete=false;
            try {complete=!_invoked||Completed;}
            finally {
                try {_effects?.Dispose();}
                finally {_hooks.UnpatchAll(_hooks.Id);Require(Harmony.GetPatchInfo(_target)?.Owners.Contains(_hooks.Id)!=true);}
            }
            Require(complete);
        }catch{_failed=true;throw;}
        finally{_disposed=true;}
    }
}
