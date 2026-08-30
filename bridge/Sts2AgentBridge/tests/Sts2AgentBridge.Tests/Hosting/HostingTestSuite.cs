using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Sts2AgentBridge.Adapters.Diagnostics;
using Sts2AgentBridge.Core.Hosting;

namespace Sts2AgentBridge.Tests.Hosting;

internal static class HostingTestSuite
{
    public static void Run()
    {
        TestLifecycleTransitions();
        TestRuntimeReverseCleanup();
        TestRuntimeDisposeBeforeStart();
        TestCompatibleRuntimeDisposeBeforeStartStopsQueue();
        TestRuntimeStartupFailureUnwinds();
        TestRuntimeJoinFailureDoesNotClaimStopped();
        TestRuntimeConcurrentDisposeIsIdempotent();
        TestHostLogFormatterIsClosedAndSanitized();
    }

    private static void TestRuntimeDisposeBeforeStart()
    {
        var calls = new List<string>();
        var runtime = new BridgeRuntime(
            new RecordingDisposable(calls, "configuration.dispose"),
            null,
            null,
            new RecordingListener(calls, throwOnStart: false));

        runtime.Dispose();

        TestAssert.Equal(BridgeLifecycleState.Stopped, runtime.State, "never-started runtime should stop");
        TestAssert.Equal(
            "listener.dispose|configuration.dispose",
            string.Join("|", calls),
            "never-started runtime cleanup order");
        TestAssert.False(runtime.Start(), "disposed runtime cannot start");
    }

    private static void TestCompatibleRuntimeDisposeBeforeStartStopsQueue()
    {
        var calls = new List<string>();
        var queue = new BoundedFrameWorkQueue();
        var runtime = new BridgeRuntime(
            new RecordingDisposable(calls, "configuration.dispose"),
            queue,
            new RecordingDisposable(calls, "dispatcher.dispose"),
            new RecordingListener(calls, throwOnStart: false));

        runtime.Dispose();

        TestAssert.Equal(BridgeLifecycleState.Stopped, runtime.State, "never-started compatible runtime should stop");
        TestAssert.Equal(
            FrameDispatchStatus.Unavailable,
            queue.Submit(() => 1).Status,
            "never-started compatible runtime should stop its frame queue");
    }

    private static void TestLifecycleTransitions()
    {
        var lifecycle = new BridgeLifecycle();
        TestAssert.Equal(BridgeLifecycleState.Created, lifecycle.State, "initial lifecycle");
        TestAssert.True(lifecycle.TryTransition(BridgeLifecycleState.Created, BridgeLifecycleState.Starting), "start transition");
        TestAssert.True(lifecycle.TryTransition(BridgeLifecycleState.Starting, BridgeLifecycleState.Running), "running transition");
        TestAssert.False(lifecycle.TryTransition(BridgeLifecycleState.Running, BridgeLifecycleState.Faulted), "invalid running fault shortcut");
        TestAssert.True(lifecycle.TryTransition(BridgeLifecycleState.Running, BridgeLifecycleState.Stopping), "stop transition");
        TestAssert.True(lifecycle.TryTransition(BridgeLifecycleState.Stopping, BridgeLifecycleState.Stopped), "stopped transition");
        TestAssert.False(lifecycle.TryTransition(BridgeLifecycleState.Stopped, BridgeLifecycleState.Starting), "stopped lifecycle cannot restart");

        var faulted = new BridgeLifecycle();
        TestAssert.True(faulted.TryTransition(BridgeLifecycleState.Created, BridgeLifecycleState.Starting), "fault fixture start");
        TestAssert.True(faulted.TryTransition(BridgeLifecycleState.Starting, BridgeLifecycleState.Faulted), "startup fault transition");
        TestAssert.True(faulted.TryTransition(BridgeLifecycleState.Faulted, BridgeLifecycleState.Stopping), "faulted cleanup transition");
        TestAssert.True(faulted.TryTransition(BridgeLifecycleState.Stopping, BridgeLifecycleState.Stopped), "faulted stopped transition");
    }

    private static void TestRuntimeReverseCleanup()
    {
        var calls = new List<string>();
        var configuration = new RecordingDisposable(calls, "configuration.dispose");
        var dispatcher = new RecordingDisposable(calls, "dispatcher.dispose");
        var listener = new RecordingListener(calls, throwOnStart: false);
        var queue = new BoundedFrameWorkQueue();
        var runtime = new BridgeRuntime(configuration, queue, dispatcher, listener);

        TestAssert.True(runtime.Start(), "runtime should start");
        TestAssert.Equal(BridgeLifecycleState.Running, runtime.State, "runtime should be running");
        runtime.Dispose();
        TestAssert.Equal(BridgeLifecycleState.Stopped, runtime.State, "runtime should stop");

        string[] expected =
        {
            "listener.start",
            "listener.stop_accepting",
            "dispatcher.dispose",
            "listener.stop_join",
            "listener.dispose",
            "configuration.dispose",
        };
        TestAssert.Equal(string.Join("|", expected), string.Join("|", calls), "runtime cleanup order");
    }

