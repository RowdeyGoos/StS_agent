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
using Sts2AgentBridge.Successors.GenericEventV3;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV1;

public sealed class GenericEventTransportRuntime : IDisposable
{
    private static readonly TimeSpan JoinTimeout =
        TimeSpan.FromMilliseconds(GenericEventTransportLimits.ShutdownJoinMilliseconds);

    private readonly object _gate = new();
    private readonly FixedTimeAuthenticator _authenticator;
    private GenericEventV3WireService? _service;
    private Action? _ownerFrameCleanup;
    private readonly GenericEventReleaseSelection _selection;
    private readonly string _nonce;
    private readonly OwnedByteFrameQueue _frameQueue;
    private readonly MonotonicTokenBucket _preAuthenticationBucket;
    private readonly MonotonicTokenBucket _authenticatedBucket;
    private readonly SemaphoreSlim _handlerSlots = new(
        GenericEventTransportLimits.MaximumHandlers,
        GenericEventTransportLimits.MaximumHandlers);
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
    private int _childPostCount;
    private int _readCount;
    private int _exchangeInFlight;
    private int _exchangeResponseSent;
    private int _authenticatedCleanupParticipants;
    private int _terminalRequested;
    private int _terminalPublished;

    private GenericEventTransportRuntime(
        FixedTimeAuthenticator authenticator,
        GenericEventReleaseSelection selection,
        string nonce)
    {
        _authenticator = authenticator;
        _selection = selection;
        _nonce = nonce;
        _frameQueue = new OwnedByteFrameQueue(OnComponentStateChanged);
        _preAuthenticationBucket = new MonotonicTokenBucket(
            32.0, 16.0, StopwatchMonotonicClock.Instance);
        _authenticatedBucket = new MonotonicTokenBucket(
            20.0, 16.0, StopwatchMonotonicClock.Instance);
        _ownerThreadId = Environment.CurrentManagedThreadId;
    }

