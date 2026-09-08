namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

[MegaCrit.Sts2.Core.Modding.ModInitializer("Initialize")]
public static class ModEntry
{
    public static void Initialize()
    {
        ItemBootstrapHost.Initialize();
    }
}
