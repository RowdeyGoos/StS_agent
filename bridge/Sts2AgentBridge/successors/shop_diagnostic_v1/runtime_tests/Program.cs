using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

internal static class Program
{
    private const string TokenText =
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    private static readonly byte[] Token = Encoding.ASCII.GetBytes(TokenText);
    private static readonly byte[] Body = Encoding.ASCII.GetBytes(
        "{\"schema_version\":1,\"status\":\"passed\",\"shop_status\":\"unsupported\",\"stage\":\"native_offers\",\"reason\":\"cost_text_invalid\"}");
    private static int _checks;

    public static int Main(string[] args)
    {
        try
        {
            if (args.Length == 2 && args[0] == "--fixture" &&
                args[1] is "ready" or "unsupported" or "lost_delivery")
                return RunFixture(args[1]);
            if (args.Length != 0) return 2;
            ThreadPool.SetMinThreads(8, 8);
            ConfigurationAndOwnership();
            ProtocolIsGetOnly();
            ReservationIsOneShot();
            SuccessfulExchangeStopsAfterCleanup();
            MalformedAndUnauthenticatedDoNotObserve();
            CompetingAuthenticatedRequestStopsWithoutSecondObserve();
            FaultAndOversizeAreTerminal();
            StartAndCleanupBoundaries();
            PublicSurface();
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                schema_version = 1,
                status = "passed",
                suite = "shop_diagnostic_v1_transport",
                check_count = _checks,
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
        finally
        {
            Array.Clear(Token);
            Array.Clear(Body);
        }
    }

    private static void ConfigurationAndOwnership()
    {
        byte[] invalid = Encoding.ASCII.GetBytes("disabled");
        int credentials = 0;
        int factories = 0;
        ShopDiagnosticTransportRuntime? missing = ShopDiagnosticTransportRuntime.Create(
            invalid,
            () => { credentials++; return (byte[])Token.Clone(); },
            () => { factories++; return new FakeService(); });
        Check(missing is null);
        Check(credentials == 0);
        Check(factories == 0);
        Check(AllZero(invalid));

        byte[] config = Configuration();
        byte[] credential = (byte[])Token.Clone();
        var service = new FakeService();
        int owner = Environment.CurrentManagedThreadId;
        ShopDiagnosticTransportRuntime runtime = Require(
            ShopDiagnosticTransportRuntime.Create(
                config,
                () => credential,
                () =>
                {
                    factories++;
                    Check(Environment.CurrentManagedThreadId == owner);
                    return service;
                }));
        Check(factories == 1);
        Check(AllZero(config));
        Check(AllZero(credential));
        Check(runtime.StopTransportAndJoin());
        Check(runtime.TransportStopped);
        Check(!runtime.ServiceDisposed);
        Check(runtime.DisposeServiceOnOwnerFrame());
        Check(service.DisposeCalls == 1);
        Check(runtime.IsFullyStopped);

        byte[] throwingConfig = Configuration();
        byte[] throwingCredential = (byte[])Token.Clone();
        Check(ShopDiagnosticTransportRuntime.Create(
            throwingConfig,
            () => throwingCredential,
            () => throw new InvalidOperationException()) is null);
        Check(AllZero(throwingConfig));
        Check(AllZero(throwingCredential));
    }

    private static void ProtocolIsGetOnly()
    {
        byte[] valid = Request(TokenText);
        Check(ShopDiagnosticTransportRequestParser.TryParse(valid, out var parsed));
        Check(parsed.AuthorizationLength == 64);
        Check(Encoding.ASCII.GetString(valid, parsed.AuthorizationOffset, 64) == TokenText);
        foreach (byte[] invalid in new[]
        {
            Replace(valid, "GET ", "POST"),
            Replace(valid, "/probe/shop-diagnostic-v1/public/diagnostic", "/probe/room-flows-v1/public/decision"),
            Replace(valid, "Accept: application/json", "X-Sts2-Action-Id: leave"),
            Replace(valid, TokenText, TokenText.ToUpperInvariant()),
            valid.Concat(new byte[] { (byte)'x' }).ToArray(),
        })
        {
            Check(!ShopDiagnosticTransportRequestParser.TryParse(invalid, out _));
            Array.Clear(invalid);
        }
        byte[] wrapped = ShopDiagnosticTransportHttpEncoder.Wrap((byte[])Body.Clone());
        Check(Encoding.ASCII.GetString(wrapped).Contains("Content-Length: " + Body.Length, StringComparison.Ordinal));
        Check(wrapped.AsSpan(wrapped.Length - Body.Length).SequenceEqual(Body));
        Array.Clear(wrapped);
        CheckThrows(() => ShopDiagnosticTransportHttpEncoder.Wrap(new byte[513]));
    }

    private static void ReservationIsOneShot()
    {
        using ShopDiagnosticTransportRuntime runtime = NewRuntime(new FakeService());
        Check(runtime.ReserveObservationForTests());
        Check(!runtime.ReserveObservationForTests());
        Check(runtime.ObservationReserved);
    }

    private static void SuccessfulExchangeStopsAfterCleanup()
    {
        var service = new FakeService((byte[])Body.Clone());
        using ShopDiagnosticTransportRuntime runtime = NewRuntime(service);
        IPEndPoint endpoint = Start(runtime);
        Task<byte[]> exchange = Task.Run(() => Exchange(endpoint, Request(TokenText)));
        DrainUntil(runtime, exchange);
        byte[] response = exchange.GetAwaiter().GetResult();
        Check(response.AsSpan(response.Length - Body.Length).SequenceEqual(Body));
        Check(service.ObserveCalls == 1);
        Check(runtime.ObservationSubmissionCount == 1);
        Check(service.LastBody is not null && AllZero(service.LastBody));
        Check(SpinWait.SpinUntil(() => runtime.IsTerminalOrStopping, 2000));
        Check(runtime.StopTransportAndJoin());
        Check(runtime.TransportStopped);
        Check(service.DisposeCalls == 0);
        Check(runtime.DisposeServiceOnOwnerFrame());
        Check(service.DisposeCalls == 1);
        Check(runtime.IsFullyStopped);
        Array.Clear(response);
    }

    private static void MalformedAndUnauthenticatedDoNotObserve()
    {
        var service = new FakeService((byte[])Body.Clone());
        using ShopDiagnosticTransportRuntime runtime = NewRuntime(service);
        IPEndPoint endpoint = Start(runtime);
        byte[] malformed = Encoding.ASCII.GetBytes("POST / HTTP/1.1\r\n\r\n");
        Check(Exchange(endpoint, malformed).Length == 0);
        Check(service.ObserveCalls == 0);
        byte[] wrong = Request(new string('d', 64));
        Check(Exchange(endpoint, wrong).Length == 0);
        Check(service.ObserveCalls == 0);
        Check(!runtime.IsTerminalOrStopping);
        Task<byte[]> valid = Task.Run(() => Exchange(endpoint, Request(TokenText)));
        DrainUntil(runtime, valid);
        Check(valid.GetAwaiter().GetResult().Length > Body.Length);
        Check(service.ObserveCalls == 1);
        Check(SpinWait.SpinUntil(() => runtime.TransportStopped, 2000));
        Check(runtime.DisposeServiceOnOwnerFrame());
    }

    private static void CompetingAuthenticatedRequestStopsWithoutSecondObserve()
    {
        var service = new FakeService((byte[])Body.Clone());
        using ShopDiagnosticTransportRuntime runtime = NewRuntime(service);
        using var reserved = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        int callbacks = 0;
        runtime.AfterAuthenticatedReservationForTests = () =>
        {
            if (Interlocked.Increment(ref callbacks) == 1)
            {
                reserved.Set();
                release.Wait(2000);
            }
        };
        IPEndPoint endpoint = Start(runtime);
        Task<byte[]> first = Task.Run(() => Exchange(endpoint, Request(TokenText)));
        Check(reserved.Wait(2000));
        Task<byte[]> second = Task.Run(() => Exchange(endpoint, Request(TokenText)));
        Check(second.Wait(2000));
        release.Set();
        Check(first.Wait(2000));
        Check(service.ObserveCalls == 0);
        Check(runtime.ObservationReserved);
        Check(SpinWait.SpinUntil(() => runtime.TransportStopped, 2000));
        Check(runtime.DisposeServiceOnOwnerFrame());
        Array.Clear(first.Result);
        Array.Clear(second.Result);
    }

    private static void FaultAndOversizeAreTerminal()
    {
        foreach (FakeService service in new[]
        {
            new FakeService(null, throwObserve: true),
            new FakeService(new byte[513]),
            new FakeService(Array.Empty<byte>()),
        })
        {
            using ShopDiagnosticTransportRuntime runtime = NewRuntime(service);
            IPEndPoint endpoint = Start(runtime);
            Task<byte[]> exchange = Task.Run(() => Exchange(endpoint, Request(TokenText)));
            DrainUntil(runtime, exchange);
            Check(exchange.GetAwaiter().GetResult().Length == 0);
            Check(service.ObserveCalls == 1);
            Check(SpinWait.SpinUntil(() => runtime.TransportStopped, 2000));
            Check(runtime.DisposeServiceOnOwnerFrame());
        }
    }

    private static void StartAndCleanupBoundaries()
    {
        Check(!ShopDiagnosticTransportRuntime.IsAllowedTestEndpoint(
            new IPEndPoint(IPAddress.Loopback, ShopDiagnosticTransportLimits.Port)));
        Check(!ShopDiagnosticTransportRuntime.IsAllowedTestEndpoint(
            new IPEndPoint(IPAddress.Any, 12345)));
        Check(ShopDiagnosticTransportRuntime.IsAllowedTestEndpoint(
            new IPEndPoint(IPAddress.Loopback, 12345)));

        var service = new FakeService();
        using ShopDiagnosticTransportRuntime runtime = NewRuntime(service);
        var unbound = new TcpListener(IPAddress.Loopback, 0);
        Check(!runtime.StartForTests(unbound));
        Check(runtime.TransportStopped);
        Task<bool> wrongThread = Task.Run(runtime.DisposeServiceOnOwnerFrame);
        Check(!wrongThread.GetAwaiter().GetResult());
        Check(runtime.DisposeServiceOnOwnerFrame());
        Check(service.DisposeCalls == 1);

        var failing = new FakeService { ThrowDispose = true };
        using ShopDiagnosticTransportRuntime failed = NewRuntime(failing);
        Check(failed.StopTransportAndJoin());
        Check(!failed.DisposeServiceOnOwnerFrame());
        Check(!failed.ServiceDisposed);
        Check(!failed.IsFullyStopped);
    }

    private static void PublicSurface()
    {
        string[] methods = typeof(ShopDiagnosticTransportRuntime)
            .GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly)
            .Select(method => method.Name)
            .OrderBy(name => name, StringComparer.Ordinal)
            .ToArray();
        Check(methods.SequenceEqual(new[]
        {
            "Create", "Dispose", "DisposeServiceOnOwnerFrame", "DrainFrame", "Start",
            "StopTransportAndJoin", "get_IsFullyStopped", "get_IsTerminalOrStopping",
            "get_ServiceDisposed", "get_TransportStopped",
        }));
    }

