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
    private readonly int _amount, _minimum, _maximum;
    private readonly bool _interactive, _cancelable, _upgrade, _transform;
    private readonly Task<IEnumerable<CardModel>> _selection;
    private NCardGrid? _grid;
    private NGridCardHolder[]? _holders;
    private NCard[]? _cardNodes;
    private GodotObject[]? _hitboxes;
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
        IReadOnlyList<Control>? ancestors = null, bool transform = false)
        : this(screen, overlays, domain, context, enchantment, amount, minimum, maximum, cancelable, true, upgrade, ancestors, transform) { }

    private PinnedDeckCardChoice(Control screen, NOverlayStack overlays, IReadOnlyList<CardModel> domain,
        Func<bool> context, EnchantmentModel? enchantment, int amount, int minimum, int maximum, bool cancelable, bool interactive, bool upgrade = false,
        IReadOnlyList<Control>? ancestors = null, bool transform = false)
    {
        _screen = screen; _overlays = overlays; _domain = domain.ToArray(); _context = context;
        _ancestors = new(overlays, ancestors);
        _enchantment = enchantment; _amount = amount; _minimum = minimum; _maximum = maximum;
        _cancelable = cancelable; _interactive = interactive; _upgrade = upgrade; _transform = transform;
        Require(!transform || !upgrade && enchantment is null);
        Require(screen.GetType() == (transform ? typeof(NDeckTransformSelectScreen) : upgrade ? typeof(NDeckUpgradeSelectScreen) : enchantment is null ? typeof(NDeckCardSelectScreen) : typeof(NDeckEnchantSelectScreen)));
        _selection = (Task<IEnumerable<CardModel>>)screen.GetType().GetMethod("CardsSelected", Type.EmptyTypes)!.Invoke(screen, null)!;
        Require(!_selection.IsCompleted && _domain.Length is >= 1 and <= 64 && _domain.Distinct(ReferenceEqualityComparer.Instance).Count() == _domain.Length &&
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
                var holder = _holders!.Single(h => ReferenceEquals(h.CardModel, card));
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
            if (holders.Length != _domain.Length) return false;
            Require(holders.Distinct(ReferenceEqualityComparer.Instance).Count() == holders.Length &&
                holders.All(h => Valid(h) && h.CardModel is {} c && _domain.Contains(c)) &&
                holders.Select(h => h.CardModel).Distinct(ReferenceEqualityComparer.Instance).Count() == _domain.Length);
            _grid = grid; _holders = holders;
            Require(holders.All(h => Valid(h.CardNode) && Valid(h.Hitbox)));
            _cardNodes = holders.Select(h => h.CardNode!).ToArray(); _hitboxes = holders.Select(h => (GodotObject)h.Hitbox!).ToArray();
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
            holders.Select((h, i) => ReferenceEquals(h, _holders[i])).All(x => x) &&
            ReferenceEquals(_screen.GetNodeOrNull<Control>(Container), _container) &&
            ReferenceEquals(_container!.GetNodeOrNull<Control>(Preview), _preview) &&
            ReferenceEquals(_container.GetNodeOrNull<NConfirmButton>(Confirm), _confirm) &&
            ReferenceEquals(_screen.GetNodeOrNull<NConfirmButton>(OpenPreview), _openPreview));
        if (_interactive) Require(ReferenceEquals(_container.GetNodeOrNull<NBackButton>(PreviewBack), _previewBack) && ReferenceEquals(_screen.GetNodeOrNull<NBackButton>("%Close"), _back));
        for (int i = 0; i < holders.Length; i++)
        {
            var h = holders[i]; Require(Valid(h) && Valid(h.CardNode) && Valid(h.Hitbox) && ReferenceEquals(h.CardNode, _cardNodes![i]) &&
                ReferenceEquals(h.Hitbox, _hitboxes![i]) && ReferenceEquals(h.CardNode!.Model, h.CardModel) && _domain.Contains(h.CardModel!));
        }
        return true;
    }

    private bool CheckHighlights()
    {
        bool settled = true;
        foreach (var h in _holders!)
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