    public static GenericEventTransportRuntime? Create(
        byte[]? configuration,
        Func<byte[]?> credentialReader,
        Func<GenericEventReleaseSelection, string, GenericEventV3WireService> factory)
    {
        FixedTimeAuthenticator? authenticator = null;
        byte[]? credential = null;
        try
        {
            if (configuration is null ||
                !GenericEventTransportConfiguration.TryParse(configuration, out GenericEventReleaseSelection selection) ||
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

                // Allocate every pure transport resource before the owner-frame factory.
                var runtime = new GenericEventTransportRuntime(authenticator, selection, nonce);
                authenticator = null;
                GenericEventV3WireService service;
                try
                {
                    service = factory(selection, nonce);
                }
                catch (GenericEventTransportFactoryFailure failure)
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
            listener = new TcpListener(IPAddress.Loopback, GenericEventTransportLimits.Port);
            listener.Start(GenericEventTransportLimits.Backlog);
            return StartCore(listener, production: true);
        }
        catch
        {
            try { listener?.Stop(); } catch { }
            FailReservedStart();
            return false;
        }
    }

#if GENERIC_EVENT_RELEASE_TEST_SEAM
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
    internal int ReservedChildPosts { get { lock (_gate) return _childPostCount; } }
    internal int OutstandingFrameCount => _frameQueue.OutstandingCount;
    internal bool DropNextPostResponseForTests { get; set; }
    internal Action? AfterAuthenticatedReservationForTests { get; set; }
    internal bool ReserveReadForTests() => ReserveRead();
    internal bool ReservePostForTests(
        GenericEventTransportRoute route,
        string decision,
        string action) => ReservePost(route, decision, action);
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
        bool terminalAfterCleanup = false;
        try
        {
            using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(stopToken);
            lifetime.CancelAfter(GenericEventTransportLimits.ConnectionLifetimeMilliseconds);
            ReceivedRequest received = await ReceiveToEofAsync(socket, lifetime.Token).ConfigureAwait(false);
            requestBuffer = received.Buffer;
            if (!received.Complete || requestBuffer is null ||
                !GenericEventTransportRequestParser.TryParse(
                    requestBuffer.AsSpan(0, received.Length), _selection,
                    out ParsedGenericEventTransportRequest parsed))
                return;
            if (!_authenticator.Matches(requestBuffer.AsSpan(
                    parsed.AuthorizationOffset, parsed.AuthorizationLength)))
                return;
            Interlocked.Increment(ref _authenticatedCleanupParticipants);
            authenticatedCleanupParticipant = true;
            if (TerminalRequestedOrStopping()) return;

            string? decision = null;
            string? action = null;
            string? parentDecision = null, parentAction = null;
            if (parsed.IsPost)
            {
                decision = Encoding.ASCII.GetString(requestBuffer,
                    parsed.DecisionOffset, parsed.DecisionLength);
                action = Encoding.ASCII.GetString(requestBuffer,
                    parsed.ActionOffset, parsed.ActionLength);
                if (parsed.IsChild)
                {
                    parentDecision = Encoding.ASCII.GetString(requestBuffer, parsed.ParentDecisionOffset, parsed.ParentDecisionLength);
                    parentAction = Encoding.ASCII.GetString(requestBuffer, parsed.ParentActionOffset, parsed.ParentActionLength);
                }
                if (!ReservePost(parsed.Route, decision, action, parsed.ChildOrdinal, parentDecision, parentAction))
                {
                    terminalAfterCleanup = true;
                    LatchTerminal();
                    return;
                }
                reservedPost = true;
            }
            else if (!ReserveRead())
            {
                terminalAfterCleanup = true;
                LatchTerminal();
                return;
            }

            if (!TryOwnExchange())
            {
                terminalAfterCleanup = true;
                LatchTerminal();
                return;
            }
            exchangeOwned = true;
#if GENERIC_EVENT_RELEASE_TEST_SEAM
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

            string method = parsed.IsPost ? "POST" : "GET";
            string route = parsed.IsPost ? GenericEventV3WireService.ActionRoute : GenericEventV3WireService.DecisionRoute;
            OwnedByteDispatchResult dispatch = _frameQueue.Submit(() =>
            {
                serviceMayHaveRun = true;
#if GENERIC_EVENT_RELEASE_TEST_SEAM
                if (!parsed.IsPost) Interlocked.Increment(ref _readSubmissionCountForTests);
#endif
                GenericEventV3WireService service = _service ??
                    throw new InvalidOperationException("Service unavailable.");
                byte[]? ownedServiceBody = null;
                try
                {
                    if (parsed.IsPost)
                    {
                        ownedServiceBody = GenericEventTransportServiceBody.Build(decision!, action!, parsed.ChildOrdinal, parentDecision, parentAction);
#if GENERIC_EVENT_RELEASE_TEST_SEAM
                        ServiceBodyOwnedForTests?.Invoke(ownedServiceBody);
#endif
                    }
                    byte[] result = service.Handle(method, route, ownedServiceBody);
                    return new OwnedServiceResponse(200, result);
                }
                finally
                {
                    Zero(ownedServiceBody);
                }
            });
            if (dispatch.Status != OwnedByteDispatchStatus.Success || dispatch.Value is null)
            {
                if (reservedPost || dispatch.Status is OwnedByteDispatchStatus.TimedOutAfterClaim or OwnedByteDispatchStatus.Fault)
                {
                    terminalAfterCleanup = true;
                    LatchTerminal();
                }
                return;
            }
            body = dispatch.Value;
            TerminalClassification classification = GenericEventTerminalClassifier.Classify(
                parsed.Route, _selection, _nonce, dispatch.StatusCode, body);
            if (classification == TerminalClassification.Invalid)
            {
                terminalAfterCleanup = true;
                LatchTerminal();
                return;
            }
            terminalBody = classification == TerminalClassification.Terminal;
#if GENERIC_EVENT_RELEASE_TEST_SEAM
            if (parsed.IsPost && DropNextPostResponseForTests)
            {
                DropNextPostResponseForTests = false;
                terminalAfterCleanup = true;
                LatchTerminal();
                return;
            }
#endif
            response = GenericEventTransportHttpEncoder.Wrap(body);
            await SendAllAsync(socket, response, lifetime.Token).ConfigureAwait(false);
            sent = true;
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
#if GENERIC_EVENT_RELEASE_TEST_SEAM
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

#if GENERIC_EVENT_RELEASE_TEST_SEAM
    private int _readSubmissionCountForTests;
    internal Action<byte[]>? ServiceBodyOwnedForTests { get; set; }
    internal Action<byte[]?, Socket>? BeforeTerminalCleanupForTests { get; set; }
#endif

    private bool ReserveRead()
    {
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                _readCount >= GenericEventTransportLimits.MaximumReads)
                return false;
            _readCount++;
            return true;
        }
    }

