using System;
using System.Collections.Generic;
using System.Diagnostics.CodeAnalysis;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1;

internal sealed class EventOrchestratorV1WireValidation
{
    private readonly string _nonce;
    private readonly HashSet<string> _reservedStableIds = new(StringComparer.Ordinal);
    private readonly Dictionary<string, ParentPublication> _parents = new(StringComparer.Ordinal);
    private string? _childKind;
    private ItemShape? _itemShape;
    private CardShape[]? _cardShape;
    private int _cardHistory;
    private bool _lastAcceptedWasProceed;

    internal EventOrchestratorV1WireValidation(string nonce)
    {
        Require(RoomFlowIdentity.IsNonce(nonce));
        _nonce = nonce;
    }

    internal void Parent(
        object value,
        RoomFlowDispatchReceipt? lastReceipt,
        EventOrchestratorV1ChildEnvelope? completedChild)
    {
        switch (value)
        {
            case EventOrchestratorV1Observation observation:
                ValidateParentObservation(observation, lastReceipt, completedChild);
                break;
            case EventOrchestratorV1ResolvedResult resolved:
                CommonParent(resolved.Version, resolved.FlowKind, resolved.SessionNonce,
                    resolved.ParentOrdinal);
                Require(lastReceipt is not null &&
                    _lastAcceptedWasProceed &&
                    resolved.DecisionId == lastReceipt.DecisionId &&
                    resolved.ActionId == lastReceipt.ActionId &&
                    resolved.Result == EventOrchestratorV1Limits.MapHandoffResult);
                ValidatePrior(resolved.PriorResult, lastReceipt, completedChild,
                    EventOrchestratorV1Limits.MapHandoffResult);
                break;
            case RoomFlowDispatchReceipt receipt:
                CommonParent(EventOrchestratorV1Limits.Version, receipt.FlowKind,
                    receipt.SessionNonce, receipt.ParentOrdinal);
                Require(RoomFlowIdentity.IsDecisionId(receipt.DecisionId) &&
                    RoomFlowIdentity.IsActionId(EventOrchestratorV1Limits.FlowKind,
                        receipt.ActionId) && receipt.Outcome == "accepted");
                Require(_parents.TryGetValue(receipt.DecisionId, out ParentPublication? published) &&
                    published.Legal.Contains(receipt.ActionId));
                ParentCandidate selected = published.Candidates.Single(
                    candidate => candidate.ActionId == receipt.ActionId);
                Require(_reservedStableIds.Add(selected.StableId));
                _lastAcceptedWasProceed = selected.IsProceed;
                _parents.Remove(receipt.DecisionId);
                break;
            case RoomFlowApplyFailure failure:
                CommonParent(EventOrchestratorV1Limits.Version, failure.FlowKind,
                    failure.SessionNonce, failure.ParentOrdinal);
                Require(failure.Outcome is "rejected" or "uncertain" or "unsupported");
                break;
            default:
                throw Invalid();
        }
    }

    internal void Child(
        JsonElement payload,
        bool apply,
        IReadOnlyList<(string Decision, string Action)> accepted)
    {
        Require(payload.ValueKind == JsonValueKind.Object && accepted is not null);
        Require(GetInt(payload, "schema_version") == 1);
        if (payload.TryGetProperty("protocol", out JsonElement protocol))
        {
            Require(_childKind is null or "item");
            _childKind = "item";
            ValidateItem(payload, StringValue(protocol), apply, accepted);
        }
        else
        {
            Require(_childKind is null or "card_selection");
            _childKind = "card_selection";
            ValidateCard(payload, Text(payload, "kind"), apply, accepted);
        }
    }

    internal void ResetChild()
    {
        _childKind = null;
        _itemShape = null;
        _cardShape = null;
        _cardHistory = 0;
    }

