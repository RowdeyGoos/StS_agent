using System;
using System.Buffers;
using System.Collections.Generic;
using System.Text.Json;

namespace Sts2AgentBridge.Successors.GenericEventV7;

internal static class GenericEventV7WireCodec
{
    internal static byte[] Decision(string nonce, GenericEventV7Observation p, byte[]? payload) =>
        Encode(w =>
        {
            Start(w, nonce, "decision");
            w.WritePropertyName("parent"); w.WriteStartObject();
            w.WriteString("status", p.Status); w.WriteString("phase", p.Phase);
            w.WriteString("decision_id", p.DecisionId); w.WriteStartArray("candidates");
            foreach (var c in p.Candidates)
            {
                w.WriteStartObject(); w.WriteNumber("index", c.Index);
                w.WriteString("action_id", c.ActionId); w.WriteString("stable_id", c.StableId);
                w.WriteString("rendered_text", c.RenderedText); w.WriteBoolean("enabled", c.Enabled);
                w.WriteBoolean("is_dangerous", c.IsDangerous); w.WriteBoolean("is_proceed", c.IsProceed);
                w.WriteString("discovery", c.Discovery); w.WriteEndObject();
            }
            w.WriteEndArray(); Strings(w, "legal_actions", p.LegalActions);
            w.WriteStartArray("prior_results");
            foreach (var r in p.PriorResults)
            {
                w.WriteStartObject(); w.WriteString("decision_id", r.DecisionId);
                w.WriteString("action_id", r.ActionId); w.WriteString("result", r.Result); w.WriteEndObject();
            }
            w.WriteEndArray();
            w.WriteNumber("parent_attempted", p.ParentAttempted); w.WriteNumber("parent_accepted", p.ParentAccepted);
            w.WriteNumber("parent_reconciled", p.ParentReconciled); w.WriteNumber("child_episodes", p.ChildEpisodes);
            w.WriteNumber("child_attempted", p.ChildAttempted); w.WriteNumber("child_accepted", p.ChildAccepted);
            w.WriteNumber("child_reconciled", p.ChildReconciled); w.WriteNumber("total_attempted", p.TotalAttempted);
            w.WriteString("effects", p.Effects);
            w.WriteNumber("completed_card_children", p.CompletedCardChildren);
            w.WriteNumber("completed_item_children", p.CompletedItemChildren); w.WriteEndObject(); Child(w, p.Child);
            Payload(w, payload); w.WriteEndObject();
        });

    internal static byte[] Action(string nonce, GenericEventV7Child? child,
        GenericEventV7ApplyResult? receipt, byte[]? payload) => Encode(w =>
    {
        Start(w, nonce, "action"); w.WriteNull("parent"); Child(w, child);
        if (receipt is null) Payload(w, payload);
        else
        {
            w.WritePropertyName("payload"); w.WriteStartObject();
            w.WriteString("version", receipt.Version); w.WriteString("session_nonce", receipt.SessionNonce);
            w.WriteString("decision_id", receipt.DecisionId); w.WriteString("action_id", receipt.ActionId);
            w.WriteString("outcome", receipt.Outcome); w.WriteEndObject();
        }
        w.WriteEndObject();
    });

    internal static byte[] Error(string nonce, string code) => Encode(w =>
    {
        Start(w, nonce, "error"); w.WriteNull("parent"); w.WriteNull("child");
        w.WriteStartObject("payload"); w.WriteString("code", code); w.WriteEndObject(); w.WriteEndObject();
    });

    internal static byte[] Request(string decision, string action, int ordinal,
        string? parentDecision, string? parentAction) => Encode(w =>
    {
        w.WriteStartObject(); w.WriteString("decision_id", decision); w.WriteString("action_id", action);
        if (ordinal == 0) w.WriteNull("child");
        else
        {
            w.WriteStartObject("child"); w.WriteNumber("ordinal", ordinal);
            w.WriteString("parent_decision_id", parentDecision); w.WriteString("parent_action_id", parentAction);
            w.WriteEndObject();
        }
        w.WriteEndObject();
    });

