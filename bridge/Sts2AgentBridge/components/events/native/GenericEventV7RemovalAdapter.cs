using System;
using System.Reflection;
using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using System.Collections.Generic;
using System.Linq;
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

public sealed class GenericEventV7RemovalAdapter : ICardSelectionV1NativeAdapter
{
    private const string HighlightWidthParameter = "width";
    private bool IsEnchant => _binding.Operation == CardSelectionV1Operation.Enchant;
    private static string ContainerPath(GenericEventV7Binding b) => b.Operation==CardSelectionV1Operation.Enchant ? "%EnchantMultiPreviewContainer" : "%PreviewContainer";
    private static string CardsPath(GenericEventV7Binding b) => b.Operation==CardSelectionV1Operation.Enchant ? "Cards" : "%Cards";
    private static string ConfirmPath(GenericEventV7Binding b) => b.Operation==CardSelectionV1Operation.Enchant ? "Confirm" : "%PreviewConfirm";

    private readonly GenericEventV7Binding _binding;
    private readonly CardSelectionV1ParentContext _context;
    private readonly NCardGridSelectionScreen _screen;
    private readonly NCardGrid _grid;
    private readonly Control _previewContainer;
    private readonly Control _preview;
    private readonly NConfirmButton _confirm;
    private readonly Action _confirmDispatch;
    private readonly NConfirmButton? _openPreview;
    private readonly Action? _previewDispatch;
    private NPreviewCardHolder[]? _previewHolders;
    private NCard[]? _previewCards;
    private readonly HashSet<object> _expectedSelection=new(ReferenceEqualityComparer.Instance);
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

