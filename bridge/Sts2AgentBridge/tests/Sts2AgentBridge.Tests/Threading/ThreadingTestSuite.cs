using System;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Hosting;

namespace Sts2AgentBridge.Tests.Threading;

internal static class ThreadingTestSuite
{
    public static void Run()
    {
        TestAssert.Equal(FrameDispatchStatus.Unavailable, default(FrameDispatchResult<int>).Status, "default dispatch fails closed");
        TestSuccessfulDrain();
        TestFaultIsSanitized();
        TestCapacityBound();
        TestTimedOutWorkRetainsBoundUntilDequeued();
        TestClaimedWorkDoesNotHoldTheAcceptanceGate();
        TestStopCancelsQueuedWork();
        TestRepeatedCompletionDoesNotLeakCapacity();
        TestStopRejectsWork();
    }

    private static void TestSuccessfulDrain()
    {
        var queue = new BoundedFrameWorkQueue();
        Task<FrameDispatchResult<int>> pending = Task.Run(() => queue.Submit(() => 42));
        WaitForOutstanding(queue, 1);
        DrainUntil(queue, () => pending.IsCompleted, "successful work should drain");
        FrameDispatchResult<int> result = pending.GetAwaiter().GetResult();
        TestAssert.Equal(FrameDispatchStatus.Success, result.Status, "drained work status");
        TestAssert.Equal(42, result.Value, "drained work value");
        queue.Stop();
    }

    private static void TestFaultIsSanitized()
    {
        var queue = new BoundedFrameWorkQueue();
        Task<FrameDispatchResult<int>> pending = Task.Run(() => queue.Submit<int>(() => throw new SecretFixtureException()));
        WaitForOutstanding(queue, 1);
        DrainUntil(queue, () => pending.IsCompleted, "faulting work should drain");
        FrameDispatchResult<int> result = pending.GetAwaiter().GetResult();
        TestAssert.Equal(FrameDispatchStatus.Fault, result.Status, "worker exception should become typed fault");
        TestAssert.Equal(0, result.Value, "fault should expose no exception-derived value");
        queue.Stop();
    }

    private static void TestCapacityBound()
    {
        var queue = new BoundedFrameWorkQueue();
        Task<FrameDispatchResult<int>> first = Task.Run(() => queue.Submit(() => 1));
        Task<FrameDispatchResult<int>> second = Task.Run(() => queue.Submit(() => 2));
        WaitForOutstanding(queue, 2);
        FrameDispatchResult<int> third = queue.Submit(() => 3);
        TestAssert.Equal(FrameDispatchStatus.Busy, third.Status, "third outstanding request should be bounded");
        DrainUntil(
            queue,
            () => first.IsCompleted && second.IsCompleted,
            "bounded work should drain");
        TestAssert.Equal(FrameDispatchStatus.Success, first.GetAwaiter().GetResult().Status, "first bounded work");
        TestAssert.Equal(FrameDispatchStatus.Success, second.GetAwaiter().GetResult().Status, "second bounded work");
        queue.Stop();
    }

    private static void TestStopRejectsWork()
    {
        var queue = new BoundedFrameWorkQueue();
        queue.Stop();
        queue.Stop();
        FrameDispatchResult<int> result = queue.Submit(() => 7);
        TestAssert.Equal(FrameDispatchStatus.Unavailable, result.Status, "stopped queue should reject work");
    }

    private static void TestTimedOutWorkRetainsBoundUntilDequeued()
    {
        var queue = new BoundedFrameWorkQueue();
        int canceledExecutions = 0;
        Task<FrameDispatchResult<int>> first = Task.Run(
            () => queue.Submit(() => Interlocked.Increment(ref canceledExecutions)));
        Task<FrameDispatchResult<int>> second = Task.Run(
            () => queue.Submit(() => Interlocked.Increment(ref canceledExecutions)));
        WaitForOutstanding(queue, 2);

        Task.WaitAll(first, second);
        TestAssert.Equal(FrameDispatchStatus.TimedOut, first.Result.Status, "first stalled work times out");
        TestAssert.Equal(FrameDispatchStatus.TimedOut, second.Result.Status, "second stalled work times out");
        TestAssert.Equal(2, queue.OutstandingCount, "timed-out tombstones retain the exact queue bound");

        FrameDispatchResult<int> blocked = queue.Submit(() => 3);
        TestAssert.Equal(FrameDispatchStatus.Busy, blocked.Status, "timed-out tombstones cannot admit more work");
        TestAssert.Equal(2, queue.OutstandingCount, "busy submission cannot expand the bounded queue");

        queue.DrainFrame();
        TestAssert.Equal(0, queue.OutstandingCount, "draining canceled tombstones releases their slots");
        TestAssert.Equal(0, canceledExecutions, "timed-out work never reaches the game callback");

        Task<FrameDispatchResult<int>> fresh = Task.Run(() => queue.Submit(() => 7));
        WaitForOutstanding(queue, 1);
        DrainUntil(queue, () => fresh.IsCompleted, "fresh work should proceed after tombstones drain");
        TestAssert.Equal(FrameDispatchStatus.Success, fresh.Result.Status, "fresh work succeeds after cleanup");
        queue.Stop();
    }

