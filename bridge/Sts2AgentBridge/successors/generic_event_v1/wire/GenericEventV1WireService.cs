using System;
using System.Collections.Generic;
using System.Diagnostics.CodeAnalysis;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;

namespace Sts2AgentBridge.Successors.GenericEventV1;

// One owner-frame route pair. The caller owns request and returned buffers.
public sealed class GenericEventV1WireService : IDisposable
{
    public const string DecisionRoute = "/probe/generic-event-v1/public/decision";
    public const string ActionRoute = "/probe/generic-event-v1/public/action";
    private readonly object _gate = new();
    private readonly IGenericEventV1Session _session;
    private readonly string _nonce;
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private readonly HashSet<string> _used = new(StringComparer.Ordinal);
    private readonly List<(string Decision, string Action)> _childAccepted = new();
    private string? _decision, _lastParentDecision, _lastParentAction;
    private string[] _legal = Array.Empty<string>();
    private GenericEventV1Child? _child;
    private GenericEventV1Observation? _previous;
    private CardSelectionV1Candidate[]? _domain;
    private bool _inside, _interfered, _disposed, _childResolved;
    private string? _failure;
    private int _reads, _attempts, _parentAttempts, _ordinal, _history;

    public GenericEventV1WireService(string nonce, IGenericEventV1Session session)
    {
        Require(Hex(nonce, 32));
        _nonce = nonce;
        _session = session ?? throw new ArgumentNullException(nameof(session));
    }

    public byte[] Handle(string? method, string? route, byte[]? body)
    {
        lock (_gate) return HandleCore(method, route, body);
    }

    private byte[] HandleCore(string? method, string? route, byte[]? body)
    {
        if (_inside) { _interfered = true; return Error("internal_failure"); }
        if (_failure is not null) return Error(_failure);
        if (_disposed || Environment.CurrentManagedThreadId != _owner) return Fail("internal_failure");
        _inside = true;
        byte[]? result = null;
        try
        {
            if (method == "GET" && route == DecisionRoute && body is null)
            {
                if (++_reads > 2048) return Fail("invalid_request");
                result = Read();
            }
            else if (method == "POST" && route == ActionRoute && body is { Length: > 0 and <= 4096 })
            {
                ActionRequest request;
                try { request = Parse(body); }
                catch { return Fail("invalid_request"); }
                result = Apply(request);
            }
            else return Fail("invalid_request");
            if (_interfered || _disposed) { Array.Clear(result); return Fail("internal_failure"); }
            byte[] transfer = result; result = null; return transfer;
        }
        catch { return Fail("internal_failure"); }
        finally { if (result is not null) Array.Clear(result); _inside = false; }
    }

    private byte[] Read()
    {
        _decision = null; _legal = Array.Empty<string>();
        GenericEventV1Observation parent = _session.Read();
        ValidateParent(parent);
        byte[]? payload = null;
        try
        {
            if (parent.Child is GenericEventV1Child child)
            {
                Require(parent.Status == "child" && !_childResolved);
                Require(child.ParentDecisionId == _lastParentDecision && child.ParentActionId == _lastParentAction);
                ValidateDescriptor(child);
                if (_child is null)
                {
                    Require(child.Ordinal == _ordinal + 1);
                    _child = child; _ordinal = child.Ordinal;
                    _domain = null; _childAccepted.Clear(); _history = 0;
                }
                else Require(SameChild(child, _child));
                object value = _session.ReadChild(child.ParentDecisionId, child.ParentActionId, child.Ordinal);
                ValidateChild(value);
                payload = CardSelectionV1WireCodec.Encode(value);
            }
            else
            {
                if (_child is not null)
                {
                    Require(_childResolved || parent.Status == "unsupported");
                    _child = null; _childResolved = false; _domain = null;
                }
                if (parent.Status == "ready") Publish(parent.DecisionId, parent.LegalActions);
            }
            return GenericEventV1WireCodec.Decision(_nonce, parent, payload);
        }
        finally { if (payload is not null) Array.Clear(payload); }
    }

