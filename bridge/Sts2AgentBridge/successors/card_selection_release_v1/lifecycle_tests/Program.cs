using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal static class Program
{
    private static int _checks;
    internal static int Main(string[] arguments)
    {
        if (arguments.Length != 0) return 2;
        try
        {
            Run(MissingAndBuildFailure);
            Run(ActivationAndCleanupOrder);
            Run(OneShotAndStopBeforeInitialize);
            Run(ExactDeadlineAndDelayedSignal);
            Run(TimerStopRace);
            Run(FactoryFailureZeroes);
            Run(StartFailureCleansOwnerService);
            Run(TerminalRuntimeStops);
            Run(FalseJoinPollsWithoutRetry);
            Run(StopFaultRetries);
            Run(ServiceDisposeFailureRetained);
            Run(WrongThreadDefersOwnerCleanup);
            Run(ConfiguredPolicyAcceptsOnlySelected);
            Run(ConfiguredPolicyForwardsFixedAndCleans);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"card_selection_v1_bootstrap\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch
        {
            Console.Error.WriteLine("card_selection_v1_bootstrap_tests_failed");
            return 1;
        }
    }

    private static void Run(Action action)
    {
        try { action(); _checks++; }
        catch { throw new InvalidOperationException(action.Method.Name); }
    }
    private static void Check(bool value) { if (!value) throw new InvalidOperationException(); }

    private static void MissingAndBuildFailure()
    {
        var missing = new Fixture(null);
        Check(!missing.Lifecycle.Initialize() && missing.BuildCalls == 0 && missing.Lifecycle.IsFullyStopped);
        var lease = FakeLease.Enabled(); byte[] config = lease.Config!; byte[] credential = lease.Credential!;
        var failed = new Fixture(lease) { BuildResult = false };
        Check(!failed.Lifecycle.Initialize() && lease.CredentialReads == 0 && failed.Frames.AttachCalls == 0);
        Check(config.All(x => x == 0) && credential.All(x => x == 0));
    }

    private static void ActivationAndCleanupOrder()
    {
        var log = new List<string>(); var runtime = new FakeRuntime(log);
        var fixture = new Fixture(FakeLease.Enabled(log), log, runtime);
        Check(fixture.Lifecycle.Initialize());
        Check(log.SequenceEqual(new[] { "open", "build", "credential", "configuration", "lease_dispose", "attach" }));
        fixture.Frames.Fire();
        Check(log.TakeLast(2).SequenceEqual(new[] { "factory", "start" }));
        Check(!fixture.Lifecycle.RequestStop() && runtime.StopCalls == 1 && runtime.DisposeCalls == 0);
        fixture.Frames.Fire();
        Check(log.TakeLast(3).SequenceEqual(new[] { "stop", "service_dispose", "detach" }));
        Check(fixture.Lifecycle.IsFullyStopped);
    }

    private static void OneShotAndStopBeforeInitialize()
    {
        var fixture = new Fixture(FakeLease.Enabled());
        Check(fixture.Lifecycle.Initialize() && !fixture.Lifecycle.Initialize() && fixture.OpenCalls == 1);
        fixture.Lifecycle.RequestStop(); fixture.Frames.Fire();
        var stopped = new Fixture(FakeLease.Enabled());
        Check(stopped.Lifecycle.RequestStop() && !stopped.Lifecycle.Initialize() && stopped.OpenCalls == 0);
    }

    private static void ExactDeadlineAndDelayedSignal()
    {
        var lease = FakeLease.Enabled(); byte[] config = lease.Config!; byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease); Check(fixture.Lifecycle.Initialize());
        fixture.Clock.Now = 5_000; fixture.Frames.Fire();
        Check(fixture.Factory.Calls == 0 && config.All(x => x == 0) && credential.All(x => x == 0));
        Check(fixture.Frames.Attachment.DetachCalls == 1 && fixture.Lifecycle.IsFullyStopped);
        fixture.Timers.Last!.Fire(); Check(fixture.Factory.Calls == 0);
    }

    private static void TimerStopRace()
    {
        var lease = FakeLease.Enabled(); byte[] config = lease.Config!; byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease); Check(fixture.Lifecycle.Initialize());
        fixture.Timers.Last!.OnDispose = () => fixture.Lifecycle.RequestStop();
        fixture.Frames.Fire();
        Check(fixture.Factory.Calls == 0 && config.All(x => x == 0) && credential.All(x => x == 0));
        Check(fixture.Frames.Attachment.DetachCalls == 1);
    }

    private static void FactoryFailureZeroes()
    {
        var lease = FakeLease.Enabled(); byte[] config = lease.Config!; byte[] credential = lease.Credential!;
        var fixture = new Fixture(lease); fixture.Factory.Throw = true;
        Check(fixture.Lifecycle.Initialize()); fixture.Frames.Fire();
        Check(fixture.Factory.Calls == 1 && config.All(x => x == 0) && credential.All(x => x == 0));
        Check(fixture.Frames.Attachment.DetachCalls == 1);
    }

    private static void StartFailureCleansOwnerService()
    {
        var runtime = new FakeRuntime { StartResult = false };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize()); fixture.Frames.Fire();
        Check(runtime.StartCalls == 1 && runtime.StopCalls == 1 && runtime.DisposeCalls == 1);
        Check(runtime.ServiceDisposed && fixture.Frames.Attachment.DetachCalls == 1);
    }

    private static void TerminalRuntimeStops()
    {
        var runtime = new FakeRuntime(); var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize()); fixture.Frames.Fire(); runtime.Terminal = true; fixture.Frames.Fire();
        Check(runtime.DrainCalls == 1 && runtime.StopCalls == 1 && runtime.DisposeCalls == 1);
        Check(fixture.Frames.Attachment.DetachCalls == 1 && fixture.Lifecycle.IsFullyStopped);
    }

    private static void FalseJoinPollsWithoutRetry()
    {
        var runtime = new FakeRuntime { SettleOnStop = false };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize()); fixture.Frames.Fire(); fixture.Lifecycle.RequestStop();
        fixture.Frames.Fire(); fixture.Frames.Fire();
        Check(runtime.StopCalls == 1 && runtime.DisposeCalls == 0 && fixture.Frames.Attachment.DetachCalls == 0);
        runtime.TransportStoppedValue = true; fixture.Frames.Fire();
        Check(runtime.DisposeCalls == 1 && fixture.Frames.Attachment.DetachCalls == 1);
    }

    private static void StopFaultRetries()
    {
        var runtime = new FakeRuntime { StopFaults = 1 };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize()); fixture.Frames.Fire(); fixture.Lifecycle.RequestStop();
        Check(runtime.StopCalls == 1 && fixture.Frames.Attachment.DetachCalls == 0);
        fixture.Frames.Fire();
        Check(runtime.StopCalls == 2 && runtime.DisposeCalls == 1 && fixture.Frames.Attachment.DetachCalls == 1);
    }

    private static void ServiceDisposeFailureRetained()
    {
        var runtime = new FakeRuntime { DisposeFailures = 1 };
        var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize()); fixture.Frames.Fire(); fixture.Lifecycle.RequestStop(); fixture.Frames.Fire();
        Check(runtime.DisposeCalls == 1 && !runtime.ServiceDisposed && fixture.Frames.Attachment.DetachCalls == 0);
        Check(!fixture.Lifecycle.IsFullyStopped); fixture.Frames.Fire();
        Check(runtime.DisposeCalls == 2 && fixture.Frames.Attachment.DetachCalls == 1 && fixture.Lifecycle.IsFullyStopped);
    }

    private static void WrongThreadDefersOwnerCleanup()
    {
        var runtime = new FakeRuntime(); var fixture = new Fixture(FakeLease.Enabled(), runtime: runtime);
        Check(fixture.Lifecycle.Initialize()); fixture.Frames.Fire();
        Task.Run(fixture.Frames.Fire).GetAwaiter().GetResult();
        Check(runtime.StopCalls == 1 && runtime.DisposeCalls == 0 && fixture.Frames.Attachment.DetachCalls == 0);
        fixture.Frames.Fire();
        Check(runtime.DisposeCalls == 1 && fixture.Frames.Attachment.DetachCalls == 1);
    }

    private static void ConfiguredPolicyAcceptsOnlySelected()
    {
        var cheeseInner = new FakeParentAdapter(Available(CheesePolicy), Available(SmithPolicy));
        var cheese = new ConfiguredCardSelectionParentV1NativeAdapter(
            CardSelectionReleaseSelection.Cheese, cheeseInner);
        Check(ReferenceEquals(cheese.CaptureSurface().Policy, CheesePolicy));
        bool rejected = false;
        try { _ = cheese.CaptureSurface(); }
        catch (InvalidOperationException) { rejected = true; }
        Check(rejected && cheeseInner.CaptureCalls == 2);

        var smithInner = new FakeParentAdapter(Available(SmithPolicy), Available(CheesePolicy));
        var smith = new ConfiguredCardSelectionParentV1NativeAdapter(
            CardSelectionReleaseSelection.Smith, smithInner);
        Check(ReferenceEquals(smith.CaptureSurface().Policy, SmithPolicy));
        rejected = false;
        try { _ = smith.CaptureSurface(); }
        catch (InvalidOperationException) { rejected = true; }
        Check(rejected && smithInner.CaptureCalls == 2);
    }

    private static void ConfiguredPolicyForwardsFixedAndCleans()
    {
        CardSelectionParentV1SurfaceCapture missing = Fixed(
            CardSelectionParentV1SurfaceStatus.Missing, SmithPolicy);
        CardSelectionParentV1SurfaceCapture unsupported = Fixed(
            CardSelectionParentV1SurfaceStatus.Unsupported, SmithPolicy);
        var inner = new FakeParentAdapter(missing, unsupported, null!);
        var wrapper = new ConfiguredCardSelectionParentV1NativeAdapter(
            CardSelectionReleaseSelection.Cheese, inner);
        Check(ReferenceEquals(wrapper.CaptureSurface(), missing));
        Check(ReferenceEquals(wrapper.CaptureSurface(), unsupported));
        bool rejectedNull = false;
        try { _ = wrapper.CaptureSurface(); }
        catch (InvalidOperationException) { rejectedNull = true; }
        wrapper.Dispose();
        Check(rejectedNull && inner.DisposeCalls == 1);

        bool rejectedSelection = false;
        try
        {
            _ = new ConfiguredCardSelectionParentV1NativeAdapter(
                (CardSelectionReleaseSelection)0, new FakeParentAdapter(missing));
        }
        catch (ArgumentOutOfRangeException) { rejectedSelection = true; }
        Check(rejectedSelection);
    }

    private static CardSelectionParentV1SurfaceCapture Available(
        CardSelectionParentV1Policy policy) => new(
            CardSelectionParentV1SurfaceStatus.Available,
            CardSelectionParentV1Phase.Initial, policy,
            new object(), new object(), new object(), new object(), new object(), new object(),
            new string('a', 64), true, false, false, false,
            false, false, false, false, null, null, null, null);

    private static CardSelectionParentV1SurfaceCapture Fixed(
        CardSelectionParentV1SurfaceStatus status,
        CardSelectionParentV1Policy policy) => new(
            status, CardSelectionParentV1Phase.Transient, policy,
            null, null, null, null, null, null, string.Empty,
            false, false, false, false, false, false, false, false,
            null, null, null, null);

    private static readonly CardSelectionParentV1Policy CheesePolicy = new(
        CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo,
        CardSelectionV1ParentKind.Event,
        CardSelectionParentV1Limits.CheeseGorgeStableKey,
        0, CardSelectionV1Operation.Add, 2, 2,
        CardSelectionV1CommitMode.AutoAtMax, 8);

    private static readonly CardSelectionParentV1Policy SmithPolicy = new(
        CardSelectionParentV1PolicyKind.RestSmithUpgradeOne,
        CardSelectionV1ParentKind.Rest,
        CardSelectionParentV1Limits.SmithStableKey,
        1, CardSelectionV1Operation.Upgrade, 1, 1,
        CardSelectionV1CommitMode.PreviewConfirm, 3);

    private sealed class FakeParentAdapter : ICardSelectionParentV1NativeAdapter
    {
        private readonly CardSelectionParentV1SurfaceCapture[] _captures;
        internal int CaptureCalls;
        internal int DisposeCalls;
        internal FakeParentAdapter(params CardSelectionParentV1SurfaceCapture[] captures) =>
            _captures = captures;
        public CardSelectionParentV1SurfaceCapture CaptureSurface()
        {
            int index = CaptureCalls++;
            return index < _captures.Length ? _captures[index] : _captures[^1];
        }
        public void Dispose() => DisposeCalls++;
    }

    private sealed class Fixture
    {
        private readonly FakeLease? _lease; internal readonly FakeFrames Frames; internal readonly FakeFactory Factory;
        internal readonly FakeClock Clock = new(); internal readonly FakeTimers Timers = new(); internal int OpenCalls, BuildCalls;
        internal bool BuildResult = true; internal CardSelectionBootstrapLifecycle Lifecycle { get; }
        internal Fixture(FakeLease? lease, List<string>? log = null, FakeRuntime? runtime = null)
        {
            _lease = lease; Frames = new FakeFrames(log); Factory = new FakeFactory(runtime ?? new FakeRuntime(log), log);
            Lifecycle = new CardSelectionBootstrapLifecycle(Open, Build, Frames, Factory, Clock, Timers);
        }
        private ICardSelectionBootstrapOperatorLease? Open() { OpenCalls++; _lease?.Log?.Add("open"); return _lease; }
        private bool Build() { BuildCalls++; _lease?.Log?.Add("build"); return BuildResult; }
    }

    private sealed class FakeLease : ICardSelectionBootstrapOperatorLease
    {
        internal byte[]? Config = new byte[] { 1, 2 }; internal byte[]? Credential = new byte[] { 3, 4 };
        internal readonly List<string>? Log; internal int CredentialReads;
        private FakeLease(List<string>? log) { Log = log; }
        internal static FakeLease Enabled(List<string>? log = null) => new(log);
        public byte[]? ReadCredentialOnce() { CredentialReads++; Log?.Add("credential"); byte[]? v=Credential; Credential=null; return v; }
        public byte[]? TakeConfiguration() { Log?.Add("configuration"); byte[]? v=Config; Config=null; return v; }
        public void Dispose() { Log?.Add("lease_dispose"); if(Config is not null)Array.Clear(Config); if(Credential is not null)Array.Clear(Credential); Config=null; Credential=null; }
    }

    private sealed class FakeClock : ICardSelectionBootstrapClock { internal long Now; public long Timestamp => Now; public long Frequency => 1000; }
    private sealed class FakeTimers : ICardSelectionBootstrapTimerFactory
    {
        internal FakeTimer? Last; public ICardSelectionBootstrapTimer Arm(TimeSpan due, Action callback) { Last=new FakeTimer(callback); return Last; }
    }
    private sealed class FakeTimer : ICardSelectionBootstrapTimer
    {
        private readonly Action _callback; private int _fired; internal Action? OnDispose;
        internal FakeTimer(Action callback) { _callback=callback; }
        internal void Fire() { if(Interlocked.Exchange(ref _fired,1)==0)_callback(); }
        public void Dispose() => OnDispose?.Invoke();
    }

    private sealed class FakeFrames : ICardSelectionBootstrapFrameConnector
    {
        private Action? _frame; private readonly List<string>? _log; internal int AttachCalls; internal FakeAttachment Attachment;
        internal FakeFrames(List<string>? log) { _log=log; Attachment=new FakeAttachment(log); }
        public ICardSelectionBootstrapFrameAttachment? Attach(Action onFrame) { AttachCalls++;_log?.Add("attach");_frame=onFrame;return Attachment; }
        internal void Fire() => _frame!();
    }
    private sealed class FakeAttachment : ICardSelectionBootstrapFrameAttachment
    {
        private readonly List<string>? _log; internal int DetachCalls; internal FakeAttachment(List<string>? log){_log=log;}
        public bool CanActivate => true;
        public bool TryDetach(){DetachCalls++;_log?.Add("detach");return true;}
    }

    private sealed class FakeFactory : ICardSelectionBootstrapRuntimeFactory
    {
        private readonly FakeRuntime _runtime; private readonly List<string>? _log; internal int Calls; internal bool Throw;
        internal FakeFactory(FakeRuntime runtime,List<string>? log){_runtime=runtime;_log=log;}
        public ICardSelectionBootstrapRuntime? Create(byte[] configuration,byte[] credential)
        {
            Calls++;_log?.Add("factory");Array.Clear(configuration);Array.Clear(credential);
            if(Throw)throw new InvalidOperationException();return _runtime;
        }
    }
    private sealed class FakeRuntime : ICardSelectionBootstrapRuntime
    {
        private readonly List<string>? _log; internal bool StartResult=true, SettleOnStop=true, Terminal;
        internal bool TransportStoppedValue, ServiceDisposedValue; internal int StopFaults, DisposeFailures;
        internal int StartCalls,DrainCalls,StopCalls,DisposeCalls;
        internal FakeRuntime(List<string>? log=null){_log=log;}
        public bool Start(){StartCalls++;_log?.Add("start");return StartResult;}
        public bool DrainFrame(){DrainCalls++;return true;}
        public bool StopTransportAndJoin(){StopCalls++;_log?.Add("stop");if(StopFaults-->0)throw new InvalidOperationException();if(SettleOnStop)TransportStoppedValue=true;return TransportStoppedValue;}
        public bool TransportStopped=>TransportStoppedValue;
        public bool DisposeServiceOnOwnerFrame(){DisposeCalls++;_log?.Add("service_dispose");if(DisposeFailures-->0)return false;ServiceDisposedValue=true;return true;}
        public bool ServiceDisposed=>ServiceDisposedValue;
        public bool IsTerminalOrStopping=>Terminal;
    }
}
