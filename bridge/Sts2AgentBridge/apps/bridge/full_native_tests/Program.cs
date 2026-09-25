using System;
using Sts2AgentBridge.Unified;
using Sts2AgentBridge.Adapters.Public;
internal static class Program {
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
 Console.WriteLine("full native coordinator: delayed card and potion child ownership passed");}
}
