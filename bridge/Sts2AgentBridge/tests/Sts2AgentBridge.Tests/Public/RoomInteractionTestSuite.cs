using System;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Tests.Public;

internal static class RoomInteractionTestSuite
{
    public static void Run()
    {
        IdentityBindsRoomAndCandidateSafetyState();
        RequestGrammarAndBudgetAreBounded();
        ServicesPreserveResultsAndScrubFaults();
        StableIdsAreAsciiAndBounded();
    }

    private static void IdentityBindsRoomAndCandidateSafetyState()
    {
        PublicRoomDecisionSnapshot ready = ReadySnapshot();
        string first = PublicRoomDecisionIdentity.Compute(ready);
        string second = PublicRoomDecisionIdentity.Compute(ready);
        string nextRoom = PublicRoomDecisionIdentity.Compute(ready with { RoomOrdinal = 12 });
        var changedCandidate = ready.Candidates[0] with { Supported = false };
        string unsupportedCandidate = PublicRoomDecisionIdentity.Compute(
            ready with { Candidates = new[] { changedCandidate } });

        TestAssert.True(PublicRoomDecisionIdentity.IsCanonical(first), "room identity is canonical");
        TestAssert.Equal(first, second, "room identity is deterministic");
        TestAssert.False(string.Equals(first, nextRoom, StringComparison.Ordinal), "room identity binds ordinal");
        TestAssert.False(
            string.Equals(first, unsupportedCandidate, StringComparison.Ordinal),
            "room identity binds candidate support");
        TestAssert.Throws<ArgumentException>(
            () => PublicRoomDecisionIdentity.Compute(PublicRoomDecisionSnapshot.Waiting()),
            "waiting room decision has no identity");
    }

    private static void RequestGrammarAndBudgetAreBounded()
    {
        string decisionId = new string('a', PublicRoomDecisionIdentity.EncodedCharacterCount);
        TestAssert.Equal(12, PublicRoomActionBudget.MaximumAcceptedActions, "room action budget");
        TestAssert.True(
            PublicRoomActionRequest.TryCreate(decisionId, "choose:7", out PublicRoomActionRequest choice),
            "highest bounded choice parses");
        TestAssert.Equal(7, choice.CandidateIndex, "choice index parses");
        TestAssert.True(
            PublicRoomActionRequest.TryCreate(decisionId, "proceed", out PublicRoomActionRequest proceed),
            "proceed parses");
        TestAssert.Equal(-1, proceed.CandidateIndex, "proceed has no candidate index");
        TestAssert.False(
            PublicRoomActionRequest.TryCreate(decisionId, "choose:8", out _),
            "out-of-range choice rejected");
        TestAssert.False(
            PublicRoomActionRequest.TryCreate(decisionId.ToUpperInvariant(), "choose:0", out _),
            "noncanonical identity rejected");
        TestAssert.False(
            PublicRoomActionRequest.TryCreate(decisionId, "skip", out _),
            "unknown action rejected");
    }

