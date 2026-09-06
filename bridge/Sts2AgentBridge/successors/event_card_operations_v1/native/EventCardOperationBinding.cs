using System;
using System.Collections.Generic;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Native;

internal sealed class EventCardOperationBinding
{
    private const string AromaPolicy = "aroma_maintain_control_upgrade_one";
    private const string AromaKey = "AROMA_OF_CHAOS.pages.INITIAL.options.MAINTAIN_CONTROL";
    private const string SapphirePolicy = "sapphire_eat_upgrade_one";
    private const string SapphireKey = "SAPPHIRE_SEED.pages.INITIAL.options.EAT";

    private readonly CardSelectionV1DeckCard[] _deck;
    private readonly CardModel[] _eligible;
    private readonly IReadOnlyList<CardSelectionV1DeckCard> _deckView;
    private readonly IReadOnlyList<CardModel> _eligibleView;

    private EventCardOperationBinding(
        EventOrchestratorV1CardPolicyDefinition definition,
        EventOrchestratorV1ChildPolicy policy,
        NRun run,
        Player player,
        NEventRoom room,
        NMapScreen map,
        NOverlayStack overlays,
        EventModel eventModel,
        EventOption option,
        NEventOptionButton controller,
        CardSelectionV1DeckCard[] deck,
        CardModel[] eligible)
    {
        Definition = definition;
        Policy = policy;
        Run = run;
        Player = player;
        Room = room;
        Map = map;
        Overlays = overlays;
        EventModel = eventModel;
        Option = option;
        Controller = controller;
        _deck = deck;
        _eligible = eligible;
        _deckView = Array.AsReadOnly(deck);
        _eligibleView = Array.AsReadOnly(eligible);
    }

    internal EventOrchestratorV1CardPolicyDefinition Definition { get; }
    internal EventOrchestratorV1ChildPolicy Policy { get; }
    internal NRun Run { get; }
    internal Player Player { get; }
    internal NEventRoom Room { get; }
    internal NMapScreen Map { get; }
    internal NOverlayStack Overlays { get; }
    internal EventModel EventModel { get; }
    internal EventOption Option { get; }
    internal NEventOptionButton Controller { get; }
    internal int DomainCount => _eligible.Length;
    internal IReadOnlyList<CardSelectionV1DeckCard> PreDispatchDeck => _deckView;
    internal IReadOnlyList<CardModel> EligibleOriginals => _eligibleView;

    internal static bool TryPrepare(
        EventOrchestratorV1CardPolicyDefinition definition,
        NRun run,
        Player player,
        NEventRoom room,
        NMapScreen map,
        EventModel eventModel,
        EventOption option,
        NEventOptionButton controller,
        out EventCardOperationBinding? binding)
    {
        binding = null;
        try
        {
            if (definition is null || run is null || player is null || room is null ||
                map is null || eventModel is null || option is null || controller is null ||
                !EventOrchestratorV1CardPolicyCatalog.TryGet(definition.PolicyId,
                    out EventOrchestratorV1CardPolicyDefinition? accepted) ||
                !ReferenceEquals(definition, accepted) || !ExactPolicy(definition) ||
                !MatchesRow(definition, eventModel, option) ||
                !ValidExact(run) || !ValidExact(room) || !ValidExact(map) ||
                !ValidExact(controller) || !ValidEvent(eventModel) ||
                option.GetType() != typeof(EventOption) ||
                !ReferenceEquals(NRun.Instance, run) ||
                !ReferenceEquals(run.EventRoom, room) ||
                !ReferenceEquals(NEventRoom.Instance, room) ||
                !ReferenceEquals(run.GlobalUi?.MapScreen, map) ||
                !ReferenceEquals(NMapScreen.Instance, map) ||
                run.GlobalUi?.Overlays is not NOverlayStack overlays || !ValidExact(overlays) ||
                overlays.ScreenCount != 0 || !room.IsVisibleInTree() ||
                map.IsOpen || map.IsTravelEnabled || map.IsTraveling ||
                room.CustomEventNode is not null || room.EmbeddedCombatRoom is not null ||
                !ReferenceEquals(eventModel.Owner, player) || eventModel.IsFinished ||
                !ReferenceEquals(controller.Event, eventModel) ||
                !ReferenceEquals(controller.Option, option) ||
                CardSelectCmd.Selector is not null ||
                !TryCopyDeck(player, out CardSelectionV1DeckCard[] deck,
                    out CardModel[] eligible) ||
                eligible.Length < definition.MinimumDomainCount ||
                eligible.Length > definition.MaximumDomainCount)
                return false;

            EventOrchestratorV1ChildPolicy policy = definition.Bind(eligible.Length);
            binding = new EventCardOperationBinding(
                definition, policy, run, player, room, map, overlays,
                eventModel, option, controller, deck, eligible);
            return true;
        }
        catch
        {
            binding = null;
            return false;
        }
    }

