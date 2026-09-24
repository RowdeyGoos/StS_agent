using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;

namespace Sts2AgentBridge.Cards.Combat;

// Metadata inspection of the pinned game identifies these exact fields. No
// selector overrides, request injection, game RNG, or hidden draw order is used.
internal sealed class PinnedCombatCardChoiceAdapter : ICombatCardChoiceAdapter
{
    private readonly NRun _run;
    private readonly CombatState _combat;
    private readonly Player _player;
    private readonly NOverlayStack _overlays;
    private readonly NCombatPileCardSelectScreen _screen;
    private readonly NCardGrid _grid;
    private readonly NConfirmButton _confirm;
    private readonly CardPile _pile;
    private readonly CardSelectorPrefs _prefs;
    private readonly object _filter;
    private readonly Task<IEnumerable<CardModel>> _task;
    private readonly NGridCardHolder[] _holders;
    private readonly CardModel[] _models;
    private readonly NCard[] _nodes;
    private readonly object[] _hitboxes;
    private readonly string[] _keys;
    private readonly int[] _levels;
    private bool _disposed;

    private static T Field<T>(object value, Type owner, string name) =>
        (T)(owner.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
            ?.GetValue(value) ?? throw new InvalidOperationException("native_field"));
    private static T Field<T>(object value, string name) => Field<T>(value, typeof(NCombatPileCardSelectScreen), name);
    private static bool Valid(GodotObject? value) => value is not null && GodotObject.IsInstanceValid(value);
    private static void Check(bool value) { if (!value) throw new InvalidOperationException("native_choice_binding"); }

    internal static ICombatCardChoiceAdapter? TryCreate()
    {
        NRun? run = NRun.Instance;
        if (!Valid(run) || run!.GlobalUi is null) return null;
        var overlays = run.GlobalUi.Overlays;
        if (!Valid(overlays)) return null;
        if (overlays.Peek() is NChooseACardSelectionScreen offer)
            return new PinnedCombatCardOfferAdapter(run, overlays, offer);
        if (overlays.Peek() is not NCombatPileCardSelectScreen screen) return null;
        CombatManager? manager = CombatManager.Instance;
        CombatState? combat = manager?.DebugOnlyGetState();
        Check(manager is not null && manager.IsInProgress && !manager.IsOverOrEnding &&
            combat is not null && combat.Players.Count == 1 && overlays.ScreenCount == 1 &&
            screen.GetType() == typeof(NCombatPileCardSelectScreen));
        return new PinnedCombatCardChoiceAdapter(run, combat!, combat!.Players[0], overlays, screen);
    }
    private PinnedCombatCardChoiceAdapter(NRun run, CombatState combat, Player player,
        NOverlayStack overlays, NCombatPileCardSelectScreen screen)
    {
        _run = run; _combat = combat; _player = player; _overlays = overlays; _screen = screen;
        _grid = screen.GetNodeOrNull<NCardGrid>("%CardGrid")!;
        _confirm = screen.GetNodeOrNull<NConfirmButton>("%Confirm")!;
        _pile = Field<CardPile>(screen, "_pile");
        _prefs = Field<CardSelectorPrefs>(screen, "_prefs");
        _filter = Field<object>(screen, "_filter");
        _task = Field<TaskCompletionSource<IEnumerable<CardModel>>>(screen, typeof(NCardGridSelectionScreen), "_completionSource").Task;
        Check(Valid(_grid) && Valid(_confirm) && !_task.IsCompleted &&
            _pile.Type is PileType.Discard or PileType.Exhaust or PileType.Draw &&
            _prefs.MinSelect >= 0 && _prefs.MinSelect <= _prefs.MaxSelect && _prefs.MaxSelect is >= 1 and <= 8);
        // Native draw-pile selectors sort this public grid by rarity/name. Bind
        // its displayed holders; never derive candidate slots from pile order.
        _holders = _grid.CurrentlyDisplayedCardHolders.Take(65).ToArray();
        Check(_holders.Length is >= 1 and <= 64 && _holders.All(h => Valid(h) && h.GetType() == typeof(NGridCardHolder)));
        _models = _holders.Select(h => h.CardModel).ToArray();
        _nodes = _holders.Select(h => h.CardNode ?? throw new InvalidOperationException("missing_card_node")).ToArray();
        _hitboxes = _holders.Select(h => (object)h.Hitbox).ToArray();
        _keys = _models.Select(m => m.Id.Entry).ToArray();
        _levels = _models.Select(m => m.CurrentUpgradeLevel).ToArray();
        Check(Context() && Field<HashSet<CardModel>>(screen, "_selectedCards").Count == 0);
    }
    private bool Context() => !_disposed && Valid(_run) && Valid(_overlays) &&
        ReferenceEquals(NRun.Instance, _run) && ReferenceEquals(_run.GlobalUi?.Overlays, _overlays) &&
        ReferenceEquals(NOverlayStack.Instance, _overlays) &&
        ReferenceEquals(CombatManager.Instance?.DebugOnlyGetState(), _combat) &&
        _combat.Players.Count == 1 && ReferenceEquals(_combat.Players[0], _player) &&
        _player.PlayerCombatState is not null && CardSelectCmd.Selector is null &&
        Valid(_run.GlobalUi?.MapScreen) && !_run.GlobalUi!.MapScreen.IsOpen && !_run.GlobalUi.MapScreen.IsTraveling;

