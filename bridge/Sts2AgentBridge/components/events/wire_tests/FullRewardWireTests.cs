using System;
using System.Collections.Generic;
using System.Linq;
using Sts2AgentBridge.Successors.GenericEventReleaseV10;
using Sts2AgentBridge.Successors.GenericEventV7;

internal static partial class GenericEventV7WireTests
{
    private static void FullRewardCases()
    {
        FullRewardBoundaryCases();
        foreach(int count in new[]{40,41})Case("compound rewards retain the 40 input bound: "+count,()=>{
            using var f=new FullRewardsFake(compound:true,inputCount:count);using var wire=new GenericEventV7WireService(Nonce,f);ItemStart(wire);
            for(int i=0;i<count;i++) {
                var p=FullBoundary(FullRead(wire),GenericEventTransportRoute.DecisionGet).GetProperty("payload");
                var result=FullPost(wire,Request(p.GetProperty("decision_id").GetString()!,f.Actions[i],1,ParentId,"choose:0"));
                if(i==40)Error(Decode(result),"internal_failure");
                else FullBoundary(result,GenericEventTransportRoute.ChildPost);
            }
            if(count==40)Check(FullBoundary(FullRead(wire),GenericEventTransportRoute.DecisionGet).GetProperty("payload").GetProperty("prior_results").GetArrayLength()==40,
                "all 40 inputs reconcile within the enclosing 52 attempt budget");
        });
        Case("compound rewards retain pending outer receipts through nested surfaces",()=>{
            using var f=new FullRewardsFake(compound:true);using var wire=new GenericEventV7WireService(Nonce,f);ItemStart(wire);
            foreach(var action in f.Actions) {
                var read=FullBoundary(FullRead(wire),GenericEventTransportRoute.DecisionGet);
                var payload=read.GetProperty("payload");
                Check(payload.GetProperty("version").GetString()=="full_rewards_v2"&&payload.GetProperty("prior_results").GetArrayLength()==0,
                    "nested inputs preserve the unsettled outer receipt");
                FullBoundary(FullPost(wire,Request(payload.GetProperty("decision_id").GetString()!,action,1,ParentId,"choose:0")),GenericEventTransportRoute.ChildPost);
            }
            var settled=FullBoundary(FullRead(wire),GenericEventTransportRoute.DecisionGet).GetProperty("payload");
            Check(settled.GetProperty("status").GetString()=="resolved"&&settled.GetProperty("prior_results").GetArrayLength()==f.Actions.Length,
                "compound resolution retains the exact ordered receipt prefix");
            Check(Read(wire).GetProperty("parent").GetProperty("parent_reconciled").GetInt32()==1,"compound parent settles after every child input");
        });
        Case("full reward protocol preserves receipts and phases",()=>{
            using var f=new FullRewardsFake();using var wire=new GenericEventV7WireService(Nonce,f);ItemStart(wire);
            foreach(var action in f.Actions) {
                var read=Read(wire);Check(read.GetProperty("kind").GetString()=="decision","full read "+read.GetRawText());Check(read.GetProperty("payload").GetProperty("version").GetString()=="full_rewards_v1","full child version");
                Check(read.GetProperty("payload").GetProperty("cards").GetArrayLength()==0,"internal wire never exposes unopened offers");
                var result=Post(wire,Request(read.GetProperty("payload").GetProperty("decision_id").GetString()!,action,1,ParentId,"choose:0"));
                Check(result.GetProperty("payload").GetProperty("outcome").GetString()=="accepted","full child accepted "+action);
            }
            var done=Read(wire);Check(done.GetProperty("kind").GetString()=="decision"&&done.GetProperty("payload").GetProperty("status").GetString()=="resolved"&&done.GetProperty("payload").GetProperty("prior_results").GetArrayLength()==f.Actions.Length,"all exact child receipts retained");
            var parent=Read(wire).GetProperty("parent");Check(parent.GetProperty("status").GetString()=="ready"&&parent.GetProperty("parent_reconciled").GetInt32()==1,"parent resumes only after child settlement");
        });
        foreach(string mutation in new[]{"phase","count","history","early"})Case("full reward rejects "+mutation,()=>{
            using var f=new FullRewardsFake();using var wire=new GenericEventV7WireService(Nonce,f);ItemStart(wire);
            if(mutation is "history" or "early"){var read=Read(wire);Post(wire,Request(read.GetProperty("payload").GetProperty("decision_id").GetString()!,f.Actions[0],1,ParentId,"choose:0"));}
            f.Mutation=mutation;Error(Read(wire),"internal_failure");
        });
    }
    private sealed class FullRewardsFake:IGenericEventV7Session
    {
        internal readonly string[] Actions={"claim:0","collect:1","take:2","discard:0","open:3","reroll","sacrifice","choose:4","open:3","skip_card","dismiss"};
        private readonly string[] _phases=Array.Empty<string>();
        private readonly bool _compound;
        private string Version=>_compound?"full_rewards_v2":"full_rewards_v1";
        private int Reconciled=>_compound&&_history.Count<Actions.Length?0:_history.Count;
        internal FullRewardsFake(bool compound=false,int inputCount=0)
        {
            _compound=compound;
            if(compound) {
                Actions=new[]{"collect:0","select:0","deselect:0","select:63","confirm","select:1","confirm","select:2","cancel","choose:4","confirm","choose:2","skip","dismiss"};
                _phases=new[]{"rewards","deck_remove","deck_remove","deck_remove","deck_remove","deck_upgrade","deck_upgrade","deck_transform","deck_transform","bundle_offer","bundle_preview","card_offer","card_offer","rewards"};
                if(inputCount>0) {
                    Actions=Enumerable.Range(0,inputCount).Select(i=>i%2==0?"select:0":"deselect:0").ToArray();
                    _phases=Enumerable.Repeat("deck_remove",inputCount).ToArray();
                }
            }
        }
        internal string Mutation="";
        internal string Status="ready", Outcome="accepted";
        private bool _parent,_delivered;
        private readonly List<GenericEventV7PriorResult> _history=new();
        private string Id=>(_history.Count+1).ToString("x64");
        public GenericEventV7Observation Read()
        {
            bool active=_parent&&!_delivered;
            return new(Nonce,active?"child":"ready",active?"child":_delivered?"proceed":"choose_option",active?"":_delivered?new string('f',64):ParentId,
                active?Array.Empty<GenericEventV7Candidate>():new[]{new GenericEventV7Candidate(0,"choose:0","OPTION","Choose",true,false,_delivered)},active?Array.Empty<string>():new[]{"choose:0"},
                active?new GenericEventV7Child(1,ParentId,"choose:0",new GenericEventV7FullRewardsAdmission(new object(),Mutation=="count"?9:4,Version)):null,
                _delivered?new[]{new GenericEventV7PriorResult(ParentId,"choose:0","child_completed")}:Array.Empty<GenericEventV7PriorResult>(),_parent?1:0,_parent?1:0,_delivered?1:0,_parent?1:0,
                _history.Count,_history.Count,Reconciled,_parent?"unverified":"none_attempted");
        }
        public GenericEventV7ApplyResult Apply(string? decision,string? action){_parent=true;return new(Nonce,decision!,action!,"accepted");}
        public GenericEventV7ChildRead ReadChild(string? pd,string? pa,int ordinal)
        {
            bool done=_history.Count==Actions.Length||Mutation=="early";
            string phase=Mutation=="phase"?"card_reward":_compound&&!done?_phases[_history.Count]:_history.Count is 5 or 6 or 7 or 9?"card_reward":"rewards";
            var history=_history.Take(Reconciled).ToArray();if(Mutation=="history")history[0]=new(history[0].DecisionId,"collect:0","completed");
            if(Mutation=="early")history=Array.Empty<GenericEventV7PriorResult>();
            if(Status!="ready")return new GenericEventV7RewardChildRead(new(Nonce,Status,Status,"",Array.Empty<GenericEventV7RewardCard>(),false,Array.Empty<string>(),history,null),Version);
            if(done)_delivered=true;
            return new GenericEventV7RewardChildRead(new(Nonce,done?"resolved":"ready",done?"complete":phase,done?"":Id,Array.Empty<GenericEventV7RewardCard>(),false,done?Array.Empty<string>():new[]{Actions[_history.Count]},history,null),Version);
        }
        public GenericEventV7ChildApply ApplyChild(string? pd,string? pa,int ordinal,string? decision,string? action){if(Outcome=="accepted")_history.Add(new(decision!,action!,"completed"));return new GenericEventV7RewardChildApply(new(Nonce,decision!,action!,Outcome),Version);}
        public void Dispose(){}
    }
}
