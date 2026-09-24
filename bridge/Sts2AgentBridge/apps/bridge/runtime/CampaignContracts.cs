using System;
namespace Sts2AgentBridge.Unified;

internal interface ICampaignNavigation : IDisposable
{
    bool Active {get;}
    ModuleReply Handle(BridgeRequest request);
}
internal static class CampaignRoutes
{
    internal const string Decision="/probe/campaign-v2/public/decision", Action="/probe/campaign-v2/public/action";
    internal const string RewardDecision="/probe/reward-v2/public/decision", RewardAction="/probe/reward-v2/public/action";
}
