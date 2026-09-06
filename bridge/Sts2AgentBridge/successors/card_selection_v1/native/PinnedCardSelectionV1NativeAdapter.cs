using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Native;

/// <summary>
/// Owner-thread adapter for the two statically witnessed v1 selector policies.
/// It never discovers a parent from the selector itself: factories require the
/// exact accepted parent context and retained typed parent witnesses.
/// </summary>
public sealed class PinnedCardSelectionV1NativeAdapter : ICardSelectionV1NativeAdapter
{
    private const string CheeseOptionKey = "ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE";
    private const string SmithOptionId = "SMITH";
    private const string HighlightWidthParameter = "width";

    private readonly CardSelectionV1ParentContext _context;
    private readonly NativePolicy _policy;
    private readonly NRun _run;
    private readonly Player _player;
    private readonly CanvasItem _room;
    private readonly NMapScreen _map;
    private readonly NCardGridSelectionScreen _screen;
    private readonly NCardGrid _grid;
    private readonly object _parentOption;
    private readonly object _parentController;
    private readonly RoomFullOfCheese? _cheese;
    private readonly NRestSiteRoom? _restRoom;
    private readonly NProceedButton? _restProceed;
    private readonly NUpgradePreview? _smithPreview;
    private readonly Control? _smithPreviewContainer;
    private readonly NConfirmButton? _smithConfirm;
    private readonly Action? _smithConfirmDispatch;
    private readonly Task<IEnumerable<CardModel>> _completionTask;
    private readonly CandidateBinding[] _bindings;
    private readonly CheeseGeometry? _cheeseGeometry;

    private CardSelectionV1NativeCandidate[] _cachedCandidates;
    private object? _cachedPreviewIdentity;
    private object[] _cachedPreviewOriginals = Array.Empty<object>();
    private CardSelectionV1NativeControl? _cachedConfirm;
    private bool _cachedPreviewOpen;
    private CardSelectionV1TaskState _taskState = CardSelectionV1TaskState.Incomplete;
    private object[] _taskResult = Array.Empty<object>();
    private bool _disposed;

    private PinnedCardSelectionV1NativeAdapter(
        CardSelectionV1ParentContext context,
        NativePolicy policy,
        NRun run,
        Player player,
        CanvasItem room,
        NMapScreen map,
        NCardGridSelectionScreen screen,
        NCardGrid grid,
        object parentOption,
        object parentController,
        RoomFullOfCheese? cheese,
        NRestSiteRoom? restRoom,
        NProceedButton? restProceed,
        NUpgradePreview? smithPreview,
        Control? smithPreviewContainer,
        NConfirmButton? smithConfirm,
        Task<IEnumerable<CardModel>> completionTask,
        CandidateBinding[] bindings,
        CardSelectionV1NativeCandidate[] candidates,
        CheeseGeometry? cheeseGeometry)
    {
        _context = context;
        _policy = policy;
        _run = run;
        _player = player;
        _room = room;
        _map = map;
        _screen = screen;
        _grid = grid;
        _parentOption = parentOption;
        _parentController = parentController;
        _cheese = cheese;
        _restRoom = restRoom;
        _restProceed = restProceed;
        _smithPreview = smithPreview;
        _smithPreviewContainer = smithPreviewContainer;
        _smithConfirm = smithConfirm;
        _smithConfirmDispatch = smithConfirm is null ? null : smithConfirm.ForceClick;
        _completionTask = completionTask;
        _bindings = bindings;
        _cachedCandidates = candidates;
        _cheeseGeometry = cheeseGeometry;
    }

