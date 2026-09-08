using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Transport;


namespace Sts2AgentBridge.Unified;

internal sealed class BridgeTransportRuntime : IDisposable
{
    private static readonly TimeSpan JoinTimeout =
        TimeSpan.FromMilliseconds(BridgeTransportLimits.ShutdownJoinMilliseconds);

    private readonly object _gate = new();
    private readonly FixedTimeAuthenticator _authenticator;
    private BridgeRouter? _service;
    private Action? _ownerFrameCleanup;
    private readonly string _nonce;
    private readonly OwnedByteFrameQueue _frameQueue;
    private readonly MonotonicTokenBucket _preAuthenticationBucket;
    private readonly MonotonicTokenBucket _authenticatedBucket;
    private readonly SemaphoreSlim _handlerSlots = new(
        BridgeTransportLimits.MaximumHandlers,
        BridgeTransportLimits.MaximumHandlers);
    private readonly CancellationTokenSource _stopSource = new();
    private readonly ManualResetEventSlim _transportSettled = new(false);
    private readonly HashSet<Socket> _activeSockets = new();
    private readonly HashSet<Task> _workers = new();
    private readonly HashSet<PostIdentity> _reservedPosts = new();
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
    private int _parentPostCount;
    private int _readCount;
    private int _exchangeInFlight;
    private int _exchangeResponseSent;
    private int _authenticatedCleanupParticipants;
    private int _terminalRequested;
    private int _terminalPublished;

    private BridgeTransportRuntime(
        FixedTimeAuthenticator authenticator,
        string nonce)
    {
        _authenticator = authenticator;
        _nonce = nonce;
        _frameQueue = new OwnedByteFrameQueue(OnComponentStateChanged);
        _preAuthenticationBucket = new MonotonicTokenBucket(
            32.0, 16.0, StopwatchMonotonicClock.Instance);
        _authenticatedBucket = new MonotonicTokenBucket(
            20.0, 16.0, StopwatchMonotonicClock.Instance);
        _ownerThreadId = Environment.CurrentManagedThreadId;
    }

