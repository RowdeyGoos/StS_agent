using System;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Successors.GenericEventReleaseV10;
using Sts2AgentBridge.Successors.GenericEventV7;

internal static partial class GenericEventV7WireTests
{
    // Classify the actual service bytes before decoding: the live regression was
    // between the wire producer and this production boundary, not inside either.
    private static JsonElement FullBoundary(byte[] body, GenericEventTransportRoute route,
        TerminalClassification expected = TerminalClassification.NonTerminal)
    {
        var actual = GenericEventTerminalClassifier.Classify(route, GenericEventReleaseSelection.Generic, Nonce, 200, body);
        Check(actual == expected, "full reward boundary " + route + ": expected " + expected + ", got " + actual);
        return Decode(body);
    }

    private static byte[] FullRead(GenericEventV7WireService wire) => wire.Handle("GET", GenericEventV7WireService.DecisionRoute, null);
    private static byte[] FullPost(GenericEventV7WireService wire, byte[] request) => wire.Handle("POST", GenericEventV7WireService.ActionRoute, request);

    private static void FullRewardBoundaryCases()
    {
        foreach(var action in new[]{"deselect:0","deselect:63","deselect:64","deselect:00","select:63","select:64"})
            Case("compound transport selector grammar "+action,()=>{
                var head=Encoding.ASCII.GetBytes("POST /probe/generic-event-v7/public/action HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "+new string('a',64)+
                    "\r\nAccept: application/json\r\nX-Sts2-Decision-Id: "+new string('b',64)+"\r\nX-Sts2-Action-Id: "+action+
                    "\r\nX-Sts2-Child-Ordinal: 1\r\nX-Sts2-Parent-Decision-Id: "+ParentId+"\r\nX-Sts2-Parent-Action-Id: choose:0\r\nConnection: close\r\n\r\n");
                bool parsed=GenericEventTransportRequestParser.TryParse(head,GenericEventReleaseSelection.Generic,out var request);
                Check(parsed==(action is "deselect:0" or "deselect:63" or "select:63"),"exact bounded selector grammar at HTTP ingress");
                if(parsed)Check(request.Route==GenericEventTransportRoute.ChildPost&&Encoding.ASCII.GetString(head,request.ActionOffset,request.ActionLength)==action,
                    "native action retained through parsing");
                Array.Clear(head);
            });
        Case("full reward wire lifecycle retains parent ownership at the production boundary", () => {
            using var f = new FullRewardsFake(); using var wire = new GenericEventV7WireService(Nonce, f);
            FullBoundary(FullRead(wire), GenericEventTransportRoute.DecisionGet);
            FullBoundary(FullPost(wire, Request()), GenericEventTransportRoute.ParentPost);
            foreach (string action in f.Actions) {
                f.Status = "waiting";
                FullBoundary(FullRead(wire), GenericEventTransportRoute.DecisionGet);
                f.Status = "ready";
                var read = FullBoundary(FullRead(wire), GenericEventTransportRoute.DecisionGet);
                string decision = read.GetProperty("payload").GetProperty("decision_id").GetString()!;
                FullBoundary(FullPost(wire, Request(decision, action, 1, ParentId, "choose:0")), GenericEventTransportRoute.ChildPost);
            }
            var done = FullBoundary(FullRead(wire), GenericEventTransportRoute.DecisionGet);
            Check(done.GetProperty("payload").GetProperty("status").GetString() == "resolved", "resolved child keeps parent owner");
            var parent = FullBoundary(FullRead(wire), GenericEventTransportRoute.DecisionGet).GetProperty("parent");
            Check(parent.GetProperty("parent_reconciled").GetInt32() == 1, "only subsequent parent read reconciles");
        });
        Case("full reward unsupported read stops at the boundary", () => {
            using var f = new FullRewardsFake(); using var wire = new GenericEventV7WireService(Nonce, f); ItemStart(wire);
            f.Status = "unsupported";
            FullBoundary(FullRead(wire), GenericEventTransportRoute.DecisionGet, TerminalClassification.Terminal);
        });
        foreach (string outcome in new[] { "rejected", "unsupported", "uncertain" })
            Case("full reward " + outcome + " receipt stops at the boundary", () => {
                using var f = new FullRewardsFake { Outcome = outcome }; using var wire = new GenericEventV7WireService(Nonce, f); ItemStart(wire);
                var read = FullBoundary(FullRead(wire), GenericEventTransportRoute.DecisionGet);
                FullBoundary(FullPost(wire, Request(read.GetProperty("payload").GetProperty("decision_id").GetString()!, f.Actions[0], 1, ParentId, "choose:0")),
                    GenericEventTransportRoute.ChildPost, TerminalClassification.Terminal);
            });

        using var fixture = new FullRewardsFake(); using var service = new GenericEventV7WireService(Nonce, fixture); ItemStart(service);
        byte[] ready = FullRead(service);
        void Reject(string name, byte[] source, GenericEventTransportRoute route, Action<JsonNode> mutate)
        {
            Case("full reward boundary rejects " + name, () => {
                var root = JsonNode.Parse(source)!; mutate(root);
                FullBoundary(JsonSerializer.SerializeToUtf8Bytes(root), route, TerminalClassification.Invalid);
            });
        }
        var get = GenericEventTransportRoute.DecisionGet;
        Reject("descriptor version", ready, get, r => r["child"]!["contract_version"] = "card_results_v1");
        Reject("descriptor-only compound upgrade", ready, get, r => r["child"]!["contract_version"] = "full_rewards_v2");
        Reject("payload-only compound upgrade", ready, get, r => r["payload"]!["version"] = "full_rewards_v2");
        foreach (int count in new[] { 0, 9 }) Reject("descriptor count " + count, ready, get, r => r["child"]!["offer_count"] = count);
        Reject("descriptor lineage", ready, get, r => r["child"]!["parent_decision_id"] = "bad");
        Reject("descriptor parent action", ready, get, r => r["child"]!["parent_action_id"] = "dismiss");
        Reject("descriptor ordinal", ready, get, r => r["child"]!["ordinal"] = 5);
        Reject("extra descriptor field", ready, get, r => r["child"]!["operation"] = "remove");
        Reject("payload version", ready, get, r => r["payload"]!["version"] = "card_results_v1");
        Reject("payload nonce", ready, get, r => r["payload"]!["session_nonce"] = new string('f', 32));
        Reject("ready decision", ready, get, r => r["payload"]!["decision_id"] = "");
        Reject("unknown phase", ready, get, r => r["payload"]!["phase"] = "choose");
        Reject("wrong phase actions", ready, get, r => r["payload"]!["phase"] = "card_reward");
        Reject("unopened cards", ready, get, r => r["payload"]!["cards"]!.AsArray().Add(new JsonObject()));
        Reject("no legal action", ready, get, r => r["payload"]!["legal_actions"] = new JsonArray());
        Reject("duplicate actions", ready, get, r => r["payload"]!["legal_actions"]!.AsArray().Add("claim:0"));
        Reject("out of range action", ready, get, r => r["payload"]!["legal_actions"]![0] = "claim:8");
        Reject("foreign card action", ready, get, r => r["payload"]!["legal_actions"]![0] = "confirm");
        Reject("extra payload field", ready, get, r => r["payload"]!["can_skip"] = true);
        Reject("waiting with input", ready, get, r => { r["payload"]!["status"] = "waiting"; r["payload"]!["phase"] = "waiting"; });

        string id = JsonNode.Parse(ready)!["payload"]!["decision_id"]!.GetValue<string>();
        byte[] receipt = FullPost(service, Request(id, fixture.Actions[0], 1, ParentId, "choose:0"));
        var post = GenericEventTransportRoute.ChildPost;
        Reject("receipt version", receipt, post, r => r["payload"]!["version"] = "card_results_v1");
        Reject("receipt-only compound upgrade", receipt, post, r => r["payload"]!["version"] = "full_rewards_v2");
        Reject("receipt nonce", receipt, post, r => r["payload"]!["session_nonce"] = new string('f', 32));
        Reject("receipt decision", receipt, post, r => r["payload"]!["decision_id"] = "");
        Reject("receipt action", receipt, post, r => r["payload"]!["action_id"] = "claim:8");
        Reject("receipt outcome", receipt, post, r => r["payload"]!["outcome"] = "completed");
        Reject("receipt field", receipt, post, r => r["payload"]!["result"] = "completed");
        FullBoundary(receipt, post);
        byte[] settled = FullRead(service);
        Reject("history result", settled, get, r => r["payload"]!["prior_results"]![0]!["result"] = "accepted");
        Reject("history action", settled, get, r => r["payload"]!["prior_results"]![0]!["action_id"] = "confirm");
        Reject("history decision", settled, get, r => r["payload"]!["prior_results"]![0]!["decision_id"] = "");
        Reject("duplicate history", settled, get, r => r["payload"]!["prior_results"]!.AsArray().Add(r["payload"]!["prior_results"]![0]!.DeepClone()));
        Reject("history bound", settled, get, r => {
            var history = r["payload"]!["prior_results"]!.AsArray();
            for (int i = 1; i <= 40; i++) { var entry = history[0]!.DeepClone(); entry["decision_id"] = (i + 1).ToString("x64"); history.Add(entry); }
        });
        FullBoundary(settled, get);
        Array.Clear(ready);
        using var compoundFixture=new FullRewardsFake(compound:true);using var compoundService=new GenericEventV7WireService(Nonce,compoundFixture);ItemStart(compoundService);
        byte[] compoundReady=FullRead(compoundService);
        FullBoundary(compoundReady.ToArray(),get);
        Reject("compound descriptor downgrade",compoundReady,get,r=>r["child"]!["contract_version"]="full_rewards_v1");
        Reject("compound payload downgrade",compoundReady,get,r=>r["payload"]!["version"]="full_rewards_v1");
        Reject("compound phase mismatch",compoundReady,get,r=>r["payload"]!["phase"]="bundle_preview");
        var compoundId=Decode(compoundReady).GetProperty("payload").GetProperty("decision_id").GetString()!;
        FullBoundary(FullPost(compoundService,Request(compoundId,"collect:0",1,ParentId,"choose:0")),post);
        var selecting=FullRead(compoundService);FullBoundary(selecting.ToArray(),get);
        Reject("compound selector bound",selecting,get,r=>r["payload"]!["legal_actions"]![0]="select:64");
        Reject("compound selector noncanonical slot",selecting,get,r=>r["payload"]!["legal_actions"]![0]="select:00");
        Reject("compound selector wrong operation",selecting,get,r=>r["payload"]!["legal_actions"]![0]="collect:0");
    }
}
