using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.GenericEventV7;

public static class GenericEventV7Limits
{
    public const string Version = "generic_event_v9";
    public const int MaximumCandidates = 8;
    public const int MaximumParentActions = 12;
    public const int MaximumChildEpisodes = 4;
    public const int MaximumTotalActions = 52;
    public const int MaximumPendingReads = 256;
    public const int MaximumHostReads = 2048;
}

// Wire consumers receive public values only. Native descriptors and identities
// cannot be supplied through this interface.
public interface IGenericEventV7Session : IDisposable
{
    GenericEventV7Observation Read();
    GenericEventV7ApplyResult Apply(string? decisionId, string? actionId);
    GenericEventV7ChildRead ReadChild(
        string? parentDecisionId, string? parentActionId, int childOrdinal);
    GenericEventV7ChildApply ApplyChild(
        string? parentDecisionId, string? parentActionId, int childOrdinal,
        string? decisionId, string? actionId);
}

public sealed class GenericEventV7Candidate
{
    public GenericEventV7Candidate(int index, string actionId, string stableId,
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

public sealed class GenericEventV7Child
{
    public GenericEventV7Child(int ordinal, string parentDecisionId,
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
        Kind = "card_selection";
        ContractVersion = GenericEventV7Families.ContractVersion(operation,maxSelect,minSelect);
    }
    public GenericEventV7Child(int ordinal, string parentDecisionId, string parentActionId, int offerCount, bool cardReward=false, bool mixed=false) {
        Ordinal=ordinal; ParentDecisionId=parentDecisionId; ParentActionId=parentActionId;
        Kind=cardReward?"card_reward":"item"; ContractVersion=mixed?"mixed_reward_set_v1":cardReward?(offerCount==1?"card_reward_v1":"card_reward_set_v1"):offerCount==1?"item_v1":"item_set_v1"; OfferCount=offerCount;
        Operation=""; CommitMode="";
    }
    public GenericEventV7Child(int ordinal,string decision,string action,int count,string offerVersion):this(ordinal,decision,action,count,true) {
        if(offerVersion is not ("card_offer_v1" or "card_offer_v2" or "bundle_offer_v1")||offerVersion=="card_offer_v2"&&count>3)throw new ArgumentException("Unknown offer version.");
        Kind="card_offer";ContractVersion=offerVersion;
    }
    public GenericEventV7Child(int ordinal,string decision,string action,GenericEventV7ResultsAdmission results) {
        if(!results.IsSupported)throw new ArgumentException("Results bounds.");
        Ordinal=ordinal;ParentDecisionId=decision;ParentActionId=action;Kind="card_results";ContractVersion="card_results_v1";OfferCount=results.CardCount;Operation="";CommitMode="";
    }
    public string Kind { get; }
    public string ContractVersion { get; }
    public int OfferCount { get; }
    public int Ordinal { get; }
    public string ParentDecisionId { get; }
    public string ParentActionId { get; }
    public string Operation { get; }
    public int MinSelect { get; }
    public int MaxSelect { get; }
    public string CommitMode { get; }
    public int DomainCount { get; }
}

public sealed class GenericEventV7PriorResult
{
    public GenericEventV7PriorResult(string decisionId, string actionId, string result)
        => (DecisionId, ActionId, Result) = (decisionId, actionId, result);
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Result { get; }
}

public sealed class GenericEventV7Observation
{
    public GenericEventV7Observation(string sessionNonce, string status, string phase,
        string decisionId, IReadOnlyList<GenericEventV7Candidate> candidates,
        IReadOnlyList<string> legalActions, GenericEventV7Child? child,
        IReadOnlyList<GenericEventV7PriorResult> priorResults,
        int parentAttempted, int parentAccepted, int parentReconciled,
        int childEpisodes, int childAttempted, int childAccepted,
        int childReconciled, string effects, int completedCardChildren = 0, int completedItemChildren = 0)
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
        CompletedCardChildren = completedCardChildren;
        CompletedItemChildren = completedItemChildren;
    }
    public string Version => GenericEventV7Limits.Version;
    public string SessionNonce { get; }
    public string Status { get; }
    public string Phase { get; }
    public string DecisionId { get; }
    public IReadOnlyList<GenericEventV7Candidate> Candidates { get; }
    public IReadOnlyList<string> LegalActions { get; }
    public GenericEventV7Child? Child { get; }
    public IReadOnlyList<GenericEventV7PriorResult> PriorResults { get; }
    public int ParentAttempted { get; }
    public int ParentAccepted { get; }
    public int ParentReconciled { get; }
    public int ChildEpisodes { get; }
    public int ChildAttempted { get; }
    public int ChildAccepted { get; }
    public int ChildReconciled { get; }
    public int TotalAttempted => ParentAttempted + ChildAttempted;
    public string Effects { get; }
    public int CompletedCardChildren { get; }
    public int CompletedItemChildren { get; }

    private static IReadOnlyList<T> Copy<T>(IReadOnlyList<T> source)
    {
        var result = new T[source.Count];
        for (int i = 0; i < result.Length; i++) result[i] = source[i];
        return Array.AsReadOnly(result);
    }
}

public sealed class GenericEventV7ApplyResult
{
    public GenericEventV7ApplyResult(string sessionNonce, string decisionId,
        string actionId, string outcome)
        => (SessionNonce, DecisionId, ActionId, Outcome) =
            (sessionNonce, decisionId, actionId, outcome);
    public string Version => GenericEventV7Limits.Version;
    public string SessionNonce { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Outcome { get; }
}
