using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

namespace Sts2AgentBridge.Cards.Combat;

// Hand selections replace their holders when moving to/from the selected row.
// Stable slots belong to original card models; only our selected card may change
// its native holder. The exact task distinguishes repeated uses of the same hand.
internal sealed class PinnedCombatHandChoiceAdapter : ICombatCardChoiceAdapter
{
    private readonly NRun _run;
    private readonly NPlayerHand _hand;
    private readonly NCombatRoom _room;
    private readonly CombatManager _manager;
    private readonly CombatState _combat;
    private readonly Player _player;
    private readonly object _playerCombat;
    private readonly NOverlayStack _overlays;
    private readonly CardSelectorPrefs _prefs;
    private readonly NPlayerHand.Mode _mode;
    private readonly object? _filter;
    private readonly Task<IEnumerable<CardModel>> _task;
    private readonly NConfirmButton _confirm;
    private readonly NSelectedHandCardContainer _selectedContainer;
    private readonly NUpgradePreview _preview;
    private readonly CardModel[] _models;
    private readonly object[] _slots;
    private readonly string[] _keys;
    private readonly int[] _levels;
    private readonly NCardHolder?[] _holders;
    private readonly NCard?[] _nodes;
    private int _moving = -1;
    private bool _movingSelected, _disposed;
    private static T Field<T>(object value, string name) =>
        (T)(typeof(NPlayerHand).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(value)!);
    private static void Check(bool value) { if (!value) throw new InvalidOperationException("native_hand_binding"); }
    private static bool Valid(GodotObject? value) => value is not null && GodotObject.IsInstanceValid(value);
    internal PinnedCombatHandChoiceAdapter(NRun run, NPlayerHand hand)
    {
        _run = run; _hand = hand; _room = NCombatRoom.Instance ?? throw new InvalidOperationException("missing_hand_room"); _overlays = run.GlobalUi.Overlays;
        _manager = CombatManager.Instance!; _combat = _manager.DebugOnlyGetState()!;
        Check(_combat is not null && _combat.Players.Count == 1);
        _player = _combat!.Players[0]; _playerCombat = _player.PlayerCombatState!;
        _prefs = Field<CardSelectorPrefs>(hand, "_prefs"); _mode = hand.CurrentMode;
        _filter = Field<object?>(hand, "_currentSelectionFilter");
        _task = Field<TaskCompletionSource<IEnumerable<CardModel>>>(hand, "_selectionCompletionSource").Task;
        _confirm = Field<NConfirmButton>(hand, "_selectModeConfirmButton");
        _selectedContainer = Field<NSelectedHandCardContainer>(hand, "_selectedHandCardContainer");
        _preview = Field<NUpgradePreview>(hand, "_upgradePreview");
        Check(_mode is NPlayerHand.Mode.SimpleSelect or NPlayerHand.Mode.UpgradeSelect &&
            !_task.IsCompleted && _prefs.MinSelect >= 0 && _prefs.MaxSelect >= Math.Max(1, _prefs.MinSelect) &&
            Field<List<CardModel>>(hand, "_selectedCards").Count == 0 && !hand.PeekButton.IsPeeking);
        var holders = hand.ActiveHolders.Where(h => h.CardNode is not null).Take(65).ToArray();
        _models = holders.Select(h => h.CardNode!.Model ?? throw new InvalidOperationException("missing_hand_model")).ToArray();
        Check(_models.Length is > 0 and <= 64 && _models.Distinct(ReferenceEqualityComparer.Instance).Count() == _models.Length);
        _slots = _models.Select(_ => new object()).ToArray();
        _keys = _models.Select(c => c.Id.Entry).ToArray(); _levels = _models.Select(c => c.CurrentUpgradeLevel).ToArray();
        _holders = holders.Cast<NCardHolder?>().ToArray(); _nodes = holders.Select(h => h.CardNode).ToArray();
    }
    private NCardHolder? Target(CardModel card, bool selected)
    {
        if (!selected) return _hand.ActiveHolders.SingleOrDefault(h => ReferenceEquals(h.CardNode?.Model, card));
        if (_mode == NPlayerHand.Mode.SimpleSelect)
            return _selectedContainer.Holders
                .SingleOrDefault(h => ReferenceEquals(h.CardNode?.Model, card));
        var preview = _preview;
        Check(ReferenceEquals(preview.Card, card));
        return preview.DefaultFocusedControl as NCardHolder;
    }
    public ChoiceSurface Capture()
    {
        Check(!_disposed && Valid(_run) && Valid(_hand) && ReferenceEquals(NRun.Instance, _run) &&
            Valid(_room) && ReferenceEquals(NCombatRoom.Instance, _room) && ReferenceEquals(_run.CombatRoom, _room) && ReferenceEquals(_room.Ui.Hand, _hand) &&
            ReferenceEquals(NPlayerHand.Instance, _hand) && ReferenceEquals(CombatManager.Instance, _manager) &&
            ReferenceEquals(_manager.DebugOnlyGetState(), _combat) && _combat.Players.Count == 1 &&
            ReferenceEquals(_combat.Players[0], _player) && ReferenceEquals(_player.PlayerCombatState, _playerCombat) &&
            ReferenceEquals(_run.GlobalUi.Overlays, _overlays) && ReferenceEquals(NOverlayStack.Instance, _overlays) &&
            _overlays.ScreenCount == 0 && !_run.GlobalUi.MapScreen.IsOpen && !_run.GlobalUi.MapScreen.IsTraveling &&
            CardSelectCmd.Selector is null &&
            ReferenceEquals(Field<TaskCompletionSource<IEnumerable<CardModel>>>(_hand, "_selectionCompletionSource").Task, _task));
        int minimum = Math.Min(_prefs.MinSelect, _models.Length), maximum = Math.Min(_prefs.MaxSelect, _models.Length);
        // This native UI always uses its explicit confirmation button, including
        // callers whose prefs allow automatic selection when no UI is needed.
        if (_task.IsCompleted || !_hand.IsInCardSelection)
            return new(_task, "hand", minimum, maximum, true, false, !_hand.IsInCardSelection,
                _task.IsCompletedSuccessfully, _task.IsCanceled || _task.IsFaulted, Array.Empty<ChoiceCard>(),
                _task.IsCompletedSuccessfully ? _task.Result.Cast<object>().ToArray() : Array.Empty<object>(), false);
        var prefs = Field<CardSelectorPrefs>(_hand, "_prefs");
        Check(_manager.IsInProgress && !_manager.IsOverOrEnding && _hand.CurrentMode == _mode &&
            ReferenceEquals(Field<object?>(_hand, "_currentSelectionFilter"), _filter) &&
            prefs.Equals(_prefs) && Valid(_selectedContainer) && Valid(_preview) &&
            ReferenceEquals(Field<NSelectedHandCardContainer>(_hand, "_selectedHandCardContainer"), _selectedContainer) &&
            ReferenceEquals(Field<NUpgradePreview>(_hand, "_upgradePreview"), _preview) && ReferenceEquals(Field<NConfirmButton>(_hand, "_selectModeConfirmButton"), _confirm));
        var selected = Field<List<CardModel>>(_hand, "_selectedCards").ToArray();
        Check(selected.Distinct(ReferenceEqualityComparer.Instance).Count() == selected.Length && selected.All(_models.Contains));
        var cards = new ChoiceCard[_models.Length];
        for (int i = 0; i < cards.Length; i++)
        {
            var model = _models[i]; bool isSelected = selected.Contains(model);
            var holder = Target(model, isSelected);
            Check(Valid(holder) && Valid(holder!.CardNode) && ReferenceEquals(holder.CardNode!.Model, model) &&
                ReferenceEquals(model.Owner, _player) && PileType.Hand.GetPile(_player).Cards.Contains(model) &&
                model.Id.Entry == _keys[i] && model.CurrentUpgradeLevel == _levels[i]);
            if (i == _moving && isSelected == _movingSelected)
            {
                if (_mode != NPlayerHand.Mode.UpgradeSelect || !isSelected) Check(ReferenceEquals(holder!.CardNode, _nodes[i]));
                _holders[i] = holder; _nodes[i] = holder!.CardNode; _moving = -1;
            }
            else Check(ReferenceEquals(holder, _holders[i]) && ReferenceEquals(holder!.CardNode, _nodes[i]));
            Check(Valid(holder!.Hitbox));
            cards[i] = new(model, _slots[i], _keys[i], _levels[i], isSelected,
                holder.IsVisibleInTree() && holder.CardNode!.IsVisibleInTree() && holder.Hitbox.IsVisibleInTree() && holder.Hitbox.IsEnabled &&
                (bool)typeof(NCardHolder).GetField("_isClickable", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(holder)!, holder);
        }
        bool ready = _hand.IsVisibleInTree() && !_hand.PeekButton.IsPeeking && ActiveScreenContext.Instance.IsCurrent(_room);
        return new(_task, "hand", minimum, maximum, true, ready, false, false, false, cards,
            Array.Empty<object>(), ready && _confirm.IsVisibleInTree() && _confirm.IsEnabled, selected.Cast<object>().ToArray());
    }
    public void Toggle(int slot)
    {
        var fresh = Capture();
        Check(fresh.Ready && slot >= 0 && slot < fresh.Cards.Length && fresh.Cards[slot].Enabled && _moving < 0);
        _moving = slot; _movingSelected = !fresh.Cards[slot].Selected;
        var holder = _holders[slot]!;
        Check(holder.EmitSignal(NCardHolder.SignalName.Pressed, holder) == Error.Ok);
    }
    public void Confirm()
    {
        var fresh = Capture(); int count = fresh.Cards.Count(c => c.Selected);
        Check(fresh.Ready && fresh.ConfirmEnabled && count >= fresh.MinSelect && count <= fresh.MaxSelect && _moving < 0);
        _confirm.ForceClick();
    }
    public void Dispose() => _disposed = true;
}
