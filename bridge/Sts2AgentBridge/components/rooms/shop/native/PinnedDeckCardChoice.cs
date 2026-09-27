using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
using Sts2AgentBridge.Adapters.Public;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

internal sealed record DeckChoiceView(CardModel[] Domain, CardModel[] Selected, int Minimum, int Maximum, bool Cancelable);

// Exact original models, allocated controls and native preview confirmation.
// The caller owns the enclosing request/task/effect. Interactive requests change
// one semantic selection; native preview dismissal/reselection is drained without
// choosing another card on the policy's behalf.
internal sealed class PinnedDeckCardChoice
{
    private readonly Control _screen;
    private readonly NOverlayStack _overlays;
    private readonly PinnedOverlayPrefix _ancestors;
    private readonly CardModel[] _domain;
    private readonly Func<bool> _context;
    private readonly EnchantmentModel? _enchantment;
    private readonly int _amount, _minimum, _maximum, _maximumDomain;
    private readonly bool _interactive, _cancelable, _upgrade, _transform;
    private readonly Task<IEnumerable<CardModel>> _selection;
    private NCardGrid? _grid;
    private NGridCardHolder[]? _holders;
    private NCard[]? _cardNodes;
    private GodotObject[]? _hitboxes;
    private CardModel[]? _holderCards, _gridCards;
    private bool[]? _holderVisible;
    private Control? _scrollContainer;
    private CardModel? _scrollTarget;
    private float _scrollDestination;
    private int _scrollReads, _scrollPages;
    private bool _scrollAllocationDrained;
    private readonly HashSet<CardModel> _scrollWindows = new(ReferenceEqualityComparer.Instance);
    private Control? _container, _preview;
    private NConfirmButton? _confirm, _openPreview;
    private NBackButton? _back, _previewBack;
    private object[]? _previewBindings;
    private CardModel[] _selected = Array.Empty<CardModel>();
    private readonly HashSet<CardModel> _highlightPending = new(ReferenceEqualityComparer.Instance);
    private CardModel[]? _desired;
    private string? _finish;
    private bool _confirmed, _cancelled, _failed, _ready, _previewRequested;
    private int _inputs;
    internal bool Completed => !_failed && (_confirmed || _cancelled) && SelectedExactly();
    internal bool ConfirmationDispatched => _confirmed;
    internal bool CancellationDispatched => _cancelled;
    internal bool Cancelled => Completed && _cancelled;
    internal CardModel[] Selected => _selected.ToArray();
    internal bool OwnsForeground => !_failed && Valid(_screen) && _ancestors.Matches(_screen) && ReferenceEquals(_overlays.Peek(), _screen) &&
        (!_interactive || ReferenceEquals(ActiveScreenContext.Instance.GetCurrentScreen(), _screen));

    // Retained legacy controller: its caller explicitly precommits the targets.
    internal PinnedDeckCardChoice(Control screen, NOverlayStack overlays, IReadOnlyList<CardModel> domain,
        CardModel[] targets, Func<bool> context, EnchantmentModel? enchantment, int amount, int maximum)
        : this(screen, overlays, domain, context, enchantment, amount, targets.Length, maximum, false, false, false)
    {
        Require(targets.Distinct(ReferenceEqualityComparer.Instance).Count() == targets.Length && targets.All(t => _domain.Contains(t)));
        _desired = targets.ToArray(); _finish = "confirm";
    }

    internal PinnedDeckCardChoice(Control screen, NOverlayStack overlays, IReadOnlyList<CardModel> domain,
        Func<bool> context, EnchantmentModel? enchantment, int amount, int minimum, int maximum, bool cancelable, bool upgrade = false,
        IReadOnlyList<Control>? ancestors = null, bool transform = false, int maximumDomain = 64)
        : this(screen, overlays, domain, context, enchantment, amount, minimum, maximum, cancelable, true, upgrade, ancestors, transform, maximumDomain) { }

