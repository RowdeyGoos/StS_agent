using System;
using System.Buffers;
using System.Collections.Generic;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Wire;

internal static class CardSelectionV1WireCodec
{
    public static byte[] Encode(object value)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer, new JsonWriterOptions { Indented = false }))
        {
            writer.WriteStartObject();
            writer.WriteNumber("schema_version", CardSelectionV1WireProtocol.SchemaVersion);
            switch (value)
            {
                case CardSelectionParentV1Observation item: ParentObservation(writer, item); break;
                case CardSelectionParentV1ResolvedResult item: ParentResolved(writer, item); break;
                case CardSelectionParentV1DispatchReceipt item: ParentReceipt(writer, item); break;
                case CardSelectionParentV1ApplyFailure item: ParentFailure(writer, item); break;
                case CardSelectionV1Observation item: ChildObservation(writer, item); break;
                case CardSelectionV1ResolvedResult item: ChildResolved(writer, item); break;
                case CardSelectionV1DispatchReceipt item: ChildReceipt(writer, item); break;
                case CardSelectionV1ApplyFailure item: ChildFailure(writer, item); break;
                case CardSelectionParentV1ChildUnavailable item: ChildUnavailable(writer, item); break;
                case CardSelectionParentV1ChildApplyFailure item: ChildParentFailure(writer, item); break;
                default: throw new InvalidOperationException("Unknown card-selection wire value.");
            }
            writer.WriteEndObject();
        }
        byte[] result = buffer.WrittenSpan.ToArray();
        if (result.Length > CardSelectionV1WireProtocol.MaximumResponseBytes)
        {
            Array.Clear(result);
            throw new InvalidOperationException("Card-selection response exceeded its cap.");
        }
        return result;
    }

    public static byte[] Error(string code)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("schema_version", 1);
            writer.WriteString("kind", "error");
            writer.WriteString("status", "error");
            writer.WriteString("code", code);
            writer.WriteEndObject();
        }
        return buffer.WrittenSpan.ToArray();
    }

    private static void ParentObservation(Utf8JsonWriter w, CardSelectionParentV1Observation x)
    {
        w.WriteString("kind", "parent_observation"); Common(w, x.Version, x.SessionNonce, x.ParentOrdinal);
        w.WriteString("status", x.Status); w.WriteString("phase", x.Phase);
        w.WriteString("parent_kind", x.ParentKind); w.WriteString("policy", x.Policy);
        w.WriteString("decision_id", x.DecisionId); Strings(w, "legal_actions", x.LegalActions);
    }
    private static void ParentResolved(Utf8JsonWriter w, CardSelectionParentV1ResolvedResult x)
    {
        w.WriteString("kind", "parent_resolved"); Common(w, x.Version, x.SessionNonce, x.ParentOrdinal);
        w.WriteString("status", x.Status); w.WriteString("result", x.Result);
        w.WriteString("begin_decision_id", x.BeginDecisionId); w.WriteString("begin_action_id", x.BeginActionId);
        w.WriteString("proceed_decision_id", x.ProceedDecisionId); w.WriteString("proceed_action_id", x.ProceedActionId);
    }
    private static void ParentReceipt(Utf8JsonWriter w, CardSelectionParentV1DispatchReceipt x)
    {
        w.WriteString("kind", "parent_receipt"); Common(w, x.Version, x.SessionNonce, x.ParentOrdinal);
        w.WriteString("decision_id", x.DecisionId); w.WriteString("action_id", x.ActionId); w.WriteString("outcome", x.Outcome);
    }
    private static void ParentFailure(Utf8JsonWriter w, CardSelectionParentV1ApplyFailure x)
    {
        w.WriteString("kind", "parent_failure"); Common(w, x.Version, x.SessionNonce, x.ParentOrdinal);
        w.WriteString("outcome", x.Outcome);
    }
    private static void ChildObservation(Utf8JsonWriter w, CardSelectionV1Observation x)
    {
        w.WriteString("kind", "child_observation"); Common(w, x.Version, x.SessionNonce, x.ParentOrdinal);
        w.WriteString("status", x.Status); w.WriteString("phase", x.Phase); w.WriteString("operation", x.Operation);
        w.WriteString("commit_mode", x.CommitMode); w.WriteNumber("min_select", x.MinSelect); w.WriteNumber("max_select", x.MaxSelect);
        w.WriteString("decision_id", x.DecisionId); Candidates(w, "candidates", x.Candidates);
        Ints(w, "selected_slots", x.SelectedSlots); Strings(w, "legal_actions", x.LegalActions);
        Results(w, x.PriorResults);
    }
    private static void ChildResolved(Utf8JsonWriter w, CardSelectionV1ResolvedResult x)
    {
        w.WriteString("kind", "child_resolved"); Common(w, x.Version, x.SessionNonce, x.ParentOrdinal);
        w.WriteString("status", x.Status); w.WriteString("phase", x.Phase); w.WriteString("operation", x.Operation);
        Candidates(w, "selected_cards", x.SelectedCards); Results(w, x.PriorResults);
    }
    private static void ChildReceipt(Utf8JsonWriter w, CardSelectionV1DispatchReceipt x)
    {
        w.WriteString("kind", "child_receipt"); Common(w, x.Version, x.SessionNonce, x.ParentOrdinal);
        w.WriteString("decision_id", x.DecisionId); w.WriteString("action_id", x.ActionId); w.WriteString("outcome", x.Outcome);
    }
    private static void ChildFailure(Utf8JsonWriter w, CardSelectionV1ApplyFailure x)
    {
        w.WriteString("kind", "child_failure"); Common(w, x.Version, x.SessionNonce, x.ParentOrdinal); w.WriteString("outcome", x.Outcome);
    }
    private static void ChildUnavailable(Utf8JsonWriter w, CardSelectionParentV1ChildUnavailable x)
    {
        w.WriteString("kind", "child_observation"); Common(w, x.Version, x.SessionNonce, 1);
        FixedChild(w, x.Status, x.Phase);
    }
    private static void ChildParentFailure(Utf8JsonWriter w, CardSelectionParentV1ChildApplyFailure x)
    {
        w.WriteString("kind", "child_failure"); Common(w, x.Version, x.SessionNonce, 1); w.WriteString("outcome", x.Outcome);
    }
    private static void FixedChild(Utf8JsonWriter w, string status, string phase)
    {
        w.WriteString("status", status); w.WriteString("phase", phase); w.WriteString("operation", "");
        w.WriteString("commit_mode", ""); w.WriteNumber("min_select", 0); w.WriteNumber("max_select", 0);
        w.WriteString("decision_id", ""); w.WriteStartArray("candidates"); w.WriteEndArray();
        w.WriteStartArray("selected_slots"); w.WriteEndArray(); w.WriteStartArray("legal_actions"); w.WriteEndArray();
        w.WriteStartArray("prior_results"); w.WriteEndArray();
    }
    private static void Common(Utf8JsonWriter w, string version, string nonce, int ordinal)
    { w.WriteString("version", version); w.WriteString("session_nonce", nonce); w.WriteNumber("parent_ordinal", ordinal); }
    private static void Candidates(Utf8JsonWriter w, string name, IReadOnlyList<CardSelectionV1Candidate> values)
    {
        w.WriteStartArray(name);
        foreach (CardSelectionV1Candidate x in values)
        { w.WriteStartObject(); w.WriteNumber("slot", x.Slot); w.WriteString("key", x.Key); w.WriteNumber("upgrade_level", x.UpgradeLevel); w.WriteBoolean("visible", x.Visible); w.WriteBoolean("enabled", x.Enabled); w.WriteBoolean("selected", x.Selected); w.WriteEndObject(); }
        w.WriteEndArray();
    }
    private static void Results(Utf8JsonWriter w, IReadOnlyList<CardSelectionV1ActionResult> values)
    {
        w.WriteStartArray("prior_results");
        foreach (CardSelectionV1ActionResult x in values)
        { w.WriteStartObject(); w.WriteString("decision_id", x.DecisionId); w.WriteString("action_id", x.ActionId); w.WriteString("result", x.Result); w.WriteEndObject(); }
        w.WriteEndArray();
    }
    private static void Strings(Utf8JsonWriter w, string name, IReadOnlyList<string> values)
    { w.WriteStartArray(name); foreach (string x in values) w.WriteStringValue(x); w.WriteEndArray(); }
    private static void Ints(Utf8JsonWriter w, string name, IReadOnlyList<int> values)
    { w.WriteStartArray(name); foreach (int x in values) w.WriteNumberValue(x); w.WriteEndArray(); }
}