    private static int RunFixture(string scenario)
    {
        byte[] record = Encoding.ASCII.GetBytes(scenario == "unsupported"
            ? "{\"schema_version\":1,\"status\":\"passed\",\"shop_status\":\"unsupported\",\"stage\":\"native_offers\",\"reason\":\"cost_text_invalid\"}"
            : "{\"schema_version\":1,\"status\":\"passed\",\"shop_status\":\"ready\",\"stage\":\"complete\",\"reason\":\"none\"}");
        var service = new FakeService(record);
        byte[] config = Configuration();
        byte[] credential = (byte[])Token.Clone();
        using ShopDiagnosticTransportRuntime runtime = Require(
            ShopDiagnosticTransportRuntime.Create(config, () => credential, () => service));
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start(ShopDiagnosticTransportLimits.Backlog);
        if (!runtime.StartForTests(listener)) return 1;
        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        Console.WriteLine(JsonSerializer.Serialize(new { port }));
        Console.Out.Flush();
        Task<string> eof = Task.Run(Console.In.ReadToEnd);
        var limit = Stopwatch.StartNew();
        while (!eof.IsCompleted && !runtime.IsTerminalOrStopping &&
            limit.Elapsed < TimeSpan.FromSeconds(20))
        {
            runtime.DrainFrame();
            Thread.Sleep(1);
        }
        bool transport = runtime.StopTransportAndJoin();
        bool disposed = runtime.DisposeServiceOnOwnerFrame();
        Console.Error.WriteLine(JsonSerializer.Serialize(new
        {
            observe_count = service.ObserveCalls,
            terminal = runtime.IsTerminalOrStopping,
            transport_stopped = transport,
            service_disposed = disposed,
        }));
        return transport && disposed && service.ObserveCalls == 1 ? 0 : 1;
    }

