using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;

internal static class Program
{
    private static int _checks;

    public static int Main()
    {
        try
        {
            CheeseBeginChildProceedMap();
            SmithBeginPreviewProceedMap();
            InitialAdmissionAndPolicyGuards();
            ParentRecaptureAndReservation();
            ExactFirstChildAndFactoryBinding();
            ChildContextAndInitialStateBinding();
            AfterAndExitWitnesses();
            UncertainBeginAndProceed();
            PendingBoundAndNoAdoption();
            ReentryAndOwnerThread();
            DisposalTruthfulness();
            PublicShapeAndCanonicalIdentity();
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"card_selection_parent_v1\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static void CheeseBeginChildProceedMap()
    {
        var f = Fixture.Cheese();
        using var session = f.Session();
        CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
        Accepted(session.Apply(initial.DecisionId, "begin"));
        Equal(1, f.BeginDispatches, "one begin dispatch");
        Waiting(session.Read(), "card_child");
        CardSelectionV1Observation child = ChildReady(session.ReadChild());
        Equal(8, child.Candidates.Count, "cheese exact domain");
        AcceptedChild(session.ApplyChild(child.DecisionId, "select:1"));
        child = ChildReady(session.ReadChild());
        AcceptedChild(session.ApplyChild(child.DecisionId, "select:6"));
        ICardSelectionV1ReadValue childResult = session.ReadChild();
        ChildResolved(childResult, "add", 2);
        Same(childResult, session.ReadChild(), "child terminal cached");
        CardSelectionParentV1Observation after = Ready(session.Read(), "after", "proceed");
        Accepted(session.Apply(after.DecisionId, "proceed"));
        CardSelectionParentV1ResolvedResult result = Resolved(session.Read());
        Equal("map_handoff", result.Result, "event result");
        Equal(1, f.ProceedDispatches, "one proceed dispatch");
        Same(result, session.Read(), "terminal cached");
        Pass();
    }

    private static void SmithBeginPreviewProceedMap()
    {
        var f = Fixture.Smith(3);
        using var session = f.Session();
        CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
        Accepted(session.Apply(initial.DecisionId, "begin"));
        Waiting(session.Read(), "card_child");
        CardSelectionV1Observation child = ChildReady(session.ReadChild());
        Equal(3, child.Candidates.Count, "smith complete eligible domain");
        AcceptedChild(session.ApplyChild(child.DecisionId, "select:2"));
        CardSelectionV1Observation preview = ChildReady(session.ReadChild());
        Equal("preview", preview.Phase, "smith preview");
        True(preview.LegalActions.SequenceEqual(new[] { "confirm" }), "smith exact confirm");
        AcceptedChild(session.ApplyChild(preview.DecisionId, "confirm"));
        ChildResolved(session.ReadChild(), "upgrade", 1);
        CardSelectionParentV1Observation after = Ready(session.Read(), "after", "proceed");
        Accepted(session.Apply(after.DecisionId, "proceed"));
        Resolved(session.Read());
        Pass();
    }

    private static void InitialAdmissionAndPolicyGuards()
    {
        foreach (Action<Fixture> corrupt in new Action<Fixture>[] {
            f => f.NoActiveOverlay = false,
            f => f.MapOpen = true,
            f => f.TravelEnabled = true,
            f => f.ProceedEnabled = true,
            f => f.EffectObserved = true,
            f => f.Witness = "bad",
            f => f.Policy = new CardSelectionParentV1Policy(
                CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo,
                CardSelectionV1ParentKind.Event, "wrong", 0,
                CardSelectionV1Operation.Add, 2, 2,
                CardSelectionV1CommitMode.AutoAtMax, 8) })
        {
            var f = Fixture.Cheese();
            corrupt(f);
            using var session = f.Session();
            Unsupported(session.Read());
            Equal(0, f.BeginDispatches, "initial guard no dispatch");
        }
        var missing = Fixture.Cheese();
        missing.Status = CardSelectionParentV1SurfaceStatus.Missing;
        using (var session = missing.Session()) Waiting(session.Read(), "initial");
        var adopted = Fixture.Cheese();
        adopted.EnterChild();
        using (var session = adopted.Session()) Unsupported(session.Read());
        Pass();
    }

    private static void ParentRecaptureAndReservation()
    {
        var f = Fixture.Cheese();
        using var session = f.Session();
        CardSelectionParentV1Observation ready = Ready(session.Read(), "initial", "begin");
        f.PlayerIdentity = new object();
        Failure(session.Apply(ready.DecisionId, "begin"), "unsupported");
        Equal(0, f.BeginDispatches, "foreign recapture no dispatch");
        Unsupported(session.Read());

        var vanished = Fixture.Cheese();
        using (var vanishedSession = vanished.Session())
        {
            Ready(vanishedSession.Read(), "initial", "begin");
            vanished.Status = CardSelectionParentV1SurfaceStatus.Missing;
            Unsupported(vanishedSession.Read());
            vanished.Status = CardSelectionParentV1SurfaceStatus.Available;
            Unsupported(vanishedSession.Read());
        }

        var captureFault = Fixture.Cheese();
        using (var faultSession = captureFault.Session())
        {
            ready = Ready(faultSession.Read(), "initial", "begin");
            captureFault.ThrowCapture = true;
            Failure(faultSession.Apply(ready.DecisionId, "begin"), "unsupported");
            Equal(0, captureFault.BeginDispatches, "capture fault is not uncertain dispatch");
        }

        var replay = Fixture.Cheese();
        using var replaySession = replay.Session();
        ready = Ready(replaySession.Read(), "initial", "begin");
        Accepted(replaySession.Apply(ready.DecisionId, "begin"));
        Failure(replaySession.Apply(ready.DecisionId, "begin"), "rejected");
        Equal(1, replay.BeginDispatches, "reserved begin not replayed");
        Pass();
    }

    private static void ExactFirstChildAndFactoryBinding()
    {
        var changed = Fixture.Cheese();
        using (var session = changed.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            Accepted(session.Apply(initial.DecisionId, "begin"));
            Waiting(session.Read(), "card_child");
            changed.ScreenIdentity = new object();
            UnsupportedChild(session.ReadChild());
            Unsupported(session.Read());
        }

        var wrongScreen = Fixture.Cheese();
        wrongScreen.Factory.WrongScreen = true;
        using (var session = wrongScreen.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            Accepted(session.Apply(initial.DecisionId, "begin"));
            Waiting(session.Read(), "card_child");
            UnsupportedChild(session.ReadChild());
            Unsupported(session.Read());
        }

        var regressed = Fixture.Cheese();
        using (var session = regressed.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            Accepted(session.Apply(initial.DecisionId, "begin"));
            Waiting(session.Read(), "card_child");
            regressed.Phase = CardSelectionParentV1Phase.Transient;
            Unsupported(session.Read());
            regressed.EnterChild();
            Unsupported(session.Read());
        }

        var transient = Fixture.Cheese();
        using (var session = transient.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            Accepted(session.Apply(initial.DecisionId, "begin"));
            transient.Phase = CardSelectionParentV1Phase.Transient;
            transient.Witness = Hex('e');
            Waiting(session.Read(), "transient");
            transient.EnterChild();
            Waiting(session.Read(), "card_child");
            Equal(0, transient.Factory.CreateCount, "factory unclaimed by parent read");
        }

        foreach (Action<Fixture> corrupt in new Action<Fixture>[] {
            f => f.MapOpen = true,
            f => f.ProceedEnabled = true,
            f => f.EffectObserved = true })
        {
            var recapture = Fixture.Cheese();
            using var session = recapture.Session();
            CardSelectionParentV1Observation initial = Ready(
                session.Read(), "initial", "begin");
            Accepted(session.Apply(initial.DecisionId, "begin"));
            Waiting(session.Read(), "card_child");
            corrupt(recapture);
            UnsupportedChild(session.ReadChild());
            Equal(0, recapture.Factory.CreateCount,
                "changed child flags reject before factory claim");
        }
        Pass();
    }

    private static void ChildContextAndInitialStateBinding()
    {
        var foreign = Fixture.Cheese();
        foreign.Factory.ForeignRun = true;
        using (var session = foreign.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            Accepted(session.Apply(initial.DecisionId, "begin"));
            Waiting(session.Read(), "card_child");
            UnsupportedChild(session.ReadChild());
        }
        var preselected = Fixture.Cheese();
        preselected.Factory.Preselected = true;
        using (var session = preselected.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            Accepted(session.Apply(initial.DecisionId, "begin"));
            Waiting(session.Read(), "card_child");
            UnsupportedChild(session.ReadChild());
        }
        var factoryThrow = Fixture.Cheese();
        factoryThrow.Factory.ThrowOnCreate = true;
        using (var session = factoryThrow.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            Accepted(session.Apply(initial.DecisionId, "begin"));
            Waiting(session.Read(), "card_child");
            UnsupportedChild(session.ReadChild());
            Equal(1, factoryThrow.Factory.CreateCount, "throwing factory claimed once");
        }

        var failedOrphanCleanup = Fixture.Cheese();
        var failedOrphanSession = failedOrphanCleanup.Session();
        CardSelectionParentV1Observation ready = Ready(
            failedOrphanSession.Read(), "initial", "begin");
        Accepted(failedOrphanSession.Apply(ready.DecisionId, "begin"));
        Waiting(failedOrphanSession.Read(), "card_child");
        failedOrphanCleanup.Factory.CreateCallback = () => failedOrphanSession.Read();
        failedOrphanCleanup.Factory.ThrowDispose = true;
        UnsupportedChild(failedOrphanSession.ReadChild());
        Equal(1, failedOrphanCleanup.Factory.ChildDisposeCount,
            "failed orphan cleanup attempted once");
        Throws<InvalidOperationException>(() => failedOrphanSession.Dispose(),
            "failed orphan cleanup remains truthful");
        Pass();
    }

    private static void AfterAndExitWitnesses()
    {
        var f = Fixture.Cheese();
        using var session = f.Session();
        CompleteChild(session, f);
        f.EffectObserved = false;
        Unsupported(session.Read());

        var map = Fixture.Smith(1);
        using var mapSession = map.Session();
        CompleteChild(mapSession, map);
        CardSelectionParentV1Observation after = Ready(mapSession.Read(), "after", "proceed");
        Accepted(mapSession.Apply(after.DecisionId, "proceed"));
        map.Traveling = true;
        Unsupported(mapSession.Read());

        var afterPending = Fixture.Cheese();
        using (var pendingSession = afterPending.Session())
        {
            CompleteChild(pendingSession, afterPending);
            afterPending.EnterAfterTransient();
            Waiting(pendingSession.Read(), "after");
            afterPending.EnterAfter();
            CardSelectionParentV1Observation ready = Ready(
                pendingSession.Read(), "after", "proceed");
            afterPending.HoldProceedTransition = true;
            Accepted(pendingSession.Apply(ready.DecisionId, "proceed"));
            Waiting(pendingSession.Read(), "exit");
        }

        var malformedTransient = Fixture.Cheese();
        using (var malformedSession = malformedTransient.Session())
        {
            CardSelectionParentV1Observation ready = Ready(
                malformedSession.Read(), "initial", "begin");
            Accepted(malformedSession.Apply(ready.DecisionId, "begin"));
            malformedTransient.Phase = CardSelectionParentV1Phase.Transient;
            malformedTransient.Witness = Hex('e');
            malformedTransient.TravelEnabled = true;
            Unsupported(malformedSession.Read());
        }
        Pass();
    }

    private static void UncertainBeginAndProceed()
    {
        var begin = Fixture.Cheese();
        begin.ThrowBegin = true;
        using (var session = begin.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            Failure(session.Apply(initial.DecisionId, "begin"), "uncertain");
            Equal(1, begin.BeginDispatches, "uncertain begin once");
            Unsupported(session.Read());
        }

        var proceed = Fixture.Cheese();
        using (var session = proceed.Session())
        {
            CompleteChild(session, proceed);
            CardSelectionParentV1Observation after = Ready(session.Read(), "after", "proceed");
            proceed.ThrowProceed = true;
            Failure(session.Apply(after.DecisionId, "proceed"), "uncertain");
            Equal(1, proceed.ProceedDispatches, "uncertain proceed once");
            Unsupported(session.Read());
        }
        Pass();
    }

    private static void PendingBoundAndNoAdoption()
    {
        var f = Fixture.Cheese();
        using var session = f.Session();
        CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
        Accepted(session.Apply(initial.DecisionId, "begin"));
        f.Phase = CardSelectionParentV1Phase.Transient;
        f.Witness = Hex('e');
        for (int i = 0; i < CardSelectionParentV1Limits.MaximumPendingReads; i++)
            Waiting(session.Read(), "transient");
        Unsupported(session.Read());
        f.EnterChild();
        Unsupported(session.Read());
        Equal(0, f.Factory.CreateCount, "late child not adopted");
        Pass();
    }

    private static void ReentryAndOwnerThread()
    {
        var read = Fixture.Cheese();
        using (var session = read.Session())
        {
            read.CaptureCallback = () => session.Read();
            Unsupported(session.Read());
        }
        var dispatch = Fixture.Cheese();
        using (var session = dispatch.Session())
        {
            CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
            dispatch.BeginCallback = () => session.Apply(initial.DecisionId, "begin");
            Failure(session.Apply(initial.DecisionId, "begin"), "uncertain");
            Equal(1, dispatch.BeginDispatches, "reentrant dispatch once");
        }
        var offOwner = Fixture.Cheese();
        using (var session = offOwner.Session())
        {
            ICardSelectionParentV1ReadValue? result = null;
            var thread = new Thread(() => result = session.Read());
            thread.Start(); thread.Join();
            Unsupported(result!);
            Equal(0, offOwner.CaptureCount, "off-owner no capture");
        }
        Pass();
    }

    private static void DisposalTruthfulness()
    {
        var f = Fixture.Cheese();
        var session = f.Session();
        session.Dispose();
        Equal(1, f.DisposeCount, "parent adapter disposed once");
        session.Dispose();
        Equal(1, f.DisposeCount, "parent dispose idempotent");
        Unsupported(session.Read());

        var failure = Fixture.Cheese();
        failure.ThrowDispose = true;
        var failed = failure.Session();
        Throws<InvalidOperationException>(() => failed.Dispose(), "dispose failure truthful");
        Throws<InvalidOperationException>(() => failed.Dispose(), "dispose failure stable");

        var reentrant = Fixture.Cheese();
        var reentrantSession = reentrant.Session();
        reentrant.CaptureCallback = () => reentrantSession.Dispose();
        Unsupported(reentrantSession.Read());
        Equal(1, reentrant.DisposeCount, "deferred reentrant cleanup");

        var cleanupReentry = Fixture.Cheese();
        var cleanupReentrySession = cleanupReentry.Session();
        cleanupReentry.DisposeCallback = () => cleanupReentrySession.Read();
        Throws<InvalidOperationException>(() => cleanupReentrySession.Dispose(),
            "cleanup reentry fails truthfully");
        Equal(1, cleanupReentry.DisposeCount, "cleanup reentry no duplicate dispose");
        Throws<InvalidOperationException>(() => cleanupReentrySession.Dispose(),
            "cleanup reentry failure stable");
        Pass();
    }

    private static void PublicShapeAndCanonicalIdentity()
    {
        var a = Fixture.Cheese();
        var b = Fixture.Cheese();
        using var sa = a.Session();
        using var sb = b.Session();
        CardSelectionParentV1Observation oa = Ready(sa.Read(), "initial", "begin");
        CardSelectionParentV1Observation ob = Ready(sb.Read(), "initial", "begin");
        Equal(oa.DecisionId, ob.DecisionId, "opaque refs excluded from digest");
        Throws<NotSupportedException>(() => ((IList<string>)oa.LegalActions).Add("x"), "actions immutable");
        Equal(2, CardSelectionParentV1Limits.MaximumAcceptedActions, "parent action bound");
        Equal(256, CardSelectionParentV1Limits.MaximumPendingReads, "read bound");
        Pass();
    }

    private static void CompleteChild(CardSelectionParentV1Session session, Fixture f)
    {
        CardSelectionParentV1Observation initial = Ready(session.Read(), "initial", "begin");
        Accepted(session.Apply(initial.DecisionId, "begin"));
        Waiting(session.Read(), "card_child");
        CardSelectionV1Observation child = ChildReady(session.ReadChild());
        if (f.Policy.Kind == CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo)
        {
            AcceptedChild(session.ApplyChild(child.DecisionId, "select:0"));
            child = ChildReady(session.ReadChild());
            AcceptedChild(session.ApplyChild(child.DecisionId, "select:1"));
        }
        else
        {
            AcceptedChild(session.ApplyChild(child.DecisionId, "select:0"));
            child = ChildReady(session.ReadChild());
            AcceptedChild(session.ApplyChild(child.DecisionId, "confirm"));
        }
        ChildResolved(session.ReadChild(),
            f.Policy.Operation.ToString().ToLowerInvariant(), f.Policy.MaxSelect);
    }

    private static CardSelectionParentV1Observation Ready(ICardSelectionParentV1ReadValue value, string phase, string action)
    {
        var observation = value as CardSelectionParentV1Observation ?? throw new InvalidOperationException("Expected parent observation.");
        Equal("ready", observation.Status, "parent ready");
        Equal(phase, observation.Phase, "parent phase");
        True(observation.LegalActions.SequenceEqual(new[] { action }), "parent exact action");
        return observation;
    }

    private static void Waiting(ICardSelectionParentV1ReadValue value, string phase)
    {
        var observation = value as CardSelectionParentV1Observation ?? throw new InvalidOperationException("Expected parent waiting.");
        Equal("waiting", observation.Status, "parent waiting");
        Equal(phase, observation.Phase, "waiting phase");
    }

    private static void Unsupported(ICardSelectionParentV1ReadValue value)
    {
        var observation = value as CardSelectionParentV1Observation ?? throw new InvalidOperationException("Expected parent unsupported.");
        Equal("unsupported", observation.Status, "parent unsupported");
    }

    private static CardSelectionV1Observation ChildReady(ICardSelectionV1ReadValue value)
    {
        var observation = value as CardSelectionV1Observation ?? throw new InvalidOperationException("Expected child observation.");
        Equal("ready", observation.Status, "child ready");
        return observation;
    }

    private static void UnsupportedChild(ICardSelectionV1ReadValue value) =>
        True(value is CardSelectionParentV1ChildUnavailable ||
             value is CardSelectionV1Observation o && o.Status == "unsupported", "child unsupported");

    private static void ChildResolved(ICardSelectionV1ReadValue value, string operation, int count)
    {
        var result = value as CardSelectionV1ResolvedResult ?? throw new InvalidOperationException("Expected child result.");
        Equal(operation, result.Operation, "child operation");
        Equal(count, result.SelectedCards.Count, "child count");
    }

    private static void Accepted(ICardSelectionParentV1ApplyValue value) =>
        Equal("accepted", ((CardSelectionParentV1DispatchReceipt)value).Outcome, "parent accepted");
    private static void Failure(ICardSelectionParentV1ApplyValue value, string outcome) =>
        Equal(outcome, ((CardSelectionParentV1ApplyFailure)value).Outcome, "parent failure");
    private static void AcceptedChild(ICardSelectionV1ApplyValue value) =>
        Equal("accepted", ((CardSelectionV1DispatchReceipt)value).Outcome, "child accepted");
    private static CardSelectionParentV1ResolvedResult Resolved(ICardSelectionParentV1ReadValue value) =>
        value as CardSelectionParentV1ResolvedResult ?? throw new InvalidOperationException("Expected parent result, got " + value.GetType().Name + (value is CardSelectionParentV1Observation o ? ":" + o.Status + "/" + o.Phase : ""));

    private static void Pass() => _checks++;
    private static void True(bool value, string message) { if (!value) throw new InvalidOperationException(message); }
    private static void Equal<T>(T expected, T actual, string message)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException($"{message}: expected {expected}, got {actual}");
    }
    private static void Same(object expected, object actual, string message) => True(ReferenceEquals(expected, actual), message);
    private static void Throws<T>(Action action, string message) where T : Exception
    {
        try { action(); } catch (T) { return; }
        throw new InvalidOperationException(message);
    }


    private sealed class Fixture : ICardSelectionParentV1NativeAdapter
    {
        private readonly Action _begin;
        private readonly Action _proceed;
        private readonly object _beginControl = new();
        private readonly object _proceedControl = new();
        private bool _capturing;

        private Fixture(CardSelectionParentV1Policy policy)
        {
            Policy = policy;
            _begin = () =>
            {
                BeginDispatches++;
                BeginCallback?.Invoke();
                if (ThrowBegin) throw new InvalidOperationException("begin");
                EnterChild();
            };
            _proceed = () =>
            {
                ProceedDispatches++;
                if (ThrowProceed) throw new InvalidOperationException("proceed");
                ProceedEnabled = false;
                if (HoldProceedTransition)
                {
                    Phase = CardSelectionParentV1Phase.Transient;
                    return;
                }
                Phase = CardSelectionParentV1Phase.Exit;
                MapOpen = true;
                TravelEnabled = true;
                Traveling = false;
                NoActiveOverlay = true;
                Witness = Hex('d');
            };
            Factory = new ChildFactory(this);
        }

        public static Fixture Cheese() => new(new CardSelectionParentV1Policy(
            CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo,
            CardSelectionV1ParentKind.Event,
            CardSelectionParentV1Limits.CheeseGorgeStableKey,
            0, CardSelectionV1Operation.Add, 2, 2,
            CardSelectionV1CommitMode.AutoAtMax, 8));

        public static Fixture Smith(int domain) => new(new CardSelectionParentV1Policy(
            CardSelectionParentV1PolicyKind.RestSmithUpgradeOne,
            CardSelectionV1ParentKind.Rest,
            CardSelectionParentV1Limits.SmithStableKey,
            1, CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.PreviewConfirm, domain));

        public CardSelectionParentV1Policy Policy { get; set; }
        public object RunIdentity { get; } = new();
        public object PlayerIdentity { get; set; } = new();
        public object RoomIdentity { get; } = new();
        public object MapIdentity { get; } = new();
        public object ParentOptionIdentity { get; } = new();
        public object ParentControllerIdentity { get; } = new();
        public object ScreenIdentity { get; set; } = new();
        public ChildFactory Factory { get; }
        public CardSelectionParentV1SurfaceStatus Status { get; set; } = CardSelectionParentV1SurfaceStatus.Available;
        public CardSelectionParentV1Phase Phase { get; set; } = CardSelectionParentV1Phase.Initial;
        public string Witness { get; set; } = Hex('a');
        public bool NoActiveOverlay { get; set; } = true;
        public bool MapOpen { get; set; }
        public bool TravelEnabled { get; set; }
        public bool Traveling { get; set; }
        public bool EffectObserved { get; set; }
        public bool EventFinished { get; set; }
        public bool EventProceedSingleton { get; set; }
        public bool RestControlsRestored { get; set; }
        public bool ProceedEnabled { get; set; }
        public bool HoldProceedTransition { get; set; }
        public bool ThrowBegin { get; set; }
        public bool ThrowProceed { get; set; }
        public bool ThrowCapture { get; set; }
        public bool ThrowDispose { get; set; }
        public Action? CaptureCallback { get; set; }
        public Action? BeginCallback { get; set; }
        public Action? DisposeCallback { get; set; }
        public int BeginDispatches { get; private set; }
        public int ProceedDispatches { get; private set; }
        public int CaptureCount { get; private set; }
        public int DisposeCount { get; private set; }

        public CardSelectionParentV1Session Session() => new(Hex('1', 32), this);

        public void EnterChild()
        {
            Phase = CardSelectionParentV1Phase.Child;
            Witness = Hex('b');
            NoActiveOverlay = false;
            MapOpen = false;
            TravelEnabled = false;
            Traveling = false;
            EffectObserved = false;
            ProceedEnabled = false;
        }

        public void EnterAfter()
        {
            Phase = CardSelectionParentV1Phase.After;
            Witness = Hex('c');
            NoActiveOverlay = true;
            MapOpen = false;
            Traveling = false;
            EffectObserved = true;
            ProceedEnabled = true;
            TravelEnabled = Policy.ParentKind == CardSelectionV1ParentKind.Rest;
            EventFinished = Policy.ParentKind == CardSelectionV1ParentKind.Event;
            EventProceedSingleton = Policy.ParentKind == CardSelectionV1ParentKind.Event;
            RestControlsRestored = Policy.ParentKind == CardSelectionV1ParentKind.Rest;
        }

        public void EnterAfterTransient()
        {
            Phase = CardSelectionParentV1Phase.Transient;
            Witness = Hex('f');
            NoActiveOverlay = true;
            MapOpen = false;
            TravelEnabled = false;
            Traveling = false;
            EffectObserved = false;
            EventFinished = false;
            EventProceedSingleton = false;
            RestControlsRestored = false;
            ProceedEnabled = false;
        }

        public CardSelectionParentV1SurfaceCapture CaptureSurface()
        {
            CaptureCount++;
            if (ThrowCapture) throw new InvalidOperationException("capture");
            if (!_capturing && CaptureCallback is not null)
            {
                _capturing = true;
                try { CaptureCallback(); }
                finally { _capturing = false; }
            }
            bool child = Phase == CardSelectionParentV1Phase.Child;
            bool after = Phase == CardSelectionParentV1Phase.After;
            bool initial = Phase == CardSelectionParentV1Phase.Initial;
            return new CardSelectionParentV1SurfaceCapture(
                Status, Phase, Policy, RunIdentity, PlayerIdentity, RoomIdentity, MapIdentity,
                ParentOptionIdentity, ParentControllerIdentity, Witness, NoActiveOverlay,
                MapOpen, TravelEnabled, Traveling,
                EventFinished,
                EventProceedSingleton,
                RestControlsRestored,
                EffectObserved,
                child ? ScreenIdentity : null,
                child ? Factory : null,
                initial ? new CardSelectionParentV1NativeControl(_beginControl, true, true, _begin) : null,
                after || ProceedEnabled
                    ? new CardSelectionParentV1NativeControl(_proceedControl, true, ProceedEnabled, _proceed)
                    : null);
        }

        public void Dispose()
        {
            DisposeCount++;
            DisposeCallback?.Invoke();
            if (ThrowDispose) throw new InvalidOperationException("dispose");
        }
    }

    private sealed class ChildFactory : ICardSelectionParentV1ChildFactory
    {
        private readonly Fixture _parent;
        internal ChildFactory(Fixture parent) => _parent = parent;
        public bool WrongScreen { get; set; }
        public bool ForeignRun { get; set; }
        public bool Preselected { get; set; }
        public bool ThrowOnCreate { get; set; }
        public bool ThrowDispose { get; set; }
        public Action? CreateCallback { get; set; }
        public int CreateCount { get; private set; }
        public int ChildDisposeCount { get; private set; }

        public ICardSelectionV1NativeAdapter Create(CardSelectionV1ParentContext context, object exactScreenIdentity)
        {
            CreateCount++;
            if (ThrowOnCreate) throw new InvalidOperationException("factory");
            CreateCallback?.Invoke();
            return new ChildAdapter(_parent, context,
                WrongScreen ? new object() : exactScreenIdentity, ForeignRun, Preselected,
                this);
        }

        internal void OnChildDispose()
        {
            ChildDisposeCount++;
            if (ThrowDispose) throw new InvalidOperationException("child dispose");
        }
    }

    private sealed class ChildAdapter : ICardSelectionV1NativeAdapter
    {
        private readonly Fixture _parent;
        private readonly CardSelectionV1ParentContext _context;
        private readonly object _screen;
        private readonly object _task = new();
        private readonly object _preview = new();
        private readonly object _previewControl = new();
        private readonly object _confirmControl = new();
        private readonly object[] _models;
        private readonly object[] _holders;
        private readonly object[] _nodes;
        private readonly string[] _keys;
        private readonly bool[] _selected;
        private readonly Action[] _select;
        private readonly Action _confirm;
        private readonly List<CardSelectionV1DeckCard> _deck = new();
        private readonly CardSelectionV1DeckCard[] _baseline;
        private readonly bool _foreignRun;
        private readonly ChildFactory _owner;
        private CardSelectionV1Phase _phase = CardSelectionV1Phase.Selecting;
        private CardSelectionV1TaskState _taskState = CardSelectionV1TaskState.Incomplete;
        private object[] _taskResult = Array.Empty<object>();
        private bool _selectorTop = true;
        private bool _selectorClosed;
        private bool _previewOpen;
        private bool _effect;

        internal ChildAdapter(Fixture parent, CardSelectionV1ParentContext context,
            object screen, bool foreignRun, bool preselected, ChildFactory owner)
        {
            _parent = parent;
            _context = context;
            _screen = screen;
            _foreignRun = foreignRun;
            _owner = owner;
            int count = context.ExpectedDomainCount;
            _models = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            _holders = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            _nodes = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            _keys = Enumerable.Range(0, count).Select(i => "Card_" + i).ToArray();
            _selected = new bool[count];
            if (preselected) _selected[0] = true;
            _select = new Action[count];
            for (int i = 0; i < count; i++)
            {
                int slot = i;
                _select[i] = () => Select(slot);
            }
            _confirm = Complete;
            if (context.Operation == CardSelectionV1Operation.Add)
            {
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Base_A", 0));
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Base_B", 0));
            }
            else
            {
                for (int i = 0; i < count; i++)
                    _deck.Add(new CardSelectionV1DeckCard(_models[i], _keys[i], 0));
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Other", 0));
            }
            _baseline = _deck.ToArray();
        }

        private void Select(int slot)
        {
            _selected[slot] = true;
            int count = _selected.Count(v => v);
            if (_context.CommitMode == CardSelectionV1CommitMode.AutoAtMax && count == _context.MaxSelect)
                Complete();
            else if (_context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm && count == _context.MaxSelect)
            {
                _phase = CardSelectionV1Phase.Preview;
                _selectorTop = false;
                _previewOpen = true;
            }
        }

        private void Complete()
        {
            int[] slots = Enumerable.Range(0, _selected.Length).Where(i => _selected[i]).ToArray();
            _taskState = CardSelectionV1TaskState.Succeeded;
            _taskResult = slots.Select(i => _models[i]).ToArray();
            _phase = CardSelectionV1Phase.Submitted;
            _selectorTop = false;
            _selectorClosed = true;
            _previewOpen = false;
            _effect = true;
            if (_context.Operation == CardSelectionV1Operation.Add)
            {
                _deck.Clear();
                _deck.Add(_baseline[0]);
                foreach (int slot in slots)
                    _deck.Add(new CardSelectionV1DeckCard(_models[slot], _keys[slot], 0));
                for (int i = 1; i < _baseline.Length; i++) _deck.Add(_baseline[i]);
            }
            else
            {
                _deck.Clear();
                foreach (CardSelectionV1DeckCard card in _baseline)
                {
                    bool selected = slots.Any(i => ReferenceEquals(_models[i], card.ModelIdentity));
                    _deck.Add(new CardSelectionV1DeckCard(card.ModelIdentity, card.StableKey,
                        card.UpgradeLevel + (selected ? 1 : 0)));
                }
            }
            _parent.EnterAfter();
        }

        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            var candidates = new List<CardSelectionV1NativeCandidate>();
            for (int i = 0; i < _models.Length; i++)
                candidates.Add(new CardSelectionV1NativeCandidate(
                    i, _keys[i], _holders[i], _models[i], _nodes[i], 0,
                    true, true, _selected[i], true, _select[i]));
            object[] previewOriginals = _previewOpen
                ? Enumerable.Range(0, _selected.Length).Where(i => _selected[i]).Select(i => _models[i]).ToArray()
                : Array.Empty<object>();
            return new CardSelectionV1SurfaceCapture(
                CardSelectionV1SurfaceStatus.Available,
                _context.ParentReceiptIdentity,
                _foreignRun ? new object() : _context.RunIdentity,
                _context.PlayerIdentity, _context.RoomIdentity, _context.MapIdentity,
                _context.ParentOptionIdentity, _context.ParentControllerIdentity,
                _screen, _task, _previewOpen ? _preview : null,
                _context.ParentKind, _context.Operation, _context.MinSelect, _context.MaxSelect,
                _context.CommitMode, _phase, _selectorTop, _selectorClosed, _previewOpen,
                true, _models.Length, true, _taskState, _effect, _taskResult, previewOriginals,
                candidates, _deck, Array.Empty<CardSelectionV1Replacement>(),
                new CardSelectionV1NativeControl(_previewControl, true, true, () => { }),
                new CardSelectionV1NativeControl(_confirmControl, true, true, _confirm));
        }

        public void Dispose() => _owner.OnChildDispose();
    }

    private static string Hex(char c, int length = 64) => new(c, length);
}
