using System;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;
using Sts2AgentBridge.Successors.CardSelectionV1.ParentNative;

internal static class Program
{
    private static int _checks;

    public static int Main()
    {
        try
        {
            CheeseBindsExactGorgeAndOwner();
            CheeseReadinessWaitThenChild();
            ForeignAndChangedOverlayFailClosed();
            BeginReservationPrecedesDispatch();
            CheeseAfterProceedAndMap();
            SmithBindsSolePlayerAndCompleteDomain();
            SmithRejectsAmbiguousCharacterProjection();
            ExactRuntimeTypesStayClosed();
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"card_selection_parent_v1_native_adapter\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static void CheeseBindsExactGorgeAndOwner()
    {
        CheeseFixture f = CheeseFixture.Create();
        using var adapter = new PinnedCardSelectionParentV1NativeAdapter();
        CardSelectionParentV1SurfaceCapture value = adapter.CaptureSurface();
        Equal(CardSelectionParentV1SurfaceStatus.Available, value.Status, "cheese available");
        Equal(CardSelectionParentV1Phase.Initial, value.Phase, "cheese initial");
        Equal(CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo, value.Policy.Kind, "cheese policy");
        Same(f.Player, value.PlayerIdentity, "event owner binds player");
        Same(f.Gorge, value.ParentOptionIdentity, "exact Gorge option");
        Same(f.GorgeButton, value.ParentControllerIdentity, "exact Gorge controller");
        True(value.BeginControl is { Visible: true, Enabled: true }, "begin legal");
        Equal(64, value.StructuralWitness.Length, "bounded witness");
        Pass();
    }

    private static void CheeseReadinessWaitThenChild()
    {
        CheeseFixture f = CheeseFixture.Create();
        using var adapter = new PinnedCardSelectionParentV1NativeAdapter();
        CardSelectionParentV1SurfaceCapture initial = adapter.CaptureSurface();
        initial.BeginControl!.Dispatch();
        var screen = new NSimpleCardSelectScreen();
        f.Overlays.Screens.Add(screen);
        PinnedCardSelectionV1NativeAdapter.CheeseReady = false;
        CardSelectionParentV1SurfaceCapture waiting = adapter.CaptureSurface();
        Equal(CardSelectionParentV1Phase.Transient, waiting.Phase, "readiness waits");
        False(waiting.NoActiveOverlay, "known selector occupies overlay");
        True(waiting.ScreenIdentity is null && waiting.ChildFactory is null,
            "unready selector not admitted");
        PinnedCardSelectionV1NativeAdapter.CheeseReady = true;
        CardSelectionParentV1SurfaceCapture child = adapter.CaptureSurface();
        Equal(CardSelectionParentV1Phase.Child, child.Phase, "ready child");
        Same(screen, child.ScreenIdentity, "exact first screen");
        True(child.ChildFactory is not null, "child factory published only when ready");
        Pass();
    }

    private static void ForeignAndChangedOverlayFailClosed()
    {
        CheeseFixture foreign = CheeseFixture.Create();
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
        {
            CardSelectionParentV1SurfaceCapture initial = adapter.CaptureSurface();
            initial.BeginControl!.Dispatch();
            foreign.Overlays.Screens.Add(new object());
            Equal(CardSelectionParentV1SurfaceStatus.Unsupported,
                adapter.CaptureSurface().Status, "foreign overlay rejected");
        }

        CheeseFixture changed = CheeseFixture.Create();
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
        {
            CardSelectionParentV1SurfaceCapture initial = adapter.CaptureSurface();
            initial.BeginControl!.Dispatch();
            var first = new NSimpleCardSelectScreen();
            changed.Overlays.Screens.Add(first);
            PinnedCardSelectionV1NativeAdapter.CheeseReady = false;
            Equal(CardSelectionParentV1Phase.Transient, adapter.CaptureSurface().Phase,
                "first selector retained while initializing");
            changed.Overlays.Screens[0] = new NSimpleCardSelectScreen();
            Equal(CardSelectionParentV1SurfaceStatus.Unsupported,
                adapter.CaptureSurface().Status, "replacement selector rejected");
        }


        CheeseFixture stack = CheeseFixture.Create();
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
        {
            Equal(CardSelectionParentV1SurfaceStatus.Available,
                adapter.CaptureSurface().Status, "overlay stack initially bound");
            stack.Run.GlobalUi.Overlays = new NOverlayStack();
            Equal(CardSelectionParentV1SurfaceStatus.Unsupported,
                adapter.CaptureSurface().Status, "replacement overlay stack rejected");
        }


        CheeseFixture disappeared = CheeseFixture.Create();
        using (var session = new CardSelectionParentV1Session(
            new string('1', 32), new PinnedCardSelectionParentV1NativeAdapter()))
        {
            var initial = (CardSelectionParentV1Observation)session.Read();
            Equal("accepted", ((CardSelectionParentV1DispatchReceipt)session.Apply(
                initial.DecisionId, "begin")).Outcome, "parent begin accepted");
            var screen = new NSimpleCardSelectScreen();
            disappeared.Overlays.Screens.Add(screen);
            PinnedCardSelectionV1NativeAdapter.CheeseReady = false;
            Equal("transient", ((CardSelectionParentV1Observation)session.Read()).Phase,
                "unready selector first retained");
            disappeared.Overlays.Screens.Clear();
            Equal("unsupported", ((CardSelectionParentV1Observation)session.Read()).Status,
                "retained selector disappearance rejected");
            disappeared.Overlays.Screens.Add(screen);
            PinnedCardSelectionV1NativeAdapter.CheeseReady = true;
            Equal("unsupported", ((CardSelectionParentV1Observation)session.Read()).Status,
                "disappeared selector never readopted");
        }
        Pass();
    }

    private static void BeginReservationPrecedesDispatch()
    {
        CheeseFixture duplicate = CheeseFixture.Create();
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
        {
            Action begin = adapter.CaptureSurface().BeginControl!.Dispatch;
            begin();
            Throws(begin, "duplicate begin rejected");
            Equal(1, duplicate.GorgeButton.Clicks, "one native begin click");
        }

        CheeseFixture uncertain = CheeseFixture.Create();
        uncertain.GorgeButton.ThrowClick = true;
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
        {
            Action begin = adapter.CaptureSurface().BeginControl!.Dispatch;
            Throws(begin, "native click fault propagated");
            uncertain.GorgeButton.ThrowClick = false;
            Throws(begin, "uncertain begin remains reserved");
            Equal(1, uncertain.GorgeButton.Clicks, "uncertain begin no retry");
        }
        Pass();
    }

    private static void CheeseAfterProceedAndMap()
    {
        CheeseFixture f = CheeseFixture.Create();
        using var adapter = new PinnedCardSelectionParentV1NativeAdapter();
        adapter.CaptureSurface().BeginControl!.Dispatch();
        var screen = new NSimpleCardSelectScreen();
        f.Overlays.Screens.Add(screen);
        PinnedCardSelectionV1NativeAdapter.CheeseReady = true;
        Equal(CardSelectionParentV1Phase.Child, adapter.CaptureSurface().Phase, "child seen");
        f.Overlays.Screens.Clear();
        CardSelectionParentV1SurfaceCapture pending = adapter.CaptureSurface();
        Equal(CardSelectionParentV1Phase.Transient, pending.Phase, "effect pending");
        False(pending.EffectCompletionObserved, "no early parent effect");

        f.Event.IsFinished = true;
        f.Layout.OptionButtons.Clear();
        var proceedOption = new EventOption { TextKey = "PROCEED", IsProceed = true };
        var proceed = new NEventOptionButton { Option = proceedOption, Event = f.Event };
        f.Layout.OptionButtons.Add(proceed);
        CardSelectionParentV1SurfaceCapture after = adapter.CaptureSurface();
        Equal(CardSelectionParentV1Phase.After, after.Phase, "event after");
        True(after.EventFinished && after.EventProceedSingleton && after.EffectCompletionObserved,
            "typed event completion");
        after.ProceedControl!.Dispatch();
        CardSelectionParentV1SurfaceCapture transition = adapter.CaptureSurface();
        Equal(CardSelectionParentV1Phase.Transient, transition.Phase, "post-Proceed wait");
        False(transition.MapOpen, "map not inferred");
        f.Map.IsOpen = true;
        f.Map.IsTravelEnabled = true;
        CardSelectionParentV1SurfaceCapture exit = adapter.CaptureSurface();
        Equal(CardSelectionParentV1Phase.Exit, exit.Phase, "same map exit");
        True(exit.MapOpen && exit.TravelEnabled && !exit.Traveling, "map handoff facts");
        Equal(1, proceed.Clicks, "one proceed click");
        Pass();
    }

    private static void SmithBindsSolePlayerAndCompleteDomain()
    {
        SmithFixture f = SmithFixture.Create(upgradable: 3, other: 2);
        using var adapter = new PinnedCardSelectionParentV1NativeAdapter();
        CardSelectionParentV1SurfaceCapture initial = adapter.CaptureSurface();
        Equal(CardSelectionParentV1SurfaceStatus.Available, initial.Status, "smith available");
        Equal(CardSelectionParentV1PolicyKind.RestSmithUpgradeOne, initial.Policy.Kind, "smith policy");
        Equal(3, initial.Policy.ExpectedDomainCount, "complete eligible domain");
        Same(f.Player, initial.PlayerIdentity, "sole rendered character player");
        Same(f.Smith, initial.ParentOptionIdentity, "exact Smith option");
        initial.BeginControl!.Dispatch();
        f.Overlays.Screens.Add(new NDeckUpgradeSelectScreen());
        PinnedCardSelectionV1NativeAdapter.SmithReady = true;
        Equal(CardSelectionParentV1Phase.Child, adapter.CaptureSurface().Phase, "smith child ready");
        Equal(3, PinnedCardSelectionV1NativeAdapter.LastSmithExpectedCount,
            "readiness receives exact eligible count");
        f.Overlays.Screens.Clear();
        f.Room.ProceedButton.Visible = true;
        f.Room.ProceedButton.IsEnabled = true;
        CardSelectionParentV1SurfaceCapture pending = adapter.CaptureSurface();
        Equal(CardSelectionParentV1Phase.Transient, pending.Phase,
            "rest requires travel-enabled after witness");
        f.Map.IsTravelEnabled = true;
        CardSelectionParentV1SurfaceCapture after = adapter.CaptureSurface();
        Equal(CardSelectionParentV1Phase.After, after.Phase, "rest after");
        True(after.RestControlsRestored && after.EffectCompletionObserved && after.TravelEnabled,
            "typed rest completion");
        after.ProceedControl!.Dispatch();
        f.Map.IsOpen = true;
        Equal(CardSelectionParentV1Phase.Exit, adapter.CaptureSurface().Phase,
            "rest explicit Proceed to same map");
        Pass();
    }

    private static void SmithRejectsAmbiguousCharacterProjection()
    {
        SmithFixture multiple = SmithFixture.Create(1, 0);
        multiple.Room.Characters.Add(new NRestSiteCharacter { Player = new Player() });
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
            Equal(CardSelectionParentV1SurfaceStatus.Missing,
                adapter.CaptureSurface().Status, "multiple rendered players rejected");

        SmithFixture changed = SmithFixture.Create(1, 0);
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
        {
            Equal(CardSelectionParentV1SurfaceStatus.Available,
                adapter.CaptureSurface().Status, "smith initially bound");
            changed.Character.Player = new Player();
            Equal(CardSelectionParentV1SurfaceStatus.Unsupported,
                adapter.CaptureSurface().Status, "retained player change rejected");
        }


        SmithFixture hidden = SmithFixture.Create(1, 0);
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
        {
            Equal(CardSelectionParentV1SurfaceStatus.Available,
                adapter.CaptureSurface().Status, "rendered character initially valid");
            hidden.Character.Visible = false;
            Equal(CardSelectionParentV1SurfaceStatus.Unsupported,
                adapter.CaptureSurface().Status, "retained character visibility change rejected");
        }
        Pass();
    }

    private static void ExactRuntimeTypesStayClosed()
    {
        CheeseFixture cheese = CheeseFixture.Create();
        var derivedLayout = new DerivedEventLayout();
        foreach (NEventOptionButton button in cheese.Layout.OptionButtons)
            derivedLayout.OptionButtons.Add(button);
        cheese.Room.Layout = derivedLayout;
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
            Equal(CardSelectionParentV1SurfaceStatus.Missing,
                adapter.CaptureSurface().Status, "derived event layout rejected");

        SmithFixture smith = SmithFixture.Create(1, 0);
        smith.Room.Characters.Clear();
        smith.Room.Characters.Add(new DerivedRestSiteCharacter { Player = smith.Player });
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
            Equal(CardSelectionParentV1SurfaceStatus.Missing,
                adapter.CaptureSurface().Status, "derived rest character rejected");

        SmithFixture proceed = SmithFixture.Create(1, 0);
        proceed.Room.ProceedButton = new DerivedProceedButton {
            Visible = false, IsEnabled = false };
        using (var adapter = new PinnedCardSelectionParentV1NativeAdapter())
            Equal(CardSelectionParentV1SurfaceStatus.Missing,
                adapter.CaptureSurface().Status, "derived Proceed rejected");
        Pass();
    }

    private static void Reset(NRun run, NMapScreen map)
    {
        NRun.Instance = run;
        NMapScreen.Instance = map;
        NEventRoom.Instance = null;
        NRestSiteRoom.Instance = null;
        PinnedCardSelectionV1NativeAdapter.CheeseReady = false;
        PinnedCardSelectionV1NativeAdapter.SmithReady = false;
    }

    private sealed class CheeseFixture
    {
        internal required NRun Run;
        internal required NMapScreen Map;
        internal required NOverlayStack Overlays;
        internal required NEventRoom Room;
        internal required NEventLayout Layout;
        internal required Player Player;
        internal required RoomFullOfCheese Event;
        internal required EventOption Gorge;
        internal required NEventOptionButton GorgeButton;

        internal static CheeseFixture Create()
        {
            var map = new NMapScreen();
            var overlays = new NOverlayStack();
            var player = new Player();
            var model = new RoomFullOfCheese { Owner = player };
            var gorge = new EventOption {
                TextKey = CardSelectionParentV1Limits.CheeseGorgeStableKey };
            var leave = new EventOption { TextKey = "LEAVE" };
            var gorgeButton = new NEventOptionButton { Option = gorge, Event = model };
            var layout = new NEventLayout();
            layout.OptionButtons.Add(gorgeButton);
            layout.OptionButtons.Add(new NEventOptionButton { Option = leave, Event = model });
            var room = new NEventRoom { Layout = layout };
            var run = new NRun {
                GlobalUi = new GlobalUiState { MapScreen = map, Overlays = overlays },
                EventRoom = room };
            Reset(run, map);
            NEventRoom.Instance = room;
            return new CheeseFixture { Run=run, Map=map, Overlays=overlays, Room=room,
                Layout=layout, Player=player, Event=model, Gorge=gorge, GorgeButton=gorgeButton };
        }
    }

    private sealed class SmithFixture
    {
        internal required NRun Run;
        internal required NMapScreen Map;
        internal required NOverlayStack Overlays;
        internal required NRestSiteRoom Room;
        internal required Player Player;
        internal required NRestSiteCharacter Character;
        internal required SmithRestSiteOption Smith;

        internal static SmithFixture Create(int upgradable, int other)
        {
            var map = new NMapScreen();
            var overlays = new NOverlayStack();
            var player = new Player();
            for (int i = 0; i < upgradable; i++)
                player.Deck.Cards.Add(new CardModel { IsUpgradable = true });
            for (int i = 0; i < other; i++)
                player.Deck.Cards.Add(new CardModel());
            var character = new NRestSiteCharacter { Player = player };
            var smith = new SmithRestSiteOption {
                OptionId = CardSelectionParentV1Limits.SmithStableKey, SmithCount = 1 };
            var button = new NRestSiteButton { Option = smith };
            var proceed = new NProceedButton { Visible = false, IsEnabled = false };
            var room = new NRestSiteRoom { ProceedButton = proceed };
            room.Characters.Add(character);
            room.AddOption(smith, button);
            var run = new NRun {
                GlobalUi = new GlobalUiState { MapScreen = map, Overlays = overlays },
                RestSiteRoom = room };
            Reset(run, map);
            NRestSiteRoom.Instance = room;
            return new SmithFixture { Run=run, Map=map, Overlays=overlays, Room=room,
                Player=player, Character=character, Smith=smith };
        }
    }

    private sealed class DerivedEventLayout : NEventLayout { }
    private sealed class DerivedRestSiteCharacter : NRestSiteCharacter { }
    private sealed class DerivedProceedButton : NProceedButton { }

    private static void Pass() => _checks++;
    private static void True(bool value, string message)
    { if (!value) throw new InvalidOperationException(message); }
    private static void False(bool value, string message) => True(!value, message);
    private static void Equal<T>(T expected, T actual, string message)
    {
        if (!Equals(expected, actual))
            throw new InvalidOperationException($"{message}: expected {expected}, got {actual}");
    }
    private static void Same(object expected, object? actual, string message) =>
        True(ReferenceEquals(expected, actual), message);
    private static void Throws(Action action, string message)
    {
        try { action(); }
        catch (InvalidOperationException) { return; }
        throw new InvalidOperationException(message);
    }
}
