namespace Sts2AgentBridge.Unified;

[MegaCrit.Sts2.Core.Modding.ModInitializer("Initialize")]
public static class BridgeModEntry
{
    public static void Initialize() => BridgeBootstrapHost.Initialize();
}
