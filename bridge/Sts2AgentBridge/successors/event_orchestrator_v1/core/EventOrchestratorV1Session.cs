using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1;

public sealed class EventOrchestratorV1Session : IEventOrchestratorV1Session
{
    private const string CheeseStableId =
        "ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE";

    private readonly object _gate = new();
    private readonly string _nonce;
    private readonly IEventOrchestratorV1NativeAdapter _adapter;
    private readonly int _ownerThreadId = Environment.CurrentManagedThreadId;
    private readonly HashSet<string> _reservedStableIds = new(StringComparer.Ordinal);
    private readonly HashSet<object> _claimedScreens = new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _claimedFactories = new(ReferenceEqualityComparer.Instance);

    private object? _boundRun;
    private object? _boundPlayer;
    private object? _boundRoom;
    private object? _boundMap;
    private object? _boundEvent;
    private PublishedDecision? _published;
    private EventOrchestratorV1AcceptedContext? _accepted;
    private string? _acceptedStructuralId;
    private IEventOrchestratorV1ChildBroker? _child;
    private IEventOrchestratorV1ChildBroker? _cleanupPendingChild;
    private EventOrchestratorV1ChildEnvelope? _childEnvelope;
    private EventOrchestratorV1ChildEnvelope? _completedChild;
    private EventOrchestratorV1PriorResult? _priorResult;
    private EventOrchestratorV1ExitProbe? _exitProbe;
    private EventOrchestratorV1ResolvedResult? _resolved;
    private bool _childWindowOpen;
    private bool _inside;
    private bool _interfered;
    private bool _dispatching;
    private bool _disposeRequested;
    private bool _unsupported;
    private bool _disposed;
    private bool _adapterDisposed;
    private int _reservedDispatches;
    private int _childEpisodes;
    private int _pendingReads;

    public EventOrchestratorV1Session(
        string sessionNonce,
        IEventOrchestratorV1NativeAdapter adapter)
    {
        if (!RoomFlowIdentity.IsNonce(sessionNonce))
            throw new ArgumentException("Session nonce is not canonical.", nameof(sessionNonce));
        _nonce = sessionNonce;
        _adapter = adapter ?? throw new ArgumentNullException(nameof(adapter));
    }

    public string FlowKind => EventOrchestratorV1Limits.FlowKind;

    public int ReservedDispatchCount
    {
        get { lock (_gate) return _reservedDispatches; }
    }

    public int ChildEpisodeCount
    {
        get { lock (_gate) return _childEpisodes; }
    }

