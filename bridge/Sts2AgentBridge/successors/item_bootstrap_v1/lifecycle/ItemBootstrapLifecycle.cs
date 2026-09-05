using System;
using System.Security.Cryptography;
using System.Threading;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal interface IItemBootstrapOperatorLease : IDisposable
{
    byte[]? ReadCredentialOnce();

    byte[]? TakeConfiguration();
}

internal interface IItemBootstrapFrameAttachment
{
    bool CanActivate { get; }

    bool TryDetach();
}

internal interface IItemBootstrapFrameConnector
{
    IItemBootstrapFrameAttachment? Attach(Action onFrame);
}

internal interface IItemBootstrapRuntime
{
    bool Start();

    bool DrainFrame();

    bool StopAndJoin();

    bool IsStopped { get; }
}

internal interface IItemBootstrapRuntimeFactory
{
    // Ownership of both arrays transfers at invocation, including failure paths.
    IItemBootstrapRuntime? Create(byte[] configuration, byte[] credential);
}

internal interface IItemBootstrapClock
{
    long Timestamp { get; }

    long Frequency { get; }
}

internal interface IItemBootstrapTimer : IDisposable
{
}

internal interface IItemBootstrapTimerFactory
{
    IItemBootstrapTimer Arm(TimeSpan dueTime, Action callback);
}

internal sealed class ItemBootstrapLifecycle
{
    internal const int PendingLifetimeSeconds = 5;

    private readonly object _gate = new();
    private readonly Func<IItemBootstrapOperatorLease?> _openEnabled;
    private readonly Func<bool> _verifyBuild;
    private readonly IItemBootstrapFrameConnector _frames;
    private readonly IItemBootstrapRuntimeFactory _runtimeFactory;
    private readonly IItemBootstrapClock _clock;
    private readonly IItemBootstrapTimerFactory _timers;

    private bool _initializationAttempted;
    private bool _initializationInProgress;
    private bool _startupInProgress;
    private bool _stopRequested;
    private int? _ownerThreadId;
    private long _deadline;
    private byte[]? _configuration;
    private byte[]? _credential;
    private IItemBootstrapTimer? _timer;
    private IItemBootstrapFrameAttachment? _attachment;
    private IItemBootstrapRuntime? _runtime;
    private bool _stopCallAttempted;
    private bool _stopCallInProgress;
    private bool _stopCallRetryRequired;

    internal ItemBootstrapLifecycle(
        Func<IItemBootstrapOperatorLease?> openEnabled,
        Func<bool> verifyBuild,
        IItemBootstrapFrameConnector frames,
        IItemBootstrapRuntimeFactory runtimeFactory,
        IItemBootstrapClock clock,
        IItemBootstrapTimerFactory timers)
    {
        _openEnabled = openEnabled ?? throw new ArgumentNullException(nameof(openEnabled));
        _verifyBuild = verifyBuild ?? throw new ArgumentNullException(nameof(verifyBuild));
        _frames = frames ?? throw new ArgumentNullException(nameof(frames));
        _runtimeFactory = runtimeFactory ?? throw new ArgumentNullException(nameof(runtimeFactory));
        _clock = clock ?? throw new ArgumentNullException(nameof(clock));
        _timers = timers ?? throw new ArgumentNullException(nameof(timers));
    }