    private bool ReservePost(GenericEventTransportRoute route, string decision, string action, int ordinal=0, string? parentDecision=null, string? parentAction=null)
    {
        var identity = new PostIdentity(route, decision, action, ordinal, parentDecision, parentAction);
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                _parentPostCount + _childPostCount >= GenericEventTransportLimits.MaximumTotalPosts ||
                !_reservedPosts.Add(identity))
                return false;
            if (route == GenericEventTransportRoute.ParentPost)
            {
                if (_parentPostCount >= GenericEventTransportLimits.MaximumParentPosts)
                {
                    _reservedPosts.Remove(identity);
                    return false;
                }
                _parentPostCount++;
            }
            else
            {
                if (route != GenericEventTransportRoute.ChildPost ||
                    _childPostCount >= GenericEventTransportLimits.MaximumChildPosts)
                {
                    _reservedPosts.Remove(identity);
                    return false;
                }
                _childPostCount++;
            }
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
        byte[] buffer = new byte[GenericEventTransportLimits.RequestBufferSize];
        bool transfer = false;
        try
        {
            using var header = CancellationTokenSource.CreateLinkedTokenSource(lifetimeToken);
            header.CancelAfter(GenericEventTransportLimits.HeaderReadMilliseconds);
            int total = 0;
            while (total < buffer.Length)
            {
                int read = await socket.ReceiveAsync(
                    buffer.AsMemory(total, buffer.Length - total),
                    SocketFlags.None,
                    header.Token).ConfigureAwait(false);
                if (read == 0)
                {
                    if (total is < 1 or > GenericEventTransportLimits.MaximumRequestHead) return default;
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
        write.CancelAfter(GenericEventTransportLimits.ResponseWriteMilliseconds);
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
        (production ? endpoint.Port == GenericEventTransportLimits.Port :
            endpoint.Port != GenericEventTransportLimits.Port);

    private static void Zero(byte[]? value)
    {
        if (value is not null) CryptographicOperations.ZeroMemory(value);
    }

    private readonly record struct PostIdentity(
        GenericEventTransportRoute Route,
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

internal enum TerminalClassification
{
    Invalid = 0,
    NonTerminal = 1,
    Terminal = 2,
}


internal static class GenericEventTerminalClassifier
{
    internal static TerminalClassification Classify(GenericEventTransportRoute route, GenericEventReleaseSelection selection,
        string nonce, int statusCode, byte[] body)
    {
        if (!Enum.IsDefined(route) || selection != GenericEventReleaseSelection.Generic || statusCode != 200 ||
            body.Length is < 1 or > 65536 || !Hex(nonce, 32)) return TerminalClassification.Invalid;
        byte[]? canonical = null;
        try
        {
            foreach (byte b in body) if (b is < 0x20 or > 0x7e) return TerminalClassification.Invalid;
            using var document = JsonDocument.Parse(body, new JsonDocumentOptions { MaxDepth = 12 });
            var root = document.RootElement;
            if (!Bounded(root) || !Keys(root, "schema_version", "protocol", "session_nonce", "kind", "parent", "child", "payload") ||
                root.GetProperty("schema_version").GetInt32() != 1 || Text(root,"protocol") != "generic_event_v3" || Text(root,"session_nonce") != nonce)
                return TerminalClassification.Invalid;
            canonical = JsonSerializer.SerializeToUtf8Bytes(root);
            if (!body.AsSpan().SequenceEqual(canonical)) return TerminalClassification.Invalid;
            var parent=root.GetProperty("parent"); var child=root.GetProperty("child"); var payload=root.GetProperty("payload");
            string? kind=Text(root,"kind");
            if (kind == "error") return Null(parent) && Null(child) && Keys(payload,"code") &&
                Text(payload,"code") is "invalid_request" or "internal_failure" or "unsupported" ? TerminalClassification.Terminal : TerminalClassification.Invalid;
            if (!Null(child) && !Child(child)) return TerminalClassification.Invalid;
            if (kind == "action")
            {
                if (route == GenericEventTransportRoute.DecisionGet || !Null(parent) || payload.ValueKind != JsonValueKind.Object ||
                    Text(payload,"session_nonce") != nonce) return TerminalClassification.Invalid;
                if (route == GenericEventTransportRoute.ParentPost)
                {
                    if (!Null(child) || !Keys(payload,"version","session_nonce","decision_id","action_id","outcome") ||
                        Text(payload,"version") != "generic_event_v3") return TerminalClassification.Invalid;
                }
                else if (Null(child) || Text(payload,"version") != "card_selection_v1" ||
                    Text(payload,"kind") is not ("child_receipt" or "child_failure") || payload.GetProperty("schema_version").GetInt32()!=1)
                    return TerminalClassification.Invalid;
                string? outcome=Text(payload,"outcome");
                if(route==GenericEventTransportRoute.ParentPost)
                {
                    if(!Hex(Text(payload,"decision_id"),64) || !GenericEventTransportRequestParser.ParentActionValue(Encoding.ASCII.GetBytes(Text(payload,"action_id")??"")))return TerminalClassification.Invalid;
                    return outcome switch { "accepted"=>TerminalClassification.NonTerminal,
                        "unsupported" or "stale_decision" or "illegal_action" or "uncertain" or "budget_exhausted"=>TerminalClassification.Terminal,
                        _=>TerminalClassification.Invalid };
                }
                if(payload.GetProperty("parent_ordinal").GetInt32()!=1)return TerminalClassification.Invalid;
                if(Text(payload,"kind")=="child_failure")
                    return Keys(payload,"schema_version","kind","version","session_nonce","parent_ordinal","outcome") && outcome is "unsupported" or "uncertain" or "rejected" ? TerminalClassification.Terminal : TerminalClassification.Invalid;
                return Keys(payload,"schema_version","kind","version","session_nonce","parent_ordinal","decision_id","action_id","outcome") &&
                    Hex(Text(payload,"decision_id"),64) && GenericEventTransportRequestParser.ChildAction(Encoding.ASCII.GetBytes(Text(payload,"action_id")??"")) && outcome=="accepted" ? TerminalClassification.NonTerminal : TerminalClassification.Invalid;
            }
            if (kind != "decision" || route != GenericEventTransportRoute.DecisionGet || parent.ValueKind != JsonValueKind.Object)
                return TerminalClassification.Invalid;
            string? status=Text(parent,"status"),phase=Text(parent,"phase");
            if (status == "child")
            {
                if (Null(child) || payload.ValueKind != JsonValueKind.Object || Text(payload,"version") != "card_selection_v1" ||
                    Text(payload,"session_nonce") != nonce || payload.GetProperty("schema_version").GetInt32()!=1) return TerminalClassification.Invalid;
                return Text(payload,"kind") switch {
                    "child_resolved" when Text(payload,"status")=="resolved" => TerminalClassification.NonTerminal,
                    "child_observation" when Text(payload,"status") is "ready" or "waiting" => TerminalClassification.NonTerminal,
                    "child_observation" when Text(payload,"status")=="unsupported" => TerminalClassification.Terminal,
                    _ => TerminalClassification.Invalid };
            }
            if (!Null(child) || !Null(payload)) return TerminalClassification.Invalid;
            return status switch {
                "complete" when phase=="map_handoff" => TerminalClassification.Terminal,
                "unsupported" => TerminalClassification.Terminal,
                "ready" or "waiting" => TerminalClassification.NonTerminal,
                _ => TerminalClassification.Invalid };
        }
        catch { return TerminalClassification.Invalid; }
        finally { if(canonical is not null) Array.Clear(canonical); }
    }
    private static bool Child(JsonElement value) => Keys(value,"ordinal","parent_decision_id","parent_action_id","operation","min_select","max_select","commit_mode","domain_count") &&
        value.GetProperty("ordinal").GetInt32() is >=1 and <=4 && Hex(Text(value,"parent_decision_id"),64) &&
        GenericEventTransportRequestParser.ParentActionValue(Encoding.ASCII.GetBytes(Text(value,"parent_action_id") ?? "")) &&
        GenericEventV3Families.Supports(Text(value,"operation") ?? "",value.GetProperty("min_select").GetInt32(),value.GetProperty("max_select").GetInt32(),Text(value,"commit_mode") ?? "",value.GetProperty("domain_count").GetInt32());
    private static bool Null(JsonElement value)=>value.ValueKind==JsonValueKind.Null;
    private static string? Text(JsonElement value,string key)=>value.GetProperty(key).GetString();
    private static bool Hex(string? value,int size)
    { if(value is null || value.Length!=size)return false;foreach(char c in value)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;return true; }
    private static bool Keys(JsonElement value,params string[] keys)
    { if(value.ValueKind!=JsonValueKind.Object)return false;int i=0;foreach(var p in value.EnumerateObject()){if(i==keys.Length||p.Name!=keys[i++])return false;}return i==keys.Length; }
    private static bool Bounded(JsonElement value)
    {
        if(value.ValueKind==JsonValueKind.Object){var keys=new HashSet<string>(StringComparer.Ordinal);foreach(var p in value.EnumerateObject())if(keys.Count==64||p.Name.Length>64||!keys.Add(p.Name)||!Bounded(p.Value))return false;return true;}
        if(value.ValueKind==JsonValueKind.Array){if(value.GetArrayLength()>128)return false;foreach(var v in value.EnumerateArray())if(!Bounded(v))return false;return true;}
        return value.ValueKind switch { JsonValueKind.String => value.GetString()!.Length<=4096,JsonValueKind.Number=>value.TryGetInt64(out _),JsonValueKind.True or JsonValueKind.False or JsonValueKind.Null=>true,_=>false };
    }
}
