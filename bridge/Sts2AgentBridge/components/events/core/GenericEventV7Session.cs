using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;
namespace Sts2AgentBridge.Successors.GenericEventV7;

public sealed class GenericEventV7Session : IGenericEventV7Session
{
    private readonly IGenericEventV7NativeAdapter _native;
    private readonly string _nonce;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    // Retire native controls, not localization keys: a settled new page may
    // legitimately offer the same choice again. Bounded by 8 * 12 controls.
    private readonly HashSet<object> _retiredOptions = new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _screens = new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _admissions = new(ReferenceEqualityComparer.Instance);
    private readonly List<GenericEventV7PriorResult> _history = new();
    private GenericEventV7NativeCapture? _published;
    private string _decision = "";
    private string _pendingDecision = "", _pendingAction = "";
    private bool _pending, _proceed, _unsupported, _complete, _inside, _disposed;
    private int _attempted, _accepted, _reconciled, _episodes, _childAttempted, _childAccepted, _childReconciled, _pendingReads, _reads;
    private IGenericEventV7ChildSession? _card;
    private GenericEventV7Child? _child;
    private bool _resolvedDelivered;
    private int _completedCardChildren, _completedItemChildren;
    private ItemV1Observation? _itemPublished;
    private ItemV1DispatchReceipt? _itemReceipt;
    private readonly List<ItemV1ResolvedResult> _itemResults=new();
    private string _effects = "none_attempted";