    private static void TestRuntimeStartupFailureUnwinds()
    {
        var calls = new List<string>();
        var runtime = new BridgeRuntime(
            new RecordingDisposable(calls, "configuration.dispose"),
            null,
            null,
            new RecordingListener(calls, throwOnStart: true));

        TestAssert.False(runtime.Start(), "listener startup failure should be contained");
        TestAssert.Equal(BridgeLifecycleState.Stopped, runtime.State, "failed startup should unwind to stopped");
        TestAssert.Equal(
            "listener.start|listener.stop_accepting|listener.stop_join|listener.dispose|configuration.dispose",
            string.Join("|", calls),
            "failed startup reverse unwind");
    }

    private static void TestRuntimeConcurrentDisposeIsIdempotent()
    {
        var calls = new List<string>();
        var runtime = new BridgeRuntime(
            new RecordingDisposable(calls, "configuration.dispose"),
            null,
            null,
            new RecordingListener(calls, throwOnStart: false));
        TestAssert.True(runtime.Start(), "concurrent cleanup fixture starts");

        Task.WaitAll(Task.Run(runtime.Dispose), Task.Run(runtime.Dispose));

        TestAssert.Equal(1, calls.Count(value => value == "listener.dispose"), "listener disposed once");
        TestAssert.Equal(1, calls.Count(value => value == "configuration.dispose"), "configuration disposed once");
    }

    private static void TestRuntimeJoinFailureDoesNotClaimStopped()
    {
        var calls = new List<string>();
        var runtime = new BridgeRuntime(
            new RecordingDisposable(calls, "configuration.dispose"),
            null,
            null,
            new RecordingListener(calls, throwOnStart: false, joinResult: false));
        TestAssert.True(runtime.Start(), "join-failure fixture starts");

        runtime.Dispose();

        TestAssert.Equal(BridgeLifecycleState.Stopping, runtime.State, "failed join must not claim stopped");
        TestAssert.Equal(1, calls.Count(value => value == "listener.stop_join"), "shutdown has one bounded join attempt");
        TestAssert.Equal(1, calls.Count(value => value == "configuration.dispose"), "join failure still clears configuration");
    }

    private static void TestHostLogFormatterIsClosedAndSanitized()
    {
        MethodInfo format = typeof(GodotBridgeLogger).GetMethod(
                "Format",
                BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException("sanitized logger formatter missing");
        var expected = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["disabled"] = "[Sts2AgentBridge] disabled",
            ["invalid_configuration"] = "[Sts2AgentBridge] invalid_configuration",
            ["uncertain_build_identity"] = "[Sts2AgentBridge] uncertain_build_identity",
            ["incompatible_locked"] = "[Sts2AgentBridge] incompatible_locked",
            ["running"] = "[Sts2AgentBridge] running",
            ["startup_failed"] = "[Sts2AgentBridge] startup_failed",
            ["stopped"] = "[Sts2AgentBridge] stopped",
        };
        foreach ((string code, string line) in expected)
        {
            TestAssert.Equal(line, format.Invoke(null, new object?[] { code }) as string, "closed host-log code " + code);
        }

        const string sensitive =
            "fixture-token-0123456789abcdef /Users/fixture/request MegaCrit.Sts2.SecretType";
        string sanitized = format.Invoke(null, new object?[] { sensitive }) as string ?? string.Empty;
        TestAssert.Equal("[Sts2AgentBridge] startup_failed", sanitized, "unknown host-log input fails closed");
        TestAssert.False(sanitized.Contains("fixture", StringComparison.Ordinal), "host log drops exception/request detail");
        TestAssert.False(sanitized.Contains("/Users", StringComparison.Ordinal), "host log drops absolute paths");
        TestAssert.False(sanitized.Contains("MegaCrit", StringComparison.Ordinal), "host log drops game type names");
    }

    private sealed class RecordingDisposable : IDisposable
    {
        private readonly List<string> _calls;
        private readonly string _value;

        public RecordingDisposable(List<string> calls, string value)
        {
            _calls = calls;
            _value = value;
        }

        public void Dispose()
        {
            _calls.Add(_value);
        }
    }

    private sealed class RecordingListener : IBridgeListener
    {
        private readonly List<string> _calls;
        private readonly bool _throwOnStart;
        private readonly bool _joinResult;

        public RecordingListener(List<string> calls, bool throwOnStart, bool joinResult = true)
        {
            _calls = calls;
            _throwOnStart = throwOnStart;
            _joinResult = joinResult;
        }

        public void Start()
        {
            _calls.Add("listener.start");
            if (_throwOnStart)
            {
                throw new InvalidOperationException("fixture-sensitive-detail");
            }
        }

        public void StopAccepting()
        {
            _calls.Add("listener.stop_accepting");
        }

        public bool StopAndJoin(TimeSpan timeout)
        {
            TestAssert.Equal(BridgeRuntime.ShutdownJoinTimeout, timeout, "join timeout");
            _calls.Add("listener.stop_join");
            return _joinResult;
        }

        public void Dispose()
        {
            _calls.Add("listener.dispose");
        }
    }
}
