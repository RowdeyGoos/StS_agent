using System;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Unified;
using Sts2AgentBridge.Adapters.Public;
internal static partial class Program {
 static void Check(bool ok,string why){if(!ok)throw new Exception(why);}
 static void Main(){foreach(bool potion in new[]{false,true}){
  var router=new BridgeRouter(potion);var backend=new FullNativeBackend(router,new PinnedPublicRewardDecisionReader(),router.Choice);
  var parent=backend.Read();backend.Apply(parent.Commands[0].Request);
  var opening=backend.Read();Check(opening.Status=="waiting"&&opening.Completed.Length==0&&router.Choice.IsActive,"opening chooser retains ownership, parent uncompleted");
  var choice=backend.Read();Check(choice.Status=="ready"&&choice.Completed.Length==0,"delayed chooser becomes actionable");
  backend.Apply(choice.Commands[0].Request);var after=backend.Read();
  Check(after.Status=="ready"&&after.Completed.Length==2&&router.ParentPosts==1&&router.Adapter.Inputs==1&&router.ParentReadsWhileChildOwned==0,"child then parent complete once, no intermediate parent read");
  backend.Dispose();
 }
 {var router=new BridgeRouter(true,true);var backend=new FullNativeBackend(router,new PinnedPublicRewardDecisionReader(),router.Choice);
  var parent=backend.Read();backend.Apply(parent.Commands[0].Request);
  var waiting=backend.Read();Check(waiting.Status=="waiting"&&!router.Choice.IsActive&&router.Adapter.Captures==0,"queued discard never probes or adopts a selector");
  router.Adapter.Done=true;var after=backend.Read();Check(after.Status=="ready"&&after.Completed.Length==1&&router.ParentPosts==1,"discard parent settles once after native completion");backend.Dispose();}
 EventParentCases();
 RoomCompletionCases();
 ReceiptFailureCases();
 Console.WriteLine("full native coordinator: delayed card/potion ownership, event-parent projection, room barriers and certified failure receipts passed");}
 static JsonObject Read(FullAgentSession session)=>JsonNode.Parse(session.Handle(new(Capability.Core,FullAgentRoutes.Decision,false,0,0)).Body)!.AsObject();
 static void RoomCompletionCases(){foreach(string family in new[]{"rest","shop"})foreach(bool fail in new[]{false,true}){
  var router=new BridgeRouter(false){RoomFamily=family,FailRoomCompletion=fail};
  var backend=new FullNativeBackend(router,new PinnedPublicRewardDecisionReader(),router.Choice);
  var session=new FullAgentSession(backend,"fixture");var before=Read(session);
  var receipt=session.Handle(new(Capability.Core,FullAgentRoutes.Action,true,0,0,before["decision_id"]!.GetValue<string>(),"action:0"));
  Check(JsonNode.Parse(receipt.Body)!["status"]!.GetValue<string>()=="accepted","room parent accepted once");
  var completed=Read(session);
  Check(completed["status"]!.GetValue<string>()==(fail?"failed":"waiting")&&router.NavigationReads==1,
   "completed room returns receipts before reading successor "+family);
  var stopped=fail?completed:Read(session);
  Check(stopped["status"]!.GetValue<string>()=="failed"&&stopped["code"]!.GetValue<string>()=="read_native_failed"&&
   stopped["attempted"]!.GetValue<int>()==1&&stopped["accepted"]!.GetValue<int>()==1&&
   stopped["reconciled"]!.GetValue<int>()==(fail?0:1)&&stopped["pending"]!.GetValue<int>()==(fail?1:0),
   "successor failure preserves only verified completion "+family);
  int reads=router.NavigationReads;Read(session);
  Check(router.ParentPosts==1&&router.NavigationReads==reads,"failed successor never retries room mutation");
  bool unresolved=false;try{session.Dispose();}catch(InvalidOperationException){unresolved=true;}catch(AgentUnsupported){unresolved=true;}
  Check(unresolved==fail,"only reconciled room can dispose cleanly");
 }}
 static void Apply(FullAgentSession session,JsonObject view){
  var reply=session.Handle(new(Capability.Core,FullAgentRoutes.Action,true,0,0,view["decision_id"]!.GetValue<string>(),"action:0"));
  Check(JsonNode.Parse(reply.Body)!["status"]!.GetValue<string>()=="accepted","one native action accepted");
 }
 static void Failure(FullAgentSession session,BridgeRouter router,JsonObject failure,int accepted,int reconciled,string code){
  Check(failure["status"]!.GetValue<string>()=="failed"&&failure["code"]!.GetValue<string>()==code&&
   failure["attempted"]!.GetValue<int>()==accepted&&failure["accepted"]!.GetValue<int>()==accepted&&
   failure["reconciled"]!.GetValue<int>()==reconciled&&failure["pending"]!.GetValue<int>()==accepted-reconciled,
   "failure retains only certified receipts: "+code+" "+failure.ToJsonString());
  int reads=router.NavigationReads,posts=router.ParentPosts,inputs=router.Adapter.Inputs;
  var stopped=Read(session);
  Check(stopped["reconciled"]!.GetValue<int>()==reconciled&&router.NavigationReads==reads&&router.ParentPosts==posts&&router.Adapter.Inputs==inputs,
   "terminal failure cannot reread, replay or double credit");
  bool unresolved=false;try{session.Dispose();}catch(InvalidOperationException){unresolved=true;}catch(AgentUnsupported){unresolved=true;}
  Check(unresolved==(accepted!=reconciled),"pending ancestors keep disposal unresolved");
 }
 static void ReceiptFailureCases(){
  foreach(string mode in new[]{"successor","projection","uncompleted"}){
   var router=new BridgeRouter(false){MapHandoff=true,FailMapSuccessor=mode=="successor",FailMapCompletion=mode=="uncompleted",FailCombatProjection=mode=="projection"};
   var session=new FullAgentSession(new FullNativeBackend(router,new PinnedPublicRewardDecisionReader(),router.Choice),"map-fixture");
   Apply(session,Read(session));
   Failure(session,router,Read(session),1,mode=="uncompleted"?0:1,mode=="projection"?"read_context_failed":"read_native_failed");
  }
  foreach(string outcome in new[]{"victory","invalid","missing"}){
   var router=new BridgeRouter(false){CombatCompletionOutcome=outcome};router.Adapter.Done=true;
   var session=new FullAgentSession(new FullNativeBackend(router,new PinnedPublicRewardDecisionReader(),router.Choice),"combat-fixture");
   Apply(session,Read(session));
   Failure(session,router,Read(session),1,outcome=="victory"?1:0,"read_context_failed");
  }
  foreach(bool potion in new[]{false,true}){
   var router=new BridgeRouter(potion){FailCombatProjection=true};router.Adapter.Done=true;
   var session=new FullAgentSession(new FullNativeBackend(router,new PinnedPublicRewardDecisionReader(),router.Choice),"projection-fixture");
   Apply(session,Read(session));Failure(session,router,Read(session),1,1,"read_context_failed");
  }
  {
   var router=new BridgeRouter(false){MissingReadyDecision=true};
   var session=new FullAgentSession(new FullNativeBackend(router,new PinnedPublicRewardDecisionReader(),router.Choice),"missing-decision-fixture");
   Apply(session,Read(session));Failure(session,router,Read(session),1,0,"read_context_failed");
  }
  foreach(bool potion in new[]{false,true}){
   var router=new BridgeRouter(potion){FailParentAfterChoice=true};
   var session=new FullAgentSession(new FullNativeBackend(router,new PinnedPublicRewardDecisionReader(),router.Choice),"child-fixture");
   Apply(session,Read(session));Check(Read(session)["status"]!.GetValue<string>()=="waiting","child opening remains pending");
   Apply(session,Read(session));Failure(session,router,Read(session),2,1,"read_native_failed");
   Check(router.ParentPosts==1&&router.Adapter.Inputs==1&&router.ParentReadsWhileChildOwned==0,"child input certified independently of failing ancestor");
  }
 }
}
