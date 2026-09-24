using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Cards.Combat;

namespace Sts2AgentBridge.Unified;

// This coordinator uses the core's existing native services. It neither queues
// game actions nor clicks native widgets itself. The core continues to own a
// combat action while this session services its nested chooser.
internal sealed class AgentSession : IDisposable
{
    internal const string DecisionRoute = "/probe/agent-v1/public/decision";
    internal const string ActionRoute = "/probe/agent-v1/public/action";
    private readonly IAgentPublicReader _reader;
    private readonly Func<BridgeRequest, ModuleReply> _legacy;
    private readonly string _nonce;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private readonly JsonArray _history = new();
    private string? _family, _decision, _legacyDecision, _source;
    private AgentCapture? _capture;
    private Pending? _pending, _child;
    private bool _choice, _failed, _disposed, _done;
    private string _outcome = "slice_complete";
    private int _revision, _reads, _attempted, _accepted, _reconciled;
    private sealed record Pending(string Decision, JsonObject Candidate, string[] Skipped)
    { internal bool Observed; }
    internal bool Active => _family is not null && !_done || _failed;

    internal AgentSession(IAgentPublicReader reader, Func<BridgeRequest, ModuleReply> legacy, string nonce)
    { _reader = reader; _legacy = legacy; _nonce = nonce; }

    internal static bool IsAction(string? decision, string? action) =>
        decision is { Length: 64 } && decision.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f') &&
        action?.StartsWith("action:", StringComparison.Ordinal) == true &&
        int.TryParse(action[7..], out int slot) && slot is >= 0 and < 512 && action == "action:" + slot;

    private static string Route(string family, bool post = false) => family == "choice"
        ? post ? CombatCardChoiceService.ActionRoute : CombatCardChoiceService.DecisionRoute
        : "/probe/v0/public/" + family + (post ? "-action" : "-decision");

    internal ModuleReply Handle(BridgeRequest request)
    {
        if (_failed || _disposed || Environment.CurrentManagedThreadId != _thread) return Stop("agent_stopped");
        try { return request.IsPost ? Apply(request) : Read(); }
        catch (AgentUnsupported) { _capture = null; _decision = null; return Reply("unsupported", code: "missing_public_fields"); }
        catch { return Stop("agent_observation_failed"); }
    }

    private ModuleReply Read()
    {
        if (++_reads > 4096) return Stop("read_limit");
        if (_done) return Reply("complete", outcome: _outcome);
        _family ??= _reader.InitialFamily();
        // At most one combat -> rewards -> map transition in an owner frame.
        for (int transitions = 0; transitions < 4; transitions++)
        {
            string family = _choice ? "choice" : _family;
            ModuleReply reply = _legacy(new(Capability.Core, Route(family), false, 0, 0));
            try
            {
                if (reply.Terminal) return Stop("native_failure");
                using var parsed = JsonDocument.Parse(reply.Body);
                var root = parsed.RootElement;
                // Reject newer semantics before reconciling any pending action.
                if (family == "combat" && root.GetProperty("schema_version").GetInt32() != 1 ||
                    family == "reward" && root.GetProperty("schema_version").GetInt32() >= 9)
                    throw new AgentUnsupported();
                string? status = root.GetProperty("status").GetString();
                if (status == "waiting")
                {
                    if (family == "combat")
                    {
                        ModuleReply child = _legacy(new(Capability.Core, Route("choice"), false, 0, 0));
                        try
                        {
                            if (child.Terminal) return Stop("native_failure");
                            using var childJson = JsonDocument.Parse(child.Body);
                            if (childJson.RootElement.GetProperty("status").GetString() == "ready")
                            {
                                // A nested selection must belong to our accepted play.
                                if (_pending?.Candidate["kind"]?.GetValue<string>() != "play_card")
                                    throw new AgentUnsupported();
                                _choice = true;
                                _source = _pending.Candidate["subject"]?.GetValue<string>();
                                Record(_pending);
                                return Ready("choice", childJson.RootElement);
                            }
                        }
                        finally { Array.Clear(child.Body); }
                    }
                    _capture = null; _decision = null;
                    return Reply("waiting");
                }
                if (status == "complete")
                {
                    if (family == "choice")
                    {
                        if (_child is null || root.GetProperty("result").GetString() != "selection_verified")
                            return Stop("choice_completion");
                        Reconcile(ref _child); _choice = false; _source = null;
                        continue;
                    }
                    Reconcile(ref _pending);
                    if (family == "combat")
                    {
                        string? outcome = root.GetProperty("outcome").GetString();
                        if (outcome == "defeat") { _done = true; _outcome = "defeat"; return Reply("complete", outcome: _outcome); }
                        if (outcome != "victory") return Stop("combat_outcome");
                        _history.Add(Event("combat_ended", null, null));
                        _family = "reward";
                    }
                    else if (family == "reward") _family = "map";
                    else { _done = true; return Reply("complete", outcome: "slice_complete"); }
                    continue;
                }
                if (status != "ready") throw new AgentUnsupported();
                string id = root.GetProperty("decision_id").GetString()!;
                Pending? pending = family == "choice" ? _child : _pending;
                if (pending is not null)
                {
                    if (pending.Decision == id) return Reply("waiting");
                    if (family == "choice") Reconcile(ref _child); else Reconcile(ref _pending);
                }
                return Ready(family, root);
            }
            finally { Array.Clear(reply.Body); }
        }
        return Stop("transition_limit");
    }

