using System;
using System.Threading;
using Sts2AgentBridge.Successors.ItemBootstrapV1;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal static class CardSelectionBootstrapHost
{
    private static int _attempted;
    private static CardSelectionBootstrapLifecycle? _lifecycle;

    internal static void Initialize()
    {
        if (Interlocked.Exchange(ref _attempted, 1) != 0) return;
        CardSelectionBootstrapLifecycle? lifecycle = null;
        try
        {
            lifecycle = new CardSelectionBootstrapLifecycle(
                OpenEnabled, PinnedItemBuildGuard.Verify,
                new CardSelectionGodotFrameConnector(),
                new ProductionCardSelectionRuntimeFactory(),
                StopwatchCardSelectionBootstrapClock.Instance,
                SystemCardSelectionBootstrapTimerFactory.Instance);
            Volatile.Write(ref _lifecycle, lifecycle);
            AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
            lifecycle.Initialize();
        }
        catch
        {
            lifecycle?.RequestStop();
        }
    }

    private static ICardSelectionBootstrapOperatorLease? OpenEnabled()
    {
        ItemOperatorConfiguration? configuration = CardSelectionOperatorFiles.OpenEnabled();
        return configuration is null ? null : new OperatorLease(configuration);
    }

    private static void OnProcessExit(object? sender, EventArgs eventArgs) =>
        Volatile.Read(ref _lifecycle)?.RequestStop();

    private sealed class OperatorLease : ICardSelectionBootstrapOperatorLease
    {
        private readonly ItemOperatorConfiguration _configuration;

        internal OperatorLease(ItemOperatorConfiguration configuration) =>
            _configuration = configuration;

        public byte[]? ReadCredentialOnce() => _configuration.ReadCredentialOnce();
        public byte[]? TakeConfiguration() => _configuration.TakeConfiguration();
        public void Dispose() => _configuration.Dispose();
    }
}