    private PinnedDeckCardChoice(Control screen, NOverlayStack overlays, IReadOnlyList<CardModel> domain,
        Func<bool> context, EnchantmentModel? enchantment, int amount, int minimum, int maximum, bool cancelable, bool interactive, bool upgrade = false,
        IReadOnlyList<Control>? ancestors = null, bool transform = false, int maximumDomain = 64)
    {
        _screen = screen; _overlays = overlays; _domain = domain.ToArray(); _context = context;
        _ancestors = new(overlays, ancestors);
        _enchantment = enchantment; _amount = amount; _maximum = maximum;
        // The pinned enchant screen opens an empty preview at MinSelect=0,
        // but ConfirmSelection deliberately does nothing without a card.
        // Publish and enforce the usable bound; genuine cancellation is separate.
        _minimum = enchantment is null ? minimum : Math.Max(1, minimum);
        Require(maximumDomain is 64 or 128 && (interactive || maximumDomain == 64)); _maximumDomain = maximumDomain;
        _cancelable = cancelable; _interactive = interactive; _upgrade = upgrade; _transform = transform;
        Require(!transform || !upgrade && enchantment is null);
        Require(screen.GetType() == (transform ? typeof(NDeckTransformSelectScreen) : upgrade ? typeof(NDeckUpgradeSelectScreen) : enchantment is null ? typeof(NDeckCardSelectScreen) : typeof(NDeckEnchantSelectScreen)));
        _selection = (Task<IEnumerable<CardModel>>)screen.GetType().GetMethod("CardsSelected", Type.EmptyTypes)!.Invoke(screen, null)!;
        Require(!_selection.IsCompleted && _domain.Length >= 1 && _domain.Length <= _maximumDomain && _domain.Distinct(ReferenceEqualityComparer.Instance).Count() == _domain.Length &&
            minimum >= 0 && minimum <= maximum && maximum is >= 1 and <= 3 && (!upgrade || maximum == 1));
    }

    private string Container => _upgrade ? "%UpgradeSinglePreviewContainer" : _enchantment is null ? "%PreviewContainer" : _maximum == 1 ? "%EnchantSinglePreviewContainer" : "%EnchantMultiPreviewContainer";
    private string Preview => _transform ? "TransformPreview" : _upgrade ? "UpgradePreview" : _enchantment is not null && _maximum == 1 ? "EnchantPreview" : _enchantment is null ? "%Cards" : "Cards";
    private string Confirm => !_upgrade && !_transform && _enchantment is null ? "%PreviewConfirm" : "Confirm";
    private string OpenPreview => !_transform && _enchantment is null ? "%Confirm" : "Confirm";
    private string PreviewBack => !_upgrade && !_transform && _enchantment is null ? "%PreviewCancel" : "Cancel";

    internal void Advance() => Read();

