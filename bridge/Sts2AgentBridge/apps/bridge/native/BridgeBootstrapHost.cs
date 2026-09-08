using System;
using System.Threading;
using Sts2AgentBridge.Successors.ItemBootstrapV1;

namespace Sts2AgentBridge.Unified;

internal static class BridgeBootstrapHost
{
    private static int _attempted;
    private static BridgeBootstrapLifecycle? _lifecycle;

    internal static void Initialize()
    {
        if (Interlocked.Exchange(ref _attempted, 1) != 0) return;
        BridgeBootstrapLifecycle? lifecycle = null;
        try
        {
            lifecycle = new BridgeBootstrapLifecycle(
                OpenEnabled, PinnedItemBuildGuard.Verify,
                new BridgeGodotFrameConnector(),
                new ProductionBridgeRuntimeFactory(),
                StopwatchBridgeBootstrapClock.Instance,
                SystemBridgeBootstrapTimerFactory.Instance);
            Volatile.Write(ref _lifecycle, lifecycle);
            AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
            lifecycle.Initialize();
        }
        catch
        {
            lifecycle?.RequestStop();
        }
    }

    private static IBridgeBootstrapOperatorLease? OpenEnabled()
    {
        ItemOperatorConfiguration? configuration = BridgeOperatorFiles.OpenEnabled();
        return configuration is null ? null : new OperatorLease(configuration);
    }

    private static void OnProcessExit(object? sender, EventArgs eventArgs) =>
        Volatile.Read(ref _lifecycle)?.RequestStop();

    private sealed class OperatorLease : IBridgeBootstrapOperatorLease
    {
        private readonly ItemOperatorConfiguration _configuration;

        internal OperatorLease(ItemOperatorConfiguration configuration) =>
            _configuration = configuration;

        public byte[]? ReadCredentialOnce() => _configuration.ReadCredentialOnce();
        public byte[]? TakeConfiguration() => _configuration.TakeConfiguration();
        public void Dispose() => _configuration.Dispose();
    }
}
