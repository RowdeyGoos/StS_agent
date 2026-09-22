using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

// The purchase owns AfterObtained and its exact selector. Native code generates
// eligibility/order and applies effects; the bounded policy selects the first
// eligible original deck cards, up to the native maximum.
internal sealed class PinnedShopPickupDispatch : IShopV1PickupDispatch,IShopV1RestockDispatch,IShopV1AbortableDispatch
{
    private static readonly AsyncLocal<PinnedShopPickupDispatch?> Scope=new();
    private static PinnedShopPickupDispatch? Active;
    private readonly Player _player;
    private readonly RelicModel _relic;
    private readonly NOverlayStack _overlays;
    private readonly IShopV1NativeDispatch _purchase;
    private readonly Func<bool> _context;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private readonly Harmony _hooks=new("sts.bridge.shop.pickup."+Guid.NewGuid().ToString("N"));
    private readonly List<MethodBase> _targets=new();
    private Snapshot[] _deck=Array.Empty<Snapshot>();
    private CardModel[] _domain=Array.Empty<CardModel>(),_selected=Array.Empty<CardModel>();
    private Task? _obtained;
    private Task<IEnumerable<CardModel>>? _request;
    private PinnedDeckCardChoice? _choice;
    private EnchantmentModel? _enchantment;
    private int _amount,_max,_gold,_hp,_maxHp;
    private CardModel? _clone;
    private volatile bool _failed;
    private bool _invoked,_disposed,_obtainedSeen,_requestSeen,_insideRequest,_screenSeen;
    private long _deadline;
    private sealed record Snapshot(CardModel Model,string Key,int Level,EnchantmentModel? Enchantment,string? EnchantmentKey,decimal Amount);
    internal static bool Supports(RelicModel r)=>r.GetType()==typeof(DollysMirror)||r.GetType()==typeof(GnarledHammer)||r.GetType()==typeof(Kifuda)||r.GetType()==typeof(PunchDagger)||r.GetType()==typeof(RoyalStamp);
    internal PinnedShopPickupDispatch(Player player,RelicModel relic,NOverlayStack overlays,IShopV1NativeDispatch purchase,Func<bool> context)
    {_player=player;_relic=relic;_overlays=overlays;_purchase=purchase;_context=context;}
    private static Snapshot Copy(CardModel c)=>new(c,c.Id.Entry,c.CurrentUpgradeLevel,c.Enchantment,c.Enchantment?.Id.Entry,c.Enchantment?.Amount??0);
    private bool Owner()=>!_failed&&!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&ReferenceEquals(Active,this)&&System.Environment.TickCount64<=_deadline&&_context()&&
        _player.Creature.CurrentHp==_hp&&_player.Creature.MaxHp==_maxHp&&(_player.Gold==_gold||_player.Gold<_gold)&&
        _deck.All(c=>ReferenceEquals(c.Model.Owner,_player)&&ReferenceEquals(c.Model.RunState,_player.RunState));
    public void Invoke() {
        Require(!_invoked&&!_disposed&&Active is null&&Supports(_relic)&&_context()&&_overlays.ScreenCount==0&&CardSelectCmd.Selector is null);
        _invoked=true;_deadline=System.Environment.TickCount64+15000;_gold=_player.Gold;_hp=_player.Creature.CurrentHp;_maxHp=_player.Creature.MaxHp;
        _deck=_player.Deck.Cards.Select(Copy).ToArray();Require(_deck.Length is >=1 and <=64&&_deck.Select(c=>c.Model).Distinct(ReferenceEqualityComparer.Instance).Count()==_deck.Length);
        Active=this;
        try {
            Patch(_relic.GetType().GetMethod("AfterObtained",Type.EmptyTypes)!,nameof(ObtainedPrefix),nameof(ObtainedPostfix));
            Patch(typeof(CardSelectCmd).GetMethod("FromDeckGeneric",new[]{typeof(Player),typeof(CardSelectorPrefs),typeof(Func<CardModel,bool>),typeof(Func<CardModel,int>)})!,nameof(GenericPrefix),nameof(RequestPostfix));
            Patch(typeof(CardSelectCmd).GetMethod("FromDeckForEnchantment",new[]{typeof(IReadOnlyList<CardModel>),typeof(EnchantmentModel),typeof(int),typeof(CardSelectorPrefs)})!,nameof(EnchantPrefix),nameof(RequestPostfix));
            Patch(typeof(NDeckCardSelectScreen).GetMethod("Create",new[]{typeof(IReadOnlyList<CardModel>),typeof(CardSelectorPrefs)})!,nameof(ScreenPrefix),nameof(ScreenPostfix));
            Patch(typeof(NDeckEnchantSelectScreen).GetMethod("ShowScreen",new[]{typeof(IReadOnlyList<CardModel>),typeof(EnchantmentModel),typeof(int),typeof(CardSelectorPrefs)})!,nameof(EnchantScreenPrefix),nameof(ScreenPostfix));
            if(_relic.GetType()==typeof(DollysMirror))Patch(_player.RunState.GetType().GetMethod("CloneCard",new[]{typeof(CardModel)})!,nameof(ClonePrefix),nameof(ClonePostfix));
            var previous=Scope.Value;try{Scope.Value=this;_purchase.Invoke();}finally{Scope.Value=previous;}
            Require(!_failed);
        }catch{Abort();throw;}
    }
    private void Patch(MethodInfo method,string prefix,string postfix) {
        Require(method is not null&&!method.IsGenericMethod&&method.GetMethodBody() is not null);method=method.DeclaringType!.GetMethod(method.Name,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static|BindingFlags.DeclaredOnly,null,method.GetParameters().Select(p=>p.ParameterType).ToArray(),null)!;_targets.Add(method);
        _hooks.Patch(method,prefix:new HarmonyMethod(typeof(PinnedShopPickupDispatch),prefix),postfix:new HarmonyMethod(typeof(PinnedShopPickupDispatch),postfix));
    }
    private static void ObtainedPrefix(RelicModel __instance,out PinnedShopPickupDispatch? __state) {
        __state=Scope.Value;if(__state is not {} s)return;
        s.Require(s.Owner()&&!s._obtainedSeen&&ReferenceEquals(__instance,s._relic)&&ReferenceEquals(__instance.Owner,s._player));s._obtainedSeen=true;
    }
    private static void ObtainedPostfix(Task __result,PinnedShopPickupDispatch? __state){if(__state is {} s)s._obtained=__result;}
    private void Begin(IReadOnlyList<CardModel> cards,CardSelectorPrefs prefs) {
        Require(Owner()&&_obtainedSeen&&!_requestSeen&&prefs.MinSelect>=0&&prefs.MaxSelect is >=1 and <=3&&prefs.MinSelect<=prefs.MaxSelect&&cards.Count<=64&&DeckValid(false));
        _requestSeen=true;_insideRequest=true;_max=prefs.MaxSelect;
        _domain=cards.ToArray();Require(_domain.Distinct(ReferenceEqualityComparer.Instance).Count()==_domain.Length&&_domain.All(c=>_deck.Any(d=>ReferenceEquals(d.Model,c))));
        // Native sorting may vary; policy uses stable original deck order.
        _selected=_deck.Select(d=>d.Model).Where(c=>_domain.Contains(c)).Take(Math.Min(_max,_domain.Length)).ToArray();
    }
    private static void GenericPrefix(Player __0,CardSelectorPrefs __1,Func<CardModel,bool>? __2,Func<CardModel,int>? __3,out PinnedShopPickupDispatch? __state) {
        __state=Scope.Value;if(__state is not {} s)return;
        s.Require(s._relic.GetType()==typeof(DollysMirror)&&ReferenceEquals(__0,s._player)&&__2 is not null&&ReferenceEquals(__2.Target,s._relic)&&__2.Method.Name=="Filter"&&__3 is null&&__1.MinSelect==1&&__1.MaxSelect==1);
        s.Begin(s._player.Deck.Cards.Where(__2!).ToArray(),__1);
    }
    private static void EnchantPrefix(IReadOnlyList<CardModel> __0,EnchantmentModel __1,int __2,CardSelectorPrefs __3,out PinnedShopPickupDispatch? __state) {
        __state=Scope.Value;if(__state is not {} s)return;
        string name=s._relic.GetType().Name;
        string expected=name=="GnarledHammer"?"SHARP":name=="Kifuda"?"ADROIT":name=="PunchDagger"?"MOMENTUM":"ROYALLY_APPROVED";
        s.Require(s._relic.GetType()!=typeof(DollysMirror)&&__1.Id.Entry==expected&&__2 is >=1 and <=100&&ReferenceEquals(__1.CanonicalInstance,__1)&&!__3.Cancelable);
        s._enchantment=__1;s._amount=__2;s.Begin(__0,__3);
        s.Require(s._domain.All(c=>c.Enchantment is null&&__1.CanEnchant(c)));
    }
    private static void RequestPostfix(Task<IEnumerable<CardModel>> __result,PinnedShopPickupDispatch? __state) {
        if(__state is {} s){s._insideRequest=false;s._request=__result;s.Require(__result is not null);}
    }
    private static void ScreenPrefix(IReadOnlyList<CardModel> __0,CardSelectorPrefs __1,out PinnedShopPickupDispatch? __state) {
        __state=Scope.Value;if(__state is not {} s)return;s.ScreenEntering(__0,__1);
    }
    private static void EnchantScreenPrefix(IReadOnlyList<CardModel> __0,EnchantmentModel __1,int __2,CardSelectorPrefs __3,out PinnedShopPickupDispatch? __state) {
        __state=Scope.Value;if(__state is not {} s)return;s.Require(ReferenceEquals(__1,s._enchantment)&&__2==s._amount);s.ScreenEntering(__0,__3);
    }
    private void ScreenEntering(IReadOnlyList<CardModel> cards,CardSelectorPrefs prefs) {
        Require(Owner()&&_insideRequest&&!_screenSeen&&prefs.MaxSelect==_max&&cards.Count==_domain.Length&&cards.All(c=>_domain.Contains(c))&&DeckValid(false));_screenSeen=true;
    }
    private static void ScreenPostfix(Control __result,PinnedShopPickupDispatch? __state) {
        if(__state is {} s){s.Require(s._screenSeen&&s._choice is null&&__result is not null);s._choice=new(__result,s._overlays,s._domain,s._selected,()=>s.Owner()&&s.DeckValid(false),s._enchantment,s._amount,s._max);}
    }
    private static void ClonePrefix(object __instance,CardModel __0,out PinnedShopPickupDispatch? __state) {
        __state=Scope.Value;if(__state is not {} s)return;
        s.Require(s.Owner()&&s._relic.GetType()==typeof(DollysMirror)&&ReferenceEquals(__instance,s._player.RunState)&&s.SelectedExactly()&&s._selected.Length==1&&ReferenceEquals(__0,s._selected[0])&&s._clone is null);
    }
    private static void ClonePostfix(CardModel __result,PinnedShopPickupDispatch? __state) {
        if(__state is {} s){s.Require(__result is not null&&!s._deck.Any(c=>ReferenceEquals(c.Model,__result)));s._clone=__result;}
    }
    private bool SelectedExactly() {
        if(_request?.IsCompletedSuccessfully!=true)return false;
        var result=_request.Result.Take(4).ToArray();
        return result.Length==_selected.Length&&result.Distinct(ReferenceEqualityComparer.Instance).Count()==result.Length&&result.All(c=>_selected.Contains(c))&&(_choice is null||_choice.Completed);
    }
    private bool DeckValid(bool complete) {
        var cards=_player.Deck.Cards;
        bool effectReady=SelectedExactly();
        if(cards.Count!=_deck.Length && !(_clone is not null&&cards.Count==_deck.Length+1&&ReferenceEquals(cards[^1],_clone)))return false;
        for(int i=0;i<_deck.Length;i++) {
            var old=_deck[i];var c=cards[i];if(!ReferenceEquals(c,old.Model)||c.Id.Entry!=old.Key||c.CurrentUpgradeLevel!=old.Level)return false;
            bool same=ReferenceEquals(c.Enchantment,old.Enchantment)&&c.Enchantment?.Id.Entry==old.EnchantmentKey&&(c.Enchantment?.Amount??0)==old.Amount;
            bool changed=effectReady&&_enchantment is not null&&_selected.Contains(c)&&old.Enchantment is null&&c.Enchantment is {} e&&ReferenceEquals(e.Card,c)&&e.Id.Entry==_enchantment.Id.Entry&&e.Amount==_amount;
            if(!same&&!changed||complete&&_enchantment is not null&&_selected.Contains(c)&&!changed)return false;
        }
        if(_clone is {} clone&&cards.Contains(clone)) {
            var original=_deck.Single(c=>ReferenceEquals(c.Model,_selected.Single()));
            if(!effectReady||!ReferenceEquals(clone.Owner,_player)||!ReferenceEquals(clone.RunState,_player.RunState)||clone.Id.Entry!=original.Key||clone.CurrentUpgradeLevel!=original.Level||
                clone.Enchantment?.Id.Entry!=original.EnchantmentKey||(clone.Enchantment?.Amount??0)!=original.Amount||clone.Enchantment is {} e&&(!ReferenceEquals(e.Card,clone)||ReferenceEquals(e,original.Enchantment)))return false;
        }
        return !complete||effectReady&&(_enchantment is not null||_selected.Length==0?cards.Count==_deck.Length:_clone is not null&&cards.Count==_deck.Length+1);
    }
    internal bool OwnsForeground=>_choice?.OwnsForeground==true;
    internal void Advance(){Require(Owner());if(_choice is not null&&!_choice.Completed)_choice.Advance();Require(DeckValid(false));}
    public bool DeckMatches(IReadOnlyList<ShopV1DeckCardBinding> deck,bool complete)=>Owner()&&DeckValid(complete)&&deck.Count==_player.Deck.Cards.Count&&deck.Select((c,i)=>ReferenceEquals(c.ModelIdentity,_player.Deck.Cards[i])&&c.StableKey==_player.Deck.Cards[i].Id.Entry&&c.UpgradeLevel==_player.Deck.Cards[i].CurrentUpgradeLevel).All(x=>x);
    public ShopV1RestockWitness? Restocked=>(_purchase as IShopV1RestockDispatch)?.Restocked;
    public ShopV1Completion Completion {get {
        if(!Owner()||_obtained?.IsFaulted==true||_obtained?.IsCanceled==true||_request?.IsFaulted==true||_request?.IsCanceled==true||!DeckValid(false))return ShopV1Completion.Invalid;
        var purchase=_purchase.Completion;if(purchase!=ShopV1Completion.Succeeded)return purchase;
        if(!_obtainedSeen||_obtained is null||!_requestSeen||_request is null)return ShopV1Completion.Invalid;
        return _obtained?.IsCompletedSuccessfully==true&&SelectedExactly()&&DeckValid(true)&&_overlays.ScreenCount==0?ShopV1Completion.Succeeded:ShopV1Completion.Pending;
    }}
    public void Abort()=>_failed=true;
    public void Dispose() {
        if(_disposed){if(_failed)throw new InvalidOperationException("Pickup cleanup uncertain.");return;}
        try{if(_invoked&&Completion!=ShopV1Completion.Succeeded)throw new InvalidOperationException("Pickup unresolved.");}
        catch{Abort();throw;}
        finally {
            _disposed=true;
            try{_purchase.Dispose();}catch{Abort();throw;}
            finally { try{_hooks.UnpatchAll(_hooks.Id);if(_targets.Any(t=>Harmony.GetPatchInfo(t)?.Owners.Contains(_hooks.Id)==true))throw new InvalidOperationException("Pickup hooks retained.");}
            catch{Abort();throw;}
            finally{if(!_failed&&ReferenceEquals(Active,this))Active=null;} }
        }
    }
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool ok){if(!ok){Abort();throw new InvalidOperationException("Native pickup ownership/effect changed.");}}
}
