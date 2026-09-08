using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal static class Program
{
    private const string FixedNonce = "0123456789abcdef0123456789abcdef";
    private const string TokenText = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    private static readonly byte[] Token = Encoding.ASCII.GetBytes(TokenText);
    private static int _groups;

    public static int Main(string[] args)
    {
        try
        {
            ThreadPool.SetMinThreads(8, 8);
            if (args.Length == 2 && args[0] == "--fixture" &&
                args[1] is "cheese" or "smith" or "lost_receipt")
                return RunFixture(args[1]);
            if (args.Length != 0) return 2;
            Run("configuration_ownership", TestConfigurationAndOwnership);
            Run("protocol_roundtrip", TestProtocol);
            Run("classifier_matrix", TestClassifierMatrix);
            Run("queue_late_zero", TestQueueLateZero);
            Run("cheese_actual_service", () => TestActualSequence(CardSelectionReleaseSelection.Cheese));
            Run("smith_actual_service", () => TestActualSequence(CardSelectionReleaseSelection.Smith));
            Run("authentication_malformed", TestAuthenticationAndMalformed);
            Run("competing_exchange", TestCompetingExchange);
            Run("terminal_cleanup_order", TestTerminalCleanupOrder);
            Run("reservation_budgets", TestBudgetsAndDuplicates);
            Run("lost_receipt", TestLostReceipt);
            Run("claimed_input_ownership", TestClaimedInputOwnership);
            Run("owner_cleanup_surface", TestOwnerCleanupAndSurface);
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                schema_version = 1,
                status = "passed",
                suite = "card_selection_v1_transport",
                check_count = _groups,
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static void Run(string name, Action test)
    {
        try { test(); _groups++; }
        catch (Exception error) { throw new InvalidOperationException(name, error); }
    }

    private static void TestConfigurationAndOwnership()
    {
        foreach (CardSelectionReleaseSelection selection in Enum.GetValues<CardSelectionReleaseSelection>())
        {
            int credentials = 0, factories = 0;
            byte[] config = Configuration(selection);
            byte[] credential = (byte[])Token.Clone();
            CardSelectionReleaseSelection observed = default;
            string? nonce = null;
            Fixture fixture = selection == CardSelectionReleaseSelection.Cheese ? Fixture.Cheese() : Fixture.Smith(3);
            CardSelectionTransportRuntime runtime = Require(CardSelectionTransportRuntime.Create(
                config,
                () => { credentials++; return credential; },
                (value, generated) =>
                {
                    factories++; observed = value; nonce = generated;
                    return fixture.Service(generated);
                }));
            Check(credentials == 1 && factories == 1 && observed == selection && nonce is { Length: 32 } && LowerHex(nonce));
            Check(AllZero(config) && AllZero(credential));
            Check(runtime.StopTransportAndJoin() && runtime.TransportStopped && !runtime.ServiceDisposed);
            Check(runtime.DisposeServiceOnOwnerFrame() && runtime.IsFullyStopped && fixture.DisposeCount == 1);
        }
        byte[] invalid = Encoding.ASCII.GetBytes("disabled");
        int invalidCredentials = 0, invalidFactories = 0;
        Check(CardSelectionTransportRuntime.Create(invalid,
            () => { invalidCredentials++; return (byte[])Token.Clone(); },
            (_, _) => { invalidFactories++; throw new InvalidOperationException(); }) is null);
        Check(invalidCredentials == 0 && invalidFactories == 0 && AllZero(invalid));
        byte[] badCredential = Encoding.ASCII.GetBytes("bad");
        byte[] valid = Configuration(CardSelectionReleaseSelection.Cheese);
        Check(CardSelectionTransportRuntime.Create(valid, () => badCredential,
            (_, _) => throw new InvalidOperationException()) is null && AllZero(valid) && AllZero(badCredential));
    }

    private static void TestProtocol()
    {
        foreach (CardSelectionReleaseSelection selection in Enum.GetValues<CardSelectionReleaseSelection>())
        {
            foreach ((string method, string route, string? decision, string? action, CardSelectionTransportRoute expected) in new[]
            {
                ("GET", ParentGet, (string?)null, (string?)null, CardSelectionTransportRoute.ParentGet),
                ("POST", ParentPost, Hex('a'), "begin", CardSelectionTransportRoute.ParentPost),
                ("GET", ChildGet, (string?)null, (string?)null, CardSelectionTransportRoute.ChildGet),
                ("POST", ChildPost, Hex('b'), "select:63", CardSelectionTransportRoute.ChildPost),
            })
            {
                byte[] request = Request(method, route, decision, action);
                Check(CardSelectionTransportRequestParser.TryParse(request, selection, out var parsed));
                Check(parsed.Route == expected && parsed.IsPost == (method == "POST") && parsed.IsChild == route.Contains("/child", StringComparison.Ordinal));
                if (parsed.IsPost)
                {
                    string d = Encoding.ASCII.GetString(request, parsed.DecisionOffset, parsed.DecisionLength);
                    string a = Encoding.ASCII.GetString(request, parsed.ActionOffset, parsed.ActionLength);
                    byte[] service = CardSelectionTransportServiceBody.Build(d, a);
                    Check(Encoding.ASCII.GetString(service) == "{\"decision_id\":\"" + d + "\",\"action_id\":\"" + a + "\"}");
                    Array.Clear(service);
                }
                Array.Clear(request);
            }
        }
        foreach (byte[] invalid in new[]
        {
            Request("POST", ParentPost, Hex('a'), "select:0"),
            Request("POST", ChildPost, Hex('a'), "select:00"),
            Request("POST", ChildPost, Hex('a'), "select:64"),
            Request("POST", ChildPost, Hex('a'), "select:999999999999999999999999999999999999999999999999999999999999"),
            Request("POST", ChildPost, Hex('A'), "confirm"),
            Request("GET", ParentGet, null, null).ReplaceAscii("Accept: application/json", "Origin: null\r\nAccept: application/json"),
            Request("GET", ParentGet, null, null).ConcatBytes("X"u8),
        })
        {
            Check(!CardSelectionTransportRequestParser.TryParse(invalid, CardSelectionReleaseSelection.Cheese, out _));
            Array.Clear(invalid);
        }
        byte[] maximum = new byte[CardSelectionTransportLimits.MaximumBody];
        Array.Fill(maximum, (byte)'x');
        byte[] wrapped = CardSelectionTransportHttpEncoder.Wrap(maximum);
        Check(wrapped.Length > maximum.Length);
        Throws(() => CardSelectionTransportHttpEncoder.Wrap(new byte[CardSelectionTransportLimits.MaximumBody + 1]));
        Array.Clear(maximum); Array.Clear(wrapped);
    }

    private static void TestClassifierMatrix()
    {
        foreach (CardSelectionReleaseSelection selection in Enum.GetValues<CardSelectionReleaseSelection>())
        {
            var cases = new List<(byte[] Body, CardSelectionTransportRoute Route, TerminalClassification Result)>();
            foreach (string phase in new[] { "initial", "after" })
                cases.Add((ParentObservation(selection, "ready", phase), CardSelectionTransportRoute.ParentGet, TerminalClassification.NonTerminal));
            foreach (string phase in new[] { "initial", "transient", "card_child", "after", "exit" })
                cases.Add((ParentObservation(selection, "waiting", phase), CardSelectionTransportRoute.ParentGet, TerminalClassification.NonTerminal));
            cases.Add((ParentObservation(selection, "unsupported", "unsupported"), CardSelectionTransportRoute.ParentGet, TerminalClassification.Terminal));
            cases.Add((ParentResolved(), CardSelectionTransportRoute.ParentGet, TerminalClassification.Terminal));
            cases.Add((ParentReceipt(), CardSelectionTransportRoute.ParentPost, TerminalClassification.NonTerminal));
            foreach (string outcome in new[] { "rejected", "unsupported", "uncertain" })
                cases.Add((ParentFailure(outcome), CardSelectionTransportRoute.ParentPost, TerminalClassification.Terminal));
            foreach (string phase in new[] { "selecting", "preview" })
                cases.Add((ChildObservation(selection, "ready", phase), CardSelectionTransportRoute.ChildGet, TerminalClassification.NonTerminal));
            foreach (string phase in new[] { "selecting", "submitted", "transient" })
                cases.Add((ChildObservation(selection, "waiting", phase), CardSelectionTransportRoute.ChildGet, TerminalClassification.NonTerminal));
            cases.Add((ChildObservation(selection, "unsupported", "unsupported"), CardSelectionTransportRoute.ChildGet, TerminalClassification.Terminal));
            cases.Add((ChildResolved(selection), CardSelectionTransportRoute.ChildGet, TerminalClassification.NonTerminal));
            cases.Add((ChildReceipt(), CardSelectionTransportRoute.ChildPost, TerminalClassification.NonTerminal));
            foreach (string outcome in new[] { "rejected", "unsupported", "uncertain" })
                cases.Add((ChildFailure(outcome), CardSelectionTransportRoute.ChildPost, TerminalClassification.Terminal));

            foreach ((byte[] body, CardSelectionTransportRoute allowed, TerminalClassification result) in cases)
            {
                foreach (CardSelectionTransportRoute route in Enum.GetValues<CardSelectionTransportRoute>())
                    CheckClass(body, selection, route, 200, route == allowed ? result : TerminalClassification.Invalid);
                CheckClass(body, selection, allowed, 400, TerminalClassification.Invalid);
                CheckClass(body, selection, allowed, 500, TerminalClassification.Invalid);
            }
            CardSelectionReleaseSelection other = selection == CardSelectionReleaseSelection.Cheese
                ? CardSelectionReleaseSelection.Smith : CardSelectionReleaseSelection.Cheese;
            byte[] wrongParentPolicy = ParentObservation(selection, "ready", "initial");
            byte[] wrongChildPolicy = ChildObservation(selection, "ready", "selecting");
            byte[] wrongResolvedPolicy = ChildResolved(selection);
            CheckClass(wrongParentPolicy, other, CardSelectionTransportRoute.ParentGet, 200, TerminalClassification.Invalid);
            CheckClass(wrongChildPolicy, other, CardSelectionTransportRoute.ChildGet, 200, TerminalClassification.Invalid);
            CheckClass(wrongResolvedPolicy, other, CardSelectionTransportRoute.ChildGet, 200, TerminalClassification.Invalid);
            Array.Clear(wrongParentPolicy); Array.Clear(wrongChildPolicy); Array.Clear(wrongResolvedPolicy);
            foreach ((byte[] body, _, _) in cases) Array.Clear(body);
        }
        byte[] badRequest = Error("invalid_request");
        byte[] internalFailure = Error("internal_failure");
        foreach (CardSelectionTransportRoute route in Enum.GetValues<CardSelectionTransportRoute>())
        {
            CheckClass(badRequest, CardSelectionReleaseSelection.Cheese, route, 400, TerminalClassification.Terminal);
            CheckClass(internalFailure, CardSelectionReleaseSelection.Smith, route, 500, TerminalClassification.Terminal);
            CheckClass(badRequest, CardSelectionReleaseSelection.Cheese, route, 200, TerminalClassification.Invalid);
            CheckClass(internalFailure, CardSelectionReleaseSelection.Smith, route, 400, TerminalClassification.Invalid);
        }
        byte[] reordered = ParentObservation(CardSelectionReleaseSelection.Cheese, "ready", "initial")
            .ReplaceAscii(
                "\"version\":\"card_selection_parent_v1\",\"session_nonce\":\"" + FixedNonce + "\"",
                "\"session_nonce\":\"" + FixedNonce + "\",\"version\":\"card_selection_parent_v1\"");
        byte[] duplicate = ParentObservation(CardSelectionReleaseSelection.Cheese, "ready", "initial")
            .ReplaceAscii("\"status\":\"ready\"", "\"status\":\"ready\",\"status\":\"ready\"");
        byte[] nestedStatus = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"Card_0\"", "\"error_resolved_accepted\"");
        CheckClass(reordered, CardSelectionReleaseSelection.Cheese, CardSelectionTransportRoute.ParentGet, 200, TerminalClassification.Invalid);
        CheckClass(duplicate, CardSelectionReleaseSelection.Cheese, CardSelectionTransportRoute.ParentGet, 200, TerminalClassification.Invalid);
        CheckClass(nestedStatus, CardSelectionReleaseSelection.Cheese, CardSelectionTransportRoute.ChildGet, 200, TerminalClassification.NonTerminal);
        CheckClass(badRequest, (CardSelectionReleaseSelection)0, CardSelectionTransportRoute.ParentGet, 400, TerminalClassification.Invalid);
        CheckClass(badRequest, CardSelectionReleaseSelection.Cheese, (CardSelectionTransportRoute)0, 400, TerminalClassification.Invalid);

        byte[] duplicateNested = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"slot\":0", "\"slot\":0,\"slot\":0");
        byte[] reorderedNested = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"slot\":0,\"key\":\"Card_0\"", "\"key\":\"Card_0\",\"slot\":0");
        byte[] malformedKey = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"Card_0\"", "\"bad-key\"");
        byte[] malformedAction = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"select:0\"", "\"select:00\"");
        byte[] malformedHistory = ChildResolved(CardSelectionReleaseSelection.Cheese)
            .ReplaceAscii("\"result\":\"selected\"", "\"result\":\"committed\"");
        byte[] emptyResolved = ChildResolved(CardSelectionReleaseSelection.Cheese)
            .ReplaceAscii(ResolvedCardsJson(CardSelectionReleaseSelection.Cheese), "[]");
        byte[] extraNested = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"selected\":false", "\"selected\":false,\"native\":\"leak\"");
        byte[] negativeLevel = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"upgrade_level\":0", "\"upgrade_level\":-1");
        byte[] wrongBoolean = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"visible\":true", "\"visible\":\"true\"");
        byte[] keyTooLong = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"Card_0\"", "\"" + new string('A', 129) + "\"");
        byte[] candidatesTooMany = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii(CandidateJson(0), "[" + string.Join(',', Enumerable.Range(0, 65).Select(CandidateObjectJson)) + "]");
        byte[] selectedTooMany = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"selected_slots\":[]", "\"selected_slots\":[0,1,2,3,4,5,6,7,8]");
        string actions66 = "[" + string.Join(',', Enumerable.Range(0, 64).Select(index => "\"select:" + index + "\"")) + ",\"preview\",\"confirm\"]";
        byte[] actionsTooMany = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("[\"select:0\"]", actions66);
        string history11 = "[" + string.Join(',', Enumerable.Range(0, 11).Select(index => HistoryObjectJson(index.ToString("x64"), "select:0", "selected"))) + "]";
        byte[] historyTooMany = ChildObservation(CardSelectionReleaseSelection.Cheese, "ready", "selecting")
            .ReplaceAscii("\"prior_results\":[]", "\"prior_results\":" + history11);
        foreach (byte[] invalid in new[] { duplicateNested, reorderedNested, malformedKey, malformedAction,
            malformedHistory, emptyResolved, extraNested, negativeLevel, wrongBoolean, keyTooLong,
            candidatesTooMany, selectedTooMany, actionsTooMany, historyTooMany })
        {
            CheckClass(invalid, CardSelectionReleaseSelection.Cheese, CardSelectionTransportRoute.ChildGet, 200, TerminalClassification.Invalid);
            Array.Clear(invalid);
        }

        string candidates64 = "[" + string.Join(',', Enumerable.Range(0, 64).Select(CandidateObjectJson)) + "]";
        byte[] maximumCandidates = ChildObservation(CardSelectionReleaseSelection.Smith, "ready", "selecting")
            .ReplaceAscii(CandidateJson(0), candidates64);
        string actions65 = "[" + string.Join(',', Enumerable.Range(0, 64).Select(index => "\"select:" + index + "\"")) + ",\"preview\"]";
        byte[] maximumActions = ChildObservation(CardSelectionReleaseSelection.Smith, "ready", "selecting")
            .ReplaceAscii("[\"select:0\"]", actions65);
        string history10 = "[" + string.Join(',', Enumerable.Range(0, 10).Select(index => HistoryObjectJson(index.ToString("x64"), "select:0", "selected"))) + "]";
        byte[] maximumHistory = ChildObservation(CardSelectionReleaseSelection.Smith, "ready", "selecting")
            .ReplaceAscii("\"prior_results\":[]", "\"prior_results\":" + history10);
        foreach (byte[] valid in new[] { maximumCandidates, maximumActions, maximumHistory })
        {
            CheckClass(valid, CardSelectionReleaseSelection.Smith, CardSelectionTransportRoute.ChildGet, 200, TerminalClassification.NonTerminal);
            Array.Clear(valid);
        }
        Array.Clear(badRequest); Array.Clear(internalFailure); Array.Clear(reordered); Array.Clear(duplicate); Array.Clear(nestedStatus);
    }

    private static void TestQueueLateZero()
    {
        var queue = new OwnedByteFrameQueue(() => { });
        byte[] late = Encoding.ASCII.GetBytes("late-canary");
        using var entered = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        Task<OwnedByteDispatchResult> submit = Task.Run(() => queue.Submit(() =>
        {
            entered.Set(); release.Wait(); return new OwnedServiceResponse(200, late);
        }));
        SpinUntil(() => queue.OutstandingCount == 1);
        Task drain = Task.Run(() => queue.DrainFrame());
        Check(entered.Wait(1000));
        OwnedByteDispatchResult result = submit.GetAwaiter().GetResult();
        Check(result.Status == OwnedByteDispatchStatus.TimedOutAfterClaim && result.Value is null);
        release.Set(); drain.GetAwaiter().GetResult();
        Check(AllZero(late));
        queue.Stop(); Check(queue.WaitForSettled(1000)); queue.Dispose();
    }

    private static void TestActualSequence(CardSelectionReleaseSelection selection)
    {
        RuntimeFixture runtime = RuntimeFixture.Create(selection, false);
        RunSequence(runtime, selection);
        SpinUntil(() => runtime.Runtime.TransportStopped, "terminal stop");
        Check(runtime.Runtime.IsTerminalOrStopping && runtime.Runtime.ReservedParentPosts == 2 &&
            runtime.Runtime.ReservedChildPosts == 2 && runtime.Fixture.DispatchCount == 4);
        Check(runtime.Runtime.DisposeServiceOnOwnerFrame() && runtime.Runtime.IsFullyStopped);
    }

    private static void RunSequence(RuntimeFixture runtime, CardSelectionReleaseSelection selection)
    {
        JsonElement parent = runtime.Get(ParentGet);
        string begin = Text(parent, "decision_id");
        runtime.Post(ParentPost, begin, "begin");
        JsonElement phase = runtime.Get(ParentGet);
        Check(Text(phase, "status") == "waiting" && Text(phase, "phase") == "card_child");
        JsonElement child = runtime.Get(ChildGet);
        string first = Text(child, "decision_id");
        runtime.Post(ChildPost, first, "select:0");
        child = runtime.Get(ChildGet);
        string second = Text(child, "decision_id");
        if (selection == CardSelectionReleaseSelection.Cheese)
            runtime.Post(ChildPost, second, "select:1");
        else
            runtime.Post(ChildPost, second, "confirm");
        JsonElement resolved = runtime.Get(ChildGet);
        Check(Text(resolved, "kind") == "child_resolved");
        parent = runtime.Get(ParentGet);
        Check(Text(parent, "phase") == "after");
        runtime.Post(ParentPost, Text(parent, "decision_id"), "proceed");
        JsonElement done = runtime.Get(ParentGet);
        Check(Text(done, "kind") == "parent_resolved");
    }

    private static void TestAuthenticationAndMalformed()
    {
        RuntimeFixture runtime = RuntimeFixture.Create(CardSelectionReleaseSelection.Cheese, false);
        byte[] wrong = runtime.ExchangeRaw(Request("GET", ParentGet, null, null, new string('d', 64)));
        byte[] malformed = runtime.ExchangeRaw(Request("GET", ParentGet, null, null)
            .ReplaceAscii("Accept: application/json", "Accept: text/plain"));
        Check(wrong.Length == 0 && malformed.Length == 0 && runtime.Runtime.ReadSubmissionCount == 0 && !runtime.Runtime.IsTerminalOrStopping);
        runtime.Close();
    }

    private static void TestCompetingExchange()
    {
        RuntimeFixture runtime = RuntimeFixture.Create(CardSelectionReleaseSelection.Cheese, false);
        using var entered = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        runtime.Runtime.AfterAuthenticatedReservationForTests = () => { entered.Set(); release.Wait(); };
        Task<byte[]> first = runtime.BeginRaw(Request("GET", ParentGet, null, null));
        Check(entered.Wait(1000));
        Task<byte[]> second = runtime.BeginRaw(Request("GET", ParentGet, null, null));
        SpinUntil(() => second.IsCompleted, "competing close");
        release.Set();
        SpinUntil(() => runtime.Runtime.OutstandingFrameCount == 1, "queued first");
        runtime.Runtime.DrainFrame();
        Check(Task.WaitAll(new Task[] { first, second }, 3000));
        SpinUntil(() => runtime.Runtime.TransportStopped, "competing stop");
        Check(first.Result.Length + second.Result.Length > 0 && runtime.Runtime.ReadSubmissionCount <= 1);
        Check(runtime.Runtime.DisposeServiceOnOwnerFrame());
    }

    private static void TestBudgetsAndDuplicates()
    {
        RuntimeFixture runtime = RuntimeFixture.CreateUnstarted(CardSelectionReleaseSelection.Cheese);
        string decision = Hex('a');
        Check(runtime.Runtime.ReservePostForTests(CardSelectionTransportRoute.ParentPost, decision, "begin"));
        Check(!runtime.Runtime.ReservePostForTests(CardSelectionTransportRoute.ParentPost, decision, "begin"));
        Check(runtime.Runtime.ReservePostForTests(CardSelectionTransportRoute.ParentPost, decision, "proceed"));
        Check(!runtime.Runtime.ReservePostForTests(CardSelectionTransportRoute.ParentPost, Hex('b'), "begin"));
        for (int index = 0; index < CardSelectionTransportLimits.MaximumChildPosts; index++)
            Check(runtime.Runtime.ReservePostForTests(CardSelectionTransportRoute.ChildPost, index.ToString("x64"), "select:0"));
        Check(!runtime.Runtime.ReservePostForTests(CardSelectionTransportRoute.ChildPost, Hex('f'), "select:1"));
        for (int index = 0; index < CardSelectionTransportLimits.MaximumReads; index++) Check(runtime.Runtime.ReserveReadForTests());
        Check(!runtime.Runtime.ReserveReadForTests());
        runtime.Close();
    }

    private static void TestTerminalCleanupOrder()
    {
        RuntimeFixture runtime = RuntimeFixture.Create(CardSelectionReleaseSelection.Cheese, false);
        JsonElement parent = runtime.Get(ParentGet);
        string decision = Text(parent, "decision_id");
        runtime.Post(ParentPost, decision, "begin");
        byte[]? rejectedRequest = null;
        Socket? rejectedSocket = null;
        using var entered = new ManualResetEventSlim(false);
        using var release = new ManualResetEventSlim(false);
        runtime.Runtime.BeforeTerminalCleanupForTests = (request, socket) =>
        {
            rejectedRequest = request;
            rejectedSocket = socket;
            entered.Set();
            release.Wait();
        };
        Task<byte[]> duplicate = runtime.BeginRaw(Request("POST", ParentPost, decision, "begin"));
        Check(entered.Wait(1000));
        Check(!runtime.Runtime.IsTerminalOrStopping && rejectedRequest is not null &&
            !AllZero(rejectedRequest) && rejectedSocket is not null && !rejectedSocket.SafeHandle.IsClosed);
        byte[] ownedRequest = rejectedRequest ?? throw new InvalidOperationException("missing rejected request");
        Socket ownedSocket = rejectedSocket ?? throw new InvalidOperationException("missing rejected socket");
        int capturesBeforeSuppressed = runtime.Fixture.TotalCaptureCount;
        Task<byte[]> suppressed = runtime.BeginRaw(Request("GET", ParentGet, null, null));
        Check(suppressed.Wait(3000) && suppressed.Result.Length == 0 &&
            runtime.Fixture.TotalCaptureCount == capturesBeforeSuppressed &&
            runtime.Runtime.ReadSubmissionCount == 1 && !runtime.Runtime.IsTerminalOrStopping);
        release.Set();
        Check(duplicate.Wait(3000) && duplicate.Result.Length == 0);
        SpinUntil(() => runtime.Runtime.TransportStopped, "duplicate cleanup stop");
        Check(AllZero(ownedRequest) && ownedSocket.SafeHandle.IsClosed &&
            runtime.Fixture.DispatchCount == 1 && runtime.Runtime.ReservedParentPosts == 1);
        Check(runtime.Runtime.DisposeServiceOnOwnerFrame());
    }

    private static void TestLostReceipt()
    {
        RuntimeFixture runtime = RuntimeFixture.Create(CardSelectionReleaseSelection.Cheese, true);
        JsonElement parent = runtime.Get(ParentGet);
        byte[] response = runtime.Exchange("POST", ParentPost, Text(parent, "decision_id"), "begin");
        SpinUntil(() => runtime.Runtime.TransportStopped, "lost receipt stop");
        Check(response.Length == 0 && runtime.Fixture.DispatchCount == 1 && runtime.Runtime.ReservedParentPosts == 1);
        Check(runtime.Runtime.DisposeServiceOnOwnerFrame());
    }

    private static void TestClaimedInputOwnership()
    {
        RuntimeFixture runtime = RuntimeFixture.Create(CardSelectionReleaseSelection.Cheese, false);
        JsonElement parent = runtime.Get(ParentGet);
        byte[]? captured = null;
        bool remainedOwned = false;
        using var release = new ManualResetEventSlim(false);
        runtime.Runtime.ServiceBodyOwnedForTests = value =>
        {
            captured = value;
            _ = Task.Run(() =>
            {
                Thread.Sleep(650);
                remainedOwned = !AllZero(value);
                release.Set();
            });
            release.Wait();
        };
        byte[] response = runtime.Exchange("POST", ParentPost, Text(parent, "decision_id"), "begin");
        SpinUntil(() => runtime.Runtime.TransportStopped, "claimed timeout stop");
        Check(response.Length == 0 && remainedOwned && captured is not null && AllZero(captured) &&
            runtime.Fixture.DispatchCount == 1 && runtime.Runtime.ReservedParentPosts == 1);
        Check(runtime.Runtime.DisposeServiceOnOwnerFrame());
    }

    private static void TestOwnerCleanupAndSurface()
    {
        RuntimeFixture runtime = RuntimeFixture.CreateUnstarted(CardSelectionReleaseSelection.Cheese);
        var unbound = new TcpListener(IPAddress.Loopback, 0);
        Check(!runtime.Runtime.StartForTests(unbound) && runtime.Runtime.TransportStopped);
        Check(!Task.Run(runtime.Runtime.DisposeServiceOnOwnerFrame).GetAwaiter().GetResult());
        Check(runtime.Runtime.DisposeServiceOnOwnerFrame() && runtime.Runtime.DisposeServiceOnOwnerFrame());
        Check(!CardSelectionTransportRuntime.IsAllowedTestEndpoint(new IPEndPoint(IPAddress.Loopback, CardSelectionTransportLimits.Port)));
        string[] properties = typeof(CardSelectionTransportRuntime).GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Select(x => x.Name).Order().ToArray();
        Check(properties.SequenceEqual(new[] { "IsFullyStopped", "IsTerminalOrStopping", "ServiceDisposed", "TransportStopped" }));
        string[] methods = typeof(CardSelectionTransportRuntime).GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static)
            .Where(x => x.DeclaringType == typeof(CardSelectionTransportRuntime)).Select(x => x.Name).Distinct().Order().ToArray();
        Check(methods.SequenceEqual(new[] { "Create", "Dispose", "DisposeServiceOnOwnerFrame", "DrainFrame",
            "get_IsFullyStopped", "get_IsTerminalOrStopping", "get_ServiceDisposed", "get_TransportStopped",
            "Start", "StopTransportAndJoin" }));
    }

    private static int RunFixture(string scenario)
    {
        CardSelectionReleaseSelection selection = scenario == "smith"
            ? CardSelectionReleaseSelection.Smith : CardSelectionReleaseSelection.Cheese;
        RuntimeFixture? runtime = null;
        bool stopped = false;
        bool disposed = false;
        bool terminal = false;
        try
        {
            runtime = RuntimeFixture.Create(selection, scenario == "lost_receipt");
            Console.WriteLine(JsonSerializer.Serialize(new { schema_version = 1, status = "ready", port = runtime.Port }));
            Console.Out.Flush();
            var deadline = Stopwatch.StartNew();
            while (!runtime.Runtime.IsTerminalOrStopping && deadline.Elapsed < TimeSpan.FromSeconds(35))
            {
                runtime.Runtime.DrainFrame();
                Thread.Sleep(1);
            }
            terminal = runtime.Runtime.IsTerminalOrStopping;
        }
        finally
        {
            if (runtime is not null)
            {
                stopped = runtime.Runtime.StopTransportAndJoin();
                disposed = runtime.Runtime.DisposeServiceOnOwnerFrame();
                Console.Error.WriteLine(JsonSerializer.Serialize(new
                {
                    schema_version = 1,
                    status = "fixture_complete",
                    capture_count = runtime.Fixture.TotalCaptureCount,
                    dispatch_count = runtime.Fixture.DispatchCount,
                    parent_post_count = runtime.Runtime.ReservedParentPosts,
                    child_post_count = runtime.Runtime.ReservedChildPosts,
                    read_count = runtime.Runtime.ReadSubmissionCount,
                    transport_stopped = stopped && runtime.Runtime.TransportStopped,
                    service_disposed = disposed && runtime.Runtime.ServiceDisposed,
                }));
            }
        }
        return terminal && stopped && disposed ? 0 : 1;
    }

    private sealed class RuntimeFixture
    {
        private RuntimeFixture(CardSelectionTransportRuntime runtime, Fixture fixture)
        { Runtime = runtime; Fixture = fixture; }
        internal CardSelectionTransportRuntime Runtime { get; }
        internal Fixture Fixture { get; }
        internal int Port { get; private set; }

        internal static RuntimeFixture Create(CardSelectionReleaseSelection selection, bool lost)
        {
            RuntimeFixture result = CreateUnstarted(selection);
            var listener = new TcpListener(IPAddress.Loopback, 0);
            listener.Start(CardSelectionTransportLimits.Backlog);
            if (lost) result.Runtime.DropNextPostResponseForTests = true;
            if (!result.Runtime.StartForTests(listener)) throw new InvalidOperationException("start");
            result.Port = ((IPEndPoint)listener.LocalEndpoint).Port;
            return result;
        }

        internal static RuntimeFixture CreateUnstarted(CardSelectionReleaseSelection selection)
        {
            Fixture fixture = selection == CardSelectionReleaseSelection.Cheese ? Fixture.Cheese() : Fixture.Smith(3);
            CardSelectionTransportRuntime runtime = Require(CardSelectionTransportRuntime.Create(
                Configuration(selection), () => (byte[])Token.Clone(),
                (actual, nonce) => actual == selection ? fixture.Service(nonce) : throw new InvalidOperationException()));
            return new(runtime, fixture);
        }

        internal JsonElement Get(string route) => Json(Exchange("GET", route, null, null));
        internal void Post(string route, string decision, string action)
        {
            JsonElement value = Json(Exchange("POST", route, decision, action));
            Check(value.GetProperty("outcome").GetString() == "accepted");
        }
        internal byte[] Exchange(string method, string route, string? decision, string? action) =>
            HttpBody(ExchangeRaw(Request(method, route, decision, action)));
        internal byte[] ExchangeRaw(byte[] request)
        {
            Task<byte[]> task = BeginRaw(request);
            var timeout = Stopwatch.StartNew();
            while (!task.IsCompleted && timeout.Elapsed < TimeSpan.FromSeconds(3))
            { Runtime.DrainFrame(); Thread.Sleep(1); }
            if (!task.Wait(1000)) throw new InvalidOperationException("exchange timeout");
            return task.Result;
        }
        internal Task<byte[]> BeginRaw(byte[] request) => Task.Factory.StartNew(
            () => SocketExchange(Port, request), CancellationToken.None,
            TaskCreationOptions.LongRunning, TaskScheduler.Default);
        internal void Close()
        {
            Check(Runtime.StopTransportAndJoin());
            Check(Runtime.DisposeServiceOnOwnerFrame());
        }
    }

    private static byte[] SocketExchange(int port, byte[] request)
    {
        using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        socket.ReceiveTimeout = 3000; socket.SendTimeout = 3000;
        socket.Connect(IPAddress.Loopback, port);
        socket.Send(request); socket.Shutdown(SocketShutdown.Send);
        using var stream = new MemoryStream();
        byte[] buffer = new byte[8192];
        try
        {
            while (true)
            {
                int read;
                try { read = socket.Receive(buffer); } catch (SocketException) { break; }
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
        int index = response.AsSpan().IndexOf("\r\n\r\n"u8);
        if (index < 0) throw new InvalidOperationException("http response");
        byte[] body = response[(index + 4)..]; Array.Clear(response); return body;
    }
    private static JsonElement Json(byte[] body)
    {
        try { using JsonDocument doc = JsonDocument.Parse(body); return doc.RootElement.Clone(); }
        finally { Array.Clear(body); }
    }
    private static string Text(JsonElement value, string name) => value.GetProperty(name).GetString()!;

    private static void CheckClass(byte[] body, CardSelectionReleaseSelection selection,
        CardSelectionTransportRoute route, int statusCode, TerminalClassification expected) =>
        Check(CardSelectionTerminalClassifier.Classify(route, selection, FixedNonce, statusCode, body) == expected);

    private static byte[] ParentObservation(CardSelectionReleaseSelection selection, string status, string phase)
    {
        bool ready = status == "ready";
        string kind = selection == CardSelectionReleaseSelection.Cheese ? "event" : "rest";
        string policy = selection == CardSelectionReleaseSelection.Cheese ? "cheese_gorge_add_two" : "rest_smith_upgrade_one";
        return Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"parent_observation\",\"version\":\"card_selection_parent_v1\",\"session_nonce\":\"" + FixedNonce +
            "\",\"parent_ordinal\":1,\"status\":\"" + status + "\",\"phase\":\"" + phase + "\",\"parent_kind\":\"" + (ready ? kind : "") +
            "\",\"policy\":\"" + (ready ? policy : "") + "\",\"decision_id\":\"" + (ready ? Hex('a') : "") +
            "\",\"legal_actions\":" + (ready ? phase == "after" ? "[\"proceed\"]" : "[\"begin\"]" : "[]") + "}");
    }
    private static byte[] ParentReceipt() => Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"parent_receipt\",\"version\":\"card_selection_parent_v1\",\"session_nonce\":\"" + FixedNonce + "\",\"parent_ordinal\":1,\"decision_id\":\"" + Hex('a') + "\",\"action_id\":\"begin\",\"outcome\":\"accepted\"}");
    private static byte[] ParentFailure(string outcome) => Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"parent_failure\",\"version\":\"card_selection_parent_v1\",\"session_nonce\":\"" + FixedNonce + "\",\"parent_ordinal\":1,\"outcome\":\"" + outcome + "\"}");
    private static byte[] ParentResolved() => Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"parent_resolved\",\"version\":\"card_selection_parent_v1\",\"session_nonce\":\"" + FixedNonce + "\",\"parent_ordinal\":1,\"status\":\"resolved\",\"result\":\"map_handoff\",\"begin_decision_id\":\"" + Hex('a') + "\",\"begin_action_id\":\"begin\",\"proceed_decision_id\":\"" + Hex('b') + "\",\"proceed_action_id\":\"proceed\"}");
    private static byte[] ChildObservation(CardSelectionReleaseSelection selection, string status, string phase)
    {
        bool ready = status == "ready";
        string op = selection == CardSelectionReleaseSelection.Cheese ? "add" : "upgrade";
        string commit = selection == CardSelectionReleaseSelection.Cheese ? "auto_at_max" : "preview_confirm";
        int count = selection == CardSelectionReleaseSelection.Cheese ? 2 : 1;
        string candidates = ready ? "[{\"slot\":0,\"key\":\"Card_0\",\"upgrade_level\":0,\"visible\":true,\"enabled\":true,\"selected\":false}]" : "[]";
        return Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"child_observation\",\"version\":\"card_selection_v1\",\"session_nonce\":\"" + FixedNonce +
            "\",\"parent_ordinal\":1,\"status\":\"" + status + "\",\"phase\":\"" + phase + "\",\"operation\":\"" + (ready ? op : "") +
            "\",\"commit_mode\":\"" + (ready ? commit : "") + "\",\"min_select\":" + (ready ? count : 0) + ",\"max_select\":" + (ready ? count : 0) +
            ",\"decision_id\":\"" + (ready ? Hex('c') : "") + "\",\"candidates\":" + candidates + ",\"selected_slots\":[],\"legal_actions\":" +
            (ready ? phase == "preview" ? "[\"confirm\"]" : "[\"select:0\"]" : "[]") + ",\"prior_results\":[]}");
    }
    private static byte[] ChildReceipt() => Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"child_receipt\",\"version\":\"card_selection_v1\",\"session_nonce\":\"" + FixedNonce + "\",\"parent_ordinal\":1,\"decision_id\":\"" + Hex('c') + "\",\"action_id\":\"select:0\",\"outcome\":\"accepted\"}");
    private static byte[] ChildFailure(string outcome) => Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"child_failure\",\"version\":\"card_selection_v1\",\"session_nonce\":\"" + FixedNonce + "\",\"parent_ordinal\":1,\"outcome\":\"" + outcome + "\"}");
    private static byte[] ChildResolved(CardSelectionReleaseSelection selection) => Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"child_resolved\",\"version\":\"card_selection_v1\",\"session_nonce\":\"" + FixedNonce + "\",\"parent_ordinal\":1,\"status\":\"resolved\",\"phase\":\"complete\",\"operation\":\"" + (selection == CardSelectionReleaseSelection.Cheese ? "add" : "upgrade") + "\",\"selected_cards\":" + ResolvedCardsJson(selection) + ",\"prior_results\":" + ResolvedHistoryJson(selection) + "}");
    private static string ResolvedCardsJson(CardSelectionReleaseSelection selection) => selection == CardSelectionReleaseSelection.Cheese
        ? "[{\"slot\":0,\"key\":\"Card_0\",\"upgrade_level\":0,\"visible\":true,\"enabled\":true,\"selected\":true},{\"slot\":1,\"key\":\"Card_1\",\"upgrade_level\":0,\"visible\":true,\"enabled\":true,\"selected\":true}]"
        : "[{\"slot\":0,\"key\":\"Card_0\",\"upgrade_level\":0,\"visible\":true,\"enabled\":true,\"selected\":true}]";
    private static string ResolvedHistoryJson(CardSelectionReleaseSelection selection) => selection == CardSelectionReleaseSelection.Cheese
        ? "[{\"decision_id\":\"" + Hex('c') + "\",\"action_id\":\"select:0\",\"result\":\"selected\"},{\"decision_id\":\"" + Hex('d') + "\",\"action_id\":\"select:1\",\"result\":\"selected\"}]"
        : "[{\"decision_id\":\"" + Hex('c') + "\",\"action_id\":\"select:0\",\"result\":\"selected\"},{\"decision_id\":\"" + Hex('d') + "\",\"action_id\":\"confirm\",\"result\":\"committed\"}]";
    private static string CandidateJson(int slot) => "[" + CandidateObjectJson(slot) + "]";
    private static string CandidateObjectJson(int slot) => "{\"slot\":" + slot + ",\"key\":\"Card_" + slot +
        "\",\"upgrade_level\":0,\"visible\":true,\"enabled\":true,\"selected\":false}";
    private static string HistoryObjectJson(string decision, string action, string result) =>
        "{\"decision_id\":\"" + decision + "\",\"action_id\":\"" + action + "\",\"result\":\"" + result + "\"}";
    private static byte[] Error(string code) => Encoding.ASCII.GetBytes("{\"schema_version\":1,\"kind\":\"error\",\"status\":\"error\",\"code\":\"" + code + "\"}");

    private static byte[] Request(string method, string route, string? decision, string? action, string token = TokenText)
    {
        string value = method + " " + route + " HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer " + token + "\r\nAccept: application/json\r\n";
        if (method == "POST") value += "X-Sts2-Decision-Id: " + decision + "\r\nX-Sts2-Action-Id: " + action + "\r\n";
        return Encoding.ASCII.GetBytes(value + "Connection: close\r\n\r\n");
    }
    private static byte[] Configuration(CardSelectionReleaseSelection selection) => Encoding.ASCII.GetBytes(
        "{\"schema_version\":\"card_selection_v1_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"" +
        (selection == CardSelectionReleaseSelection.Cheese ? "cheese" : "smith") +
        "\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static string Hex(char value, int length = 64) => new(value, length);
    private static T Require<T>(T? value) where T : class => value ?? throw new InvalidOperationException("required");
    private static void SpinUntil(Func<bool> condition, string label = "condition")
    { var watch = Stopwatch.StartNew(); while (!condition() && watch.Elapsed < TimeSpan.FromSeconds(3)) Thread.Sleep(1); if (!condition()) throw new InvalidOperationException(label); }
    private static bool LowerHex(string value) => value.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');
    private static bool AllZero(byte[] value) => value.All(x => x == 0);
    private static void Throws(Action action) { bool threw = false; try { action(); } catch (InvalidOperationException) { threw = true; } Check(threw); }
    private static void Check(bool value) { if (!value) throw new InvalidOperationException("check failed"); }
    private const string ParentGet = "/card-selection-v1/parent";
    private const string ParentPost = "/card-selection-v1/parent/action";
    private const string ChildGet = "/card-selection-v1/child";
    private const string ChildPost = "/card-selection-v1/child/action";
    private static byte[] ReplaceAscii(this byte[] source, string oldValue, string newValue)
    { string text = Encoding.ASCII.GetString(source); Array.Clear(source); return Encoding.ASCII.GetBytes(text.Replace(oldValue, newValue, StringComparison.Ordinal)); }
    private static byte[] ConcatBytes(this byte[] source, ReadOnlySpan<byte> suffix)
    { byte[] result = new byte[source.Length + suffix.Length]; source.CopyTo(result, 0); suffix.CopyTo(result.AsSpan(source.Length)); Array.Clear(source); return result; }
    private sealed class Fixture : ICardSelectionParentV1NativeAdapter
    {
        private readonly Action _begin;
        private readonly Action _proceed;
        private readonly object _beginIdentity = new();
        private readonly object _proceedIdentity = new();
        private bool _capturing;

        private Fixture(CardSelectionParentV1Policy policy, int keyLength)
        {
            Policy = policy;
            Factory = new ChildFactory(this, keyLength);
            _begin = () =>
            {
                DispatchCount++;
                if (ThrowBegin) throw new InvalidOperationException("begin");
                Phase = CardSelectionParentV1Phase.Child;
                Witness = Hex('b'); NoActiveOverlay = false; TravelEnabled = false;
            };
            _proceed = () =>
            {
                DispatchCount++;
                Phase = CardSelectionParentV1Phase.Exit; Witness = Hex('d');
                MapOpen = true; TravelEnabled = true; NoActiveOverlay = true;
            };
        }

        internal static Fixture Cheese() => new(new CardSelectionParentV1Policy(
            CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo, CardSelectionV1ParentKind.Event,
            CardSelectionParentV1Limits.CheeseGorgeStableKey, 0,
            CardSelectionV1Operation.Add, 2, 2, CardSelectionV1CommitMode.AutoAtMax, 8), 0);

        internal static Fixture Smith(int domain, int keyLength = 0) => new(new CardSelectionParentV1Policy(
            CardSelectionParentV1PolicyKind.RestSmithUpgradeOne, CardSelectionV1ParentKind.Rest,
            CardSelectionParentV1Limits.SmithStableKey, 1,
            CardSelectionV1Operation.Upgrade, 1, 1, CardSelectionV1CommitMode.PreviewConfirm, domain), keyLength);

        internal CardSelectionV1WireService Service(string nonce) => new(nonce, new CardSelectionParentV1Session(nonce, this));
        internal int TotalCaptureCount => CaptureCount + Factory.CaptureCount;
        internal CardSelectionParentV1Policy Policy { get; }
        internal ChildFactory Factory { get; }
        internal object Run { get; } = new();
        internal object Player { get; } = new();
        internal object Room { get; } = new();
        internal object Map { get; } = new();
        internal object Option { get; } = new();
        internal object Controller { get; } = new();
        internal object Screen { get; } = new();
        internal CardSelectionParentV1Phase Phase { get; set; } = CardSelectionParentV1Phase.Initial;
        internal string Witness { get; set; } = Hex('a');
        internal bool NoActiveOverlay { get; set; } = true;
        internal bool MapOpen { get; set; }
        internal bool TravelEnabled { get; set; }
        internal bool EffectObserved { get; set; }
        internal bool ThrowBegin { get; set; }
        internal Action? CaptureCallback { get; set; }
        internal int DispatchCount { get; set; }
        internal int CaptureCount { get; private set; }
        internal int DisposeCount { get; private set; }

        internal void EnterAfter()
        {
            Phase = CardSelectionParentV1Phase.After; Witness = Hex('c');
            NoActiveOverlay = true; MapOpen = false;
            TravelEnabled = Policy.ParentKind == CardSelectionV1ParentKind.Rest;
            EffectObserved = true;
        }

        public CardSelectionParentV1SurfaceCapture CaptureSurface()
        {
            CaptureCount++;
            if (!_capturing && CaptureCallback is not null)
            {
                _capturing = true;
                try { CaptureCallback(); }
                finally { _capturing = false; }
            }
            bool initial = Phase == CardSelectionParentV1Phase.Initial;
            bool child = Phase == CardSelectionParentV1Phase.Child;
            bool after = Phase == CardSelectionParentV1Phase.After;
            return new CardSelectionParentV1SurfaceCapture(
                CardSelectionParentV1SurfaceStatus.Available, Phase, Policy,
                Run, Player, Room, Map, Option, Controller, Witness,
                NoActiveOverlay, MapOpen, TravelEnabled, false,
                after && Policy.ParentKind == CardSelectionV1ParentKind.Event,
                after && Policy.ParentKind == CardSelectionV1ParentKind.Event,
                after && Policy.ParentKind == CardSelectionV1ParentKind.Rest,
                EffectObserved, child ? Screen : null, child ? Factory : null,
                initial ? new CardSelectionParentV1NativeControl(_beginIdentity, true, true, _begin) : null,
                after ? new CardSelectionParentV1NativeControl(_proceedIdentity, true, true, _proceed) : null);
        }

        public void Dispose() => DisposeCount++;
    }

    private sealed class ChildFactory : ICardSelectionParentV1ChildFactory
    {
        private readonly Fixture _parent;
        private readonly int _keyLength;
        internal int CaptureCount => Last?.CaptureCount ?? 0;
        private ChildAdapter? Last;
        internal ChildFactory(Fixture parent, int keyLength) { _parent = parent; _keyLength = keyLength; }
        public ICardSelectionV1NativeAdapter Create(CardSelectionV1ParentContext context, object exactScreenIdentity)
        {
            Last = new ChildAdapter(_parent, context, exactScreenIdentity, _keyLength);
            return Last;
        }
    }

    private sealed class ChildAdapter : ICardSelectionV1NativeAdapter
    {
        private readonly Fixture _parent;
        private readonly CardSelectionV1ParentContext _context;
        private readonly object _screen;
        private readonly object _task = new();
        private readonly object _preview = new();
        private readonly object _previewControl = new();
        private readonly object _confirmControl = new();
        private readonly Action _previewDispatch;
        private readonly Action _confirmDispatch;
        private readonly object[] _models;
        private readonly object[] _holders;
        private readonly object[] _nodes;
        private readonly string[] _keys;
        private readonly bool[] _selected;
        private readonly Action[] _select;
        private readonly List<CardSelectionV1DeckCard> _deck = new();
        private readonly CardSelectionV1DeckCard[] _baseline;
        private CardSelectionV1Phase _phase = CardSelectionV1Phase.Selecting;
        private CardSelectionV1TaskState _taskState = CardSelectionV1TaskState.Incomplete;
        private object[] _taskResult = Array.Empty<object>();
        private bool _selectorTop = true;
        private bool _selectorClosed;
        private bool _previewOpen;
        private bool _effect;
        internal int CaptureCount { get; private set; }

        internal ChildAdapter(Fixture parent, CardSelectionV1ParentContext context, object screen, int keyLength)
        {
            _parent = parent; _context = context; _screen = screen;
            _previewDispatch = () => { };
            _confirmDispatch = Confirm;
            int count = context.ExpectedDomainCount;
            _models = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            _holders = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            _nodes = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            _keys = Enumerable.Range(0, count).Select(i => keyLength == 0
                ? "Card_" + i : new string((char)('A' + i % 26), keyLength)).ToArray();
            _selected = new bool[count];
            _select = new Action[count];
            for (int index = 0; index < count; index++)
            {
                int slot = index;
                _select[index] = () => Select(slot);
            }
            if (context.Operation == CardSelectionV1Operation.Add)
            {
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Base_A", 0));
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Base_B", 0));
            }
            else
            {
                for (int index = 0; index < count; index++)
                    _deck.Add(new CardSelectionV1DeckCard(_models[index], _keys[index], 0));
                _deck.Add(new CardSelectionV1DeckCard(new object(), "Other", 0));
            }
            _baseline = _deck.ToArray();
        }

        private void Select(int slot)
        {
            _parent.DispatchCount++;
            _selected[slot] = true;
            int count = _selected.Count(value => value);
            if (_context.CommitMode == CardSelectionV1CommitMode.AutoAtMax && count == _context.MaxSelect)
                Complete();
            else if (_context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm && count == _context.MaxSelect)
            {
                _phase = CardSelectionV1Phase.Preview; _selectorTop = false; _previewOpen = true;
            }
        }

        private void Complete()
        {
            int[] slots = Enumerable.Range(0, _selected.Length).Where(index => _selected[index]).ToArray();
            _taskState = CardSelectionV1TaskState.Succeeded;
            _taskResult = slots.Select(index => _models[index]).ToArray();
            _phase = CardSelectionV1Phase.Submitted; _selectorTop = false;
            _selectorClosed = true; _previewOpen = false; _effect = true;
            _deck.Clear();
            if (_context.Operation == CardSelectionV1Operation.Add)
            {
                _deck.Add(_baseline[0]);
                foreach (int slot in slots)
                    _deck.Add(new CardSelectionV1DeckCard(_models[slot], _keys[slot], 0));
                for (int index = 1; index < _baseline.Length; index++) _deck.Add(_baseline[index]);
            }
            else
            {
                foreach (CardSelectionV1DeckCard card in _baseline)
                {
                    bool selected = slots.Any(index => ReferenceEquals(_models[index], card.ModelIdentity));
                    _deck.Add(new CardSelectionV1DeckCard(card.ModelIdentity, card.StableKey,
                        card.UpgradeLevel + (selected ? 1 : 0)));
                }
            }
            _parent.EnterAfter();
        }

        private void Confirm()
        {
            _parent.DispatchCount++;
            Complete();
        }

        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            CaptureCount++;
            var candidates = new List<CardSelectionV1NativeCandidate>();
            for (int index = 0; index < _models.Length; index++)
                candidates.Add(new CardSelectionV1NativeCandidate(index, _keys[index],
                    _holders[index], _models[index], _nodes[index], 0,
                    true, true, _selected[index], true, _select[index]));
            object[] preview = _previewOpen
                ? Enumerable.Range(0, _selected.Length).Where(index => _selected[index]).Select(index => _models[index]).ToArray()
                : Array.Empty<object>();
            return new CardSelectionV1SurfaceCapture(
                CardSelectionV1SurfaceStatus.Available, _context.ParentReceiptIdentity,
                _context.RunIdentity, _context.PlayerIdentity, _context.RoomIdentity,
                _context.MapIdentity, _context.ParentOptionIdentity, _context.ParentControllerIdentity,
                _screen, _task, _previewOpen ? _preview : null, _context.ParentKind,
                _context.Operation, _context.MinSelect, _context.MaxSelect, _context.CommitMode,
                _phase, _selectorTop, _selectorClosed, _previewOpen, true, _models.Length,
                true, _taskState, _effect, _taskResult, preview, candidates, _deck,
                Array.Empty<CardSelectionV1Replacement>(),
                new CardSelectionV1NativeControl(_previewControl, true, true, _previewDispatch),
                new CardSelectionV1NativeControl(_confirmControl, true, true, _confirmDispatch));
        }

        public void Dispose() { }
    }
}
