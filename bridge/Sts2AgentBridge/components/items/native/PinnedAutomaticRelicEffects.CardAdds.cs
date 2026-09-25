using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace Sts2AgentBridge.Items.Native;

internal sealed partial class PinnedAutomaticRelicEffects
{
    private readonly Func<CardModel,bool>? _addedCard;
    private readonly Func<bool>? _modifyingCard;
    private static readonly AsyncLocal<CardCallback?> CardSource=new();
    private readonly List<CardCallback> _cardCallbacks=new();
    private sealed class CardCallback
    {
        internal readonly PinnedAutomaticRelicEffects Owner;
        internal readonly RelicModel Relic;
        internal readonly CardModel Card;
        internal Task? Task;
        internal bool Restored;
        internal CardCallback(PinnedAutomaticRelicEffects owner,RelicModel relic,CardModel card){Owner=owner;Relic=relic;Card=card;}
    }
    private sealed class EffectLease : IDisposable
    {
        private Action? _exit;
        internal EffectLease(Action exit)=>_exit=exit;
        public void Dispose(){var exit=_exit;_exit=null;exit?.Invoke();}
    }
    internal IDisposable EnterLease()
    {
        Require(Valid());if(ReferenceEquals(Scope.Value,this))return new EffectLease(()=>{});
        var previous=Enter();return new EffectLease(()=>Exit(previous));
    }
    private static bool Named(RelicModel relic,params string[] names)=>relic.GetType().Assembly==typeof(RelicModel).Assembly&&
        relic.GetType().Namespace=="MegaCrit.Sts2.Core.Models.Relics"&&names.Contains(relic.GetType().Name);
    private bool CardEffect(params string[] names)=>_addedCard is not null&&CardSource.Value is {} callback&&
        ReferenceEquals(callback.Owner,this)&&_addedCard(callback.Card)&&Named(callback.Relic,names);
    private bool CardGoldEffect=>CardEffect("LuckyFysh");
    private bool CardHpEffect=>CardEffect("DarkstonePeriapt","BookOfFiveRings");
    private void PatchCardAddEffects()
    {
        foreach(var method in _expected.Relics.Where(r=>Named(r.Model,"LuckyFysh","DarkstonePeriapt","BookOfFiveRings"))
            .Select(r=>r.Model.GetType().GetMethod("AfterCardChangedPiles",new[]{typeof(CardModel),typeof(PileType),typeof(AbstractModel)})!).Distinct()) {
            Require(method is not null&&method.DeclaringType?.Assembly==typeof(RelicModel).Assembly&&method.ReturnType==typeof(Task)&&
                method.GetMethodBody() is not null&&!(Harmony.GetPatchInfo(method)?.Owners.Any()??false));
            _targets.Add(method);_hooks.Patch(method,new HarmonyMethod(typeof(PinnedAutomaticRelicEffects),nameof(CardPrefix)),
                new HarmonyMethod(typeof(PinnedAutomaticRelicEffects),nameof(CardPostfix)),finalizer:new HarmonyMethod(typeof(PinnedAutomaticRelicEffects),nameof(CardFinalizer)));
        }
    }
    private static void CardPrefix(RelicModel __instance,CardModel __0,PileType __1,AbstractModel? __2,out CardCallback? __state)
    {
        __state=null;var owner=Scope.Value;if(owner?._addedCard is null)return;
        owner.Require(owner.Valid()&&CardSource.Value is null&&owner._cardCallbacks.Count<64&&__2 is null&&
            owner._addedCard(__0)&&ReferenceEquals(__instance.Owner,owner._player)&&owner._expected.Relics.Any(r=>ReferenceEquals(r.Model,__instance))&&
            !owner._cardCallbacks.Any(c=>ReferenceEquals(c.Card,__0)&&ReferenceEquals(c.Relic,__instance)));
        __state=new(owner,__instance,__0);owner._cardCallbacks.Add(__state);CardSource.Value=__state;
    }
    private static void CardPostfix(Task __result,CardCallback? __state)
    {
        if(__state is not {} call)return;
        try{call.Owner.Require(__result is not null&&call.Task is null&&call.Owner.Valid());call.Task=__result;}
        finally{RestoreCard(call);}
    }
    private static void CardFinalizer(Exception? __exception,CardCallback? __state)
    {if(__state is {} call){if(__exception is not null)call.Owner._failed=true;RestoreCard(call);}}
    private static void RestoreCard(CardCallback call){if(!call.Restored){call.Restored=true;CardSource.Value=null;}}
    internal void CertifyDeckAppend(State before,State after)
    {
        Require(_addedCard is not null&&!_failed&&!_disposed&&_owner()&&ExactHooks()&&ReferenceEquals(Scope.Value,this)&&
            _expected.Same(before)&&ReferenceEquals(before.Player,after.Player)&&ReferenceEquals(before.Run,after.Run)&&
            before.Gold==after.Gold&&before.Hp==after.Hp&&before.MaxHp==after.MaxHp&&before.Relics.SequenceEqual(after.Relics)&&before.Potions.SequenceEqual(after.Potions)&&
            after.Deck.Length==before.Deck.Length+1&&after.Deck.Take(before.Deck.Length).SequenceEqual(before.Deck));
        _expected=after;
    }
    // The caller supplies the exact retained selector/transform witness.
    // Scalar and item changes cannot be absorbed by a deck-only certificate.
    internal void CertifyDeck(Func<Card[],Card[],bool> witness)
    {
        var after=new State(_player);var before=_expected;
        Require(!_failed&&!_disposed&&_owner()&&ExactHooks()&&ReferenceEquals(before.Run,after.Run)&&
            before.Gold==after.Gold&&before.Hp==after.Hp&&before.MaxHp==after.MaxHp&&before.Relics.SequenceEqual(after.Relics)&&
            before.Potions.SequenceEqual(after.Potions)&&witness(before.Deck,after.Deck));
        _expected=after;
    }
    internal void CertifyPotions(State before,(PotionModel? Model,string? Key)[] expected)
    {
        var after=new State(_player);
        Require(!_failed&&!_disposed&&_owner()&&ExactHooks()&&ReferenceEquals(Scope.Value,this)&&_expected.Same(before)&&
            ReferenceEquals(before.Run,after.Run)&&before.Gold==after.Gold&&before.Hp==after.Hp&&before.MaxHp==after.MaxHp&&
            before.Relics.SequenceEqual(after.Relics)&&before.Deck.SequenceEqual(after.Deck)&&after.Potions.SequenceEqual(expected));
        _expected=after;
    }
    internal bool CardEffectsCompleted
    {
        get {
            Require(_addedCard is not null&&Valid()&&_cardCallbacks.All(c=>c.Task?.IsFaulted!=true&&c.Task?.IsCanceled!=true));
            return _cardCallbacks.All(c=>c.Task?.IsCompletedSuccessfully==true);
        }
    }
}