    private void ValidateParentObservation(
        EventOrchestratorV1Observation x,
        RoomFlowDispatchReceipt? lastReceipt,
        EventOrchestratorV1ChildEnvelope? completedChild)
    {
        CommonParent(x.Version, x.FlowKind, x.SessionNonce, x.ParentOrdinal);
        Require(x.Child is null && x.Status != EventOrchestratorV1Limits.ChildStatus);
        if (x.PriorResult is null)
            Require(completedChild is null || x.Status == EventOrchestratorV1Limits.WaitingStatus);
        else
            ValidatePrior(x.PriorResult, lastReceipt, completedChild, null);
        if (x.Status is EventOrchestratorV1Limits.WaitingStatus or
            EventOrchestratorV1Limits.UnsupportedStatus)
        {
            Require(x.Phase == (x.Status == EventOrchestratorV1Limits.WaitingStatus
                    ? EventOrchestratorV1Limits.WaitingPhase
                    : EventOrchestratorV1Limits.UnsupportedPhase) &&
                x.DecisionId == "" && x.Candidates.Count == 0 && x.LegalActions.Count == 0);
            return;
        }
        Require(x.Status == EventOrchestratorV1Limits.ReadyStatus &&
            x.Phase is EventOrchestratorV1Limits.ChooseOptionPhase or
                EventOrchestratorV1Limits.ProceedPhase &&
            RoomFlowIdentity.IsDecisionId(x.DecisionId) &&
            x.Candidates.Count is > 0 and <= EventOrchestratorV1Limits.MaximumCandidates);
        Require(lastReceipt is null || x.PriorResult is not null);
        var candidates = new ParentCandidate[x.Candidates.Count];
        var stable = new HashSet<string>(StringComparer.Ordinal);
        for (int index = 0; index < candidates.Length; index++)
        {
            EventOrchestratorV1Candidate candidate = x.Candidates[index];
            Require(candidate is not null && candidate.CandidateIndex == index &&
                candidate.ActionId == EventOrchestratorV1CanonicalEncoder.ActionIdFor(index) &&
                RoomFlowIdentity.IsEventStableId(candidate.StableId) &&
                RoomFlowIdentity.IsRenderedText(candidate.RenderedText) &&
                stable.Add(candidate.StableId) &&
                candidate.ChildPolicy is "" or EventOrchestratorV1Limits.ItemRewardPolicy or
                    EventOrchestratorV1Limits.CheeseGorgeAddTwoPolicy);
            if (candidate.IsProceed)
                Require(candidate.StableId == "PROCEED" && candidate.ChildPolicy == "" &&
                    !candidate.IsDangerous);
            else
                Require(candidate.ChildPolicy != "" &&
                    (candidate.StableId == "ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE"
                        ? candidate.ChildPolicy == EventOrchestratorV1Limits.CheeseGorgeAddTwoPolicy
                        : candidate.ChildPolicy == EventOrchestratorV1Limits.ItemRewardPolicy));
            candidates[index] = new(candidate.ActionId, candidate.StableId,
                candidate.Enabled, candidate.IsDangerous, candidate.IsProceed);
        }
        if (x.Phase == EventOrchestratorV1Limits.ProceedPhase)
            Require(candidates.Length == 1 && x.Candidates[0].IsProceed);
        else
            Require(x.Candidates.All(candidate => !candidate.IsProceed));

        string[] expectedLegal = candidates
            .Where(candidate => candidate.Enabled && !candidate.Dangerous &&
                !_reservedStableIds.Contains(candidate.StableId))
            .Select(candidate => candidate.ActionId).ToArray();
        Require(expectedLegal.Length > 0 && expectedLegal.SequenceEqual(x.LegalActions) &&
            x.DecisionId == EventOrchestratorV1CanonicalEncoder.ComputeDecisionId(
                _nonce, x.Phase, x.Candidates, x.LegalActions));
        _parents.Clear();
        _parents[x.DecisionId] = new(candidates, new HashSet<string>(x.LegalActions,
            StringComparer.Ordinal));
    }

    private void ValidatePrior(
        EventOrchestratorV1PriorResult? prior,
        RoomFlowDispatchReceipt? lastReceipt,
        EventOrchestratorV1ChildEnvelope? completedChild,
        string? requiredResult)
    {
        if (prior is null)
        {
            Require(requiredResult is null && completedChild is null);
            return;
        }
        Require(lastReceipt is not null && prior.DecisionId == lastReceipt.DecisionId &&
            prior.ActionId == lastReceipt.ActionId &&
            prior.Result is EventOrchestratorV1Limits.OptionTransitionResult or
                EventOrchestratorV1Limits.ChildCompletedResult or
                EventOrchestratorV1Limits.MapHandoffResult &&
            (requiredResult is null || prior.Result == requiredResult));
        if (prior.Result == EventOrchestratorV1Limits.ChildCompletedResult)
            Require(completedChild is not null && Same(prior.Child, completedChild));
        else
            Require(prior.Child is null && completedChild is null);
    }