    private ModuleReply Ready(string family, JsonElement legacy)
    {
        AgentCapture fresh = _reader.Capture(family, legacy, _history, _source);
        if (fresh.Commands.Length is < 1 or > 512) throw new AgentUnsupported();
        string id = legacy.GetProperty("decision_id").GetString()!;
        bool same = _capture is not null && _legacyDecision == id &&
            JsonNode.DeepEquals(_capture.Observation, fresh.Observation) &&
            _capture.Bindings.Length == fresh.Bindings.Length &&
            _capture.Bindings.Zip(fresh.Bindings).All(x => ReferenceEquals(x.First, x.Second)) &&
            _capture.Commands.Select(c => c.Action).SequenceEqual(fresh.Commands.Select(c => c.Action));
        if (!same)
            _decision = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(_nonce + ":agent:" + ++_revision))).ToLowerInvariant();
        _capture = fresh; _legacyDecision = id;
        return Reply("ready", observation: fresh.Observation);
    }

    private ModuleReply Apply(BridgeRequest request)
    {
        AgentCapture? saved = _capture;
        string? savedDecision = _decision;
        if (saved is null || request.Decision != savedDecision || !IsAction(request.Decision, request.Action))
            return Stale(request);
        int slot = int.Parse(request.Action![7..]);
        if (slot >= saved.Commands.Length) return Stop("invalid_action");
        ModuleReply fresh = Read();
        try
        {
            if (fresh.Terminal) return fresh;
            using var parsed = JsonDocument.Parse(fresh.Body);
            if (parsed.RootElement.GetProperty("status").GetString() != "ready" || _decision != savedDecision)
                return Stale(request);
        }
        finally { if (!fresh.Terminal) Array.Clear(fresh.Body); }
        if (++_attempted > 512) return Stop("action_limit");
        string family = _choice ? "choice" : _family!;
        AgentCommand command = saved.Commands[slot];
        ModuleReply receipt = _legacy(new(Capability.Core, Route(family, true), true, 0, 0, _legacyDecision, command.Action));
        _capture = null; _decision = null;
        try
        {
            if (receipt.StaleWithoutMutation) return Stale(request);
            if (receipt.Terminal) return Stop("uncertain_dispatch");
            using var parsed = JsonDocument.Parse(receipt.Body);
            if (parsed.RootElement.GetProperty("status").GetString() != "accepted") return Stop("uncertain_dispatch");
            string[] skipped = command.Candidate["kind"]?.GetValue<string>() == "leave_rewards"
                ? saved.Observation["context"]!["entries"]!.AsArray().Where(r => !r!["resolved"]!.GetValue<bool>()).Select(r => r!["ref"]!.GetValue<string>()).ToArray()
                : Array.Empty<string>();
            var pending = new Pending(_legacyDecision!, (JsonObject)command.Candidate.DeepClone(), skipped);
            if (_choice) _child = pending; else _pending = pending;
            _accepted++;
            return Reply("accepted", action: request.Action, receiptDecision: request.Decision);
        }
        finally { Array.Clear(receipt.Body); }
    }

    private void Reconcile(ref Pending? pending)
    {
        if (pending is null) return;
        Record(pending);
        _reconciled++; pending = null;
    }
    private void Record(Pending pending)
    {
        if (pending.Observed) return;
        pending.Observed = true;
        foreach (var reward in pending.Skipped) _history.Add(Event("reward_skipped", reward, null));
        JsonObject c = pending.Candidate;
        string kind = c["kind"]!.GetValue<string>();
        string eventKind = kind switch {
            "play_card" => "card_played", "end_turn" => "end_turn",
            "select_card" or "deselect_card" => "card_selected", "confirm_selection" => "selection_confirmed",
            "open_card_reward" => "reward_opened", "claim_reward" or "choose_reward_card" => "reward_claimed",
            "skip_reward" => "reward_skipped", "choose_map_node" => "map_selected", _ => "" };
        if (eventKind.Length != 0)
        {
            var entry = Event(eventKind, c["subject"]?.GetValue<string>(), c["target"]?.GetValue<string>());
            if (kind is "select_card" or "deselect_card")
                entry["values"] = new JsonArray(new JsonObject { ["key"] = "selected", ["amount"] = kind == "select_card" ? 1 : 0 });
            _history.Add(entry);
        }
    }
    private static JsonObject Event(string kind, string? subject, string? target) => new() {
        ["kind"] = kind, ["subject"] = Observed(subject), ["target"] = Observed(target), ["values"] = new JsonArray() };
    private static JsonObject Observed(string? value) => new() { ["status"] = value is null ? "not_applicable" : "known", ["value"] = value };
    private ModuleReply Stale(BridgeRequest request) => new(JsonSerializer.SerializeToUtf8Bytes(new {
        schema_version = 1, protocol = "agent_v1", status = "rejected", mutation_state = "none", reason = "stale_decision",
        decision_id = request.Decision, action_id = request.Action, attempted = _attempted, accepted = _accepted, reconciled = _reconciled
    }), StaleWithoutMutation: true);
    private ModuleReply Reply(string status, JsonObject? observation = null, string? code = null, string? outcome = null,
        string? action = null, string? receiptDecision = null) => new(JsonSerializer.SerializeToUtf8Bytes(new {
            schema_version = 1, protocol = "agent_v1", status, decision_id = receiptDecision ?? (status == "ready" ? _decision : null),
            action_id = action, observation, code, outcome, attempted = _attempted, accepted = _accepted, reconciled = _reconciled,
            parent_pending = _pending is not null, child_pending = _child is not null }));
    private ModuleReply Stop(string code) { _failed = true; return Reply("failed", code: code) with { Terminal = true }; }
    public void Dispose() { _reader.Dispose(); _disposed = true; }
}
