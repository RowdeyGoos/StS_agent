using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.GenericEventV6;

internal static class GenericEventV6WireTests
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static readonly string ParentId = new('a', 64), ChildId = new('b', 64);
    private static int _checks;
    private static void Check(bool value, string label) { if (!value) throw new Exception(label); }
    private static void Case(string name, Action action)
    { try { action(); _checks++; } catch (Exception e) { throw new Exception(name, e); } }
    private static JsonElement Decode(byte[] b)
    { using var d = JsonDocument.Parse(b); var value = d.RootElement.Clone(); Array.Clear(b); return value; }
    private static JsonElement Read(GenericEventV6WireService s) => Decode(s.Handle("GET", GenericEventV6WireService.DecisionRoute, null));
    private static JsonElement Post(GenericEventV6WireService s, byte[] body) => Decode(s.Handle("POST", GenericEventV6WireService.ActionRoute, body));
    private static byte[] Request(string decision = "", string action = "choose:0", int ordinal = 0,
        string? parentDecision = null, string? parentAction = null) => GenericEventV6WireCodec.Request(
            decision == "" ? ParentId : decision, action, ordinal, parentDecision, parentAction);
    private static void Error(JsonElement value, string code) => Check(value.GetProperty("kind").GetString() == "error" &&
        value.GetProperty("payload").GetProperty("code").GetString() == code, "expected error " + code);
    private static void Child(FakeSession f, GenericEventV6WireService s)
    {
        Check(Read(s).GetProperty("kind").GetString() == "decision", "parent ready");
        Check(Post(s, Request()).GetProperty("payload").GetProperty("outcome").GetString() == "accepted", "accepted parent");
        f.HasChild = true;
    }
    private static int Main()
    {
        foreach (string stable in new[] { "UNRELATED_FOREST.OPT", "UNRELATED_LIBRARY.OPT", "HELD_OUT_991.NO_CATALOG" })
            Case("unregistered " + stable, () => {
                using var f = new FakeSession { Stable = stable }; using var s = new GenericEventV6WireService(Nonce, f);
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
                using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
                Read(s); Error(Post(s, Encoding.UTF8.GetBytes(input)), "invalid_request");
                Error(Post(s, Request()), "invalid_request"); Check(f.ParentApplies == 0, "no dispatch or retry");
            });
        Case("stale decision", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Read(s); Error(Post(s, Request(new string('f', 64))), "internal_failure");
            Check(f.ParentApplies == 0, "stale undispatched");
        });
        Case("uncertain no retry", () => {
            using var f = new FakeSession { Uncertain = true }; using var s = new GenericEventV6WireService(Nonce, f);
            Read(s); var r = Post(s, Request());
            Check(r.GetProperty("payload").GetProperty("outcome").GetString() == "uncertain", "uncertain receipt delivered");
            Error(Post(s, Request()), "unsupported"); Error(Read(s), "unsupported");
            Check(f.ParentApplies == 1, "uncertain one attempt");
        });
        Case("throw after mutation no retry", () => {
            using var f = new FakeSession { Throw = true }; using var s = new GenericEventV6WireService(Nonce, f);
            Read(s); Error(Post(s, Request()), "internal_failure"); Error(Read(s), "internal_failure");
            Check(f.ParentApplies == 1, "one side effect");
        });
        Case("delayed child admission", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Read(s); Post(s, Request());
            for (int i = 0; i < 3; i++) Check(Read(s).GetProperty("parent").GetProperty("status").GetString() == "waiting", "waiting");
            f.HasChild = true;
            Check(Read(s).GetProperty("payload").GetProperty("status").GetString() == "ready", "delayed child");
            Check(f.ParentApplies == 1, "one parent dispatch");
        });
        foreach (string mutation in new[] { "lineage", "ordinal", "operation", "count", "mode", "domain" })
            Case("bad descriptor " + mutation, () => {
                using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
                Child(f, s); f.Mutation = mutation; Error(Read(s), "internal_failure");
                Check(f.ChildReads == 0 && f.ChildApplies == 0, "descriptor rejected before child");
            });
        foreach (string mutation in new[] { "domain_changed", "key_changed" })
            Case("descriptor stable " + mutation, () => {
                using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
                Child(f, s); Read(s); f.Mutation = mutation; Error(Read(s), "internal_failure");
                Check(f.ChildApplies == 0, "tamper no child action");
            });
        Case("wrong action lineage", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Child(f, s); Read(s);
            Error(Post(s, Request(ChildId, "select:0", 1, new string('f', 64), "choose:0")), "invalid_request");
            Check(f.ChildApplies == 0, "wrong lineage no dispatch");
        });
        Case("client supplied descriptor", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Child(f, s); Read(s);
            string input = Encoding.UTF8.GetString(Request(ChildId, "select:0", 1, ParentId, "choose:0"));
            input = input[..^2] + ",\"domain_count\":3}}";
            Error(Post(s, Encoding.UTF8.GetBytes(input)), "invalid_request");
            Check(f.ChildApplies == 0, "client descriptor no dispatch");
        });
        Case("child receipt replay", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Child(f, s); Read(s); var request = Request(ChildId, "select:0", 1, ParentId, "choose:0");
            Check(Post(s, request).GetProperty("kind").GetString() == "action", "child accepted");
            Error(Post(s, request), "internal_failure"); Check(f.ChildApplies == 1, "one child dispatch");
        });
        Case("counter regression", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Read(s); Post(s, Request()); Read(s); f.Regress = true;
            Error(Read(s), "internal_failure");
        });
        Case("read budget", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Read(s); Post(s, Request());
            for (int i = 1; i < 2048; i++) Check(Read(s).GetProperty("kind").GetString() == "decision", "bounded read");
            Error(Read(s), "invalid_request"); Check(f.Reads == 2048, "no excess session read");
        });
        Case("route isolation", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Error(Decode(s.Handle("GET", "/probe/event-orchestrator-v1/public/decision", null)), "invalid_request");
            Check(f.Reads == 0, "old route isolated");
        });
        Case("cross-thread request", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            var response = Task.Run(() => Read(s)).GetAwaiter().GetResult();
            Error(response, "internal_failure");
            Check(f.Reads == 0 && f.ParentApplies == 0, "foreign thread never calls session");
            Error(Read(s), "internal_failure");
        });
        Case("reentrant read", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            f.OnRead = () => Error(Read(s), "internal_failure");
            Error(Read(s), "internal_failure"); Error(Read(s), "internal_failure");
            Check(f.Reads == 1 && f.ParentApplies == 0, "nested read suppressed");
        });
        Case("reentrant apply", () => {
            using var f = new FakeSession(); using var s = new GenericEventV6WireService(Nonce, f);
            Read(s); f.OnApply = () => Error(Post(s, Request()), "internal_failure");
            Error(Post(s, Request()), "internal_failure"); Error(Post(s, Request()), "internal_failure");
            Check(f.ParentApplies == 1, "reentrant mutation dispatched once");
        });
        Case("disposed handler", () => {
            var f = new FakeSession(); var s = new GenericEventV6WireService(Nonce, f);
            Read(s); s.Dispose();
            Error(Read(s), "unsupported"); Error(Post(s, Request()), "unsupported");
            s.Dispose(); Check(f.Reads == 1 && f.ParentApplies == 0 && f.Disposals == 1, "disposed owner untouched");
        });
        Case("cleanup failure preserves retry", () => {
            var f = new FakeSession { ThrowFirstDispose = true }; var s = new GenericEventV6WireService(Nonce, f);
            bool threw = false;
            try { s.Dispose(); } catch (InvalidOperationException) { threw = true; }
            Check(threw && f.Disposals == 1, "initial cleanup failure visible");
            Error(Read(s), "unsupported"); Check(f.Reads == 0, "failed cleanup stays terminal");
            s.Dispose(); s.Dispose(); Check(f.Disposals == 2, "cleanup retried and then idempotent");
        });
        foreach (var config in new[] {
            (Min: 2, Max: 2, Domain: 5, Actions: new[] { "select:3", "select:1", "confirm" }),
            (Min: 1, Max: 3, Domain: 5, Actions: new[] { "select:3", "preview", "confirm" }),
            (Min: 1, Max: 3, Domain: 5, Actions: new[] { "select:3", "select:1", "preview", "confirm" }),
            (Min: 1, Max: 3, Domain: 5, Actions: new[] { "select:3", "select:1", "select:0", "confirm" }),
            (Min: 8, Max: 8, Domain: 9, Actions: Enumerable.Range(0, 8).Reverse().Select(i => "select:" + i).Append("confirm").ToArray()),
        })
            Case("removal selection set and variable preview", () => {
                using var f = new FakeSession { Family = "remove", Min = config.Min, Max = config.Max, Domain = config.Domain };
                using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
                foreach (string action in config.Actions) Play(s, action);
                var done = Read(s).GetProperty("payload");
                Check(done.GetProperty("kind").GetString() == "child_resolved", "removal resolved");
                var slots = done.GetProperty("selected_cards").EnumerateArray().Select(c => c.GetProperty("slot").GetInt32()).ToArray();
                Check(slots.Order().SequenceEqual(config.Actions.Where(a => a.StartsWith("select:", StringComparison.Ordinal)).Select(a => int.Parse(a[7..])).Order()), "slot membership independent of receipt order");
                Check(f.ChildApplies == config.Actions.Length, "native action count");
            });
        foreach (var config in new[] {
            (Family: "remove", Min: 0, Max: 1, Domain: 3),
            (Family: "remove", Min: -1, Max: 1, Domain: 3),
            (Family: "remove", Min: 3, Max: 2, Domain: 5),
            (Family: "remove", Min: 1, Max: 9, Domain: 10),
            (Family: "remove", Min: 2, Max: 2, Domain: 2),
            (Family: "remove", Min: 1, Max: 2, Domain: 1),
            (Family: "remove", Min: 1, Max: 2, Domain: 65),
            (Family: "upgrade", Min: 1, Max: 2, Domain: 3),
            (Family: "add", Min: 1, Max: 1, Domain: 3),
            (Family: "transform", Min: 1, Max: 2, Domain: 3),
        })
            Case("unsupported family descriptor", () => {
                using var f = new FakeSession { Family = config.Family, Min = config.Min, Max = config.Max, Domain = config.Domain };
                using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
                Error(Read(s), "internal_failure"); Check(f.ChildReads == 0, "invalid descriptor before child read");
            });
        foreach (string mutation in new[] { "payload_family", "payload_min", "payload_max" })
            Case("payload descriptor disagreement", () => {
                using var f = new FakeSession { Family = "remove", Min = 1, Max = 3, Domain = 5, Mutation = mutation };
                using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
                Error(Read(s), "internal_failure"); Check(f.ChildApplies == 0, "disagreement not actionable");
            });
        foreach (string mutation in new[] { "resolved_duplicate", "resolved_wrong_slot", "resolved_family" })
            Case("resolved exact removal membership", () => {
                using var f = new FakeSession { Family = "remove", Min = 2, Max = 2, Domain = 5 };
                using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
                Play(s, "select:3"); Play(s, "select:1"); Play(s, "confirm");
                f.Mutation = mutation; Error(Read(s), "internal_failure");
                Check(f.ChildApplies == 3, "no retry on wrong resolved membership");
            });
        Case("admitted removal counts cannot change", () => {
            using var f = new FakeSession { Family = "remove", Min = 1, Max = 3, Domain = 5 };
            using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
            Read(s); f.Max = 4; Error(Read(s), "internal_failure");
            Check(f.ChildApplies == 0, "valid but changed descriptor rejected");
        });
        foreach (string mutation in new[] { "selected_mismatch", "selection_lost", "hidden_history", "preview_below_min" })
            Case("ready selection and history exactness", () => {
                using var f = new FakeSession { Family = "remove", Min = 2, Max = 3, Domain = 5 };
                using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
                Play(s, "select:3"); f.Mutation = mutation;
                Error(Read(s), "internal_failure"); Check(f.ChildApplies == 1, "bad ready never actionable");
            });
        Case("confirmation requires witnessed preview", () => {
            using var f = new FakeSession { Family = "remove", Min = 2, Max = 2, Domain = 5 };
            using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
            Play(s, "select:3"); Play(s, "select:1"); f.Mutation = "missing_preview";
            Error(Read(s), "internal_failure"); Check(f.ChildApplies == 2, "unwitnessed confirmation never dispatched");
        });
        Case("preview cannot reopen selection", () => {
            using var f = new FakeSession { Family = "remove", Min = 1, Max = 3, Domain = 5 };
            using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
            Play(s, "select:3"); Play(s, "preview"); Read(s); f.Mutation = "reopen_selecting";
            Error(Read(s), "internal_failure"); Check(f.ChildApplies == 2, "reopened selection terminal");
        });
        Case("uncertain child no retry", () => {
            using var f = new FakeSession { Family = "remove", Min = 2, Max = 2, Domain = 5, UncertainChild = true };
            using var s = new GenericEventV6WireService(Nonce, f); Child(f, s); Read(s);
            var receipt = Post(s, Request(ChildId, "select:3", 1, ParentId, "choose:0"));
            Check(receipt.GetProperty("payload").GetProperty("outcome").GetString() == "uncertain", "uncertain child preserved");
            Error(Post(s, Request(ChildId, "select:3", 1, ParentId, "choose:0")), "unsupported");
            Check(f.ChildApplies == 1, "uncertain child side effect exactly once");
        });
        foreach (string mutation in new[] { "preview_below_count", "selected_legal", "flags_mismatch" })
            Case("child advertisements cannot authorize invalid mutation", () => {
                using var f = new FakeSession { Family = "remove", Min = 2, Max = 3, Domain = 5 };
                using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
                Play(s, "select:3"); f.Mutation = mutation; Error(Read(s), "internal_failure");
                Check(f.ChildApplies == 1, "invalid advertisement stopped before second mutation");
            });
        foreach (string mutation in new[] { "duplicate_legal", "hidden_candidate" })
            Case("initial child legal list validation", () => {
                using var f = new FakeSession { Family = "remove", Min = 2, Max = 3, Domain = 5, Mutation = mutation };
                using var s = new GenericEventV6WireService(Nonce, f); Child(f, s);
                Error(Read(s), "internal_failure"); Check(f.ChildApplies == 0, "malformed initial legal list no dispatch");
            });
        foreach (string stable in new[] { "OPTION\u0000", "OPTION\n", "OPTION_é" })
            Case("parent stable key is printable ASCII", () => {
                using var f = new FakeSession { Stable = stable }; using var s = new GenericEventV6WireService(Nonce, f);
                Error(Read(s), "internal_failure"); Check(f.ParentApplies == 0, "bad key no parent dispatch");
            });
        foreach (string rendered in new[] { "Visible\u0000text", string.Concat(Enumerable.Repeat("🙂", 300)) })
            Case("parent text controls and UTF8 byte ceiling", () => {
                using var f = new FakeSession { Rendered = rendered }; using var s = new GenericEventV6WireService(Nonce, f);
                Error(Read(s), "internal_failure"); Check(f.ParentApplies == 0, "bad text no parent dispatch");
            });
        foreach (var config in new[] {
            (Mode: "auto_at_max", Min: 2, Max: 2, Domain: 5, Actions: new[] { "select:3", "select:1" }),
            (Mode: "auto_at_max", Min: 1, Max: 3, Domain: 5, Actions: new[] { "select:3", "select:1", "select:0" }),
            (Mode: "explicit_confirm", Min: 2, Max: 2, Domain: 5, Actions: new[] { "select:3", "select:1", "confirm" }),
            (Mode: "explicit_confirm", Min: 1, Max: 3, Domain: 5, Actions: new[] { "select:3", "confirm" }),
            (Mode: "explicit_confirm", Min: 1, Max: 3, Domain: 5, Actions: new[] { "select:3", "select:1", "select:0", "confirm" }),
            (Mode: "auto_at_max", Min: 8, Max: 8, Domain: 9, Actions: Enumerable.Range(1, 8).Reverse().Select(i => "select:" + i).ToArray()),
            (Mode: "explicit_confirm", Min: 8, Max: 8, Domain: 9, Actions: Enumerable.Range(1, 8).Reverse().Select(i => "select:" + i).Append("confirm").ToArray()),
        })
            Case("reward terminal mode and selected history", () => {
                using var f = new FakeSession { Family = "add", Mode = config.Mode, Min = config.Min, Max = config.Max, Domain = config.Domain };
                using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
                foreach (string action in config.Actions) Play(service, action);
                var result = Read(service).GetProperty("payload");
                Check(result.GetProperty("kind").GetString() == "child_resolved", "reward resolved without preview");
                var history = result.GetProperty("prior_results").EnumerateArray().ToArray();
                Check(history.Length == config.Actions.Length && history[^1].GetProperty("result").GetString() == (config.Mode == "auto_at_max" ? "selected" : "committed"), "terminal history mode");
                Check(f.ChildApplies == config.Actions.Length, "one dispatch per accepted reward action");
            });
        foreach (var config in new[] {
            (Family: "add", Mode: "preview_confirm", Min: 1, Max: 2, Domain: 5),
            (Family: "remove", Mode: "auto_at_max", Min: 1, Max: 2, Domain: 5),
            (Family: "upgrade", Mode: "explicit_confirm", Min: 1, Max: 1, Domain: 5),
            (Family: "add", Mode: "explicit_confirm", Min: 0, Max: 2, Domain: 5),
            (Family: "add", Mode: "auto_at_max", Min: 1, Max: 9, Domain: 10),
            (Family: "add", Mode: "auto_at_max", Min: 2, Max: 2, Domain: 2),
        })
            Case("unsupported reward family mode combination", () => {
                using var f = new FakeSession { Family = config.Family, Mode = config.Mode, Min = config.Min, Max = config.Max, Domain = config.Domain };
                using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
                Error(Read(service), "internal_failure"); Check(f.ChildApplies == 0, "bad reward admission no dispatch");
            });
        foreach (var config in new[] {
            (Mode: "auto_at_max", Mutation: "forbidden_confirm"),
            (Mode: "auto_at_max", Mutation: "forbidden_preview"),
            (Mode: "explicit_confirm", Mutation: "forbidden_preview"),
            (Mode: "explicit_confirm", Mutation: "payload_mode"),
        })
            Case("reward terminal controls before publication", () => {
                using var f = new FakeSession { Family = "add", Mode = config.Mode, Min = 1, Max = 3, Domain = 5 };
                using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
                Play(service, "select:3"); f.Mutation = config.Mutation;
                Error(Read(service), "internal_failure"); Check(f.ChildApplies == 1, "forbidden reward control undispatched");
            });
        foreach (string mode in new[] { "auto_at_max", "explicit_confirm" })
            Case("early reward completion cannot certify effects", () => {
                using var f = new FakeSession { Family = "add", Mode = mode, Min = 1, Max = 3, Domain = 5 };
                using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
                Play(service, "select:3"); f.Mutation = "early_resolved";
                Error(Read(service), "internal_failure"); Check(f.ChildApplies == 1, "missing terminal witness no retry");
            });
        foreach (string mutation in new[] { "resolved_empty", "resolved_duplicate", "resolved_wrong_slot" })
            Case("reward resolved exact selected originals", () => {
                using var f = new FakeSession { Family = "add", Mode = "auto_at_max", Min = 2, Max = 2, Domain = 5 };
                using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
                Play(service, "select:3"); Play(service, "select:1"); f.Mutation = mutation;
                Error(Read(service), "internal_failure"); Check(f.ChildApplies == 2, "bad auto result cannot retry");
            });
        foreach (int count in new[] { 2, 8 })
            Case("fixed multi-upgrade reverse selection", () => {
                using var f = new FakeSession { Min = count, Max = count, Domain = count + 1, Resume = true };
                using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
                foreach (int slot in Enumerable.Range(0, count).Reverse()) Play(service, "select:" + slot);
                Play(service, "confirm");
                Check(Read(service).GetProperty("parent").GetProperty("completed_card_children").GetInt32() == 0, "terminal envelope snapshot precedes child read");
                var ready = Read(service).GetProperty("parent");
                Check(ready.GetProperty("completed_card_children").GetInt32() == 1, "next snapshot retains completion");
                Post(service, Request(new string('d', 64)));
                for (int i=0;i<2;i++) Check(Read(service).GetProperty("parent").GetProperty("completed_card_children").GetInt32() == 1, "repeated parent terminal stable");
            });
        foreach (int value in new[] { -1, 1, 5 })
            Case("forged initial completed count", () => {
                using var f = new FakeSession { CompletedOverride = value };
                using var service = new GenericEventV6WireService(Nonce, f);
                Error(Read(service), "internal_failure"); Check(f.ParentApplies == 0, "count forgery cannot dispatch");
            });
        foreach (int value in new[] { 0, 2 })
            Case("next completion snapshot cannot regress or skip", () => {
                using var f = new FakeSession { Family = "remove", Resume = true };
                using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
                Play(service, "select:0"); Play(service, "confirm"); Read(service);
                f.CompletedOverride = value; Error(Read(service), "internal_failure");
                Check(f.ParentApplies == 1, "no next parent dispatch");
            });
        Case("unsupported cleanup preserves latest completed lineage", () => {
            using var f = new FakeSession { Family = "remove", FailAfterResolution = true };
            using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
            Play(service, "select:0"); Play(service, "confirm"); Read(service);
            var p = Read(service).GetProperty("parent");
            Check(p.GetProperty("status").GetString() == "unsupported" && p.GetProperty("completed_card_children").GetInt32() == 1 && p.GetProperty("prior_results").GetArrayLength() == 0, "child effect survives parent cleanup failure");
        });
        foreach (string mutation in new[] { "history_missing", "history_duplicate", "history_foreign" })
            Case("completion history must match validated lineage", () => {
                using var f = new FakeSession { Family = "remove", Resume = true };
                using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
                Play(service, "select:0"); Play(service, "confirm"); Read(service);
                f.Mutation = mutation; Error(Read(service), "internal_failure");
            });
        Case("terminal child envelope is not repeatable", () => {
            using var f = new FakeSession { Family = "remove" };
            using var service = new GenericEventV6WireService(Nonce, f); Child(f, service);
            Play(service, "select:0"); Play(service, "confirm"); Read(service); Error(Read(service), "internal_failure");
        });
        foreach(int count in new[]{1,2,8})
            Case("transform semantic version and fixed count",()=>{
                using var f=new FakeSession{Family="transform",Min=count,Max=count,Domain=count+1,Resume=true};
                using var service=new GenericEventV6WireService(Nonce,f);Child(f,service);
                foreach(int slot in Enumerable.Range(0,count).Reverse())
                {
                    var observation=Read(service);Check(observation.GetProperty("payload").GetProperty("version").GetString()=="card_transform_v1","transform observation version");
                    var receipt=Post(service,Request(observation.GetProperty("payload").GetProperty("decision_id").GetString()!,"select:"+slot,1,ParentId,"choose:0"));
                    Check(receipt.GetProperty("payload").GetProperty("version").GetString()=="card_transform_v1","transform receipt version");
                }
                Play(service,"confirm");var done=Read(service);
                Check(done.GetProperty("payload").GetProperty("version").GetString()=="card_transform_v1","transform terminal version");
                Check(done.GetProperty("parent").GetProperty("completed_card_children").GetInt32()==0,"terminal lag preserved");
                Check(Read(service).GetProperty("parent").GetProperty("completed_card_children").GetInt32()==1,"completion retained");
            });
        foreach(string family in new[]{"upgrade","transform"})
            Case("wrong engine read tag rejected",()=>{
                using var f=new FakeSession{Family=family,ReadTag=family=="transform"?"card_selection_v1":"card_transform_v1"};
                using var service=new GenericEventV6WireService(Nonce,f);Child(f,service);Error(Read(service),"internal_failure");Check(f.ChildApplies==0,"wrong read tag no dispatch");
            });
        foreach(bool uncertain in new[]{false,true})
            foreach(bool wrong in new[]{false,true})
                Case("transform receipt and failure tag",()=>{
                    using var f=new FakeSession{Family="transform",UncertainChild=uncertain,ApplyTag=wrong?"card_selection_v1":"card_transform_v1"};
                    using var service=new GenericEventV6WireService(Nonce,f);Child(f,service);var observation=Read(service);
                    var result=Post(service,Request(observation.GetProperty("payload").GetProperty("decision_id").GetString()!,"select:0",1,ParentId,"choose:0"));
                    if(wrong)Error(result,"internal_failure");else Check(result.GetProperty("payload").GetProperty("version").GetString()=="card_transform_v1","exact receipt/failure codec");
                    if(wrong||uncertain){Error(Read(service),wrong?"internal_failure":"unsupported");Check(f.ChildApplies==1,"never retry uncertain/tag failure");}
                });
        Case("transform resolved wrong engine tag",()=>{
            using var f=new FakeSession{Family="transform"};using var service=new GenericEventV6WireService(Nonce,f);Child(f,service);
            Play(service,"select:0");Play(service,"confirm");f.ReadTag="card_selection_v1";Error(Read(service),"internal_failure");Check(f.ParentApplies==1,"no next parent");
        });
        Case("explicit G6 routes",()=>Check(GenericEventV6WireService.DecisionRoute=="/probe/generic-event-v6/public/decision"&&GenericEventV6WireService.ActionRoute=="/probe/generic-event-v6/public/action","exact routes"));
        ItemCases();
        Console.WriteLine(JsonSerializer.Serialize(new { schema_version = 1, status = "passed", suite = "generic_event_v6_wire", check_count = _checks }));
        return 0;
    }

    private static void Play(GenericEventV6WireService service, string action)
    {
        var value = Read(service); var child = value.GetProperty("child");
        var payload = value.GetProperty("payload");
        Check(payload.GetProperty("legal_actions").EnumerateArray().Any(a => a.GetString() == action), "advertised action " + action);
        var receipt = Post(service, Request(payload.GetProperty("decision_id").GetString()!, action,
            child.GetProperty("ordinal").GetInt32(), child.GetProperty("parent_decision_id").GetString(),
            child.GetProperty("parent_action_id").GetString()));
        Check(receipt.GetProperty("kind").GetString() == "action" && receipt.GetProperty("payload").GetProperty("outcome").GetString() == "accepted", "accepted child " + action);
    }

    private sealed class FakeSession : IGenericEventV6Session
    {
        internal string Stable = "UNREGISTERED.OPTION", Rendered = "A presented option", Mutation = "", Family = "upgrade", Mode = "preview_confirm";
        internal int Min = 1, Max = 1, Domain = 3;
        private readonly HashSet<int> _selected = new();
        private readonly List<CardSelectionV1ActionResult> _history = new();
        private bool _preview, _resolved, _delivered;
        internal bool Resume, FailAfterResolution;
        internal int? CompletedOverride;
        internal bool HasChild, Uncertain, Throw, Regress, ThrowFirstDispose, UncertainChild;
        internal string? ReadTag, ApplyTag;
        internal Action? OnRead, OnApply;
        internal int Disposals;
        internal int ParentApplies, ChildApplies, ChildReads, Reads;
        public GenericEventV6Observation Read()
        {
            Reads++; OnRead?.Invoke();
            if (_delivered && (Resume || FailAfterResolution))
            {
                bool complete = ParentApplies > 1;
                var rows = new List<GenericEventV6PriorResult>();
                if (!FailAfterResolution && Mutation != "history_missing") rows.Add(new(Mutation == "history_foreign" ? new string('f',64) : ParentId,"choose:0","child_completed"));
                if (Mutation == "history_duplicate") rows.Add(rows[0]);
                if (complete) rows.Add(new(new string('d',64),"choose:0","map_handoff"));
                bool ready = !FailAfterResolution && !complete;
                return new(Nonce, FailAfterResolution ? "unsupported" : complete ? "complete" : "ready",
                    FailAfterResolution ? "unsupported" : complete ? "map_handoff" : "proceed", ready ? new string('d',64) : "",
                    ready ? new[] { new GenericEventV6Candidate(0,"choose:0","PROCEED","Continue",true,false,true) } : Array.Empty<GenericEventV6Candidate>(),
                    ready ? new[] { "choose:0" } : Array.Empty<string>(), null, rows, ParentApplies, ParentApplies, rows.Count, 1,
                    ChildApplies, ChildApplies, _history.Count, "unverified", CompletedOverride ?? 1);
            }
            bool initial = ParentApplies == 0;
            int count = Regress ? 0 : ParentApplies;
            GenericEventV6Child? child = !HasChild ? null : new(
                Mutation == "ordinal" ? 2 : 1, Mutation == "lineage" ? new string('f', 64) : ParentId,
                "choose:0", Mutation == "operation" ? "unknown" : Family, Min,
                Mutation == "count" ? 2 : Max, Mutation == "mode" ? "auto_at_max" : Mode,
                Mutation == "domain" ? 1 : Mutation == "domain_changed" ? 4 : Domain);
            return new(Nonce, initial ? "ready" : HasChild ? "child" : "waiting",
                initial ? "choose_option" : HasChild ? "child" : "waiting", initial ? ParentId : "",
                initial ? new[] { new GenericEventV6Candidate(0, "choose:0", Stable, Rendered, true, false, false) } : Array.Empty<GenericEventV6Candidate>(),
                initial ? new[] { "choose:0" } : Array.Empty<string>(), child,
                Array.Empty<GenericEventV6PriorResult>(), count, count, 0, HasChild ? 1 : 0,
                ChildApplies, ChildApplies, _history.Count, initial ? "none_attempted" : "unverified", CompletedOverride ?? (_delivered ? 1 : 0));
        }
        public GenericEventV6ApplyResult Apply(string? decisionId, string? actionId)
        {
            ParentApplies++; OnApply?.Invoke();
            if (Throw) throw new InvalidOperationException("After side effect");
            return new(Nonce, decisionId!, actionId!, Uncertain ? "uncertain" : "accepted");
        }
        public GenericEventV6ChildRead ReadChild(string? d, string? a, int o) => new GenericEventV6CardRead(ReadTag ?? GenericEventV6Families.ContractVersion(Family), ReadChildValue(d,a,o));
        public GenericEventV6ChildApply ApplyChild(string? d, string? a, int o, string? decision, string? action) => new GenericEventV6CardApply(ApplyTag ?? GenericEventV6Families.ContractVersion(Family), ApplyChildValue(d,a,o,decision,action));
        private ICardSelectionV1ReadValue ReadChildValue(string? parentDecisionId, string? parentActionId, int childOrdinal)
        {
            ChildReads++;
            int[] slots = Mutation == "selected_mismatch" ? new[] { 0 } : Mutation == "selection_lost" ? Array.Empty<int>() : _selected.Order().ToArray();
            bool publishedPreview = Mutation == "preview_below_min" || (_preview && Mutation is not "missing_preview" and not "reopen_selecting");
            var candidates = Enumerable.Range(0, Domain).Select(i => new CardSelectionV1Candidate(i,
                Mutation == "key_changed" ? "Changed_" + i : "Card_" + i, 0,
                Mutation != "hidden_candidate" || i != 0, true,
                Mutation == "flags_mismatch" ? !slots.Contains(i) : slots.Contains(i))).ToArray();
            if (_resolved || (Mutation == "early_resolved" && _selected.Count > 0))
            {
                var selected = candidates.Where(c => _selected.Contains(c.Slot)).ToList();
                if (Mutation == "resolved_empty") selected.Clear();
                if (Mutation == "resolved_duplicate") selected.Add(selected[0]);
                if (Mutation == "resolved_wrong_slot") selected[0] = candidates.First(c => !_selected.Contains(c.Slot));
                _delivered = true;
                return new CardSelectionV1ResolvedResult(Nonce,
                    Mutation == "resolved_family" ? "transform" : Family, selected, _history);
            }
            var legal = _preview ? new List<string> { "confirm" } :
                Enumerable.Range(0, Domain).Where(i => !_selected.Contains(i) && _selected.Count < Max)
                    .Select(i => "select:" + i).ToList();
            if (!_preview && _selected.Count >= Min && Mode == "preview_confirm") legal.Add("preview");
            if (!_preview && _selected.Count >= Min && Mode == "explicit_confirm") legal.Add("confirm");
            if (Mutation == "forbidden_confirm") legal.Add("confirm");
            if (Mutation == "forbidden_preview") legal.Add("preview");
            if (Mutation == "preview_below_count") legal.Add("preview");
            if (Mutation == "duplicate_legal") legal.Add(legal[0]);
            if (Mutation == "selected_legal") legal.Add("select:3");
            string decision = ChildApplies == 0 ? ChildId : new string('b', 62) + ChildApplies.ToString("x2");
            return new CardSelectionV1Observation(Nonce, "ready", publishedPreview ? "preview" : "selecting",
                Mutation == "payload_family" ? "transform" : Family, Mutation == "payload_mode" ? "preview_confirm" : Mode,
                Mutation == "payload_min" ? Min + 1 : Min, Mutation == "payload_max" ? Max + 1 : Max,
                decision, candidates, slots, legal, Mutation == "hidden_history" ? Array.Empty<CardSelectionV1ActionResult>() : _history);
        }
        private ICardSelectionV1ApplyValue ApplyChildValue(string? parentDecisionId, string? parentActionId, int childOrdinal, string? decisionId, string? actionId)
        {
            ChildApplies++;
            string result;
            if (actionId!.StartsWith("select:", StringComparison.Ordinal))
            {
                _selected.Add(int.Parse(actionId[7..])); result = "selected";
                if ((Family is "remove" or "transform" || Family == "upgrade" && Max > 1) && _selected.Count == Max) _preview = true;
                if (Family == "add" && Mode == "auto_at_max" && _selected.Count == Max) _resolved = true;
            }
            else if (actionId == "preview") { _preview = true; result = "previewed"; }
            else { _resolved = true; result = "committed"; }
            if (UncertainChild) return new CardSelectionV1ApplyFailure(Nonce, "uncertain");
            _history.Add(new CardSelectionV1ActionResult(decisionId!, actionId!, result));
            return new CardSelectionV1DispatchReceipt(Nonce, decisionId!, actionId!);
        }
        public void Dispose()
        {
            Disposals++;
            if (ThrowFirstDispose && Disposals == 1) throw new InvalidOperationException("First cleanup failure.");
        }
    }
    private static void ItemCases() {
        foreach(bool stale in new[]{false,true}) Case("item effect label belongs to latest family owner",()=>{
            using var f=new ItemFake();using var s=new GenericEventV6WireService(Nonce,f);ItemStart(s);ItemCollect(s);Read(s);
            if(stale){var r=Read(s);Post(s,Request(r.GetProperty("parent").GetProperty("decision_id").GetString()!));f.Effects="item_effect_verified";}
            else f.Effects="card_effect_verified";
            Error(Read(s),"internal_failure");
        });
        foreach(string kind in new[]{"potion","relic"}) Case("item singleton "+kind,()=>{
            using var f=new ItemFake{Kind=kind};using var s=new GenericEventV6WireService(Nonce,f);
            ItemStart(s);ItemCollect(s);var done=Read(s);
            Check(done.GetProperty("payload").GetProperty("result").GetString()=="collected","frozen item codec");
            Check(done.GetProperty("parent").GetProperty("completed_item_children").GetInt32()==0,"terminal lag");
            var next=Read(s);Check(next.GetProperty("parent").GetProperty("completed_item_children").GetInt32()==1,"item count retained");
            Check(next.GetProperty("parent").GetProperty("completed_card_children").GetInt32()==0,"item never card credit");
        });
        Case("identical item decision scoped across four children",()=>{
            using var f=new ItemFake{Target=4};using var s=new GenericEventV6WireService(Nonce,f);string? digest=null;
            for(int i=0;i<4;i++) {
                ItemStart(s);var child=Read(s);var payload=child.GetProperty("payload");var c=child.GetProperty("child");
                string id=payload.GetProperty("decision_id").GetString()!;Check(digest is null||digest==id,"same inner digest");digest=id;
                var r=Post(s,Request(id,"collect:7",i+1,c.GetProperty("parent_decision_id").GetString(),"choose:0"));
                Check(r.GetProperty("payload").GetProperty("status").GetString()=="accepted","scoped accept");Read(s);
            }
            Check(Read(s).GetProperty("parent").GetProperty("completed_item_children").GetInt32()==4&&f.Applies==4,"four shared episodes");
        });
        foreach(string mutation in new[]{"descriptor","tag","count","key","index","enabled","slots","legal","digest"})
            Case("malformed item ready "+mutation,()=>{
                using var f=new ItemFake{Mutation=mutation};using var s=new GenericEventV6WireService(Nonce,f);
                ItemStart(s);Error(Read(s),"internal_failure");Check(f.Applies==0,"before item POST");
            });
        foreach(string mutation in new[]{"done_key","done_kind","done_index","done_decision","done_action","done_tag"})
            Case("malformed item resolution "+mutation,()=>{
                using var f=new ItemFake();using var s=new GenericEventV6WireService(Nonce,f);ItemStart(s);ItemCollect(s);
                f.Mutation=mutation;Error(Read(s),"internal_failure");Error(Read(s),"internal_failure");Check(f.Applies==1,"no retry");
            });
        foreach(string mutation in new[]{"apply_tag","uncertain","throw"})
            Case("item uncertain or wrong apply family "+mutation,()=>{
                using var f=new ItemFake{Mutation=mutation};using var s=new GenericEventV6WireService(Nonce,f);ItemStart(s);
                var ready=Read(s);var c=ready.GetProperty("child");var id=ready.GetProperty("payload").GetProperty("decision_id").GetString()!;
                var r=Post(s,Request(id,"collect:7",1,c.GetProperty("parent_decision_id").GetString(),"choose:0"));
                if(mutation=="uncertain")Check(r.GetProperty("payload").GetProperty("status").GetString()=="uncertain","canonical uncertain");
                else Error(r,"internal_failure");
                Error(Read(s),mutation=="uncertain"?"unsupported":"internal_failure");Check(f.Applies==1,"no repeated dispatch");
            });
        Case("item failure cannot be card tag",()=>{
            using var f=new ItemFake{Mutation="failure_tag"};using var s=new GenericEventV6WireService(Nonce,f);
            ItemStart(s);var r=Read(s);var c=r.GetProperty("child");
            Error(Post(s,Request(r.GetProperty("payload").GetProperty("decision_id").GetString()!,"collect:7",1,c.GetProperty("parent_decision_id").GetString(),"choose:0")),"internal_failure");
            Check(f.Applies==1,"one attempt");
        });
        foreach(string action in new[]{"collect:07","collect:256","select:7","confirm"}) Case("item grammar "+action,()=>{
            using var f=new ItemFake();using var s=new GenericEventV6WireService(Nonce,f);ItemStart(s);var r=Read(s);
            Error(Post(s,Request(r.GetProperty("payload").GetProperty("decision_id").GetString()!,action,1,r.GetProperty("child").GetProperty("parent_decision_id").GetString(),"choose:0")),"invalid_request");
            Check(f.Applies==0,"grammar stops dispatch");
        });
        Case("item stale lineage cannot replay second episode",()=>{
            using var f=new ItemFake{Target=2};using var s=new GenericEventV6WireService(Nonce,f);ItemStart(s);ItemCollect(s);Read(s);
            ItemStart(s);var r=Read(s);Error(Post(s,Request(r.GetProperty("payload").GetProperty("decision_id").GetString()!,"collect:7",1,new string('a',64),"choose:0")),"invalid_request");
            Check(f.Applies==1,"old child correlation no dispatch");
        });
    }
    private static void ItemStart(GenericEventV6WireService s) {
        var r=Read(s);var d=r.GetProperty("parent").GetProperty("decision_id").GetString()!;
        Check(Post(s,Request(d)).GetProperty("kind").GetString()=="action","item parent accepted");
    }
    private static void ItemCollect(GenericEventV6WireService s) {
        var r=Read(s);var c=r.GetProperty("child");var d=r.GetProperty("payload").GetProperty("decision_id").GetString()!;
        Check(Post(s,Request(d,"collect:7",c.GetProperty("ordinal").GetInt32(),c.GetProperty("parent_decision_id").GetString(),"choose:0")).GetProperty("payload").GetProperty("status").GetString()=="accepted","item accepted");
    }
    private sealed class ItemFake : IGenericEventV6Session {
        internal string Kind="relic",Mutation="";internal string? Effects;internal int Target=1,Applies;
        private int _parents,_episodes,_completed;private bool _active,_accepted,_delivered,_complete;
        private string _pd="";private readonly List<GenericEventV6PriorResult> _prior=new();
        private ItemV1Offer Offer=>new(7,Kind,"ITEM",true);
        private string[] Actions=>new[]{"collect:7"};private string?[] Slots=>new string?[]{"BASE",null};
        private string Id=>ItemV1CanonicalEncoder.ComputeDecisionId(Nonce,new[]{Offer},Slots,Actions);
        public GenericEventV6Observation Read() {
            if(_delivered) {_active=false;_delivered=false;_prior.Add(new(_pd,"choose:0","child_completed"));}
            bool proceed=_completed==Target;string status=_active?"child":_complete?"complete":"ready";
            var c=_active?new GenericEventV6Child(_episodes,_pd,"choose:0",Mutation=="descriptor"?2:1):null;
            return new(Nonce,status,_active?"child":_complete?"map_handoff":proceed?"proceed":"choose_option",
                status=="ready"?new string((char)('a'+_completed),64):"",
                status=="ready"?new[]{new GenericEventV6Candidate(0,"choose:0","PAGE_"+_completed,"Choose",true,false,proceed)}:Array.Empty<GenericEventV6Candidate>(),
                status=="ready"?new[]{"choose:0"}:Array.Empty<string>(),c,_prior,
                _parents,_parents,_prior.Count,_episodes,Applies,Applies,_completed,Effects??(_parents==0?"none_attempted":"unverified"),0,_completed);
        }
        public GenericEventV6ApplyResult Apply(string? d,string? a) {
            _parents++;_pd=d!;if(_completed==Target){_complete=true;_prior.Add(new(d!,a!,"map_handoff"));}
            else{_active=true;_episodes++;_accepted=false;}
            return new(Nonce,d!,a!,"accepted");
        }
        public GenericEventV6ChildRead ReadChild(string? pd,string? pa,int ordinal) {
            if(Mutation is "tag" or "done_tag")return new GenericEventV6CardRead("item_v1",CardSelectionV1Observation.Fixed(Nonce,"unsupported","unsupported",Array.Empty<CardSelectionV1ActionResult>()));
            if(_accepted) {
                _completed++;_delivered=true;
                return new GenericEventV6ItemRead(new ItemV1ResolvedResult(Nonce,Mutation=="done_decision"?new string('f',64):Id,
                    Mutation=="done_action"?"collect:8":"collect:7",Mutation=="done_index"?8:7,Mutation=="done_kind"?"potion":Kind,Mutation=="done_key"?"OTHER":"ITEM"));
            }
            var offers=Mutation=="count"?new[]{Offer,Offer}:new[]{new ItemV1Offer(Mutation=="index"?256:7,Kind,Mutation=="key"?"bad-key":"ITEM",Mutation!="enabled")};
            return new GenericEventV6ItemRead(new ItemV1Observation(Nonce,"ready",Mutation=="digest"?new string('f',64):Id,offers,
                Mutation=="slots"?new string?[]{"OTHER",null}:Slots,Mutation=="legal"?new[]{"collect:7","collect:7"}:Actions));
        }
        public GenericEventV6ChildApply ApplyChild(string? pd,string? pa,int ordinal,string? d,string? a) {
            Applies++;if(Mutation=="throw")throw new Exception();
            if(Mutation=="failure_tag")return new GenericEventV6CardApply("item_v1",new CardSelectionV1ApplyFailure(Nonce,"uncertain"));
            if(Mutation=="apply_tag")return new GenericEventV6CardApply("item_v1",new CardSelectionV1DispatchReceipt(Nonce,d!,a!));
            if(Mutation=="uncertain")return new GenericEventV6ItemApply(new ItemV1ApplyFailure(Nonce,"uncertain"));
            _accepted=true;return new GenericEventV6ItemApply(new ItemV1DispatchReceipt(Nonce,d!,a!));
        }
        public void Dispose(){}
    }
}
