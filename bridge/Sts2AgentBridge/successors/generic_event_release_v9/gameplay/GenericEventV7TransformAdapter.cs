using System;
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
using Sts2AgentBridge.Successors.CardTransformV2;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

public sealed class GenericEventV7TransformAdapter : ICardTransformV2NativeAdapter
{
    private const string HighlightWidthParameter = "width";

    private readonly GenericEventV7Binding _binding;
    private readonly CardSelectionV1ParentContext _context;
    private readonly NDeckTransformSelectScreen _screen;
    private readonly NCardGrid _grid;
    private readonly Control _previewContainer;
    private readonly Control _preview;
    private readonly Control _before,_after;
    private readonly NConfirmButton _confirm;
    private readonly NConfirmButton? _openPreview;
    private readonly List<object> _selectedByDispatch=new();
    private object[]? _expectedPreview;
    private readonly GridGeometry _geometry;
    private readonly Action _confirmDispatch,_previewDispatch;
    private readonly GenericEventV7TransformState _transform;
    private NPreviewCardHolder[]? _previewHolders;
    private NCard[]? _previewCards;
    private CardModel[]? _previewClones;
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

    internal GenericEventV7TransformAdapter(
        GenericEventV7Binding binding,
        CardSelectionV1ParentContext context,
        NDeckTransformSelectScreen screen)
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
                out GridGeometry geometry, out _))
            throw new InvalidOperationException("Event selector binding is unsupported.");
        _grid = grid;
        _candidates = candidateBindings;
        _transform=binding.Transform ?? throw new InvalidOperationException("Transformation observation unavailable.");
        _cachedCandidates = candidates;
        _previewContainer = previewContainer;
        _preview = preview;
        _before=RequiredNode<Control>(preview,"%Before");_after=RequiredNode<Control>(preview,"%After");
        _confirm = confirm;
        _geometry = geometry;
        _previewDispatch=RequestPreview;
        if(_binding.Prefs.MinSelect<_binding.Prefs.MaxSelect)
            _openPreview=RequiredNode<NConfirmButton>(_screen,"Confirm");
        foreach(var candidate in _candidates)candidate.Dispatch=()=>Select(candidate);
        _cachedCandidates=WithDispatch(candidates);
        _confirmDispatch = ()=>{
            if(!FreshContext()||!TryCapturePreview(out bool open,out _,out var originals,out var control)||!open||_expectedPreview is null||originals.Length!=_expectedPreview.Length||_previewHolders is null||control?.Visible!=true||control.Enabled!=true)
                throw new InvalidOperationException("Transformation preview changed.");
            _transform.Reserve(originals);
            try{_confirm.ForceClick();}catch{_transform.Fail();throw;}
        };

        _completionTask = _screen.CardsSelected() ??
            throw new InvalidOperationException("Event selector task was unavailable.");
        if (_completionTask.IsCompleted)
            throw new InvalidOperationException("Event selector task was not fresh.");
    }

    internal static bool IsReady(
        GenericEventV7Binding binding,
        NDeckTransformSelectScreen screen,
        out GenericEventDiagnosticCode diagnostic)
    {
        diagnostic = GenericEventDiagnosticCode.PrepareBinding;
        try
        {
            return binding is not null && screen is not null &&
                TryPrepareSurface(binding, screen, out _, out _, out _,
                    out _, out _, out _, out _, out diagnostic);
        }
        catch { return false; }
    }

    public CardTransformV2SurfaceCapture CaptureSurface()
    {
        if (_disposed) return new(Unsupported(),EmptyEffect());
        try {var surface=CaptureCore();return new(surface,_transform.Capture());}
        catch {_transform.Fail();return new(Unsupported(),EmptyEffect());}
    }

    public void Dispose() { _transform.Close(); _disposed = true; }
    private static CardTransformV2EffectWitness EmptyEffect()=>new(Array.Empty<CardTransformV2CommandWitness>(),Array.Empty<object>(),Array.Empty<CardTransformV2Insertion>());

    private CardSelectionV1SurfaceCapture CaptureCore()
    {
        if (!TryBoundForeground(out bool selectorClosed) ||
            !TryCopyDeck(out CardSelectionV1DeckCard[] deck))
            return Unsupported();
        SnapshotTask();

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
                !_geometry.Matches(_grid) ||
                !TrySnapshotHolders(_grid, out NGridCardHolder[] holders) ||
                !TryCaptureBindings(holders, _candidates, out candidates,
                    out bool allSettled, _geometry))
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
                previewOriginals.Length<=_binding.Prefs.MaxSelect && _previewHolders is not null && confirm is not null && confirm.Visible && confirm.Enabled;
            if (!allSettled || _grid.IsAnimatingOut)
                phase = CardSelectionV1Phase.Transient;
            else if (previewReady)
                phase = CardSelectionV1Phase.Preview;
            else if (previewOpen || _expectedPreview is not null || CountSelected(candidates) == _binding.Prefs.MaxSelect)
                phase = CardSelectionV1Phase.Transient;
            else
                phase = CardSelectionV1Phase.Selecting;
        }

        if (_binding.Failed || _binding.ChosenTask?.IsFaulted == true || _binding.ChosenTask?.IsCanceled == true || _binding.RequestTask?.IsFaulted == true || _binding.RequestTask?.IsCanceled == true)
            return Unsupported();
        bool effectCompletion = selectorClosed && _taskState == CardSelectionV1TaskState.Succeeded && _binding.EffectCompleted(_taskResult) && _transform.Complete;
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
            CardSelectionV1Operation.Transform,
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
            !selectorClosed && !previewOpen && _expectedPreview is null ? PreviewControl(candidates) : null,
            confirm);
    }

    private CardSelectionV1NativeCandidate[] WithDispatch(CardSelectionV1NativeCandidate[] values)=>values.Select(c=>
        new CardSelectionV1NativeCandidate(c.Slot,c.StableKey,c.HolderIdentity,c.ModelIdentity,c.CardNodeIdentity,c.UpgradeLevel,
            c.Visible,c.Enabled,c.Selected,c.SelectionSettled,_candidates[c.Slot].Dispatch)).ToArray();

    private bool FreshContext()=>!_disposed&&!_binding.Failed&&_binding.MatchesChildBinding()&&_binding.MatchesCurrentDeck()&&
        TryBoundForeground(out bool closed)&&!closed&&Valid(_screen)&&_screen.IsVisibleInTree()&&!_completionTask.IsCompleted;
    private bool FreshSelection(out CardSelectionV1NativeCandidate[] candidates)
    {
        candidates=Array.Empty<CardSelectionV1NativeCandidate>();
        if(!FreshContext()||_expectedPreview is not null||_previewContainer.Visible||
            !ReferenceEquals(_screen.GetNodeOrNull<NCardGrid>("%CardGrid"),_grid)||!_geometry.Matches(_grid)||_grid.IsAnimatingOut||
            !TrySnapshotHolders(_grid,out var holders)||!TryCaptureBindings(holders,_candidates,out candidates,out bool settled,_geometry)||!settled)return false;
        var selected=candidates.Where(c=>c.Selected).Select(c=>c.ModelIdentity).ToArray();
        return selected.Length==_selectedByDispatch.Count&&selected.All(o=>_selectedByDispatch.Any(p=>ReferenceEquals(p,o)));
    }
    private CardSelectionV1NativeControl? PreviewControl(CardSelectionV1NativeCandidate[] candidates)
    {
        if(_openPreview is null)return null;
        if(!Valid(_openPreview)||!ReferenceEquals(_screen.GetNodeOrNull<NConfirmButton>("Confirm"),_openPreview))
            throw new InvalidOperationException("Transformation root preview control replaced.");
        int count=CountSelected(candidates);
        return new(_openPreview,_openPreview.IsVisibleInTree(),_openPreview.IsEnabled&&count>=_binding.Prefs.MinSelect&&count<_binding.Prefs.MaxSelect,_previewDispatch);
    }
    private void Select(CandidateBinding candidate)
    {
        try
        {
            if(!FreshSelection(out var current)||!current[candidate.Slot].Visible||!current[candidate.Slot].Enabled||current[candidate.Slot].Selected||
                _selectedByDispatch.Count>=_binding.Prefs.MaxSelect)throw new InvalidOperationException("Stale transformation selection.");
            _selectedByDispatch.Add(candidate.Model);
            if(_selectedByDispatch.Count==_binding.Prefs.MaxSelect)_expectedPreview=_selectedByDispatch.ToArray();
            DispatchCard(candidate.Holder);
        }
        catch{_transform.Fail();throw;}
    }
    private void RequestPreview()
    {
        try
        {
            if(!FreshSelection(out var candidates)||_selectedByDispatch.Count<_binding.Prefs.MinSelect||_selectedByDispatch.Count>=_binding.Prefs.MaxSelect||
                PreviewControl(candidates) is not {Visible:true,Enabled:true})throw new InvalidOperationException("Stale transformation preview control.");
            _expectedPreview=_selectedByDispatch.ToArray();
            _openPreview!.ForceClick();
        }
        catch{_transform.Fail();throw;}
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
        NDeckTransformSelectScreen screen,
        out NCardGrid grid,
        out CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates,
        out Control previewContainer,
        out Control preview,
        out NConfirmButton confirm,
        out GridGeometry geometry,
        out GenericEventDiagnosticCode diagnostic)
    {
        grid = null!;
        bindings = Array.Empty<CandidateBinding>();
        candidates = Array.Empty<CardSelectionV1NativeCandidate>();
        previewContainer = null!;
        preview = null!;
        confirm = null!;
        geometry = null!;
        diagnostic = GenericEventDiagnosticCode.PrepareBinding;
        if (!binding.Ready || binding.Operation!=CardSelectionV1Operation.Transform || binding.Prefs.MinSelect<1 || binding.Prefs.MinSelect>binding.Prefs.MaxSelect || binding.Prefs.MaxSelect>8 || (binding.Prefs.MinSelect<binding.Prefs.MaxSelect&&!binding.Prefs.RequireManualConfirmation) || binding.Transform is null) return false;
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
        if (!TryCreateBindings(holders, binding.EligibleOriginals, out bindings, out candidates)) return false;
        diagnostic = GenericEventDiagnosticCode.PrepareGeometry;
        if (!GridGeometry.TryBind(grid, bindings, out geometry, ref diagnostic)) return false;
        candidates=geometry.Mask(candidates, ref diagnostic);
        if(!InitialCandidatesValid(candidates, ref diagnostic))return false;
        diagnostic = GenericEventDiagnosticCode.PreparePreviewNodes;
        previewContainer = RequiredNode<Control>(screen,
            "%PreviewContainer");
        preview = RequiredNode<NTransformPreview>(previewContainer, "TransformPreview");
        confirm = RequiredNode<NConfirmButton>(previewContainer, "Confirm");
        diagnostic = GenericEventDiagnosticCode.PreparePreviewState;
        return (binding.Prefs.MinSelect==binding.Prefs.MaxSelect || Valid(RequiredNode<NConfirmButton>(screen,"Confirm"))) && Valid(preview) && ValidExact(confirm) &&
            !previewContainer.Visible &&
            RequiredNode<Control>(preview,"%Before").GetChildren().Count==0 &&
            Valid(RequiredNode<Control>(preview,"%After"));
    }

    private static bool InitialForeground(
        GenericEventV7Binding binding,
        NDeckTransformSelectScreen screen) =>
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
        if (!Valid(_previewContainer) || !Valid(_preview) ||
            !ValidExact(_confirm) ||
            !ReferenceEquals(_screen.GetNodeOrNull<Control>(
                "%PreviewContainer"), _previewContainer) ||
            !ReferenceEquals(_previewContainer.GetNodeOrNull<NTransformPreview>(
                "TransformPreview"), _preview) ||
            !Valid(_before)||!Valid(_after)||!ReferenceEquals(_preview.GetNodeOrNull<Control>("%Before"),_before)||!ReferenceEquals(_preview.GetNodeOrNull<Control>("%After"),_after) ||
            !ReferenceEquals(_previewContainer.GetNodeOrNull<NConfirmButton>(
                "Confirm"), _confirm))
            return false;
        open = _previewContainer.Visible && _previewContainer.IsVisibleInTree();
        if (!open) return true;
        if(_expectedPreview is null)return false;
        identity = _preview;
        var holders=new List<NPreviewCardHolder>();var cards=new List<NCard>();var models=new List<object>();var clones=new List<CardModel>();
        foreach(Node node in _before.GetChildren())
        {
            if(node is not NPreviewCardHolder holder||!ValidExact(holder)||holders.Count>=_binding.Prefs.MaxSelect||
                holder.CardNode is not NCard card||!ValidExact(card)||!holder.IsVisibleInTree()||!card.IsVisibleInTree()||
                card.Model is not CardModel model||!ReferenceEquals(holder.CardModel,model)||clones.Any(o=>ReferenceEquals(o,model)))return false;
            var original=_candidates.SingleOrDefault(c=>ReferenceEquals(c.Model,model));
            if(original is null||!_expectedPreview.Any(o=>ReferenceEquals(o,model))||model.Id.Entry!=original.StableKey||model.CurrentUpgradeLevel!=original.UpgradeLevel||
                models.Any(o=>ReferenceEquals(o,model)))return false;
            var originalModel=model;
            holders.Add(holder);cards.Add(card);clones.Add(model);models.Add(originalModel);
        }
        if(_previewHolders is not null && (holders.Count!=_previewHolders.Length||holders.Where((h,i)=>
            !ReferenceEquals(h,_previewHolders[i])||!ReferenceEquals(cards[i],_previewCards![i])||!ReferenceEquals(clones[i],_previewClones![i])).Any()))return false;
        if(holders.Count==_expectedPreview.Length)
        {_previewHolders??=holders.ToArray();_previewCards??=cards.ToArray();_previewClones??=clones.ToArray();}
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

    private sealed class GridGeometry
    {
        private const float Padding = 40f;
        private const float TopPadding = 80f;
        private const float BottomPadding = 320f;

        private GridGeometry(Control scroll, Vector2 scrollSize,
            Vector2 scrollPosition, Vector2 gridSize, int yOffset,
            Vector2 cardSize, ProbeGeometry probe)
        {
            Scroll = scroll;
            ScrollSize = scrollSize;
            ScrollPosition = scrollPosition;
            GridSize = gridSize;
            YOffset = yOffset;
            CardSize = cardSize;
            Probe = probe;
        }

        private Control Scroll { get; }
        private Vector2 ScrollSize { get; }
        private Vector2 ScrollPosition { get; }
        private Vector2 GridSize { get; }
        private int YOffset { get; }
        private Vector2 CardSize { get; }
        private ProbeGeometry Probe { get; }
        internal CardSelectionV1NativeCandidate[] Mask(CardSelectionV1NativeCandidate[] candidates)=>Probe.Mask(candidates);
        internal CardSelectionV1NativeCandidate[] Mask(CardSelectionV1NativeCandidate[] candidates, ref GenericEventDiagnosticCode diagnostic)=>Probe.Mask(candidates, ref diagnostic);

        internal static bool TryBind(NCardGrid grid, CandidateBinding[] candidates,
            out GridGeometry geometry, ref GenericEventDiagnosticCode diagnostic)
        {
            geometry = null!;
            int count=candidates.Length;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollMissing;
            Control? scroll = grid.GetNodeOrNull<Control>("%ScrollContainer");
            diagnostic = GenericEventDiagnosticCode.GeometryCandidateCount;
            if (count is < 2 or > 64) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollMissing;
            if (scroll is null) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollInvalid;
            if (!Valid(scroll)) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollInvisible;
            if (!scroll.IsVisibleInTree()) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollSize;
            Vector2 scrollSize = scroll.Size;
            diagnostic = GenericEventDiagnosticCode.GeometryGridSize;
            Vector2 gridSize = grid.Size;
            diagnostic = GenericEventDiagnosticCode.GeometryCardSize;
            Vector2 cardSize = NCard.defaultSize * NCardHolder.smallScale;
            diagnostic = GenericEventDiagnosticCode.GeometryYOffset;
            int yOffset = grid.YOffset;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollPosition;
            if (!CompleteVisibleLayout(count, scrollSize, scroll.Position,
                    gridSize, cardSize, yOffset, ref diagnostic)) return false;
            if (!ProbeGeometry.TryBind(grid, candidates, out var probe, ref diagnostic)) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollPosition;
            geometry = new GridGeometry(scroll, scrollSize, scroll.Position,
                gridSize, yOffset, cardSize, probe);
            return true;
        }

        internal bool Matches(NCardGrid grid)
        {
            if (!Valid(Scroll) ||
                !ReferenceEquals(grid.GetNodeOrNull<Control>("%ScrollContainer"), Scroll))
                return false;
            Vector2 cardSize = NCard.defaultSize * NCardHolder.smallScale;
            return Scroll.Size == ScrollSize && Scroll.Position == ScrollPosition &&
                grid.Size == GridSize && grid.YOffset == YOffset &&
                cardSize == CardSize && !grid.IsAnimatingOut && Probe.Matches();
        }

        private static bool CompleteVisibleLayout(int count, Vector2 scrollSize,
            Vector2 scrollPosition, Vector2 gridSize, Vector2 cardSize, int yOffset, ref GenericEventDiagnosticCode diagnostic)
        {
            diagnostic = GenericEventDiagnosticCode.GeometryScrollSize;
            if (!FinitePositive(scrollSize.X) || !FinitePositive(scrollSize.Y)) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollPosition;
            if (!float.IsFinite(scrollPosition.X) || !float.IsFinite(scrollPosition.Y)) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryGridSize;
            if (!FinitePositive(gridSize.X) || !FinitePositive(gridSize.Y)) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryCardSize;
            if (!FinitePositive(cardSize.X) || !FinitePositive(cardSize.Y)) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryYOffset;
            if (yOffset < 0) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryColumns;
            int columns = (int)((scrollSize.X + Padding) / (cardSize.X + Padding));
            if (columns is < 1 or > 64) return false;
            int rows = (count + columns - 1) / columns;
            float containedHeight = rows * cardSize.Y + (rows - 1) * Padding;
            float expectedScrollHeight = containedHeight + TopPadding +
                BottomPadding + yOffset;
            float expectedPositionY = Math.Max(0f,
                (gridSize.Y - scrollSize.Y) * 0.5f);
            diagnostic = GenericEventDiagnosticCode.GeometryScrollHeightMismatch;
            if (!SameFloat(scrollSize.Y, expectedScrollHeight)) return false;
            diagnostic = GenericEventDiagnosticCode.GeometryScrollPositionMismatch;
            return SameFloat(scrollPosition.Y, expectedPositionY);
        }

        private static bool FinitePositive(float value) =>
            float.IsFinite(value) && value > 0f;

        private static bool SameFloat(float left, float right) =>
            BitConverter.SingleToInt32Bits(left) ==
            BitConverter.SingleToInt32Bits(right);
    }

    // A release-only certificate: candidates remain in the complete domain,
    // but only an exact retained control below inherited clipping may dispatch.
    private sealed class ProbeGeometry
    {
        private readonly Control _clip;
        private readonly Rect2 _clipRect;
        private readonly NodeGeometry[][] _chains;
        private readonly bool[] _below;
        private ProbeGeometry(Control clip,Rect2 clipRect,NodeGeometry[][] chains,bool[] below)
        { _clip=clip;_clipRect=clipRect;_chains=chains;_below=below; }
        internal static bool TryBind(NCardGrid grid,CandidateBinding[] candidates,out ProbeGeometry result, ref GenericEventDiagnosticCode diagnostic)
        {
            result=null!;
            Control? clip=null;Node? cursor=grid;
            var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
            for(int depth=0;depth<=32&&cursor is not null;depth++)
            {
                diagnostic=GenericEventDiagnosticCode.GeometryClipSearchInvalid;
                if(!Valid(cursor))return false;
                diagnostic=GenericEventDiagnosticCode.GeometryClipSearchCycle;
                if(!seen.Add(cursor))return false;
                diagnostic=GenericEventDiagnosticCode.GeometryClipMissing;
                if(cursor is Control control&&control.ClipContents){clip=control;break;}
                diagnostic=GenericEventDiagnosticCode.GeometryClipSearchDepth;
                if(depth==32)return false;
                diagnostic=GenericEventDiagnosticCode.GeometryClipMissing;
                cursor=cursor.GetParent();
            }
            diagnostic=GenericEventDiagnosticCode.GeometryClipMissing;
            if(clip is null)return false;
            diagnostic=GenericEventDiagnosticCode.GeometryClipRect;
            if(!TryRect(clip,out var clipRect))return false;
            diagnostic=GenericEventDiagnosticCode.GeometryCanvasInvalid;
            Rid canvas=clip.GetCanvas();if(!canvas.IsValid)return false;
            var chains=new List<NodeGeometry[]>();
            if(!TryChain(grid,clip,canvas,out var gridChain,ref diagnostic))return false;chains.Add(gridChain);
            var below=new bool[candidates.Length];
            for(int index=0;index<candidates.Length;index++)
            {
                CandidateBinding candidate=candidates[index];bool full=true;
                foreach(Control control in new Control[]{candidate.Holder,candidate.Card,candidate.Hitbox})
                {
                    if(!TryChain(control,clip,canvas,out var chain,ref diagnostic))return false;
                    diagnostic=GenericEventDiagnosticCode.GeometryControlRect;
                    if(!TryRect(control,out var rect))return false;
                    chains.Add(chain);full&=rect.Position.Y>clipRect.Position.Y+clipRect.Size.Y;
                }
                below[index]=full;
            }
            result=new ProbeGeometry(clip,clipRect,chains.ToArray(),below);
            return result.Matches(ref diagnostic);
        }
        internal bool Matches()
        { var diagnostic=GenericEventDiagnosticCode.PrepareGeometry; return Matches(ref diagnostic); }
        internal bool Matches(ref GenericEventDiagnosticCode diagnostic)
        {
            diagnostic=GenericEventDiagnosticCode.GeometryClipChanged;
            if(!Valid(_clip)||!_clip.ClipContents||!TryRect(_clip,out var rect)||!Same(rect,_clipRect))return false;
            foreach(var chain in _chains)
                foreach(var node in chain)
                    if(!node.Matches(ref diagnostic))return false;
            return true;
        }
        internal CardSelectionV1NativeCandidate[] Mask(CardSelectionV1NativeCandidate[] candidates)
        { var diagnostic=GenericEventDiagnosticCode.PrepareGeometry; return Mask(candidates,ref diagnostic); }
        internal CardSelectionV1NativeCandidate[] Mask(CardSelectionV1NativeCandidate[] candidates, ref GenericEventDiagnosticCode diagnostic)
        {
            diagnostic=GenericEventDiagnosticCode.GeometryMaskCount;
            if(candidates.Length!=_below.Length||!Matches(ref diagnostic))throw new InvalidOperationException("Offscreen geometry changed.");
            return candidates.Select((c,i)=>new CardSelectionV1NativeCandidate(c.Slot,c.StableKey,c.HolderIdentity,c.ModelIdentity,
                c.CardNodeIdentity,c.UpgradeLevel,c.Visible,c.Enabled&&_below[i],c.Selected,c.SelectionSettled,c.SelectDispatch)).ToArray();
        }
        private static bool TryChain(Node start,Control clip,Rid canvas,out NodeGeometry[] chain, ref GenericEventDiagnosticCode diagnostic)
        {
            chain=Array.Empty<NodeGeometry>();var values=new List<NodeGeometry>();
            var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);Node? current=start;
            for(int depth=0;depth<=32&&current is not null;depth++)
            {
                bool atClip=ReferenceEquals(current,clip);
                diagnostic=GenericEventDiagnosticCode.GeometryChainInvalid;
                if(!Valid(current))return false;
                diagnostic=GenericEventDiagnosticCode.GeometryChainNonCanvas;
                if(current is not CanvasItem)return false;
                diagnostic=GenericEventDiagnosticCode.GeometryChainCycle;
                if(!seen.Add(current))return false;
                diagnostic=GenericEventDiagnosticCode.GeometryChainDepth;
                if(!atClip&&depth==32)return false;
                diagnostic=GenericEventDiagnosticCode.GeometryChainUnreached;
                Node? parent=atClip?null:current.GetParent();
                if(!NodeGeometry.TryBind(current,canvas,parent,!atClip,out var snapshot,ref diagnostic))return false;
                values.Add(snapshot);if(atClip){chain=values.ToArray();return true;}
                current=parent;
            }
            diagnostic=GenericEventDiagnosticCode.GeometryChainUnreached;
            return false;
        }
        private static bool Finite(Vector2 value)=>float.IsFinite(value.X)&&float.IsFinite(value.Y);
        private static bool AxisAligned(Transform2D value)=>Finite(value.X)&&Finite(value.Y)&&Finite(value.Origin)&&
            value.X.X>0&&value.Y.Y>0&&value.X.Y==0&&value.Y.X==0;
        private static bool Same(Rect2 left,Rect2 right)=>left.Position==right.Position&&left.Size==right.Size;
        private static bool Same(Transform2D left,Transform2D right)=>left.X==right.X&&left.Y==right.Y&&left.Origin==right.Origin;
        private static bool TryRect(Control control,out Rect2 rectangle)
        {
            rectangle=control.GetGlobalRect();
            return Finite(rectangle.Position)&&Finite(rectangle.Size)&&rectangle.Size.X>0&&rectangle.Size.Y>0&&
                float.IsFinite(rectangle.Position.X+rectangle.Size.X)&&float.IsFinite(rectangle.Position.Y+rectangle.Size.Y);
        }
        private sealed class NodeGeometry
        {
            private readonly Node _node;
            private readonly Node? _parent;
            private readonly bool _trackParent;
            private readonly Rid _canvas;
            private readonly Transform2D _transform;
            private readonly Rect2 _rectangle;
            private readonly bool _clip;
            private NodeGeometry(Node node,Node? parent,bool trackParent,Rid canvas,Transform2D transform,Rect2 rectangle,bool clip)
            {_node=node;_parent=parent;_trackParent=trackParent;_canvas=canvas;_transform=transform;_rectangle=rectangle;_clip=clip;}
            internal static bool TryBind(Node node,Rid canvas,Node? parent,bool trackParent,out NodeGeometry result, ref GenericEventDiagnosticCode diagnostic)
            {
                result=null!;Transform2D transform=default;Rect2 rectangle=default;bool clip=false;
                if(node is CanvasItem item)
                {
                    diagnostic=GenericEventDiagnosticCode.GeometryTopLevel;
                    if(item.IsSetAsTopLevel())return false;
                    diagnostic=GenericEventDiagnosticCode.GeometryCanvasMismatch;
                    if(item.GetCanvas()!=canvas)return false;
                    diagnostic=GenericEventDiagnosticCode.GeometryTransform;
                    transform=item.GetGlobalTransform();if(!AxisAligned(transform))return false;
                }
                if(node is Control control)
                {
                    diagnostic=GenericEventDiagnosticCode.GeometryNodeRect;
                    rectangle=control.GetGlobalRect();if(!Finite(rectangle.Position)||!Finite(rectangle.Size))return false;
                    diagnostic=GenericEventDiagnosticCode.GeometryNodeClipChanged;
                    clip=control.ClipContents;
                }
                result=new NodeGeometry(node,parent,trackParent,canvas,transform,rectangle,clip);return true;
            }
            internal bool Matches(ref GenericEventDiagnosticCode diagnostic)
            {
                diagnostic=GenericEventDiagnosticCode.GeometryChainInvalid;
                if(!Valid(_node))return false;
                diagnostic=GenericEventDiagnosticCode.GeometryParentChanged;
                if(_trackParent&&!ReferenceEquals(_node.GetParent(),_parent))return false;
                if(_node is CanvasItem item)
                {
                    diagnostic=GenericEventDiagnosticCode.GeometryTopLevel;
                    if(item.IsSetAsTopLevel())return false;
                    diagnostic=GenericEventDiagnosticCode.GeometryCanvasMismatch;
                    if(item.GetCanvas()!=_canvas)return false;
                    diagnostic=GenericEventDiagnosticCode.GeometryTransformChanged;
                    if(!Same(item.GetGlobalTransform(),_transform))return false;
                }
                if(_node is Control control)
                {
                    diagnostic=GenericEventDiagnosticCode.GeometryNodeClipChanged;
                    if(control.ClipContents!=_clip)return false;
                    diagnostic=GenericEventDiagnosticCode.GeometryRectChanged;
                    if(!Same(control.GetGlobalRect(),_rectangle))return false;
                }
                return true;
            }
        }
    }

    private static bool TryCaptureBindings(
        IReadOnlyList<NGridCardHolder> holdersSnapshot,
        CandidateBinding[] bindings,
        out CardSelectionV1NativeCandidate[] candidates,
        out bool allSettled, GridGeometry? geometry=null)
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
                binding.Hitbox.IsEnabled,
                endpoint == CardSelectionV1HighlightEndpoint.Selected,
                settled,
                binding.Dispatch);
        }
        if(geometry is not null)candidates=geometry.Mask(candidates);
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
        IReadOnlyList<CardSelectionV1NativeCandidate> candidates)
    {
        var diagnostic=GenericEventDiagnosticCode.PrepareGeometry;
        return InitialCandidatesValid(candidates,ref diagnostic);
    }

    private static bool InitialCandidatesValid(
        IReadOnlyList<CardSelectionV1NativeCandidate> candidates, ref GenericEventDiagnosticCode diagnostic)
    {
        bool enabled = false;
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
        {
            diagnostic=GenericEventDiagnosticCode.GeometryInitiallySelected;
            if(candidate.Selected)return false;
            diagnostic=GenericEventDiagnosticCode.GeometryCandidateInvisible;
            if(!candidate.Visible)return false;
            enabled |= candidate.Enabled;
        }
        diagnostic=GenericEventDiagnosticCode.GeometryNoneEligible;
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
        CardSelectionV1Operation.Transform,
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
