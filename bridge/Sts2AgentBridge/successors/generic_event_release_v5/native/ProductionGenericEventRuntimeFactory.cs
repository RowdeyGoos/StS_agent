using System;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using Sts2AgentBridge.Successors.GenericEventV3;
using Sts2AgentBridge.Successors.GenericEventV3.Native;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV5;

internal sealed class ProductionGenericEventRuntimeFactory : IGenericEventBootstrapRuntimeFactory
{
    public IGenericEventBootstrapRuntime? Create(byte[] configuration, byte[] credential)
    {
        try
        {
            var owner = new Runtime();
            GenericEventTransportRuntime? runtime = GenericEventTransportRuntime.Create(
                configuration, () => credential,
                (selection, nonce) => CreateService(selection, nonce, owner), owner.ReadDiagnostic);
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

    private static GenericEventV3WireService CreateService(GenericEventReleaseSelection selection, string nonce, Runtime owner)
    {
        if (selection != GenericEventReleaseSelection.Generic || !PinnedGenericEventHarmonyGuard.Verify())
            throw new InvalidOperationException("Generic event native dependency unavailable.");
        return CreateVerifiedService(nonce, owner);
    }

    // No native constructor is JIT-entered until the exact resolved dependency passed.
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static GenericEventV3WireService CreateVerifiedService(string nonce, Runtime owner)
    {
        IGenericEventV3NativeAdapter? adapter = null;
        GenericEventV3Session? session = null;
        try
        {
            var pinned = new PinnedGenericEventV3NativeAdapter();
            adapter = pinned;
            owner.BindDiagnostic(pinned);
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
        private PinnedGenericEventV3NativeAdapter? _diagnosticTarget;
        private bool _diagnosticBound;
        internal void BindDiagnostic(PinnedGenericEventV3NativeAdapter target)
        {
            if (_diagnosticBound) throw new InvalidOperationException("Diagnostic target already bound.");
            _diagnosticTarget=target ?? throw new ArgumentNullException(nameof(target));
            _diagnosticBound=true;
        }
        internal GenericEventDiagnosticCode ReadDiagnostic() =>
            _diagnosticTarget?.LastDiagnostic ?? GenericEventDiagnosticCode.NotCaptured;
        internal void Set(GenericEventTransportRuntime runtime) => _runtime = runtime ?? throw new ArgumentNullException(nameof(runtime));
        public bool Start() => Inner.Start();
        public bool DrainFrame() => Inner.DrainFrame();
        public bool StopTransportAndJoin() => Inner.StopTransportAndJoin();
        public bool TransportStopped => Inner.TransportStopped;
        public bool DisposeServiceOnOwnerFrame()
        {
            bool disposed=Inner.DisposeServiceOnOwnerFrame();
            if(disposed && Inner.ServiceDisposed) _diagnosticTarget=null;
            return disposed;
        }
        public bool ServiceDisposed => Inner.ServiceDisposed;
        public bool IsTerminalOrStopping => Inner.IsTerminalOrStopping;
        private GenericEventTransportRuntime Inner => _runtime ?? throw new InvalidOperationException("Runtime was not initialized.");
    }
}