    private void ValidateItem(JsonElement x, string protocol, bool apply,
        IReadOnlyList<(string Decision, string Action)> accepted)
    {
        Require(protocol == "item_probe_v1" && Text(x, "version") == "item_v1" &&
            Text(x, "session_nonce") == _nonce && GetInt(x, "surface_ordinal") == 1);
        string status = Text(x, "status");
        if (apply)
        {
            if (status == "accepted")
            {
                Keys(x, "schema_version", "protocol", "version", "session_nonce",
                    "surface_ordinal", "status", "decision_id", "action_id");
                Require(RoomFlowIdentity.IsDecisionId(Text(x, "decision_id")) &&
                    IsCollect(Text(x, "action_id"), out _));
            }
            else
            {
                Require(status is "rejected" or "uncertain" or "unsupported");
                ItemBaseKeys(x);
            }
            return;
        }
        if (status is "waiting" or "unsupported")
        {
            ItemBaseKeys(x);
            return;
        }
        if (status == "ready") ValidateItemReady(x);
        else if (status == "resolved") ValidateItemResolved(x, accepted);
        else throw Invalid();
    }

    private void ValidateItemReady(JsonElement x)
    {
        Keys(x, "schema_version", "protocol", "version", "session_nonce", "surface_ordinal",
            "status", "decision_id", "offers", "potion_slots", "legal_actions");
        JsonElement offers = Property(x, "offers"), slots = Property(x, "potion_slots"),
            legal = Property(x, "legal_actions");
        Require(offers.ValueKind == JsonValueKind.Array && offers.GetArrayLength() is > 0 and <= 8 &&
            slots.ValueKind == JsonValueKind.Array && slots.GetArrayLength() <= 8 &&
            legal.ValueKind == JsonValueKind.Array && legal.GetArrayLength() is > 0 and <= 8);
        var rows = new List<ItemOffer>(); int previous = -1;
        foreach (JsonElement offer in offers.EnumerateArray())
        {
            Keys(offer, "index", "kind", "key", "enabled");
            int index = GetInt(offer, "index"); string kind = Text(offer, "kind"), key = Text(offer, "key");
            Require(Bool(offer, "enabled", out bool enabled));
            Require(index is >= 0 and <= 255 && index > previous && kind is "potion" or "relic" &&
                StableKey(key));
            rows.Add(new(index, kind, key, enabled)); previous = index;
        }
        var slotValues = new List<string?>();
        foreach (JsonElement slot in slots.EnumerateArray())
        {
            Require(slot.ValueKind is JsonValueKind.Null or JsonValueKind.String);
            string? value = slot.ValueKind == JsonValueKind.Null ? null : slot.GetString();
            Require(value is null || StableKey(value)); slotValues.Add(value);
        }
        string[] actions = legal.EnumerateArray().Select(StringValue).ToArray();
        bool empty = slotValues.Any(slot => slot is null);
        string[] expected = rows.Where(row => row.Enabled && (row.Kind == "relic" || empty))
            .Select(row => "collect:" + row.Index.ToString(CultureInfo.InvariantCulture)).ToArray();
        Require(actions.SequenceEqual(expected));
        string decision = Text(x, "decision_id");
        Require(RoomFlowIdentity.IsDecisionId(decision) &&
            decision == ItemDecision(rows, slotValues, actions));
        var shape = new ItemShape(rows.ToArray(), slotValues.ToArray());
        Require(_itemShape is null || _itemShape.Same(shape));
        _itemShape ??= shape;
    }

    private void ValidateItemResolved(JsonElement x,
        IReadOnlyList<(string Decision, string Action)> accepted)
    {
        Keys(x, "schema_version", "protocol", "version", "session_nonce", "surface_ordinal",
            "status", "decision_id", "action_id", "offer_index", "kind", "key", "result");
        Require(accepted.Count == 1);
        Require(IsCollect(accepted[0].Action, out int index));
        Require(Text(x, "decision_id") == accepted[0].Decision &&
            Text(x, "action_id") == accepted[0].Action &&
            GetInt(x, "offer_index") == index &&
            Text(x, "kind") is "potion" or "relic" && StableKey(Text(x, "key")) &&
            Text(x, "result") == "collected" && _itemShape is not null);
        ItemOffer? source = _itemShape.Offers.SingleOrDefault(offer => offer.Index == index);
        Require(source is not null && source.Kind == Text(x, "kind") && source.Key == Text(x, "key"));
    }

