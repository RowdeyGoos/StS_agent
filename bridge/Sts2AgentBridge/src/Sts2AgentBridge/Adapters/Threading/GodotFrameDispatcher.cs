using System;
using System.Threading;
using Godot;

namespace Sts2AgentBridge.Adapters.Threading;

public sealed class GodotFrameDispatcher : IDisposable
{
    private readonly SceneTree _tree;
    private readonly Callable _callable;
    private int _disposed;

    public GodotFrameDispatcher(Action onFrame)
    {
        ArgumentNullException.ThrowIfNull(onFrame);

        _tree = Engine.GetMainLoop() as SceneTree
            ?? throw new InvalidOperationException("main_loop_unavailable");
        _callable = Callable.From(onFrame);
        Error result = _tree.Connect(SceneTree.SignalName.ProcessFrame, _callable, 0u);
        if (result != Error.Ok)
        {
            throw new InvalidOperationException("frame_connect_failed");
        }
    }

    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
        {
            return;
        }

        _tree.Disconnect(SceneTree.SignalName.ProcessFrame, _callable);
    }
}
