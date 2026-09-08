namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

[MegaCrit.Sts2.Core.Modding.ModInitializer("Initialize")]
public static class CardSelectionModEntry
{
    public static void Initialize() => CardSelectionBootstrapHost.Initialize();
}