    private void ValidateCard(JsonElement x, string kind, bool apply,
        IReadOnlyList<(string Decision, string Action)> accepted)
    {
        Require(Text(x, "version") == "card_selection_v1" &&
            Text(x, "session_nonce") == _nonce && GetInt(x, "parent_ordinal") == 1);
        if (apply)
        {
            if (kind == "child_receipt")
            {
                Keys(x, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "decision_id", "action_id", "outcome");
                Require(!x.TryGetProperty("status", out _));
                Require(RoomFlowIdentity.IsDecisionId(Text(x, "decision_id")) &&
                    CardAction(Text(x, "action_id")) && Text(x, "outcome") == "accepted");
            }
            else
            {
                Require(kind == "child_failure");
                Keys(x, "schema_version", "kind", "version", "session_nonce", "parent_ordinal", "outcome");
                Require(!x.TryGetProperty("status", out _) &&
                    Text(x, "outcome") is "rejected" or "uncertain" or "unsupported");
            }
            return;
        }
        string status = Text(x, "status");
        if (kind == "child_observation") ValidateCardObservation(x, status, accepted);
        else if (kind == "child_resolved") ValidateCardResolved(x, status, accepted);
        else throw Invalid();
    }

    private void ValidateCardObservation(JsonElement x, string status,
        IReadOnlyList<(string Decision, string Action)> accepted)
    {
        Keys(x, "schema_version", "kind", "version", "session_nonce", "parent_ordinal", "status",
            "phase", "operation", "commit_mode", "min_select", "max_select", "decision_id",
            "candidates", "selected_slots", "legal_actions", "prior_results");
        ValidateCardHistory(Property(x, "prior_results"), accepted, status == "ready");
        if (status != "ready")
        {
            Require((status == "waiting" && Text(x, "phase") is "selecting" or "submitted" or "transient") ||
                (status == "unsupported" && Text(x, "phase") == "unsupported"));
            Require(Text(x, "operation") == "" && Text(x, "commit_mode") == "" &&
                GetInt(x, "min_select") == 0 && GetInt(x, "max_select") == 0 &&
                Text(x, "decision_id") == "" && EmptyArray(x, "candidates") &&
                EmptyArray(x, "selected_slots") && EmptyArray(x, "legal_actions"));
            return;
        }
        Require(Text(x, "phase") == "selecting" && Text(x, "operation") == "add" &&
            Text(x, "commit_mode") == "auto_at_max" && GetInt(x, "min_select") == 2 &&
            GetInt(x, "max_select") == 2 && RoomFlowIdentity.IsDecisionId(Text(x, "decision_id")));
        JsonElement candidates = Property(x, "candidates");
        Require(candidates.ValueKind == JsonValueKind.Array && candidates.GetArrayLength() == 8);
        CardShape[] shape = ValidateCardCandidates(candidates);
        Require(_cardShape is null || SameCardShape(_cardShape, shape));
        _cardShape ??= shape;
        int[] selected = IntArray(x, "selected_slots", 8);
        Require(selected.Distinct().Count() == selected.Length &&
            selected.SequenceEqual(shape.Where(row => row.Selected).Select(row => row.Slot)) &&
            selected.Length <= 2);
        int[] historySelected = accepted.Where(pair => pair.Action.StartsWith("select:", StringComparison.Ordinal))
            .Select(pair => int.Parse(pair.Action.AsSpan(7), CultureInfo.InvariantCulture)).ToArray();
        Require(selected.Order().SequenceEqual(historySelected.Order()));
        string[] legal = StringArray(x, "legal_actions", 65);
        string[] expected = shape.Where(row => row.Visible && row.Enabled && !row.Selected && selected.Length < 2)
            .Select(row => "select:" + row.Slot.ToString(CultureInfo.InvariantCulture)).ToArray();
        Require(legal.SequenceEqual(expected) && legal.Length > 0);
    }