    private static ShopDiagnosticTransportRuntime NewRuntime(FakeService service)
    {
        byte[] config = Configuration();
        byte[] credential = (byte[])Token.Clone();
        ShopDiagnosticTransportRuntime runtime = Require(
            ShopDiagnosticTransportRuntime.Create(config, () => credential, () => service));
        Check(AllZero(config));
        Check(AllZero(credential));
        return runtime;
    }

    private static IPEndPoint Start(ShopDiagnosticTransportRuntime runtime)
    {
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        var endpoint = (IPEndPoint)listener.LocalEndpoint;
        Check(runtime.StartForTests(listener));
        return endpoint;
    }

    private static void DrainUntil(ShopDiagnosticTransportRuntime runtime, Task exchange)
    {
        DateTime deadline = DateTime.UtcNow.AddSeconds(3);
        while (!exchange.IsCompleted && DateTime.UtcNow < deadline)
        {
            runtime.DrainFrame();
            Thread.Sleep(1);
        }
        Check(exchange.IsCompleted);
    }

    private static byte[] Exchange(IPEndPoint endpoint, byte[] request)
    {
        using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        socket.SendTimeout = 2000;
        socket.ReceiveTimeout = 2000;
        var received = new List<byte>();
        try
        {
            socket.Connect(endpoint);
            int sent = 0;
            while (sent < request.Length)
            {
                int count = socket.Send(request, sent, request.Length - sent, SocketFlags.None);
                if (count <= 0) throw new InvalidOperationException();
                sent += count;
            }
            socket.Shutdown(SocketShutdown.Send);
            var chunk = new byte[256];
            try
            {
                while (true)
                {
                    int count = socket.Receive(chunk);
                    if (count == 0) break;
                    received.AddRange(chunk.AsSpan(0, count).ToArray());
                }
            }
            catch (SocketException error) when (
                error.SocketErrorCode is SocketError.ConnectionReset or SocketError.OperationAborted)
            {
            }
            finally
            {
                Array.Clear(chunk);
            }
            return received.ToArray();
        }
        finally
        {
            Array.Clear(request);
        }
    }

