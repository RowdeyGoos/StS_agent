using System;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Potions;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Unified;
internal static class Program {
 static int checks;
 static void Check(bool ok,string why){checks++;if(!ok)throw new Exception(why);}
 static JsonElement Parse(CombatPotionReply reply)=>JsonDocument.Parse(reply.Body).RootElement;
 sealed class Fixture {
  internal readonly Player Player=new();internal readonly CombatManager Manager=new();internal readonly RunManager Run=new();
  internal readonly Creature Enemy=new();internal readonly CombatPotions Service;internal readonly PotionModel Potion;internal string Decision;
  internal Fixture(PotionModel? potion=null){CombatPotions.ResetFixture();NOverlayStack.Instance=null;MegaCrit.Sts2.Core.Nodes.NRun.Instance=new();MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance=new();RunManager.Instance=Run;CombatManager.Instance=Manager;Player.RunState=Run.Run;Manager.State.Players.Add(Player);Manager.State.Enemies.Add(Enemy);Manager.State.HittableEnemies.Add(Enemy);Potion=potion??new FirePotion();Potion.Owner=Player;Player.PotionSlots[0]=Potion;Service=new(new PinnedPublicCombatDecisionReader());Decision=Read().GetProperty("decision_id").GetString()!;}
  internal JsonElement Read()=>Parse(Service.Read());
  internal string Status()=>Read().GetProperty("status").GetString()!;
  internal void Post(string action="use:0:0"){var reply=Service.Apply(Decision,action);Check(!reply.Terminal&&Parse(reply).GetProperty("status").GetString()=="accepted","accepted one native use");}
  internal UsePotionAction Action=>(UsePotionAction)Run.ActionQueueSynchronizer.Actions.Single();
 }
 static void Main(){
  foreach(var potion in new PotionModel[]{new FirePotion(),new BlockPotion(),new ExplosiveAmpoule()}){
   var f=new Fixture(potion);string action=potion is FirePotion?"use:0:0":"use:0";f.Post(action);
   Check(f.Service.Active&&f.Status()=="waiting","queued remains owned");
   Check(ReferenceEquals(f.Action.Target,potion is BlockPotion?f.Player.Creature:potion is FirePotion?f.Enemy:null),"exact native target family");
   var gate=new TaskCompletionSource();potion.Effect=()=>gate.Task;f.Action.Start();
   Check(potion.HasBeenRemovedFromState&&f.Status()=="waiting","early removal cannot reconcile pending effect");
   gate.SetResult();Check(f.Status()=="resolved"&&!f.Service.Active,"exact task success reconciles");f.Service.Dispose();
  }
  foreach(string change in new[]{"slot","player","run","queue","net","combat","target","turn","disabled","remove","custom","overlay","foreground","node","room","cancel","fault","false_completion","dispose"}){
   var f=new Fixture();f.Post();int effects=0;f.Potion.Effect=()=>{effects++;return change=="fault"?Task.FromException(new Exception("effect")):Task.CompletedTask;};
   switch(change){
    case "slot":f.Player.PotionSlots[0]=new FirePotion{Owner=f.Player};break;
    case "player":f.Manager.State.Players[0]=new();break;
    case "run":f.Run.Run=new();break;
    case "queue":f.Run.ActionQueueSynchronizer=new();break;
    case "net":f.Run.NetService=new();break;
    case "combat":f.Manager.State=new();break;
    case "target":f.Manager.State.HittableEnemies.Clear();break;
    case "turn":f.Player.PlayerCombatState!.TurnNumber++;break;
    case "disabled":f.Manager.PlayerActionsDisabled=true;break;
    case "remove":f.Player.CanRemovePotions=false;break;
    case "custom":f.Potion.PassesCustomUsabilityCheck=false;break;
    case "overlay":NOverlayStack.Instance=new(){ScreenCount=1};break;
    case "foreground":MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance.Blocker=new();break;
    case "node":MegaCrit.Sts2.Core.Nodes.NRun.Instance=new();break;
    case "room":MegaCrit.Sts2.Core.Nodes.NRun.Instance.CombatRoom=new();break;
    case "cancel":f.Action.Cancel();break;
    case "false_completion":f.Action.ForgeCompletion();break;
    case "dispose":for(int i=0;i<2;i++){bool failed=false;try{f.Service.Dispose();}catch{failed=true;}Check(failed,"unsettled disposal fails repeatedly");}break;
   }
   // Keep exact queued action even if the queue itself was replaced.
   if(change=="queue") {Check(f.Status()=="failed","changed queue fails");}
   else {if(change!="false_completion")f.Action.Start();Check(f.Status()=="failed","failure cannot reconcile: "+change);}
   Check(f.Service.Active,"failed owner remains fenced");
   if(change!="fault")Check(effects==0&&!f.Potion.HasBeenRemovedFromState,"failed guard prevents effect: "+change);
   bool cleanup=false;try{f.Service.Dispose();}catch{cleanup=true;}Check(cleanup,"uncertain cleanup cannot release: "+change);
  }
  foreach(string change in new[]{"slot","target","run","public"}){
   var f=new Fixture();if(change=="slot")f.Player.PotionSlots[0]=new FirePotion{Owner=f.Player};if(change=="target"){f.Manager.State.HittableEnemies.Clear();}if(change=="run"){f.Player.RunState=f.Run.Run=new();}if(change=="public")f.Enemy.CurrentHp--;
   var reply=f.Service.Apply(f.Decision,"use:0:0");Check(reply.StaleWithoutMutation&&!reply.Terminal&&f.Run.ActionQueueSynchronizer.Actions.Count==0,"stale identity dispatches nothing: "+change);f.Service.Dispose();
  }
  {var f=new Fixture(new AttackPotion());Check(f.Read().GetProperty("legal_actions").GetArrayLength()==0,"choice potion unadvertised");f.Service.Dispose();}
  {var f=new Fixture();f.Post();f.Potion.Effect=()=>{f.Manager.IsOverOrEnding=true;f.Manager.IsInProgress=false;f.Enemy.IsAlive=false;return Task.CompletedTask;};f.Action.Start();Check(f.Status()=="resolved","potion finisher reconciles native ending");f.Service.Dispose();}
  {var f=new Fixture();f.Run.ActionQueueSynchronizer.ThrowAfterEnqueue=true;Check(f.Service.Apply(f.Decision,"use:0:0").Terminal,"uncertain queue reply terminal");f.Action.Start();Check(!f.Potion.HasBeenRemovedFromState,"lost enqueue receipt revokes execution");}
  CombatPotions.ResetFixture();Console.WriteLine($"combat potions: {checks} checks passed");
 }
}