    private void ValidateCardResolved(JsonElement x, string status,
        IReadOnlyList<(string Decision, string Action)> accepted)
    {
        Keys(x, "schema_version", "kind", "version", "session_nonce", "parent_ordinal", "status",
            "phase", "operation", "selected_cards", "prior_results");
        Require(status == "resolved" && Text(x, "phase") == "complete" &&
            Text(x, "operation") == "add" && _cardShape is not null && accepted.Count == 2);
        ValidateCardHistory(Property(x, "prior_results"), accepted, complete: true);
        CardShape[] selected = ValidateCardCandidates(Property(x, "selected_cards"));
        Require(selected.Length == 2 && selected.All(row => row.Selected));
        foreach (CardShape row in selected)
            Require(_cardShape.Any(source => source.Slot == row.Slot && source.Key == row.Key &&
                source.UpgradeLevel == row.UpgradeLevel));
        int[] expected = accepted.Select(pair =>
        {
            Require(pair.Action.StartsWith("select:", StringComparison.Ordinal));
            return int.Parse(pair.Action.AsSpan(7), CultureInfo.InvariantCulture);
        }).Order().ToArray();
        Require(selected.Select(row => row.Slot).Order().SequenceEqual(expected));
    }

    private static CardShape[] ValidateCardCandidates(JsonElement values)
    {
        Require(values.ValueKind == JsonValueKind.Array && values.GetArrayLength() is > 0 and <= 64);
        var result = new List<CardShape>(); var slots = new HashSet<int>();
        foreach (JsonElement value in values.EnumerateArray())
        {
            Keys(value, "slot", "key", "upgrade_level", "visible", "enabled", "selected");
            int slot = GetInt(value, "slot"), level = GetInt(value, "upgrade_level");
            Require(Bool(value, "visible", out bool visible));
            Require(Bool(value, "enabled", out bool enabled));
            Require(Bool(value, "selected", out bool selected));
            Require(slot is >= 0 and < 64 && level >= 0 && StableKey(Text(value, "key")) &&
                slots.Add(slot));
            result.Add(new(slot, Text(value, "key"), level, visible, enabled, selected));
        }
        return result.ToArray();
    }

    private void ValidateCardHistory(JsonElement history,
        IReadOnlyList<(string Decision, string Action)> accepted, bool complete)
    {
        Require(history.ValueKind == JsonValueKind.Array && history.GetArrayLength() <= 10 &&
            history.GetArrayLength() <= accepted.Count && history.GetArrayLength() >= _cardHistory &&
            (!complete || history.GetArrayLength() == accepted.Count));
        int index = 0;
        foreach (JsonElement row in history.EnumerateArray())
        {
            Keys(row, "decision_id", "action_id", "result");
            string action = Text(row, "action_id");
            Require(Text(row, "decision_id") == accepted[index].Decision &&
                action == accepted[index].Action && CardAction(action) &&
                Text(row, "result") == (action.StartsWith("select:", StringComparison.Ordinal)
                    ? "selected" : action == "preview" ? "previewed" : "committed"));
            index++;
        }
        _cardHistory = index;
    }

