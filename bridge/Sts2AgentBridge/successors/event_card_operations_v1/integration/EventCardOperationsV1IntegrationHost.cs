using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Integration;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static readonly EventOrchestratorV1CardPolicyDefinition[] Definitions =
    {
        Definition("fixture_add_three", "FIXTURE.ADD", CardSelectionV1Operation.Add,
            3, CardSelectionV1CommitMode.AutoAtMax, EventOrchestratorV1CardDomainSource.GeneratedAtAdmission, 6),
        Definition("fixture_remove_two", "FIXTURE.REMOVE", CardSelectionV1Operation.Remove,
            2, CardSelectionV1CommitMode.PreviewConfirm, EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 5),
        Definition("fixture_upgrade_two", "FIXTURE.UPGRADE", CardSelectionV1Operation.Upgrade,
            2, CardSelectionV1CommitMode.PreviewConfirm, EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 5),
        Definition("fixture_transform_two", "FIXTURE.TRANSFORM", CardSelectionV1Operation.Transform,
            2, CardSelectionV1CommitMode.PreviewConfirm, EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 5),
    };

    private static int Main(string[] args)
    {
        EventOrchestratorV1WireService? service = null;
        try
        {
            if (args.Length != 1 || args[0] is not ("all_cards" or "mixed")) return 2;
            Surface.Reset();
            Scenario scenario = args[0] == "all_cards" ? AllCards() : Mixed();
            service = new EventOrchestratorV1WireService(
                Nonce, new EventOrchestratorV1Session(Nonce, scenario.Parent), Definitions);
            string? line;
            while ((line = Console.ReadLine()) is not null)
            {
                using JsonDocument document = JsonDocument.Parse(line);
                JsonElement root = document.RootElement;
                byte[]? request = root.GetProperty("body").ValueKind == JsonValueKind.Null
                    ? null : Convert.FromBase64String(root.GetProperty("body").GetString()!);
                byte[] response;
                try
                {
                    response = service.Handle(root.GetProperty("method").GetString(),
                        root.GetProperty("route").GetString(), request);
                }
                finally { if (request is not null) Array.Clear(request); }
                try
                {
                    Console.WriteLine(JsonSerializer.Serialize(new
                    {
                        body = Convert.ToBase64String(response),
                        parent_dispatches = Surface.Dispatches,
                        item_dispatches = scenario.Item?.Item?.DispatchCount ?? 0,
                        card_dispatches = scenario.Cards.Sum(factory => factory.Card?.DispatchCount ?? 0),
                        disposed_children = scenario.Cards.Sum(factory => factory.Card?.DisposeCount ?? 0) +
                            (scenario.Item?.Item?.DisposeCount ?? 0),
                    }));
                    Console.Out.Flush();
                }
                finally { Array.Clear(response); }
            }
            service.Dispose(); service = null;
            int disposed = scenario.Cards.Sum(factory => factory.Card?.DisposeCount ?? 0) +
                (scenario.Item?.Item?.DisposeCount ?? 0);
            int created = scenario.Cards.Count(factory => factory.Card is not null);
            if (disposed != created) return 1;
            return 0;
        }
        catch
        {
            try { service?.Dispose(); } catch { }
            return 1;
        }
    }

    private static Scenario AllCards()
    {
        ActualFactory[] cards = Definitions.Select(definition =>
            new ActualFactory(definition.Bind(definition.MinimumDomainCount))).ToArray();
        var captures = new List<EventOrchestratorV1SurfaceCapture>();
        foreach (ActualFactory factory in cards)
        {
            Surface surface = new(factory.Policy.ParentStableId, factory,
                EventOrchestratorV1CapabilityKind.SupportedCardSelection);
            captures.Add(surface.Parent()); captures.Add(surface.Parent());
            captures.Add(surface.Child(new object()));
        }
        Surface proceed = Surface.Proceed();
        captures.Add(proceed.Parent()); captures.Add(proceed.Parent());
        return new Scenario(new ParentAdapter(captures), cards, null);
    }

    private static Scenario Mixed()
    {
        ActualFactory item = new(item: true);
        ActualFactory optional = new(item: true);
        ActualFactory card = new(Definitions[0].Bind(6));
        Surface ordinary = new("FIXTURE.ORDINARY", optional,
            EventOrchestratorV1CapabilityKind.OrdinaryItemEligible);
        Surface itemSurface = new("FIXTURE.ITEM", item,
            EventOrchestratorV1CapabilityKind.OrdinaryItemEligible);
        Surface cardSurface = new(card.Policy.ParentStableId, card,
            EventOrchestratorV1CapabilityKind.SupportedCardSelection);
        Surface proceed = Surface.Proceed();
        var captures = new[]
        {
            ordinary.Parent(), ordinary.Parent(),
            itemSurface.Parent(), itemSurface.Parent(), itemSurface.Child(new object()),
            cardSurface.Parent(), cardSurface.Parent(), cardSurface.Child(new object()),
            proceed.Parent(), proceed.Parent(),
        };
        return new Scenario(new ParentAdapter(captures), new[] { card }, item);
    }

    private static EventOrchestratorV1CardPolicyDefinition Definition(
        string id, string key, CardSelectionV1Operation operation, int count,
        CardSelectionV1CommitMode commit, EventOrchestratorV1CardDomainSource source, int domain) =>
        EventOrchestratorV1CardPolicyDefinition.CreateForTests(
            id, key, operation, count, count, commit, source, domain, domain);

    private sealed record Scenario(ParentAdapter Parent, ActualFactory[] Cards, ActualFactory? Item);

    private sealed class ParentAdapter : IEventOrchestratorV1NativeAdapter
    {
        private readonly Queue<EventOrchestratorV1SurfaceCapture> _captures;
        internal ParentAdapter(IEnumerable<EventOrchestratorV1SurfaceCapture> captures) => _captures = new(captures);
        public EventOrchestratorV1SurfaceCapture CaptureSurface() => _captures.Dequeue();
        public EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending) =>
            new(Surface.Run, Surface.Player, Surface.Room, Surface.Map,
                mapOpen: true, travelEnabled: true, traveling: false);
        public void Dispose() { }
    }

    private sealed class Surface
    {
        internal static readonly object Run = new(), Player = new(), Room = new(), Map = new(), Event = new();
        internal static int Dispatches;
        private readonly string _key;
        private readonly IEventOrchestratorV1ChildFactory? _factory;
        private readonly EventOrchestratorV1CapabilityKind _capability;
        private readonly object _button = new(), _option = new(), _controller = new();
        internal Surface(string key, IEventOrchestratorV1ChildFactory? factory,
            EventOrchestratorV1CapabilityKind capability)
        { _key = key; _factory = factory; _capability = capability; }
        internal static void Reset() => Dispatches = 0;
        internal static Surface Proceed() =>
            new("PROCEED", null, EventOrchestratorV1CapabilityKind.Proceed);
        internal EventOrchestratorV1SurfaceCapture Parent()
        {
            bool proceed = _capability == EventOrchestratorV1CapabilityKind.Proceed;
            var candidate = new EventOrchestratorV1NativeCandidate(
                0, _key, "bounded \"<>& café\\ntext", true, true, false, false, proceed,
                _button, _option, _controller, () => Dispatches++, _capability,
                _factory?.Policy.ExpectedDomainCount ?? 0, _factory?.Policy, _factory);
            return EventOrchestratorV1SurfaceCapture.Parent(
                Run, Player, Room, Map, Event, proceed, false, false, false, new[] { candidate });
        }
        internal EventOrchestratorV1SurfaceCapture Child(object screen) =>
            EventOrchestratorV1SurfaceCapture.Child(
                Run, Player, Room, Map, Event, screen, _factory!.Policy, _factory);
    }

    private sealed class ActualFactory : IEventOrchestratorV1ChildFactory
    {
        private readonly bool _item;
        internal ActualFactory(bool item)
        { _item = item; Policy = EventOrchestratorV1ChildPolicy.ItemReward(); }
        internal ActualFactory(EventOrchestratorV1ChildPolicy policy)
        { Policy = policy; _item = false; }
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
            Card = new CardFixture(correlation, accepted, screen, Policy);
            return new EventOrchestratorV1CardChildBroker(
                correlation, accepted, screen, Card, Guard);
        }
    }

    private sealed class ItemFixture : IItemV1NativeAdapter
    {
        private readonly object _run = new(), _player = new(), _screen = new();
        private readonly object _button = new(), _reward = new(), _model = new();
        internal int DispatchCount { get; private set; }
        internal int DisposeCount { get; private set; }
        public ItemV1SurfaceCapture CaptureSurface()
        {
            var offer = new ItemV1NativeOffer(0, ItemV1ItemKind.Relic, "Relic_A", true,
                false, true, true, _button, _reward, _model, () => DispatchCount++);
            return ItemV1SurfaceCapture.Available(_run, _player, _screen, 0,
                new[] { offer }, Array.Empty<ItemV1PotionSlotBinding>());
        }
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) =>
            new(_run, _player, _reward, _model, "Relic_A", true, _model, "Relic_A", 0,
                Array.Empty<ItemV1PotionSlotBinding>());
        public void Dispose() => DisposeCount++;
    }

    private sealed class CardFixture : ICardSelectionV1NativeAdapter
    {
        private readonly object _receipt, _run, _player, _room, _map, _option, _controller, _screen;
        private readonly object _task = new(), _preview = new(), _previewControl = new(), _confirmControl = new();
        private readonly object[] _models, _holders, _nodes, _replacements;
        private readonly bool[] _selected;
        private readonly Action[] _selectActions;
        private readonly Action _previewDispatch, _confirmDispatch;
        private readonly CardSelectionV1Operation _operation;
        private readonly int _count;
        private readonly CardSelectionV1CommitMode _commit;
        private readonly CardSelectionV1DeckCard[] _baseline;
        private CardSelectionV1Phase _phase = CardSelectionV1Phase.Selecting;
        private CardSelectionV1TaskState _taskState = CardSelectionV1TaskState.Incomplete;
        private bool _selectorTop = true, _selectorClosed, _previewOpen, _effectObserved;
        private object[] _taskResult = Array.Empty<object>(), _previewOriginals = Array.Empty<object>();
        private CardSelectionV1Replacement[] _replacementRows = Array.Empty<CardSelectionV1Replacement>();
        private readonly List<CardSelectionV1DeckCard> _deck = new();
        internal int DispatchCount { get; private set; }
        internal int DisposeCount { get; private set; }

        internal CardFixture(EventOrchestratorV1ChildCorrelation correlation,
            EventOrchestratorV1AcceptedContext accepted, object screen,
            EventOrchestratorV1ChildPolicy policy)
        {
            _receipt = correlation; _run = accepted.RunIdentity; _player = accepted.PlayerIdentity;
            _room = accepted.RoomIdentity; _map = accepted.MapIdentity;
            _option = accepted.OptionIdentity; _controller = accepted.ControllerIdentity; _screen = screen;
            _operation = policy.CardOperation; _count = policy.MaxSelect; _commit = policy.CardCommitMode;
            int domain = policy.ExpectedDomainCount;
            _models = Enumerable.Range(0, domain).Select(_ => new object()).ToArray();
            _holders = Enumerable.Range(0, domain).Select(_ => new object()).ToArray();
            _nodes = Enumerable.Range(0, domain).Select(_ => new object()).ToArray();
            _replacements = Enumerable.Range(0, domain).Select(_ => new object()).ToArray();
            _selected = new bool[domain]; _selectActions = new Action[domain];
            if (_operation == CardSelectionV1Operation.Add)
            {
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Base_A", 0));
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Base_B", 0));
            }
            else
            {
                for (int index = 0; index < domain; index++)
                    _deck.Add(new CardSelectionV1DeckCard(_models[index], "Card_" + index, 0));
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Other", 0));
            }
            _baseline = _deck.ToArray();
            _previewDispatch = () => { DispatchCount++; EnterPreview(SelectedSlots()); };
            _confirmDispatch = () => { DispatchCount++; Complete(SelectedSlots()); };
            for (int index = 0; index < domain; index++)
            {
                int slot = index;
                _selectActions[index] = () =>
                {
                    DispatchCount++; _selected[slot] = true;
                    if (_selected.Count(value => value) != _count) return;
                    int[] selected = SelectedSlots();
                    if (_commit == CardSelectionV1CommitMode.AutoAtMax) Complete(selected);
                };
            }
        }

        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            int[] slots = SelectedSlots();
            CardSelectionV1NativeControl? preview = _phase == CardSelectionV1Phase.Selecting &&
                _commit == CardSelectionV1CommitMode.PreviewConfirm && slots.Length >= _count
                ? new CardSelectionV1NativeControl(_previewControl, true, true,
                    _previewDispatch) : null;
            CardSelectionV1NativeControl? confirm = _previewOpen
                ? new CardSelectionV1NativeControl(_confirmControl, true, true,
                    _confirmDispatch) : null;
            CardSelectionV1NativeCandidate[] candidates = Enumerable.Range(0, _models.Length)
                .Select(index => new CardSelectionV1NativeCandidate(index, "Card_" + index,
                    _holders[index], _models[index], _nodes[index], 0, true, true,
                    _selected[index], true, _selectActions[index])).ToArray();
            return new CardSelectionV1SurfaceCapture(
                CardSelectionV1SurfaceStatus.Available, _receipt, _run, _player, _room, _map,
                _option, _controller, _screen, _task, _previewOpen ? _preview : null,
                CardSelectionV1ParentKind.Event, _operation, _count, _count, _commit,
                _phase, _selectorTop, _selectorClosed, _previewOpen, true, _models.Length, true,
                _taskState, _effectObserved, _taskResult, _previewOriginals, candidates, _deck,
                _replacementRows, preview, confirm);
        }

        private int[] SelectedSlots() => Enumerable.Range(0, _selected.Length)
            .Where(index => _selected[index]).ToArray();

        private void EnterPreview(int[] slots)
        {
            _phase = CardSelectionV1Phase.Preview; _selectorTop = false; _previewOpen = true;
            _previewOriginals = slots.Select(slot => _models[slot]).ToArray();
        }

        private void Complete(int[] slots)
        {
            _taskState = CardSelectionV1TaskState.Succeeded;
            _taskResult = slots.Reverse().Select(slot => _models[slot]).ToArray();
            _phase = CardSelectionV1Phase.Submitted; _selectorTop = false;
            _selectorClosed = true; _previewOpen = false; _previewOriginals = Array.Empty<object>();
            ApplyEffect(slots); _effectObserved = true;
        }

        private void ApplyEffect(int[] slots)
        {
            _deck.Clear();
            if (_operation == CardSelectionV1Operation.Add)
            {
                _deck.Add(_baseline[0]);
                foreach (int slot in slots)
                    _deck.Add(new CardSelectionV1DeckCard(_models[slot], "Card_" + slot, 0));
                for (int index = 1; index < _baseline.Length; index++) _deck.Add(_baseline[index]);
                return;
            }
            var replacements = new List<CardSelectionV1Replacement>();
            foreach (CardSelectionV1DeckCard card in _baseline)
            {
                int slot = Array.FindIndex(_models, model => ReferenceEquals(model, card.ModelIdentity));
                bool selected = slots.Contains(slot);
                if (_operation == CardSelectionV1Operation.Remove && selected) continue;
                if (_operation == CardSelectionV1Operation.Upgrade && selected)
                    _deck.Add(new CardSelectionV1DeckCard(card.ModelIdentity, card.StableKey, card.UpgradeLevel + 1));
                else if (_operation == CardSelectionV1Operation.Transform && selected)
                {
                    string key = "Replacement_" + slot;
                    _deck.Add(new CardSelectionV1DeckCard(_replacements[slot], key, 0));
                    replacements.Add(new CardSelectionV1Replacement(
                        card.ModelIdentity, _replacements[slot], key, 0));
                }
                else _deck.Add(card);
            }
            _replacementRows = replacements.ToArray();
        }

        public void Dispose() => DisposeCount++;
    }
}
