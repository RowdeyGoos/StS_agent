using System;
using System.Threading;
using Godot;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV1;

internal sealed class GenericEventGodotFrameConnector : IGenericEventBootstrapFrameConnector
{
    public IGenericEventBootstrapFrameAttachment? Attach(Action onFrame)
    {
        if (onFrame is null || Engine.GetMainLoop() is not SceneTree tree)
            return null;
        Callable callable = Callable.From(onFrame);
        var attachment = new Attachment(tree, callable);
        try
        {
            if (tree.Connect(SceneTree.SignalName.ProcessFrame, callable, 0u) != Error.Ok)
                return null;
            attachment.ConfirmConnection();
            return attachment;
        }
        catch
        {
            return attachment;
        }
    }

    private sealed class Attachment : IGenericEventBootstrapFrameAttachment
    {
        private readonly SceneTree _tree;
        private readonly Callable _callable;
        private int _state;
        private int _confirmed;

        internal Attachment(SceneTree tree, Callable callable)
        {
            _tree = tree; _callable = callable;
        }

        public bool CanActivate => Volatile.Read(ref _confirmed) != 0;
        internal void ConfirmConnection() => Volatile.Write(ref _confirmed, 1);

        public bool TryDetach()
        {
            int observed = Interlocked.CompareExchange(ref _state, 1, 0);
            if (observed == 2) return true;
            if (observed != 0) return false;
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
