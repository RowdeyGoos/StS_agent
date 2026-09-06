using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;

using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Native;

public sealed class PinnedCardSelectionV1NativeAdapter : ICardSelectionV1NativeAdapter
{
    internal static bool Ready { get; set; }
    internal static CardSelectionV1ParentContext? LastContext { get; private set; }
    internal static object? LastScreen { get; private set; }
    public static bool IsRoomFullOfCheeseReady(
        NRun run, Player player, NEventRoom room, NMapScreen map,
        RoomFullOfCheese eventModel, EventOption option,
        NEventOptionButton button, NSimpleCardSelectScreen screen) => Ready;

    public static PinnedCardSelectionV1NativeAdapter CreateRoomFullOfCheese(
        CardSelectionV1ParentContext context,
        NRun run, Player player, NEventRoom room, NMapScreen map,
        RoomFullOfCheese eventModel, EventOption option,
        NEventOptionButton button, NSimpleCardSelectScreen screen)
    {
        LastContext = context;
        LastScreen = screen;
        return new PinnedCardSelectionV1NativeAdapter();
    }

    public CardSelectionV1SurfaceCapture CaptureSurface() => throw new System.InvalidOperationException();
    public void Dispose() { }
}
