using System;
using System.Security.Cryptography;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event.Native;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

namespace Sts2AgentBridge.Successors.RoomReleaseV1;

internal sealed class ProductionRoomFlowRuntimeFactory : IRoomFlowBootstrapRuntimeFactory
{
    public IRoomFlowBootstrapRuntime? Create(byte[] configuration, byte[] credential)
    {
        try
        {
            var owner = new Runtime();
            RoomFlowTransportRuntime? runtime = RoomFlowTransportRuntime.Create(
                configuration, () => credential, CreateService);
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
            // Create has synchronously parsed/copied everything it retains.
            // This also covers an invalid configuration that never calls the
            // credential reader.
            CryptographicOperations.ZeroMemory(configuration);
            CryptographicOperations.ZeroMemory(credential);
        }
    }

    private static RoomFlowWireService CreateService(RoomFlowSelection selection, string nonce)
    {
        if (selection == RoomFlowSelection.Shop)
        {
            var session = new ShopV1Session(nonce, new PinnedShopV1NativeAdapter());
            try { return new RoomFlowWireService(nonce, session); }
            catch { session.Dispose(); throw; }
        }
        if (selection == RoomFlowSelection.Event)
        {
            var session = new EventV1Session(
                nonce, new PinnedEventV1NativeAdapter(), new FrozenEventItemChildFactory());
            try { return new RoomFlowWireService(nonce, session); }
            catch { session.Dispose(); throw; }
        }
        throw new InvalidOperationException("Unsupported room flow selection.");
    }

    private sealed class Runtime : IRoomFlowBootstrapRuntime
    {
        private RoomFlowTransportRuntime? _runtime;
        internal void Set(RoomFlowTransportRuntime runtime) => _runtime = runtime;
        public bool Start() => Inner.Start();
        public bool DrainFrame() => Inner.DrainFrame();
        public bool StopTransportAndJoin() => Inner.StopTransportAndJoin();
        public bool TransportStopped => Inner.TransportStopped;
        public bool DisposeServiceOnOwnerFrame() => Inner.DisposeServiceOnOwnerFrame();
        public bool ServiceDisposed => Inner.ServiceDisposed;
        public bool IsTerminalOrStopping => Inner.IsTerminalOrStopping;
        private RoomFlowTransportRuntime Inner => _runtime ?? throw new InvalidOperationException();
    }
}
