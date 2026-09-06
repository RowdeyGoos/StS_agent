using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Transport;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

public sealed class ShopDiagnosticTransportRuntime : IDisposable
{
    private static readonly TimeSpan JoinTimeout =
        TimeSpan.FromMilliseconds(ShopDiagnosticTransportLimits.ShutdownJoinMilliseconds);

    private readonly object _gate = new();
    private readonly FixedTimeAuthenticator _authenticator;
    private IShopDiagnosticService? _service;
    private readonly OwnedByteFrameQueue _frameQueue;
    private readonly MonotonicTokenBucket _preAuthenticationBucket;
    private readonly MonotonicTokenBucket _authenticatedBucket;
    private readonly SemaphoreSlim _handlerSlots = new(
        ShopDiagnosticTransportLimits.MaximumHandlers,
        ShopDiagnosticTransportLimits.MaximumHandlers);
    private readonly CancellationTokenSource _stopSource = new();
    private readonly ManualResetEventSlim _transportSettled = new(false);
    private readonly HashSet<Socket> _activeSockets = new();
    private readonly HashSet<Task> _workers = new();
    private readonly int _ownerThreadId;
    private TcpListener? _listener;
    private Task? _acceptTask;
    private bool _acceptCompleted = true;
    private bool _startAttempted;
    private bool _startInProgress;
    private bool _started;
    private bool _stopping;
    private bool _transportDispositionStarted;
    private bool _transportStopped;
    private bool _settledDisposed;
    private bool _serviceDisposeAttempted;
    private bool _serviceDisposed;
    private int _joinWaiters;
    private int _observationReserved;
    private int _exchangeInFlight;
    private int _terminalRequested;
    private int _terminalPublished;

    private ShopDiagnosticTransportRuntime(FixedTimeAuthenticator authenticator)
    {
        _authenticator = authenticator;
        _frameQueue = new OwnedByteFrameQueue(OnComponentStateChanged);
        _preAuthenticationBucket = new MonotonicTokenBucket(
            32.0, 16.0, StopwatchMonotonicClock.Instance);
        _authenticatedBucket = new MonotonicTokenBucket(
            20.0, 16.0, StopwatchMonotonicClock.Instance);
        _ownerThreadId = Environment.CurrentManagedThreadId;
    }

    public static ShopDiagnosticTransportRuntime? Create(
        byte[]? configuration,
        Func<byte[]?> credentialReader,
        Func<IShopDiagnosticService> factory)
    {
        FixedTimeAuthenticator? authenticator = null;
        byte[]? credential = null;
        try
        {
            if (configuration is null ||
                !ShopDiagnosticTransportConfiguration.IsEnabled(configuration) ||
                credentialReader is null || factory is null)
            {
                return null;
            }
            try
            {
                credential = credentialReader();
            }
            catch
            {
                return null;
            }
            if (credential is null ||
                !FixedTimeAuthenticator.TryCreate(credential, out authenticator) ||
                authenticator is null)
            {
                return null;
            }

            var runtime = new ShopDiagnosticTransportRuntime(authenticator);
            authenticator = null;
            IShopDiagnosticService service;
            try
            {
                service = factory();
            }
            catch
            {
                runtime.DisposeBeforeService();
                return null;
            }
            if (service is null)
            {
                runtime.DisposeBeforeService();
                return null;
            }
            runtime._service = service;
            return runtime;
        }
        catch
        {
            return null;
        }
        finally
        {
            if (credential is not null) CryptographicOperations.ZeroMemory(credential);
            if (configuration is not null) CryptographicOperations.ZeroMemory(configuration);
            authenticator?.Dispose();
        }
    }

    public bool Start()
    {
        if (!TryReserveStart()) return false;
        TcpListener? listener = null;
        try
        {
            listener = new TcpListener(IPAddress.Loopback, ShopDiagnosticTransportLimits.Port);
            listener.Start(ShopDiagnosticTransportLimits.Backlog);
            return StartCore(listener, production: true);
        }
        catch
        {
            try { listener?.Stop(); } catch { }
            FailReservedStart();
            return false;
        }
    }

#if SHOP_DIAGNOSTIC_TEST_SEAM
    internal bool StartForTests(TcpListener listener, Action? afterReserved = null)
    {
        if (!TryReserveStart()) return false;
        try
        {
            afterReserved?.Invoke();
            if (listener is null || listener.Server.AddressFamily != AddressFamily.InterNetwork ||
                !listener.Server.IsBound || listener.LocalEndpoint is not IPEndPoint endpoint ||
                !IsAllowedEndpoint(endpoint, production: false))
            {
                listener?.Stop();
                FailReservedStart();
                return false;
            }
            return StartCore(listener, production: false);
        }
        catch
        {
            try { listener?.Stop(); } catch { }
            FailReservedStart();
            return false;
        }
    }