    public ChoiceSurface Capture()
    {
        Check(Context());
        int minimum = Math.Min(_prefs.MinSelect, _models.Length), maximum = Math.Min(_prefs.MaxSelect, _models.Length);
        string pile = _pile.Type switch { PileType.Discard => "discard", PileType.Exhaust => "exhaust",
            PileType.Draw => "draw", _ => throw new InvalidOperationException("native_choice_binding") };
        bool closed = _overlays.ScreenCount == 0 && _overlays.Peek() is null;
        bool succeeded = _task.IsCompletedSuccessfully;
        object[] result = succeeded ? _task.Result.Take(65).Cast<object>().ToArray() : Array.Empty<object>();
        if (closed)
            return new(_screen, pile, minimum, maximum, _prefs.RequireManualConfirmation, false, true,
                succeeded, _task.IsFaulted || _task.IsCanceled, Array.Empty<ChoiceCard>(), result, false);
        Check(_overlays.ScreenCount == 1 && ReferenceEquals(_overlays.Peek(), _screen) && Valid(_screen) &&
            Valid(_grid) && Valid(_confirm) && ReferenceEquals(_screen.GetNodeOrNull<NCardGrid>("%CardGrid"), _grid) &&
            ReferenceEquals(_screen.GetNodeOrNull<NConfirmButton>("%Confirm"), _confirm) &&
            ReferenceEquals(Field<CardPile>(_screen, "_pile"), _pile) && ReferenceEquals(_pile.Type.GetPile(_player), _pile) &&
            ReferenceEquals(Field<object>(_screen, "_filter"), _filter) &&
            ReferenceEquals(Field<TaskCompletionSource<IEnumerable<CardModel>>>(_screen, typeof(NCardGridSelectionScreen), "_completionSource").Task, _task));
        CardSelectorPrefs prefs = Field<CardSelectorPrefs>(_screen, "_prefs");
        Check(prefs.MinSelect == _prefs.MinSelect && prefs.MaxSelect == _prefs.MaxSelect &&
            prefs.RequireManualConfirmation == _prefs.RequireManualConfirmation && prefs.Cancelable == _prefs.Cancelable);
        var holders = _grid.CurrentlyDisplayedCardHolders.Take(65).ToArray();
        var displayed = _grid.CurrentlyDisplayedCards.Take(65).ToArray();
        var selected = Field<HashSet<CardModel>>(_screen, "_selectedCards");
        Check(holders.Length == _holders.Length && displayed.Length == _models.Length &&
            displayed.Distinct(ReferenceEqualityComparer.Instance).Count() == _models.Length &&
            displayed.All(m => _models.Any(b => ReferenceEquals(b, m))) &&
            selected.All(m => _models.Any(b => ReferenceEquals(b, m))));
        var cards = new ChoiceCard[_holders.Length];
        for (int i = 0; i < cards.Length; i++)
        {
            var holder = _holders[i]; var model = _models[i];
            Check(ReferenceEquals(holders[i], holder) && Valid(holder) && Valid(_nodes[i]) && Valid(holder.Hitbox) &&
                ReferenceEquals(holder.CardModel, model) && ReferenceEquals(holder.CardNode, _nodes[i]) &&
                ReferenceEquals(_nodes[i].Model, model) && ReferenceEquals(holder.Hitbox, _hitboxes[i]) &&
                ReferenceEquals(model.Owner, _player) && _pile.Cards.Any(m => ReferenceEquals(m, model)) &&
                model.Id.Entry == _keys[i] && model.CurrentUpgradeLevel == _levels[i]);
            cards[i] = new(model, holder, _keys[i], _levels[i], selected.Contains(model),
                holder.IsVisibleInTree() && _nodes[i].IsVisibleInTree() && holder.Hitbox.IsVisibleInTree() && holder.Hitbox.IsEnabled &&
                Field<bool>(holder, typeof(NCardHolder), "_isClickable"));
        }
        return new(_screen, pile, minimum, maximum, _prefs.RequireManualConfirmation,
            _screen.IsVisibleInTree() && _grid.IsVisibleInTree() && !_grid.IsAnimatingOut,
            false, succeeded, _task.IsFaulted || _task.IsCanceled, cards, result,
            _confirm.IsVisibleInTree() && _confirm.IsEnabled, selected.Cast<object>().ToArray(), _prefs.Cancelable);
    }
    public void Toggle(int slot)
    {
        ChoiceSurface fresh = Capture();
        Check(fresh.Ready && !fresh.TaskSucceeded && !fresh.TaskFailed && slot >= 0 && slot < fresh.Cards.Length && fresh.Cards[slot].Enabled);
        using var input = new InputEventAction { Action = MegaInput.select, Pressed = true };
        _holders[slot]._GuiInput(input);
    }
    public void Confirm()
    {
        ChoiceSurface fresh = Capture();
        int selected = fresh.Cards.Count(c => c.Selected);
        Check(fresh.Ready && !fresh.TaskSucceeded && !fresh.TaskFailed && fresh.ConfirmEnabled &&
            selected >= fresh.MinSelect && selected <= fresh.MaxSelect);
        _confirm.ForceClick();
    }
    public void Dispose() => _disposed = true;
}

