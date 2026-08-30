using System;
using System.Collections.Concurrent;
using System.Threading;

namespace Sts2AgentBridge.Core.Hosting;

public enum FrameDispatchStatus
{
    Unavailable = 0,
    Success = 1,
    Busy = 2,
    TimedOut = 3,
    Fault = 4,
}

public readonly record struct FrameDispatchResult<T>(FrameDispatchStatus Status, T? Value)
{
    public static FrameDispatchResult<T> Success(T value) => new(FrameDispatchStatus.Success, value);
}

public sealed class BoundedFrameWorkQueue
{
    public const int Capacity = 2;
    public const int WorkPerFrame = 2;
    public const int QueueWaitMilliseconds = 250;
    public const int ResultWaitMilliseconds = 500;

    private readonly ConcurrentQueue<IWorkItem> _queue = new();
    private readonly SemaphoreSlim _slots = new(Capacity, Capacity);
    private readonly object _acceptGate = new();
    private int _accepting = 1;

    public int OutstandingCount => Capacity - _slots.CurrentCount;

    public FrameDispatchResult<T> Submit<T>(Func<T> operation)
    {
        ArgumentNullException.ThrowIfNull(operation);

        if (Volatile.Read(ref _accepting) == 0)
        {
            return new FrameDispatchResult<T>(FrameDispatchStatus.Unavailable, default);
        }

        if (!_slots.Wait(QueueWaitMilliseconds))
        {
            return new FrameDispatchResult<T>(FrameDispatchStatus.Busy, default);
        }

        var item = new WorkItem<T>(operation, _slots);
        lock (_acceptGate)
        {
            if (Volatile.Read(ref _accepting) == 0)
            {
                item.CancelDequeued();
                return new FrameDispatchResult<T>(FrameDispatchStatus.Unavailable, default);
            }

            _queue.Enqueue(item);
        }

        if (!item.Wait(ResultWaitMilliseconds))
        {
            item.Timeout();
            return new FrameDispatchResult<T>(FrameDispatchStatus.TimedOut, default);
        }

        return item.Status == FrameDispatchStatus.Success
            ? FrameDispatchResult<T>.Success(item.Value!)
            : new FrameDispatchResult<T>(item.Status, default);
    }

    public void DrainFrame()
    {
        for (int index = 0; index < WorkPerFrame; index++)
        {
            IWorkItem? item;
            lock (_acceptGate)
            {
                if (Volatile.Read(ref _accepting) == 0 ||
                    !_queue.TryDequeue(out item))
                {
                    return;
                }

                if (!item.TryClaim())
                {
                    item.CancelDequeued();
                    continue;
                }
            }

            item.ExecuteClaimed();
        }
    }

    public void Stop()
    {
        lock (_acceptGate)
        {
            if (Interlocked.Exchange(ref _accepting, 0) == 0)
            {
                return;
            }

            while (_queue.TryDequeue(out IWorkItem? item))
            {
                item.CancelDequeued();
            }
        }
    }

    private interface IWorkItem
    {
        bool TryClaim();

        void ExecuteClaimed();

        void CancelDequeued();
    }

    private sealed class WorkItem<T> : IWorkItem
    {
        private readonly Func<T> _operation;
        private readonly SemaphoreSlim _slots;
        private readonly object _completionGate = new();
        private bool _completed;
        private int _state;
        private int _slotReleased;

        public WorkItem(Func<T> operation, SemaphoreSlim slots)
        {
            _operation = operation;
            _slots = slots;
        }

        public FrameDispatchStatus Status { get; private set; } = FrameDispatchStatus.Unavailable;

        public T? Value { get; private set; }

        public bool Wait(int milliseconds)
        {
            lock (_completionGate)
            {
                if (_completed)
                {
                    return true;
                }

                return Monitor.Wait(_completionGate, milliseconds) && _completed;
            }
        }

        public bool TryClaim()
        {
            return Interlocked.CompareExchange(ref _state, 1, 0) == 0;
        }

        public void ExecuteClaimed()
        {
            try
            {
                Value = _operation();
                Status = FrameDispatchStatus.Success;
            }
            catch
            {
                Status = FrameDispatchStatus.Fault;
            }
            finally
            {
                ReleaseSlotOnce();
                SignalCompletion();
            }
        }

        public void Timeout()
        {
            if (Interlocked.CompareExchange(ref _state, 2, 0) == 0)
            {
                Status = FrameDispatchStatus.TimedOut;
                SignalCompletion();
            }
        }

        public void CancelDequeued()
        {
            if (Interlocked.CompareExchange(ref _state, 2, 0) == 0)
            {
                Status = FrameDispatchStatus.Unavailable;
                SignalCompletion();
            }

            ReleaseSlotOnce();
        }

        private void SignalCompletion()
        {
            lock (_completionGate)
            {
                _completed = true;
                Monitor.PulseAll(_completionGate);
            }
        }

        private void ReleaseSlotOnce()
        {
            if (Interlocked.Exchange(ref _slotReleased, 1) == 0)
            {
                _slots.Release();
            }
        }
    }
}
