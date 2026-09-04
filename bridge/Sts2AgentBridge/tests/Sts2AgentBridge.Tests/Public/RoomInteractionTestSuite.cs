using System;
using Sts2AgentBridge.Adapters.Public;
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
        EventProceedOptionsRemainIndexedChoices();
        ForegroundMapSuppressesPersistentRooms();
        CompletionRequiresAcceptedSameRoomRestProceed();
        LifecycleInvalidationAndOrdinalBounds();
        ImmediateRevalidationPreventsClicksAndBudgetConsumption();
        PendingProjectionAndReplayRemainFailClosed();
        UncertainClickRemainsReserved();
        RestContinuationAndEmbeddedCombatStayBound();
        RoomIdentitySurvivesVisibilityGaps();
        ReturningRoomCannotReissueAcceptedAction();
        KnownRoomKindIsImmutable();
        KnownRoomsSurviveOrdinalExhaustion();
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

    private static void EventProceedOptionsRemainIndexedChoices()
    {
        PublicRoomCandidate candidate = PinnedPublicRoomDecisionReader.CreateEventCandidate(
            0,
            "EVENT.PROCEED",
            true,
            false);

        TestAssert.Equal("choose:0", candidate.ActionId, "event proceed remains indexed");
        TestAssert.Equal(
            PublicRoomCandidateKind.EventOption,
            candidate.Kind,
            "event proceed remains an event option");
        TestAssert.True(candidate.Enabled, "event proceed remains enabled");
        TestAssert.True(candidate.Supported, "event proceed remains supported");
        TestAssert.False(candidate.IsProceed, "wire proceed flag is literal-action-only");
        TestAssert.False(candidate.IsDangerous, "event proceed remains safe");
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

    private static void ForegroundMapSuppressesPersistentRooms()
    {
        foreach (string kind in new[] { "rest_site", "event" })
        {
            var fixture = new LifecycleFixture(kind);
            PublicRoomDecisionSnapshot before = fixture.Reader.Read();
            fixture.Surface = fixture.Surface with { MapOpen = true, TravelEnabled = true };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting, "inspection map");
            TestAssert.Equal(1, fixture.ProjectionCount, "map never projects underlying controls");
            TestAssert.Equal(PublicRoomActionApplyOutcome.StaleDecision,
                fixture.Applier.Apply(Request(before)).Outcome, "behind-map request is stale");
            TestAssert.Equal(0, fixture.ClickCount, "behind-map request cannot click");
            fixture.Surface = fixture.Surface with { MapOpen = false };
            TestAssert.Equal(before.DecisionId, fixture.Reader.Read().DecisionId,
                "inspection open/close preserves decision identity");
            fixture.Surface = fixture.Surface with { Traveling = true };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting, "closed traveling map");
        }
    }

    private static void CompletionRequiresAcceptedSameRoomRestProceed()
    {
        foreach (bool mapOpen in new[] { false, true })
        foreach (bool travelEnabled in new[] { false, true })
        foreach (bool traveling in new[] { false, true })
        {
            var fixture = new LifecycleFixture("rest_site") { Proceed = true };
            PublicRoomDecisionSnapshot ready = fixture.Reader.Read();
            TestAssert.Equal(PublicRoomActionApplyOutcome.Accepted, fixture.Click(ready).Outcome,
                "rest proceed accepted");
            fixture.Surface = fixture.Surface with
            {
                MapOpen = mapOpen, TravelEnabled = travelEnabled, Traveling = traveling,
            };
            PublicRoomDecisionSnapshot result = fixture.Reader.Read();
            bool complete = mapOpen && travelEnabled && !traveling;
            AssertNoCandidates(result, complete ? PublicDecisionStatus.Complete : PublicDecisionStatus.Waiting,
                "rest completion truth table");
            if (complete)
            {
                TestAssert.Equal(ready.RoomOrdinal, result.RoomOrdinal, "completion binds room ordinal");
                TestAssert.Equal("rest_site", result.ScreenKind, "completion binds room kind");
                TestAssert.Equal(result, fixture.Reader.Read(), "completion stable while map remains ready");
                fixture.Surface = fixture.Surface with { MapOpen = false };
                AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting, "completed map closed");
                fixture.Surface = fixture.Surface with { MapOpen = true };
                TestAssert.Equal(result, fixture.Reader.Read(), "same completed map reopens");
            }
        }

        foreach (string kind in new[] { "rest_site", "event" })
        {
            var fixture = new LifecycleFixture(kind);
            PublicRoomDecisionSnapshot ready = fixture.Reader.Read();
            fixture.Click(ready);
            fixture.Surface = fixture.Surface with { MapOpen = true, TravelEnabled = true };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting,
                "heal or indexed event PROCEED text is not accepted exit evidence");
        }

        var unaccepted = new LifecycleFixture("rest_site") { Proceed = true };
        unaccepted.Reader.Read();
        unaccepted.Surface = unaccepted.Surface with { MapOpen = true, TravelEnabled = true };
        AssertNoCandidates(unaccepted.Reader.Read(), PublicDecisionStatus.Waiting,
            "merely observed proceed cannot complete");
        unaccepted.Surface = unaccepted.Surface with { RoomInstanceId = null, ScreenKind = "unknown" };
        AssertNoCandidates(unaccepted.Reader.Read(), PublicDecisionStatus.Waiting,
            "room disappearance alone cannot complete");
    }

    private static void LifecycleInvalidationAndOrdinalBounds()
    {
        foreach (string change in new[] { "room", "run", "kind", "absent", "map_absent", "nested", "travel" })
        {
            var fixture = new LifecycleFixture("rest_site") { Proceed = true };
            PublicRoomDecisionSnapshot ready = fixture.Reader.Read();
            fixture.Click(ready);
            PublicRoomSurface original = fixture.Surface;
            fixture.Surface = change switch
            {
                "room" => original with { RoomInstanceId = 99 },
                "run" => original with { RunInstanceId = 99 },
                "kind" => original with { ScreenKind = "event" },
                "absent" => original with { RoomInstanceId = null },
                "map_absent" => original with { MapAvailable = false },
                "nested" => original with { Unsupported = true },
                _ => original with { Traveling = true },
            };
            fixture.Reader.Read();
            fixture.Surface = original with { MapOpen = true, TravelEnabled = true };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting,
                "invalidated evidence never completes a later map: " + change);
            TestAssert.Equal(PublicRoomActionApplyOutcome.AlreadyApplied,
                fixture.Applier.Apply(Request(ready)).Outcome, "invalidation preserves replay reservation");
        }

        foreach (string kind in new[] { "rest_site", "event" })
        {
            var fixture = new LifecycleFixture(kind);
            fixture.Surface = fixture.Surface with { Unsupported = true, MapOpen = true, TravelEnabled = true };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Unsupported,
                "nested/custom/ambiguous surface cannot complete or project");
            TestAssert.Equal(0, fixture.ProjectionCount, "unsupported content not projected");
        }

        var bounded = new LifecycleFixture("rest_site");
        for (int ordinal = 0; ordinal <= 999; ordinal++)
        {
            bounded.Surface = bounded.Surface with { RoomInstanceId = (ulong)ordinal + 1 };
            TestAssert.Equal(ordinal, bounded.Reader.Read().RoomOrdinal, "ordinal monotonically allocated");
        }
        bounded.Surface = bounded.Surface with { RoomInstanceId = 1001 };
        AssertNoCandidates(bounded.Reader.Read(), PublicDecisionStatus.Unsupported, "ordinal cap fails closed");
        bounded.Surface = bounded.Surface with { RunInstanceId = 2, RoomInstanceId = 1 };
        AssertNoCandidates(bounded.Reader.Read(), PublicDecisionStatus.Unsupported, "new run cannot reset ordinal cap");
    }

    private static void ImmediateRevalidationPreventsClicksAndBudgetConsumption()
    {
        var fixture = new LifecycleFixture("rest_site");
        PublicRoomDecisionSnapshot ready = fixture.Reader.Read();
        fixture.Surface = fixture.Surface with { MapOpen = true };
        TestAssert.Equal(PublicRoomActionApplyOutcome.StaleDecision, fixture.Click(ready).Outcome,
            "map opening after target resolution fails immediate revalidation");
        fixture.Surface = fixture.Surface with { MapOpen = false };
        TestAssert.Equal(PublicRoomActionApplyOutcome.StaleDecision,
            fixture.Click(ready, roomInstanceId: 999).Outcome, "wrong resolved room cannot click");
        fixture.Surface = fixture.Surface with { Unsupported = true };
        TestAssert.Equal(PublicRoomActionApplyOutcome.StaleDecision, fixture.Click(ready).Outcome,
            "nested overlay appearing after resolution cannot click");
        TestAssert.Equal(0, fixture.ClickCount, "stale targets never click");
        fixture.Surface = fixture.Surface with { Unsupported = false };

        for (int index = 0; index < PublicRoomActionBudget.MaximumAcceptedActions; index++)
        {
            fixture.Surface = fixture.Surface with { RoomInstanceId = (ulong)index + 1 };
            ready = fixture.Reader.Read();
            TestAssert.Equal(PublicRoomActionApplyOutcome.Accepted, fixture.Click(ready).Outcome,
                "stale revalidation consumed no action budget");
        }
        fixture.Surface = fixture.Surface with { RoomInstanceId = 100 };
        ready = fixture.Reader.Read();
        TestAssert.Equal(PublicRoomActionApplyOutcome.ActionLimitReached,
            fixture.Applier.Apply(Request(ready)).Outcome, "process action cap survives new rooms");
        TestAssert.Equal(12, fixture.ClickCount, "exactly twelve clicks allowed");
    }

    private static void PendingProjectionAndReplayRemainFailClosed()
    {
        var fixture = new LifecycleFixture("event");
        PublicRoomDecisionSnapshot ready = fixture.Reader.Read();
        fixture.Click(ready);
        AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting, "unchanged accepted event waits");
        fixture.Surface = fixture.Surface with { MapOpen = true, TravelEnabled = true };
        fixture.Reader.Read();
        fixture.Surface = fixture.Surface with { MapOpen = false };
        AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting, "inspection preserves pending event");
        TestAssert.Equal(PublicRoomActionApplyOutcome.AlreadyApplied,
            fixture.Applier.Apply(Request(ready)).Outcome, "replay still rejected after map close");
        fixture.StableId = "NEXT.OPTION";
        PublicRoomDecisionSnapshot next = fixture.Reader.Read();
        TestAssert.Equal(PublicDecisionStatus.Ready, next.Status, "changed public projection remains eligible");
        TestAssert.False(next.DecisionId == ready.DecisionId, "existing hash observes changed candidate");
        TestAssert.Equal(PublicRoomActionApplyOutcome.StaleDecision, fixture.Click(ready).Outcome,
            "changed projection revalidates stale before dispatch");
        fixture.Click(next);
        fixture.StableId = "EVENT.PROCEED";
        PublicRoomDecisionSnapshot repeated = fixture.Reader.Read();
        TestAssert.Equal(ready.DecisionId, repeated.DecisionId, "event step hashing is unchanged");
        TestAssert.Equal(PublicRoomActionApplyOutcome.AlreadyApplied,
            fixture.Applier.Apply(Request(repeated)).Outcome, "repeated event identity never reset");
    }

    private static void UncertainClickRemainsReserved()
    {
        var fixture = new LifecycleFixture("rest_site") { Proceed = true };
        PublicRoomDecisionSnapshot ready = fixture.Reader.Read();
        TestAssert.Throws<InvalidOperationException>(() => fixture.Applier.ReserveAndApply(
            Request(ready), ready, ready.Candidates[0], 1,
            () => throw new InvalidOperationException("synthetic dispatch failure")),
            "uncertain click propagates to existing backend-fault boundary");
        TestAssert.Equal(PublicRoomActionApplyOutcome.AlreadyApplied,
            fixture.Applier.Apply(Request(ready)).Outcome, "uncertain dispatch remains reserved");
        fixture.Surface = fixture.Surface with { MapOpen = true, TravelEnabled = true };
        AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting,
            "uncertain click never creates completion evidence");
    }

    private static void RestContinuationAndEmbeddedCombatStayBound()
    {
        var rest = new LifecycleFixture("rest_site");
        PublicRoomDecisionSnapshot heal = rest.Reader.Read();
        rest.Click(heal);
        rest.ProjectionStatus = PublicDecisionStatus.Unsupported;
        AssertNoCandidates(rest.Reader.Read(), PublicDecisionStatus.Waiting, "healing transition waits");
        rest.ProjectionStatus = PublicDecisionStatus.Ready;
        AssertNoCandidates(rest.Reader.Read(), PublicDecisionStatus.Waiting, "unchanged heal stays pending");
        rest.Proceed = true;
        PublicRoomDecisionSnapshot proceed = rest.Reader.Read();
        TestAssert.Equal(PublicDecisionStatus.Ready, proceed.Status, "post-heal proceed becomes ready");
        rest.Click(proceed);
        rest.Surface = rest.Surface with { MapOpen = true, TravelEnabled = true };
        AssertNoCandidates(rest.Reader.Read(), PublicDecisionStatus.Complete, "heal/proceed/map completes");

        var embedded = new LifecycleFixture("event") { ProjectionStatus = PublicDecisionStatus.Complete };
        AssertNoCandidates(embedded.Reader.Read(), PublicDecisionStatus.Waiting, "unobserved embedded combat");
        embedded.ProjectionStatus = PublicDecisionStatus.Ready;
        PublicRoomDecisionSnapshot ready = embedded.Reader.Read();
        embedded.Click(ready);
        embedded.ProjectionStatus = PublicDecisionStatus.Complete;
        TestAssert.Equal(PublicRoomDecisionSnapshot.Complete("event", ready.RoomOrdinal),
            embedded.Reader.Read(), "existing embedded combat completes only its accepted event");
        embedded.Surface = embedded.Surface with { RoomInstanceId = 2 };
        AssertNoCandidates(embedded.Reader.Read(), PublicDecisionStatus.Waiting, "new embedded event not accepted");

        foreach (bool changeRun in new[] { false, true })
        {
            var fixture = new LifecycleFixture("rest_site") { Proceed = true };
            ready = fixture.Reader.Read();
            fixture.Surface = changeRun ? fixture.Surface with { RunInstanceId = 2 }
                : fixture.Surface with { RoomInstanceId = 2 };
            TestAssert.Equal(PublicRoomActionApplyOutcome.StaleDecision, fixture.Click(ready).Outcome,
                "room/run changed between resolution and click");
            TestAssert.Equal(0, fixture.ClickCount, "wrong incarnation never clicked");
        }
    }

    private static void AssertNoCandidates(
        PublicRoomDecisionSnapshot snapshot, PublicDecisionStatus status, string message)
    {
        TestAssert.Equal(status, snapshot.Status, message);
        TestAssert.Equal(0, snapshot.Candidates.Count, message + " candidates");
        TestAssert.Equal(0, snapshot.LegalActions.Count, message + " legal actions");
        TestAssert.Equal(string.Empty, snapshot.DecisionId, message + " decision identity");
    }

    private static void RoomIdentitySurvivesVisibilityGaps()
    {
        foreach (string kind in new[] { "event", "rest_site" })
        foreach (string gap in new[] { "room", "run", "map" })
        {
            var fixture = new LifecycleFixture(kind) { Proceed = kind == "rest_site" };
            PublicRoomDecisionSnapshot accepted = fixture.Reader.Read();
            TestAssert.Equal(PublicRoomActionApplyOutcome.Accepted,
                fixture.Applier.Apply(Request(accepted)).Outcome, "initial action accepted through Apply");
            PublicRoomSurface original = fixture.Surface;
            fixture.Surface = gap switch
            {
                "room" => original with { RoomInstanceId = null, ScreenKind = "unknown" },
                "run" => default,
                _ => original with { MapAvailable = false },
            };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting, "temporary visibility gap");
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting, "repeated gap allocates nothing");
            fixture.Surface = original with { MapOpen = true, TravelEnabled = true };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting, "gap clears completion evidence");
            fixture.Surface = original;
            PublicRoomDecisionSnapshot returned = fixture.Reader.Read();
            TestAssert.Equal(PublicDecisionStatus.Ready, returned.Status, "unchanged room projection returns");
            PublicRoomActionApplyResult repeated = fixture.Applier.Apply(Request(returned));
            TestAssert.Equal(PublicRoomActionApplyOutcome.AlreadyApplied, repeated.Outcome,
                "returned decision cannot replay accepted action across " + kind + "/" + gap + "; ordinals " +
                accepted.RoomOrdinal + " -> " + returned.RoomOrdinal + "; clicks " + fixture.ClickCount);
            TestAssert.Equal(accepted.RoomOrdinal, returned.RoomOrdinal, "visibility gap preserves ordinal");
            TestAssert.Equal(accepted.DecisionId, returned.DecisionId, "visibility gap preserves decision identity");
            TestAssert.Equal(1, fixture.ClickCount, "one click across visibility gap");
        }

        foreach (bool changeRun in new[] { false, true })
        {
            var fixture = new LifecycleFixture("event");
            PublicRoomDecisionSnapshot first = fixture.Reader.Read();
            fixture.Applier.Apply(Request(first));
            fixture.Surface = changeRun ? fixture.Surface with { RunInstanceId = 2 }
                : fixture.Surface with { RoomInstanceId = 2 };
            PublicRoomDecisionSnapshot next = fixture.Reader.Read();
            TestAssert.Equal(first.RoomOrdinal + 1, next.RoomOrdinal, "new confirmed identity advances ordinal");
            TestAssert.False(first.DecisionId == next.DecisionId, "new confirmed identity has distinct decision");
            TestAssert.Equal(PublicRoomActionApplyOutcome.Accepted,
                fixture.Applier.Apply(Request(next)).Outcome, "new confirmed room remains actionable");
            TestAssert.Equal(2, fixture.ClickCount, "one click per confirmed room");
        }
    }

    private static void ReturningRoomCannotReissueAcceptedAction()
    {
        foreach (string kind in new[] { "event", "rest_site" })
        {
            var fixture = new LifecycleFixture(kind) { Proceed = kind == "rest_site" };
            PublicRoomDecisionSnapshot first = fixture.Reader.Read();
            fixture.Applier.Apply(Request(first));
            PublicRoomSurface original = fixture.Surface;
            fixture.Surface = original with { RoomInstanceId = 2 };
            PublicRoomDecisionSnapshot second = fixture.Reader.Read();
            TestAssert.Equal(first.RoomOrdinal + 1, second.RoomOrdinal, "B gets next ordinal");
            TestAssert.Equal(PublicRoomActionApplyOutcome.Accepted,
                fixture.Applier.Apply(Request(second)).Outcome, "B action accepted once");
            fixture.Surface = original with { MapOpen = true, TravelEnabled = true };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Waiting,
                "returning A does not restore prior completion evidence");
            fixture.Surface = original;
            PublicRoomDecisionSnapshot returned = fixture.Reader.Read();
            TestAssert.Equal(first.DecisionId, returned.DecisionId, "A-B-A preserves first A hash");
            TestAssert.Equal(PublicRoomActionApplyOutcome.AlreadyApplied,
                fixture.Applier.Apply(Request(returned)).Outcome, "freshly returned A cannot replay");
            TestAssert.Equal(2, fixture.ClickCount, "exactly one click per distinct room");
            fixture.Surface = original with { RoomInstanceId = 3 };
            TestAssert.Equal(2, fixture.Reader.Read().RoomOrdinal, "returning A consumes no ordinal");
        }
    }

    private static void KnownRoomKindIsImmutable()
    {
        foreach (string kind in new[] { "event", "rest_site" })
        {
            var fixture = new LifecycleFixture(kind) { Proceed = kind == "rest_site" };
            PublicRoomDecisionSnapshot accepted = fixture.Reader.Read();
            fixture.Applier.Apply(Request(accepted));
            PublicRoomSurface original = fixture.Surface;
            int projections = fixture.ProjectionCount;
            fixture.Surface = original with { ScreenKind = kind == "event" ? "rest_site" : "event" };
            AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Unsupported, "known pair kind conflict");
            TestAssert.Equal(projections, fixture.ProjectionCount, "conflicting kind cannot project controls");
            fixture.Surface = original;
            PublicRoomDecisionSnapshot returned = fixture.Reader.Read();
            TestAssert.Equal(accepted.DecisionId, returned.DecisionId, "kind conflict cannot mint identity");
            TestAssert.Equal(PublicRoomActionApplyOutcome.AlreadyApplied,
                fixture.Applier.Apply(Request(returned)).Outcome, "kind conflict cannot bypass replay");
            TestAssert.Equal(1, fixture.ClickCount, "kind conflict never clicks");
            fixture.Surface = original with { RoomInstanceId = 2 };
            TestAssert.Equal(1, fixture.Reader.Read().RoomOrdinal, "kind conflict consumes no ordinal");
        }
    }

    private static void KnownRoomsSurviveOrdinalExhaustion()
    {
        var fixture = new LifecycleFixture("event");
        PublicRoomDecisionSnapshot first = fixture.Reader.Read();
        fixture.Applier.Apply(Request(first));
        PublicRoomDecisionSnapshot last = first;
        for (int ordinal = 1; ordinal < 1000; ordinal++)
        {
            fixture.Surface = fixture.Surface with { RoomInstanceId = (ulong)ordinal + 1 };
            last = fixture.Reader.Read();
            TestAssert.Equal(ordinal, last.RoomOrdinal, "new pairs allocate monotonically up to cap");
        }
        fixture.Surface = fixture.Surface with { RoomInstanceId = 1001 };
        AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Unsupported, "new pair fails at cap");
        fixture.Surface = fixture.Surface with { RoomInstanceId = 1 };
        PublicRoomDecisionSnapshot returned = fixture.Reader.Read();
        TestAssert.Equal(first.DecisionId, returned.DecisionId, "known pair retains identity at cap");
        TestAssert.Equal(PublicRoomActionApplyOutcome.AlreadyApplied,
            fixture.Applier.Apply(Request(returned)).Outcome, "known pair cannot replay at cap");
        fixture.Surface = fixture.Surface with { RoomInstanceId = 1000 };
        TestAssert.Equal(last.DecisionId, fixture.Reader.Read().DecisionId, "last known pair recognized at cap");
        fixture.Surface = fixture.Surface with { RunInstanceId = 2 };
        AssertNoCandidates(fixture.Reader.Read(), PublicDecisionStatus.Unsupported, "new run cannot reset cap");
        TestAssert.Equal(1, fixture.ClickCount, "ordinal exhaustion never replays accepted action");
    }

    private static PublicRoomActionRequest Request(PublicRoomDecisionSnapshot snapshot)
    {
        TestAssert.True(PublicRoomActionRequest.TryCreate(snapshot.DecisionId,
            snapshot.LegalActions[0], out PublicRoomActionRequest request), "synthetic request valid");
        return request;
    }

    private sealed class LifecycleFixture
    {
        internal PublicRoomSurface Surface;
        internal bool Proceed;
        internal string StableId = "EVENT.PROCEED";
        internal int ClickCount;
        internal int ProjectionCount;
        internal PublicDecisionStatus ProjectionStatus = PublicDecisionStatus.Ready;
        internal readonly PinnedPublicRoomDecisionReader Reader;
        internal readonly PinnedPublicRoomActionApplier Applier;

        internal LifecycleFixture(string kind)
        {
            Surface = new PublicRoomSurface(1, 1, kind, true, false, false, false, false);
            Reader = new PinnedPublicRoomDecisionReader(() => Surface, Project);
            Applier = new PinnedPublicRoomActionApplier(Reader,
                () => Surface.RoomInstanceId!.Value, () => ClickCount++);
        }

        private PublicRoomDecisionSnapshot Project(int ordinal)
        {
            ProjectionCount++;
            if (ProjectionStatus == PublicDecisionStatus.Complete)
            {
                return PublicRoomDecisionSnapshot.Complete(Surface.ScreenKind, ordinal);
            }
            if (ProjectionStatus == PublicDecisionStatus.Unsupported)
            {
                return PublicRoomDecisionSnapshot.Unsupported(Surface.ScreenKind, ordinal);
            }
            PublicRoomCandidate candidate = Surface.ScreenKind == "event"
                ? PinnedPublicRoomDecisionReader.CreateEventCandidate(0, StableId, true, false)
                : Proceed
                    ? new PublicRoomCandidate(0, "proceed", PublicRoomCandidateKind.Proceed,
                        "proceed", true, true, true, false)
                    : ReadySnapshot().Candidates[0];
            var snapshot = new PublicRoomDecisionSnapshot(PublicDecisionStatus.Ready, string.Empty,
                Surface.ScreenKind, Proceed ? "proceed" : "choose_option", ordinal,
                new[] { candidate }, new[] { candidate.ActionId });
            return snapshot with { DecisionId = PublicRoomDecisionIdentity.Compute(snapshot) };
        }

        internal PublicRoomActionApplyResult Click(PublicRoomDecisionSnapshot snapshot, ulong? roomInstanceId = null) =>
            Applier.ReserveAndApply(Request(snapshot), snapshot, snapshot.Candidates[0],
                roomInstanceId ?? Surface.RoomInstanceId!.Value, () => ClickCount++);
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