    private static void ServicesPreserveResultsAndScrubFaults()
    {
        PublicRoomDecisionSnapshot snapshot = ReadySnapshot();
        var reader = new FixedRoomDecisionReader(snapshot);
        var decisionService = new PublicRoomDecisionService(reader);
        PublicRoomDecisionReadResult read = decisionService.Read();
        TestAssert.True(read.IsSuccess, "room decision service succeeds");
        TestAssert.Equal(snapshot, read.Snapshot, "room decision snapshot preserved");
        TestAssert.Equal(1, reader.ReadCount, "room reader invoked once");

        string decisionId = new string('0', PublicRoomDecisionIdentity.EncodedCharacterCount);
        _ = PublicRoomActionRequest.TryCreate(decisionId, "choose:0", out PublicRoomActionRequest request);
        var applier = new FixedRoomActionApplier(
            PublicRoomActionApplyResult.FromRequest(PublicRoomActionApplyOutcome.Accepted, request));
        var actionService = new PublicRoomActionService(applier);
        PublicRoomActionApplyResult accepted = actionService.Apply(request);
        TestAssert.Equal(PublicRoomActionApplyOutcome.Accepted, accepted.Outcome, "room action preserved");
        TestAssert.Equal(1, applier.ApplyCount, "room applier invoked once");

        const string sensitiveDetail = "fixture-token /private/fake/path room";
        var throwingDecision = new PublicRoomDecisionService(new ThrowingRoomDecisionReader(sensitiveDetail));
        TestAssert.False(throwingDecision.Read().IsSuccess, "throwing room reader becomes backend fault");
        var throwingAction = new PublicRoomActionService(new ThrowingRoomActionApplier(sensitiveDetail));
        PublicRoomActionApplyResult fault = throwingAction.Apply(request);
        TestAssert.True(fault.IsBackendFault, "throwing room applier becomes backend fault");
        TestAssert.False(
            fault.ToString().Contains(sensitiveDetail, StringComparison.Ordinal),
            "room backend fault carries no exception detail");
    }

    private static void StableIdsAreAsciiAndBounded()
    {
        TestAssert.True(PublicRoomDecisionIdentity.IsBoundedPublicId("HEAL"), "simple id accepted");
        TestAssert.True(PublicRoomDecisionIdentity.IsBoundedPublicId("INITIAL.OPTION_1"), "event key accepted");
        TestAssert.False(PublicRoomDecisionIdentity.IsBoundedPublicId(string.Empty), "empty id rejected");
        TestAssert.False(PublicRoomDecisionIdentity.IsBoundedPublicId("snowman-\u2603"), "non-ascii id rejected");
        TestAssert.False(
            PublicRoomDecisionIdentity.IsBoundedPublicId(
                new string('a', PublicRoomLimits.MaximumStableIdLength + 1)),
            "oversized id rejected");
    }

    private static PublicRoomDecisionSnapshot ReadySnapshot()
    {
        var candidate = new PublicRoomCandidate(
            0,
            "choose:0",
            PublicRoomCandidateKind.RestHeal,
            "HEAL",
            true,
            true,
            false,
            false);
        return new PublicRoomDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "rest_site",
            "choose_option",
            11,
            new[] { candidate },
            new[] { "choose:0" });
    }

    private sealed class FixedRoomDecisionReader : IPublicRoomDecisionReader
    {
        private readonly PublicRoomDecisionSnapshot _snapshot;

        public FixedRoomDecisionReader(PublicRoomDecisionSnapshot snapshot)
        {
            _snapshot = snapshot;
        }

        public int ReadCount { get; private set; }

        public PublicRoomDecisionSnapshot Read()
        {
            ReadCount++;
            return _snapshot;
        }
    }

    private sealed class ThrowingRoomDecisionReader : IPublicRoomDecisionReader
    {
        private readonly string _message;

        public ThrowingRoomDecisionReader(string message)
        {
            _message = message;
        }

        public PublicRoomDecisionSnapshot Read() => throw new InvalidOperationException(_message);
    }

    private sealed class FixedRoomActionApplier : IPublicRoomActionApplier
    {
        private readonly PublicRoomActionApplyResult _result;

        public FixedRoomActionApplier(PublicRoomActionApplyResult result)
        {
            _result = result;
        }

        public int ApplyCount { get; private set; }

        public PublicRoomActionApplyResult Apply(PublicRoomActionRequest request)
        {
            ApplyCount++;
            return _result;
        }
    }

    private sealed class ThrowingRoomActionApplier : IPublicRoomActionApplier
    {
        private readonly string _message;

        public ThrowingRoomActionApplier(string message)
        {
            _message = message;
        }

        public PublicRoomActionApplyResult Apply(PublicRoomActionRequest request) =>
            throw new InvalidOperationException(_message);
    }
}
