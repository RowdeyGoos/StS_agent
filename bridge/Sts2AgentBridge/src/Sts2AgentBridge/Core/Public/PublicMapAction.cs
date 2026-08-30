using System;

namespace Sts2AgentBridge.Core.Public;

public static class PublicMapActionBudget
{
    public const int MaximumAcceptedActions = 3;
}

public readonly record struct PublicMapActionRequest(
    string DecisionId,
    string ActionId,
    int CandidateIndex)
{
    public static bool TryCreate(
        string decisionId,
        string actionId,
        out PublicMapActionRequest request)
    {
        request = default;
        if (!PublicMapDecisionIdentity.IsCanonical(decisionId) ||
            actionId is null || actionId.Length != 8 ||
            !actionId.AsSpan(0, 7).SequenceEqual("select:"))
        {
            return false;
        }

        int candidateIndex = actionId[7] - '0';
        if (candidateIndex is < 0 or > 7)
        {
            return false;
        }

        request = new PublicMapActionRequest(decisionId, actionId, candidateIndex);
        return true;
    }

    public static string ActionIdFor(int candidateIndex)
    {
        if (candidateIndex is < 0 or > 7)
        {
            throw new ArgumentOutOfRangeException(nameof(candidateIndex));
        }
        return "select:" + (char)('0' + candidateIndex);
    }
}

public enum PublicMapActionApplyOutcome
{
    Accepted = 1,
    StaleDecision = 2,
    InvalidAction = 3,
    AlreadyApplied = 4,
    ActionLimitReached = 5,
    BackendFault = 6,
}

public readonly record struct PublicMapActionApplyResult(
    PublicMapActionApplyOutcome Outcome,
    string DecisionId,
    string ActionId)
{
    public bool IsBackendFault => Outcome == PublicMapActionApplyOutcome.BackendFault;

    public static PublicMapActionApplyResult FromRequest(
        PublicMapActionApplyOutcome outcome,
        PublicMapActionRequest request) =>
        new(outcome, request.DecisionId, request.ActionId);

    public static PublicMapActionApplyResult BackendFault() =>
        new(PublicMapActionApplyOutcome.BackendFault, string.Empty, string.Empty);
}

public interface IPublicMapActionApplier
{
    PublicMapActionApplyResult Apply(PublicMapActionRequest request);
}

public interface IPublicMapActionService
{
    PublicMapActionApplyResult Apply(PublicMapActionRequest request);
}

public sealed class PublicMapActionService : IPublicMapActionService
{
    private readonly IPublicMapActionApplier _applier;

    public PublicMapActionService(IPublicMapActionApplier applier)
    {
        _applier = applier ?? throw new ArgumentNullException(nameof(applier));
    }

    public PublicMapActionApplyResult Apply(PublicMapActionRequest request)
    {
        try
        {
            return _applier.Apply(request);
        }
        catch (Exception)
        {
            return PublicMapActionApplyResult.BackendFault();
        }
    }
}
