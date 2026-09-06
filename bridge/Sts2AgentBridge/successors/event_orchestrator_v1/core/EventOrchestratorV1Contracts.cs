using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1;

// DRAFT: this file is a review input. It is not an accepted production contract.
public static class EventOrchestratorV1Limits
{
    public const string Version = "event_orchestrator_v1";
    public const string FlowKind = "event";
    public const int MaximumCandidates = 8;
    public const int MaximumParentActions = 12;
    public const int MaximumChildEpisodes = 4;
    public const int MaximumNativePendingReads = 256;
    public const int MaximumHostReads = 2048;
    public const int MaximumTotalActions = 52;
    public const string ReadyStatus = "ready";
    public const string WaitingStatus = "waiting";
    public const string ChildStatus = "child";
    public const string UnsupportedStatus = "unsupported";
    public const string ChooseOptionPhase = "choose_option";
    public const string ProceedPhase = "proceed";
    public const string ChildPhase = "child";
    public const string WaitingPhase = "waiting";
    public const string UnsupportedPhase = "unsupported";
    public const string NoChildPolicy = "";
    public const string ItemRewardPolicy = "item_reward";
    public const string CheeseGorgeAddTwoPolicy = "cheese_gorge_add_two";
    public const string OptionTransitionResult = "option_transition";
    public const string ChildCompletedResult = "child_completed";
    public const string MapHandoffResult = "map_handoff";
}

public enum EventOrchestratorV1SurfaceStatus
{
    Missing = 1,
    Parent = 2,
    Child = 3,
    Transient = 4,
    Unsupported = 5,
}

public enum EventOrchestratorV1ChildKind
{
    Item = 1,
    CardSelection = 2,
}

// The first version recognizes only capabilities backed by frozen native facts.
// Adding another policy is a contract and native-census change.
public enum EventOrchestratorV1ChildPolicyKind
{
    ItemReward = 1,
    CheeseGorgeAddTwo = 2,
}

public enum EventOrchestratorV1ChildStatus
{
    Active = 1,
    Resolved = 2,
    Failed = 3,
}

public sealed class EventOrchestratorV1ChildPolicy
{
    private EventOrchestratorV1ChildPolicy(
        EventOrchestratorV1ChildPolicyKind policyKind,
        EventOrchestratorV1ChildKind childKind,
        CardSelectionV1Operation cardOperation,
        int minSelect,
        int maxSelect,
        CardSelectionV1CommitMode cardCommitMode,
        int expectedDomainCount)
    {
        PolicyKind = policyKind;
        ChildKind = childKind;
        CardOperation = cardOperation;
        MinSelect = minSelect;
        MaxSelect = maxSelect;
        CardCommitMode = cardCommitMode;
        ExpectedDomainCount = expectedDomainCount;
    }

    public EventOrchestratorV1ChildPolicyKind PolicyKind { get; }
    public EventOrchestratorV1ChildKind ChildKind { get; }
    public CardSelectionV1Operation CardOperation { get; }
    public int MinSelect { get; }
    public int MaxSelect { get; }
    public CardSelectionV1CommitMode CardCommitMode { get; }
    public int ExpectedDomainCount { get; }

    public static EventOrchestratorV1ChildPolicy ItemReward() =>
        new(EventOrchestratorV1ChildPolicyKind.ItemReward,
            EventOrchestratorV1ChildKind.Item,
            default, 0, 0, default, 0);

    public static EventOrchestratorV1ChildPolicy CheeseGorgeAddTwo() =>
        new(EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo,
            EventOrchestratorV1ChildKind.CardSelection,
            CardSelectionV1Operation.Add, 2, 2,
            CardSelectionV1CommitMode.AutoAtMax, 8);
}

// The same policy and factory instances are retained at decision publication,
// copied into the accepted context, and reference-compared at child admission.
public interface IEventOrchestratorV1ChildFactory
{
    EventOrchestratorV1ChildPolicy Policy { get; }

    // The caller tombstones this factory and exactForegroundIdentity before
    // invocation. A returned broker must retain the exact correlation object.
    IEventOrchestratorV1ChildBroker Create(
        EventOrchestratorV1AcceptedContext acceptedContext,
        EventOrchestratorV1ChildCorrelation correlation,
        object exactForegroundIdentity);
}

public sealed class EventOrchestratorV1NativeCandidate
{
    public EventOrchestratorV1NativeCandidate(
        int candidateIndex,
        string stableId,
        string renderedText,
        bool visible,
        bool enabled,
        bool locked,
        bool isDangerous,
        bool isProceed,
        object buttonIdentity,
        object optionIdentity,
        object controllerIdentity,
        Action dispatch,
        EventOrchestratorV1ChildPolicy? childPolicy,
        IEventOrchestratorV1ChildFactory? childFactory)
    {
        CandidateIndex = candidateIndex;
        StableId = stableId;
        RenderedText = renderedText;
        Visible = visible;
        Enabled = enabled;
        Locked = locked;
        IsDangerous = isDangerous;
        IsProceed = isProceed;
        ButtonIdentity = buttonIdentity;
        OptionIdentity = optionIdentity;
        ControllerIdentity = controllerIdentity;
        Dispatch = dispatch;
        ChildPolicy = childPolicy;
        ChildFactory = childFactory;
    }

