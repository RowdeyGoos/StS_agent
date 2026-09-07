namespace Sts2AgentBridge.Successors.GenericEventReleaseV1;

[MegaCrit.Sts2.Core.Modding.ModInitializer("Initialize")]
public static class GenericEventModEntry
{
    public static void Initialize() => GenericEventBootstrapHost.Initialize();
}
