using System;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Unified;

internal static class AgentSessionTests
{
    internal sealed class Reader : IAgentPublicReader
    {
        internal object Entity = new();
        internal int Hp = 80;
        internal bool Unsupported, FailDispose;
        public string InitialFamily() => "combat";
        public AgentCapture Capture(string family, JsonElement legacy, JsonArray history, string? source)
        {
            if (Unsupported) throw new AgentUnsupported();
            var actions = legacy.GetProperty("legal_actions").EnumerateArray().Select((a, i) => {
                string id = a.ValueKind == JsonValueKind.String ? a.GetString()! : a.GetProperty("action_id").GetString()!;
                string kind = id switch { "play:0:0" => "play_card", "select:0" => "select_card", "confirm" => "confirm_selection", _ => "end_turn" };
                return new AgentCommand(id, new JsonObject { ["ref"] = "action:" + i, ["kind"] = kind,
                    ["subject"] = kind is "play_card" or "select_card" ? "card:0" : null, ["target"] = kind == "play_card" ? "enemy:0" : null });
            }).ToArray();
            return new(new JsonObject { ["hp"] = Hp, ["history"] = history.DeepClone(), ["source"] = source }, actions, new[] { Entity });
        }
        public void Dispose() { if (FailDispose) throw new InvalidOperationException(); }
    }
    private sealed class Native
    {
        internal int Step, Posts, Waits, BeforeChoiceWaits, AfterChoiceWaits;
        internal bool Stale, Uncertain, CleanupFailure;
        internal string Id => new((char)('a' + Step), 64);
        internal ModuleReply Handle(BridgeRequest r)
        {
            if (r.IsPost)
            {
                Posts++;
                if (Stale) return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "rejected", mutation_state = "none", reason = "stale_decision" }), StaleWithoutMutation: true);
                if (Uncertain) return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "failed" }), Terminal: true);
                Step++; Waits = 1;
                return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "accepted" }));
            }
            bool choice = r.Path.Contains("combat-choice");
            if (Step == 1 && BeforeChoiceWaits > 0)
            {
                if (choice) BeforeChoiceWaits--;
                return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "waiting" }));
            }
            if (!choice && Step == 3 && AfterChoiceWaits-- > 0)
                return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "waiting" }));
            if (choice && Step is 1 or 2)
                return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "ready", decision_id = Id,
                    legal_actions = Step == 1 ? new[] { "select:0", "confirm" } : new[] { "confirm" } }));
            if (choice && Step == 3)
                return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "complete", result = "selection_verified" }), Terminal: CleanupFailure);
            if (choice || Step is 1 or 2 || Waits-- > 0)
                return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "waiting" }));
            return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, status = "ready", decision_id = Id,
                legal_actions = new[] { new { action_id = Step == 0 ? "play:0:0" : "end_turn" } } }));
        }
    }
    private static JsonObject Read(AgentSession session)
    {
        var result = session.Handle(new(Capability.Core, AgentSession.DecisionRoute, false, 0, 0));
        return JsonNode.Parse(result.Body)!.AsObject();
    }
    private static ModuleReply Act(AgentSession session, JsonObject view, int slot = 0) =>
        session.Handle(new(Capability.Core, AgentSession.ActionRoute, true, 0, 0, view["decision_id"]!.GetValue<string>(), "action:" + slot));

    internal static void Run(Action<bool, string> check)
    {
        foreach(bool complete in new[]{false,true})
        {
            var native=new Native();bool infinity=false;
            ModuleReply Legacy(BridgeRequest r)=>infinity&&!r.IsPost
                ?new(JsonSerializer.SerializeToUtf8Bytes(new{schema_version=2,status=complete?"complete":"ready",decision_id=new string('e',64),outcome="defeat"}))
                :native.Handle(r);
            using var session=new AgentSession(new Reader(),Legacy,"nonce");
            var before=Read(session);Act(session,before);infinity=true;
            var after=Read(session);
            check(after["status"]!.GetValue<string>()=="unsupported"&&after["accepted"]!.GetValue<int>()==1&&after["reconciled"]!.GetValue<int>()==0&&native.Posts==1,"agent v1 rejects schema2 before reconciliation or another action");
        }
        foreach (bool identity in new[] { false, true })
        {
            var native = new Native(); var reader = new Reader(); using var session = new AgentSession(reader, native.Handle, "nonce");
            var before = Read(session); var repeated = Read(session);
            check(before["decision_id"]!.ToJsonString() == repeated["decision_id"]!.ToJsonString(), "unchanged coherent view retains token");
            if (identity) reader.Entity = new(); else reader.Hp--;
            var rejected = Act(session, before);
            check(rejected.StaleWithoutMutation && native.Posts == 0 && !rejected.Terminal, "rich-state/object change rejected before native mutation");
        }
        {
            var native = new Native(); using var session = new AgentSession(new Reader(), native.Handle, "nonce");
            var view = Read(session); Act(session, view);
            view = Read(session);
            check(view["status"]!.GetValue<string>() == "ready" && view["parent_pending"]!.GetValue<bool>() && view["reconciled"]!.GetValue<int>() == 0,
                "nested chooser preserves unreconciled combat parent");
            check(view["observation"]!["source"]!.GetValue<string>() == "card:0", "nested source from accepted public action");
            Act(session, view); view = Read(session);
            check(view["accepted"]!.GetValue<int>() == 2 && view["reconciled"]!.GetValue<int>() == 1, "toggle reconciles independently");
            Act(session, view); view = Read(session);
            if (view["status"]!.GetValue<string>() == "waiting") view = Read(session);
            check(view["accepted"]!.GetValue<int>() == 3 && view["reconciled"]!.GetValue<int>() == 3 && !view["parent_pending"]!.GetValue<bool>(),
                "confirmed child disposal precedes combat parent reconciliation");
        }
        {
            var native = new Native { BeforeChoiceWaits = 3, AfterChoiceWaits = 3 };
            using var session = new AgentSession(new Reader(), native.Handle, "nonce");
            var view = Read(session); Act(session, view);
            for (int i = 0; i < 3; i++)
            {
                view = Read(session);
                check(view["status"]!.GetValue<string>() == "waiting" && view["parent_pending"]!.GetValue<bool>() &&
                    view["reconciled"]!.GetValue<int>() == 0 && native.Posts == 1, "delayed selector retains exact combat parent");
            }
            view = Read(session); Act(session, view); view = Read(session); Act(session, view);
            for (int i = 0; i < 3; i++)
            {
                view = Read(session);
                check(view["status"]!.GetValue<string>() == "waiting" && view["parent_pending"]!.GetValue<bool>() &&
                    !view["child_pending"]!.GetValue<bool>() && view["reconciled"]!.GetValue<int>() == 2,
                    "completed child does not release delayed parent continuation");
            }
            view = Read(session);
            if (view["status"]!.GetValue<string>() == "waiting") view = Read(session);
            check(view["status"]!.GetValue<string>() == "ready" && view["reconciled"]!.GetValue<int>() == 3 &&
                !view["parent_pending"]!.GetValue<bool>() && native.Posts == 3, "only native parent completion releases the next combat decision");
        }
        foreach (string failure in new[] { "stale", "uncertain", "unsupported", "cleanup" })
        {
            var native = new Native(); var reader = new Reader(); using var session = new AgentSession(reader, native.Handle, "nonce");
            var view = Read(session);
            if (failure == "stale") { native.Stale = true; check(Act(session, view).StaleWithoutMutation, "confirmed native stale permits reobserve"); }
            if (failure == "uncertain") { native.Uncertain = true; check(Act(session, view).Terminal && Read(session)["status"]!.GetValue<string>() == "failed", "uncertain dispatch cannot restart"); }
            if (failure == "unsupported") { reader.Unsupported = true; check(Act(session, view).Body.Length > 0 && native.Posts == 0, "missing public fields cannot dispatch"); }
            if (failure == "cleanup")
            {
                Act(session, view); view = Read(session); Act(session, view, 1); native.CleanupFailure = true;
                // The zero-selection confirm closes at fixture stage three.
                native.Step = 3;
                check(Read(session)["status"]!.GetValue<string>() == "failed", "failed child cleanup never becomes clean handoff");
            }
        }
        {
            var reader = new Reader { FailDispose = true }; var session = new AgentSession(reader, new Native().Handle, "nonce");
            bool threw = false; try { session.Dispose(); } catch { threw = true; }
            check(threw, "observer cleanup failure propagates to host");
        }
        check(AgentSession.IsAction(new string('a', 64), "action:0") && !AgentSession.IsAction(new string('a', 64), "action:00") &&
            !AgentSession.IsAction(new string('a', 64), "action:512"), "agent action grammar bounded and canonical");
    }
}
