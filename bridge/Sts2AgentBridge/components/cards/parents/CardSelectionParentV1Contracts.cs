using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Parents;

public static class CardSelectionParentV1Limits
{
    public const string Version = "card_selection_parent_v1";
    public const int ParentOrdinal = 1;
    public const int MaximumAcceptedActions = 2;
    public const int MaximumPendingReads = 256;
    public const int MaximumWitnessLength = 64;
    public const string BeginAction = "begin";
    public const string ProceedAction = "proceed";
    public const string CheeseGorgeStableKey =
        "ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE";
    public const string SmithStableKey = "SMITH";
}

public enum CardSelectionParentV1PolicyKind
{
    CheeseGorgeAddTwo = 1,
    RestSmithUpgradeOne = 2,
}

public enum CardSelectionParentV1Phase
{
    Initial = 1,
    Child = 2,
    After = 3,
    Exit = 4,
    Transient = 5,
}

public enum CardSelectionParentV1SurfaceStatus
{
    Missing = 1,
    Available = 2,
    Unsupported = 3,
}

public interface ICardSelectionParentV1ReadValue { }
public interface ICardSelectionParentV1ApplyValue { }

public interface ICardSelectionParentV1NativeAdapter : IDisposable
{
    CardSelectionParentV1SurfaceCapture CaptureSurface();
}

// A capture supplies this capability only for the exact foreground selector it
// reports. Create is claimed at most once after the parent begin receipt is
// accepted and the child capture has been revalidated.
public interface ICardSelectionParentV1ChildFactory
{
    ICardSelectionV1NativeAdapter Create(
        CardSelectionV1ParentContext context,
        object exactScreenIdentity);
}

public sealed class CardSelectionParentV1Policy
{
    public CardSelectionParentV1Policy(
        CardSelectionParentV1PolicyKind kind,
        CardSelectionV1ParentKind parentKind,
        string parentStableKey,
        int smithCount,
        CardSelectionV1Operation operation,
        int minSelect,
        int maxSelect,
        CardSelectionV1CommitMode commitMode,
        int expectedDomainCount)
    {
        Kind = kind;
        ParentKind = parentKind;
        ParentStableKey = parentStableKey;
        SmithCount = smithCount;
        Operation = operation;
        MinSelect = minSelect;
        MaxSelect = maxSelect;
        CommitMode = commitMode;
        ExpectedDomainCount = expectedDomainCount;
    }

    public CardSelectionParentV1PolicyKind Kind { get; }
    public CardSelectionV1ParentKind ParentKind { get; }
    public string ParentStableKey { get; }
    public int SmithCount { get; }
    public CardSelectionV1Operation Operation { get; }
    public int MinSelect { get; }
    public int MaxSelect { get; }
    public CardSelectionV1CommitMode CommitMode { get; }
    public int ExpectedDomainCount { get; }
}

public sealed class CardSelectionParentV1NativeControl
{
    public CardSelectionParentV1NativeControl(
        object identity,
        bool visible,
        bool enabled,
        Action dispatch)
    {
        Identity = identity;
        Visible = visible;
        Enabled = enabled;
        Dispatch = dispatch;
    }

    public object Identity { get; }
    public bool Visible { get; }
    public bool Enabled { get; }
    public Action Dispatch { get; }
}

public sealed class CardSelectionParentV1SurfaceCapture
{
    public CardSelectionParentV1SurfaceCapture(
        CardSelectionParentV1SurfaceStatus status,
        CardSelectionParentV1Phase phase,
        CardSelectionParentV1Policy policy,
        object? runIdentity,
        object? playerIdentity,
        object? roomIdentity,
        object? mapIdentity,
        object? parentOptionIdentity,
        object? parentControllerIdentity,
        string structuralWitness,
        bool noActiveOverlay,
        bool mapOpen,
        bool travelEnabled,
        bool traveling,
        bool eventFinished,
        bool eventProceedSingleton,
        bool restControlsRestored,
        bool effectCompletionObserved,
        object? screenIdentity,
        ICardSelectionParentV1ChildFactory? childFactory,
        CardSelectionParentV1NativeControl? beginControl,
        CardSelectionParentV1NativeControl? proceedControl)
    {
        Status = status;
        Phase = phase;
        Policy = policy;
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RoomIdentity = roomIdentity;
        MapIdentity = mapIdentity;
        ParentOptionIdentity = parentOptionIdentity;
        ParentControllerIdentity = parentControllerIdentity;
        StructuralWitness = structuralWitness;
        NoActiveOverlay = noActiveOverlay;
        MapOpen = mapOpen;
        TravelEnabled = travelEnabled;
        Traveling = traveling;
        EventFinished = eventFinished;
        EventProceedSingleton = eventProceedSingleton;
        RestControlsRestored = restControlsRestored;
        EffectCompletionObserved = effectCompletionObserved;
        ScreenIdentity = screenIdentity;
        ChildFactory = childFactory;
        BeginControl = beginControl;
        ProceedControl = proceedControl;
    }