    internal static bool IsAllowedTestEndpoint(IPEndPoint endpoint) =>
        IsAllowedEndpoint(endpoint, production: false);
    internal int ObservationSubmissionCount => Volatile.Read(ref _observationSubmissionCountForTests);
    internal bool ObservationReserved => Volatile.Read(ref _observationReserved) != 0;
    internal int OutstandingFrameCount => _frameQueue.OutstandingCount;
    internal Action? AfterAuthenticatedReservationForTests { get; set; }
    internal bool ReserveObservationForTests() => ReserveObservation();
#endif

    public bool DrainFrame()
    {
        if (Environment.CurrentManagedThreadId != _ownerThreadId) return false;
        lock (_gate)
        {
            if (!_started || _stopping) return false;
        }
        return _frameQueue.DrainFrame();
    }

    public bool StopTransportAndJoin()
    {
        var stopwatch = Stopwatch.StartNew();
        InitiateStop();
        lock (_gate)
        {
            if (_transportStopped) return true;
            _joinWaiters++;
        }
        bool complete;
        try
        {
            TimeSpan remaining = JoinTimeout - stopwatch.Elapsed;
            complete = remaining > TimeSpan.Zero && _transportSettled.Wait(remaining);
        }
        catch (ObjectDisposedException)
        {
            complete = true;
        }
        finally
        {
            bool disposeSettled;
            lock (_gate)
            {
                _joinWaiters--;
                disposeSettled = ShouldDisposeSettledLocked();
            }
            if (disposeSettled) _transportSettled.Dispose();
        }
        return complete && TransportStopped;
    }

    public bool TransportStopped
    {
        get { lock (_gate) return _transportStopped; }
    }

    public bool DisposeServiceOnOwnerFrame()
    {
        if (Environment.CurrentManagedThreadId != _ownerThreadId) return false;
        lock (_gate)
        {
            if (_serviceDisposed) return true;
            if (!_transportStopped || _serviceDisposeAttempted) return false;
            _serviceDisposeAttempted = true;
        }
        try
        {
            IShopDiagnosticService service = _service ??
                throw new InvalidOperationException("Service unavailable.");
            service.Dispose();
            lock (_gate) _serviceDisposed = true;
            return true;
        }
        catch
        {
            return false;
        }
    }

    public bool ServiceDisposed
    {
        get { lock (_gate) return _serviceDisposed; }
    }

    public bool IsTerminalOrStopping =>
        Volatile.Read(ref _terminalPublished) != 0 || IsStopping;

    public bool IsFullyStopped => TransportStopped && ServiceDisposed;

    public void Dispose()
    {
        StopTransportAndJoin();
    }

    private bool IsStopping
    {
        get { lock (_gate) return _stopping; }
    }

    private bool TryReserveStart()
    {
        lock (_gate)
        {
            if (_startAttempted || _stopping || _transportDispositionStarted)
                return false;
            _startAttempted = true;
            _startInProgress = true;
            return true;
        }
    }

    private bool StartCore(TcpListener listener, bool production)
    {
        try
        {
            lock (_gate)
            {
                if (_stopping || _transportDispositionStarted ||
                    listener.LocalEndpoint is not IPEndPoint endpoint ||
                    !IsAllowedEndpoint(endpoint, production))
                    throw new InvalidOperationException("Invalid reserved listener.");
                _started = true;
                _acceptCompleted = false;
                _listener = listener;
                CancellationToken token = _stopSource.Token;
                _acceptTask = Task.Run(() => AcceptLoopAsync(listener, token));
                _startInProgress = false;
                return true;
            }
        }
        catch
        {
            try { listener.Stop(); } catch { }
            FailReservedStart();
            return false;
        }
    }

    private void FailReservedStart()
    {
        lock (_gate)
        {
            _startInProgress = false;
            _acceptCompleted = true;
        }
        InitiateStop();
        OnComponentStateChanged();
    }