    public static PinnedCardSelectionV1NativeAdapter CreateRoomFullOfCheese(
        CardSelectionV1ParentContext context,
        NRun run,
        Player player,
        NEventRoom room,
        NMapScreen map,
        RoomFullOfCheese eventModel,
        EventOption option,
        NEventOptionButton parentController,
        NSimpleCardSelectScreen screen)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(run);
        ArgumentNullException.ThrowIfNull(player);
        ArgumentNullException.ThrowIfNull(room);
        ArgumentNullException.ThrowIfNull(map);
        ArgumentNullException.ThrowIfNull(eventModel);
        ArgumentNullException.ThrowIfNull(option);
        ArgumentNullException.ThrowIfNull(parentController);
        ArgumentNullException.ThrowIfNull(screen);
        if (!CardSelectionV1NativeRules.IsCheesePolicy(context) ||
            !CardSelectionV1NativeRules.IsExactRuntimeType(eventModel, typeof(RoomFullOfCheese)) ||
            !CardSelectionV1NativeRules.IsExactRuntimeType(option, typeof(EventOption)) ||
            !CardSelectionV1NativeRules.IsExactRuntimeType(parentController, typeof(NEventOptionButton)) ||
            !CardSelectionV1NativeRules.IsExactRuntimeType(screen, typeof(NSimpleCardSelectScreen)) ||
            !MatchesContext(context, run, player, room, map, option, parentController) ||
            !string.Equals(option.TextKey, CheeseOptionKey, StringComparison.Ordinal) ||
            !ReferenceEquals(eventModel.Owner, player) || eventModel.IsFinished ||
            !ReferenceEquals(parentController.Option, option) ||
            !ReferenceEquals(parentController.Event, eventModel) ||
            !ReferenceEquals(NRun.Instance, run) || !ReferenceEquals(run.EventRoom, room) ||
            !ReferenceEquals(NEventRoom.Instance, room) || !ReferenceEquals(NMapScreen.Instance, map))
            throw new InvalidOperationException("Cheese selector parent binding is unsupported.");

