using System;
using System.Collections.Generic;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Event;

public sealed class EventV1Session : IRoomFlowSession
{
    private readonly object _gate = new();
    private readonly string _sessionNonce;
    private readonly IEventV1NativeAdapter _adapter;
    private readonly IEventItemChildFactory _childFactory;
    private readonly int _ownerThreadId;
    private readonly HashSet<string> _reservedStableIds = new(StringComparer.Ordinal);
    private object? _boundRun;
    private object? _boundPlayer;
    private object? _boundRoom;
    private object? _boundMap;
    private PublishedDecision? _published;
    private RoomFlowDispatchReceipt? _acceptedReceipt;
    private string? _acceptedTransitionId;
    private EventV1ExitProbe? _exitProbe;
    private EventV1ResolvedResult? _resolved;
    private IEventItemChildBroker? _child;
    private object? _childIdentity;
    private bool _lastAcceptedWasOrdinary;
    private bool _waitingForTransition;
    private bool _waitingAfterChild;
    private bool _childCreated;
    private bool _dispatching;
    private bool _operationInProgress;
    private bool _disposeRequested;
    private bool _unsupported;
    private bool _disposed;
    private int _reservationCount;
    private int _pendingReads;

    public EventV1Session(
        string sessionNonce,
        IEventV1NativeAdapter adapter,
        IEventItemChildFactory childFactory)
    {
        if (!RoomFlowIdentity.IsNonce(sessionNonce))
            throw new ArgumentException("Session nonce is not canonical.", nameof(sessionNonce));
        _sessionNonce = sessionNonce;
        _adapter = adapter ?? throw new ArgumentNullException(nameof(adapter));
        _childFactory = childFactory ?? throw new ArgumentNullException(nameof(childFactory));
        _ownerThreadId = Environment.CurrentManagedThreadId;
    }

    public string FlowKind => EventV1Constants.FlowKind;

    public int ReservedDispatchCount
    {
        get { lock (_gate) return _reservationCount; }
    }

    public IEventItemChildBroker? ActiveItemChild
    {
        get
        {
            lock (_gate)
                return _disposed || _unsupported || _disposeRequested ? null : _child;
        }
    }

    public IRoomFlowReadValue Read()
    {
        lock (_gate)
        {
            if (!IsOwnerThread())
            {
                _unsupported = true;
                _disposed = true;
                _disposeRequested = true;
                return UnsupportedObservation();
            }
            if (_operationInProgress) return WaitingObservation();
            _operationInProgress = true;
            IRoomFlowReadValue result;
            try
            {
                result = ReadCore();
            }
            finally
            {
                _operationInProgress = false;
            }
            if (_disposeRequested)
            {
                FinishDeferredDispose();
                return UnsupportedObservation();
            }
            return result;
        }
    }