    internal DeckChoiceView? Read()
    {
        _ready = false;
        Require(!_failed && !_selection.IsFaulted && !_selection.IsCanceled);
        if (_selection.IsCompleted) { Require(Completed); return null; }
        if (_confirmed || _cancelled) { Require(_context()); return null; }
        Require(OwnsForeground && _context());
        if (_scrollTarget is not null) Require(++_scrollReads <= 128);
        if (!_screen.IsVisibleInTree()) return null;
        if (!Bind()) return null;
        bool preview = _container!.Visible && _container.IsVisibleInTree();
        if (preview) { if (!CheckPreview()) return null; }
        else if (!CheckHighlights()) return null;

        if (_desired is not null)
        {
            if (preview && (!SameSet(_selected, _desired) || _finish == "cancel"))
            {
                Require(_interactive && Ready(_previewBack));
                _highlightPending.UnionWith(_selected);
                _previewBindings = null; _previewRequested = false; _selected = Array.Empty<CardModel>();
                Input(_previewBack!.ForceClick); return null;
            }
            if (!SameSet(_selected, _desired))
            {
                Require(!preview);
                CardModel? remove = _selected.FirstOrDefault(c => !_desired.Contains(c));
                CardModel card = remove ?? _desired.First(c => !_selected.Contains(c));
                var holder = _holders!.SingleOrDefault(h => h.Visible && ReferenceEquals(h.CardModel, card));
                if (holder is null) { ScrollTo(card); return null; }
                Require(Clickable(holder));
                _highlightPending.Add(card);
                _selected = remove is null ? _selected.Append(card).ToArray() : _selected.Where(c => !ReferenceEquals(c, card)).ToArray();
                // Same native Pressed signal as EmitPressed, dispatched synchronously:
                // no deferred callback can outlive this exact holder binding.
                Input(() => Require(holder.EmitSignal(NCardHolder.SignalName.Pressed, holder) == Error.Ok));
                return null;
            }
            if (_finish == "cancel")
            {
                Require(_cancelable && !preview && Ready(_back));
                _cancelled = true; Input(_back!.ForceClick); return null;
            }
            if (_finish == "confirm")
            {
                Require(_selected.Length >= _minimum && _selected.Length <= _maximum);
                if (!preview)
                {
                    // Below-maximum optional selections require the native preview button.
                    if (_previewRequested) return null;
                    if (!Ready(_openPreview)) return null;
                    _previewRequested = true; Input(_openPreview!.ForceClick); return null;
                }
                if (!Ready(_confirm)) return null;
                _confirmed = true; Input(_confirm!.ForceClick); return null;
            }
            _desired = null;
        }
        if (!_interactive) return null;
        _ready = true;
        return new(_domain.ToArray(), _selected.ToArray(), _minimum, _maximum, _cancelable);
    }

    internal void Apply(string operation, CardModel? card = null)
    {
        Require(_interactive && _ready && _desired is null && !_confirmed && !_cancelled);
        var fresh = Read(); Require(fresh is not null && _ready && _context());
        _ready = false;
        _scrollPages = 0;
        switch (operation)
        {
            case "select":
                Require(card is not null && _domain.Contains(card) && !_selected.Contains(card) && _selected.Length < _maximum);
                _desired = _selected.Append(card).ToArray(); break;
            case "deselect":
                Require(card is not null && _selected.Contains(card));
                _desired = _selected.Where(c => !ReferenceEquals(c, card)).ToArray(); break;
            case "confirm":
                Require(card is null && _selected.Length >= _minimum && _selected.Length <= _maximum);
                _desired = _selected.ToArray(); _finish = "confirm"; break;
            case "cancel":
                Require(card is null && _cancelable);
                _desired = Array.Empty<CardModel>(); _finish = "cancel"; break;
            default: Require(false); break;
        }
    }

