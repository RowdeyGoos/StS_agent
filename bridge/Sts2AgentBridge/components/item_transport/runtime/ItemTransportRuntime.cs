using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Transport;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.ItemWireV1;

namespace Sts2AgentBridge.Successors.ItemTransportV1;

public sealed class ItemTransportRuntime : IDisposable
{
    private static readonly TimeSpan JoinTimeout =
        TimeSpan.FromMilliseconds(ItemTransportLimits.ShutdownJoinMilliseconds);

    private readonly object _gate = new();
    private readonly FixedTimeAuthenticator _authenticator;
    private readonly ItemWireV1Service _service;
    private readonly OwnedByteFrameQueue _frameQueue;
    private readonly MonotonicTokenBucket _preAuthenticationBucket;
    private readonly MonotonicTokenBucket _authenticatedBucket;
    private readonly SemaphoreSlim _handlerSlots = new(
        ItemTransportLimits.MaximumHandlers,
        ItemTransportLimits.MaximumHandlers);
    private readonly CancellationTokenSource _stopSource = new();
    private readonly ManualResetEventSlim _settled = new(false);
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
    private bool _dispositionStarted;
    private bool _cleanupComplete;
    private bool _settledDisposed;
    private int _joinWaiters;
    private int _postReserved;
    private int _terminal;
    private int _readSubmissionCount;

    private ItemTransportRuntime(
        FixedTimeAuthenticator authenticator,
        string nonce,
        IItemV1NativeAdapter adapter)
    {
        _authenticator = authenticator;
        _service = new ItemWireV1Service(nonce, adapter);
        _frameQueue = new OwnedByteFrameQueue(OnComponentStateChanged);
        _preAuthenticationBucket = new MonotonicTokenBucket(
            32.0, 16.0, StopwatchMonotonicClock.Instance);
        _authenticatedBucket = new MonotonicTokenBucket(
            20.0, 10.0, StopwatchMonotonicClock.Instance);
        _ownerThreadId = Environment.CurrentManagedThreadId;
    }

    public static ItemTransportRuntime? Create(
        byte[]? configuration,
        Func<byte[]?> credentialReader,
        IItemV1NativeAdapter adapter)
    {
        FixedTimeAuthenticator? authenticator = null;
        byte[]? credential = null;
        try
        {
            if (configuration is null ||
                ItemTransportConfiguration.Parse(configuration) !=
                    ItemTransportConfigurationState.Enabled ||
                credentialReader is null || adapter is null)
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
                var runtime = new ItemTransportRuntime(authenticator, nonce, adapter);
                authenticator = null;
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
            if (credential is not null)
            {
                CryptographicOperations.ZeroMemory(credential);
            }
            if (configuration is not null)
            {
                CryptographicOperations.ZeroMemory(configuration);
            }
            authenticator?.Dispose();
        }
    }

    public bool Start()
    {
        if (!TryReserveStart())
        {
            return false;
        }
        TcpListener? listener = null;
        try
        {
            listener = new TcpListener(IPAddress.Loopback, ItemTransportLimits.Port);
            listener.Start(ItemTransportLimits.Backlog);
            return StartCore(listener, requireProductionPort: true);
        }
        catch
        {
            try
            {
                listener?.Stop();
            }
            catch
            {
            }
            FailReservedStart();
            return false;
        }
    }

    internal bool StartForTests(TcpListener listener) =>
        StartForTests(listener, null);

    internal bool StartForTests(TcpListener listener, Action? afterReserved)
    {
        if (!TryReserveStart())
        {
            return false;
        }
        try
        {
            afterReserved?.Invoke();
            if (listener is null ||
                listener.Server.AddressFamily != AddressFamily.InterNetwork ||
                !listener.Server.IsBound ||
                listener.LocalEndpoint is not IPEndPoint endpoint ||
                !IsAllowedEndpoint(endpoint, production: false))
            {
                listener?.Stop();
                FailReservedStart();
                return false;
            }
            return StartCore(listener, requireProductionPort: false);
        }
        catch
        {
            try
            {
                listener?.Stop();
            }
            catch
            {
            }
            FailReservedStart();
            return false;
        }
    }

    public bool DrainFrame()
    {
        if (Environment.CurrentManagedThreadId != _ownerThreadId)
        {
            return false;
        }
        lock (_gate)
        {
            if (!_started || _stopping)
            {
                return false;
            }
        }
        return _frameQueue.DrainFrame();
    }

    public bool StopAndJoin()
    {
        var stopwatch = Stopwatch.StartNew();
        InitiateStop();
        lock (_gate)
        {
            if (_cleanupComplete)
            {
                return true;
            }
            _joinWaiters++;
        }
        bool complete;
        try
        {
            TimeSpan remaining = JoinTimeout - stopwatch.Elapsed;
            complete = remaining > TimeSpan.Zero && _settled.Wait(remaining);
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
            if (disposeSettled)
            {
                _settled.Dispose();
            }
        }
        return complete && IsStopped;
    }

