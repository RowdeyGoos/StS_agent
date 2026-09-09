using System;
using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using System.Collections.Generic;
using System.Reflection;
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

public sealed class GenericEventV7RewardAdapter : ICardSelectionV1NativeAdapter
{
    private const string HighlightWidthParameter = "width";

    private readonly GenericEventV7Binding _binding;
    private readonly CardSelectionV1ParentContext _context;
    private readonly NSimpleCardSelectScreen _screen;
    private readonly NCardGrid _grid;
    private readonly NConfirmButton _confirm;
    private readonly Action _confirmDispatch;
    private readonly Task<IEnumerable<CardModel>> _completionTask;
    private readonly CandidateBinding[] _candidates;

    private CardSelectionV1NativeCandidate[] _cachedCandidates;
    private CardSelectionV1TaskState _taskState = CardSelectionV1TaskState.Incomplete;
    private object[] _taskResult = Array.Empty<object>();
    private bool _disposed;

    internal GenericEventV7RewardAdapter(
        GenericEventV7Binding binding,
        CardSelectionV1ParentContext context,
        NSimpleCardSelectScreen screen)
    {
        _binding = binding ?? throw new ArgumentNullException(nameof(binding));
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _screen = screen ?? throw new ArgumentNullException(nameof(screen));
        if (!_binding.MatchesAcceptedParent(_context) ||
            !TryPrepareSurface(_binding, _screen,
                out NCardGrid grid,
                out CandidateBinding[] candidateBindings,
                out CardSelectionV1NativeCandidate[] candidates,
                out NConfirmButton confirm, out _))
            throw new InvalidOperationException("Event selector binding is unsupported.");
        _grid = grid;
        _candidates = candidateBindings;
        _cachedCandidates = candidates;
        _confirm = confirm;
        _confirmDispatch = _confirm.ForceClick;

        _completionTask = _screen.CardsSelected() ??
            throw new InvalidOperationException("Event selector task was unavailable.");
        if (_completionTask.IsCompleted)
            throw new InvalidOperationException("Event selector task was not fresh.");
    }

