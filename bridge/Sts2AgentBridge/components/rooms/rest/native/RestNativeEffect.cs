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
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;
using Sts2AgentBridge.Adapters.Public;

namespace Sts2AgentBridge.Rooms.Rest;

// Scope follows native async continuations. Only selectors produced inside this
// exact option invocation may receive input; already-open screens are not adopted.
internal sealed class RestNativeEffect : IDisposable
{
    private static RestNativeEffect? Active;
    private static readonly AsyncLocal<RestNativeEffect?> Scope = new();
    private readonly Harmony _harmony = new("sts.bridge.rest.effect." + Guid.NewGuid().ToString("N"));
    private readonly List<(MethodInfo Target, MethodInfo Prefix, MethodInfo Postfix)> _hooks = new();
    private readonly int _thread = System.Environment.CurrentManagedThreadId;
    private readonly RestSiteOption _option;
    private readonly string _action;
    private readonly RestNativeState _before;
    private readonly Player _player;
    private readonly NOverlayStack _overlays;
    private readonly Func<bool> _context;
    private readonly bool _interactive;
    private readonly Func<PinnedPublicRewardParentTarget,NCardRewardSelectionScreen,IPinnedRewardAlternatives>? _alternatives;
    private readonly Func<Player,IPinnedRewardInventory>? _inventory;
    private CardModel[] _chosen = Array.Empty<CardModel>();
    private RestNativeState? _selectorBefore;
    private PinnedDeckCardChoice? _choice;
    internal RestRewardContinuation? Rewards { get; private set; }
    private Task<bool>? _selection;
    private Task<RelicModel>? _obtain;
    private RelicModel? _relic;
    private bool _entered, _screenSeen, _failed, _disposed, _verified, _unresolvedDisposal;
    private readonly List<CardModel> _cloneInputs = new();
    private readonly List<Task<CardPileAddResult>> _insertions = new();

