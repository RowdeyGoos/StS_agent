using System;
using System.Diagnostics;

namespace Sts2AgentBridge.Core.Transport;

internal interface IMonotonicClock
{
    long GetTimestamp();

    long Frequency { get; }
}

internal sealed class StopwatchMonotonicClock : IMonotonicClock
{
    public static readonly StopwatchMonotonicClock Instance = new();

    private StopwatchMonotonicClock()
    {
    }

    public long GetTimestamp()
    {
        return Stopwatch.GetTimestamp();
    }

    public long Frequency => Stopwatch.Frequency;
}

internal sealed class MonotonicTokenBucket
{
    private readonly object _gate = new();
    private readonly double _refillPerSecond;
    private readonly double _capacity;
    private readonly IMonotonicClock _clock;
    private double _tokens;
    private long _lastTimestamp;

    public MonotonicTokenBucket(
        double refillPerSecond,
        double capacity,
        IMonotonicClock clock)
    {
        if (!double.IsFinite(refillPerSecond) || refillPerSecond <= 0.0)
        {
            throw new ArgumentOutOfRangeException(nameof(refillPerSecond));
        }

        if (!double.IsFinite(capacity) || capacity < 1.0)
        {
            throw new ArgumentOutOfRangeException(nameof(capacity));
        }

        _clock = clock ?? throw new ArgumentNullException(nameof(clock));
        if (_clock.Frequency <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(clock));
        }

        _refillPerSecond = refillPerSecond;
        _capacity = capacity;
        _tokens = capacity;
        _lastTimestamp = _clock.GetTimestamp();
    }

    public bool TryConsume()
    {
        lock (_gate)
        {
            long currentTimestamp = _clock.GetTimestamp();
            long elapsedTicks = currentTimestamp >= _lastTimestamp
                ? currentTimestamp - _lastTimestamp
                : 0;
            double elapsedSeconds = (double)elapsedTicks / _clock.Frequency;
            _tokens = Math.Min(
                _capacity,
                _tokens + (elapsedSeconds * _refillPerSecond));
            _lastTimestamp = currentTimestamp;

            if (_tokens < 1.0)
            {
                return false;
            }

            _tokens -= 1.0;
            return true;
        }
    }
}
