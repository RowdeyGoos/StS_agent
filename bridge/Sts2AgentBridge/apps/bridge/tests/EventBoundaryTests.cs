using System;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Unified;
using Sts2AgentBridge.Successors.ItemWireV1;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV5;
using Sts2AgentBridge.Successors.GenericEventReleaseV10;
using Sts2AgentBridge.Successors.CardSelectionV1;

internal static class EventBoundaryTests
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static readonly string Decision = new('b',64);
    private static GenericEventV7Observation Parent(GenericEventV7Child? child,string status="child",string phase="child") =>
        new(Nonce,status,phase,"",Array.Empty<GenericEventV7Candidate>(),Array.Empty<string>(),child,
            Array.Empty<GenericEventV7PriorResult>(),1,1,0,child is null?0:1,0,0,0,"unverified");
    private static TerminalClassification Classify(byte[] body,GenericEventTransportRoute route=GenericEventTransportRoute.DecisionGet) =>
        GenericEventTerminalClassifier.Classify(route,GenericEventReleaseSelection.Generic,Nonce,200,body);
    private static byte[] Mutate(byte[] body,Action<JsonNode> edit) {
        var root=JsonNode.Parse(body)!;edit(root);return JsonSerializer.SerializeToUtf8Bytes(root);
    }
    private static byte[] Header(string action,bool child=true,string path="/probe/generic-event-v7/public/action") => Encoding.ASCII.GetBytes(
        "POST "+path+" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "+new string('a',64)+
        "\r\nAccept: application/json\r\nX-Sts2-Decision-Id: "+Decision+"\r\nX-Sts2-Action-Id: "+action+"\r\n"+
        (child?"X-Sts2-Child-Ordinal: 1\r\nX-Sts2-Parent-Decision-Id: "+Decision+"\r\nX-Sts2-Parent-Action-Id: choose:0\r\n":"")+
        "Connection: close\r\n\r\n");

    internal static void Run(Action<bool,string> check)
    {
        foreach(int count in new[]{1,2,8}) {
            var child=new GenericEventV7Child(1,Decision,"choose:0","enchant",count,count,"preview_confirm",20);
            var observation=new CardSelectionV1Observation(Nonce,"waiting","transient","","",0,0,"",
                Array.Empty<CardSelectionV1Candidate>(),Array.Empty<int>(),Array.Empty<string>(),Array.Empty<CardSelectionV1ActionResult>());
            var body=GenericEventV7WireCodec.Decision(Nonce,Parent(child),CardEnchantV1WireCodec.Encode(observation,count>1));
            check(Classify(body)==TerminalClassification.NonTerminal,"enchantment production boundary count "+count);
            check(Classify(Mutate(body,n=>n["child"]!["contract_version"]="card_enchant_v99"))==TerminalClassification.Invalid,"unknown enchantment version rejected");
            if(count>1)check(Classify(Mutate(body,n=>n["child"]!["contract_version"]="card_enchant_v1"))==TerminalClassification.Invalid,"multi enchantment cannot use singleton descriptor");
            var receipt=GenericEventV7WireCodec.Action(Nonce,child,null,CardEnchantV1WireCodec.Encode(new CardSelectionV1DispatchReceipt(Nonce,Decision,"select:0"),count>1));
            check(Classify(receipt,GenericEventTransportRoute.ChildPost)==TerminalClassification.NonTerminal,"enchantment accepted receipt");
            check(Classify(receipt)==TerminalClassification.Invalid,"receipt cannot be decision GET");
        }
        foreach(int count in new[]{1,2,8}) {
            var child=new GenericEventV7Child(1,Decision,"choose:0",count,true);
            string version=child.ContractVersion;
            GenericEventV7RewardRead Read(string status,string phase)=>new(Nonce,status,phase,status=="ready"?Decision:"",
                Array.Empty<GenericEventV7RewardCard>(),false,status=="ready"?new[]{count==1?"open":"open:0"}:Array.Empty<string>(),
                Array.Empty<GenericEventV7PriorResult>(),null,count,0,Array.Empty<GenericEventV7RewardSettlement>());
            foreach(var state in new[]{("ready","open"),("waiting","waiting"),("unsupported","unsupported")}) {
                var body=GenericEventV7WireCodec.Decision(Nonce,Parent(child),GenericEventV7WireCodec.CardReward(Read(state.Item1,state.Item2),version));
                check(Classify(body)==(state.Item1=="unsupported"?TerminalClassification.Terminal:TerminalClassification.NonTerminal),"reward status "+state+" count "+count);
                check(Classify(Mutate(body,n=>n["payload"]!["session_nonce"]=new string('f',32)))==TerminalClassification.Invalid,"reward nonce mismatch");
                check(Classify(Mutate(body,n=>n["child"]!["offer_count"]=9))==TerminalClassification.Invalid,"reward count overflow");
                check(Classify(Mutate(body,n=>n["payload"]!["status"]="accepted"))==TerminalClassification.Invalid,"receipt status cannot masquerade as read");
            }
            string[] actions=count==1?new[]{"open","choose:0","choose:4","skip","dismiss"}:
                Enumerable.Range(0,count).SelectMany(i=>new[]{"open:"+i,"choose:"+i+":0","choose:"+i+":4","skip:"+i}).Append("dismiss").ToArray();
            foreach(string action in actions) {
                check(BridgeRequestParser.TryParse(Header(action),out var parsed)&&parsed.Capability==Capability.Events&&parsed.IsChild&&parsed.Action==action,"shared parser reward action "+action);
                if(!action.StartsWith("choose:",StringComparison.Ordinal))check(!BridgeRequestParser.TryParse(Header(action,false),out _),"reward action needs child lineage "+action);
                foreach(string outcome in new[]{"accepted","rejected","unsupported","uncertain"}) {
                    var body=GenericEventV7WireCodec.Action(Nonce,child,null,GenericEventV7WireCodec.CardReward(new GenericEventV7RewardReceipt(Nonce,Decision,action,outcome),version));
                    check(Classify(body,GenericEventTransportRoute.ChildPost)==(outcome=="accepted"?TerminalClassification.NonTerminal:TerminalClassification.Terminal),"reward receipt "+action+" "+outcome);
                    check(Classify(body,GenericEventTransportRoute.ParentPost)==TerminalClassification.Invalid,"reward receipt cannot masquerade as parent");
                }
            }
        }
        {
            var child=new GenericEventV7Child(1,Decision,"choose:0",2,true,true);
            var item=new Sts2AgentBridge.Successors.ItemV1.ItemV1Observation(Nonce,"ready",Decision,
                new[]{new Sts2AgentBridge.Successors.ItemV1.ItemV1Offer(0,"potion","POTION",true)},new string?[]{null},new[]{"collect:0"});
            var read=new GenericEventV7RewardRead(Nonce,"ready","collect",Decision,Array.Empty<GenericEventV7RewardCard>(),false,new[]{"collect:0"},
                Array.Empty<GenericEventV7PriorResult>(),null,2,0,Array.Empty<GenericEventV7RewardSettlement>(),new[]{"potion","card"},item);
            var body=GenericEventV7WireCodec.Decision(Nonce,Parent(child),GenericEventV7WireCodec.CardReward(read,child.ContractVersion));
            check(Classify(body)==TerminalClassification.NonTerminal,"mixed native item observation remains owned");
            foreach(string change in new[]{"version","kinds","item","index","nonce","action","cards","skip"}) {
                var bad=Mutate(body,n=>{var p=n["payload"]!;
                    if(change=="version")n["child"]!["contract_version"]="card_reward_set_v1";
                    if(change=="kinds")p["offer_kinds"]![0]="card";
                    if(change=="item")p["item"]=null;
                    if(change=="index")p["item"]!["offers"]![0]!["index"]=1;
                    if(change=="nonce")p["item"]!["session_nonce"]=new string('f',32);
                    if(change=="action")p["legal_actions"]![0]="collect:1";
                    if(change=="cards")p["cards"]=new JsonArray(new JsonObject());
                    if(change=="skip")p["can_skip"]=true;
                });check(Classify(bad)==TerminalClassification.Invalid,"mixed malformed boundary "+change);
            }
            foreach(string action in new[]{"collect:0","collect:1","open:1","choose:1:4","skip:1","dismiss"}) {
                check(BridgeRequestParser.TryParse(Header(action),out var parsed)&&parsed.IsChild&&parsed.Action==action,"mixed shared request "+action);
                var receipt=GenericEventV7WireCodec.Action(Nonce,child,null,GenericEventV7WireCodec.CardReward(new GenericEventV7RewardReceipt(Nonce,Decision,action,"accepted"),child.ContractVersion));
                check(Classify(receipt,GenericEventTransportRoute.ChildPost)==TerminalClassification.NonTerminal,"mixed receipt "+action);
            }
            foreach(string action in new[]{"collect:2","collect:00","collect:255"}) {
                var receipt=GenericEventV7WireCodec.Action(Nonce,child,null,GenericEventV7WireCodec.CardReward(new GenericEventV7RewardReceipt(Nonce,Decision,action,"accepted"),child.ContractVersion));
                check(Classify(receipt,GenericEventTransportRoute.ChildPost)==TerminalClassification.Invalid,"mixed action bounds "+action);
            }
            var done=read with {Status="resolved",Phase="complete",DecisionId="",LegalActions=Array.Empty<string>(),Item=null,OfferIndex=2,
                Settled=new[]{new GenericEventV7RewardSettlement(0,null,"POTION",null,"collected","potion"),new GenericEventV7RewardSettlement(1,0,"CARD",0,"collected")}};
            check(Classify(GenericEventV7WireCodec.Decision(Nonce,Parent(child),GenericEventV7WireCodec.CardReward(done,child.ContractVersion)))==TerminalClassification.NonTerminal,"mixed child completion retains parent ownership");
        }
        foreach(int count in new[]{2,8}) {
            var child=new GenericEventV7Child(1,Decision,"choose:0",count);
            JsonNode Entry(int index) => JsonNode.Parse(ItemWireV1Codec.Encode(new ItemWireV1Envelope(Nonce,"resolved",decisionId:Decision,
                actionId:"collect:"+index,offerIndex:index,kind:"relic",key:"ANCHOR",result:"collected")))!;
            byte[] Set(string status,int completed,JsonNode? current=null) {
                var payload=new JsonObject { ["version"]="item_set_v1",["session_nonce"]=Nonce,["status"]=status,["offer_count"]=count,
                    ["collected"]=new JsonArray(Enumerable.Range(0,completed).Select(Entry).ToArray()),["current"]=current };
                return GenericEventV7WireCodec.Decision(Nonce,Parent(child),JsonSerializer.SerializeToUtf8Bytes(payload));
            }
            foreach(int completed in new[]{0,1,count}) {
                check(Classify(Set("waiting",completed))==TerminalClassification.NonTerminal,"item set pending retains parent ownership");
                check(Classify(Set("unsupported",completed))==TerminalClassification.Terminal,"item set failure retains earlier progress and stops");
            }
            var resolved=Set("resolved",count);
            check(Classify(resolved)==TerminalClassification.NonTerminal,"resolved item set retains parent ownership");
            check(Classify(Set("resolved",count-1))==TerminalClassification.Invalid,"partial set cannot resolve");
            check(Classify(Mutate(resolved,n=>n["payload"]!["collected"]![1]!["offer_index"]=0))==TerminalClassification.Invalid,"duplicate set index rejected");
            check(Classify(Mutate(resolved,n=>n["payload"]!["collected"]![0]!["session_nonce"]=new string('f',32)))==TerminalClassification.Invalid,"nested item nonce rejected");
            check(Classify(Mutate(resolved,n=>n["payload"]!["offer_count"]=count-1))==TerminalClassification.Invalid,"set count mismatch rejected");
            var ready=Set("ready",0,JsonNode.Parse(ItemWireV1Codec.Encode(new ItemWireV1Envelope(Nonce,"ready",decisionId:Decision,
                offers:new[]{new ItemWireV1OfferDto(0,"relic","ANCHOR",true)},potionSlots:Array.Empty<string?>(),legalActions:new[]{"collect:0"}))));
            check(Classify(ready)==TerminalClassification.NonTerminal,"item set current singleton payload accepted");
            check(Classify(Mutate(ready,n=>n["payload"]!["current"]!["status"]="unsupported"))==TerminalClassification.Invalid,"ready cannot conceal failed current item");
            foreach(string status in new[]{"accepted","rejected","unsupported","uncertain"}) {
                var receipt=GenericEventV7WireCodec.Action(Nonce,child,null,ItemWireV1Codec.Encode(new ItemWireV1Envelope(Nonce,status,decisionId:Decision,actionId:"collect:0")));
                check(Classify(receipt,GenericEventTransportRoute.ChildPost)==(status=="accepted"?TerminalClassification.NonTerminal:TerminalClassification.Terminal),"item set uses singleton receipt "+status);
            }
        }
        foreach(string action in new[]{"open:8","open:00","choose:5","choose:8:0","choose:0:5","choose:00:0","skip:8","dismiss:0","select:64","collect:256","choose:0:0:0","OPEN"})
            check(!BridgeRequestParser.TryParse(Header(action),out _),"invalid reward/card/item action "+action);
        check(!BridgeRequestParser.TryParse(Header("open",true,"/probe/item-v1/public/item-action"),out _),"reward action cannot use item route");
        foreach(string action in new[]{"select:0","select:63","preview","confirm","collect:0","collect:255"})
            check(BridgeRequestParser.TryParse(Header(action),out _),"existing child action preserved "+action);
        var complete=GenericEventV7WireCodec.Decision(Nonce,Parent(null,"complete","map_handoff"),null);
        check(Classify(complete)==TerminalClassification.Terminal,"only completed parent allows map handoff");
    }
}