    internal bool MatchesBeforeDispatch(
        NRun run,
        Player player,
        NEventRoom room,
        NMapScreen map,
        EventModel eventModel,
        EventOption option,
        NEventOptionButton controller)
    {
        try
        {
            return ReferenceEquals(run, Run) && ReferenceEquals(player, Player) &&
                ReferenceEquals(room, Room) && ReferenceEquals(map, Map) &&
                ReferenceEquals(eventModel, EventModel) && ReferenceEquals(option, Option) &&
                ReferenceEquals(controller, Controller) &&
                ReferenceEquals(NRun.Instance, Run) && ReferenceEquals(Run.EventRoom, Room) &&
                ReferenceEquals(NEventRoom.Instance, Room) &&
                ReferenceEquals(Run.GlobalUi?.MapScreen, Map) &&
                ReferenceEquals(Run.GlobalUi?.Overlays, Overlays) &&
                ReferenceEquals(NMapScreen.Instance, Map) &&
                ValidExact(Run) && ValidExact(Room) && ValidExact(Map) &&
                ValidExact(Overlays) && ValidExact(Controller) && ValidEvent(EventModel) &&
                Room.IsVisibleInTree() && Overlays.ScreenCount == 0 &&
                !Map.IsOpen && !Map.IsTravelEnabled && !Map.IsTraveling &&
                Room.CustomEventNode is null && Room.EmbeddedCombatRoom is null &&
                ReferenceEquals(EventModel.Owner, Player) && !EventModel.IsFinished &&
                ReferenceEquals(Controller.Event, EventModel) &&
                ReferenceEquals(Controller.Option, Option) &&
                MatchesRow(Definition, EventModel, Option) && CardSelectCmd.Selector is null &&
                TryCopyDeck(Player, out CardSelectionV1DeckCard[] deck,
                    out CardModel[] eligible) && SameDeck(_deck, deck) &&
                SameReferences(_eligible, eligible);
        }
        catch
        {
            return false;
        }
    }

    internal bool MatchesAcceptedParent(CardSelectionV1ParentContext context) =>
        context is not null && context.ParentKind == CardSelectionV1ParentKind.Event &&
        context.ParentReceiptIdentity is not null &&
        ReferenceEquals(context.RunIdentity, Run) &&
        ReferenceEquals(context.PlayerIdentity, Player) &&
        ReferenceEquals(context.RoomIdentity, Room) &&
        ReferenceEquals(context.MapIdentity, Map) &&
        ReferenceEquals(context.ParentOptionIdentity, Option) &&
        ReferenceEquals(context.ParentControllerIdentity, Controller) &&
        context.Operation == Definition.Operation && context.MinSelect == Definition.MinSelect &&
        context.MaxSelect == Definition.MaxSelect &&
        context.CommitMode == Definition.CommitMode &&
        context.ExpectedDomainCount == DomainCount;

    internal bool MatchesChildBinding()
    {
        try
        {
            return EventOrchestratorV1CardPolicyCatalog.TryGet(
                    Definition.PolicyId,
                    out EventOrchestratorV1CardPolicyDefinition? accepted) &&
                ReferenceEquals(Definition, accepted) && ExactPolicy(Definition) &&
                ValidEvent(EventModel) && Option.GetType() == typeof(EventOption) &&
                ValidExact(Controller) && MatchesRow(Definition, EventModel, Option) &&
                ReferenceEquals(EventModel.Owner, Player) &&
                ReferenceEquals(Controller.Event, EventModel) &&
                ReferenceEquals(Controller.Option, Option);
        }
        catch { return false; }
    }

