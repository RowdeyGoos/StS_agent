using System;
using System.Collections.Generic;
using System.Diagnostics.CodeAnalysis;
using System.Linq;
using System.Text.Json;
using System.Text;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.ItemWireV1;

namespace Sts2AgentBridge.Successors.GenericEventV7;

// One owner-frame route pair. The caller owns request and returned buffers.
public sealed class GenericEventV7WireService : IDisposable
{
    public const string DecisionRoute = "/probe/generic-event-v7/public/decision";
    public const string ActionRoute = "/probe/generic-event-v7/public/action";
    private readonly object _gate = new();
    private readonly IGenericEventV7Session _session;
    private readonly string _nonce;
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private readonly HashSet<string> _used = new(StringComparer.Ordinal);
    private readonly List<(string Decision, string Action)> _childAccepted = new();
    private readonly HashSet<(string Decision, string Action)> _completedChildren = new();
    private readonly HashSet<(string Decision, string Action)> _completedItems = new();
    private ItemV1Observation? _itemDomain;
    private GenericEventV7RewardCard[]? _rewardCards;
    private bool? _rewardCanSkip;
    private readonly List<ItemV1ResolvedResult> _itemSetHistory=new();
    private string? _decision, _lastParentDecision, _lastParentAction;
    private string[] _legal = Array.Empty<string>();
    private GenericEventV7Child? _child;
    private GenericEventV7Observation? _previous;
    private CardSelectionV1Candidate[]? _domain;
    private CardSelectionV1EnchantmentEffect? _enchantment;
    private bool _inside, _interfered, _disposed, _childResolved, _previewSeen;
    private string? _failure;
    private int _reads, _attempts, _parentAttempts, _ordinal, _history;

