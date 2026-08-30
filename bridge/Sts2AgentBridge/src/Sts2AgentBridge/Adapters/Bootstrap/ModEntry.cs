namespace Sts2AgentBridge.Adapters.Bootstrap;

[MegaCrit.Sts2.Core.Modding.ModInitializer("Initialize")]
public static class ModEntry
{
    public static void Initialize()
    {
        BridgeBootstrap.Initialize();
    }
}