    internal static byte[] CardReward(object value)=>Encode(w=>{
        w.WriteStartObject();w.WriteString("version","card_reward_v1");
        if(value is GenericEventV7RewardRead p) {
            w.WriteString("session_nonce",p.SessionNonce);w.WriteString("status",p.Status);w.WriteString("phase",p.Phase);w.WriteString("decision_id",p.DecisionId);
            w.WriteStartArray("cards");foreach(var c in p.Cards){w.WriteStartObject();w.WriteNumber("slot",c.Slot);w.WriteString("key",c.Key);w.WriteNumber("upgrade_level",c.UpgradeLevel);w.WriteEndObject();}w.WriteEndArray();
            w.WriteBoolean("can_skip",p.CanSkip);Strings(w,"legal_actions",p.LegalActions);
            w.WriteStartArray("prior_results");foreach(var h in p.PriorResults){w.WriteStartObject();w.WriteString("decision_id",h.DecisionId);w.WriteString("action_id",h.ActionId);w.WriteString("result",h.Result);w.WriteEndObject();}w.WriteEndArray();
            if(p.SelectedSlot is {} slot)w.WriteNumber("selected_slot",slot);else w.WriteNull("selected_slot");
        }else if(value is GenericEventV7RewardReceipt receipt) {
            w.WriteString("session_nonce",receipt.SessionNonce);w.WriteString("decision_id",receipt.DecisionId);w.WriteString("action_id",receipt.ActionId);w.WriteString("outcome",receipt.Outcome);
        }else throw new InvalidOperationException("Wrong card reward value.");
        w.WriteEndObject();
    });

    private static void Start(Utf8JsonWriter w, string nonce, string kind)
    {
        w.WriteStartObject(); w.WriteNumber("schema_version", 1);
        w.WriteString("protocol", GenericEventV7Limits.Version); w.WriteString("session_nonce", nonce);
        w.WriteString("kind", kind);
    }
    private static void Child(Utf8JsonWriter w, GenericEventV7Child? c)
    {
        if (c is null) { w.WriteNull("child"); return; }
        w.WriteStartObject("child"); w.WriteNumber("ordinal", c.Ordinal);
        w.WriteString("parent_decision_id", c.ParentDecisionId); w.WriteString("parent_action_id", c.ParentActionId);
        w.WriteString("kind", c.Kind); w.WriteString("contract_version", c.ContractVersion);
        if (c.Kind is "item" or "card_reward") { w.WriteNumber("offer_count", c.OfferCount); w.WriteEndObject(); return; }
        w.WriteString("operation", c.Operation); w.WriteNumber("min_select", c.MinSelect);
        w.WriteNumber("max_select", c.MaxSelect); w.WriteString("commit_mode", c.CommitMode);
        w.WriteNumber("domain_count", c.DomainCount); w.WriteEndObject();
    }
    private static void Payload(Utf8JsonWriter w, byte[]? payload)
    {
        w.WritePropertyName("payload");
        if (payload is null) w.WriteNullValue();
        else w.WriteRawValue(payload);
    }
    private static void Strings(Utf8JsonWriter w, string name, IReadOnlyList<string> values)
    { w.WriteStartArray(name); foreach (var value in values) w.WriteStringValue(value); w.WriteEndArray(); }
    private static byte[] Encode(Action<Utf8JsonWriter> write)
    {
        var buffer = new ArrayBufferWriter<byte>();
        try
        {
            using (var writer = new Utf8JsonWriter(buffer)) write(writer);
            if (buffer.WrittenCount > 65536) throw new InvalidOperationException("Response too large.");
            return buffer.WrittenSpan.ToArray();
        }
        finally { buffer.Clear(); }
    }
}
