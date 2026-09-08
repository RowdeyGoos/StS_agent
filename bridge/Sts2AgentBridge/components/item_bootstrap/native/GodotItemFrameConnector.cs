using System;
using System.Threading;
using Godot;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal sealed class GodotItemFrameConnector : IItemBootstrapFrameConnector
{
    public IItemBootstrapFrameAttachment? Attach(Action onFrame)
    {
        if (onFrame is null)
        {
            return null;
        }

        SceneTree? tree = Engine.GetMainLoop() as SceneTree;
        if (tree is null)
        {
            return null;
        }

        Callable callable = Callable.From(onFrame);
        var attachment = new Attachment(tree, callable);
        try
        {
            Error result = tree.Connect(SceneTree.SignalName.ProcessFrame, callable, 0u);
            if (result != Error.Ok)
            {
                return null;
            }
            attachment.ConfirmConnection();
            return attachment;
        }
        catch
        {
            // A throwing Connect has uncertain side effects. Retain the
            // attachment for a possible later owner-frame detach.
            return attachment;
        }
    }

    private sealed class Attachment : IItemBootstrapFrameAttachment
    {
        private readonly SceneTree _tree;
        private readonly Callable _callable;
        private int _state;
        private int _connectionConfirmed;

        internal Attachment(SceneTree tree, Callable callable)
        {
            _tree = tree;
            _callable = callable;
        }

        public bool CanActivate => Volatile.Read(ref _connectionConfirmed) != 0;

        internal void ConfirmConnection()
        {
            Volatile.Write(ref _connectionConfirmed, 1);
        }

        public bool TryDetach()
        {
            int observed = Interlocked.CompareExchange(ref _state, 1, 0);
            if (observed == 2)
            {
                return true;
            }
            if (observed != 0)
            {
                return false;
            }

            try
            {
                _tree.Disconnect(SceneTree.SignalName.ProcessFrame, _callable);
                Volatile.Write(ref _state, 2);
                return true;
            }
            catch
            {
                Volatile.Write(ref _state, 0);
                return false;
            }
        }
    }
}