    internal bool Initialize()
    {
        lock (_gate)
        {
            if (_initializationAttempted)
            {
                return false;
            }

            _initializationAttempted = true;
            if (_stopRequested)
            {
                return false;
            }
            _initializationInProgress = true;
        }

        IItemBootstrapOperatorLease? lease = null;
        byte[]? configuration = null;
        byte[]? credential = null;
        IItemBootstrapTimer? timer = null;
        IItemBootstrapFrameAttachment? attachment = null;
        try
        {
            lease = _openEnabled();
            if (lease is null || StopWasRequested() || !_verifyBuild() || StopWasRequested())
            {
                return FailInitialization(lease, configuration, credential, timer);
            }

            credential = lease.ReadCredentialOnce();
            if (credential is null)
            {
                return FailInitialization(lease, configuration, credential, timer);
            }

            if (StopWasRequested())
            {
                return FailInitialization(lease, configuration, credential, timer);
            }

            long now = _clock.Timestamp;
            long frequency = _clock.Frequency;
            if (frequency <= 0 || frequency > long.MaxValue / PendingLifetimeSeconds)
            {
                return FailInitialization(lease, configuration, credential, timer);
            }
            long lifetime = frequency * PendingLifetimeSeconds;
            if (now > long.MaxValue - lifetime)
            {
                return FailInitialization(lease, configuration, credential, timer);
            }
            long deadline = now + lifetime;

            configuration = lease.TakeConfiguration();
            if (configuration is null)
            {
                return FailInitialization(lease, configuration, credential, timer);
            }

            IItemBootstrapOperatorLease leaseToDispose = lease;
            lease = null;
            leaseToDispose.Dispose();

            bool stoppedBeforePublish;
            lock (_gate)
            {
                stoppedBeforePublish = _stopRequested;
                if (!stoppedBeforePublish)
                {
                    _configuration = configuration;
                    _credential = credential;
                    _deadline = deadline;
                    configuration = null;
                    credential = null;
                }
            }
            if (stoppedBeforePublish)
            {
                return FailInitialization(null, configuration, credential, null);
            }

            TimeSpan remaining = Remaining(deadline, _clock.Timestamp, frequency);
            timer = _timers.Arm(remaining, RequestStopFromSignal);
            bool stoppedBeforeTimerPublish;
            lock (_gate)
            {
                stoppedBeforeTimerPublish = _stopRequested;
                if (!stoppedBeforeTimerPublish)
                {
                    _timer = timer;
                    timer = null;
                }
            }
            if (stoppedBeforeTimerPublish)
            {
                if (timer is not null && !TryDispose(timer))
                {
                    lock (_gate)
                    {
                        _timer ??= timer;
                    }
                }
                timer = null;
                return FinishInitializationAfterStop();
            }

            attachment = _frames.Attach(OnFrame);
            if (attachment is null)
            {
                return FailInitialization(null, null, null, null);
            }

            bool canActivate;
            try
            {
                canActivate = attachment.CanActivate;
            }
            catch
            {
                canActivate = false;
            }

            bool accepted;
            lock (_gate)
            {
                _attachment = attachment;
                attachment = null;
                _initializationInProgress = false;
                accepted = canActivate && !_stopRequested;
            }
            if (!accepted)
            {
                RequestStop();
            }
            return accepted;
        }
        catch
        {
            return FailInitialization(lease, configuration, credential, timer, attachment);
        }
    }

    internal bool RequestStop()
    {
        byte[]? configuration;
        byte[]? credential;
        IItemBootstrapTimer? timer;
        IItemBootstrapRuntime? runtime;
        lock (_gate)
        {
            _stopRequested = true;
            configuration = _configuration;
            credential = _credential;
            timer = _timer;
            runtime = _runtime;
            _configuration = null;
            _credential = null;
            _timer = null;
        }

        Zero(configuration);
        Zero(credential);
        if (timer is not null && !TryDispose(timer))
        {
            lock (_gate)
            {
                _timer ??= timer;
            }
        }
        if (runtime is not null)
        {
            IssueRuntimeStop(runtime);
        }

        return IsFullyStopped;
    }

    internal bool IsFullyStopped
    {
        get
        {
            IItemBootstrapRuntime? runtime;
            lock (_gate)
            {
                if (!_stopRequested || _initializationInProgress || _startupInProgress ||
                    _configuration is not null || _credential is not null || _timer is not null ||
                    _attachment is not null)
                {
                    return false;
                }
                runtime = _runtime;
            }

            return runtime is null || IsRuntimeStopped(runtime);
        }
    }

