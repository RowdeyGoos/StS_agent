using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.CardSelectionV1;

public sealed class CardSelectionV1Session : IDisposable
{
    private readonly object _gate = new();
    private readonly int _ownerThreadId = Environment.CurrentManagedThreadId;
    private readonly CardSelectionV1ParentContext _context;
    private readonly ICardSelectionV1NativeAdapter _adapter;
    private readonly List<CardSelectionV1ActionResult> _history = new();
    private readonly HashSet<string> _reservedDecisions = new(StringComparer.Ordinal);
    private BoundSurface? _bound;
    private PublishedDecision? _published;
    private PendingAction? _pending;
    private object[] _selected = Array.Empty<object>();
    private CardSelectionV1ResolvedResult? _resolved;
    private bool _awaitingCommit;
    private object[] _effectProgress = Array.Empty<object>();
    private bool _taskSucceededSeen;
    private bool _selectorClosedSeen;
    private bool _effectWitnessSeen;
    private bool _inside;
    private bool _interfered;
    private bool _dispatching;
    private bool _unsupported;
    private bool _disposed;
    private bool _cleanupFailed;
    private int _acceptedActions;
    private int _pendingReads;

    public CardSelectionV1Session(
        CardSelectionV1ParentContext context,
        ICardSelectionV1NativeAdapter adapter)
    {
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _adapter = adapter ?? throw new ArgumentNullException(nameof(adapter));
        if (!ValidContext(context))
            throw new ArgumentException("The card-selection parent context is invalid.", nameof(context));
    }

    public ICardSelectionV1ReadValue Read()
    {
        lock (_gate)
        {
            if (_inside)
            {
                _interfered = true;
                return Waiting("transient");
            }
            if (Environment.CurrentManagedThreadId != _ownerThreadId)
            {
                _unsupported = true;
                return Unsupported();
            }
            if (_disposed || _unsupported) return Unsupported();
            if (_resolved is not null) return _resolved;
            if (_dispatching) return Waiting("transient");
            if (_pending is not null || _awaitingCommit) return Reconcile();
            return CaptureAndPublish(initial: _bound is null);
        }
    }

    public ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (_inside)
            {
                _interfered = true;
                return Failure("rejected");
            }
            if (Environment.CurrentManagedThreadId != _ownerThreadId)
            {
                _unsupported = true;
                return Failure("unsupported");
            }
            if (_disposed || _unsupported) return Failure("unsupported");
            if (_resolved is not null || _dispatching || _pending is not null ||
                _awaitingCommit || _published is null ||
                !CardSelectionV1Identity.IsDecisionId(decisionId) ||
                !CardSelectionV1Identity.IsActionId(actionId) ||
                !string.Equals(_published.Observation.DecisionId, decisionId,
                    StringComparison.Ordinal) ||
                !_published.Actions.TryGetValue(actionId!, out ActionProbe? probe) ||
                _reservedDecisions.Contains(decisionId!) ||
                _acceptedActions >= CardSelectionV1Limits.MaximumAcceptedActions)
            {
                return Failure("rejected");
            }

            CardSelectionV1SurfaceCapture capture;
            PublishedDecision? recaptured;
            try
            {
                _inside = true;
                capture = _adapter.CaptureSurface();
                if (_disposed || _interfered ||
                    !TryProject(capture, initial: false, out recaptured) ||
                    recaptured is null || !SamePublished(_published, recaptured) ||
                    !string.Equals(recaptured.Observation.DecisionId, decisionId,
                        StringComparison.Ordinal))
                {
                    LatchUnsupported();
                    return Failure("unsupported");
                }
            }
            catch
            {
                LatchUnsupported();
                return Failure("unsupported");
            }
            finally
            {
                _inside = false;
            }

            if (!recaptured.Actions.TryGetValue(actionId!, out ActionProbe? currentProbe) ||
                !SameProbe(probe, currentProbe))
            {
                LatchUnsupported();
                return Failure("unsupported");
            }

            var expected = BuildExpectedSelection(probe);
            if (expected is null)
                return Failure("rejected");

            _pending = new PendingAction(
                probe.Kind, probe.Slot, decisionId!, actionId!, expected,
                probe.Dispatch);
            _published = null;
            _pendingReads = 0;
            _dispatching = true;
            _acceptedActions++;
            _reservedDecisions.Add(decisionId!);

