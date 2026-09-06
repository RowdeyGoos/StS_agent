using System;
using System.Collections.Generic;
using Godot;
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

namespace Sts2AgentBridge.Successors.CardSelectionV1.ParentNative;

public sealed class PinnedCardSelectionParentV1NativeAdapter : ICardSelectionParentV1NativeAdapter
{
    private BoundParent? _bound;
    private bool _beginDispatched;
    private bool _proceedDispatched;
    private bool _childSeen;
    private bool _childReady;
    private object? _screen;
    private object? _proceedIdentity;
    private Action? _proceedDispatch;
    private string? _afterWitness;
    private bool _afterEventFinished;
    private bool _afterEventProceed;
    private bool _afterRestRestored;
    private bool _afterTravelEnabled;
    private bool _disposed;
    private readonly Action _proceedAction;

    public PinnedCardSelectionParentV1NativeAdapter() => _proceedAction = Proceed;

    public CardSelectionParentV1SurfaceCapture CaptureSurface()
    {
        if (_disposed) return Unsupported();
        try { return CaptureCore(); }
        catch { return Unsupported(); }
    }

    public void Dispose() => _disposed = true;

    private CardSelectionParentV1SurfaceCapture CaptureCore()
    {
        NRun? run = NRun.Instance;
        if (!Valid(run)) return Missing();
        NMapScreen? map = run!.GlobalUi?.MapScreen;
        NOverlayStack? overlays = run.GlobalUi?.Overlays;
        if (run.GetType() != typeof(NRun) || !Valid(map) || map!.GetType() != typeof(NMapScreen) ||
            !Valid(overlays) || overlays!.GetType() != typeof(NOverlayStack) ||
            !ReferenceEquals(NMapScreen.Instance, map))
            return Missing();
        NMapScreen currentMap = map!;

        if (_bound is null)
        {
            if (overlays!.ScreenCount != 0 || map!.IsOpen || map.IsTravelEnabled || map.IsTraveling)
                return Unsupported();
            _bound = TryBindCheese(run, currentMap, overlays) ?? TryBindSmith(run, currentMap, overlays);
            if (_bound is null) return Missing();
        }
        if (!_bound.Matches(run, currentMap) || overlays!.ScreenCount < 0) return Unsupported();

        if (!_beginDispatched)
            return CaptureInitial(overlays, map!);
        if (overlays.ScreenCount == 1)
            return CaptureSelector(overlays, map!);
        if (overlays.ScreenCount != 0) return Unsupported();
        if (!_childSeen)
        {
            if (_screen is not null) return Unsupported();
            if (map!.IsOpen || map.IsTravelEnabled || map.IsTraveling ||
                !_bound.ParentEffectStillPending()) return Unsupported();
            return CaptureTransient("before-child", map!);
        }
        return CaptureAfterOrExit(map!);
    }

    private CardSelectionParentV1SurfaceCapture CaptureInitial(NOverlayStack overlays, NMapScreen map)
    {
        if (overlays.ScreenCount != 0 || !ValidateInitialStructure(out string witness) ||
            map.IsOpen || map.IsTravelEnabled || map.IsTraveling)
            return Unsupported();
        CardSelectionParentV1NativeControl control = new(
            _bound!.ParentController, _bound.BeginVisible(), _bound.BeginEnabled(), _bound.BeginDispatch);
        return Capture(CardSelectionParentV1Phase.Initial, witness, true, false, false, false,
            false, false, false, false, null, null, control, InitialProceedControl());
    }

