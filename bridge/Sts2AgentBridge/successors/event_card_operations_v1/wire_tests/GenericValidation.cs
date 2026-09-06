using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.EventOrchestratorV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.CardSelectionV1;

internal static partial class Program
{
    private static readonly EventOrchestratorV1CardPolicyDefinition[] Policies = {
        EventOrchestratorV1CardPolicyDefinition.CreateForTests("fixture_add_three","FIXTURE.ADD",CardSelectionV1Operation.Add,3,3,CardSelectionV1CommitMode.AutoAtMax,EventOrchestratorV1CardDomainSource.GeneratedAtAdmission,6,6),
        EventOrchestratorV1CardPolicyDefinition.CreateForTests("fixture_remove_two","FIXTURE.REMOVE",CardSelectionV1Operation.Remove,2,2,CardSelectionV1CommitMode.ExplicitConfirm,EventOrchestratorV1CardDomainSource.ExistingDeckOriginals,4,9),
        EventOrchestratorV1CardPolicyDefinition.CreateForTests("fixture_upgrade_two","FIXTURE.UPGRADE",CardSelectionV1Operation.Upgrade,2,2,CardSelectionV1CommitMode.PreviewConfirm,EventOrchestratorV1CardDomainSource.ExistingDeckOriginals,4,9),
        EventOrchestratorV1CardPolicyDefinition.CreateForTests("fixture_transform_two","FIXTURE.TRANSFORM",CardSelectionV1Operation.Transform,2,2,CardSelectionV1CommitMode.PreviewConfirm,EventOrchestratorV1CardDomainSource.ExistingDeckOriginals,4,9)
    };
    private static EventOrchestratorV1Observation Publication(EventOrchestratorV1CardPolicyDefinition p,int domain=6,string? key=null,string? policy=null)
    {
        var candidates=new[]{new EventOrchestratorV1Candidate(0,"choose:0",key??p.ParentStableId,"Choose",true,false,false,policy??p.PolicyId,domain)};
        var legal=new[]{"choose:0"};
        return new(Nonce,"ready","choose_option",EventOrchestratorV1CanonicalEncoder.ComputeDecisionId(Nonce,"choose_option",candidates,legal),candidates,legal,null,null);
    }
    private static (EventOrchestratorV1WireValidation Validator,RoomFlowDispatchReceipt Receipt) Admitted(EventOrchestratorV1CardPolicyDefinition p)
    {
        var v=new EventOrchestratorV1WireValidation(Nonce,Policies);var o=Publication(p);
        v.Parent(o,null,null);var r=new RoomFlowDispatchReceipt("event",Nonce,o.DecisionId,"choose:0");v.Parent(r,null,null);return(v,r);
    }
    private static string Id(int i)=>i.ToString("x64");
    private static JsonElement CardPayload(EventOrchestratorV1CardPolicyDefinition p,List<(string Decision,string Action)> accepted,bool complete=false,string phase="selecting",int domain=6,string? operation=null,string? replaced=null)
    {
        int[] selected=accepted.Where(x=>x.Action.StartsWith("select:",StringComparison.Ordinal)).Select(x=>int.Parse(x.Action[7..])).ToArray();
        var candidates=Enumerable.Range(0,domain).Select(i=>new{slot=i,key=replaced is not null&&i==0?replaced:"CARD_"+i,upgrade_level=0,visible=true,enabled=true,selected=selected.Contains(i)}).ToArray();
        var history=accepted.Select(x=>new{decision_id=x.Decision,action_id=x.Action,result=x.Action.StartsWith("select:",StringComparison.Ordinal)?"selected":x.Action=="preview"?"previewed":"committed"}).ToArray();
        string op=operation??p.Operation.ToString().ToLowerInvariant();
        if(complete)return JsonSerializer.SerializeToElement(new{schema_version=1,kind="child_resolved",version="card_selection_v1",session_nonce=Nonce,parent_ordinal=1,status="resolved",phase="complete",operation=op,selected_cards=candidates.Where(c=>c.selected).ToArray(),prior_results=history});
        var legal=phase=="selecting"&&selected.Length<p.MaxSelect?candidates.Where(c=>!c.selected).Select(c=>"select:"+c.slot).ToList():new List<string>();
        if(selected.Length>=p.MinSelect)
        {
            if(p.CommitMode==CardSelectionV1CommitMode.ExplicitConfirm||phase=="preview")legal.Add("confirm");
            else if(p.CommitMode==CardSelectionV1CommitMode.PreviewConfirm)legal.Add("preview");
        }
        string commit=p.CommitMode==CardSelectionV1CommitMode.AutoAtMax?"auto_at_max":p.CommitMode==CardSelectionV1CommitMode.ExplicitConfirm?"explicit_confirm":"preview_confirm";
        return JsonSerializer.SerializeToElement(new{schema_version=1,kind="child_observation",version="card_selection_v1",session_nonce=Nonce,parent_ordinal=1,status="ready",phase,operation=op,commit_mode=commit,min_select=p.MinSelect,max_select=p.MaxSelect,decision_id=Id(accepted.Count+1),candidates,selected_slots=selected,legal_actions=legal,prior_results=history});
    }
    private static void Reject(Action action)
    {
        bool rejected=false;try{action();}catch(InvalidOperationException e) when(e.Message=="Invalid event wire state."){rejected=true;}
        Check(rejected);_checks++;
    }
    private static void GenericValidation()
    {
        foreach (var row in new[] {
            ("aroma_maintain_control_upgrade_one", "AROMA_OF_CHAOS.pages.INITIAL.options.LET_GO"),
            ("sapphire_eat_upgrade_one", "SAPPHIRE_SEED.pages.INITIAL.options.PLANT") })
        {
            Check(EventOrchestratorV1CardPolicyCatalog.TryGet(row.Item1, out var definition));
            var p = definition ?? throw new InvalidOperationException("Accepted production policy missing.");
            foreach (int domain in new[] { 2, 64 })
            {
                var v = new EventOrchestratorV1WireValidation(Nonce);
                var o = Publication(p, domain);
                v.Parent(o, null, null);
                var receipt = new RoomFlowDispatchReceipt("event", Nonce, o.DecisionId, "choose:0");
                v.Parent(receipt, null, null);
                var accepted = new List<(string Decision, string Action)>();
                v.Child(CardPayload(p, accepted, domain: domain), false, accepted);
                accepted.Add((Id(1), "select:0"));
                v.Child(CardPayload(p, accepted, domain: domain), false, accepted);
                accepted.Add((Id(2), "preview"));
                v.Child(CardPayload(p, accepted, phase: "preview", domain: domain), false, accepted);
                accepted.Add((Id(3), "confirm"));
                v.Child(CardPayload(p, accepted, complete: true, domain: domain), false, accepted);
            }
            _checks++;
            foreach (int domain in new[] { 0, 1, 65 })
                Reject(() => new EventOrchestratorV1WireValidation(Nonce).Parent(Publication(p, domain), null, null));
            Reject(() => new EventOrchestratorV1WireValidation(Nonce).Parent(Publication(p, 2, key: row.Item2), null, null));
            var wrong = new EventOrchestratorV1WireValidation(Nonce);
            var wrongPublication = Publication(p, 2);
            var wrongReceipt = new RoomFlowDispatchReceipt("event", Nonce, wrongPublication.DecisionId, "choose:0");
            wrong.Parent(wrongPublication, null, null); wrong.Parent(wrongReceipt, null, null);
            Reject(() => wrong.Child(CardPayload(p, new(), domain: 2, operation: "remove"), false, Array.Empty<(string,string)>()));
        }
        foreach(var p in Policies)
        {
            var(v,_)=Admitted(p);var accepted=new List<(string Decision,string Action)>();
            for(int i=0;i<p.MaxSelect;i++){v.Child(CardPayload(p,accepted),false,accepted);accepted.Add((Id(accepted.Count+1),"select:"+i));}
            if(p.CommitMode!=CardSelectionV1CommitMode.AutoAtMax)
            {
                v.Child(CardPayload(p,accepted),false,accepted);
                if(p.CommitMode==CardSelectionV1CommitMode.PreviewConfirm){accepted.Add((Id(accepted.Count+1),"preview"));v.Child(CardPayload(p,accepted,phase:"preview"),false,accepted);}
                accepted.Add((Id(accepted.Count+1),"confirm"));
            }
            v.Child(CardPayload(p,accepted,complete:true),false,accepted);_checks++;
        }
        {
            var p=Policies[1];var(v,r)=Admitted(p);
            var prior=new EventOrchestratorV1PriorResult(r.DecisionId,r.ActionId,"option_transition",null);
            var waiting=new EventOrchestratorV1Observation(Nonce,"waiting","waiting","",Array.Empty<EventOrchestratorV1Candidate>(),Array.Empty<string>(),null,prior);
            Reject(()=>v.Parent(waiting,r,null));
        }
        foreach(int domain in new[]{0,3,10})
            Reject(()=>new EventOrchestratorV1WireValidation(Nonce,Policies).Parent(Publication(Policies[1],domain),null,null));
        Reject(()=>new EventOrchestratorV1WireValidation(Nonce,Policies).Parent(Publication(Policies[1],key:"OTHER"),null,null));
        Reject(()=>new EventOrchestratorV1WireValidation(Nonce,Policies).Parent(Publication(Policies[1],0,policy:"item_reward"),null,null));
        Reject(()=>new EventOrchestratorV1WireValidation(Nonce).Parent(Publication(Policies[1]),null,null));
        Reject(()=>new EventOrchestratorV1WireValidation(Nonce,new[]{Policies[1],Policies[1]}));
        {
            var(v,_)=Admitted(Policies[1]);Reject(()=>v.Child(CardPayload(Policies[1],new(),domain:5),false,Array.Empty<(string,string)>()));
        }
        {
            var(v,_)=Admitted(Policies[1]);Reject(()=>v.Child(CardPayload(Policies[1],new(),operation:"add"),false,Array.Empty<(string,string)>()));
        }
        {
            var p=Policies[1];var(v,_)=Admitted(p);var a=new List<(string Decision,string Action)>();v.Child(CardPayload(p,a),false,a);
            a.Add((Id(1),"select:0"));a.Add((Id(2),"select:1"));Reject(()=>v.Child(CardPayload(p,a,complete:true),false,a));
        }
        {
            var p=Policies[2];var(v,_)=Admitted(p);var a=new List<(string Decision,string Action)>();v.Child(CardPayload(p,a),false,a);
            a.Add((Id(1),"select:0"));a.Add((Id(2),"select:1"));v.Child(CardPayload(p,a),false,a);a.Add((Id(3),"preview"));
            Reject(()=>v.Child(CardPayload(p,a),false,a));
        }
        {
            var p=Policies[2];var(v,_)=Admitted(p);var a=new List<(string Decision,string Action)>();v.Child(CardPayload(p,a),false,a);
            a.Add((Id(1),"select:0"));a.Add((Id(2),"select:1"));a.Add((Id(3),"preview"));v.Child(CardPayload(p,a,phase:"preview"),false,a);a.Add((Id(4),"confirm"));
            Reject(()=>v.Child(CardPayload(p,a,complete:true,replaced:"OTHER"),false,a));
        }
    }
}
