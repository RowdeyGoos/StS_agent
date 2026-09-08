using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;
namespace Sts2AgentBridge.Unified;
internal static class CoreNativeFactory
{
    internal static CoreBridgeModule Create(string nonce)
    {
        var combat = new PinnedPublicCombatDecisionReader();
        var reward = new PinnedPublicRewardDecisionReader();
        var map = new PinnedPublicMapDecisionReader();
        var room = new PinnedPublicRoomDecisionReader();
        return new CoreBridgeModule(nonce, new PublicScreenService(new PinnedPublicScreenReader()),
            new PublicCombatDecisionService(combat), new PublicCombatActionService(new PinnedPublicCombatActionApplier(combat)),
            new PublicRewardDecisionService(reward), new PublicRewardActionService(new PinnedPublicRewardActionApplier(reward)),
            new PublicMapDecisionService(map), new PublicMapActionService(new PinnedPublicMapActionApplier(map)),
            new PublicRoomDecisionService(room), new PublicRoomActionService(new PinnedPublicRoomActionApplier(room)));
    }
}
