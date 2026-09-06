using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.EventOrchestratorV1;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Integration;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";

    private static int Main(string[] args)
    {
        EventOrchestratorV1WireService? service = null;
        try
        {
            if (args.Length != 1 || args[0] is not ("sequential" or "ordinary")) return 2;
            ActualFactory item = new(item: true);
            ActualFactory card;
            Surface proceed = Surface.Proceed();
            ParentAdapter parent;
            if (args[0] == "sequential")
            {
                card = new ActualFactory(item: false);
                Surface first = new("ITEM_OPTION", item);
                Surface cheese = Surface.Cheese(card);
                parent = new ParentAdapter(new[] {
                    first.Parent(), first.Parent(), first.Child(new object()),
                    first.Parent(), cheese.Parent(), cheese.Parent(), cheese.Child(new object()),
                    cheese.Parent(), proceed.Parent(), proceed.Parent(),
                }, new EventOrchestratorV1ExitCapture(
                    Surface.Run, Surface.Player, Surface.Room, Surface.Map,
                    mapOpen: true, travelEnabled: true, traveling: false));
            }
            else
            {
                card = new ActualFactory(item: true);
                Surface first = new("ORDINARY_A", item);
                Surface second = new("ORDINARY_B", card);
                parent = new ParentAdapter(new[] {
                    first.Parent(), first.Parent(), second.Parent(), second.Parent(),
                    proceed.Parent(), proceed.Parent(),
                }, new EventOrchestratorV1ExitCapture(
                    Surface.Run, Surface.Player, Surface.Room, Surface.Map,
                    mapOpen: true, travelEnabled: true, traveling: false));
            }
            service = new EventOrchestratorV1WireService(
                Nonce, new EventOrchestratorV1Session(Nonce, parent));
            string? line;
            while ((line = Console.ReadLine()) is not null)
            {
                using JsonDocument document = JsonDocument.Parse(line);
                JsonElement root = document.RootElement;
                string? method = root.GetProperty("method").GetString();
                string? route = root.GetProperty("route").GetString();
                byte[]? request = root.GetProperty("body").ValueKind == JsonValueKind.Null
                    ? null : Convert.FromBase64String(root.GetProperty("body").GetString()!);
                byte[] response;
                try { response = service.Handle(method, route, request); }
                finally { if (request is not null) Array.Clear(request); }
                try
                {
                    Console.WriteLine(JsonSerializer.Serialize(new
                    {
                        body = Convert.ToBase64String(response),
                        parent_dispatches = Surface.Dispatches,
                        item_dispatches = item.Item?.DispatchCount ?? 0,
                        card_dispatches = card.Card?.DispatchCount ?? 0,
                    }));
                    Console.Out.Flush();
                }
                finally { Array.Clear(response); }
            }
            service.Dispose(); service = null;
            return 0;
        }
        catch
        {
            try { service?.Dispose(); } catch { }
            return 1;
        }
    }

    private sealed class ParentAdapter : IEventOrchestratorV1NativeAdapter
    {
        private readonly Queue<EventOrchestratorV1SurfaceCapture> _captures;
        private readonly EventOrchestratorV1ExitCapture _exit;
        internal ParentAdapter(IEnumerable<EventOrchestratorV1SurfaceCapture> captures,
            EventOrchestratorV1ExitCapture exit)
        { _captures = new(captures); _exit = exit; }
        public EventOrchestratorV1SurfaceCapture CaptureSurface() => _captures.Dequeue();
        public EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending) => _exit;
        public void Dispose() { }
    }

    private sealed class Surface
    {
        internal static readonly object Run = new(), Player = new(), Room = new(), Map = new(), Event = new();
        internal static int Dispatches;
        private readonly string _key;
        private readonly IEventOrchestratorV1ChildFactory? _factory;
        private readonly object _button = new(), _option = new(), _controller = new();
        internal Surface(string key, IEventOrchestratorV1ChildFactory factory)
        { _key = key; _factory = factory; }
        private Surface(string key) { _key = key; }
        internal static Surface Cheese(IEventOrchestratorV1ChildFactory factory) =>
            new("ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE", factory);
        internal static Surface Proceed() => new("PROCEED");
        internal EventOrchestratorV1SurfaceCapture Parent()
        {
            var candidate = new EventOrchestratorV1NativeCandidate(
                0, _key, "bounded \"<>& café\ntext", visible: true, enabled: true,
                locked: false, isDangerous: false, isProceed: _factory is null,
                _button, _option, _controller, () => Dispatches++,
                _factory?.Policy, _factory);
            return EventOrchestratorV1SurfaceCapture.Parent(
                Run, Player, Room, Map, Event, eventFinished: _factory is null,
                mapOpen: false, travelEnabled: false, traveling: false,
                new[] { candidate });
        }
        internal EventOrchestratorV1SurfaceCapture Child(object screen) =>
            EventOrchestratorV1SurfaceCapture.Child(
                Run, Player, Room, Map, Event, screen, _factory!.Policy, _factory);
    }

    private sealed class ActualFactory : IEventOrchestratorV1ChildFactory
    {
        private readonly bool _item;
        internal ActualFactory(bool item)
        { _item = item; Policy = item ? EventOrchestratorV1ChildPolicy.ItemReward() : EventOrchestratorV1ChildPolicy.CheeseGorgeAddTwo(); }
        public EventOrchestratorV1ChildPolicy Policy { get; }
        internal ItemFixture? Item { get; private set; }
        internal CardFixture? Card { get; private set; }
        public IEventOrchestratorV1ChildBroker Create(
            EventOrchestratorV1AcceptedContext accepted,
            EventOrchestratorV1ChildCorrelation correlation,
            object screen)
        {
            bool Guard(EventOrchestratorV1AcceptedContext current, object foreground) =>
                ReferenceEquals(current, accepted) && ReferenceEquals(foreground, screen);
            if (_item)
            {
                Item = new ItemFixture();
                return new EventOrchestratorV1ItemChildBroker(
                    correlation, accepted, screen, Item, Guard);
            }
            Card = new CardFixture(correlation, accepted, screen);
            return new EventOrchestratorV1CardChildBroker(
                correlation, accepted, screen, Card, Guard);
        }
    }

    private sealed class ItemFixture : IItemV1NativeAdapter
    {
        private readonly object _run = new(), _player = new(), _screen = new();
        private readonly object _button = new(), _reward = new(), _model = new();
        internal int DispatchCount { get; private set; }
        public ItemV1SurfaceCapture CaptureSurface()
        {
            var offer = new ItemV1NativeOffer(
                0, ItemV1ItemKind.Relic, "Relic_A", true, false,
                true, true, _button, _reward, _model,
                () => DispatchCount++);
            return ItemV1SurfaceCapture.Available(
                _run, _player, _screen, 0, new[] { offer },
                Array.Empty<ItemV1PotionSlotBinding>());
        }
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) =>
            new(_run, _player, _reward, _model, "Relic_A", true,
                _model, "Relic_A", 0, Array.Empty<ItemV1PotionSlotBinding>());
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
        internal int DispatchCount { get; private set; }
        private bool Completed => _selected.Count(value => value) == 2;
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
            var candidates = new CardSelectionV1NativeCandidate[8];
            for (int index = 0; index < candidates.Length; index++)
            {
                candidates[index] = new CardSelectionV1NativeCandidate(
                    index, "Card_" + index, _holders[index], _models[index], _nodes[index],
                    0, true, true, _selected[index], true,
                    _selectActions[index]);
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
                !Completed, Completed, false,
                true, 8, true,
                Completed ? CardSelectionV1TaskState.Succeeded : CardSelectionV1TaskState.Incomplete,
                Completed,
                Completed ? new[] { _models[1], _models[0] } : Array.Empty<object>(),
                Array.Empty<object>(), candidates, deck,
                Array.Empty<CardSelectionV1Replacement>(), null, null);
        }
        public void Dispose() { }
    }
}
