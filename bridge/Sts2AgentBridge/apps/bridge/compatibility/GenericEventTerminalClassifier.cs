using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Successors.GenericEventV7;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV10;

internal enum TerminalClassification
{
    Invalid = 0,
    NonTerminal = 1,
    Terminal = 2,
}


internal static class GenericEventTerminalClassifier
{
    internal static TerminalClassification Classify(GenericEventTransportRoute route, GenericEventReleaseSelection selection,
        string nonce, int statusCode, byte[] body)
    {
        if (!Enum.IsDefined(route) || selection != GenericEventReleaseSelection.Generic || statusCode != 200 ||
            body.Length is < 1 or > 65536 || !Hex(nonce, 32)) return TerminalClassification.Invalid;
        byte[]? canonical = null;
        try
        {
            foreach (byte b in body) if (b is < 0x20 or > 0x7e) return TerminalClassification.Invalid;
            using var document = JsonDocument.Parse(body, new JsonDocumentOptions { MaxDepth = 12 });
            var root = document.RootElement;
            if (!Bounded(root) || !Keys(root, "schema_version", "protocol", "session_nonce", "kind", "parent", "child", "payload") ||
                root.GetProperty("schema_version").GetInt32() != 1 || Text(root,"protocol") != "generic_event_v7" || Text(root,"session_nonce") != nonce)
                return TerminalClassification.Invalid;
            canonical = JsonSerializer.SerializeToUtf8Bytes(root);
            if (!body.AsSpan().SequenceEqual(canonical)) return TerminalClassification.Invalid;
            var parent=root.GetProperty("parent"); var child=root.GetProperty("child"); var payload=root.GetProperty("payload");
            string? kind=Text(root,"kind");
            if (kind == "error") return Null(parent) && Null(child) && Keys(payload,"code") &&
                Text(payload,"code") is "invalid_request" or "internal_failure" or "unsupported" ? TerminalClassification.Terminal : TerminalClassification.Invalid;
            if (!Null(child) && !Child(child)) return TerminalClassification.Invalid;
            if (kind == "action")
            {
                if (route == GenericEventTransportRoute.DecisionGet || !Null(parent) || payload.ValueKind != JsonValueKind.Object ||
                    Text(payload,"session_nonce") != nonce) return TerminalClassification.Invalid;
                if (route == GenericEventTransportRoute.ParentPost)
                {
                    if (!Null(child) || !Keys(payload,"version","session_nonce","decision_id","action_id","outcome") ||
                        Text(payload,"version") != "generic_event_v7") return TerminalClassification.Invalid;
                }
                else if (!Null(child) && Text(child,"kind")=="item") return Item(payload,nonce,true);
                else if (!Null(child) && Text(child,"kind")=="card_reward") return Reward(payload,child,nonce,true);
                else if (Null(child) || Text(payload,"version") != Text(child,"contract_version") ||
                    Text(payload,"kind") is not ("child_receipt" or "child_failure") || payload.GetProperty("schema_version").GetInt32()!=1)
                    return TerminalClassification.Invalid;
                string? outcome=Text(payload,"outcome");
                if(route==GenericEventTransportRoute.ParentPost)
                {
                    if(!Hex(Text(payload,"decision_id"),64) || !GenericEventTransportRequestParser.ParentActionValue(Encoding.ASCII.GetBytes(Text(payload,"action_id")??"")))return TerminalClassification.Invalid;
                    return outcome switch { "accepted"=>TerminalClassification.NonTerminal,
                        "unsupported" or "stale_decision" or "illegal_action" or "uncertain" or "budget_exhausted"=>TerminalClassification.Terminal,
                        _=>TerminalClassification.Invalid };
                }
                if(payload.GetProperty("parent_ordinal").GetInt32()!=1)return TerminalClassification.Invalid;
                if(Text(payload,"kind")=="child_failure")
                    return Keys(payload,"schema_version","kind","version","session_nonce","parent_ordinal","outcome") && outcome is "unsupported" or "uncertain" or "rejected" ? TerminalClassification.Terminal : TerminalClassification.Invalid;
                return Keys(payload,"schema_version","kind","version","session_nonce","parent_ordinal","decision_id","action_id","outcome") &&
                    Hex(Text(payload,"decision_id"),64) && CardAction(Text(payload,"action_id")??"") && outcome=="accepted" ? TerminalClassification.NonTerminal : TerminalClassification.Invalid;
            }
            if (kind != "decision" || route != GenericEventTransportRoute.DecisionGet || parent.ValueKind != JsonValueKind.Object)
                return TerminalClassification.Invalid;
            string? status=Text(parent,"status"),phase=Text(parent,"phase");
            if (status == "child")
            {
                if (!Null(child) && Text(child,"kind")=="item") return Text(child,"contract_version")=="item_set_v1" ? ItemSet(payload,child,nonce) : Item(payload,nonce,false);
                if (!Null(child) && Text(child,"kind")=="card_reward") return Reward(payload,child,nonce,false);
                if (Null(child) || payload.ValueKind != JsonValueKind.Object || Text(payload,"version") != Text(child,"contract_version") ||
                    Text(payload,"session_nonce") != nonce || payload.GetProperty("schema_version").GetInt32()!=1) return TerminalClassification.Invalid;
                return Text(payload,"kind") switch {
                    "child_resolved" when Text(payload,"status")=="resolved" => TerminalClassification.NonTerminal,
                    "child_observation" when Text(payload,"status") is "ready" or "waiting" => TerminalClassification.NonTerminal,
                    "child_observation" when Text(payload,"status")=="unsupported" => TerminalClassification.Terminal,
                    _ => TerminalClassification.Invalid };
            }
            if (!Null(child) || !Null(payload)) return TerminalClassification.Invalid;
            return status switch {
                "complete" when phase=="map_handoff" => TerminalClassification.Terminal,
                "unsupported" => TerminalClassification.Terminal,
                "ready" or "waiting" => TerminalClassification.NonTerminal,
                _ => TerminalClassification.Invalid };
        }
        catch { return TerminalClassification.Invalid; }
        finally { if(canonical is not null) Array.Clear(canonical); }
    }
    private static bool Child(JsonElement value) {
        bool item=Text(value,"kind") is "item" or "card_reward";
        if(!Keys(value,item?new[]{"ordinal","parent_decision_id","parent_action_id","kind","contract_version","offer_count"}:
            new[]{"ordinal","parent_decision_id","parent_action_id","kind","contract_version","operation","min_select","max_select","commit_mode","domain_count"}) ||
            value.GetProperty("ordinal").GetInt32() is <1 or >4 || !Hex(Text(value,"parent_decision_id"),64) ||
            !GenericEventTransportRequestParser.ParentActionValue(Encoding.ASCII.GetBytes(Text(value,"parent_action_id")??"")))return false;
        if(item) {
            int count=value.GetProperty("offer_count").GetInt32();
            string version=Text(value,"kind")=="item" ? (count==1?"item_v1":"item_set_v1") : (count==1?"card_reward_v1":"card_reward_set_v1");
            return count is >=1 and <=8 && (Text(value,"contract_version")==version||Text(value,"kind")=="card_reward"&&count>=2&&Text(value,"contract_version")=="mixed_reward_set_v1");
        }
        return
            Text(value,"kind")=="card_selection"&&Text(value,"contract_version")==GenericEventV7Families.ContractVersion(Text(value,"operation")??"",value.GetProperty("max_select").GetInt32())&&
            GenericEventV7Families.Supports(Text(value,"operation")??"",value.GetProperty("min_select").GetInt32(),value.GetProperty("max_select").GetInt32(),Text(value,"commit_mode")??"",value.GetProperty("domain_count").GetInt32());
    }
    // The wire service validates action history and native effects. This boundary
    // validates the emitted family and keeps child completion owned by its parent.
    private static bool CardAction(string action) => !action.StartsWith("collect:",StringComparison.Ordinal) &&
        !GenericEventTransportRequestParser.RewardAction(Encoding.ASCII.GetBytes(action)) &&
        GenericEventTransportRequestParser.ChildAction(Encoding.ASCII.GetBytes(action));

