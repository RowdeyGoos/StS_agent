using System;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Tests.Public;

internal static class RewardInteractionTestSuite
{
    public static void Run()
    {
        ActionGrammarIsExactAndBounded();
        IdentityBindsDecisionRevision();
        SessionAndProcessBudgetsAreBounded();
    }

    private static void ActionGrammarIsExactAndBounded()
    {
        string decisionId = new('a', PublicRewardDecisionIdentity.EncodedCharacterCount);
        AssertAction(decisionId, "claim:7", PublicRewardActionKind.ClaimGold, 7, -1);
        AssertAction(decisionId, "open:0", PublicRewardActionKind.OpenCard, 0, -1);
        AssertAction(decisionId, "choose:4", PublicRewardActionKind.ChooseCard, -1, 4);
        AssertAction(decisionId, "skip_card", PublicRewardActionKind.SkipCard, -1, -1);
        AssertAction(decisionId, "proceed", PublicRewardActionKind.Proceed, -1, -1);

        TestAssert.False(
            PublicRewardActionRequest.TryCreate(decisionId, "claim:8", out _),
            "reward slot above seven rejected");
        TestAssert.False(
            PublicRewardActionRequest.TryCreate(decisionId, "choose:5", out _),
            "card slot above four rejected");
        TestAssert.False(
            PublicRewardActionRequest.TryCreate(decisionId, "claim:00", out _),
            "multi-digit slot rejected");
        TestAssert.False(
            PublicRewardActionRequest.TryCreate(decisionId, "Proceed", out _),
            "noncanonical action casing rejected");
    }

    private static void IdentityBindsDecisionRevision()
    {
        var snapshot = new PublicRewardDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "rewards",
            new PublicRewardPlayer(80, 80, 99, 10),
            Array.Empty<PublicRewardItem>(),
            new[] { PublicRewardActionRequest.ProceedActionId },
            0);
        string first = PublicRewardDecisionIdentity.Compute(snapshot);
        string second = PublicRewardDecisionIdentity.Compute(
            snapshot with { DecisionRevision = 1 });
        TestAssert.False(
            string.Equals(first, second, StringComparison.Ordinal),
            "reward revision changes decision identity");
    }

    private static void SessionAndProcessBudgetsAreBounded()
    {
        TestAssert.Equal(
            17,
            PublicRewardActionBudget.MaximumAcceptedActionsPerSession,
            "reward session action cap");
        TestAssert.Equal(
            3,
            PublicRewardActionBudget.MaximumRewardSessionsPerProcess,
            "reward process session cap");
        TestAssert.Equal(
            51,
            PublicRewardActionBudget.MaximumAcceptedActionsPerProcess,
            "reward process action cap");

        var session = new PinnedPublicRewardInteractionSession();
        string lastDecisionId = string.Empty;
        for (int sessionIndex = 0;
             sessionIndex < PublicRewardActionBudget.MaximumRewardSessionsPerProcess;
             sessionIndex++)
        {
            TestAssert.True(session.BeginSessionForTest(), "bounded reward session begins");
            for (int actionIndex = 0;
                 actionIndex < PublicRewardActionBudget.MaximumAcceptedActionsPerSession;
                 actionIndex++)
            {
                string decisionId = CanonicalDecisionId(sessionIndex, actionIndex);
                session.SeedDecisionForTest(decisionId);
                var pending = new PinnedPublicRewardPendingMutation(
                    PublicRewardActionKind.ClaimGold,
                    default);
                TestAssert.Equal<PublicRewardActionApplyOutcome?>(
                    null,
                    session.Begin(decisionId, pending),
                    "in-budget reward action accepted");
                session.ResolveClaim(default);
                lastDecisionId = decisionId;
            }

            TestAssert.Equal(
                PublicRewardActionBudget.MaximumAcceptedActionsPerSession,
                session.AcceptedDecisionCountForTest,
                "replay IDs are bounded to one reward session");
            TestAssert.Equal<PublicRewardActionApplyOutcome?>(
                PublicRewardActionApplyOutcome.AlreadyApplied,
                session.ReservationFailure(lastDecisionId),
                "duplicate rejection precedes budget rejection");
            TestAssert.Equal<PublicRewardActionApplyOutcome?>(
                PublicRewardActionApplyOutcome.ActionLimitReached,
                session.ReservationFailure(CanonicalDecisionId(sessionIndex, 63)),
                "new action is rejected at session cap");
        }

        TestAssert.False(session.BeginSessionForTest(), "fourth reward session rejected");
        TestAssert.Equal<PublicRewardActionApplyOutcome?>(
            PublicRewardActionApplyOutcome.AlreadyApplied,
            session.ReservationFailure(lastDecisionId),
            "duplicate rejection precedes process-cap rejection");
        TestAssert.Equal<PublicRewardActionApplyOutcome?>(
            PublicRewardActionApplyOutcome.ActionLimitReached,
            session.ReservationFailure(CanonicalDecisionId(3, 0)),
            "new action rejected at process cap");
    }

    private static void AssertAction(
        string decisionId,
        string actionId,
        PublicRewardActionKind kind,
        int rewardSlot,
        int cardSlot)
    {
        TestAssert.True(
            PublicRewardActionRequest.TryCreate(
                decisionId,
                actionId,
                out PublicRewardActionRequest request),
            actionId + " parses");
        TestAssert.Equal(kind, request.Kind, actionId + " kind");
        TestAssert.Equal(rewardSlot, request.RewardSlot, actionId + " reward slot");
        TestAssert.Equal(cardSlot, request.CardSlot, actionId + " card slot");
    }

    private static string CanonicalDecisionId(int sessionIndex, int actionIndex)
    {
        string suffix = sessionIndex.ToString("x1") + actionIndex.ToString("x2");
        return new string('0', PublicRewardDecisionIdentity.EncodedCharacterCount - suffix.Length) + suffix;
    }
}
