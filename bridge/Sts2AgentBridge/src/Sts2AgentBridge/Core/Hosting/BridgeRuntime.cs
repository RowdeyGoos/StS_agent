using System;

namespace Sts2AgentBridge.Core.Hosting;

public interface IBridgeListener : IDisposable
{
    void Start();

    void StopAccepting();

    bool StopAndJoin(TimeSpan timeout);
}

public sealed class BridgeRuntime : IDisposable
{
    public static readonly TimeSpan ShutdownJoinTimeout = TimeSpan.FromMilliseconds(2_000);

    private readonly object _gate = new();
    private readonly IDisposable _ownedConfiguration;
    private readonly BoundedFrameWorkQueue? _frameQueue;
    private readonly IDisposable? _frameDispatcher;
    private readonly IBridgeListener _listener;
    private readonly BridgeLifecycle _lifecycle = new();
    private bool _cleanupComplete;

    public BridgeRuntime(
        IDisposable ownedConfiguration,
        BoundedFrameWorkQueue? frameQueue,
        IDisposable? frameDispatcher,
        IBridgeListener listener)
    {
        _ownedConfiguration = ownedConfiguration ?? throw new ArgumentNullException(nameof(ownedConfiguration));
        _frameQueue = frameQueue;
        _frameDispatcher = frameDispatcher;
        _listener = listener ?? throw new ArgumentNullException(nameof(listener));

        if ((frameQueue is null) != (frameDispatcher is null))
        {
            throw new ArgumentException("Frame queue and dispatcher must either both be present or both be absent.");
        }
    }

    public BridgeLifecycleState State => _lifecycle.State;

    public bool Start()
    {
        lock (_gate)
        {
            if (!_lifecycle.TryTransition(BridgeLifecycleState.Created, BridgeLifecycleState.Starting))
            {
                return false;
            }

            try
            {
                _listener.Start();
                return _lifecycle.TryTransition(BridgeLifecycleState.Starting, BridgeLifecycleState.Running);
            }
            catch
            {
                _lifecycle.TryTransition(BridgeLifecycleState.Starting, BridgeLifecycleState.Faulted);
                CleanupLocked();
                return false;
            }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            CleanupLocked();
        }
    }

    private void CleanupLocked()
    {
        if (_cleanupComplete)
        {
            return;
        }

        BridgeLifecycleState state = _lifecycle.State;
        if (state == BridgeLifecycleState.Running)
        {
            _lifecycle.TryTransition(BridgeLifecycleState.Running, BridgeLifecycleState.Stopping);
        }
        else if (state == BridgeLifecycleState.Faulted)
        {
            _lifecycle.TryTransition(BridgeLifecycleState.Faulted, BridgeLifecycleState.Stopping);
        }
        else if (state == BridgeLifecycleState.Created)
        {
            _lifecycle.TryTransition(BridgeLifecycleState.Created, BridgeLifecycleState.Stopping);
            _cleanupComplete = true;
            DisposeNoThrow(_listener);
            if (_frameQueue is not null)
            {
                TryNoThrow(_frameQueue.Stop);
            }
            DisposeNoThrow(_frameDispatcher);
            DisposeNoThrow(_ownedConfiguration);
            _lifecycle.TryTransition(BridgeLifecycleState.Stopping, BridgeLifecycleState.Stopped);
            return;
        }

        TryNoThrow(_listener.StopAccepting);
        if (_frameQueue is not null)
        {
            TryNoThrow(_frameQueue.Stop);
        }
        DisposeNoThrow(_frameDispatcher);
        bool joined = TryStopAndJoin(_listener, ShutdownJoinTimeout);
        DisposeNoThrow(_listener);
        DisposeNoThrow(_ownedConfiguration);
        _cleanupComplete = true;

        if (joined && _lifecycle.State == BridgeLifecycleState.Stopping)
        {
            _lifecycle.TryTransition(BridgeLifecycleState.Stopping, BridgeLifecycleState.Stopped);
        }
    }

    private static void DisposeNoThrow(IDisposable? disposable)
    {
        if (disposable is null)
        {
            return;
        }

        try
        {
            disposable.Dispose();
        }
        catch
        {
        }
    }

    private static void TryNoThrow(Action? action)
    {
        if (action is null)
        {
            return;
        }

        try
        {
            action();
        }
        catch
        {
        }
    }

    private static bool TryStopAndJoin(IBridgeListener listener, TimeSpan timeout)
    {
        try
        {
            return listener.StopAndJoin(timeout);
        }
        catch
        {
            return false;
        }
    }
}
