using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

internal static class Program
{
    private static int _checks;

    private static int Main()
    {
        try
        {
#if ORIGINAL_CONTROL
            ReproducesTaskSucceededBeforeClose();
            ReproducesClosedWithCachedPreview();
#else
            SmithCompletedTopThenClosedAndEffectLate();
            SmithImmediateCloseAndEffectPrefixes();
            SmithTaskFailuresAndWrongOriginal();
            SmithContextOverlayDeckAndMapFailures();
            CheeseCompletedTopThenLateEffect();
#endif
            Console.WriteLine(JsonSerializer.Serialize(new SortedDictionary<string, object>
            {
                ["check_count"] = _checks,
                ["schema_version"] = 1,
                ["status"] = "passed",
#if ORIGINAL_CONTROL
                ["suite"] = "card_selection_completion_diagnostic_original",
#else
                ["suite"] = "card_selection_completion_v1_native",
#endif
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

#if !ORIGINAL_CONTROL
    private static void SmithCompletedTopThenClosedAndEffectLate()
    {
        using SmithFixture fixture = new(ConfirmOutcome.SuccessOpen);
        CardSelectionV1Session session = fixture.Session;
        CardSelectionV1Observation initial = Ready(session.Read());
        Accepted(session.Apply(initial.DecisionId, "select:0"));
        CardSelectionV1Observation preview = Ready(session.Read());
        Equal("preview", preview.Phase);
        Accepted(session.Apply(preview.DecisionId, "confirm"));
        CardSelectionV1Observation top = Waiting(session.Read());
        Equal(2, top.PriorResults.Count);
        fixture.CloseSelector();
        Waiting(session.Read());
        fixture.ApplyUpgrade();
        Waiting(session.Read());
        fixture.CompleteRestEffect();
        CardSelectionV1ResolvedResult resolved = Resolved(session.Read());
        Equal(2, resolved.PriorResults.Count);
        Same(resolved, session.Read());
    }

    private static void SmithImmediateCloseAndEffectPrefixes()
    {
        using SmithFixture fixture = new(ConfirmOutcome.SuccessClosed);
        CardSelectionV1Session session = fixture.Session;
        CardSelectionV1Observation initial = Ready(session.Read());
        Accepted(session.Apply(initial.DecisionId, "select:0"));
        CardSelectionV1Observation preview = Ready(session.Read());
        Accepted(session.Apply(preview.DecisionId, "confirm"));
        Waiting(session.Read());
        fixture.ApplyUpgrade();
        Waiting(session.Read());
        fixture.CompleteRestEffect();
        Resolved(session.Read());
    }

    private static void SmithTaskFailuresAndWrongOriginal()
    {
        foreach (ConfirmOutcome outcome in new[] { ConfirmOutcome.Canceled, ConfirmOutcome.Faulted, ConfirmOutcome.WrongOriginal })
        {
            using SmithFixture fixture = new(outcome);
            CardSelectionV1Session session = fixture.Session;
            CardSelectionV1Observation initial = Ready(session.Read());
            Accepted(session.Apply(initial.DecisionId, "select:0"));
            CardSelectionV1Observation preview = Ready(session.Read());
            Accepted(session.Apply(preview.DecisionId, "confirm"));
            CardSelectionV1Observation failed = Unsupported(session.Read());
            Equal(outcome == ConfirmOutcome.WrongOriginal ? 2 : 1, failed.PriorResults.Count);
            Failure(session.Apply(preview.DecisionId, "confirm"));
            Equal(2, fixture.DispatchCount);
        }
    }

    private static void SmithContextOverlayDeckAndMapFailures()
    {
        foreach (Action<SmithFixture> corrupt in new Action<SmithFixture>[]
        {
            f => f.ReplaceRun(),
            f => f.ReplaceOverlay(),
            f => f.AddForeignDeckCard(),
            f => f.OpenMap(),
        })
        {
            using SmithFixture fixture = new(ConfirmOutcome.SuccessOpen);
            CardSelectionV1Session session = fixture.Session;
            CardSelectionV1Observation initial = Ready(session.Read());
            Accepted(session.Apply(initial.DecisionId, "select:0"));
            CardSelectionV1Observation preview = Ready(session.Read());
            Accepted(session.Apply(preview.DecisionId, "confirm"));
            corrupt(fixture);
            Unsupported(session.Read());
            Equal(2, fixture.DispatchCount);
        }

        using (SmithFixture incomplete = new(ConfirmOutcome.IncompleteClosed))
        {
            CardSelectionV1Session session = incomplete.Session;
            CardSelectionV1Observation initial = Ready(session.Read());
            Accepted(session.Apply(initial.DecisionId, "select:0"));
            CardSelectionV1Observation preview = Ready(session.Read());
            Accepted(session.Apply(preview.DecisionId, "confirm"));
            Unsupported(session.Read());
        }

        using (SmithFixture doubled = new(ConfirmOutcome.SuccessClosed))
        {
            CardSelectionV1Session session = doubled.Session;
            CardSelectionV1Observation initial = Ready(session.Read());
            Accepted(session.Apply(initial.DecisionId, "select:0"));
            CardSelectionV1Observation preview = Ready(session.Read());
            Accepted(session.Apply(preview.DecisionId, "confirm"));
            doubled.ApplyDoubleUpgrade();
            Unsupported(session.Read());
        }
    }

    private static void CheeseCompletedTopThenLateEffect()
    {
        using CheeseFixture fixture = new();
        CardSelectionV1Session session = fixture.Session;
        CardSelectionV1Observation first = Ready(session.Read());
        Accepted(session.Apply(first.DecisionId, "select:0"));
        CardSelectionV1Observation second = Ready(session.Read());
        Accepted(session.Apply(second.DecisionId, "select:1"));
        CardSelectionV1Observation top = Waiting(session.Read());
        Equal(2, top.PriorResults.Count);
        fixture.CloseSelector();
        Waiting(session.Read());
        fixture.ApplyAdditions();
        Waiting(session.Read());
        fixture.CompleteEffect();
        CardSelectionV1ResolvedResult resolved = Resolved(session.Read());
        Equal(2, resolved.SelectedCards.Count);
    }
#endif

    private static void ReproducesTaskSucceededBeforeClose()
    {
        using SmithFixture fixture = new(closeOnConfirm: false);
        CardSelectionV1Session session = fixture.Session;
        CardSelectionV1Observation initial = Ready(session.Read());
        Accepted(session.Apply(initial.DecisionId, "select:0"));
        CardSelectionV1Observation preview = Ready(session.Read());
        Equal("preview", preview.Phase);
        Accepted(session.Apply(preview.DecisionId, "confirm"));
        CardSelectionV1Observation failed = Unsupported(session.Read());
        Equal(1, failed.PriorResults.Count);
    }

    private static void ReproducesClosedWithCachedPreview()
    {
        using SmithFixture fixture = new(closeOnConfirm: true);
        CardSelectionV1Session session = fixture.Session;
        CardSelectionV1Observation initial = Ready(session.Read());
        Accepted(session.Apply(initial.DecisionId, "select:0"));
        CardSelectionV1Observation preview = Ready(session.Read());
        Accepted(session.Apply(preview.DecisionId, "confirm"));
        CardSelectionV1Observation failed = Unsupported(session.Read());
        Equal(1, failed.PriorResults.Count);
    }

    private enum ConfirmOutcome { SuccessOpen, SuccessClosed, Canceled, Faulted, WrongOriginal, IncompleteClosed }

    private sealed class SmithFixture : IDisposable
    {
        private readonly TaskCompletionSource<IEnumerable<CardModel>> _completion = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private NOverlayStack _overlays = new();
        private readonly NDeckUpgradeSelectScreen _screen = new();
        private readonly CardModel _card = new();
        private readonly ShaderMaterial _material = new();
        private readonly NUpgradePreview _preview = new();
        private readonly Control _previewContainer = new() { Visible = false };
        private readonly NProceedButton _proceed = new() { Visible = false, IsEnabled = false };
        private readonly NMapScreen _map = new();
        private readonly PinnedCardSelectionV1NativeAdapter _adapter;
        private readonly Player _player = new();

        private readonly NRun _run;
        internal int DispatchCount { get; private set; }

        internal SmithFixture(bool closeOnConfirm) : this(closeOnConfirm ? ConfirmOutcome.SuccessClosed : ConfirmOutcome.SuccessOpen) { }

        internal SmithFixture(ConfirmOutcome outcome)
        {
            _card.Id.Entry = "Card_0";
            _card.IsUpgradable = true;
            _player.Deck.Cards.Add(_card);
            var cardNode = new NCard { CardHighlight = new NCardHighlight { Material = _material } };
            var hitbox = new NClickableControl();
            var holder = new NGridCardHolder { CardModel = _card, CardNode = cardNode, Hitbox = hitbox };
            var grid = new NCardGrid();
            grid.CurrentlyDisplayedCardHolders.Add(holder);
            _screen.SelectionTask = _completion.Task;
            _screen.Bind("%CardGrid", grid);
            var confirm = new NConfirmButton();
            _previewContainer.Bind("UpgradePreview", _preview);
            _previewContainer.Bind("Confirm", confirm);
            _screen.Bind("%UpgradeSinglePreviewContainer", _previewContainer);
            holder.Selected = () =>
            {
                DispatchCount++;
                _material.Width = BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits);
                _preview.Card = _card;
                _previewContainer.Visible = true;
            };
            confirm.Clicked = () =>
            {
                DispatchCount++;
                switch (outcome)
                {
                    case ConfirmOutcome.SuccessOpen:
                    case ConfirmOutcome.SuccessClosed:
                        _completion.TrySetResult(new[] { _card });
                        break;
                    case ConfirmOutcome.Canceled:
                        _completion.TrySetCanceled();
                        break;
                    case ConfirmOutcome.Faulted:
                        _completion.TrySetException(new InvalidOperationException("canary"));
                        break;
                    case ConfirmOutcome.WrongOriginal:
                        _completion.TrySetResult(new[] { new CardModel { IsUpgradable = true } });
                        break;
                    case ConfirmOutcome.IncompleteClosed:
                        break;
                }
                if (outcome is ConfirmOutcome.SuccessClosed or ConfirmOutcome.IncompleteClosed) CloseSelector();
            };
            var option = new SmithRestSiteOption { OptionId = "SMITH", SmithCount = 1 };
            var button = new NRestSiteButton { Option = option };
            var room = new NRestSiteRoom { ProceedButton = _proceed };
            room.AddOption(option, button);
            _run = new NRun { RestSiteRoom = room, GlobalUi = new GlobalUiState { MapScreen = _map, Overlays = _overlays } };
            _overlays.Screens.Add(_screen);
            NRun.Instance = _run;
            NRestSiteRoom.Instance = room;
            NMapScreen.Instance = _map;
            var receiptIdentity = new object();
            var context = new CardSelectionV1ParentContext(
                new string('a', 32), CardSelectionV1ParentKind.Rest,
                new string('b', 64), "begin", receiptIdentity,
                _run, _player, room, _map, option, button,
                CardSelectionV1Operation.Upgrade, 1, 1,
                CardSelectionV1CommitMode.PreviewConfirm, 1);
            _adapter = PinnedCardSelectionV1NativeAdapter.CreateSmith(
                context, _run, _player, room, _map, option, button, _screen);
            Session = new CardSelectionV1Session(context, _adapter);
        }

        internal CardSelectionV1Session Session { get; }
        internal void CloseSelector() { _overlays.Screens.Clear(); _screen.Visible = false; }
        internal void ApplyUpgrade() => _card.CurrentUpgradeLevel = 1;
        internal void ApplyDoubleUpgrade() => _card.CurrentUpgradeLevel = 2;
        internal void CompleteRestEffect() { _proceed.Visible = true; _proceed.IsEnabled = true; _map.IsTravelEnabled = true; }
        internal void ReplaceRun() => NRun.Instance = new NRun();
        internal void ReplaceOverlay() { _overlays = new NOverlayStack(); _overlays.Screens.Add(new object()); _run.GlobalUi.Overlays = _overlays; }
        internal void AddForeignDeckCard()
        {
            var foreign = new CardModel(); foreign.Id.Entry = "Foreign";
            _player.Deck.Cards.Add(foreign);
        }
        internal void OpenMap() => _map.IsOpen = true;
        public void Dispose() => Session.Dispose();
    }

    private sealed class CheeseFixture : IDisposable
    {
        private readonly TaskCompletionSource<IEnumerable<CardModel>> _completion = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly NOverlayStack _overlays = new();
        private readonly NSimpleCardSelectScreen _screen = new();
        private readonly NMapScreen _map = new();
        private readonly MegaCrit.Sts2.Core.Models.Events.RoomFullOfCheese _event = new();
        private readonly Player _player = new();
        private readonly CardModel[] _cards = new CardModel[8];
        internal CheeseFixture()
        {
            var grid = new NCardGrid { Size = new Vector2(920, 900), YOffset = 20 };
            var scroll = new Control { Size = new Vector2(920, 1060), Position = new Vector2(0, 0) };
            grid.Bind("%ScrollContainer", scroll);
            for (int index = 0; index < 8; index++)
            {
                int slot = index;
                CardModel card = _cards[index] = new CardModel();
                card.Id.Entry = "Offer_" + index;
                var material = new ShaderMaterial();
                var holder = new NGridCardHolder
                {
                    CardModel = card,
                    CardNode = new NCard { CardHighlight = new NCardHighlight { Material = material } },
                    Hitbox = new NClickableControl(),
                };
                holder.Selected = () =>
                {
                    material.Width = BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits);
                    if (slot == 1) _completion.TrySetResult(new[] { _cards[1], _cards[0] });
                };
                grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            _screen.SelectionTask = _completion.Task;
            _screen.Bind("%CardGrid", grid);
            _overlays.Screens.Add(_screen);
            _event.Owner = _player;
            var option = new MegaCrit.Sts2.Core.Events.EventOption { TextKey = "ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE" };
            var button = new MegaCrit.Sts2.Core.Nodes.Events.NEventOptionButton { Option = option, Event = _event };
            var room = new NEventRoom();
            var run = new NRun { EventRoom = room, GlobalUi = new GlobalUiState { MapScreen = _map, Overlays = _overlays } };
            NRun.Instance = run; NEventRoom.Instance = room; NMapScreen.Instance = _map;
            var context = new CardSelectionV1ParentContext(new string('a', 32), CardSelectionV1ParentKind.Event,
                new string('b', 64), "begin", new object(), run, _player, room, _map, option, button,
                CardSelectionV1Operation.Add, 2, 2, CardSelectionV1CommitMode.AutoAtMax, 8);
            var adapter = PinnedCardSelectionV1NativeAdapter.CreateRoomFullOfCheese(
                context, run, _player, room, _map, _event, option, button, _screen);
            Session = new CardSelectionV1Session(context, adapter);
        }
        internal CardSelectionV1Session Session { get; }
        internal void CloseSelector() { _overlays.Screens.Clear(); _screen.Visible = false; }
        internal void ApplyAdditions() { _player.Deck.Cards.Add(_cards[0]); _player.Deck.Cards.Add(_cards[1]); }
        internal void CompleteEffect() => _event.IsFinished = true;
        public void Dispose() => Session.Dispose();
    }

    private static CardSelectionV1Observation Ready(ICardSelectionV1ReadValue value)
    {
        _checks++;
        return value is CardSelectionV1Observation { Status: "ready" } result
            ? result : throw new InvalidOperationException("Expected ready.");
    }

    private static CardSelectionV1Observation Unsupported(ICardSelectionV1ReadValue value)
    {
        _checks++;
        return value is CardSelectionV1Observation { Status: "unsupported" } result
            ? result : throw new InvalidOperationException("Expected unsupported.");
    }

    private static CardSelectionV1Observation Waiting(ICardSelectionV1ReadValue value)
    {
        _checks++;
        return value is CardSelectionV1Observation { Status: "waiting" } result
            ? result : throw new InvalidOperationException("Expected waiting.");
    }

    private static CardSelectionV1ResolvedResult Resolved(ICardSelectionV1ReadValue value)
    {
        _checks++;
        return value as CardSelectionV1ResolvedResult ?? throw new InvalidOperationException("Expected resolved.");
    }

    private static void Failure(ICardSelectionV1ApplyValue value)
    {
        _checks++;
        if (value is not CardSelectionV1ApplyFailure) throw new InvalidOperationException("Expected failure.");
    }

    private static void Same(object expected, object actual)
    {
        _checks++;
        if (!ReferenceEquals(expected, actual)) throw new InvalidOperationException("Expected same object.");
    }

    private static void Accepted(ICardSelectionV1ApplyValue value)
    {
        _checks++;
        if (value is not CardSelectionV1DispatchReceipt { Outcome: "accepted" })
            throw new InvalidOperationException("Expected accepted.");
    }

    private static void Equal<T>(T expected, T actual)
    {
        _checks++;
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException($"Expected {expected}; got {actual}.");
    }
}