            try
            {
                _inside = true;
                probe.Dispatch();
                if (_disposed || _interfered)
                    throw new InvalidOperationException("Card selection dispatch was interrupted.");
                return new CardSelectionV1DispatchReceipt(
                    _context.SessionNonce, decisionId!, actionId!);
            }
            catch
            {
                LatchUnsupported();
                return Failure("uncertain");
            }
            finally
            {
                _inside = false;
                _dispatching = false;
            }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (Environment.CurrentManagedThreadId != _ownerThreadId)
                throw new InvalidOperationException("Card-selection cleanup requires the owner thread.");
            if (_disposed)
            {
                if (_cleanupFailed)
                    throw new InvalidOperationException("Card-selection cleanup failed.");
                return;
            }
            _disposed = true;
            _unsupported = true;
            _published = null;
            _pending = null;
            _awaitingCommit = false;
            _resolved = null;
            if (_inside)
            {
                _interfered = true;
                _cleanupFailed = true;
                return;
            }
            try
            {
                _interfered = false;
                _inside = true;
                _adapter.Dispose();
                if (_interfered)
                    throw new InvalidOperationException("Card-selection cleanup was reentered.");
            }
            catch
            {
                _cleanupFailed = true;
                throw new InvalidOperationException("Card-selection cleanup failed.");
            }
            finally
            {
                _inside = false;
            }
        }
    }

    private ICardSelectionV1ReadValue CaptureAndPublish(bool initial)
    {
        CardSelectionV1SurfaceCapture capture;
        try
        {
            _inside = true;
            capture = _adapter.CaptureSurface();
            if (_disposed || _interfered)
            {
                LatchUnsupported();
                return Unsupported();
            }
            if (capture is null)
            {
                LatchUnsupported();
                return Unsupported();
            }
            if (capture.Status == CardSelectionV1SurfaceStatus.Missing)
            {
                if (_bound is null) return Waiting("transient");
                LatchUnsupported();
                return Unsupported();
            }
            if (capture.Phase == CardSelectionV1Phase.Transient)
            {
                bool validTransient = capture.TaskState == CardSelectionV1TaskState.Incomplete &&
                    capture.TaskResultOriginals.Count == 0 && !capture.PreviewOpen &&
                    capture.PreviewIdentity is null && capture.PreviewOriginals.Count == 0 &&
                    !capture.EffectCompletionObserved && ValidateCollections(capture) &&
                    (_bound is null
                        ? SameContext(capture) && ValidPolicy(capture) &&
                          capture.ScreenIdentity is not null && capture.CompletionTaskIdentity is not null &&
                          SelectedFromCapture(capture).Length == 0
                        : ValidateBound(capture) && SameSet(SelectedFromCapture(capture), _selected));
                if (!validTransient)
                {
                    LatchUnsupported();
                    return Unsupported();
                }
                return Waiting("transient");
            }
            if (!TryProject(capture, initial, out PublishedDecision? decision) ||
                decision is null)
            {
                LatchUnsupported();
                return Unsupported();
            }
            _published = decision;
            return decision.Observation;
        }
        catch
        {
            LatchUnsupported();
            return Unsupported();
        }
        finally
        {
            _inside = false;
        }
    }

    private ICardSelectionV1ReadValue Reconcile()
    {
        if (++_pendingReads > CardSelectionV1Limits.MaximumPendingReads)
        {
            LatchUnsupported();
            return Unsupported();
        }

        CardSelectionV1SurfaceCapture capture;
        try
        {
            _inside = true;
            capture = _adapter.CaptureSurface();
            if (_disposed || _interfered || capture is null ||
                capture.Status != CardSelectionV1SurfaceStatus.Available ||
                !ValidateBound(capture) || !ValidateStateShape(capture))
            {
                LatchUnsupported();
                return Unsupported();
            }

            if (capture.TaskState is CardSelectionV1TaskState.Canceled or
                CardSelectionV1TaskState.Faulted)
            {
                LatchUnsupported();
                return Unsupported();
            }

            if (_pending is not null)
                return ReconcilePending(capture, _pending);
            return ReconcileCommit(capture);
        }
        catch
        {
            LatchUnsupported();
            return Unsupported();
        }
        finally
        {
            _inside = false;
        }
    }

    private ICardSelectionV1ReadValue ReconcilePending(
        CardSelectionV1SurfaceCapture capture,
        PendingAction pending)
    {
        if (!ValidateDeckPrefix(capture, pending.ExpectedSelection, out bool effectComplete))
        {
            LatchUnsupported();
            return Unsupported();
        }

        switch (pending.Kind)
        {
            case ActionKind.Select:
                return ReconcileSelect(capture, pending, effectComplete);
            case ActionKind.Preview:
                return ReconcilePreview(capture, pending);
            case ActionKind.Confirm:
                AddHistory(pending, "committed");
                _pending = null;
                _awaitingCommit = true;
                return ReconcileCommit(capture, effectComplete);
            default:
                LatchUnsupported();
                return Unsupported();
        }
    }

    private ICardSelectionV1ReadValue ReconcileSelect(
        CardSelectionV1SurfaceCapture capture,
        PendingAction pending,
        bool effectComplete)
    {
        object[] observedSelection = SelectedFromCapture(capture);
        bool selectedObserved = SameSet(observedSelection, pending.ExpectedSelection);
        bool taskSucceeded = capture.TaskState == CardSelectionV1TaskState.Succeeded;
        bool finalAuto = _context.CommitMode == CardSelectionV1CommitMode.AutoAtMax &&
            pending.ExpectedSelection.Length == _context.MaxSelect;
        bool previewObserved = _context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
            ValidPreview(capture, pending.ExpectedSelection);
        if (!finalAuto && !DeckEqualsBaseline(capture.Deck))
        {
            LatchUnsupported();
            return Unsupported();
        }

        if (!selectedObserved && !previewObserved && !(finalAuto && taskSucceeded &&
            ExactTaskResult(capture, pending.ExpectedSelection)))
        {
            if (capture.Phase == CardSelectionV1Phase.Transient ||
                (capture.TaskState == CardSelectionV1TaskState.Incomplete &&
                 SameSet(observedSelection, _selected)))
                return Waiting("selecting");
            LatchUnsupported();
            return Unsupported();
        }

        if (!finalAuto && capture.TaskState != CardSelectionV1TaskState.Incomplete)
        {
            LatchUnsupported();
            return Unsupported();
        }

        AddHistory(pending, "selected");
        _selected = (object[])pending.ExpectedSelection.Clone();
        _pending = null;
        _pendingReads = 0;

        if (finalAuto)
        {
            _awaitingCommit = true;
            return ReconcileCommit(capture, effectComplete);
        }

        if (_context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
            capture.Phase == CardSelectionV1Phase.Preview)
        {
            if (!ValidPreview(capture, _selected))
            {
                LatchUnsupported();
                return Unsupported();
            }
        }
        else if (capture.Phase != CardSelectionV1Phase.Selecting ||
                 !capture.SelectorTop || capture.SelectorClosed || capture.PreviewOpen)
        {
            if (capture.Phase == CardSelectionV1Phase.Transient)
                return Waiting("transient");
            LatchUnsupported();
            return Unsupported();
        }

        return PublishCaptured(capture);
    }

    private ICardSelectionV1ReadValue ReconcilePreview(
        CardSelectionV1SurfaceCapture capture,
        PendingAction pending)
    {
        if (capture.TaskState != CardSelectionV1TaskState.Incomplete ||
            !ValidPreview(capture, pending.ExpectedSelection) ||
            !DeckEqualsBaseline(capture.Deck))
        {
            if (capture.Phase == CardSelectionV1Phase.Transient)
                return Waiting("transient");
            LatchUnsupported();
            return Unsupported();
        }
        AddHistory(pending, "previewed");
        _selected = (object[])pending.ExpectedSelection.Clone();
        _pending = null;
        _pendingReads = 0;
        return PublishCaptured(capture);
    }

    private ICardSelectionV1ReadValue ReconcileCommit(
        CardSelectionV1SurfaceCapture capture,
        bool? knownEffectComplete = null)
    {
        if (!_awaitingCommit || _selected.Length < _context.MinSelect ||
            _selected.Length > _context.MaxSelect)
        {
            LatchUnsupported();
            return Unsupported();
        }
        if ((_taskSucceededSeen && capture.TaskState != CardSelectionV1TaskState.Succeeded) ||
            (_selectorClosedSeen && !capture.SelectorClosed) ||
            (_effectWitnessSeen && !capture.EffectCompletionObserved))
        {
            LatchUnsupported();
            return Unsupported();
        }
        if (!ValidateDeckPrefix(capture, _selected, out bool effectComplete))
        {
            LatchUnsupported();
            return Unsupported();
        }
        if (knownEffectComplete.HasValue && knownEffectComplete.Value != effectComplete)
        {
            LatchUnsupported();
            return Unsupported();
        }
        if (capture.SelectorClosed) _selectorClosedSeen = true;
        if (capture.EffectCompletionObserved) _effectWitnessSeen = true;
        if (capture.TaskState == CardSelectionV1TaskState.Incomplete)
        {
            if (capture.SelectorClosed)
            {
                LatchUnsupported();
                return Unsupported();
            }
            return Waiting("submitted");
        }
        if (capture.TaskState != CardSelectionV1TaskState.Succeeded ||
            !ExactTaskResult(capture, _selected))
        {
            LatchUnsupported();
            return Unsupported();
        }
        _taskSucceededSeen = true;
        if (!capture.SelectorClosed || capture.SelectorTop || capture.PreviewOpen ||
            !effectComplete || !capture.EffectCompletionObserved)
            return Waiting("submitted");

        var selectedCards = PublicSelected(_selected);
        _resolved = new CardSelectionV1ResolvedResult(
            _context.SessionNonce, OperationName(_context.Operation),
            selectedCards, _history);
        _pending = null;
        _awaitingCommit = false;
        _published = null;
        return _resolved;
    }

    private ICardSelectionV1ReadValue PublishCaptured(
        CardSelectionV1SurfaceCapture capture)
    {
        if (!TryProject(capture, initial: false, out PublishedDecision? decision) ||
            decision is null)
        {
            LatchUnsupported();
            return Unsupported();
        }
        _published = decision;
        return decision.Observation;
    }

    private bool TryProject(
        CardSelectionV1SurfaceCapture capture,
        bool initial,
        out PublishedDecision? decision)
    {
        decision = null;
        if (capture.Status != CardSelectionV1SurfaceStatus.Available ||
            !ValidatePolicyAndContext(capture) ||
            !ValidateCollections(capture) || !ValidateStateShape(capture) ||
            !AllSelectionSettled(capture.Candidates) ||
            capture.Phase == CardSelectionV1Phase.Submitted ||
            capture.TaskState != CardSelectionV1TaskState.Incomplete ||
            capture.TaskResultOriginals.Count != 0)
            return false;

        if (initial)
        {
            if (capture.Phase != CardSelectionV1Phase.Selecting ||
                !capture.SelectorTop || capture.SelectorClosed || capture.PreviewOpen ||
                capture.PreviewIdentity is not null || capture.PreviewOriginals.Count != 0 ||
                capture.EffectCompletionObserved || SelectedFromCapture(capture).Length != 0 ||
                !AllSelectionSettled(capture.Candidates))
                return false;
            _bound = BoundSurface.Create(capture);
            _selected = Array.Empty<object>();
        }
        else
        {
            if (_bound is null || !ValidateBound(capture)) return false;
            if (capture.Phase == CardSelectionV1Phase.Transient) return false;
            object[] currentSelected = capture.Phase == CardSelectionV1Phase.Preview &&
                ValidPreview(capture, _selected)
                ? (object[])_selected.Clone()
                : SelectedFromCapture(capture);
            if (!SameSet(currentSelected, _selected)) return false;
            if (!DeckEqualsBaseline(capture.Deck)) return false;
            if (capture.Phase == CardSelectionV1Phase.Selecting)
            {
                if (!capture.SelectorTop || capture.SelectorClosed || capture.PreviewOpen)
                    return false;
            }
            else if (capture.Phase == CardSelectionV1Phase.Preview)
            {
                if (_context.CommitMode != CardSelectionV1CommitMode.PreviewConfirm ||
                    !ValidPreview(capture, _selected))
                    return false;
            }
            else return false;
        }

        var actions = BuildActions(capture, _selected);
        if (actions.Count == 0) return false;
        string phase = PhaseName(capture.Phase);
        string decisionId = CardSelectionV1Identity.DecisionId(
            _context, capture, _selected, actions.Keys, _history);
        var candidates = PublicCandidates(capture);
        var selectedSlots = SelectedSlots(capture, _selected);
        var observation = new CardSelectionV1Observation(
            _context.SessionNonce, "ready", phase,
            OperationName(_context.Operation), CommitModeName(_context.CommitMode),
            _context.MinSelect, _context.MaxSelect, decisionId,
            candidates, selectedSlots, new List<string>(actions.Keys), _history);
        decision = new PublishedDecision(observation, actions, capture);
        return true;
    }

    private Dictionary<string, ActionProbe> BuildActions(
        CardSelectionV1SurfaceCapture capture,
        object[] selected)
    {
        var actions = new Dictionary<string, ActionProbe>(StringComparer.Ordinal);
        if (capture.Phase == CardSelectionV1Phase.Selecting &&
            selected.Length < _context.MaxSelect)
        {
            foreach (CardSelectionV1NativeCandidate candidate in capture.Candidates)
            {
                if (candidate.Visible && candidate.Enabled && !candidate.Selected &&
                    candidate.SelectionSettled)
                {
                    string action = "select:" + candidate.Slot.ToString(CultureInfo.InvariantCulture);
                    actions.Add(action, new ActionProbe(
                        ActionKind.Select, candidate.Slot, candidate.SelectDispatch,
                        candidate.HolderIdentity));
                }
            }
        }

        bool cardinalityMet = selected.Length >= _context.MinSelect &&
            selected.Length <= _context.MaxSelect;
        if (capture.Phase == CardSelectionV1Phase.Selecting && cardinalityMet)
        {
            if (_context.CommitMode == CardSelectionV1CommitMode.ExplicitConfirm &&
                ValidControl(capture.ConfirmControl))
                actions.Add("confirm", ActionProbe.ForControl(
                    ActionKind.Confirm, capture.ConfirmControl!));
            else if (_context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
                     ValidControl(capture.PreviewControl))
                actions.Add("preview", ActionProbe.ForControl(
                    ActionKind.Preview, capture.PreviewControl!));
        }
        else if (capture.Phase == CardSelectionV1Phase.Preview && cardinalityMet &&
                 _context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
                 ValidControl(capture.ConfirmControl))
        {
            actions.Add("confirm", ActionProbe.ForControl(
                ActionKind.Confirm, capture.ConfirmControl!));
        }
        return actions;
    }

    private object[]? BuildExpectedSelection(ActionProbe probe)
    {
        if (probe.Kind != ActionKind.Select) return (object[])_selected.Clone();
        if (_bound is null || _selected.Length >= _context.MaxSelect) return null;
        CardSelectionV1NativeCandidate? candidate = null;
        foreach (CardSelectionV1NativeCandidate item in _bound.Candidates)
            if (item.Slot == probe.Slot) { candidate = item; break; }
        if (candidate is null || ContainsReference(_selected, candidate.ModelIdentity)) return null;
        var result = new object[_selected.Length + 1];
        Array.Copy(_selected, result, _selected.Length);
        result[^1] = candidate.ModelIdentity;
        return result;
    }

    private bool ValidatePolicyAndContext(CardSelectionV1SurfaceCapture capture)
    {
        return _bound is null
            ? SameContext(capture) && ValidPolicy(capture) &&
              capture.ScreenIdentity is not null && capture.CompletionTaskIdentity is not null
            : ValidateBound(capture);
    }

    private bool ValidateBound(CardSelectionV1SurfaceCapture capture)
    {
        if (_bound is null || !SameContext(capture) || !ValidPolicy(capture) ||
            !ReferenceEquals(capture.ScreenIdentity, _bound.ScreenIdentity) ||
            !ReferenceEquals(capture.CompletionTaskIdentity, _bound.CompletionTaskIdentity) ||
            capture.Candidates.Count != _bound.Candidates.Length)
            return false;

        for (int index = 0; index < _bound.Candidates.Length; index++)
        {
            CardSelectionV1NativeCandidate before = _bound.Candidates[index];
            CardSelectionV1NativeCandidate now = capture.Candidates[index];
            if (before.Slot != now.Slot ||
                !string.Equals(before.StableKey, now.StableKey, StringComparison.Ordinal) ||
                before.UpgradeLevel != now.UpgradeLevel ||
                !ReferenceEquals(before.HolderIdentity, now.HolderIdentity) ||
                !ReferenceEquals(before.ModelIdentity, now.ModelIdentity) ||
                !ReferenceEquals(before.CardNodeIdentity, now.CardNodeIdentity) ||
                !ReferenceEquals(before.SelectDispatch, now.SelectDispatch))
                return false;
        }
        return true;
    }

    private bool SameContext(CardSelectionV1SurfaceCapture capture)
    {
        return ReferenceEquals(capture.ParentReceiptIdentity, _context.ParentReceiptIdentity) &&
            ReferenceEquals(capture.RunIdentity, _context.RunIdentity) &&
            ReferenceEquals(capture.PlayerIdentity, _context.PlayerIdentity) &&
            ReferenceEquals(capture.RoomIdentity, _context.RoomIdentity) &&
            ReferenceEquals(capture.MapIdentity, _context.MapIdentity) &&
            ReferenceEquals(capture.ParentOptionIdentity, _context.ParentOptionIdentity) &&
            ReferenceEquals(capture.ParentControllerIdentity, _context.ParentControllerIdentity) &&
            capture.ParentKind == _context.ParentKind &&
            capture.Operation == _context.Operation &&
            capture.MinSelect == _context.MinSelect &&
            capture.MaxSelect == _context.MaxSelect &&
            capture.CommitMode == _context.CommitMode;
    }

    private bool ValidPolicy(CardSelectionV1SurfaceCapture capture)
    {
        if (!Enum.IsDefined(capture.ParentKind) || !Enum.IsDefined(capture.Operation) ||
            !Enum.IsDefined(capture.CommitMode) || !Enum.IsDefined(capture.Phase) ||
            capture.MinSelect is < 1 or > CardSelectionV1Limits.MaximumSelectedCards ||
            capture.MaxSelect is < 1 or > CardSelectionV1Limits.MaximumSelectedCards ||
            capture.MinSelect > capture.MaxSelect ||
            !capture.CompleteDomain ||
            capture.CompleteDomainCount != capture.Candidates.Count ||
            (_context.ExpectedDomainCount > 0 &&
             capture.CompleteDomainCount != _context.ExpectedDomainCount))
            return false;
        if (_context.ParentKind == CardSelectionV1ParentKind.Rest)
            return _context.Operation == CardSelectionV1Operation.Upgrade &&
                _context.MinSelect == 1 && _context.MaxSelect == 1 &&
                _context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm;
        return true;
    }

    private bool ValidateCollections(CardSelectionV1SurfaceCapture capture)
    {
        if (!capture.CompleteDeck ||
            capture.Candidates.Count is < 1 or > CardSelectionV1Limits.MaximumCandidates ||
            capture.Deck.Count > CardSelectionV1Limits.MaximumDeckCards ||
            capture.TaskResultOriginals.Count > CardSelectionV1Limits.MaximumSelectedCards ||
            capture.PreviewOriginals.Count > CardSelectionV1Limits.MaximumSelectedCards ||
            capture.Replacements.Count > CardSelectionV1Limits.MaximumSelectedCards)
            return false;

        var slots = new HashSet<int>();
        var models = new HashSet<object>(ReferenceComparer.Instance);
        var holders = new HashSet<object>(ReferenceComparer.Instance);
        var nodes = new HashSet<object>(ReferenceComparer.Instance);
        foreach (CardSelectionV1NativeCandidate candidate in capture.Candidates)
        {
            if (candidate is null || candidate.Slot is < 0 or >= CardSelectionV1Limits.MaximumCandidates ||
                !slots.Add(candidate.Slot) || !CardSelectionV1Identity.IsStableKey(candidate.StableKey) ||
                candidate.HolderIdentity is null || candidate.ModelIdentity is null ||
                candidate.CardNodeIdentity is null || candidate.SelectDispatch is null ||
                candidate.UpgradeLevel < 0 || !candidate.Visible ||
                !models.Add(candidate.ModelIdentity) || !holders.Add(candidate.HolderIdentity) ||
                !nodes.Add(candidate.CardNodeIdentity))
                return false;
        }

        var deckModels = new HashSet<object>(ReferenceComparer.Instance);
        foreach (CardSelectionV1DeckCard card in capture.Deck)
        {
            if (card is null || card.ModelIdentity is null ||
                !CardSelectionV1Identity.IsStableKey(card.StableKey) || card.UpgradeLevel < 0 ||
                !deckModels.Add(card.ModelIdentity)) return false;
        }
        foreach (CardSelectionV1NativeCandidate candidate in capture.Candidates)
        {
            bool inDeck = deckModels.Contains(candidate.ModelIdentity);
            if (_bound is null &&
                ((_context.Operation == CardSelectionV1Operation.Add && inDeck) ||
                 (_context.Operation != CardSelectionV1Operation.Add && !inDeck)))
                return false;
        }
        return true;
    }

    private bool ValidateDeckPrefix(
        CardSelectionV1SurfaceCapture capture,
        object[] selected,
        out bool complete)
    {
        complete = false;
        if (_bound is null || !ValidateCollections(capture) ||
            !SameSetSubset(selected, _bound.CandidateModels)) return false;
        bool valid = _context.Operation switch
        {
            CardSelectionV1Operation.Add => ValidateAdd(capture.Deck, selected, out complete),
            CardSelectionV1Operation.Remove => ValidateRemove(capture.Deck, selected, out complete),
            CardSelectionV1Operation.Upgrade => ValidateUpgrade(capture.Deck, selected, out complete),
            CardSelectionV1Operation.Transform => ValidateTransform(capture, selected, out complete),
            _ => false,
        };
        if (!valid) return false;
        object[] progress = EffectProgress(capture, selected);
        if (!SameSetSubset(_effectProgress, progress)) return false;
        _effectProgress = progress;
        return true;
    }

    private object[] EffectProgress(
        CardSelectionV1SurfaceCapture capture,
        object[] selected)
    {
        if (_bound is null) return Array.Empty<object>();
        var result = new List<object>();
        foreach (object model in selected)
        {
            CardSelectionV1DeckCard? before = FindDeckCard(_bound.BaselineDeck, model);
            CardSelectionV1DeckCard? now = FindDeckCard(capture.Deck, model);
            bool progressed = _context.Operation switch
            {
                CardSelectionV1Operation.Add => now is not null,
                CardSelectionV1Operation.Remove => now is null,
                CardSelectionV1Operation.Upgrade => before is not null && now is not null &&
                    (long)now.UpgradeLevel - before.UpgradeLevel == 1L,
                CardSelectionV1Operation.Transform => now is null &&
                    FindReplacement(capture.Replacements, model) is CardSelectionV1Replacement replacement &&
                    FindDeckCard(capture.Deck, replacement.ReplacementModelIdentity) is not null,
                _ => false,
            };
            if (progressed) result.Add(model);
        }
        return result.ToArray();
    }

    private static CardSelectionV1DeckCard? FindDeckCard(
        IReadOnlyList<CardSelectionV1DeckCard> deck,
        object model)
    {
        foreach (CardSelectionV1DeckCard card in deck)
            if (ReferenceEquals(card.ModelIdentity, model)) return card;
        return null;
    }

    private bool ValidateAdd(
        IReadOnlyList<CardSelectionV1DeckCard> current,
        object[] selected,
        out bool complete)
    {
        complete = false;
        if (_bound is null || current.Count < _bound.BaselineDeck.Length ||
            current.Count > _bound.BaselineDeck.Length + selected.Length) return false;
        int beforeIndex = 0;
        var seenAdded = new HashSet<object>(ReferenceComparer.Instance);
        foreach (CardSelectionV1DeckCard card in current)
        {
            if (beforeIndex < _bound.BaselineDeck.Length &&
                SameDeckCard(card, _bound.BaselineDeck[beforeIndex]))
            {
                beforeIndex++;
                continue;
            }
            if (!ContainsReference(selected, card.ModelIdentity) ||
                !seenAdded.Add(card.ModelIdentity) || !MatchesCandidate(card)) return false;
        }
        if (beforeIndex != _bound.BaselineDeck.Length) return false;
        complete = seenAdded.Count == selected.Length;
        return true;
    }

    private bool ValidateRemove(
        IReadOnlyList<CardSelectionV1DeckCard> current,
        object[] selected,
        out bool complete)
    {
        complete = false;
        if (_bound is null || current.Count > _bound.BaselineDeck.Length ||
            current.Count < _bound.BaselineDeck.Length - selected.Length) return false;
        int currentIndex = 0;
        int removed = 0;
        foreach (CardSelectionV1DeckCard before in _bound.BaselineDeck)
        {
            if (currentIndex < current.Count && SameDeckCard(current[currentIndex], before))
                currentIndex++;
            else if (ContainsReference(selected, before.ModelIdentity)) removed++;
            else return false;
        }
        if (currentIndex != current.Count) return false;
        complete = removed == selected.Length;
        return true;
    }

    private bool ValidateUpgrade(
        IReadOnlyList<CardSelectionV1DeckCard> current,
        object[] selected,
        out bool complete)
    {
        complete = false;
        if (_bound is null || current.Count != _bound.BaselineDeck.Length) return false;
        int upgraded = 0;
        for (int index = 0; index < current.Count; index++)
        {
            CardSelectionV1DeckCard before = _bound.BaselineDeck[index];
            CardSelectionV1DeckCard now = current[index];
            if (!ReferenceEquals(before.ModelIdentity, now.ModelIdentity) ||
                !string.Equals(before.StableKey, now.StableKey, StringComparison.Ordinal)) return false;
            long delta = (long)now.UpgradeLevel - before.UpgradeLevel;
            if (ContainsReference(selected, before.ModelIdentity))
            {
                if (delta is < 0 or > 1) return false;
                if (delta == 1) upgraded++;
            }
            else if (delta != 0) return false;
        }
        complete = upgraded == selected.Length;
        return true;
    }

    private bool ValidateTransform(
        CardSelectionV1SurfaceCapture capture,
        object[] selected,
        out bool complete)
    {
        complete = false;
        if (_bound is null || capture.Deck.Count != _bound.BaselineDeck.Length ||
            !ValidateReplacementBindings(capture.Replacements, selected)) return false;
        int replaced = 0;
        for (int index = 0; index < capture.Deck.Count; index++)
        {
            CardSelectionV1DeckCard before = _bound.BaselineDeck[index];
            CardSelectionV1DeckCard now = capture.Deck[index];
            if (!ContainsReference(selected, before.ModelIdentity))
            {
                if (!SameDeckCard(now, before)) return false;
                continue;
            }
            if (SameDeckCard(now, before)) continue;
            CardSelectionV1Replacement? witness = FindReplacement(
                capture.Replacements, before.ModelIdentity);
            if (witness is null ||
                !ReferenceEquals(now.ModelIdentity, witness.ReplacementModelIdentity) ||
                !string.Equals(now.StableKey, witness.ReplacementStableKey,
                    StringComparison.Ordinal) ||
                now.UpgradeLevel != witness.ReplacementUpgradeLevel)
                return false;
            replaced++;
        }
        complete = replaced == selected.Length;
        return true;
    }

    private static bool ValidateReplacementBindings(
        IReadOnlyList<CardSelectionV1Replacement> replacements,
        object[] selected)
    {
        var originals = new HashSet<object>(ReferenceComparer.Instance);
        var replacementsSeen = new HashSet<object>(ReferenceComparer.Instance);
        foreach (CardSelectionV1Replacement item in replacements)
        {
            if (item is null || item.OriginalModelIdentity is null ||
                item.ReplacementModelIdentity is null ||
                ReferenceEquals(item.OriginalModelIdentity, item.ReplacementModelIdentity) ||
                !ContainsReference(selected, item.OriginalModelIdentity) ||
                !originals.Add(item.OriginalModelIdentity) ||
                !replacementsSeen.Add(item.ReplacementModelIdentity) ||
                !CardSelectionV1Identity.IsStableKey(item.ReplacementStableKey) ||
                item.ReplacementUpgradeLevel < 0) return false;
        }
        return true;
    }

    private bool ExactSelected(CardSelectionV1SurfaceCapture capture, object[] expected)
    {
        if (capture.Phase == CardSelectionV1Phase.Transient) return false;
        object[] actual = SelectedFromCapture(capture);
        return SameSet(actual, expected);
    }

    private static object[] SelectedFromCapture(CardSelectionV1SurfaceCapture capture)
    {
        var selected = new List<object>();
        foreach (CardSelectionV1NativeCandidate candidate in capture.Candidates)
            if (candidate.Selected)
            {
                if (!candidate.SelectionSettled) return Array.Empty<object>();
                selected.Add(candidate.ModelIdentity);
            }
        return selected.ToArray();
    }

    private static bool ExactTaskResult(
        CardSelectionV1SurfaceCapture capture,
        object[] expected)
    {
        if (capture.TaskResultOriginals.Count != expected.Length) return false;
        var seen = new HashSet<object>(ReferenceComparer.Instance);
        foreach (object item in capture.TaskResultOriginals)
            if (item is null || !seen.Add(item)) return false;
        return SameSet(seen, expected);
    }

    private static bool ValidPreview(
        CardSelectionV1SurfaceCapture capture,
        object[] selected)
    {
        if (capture.Phase != CardSelectionV1Phase.Preview || !capture.PreviewOpen ||
            capture.SelectorClosed || capture.PreviewIdentity is null ||
            capture.PreviewOriginals.Count != selected.Length) return false;
        var seen = new HashSet<object>(ReferenceComparer.Instance);
        foreach (object item in capture.PreviewOriginals)
            if (item is null || !seen.Add(item)) return false;
        return SameSet(seen, selected);
    }

    private bool DeckEqualsBaseline(IReadOnlyList<CardSelectionV1DeckCard> deck) =>
        _bound is not null && DeckEquals(deck, _bound.BaselineDeck);

    private static bool DeckEquals(
        IReadOnlyList<CardSelectionV1DeckCard> deck,
        IReadOnlyList<CardSelectionV1DeckCard>? baseline)
    {
        if (baseline is null || deck.Count != baseline.Count) return false;
        for (int index = 0; index < deck.Count; index++)
            if (!SameDeckCard(deck[index], baseline[index])) return false;
        return true;
    }

    private static bool SameDeckCard(CardSelectionV1DeckCard left, CardSelectionV1DeckCard right) =>
        ReferenceEquals(left.ModelIdentity, right.ModelIdentity) &&
        string.Equals(left.StableKey, right.StableKey, StringComparison.Ordinal) &&
        left.UpgradeLevel == right.UpgradeLevel;

    private bool MatchesCandidate(CardSelectionV1DeckCard card)
    {
        if (_bound is null) return false;
        foreach (CardSelectionV1NativeCandidate candidate in _bound.Candidates)
            if (ReferenceEquals(card.ModelIdentity, candidate.ModelIdentity))
                return string.Equals(card.StableKey, candidate.StableKey,
                    StringComparison.Ordinal) && card.UpgradeLevel == candidate.UpgradeLevel;
        return false;
    }

    private static CardSelectionV1Replacement? FindReplacement(
        IReadOnlyList<CardSelectionV1Replacement> replacements,
        object original)
    {
        foreach (CardSelectionV1Replacement item in replacements)
            if (ReferenceEquals(item.OriginalModelIdentity, original)) return item;
        return null;
    }

    private static bool SameSet(IEnumerable<object> left, IEnumerable<object> right)
    {
        var set = new HashSet<object>(left, ReferenceComparer.Instance);
        var other = new HashSet<object>(right, ReferenceComparer.Instance);
        return set.Count == other.Count && set.SetEquals(other);
    }

    private static bool SameSetSubset(object[] selected, object[] domain)
    {
        var set = new HashSet<object>(selected, ReferenceComparer.Instance);
        return set.Count == selected.Length && set.IsSubsetOf(domain);
    }

    private static bool ContainsReference(IEnumerable<object> values, object value)
    {
        foreach (object item in values)
            if (ReferenceEquals(item, value)) return true;
        return false;
    }

    private IReadOnlyList<CardSelectionV1Candidate> PublicCandidates(
        CardSelectionV1SurfaceCapture capture)
    {
        var result = new CardSelectionV1Candidate[capture.Candidates.Count];
        for (int index = 0; index < capture.Candidates.Count; index++)
        {
            CardSelectionV1NativeCandidate item = capture.Candidates[index];
            bool selected = capture.Phase == CardSelectionV1Phase.Preview
                ? ContainsReference(_selected, item.ModelIdentity)
                : item.Selected;
            result[index] = new CardSelectionV1Candidate(
                item.Slot, item.StableKey, item.UpgradeLevel, item.Visible, item.Enabled, selected);
        }
        return result;
    }

    private IReadOnlyList<CardSelectionV1Candidate> PublicSelected(object[] selected)
    {
        if (_bound is null) return Array.Empty<CardSelectionV1Candidate>();
        var result = new List<CardSelectionV1Candidate>();
        foreach (CardSelectionV1NativeCandidate item in _bound.Candidates)
            if (ContainsReference(selected, item.ModelIdentity))
                result.Add(new CardSelectionV1Candidate(
                    item.Slot, item.StableKey, item.UpgradeLevel, item.Visible, item.Enabled, true));
        return result;
    }

    private static IReadOnlyList<int> SelectedSlots(
        CardSelectionV1SurfaceCapture capture,
        object[] selected)
    {
        var result = new List<int>();
        foreach (CardSelectionV1NativeCandidate item in capture.Candidates)
            if (ContainsReference(selected, item.ModelIdentity)) result.Add(item.Slot);
        return result;
    }

    private void AddHistory(PendingAction pending, string result)
    {
        _history.Add(new CardSelectionV1ActionResult(
            pending.DecisionId, pending.ActionId, result));
    }

    private CardSelectionV1Observation Waiting(string phase) =>
        CardSelectionV1Observation.Fixed(
            _context.SessionNonce, "waiting", phase, _history);

    private CardSelectionV1Observation Unsupported() =>
        CardSelectionV1Observation.Fixed(
            _context.SessionNonce, "unsupported", "unsupported", _history);

    private CardSelectionV1ApplyFailure Failure(string outcome) =>
        new(_context.SessionNonce, outcome);

    private void LatchUnsupported()
    {
        _unsupported = true;
        _published = null;
        _pending = null;
        _awaitingCommit = false;
        _resolved = null;
    }

    private static bool ValidControl(CardSelectionV1NativeControl? control) =>
        control is not null && control.Identity is not null &&
        control.Dispatch is not null && control.Visible && control.Enabled;

    private static bool SameProbe(ActionProbe left, ActionProbe right) =>
        left.Kind == right.Kind && left.Slot == right.Slot &&
        ReferenceEquals(left.Identity, right.Identity) &&
        ReferenceEquals(left.Dispatch, right.Dispatch);

    private static bool SamePublished(PublishedDecision left, PublishedDecision right)
    {
        CardSelectionV1Observation a = left.Observation;
        CardSelectionV1Observation b = right.Observation;
        if (!string.Equals(a.DecisionId, b.DecisionId, StringComparison.Ordinal) ||
            a.Candidates.Count != b.Candidates.Count ||
            a.SelectedSlots.Count != b.SelectedSlots.Count ||
            a.LegalActions.Count != b.LegalActions.Count) return false;
        for (int index = 0; index < a.Candidates.Count; index++)
        {
            CardSelectionV1Candidate x = a.Candidates[index];
            CardSelectionV1Candidate y = b.Candidates[index];
            if (x.Slot != y.Slot || x.UpgradeLevel != y.UpgradeLevel ||
                x.Selected != y.Selected || !string.Equals(x.Key, y.Key, StringComparison.Ordinal))
                return false;
        }
        for (int index = 0; index < a.SelectedSlots.Count; index++)
            if (a.SelectedSlots[index] != b.SelectedSlots[index]) return false;
        for (int index = 0; index < a.LegalActions.Count; index++)
            if (!string.Equals(a.LegalActions[index], b.LegalActions[index],
                StringComparison.Ordinal)) return false;
        foreach (KeyValuePair<string, ActionProbe> pair in left.Actions)
            if (!right.Actions.TryGetValue(pair.Key, out ActionProbe? other) ||
                !SameProbe(pair.Value, other)) return false;
        return SameProjectedCapture(left.Capture, right.Capture);
    }


    private bool ValidateStateShape(CardSelectionV1SurfaceCapture capture)
    {
        if (!Enum.IsDefined(capture.Status) || !Enum.IsDefined(capture.TaskState) ||
            capture.SelectorTop && capture.SelectorClosed) return false;
        if (capture.TaskState == CardSelectionV1TaskState.Incomplete &&
            capture.TaskResultOriginals.Count != 0) return false;
        if (capture.TaskState is CardSelectionV1TaskState.Canceled or CardSelectionV1TaskState.Faulted &&
            capture.TaskResultOriginals.Count != 0) return false;
        if (capture.TaskState == CardSelectionV1TaskState.Succeeded &&
            capture.TaskResultOriginals.Count is < 1 or > CardSelectionV1Limits.MaximumSelectedCards)
            return false;
        if (_context.Operation != CardSelectionV1Operation.Transform &&
            capture.Replacements.Count != 0) return false;
        if (capture.Phase == CardSelectionV1Phase.Selecting)
            return capture.SelectorTop && !capture.SelectorClosed && !capture.PreviewOpen &&
                capture.PreviewIdentity is null && capture.PreviewOriginals.Count == 0 &&
                !capture.EffectCompletionObserved;
        if (capture.Phase == CardSelectionV1Phase.Preview)
            return !capture.SelectorClosed && capture.PreviewOpen &&
                capture.PreviewIdentity is not null && !capture.EffectCompletionObserved;
        if (capture.Phase == CardSelectionV1Phase.Submitted)
            return !capture.SelectorTop && !capture.PreviewOpen &&
                capture.PreviewIdentity is null && capture.PreviewOriginals.Count == 0;
        return capture.Phase == CardSelectionV1Phase.Transient;
    }

    private static bool AllSelectionSettled(
        IReadOnlyList<CardSelectionV1NativeCandidate> candidates)
    {
        foreach (CardSelectionV1NativeCandidate candidate in candidates)
            if (!candidate.SelectionSettled) return false;
        return true;
    }

    private static bool SameProjectedCapture(
        CardSelectionV1SurfaceCapture left,
        CardSelectionV1SurfaceCapture right)
    {
        if (left.Phase != right.Phase || left.SelectorTop != right.SelectorTop ||
            left.SelectorClosed != right.SelectorClosed || left.PreviewOpen != right.PreviewOpen ||
            left.CompleteDomain != right.CompleteDomain ||
            left.CompleteDomainCount != right.CompleteDomainCount ||
            left.CompleteDeck != right.CompleteDeck ||
            left.TaskState != right.TaskState ||
            left.EffectCompletionObserved != right.EffectCompletionObserved ||
            !ReferenceEquals(left.PreviewIdentity, right.PreviewIdentity) ||
            !SameControl(left.PreviewControl, right.PreviewControl) ||
            !SameControl(left.ConfirmControl, right.ConfirmControl) ||
            left.Candidates.Count != right.Candidates.Count ||
            left.Deck.Count != right.Deck.Count ||
            left.TaskResultOriginals.Count != right.TaskResultOriginals.Count ||
            left.PreviewOriginals.Count != right.PreviewOriginals.Count ||
            left.Replacements.Count != right.Replacements.Count) return false;
        for (int index = 0; index < left.Candidates.Count; index++)
        {
            CardSelectionV1NativeCandidate a = left.Candidates[index];
            CardSelectionV1NativeCandidate b = right.Candidates[index];
            if (a.Visible != b.Visible || a.Enabled != b.Enabled ||
                a.Selected != b.Selected || a.SelectionSettled != b.SelectionSettled) return false;
        }
        for (int index = 0; index < left.Deck.Count; index++)
            if (!SameDeckCard(left.Deck[index], right.Deck[index])) return false;
        for (int index = 0; index < left.TaskResultOriginals.Count; index++)
            if (!ReferenceEquals(left.TaskResultOriginals[index], right.TaskResultOriginals[index])) return false;
        for (int index = 0; index < left.PreviewOriginals.Count; index++)
            if (!ReferenceEquals(left.PreviewOriginals[index], right.PreviewOriginals[index])) return false;
        for (int index = 0; index < left.Replacements.Count; index++)
        {
            CardSelectionV1Replacement a = left.Replacements[index];
            CardSelectionV1Replacement b = right.Replacements[index];
            if (!ReferenceEquals(a.OriginalModelIdentity, b.OriginalModelIdentity) ||
                !ReferenceEquals(a.ReplacementModelIdentity, b.ReplacementModelIdentity) ||
                !string.Equals(a.ReplacementStableKey, b.ReplacementStableKey, StringComparison.Ordinal) ||
                a.ReplacementUpgradeLevel != b.ReplacementUpgradeLevel) return false;
        }
        return true;
    }

    private static bool SameControl(
        CardSelectionV1NativeControl? left,
        CardSelectionV1NativeControl? right)
    {
        if (left is null || right is null) return left is null && right is null;
        return ReferenceEquals(left.Identity, right.Identity) &&
            ReferenceEquals(left.Dispatch, right.Dispatch) &&
            left.Visible == right.Visible && left.Enabled == right.Enabled;
    }
    private static bool ValidContext(CardSelectionV1ParentContext context)
    {
        return CardSelectionV1Identity.IsNonce(context.SessionNonce) &&
            CardSelectionV1Identity.IsDecisionId(context.ParentDecisionId) &&
            CardSelectionV1Identity.IsParentAction(context.ParentActionId) &&
            context.ParentReceiptIdentity is not null && context.RunIdentity is not null &&
            context.PlayerIdentity is not null && context.RoomIdentity is not null &&
            context.MapIdentity is not null && context.ParentOptionIdentity is not null &&
            context.ParentControllerIdentity is not null &&
            Enum.IsDefined(context.ParentKind) && Enum.IsDefined(context.Operation) &&
            Enum.IsDefined(context.CommitMode) &&
            context.MinSelect is >= 1 and <= CardSelectionV1Limits.MaximumSelectedCards &&
            context.MaxSelect is >= 1 and <= CardSelectionV1Limits.MaximumSelectedCards &&
            context.MinSelect <= context.MaxSelect &&
            context.ExpectedDomainCount is >= 0 and <= CardSelectionV1Limits.MaximumCandidates &&
            (context.ExpectedDomainCount == 0 || context.ExpectedDomainCount >= context.MaxSelect) &&
            (context.ParentKind != CardSelectionV1ParentKind.Rest ||
             context.Operation == CardSelectionV1Operation.Upgrade &&
             context.MinSelect == 1 && context.MaxSelect == 1 &&
             context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm);
    }

    private static string PhaseName(CardSelectionV1Phase value) => value switch
    {
        CardSelectionV1Phase.Selecting => "selecting",
        CardSelectionV1Phase.Preview => "preview",
        _ => throw new InvalidOperationException("Unsupported ready phase."),
    };

    private static string OperationName(CardSelectionV1Operation value) => value switch
    {
        CardSelectionV1Operation.Add => "add",
        CardSelectionV1Operation.Remove => "remove",
        CardSelectionV1Operation.Upgrade => "upgrade",
        CardSelectionV1Operation.Transform => "transform",
        _ => throw new InvalidOperationException("Unsupported operation."),
    };

    private static string CommitModeName(CardSelectionV1CommitMode value) => value switch
    {
        CardSelectionV1CommitMode.AutoAtMax => "auto_at_max",
        CardSelectionV1CommitMode.ExplicitConfirm => "explicit_confirm",
        CardSelectionV1CommitMode.PreviewConfirm => "preview_confirm",
        _ => throw new InvalidOperationException("Unsupported commit mode."),
    };

    private sealed class BoundSurface
    {
        private BoundSurface(CardSelectionV1SurfaceCapture capture)
        {
            ScreenIdentity = capture.ScreenIdentity!;
            CompletionTaskIdentity = capture.CompletionTaskIdentity!;
            Candidates = Copy(capture.Candidates);
            BaselineDeck = Copy(capture.Deck);
            CandidateModels = new object[Candidates.Length];
            for (int index = 0; index < Candidates.Length; index++)
                CandidateModels[index] = Candidates[index].ModelIdentity;
        }

        public object ScreenIdentity { get; }
        public object CompletionTaskIdentity { get; }
        public CardSelectionV1NativeCandidate[] Candidates { get; }
        public CardSelectionV1DeckCard[] BaselineDeck { get; }
        public object[] CandidateModels { get; }

        public static BoundSurface Create(CardSelectionV1SurfaceCapture capture) => new(capture);

        private static T[] Copy<T>(IReadOnlyList<T> source)
        {
            var result = new T[source.Count];
            for (int index = 0; index < source.Count; index++) result[index] = source[index];
            return result;
        }
    }

    private sealed class PublishedDecision
    {
        public PublishedDecision(
            CardSelectionV1Observation observation,
            Dictionary<string, ActionProbe> actions,
            CardSelectionV1SurfaceCapture capture)
        {
            Observation = observation;
            Actions = actions;
            Capture = capture;
        }
        public CardSelectionV1Observation Observation { get; }
        public Dictionary<string, ActionProbe> Actions { get; }
        public CardSelectionV1SurfaceCapture Capture { get; }
    }

    private sealed class PendingAction
    {
        public PendingAction(
            ActionKind kind,
            int slot,
            string decisionId,
            string actionId,
            object[] expectedSelection,
            Action dispatch)
        {
            Kind = kind;
            Slot = slot;
            DecisionId = decisionId;
            ActionId = actionId;
            ExpectedSelection = expectedSelection;
            Dispatch = dispatch;
        }
        public ActionKind Kind { get; }
        public int Slot { get; }
        public string DecisionId { get; }
        public string ActionId { get; }
        public object[] ExpectedSelection { get; }
        public Action Dispatch { get; }
    }

    private sealed class ActionProbe
    {
        public ActionProbe(ActionKind kind, int slot, Action dispatch, object identity)
        {
            Kind = kind;
            Slot = slot;
            Dispatch = dispatch;
            Identity = identity;
        }
        public ActionKind Kind { get; }
        public int Slot { get; }
        public Action Dispatch { get; }
        public object Identity { get; }
        public static ActionProbe ForControl(ActionKind kind, CardSelectionV1NativeControl control) =>
            new(kind, -1, control.Dispatch, control.Identity);
    }

    private enum ActionKind
    {
        Select = 1,
        Preview = 2,
        Confirm = 3,
    }

    private sealed class ReferenceComparer : IEqualityComparer<object>
    {
        public static readonly ReferenceComparer Instance = new();
        public new bool Equals(object? left, object? right) => ReferenceEquals(left, right);
        public int GetHashCode(object value) =>
            System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(value);
    }
}

