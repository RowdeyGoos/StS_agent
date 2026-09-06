using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Godot;
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
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Native;

public sealed class PinnedEventOrchestratorV1NativeAdapter : IEventOrchestratorV1NativeAdapter
{
    internal const string CheeseStableId = "ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE";
    private readonly IEventOrchestratorV1NativeChildFactoryBuilder _factoryBuilder;
    private readonly List<CandidateBinding> _bindings = new();
    private BoundEvent? _bound;
    private CandidateBinding? _pending;
    private string? _pendingProjection;
    private string? _currentProjection;
    private object? _expectedCheeseScreen;
    private bool _cheeseReadyPublished;
    private object? _expectedEventCardScreen;
    private bool _eventCardReadyPublished;
    private bool _disposed;

    public PinnedEventOrchestratorV1NativeAdapter()
        : this(ProductionEventOrchestratorV1ChildFactoryBuilder.Instance) { }

    internal PinnedEventOrchestratorV1NativeAdapter(
        IEventOrchestratorV1NativeChildFactoryBuilder factoryBuilder) =>
        _factoryBuilder = factoryBuilder ?? throw new ArgumentNullException(nameof(factoryBuilder));

    public EventOrchestratorV1SurfaceCapture CaptureSurface()
    {
        if (_disposed) return EventOrchestratorV1SurfaceCapture.Unsupported();
        try { return CaptureCore(); }
        catch { return EventOrchestratorV1SurfaceCapture.Unsupported(); }
    }

