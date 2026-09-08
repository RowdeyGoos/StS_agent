using System;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

namespace Sts2AgentBridge.Successors.RoomFlowsV1;

internal static class RoomFlowWireCodec
{
    internal static byte[] Error(string nonce, string flow, string code) => Encode(nonce, flow, code);
    internal static byte[] Encode(string nonce, string flow, object value)
    {
        using var stream = new MemoryStream();
        using (var w = new Utf8JsonWriter(stream))
        {
            w.WriteStartObject();
            w.WriteNumber("schema_version", 1); S(w,"protocol","room_flows_v1");
            S(w,"version",flow+"_v1"); S(w,"flow_kind",flow); S(w,"session_nonce",nonce);
            w.WriteNumber("parent_ordinal",1);
            switch (value)
            {
                case string code:
                    S(w,"status","error"); S(w,"code",code); break;
                case RoomFlowDispatchReceipt receipt:
                    S(w,"status","accepted"); S(w,"decision_id",receipt.DecisionId); S(w,"action_id",receipt.ActionId); break;
                case RoomFlowApplyFailure failure:
                    S(w,"status",failure.Outcome); break;
                case ShopV1Observation shop:
                    S(w,"status",shop.Status); S(w,"phase",shop.Phase); S(w,"decision_id",shop.DecisionId);
                    w.WriteStartObject("player"); w.WriteNumber("gold",shop.Player.Gold); w.WriteNumber("deck_count",shop.Player.DeckCount); w.WriteEndObject();
                    w.WriteStartArray("offers");
                    foreach (ShopV1Offer offer in shop.Offers)
                    {
                        w.WriteStartObject(); w.WriteNumber("slot",offer.Slot); S(w,"kind",offer.Kind); S(w,"key",offer.Key);
                        w.WriteNumber("displayed_price",offer.DisplayedPrice); w.WriteBoolean("affordable",offer.Affordable);
                        w.WriteBoolean("enabled",offer.Enabled); w.WriteBoolean("supported",offer.Supported); w.WriteEndObject();
                    }
                    w.WriteEndArray(); Actions(w,shop.LegalActions); w.WriteStartArray("prior_results");
                    foreach (ShopV1ReconciledAction prior in shop.PriorResults)
                    {
                        w.WriteStartObject(); S(w,"flow_kind",prior.FlowKind); S(w,"session_nonce",prior.SessionNonce);
                        w.WriteNumber("parent_ordinal",prior.ParentOrdinal); S(w,"decision_id",prior.DecisionId);
                        S(w,"action_id",prior.ActionId); S(w,"kind",prior.Kind); S(w,"result",prior.Result); w.WriteEndObject();
                    }
                    w.WriteEndArray(); break;
                case EventV1Observation ev:
                    S(w,"status",ev.Status); S(w,"phase",ev.Phase); S(w,"decision_id",ev.DecisionId);
                    w.WriteStartArray("candidates");
                    foreach (EventV1Candidate c in ev.Candidates)
                    {
                        w.WriteStartObject(); w.WriteNumber("candidate_index",c.CandidateIndex); S(w,"action_id",c.ActionId);
                        S(w,"stable_id",c.StableId); S(w,"rendered_text",c.RenderedText); w.WriteBoolean("enabled",c.Enabled);
                        w.WriteBoolean("is_dangerous",c.IsDangerous); w.WriteBoolean("is_proceed",c.IsProceed); w.WriteEndObject();
                    }
                    w.WriteEndArray(); Actions(w,ev.LegalActions); break;
                case EventV1ResolvedResult result:
                    S(w,"status","resolved"); S(w,"decision_id",result.DecisionId);
                    S(w,"action_id",result.ActionId); S(w,"result",result.Result); break;
                default: throw new InvalidOperationException("Unknown wire value.");
            }
            w.WriteEndObject();
        }
        if (stream.Length > RoomFlowLimits.MaximumResponseBytes) throw new InvalidOperationException("Body too large.");
        return stream.ToArray();
    }
    private static void Actions(Utf8JsonWriter w, System.Collections.Generic.IReadOnlyList<string> actions)
    {
        w.WriteStartArray("legal_actions"); foreach (string action in actions) String(w, action); w.WriteEndArray();
    }
    private static void S(Utf8JsonWriter w,string name,string value) { w.WritePropertyName(name); String(w,value); }
    // Python json.dumps(ensure_ascii=True,separators=(",",":")) byte convention.
    // Encode text explicitly; no reflection or native objects enter this codec.
    private static void String(Utf8JsonWriter w,string value)
    {
        var b=new StringBuilder(); b.Append('"');
        foreach(char c in value)
        {
            switch(c)
            {
                case '"': b.Append("\\\""); break;
                case '\\': b.Append("\\\\"); break;
                case '\n': b.Append("\\n"); break;
                case '\r': b.Append("\\r"); break;
                case '\t': b.Append("\\t"); break;
                case '\b': b.Append("\\b"); break;
                case '\f': b.Append("\\f"); break;
                default:
                    if(c < 32 || c >= 127) b.Append("\\u").Append(((int)c).ToString("x4",CultureInfo.InvariantCulture));
                    else b.Append(c);
                    break;
            }
        }
        b.Append('"'); w.WriteRawValue(b.ToString(),skipInputValidation:false);
    }
}
