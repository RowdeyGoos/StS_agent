using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.ItemTransportV1.Tests;

internal static class Program
{
    private const string Token =
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    private static readonly byte[] EnabledConfiguration = Encoding.ASCII.GetBytes(
        "{\"schema_version\":\"item_probe_v1_transport_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static readonly byte[] DisabledConfiguration = Encoding.ASCII.GetBytes(
        "{\"schema_version\":\"item_probe_v1_transport_config_v1\",\"enabled\":false,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static int _checkCount;

    private static int Main(string[] arguments)
    {
        if (arguments.Length == 2 && arguments[0] == "--fixture")
        {
            return RunFixture(arguments[1]);
        }
        if (arguments.Length != 0)
        {
            return 2;
        }
        Run("configuration_factory", ConfigurationFactory);
        Run("parser_exact_grammar", ParserExactGrammar);
        Run("queue_success_and_timeout_before_claim", QueueSuccessAndTimeoutBeforeClaim);
        Run("queue_claimed_timeout_zeroes_late_result", QueueClaimedTimeoutZeroesLateResult);
        Run("ephemeral_get_and_owner_thread", EphemeralGetAndOwnerThread);
        Run("post_reservation_and_resolution", PostReservationAndResolution);
        Run("half_close_and_trailing_rejection", HalfCloseAndTrailingRejection);
        Run("terminal_retires_prequeued_reads", TerminalRetiresPrequeuedReads);
        Run("start_failure_and_accept_fault", StartFailureAndAcceptFault);
        Run("deferred_cleanup_after_false_join", DeferredCleanupAfterFalseJoin);
        Run("shutdown_idempotence", ShutdownIdempotence);
        Console.WriteLine(
            "{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"item_v1_transport_runtime\",\"check_count\":" +
            _checkCount + "}");
        return 0;
    }

    private static int RunFixture(string scenario)
    {
        if (!FixtureAdapter.IsKnown(scenario))
        {
            return 2;
        }
        var adapter = new FixtureAdapter(scenario);
        ItemTransportRuntime? runtime = CreateRuntime(adapter);
        if (runtime is null)
        {
            return 5;
        }
        var listener = new TcpListener(IPAddress.Loopback, 0);
        try
        {
            listener.Start(8);
            if (!runtime.StartForTests(listener) ||
                listener.LocalEndpoint is not IPEndPoint endpoint)
            {
                return 5;
            }
            Console.WriteLine("{\"port\":" + endpoint.Port + "}");
            Console.Out.Flush();
            Task<string> eof = Task.Run(Console.In.ReadToEnd);
            var lifetime = Stopwatch.StartNew();
            while (!eof.IsCompleted && lifetime.Elapsed < TimeSpan.FromSeconds(20))
            {
                runtime.DrainFrame();
                Thread.Sleep(1);
            }
            if (!eof.IsCompleted)
            {
                runtime.StopAndJoin();
                return 5;
            }
            if (!runtime.StopAndJoin() || !runtime.IsStopped)
            {
                return 5;
            }
            Console.Error.Write(
                "{\"dispatch_count\":" + adapter.DispatchCount +
                ",\"last_action_index\":" + adapter.LastActionIndex +
                ",\"read_count\":" + runtime.ReadSubmissionCount +
                ",\"stopped\":true}\n");
            return 0;
        }
        finally
        {
            runtime.Dispose();
            listener.Stop();
        }
    }

    private static void ConfigurationFactory()
    {
        var adapter = new FixtureAdapter("relic_success");
        int reads = 0;
        Check(ItemTransportRuntime.Create(null, () => { reads++; return null; }, adapter) is null &&
              reads == 0, "missing config no credential");
        byte[] disabled = DisabledConfiguration.ToArray();
        Check(ItemTransportRuntime.Create(disabled, () => { reads++; return null; }, adapter) is null &&
              reads == 0 && disabled.All(value => value == 0), "disabled cleanup");
        byte[] old = Encoding.ASCII.GetBytes(
            "{\"schema_version\":\"live_probe_v0_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
        Check(ItemTransportRuntime.Create(old, () => { reads++; return null; }, adapter) is null &&
              reads == 0 && old.All(value => value == 0), "old config rejected");

        byte[] configuration = EnabledConfiguration.ToArray();
        byte[] credential = Encoding.ASCII.GetBytes(Token);
        ItemTransportRuntime? runtime = ItemTransportRuntime.Create(
            configuration, () => { reads++; return credential; }, adapter);
        Check(runtime is not null && reads == 1 &&
              configuration.All(value => value == 0) && credential.All(value => value == 0),
            "enabled ownership cleanup");
        Check(runtime!.StopAndJoin() && runtime.IsStopped, "unstarted runtime stops");

        byte[] invalidCredential = Encoding.ASCII.GetBytes(new string('B', 64));
        Check(ItemTransportRuntime.Create(
                  EnabledConfiguration.ToArray(), () => invalidCredential, adapter) is null &&
              invalidCredential.All(value => value == 0), "invalid credential cleanup");
    }

    private static void ParserExactGrammar()
    {
        byte[] get = GetRequest(Token);
        Check(ItemTransportRequestParser.TryParse(get, out ParsedItemTransportRequest parsed) &&
              !parsed.IsPost && parsed.AuthorizationLength == 64, "exact get");
        byte[] post = PostRequest(Token, new string('a', 64), "collect:255");
        Check(ItemTransportRequestParser.TryParse(post, out parsed) && parsed.IsPost &&
              Encoding.ASCII.GetString(post, parsed.ActionOffset, parsed.ActionLength) ==
                  "collect:255", "exact post");
        foreach (byte[] invalid in new[]
        {
            get.Concat(new byte[] { (byte)'X' }).ToArray(),
            Encoding.ASCII.GetBytes(Text(get).Replace("Host:", "host:", StringComparison.Ordinal)),
            Encoding.ASCII.GetBytes(Text(get).Replace(
                "Connection: close\r\n", "Origin: x\r\nConnection: close\r\n",
                StringComparison.Ordinal)),
            Encoding.ASCII.GetBytes(Text(get).Replace("\r\n", "\n", StringComparison.Ordinal)),
            PostRequest(Token, new string('a', 64), "collect:01"),
            PostRequest(Token, new string('a', 63), "collect:1"),
        })
        {
            Check(!ItemTransportRequestParser.TryParse(invalid, out _), "invalid grammar");
        }
    }

    private static void QueueSuccessAndTimeoutBeforeClaim()
    {
        int stateChanges = 0;
        var queue = new OwnedByteFrameQueue(() => stateChanges++);
        byte[] value = { 1, 2, 3 };
        Task<OwnedByteDispatchResult> success = Task.Run(() => queue.Submit(() => value));
        SpinUntil(() => queue.OutstandingCount == 1);
        Check(queue.DrainFrame(), "queue drained");
        OwnedByteDispatchResult result = success.GetAwaiter().GetResult();
        Check(result.Status == OwnedByteDispatchStatus.Success &&
              ReferenceEquals(result.Value, value) && value.SequenceEqual(new byte[] { 1, 2, 3 }),
            "success ownership transfers");
        CryptographicOperations.ZeroMemory(value);

        int calls = 0;
        OwnedByteDispatchResult firstTimed = Task.Run(() =>
            queue.Submit(() => { calls++; return new byte[] { 9 }; }))
            .GetAwaiter().GetResult();
        OwnedByteDispatchResult secondTimed = Task.Run(() =>
            queue.Submit(() => { calls++; return new byte[] { 8 }; }))
            .GetAwaiter().GetResult();
        OwnedByteDispatchResult bounded = queue.Submit(
            () => { calls++; return new byte[] { 7 }; });
        Check(firstTimed.Status == OwnedByteDispatchStatus.TimedOutBeforeClaim &&
              secondTimed.Status == OwnedByteDispatchStatus.TimedOutBeforeClaim &&
              bounded.Status == OwnedByteDispatchStatus.Busy &&
              calls == 0 && queue.OutstandingCount == OwnedByteFrameQueue.Capacity,
            "timeouts retain bounded capacity");
        queue.Stop();
        Check(queue.WaitForSettled(1000) && queue.OutstandingCount == 0 && stateChanges >= 2,
            "queue settles");
        queue.Dispose();
    }

    private static void QueueClaimedTimeoutZeroesLateResult()
    {
        var queue = new OwnedByteFrameQueue(() => { });
        byte[] late = { 7, 8, 9 };
        using var release = new ManualResetEventSlim(false);
        Task<OwnedByteDispatchResult> submit = Task.Run(() => queue.Submit(() =>
        {
            release.Wait();
            return late;
        }));
        SpinUntil(() => queue.OutstandingCount == 1);
        Task releaser = Task.Run(() =>
        {
            Thread.Sleep(650);
            release.Set();
        });
        Check(queue.DrainFrame(), "claimed drain");
        OwnedByteDispatchResult result = submit.GetAwaiter().GetResult();
        releaser.GetAwaiter().GetResult();
        Check(result.Status == OwnedByteDispatchStatus.TimedOutAfterClaim &&
              result.Value is null && late.All(value => value == 0), "late zeroed");
        queue.Stop();
        Check(queue.WaitForSettled(1000), "claimed settled");
        queue.Dispose();
    }

    private static void EphemeralGetAndOwnerThread()
    {
        var adapter = new FixtureAdapter("relic_success");
        using RuntimeFixture fixture = StartFixture(adapter);
        bool wrongThread = Task.Run(fixture.Runtime.DrainFrame).GetAwaiter().GetResult();
        Check(!wrongThread && adapter.SurfaceCalls == 0, "wrong thread no native read");
        byte[] response = Exchange(fixture, GetRequest(Token));
        using JsonDocument body = JsonDocument.Parse(ResponseBody(response));
        Check(body.RootElement.GetProperty("status").GetString() == "ready" &&
              fixture.Runtime.ReadSubmissionCount == 1 && adapter.SurfaceCalls == 1,
            "actual get on owner");
        CryptographicOperations.ZeroMemory(response);
    }

    private static void PostReservationAndResolution()
    {
        var adapter = new FixtureAdapter("relic_success");
        using RuntimeFixture fixture = StartFixture(adapter);
        byte[] readyResponse = Exchange(fixture, GetRequest(Token));
        using JsonDocument ready = JsonDocument.Parse(ResponseBody(readyResponse));
        string decision = ready.RootElement.GetProperty("decision_id").GetString()!;
        string action = ready.RootElement.GetProperty("legal_actions")[0].GetString()!;
        CryptographicOperations.ZeroMemory(readyResponse);
        byte[] accepted = Exchange(fixture, PostRequest(Token, decision, action));
        using JsonDocument receipt = JsonDocument.Parse(ResponseBody(accepted));
        Check(receipt.RootElement.GetProperty("status").GetString() == "accepted" &&
              adapter.DispatchCount == 1, "actual accepted");
        CryptographicOperations.ZeroMemory(accepted);
        byte[] second = Exchange(fixture, PostRequest(Token, decision, action));
        Check(second.Length == 0 && adapter.DispatchCount == 1, "second post silent");
        byte[] resolved = Exchange(fixture, GetRequest(Token));
        using JsonDocument result = JsonDocument.Parse(ResponseBody(resolved));
        Check(result.RootElement.GetProperty("status").GetString() == "resolved" &&
              fixture.Runtime.ReadSubmissionCount == 2, "actual resolved");
        CryptographicOperations.ZeroMemory(second);
        CryptographicOperations.ZeroMemory(resolved);
    }

    private static void HalfCloseAndTrailingRejection()
    {
        var adapter = new FixtureAdapter("relic_success");
        using RuntimeFixture fixture = StartFixture(adapter);
        byte[] trailing = GetRequest(Token).Concat(new byte[] { (byte)'X' }).ToArray();
        Check(Exchange(fixture, trailing).Length == 0 && adapter.SurfaceCalls == 0,
            "trailing rejected");

        using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        socket.Connect(IPAddress.Loopback, fixture.Port);
        socket.Send(GetRequest(Token));
        var timer = Stopwatch.StartNew();
        while (timer.Elapsed < TimeSpan.FromMilliseconds(1200))
        {
            fixture.Runtime.DrainFrame();
            Thread.Sleep(2);
        }
        socket.ReceiveTimeout = 500;
        int received;
        try
        {
            received = socket.Receive(new byte[1]);
        }
        catch (SocketException)
        {
            received = 0;
        }
        Check(received == 0 && adapter.SurfaceCalls == 0 &&
              fixture.Runtime.ReadSubmissionCount == 0, "half close required");

        byte[] fragmented = ExchangeFragmented(fixture, GetRequest(Token));
        using JsonDocument fragmentBody = JsonDocument.Parse(ResponseBody(fragmented));
        Check(fragmentBody.RootElement.GetProperty("status").GetString() == "ready" &&
              adapter.SurfaceCalls == 1 && fixture.Runtime.ReadSubmissionCount == 1,
            "fragmented exact request accepted");
        CryptographicOperations.ZeroMemory(fragmented);
    }

    private static void TerminalRetiresPrequeuedReads()
    {
        var adapter = new FixtureAdapter("relic_success");
        using RuntimeFixture fixture = StartFixture(adapter);
        byte[] readyResponse = Exchange(fixture, GetRequest(Token));
        using JsonDocument ready = JsonDocument.Parse(ResponseBody(readyResponse));
        string decision = ready.RootElement.GetProperty("decision_id").GetString()!;
        string action = ready.RootElement.GetProperty("legal_actions")[0].GetString()!;
        CryptographicOperations.ZeroMemory(readyResponse);

        Task<byte[]> queuedOne = Task.Run(() =>
            SocketExchange(fixture.Port, GetRequest(Token)));
        Task<byte[]> queuedTwo = Task.Run(() =>
            SocketExchange(fixture.Port, GetRequest(Token)));
        SpinUntil(() => fixture.Runtime.OutstandingFrameCount == OwnedByteFrameQueue.Capacity);
        byte[] post = SocketExchange(fixture.Port, PostRequest(Token, decision, action));
        byte[] first = queuedOne.GetAwaiter().GetResult();
        byte[] second = queuedTwo.GetAwaiter().GetResult();
        Check(post.Length == 0 && first.Length == 0 && second.Length == 0 &&
              fixture.Runtime.IsTerminal && fixture.Runtime.OutstandingFrameCount == 0 &&
              fixture.Runtime.ReadSubmissionCount == 1 && adapter.SurfaceCalls == 1 &&
              adapter.DispatchCount == 0 && !fixture.Runtime.DrainFrame(),
            "terminal post admission failure retires queued reads");
        CryptographicOperations.ZeroMemory(post);
        CryptographicOperations.ZeroMemory(first);
        CryptographicOperations.ZeroMemory(second);
    }

    private static void StartFailureAndAcceptFault()
    {
        var adapter = new FixtureAdapter("relic_success");
        Check(!ItemTransportRuntime.IsAllowedTestEndpoint(
                  new IPEndPoint(IPAddress.Loopback, ItemTransportLimits.Port)) &&
              ItemTransportRuntime.IsAllowedTestEndpoint(
                  new IPEndPoint(IPAddress.Loopback, 1)) &&
              !ItemTransportRuntime.IsAllowedTestEndpoint(
                  new IPEndPoint(IPAddress.Any, 1)),
            "test endpoint predicate is loopback ephemeral only");
        ItemTransportRuntime invalid = CreateRuntime(adapter) ??
            throw new InvalidOperationException("runtime create failed");
        var unbound = new TcpListener(IPAddress.Loopback, 0);
        Check(!invalid.StartForTests(unbound), "unbound listener rejected");
        SpinUntil(() => invalid.IsStopped);
        Check(invalid.IsStopped && !invalid.StartForTests(unbound),
            "failed start cannot restart");
        invalid.Dispose();

        ItemTransportRuntime racing = CreateRuntime(adapter) ??
            throw new InvalidOperationException("runtime create failed");
        var reserved = new ManualResetEventSlim(false);
        var proceed = new ManualResetEventSlim(false);
        var racingListener = new TcpListener(IPAddress.Loopback, 0);
        racingListener.Start(8);
        Task<bool> starting = Task.Run(() => racing.StartForTests(
            racingListener, () => { reserved.Set(); proceed.Wait(); }));
        Check(reserved.Wait(1000), "start reserved");
        Task<bool> stopping = Task.Run(racing.StopAndJoin);
        SpinUntil(() => racing.IsStopping);
        Check(!racing.IsStopped, "reserved start prevents early stopped publication");
        proceed.Set();
        Check(!starting.GetAwaiter().GetResult() && stopping.GetAwaiter().GetResult() &&
              racing.IsStopped, "concurrent stop waits for start unwind");
        racing.Dispose();
        racingListener.Stop();

        using RuntimeFixture fixture = StartFixture(new FixtureAdapter("relic_success"));
        fixture.Listener.Stop();
        SpinUntil(() => fixture.Runtime.IsStopped);
        Check(fixture.Runtime.IsTerminal && fixture.Runtime.IsStopped &&
              !fixture.Runtime.DrainFrame() && !fixture.Runtime.StartForTests(fixture.Listener),
            "unexpected accept completion fails closed");
    }

    private static void DeferredCleanupAfterFalseJoin()
    {
        var adapter = new BlockingReadAdapter();
        using RuntimeFixture fixture = StartFixture(adapter);
        Task<byte[]> client = Task.Run(() =>
            SocketExchange(fixture.Port, GetRequest(Token)));
        Task<(bool Stopped, long Milliseconds)> firstStop = Task.Run(() =>
        {
            adapter.Entered.Wait();
            var timer = Stopwatch.StartNew();
            bool stopped = fixture.Runtime.StopAndJoin();
            timer.Stop();
            adapter.Release.Set();
            return (stopped, timer.ElapsedMilliseconds);
        });
        while (!adapter.Entered.IsSet)
        {
            fixture.Runtime.DrainFrame();
        }
        (bool stopped, long milliseconds) = firstStop.GetAwaiter().GetResult();
        byte[] response = client.GetAwaiter().GetResult();
        SpinUntil(() => fixture.Runtime.IsStopped);
        Check(!stopped && milliseconds is >= 1800 and < 3000 && response.Length == 0 &&
              adapter.SurfaceCalls == 1 && fixture.Runtime.IsStopped &&
              fixture.Runtime.StopAndJoin(),
            "false join followed by deferred cleanup");
        CryptographicOperations.ZeroMemory(response);
    }

    private static void ShutdownIdempotence()
    {
        var adapter = new FixtureAdapter("relic_success");
        RuntimeFixture fixture = StartFixture(adapter);
        Check(fixture.Runtime.StopAndJoin() && fixture.Runtime.IsStopped,
            "first stop true");
        Check(fixture.Runtime.StopAndJoin() && fixture.Runtime.IsStopped,
            "second stop true");
        fixture.Dispose();
    }

    private static RuntimeFixture StartFixture(IItemV1NativeAdapter adapter)
    {
        ItemTransportRuntime runtime = CreateRuntime(adapter) ??
            throw new InvalidOperationException("runtime create failed");
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start(8);
        if (!runtime.StartForTests(listener) ||
            listener.LocalEndpoint is not IPEndPoint endpoint)
        {
            throw new InvalidOperationException("fixture start failed");
        }
        return new RuntimeFixture(runtime, listener, endpoint.Port);
    }

    private static ItemTransportRuntime? CreateRuntime(IItemV1NativeAdapter adapter) =>
        ItemTransportRuntime.Create(
            EnabledConfiguration.ToArray(),
            () => Encoding.ASCII.GetBytes(Token),
            adapter);

    private static byte[] Exchange(RuntimeFixture fixture, byte[] request)
    {
        Task<byte[]> client = Task.Run(() => SocketExchange(fixture.Port, request));
        var timer = Stopwatch.StartNew();
        while (!client.IsCompleted && timer.Elapsed < TimeSpan.FromSeconds(4))
        {
            fixture.Runtime.DrainFrame();
            Thread.Sleep(1);
        }
        Check(client.IsCompleted, "client exchange completed");
        return client.GetAwaiter().GetResult();
    }

    private static byte[] SocketExchange(int port, byte[] request)
    {
        using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        socket.ReceiveTimeout = 3000;
        socket.SendTimeout = 3000;
        socket.Connect(IPAddress.Loopback, port);
        SendAll(socket, request);
        socket.Shutdown(SocketShutdown.Send);
        using var output = new MemoryStream();
        var buffer = new byte[1024];
        try
        {
            while (true)
            {
                int count = socket.Receive(buffer);
                if (count == 0)
                {
                    break;
                }
                output.Write(buffer, 0, count);
            }
            return output.ToArray();
        }
        finally
        {
            CryptographicOperations.ZeroMemory(buffer);
        }
    }

    private static byte[] ExchangeFragmented(RuntimeFixture fixture, byte[] request)
    {
        Task<byte[]> client = Task.Run(() =>
        {
            using var socket = new Socket(
                AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
            socket.ReceiveTimeout = 3000;
            socket.SendTimeout = 3000;
            socket.Connect(IPAddress.Loopback, fixture.Port);
            foreach (byte value in request)
            {
                socket.Send(new[] { value });
            }
            socket.Shutdown(SocketShutdown.Send);
            using var output = new MemoryStream();
            var buffer = new byte[37];
            try
            {
                while (true)
                {
                    int count = socket.Receive(buffer);
                    if (count == 0)
                    {
                        return output.ToArray();
                    }
                    output.Write(buffer, 0, count);
                }
            }
            finally
            {
                CryptographicOperations.ZeroMemory(buffer);
                CryptographicOperations.ZeroMemory(request);
            }
        });
        var timer = Stopwatch.StartNew();
        while (!client.IsCompleted && timer.Elapsed < TimeSpan.FromSeconds(4))
        {
            fixture.Runtime.DrainFrame();
            Thread.Sleep(1);
        }
        Check(client.IsCompleted, "fragmented exchange completed");
        return client.GetAwaiter().GetResult();
    }

    private static void SendAll(Socket socket, byte[] request)
    {
        int sent = 0;
        while (sent < request.Length)
        {
            int count = socket.Send(request.AsSpan(sent));
            Check(count > 0, "request send progressed");
            sent += count;
        }
    }

    private static ReadOnlyMemory<byte> ResponseBody(byte[] response)
    {
        byte[] marker = Encoding.ASCII.GetBytes("\r\n\r\n");
        int offset = response.AsSpan().IndexOf(marker);
        Check(offset >= 0, "response header terminator");
        string header = Encoding.ASCII.GetString(response, 0, offset + marker.Length);
        Check(header.StartsWith("HTTP/1.1 200 OK\r\n", StringComparison.Ordinal) &&
              header.EndsWith(
                  "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n",
                  StringComparison.Ordinal), "exact response header");
        return response.AsMemory(offset + marker.Length);
    }

    private static byte[] GetRequest(string token) => Encoding.ASCII.GetBytes(
        "GET /probe/item-v1/public/item-decision HTTP/1.1\r\n" +
        "Host: 127.0.0.1:43117\r\n" +
        "Authorization: Bearer " + token + "\r\n" +
        "Accept: application/json\r\n" +
        "Connection: close\r\n\r\n");

    private static byte[] PostRequest(string token, string decision, string action) =>
        Encoding.ASCII.GetBytes(
            "POST /probe/item-v1/public/item-action HTTP/1.1\r\n" +
            "Host: 127.0.0.1:43117\r\n" +
            "Authorization: Bearer " + token + "\r\n" +
            "Accept: application/json\r\n" +
            "X-Sts2-Decision-Id: " + decision + "\r\n" +
            "X-Sts2-Action-Id: " + action + "\r\n" +
            "Connection: close\r\n\r\n");

    private static string Text(byte[] value) => Encoding.ASCII.GetString(value);

    private static void SpinUntil(Func<bool> predicate)
    {
        var timer = Stopwatch.StartNew();
        while (!predicate() && timer.Elapsed < TimeSpan.FromSeconds(2))
        {
            Thread.Sleep(1);
        }
        Check(predicate(), "bounded spin");
    }

    private static void Run(string name, Action action)
    {
        try
        {
            action();
            _checkCount++;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(name + ": " + exception.GetType().Name + ": " +
                exception.Message);
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

    private sealed class RuntimeFixture : IDisposable
    {
        public RuntimeFixture(ItemTransportRuntime runtime, TcpListener listener, int port)
        {
            Runtime = runtime;
            Listener = listener;
            Port = port;
        }

        public ItemTransportRuntime Runtime { get; }
        public TcpListener Listener { get; }
        public int Port { get; }

        public void Dispose()
        {
            Runtime.StopAndJoin();
            Runtime.Dispose();
            Listener.Stop();
        }
    }

    private sealed class FixtureAdapter : IItemV1NativeAdapter
    {
        private readonly string _name;
        private readonly object _run = new();
        private readonly object _player = new();
        private readonly object _screen = new();
        private readonly object _changedScreen = new();
        private readonly object _button = new();
        private readonly object _reward = new();
        private readonly object _model = new();
        private readonly object _held = new();
        private readonly object[] _maximumButtons = NewIdentities();
        private readonly object[] _maximumRewards = NewIdentities();
        private readonly object[] _maximumModels = NewIdentities();
        private readonly object[] _maximumSlotModels = NewIdentities();
        private bool _dispatched;
        private int _pendingReads;

        public FixtureAdapter(string name)
        {
            _name = name;
        }

        public int SurfaceCalls { get; private set; }
        public int DispatchCount { get; private set; }
        public int LastActionIndex { get; private set; } = -1;

        public static bool IsKnown(string value) => value is
            "potion_success" or "relic_success" or "delayed" or "full_belt" or
            "stale" or "uncertain" or "overlay_closed" or "bounds_ready";

        public ItemV1SurfaceCapture CaptureSurface()
        {
            SurfaceCalls++;
            if (_name == "delayed" && SurfaceCalls <= 2)
            {
                return ItemV1SurfaceCapture.Missing();
            }
            if (_name == "overlay_closed" && _dispatched)
            {
                return ItemV1SurfaceCapture.Missing();
            }
            if (_name == "bounds_ready")
            {
                return MaximumSurface();
            }
            (int index, ItemV1ItemKind kind, string key) = Definition();
            bool full = _name == "full_belt";
            var slots = full
                ? new[] { new ItemV1PotionSlotBinding(_held, "Potion_Held") }
                : new[]
                {
                    new ItemV1PotionSlotBinding(_held, "Potion_Held"),
                    new ItemV1PotionSlotBinding(null, null),
                };
            var offer = new ItemV1NativeOffer(
                index, kind, key, true, false, true, true,
                _button, _reward, _model, () => Dispatch(index));
            object screen = _name == "stale" && SurfaceCalls > 1
                ? _changedScreen : _screen;
            return ItemV1SurfaceCapture.Available(
                _run, _player, screen, slots.Length, new[] { offer }, slots);
        }

        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending)
        {
            _pendingReads++;
            if (_name == "bounds_ready")
            {
                int offerPosition = Array.IndexOf(
                    _maximumModels, pending.OfferedModelIdentity);
                if (offerPosition < 0)
                {
                    throw new InvalidOperationException("Unknown maximum offer.");
                }
                string key = new((char)('A' + offerPosition), 128);
                var slots = new ItemV1PotionSlotBinding[8];
                for (int index = 0; index < slots.Length; index++)
                {
                    slots[index] = new ItemV1PotionSlotBinding(
                        _maximumSlotModels[index], new string((char)('a' + index), 128));
                }
                return Pending(pending, key, true, slots);
            }
            (int _, ItemV1ItemKind kind, string stableKey) = Definition();
            bool resolved = _name != "delayed" || _pendingReads >= 3;
            ItemV1PotionSlotBinding[] currentSlots = kind == ItemV1ItemKind.Potion
                ? new[]
                {
                    new ItemV1PotionSlotBinding(_held, "Potion_Held"),
                    new ItemV1PotionSlotBinding(
                        resolved ? pending.OfferedModelIdentity : null,
                        resolved ? stableKey : null),
                }
                : new[]
                {
                    new ItemV1PotionSlotBinding(_held, "Potion_Held"),
                    new ItemV1PotionSlotBinding(null, null),
                };
            return Pending(pending, stableKey, resolved, currentSlots);
        }

        private ItemV1PendingCapture Pending(
            ItemV1PendingProbe pending,
            string key,
            bool resolved,
            IReadOnlyList<ItemV1PotionSlotBinding> slots) =>
            new(
                pending.RunIdentity,
                pending.PlayerIdentity,
                pending.RewardIdentity,
                pending.OfferedModelIdentity,
                key,
                resolved,
                resolved ? pending.OfferedModelIdentity : null,
                resolved ? key : null,
                slots.Count,
                slots);

        private ItemV1SurfaceCapture MaximumSurface()
        {
            var offers = new ItemV1NativeOffer[8];
            for (int position = 0; position < offers.Length; position++)
            {
                int index = 248 + position;
                offers[position] = new ItemV1NativeOffer(
                    index, ItemV1ItemKind.Relic,
                    new string((char)('A' + position), 128),
                    true, false, true, true,
                    _maximumButtons[position],
                    _maximumRewards[position],
                    _maximumModels[position],
                    () => Dispatch(index));
            }
            var slots = Enumerable.Range(0, 8)
                .Select(index => new ItemV1PotionSlotBinding(
                    _maximumSlotModels[index], new string((char)('a' + index), 128)))
                .ToArray();
            return ItemV1SurfaceCapture.Available(
                _run, _player, _screen, slots.Length, offers, slots);
        }

        private void Dispatch(int index)
        {
            DispatchCount++;
            LastActionIndex = index;
            _dispatched = true;
            if (_name == "uncertain")
            {
                throw new InvalidOperationException("SYNTHETIC_DISPATCH_CANARY");
            }
        }

        private (int Index, ItemV1ItemKind Kind, string Key) Definition() => _name switch
        {
            "potion_success" => (3, ItemV1ItemKind.Potion, "Potion_Synthetic"),
            "relic_success" => (7, ItemV1ItemKind.Relic, "Relic_Synthetic"),
            "delayed" => (5, ItemV1ItemKind.Potion, "Potion_Delayed"),
            "full_belt" => (4, ItemV1ItemKind.Potion, "Potion_Full"),
            "stale" => (6, ItemV1ItemKind.Relic, "Relic_Stale"),
            "uncertain" => (8, ItemV1ItemKind.Relic, "Relic_Uncertain"),
            "overlay_closed" => (9, ItemV1ItemKind.Relic, "Relic_Closed"),
            _ => throw new InvalidOperationException("Unknown fixture scenario."),
        };

        private static object[] NewIdentities() =>
            Enumerable.Range(0, 8).Select(_ => new object()).ToArray();
    }

    private sealed class BlockingReadAdapter : IItemV1NativeAdapter
    {
        public ManualResetEventSlim Entered { get; } = new(false);
        public ManualResetEventSlim Release { get; } = new(false);
        public int SurfaceCalls { get; private set; }

        public ItemV1SurfaceCapture CaptureSurface()
        {
            SurfaceCalls++;
            Entered.Set();
            Release.Wait();
            return ItemV1SurfaceCapture.Missing();
        }

        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) =>
            throw new InvalidOperationException("No pending capture expected.");
    }
}
