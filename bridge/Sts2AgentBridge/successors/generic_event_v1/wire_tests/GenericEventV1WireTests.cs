using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV1;

internal static class GenericEventV1WireTests
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static readonly string ParentId = new('a', 64), ChildId = new('b', 64);
    private static int _checks;
    private static void Check(bool value, string label) { if (!value) throw new Exception(label); }
    private static void Case(string name, Action action)
    { try { action(); _checks++; } catch (Exception e) { throw new Exception(name, e); } }
    private static JsonElement Decode(byte[] b)
    { using var d = JsonDocument.Parse(b); var value = d.RootElement.Clone(); Array.Clear(b); return value; }
    private static JsonElement Read(GenericEventV1WireService s) => Decode(s.Handle("GET", GenericEventV1WireService.DecisionRoute, null));
    private static JsonElement Post(GenericEventV1WireService s, byte[] body) => Decode(s.Handle("POST", GenericEventV1WireService.ActionRoute, body));
    private static byte[] Request(string decision = "", string action = "choose:0", int ordinal = 0,
        string? parentDecision = null, string? parentAction = null) => GenericEventV1WireCodec.Request(
            decision == "" ? ParentId : decision, action, ordinal, parentDecision, parentAction);
    private static void Error(JsonElement value, string code) => Check(value.GetProperty("kind").GetString() == "error" &&
        value.GetProperty("payload").GetProperty("code").GetString() == code, "expected error " + code);
    private static void Child(FakeSession f, GenericEventV1WireService s)
    {
        Check(Read(s).GetProperty("kind").GetString() == "decision", "parent ready");
        Check(Post(s, Request()).GetProperty("payload").GetProperty("outcome").GetString() == "accepted", "accepted parent");
        f.HasChild = true;
    }
    private static int Main()
    {
        foreach (string stable in new[] { "UNRELATED_FOREST.OPT", "UNRELATED_LIBRARY.OPT", "HELD_OUT_991.NO_CATALOG" })
            Case("unregistered " + stable, () => {
                using var f = new FakeSession { Stable = stable }; using var s = new GenericEventV1WireService(Nonce, f);
                var p = Read(s).GetProperty("parent");
                Check(p.GetProperty("candidates")[0].GetProperty("stable_id").GetString() == stable, "stable identity preserved");
                Check(p.GetProperty("candidates")[0].GetProperty("discovery").GetString() == "deferred", "deferred discovery");
                Check(Post(s, Request()).GetProperty("kind").GetString() == "action" && f.ParentApplies == 1, "dispatch exactly once");
            });
        var malformed = new[] {
            "{}", "null", "[]", "{", "{\"decision_id\":\"" + ParentId + "\",\"action_id\":\"choose:0\",\"child\":null,\"operation\":\"upgrade\"}",
            "{\"decision_id\":\"" + ParentId + "\",\"decision_id\":\"" + ParentId + "\",\"action_id\":\"choose:0\",\"child\":null}",
            "{\"action_id\":\"choose:0\",\"decision_id\":\"" + ParentId + "\",\"child\":null}",
            "{\"decision_id\":\"" + ParentId + "\",\"action_id\":\"choose:0\",\"child\":null} ",
        };
        foreach (string input in malformed)
            Case("malformed request", () => {
                using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
                Read(s); Error(Post(s, Encoding.UTF8.GetBytes(input)), "invalid_request");
                Error(Post(s, Request()), "invalid_request"); Check(f.ParentApplies == 0, "no dispatch or retry");
            });
        Case("stale decision", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Read(s); Error(Post(s, Request(new string('f', 64))), "internal_failure");
            Check(f.ParentApplies == 0, "stale undispatched");
        });
        Case("uncertain no retry", () => {
            using var f = new FakeSession { Uncertain = true }; using var s = new GenericEventV1WireService(Nonce, f);
            Read(s); var r = Post(s, Request());
            Check(r.GetProperty("payload").GetProperty("outcome").GetString() == "uncertain", "uncertain receipt delivered");
            Error(Post(s, Request()), "unsupported"); Error(Read(s), "unsupported");
            Check(f.ParentApplies == 1, "uncertain one attempt");
        });
        Case("throw after mutation no retry", () => {
            using var f = new FakeSession { Throw = true }; using var s = new GenericEventV1WireService(Nonce, f);
            Read(s); Error(Post(s, Request()), "internal_failure"); Error(Read(s), "internal_failure");
            Check(f.ParentApplies == 1, "one side effect");
        });
        Case("delayed child admission", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Read(s); Post(s, Request());
            for (int i = 0; i < 3; i++) Check(Read(s).GetProperty("parent").GetProperty("status").GetString() == "waiting", "waiting");
            f.HasChild = true;
            Check(Read(s).GetProperty("payload").GetProperty("status").GetString() == "ready", "delayed child");
            Check(f.ParentApplies == 1, "one parent dispatch");
        });
        foreach (string mutation in new[] { "lineage", "ordinal", "operation", "count", "mode", "domain" })
            Case("bad descriptor " + mutation, () => {
                using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
                Child(f, s); f.Mutation = mutation; Error(Read(s), "internal_failure");
                Check(f.ChildReads == 0 && f.ChildApplies == 0, "descriptor rejected before child");
            });
        foreach (string mutation in new[] { "domain_changed", "key_changed" })
            Case("descriptor stable " + mutation, () => {
                using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
                Child(f, s); Read(s); f.Mutation = mutation; Error(Read(s), "internal_failure");
                Check(f.ChildApplies == 0, "tamper no child action");
            });
        Case("wrong action lineage", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Child(f, s); Read(s);
            Error(Post(s, Request(ChildId, "select:0", 1, new string('f', 64), "choose:0")), "invalid_request");
            Check(f.ChildApplies == 0, "wrong lineage no dispatch");
        });
        Case("client supplied descriptor", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Child(f, s); Read(s);
            string input = Encoding.UTF8.GetString(Request(ChildId, "select:0", 1, ParentId, "choose:0"));
            input = input[..^2] + ",\"domain_count\":3}}";
            Error(Post(s, Encoding.UTF8.GetBytes(input)), "invalid_request");
            Check(f.ChildApplies == 0, "client descriptor no dispatch");
        });
        Case("child receipt replay", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Child(f, s); Read(s); var request = Request(ChildId, "select:0", 1, ParentId, "choose:0");
            Check(Post(s, request).GetProperty("kind").GetString() == "action", "child accepted");
            Error(Post(s, request), "internal_failure"); Check(f.ChildApplies == 1, "one child dispatch");
        });
        Case("counter regression", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Read(s); Post(s, Request()); Read(s); f.Regress = true;
            Error(Read(s), "internal_failure");
        });
        Case("read budget", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Read(s); Post(s, Request());
            for (int i = 1; i < 2048; i++) Check(Read(s).GetProperty("kind").GetString() == "decision", "bounded read");
            Error(Read(s), "invalid_request"); Check(f.Reads == 2048, "no excess session read");
        });
        Case("route isolation", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Error(Decode(s.Handle("GET", "/probe/event-orchestrator-v1/public/decision", null)), "invalid_request");
            Check(f.Reads == 0, "old route isolated");
        });
        Case("cross-thread request", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            var response = Task.Run(() => Read(s)).GetAwaiter().GetResult();
            Error(response, "internal_failure");
            Check(f.Reads == 0 && f.ParentApplies == 0, "foreign thread never calls session");
            Error(Read(s), "internal_failure");
        });
        Case("reentrant read", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            f.OnRead = () => Error(Read(s), "internal_failure");
            Error(Read(s), "internal_failure"); Error(Read(s), "internal_failure");
            Check(f.Reads == 1 && f.ParentApplies == 0, "nested read suppressed");
        });
        Case("reentrant apply", () => {
            using var f = new FakeSession(); using var s = new GenericEventV1WireService(Nonce, f);
            Read(s); f.OnApply = () => Error(Post(s, Request()), "internal_failure");
            Error(Post(s, Request()), "internal_failure"); Error(Post(s, Request()), "internal_failure");
            Check(f.ParentApplies == 1, "reentrant mutation dispatched once");
        });
        Case("disposed handler", () => {
            var f = new FakeSession(); var s = new GenericEventV1WireService(Nonce, f);
            Read(s); s.Dispose();
            Error(Read(s), "unsupported"); Error(Post(s, Request()), "unsupported");
            s.Dispose(); Check(f.Reads == 1 && f.ParentApplies == 0 && f.Disposals == 1, "disposed owner untouched");
        });
        Case("cleanup failure preserves retry", () => {
            var f = new FakeSession { ThrowFirstDispose = true }; var s = new GenericEventV1WireService(Nonce, f);
            bool threw = false;
            try { s.Dispose(); } catch (InvalidOperationException) { threw = true; }
            Check(threw && f.Disposals == 1, "initial cleanup failure visible");
            Error(Read(s), "unsupported"); Check(f.Reads == 0, "failed cleanup stays terminal");
            s.Dispose(); s.Dispose(); Check(f.Disposals == 2, "cleanup retried and then idempotent");
        });
        Console.WriteLine(JsonSerializer.Serialize(new { schema_version = 1, status = "passed", suite = "generic_event_v1_wire", check_count = _checks }));
        return 0;
    }

    private sealed class FakeSession : IGenericEventV1Session
    {
        internal string Stable = "UNREGISTERED.OPTION", Mutation = "";
        internal bool HasChild, Uncertain, Throw, Regress, ThrowFirstDispose;
        internal Action? OnRead, OnApply;
        internal int Disposals;
        internal int ParentApplies, ChildApplies, ChildReads, Reads;
        public GenericEventV1Observation Read()
        {
            Reads++; OnRead?.Invoke();
            bool initial = ParentApplies == 0;
            int count = Regress ? 0 : ParentApplies;
            GenericEventV1Child? child = !HasChild ? null : new(
                Mutation == "ordinal" ? 2 : 1, Mutation == "lineage" ? new string('f', 64) : ParentId,
                "choose:0", Mutation == "operation" ? "remove" : "upgrade", 1,
                Mutation == "count" ? 2 : 1, Mutation == "mode" ? "auto_at_max" : "preview_confirm",
                Mutation == "domain" ? 1 : Mutation == "domain_changed" ? 4 : 3);
            return new(Nonce, initial ? "ready" : HasChild ? "child" : "waiting",
                initial ? "choose_option" : HasChild ? "child" : "waiting", initial ? ParentId : "",
                initial ? new[] { new GenericEventV1Candidate(0, "choose:0", Stable, "A presented option", true, false, false) } : Array.Empty<GenericEventV1Candidate>(),
                initial ? new[] { "choose:0" } : Array.Empty<string>(), child,
                Array.Empty<GenericEventV1PriorResult>(), count, count, 0, HasChild ? 1 : 0,
                ChildApplies, ChildApplies, 0, initial ? "none_attempted" : "unverified");
        }
        public GenericEventV1ApplyResult Apply(string? decisionId, string? actionId)
        {
            ParentApplies++; OnApply?.Invoke();
            if (Throw) throw new InvalidOperationException("After side effect");
            return new(Nonce, decisionId!, actionId!, Uncertain ? "uncertain" : "accepted");
        }
        public ICardSelectionV1ReadValue ReadChild(string? parentDecisionId, string? parentActionId, int childOrdinal)
        {
            ChildReads++;
            var candidates = Enumerable.Range(0, 3).Select(i => new CardSelectionV1Candidate(i,
                Mutation == "key_changed" ? "Changed_" + i : "Card_" + i, 0, true, true, false)).ToArray();
            return new CardSelectionV1Observation(Nonce, "ready", "selecting", "upgrade", "preview_confirm",
                1, 1, ChildId, candidates, Array.Empty<int>(), new[] { "select:0", "select:1", "select:2" }, Array.Empty<CardSelectionV1ActionResult>());
        }
        public ICardSelectionV1ApplyValue ApplyChild(string? parentDecisionId, string? parentActionId, int childOrdinal, string? decisionId, string? actionId)
        { ChildApplies++; return new CardSelectionV1DispatchReceipt(Nonce, decisionId!, actionId!); }
        public void Dispose()
        {
            Disposals++;
            if (ThrowFirstDispose && Disposals == 1) throw new InvalidOperationException("First cleanup failure.");
        }
    }
}