    private CardSelectionParentV1SurfaceCapture CaptureSelector(NOverlayStack overlays, NMapScreen map)
    {
        object? current = overlays.Peek();
        if (_screen is null)
        {
            if (!_bound!.ExpectedScreen(current)) return Unsupported();
            _screen = current;
        }
        else if (!ReferenceEquals(_screen, current)) return Unsupported();
        if (map.IsOpen || map.IsTravelEnabled || map.IsTraveling || !_bound!.ParentEffectStillPending())
            return Unsupported();

        bool ready = _bound.Ready(_screen!);
        if (!ready)
        {
            if (_childReady) return Unsupported();
            return CaptureTransient("selector-initializing", map);
        }
        _childReady = true;
        _childSeen = true;
        string witness = _bound.Witness("child", new[] {
            new StructuralEntry(_bound.Policy.ParentStableKey, _screen!.GetType().FullName ?? "screen",
                true, true, false, false),
        });
        return Capture(CardSelectionParentV1Phase.Child, witness, false, false, false, false,
            false, false, false, false, _screen, _bound.ChildFactory, null, null);
    }

    private CardSelectionParentV1SurfaceCapture CaptureAfterOrExit(NMapScreen map)
    {
        if (_proceedDispatched && map.IsOpen && map.IsTravelEnabled && !map.IsTraveling)
            return Capture(CardSelectionParentV1Phase.Exit,
                _bound!.Witness("exit", Array.Empty<StructuralEntry>()), true,
                true, true, false, _bound.IsCheese && _bound.EventFinished(),
                _bound.IsCheese, !_bound.IsCheese, true, null, null, null, null);

        if (_proceedDispatched)
        {
            if (_afterWitness is null || map.IsOpen || map.IsTraveling ||
                map.IsTravelEnabled != _afterTravelEnabled) return Unsupported();
            return Capture(CardSelectionParentV1Phase.Transient, _afterWitness, true,
                false, _afterTravelEnabled, false, _afterEventFinished, _afterEventProceed,
                _afterRestRestored, true, null, null, null, null);
        }

        if (!_bound!.TryAfter(out object proceed, out Action dispatch,
                out bool eventFinished, out bool eventProceed, out bool restRestored,
                out bool travelEnabled, out StructuralEntry entry))
            return CaptureTransient("effect-pending", map);
        if (map.IsOpen || map.IsTraveling || map.IsTravelEnabled != travelEnabled)
            return Unsupported();
        dispatch = _proceedAction;
        if (_proceedIdentity is null)
        {
            _proceedIdentity = proceed;
            _proceedDispatch = dispatch;
        }
        else if (!ReferenceEquals(_proceedIdentity, proceed) ||
                 !ReferenceEquals(_proceedDispatch, dispatch)) return Unsupported();
        var control = new CardSelectionParentV1NativeControl(
            proceed, _bound.ProceedVisible(proceed), _bound.ProceedEnabled(proceed), dispatch);
        _afterWitness = _bound.Witness("after", new[] { entry });
        _afterEventFinished = eventFinished;
        _afterEventProceed = eventProceed;
        _afterRestRestored = restRestored;
        _afterTravelEnabled = travelEnabled;
        return Capture(CardSelectionParentV1Phase.After,
            _afterWitness, true, false, travelEnabled, false,
            eventFinished, eventProceed, restRestored, true, null, null, null, control);
    }

    private CardSelectionParentV1SurfaceCapture CaptureTransient(string reason, NMapScreen map) =>
        Capture(CardSelectionParentV1Phase.Transient,
            _bound!.Witness(reason, Array.Empty<StructuralEntry>()),
            _bound.NoOverlay(), map.IsOpen, map.IsTravelEnabled, map.IsTraveling,
            false, false, false, false, null, null, null, null);

    private CardSelectionParentV1SurfaceCapture Capture(
        CardSelectionParentV1Phase phase,
        string witness,
        bool noOverlay,
        bool mapOpen,
        bool travelEnabled,
        bool traveling,
        bool eventFinished,
        bool eventProceed,
        bool restRestored,
        bool effectObserved,
        object? screen,
        ICardSelectionParentV1ChildFactory? childFactory,
        CardSelectionParentV1NativeControl? begin,
        CardSelectionParentV1NativeControl? proceed) =>
        new(CardSelectionParentV1SurfaceStatus.Available, phase, _bound!.Policy,
            _bound.Run, _bound.Player, _bound.Room, _bound.Map,
            _bound.ParentOption, _bound.ParentController, witness,
            noOverlay, mapOpen, travelEnabled, traveling, eventFinished,
            eventProceed, restRestored, effectObserved, screen, childFactory, begin, proceed);

