using System;
using System.Reflection;
using System.Linq;
using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using System.Collections.Generic;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

public sealed class GenericEventV7CardAdapter : ICardSelectionV1NativeAdapter
{
    private const string HighlightWidthParameter = "width";

    private readonly GenericEventV7Binding _binding;
    private readonly CardSelectionV1ParentContext _context;
    private readonly NCardGridSelectionScreen _screen;
    private readonly NCardGrid _grid;
    private readonly Control _previewContainer;
    private readonly Control _preview;
    private readonly NConfirmButton _confirm;
    private readonly Action _confirmDispatch;
    private readonly Task<IEnumerable<CardModel>> _completionTask;
    private readonly CandidateBinding[] _candidates;

    private CardSelectionV1NativeCandidate[] _cachedCandidates;
    private object? _cachedPreviewIdentity;
    private object[] _cachedPreviewOriginals = Array.Empty<object>();
    private CardSelectionV1NativeControl? _cachedConfirm;
    private bool _cachedPreviewOpen;
    private CardSelectionV1TaskState _taskState = CardSelectionV1TaskState.Incomplete;
    private object[] _taskResult = Array.Empty<object>();
    private bool _disposed;
    private object[]? _enchantPreviewBindings;

    internal GenericEventV7CardAdapter(
        GenericEventV7Binding binding,
        CardSelectionV1ParentContext context,
        NCardGridSelectionScreen screen)
    {
        _binding = binding ?? throw new ArgumentNullException(nameof(binding));
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _screen = screen ?? throw new ArgumentNullException(nameof(screen));
        if (!_binding.MatchesAcceptedParent(_context) ||
            !TryPrepareSurface(_binding, _screen,
                out NCardGrid grid,
                out CandidateBinding[] candidateBindings,
                out CardSelectionV1NativeCandidate[] candidates,
                out Control previewContainer,
                out Control preview,
                out NConfirmButton confirm,
                out _))
            throw new InvalidOperationException("Event selector binding is unsupported.");
        _grid = grid;
        _candidates = candidateBindings;
        _cachedCandidates = candidates;
        _previewContainer = previewContainer;
        _preview = preview;
        _confirm = confirm;
        _confirmDispatch = _confirm.ForceClick;

        _completionTask = _screen.CardsSelected() ??
            throw new InvalidOperationException("Event selector task was unavailable.");
        if (_completionTask.IsCompleted)
            throw new InvalidOperationException("Event selector task was not fresh.");
    }

    internal static bool IsReady(
        GenericEventV7Binding binding,
        NCardGridSelectionScreen screen,
        out GenericEventDiagnosticCode diagnostic)
    {
        diagnostic = GenericEventDiagnosticCode.PrepareBinding;
        try
        {
            return binding is not null && screen is not null &&
                TryPrepareSurface(binding, screen, out _, out _, out _,
                    out _, out _, out _, out diagnostic);
        }
        catch { return false; }
    }

    public CardSelectionV1SurfaceCapture CaptureSurface()
    {
        if (_disposed) return Unsupported();
        try { return CaptureCore(); }
        catch { return Unsupported(); }
    }

    public void Dispose() => _disposed = true;

