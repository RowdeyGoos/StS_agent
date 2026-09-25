using System;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Unified;
using static Sts2AgentBridge.Unified.FullPublicGraph;

internal static class FullAgentSessionTests
{
    // Authored transport fixture. It does not execute target-game assemblies or
    // claim equivalence of the native/headless gameplay producers.
    internal sealed class SocketBackend : IFullAgentBackend
    {
        private int _stage;
        private readonly object _identity = new();
        private readonly System.Collections.Generic.List<FullCompletion> _completed = new();
        public FullCapture Read()
        {
            if (_stage == 2) return new("complete", null, Array.Empty<FullCommand>(), Array.Empty<object>(), _completed.ToArray(), "victory");
            int count = _stage == 0 ? 2048 : 1;
            var actions = Enumerable.Range(0, count).Select(i => Candidate(i, _stage == 0 ? "choose_event_option" : "confirm_selection", "option:" + i)).ToArray();
            var graph = Decision(Node("run", fields: new (string, object?)[] { ("hp", 80), ("max_hp", 80) }),
                Node(_stage == 0 ? "event" : "rest", children: Enumerable.Range(0, count).Select(i => Node("option", "option_" + i, "option:" + i,
                    new (string, object?)[] { ("description", new string('x', 80)) }))), actions);
            return new("ready", graph, actions.Select((a, i) => new FullCommand(new(Capability.Core,
                "/fixture/native", true, 0, 0, _stage.ToString("x64"), "select:" + i), a)).ToArray(),
                new[] { _identity }, Array.Empty<FullCompletion>());
        }
        public ModuleReply Apply(BridgeRequest request)
        {
            if (request.Action != (_stage == 0 ? "select:2047" : "select:0")) throw new InvalidOperationException("wrong fixture target");
            _completed.Add(FullCompletion.For(request)); _stage++;
            return new(JsonSerializer.SerializeToUtf8Bytes(new { status = "accepted", decision_id = request.Decision, action_id = request.Action }));
        }
        public void Dispose() { if (_stage is not (0 or 2)) throw new InvalidOperationException("pending fixture parent"); }
    }
    internal sealed class Backend : IFullAgentBackend
    {
        internal int Posts, Reads, Revision, Ordinal, Hp = 80;
        internal object Identity = new();
        internal string Status = "ready", Outcome = "victory";
        internal bool Stale, WrongReceipt, Uncertain, DisposeFailed;
        internal FullCompletion[] Completed = Array.Empty<FullCompletion>();
        internal Action<JsonObject>? Change;
        internal FullCommand? Last;
        internal string Id => Revision.ToString("x64");
        public FullCapture Read()
        {
            Reads++;
            var candidate = Candidate(0, "end_turn");
            var graph = Decision(Node("run", fields: new (string, object?)[] { ("hp", Hp) }), Node("combat"), new[] { candidate });
            Change?.Invoke(graph);
            var command = new FullCommand(new(Capability.Core, "/probe/v0/public/combat-action", true, 0, 0, Id, "end_turn", Ordinal, new string('a', 64), "choose:0"), candidate);
            return new(Status, Status == "ready" ? graph : null, Status == "ready" ? new[] { command } : Array.Empty<FullCommand>(),
                new[] { Identity }, Completed, Status == "complete" ? Outcome : null);
        }
        public ModuleReply Apply(BridgeRequest command)
        {
            Posts++; Last = new(command, Candidate(0, "end_turn"));
            if (Stale) return new("{}"u8.ToArray(), StaleWithoutMutation: true);
            if (Uncertain) throw new InvalidOperationException("lost receipt");
            return new(JsonSerializer.SerializeToUtf8Bytes(new { status = "accepted", decision_id = WrongReceipt ? new string('f', 64) : command.Decision, action_id = command.Action }));
        }
        public void Dispose() { if (DisposeFailed) throw new InvalidOperationException("cleanup"); }
        internal FullCompletion LastCompletion => FullCompletion.For(Last!.Request);
    }
    private static JsonObject Read(FullAgentSession session)
    {
        var reply = session.Handle(new(Capability.Core, FullAgentRoutes.Decision, false, 0, 0));
        try { return JsonNode.Parse(reply.Body)!.AsObject(); } finally { Array.Clear(reply.Body); }
    }
    private static ModuleReply Apply(FullAgentSession session, JsonObject observation) =>
        session.Handle(new(Capability.Core, FullAgentRoutes.Action, true, 0, 0, observation["decision_id"]!.GetValue<string>(), "action:0"));
    internal static void Run(Action<bool, string> check)
    {
        {
            byte[] body = "{\"status\":\"ready\",\"surface\":\"rest\",\"completed\":[],\"options\":[{\"kind\":\"smith\",\"enabled\":true}]}"u8.ToArray();
            using var wire = FullAgentWire.Read(new(body));
            check(body.All(b => b == 0), "native response source buffer cleared");
            check(wire.RootElement.GetProperty("status").GetString() == "ready" &&
                wire.RootElement.GetProperty("surface").GetString() == "rest" &&
                wire.RootElement.GetProperty("options")[0].GetProperty("enabled").GetBoolean(),
                "native response document owns bytes after source wipe");
        }
        foreach (bool terminal in new[] { false, true })
        {
            byte[] body = terminal ? "{\"status\":\"failed\"}"u8.ToArray() : "{\"status\":\"ready\"} {}"u8.ToArray();
            bool rejected = false;
            try { using var wire = FullAgentWire.Read(new(body, Terminal: terminal)); }
            catch (Exception error) when (error is JsonException or AgentUnsupported) { rejected = true; }
            check(rejected && body.All(b => b == 0), "failed native reply clears its source buffer");
        }
        foreach (var stage in Enum.GetValues<FullReadStage>())
        {
            var backend = new Backend(); using var session = new FullAgentSession(backend, "fixture");
            backend.Change = _ => FullReadFailure.At(FullReadStage.Run, () => FullReadFailure.At<bool>(stage,
                () => throw new InvalidOperationException("private sentinel must not escape")));
            var stopped = Read(session);
            check(stopped["code"]!.GetValue<string>() == "read_" + stage.ToString().ToLowerInvariant() + "_failed",
                "innermost read boundary retained " + stage);
            check(!stopped.ToJsonString().Contains("sentinel") && backend.Posts == 0 &&
                stopped["accepted"]!.GetValue<int>() == 0, "read diagnostic is bounded and nonmutating " + stage);
            int reads = backend.Reads;
            Read(session);
            session.Handle(new(Capability.Core, FullAgentRoutes.Action, true, 0, 0, new string('a', 64), "action:0"));
            check(backend.Reads == reads && backend.Posts == 0, "read failure remains stopped " + stage);
        }
        foreach (string reference in new[] { "card:0", "option:2047", "cell:120", "private:0", "card:", "card:-1", "card:1\n", "card:1:2", "card:１" })
        {
            var graph = Decision(Node("run", children: new[] { Node("card", reference: reference) }), Node("combat"), new[] { Candidate(0, "end_turn") });
            bool valid = true; try { Validate(graph); } catch (AgentUnsupported) { valid = false; }
            check(valid == (reference is "card:0" or "option:2047" or "cell:120"), "closed public reference boundary " + reference);
        }
        foreach (bool identity in new[] { false, true })
        {
            var backend = new Backend(); using var session = new FullAgentSession(backend, "fixture");
            var initial = Read(session); var same = Read(session);
            check(initial["decision_id"]!.ToJsonString() == same["decision_id"]!.ToJsonString(), "full stable graph preserves opaque token");
            if (identity) backend.Identity = new(); else backend.Hp--;
            var stale = Apply(session, initial);
            check(stale.StaleWithoutMutation && !stale.Terminal && backend.Posts == 0, "full richer view or object change blocks mutation");
        }
        {
            var backend = new Backend(); using var session = new FullAgentSession(backend, "fixture");
            var first = Read(session); var receipt = Apply(session, first);
            check(!receipt.Terminal && backend.Posts == 1, "full accepted native command");
            var parent = backend.LastCompletion;
            backend.Revision++;
            var child = Read(session);
            check(child["pending"]!.GetValue<int>() == 1 && child["reconciled"]!.GetValue<int>() == 0, "full next child decision does not settle parent");
            Apply(session, child);
            var childCompletion = backend.LastCompletion;
            backend.Completed = new[] { childCompletion }; backend.Revision++;
            var next = Read(session);
            check(next["pending"]!.GetValue<int>() == 1 && next["reconciled"]!.GetValue<int>() == 1, "full child settles independently");
            next = Read(session);
            check(next["reconciled"]!.GetValue<int>() == 1, "full retained receipt does not double count");
            backend.Completed = new[] { parent }; backend.Status = "complete";
            var done = Read(session);
            check(done["status"]!.GetValue<string>() == "complete" && done["outcome"]!.GetValue<string>() == "victory" &&
                done["accepted"]!.GetValue<int>() == 2 && done["reconciled"]!.GetValue<int>() == 2, "full outcome requires both native completions");
            int reads = backend.Reads; backend.Status = "ready"; backend.Hp = 1;
            check(Read(session).ToJsonString() == done.ToJsonString() && backend.Reads == reads, "terminal is retained without backend reads");
            check(Apply(session, first).StaleWithoutMutation && backend.Posts == 2, "full replay never redispatches");
        }
        {
            var backend = new Backend(); using var session = new FullAgentSession(backend, "fixture");
            for (int ordinal = 1; ordinal <= 4; ordinal++)
            {
                backend.Ordinal = ordinal;
                Apply(session, Read(session));
                backend.Completed = new[] { backend.LastCompletion };
                var done = Read(session);
                check(done["reconciled"]!.GetValue<int>() == ordinal && backend.Posts == ordinal,
                    "identical native offer is independently owned in child " + ordinal);
            }
        }
        foreach (string failure in new[] { "unowned", "wrong_receipt", "uncertain", "incomplete", "duplicate", "bad_graph", "bad_outcome" })
        {
            var backend = new Backend(); var session = new FullAgentSession(backend, "fixture");
            var before = Read(session); ModuleReply? bad = null;
            if (failure == "unowned") backend.Completed = new[] { new FullCompletion(new string('e', 64), "end_turn", Capability.Core, "/probe/v0/public/combat-action") };
            else if (failure == "bad_graph") backend.Change = graph => graph["run"]!["ref"] = "private:0";
            else if (failure == "bad_outcome") { backend.Status = "complete"; backend.Outcome = "slice_complete"; }
            else
            {
                backend.WrongReceipt = failure == "wrong_receipt"; backend.Uncertain = failure == "uncertain";
                bad = Apply(session, before);
                if (failure == "incomplete") backend.Status = "complete";
                if (failure == "duplicate") bad = Apply(session, Read(session));
            }
            var stopped = Read(session);
            check(stopped["status"]!.GetValue<string>() == "failed", "full fail closed: " + failure);
            int posts = backend.Posts;
            Apply(session, before);
            check(backend.Posts == posts, "full no retry after " + failure);
            if (failure is "incomplete" or "duplicate")
            {
                bool rejected = false; try { session.Dispose(); } catch { rejected = true; }
                check(rejected, "full incomplete cleanup is not a clean handoff");
            }
        }
        {
            var backend = new Backend { Stale = true }; using var session = new FullAgentSession(backend, "fixture");
            var receipt = Apply(session, Read(session)); var read = Read(session);
            check(receipt.StaleWithoutMutation && !receipt.Terminal && read["accepted"]!.GetValue<int>() == 0 &&
                read["pending"]!.GetValue<int>() == 0 && backend.Posts == 1, "full native stale rejection is proven nonmutating");
        }
        {
            var backend = new Backend { DisposeFailed = true }; var session = new FullAgentSession(backend, "fixture");
            bool rejected = false; try { session.Dispose(); } catch { rejected = true; }
            check(rejected && Read(session)["status"]!.GetValue<string>() == "failed", "full disposal failure remains stopped");
        }
        foreach (string action in new[] { "action:0", "action:511", "action:2047" })
            check(FullAgentRoutes.IsAction(new string('a', 64), action), "full accepted slot grammar " + action);
        foreach (string action in new[] { "action:2048", "action:-1", "action:01", "action: 1", "action:1x" })
            check(!FullAgentRoutes.IsAction(new string('a', 64), action), "full rejected slot grammar " + action);
    }
}
