using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Items.Native;
using Sts2AgentBridge.Rooms.Rest;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

internal sealed class PinnedShopEffectDispatch : IShopV1ObservedDispatch
{
    private static readonly AsyncLocal<PinnedShopEffectDispatch?> Scope=new();
    private readonly Harmony _hooks=new("sts.bridge.shop.effect."+Guid.NewGuid().ToString("N"));
    private readonly List<MethodInfo> _targets=new();
    private readonly Player _player;
    private readonly RelicModel _relic;
    private readonly NOverlayStack _overlays;
    private readonly IShopV1NativeDispatch _purchase;
    private readonly Func<bool> _context;
    private readonly int _price,_thread=Environment.CurrentManagedThreadId;
    private readonly PinnedAutomaticRelicEffects.State _before;
    private PinnedAutomaticRelicEffects.State? _expected;
    private PinnedAutomaticRelicEffects? _effects;
    private RestRewardContinuation? _rewards;
    private PublicRewardDecisionSnapshot? _rewardView;
    private Task? _obtained;
    private bool _invoked,_entered,_failed,_disposed,_childPending;
    private int _childRevision;
    private long _deadline;
    internal static IShopV1ObservedDispatch? Create(Player player,RelicModel relic,NOverlayStack overlays,IShopV1NativeDispatch purchase,Func<bool> context,int price) =>
        PinnedAutomaticRelicEffects.Supports(relic)||relic.GetType()==typeof(Cauldron)||relic.GetType()==typeof(Orrery)
            ? new PinnedShopEffectDispatch(player,relic,overlays,purchase,context,price) : null;
    private PinnedShopEffectDispatch(Player player,RelicModel relic,NOverlayStack overlays,IShopV1NativeDispatch purchase,Func<bool> context,int price)
    {_player=player;_relic=relic;_overlays=overlays;_purchase=purchase;_context=context;_price=price;_before=new(player);}
    private bool RewardRelic=>_relic.GetType()==typeof(Cauldron)||_relic.GetType()==typeof(Orrery);
    private bool Owner()=>!_failed&&!_disposed&&Environment.CurrentManagedThreadId==_thread&&_context()&&ReferenceEquals(_player.RunState,_before.Run)&&
        (_deadline==0||Environment.TickCount64<=_deadline);
    public void Invoke()
    {
        Require(!_invoked&&Owner()&&_before.Same(new(_player))&&_price>=0&&_before.Gold>=_price&&_relic.Owner is null&&_overlays.ScreenCount==0&&Scope.Value is null);
        _invoked=true;_deadline=Environment.TickCount64+60000;
        try {
            Patch(_relic.GetType().GetMethod("AfterObtained",Type.EmptyTypes)!,nameof(ObtainedPrefix),nameof(ObtainedPostfix));
            if(RewardRelic) {
                Patch(typeof(RewardsSet).GetMethod("Offer",Type.EmptyTypes)!,nameof(OfferPrefix),nameof(OfferPostfix));
                Patch(typeof(NRewardsScreen).GetMethod("ShowScreen",new[]{typeof(RewardsSet),typeof(bool),typeof(IRunState)})!,nameof(ScreenPrefix),nameof(ScreenPostfix));
            }
            Scope.Value=this;try{_purchase.Invoke();}finally{Scope.Value=null;}
            Require(!_failed);
        } catch {Abort();throw;}
    }
    private bool PaidInsertion(PinnedAutomaticRelicEffects.State next)=>ReferenceEquals(next.Run,_before.Run)&&next.Gold==_before.Gold-_price&&next.Hp==_before.Hp&&next.MaxHp==_before.MaxHp&&
        next.Deck.SequenceEqual(_before.Deck)&&next.Potions.SequenceEqual(_before.Potions)&&next.Relics.Length==_before.Relics.Length+1&&
        next.Relics.Take(_before.Relics.Length).SequenceEqual(_before.Relics)&&ReferenceEquals(next.Relics[^1].Model,_relic);
    private static void ObtainedPrefix(RelicModel __instance,out PinnedAutomaticRelicEffects? __state)
    {
        __state=null;var s=Scope.Value;if(s is null)return;
        s.Require(s.Owner()&&!s._entered&&ReferenceEquals(__instance,s._relic)&&s.PaidInsertion(new(s._player)));
        s._entered=true;s._expected=new(s._player);
        if(!s.RewardRelic){s._effects=new(s._player,s._relic,s.Owner);__state=s._effects.Enter();}
    }
    private static void ObtainedPostfix(Task __result,PinnedAutomaticRelicEffects? __state)
    {var s=Scope.Value;if(s is null)return;if(!s.RewardRelic)PinnedAutomaticRelicEffects.Exit(__state);s.Require(__result is not null);s._obtained=__result;}
    private static void OfferPrefix(RewardsSet __instance,out PinnedShopEffectDispatch? __state)
    {
        __state=Scope.Value;if(__state is not {} s)return;
        s.Require(s.Owner()&&s._entered&&s.RewardRelic&&s._rewards is null&&s._expected!.Same(new(s._player)));
        s._rewards=new(__instance,s._player,s._overlays,s.Owner,(parent,screen)=>new PinnedRewardAlternatives(parent,screen),player=>new PinnedRewardInventory(player));
    }
    private static void OfferPostfix(Task __result,PinnedShopEffectDispatch? __state)
    {if(__state is {} s){s.Require(__result is not null&&s._rewards is not null);s._rewards!.Offering(__result);}}
    private static void ScreenPrefix(RewardsSet __0,bool __1,IRunState __2,out PinnedShopEffectDispatch? __state)
    {__state=Scope.Value;if(__state is {} s){s.Require(s._rewards is not null);s._rewards!.ScreenEntering(__0,__1,__2);}}
    private static void ScreenPostfix(NRewardsScreen __result,PinnedShopEffectDispatch? __state)
    {if(__state is {} s)s._rewards!.ScreenEntered(__result);}
    public void Advance()
    {
        Require(Owner()&&_invoked&&ExactHooks()&&_obtained?.IsFaulted!=true&&_obtained?.IsCanceled!=true);
        if(_rewards is not null) {
            var view=_rewards.Read();_rewardView=view;
            if(_childPending&&(_rewards.Completed||view.Status==PublicDecisionStatus.Ready&&view.DecisionRevision>_childRevision)) {
                _childPending=false;_expected=new(_player);
            }
            if(!_childPending)Require(_expected!.Same(new(_player)));
        } else if(_effects is not null)Require(_effects.Valid());
        else {
            var now=new PinnedAutomaticRelicEffects.State(_player);
            Require(now.Deck.SequenceEqual(_before.Deck)&&now.Relics.SequenceEqual(_before.Relics)&&now.Potions.SequenceEqual(_before.Potions)&&now.Hp==_before.Hp&&now.MaxHp==_before.MaxHp&&
                (now.Gold==_before.Gold||now.Gold==_before.Gold-_price));
        }
    }
    public ShopRewardView? ReadRewards()
    {
        Advance();if(_rewards is null||_rewardView is not {} view)return null;
        var actions=view.LegalActions.Where(a=>a!="proceed").ToList();if(_rewards.CanDismiss(view))actions.Add("dismiss");
        return new(view.Status==PublicDecisionStatus.Ready,_rewards.Completed,view.DecisionId,view.DecisionRevision,view.ScreenKind,actions);
    }
    public void ApplyReward(string decision,string action)
    {
        var view=ReadRewards();Require(view is {Ready:true,Complete:false}&&view.Decision==decision&&view.Actions.Contains(action)&&!_childPending);
        _childPending=true;_childRevision=view!.Revision;_rewards!.Apply(decision,action);
    }
    public object? RewardSource=>_rewards;
    public bool OwnsForeground=>Owner()&&_rewards is not null&&_overlays.ScreenCount is 1 or 2&&ReferenceEquals(_overlays.Peek(),ActiveScreenContext.Instance.GetCurrentScreen());
    public ShopV1RestockWitness? Restocked=>(_purchase as IShopV1RestockDispatch)?.Restocked;
    public ShopV1Completion Completion {get {
        Advance();var state=_purchase.Completion;if(state!=ShopV1Completion.Succeeded)return state;
        if(!_entered||_obtained is null)return ShopV1Completion.Invalid;
        return _obtained.IsCompletedSuccessfully&&(!RewardRelic||_rewards?.Completed==true&&!_childPending)&&_overlays.ScreenCount==0 ? ShopV1Completion.Succeeded:ShopV1Completion.Pending;
    }}
    public bool Verify(ShopV1PendingProbe probe,ShopV1PendingCapture capture)
    {
        Advance();var now=new PinnedAutomaticRelicEffects.State(_player);
        return ReferenceEquals(probe.PlayerIdentity,_player)&&ReferenceEquals(probe.TargetModelIdentity,_relic)&&probe.DisplayedPrice==_price&&probe.BeforeGold==_before.Gold&&
            capture.Gold==now.Gold&&capture.Deck.Count==now.Deck.Length&&capture.Deck.Select((c,i)=>ReferenceEquals(c.ModelIdentity,now.Deck[i].Model)&&c.StableKey==now.Deck[i].Key&&c.UpgradeLevel==now.Deck[i].Level).All(x=>x)&&
            capture.Relics.Count==now.Relics.Length&&capture.Relics.Select((r,i)=>ReferenceEquals(r.ModelIdentity,now.Relics[i].Model)&&r.StableKey==now.Relics[i].Key).All(x=>x)&&
            capture.PotionSlots.Count==now.Potions.Length&&capture.PotionSlots.Select((p,i)=>ReferenceEquals(p.ModelIdentity,now.Potions[i].Model)&&p.StableKey==now.Potions[i].Key).All(x=>x);
    }
    private void Patch(MethodInfo method,string prefix,string postfix)
    {Require(method is not null&&method.GetMethodBody() is not null&&!(Harmony.GetPatchInfo(method)?.Owners.Any()??false));_targets.Add(method);_hooks.Patch(method,new HarmonyMethod(typeof(PinnedShopEffectDispatch),prefix),new HarmonyMethod(typeof(PinnedShopEffectDispatch),postfix));}
    private bool ExactHooks()=>_targets.All(m=>Harmony.GetPatchInfo(m) is {} p&&p.Owners.Count==1&&p.Owners.Contains(_hooks.Id));
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool condition){if(!condition){Abort();throw new InvalidOperationException("shop_effect_boundary");}}
    public void Abort()=>_failed=true;
    public void Dispose()
    {
        if(_disposed){Require(!_failed);return;}
        bool clean=false;
        try {
            try {clean=!_invoked||Completion==ShopV1Completion.Succeeded;}
            finally {
                _disposed=true;
                try {_rewards?.Dispose();}
                finally {
                    try {_effects?.Dispose();}
                    finally {
                        try {_purchase.Dispose();}
                        finally {_hooks.UnpatchAll(_hooks.Id);Require(!_targets.Any(m=>Harmony.GetPatchInfo(m)?.Owners.Contains(_hooks.Id)==true));}
                    }
                }
            }
            Require(clean);
        } catch {Abort();throw;}
    }
}
