using System;
using System.Collections.Generic;
using System.Linq;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.EventOrchestratorV1;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.BrokerTests;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int _checks;

    private static int Main()
    {
        try
        {
            Check("actual_item", ActualItem);
            Check("actual_card", ActualCard);
            Check("item_foreground_guard", ItemForegroundGuard);
            Check("card_foreground_guard", CardForegroundGuard);
            Check("reentrant_dispose", ReentrantDispose);
            Check("cleanup_retry", CleanupRetry);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"event_orchestrator_v1_brokers\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"event_orchestrator_v1_brokers\",\"check_count\":" + _checks + "}");
            return 1;
        }
    }

    private static void Check(string name, Action test) { test(); _checks++; GC.KeepAlive(name); }

    private static void ActualItem()
    {
        var factory = new ActualFactory(item: true);
        Surface parent = new("ITEM_OPTION", factory);
        Surface next = new("NEXT", new PassiveFactory());
        using var native = new ParentAdapter(parent.Parent(), parent.Parent(), parent.Child(new object()), next.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Receipt(session.Apply(decision.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var broker = (EventOrchestratorV1ItemChildBroker)session.ActiveChild!;
        ItemV1Observation item = (ItemV1Observation)broker.Read();
        Require(item.Status == "ready" && item.LegalActions.SequenceEqual(new[] { "collect:0" }));
        Require(broker.Apply(item.DecisionId, "collect:0") is ItemV1DispatchReceipt);
        Require(broker.Read() is ItemV1ResolvedResult && broker.Status == EventOrchestratorV1ChildStatus.Resolved);
        EventOrchestratorV1Observation after = Ready(session.Read());
        Require(after.PriorResult?.Result == "child_completed");
        Require(factory.GuardCalls == 3 && factory.Item!.DispatchCount == 1);
    }

    private static void ActualCard()
    {
        var factory = new ActualFactory(item: false);
        Surface parent = Surface.Cheese(factory);
        Surface next = new("NEXT", new PassiveFactory());
        object screen = new();
        using var native = new ParentAdapter(parent.Parent(), parent.Parent(), parent.Child(screen), next.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Receipt(session.Apply(decision.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var broker = (EventOrchestratorV1CardChildBroker)session.ActiveChild!;
        CardSelectionV1Observation first = (CardSelectionV1Observation)broker.Read();
        Require(first.Status == "ready" && first.Candidates.Count == 8);
        ICardSelectionV1ApplyValue firstApply = broker.Apply(first.DecisionId, "select:0");
        Require(firstApply is CardSelectionV1DispatchReceipt);
        CardSelectionV1Observation second = (CardSelectionV1Observation)broker.Read();
        Require(broker.Apply(second.DecisionId, "select:1") is CardSelectionV1DispatchReceipt);
        factory.Card!.Complete();
        ICardSelectionV1ReadValue completed = broker.Read();
        Require(completed is CardSelectionV1ResolvedResult);
        Require(broker.Status == EventOrchestratorV1ChildStatus.Resolved);
        EventOrchestratorV1Observation after = Ready(session.Read());
        Require(after.PriorResult?.Child?.Kind == "card_selection");
        Require(factory.GuardCalls == 5 && factory.Card.DispatchCount == 2);
    }

    private static void ItemForegroundGuard()
    {
        var factory = new ActualFactory(item: true) { GuardResult = false };
        Surface parent = new("ITEM_OPTION", factory);
        using var native = new ParentAdapter(parent.Parent(), parent.Parent(), parent.Child(new object()));
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Receipt(session.Apply(decision.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var broker = (EventOrchestratorV1ItemChildBroker)session.ActiveChild!;
        Require(((ItemV1Observation)broker.Read()).Status == "unsupported");
        Require(broker.Status == EventOrchestratorV1ChildStatus.Failed);
        Require(factory.Item!.CaptureCount == 0 && factory.GuardCalls == 1);
    }

    private static void CardForegroundGuard()
    {
        var factory = new ActualFactory(item: false) { GuardResult = false };
        Surface parent = Surface.Cheese(factory);
        using var native = new ParentAdapter(parent.Parent(), parent.Parent(), parent.Child(new object()));
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Receipt(session.Apply(decision.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var broker = (EventOrchestratorV1CardChildBroker)session.ActiveChild!;
        Require(((CardSelectionV1Observation)broker.Read()).Status == "unsupported");
        Require(broker.Status == EventOrchestratorV1ChildStatus.Failed);
        Require(factory.Card!.CaptureCount == 0 && factory.GuardCalls == 1);
    }

    private static void ReentrantDispose()
    {
        var factory = new ActualFactory(item: false);
        Surface parent = Surface.Cheese(factory);
        using var native = new ParentAdapter(parent.Parent(), parent.Parent(), parent.Child(new object()));
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Receipt(session.Apply(decision.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var broker = (EventOrchestratorV1CardChildBroker)session.ActiveChild!;
        factory.Card!.CaptureCallback = broker.Dispose;
        ICardSelectionV1ReadValue value = broker.Read();
        Require(value is CardSelectionV1Observation observation && observation.Status == "unsupported");
        Require(broker.Status == EventOrchestratorV1ChildStatus.Failed);
        Require(factory.Card.DisposeCount == 1);
    }

    private static void CleanupRetry()
    {
        var factory = new ActualFactory(item: false);
        Surface parent = Surface.Cheese(factory);
        using var native = new ParentAdapter(parent.Parent(), parent.Parent(), parent.Child(new object()));
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Receipt(session.Apply(decision.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var broker = (EventOrchestratorV1CardChildBroker)session.ActiveChild!;
        factory.Card!.DisposeFailures = 1;
        bool threw = false;
        try { broker.Dispose(); } catch (InvalidOperationException) { threw = true; }
        Require(threw && factory.Card.DisposeCount == 1);
        broker.Dispose();
        Require(factory.Card.DisposeCount == 2 && broker.Status == EventOrchestratorV1ChildStatus.Failed);
    }

    private static EventOrchestratorV1Observation Observation(IRoomFlowReadValue value) =>
        value as EventOrchestratorV1Observation ?? throw new InvalidOperationException();
    private static EventOrchestratorV1Observation Ready(IRoomFlowReadValue value)
    { var result = Observation(value); Require(result.Status == "ready"); return result; }
    private static RoomFlowDispatchReceipt Receipt(IRoomFlowApplyValue value) =>
        value as RoomFlowDispatchReceipt ?? throw new InvalidOperationException();
    private static void Require(bool value) { if (!value) throw new InvalidOperationException(); }

    private sealed class ParentAdapter : IEventOrchestratorV1NativeAdapter
    {
        private readonly Queue<EventOrchestratorV1SurfaceCapture> _values;
        internal ParentAdapter(params EventOrchestratorV1SurfaceCapture[] values) => _values = new(values);
        public EventOrchestratorV1SurfaceCapture CaptureSurface() => _values.Dequeue();
        public EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending) => throw new NotSupportedException();
        public void Dispose() { }
    }

    private sealed class Surface
    {
        internal static readonly object Run = new(), Player = new(), Room = new(), Map = new(), Event = new();
        private readonly string _key; private readonly IEventOrchestratorV1ChildFactory _factory;
        private readonly object _button = new(), _option = new(), _controller = new();
        internal Surface(string key, IEventOrchestratorV1ChildFactory factory) { _key = key; _factory = factory; }
        internal static Surface Cheese(IEventOrchestratorV1ChildFactory factory) =>
            new("ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE", factory);
        internal EventOrchestratorV1SurfaceCapture Parent()
        {
            var candidate = new EventOrchestratorV1NativeCandidate(0, _key, "text", true, true,
                false, false, false, _button, _option, _controller, () => { }, _factory.Policy, _factory);
            return EventOrchestratorV1SurfaceCapture.Parent(Run, Player, Room, Map, Event,
                false, false, false, false, new[] { candidate });
        }
        internal EventOrchestratorV1SurfaceCapture Child(object screen) =>
            EventOrchestratorV1SurfaceCapture.Child(Run, Player, Room, Map, Event,
                screen, _factory.Policy, _factory);
    }

    private sealed class PassiveFactory : IEventOrchestratorV1ChildFactory
    {
        public EventOrchestratorV1ChildPolicy Policy { get; } = EventOrchestratorV1ChildPolicy.ItemReward();
        public IEventOrchestratorV1ChildBroker Create(EventOrchestratorV1AcceptedContext a,
            EventOrchestratorV1ChildCorrelation c, object s) => throw new NotSupportedException();
    }

    private sealed class ActualFactory : IEventOrchestratorV1ChildFactory
    {
        private readonly bool _item;
        internal ActualFactory(bool item)
        {
            _item = item;
            Policy = item ? EventOrchestratorV1ChildPolicy.ItemReward() :
                EventOrchestratorV1ChildPolicy.CheeseGorgeAddTwo();
        }
        public EventOrchestratorV1ChildPolicy Policy { get; }
        internal bool GuardResult = true;
        internal int GuardCalls;
        internal ItemFixture? Item;
        internal CardFixture? Card;
        public IEventOrchestratorV1ChildBroker Create(EventOrchestratorV1AcceptedContext accepted,
            EventOrchestratorV1ChildCorrelation correlation, object screen)
        {
            bool Guard(EventOrchestratorV1AcceptedContext a, object s)
            { GuardCalls++; return GuardResult && ReferenceEquals(a, accepted) && ReferenceEquals(s, screen); }
            if (_item)
            {
                Item = new ItemFixture();
                return new EventOrchestratorV1ItemChildBroker(correlation, accepted, screen, Item, Guard);
            }
            Card = new CardFixture(correlation, accepted, screen);
            return new EventOrchestratorV1CardChildBroker(correlation, accepted, screen, Card, Guard);
        }
    }

    private sealed class ItemFixture : IItemV1NativeAdapter
    {
        private readonly object _run = new(), _player = new(), _screen = new();
        private readonly object _button = new(), _reward = new(), _model = new();
        internal int CaptureCount, DispatchCount;
        public ItemV1SurfaceCapture CaptureSurface()
        {
            CaptureCount++;
            var offer = new ItemV1NativeOffer(0, ItemV1ItemKind.Relic, "Relic_A", true,
                false, true, true, _button, _reward, _model, () => DispatchCount++);
            return ItemV1SurfaceCapture.Available(_run, _player, _screen, 0,
                new[] { offer }, Array.Empty<ItemV1PotionSlotBinding>());
        }
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) =>
            new(_run, _player, _reward, _model, "Relic_A", true, _model, "Relic_A", 0,
                Array.Empty<ItemV1PotionSlotBinding>());
    }

    private sealed class CardFixture : ICardSelectionV1NativeAdapter
    {
        private readonly object _receipt, _run, _player, _room, _map, _option, _controller, _screen;
        private readonly object _task = new();
        private readonly object[] _models = Enumerable.Range(0, 8).Select(_ => new object()).ToArray();
        private readonly object[] _holders = Enumerable.Range(0, 8).Select(_ => new object()).ToArray();
        private readonly object[] _nodes = Enumerable.Range(0, 8).Select(_ => new object()).ToArray();
        private readonly bool[] _selected = new bool[8];
        private readonly Action[] _selectActions = new Action[8];
        private readonly CardSelectionV1DeckCard[] _baseline;
        internal int CaptureCount, DispatchCount, DisposeCount, DisposeFailures;
        internal Action? CaptureCallback;
        internal bool Completed;

        internal CardFixture(EventOrchestratorV1ChildCorrelation correlation,
            EventOrchestratorV1AcceptedContext accepted, object screen)
        {
            _receipt = correlation; _run = accepted.RunIdentity; _player = accepted.PlayerIdentity;
            _room = accepted.RoomIdentity; _map = accepted.MapIdentity;
            _option = accepted.OptionIdentity; _controller = accepted.ControllerIdentity; _screen = screen;
            _baseline = new[]
            {
                new CardSelectionV1DeckCard(new object(), "Base_A", 0),
                new CardSelectionV1DeckCard(new object(), "Base_B", 0),
            };
            for (int index = 0; index < _selectActions.Length; index++)
            {
                int slot = index;
                _selectActions[index] = () => { DispatchCount++; _selected[slot] = true; };
            }
        }

        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            CaptureCount++;
            Action? callback = CaptureCallback; CaptureCallback = null; callback?.Invoke();
            var candidates = new CardSelectionV1NativeCandidate[8];
            for (int index = 0; index < candidates.Length; index++)
            {
                int slot = index;
                candidates[index] = new CardSelectionV1NativeCandidate(index, "Card_" + index,
                    _holders[index], _models[index], _nodes[index], 0, true, true,
                    _selected[index], true, _selectActions[slot]);
            }
            IReadOnlyList<CardSelectionV1DeckCard> deck = Completed
                ? new[] { _baseline[0], new CardSelectionV1DeckCard(_models[0], "Card_0", 0),
                    new CardSelectionV1DeckCard(_models[1], "Card_1", 0), _baseline[1] }
                : _baseline;
            return new CardSelectionV1SurfaceCapture(
                CardSelectionV1SurfaceStatus.Available, _receipt, _run, _player, _room, _map,
                _option, _controller, _screen, _task, null,
                CardSelectionV1ParentKind.Event, CardSelectionV1Operation.Add, 2, 2,
                CardSelectionV1CommitMode.AutoAtMax,
                Completed ? CardSelectionV1Phase.Submitted : CardSelectionV1Phase.Selecting,
                !Completed, Completed, false, true, 8, true,
                Completed ? CardSelectionV1TaskState.Succeeded : CardSelectionV1TaskState.Incomplete,
                Completed, Completed ? new[] { _models[1], _models[0] } : Array.Empty<object>(),
                Array.Empty<object>(), candidates, deck, Array.Empty<CardSelectionV1Replacement>(),
                null, null);
        }

        internal void Complete() => Completed = true;
        public void Dispose()
        {
            DisposeCount++;
            if (DisposeFailures-- > 0) throw new InvalidOperationException();
        }
    }
}