    private string ItemDecision(IReadOnlyList<ItemOffer> offers,
        IReadOnlyList<string?> slots, IReadOnlyList<string> legal)
    {
        var builder = new StringBuilder();
        Append(builder, "item_v1"); Append(builder, _nonce); Integer(builder, 1);
        Integer(builder, offers.Count);
        foreach (ItemOffer offer in offers)
        { Integer(builder, offer.Index); Append(builder, offer.Kind); Append(builder, offer.Key); Integer(builder, offer.Enabled ? 1 : 0); }
        Integer(builder, slots.Count);
        foreach (string? slot in slots) { Integer(builder, slot is null ? 0 : 1); if (slot is not null) Append(builder, slot); }
        Integer(builder, legal.Count); foreach (string action in legal) Append(builder, action);
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(builder.ToString()))).ToLowerInvariant();
    }

    private static void Append(StringBuilder b, string value) => b.Append(value.Length).Append(':').Append(value).Append(';');
    private static void Integer(StringBuilder b, int value) => b.Append(value.ToString(CultureInfo.InvariantCulture)).Append(';');
    private static void ItemBaseKeys(JsonElement x) => Keys(x, "schema_version", "protocol", "version", "session_nonce", "surface_ordinal", "status");
    private void CommonParent(string version, string flow, string nonce, int ordinal) =>
        Require(version == EventOrchestratorV1Limits.Version && flow == "event" &&
            nonce == _nonce && ordinal == 1);
    private static bool Same(EventOrchestratorV1ChildEnvelope? a, EventOrchestratorV1ChildEnvelope b) =>
        a is not null && a.Kind == b.Kind && a.ChildOrdinal == b.ChildOrdinal &&
        a.ParentDecisionId == b.ParentDecisionId && a.ParentActionId == b.ParentActionId;
    private static bool SameCardShape(CardShape[] a, CardShape[] b) => a.Length == b.Length &&
        a.Zip(b).All(pair => pair.First.Slot == pair.Second.Slot && pair.First.Key == pair.Second.Key &&
            pair.First.UpgradeLevel == pair.Second.UpgradeLevel);
    private static bool EmptyArray(JsonElement x, string name) => Property(x, name).ValueKind == JsonValueKind.Array && Property(x, name).GetArrayLength() == 0;
    private static int[] IntArray(JsonElement x, string name, int maximum)
    { JsonElement a = Property(x, name); Require(a.ValueKind == JsonValueKind.Array && a.GetArrayLength() <= maximum); return a.EnumerateArray().Select(v => { Require(v.ValueKind == JsonValueKind.Number); Require(v.TryGetInt32(out int n)); return n; }).ToArray(); }
    private static string[] StringArray(JsonElement x, string name, int maximum)
    { JsonElement a = Property(x, name); Require(a.ValueKind == JsonValueKind.Array && a.GetArrayLength() <= maximum); return a.EnumerateArray().Select(StringValue).ToArray(); }
    private static string StringValue(JsonElement x) { Require(x.ValueKind == JsonValueKind.String); return x.GetString()!; }
    private static JsonElement Property(JsonElement x, string name) { Require(x.TryGetProperty(name, out JsonElement value)); return value; }
    private static string Text(JsonElement x, string name) => StringValue(Property(x, name));
    private static int GetInt(JsonElement x, string name) { JsonElement value = Property(x, name); Require(value.ValueKind == JsonValueKind.Number); Require(value.TryGetInt32(out int result)); return result; }
    private static bool Bool(JsonElement x, string name, out bool result) { JsonElement value = Property(x, name); result = value.ValueKind == JsonValueKind.True; return value.ValueKind is JsonValueKind.True or JsonValueKind.False; }
    private static bool StableKey(string? value) => RoomFlowIdentity.IsStableKey(value);
    private static bool CardAction(string value)
    { if (value is "preview" or "confirm") return true; return value.StartsWith("select:", StringComparison.Ordinal) && int.TryParse(value.AsSpan(7), NumberStyles.None, CultureInfo.InvariantCulture, out int slot) && slot is >= 0 and < 64 && value == "select:" + slot.ToString(CultureInfo.InvariantCulture); }
    private static bool IsCollect(string value, out int index)
    { index = -1; return value.StartsWith("collect:", StringComparison.Ordinal) && int.TryParse(value.AsSpan(8), NumberStyles.None, CultureInfo.InvariantCulture, out index) && index is >= 0 and <= 255 && value == "collect:" + index.ToString(CultureInfo.InvariantCulture); }
    private static void Keys(JsonElement x, params string[] names)
    { Require(x.ValueKind == JsonValueKind.Object); int index = 0; foreach (JsonProperty property in x.EnumerateObject()) { Require(index < names.Length && property.Name == names[index]); index++; } Require(index == names.Length); }
    private static InvalidOperationException Invalid() => new("Invalid event wire state.");
    private static void Require([DoesNotReturnIf(false)] bool condition) { if (!condition) throw Invalid(); }

    private sealed record ParentCandidate(string ActionId, string StableId, bool Enabled, bool Dangerous, bool IsProceed);
    private sealed record ParentPublication(ParentCandidate[] Candidates, HashSet<string> Legal);
    private sealed record ItemOffer(int Index, string Kind, string Key, bool Enabled);
    private sealed record ItemShape(ItemOffer[] Offers, string?[] Slots)
    {
        internal bool Same(ItemShape other) => Offers.SequenceEqual(other.Offers) && Slots.SequenceEqual(other.Slots);
    }
    private sealed record CardShape(int Slot, string Key, int UpgradeLevel, bool Visible, bool Enabled, bool Selected);
}