    public int CandidateIndex { get; }
    public string StableId { get; }
    public string RenderedText { get; }
    public bool Visible { get; }
    public bool Enabled { get; }
    public bool Locked { get; }
    public bool IsDangerous { get; }
    public bool IsProceed { get; }
    public object ButtonIdentity { get; }
    public object OptionIdentity { get; }
    public object ControllerIdentity { get; }
    public Action Dispatch { get; }
    public EventOrchestratorV1ChildPolicy? ChildPolicy { get; }
    public IEventOrchestratorV1ChildFactory? ChildFactory { get; }
}

public sealed class EventOrchestratorV1SurfaceCapture
{
    private readonly IReadOnlyList<EventOrchestratorV1NativeCandidate> _candidates;

    private EventOrchestratorV1SurfaceCapture(
        EventOrchestratorV1SurfaceStatus status,
        object? runIdentity,
        object? playerIdentity,
        object? roomIdentity,
        object? mapIdentity,
        object? eventIdentity,
        bool eventFinished,
        bool mapOpen,
        bool travelEnabled,
        bool traveling,
        IReadOnlyList<EventOrchestratorV1NativeCandidate> candidates,
        object? childIdentity,
        EventOrchestratorV1ChildPolicy? childPolicy,
        IEventOrchestratorV1ChildFactory? childFactory)
    {
        Status = status;
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RoomIdentity = roomIdentity;
        MapIdentity = mapIdentity;
        EventIdentity = eventIdentity;
        EventFinished = eventFinished;
        MapOpen = mapOpen;
        TravelEnabled = travelEnabled;
        Traveling = traveling;
        var copy = new EventOrchestratorV1NativeCandidate[candidates.Count];
        for (int index = 0; index < copy.Length; index++) copy[index] = candidates[index];
        _candidates = Array.AsReadOnly(copy);
        ChildIdentity = childIdentity;
        ChildPolicy = childPolicy;
        ChildFactory = childFactory;
    }

    public EventOrchestratorV1SurfaceStatus Status { get; }
    public object? RunIdentity { get; }
    public object? PlayerIdentity { get; }
    public object? RoomIdentity { get; }
    public object? MapIdentity { get; }
    public object? EventIdentity { get; }
    public bool EventFinished { get; }
    public bool MapOpen { get; }
    public bool TravelEnabled { get; }
    public bool Traveling { get; }
    public IReadOnlyList<EventOrchestratorV1NativeCandidate> Candidates => _candidates;
    public object? ChildIdentity { get; }
    public EventOrchestratorV1ChildPolicy? ChildPolicy { get; }
    public IEventOrchestratorV1ChildFactory? ChildFactory { get; }

    public static EventOrchestratorV1SurfaceCapture Missing() =>
        Empty(EventOrchestratorV1SurfaceStatus.Missing);

    public static EventOrchestratorV1SurfaceCapture Unsupported() =>
        Empty(EventOrchestratorV1SurfaceStatus.Unsupported);

    // A post-dispatch absence is waitable only when the native adapter can
    // still prove the exact bound event context. It carries no action or child
    // capability and cannot reopen a closed child-admission window.
    public static EventOrchestratorV1SurfaceCapture Transient(
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity,
        object eventIdentity) =>
        new(EventOrchestratorV1SurfaceStatus.Transient,
            runIdentity, playerIdentity, roomIdentity, mapIdentity, eventIdentity,
            false, false, false, false,
            Array.Empty<EventOrchestratorV1NativeCandidate>(), null, null, null);

    public static EventOrchestratorV1SurfaceCapture Parent(
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity,
        object eventIdentity,
        bool eventFinished,
        bool mapOpen,
        bool travelEnabled,
        bool traveling,
        IReadOnlyList<EventOrchestratorV1NativeCandidate> candidates) =>
        new(EventOrchestratorV1SurfaceStatus.Parent,
            runIdentity, playerIdentity, roomIdentity, mapIdentity, eventIdentity,
            eventFinished, mapOpen, travelEnabled, traveling, candidates,
            null, null, null);

    public static EventOrchestratorV1SurfaceCapture Child(
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity,
        object eventIdentity,
        object childIdentity,
        EventOrchestratorV1ChildPolicy childPolicy,
        IEventOrchestratorV1ChildFactory childFactory) =>
        new(EventOrchestratorV1SurfaceStatus.Child,
            runIdentity, playerIdentity, roomIdentity, mapIdentity, eventIdentity,
            false, false, false, false,
            Array.Empty<EventOrchestratorV1NativeCandidate>(),
            childIdentity, childPolicy, childFactory);

