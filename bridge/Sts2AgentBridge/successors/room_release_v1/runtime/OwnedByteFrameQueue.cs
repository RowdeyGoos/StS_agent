using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Threading;

namespace Sts2AgentBridge.Successors.RoomReleaseV1;

internal enum OwnedByteDispatchStatus
{
    Unavailable = 0,
    Success = 1,
    Busy = 2,
    TimedOutBeforeClaim = 3,
    TimedOutAfterClaim = 4,
    Fault = 5,
}

internal readonly record struct OwnedByteDispatchResult(
    OwnedByteDispatchStatus Status,
    byte[]? Value);

internal sealed class OwnedByteFrameQueue : IDisposable
{
    public const int Capacity = 2;
    public const int WorkPerFrame = 2;
    public const int QueueWaitMilliseconds = 250;
    public const int ResultWaitMilliseconds = 500;

    private readonly ConcurrentQueue<WorkItem> _queue = new();
    private readonly SemaphoreSlim _slots = new(Capacity, Capacity);
    private readonly object _gate = new();
    private readonly HashSet<WorkItem> _claimed = new();
    private readonly ManualResetEventSlim _settled = new(false);
    private readonly Action _stateChanged;
    private bool _accepting = true;
    private int _outstanding;
    private bool _disposed;

    public OwnedByteFrameQueue(Action stateChanged)
    {
        _stateChanged = stateChanged ?? throw new ArgumentNullException(nameof(stateChanged));
    }

    public int OutstandingCount
    {
        get
        {
            lock (_gate)
            {
                return _outstanding;
            }
        }
    }

    public bool IsSettled
    {
        get
        {
            lock (_gate)
            {
                return !_accepting && _outstanding == 0;
            }
        }
    }

    public OwnedByteDispatchResult Submit(Func<byte[]> operation)
    {
        ArgumentNullException.ThrowIfNull(operation);
        lock (_gate)
        {
            if (!_accepting)
            {
                return new OwnedByteDispatchResult(
                    OwnedByteDispatchStatus.Unavailable, null);
            }
        }
        if (!_slots.Wait(QueueWaitMilliseconds))
        {
            return new OwnedByteDispatchResult(OwnedByteDispatchStatus.Busy, null);
        }

        var item = new WorkItem(operation);
        lock (_gate)
        {
            if (!_accepting)
            {
                _slots.Release();
                return new OwnedByteDispatchResult(
                    OwnedByteDispatchStatus.Unavailable, null);
            }
            _outstanding++;
            _queue.Enqueue(item);
        }

        if (item.Wait(ResultWaitMilliseconds))
        {
            return item.TakeResult();
        }
        OwnedByteDispatchResult result = item.DetachForTimeout();
        return result;
    }

    public bool DrainFrame()
    {
        bool drained = false;
        for (int index = 0; index < WorkPerFrame; index++)
        {
            WorkItem? item;
            bool claimed;
            bool retireCancelled = false;
            lock (_gate)
            {
                if (!_accepting || !_queue.TryDequeue(out item))
                {
                    return drained;
                }
                claimed = item.TryClaim();
                if (!claimed)
                {
                    retireCancelled = item.RetireCancelled();
                }
                else
                {
                    _claimed.Add(item);
                }
            }
            if (!claimed)
            {
                if (retireCancelled)
                {
                    CompleteOutstanding(item, wasClaimed: false);
                }
                continue;
            }
            drained = true;
            item.Execute();
            CompleteOutstanding(item, wasClaimed: true);
        }
        return drained;
    }

    public void Stop()
    {
        List<WorkItem> waiting = new();
        lock (_gate)
        {
            if (!_accepting)
            {
                return;
            }
            _accepting = false;
            if (_outstanding == 0)
            {
                _settled.Set();
            }
            while (_queue.TryDequeue(out WorkItem? item))
            {
                waiting.Add(item);
            }
            foreach (WorkItem item in _claimed)
            {
                item.DetachForStop();
            }
        }
        foreach (WorkItem item in waiting)
        {
            if (item.CancelAndRetireBeforeClaim())
            {
                CompleteOutstanding(item, wasClaimed: false);
            }
        }
    }

