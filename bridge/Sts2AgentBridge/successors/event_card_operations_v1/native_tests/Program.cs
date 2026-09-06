using System;
using System.Collections.Generic;
using System.Text.Json;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.EventOrchestratorV1.Native;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.NativeTests;

internal static class Program
{
    private const string Nonce = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private static int _checks;

    public static int Main()
    {
        try
        {
            OrdinaryFactoriesAreStable(); Pass();
            CheeseDispatchAndChildAreBound(); Pass();
            CheeseReadinessCannotReadopt(); Pass();
            ChildGuardRejectsContextChanges(); Pass();
            TextOnlyChangeRetainsChildWindow(); Pass();
            StructuralChangeRevokesChild(); Pass();
            ExactRuntimeTypesAreRequired(); Pass();
            DispatchUncertaintyHasNoRetry(); Pass();
            ProceedUsesSameMapExit(); Pass();
            ExitRejectsChangedBinding(); Pass();
            SelectedUpgradeRowsAreClosedAndStable(); Pass();
            InvalidDomainDisablesDispatch(); Pass();
            EventCardReadinessCannotReadopt(); Pass();
            OtherPositiveCallerEventsAreWholeUnsupported(); Pass();
            Console.WriteLine(JsonSerializer.Serialize(new { schema_version = 1, status = "passed",
                suite = "event_card_operations_v1_native", check_count = _checks }));
            return 0;
        }
        catch
        {
            Console.Error.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"error\":\"fixture_failure\"}");
            return 1;
        }
    }

    private static void OrdinaryFactoriesAreStable()
    {
        Surface s = Surface.Ordinary("A", "B");
        var builder = new RecordingBuilder();
        using var adapter = new PinnedEventOrchestratorV1NativeAdapter(builder);
        EventOrchestratorV1SurfaceCapture first = adapter.CaptureSurface();
        EventOrchestratorV1SurfaceCapture second = adapter.CaptureSurface();
        Require(first.Status == EventOrchestratorV1SurfaceStatus.Parent && first.Candidates.Count == 2);
        Require(second.Candidates.Count == 2 && builder.Values.Count == 2);
        for (int i = 0; i < 2; i++)
        {
            Require(first.Candidates[i].ChildPolicy?.PolicyKind == EventOrchestratorV1ChildPolicyKind.ItemReward);
            Require(ReferenceEquals(first.Candidates[i].ChildFactory, second.Candidates[i].ChildFactory));
            Require(ReferenceEquals(first.Candidates[i].Dispatch, second.Candidates[i].Dispatch));
        }
    }

    private static void CheeseDispatchAndChildAreBound()
    {
        Surface s = Surface.Cheese();
        var builder = new RecordingBuilder();
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(builder));
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Require(decision.Candidates[0].ChildPolicy == EventOrchestratorV1Limits.CheeseGorgeAddTwoPolicy);
        Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        Require(s.Buttons[0].Clicks == 1);
        var screen = new NSimpleCardSelectScreen();
        s.Overlays.Screens.Add(screen);
        PinnedCardSelectionV1NativeAdapter.Ready = true;
        EventOrchestratorV1Observation child = Observation(session.Read());
        Require(child.Status == EventOrchestratorV1Limits.ChildStatus && builder.Values.Count == 1);
        Require(builder.Values[0].Accepted is not null && builder.Values[0].Check());
    }

    private static void ChildGuardRejectsContextChanges()
    {
        Surface s = Surface.Ordinary("ITEM");
        var builder = new RecordingBuilder();
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(builder));
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        var screen = new NRewardsScreen(); s.Overlays.Screens.Add(screen);
        _ = session.Read();
        RecordingFactory factory = builder.Values[0];
        Require(factory.Check());
        s.Map.IsTravelEnabled = true; Require(!factory.Check()); s.Map.IsTravelEnabled = false;
        s.Room.CustomEventNode = new object(); Require(!factory.Check()); s.Room.CustomEventNode = null;
        s.Room.EmbeddedCombatRoom = new object(); Require(!factory.Check()); s.Room.EmbeddedCombatRoom = null;
        s.Overlays.Screens[0] = new NRewardsScreen(); Require(!factory.Check());
        s.Overlays.Screens[0] = screen; screen.Visible = false; Require(!factory.Check());
        screen.Visible = true; screen.InstanceValid = false; Require(!factory.Check());
    }

    private static void CheeseReadinessCannotReadopt()
    {
        Surface s = Surface.Cheese();
        PinnedCardSelectionV1NativeAdapter.Ready = false;
        using (var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder())))
        {
            EventOrchestratorV1Observation decision = Ready(session.Read());
            Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
            var screen = new NSimpleCardSelectScreen(); s.Overlays.Screens.Add(screen);
            Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.WaitingStatus);
            PinnedCardSelectionV1NativeAdapter.Ready = true;
            Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.ChildStatus);
        }

        s = Surface.Cheese(); PinnedCardSelectionV1NativeAdapter.Ready = false;
        using (var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder())))
        {
            EventOrchestratorV1Observation decision = Ready(session.Read());
            _ = session.Apply(decision.DecisionId, "choose:0");
            s.Overlays.Screens.Add(new NSimpleCardSelectScreen());
            Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.WaitingStatus);
            s.Overlays.Screens.Clear();
            Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.UnsupportedStatus);
        }

        s = Surface.Cheese(); PinnedCardSelectionV1NativeAdapter.Ready = false;
        using (var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder())))
        {
            EventOrchestratorV1Observation decision = Ready(session.Read());
            _ = session.Apply(decision.DecisionId, "choose:0");
            s.Overlays.Screens.Add(new NSimpleCardSelectScreen());
            _ = session.Read();
            s.Overlays.Screens[0] = new NSimpleCardSelectScreen();
            Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.UnsupportedStatus);
        }
    }

    private static void TextOnlyChangeRetainsChildWindow()
    {
        Surface s = Surface.Ordinary("ITEM");
        var builder = new RecordingBuilder();
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(builder));
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        s.Labels[0].Text = "changed text";
        Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.WaitingStatus);
        s.Overlays.Screens.Add(new NRewardsScreen());
        Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.ChildStatus);
    }

    private static void StructuralChangeRevokesChild()
    {
        Surface s = Surface.Ordinary("ITEM");
        var builder = new RecordingBuilder();
        using var adapter = new PinnedEventOrchestratorV1NativeAdapter(builder);
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        s.Buttons[0].IsEnabled = false;
        _ = session.Read();
        s.Overlays.Screens.Add(new NRewardsScreen());
        Require(adapter.CaptureSurface().Status == EventOrchestratorV1SurfaceStatus.Unsupported);
    }

    private static void ExactRuntimeTypesAreRequired()
    {
        Surface s = Surface.Ordinary("A");
        s.Room.Layout = new DerivedLayout();
        using var adapter = new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder());
        Require(adapter.CaptureSurface().Status == EventOrchestratorV1SurfaceStatus.Missing);
        s = Surface.Ordinary("A");
        s.Layout.OptionButtons.Clear();
        var option = new EventOption { TextKey = "A" };
        var button = new DerivedButton { Event = s.Event, Option = option };
        button.Named["%Text"] = new MegaRichTextLabel { Text = "A" };
        s.Layout.OptionButtons.Add(button);
        using var adapter2 = new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder());
        Require(adapter2.CaptureSurface().Status == EventOrchestratorV1SurfaceStatus.Unsupported);
    }

    private static void DispatchUncertaintyHasNoRetry()
    {
        Surface s = Surface.Ordinary("A"); s.Buttons[0].ThrowClick = true;
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder()));
        EventOrchestratorV1Observation decision = Ready(session.Read());
        var failure = session.Apply(decision.DecisionId, "choose:0") as RoomFlowApplyFailure;
        Require(failure?.Outcome == "uncertain" && s.Buttons[0].Clicks == 1);
        Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowApplyFailure && s.Buttons[0].Clicks == 1);
    }

    private static void ProceedUsesSameMapExit()
    {
        Surface s = Surface.Proceed();
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder()));
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Require(decision.Phase == EventOrchestratorV1Limits.ProceedPhase);
        Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        s.Room.Visible = false; s.Map.IsOpen = true; s.Map.IsTravelEnabled = true;
        Require(session.Read() is EventOrchestratorV1ResolvedResult && s.Buttons[0].Clicks == 1);
    }

    private static void ExitRejectsChangedBinding()
    {
        Surface s = Surface.Proceed();
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder()));
        EventOrchestratorV1Observation decision = Ready(session.Read());
        _ = session.Apply(decision.DecisionId, "choose:0");
        s.Map.IsOpen = true; s.Map.IsTravelEnabled = true;
        s.Run.EventRoom = new NEventRoom { Layout = s.Layout };
        Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.UnsupportedStatus);
    }

    private static void SelectedUpgradeRowsAreClosedAndStable()
    {
        foreach ((EventModel model, string supported, string blocked) in new[]
        {
            ((EventModel)new AromaOfChaos(), EventCardOperationNativeRegistry.AromaSupportedKey,
                EventCardOperationNativeRegistry.AromaUnsupportedKey),
            ((EventModel)new SapphireSeed(), EventCardOperationNativeRegistry.SapphireSupportedKey,
                EventCardOperationNativeRegistry.SapphireUnsupportedKey),
        })
        {
            EventCardOperationBinding.Reset();
            Surface s = Surface.Selected(model, supported, blocked);
            var builder = new RecordingBuilder();
            using var adapter = new PinnedEventOrchestratorV1NativeAdapter(builder);
            EventOrchestratorV1SurfaceCapture first = adapter.CaptureSurface();
            EventOrchestratorV1SurfaceCapture second = adapter.CaptureSurface();
            Require(first.Status == EventOrchestratorV1SurfaceStatus.Parent &&
                first.Candidates.Count == 2 && builder.Values.Count == 1 &&
                EventCardOperationBinding.PreparedCount == 1);
            Require(first.Candidates[0].CapabilityKind ==
                EventOrchestratorV1CapabilityKind.SupportedCardSelection &&
                first.Candidates[0].ChildDomainCount == 2 &&
                first.Candidates[0].ChildPolicy?.PolicyKind ==
                    EventOrchestratorV1ChildPolicyKind.EventCardSelection &&
                ReferenceEquals(first.Candidates[0].ChildFactory,
                    second.Candidates[0].ChildFactory));
            Require(first.Candidates[1].CapabilityKind ==
                EventOrchestratorV1CapabilityKind.UnsupportedCardSelection &&
                first.Candidates[1].ChildDomainCount == 0 &&
                first.Candidates[1].ChildPolicy is null &&
                first.Candidates[1].ChildFactory is null);
        }
    }

    private static void InvalidDomainDisablesDispatch()
    {
        EventCardOperationBinding.Reset();
        EventCardOperationBinding.Allow = false;
        Surface s = Surface.Selected(new AromaOfChaos(),
            EventCardOperationNativeRegistry.AromaSupportedKey,
            EventCardOperationNativeRegistry.AromaUnsupportedKey);
        using var adapter = new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder());
        EventOrchestratorV1SurfaceCapture capture = adapter.CaptureSurface();
        Require(capture.Status == EventOrchestratorV1SurfaceStatus.Parent);
        foreach (EventOrchestratorV1NativeCandidate candidate in capture.Candidates)
            Require(candidate.CapabilityKind ==
                EventOrchestratorV1CapabilityKind.UnsupportedCardSelection &&
                candidate.ChildPolicy is null && candidate.ChildFactory is null);
        EventCardOperationBinding.Reset();

        s = Surface.Selected(new SapphireSeed(),
            EventCardOperationNativeRegistry.SapphireSupportedKey,
            EventCardOperationNativeRegistry.SapphireUnsupportedKey);
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder()));
        EventOrchestratorV1Observation decision = Ready(session.Read());
        EventCardOperationBinding.Allow = false;
        Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowApplyFailure &&
            s.Buttons[0].Clicks == 0);
        EventCardOperationBinding.Reset();
    }

    private static void EventCardReadinessCannotReadopt()
    {
        EventCardOperationBinding.Reset();
        EventCardSelectionV1NativeAdapter.Ready = false;
        Surface s = Surface.Selected(new SapphireSeed(),
            EventCardOperationNativeRegistry.SapphireSupportedKey,
            EventCardOperationNativeRegistry.SapphireUnsupportedKey);
        using var session = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder()));
        EventOrchestratorV1Observation decision = Ready(session.Read());
        Require(session.Apply(decision.DecisionId, "choose:0") is RoomFlowDispatchReceipt);
        var screen = new NDeckUpgradeSelectScreen();
        s.Overlays.Screens.Add(screen);
        Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.WaitingStatus);
        EventCardSelectionV1NativeAdapter.Ready = true;
        Require(Observation(session.Read()).Status == EventOrchestratorV1Limits.ChildStatus);

        EventCardOperationBinding.Reset();
        EventCardSelectionV1NativeAdapter.Ready = false;
        s = Surface.Selected(new AromaOfChaos(),
            EventCardOperationNativeRegistry.AromaSupportedKey,
            EventCardOperationNativeRegistry.AromaUnsupportedKey);
        using var second = new EventOrchestratorV1Session(Nonce,
            new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder()));
        decision = Ready(second.Read());
        _ = second.Apply(decision.DecisionId, "choose:0");
        s.Overlays.Screens.Add(new NDeckUpgradeSelectScreen());
        _ = second.Read();
        s.Overlays.Screens.Clear();
        Require(Observation(second.Read()).Status == EventOrchestratorV1Limits.UnsupportedStatus);
        EventCardSelectionV1NativeAdapter.Ready = false;
    }

    private static void OtherPositiveCallerEventsAreWholeUnsupported()
    {
        foreach (EventModel model in new EventModel[]
        {
            new Amalgamator(), new BattlewornDummy(), new BrainLeech(),
            new Bugslayer(), new ByrdonisNest(), new DoorsOfLightAndDark(),
            new EndlessConveyor(), new FieldOfManSizedHoles(),
            new GraveOfTheForgotten(), new InfestedAutomaton(), new LuminousChoir(),
            new MorphicGrove(), new Reflections(), new SelfHelpBook(),
            new SlipperyBridge(), new SpiralingWhirlpool(), new SpiritGrafter(),
            new StoneOfAllTime(), new Symbiote(), new TabletOfTruth(),
            new TheLegendsWereTrue(), new TinkerTime(), new TrashHeap(), new Trial(),
            new WarHistorianRepy(), new WaterloggedScriptorium(), new Wellspring(),
            new WhisperingHollow(), new WoodCarvings(), new ZenWeaver(),
        })
        {
            Surface blocked = Surface.Selected(model, "UNKNOWN");
            using var adapter = new PinnedEventOrchestratorV1NativeAdapter(
                new RecordingBuilder());
            Require(adapter.CaptureSurface().Status ==
                EventOrchestratorV1SurfaceStatus.Unsupported);
        }

        Surface s = Surface.Selected(new AromaOfChaos(),
            EventCardOperationNativeRegistry.AromaSupportedKey, "UNKNOWN");
        using var selected = new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder());
        Require(selected.CaptureSurface().Status == EventOrchestratorV1SurfaceStatus.Unsupported);

        s = Surface.Selected(new DerivedAroma(),
            EventCardOperationNativeRegistry.AromaSupportedKey,
            EventCardOperationNativeRegistry.AromaUnsupportedKey);
        using var derived = new PinnedEventOrchestratorV1NativeAdapter(new RecordingBuilder());
        Require(derived.CaptureSurface().Status == EventOrchestratorV1SurfaceStatus.Unsupported);
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

    private sealed class DerivedLayout : NEventLayout { }
    private sealed class DerivedButton : NEventOptionButton { }
    private sealed class DerivedAroma : AromaOfChaos { }

    private sealed class Surface
    {
        internal NRun Run = null!; internal NMapScreen Map = null!; internal NOverlayStack Overlays = null!;
        internal NEventRoom Room = null!; internal NEventLayout Layout = null!; internal EventModel Event = null!;
        internal List<NEventOptionButton> Buttons = new(); internal List<MegaRichTextLabel> Labels = new();

        internal static Surface Ordinary(params string[] keys) => Create(new EventModel(), false, keys);
        internal static Surface Selected(EventModel model, params string[] keys) =>
            Create(model, false, keys);
        internal static Surface Cheese() => Create(new RoomFullOfCheese(), false,
            PinnedEventOrchestratorV1NativeAdapter.CheeseStableId);
        internal static Surface Proceed() => Create(new EventModel(), true, "PROCEED");
        private static Surface Create(EventModel eventModel, bool finished, params string[] keys)
        {
            var value = new Surface(); var player = new Player();
            eventModel.Owner = player; eventModel.IsFinished = finished;
            value.Map = new NMapScreen(); value.Overlays = new NOverlayStack();
            value.Layout = new NEventLayout(); value.Room = new NEventRoom { Layout = value.Layout };
            value.Run = new NRun { GlobalUi = new GlobalUiState { MapScreen = value.Map,
                Overlays = value.Overlays }, EventRoom = value.Room };
            value.Event = eventModel;
            NRun.Instance = value.Run; NMapScreen.Instance = value.Map; NEventRoom.Instance = value.Room;
            foreach (string key in keys)
            {
                var option = new EventOption { TextKey = key, IsProceed = finished };
                var label = new MegaRichTextLabel { Text = key };
                var button = new NEventOptionButton { Event = eventModel, Option = option };
                button.Named["%Text"] = label;
                value.Layout.OptionButtons.Add(button); value.Buttons.Add(button); value.Labels.Add(label);
            }
            return value;
        }
    }
}
