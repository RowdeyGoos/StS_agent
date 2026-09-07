using System;
using System.Threading;
using Sts2AgentBridge.Successors.ItemBootstrapV1;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV4;

internal static class GenericEventBootstrapHost
{
    private static int _attempted;
    private static GenericEventBootstrapLifecycle? _lifecycle;

    internal static void Initialize()
    {
        if (Interlocked.Exchange(ref _attempted, 1) != 0) return;
        GenericEventBootstrapLifecycle? lifecycle = null;
        try
        {
            lifecycle = new GenericEventBootstrapLifecycle(
                OpenEnabled, PinnedItemBuildGuard.Verify,
                new GenericEventGodotFrameConnector(),
                new ProductionGenericEventRuntimeFactory(),
                StopwatchGenericEventBootstrapClock.Instance,
                SystemGenericEventBootstrapTimerFactory.Instance);
            Volatile.Write(ref _lifecycle, lifecycle);
            AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
            lifecycle.Initialize();
        }
        catch
        {
            lifecycle?.RequestStop();
        }
    }

    private static IGenericEventBootstrapOperatorLease? OpenEnabled()
    {
        ItemOperatorConfiguration? configuration = GenericEventOperatorFiles.OpenEnabled();
        return configuration is null ? null : new OperatorLease(configuration);
    }

    private static void OnProcessExit(object? sender, EventArgs eventArgs) =>
        Volatile.Read(ref _lifecycle)?.RequestStop();

    private sealed class OperatorLease : IGenericEventBootstrapOperatorLease
    {
        private readonly ItemOperatorConfiguration _configuration;

        internal OperatorLease(ItemOperatorConfiguration configuration) =>
            _configuration = configuration;

        public byte[]? ReadCredentialOnce() => _configuration.ReadCredentialOnce();
        public byte[]? TakeConfiguration() => _configuration.TakeConfiguration();
        public void Dispose() => _configuration.Dispose();
    }
}
