using System;
using System.Threading;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal static class ItemBootstrapHost
{
    private static int _attempted;
    private static ItemBootstrapLifecycle? _lifecycle;

    internal static void Initialize()
    {
        if (Interlocked.Exchange(ref _attempted, 1) != 0)
        {
            return;
        }

        ItemBootstrapLifecycle? lifecycle = null;
        try
        {
            lifecycle = new ItemBootstrapLifecycle(
                OpenEnabled,
                PinnedItemBuildGuard.Verify,
                new GodotItemFrameConnector(),
                new ProductionItemRuntimeFactory(),
                StopwatchItemBootstrapClock.Instance,
                SystemItemBootstrapTimerFactory.Instance);
            Volatile.Write(ref _lifecycle, lifecycle);
            AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
            lifecycle.Initialize();
        }
        catch
        {
            lifecycle?.RequestStop();
        }
    }

    private static IItemBootstrapOperatorLease? OpenEnabled()
    {
        ItemOperatorConfiguration? configuration = ItemOperatorFiles.OpenEnabled();
        return configuration is null ? null : new OperatorLease(configuration);
    }

    private static void OnProcessExit(object? sender, EventArgs eventArgs)
    {
        Volatile.Read(ref _lifecycle)?.RequestStop();
    }

    private sealed class OperatorLease : IItemBootstrapOperatorLease
    {
        private readonly ItemOperatorConfiguration _configuration;

        internal OperatorLease(ItemOperatorConfiguration configuration)
        {
            _configuration = configuration;
        }

        public byte[]? ReadCredentialOnce() => _configuration.ReadCredentialOnce();

        public byte[]? TakeConfiguration() => _configuration.TakeConfiguration();

        public void Dispose() => _configuration.Dispose();
    }
}