        return Admit(
            context, NativePolicy.Cheese, run, player, room, map, screen,
            option, parentController, eventModel, null, null, null, null, null);
    }

    public static bool IsRoomFullOfCheeseReady(
        NRun run,
        Player player,
        NEventRoom room,
        NMapScreen map,
        RoomFullOfCheese eventModel,
        EventOption option,
        NEventOptionButton parentController,
        NSimpleCardSelectScreen screen)
    {
        try
        {
            return CardSelectionV1NativeRules.IsExactRuntimeType(eventModel, typeof(RoomFullOfCheese)) &&
                CardSelectionV1NativeRules.IsExactRuntimeType(option, typeof(EventOption)) &&
                CardSelectionV1NativeRules.IsExactRuntimeType(parentController, typeof(NEventOptionButton)) &&
                CardSelectionV1NativeRules.IsExactRuntimeType(screen, typeof(NSimpleCardSelectScreen)) &&
                string.Equals(option.TextKey, CheeseOptionKey, StringComparison.Ordinal) &&
                ReferenceEquals(eventModel.Owner, player) && !eventModel.IsFinished &&
                ReferenceEquals(parentController.Option, option) &&
                ReferenceEquals(parentController.Event, eventModel) &&
                ReferenceEquals(NRun.Instance, run) && ReferenceEquals(run.EventRoom, room) &&
                ReferenceEquals(NEventRoom.Instance, room) && ReferenceEquals(NMapScreen.Instance, map) &&
                TryPrepare(NativePolicy.Cheese, 8, run, player, room, map, screen,
                    out _, out _, out _, out _);
        }
        catch { return false; }
    }

    public static PinnedCardSelectionV1NativeAdapter CreateSmith(
        CardSelectionV1ParentContext context,
        NRun run,
        Player player,
        NRestSiteRoom room,
        NMapScreen map,
        SmithRestSiteOption option,
        NRestSiteButton parentController,
        NDeckUpgradeSelectScreen screen)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(run);
        ArgumentNullException.ThrowIfNull(player);
        ArgumentNullException.ThrowIfNull(room);
        ArgumentNullException.ThrowIfNull(map);
        ArgumentNullException.ThrowIfNull(option);
        ArgumentNullException.ThrowIfNull(parentController);
        ArgumentNullException.ThrowIfNull(screen);
        if (!CardSelectionV1NativeRules.IsSmithPolicy(context) ||
            !CardSelectionV1NativeRules.IsExactRuntimeType(option, typeof(SmithRestSiteOption)) ||
            !CardSelectionV1NativeRules.IsExactRuntimeType(parentController, typeof(NRestSiteButton)) ||
            !CardSelectionV1NativeRules.IsExactRuntimeType(screen, typeof(NDeckUpgradeSelectScreen)) ||
            !MatchesContext(context, run, player, room, map, option, parentController) ||
            option.SmithCount != 1 ||
            !string.Equals(option.OptionId, SmithOptionId, StringComparison.Ordinal) ||
            !ReferenceEquals(room.GetButtonForOption(option), parentController) ||
            !ReferenceEquals(NRun.Instance, run) || !ReferenceEquals(run.RestSiteRoom, room) ||
            !ReferenceEquals(NRestSiteRoom.Instance, room) || !ReferenceEquals(NMapScreen.Instance, map))
            throw new InvalidOperationException("Smith selector parent binding is unsupported.");

        NProceedButton? proceed = room.ProceedButton;
        if (proceed is null || !Valid(proceed) ||
            proceed.IsVisibleInTree() && proceed.IsEnabled)
            throw new InvalidOperationException("Smith proceed state is not initial.");
        Control previewContainer = RequiredNode<Control>(screen, "%UpgradeSinglePreviewContainer");
        NUpgradePreview preview = RequiredNode<NUpgradePreview>(previewContainer, "UpgradePreview");
        NConfirmButton confirm = RequiredNode<NConfirmButton>(previewContainer, "Confirm");
        if (previewContainer.Visible || preview.Card is not null)
            throw new InvalidOperationException("Smith selector was already previewing.");

        return Admit(
            context, NativePolicy.Smith, run, player, room, map, screen,
            option, parentController, null, room, proceed, preview, previewContainer, confirm);
    }

    public static bool IsSmithReady(
        int expectedDomainCount,
        NRun run,
        Player player,
        NRestSiteRoom room,
        NMapScreen map,
        SmithRestSiteOption option,
        NRestSiteButton parentController,
        NDeckUpgradeSelectScreen screen)
    {
        try
        {
            if (expectedDomainCount < 1 ||
                !CardSelectionV1NativeRules.IsExactRuntimeType(option, typeof(SmithRestSiteOption)) ||
                !CardSelectionV1NativeRules.IsExactRuntimeType(parentController, typeof(NRestSiteButton)) ||
                !CardSelectionV1NativeRules.IsExactRuntimeType(screen, typeof(NDeckUpgradeSelectScreen)) ||
                option.SmithCount != 1 || !string.Equals(option.OptionId, SmithOptionId, StringComparison.Ordinal) ||
                !ReferenceEquals(room.GetButtonForOption(option), parentController) ||
                !ReferenceEquals(NRun.Instance, run) || !ReferenceEquals(run.RestSiteRoom, room) ||
                !ReferenceEquals(NRestSiteRoom.Instance, room) || !ReferenceEquals(NMapScreen.Instance, map))
                return false;
            NProceedButton? proceed = room.ProceedButton;
            if (proceed is null || !Valid(proceed) || proceed.IsVisibleInTree() && proceed.IsEnabled)
                return false;
            Control container = RequiredNode<Control>(screen, "%UpgradeSinglePreviewContainer");
            NUpgradePreview preview = RequiredNode<NUpgradePreview>(container, "UpgradePreview");
            NConfirmButton confirm = RequiredNode<NConfirmButton>(container, "Confirm");
            return !container.Visible && preview.Card is null && Valid(confirm) &&
                TryPrepare(NativePolicy.Smith, expectedDomainCount, run, player, room, map,
                    screen, out _, out _, out _, out _);
        }
        catch { return false; }
    }

    public CardSelectionV1SurfaceCapture CaptureSurface()
    {
        if (_disposed) return Unsupported();
        try
        {
            return CaptureCore();
        }
        catch
        {
            return Unsupported();
        }
    }

    public void Dispose()
    {
        _disposed = true;
    }

    private static PinnedCardSelectionV1NativeAdapter Admit(
        CardSelectionV1ParentContext context,
        NativePolicy policy,
        NRun run,
        Player player,
        CanvasItem room,
        NMapScreen map,
        NCardGridSelectionScreen screen,
        object parentOption,
        object parentController,
        RoomFullOfCheese? cheese,
        NRestSiteRoom? restRoom,
        NProceedButton? restProceed,
        NUpgradePreview? smithPreview,
        Control? smithPreviewContainer,
        NConfirmButton? smithConfirm)
    {
        if (!TryPrepare(policy, context.ExpectedDomainCount, run, player, room, map, screen,
                out NCardGrid grid, out CandidateBinding[] bindings,
                out CardSelectionV1NativeCandidate[] candidates,
                out CheeseGeometry? cheeseGeometry))
            throw new InvalidOperationException("Selector readiness projection is unsupported.");

        Task<IEnumerable<CardModel>> task = screen.CardsSelected();
        if (task is null || task.IsCompleted)
            throw new InvalidOperationException("Selector completion task was not fresh.");

        return new PinnedCardSelectionV1NativeAdapter(
            context, policy, run, player, room, map, screen, grid,
            parentOption, parentController, cheese, restRoom, restProceed,
            smithPreview, smithPreviewContainer, smithConfirm,
            task, bindings, candidates, cheeseGeometry);
    }

    private static bool TryPrepare(
        NativePolicy policy,
        int expectedDomainCount,
        NRun run,
        Player player,
        CanvasItem room,
        NMapScreen map,
        NCardGridSelectionScreen screen,
        out NCardGrid grid,
        out CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates,
        out CheeseGeometry? cheeseGeometry)
    {
        grid = null!;
        bindings = Array.Empty<CandidateBinding>();
        candidates = Array.Empty<CardSelectionV1NativeCandidate>();
        cheeseGeometry = null;
        if (!Valid(run) || !Valid(room) || !Valid(map) || !Valid(screen) ||
            !room.IsVisibleInTree() || !screen.IsVisibleInTree() ||
            map.IsOpen || map.IsTravelEnabled || map.IsTraveling)
            return false;
        NOverlayStack? overlays = run.GlobalUi?.Overlays;
        if (!Valid(overlays) || overlays!.ScreenCount != 1 || !ReferenceEquals(overlays.Peek(), screen))
            return false;
        grid = RequiredNode<NCardGrid>(screen, "%CardGrid");
        if (!CardSelectionV1NativeRules.IsExactRuntimeType(grid, typeof(NCardGrid)) || grid.IsAnimatingOut ||
            !TryCreateBindings(grid, out bindings, out candidates) || bindings.Length == 0 ||
            bindings.Length > CardSelectionV1Limits.MaximumCandidates)
            return false;
        int enabledCandidates = 0;
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
        {
            if (!candidate.SelectionSettled || candidate.Selected || !candidate.Visible)
                return false;
            if (candidate.Enabled) enabledCandidates++;
        }
        int requiredEnabled = policy == NativePolicy.Cheese ? 2 : 1;
        if (enabledCandidates < requiredEnabled) return false;
        if (policy == NativePolicy.Cheese)
        {
            if (bindings.Length != 8 || !CheeseGeometry.TryBind(grid, out cheeseGeometry)) return false;
        }
        else if (!ExactSmithDomain(expectedDomainCount, player, bindings)) return false;
        return TryCopyDeck(player, out _);
    }

    private CardSelectionV1SurfaceCapture CaptureCore()
    {
        if (!TryBoundForeground(out NOverlayStack? overlays, out bool selectorClosed))
            return Unsupported();
        if (!TryCopyDeck(_player, out CardSelectionV1DeckCard[] deck))
            return Unsupported();
        SnapshotTask();

        bool selectorTop = !selectorClosed;
        CardSelectionV1Phase phase;
        bool previewOpen = false;
        object? previewIdentity = _cachedPreviewIdentity;
        object[] previewOriginals = _cachedPreviewOriginals;
        CardSelectionV1NativeControl? confirmControl = _cachedConfirm;
        CardSelectionV1NativeCandidate[] candidates = _cachedCandidates;

        if (selectorClosed)
        {
            phase = CardSelectionV1Phase.Submitted;
        }
        else if (!Valid(_screen))
        {
            return Unsupported();
        }
        else if (!_screen.IsVisibleInTree())
        {
            phase = CardSelectionV1Phase.Transient;
        }
        else
        {
            if (_taskState != CardSelectionV1TaskState.Incomplete)
            {
                phase = CardSelectionV1Phase.Submitted;
                previewOpen = _cachedPreviewOpen;
            }
            else
            {
                if (!ReferenceEquals(_screen.GetNodeOrNull<NCardGrid>("%CardGrid"), _grid) ||
                    _cheeseGeometry is not null && !_cheeseGeometry.Matches(_grid) ||
                    !TryCaptureBindings(_grid, _bindings, out candidates, out bool allSettled))
                    return Unsupported();
                _cachedCandidates = candidates;

                bool previewReady = false;
                if (_policy == NativePolicy.Smith)
                {
                    if (!TryCaptureSmithPreview(out previewOpen, out previewIdentity,
                            out previewOriginals, out confirmControl))
                        return Unsupported();
                    previewReady = previewOpen && previewOriginals.Length == 1 &&
                        confirmControl is not null && confirmControl.Visible && confirmControl.Enabled &&
                        SelectedModelIs(candidates, previewOriginals[0]);
                    _cachedPreviewOpen = previewOpen;
                    _cachedPreviewIdentity = previewIdentity;
                    _cachedPreviewOriginals = previewOriginals;
                    _cachedConfirm = confirmControl;
                }

                if (!allSettled || _grid.IsAnimatingOut)
                    phase = CardSelectionV1Phase.Transient;
                else if (previewReady)
                    phase = CardSelectionV1Phase.Preview;
                else if (previewOpen ||
                    _policy == NativePolicy.Smith && CountSelected(candidates) == 1)
                    phase = CardSelectionV1Phase.Transient;
                else
                    phase = CardSelectionV1Phase.Selecting;
            }
        }

        bool effectCompletion = selectorClosed && EffectCompletionObserved();
        if (_policy == NativePolicy.Cheese && !selectorClosed && _cheese!.IsFinished ||
            _policy == NativePolicy.Smith &&
                (_map.IsTravelEnabled && (!selectorClosed || !effectCompletion) ||
                 selectorClosed && RestProceedReady() != _map.IsTravelEnabled))
            return Unsupported();
        return new CardSelectionV1SurfaceCapture(
            CardSelectionV1SurfaceStatus.Available,
            _context.ParentReceiptIdentity, _run, _player, _room, _map,
            _parentOption, _parentController, _screen, _completionTask,
            previewIdentity, _context.ParentKind, _context.Operation,
            _context.MinSelect, _context.MaxSelect, _context.CommitMode,
            phase, selectorTop, selectorClosed, previewOpen,
            true, _bindings.Length, true, _taskState, effectCompletion,
            _taskResult, previewOriginals, candidates, deck,
            Array.Empty<CardSelectionV1Replacement>(), null, confirmControl);
    }

    private bool TryBoundForeground(out NOverlayStack? overlays, out bool selectorClosed)
    {
        overlays = null;
        selectorClosed = false;
        if (!ReferenceEquals(NRun.Instance, _run) || !Valid(_run) ||
            !ReferenceEquals(_context.RunIdentity, _run) ||
            !ReferenceEquals(_context.PlayerIdentity, _player) ||
            !ReferenceEquals(_context.RoomIdentity, _room) ||
            !ReferenceEquals(_context.MapIdentity, _map) ||
            !ReferenceEquals(_context.ParentOptionIdentity, _parentOption) ||
            !ReferenceEquals(_context.ParentControllerIdentity, _parentController) ||
            !Valid(_room) || !Valid(_map) || !_room.IsVisibleInTree() ||
            !ReferenceEquals(NMapScreen.Instance, _map) || _map.IsOpen || _map.IsTraveling)
            return false;

        if (_policy == NativePolicy.Cheese)
        {
            if (_map.IsTravelEnabled || _cheese is null ||
                !ReferenceEquals(_run.EventRoom, _room) ||
                !ReferenceEquals(NEventRoom.Instance, _room) ||
                !ReferenceEquals(_cheese.Owner, _player)) return false;
        }
        else
        {
            if (_restRoom is null || !ReferenceEquals(_run.RestSiteRoom, _restRoom) ||
                !ReferenceEquals(NRestSiteRoom.Instance, _restRoom)) return false;
        }

        overlays = _run.GlobalUi?.Overlays;
        if (!Valid(overlays) || overlays!.ScreenCount < 0) return false;
        if (overlays.ScreenCount == 0)
        {
            selectorClosed = true;
            return true;
        }
        return overlays.ScreenCount == 1 && ReferenceEquals(overlays.Peek(), _screen);
    }

    private bool TryCaptureSmithPreview(
        out bool open,
        out object? identity,
        out object[] originals,
        out CardSelectionV1NativeControl? confirm)
    {
        open = false;
        identity = null;
        originals = Array.Empty<object>();
        confirm = null;
        if (_smithPreview is null || _smithPreviewContainer is null ||
            _smithConfirm is null || _smithConfirmDispatch is null ||
            !Valid(_smithPreview) || !Valid(_smithPreviewContainer) || !Valid(_smithConfirm) ||
            !ReferenceEquals(_screen.GetNodeOrNull<Control>("%UpgradeSinglePreviewContainer"),
                _smithPreviewContainer) ||
            !ReferenceEquals(_smithPreviewContainer.GetNodeOrNull<NUpgradePreview>("UpgradePreview"),
                _smithPreview) ||
            !ReferenceEquals(_smithPreviewContainer.GetNodeOrNull<NConfirmButton>("Confirm"),
                _smithConfirm)) return false;

        open = _smithPreviewContainer.Visible && _smithPreviewContainer.IsVisibleInTree();
        if (!open) return true;
        identity = _smithPreview;
        CardModel? original = _smithPreview.Card;
        if (original is not null) originals = new object[] { original };
        confirm = new CardSelectionV1NativeControl(
            _smithConfirm, _smithConfirm.IsVisibleInTree(),
            _smithConfirm.IsEnabled, _smithConfirmDispatch);
        return true;
    }

    private bool EffectCompletionObserved()
    {
        if (_policy == NativePolicy.Cheese)
            return _cheese is not null && _cheese.IsFinished && !_map.IsTravelEnabled;
        return RestProceedReady() && _map.IsTravelEnabled && !_map.IsOpen && !_map.IsTraveling;
    }

    private bool RestProceedReady()
    {
        return _restProceed is not null && Valid(_restProceed) &&
            ReferenceEquals(_restRoom?.ProceedButton, _restProceed) &&
            _restProceed.IsVisibleInTree() && _restProceed.IsEnabled;
    }

    private void SnapshotTask()
    {
        if (_taskState != CardSelectionV1TaskState.Incomplete || !_completionTask.IsCompleted)
            return;
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
                if (model is null || values.Count >= CardSelectionV1Limits.MaximumSelectedCards ||
                    !seen.Add(model))
                {
                    _taskState = CardSelectionV1TaskState.Faulted;
                    _taskResult = Array.Empty<object>();
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
        NCardGrid grid,
        out CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates)
    {
        var found = new List<CandidateBinding>();
        var holderSet = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var modelSet = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (NCardHolder? holder in grid.CurrentlyDisplayedCardHolders)
        {
            if (found.Count >= CardSelectionV1Limits.MaximumCandidates ||
                holder is not NGridCardHolder gridHolder || !Valid(gridHolder) ||
                !holderSet.Add(gridHolder))
            {
                bindings = Array.Empty<CandidateBinding>();
                candidates = Array.Empty<CardSelectionV1NativeCandidate>();
                return false;
            }
            CardModel? model = gridHolder.CardModel;
            NCard? card = gridHolder.CardNode;
            NClickableControl? hitbox = gridHolder.Hitbox;
            NCardHighlight? highlight = card?.CardHighlight;
            if (model is null || card is null || hitbox is null || highlight is null ||
                !modelSet.Add(model) || !Valid(card) || !Valid(hitbox) || !Valid(highlight) ||
                highlight.Material is not ShaderMaterial material || !Valid(material) ||
                !CardSelectionV1NativeRules.IsStableKey(model.Id.Entry))
            {
                bindings = Array.Empty<CandidateBinding>();
                candidates = Array.Empty<CardSelectionV1NativeCandidate>();
                return false;
            }
            var binding = new CandidateBinding(
                found.Count, gridHolder, model, card, hitbox, highlight, material);
            found.Add(binding);
        }
        bindings = found.ToArray();
        return TryCaptureBindings(grid, bindings, out candidates, out _);
    }

    private static bool TryCaptureBindings(
        NCardGrid grid,
        CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates,
        out bool allSettled)
    {
        candidates = new CardSelectionV1NativeCandidate[bindings.Length];
        allSettled = true;
        int displayed = 0;
        foreach (NCardHolder? holder in grid.CurrentlyDisplayedCardHolders)
        {
            if (displayed >= bindings.Length ||
                !ReferenceEquals(holder, bindings[displayed].Holder)) return false;
            displayed++;
        }
        if (displayed != bindings.Length) return false;
        for (int index = 0; index < bindings.Length; index++)
        {
            CandidateBinding binding = bindings[index];
            if (!Valid(binding.Holder) || !Valid(binding.Card) || !Valid(binding.Hitbox) ||
                !Valid(binding.Highlight) || !Valid(binding.Material) ||
                !ReferenceEquals(binding.Holder.CardModel, binding.Model) ||
                !ReferenceEquals(binding.Holder.CardNode, binding.Card) ||
                !ReferenceEquals(binding.Holder.Hitbox, binding.Hitbox) ||
                !ReferenceEquals(binding.Card.CardHighlight, binding.Highlight) ||
                !ReferenceEquals(binding.Highlight.Material, binding.Material) ||
                !string.Equals(binding.Model.Id.Entry, binding.StableKey,
                    StringComparison.Ordinal) ||
                binding.Model.CurrentUpgradeLevel != binding.UpgradeLevel)
                return false;

            float width = binding.Material.GetShaderParameter(HighlightWidthParameter).AsSingle();
            CardSelectionV1HighlightEndpoint endpoint =
                CardSelectionV1NativeRules.ClassifyHighlight(width);
            bool settled = endpoint != CardSelectionV1HighlightEndpoint.Transient;
            allSettled &= settled;
            candidates[index] = new CardSelectionV1NativeCandidate(
                binding.Slot, binding.StableKey, binding.Holder, binding.Model,
                binding.Card, binding.UpgradeLevel,
                binding.Holder.IsVisibleInTree() && binding.Card.IsVisibleInTree() &&
                    binding.Hitbox.IsVisibleInTree(),
                binding.Hitbox.IsEnabled,
                endpoint == CardSelectionV1HighlightEndpoint.Selected,
                settled, binding.Dispatch);
        }
        return true;
    }

    private static bool ExactSmithDomain(
        int expectedDomainCount,
        Player player,
        CandidateBinding[] bindings)
    {
        var eligible = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (CardModel? card in player.Deck.Cards)
        {
            if (card is null) return false;
            if (card.IsUpgradable && !eligible.Add(card)) return false;
        }
        if (eligible.Count == 0 || eligible.Count != bindings.Length ||
            expectedDomainCount != eligible.Count)
            return false;
        foreach (CandidateBinding binding in bindings)
            if (!eligible.Remove(binding.Model)) return false;
        return eligible.Count == 0;
    }

    private static bool TryCopyDeck(Player player, out CardSelectionV1DeckCard[] deck)
    {
        var copied = new List<CardSelectionV1DeckCard>();
        var seen = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (CardModel? card in player.Deck.Cards)
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
        CardSelectionV1NativeCandidate[] candidates, object model)
    {
        int selected = 0;
        bool matched = false;
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
        {
            if (!candidate.Selected) continue;
            selected++;
            matched |= ReferenceEquals(candidate.ModelIdentity, model);
        }
        return selected == 1 && matched;
    }

    private static int CountSelected(CardSelectionV1NativeCandidate[] candidates)
    {
        int count = 0;
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
            if (candidate.Selected) count++;
        return count;
    }

    private static void DispatchCard(NGridCardHolder holder)
    {
        using var input = new InputEventAction
        {
            Action = MegaInput.select,
            Pressed = true,
        };
        holder._GuiInput(input);
    }

    private static bool MatchesContext(
        CardSelectionV1ParentContext context,
        object run,
        object player,
        object room,
        object map,
        object option,
        object controller) =>
        ReferenceEquals(context.RunIdentity, run) &&
        ReferenceEquals(context.PlayerIdentity, player) &&
        ReferenceEquals(context.RoomIdentity, room) &&
        ReferenceEquals(context.MapIdentity, map) &&
        ReferenceEquals(context.ParentOptionIdentity, option) &&
        ReferenceEquals(context.ParentControllerIdentity, controller) &&
        context.ParentReceiptIdentity is not null;

    private static T RequiredNode<T>(Node parent, string path) where T : Node
    {
        T? node = parent.GetNodeOrNull<T>(path);
        if (node is null || !Valid(node))
            throw new InvalidOperationException("Required selector node is unavailable.");
        return node;
    }

    private static bool Valid(GodotObject? value) =>
        value is not null && GodotObject.IsInstanceValid(value);

    private CardSelectionV1SurfaceCapture Unsupported() =>
        new(CardSelectionV1SurfaceStatus.Unsupported,
            null, null, null, null, null, null, null, null, null, null,
            _context.ParentKind, _context.Operation, _context.MinSelect, _context.MaxSelect,
            _context.CommitMode, CardSelectionV1Phase.Transient,
            false, false, false, false, 0, false,
            CardSelectionV1TaskState.Faulted, false,
            Array.Empty<object>(), Array.Empty<object>(),
            Array.Empty<CardSelectionV1NativeCandidate>(),
            Array.Empty<CardSelectionV1DeckCard>(),
            Array.Empty<CardSelectionV1Replacement>(), null, null);

    private enum NativePolicy
    {
        Cheese = 1,
        Smith = 2,
    }

    private sealed class CheeseGeometry
    {
        private CheeseGeometry(
            Control scroll, Vector2 scrollSize, Vector2 scrollPosition,
            Vector2 gridSize, int yOffset, Vector2 cardSize)
        {
            Scroll = scroll;
            ScrollSize = scrollSize;
            ScrollPosition = scrollPosition;
            GridSize = gridSize;
            YOffset = yOffset;
            CardSize = cardSize;
        }

        internal Control Scroll { get; }
        internal Vector2 ScrollSize { get; }
        internal Vector2 ScrollPosition { get; }
        internal Vector2 GridSize { get; }
        internal int YOffset { get; }
        internal Vector2 CardSize { get; }

        internal static bool TryBind(NCardGrid grid, out CheeseGeometry? geometry)
        {
            geometry = null;
            Control? scroll = grid.GetNodeOrNull<Control>("%ScrollContainer");
            if (scroll is null || !Valid(scroll) || !scroll.IsVisibleInTree()) return false;
            Vector2 scrollSize = scroll.Size;
            Vector2 gridSize = grid.Size;
            Vector2 cardSize = NCard.defaultSize * NCardHolder.smallScale;
            int yOffset = grid.YOffset;
            if (!float.IsFinite(gridSize.X) || gridSize.X <= 0f ||
                !float.IsFinite(scroll.Position.X) ||
                !CardSelectionV1NativeRules.TryCheeseGeometry(
                    scrollSize.X, scrollSize.Y, scroll.Position.Y, gridSize.Y,
                    cardSize.X, cardSize.Y, yOffset, out _, out _)) return false;
            geometry = new CheeseGeometry(
                scroll, scrollSize, scroll.Position, gridSize, yOffset, cardSize);
            return true;
        }

        internal bool Matches(NCardGrid grid)
        {
            if (!Valid(Scroll) ||
                !ReferenceEquals(grid.GetNodeOrNull<Control>("%ScrollContainer"), Scroll))
                return false;
            Vector2 currentCardSize = NCard.defaultSize * NCardHolder.smallScale;
            return Scroll.Size == ScrollSize && Scroll.Position == ScrollPosition &&
                grid.Size == GridSize && grid.YOffset == YOffset && currentCardSize == CardSize;
        }

    }

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
