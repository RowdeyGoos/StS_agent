using System;
using System.Security.Cryptography;
using Sts2AgentBridge.Successors.CardSelectionV1.ParentNative;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal sealed class ProductionCardSelectionRuntimeFactory :
    ICardSelectionBootstrapRuntimeFactory
{
    public ICardSelectionBootstrapRuntime? Create(byte[] configuration, byte[] credential)
    {
        try
        {
            var owner = new Runtime();
            CardSelectionTransportRuntime? runtime = CardSelectionTransportRuntime.Create(
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
            // Runtime Create synchronously parses or copies every retained byte.
            // The defensive clear also covers invalid configuration paths that
            // deliberately never invoke the credential reader.
            CryptographicOperations.ZeroMemory(configuration);
            CryptographicOperations.ZeroMemory(credential);
        }
    }

    private static CardSelectionV1WireService CreateService(
        CardSelectionReleaseSelection selection,
        string nonce)
    {
        ICardSelectionParentV1NativeAdapter? adapter = null;
        CardSelectionParentV1Session? session = null;
        try
        {
            var pinned = new PinnedCardSelectionParentV1NativeAdapter();
            adapter = pinned;
            var configured = new ConfiguredCardSelectionParentV1NativeAdapter(selection, pinned);
            adapter = configured;
            session = new CardSelectionParentV1Session(nonce, configured);
            adapter = null;
            var service = new CardSelectionV1WireService(nonce, session);
            session = null;
            return service;
        }
        finally
        {
            session?.Dispose();
            adapter?.Dispose();
        }
    }

    private sealed class Runtime : ICardSelectionBootstrapRuntime
    {
        private CardSelectionTransportRuntime? _runtime;

        internal void Set(CardSelectionTransportRuntime runtime) =>
            _runtime = runtime ?? throw new ArgumentNullException(nameof(runtime));

        public bool Start() => Inner.Start();
        public bool DrainFrame() => Inner.DrainFrame();
        public bool StopTransportAndJoin() => Inner.StopTransportAndJoin();
        public bool TransportStopped => Inner.TransportStopped;
        public bool DisposeServiceOnOwnerFrame() => Inner.DisposeServiceOnOwnerFrame();
        public bool ServiceDisposed => Inner.ServiceDisposed;
        public bool IsTerminalOrStopping => Inner.IsTerminalOrStopping;

        private CardSelectionTransportRuntime Inner =>
            _runtime ?? throw new InvalidOperationException("Runtime was not initialized.");
    }
}