    private CardSelectionV1SurfaceCapture CaptureCore()
    {
        if (!TryBoundForeground(out bool selectorClosed) ||
            !TryCopyDeck(out CardSelectionV1DeckCard[] deck))
            return Unsupported();
        SnapshotTask();
        if (!selectorClosed && _context.Operation == CardSelectionV1Operation.Enchant &&
            (!EnchantmentScreenMatches(_binding, _screen) ||
             _taskState == CardSelectionV1TaskState.Incomplete && _binding.Originals.Any(c =>
                 c.Enchantment is not null || !_binding.EnchantmentModel!.CanEnchant(c))))
            return Unsupported();

        bool selectorTop = !selectorClosed;
        CardSelectionV1Phase phase;
        bool previewOpen = false;
        object? previewIdentity = _cachedPreviewIdentity;
        object[] previewOriginals = _cachedPreviewOriginals;
        CardSelectionV1NativeControl? confirm = _cachedConfirm;
        CardSelectionV1NativeCandidate[] candidates = _cachedCandidates;

        if (selectorClosed)
        {
            phase = CardSelectionV1Phase.Submitted;
            previewIdentity = null;
            previewOriginals = Array.Empty<object>();
            confirm = null;
        }
        else if (!Valid(_screen))
        {
            return Unsupported();
        }
        else if (!_screen.IsVisibleInTree())
        {
            phase = CardSelectionV1Phase.Transient;
        }
        else if (_taskState != CardSelectionV1TaskState.Incomplete)
        {
            phase = CardSelectionV1Phase.Transient;
            previewOpen = _cachedPreviewOpen;
        }
        else
        {
            if (!ReferenceEquals(_screen.GetNodeOrNull<NCardGrid>("%CardGrid"), _grid) ||
                !GridReady(_grid) ||
                !TrySnapshotHolders(_grid, out NGridCardHolder[] holders) ||
                !TryCaptureBindings(holders, _candidates, out candidates,
                    out bool allSettled))
                return Unsupported();
            _cachedCandidates = candidates;
            if (!TryCapturePreview(out previewOpen, out previewIdentity,
                    out previewOriginals, out confirm))
                return Unsupported();
            _cachedPreviewOpen = previewOpen;
            _cachedPreviewIdentity = previewIdentity;
            _cachedPreviewOriginals = previewOriginals;
            _cachedConfirm = confirm;

            bool previewReady = previewOpen && previewOriginals.Length == 1 &&
                confirm is not null && confirm.Visible && confirm.Enabled &&
                SelectedModelIs(candidates, previewOriginals[0]);
            if (!allSettled || _grid.IsAnimatingOut)
                phase = CardSelectionV1Phase.Transient;
            else if (previewReady)
                phase = CardSelectionV1Phase.Preview;
            else if (previewOpen || CountSelected(candidates) == 1)
                phase = CardSelectionV1Phase.Transient;
            else
                phase = CardSelectionV1Phase.Selecting;
        }

        if (_binding.Failed || _binding.ChosenTask?.IsFaulted == true || _binding.ChosenTask?.IsCanceled == true || _binding.RequestTask?.IsFaulted == true || _binding.RequestTask?.IsCanceled == true)
            return Unsupported();
        bool effectCompletion = selectorClosed && _taskState == CardSelectionV1TaskState.Succeeded && _binding.EffectCompleted(_taskResult);
        if(_binding.Failed)return Unsupported();
        return new CardSelectionV1SurfaceCapture(
            CardSelectionV1SurfaceStatus.Available,
            _context.ParentReceiptIdentity,
            _binding.Run,
            _binding.Player,
            _binding.Room,
            _binding.Map,
            _binding.Option,
            _binding.Controller,
            _screen,
            _completionTask,
            previewIdentity,
            CardSelectionV1ParentKind.Event,
            _context.Operation,
            1,
            1,
            CardSelectionV1CommitMode.PreviewConfirm,
            phase,
            selectorTop,
            selectorClosed,
            previewOpen,
            true,
            _binding.DomainCount,
            true,
            _taskState,
            effectCompletion,
            _taskResult,
            previewOriginals,
            candidates,
            deck,
            Array.Empty<CardSelectionV1Replacement>(),
            null,
            confirm,
            _context.Enchantment);
    }

    private bool TryBoundForeground(out bool selectorClosed)
    {
        selectorClosed = false;
        if (!BoundForeground(true) || CardSelectCmd.Selector is not null) return false;
        int count = _binding.Overlays.ScreenCount;
        if (count == 0)
        {
            selectorClosed = true;
            return true;
        }
        return count == 1 && ReferenceEquals(_binding.Overlays.Peek(), _screen);
    }