    internal bool MatchesCurrentDeck() =>
        TryCopyDeck(Player, out CardSelectionV1DeckCard[] deck, out CardModel[] eligible) &&
        SameDeck(_deck, deck) && SameReferences(_eligible, eligible);

    private static bool ExactPolicy(EventOrchestratorV1CardPolicyDefinition definition) =>
        definition.PolicyKind == EventOrchestratorV1ChildPolicyKind.EventCardSelection &&
        definition.Operation == CardSelectionV1Operation.Upgrade &&
        definition.MinSelect == 1 && definition.MaxSelect == 1 &&
        definition.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
        definition.DomainSource == EventOrchestratorV1CardDomainSource.ExistingDeckOriginals &&
        definition.MinimumDomainCount == 2 && definition.MaximumDomainCount == 64;

    private static bool MatchesRow(
        EventOrchestratorV1CardPolicyDefinition definition,
        EventModel eventModel,
        EventOption option) =>
        definition.PolicyId switch
        {
            AromaPolicy => eventModel.GetType() == typeof(AromaOfChaos) &&
                string.Equals(definition.ParentStableId, AromaKey, StringComparison.Ordinal) &&
                string.Equals(option.TextKey, AromaKey, StringComparison.Ordinal),
            SapphirePolicy => eventModel.GetType() == typeof(SapphireSeed) &&
                string.Equals(definition.ParentStableId, SapphireKey, StringComparison.Ordinal) &&
                string.Equals(option.TextKey, SapphireKey, StringComparison.Ordinal),
            _ => false,
        };

    private static bool TryCopyDeck(
        Player player,
        out CardSelectionV1DeckCard[] deck,
        out CardModel[] eligible)
    {
        var copied = new List<CardSelectionV1DeckCard>();
        var upgradable = new List<CardModel>();
        var seen = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (CardModel? card in player.Deck.Cards)
        {
            if (card is null || copied.Count >= CardSelectionV1Limits.MaximumDeckCards ||
                !seen.Add(card) || !CardSelectionV1NativeRules.IsStableKey(card.Id.Entry) ||
                card.CurrentUpgradeLevel < 0)
            {
                deck = Array.Empty<CardSelectionV1DeckCard>();
                eligible = Array.Empty<CardModel>();
                return false;
            }
            copied.Add(new CardSelectionV1DeckCard(card, card.Id.Entry,
                card.CurrentUpgradeLevel));
            if (card.IsUpgradable) upgradable.Add(card);
        }
        deck = copied.ToArray();
        eligible = upgradable.ToArray();
        return true;
    }

    private static bool SameDeck(
        IReadOnlyList<CardSelectionV1DeckCard> expected,
        IReadOnlyList<CardSelectionV1DeckCard> current)
    {
        if (expected.Count != current.Count) return false;
        for (int index = 0; index < expected.Count; index++)
        {
            CardSelectionV1DeckCard left = expected[index];
            CardSelectionV1DeckCard right = current[index];
            if (!ReferenceEquals(left.ModelIdentity, right.ModelIdentity) ||
                !string.Equals(left.StableKey, right.StableKey, StringComparison.Ordinal) ||
                left.UpgradeLevel != right.UpgradeLevel)
                return false;
        }
        return true;
    }

    private static bool SameReferences(
        IReadOnlyList<CardModel> expected,
        IReadOnlyList<CardModel> current)
    {
        if (expected.Count != current.Count) return false;
        for (int index = 0; index < expected.Count; index++)
            if (!ReferenceEquals(expected[index], current[index])) return false;
        return true;
    }

    private static bool ValidEvent(EventModel value) =>
        value.GetType() is Type type &&
        (type == typeof(AromaOfChaos) || type == typeof(SapphireSeed));

    private static bool ValidExact<T>(T value) where T : Godot.GodotObject =>
        value.GetType() == typeof(T) && Godot.GodotObject.IsInstanceValid(value);
}