    private byte[] Apply(ActionRequest request)
    {
        Require(_decision is not null && request.Decision == _decision &&
            _legal.Contains(request.Action, StringComparer.Ordinal) && _used.Add(request.Decision));
        Require(_attempts < 52 && (_child is not null || _parentAttempts < 12));
        _decision = null; _legal = Array.Empty<string>(); _attempts++;
        if (_child is null)
        {
            Require(request.Ordinal == 0);
            _parentAttempts++;
            GenericEventV1ApplyResult result = _session.Apply(request.Decision, request.Action);
            Require(result.Version == GenericEventV1Limits.Version && result.SessionNonce == _nonce &&
                result.DecisionId == request.Decision && result.ActionId == request.Action &&
                result.Outcome is "accepted" or "unsupported" or "stale_decision" or "illegal_action" or "uncertain" or "budget_exhausted");
            if (result.Outcome == "accepted")
            { _lastParentDecision = result.DecisionId; _lastParentAction = result.ActionId; }
            else _failure = "unsupported";
            return GenericEventV1WireCodec.Action(_nonce, null, result, null);
        }
        Require(!_childResolved && request.Ordinal == _child.Ordinal &&
            request.ParentDecision == _child.ParentDecisionId && request.ParentAction == _child.ParentActionId &&
            _childAccepted.Count < 10);
        object childResult = _session.ApplyChild(request.ParentDecision, request.ParentAction,
            request.Ordinal, request.Decision, request.Action);
        if (childResult is CardSelectionV1DispatchReceipt receipt)
        {
            Require(receipt.SessionNonce == _nonce && receipt.DecisionId == request.Decision &&
                receipt.ActionId == request.Action && receipt.Outcome == "accepted");
            _childAccepted.Add((request.Decision, request.Action));
        }
        else if (childResult is CardSelectionV1ApplyFailure failure)
        {
            Require(failure.SessionNonce == _nonce && failure.Outcome is "unsupported" or "uncertain" or "rejected");
            _failure = "unsupported";
        }
        else throw new InvalidOperationException();
        byte[] bytes = CardSelectionV1WireCodec.Encode(childResult);
        try { return GenericEventV1WireCodec.Action(_nonce, _child, null, bytes); }
        finally { Array.Clear(bytes); }
    }

    private ActionRequest Parse(byte[] body)
    {
        using JsonDocument document = JsonDocument.Parse(body, new JsonDocumentOptions { MaxDepth = 4 });
        JsonElement root = document.RootElement;
        Keys(root, "decision_id", "action_id", "child");
        string decision = root.GetProperty("decision_id").GetString()!;
        string action = root.GetProperty("action_id").GetString()!;
        Require(Hex(decision, 64) && action is { Length: > 0 and <= 16 });
        JsonElement child = root.GetProperty("child");
        var request = new ActionRequest(decision, action, 0, null, null);
        if (child.ValueKind != JsonValueKind.Null)
        {
            Keys(child, "ordinal", "parent_decision_id", "parent_action_id");
            Require(child.GetProperty("ordinal").TryGetInt32(out int ordinal) && ordinal is >= 1 and <= 4);
            string pd = child.GetProperty("parent_decision_id").GetString()!;
            string pa = child.GetProperty("parent_action_id").GetString()!;
            Require(Hex(pd, 64) && ParentAction(pa));
            request = new ActionRequest(decision, action, ordinal, pd, pa);
        }
        Require((_child is null && request.Ordinal == 0 && ParentAction(action)) ||
            (_child is not null && request.Ordinal == _child.Ordinal &&
             request.ParentDecision == _child.ParentDecisionId && request.ParentAction == _child.ParentActionId &&
             CardSelectionV1WireProtocol.IsChildAction(action)));
        // Exact canonical requests have no text-bearing fields or alternative JSON encodings.
        byte[] canonical = GenericEventV1WireCodec.Request(request.Decision, request.Action,
            request.Ordinal, request.ParentDecision, request.ParentAction);
        try { Require(body.AsSpan().SequenceEqual(canonical)); }
        finally { Array.Clear(canonical); }
        return request;
    }