internal static class CardSelectionV1Identity
{
    public static bool IsNonce(string? value) => IsLowerHex(value, 32);
    public static bool IsDecisionId(string? value) => IsLowerHex(value, 64);

    public static bool IsParentAction(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > 128) return false;
        foreach (char c in value) if (c is < ' ' or > '~') return false;
        return true;
    }

    public static bool IsActionId(string? value)
    {
        if (value is "preview" or "confirm") return true;
        if (value is null || !value.StartsWith("select:", StringComparison.Ordinal)) return false;
        ReadOnlySpan<char> digits = value.AsSpan(7);
        if (digits.Length is < 1 or > 2 || (digits.Length > 1 && digits[0] == '0')) return false;
        int slot = 0;
        foreach (char c in digits)
        {
            if (c is < '0' or > '9') return false;
            slot = slot * 10 + c - '0';
        }
        return slot < CardSelectionV1Limits.MaximumCandidates;
    }

    public static bool IsStableKey(string? value)
    {
        if (value is null || value.Length is < 1 or > CardSelectionV1Limits.MaximumKeyLength)
            return false;
        foreach (char c in value)
            if (!(c is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '_'))
                return false;
        return true;
    }

    public static string DecisionId(
        CardSelectionV1ParentContext context,
        CardSelectionV1SurfaceCapture capture,
        object[] selected,
        IEnumerable<string> actions,
        IReadOnlyList<CardSelectionV1ActionResult> history)
    {
        var builder = new StringBuilder();
        Append(builder, context.SessionNonce);
        Append(builder, ((int)context.ParentKind).ToString(CultureInfo.InvariantCulture));
        Append(builder, context.ParentDecisionId);
        Append(builder, context.ParentActionId);
        Append(builder, ((int)context.Operation).ToString(CultureInfo.InvariantCulture));
        Append(builder, context.MinSelect.ToString(CultureInfo.InvariantCulture));
        Append(builder, context.MaxSelect.ToString(CultureInfo.InvariantCulture));
        Append(builder, ((int)context.CommitMode).ToString(CultureInfo.InvariantCulture));
        Append(builder, ((int)capture.Phase).ToString(CultureInfo.InvariantCulture));
        Append(builder, capture.CompleteDeck ? "1" : "0");
        foreach (CardSelectionV1NativeCandidate candidate in capture.Candidates)
        {
            Append(builder, candidate.Slot.ToString(CultureInfo.InvariantCulture));
            Append(builder, candidate.StableKey);
            Append(builder, candidate.UpgradeLevel.ToString(CultureInfo.InvariantCulture));
            Append(builder, candidate.Visible ? "1" : "0");
            Append(builder, candidate.Enabled ? "1" : "0");
            Append(builder, candidate.Selected ? "1" : "0");
            Append(builder, candidate.SelectionSettled ? "1" : "0");
        }
        foreach (CardSelectionV1DeckCard card in capture.Deck)
        {
            Append(builder, card.StableKey);
            Append(builder, card.UpgradeLevel.ToString(CultureInfo.InvariantCulture));
        }
        foreach (object item in selected)
        {
            int slot = -1;
            foreach (CardSelectionV1NativeCandidate candidate in capture.Candidates)
                if (ReferenceEquals(candidate.ModelIdentity, item)) { slot = candidate.Slot; break; }
            Append(builder, slot.ToString(CultureInfo.InvariantCulture));
        }
        foreach (string action in actions) Append(builder, action);
        foreach (CardSelectionV1ActionResult result in history)
        {
            Append(builder, result.DecisionId);
            Append(builder, result.ActionId);
            Append(builder, result.Result);
        }
        byte[] bytes = Encoding.ASCII.GetBytes(builder.ToString());
        byte[] digest = SHA256.HashData(bytes);
        CryptographicOperations.ZeroMemory(bytes);
        return Convert.ToHexString(digest).ToLowerInvariant();
    }

    private static void Append(StringBuilder builder, string value)
    {
        builder.Append(value.Length.ToString(CultureInfo.InvariantCulture));
        builder.Append(':');
        builder.Append(value);
        builder.Append('|');
    }

    private static bool IsLowerHex(string? value, int length)
    {
        if (value is null || value.Length != length) return false;
        foreach (char c in value)
            if (!(c is >= '0' and <= '9' or >= 'a' and <= 'f')) return false;
        return true;
    }
}