    public GenericEventV7WireService(string nonce, IGenericEventV7Session session)
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
        GenericEventV7Observation parent = _session.Read();
        ValidateParent(parent);
        byte[]? payload = null;
        try
        {
            if (parent.Child is GenericEventV7Child child)
            {
                Require(parent.Status == "child" && !_childResolved);
                Require(child.ParentDecisionId == _lastParentDecision && child.ParentActionId == _lastParentAction);
                ValidateDescriptor(child);
                if (_child is null)
                {
                    Require(child.Ordinal == _ordinal + 1);
                    _child = child; _ordinal = child.Ordinal;
                    _domain = null; _enchantment = null; _itemDomain = null; _rewardCards=null; _rewardCanSkip=null; _itemSetHistory.Clear(); _childAccepted.Clear(); _history = 0; _previewSeen = false;
                }
                else Require(SameChild(child, _child));
                var tagged = _session.ReadChild(child.ParentDecisionId, child.ParentActionId, child.Ordinal);
                Require(tagged.ContractVersion == child.ContractVersion);
                object value = tagged switch {
                    GenericEventV7ItemRead i when child.Kind == "item" => i.Value,
                    GenericEventV7RewardChildRead r when child.Kind=="card_reward"=>r.Value,
                    GenericEventV7CardRead c when child.Kind == "card_selection" => c.Value,
                    _ => throw new InvalidOperationException() };
                ValidateChild(value);
                payload = EncodeChild(value);
            }
            else
            {
                if (_child is not null)
                {
                    Require(_childResolved || parent.Status == "unsupported");
                    _child = null; _childResolved = false; _domain = null; _enchantment = null;
                }
                if (parent.Status == "ready") Publish(parent.DecisionId, parent.LegalActions);
            }
            return GenericEventV7WireCodec.Decision(_nonce, parent, payload);
        }
        finally { if (payload is not null) Array.Clear(payload); }
    }

    private byte[] Apply(ActionRequest request)
    {
        Require(_decision is not null && request.Decision == _decision &&
            _legal.Contains(request.Action, StringComparer.Ordinal) && _used.Add(ReplayKey(request.Decision)));
        Require(_attempts < 52 && (_child is not null || _parentAttempts < 12));
        _decision = null; _legal = Array.Empty<string>(); _attempts++;
        if (_child is null)
        {
            Require(request.Ordinal == 0 && _previous is not null &&
                _previous.PriorResults.Count(r => r.Result == "child_completed") == _completedChildren.Count);
            _parentAttempts++;
            GenericEventV7ApplyResult result = _session.Apply(request.Decision, request.Action);
            Require(result.Version == GenericEventV7Limits.Version && result.SessionNonce == _nonce &&
                result.DecisionId == request.Decision && result.ActionId == request.Action &&
                result.Outcome is "accepted" or "unsupported" or "stale_decision" or "illegal_action" or "uncertain" or "budget_exhausted");
            if (result.Outcome == "accepted")
            { _lastParentDecision = result.DecisionId; _lastParentAction = result.ActionId; }
            else _failure = "unsupported";
            return GenericEventV7WireCodec.Action(_nonce, null, result, null);
        }
        Require(!_childResolved && request.Ordinal == _child.Ordinal &&
            request.ParentDecision == _child.ParentDecisionId && request.ParentAction == _child.ParentActionId &&
            _childAccepted.Count < (_child.Kind=="card_reward"?3:_child.Kind == "item" ? _child.OfferCount : 10));
        var tagged = _session.ApplyChild(request.ParentDecision, request.ParentAction,
            request.Ordinal, request.Decision, request.Action);
        Require(tagged.ContractVersion == _child.ContractVersion);
        object childResult = tagged switch {
            GenericEventV7ItemApply i when _child.Kind == "item" => i.Value,
            GenericEventV7RewardChildApply r when _child.Kind=="card_reward"=>r.Value,
            GenericEventV7CardApply c when _child.Kind == "card_selection" => c.Value,
            _ => throw new InvalidOperationException() };
        if(_child.Kind=="card_reward") {
            Require(childResult is GenericEventV7RewardReceipt);
            var receipt=(GenericEventV7RewardReceipt)childResult;
            Require(receipt.SessionNonce==_nonce&&receipt.DecisionId==request.Decision&&receipt.ActionId==request.Action&&receipt.Outcome is "accepted" or "rejected" or "unsupported" or "uncertain");
            if(receipt.Outcome=="accepted")_childAccepted.Add((request.Decision,request.Action));else _failure="unsupported";
        }else if (_child.Kind == "item") {
            if (childResult is ItemV1DispatchReceipt itemReceipt) {
                Require(itemReceipt.Version == "item_v1" && itemReceipt.SurfaceOrdinal == 1 &&
                    itemReceipt.SessionNonce == _nonce && itemReceipt.DecisionId == request.Decision &&
                    itemReceipt.ActionId == request.Action && itemReceipt.Outcome == "accepted");
                _childAccepted.Add((request.Decision,request.Action));
            } else if (childResult is ItemV1ApplyFailure itemFailure) {
                Require(itemFailure.Version == "item_v1" && itemFailure.SurfaceOrdinal == 1 &&
                    itemFailure.SessionNonce == _nonce && itemFailure.Outcome is "rejected" or "unsupported" or "uncertain");
                _failure="unsupported";
            } else throw new InvalidOperationException();
        }
        else
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
        byte[] bytes = EncodeChild(childResult);
        try { return GenericEventV7WireCodec.Action(_nonce, _child, null, bytes); }
        finally { Array.Clear(bytes); }
    }

    private byte[] EncodeChild(object value) => _child!.Kind=="card_reward"?GenericEventV7WireCodec.CardReward(value):_child.Kind == "item" ? EncodeItem(value) : _child.Operation == "enchant"
        ? Sts2AgentBridge.Successors.GenericEventV5.CardEnchantV1WireCodec.Encode(value,_child.MaxSelect>1) : _child.Operation == "remove"
        ? Sts2AgentBridge.Successors.GenericEventV5.CardRemoveV2WireCodec.Encode(value) : _child.Operation == "transform"
        ? Sts2AgentBridge.Successors.GenericEventV5.CardTransformV2WireCodec.Encode(value) : CardSelectionV1WireCodec.Encode(value);
    private static byte[] EncodeItem(object value) {
        if(value is GenericEventV7ItemSetRead set) {
            using var stream=new System.IO.MemoryStream();
            using(var w=new Utf8JsonWriter(stream)) {
                w.WriteStartObject();w.WriteString("version","item_set_v1");w.WriteString("session_nonce",set.SessionNonce);
                w.WriteString("status",set.Status);w.WriteNumber("offer_count",set.OfferCount);
                w.WritePropertyName("collected");w.WriteStartArray();
                foreach(var entry in set.Collected)WriteItem(w,entry);
                w.WriteEndArray();w.WritePropertyName("current");
                if(set.Current is null)w.WriteNullValue();else WriteItem(w,set.Current);
                w.WriteEndObject();
            }
            return stream.ToArray();
        }
        ItemWireV1Envelope envelope=value switch {
            ItemV1Observation x => new(x.SessionNonce,x.Status,decisionId:x.DecisionId,
                offers:x.Offers.Select(o=>new ItemWireV1OfferDto(o.Index,o.Kind,o.Key,o.Enabled)).ToArray(),potionSlots:x.PotionSlots,legalActions:x.LegalActions),
            ItemV1ResolvedResult x => new(x.SessionNonce,"resolved",decisionId:x.DecisionId,actionId:x.ActionId,
                offerIndex:x.OfferIndex,kind:x.Kind,key:x.Key,result:x.Result),
            ItemV1DispatchReceipt x => new(x.SessionNonce,"accepted",decisionId:x.DecisionId,actionId:x.ActionId),
            ItemV1ApplyFailure x => new(x.SessionNonce,x.Outcome),
            _ => throw new InvalidOperationException() };
        return ItemWireV1Codec.Encode(envelope);
    }

    private static void WriteItem(Utf8JsonWriter writer,object value) {
        var bytes=EncodeItem(value);try{using var doc=JsonDocument.Parse(bytes);doc.RootElement.WriteTo(writer);}finally{Array.Clear(bytes);}
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
             (_child.Kind=="card_reward"?RewardAction(action):_child.Kind == "item" ? ItemWireV1Protocol.IsCanonicalActionId(action,out _) : CardSelectionV1WireProtocol.IsChildAction(action))));
        // Exact canonical requests have no text-bearing fields or alternative JSON encodings.
        byte[] canonical = GenericEventV7WireCodec.Request(request.Decision, request.Action,
            request.Ordinal, request.ParentDecision, request.ParentAction);
        try { Require(body.AsSpan().SequenceEqual(canonical)); }
        finally { Array.Clear(canonical); }
        return request;
    }

    private void ValidateParent(GenericEventV7Observation p)
    {
        Require(p.Version == GenericEventV7Limits.Version && p.SessionNonce == _nonce);
        Require((p.Status, p.Phase) is ("ready", "choose_option") or ("ready", "proceed") or
            ("waiting", "waiting") or ("child", "child") or ("complete", "map_handoff") or
            ("unsupported", "unsupported"));
        Require(p.ParentAttempted >= 0 && p.ParentAttempted <= _parentAttempts &&
            p.ParentReconciled >= 0 && p.ParentReconciled <= p.ParentAccepted &&
            p.ParentAccepted <= p.ParentAttempted && p.ChildEpisodes is >= 0 and <= 4 &&
            p.ChildReconciled >= 0 && p.ChildReconciled <= p.ChildAccepted &&
            p.ChildAccepted <= p.ChildAttempted && p.ChildAttempted >= 0 &&
            p.TotalAttempted <= _attempts && p.Effects is "none_attempted" or "unverified" or "card_effect_verified" or "item_effect_verified");
        Require(p.CompletedCardChildren is >= 0 and <= 4 &&
            p.CompletedItemChildren is >= 0 and <= 4 &&
            p.CompletedCardChildren == _completedChildren.Count - _completedItems.Count &&
            p.CompletedItemChildren == _completedItems.Count && _completedChildren.Count <= p.ChildEpisodes);
        if (p.Effects is "item_effect_verified" or "card_effect_verified") {
            var latest=(_lastParentDecision!,_lastParentAction!);
            Require(_completedChildren.Contains(latest) &&
                (_completedItems.Contains(latest) == (p.Effects == "item_effect_verified")));
        }
        var completedHistory = p.PriorResults.Where(r => r.Result == "child_completed")
            .Select(r => (r.DecisionId, r.ActionId)).ToArray();
        Require(completedHistory.Distinct().Count() == completedHistory.Length &&
            completedHistory.All(owner => _completedChildren.Contains(owner)));
        var unreconciled = _completedChildren.Except(completedHistory).ToArray();
        Require(unreconciled.Length <= 1 && (unreconciled.Length == 0 ||
            p.Status == "unsupported" && unreconciled[0] == (_lastParentDecision, _lastParentAction)));
        Require((p.Status == "child") == (p.Child is not null));
        Require(p.PriorResults.Count == p.ParentReconciled && p.PriorResults.Count <= 12);
        foreach (GenericEventV7PriorResult r in p.PriorResults)
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
            foreach (GenericEventV7Candidate c in p.Candidates)
                Require(c.Index >= 0 && c.Index < p.Candidates.Count && ReferenceEquals(c, p.Candidates[c.Index]) &&
                    c.ActionId == "choose:" + c.Index && c.StableId is { Length: > 0 and <= 96 } &&
                    c.StableId.All(ch => ch is >= ' ' and <= '~') && keys.Add(c.StableId) &&
                    c.RenderedText is { Length: > 0 } && Encoding.UTF8.GetByteCount(c.RenderedText) <= 1024 &&
                    !c.RenderedText.Any(ch => char.IsControl(ch) && ch != '\n' && ch != '\t') && c.Discovery == (c.IsProceed ? "none" : "deferred"));
            Require(p.LegalActions.Distinct().Count() == p.LegalActions.Count &&
                p.LegalActions.All(a => p.Candidates.Any(c => c.ActionId == a && c.Enabled && !c.IsDangerous)));
            Require(p.Phase == "proceed" ? p.Candidates.Count == 1 && p.Candidates[0].IsProceed :
                p.Candidates.All(c => !c.IsProceed));
        }
        else Require(p.DecisionId == "" && p.Candidates.Count == 0 && p.LegalActions.Count == 0);
        if (p.Status == "complete") Require(p.PriorResults.Count > 0 && p.PriorResults[^1].Result == "map_handoff");
        _previous = p;
    }

    private static bool StableKey(string key)=>key is {Length:>0 and <=128} &&
        key.All(c=>c is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '_');
    private void ValidateEnchantment(CardSelectionV1EnchantmentEffect? value)
    {
        if (_child!.Operation != "enchant") { Require(value is null); return; }
        Require(value is { Amount: > 0 } && value.Key is { Length: > 0 and <= 128 } && value.Key.All(c => c is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '_'));
        _enchantment ??= value;
        Require(_enchantment!.Key == value!.Key && _enchantment.Amount == value.Amount);
    }

    private void ValidateChild(object value)
    {
        Require(_child is not null);
        if(_child.Kind=="card_reward"){ValidateReward(value);return;}
        if (_child.Kind == "item") { if(_child.OfferCount>1)ValidateItemSet(value);else ValidateItem(value); return; }
        if (value is CardSelectionV1Observation p)
        {
            Require(p.Version == "card_selection_v1" && p.SessionNonce == _nonce && p.ParentOrdinal == 1 &&
                p.Status is "ready" or "waiting" or "unsupported");
            ValidateHistory(p.PriorResults);
            if (p.Status == "ready")
            {
                ValidateEnchantment(p.Enchantment);
                Require(p.Operation == _child!.Operation && p.MinSelect == _child.MinSelect && p.MaxSelect == _child.MaxSelect &&
                    p.CommitMode == _child.CommitMode && p.Candidates.Count == _child.DomainCount);
                Require(p.PriorResults.Count == _childAccepted.Count);
                var selectedActions = _childAccepted.Where(a => a.Action.StartsWith("select:", StringComparison.Ordinal))
                    .Select(a => a.Action).ToArray();
                Require(selectedActions.Length <= _child.MaxSelect && selectedActions.Distinct().Count() == selectedActions.Length &&
                    p.SelectedSlots.Count == selectedActions.Length && p.SelectedSlots.Distinct().Count() == p.SelectedSlots.Count &&
                    p.SelectedSlots.All(slot => selectedActions.Contains("select:" + slot)) &&
                    !_childAccepted.Any(a => a.Action == "confirm"));
                if (p.Phase == "preview")
                {
                    Require(_child.CommitMode == "preview_confirm" && selectedActions.Length >= _child.MinSelect &&
                        (!(_child.Operation is "remove" or "transform" || _child.Operation is "upgrade" or "enchant" && _child.MaxSelect > 1) || selectedActions.Length == _child.MaxSelect ||
                         _childAccepted.Any(a => a.Action == "preview")));
                    Require(p.LegalActions.SequenceEqual(new[] { "confirm" }));
                    _previewSeen = true;
                }
                else
                {
                    Require(p.Phase == "selecting" && !_previewSeen && !_childAccepted.Any(a => a.Action == "preview") &&
                        (_child.CommitMode == "explicit_confirm" || !p.LegalActions.Contains("confirm")) &&
                        ((!(_child.Operation is "remove" or "transform" || _child.Operation is "upgrade" or "enchant" && _child.MaxSelect > 1) && _child.CommitMode != "auto_at_max") || selectedActions.Length < _child.MaxSelect));
                }
                if (_domain is null) _domain = p.Candidates.ToArray();
                for (int i = 0; i < _domain.Length; i++)
                {
                    var a = _domain[i]; var b = p.Candidates[i];
                    Require(a.Slot == i && b.Slot == i && a.Key == b.Key && a.UpgradeLevel == b.UpgradeLevel &&
                        b.Selected == p.SelectedSlots.Contains(b.Slot));
                }
                if (p.Phase == "selecting")
                {
                    // Public payload omits settling/control flags, so a native producer
                    // may narrow this allowed set; it must never expand it.
                    Require(p.LegalActions.Distinct().Count() == p.LegalActions.Count &&
                        p.LegalActions.All(action => action == "preview"
                            ? _child.CommitMode == "preview_confirm" && selectedActions.Length >= _child.MinSelect && selectedActions.Length <= _child.MaxSelect
                            : action == "confirm"
                                ? _child.CommitMode == "explicit_confirm" && selectedActions.Length >= _child.MinSelect && selectedActions.Length <= _child.MaxSelect
                            : selectedActions.Length < _child.MaxSelect && p.Candidates.Any(candidate =>
                                action == "select:" + candidate.Slot && candidate.Visible && candidate.Enabled && !candidate.Selected)));
                }
                Publish(p.DecisionId, p.LegalActions);
            }
            else Require(p.DecisionId == "" && p.LegalActions.Count == 0);
        }
        else if (value is CardSelectionV1ResolvedResult done)
        {
            ValidateEnchantment(done.Enchantment);
            Require(done.ParentAddedCards.Count<=(_child!.Operation=="remove"?1:0));
            foreach(var added in done.ParentAddedCards) {
                Require(StableKey(added.Key) && added.UpgradeLevel>=0);
                if(added.Enchantment is {} e) Require(StableKey(e.Key) && e.Amount>0);
            }
            Require(done.SessionNonce == _nonce && done.Operation == _child!.Operation && _domain is not null &&
                done.SelectedCards.Count >= _child.MinSelect && done.SelectedCards.Count <= _child.MaxSelect &&
                done.PriorResults.Count == _childAccepted.Count && _childAccepted.Count > 0);
            ValidateHistory(done.PriorResults);
            var selectedSlots = new HashSet<int>();
            var selectionActions = _childAccepted.Where(a => a.Action.StartsWith("select:", StringComparison.Ordinal))
                .Select(a => a.Action).ToArray();
            Require(selectionActions.Distinct().Count() == selectionActions.Length &&
                selectionActions.Length == done.SelectedCards.Count);
            if (_child.CommitMode == "auto_at_max")
                Require(!_previewSeen && selectionActions.Length == _child.MaxSelect && _childAccepted.Count == selectionActions.Length);
            else
            {
                Require(_childAccepted[^1].Action == "confirm" && _childAccepted.Count(a => a.Action == "confirm") == 1);
                if (_child.CommitMode == "preview_confirm") Require(_previewSeen);
                else Require(_child.CommitMode == "explicit_confirm" && !_previewSeen &&
                    _childAccepted.Count == selectionActions.Length + 1);
            }
            foreach (var selected in done.SelectedCards)
                Require(selected.Slot >= 0 && selected.Slot < _domain!.Length && selectedSlots.Add(selected.Slot) &&
                    selected.Key == _domain[selected.Slot].Key && selected.UpgradeLevel == _domain[selected.Slot].UpgradeLevel &&
                    selected.Selected && selectionActions.Contains("select:" + selected.Slot));
            Require(_completedChildren.Count < 4 &&
                _completedChildren.Add((_child.ParentDecisionId, _child.ParentActionId)));
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
        Require(Hex(decision, 64) && !_used.Contains(ReplayKey(decision)) && legal.Count is > 0 and <= 66);
        _decision = decision; _legal = legal.ToArray();
    }
    private string ReplayKey(string decision) => _child?.Kind is "item" or "card_reward"
        ? _child.Kind+":"+_child.ParentDecisionId+":"+_child.ParentActionId+":"+_child.Ordinal+":"+_child.ContractVersion+":"+decision : decision;
    private static void ValidateDescriptor(GenericEventV7Child c) => Require(c.Ordinal is >= 1 and <= 4 &&
        Hex(c.ParentDecisionId,64) && ParentAction(c.ParentActionId) &&
        (c.Kind=="card_reward"?c.OfferCount==1&&c.ContractVersion=="card_reward_v1"&&c.Operation==""&&c.MinSelect==0&&c.MaxSelect==0&&c.DomainCount==0&&c.CommitMode=="":c.Kind == "item" ? c.OfferCount is >=1 and <=8 && c.ContractVersion == (c.OfferCount==1?"item_v1":"item_set_v1") && c.Operation == "" &&
            c.MinSelect == 0 && c.MaxSelect == 0 && c.CommitMode == "" && c.DomainCount == 0 :
         c.Kind == "card_selection" && c.OfferCount == 0 && c.ContractVersion == GenericEventV7Families.ContractVersion(c.Operation,c.MaxSelect) &&
            GenericEventV7Families.Supports(c.Operation,c.MinSelect,c.MaxSelect,c.CommitMode,c.DomainCount)));
    private static bool SameChild(GenericEventV7Child a,GenericEventV7Child b) => a.Ordinal == b.Ordinal &&
        a.ParentDecisionId == b.ParentDecisionId && a.ParentActionId == b.ParentActionId && a.Kind == b.Kind &&
        a.ContractVersion == b.ContractVersion && a.OfferCount == b.OfferCount && a.Operation == b.Operation &&
        a.MinSelect == b.MinSelect && a.MaxSelect == b.MaxSelect && a.CommitMode == b.CommitMode && a.DomainCount == b.DomainCount;
    private static bool RewardAction(string action)=>action is "open" or "skip" or "dismiss"||action.Length==8&&action.StartsWith("choose:",StringComparison.Ordinal)&&action[7] is >= '0' and <= '4';
    private void ValidateReward(object value) {
        Require(value is GenericEventV7RewardRead);var p=(GenericEventV7RewardRead)value;
        Require(p.SessionNonce==_nonce&&p.PriorResults.Count>=_history&&p.PriorResults.Count<=_childAccepted.Count);
        for(int i=0;i<p.PriorResults.Count;i++) {
            var h=p.PriorResults[i];var a=_childAccepted[i];
            Require(h.DecisionId==a.Decision&&h.ActionId==a.Action&&h.Result==(a.Action=="open"?"opened":a.Action=="skip"?"skipped":a.Action=="dismiss"?"dismissed":"collected"));
        }
        _history=p.PriorResults.Count;
        if(p.Status=="ready") {
            Require(_history==_childAccepted.Count&&p.SelectedSlot is null);
            if(p.Phase=="choose") {
                Require(_childAccepted.Count==1&&_childAccepted[0].Action=="open"&&p.Cards.Count is >=1 and <=5);
                for(int i=0;i<p.Cards.Count;i++)Require(p.Cards[i].Slot==i&&StableKey(p.Cards[i].Key)&&p.Cards[i].UpgradeLevel>=0);
                _rewardCards??=p.Cards.ToArray();_rewardCanSkip??=p.CanSkip;
                Require(_rewardCards.SequenceEqual(p.Cards)&&_rewardCanSkip==p.CanSkip&&p.LegalActions.SequenceEqual(p.Cards.Select(c=>"choose:"+c.Slot).Concat(p.CanSkip?new[]{"skip"}:Array.Empty<string>())));
            }else {
                Require(p.Cards.Count==0&&!p.CanSkip&&((p.Phase=="open"&&_childAccepted.Count==0&&p.LegalActions.SequenceEqual(new[]{"open"}))||
                    (p.Phase=="dismiss"&&_childAccepted.Count==2&&_childAccepted[0].Action=="open"&&_childAccepted[1].Action=="skip"&&_rewardCanSkip==true&&p.LegalActions.SequenceEqual(new[]{"dismiss"}))));
            }
            Publish(p.DecisionId,p.LegalActions);return;
        }
        Require(p.DecisionId==""&&p.Cards.Count==0&&!p.CanSkip&&p.LegalActions.Count==0);
        if(p.Status=="resolved") {
            Require(p.Phase=="complete"&&_rewardCards is not null&&_history==_childAccepted.Count&&_childAccepted[0].Action=="open");
            Require(p.SelectedSlot is {} slot?_childAccepted.Count==2&&slot>=0&&slot<_rewardCards.Length&&_childAccepted[1].Action=="choose:"+slot:
                _childAccepted.Count==3&&_rewardCanSkip==true&&_childAccepted[1].Action=="skip"&&_childAccepted[2].Action=="dismiss");
            Require(_completedChildren.Count<4&&_completedChildren.Add((_child!.ParentDecisionId,_child.ParentActionId)));_childResolved=true;
        }else Require(p.SelectedSlot is null&&(p.Status,p.Phase) is ("waiting","waiting") or ("unsupported","unsupported"));
    }
    private void CompleteItem() {
        var owner=(_child!.ParentDecisionId,_child.ParentActionId);
        Require(_completedChildren.Count<4&&_completedChildren.Add(owner)&&_completedItems.Add(owner));_childResolved=true;
    }
    private static bool SameItem(ItemV1ResolvedResult a,ItemV1ResolvedResult b)=>a.SessionNonce==b.SessionNonce&&
        a.DecisionId==b.DecisionId&&a.ActionId==b.ActionId&&a.OfferIndex==b.OfferIndex&&a.Kind==b.Kind&&a.Key==b.Key&&a.Result==b.Result;
    private void ValidateItemSet(object value) {
        Require(value is GenericEventV7ItemSetRead);
        var set=(GenericEventV7ItemSetRead)value;
        Require(set.SessionNonce==_nonce&&set.OfferCount==_child!.OfferCount&&set.Collected.Count>=_itemSetHistory.Count&&
            set.Collected.Count<=Math.Min(set.OfferCount,_itemSetHistory.Count+1));
        for(int i=0;i<_itemSetHistory.Count;i++)Require(SameItem(_itemSetHistory[i],set.Collected[i]));
        if(set.Collected.Count>_itemSetHistory.Count) {
            ValidateItem(set.Collected[^1]);_itemSetHistory.Add(set.Collected[^1]);_itemDomain=null;
        }
        Require(set.Status is "ready" or "waiting" or "unsupported" or "resolved");
        if(set.Status=="resolved") {
            Require(set.Current is null&&set.Collected.Count==set.OfferCount&&_childAccepted.Count==set.OfferCount);CompleteItem();
        }else if(set.Status=="ready") {
            Require(set.Collected.Count<set.OfferCount&&set.Current is ItemV1Observation {Status:"ready"});ValidateItem(set.Current);
        }else if(set.Current is not null) {
            Require(set.Status=="waiting"&&set.Current is ItemV1Observation {Status:"waiting"});ValidateItem(set.Current);
        }
    }
    private void ValidateItem(object value) {
        if (value is ItemV1Observation p) {
            Require(p.Version == "item_v1" && p.SessionNonce == _nonce && p.SurfaceOrdinal == 1 && p.Status is "ready" or "waiting" or "unsupported");
            if (p.Status != "ready") {
                Require(p.DecisionId == "" && p.Offers.Count == 0 && p.PotionSlots.Count == 0 && p.LegalActions.Count == 0);
                return;
            }
            Require(_childAccepted.Count == _itemSetHistory.Count && p.Offers.Count == 1 && p.PotionSlots.Count <= 8);
            var offer=p.Offers[0];
            Require(_child!.OfferCount==1||offer.Index==_itemSetHistory.Count);
            Require(offer.Index is >= 0 and <= 255 && offer.Kind is "potion" or "relic" &&
                ItemV1CanonicalEncoder.IsStableKey(offer.Key) && offer.Enabled &&
                p.PotionSlots.All(slot=>slot is null || ItemV1CanonicalEncoder.IsStableKey(slot)) &&
                (offer.Kind == "relic" || p.PotionSlots.Any(slot=>slot is null)) &&
                p.LegalActions.SequenceEqual(new[]{"collect:"+offer.Index}) &&
                p.DecisionId == ItemV1CanonicalEncoder.ComputeDecisionId(_nonce,p.Offers,p.PotionSlots,p.LegalActions));
            if (_itemDomain is not null) {
                var prior=_itemDomain.Offers[0];
                Require(prior.Index == offer.Index && prior.Kind == offer.Kind && prior.Key == offer.Key &&
                    prior.Enabled == offer.Enabled && _itemDomain.PotionSlots.SequenceEqual(p.PotionSlots));
            }
            _itemDomain ??= p; Publish(p.DecisionId,p.LegalActions);
        } else if (value is ItemV1ResolvedResult r) {
            Require(r.Version == "item_v1" && r.SessionNonce == _nonce && r.SurfaceOrdinal == 1 &&
                _childAccepted.Count == _itemSetHistory.Count+1 && _itemDomain is not null);
            var offer=_itemDomain.Offers[0]; var accepted=_childAccepted[_itemSetHistory.Count];
            Require(r.DecisionId == accepted.Decision && r.ActionId == accepted.Action && r.ActionId == "collect:"+offer.Index &&
                r.OfferIndex == offer.Index && r.Kind == offer.Kind && r.Key == offer.Key && r.Result == "collected");
            if(_child!.OfferCount==1)CompleteItem();
        } else throw new InvalidOperationException();
    }
    private static bool ParentAction(string? s) => s is { Length: 8 } && s.StartsWith("choose:", StringComparison.Ordinal) && s[7] is >= '0' and <= '7';
    private static bool Hex(string? s, int n) => s is not null && s.Length == n && s.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');
    private static void Keys(JsonElement x, params string[] keys) => Require(x.ValueKind == JsonValueKind.Object && x.EnumerateObject().Select(p => p.Name).SequenceEqual(keys));
    private static void Require([DoesNotReturnIf(false)] bool condition) { if (!condition) throw new InvalidOperationException("Invalid generic-event value."); }
    private byte[] Fail(string code) { _failure = code; _decision = null; _legal = Array.Empty<string>(); return Error(code); }
    private byte[] Error(string code) => GenericEventV7WireCodec.Error(_nonce, code);
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
