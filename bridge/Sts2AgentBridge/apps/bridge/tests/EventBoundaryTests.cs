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
        foreach(int count in new[]{1,10,64}) {
            var child=new GenericEventV7Child(1,Decision,"choose:0",new GenericEventV7ResultsAdmission(new object(),count));
            var cards=Enumerable.Range(0,count).Select(i=>new GenericEventV7RewardCard(i,"CARD_"+i,0)).ToArray();
            GenericEventV7RewardRead Read(string status)=>new(Nonce,status,status=="ready"?"acknowledge":status=="resolved"?"complete":status,status=="ready"?Decision:"",status is "ready" or "resolved"?cards:Array.Empty<GenericEventV7RewardCard>(),false,status=="ready"?new[]{"confirm"}:Array.Empty<string>(),status=="resolved"?new[]{new GenericEventV7PriorResult(Decision,"confirm","acknowledged")}:Array.Empty<GenericEventV7PriorResult>(),null);
            byte[] Encode(string status)=>GenericEventV7WireCodec.Decision(Nonce,Parent(child),GenericEventV7WireCodec.CardResults(Read(status)));
            foreach(string status in new[]{"ready","waiting","unsupported","resolved"})check(Classify(Encode(status))==(status=="unsupported"?TerminalClassification.Terminal:TerminalClassification.NonTerminal),"result screen boundary "+status);
            var ready=Encode("ready");
            foreach(string mutation in new[]{"version","count","slot","action","key","effect"}) {
                var invalid=Mutate(ready,n=>{switch(mutation){case "version":n["child"]!["contract_version"]="card_offer_v1";break;case "count":n["child"]!["offer_count"]=65;break;case "slot":n["payload"]!["cards"]![0]!["slot"]=true;break;case "action":n["payload"]!["legal_actions"]=new JsonArray("choose:0");break;case "key":n["payload"]!["cards"]![0]!["key"]="BAD KEY";break;case "effect":n["payload"]!["effect"]="transformed";break;}});
                check(Classify(invalid)==TerminalClassification.Invalid,"malformed results boundary "+mutation);
            }
            check(Classify(Mutate(Encode("resolved"),n=>n["payload"]!["prior_results"]![0]!["result"]="collected"))==TerminalClassification.Invalid,"acknowledgment is not collection");
            foreach(string outcome in new[]{"accepted","rejected","unsupported","uncertain"}) {
                var receipt=GenericEventV7WireCodec.Action(Nonce,child,null,GenericEventV7WireCodec.CardResults(new GenericEventV7RewardReceipt(Nonce,Decision,"confirm",outcome)));
                check(Classify(receipt,GenericEventTransportRoute.ChildPost)==(outcome=="accepted"?TerminalClassification.NonTerminal:TerminalClassification.Terminal),"results action receipt "+outcome);
            }
        }

        foreach(bool skip in new[]{false,true}) {
            var child=new GenericEventV7Child(1,Decision,"choose:0",1,"card_offer_v2");
            var offer=new[]{new GenericEventV7Offer(0,new[]{new GenericEventV7RewardCard(0,"CARD",0)})};
            var ready=new GenericEventV7RewardRead(Nonce,"ready","choose",Decision,Array.Empty<GenericEventV7RewardCard>(),false,new[]{"choose:0","skip"},Array.Empty<GenericEventV7PriorResult>(),null,Offers:offer);
            var done=ready with{Status="resolved",Phase="complete",DecisionId="",LegalActions=Array.Empty<string>(),SelectedSlot=skip?null:0,
                PriorResults=new[]{new GenericEventV7PriorResult(Decision,skip?"skip":"choose:0",skip?"skipped":"collected")},AdditionalCards=new[]{new GenericEventV7RewardCard(0,"INJURY",0)}};
            byte[] Encode(GenericEventV7RewardRead p)=>GenericEventV7WireCodec.Decision(Nonce,Parent(child),GenericEventV7WireCodec.CardOffer(p,"card_offer_v2"));
            check(Classify(Encode(ready))==TerminalClassification.NonTerminal,"optional offer ready");
            check(Classify(Encode(done))==TerminalClassification.NonTerminal,"optional offer reconciles choose or skip");
            foreach(string fault in new[]{"early","count","key","slot","level","selected","history","missing"}) {
                var invalid=Mutate(Encode(fault=="early"?ready:done),n=>{var p=n["payload"]!;switch(fault) {
                    case "early":p["additional_cards"]=new JsonArray(new JsonObject{["slot"]=0,["key"]="INJURY",["upgrade_level"]=0});break;
                    case "count":n["child"]!["offer_count"]=4;break;case "key":p["additional_cards"]![0]!["key"]="BAD KEY";break;
                    case "slot":p["additional_cards"]![0]!["slot"]=true;break;case "level":p["additional_cards"]![0]!["upgrade_level"]=-1;break;
                    case "selected":p["selected_index"]=skip?JsonValue.Create(0):null;break;
                    case "history":p["prior_results"]![0]!["result"]="acknowledged";break;case "missing":p.AsObject().Remove("additional_cards");break;
                }});check(Classify(invalid)==TerminalClassification.Invalid,"optional boundary rejects "+fault);
            }
            foreach(string outcome in new[]{"accepted","rejected","unsupported","uncertain"}) {
                var receipt=GenericEventV7WireCodec.Action(Nonce,child,null,GenericEventV7WireCodec.CardOffer(new GenericEventV7RewardReceipt(Nonce,Decision,"skip",outcome),"card_offer_v2"));
                check(Classify(receipt,GenericEventTransportRoute.ChildPost)==(outcome=="accepted"?TerminalClassification.NonTerminal:TerminalClassification.Terminal),"optional skip receipt "+outcome);
            }
        }

        foreach(bool bundle in new[]{false,true}) {
            string version=bundle?"bundle_offer_v1":"card_offer_v1";
            var child=new GenericEventV7Child(1,Decision,"choose:0",3,version);
            var offers=Enumerable.Range(0,3).Select(i=>new GenericEventV7Offer(i,Enumerable.Range(0,bundle?2:1).Select(j=>new GenericEventV7RewardCard(j,"CARD_"+i+"_"+j,0)).ToArray())).ToArray();
            GenericEventV7RewardRead Read(string status,string phase,int count,int? selected)=>new(Nonce,status,phase,status=="ready"?Decision:"",Array.Empty<GenericEventV7RewardCard>(),false,
                status=="ready"?(phase=="choose"?new[]{"choose:0","choose:1","choose:2"}:new[]{"confirm"}):Array.Empty<string>(),
                Enumerable.Range(0,count).Select(i=>new GenericEventV7PriorResult(Decision,i==0?"choose:2":"confirm",bundle&&i==0?"previewed":"collected")).ToArray(),selected,Offers:status is "ready" or "resolved"?offers:Array.Empty<GenericEventV7Offer>());
            byte[] Encode(GenericEventV7RewardRead p)=>GenericEventV7WireCodec.Decision(Nonce,Parent(child),GenericEventV7WireCodec.CardOffer(p,version));
            var ready=Encode(Read("ready","choose",0,null));
            check(Classify(ready)==TerminalClassification.NonTerminal,"card offer ready boundary");
            foreach(string invalid in new[]{"version","count","key","slot","selected","history","confirm"})
                check(Classify(Mutate(ready,n=>{var p=n["payload"]!;switch(invalid){case "version":p["version"]="card_reward_v1";break;case "count":n["child"]!["offer_count"]=6;break;case "key":p["offers"]![0]!["cards"]![0]!["key"]="BAD KEY";break;case "slot":p["offers"]![0]!["cards"]![0]!["slot"]=true;break;case "selected":p["selected_index"]=2;break;case "history":p["prior_results"]=new JsonArray(new JsonObject{["decision_id"]=Decision,["action_id"]="choose:2",["result"]="collected"});break;case "confirm":p["legal_actions"]=new JsonArray("confirm");break;}}))==TerminalClassification.Invalid,"malformed offer boundary "+invalid);
            check(Classify(Encode(Read("waiting","waiting",0,null)))==TerminalClassification.NonTerminal,"offer waiting retains owner");
            check(Classify(Encode(Read("unsupported","unsupported",0,null)))==TerminalClassification.Terminal,"offer failure stops owner");
            if(bundle)check(Classify(Encode(Read("ready","preview",1,2)))==TerminalClassification.NonTerminal,"bundle preview retains owner");
            var done=Encode(Read("resolved","complete",bundle?2:1,2));
            check(Classify(done)==TerminalClassification.NonTerminal,"offer completed child retains parent");
            check(Classify(Mutate(done,n=>n["payload"]!["selected_index"]=0))==TerminalClassification.Invalid,"offer settlement selected identity");
            foreach(string outcome in new[]{"accepted","rejected","unsupported","uncertain"}) {
                var receipt=GenericEventV7WireCodec.Action(Nonce,child,null,GenericEventV7WireCodec.CardOffer(new GenericEventV7RewardReceipt(Nonce,Decision,bundle?"confirm":"choose:2",outcome),version));
                check(Classify(receipt,GenericEventTransportRoute.ChildPost)==(outcome=="accepted"?TerminalClassification.NonTerminal:TerminalClassification.Terminal),"offer receipt "+outcome);
            }
        }

        foreach(var spec in new[]{("add",15,"explicit_confirm","card_add_v2"),("transform",6,"preview_confirm","card_transform_v3")}) {
            var child=new GenericEventV7Child(1,Decision,"choose:0",spec.Item1,0,spec.Item2,spec.Item3,spec.Item2);
            var value=CardSelectionV1Observation.Fixed(Nonce,"waiting","transient",Array.Empty<CardSelectionV1ActionResult>());
            var body=GenericEventV7WireCodec.Decision(Nonce,Parent(child),CardTransformV2WireCodec.Encode(value,spec.Item4));
            check(Classify(body)==TerminalClassification.NonTerminal,"optional card boundary");
            check(Classify(Mutate(body,n=>n["child"]!["contract_version"]="card_selection_v1"))==TerminalClassification.Invalid,"optional descriptor cannot use legacy contract");
            check(Classify(Mutate(body,n=>n["payload"]!["version"]="card_transform_v2"))==TerminalClassification.Invalid,"optional payload version must match");
            check(Classify(Mutate(body,n=>n["child"]!["operation"]="upgrade"))==TerminalClassification.Invalid,"optional upgrade forbidden");
            check(Classify(Mutate(body,n=>n["child"]!["max_select"]=16))==TerminalClassification.Invalid,"optional overflow forbidden");
            check(Classify(Mutate(body,n=>n["child"]!["domain_count"]=0))==TerminalClassification.Invalid,"empty candidate domain forbidden");
            var receipt=GenericEventV7WireCodec.Action(Nonce,child,null,CardTransformV2WireCodec.Encode(new CardSelectionV1DispatchReceipt(Nonce,Decision,"confirm"),spec.Item4));
            check(Classify(receipt,GenericEventTransportRoute.ChildPost)==TerminalClassification.NonTerminal,"optional confirm accepted receipt");
        }
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