    private bool BoundForeground(bool allowClosed)
    {
        if (!ReferenceEquals(MegaCrit.Sts2.Core.Nodes.NRun.Instance, _binding.Run) ||
            !ReferenceEquals(_binding.Run.EventRoom, _binding.Room) ||
            !ReferenceEquals(MegaCrit.Sts2.Core.Nodes.Rooms.NEventRoom.Instance,
                _binding.Room) ||
            !ReferenceEquals(_binding.Run.GlobalUi?.MapScreen, _binding.Map) ||
            !ReferenceEquals(_binding.Run.GlobalUi?.Overlays, _binding.Overlays) ||
            !ReferenceEquals(MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen.Instance,
                _binding.Map) ||
            !Valid(_binding.Run) || !Valid(_binding.Room) || !Valid(_binding.Map) ||
            !Valid(_binding.Overlays) || !_binding.Room.IsVisibleInTree() ||
            _binding.Map.IsOpen || _binding.Map.IsTravelEnabled || _binding.Map.IsTraveling ||
            _binding.Room.CustomEventNode is not null ||
            _binding.Room.EmbeddedCombatRoom is not null ||
            !ReferenceEquals(_binding.EventModel.Owner, _binding.Player) ||
            !_binding.MatchesChildBinding())
            return false;
        int count = _binding.Overlays.ScreenCount;
        return count == 1 && ReferenceEquals(_binding.Overlays.Peek(), _screen) ||
            allowClosed && count == 0;
    }

    private static bool TryPrepareSurface(
        GenericEventV7Binding binding,
        NCardGridSelectionScreen screen,
        out NCardGrid grid,
        out CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates,
        out Control previewContainer,
        out Control preview,
        out NConfirmButton confirm,
        out GenericEventDiagnosticCode diagnostic)
    {
        grid = null!;
        bindings = Array.Empty<CandidateBinding>();
        candidates = Array.Empty<CardSelectionV1NativeCandidate>();
        previewContainer = null!;
        preview = null!;
        confirm = null!;
        diagnostic = GenericEventDiagnosticCode.PrepareBinding;
        if (!binding.Ready) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareScreen;
        if (!(binding.Operation == CardSelectionV1Operation.Enchant
            ? screen.GetType() == typeof(NDeckEnchantSelectScreen) && EnchantmentScreenMatches(binding, screen)
            : screen.GetType() == typeof(NDeckUpgradeSelectScreen)) ||
            !Valid(screen) || !screen.IsVisibleInTree()) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareExternalSelector;
        if (CardSelectCmd.Selector is not null) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareDeck;
        if (!binding.MatchesCurrentDeck()) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareForeground;
        if (!InitialForeground(binding, screen)) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareGridNode;
        grid = RequiredNode<NCardGrid>(screen, "%CardGrid");
        diagnostic = GenericEventDiagnosticCode.PrepareGridState;
        if (!GridReady(grid)) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareHolders;
        if (!TrySnapshotHolders(grid, out NGridCardHolder[] holders)) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
        if (!TryCreateBindings(holders, binding.EligibleOriginals, out bindings, out candidates)) return false;
        diagnostic = GenericEventDiagnosticCode.PreparePreviewNodes;
        bool enchant = binding.Operation == CardSelectionV1Operation.Enchant;
        previewContainer = RequiredNode<Control>(screen,
            enchant ? "%EnchantSinglePreviewContainer" : "%UpgradeSinglePreviewContainer");
        preview = enchant ? RequiredNode<NEnchantPreview>(previewContainer, "EnchantPreview") :
            RequiredNode<NUpgradePreview>(previewContainer, "UpgradePreview");
        confirm = RequiredNode<NConfirmButton>(previewContainer, "Confirm");
        diagnostic = GenericEventDiagnosticCode.PreparePreviewState;
        return PreviewTypeValid(preview, enchant) && ValidExact(confirm) &&
            !previewContainer.Visible && (enchant || ((NUpgradePreview)preview).Card is null);
    }