    public GenericEventV7Session(IGenericEventV7NativeAdapter adapter, string sessionNonce)
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
    public GenericEventV7Observation Read()
    {
        if (!Enter()) return Observation("unsupported", "unsupported");
        try { return ReadCore(); }
        catch { _unsupported = true; return Observation("unsupported", "unsupported"); }
        finally { _inside = false; }
    }
    private GenericEventV7Observation ReadCore()
    {
        if (++_reads > GenericEventV7Limits.MaximumHostReads) _unsupported = true;
        if (_unsupported) return Observation("unsupported", "unsupported");
        if (_complete) return Observation("complete", "map_handoff");
        if (_card is not null)
        {
            if (!_resolvedDelivered) return Observation("child", "child");
            _card.Dispose(); _card = null;
            _effects = _child!.Kind=="card_results"?"unverified":_child.Kind == "item" ? "item_effect_verified" : "card_effect_verified";
            _child = null;
            Reconcile("child_completed");
        }
        GenericEventV7NativeCapture capture = _native.Capture();
        if (_unsupported || capture.Status == "unsupported") return Stop();
        if (capture.Status == "parent" && !ValidParent(capture)) return Stop();
        if (_pending)
        {
            if (++_pendingReads > GenericEventV7Limits.MaximumPendingReads) return Stop();
            if (capture.Status == "child")
            {
                if (_proceed || _episodes >= GenericEventV7Limits.MaximumChildEpisodes ||
                    capture.ChildIdentity is null || !_screens.Add(capture.ChildIdentity) ||
                    capture.Admission is not { IsSupported: true } admission ||
                    !_admissions.Add(admission.Identity)) return Stop();
                _card = _native.CreateChild(admission.Identity);
                _child = admission switch {
                    GenericEventV7CardAdmission c => new GenericEventV7Child(_episodes+1,_pendingDecision,_pendingAction,c.Operation,c.MinSelect,c.MaxSelect,c.CommitMode,c.DomainCount),
                    GenericEventV7ResultsAdmission r => new GenericEventV7Child(_episodes+1,_pendingDecision,_pendingAction,r),
                    GenericEventV7OfferAdmission o => new GenericEventV7Child(_episodes+1,_pendingDecision,_pendingAction,o.OfferCount,o.Bundle?"bundle_offer_v1":"card_offer_v1"),
                    GenericEventV7RewardAdmission r => new GenericEventV7Child(_episodes+1,_pendingDecision,_pendingAction,r.OfferCount,true,r.Mixed),
                    GenericEventV7ItemAdmission i => new GenericEventV7Child(_episodes+1,_pendingDecision,_pendingAction,i.OfferCount),
                    _ => null };
                if (_child is null || !TypedChild()) return Stop();
                _episodes++;
                _itemPublished=null; _itemReceipt=null; _itemResults.Clear();
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
            // A parent capture during a pending choice already requires the
            // owned native Chosen task to have succeeded. Also require fresh
            // controls: changed labels/flags alone cannot settle the action.
            if (capture.Options.Any(x => _retiredOptions.Contains(x.Identity)))
                return Observation("waiting", "waiting");
            Reconcile("option_transition");
        }
        if (capture.Status != "parent" || capture.Options.Any(x => _retiredOptions.Contains(x.Identity))) return Stop();
        _published = capture;
        _decision = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
            _nonce + ":" + _attempted + ":" + DecisionStamp(capture)))).ToLowerInvariant();
        return Observation("ready", capture.EventFinished ? "proceed" : "choose_option");
    }
    private static bool ValidParent(GenericEventV7NativeCapture capture)
    {
        if (capture.Options.Count is < 1 or > GenericEventV7Limits.MaximumCandidates) return false;
        var ids = new HashSet<string>(StringComparer.Ordinal);
        var identities = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (var option in capture.Options)
            if (option.Identity is null || !identities.Add(option.Identity) || option.StableId.Length is < 1 or > 96 || option.StableId.Any(c => c < ' ' || c > '~') ||
                option.RenderedText.Length == 0 || Encoding.UTF8.GetByteCount(option.RenderedText) > 1024 || option.RenderedText.Any(c => char.IsControl(c) && c != '\n' && c != '\t') || !ids.Add(option.StableId) ||
                capture.EventFinished != option.IsProceed) return false;
        return !capture.EventFinished || capture.Options.Count == 1;
    }
    public GenericEventV7ApplyResult Apply(string? decisionId, string? actionId)
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
            GenericEventV7NativeOption selected = _published.Options[index];
            if (!selected.Enabled || selected.Dangerous)
                return Result(decisionId, actionId, "illegal_action");
            if (_attempted >= 12 || _attempted + _childAttempted >= 52)
            { _unsupported = true; return Result(decisionId, actionId, "budget_exhausted"); }
            var recapture = _native.Capture();
            if (_unsupported || recapture.Status != "parent" || DecisionStamp(recapture) != DecisionStamp(_published) ||
                recapture.Options.Count != _published.Options.Count ||
                recapture.Options.Where((x,i) => !ReferenceEquals(x.Identity,_published.Options[i].Identity)).Any())
            { _unsupported = true; return Result(decisionId, actionId, "unsupported"); }
            _pending = true; _proceed = selected.IsProceed; _pendingReads = 0;
            _pendingDecision = decisionId!; _pendingAction = actionId!;
            foreach (var option in _published.Options) _retiredOptions.Add(option.Identity);
            _attempted++; _effects = "unverified";
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
    public GenericEventV7ChildRead ReadChild(string? parentDecisionId, string? parentActionId, int childOrdinal)
    {
        if (!Enter()) return ChildFailure();
        try
        {
            if (!Lineage(parentDecisionId,parentActionId,childOrdinal)) { _unsupported = true; return ChildFailure(); }
            if (!TypedChild()) { _unsupported = true; return ChildFailure(); }
            if(_card is IGenericEventV7RewardChildSession reward) {
                var read=reward.Read();_childReconciled=_completedChildActions+read.PriorResults.Count;
                if(read.Status=="unsupported")_unsupported=true;
                if(read.Status=="resolved"){if(!_resolvedDelivered)_completedCardChildren++;_resolvedDelivered=true;}
                return new GenericEventV7RewardChildRead(read,ChildContract());
            }
            if (_card is IGenericEventV7ItemChildSession item) {
                var itemValue=item.Read();
                if(itemValue is GenericEventV7ItemSetRead set) {
                    if(_child!.ContractVersion!="item_set_v1"||set.SessionNonce!=_nonce||set.OfferCount!=_child.OfferCount||
                        set.Collected.Count<_itemResults.Count||set.Collected.Count>_itemResults.Count+1||set.Collected.Count>set.OfferCount)return StopItemSet();
                    for(int i=0;i<_itemResults.Count;i++)if(!SameItem(_itemResults[i],set.Collected[i]))return StopItemSet();
                    if(set.Collected.Count>_itemResults.Count) {
                        if(!ValidItemResult(set.Collected[^1]))return StopItemSet();
                        _itemResults.Add(set.Collected[^1]);_itemPublished=null;_itemReceipt=null;
                        _childReconciled=_completedChildActions+_itemResults.Count;
                    }
                    if(set.Status=="resolved") {
                        if(set.Collected.Count!=set.OfferCount||set.Current is not null)return StopItemSet();
                        if(!_resolvedDelivered)_completedItemChildren++;
                        _resolvedDelivered=true;
                    }else if(set.Status=="ready") {
                        if(_itemReceipt is not null||set.Collected.Count>=set.OfferCount||set.Current is not ItemV1Observation {Status:"ready",Offers.Count:1} next)return StopItemSet();
                        _itemPublished=next;
                    }else if(set.Status=="unsupported")_unsupported=true;
                    else if(set.Status!="waiting")return StopItemSet();
                    return new GenericEventV7ItemRead(set,ChildContract());
                }
                if(_child!.ContractVersion!="item_v1")return StopItemSet();
                if (itemValue is ItemV1Observation o) {
                    if (o.Status == "unsupported") _unsupported=true;
                    else if (o.Status == "ready") _itemPublished=o;
                    else if (o.Status != "waiting") _unsupported=true;
                } else if (itemValue is ItemV1ResolvedResult done) {
                    var offer=_itemPublished?.Offers.SingleOrDefault();
                    if (_itemReceipt is null || offer is null || done.SessionNonce != _nonce || done.SurfaceOrdinal != 1 ||
                        done.DecisionId != _itemReceipt.DecisionId || done.ActionId != _itemReceipt.ActionId ||
                        done.ActionId != "collect:"+offer.Index || done.OfferIndex != offer.Index || done.Kind != offer.Kind ||
                        done.Key != offer.Key || done.Result != "collected") { _unsupported=true; return ChildFailure(); }
                    _childReconciled=_completedChildActions+1;
                    if (!_resolvedDelivered) _completedItemChildren++;
                    _resolvedDelivered=true;
                } else { _unsupported=true; return ChildFailure(); }
                return new GenericEventV7ItemRead(itemValue);
            }
            var value = ((IGenericEventV7CardChildSession)_card!).Read();
            if (value is CardSelectionV1Observation observation)
            {
                _childReconciled = Math.Max(_childReconciled,
                    _completedChildActions + observation.PriorResults.Count);
                if (observation.Status == "unsupported") _unsupported = true;
            }
            else if (value is CardSelectionV1ResolvedResult resolved)
            {
                _childReconciled = _completedChildActions + resolved.PriorResults.Count;
                if (!_resolvedDelivered) _completedCardChildren++;
                _resolvedDelivered = true;
            }
            else _unsupported = true;
            return new GenericEventV7CardRead(ChildContract(), value);
        }
        catch { _unsupported = true; return ChildFailure(); }
        finally { _inside = false; }
    }
    private GenericEventV7ChildRead StopItemSet(){_unsupported=true;return ChildFailure();}
    private bool ValidItemResult(ItemV1ResolvedResult done) {
        var offer=_itemPublished?.Offers.SingleOrDefault();
        return _itemReceipt is not null&&offer is not null&&done.SessionNonce==_nonce&&done.SurfaceOrdinal==1&&
            done.DecisionId==_itemReceipt.DecisionId&&done.ActionId==_itemReceipt.ActionId&&done.ActionId=="collect:"+offer.Index&&
            done.OfferIndex==offer.Index&&done.Kind==offer.Kind&&done.Key==offer.Key&&done.Result=="collected";
    }
    private static bool SameItem(ItemV1ResolvedResult a,ItemV1ResolvedResult b)=>a.SessionNonce==b.SessionNonce&&
        a.DecisionId==b.DecisionId&&a.ActionId==b.ActionId&&a.OfferIndex==b.OfferIndex&&a.Kind==b.Kind&&a.Key==b.Key&&a.Result==b.Result;
    private int _completedChildActions;
    public GenericEventV7ChildApply ApplyChild(string? parentDecisionId, string? parentActionId,
        int childOrdinal, string? decisionId, string? actionId)
    {
        if (!Enter()) return ApplyFailure("unsupported",decisionId,actionId);
        try
        {
            if (!Lineage(parentDecisionId,parentActionId,childOrdinal) || _resolvedDelivered ||
                _attempted + _childAttempted >= 52)
            { _unsupported = true; return ApplyFailure("unsupported",decisionId,actionId); }
            if (!TypedChild()) { _unsupported = true; return ApplyFailure("unsupported",decisionId,actionId); }
            if(_card is IGenericEventV7RewardChildSession reward) {
                var read=reward.Read();
                if(read.Status!="ready"||read.DecisionId!=decisionId||!read.LegalActions.Contains(actionId??""))return ApplyFailure("rejected",decisionId,actionId);
                _childAttempted++;var outcome=reward.Apply(decisionId,actionId);
                if(outcome.Outcome=="accepted")_childAccepted++;else _unsupported=true;
                return new GenericEventV7RewardChildApply(outcome,ChildContract());
            }
            if (_card is IGenericEventV7ItemChildSession item) {
                if (_itemReceipt is not null) return ApplyFailure("rejected",decisionId,actionId);
                var itemRead=item.Read();
                var current=itemRead is GenericEventV7ItemSetRead {Status:"ready"} set&&set.Collected.Count==_itemResults.Count
                    ? set.Current as ItemV1Observation : itemRead as ItemV1Observation;
                if (current is null || current.Status != "ready" || current.DecisionId != decisionId ||
                    current.Offers.Count != 1 || !current.LegalActions.Contains(actionId ?? "")) return ApplyFailure("rejected",decisionId,actionId);
                _itemPublished=current; _childAttempted++;
                var outcome=item.Apply(decisionId,actionId);
                if (outcome is ItemV1DispatchReceipt receipt && receipt.SessionNonce == _nonce &&
                    receipt.DecisionId == decisionId && receipt.ActionId == actionId) { _itemReceipt=receipt; _childAccepted++; }
                else _unsupported=true;
                return new GenericEventV7ItemApply(outcome,ChildContract());
            }
            // Validate advertised child action before counting a native attempt.
            var observation = ((IGenericEventV7CardChildSession)_card!).Read() as CardSelectionV1Observation;
            if (observation is null || observation.DecisionId != decisionId ||
                !observation.LegalActions.Contains(actionId ?? ""))
                return ApplyFailure("rejected",decisionId,actionId);
            _childAttempted++;
            var result = ((IGenericEventV7CardChildSession)_card).Apply(decisionId, actionId);
            if (result is CardSelectionV1DispatchReceipt) _childAccepted++;
            else _unsupported = true;
            return new GenericEventV7CardApply(ChildContract(), result);
        }
        catch { _unsupported = true; return ApplyFailure("unsupported",decisionId,actionId); }
        finally { _inside = false; }
    }
    private bool Lineage(string? decision,string? action,int ordinal) => !_unsupported &&
        _card is not null && _child is not null && decision == _child.ParentDecisionId &&
        action == _child.ParentActionId && ordinal == _child.Ordinal;
    private string ChildContract() => _child?.ContractVersion ?? "card_selection_v1";
    private bool TypedChild() => _card is not null && _child is not null && _card.ContractVersion == ChildContract() &&
        (_child.Kind is "card_reward" or "card_offer" or "card_results" ? _card is IGenericEventV7RewardChildSession && _card is not IGenericEventV7CardChildSession && _card is not IGenericEventV7ItemChildSession : _child.Kind == "item" ? _card is IGenericEventV7ItemChildSession && _card is not IGenericEventV7CardChildSession :
            _card is IGenericEventV7CardChildSession && _card is not IGenericEventV7ItemChildSession);
    private GenericEventV7ChildRead ChildFailure() => _child?.Kind is "card_reward" or "card_offer" or "card_results" ? new GenericEventV7RewardChildRead(new(_nonce,"unsupported","unsupported","",Array.Empty<GenericEventV7RewardCard>(),false,Array.Empty<string>(),Array.Empty<GenericEventV7PriorResult>(),null),ChildContract()) : _child?.Kind == "item"
        ? new GenericEventV7ItemRead(_child!.OfferCount>1 ? new GenericEventV7ItemSetRead(_nonce,"unsupported",_child.OfferCount,Array.AsReadOnly(_itemResults.ToArray()),null) : ItemV1Observation.Fixed(_nonce,"unsupported"),ChildContract())
        : new GenericEventV7CardRead(ChildContract(),CardSelectionV1Observation.Fixed(
            _nonce,"unsupported","unsupported",Array.Empty<CardSelectionV1ActionResult>()));
    private GenericEventV7ChildApply ApplyFailure(string outcome,string? decision,string? action) => _child?.Kind is "card_reward" or "card_offer" or "card_results" ? new GenericEventV7RewardChildApply(new(_nonce,decision??"",action??"",outcome),ChildContract()) : _child?.Kind == "item"
        ? new GenericEventV7ItemApply(new ItemV1ApplyFailure(_nonce,outcome),ChildContract())
        : new GenericEventV7CardApply(ChildContract(),new CardSelectionV1ApplyFailure(_nonce,outcome));
    private void Reconcile(string result)
    {
        _native.CompleteParent(); _reconciled++; _pending = false;
        _completedChildActions = _childReconciled;
        _history.Add(new GenericEventV7PriorResult(_pendingDecision,_pendingAction,result));
    }
    private GenericEventV7Observation Stop() { _unsupported = true; return Observation("unsupported","unsupported"); }
    private GenericEventV7ApplyResult Result(string? decision,string? action,string outcome) =>
        new(_nonce,decision ?? "",action ?? "",outcome);
    private GenericEventV7Observation Observation(string status,string phase)
    {
        var candidates = new List<GenericEventV7Candidate>(); var actions = new List<string>();
        if (status == "ready" && _published is not null)
            for (int i=0;i<_published.Options.Count;i++)
            {
                var c = _published.Options[i]; string action = "choose:"+i;
                bool enabled = c.Enabled;
                candidates.Add(new GenericEventV7Candidate(i,action,c.StableId,c.RenderedText,enabled,c.Dangerous,c.IsProceed));
                if (enabled && !c.Dangerous) actions.Add(action);
            }
        return new GenericEventV7Observation(_nonce,status,phase,status=="ready"?_decision:"",candidates,actions,
            status=="child"?_child:null,_history,_attempted,_accepted,_reconciled,_episodes,
            _childAttempted,_childAccepted,_childReconciled,_effects,_completedCardChildren,_completedItemChildren);
    }
    private static string Stamp(GenericEventV7NativeCapture capture)
    {
        var b = new StringBuilder(capture.EventFinished ? "1" : "0");
        foreach (var x in capture.Options)
            b.Append('|').Append(x.StableId.Length).Append(':').Append(x.StableId)

                .Append(x.Enabled?'1':'0').Append(x.Dangerous?'1':'0').Append(x.IsProceed?'1':'0');
        return b.ToString();
    }
    private static string DecisionStamp(GenericEventV7NativeCapture capture) => Stamp(capture) + string.Concat(capture.Options.Select(x => "|" + x.RenderedText.Length + ":" + x.RenderedText));
    public void Dispose()
    {
        if (Environment.CurrentManagedThreadId != _thread || _inside) { _unsupported = true; throw new InvalidOperationException("Owner thread cleanup required."); }
        _unsupported = true; _card?.Dispose(); _native.Dispose(); _disposed = true;
    }
}