    private CardSelectionParentV1NativeControl? InitialProceedControl()
    {
        if (_bound!.IsCheese) return null;
        object proceed = _bound.InitialProceed!;
        return new CardSelectionParentV1NativeControl(
            proceed, _bound.ProceedVisible(proceed), _bound.ProceedEnabled(proceed),
            _bound.InitialProceedDispatch!);
    }

    private bool ValidateInitialStructure(out string witness)
    {
        witness = string.Empty;
        if (!_bound!.TryInitialEntries(out StructuralEntry[] entries,
                out object[] options, out object[] controllers) ||
            !CardSelectionParentV1NativeRules.SameReferences(_bound.Options, options) ||
            !CardSelectionParentV1NativeRules.SameReferences(_bound.Controllers, controllers))
            return false;
        witness = _bound.Witness("initial", entries);
        return witness == _bound.InitialWitness;
    }

    private BoundParent? TryBindCheese(NRun run, NMapScreen map, NOverlayStack overlays)
    {
        NEventRoom? room = run.EventRoom;
        NEventLayout? layout = room?.Layout;
        if (!Valid(room) || room!.GetType() != typeof(NEventRoom) || !Valid(layout) ||
            layout!.GetType() != typeof(NEventLayout) ||
            !room.IsVisibleInTree() || !layout!.IsVisibleInTree() ||
            room.CustomEventNode is not null || room.EmbeddedCombatRoom is not null)
            return null;
        if (!TryEventEntries(layout, out StructuralEntry[] entries, out object[] options,
                out object[] controllers, out RoomFullOfCheese? cheese, out Player? player,
                out EventOption? gorge, out NEventOptionButton? button))
            return null;
        var policy = new CardSelectionParentV1Policy(
            CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo,
            CardSelectionV1ParentKind.Event, CardSelectionParentV1Limits.CheeseGorgeStableKey,
            0, CardSelectionV1Operation.Add, 2, 2,
            CardSelectionV1CommitMode.AutoAtMax, 8);
        var bound = BoundParent.Cheese(run, player!, room, map, overlays, layout, cheese!, gorge!, button!,
            options, controllers, policy, BeginCheese, new CheeseChildFactory(
                run, player!, room, map, cheese!, gorge!, button!));
        bound.InitialWitness = bound.Witness("initial", entries);
        return bound;
    }

    private BoundParent? TryBindSmith(NRun run, NMapScreen map, NOverlayStack overlays)
    {
        NRestSiteRoom? room = run.RestSiteRoom;
        if (!Valid(room) || room!.GetType() != typeof(NRestSiteRoom) ||
            !room.IsVisibleInTree() || room.Characters.Count != 1)
            return null;
        NRestSiteCharacter? character = room.Characters[0];
        Player? player = character?.Player;
        if (!Valid(character) || character!.GetType() != typeof(NRestSiteCharacter) ||
            !character.IsVisibleInTree() || player is null) return null;
        if (!TryRestEntries(room, out StructuralEntry[] entries, out object[] options,
                out object[] controllers, out SmithRestSiteOption? smith, out NRestSiteButton? button))
            return null;
        int eligible = CountEligible(player);
        if (!CardSelectionParentV1NativeRules.ValidSmithDomainCount(eligible)) return null;
        NProceedButton? proceed = room.ProceedButton;
        if (!Valid(proceed) || proceed!.GetType() != typeof(NProceedButton) ||
            proceed.IsVisibleInTree() && proceed.IsEnabled) return null;
        var policy = new CardSelectionParentV1Policy(
            CardSelectionParentV1PolicyKind.RestSmithUpgradeOne,
            CardSelectionV1ParentKind.Rest, CardSelectionParentV1Limits.SmithStableKey,
            1, CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.PreviewConfirm, eligible);
        var bound = BoundParent.Smith(run, player, room, map, overlays, character, smith!, button!, proceed,
            options, controllers, policy, BeginSmith, new SmithChildFactory(
                eligible, run, player, room, map, smith!, button!));
        bound.InitialWitness = bound.Witness("initial", entries);
        return bound;
    }