    private void ValidateParent(GenericEventV1Observation p)
    {
        Require(p.Version == GenericEventV1Limits.Version && p.SessionNonce == _nonce);
        Require((p.Status, p.Phase) is ("ready", "choose_option") or ("ready", "proceed") or
            ("waiting", "waiting") or ("child", "child") or ("complete", "map_handoff") or
            ("unsupported", "unsupported"));
        Require(p.ParentAttempted >= 0 && p.ParentAttempted <= _parentAttempts &&
            p.ParentReconciled >= 0 && p.ParentReconciled <= p.ParentAccepted &&
            p.ParentAccepted <= p.ParentAttempted && p.ChildEpisodes is >= 0 and <= 4 &&
            p.ChildReconciled >= 0 && p.ChildReconciled <= p.ChildAccepted &&
            p.ChildAccepted <= p.ChildAttempted && p.ChildAttempted >= 0 &&
            p.TotalAttempted <= _attempts && p.Effects is "none_attempted" or "unverified" or "card_effect_verified");
        Require((p.Status == "child") == (p.Child is not null));
        Require(p.PriorResults.Count == p.ParentReconciled && p.PriorResults.Count <= 12);
        foreach (GenericEventV1PriorResult r in p.PriorResults)
            Require(Hex(r.DecisionId, 64) && ParentAction(r.ActionId) &&
                r.Result is "option_transition" or "child_completed" or "map_handoff");
        if (_previous is not null)
        {
            Require(p.ParentAttempted >= _previous.ParentAttempted && p.ParentAccepted >= _previous.ParentAccepted &&
                p.ParentReconciled >= _previous.ParentReconciled && p.ChildEpisodes >= _previous.ChildEpisodes &&
                p.ChildAttempted >= _previous.ChildAttempted && p.ChildAccepted >= _previous.ChildAccepted &&
                p.ChildReconciled >= _previous.ChildReconciled);
            for (int i = 0; i < _previous.PriorResults.Count; i++)
            {
                var a = _previous.PriorResults[i]; var b = p.PriorResults[i];
                Require(a.DecisionId == b.DecisionId && a.ActionId == b.ActionId && a.Result == b.Result);
            }
        }
        if (p.Status == "ready")
        {
            Require(Hex(p.DecisionId, 64) && p.Candidates.Count is >= 1 and <= 8 && p.LegalActions.Count > 0);
            var keys = new HashSet<string>(StringComparer.Ordinal);
            foreach (GenericEventV1Candidate c in p.Candidates)
                Require(c.Index >= 0 && c.Index < p.Candidates.Count && ReferenceEquals(c, p.Candidates[c.Index]) &&
                    c.ActionId == "choose:" + c.Index && c.StableId is { Length: > 0 and <= 96 } && keys.Add(c.StableId) &&
                    c.RenderedText is { Length: > 0 and <= 1024 } && c.Discovery == (c.IsProceed ? "none" : "deferred"));
            Require(p.LegalActions.Distinct().Count() == p.LegalActions.Count &&
                p.LegalActions.All(a => p.Candidates.Any(c => c.ActionId == a && c.Enabled && !c.IsDangerous)));
            Require(p.Phase == "proceed" ? p.Candidates.Count == 1 && p.Candidates[0].IsProceed :
                p.Candidates.All(c => !c.IsProceed));
        }
        else Require(p.DecisionId == "" && p.Candidates.Count == 0 && p.LegalActions.Count == 0);
        if (p.Status == "complete") Require(p.PriorResults.Count > 0 && p.PriorResults[^1].Result == "map_handoff");
        _previous = p;
    }