    private static TerminalClassification ItemSet(JsonElement p,JsonElement child,string nonce) {
        if(!Keys(p,"version","session_nonce","status","offer_count","collected","current") ||
            Text(p,"version")!="item_set_v1" || Text(p,"session_nonce")!=nonce ||
            p.GetProperty("offer_count").GetInt32()!=child.GetProperty("offer_count").GetInt32())return TerminalClassification.Invalid;
        int count=p.GetProperty("offer_count").GetInt32();
        var collected=p.GetProperty("collected");var current=p.GetProperty("current");
        if(collected.ValueKind!=JsonValueKind.Array || collected.GetArrayLength()>count)return TerminalClassification.Invalid;
        int index=0;
        foreach(var entry in collected.EnumerateArray()) {
            if(Item(entry,nonce,false)!=TerminalClassification.NonTerminal || Text(entry,"status")!="resolved" ||
                entry.GetProperty("offer_index").GetInt32()!=index++)return TerminalClassification.Invalid;
        }
        string? status=Text(p,"status");
        if(status=="resolved")return index==count && Null(current)?TerminalClassification.NonTerminal:TerminalClassification.Invalid;
        if(status=="unsupported")return Null(current)?TerminalClassification.Terminal:TerminalClassification.Invalid;
        if(status=="waiting")return Null(current) || Text(current,"status")=="waiting" && Item(current,nonce,false)==TerminalClassification.NonTerminal
            ?TerminalClassification.NonTerminal:TerminalClassification.Invalid;
        if(status!="ready" || index>=count || Null(current) || Item(current,nonce,false)!=TerminalClassification.NonTerminal ||
            Text(current,"status")!="ready" || current.GetProperty("offers")[0].GetProperty("index").GetInt32()!=index)return TerminalClassification.Invalid;
        return TerminalClassification.NonTerminal;
    }

