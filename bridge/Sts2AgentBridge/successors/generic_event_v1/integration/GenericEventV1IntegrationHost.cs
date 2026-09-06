using System;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV1;

// Inert adapter only: the production parent, frozen card state machine and wire
// service below execute unchanged. This fixture never references target assemblies.
internal static class GenericEventV1IntegrationHost
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int Main(string[] args)
    {
        if (args.Length != 1) return 2;
        using var adapter = new InertEvent(args[0]);
        using var session = new GenericEventV1Session(adapter, Nonce);
        using var service = new GenericEventV1WireService(Nonce, session);
        for (int count = 0; count < 2200; count++)
        {
            string? line = ReadLineBounded();
            if (line is null) return 0;
            using JsonDocument request = JsonDocument.Parse(line);
            var root = request.RootElement;
            if (!root.EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "method", "route", "body" })) return 3;
            string method = root.GetProperty("method").GetString()!;
            byte[]? body = root.GetProperty("body").ValueKind == JsonValueKind.Null ? null :
                Convert.FromBase64String(root.GetProperty("body").GetString()!);
            if (method == "GET") adapter.Advance();
            byte[] response = service.Handle(method, root.GetProperty("route").GetString(), body);
            Console.WriteLine(JsonSerializer.Serialize(new {
                body = Convert.ToBase64String(response), parent_dispatches = adapter.Dispatches,
                card_dispatches = adapter.Card?.Dispatches ?? 0,
                before_child_effects = adapter.BeforeEffects,
                disposed_children = adapter.Card?.Disposals ?? 0,
            }));
            if (body is not null) Array.Clear(body);
            Array.Clear(response);
        }
        return 4;
    }
    private static string? ReadLineBounded()
    {
        var chars = new char[8192]; int used = 0;
        while (true)
        {
            int next = Console.Read();
            if (next < 0) return used == 0 ? null : throw new InvalidOperationException("Truncated line.");
            if (next == '\n') return new string(chars, 0, used);
            if (used == chars.Length) throw new InvalidOperationException("Oversized line.");
            chars[used++] = (char)next;
        }
    }

    private sealed class InertEvent : IGenericEventV1NativeAdapter
    {
        private readonly string _scenario;
        private readonly object[] _options = { new(), new(), new() };
        private readonly object _screen = new();
        private int _stage, _delay;
        private bool _pending;
        internal InertCard? Card;
        internal int Dispatches, BeforeEffects;
        internal InertEvent(string scenario) { _scenario = scenario; }
        internal void Advance() { if (_delay > 0) _delay--; }
        public GenericEventV1NativeCapture Capture()
        {
            if (_stage == 3) return new("map", true, Array.Empty<GenericEventV1NativeOption>());
            if (_pending && _stage == 0)
            {
                if (_scenario == "unsupported") return new("unsupported", false, Array.Empty<GenericEventV1NativeOption>());
                if (_scenario == "never_child" || _delay > 0) return new("waiting", false, Array.Empty<GenericEventV1NativeOption>());
                return new("child", false, Array.Empty<GenericEventV1NativeOption>(), _screen, 3);
            }
            return new("parent", _stage == 2, new[] {
                new GenericEventV1NativeOption(_options[_stage], _scenario + ".PAGE_" + _stage,
                    _stage == 2 ? "Proceed" : "Public option for " + _scenario,
                    true, false, _stage == 2),
            });
        }
        public void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId)
        {
            if (!ReferenceEquals(candidateIdentity, _options[_stage])) throw new InvalidOperationException();
            Dispatches++;
            if (_stage != 0) { _stage++; return; }
            _pending = true; BeforeEffects++;
            if (_scenario == "uncertain") throw new InvalidOperationException("Callback failed after effect.");
            _delay = _scenario == "delayed" ? 4 : 0;
            var context = new CardSelectionV1ParentContext(nonce, CardSelectionV1ParentKind.Event,
                decisionId, actionId, new object(), new object(), new object(), new object(),
                new object(), candidateIdentity, this, CardSelectionV1Operation.Upgrade, 1, 1,
                CardSelectionV1CommitMode.PreviewConfirm, 3);
            Card = new InertCard(context, _screen, _scenario == "early_delta");
        }
        public CardSelectionV1Session CreateChild() => new(Card!.Context, Card);
        public void CompleteParent() { if (_stage == 0) { _pending = false; _stage = 1; } }
        public void Dispose() { }
    }

    private sealed class InertCard : ICardSelectionV1NativeAdapter
    {
        internal readonly CardSelectionV1ParentContext Context;
        private readonly object _screen, _task = new(), _preview = new(), _previewControl = new(), _confirmControl = new();
        private readonly object[] _models = { new(), new(), new() }, _holders = { new(), new(), new() }, _nodes = { new(), new(), new() };
        private readonly Action[] _select;
        private readonly Action _previewDispatch, _confirmDispatch;
        private readonly bool _early;
        private int _selected = -1, _completionDelay;
        private CardSelectionV1Phase _phase = CardSelectionV1Phase.Selecting;
        private bool _completed;
        internal int Dispatches, Disposals;
        internal InertCard(CardSelectionV1ParentContext context, object screen, bool early)
        {
            Context = context; _screen = screen; _early = early;
            _select = Enumerable.Range(0, 3).Select(i => (Action)(() => { Dispatches++; _selected = i; })).ToArray();
            _previewDispatch = () => { Dispatches++; _phase = CardSelectionV1Phase.Preview; };
            _confirmDispatch = () => {
                Dispatches++; _phase = CardSelectionV1Phase.Submitted; _completed = true;
                _completionDelay = _early ? 4 : 0;
            };
        }
        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            bool witness = _completed && _completionDelay == 0;
            if (_completionDelay > 0) _completionDelay--;
            bool preview = _phase == CardSelectionV1Phase.Preview;
            var candidates = Enumerable.Range(0, 3).Select(i => new CardSelectionV1NativeCandidate(
                i, "Card_" + i, _holders[i], _models[i], _nodes[i], 0, true, true,
                _selected == i, true, _select[i])).ToArray();
            var deck = Enumerable.Range(0, 3).Select(i => new CardSelectionV1DeckCard(
                _models[i], "Card_" + i, _completed && _selected == i ? 1 : 0)).ToArray();
            return new(CardSelectionV1SurfaceStatus.Available,
                Context.ParentReceiptIdentity, Context.RunIdentity, Context.PlayerIdentity,
                Context.RoomIdentity, Context.MapIdentity, Context.ParentOptionIdentity,
                Context.ParentControllerIdentity, _screen, _task, preview ? _preview : null,
                CardSelectionV1ParentKind.Event, CardSelectionV1Operation.Upgrade, 1, 1,
                CardSelectionV1CommitMode.PreviewConfirm, _phase,
                _phase == CardSelectionV1Phase.Selecting, _completed, preview, true, 3, true,
                witness ? CardSelectionV1TaskState.Succeeded : CardSelectionV1TaskState.Incomplete,
                witness, witness ? new[] { _models[_selected] } : Array.Empty<object>(),
                preview ? new[] { _models[_selected] } : Array.Empty<object>(),
                candidates, deck, Array.Empty<CardSelectionV1Replacement>(),
                _phase == CardSelectionV1Phase.Selecting && _selected >= 0 ?
                    new CardSelectionV1NativeControl(_previewControl, true, true, _previewDispatch) : null,
                preview ? new CardSelectionV1NativeControl(_confirmControl, true, true, _confirmDispatch) : null);
        }
        public void Dispose() { Disposals++; }
    }
}
