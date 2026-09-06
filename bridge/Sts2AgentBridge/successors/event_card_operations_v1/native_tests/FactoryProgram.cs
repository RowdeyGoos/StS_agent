using System;
using System.Text.Json;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
using Sts2AgentBridge.Successors.EventOrchestratorV1.Native;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.NativeTests;

internal static class FactoryProgram
{
    private const string Nonce = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    private static int _checks;

    public static int Main()
    {
        try
        {
            ItemFactoryRunsTheRealBoundAdapter(); Pass();
            ItemBrokerChecksTheParentBeforeDispatch(); Pass();
            CheeseFactoryTransfersTheExactParentContext(); Pass();
            EventCardFactoryTransfersTheExactBindingAndContext(); Pass();
            Console.WriteLine(JsonSerializer.Serialize(new { schema_version = 1, status = "passed",
                suite = "event_card_operations_v1_native_factories", check_count = _checks }));
            return 0;
        }
        catch
        {
            Console.Error.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"error\":\"fixture_failure\"}");
            return 1;
        }
    }

    private static void ItemFactoryRunsTheRealBoundAdapter()
    {
        Surface s = Surface.Create(new EventModel(), "ITEM");
        var potion = new PotionModel { Id = new ModelId { Entry = "Potion_One" } };
        s.Player.MaxPotionCount = 1;
        s.Player.PotionSlots.Add(null);
        var reward = new PotionReward {
            Player = s.Player, RewardsSetIndex = 7, Potion = potion, IsPopulated = true,
        };
        var rewardButton = new NRewardButton { Reward = reward, IsEnabled = true };
        var rewardScreen = new NRewardsScreen();
        rewardScreen.AddChild(rewardButton);

        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter());
        EventOrchestratorV1Observation parent = Ready(session.Read());
        Require(session.Apply(parent.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        s.Overlays.Screens.Add(rewardScreen);
        Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.ChildStatus);
        IEventOrchestratorV1ItemChildBroker child = session.ActiveChild as IEventOrchestratorV1ItemChildBroker
            ?? throw new InvalidOperationException();
        ItemV1Observation offered = child.Read() as ItemV1Observation
            ?? throw new InvalidOperationException();
        Require(offered.Status == "ready" && offered.LegalActions.Count == 1 &&
            offered.LegalActions[0] == "collect:7" && offered.Offers.Count == 1 &&
            offered.Offers[0].Key == "Potion_One" && offered.PotionSlots.Count == 1 &&
            offered.PotionSlots[0] is null);
        Require(child.Apply(offered.DecisionId, offered.LegalActions[0]) is ItemV1DispatchReceipt);
        Require(rewardButton.Clicks == 1 && ReferenceEquals(reward.ClaimedPotion, potion) &&
            ReferenceEquals(s.Player.PotionSlots[0], potion));
        ItemV1ResolvedResult resolved = child.Read() as ItemV1ResolvedResult
            ?? throw new InvalidOperationException();
        Require(resolved.OfferIndex == 7 && resolved.Kind == "potion" &&
            resolved.Key == "Potion_One" && resolved.Result == "collected");
    }

    private static void ItemBrokerChecksTheParentBeforeDispatch()
    {
        Surface s = Surface.Create(new EventModel(), "ITEM");
        s.Player.MaxPotionCount = 0;
        var relic = new RelicModel { Id = new ModelId { Entry = "Relic_One" } };
        var reward = new RelicReward {
            Player = s.Player, RewardsSetIndex = 3, Relic = relic, IsPopulated = true,
        };
        var rewardButton = new NRewardButton { Reward = reward, IsEnabled = true };
        var rewardScreen = new NRewardsScreen(); rewardScreen.AddChild(rewardButton);
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter());
        EventOrchestratorV1Observation parent = Ready(session.Read());
        _ = session.Apply(parent.DecisionId, "choose:0");
        s.Overlays.Screens.Add(rewardScreen); _ = session.Read();
        var child = session.ActiveChild as IEventOrchestratorV1ItemChildBroker
            ?? throw new InvalidOperationException();
        ItemV1Observation offered = child.Read() as ItemV1Observation
            ?? throw new InvalidOperationException();
        s.Room.CustomEventNode = new object();
        Require(child.Apply(offered.DecisionId, "collect:3") is ItemV1ApplyFailure failure &&
            failure.Outcome == "rejected" && rewardButton.Clicks == 0 &&
            child.Status == EventOrchestratorV1ChildStatus.Failed);
    }

    private static void CheeseFactoryTransfersTheExactParentContext()
    {
        var cheese = new RoomFullOfCheese();
        Surface s = Surface.Create(cheese,
            PinnedEventOrchestratorV1NativeAdapter.CheeseStableId);
        PinnedCardSelectionV1NativeAdapter.Ready = true;
        var screen = new NSimpleCardSelectScreen();
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter());
        EventOrchestratorV1Observation parent = Ready(session.Read());
        Require(session.Apply(parent.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        s.Overlays.Screens.Add(screen);
        Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.ChildStatus &&
            session.ActiveChild is IEventOrchestratorV1CardChildBroker);
        var child = (IEventOrchestratorV1CardChildBroker)session.ActiveChild!;
        CardSelectionV1ParentContext context = PinnedCardSelectionV1NativeAdapter.LastContext
            ?? throw new InvalidOperationException();
        Require(ReferenceEquals(PinnedCardSelectionV1NativeAdapter.LastScreen, screen) &&
            ReferenceEquals(context.ParentReceiptIdentity, child.Correlation) &&
            context.ParentKind == CardSelectionV1ParentKind.Event &&
            context.ParentDecisionId == parent.DecisionId && context.ParentActionId == "choose:0" &&
            ReferenceEquals(context.RunIdentity, s.Run) && ReferenceEquals(context.PlayerIdentity, s.Player) &&
            ReferenceEquals(context.RoomIdentity, s.Room) && ReferenceEquals(context.MapIdentity, s.Map) &&
            ReferenceEquals(context.ParentOptionIdentity, s.Option) &&
            ReferenceEquals(context.ParentControllerIdentity, s.Button) &&
            context.Operation == CardSelectionV1Operation.Add && context.MinSelect == 2 &&
            context.MaxSelect == 2 && context.CommitMode == CardSelectionV1CommitMode.AutoAtMax &&
            context.ExpectedDomainCount == 8);
    }

    private static void EventCardFactoryTransfersTheExactBindingAndContext()
    {
        EventCardOperationBinding.Reset();
        EventCardSelectionV1NativeAdapter.Ready = true;
        Surface s = Surface.Create(new AromaOfChaos(),
            EventCardOperationNativeRegistry.AromaSupportedKey,
            EventCardOperationNativeRegistry.AromaUnsupportedKey);
        var screen = new NDeckUpgradeSelectScreen();
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter());
        EventOrchestratorV1Observation parent = Ready(session.Read());
        Require(parent.Candidates.Count == 2 &&
            parent.Candidates[0].ChildPolicy == "aroma_maintain_control_upgrade_one" &&
            parent.Candidates[1].ChildPolicy == EventOrchestratorV1Limits.UnsupportedCardPolicy);
        Require(session.Apply(parent.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        s.Overlays.Screens.Add(screen);
        Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.ChildStatus &&
            session.ActiveChild is IEventOrchestratorV1CardChildBroker);
        var child = (IEventOrchestratorV1CardChildBroker)session.ActiveChild!;
        CardSelectionV1ParentContext context = EventCardSelectionV1NativeAdapter.LastContext
            ?? throw new InvalidOperationException();
        Require(EventCardSelectionV1NativeAdapter.LastBinding is not null &&
            ReferenceEquals(EventCardSelectionV1NativeAdapter.LastScreen, screen) &&
            ReferenceEquals(context.ParentReceiptIdentity, child.Correlation) &&
            context.ParentKind == CardSelectionV1ParentKind.Event &&
            context.ParentDecisionId == parent.DecisionId &&
            context.ParentActionId == "choose:0" &&
            ReferenceEquals(context.RunIdentity, s.Run) &&
            ReferenceEquals(context.PlayerIdentity, s.Player) &&
            ReferenceEquals(context.RoomIdentity, s.Room) &&
            ReferenceEquals(context.MapIdentity, s.Map) &&
            ReferenceEquals(context.ParentOptionIdentity, s.Option) &&
            ReferenceEquals(context.ParentControllerIdentity, s.Button) &&
            context.Operation == CardSelectionV1Operation.Upgrade &&
            context.MinSelect == 1 && context.MaxSelect == 1 &&
            context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
            context.ExpectedDomainCount == 2);
    }

    private static EventOrchestratorV1Observation Observation(IRoomFlowReadValue value) =>
        value as EventOrchestratorV1Observation ?? throw new InvalidOperationException();
    private static EventOrchestratorV1Observation Ready(IRoomFlowReadValue value)
    {
        EventOrchestratorV1Observation result = Observation(value);
        Require(result.Status == EventOrchestratorV1Limits.ReadyStatus);
        return result;
    }
    private static void Pass() => _checks++;
    private static void Require(bool value) { if (!value) throw new InvalidOperationException(); }

    private sealed class Surface
    {
        internal NRun Run = null!; internal Player Player = null!; internal NMapScreen Map = null!;
        internal NOverlayStack Overlays = null!; internal NEventRoom Room = null!;
        internal EventOption Option = null!; internal NEventOptionButton Button = null!;

        internal static Surface Create(EventModel model, params string[] keys)
        {
            var value = new Surface { Player = new Player(), Map = new NMapScreen(),
                Overlays = new NOverlayStack() };
            model.Owner = value.Player;
            var layout = new NEventLayout();
            value.Room = new NEventRoom { Layout = layout };
            value.Run = new NRun { GlobalUi = new GlobalUiState {
                MapScreen = value.Map, Overlays = value.Overlays }, EventRoom = value.Room };
            foreach (string key in keys)
            {
                var option = new EventOption { TextKey = key };
                var button = new NEventOptionButton { Event = model, Option = option };
                button.Named["%Text"] = new MegaRichTextLabel { Text = key };
                layout.OptionButtons.Add(button);
                if (value.Option is null) { value.Option = option; value.Button = button; }
            }
            NRun.Instance = value.Run; NMapScreen.Instance = value.Map; NEventRoom.Instance = value.Room;
            return value;
        }
    }
}