    private static TerminalClassification Reward(JsonElement p,JsonElement child,string nonce,bool apply) {
        if(p.ValueKind!=JsonValueKind.Object || Text(p,"version")!=Text(child,"contract_version") || Text(p,"session_nonce")!=nonce)return TerminalClassification.Invalid;
        bool mixed=Text(child,"contract_version")=="mixed_reward_set_v1";
        bool set=mixed||Text(child,"contract_version")=="card_reward_set_v1";
        int count=child.GetProperty("offer_count").GetInt32();
        bool Action(string? action) {
            if(mixed&&Collect(action,out int collected)&&collected<count)return true;
            if(action is null || !GenericEventTransportRequestParser.RewardAction(Encoding.ASCII.GetBytes(action)))return false;
            if(action=="dismiss")return true;
            if(!set)return action is "open" or "skip" || action.Length==8 && action.StartsWith("choose:",StringComparison.Ordinal);
            return action.Length==6 && action[5]-'0'<count || action.Length==10 && action[7]-'0'<count;
        }
        if(apply) {
            if(!Keys(p,"version","session_nonce","decision_id","action_id","outcome") || !Hex(Text(p,"decision_id"),64) || !Action(Text(p,"action_id")))return TerminalClassification.Invalid;
            return Text(p,"outcome") switch {"accepted"=>TerminalClassification.NonTerminal,
                "rejected" or "unsupported" or "uncertain"=>TerminalClassification.Terminal,_=>TerminalClassification.Invalid};
        }
        string[] common={"version","session_nonce","status","phase","decision_id","cards","can_skip","legal_actions","prior_results","selected_slot"};
        if(!Keys(p,set?System.Linq.Enumerable.ToArray(System.Linq.Enumerable.Concat(common,(mixed?new[]{"offer_count","offer_index","settled","offer_kinds","item"}:new[]{"offer_count","offer_index","settled"}))):common))return TerminalClassification.Invalid;
        if(set) {
            var settled=p.GetProperty("settled");
            if(p.GetProperty("offer_count").GetInt32()!=count || settled.ValueKind!=JsonValueKind.Array || settled.GetArrayLength()>count ||
                p.GetProperty("offer_index").GetInt32()!=settled.GetArrayLength() || !Null(p.GetProperty("selected_slot")))return TerminalClassification.Invalid;
        }
        if(mixed) {
            var kinds=p.GetProperty("offer_kinds");var item=p.GetProperty("item");int index=p.GetProperty("offer_index").GetInt32();
            if(kinds.ValueKind!=JsonValueKind.Array||kinds.GetArrayLength()!=count)return TerminalClassification.Invalid;
            bool card=false,other=false;
            foreach(var k in kinds.EnumerateArray()){string? text=k.GetString();if(text=="card")card=true;else if(text is "potion" or "relic")other=true;else return TerminalClassification.Invalid;}
            if(!card||!other)return TerminalClassification.Invalid;
            if(Text(p,"phase")=="collect") {
                if(Text(p,"status")!="ready"||index>=count||kinds[index].GetString()=="card"||Item(item,nonce,false)!=TerminalClassification.NonTerminal||Text(item,"status")!="ready"||
                    Text(item,"decision_id")!=Text(p,"decision_id")||item.GetProperty("offers")[0].GetProperty("index").GetInt32()!=index||
                    Text(item.GetProperty("offers")[0],"kind")!=kinds[index].GetString()||p.GetProperty("cards").GetArrayLength()!=0||p.GetProperty("can_skip").GetBoolean()||
                    p.GetProperty("legal_actions").GetArrayLength()!=1||p.GetProperty("legal_actions")[0].GetString()!="collect:"+index)return TerminalClassification.Invalid;
            }else if(!Null(item))return TerminalClassification.Invalid;
        }
        var cards=p.GetProperty("cards");var actions=p.GetProperty("legal_actions");var history=p.GetProperty("prior_results");
        if(cards.ValueKind!=JsonValueKind.Array || cards.GetArrayLength()>5 || actions.ValueKind!=JsonValueKind.Array || actions.GetArrayLength()>6 ||
            history.ValueKind!=JsonValueKind.Array || history.GetArrayLength()>2*count+1 || p.GetProperty("can_skip").ValueKind is not (JsonValueKind.True or JsonValueKind.False))return TerminalClassification.Invalid;
        foreach(var action in actions.EnumerateArray())if(!Action(action.GetString()))return TerminalClassification.Invalid;
        string? status=Text(p,"status"),phase=Text(p,"phase");
        if(status=="ready")return Hex(Text(p,"decision_id"),64) && actions.GetArrayLength()>0 && (phase is "open" or "choose" or "dismiss" || mixed&&phase=="collect")
            ?TerminalClassification.NonTerminal:TerminalClassification.Invalid;
        if(Text(p,"decision_id")!="" || cards.GetArrayLength()!=0 || actions.GetArrayLength()!=0 || p.GetProperty("can_skip").GetBoolean())return TerminalClassification.Invalid;
        return (status,phase) switch {("waiting","waiting")=>TerminalClassification.NonTerminal,
            ("resolved","complete") when !set || p.GetProperty("offer_index").GetInt32()==count=>TerminalClassification.NonTerminal,
            ("unsupported","unsupported")=>TerminalClassification.Terminal,_=>TerminalClassification.Invalid};
    }
    private static TerminalClassification Item(JsonElement p,string nonce,bool apply) {
        if(p.ValueKind!=JsonValueKind.Object||p.GetProperty("schema_version").GetInt32()!=1||Text(p,"protocol")!="item_probe_v1"||
            Text(p,"version")!="item_v1"||Text(p,"session_nonce")!=nonce||p.GetProperty("surface_ordinal").GetInt32()!=1)return TerminalClassification.Invalid;
        string? status=Text(p,"status");
        string[] common={"schema_version","protocol","version","session_nonce","surface_ordinal","status"};
        bool Shape(params string[] suffix)=>Keys(p,System.Linq.Enumerable.ToArray(System.Linq.Enumerable.Concat(common,suffix)));
        bool Correlation()=>Hex(Text(p,"decision_id"),64)&&Collect(Text(p,"action_id"),out _);
        if(apply) {
            if(status is "rejected" or "unsupported" or "uncertain")return Shape()?TerminalClassification.Terminal:TerminalClassification.Invalid;
            return status=="accepted"&&Shape("decision_id","action_id")&&Correlation()?TerminalClassification.NonTerminal:TerminalClassification.Invalid;
        }
        if(status is "waiting" or "unsupported")return Shape()?(status=="waiting"?TerminalClassification.NonTerminal:TerminalClassification.Terminal):TerminalClassification.Invalid;
        if(status=="resolved")return Shape("decision_id","action_id","offer_index","kind","key","result")&&Correlation()&&
            Collect(Text(p,"action_id"),out int index)&&p.GetProperty("offer_index").GetInt32()==index&&Text(p,"kind") is "potion" or "relic"&&
            Sts2AgentBridge.Successors.ItemV1.ItemV1CanonicalEncoder.IsStableKey(Text(p,"key"))&&Text(p,"result")=="collected"?TerminalClassification.NonTerminal:TerminalClassification.Invalid;
        if(status!="ready"||!Shape("decision_id","offers","potion_slots","legal_actions")||!Hex(Text(p,"decision_id"),64))return TerminalClassification.Invalid;
        var offers=p.GetProperty("offers");var slots=p.GetProperty("potion_slots");var actions=p.GetProperty("legal_actions");
        if(offers.ValueKind!=JsonValueKind.Array||offers.GetArrayLength()!=1||slots.ValueKind!=JsonValueKind.Array||slots.GetArrayLength()>8||actions.ValueKind!=JsonValueKind.Array||actions.GetArrayLength()!=1)return TerminalClassification.Invalid;
        var offer=offers[0];if(!Keys(offer,"index","kind","key","enabled")||!offer.GetProperty("enabled").GetBoolean()||Text(offer,"kind") is not ("potion" or "relic")||!Sts2AgentBridge.Successors.ItemV1.ItemV1CanonicalEncoder.IsStableKey(Text(offer,"key")))return TerminalClassification.Invalid;
        if(!Collect(actions[0].GetString(),out int selected)||selected!=offer.GetProperty("index").GetInt32())return TerminalClassification.Invalid;
        bool empty=false;foreach(var slot in slots.EnumerateArray()){if(Null(slot))empty=true;else if(slot.ValueKind!=JsonValueKind.String||!Sts2AgentBridge.Successors.ItemV1.ItemV1CanonicalEncoder.IsStableKey(slot.GetString()))return TerminalClassification.Invalid;}
        return Text(offer,"kind")=="relic"||empty?TerminalClassification.NonTerminal:TerminalClassification.Invalid;
    }
    private static bool Collect(string? value,out int index) {
        index=-1;return value is not null&&Sts2AgentBridge.Successors.ItemWireV1.ItemWireV1Protocol.IsCanonicalActionId(value,out index);
    }
    private static bool Null(JsonElement value)=>value.ValueKind==JsonValueKind.Null;
    private static string? Text(JsonElement value,string key)=>value.GetProperty(key).GetString();
    private static bool Hex(string? value,int size)
    { if(value is null || value.Length!=size)return false;foreach(char c in value)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;return true; }
    private static bool Keys(JsonElement value,params string[] keys)
    { if(value.ValueKind!=JsonValueKind.Object)return false;int i=0;foreach(var p in value.EnumerateObject()){if(i==keys.Length||p.Name!=keys[i++])return false;}return i==keys.Length; }
    private static bool Bounded(JsonElement value)
    {
        if(value.ValueKind==JsonValueKind.Object){var keys=new HashSet<string>(StringComparer.Ordinal);foreach(var p in value.EnumerateObject())if(keys.Count==64||p.Name.Length>64||!keys.Add(p.Name)||!Bounded(p.Value))return false;return true;}
        if(value.ValueKind==JsonValueKind.Array){if(value.GetArrayLength()>128)return false;foreach(var v in value.EnumerateArray())if(!Bounded(v))return false;return true;}
        return value.ValueKind switch { JsonValueKind.String => value.GetString()!.Length<=4096,JsonValueKind.Number=>value.TryGetInt64(out _),JsonValueKind.True or JsonValueKind.False or JsonValueKind.Null=>true,_=>false };
    }
}