    public bool WaitForSettled(int milliseconds)
    {
        if (IsSettled)
        {
            return true;
        }
        return _settled.Wait(milliseconds) && IsSettled;
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed)
            {
                return;
            }
            if (_accepting || _outstanding != 0)
            {
                throw new InvalidOperationException("Queue is still in use.");
            }
            _disposed = true;
        }
        _settled.Dispose();
        _slots.Dispose();
    }

    private void CompleteOutstanding(WorkItem item, bool wasClaimed)
    {
        _slots.Release();
        lock (_gate)
        {
            if (wasClaimed)
            {
                _claimed.Remove(item);
            }
            _outstanding--;
            if (!_accepting && _outstanding == 0)
            {
                _settled.Set();
            }
        }
        _stateChanged();
    }

    private enum WorkPhase
    {
        Queued = 0,
        Claimed = 1,
        Completed = 2,
        Detached = 3,
        Cancelled = 4,
        Transferred = 5,
        Retired = 6,
    }

    private sealed class WorkItem
    {
        private readonly Func<byte[]> _operation;
        private readonly object _gate = new();
        private bool _signalled;
        private WorkPhase _phase;
        private OwnedByteDispatchStatus _status;
        private byte[]? _value;

        public WorkItem(Func<byte[]> operation)
        {
            _operation = operation;
        }

        public bool Wait(int milliseconds)
        {
            lock (_gate)
            {
                if (_signalled)
                {
                    return true;
                }
                return Monitor.Wait(_gate, milliseconds) && _signalled;
            }
        }

        public bool TryClaim()
        {
            lock (_gate)
            {
                if (_phase != WorkPhase.Queued)
                {
                    return false;
                }
                _phase = WorkPhase.Claimed;
                return true;
            }
        }

        public void Execute()
        {
            byte[]? value = null;
            bool success = false;
            try
            {
                value = _operation();
                success = value is not null &&
                    value.Length is >= 1 and <= RoomFlowTransportLimits.MaximumParentBody;
            }
            catch
            {
            }

            bool discard;
            lock (_gate)
            {
                discard = _phase == WorkPhase.Detached;
                if (!discard)
                {
                    _phase = WorkPhase.Completed;
                    _status = success
                        ? OwnedByteDispatchStatus.Success
                        : OwnedByteDispatchStatus.Fault;
                    _value = success ? value : null;
                    SignalLocked();
                }
            }
            if (!success || discard)
            {
                Zero(value);
            }
        }

        public OwnedByteDispatchResult TakeResult()
        {
            lock (_gate)
            {
                if (_phase != WorkPhase.Completed)
                {
                    return new OwnedByteDispatchResult(_status, null);
                }
                _phase = WorkPhase.Transferred;
                byte[]? value = _value;
                _value = null;
                return new OwnedByteDispatchResult(_status, value);
            }
        }

        public OwnedByteDispatchResult DetachForTimeout()
        {
            lock (_gate)
            {
                if (_phase == WorkPhase.Completed)
                {
                    return TakeResult();
                }
                if (_phase == WorkPhase.Queued)
                {
                    _phase = WorkPhase.Cancelled;
                    _status = OwnedByteDispatchStatus.TimedOutBeforeClaim;
                    SignalLocked();
                    return new OwnedByteDispatchResult(_status, null);
                }
                if (_phase == WorkPhase.Claimed)
                {
                    _phase = WorkPhase.Detached;
                    _status = OwnedByteDispatchStatus.TimedOutAfterClaim;
                    SignalLocked();
                    return new OwnedByteDispatchResult(_status, null);
                }
                return new OwnedByteDispatchResult(_status, null);
            }
        }

        public bool RetireCancelled()
        {
            lock (_gate)
            {
                if (_phase != WorkPhase.Cancelled)
                {
                    return false;
                }
                _phase = WorkPhase.Retired;
                return true;
            }
        }

        public bool CancelAndRetireBeforeClaim()
        {
            lock (_gate)
            {
                if (_phase == WorkPhase.Queued)
                {
                    _status = OwnedByteDispatchStatus.Unavailable;
                    _phase = WorkPhase.Retired;
                    SignalLocked();
                    return true;
                }
                if (_phase == WorkPhase.Cancelled)
                {
                    _phase = WorkPhase.Retired;
                    return true;
                }
                return false;
            }
        }

        public void DetachForStop()
        {
            lock (_gate)
            {
                if (_phase == WorkPhase.Claimed)
                {
                    _phase = WorkPhase.Detached;
                    _status = OwnedByteDispatchStatus.Unavailable;
                    SignalLocked();
                }
            }
        }

        private void SignalLocked()
        {
            _signalled = true;
            Monitor.PulseAll(_gate);
        }

        private static void Zero(byte[]? value)
        {
            if (value is not null)
            {
                CryptographicOperations.ZeroMemory(value);
            }
        }
    }
}