    public CardSelectionParentV1SurfaceStatus Status { get; }
    public CardSelectionParentV1Phase Phase { get; }
    public CardSelectionParentV1Policy Policy { get; }
    public object? RunIdentity { get; }
    public object? PlayerIdentity { get; }
    public object? RoomIdentity { get; }
    public object? MapIdentity { get; }
    public object? ParentOptionIdentity { get; }
    public object? ParentControllerIdentity { get; }
    public string StructuralWitness { get; }
    public bool NoActiveOverlay { get; }
    public bool MapOpen { get; }
    public bool TravelEnabled { get; }
    public bool Traveling { get; }
    public bool EventFinished { get; }
    public bool EventProceedSingleton { get; }
    public bool RestControlsRestored { get; }
    public bool EffectCompletionObserved { get; }
    public object? ScreenIdentity { get; }
    public ICardSelectionParentV1ChildFactory? ChildFactory { get; }
    public CardSelectionParentV1NativeControl? BeginControl { get; }
    public CardSelectionParentV1NativeControl? ProceedControl { get; }
}

public sealed class CardSelectionParentV1Observation : ICardSelectionParentV1ReadValue
{
    private readonly ReadOnlyCollection<string> _legalActions;

    internal CardSelectionParentV1Observation(
        string sessionNonce,
        string status,
        string phase,
        string parentKind,
        string policy,
        string decisionId,
        IReadOnlyList<string> legalActions)
    {
        Version = CardSelectionParentV1Limits.Version;
        SessionNonce = sessionNonce;
        ParentOrdinal = CardSelectionParentV1Limits.ParentOrdinal;
        Status = status;
        Phase = phase;
        ParentKind = parentKind;
        Policy = policy;
        DecisionId = decisionId;
        var copy = new string[legalActions.Count];
        for (int index = 0; index < copy.Length; index++)
            copy[index] = legalActions[index];
        _legalActions = Array.AsReadOnly(copy);
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string Status { get; }
    public string Phase { get; }
    public string ParentKind { get; }
    public string Policy { get; }
    public string DecisionId { get; }
    public IReadOnlyList<string> LegalActions => _legalActions;

    internal static CardSelectionParentV1Observation Fixed(
        string nonce,
        string status,
        string phase) =>
        new(nonce, status, phase, string.Empty, string.Empty, string.Empty,
            Array.Empty<string>());
}

public sealed class CardSelectionParentV1ResolvedResult : ICardSelectionParentV1ReadValue
{
    internal CardSelectionParentV1ResolvedResult(
        string sessionNonce,
        string beginDecisionId,
        string beginActionId,
        string proceedDecisionId,
        string proceedActionId)
    {
        Version = CardSelectionParentV1Limits.Version;
        SessionNonce = sessionNonce;
        ParentOrdinal = CardSelectionParentV1Limits.ParentOrdinal;
        BeginDecisionId = beginDecisionId;
        BeginActionId = beginActionId;
        ProceedDecisionId = proceedDecisionId;
        ProceedActionId = proceedActionId;
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string Status => "resolved";
    public string Result => "map_handoff";
    public string BeginDecisionId { get; }
    public string BeginActionId { get; }
    public string ProceedDecisionId { get; }
    public string ProceedActionId { get; }
}

public sealed class CardSelectionParentV1DispatchReceipt : ICardSelectionParentV1ApplyValue
{
    internal CardSelectionParentV1DispatchReceipt(
        string sessionNonce,
        string decisionId,
        string actionId)
    {
        Version = CardSelectionParentV1Limits.Version;
        SessionNonce = sessionNonce;
        ParentOrdinal = CardSelectionParentV1Limits.ParentOrdinal;
        DecisionId = decisionId;
        ActionId = actionId;
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Outcome => "accepted";
}

public sealed class CardSelectionParentV1ApplyFailure : ICardSelectionParentV1ApplyValue
{
    internal CardSelectionParentV1ApplyFailure(string sessionNonce, string outcome)
    {
        Version = CardSelectionParentV1Limits.Version;
        SessionNonce = sessionNonce;
        ParentOrdinal = CardSelectionParentV1Limits.ParentOrdinal;
        Outcome = outcome;
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string Outcome { get; }
}

public sealed class CardSelectionParentV1ChildUnavailable : ICardSelectionV1ReadValue
{
    internal CardSelectionParentV1ChildUnavailable(string sessionNonce)
    {
        Version = CardSelectionV1Limits.Version;
        SessionNonce = sessionNonce;
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public string Status => "unsupported";
    public string Phase => "unsupported";
}

public sealed class CardSelectionParentV1ChildApplyFailure : ICardSelectionV1ApplyValue
{
    internal CardSelectionParentV1ChildApplyFailure(string sessionNonce, string outcome)
    {
        Version = CardSelectionV1Limits.Version;
        SessionNonce = sessionNonce;
        Outcome = outcome;
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public string Outcome { get; }
}