    private static EventOrchestratorV1SurfaceCapture Empty(
        EventOrchestratorV1SurfaceStatus status) =>
        new(status, null, null, null, null, null, false, false, false, false,
            Array.Empty<EventOrchestratorV1NativeCandidate>(), null, null, null);
}

// Created only after reservation, exact decision recapture and successful
// native dispatch. A dispatch throw never creates an accepted context or child
// authority. Native identities never enter a wire projection.
public sealed class EventOrchestratorV1AcceptedContext
{
    internal EventOrchestratorV1AcceptedContext(
        RoomFlowDispatchReceipt parentReceipt,
        int acceptedActionOrdinal,
        string stableId,
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity,
        object eventIdentity,
        object buttonIdentity,
        object optionIdentity,
        object controllerIdentity,
        EventOrchestratorV1ChildPolicy? childPolicy,
        IEventOrchestratorV1ChildFactory? childFactory)
    {
        ParentReceipt = parentReceipt;
        AcceptedActionOrdinal = acceptedActionOrdinal;
        StableId = stableId;
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RoomIdentity = roomIdentity;
        MapIdentity = mapIdentity;
        EventIdentity = eventIdentity;
        ButtonIdentity = buttonIdentity;
        OptionIdentity = optionIdentity;
        ControllerIdentity = controllerIdentity;
        ChildPolicy = childPolicy;
        ChildFactory = childFactory;
    }

    public RoomFlowDispatchReceipt ParentReceipt { get; }
    public int AcceptedActionOrdinal { get; }
    public string StableId { get; }
    public object RunIdentity { get; }
    public object PlayerIdentity { get; }
    public object RoomIdentity { get; }
    public object MapIdentity { get; }
    public object EventIdentity { get; }
    public object ButtonIdentity { get; }
    public object OptionIdentity { get; }
    public object ControllerIdentity { get; }
    public EventOrchestratorV1ChildPolicy? ChildPolicy { get; }
    public IEventOrchestratorV1ChildFactory? ChildFactory { get; }
}

public sealed class EventOrchestratorV1ChildCorrelation
{
    internal EventOrchestratorV1ChildCorrelation(
        RoomFlowDispatchReceipt parentReceipt,
        EventOrchestratorV1ChildKind kind,
        int childOrdinal)
    {
        ParentReceipt = parentReceipt;
        Kind = kind;
        ChildOrdinal = childOrdinal;
    }

    public RoomFlowDispatchReceipt ParentReceipt { get; }
    public EventOrchestratorV1ChildKind Kind { get; }
    public int ChildOrdinal { get; }
}

public interface IEventOrchestratorV1ChildBroker : IDisposable
{
    EventOrchestratorV1ChildCorrelation Correlation { get; }
    EventOrchestratorV1ChildStatus Status { get; }
}

public interface IEventOrchestratorV1ItemChildBroker : IEventOrchestratorV1ChildBroker
{
    IItemV1ReadValue Read();
    IItemV1ApplyValue Apply(string? decisionId, string? actionId);
}

public interface IEventOrchestratorV1CardChildBroker : IEventOrchestratorV1ChildBroker
{
    ICardSelectionV1ReadValue Read();
    ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId);
}

public sealed class EventOrchestratorV1Candidate
{
    public EventOrchestratorV1Candidate(
        int candidateIndex,
        string actionId,
        string stableId,
        string renderedText,
        bool enabled,
        bool isDangerous,
        bool isProceed,
        string childPolicy)
    {
        CandidateIndex = candidateIndex;
        ActionId = actionId;
        StableId = stableId;
        RenderedText = renderedText;
        Enabled = enabled;
        IsDangerous = isDangerous;
        IsProceed = isProceed;
        ChildPolicy = childPolicy;
    }

    public int CandidateIndex { get; }
    public string ActionId { get; }
    public string StableId { get; }
    public string RenderedText { get; }
    public bool Enabled { get; }
    public bool IsDangerous { get; }
    public bool IsProceed { get; }
    public string ChildPolicy { get; }
}

// Scalar wire-safe projection of the active child correlation.
public sealed class EventOrchestratorV1ChildEnvelope
{
    internal EventOrchestratorV1ChildEnvelope(EventOrchestratorV1ChildCorrelation correlation)
    {
        Kind = correlation.Kind == EventOrchestratorV1ChildKind.Item
            ? "item" : "card_selection";
        ChildOrdinal = correlation.ChildOrdinal;
        ParentDecisionId = correlation.ParentReceipt.DecisionId;
        ParentActionId = correlation.ParentReceipt.ActionId;
    }