    private static void TestClaimedWorkDoesNotHoldTheAcceptanceGate()
    {
        var queue = new BoundedFrameWorkQueue();
        using var operationStarted = new ManualResetEventSlim();
        using var releaseOperation = new ManualResetEventSlim();
        int canceledExecutions = 0;
        Task<FrameDispatchResult<int>> executing = Task.Run(
            () => queue.Submit(
                () =>
                {
                    operationStarted.Set();
                    releaseOperation.Wait();
                    return 1;
                }));
        WaitForOutstanding(queue, 1);
        Task<FrameDispatchResult<int>> queued = Task.Run(
            () => queue.Submit(() => Interlocked.Increment(ref canceledExecutions)));
        WaitForOutstanding(queue, 2);

        Task drain = Task.Run(queue.DrainFrame);
        TestAssert.True(operationStarted.Wait(TimeSpan.FromMilliseconds(200)), "drain should enter first callback");
        Task stop = Task.Run(queue.Stop);
        WaitForAcceptanceStop(queue);
        TestAssert.True(
            stop.Wait(TimeSpan.FromMilliseconds(200)),
            "a claimed callback must not hold the acceptance gate or delay queued-work cancellation");
        TestAssert.Equal(
            FrameDispatchStatus.Unavailable,
            queued.GetAwaiter().GetResult().Status,
            "stop cancels the still-queued callback while claimed work is in flight");
        TestAssert.Equal(
            FrameDispatchStatus.Unavailable,
            queue.Submit(() => 3).Status,
            "stop closes acceptance while claimed work is in flight");

        releaseOperation.Set();
        Task.WaitAll(drain, stop, executing, queued);
        TestAssert.Equal(FrameDispatchStatus.Success, executing.Result.Status, "claimed callback completes independently");
        TestAssert.Equal(0, canceledExecutions, "queued callback cannot execute after stop begins");
        TestAssert.Equal(0, queue.OutstandingCount, "stop/drain interleaving releases all capacity");
    }

    private static void TestStopCancelsQueuedWork()
    {
        var queue = new BoundedFrameWorkQueue();
        Task<FrameDispatchResult<int>> pending = Task.Run(() => queue.Submit(() => 7));
        WaitForOutstanding(queue, 1);

        queue.Stop();

        FrameDispatchResult<int> result = pending.GetAwaiter().GetResult();
        TestAssert.Equal(FrameDispatchStatus.Unavailable, result.Status, "stop should cancel queued work");
        TestAssert.Equal(0, queue.OutstandingCount, "canceled work should release queue capacity");
    }

    private static void TestRepeatedCompletionDoesNotLeakCapacity()
    {
        var queue = new BoundedFrameWorkQueue();
        for (int index = 0; index < 64; index++)
        {
            int expected = index;
            Task<FrameDispatchResult<int>> pending = Task.Run(() => queue.Submit(() => expected));
            WaitForOutstanding(queue, 1);
            DrainUntil(queue, () => pending.IsCompleted, "repeated work should drain");
            FrameDispatchResult<int> result = pending.GetAwaiter().GetResult();
            TestAssert.Equal(FrameDispatchStatus.Success, result.Status, "repeated work status");
            TestAssert.Equal(expected, result.Value, "repeated work value");
            TestAssert.Equal(0, queue.OutstandingCount, "completed work should release queue capacity");
        }

        queue.Stop();
    }

    private static void WaitForOutstanding(BoundedFrameWorkQueue queue, int expected)
    {
        bool reached = SpinWait.SpinUntil(
            () => queue.OutstandingCount == expected,
            TimeSpan.FromMilliseconds(200));
        TestAssert.True(reached, "work should enter bounded queue");
    }

    private static void WaitForAcceptanceStop(BoundedFrameWorkQueue queue)
    {
        FieldInfo accepting = typeof(BoundedFrameWorkQueue).GetField(
                "_accepting",
                BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("accepting state field missing");
        bool stopped = SpinWait.SpinUntil(
            () => (int)(accepting.GetValue(queue) ?? 1) == 0,
            TimeSpan.FromMilliseconds(200));
        TestAssert.True(stopped, "stop should close queue acceptance");
    }

    private static void DrainUntil(BoundedFrameWorkQueue queue, Func<bool> completed, string message)
    {
        bool drained = SpinWait.SpinUntil(
            () =>
            {
                queue.DrainFrame();
                return completed();
            },
            TimeSpan.FromMilliseconds(200));
        TestAssert.True(drained, message);
    }

    private sealed class SecretFixtureException : Exception
    {
    }
}
