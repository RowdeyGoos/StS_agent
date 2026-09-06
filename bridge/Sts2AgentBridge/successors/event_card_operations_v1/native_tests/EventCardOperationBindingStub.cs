using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Native;

internal sealed class EventCardOperationBinding
{
    internal static bool Allow { get; set; } = true;
    internal static int PreparedCount { get; private set; }
    internal EventOrchestratorV1ChildPolicy Policy { get; private init; } = null!;
    internal NRun Run { get; private init; } = null!;
    internal Player Player { get; private init; } = null!;
    internal NEventRoom Room { get; private init; } = null!;
    internal NMapScreen Map { get; private init; } = null!;
    internal EventModel EventModel { get; private init; } = null!;
    internal EventOption Option { get; private init; } = null!;
    internal NEventOptionButton Controller { get; private init; } = null!;
    internal int DomainCount => Policy.ExpectedDomainCount;

    internal static void Reset() { Allow = true; PreparedCount = 0; }

    internal static bool TryPrepare(
        EventOrchestratorV1CardPolicyDefinition definition,
        NRun run, Player player, NEventRoom room, NMapScreen map,
        EventModel eventModel, EventOption option, NEventOptionButton controller,
        out EventCardOperationBinding? binding)
    {
        PreparedCount++;
        binding = Allow ? new EventCardOperationBinding
        {
            Policy = definition.Bind(2), Run = run, Player = player,
            Room = room, Map = map, EventModel = eventModel,
            Option = option, Controller = controller,
        } : null;
        return binding is not null;
    }

    internal bool MatchesBeforeDispatch(
        NRun run, Player player, NEventRoom room, NMapScreen map,
        EventModel eventModel, EventOption option, NEventOptionButton controller) => Allow;

    internal bool MatchesChildBinding() => Allow;
}

public sealed class EventCardSelectionV1NativeAdapter :
    Sts2AgentBridge.Successors.CardSelectionV1.ICardSelectionV1NativeAdapter
{
    internal static bool Ready { get; set; }
    internal static CardSelectionV1ParentContext? LastContext { get; private set; }
    internal static EventCardOperationBinding? LastBinding { get; private set; }
    internal static object? LastScreen { get; private set; }
    internal EventCardSelectionV1NativeAdapter(
        EventCardOperationBinding binding,
        CardSelectionV1ParentContext context,
        NDeckUpgradeSelectScreen screen)
    {
        LastBinding = binding; LastContext = context; LastScreen = screen;
    }
    internal static bool IsReady(
        EventCardOperationBinding binding, NDeckUpgradeSelectScreen screen) => Ready;
    public CardSelectionV1SurfaceCapture CaptureSurface() =>
        throw new System.NotSupportedException();
    public void Dispose() { }
}