    private void BeginCheese()
    {
        if (_beginDispatched) throw new InvalidOperationException("Begin already dispatched.");
        _beginDispatched = true;
        ((NEventOptionButton)_bound!.ParentController).ForceClick();
    }

    private void BeginSmith()
    {
        if (_beginDispatched) throw new InvalidOperationException("Begin already dispatched.");
        _beginDispatched = true;
        ((NRestSiteButton)_bound!.ParentController).ForceClick();
    }

    private void Proceed()
    {
        if (_proceedDispatched) throw new InvalidOperationException("Proceed already dispatched.");
        _proceedDispatched = true;
        if (_proceedIdentity is NEventOptionButton eventButton) eventButton.ForceClick();
        else if (_proceedIdentity is NProceedButton restButton) restButton.ForceClick();
        else throw new InvalidOperationException("Proceed control changed.");
    }

    private static bool TryEventEntries(
        NEventLayout layout,
        out StructuralEntry[] entries,
        out object[] options,
        out object[] controllers,
        out RoomFullOfCheese? cheese,
        out Player? player,
        out EventOption? gorge,
        out NEventOptionButton? gorgeButton)
    {
        entries = Array.Empty<StructuralEntry>();
        options = Array.Empty<object>();
        controllers = Array.Empty<object>();
        var es = new List<StructuralEntry>(); var os = new List<object>(); var cs = new List<object>();
        cheese = null; player = null; gorge = null; gorgeButton = null;
        foreach (NEventOptionButton? button in layout.OptionButtons)
        {
            if (es.Count >= CardSelectionParentV1NativeRules.MaximumStructuralEntries || !Valid(button) ||
                button!.Option is not EventOption option || button.Event is not RoomFullOfCheese current ||
                current.Owner is not Player owner || !ReferenceEquals(button.Event, current)) return false;
            if (cheese is null) { cheese = current; player = owner; }
            else if (!ReferenceEquals(cheese, current) || !ReferenceEquals(player, owner)) return false;
            es.Add(new StructuralEntry(option.TextKey, option.GetType().FullName ?? "EventOption",
                button.IsVisibleInTree(), button.IsEnabled, option.IsLocked, option.IsProceed));
            os.Add(option); cs.Add(button);
            if (option.TextKey == CardSelectionParentV1Limits.CheeseGorgeStableKey)
            {
                if (gorge is not null || option.IsProceed || option.IsLocked) return false;
                gorge = option; gorgeButton = button;
            }
        }
        if (es.Count == 0 || cheese is null || cheese.GetType() != typeof(RoomFullOfCheese) ||
            player is null || cheese.IsFinished || gorge is null || gorgeButton is null ||
            gorge.GetType() != typeof(EventOption) || gorgeButton.GetType() != typeof(NEventOptionButton) ||
            !gorgeButton.IsVisibleInTree() || !gorgeButton.IsEnabled) return false;
        entries = es.ToArray(); options = os.ToArray(); controllers = cs.ToArray(); return true;
    }

