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
 Console.WriteLine("full native coordinator: delayed card/potion ownership, event-parent projection and room completion barriers passed");}
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
}
