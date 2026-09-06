namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

[MegaCrit.Sts2.Core.Modding.ModInitializer("Initialize")]
public static class ShopDiagnosticModEntry
{
    public static void Initialize() => ShopDiagnosticBootstrapHost.Initialize();
}