    public static BridgeTransportRuntime? Create(
        byte[]? configuration,
        Func<byte[]?> credentialReader,
        Func<string, BridgeRouter> factory)
    {
#if BRIDGE_TEST_SEAM
        string? fixedNonce=_fixedNonceForTests;_fixedNonceForTests=null;
#endif
        FixedTimeAuthenticator? authenticator = null;
        byte[]? credential = null;
        try
        {
            if (configuration is null ||
                !BridgeConfiguration.IsEnabled(configuration) ||
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

            Span<byte> random = stackalloc byte[16];
            try
            {
                RandomNumberGenerator.Fill(random);
                string nonce = Convert.ToHexString(random).ToLowerInvariant();
#if BRIDGE_TEST_SEAM
                if (fixedNonce is not null) {
                    nonce=fixedNonce;
                }
#endif

                // Allocate every pure transport resource before the owner-frame factory.
                var runtime = new BridgeTransportRuntime(authenticator, nonce);
                authenticator = null;
                BridgeRouter service;
                try
                {
                    service = factory(nonce);
                }
                catch (BridgeTransportFactoryFailure failure)
                {
                    runtime._ownerFrameCleanup = failure.OwnerFrameCleanup;
                    runtime.RequestTerminal();
                    runtime.StopTransportAndJoin();
                    return runtime;
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
                // This is the only operation after ownership transfers from the factory.
                runtime._service = service;
                return runtime;
            }
            finally
            {
                CryptographicOperations.ZeroMemory(random);
            }
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
            listener = new TcpListener(IPAddress.Loopback, BridgeTransportLimits.Port);
            listener.Start(BridgeTransportLimits.Backlog);
            return StartCore(listener, production: true);
        }
        catch
        {
            try { listener?.Stop(); } catch { }
            FailReservedStart();
            return false;
        }
    }

#if BRIDGE_TEST_SEAM
    [ThreadStatic] private static string? _fixedNonceForTests;
    internal static void SetNextNonceForTests(string nonce) {
        if(_fixedNonceForTests is not null||nonce.Length!=32)throw new InvalidOperationException("Invalid fixture nonce.");
        foreach(char c in nonce)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))throw new InvalidOperationException("Invalid fixture nonce.");
        _fixedNonceForTests=nonce;
    }
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
    internal int ReadSubmissionCount => Volatile.Read(ref _readSubmissionCountForTests);
    internal int ReservedParentPosts { get { lock (_gate) return _parentPostCount; } }
    internal int OutstandingFrameCount => _frameQueue.OutstandingCount;
    internal bool DropNextPostResponseForTests { get; set; }
    internal Action? AfterAuthenticatedReservationForTests { get; set; }
    internal bool ReserveReadForTests() => ReserveRead();
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
            if (_ownerFrameCleanup is Action cleanup) cleanup();
            else (_service ?? throw new InvalidOperationException("Service unavailable.")).Dispose();
            lock (_gate) { _serviceDisposed = true; _service = null; _ownerFrameCleanup = null; }
            return true;
        }
        catch
        {
            return false;
        }
        finally { lock (_gate) _serviceDisposeAttempted = false; }
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
        // Never let a synchronously available request run the handler on the
        // accept-loop continuation and stall admission of the bounded peers.
        await Task.Yield();
        byte[]? requestBuffer = null;
        byte[]? body = null;
        byte[]? response = null;
        bool exchangeOwned = false;
        bool authenticatedCleanupParticipant = false;
        bool reservedPost = false;
        bool serviceMayHaveRun = false;
        bool sent = false;
        bool terminalBody = false;
        bool staleWithoutMutation = false;
        bool terminalAfterCleanup = false;
        try
        {
            using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(stopToken);
            lifetime.CancelAfter(BridgeTransportLimits.ConnectionLifetimeMilliseconds);
            ReceivedRequest received = await ReceiveToEofAsync(socket, lifetime.Token).ConfigureAwait(false);
            requestBuffer = received.Buffer;
            if (!received.Complete || requestBuffer is null ||
                !BridgeRequestParser.TryParse(
                    requestBuffer.AsSpan(0, received.Length),
                    out BridgeRequest parsed))
                return;
            if (!_authenticator.Matches(requestBuffer.AsSpan(
                    parsed.AuthorizationOffset, parsed.AuthorizationLength)))
                return;
            Interlocked.Increment(ref _authenticatedCleanupParticipants);
            authenticatedCleanupParticipant = true;
            if (TerminalRequestedOrStopping()) return;

            BridgeRequest request = parsed;
            if (request.IsPost)
            {
                if (!ReservePost(request)) { terminalAfterCleanup = true; LatchTerminal(); return; }
                reservedPost = true;
            }
            else if (!ReserveRead()) { terminalAfterCleanup = true; LatchTerminal(); return; }

            if (!TryOwnExchange())
            {
                terminalAfterCleanup = true;
                LatchTerminal();
                return;
            }
            exchangeOwned = true;
#if BRIDGE_TEST_SEAM
            AfterAuthenticatedReservationForTests?.Invoke();
#endif
            if (!_authenticatedBucket.TryConsume())
            {
                if (reservedPost)
                {
                    terminalAfterCleanup = true;
                    LatchTerminal();
                }
                return;
            }

            OwnedByteDispatchResult dispatch = _frameQueue.Submit(() =>
            {
                serviceMayHaveRun = true;
#if BRIDGE_TEST_SEAM
                if (!request.IsPost) Interlocked.Increment(ref _readSubmissionCountForTests);
#endif
                BridgeReply reply = (_service ?? throw new InvalidOperationException("Service unavailable.")).Handle(request);
                staleWithoutMutation = reply.StaleWithoutMutation;
                return new OwnedServiceResponse(reply.Terminal ? 503 : 200, reply.Response);
            });
            body = dispatch.Value;
            if (dispatch.Status != OwnedByteDispatchStatus.Success || body is null)
            { terminalAfterCleanup = true; LatchTerminal(); return; }
            terminalBody = dispatch.StatusCode == 503;
#if BRIDGE_TEST_SEAM
            if (parsed.IsPost && DropNextPostResponseForTests)
            {
                DropNextPostResponseForTests = false;
                terminalAfterCleanup = true;
                LatchTerminal();
                return;
            }
#endif
            response = body; body = null;
            await SendAllAsync(socket, response, lifetime.Token).ConfigureAwait(false);
            sent = true;
            // A failed/partial delivery never reaches this point. Keep the total
            // attempt budget, but allow a freshly observed, previously rejected
            // identity to be selected again after native revalidation.
            if (reservedPost && !terminalBody && staleWithoutMutation)
                ReleaseStalePost(request);
            Volatile.Write(ref _exchangeResponseSent, 1);
            if (terminalBody)
            {
                terminalAfterCleanup = true;
                LatchTerminal();
            }
        }
        catch
        {
            if (reservedPost || serviceMayHaveRun || terminalBody)
            {
                terminalAfterCleanup = true;
                LatchTerminal();
            }
        }
        finally
        {
            if ((reservedPost || serviceMayHaveRun || terminalBody) && !sent)
            {
                terminalAfterCleanup = true;
                LatchTerminal();
            }
#if BRIDGE_TEST_SEAM
            if (terminalAfterCleanup)
            {
                try { BeforeTerminalCleanupForTests?.Invoke(requestBuffer, socket); }
                catch { }
            }
#endif
            Zero(response);
            Zero(body);
            Zero(requestBuffer);
            try { socket.Shutdown(SocketShutdown.Both); } catch { }
            socket.Dispose();
            if (exchangeOwned) FinishExchange();
            if (authenticatedCleanupParticipant) FinishAuthenticatedCleanupParticipant();
            if (terminalAfterCleanup) TryPublishTerminal();
        }
    }

