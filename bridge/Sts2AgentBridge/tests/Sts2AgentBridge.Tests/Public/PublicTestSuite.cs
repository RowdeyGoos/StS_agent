using System;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Tests.Public;

internal static class PublicTestSuite
{
    private static readonly PublicMenuState[] MenuStates =
    {
        PublicMenuState.MissingOrInvalid,
        PublicMenuState.Hidden,
        PublicMenuState.Visible,
    };

    private static readonly PublicSubmenuStackState[] StackStates =
    {
        PublicSubmenuStackState.MissingOrInvalid,
        PublicSubmenuStackState.Hidden,
        PublicSubmenuStackState.Visible,
    };

    private static readonly PublicTopSubmenuState[] TopStates =
    {
        PublicTopSubmenuState.None,
        PublicTopSubmenuState.VisibleSettings,
        PublicTopSubmenuState.Invalid,
        PublicTopSubmenuState.Hidden,
        PublicTopSubmenuState.Other,
        PublicTopSubmenuState.TransitionAmbiguous,
    };

    public static void Run()
    {
        ExhaustiveTruthTableIsFailClosed();
        MissingGameAndRootWait();
        NullTopProjectsMainMenu();
        VisibleSettingsTakesPrecedence();
        InvalidAndHiddenMenuAreUnsupported();
        InvalidAndHiddenStackAreUnsupported();
        InvalidAndHiddenTopAreUnsupported();
        OtherSubmenuAndTransitionAreUnsupported();
        UnknownFactValuesAreUnsupported();
        RepeatedStableReadsStayStable();
        FaultBoundaryDropsExceptionDetails();
        CombatDecisionServicePreservesSnapshot();
        CombatDecisionFaultBoundaryDropsExceptionDetails();
        CombatDecisionIdentityBindsVisibleState();
        CombatActionRequestAndServiceFailClosed();
        RewardDecisionAndActionContractsFailClosed();
        MapDecisionAndActionContractsFailClosed();
        NullReaderIsRejected();
    }

    private static void ExhaustiveTruthTableIsFailClosed()
    {
        bool[] validity = { false, true };
        int cases = 0;

        foreach (bool gameValid in validity)
        {
            foreach (bool rootValid in validity)
            {
                foreach (PublicMenuState menuState in MenuStates)
                {
                    foreach (PublicSubmenuStackState stackState in StackStates)
                    {
                        foreach (PublicTopSubmenuState topState in TopStates)
                        {
                            var facts = new PublicScreenFacts(
                                gameValid,
                                rootValid,
                                menuState,
                                stackState,
                                topState);

                            PublicScreenSnapshot expected = ExpectedProjection(facts);
                            PublicScreenSnapshot actual = PublicScreenProjector.Project(facts);
                            TestAssert.Equal(expected, actual, $"public projection case {cases}");
                            cases++;
                        }
                    }
                }
            }
        }

        TestAssert.Equal(216, cases, "exhaustive public projection case count");
    }

    private static void MissingGameAndRootWait()
    {
        AssertProjection(
            new PublicScreenFacts(
                false,
                true,
                PublicMenuState.Visible,
                PublicSubmenuStackState.Visible,
                PublicTopSubmenuState.VisibleSettings),
            PublicScreenStatus.Waiting,
            PublicScreenKind.Unknown,
            "missing or invalid game waits before later facts");

        AssertProjection(
            new PublicScreenFacts(
                true,
                false,
                PublicMenuState.Visible,
                PublicSubmenuStackState.Visible,
                PublicTopSubmenuState.None),
            PublicScreenStatus.Waiting,
            PublicScreenKind.Unknown,
            "missing or invalid root waits before later facts");
    }