    private async Task AcceptLoopAsync(TcpListener listener, CancellationToken token)
    {
        bool unexpected = false;
        try
        {
            while (!token.IsCancellationRequested)
            {
                Socket socket;
                try
                {
                    socket = await listener.AcceptSocketAsync(token).ConfigureAwait(false);
                }
                catch
                {
                    unexpected = !token.IsCancellationRequested;
                    break;
                }
                if (!_preAuthenticationBucket.TryConsume() || !_handlerSlots.Wait(0))
                {
                    socket.Dispose();
                    continue;
                }
                lock (_gate)
                {
                    if (_stopping)
                    {
                        _handlerSlots.Release();
                        socket.Dispose();
                        continue;
                    }
                    _activeSockets.Add(socket);
                }
                Task worker = HandleSocketAsync(socket, token);
                lock (_gate) _workers.Add(worker);
                _ = worker.ContinueWith(
                    _ => WorkerFinished(worker, socket),
                    CancellationToken.None,
                    TaskContinuationOptions.ExecuteSynchronously,
                    TaskScheduler.Default);
            }
        }
        finally
        {
            lock (_gate) _acceptCompleted = true;
            if (unexpected) RequestTerminal();
            InitiateStop();
            OnComponentStateChanged();
        }
    }

    private async Task HandleSocketAsync(Socket socket, CancellationToken stopToken)
    {
        await Task.Yield();
        byte[]? requestBuffer = null;
        byte[]? body = null;
        byte[]? response = null;
        bool exchangeOwned = false;
        bool observationReserved = false;
        bool serviceMayHaveRun = false;
        try
        {
            using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(stopToken);
            lifetime.CancelAfter(ShopDiagnosticTransportLimits.ConnectionLifetimeMilliseconds);
            ReceivedRequest received = await ReceiveToEofAsync(socket, lifetime.Token).ConfigureAwait(false);
            requestBuffer = received.Buffer;
            if (!received.Complete || requestBuffer is null ||
                !ShopDiagnosticTransportRequestParser.TryParse(
                    requestBuffer.AsSpan(0, received.Length),
                    out ParsedShopDiagnosticRequest parsed))
                return;
            if (!_authenticator.Matches(requestBuffer.AsSpan(
                    parsed.AuthorizationOffset, parsed.AuthorizationLength)))
                return;
            if (TerminalRequestedOrStopping()) return;
            if (!ReserveObservation())
            {
                RequestTerminal();
                return;
            }
            observationReserved = true;

            if (!TryOwnExchange())
            {
                RequestTerminal();
                return;
            }
            exchangeOwned = true;
#if SHOP_DIAGNOSTIC_TEST_SEAM
            AfterAuthenticatedReservationForTests?.Invoke();
#endif
            if (!_authenticatedBucket.TryConsume())
            {
                RequestTerminal();
                return;
            }

            OwnedByteDispatchResult dispatch = _frameQueue.Submit(() =>
            {
                serviceMayHaveRun = true;
#if SHOP_DIAGNOSTIC_TEST_SEAM
                Interlocked.Increment(ref _observationSubmissionCountForTests);
#endif
                IShopDiagnosticService service = _service ??
                    throw new InvalidOperationException("Service unavailable.");
                return service.Observe();
            });
            if (dispatch.Status != OwnedByteDispatchStatus.Success || dispatch.Value is null)
            {
                return;
            }
            body = dispatch.Value;
            response = ShopDiagnosticTransportHttpEncoder.Wrap(body);
            await SendAllAsync(socket, response, lifetime.Token).ConfigureAwait(false);
        }
        catch
        {
        }
        finally
        {
            Zero(response);
            Zero(body);
            Zero(requestBuffer);
            try { socket.Shutdown(SocketShutdown.Both); } catch { }
            socket.Dispose();
            if (exchangeOwned) FinishExchange();
            if (observationReserved || serviceMayHaveRun) RequestTerminal();
        }
    }

#if SHOP_DIAGNOSTIC_TEST_SEAM
    private int _observationSubmissionCountForTests;
#endif

