using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
using Sts2AgentBridge.Successors.EventOrchestratorV1;
using Sts2AgentBridge.Successors.EventOrchestratorV1.Native;

internal static class Program
{
    private static int _checks;

    private static int Main()
    {
        try
        {
            CatalogIsClosedAndExact();
            BindingCapturesCompleteDomainAndDeck();
            BindingRejectsChangedOrInvalidPredispatchFacts();
            ReadinessIsPassiveAndConstructorClaimsOnce();
            AromaCompletesThroughActualSession();
            SapphireCompletesThroughActualSession();
            CompletionRequiresExactTaskDeckAndEventWitness();
            ForegroundAndReplacementFailuresStop();
            ExactRuntimeTypesAreRequired();
            TaskAndStartupFailuresStop();
            DisposeSuppressesFurtherCapture();
            Console.WriteLine(JsonSerializer.Serialize(new SortedDictionary<string, object>
            {
                ["check_count"] = _checks,
                ["schema_version"] = 1,
                ["status"] = "passed",
                ["suite"] = "event_card_operations_v1_native_card",
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static void CatalogIsClosedAndExact()
    {
        Equal(3, EventOrchestratorV1CardPolicyCatalog.Definitions.Count);
        EventOrchestratorV1CardPolicyDefinition aroma = Policy(EventKind.Aroma);
        EventOrchestratorV1CardPolicyDefinition sapphire = Policy(EventKind.Sapphire);
        Equal(CardSelectionV1Operation.Upgrade, aroma.Operation);
        Equal(CardSelectionV1CommitMode.PreviewConfirm, aroma.CommitMode);
        Equal(1, aroma.MinSelect);
        Equal(1, aroma.MaxSelect);
        Equal(2, aroma.MinimumDomainCount);
        Equal(64, aroma.MaximumDomainCount);
        Equal(EventOrchestratorV1CardDomainSource.ExistingDeckOriginals,
            sapphire.DomainSource);
        Require(!EventOrchestratorV1CardPolicyCatalog.TryGet(
            "unknown", out EventOrchestratorV1CardPolicyDefinition? missing) &&
            missing is null);
        _checks++;
    }

    private static void BindingCapturesCompleteDomainAndDeck()
    {
        using Fixture fixture = new(EventKind.Aroma, 3);
        EventCardOperationBinding binding = fixture.Prepare();
        Equal(3, binding.PreDispatchDeck.Count);
        Equal(2, binding.EligibleOriginals.Count);
        Same(fixture.Cards[0], binding.EligibleOriginals[0]);
        Same(fixture.Cards[1], binding.EligibleOriginals[1]);
        Require(binding.PreDispatchDeck is not CardSelectionV1DeckCard[] &&
            binding.EligibleOriginals is not CardModel[]);
        Equal(2, binding.DomainCount);
        Require(binding.MatchesBeforeDispatch(
            fixture.Run, fixture.Player, fixture.Room, fixture.Map,
            fixture.EventModel, fixture.Option, fixture.Button));
        _checks++;
    }

    private static void BindingRejectsChangedOrInvalidPredispatchFacts()
    {
        using (Fixture one = new(EventKind.Aroma, 2, upgradable: 1))
            Require(!one.TryPrepare(out _));
        using (Fixture tooMany = new(EventKind.Aroma, 65, upgradable: 65))
            Require(!tooMany.TryPrepare(out _));
        using (Fixture selector = new(EventKind.Aroma, 3))
        {
            CardSelectCmd.Selector = new object();
            Require(!selector.TryPrepare(out _));
        }
        using (Fixture changed = new(EventKind.Sapphire, 3))
        {
            EventCardOperationBinding binding = changed.Prepare();
            changed.Cards[1].IsUpgradable = false;
            Require(!binding.MatchesBeforeDispatch(
                changed.Run, changed.Player, changed.Room, changed.Map,
                changed.EventModel, changed.Option, changed.Button));
        }
        using (Fixture wrongKey = new(EventKind.Aroma, 3))
        {
            wrongKey.Option.TextKey = "SAPPHIRE_SEED.pages.INITIAL.options.EAT";
            Require(!wrongKey.TryPrepare(out _));
        }
        _checks++;
    }

    private static void ReadinessIsPassiveAndConstructorClaimsOnce()
    {
        using Fixture fixture = new(EventKind.Aroma, 3);
        fixture.OpenSelector(populate: false);
        Require(!EventCardSelectionV1NativeAdapter.IsReady(
            fixture.Binding!, fixture.Screen));
        Equal(0, fixture.Screen.CardsSelectedCalls);
        fixture.PopulateSelector();
        Require(EventCardSelectionV1NativeAdapter.IsReady(
            fixture.Binding!, fixture.Screen));
        Equal(0, fixture.Screen.CardsSelectedCalls);
        using CardSelectionV1Session session = fixture.CreateSession();
        Equal(1, fixture.Screen.CardsSelectedCalls);
        Ready(session.Read());
        Equal(1, fixture.Screen.CardsSelectedCalls);
        _checks++;
    }

    private static void AromaCompletesThroughActualSession()
    {
        using Fixture fixture = new(EventKind.Aroma, 4);
        CardSelectionV1ResolvedResult result = Complete(fixture);
        Equal("resolved", result.Status);
        Equal(1, result.SelectedCards.Count);
        Equal(2, result.PriorResults.Count);
        Same(result, fixture.Session!.Read());
        _checks++;
    }

    private static void SapphireCompletesThroughActualSession()
    {
        using Fixture fixture = new(EventKind.Sapphire, 4);
        CardSelectionV1ResolvedResult result = Complete(fixture);
        Equal("upgrade", result.Operation);
        Equal(0, result.SelectedCards[0].UpgradeLevel);
        _checks++;
    }

    private static void CompletionRequiresExactTaskDeckAndEventWitness()
    {
        using (Fixture delayed = new(EventKind.Aroma, 3))
        {
            DriveThroughConfirm(delayed);
            delayed.CloseSelector();
            Waiting(delayed.Session!.Read());
            delayed.UpgradeSelected();
            Waiting(delayed.Session.Read());
            delayed.EventModel.IsFinished = true;
            Resolved(delayed.Session.Read());
        }
        using (Fixture wrongTask = new(EventKind.Sapphire, 3))
        {
            wrongTask.TaskResultOverride = new CardModel { IsUpgradable = true };
            DriveThroughConfirm(wrongTask);
            Unsupported(wrongTask.Session!.Read());
        }
        using (Fixture foreignDeck = new(EventKind.Aroma, 3))
        {
            DriveThroughConfirm(foreignDeck);
            foreignDeck.CloseSelector();
            CardModel extra = new(); extra.Id.Entry = "Foreign";
            foreignDeck.Player.Deck.Cards.Add(extra);
            Unsupported(foreignDeck.Session!.Read());
        }
        using (Fixture doubleUpgrade = new(EventKind.Sapphire, 3))
        {
            DriveThroughConfirm(doubleUpgrade);
            doubleUpgrade.CloseSelector();
            doubleUpgrade.Cards[0].CurrentUpgradeLevel = 2;
            doubleUpgrade.EventModel.IsFinished = true;
            Unsupported(doubleUpgrade.Session!.Read());
        }
        _checks++;
    }

    private static void ForegroundAndReplacementFailuresStop()
    {
        using (Fixture map = new(EventKind.Aroma, 3))
        {
            map.OpenSelector();
            map.CreateSession();
            map.Map.IsOpen = true;
            Unsupported(map.Session!.Read());
        }
        using (Fixture parent = new(EventKind.Sapphire, 3))
        {
            parent.OpenSelector();
            parent.CreateSession();
            parent.Button.Event = new SapphireSeed { Owner = parent.Player };
            Unsupported(parent.Session!.Read());
        }
        using (Fixture keyDrift = new(EventKind.Aroma, 3))
        {
            keyDrift.OpenSelector();
            keyDrift.CreateSession();
            keyDrift.Option.TextKey =
                "AROMA_OF_CHAOS.pages.INITIAL.options.OTHER";
            Unsupported(keyDrift.Session!.Read());
        }
        using (Fixture screen = new(EventKind.Aroma, 3))
        {
            screen.OpenSelector();
            EventCardOperationBinding binding = screen.Binding!;
            NDeckUpgradeSelectScreen replacement = new();
            Require(!EventCardSelectionV1NativeAdapter.IsReady(binding, replacement));
        }
        using (Fixture reordered = new(EventKind.Sapphire, 4))
        {
            reordered.OpenSelector(reverseGrid: true);
            Require(EventCardSelectionV1NativeAdapter.IsReady(
                reordered.Binding!, reordered.Screen));
        }
        using (Fixture scrolling = new(EventKind.Aroma, 3))
        {
            scrolling.OpenSelector();
            scrolling.Scroll.Position = new Vector2(0f, 51f);
            Require(!EventCardSelectionV1NativeAdapter.IsReady(
                scrolling.Binding!, scrolling.Screen));
        }
        using (Fixture changedLayout = new(EventKind.Sapphire, 3))
        {
            changedLayout.OpenSelector();
            changedLayout.CreateSession();
            changedLayout.Scroll.Size = new Vector2(1000f,
                changedLayout.Scroll.Size.Y + 1f);
            Unsupported(changedLayout.Session!.Read());
        }
        using (Fixture animating = new(EventKind.Aroma, 3))
        {
            animating.OpenSelector();
            animating.Grid.IsAnimatingOut = true;
            Require(!EventCardSelectionV1NativeAdapter.IsReady(
                animating.Binding!, animating.Screen));
        }
        using (Fixture closedForeignSelector = new(EventKind.Sapphire, 3))
        {
            closedForeignSelector.OpenSelector();
            closedForeignSelector.CreateSession();
            closedForeignSelector.CloseSelector();
            CardSelectCmd.Selector = new object();
            Unsupported(closedForeignSelector.Session!.Read());
        }
        _checks++;
    }

    private static void TaskAndStartupFailuresStop()
    {
        using (Fixture complete = new(EventKind.Aroma, 3))
        {
            complete.OpenSelector(taskInitiallyComplete: true);
            Require(EventCardSelectionV1NativeAdapter.IsReady(
                complete.Binding!, complete.Screen));
            Throws(() => complete.CreateSession());
        }
        using (Fixture canceled = new(EventKind.Sapphire, 3))
        {
            canceled.CancelOnConfirm = true;
            DriveThroughConfirm(canceled);
            Unsupported(canceled.Session!.Read());
        }
        using (Fixture replaced = new(EventKind.Aroma, 3))
        {
            replaced.OpenSelector();
            replaced.Player.Deck.Cards.Reverse();
            Require(!EventCardSelectionV1NativeAdapter.IsReady(
                replaced.Binding!, replaced.Screen));
        }
        _checks++;
    }

    private static void ExactRuntimeTypesAreRequired()
    {
        foreach (DerivedPart part in Enum.GetValues<DerivedPart>())
        {
            if (part == DerivedPart.None) continue;
            using Fixture fixture = new(EventKind.Aroma, 3);
            fixture.OpenSelector(derivedPart: part);
            Require(!EventCardSelectionV1NativeAdapter.IsReady(
                fixture.Binding!, fixture.Screen));
            Equal(0, fixture.Screen.CardsSelectedCalls);
        }
        _checks++;
    }

    private static void DisposeSuppressesFurtherCapture()
    {
        using Fixture fixture = new(EventKind.Aroma, 3);
        fixture.OpenSelector();
        fixture.CreateSession();
        fixture.Session!.Dispose();
        Unsupported(fixture.Session.Read());
        _checks++;
    }

    private static CardSelectionV1ResolvedResult Complete(Fixture fixture)
    {
        DriveThroughConfirm(fixture);
        fixture.CloseSelector();
        Waiting(fixture.Session!.Read());
        fixture.UpgradeSelected();
        Waiting(fixture.Session.Read());
        fixture.EventModel.IsFinished = true;
        return Resolved(fixture.Session.Read());
    }

    private static void DriveThroughConfirm(Fixture fixture)
    {
        fixture.OpenSelector();
        CardSelectionV1Session session = fixture.CreateSession();
        CardSelectionV1Observation initial = Ready(session.Read());
        Accepted(session.Apply(initial.DecisionId, "select:0"));
        CardSelectionV1Observation preview = Ready(session.Read());
        Equal("preview", preview.Phase);
        Accepted(session.Apply(preview.DecisionId, "confirm"));
    }

    private static EventOrchestratorV1CardPolicyDefinition Policy(EventKind kind)
    {
        string id = kind == EventKind.Aroma
            ? "aroma_maintain_control_upgrade_one"
            : "sapphire_eat_upgrade_one";
        return EventOrchestratorV1CardPolicyCatalog.TryGet(
            id, out EventOrchestratorV1CardPolicyDefinition? definition) &&
            definition is not null ? definition : throw new InvalidOperationException("policy");
    }

    private sealed class Fixture : IDisposable
    {
        private readonly TaskCompletionSource<IEnumerable<CardModel>> _task =
            new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly ShaderMaterial[] _materials;
        private readonly Control _previewContainer = new() { Visible = false };
        private NUpgradePreview _preview = new();
        private NConfirmButton _confirm = new();

        internal Fixture(EventKind kind, int deckCount, int upgradable = 2)
        {
            Kind = kind;
            Player = new Player();
            Cards = new CardModel[deckCount];
            _materials = new ShaderMaterial[Math.Min(deckCount, upgradable)];
            for (int index = 0; index < deckCount; index++)
            {
                CardModel card = Cards[index] = new CardModel
                {
                    IsUpgradable = index < upgradable,
                    CurrentUpgradeLevel = 0,
                };
                card.Id.Entry = "Card_" + index;
                Player.Deck.Cards.Add(card);
            }
            EventModel = kind == EventKind.Aroma
                ? new AromaOfChaos() : new SapphireSeed();
            EventModel.Owner = Player;
            string key = kind == EventKind.Aroma
                ? "AROMA_OF_CHAOS.pages.INITIAL.options.MAINTAIN_CONTROL"
                : "SAPPHIRE_SEED.pages.INITIAL.options.EAT";
            Option = new EventOption { TextKey = key };
            Button = new NEventOptionButton { Option = Option, Event = EventModel };
            Room = new NEventRoom();
            Map = new NMapScreen();
            Overlays = new NOverlayStack();
            Run = new NRun
            {
                EventRoom = Room,
                GlobalUi = new GlobalUiState { MapScreen = Map, Overlays = Overlays },
            };
            NRun.Instance = Run;
            NEventRoom.Instance = Room;
            NMapScreen.Instance = Map;
            CardSelectCmd.Selector = null;
        }

        internal EventKind Kind { get; }
        internal Player Player { get; }
        internal CardModel[] Cards { get; }
        internal EventModel EventModel { get; }
        internal EventOption Option { get; }
        internal NEventOptionButton Button { get; }
        internal NEventRoom Room { get; }
        internal NMapScreen Map { get; }
        internal NOverlayStack Overlays { get; }
        internal NRun Run { get; }
        internal NDeckUpgradeSelectScreen Screen { get; private set; } = null!;
        internal NCardGrid Grid { get; private set; } = null!;
        internal Control Scroll { get; private set; } = null!;
        internal EventCardOperationBinding? Binding { get; private set; }
        internal CardSelectionV1Session? Session { get; private set; }
        internal CardModel? TaskResultOverride { get; set; }
        internal bool CancelOnConfirm { get; set; }

        internal bool TryPrepare(out EventCardOperationBinding? binding)
        {
            bool result = EventCardOperationBinding.TryPrepare(
                Policy(Kind), Run, Player, Room, Map, EventModel, Option, Button,
                out binding);
            Binding = binding;
            return result;
        }

        internal EventCardOperationBinding Prepare() => TryPrepare(out EventCardOperationBinding? binding) && binding is not null
            ? binding : throw new InvalidOperationException("prepare");

        internal void OpenSelector(bool taskInitiallyComplete = false,
            bool populate = true, bool reverseGrid = false,
            DerivedPart derivedPart = DerivedPart.None)
        {
            Binding ??= Prepare();
            Screen = derivedPart == DerivedPart.Screen
                ? new DerivedScreen() : new NDeckUpgradeSelectScreen();
            Grid = derivedPart == DerivedPart.Grid
                ? new DerivedGrid() : new NCardGrid();
            int columns = 4;
            int rows = (Binding.EligibleOriginals.Count + columns - 1) / columns;
            float containedHeight = rows * NCard.defaultSize.Y +
                (rows - 1) * 40f;
            float scrollHeight = containedHeight + 400f;
            Grid.Size = new Vector2(1000f, scrollHeight + 100f);
            Scroll = new Control
            {
                Size = new Vector2(1000f, scrollHeight),
                Position = new Vector2(0f, 50f),
            };
            Grid.Bind("%ScrollContainer", Scroll);
            Screen.Bind("%CardGrid", Grid);
            _reverseGrid = reverseGrid;
            _derivedPart = derivedPart;
            if (populate) PopulateSelector();
            _preview = derivedPart == DerivedPart.Preview
                ? new DerivedPreview() : new NUpgradePreview();
            _confirm = derivedPart == DerivedPart.Confirm
                ? new DerivedConfirm() : new NConfirmButton();
            _previewContainer.Bind("UpgradePreview", _preview);
            _previewContainer.Bind("Confirm", _confirm);
            Screen.Bind("%UpgradeSinglePreviewContainer", _previewContainer);
            _confirm.Clicked = Confirm;
            if (taskInitiallyComplete) _task.TrySetResult(new[] { Cards[0] });
            Screen.SelectionTask = _task.Task;
            Overlays.Screens.Add(Screen);
            CardSelectCmd.Selector = null;
        }

        private bool _reverseGrid;
        private DerivedPart _derivedPart;

        internal void PopulateSelector()
        {
            if (Grid.CurrentlyDisplayedCardHolders.Count != 0)
                throw new InvalidOperationException("already populated");
            for (int display = 0; display < Binding!.EligibleOriginals.Count; display++)
            {
                int index = _reverseGrid
                    ? Binding.EligibleOriginals.Count - 1 - display : display;
                CardModel model = Binding.EligibleOriginals[index];
                ShaderMaterial material = _materials[display] =
                    display == 0 && _derivedPart == DerivedPart.Material
                        ? new DerivedMaterial() : new ShaderMaterial();
                NGridCardHolder holder = display == 0 &&
                    _derivedPart == DerivedPart.Holder
                        ? new DerivedHolder() : new NGridCardHolder();
                holder.CardModel = model;
                holder.CardNode = display == 0 && _derivedPart == DerivedPart.Card
                    ? new DerivedCard() : new NCard();
                holder.CardNode.CardHighlight = display == 0 &&
                    _derivedPart == DerivedPart.Highlight
                        ? new DerivedHighlight { Material = material }
                        : new NCardHighlight { Material = material };
                holder.Hitbox = display == 0 && _derivedPart == DerivedPart.Hitbox
                    ? new DerivedHitbox() : new NClickableControl();
                int selected = display;
                holder.Selected = () => Select(selected, holder);
                Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
        }

        internal CardSelectionV1Session CreateSession()
        {
            Binding ??= Prepare();
            var context = new CardSelectionV1ParentContext(
                new string('a', 32),
                CardSelectionV1ParentKind.Event,
                new string('b', 64),
                "choose:0",
                new object(),
                Run, Player, Room, Map, Option, Button,
                CardSelectionV1Operation.Upgrade,
                1, 1,
                CardSelectionV1CommitMode.PreviewConfirm,
                Binding.DomainCount);
            var adapter = new EventCardSelectionV1NativeAdapter(Binding, context, Screen);
            return Session = new CardSelectionV1Session(context, adapter);
        }

        internal void CloseSelector()
        {
            Overlays.Screens.Clear();
            Screen.Visible = false;
            CardSelectCmd.Selector = null;
        }

        internal void UpgradeSelected() => Cards[0].CurrentUpgradeLevel++;

        private void Select(int index, NGridCardHolder holder)
        {
            foreach (ShaderMaterial material in _materials) material.Width = 0f;
            _materials[index].Width = BitConverter.Int32BitsToSingle(
                CardSelectionV1NativeRules.SelectedWidthBits);
            _preview.Card = holder.CardModel;
            _previewContainer.Visible = true;
        }

        private void Confirm()
        {
            if (CancelOnConfirm) _task.TrySetCanceled();
            else _task.TrySetResult(new[] { TaskResultOverride ?? _preview.Card! });
        }

        public void Dispose()
        {
            Session?.Dispose();
            CardSelectCmd.Selector = null;
            NRun.Instance = null;
            NEventRoom.Instance = null;
            NMapScreen.Instance = null;
        }
    }

    private enum EventKind { Aroma, Sapphire }
    private enum DerivedPart
    {
        None,
        Screen,
        Grid,
        Holder,
        Card,
        Hitbox,
        Highlight,
        Material,
        Preview,
        Confirm,
    }

    private sealed class DerivedScreen : NDeckUpgradeSelectScreen { }
    private sealed class DerivedGrid : NCardGrid { }
    private sealed class DerivedHolder : NGridCardHolder { }
    private sealed class DerivedCard : NCard { }
    private sealed class DerivedHitbox : NClickableControl { }
    private sealed class DerivedHighlight : NCardHighlight { }
    private sealed class DerivedMaterial : ShaderMaterial { }
    private sealed class DerivedPreview : NUpgradePreview { }
    private sealed class DerivedConfirm : NConfirmButton { }

    private static CardSelectionV1Observation Ready(ICardSelectionV1ReadValue value) =>
        value is CardSelectionV1Observation { Status: "ready" } result
            ? result : throw new InvalidOperationException("ready");

    private static CardSelectionV1Observation Waiting(ICardSelectionV1ReadValue value) =>
        value is CardSelectionV1Observation { Status: "waiting" } result
            ? result : throw new InvalidOperationException("waiting");

    private static CardSelectionV1Observation Unsupported(ICardSelectionV1ReadValue value) =>
        value is CardSelectionV1Observation { Status: "unsupported" } result
            ? result : throw new InvalidOperationException("unsupported");

    private static CardSelectionV1ResolvedResult Resolved(ICardSelectionV1ReadValue value) =>
        value as CardSelectionV1ResolvedResult ?? throw new InvalidOperationException("resolved");

    private static void Accepted(ICardSelectionV1ApplyValue value)
    {
        if (value is not CardSelectionV1DispatchReceipt { Outcome: "accepted" })
            throw new InvalidOperationException("accepted");
    }

    private static void Throws(Action action)
    {
        try { action(); }
        catch (InvalidOperationException) { return; }
        throw new InvalidOperationException("throw expected");
    }

    private static void Require(bool value)
    {
        if (!value) throw new InvalidOperationException("require");
    }

    private static void Equal<T>(T expected, T actual) where T : notnull
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException($"expected {expected}, actual {actual}");
    }

    private static void Same(object expected, object actual)
    {
        if (!ReferenceEquals(expected, actual))
            throw new InvalidOperationException("same");
    }
}