    private static bool TryRestEntries(
        NRestSiteRoom room,
        out StructuralEntry[] entries,
        out object[] options,
        out object[] controllers,
        out SmithRestSiteOption? smith,
        out NRestSiteButton? smithButton)
    {
        entries = Array.Empty<StructuralEntry>();
        options = Array.Empty<object>();
        controllers = Array.Empty<object>();
        var es = new List<StructuralEntry>(); var os = new List<object>(); var cs = new List<object>();
        smith = null; smithButton = null;
        foreach (Node node in Descendants(room))
        {
            if (node is not NRestSiteButton button) continue;
            RestSiteOption? option = button.Option;
            if (es.Count >= CardSelectionParentV1NativeRules.MaximumStructuralEntries || option is null ||
                !Valid(button) || !ReferenceEquals(room.GetButtonForOption(option), button)) return false;
            es.Add(new StructuralEntry(option.OptionId, option.GetType().FullName ?? "RestSiteOption",
                button.IsVisibleInTree(), button.IsEnabled, false, false));
            os.Add(option); cs.Add(button);
            if (option is SmithRestSiteOption current && current.OptionId == CardSelectionParentV1Limits.SmithStableKey)
            {
                if (smith is not null || current.SmithCount != 1 || current.GetType() != typeof(SmithRestSiteOption) ||
                    button.GetType() != typeof(NRestSiteButton)) return false;
                smith = current; smithButton = button;
            }
        }
        if (es.Count == 0 || smith is null || smithButton is null ||
            !smithButton.IsVisibleInTree() || !smithButton.IsEnabled || !smith.IsEnabled) return false;
        entries = es.ToArray(); options = os.ToArray(); controllers = cs.ToArray(); return true;
    }

    private static IEnumerable<Node> Descendants(Node root)
    {
        var queue = new Queue<Node>();
        foreach (Node child in root.GetChildren()) queue.Enqueue(child);
        int visited = 0;
        while (queue.Count != 0)
        {
            Node current = queue.Dequeue();
            if (++visited > 2048) throw new InvalidOperationException("Rest node graph is too large.");
            yield return current;
            foreach (Node child in current.GetChildren()) queue.Enqueue(child);
        }
    }

    private static int CountEligible(Player player)
    {
        var seen = new HashSet<object>(ReferenceEqualityComparer.Instance);
        int count = 0, total = 0;
        foreach (CardModel? card in player.Deck.Cards)
        {
            if (card is null || ++total > CardSelectionV1Limits.MaximumDeckCards || !seen.Add(card)) return -1;
            if (card.IsUpgradable) count++;
        }
        return count;
    }

    private static bool Valid(GodotObject? value) => value is not null && GodotObject.IsInstanceValid(value);

    private CardSelectionParentV1SurfaceCapture Missing() => Fixed(CardSelectionParentV1SurfaceStatus.Missing);
    private CardSelectionParentV1SurfaceCapture Unsupported() => Fixed(CardSelectionParentV1SurfaceStatus.Unsupported);
    private CardSelectionParentV1SurfaceCapture Fixed(CardSelectionParentV1SurfaceStatus status) =>
        new(status, CardSelectionParentV1Phase.Transient,
            _bound?.Policy ?? EmptyPolicy(), null, null, null, null, null, null, string.Empty,
            false, false, false, false, false, false, false, false,
            null, null, null, null);

    private static CardSelectionParentV1Policy EmptyPolicy() => new(
        CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo, CardSelectionV1ParentKind.Event,
        CardSelectionParentV1Limits.CheeseGorgeStableKey, 0,
        CardSelectionV1Operation.Add, 2, 2, CardSelectionV1CommitMode.AutoAtMax, 8);

