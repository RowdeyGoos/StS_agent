using System;
using System.Security.Cryptography;

namespace Sts2AgentBridge.Unified;

internal sealed class ProductionBridgeRuntimeFactory : IBridgeBootstrapRuntimeFactory
{
    public IBridgeBootstrapRuntime? Create(byte[] configuration, byte[] credential)
    {
        try
        {
            var runtime = BridgeTransportRuntime.Create(configuration, () => credential,
                nonce => new BridgeRouter(CoreNativeFactory.Create(nonce), (capability, session) => new NativeBridgeModule(capability, session)));
            return runtime is null ? null : new Runtime(runtime);
        }
        finally { CryptographicOperations.ZeroMemory(configuration); CryptographicOperations.ZeroMemory(credential); }
    }
    private sealed class Runtime(BridgeTransportRuntime inner) : IBridgeBootstrapRuntime
    {
        public bool Start() => inner.Start();
        public bool DrainFrame() => inner.DrainFrame();
        public bool StopTransportAndJoin() => inner.StopTransportAndJoin();
        public bool TransportStopped => inner.TransportStopped;
        public bool DisposeServiceOnOwnerFrame() => inner.DisposeServiceOnOwnerFrame();
        public bool ServiceDisposed => inner.ServiceDisposed;
        public bool IsTerminalOrStopping => inner.IsTerminalOrStopping;
    }
}
