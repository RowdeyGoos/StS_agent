using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Sts2AgentBridge.Unified;

// One policy boundary for every family. Existing native modules retain all
// action execution, parent/child ownership, reconciliation and cleanup.
internal sealed class FullAgentSession : IDisposable
{
    private readonly IFullAgentBackend _backend;
    private readonly string _nonce;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private readonly Dictionary<FullCompletion, JsonObject> _pending = new();
    private readonly HashSet<FullCompletion> _settled = new();
    private FullCapture? _capture;
    private string? _decision, _outcome;
    private int _reads, _attempted, _accepted, _reconciled, _revision;
    private bool _failed, _disposed, _started, _inside;
    internal bool Active => _started;
    internal FullAgentSession(IFullAgentBackend backend, string nonce) { _backend = backend; _nonce = nonce; }

    internal ModuleReply Handle(BridgeRequest request)
    {
        if (_inside || _failed || _disposed || Environment.CurrentManagedThreadId != _thread) return Stop("agent_stopped");
        _inside = true; _started = true;
        try { return request.IsPost ? Apply(request) : Read(); }
        catch (FullReadFailure error) { return Stop(error.Code); }
        catch (AgentUnsupported) { return Stop("unsupported_public_surface"); }
        catch { return Stop("agent_boundary_failed"); }
        finally { _inside = false; }
    }

    private ModuleReply Read()
    {
        if (++_reads > FullAgentRoutes.MaximumReads) return Stop("read_limit");
        if (_outcome is not null) return Reply("complete", outcome: _outcome);
        var fresh = _backend.Read();
        foreach (var completion in fresh.Completed)
        {
            if (_settled.Contains(completion)) continue; // Native receipts remain visible until the next accepted action.
            if (!_pending.Remove(completion)) return Stop("unowned_completion");
            _settled.Add(completion); _reconciled++;
        }
        if (fresh.Status == "waiting")
        { _capture = null; _decision = null; return Reply("waiting"); }
        if (fresh.Status == "complete")
        {
            if (_pending.Count != 0 || fresh.Outcome is not ("victory" or "defeat" or "run_abandoned")) return Stop("incomplete_run");
            _capture = null; _decision = null; _outcome = fresh.Outcome; return Reply("complete", outcome: _outcome);
        }
        if (fresh.Status != "ready" || fresh.Observation is null || fresh.Commands.Length is < 1 or > FullAgentRoutes.MaximumCandidates)
            return Stop(fresh.Code ?? "unsupported_public_surface");
        FullReadFailure.At(FullReadStage.Graph, () => { FullPublicGraph.Validate(fresh.Observation); return true; });
        // The native backend builds this graph from explicit public fields in
        // the same owner frame as the existing command observation.
        var candidates = fresh.Observation["candidates"]?.AsArray();
        if (fresh.Observation["schema"]?.GetValue<string>() != "sts_public_decision_v2" ||
            fresh.Observation["profile"]?.GetValue<string>() != "full_run_v2" ||
            candidates is null || candidates.Count != fresh.Commands.Length) return Stop("invalid_public_graph");
        for (int i = 0; i < fresh.Commands.Length; i++)
            if (fresh.Commands[i].Candidate["ref"]?.GetValue<string>() != "action:" + i ||
                !JsonNode.DeepEquals(candidates[i], fresh.Commands[i].Candidate)) return Stop("candidate_binding");
        bool same = _capture is not null && JsonNode.DeepEquals(_capture.Observation, fresh.Observation) &&
            _capture.Bindings.Length == fresh.Bindings.Length && _capture.Bindings.Zip(fresh.Bindings).All(p => ReferenceEquals(p.First, p.Second)) &&
            _capture.Commands.Select(c => c.Request).SequenceEqual(fresh.Commands.Select(c => c.Request));
        if (!same) _decision = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(_nonce + ":full:" + ++_revision))).ToLowerInvariant();
        _capture = fresh;
        return Reply("ready", observation: fresh.Observation);
    }

    private ModuleReply Apply(BridgeRequest request)
    {
        var saved = _capture; string? token = _decision;
        if (saved is null || request.Decision != token || !FullAgentRoutes.IsAction(request.Decision, request.Action)) return Stale(request);
        int slot = int.Parse(request.Action![7..]);
        if (slot >= saved.Commands.Length) return Stop("invalid_action");
        var checkedRead = Read();
        try
        {
            if (checkedRead.Terminal) return checkedRead;
            if (_capture is null || _decision != token) return Stale(request);
        }
        finally { if (!checkedRead.Terminal) Array.Clear(checkedRead.Body); }
        if (++_attempted > FullAgentRoutes.MaximumActions) return Stop("action_limit");
        var command = saved.Commands[slot];
        var key = FullCompletion.For(command.Request);
        if (_pending.ContainsKey(key) || _settled.Contains(key)) return Stop("duplicate_native_action");
        // Invalidate before crossing the mutation boundary. There is never a
        // second dispatch after an unknown receipt or exception.
        _capture = null; _decision = null;
        var receipt = _backend.Apply(command.Request);
        try
        {
            if (receipt.StaleWithoutMutation) return Stale(request);
            if (receipt.Terminal) return Stop("uncertain_dispatch");
            using var parsed = JsonDocument.Parse(receipt.Body);
            var root = parsed.RootElement;
            if (!root.TryGetProperty("status", out var status) || status.GetString() != "accepted" ||
                root.GetProperty("decision_id").GetString() != command.Request.Decision ||
                root.GetProperty("action_id").GetString() != command.Request.Action) return Stop("uncertain_dispatch");
            _pending.Add(key, (JsonObject)command.Candidate.DeepClone()); _accepted++;
            return Reply("accepted", action: request.Action, receiptDecision: request.Decision);
        }
        finally { Array.Clear(receipt.Body); }
    }

    private ModuleReply Reply(string status, JsonObject? observation = null, string? action = null,
        string? receiptDecision = null, string? outcome = null, string? code = null)
    {
        var bytes = JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 2, protocol = "agent_v2", status,
            decision_id = receiptDecision ?? _decision, action_id = action, observation, outcome, code,
            attempted = _attempted, accepted = _accepted, reconciled = _reconciled, pending = _pending.Count });
        if (bytes.Length > FullAgentRoutes.MaximumBody) { Array.Clear(bytes); return Stop("public_capacity"); }
        return new(bytes, Terminal: _failed);
    }
    private ModuleReply Stale(BridgeRequest request) => new(JsonSerializer.SerializeToUtf8Bytes(new {
        schema_version = 2, protocol = "agent_v2", status = "rejected", reason = "stale_decision", mutation_state = "none",
        decision_id = request.Decision, action_id = request.Action, attempted = _attempted, accepted = _accepted,
        reconciled = _reconciled, pending = _pending.Count }), StaleWithoutMutation: true);
    private ModuleReply Stop(string code)
    { _failed = true; _capture = null; _decision = null; return Reply("failed", code: code); }
    public void Dispose()
    {
        if (_disposed) return;
        _failed = true;
        _backend.Dispose();
        if (_pending.Count != 0) throw new InvalidOperationException("Unreconciled shared action.");
        _disposed = true;
    }
}