    public IRoomFlowApplyValue Apply(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (!IsOwnerThread())
            {
                _unsupported = true;
                _disposed = true;
                _disposeRequested = true;
                return Failure("unsupported");
            }
            if (_operationInProgress) return Failure("rejected");
            _operationInProgress = true;
            IRoomFlowApplyValue result;
            int reservationsBefore = _reservationCount;
            try
            {
                result = ApplyCore(decisionId, actionId);
            }
            finally
            {
                _operationInProgress = false;
            }
            if (_disposeRequested)
            {
                bool mutationReserved = _reservationCount != reservationsBefore;
                FinishDeferredDispose();
                if (!mutationReserved) return Failure("unsupported");
            }
            return result;
        }
    }

    private IRoomFlowReadValue ReadCore()
    {
        if (_disposed || _unsupported) return UnsupportedObservation();
        if (_resolved is not null) return _resolved;
        if (_dispatching) return WaitingObservation();
        if (_child is not null && !AdvanceChild()) return CurrentTerminalOrChild();
        if (_unsupported) return UnsupportedObservation();
        if (_exitProbe is not null) return ReadExit();
        return ReadSurface();
    }

    private IRoomFlowApplyValue ApplyCore(string? decisionId, string? actionId)
    {
            if (_disposed || _unsupported || _resolved is not null || _dispatching ||
                _child is not null || _published is null)
            {
                return Failure("rejected");
            }
            PublishedDecision published = _published;
            PublishedCandidate? selected = published.FindAction(actionId);
            if (!RoomFlowIdentity.IsDecisionId(decisionId) ||
                !string.Equals(decisionId, published.Observation.DecisionId,
                    StringComparison.Ordinal) || selected is null ||
                !published.ContainsLegalAction(actionId) ||
                _reservedStableIds.Contains(selected.Public.StableId))
            {
                return Failure("rejected");
            }
            if (_reservationCount >= RoomFlowLimits.MaximumParentActions)
            {
                return Failure("rejected");
            }

            EventV1SurfaceCapture current;
            PublishedDecision? recaptured;
            try
            {
                current = _adapter.CaptureSurface();
                if (_disposeRequested) return Failure("unsupported");
                if (!TryProjectParent(current, bind: false, out recaptured) ||
                    recaptured is null || !SamePublished(published, recaptured) ||
                    !string.Equals(recaptured.Observation.DecisionId, decisionId,
                        StringComparison.Ordinal))
                {
                    _published = null;
                    return Failure("unsupported");
                }
            }
            catch
            {
                LatchUnsupported();
                return Failure("unsupported");
            }

            PublishedCandidate? exact = recaptured.FindAction(actionId);
            if (exact is null || !SameBinding(selected, exact) ||
                !recaptured.ContainsLegalAction(actionId))
            {
                _published = null;
                return Failure("unsupported");
            }

            _reservedStableIds.Add(exact.Public.StableId);
            _reservationCount++;
            _published = null;
            _acceptedReceipt = null;
            _acceptedTransitionId = recaptured.TransitionId;
            _lastAcceptedWasOrdinary = !exact.Public.IsProceed;
            _waitingForTransition = !exact.Public.IsProceed;
            _waitingAfterChild = false;
            _pendingReads = 0;
            _exitProbe = exact.Public.IsProceed
                ? new EventV1ExitProbe(_boundRun!, _boundPlayer!, _boundRoom!, _boundMap!)
                : null;
            _dispatching = true;
            try
            {
                exact.Native.Dispatch();
                var receipt = new RoomFlowDispatchReceipt(
                    EventV1Constants.FlowKind, _sessionNonce, decisionId!, actionId!);
                _acceptedReceipt = receipt;
                return receipt;
            }
            catch
            {
                LatchUnsupported();
                return Failure("uncertain");
            }
            finally
            {
                _dispatching = false;
            }
    }

    public void Dispose()
    {
        IEventItemChildBroker? child;
        lock (_gate)
        {
            if (!IsOwnerThread())
            {
                _disposeRequested = true;
                _disposed = true;
                _unsupported = true;
                return;
            }
            if (_operationInProgress)
            {
                _disposeRequested = true;
                _disposed = true;
                _unsupported = true;
                return;
            }
            if (_disposeRequested)
            {
                FinishDeferredDispose();
                return;
            }
            if (_disposed) return;
            _disposed = true;
            _unsupported = true;
            child = _child;
            _child = null;
            _childIdentity = null;
            _published = null;
            _acceptedReceipt = null;
            _exitProbe = null;
            _resolved = null;
            _boundRun = null;
            _boundPlayer = null;
            _boundRoom = null;
            _boundMap = null;
            _reservedStableIds.Clear();
        }
        child?.Dispose();
    }

    private IRoomFlowReadValue ReadSurface()
    {
        EventV1SurfaceCapture? capture;
        try
        {
            capture = _adapter.CaptureSurface();
        }
        catch
        {
            LatchUnsupported();
            return UnsupportedObservation();
        }

        if (capture is null)
        {
            LatchUnsupported();
            return UnsupportedObservation();
        }

        if (capture.Status == EventV1SurfaceStatus.Missing)
            return PendingWaitOrInitialWait();
        if (capture.Status == EventV1SurfaceStatus.Unsupported)
        {
            LatchUnsupported();
            return UnsupportedObservation();
        }
        if (capture.Status == EventV1SurfaceStatus.ItemChild)
            return ReadOrStartChild(capture);

        PublishedDecision? projected;
        try
        {
            if (!TryProjectParent(capture, bind: true, out projected) || projected is null)
            {
                LatchUnsupported();
                return UnsupportedObservation();
            }
        }
        catch
        {
            LatchUnsupported();
            return UnsupportedObservation();
        }

        if (_waitingForTransition || _waitingAfterChild)
        {
            if (string.Equals(projected.TransitionId, _acceptedTransitionId,
                    StringComparison.Ordinal) || projected.Observation.Status != "ready")
            {
                return PendingWaitOrInitialWait();
            }
            _waitingForTransition = false;
            _waitingAfterChild = false;
            _pendingReads = 0;
            _lastAcceptedWasOrdinary = false;
            _acceptedReceipt = null;
        }
        if (projected.Observation.Status != "ready")
        {
            _published = null;
            return WaitingObservation();
        }
        _published = projected;
        return projected.Observation;
    }

    private IRoomFlowReadValue ReadOrStartChild(EventV1SurfaceCapture capture)
    {
        if (!MatchesBound(capture) || !_lastAcceptedWasOrdinary ||
            _acceptedReceipt is null || capture.ItemChildIdentity is null ||
            capture.ItemChildAdapter is null)
        {
            LatchUnsupported();
            return UnsupportedObservation();
        }
        if (_childCreated)
        {
            if (_waitingAfterChild && ReferenceEquals(_childIdentity, capture.ItemChildIdentity))
                return PendingWaitOrInitialWait();
            LatchUnsupported();
            return UnsupportedObservation();
        }
        IEventItemChildBroker? broker = null;
        try
        {
            broker = _childFactory.Create(_acceptedReceipt, capture.ItemChildAdapter);
            if (_disposeRequested)
                throw new InvalidOperationException("Event disposal requested during child creation.");
            if (broker is null || !ReferenceEquals(broker.ParentReceipt, _acceptedReceipt))
                throw new InvalidOperationException("Child broker receipt mismatch.");
            EventItemChildStatus status = broker.Status;
            if (status is not EventItemChildActive ||
                !ReferenceEquals(status.ParentReceipt, _acceptedReceipt))
                throw new InvalidOperationException("Child broker did not start active.");
        }
        catch
        {
            bool cleanupFailed = false;
            try { broker?.Dispose(); }
            catch { cleanupFailed = true; }
            LatchUnsupported();
            if (_disposeRequested && cleanupFailed)
                throw new InvalidOperationException("Event child cleanup failed.");
            return UnsupportedObservation();
        }
        _child = broker;
        _childIdentity = capture.ItemChildIdentity;
        _childCreated = true;
        _published = null;
        _waitingForTransition = false;
        _pendingReads = 0;
        return ItemChildObservation();
    }

    private bool AdvanceChild()
    {
        IEventItemChildBroker broker = _child!;
        EventItemChildStatus status;
        try
        {
            if (!ReferenceEquals(broker.ParentReceipt, _acceptedReceipt))
                throw new InvalidOperationException("Child broker receipt changed.");
            status = broker.Status;
            if (!ReferenceEquals(status.ParentReceipt, _acceptedReceipt))
                throw new InvalidOperationException("Child status receipt changed.");
        }
        catch
        {
            DisposeChild(latchUnsupported: true);
            return false;
        }
        if (status is EventItemChildActive) return false;
        if (status is EventItemChildFailed)
        {
            DisposeChild(latchUnsupported: true);
            return false;
        }
        if (status is not EventItemChildResolved)
        {
            DisposeChild(latchUnsupported: true);
            return false;
        }
        DisposeChild(latchUnsupported: false);
        _waitingAfterChild = true;
        _waitingForTransition = false;
        _pendingReads = 0;
        return true;
    }

    private IRoomFlowReadValue CurrentTerminalOrChild() =>
        _unsupported ? UnsupportedObservation() : ItemChildObservation();

    private IRoomFlowReadValue ReadExit()
    {
        EventV1ExitCapture? capture;
        try
        {
            capture = _adapter.CaptureExit(_exitProbe!);
        }
        catch
        {
            LatchUnsupported();
            return UnsupportedObservation();
        }
        if (capture is null)
        {
            LatchUnsupported();
            return UnsupportedObservation();
        }
        if (!ReferenceEquals(capture.RunIdentity, _boundRun) ||
            !ReferenceEquals(capture.PlayerIdentity, _boundPlayer) ||
            !ReferenceEquals(capture.RoomIdentity, _boundRoom) ||
            !ReferenceEquals(capture.MapIdentity, _boundMap))
        {
            LatchUnsupported();
            return UnsupportedObservation();
        }
        if (capture.MapOpen && capture.TravelEnabled && !capture.Traveling)
        {
            RoomFlowDispatchReceipt? receipt = _acceptedReceipt;
            if (receipt is null)
            {
                LatchUnsupported();
                return UnsupportedObservation();
            }
            _resolved = new EventV1ResolvedResult(
                _sessionNonce, receipt.DecisionId, receipt.ActionId);
            _exitProbe = null;
            _pendingReads = 0;
            return _resolved;
        }
        if (!capture.MapOpen && !capture.TravelEnabled && !capture.Traveling)
            return PendingWaitOrInitialWait();
        LatchUnsupported();
        return UnsupportedObservation();
    }

    private IRoomFlowReadValue PendingWaitOrInitialWait()
    {
        if (_waitingForTransition || _waitingAfterChild || _exitProbe is not null)
        {
            _pendingReads++;
            if (_pendingReads >= RoomFlowLimits.MaximumPendingReads)
            {
                LatchUnsupported();
                return UnsupportedObservation();
            }
        }
        _published = null;
        return WaitingObservation();
    }

    private bool TryProjectParent(
        EventV1SurfaceCapture capture,
        bool bind,
        out PublishedDecision? decision)
    {
        decision = null;
        if (capture.Status != EventV1SurfaceStatus.Parent ||
            capture.RunIdentity is null || capture.PlayerIdentity is null ||
            capture.RoomIdentity is null || capture.MapIdentity is null ||
            capture.MapOpen || capture.TravelEnabled || capture.Traveling ||
            capture.Candidates.Count > RoomFlowLimits.MaximumEventCandidates)
            return false;
        if (_boundRun is null)
        {
            if (!bind) return false;
            _boundRun = capture.RunIdentity;
            _boundPlayer = capture.PlayerIdentity;
            _boundRoom = capture.RoomIdentity;
            _boundMap = capture.MapIdentity;
        }
        else if (!MatchesBound(capture))
        {
            return false;
        }

        var publicCandidates = new List<EventV1Candidate>(capture.Candidates.Count);
        var publishedCandidates = new List<PublishedCandidate>(capture.Candidates.Count);
        var rawLegal = new List<string>();
        var legal = new List<string>();
        var keys = new HashSet<string>(StringComparer.Ordinal);
        for (int index = 0; index < capture.Candidates.Count; index++)
        {
            EventV1NativeCandidate native = capture.Candidates[index];
            if (native.CandidateIndex != index ||
                !RoomFlowIdentity.IsEventStableId(native.StableId) ||
                !RoomFlowIdentity.IsRenderedText(native.RenderedText) ||
                native.ButtonIdentity is null || native.OptionIdentity is null ||
                native.Dispatch is null || !keys.Add(native.StableId))
                return false;
            string actionId = EventV1CanonicalEncoder.ActionIdFor(index);
            bool enabled = native.Visible && native.Enabled && !native.Locked;
            var candidate = new EventV1Candidate(index, actionId, native.StableId,
                native.RenderedText, enabled, native.IsDangerous, native.IsProceed);
            publicCandidates.Add(candidate);
            publishedCandidates.Add(new PublishedCandidate(candidate, native));
            if (enabled && !native.IsDangerous)
            {
                rawLegal.Add(actionId);
                if (_reservationCount < RoomFlowLimits.MaximumParentActions &&
                    !_reservedStableIds.Contains(native.StableId)) legal.Add(actionId);
            }
        }

        if (capture.EventFinished)
        {
            if (publicCandidates.Count != 1 ||
                !publicCandidates[0].IsProceed ||
                !string.Equals(publicCandidates[0].StableId,
                    EventV1Constants.ProceedStableId, StringComparison.Ordinal) ||
                publicCandidates[0].IsDangerous)
                return false;
        }
        else
        {
            foreach (EventV1Candidate candidate in publicCandidates)
                if (candidate.IsProceed) return false;
        }

        string phase = capture.EventFinished ? "proceed" : "choose_option";
        string displayId = EventV1CanonicalEncoder.ComputeDecisionId(
            _sessionNonce, phase, publicCandidates, rawLegal);
        string transitionId = EventV1CanonicalEncoder.ComputeTransitionId(
            _sessionNonce, phase, publicCandidates, rawLegal);
        EventV1Observation observation;
        if (legal.Count == 0)
        {
            observation = WaitingObservation();
        }
        else
        {
            string decisionId = EventV1CanonicalEncoder.ComputeDecisionId(
                _sessionNonce, phase, publicCandidates, legal);
            observation = new EventV1Observation(_sessionNonce, "ready", phase,
                decisionId, publicCandidates, legal);
        }
        decision = new PublishedDecision(
            observation, displayId, transitionId, publishedCandidates, legal);
        return true;
    }

    private bool MatchesBound(EventV1SurfaceCapture capture) =>
        ReferenceEquals(capture.RunIdentity, _boundRun) &&
        ReferenceEquals(capture.PlayerIdentity, _boundPlayer) &&
        ReferenceEquals(capture.RoomIdentity, _boundRoom) &&
        ReferenceEquals(capture.MapIdentity, _boundMap);

    private static bool SamePublished(PublishedDecision left, PublishedDecision right)
    {
        if (!string.Equals(left.Observation.DecisionId, right.Observation.DecisionId,
                StringComparison.Ordinal) || left.Candidates.Count != right.Candidates.Count)
            return false;
        for (int index = 0; index < left.Candidates.Count; index++)
            if (!SameBinding(left.Candidates[index], right.Candidates[index])) return false;
        return true;
    }

    private static bool SameBinding(PublishedCandidate left, PublishedCandidate right) =>
        ReferenceEquals(left.Native.ButtonIdentity, right.Native.ButtonIdentity) &&
        ReferenceEquals(left.Native.OptionIdentity, right.Native.OptionIdentity) &&
        left.Public.CandidateIndex == right.Public.CandidateIndex &&
        string.Equals(left.Public.ActionId, right.Public.ActionId, StringComparison.Ordinal) &&
        string.Equals(left.Public.StableId, right.Public.StableId, StringComparison.Ordinal) &&
        string.Equals(left.Public.RenderedText, right.Public.RenderedText, StringComparison.Ordinal) &&
        left.Public.Enabled == right.Public.Enabled &&
        left.Public.IsDangerous == right.Public.IsDangerous &&
        left.Public.IsProceed == right.Public.IsProceed;

    private void DisposeChild(bool latchUnsupported)
    {
        IEventItemChildBroker? child = _child;
        _child = null;
        if (latchUnsupported) _unsupported = true;
        try
        {
            child?.Dispose();
        }
        catch
        {
            _unsupported = true;
        }
    }

    private void LatchUnsupported()
    {
        _unsupported = true;
        _published = null;
        _waitingForTransition = false;
        _waitingAfterChild = false;
        _exitProbe = null;
        if (_child is not null) DisposeChild(latchUnsupported: true);
    }

    private bool IsOwnerThread() => Environment.CurrentManagedThreadId == _ownerThreadId;

    private void FinishDeferredDispose()
    {
        _disposeRequested = false;
        IEventItemChildBroker? child = _child;
        _child = null;
        _childIdentity = null;
        _published = null;
        _acceptedReceipt = null;
        _exitProbe = null;
        _resolved = null;
        _boundRun = null;
        _boundPlayer = null;
        _boundRoom = null;
        _boundMap = null;
        _reservedStableIds.Clear();
        child?.Dispose();
    }

    private EventV1Observation WaitingObservation() =>
        EventV1Observation.Inactive(_sessionNonce, "waiting", "waiting");

    private EventV1Observation ItemChildObservation() =>
        EventV1Observation.Inactive(_sessionNonce, "item_child", "item_child");

    private EventV1Observation UnsupportedObservation() =>
        EventV1Observation.Inactive(_sessionNonce, "unsupported", "unknown");

    private RoomFlowApplyFailure Failure(string outcome) =>
        new(EventV1Constants.FlowKind, _sessionNonce, outcome);

    private sealed class PublishedCandidate
    {
        internal PublishedCandidate(EventV1Candidate value, EventV1NativeCandidate native)
        {
            Public = value;
            Native = native;
        }
        internal EventV1Candidate Public { get; }
        internal EventV1NativeCandidate Native { get; }
    }

    private sealed class PublishedDecision
    {
        private readonly IReadOnlyList<string> _legalActions;

        internal PublishedDecision(
            EventV1Observation observation,
            string displayId,
            string transitionId,
            IReadOnlyList<PublishedCandidate> candidates,
            IReadOnlyList<string> legalActions)
        {
            Observation = observation;
            DisplayId = displayId;
            TransitionId = transitionId;
            Candidates = candidates;
            _legalActions = legalActions;
        }

        internal EventV1Observation Observation { get; }
        internal string DisplayId { get; }
        internal string TransitionId { get; }
        internal IReadOnlyList<PublishedCandidate> Candidates { get; }

        internal PublishedCandidate? FindAction(string? actionId)
        {
            if (actionId is null) return null;
            foreach (PublishedCandidate candidate in Candidates)
                if (string.Equals(candidate.Public.ActionId, actionId,
                        StringComparison.Ordinal)) return candidate;
            return null;
        }

        internal bool ContainsLegalAction(string? actionId)
        {
            if (actionId is null) return false;
            foreach (string current in _legalActions)
                if (string.Equals(current, actionId, StringComparison.Ordinal)) return true;
            return false;
        }
    }
}