    private bool ReserveObservation()
    {
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                Interlocked.CompareExchange(ref _observationReserved, 1, 0) != 0)
                return false;
            return true;
        }
    }

    private bool TerminalRequestedOrStopping()
    {
        if (Volatile.Read(ref _terminalRequested) != 0) return true;
        lock (_gate) return _stopping;
    }

    private void RequestTerminal()
    {
        Interlocked.Exchange(ref _terminalRequested, 1);
        if (Volatile.Read(ref _exchangeInFlight) == 0) PublishTerminal();
    }

    private void FinishExchange()
    {
        Interlocked.Exchange(ref _exchangeInFlight, 0);
        if (Volatile.Read(ref _terminalRequested) != 0) PublishTerminal();
    }

    private bool TryOwnExchange()
    {
        if (Interlocked.CompareExchange(ref _exchangeInFlight, 1, 0) == 0)
        {
            if (Volatile.Read(ref _terminalRequested) == 0) return true;
            Interlocked.Exchange(ref _exchangeInFlight, 0);
            PublishTerminal();
            return false;
        }
        return false;
    }

    private void PublishTerminal()
    {
        if (Interlocked.Exchange(ref _terminalPublished, 1) == 0)
            InitiateStop();
    }

    private static async Task<ReceivedRequest> ReceiveToEofAsync(
        Socket socket,
        CancellationToken lifetimeToken)
    {
        byte[] buffer = new byte[ShopDiagnosticTransportLimits.RequestBufferSize];
        bool transfer = false;
        try
        {
            using var header = CancellationTokenSource.CreateLinkedTokenSource(lifetimeToken);
            header.CancelAfter(ShopDiagnosticTransportLimits.HeaderReadMilliseconds);
            int total = 0;
            while (total < buffer.Length)
            {
                int read = await socket.ReceiveAsync(
                    buffer.AsMemory(total, buffer.Length - total),
                    SocketFlags.None,
                    header.Token).ConfigureAwait(false);
                if (read == 0)
                {
                    if (total is < 1 or > ShopDiagnosticTransportLimits.MaximumRequestHead) return default;
                    transfer = true;
                    return new ReceivedRequest(true, buffer, total);
                }
                total += read;
            }
            return default;
        }
        catch
        {
            return default;
        }
        finally
        {
            if (!transfer) Zero(buffer);
        }
    }

    private static async Task SendAllAsync(
        Socket socket,
        byte[] response,
        CancellationToken lifetimeToken)
    {
        using var write = CancellationTokenSource.CreateLinkedTokenSource(lifetimeToken);
        write.CancelAfter(ShopDiagnosticTransportLimits.ResponseWriteMilliseconds);
        int sent = 0;
        while (sent < response.Length)
        {
            int count = await socket.SendAsync(
                response.AsMemory(sent), SocketFlags.None, write.Token).ConfigureAwait(false);
            if (count <= 0) throw new InvalidOperationException("Response write failed.");
            sent += count;
        }
    }

    private void WorkerFinished(Task worker, Socket socket)
    {
        _handlerSlots.Release();
        lock (_gate)
        {
            _workers.Remove(worker);
            _activeSockets.Remove(socket);
        }
        OnComponentStateChanged();
    }

    private void InitiateStop()
    {
        TcpListener? listener;
        Socket[] sockets;
        lock (_gate)
        {
            if (_stopping) return;
            _stopping = true;
            _started = false;
            listener = _listener;
            sockets = new Socket[_activeSockets.Count];
            _activeSockets.CopyTo(sockets);
        }
        _stopSource.Cancel();
        try { listener?.Stop(); } catch { }
        foreach (Socket socket in sockets)
        {
            try { socket.Dispose(); } catch { }
        }
        _frameQueue.Stop();
        OnComponentStateChanged();
    }

    private void OnComponentStateChanged()
    {
        bool dispose = false;
        lock (_gate)
        {
            bool ready = _stopping && !_startInProgress && _acceptCompleted &&
                _workers.Count == 0 && _frameQueue.IsSettled;
            if (ready && !_transportDispositionStarted)
            {
                _transportDispositionStarted = true;
                dispose = true;
            }
        }
        if (dispose) DisposeTransportResources();
    }

    private void DisposeTransportResources()
    {
        _authenticator.Dispose();
        _frameQueue.Dispose();
        _handlerSlots.Dispose();
        _stopSource.Dispose();
        bool disposeSettled;
        lock (_gate)
        {
            _transportStopped = true;
            _transportSettled.Set();
            disposeSettled = ShouldDisposeSettledLocked();
        }
        if (disposeSettled) _transportSettled.Dispose();
    }

    private bool ShouldDisposeSettledLocked()
    {
        if (!_transportStopped || _joinWaiters != 0 || _settledDisposed) return false;
        _settledDisposed = true;
        return true;
    }

    private static bool IsAllowedEndpoint(IPEndPoint endpoint, bool production) =>
        endpoint.AddressFamily == AddressFamily.InterNetwork &&
        IPAddress.Loopback.Equals(endpoint.Address) &&
        endpoint.Port is >= 1 and <= 65535 &&
        (production ? endpoint.Port == ShopDiagnosticTransportLimits.Port :
            endpoint.Port != ShopDiagnosticTransportLimits.Port);

    private static void Zero(byte[]? value)
    {
        if (value is not null) CryptographicOperations.ZeroMemory(value);
    }

    private readonly record struct ReceivedRequest(bool Complete, byte[]? Buffer, int Length);

    private void DisposeBeforeService()
    {
        _frameQueue.Stop();
        _authenticator.Dispose();
        _frameQueue.Dispose();
        _handlerSlots.Dispose();
        _stopSource.Dispose();
        _transportSettled.Dispose();
    }
}
