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
using Sts2AgentBridge.Successors.ItemWireV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.RoomReleaseV1;

public sealed class RoomFlowTransportRuntime : IDisposable
{
    private static readonly TimeSpan JoinTimeout =
        TimeSpan.FromMilliseconds(RoomFlowTransportLimits.ShutdownJoinMilliseconds);

    private readonly object _gate = new();
    private readonly FixedTimeAuthenticator _authenticator;
    private RoomFlowWireService? _service;
    private readonly RoomFlowSelection _selection;
    private readonly string _nonce;
    private readonly OwnedByteFrameQueue _frameQueue;
    private readonly MonotonicTokenBucket _preAuthenticationBucket;
    private readonly MonotonicTokenBucket _authenticatedBucket;
    private readonly SemaphoreSlim _handlerSlots = new(
        RoomFlowTransportLimits.MaximumHandlers,
        RoomFlowTransportLimits.MaximumHandlers);
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
    private int _itemPostCount;
    private int _readCount;
    private int _exchangeInFlight;
    private int _exchangeResponseSent;
    private int _terminalRequested;
    private int _terminalPublished;

    private RoomFlowTransportRuntime(
        FixedTimeAuthenticator authenticator,
        RoomFlowSelection selection,
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

    public static RoomFlowTransportRuntime? Create(
        byte[]? configuration,
        Func<byte[]?> credentialReader,
        Func<RoomFlowSelection, string, RoomFlowWireService> factory)
    {
        FixedTimeAuthenticator? authenticator = null;
        byte[]? credential = null;
        try
        {
            if (configuration is null ||
                !RoomFlowTransportConfiguration.TryParse(configuration, out RoomFlowSelection selection) ||
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
                var runtime = new RoomFlowTransportRuntime(authenticator, selection, nonce);
                authenticator = null;
                RoomFlowWireService service;
                try
                {
                    service = factory(selection, nonce);
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
            listener = new TcpListener(IPAddress.Loopback, RoomFlowTransportLimits.Port);
            listener.Start(RoomFlowTransportLimits.Backlog);
            return StartCore(listener, production: true);
        }
        catch
        {
            try { listener?.Stop(); } catch { }
            FailReservedStart();
            return false;
        }
    }

#if ROOM_RELEASE_TEST_SEAM
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
    internal int ReservedItemPosts { get { lock (_gate) return _itemPostCount; } }
    internal int OutstandingFrameCount => _frameQueue.OutstandingCount;
    internal bool DropNextPostResponseForTests { get; set; }
    internal Action? AfterAuthenticatedReservationForTests { get; set; }
    internal bool ReserveReadForTests() => ReserveRead();
    internal bool ReservePostForTests(
        RoomFlowTransportRoute route,
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
            RoomFlowWireService service = _service ??
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
        // Never let a synchronously available request run the handler on the
        // accept-loop continuation and stall admission of the bounded peers.
        await Task.Yield();
        byte[]? requestBuffer = null;
        byte[]? body = null;
        byte[]? response = null;
        bool exchangeOwned = false;
        bool reservedPost = false;
        bool serviceMayHaveRun = false;
        bool sent = false;
        bool terminalBody = false;
        try
        {
            using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(stopToken);
            lifetime.CancelAfter(RoomFlowTransportLimits.ConnectionLifetimeMilliseconds);
            ReceivedRequest received = await ReceiveToEofAsync(socket, lifetime.Token).ConfigureAwait(false);
            requestBuffer = received.Buffer;
            if (!received.Complete || requestBuffer is null ||
                !RoomFlowTransportRequestParser.TryParse(
                    requestBuffer.AsSpan(0, received.Length), _selection,
                    out ParsedRoomFlowTransportRequest parsed))
                return;
            if (!_authenticator.Matches(requestBuffer.AsSpan(
                    parsed.AuthorizationOffset, parsed.AuthorizationLength)))
                return;
            if (TerminalRequestedOrStopping()) return;

            string? decision = null;
            string? action = null;
            if (parsed.IsPost)
            {
                decision = Encoding.ASCII.GetString(requestBuffer,
                    parsed.DecisionOffset, parsed.DecisionLength);
                action = Encoding.ASCII.GetString(requestBuffer,
                    parsed.ActionOffset, parsed.ActionLength);
                if (!ReservePost(parsed.Route, decision, action))
                {
                    RequestTerminal();
                    return;
                }
                reservedPost = true;
            }
            else if (!ReserveRead())
            {
                RequestTerminal();
                return;
            }

            if (!TryOwnExchange())
            {
                RequestTerminal();
                return;
            }
            exchangeOwned = true;
#if ROOM_RELEASE_TEST_SEAM
            AfterAuthenticatedReservationForTests?.Invoke();
#endif
            if (!_authenticatedBucket.TryConsume())
            {
                if (reservedPost) RequestTerminal();
                return;
            }

            string method = parsed.IsPost ? "POST" : "GET";
            string route = parsed.Route switch
            {
                RoomFlowTransportRoute.ParentGet => RoomFlowWireProtocol.DecisionRoute,
                RoomFlowTransportRoute.ParentPost => RoomFlowWireProtocol.ActionRoute,
                RoomFlowTransportRoute.ItemGet => ItemWireV1Protocol.DecisionRoute,
                RoomFlowTransportRoute.ItemPost => ItemWireV1Protocol.ActionRoute,
                _ => throw new InvalidOperationException("Unknown route."),
            };
            OwnedByteDispatchResult dispatch = _frameQueue.Submit(() =>
            {
                serviceMayHaveRun = true;
#if ROOM_RELEASE_TEST_SEAM
                if (!parsed.IsPost) Interlocked.Increment(ref _readSubmissionCountForTests);
#endif
                RoomFlowWireService service = _service ??
                    throw new InvalidOperationException("Service unavailable.");
                return service.Handle(method, route, decision, action);
            });
            if (dispatch.Status != OwnedByteDispatchStatus.Success || dispatch.Value is null)
            {
                if (reservedPost || dispatch.Status is OwnedByteDispatchStatus.TimedOutAfterClaim or OwnedByteDispatchStatus.Fault)
                    RequestTerminal();
                return;
            }
            body = dispatch.Value;
            TerminalClassification classification = RoomFlowTerminalClassifier.Classify(
                parsed.Route, _selection, _nonce, body);
            if (classification == TerminalClassification.Invalid)
            {
                RequestTerminal();
                return;
            }
            terminalBody = classification == TerminalClassification.Terminal;
#if ROOM_RELEASE_TEST_SEAM
            if (parsed.IsPost && DropNextPostResponseForTests)
            {
                DropNextPostResponseForTests = false;
                RequestTerminal();
                return;
            }
#endif
            response = RoomFlowTransportHttpEncoder.Wrap(parsed.Route, body);
            await SendAllAsync(socket, response, lifetime.Token).ConfigureAwait(false);
            sent = true;
            Volatile.Write(ref _exchangeResponseSent, 1);
            if (terminalBody) RequestTerminal();
        }
        catch
        {
            if (reservedPost || serviceMayHaveRun || terminalBody) RequestTerminal();
        }
        finally
        {
            if ((reservedPost || serviceMayHaveRun || terminalBody) && !sent) RequestTerminal();
            Zero(response);
            Zero(body);
            Zero(requestBuffer);
            try { socket.Shutdown(SocketShutdown.Both); } catch { }
            socket.Dispose();
            if (exchangeOwned) FinishExchange();
        }
    }

#if ROOM_RELEASE_TEST_SEAM
    private int _readSubmissionCountForTests;
#endif

    private bool ReserveRead()
    {
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                _readCount >= RoomFlowTransportLimits.MaximumReads)
                return false;
            _readCount++;
            return true;
        }
    }

    private bool ReservePost(RoomFlowTransportRoute route, string decision, string action)
    {
        var identity = new PostIdentity(route, decision, action);
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                !_reservedPosts.Add(identity))
                return false;
            if (route == RoomFlowTransportRoute.ParentPost)
            {
                int maximum = _selection == RoomFlowSelection.Shop
                    ? RoomFlowTransportLimits.MaximumShopParentPosts
                    : RoomFlowTransportLimits.MaximumEventParentPosts;
                if (_parentPostCount >= maximum)
                {
                    _reservedPosts.Remove(identity);
                    return false;
                }
                _parentPostCount++;
            }
            else
            {
                if (_selection != RoomFlowSelection.Event ||
                    _itemPostCount >= RoomFlowTransportLimits.MaximumEventItemPosts)
                {
                    _reservedPosts.Remove(identity);
                    return false;
                }
                _itemPostCount++;
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
            Volatile.Write(ref _exchangeResponseSent, 0);
            if (Volatile.Read(ref _terminalRequested) == 0) return true;
            Interlocked.Exchange(ref _exchangeInFlight, 0);
            PublishTerminal();
            return false;
        }

        // A client can receive the final byte just before the prior worker
        // finishes local socket cleanup. Treat that bounded cleanup tail as
        // sequential only after the complete response is known to be sent.
        var wait = Stopwatch.StartNew();
        while (Volatile.Read(ref _exchangeInFlight) != 0 &&
            Volatile.Read(ref _exchangeResponseSent) == 0 &&
            Volatile.Read(ref _terminalRequested) == 0 &&
            wait.ElapsedMilliseconds < 250)
        {
            Thread.Yield();
        }
        if (Volatile.Read(ref _exchangeInFlight) != 0 &&
            Volatile.Read(ref _exchangeResponseSent) == 0)
            return false;
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
        PublishTerminal();
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
        byte[] buffer = new byte[RoomFlowTransportLimits.RequestBufferSize];
        bool transfer = false;
        try
        {
            using var header = CancellationTokenSource.CreateLinkedTokenSource(lifetimeToken);
            header.CancelAfter(RoomFlowTransportLimits.HeaderReadMilliseconds);
            int total = 0;
            while (total < buffer.Length)
            {
                int read = await socket.ReceiveAsync(
                    buffer.AsMemory(total, buffer.Length - total),
                    SocketFlags.None,
                    header.Token).ConfigureAwait(false);
                if (read == 0)
                {
                    if (total is < 1 or > RoomFlowTransportLimits.MaximumRequestHead) return default;
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
        write.CancelAfter(RoomFlowTransportLimits.ResponseWriteMilliseconds);
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
        (production ? endpoint.Port == RoomFlowTransportLimits.Port :
            endpoint.Port != RoomFlowTransportLimits.Port);

    private static void Zero(byte[]? value)
    {
        if (value is not null) CryptographicOperations.ZeroMemory(value);
    }

    private readonly record struct PostIdentity(
        RoomFlowTransportRoute Route,
        string Decision,
        string Action);

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

internal static class RoomFlowTerminalClassifier
{
    public static TerminalClassification Classify(
        RoomFlowTransportRoute route,
        RoomFlowSelection selection,
        string nonce,
        byte[] body)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(body);
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object) return TerminalClassification.Invalid;
            var properties = new List<JsonProperty>();
            foreach (JsonProperty property in root.EnumerateObject()) properties.Add(property);
            return route is RoomFlowTransportRoute.ItemGet or RoomFlowTransportRoute.ItemPost
                ? Item(route, properties, nonce)
                : Parent(route, properties, selection, nonce);
        }
        catch (JsonException)
        {
            return TerminalClassification.Invalid;
        }
    }

    private static TerminalClassification Parent(
        RoomFlowTransportRoute route,
        IReadOnlyList<JsonProperty> p,
        RoomFlowSelection selection,
        string nonce)
    {
        string flow = selection == RoomFlowSelection.Shop ? "shop" : "event";
        if (p.Count < 7 || !Number(p[0], "schema_version", 1) ||
            !Text(p[1], "protocol", "room_flows_v1") ||
            !Text(p[2], "version", flow + "_v1") ||
            !Text(p[3], "flow_kind", flow) || !Text(p[4], "session_nonce", nonce) ||
            !Number(p[5], "parent_ordinal", 1) || p[6].Name != "status" ||
            p[6].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        string? status = p[6].Value.GetString();
        bool allowed = route switch
        {
            RoomFlowTransportRoute.ParentGet when selection == RoomFlowSelection.Shop =>
                status is "ready" or "waiting" or "unsupported" or "complete" or "error",
            RoomFlowTransportRoute.ParentGet =>
                status is "ready" or "waiting" or "unsupported" or "item_child" or "resolved" or "error",
            RoomFlowTransportRoute.ParentPost =>
                status is "accepted" or "rejected" or "uncertain" or "unsupported" or "error",
            _ => false,
        };
        if (!allowed) return TerminalClassification.Invalid;
        int expected = status switch
        {
            "accepted" => 9,
            "rejected" or "uncertain" => 7,
            "error" => 8,
            "resolved" when selection == RoomFlowSelection.Event => 10,
            "ready" or "waiting" or "complete" when selection == RoomFlowSelection.Shop => 13,
            "ready" or "waiting" or "item_child" when selection == RoomFlowSelection.Event => 11,
            _ => -1,
        };
        if (status == "unsupported")
        {
            bool fixedFailure = p.Count == 7;
            bool observation = selection == RoomFlowSelection.Shop
                ? p.Count == 13 && ParentTailNames(p, selection, status)
                : p.Count == 11 && ParentTailNames(p, selection, status);
            bool valid = route == RoomFlowTransportRoute.ParentGet ? observation : fixedFailure;
            return valid
                ? TerminalClassification.Terminal
                : TerminalClassification.Invalid;
        }
        if (p.Count != expected || !ParentTailNames(p, selection, status!))
            return TerminalClassification.Invalid;
        if (status == "error" && !ErrorCode(p[7])) return TerminalClassification.Invalid;
        return status is "complete" or "resolved" or "rejected" or "uncertain" or "unsupported" or "error"
            ? TerminalClassification.Terminal
            : TerminalClassification.NonTerminal;
    }

    private static bool ParentTailNames(
        IReadOnlyList<JsonProperty> p,
        RoomFlowSelection selection,
        string status)
    {
        if (status == "accepted") return Names(p, 7, "decision_id", "action_id");
        if (status == "error") return Names(p, 7, "code");
        if (status is "rejected" or "uncertain") return p.Count == 7;
        if (status == "resolved") return Names(p, 7, "decision_id", "action_id", "result");
        return selection == RoomFlowSelection.Shop
            ? Names(p, 7, "phase", "decision_id", "player", "offers", "legal_actions", "prior_results")
            : Names(p, 7, "phase", "decision_id", "candidates", "legal_actions");
    }

    private static TerminalClassification Item(
        RoomFlowTransportRoute route,
        IReadOnlyList<JsonProperty> p,
        string nonce)
    {
        if (p.Count < 6 || !Number(p[0], "schema_version", 1) ||
            !Text(p[1], "protocol", "item_probe_v1") || !Text(p[2], "version", "item_v1") ||
            !Text(p[3], "session_nonce", nonce) || !Number(p[4], "surface_ordinal", 1) ||
            p[5].Name != "status" || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        string? status = p[5].Value.GetString();
        bool allowed = route switch
        {
            RoomFlowTransportRoute.ItemGet =>
                status is "waiting" or "ready" or "unsupported" or "resolved" or "error",
            RoomFlowTransportRoute.ItemPost =>
                status is "accepted" or "rejected" or "uncertain" or "unsupported" or "error",
            _ => false,
        };
        if (!allowed) return TerminalClassification.Invalid;
        bool shape = status switch
        {
            "waiting" or "unsupported" or "rejected" or "uncertain" => p.Count == 6,
            "ready" => p.Count == 10 && Names(p, 6, "decision_id", "offers", "potion_slots", "legal_actions"),
            "accepted" => p.Count == 8 && Names(p, 6, "decision_id", "action_id"),
            "resolved" => p.Count == 12 && Names(p, 6, "decision_id", "action_id", "offer_index", "kind", "key", "result"),
            "error" => p.Count == 7 && Names(p, 6, "code"),
            _ => false,
        };
        if (!shape || status == "error" && !ErrorCode(p[6]))
            return TerminalClassification.Invalid;
        return status is "unsupported" or "rejected" or "uncertain" or "error"
            ? TerminalClassification.Terminal
            : TerminalClassification.NonTerminal;
    }

    private static bool Names(IReadOnlyList<JsonProperty> p, int start, params string[] names)
    {
        if (p.Count != start + names.Length) return false;
        for (int index = 0; index < names.Length; index++)
            if (p[start + index].Name != names[index]) return false;
        return true;
    }

    private static bool Text(JsonProperty p, string name, string expected) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.String &&
        p.Value.GetString() == expected;

    private static bool Number(JsonProperty p, string name, int expected) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.Number &&
        p.Value.TryGetInt32(out int value) && value == expected;

    private static bool ErrorCode(JsonProperty p) =>
        p.Name == "code" && p.Value.ValueKind == JsonValueKind.String &&
        p.Value.GetString() is "invalid_request" or "internal_failure";
}
