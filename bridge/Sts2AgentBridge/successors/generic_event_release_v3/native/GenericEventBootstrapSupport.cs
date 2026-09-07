using System;
using System.Diagnostics;
using System.Threading;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV3;

internal sealed class StopwatchGenericEventBootstrapClock : IGenericEventBootstrapClock
{
    internal static readonly StopwatchGenericEventBootstrapClock Instance = new();
    private StopwatchGenericEventBootstrapClock() { }
    public long Timestamp => Stopwatch.GetTimestamp();
    public long Frequency => Stopwatch.Frequency;
}

internal sealed class SystemGenericEventBootstrapTimerFactory : IGenericEventBootstrapTimerFactory
{
    internal static readonly SystemGenericEventBootstrapTimerFactory Instance = new();
    private SystemGenericEventBootstrapTimerFactory() { }

    public IGenericEventBootstrapTimer Arm(TimeSpan dueTime, Action callback)
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

    private sealed class TimerOwner : IGenericEventBootstrapTimer
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
