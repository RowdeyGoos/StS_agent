using System;
using System.Diagnostics;
using System.Threading;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal sealed class StopwatchItemBootstrapClock : IItemBootstrapClock
{
    internal static readonly StopwatchItemBootstrapClock Instance = new();

    private StopwatchItemBootstrapClock()
    {
    }

    public long Timestamp => Stopwatch.GetTimestamp();

    public long Frequency => Stopwatch.Frequency;
}

internal sealed class SystemItemBootstrapTimerFactory : IItemBootstrapTimerFactory
{
    internal static readonly SystemItemBootstrapTimerFactory Instance = new();

    private SystemItemBootstrapTimerFactory()
    {
    }

    public IItemBootstrapTimer Arm(TimeSpan dueTime, Action callback)
    {
        if (callback is null)
        {
            throw new ArgumentNullException(nameof(callback));
        }

        TimeSpan bounded = dueTime <= TimeSpan.Zero ? TimeSpan.Zero : dueTime;
        var owner = new TimerOwner();
        Timer? timer = null;
        try
        {
            timer = new Timer(
                static state => ((Action)state!).Invoke(),
                callback,
                bounded,
                Timeout.InfiniteTimeSpan);
            owner.Set(timer);
            timer = null;
            return owner;
        }
        finally
        {
            timer?.Dispose();
        }
    }

    private sealed class TimerOwner : IItemBootstrapTimer
    {
        private readonly object _gate = new();
        private Timer? _timer;

        internal void Set(Timer timer)
        {
            lock (_gate)
            {
                if (_timer is not null)
                {
                    throw new InvalidOperationException("Timer ownership already assigned.");
                }
                _timer = timer;
            }
        }

        public void Dispose()
        {
            lock (_gate)
            {
                if (_timer is null)
                {
                    return;
                }
                _timer.Dispose();
                _timer = null;
            }
        }
    }
}