    internal GenericEventV7RemovalAdapter(
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
                out NConfirmButton confirm, out _))
            throw new InvalidOperationException("Event selector binding is unsupported.");
        _grid = grid;
        _candidates = candidateBindings;
        foreach(var candidate in _candidates)candidate.Dispatch=()=>{
            if(!_expectedSelection.Add(candidate.Model))throw new InvalidOperationException("Repeated native selection.");
            DispatchCard(candidate.Holder);
        };
        _cachedCandidates = candidates;
        _previewContainer = previewContainer;
        _preview = preview;
        _confirm = confirm;
        _confirmDispatch = _confirm.ForceClick;
        _openPreview = IsEnchant ? null : RequiredNode<NConfirmButton>(_screen,"%Confirm");
        _previewDispatch = _openPreview is null ? null : _openPreview.ForceClick;

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
        if (!selectorClosed && IsEnchant &&
            (!GenericEventV7CardAdapter.EnchantmentScreenMatches(_binding,_screen) ||
             _taskState==CardSelectionV1TaskState.Incomplete && _binding.Originals.Any(c=>
                 c.Enchantment is not null || !_binding.EnchantmentModel!.CanEnchant(c)))) return Unsupported();

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
            if (!TryCapturePreview(out previewOpen, out previewIdentity,
                    out previewOriginals, out confirm))
                return Unsupported();
            _cachedPreviewOpen = previewOpen;
            _cachedPreviewIdentity = previewIdentity;
            _cachedPreviewOriginals = previewOriginals;
            _cachedConfirm = confirm;

            if(previewOpen)
            {
                candidates=candidates.Select(c=>new CardSelectionV1NativeCandidate(c.Slot,c.StableKey,c.HolderIdentity,c.ModelIdentity,
                    c.CardNodeIdentity,c.UpgradeLevel,c.Visible,c.Enabled,previewOriginals.Any(o=>ReferenceEquals(o,c.ModelIdentity)),
                    true,c.SelectDispatch)).ToArray();
                allSettled=true; // Preview membership uses original references; grid highlights are intentionally cleared.
            }
            _cachedCandidates=candidates;
            bool previewReady = previewOpen && previewOriginals.Length>=_binding.Prefs.MinSelect &&
                previewOriginals.Length<=_binding.Prefs.MaxSelect && _expectedSelection.SetEquals(previewOriginals) && confirm is not null && confirm.Visible && confirm.Enabled;
            if (!allSettled || _grid.IsAnimatingOut)
                phase = CardSelectionV1Phase.Transient;
            else if (previewReady)
                phase = CardSelectionV1Phase.Preview;
            else if (previewOpen || CountSelected(candidates) == _binding.Prefs.MaxSelect)
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
            _binding.Operation,
            _binding.Prefs.MinSelect,
            _binding.Prefs.MaxSelect,
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
            selectorTop && !previewOpen && _openPreview is not null ? new CardSelectionV1NativeControl(_openPreview,_openPreview.IsVisibleInTree(),_openPreview.IsEnabled,_previewDispatch!) : null,
            confirm, _binding.Enchantment);
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
        if (!binding.Ready || binding.Operation is not (CardSelectionV1Operation.Remove or CardSelectionV1Operation.Enchant)) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareScreen;
        if (!Valid(screen) || !screen.IsVisibleInTree() ||
            !(binding.Operation==CardSelectionV1Operation.Remove ? screen.GetType()==typeof(NDeckCardSelectScreen) :
              screen.GetType()==typeof(NDeckEnchantSelectScreen) && binding.Prefs.MinSelect==binding.Prefs.MaxSelect && binding.Prefs.MaxSelect>=2 &&
              GenericEventV7CardAdapter.EnchantmentScreenMatches(binding,screen))) return false;
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
        previewContainer = RequiredNode<Control>(screen,
            ContainerPath(binding));
        preview = RequiredNode<Control>(previewContainer, CardsPath(binding));
        confirm = RequiredNode<NConfirmButton>(previewContainer, ConfirmPath(binding));
        diagnostic = GenericEventDiagnosticCode.PreparePreviewState;
        return Valid(preview) && ValidExact(confirm) &&
            !previewContainer.Visible && preview.GetChildren().Count==0 &&
            (binding.Operation==CardSelectionV1Operation.Enchant || ValidExact(RequiredNode<NConfirmButton>(screen,"%Confirm")));
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
        if (!Valid(_previewContainer) || !Valid(_preview) || (!IsEnchant && (_openPreview is null || !ValidExact(_openPreview) ||
            !ReferenceEquals(_screen.GetNodeOrNull<NConfirmButton>("%Confirm"),_openPreview))) ||
            !ValidExact(_confirm) ||
            !ReferenceEquals(_screen.GetNodeOrNull<Control>(
                ContainerPath(_binding)), _previewContainer) ||
            !ReferenceEquals(_previewContainer.GetNodeOrNull<Control>(
                CardsPath(_binding)), _preview) ||
            !ReferenceEquals(_previewContainer.GetNodeOrNull<NConfirmButton>(
                ConfirmPath(_binding)), _confirm))
            return false;
        open = _previewContainer.Visible && _previewContainer.IsVisibleInTree();
        if (!open) return true;
        identity = _preview;
        var holders=new List<NPreviewCardHolder>();var cards=new List<NCard>();var models=new List<object>();
        foreach(Node node in _preview.GetChildren())
        {
            if(node is not NPreviewCardHolder holder||!ValidExact(holder)||holders.Count>=_binding.Prefs.MaxSelect||
                holder.CardNode is not NCard card||!ValidExact(card)||!holder.IsVisibleInTree()||!card.IsVisibleInTree()||
                card.Model is not CardModel model||!ReferenceEquals(holder.CardModel,model)||models.Any(o=>ReferenceEquals(o,model)))return false;
            var original=_candidates.SingleOrDefault(c=>ReferenceEquals(c.Model,model));
            if(original is null||!_expectedSelection.Contains(model)||model.Id.Entry!=original.StableKey||model.CurrentUpgradeLevel!=original.UpgradeLevel)return false;
            holders.Add(holder);cards.Add(card);models.Add(model);
        }
        if(_previewHolders is not null && (holders.Count!=_previewHolders.Length||holders.Where((h,i)=>
            !ReferenceEquals(h,_previewHolders[i])||!ReferenceEquals(cards[i],_previewCards![i])).Any()))return false;
        if(holders.Count>=_binding.Prefs.MinSelect && _expectedSelection.SetEquals(models))
        {_previewHolders??=holders.ToArray();_previewCards??=cards.ToArray();}
        originals=models.ToArray();
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

    // Native holder input uses object identity, not scroll coordinates or a
    // computed full-grid layout. Keep the allocated domain and native input gate.
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
        deck=Array.Empty<CardSelectionV1DeckCard>();
        try
        {
            deck=GenericEventV7Binding.CopyDeck(_binding.Player);
            return deck.All(c=>c.ModelIdentity is CardModel card &&
                ReferenceEquals(card.Owner,_binding.Player) && ReferenceEquals(card.RunState,_binding.RunState) &&
                (_binding.SelectionDeck.Any(before=>ReferenceEquals(before.ModelIdentity,card)) ||
                 !_binding.ObservedPreviewClones.Contains(card) && !_binding.ObservedUpgradeClones.Contains(card)));
        }
        catch { return false; }
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
        _binding.Operation,
        _binding.Prefs.MinSelect, _binding.Prefs.MaxSelect,
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
        internal Action Dispatch { get; set; }
    }
}