    private static void NullTopProjectsMainMenu()
    {
        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.None),
            PublicScreenStatus.Ready,
            PublicScreenKind.MainMenu,
            "null top projects main menu");
    }

    private static void VisibleSettingsTakesPrecedence()
    {
        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.VisibleSettings),
            PublicScreenStatus.Ready,
            PublicScreenKind.Settings,
            "visible settings takes precedence over the visible menu");
    }

    private static void InvalidAndHiddenMenuAreUnsupported()
    {
        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.VisibleSettings) with
            {
                MenuState = PublicMenuState.MissingOrInvalid,
            },
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "invalid menu is unsupported");

        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.VisibleSettings) with
            {
                MenuState = PublicMenuState.Hidden,
            },
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "hidden menu is unsupported");
    }

    private static void InvalidAndHiddenStackAreUnsupported()
    {
        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.VisibleSettings) with
            {
                SubmenuStackState = PublicSubmenuStackState.MissingOrInvalid,
            },
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "invalid stack is unsupported");

        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.VisibleSettings) with
            {
                SubmenuStackState = PublicSubmenuStackState.Hidden,
            },
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "hidden stack is unsupported");
    }

    private static void InvalidAndHiddenTopAreUnsupported()
    {
        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.Invalid),
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "invalid top submenu is unsupported");

        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.Hidden),
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "hidden top submenu is unsupported");
    }

    private static void OtherSubmenuAndTransitionAreUnsupported()
    {
        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.Other),
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "non-settings submenu is unsupported");

        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.TransitionAmbiguous),
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "transition ambiguity is unsupported");
    }

    private static void UnknownFactValuesAreUnsupported()
    {
        AssertProjection(
            ReadyFacts((PublicTopSubmenuState)999),
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "unknown top-submenu value fails closed");

        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.None) with
            {
                MenuState = (PublicMenuState)999,
            },
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "unknown menu value fails closed");

        AssertProjection(
            ReadyFacts(PublicTopSubmenuState.None) with
            {
                SubmenuStackState = (PublicSubmenuStackState)999,
            },
            PublicScreenStatus.Unsupported,
            PublicScreenKind.Unknown,
            "unknown stack value fails closed");
    }

    private static void RepeatedStableReadsStayStable()
    {
        PublicScreenFacts facts = ReadyFacts(PublicTopSubmenuState.VisibleSettings);
        var reader = new FixedReader(facts);
        var service = new PublicScreenService(reader);

        PublicScreenReadResult first = service.Read();
        PublicScreenReadResult second = service.Read();

        TestAssert.True(first.IsSuccess, "first stable read succeeds");
        TestAssert.True(second.IsSuccess, "second stable read succeeds");
        TestAssert.Equal(first, second, "repeated stable reads are identical");
        TestAssert.Equal(facts, reader.Facts, "reader facts remain unchanged");
        TestAssert.Equal(2, reader.ReadCount, "stable reader invoked once per service read");
    }

    private static void FaultBoundaryDropsExceptionDetails()
    {
        const string sensitiveDetail = "fixture-token /private/fake/path NGame";
        var service = new PublicScreenService(new ThrowingReader(sensitiveDetail));

        PublicScreenReadResult result = service.Read();

        TestAssert.False(result.IsSuccess, "throwing reader does not become content");
        TestAssert.Equal(
            PublicScreenReadOutcome.BackendFault,
            result.Outcome,
            "throwing reader becomes backend fault");
        TestAssert.False(
            result.ToString().Contains(sensitiveDetail, StringComparison.Ordinal),
            "backend fault carries no exception detail");
    }

    private static void NullReaderIsRejected()
    {
        TestAssert.Throws<ArgumentNullException>(
            () => _ = new PublicScreenService(null!),
            "public screen service rejects a null reader");
        TestAssert.Throws<ArgumentNullException>(
            () => _ = new PublicCombatDecisionService(null!),
            "public combat decision service rejects a null reader");
        TestAssert.Throws<ArgumentNullException>(
            () => _ = new PublicCombatActionService(null!),
            "public combat action service rejects a null applier");
        TestAssert.Throws<ArgumentNullException>(
            () => _ = new PublicRewardDecisionService(null!),
            "public reward decision service rejects a null reader");
        TestAssert.Throws<ArgumentNullException>(
            () => _ = new PublicRewardActionService(null!),
            "public reward action service rejects a null applier");
        TestAssert.Throws<ArgumentNullException>(
            () => _ = new PublicMapDecisionService(null!),
            "public map decision service rejects a null reader");
        TestAssert.Throws<ArgumentNullException>(
            () => _ = new PublicMapActionService(null!),
            "public map action service rejects a null applier");
    }

    private static void CombatDecisionServicePreservesSnapshot()
    {
        PublicCombatDecisionSnapshot snapshot = PublicCombatDecisionSnapshot.Waiting();
        var reader = new FixedCombatDecisionReader(snapshot);
        var service = new PublicCombatDecisionService(reader);

        PublicCombatDecisionReadResult result = service.Read();

        TestAssert.True(result.IsSuccess, "combat decision read succeeds");
        TestAssert.Equal(snapshot, result.Snapshot, "combat decision snapshot is preserved");
        TestAssert.Equal(1, reader.ReadCount, "combat decision reader invoked once");
    }

    private static void CombatDecisionFaultBoundaryDropsExceptionDetails()
    {
        const string sensitiveDetail = "fixture-token /private/fake/path combat";
        var service = new PublicCombatDecisionService(new ThrowingCombatDecisionReader(sensitiveDetail));

        PublicCombatDecisionReadResult result = service.Read();

        TestAssert.False(result.IsSuccess, "throwing combat reader does not become content");
        TestAssert.Equal(
            PublicCombatDecisionReadOutcome.BackendFault,
            result.Outcome,
            "throwing combat reader becomes backend fault");
        TestAssert.False(
            result.ToString().Contains(sensitiveDetail, StringComparison.Ordinal),
            "combat backend fault carries no exception detail");
    }

    private static void CombatDecisionIdentityBindsVisibleState()
    {
        PublicCombatDecisionSnapshot snapshot = ReadyCombatDecision();
        string first = PublicCombatDecisionIdentity.Compute(snapshot);
        string second = PublicCombatDecisionIdentity.Compute(snapshot);
        string changed = PublicCombatDecisionIdentity.Compute(
            snapshot with { Player = snapshot.Player with { Energy = 1 } });

        TestAssert.True(PublicCombatDecisionIdentity.IsCanonical(first), "decision identity is canonical");
        TestAssert.Equal(first, second, "decision identity is deterministic");
        TestAssert.False(string.Equals(first, changed, StringComparison.Ordinal), "visible state changes decision identity");
        TestAssert.False(PublicCombatDecisionIdentity.IsCanonical(new string('A', 64)), "uppercase decision identity rejected");
        TestAssert.Throws<ArgumentException>(
            () => PublicCombatDecisionIdentity.Compute(PublicCombatDecisionSnapshot.Waiting()),
            "waiting decision has no identity");
    }

    private static void CombatActionRequestAndServiceFailClosed()
    {
        TestAssert.Equal(48, PublicCombatActionBudget.MaximumAcceptedActionsPerCombat, "per-combat action budget");
        TestAssert.Equal(144, PublicCombatActionBudget.MaximumAcceptedActions, "process combat action budget");
        string decisionId = new string('0', 64);
        TestAssert.True(
            PublicCombatActionRequest.TryCreate(decisionId, "play:3:2", out PublicCombatActionRequest request),
            "bounded play action parses");
        TestAssert.Equal(3, request.HandIndex, "parsed hand index");
        TestAssert.Equal(2, request.TargetIndex, "parsed target index");
        TestAssert.True(
            PublicCombatActionRequest.TryCreate(decisionId, "play:3", out PublicCombatActionRequest untargeted),
            "bounded untargeted play parses");
        TestAssert.Equal(-1, untargeted.TargetIndex, "untargeted action sentinel");
        TestAssert.True(
            PublicCombatActionRequest.TryCreate(decisionId, "end_turn", out PublicCombatActionRequest endTurn),
            "bounded end turn parses");
        TestAssert.True(endTurn.IsEndTurn, "end turn request kind");
        TestAssert.Equal(-1, endTurn.HandIndex, "end turn hand sentinel");
        TestAssert.Equal(-1, endTurn.TargetIndex, "end turn target sentinel");
        TestAssert.False(untargeted.IsEndTurn, "play request kind");
        TestAssert.False(
            PublicCombatActionRequest.TryCreate(decisionId, "play:10", out _),
            "multi-digit hand index is outside the bounded contract");

        var applier = new FixedCombatActionApplier(
            PublicCombatActionApplyResult.FromRequest(
                PublicCombatActionApplyOutcome.Accepted,
                untargeted));
        var service = new PublicCombatActionService(applier);
        PublicCombatActionApplyResult accepted = service.Apply(untargeted);
        TestAssert.Equal(PublicCombatActionApplyOutcome.Accepted, accepted.Outcome, "action outcome preserved");
        TestAssert.Equal(1, applier.ApplyCount, "action applier invoked once");

        const string sensitiveDetail = "fixture-token /private/fake/path action";
        var throwing = new PublicCombatActionService(new ThrowingCombatActionApplier(sensitiveDetail));
        PublicCombatActionApplyResult fault = throwing.Apply(untargeted);
        TestAssert.True(fault.IsBackendFault, "throwing action applier becomes backend fault");
        TestAssert.False(
            fault.ToString().Contains(sensitiveDetail, StringComparison.Ordinal),
            "action backend fault carries no exception detail");
    }

    private static void RewardDecisionAndActionContractsFailClosed()
    {
        var ready = new PublicRewardDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "rewards",
            new PublicRewardPlayer(74, 80, 99, 10),
            new[]
            {
                new PublicRewardItem(
                    0,
                    PublicRewardKind.Card,
                    false,
                    0,
                    new[] { "ANGER", "BASH" },
                    true),
            },
            new[] { PublicRewardActionRequest.SkipRewardsActionId });
        string first = PublicRewardDecisionIdentity.Compute(ready);
        string second = PublicRewardDecisionIdentity.Compute(ready);
        string changed = PublicRewardDecisionIdentity.Compute(
            ready with { Player = ready.Player with { Gold = 100 } });
        TestAssert.True(PublicRewardDecisionIdentity.IsCanonical(first), "reward identity is canonical");
        TestAssert.Equal(first, second, "reward identity is deterministic");
        TestAssert.False(string.Equals(first, changed, StringComparison.Ordinal), "reward identity binds visible state");
        TestAssert.Throws<ArgumentException>(
            () => PublicRewardDecisionIdentity.Compute(PublicRewardDecisionSnapshot.Waiting()),
            "waiting reward decision has no identity");

        var reader = new FixedRewardDecisionReader(ready);
        var decisionService = new PublicRewardDecisionService(reader);
        PublicRewardDecisionReadResult read = decisionService.Read();
        TestAssert.True(read.IsSuccess, "reward decision service succeeds");
        TestAssert.Equal(ready, read.Snapshot, "reward decision snapshot preserved");
        TestAssert.Equal(1, reader.ReadCount, "reward decision reader invoked once");

        string decisionId = new string('0', 64);
        TestAssert.Equal(17, PublicRewardActionBudget.MaximumAcceptedActions, "reward session action budget");
        TestAssert.Equal(51, PublicRewardActionBudget.MaximumAcceptedActionsPerProcess, "reward process action budget");
        TestAssert.True(
            PublicRewardActionRequest.TryCreate(
                decisionId,
                PublicRewardActionRequest.SkipRewardsActionId,
                out PublicRewardActionRequest request),
            "bounded reward skip parses");
        TestAssert.False(
            PublicRewardActionRequest.TryCreate(decisionId, "take:0", out _),
            "unadvertised reward action rejected");

        var applier = new FixedRewardActionApplier(
            PublicRewardActionApplyResult.FromRequest(
                PublicRewardActionApplyOutcome.Accepted,
                request));
        var actionService = new PublicRewardActionService(applier);
        PublicRewardActionApplyResult accepted = actionService.Apply(request);
        TestAssert.Equal(PublicRewardActionApplyOutcome.Accepted, accepted.Outcome, "reward action outcome preserved");
        TestAssert.Equal(1, applier.ApplyCount, "reward action applier invoked once");

        const string sensitiveDetail = "fixture-token /private/fake/path reward";
        var throwingDecision = new PublicRewardDecisionService(
            new ThrowingRewardDecisionReader(sensitiveDetail));
        TestAssert.False(throwingDecision.Read().IsSuccess, "throwing reward reader becomes backend fault");
        var throwingAction = new PublicRewardActionService(
            new ThrowingRewardActionApplier(sensitiveDetail));
        PublicRewardActionApplyResult fault = throwingAction.Apply(request);
        TestAssert.True(fault.IsBackendFault, "throwing reward applier becomes backend fault");
        TestAssert.False(
            fault.ToString().Contains(sensitiveDetail, StringComparison.Ordinal),
            "reward backend fault carries no exception detail");
    }

    private static void MapDecisionAndActionContractsFailClosed()
    {
        var ready = new PublicMapDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "map",
            null,
            new[]
            {
                new PublicMapCandidate(0, 2, 3, "monster"),
                new PublicMapCandidate(1, 4, 3, "shop"),
            },
            new[] { "select:0", "select:1" });
        string first = PublicMapDecisionIdentity.Compute(ready);
        string second = PublicMapDecisionIdentity.Compute(ready);
        string changed = PublicMapDecisionIdentity.Compute(
            ready with
            {
                Candidates = new[]
                {
                    new PublicMapCandidate(0, 2, 3, "elite"),
                    new PublicMapCandidate(1, 4, 3, "shop"),
                },
            });
        TestAssert.True(PublicMapDecisionIdentity.IsCanonical(first), "map identity is canonical");
        TestAssert.Equal(first, second, "map identity is deterministic");
        TestAssert.False(string.Equals(first, changed, StringComparison.Ordinal), "map identity binds candidates");
        TestAssert.Throws<ArgumentException>(
            () => PublicMapDecisionIdentity.Compute(PublicMapDecisionSnapshot.Waiting()),
            "waiting map decision has no identity");

        var reader = new FixedMapDecisionReader(ready);
        var decisionService = new PublicMapDecisionService(reader);
        PublicMapDecisionReadResult read = decisionService.Read();
        TestAssert.True(read.IsSuccess, "map decision service succeeds");
        TestAssert.Equal(ready, read.Snapshot, "map decision snapshot preserved");
        TestAssert.Equal(1, reader.ReadCount, "map decision reader invoked once");

        string decisionId = new string('0', 64);
        TestAssert.Equal(3, PublicMapActionBudget.MaximumAcceptedActions, "map action budget");
        TestAssert.True(
            PublicMapActionRequest.TryCreate(decisionId, "select:1", out PublicMapActionRequest request),
            "bounded map selection parses");
        TestAssert.Equal(1, request.CandidateIndex, "map candidate index parses");
        TestAssert.False(
            PublicMapActionRequest.TryCreate(decisionId, "select:8", out _),
            "out-of-range map selection rejected");

        var applier = new FixedMapActionApplier(
            PublicMapActionApplyResult.FromRequest(PublicMapActionApplyOutcome.Accepted, request));
        var actionService = new PublicMapActionService(applier);
        PublicMapActionApplyResult accepted = actionService.Apply(request);
        TestAssert.Equal(PublicMapActionApplyOutcome.Accepted, accepted.Outcome, "map action outcome preserved");
        TestAssert.Equal(1, applier.ApplyCount, "map action applier invoked once");

        const string sensitiveDetail = "fixture-token /private/fake/path map";
        var throwingDecision = new PublicMapDecisionService(new ThrowingMapDecisionReader(sensitiveDetail));
        TestAssert.False(throwingDecision.Read().IsSuccess, "throwing map reader becomes backend fault");
        var throwingAction = new PublicMapActionService(new ThrowingMapActionApplier(sensitiveDetail));
        PublicMapActionApplyResult fault = throwingAction.Apply(request);
        TestAssert.True(fault.IsBackendFault, "throwing map applier becomes backend fault");
        TestAssert.False(
            fault.ToString().Contains(sensitiveDetail, StringComparison.Ordinal),
            "map backend fault carries no exception detail");
    }

    private static PublicCombatDecisionSnapshot ReadyCombatDecision()
    {
        return new PublicCombatDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            1,
            new PublicCombatPlayer(80, 80, 0, 3),
            new[]
            {
                new PublicCombatEnemy(0, "NIBBIT", 43, 43, 0, new[] { "attack" }),
            },
            new[]
            {
                new PublicCombatCard(0, "DEFEND_IRONCLAD", "skill", "1", "self", true),
            },
            new[]
            {
                new PublicDecisionAction(PublicDecisionActionKind.PlayCard, 0, -1),
                new PublicDecisionAction(PublicDecisionActionKind.EndTurn, -1, -1),
            },
            PublicCombatOutcome.None);
    }

    private static PublicScreenFacts ReadyFacts(PublicTopSubmenuState topState)
    {
        return new PublicScreenFacts(
            HasValidGame: true,
            HasValidRoot: true,
            PublicMenuState.Visible,
            PublicSubmenuStackState.Visible,
            topState);
    }

    private static PublicScreenSnapshot ExpectedProjection(PublicScreenFacts facts)
    {
        if (!facts.HasValidGame || !facts.HasValidRoot)
        {
            return new PublicScreenSnapshot(PublicScreenStatus.Waiting, PublicScreenKind.Unknown);
        }

        if (facts.MenuState != PublicMenuState.Visible ||
            facts.SubmenuStackState != PublicSubmenuStackState.Visible)
        {
            return new PublicScreenSnapshot(PublicScreenStatus.Unsupported, PublicScreenKind.Unknown);
        }

        if (facts.TopSubmenuState == PublicTopSubmenuState.None)
        {
            return new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.MainMenu);
        }

        if (facts.TopSubmenuState == PublicTopSubmenuState.VisibleSettings)
        {
            return new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.Settings);
        }

        return new PublicScreenSnapshot(PublicScreenStatus.Unsupported, PublicScreenKind.Unknown);
    }

    private static void AssertProjection(
        PublicScreenFacts facts,
        PublicScreenStatus expectedStatus,
        PublicScreenKind expectedKind,
        string message)
    {
        var expected = new PublicScreenSnapshot(expectedStatus, expectedKind);
        PublicScreenSnapshot actual = PublicScreenProjector.Project(facts);
        TestAssert.Equal(expected, actual, message);
    }

    private sealed class FixedReader : IPublicScreenReader
    {
        public FixedReader(PublicScreenFacts facts)
        {
            Facts = facts;
        }

        public PublicScreenFacts Facts { get; }

        public int ReadCount { get; private set; }

        public PublicScreenFacts Read()
        {
            ReadCount++;
            return Facts;
        }
    }

    private sealed class ThrowingReader : IPublicScreenReader
    {
        private readonly string _message;

        public ThrowingReader(string message)
        {
            _message = message;
        }

        public PublicScreenFacts Read()
        {
            throw new InvalidOperationException(_message);
        }
    }

    private sealed class FixedCombatDecisionReader : IPublicCombatDecisionReader
    {
        private readonly PublicCombatDecisionSnapshot _snapshot;

        public FixedCombatDecisionReader(PublicCombatDecisionSnapshot snapshot)
        {
            _snapshot = snapshot;
        }

        public int ReadCount { get; private set; }

        public PublicCombatDecisionSnapshot Read()
        {
            ReadCount++;
            return _snapshot;
        }
    }

    private sealed class ThrowingCombatDecisionReader : IPublicCombatDecisionReader
    {
        private readonly string _message;

        public ThrowingCombatDecisionReader(string message)
        {
            _message = message;
        }

        public PublicCombatDecisionSnapshot Read()
        {
            throw new InvalidOperationException(_message);
        }
    }

    private sealed class FixedCombatActionApplier : IPublicCombatActionApplier
    {
        private readonly PublicCombatActionApplyResult _result;

        public FixedCombatActionApplier(PublicCombatActionApplyResult result)
        {
            _result = result;
        }

        public int ApplyCount { get; private set; }

        public PublicCombatActionApplyResult Apply(PublicCombatActionRequest request)
        {
            ApplyCount++;
            return _result;
        }
    }

    private sealed class ThrowingCombatActionApplier : IPublicCombatActionApplier
    {
        private readonly string _message;

        public ThrowingCombatActionApplier(string message)
        {
            _message = message;
        }

        public PublicCombatActionApplyResult Apply(PublicCombatActionRequest request)
        {
            throw new InvalidOperationException(_message);
        }
    }

    private sealed class FixedRewardDecisionReader : IPublicRewardDecisionReader
    {
        private readonly PublicRewardDecisionSnapshot _snapshot;

        public FixedRewardDecisionReader(PublicRewardDecisionSnapshot snapshot)
        {
            _snapshot = snapshot;
        }

        public int ReadCount { get; private set; }

        public PublicRewardDecisionSnapshot Read()
        {
            ReadCount++;
            return _snapshot;
        }
    }

    private sealed class ThrowingRewardDecisionReader : IPublicRewardDecisionReader
    {
        private readonly string _message;

        public ThrowingRewardDecisionReader(string message)
        {
            _message = message;
        }

        public PublicRewardDecisionSnapshot Read()
        {
            throw new InvalidOperationException(_message);
        }
    }

    private sealed class FixedRewardActionApplier : IPublicRewardActionApplier
    {
        private readonly PublicRewardActionApplyResult _result;

        public FixedRewardActionApplier(PublicRewardActionApplyResult result)
        {
            _result = result;
        }

        public int ApplyCount { get; private set; }

        public PublicRewardActionApplyResult Apply(PublicRewardActionRequest request)
        {
            ApplyCount++;
            return _result;
        }
    }

    private sealed class ThrowingRewardActionApplier : IPublicRewardActionApplier
    {
        private readonly string _message;

        public ThrowingRewardActionApplier(string message)
        {
            _message = message;
        }

        public PublicRewardActionApplyResult Apply(PublicRewardActionRequest request)
        {
            throw new InvalidOperationException(_message);
        }
    }

    private sealed class FixedMapDecisionReader : IPublicMapDecisionReader
    {
        private readonly PublicMapDecisionSnapshot _snapshot;

        public FixedMapDecisionReader(PublicMapDecisionSnapshot snapshot)
        {
            _snapshot = snapshot;
        }

        public int ReadCount { get; private set; }

        public PublicMapDecisionSnapshot Read()
        {
            ReadCount++;
            return _snapshot;
        }
    }

    private sealed class ThrowingMapDecisionReader : IPublicMapDecisionReader
    {
        private readonly string _message;

        public ThrowingMapDecisionReader(string message)
        {
            _message = message;
        }

        public PublicMapDecisionSnapshot Read()
        {
            throw new InvalidOperationException(_message);
        }
    }

    private sealed class FixedMapActionApplier : IPublicMapActionApplier
    {
        private readonly PublicMapActionApplyResult _result;

        public FixedMapActionApplier(PublicMapActionApplyResult result)
        {
            _result = result;
        }

        public int ApplyCount { get; private set; }

        public PublicMapActionApplyResult Apply(PublicMapActionRequest request)
        {
            ApplyCount++;
            return _result;
        }
    }

    private sealed class ThrowingMapActionApplier : IPublicMapActionApplier
    {
        private readonly string _message;

        public ThrowingMapActionApplier(string message)
        {
            _message = message;
        }

        public PublicMapActionApplyResult Apply(PublicMapActionRequest request)
        {
            throw new InvalidOperationException(_message);
        }
    }
}