// Knowledge Demon's enemy-turn curse choice uses this screen, not a combat pile.
// Only its displayed mandatory single-card offer is supported. The native caller
// owns the returned card's effect; this adapter only proves the selection result.
internal sealed class PinnedCombatCardOfferAdapter : ICombatCardChoiceAdapter
{
    private readonly NRun _run;
    private readonly CombatManager _manager;
    private readonly CombatState _combat;
    private readonly Player _player;
    private readonly object _playerCombat;
    private readonly NOverlayStack _overlays;
    private readonly NChooseACardSelectionScreen _screen;
    private readonly Control _row;
    private readonly NPeekButton _peek;
    private readonly IReadOnlyList<CardModel> _offered;
    private readonly Task<IEnumerable<CardModel>> _task;
    private readonly NGridCardHolder[] _holders;
    private readonly CardModel[] _models;
    private readonly NCard[] _nodes;
    private readonly object[] _hitboxes;
    private readonly string[] _keys;
    private readonly int[] _levels;
    private readonly ulong _openedTicks;
    private bool _disposed;

    private static T Field<T>(object value, string name, Type? owner = null) =>
        (T)((owner ?? typeof(NChooseACardSelectionScreen)).GetField(name,
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
            ?.GetValue(value) ?? throw new InvalidOperationException("native_offer_field"));
    private static bool Valid(GodotObject? value) => value is not null && GodotObject.IsInstanceValid(value);
    private static void Check(bool value) { if (!value) throw new InvalidOperationException("native_offer_binding"); }
    internal PinnedCombatCardOfferAdapter(NRun run, NOverlayStack overlays, NChooseACardSelectionScreen screen)
    {
        _run = run; _overlays = overlays; _screen = screen;
        _manager = CombatManager.Instance ?? throw new InvalidOperationException("native_offer_manager");
        _combat = _manager.DebugOnlyGetState() ?? throw new InvalidOperationException("native_offer_combat");
        Check(_manager.IsInProgress && !_manager.IsOverOrEnding &&
            _combat is not null && _combat.Players.Count == 1 && overlays.ScreenCount == 1 &&
            screen.GetType() == typeof(NChooseACardSelectionScreen) && Valid(screen));
        _player = _combat!.Players[0];
        _playerCombat = _player.PlayerCombatState ?? throw new InvalidOperationException("native_offer_player");
        _row = screen.GetNodeOrNull<Control>("CardRow")!;
        _peek = screen.GetNodeOrNull<NPeekButton>("%PeekButton")!;
        _offered = Field<IReadOnlyList<CardModel>>(screen, "_cards");
        _task = Field<TaskCompletionSource<IEnumerable<CardModel>>>(screen, "_completionSource").Task;
        _openedTicks = Field<ulong>(screen, "_openedTicks");
        Check(Valid(_row) && Valid(_peek) && !_task.IsCompleted && _offered.Count is >= 1 and <= 3 &&
            !Field<bool>(screen, "_canSkip") && !Field<bool>(screen, "_screenComplete") && !Field<bool>(screen, "_cardSelected"));
        _holders = _row.GetChildren().OfType<NGridCardHolder>().Take(4).ToArray();
        Check(_row.GetChildCount() == _offered.Count && _holders.Length == _offered.Count &&
            _holders.All(h => Valid(h) && h.GetType() == typeof(NGridCardHolder)));
        _models = _offered.ToArray();
        _nodes = _holders.Select(h => h.CardNode ?? throw new InvalidOperationException("native_offer_card_node")).ToArray();
        _hitboxes = _holders.Select(h => (object)h.Hitbox).ToArray();
        _keys = _models.Select(m => m.Id.Entry).ToArray();
        _levels = _models.Select(m => m.CurrentUpgradeLevel).ToArray();
        Check(Context());
    }
    private bool Context() => !_disposed && Valid(_run) && Valid(_overlays) &&
        ReferenceEquals(NRun.Instance, _run) && ReferenceEquals(_run.GlobalUi?.Overlays, _overlays) &&
        ReferenceEquals(NOverlayStack.Instance, _overlays) && ReferenceEquals(CombatManager.Instance, _manager) &&
        ReferenceEquals(_manager.DebugOnlyGetState(), _combat) && _combat.Players.Count == 1 &&
        ReferenceEquals(_combat.Players[0], _player) && ReferenceEquals(_player.PlayerCombatState, _playerCombat) &&
        CardSelectCmd.Selector is null && Valid(_run.GlobalUi?.MapScreen) &&
        !_run.GlobalUi!.MapScreen.IsOpen && !_run.GlobalUi.MapScreen.IsTraveling;

    public ChoiceSurface Capture()
    {
        Check(Context());
        bool closed = _overlays.ScreenCount == 0 && _overlays.Peek() is null;
        bool succeeded = _task.IsCompletedSuccessfully;
        object[] result = succeeded ? _task.Result.Take(4).Cast<object>().ToArray() : Array.Empty<object>();
        if (closed)
            return new(_screen, "offer", 1, 1, false, false, true, succeeded,
                _task.IsFaulted || _task.IsCanceled, Array.Empty<ChoiceCard>(), result, false);
        Check(_manager.IsInProgress && !_manager.IsOverOrEnding && _overlays.ScreenCount == 1 &&
            ReferenceEquals(_overlays.Peek(), _screen) && Valid(_screen) && Valid(_row) && Valid(_peek) &&
            ReferenceEquals(_screen.GetNodeOrNull<Control>("CardRow"), _row) &&
            ReferenceEquals(_screen.GetNodeOrNull<NPeekButton>("%PeekButton"), _peek) &&
            ReferenceEquals(Field<IReadOnlyList<CardModel>>(_screen, "_cards"), _offered) &&
            ReferenceEquals(Field<TaskCompletionSource<IEnumerable<CardModel>>>(_screen, "_completionSource").Task, _task) &&
            Field<ulong>(_screen, "_openedTicks") == _openedTicks && !Field<bool>(_screen, "_canSkip") &&
            _offered.Count == _models.Length && _row.GetChildCount() == _holders.Length);
        var holders = _row.GetChildren().OfType<NGridCardHolder>().Take(4).ToArray();
        Check(holders.Length == _holders.Length);
        var cards = new ChoiceCard[_holders.Length];
        for (int i = 0; i < cards.Length; i++)
        {
            var holder = _holders[i]; var model = _models[i];
            Check(ReferenceEquals(holders[i], holder) && Valid(holder) && Valid(_nodes[i]) && Valid(holder.Hitbox) &&
                ReferenceEquals(_offered[i], model) && ReferenceEquals(holder.CardModel, model) &&
                ReferenceEquals(holder.CardNode, _nodes[i]) && ReferenceEquals(_nodes[i].Model, model) &&
                ReferenceEquals(holder.Hitbox, _hitboxes[i]) && ReferenceEquals(model.Owner, _player) &&
                model.Id.Entry == _keys[i] && model.CurrentUpgradeLevel == _levels[i]);
            cards[i] = new(model, holder, _keys[i], _levels[i], false,
                holder.IsVisibleInTree() && _nodes[i].IsVisibleInTree() && holder.Hitbox.IsVisibleInTree() &&
                holder.Hitbox.IsEnabled && Field<bool>(holder, "_isClickable", typeof(NCardHolder)));
        }
        bool ready = !succeeded && !_task.IsCompleted && !Field<bool>(_screen, "_screenComplete") &&
            !Field<bool>(_screen, "_cardSelected") && ActiveScreenContext.Instance.IsCurrent(_screen) &&
            !_peek.IsPeeking && _screen.IsVisibleInTree() &&
            _row.IsVisibleInTree() && Time.GetTicksMsec() >= _openedTicks && Time.GetTicksMsec() - _openedTicks > 350;
        return new(_screen, "offer", 1, 1, false, ready, false, succeeded,
            _task.IsFaulted || _task.IsCanceled, cards, result, false);
    }
    public void Toggle(int slot)
    {
        ChoiceSurface fresh = Capture();
        Check(fresh.Ready && slot >= 0 && slot < fresh.Cards.Length && fresh.Cards[slot].Enabled);
        // The ordinary keyboard helper defers EmitPressed and can outlive this
        // binding. Use the same synchronous native signal as the event offer
        // adapter, while the owner-thread capture still binds this exact holder.
        Check(_holders[slot].EmitSignal(NCardHolder.SignalName.Pressed, _holders[slot]) == Error.Ok);
    }
    public void Confirm() => throw new InvalidOperationException("native_offer_has_no_confirmation");
    public void Dispose() => _disposed = true;
}