    private void OnFrame()
    {
        int threadId = Environment.CurrentManagedThreadId;
        IItemBootstrapRuntime? runtimeToDrain = null;
        byte[]? configuration = null;
        byte[]? credential = null;
        IItemBootstrapTimer? timer = null;
        bool wrongThread = false;
        bool expired = false;

        lock (_gate)
        {
            if (_ownerThreadId is null)
            {
                _ownerThreadId = threadId;
            }
            else if (_ownerThreadId.Value != threadId)
            {
                wrongThread = true;
            }

            if (!wrongThread && !_initializationInProgress)
            {
                if (_stopRequested)
                {
                    // Owner-frame cleanup occurs below.
                }
                else if (_runtime is not null)
                {
                    runtimeToDrain = _runtime;
                }
                else if (!_startupInProgress)
                {
                    long now;
                    try
                    {
                        now = _clock.Timestamp;
                    }
                    catch
                    {
                        now = long.MaxValue;
                    }

                    if (_configuration is null || _credential is null || now >= _deadline)
                    {
                        expired = true;
                    }
                    else
                    {
                        _startupInProgress = true;
                        configuration = _configuration;
                        credential = _credential;
                        timer = _timer;
                        _configuration = null;
                        _credential = null;
                        _timer = null;
                    }
                }
            }
        }

        if (wrongThread)
        {
            RequestStop();
            return;
        }
        if (expired)
        {
            RequestStop();
            FinishStopOnOwnerFrame(threadId);
            return;
        }
        if (configuration is not null && credential is not null)
        {
            bool timerDisposed = TryDispose(timer);
            long now;
            try
            {
                now = _clock.Timestamp;
            }
            catch
            {
                now = long.MaxValue;
            }

            bool abort;
            lock (_gate)
            {
                abort = !timerDisposed || _stopRequested || now >= _deadline;
                if (abort)
                {
                    _stopRequested = true;
                    _startupInProgress = false;
                    if (!timerDisposed && timer is not null)
                    {
                        _timer ??= timer;
                    }
                }
                // When abort is false, this is the final factory-transfer commit.
                // A later stop races with the explicit startup participant.
            }
            if (abort)
            {
                Zero(configuration);
                Zero(credential);
                FinishStopOnOwnerFrame(threadId);
                return;
            }

            ActivateOnOwnerFrame(threadId, configuration, credential);
            return;
        }
        if (runtimeToDrain is not null)
        {
            bool shouldStop = false;
            try
            {
                runtimeToDrain.DrainFrame();
            }
            catch
            {
                shouldStop = true;
            }
            if (shouldStop)
            {
                RequestStop();
            }
        }

        FinishStopOnOwnerFrame(threadId);
    }

    private void ActivateOnOwnerFrame(int threadId, byte[] configuration, byte[] credential)
    {
        IItemBootstrapRuntime? runtime = null;
        try
        {
            runtime = _runtimeFactory.Create(configuration, credential);
        }
        catch
        {
            // Ownership transferred to the factory at invocation.
        }

        bool stopBeforeStart;
        lock (_gate)
        {
            _runtime = runtime;
            stopBeforeStart = _stopRequested || runtime is null;
            if (runtime is null)
            {
                _stopRequested = true;
            }
        }

        bool started = false;
        if (!stopBeforeStart && runtime is not null)
        {
            lock (_gate)
            {
                stopBeforeStart = _stopRequested;
            }
            if (!stopBeforeStart)
            {
                try
                {
                    started = runtime.Start();
                }
                catch
                {
                    started = false;
                }
            }
        }

        bool mustStop;
        lock (_gate)
        {
            if (!started)
            {
                _stopRequested = true;
            }
            mustStop = _stopRequested;
            _startupInProgress = false;
        }

        if (mustStop && runtime is not null)
        {
            IssueRuntimeStop(runtime);
        }

        FinishStopOnOwnerFrame(threadId);
    }

