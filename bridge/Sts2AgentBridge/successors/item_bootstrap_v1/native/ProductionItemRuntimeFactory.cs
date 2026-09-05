using System;
using System.Security.Cryptography;
using Sts2AgentBridge.Successors.ItemTransportV1;
using Sts2AgentBridge.Successors.ItemV1.Native;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal sealed class ProductionItemRuntimeFactory : IItemBootstrapRuntimeFactory
{
    public IItemBootstrapRuntime? Create(byte[] configuration, byte[] credential)
    {
        bool createInvoked = false;
        try
        {
            var owner = new Runtime();
            var adapter = new PinnedItemV1NativeAdapter();
            createInvoked = true;
            ItemTransportRuntime? runtime = ItemTransportRuntime.Create(
                configuration,
                () => credential,
                adapter);
            if (runtime is null)
            {
                return null;
            }

            owner.Set(runtime);
            return owner;
        }
        catch
        {
            return null;
        }
        finally
        {
            if (!createInvoked)
            {
                CryptographicOperations.ZeroMemory(configuration);
                CryptographicOperations.ZeroMemory(credential);
            }
        }
    }

    private sealed class Runtime : IItemBootstrapRuntime
    {
        private ItemTransportRuntime? _runtime;

        internal void Set(ItemTransportRuntime runtime)
        {
            _runtime = runtime;
        }

        public bool Start() => Inner.Start();

        public bool DrainFrame() => Inner.DrainFrame();

        public bool StopAndJoin() => Inner.StopAndJoin();

        public bool IsStopped => Inner.IsStopped;

        private ItemTransportRuntime Inner => _runtime ??
            throw new InvalidOperationException("Runtime ownership is not initialized.");
    }
}
