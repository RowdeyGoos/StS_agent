using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Event;

public static class EventV1Constants
{
    public const string Version = "event_v1";
    public const string FlowKind = "event";
    public const string ProceedStableId = "PROCEED";
}

public sealed class EventV1Candidate
{
    public EventV1Candidate(
        int candidateIndex,
        string actionId,
        string stableId,
        string renderedText,
        bool enabled,
        bool isDangerous,
        bool isProceed)
    {
        CandidateIndex = candidateIndex;
        ActionId = actionId;
        StableId = stableId;
        RenderedText = renderedText;
        Enabled = enabled;
        IsDangerous = isDangerous;
        IsProceed = isProceed;
    }

    public int CandidateIndex { get; }
    public string ActionId { get; }
    public string StableId { get; }
    public string RenderedText { get; }
    public bool Enabled { get; }
    public bool IsDangerous { get; }
    public bool IsProceed { get; }
}

public sealed class EventV1Observation : IRoomFlowReadValue
{
    private readonly IReadOnlyList<EventV1Candidate> _candidates;
    private readonly IReadOnlyList<string> _legalActions;

    internal EventV1Observation(
        string sessionNonce,
        string status,
        string phase,
        string decisionId,
        IReadOnlyList<EventV1Candidate> candidates,
        IReadOnlyList<string> legalActions)
    {
        Version = EventV1Constants.Version;
        FlowKind = EventV1Constants.FlowKind;
        SessionNonce = sessionNonce;
        Status = status;
        Phase = phase;
        DecisionId = decisionId;
        _candidates = Copy(candidates);
        _legalActions = Copy(legalActions);
    }

    public string Version { get; }
    public string FlowKind { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal => RoomFlowLimits.ParentOrdinal;
    public string Status { get; }
    public string Phase { get; }
    public string DecisionId { get; }
    public IReadOnlyList<EventV1Candidate> Candidates => _candidates;
    public IReadOnlyList<string> LegalActions => _legalActions;

    internal static EventV1Observation Inactive(string nonce, string status, string phase) =>
        new(nonce, status, phase, string.Empty,
            Array.Empty<EventV1Candidate>(), Array.Empty<string>());

    private static IReadOnlyList<EventV1Candidate> Copy(
        IReadOnlyList<EventV1Candidate> source)
    {
        var copy = new EventV1Candidate[source.Count];
        for (int index = 0; index < source.Count; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }

    private static IReadOnlyList<string> Copy(IReadOnlyList<string> source)
    {
        var copy = new string[source.Count];
        for (int index = 0; index < source.Count; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }
}

public sealed class EventV1ResolvedResult : IRoomFlowReadValue
{
    internal EventV1ResolvedResult(
        string sessionNonce,
        string decisionId,
        string actionId)
    {
        Version = EventV1Constants.Version;
        FlowKind = EventV1Constants.FlowKind;
        SessionNonce = sessionNonce;
        DecisionId = decisionId;
        ActionId = actionId;
    }

    public string Version { get; }
    public string FlowKind { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal => RoomFlowLimits.ParentOrdinal;
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Result => "map_handoff";
}

public enum EventV1SurfaceStatus
{
    Missing,
    Parent,
    ItemChild,
    Unsupported,
}

public sealed class EventV1NativeCandidate
{
    public EventV1NativeCandidate(
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
        Action dispatch)
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
        Dispatch = dispatch;
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
    public Action Dispatch { get; }
}

public sealed class EventV1SurfaceCapture
{
    private readonly IReadOnlyList<EventV1NativeCandidate> _candidates;

    private EventV1SurfaceCapture(
        EventV1SurfaceStatus status,
        object? runIdentity,
        object? playerIdentity,
        object? roomIdentity,
        object? mapIdentity,
        bool eventFinished,
        bool mapOpen,
        bool travelEnabled,
        bool traveling,
        IReadOnlyList<EventV1NativeCandidate> candidates,
        object? itemChildIdentity,
        IItemV1NativeAdapter? itemChildAdapter)
    {
        Status = status;
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RoomIdentity = roomIdentity;
        MapIdentity = mapIdentity;
        EventFinished = eventFinished;
        MapOpen = mapOpen;
        TravelEnabled = travelEnabled;
        Traveling = traveling;
        var copy = new EventV1NativeCandidate[candidates.Count];
        for (int index = 0; index < copy.Length; index++) copy[index] = candidates[index];
        _candidates = Array.AsReadOnly(copy);
        ItemChildIdentity = itemChildIdentity;
        ItemChildAdapter = itemChildAdapter;
    }

    public EventV1SurfaceStatus Status { get; }
    public object? RunIdentity { get; }
    public object? PlayerIdentity { get; }
    public object? RoomIdentity { get; }
    public object? MapIdentity { get; }
    public bool EventFinished { get; }
    public bool MapOpen { get; }
    public bool TravelEnabled { get; }
    public bool Traveling { get; }
    public IReadOnlyList<EventV1NativeCandidate> Candidates => _candidates;
    public object? ItemChildIdentity { get; }
    public IItemV1NativeAdapter? ItemChildAdapter { get; }

    public static EventV1SurfaceCapture Missing() => Empty(EventV1SurfaceStatus.Missing);
    public static EventV1SurfaceCapture Unsupported() => Empty(EventV1SurfaceStatus.Unsupported);

    public static EventV1SurfaceCapture Parent(
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity,
        bool eventFinished,
        bool mapOpen,
        bool travelEnabled,
        bool traveling,
        IReadOnlyList<EventV1NativeCandidate> candidates) =>
        new(EventV1SurfaceStatus.Parent, runIdentity, playerIdentity, roomIdentity,
            mapIdentity, eventFinished, mapOpen, travelEnabled, traveling,
            candidates, null, null);

    public static EventV1SurfaceCapture ItemChild(
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity,
        object itemChildIdentity,
        IItemV1NativeAdapter itemChildAdapter) =>
        new(EventV1SurfaceStatus.ItemChild, runIdentity, playerIdentity, roomIdentity,
            mapIdentity, false, false, false, false,
            Array.Empty<EventV1NativeCandidate>(), itemChildIdentity, itemChildAdapter);

    private static EventV1SurfaceCapture Empty(EventV1SurfaceStatus status) =>
        new(status, null, null, null, null, false, false, false, false,
            Array.Empty<EventV1NativeCandidate>(), null, null);
}

public sealed class EventV1ExitProbe
{
    internal EventV1ExitProbe(
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

public sealed class EventV1ExitCapture
{
    public EventV1ExitCapture(
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

public interface IEventV1NativeAdapter
{
    EventV1SurfaceCapture CaptureSurface();
    EventV1ExitCapture CaptureExit(EventV1ExitProbe pending);
}
