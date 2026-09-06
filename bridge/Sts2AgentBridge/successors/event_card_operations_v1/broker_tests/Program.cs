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
            Check("add_three", AddThree);
            Check("remove_two_preview", RemoveTwoPreview);
            Check("upgrade_two_delayed", UpgradeTwoDelayed);
            Check("wrong_result_and_count", WrongResultAndCount);
            Check("unsupported_known_option", UnsupportedKnownOption);
            Check("sequential_card_item", SequentialCardItem);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"event_card_operations_v1_brokers\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"event_card_operations_v1_brokers\",\"check_count\":" + _checks + "}");
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
        if (!(first.Status == "ready" && first.Candidates.Count == 8)) throw new InvalidOperationException("actual_card_initial");
        ICardSelectionV1ApplyValue firstApply = broker.Apply(first.DecisionId, "select:0");
        if (firstApply is not CardSelectionV1DispatchReceipt) throw new InvalidOperationException("actual_card_select0");
        CardSelectionV1Observation second = (CardSelectionV1Observation)broker.Read();
        if (broker.Apply(second.DecisionId, "select:1") is not CardSelectionV1DispatchReceipt) throw new InvalidOperationException("actual_card_select1");
        factory.Card!.Complete();
        ICardSelectionV1ReadValue completed = broker.Read();
        if (completed is not CardSelectionV1ResolvedResult) throw new InvalidOperationException("actual_card_resolve:" + completed.GetType().Name + ":" + ((CardSelectionV1Observation)completed).Status + ":" + ((CardSelectionV1Observation)completed).Phase);
        if (broker.Status != EventOrchestratorV1ChildStatus.Resolved) throw new InvalidOperationException("actual_card_status");
        EventOrchestratorV1Observation after = Ready(session.Read());
        if (after.PriorResult?.Child?.Kind != "card_selection") throw new InvalidOperationException("actual_card_parent");
        if (!(factory.GuardCalls == 5 && factory.Card.DispatchCount == 2)) throw new InvalidOperationException("actual_card_counts:" + factory.GuardCalls + ":" + factory.Card.DispatchCount);
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

    private static void AddThree()
    {
        ActualFactory factory = CardFactory("ADD_THREE", "add_three",
            CardSelectionV1Operation.Add, 3, 3,
            CardSelectionV1CommitMode.AutoAtMax,
            EventOrchestratorV1CardDomainSource.GeneratedAtAdmission, 5);
        Surface parent = new("ADD_THREE", factory);
        Surface next = new("NEXT", new PassiveFactory());
        using var native = new ParentAdapter(
            parent.Parent(), parent.Parent(), parent.Child(new object()), next.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation outer = Ready(session.Read());
        Receipt(session.Apply(outer.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var broker = (EventOrchestratorV1CardChildBroker)session.ActiveChild!;
        for (int slot = 0; slot < 3; slot++)
        {
            CardSelectionV1Observation ready =
                (CardSelectionV1Observation)broker.Read();
            Require(broker.Apply(ready.DecisionId, "select:" + slot) is
                CardSelectionV1DispatchReceipt);
        }
        factory.Card!.CompleteExact(new[] { 0, 1, 2 }, true, true);
        Require(broker.Read() is CardSelectionV1ResolvedResult &&
            broker.Status == EventOrchestratorV1ChildStatus.Resolved);
        Require(Ready(session.Read()).PriorResult?.Result == "child_completed" &&
            factory.Card.DispatchCount == 3);
    }

    private static void RemoveTwoPreview()
    {
        ActualFactory factory = CardFactory("REMOVE_TWO", "remove_two",
            CardSelectionV1Operation.Remove, 2, 2,
            CardSelectionV1CommitMode.PreviewConfirm,
            EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 4);
        using CardHarness harness = OpenCard(factory, "REMOVE_TWO");
        EventOrchestratorV1CardChildBroker broker = harness.Broker;
        CardSelectionV1Observation first = (CardSelectionV1Observation)broker.Read();
        if (broker.Apply(first.DecisionId, "select:0") is not
            CardSelectionV1DispatchReceipt) throw new InvalidOperationException("remove_select0");
        CardSelectionV1Observation second = (CardSelectionV1Observation)broker.Read();
        if (broker.Apply(second.DecisionId, "select:1") is not
            CardSelectionV1DispatchReceipt) throw new InvalidOperationException("remove_select1");
        factory.Card!.EnterPreview(new[] { 0, 1 }, clearHighlights: true);
        CardSelectionV1Observation preview = (CardSelectionV1Observation)broker.Read();
        if (!(preview.Phase == "preview" &&
            factory.Card.RawSelected.All(selected => !selected) &&
            preview.SelectedSlots.SequenceEqual(new[] { 0, 1 })))
            throw new InvalidOperationException("remove_preview:" + preview.Status + ":" + preview.Phase);
        if (broker.Apply(preview.DecisionId, "confirm") is not
            CardSelectionV1DispatchReceipt) throw new InvalidOperationException("remove_confirm");
        factory.Card.CompleteExact(new[] { 0, 1 }, true, true);
        ICardSelectionV1ReadValue result = broker.Read();
        if (!(result is CardSelectionV1ResolvedResult &&
            factory.Card.DispatchCount == 3))
            throw new InvalidOperationException("remove_resolve:" + result.GetType().Name);
    }

    private static void UpgradeTwoDelayed()
    {
        ActualFactory factory = CardFactory("UPGRADE_TWO", "upgrade_two",
            CardSelectionV1Operation.Upgrade, 2, 2,
            CardSelectionV1CommitMode.PreviewConfirm,
            EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 5);
        using CardHarness harness = OpenCard(factory, "UPGRADE_TWO");
        EventOrchestratorV1CardChildBroker broker = harness.Broker;
        for (int slot = 0; slot < 2; slot++)
        {
            CardSelectionV1Observation ready =
                (CardSelectionV1Observation)broker.Read();
            Require(broker.Apply(ready.DecisionId, "select:" + slot) is
                CardSelectionV1DispatchReceipt);
        }
        factory.Card!.EnterPreview(new[] { 0, 1 });
        CardSelectionV1Observation preview = (CardSelectionV1Observation)broker.Read();
        Require(broker.Apply(preview.DecisionId, "confirm") is
            CardSelectionV1DispatchReceipt);
        factory.Card.CompleteExact(new[] { 0, 1 }, false, false);
        Require(((CardSelectionV1Observation)broker.Read()).Status == "waiting");
        factory.Card.ApplyExactEffect(new[] { 0, 1 });
        Require(((CardSelectionV1Observation)broker.Read()).Status == "waiting");
        factory.Card.EffectObserved = true;
        Require(broker.Read() is CardSelectionV1ResolvedResult);
    }

    private static void WrongResultAndCount()
    {
        foreach (bool wrongCount in new[] { false, true })
        {
            ActualFactory factory = CardFactory("REMOVE_PAIR", "remove_pair",
                CardSelectionV1Operation.Remove, 2, 2,
                CardSelectionV1CommitMode.PreviewConfirm,
                EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 4);
            using CardHarness harness = OpenCard(factory, "REMOVE_PAIR");
            EventOrchestratorV1CardChildBroker broker = harness.Broker;
            for (int slot = 0; slot < 2; slot++)
            {
                CardSelectionV1Observation ready =
                    (CardSelectionV1Observation)broker.Read();
                Require(broker.Apply(ready.DecisionId, "select:" + slot) is
                    CardSelectionV1DispatchReceipt);
            }
            factory.Card!.EnterPreview(new[] { 0, 1 });
            CardSelectionV1Observation preview = (CardSelectionV1Observation)broker.Read();
            Require(broker.Apply(preview.DecisionId, "confirm") is
                CardSelectionV1DispatchReceipt);
            factory.Card.CompleteExact(new[] { 0, 1 }, true, true);
            factory.Card.TaskResult = wrongCount
                ? new[] { factory.Card.Models[0] }
                : new[] { new object(), factory.Card.Models[1] };
            Require(((CardSelectionV1Observation)broker.Read()).Status == "unsupported" &&
                broker.Status == EventOrchestratorV1ChildStatus.Failed);
        }
    }

    private static void UnsupportedKnownOption()
    {
        object button = new(), option = new(), controller = new();
        var candidate = new EventOrchestratorV1NativeCandidate(
            0, "KNOWN_CARD", "text", true, true, false, false, false,
            button, option, controller, () => throw new InvalidOperationException(),
            EventOrchestratorV1CapabilityKind.UnsupportedCardSelection,
            0, null, null);
        EventOrchestratorV1SurfaceCapture capture =
            EventOrchestratorV1SurfaceCapture.Parent(
                Surface.Run, Surface.Player, Surface.Room, Surface.Map, Surface.Event,
                false, false, false, false, new[] { candidate });
        using var native = new ParentAdapter(capture);
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation value = Observation(session.Read());
        Require(value.Status == "unsupported" &&
            session.ReservedDispatchCount == 0 && session.ActiveChild is null);
    }

    private static void SequentialCardItem()
    {
        ActualFactory card = CardFactory("UPGRADE_ONE", "upgrade_one",
            CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.PreviewConfirm,
            EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 3);
        ActualFactory item = new(item: true);
        Surface cardSurface = new("UPGRADE_ONE", card);
        Surface itemSurface = new("ITEM_NEXT", item);
        Surface final = new("FINAL", new PassiveFactory());
        using var native = new ParentAdapter(
            cardSurface.Parent(), cardSurface.Parent(), cardSurface.Child(new object()),
            itemSurface.Parent(), itemSurface.Parent(), itemSurface.Child(new object()),
            final.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation first = Ready(session.Read());
        Receipt(session.Apply(first.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var cardBroker = (EventOrchestratorV1CardChildBroker)session.ActiveChild!;
        CardSelectionV1Observation select =
            (CardSelectionV1Observation)cardBroker.Read();
        Require(cardBroker.Apply(select.DecisionId, "select:0") is
            CardSelectionV1DispatchReceipt);
        card.Card!.EnterPreview(new[] { 0 });
        CardSelectionV1Observation preview =
            (CardSelectionV1Observation)cardBroker.Read();
        Require(cardBroker.Apply(preview.DecisionId, "confirm") is
            CardSelectionV1DispatchReceipt);
        card.Card.CompleteExact(new[] { 0 }, true, true);
        Require(cardBroker.Read() is CardSelectionV1ResolvedResult);

        EventOrchestratorV1Observation second = Ready(session.Read());
        Require(second.PriorResult?.Result == "child_completed");
        Receipt(session.Apply(second.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        var itemBroker = (EventOrchestratorV1ItemChildBroker)session.ActiveChild!;
        ItemV1Observation offer = (ItemV1Observation)itemBroker.Read();
        Require(itemBroker.Apply(offer.DecisionId, "collect:0") is
            ItemV1DispatchReceipt);
        Require(itemBroker.Read() is ItemV1ResolvedResult);
        EventOrchestratorV1Observation after = Ready(session.Read());
        Require(after.PriorResult?.Result == "child_completed" &&
            session.ChildEpisodeCount == 2 && item.Item!.DispatchCount == 1);
    }

    private static ActualFactory CardFactory(
        string stableId,
        string policyId,
        CardSelectionV1Operation operation,
        int minSelect,
        int maxSelect,
        CardSelectionV1CommitMode commitMode,
        EventOrchestratorV1CardDomainSource source,
        int domainCount)
    {
        EventOrchestratorV1CardPolicyDefinition definition =
            EventOrchestratorV1CardPolicyDefinition.CreateForTests(
                policyId, stableId, operation, minSelect, maxSelect,
                commitMode, source, domainCount, domainCount);
        return new ActualFactory(definition.Bind(domainCount));
    }

    private static CardHarness OpenCard(
        ActualFactory factory,
        string stableId)
    {
        Surface parent = new(stableId, factory);
        var native = new ParentAdapter(
            parent.Parent(), parent.Parent(), parent.Child(new object()));
        var session = new EventOrchestratorV1Session(Nonce, native);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        return new CardHarness(session, native,
            (EventOrchestratorV1CardChildBroker)session.ActiveChild!);
    }

    private sealed class CardHarness : IDisposable
    {
        private readonly EventOrchestratorV1Session _session;
        private readonly ParentAdapter _native;
        internal CardHarness(EventOrchestratorV1Session session, ParentAdapter native,
            EventOrchestratorV1CardChildBroker broker)
        { _session = session; _native = native; Broker = broker; }
        internal EventOrchestratorV1CardChildBroker Broker { get; }
        public void Dispose()
        {
            _session.Dispose();
            GC.KeepAlive(_native);
        }
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
                false, false, false, _button, _option, _controller, () => { },
                _factory.Policy.ChildKind == EventOrchestratorV1ChildKind.CardSelection
                    ? EventOrchestratorV1CapabilityKind.SupportedCardSelection
                    : EventOrchestratorV1CapabilityKind.OrdinaryItemEligible,
                _factory.Policy.ExpectedDomainCount, _factory.Policy, _factory);
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
        internal ActualFactory(EventOrchestratorV1ChildPolicy policy)
        {
            Policy = policy;
            _item = policy.ChildKind == EventOrchestratorV1ChildKind.Item;
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
            Card = new CardFixture(correlation, accepted, screen, Policy);
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
        private readonly object _preview = new();
        private readonly object _previewControl = new(), _confirmControl = new();
        private readonly Action _previewDispatch, _confirmDispatch;
        private readonly object[] _models;
        private readonly object[] _holders;
        private readonly object[] _nodes;
        private readonly bool[] _selected;
        private readonly Action[] _selectActions;
        private readonly CardSelectionV1Operation _operation;
        private readonly int _minSelect, _maxSelect, _expectedDomainCount;
        private readonly CardSelectionV1CommitMode _commitMode;
        private readonly CardSelectionV1DeckCard[] _baseline;
        internal int CaptureCount, DispatchCount, DisposeCount, DisposeFailures;
        internal Action? CaptureCallback;
        internal bool Completed, EffectObserved;
        internal bool SelectorTop = true, SelectorClosed, PreviewOpen;
        internal CardSelectionV1Phase Phase = CardSelectionV1Phase.Selecting;
        internal CardSelectionV1TaskState TaskState = CardSelectionV1TaskState.Incomplete;
        internal object[] TaskResult = Array.Empty<object>();
        internal object[] PreviewOriginals = Array.Empty<object>();
        internal readonly List<CardSelectionV1DeckCard> Deck = new();
        internal object[] Models => _models;
        internal bool[] RawSelected => _selected;

        internal CardFixture(EventOrchestratorV1ChildCorrelation correlation,
            EventOrchestratorV1AcceptedContext accepted, object screen,
            EventOrchestratorV1ChildPolicy policy)
        {
            _receipt = correlation; _run = accepted.RunIdentity; _player = accepted.PlayerIdentity;
            _room = accepted.RoomIdentity; _map = accepted.MapIdentity;
            _option = accepted.OptionIdentity; _controller = accepted.ControllerIdentity; _screen = screen;
            _operation = policy.CardOperation; _minSelect = policy.MinSelect;
            _maxSelect = policy.MaxSelect; _commitMode = policy.CardCommitMode;
            _expectedDomainCount = policy.ExpectedDomainCount;
            _models = Enumerable.Range(0, _expectedDomainCount).Select(_ => new object()).ToArray();
            _holders = Enumerable.Range(0, _expectedDomainCount).Select(_ => new object()).ToArray();
            _nodes = Enumerable.Range(0, _expectedDomainCount).Select(_ => new object()).ToArray();
            _selected = new bool[_expectedDomainCount];
            _selectActions = new Action[_expectedDomainCount];
            _previewDispatch = () => { DispatchCount++; };
            _confirmDispatch = () => { DispatchCount++; };
            if (_operation == CardSelectionV1Operation.Add)
            {
                Deck.Add(new CardSelectionV1DeckCard(new object(), "Base_A", 0));
                Deck.Add(new CardSelectionV1DeckCard(new object(), "Base_B", 0));
            }
            else
            {
                for (int index = 0; index < _expectedDomainCount; index++)
                    Deck.Add(new CardSelectionV1DeckCard(
                        _models[index], "Card_" + index, 0));
                Deck.Add(new CardSelectionV1DeckCard(new object(), "Other", 0));
            }
            _baseline = Deck.ToArray();
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
            var candidates = new CardSelectionV1NativeCandidate[_models.Length];
            for (int index = 0; index < candidates.Length; index++)
            {
                int slot = index;
                candidates[index] = new CardSelectionV1NativeCandidate(index, "Card_" + index,
                    _holders[index], _models[index], _nodes[index], 0, true, true,
                    _selected[index], true, _selectActions[slot]);
            }
            CardSelectionV1NativeControl? previewControl = null;
            CardSelectionV1NativeControl? confirmControl = PreviewOpen
                ? new CardSelectionV1NativeControl(
                    _confirmControl, true, true, _confirmDispatch)
                : null;
            return new CardSelectionV1SurfaceCapture(
                CardSelectionV1SurfaceStatus.Available, _receipt, _run, _player, _room, _map,
                _option, _controller, _screen, _task, PreviewOpen ? _preview : null,
                CardSelectionV1ParentKind.Event, _operation, _minSelect, _maxSelect,
                _commitMode, Phase, SelectorTop, SelectorClosed, PreviewOpen,
                true, _expectedDomainCount, true, TaskState, EffectObserved,
                TaskResult, PreviewOriginals, candidates, Deck,
                Array.Empty<CardSelectionV1Replacement>(), previewControl, confirmControl);
        }

        internal void EnterPreview(int[] slots, bool clearHighlights = false)
        {
            Phase = CardSelectionV1Phase.Preview;
            SelectorTop = false;
            PreviewOpen = true;
            PreviewOriginals = slots.Select(slot => _models[slot]).ToArray();
            if (clearHighlights)
                foreach (int slot in slots) _selected[slot] = false;
        }

        internal void Complete() => CompleteExact(new[] { 0, 1 }, applyEffect: true,
            effectObserved: true);

        internal void CompleteExact(
            int[] slots,
            bool applyEffect,
            bool effectObserved)
        {
            foreach (int slot in slots) _selected[slot] = true;
            TaskState = CardSelectionV1TaskState.Succeeded;
            TaskResult = slots.Reverse().Select(slot => _models[slot]).ToArray();
            SelectorTop = false;
            SelectorClosed = true;
            PreviewOpen = false;
            PreviewOriginals = Array.Empty<object>();
            Phase = CardSelectionV1Phase.Submitted;
            if (applyEffect) ApplyExactEffect(slots);
            EffectObserved = effectObserved;
            Completed = true;
        }

        internal void ApplyExactEffect(int[] slots)
        {
            Deck.Clear();
            if (_operation == CardSelectionV1Operation.Add)
            {
                Deck.Add(_baseline[0]);
                foreach (int slot in slots)
                    Deck.Add(new CardSelectionV1DeckCard(
                        _models[slot], "Card_" + slot, 0));
                for (int index = 1; index < _baseline.Length; index++)
                    Deck.Add(_baseline[index]);
                return;
            }
            foreach (CardSelectionV1DeckCard card in _baseline)
            {
                bool selected = slots.Any(slot =>
                    ReferenceEquals(_models[slot], card.ModelIdentity));
                if (_operation == CardSelectionV1Operation.Remove && selected) continue;
                Deck.Add(_operation == CardSelectionV1Operation.Upgrade && selected
                    ? new CardSelectionV1DeckCard(
                        card.ModelIdentity, card.StableKey, card.UpgradeLevel + 1)
                    : card);
            }
        }
        public void Dispose()
        {
            DisposeCount++;
            if (DisposeFailures-- > 0) throw new InvalidOperationException();
        }
    }
}
