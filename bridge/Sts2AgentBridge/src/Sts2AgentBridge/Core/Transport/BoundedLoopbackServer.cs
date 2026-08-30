using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Hosting;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Core.Transport;

public sealed class BoundedLoopbackServer : IBridgeListener
{
    private static readonly MonotonicTokenBucket ProductionPreAuthenticationBucket =
        new(
            LiveProbeLimits.PreAuthenticationRefillPerSecond,
            LiveProbeLimits.PreAuthenticationBurst,
            StopwatchMonotonicClock.Instance);

    private static readonly MonotonicTokenBucket ProductionAuthenticatedBucket =
        new(
            LiveProbeLimits.AuthenticatedRefillPerSecond,
            LiveProbeLimits.AuthenticatedBurst,
            StopwatchMonotonicClock.Instance);

    private readonly object _lifecycleGate = new();
    private readonly object _workerGate = new();
    private readonly CancellationTokenSource _stopSource = new();
    private readonly SemaphoreSlim _handlerSlots = new(
        LiveProbeLimits.MaximumConcurrentConnections,
        LiveProbeLimits.MaximumConcurrentConnections);
    private readonly List<Task> _workers = new();
    private readonly MonotonicTokenBucket _preAuthenticationBucket;
    private readonly ProbeRequestProcessor _processor;
#if STS2_AGENT_BRIDGE_TEST_SEAM
    private readonly TcpListener? _testListener;
#endif
    private Task? _acceptTask;
    private bool _started;
    private bool _disposed;
    private bool _infrastructureDisposed;

    public BoundedLoopbackServer(
        ProbeMode mode,
        string processCorrelationId,
        FixedTimeAuthenticator authenticator,
        BoundedFrameWorkQueue? frameQueue,
        IPublicScreenService? publicScreenService,
        IPublicCombatDecisionService? publicCombatDecisionService = null,
        IPublicCombatActionService? publicCombatActionService = null,
        IPublicRewardDecisionService? publicRewardDecisionService = null,
        IPublicRewardActionService? publicRewardActionService = null,
        IPublicMapDecisionService? publicMapDecisionService = null,
        IPublicMapActionService? publicMapActionService = null,
        IPublicRoomDecisionService? publicRoomDecisionService = null,
        IPublicRoomActionService? publicRoomActionService = null)
        : this(
            mode,
            processCorrelationId,
            authenticator,
            frameQueue,
            publicScreenService,
            ProductionPreAuthenticationBucket,
            ProductionAuthenticatedBucket,
            publicCombatDecisionService,
            publicCombatActionService,
            publicRewardDecisionService,
            publicRewardActionService,
            publicMapDecisionService,
            publicMapActionService,
            publicRoomDecisionService,
            publicRoomActionService)
    {
    }

