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
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

public sealed class CardSelectionTransportRuntime : IDisposable
{
    private static readonly TimeSpan JoinTimeout =
        TimeSpan.FromMilliseconds(CardSelectionTransportLimits.ShutdownJoinMilliseconds);

    private readonly object _gate = new();
    private readonly FixedTimeAuthenticator _authenticator;
    private CardSelectionV1WireService? _service;
    private readonly CardSelectionReleaseSelection _selection;
    private readonly string _nonce;
    private readonly OwnedByteFrameQueue _frameQueue;
    private readonly MonotonicTokenBucket _preAuthenticationBucket;
    private readonly MonotonicTokenBucket _authenticatedBucket;
    private readonly SemaphoreSlim _handlerSlots = new(
        CardSelectionTransportLimits.MaximumHandlers,
        CardSelectionTransportLimits.MaximumHandlers);
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

    private CardSelectionTransportRuntime(
        FixedTimeAuthenticator authenticator,
        CardSelectionReleaseSelection selection,
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

    public static CardSelectionTransportRuntime? Create(
        byte[]? configuration,
        Func<byte[]?> credentialReader,
        Func<CardSelectionReleaseSelection, string, CardSelectionV1WireService> factory)
    {
        FixedTimeAuthenticator? authenticator = null;
        byte[]? credential = null;
        try
        {
            if (configuration is null ||
                !CardSelectionTransportConfiguration.TryParse(configuration, out CardSelectionReleaseSelection selection) ||
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
                var runtime = new CardSelectionTransportRuntime(authenticator, selection, nonce);
                authenticator = null;
                CardSelectionV1WireService service;
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
            listener = new TcpListener(IPAddress.Loopback, CardSelectionTransportLimits.Port);
            listener.Start(CardSelectionTransportLimits.Backlog);
            return StartCore(listener, production: true);
        }
        catch
        {
            try { listener?.Stop(); } catch { }
            FailReservedStart();
            return false;
        }
    }

#if CARD_SELECTION_RELEASE_TEST_SEAM
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
        CardSelectionTransportRoute route,
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
            CardSelectionV1WireService service = _service ??
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
        bool authenticatedCleanupParticipant = false;
        bool reservedPost = false;
        bool serviceMayHaveRun = false;
        bool sent = false;
        bool terminalBody = false;
        bool terminalAfterCleanup = false;
        try
        {
            using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(stopToken);
            lifetime.CancelAfter(CardSelectionTransportLimits.ConnectionLifetimeMilliseconds);
            ReceivedRequest received = await ReceiveToEofAsync(socket, lifetime.Token).ConfigureAwait(false);
            requestBuffer = received.Buffer;
            if (!received.Complete || requestBuffer is null ||
                !CardSelectionTransportRequestParser.TryParse(
                    requestBuffer.AsSpan(0, received.Length), _selection,
                    out ParsedCardSelectionTransportRequest parsed))
                return;
            if (!_authenticator.Matches(requestBuffer.AsSpan(
                    parsed.AuthorizationOffset, parsed.AuthorizationLength)))
                return;
            Interlocked.Increment(ref _authenticatedCleanupParticipants);
            authenticatedCleanupParticipant = true;
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
#if CARD_SELECTION_RELEASE_TEST_SEAM
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
            string route = parsed.Route switch
            {
                CardSelectionTransportRoute.ParentGet => CardSelectionV1WireProtocol.ParentRoute,
                CardSelectionTransportRoute.ParentPost => CardSelectionV1WireProtocol.ParentActionRoute,
                CardSelectionTransportRoute.ChildGet => CardSelectionV1WireProtocol.ChildRoute,
                CardSelectionTransportRoute.ChildPost => CardSelectionV1WireProtocol.ChildActionRoute,
                _ => throw new InvalidOperationException("Unknown route."),
            };
            OwnedByteDispatchResult dispatch = _frameQueue.Submit(() =>
            {
                serviceMayHaveRun = true;
#if CARD_SELECTION_RELEASE_TEST_SEAM
                if (!parsed.IsPost) Interlocked.Increment(ref _readSubmissionCountForTests);
#endif
                CardSelectionV1WireService service = _service ??
                    throw new InvalidOperationException("Service unavailable.");
                byte[]? ownedServiceBody = null;
                try
                {
                    if (parsed.IsPost)
                    {
                        ownedServiceBody = CardSelectionTransportServiceBody.Build(decision!, action!);
#if CARD_SELECTION_RELEASE_TEST_SEAM
                        ServiceBodyOwnedForTests?.Invoke(ownedServiceBody);
#endif
                    }
                    CardSelectionV1WireResponse result = service.Handle(method, route, ownedServiceBody);
                    return new OwnedServiceResponse(result.StatusCode, result.Body);
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
            TerminalClassification classification = CardSelectionTerminalClassifier.Classify(
                parsed.Route, _selection, _nonce, dispatch.StatusCode, body);
            if (classification == TerminalClassification.Invalid)
            {
                terminalAfterCleanup = true;
                LatchTerminal();
                return;
            }
            terminalBody = classification == TerminalClassification.Terminal;
#if CARD_SELECTION_RELEASE_TEST_SEAM
            if (parsed.IsPost && DropNextPostResponseForTests)
            {
                DropNextPostResponseForTests = false;
                terminalAfterCleanup = true;
                LatchTerminal();
                return;
            }
#endif
            response = CardSelectionTransportHttpEncoder.Wrap(body);
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
#if CARD_SELECTION_RELEASE_TEST_SEAM
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

#if CARD_SELECTION_RELEASE_TEST_SEAM
    private int _readSubmissionCountForTests;
    internal Action<byte[]>? ServiceBodyOwnedForTests { get; set; }
    internal Action<byte[]?, Socket>? BeforeTerminalCleanupForTests { get; set; }
#endif

    private bool ReserveRead()
    {
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                _readCount >= CardSelectionTransportLimits.MaximumReads)
                return false;
            _readCount++;
            return true;
        }
    }

    private bool ReservePost(CardSelectionTransportRoute route, string decision, string action)
    {
        var identity = new PostIdentity(route, decision, action);
        lock (_gate)
        {
            if (_stopping || Volatile.Read(ref _terminalRequested) != 0 ||
                !_reservedPosts.Add(identity))
                return false;
            if (route == CardSelectionTransportRoute.ParentPost)
            {
                if (_parentPostCount >= CardSelectionTransportLimits.MaximumParentPosts)
                {
                    _reservedPosts.Remove(identity);
                    return false;
                }
                _parentPostCount++;
            }
            else
            {
                if (route != CardSelectionTransportRoute.ChildPost ||
                    _childPostCount >= CardSelectionTransportLimits.MaximumChildPosts)
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
        byte[] buffer = new byte[CardSelectionTransportLimits.RequestBufferSize];
        bool transfer = false;
        try
        {
            using var header = CancellationTokenSource.CreateLinkedTokenSource(lifetimeToken);
            header.CancelAfter(CardSelectionTransportLimits.HeaderReadMilliseconds);
            int total = 0;
            while (total < buffer.Length)
            {
                int read = await socket.ReceiveAsync(
                    buffer.AsMemory(total, buffer.Length - total),
                    SocketFlags.None,
                    header.Token).ConfigureAwait(false);
                if (read == 0)
                {
                    if (total is < 1 or > CardSelectionTransportLimits.MaximumRequestHead) return default;
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
        write.CancelAfter(CardSelectionTransportLimits.ResponseWriteMilliseconds);
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
        (production ? endpoint.Port == CardSelectionTransportLimits.Port :
            endpoint.Port != CardSelectionTransportLimits.Port);

    private static void Zero(byte[]? value)
    {
        if (value is not null) CryptographicOperations.ZeroMemory(value);
    }

    private readonly record struct PostIdentity(
        CardSelectionTransportRoute Route,
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

internal static class CardSelectionTerminalClassifier
{
    internal static TerminalClassification Classify(
        CardSelectionTransportRoute route,
        CardSelectionReleaseSelection selection,
        string nonce,
        int statusCode,
        byte[] body)
    {
        byte[]? canonical = null;
        try
        {
            if (!Enum.IsDefined(route) || !Enum.IsDefined(selection) ||
                !LowerHex(nonce, 32) || body.Length is < 1 or > CardSelectionTransportLimits.MaximumBody)
                return TerminalClassification.Invalid;
            foreach (byte value in body)
                if (value is < 0x20 or > 0x7e) return TerminalClassification.Invalid;
            using JsonDocument document = JsonDocument.Parse(body, new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 64,
            });
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object) return TerminalClassification.Invalid;
            canonical = JsonSerializer.SerializeToUtf8Bytes(root);
            if (!canonical.AsSpan().SequenceEqual(body)) return TerminalClassification.Invalid;
            var properties = new List<JsonProperty>();
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in root.EnumerateObject())
            {
                if (!names.Add(property.Name)) return TerminalClassification.Invalid;
                properties.Add(property);
            }
            if (properties.Count < 2 || !Number(properties[0], "schema_version", 1) ||
                properties[1].Name != "kind" || properties[1].Value.ValueKind != JsonValueKind.String)
                return TerminalClassification.Invalid;
            string? kind = properties[1].Value.GetString();
            if (kind == "error") return Error(statusCode, properties);
            if (statusCode != 200) return TerminalClassification.Invalid;
            return route switch
            {
                CardSelectionTransportRoute.ParentGet => ParentGet(selection, nonce, kind, properties),
                CardSelectionTransportRoute.ParentPost => ParentPost(nonce, kind, properties),
                CardSelectionTransportRoute.ChildGet => ChildGet(selection, nonce, kind, properties),
                CardSelectionTransportRoute.ChildPost => ChildPost(nonce, kind, properties),
                _ => TerminalClassification.Invalid,
            };
        }
        catch (JsonException) { return TerminalClassification.Invalid; }
        catch (NotSupportedException) { return TerminalClassification.Invalid; }
        finally { if (canonical is not null) CryptographicOperations.ZeroMemory(canonical); }
    }

    private static TerminalClassification Error(int statusCode, IReadOnlyList<JsonProperty> p)
    {
        if (!Names(p, "schema_version", "kind", "status", "code") ||
            !Text(p[1], "kind", "error") || !Text(p[2], "status", "error") ||
            p[3].Value.ValueKind != JsonValueKind.String) return TerminalClassification.Invalid;
        string? code = p[3].Value.GetString();
        return statusCode == 400 && code == "invalid_request" ||
               statusCode == 500 && code == "internal_failure"
            ? TerminalClassification.Terminal : TerminalClassification.Invalid;
    }

    private static TerminalClassification ParentGet(
        CardSelectionReleaseSelection selection, string nonce, string? kind,
        IReadOnlyList<JsonProperty> p)
    {
        if (kind == "parent_resolved")
        {
            if (!Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "status", "result", "begin_decision_id", "begin_action_id",
                    "proceed_decision_id", "proceed_action_id") ||
                !ParentCommon(p, nonce) || !Text(p[5], "status", "resolved") ||
                !Text(p[6], "result", "map_handoff") ||
                !HexText(p[7], "begin_decision_id", 64) || !Text(p[8], "begin_action_id", "begin") ||
                !HexText(p[9], "proceed_decision_id", 64) || !Text(p[10], "proceed_action_id", "proceed"))
                return TerminalClassification.Invalid;
            return TerminalClassification.Terminal;
        }
        if (kind != "parent_observation" ||
            !Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                "status", "phase", "parent_kind", "policy", "decision_id", "legal_actions") ||
            !ParentCommon(p, nonce) || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        string? status = p[5].Value.GetString();
        string? phase = StringValue(p[6]);
        if (status == "ready")
        {
            bool pair = selection == CardSelectionReleaseSelection.Cheese
                ? Text(p[7], "parent_kind", "event") && Text(p[8], "policy", "cheese_gorge_add_two")
                : selection == CardSelectionReleaseSelection.Smith &&
                  Text(p[7], "parent_kind", "rest") && Text(p[8], "policy", "rest_smith_upgrade_one");
            bool action = phase == "initial" ? SingleText(p[10], "legal_actions", "begin") :
                phase == "after" && SingleText(p[10], "legal_actions", "proceed");
            return pair && action && HexText(p[9], "decision_id", 64)
                ? TerminalClassification.NonTerminal : TerminalClassification.Invalid;
        }
        bool fixedShape = Text(p[7], "parent_kind", "") && Text(p[8], "policy", "") &&
            Text(p[9], "decision_id", "") && EmptyArray(p[10], "legal_actions");
        if (!fixedShape) return TerminalClassification.Invalid;
        if (status == "waiting" && phase is ("initial" or "transient" or "card_child" or "after" or "exit"))
            return TerminalClassification.NonTerminal;
        if (status == "unsupported" && phase == "unsupported") return TerminalClassification.Terminal;
        return TerminalClassification.Invalid;
    }

    private static TerminalClassification ParentPost(
        string nonce, string? kind, IReadOnlyList<JsonProperty> p)
    {
        if (kind == "parent_receipt")
        {
            if (!Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "decision_id", "action_id", "outcome") || !ParentCommon(p, nonce) ||
                !HexText(p[5], "decision_id", 64) || !ParentAction(p[6]) ||
                !Text(p[7], "outcome", "accepted")) return TerminalClassification.Invalid;
            return TerminalClassification.NonTerminal;
        }
        if (kind != "parent_failure" ||
            !Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal", "outcome") ||
            !ParentCommon(p, nonce) || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        return p[5].Value.GetString() is "rejected" or "unsupported" or "uncertain"
            ? TerminalClassification.Terminal : TerminalClassification.Invalid;
    }

    private static TerminalClassification ChildGet(
        CardSelectionReleaseSelection selection, string nonce, string? kind,
        IReadOnlyList<JsonProperty> p)
    {
        if (kind == "child_resolved")
        {
            if (!Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "status", "phase", "operation", "selected_cards", "prior_results") ||
                !ChildCommon(p, nonce) || !Text(p[5], "status", "resolved") ||
                !Text(p[6], "phase", "complete") || !SelectionOperation(selection, p[7]) ||
                !ResolvedCards(selection, p[8]) || !ResolvedHistory(selection, p[9]))
                return TerminalClassification.Invalid;
            return TerminalClassification.NonTerminal;
        }
        if (kind != "child_observation" ||
            !Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                "status", "phase", "operation", "commit_mode", "min_select", "max_select",
                "decision_id", "candidates", "selected_slots", "legal_actions", "prior_results") ||
            !ChildCommon(p, nonce) || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        string? status = p[5].Value.GetString();
        string? phase = StringValue(p[6]);
        if (status == "ready")
        {
            bool policy = selection == CardSelectionReleaseSelection.Cheese
                ? Text(p[7], "operation", "add") && Text(p[8], "commit_mode", "auto_at_max") &&
                  Number(p[9], "min_select", 2) && Number(p[10], "max_select", 2)
                : selection == CardSelectionReleaseSelection.Smith &&
                  Text(p[7], "operation", "upgrade") && Text(p[8], "commit_mode", "preview_confirm") &&
                  Number(p[9], "min_select", 1) && Number(p[10], "max_select", 1);
            return policy && phase is ("selecting" or "preview") &&
                HexText(p[11], "decision_id", 64) && Candidates(p[12], 1, 64, false) &&
                SelectedSlots(p[13]) && LegalActions(p[14]) && History(p[15])
                ? TerminalClassification.NonTerminal : TerminalClassification.Invalid;
        }
        bool fixedShape = Text(p[7], "operation", "") && Text(p[8], "commit_mode", "") &&
            Number(p[9], "min_select", 0) && Number(p[10], "max_select", 0) &&
            Text(p[11], "decision_id", "") && EmptyArray(p[12], "candidates") &&
            EmptyArray(p[13], "selected_slots") && EmptyArray(p[14], "legal_actions") &&
            History(p[15]);
        if (!fixedShape) return TerminalClassification.Invalid;
        if (status == "waiting" && phase is ("selecting" or "submitted" or "transient"))
            return TerminalClassification.NonTerminal;
        if (status == "unsupported" && phase == "unsupported") return TerminalClassification.Terminal;
        return TerminalClassification.Invalid;
    }

    private static TerminalClassification ChildPost(
        string nonce, string? kind, IReadOnlyList<JsonProperty> p)
    {
        if (kind == "child_receipt")
        {
            if (!Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "decision_id", "action_id", "outcome") || !ChildCommon(p, nonce) ||
                !HexText(p[5], "decision_id", 64) || !ChildAction(p[6]) ||
                !Text(p[7], "outcome", "accepted")) return TerminalClassification.Invalid;
            return TerminalClassification.NonTerminal;
        }
        if (kind != "child_failure" ||
            !Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal", "outcome") ||
            !ChildCommon(p, nonce) || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        return p[5].Value.GetString() is "rejected" or "unsupported" or "uncertain"
            ? TerminalClassification.Terminal : TerminalClassification.Invalid;
    }

    private static bool ParentCommon(IReadOnlyList<JsonProperty> p, string nonce) =>
        Text(p[2], "version", "card_selection_parent_v1") &&
        Text(p[3], "session_nonce", nonce) && Number(p[4], "parent_ordinal", 1);

    private static bool ChildCommon(IReadOnlyList<JsonProperty> p, string nonce) =>
        Text(p[2], "version", "card_selection_v1") &&
        Text(p[3], "session_nonce", nonce) && Number(p[4], "parent_ordinal", 1);

    private static bool SelectionOperation(CardSelectionReleaseSelection selection, JsonProperty p) =>
        selection == CardSelectionReleaseSelection.Cheese
            ? Text(p, "operation", "add")
            : selection == CardSelectionReleaseSelection.Smith && Text(p, "operation", "upgrade");

    private static bool ParentAction(JsonProperty p) => p.Name == "action_id" &&
        p.Value.ValueKind == JsonValueKind.String && p.Value.GetString() is ("begin" or "proceed");

    private static bool ChildAction(JsonProperty p)
    {
        if (p.Name != "action_id" || p.Value.ValueKind != JsonValueKind.String) return false;
        string? value = p.Value.GetString();
        return value is not null && ChildActionValue(value);
    }

    private static bool ChildActionValue(string value)
    {
        if (value is "preview" or "confirm") return true;
        if (!value.StartsWith("select:", StringComparison.Ordinal)) return false;
        string suffix = value[7..];
        if (suffix.Length is < 1 or > 2 || suffix.Length > 1 && suffix[0] == '0') return false;
        int slot = 0;
        foreach (char c in suffix)
        {
            if (c is < '0' or > '9') return false;
            slot = slot * 10 + c - '0';
        }
        return slot < 64;
    }

    private static bool Candidates(JsonProperty property, int minimum, int maximum, bool requireSelected)
    {
        if (property.Value.ValueKind != JsonValueKind.Array ||
            property.Value.GetArrayLength() is < 0 or > 64 ||
            property.Value.GetArrayLength() < minimum || property.Value.GetArrayLength() > maximum)
            return false;
        var slots = new HashSet<int>();
        foreach (JsonElement item in property.Value.EnumerateArray())
        {
            if (!Object(item, out List<JsonProperty>? p) ||
                !Names(p, "slot", "key", "upgrade_level", "visible", "enabled", "selected") ||
                !Int(p[0], "slot", 0, 63, out int slot) || !slots.Add(slot) ||
                !StableKey(p[1], "key") || !Int(p[2], "upgrade_level", 0, int.MaxValue, out _) ||
                !Boolean(p[3], "visible") || !Boolean(p[4], "enabled") || !Boolean(p[5], "selected") ||
                requireSelected && !p[5].Value.GetBoolean())
                return false;
        }
        return true;
    }

    private static bool SelectedSlots(JsonProperty property)
    {
        if (property.Name != "selected_slots" || property.Value.ValueKind != JsonValueKind.Array ||
            property.Value.GetArrayLength() > 8) return false;
        var slots = new HashSet<int>();
        foreach (JsonElement item in property.Value.EnumerateArray())
            if (item.ValueKind != JsonValueKind.Number || !item.TryGetInt32(out int slot) ||
                slot is < 0 or > 63 || !slots.Add(slot)) return false;
        return true;
    }

    private static bool LegalActions(JsonProperty property)
    {
        if (property.Name != "legal_actions" || property.Value.ValueKind != JsonValueKind.Array ||
            property.Value.GetArrayLength() > 65) return false;
        var actions = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonElement item in property.Value.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.String) return false;
            string? value = item.GetString();
            if (value is null || !actions.Add(value) || !ChildActionValue(value)) return false;
        }
        return true;
    }

    private static bool History(JsonProperty property)
    {
        if (property.Name != "prior_results" || property.Value.ValueKind != JsonValueKind.Array ||
            property.Value.GetArrayLength() > 10) return false;
        var decisions = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonElement item in property.Value.EnumerateArray())
        {
            if (!Object(item, out List<JsonProperty>? p) ||
                !Names(p, "decision_id", "action_id", "result") ||
                !HexText(p[0], "decision_id", 64) || !decisions.Add(p[0].Value.GetString()!) ||
                p[1].Value.ValueKind != JsonValueKind.String || p[2].Value.ValueKind != JsonValueKind.String)
                return false;
            string? action = p[1].Value.GetString();
            string? result = p[2].Value.GetString();
            if (action is null || !ChildActionValue(action) || result != ResultFor(action)) return false;
        }
        return true;
    }

    private static bool ResolvedCards(CardSelectionReleaseSelection selection, JsonProperty property)
    {
        int count = selection == CardSelectionReleaseSelection.Cheese ? 2 : 1;
        return property.Name == "selected_cards" && Candidates(property, count, count, true);
    }

    private static bool ResolvedHistory(CardSelectionReleaseSelection selection, JsonProperty property)
    {
        if (!History(property)) return false;
        JsonElement.ArrayEnumerator values = property.Value.EnumerateArray();
        if (selection == CardSelectionReleaseSelection.Cheese)
        {
            if (property.Value.GetArrayLength() != 2) return false;
            foreach (JsonElement item in values)
                if (!item.GetProperty("action_id").GetString()!.StartsWith("select:", StringComparison.Ordinal))
                    return false;
            return true;
        }
        if (selection != CardSelectionReleaseSelection.Smith || property.Value.GetArrayLength() != 2)
            return false;
        values.MoveNext();
        JsonElement first = values.Current;
        values.MoveNext();
        JsonElement second = values.Current;
        return first.GetProperty("action_id").GetString()!.StartsWith("select:", StringComparison.Ordinal) &&
            second.GetProperty("action_id").GetString() == "confirm";
    }

    private static bool Object(JsonElement value, out List<JsonProperty> properties)
    {
        properties = new List<JsonProperty>();
        if (value.ValueKind != JsonValueKind.Object) return false;
        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in value.EnumerateObject())
        {
            if (!names.Add(property.Name)) return false;
            properties.Add(property);
        }
        return true;
    }

    private static bool Int(JsonProperty property, string name, int minimum, int maximum, out int value)
    {
        value = 0;
        return property.Name == name && property.Value.ValueKind == JsonValueKind.Number &&
            property.Value.TryGetInt32(out value) && value >= minimum && value <= maximum;
    }

    private static bool Boolean(JsonProperty property, string name) =>
        property.Name == name && property.Value.ValueKind is JsonValueKind.True or JsonValueKind.False;

    private static bool StableKey(JsonProperty property, string name)
    {
        if (property.Name != name || property.Value.ValueKind != JsonValueKind.String) return false;
        string? value = property.Value.GetString();
        if (value is null || value.Length is < 1 or > 128) return false;
        foreach (char c in value)
            if (!(c is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9' or '_')) return false;
        return true;
    }

    private static string ResultFor(string action) =>
        action.StartsWith("select:", StringComparison.Ordinal) ? "selected" :
        action == "preview" ? "previewed" : "committed";

    private static bool Names(IReadOnlyList<JsonProperty> p, params string[] names)
    {
        if (p.Count != names.Length) return false;
        for (int index = 0; index < names.Length; index++)
            if (p[index].Name != names[index]) return false;
        return true;
    }

    private static bool Text(JsonProperty p, string name, string expected) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.String && p.Value.GetString() == expected;

    private static string? StringValue(JsonProperty p) =>
        p.Value.ValueKind == JsonValueKind.String ? p.Value.GetString() : null;

    private static bool Number(JsonProperty p, string name, int expected) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.Number &&
        p.Value.TryGetInt32(out int value) && value == expected;

    private static bool Array(JsonProperty p, string name) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.Array;

    private static bool EmptyArray(JsonProperty p, string name) =>
        Array(p, name) && p.Value.GetArrayLength() == 0;

    private static bool SingleText(JsonProperty p, string name, string expected)
    {
        if (!Array(p, name) || p.Value.GetArrayLength() != 1) return false;
        JsonElement item = p.Value[0];
        return item.ValueKind == JsonValueKind.String && item.GetString() == expected;
    }

    private static bool HexText(JsonProperty p, string name, int length) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.String && LowerHex(p.Value.GetString(), length);

    private static bool LowerHex(string? value, int length)
    {
        if (value is null || value.Length != length) return false;
        foreach (char c in value)
            if (c is not (>= '0' and <= '9') and not (>= 'a' and <= 'f')) return false;
        return true;
    }
}