    public bool IsStopped
    {
        get
        {
            lock (_gate)
            {
                return _cleanupComplete;
            }
        }
    }

    internal int ReadSubmissionCount => Volatile.Read(ref _readSubmissionCount);

    internal bool IsTerminal => Volatile.Read(ref _terminal) != 0;

    internal int OutstandingFrameCount => _frameQueue.OutstandingCount;

    internal bool IsStopping
    {
        get
        {
            lock (_gate)
            {
                return _stopping;
            }
        }
    }

    internal static bool IsAllowedTestEndpoint(IPEndPoint endpoint) =>
        IsAllowedEndpoint(endpoint, production: false);

    public void Dispose()
    {
        StopAndJoin();
    }

    private bool TryReserveStart()
    {
        lock (_gate)
        {
            if (_startAttempted || _stopping || _dispositionStarted)
            {
                return false;
            }
            _startAttempted = true;
            _startInProgress = true;
            return true;
        }
    }

    private bool StartCore(TcpListener listener, bool requireProductionPort)
    {
        try
        {
            lock (_gate)
            {
                if (_stopping || _dispositionStarted ||
                    listener.LocalEndpoint is not IPEndPoint endpoint ||
                    !IsAllowedEndpoint(endpoint, requireProductionPort))
                {
                    throw new InvalidOperationException("Invalid reserved listener.");
                }
                _started = true;
                _acceptCompleted = false;
                _listener = listener;
                CancellationToken stopToken = _stopSource.Token;
                _acceptTask = Task.Run(() => AcceptLoopAsync(listener, stopToken));
                _startInProgress = false;
                return true;
            }
        }
        catch
        {
            try
            {
                listener.Stop();
            }
            catch
            {
            }
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

    private async Task AcceptLoopAsync(
        TcpListener listener,
        CancellationToken cancellationToken)
    {
        bool unexpectedCompletion = false;
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                Socket socket;
                try
                {
                    socket = await listener.AcceptSocketAsync(cancellationToken)
                        .ConfigureAwait(false);
                }
                catch
                {
                    unexpectedCompletion = !cancellationToken.IsCancellationRequested;
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
                Task worker = HandleSocketAsync(socket, cancellationToken);
                lock (_gate)
                {
                    _workers.Add(worker);
                }
                _ = worker.ContinueWith(
                    _ => WorkerFinished(worker, socket),
                    CancellationToken.None,
                    TaskContinuationOptions.ExecuteSynchronously,
                    TaskScheduler.Default);
            }
        }
        finally
        {
            lock (_gate)
            {
                _acceptCompleted = true;
            }
            if (unexpectedCompletion)
            {
                MarkTerminal();
            }
            InitiateStop();
            OnComponentStateChanged();
        }
    }

    private async Task HandleSocketAsync(Socket socket, CancellationToken stopToken)
    {
        byte[]? requestBuffer = null;
        byte[]? body = null;
        byte[]? response = null;
        bool reservedPost = false;
        bool sent = false;
        try
        {
            using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(stopToken);
            lifetime.CancelAfter(ItemTransportLimits.ConnectionLifetimeMilliseconds);
            ReceivedRequest received = await ReceiveToEofAsync(socket, lifetime.Token)
                .ConfigureAwait(false);
            requestBuffer = received.Buffer;
            if (!received.Complete || requestBuffer is null ||
                !ItemTransportRequestParser.TryParse(
                    requestBuffer.AsSpan(0, received.Length), out ParsedItemTransportRequest parsed))
            {
                return;
            }
            if (!_authenticator.Matches(requestBuffer.AsSpan(
                    parsed.AuthorizationOffset, parsed.AuthorizationLength)))
            {
                return;
            }
            if (Volatile.Read(ref _terminal) != 0)
            {
                return;
            }
            if (parsed.IsPost)
            {
                if (Interlocked.CompareExchange(ref _postReserved, 1, 0) != 0)
                {
                    return;
                }
                reservedPost = true;
            }
            if (!_authenticatedBucket.TryConsume())
            {
                if (reservedPost)
                {
                    MarkTerminal();
                }
                return;
            }

            string? decision = null;
            string? action = null;
            if (parsed.IsPost)
            {
                decision = Encoding.ASCII.GetString(requestBuffer,
                    parsed.DecisionOffset, parsed.DecisionLength);
                action = Encoding.ASCII.GetString(requestBuffer,
                    parsed.ActionOffset, parsed.ActionLength);
            }
            OwnedByteDispatchResult dispatch = _frameQueue.Submit(() =>
            {
                if (!parsed.IsPost)
                {
                    Interlocked.Increment(ref _readSubmissionCount);
                }
                return _service.Handle(
                    parsed.IsPost ? "POST" : "GET",
                    parsed.IsPost ? ItemWireV1Protocol.ActionRoute :
                        ItemWireV1Protocol.DecisionRoute,
                    decision,
                    action);
            });
            if (dispatch.Status != OwnedByteDispatchStatus.Success || dispatch.Value is null)
            {
                if (reservedPost)
                {
                    MarkTerminal();
                }
                return;
            }
            body = dispatch.Value;
            if (lifetime.IsCancellationRequested || Volatile.Read(ref _terminal) != 0)
            {
                if (reservedPost)
                {
                    MarkTerminal();
                }
                return;
            }
            response = ItemTransportHttpEncoder.Wrap(body);
            await SendAllAsync(socket, response, lifetime.Token).ConfigureAwait(false);
            sent = true;
        }
        catch
        {
            if (reservedPost)
            {
                MarkTerminal();
            }
        }
        finally
        {
            if (reservedPost && !sent)
            {
                MarkTerminal();
            }
            Zero(response);
            Zero(body);
            Zero(requestBuffer);
            try
            {
                socket.Shutdown(SocketShutdown.Both);
            }
            catch
            {
            }
            socket.Dispose();
        }
    }

    private static async Task<ReceivedRequest> ReceiveToEofAsync(
        Socket socket,
        CancellationToken lifetimeToken)
    {
        byte[] buffer = new byte[ItemTransportLimits.RequestBufferSize];
        bool transfer = false;
        try
        {
            using var header = CancellationTokenSource.CreateLinkedTokenSource(lifetimeToken);
            header.CancelAfter(ItemTransportLimits.HeaderReadMilliseconds);
            int total = 0;
            while (total < buffer.Length)
            {
                int read = await socket.ReceiveAsync(
                    buffer.AsMemory(total, buffer.Length - total),
                    SocketFlags.None,
                    header.Token).ConfigureAwait(false);
                if (read == 0)
                {
                    if (total is < 1 or > ItemTransportLimits.MaximumRequestHead)
                    {
                        return default;
                    }
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
            if (!transfer)
            {
                Zero(buffer);
            }
        }
    }

    private static async Task SendAllAsync(
        Socket socket,
        byte[] response,
        CancellationToken lifetimeToken)
    {
        using var write = CancellationTokenSource.CreateLinkedTokenSource(lifetimeToken);
        write.CancelAfter(ItemTransportLimits.ResponseWriteMilliseconds);
        int sent = 0;
        while (sent < response.Length)
        {
            int count = await socket.SendAsync(
                response.AsMemory(sent), SocketFlags.None, write.Token)
                .ConfigureAwait(false);
            if (count <= 0)
            {
                throw new InvalidOperationException("Response write failed.");
            }
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

    private void MarkTerminal()
    {
        if (Interlocked.Exchange(ref _terminal, 1) == 0)
        {
            _frameQueue.Stop();
        }
    }

    private void InitiateStop()
    {
        TcpListener? listener;
        Socket[] sockets;
        lock (_gate)
        {
            if (_stopping)
            {
                return;
            }
            _stopping = true;
            _started = false;
            listener = _listener;
            sockets = new Socket[_activeSockets.Count];
            _activeSockets.CopyTo(sockets);
        }
        _stopSource.Cancel();
        try
        {
            listener?.Stop();
        }
        catch
        {
        }
        foreach (Socket socket in sockets)
        {
            try
            {
                socket.Dispose();
            }
            catch
            {
            }
        }
        _frameQueue.Stop();
        OnComponentStateChanged();
    }

    private void OnComponentStateChanged()
    {
        bool disposeResources = false;
        lock (_gate)
        {
            bool ready = _stopping && !_startInProgress && _acceptCompleted &&
                _workers.Count == 0 &&
                _frameQueue.IsSettled;
            if (ready && !_dispositionStarted)
            {
                _dispositionStarted = true;
                disposeResources = true;
            }
        }
        if (disposeResources)
        {
            DisposeResources();
        }
    }

    private void DisposeResources()
    {
        _authenticator.Dispose();
        _frameQueue.Dispose();
        _handlerSlots.Dispose();
        _stopSource.Dispose();
        bool disposeSettled;
        lock (_gate)
        {
            _cleanupComplete = true;
            _settled.Set();
            disposeSettled = ShouldDisposeSettledLocked();
        }
        if (disposeSettled)
        {
            _settled.Dispose();
        }
    }

    private bool ShouldDisposeSettledLocked()
    {
        if (!_cleanupComplete || _joinWaiters != 0 || _settledDisposed)
        {
            return false;
        }
        _settledDisposed = true;
        return true;
    }

    private static bool IsAllowedEndpoint(IPEndPoint endpoint, bool production) =>
        endpoint.AddressFamily == AddressFamily.InterNetwork &&
        IPAddress.Loopback.Equals(endpoint.Address) &&
        endpoint.Port is >= 1 and <= 65535 &&
        (production
            ? endpoint.Port == ItemTransportLimits.Port
            : endpoint.Port != ItemTransportLimits.Port);

    private static void Zero(byte[]? value)
    {
        if (value is not null)
        {
            CryptographicOperations.ZeroMemory(value);
        }
    }

    private readonly record struct ReceivedRequest(
        bool Complete,
        byte[]? Buffer,
        int Length);
}