    internal static bool IsReady(
        GenericEventV7Binding binding,
        NSimpleCardSelectScreen screen,
        out GenericEventDiagnosticCode diagnostic)
    {
        diagnostic = GenericEventDiagnosticCode.PrepareBinding;
        try
        {
            return binding is not null && screen is not null &&
                TryPrepareSurface(binding, screen, out _, out _, out _,
                    out _, out diagnostic);
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

        bool selectorTop = !selectorClosed;
        CardSelectionV1Phase phase;
        CardSelectionV1NativeControl? confirm=null;
        CardSelectionV1NativeCandidate[] candidates=_cachedCandidates;
        if(selectorClosed)phase=CardSelectionV1Phase.Submitted;
        else if(!Valid(_screen))return Unsupported();
        else if(!_screen.IsVisibleInTree()||_taskState!=CardSelectionV1TaskState.Incomplete)phase=CardSelectionV1Phase.Transient;
        else
        {
            if(!ReferenceEquals(_screen.GetNodeOrNull<NCardGrid>("%CardGrid"),_grid)||!ValidExact(_grid)||
                !TrySnapshotHolders(_grid,out NGridCardHolder[] holders)||
                !TryCaptureBindings(holders,_candidates,out candidates,out bool allSettled,out _,out _)||
                !ValidExact(_confirm)||!ReferenceEquals(_screen.GetNodeOrNull<NConfirmButton>("%Confirm"),_confirm))return Unsupported();
            _cachedCandidates=candidates;
            phase=!allSettled||_grid.IsAnimatingOut?CardSelectionV1Phase.Transient:CardSelectionV1Phase.Selecting;
            if(_binding.CommitMode==CardSelectionV1CommitMode.ExplicitConfirm)
                confirm=new CardSelectionV1NativeControl(_confirm,_confirm.IsVisibleInTree(),_confirm.IsEnabled,_confirmDispatch);
            else if(_confirm.IsEnabled)return Unsupported();
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
            null,
            CardSelectionV1ParentKind.Event,
            CardSelectionV1Operation.Add,
            _binding.Prefs.MinSelect,
            _binding.Prefs.MaxSelect,
            _binding.CommitMode,
            phase,
            selectorTop,
            selectorClosed,
            false,
            true,
            _binding.DomainCount,
            true,
            _taskState,
            effectCompletion,
            _taskResult,
            Array.Empty<object>(),
            candidates,
            deck,
            Array.Empty<CardSelectionV1Replacement>(),
            null,
            confirm);
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
        NSimpleCardSelectScreen screen,
        out NCardGrid grid,
        out CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates,
        out NConfirmButton confirm,
        out GenericEventDiagnosticCode diagnostic)
    {
        grid = null!;
        bindings = Array.Empty<CandidateBinding>();
        candidates = Array.Empty<CardSelectionV1NativeCandidate>();
        confirm = null!;
        diagnostic = GenericEventDiagnosticCode.PrepareBinding;
        if (!binding.Ready || binding.Operation!=CardSelectionV1Operation.Add || !binding.MatchesOffers()) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareScreen;
        if (!ValidExact(screen) || !screen.IsVisibleInTree()) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareExternalSelector;
        if (CardSelectCmd.Selector is not null) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareDeck;
        if (!binding.MatchesCurrentDeck()) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareForeground;
        if (!InitialForeground(binding, screen)) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareGridNode;
        grid = RequiredNode<NCardGrid>(screen, "%CardGrid");
        diagnostic = GenericEventDiagnosticCode.PrepareGridState;
        if (!ValidExact(grid) || grid.IsAnimatingOut) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareHolders;
        if (!TrySnapshotHolders(grid, out NGridCardHolder[] holders)) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
        if (!TryCreateBindings(holders, binding.EligibleOriginals, out bindings, out candidates, out diagnostic)) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareConfirm;
        confirm = RequiredNode<NConfirmButton>(screen,"%Confirm");
        return ValidExact(confirm) && confirm.IsEnabled==(binding.Prefs.MinSelect==0);
    }

    private static bool InitialForeground(
        GenericEventV7Binding binding,
        NSimpleCardSelectScreen screen) =>
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
        out CardSelectionV1NativeCandidate[] candidates,
        out GenericEventDiagnosticCode diagnostic)
    {
        bindings = Array.Empty<CandidateBinding>();
        candidates = Array.Empty<CardSelectionV1NativeCandidate>();
        diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
        var found = new List<CandidateBinding>();
        var expectedModels = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (CardModel model in expected)
        {
            if (model is null) { diagnostic = GenericEventDiagnosticCode.CandidateExpectedNull; return false; }
            if (!expectedModels.Add(model)) { diagnostic = GenericEventDiagnosticCode.CandidateExpectedDuplicate; return false; }
        }
        var foundModels = new HashSet<object>(ReferenceEqualityComparer.Instance);
        for (int index = 0; index < holdersSnapshot.Count; index++)
        {
            NGridCardHolder holder = holdersSnapshot[index];
            if (holder.CardModel is not CardModel displayed) { diagnostic = GenericEventDiagnosticCode.CandidateDisplayedNull; return false; }
            if (!expectedModels.Contains(displayed)) { diagnostic = GenericEventDiagnosticCode.CandidateUnexpectedModel; return false; }
            if (!foundModels.Add(displayed)) { diagnostic = GenericEventDiagnosticCode.CandidateDisplayedDuplicate; return false; }
            CardModel? model = holder.CardModel;
            NCard? card = holder.CardNode;
            NClickableControl? hitbox = holder.Hitbox;
            NCardHighlight? highlight = card?.CardHighlight;
            if (model is null) { diagnostic = GenericEventDiagnosticCode.CandidateModelNull; return false; }
            if (card is null) { diagnostic = GenericEventDiagnosticCode.CandidateCardNull; return false; }
            if (hitbox is null) { diagnostic = GenericEventDiagnosticCode.CandidateHitboxNull; return false; }
            if (highlight is null) { diagnostic = GenericEventDiagnosticCode.CandidateHighlightNull; return false; }
            if (!CandidateValid(card, GenericEventDiagnosticCode.CandidateCardType, GenericEventDiagnosticCode.CandidateCardInvalid, out diagnostic) ||
                !CandidateHitboxValid(hitbox, out diagnostic) ||
                !CandidateValid(highlight, GenericEventDiagnosticCode.CandidateHighlightType, GenericEventDiagnosticCode.CandidateHighlightInvalid, out diagnostic)) return false;
            var materialValue = highlight.Material;
            if (materialValue is null) { diagnostic = GenericEventDiagnosticCode.CandidateMaterialNull; return false; }
            if (materialValue is not ShaderMaterial material) { diagnostic = GenericEventDiagnosticCode.CandidateMaterialKind; return false; }
            if (!CandidateValid(material, GenericEventDiagnosticCode.CandidateMaterialType, GenericEventDiagnosticCode.CandidateMaterialInvalid, out diagnostic)) return false;
            if (!CardSelectionV1NativeRules.IsStableKey(model.Id.Entry)) { diagnostic = GenericEventDiagnosticCode.CandidateStableKey; return false; }
            found.Add(new CandidateBinding(index, holder, model, card, hitbox,
                highlight, material));
        }
        if (found.Count != expected.Count) { diagnostic = GenericEventDiagnosticCode.CandidateDomainCount; return false; }
        if (found.Count is <1 or >64) { diagnostic = GenericEventDiagnosticCode.CandidateDomainBounds; return false; }
        bindings = found.ToArray();
        if (!TryCaptureBindings(holdersSnapshot, bindings, out candidates, out bool settled,
            out GenericEventDiagnosticCode[] visibilityReasons, out diagnostic)) return false;
        if (!settled) { diagnostic = GenericEventDiagnosticCode.CandidateHighlightUnsettled; return false; }
        return InitialCandidatesValid(candidates, visibilityReasons, out diagnostic);
    }

