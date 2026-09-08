using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Native;

public sealed class PinnedCardSelectionV1NativeAdapter : ICardSelectionV1NativeAdapter
{
    internal static bool CheeseReady { get; set; }
    internal static bool SmithReady { get; set; }
    internal static int LastSmithExpectedCount { get; private set; }

    public static bool IsRoomFullOfCheeseReady(
        NRun run, Player player, NEventRoom room, NMapScreen map,
        RoomFullOfCheese eventModel, EventOption option,
        NEventOptionButton button, NSimpleCardSelectScreen screen) => CheeseReady;

    public static bool IsSmithReady(
        int expectedDomainCount, NRun run, Player player, NRestSiteRoom room,
        NMapScreen map, MegaCrit.Sts2.Core.Entities.RestSite.SmithRestSiteOption option,
        NRestSiteButton button, NDeckUpgradeSelectScreen screen)
    {
        LastSmithExpectedCount = expectedDomainCount;
        return SmithReady;
    }

    public static ICardSelectionV1NativeAdapter CreateRoomFullOfCheese(
        CardSelectionV1ParentContext context, NRun run, Player player,
        NEventRoom room, NMapScreen map, RoomFullOfCheese eventModel,
        EventOption option, NEventOptionButton button, NSimpleCardSelectScreen screen) =>
        new PinnedCardSelectionV1NativeAdapter();

    public static ICardSelectionV1NativeAdapter CreateSmith(
        CardSelectionV1ParentContext context, NRun run, Player player,
        NRestSiteRoom room, NMapScreen map,
        MegaCrit.Sts2.Core.Entities.RestSite.SmithRestSiteOption option,
        NRestSiteButton button, NDeckUpgradeSelectScreen screen) =>
        new PinnedCardSelectionV1NativeAdapter();

    public CardSelectionV1SurfaceCapture CaptureSurface() => throw new System.NotSupportedException();
    public void Dispose() { }
}