    public EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending)
    {
        if (_disposed || pending is null || _bound is null || !_bound.MatchesExitReferences())
            throw new InvalidOperationException("Event exit binding is unavailable.");
        BoundEvent bound = _bound;
        if (!ReferenceEquals(pending.RunIdentity, bound.Run) ||
            !ReferenceEquals(pending.PlayerIdentity, bound.Player) ||
            !ReferenceEquals(pending.RoomIdentity, bound.Room) ||
            !ReferenceEquals(pending.MapIdentity, bound.Map))
            throw new InvalidOperationException("Event exit binding changed.");
        return new EventOrchestratorV1ExitCapture(
            bound.Run, bound.Player, bound.Room, bound.Map,
            bound.Map.IsOpen, bound.Map.IsTravelEnabled, bound.Map.IsTraveling);
    }

    public void Dispose()
    {
        _disposed = true;
        _pending = null;
        _pendingProjection = null;
        _currentProjection = null;
        _expectedCheeseScreen = null;
        _cheeseReadyPublished = false;
        _expectedEventCardScreen = null;
        _eventCardReadyPublished = false;
        _bindings.Clear();
        _bound = null;
    }

    private EventOrchestratorV1SurfaceCapture CaptureCore()
    {
        NRun? run = NRun.Instance;
        if (!ValidExact<NRun>(run)) return EventOrchestratorV1SurfaceCapture.Missing();
        var globalUi = run!.GlobalUi;
        NMapScreen? map = globalUi?.MapScreen;
        NOverlayStack? overlays = globalUi?.Overlays;
        NEventRoom? room = run.EventRoom;
        if (!Valid(globalUi) || !ValidExact<NMapScreen>(map) ||
            !ValidExact<NOverlayStack>(overlays) || !ValidExact<NEventRoom>(room) ||
            !ReferenceEquals(NMapScreen.Instance, map) ||
            !ReferenceEquals(NEventRoom.Instance, room))
            return EventOrchestratorV1SurfaceCapture.Missing();

        if (_bound is not null && !_bound.MatchesLive(run, room, map!, overlays!))
            return EventOrchestratorV1SurfaceCapture.Unsupported();
        if (map!.IsOpen || map.IsTravelEnabled || map.IsTraveling ||
            room!.CustomEventNode is not null || room.EmbeddedCombatRoom is not null ||
            !room.IsVisibleInTree())
            return EventOrchestratorV1SurfaceCapture.Unsupported();

        int screenCount = overlays!.ScreenCount;
        if (screenCount < 0) return EventOrchestratorV1SurfaceCapture.Unsupported();
        if (screenCount != 0) return CaptureChild(overlays);
        if (_expectedCheeseScreen is not null && !_cheeseReadyPublished)
            return EventOrchestratorV1SurfaceCapture.Unsupported();
        if (_expectedEventCardScreen is not null && !_eventCardReadyPublished)
            return EventOrchestratorV1SurfaceCapture.Unsupported();

        NEventLayout? layout = room.Layout;
        if (_bound is not null && !ReferenceEquals(layout, _bound.Layout))
            return EventOrchestratorV1SurfaceCapture.Unsupported();
        if (!ValidExact<NEventLayout>(layout) || !layout!.IsVisibleInTree())
            return _bound is not null && _pending is not null
                ? Transient(_bound) : EventOrchestratorV1SurfaceCapture.Missing();

        var raw = new List<RawCandidate>();
        EventModel? eventModel = null;
        Player? player = null;
        foreach (NEventOptionButton? button in layout.OptionButtons)
        {
            if (raw.Count >= EventOrchestratorV1Limits.MaximumCandidates ||
                !ValidExact<NEventOptionButton>(button) ||
                button!.Option is not EventOption option || option.GetType() != typeof(EventOption) ||
                button.Event is not EventModel currentEvent || currentEvent.Owner is not Player currentPlayer ||
                !ReferenceEquals(button.Option, option) || !ReferenceEquals(button.Event, currentEvent))
                return EventOrchestratorV1SurfaceCapture.Unsupported();
            if (eventModel is null) { eventModel = currentEvent; player = currentPlayer; }
            else if (!ReferenceEquals(eventModel, currentEvent) || !ReferenceEquals(player, currentPlayer))
                return EventOrchestratorV1SurfaceCapture.Unsupported();
            Node labelNode = button.GetNode("%Text");
            if (labelNode is not MegaRichTextLabel label || !ValidExact<MegaRichTextLabel>(label))
                return EventOrchestratorV1SurfaceCapture.Unsupported();
            bool dangerous = option.WillKillPlayer is Func<Player, bool> predicate && predicate(currentPlayer);
            raw.Add(new RawCandidate(button, option, label.Text, dangerous));
        }

        if (eventModel is null || player is null)
            return _bound is not null && _pending is not null
                ? Transient(_bound) : EventOrchestratorV1SurfaceCapture.Missing();
        if (_bound is null)
            _bound = new BoundEvent(run, player, room, map, overlays, layout, eventModel);
        else if (!_bound.MatchesLive(run, room, map, overlays) ||
                 !ReferenceEquals(_bound.Layout, layout) ||
                 !ReferenceEquals(_bound.Event, eventModel) ||
                 !ReferenceEquals(_bound.Player, player))
            return EventOrchestratorV1SurfaceCapture.Unsupported();

        EventCardOperationEventClass eventClass =
            EventCardOperationNativeRegistry.Classify(eventModel);
        if (eventClass == EventCardOperationEventClass.KnownUnsupported)
            return EventOrchestratorV1SurfaceCapture.Unsupported();
        if (!ValidSelectedOptionMap(eventClass, eventModel.IsFinished, raw))
            return EventOrchestratorV1SurfaceCapture.Unsupported();

        var candidates = new List<EventOrchestratorV1NativeCandidate>(raw.Count);
        var stamp = new StringBuilder();
        for (int index = 0; index < raw.Count; index++)
        {
            RawCandidate value = raw[index];
            CandidateBinding? binding = Find(value.Button, value.Option);
            if (binding is null)
            {
                EventOrchestratorV1ChildPolicy? policy = null;
                IEventOrchestratorV1ChildFactory? factory = null;
                EventCardOperationBinding? eventCardBinding = null;
                if (!value.Option.IsProceed)
                {
                    if (string.Equals(value.Option.TextKey, CheeseStableId, StringComparison.Ordinal))
                    {
                        if (eventModel.GetType() != typeof(RoomFullOfCheese))
                            return EventOrchestratorV1SurfaceCapture.Unsupported();
                        policy = EventOrchestratorV1ChildPolicy.CheeseGorgeAddTwo();
                        factory = _factoryBuilder.CreateCheese(
                            policy, _bound, (RoomFullOfCheese)eventModel, value.Option, value.Button);
                    }
                    else if (eventClass is EventCardOperationEventClass.SelectedAroma or
                            EventCardOperationEventClass.SelectedSapphire)
                    {
                        if (!EventCardOperationNativeRegistry.TryGetSelectedDefinition(
                                eventClass, value.Option.TextKey,
                                out EventOrchestratorV1CardPolicyDefinition? definition,
                                out bool knownUnsupported))
                            return EventOrchestratorV1SurfaceCapture.Unsupported();
                        if (!knownUnsupported && definition is not null &&
                            EventCardOperationBinding.TryPrepare(
                                definition, run, player, room, map, eventModel,
                                value.Option, value.Button,
                                out eventCardBinding) &&
                            eventCardBinding is not null)
                        {
                            policy = eventCardBinding.Policy;
                            factory = _factoryBuilder.CreateEventCard(
                                policy, _bound, eventCardBinding, value.Option, value.Button);
                        }
                    }
                    else
                    {
                        policy = EventOrchestratorV1ChildPolicy.ItemReward();
                        factory = _factoryBuilder.CreateItem(policy, _bound, value.Option, value.Button);
                    }
                }
                binding = new CandidateBinding(
                    this, value.Button, value.Option, policy, factory, eventCardBinding);
                _bindings.Add(binding);
            }
            if (!binding.Matches(value.Button, value.Option))
                return EventOrchestratorV1SurfaceCapture.Unsupported();
            if (_pending is null && binding.EventCardBinding is not null &&
                !binding.EventCardBinding.MatchesBeforeDispatch(
                    _bound.Run, _bound.Player, _bound.Room, _bound.Map, _bound.Event,
                    binding.Option, binding.Button))
                return EventOrchestratorV1SurfaceCapture.Unsupported();
            candidates.Add(binding.Project(index, value.Text, value.Dangerous));
            AppendStamp(stamp, binding, value.Dangerous);
        }
        string projection = stamp.ToString();
        if (_pending is not null && !string.Equals(_pendingProjection, projection, StringComparison.Ordinal))
        {
            _pending = null;
            _pendingProjection = null;
        }
        _currentProjection = projection;
        return EventOrchestratorV1SurfaceCapture.Parent(
            run, player, room, map, eventModel, eventModel.IsFinished,
            map.IsOpen, map.IsTravelEnabled, map.IsTraveling, candidates);
    }

    private EventOrchestratorV1SurfaceCapture CaptureChild(NOverlayStack overlays)
    {
        if (_bound is null || _pending is null || overlays.ScreenCount != 1 || !_bound.MatchesLive())
            return EventOrchestratorV1SurfaceCapture.Unsupported();
        object? top = overlays.Peek();
        bool expected = _pending.Policy?.PolicyKind switch
        {
            EventOrchestratorV1ChildPolicyKind.ItemReward =>
                top is NRewardsScreen reward && reward.GetType() == typeof(NRewardsScreen) && Valid(reward) && reward.IsVisibleInTree(),
            EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo =>
                top is NSimpleCardSelectScreen card && card.GetType() == typeof(NSimpleCardSelectScreen) && Valid(card) && card.IsVisibleInTree(),
            EventOrchestratorV1ChildPolicyKind.EventCardSelection =>
                top is NDeckUpgradeSelectScreen upgrade &&
                upgrade.GetType() == typeof(NDeckUpgradeSelectScreen) &&
                Valid(upgrade) && upgrade.IsVisibleInTree(),
            _ => false,
        };
        if (!expected || top is null || _pending.Factory is null || _pending.Policy is null)
            return EventOrchestratorV1SurfaceCapture.Unsupported();
        if (_pending.Policy.PolicyKind == EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo)
        {
            if (_expectedCheeseScreen is null) _expectedCheeseScreen = top;
            else if (!ReferenceEquals(_expectedCheeseScreen, top))
                return EventOrchestratorV1SurfaceCapture.Unsupported();
            if (!_cheeseReadyPublished)
            {
                if (_bound.Event is not RoomFullOfCheese cheese ||
                    top is not NSimpleCardSelectScreen card ||
                    !PinnedCardSelectionV1NativeAdapter.IsRoomFullOfCheeseReady(
                        _bound.Run, _bound.Player, _bound.Room, _bound.Map,
                        cheese, _pending.Option, _pending.Button, card))
                    return Transient(_bound);
                _cheeseReadyPublished = true;
            }
        }
        else if (_pending.Policy.PolicyKind == EventOrchestratorV1ChildPolicyKind.EventCardSelection)
        {
            if (_pending.EventCardBinding is null || top is not NDeckUpgradeSelectScreen screen)
                return EventOrchestratorV1SurfaceCapture.Unsupported();
            if (_expectedEventCardScreen is null) _expectedEventCardScreen = top;
            else if (!ReferenceEquals(_expectedEventCardScreen, top))
                return EventOrchestratorV1SurfaceCapture.Unsupported();
            if (!_eventCardReadyPublished)
            {
                if (!EventCardSelectionV1NativeAdapter.IsReady(
                        _pending.EventCardBinding, screen))
                    return Transient(_bound);
                _eventCardReadyPublished = true;
            }
        }
        return EventOrchestratorV1SurfaceCapture.Child(
            _bound.Run, _bound.Player, _bound.Room, _bound.Map, _bound.Event,
            top, _pending.Policy, _pending.Factory);
    }

    private void Dispatch(CandidateBinding binding)
    {
        if (_disposed || _bound is null || _pending is not null || !binding.MatchesLive() ||
            !ReferenceEquals(_bound.Event, binding.Button.Event) ||
            binding.EventCardBinding is not null &&
            !binding.EventCardBinding.MatchesBeforeDispatch(
                _bound.Run, _bound.Player, _bound.Room, _bound.Map, _bound.Event,
                binding.Option, binding.Button))
            throw new InvalidOperationException("Event dispatch binding changed.");
        _pending = binding;
        _pendingProjection = _currentProjection ??
            throw new InvalidOperationException("Event projection is unavailable.");
        binding.Button.ForceClick();
    }

    private CandidateBinding? Find(NEventOptionButton button, EventOption option)
    {
        foreach (CandidateBinding binding in _bindings)
            if (ReferenceEquals(binding.Button, button) || ReferenceEquals(binding.Option, option))
                return binding;
        return null;
    }

    private static void AppendStamp(StringBuilder target, CandidateBinding binding, bool dangerous)
    {
        target.Append(binding.Option.TextKey).Append('\u001f')
            .Append(binding.Button.IsVisibleInTree() ? '1' : '0')
            .Append(binding.Button.IsEnabled ? '1' : '0')
            .Append(binding.Option.IsLocked ? '1' : '0')
            .Append(dangerous ? '1' : '0')
            .Append(binding.Option.IsProceed ? '1' : '0')
            .Append(((int?)binding.Policy?.PolicyKind ?? 0).ToString(CultureInfo.InvariantCulture))
            .Append('\u001e');
    }

    private static EventOrchestratorV1SurfaceCapture Transient(BoundEvent bound) =>
        EventOrchestratorV1SurfaceCapture.Transient(
            bound.Run, bound.Player, bound.Room, bound.Map, bound.Event);

    internal static bool ExactAccepted(
        EventOrchestratorV1AcceptedContext accepted,
        BoundEvent bound,
        EventOption option,
        NEventOptionButton button,
        EventOrchestratorV1ChildPolicy policy,
        IEventOrchestratorV1ChildFactory factory) =>
        ReferenceEquals(accepted.RunIdentity, bound.Run) &&
        ReferenceEquals(accepted.PlayerIdentity, bound.Player) &&
        ReferenceEquals(accepted.RoomIdentity, bound.Room) &&
        ReferenceEquals(accepted.MapIdentity, bound.Map) &&
        ReferenceEquals(accepted.EventIdentity, bound.Event) &&
        ReferenceEquals(accepted.ButtonIdentity, button) &&
        ReferenceEquals(accepted.OptionIdentity, option) &&
        ReferenceEquals(accepted.ControllerIdentity, button) &&
        ReferenceEquals(accepted.ChildPolicy, policy) &&
        ReferenceEquals(accepted.ChildFactory, factory);

    internal static bool Foreground(
        BoundEvent bound,
        EventOrchestratorV1AcceptedContext accepted,
        object exactScreen,
        EventOption option,
        NEventOptionButton button,
        EventOrchestratorV1ChildPolicy policy,
        IEventOrchestratorV1ChildFactory factory)
    {
        if (!ExactAccepted(accepted, bound, option, button, policy, factory) || !bound.MatchesLive() ||
            !ReferenceEquals(button.Event, bound.Event) || !ReferenceEquals(button.Option, option) ||
            bound.Map.IsOpen || bound.Map.IsTravelEnabled || bound.Map.IsTraveling ||
            bound.Room.CustomEventNode is not null || bound.Room.EmbeddedCombatRoom is not null) return false;
        NOverlayStack overlays = bound.Overlays;
        if (overlays.ScreenCount == 0) return true;
        if (overlays.ScreenCount != 1 || !ReferenceEquals(overlays.Peek(), exactScreen)) return false;
        return policy.PolicyKind switch
        {
            EventOrchestratorV1ChildPolicyKind.ItemReward =>
                exactScreen is NRewardsScreen reward && reward.GetType() == typeof(NRewardsScreen) &&
                Valid(reward) && reward.IsVisibleInTree(),
            EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo =>
                exactScreen is NSimpleCardSelectScreen card && card.GetType() == typeof(NSimpleCardSelectScreen) &&
                Valid(card) && card.IsVisibleInTree(),
            EventOrchestratorV1ChildPolicyKind.EventCardSelection =>
                exactScreen is NDeckUpgradeSelectScreen upgrade &&
                upgrade.GetType() == typeof(NDeckUpgradeSelectScreen) &&
                Valid(upgrade) && upgrade.IsVisibleInTree(),
            _ => false,
        };
    }

    private static bool ValidSelectedOptionMap(
        EventCardOperationEventClass eventClass,
        bool eventFinished,
        IReadOnlyList<RawCandidate> raw)
    {
        if (eventClass is EventCardOperationEventClass.Ordinary) return true;
        if (eventClass is EventCardOperationEventClass.KnownUnsupported) return false;
        if (eventFinished)
            return raw.Count == 1 && raw[0].Option.IsProceed;
        if (raw.Count != 2) return false;
        bool supported = false;
        bool unsupported = false;
        foreach (RawCandidate candidate in raw)
        {
            if (candidate.Option.IsProceed ||
                !EventCardOperationNativeRegistry.TryGetSelectedDefinition(
                    eventClass, candidate.Option.TextKey, out var definition,
                    out bool knownUnsupported))
                return false;
            if (knownUnsupported)
            {
                if (unsupported) return false;
                unsupported = true;
            }
            else
            {
                if (supported || definition is null) return false;
                supported = true;
            }
        }
        return supported && unsupported;
    }

    private static bool Valid(GodotObject? value) => value is not null && GodotObject.IsInstanceValid(value);
    private static bool ValidExact<T>(T? value) where T : GodotObject =>
        Valid(value) && value!.GetType() == typeof(T);

    internal sealed class BoundEvent
    {
        internal BoundEvent(NRun run, Player player, NEventRoom room, NMapScreen map,
            NOverlayStack overlays, NEventLayout layout, EventModel eventModel) =>
            (Run, Player, Room, Map, Overlays, Layout, Event) =
            (run, player, room, map, overlays, layout, eventModel);
        internal NRun Run { get; }
        internal Player Player { get; }
        internal NEventRoom Room { get; }
        internal NMapScreen Map { get; }
        internal NOverlayStack Overlays { get; }
        internal NEventLayout Layout { get; }
        internal EventModel Event { get; }
        internal bool MatchesLive() => MatchesLive(NRun.Instance, Run.EventRoom, Run.GlobalUi?.MapScreen, Run.GlobalUi?.Overlays);
        internal bool MatchesLive(NRun? run, NEventRoom? room, NMapScreen? map, NOverlayStack? overlays) =>
            ReferenceEquals(run, Run) && ReferenceEquals(room, Room) && ReferenceEquals(map, Map) &&
            ReferenceEquals(overlays, Overlays) && ReferenceEquals(NEventRoom.Instance, Room) &&
            ReferenceEquals(NMapScreen.Instance, Map) && ReferenceEquals(Room.Layout, Layout) &&
            ValidExact<NRun>(Run) && ValidExact<NEventRoom>(Room) && ValidExact<NMapScreen>(Map) &&
            ValidExact<NOverlayStack>(Overlays) && ValidExact<NEventLayout>(Layout) &&
            Room.IsVisibleInTree() && ReferenceEquals(Event.Owner, Player);
        internal bool MatchesExitReferences() => ReferenceEquals(NRun.Instance, Run) &&
            ReferenceEquals(Run.EventRoom, Room) && ReferenceEquals(Run.GlobalUi?.MapScreen, Map) &&
            ReferenceEquals(Run.GlobalUi?.Overlays, Overlays) && ReferenceEquals(NEventRoom.Instance, Room) &&
            ReferenceEquals(NMapScreen.Instance, Map) && ValidExact<NRun>(Run) &&
            ValidExact<NEventRoom>(Room) && ValidExact<NMapScreen>(Map) &&
            ValidExact<NOverlayStack>(Overlays) && ReferenceEquals(Event.Owner, Player);
    }

    private sealed class CandidateBinding
    {
        private readonly PinnedEventOrchestratorV1NativeAdapter _owner;
        private readonly Action _dispatch;
        internal CandidateBinding(PinnedEventOrchestratorV1NativeAdapter owner,
            NEventOptionButton button, EventOption option,
            EventOrchestratorV1ChildPolicy? policy, IEventOrchestratorV1ChildFactory? factory,
            EventCardOperationBinding? eventCardBinding = null)
        {
            _owner = owner; Button = button; Option = option; Policy = policy; Factory = factory;
            EventCardBinding = eventCardBinding;
            _dispatch = Dispatch;
        }
        internal NEventOptionButton Button { get; }
        internal EventOption Option { get; }
        internal EventOrchestratorV1ChildPolicy? Policy { get; }
        internal IEventOrchestratorV1ChildFactory? Factory { get; }
        internal EventCardOperationBinding? EventCardBinding { get; }
        internal bool Matches(NEventOptionButton button, EventOption option) =>
            ReferenceEquals(Button, button) && ReferenceEquals(Option, option) && MatchesLive();
        internal bool MatchesLive() => ValidExact<NEventOptionButton>(Button) &&
            Option.GetType() == typeof(EventOption) && ReferenceEquals(Button.Option, Option);
        private void Dispatch() => _owner.Dispatch(this);
        internal EventOrchestratorV1NativeCandidate Project(int index, string text, bool dangerous) => new(
            index, Option.TextKey, text, Button.IsVisibleInTree(), Button.IsEnabled,
            Option.IsLocked, dangerous, Option.IsProceed, Button, Option, Button,
            _dispatch,
            Option.IsProceed ? EventOrchestratorV1CapabilityKind.Proceed :
            Policy?.ChildKind == EventOrchestratorV1ChildKind.CardSelection ?
                EventOrchestratorV1CapabilityKind.SupportedCardSelection :
            Policy is null ? EventOrchestratorV1CapabilityKind.UnsupportedCardSelection :
            EventOrchestratorV1CapabilityKind.OrdinaryItemEligible,
            Policy?.ChildKind == EventOrchestratorV1ChildKind.CardSelection ?
                Policy.ExpectedDomainCount : 0,
            Policy, Factory);
    }

    private sealed record RawCandidate(
        NEventOptionButton Button, EventOption Option, string Text, bool Dangerous);
}

internal interface IEventOrchestratorV1NativeChildFactoryBuilder
{
    IEventOrchestratorV1ChildFactory CreateItem(
        EventOrchestratorV1ChildPolicy policy,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
        EventOption option,
        NEventOptionButton button);
    IEventOrchestratorV1ChildFactory CreateCheese(
        EventOrchestratorV1ChildPolicy policy,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
        RoomFullOfCheese eventModel,
        EventOption option,
        NEventOptionButton button);
    IEventOrchestratorV1ChildFactory CreateEventCard(
        EventOrchestratorV1ChildPolicy policy,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
        EventCardOperationBinding binding,
        EventOption option,
        NEventOptionButton button);
}