    public string Kind { get; }
    public int ChildOrdinal { get; }
    public string ParentDecisionId { get; }
    public string ParentActionId { get; }
}

public sealed class EventOrchestratorV1PriorResult
{
    internal EventOrchestratorV1PriorResult(
        string decisionId,
        string actionId,
        string result,
        EventOrchestratorV1ChildEnvelope? child)
    {
        DecisionId = decisionId;
        ActionId = actionId;
        Result = result;
        Child = child;
    }

    public string DecisionId { get; }
    public string ActionId { get; }
    public string Result { get; }
    public EventOrchestratorV1ChildEnvelope? Child { get; }
}

public sealed class EventOrchestratorV1Observation : IRoomFlowReadValue
{
    private readonly IReadOnlyList<EventOrchestratorV1Candidate> _candidates;
    private readonly IReadOnlyList<string> _legalActions;

    internal EventOrchestratorV1Observation(
        string sessionNonce,
        string status,
        string phase,
        string decisionId,
        IReadOnlyList<EventOrchestratorV1Candidate> candidates,
        IReadOnlyList<string> legalActions,
        EventOrchestratorV1ChildEnvelope? child,
        EventOrchestratorV1PriorResult? priorResult)
    {
        Version = EventOrchestratorV1Limits.Version;
        FlowKind = EventOrchestratorV1Limits.FlowKind;
        SessionNonce = sessionNonce;
        Status = status;
        Phase = phase;
        DecisionId = decisionId;
        _candidates = Copy(candidates);
        _legalActions = Copy(legalActions);
        Child = child;
        PriorResult = priorResult;
    }

    public string Version { get; }
    public string FlowKind { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal => RoomFlowLimits.ParentOrdinal;
    public string Status { get; }
    public string Phase { get; }
    public string DecisionId { get; }
    public IReadOnlyList<EventOrchestratorV1Candidate> Candidates => _candidates;
    public IReadOnlyList<string> LegalActions => _legalActions;
    public EventOrchestratorV1ChildEnvelope? Child { get; }
    public EventOrchestratorV1PriorResult? PriorResult { get; }

    private static IReadOnlyList<T> Copy<T>(IReadOnlyList<T> source)
    {
        var copy = new T[source.Count];
        for (int index = 0; index < copy.Length; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }
}

public sealed class EventOrchestratorV1ResolvedResult : IRoomFlowReadValue
{
    internal EventOrchestratorV1ResolvedResult(
        string sessionNonce,
        string decisionId,
        string actionId,
        EventOrchestratorV1PriorResult? priorResult)
    {
        Version = EventOrchestratorV1Limits.Version;
        FlowKind = EventOrchestratorV1Limits.FlowKind;
        SessionNonce = sessionNonce;
        DecisionId = decisionId;
        ActionId = actionId;
        PriorResult = priorResult;
    }

    public string Version { get; }
    public string FlowKind { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal => RoomFlowLimits.ParentOrdinal;
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Result => EventOrchestratorV1Limits.MapHandoffResult;
    public EventOrchestratorV1PriorResult? PriorResult { get; }
}

public sealed class EventOrchestratorV1ExitProbe
{
    internal EventOrchestratorV1ExitProbe(
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity)
    {
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RoomIdentity = roomIdentity;
        MapIdentity = mapIdentity;
    }

    public object RunIdentity { get; }
    public object PlayerIdentity { get; }
    public object RoomIdentity { get; }
    public object MapIdentity { get; }
}

public sealed class EventOrchestratorV1ExitCapture
{
    public EventOrchestratorV1ExitCapture(
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity,
        bool mapOpen,
        bool travelEnabled,
        bool traveling)
    {
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RoomIdentity = roomIdentity;
        MapIdentity = mapIdentity;
        MapOpen = mapOpen;
        TravelEnabled = travelEnabled;
        Traveling = traveling;
    }

    public object RunIdentity { get; }
    public object PlayerIdentity { get; }
    public object RoomIdentity { get; }
    public object MapIdentity { get; }
    public bool MapOpen { get; }
    public bool TravelEnabled { get; }
    public bool Traveling { get; }
}

public interface IEventOrchestratorV1NativeAdapter : IDisposable
{
    EventOrchestratorV1SurfaceCapture CaptureSurface();
    EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending);
}

// Parent Read returns only EventOrchestratorV1Observation or
// EventOrchestratorV1ResolvedResult. Parent Apply returns only the frozen
// RoomFlowDispatchReceipt or RoomFlowApplyFailure. While Read reports the
// child phase, ActiveChild supplies the one correlated typed child broker to
// the unified wire service; a request can never create or select that broker.
public interface IEventOrchestratorV1Session : IRoomFlowSession
{
    IEventOrchestratorV1ChildBroker? ActiveChild { get; }
}
