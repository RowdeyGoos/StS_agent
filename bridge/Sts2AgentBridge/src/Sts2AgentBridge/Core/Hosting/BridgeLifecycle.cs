using System;

namespace Sts2AgentBridge.Core.Hosting;

public enum BridgeLifecycleState
{
    Created,
    Starting,
    Running,
    Stopping,
    Stopped,
    Faulted,
}

public sealed class BridgeLifecycle
{
    private readonly object _gate = new();
    private BridgeLifecycleState _state = BridgeLifecycleState.Created;

    public BridgeLifecycleState State
    {
        get
        {
            lock (_gate)
            {
                return _state;
            }
        }
    }

    public bool TryTransition(BridgeLifecycleState expected, BridgeLifecycleState next)
    {
        if (!IsAllowed(expected, next))
        {
            return false;
        }

        lock (_gate)
        {
            if (_state != expected)
            {
                return false;
            }

            _state = next;
            return true;
        }
    }

    private static bool IsAllowed(BridgeLifecycleState expected, BridgeLifecycleState next) =>
        (expected, next) switch
        {
            (BridgeLifecycleState.Created, BridgeLifecycleState.Starting) => true,
            (BridgeLifecycleState.Created, BridgeLifecycleState.Stopping) => true,
            (BridgeLifecycleState.Starting, BridgeLifecycleState.Running) => true,
            (BridgeLifecycleState.Starting, BridgeLifecycleState.Faulted) => true,
            (BridgeLifecycleState.Running, BridgeLifecycleState.Stopping) => true,
            (BridgeLifecycleState.Faulted, BridgeLifecycleState.Stopping) => true,
            (BridgeLifecycleState.Stopping, BridgeLifecycleState.Stopped) => true,
            _ => false,
        };
}
