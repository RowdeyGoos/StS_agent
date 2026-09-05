namespace Sts2AgentBridge.Successors.RoomReleaseV1;

[MegaCrit.Sts2.Core.Modding.ModInitializer("Initialize")]
public static class RoomFlowModEntry
{
    public static void Initialize() => RoomFlowBootstrapHost.Initialize();
}