    private void ValidateChild(object value)
    {
        Require(_child is not null);
        if (value is CardSelectionV1Observation p)
        {
            Require(p.Version == "card_selection_v1" && p.SessionNonce == _nonce && p.ParentOrdinal == 1 &&
                p.Status is "ready" or "waiting" or "unsupported");
            ValidateHistory(p.PriorResults);
            if (p.Status == "ready")
            {
                Require(p.Operation == "upgrade" && p.MinSelect == 1 && p.MaxSelect == 1 &&
                    p.CommitMode == "preview_confirm" && p.Candidates.Count == _child!.DomainCount);
                if (_domain is null) _domain = p.Candidates.ToArray();
                for (int i = 0; i < _domain.Length; i++)
                {
                    var a = _domain[i]; var b = p.Candidates[i];
                    Require(a.Slot == i && b.Slot == i && a.Key == b.Key && a.UpgradeLevel == b.UpgradeLevel);
                }
                Publish(p.DecisionId, p.LegalActions);
            }
            else Require(p.DecisionId == "" && p.LegalActions.Count == 0);
        }
        else if (value is CardSelectionV1ResolvedResult done)
        {
            Require(done.SessionNonce == _nonce && done.Operation == "upgrade" && _domain is not null &&
                done.SelectedCards.Count == 1 && done.PriorResults.Count == _childAccepted.Count &&
                _childAccepted.Count > 0);
            ValidateHistory(done.PriorResults);
            var selected = done.SelectedCards[0];
            Require(selected.Slot >= 0 && selected.Slot < _domain!.Length &&
                selected.Key == _domain[selected.Slot].Key && selected.UpgradeLevel == _domain[selected.Slot].UpgradeLevel &&
                selected.Selected && _childAccepted.Any(a => a.Action == "select:" + selected.Slot) &&
                _childAccepted[^1].Action == "confirm");
            _childResolved = true;
        }
        else throw new InvalidOperationException();
    }

    private void ValidateHistory(IReadOnlyList<CardSelectionV1ActionResult> results)
    {
        Require(results.Count >= _history && results.Count <= _childAccepted.Count);
        for (int i = 0; i < results.Count; i++)
        {
            Require(results[i].DecisionId == _childAccepted[i].Decision && results[i].ActionId == _childAccepted[i].Action &&
                results[i].Result == (_childAccepted[i].Action.StartsWith("select:", StringComparison.Ordinal) ? "selected" : _childAccepted[i].Action == "preview" ? "previewed" : "committed"));
        }
        _history = results.Count;
    }

    private void Publish(string decision, IReadOnlyList<string> legal)
    {
        Require(Hex(decision, 64) && !_used.Contains(decision) && legal.Count is > 0 and <= 66);
        _decision = decision; _legal = legal.ToArray();
    }
    private static void ValidateDescriptor(GenericEventV1Child c) => Require(c.Ordinal is >= 1 and <= 4 &&
        Hex(c.ParentDecisionId, 64) && ParentAction(c.ParentActionId) && c.Operation == "upgrade" &&
        c.MinSelect == 1 && c.MaxSelect == 1 && c.CommitMode == "preview_confirm" && c.DomainCount is >= 2 and <= 64);
    private static bool SameChild(GenericEventV1Child a, GenericEventV1Child b) => a.Ordinal == b.Ordinal &&
        a.ParentDecisionId == b.ParentDecisionId && a.ParentActionId == b.ParentActionId && a.Operation == b.Operation &&
        a.MinSelect == b.MinSelect && a.MaxSelect == b.MaxSelect && a.CommitMode == b.CommitMode && a.DomainCount == b.DomainCount;
    private static bool ParentAction(string? s) => s is { Length: 8 } && s.StartsWith("choose:", StringComparison.Ordinal) && s[7] is >= '0' and <= '7';
    private static bool Hex(string? s, int n) => s is not null && s.Length == n && s.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');
    private static void Keys(JsonElement x, params string[] keys) => Require(x.ValueKind == JsonValueKind.Object && x.EnumerateObject().Select(p => p.Name).SequenceEqual(keys));
    private static void Require([DoesNotReturnIf(false)] bool condition) { if (!condition) throw new InvalidOperationException("Invalid generic-event value."); }
    private byte[] Fail(string code) { _failure = code; _decision = null; _legal = Array.Empty<string>(); return Error(code); }
    private byte[] Error(string code) => GenericEventV1WireCodec.Error(_nonce, code);
    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed) return;
            Require(Environment.CurrentManagedThreadId == _owner);
            _failure = "unsupported"; _decision = null; _legal = Array.Empty<string>();
            if (_inside) { _interfered = true; throw new InvalidOperationException("Reentrant disposal."); }
            _session.Dispose();
            _disposed = true;
        }
    }
    private sealed record ActionRequest(string Decision, string Action, int Ordinal, string? ParentDecision, string? ParentAction);
}