    internal BoundedLoopbackServer(
        ProbeMode mode,
        string processCorrelationId,
        FixedTimeAuthenticator authenticator,
        BoundedFrameWorkQueue? frameQueue,
        IPublicScreenService? publicScreenService,
        IMonotonicClock preAuthenticationClock,
        IMonotonicClock authenticatedClock,
        IPublicCombatDecisionService? publicCombatDecisionService = null,
        IPublicCombatActionService? publicCombatActionService = null,
        IPublicRewardDecisionService? publicRewardDecisionService = null,
        IPublicRewardActionService? publicRewardActionService = null,
        IPublicMapDecisionService? publicMapDecisionService = null,
        IPublicMapActionService? publicMapActionService = null,
        IPublicRoomDecisionService? publicRoomDecisionService = null,
        IPublicRoomActionService? publicRoomActionService = null)
        : this(
            mode,
            processCorrelationId,
            authenticator,
            frameQueue,
            publicScreenService,
            new MonotonicTokenBucket(
                LiveProbeLimits.PreAuthenticationRefillPerSecond,
                LiveProbeLimits.PreAuthenticationBurst,
                preAuthenticationClock),
            new MonotonicTokenBucket(
                LiveProbeLimits.AuthenticatedRefillPerSecond,
                LiveProbeLimits.AuthenticatedBurst,
            authenticatedClock),
            publicCombatDecisionService,
            publicCombatActionService,
            publicRewardDecisionService,
            publicRewardActionService,
            publicMapDecisionService,
            publicMapActionService,
            publicRoomDecisionService,
            publicRoomActionService)
    {
    }

#if STS2_AGENT_BRIDGE_TEST_SEAM
    internal BoundedLoopbackServer(
        ProbeMode mode,
        string processCorrelationId,
        FixedTimeAuthenticator authenticator,
        BoundedFrameWorkQueue? frameQueue,
        IPublicScreenService? publicScreenService,
        TcpListener testListener,
        IMonotonicClock preAuthenticationClock,
        IMonotonicClock authenticatedClock,
        IPublicCombatDecisionService? publicCombatDecisionService = null,
        IPublicCombatActionService? publicCombatActionService = null,
        IPublicRewardDecisionService? publicRewardDecisionService = null,
        IPublicRewardActionService? publicRewardActionService = null,
        IPublicMapDecisionService? publicMapDecisionService = null,
        IPublicMapActionService? publicMapActionService = null,
        IPublicRoomDecisionService? publicRoomDecisionService = null,
        IPublicRoomActionService? publicRoomActionService = null)
        : this(
            mode,
            processCorrelationId,
            authenticator,
            frameQueue,
            publicScreenService,
            new MonotonicTokenBucket(
                LiveProbeLimits.PreAuthenticationRefillPerSecond,
                LiveProbeLimits.PreAuthenticationBurst,
                preAuthenticationClock),
            new MonotonicTokenBucket(
                LiveProbeLimits.AuthenticatedRefillPerSecond,
                LiveProbeLimits.AuthenticatedBurst,
            authenticatedClock),
            publicCombatDecisionService,
            publicCombatActionService,
            publicRewardDecisionService,
            publicRewardActionService,
            publicMapDecisionService,
            publicMapActionService,
            publicRoomDecisionService,
            publicRoomActionService)
    {
        _testListener = testListener ?? throw new ArgumentNullException(nameof(testListener));
    }
#endif

    private BoundedLoopbackServer(
        ProbeMode mode,
        string processCorrelationId,
        FixedTimeAuthenticator authenticator,
        BoundedFrameWorkQueue? frameQueue,
        IPublicScreenService? publicScreenService,
        MonotonicTokenBucket preAuthenticationBucket,
        MonotonicTokenBucket authenticatedBucket,
        IPublicCombatDecisionService? publicCombatDecisionService,
        IPublicCombatActionService? publicCombatActionService,
        IPublicRewardDecisionService? publicRewardDecisionService,
        IPublicRewardActionService? publicRewardActionService,
        IPublicMapDecisionService? publicMapDecisionService,
        IPublicMapActionService? publicMapActionService,
        IPublicRoomDecisionService? publicRoomDecisionService,
        IPublicRoomActionService? publicRoomActionService)
    {
        _preAuthenticationBucket = preAuthenticationBucket ??
            throw new ArgumentNullException(nameof(preAuthenticationBucket));
        _processor = new ProbeRequestProcessor(
            mode,
            processCorrelationId,
            authenticator,
            frameQueue,
            publicScreenService,
            authenticatedBucket,
            publicCombatDecisionService,
            publicCombatActionService,
            publicRewardDecisionService,
            publicRewardActionService,
            publicMapDecisionService,
            publicMapActionService,
            publicRoomDecisionService,
            publicRoomActionService);
    }