    private static byte[] Request(string token) => Encoding.ASCII.GetBytes(
        "GET /probe/shop-diagnostic-v1/public/diagnostic HTTP/1.1\r\n" +
        "Host: 127.0.0.1:43117\r\n" +
        "Authorization: Bearer " + token + "\r\n" +
        "Accept: application/json\r\n" +
        "Connection: close\r\n\r\n");

    private static byte[] Configuration() => Encoding.ASCII.GetBytes(
        "{\"schema_version\":\"shop_diagnostic_v1_transport_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");

    private static byte[] Replace(byte[] value, string oldValue, string newValue) =>
        Encoding.ASCII.GetBytes(
            Encoding.ASCII.GetString(value).Replace(oldValue, newValue, StringComparison.Ordinal));

    private static bool AllZero(byte[] value) => value.All(item => item == 0);
    private static T Require<T>(T? value) where T : class =>
        value ?? throw new InvalidOperationException();
    private static void Check(bool value)
    {
        if (!value) throw new InvalidOperationException();
        _checks++;
    }
    private static void CheckThrows(Action action)
    {
        try { action(); }
        catch (InvalidOperationException) { Check(true); return; }
        throw new InvalidOperationException();
    }

    private sealed class FakeService : IShopDiagnosticService
    {
        private readonly byte[]? _body;
        private readonly bool _throwObserve;
        internal int ObserveCalls;
        internal int DisposeCalls;
        internal bool ThrowDispose;
        internal byte[]? LastBody;

        internal FakeService(byte[]? body = null, bool throwObserve = false)
        {
            _body = body ?? (byte[])Body.Clone();
            _throwObserve = throwObserve;
        }

        public byte[] Observe()
        {
            ObserveCalls++;
            if (_throwObserve) throw new InvalidOperationException();
            LastBody = _body!;
            return _body!;
        }

        public void Dispose()
        {
            DisposeCalls++;
            if (ThrowDispose) throw new InvalidOperationException();
        }
    }
}
