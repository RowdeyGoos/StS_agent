using System;

namespace Sts2AgentBridge.Core.Public;

public static class PublicProcessActionBudget
{
    public const int MaximumFloors = 3;

    public static int MaximumAcceptedActions(int maximumRewardAcceptedActions)
    {
        if (maximumRewardAcceptedActions < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumRewardAcceptedActions));
        }

        return checked(
            PublicCombatActionBudget.MaximumAcceptedActions +
            maximumRewardAcceptedActions +
            PublicMapActionBudget.MaximumAcceptedActions +
            PublicRoomActionBudget.MaximumAcceptedActions);
    }
}

public static class PublicCombatActionBudget
{
    public const int MaximumAcceptedActionsPerCombat = 48;
    public const int MaximumAcceptedActions = 144;
}

public readonly record struct PublicCombatActionRequest(
    string DecisionId,
    string ActionId,
    int HandIndex,
    int TargetIndex)
{
    public bool IsEndTurn => string.Equals(ActionId, "end_turn", StringComparison.Ordinal);

    public static bool TryCreate(
        string decisionId,
        string actionId,
        out PublicCombatActionRequest request)
    {
        request = default;
        if (!PublicCombatDecisionIdentity.IsCanonical(decisionId) || actionId is null)
        {
            return false;
        }

        if (string.Equals(actionId, "end_turn", StringComparison.Ordinal))
        {
            request = new PublicCombatActionRequest(decisionId, actionId, -1, -1);
            return true;
        }

        if (!actionId.StartsWith("play:", StringComparison.Ordinal))
        {
            return false;
        }

        ReadOnlySpan<char> suffix = actionId.AsSpan(5);
        if (suffix.Length is not 1 and not 3 || suffix[0] < '0' || suffix[0] > '9')
        {
            return false;
        }

        int handIndex = suffix[0] - '0';
        int targetIndex = -1;
        if (suffix.Length == 3)
        {
            if (suffix[1] != ':' || suffix[2] < '0' || suffix[2] > '5')
            {
                return false;
            }
            targetIndex = suffix[2] - '0';
        }

        request = new PublicCombatActionRequest(
            decisionId,
            actionId,
            handIndex,
            targetIndex);
        return true;
    }
}

public enum PublicCombatActionApplyOutcome
{
    Accepted = 1,
    StaleDecision = 2,
    InvalidAction = 3,
    AlreadyApplied = 4,
    ActionLimitReached = 5,
    BackendFault = 6,
}

public readonly record struct PublicCombatActionApplyResult(
    PublicCombatActionApplyOutcome Outcome,
    string DecisionId,
    string ActionId)
{
    public bool IsBackendFault => Outcome == PublicCombatActionApplyOutcome.BackendFault;

    public static PublicCombatActionApplyResult FromRequest(
        PublicCombatActionApplyOutcome outcome,
        PublicCombatActionRequest request)
    {
        return new PublicCombatActionApplyResult(outcome, request.DecisionId, request.ActionId);
    }

    public static PublicCombatActionApplyResult BackendFault() =>
        new(PublicCombatActionApplyOutcome.BackendFault, string.Empty, string.Empty);
}

public interface IPublicCombatActionApplier
{
    PublicCombatActionApplyResult Apply(PublicCombatActionRequest request);
}

public interface IPublicCombatActionService
{
    PublicCombatActionApplyResult Apply(PublicCombatActionRequest request);
}

public sealed class PublicCombatActionService : IPublicCombatActionService
{
    private readonly IPublicCombatActionApplier _applier;

    public PublicCombatActionService(IPublicCombatActionApplier applier)
    {
        _applier = applier ?? throw new ArgumentNullException(nameof(applier));
    }

    public PublicCombatActionApplyResult Apply(PublicCombatActionRequest request)
    {
        try
        {
            return _applier.Apply(request);
        }
        catch (Exception)
        {
            return PublicCombatActionApplyResult.BackendFault();
        }
    }
}