#if BRIDGE_TEST_SEAM
    private int _readSubmissionCountForTests;
    internal Action<byte[]>? ServiceBodyOwnedForTests { get; set; }
    internal Action<byte[]?, Socket>? BeforeTerminalCleanupForTests { get; set; }
#endif

    private bool ReserveRead()
    {
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                _readCount >= BridgeTransportLimits.MaximumReads)
                return false;
            _readCount++;
            return true;
        }
    }

    private bool ReservePost(BridgeRequest request)
    {
        var identity = new PostIdentity(request.Path, request.Decision!, request.Action!,
            request.ChildOrdinal, request.ParentDecision, request.ParentAction);
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                _parentPostCount >= BridgeTransportLimits.MaximumTotalPosts || !_reservedPosts.Add(identity)) return false;
            _parentPostCount++;
            return true;
        }
    }

    private void ReleaseStalePost(BridgeRequest request)
    {
        var identity = new PostIdentity(request.Path, request.Decision!, request.Action!,
            request.ChildOrdinal, request.ParentDecision, request.ParentAction);
        lock (_gate) _reservedPosts.Remove(identity);
    }

    private bool TerminalRequestedOrStopping()
    {
        if (Volatile.Read(ref _terminalRequested) != 0) return true;
        lock (_gate) return _stopping;
    }

    private void RequestTerminal()
    {
        LatchTerminal();
        TryPublishTerminal();
    }

    private void LatchTerminal() => Interlocked.Exchange(ref _terminalRequested, 1);

    private void FinishExchange()
    {
        Interlocked.Exchange(ref _exchangeInFlight, 0);
        TryPublishTerminal();
    }

    private void FinishAuthenticatedCleanupParticipant()
    {
        Interlocked.Decrement(ref _authenticatedCleanupParticipants);
        TryPublishTerminal();
    }

    private void TryPublishTerminal()
    {
        if (Volatile.Read(ref _terminalRequested) != 0 &&
            Volatile.Read(ref _exchangeInFlight) == 0 &&
            Volatile.Read(ref _authenticatedCleanupParticipants) == 0)
            PublishTerminal();
    }

    private bool TryOwnExchange()
    {
        if (Interlocked.CompareExchange(ref _exchangeInFlight, 1, 0) == 0)
        {
            Volatile.Write(ref _exchangeResponseSent, 0);
            if (Volatile.Read(ref _terminalRequested) == 0) return true;
            Interlocked.Exchange(ref _exchangeInFlight, 0);
            TryPublishTerminal();
            return false;
        }

        // A concurrently authenticated exchange is terminal while the first
        // response is still unsent. Only the cleanup tail after a complete
        // send may settle as sequential.
        if (Volatile.Read(ref _exchangeResponseSent) == 0) return false;
        var wait = Stopwatch.StartNew();
        while (Volatile.Read(ref _exchangeInFlight) != 0 &&
            Volatile.Read(ref _terminalRequested) == 0 &&
            wait.ElapsedMilliseconds < 250)
        {
            Thread.Yield();
        }
        if (Volatile.Read(ref _terminalRequested) != 0 ||
            Interlocked.CompareExchange(ref _exchangeInFlight, 1, 0) != 0)
            return false;
        Volatile.Write(ref _exchangeResponseSent, 0);
        if (Volatile.Read(ref _terminalRequested) == 0) return true;
        Interlocked.Exchange(ref _exchangeInFlight, 0);
        TryPublishTerminal();
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
        byte[] buffer = new byte[BridgeTransportLimits.RequestBufferSize];
        bool transfer = false;
        try
        {
            using var header = CancellationTokenSource.CreateLinkedTokenSource(lifetimeToken);
            header.CancelAfter(BridgeTransportLimits.HeaderReadMilliseconds);
            int total = 0;
            while (total < buffer.Length)
            {
                int read = await socket.ReceiveAsync(
                    buffer.AsMemory(total, buffer.Length - total),
                    SocketFlags.None,
                    header.Token).ConfigureAwait(false);
                if (read == 0)
                {
                    if (total is < 1 or > BridgeTransportLimits.MaximumRequestHead) return default;
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
        write.CancelAfter(BridgeTransportLimits.ResponseWriteMilliseconds);
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
            _reservedPosts.Clear();
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
        (production ? endpoint.Port == BridgeTransportLimits.Port :
            endpoint.Port != BridgeTransportLimits.Port);

    private static void Zero(byte[]? value)
    {
        if (value is not null) CryptographicOperations.ZeroMemory(value);
    }

    private readonly record struct PostIdentity(
        string Route,
        string Decision,
        string Action, int Ordinal, string? ParentDecision, string? ParentAction);

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
