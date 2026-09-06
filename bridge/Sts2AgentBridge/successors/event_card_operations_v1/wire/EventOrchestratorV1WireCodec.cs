using System;
using System.Buffers;
using System.Linq;
using System.Text.Json;
using System.Text;
using System.Globalization;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.ItemWireV1;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1;

internal static class EventOrchestratorV1WireCodec
{
    internal static byte[] Wrap(string nonce, EventOrchestratorV1ChildEnvelope? child, byte[] payload)
    {
        var b = new ArrayBufferWriter<byte>();
        try
        {
            using (var w = new Utf8JsonWriter(b))
            {
                w.WriteStartObject(); w.WriteNumber("schema_version",1); w.WriteString("protocol",EventOrchestratorV1Limits.Version);
                w.WriteString("session_nonce",nonce); w.WritePropertyName("child"); Child(w,child);
                w.WritePropertyName("payload"); w.WriteRawValue(payload); w.WriteEndObject();
            }
            if (b.WrittenCount > 65536) throw new InvalidOperationException("Response limit.");
            return b.WrittenSpan.ToArray();
        }
        finally { b.Clear(); Array.Clear(payload); }
    }
    internal static void Child(Utf8JsonWriter w, EventOrchestratorV1ChildEnvelope? c)
    {
        if(c is null){w.WriteNullValue();return;}
        w.WriteStartObject();w.WriteString("kind",c.Kind);w.WriteNumber("child_ordinal",c.ChildOrdinal);
        w.WriteString("parent_decision_id",c.ParentDecisionId);w.WriteString("parent_action_id",c.ParentActionId);w.WriteEndObject();
    }
    private static void Prior(Utf8JsonWriter w,EventOrchestratorV1PriorResult? p)
    {
        if(p is null){w.WriteNullValue();return;}
        if(p.Result is not ("option_transition" or "child_completed" or "map_handoff"))throw new InvalidOperationException();
        w.WriteStartObject();w.WriteString("decision_id",p.DecisionId);w.WriteString("action_id",p.ActionId);w.WriteString("result",p.Result);
        w.WritePropertyName("child");Child(w,p.Child);w.WriteEndObject();
    }
    internal static byte[] Parent(string nonce,object value)
    {
        var b=new ArrayBufferWriter<byte>();
        try
        {
        using(var w=new Utf8JsonWriter(b))
        {
            w.WriteStartObject();w.WriteNumber("schema_version",1);
            string kind=value switch {EventOrchestratorV1Observation=>"parent_observation",EventOrchestratorV1ResolvedResult=>"parent_resolved",RoomFlowDispatchReceipt=>"parent_receipt",RoomFlowApplyFailure=>"parent_failure",_=>throw new InvalidOperationException()};
            w.WriteString("kind",kind);w.WriteString("version",EventOrchestratorV1Limits.Version);w.WriteString("session_nonce",nonce);w.WriteNumber("parent_ordinal",1);
            switch(value)
            {
                case EventOrchestratorV1Observation x:
                    if(x.Status=="child")throw new InvalidOperationException("Internal child signal.");
                    w.WriteString("status",x.Status);w.WriteString("phase",x.Phase);w.WriteString("decision_id",x.DecisionId);
                    w.WriteStartArray("candidates");foreach(var c in x.Candidates)
                    {w.WriteStartObject();w.WriteNumber("candidate_index",c.CandidateIndex);w.WriteString("action_id",c.ActionId);w.WriteString("stable_id",c.StableId);w.WriteString("rendered_text",c.RenderedText);w.WriteBoolean("enabled",c.Enabled);w.WriteBoolean("is_dangerous",c.IsDangerous);w.WriteBoolean("is_proceed",c.IsProceed);w.WriteString("child_policy",c.ChildPolicy);w.WriteNumber("child_domain_count",c.ChildDomainCount);w.WriteEndObject();}w.WriteEndArray();
                    w.WriteStartArray("legal_actions");foreach(string a in x.LegalActions)w.WriteStringValue(a);w.WriteEndArray();
                    w.WritePropertyName("child");Child(w,x.Child);w.WritePropertyName("prior_result");Prior(w,x.PriorResult);break;
                case EventOrchestratorV1ResolvedResult x:
                    w.WriteString("status","resolved");w.WriteString("phase","complete");w.WriteString("decision_id",x.DecisionId);w.WriteString("action_id",x.ActionId);w.WriteString("result",x.Result);w.WritePropertyName("prior_result");Prior(w,x.PriorResult);break;
                case RoomFlowDispatchReceipt x:
                    w.WriteString("status","accepted");w.WriteString("decision_id",x.DecisionId);w.WriteString("action_id",x.ActionId);break;
                case RoomFlowApplyFailure x:
                    w.WriteString("status","failed");w.WriteString("code",x.Outcome);break;
            }
            w.WriteEndObject();
        }
        return CanonicalParent(b.WrittenSpan.ToArray());
        }
        finally { b.Clear(); }
    }
    // Parent text uses the same compact ASCII escape convention as the host.
    // Frozen item/card payloads bypass this conversion and retain their bytes.
    private static byte[] CanonicalParent(byte[] input)
    {
        try
        {
            using var document=JsonDocument.Parse(input);
            var text=new StringBuilder();
            void String(string value)
            {
                text.Append('"');
                foreach(char c in value)
                {
                    switch(c)
                    {
                        case '"':text.Append("\\\"");break;
                        case '\\':text.Append("\\\\");break;
                        case '\b':text.Append("\\b");break;
                        case '\f':text.Append("\\f");break;
                        case '\n':text.Append("\\n");break;
                        case '\r':text.Append("\\r");break;
                        case '\t':text.Append("\\t");break;
                        default:
                            if(c<' '||c>'~')text.Append("\\u").Append(((int)c).ToString("x4",CultureInfo.InvariantCulture));
                            else text.Append(c);
                            break;
                    }
                }
                text.Append('"');
            }
            void Value(JsonElement e)
            {
                switch(e.ValueKind)
                {
                    case JsonValueKind.Object:
                        text.Append('{');bool first=true;
                        foreach(var p in e.EnumerateObject()){if(!first)text.Append(',');first=false;String(p.Name);text.Append(':');Value(p.Value);}text.Append('}');break;
                    case JsonValueKind.Array:
                        text.Append('[');bool initial=true;
                        foreach(var v in e.EnumerateArray()){if(!initial)text.Append(',');initial=false;Value(v);}text.Append(']');break;
                    case JsonValueKind.String:String(e.GetString()!);break;
                    case JsonValueKind.Number:text.Append(e.GetInt32().ToString(CultureInfo.InvariantCulture));break;
                    case JsonValueKind.True:text.Append("true");break;
                    case JsonValueKind.False:text.Append("false");break;
                    case JsonValueKind.Null:text.Append("null");break;
                    default:throw new InvalidOperationException();
                }
            }
            Value(document.RootElement);
            return Encoding.ASCII.GetBytes(text.ToString());
        }
        finally{Array.Clear(input);}
    }
    internal static byte[] Item(object value)
    {
        ItemWireV1Envelope e=value switch {
            ItemV1Observation x=>new(x.SessionNonce,x.Status,decisionId:x.DecisionId,offers:x.Offers.Select(o=>new ItemWireV1OfferDto(o.Index,o.Kind,o.Key,o.Enabled)).ToArray(),potionSlots:x.PotionSlots,legalActions:x.LegalActions),
            ItemV1ResolvedResult x=>new(x.SessionNonce,"resolved",decisionId:x.DecisionId,actionId:x.ActionId,offerIndex:x.OfferIndex,kind:x.Kind,key:x.Key,result:x.Result),
            ItemV1DispatchReceipt x=>new(x.SessionNonce,"accepted",decisionId:x.DecisionId,actionId:x.ActionId),
            ItemV1ApplyFailure x=>new(x.SessionNonce,x.Outcome),
            _=>throw new InvalidOperationException()};
        return ItemWireV1Codec.Encode(e);
    }
    internal static byte[] Card(object value)=>CardSelectionV1WireCodec.Encode(value);
    internal static byte[] Error(string nonce,string code)
    {
        if(code is not ("invalid_request" or "internal_failure" or "unsupported"))throw new InvalidOperationException();
        return Wrap(nonce,null,JsonSerializer.SerializeToUtf8Bytes(new {schema_version=1,kind="error",status="error",code}));
    }
}