    private sealed class CheeseChildFactory : ICardSelectionParentV1ChildFactory
    {
        private readonly NRun _run; private readonly Player _player; private readonly NEventRoom _room;
        private readonly NMapScreen _map; private readonly RoomFullOfCheese _event;
        private readonly EventOption _option; private readonly NEventOptionButton _button;
        internal CheeseChildFactory(NRun run, Player player, NEventRoom room, NMapScreen map,
            RoomFullOfCheese eventModel, EventOption option, NEventOptionButton button) =>
            (_run, _player, _room, _map, _event, _option, _button) =
            (run, player, room, map, eventModel, option, button);
        public ICardSelectionV1NativeAdapter Create(CardSelectionV1ParentContext context, object exactScreenIdentity)
        {
            if (exactScreenIdentity is not NSimpleCardSelectScreen screen)
                throw new InvalidOperationException("Wrong Cheese selector.");
            return PinnedCardSelectionV1NativeAdapter.CreateRoomFullOfCheese(
                context, _run, _player, _room, _map, _event, _option, _button, screen);
        }
    }

    private sealed class SmithChildFactory : ICardSelectionParentV1ChildFactory
    {
        private readonly int _count; private readonly NRun _run; private readonly Player _player;
        private readonly NRestSiteRoom _room; private readonly NMapScreen _map;
        private readonly SmithRestSiteOption _option; private readonly NRestSiteButton _button;
        internal SmithChildFactory(int count, NRun run, Player player, NRestSiteRoom room, NMapScreen map,
            SmithRestSiteOption option, NRestSiteButton button) =>
            (_count, _run, _player, _room, _map, _option, _button) =
            (count, run, player, room, map, option, button);
        public ICardSelectionV1NativeAdapter Create(CardSelectionV1ParentContext context, object exactScreenIdentity)
        {
            if (context.ExpectedDomainCount != _count || exactScreenIdentity is not NDeckUpgradeSelectScreen screen)
                throw new InvalidOperationException("Wrong Smith selector.");
            return PinnedCardSelectionV1NativeAdapter.CreateSmith(
                context, _run, _player, _room, _map, _option, _button, screen);
        }
    }

    private sealed class BoundParent
    {
        internal required bool IsCheese; internal required NRun Run; internal required Player Player;
        internal required CanvasItem Room; internal required NMapScreen Map;
        internal required NOverlayStack Overlays;
        internal required object ParentOption; internal required object ParentController;
        internal required object[] Options; internal required object[] Controllers;
        internal required CardSelectionParentV1Policy Policy; internal required Action BeginDispatch;
        internal required ICardSelectionParentV1ChildFactory ChildFactory;
        internal required Func<bool> BeginVisible; internal required Func<bool> BeginEnabled;
        internal required Func<string, StructuralEntry[], string> Witness;
        internal required Func<string, (bool ok, StructuralEntry[] entries, object[] options, object[] controllers)> Initial;
        internal required Func<object?, bool> ExpectedScreen; internal required Func<object, bool> Ready;
        internal required Func<bool> ParentEffectStillPending; internal required Func<bool> NoOverlay;
        internal required Func<bool> LiveBinding;
        internal required Func<bool> EventFinished; internal required Func<object, bool> ProceedVisible;
        internal required Func<object, bool> ProceedEnabled;
        internal required Func<(bool ok, object proceed, Action dispatch, bool eventFinished, bool eventProceed, bool restRestored, bool travelEnabled, StructuralEntry entry)> After;
        internal object? InitialProceed; internal Action? InitialProceedDispatch; internal string InitialWitness = string.Empty;

        internal bool Matches(NRun run, NMapScreen map) => ReferenceEquals(Run, run) &&
            ReferenceEquals(Map, map) && Valid(Run) && Valid(Room) && Valid(Map) &&
            Room.IsVisibleInTree() && ReferenceEquals(Overlays, Run.GlobalUi.Overlays) && LiveBinding();
        internal bool TryInitialEntries(out StructuralEntry[] e, out object[] o, out object[] c)
        { var x = Initial("initial"); e=x.entries; o=x.options; c=x.controllers; return x.ok; }
        internal bool TryAfter(out object p, out Action d, out bool ef, out bool ep, out bool rr, out bool te, out StructuralEntry e)
        { var x=After(); p=x.proceed; d=x.dispatch; ef=x.eventFinished; ep=x.eventProceed; rr=x.restRestored; te=x.travelEnabled; e=x.entry; return x.ok; }

