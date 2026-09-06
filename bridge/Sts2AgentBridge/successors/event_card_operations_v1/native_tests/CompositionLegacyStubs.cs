using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Native
{
    public sealed class PinnedCardSelectionV1NativeAdapter : ICardSelectionV1NativeAdapter
    {
        public static bool IsRoomFullOfCheeseReady(
            NRun run, Player player, NEventRoom room, NMapScreen map,
            RoomFullOfCheese eventModel, EventOption option,
            NEventOptionButton button, NSimpleCardSelectScreen screen) => false;
        public static PinnedCardSelectionV1NativeAdapter CreateRoomFullOfCheese(
            CardSelectionV1ParentContext context,
            NRun run, Player player, NEventRoom room, NMapScreen map,
            RoomFullOfCheese eventModel, EventOption option,
            NEventOptionButton button, NSimpleCardSelectScreen screen) => new();
        public CardSelectionV1SurfaceCapture CaptureSurface() =>
            throw new System.NotSupportedException();
        public void Dispose() { }
    }
}

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Native
{
    internal sealed class BoundEventItemV1NativeAdapter : IItemV1NativeAdapter
    {
        internal BoundEventItemV1NativeAdapter(
            NRun run, Player player, NEventRoom room, NMapScreen map,
            NRewardsScreen screen) { }
        public ItemV1SurfaceCapture CaptureSurface() =>
            throw new System.NotSupportedException();
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) =>
            throw new System.NotSupportedException();
    }
}
