using System;
using System.Diagnostics;
using System.Threading;

namespace Sts2AgentBridge.Unified;

internal sealed class StopwatchBridgeBootstrapClock : IBridgeBootstrapClock
{
    internal static readonly StopwatchBridgeBootstrapClock Instance = new();
    private StopwatchBridgeBootstrapClock() { }
    public long Timestamp => Stopwatch.GetTimestamp();
    public long Frequency => Stopwatch.Frequency;
}

internal sealed class SystemBridgeBootstrapTimerFactory : IBridgeBootstrapTimerFactory
{
    internal static readonly SystemBridgeBootstrapTimerFactory Instance = new();
    private SystemBridgeBootstrapTimerFactory() { }

    public IBridgeBootstrapTimer Arm(TimeSpan dueTime, Action callback)
    {
        ArgumentNullException.ThrowIfNull(callback);
        var owner = new TimerOwner();
        Timer? timer = null;
        try
        {
            timer = new Timer(static state => ((Action)state!).Invoke(), callback,
                dueTime <= TimeSpan.Zero ? TimeSpan.Zero : dueTime, Timeout.InfiniteTimeSpan);
            owner.Set(timer); timer = null; return owner;
        }
        finally { timer?.Dispose(); }
    }

    private sealed class TimerOwner : IBridgeBootstrapTimer
    {
        private readonly object _gate = new();
        private Timer? _timer;
        internal void Set(Timer timer)
        {
            lock (_gate)
            {
                if (_timer is not null) throw new InvalidOperationException();
                _timer = timer;
            }
        }
        public void Dispose()
        {
            lock (_gate)
            {
                if (_timer is null) return;
                _timer.Dispose();
                _timer = null;
            }
        }
    }
}
