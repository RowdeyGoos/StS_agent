using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.GenericEventV3;

public static class GenericEventV3Limits
{
    public const string Version = "generic_event_v3";
    public const int MaximumCandidates = 8;
    public const int MaximumParentActions = 12;
    public const int MaximumChildEpisodes = 4;
    public const int MaximumTotalActions = 52;
    public const int MaximumPendingReads = 256;
    public const int MaximumHostReads = 2048;
}

// Wire consumers receive public values only. Native descriptors and identities
// cannot be supplied through this interface.
public interface IGenericEventV3Session : IDisposable
{
    GenericEventV3Observation Read();
    GenericEventV3ApplyResult Apply(string? decisionId, string? actionId);
    ICardSelectionV1ReadValue ReadChild(
        string? parentDecisionId, string? parentActionId, int childOrdinal);
    ICardSelectionV1ApplyValue ApplyChild(
        string? parentDecisionId, string? parentActionId, int childOrdinal,
        string? decisionId, string? actionId);
}

public sealed class GenericEventV3Candidate
{
    public GenericEventV3Candidate(int index, string actionId, string stableId,
        string renderedText, bool enabled, bool isDangerous, bool isProceed)
    {
        Index = index;
        ActionId = actionId;
        StableId = stableId;
        RenderedText = renderedText;
        Enabled = enabled;
        IsDangerous = isDangerous;
        IsProceed = isProceed;
    }
    public int Index { get; }
    public string ActionId { get; }
    public string StableId { get; }
    public string RenderedText { get; }
    public bool Enabled { get; }
    public bool IsDangerous { get; }
    public bool IsProceed { get; }
    public string Discovery => IsProceed ? "none" : "deferred";
}

public sealed class GenericEventV3Child
{
    public GenericEventV3Child(int ordinal, string parentDecisionId,
        string parentActionId, string operation, int minSelect, int maxSelect,
        string commitMode, int domainCount)
    {
        Ordinal = ordinal;
        ParentDecisionId = parentDecisionId;
        ParentActionId = parentActionId;
        Operation = operation;
        MinSelect = minSelect;
        MaxSelect = maxSelect;
        CommitMode = commitMode;
        DomainCount = domainCount;
    }
    public int Ordinal { get; }
    public string ParentDecisionId { get; }
    public string ParentActionId { get; }
    public string Operation { get; }
    public int MinSelect { get; }
    public int MaxSelect { get; }
    public string CommitMode { get; }
    public int DomainCount { get; }
}

public sealed class GenericEventV3PriorResult
{
    public GenericEventV3PriorResult(string decisionId, string actionId, string result)
        => (DecisionId, ActionId, Result) = (decisionId, actionId, result);
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Result { get; }
}

public sealed class GenericEventV3Observation
{
    public GenericEventV3Observation(string sessionNonce, string status, string phase,
        string decisionId, IReadOnlyList<GenericEventV3Candidate> candidates,
        IReadOnlyList<string> legalActions, GenericEventV3Child? child,
        IReadOnlyList<GenericEventV3PriorResult> priorResults,
        int parentAttempted, int parentAccepted, int parentReconciled,
        int childEpisodes, int childAttempted, int childAccepted,
        int childReconciled, string effects)
    {
        SessionNonce = sessionNonce;
        Status = status;
        Phase = phase;
        DecisionId = decisionId;
        Candidates = Copy(candidates);
        LegalActions = Copy(legalActions);
        Child = child;
        PriorResults = Copy(priorResults);
        ParentAttempted = parentAttempted;
        ParentAccepted = parentAccepted;
        ParentReconciled = parentReconciled;
        ChildEpisodes = childEpisodes;
        ChildAttempted = childAttempted;
        ChildAccepted = childAccepted;
        ChildReconciled = childReconciled;
        Effects = effects;
    }
    public string Version => GenericEventV3Limits.Version;
    public string SessionNonce { get; }
    public string Status { get; }
    public string Phase { get; }
    public string DecisionId { get; }
    public IReadOnlyList<GenericEventV3Candidate> Candidates { get; }
    public IReadOnlyList<string> LegalActions { get; }
    public GenericEventV3Child? Child { get; }
    public IReadOnlyList<GenericEventV3PriorResult> PriorResults { get; }
    public int ParentAttempted { get; }
    public int ParentAccepted { get; }
    public int ParentReconciled { get; }
    public int ChildEpisodes { get; }
    public int ChildAttempted { get; }
    public int ChildAccepted { get; }
    public int ChildReconciled { get; }
    public int TotalAttempted => ParentAttempted + ChildAttempted;
    public string Effects { get; }

    private static IReadOnlyList<T> Copy<T>(IReadOnlyList<T> source)
    {
        var result = new T[source.Count];
        for (int i = 0; i < result.Length; i++) result[i] = source[i];
        return Array.AsReadOnly(result);
    }
}

public sealed class GenericEventV3ApplyResult
{
    public GenericEventV3ApplyResult(string sessionNonce, string decisionId,
        string actionId, string outcome)
        => (SessionNonce, DecisionId, ActionId, Outcome) =
            (sessionNonce, decisionId, actionId, outcome);
    public string Version => GenericEventV3Limits.Version;
    public string SessionNonce { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Outcome { get; }
}