        internal static BoundParent Cheese(NRun run, Player player, NEventRoom room, NMapScreen map,
            NOverlayStack overlays, NEventLayout layout, RoomFullOfCheese ev, EventOption option, NEventOptionButton button,
            object[] options, object[] controllers, CardSelectionParentV1Policy policy, Action begin,
            ICardSelectionParentV1ChildFactory factory)
        {
            Action? proceedDispatch = null; NEventOptionButton? proceed = null;
            return new BoundParent {
                IsCheese=true, Run=run, Player=player, Room=room, Map=map, Overlays=overlays, ParentOption=option,
                ParentController=button, Options=options, Controllers=controllers, Policy=policy,
                BeginDispatch=begin, ChildFactory=factory,
                BeginVisible=button.IsVisibleInTree, BeginEnabled=()=>button.IsEnabled,
                Witness=(phase, entries)=>CardSelectionParentV1NativeRules.StructuralWitness("cheese",phase,entries),
                Initial=_ => { bool ok=TryEventEntries(layout,out var e,out var o,out var c,out var ce,out var pl,out var go,out var bu) && ReferenceEquals(ce,ev)&&ReferenceEquals(pl,player)&&ReferenceEquals(go,option)&&ReferenceEquals(bu,button); return(ok,e,o,c); },
                ExpectedScreen=s=>s is NSimpleCardSelectScreen x && x.GetType()==typeof(NSimpleCardSelectScreen) && Valid(x),
                Ready=s=>PinnedCardSelectionV1NativeAdapter.IsRoomFullOfCheeseReady(run,player,room,map,ev,option,button,(NSimpleCardSelectScreen)s),
                ParentEffectStillPending=()=>!ev.IsFinished,
                NoOverlay=()=>run.GlobalUi.Overlays.ScreenCount==0,
                LiveBinding=()=>ReferenceEquals(NRun.Instance,run)&&ReferenceEquals(run.EventRoom,room)&&
                    ReferenceEquals(NEventRoom.Instance,room)&&ReferenceEquals(run.GlobalUi.MapScreen,map)&&
                    ReferenceEquals(NMapScreen.Instance,map)&&ReferenceEquals(run.GlobalUi.Overlays,overlays)&&
                    ReferenceEquals(room.Layout,layout)&&
                    ReferenceEquals(ev.Owner,player),
                EventFinished=()=>ev.IsFinished,
                ProceedVisible=o=>o is NEventOptionButton b && b.IsVisibleInTree(),
                ProceedEnabled=o=>o is NEventOptionButton b && b.IsEnabled,
                After=()=> {
                    if (!ev.IsFinished || map.IsTravelEnabled) return (false,null!,null!,false,false,false,false,default);
                    NEventOptionButton? only=null; int count=0;
                    foreach (NEventOptionButton candidate in layout.OptionButtons) { only=candidate; if (++count>1) break; }
                    if (count!=1 || only is null) return(false,null!,null!,false,false,false,false,default);
                    NEventOptionButton b=only; EventOption op=b.Option;
                    if (!Valid(b)||b.GetType()!=typeof(NEventOptionButton)||!b.IsVisibleInTree()||!b.IsEnabled||
                        op is null||op.GetType()!=typeof(EventOption)||!op.IsProceed||op.IsLocked||
                        !ReferenceEquals(b.Event,ev)||!ReferenceEquals(ev.Owner,player)) return(false,null!,null!,false,false,false,false,default);
                    var entry=new StructuralEntry(op.TextKey,op.GetType().FullName??"EventOption",true,true,false,true);
                    if (proceed is null) { proceed=b; proceedDispatch=b.ForceClick; }
                    if (!ReferenceEquals(proceed,b)) return(false,null!,null!,false,false,false,false,default);
                    return(true,(object)b,proceedDispatch!,true,true,false,false,entry); },
            };
        }

