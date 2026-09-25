using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Cards.Combat;
namespace Sts2AgentBridge.Unified;
internal static class CoreNativeFactory
{
    internal static BridgeRouter Create(string nonce)
    {
        var combat = new PinnedPublicCombatDecisionReader();
        var reward = new PinnedPublicRewardDecisionReader(64);
        var map = new PinnedPublicMapDecisionReader();
        var room = new PinnedPublicRoomDecisionReader();
        var choice = new CombatCardChoiceService(PinnedCombatCardChoiceAdapter.TryCreate, nonce);
        var core = new CoreBridgeModule(nonce, new PublicScreenService(new PinnedPublicScreenReader()),
            new PublicCombatDecisionService(combat), new PublicCombatActionService(new PinnedPublicCombatActionApplier(combat, 8192)),
            new PublicRewardDecisionService(reward), new PublicRewardActionService(new PinnedPublicRewardActionApplier(reward,CampaignRewardTransition.Legacy)),
            new PublicMapDecisionService(map), new PublicMapActionService(new PinnedPublicMapActionApplier(map, 80)),
            new PublicRoomDecisionService(room), new PublicRoomActionService(new PinnedPublicRoomActionApplier(room, 160)),
            choice, combat.BeginObservedCombat, () => { try { reward.Dispose(); } finally { combat.Dispose(); } });
        core.BindPotions(new CombatPotions(combat));
        core.BindAgent(new AgentPublicReader(reward, choice));
        core.BindCampaign(new CampaignNavigation(),new PublicRewardActionService(new PinnedPublicRewardActionApplier(reward,screen=>new CampaignRewardTransition(screen))));
        var router = new BridgeRouter(core, (capability, session) => new NativeBridgeModule(capability, session));
        router.BindFullAgent(new FullAgentSession(new FullNativeBackend(router, reward, choice), nonce));
        return router;
    }
}
