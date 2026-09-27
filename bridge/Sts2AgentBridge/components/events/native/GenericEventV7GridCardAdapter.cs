using System;
using System.Linq;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// Full-producer single-card selectors use the shared bounded allocation driver.
// The legacy adapters retain their exact allocated-holder contracts.
internal sealed class GenericEventV7GridCardAdapter : IGenericEventV7GridNative
{
    private readonly GenericEventV7Binding _binding;
    private readonly CardModel[] _domain;
    private readonly GenericEventV7GridCard[] _cards;
    private readonly CardSelectionV1DeckCard[] _before;
    private readonly PinnedDeckCardChoice _choice;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private int? _selected;
    private bool _failed, _disposed, _completed, _upgradeApplied;
    private CardSelectionV1Enchantment? _applied;
    internal CardModel[] Domain => _domain.ToArray();

    internal GenericEventV7GridCardAdapter(GenericEventV7Binding binding)
    {
        _binding = binding;
        Require(binding.FullCardGrid && binding.Ready && binding.MatchesCurrentDeck() && binding.MatchesChildBinding() &&
            binding.Prefs.MinSelect == 1 && binding.Prefs.MaxSelect == 1 && !binding.Prefs.Cancelable &&
            binding.DomainCount is >= 2 and <= 128 && binding.SelectionDeck.Length <= 128 &&
            binding.Operation is CardSelectionV1Operation.Enchant or CardSelectionV1Operation.Upgrade);
        _domain = binding.Originals.ToArray(); _before = binding.SelectionDeck.ToArray();
        _cards = _domain.Select(c => new GenericEventV7GridCard(c.Id.Entry, c.CurrentUpgradeLevel)).ToArray();
        bool upgrade = binding.Operation == CardSelectionV1Operation.Upgrade;
        Require(binding.Screen!.GetType() == (upgrade ? typeof(NDeckUpgradeSelectScreen) : typeof(NDeckEnchantSelectScreen)) &&
            (upgrade || GenericEventV7CardAdapter.EnchantmentScreenMatches(binding, binding.Screen)));
        _choice = new(binding.Screen, binding.Overlays, _domain, Context, binding.EnchantmentModel,
            binding.Enchantment?.Amount ?? 0, 1, 1, false, upgrade, maximumDomain: 128);
    }
    private void Require(bool good) { if (!good) { _failed = true; _binding.Failed = true; throw new InvalidOperationException("event_grid_native_boundary"); } }
    private bool Context() => !_failed && !_disposed && Environment.CurrentManagedThreadId == _thread &&
        _binding.MatchesChildBinding() && _binding.ChosenTask?.IsFaulted != true && _binding.ChosenTask?.IsCanceled != true &&
        _binding.RequestTask?.IsFaulted != true && _binding.RequestTask?.IsCanceled != true &&
        (_choice?.ConfirmationDispatched != true || _binding.Overlays.ScreenCount == 0 && _binding.Overlays.Peek() is null ||
            _binding.Overlays.ScreenCount == 1 && ReferenceEquals(_binding.Overlays.Peek(), _binding.Screen)) &&
        (_choice?.ConfirmationDispatched == true || _binding.MatchesCurrentDeck() &&
            (_binding.Operation == CardSelectionV1Operation.Upgrade ? _domain.All(c => c.IsUpgradable) :
                GenericEventV7CardAdapter.EnchantmentScreenMatches(_binding, _binding.Screen!) &&
                _domain.All(c => c.Enchantment is null && _binding.EnchantmentModel!.CanEnchant(c))));
    public GenericEventV7GridCapture Read()
    {
        Require(Context());
        if (_completed) { VerifyEffect(); return new("resolved", _cards, _selected); }
        var view = _choice.Read();
        if (_choice.ConfirmationDispatched)
        {
            // Until the parent's effect has finished, retain any first observed
            // applied enchant identity and reject survivor or ordering changes.
            VerifyEffect(allowPending: true);
            if (!_choice.Completed || _binding.RequestTask?.IsCompletedSuccessfully != true ||
                _binding.ChosenTask?.IsCompletedSuccessfully != true) return new("waiting", _cards, _selected);
            Require(_selected is not null && _binding.EffectCompleted(new object[] { _domain[_selected!.Value] }));
            if (_binding.Overlays.ScreenCount != 0) return new("waiting", _cards, _selected);
            VerifyEffect(); _completed = true;
            return new("resolved", _cards, _selected);
        }
        if (view is null) return new("waiting", _cards, _selected);
        Require(view.Domain.SequenceEqual(_domain) && view.Selected.Length <= 1);
        int? selected = view.Selected.Length == 0 ? null : Array.IndexOf(_domain, view.Selected[0]);
        Require(selected == _selected);
        return new("ready", _cards, selected);
    }
    public void Apply(string operation, int? slot)
    {
        Require(Context() && !_completed && !_choice.ConfirmationDispatched);
        Require(operation == "select" ? _selected is null && slot is >= 0 && slot < _domain.Length : operation == "confirm" && slot is null && _selected is not null);
        if (operation == "select") _selected = slot;
        _choice.Apply(operation, slot is null ? null : _domain[slot.Value]);
    }
    private void VerifyEffect(bool allowPending = false)
    {
        Require(_selected is not null);
        var after = GenericEventV7Binding.CopyDeck(_binding.Player);
        Require(after.Length == _before.Length);
        for (int i = 0; i < after.Length; i++)
        {
            var old = _before[i]; var now = after[i];
            Require(ReferenceEquals(old.ModelIdentity, now.ModelIdentity) && old.StableKey == now.StableKey &&
                now.ModelIdentity is CardModel card && ReferenceEquals(card.Owner, _binding.Player) && ReferenceEquals(card.RunState, _binding.RunState));
            if (!ReferenceEquals(old.ModelIdentity, _domain[_selected!.Value]))
            { Require(GenericEventV7Binding.SameDeckCard(old, now)); continue; }
            if (_binding.Operation == CardSelectionV1Operation.Upgrade)
            {
                Require(CardSelectionV1Enchantment.Same(old.Enchantment, now.Enchantment) &&
                    (now.UpgradeLevel == old.UpgradeLevel + 1 || allowPending && !_upgradeApplied && now.UpgradeLevel == old.UpgradeLevel));
                _upgradeApplied |= now.UpgradeLevel == old.UpgradeLevel + 1;
            }
            else
            {
                Require(old.Enchantment is null && now.UpgradeLevel == old.UpgradeLevel);
                if (allowPending && now.Enchantment is null) { Require(_applied is null); continue; }
                Require(now.Enchantment is {} applied && _binding.Enchantment is {} expected &&
                    applied.Key == expected.Key && applied.Amount == expected.Amount && !ReferenceEquals(applied.Identity, expected.Identity) &&
                    !_before.Any(c => ReferenceEquals(c.Enchantment?.Identity, applied.Identity)));
                _applied ??= now.Enchantment;
                Require(CardSelectionV1Enchantment.Same(_applied, now.Enchantment));
            }
        }
    }
    public void Dispose()
    {
        if (_disposed) return;
        Require(Context() && _completed && _binding.Overlays.ScreenCount == 0);
        VerifyEffect(); _disposed = true;
    }
}
