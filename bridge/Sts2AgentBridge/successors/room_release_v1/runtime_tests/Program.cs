using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.ItemWireV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

namespace Sts2AgentBridge.Successors.RoomReleaseV1;

internal static class Program
{
    private const string FixedNonce = "0123456789abcdef0123456789abcdef";
    private const string TokenText = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    private static readonly byte[] Token = Encoding.ASCII.GetBytes(TokenText);
    private static int _checks;

    public static int Main(string[] args)
    {
        try
        {
            ThreadPool.SetMinThreads(8, 8);
            if (args.Length == 2 && args[0] == "--fixture" &&
                args[1] is "shop_success" or "event_continuation" or "event_item" or "lost_receipt")
                return RunFixture(args[1]);
            if (args.Length != 0) return 2;
            TestConfigurationAndOwnership();
            TestProtocol();
            TestTerminalClassification();
            TestQueueLateZero();
            TestStartAndParentGet();
            TestAuthenticationAndMalformed();
            TestCompetingAuthenticatedExchange();
            TestCompetingPostAndNoReplay();
            TestBudgetsAndDuplicateReservation();
            TestLostPostReceipt();
            TestOwnerCleanupAndStartFailure();
            TestPublicSurface();
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                schema_version = 1,
                status = "passed",
                suite = "room_flow_transport",
                check_count = _checks,
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static void TestConfigurationAndOwnership()
    {
        byte[] invalid = Encoding.ASCII.GetBytes("disabled");
        int credentials = 0, factories = 0;
        RoomFlowTransportRuntime? missing = RoomFlowTransportRuntime.Create(
            invalid,
            () => { credentials++; return (byte[])Token.Clone(); },
            (_, _) => { factories++; throw new InvalidOperationException(); });
        Check(missing is null && credentials == 0 && factories == 0 && AllZero(invalid));

        ShopFixture shop = new("shop_success");
        byte[] config = Configuration(RoomFlowSelection.Shop);
        byte[] credential = (byte[])Token.Clone();
        int owner = Environment.CurrentManagedThreadId;
        RoomFlowSelection observed = default;
        string? nonce = null;
        RoomFlowTransportRuntime runtime = Require(RoomFlowTransportRuntime.Create(
            config,
            () => credential,
            (selection, value) =>
            {
                factories++;
                observed = selection;
                nonce = value;
                Check(Environment.CurrentManagedThreadId == owner);
                return new RoomFlowWireService(value, new ShopV1Session(value, shop.Adapter));
            }));
        Check(factories == 1 && observed == RoomFlowSelection.Shop &&
            nonce is { Length: 32 } && LowerHex(nonce) && AllZero(config) && AllZero(credential));
        Check(runtime.StopTransportAndJoin() && runtime.TransportStopped && !runtime.ServiceDisposed);
        Check(runtime.DisposeServiceOnOwnerFrame() && runtime.IsFullyStopped);
    }

    private static void TestProtocol()
    {
        foreach (RoomFlowSelection selection in new[] { RoomFlowSelection.Shop, RoomFlowSelection.Event })
        {
            byte[] get = Request("GET", ParentGet, null, null);
            Check(RoomFlowTransportRequestParser.TryParse(get, selection, out var parsed) &&
                parsed.Route == RoomFlowTransportRoute.ParentGet && !parsed.IsPost && !parsed.IsItem);
            byte[] post = Request("POST", ParentPost, new string('a', 64),
                selection == RoomFlowSelection.Shop ? "buy:card:31" : "choose:7");
            Check(RoomFlowTransportRequestParser.TryParse(post, selection, out parsed) && parsed.IsPost);
        }
        Check(RoomFlowTransportRequestParser.TryParse(
            Request("GET", ItemGet, null, null), RoomFlowSelection.Event, out var item) && item.IsItem);
        Check(!RoomFlowTransportRequestParser.TryParse(
            Request("GET", ItemGet, null, null), RoomFlowSelection.Shop, out _));
        foreach (string invalid in new[] { "buy:card:00", "buy:card:32", "choose:08", "collect:256" })
        {
            RoomFlowSelection selection = invalid.StartsWith("buy", StringComparison.Ordinal)
                ? RoomFlowSelection.Shop : RoomFlowSelection.Event;
            string route = invalid.StartsWith("collect", StringComparison.Ordinal) ? ItemPost : ParentPost;
            Check(!RoomFlowTransportRequestParser.TryParse(
                Request("POST", route, new string('a', 64), invalid), selection, out _));
        }
        byte[] origin = Request("GET", ParentGet, null, null)
            .ReplaceAscii("Connection: close", "Origin: null\r\nConnection: close");
        Check(!RoomFlowTransportRequestParser.TryParse(origin, RoomFlowSelection.Shop, out _));
    }

    private static void TestTerminalClassification()
    {
        ShopFixture shop = new("shop_success");
        using var service = new RoomFlowWireService(FixedNonce, new ShopV1Session(FixedNonce, shop.Adapter));
        byte[] ready = service.Handle("GET", RoomFlowWireProtocol.DecisionRoute, null, null);
        try
        {
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
                RoomFlowSelection.Shop, FixedNonce, ready) == TerminalClassification.NonTerminal);
        }
        finally { Array.Clear(ready); }
        byte[] accepted = Encoding.ASCII.GetBytes(
            "{\"schema_version\":1,\"protocol\":\"room_flows_v1\",\"version\":\"shop_v1\",\"flow_kind\":\"shop\",\"session_nonce\":\"" + FixedNonce +
            "\",\"parent_ordinal\":1,\"status\":\"accepted\",\"decision_id\":\"" + new string('a', 64) + "\",\"action_id\":\"inventory:close\"}");
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentPost,
            RoomFlowSelection.Shop, FixedNonce, accepted) == TerminalClassification.NonTerminal);
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
            RoomFlowSelection.Shop, FixedNonce, accepted) == TerminalClassification.Invalid);
        byte[] childResolved = Encoding.ASCII.GetBytes(
            "{\"schema_version\":1,\"protocol\":\"item_probe_v1\",\"version\":\"item_v1\",\"session_nonce\":\"" + FixedNonce +
            "\",\"surface_ordinal\":1,\"status\":\"resolved\",\"decision_id\":\"" + new string('b',64) +
            "\",\"action_id\":\"collect:0\",\"offer_index\":0,\"kind\":\"relic\",\"key\":\"R\",\"result\":\"collected\"}");
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ItemGet,
            RoomFlowSelection.Event, FixedNonce, childResolved) == TerminalClassification.NonTerminal);
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ItemPost,
            RoomFlowSelection.Event, FixedNonce, childResolved) == TerminalClassification.Invalid);
        byte[] terminal = Encoding.ASCII.GetBytes(
            "{\"schema_version\":1,\"protocol\":\"room_flows_v1\",\"version\":\"event_v1\",\"flow_kind\":\"event\",\"session_nonce\":\"" + FixedNonce +
            "\",\"parent_ordinal\":1,\"status\":\"error\",\"code\":\"internal_failure\"}");
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
            RoomFlowSelection.Event, FixedNonce, terminal) == TerminalClassification.Terminal);
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentPost,
            RoomFlowSelection.Event, FixedNonce, EventEnvelope("ready")) == TerminalClassification.Invalid);
        byte[] textCanary = Encoding.ASCII.GetBytes(
            "{\"schema_version\":1,\"protocol\":\"room_flows_v1\",\"version\":\"event_v1\",\"flow_kind\":\"event\",\"session_nonce\":\"" + FixedNonce +
            "\",\"parent_ordinal\":1,\"status\":\"ready\",\"phase\":\"choose_option\",\"decision_id\":\"" + new string('c',64) +
            "\",\"candidates\":[{\"rendered_text\":\"status error complete resolved\"}],\"legal_actions\":[]}");
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
            RoomFlowSelection.Event, FixedNonce, textCanary) == TerminalClassification.NonTerminal);
        textCanary[^1] = (byte)' ';
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
            RoomFlowSelection.Event, FixedNonce, textCanary) == TerminalClassification.Invalid);

        CheckParentStatusMatrix(RoomFlowSelection.Shop,
            (ShopEnvelope("waiting"), TerminalClassification.NonTerminal, TerminalClassification.Invalid),
            (ShopEnvelope("ready"), TerminalClassification.NonTerminal, TerminalClassification.Invalid),
            (ShopEnvelope("complete"), TerminalClassification.Terminal, TerminalClassification.Invalid),
            (ShopEnvelope("accepted"), TerminalClassification.Invalid, TerminalClassification.NonTerminal),
            (ShopEnvelope("rejected"), TerminalClassification.Invalid, TerminalClassification.Terminal),
            (ShopEnvelope("uncertain"), TerminalClassification.Invalid, TerminalClassification.Terminal),
            (ShopEnvelope("waiting").ReplaceAscii("\"status\":\"waiting\"", "\"status\":\"unsupported\""),
                TerminalClassification.Terminal, TerminalClassification.Invalid),
            (ShopEnvelope("unsupported"), TerminalClassification.Invalid, TerminalClassification.Terminal),
            (ShopEnvelope("error"), TerminalClassification.Terminal, TerminalClassification.Terminal));

        CheckParentStatusMatrix(RoomFlowSelection.Event,
            (EventEnvelope("waiting"), TerminalClassification.NonTerminal, TerminalClassification.Invalid),
            (EventEnvelope("ready"), TerminalClassification.NonTerminal, TerminalClassification.Invalid),
            (EventEnvelope("item_child"), TerminalClassification.NonTerminal, TerminalClassification.Invalid),
            (EventEnvelope("resolved"), TerminalClassification.Terminal, TerminalClassification.Invalid),
            (EventEnvelope("accepted"), TerminalClassification.Invalid, TerminalClassification.NonTerminal),
            (EventEnvelope("rejected"), TerminalClassification.Invalid, TerminalClassification.Terminal),
            (EventEnvelope("uncertain"), TerminalClassification.Invalid, TerminalClassification.Terminal),
            (EventEnvelope("waiting").ReplaceAscii("\"status\":\"waiting\"", "\"status\":\"unsupported\""),
                TerminalClassification.Terminal, TerminalClassification.Invalid),
            (EventEnvelope("unsupported"), TerminalClassification.Invalid, TerminalClassification.Terminal),
            (EventEnvelope("error"), TerminalClassification.Terminal, TerminalClassification.Terminal));

        CheckItemStatusMatrix(
            (ItemEnvelope("waiting"), TerminalClassification.NonTerminal, TerminalClassification.Invalid),
            (ItemEnvelope("ready"), TerminalClassification.NonTerminal, TerminalClassification.Invalid),
            (ItemEnvelope("resolved"), TerminalClassification.NonTerminal, TerminalClassification.Invalid),
            (ItemEnvelope("accepted"), TerminalClassification.Invalid, TerminalClassification.NonTerminal),
            (ItemEnvelope("rejected"), TerminalClassification.Invalid, TerminalClassification.Terminal),
            (ItemEnvelope("uncertain"), TerminalClassification.Invalid, TerminalClassification.Terminal),
            (ItemEnvelope("unsupported"), TerminalClassification.Terminal, TerminalClassification.Terminal),
            (ItemEnvelope("error"), TerminalClassification.Terminal, TerminalClassification.Terminal));
        byte[] reordered = EventEnvelope("ready").ReplaceAscii(
            "\"protocol\":\"room_flows_v1\",\"version\":\"event_v1\"",
            "\"version\":\"event_v1\",\"protocol\":\"room_flows_v1\"");
        byte[] duplicate = EventEnvelope("ready").ReplaceAscii(
            "\"status\":\"ready\"", "\"status\":\"ready\",\"status\":\"ready\"");
        byte[] unknown = EventEnvelope("ready").ReplaceAscii(
            "\"status\":\"ready\"", "\"status\":\"complete\"");
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
            RoomFlowSelection.Event, FixedNonce, reordered) == TerminalClassification.Invalid);
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
            RoomFlowSelection.Event, FixedNonce, duplicate) == TerminalClassification.Invalid);
        Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
            RoomFlowSelection.Event, FixedNonce, unknown) == TerminalClassification.Invalid);

        byte[] parentMaximum = new byte[RoomFlowTransportLimits.MaximumParentBody];
        byte[] itemMaximum = new byte[RoomFlowTransportLimits.MaximumItemBody];
        Array.Fill(parentMaximum, (byte)'x');
        Array.Fill(itemMaximum, (byte)'x');
        byte[] parentResponse = RoomFlowTransportHttpEncoder.Wrap(RoomFlowTransportRoute.ParentGet, parentMaximum);
        byte[] itemResponse = RoomFlowTransportHttpEncoder.Wrap(RoomFlowTransportRoute.ItemGet, itemMaximum);
        Check(parentResponse.Length > parentMaximum.Length && itemResponse.Length > itemMaximum.Length);
        CheckThrows(() => RoomFlowTransportHttpEncoder.Wrap(RoomFlowTransportRoute.ItemGet, parentMaximum));
        CheckThrows(() => RoomFlowTransportHttpEncoder.Wrap(RoomFlowTransportRoute.ParentGet,
            new byte[RoomFlowTransportLimits.MaximumParentBody + 1]));
        Array.Clear(parentMaximum); Array.Clear(itemMaximum); Array.Clear(parentResponse); Array.Clear(itemResponse);
    }

    private static void CheckParentStatusMatrix(
        RoomFlowSelection selection,
        params (byte[] Body, TerminalClassification Get, TerminalClassification Post)[] cases)
    {
        RoomFlowSelection other = selection == RoomFlowSelection.Shop
            ? RoomFlowSelection.Event : RoomFlowSelection.Shop;
        foreach ((byte[] body, TerminalClassification get, TerminalClassification post) in cases)
        {
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
                selection, FixedNonce, body) == get);
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentPost,
                selection, FixedNonce, body) == post);
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
                other, FixedNonce, body) == TerminalClassification.Invalid);
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentPost,
                other, FixedNonce, body) == TerminalClassification.Invalid);
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ItemGet,
                selection, FixedNonce, body) == TerminalClassification.Invalid);
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ItemPost,
                selection, FixedNonce, body) == TerminalClassification.Invalid);
            Array.Clear(body);
        }
    }

    private static void CheckItemStatusMatrix(
        params (byte[] Body, TerminalClassification Get, TerminalClassification Post)[] cases)
    {
        foreach ((byte[] body, TerminalClassification get, TerminalClassification post) in cases)
        {
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ItemGet,
                RoomFlowSelection.Event, FixedNonce, body) == get);
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ItemPost,
                RoomFlowSelection.Event, FixedNonce, body) == post);
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet,
                RoomFlowSelection.Event, FixedNonce, body) == TerminalClassification.Invalid);
            Check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentPost,
                RoomFlowSelection.Event, FixedNonce, body) == TerminalClassification.Invalid);
            Array.Clear(body);
        }
    }

    private static void TestQueueLateZero()
    {
        var queue = new OwnedByteFrameQueue(() => { });
        byte[] late = Encoding.ASCII.GetBytes("late-canary");
        using var entered = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        Task<OwnedByteDispatchResult> submit = Task.Run(() => queue.Submit(() =>
        {
            entered.Set();
            release.Wait();
            return late;
        }));
        while (queue.OutstandingCount == 0) Thread.Yield();
        Task drain = Task.Run(() => queue.DrainFrame());
        Check(entered.Wait(1000));
        OwnedByteDispatchResult result = submit.GetAwaiter().GetResult();
        Check(result.Status == OwnedByteDispatchStatus.TimedOutAfterClaim && result.Value is null);
        release.Set();
        drain.GetAwaiter().GetResult();
        Check(AllZero(late));
        queue.Stop();
        Check(queue.WaitForSettled(1000));
        queue.Dispose();
    }

    private static void TestStartAndParentGet()
    {
        RuntimeFixture fixture = RuntimeFixture.Create("shop_success");
        byte[] response = fixture.Exchange("GET", ParentGet, null, null);
        Check(Status(response) == "ready" && fixture.Runtime.ReadSubmissionCount == 1);
        fixture.Close();
        Check(fixture.Runtime.IsFullyStopped && fixture.Shop!.PurchaseDisposals == 0);
    }

    private static void TestAuthenticationAndMalformed()
    {
        RuntimeFixture fixture = RuntimeFixture.Create("shop_success");
        byte[] wrong = fixture.ExchangeRaw(Request("GET", ParentGet, null, null, new string('d', 64)));
        Check(wrong.Length == 0 && fixture.Runtime.ReadSubmissionCount == 0);
        byte[] malformed = fixture.ExchangeRaw(Request("GET", ParentGet, null, null)
            .ReplaceAscii("Accept: application/json", "Accept: text/plain"));
        Check(malformed.Length == 0 && fixture.Runtime.ReadSubmissionCount == 0 &&
            !fixture.Runtime.IsTerminalOrStopping);
        fixture.Close();
    }

    private static void TestCompetingAuthenticatedExchange()
    {
        RuntimeFixture fixture = RuntimeFixture.Create("shop_success");
        using var entered = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        fixture.Runtime.AfterAuthenticatedReservationForTests = () =>
        {
            entered.Set();
            release.Wait();
        };
        Task<byte[]> first = fixture.BeginRaw(Request("GET", ParentGet, null, null));
        Check(entered.Wait(1000));
        Task<byte[]> second = fixture.BeginRaw(Request("GET", ParentGet, null, null));
        SpinUntil(() => second.IsCompleted, "competing_second");
        release.Set();
        SpinUntil(() => fixture.Runtime.OutstandingFrameCount == 1, "competing_queued");
        fixture.Runtime.DrainFrame();
        Task.WaitAll(new Task[] { first, second }, 3000);
        SpinUntil(() => fixture.Runtime.TransportStopped, "competing_stopped");
        Check(fixture.Runtime.IsTerminalOrStopping && fixture.Runtime.ReadSubmissionCount <= 1 &&
            first.Result.Length + second.Result.Length > 0);
        Check(fixture.Runtime.DisposeServiceOnOwnerFrame());
    }

    private static void TestCompetingPostAndNoReplay()
    {
        RuntimeFixture fixture = RuntimeFixture.Create("shop_success");
        byte[] readyBody = fixture.Exchange("GET", ParentGet, null, null);
        using JsonDocument ready = JsonDocument.Parse(readyBody);
        string decision = ready.RootElement.GetProperty("decision_id").GetString()!;
        string action = ready.RootElement.GetProperty("legal_actions")[0].GetString()!;
        using var entered = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        fixture.Runtime.AfterAuthenticatedReservationForTests = () =>
        {
            entered.Set();
            release.Wait();
        };
        Task<byte[]> first = fixture.BeginRaw(Request("POST", ParentPost, decision, action));
        Check(entered.Wait(1000));
        Task<byte[]> competing = fixture.BeginRaw(Request("POST", ParentPost, decision, action));
        SpinUntil(() => competing.IsCompleted, "competing_post");
        release.Set();
        SpinUntil(() => fixture.Runtime.OutstandingFrameCount == 1, "original_post_queued");
        fixture.Runtime.DrainFrame();
        Check(Task.WaitAll(new Task[] { first, competing }, 3000));
        SpinUntil(() => fixture.Runtime.TransportStopped, "competing_post_stopped");
        Check(fixture.Shop!.Dispatches == 1 && fixture.Runtime.ReservedParentPosts == 1 &&
            first.Result.Length > 0 && competing.Result.Length == 0);
        byte[] replay;
        try { replay = fixture.Exchange("POST", ParentPost, decision, action); }
        catch { replay = Array.Empty<byte>(); }
        Check(replay.Length == 0 && fixture.Shop.Dispatches == 1);
        Check(fixture.Runtime.DisposeServiceOnOwnerFrame());
    }

    private static void TestBudgetsAndDuplicateReservation()
    {
        RuntimeFixture shop = RuntimeFixture.CreateUnstarted("shop_success");
        string decision = new string('a', 64);
        Check(shop.Runtime.ReservePostForTests(RoomFlowTransportRoute.ParentPost, decision, "buy:card:0"));
        Check(!shop.Runtime.ReservePostForTests(RoomFlowTransportRoute.ParentPost, decision, "buy:card:0"));
        Check(shop.Runtime.ReservePostForTests(RoomFlowTransportRoute.ParentPost, new string('b',64), "inventory:close"));
        Check(shop.Runtime.ReservePostForTests(RoomFlowTransportRoute.ParentPost, new string('c',64), "leave"));
        Check(!shop.Runtime.ReservePostForTests(RoomFlowTransportRoute.ParentPost, new string('d',64), "leave"));
        for (int index = 0; index < RoomFlowTransportLimits.MaximumReads; index++)
            Check(shop.Runtime.ReserveReadForTests());
        Check(!shop.Runtime.ReserveReadForTests());
        shop.Close();

        RuntimeFixture ev = RuntimeFixture.CreateUnstarted("event_item");
        Check(ev.Runtime.ReservePostForTests(RoomFlowTransportRoute.ItemPost, decision, "collect:0"));
        Check(!ev.Runtime.ReservePostForTests(RoomFlowTransportRoute.ItemPost, new string('b',64), "collect:1"));
        for (int index = 0; index < RoomFlowTransportLimits.MaximumEventParentPosts; index++)
            Check(ev.Runtime.ReservePostForTests(RoomFlowTransportRoute.ParentPost,
                index.ToString("x64"), "choose:0"));
        Check(!ev.Runtime.ReservePostForTests(RoomFlowTransportRoute.ParentPost,
            new string('f',64), "choose:0"));
        ev.Close();
    }

    private static void TestLostPostReceipt()
    {
        RuntimeFixture fixture = RuntimeFixture.Create("shop_success");
        byte[] readyBody = fixture.Exchange("GET", ParentGet, null, null);
        using JsonDocument ready = JsonDocument.Parse(readyBody);
        string decision = ready.RootElement.GetProperty("decision_id").GetString()!;
        string action = ready.RootElement.GetProperty("legal_actions")[0].GetString()!;
        fixture.Runtime.DropNextPostResponseForTests = true;
        byte[] response = fixture.Exchange("POST", ParentPost, decision, action);
        SpinUntil(() => fixture.Runtime.TransportStopped, "lost_stopped");
        Check(response.Length == 0 && fixture.Shop!.Dispatches == 1 &&
            fixture.Runtime.IsTerminalOrStopping && fixture.Runtime.ReservedParentPosts == 1);
        Check(fixture.Runtime.DisposeServiceOnOwnerFrame());
    }

    private static void TestOwnerCleanupAndStartFailure()
    {
        RuntimeFixture fixture = RuntimeFixture.CreateUnstarted("shop_success");
        var unbound = new TcpListener(IPAddress.Loopback, 0);
        Check(!fixture.Runtime.StartForTests(unbound) && fixture.Runtime.TransportStopped);
        Check(!Task.Run(() => fixture.Runtime.DisposeServiceOnOwnerFrame()).GetAwaiter().GetResult());
        Check(fixture.Runtime.DisposeServiceOnOwnerFrame() && fixture.Runtime.DisposeServiceOnOwnerFrame());
        Check(!RoomFlowTransportRuntime.IsAllowedTestEndpoint(
            new IPEndPoint(IPAddress.Loopback, RoomFlowTransportLimits.Port)));
    }

    private static void TestPublicSurface()
    {
        string[] names = typeof(RoomFlowTransportRuntime).GetProperties()
            .Where(value => value.GetMethod?.IsPublic == true).Select(value => value.Name).Order().ToArray();
        Check(names.Length == 4 && new HashSet<string>(names, StringComparer.Ordinal).SetEquals(new[]
        {
            "IsFullyStopped", "IsTerminalOrStopping", "ServiceDisposed", "TransportStopped",
        }));
        string[] methods = typeof(RoomFlowTransportRuntime).GetMethods()
            .Where(value => value.IsPublic && value.DeclaringType == typeof(RoomFlowTransportRuntime))
            .Select(value => value.Name).Distinct().Order().ToArray();
        Check(methods.Length == 10 && new HashSet<string>(methods, StringComparer.Ordinal).SetEquals(new[]
        {
            "Create", "Dispose", "DisposeServiceOnOwnerFrame", "DrainFrame", "Start",
            "StopTransportAndJoin", "get_IsFullyStopped", "get_IsTerminalOrStopping",
            "get_ServiceDisposed", "get_TransportStopped",
        }));
    }

    private static int RunFixture(string scenario)
    {
        RuntimeFixture fixture = RuntimeFixture.Create(scenario);
        if (scenario == "lost_receipt") fixture.Runtime.DropNextPostResponseForTests = true;
        Console.WriteLine(JsonSerializer.Serialize(new { port = fixture.Port }));
        Console.Out.Flush();
        Task<string> eof = Task.Run(Console.In.ReadToEnd);
        var limit = Stopwatch.StartNew();
        while (!eof.IsCompleted && !fixture.Runtime.IsTerminalOrStopping && limit.Elapsed < TimeSpan.FromSeconds(20))
        {
            fixture.Runtime.DrainFrame();
            Thread.Sleep(1);
        }
        bool transport = fixture.Runtime.StopTransportAndJoin();
        bool service = fixture.Runtime.DisposeServiceOnOwnerFrame();
        Console.Error.WriteLine(JsonSerializer.Serialize(new
        {
            dispatch_count = fixture.Shop?.Dispatches ?? fixture.Event?.Dispatches ?? 0,
            item_dispatch_count = fixture.Event?.ItemDispatches ?? 0,
            read_count = fixture.Runtime.ReadSubmissionCount,
            terminal = fixture.Runtime.IsTerminalOrStopping,
            transport_stopped = transport,
            service_disposed = service,
        }));
        return transport && service ? 0 : 1;
    }

    private sealed class RuntimeFixture
    {
        private RuntimeFixture(RoomFlowTransportRuntime runtime, ShopFixture? shop, EventFixture? ev)
        {
            Runtime = runtime;
            Shop = shop;
            Event = ev;
        }

        public RoomFlowTransportRuntime Runtime { get; }
        public ShopFixture? Shop { get; }
        public EventFixture? Event { get; }
        public int Port { get; private set; }

        public static RuntimeFixture Create(string scenario)
        {
            RuntimeFixture fixture = CreateUnstarted(scenario);
            var listener = new TcpListener(IPAddress.Loopback, 0);
            listener.Start(RoomFlowTransportLimits.Backlog);
            if (!fixture.Runtime.StartForTests(listener)) throw new InvalidOperationException();
            fixture.Port = ((IPEndPoint)listener.LocalEndpoint).Port;
            return fixture;
        }

        public static RuntimeFixture CreateUnstarted(string scenario)
        {
            bool shopFlow = scenario is "shop_success" or "lost_receipt";
            var shop = shopFlow ? new ShopFixture(scenario) : null;
            var ev = shopFlow ? null : new EventFixture(scenario);
            RoomFlowSelection selection = shopFlow ? RoomFlowSelection.Shop : RoomFlowSelection.Event;
            RoomFlowTransportRuntime runtime = Require(RoomFlowTransportRuntime.Create(
                Configuration(selection),
                () => (byte[])Token.Clone(),
                (selected, nonce) => selected == RoomFlowSelection.Shop
                    ? new RoomFlowWireService(nonce, new ShopV1Session(nonce, shop!.Adapter))
                    : new RoomFlowWireService(nonce,
                        new EventV1Session(nonce, ev!, new FrozenEventItemChildFactory()))));
            return new RuntimeFixture(runtime, shop, ev);
        }

        public byte[] Exchange(string method, string route, string? decision, string? action) =>
            ExchangeRaw(Request(method, route, decision, action));

        public Task<byte[]> BeginRaw(byte[] request) => Task.Factory.StartNew(
            () => SocketExchange(Port, request),
            CancellationToken.None,
            TaskCreationOptions.LongRunning,
            TaskScheduler.Default);

        public byte[] ExchangeRaw(byte[] request)
        {
            Task<byte[]> task = BeginRaw(request);
            var timeout = Stopwatch.StartNew();
            while (!task.IsCompleted && timeout.Elapsed < TimeSpan.FromSeconds(3))
            {
                Runtime.DrainFrame();
                Thread.Sleep(1);
            }
            if (!task.Wait(1000)) throw new InvalidOperationException("Exchange timeout.");
            return HttpBody(task.Result);
        }

        public void Close()
        {
            Check(Runtime.StopTransportAndJoin());
            Check(Runtime.DisposeServiceOnOwnerFrame());
        }
    }

    private sealed class ShopFixture
    {
        private readonly string _mode;
        private readonly object _run = new(), _room = new(), _inventory = new(), _inventoryModel = new();
        private readonly object _player = new(), _map = new(), _back = new(), _merchant = new(), _proceed = new();
        private readonly object _card = new(), _oldCard = new(), _slot = new(), _entry = new(), _control = new(), _label = new();
        private bool _bought, _closed, _left;
        public int Dispatches, PurchaseDisposals;

        public ShopFixture(string mode)
        {
            _mode = mode;
            Adapter = new AdapterImpl(this);
        }

        public IShopV1NativeAdapter Adapter { get; }

        private IReadOnlyList<ShopV1DeckCardBinding> Deck => _bought
            ? new[] { new ShopV1DeckCardBinding(_oldCard, "OLD"), new ShopV1DeckCardBinding(_card, "NEW") }
            : new[] { new ShopV1DeckCardBinding(_oldCard, "OLD") };
        private ShopV1NativeControl MerchantControl() => new(_merchant, true, _closed, null);
        private ShopV1NativeControl ProceedControl() => new(_proceed, true, _closed,
            () => { Dispatches++; _left = true; });

        private sealed class AdapterImpl : IShopV1NativeAdapter
        {
            private readonly ShopFixture _owner;
            public AdapterImpl(ShopFixture owner) { _owner = owner; }
            public ShopV1SurfaceCapture CaptureSurface() => new(ShopV1SurfaceStatus.Available,
                _owner._run, _owner._room, _owner._inventory, _owner._inventoryModel, _owner._player,
                _owner._map, true, !_owner._closed, !_owner._closed, false, _owner._left, _owner._left,
                false, _owner._bought ? 75 : 100, _owner.Deck,
                _owner._bought || _owner._closed ? Array.Empty<ShopV1NativeOffer>() :
                    new[] { new ShopV1NativeOffer(0, ShopV1OfferKind.Card, "NEW", 25, true, true, true,
                        _owner._slot, _owner._entry, _owner._card, _owner._control, _owner._label,
                        new Purchase(_owner)) },
                new ShopV1NativeControl(_owner._back, true, !_owner._closed,
                    () => { _owner.Dispatches++; _owner._closed = true; }),
                _owner.MerchantControl(), _owner.ProceedControl());

            public ShopV1PendingCapture CapturePending(ShopV1PendingProbe probe) => new(
                ShopV1SurfaceStatus.Available, _owner._run, _owner._room, _owner._inventory,
                _owner._inventoryModel, _owner._player, _owner._map, !_owner._left, !_owner._closed,
                !_owner._closed, false, _owner._left, _owner._left, false, _owner._bought ? 75 : 100,
                _owner.Deck, _owner.MerchantControl(), _owner.ProceedControl(), true, _owner._slot,
                _owner._entry, !_owner._bought, _owner._bought ? null : _owner._card,
                _owner._bought ? ShopV1Completion.Succeeded : ShopV1Completion.Pending);
        }

        private sealed class Purchase : IShopV1NativeDispatch
        {
            private readonly ShopFixture _owner;
            public Purchase(ShopFixture owner) { _owner = owner; }
            public ShopV1Completion Completion => _owner._bought
                ? ShopV1Completion.Succeeded : ShopV1Completion.Pending;
            public void Invoke()
            {
                _owner.Dispatches++;
                _owner._bought = true;
                if (_owner._mode == "lost_before_dispatch") throw new InvalidOperationException();
            }
            public void Dispose() { _owner.PurchaseDisposals++; }
        }
    }

    private sealed class EventFixture : IEventV1NativeAdapter, IItemV1NativeAdapter
    {
        private readonly string _mode;
        private readonly object _run = new(), _player = new(), _room = new(), _map = new(), _screen = new();
        private readonly object _reward = new(), _item = new(), _itemButton = new();
        private readonly object[] _buttons = { new(), new(), new() };
        private readonly object[] _options = { new(), new(), new() };
        private int _stage;
        private bool _mapOpen, _collected;
        public int Dispatches, ItemDispatches;
        private bool HasChild => _mode == "event_item";

        public EventFixture(string mode) { _mode = mode; }

        public EventV1SurfaceCapture CaptureSurface()
        {
            if (HasChild && _stage == 1 && !_collected)
                return EventV1SurfaceCapture.ItemChild(_run, _player, _room, _map, _screen, this);
            int display = _stage == 0 ? 0 : _stage is 1 or 2 ? 1 : 2;
            bool final = display == 2;
            var candidates = new List<EventV1NativeCandidate>
            {
                new(0, final ? "PROCEED" : display == 0 ? "FIRST" : "SECOND",
                    final ? "Proceed" : "Option " + display, true, true, false, false, final,
                    _buttons[display], _options[display], () =>
                    {
                        Dispatches++;
                        if (final) _mapOpen = true;
                        else if (_stage == 0) _stage = HasChild ? 1 : 2;
                        else _stage = 3;
                    }),
            };
            return EventV1SurfaceCapture.Parent(
                _run, _player, _room, _map, final, _mapOpen, _mapOpen, false, candidates);
        }

        public EventV1ExitCapture CaptureExit(EventV1ExitProbe probe) =>
            new(_run, _player, _room, _map, _mapOpen, _mapOpen, false);

        ItemV1SurfaceCapture IItemV1NativeAdapter.CaptureSurface() => ItemV1SurfaceCapture.Available(
            _run, _player, _screen, 0,
            new[] { new ItemV1NativeOffer(0, ItemV1ItemKind.Relic, "FIXTURE_RELIC", true,
                false, true, true, _itemButton, _reward, _item,
                () => { ItemDispatches++; _collected = true; _stage = 2; }) },
            Array.Empty<ItemV1PotionSlotBinding>());

        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe) =>
            new(_run, _player, _reward, _item, "FIXTURE_RELIC", _collected,
                _collected ? _item : null, _collected ? "FIXTURE_RELIC" : null, 0,
                Array.Empty<ItemV1PotionSlotBinding>());
    }

    private static byte[] SocketExchange(int port, byte[] request)
    {
        using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        socket.ReceiveTimeout = 3000;
        socket.SendTimeout = 3000;
        socket.Connect(IPAddress.Loopback, port);
        socket.Send(request);
        socket.Shutdown(SocketShutdown.Send);
        using var stream = new MemoryStream();
        byte[] buffer = new byte[8192];
        try
        {
            while (true)
            {
                int read;
                try { read = socket.Receive(buffer); }
                catch (SocketException) { break; }
                if (read == 0) break;
                stream.Write(buffer, 0, read);
            }
            return stream.ToArray();
        }
        finally { Array.Clear(buffer); Array.Clear(request); }
    }

    private static byte[] HttpBody(byte[] response)
    {
        if (response.Length == 0) return response;
        byte[] marker = "\r\n\r\n"u8.ToArray();
        int index = response.AsSpan().IndexOf(marker);
        if (index < 0) throw new InvalidOperationException("Invalid HTTP response.");
        byte[] body = response[(index + marker.Length)..];
        Array.Clear(response);
        Array.Clear(marker);
        return body;
    }

    private static string Status(byte[] body)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(body);
            return document.RootElement.GetProperty("status").GetString()!;
        }
        finally { Array.Clear(body); }
    }

    private static byte[] ShopEnvelope(string status)
    {
        string tail = status switch
        {
            "accepted" => ",\"decision_id\":\"" + new string('a', 64) + "\",\"action_id\":\"inventory:close\"",
            "error" => ",\"code\":\"internal_failure\"",
            "rejected" or "uncertain" => "",
            "unsupported" => "",
            _ => ",\"phase\":\"" + (status == "complete" ? "complete" : "inventory_browse") +
                "\",\"decision_id\":\"\",\"player\":{\"gold\":0,\"deck_count\":0},\"offers\":[],\"legal_actions\":[],\"prior_results\":[]",
        };
        return Encoding.ASCII.GetBytes(
            "{\"schema_version\":1,\"protocol\":\"room_flows_v1\",\"version\":\"shop_v1\",\"flow_kind\":\"shop\",\"session_nonce\":\"" +
            FixedNonce + "\",\"parent_ordinal\":1,\"status\":\"" + status + "\"" + tail + "}");
    }

    private static byte[] EventEnvelope(string status)
    {
        string tail = status switch
        {
            "accepted" => ",\"decision_id\":\"" + new string('a', 64) + "\",\"action_id\":\"choose:0\"",
            "resolved" => ",\"decision_id\":\"" + new string('a', 64) +
                "\",\"action_id\":\"choose:0\",\"result\":\"map_handoff\"",
            "error" => ",\"code\":\"internal_failure\"",
            "rejected" or "uncertain" => "",
            "unsupported" => "",
            _ => ",\"phase\":\"" + (status == "item_child" ? "item_child" : status == "waiting" ? "waiting" : "choose_option") +
                "\",\"decision_id\":\"\",\"candidates\":[{\"rendered_text\":\"status complete resolved error\"}],\"legal_actions\":[]",
        };
        return Encoding.ASCII.GetBytes(
            "{\"schema_version\":1,\"protocol\":\"room_flows_v1\",\"version\":\"event_v1\",\"flow_kind\":\"event\",\"session_nonce\":\"" +
            FixedNonce + "\",\"parent_ordinal\":1,\"status\":\"" + status + "\"" + tail + "}");
    }

    private static byte[] ItemEnvelope(string status)
    {
        string tail = status switch
        {
            "ready" => ",\"decision_id\":\"" + new string('a', 64) +
                "\",\"offers\":[],\"potion_slots\":[],\"legal_actions\":[]",
            "accepted" => ",\"decision_id\":\"" + new string('a', 64) + "\",\"action_id\":\"collect:0\"",
            "resolved" => ",\"decision_id\":\"" + new string('a', 64) +
                "\",\"action_id\":\"collect:0\",\"offer_index\":0,\"kind\":\"relic\",\"key\":\"R\",\"result\":\"collected\"",
            "error" => ",\"code\":\"internal_failure\"",
            _ => "",
        };
        return Encoding.ASCII.GetBytes(
            "{\"schema_version\":1,\"protocol\":\"item_probe_v1\",\"version\":\"item_v1\",\"session_nonce\":\"" +
            FixedNonce + "\",\"surface_ordinal\":1,\"status\":\"" + status + "\"" + tail + "}");
    }

    private static byte[] Request(
        string method,
        string route,
        string? decision,
        string? action,
        string token = TokenText)
    {
        string value = method + " " + route + " HTTP/1.1\r\n" +
            "Host: 127.0.0.1:43117\r\n" +
            "Authorization: Bearer " + token + "\r\n" +
            "Accept: application/json\r\n";
        if (method == "POST")
            value += "X-Sts2-Decision-Id: " + decision + "\r\n" +
                "X-Sts2-Action-Id: " + action + "\r\n";
        value += "Connection: close\r\n\r\n";
        return Encoding.ASCII.GetBytes(value);
    }

    private static byte[] Configuration(RoomFlowSelection selection) => Encoding.ASCII.GetBytes(
        "{\"schema_version\":\"room_flows_v1_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"" +
        (selection == RoomFlowSelection.Shop ? "shop" : "event") +
        "\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");

    private static T Require<T>(T? value) where T : class =>
        value ?? throw new InvalidOperationException("Expected value.");

    private static void SpinUntil(Func<bool> predicate, string label = "condition")
    {
        var timeout = Stopwatch.StartNew();
        while (!predicate() && timeout.Elapsed < TimeSpan.FromSeconds(3)) Thread.Sleep(1);
        if (!predicate()) throw new InvalidOperationException("Timed out: " + label);
    }

    private static bool AllZero(byte[] value) => value.All(item => item == 0);
    private static bool LowerHex(string value) => value.All(item =>
        item is >= '0' and <= '9' or >= 'a' and <= 'f');
    private static void CheckThrows(Action operation)
    {
        bool threw = false;
        try { operation(); }
        catch (InvalidOperationException) { threw = true; }
        Check(threw);
    }
    private static void Check(bool value)
    {
        _checks++;
        if (!value) throw new InvalidOperationException("Fixture check failed.");
    }

    private const string ParentGet = "/probe/room-flows-v1/public/decision";
    private const string ParentPost = "/probe/room-flows-v1/public/action";
    private const string ItemGet = "/probe/item-v1/public/item-decision";
    private const string ItemPost = "/probe/item-v1/public/item-action";

    private static byte[] ReplaceAscii(this byte[] source, string oldValue, string newValue)
    {
        string text = Encoding.ASCII.GetString(source);
        Array.Clear(source);
        return Encoding.ASCII.GetBytes(text.Replace(oldValue, newValue, StringComparison.Ordinal));
    }
}
