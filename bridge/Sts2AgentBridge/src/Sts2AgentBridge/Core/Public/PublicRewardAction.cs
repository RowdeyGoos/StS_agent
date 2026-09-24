using System;
using System.Globalization;

namespace Sts2AgentBridge.Core.Public;

public static class PublicRewardActionBudget
{
    public const int MaximumAcceptedActionsPerSession = 17;
    public const int MaximumExpandedRewards = 32;
    public const int MaximumExpandedActions = 2 * MaximumExpandedRewards + 1;
    public const int MaximumExpandedResponseBytes = 65536;
    public const int MaximumRewardSessionsPerProcess = 3;
    public const int MaximumAcceptedActionsPerProcess =
        MaximumAcceptedActionsPerSession * MaximumRewardSessionsPerProcess;

    public const int MaximumAcceptedActions = MaximumAcceptedActionsPerSession;
}

public enum PublicRewardActionKind
{
    ClaimGold = 1,
    OpenCard = 2,
    ChooseCard = 3,
    SkipCard = 4,
    Proceed = 5,
    ClaimSpecialCard = 6,
    CollectItem = 7,
    DiscardPotion = 8,
}

public readonly record struct PublicRewardActionRequest(
    string DecisionId,
    string ActionId,
    PublicRewardActionKind Kind,
    int RewardSlot,
    int CardSlot,
    int PotionSlot = -1)
{
    // Preserved until all shared protocol fixtures have migrated. It is never
    // advertised by the granular reward reader.
    public const string SkipRewardsActionId = "skip_rewards";
    public const string SkipCardActionId = "skip_card";
    public const string ProceedActionId = "proceed";

    public static bool TryCreate(
        string decisionId,
        string actionId,
        out PublicRewardActionRequest request)
    {
        request = default;
        if (!PublicRewardDecisionIdentity.IsCanonical(decisionId) || actionId is null)
        {
            return false;
        }

        if (string.Equals(actionId, SkipCardActionId, StringComparison.Ordinal))
        {
            request = new PublicRewardActionRequest(
                decisionId,
                actionId,
                PublicRewardActionKind.SkipCard,
                -1,
                -1);
            return true;
        }
        if (string.Equals(actionId, ProceedActionId, StringComparison.Ordinal) ||
            string.Equals(actionId, SkipRewardsActionId, StringComparison.Ordinal))
        {
            request = new PublicRewardActionRequest(
                decisionId,
                actionId,
                PublicRewardActionKind.Proceed,
                -1,
                -1);
            return true;
        }
        if (TryParseSlot(actionId, "claim:", MaximumRewardSlot, out int rewardSlot))
        {
            request = new PublicRewardActionRequest(
                decisionId,
                actionId,
                PublicRewardActionKind.ClaimGold,
                rewardSlot,
                -1);
            return true;
        }
        if (TryParseSlot(actionId, "discard:", 7, out int potionSlot))
        {
            request = new(decisionId, actionId, PublicRewardActionKind.DiscardPotion, -1, -1, potionSlot);
            return true;
        }
        if (TryParseSlot(actionId, "collect:", MaximumRewardSlot, out rewardSlot))
        {
            request = new(decisionId, actionId, PublicRewardActionKind.CollectItem, rewardSlot, -1);
            return true;
        }
        if (TryParseSlot(actionId, "take:", MaximumRewardSlot, out rewardSlot))
        {
            request = new(decisionId, actionId, PublicRewardActionKind.ClaimSpecialCard, rewardSlot, -1);
            return true;
        }
        if (TryParseSlot(actionId, "open:", MaximumRewardSlot, out rewardSlot))
        {
            request = new PublicRewardActionRequest(
                decisionId,
                actionId,
                PublicRewardActionKind.OpenCard,
                rewardSlot,
                -1);
            return true;
        }
        if (TryParseSlot(actionId, "choose:", 4, out int cardSlot))
        {
            request = new PublicRewardActionRequest(
                decisionId,
                actionId,
                PublicRewardActionKind.ChooseCard,
                -1,
                cardSlot);
            return true;
        }

        return false;
    }

    private const int MaximumRewardSlot = PublicRewardActionBudget.MaximumExpandedRewards - 1;

    public static string ClaimGoldActionIdFor(int rewardSlot) =>
        ActionIdFor("claim:", rewardSlot, MaximumRewardSlot, nameof(rewardSlot));

    public static string CollectItemActionIdFor(int rewardSlot) =>
        ActionIdFor("collect:", rewardSlot, MaximumRewardSlot, nameof(rewardSlot));

    public static string ClaimSpecialCardActionIdFor(int rewardSlot) =>
        ActionIdFor("take:", rewardSlot, MaximumRewardSlot, nameof(rewardSlot));

    public static string OpenCardActionIdFor(int rewardSlot) =>
        ActionIdFor("open:", rewardSlot, MaximumRewardSlot, nameof(rewardSlot));

    public static string ChooseCardActionIdFor(int cardSlot) =>
        ActionIdFor("choose:", cardSlot, 4, nameof(cardSlot));

    private static bool TryParseSlot(
        string actionId,
        string prefix,
        int maximumSlot,
        out int slot)
    {
        slot = -1;
        if (!actionId.StartsWith(prefix, StringComparison.Ordinal))
        {
            return false;
        }

        var digits = actionId.AsSpan(prefix.Length);
        return digits.Length is >= 1 and <= 2 && (digits.Length == 1 || digits[0] != '0') &&
            int.TryParse(digits, NumberStyles.None, CultureInfo.InvariantCulture, out slot) &&
            slot >= 0 && slot <= maximumSlot;
    }

    private static string ActionIdFor(
        string prefix,
        int slot,
        int maximumSlot,
        string parameterName)
    {
        if (slot < 0 || slot > maximumSlot)
        {
            throw new ArgumentOutOfRangeException(parameterName);
        }
        return prefix + slot.ToString(CultureInfo.InvariantCulture);
    }
}

public enum PublicRewardActionApplyOutcome
{
    Accepted = 1,
    StaleDecision = 2,
    InvalidAction = 3,
    AlreadyApplied = 4,
    ActionLimitReached = 5,
    BackendFault = 6,
}

public readonly record struct PublicRewardActionApplyResult(
    PublicRewardActionApplyOutcome Outcome,
    string DecisionId,
    string ActionId)
{
    public bool IsBackendFault => Outcome == PublicRewardActionApplyOutcome.BackendFault;

    public static PublicRewardActionApplyResult FromRequest(
        PublicRewardActionApplyOutcome outcome,
        PublicRewardActionRequest request) =>
        new(outcome, request.DecisionId, request.ActionId);

    public static PublicRewardActionApplyResult BackendFault() =>
        new(PublicRewardActionApplyOutcome.BackendFault, string.Empty, string.Empty);
}

public interface IPublicRewardActionApplier
{
    PublicRewardActionApplyResult Apply(PublicRewardActionRequest request);
}

public interface IPublicRewardActionService
{
    PublicRewardActionApplyResult Apply(PublicRewardActionRequest request);
}

public sealed class PublicRewardActionService : IPublicRewardActionService
{
    private readonly IPublicRewardActionApplier _applier;

    public PublicRewardActionService(IPublicRewardActionApplier applier)
    {
        _applier = applier ?? throw new ArgumentNullException(nameof(applier));
    }

    public PublicRewardActionApplyResult Apply(PublicRewardActionRequest request)
    {
        try
        {
            return _applier.Apply(request);
        }
        catch (Exception)
        {
            return PublicRewardActionApplyResult.BackendFault();
        }
    }
}
