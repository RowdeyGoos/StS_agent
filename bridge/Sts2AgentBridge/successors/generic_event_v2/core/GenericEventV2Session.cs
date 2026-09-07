using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV2;

public sealed class GenericEventV2Session : IGenericEventV2Session
{
    private readonly IGenericEventV2NativeAdapter _native;
    private readonly string _nonce;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private readonly HashSet<string> _seenStructures = new(StringComparer.Ordinal);
    private string _lastStructure = "";
    private readonly HashSet<string> _chosen = new(StringComparer.Ordinal);
    private readonly HashSet<object> _screens = new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _admissions = new(ReferenceEqualityComparer.Instance);
    private readonly List<GenericEventV2PriorResult> _history = new();
    private GenericEventV2NativeCapture? _published;
    private string _decision = "";
    private string _pendingDecision = "", _pendingAction = "", _pendingStamp = "";
    private bool _pending, _proceed, _unsupported, _complete, _inside, _disposed;
    private int _attempted, _accepted, _reconciled, _episodes, _childAttempted, _childAccepted, _childReconciled, _pendingReads, _reads;
    private CardSelectionV1Session? _card;
    private GenericEventV2Child? _child;
    private bool _resolvedDelivered;
    private string _effects = "none_attempted";

    public GenericEventV2Session(IGenericEventV2NativeAdapter adapter, string sessionNonce)
    {
        _native = adapter ?? throw new ArgumentNullException(nameof(adapter));
        if (sessionNonce.Length != 32 || sessionNonce.Any(c => !(c is >= '0' and <= '9' or >= 'a' and <= 'f')))
            throw new ArgumentException("Expected a 32-digit session nonce.", nameof(sessionNonce));
        _nonce = sessionNonce;
    }
    private bool Enter()
    {
        if (_inside || Environment.CurrentManagedThreadId != _thread || _disposed)
        { _unsupported = true; return false; }
        _inside = true; return true;
    }
    public GenericEventV2Observation Read()
    {
        if (!Enter()) return Observation("unsupported", "unsupported");
        try { return ReadCore(); }
        catch { _unsupported = true; return Observation("unsupported", "unsupported"); }
        finally { _inside = false; }
    }
    private GenericEventV2Observation ReadCore()
    {
        if (++_reads > GenericEventV2Limits.MaximumHostReads) _unsupported = true;
        if (_unsupported) return Observation("unsupported", "unsupported");
        if (_complete) return Observation("complete", "map_handoff");
        if (_card is not null)
        {
            if (!_resolvedDelivered) return Observation("child", "child");
            _card.Dispose(); _card = null; _child = null;
            _effects = "card_effect_verified";
            Reconcile("child_completed");
        }
        GenericEventV2NativeCapture capture = _native.Capture();
        if (_unsupported || capture.Status == "unsupported") return Stop();
        if (_pending)
        {
            if (++_pendingReads > GenericEventV2Limits.MaximumPendingReads) return Stop();
            if (capture.Status == "child")
            {
                if (_proceed || _episodes >= GenericEventV2Limits.MaximumChildEpisodes ||
                    capture.ChildIdentity is null || !_screens.Add(capture.ChildIdentity) ||
                    capture.Admission is not { IsSupported: true } admission ||
                    !_admissions.Add(admission.Identity)) return Stop();
                _card = _native.CreateChild(admission.Identity);
                _episodes++;
                _child = new GenericEventV2Child(_episodes, _pendingDecision,
                    _pendingAction, admission.Operation, admission.MinSelect, admission.MaxSelect,
                    admission.CommitMode, admission.DomainCount);
                _resolvedDelivered = false;
                return Observation("child", "child");
            }
            if (_proceed)
            {
                if (capture.Status == "map")
                { Reconcile("map_handoff"); _complete = true; return Observation("complete", "map_handoff"); }
                if (capture.Status is "waiting" or "parent") return Observation("waiting", "waiting");
                return Stop();
            }
            if (capture.Status == "waiting") return Observation("waiting", "waiting");
            if (capture.Status != "parent") return Stop();
            if (Stamp(capture) == _pendingStamp) return Observation("waiting", "waiting");
            Reconcile("option_transition");
        }
        if (capture.Status != "parent" || capture.Options.Count is < 1 or > 8) return Stop();
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var option in capture.Options)
            if (option.Identity is null || option.StableId.Length is < 1 or > 96 || option.StableId.Any(c => c < ' ' || c > '~') ||
                option.RenderedText.Length == 0 || Encoding.UTF8.GetByteCount(option.RenderedText) > 1024 || option.RenderedText.Any(c => char.IsControl(c) && c != '\n' && c != '\t') || !ids.Add(option.StableId) ||
                capture.EventFinished != option.IsProceed) return Stop();
        if (capture.EventFinished && capture.Options.Count != 1) return Stop();
        string structure = Stamp(capture);
        if (structure != _lastStructure && !_seenStructures.Add(structure)) return Stop();
        _lastStructure = structure;
        _published = capture;
        _decision = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
            _nonce + ":" + _attempted + ":" + DecisionStamp(capture)))).ToLowerInvariant();
        return Observation("ready", capture.EventFinished ? "proceed" : "choose_option");
    }
    public GenericEventV2ApplyResult Apply(string? decisionId, string? actionId)
    {
        if (!Enter()) return Result(decisionId, actionId, "unsupported");
        try
        {
            if (_unsupported || _complete || _pending || _card is not null || _published is null)
                return Result(decisionId, actionId, "unsupported");
            if (decisionId != _decision) return Result(decisionId, actionId, "stale_decision");
            int index = -1;
            for (int i = 0; i < _published.Options.Count; i++) if (actionId == "choose:" + i) index = i;
            if (index < 0) return Result(decisionId, actionId, "illegal_action");
            GenericEventV2NativeOption selected = _published.Options[index];
            if (!selected.Enabled || selected.Dangerous || _chosen.Contains(selected.StableId))
                return Result(decisionId, actionId, "illegal_action");
            if (_attempted >= 12 || _attempted + _childAttempted >= 52)
            { _unsupported = true; return Result(decisionId, actionId, "budget_exhausted"); }
            var recapture = _native.Capture();
            if (_unsupported || recapture.Status != "parent" || DecisionStamp(recapture) != DecisionStamp(_published) ||
                recapture.Options.Count != _published.Options.Count ||
                recapture.Options.Where((x,i) => !ReferenceEquals(x.Identity,_published.Options[i].Identity)).Any())
            { _unsupported = true; return Result(decisionId, actionId, "unsupported"); }
            _pending = true; _proceed = selected.IsProceed; _pendingReads = 0;
            _pendingDecision = decisionId!; _pendingAction = actionId!; _pendingStamp = Stamp(_published);
            _chosen.Add(selected.StableId); _attempted++; _effects = "unverified";
            _published = null; _decision = "";
            try { _native.Dispatch(selected.Identity, _nonce, decisionId!, actionId!); }
            catch { _unsupported = true; return Result(decisionId, actionId, "uncertain"); }
            if (_unsupported) return Result(decisionId, actionId, "uncertain");
            _accepted++;
            return Result(decisionId, actionId, "accepted");
        }
        catch { _unsupported = true; return Result(decisionId, actionId, "uncertain"); }
        finally { _inside = false; }
    }
    public ICardSelectionV1ReadValue ReadChild(string? parentDecisionId, string? parentActionId, int childOrdinal)
    {
        if (!Enter()) return ChildFailure();
        try
        {
            if (!Lineage(parentDecisionId,parentActionId,childOrdinal)) { _unsupported = true; return ChildFailure(); }
            var value = _card!.Read();
            if (value is CardSelectionV1Observation observation)
            {
                _childReconciled = Math.Max(_childReconciled,
                    _completedChildActions + observation.PriorResults.Count);
                if (observation.Status == "unsupported") _unsupported = true;
            }
            else if (value is CardSelectionV1ResolvedResult resolved)
            {
                _childReconciled = _completedChildActions + resolved.PriorResults.Count;
                _resolvedDelivered = true;
            }
            else _unsupported = true;
            return value;
        }
        catch { _unsupported = true; return ChildFailure(); }
        finally { _inside = false; }
    }
    private int _completedChildActions;
    public ICardSelectionV1ApplyValue ApplyChild(string? parentDecisionId, string? parentActionId,
        int childOrdinal, string? decisionId, string? actionId)
    {
        if (!Enter()) return new CardSelectionV1ApplyFailure(_nonce,"unsupported");
        try
        {
            if (!Lineage(parentDecisionId,parentActionId,childOrdinal) || _resolvedDelivered ||
                _attempted + _childAttempted >= 52)
            { _unsupported = true; return new CardSelectionV1ApplyFailure(_nonce,"unsupported"); }
            // Validate advertised child action before counting a native attempt.
            var observation = _card!.Read() as CardSelectionV1Observation;
            if (observation is null || observation.DecisionId != decisionId ||
                !observation.LegalActions.Contains(actionId ?? ""))
                return new CardSelectionV1ApplyFailure(_nonce,"rejected");
            _childAttempted++;
            var result = _card.Apply(decisionId, actionId);
            if (result is CardSelectionV1DispatchReceipt) _childAccepted++;
            else _unsupported = true;
            return result;
        }
        catch { _unsupported = true; return new CardSelectionV1ApplyFailure(_nonce,"unsupported"); }
        finally { _inside = false; }
    }
    private bool Lineage(string? decision,string? action,int ordinal) => !_unsupported &&
        _card is not null && _child is not null && decision == _child.ParentDecisionId &&
        action == _child.ParentActionId && ordinal == _child.Ordinal;
    private ICardSelectionV1ReadValue ChildFailure() => CardSelectionV1Observation.Fixed(
        _nonce,"unsupported","unsupported",Array.Empty<CardSelectionV1ActionResult>());
    private void Reconcile(string result)
    {
        _native.CompleteParent(); _reconciled++; _pending = false;
        _completedChildActions = _childReconciled;
        _history.Add(new GenericEventV2PriorResult(_pendingDecision,_pendingAction,result));
    }
    private GenericEventV2Observation Stop() { _unsupported = true; return Observation("unsupported","unsupported"); }
    private GenericEventV2ApplyResult Result(string? decision,string? action,string outcome) =>
        new(_nonce,decision ?? "",action ?? "",outcome);
    private GenericEventV2Observation Observation(string status,string phase)
    {
        var candidates = new List<GenericEventV2Candidate>(); var actions = new List<string>();
        if (status == "ready" && _published is not null)
            for (int i=0;i<_published.Options.Count;i++)
            {
                var c = _published.Options[i]; string action = "choose:"+i;
                bool enabled = c.Enabled && !_chosen.Contains(c.StableId);
                candidates.Add(new GenericEventV2Candidate(i,action,c.StableId,c.RenderedText,enabled,c.Dangerous,c.IsProceed));
                if (enabled && !c.Dangerous) actions.Add(action);
            }
        return new GenericEventV2Observation(_nonce,status,phase,status=="ready"?_decision:"",candidates,actions,
            status=="child"?_child:null,_history,_attempted,_accepted,_reconciled,_episodes,
            _childAttempted,_childAccepted,_childReconciled,_effects);
    }
    private static string Stamp(GenericEventV2NativeCapture capture)
    {
        var b = new StringBuilder(capture.EventFinished ? "1" : "0");
        foreach (var x in capture.Options)
            b.Append('|').Append(x.StableId.Length).Append(':').Append(x.StableId)

                .Append(x.Enabled?'1':'0').Append(x.Dangerous?'1':'0').Append(x.IsProceed?'1':'0');
        return b.ToString();
    }
    private static string DecisionStamp(GenericEventV2NativeCapture capture) => Stamp(capture) + string.Concat(capture.Options.Select(x => "|" + x.RenderedText.Length + ":" + x.RenderedText));
    public void Dispose()
    {
        if (Environment.CurrentManagedThreadId != _thread || _inside) { _unsupported = true; throw new InvalidOperationException("Owner thread cleanup required."); }
        _unsupported = true; _card?.Dispose(); _native.Dispose(); _disposed = true;
    }
}
