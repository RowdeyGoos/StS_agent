using System;
using System.Buffers;
using System.Collections.Generic;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;

namespace Sts2AgentBridge.Successors.GenericEventV5;

internal static class CardTransformV2WireCodec
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
                case CardSelectionV1Observation item:
                    if (item.Status == "ready" && item.Operation != "transform") throw new InvalidOperationException("Wrong transform operation.");
                    ChildObservation(writer, item); break;
                case CardSelectionV1ResolvedResult item:
                    if (item.Operation != "transform") throw new InvalidOperationException("Wrong transform operation.");
                    ChildResolved(writer, item); break;
                case CardSelectionV1DispatchReceipt item: ChildReceipt(writer, item); break;
                case CardSelectionV1ApplyFailure item: ChildFailure(writer, item); break;
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

    private static void ChildObservation(Utf8JsonWriter w, CardSelectionV1Observation x)
    {
        w.WriteString("kind", "child_observation"); Common(w, "card_transform_v2", x.SessionNonce, x.ParentOrdinal);
        w.WriteString("status", x.Status); w.WriteString("phase", x.Phase); w.WriteString("operation", x.Operation);
        w.WriteString("commit_mode", x.CommitMode); w.WriteNumber("min_select", x.MinSelect); w.WriteNumber("max_select", x.MaxSelect);
        w.WriteString("decision_id", x.DecisionId); Candidates(w, "candidates", x.Candidates);
        Ints(w, "selected_slots", x.SelectedSlots); Strings(w, "legal_actions", x.LegalActions);
        Results(w, x.PriorResults);
    }
    private static void ChildResolved(Utf8JsonWriter w, CardSelectionV1ResolvedResult x)
    {
        w.WriteString("kind", "child_resolved"); Common(w, "card_transform_v2", x.SessionNonce, x.ParentOrdinal);
        w.WriteString("status", x.Status); w.WriteString("phase", x.Phase); w.WriteString("operation", x.Operation);
        Candidates(w, "selected_cards", x.SelectedCards); Results(w, x.PriorResults);
    }
    private static void ChildReceipt(Utf8JsonWriter w, CardSelectionV1DispatchReceipt x)
    {
        w.WriteString("kind", "child_receipt"); Common(w, "card_transform_v2", x.SessionNonce, x.ParentOrdinal);
        w.WriteString("decision_id", x.DecisionId); w.WriteString("action_id", x.ActionId); w.WriteString("outcome", x.Outcome);
    }
    private static void ChildFailure(Utf8JsonWriter w, CardSelectionV1ApplyFailure x)
    {
        w.WriteString("kind", "child_failure"); Common(w, "card_transform_v2", x.SessionNonce, x.ParentOrdinal); w.WriteString("outcome", x.Outcome);
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

internal static class CardEnchantV1WireCodec
{
    public static byte[] Encode(object value)
    {
        CardSelectionV1EnchantmentEffect? enchantment = value switch
        {
            CardSelectionV1Observation o when o.Status != "ready" || o.Operation == "enchant" => o.Enchantment,
            CardSelectionV1ResolvedResult r when r.Operation == "enchant" => r.Enchantment,
            CardSelectionV1DispatchReceipt or CardSelectionV1ApplyFailure => null,
            _ => throw new InvalidOperationException("Wrong enchantment wire value.")
        };
        byte[] source = CardSelectionV1WireCodec.Encode(value);
        try
        {
            using var document = JsonDocument.Parse(source);
            var buffer = new ArrayBufferWriter<byte>();
            using (var writer = new Utf8JsonWriter(buffer))
            {
                writer.WriteStartObject();
                foreach (var property in document.RootElement.EnumerateObject())
                {
                    if (property.Name == "version") writer.WriteString("version", "card_enchant_v1");
                    else property.WriteTo(writer);
                }
                if (value is CardSelectionV1Observation or CardSelectionV1ResolvedResult)
                {
                    writer.WritePropertyName("enchantment");
                    if (enchantment is null) writer.WriteNullValue();
                    else
                    {
                        writer.WriteStartObject();
                        writer.WriteString("key", enchantment.Key);
                        writer.WriteNumber("amount", enchantment.Amount);
                        writer.WriteEndObject();
                    }
                }
                writer.WriteEndObject();
            }
            if (buffer.WrittenCount > CardSelectionV1WireProtocol.MaximumResponseBytes)
                throw new InvalidOperationException("Enchantment response exceeded its cap.");
            return buffer.WrittenSpan.ToArray();
        }
        finally { Array.Clear(source); }
    }
}

internal static class CardRemoveV2WireCodec
{
    public static byte[] Encode(object value)
    {
        if(value is CardSelectionV1Observation o && o.Status=="ready" && o.Operation!="remove" ||
            value is CardSelectionV1ResolvedResult r && r.Operation!="remove")
            throw new InvalidOperationException("Wrong removal wire value.");
        byte[] source=CardSelectionV1WireCodec.Encode(value);
        try
        {
            using var document=JsonDocument.Parse(source);
            var buffer=new ArrayBufferWriter<byte>();
            using(var writer=new Utf8JsonWriter(buffer))
            {
                writer.WriteStartObject();
                foreach(var property in document.RootElement.EnumerateObject())
                    if(property.Name=="version") writer.WriteString("version","card_remove_v2");
                    else property.WriteTo(writer);
                if(value is CardSelectionV1ResolvedResult done)
                {
                    writer.WriteStartObject("parent_additions");
                    writer.WriteString("status","unverified");
                    writer.WriteStartArray("cards");
                    foreach(var card in done.ParentAddedCards)
                    {
                        writer.WriteStartObject();
                        writer.WriteString("key",card.Key);
                        writer.WriteNumber("upgrade_level",card.UpgradeLevel);
                        writer.WritePropertyName("enchantment");
                        if(card.Enchantment is {} e) {
                            writer.WriteStartObject();writer.WriteString("key",e.Key);
                            writer.WriteNumber("amount",e.Amount);writer.WriteEndObject();
                        } else writer.WriteNullValue();
                        writer.WriteEndObject();
                    }
                    writer.WriteEndArray();writer.WriteEndObject();
                }
                writer.WriteEndObject();
            }
            if(buffer.WrittenCount>CardSelectionV1WireProtocol.MaximumResponseBytes)
                throw new InvalidOperationException("Removal response exceeded its cap.");
            return buffer.WrittenSpan.ToArray();
        }
        finally { Array.Clear(source); }
    }
}
