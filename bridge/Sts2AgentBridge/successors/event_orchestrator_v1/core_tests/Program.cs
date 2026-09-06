using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.EventOrchestratorV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.CoreTests;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int _checks;

    private static int Main()
    {
        try
        {
            Check("ordinary_transition", OrdinaryTransition);
            Check("bound_transient", BoundTransient);
            Check("cheese_child", CheeseChild);
            Check("factory_replacement", FactoryReplacement);
            Check("recapture_binding", RecaptureBinding);
            Check("dispatch_uncertain", DispatchUncertain);
            Check("stable_key_aba", StableKeyAba);
            Check("proceed_exit", ProceedExit);
            Check("four_child_cap", FourChildCap);
            Check("child_cleanup_failure", ChildCleanupFailure);
            Check("reentry", Reentry);
            Check("malformed_capability", MalformedCapability);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"event_orchestrator_v1_core\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"event_orchestrator_v1_core\",\"check_count\":" + _checks + "}");
            return 1;
        }
    }

    private static void Check(string name, Action test)
    {
        test();
        _checks++;
        GC.KeepAlive(name);
    }

    private static void OrdinaryTransition()
    {
        var f1 = FakeFactory.Item(); var f2 = FakeFactory.Item();
        int dispatch = 0;
        Surface p1 = new("A", f1, () => dispatch++);
        Surface p2 = new("B", f2);
        using var adapter = new FakeAdapter(p1.Parent(), p1.Parent(), p2.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation first = Ready(session.Read());
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(first.DecisionId, "choose:0"));
        EventOrchestratorV1Observation second = Ready(session.Read());
        Require(dispatch == 1 && receipt.ActionId == "choose:0");
        Require(second.PriorResult?.Result == EventOrchestratorV1Limits.OptionTransitionResult);
        Require(second.PriorResult!.DecisionId == receipt.DecisionId && second.Child is null);
    }

    private static void BoundTransient()
    {
        var f1 = FakeFactory.Item(); var f2 = FakeFactory.Item();
        Surface p1 = new("A", f1); Surface p2 = new("B", f2);
        using (var adapter = new FakeAdapter(p1.Parent(), p1.Parent(), p1.Transient(), p2.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation ready = Ready(session.Read());
            Receipt(session.Apply(ready.DecisionId, "choose:0"));
            Require(Observation(session.Read()).Status == "waiting");
            Require(Ready(session.Read()).PriorResult?.Result == "option_transition");
        }
        using (var adapter = new FakeAdapter(p1.Parent(), p1.Parent(), EventOrchestratorV1SurfaceCapture.Missing()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation ready = Ready(session.Read());
            Receipt(session.Apply(ready.DecisionId, "choose:0"));
            Require(Observation(session.Read()).Status == "unsupported");
        }
    }

    private static void CheeseChild()
    {
        FakeFactory cheese = FakeFactory.Cheese(); FakeFactory next = FakeFactory.Item();
        Surface p1 = new("ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE", cheese);
        Surface p2 = new("NEXT", next);
        object screen = new();
        using var adapter = new FakeAdapter(p1.Parent(), p1.Parent(), p1.Child(screen), p2.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(ready.DecisionId, "choose:0"));
        EventOrchestratorV1Observation child = Observation(session.Read());
        Require(child.Status == "child" && child.Child?.Kind == "card_selection");
        Require(child.Child!.ChildOrdinal == 1 && cheese.Calls == 1);
        Require(ReferenceEquals(cheese.Accepted?.ParentReceipt, receipt));
        cheese.Broker!.Current = EventOrchestratorV1ChildStatus.Resolved;
        EventOrchestratorV1Observation after = Ready(session.Read());
        Require(after.PriorResult?.Result == "child_completed");
        Require(after.PriorResult!.Child?.ChildOrdinal == 1 && cheese.Broker.Disposed);
    }

    private static void FactoryReplacement()
    {
        EventOrchestratorV1ChildPolicy policy = EventOrchestratorV1ChildPolicy.ItemReward();
        var expected = new FakeFactory(policy); var foreign = new FakeFactory(policy);
        Surface p = new("A", expected);
        using var adapter = new FakeAdapter(p.Parent(), p.Parent(), p.Child(new object(), foreign));
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "unsupported");
        Require(expected.Calls == 0 && foreign.Calls == 0);
    }

    private static void RecaptureBinding()
    {
        EventOrchestratorV1ChildPolicy policy = EventOrchestratorV1ChildPolicy.ItemReward();
        var f1 = new FakeFactory(policy); var f2 = new FakeFactory(policy);
        Surface first = new("A", f1); Surface changed = new("A", f2,
            button: first.Button, option: first.Option, controller: first.Controller);
        using var adapter = new FakeAdapter(first.Parent(), changed.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        RoomFlowApplyFailure failure = Failure(session.Apply(ready.DecisionId, "choose:0"));
        Require(failure.Outcome == "unsupported" && first.DispatchCount == 0);
    }

    private static void DispatchUncertain()
    {
        var factory = FakeFactory.Item();
        Surface p = new("A", factory, () => throw new InvalidOperationException());
        using var adapter = new FakeAdapter(p.Parent(), p.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Require(Failure(session.Apply(ready.DecisionId, "choose:0")).Outcome == "uncertain");
        Require(factory.Calls == 0 && session.ReservedDispatchCount == 1);
        Require(Failure(session.Apply(ready.DecisionId, "choose:0")).Outcome == "rejected");
    }

    private static void StableKeyAba()
    {
        Surface a = new("A", FakeFactory.Item()); Surface b = new("B", FakeFactory.Item());
        Surface again = new("A", FakeFactory.Item());
        using var adapter = new FakeAdapter(a.Parent(), a.Parent(), b.Parent(), b.Parent(), again.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation first = Ready(session.Read());
        Receipt(session.Apply(first.DecisionId, "choose:0"));
        EventOrchestratorV1Observation second = Ready(session.Read());
        Receipt(session.Apply(second.DecisionId, "choose:0"));
        EventOrchestratorV1Observation final = Observation(session.Read());
        Require(final.Status == "waiting" && final.LegalActions.Count == 0);
    }

    private static void ProceedExit()
    {
        Surface proceed = Surface.Proceed();
        using var adapter = new FakeAdapter(proceed.Parent(), proceed.Parent());
        adapter.Exits.Enqueue(new EventOrchestratorV1ExitCapture(
            Surface.Run, Surface.Player, Surface.Room, Surface.Map, false, false, false));
        adapter.Exits.Enqueue(new EventOrchestratorV1ExitCapture(
            Surface.Run, Surface.Player, Surface.Room, Surface.Map, true, true, false));
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(ready.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "waiting");
        var resolved = (EventOrchestratorV1ResolvedResult)session.Read();
        Require(resolved.Result == "map_handoff" && resolved.DecisionId == receipt.DecisionId);
        Require(resolved.PriorResult?.Result == "map_handoff");
    }

    private static void FourChildCap()
    {
        var factories = new FakeFactory[5]; var surfaces = new Surface[5];
        var captures = new List<EventOrchestratorV1SurfaceCapture>();
        for (int i = 0; i < 5; i++)
        {
            factories[i] = FakeFactory.Item();
            surfaces[i] = new Surface("K" + i, factories[i]);
            captures.Add(surfaces[i].Parent());
            captures.Add(surfaces[i].Parent());
            captures.Add(surfaces[i].Child(new object()));
        }
        using var adapter = new FakeAdapter(captures.ToArray());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation current = Ready(session.Read());
        for (int i = 0; i < 4; i++)
        {
            Receipt(session.Apply(current.DecisionId, "choose:0"));
            Require(Observation(session.Read()).Status == "child");
            factories[i].Broker!.Current = EventOrchestratorV1ChildStatus.Resolved;
            current = Ready(session.Read());
        }
        Receipt(session.Apply(current.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "unsupported");
        Require(session.ChildEpisodeCount == 4 && factories[4].Calls == 0);
    }

    private static void ChildCleanupFailure()
    {
        FakeFactory f = FakeFactory.Item(); f.ThrowDispose = true;
        Surface p = new("A", f); Surface after = new("B", FakeFactory.Item());
        using var adapter = new FakeAdapter(p.Parent(), p.Parent(), p.Child(new object()), after.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        f.Broker!.Current = EventOrchestratorV1ChildStatus.Resolved;
        Require(Observation(session.Read()).Status == "unsupported");
    }

    private static void Reentry()
    {
        FakeFactory f = FakeFactory.Item();
        EventOrchestratorV1Session? session = null;
        Surface p = new("A", f, () => { _ = session!.Read(); });
        using var adapter = new FakeAdapter(p.Parent(), p.Parent());
        using (session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation ready = Ready(session.Read());
            Require(Failure(session.Apply(ready.DecisionId, "choose:0")).Outcome == "uncertain");
            Require(session.ReservedDispatchCount == 1);
        }
    }

    private static void MalformedCapability()
    {
        FakeFactory cheese = FakeFactory.Cheese();
        Surface wrong = new("ORDINARY", cheese);
        using (var adapter = new FakeAdapter(wrong.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
            Require(Observation(session.Read()).Status == "unsupported");

        Surface none = new("ORDINARY", null);
        using (var adapter = new FakeAdapter(none.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
            Require(Observation(session.Read()).Status == "unsupported");
    }

    private static EventOrchestratorV1Observation Observation(IRoomFlowReadValue value) =>
        value as EventOrchestratorV1Observation ?? throw new InvalidOperationException();
    private static EventOrchestratorV1Observation Ready(IRoomFlowReadValue value)
    {
        EventOrchestratorV1Observation result = Observation(value);
        Require(result.Status == "ready");
        return result;
    }
    private static RoomFlowDispatchReceipt Receipt(IRoomFlowApplyValue value) =>
        value as RoomFlowDispatchReceipt ?? throw new InvalidOperationException();
    private static RoomFlowApplyFailure Failure(IRoomFlowApplyValue value) =>
        value as RoomFlowApplyFailure ?? throw new InvalidOperationException();
    private static void Require(bool value)
    {
        if (!value) throw new InvalidOperationException();
    }

    private sealed class FakeAdapter : IEventOrchestratorV1NativeAdapter
    {
        private readonly Queue<EventOrchestratorV1SurfaceCapture> _captures;
        internal readonly Queue<EventOrchestratorV1ExitCapture> Exits = new();
        internal FakeAdapter(params EventOrchestratorV1SurfaceCapture[] captures) =>
            _captures = new Queue<EventOrchestratorV1SurfaceCapture>(captures);
        public EventOrchestratorV1SurfaceCapture CaptureSurface() => _captures.Dequeue();
        public EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending) => Exits.Dequeue();
        public void Dispose() { }
    }

    private sealed class Surface
    {
        internal static readonly object Run = new();
        internal static readonly object Player = new();
        internal static readonly object Room = new();
        internal static readonly object Map = new();
        internal static readonly object Event = new();
        internal readonly object Button;
        internal readonly object Option;
        internal readonly object Controller;
        internal readonly string Key;
        internal readonly FakeFactory? Factory;
        internal readonly bool IsProceed;
        private readonly Action? _dispatch;
        internal int DispatchCount;

        internal Surface(string key, FakeFactory? factory, Action? dispatch = null,
            object? button = null, object? option = null, object? controller = null,
            bool proceed = false)
        {
            Key = key; Factory = factory; _dispatch = dispatch; IsProceed = proceed;
            Button = button ?? new object(); Option = option ?? new object(); Controller = controller ?? new object();
        }

        internal static Surface Proceed() => new("PROCEED", null, proceed: true);

        internal EventOrchestratorV1SurfaceCapture Parent()
        {
            var candidate = new EventOrchestratorV1NativeCandidate(
                0, Key, "text", true, true, false, false, IsProceed,
                Button, Option, Controller, () => { DispatchCount++; _dispatch?.Invoke(); },
                Factory?.Policy, Factory);
            return EventOrchestratorV1SurfaceCapture.Parent(
                Run, Player, Room, Map, Event, IsProceed, false, false, false,
                new[] { candidate });
        }

        internal EventOrchestratorV1SurfaceCapture Child(object screen, FakeFactory? factory = null)
        {
            FakeFactory exact = factory ?? Factory ?? throw new InvalidOperationException();
            return EventOrchestratorV1SurfaceCapture.Child(
                Run, Player, Room, Map, Event, screen, exact.Policy, exact);
        }

        internal EventOrchestratorV1SurfaceCapture Transient() =>
            EventOrchestratorV1SurfaceCapture.Transient(Run, Player, Room, Map, Event);
    }

    private sealed class FakeFactory : IEventOrchestratorV1ChildFactory
    {
        internal FakeFactory(EventOrchestratorV1ChildPolicy policy) => Policy = policy;
        internal static FakeFactory Item() => new(EventOrchestratorV1ChildPolicy.ItemReward());
        internal static FakeFactory Cheese() => new(EventOrchestratorV1ChildPolicy.CheeseGorgeAddTwo());
        public EventOrchestratorV1ChildPolicy Policy { get; }
        internal int Calls;
        internal EventOrchestratorV1AcceptedContext? Accepted;
        internal FakeBroker? Broker;
        internal bool ThrowDispose;
        public IEventOrchestratorV1ChildBroker Create(
            EventOrchestratorV1AcceptedContext acceptedContext,
            EventOrchestratorV1ChildCorrelation correlation,
            object exactForegroundIdentity)
        {
            Calls++; Accepted = acceptedContext;
            Broker = Policy.ChildKind == EventOrchestratorV1ChildKind.Item
                ? new FakeItemBroker(correlation, ThrowDispose)
                : new FakeCardBroker(correlation, ThrowDispose);
            return Broker;
        }
    }

    private abstract class FakeBroker : IEventOrchestratorV1ChildBroker
    {
        private int _disposeFailures;
        internal FakeBroker(EventOrchestratorV1ChildCorrelation correlation,
            bool throwDispose)
        { Correlation = correlation; _disposeFailures = throwDispose ? 1 : 0; }
        public EventOrchestratorV1ChildCorrelation Correlation { get; }
        internal EventOrchestratorV1ChildStatus Current = EventOrchestratorV1ChildStatus.Active;
        public EventOrchestratorV1ChildStatus Status => Current;
        internal bool Disposed;
        public void Dispose()
        {
            Disposed = true;
            if (_disposeFailures-- > 0) throw new InvalidOperationException();
        }
    }

    private sealed class FakeItemBroker : FakeBroker, IEventOrchestratorV1ItemChildBroker
    {
        internal FakeItemBroker(EventOrchestratorV1ChildCorrelation correlation, bool fail) : base(correlation, fail) { }
        Sts2AgentBridge.Successors.ItemV1.IItemV1ReadValue IEventOrchestratorV1ItemChildBroker.Read() => throw new NotSupportedException();
        Sts2AgentBridge.Successors.ItemV1.IItemV1ApplyValue IEventOrchestratorV1ItemChildBroker.Apply(string? d, string? a) => throw new NotSupportedException();
    }

    private sealed class FakeCardBroker : FakeBroker, IEventOrchestratorV1CardChildBroker
    {
        internal FakeCardBroker(EventOrchestratorV1ChildCorrelation correlation, bool fail) : base(correlation, fail) { }
        Sts2AgentBridge.Successors.CardSelectionV1.ICardSelectionV1ReadValue IEventOrchestratorV1CardChildBroker.Read() => throw new NotSupportedException();
        Sts2AgentBridge.Successors.CardSelectionV1.ICardSelectionV1ApplyValue IEventOrchestratorV1CardChildBroker.Apply(string? d, string? a) => throw new NotSupportedException();
    }
}