    public void Start()
    {
        lock (_lifecycleGate)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            if (_started)
            {
                throw new InvalidOperationException("The listener has already been started.");
            }

            if (_stopSource.IsCancellationRequested)
            {
                throw new InvalidOperationException("The listener has already been stopped.");
            }

            Task acceptTask = AcceptLoopAsync(_stopSource.Token);
            if (acceptTask.IsCompleted)
            {
                acceptTask.GetAwaiter().GetResult();
            }

            _acceptTask = acceptTask;
            _started = true;
        }
    }

    public void StopAccepting()
    {
        lock (_lifecycleGate)
        {
            if (!_disposed)
            {
                _stopSource.Cancel();
            }
        }
    }

    public bool StopAndJoin(TimeSpan timeout)
    {
        if (timeout < TimeSpan.Zero && timeout != Timeout.InfiniteTimeSpan)
        {
            throw new ArgumentOutOfRangeException(nameof(timeout));
        }

        StopAccepting();
        Task? acceptTask;
        lock (_lifecycleGate)
        {
            acceptTask = _acceptTask;
        }

        if (acceptTask is null)
        {
            return true;
        }

        try
        {
            return acceptTask.Wait(timeout);
        }
        catch (AggregateException)
        {
            return acceptTask.IsCompleted;
        }
    }

    public void Dispose()
    {
        bool canDisposeInfrastructure;
        lock (_lifecycleGate)
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            _stopSource.Cancel();
            canDisposeInfrastructure = _acceptTask is null || _acceptTask.IsCompleted;
        }

        if (canDisposeInfrastructure)
        {
            DisposeInfrastructure();
        }
    }

    internal async Task AcceptLoopAsync(CancellationToken cancellationToken)
    {
#if STS2_AGENT_BRIDGE_TEST_SEAM
        TcpListener listener = _testListener ??
            new TcpListener(IPAddress.Loopback, LiveProbeLimits.ListenerPort);
#else
        var listener = new TcpListener(IPAddress.Loopback, LiveProbeLimits.ListenerPort);
#endif
        try
        {
            listener.Start(LiveProbeLimits.ListenerBacklog);
            while (!cancellationToken.IsCancellationRequested)
            {
                Socket acceptedSocket;
                try
                {
                    acceptedSocket = await listener.AcceptSocketAsync(cancellationToken).ConfigureAwait(false);
                }
                catch when (cancellationToken.IsCancellationRequested)
                {
                    break;
                }

                if (!TryAdmitAcceptedConnection())
                {
                    acceptedSocket.Dispose();
                    continue;
                }

                Task worker = HandleAcceptedSocketAsync(acceptedSocket, cancellationToken);
                TrackWorker(worker);
            }
        }
        finally
        {
            listener.Stop();
            Task[] workers = SnapshotWorkers();
            if (workers.Length != 0)
            {
                try
                {
                    await Task.WhenAll(workers).ConfigureAwait(false);
                }
                catch
                {
                }
            }

            DisposeInfrastructure();
        }
    }

    internal async Task HandleAcceptedSocketAsync(
        Socket socket,
        CancellationToken cancellationToken)
    {
        if (!_handlerSlots.Wait(0))
        {
            socket.Dispose();
            return;
        }

        byte[]? requestBuffer = null;
        try
        {
            using var lifetimeSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            lifetimeSource.CancelAfter(LiveProbeLimits.TotalConnectionLifetimeMilliseconds);
            CancellationToken lifetimeToken = lifetimeSource.Token;

            ReceivedHead received = await ReceiveBoundedHeadAsync(socket, lifetimeToken).ConfigureAwait(false);
            requestBuffer = received.Buffer;
            ProbeProcessingResult processing;
            if (received.Status == ReceivedHeadStatus.PayloadTooLarge)
            {
                string correlationId = CorrelationIdGenerator.Create();
                processing = ProbeProcessingResult.Respond(
                    CanonicalProbeEncoder.EncodeErrorResponse(
                        ProbeErrorKind.PayloadTooLarge,
                        correlationId));
            }
            else if (received.Status != ReceivedHeadStatus.Complete || requestBuffer is null)
            {
                return;
            }
            else
            {
                processing = _processor.Process(requestBuffer.AsSpan(0, received.Length));
            }

            if (processing.ShouldRespond)
            {
                await SendAllAsync(socket, processing.Response, lifetimeToken).ConfigureAwait(false);
            }
        }
        catch
        {
        }
        finally
        {
            if (requestBuffer is not null)
            {
                CryptographicOperations.ZeroMemory(requestBuffer);
            }

            try
            {
                socket.Shutdown(SocketShutdown.Both);
            }
            catch
            {
            }

            socket.Dispose();
            _handlerSlots.Release();
        }
    }

    internal async Task<ReceivedHead> ReceiveBoundedHeadAsync(
        Socket socket,
        CancellationToken cancellationToken)
    {
        byte[] buffer = new byte[LiveProbeLimits.RequestHeadBufferBytes];
        bool transferOwnership = false;
        try
        {
            using var headerSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            headerSource.CancelAfter(LiveProbeLimits.HeaderReadTimeoutMilliseconds);
            int total = 0;
            while (total < buffer.Length)
            {
                int received = await socket.ReceiveAsync(
                        buffer.AsMemory(total),
                        SocketFlags.None,
                        headerSource.Token)
                    .ConfigureAwait(false);
                if (received == 0)
                {
                    return ReceivedHead.Silent();
                }

                total += received;
                int terminatorOffset = ProbeRequestParser.FindHeaderTerminator(buffer.AsSpan(0, total));
                if (terminatorOffset >= 0)
                {
                    int completeLength = terminatorOffset + 4;
                    if (completeLength != total)
                    {
                        return ReceivedHead.Silent();
                    }

                    if (completeLength > LiveProbeLimits.MaximumRequestHeadBytes)
                    {
                        return ReceivedHead.TooLarge();
                    }

                    transferOwnership = true;
                    return ReceivedHead.Complete(buffer, completeLength);
                }
            }

            return ReceivedHead.Silent();
        }
        catch
        {
            return ReceivedHead.Silent();
        }
        finally
        {
            if (!transferOwnership)
            {
                CryptographicOperations.ZeroMemory(buffer);
            }
        }
    }

    internal async Task SendAllAsync(
        Socket socket,
        ReadOnlyMemory<byte> response,
        CancellationToken cancellationToken)
    {
        using var responseSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        responseSource.CancelAfter(LiveProbeLimits.ResponseWriteTimeoutMilliseconds);
        int sent = 0;
        while (sent < response.Length)
        {
            int written = await socket.SendAsync(
                    response[sent..],
                    SocketFlags.None,
                    responseSource.Token)
                .ConfigureAwait(false);
            if (written <= 0)
            {
                throw new InvalidOperationException("Socket closed before the bounded response completed.");
            }

            sent += written;
        }
    }

    internal bool TryAdmitAcceptedConnection()
    {
        return _preAuthenticationBucket.TryConsume();
    }

    private void TrackWorker(Task worker)
    {
        lock (_workerGate)
        {
            for (int index = _workers.Count - 1; index >= 0; index--)
            {
                if (_workers[index].IsCompleted)
                {
                    _workers.RemoveAt(index);
                }
            }

            if (!worker.IsCompleted)
            {
                _workers.Add(worker);
            }
        }
    }

    private Task[] SnapshotWorkers()
    {
        lock (_workerGate)
        {
            return _workers.ToArray();
        }
    }

    private void DisposeInfrastructure()
    {
        lock (_lifecycleGate)
        {
            if (!_disposed || _infrastructureDisposed)
            {
                return;
            }

            _infrastructureDisposed = true;
        }

        _stopSource.Dispose();
        _handlerSlots.Dispose();
    }
}

internal enum ReceivedHeadStatus
{
    Complete = 1,
    PayloadTooLarge = 2,
    SilentClose = 3,
}

internal readonly record struct ReceivedHead(
    ReceivedHeadStatus Status,
    byte[]? Buffer,
    int Length)
{
    public static ReceivedHead Complete(byte[] buffer, int length)
    {
        return new ReceivedHead(ReceivedHeadStatus.Complete, buffer, length);
    }

    public static ReceivedHead TooLarge()
    {
        return new ReceivedHead(ReceivedHeadStatus.PayloadTooLarge, null, 0);
    }

    public static ReceivedHead Silent()
    {
        return new ReceivedHead(ReceivedHeadStatus.SilentClose, null, 0);
    }
}
