using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;

internal static class Program
{
    private static int _checks;

    public static int Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "--fixture")
            return RunFixture(args[1]);
        try
        {
            CheeseEndToEnd();
            SmithEndToEnd();
            ExactRequestGrammar();
            RouteAndMethodFailClosed();
            CorrelationAndNoRetry();
            UncertainMutationNoRetry();
            OwnerReentryAndCleanup();
            ScalarShapesAndPrivacy();
            MaximumReadyBodyBound();
            ConservativeTenHistoryBodyBound();
            SemanticMutationGuards();
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"card_selection_v1_wire\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static int RunFixture(string scenario)
    {
        Fixture fixture = scenario switch
        {
            "cheese" => Fixture.Cheese(),
            "smith" => Fixture.Smith(3),
            "bounds" => Fixture.Smith(64, 128),
            _ => throw new InvalidOperationException("Unknown fixture scenario."),
        };
        try
        {
            using var service = fixture.Service();
            string? line;
            while ((line = Console.ReadLine()) is not null)
            {
                using JsonDocument document = JsonDocument.Parse(line);
                JsonElement root = document.RootElement;
                string[] names = root.EnumerateObject().Select(x => x.Name).ToArray();
                if (!names.SequenceEqual(new[] { "method", "route", "decision_id", "action_id" }))
                    throw new InvalidOperationException("Invalid fixture command.");
                string method = root.GetProperty("method").GetString()!;
                string route = root.GetProperty("route").GetString()!;
                string? decision = root.GetProperty("decision_id").ValueKind == JsonValueKind.Null
                    ? null : root.GetProperty("decision_id").GetString();
                string? action = root.GetProperty("action_id").ValueKind == JsonValueKind.Null
                    ? null : root.GetProperty("action_id").GetString();
                byte[]? body = method == "GET" ? null : ActionBody(decision!, action!);
                try
                {
                    CardSelectionV1WireResponse response = service.Handle(method, route, body);
                    byte[] output = response.Body;
                    try { Console.WriteLine(Encoding.UTF8.GetString(output)); }
                    finally { Array.Clear(output); }
                }
                finally
                {
                    if (body is not null) Array.Clear(body);
                }
            }
            Console.Error.WriteLine("{\"schema_version\":1,\"status\":\"fixture_complete\",\"capture_count\":" + fixture.CaptureCount + ",\"dispatch_count\":" + fixture.DispatchCount + "}");
            return 0;
        }
        catch
        {
            Console.Error.WriteLine("{\"schema_version\":1,\"status\":\"fixture_failed\"}");
            return 1;
        }
    }

    private static void CheeseEndToEnd()
    {
        var fixture = Fixture.Cheese();
        using var service = fixture.Service();
        JsonElement parent = Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "ready");
        string begin = Text(parent, "decision_id");
        Receipt(Post(service, CardSelectionV1WireProtocol.ParentActionRoute, begin, "begin"), "parent_receipt", begin, "begin");
        Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "waiting");
        JsonElement child = Get(service, CardSelectionV1WireProtocol.ChildRoute, "child_observation", "ready");
        Equal(8, child.GetProperty("candidates").GetArrayLength(), "cheese domain");
        Equal(2, child.GetProperty("min_select").GetInt32(), "cheese min");
        string first = Text(child, "decision_id");
        Receipt(Post(service, CardSelectionV1WireProtocol.ChildActionRoute, first, "select:0"), "child_receipt", first, "select:0");
        child = Get(service, CardSelectionV1WireProtocol.ChildRoute, "child_observation", "ready");
        Equal(1, child.GetProperty("selected_slots").GetArrayLength(), "one selected");
        False(child.GetProperty("legal_actions").EnumerateArray().Any(x => x.GetString() == "confirm"), "no early exact-two confirm");
        string second = Text(child, "decision_id");
        Receipt(Post(service, CardSelectionV1WireProtocol.ChildActionRoute, second, "select:1"), "child_receipt", second, "select:1");
        JsonElement resolvedChild = Get(service, CardSelectionV1WireProtocol.ChildRoute, "child_resolved", "resolved");
        Equal(2, resolvedChild.GetProperty("selected_cards").GetArrayLength(), "two resolved cards");
        Equal(2, resolvedChild.GetProperty("prior_results").GetArrayLength(), "two child results");
        parent = Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "ready");
        Equal("after", Text(parent, "phase"), "parent after");
        string proceed = Text(parent, "decision_id");
        Receipt(Post(service, CardSelectionV1WireProtocol.ParentActionRoute, proceed, "proceed"), "parent_receipt", proceed, "proceed");
        JsonElement done = Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_resolved", "resolved");
        Equal(begin, Text(done, "begin_decision_id"), "begin correlation");
        Equal(proceed, Text(done, "proceed_decision_id"), "proceed correlation");
        Equal(4, fixture.DispatchCount, "four exact dispatches");
        Pass();
    }

    private static void SmithEndToEnd()
    {
        var fixture = Fixture.Smith(3);
        using var service = fixture.Service();
        JsonElement parent = Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "ready");
        Receipt(Post(service, CardSelectionV1WireProtocol.ParentActionRoute,
            Text(parent, "decision_id"), "begin"), "parent_receipt", Text(parent, "decision_id"), "begin");
        Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "waiting");
        JsonElement child = Get(service, CardSelectionV1WireProtocol.ChildRoute, "child_observation", "ready");
        string select = Text(child, "decision_id");
        Receipt(Post(service, CardSelectionV1WireProtocol.ChildActionRoute, select, "select:0"), "child_receipt", select, "select:0");
        child = Get(service, CardSelectionV1WireProtocol.ChildRoute, "child_observation", "ready");
        Equal("preview", Text(child, "phase"), "smith preview");
        True(child.GetProperty("legal_actions").EnumerateArray().Select(x => x.GetString()).SequenceEqual(new[] { "confirm" }), "smith confirm only");
        string confirm = Text(child, "decision_id");
        Receipt(Post(service, CardSelectionV1WireProtocol.ChildActionRoute, confirm, "confirm"), "child_receipt", confirm, "confirm");
        Get(service, CardSelectionV1WireProtocol.ChildRoute, "child_resolved", "resolved");
        parent = Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "ready");
        string proceed = Text(parent, "decision_id");
        Receipt(Post(service, CardSelectionV1WireProtocol.ParentActionRoute, proceed, "proceed"), "parent_receipt", proceed, "proceed");
        Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_resolved", "resolved");
        Equal(4, fixture.DispatchCount, "smith exact dispatches");
        Pass();
    }

    private static void ExactRequestGrammar()
    {
        foreach (byte[] bad in new[] {
            Encoding.UTF8.GetBytes(" {\"decision_id\":\"" + Hex('a') + "\",\"action_id\":\"begin\"}"),
            Encoding.UTF8.GetBytes("{\"action_id\":\"begin\",\"decision_id\":\"" + Hex('a') + "\"}"),
            Encoding.UTF8.GetBytes("{\"decision_id\":\"" + Hex('a') + "\",\"action_id\":\"begin\",\"x\":0}"),
            Encoding.UTF8.GetBytes("{\"decision_id\":\"" + Hex('a') + "\",\"decision_id\":\"" + Hex('a') + "\",\"action_id\":\"begin\"}"),
            Encoding.UTF8.GetBytes("{\"decision_id\":\"" + Hex('A') + "\",\"action_id\":\"begin\"}"),
            Encoding.UTF8.GetBytes("{\"decision_id\":\"" + Hex('a') + "\",\"action_id\":\"select:00\"}"),
            new byte[257] })
        {
            var fixture = Fixture.Cheese();
            using var service = fixture.Service();
            CardSelectionV1WireResponse response = service.Handle("POST", CardSelectionV1WireProtocol.ParentActionRoute, bad);
            Error(response, 400, "invalid_request");
            Error(service.Handle("GET", CardSelectionV1WireProtocol.ParentRoute, null), 500, "internal_failure");
            Equal(0, fixture.CaptureCount, "invalid request before core");
        }
        Pass();
    }

    private static void RouteAndMethodFailClosed()
    {
        foreach ((string method, string route, byte[]? body) in new[] {
            ("get", CardSelectionV1WireProtocol.ParentRoute, (byte[]?)null),
            ("GET", "/card-selection-v1/Parent", (byte[]?)null),
            ("GET", CardSelectionV1WireProtocol.ParentRoute, new byte[] { 0 }),
            ("POST", CardSelectionV1WireProtocol.ChildRoute, ActionBody(Hex('a'), "select:0")) })
        {
            var fixture = Fixture.Cheese();
            using var service = fixture.Service();
            Error(service.Handle(method, route, body), 400, "invalid_request");
            Equal(0, fixture.CaptureCount, "route rejection before core");
        }
        Pass();
    }

    private static void CorrelationAndNoRetry()
    {
        var fixture = Fixture.Cheese();
        using var service = fixture.Service();
        JsonElement parent = Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "ready");
        string decision = Text(parent, "decision_id");
        Error(Post(service, CardSelectionV1WireProtocol.ParentActionRoute, Hex('f'), "begin"), 400, "invalid_request");
        Error(Post(service, CardSelectionV1WireProtocol.ParentActionRoute, decision, "begin"), 500, "internal_failure");
        Equal(0, fixture.DispatchCount, "wrong correlation prevents retry");
        Pass();
    }

    private static void UncertainMutationNoRetry()
    {
        var fixture = Fixture.Cheese();
        fixture.ThrowBegin = true;
        using var service = fixture.Service();
        JsonElement parent = Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "ready");
        string decision = Text(parent, "decision_id");
        JsonElement failure = Element(Post(service, CardSelectionV1WireProtocol.ParentActionRoute, decision, "begin"), 200);
        Equal("parent_failure", Text(failure, "kind"), "uncertain kind");
        Equal("uncertain", Text(failure, "outcome"), "uncertain outcome");
        Error(Post(service, CardSelectionV1WireProtocol.ParentActionRoute, decision, "begin"), 500, "internal_failure");
        Equal(1, fixture.DispatchCount, "uncertain dispatch once");
        Pass();
    }

    private static void OwnerReentryAndCleanup()
    {
        var offOwner = Fixture.Cheese();
        using (var service = offOwner.Service())
        {
            CardSelectionV1WireResponse? response = null;
            var thread = new Thread(() => response = service.Handle("GET", CardSelectionV1WireProtocol.ParentRoute, null));
            thread.Start(); thread.Join();
            Error(response!, 500, "internal_failure");
            Equal(0, offOwner.CaptureCount, "off-owner before core");
        }

        var reentrant = Fixture.Cheese();
        using (var service = reentrant.Service())
        {
            reentrant.CaptureCallback = () => service.Handle("GET", CardSelectionV1WireProtocol.ParentRoute, null);
            Error(service.Handle("GET", CardSelectionV1WireProtocol.ParentRoute, null), 500, "internal_failure");
            Equal(1, reentrant.CaptureCount, "reentry does not recapture");
        }

        var disposed = Fixture.Cheese();
        var disposedService = disposed.Service();
        disposedService.Dispose();
        Error(disposedService.Handle("GET", CardSelectionV1WireProtocol.ParentRoute, null), 500, "internal_failure");
        Equal(1, disposed.DisposeCount, "owned cleanup once");
        Pass();
    }

    private static void ScalarShapesAndPrivacy()
    {
        var fixture = Fixture.Cheese();
        using var service = fixture.Service();
        CardSelectionV1WireResponse response = service.Handle("GET", CardSelectionV1WireProtocol.ParentRoute, null);
        byte[] body = response.Body;
        string text = Encoding.UTF8.GetString(body);
        False(text.EndsWith('\n'), "no newline");
        False(text.Contains("System.Object", StringComparison.Ordinal), "no opaque type");
        using JsonDocument document = JsonDocument.Parse(body);
        string[] names = document.RootElement.EnumerateObject().Select(x => x.Name).ToArray();
        True(names.SequenceEqual(new[] { "schema_version", "kind", "version", "session_nonce", "parent_ordinal", "status", "phase", "parent_kind", "policy", "decision_id", "legal_actions" }), "parent property order");
        Array.Clear(body);
        Pass();
    }

    private static void MaximumReadyBodyBound()
    {
        var fixture = Fixture.Smith(64, keyLength: 128);
        using var service = fixture.Service();
        JsonElement parent = Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "ready");
        Receipt(Post(service, CardSelectionV1WireProtocol.ParentActionRoute,
            Text(parent, "decision_id"), "begin"), "parent_receipt", Text(parent, "decision_id"), "begin");
        Get(service, CardSelectionV1WireProtocol.ParentRoute, "parent_observation", "waiting");
        CardSelectionV1WireResponse response = service.Handle("GET", CardSelectionV1WireProtocol.ChildRoute, null);
        Equal(200, response.StatusCode, "maximum status");
        byte[] body = response.Body;
        True(body.Length < CardSelectionV1WireProtocol.MaximumResponseBytes, "maximum response bound");
        using JsonDocument document = JsonDocument.Parse(body);
        Equal(64, document.RootElement.GetProperty("candidates").GetArrayLength(), "maximum candidates");
        Array.Clear(body);
        Pass();
    }

    private static void ConservativeTenHistoryBodyBound()
    {
        var candidates = new List<CardSelectionV1Candidate>();
        for (int slot = 0; slot < 64; slot++)
            candidates.Add(Construct<CardSelectionV1Candidate>(
                slot, new string((char)('A' + slot % 26), 128), int.MaxValue,
                true, true, slot < 8));
        var history = new List<CardSelectionV1ActionResult>();
        for (int index = 0; index < 8; index++)
            history.Add(Construct<CardSelectionV1ActionResult>(
                new string((char)('a' + index % 6), 64), "select:" + index, "selected"));
        history.Add(Construct<CardSelectionV1ActionResult>(Hex('c'), "preview", "previewed"));
        history.Add(Construct<CardSelectionV1ActionResult>(Hex('d'), "confirm", "committed"));
        CardSelectionV1Observation observation = Construct<CardSelectionV1Observation>(
            Hex('1', 32), "ready", "preview", "transform", "preview_confirm",
            1, 8, Hex('e'), candidates, Enumerable.Range(0, 8).ToArray(),
            new[] { "confirm" }, history, null!);
        Type codec = typeof(CardSelectionV1WireProtocol).Assembly.GetType(
            "Sts2AgentBridge.Successors.CardSelectionV1.Wire.CardSelectionV1WireCodec", true)!;
        MethodInfo encode = codec.GetMethod("Encode", BindingFlags.Static | BindingFlags.Public)!
            ?? throw new InvalidOperationException("Missing codec.");
        byte[] encoded = (byte[])encode.Invoke(null, new object[] { observation })!;
        try
        {
            True(encoded.Length < CardSelectionV1WireProtocol.MaximumResponseBytes,
                "64-key ten-history conservative response bound");
            using JsonDocument document = JsonDocument.Parse(encoded);
            Equal(64, document.RootElement.GetProperty("candidates").GetArrayLength(), "bound candidates");
            Equal(10, document.RootElement.GetProperty("prior_results").GetArrayLength(), "bound history");
        }
        finally { Array.Clear(encoded); }
        Pass();
    }

    private static void SemanticMutationGuards()
    {
        var smith = Fixture.Smith(3);
        using (var service = smith.Service())
        {
            JsonElement parent = Get(service, CardSelectionV1WireProtocol.ParentRoute,
                "parent_observation", "ready");
            Receipt(Post(service, CardSelectionV1WireProtocol.ParentActionRoute,
                Text(parent, "decision_id"), "begin"), "parent_receipt",
                Text(parent, "decision_id"), "begin");
            Get(service, CardSelectionV1WireProtocol.ParentRoute,
                "parent_observation", "waiting");
            JsonElement child = Get(service, CardSelectionV1WireProtocol.ChildRoute,
                "child_observation", "ready");
            string select = Text(child, "decision_id");
            Receipt(Post(service, CardSelectionV1WireProtocol.ChildActionRoute,
                select, "select:0"), "child_receipt", select, "select:0");
            CardSelectionParentV1Session session = InnerSession(service);
            CardSelectionV1Observation preview = (CardSelectionV1Observation)session.ReadChild();
            var onlySelected = preview.Candidates.Where(item => item.Selected).ToArray();
            CardSelectionV1ResolvedResult missingConfirm = Construct<CardSelectionV1ResolvedResult>(
                Hex('1', 32), "upgrade", onlySelected, preview.PriorResults, null!);
            InvokeValidationReject(service, "ValidateChildRead", missingConfirm,
                "smith resolved without confirm");
        }

        var order = Fixture.Cheese();
        using (var service = order.Service())
        {
            AdmitChild(service);
            Get(service, CardSelectionV1WireProtocol.ChildRoute,
                "child_observation", "ready");
            CardSelectionV1Observation original = (CardSelectionV1Observation)InnerSession(service).ReadChild();
            CardSelectionV1Observation reversed = CloneObservation(original,
                original.DecisionId, original.Candidates.Reverse().ToArray());
            InvokeValidationReject(service, "ValidateChildRead", reversed,
                "candidate order mutation");
        }

        var reused = Fixture.Cheese();
        using (var service = reused.Service())
        {
            AdmitChild(service);
            JsonElement initial = Get(service, CardSelectionV1WireProtocol.ChildRoute,
                "child_observation", "ready");
            string used = Text(initial, "decision_id");
            Receipt(Post(service, CardSelectionV1WireProtocol.ChildActionRoute,
                used, "select:0"), "child_receipt", used, "select:0");
            CardSelectionV1Observation next = (CardSelectionV1Observation)InnerSession(service).ReadChild();
            CardSelectionV1Observation repeated = CloneObservation(next, used,
                next.Candidates.ToArray());
            InvokeValidationReject(service, "ValidateChildRead", repeated,
                "reused child decision");
            Equal(2, reused.DispatchCount, "reused decision no second child dispatch");
        }
        Pass();
    }

    private static void AdmitChild(CardSelectionV1WireService service)
    {
        JsonElement parent = Get(service, CardSelectionV1WireProtocol.ParentRoute,
            "parent_observation", "ready");
        Receipt(Post(service, CardSelectionV1WireProtocol.ParentActionRoute,
            Text(parent, "decision_id"), "begin"), "parent_receipt",
            Text(parent, "decision_id"), "begin");
        Get(service, CardSelectionV1WireProtocol.ParentRoute,
            "parent_observation", "waiting");
    }

    private static CardSelectionParentV1Session InnerSession(CardSelectionV1WireService service) =>
        (CardSelectionParentV1Session)typeof(CardSelectionV1WireService).GetField(
            "_session", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(service)!;

    private static CardSelectionV1Observation CloneObservation(
        CardSelectionV1Observation value,
        string decision,
        IReadOnlyList<CardSelectionV1Candidate> candidates) =>
        Construct<CardSelectionV1Observation>(value.SessionNonce, value.Status, value.Phase,
            value.Operation, value.CommitMode, value.MinSelect, value.MaxSelect, decision,
            candidates, value.SelectedSlots, value.LegalActions, value.PriorResults, null!);

    private static void InvokeValidationReject(
        CardSelectionV1WireService service, string method, object value, string message)
    {
        try
        {
            typeof(CardSelectionV1WireService).GetMethod(
                method, BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(
                    service, new[] { value });
        }
        catch (TargetInvocationException error) when (error.InnerException is InvalidOperationException)
        {
            return;
        }
        throw new InvalidOperationException(message);
    }

    private static T Construct<T>(params object[] arguments) where T : class
    {
        ConstructorInfo constructor = typeof(T).GetConstructors(
            BindingFlags.Instance | BindingFlags.NonPublic).Single();
        return (T)constructor.Invoke(arguments);
    }

    private static JsonElement Get(CardSelectionV1WireService service, string route, string kind, string status)
    {
        JsonElement value = Element(service.Handle("GET", route, null), 200);
        Equal(kind, Text(value, "kind"), route + " kind");
        Equal(status, Text(value, "status"), route + " status");
        return value;
    }

    private static CardSelectionV1WireResponse Post(CardSelectionV1WireService service, string route, string decision, string action) =>
        service.Handle("POST", route, ActionBody(decision, action));

    private static byte[] ActionBody(string decision, string action) =>
        Encoding.UTF8.GetBytes("{\"decision_id\":\"" + decision + "\",\"action_id\":\"" + action + "\"}");

    private static void Receipt(CardSelectionV1WireResponse response, string kind, string decision, string action)
    {
        JsonElement value = Element(response, 200);
        Equal(kind, Text(value, "kind"), "receipt kind");
        Equal(decision, Text(value, "decision_id"), "receipt decision");
        Equal(action, Text(value, "action_id"), "receipt action");
        Equal("accepted", Text(value, "outcome"), "receipt outcome");
    }

    private static void Error(CardSelectionV1WireResponse response, int status, string code)
    {
        JsonElement value = Element(response, status);
        Equal("error", Text(value, "kind"), "error kind");
        Equal(code, Text(value, "code"), "error code");
    }

    private static JsonElement Element(CardSelectionV1WireResponse response, int status)
    {
        Equal(status, response.StatusCode, "status code");
        byte[] body = response.Body;
        using JsonDocument document = JsonDocument.Parse(body);
        JsonElement clone = document.RootElement.Clone();
        Array.Clear(body);
        return clone;
    }

    private static string Text(JsonElement value, string property) => value.GetProperty(property).GetString()!;
    private static string Hex(char c, int length = 64) => new(c, length);
    private static void Pass() => _checks++;
    private static void True(bool value, string message) { if (!value) throw new InvalidOperationException(message); }
    private static void False(bool value, string message) => True(!value, message);
    private static void Equal<T>(T expected, T actual, string message) where T : notnull
    { if (!EqualityComparer<T>.Default.Equals(expected, actual)) throw new InvalidOperationException(message + ": expected=" + expected + ", actual=" + actual); }

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

        internal CardSelectionV1WireService Service() => new(Hex('1', 32), new CardSelectionParentV1Session(Hex('1', 32), this));
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
        internal ChildFactory(Fixture parent, int keyLength) { _parent = parent; _keyLength = keyLength; }
        public ICardSelectionV1NativeAdapter Create(CardSelectionV1ParentContext context, object exactScreenIdentity) =>
            new ChildAdapter(_parent, context, exactScreenIdentity, _keyLength);
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
