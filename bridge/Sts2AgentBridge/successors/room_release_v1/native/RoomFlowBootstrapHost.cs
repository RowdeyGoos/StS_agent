using System;
using System.Threading;
using Sts2AgentBridge.Successors.ItemBootstrapV1;

namespace Sts2AgentBridge.Successors.RoomReleaseV1;

internal static class RoomFlowBootstrapHost
{
    private static int _attempted;
    private static RoomFlowBootstrapLifecycle? _lifecycle;

    internal static void Initialize()
    {
        if (Interlocked.Exchange(ref _attempted, 1) != 0) return;
        RoomFlowBootstrapLifecycle? lifecycle = null;
        try
        {
            lifecycle = new RoomFlowBootstrapLifecycle(
                OpenEnabled, PinnedItemBuildGuard.Verify,
                new RoomFlowGodotFrameConnector(), new ProductionRoomFlowRuntimeFactory(),
                StopwatchRoomFlowBootstrapClock.Instance,
                SystemRoomFlowBootstrapTimerFactory.Instance);
            Volatile.Write(ref _lifecycle, lifecycle);
            AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
            lifecycle.Initialize();
        }
        catch { lifecycle?.RequestStop(); }
    }

    private static IRoomFlowBootstrapOperatorLease? OpenEnabled()
    {
        ItemOperatorConfiguration? configuration = RoomFlowOperatorFiles.OpenEnabled();
        return configuration is null ? null : new OperatorLease(configuration);
    }

    private static void OnProcessExit(object? sender, EventArgs eventArgs) =>
        Volatile.Read(ref _lifecycle)?.RequestStop();

    private sealed class OperatorLease : IRoomFlowBootstrapOperatorLease
    {
        private readonly ItemOperatorConfiguration _configuration;
        internal OperatorLease(ItemOperatorConfiguration configuration) => _configuration = configuration;
        public byte[]? ReadCredentialOnce() => _configuration.ReadCredentialOnce();
        public byte[]? TakeConfiguration() => _configuration.TakeConfiguration();
        public void Dispose() => _configuration.Dispose();
    }
}
