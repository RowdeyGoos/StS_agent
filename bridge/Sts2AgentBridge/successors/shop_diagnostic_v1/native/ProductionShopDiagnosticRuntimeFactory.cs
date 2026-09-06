using System;
using System.Security.Cryptography;
using Sts2AgentBridge.Successors.RoomReleaseV1;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

internal sealed class ProductionShopDiagnosticRuntimeFactory : IRoomFlowBootstrapRuntimeFactory
{
    public IRoomFlowBootstrapRuntime? Create(byte[] configuration, byte[] credential)
    {
        try
        {
            var owner = new Runtime();
            ShopDiagnosticTransportRuntime? runtime = ShopDiagnosticTransportRuntime.Create(
                configuration,
                () => credential,
                static () => new ShopDiagnosticService(new ShopDiagnosticNativeAdapter()));
            if (runtime is null) return null;
            owner.Set(runtime);
            return owner;
        }
        catch
        {
            return null;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(configuration);
            CryptographicOperations.ZeroMemory(credential);
        }
    }

    private sealed class Runtime : IRoomFlowBootstrapRuntime
    {
        private ShopDiagnosticTransportRuntime? _runtime;
        internal void Set(ShopDiagnosticTransportRuntime runtime) => _runtime = runtime;
        public bool Start() => Inner.Start();
        public bool DrainFrame() => Inner.DrainFrame();
        public bool StopTransportAndJoin() => Inner.StopTransportAndJoin();
        public bool TransportStopped => Inner.TransportStopped;
        public bool DisposeServiceOnOwnerFrame() => Inner.DisposeServiceOnOwnerFrame();
        public bool ServiceDisposed => Inner.ServiceDisposed;
        public bool IsTerminalOrStopping => Inner.IsTerminalOrStopping;
        private ShopDiagnosticTransportRuntime Inner =>
            _runtime ?? throw new InvalidOperationException();
    }
}