    private static bool InitialForeground(
        GenericEventV7Binding binding,
        NCardGridSelectionScreen screen) =>
        ReferenceEquals(MegaCrit.Sts2.Core.Nodes.NRun.Instance, binding.Run) &&
        ReferenceEquals(binding.Run.EventRoom, binding.Room) &&
        ReferenceEquals(MegaCrit.Sts2.Core.Nodes.Rooms.NEventRoom.Instance,
            binding.Room) &&
        ReferenceEquals(binding.Run.GlobalUi?.MapScreen, binding.Map) &&
        ReferenceEquals(binding.Run.GlobalUi?.Overlays, binding.Overlays) &&
        ReferenceEquals(MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen.Instance,
            binding.Map) &&
        Valid(binding.Run) && Valid(binding.Room) && Valid(binding.Map) &&
        Valid(binding.Overlays) && binding.Room.IsVisibleInTree() &&
        !binding.Map.IsOpen && !binding.Map.IsTravelEnabled && !binding.Map.IsTraveling &&
        binding.Room.CustomEventNode is null && binding.Room.EmbeddedCombatRoom is null &&
        ReferenceEquals(binding.EventModel.Owner, binding.Player) &&
        !binding.EventModel.IsFinished &&
        binding.Overlays.ScreenCount == 1 &&
        ReferenceEquals(binding.Overlays.Peek(), screen);

    private bool TryCapturePreview(
        out bool open,
        out object? identity,
        out object[] originals,
        out CardSelectionV1NativeControl? confirm)
    {
        open = false;
        identity = null;
        originals = Array.Empty<object>();
        confirm = null;
        bool enchant = _context.Operation == CardSelectionV1Operation.Enchant;
        if (!Valid(_previewContainer) || !PreviewTypeValid(_preview, enchant) ||
            !ValidExact(_confirm) ||
            !ReferenceEquals(_screen.GetNodeOrNull<Control>(
                enchant ? "%EnchantSinglePreviewContainer" : "%UpgradeSinglePreviewContainer"), _previewContainer) ||
            !ReferenceEquals(_previewContainer.GetNodeOrNull<Control>(
                enchant ? "EnchantPreview" : "UpgradePreview"), _preview) ||
            !ReferenceEquals(_previewContainer.GetNodeOrNull<NConfirmButton>("Confirm"), _confirm) ||
            enchant && !EnchantmentScreenMatches(_binding, _screen))
            return false;
        open = _previewContainer.Visible && _previewContainer.IsVisibleInTree();
        if (!open) return true;
        identity = _preview;
        if (enchant)
        {
            if (!TryEnchantPreview(out CardModel original)) return false;
            originals = new object[] { original };
        }
        else if (((NUpgradePreview)_preview).Card is { } original)
            originals = new object[] { original };
        confirm = new CardSelectionV1NativeControl(
            _confirm, _confirm.IsVisibleInTree(), _confirm.IsEnabled, _confirmDispatch);
        return true;
    }

    private void SnapshotTask()
    {
        if (_taskState != CardSelectionV1TaskState.Incomplete ||
            !_completionTask.IsCompleted) return;
        if (_completionTask.IsCanceled)
        {
            _taskState = CardSelectionV1TaskState.Canceled;
            return;
        }
        if (_completionTask.IsFaulted || !_completionTask.IsCompletedSuccessfully)
        {
            _taskState = CardSelectionV1TaskState.Faulted;
            return;
        }
        try
        {
            IEnumerable<CardModel>? result = _completionTask.Result;
            if (result is null)
            {
                _taskState = CardSelectionV1TaskState.Faulted;
                return;
            }
            var values = new List<object>();
            var seen = new HashSet<object>(ReferenceEqualityComparer.Instance);
            foreach (CardModel? model in result)
            {
                if (model is null || values.Count >= _binding.Prefs.MaxSelect ||
                    !seen.Add(model))
                {
                    _taskResult = Array.Empty<object>();
                    _taskState = CardSelectionV1TaskState.Faulted;
                    return;
                }
                values.Add(model);
            }
            _taskResult = values.ToArray();
            _taskState = CardSelectionV1TaskState.Succeeded;
        }
        catch
        {
            _taskResult = Array.Empty<object>();
            _taskState = CardSelectionV1TaskState.Faulted;
        }
    }

