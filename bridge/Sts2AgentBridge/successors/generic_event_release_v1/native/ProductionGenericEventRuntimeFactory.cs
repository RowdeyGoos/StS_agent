using System;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using Sts2AgentBridge.Successors.GenericEventV3;
using Sts2AgentBridge.Successors.GenericEventV3.Native;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV1;

internal sealed class ProductionGenericEventRuntimeFactory : IGenericEventBootstrapRuntimeFactory
{
    public IGenericEventBootstrapRuntime? Create(byte[] configuration, byte[] credential)
    {
        try
        {
            var owner = new Runtime();
            GenericEventTransportRuntime? runtime = GenericEventTransportRuntime.Create(
                configuration, () => credential, CreateService);
            if (runtime is null) return null;
            owner.Set(runtime);
            return owner;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(configuration);
            CryptographicOperations.ZeroMemory(credential);
        }
    }

    private static GenericEventV3WireService CreateService(GenericEventReleaseSelection selection, string nonce)
    {
        if (selection != GenericEventReleaseSelection.Generic || !PinnedGenericEventHarmonyGuard.Verify())
            throw new InvalidOperationException("Generic event native dependency unavailable.");
        return CreateVerifiedService(nonce);
    }

    // No native constructor is JIT-entered until the exact resolved dependency passed.
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static GenericEventV3WireService CreateVerifiedService(string nonce)
    {
        IGenericEventV3NativeAdapter? adapter = null;
        GenericEventV3Session? session = null;
        try
        {
            adapter = new PinnedGenericEventV3NativeAdapter();
            session = new GenericEventV3Session(adapter, nonce);
            adapter = null;
            var service = new GenericEventV3WireService(nonce, session);
            session = null;
            return service;
        }
        catch
        {
            // Failed constructors can retain an exclusive hook lease. Transfer
            // every possible owner to the runtime rather than dropping cleanup.
            throw new GenericEventTransportFactoryFailure(() =>
            {
                if (session is not null) { session.Dispose(); session = null; }
                else if (adapter is not null) { adapter.Dispose(); adapter = null; }
                else GenericEventV3Hooks.RecoverFailedInstallation();
            });
        }
    }

    private sealed class Runtime : IGenericEventBootstrapRuntime
    {
        private GenericEventTransportRuntime? _runtime;
        internal void Set(GenericEventTransportRuntime runtime) => _runtime = runtime ?? throw new ArgumentNullException(nameof(runtime));
        public bool Start() => Inner.Start();
        public bool DrainFrame() => Inner.DrainFrame();
        public bool StopTransportAndJoin() => Inner.StopTransportAndJoin();
        public bool TransportStopped => Inner.TransportStopped;
        public bool DisposeServiceOnOwnerFrame() => Inner.DisposeServiceOnOwnerFrame();
        public bool ServiceDisposed => Inner.ServiceDisposed;
        public bool IsTerminalOrStopping => Inner.IsTerminalOrStopping;
        private GenericEventTransportRuntime Inner => _runtime ?? throw new InvalidOperationException("Runtime was not initialized.");
    }
}
