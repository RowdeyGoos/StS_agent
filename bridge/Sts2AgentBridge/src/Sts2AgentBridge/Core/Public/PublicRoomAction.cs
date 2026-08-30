using System;

namespace Sts2AgentBridge.Core.Public;

public static class PublicRoomActionBudget
{
    public const int MaximumAcceptedActions = 12;
}

public readonly record struct PublicRoomActionRequest(
    string DecisionId,
    string ActionId,
    int CandidateIndex)
{
    public const string ProceedActionId = "proceed";

    public static bool TryCreate(
        string decisionId,
        string actionId,
        out PublicRoomActionRequest request)
    {
        request = default;
        if (!PublicRoomDecisionIdentity.IsCanonical(decisionId) || actionId is null)
        {
            return false;
        }

        if (string.Equals(actionId, ProceedActionId, StringComparison.Ordinal))
        {
            request = new PublicRoomActionRequest(decisionId, actionId, -1);
            return true;
        }

        if (actionId.Length != 8 ||
            !actionId.AsSpan(0, 7).SequenceEqual("choose:"))
        {
            return false;
        }

        int candidateIndex = actionId[7] - '0';
        if (candidateIndex is < 0 or >= PublicRoomLimits.MaximumCandidates)
        {
            return false;
        }

        request = new PublicRoomActionRequest(decisionId, actionId, candidateIndex);
        return true;
    }

    public static string ChoiceActionIdFor(int candidateIndex)
    {
        if (candidateIndex is < 0 or >= PublicRoomLimits.MaximumCandidates)
        {
            throw new ArgumentOutOfRangeException(nameof(candidateIndex));
        }
        return "choose:" + (char)('0' + candidateIndex);
    }
}

public enum PublicRoomActionApplyOutcome
{
    Accepted = 1,
    StaleDecision = 2,
    InvalidAction = 3,
    AlreadyApplied = 4,
    ActionLimitReached = 5,
    BackendFault = 6,
}

public readonly record struct PublicRoomActionApplyResult(
    PublicRoomActionApplyOutcome Outcome,
    string DecisionId,
    string ActionId)
{
    public bool IsBackendFault => Outcome == PublicRoomActionApplyOutcome.BackendFault;

    public static PublicRoomActionApplyResult FromRequest(
        PublicRoomActionApplyOutcome outcome,
        PublicRoomActionRequest request) =>
        new(outcome, request.DecisionId, request.ActionId);

    public static PublicRoomActionApplyResult BackendFault() =>
        new(PublicRoomActionApplyOutcome.BackendFault, string.Empty, string.Empty);
}

public interface IPublicRoomActionApplier
{
    PublicRoomActionApplyResult Apply(PublicRoomActionRequest request);
}

public interface IPublicRoomActionService
{
    PublicRoomActionApplyResult Apply(PublicRoomActionRequest request);
}

public sealed class PublicRoomActionService : IPublicRoomActionService
{
    private readonly IPublicRoomActionApplier _applier;

    public PublicRoomActionService(IPublicRoomActionApplier applier)
    {
        _applier = applier ?? throw new ArgumentNullException(nameof(applier));
    }

    public PublicRoomActionApplyResult Apply(PublicRoomActionRequest request)
    {
        try
        {
            return _applier.Apply(request);
        }
        catch (Exception)
        {
            return PublicRoomActionApplyResult.BackendFault();
        }
    }
}
