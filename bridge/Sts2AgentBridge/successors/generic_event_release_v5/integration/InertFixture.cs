using System;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV3;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV5;
internal static class InertFixture
{
    internal sealed class InertEvent : IGenericEventV3NativeAdapter
    {
        private readonly string _scenario;
        private readonly object[] _options = { new(), new(), new(), new() };
        private object _screen = new(), _admissionIdentity = new();
        private readonly bool _removal, _mixed, _reward, _three;
        private readonly int _min, _max, _domain;
        private GenericEventV3Admission? _admission;
        private int _stage, _delay;
        private bool _pending;
        internal InertCard? Card;
        internal int Dispatches, BeforeEffects;
        private int _previousCardDispatches, _previousDisposals;
        internal int CardDispatches => _previousCardDispatches + (Card?.Dispatches ?? 0);
        internal int DisposedChildren => _previousDisposals + (Card?.Disposals ?? 0);
        private int ProceedStage => _three ? 3 : 2;
        private bool ChildStage => _stage == 0 || (_mixed && _stage == 1) || (_three && _stage == 2);
        private bool CurrentAdd => _reward || (_three && _stage == 2);
        private bool CurrentRemoval => _removal || (_mixed && _stage == 1);
        internal InertEvent(string scenario)
        {
            _scenario = scenario; _removal = scenario.StartsWith("removal_", StringComparison.Ordinal); _three = scenario == "mixed_three"; _mixed = scenario == "mixed_families" || _three; _reward = scenario.StartsWith("reward_", StringComparison.Ordinal);
            _domain = _reward ? (scenario.Contains("eight", StringComparison.Ordinal) ? 9 : 5) : !_removal ? 3 : scenario == "removal_eight" ? 9 : 5;
            _min = _reward ? (scenario.Contains("eight", StringComparison.Ordinal) ? 8 : scenario.Contains("variable", StringComparison.Ordinal) ? 1 : 2) : !_removal ? 1 : scenario == "removal_eight" ? 8 : scenario.Contains("variable", StringComparison.Ordinal) || scenario == "removal_reverse" ? 1 : 2;
            _max = _reward ? (scenario.Contains("eight", StringComparison.Ordinal) ? 8 : scenario.Contains("variable", StringComparison.Ordinal) ? 3 : 2) : !_removal ? 1 : scenario == "removal_eight" ? 8 : _min == 1 ? 3 : 2;
        }
        internal void Advance() { if (_delay > 0) _delay--; }
        public GenericEventV3NativeCapture Capture()
        {
            if (_stage == ProceedStage + 1) return new("map", true, Array.Empty<GenericEventV3NativeOption>());
            if (_pending && ChildStage)
            {
                if (_scenario == "unsupported") return new("unsupported", false, Array.Empty<GenericEventV3NativeOption>());
                if (_scenario == "never_child" || _delay > 0) return new("waiting", false, Array.Empty<GenericEventV3NativeOption>());
                return new("child", false, Array.Empty<GenericEventV3NativeOption>(), _screen, _admission);
            }
            return new("parent", _stage == ProceedStage, new[] {
                new GenericEventV3NativeOption(_options[_stage], _scenario + ".PAGE_" + _stage,
                    _stage == ProceedStage ? "Proceed" : "Public option for " + _scenario,
                    true, false, _stage == ProceedStage),
            });
        }
        public void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId)
        {
            if (!ReferenceEquals(candidateIdentity, _options[_stage])) throw new InvalidOperationException();
            Dispatches++;
            if (!ChildStage) { _stage++; return; }
            _pending = true; BeforeEffects++;
            if (_scenario is "uncertain" or "removal_uncertain") throw new InvalidOperationException("Callback failed after effect.");
            _delay = _scenario is "delayed" or "removal_delayed" or "reward_auto_delayed_creation" ? 4 : 0;
            int minimum = _mixed && _stage > 0 ? 2 : _min;
            int maximum = _mixed && _stage > 0 ? 2 : _max;
            int domain = _three && _stage == 2 ? 5 : _domain;
            string mode = CurrentAdd ? (_scenario.Contains("explicit", StringComparison.Ordinal) || _three ? "explicit_confirm" : "auto_at_max") : "preview_confirm";
            IReadOnlyList<CardSelectionV1DeckCard>? inherited = _mixed && _stage > 0 ? Card!.Deck : null;
            if (Card is not null) { _previousCardDispatches += Card.Dispatches; _previousDisposals += Card.Disposals; }
            _screen = new object(); _admissionIdentity = new object();
            _admission = new(_admissionIdentity, CurrentAdd ? "add" : CurrentRemoval ? "remove" : "upgrade", minimum, maximum, mode, domain);
            var context = new CardSelectionV1ParentContext(nonce, CardSelectionV1ParentKind.Event,
                decisionId, actionId, new object(), new object(), new object(), new object(),
                new object(), candidateIdentity, this, CurrentAdd ? CardSelectionV1Operation.Add : CurrentRemoval ? CardSelectionV1Operation.Remove : CardSelectionV1Operation.Upgrade,
                minimum, maximum, mode == "auto_at_max" ? CardSelectionV1CommitMode.AutoAtMax : mode == "explicit_confirm" ? CardSelectionV1CommitMode.ExplicitConfirm : CardSelectionV1CommitMode.PreviewConfirm, domain);
            Card = new InertCard(context, _screen, _scenario is "early_delta" or "removal_early_delta",
                _scenario is "removal_delayed_completion" or "reward_auto_partial" or "reward_explicit_delayed_completion", inherited,
                _scenario.Contains("sorted", StringComparison.Ordinal), _scenario.Contains("partial_terminal", StringComparison.Ordinal) ? "partial" : _scenario.Contains("empty", StringComparison.Ordinal) ? "empty" : "");
        }
        public CardSelectionV1Session CreateChild(object admissionIdentity)
        {
            if (!ReferenceEquals(admissionIdentity, _admissionIdentity) || _scenario == "admission_changed")
                throw new InvalidOperationException("Changed admission.");
            return new(Card!.Context, Card);
        }
        public void CompleteParent() { if (ChildStage) { _pending = false; _stage++; } }
        internal int DisposeCalls; internal bool ThrowFirstDispose { get; set; }
        public void Dispose() { DisposeCalls++; if(ThrowFirstDispose && DisposeCalls==1)throw new InvalidOperationException("Synthetic cleanup failure."); }
    }

    internal sealed class InertCard : ICardSelectionV1NativeAdapter
    {
        internal readonly CardSelectionV1ParentContext Context;
        private readonly object _screen, _task = new(), _preview = new(), _previewControl = new(), _confirmControl = new();
        private readonly object[] _models, _holders, _nodes;
        private readonly bool[] _selected;
        private readonly int[] _levels;
        private readonly string[] _keys;
        private readonly CardSelectionV1DeckCard[] _baseline;
        private readonly Action[] _select;
        private readonly Action _previewDispatch, _confirmDispatch;
        private readonly bool _early, _delayed;
        private readonly string _badEffect;
        private int _completionDelay;
        private CardSelectionV1Phase _phase = CardSelectionV1Phase.Selecting;
        private bool _completed;
        internal int Dispatches, Disposals;
        private bool Removal => Context.Operation == CardSelectionV1Operation.Remove;
        private bool Add => Context.Operation == CardSelectionV1Operation.Add;
        private int[] Selected => Enumerable.Range(0, _models.Length).Where(i => _selected[i]).ToArray();
        internal string[] RemainingKeys => Deck.Select(c => c.StableKey).ToArray();
        internal int[] RemainingLevels => Deck.Select(c => c.UpgradeLevel).ToArray();
        internal CardSelectionV1DeckCard[] Deck
        {
            get
            {
                if (Add)
                {
                    int count = !_completed || _badEffect == "empty" ? 0 : _badEffect == "partial" || (_delayed && _completionDelay >= 3) ? 1 : Selected.Length;
                    return _baseline.Concat(Selected.Take(count).Select(i => new CardSelectionV1DeckCard(_models[i], _keys[i], _levels[i]))).ToArray();
                }
                return Enumerable.Range(0, _models.Length).Where(i => !(_completed && Removal && _selected[i]))
                    .Select(i => new CardSelectionV1DeckCard(_models[i], _keys[i], _levels[i] + (_completed && !Removal && _selected[i] ? 1 : 0))).ToArray();
            }
        }
        internal InertCard(CardSelectionV1ParentContext context, object screen, bool early, bool delayed,
            IReadOnlyList<CardSelectionV1DeckCard>? inherited = null, bool sorted = false, string badEffect = "")
        {
            Context = context; _screen = screen; _early = early; _delayed = delayed; _badEffect = badEffect;
            _models = Add || inherited is null ? Enumerable.Range(0, context.ExpectedDomainCount).Select(_ => new object()).ToArray() : inherited.Select(c => c.ModelIdentity).ToArray();
            _levels = Add || inherited is null ? new int[_models.Length] : inherited.Select(c => c.UpgradeLevel).ToArray();
            _keys = Enumerable.Range(0, _models.Length).Select(i => Add ? "Offer_" + (sorted ? _models.Length - 1 - i : i) : inherited is null ? "Card_" + i : inherited[i].StableKey).ToArray();
            _baseline = inherited?.ToArray() ?? (Add ? new[] { new CardSelectionV1DeckCard(new object(), "Base_0", 0), new CardSelectionV1DeckCard(new object(), "Base_1", 0) } :
                _models.Select((model, i) => new CardSelectionV1DeckCard(model, _keys[i], _levels[i])).ToArray());
            _holders = _models.Select(_ => new object()).ToArray(); _nodes = _models.Select(_ => new object()).ToArray();
            _selected = new bool[_models.Length];
            _select = Enumerable.Range(0, _models.Length).Select(i => (Action)(() => {
                Dispatches++; _selected[i] = true;
                if (Removal && Selected.Length == Context.MaxSelect) _phase = CardSelectionV1Phase.Preview;
                if (Add && Context.CommitMode == CardSelectionV1CommitMode.AutoAtMax && Selected.Length == Context.MaxSelect) Complete();
            })).ToArray();
            _previewDispatch = () => { Dispatches++; _phase = CardSelectionV1Phase.Preview; };
            _confirmDispatch = () => { Dispatches++; Complete(); };
        }
        private void Complete()
        {
            _phase = CardSelectionV1Phase.Submitted; _completed = true;
            _completionDelay = _early || _delayed ? 4 : 0;
        }
        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            bool witness = _completed && _completionDelay == 0;
            bool taskDone = _completed && (!_early || witness);
            bool preview = _phase == CardSelectionV1Phase.Preview;
            var candidates = Enumerable.Range(0, _models.Length).Select(i => new CardSelectionV1NativeCandidate(
                i, _keys[i], _holders[i], _models[i], _nodes[i], _levels[i], true, true,
                _selected[i] && !(Add && _completed), true, _select[i])).ToArray();
            var deck = Deck;
            if (_completionDelay > 0) _completionDelay--;
            return new(CardSelectionV1SurfaceStatus.Available,
                Context.ParentReceiptIdentity, Context.RunIdentity, Context.PlayerIdentity,
                Context.RoomIdentity, Context.MapIdentity, Context.ParentOptionIdentity,
                Context.ParentControllerIdentity, _screen, _task, preview ? _preview : null,
                CardSelectionV1ParentKind.Event, Context.Operation, Context.MinSelect, Context.MaxSelect,
                Context.CommitMode, _phase,
                _phase == CardSelectionV1Phase.Selecting, _completed, preview, true, _models.Length, true,
                taskDone ? CardSelectionV1TaskState.Succeeded : CardSelectionV1TaskState.Incomplete,
                witness, taskDone ? Selected.Reverse().Select(i => _models[i]).ToArray() : Array.Empty<object>(),
                preview ? Selected.Reverse().Select(i => _models[i]).ToArray() : Array.Empty<object>(),
                candidates, deck, Array.Empty<CardSelectionV1Replacement>(),
                !Add && _phase == CardSelectionV1Phase.Selecting && Selected.Length >= Context.MinSelect ?
                    new CardSelectionV1NativeControl(_previewControl, true, true, _previewDispatch) : null,
                preview || (Add && Context.CommitMode == CardSelectionV1CommitMode.ExplicitConfirm && _phase == CardSelectionV1Phase.Selecting && Selected.Length >= Context.MinSelect) ?
                    new CardSelectionV1NativeControl(_confirmControl, true, true, _confirmDispatch) : null);
        }
        public void Dispose() { Disposals++; }
    }
}