        internal static BoundParent Smith(NRun run, Player player, NRestSiteRoom room, NMapScreen map,
            NOverlayStack overlays, NRestSiteCharacter character, SmithRestSiteOption option, NRestSiteButton button,
            NProceedButton proceed, object[] options, object[] controllers, CardSelectionParentV1Policy policy,
            Action begin, ICardSelectionParentV1ChildFactory factory)
        {
            Action proceedAction = proceed.ForceClick;
            return new BoundParent {
                IsCheese=false, Run=run, Player=player, Room=room, Map=map, Overlays=overlays, ParentOption=option,
                ParentController=button, Options=options, Controllers=controllers, Policy=policy,
                BeginDispatch=begin, ChildFactory=factory, InitialProceed=proceed, InitialProceedDispatch=proceedAction,
                BeginVisible=button.IsVisibleInTree, BeginEnabled=()=>button.IsEnabled,
                Witness=(phase,entries)=>CardSelectionParentV1NativeRules.StructuralWitness("smith",phase,entries),
                Initial=_=> {
                    StructuralEntry[] e=Array.Empty<StructuralEntry>(); object[] o=Array.Empty<object>(); object[] c=Array.Empty<object>();
                    bool ok=room.Characters.Count==1&&ReferenceEquals(room.Characters[0],character)&&ReferenceEquals(character.Player,player)&&TryRestEntries(room,out e,out o,out c,out var sm,out var bu)&&ReferenceEquals(sm,option)&&ReferenceEquals(bu,button)&&ReferenceEquals(room.ProceedButton,proceed);
                    return(ok,e,o,c); },
                ExpectedScreen=s=>s is NDeckUpgradeSelectScreen x && x.GetType()==typeof(NDeckUpgradeSelectScreen)&&Valid(x),
                Ready=s=>PinnedCardSelectionV1NativeAdapter.IsSmithReady(policy.ExpectedDomainCount,run,player,room,map,option,button,(NDeckUpgradeSelectScreen)s),
                ParentEffectStillPending=()=>!(proceed.IsVisibleInTree()&&proceed.IsEnabled&&map.IsTravelEnabled),
                NoOverlay=()=>run.GlobalUi.Overlays.ScreenCount==0,
                LiveBinding=()=>ReferenceEquals(NRun.Instance,run)&&ReferenceEquals(run.RestSiteRoom,room)&&
                    ReferenceEquals(NRestSiteRoom.Instance,room)&&ReferenceEquals(run.GlobalUi.MapScreen,map)&&
                    ReferenceEquals(NMapScreen.Instance,map)&&ReferenceEquals(run.GlobalUi.Overlays,overlays)&&
                    room.Characters.Count==1&&
                    ReferenceEquals(room.Characters[0],character)&&Valid(character)&&
                    character.GetType()==typeof(NRestSiteCharacter)&&character.IsVisibleInTree()&&
                    ReferenceEquals(character.Player,player),
                EventFinished=()=>false,
                ProceedVisible=o=>ReferenceEquals(o,proceed)&&proceed.IsVisibleInTree(),
                ProceedEnabled=o=>ReferenceEquals(o,proceed)&&proceed.IsEnabled,
                After=()=> {
                    bool ready=room.Characters.Count==1&&ReferenceEquals(room.Characters[0],character)&&ReferenceEquals(character.Player,player)&&ReferenceEquals(room.ProceedButton,proceed)&&proceed.IsVisibleInTree()&&proceed.IsEnabled&&map.IsTravelEnabled;
                    var e=new StructuralEntry("PROCEED",proceed.GetType().FullName??"NProceedButton",proceed.IsVisibleInTree(),proceed.IsEnabled,false,true);
                    return ready?(true,(object)proceed,proceedAction,false,false,true,true,e):(false,null!,null!,false,false,false,false,default); },
            };
        }
    }
}