    private bool Bind()
    {
        var grid = _screen.GetNodeOrNull<NCardGrid>("%CardGrid"); Require(Valid(grid));
        if (grid!.IsAnimatingOut) return false;
        var holders = grid.CurrentlyDisplayedCardHolders.ToArray();
        if (_holders is null)
        {
            if (holders.Length == 0) return false;
            if (holders.Length != _domain.Length || holders.Count(h => h.Visible) != _domain.Length)
            {
                // A native grid recycles a bounded window of holders. The
                // request's complete public domain is independent of that pool.
                _gridCards = GridCards(grid);
                Require(SameSet(_gridCards, _domain));
                _scrollContainer = Field(grid, "_scrollContainer") as Control;
                Require(Valid(_scrollContainer));
            }
            Require(holders.Distinct(ReferenceEqualityComparer.Instance).Count() == holders.Length &&
                holders.All(h => Valid(h) && h.CardModel is {} c && _domain.Contains(c)) &&
                holders.Where(h => h.Visible).Select(h => h.CardModel).Distinct(ReferenceEqualityComparer.Instance).Count() == holders.Count(h => h.Visible));
            _grid = grid; _holders = holders;
            Require(holders.All(h => Valid(h.CardNode) && Valid(h.Hitbox)));
            _cardNodes = holders.Select(h => h.CardNode!).ToArray(); _hitboxes = holders.Select(h => (GodotObject)h.Hitbox!).ToArray();
            _holderCards = holders.Select(h => h.CardModel!).ToArray(); _holderVisible = holders.Select(h => h.Visible).ToArray();
            _container = _screen.GetNodeOrNull<Control>(Container); Require(Valid(_container));
            _preview = _container!.GetNodeOrNull<Control>(Preview); _confirm = _container.GetNodeOrNull<NConfirmButton>(Confirm);
            Require(Valid(_preview) && Valid(_confirm) && !_container.Visible);
            _openPreview = _screen.GetNodeOrNull<NConfirmButton>(OpenPreview);
            if (_interactive)
            {
                _previewBack = _container.GetNodeOrNull<NBackButton>(PreviewBack); Require(Valid(_previewBack));
                _back = _screen.GetNodeOrNull<NBackButton>("%Close"); if (_cancelable) Require(Valid(_back));
            }
        }
        Require(ReferenceEquals(grid, _grid) && holders.Length == _holders!.Length &&
            holders.Distinct(ReferenceEqualityComparer.Instance).Count() == holders.Length &&
            ReferenceEquals(_screen.GetNodeOrNull<Control>(Container), _container) &&
            ReferenceEquals(_container!.GetNodeOrNull<Control>(Preview), _preview) &&
            ReferenceEquals(_container.GetNodeOrNull<NConfirmButton>(Confirm), _confirm) &&
            ReferenceEquals(_screen.GetNodeOrNull<NConfirmButton>(OpenPreview), _openPreview));
        if (_interactive) Require(ReferenceEquals(_container.GetNodeOrNull<NBackButton>(PreviewBack), _previewBack) && ReferenceEquals(_screen.GetNodeOrNull<NBackButton>("%Close"), _back));
        if (_gridCards is not null)
        {
            Require(GridCards(grid).SequenceEqual(_gridCards) && ReferenceEquals(Field(grid, "_scrollContainer"), _scrollContainer));
            CheckWindow(holders);
        }
        if (_scrollTarget is not null)
        {
            // Only our outstanding pan may recycle this exact holder pool.
            // Hidden padding holders retain stale models in the native grid.
            Require(!_container!.Visible && _context());
            foreach (var h in holders)
            {
                int prior = Array.IndexOf(_holders!, h);
                Require(prior >= 0 && Valid(h) && !h.IsQueuedForDeletion() && ReferenceEquals(h.CardNode, _cardNodes![prior]) &&
                    ReferenceEquals(h.Hitbox, _hitboxes![prior]) && Valid(h.CardNode) && Valid(h.Hitbox) &&
                    !h.CardNode!.IsQueuedForDeletion() && !h.Hitbox.IsQueuedForDeletion() && ReferenceEquals(h.CardNode.Model, h.CardModel));
            }
            CheckNativeHighlights();
            float current = _scrollContainer!.Position.Y;
            Require(float.IsFinite(current) && Field(grid, "_targetDrag") is float target && target == _scrollDestination);
            bool allocated = holders.Any(h => h.Visible && ReferenceEquals(h.CardModel, _scrollTarget));
            if (!allocated && Math.Abs(current - _scrollDestination) > 0.1f) return false;
            // Native top/bottom viewport predicates can alternate adjacent
            // windows at a settled page. The ordered window was just validated;
            // a repeated first original ends this page's presentation drain,
            // allowing the same explicit request to continue its bounded pan.
            if (!allocated && !_scrollWindows.Add(holders.First(h => h.Visible).CardModel!)) _scrollAllocationDrained = true;
            if (!allocated && !_scrollAllocationDrained)
            {
                // UpdateScrollPosition allocates at the old position, then
                // moves. A snapping frame may leave more rows to recycle with
                // no further motion. Finish that native presentation work under
                // the same pan owner; never emit a second selection or gesture.
                var cards = holders.Select(h => h.CardModel).ToArray();
                var visible = holders.Select(h => h.Visible).ToArray();
                var allocate = typeof(NCardGrid).GetMethod("AllocateCardHolders", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                Require(allocate is not null && allocate.ReturnType == typeof(void) && allocate.GetParameters().Length == 0);
                Input(() => allocate.Invoke(grid, null));
                var after = grid.CurrentlyDisplayedCardHolders.ToArray();
                _scrollAllocationDrained = after.Length == holders.Length && after.Select((h, i) =>
                    ReferenceEquals(h, holders[i]) && ReferenceEquals(h.CardModel, cards[i]) && h.Visible == visible[i]).All(x => x);
                // Revalidate the entire pool, domain, owner and selected set on
                // the next read before accepting a binding or touching a card.
                return false;
            }
            // Stop residual easing before freezing a new binding or selecting.
            Input(() => grid.SetScrollPosition(current));
            _holders = holders; _cardNodes = holders.Select(h => h.CardNode!).ToArray();
            _hitboxes = holders.Select(h => (GodotObject)h.Hitbox!).ToArray();
            _holderCards = holders.Select(h => h.CardModel!).ToArray(); _holderVisible = holders.Select(h => h.Visible).ToArray();
            _highlightPending.UnionWith(holders.Where(h => h.Visible).Select(h => h.CardModel!));
            _scrollTarget = null;
        }
        Require(holders.Select((h, i) => ReferenceEquals(h, _holders![i])).All(x => x));
        for (int i = 0; i < holders.Length; i++)
        {
            var h = holders[i]; Require(Valid(h) && Valid(h.CardNode) && Valid(h.Hitbox) && ReferenceEquals(h.CardNode, _cardNodes![i]) &&
                ReferenceEquals(h.Hitbox, _hitboxes![i]) && ReferenceEquals(h.CardNode!.Model, h.CardModel) &&
                ReferenceEquals(h.CardModel, _holderCards![i]) && h.Visible == _holderVisible![i] && _domain.Contains(h.CardModel!));
        }
        return true;
    }

    private CardModel[] GridCards(NCardGrid grid)
    {
        Require(Field(grid, "_cards") is IEnumerable<CardModel>);
        var cards = ((IEnumerable<CardModel>)Field(grid, "_cards")!).Take(_maximumDomain + 1).ToArray();
        Require(cards.Length >= 1 && cards.Length <= _maximumDomain && cards.Distinct(ReferenceEqualityComparer.Instance).Count() == cards.Length);
        return cards;
    }
    private void CheckWindow(NGridCardHolder[] holders)
    {
        Require(holders.All(h => Valid(h) && !h.IsQueuedForDeletion() && h.CardModel is not null));
        var indices = holders.Where(h => h.Visible).Select(h => Array.IndexOf(_gridCards!, h.CardModel)).ToArray();
        Require(indices.Length > 0 && indices[0] >= 0 && indices.Select((value, index) => value == indices[0] + index).All(x => x));
    }
    private void CheckNativeHighlights()
    {
        Require(Field(_grid!, "_highlightedCards") is IEnumerable<CardModel>);
        var cards = ((IEnumerable<CardModel>)Field(_grid!, "_highlightedCards")!).Take(65).ToArray();
        Require(cards.Distinct(ReferenceEqualityComparer.Instance).Count() == cards.Length && SameSet(cards, _selected));
    }
    private void ScrollTo(CardModel card)
    {
        Require(_gridCards is not null && _scrollTarget is null && !_container!.Visible && ++_scrollPages <= 64 &&
            typeof(NCardGrid).GetProperty("CanScroll", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(_grid) is true);
        var allocated = _holders!.Where(h => h.Visible).Select(h => Array.IndexOf(_gridCards!, h.CardModel)).ToArray();
        int index = Array.IndexOf(_gridCards!, card);
        Require(index >= 0 && allocated.Length > 0 && (index < allocated[0] || index > allocated[^1]));
        float current = _scrollContainer!.Position.Y, height = _grid!.Size.Y;
        float top = (float)typeof(NCardGrid).GetProperty("ScrollLimitTop", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(_grid)!;
        float bottom = (float)typeof(NCardGrid).GetProperty("ScrollLimitBottom", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(_grid)!;
        Require(float.IsFinite(current) && float.IsFinite(height) && height > 0 && float.IsFinite(top) && float.IsFinite(bottom));
        _scrollDestination = Math.Clamp(current + (index < allocated[0] ? height : -height), Math.Min(top, bottom), Math.Max(top, bottom));
        Require(Math.Abs(_scrollDestination - current) > 0.1f);
        _scrollTarget = card; _scrollReads = 0; _scrollAllocationDrained = false; _scrollWindows.Clear();
        // Pan input changes the native target; _Process performs allocation.
        // SetScrollPosition alone changes position without allocating any rows.
        using var gesture = new InputEventPanGesture { Delta = new Vector2(0, (current - _scrollDestination) / 50f) };
        Input(() => _grid._GuiInput(gesture));
        Require(Field(_grid, "_targetDrag") is float changed && float.IsFinite(changed) && Math.Abs(changed - _scrollDestination) <= 0.01f);
        _scrollDestination = (float)Field(_grid, "_targetDrag")!;
    }

    private bool CheckHighlights()
    {
        if (_gridCards is not null) CheckNativeHighlights();
        bool settled = true;
        foreach (var h in _holders!.Where(h => h.Visible))
        {
            Require(h.CardNode!.CardHighlight?.Material is ShaderMaterial);
            var endpoint = CardSelectionV1NativeRules.ClassifyHighlight(((ShaderMaterial)h.CardNode.CardHighlight.Material).GetShaderParameter("width").AsSingle());
            var expected = _selected.Contains(h.CardModel!) ? CardSelectionV1HighlightEndpoint.Selected : CardSelectionV1HighlightEndpoint.Unselected;
            if (endpoint == expected) _highlightPending.Remove(h.CardModel!);
            else
            {
                // AnimShow/AnimHide creates a tween: the same-frame shader may
                // still be at its old endpoint. Only our exact outstanding
                // changes may wait there; never redispatch the native input.
                Require(endpoint == CardSelectionV1HighlightEndpoint.Transient || _highlightPending.Contains(h.CardModel!));
                settled = false;
            }
        }
        return settled;
    }

    private bool CheckPreview()
    {
        var bindings = new List<object>();
        if (_transform)
        {
            Require(_preview is NTransformPreview);
            var before = _preview!.GetNodeOrNull<Control>("%Before");
            var after = _preview.GetNodeOrNull<Control>("%After");
            Require(Valid(before) && Valid(after));
            var originals = before!.GetChildren().Select(n => CheckHolder(n, bindings)).ToArray();
            Require(originals.Length == _selected.Length && SameSet(originals, _selected));
            bindings.Add(before); bindings.Add(after!);
        }
        else if (_upgrade)
        {
            Require(_selected.Length == 1 && _preview is NUpgradePreview p && ReferenceEquals(p.Card, _selected[0]));
            bindings.Add(_selected[0]);
        }
        else if (_enchantment is not null && _maximum == 1)
        {
            var before = Field(_preview!, "_before") as Control; var after = Field(_preview!, "_after") as Control; Require(Valid(before) && Valid(after));
            var originals = before!.GetChildren().ToArray(); var previews = after!.GetChildren().ToArray();
            if (originals.Concat(previews).Any(n => n.IsQueuedForDeletion()))
            {
                // NEnchantPreview.Init queues its scene's initial hitboxes (or
                // old previews on reselection) before adding the new holders.
                // They remain children until frame end. Wait only for our
                // outstanding input, before any preview has been accepted;
                // never confirm, redispatch or forgive a bound preview change.
                Require(_desired is not null && _previewBindings is null);
                return false;
            }
            Require(originals.Length == 1 && previews.Length == 1);
            var original = CheckHolder(originals[0], bindings); var clone = CheckHolder(previews[0], bindings);
            Require(ReferenceEquals(original, _selected.Single()) && !ReferenceEquals(clone, original) && clone.IsEnchantmentPreview &&
                ReferenceEquals(clone.Owner, original.Owner) && ReferenceEquals(clone.RunState, original.RunState) && clone.Id.Entry == original.Id.Entry && clone.CurrentUpgradeLevel == original.CurrentUpgradeLevel &&
                clone.Enchantment is {} e && ReferenceEquals(e.Card, clone) && e.Id.Entry == _enchantment.Id.Entry && e.Amount == _amount);
            bindings.Add(before); bindings.Add(after); bindings.Add(clone.Enchantment!);
        }
        else
        {
            var nodes = _preview!.GetChildren().ToArray(); Require(nodes.Length == _selected.Length);
            var originals = nodes.Select(n => CheckHolder(n, bindings)).ToArray(); Require(originals.Distinct(ReferenceEqualityComparer.Instance).Count() == originals.Length && SameSet(originals, _selected));
        }
        _previewBindings ??= bindings.ToArray();
        Require(bindings.Count == _previewBindings.Length && bindings.Select((b, i) => ReferenceEquals(b, _previewBindings[i])).All(x => x));
        return true;
    }
    private CardModel CheckHolder(Node node, List<object> bindings)
    {
        Require(node is NPreviewCardHolder); var holder = (NPreviewCardHolder)node;
        Require(Valid(holder) && Valid(holder.CardNode) && holder.CardModel is not null && ReferenceEquals(holder.CardNode!.Model, holder.CardModel) && holder.IsVisibleInTree() && holder.CardNode.IsVisibleInTree());
        bindings.Add(holder); bindings.Add(holder.CardNode!); bindings.Add(holder.CardModel!); return holder.CardModel!;
    }
    private static bool Clickable(NGridCardHolder h) => h.IsVisibleInTree() && h.CardNode!.IsVisibleInTree() && h.Hitbox.IsVisibleInTree() && h.Hitbox.IsEnabled &&
        typeof(NCardHolder).GetField("_isClickable", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)?.GetValue(h) is true;
    private static bool Ready(NConfirmButton? button) => Valid(button) && button.IsVisibleInTree() && button.IsEnabled;
    private static bool Ready(NBackButton? button) => Valid(button) && button.IsVisibleInTree() && button.IsEnabled;
    private void Input(Action action) { Require(_context() && ++_inputs <= 256); action(); Require(_context()); }
    private bool SelectedExactly()
    {
        if (!_selection.IsCompletedSuccessfully) return false;
        var result = _selection.Result.Take(4).ToArray();
        var expected = _cancelled ? Array.Empty<CardModel>() : _selected;
        return result.Distinct(ReferenceEqualityComparer.Instance).Count() == result.Length && SameSet(result, expected);
    }
    private static bool SameSet(CardModel[] a, CardModel[] b) => a.Length == b.Length && a.All(b.Contains);
    private static object? Field(object value, string name) => value.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)?.GetValue(value);
    private static bool Valid([System.Diagnostics.CodeAnalysis.NotNullWhen(true)] GodotObject? value) => value is not null && GodotObject.IsInstanceValid(value);
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool ok, [System.Runtime.CompilerServices.CallerLineNumber] int boundary = 0)
    { if (!ok) { _failed = true; throw new InvalidOperationException("Owned pickup selection changed at boundary " + boundary + "."); } }
}