    private static bool TryCreateBindings(
        IReadOnlyList<NGridCardHolder> holdersSnapshot,
        IReadOnlyList<CardModel> expected,
        out CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates)
    {
        bindings = Array.Empty<CandidateBinding>();
        candidates = Array.Empty<CardSelectionV1NativeCandidate>();
        var found = new List<CandidateBinding>();
        var expectedModels = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (CardModel model in expected)
            if (model is null || !expectedModels.Add(model)) return false;
        var foundModels = new HashSet<object>(ReferenceEqualityComparer.Instance);
        for (int index = 0; index < holdersSnapshot.Count; index++)
        {
            NGridCardHolder holder = holdersSnapshot[index];
            if (holder.CardModel is not CardModel displayed ||
                !expectedModels.Contains(displayed) || !foundModels.Add(displayed))
                return false;
            CardModel? model = holder.CardModel;
            NCard? card = holder.CardNode;
            NClickableControl? hitbox = holder.Hitbox;
            NCardHighlight? highlight = card?.CardHighlight;
            if (model is null || card is null || hitbox is null || highlight is null ||
                !ValidExact(card) || !Valid(hitbox) || !ValidExact(highlight) ||
                highlight.Material is not ShaderMaterial material ||
                !ValidExact(material) ||
                !CardSelectionV1NativeRules.IsStableKey(model.Id.Entry))
                return false;
            found.Add(new CandidateBinding(index, holder, model, card, hitbox,
                highlight, material));
        }
        if (found.Count != expected.Count || found.Count is < 2 or > 64)
            return false;
        bindings = found.ToArray();
        return TryCaptureBindings(holdersSnapshot, bindings, out candidates,
            out bool settled) &&
            settled && InitialCandidatesValid(candidates);
    }

    private static bool TrySnapshotHolders(
        NCardGrid grid,
        out NGridCardHolder[] holders)
    {
        holders = Array.Empty<NGridCardHolder>();
        var found = new List<NGridCardHolder>();
        var seen = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (NGridCardHolder? holder in grid.CurrentlyDisplayedCardHolders)
        {
            if (holder is null || found.Count >= 64 || !ValidExact(holder) ||
                !seen.Add(holder)) return false;
            found.Add(holder);
        }
        holders = found.ToArray();
        return true;
    }

    // Direct holder input does not depend on scroll geometry. Retain the exact
    // allocated domain and the native holder's input gate, including off-screen cards.
    private static bool GridReady(NCardGrid grid) =>
        ValidExact(grid) && !grid.IsAnimatingOut;