    public IEventOrchestratorV1ChildBroker? ActiveChild
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
            if (!Owner())
            {
                RequestDispose();
                return Unsupported();
            }
            if (_inside)
            {
                _interfered = true;
                return Waiting();
            }
            _inside = true;
            IRoomFlowReadValue result;
            try { result = ReadCore(); }
            catch { LatchUnsupported(); result = Unsupported(); }
            finally { _inside = false; }
            if (_disposeRequested)
            {
                RunFinishDispose();
                return Unsupported();
            }
            return result;
        }
    }

    public IRoomFlowApplyValue Apply(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (!Owner())
            {
                RequestDispose();
                return Failure("unsupported");
            }
            if (_inside)
            {
                _interfered = true;
                return Failure("rejected");
            }
            _inside = true;
            int before = _reservedDispatches;
            IRoomFlowApplyValue result;
            try { result = ApplyCore(decisionId, actionId); }
            catch { LatchUnsupported(); result = Failure("unsupported"); }
            finally { _inside = false; }
            if (_disposeRequested)
            {
                bool reserved = before != _reservedDispatches;
                RunFinishDispose();
                if (!reserved) return Failure("unsupported");
            }
            return result;
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (!Owner())
            {
                RequestDispose();
                return;
            }
            if (_inside)
            {
                RequestDispose();
                return;
            }
            if (_disposed && _cleanupPendingChild is null && _adapterDisposed) return;
            RunFinishDispose();
        }
    }

    private IRoomFlowReadValue ReadCore()
    {
        if (_disposed || _unsupported) return Unsupported();
        if (_resolved is not null) return _resolved;
        if (_dispatching) return Waiting();
        if (_child is not null)
        {
            if (!AdvanceChild()) return _unsupported ? Unsupported() : ChildObservation();
            if (_unsupported) return Unsupported();
        }
        if (_exitProbe is not null) return ReadExit();
        return ReadSurface();
    }

    private IRoomFlowApplyValue ApplyCore(string? decisionId, string? actionId)
    {
        if (_disposed || _unsupported || _resolved is not null || _dispatching ||
            _child is not null || _accepted is not null || _published is null)
            return Failure("rejected");

        PublishedDecision published = _published;
        PublishedCandidate? selected = published.Find(actionId);
        if (!RoomFlowIdentity.IsDecisionId(decisionId) ||
            !string.Equals(decisionId, published.Observation.DecisionId, StringComparison.Ordinal) ||
            selected is null || !published.ContainsLegal(actionId) ||
            _reservedStableIds.Contains(selected.Public.StableId) ||
            _reservedDispatches >= EventOrchestratorV1Limits.MaximumParentActions)
            return Failure("rejected");

        EventOrchestratorV1SurfaceCapture current = _adapter.CaptureSurface();
        if (_interfered || _disposeRequested ||
            !TryProject(current, bind: false, out PublishedDecision? recaptured) ||
            recaptured is null || !SamePublished(published, recaptured) ||
            !string.Equals(recaptured.Observation.DecisionId, decisionId,
                StringComparison.Ordinal))
        {
            LatchUnsupported();
            return Failure("unsupported");
        }
        PublishedCandidate? exact = recaptured.Find(actionId);
        if (exact is null || !SameBinding(selected, exact) || !recaptured.ContainsLegal(actionId))
        {
            LatchUnsupported();
            return Failure("unsupported");
        }

        _reservedStableIds.Add(exact.Public.StableId);
        _reservedDispatches++;
        _published = null;
        _priorResult = null;
        _acceptedStructuralId = recaptured.StructuralId;
        _pendingReads = 0;
        _dispatching = true;
        try
        {
            exact.Native.Dispatch();
            if (_interfered || _disposeRequested)
            {
                LatchUnsupported();
                return Failure("uncertain");
            }
            var receipt = new RoomFlowDispatchReceipt(
                EventOrchestratorV1Limits.FlowKind, _nonce, decisionId!, actionId!);
            _accepted = new EventOrchestratorV1AcceptedContext(
                receipt, _reservedDispatches, exact.Public.StableId,
                _boundRun!, _boundPlayer!, _boundRoom!, _boundMap!, _boundEvent!,
                exact.Native.ButtonIdentity, exact.Native.OptionIdentity,
                exact.Native.ControllerIdentity, exact.Native.ChildPolicy,
                exact.Native.ChildFactory);
            if (exact.Public.IsProceed)
            {
                _childWindowOpen = false;
                _exitProbe = new EventOrchestratorV1ExitProbe(
                    _boundRun!, _boundPlayer!, _boundRoom!, _boundMap!);
            }
            else
            {
                _childWindowOpen = exact.Native.ChildFactory is not null;
            }
            return receipt;
        }
        catch
        {
            LatchUnsupported();
            return Failure("uncertain");
        }
        finally { _dispatching = false; }
    }

    private IRoomFlowReadValue ReadSurface()
    {
        EventOrchestratorV1SurfaceCapture capture = _adapter.CaptureSurface();
        if (_interfered || capture is null)
        {
            LatchUnsupported();
            return Unsupported();
        }
        if (_accepted is not null) return ReadPending(capture);
        if (capture.Status == EventOrchestratorV1SurfaceStatus.Missing)
            return Waiting();
        if (capture.Status != EventOrchestratorV1SurfaceStatus.Parent ||
            !TryProject(capture, bind: true, out PublishedDecision? projected) ||
            projected is null)
        {
            LatchUnsupported();
            return Unsupported();
        }
        _published = projected;
        return projected.Observation;
    }

    private IRoomFlowReadValue ReadPending(EventOrchestratorV1SurfaceCapture capture)
    {
        if (capture.Status == EventOrchestratorV1SurfaceStatus.Transient)
        {
            if (!ValidTransient(capture)) return FailRead();
            return PendingWait();
        }
        if (capture.Status == EventOrchestratorV1SurfaceStatus.Child)
        {
            if (!_childWindowOpen || !TryAdmitChild(capture)) return FailRead();
            return ChildObservation();
        }
        if (capture.Status != EventOrchestratorV1SurfaceStatus.Parent ||
            !TryProject(capture, bind: false, out PublishedDecision? projected) ||
            projected is null)
            return FailRead();

        if (string.Equals(projected.StructuralId, _acceptedStructuralId,
                StringComparison.Ordinal))
        {
            if (!MatchesAcceptedCandidate(projected)) return FailRead();
            return PendingWait();
        }

        _childWindowOpen = false;
        ReconcileParentTransition();
        projected = AttachPrior(projected);
        _published = projected;
        return projected.Observation;
    }

    private bool TryAdmitChild(EventOrchestratorV1SurfaceCapture capture)
    {
        EventOrchestratorV1AcceptedContext accepted = _accepted!;
        EventOrchestratorV1ChildPolicy? policy = accepted.ChildPolicy;
        IEventOrchestratorV1ChildFactory? factory = accepted.ChildFactory;
        if (policy is null || factory is null || _childEpisodes >= EventOrchestratorV1Limits.MaximumChildEpisodes ||
            !MatchesBound(capture) || capture.Candidates.Count != 0 || capture.ChildIdentity is null ||
            !ReferenceEquals(capture.ChildPolicy, policy) || !ReferenceEquals(capture.ChildFactory, factory) ||
            _claimedScreens.Contains(capture.ChildIdentity) || _claimedFactories.Contains(factory) ||
            !FactoryMatches(factory, policy))
            return false;

        object screen = capture.ChildIdentity;
        var correlation = new EventOrchestratorV1ChildCorrelation(
            accepted.ParentReceipt, policy.ChildKind, _childEpisodes + 1);

        // Close and tombstone before invoking external construction.
        _childWindowOpen = false;
        _claimedScreens.Add(screen);
        _claimedFactories.Add(factory);
        IEventOrchestratorV1ChildBroker? broker = null;
        try
        {
            broker = factory.Create(accepted, correlation, screen);
            if (_interfered || _disposeRequested || broker is null ||
                !ReferenceEquals(broker.Correlation, correlation) ||
                broker.Correlation.Kind != policy.ChildKind ||
                broker.Correlation.ChildOrdinal != _childEpisodes + 1 ||
                broker.Status != EventOrchestratorV1ChildStatus.Active ||
                policy.ChildKind == EventOrchestratorV1ChildKind.Item &&
                    (broker is not IEventOrchestratorV1ItemChildBroker ||
                     broker is IEventOrchestratorV1CardChildBroker) ||
                policy.ChildKind == EventOrchestratorV1ChildKind.CardSelection &&
                    (broker is not IEventOrchestratorV1CardChildBroker ||
                     broker is IEventOrchestratorV1ItemChildBroker))
                throw new InvalidOperationException("Invalid child broker.");
        }
        catch
        {
            if (broker is not null) RetainAndTryDisposeChild(broker);
            return false;
        }
        _child = broker;
        _childEnvelope = new EventOrchestratorV1ChildEnvelope(correlation);
        _childEpisodes++;
        _pendingReads = 0;
        return true;
    }

    private bool AdvanceChild()
    {
        IEventOrchestratorV1ChildBroker child = _child!;
        EventOrchestratorV1ChildStatus status;
        try { status = child.Status; }
        catch { return FailChild(); }
        if (_interfered || !ReferenceEquals(child.Correlation.ParentReceipt, _accepted?.ParentReceipt) ||
            child.Correlation.ChildOrdinal != _childEpisodes ||
            _childEnvelope is null)
            return FailChild();
        if (status == EventOrchestratorV1ChildStatus.Active) return false;
        if (status != EventOrchestratorV1ChildStatus.Resolved) return FailChild();

        EventOrchestratorV1ChildEnvelope completed = _childEnvelope;
        _child = null;
        _childEnvelope = null;
        _childWindowOpen = false;
        _completedChild = completed;
        _pendingReads = 0;
        if (!RetainAndTryDisposeChild(child))
        {
            LatchUnsupported();
            return false;
        }
        if (_interfered || _disposeRequested)
        {
            LatchUnsupported();
            return false;
        }
        return true;
    }

    private bool FailChild()
    {
        IEventOrchestratorV1ChildBroker? child = _child;
        _child = null;
        _childEnvelope = null;
        LatchUnsupported();
        if (child is not null) RetainAndTryDisposeChild(child);
        return false;
    }

    private IRoomFlowReadValue ReadExit()
    {
        EventOrchestratorV1ExitCapture capture = _adapter.CaptureExit(_exitProbe!);
        if (_interfered || capture is null ||
            !ReferenceEquals(capture.RunIdentity, _boundRun) ||
            !ReferenceEquals(capture.PlayerIdentity, _boundPlayer) ||
            !ReferenceEquals(capture.RoomIdentity, _boundRoom) ||
            !ReferenceEquals(capture.MapIdentity, _boundMap))
            return FailRead();
        if (capture.MapOpen && capture.TravelEnabled && !capture.Traveling)
        {
            RoomFlowDispatchReceipt receipt = _accepted!.ParentReceipt;
            var result = new EventOrchestratorV1PriorResult(
                receipt.DecisionId, receipt.ActionId,
                EventOrchestratorV1Limits.MapHandoffResult, null);
            _resolved = new EventOrchestratorV1ResolvedResult(
                _nonce, receipt.DecisionId, receipt.ActionId, result);
            _priorResult = result;
            _exitProbe = null;
            _accepted = null;
            _acceptedStructuralId = null;
            return _resolved;
        }
        if (!capture.MapOpen && !capture.TravelEnabled && !capture.Traveling)
            return PendingWait();
        return FailRead();
    }

    private void ReconcileParentTransition()
    {
        RoomFlowDispatchReceipt receipt = _accepted!.ParentReceipt;
        string result = _completedChild is null
            ? EventOrchestratorV1Limits.OptionTransitionResult
            : EventOrchestratorV1Limits.ChildCompletedResult;
        _priorResult = new EventOrchestratorV1PriorResult(
            receipt.DecisionId, receipt.ActionId, result, _completedChild);
        _accepted = null;
        _acceptedStructuralId = null;
        _completedChild = null;
        _pendingReads = 0;
    }

    private bool TryProject(
        EventOrchestratorV1SurfaceCapture capture,
        bool bind,
        out PublishedDecision? decision)
    {
        decision = null;
        if (capture.Status != EventOrchestratorV1SurfaceStatus.Parent ||
            capture.RunIdentity is null || capture.PlayerIdentity is null ||
            capture.RoomIdentity is null || capture.MapIdentity is null ||
            capture.EventIdentity is null || capture.MapOpen || capture.TravelEnabled ||
            capture.Traveling || capture.ChildIdentity is not null ||
            capture.ChildPolicy is not null || capture.ChildFactory is not null ||
            capture.Candidates.Count > EventOrchestratorV1Limits.MaximumCandidates)
            return false;
        if (_boundRun is null)
        {
            if (!bind) return false;
            _boundRun = capture.RunIdentity;
            _boundPlayer = capture.PlayerIdentity;
            _boundRoom = capture.RoomIdentity;
            _boundMap = capture.MapIdentity;
            _boundEvent = capture.EventIdentity;
        }
        else if (!MatchesBound(capture)) return false;

        var values = new List<EventOrchestratorV1Candidate>(capture.Candidates.Count);
        var natives = new List<PublishedCandidate>(capture.Candidates.Count);
        var legal = new List<string>();
        var keys = new HashSet<string>(StringComparer.Ordinal);
        for (int index = 0; index < capture.Candidates.Count; index++)
        {
            EventOrchestratorV1NativeCandidate native = capture.Candidates[index];
            if (native is null || native.CandidateIndex != index ||
                !RoomFlowIdentity.IsEventStableId(native.StableId) ||
                !RoomFlowIdentity.IsRenderedText(native.RenderedText) ||
                native.ButtonIdentity is null || native.OptionIdentity is null ||
                native.ControllerIdentity is null || native.Dispatch is null ||
                !keys.Add(native.StableId) || !ValidCapability(native))
                return false;
            string action = EventOrchestratorV1CanonicalEncoder.ActionIdFor(index);
            bool enabled = native.Visible && native.Enabled && !native.Locked;
            string policy = PolicyName(native.ChildPolicy);
            var value = new EventOrchestratorV1Candidate(index, action, native.StableId,
                native.RenderedText, enabled, native.IsDangerous, native.IsProceed, policy);
            values.Add(value);
            natives.Add(new PublishedCandidate(value, native));
            if (enabled && !native.IsDangerous &&
                _reservedDispatches < EventOrchestratorV1Limits.MaximumParentActions &&
                !_reservedStableIds.Contains(native.StableId)) legal.Add(action);
        }
        if (capture.EventFinished)
        {
            if (values.Count != 1 || !values[0].IsProceed || values[0].IsDangerous ||
                values[0].StableId != "PROCEED") return false;
        }
        else
        {
            if (values.Count == 0) return false;
            foreach (EventOrchestratorV1Candidate value in values)
                if (value.IsProceed) return false;
        }
        string phase = capture.EventFinished
            ? EventOrchestratorV1Limits.ProceedPhase
            : EventOrchestratorV1Limits.ChooseOptionPhase;
        string structural = EventOrchestratorV1CanonicalEncoder.ComputeStructuralId(
            _nonce, phase, values);
        EventOrchestratorV1Observation observation;
        if (legal.Count == 0)
            observation = Observation(EventOrchestratorV1Limits.WaitingStatus,
                EventOrchestratorV1Limits.WaitingPhase, string.Empty,
                Array.Empty<EventOrchestratorV1Candidate>(), Array.Empty<string>(), null);
        else
        {
            string id = EventOrchestratorV1CanonicalEncoder.ComputeDecisionId(
                _nonce, phase, values, legal);
            observation = Observation(EventOrchestratorV1Limits.ReadyStatus,
                phase, id, values, legal, null);
        }
        decision = new PublishedDecision(observation, structural, natives, legal);
        return true;
    }

    private static bool ValidCapability(EventOrchestratorV1NativeCandidate candidate)
    {
        bool paired = (candidate.ChildPolicy is null) == (candidate.ChildFactory is null);
        if (!paired || candidate.IsProceed && candidate.ChildPolicy is not null) return false;
        if (candidate.IsProceed) return true;
        if (candidate.ChildPolicy is null || candidate.ChildFactory is null ||
            !ValidPolicy(candidate.ChildPolicy) ||
            !FactoryMatches(candidate.ChildFactory, candidate.ChildPolicy)) return false;
        if (candidate.StableId == CheeseStableId)
            return candidate.ChildPolicy.PolicyKind ==
                EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo;
        return candidate.ChildPolicy.PolicyKind == EventOrchestratorV1ChildPolicyKind.ItemReward;
    }

    private static bool ValidPolicy(EventOrchestratorV1ChildPolicy policy) =>
        policy.PolicyKind switch
        {
            EventOrchestratorV1ChildPolicyKind.ItemReward =>
                policy.ChildKind == EventOrchestratorV1ChildKind.Item &&
                policy.MinSelect == 0 && policy.MaxSelect == 0 &&
                policy.ExpectedDomainCount == 0,
            EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo =>
                policy.ChildKind == EventOrchestratorV1ChildKind.CardSelection &&
                policy.CardOperation == CardSelectionV1.CardSelectionV1Operation.Add &&
                policy.MinSelect == 2 && policy.MaxSelect == 2 &&
                policy.CardCommitMode == CardSelectionV1.CardSelectionV1CommitMode.AutoAtMax &&
                policy.ExpectedDomainCount == 8,
            _ => false,
        };

    private static bool FactoryMatches(
        IEventOrchestratorV1ChildFactory factory,
        EventOrchestratorV1ChildPolicy policy)
    {
        try { return ReferenceEquals(factory.Policy, policy); }
        catch { return false; }
    }

    private bool ValidTransient(EventOrchestratorV1SurfaceCapture capture) =>
        MatchesBound(capture) && capture.Candidates.Count == 0 &&
        capture.ChildIdentity is null && capture.ChildPolicy is null && capture.ChildFactory is null;

    private bool MatchesBound(EventOrchestratorV1SurfaceCapture capture) =>
        ReferenceEquals(capture.RunIdentity, _boundRun) &&
        ReferenceEquals(capture.PlayerIdentity, _boundPlayer) &&
        ReferenceEquals(capture.RoomIdentity, _boundRoom) &&
        ReferenceEquals(capture.MapIdentity, _boundMap) &&
        ReferenceEquals(capture.EventIdentity, _boundEvent);

    private static bool SamePublished(PublishedDecision left, PublishedDecision right)
    {
        if (left.Observation.DecisionId != right.Observation.DecisionId ||
            left.Candidates.Count != right.Candidates.Count) return false;
        for (int index = 0; index < left.Candidates.Count; index++)
            if (!SameBinding(left.Candidates[index], right.Candidates[index])) return false;
        return true;
    }

    private bool MatchesAcceptedCandidate(PublishedDecision current)
    {
        EventOrchestratorV1AcceptedContext accepted = _accepted!;
        PublishedCandidate? candidate = current.Find(accepted.ParentReceipt.ActionId);
        return candidate is not null &&
            candidate.Public.StableId == accepted.StableId &&
            ReferenceEquals(candidate.Native.ButtonIdentity, accepted.ButtonIdentity) &&
            ReferenceEquals(candidate.Native.OptionIdentity, accepted.OptionIdentity) &&
            ReferenceEquals(candidate.Native.ControllerIdentity, accepted.ControllerIdentity) &&
            ReferenceEquals(candidate.Native.ChildPolicy, accepted.ChildPolicy) &&
            ReferenceEquals(candidate.Native.ChildFactory, accepted.ChildFactory);
    }

    private PublishedDecision AttachPrior(PublishedDecision projected)
    {
        EventOrchestratorV1Observation old = projected.Observation;
        var observation = new EventOrchestratorV1Observation(
            _nonce, old.Status, old.Phase, old.DecisionId,
            old.Candidates, old.LegalActions, old.Child, _priorResult);
        return new PublishedDecision(
            observation, projected.StructuralId, projected.Candidates, projected.LegalActions);
    }

    private static bool SameBinding(PublishedCandidate left, PublishedCandidate right) =>
        ReferenceEquals(left.Native.ButtonIdentity, right.Native.ButtonIdentity) &&
        ReferenceEquals(left.Native.OptionIdentity, right.Native.OptionIdentity) &&
        ReferenceEquals(left.Native.ControllerIdentity, right.Native.ControllerIdentity) &&
        ReferenceEquals(left.Native.ChildPolicy, right.Native.ChildPolicy) &&
        ReferenceEquals(left.Native.ChildFactory, right.Native.ChildFactory) &&
        left.Public.CandidateIndex == right.Public.CandidateIndex &&
        left.Public.ActionId == right.Public.ActionId &&
        left.Public.StableId == right.Public.StableId &&
        left.Public.RenderedText == right.Public.RenderedText &&
        left.Public.Enabled == right.Public.Enabled &&
        left.Public.IsDangerous == right.Public.IsDangerous &&
        left.Public.IsProceed == right.Public.IsProceed &&
        left.Public.ChildPolicy == right.Public.ChildPolicy;

    private static string PolicyName(EventOrchestratorV1ChildPolicy? policy) =>
        policy?.PolicyKind switch
        {
            null => EventOrchestratorV1Limits.NoChildPolicy,
            EventOrchestratorV1ChildPolicyKind.ItemReward =>
                EventOrchestratorV1Limits.ItemRewardPolicy,
            EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo =>
                EventOrchestratorV1Limits.CheeseGorgeAddTwoPolicy,
            _ => throw new InvalidOperationException("Unknown child policy."),
        };

    private IRoomFlowReadValue PendingWait()
    {
        _pendingReads++;
        if (_pendingReads >= EventOrchestratorV1Limits.MaximumNativePendingReads)
            return FailRead();
        _published = null;
        return Waiting();
    }

    private IRoomFlowReadValue FailRead()
    {
        LatchUnsupported();
        return Unsupported();
    }

    private EventOrchestratorV1Observation Observation(
        string status,
        string phase,
        string decision,
        IReadOnlyList<EventOrchestratorV1Candidate> candidates,
        IReadOnlyList<string> legal,
        EventOrchestratorV1ChildEnvelope? child) =>
        new(_nonce, status, phase, decision, candidates, legal, child, _priorResult);

    private EventOrchestratorV1Observation Waiting() =>
        Observation(EventOrchestratorV1Limits.WaitingStatus,
            EventOrchestratorV1Limits.WaitingPhase, string.Empty,
            Array.Empty<EventOrchestratorV1Candidate>(), Array.Empty<string>(), null);

    private EventOrchestratorV1Observation ChildObservation() =>
        Observation(EventOrchestratorV1Limits.ChildStatus,
            EventOrchestratorV1Limits.ChildPhase, string.Empty,
            Array.Empty<EventOrchestratorV1Candidate>(), Array.Empty<string>(), _childEnvelope);

    private EventOrchestratorV1Observation Unsupported() =>
        new(_nonce, EventOrchestratorV1Limits.UnsupportedStatus,
            EventOrchestratorV1Limits.UnsupportedPhase, string.Empty,
            Array.Empty<EventOrchestratorV1Candidate>(), Array.Empty<string>(), null, null);

    private RoomFlowApplyFailure Failure(string outcome) =>
        new(EventOrchestratorV1Limits.FlowKind, _nonce, outcome);

    private void LatchUnsupported()
    {
        _unsupported = true;
        _published = null;
        _childWindowOpen = false;
        _exitProbe = null;
    }

    private void RequestDispose()
    {
        _disposeRequested = true;
        _unsupported = true;
        _disposed = true;
        _published = null;
        _childWindowOpen = false;
    }

    private bool RetainAndTryDisposeChild(IEventOrchestratorV1ChildBroker child)
    {
        _cleanupPendingChild = child;
        try
        {
            child.Dispose();
            _cleanupPendingChild = null;
            return true;
        }
        catch { return false; }
    }

    private void RunFinishDispose()
    {
        bool priorInside = _inside;
        _inside = true;
        try { FinishDispose(); }
        finally { _inside = priorInside; }
    }

    private void FinishDispose()
    {
        _disposeRequested = false;
        _disposed = true;
        _unsupported = true;
        IEventOrchestratorV1ChildBroker? child = _child;
        _child = null;
        _childEnvelope = null;
        _published = null;
        _accepted = null;
        _acceptedStructuralId = null;
        _exitProbe = null;
        _resolved = null;
        _boundRun = null;
        _boundPlayer = null;
        _boundRoom = null;
        _boundMap = null;
        _boundEvent = null;
        _reservedStableIds.Clear();
        if (_cleanupPendingChild is null && child is not null)
            _cleanupPendingChild = child;
        if (_cleanupPendingChild is not null)
        {
            IEventOrchestratorV1ChildBroker pending = _cleanupPendingChild;
            try { pending.Dispose(); }
            catch (Exception error)
            {
                throw new InvalidOperationException("Event child cleanup failed.", error);
            }
            _cleanupPendingChild = null;
        }
        if (!_adapterDisposed)
        {
            try { _adapter.Dispose(); }
            catch (Exception error)
            {
                throw new InvalidOperationException("Event adapter cleanup failed.", error);
            }
            _adapterDisposed = true;
        }
    }

    private bool Owner() => Environment.CurrentManagedThreadId == _ownerThreadId;

    private sealed class PublishedCandidate
    {
        internal PublishedCandidate(
            EventOrchestratorV1Candidate value,
            EventOrchestratorV1NativeCandidate native)
        {
            Public = value;
            Native = native;
        }
        internal EventOrchestratorV1Candidate Public { get; }
        internal EventOrchestratorV1NativeCandidate Native { get; }
    }

    private sealed class PublishedDecision
    {
        private readonly IReadOnlyList<string> _legal;
        internal PublishedDecision(
            EventOrchestratorV1Observation observation,
            string structuralId,
            IReadOnlyList<PublishedCandidate> candidates,
            IReadOnlyList<string> legal)
        {
            Observation = observation;
            StructuralId = structuralId;
            Candidates = candidates;
            _legal = legal;
        }
        internal EventOrchestratorV1Observation Observation { get; }
        internal string StructuralId { get; }
        internal IReadOnlyList<PublishedCandidate> Candidates { get; }
        internal IReadOnlyList<string> LegalActions => _legal;
        internal bool ContainsLegal(string? action) => action is not null &&
            IndexOf(_legal, action) >= 0;
        internal PublishedCandidate? Find(string? action)
        {
            if (action is null) return null;
            foreach (PublishedCandidate candidate in Candidates)
                if (candidate.Public.ActionId == action) return candidate;
            return null;
        }
        private static int IndexOf(IReadOnlyList<string> values, string value)
        {
            for (int index = 0; index < values.Count; index++)
                if (values[index] == value) return index;
            return -1;
        }
    }
}
