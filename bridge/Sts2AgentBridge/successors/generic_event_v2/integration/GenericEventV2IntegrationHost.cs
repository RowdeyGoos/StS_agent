using System;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV2;

// Inert adapter only: production parent, frozen card state machine and wire run
// unchanged. No target assemblies or native controller substitute are used.
internal static class GenericEventV2IntegrationHost
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int Main(string[] args)
    {
        if (args.Length != 1) return 2;
        using var adapter = new InertEvent(args[0]);
        using var session = new GenericEventV2Session(adapter, Nonce);
        using var service = new GenericEventV2WireService(Nonce, session);
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
                card_dispatches = adapter.CardDispatches,
                before_child_effects = adapter.BeforeEffects,
                disposed_children = adapter.DisposedChildren,
                remaining_keys = adapter.Card?.RemainingKeys ?? Array.Empty<string>(),
                remaining_levels = adapter.Card?.RemainingLevels ?? Array.Empty<int>(),
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

    private sealed class InertEvent : IGenericEventV2NativeAdapter
    {
        private readonly string _scenario;
        private readonly object[] _options = { new(), new(), new() };
        private object _screen = new(), _admissionIdentity = new();
        private readonly bool _removal, _mixed;
        private readonly int _min, _max, _domain;
        private GenericEventV2Admission? _admission;
        private int _stage, _delay;
        private bool _pending;
        internal InertCard? Card;
        internal int Dispatches, BeforeEffects;
        private int _previousCardDispatches, _previousDisposals;
        internal int CardDispatches => _previousCardDispatches + (Card?.Dispatches ?? 0);
        internal int DisposedChildren => _previousDisposals + (Card?.Disposals ?? 0);
        private bool ChildStage => _stage == 0 || (_mixed && _stage == 1);
        private bool CurrentRemoval => _removal || (_mixed && _stage == 1);
        internal InertEvent(string scenario)
        {
            _scenario = scenario; _removal = scenario.StartsWith("removal_", StringComparison.Ordinal); _mixed = scenario == "mixed_families";
            _domain = !_removal ? 3 : scenario == "removal_eight" ? 9 : 5;
            _min = !_removal ? 1 : scenario == "removal_eight" ? 8 : scenario.Contains("variable", StringComparison.Ordinal) || scenario == "removal_reverse" ? 1 : 2;
            _max = !_removal ? 1 : scenario == "removal_eight" ? 8 : _min == 1 ? 3 : 2;
        }
        internal void Advance() { if (_delay > 0) _delay--; }
        public GenericEventV2NativeCapture Capture()
        {
            if (_stage == 3) return new("map", true, Array.Empty<GenericEventV2NativeOption>());
            if (_pending && ChildStage)
            {
                if (_scenario == "unsupported") return new("unsupported", false, Array.Empty<GenericEventV2NativeOption>());
                if (_scenario == "never_child" || _delay > 0) return new("waiting", false, Array.Empty<GenericEventV2NativeOption>());
                return new("child", false, Array.Empty<GenericEventV2NativeOption>(), _screen, _admission);
            }
            return new("parent", _stage == 2, new[] {
                new GenericEventV2NativeOption(_options[_stage], _scenario + ".PAGE_" + _stage,
                    _stage == 2 ? "Proceed" : "Public option for " + _scenario,
                    true, false, _stage == 2),
            });
        }
        public void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId)
        {
            if (!ReferenceEquals(candidateIdentity, _options[_stage])) throw new InvalidOperationException();
            Dispatches++;
            if (!ChildStage) { _stage++; return; }
            _pending = true; BeforeEffects++;
            if (_scenario is "uncertain" or "removal_uncertain") throw new InvalidOperationException("Callback failed after effect.");
            _delay = _scenario is "delayed" or "removal_delayed" ? 4 : 0;
            int minimum = _mixed && _stage == 1 ? 2 : _min;
            int maximum = _mixed && _stage == 1 ? 2 : _max;
            IReadOnlyList<CardSelectionV1DeckCard>? inherited = _mixed && _stage == 1 ? Card!.Deck : null;
            if (Card is not null) { _previousCardDispatches += Card.Dispatches; _previousDisposals += Card.Disposals; }
            _screen = new object(); _admissionIdentity = new object();
            _admission = new(_admissionIdentity, CurrentRemoval ? "remove" : "upgrade", minimum, maximum, "preview_confirm", _domain);
            var context = new CardSelectionV1ParentContext(nonce, CardSelectionV1ParentKind.Event,
                decisionId, actionId, new object(), new object(), new object(), new object(),
                new object(), candidateIdentity, this, CurrentRemoval ? CardSelectionV1Operation.Remove : CardSelectionV1Operation.Upgrade,
                minimum, maximum, CardSelectionV1CommitMode.PreviewConfirm, _domain);
            Card = new InertCard(context, _screen, _scenario is "early_delta" or "removal_early_delta",
                _scenario == "removal_delayed_completion", inherited);
        }
        public CardSelectionV1Session CreateChild(object admissionIdentity)
        {
            if (!ReferenceEquals(admissionIdentity, _admissionIdentity) || _scenario == "admission_changed")
                throw new InvalidOperationException("Changed admission.");
            return new(Card!.Context, Card);
        }
        public void CompleteParent() { if (ChildStage) { _pending = false; _stage++; } }
        public void Dispose() { }
    }

    private sealed class InertCard : ICardSelectionV1NativeAdapter
    {
        internal readonly CardSelectionV1ParentContext Context;
        private readonly object _screen, _task = new(), _preview = new(), _previewControl = new(), _confirmControl = new();
        private readonly object[] _models, _holders, _nodes;
        private readonly bool[] _selected;
        private readonly int[] _baselineLevels;
        private readonly Action[] _select;
        private readonly Action _previewDispatch, _confirmDispatch;
        private readonly bool _early, _delayedCompletion;
        private int _completionDelay;
        private CardSelectionV1Phase _phase = CardSelectionV1Phase.Selecting;
        private bool _completed;
        internal int Dispatches, Disposals;
        private bool Removal => Context.Operation == CardSelectionV1Operation.Remove;
        private int[] Selected => Enumerable.Range(0, _models.Length).Where(i => _selected[i]).ToArray();
        private int[] Remaining => Enumerable.Range(0, _models.Length).Where(i => !(_completed && Removal && _selected[i])).ToArray();
        internal string[] RemainingKeys => Remaining.Select(i => "Card_" + i).ToArray();
        internal int[] RemainingLevels => Remaining.Select(i => _baselineLevels[i] + (_completed && !Removal && _selected[i] ? 1 : 0)).ToArray();
        internal CardSelectionV1DeckCard[] Deck => Remaining.Select(i => new CardSelectionV1DeckCard(_models[i], "Card_" + i,
            _baselineLevels[i] + (_completed && !Removal && _selected[i] ? 1 : 0))).ToArray();
        internal InertCard(CardSelectionV1ParentContext context, object screen, bool early, bool delayedCompletion, IReadOnlyList<CardSelectionV1DeckCard>? inherited = null)
        {
            Context = context; _screen = screen; _early = early; _delayedCompletion = delayedCompletion;
            _models = inherited is null ? Enumerable.Range(0, context.ExpectedDomainCount).Select(_ => new object()).ToArray() : inherited.Select(c => c.ModelIdentity).ToArray();
            _baselineLevels = inherited is null ? new int[_models.Length] : inherited.Select(c => c.UpgradeLevel).ToArray();
            _holders = _models.Select(_ => new object()).ToArray(); _nodes = _models.Select(_ => new object()).ToArray();
            _selected = new bool[_models.Length];
            _select = Enumerable.Range(0, _models.Length).Select(i => (Action)(() => {
                Dispatches++; _selected[i] = true;
                if (Removal && Selected.Length == Context.MaxSelect) _phase = CardSelectionV1Phase.Preview;
            })).ToArray();
            _previewDispatch = () => { Dispatches++; _phase = CardSelectionV1Phase.Preview; };
            _confirmDispatch = () => {
                Dispatches++; _phase = CardSelectionV1Phase.Submitted; _completed = true;
                _completionDelay = _early || _delayedCompletion ? 4 : 0;
            };
        }
        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            bool witness = _completed && _completionDelay == 0;
            bool taskDone = _completed && (!_early || witness);
            if (_completionDelay > 0) _completionDelay--;
            bool preview = _phase == CardSelectionV1Phase.Preview;
            var candidates = Enumerable.Range(0, _models.Length).Select(i => new CardSelectionV1NativeCandidate(
                i, "Card_" + i, _holders[i], _models[i], _nodes[i], _baselineLevels[i], true, true,
                _selected[i], true, _select[i])).ToArray();
            var deck = Deck;
            return new(CardSelectionV1SurfaceStatus.Available,
                Context.ParentReceiptIdentity, Context.RunIdentity, Context.PlayerIdentity,
                Context.RoomIdentity, Context.MapIdentity, Context.ParentOptionIdentity,
                Context.ParentControllerIdentity, _screen, _task, preview ? _preview : null,
                CardSelectionV1ParentKind.Event, Context.Operation, Context.MinSelect, Context.MaxSelect,
                CardSelectionV1CommitMode.PreviewConfirm, _phase,
                _phase == CardSelectionV1Phase.Selecting, _completed, preview, true, _models.Length, true,
                taskDone ? CardSelectionV1TaskState.Succeeded : CardSelectionV1TaskState.Incomplete,
                witness, taskDone ? Selected.Reverse().Select(i => _models[i]).ToArray() : Array.Empty<object>(),
                preview ? Selected.Reverse().Select(i => _models[i]).ToArray() : Array.Empty<object>(),
                candidates, deck, Array.Empty<CardSelectionV1Replacement>(),
                _phase == CardSelectionV1Phase.Selecting && Selected.Length >= Context.MinSelect ?
                    new CardSelectionV1NativeControl(_previewControl, true, true, _previewDispatch) : null,
                preview ? new CardSelectionV1NativeControl(_confirmControl, true, true, _confirmDispatch) : null);
        }
        public void Dispose() { Disposals++; }
    }
}