    private static bool HolderClickable(NGridCardHolder holder) =>
        typeof(NCardHolder).GetField("_isClickable",
            BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
            ?.GetValue(holder) is true;

    private static bool TryCaptureBindings(
        IReadOnlyList<NGridCardHolder> holdersSnapshot,
        CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates,
        out bool allSettled)
    {
        candidates = new CardSelectionV1NativeCandidate[bindings.Length];
        allSettled = true;
        if (holdersSnapshot.Count != bindings.Length) return false;
        for (int index = 0; index < bindings.Length; index++)
        {
            CandidateBinding binding = bindings[index];
            if (!ReferenceEquals(holdersSnapshot[index], binding.Holder) ||
                !ValidExact(binding.Holder) || !ValidExact(binding.Card) ||
                !Valid(binding.Hitbox) || !ValidExact(binding.Highlight) ||
                !ValidExact(binding.Material) ||
                !ReferenceEquals(binding.Holder.CardModel, binding.Model) ||
                !ReferenceEquals(binding.Holder.CardNode, binding.Card) ||
                !ReferenceEquals(binding.Holder.Hitbox, binding.Hitbox) ||
                !ReferenceEquals(binding.Card.CardHighlight, binding.Highlight) ||
                !ReferenceEquals(binding.Highlight.Material, binding.Material) ||
                !string.Equals(binding.Model.Id.Entry, binding.StableKey,
                    StringComparison.Ordinal) ||
                binding.Model.CurrentUpgradeLevel != binding.UpgradeLevel)
                return false;
            CardSelectionV1HighlightEndpoint endpoint =
                CardSelectionV1NativeRules.ClassifyHighlight(
                    binding.Material.GetShaderParameter(HighlightWidthParameter).AsSingle());
            bool settled = endpoint != CardSelectionV1HighlightEndpoint.Transient;
            allSettled &= settled;
            candidates[index] = new CardSelectionV1NativeCandidate(
                binding.Slot,
                binding.StableKey,
                binding.Holder,
                binding.Model,
                binding.Card,
                binding.UpgradeLevel,
                binding.Holder.IsVisibleInTree() && binding.Card.IsVisibleInTree() &&
                    binding.Hitbox.IsVisibleInTree(),
                binding.Hitbox.IsEnabled && HolderClickable(binding.Holder),
                endpoint == CardSelectionV1HighlightEndpoint.Selected,
                settled,
                binding.Dispatch);
        }
        return true;
    }

    private bool TryCopyDeck(out CardSelectionV1DeckCard[] deck)
    {
        var copied = new List<CardSelectionV1DeckCard>();
        var seen = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (CardModel? card in _binding.Player.Deck.Cards)
        {
            if (card is null || copied.Count >= CardSelectionV1Limits.MaximumDeckCards ||
                !seen.Add(card) || !CardSelectionV1NativeRules.IsStableKey(card.Id.Entry) ||
                card.CurrentUpgradeLevel < 0)
            {
                deck = Array.Empty<CardSelectionV1DeckCard>();
                return false;
            }
            copied.Add(new CardSelectionV1DeckCard(
                card, card.Id.Entry, card.CurrentUpgradeLevel,
                _context.Operation == CardSelectionV1Operation.Enchant ? GenericEventV7Binding.CopyEnchantment(card) : null));
        }
        deck = copied.ToArray();
        return true;
    }

    private static bool PreviewTypeValid(Control preview, bool enchant) =>
        Valid(preview) && preview.GetType() == (enchant ? typeof(NEnchantPreview) : typeof(NUpgradePreview));

    private static object? Field(object obj, string name) =>
        obj.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)?.GetValue(obj);

    private static bool EnchantmentScreenMatches(GenericEventV7Binding b, NCardGridSelectionScreen screen) =>
        b.Enchantment is { } requested && b.EnchantmentModel is { } model &&
        ReferenceEquals(requested.Identity, model) && model.Id.Entry == requested.Key &&
        ReferenceEquals(Field(screen, "_enchantment"), model) &&
        Field(screen, "_enchantmentAmount") is int amount && amount == requested.Amount &&
        Field(screen, "_prefs") is MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs && b.SamePrefs(prefs);

    private bool TryEnchantPreview(out CardModel original)
    {
        original = null!;
        if (Field(_preview, "_before") is not Control before ||
            Field(_preview, "_after") is not Control after || !Valid(before) || !Valid(after))
            return false;
        var originals = before.GetChildren();
        var previews = after.GetChildren();
        if (originals.Count != 1 || previews.Count != 1 ||
            originals[0] is not NPreviewCardHolder originalHolder || !ValidExact(originalHolder) ||
            previews[0] is not NPreviewCardHolder previewHolder || !ValidExact(previewHolder) ||
            originalHolder.CardModel is not CardModel card || previewHolder.CardModel is not CardModel clone ||
            !ReferenceEquals(originalHolder.CardNode?.Model, card) || !ReferenceEquals(previewHolder.CardNode?.Model, clone) ||
            !_binding.Originals.Any(c => ReferenceEquals(c, card)) || ReferenceEquals(card, clone) ||
            _binding.Player.Deck.Cards.Any(c => ReferenceEquals(c, clone)) ||
            !ReferenceEquals(clone.Owner, _binding.Player) || !ReferenceEquals(clone.RunState, _binding.RunState) ||
            card.Enchantment is not null || !clone.IsEnchantmentPreview ||
            clone.Id.Entry != card.Id.Entry || clone.CurrentUpgradeLevel != card.CurrentUpgradeLevel ||
            GenericEventV7Binding.CopyEnchantment(clone) is not { } effect ||
            effect.Key != _context.Enchantment!.Key || effect.Amount != _context.Enchantment.Amount)
            return false;
        object[] bindings = { before, after, originalHolder, originalHolder.CardNode!,
            previewHolder, previewHolder.CardNode!, card, clone, effect.Identity };
        _enchantPreviewBindings ??= bindings;
        if (bindings.Where((value,i) => !ReferenceEquals(value,_enchantPreviewBindings[i])).Any())
            return false;
        original = card;
        return true;
    }

