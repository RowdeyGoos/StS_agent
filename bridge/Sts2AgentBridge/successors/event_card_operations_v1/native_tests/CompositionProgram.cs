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
using Sts2AgentBridge.Successors.RoomFlowsV1;

internal static class CompositionProgram
{
    private static int _checks;

    private static int Main()
    {
        try
        {
            AromaRunsThroughParentFactoryAndChild();
            SapphireRunsThroughParentFactoryAndChild();
            Console.WriteLine(JsonSerializer.Serialize(new SortedDictionary<string, object>
            {
                ["check_count"] = _checks,
                ["schema_version"] = 1,
                ["status"] = "passed",
                ["suite"] = "event_card_operations_v1_native_composition",
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static void AromaRunsThroughParentFactoryAndChild() =>
        RunThroughParent(EventKind.Aroma, proveReadinessRetention: true);

    private static void SapphireRunsThroughParentFactoryAndChild()
    {
        using (Fixture changedKey = new(EventKind.Sapphire, 4))
        using (var keyParent = new EventOrchestratorV1Session(
            new string('c', 32), new PinnedEventOrchestratorV1NativeAdapter()))
        {
            EventOrchestratorV1Observation decision = ParentReady(keyParent.Read());
            Require(keyParent.Apply(decision.DecisionId, "choose:0") is
                RoomFlowDispatchReceipt { Outcome: "accepted" });
            changedKey.OpenSelector();
            Equal(EventOrchestratorV1Limits.ChildStatus,
                ParentObservation(keyParent.Read()).Status);
            var child = keyParent.ActiveChild as IEventOrchestratorV1CardChildBroker
                ?? throw new InvalidOperationException("card child");
            changedKey.Option.TextKey = EventCardOperationNativeRegistry.SapphireUnsupportedKey;
            Equal("unsupported", ReadyOrUnsupported(child.Read()).Status);
            Equal(EventOrchestratorV1ChildStatus.Failed, child.Status);
        }
        using (Fixture replaced = new(EventKind.Sapphire, 4))
        using (var parent = new EventOrchestratorV1Session(
            new string('c', 32), new PinnedEventOrchestratorV1NativeAdapter()))
        {
            EventOrchestratorV1Observation decision = ParentReady(parent.Read());
            Require(parent.Apply(decision.DecisionId, "choose:0") is
                RoomFlowDispatchReceipt { Outcome: "accepted" });
            replaced.OpenSelector(populate: false);
            Equal(EventOrchestratorV1Limits.WaitingStatus,
                ParentObservation(parent.Read()).Status);
            Equal(0, replaced.Screen.CardsSelectedCalls);
            replaced.ReplaceSelector();
            Equal(EventOrchestratorV1Limits.UnsupportedStatus,
                ParentObservation(parent.Read()).Status);
            Require(parent.ActiveChild is null);
            Equal(0, replaced.Screen.CardsSelectedCalls);
        }
        RunThroughParent(EventKind.Sapphire, proveReadinessRetention: false);
    }

    private static void RunThroughParent(
        EventKind kind, bool proveReadinessRetention)
    {
        using Fixture fixture = new(kind, 4);
        using var parent = new EventOrchestratorV1Session(
            new string('c', 32), new PinnedEventOrchestratorV1NativeAdapter());
        EventOrchestratorV1Observation decision = ParentReady(parent.Read());
        Equal(2, decision.Candidates.Count);
        Equal(kind == EventKind.Aroma
                ? "aroma_maintain_control_upgrade_one"
                : "sapphire_eat_upgrade_one",
            decision.Candidates[0].ChildPolicy);
        Equal(EventOrchestratorV1Limits.UnsupportedCardPolicy,
            decision.Candidates[1].ChildPolicy);
        Require(parent.Apply(decision.DecisionId, "choose:0") is
            RoomFlowDispatchReceipt { Outcome: "accepted" });
        Equal(1, fixture.Button.Clicks);

        fixture.OpenSelector(populate: !proveReadinessRetention);
        if (proveReadinessRetention)
        {
            Equal(EventOrchestratorV1Limits.WaitingStatus,
                ParentObservation(parent.Read()).Status);
            Require(parent.ActiveChild is null);
            Equal(0, fixture.Screen.CardsSelectedCalls);
            fixture.PopulateSelector();
        }
        EventOrchestratorV1Observation childState = ParentObservation(parent.Read());
        Equal(EventOrchestratorV1Limits.ChildStatus, childState.Status);
        var child = parent.ActiveChild as IEventOrchestratorV1CardChildBroker
            ?? throw new InvalidOperationException("card child");
        Equal(1, fixture.Screen.CardsSelectedCalls);
        CardSelectionV1Observation selecting = Ready(child.Read());
        Accepted(child.Apply(selecting.DecisionId, "select:0"));
        CardSelectionV1Observation preview = Ready(child.Read());
        Equal("preview", preview.Phase);
        Accepted(child.Apply(preview.DecisionId, "confirm"));
        fixture.CloseSelector();
        Waiting(child.Read());
        fixture.UpgradeSelected();
        Waiting(child.Read());
        fixture.EventModel.IsFinished = true;
        Resolved(child.Read());

        fixture.ShowProceed();
        EventOrchestratorV1Observation proceed = ParentReady(parent.Read());
        Equal(EventOrchestratorV1Limits.ProceedPhase, proceed.Phase);
        Require(proceed.PriorResult?.Result ==
            EventOrchestratorV1Limits.ChildCompletedResult);
        Require(parent.Apply(proceed.DecisionId, "choose:0") is
            RoomFlowDispatchReceipt { Outcome: "accepted" });
        fixture.Room.Visible = false;
        fixture.Map.IsOpen = true;
        fixture.Map.IsTravelEnabled = true;
        Require(parent.Read() is EventOrchestratorV1ResolvedResult);
        Equal(1, fixture.ProceedButton!.Clicks);
        _checks++;
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
            Layout = new NEventLayout();
            Room = new NEventRoom { Layout = Layout };
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
            string blockedKey = kind == EventKind.Aroma
                ? EventCardOperationNativeRegistry.AromaUnsupportedKey
                : EventCardOperationNativeRegistry.SapphireUnsupportedKey;
            BindOption(Button, Option, key);
            var blocked = new EventOption { TextKey = blockedKey };
            var blockedButton = new NEventOptionButton
                { Option = blocked, Event = EventModel };
            BindOption(blockedButton, blocked, blockedKey);
        }

        internal EventKind Kind { get; }
        internal Player Player { get; }
        internal CardModel[] Cards { get; }
        internal EventModel EventModel { get; }
        internal EventOption Option { get; }
        internal NEventOptionButton Button { get; }
        internal NEventRoom Room { get; }
        internal NEventLayout Layout { get; }
        internal NMapScreen Map { get; }
        internal NOverlayStack Overlays { get; }
        internal NRun Run { get; }
        internal NEventOptionButton? ProceedButton { get; private set; }
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

        internal void ReplaceSelector()
        {
            Overlays.Screens.Clear();
            Overlays.Screens.Add(new NDeckUpgradeSelectScreen());
        }

        internal void UpgradeSelected() => Cards[0].CurrentUpgradeLevel++;

        internal void ShowProceed()
        {
            Layout.OptionButtons.Clear();
            var option = new EventOption { TextKey = "PROCEED", IsProceed = true };
            ProceedButton = new NEventOptionButton { Option = option, Event = EventModel };
            BindOption(ProceedButton, option, "PROCEED");
        }

        private void BindOption(
            NEventOptionButton button, EventOption option, string text)
        {
            button.Bind("%Text", new MegaCrit.Sts2.addons.mega_text.MegaRichTextLabel
                { Text = text });
            Layout.OptionButtons.Add(button);
        }

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

    private static CardSelectionV1Observation ReadyOrUnsupported(
        ICardSelectionV1ReadValue value) =>
        value as CardSelectionV1Observation ??
            throw new InvalidOperationException("card observation");

    private static CardSelectionV1Observation Waiting(ICardSelectionV1ReadValue value) =>
        value is CardSelectionV1Observation { Status: "waiting" } result
            ? result : throw new InvalidOperationException("waiting");

    private static CardSelectionV1ResolvedResult Resolved(ICardSelectionV1ReadValue value) =>
            value as CardSelectionV1ResolvedResult ?? throw new InvalidOperationException("resolved");

    private static EventOrchestratorV1Observation ParentObservation(IRoomFlowReadValue value) =>
        value as EventOrchestratorV1Observation ??
            throw new InvalidOperationException("parent observation");

    private static EventOrchestratorV1Observation ParentReady(IRoomFlowReadValue value) =>
        value is EventOrchestratorV1Observation
            { Status: EventOrchestratorV1Limits.ReadyStatus } result
            ? result : throw new InvalidOperationException("parent ready");

    private static void Accepted(ICardSelectionV1ApplyValue value)
    {
        if (value is not CardSelectionV1DispatchReceipt { Outcome: "accepted" })
            throw new InvalidOperationException("accepted");
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

}