    private static bool CandidateHitboxValid(NClickableControl hitbox, out GenericEventDiagnosticCode diagnostic)
    {
        diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
        if (!GodotObject.IsInstanceValid(hitbox)) { diagnostic = GenericEventDiagnosticCode.CandidateHitboxInvalid; return false; }
        return true;
    }

    private static bool CandidateValid<T>(T value, GenericEventDiagnosticCode typeCode,
        GenericEventDiagnosticCode invalidCode, out GenericEventDiagnosticCode diagnostic) where T : GodotObject
    {
        diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
        if (value.GetType() != typeof(T)) { diagnostic = typeCode; return false; }
        if (!GodotObject.IsInstanceValid(value)) { diagnostic = invalidCode; return false; }
        return true;
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

    // Native holder input does not depend on inferred viewport dimensions.
    private static bool HolderClickable(NGridCardHolder holder) =>
        typeof(NCardHolder).GetField("_isClickable",
            BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
            ?.GetValue(holder) is true;

    private static bool TryCaptureBindings(
        IReadOnlyList<NGridCardHolder> holdersSnapshot,
        CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates,
        out bool allSettled,
        out GenericEventDiagnosticCode[] visibilityReasons,
        out GenericEventDiagnosticCode diagnostic)
    {
        candidates = new CardSelectionV1NativeCandidate[bindings.Length];
        visibilityReasons = new GenericEventDiagnosticCode[bindings.Length];
        diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
        allSettled = true;
        if (holdersSnapshot.Count != bindings.Length) { diagnostic = GenericEventDiagnosticCode.CandidateSnapshotCount; return false; }
        for (int index = 0; index < bindings.Length; index++)
        {
            CandidateBinding binding = bindings[index];
            if (!ReferenceEquals(holdersSnapshot[index], binding.Holder)) { diagnostic = GenericEventDiagnosticCode.CandidateHolderIdentity; return false; }
            if (!CandidateValid(binding.Holder, GenericEventDiagnosticCode.CandidateHolderType, GenericEventDiagnosticCode.CandidateHolderInvalid, out diagnostic)) return false;
            if (!CandidateValid(binding.Card, GenericEventDiagnosticCode.CandidateCardType, GenericEventDiagnosticCode.CandidateCardInvalid, out diagnostic)) return false;
            if (!CandidateHitboxValid(binding.Hitbox, out diagnostic)) return false;
            if (!CandidateValid(binding.Highlight, GenericEventDiagnosticCode.CandidateHighlightType, GenericEventDiagnosticCode.CandidateHighlightInvalid, out diagnostic)) return false;
            if (!CandidateValid(binding.Material, GenericEventDiagnosticCode.CandidateMaterialType, GenericEventDiagnosticCode.CandidateMaterialInvalid, out diagnostic)) return false;
            if (!(ReferenceEquals(binding.Holder.CardModel, binding.Model))) { diagnostic = GenericEventDiagnosticCode.CandidateModelIdentity; return false; }
            if (!(ReferenceEquals(binding.Holder.CardNode, binding.Card))) { diagnostic = GenericEventDiagnosticCode.CandidateCardIdentity; return false; }
            if (!(ReferenceEquals(binding.Holder.Hitbox, binding.Hitbox))) { diagnostic = GenericEventDiagnosticCode.CandidateHitboxIdentity; return false; }
            if (!(ReferenceEquals(binding.Card.CardHighlight, binding.Highlight))) { diagnostic = GenericEventDiagnosticCode.CandidateHighlightIdentity; return false; }
            if (!(ReferenceEquals(binding.Highlight.Material, binding.Material))) { diagnostic = GenericEventDiagnosticCode.CandidateMaterialIdentity; return false; }
            if (!(string.Equals(binding.Model.Id.Entry, binding.StableKey, StringComparison.Ordinal))) { diagnostic = GenericEventDiagnosticCode.CandidateKeyChanged; return false; }
            if (!(binding.Model.CurrentUpgradeLevel == binding.UpgradeLevel)) { diagnostic = GenericEventDiagnosticCode.CandidateLevelChanged; return false; }
            diagnostic = GenericEventDiagnosticCode.CandidateShaderRead;
            CardSelectionV1HighlightEndpoint endpoint =
                CardSelectionV1NativeRules.ClassifyHighlight(
                    binding.Material.GetShaderParameter(HighlightWidthParameter).AsSingle());
            diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
            bool settled = endpoint != CardSelectionV1HighlightEndpoint.Transient;
            allSettled &= settled;
            bool visible;
            if (!binding.Holder.IsVisibleInTree()) { visible = false; visibilityReasons[index] = GenericEventDiagnosticCode.CandidateHolderInvisible; }
            else if (!binding.Card.IsVisibleInTree()) { visible = false; visibilityReasons[index] = GenericEventDiagnosticCode.CandidateCardInvisible; }
            else if (!binding.Hitbox.IsVisibleInTree()) { visible = false; visibilityReasons[index] = GenericEventDiagnosticCode.CandidateHitboxInvisible; }
            else visible = true;
            diagnostic = GenericEventDiagnosticCode.CandidateEnabledRead;
            bool enabled = binding.Hitbox.IsEnabled && HolderClickable(binding.Holder);
            diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
            candidates[index] = new CardSelectionV1NativeCandidate(
                binding.Slot, binding.StableKey, binding.Holder, binding.Model, binding.Card,
                binding.UpgradeLevel, visible, enabled,
                endpoint == CardSelectionV1HighlightEndpoint.Selected, settled, binding.Dispatch);
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
                card, card.Id.Entry, card.CurrentUpgradeLevel));
        }
        deck = copied.ToArray();
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
        IReadOnlyList<CardSelectionV1NativeCandidate> candidates,
        GenericEventDiagnosticCode[] visibilityReasons,
        out GenericEventDiagnosticCode diagnostic)
    {
        diagnostic = GenericEventDiagnosticCode.PrepareCandidates;
        bool enabled = false;
        int index = 0;
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
        {
            if (candidate.Selected) { diagnostic = GenericEventDiagnosticCode.CandidateInitiallySelected; return false; }
            if (!candidate.Visible) { diagnostic = visibilityReasons[index]; return false; }
            enabled |= candidate.Enabled;
            index++;
        }
        if (!enabled) diagnostic = GenericEventDiagnosticCode.CandidateNoneEnabled;
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
        CardSelectionV1Operation.Add,
        _binding.Prefs.MinSelect, _binding.Prefs.MaxSelect,
        _binding.CommitMode,
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