    private void FinishStopOnOwnerFrame(int threadId)
    {
        IItemBootstrapFrameAttachment? attachment;
        IItemBootstrapRuntime? runtime;
        IItemBootstrapTimer? timer;
        lock (_gate)
        {
            if (!_stopRequested || _ownerThreadId != threadId ||
                _initializationInProgress || _startupInProgress)
            {
                return;
            }
            runtime = _runtime;
            attachment = _attachment;
            timer = _timer;
            _timer = null;
        }

        if (timer is not null && !TryDispose(timer))
        {
            lock (_gate)
            {
                _timer ??= timer;
            }
            return;
        }
        if (runtime is not null)
        {
            bool retryStop;
            lock (_gate)
            {
                retryStop = _stopCallRetryRequired;
            }
            if (retryStop)
            {
                IssueRuntimeStop(runtime);
            }
        }

        if (runtime is not null && !IsRuntimeStopped(runtime))
        {
            return;
        }
        if (attachment is null)
        {
            return;
        }

        bool detached;
        try
        {
            detached = attachment.TryDetach();
        }
        catch
        {
            detached = false;
        }
        if (!detached)
        {
            return;
        }

        lock (_gate)
        {
            if (ReferenceEquals(_attachment, attachment))
            {
                _attachment = null;
            }
        }
    }

    private bool FailInitialization(
        IItemBootstrapOperatorLease? lease,
        byte[]? configuration,
        byte[]? credential,
        IItemBootstrapTimer? timer,
        IItemBootstrapFrameAttachment? attachment = null)
    {
        try
        {
            lease?.Dispose();
        }
        catch
        {
        }
        Zero(configuration);
        Zero(credential);
        IItemBootstrapTimer? failedTimer = timer is not null && !TryDispose(timer) ? timer : null;

        byte[]? ownedConfiguration;
        byte[]? ownedCredential;
        IItemBootstrapTimer? ownedTimer;
        lock (_gate)
        {
            _stopRequested = true;
            _initializationInProgress = false;
            if (attachment is not null)
            {
                _attachment = attachment;
            }
            ownedConfiguration = _configuration;
            ownedCredential = _credential;
            ownedTimer = _timer;
            _configuration = null;
            _credential = null;
            _timer = null;
        }
        Zero(ownedConfiguration);
        Zero(ownedCredential);
        if (ownedTimer is not null && !TryDispose(ownedTimer))
        {
            failedTimer ??= ownedTimer;
        }
        if (failedTimer is not null)
        {
            lock (_gate)
            {
                _timer ??= failedTimer;
            }
        }
        return false;
    }

    private bool FinishInitializationAfterStop()
    {
        byte[]? configuration;
        byte[]? credential;
        lock (_gate)
        {
            _initializationInProgress = false;
            configuration = _configuration;
            credential = _credential;
            _configuration = null;
            _credential = null;
        }
        Zero(configuration);
        Zero(credential);
        return false;
    }

    private void RequestStopFromSignal()
    {
        RequestStop();
    }

    private bool StopWasRequested()
    {
        lock (_gate)
        {
            return _stopRequested;
        }
    }

    private static TimeSpan Remaining(long deadline, long now, long frequency)
    {
        long ticks = deadline - now;
        if (ticks <= 0)
        {
            return TimeSpan.Zero;
        }
        double seconds = (double)ticks / frequency;
        return TimeSpan.FromSeconds(Math.Min(seconds, PendingLifetimeSeconds));
    }

    private static bool IsRuntimeStopped(IItemBootstrapRuntime runtime)
    {
        try
        {
            return runtime.IsStopped;
        }
        catch
        {
            return false;
        }
    }

    private void IssueRuntimeStop(IItemBootstrapRuntime runtime)
    {
        lock (_gate)
        {
            if (!ReferenceEquals(_runtime, runtime) || _stopCallInProgress ||
                (_stopCallAttempted && !_stopCallRetryRequired))
            {
                return;
            }
            _stopCallAttempted = true;
            _stopCallInProgress = true;
            _stopCallRetryRequired = false;
        }

        bool faulted = false;
        try
        {
            runtime.StopAndJoin();
        }
        catch
        {
            faulted = true;
        }
        finally
        {
            lock (_gate)
            {
                _stopCallInProgress = false;
                if (faulted)
                {
                    _stopCallRetryRequired = true;
                }
            }
        }
    }

    private static bool TryDispose(IDisposable? value)
    {
        try
        {
            value?.Dispose();
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static void Zero(byte[]? value)
    {
        if (value is not null)
        {
            CryptographicOperations.ZeroMemory(value);
        }
    }
}