    internal RestNativeEffect(RestSiteOption option, string action, RestNativeState before, NOverlayStack overlays, Func<bool> context, bool interactive = false,
        Func<PinnedPublicRewardParentTarget,NCardRewardSelectionScreen,IPinnedRewardAlternatives>? alternatives=null,Func<Player,IPinnedRewardInventory>? inventory=null)
    { _interactive = interactive; _option = option; _action = action; _before = before; _player = before.Player; _overlays = overlays; _context = context; _alternatives=alternatives;_inventory=inventory; }
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool value) { if (!value) { _failed = true; throw new InvalidOperationException("rest_effect_boundary"); } }
    private bool Context() => !_failed && !_disposed && System.Environment.CurrentManagedThreadId == _thread &&
        ReferenceEquals(Active, this) && ReferenceEquals(_player.RunState, _before.RunState) && _context();
    internal void Install()
    {
        Require(Active is null && _overlays.ScreenCount == 0 && CardSelectCmd.Selector is null && _context());
        Active = this;
        Patch(_option.GetType().GetMethod("OnSelect", Type.EmptyTypes)!, nameof(SelectPrefix), nameof(SelectPostfix));
        if (_action == "heal")
        {
            Require(_interactive);
            Patch(typeof(RewardsSet).GetMethod("Offer", Type.EmptyTypes)!, nameof(OfferPrefix), nameof(OfferPostfix));
            Patch(typeof(NRewardsScreen).GetMethod("ShowScreen", new[] { typeof(RewardsSet), typeof(bool), typeof(IRunState) })!, nameof(RewardScreenPrefix), nameof(RewardScreenPostfix));
        }
        if (_action is "dig" or "hatch")
            Patch(typeof(RelicCmd).GetMethod("Obtain", new[] { typeof(RelicModel), typeof(Player), typeof(int) })!, nameof(ObtainPrefix), nameof(ObtainPostfix));
        if (_action == "clone")
            Patch(typeof(CardPileCmd).GetMethod("Add", new[] { typeof(CardModel), typeof(PileType), typeof(CardPilePosition), typeof(AbstractModel), typeof(bool) })!, nameof(AddPrefix), nameof(AddPostfix));
        if (_action == "dig" || RestV2Session.Kind(_action) == "cook")
        {
            Patch(typeof(NDeckCardSelectScreen).GetMethod("Create", new[] { typeof(IReadOnlyList<CardModel>), typeof(CardSelectorPrefs) })!, nameof(ScreenPrefix), nameof(ScreenPostfix));
            Patch(typeof(NDeckEnchantSelectScreen).GetMethod("ShowScreen", new[] { typeof(IReadOnlyList<CardModel>), typeof(EnchantmentModel), typeof(int), typeof(CardSelectorPrefs) })!, nameof(EnchantPrefix), nameof(ScreenPostfix));
        }
        if (_action == "smith")
        {
            Require(_interactive);
            Patch(typeof(NDeckUpgradeSelectScreen).GetMethod("ShowScreen", new[] { typeof(IReadOnlyList<CardModel>), typeof(CardSelectorPrefs), typeof(IRunState) })!, nameof(UpgradePrefix), nameof(ScreenPostfix));
        }
        Require(ExactHooks());
    }
    private void Patch(MethodInfo target, string prefix, string postfix)
    {
        Require(target is not null && !target.IsGenericMethod && Harmony.GetPatchInfo(target)?.Owners.Count is not > 0);
        var p = typeof(RestNativeEffect).GetMethod(prefix, BindingFlags.Static | BindingFlags.NonPublic)!;
        var q = typeof(RestNativeEffect).GetMethod(postfix, BindingFlags.Static | BindingFlags.NonPublic)!;
        _hooks.Add((target, p, q)); // Own partially installed hooks before patching.
        _harmony.Patch(target, prefix: new HarmonyMethod(p), postfix: new HarmonyMethod(q));
    }
    private bool ExactHooks() => _hooks.All(h => {
        var p = Harmony.GetPatchInfo(h.Target);
        return p is not null && p.Prefixes.Count == 1 && p.Postfixes.Count == 1 && p.Transpilers.Count == 0 && p.Finalizers.Count == 0 &&
            p.Prefixes[0].owner == _harmony.Id && p.Prefixes[0].PatchMethod == h.Prefix && p.Postfixes[0].owner == _harmony.Id && p.Postfixes[0].PatchMethod == h.Postfix;
    });
    private static void SelectPrefix(RestSiteOption __instance, out RestNativeEffect? __state)
    {
        __state = Active;
        if (__state is not {} s) return;
        s.Require(s.Context() && !s._entered && ReferenceEquals(__instance, s._option) && Scope.Value is null);
        s._entered = true; Scope.Value = s;
    }
    private static void SelectPostfix(Task<bool> __result, RestNativeEffect? __state)
    {
        if (__state is not {} s) return;
        Scope.Value = null; s.Require(__result is not null); s._selection = __result;
    }
    private static void OfferPrefix(RewardsSet __instance, out RestNativeEffect? __state)
    {
        __state = Scope.Value;
        if (__state is {} s)
        {
            s.Require(s.Context() && s._action == "heal" && s.Rewards is null);
            s.Rewards = new(__instance, s._player, s._overlays, s.Context,s._alternatives,s._inventory);
        }
    }
    private static void OfferPostfix(Task __result, RestNativeEffect? __state)
    { if (__state is {} s) { s.Require(__result is not null && s.Rewards is not null); s.Rewards!.Offering(__result); } }
    private static void RewardScreenPrefix(RewardsSet __0, bool __1, IRunState __2, out RestNativeEffect? __state)
    { __state = Scope.Value; if (__state is {} s) { s.Require(s.Rewards is not null); s.Rewards!.ScreenEntering(__0, __1, __2); } }
    private static void RewardScreenPostfix(NRewardsScreen __result, RestNativeEffect? __state)
    { if (__state is {} s) s.Rewards!.ScreenEntered(__result); }
    private static void ObtainPrefix(RelicModel __0, Player __1, int __2, out RestNativeEffect? __state)
    {
        __state = Scope.Value;
        if (__state is not {} s) return;
        s.Require(s.Context() && s._entered && s._relic is null && ReferenceEquals(__1, s._player) && __2 == -1 &&
            __0.Owner is null && !s._before.Relics.Contains(__0) && (s._action == "dig" || __0.GetType() == typeof(Byrdpip)));
        s._relic = __0;
    }
    private static void ObtainPostfix(Task<RelicModel> __result, RestNativeEffect? __state)
    { if (__state is {} s) { s.Require(__result is not null); s._obtain = __result; } }
    private static void AddPrefix(CardModel __0, PileType __1, CardPilePosition __2, AbstractModel? __3, bool __4, out RestNativeEffect? __state)
    {
        __state = Scope.Value;
        if (__state is not {} s) return;
        var originals = s._before.Clonable;
        s.Require(s.Context() && s._action == "clone" && s._cloneInputs.Count < originals.Length && s._cloneInputs.Count == s._insertions.Count &&
            (int)__1 == 6 && (int)__2 == 1 && __3 is null && !__4 && !s._before.Deck.Any(c => ReferenceEquals(c.Model, __0)) && !s._cloneInputs.Contains(__0));
        var original = originals[s._cloneInputs.Count];
        s.Require(ReferenceEquals(__0.Owner, s._player) && ReferenceEquals(__0.RunState, s._player.RunState) &&
            __0.Id.Entry == original.Key && __0.CurrentUpgradeLevel == original.Upgrade && __0.Enchantment?.Id.Entry == original.EnchantmentKey &&
            __0.Enchantment?.Amount == original.Amount && !ReferenceEquals(__0.Enchantment, original.Enchantment));
        s._cloneInputs.Add(__0);
    }
    private static void AddPostfix(Task<CardPileAddResult> __result, RestNativeEffect? __state)
    { if (__state is {} s) { s.Require(__result is not null); s._insertions.Add(__result); } }
    private static void ScreenPrefix(IReadOnlyList<CardModel> __0, CardSelectorPrefs __1, out RestNativeEffect? __state)
    {
        __state = Scope.Value; if (__state is {} s) s.Screen(__0, __1, null, 0);
    }
    private static void EnchantPrefix(IReadOnlyList<CardModel> __0, EnchantmentModel __1, int __2, CardSelectorPrefs __3, out RestNativeEffect? __state)
    {
        __state = Scope.Value; if (__state is {} s) s.Screen(__0, __3, __1, __2);
    }
    private static void UpgradePrefix(IReadOnlyList<CardModel> __0, CardSelectorPrefs __1, IRunState __2, out RestNativeEffect? __state)
    {
        __state = Scope.Value;
        if (__state is {} s) { s.Require(ReferenceEquals(__2, s._before.RunState)); s.Screen(__0, __1, null, 0); }
    }
    private CardModel[] _domain = Array.Empty<CardModel>();
    private EnchantmentModel? _enchantment;
    private int _amount, _minimum, _maximum;
    private bool _cancelable;
    private void Screen(IReadOnlyList<CardModel> cards, CardSelectorPrefs prefs, EnchantmentModel? enchantment, int amount)
    {
        Require(Context() && _entered && !_screenSeen && _choice is null && cards.Count is >= 1 and <= 64 &&
            prefs.MinSelect >= 0 && prefs.MaxSelect is >= 1 and <= 3 && prefs.MinSelect <= prefs.MaxSelect && _overlays.ScreenCount == 0);
        _selectorBefore = new(_player);
        _domain = cards.ToArray();
        Require(_domain.Distinct(ReferenceEqualityComparer.Instance).Count() == cards.Count &&
            _domain.All(c => _selectorBefore.Deck.Any(d => ReferenceEquals(d.Model, c))));
        if (RestV2Session.Kind(_action) == "cook")
        {
            Require(_before.Equals(_selectorBefore) && enchantment is null && prefs.MinSelect == 2 && prefs.MaxSelect == 2 && prefs.Cancelable && prefs.RequireManualConfirmation &&
                _domain.Length == _before.Deck.Count(c => c.Removable) && _domain.All(c => c.IsRemovable));
            if (!_interactive)
            {
                var slots = _action.Split(':');
                _chosen = new[] { _before.Deck[int.Parse(slots[1])].Model, _before.Deck[int.Parse(slots[2])].Model };
                Require(_chosen.All(c => _domain.Contains(c)));
            }
        }
        else if (_action == "smith")
        {
            Require(_interactive && _before.Equals(_selectorBefore) && enchantment is null && prefs.MinSelect == 1 && prefs.MaxSelect == 1 &&
                prefs.Cancelable && prefs.RequireManualConfirmation && _domain.Length == _before.Deck.Count(c => c.Model.IsUpgradable) && _domain.All(c => c.IsUpgradable));
        }
        else
        {
            Require(_action == "dig" && _relic is not null && ReferenceEquals(_relic.Owner, _player));
            _chosen = _selectorBefore.Deck.Select(c => c.Model).Where(c => _domain.Contains(c)).Take(Math.Min(cards.Count, prefs.MaxSelect)).ToArray();
        }
        _enchantment = enchantment; _amount = amount; _minimum = prefs.MinSelect; _maximum = prefs.MaxSelect; _cancelable = prefs.Cancelable; _screenSeen = true;
    }
    private static void ScreenPostfix(Control __result, RestNativeEffect? __state)
    {
        if (__state is not {} s) return;
        s.Require(s._screenSeen && s._choice is null && __result is not null);
        Func<bool> context = () => s.Context() && (s._choice?.ConfirmationDispatched == true || s._selectorBefore!.Equals(new RestNativeState(s._player)));
        s._choice = s._interactive
            ? new(__result, s._overlays, s._domain, context, s._enchantment, s._amount, s._minimum, s._maximum, s._cancelable, s._action == "smith")
            : new(__result, s._overlays, s._domain, s._chosen, context, s._enchantment, s._amount, s._maximum);
    }
    internal void Advance()
    {
        Require(Context() && ExactHooks());
        Require(_selection?.IsFaulted != true && _selection?.IsCanceled != true && _obtain?.IsFaulted != true && _obtain?.IsCanceled != true);
        Require(_selection?.IsCompletedSuccessfully != true || _selection.Result || _interactive && _choice?.Cancelled == true);
        if (_choice is not null && !_choice.Completed) _choice.Advance();
        if (_interactive && _choice?.ConfirmationDispatched == true) _chosen = _choice.Selected;
        Rewards?.Read();
    }
    internal DeckChoiceView? ReadChoice()
    {
        Require(_interactive && Context() && ExactHooks());
        return _choice?.Read();
    }
    internal void ApplyChoice(string operation, CardModel? card)
    {
        Require(_interactive && Context() && ExactHooks() && _choice is not null);
        _choice.Apply(operation, card);
    }
    internal bool Cancelled => _interactive && _selection?.IsCompletedSuccessfully == true && !_selection.Result && _choice?.Cancelled == true;
    internal bool Completed => _selection?.IsCompletedSuccessfully == true && (_selection.Result || Cancelled) &&
        (_choice is null || _choice.Completed) && (Rewards is null || Rewards.Completed) && _overlays.ScreenCount == 0;
    internal void Verify()
    {
        Require(Context() && ExactHooks() && Completed);
        var after = new RestNativeState(_player);
        if (Cancelled) { Require(_action is "cook" or "smith" && _before.Equals(after)); _verified = true; return; }
        switch (RestV2Session.Kind(_action))
        {
            case "heal":
                // Native Heal also executes relic hooks.
                // Collection effects belong to the owned reward reader; do not
                // invent a fixed HP delta for the entire parent callback.
                Require(_interactive && Rewards?.Completed == true && after.Hp > 0 && after.Hp <= after.MaxHp);
                break;
            case "smith":
                Require(_interactive && _choice?.Completed == true && _chosen.Length == 1 &&
                    after.Deck.Length == _before.Deck.Length && after.Gold == _before.Gold && after.Relics.SequenceEqual(_before.Relics) && after.Potions.SequenceEqual(_before.Potions));
                for (int i = 0; i < _before.Deck.Length; i++)
                {
                    var original = _before.Deck[i]; var actual = after.Deck[i];
                    Require(ReferenceEquals(actual.Model, original.Model) && actual == original with { Upgrade = original.Upgrade + (_chosen.Contains(original.Model) ? 1 : 0) });
                }
                break;
            case "cook":
                Require(_choice?.Completed == true && _chosen.Length == 2 && after.MaxHp == checked(_before.MaxHp + 9) &&
                    after.Gold == _before.Gold && after.Relics.SequenceEqual(_before.Relics) && after.Potions.SequenceEqual(_before.Potions) &&
                    after.Deck.SequenceEqual(_before.Deck.Where(c => !_chosen.Contains(c.Model))));
                break;
            case "clone":
                var originals = _before.Clonable;
                Require(_insertions.Count == originals.Length && after.Deck.Length == _before.Deck.Length + originals.Length &&
                    after.Deck.Take(_before.Deck.Length).SequenceEqual(_before.Deck));
                for (int i = 0; i < originals.Length; i++)
                {
                    var task = _insertions[i]; var added = after.Deck[_before.Deck.Length + i].Model;
                    // Native add modifiers may replace/upgrade the clone (egg relics),
                    // and on-add hooks may grant gold. Certify the actual insertion.
                    Require(task.IsCompletedSuccessfully && task.Result.success && ReferenceEquals(task.Result.cardAdded, added) &&
                        !_before.Deck.Any(c => ReferenceEquals(c.Model, added)));
                }
                break;
            case "dig":
            case "hatch":
                Require(_obtain?.IsCompletedSuccessfully == true && ReferenceEquals(_obtain.Result, _relic) && ReferenceEquals(_relic!.Owner, _player) &&
                    after.Relics.Length == _before.Relics.Length + 1 && after.Relics.Take(_before.Relics.Length).SequenceEqual(_before.Relics) && ReferenceEquals(after.Relics[^1], _relic));
                if (_action == "hatch")
                {
                    var eggs = _before.Eggs;
                    var survivors = _before.Deck.Where(c => !eggs.Contains(c)).ToArray();
                    Require(eggs.Length > 0 && after.Deck.Length == _before.Deck.Length &&
                        after.Deck.Where(c => survivors.Any(s => ReferenceEquals(s.Model, c.Model))).SequenceEqual(survivors) &&
                        after.Deck.Where(c => !survivors.Any(s => ReferenceEquals(s.Model, c.Model))).All(c => c.Model.GetType() == typeof(ByrdSwoop) && !_before.Deck.Any(b => ReferenceEquals(b.Model, c.Model))));
                }
                break;
        }
        _verified = true;
    }
    public void Dispose()
    {
        Require(System.Environment.CurrentManagedThreadId == _thread);
        if (_disposed) { Require(!_unresolvedDisposal); return; }
        _unresolvedDisposal |= _entered && !_verified;
        foreach (var h in _hooks)
        {
            var info = Harmony.GetPatchInfo(h.Target);
            var all = info is null ? Array.Empty<HarmonyLib.Patch>() : info.Prefixes.Concat(info.Postfixes).Concat(info.Transpilers).Concat(info.Finalizers).ToArray();
            Require(!all.Any(p => (p.PatchMethod == h.Prefix || p.PatchMethod == h.Postfix) && p.owner != _harmony.Id));
            _harmony.Unpatch(h.Target, h.Prefix); _harmony.Unpatch(h.Target, h.Postfix);
            Require(Harmony.GetPatchInfo(h.Target)?.Owners.Contains(_harmony.Id) != true);
        }
        if (ReferenceEquals(Scope.Value, this)) Scope.Value = null;
        if (ReferenceEquals(Active, this)) Active = null;
        Rewards?.Dispose();
        _disposed = true;
        Require(!_unresolvedDisposal);
    }
}
