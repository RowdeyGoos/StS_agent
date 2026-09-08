using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal static class Program
{
    private static int _checkCount;

    private static int Main(string[] arguments)
    {
        if (arguments.Length != 0)
        {
            return 2;
        }

        Run("missing_configuration", MissingConfiguration);
        Run("build_failure_stops_before_credential", BuildFailureStopsBeforeCredential);
        Run("credential_failure", CredentialFailure);
        Run("attach_activate_and_stop_order", AttachActivateAndStopOrder);
        Run("one_shot", OneShot);
        Run("stop_before_initialize", StopBeforeInitialize);
        Run("immediate_timer_stop", ImmediateTimerStop);
        Run("timer_dispose_stop_race", TimerDisposeStopRace);
        Run("timer_dispose_deadline_race", TimerDisposeDeadlineRace);
        Run("timer_dispose_failure_retained", TimerDisposeFailureRetained);
        Run("before_deadline_activates", BeforeDeadlineActivates);
        Run("exact_deadline_expires", ExactDeadlineExpires);
        Run("delayed_timer_cannot_activate", DelayedTimerCannotActivate);
        Run("attach_failure_zeroes", AttachFailureZeroes);
        Run("uncertain_attach_retained", UncertainAttachRetained);
        Run("wrong_thread_requests_stop", WrongThreadRequestsStop);
        Run("factory_failure", FactoryFailure);
        Run("start_failure", StartFailure);
        Run("stop_during_factory", StopDuringFactory);
        Run("stop_during_start", StopDuringStart);
        Run("false_join_deferred_cleanup", FalseJoinDeferredCleanup);
        Run("disconnect_failure_retries", DisconnectFailureRetries);
        Run("stop_fault_retries", StopFaultRetries);
        Run("drain_failure_stops", DrainFailureStops);

        Console.WriteLine(
            "{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"item_v1_bootstrap\",\"check_count\":" +
            _checkCount + "}");
        return 0;
    }

    private static void MissingConfiguration()
    {
        var fixture = new Fixture(null);
        Check(!fixture.Lifecycle.Initialize(), "missing configuration accepted");
        Check(fixture.BuildCalls == 0, "build read after missing configuration");
        Check(fixture.Frames.AttachCalls == 0, "frame attached after missing configuration");
        Check(fixture.Lifecycle.IsFullyStopped, "missing configuration did not settle");
    }

    private static void BuildFailureStopsBeforeCredential()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease) { BuildResult = false };
        Check(!fixture.Lifecycle.Initialize(), "build failure accepted");
        Check(lease.ReadCredentialCalls == 0, "credential read before build passed");
        Check(lease.DisposeCalls == 1, "lease not disposed exactly once");
        Check(IsZero(configuration) && IsZero(credential), "lease buffers not zeroed");
        Check(fixture.Frames.AttachCalls == 0, "frame attached after build failure");
    }

    private static void CredentialFailure()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        lease.Credential = null;
        var fixture = new Fixture(lease);
        Check(!fixture.Lifecycle.Initialize(), "missing credential accepted");
        Check(lease.ReadCredentialCalls == 1, "credential attempt count changed");
        Check(lease.TakeConfigurationCalls == 0, "configuration transferred after credential failure");
        Check(IsZero(configuration), "configuration survived credential failure");
        Check(fixture.Frames.AttachCalls == 0, "frame attached after credential failure");
    }

    private static void AttachActivateAndStopOrder()
    {
        var log = new List<string>();
        var lease = FakeLease.Enabled(log);
        var runtime = new FakeRuntime(log) { Stopped = true };
        var fixture = new Fixture(lease, log, runtime);
        Check(fixture.Lifecycle.Initialize(), "valid initialization failed");
        CheckSequence(log, "open", "build", "credential", "configuration", "lease_dispose", "timer_arm", "attach");
        Check(fixture.Factory.CreateCalls == 0, "runtime created before first frame");
        fixture.Frames.Fire();
        CheckSequence(log, "factory", "start");
        Check(runtime.StartCalls == 1, "runtime start count changed");
        fixture.Frames.Fire();
        Check(runtime.DrainCalls == 1, "later frame did not drain");
        Check(!fixture.Lifecycle.RequestStop(), "off-callback stop claimed attached cleanup complete");
        Check(fixture.Frames.Attachment.DetachCalls == 0, "off-callback stop detached frame");
        fixture.Frames.Fire();
        Check(fixture.Frames.Attachment.DetachCalls == 1, "owner callback did not detach");
        Check(fixture.Lifecycle.IsFullyStopped, "successful lifecycle did not fully stop");
    }

    private static void OneShot()
    {
        var fixture = new Fixture(FakeLease.Enabled());
        Check(fixture.Lifecycle.Initialize(), "first initialize failed");
        Check(!fixture.Lifecycle.Initialize(), "second initialize accepted");
        Check(fixture.OpenCalls == 1 && fixture.Frames.AttachCalls == 1, "one-shot performed repeated work");
        fixture.Timers.Last!.Fire();
        fixture.Frames.Fire();
    }

    private static void StopBeforeInitialize()
    {
        var fixture = new Fixture(FakeLease.Enabled());
        Check(fixture.Lifecycle.RequestStop(), "empty lifecycle did not stop");
        Check(!fixture.Lifecycle.Initialize(), "initialize accepted after process-exit stop");
        Check(fixture.OpenCalls == 0 && fixture.Frames.AttachCalls == 0,
            "stopped lifecycle accessed initialization dependencies");
    }

    private static void ImmediateTimerStop()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        fixture.Timers.FireBeforeReturn = true;
        Check(!fixture.Lifecycle.Initialize(), "immediate timer stop reported initialized");
        Check(IsZero(configuration) && IsZero(credential), "immediate timer stop leaked buffers");
        Check(fixture.Frames.AttachCalls == 0 && fixture.Factory.CreateCalls == 0,
            "immediate timer stop reached frame/runtime");
        Check(fixture.Timers.Last!.DisposeCalls == 1, "immediate timer was not disposed");
    }

    private static void TimerDisposeStopRace()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Timers.Last!.DisposeAction = () => fixture.Lifecycle.RequestStop();
        fixture.Frames.Fire();
        Check(fixture.Factory.CreateCalls == 0, "factory ran after stop during timer disposal");
        Check(IsZero(configuration) && IsZero(credential), "stop during timer disposal leaked buffers");
        Check(fixture.Frames.Attachment.DetachCalls == 1, "stop race did not detach on owner frame");
    }

    private static void TimerDisposeDeadlineRace()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Clock.Now = 4_999;
        fixture.Timers.Last!.DisposeAction = () => fixture.Clock.Now = 5_000;
        fixture.Frames.Fire();
        Check(fixture.Factory.CreateCalls == 0, "factory ran after deadline crossed during timer disposal");
        Check(IsZero(configuration) && IsZero(credential), "deadline race leaked buffers");
        Check(fixture.Frames.Attachment.DetachCalls == 1, "deadline race did not detach");
    }

    private static void TimerDisposeFailureRetained()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Timers.Last!.DisposeFailuresRemaining = 2;
        fixture.Frames.Fire();
        Check(fixture.Factory.CreateCalls == 0, "factory ran after timer cancellation fault");
        Check(!fixture.Lifecycle.IsFullyStopped, "failed timer cleanup was forgotten");
        Check(fixture.Frames.Attachment.DetachCalls == 0, "detached while timer cleanup remained");
        fixture.Frames.Fire();
        Check(fixture.Timers.Last.DisposeCalls == 3, "timer cleanup retry count changed");
        Check(fixture.Frames.Attachment.DetachCalls == 1 && fixture.Lifecycle.IsFullyStopped,
            "timer cleanup did not complete on later owner frame");
        Check(IsZero(configuration) && IsZero(credential), "timer fault leaked buffers");
    }

    private static void BeforeDeadlineActivates()
    {
        var fixture = new Fixture(FakeLease.Enabled());
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Clock.Now = 4_999;
        fixture.Frames.Fire();
        Check(fixture.Factory.CreateCalls == 1, "pre-deadline frame did not create runtime");
        Check(fixture.Runtime.StartCalls == 1, "pre-deadline frame did not start runtime");
        Check(fixture.Timers.Last!.DisposeCalls == 1, "activation did not cancel timer");
        fixture.Lifecycle.RequestStop();
        fixture.Runtime.Stopped = true;
        fixture.Frames.Fire();
    }

    private static void ExactDeadlineExpires()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Clock.Now = 5_000;
        fixture.Frames.Fire();
        Check(fixture.Factory.CreateCalls == 0, "runtime created at exact deadline");
        Check(IsZero(configuration) && IsZero(credential), "deadline did not zero pending buffers");
        Check(fixture.Frames.Attachment.DetachCalls == 1, "expired owner frame did not detach");
        Check(fixture.Lifecycle.IsFullyStopped, "expired lifecycle did not settle");
    }

    private static void DelayedTimerCannotActivate()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Clock.Now = 6_000;
        fixture.Frames.Fire();
        Check(fixture.Factory.CreateCalls == 0, "late frame activated before delayed timer callback");
        Check(IsZero(configuration) && IsZero(credential), "late frame retained buffers");
        fixture.Timers.Last!.Fire();
        Check(fixture.Frames.Attachment.DetachCalls == 1, "late frame did not detach");
    }

    private static void AttachFailureZeroes()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        fixture.Frames.ThrowOnAttach = true;
        Check(!fixture.Lifecycle.Initialize(), "throwing attach accepted");
        Check(IsZero(configuration) && IsZero(credential), "attach failure leaked buffers");
        Check(fixture.Timers.Last!.DisposeCalls == 1, "attach failure retained timer");
        Check(fixture.Factory.CreateCalls == 0, "attach failure created runtime");
    }

    private static void UncertainAttachRetained()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        fixture.Frames.Attachment.CanActivate = false;
        Check(!fixture.Lifecycle.Initialize(), "uncertain attachment allowed activation");
        Check(IsZero(configuration) && IsZero(credential), "uncertain attachment leaked buffers");
        Check(fixture.Factory.CreateCalls == 0, "uncertain attachment created runtime");
        Check(fixture.Frames.Attachment.DetachCalls == 0 && !fixture.Lifecycle.IsFullyStopped,
            "uncertain attachment was discarded off owner frame");
        fixture.Frames.Fire();
        Check(fixture.Frames.Attachment.DetachCalls == 1 && fixture.Lifecycle.IsFullyStopped,
            "uncertain attachment was not cleaned by owner frame");
    }

    private static void WrongThreadRequestsStop()
    {
        var runtime = new FakeRuntime { Stopped = true };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Frames.Fire();
        Task.Run(fixture.Frames.Fire).GetAwaiter().GetResult();
        Check(runtime.StopCalls == 1, "wrong thread did not request runtime stop");
        Check(runtime.DrainCalls == 0, "wrong thread drained runtime");
        Check(fixture.Frames.Attachment.DetachCalls == 0, "wrong thread detached frame");
        fixture.Frames.Fire();
        Check(fixture.Frames.Attachment.DetachCalls == 1, "owner frame did not finish wrong-thread stop");
    }

    private static void FactoryFailure()
    {
        var lease = FakeLease.Enabled();
        byte[] configuration = lease.Configuration!;
        byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease);
        fixture.Factory.Throw = true;
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Frames.Fire();
        Check(fixture.Factory.CreateCalls == 1, "factory not invoked exactly once");
        Check(IsZero(configuration) && IsZero(credential), "factory failure leaked transferred buffers");
        Check(fixture.Runtime.StartCalls == 0, "runtime started after factory failure");
        Check(fixture.Frames.Attachment.DetachCalls == 1, "factory failure did not detach");
    }

    private static void StartFailure()
    {
        var runtime = new FakeRuntime { StartResult = false, Stopped = true };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Frames.Fire();
        Check(runtime.StartCalls == 1, "start not attempted exactly once");
        Check(runtime.StopCalls == 1, "failed start did not stop runtime");
        Check(fixture.Frames.Attachment.DetachCalls == 1, "failed start did not detach");
        fixture.Frames.Fire();
        Check(runtime.StartCalls == 1 && fixture.Factory.CreateCalls == 1, "failed start retried");
    }

    private static void StopDuringFactory()
    {
        using var entered = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        var runtime = new FakeRuntime { Stopped = true };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        fixture.Factory.BeforeReturn = () =>
        {
            entered.Set();
            release.Wait();
        };
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        Task owner = Task.Run(() =>
        {
            fixture.Frames.Fire();
            fixture.Frames.Fire();
        });
        Check(entered.Wait(TimeSpan.FromSeconds(5)), "factory barrier not reached");
        Check(!fixture.Lifecycle.RequestStop(), "startup participant reported full stop");
        release.Set();
        owner.GetAwaiter().GetResult();
        Check(runtime.StartCalls == 0, "runtime started after stop during factory");
        Check(runtime.StopCalls == 1, "created runtime was not stopped");
        Check(fixture.Frames.Attachment.DetachCalls == 1, "owner did not detach after factory unwind");
        Check(fixture.Factory.CreateCalls == 1, "factory retried after stop race");
    }

    private static void StopDuringStart()
    {
        using var entered = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        var runtime = new FakeRuntime { Stopped = false };
        runtime.StartAction = () =>
        {
            entered.Set();
            release.Wait();
            runtime.Stopped = true;
            return false;
        };
        runtime.StopAction = () => false;
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        Task owner = Task.Run(fixture.Frames.Fire);
        Check(entered.Wait(TimeSpan.FromSeconds(5)), "start barrier not reached");
        Check(!fixture.Lifecycle.RequestStop(), "in-flight start reported full stop");
        release.Set();
        owner.GetAwaiter().GetResult();
        Check(runtime.StartCalls == 1 && runtime.StopCalls >= 1, "start/stop race counts changed");
        Check(fixture.Frames.Attachment.DetachCalls == 1, "deferred owner cleanup failed");
    }

    private static void FalseJoinDeferredCleanup()
    {
        var runtime = new FakeRuntime { Stopped = false, StopAction = () => false };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Frames.Fire();
        Check(!fixture.Lifecycle.RequestStop(), "false join reported full stop");
        fixture.Frames.Fire();
        Check(fixture.Frames.Attachment.DetachCalls == 0, "frame detached before runtime settled");
        runtime.Stopped = true;
        fixture.Frames.Fire();
        Check(fixture.Frames.Attachment.DetachCalls == 1, "settled runtime did not detach");
        Check(fixture.Lifecycle.IsFullyStopped, "deferred cleanup not truthful");
    }

    private static void DisconnectFailureRetries()
    {
        var runtime = new FakeRuntime { Stopped = true };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        fixture.Frames.Attachment.DetachResults.Enqueue(false);
        fixture.Frames.Attachment.DetachResults.Enqueue(true);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Frames.Fire();
        fixture.Lifecycle.RequestStop();
        fixture.Frames.Fire();
        Check(fixture.Frames.Attachment.DetachCalls == 1 && !fixture.Lifecycle.IsFullyStopped,
            "failed disconnect lost attachment ownership");
        fixture.Frames.Fire();
        Check(fixture.Frames.Attachment.DetachCalls == 2 && fixture.Lifecycle.IsFullyStopped,
            "disconnect was not retried truthfully");
    }

    private static void StopFaultRetries()
    {
        var runtime = new FakeRuntime { Stopped = false };
        int faults = 1;
        runtime.StopAction = () =>
        {
            if (faults-- > 0)
            {
                throw new InvalidOperationException("synthetic stop fault");
            }
            runtime.Stopped = true;
            return true;
        };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Frames.Fire();
        Check(!fixture.Lifecycle.RequestStop(), "throwing stop reported complete");
        Check(runtime.StopCalls == 1 && fixture.Frames.Attachment.DetachCalls == 0,
            "throwing stop lost retained ownership");
        fixture.Frames.Fire();
        Check(runtime.StopCalls == 2, "throwing stop was not retried once");
        Check(fixture.Frames.Attachment.DetachCalls == 1 && fixture.Lifecycle.IsFullyStopped,
            "retried stop did not settle");
        fixture.Frames.Fire();
        Check(runtime.StopCalls == 2, "successful stop was retried");
    }

    private static void DrainFailureStops()
    {
        var runtime = new FakeRuntime { Stopped = true, ThrowOnDrain = true };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize(), "initialization failed");
        fixture.Frames.Fire();
        fixture.Frames.Fire();
        Check(runtime.DrainCalls == 1 && runtime.StopCalls == 1, "drain failure did not stop once");
        Check(fixture.Frames.Attachment.DetachCalls == 1, "drain failure did not detach");
    }

    private static void Run(string name, Action test)
    {
        try
        {
            test();
            _checkCount++;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(name + ": " + exception.Message);
            Environment.ExitCode = 1;
            throw;
        }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    private static void CheckSequence(List<string> log, params string[] expected)
    {
        int cursor = 0;
        foreach (string entry in log)
        {
            if (cursor < expected.Length && entry == expected[cursor])
            {
                cursor++;
            }
        }
        Check(cursor == expected.Length, "missing sequence: " + string.Join(",", expected));
    }

    private static bool IsZero(byte[] value)
    {
        foreach (byte item in value)
        {
            if (item != 0)
            {
                return false;
            }
        }
        return true;
    }

    private sealed class Fixture
    {
        private readonly FakeLease? _lease;
        private readonly List<string> _log;

        public Fixture(FakeLease? lease, List<string>? log = null, FakeRuntime? runtime = null)
        {
            _lease = lease;
            _log = log ?? new List<string>();
            Runtime = runtime ?? new FakeRuntime(_log) { Stopped = true };
            Clock = new FakeClock();
            Timers = new FakeTimerFactory(_log);
            Frames = new FakeFrameConnector(_log);
            Factory = new FakeRuntimeFactory(Runtime, _log);
            Lifecycle = new ItemBootstrapLifecycle(
                Open,
                VerifyBuild,
                Frames,
                Factory,
                Clock,
                Timers);
        }

        public bool BuildResult { get; set; } = true;
        public int BuildCalls { get; private set; }
        public int OpenCalls { get; private set; }
        public FakeClock Clock { get; }
        public FakeTimerFactory Timers { get; }
        public FakeFrameConnector Frames { get; }
        public FakeRuntimeFactory Factory { get; }
        public FakeRuntime Runtime { get; }
        public ItemBootstrapLifecycle Lifecycle { get; }

        private IItemBootstrapOperatorLease? Open()
        {
            OpenCalls++;
            _log.Add("open");
            return _lease;
        }

        private bool VerifyBuild()
        {
            BuildCalls++;
            _log.Add("build");
            return BuildResult;
        }
    }

    private sealed class FakeLease : IItemBootstrapOperatorLease
    {
        private readonly List<string>? _log;

        private FakeLease(List<string>? log)
        {
            _log = log;
        }

        public byte[]? Configuration { get; set; }
        public byte[]? Credential { get; set; }
        public int ReadCredentialCalls { get; private set; }
        public int TakeConfigurationCalls { get; private set; }
        public int DisposeCalls { get; private set; }

        public static FakeLease Enabled(List<string>? log = null) => new(log)
        {
            Configuration = Filled(147, 0x63),
            Credential = Filled(64, 0x64),
        };

        public byte[]? ReadCredentialOnce()
        {
            ReadCredentialCalls++;
            _log?.Add("credential");
            byte[]? value = Credential;
            Credential = null;
            return value;
        }

        public byte[]? TakeConfiguration()
        {
            TakeConfigurationCalls++;
            _log?.Add("configuration");
            byte[]? value = Configuration;
            Configuration = null;
            return value;
        }

        public void Dispose()
        {
            DisposeCalls++;
            _log?.Add("lease_dispose");
            Zero(Configuration);
            Zero(Credential);
            Configuration = null;
            Credential = null;
        }
    }

    private sealed class FakeClock : IItemBootstrapClock
    {
        public long Now { get; set; }
        public long Timestamp => Now;
        public long Frequency => 1_000;
    }

    private sealed class FakeTimerFactory : IItemBootstrapTimerFactory
    {
        private readonly List<string> _log;

        public FakeTimerFactory(List<string> log)
        {
            _log = log;
        }

        public FakeTimer? Last { get; private set; }
        public bool FireBeforeReturn { get; set; }

        public IItemBootstrapTimer Arm(TimeSpan dueTime, Action callback)
        {
            _log.Add("timer_arm");
            Last = new FakeTimer(callback, dueTime);
            if (FireBeforeReturn)
            {
                Last.Fire();
            }
            return Last;
        }
    }

    private sealed class FakeTimer : IItemBootstrapTimer
    {
        private readonly Action _callback;
        private int _fired;

        public FakeTimer(Action callback, TimeSpan dueTime)
        {
            _callback = callback;
            DueTime = dueTime;
        }

        public TimeSpan DueTime { get; }
        public int DisposeCalls { get; private set; }
        public int DisposeFailuresRemaining { get; set; }
        public Action? DisposeAction { get; set; }

        public void Fire()
        {
            if (Interlocked.Exchange(ref _fired, 1) == 0)
            {
                _callback();
            }
        }

        public void Dispose()
        {
            DisposeCalls++;
            DisposeAction?.Invoke();
            if (DisposeFailuresRemaining > 0)
            {
                DisposeFailuresRemaining--;
                throw new InvalidOperationException("synthetic timer dispose failure");
            }
        }
    }

    private sealed class FakeFrameConnector : IItemBootstrapFrameConnector
    {
        private readonly List<string> _log;
        private Action? _callback;

        public FakeFrameConnector(List<string> log)
        {
            _log = log;
        }

        public bool ThrowOnAttach { get; set; }
        public int AttachCalls { get; private set; }
        public FakeAttachment Attachment { get; } = new();

        public IItemBootstrapFrameAttachment? Attach(Action onFrame)
        {
            AttachCalls++;
            _log.Add("attach");
            if (ThrowOnAttach)
            {
                throw new InvalidOperationException("synthetic attach failure");
            }
            _callback = onFrame;
            return Attachment;
        }

        public void Fire()
        {
            _callback?.Invoke();
        }
    }

    private sealed class FakeAttachment : IItemBootstrapFrameAttachment
    {
        public Queue<bool> DetachResults { get; } = new();
        public int DetachCalls { get; private set; }
        public bool CanActivate { get; set; } = true;

        public bool TryDetach()
        {
            DetachCalls++;
            return DetachResults.Count == 0 || DetachResults.Dequeue();
        }
    }

    private sealed class FakeRuntimeFactory : IItemBootstrapRuntimeFactory
    {
        private readonly FakeRuntime _runtime;
        private readonly List<string> _log;

        public FakeRuntimeFactory(FakeRuntime runtime, List<string> log)
        {
            _runtime = runtime;
            _log = log;
        }

        public bool Throw { get; set; }
        public int CreateCalls { get; private set; }
        public Action? BeforeReturn { get; set; }

        public IItemBootstrapRuntime? Create(byte[] configuration, byte[] credential)
        {
            CreateCalls++;
            _log.Add("factory");
            try
            {
                BeforeReturn?.Invoke();
                if (Throw)
                {
                    throw new InvalidOperationException("synthetic factory failure");
                }
                return _runtime;
            }
            finally
            {
                Zero(configuration);
                Zero(credential);
            }
        }
    }

    private sealed class FakeRuntime : IItemBootstrapRuntime
    {
        private readonly List<string>? _log;

        public FakeRuntime(List<string>? log = null)
        {
            _log = log;
        }

        public bool StartResult { get; set; } = true;
        public bool Stopped { get; set; }
        public bool ThrowOnDrain { get; set; }
        public Func<bool>? StartAction { get; set; }
        public Func<bool>? StopAction { get; set; }
        public int StartCalls { get; private set; }
        public int DrainCalls { get; private set; }
        public int StopCalls { get; private set; }

        public bool Start()
        {
            StartCalls++;
            _log?.Add("start");
            return StartAction?.Invoke() ?? StartResult;
        }

        public bool DrainFrame()
        {
            DrainCalls++;
            if (ThrowOnDrain)
            {
                throw new InvalidOperationException("synthetic drain failure");
            }
            return true;
        }

        public bool StopAndJoin()
        {
            StopCalls++;
            return StopAction?.Invoke() ?? Stopped;
        }

        public bool IsStopped => Stopped;
    }

    private static byte[] Filled(int length, byte value)
    {
        var result = new byte[length];
        Array.Fill(result, value);
        return result;
    }

    private static void Zero(byte[]? value)
    {
        if (value is not null)
        {
            CryptographicOperations.ZeroMemory(value);
        }
    }
}