    private static bool SelectedModelIs(
        IReadOnlyList<CardSelectionV1NativeCandidate> candidates,
        object model)
    {
        int selected = 0;
        bool found = false;
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
        {
            if (!candidate.Selected) continue;
            selected++;
            found |= ReferenceEquals(candidate.ModelIdentity, model);
        }
        return selected == 1 && found;
    }

    private static bool InitialCandidatesValid(
        IReadOnlyList<CardSelectionV1NativeCandidate> candidates)
    {
        bool enabled = false;
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
        {
            if (candidate.Selected || !candidate.Visible) return false;
            enabled |= candidate.Enabled;
        }
        return enabled;
    }

    private static int CountSelected(
        IReadOnlyList<CardSelectionV1NativeCandidate> candidates)
    {
        int count = 0;
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
            if (candidate.Selected) count++;
        return count;
    }

    private static T RequiredNode<T>(Node parent, string path) where T : Node
    {
        T? node = parent.GetNodeOrNull<T>(path);
        if (node is null || !Valid(node))
            throw new InvalidOperationException("Required selector node is unavailable.");
        return node;
    }

    private static void DispatchCard(NGridCardHolder holder)
    {
        using var input = new InputEventAction { Action = MegaInput.select, Pressed = true };
        holder._GuiInput(input);
    }

    private CardSelectionV1SurfaceCapture Unsupported() => new(
        CardSelectionV1SurfaceStatus.Unsupported,
        null, null, null, null, null, null, null, null, null, null,
        CardSelectionV1ParentKind.Event,
        _context.Operation,
        1, 1,
        CardSelectionV1CommitMode.PreviewConfirm,
        CardSelectionV1Phase.Transient,
        false, false, false, false, 0, false,
        CardSelectionV1TaskState.Faulted, false,
        Array.Empty<object>(), Array.Empty<object>(),
        Array.Empty<CardSelectionV1NativeCandidate>(),
        Array.Empty<CardSelectionV1DeckCard>(),
        Array.Empty<CardSelectionV1Replacement>(), null, null);

    private static bool Valid(GodotObject? value) =>
        value is not null && GodotObject.IsInstanceValid(value);

    private static bool ValidExact<T>(T value) where T : GodotObject =>
        value.GetType() == typeof(T) && GodotObject.IsInstanceValid(value);

    private sealed class CandidateBinding
    {
        internal CandidateBinding(
            int slot,
            NGridCardHolder holder,
            CardModel model,
            NCard card,
            NClickableControl hitbox,
            NCardHighlight highlight,
            ShaderMaterial material)
        {
            Slot = slot;
            Holder = holder;
            Model = model;
            Card = card;
            Hitbox = hitbox;
            Highlight = highlight;
            Material = material;
            StableKey = model.Id.Entry;
            UpgradeLevel = model.CurrentUpgradeLevel;
            Dispatch = () => DispatchCard(holder);
        }

        internal int Slot { get; }
        internal NGridCardHolder Holder { get; }
        internal CardModel Model { get; }
        internal NCard Card { get; }
        internal NClickableControl Hitbox { get; }
        internal NCardHighlight Highlight { get; }
        internal ShaderMaterial Material { get; }
        internal string StableKey { get; }
        internal int UpgradeLevel { get; }
        internal Action Dispatch { get; }
    }
}
