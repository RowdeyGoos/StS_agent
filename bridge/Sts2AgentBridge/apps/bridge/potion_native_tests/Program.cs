using System;
using MegaCrit.Sts2.Core.Entities.Actions;
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
  internal Fixture(PotionModel? potion=null){CombatPotions.ResetFixture();NOverlayStack.Instance=null;MegaCrit.Sts2.Core.Nodes.NRun.Instance=new();MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance=new();RunManager.Instance=Run;CombatManager.Instance=Manager;Player.RunState=Run.Run;Manager.State.Players.Add(Player);Run.Run.Players.Add(Player);Manager.State.Enemies.Add(Enemy);Manager.State.HittableEnemies.Add(Enemy);Potion=potion??new FirePotion();Potion.Owner=Player;Player.PotionSlots[0]=Potion;Service=new(new PinnedPublicCombatDecisionReader());Decision=Read().GetProperty("decision_id").GetString()!;}
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
   var f=new Fixture();if(change=="slot")f.Player.PotionSlots[0]=new FirePotion{Owner=f.Player};if(change=="target"){f.Manager.State.HittableEnemies.Clear();}if(change=="run"){f.Player.RunState=f.Run.Run=new();f.Run.Run.Players.Add(f.Player);}if(change=="public")f.Enemy.CurrentHp--;
   var reply=f.Service.Apply(f.Decision,"use:0:0");Check(reply.StaleWithoutMutation&&!reply.Terminal&&f.Run.ActionQueueSynchronizer.Actions.Count==0,"stale identity dispatches nothing: "+change);f.Service.Dispose();
  }
  {var f=new Fixture(new AttackPotion());Check(f.Read().GetProperty("legal_actions").GetArrayLength()==0,"choice potion unadvertised");f.Service.Dispose();}
  {var f=new Fixture();f.Post();f.Potion.Effect=()=>{f.Manager.IsOverOrEnding=true;f.Manager.IsInProgress=false;f.Enemy.IsAlive=false;return Task.CompletedTask;};f.Action.Start();Check(f.Status()=="resolved","potion finisher reconciles native ending");f.Service.Dispose();}
  {var f=new Fixture();f.Run.ActionQueueSynchronizer.ThrowAfterEnqueue=true;Check(f.Service.Apply(f.Decision,"use:0:0").Terminal,"uncertain queue reply terminal");f.Action.Start();Check(!f.Potion.HasBeenRemovedFromState,"lost enqueue receipt revokes execution");}
  foreach(bool async in new[]{false,true}) {
   var f=new Fixture(new AttackPotion());var view=Parse(f.Service.ReadFull());Check(view.GetProperty("legal_actions").GetArrayLength()==2,"full potion profile admits native choice potion");
   Check(!f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"use:0:0").Terminal,"full potion accepted");
   Check(!f.Service.AllowsChoices,"queued potion cannot adopt a selector");
   var gate=new TaskCompletionSource(); f.Potion.Effect=async?()=>{f.Action.State=GameActionState.GatheringPlayerChoice;f.Action.PlayerChoiceContext=new();return gate.Task;}:()=>Task.CompletedTask;f.Action.Start();
   if(async){Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()=="waiting"&&f.Service.AllowsChoices,"owned potion waits for child selector");gate.SetResult();}
   Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()=="resolved","full potion task completion verified");f.Service.Dispose();
  }
  foreach(bool scoped in new[]{false,true}) {
   var f=new Fixture();var view=Parse(f.Service.ReadFull()); f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"use:0:0");
   var added=new BlockPotion();f.Potion.Effect=()=>{if(scoped)f.Player.AddPotionInternal(added);return Task.CompletedTask;}; f.Action.Start();
   if(!scoped)f.Player.AddPotionInternal(added);
   Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()==(scoped?"resolved":"failed"),"only native scoped potion refill can reconcile");
  }
  {var f=new Fixture(new BlockPotion());f.Potion.Usage=MegaCrit.Sts2.Core.Entities.Potions.PotionUsage.AnyTime;f.Manager.IsInProgress=false;
   MegaCrit.Sts2.Core.Nodes.NRun.Instance.GlobalUi.MapScreen.IsOpen=true;var view=Parse(f.Service.ReadFull());
   Check(view.GetProperty("legal_actions").GetArrayLength()==2,"AnyTime potion at map");f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"use:0");f.Action.Start();
   Check(!f.Action.WasEnqueuedInCombat&&Parse(f.Service.ReadFull()).GetProperty("status").GetString()=="resolved","noncombat native use settles");f.Service.Dispose();}
  foreach(string change in new[]{"location","map"}) {
   var f=new Fixture(new BlockPotion());f.Potion.Usage=MegaCrit.Sts2.Core.Entities.Potions.PotionUsage.AnyTime;f.Manager.IsInProgress=false;
   MegaCrit.Sts2.Core.Nodes.NRun.Instance.GlobalUi.MapScreen.IsOpen=true;var view=Parse(f.Service.ReadFull());
   if(change=="location") f.Run.Run.CurrentRoom=new(); else MegaCrit.Sts2.Core.Nodes.NRun.Instance.GlobalUi.MapScreen=new(){IsOpen=true};
   var reply=f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"use:0");
   Check(reply.StaleWithoutMutation&&f.Run.ActionQueueSynchronizer.Actions.Count==0,"map identity stale before dispatch: "+change);f.Service.Dispose();
  }
  foreach(bool scoped in new[]{false,true}) {
   var f=new Fixture();var fairy=new BlockPotion{Owner=f.Player};f.Player.PotionSlots[1]=fairy;
   var view=Parse(f.Service.ReadFull());f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"use:0:0");
   var gate=new TaskCompletionSource();f.Potion.Effect=()=>{if(scoped)fairy.Use();return gate.Task;};f.Action.Start();
   if(!scoped)fairy.Use();gate.SetResult();
   Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()==(scoped?"resolved":"failed"),"only owned automatic potion consumption reconciles");
  }
  foreach(bool move in new[]{false,true}) {
   var f=new Fixture();var view=Parse(f.Service.ReadFull());f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"use:0:0");
   var gate=new TaskCompletionSource();var added=new BlockPotion();f.Potion.Effect=()=>{f.Player.AddPotionInternal(added);return gate.Task;};f.Action.Start();
   f.Player.PotionSlots[0]=null;if(move)f.Player.PotionSlots[1]=added;gate.SetResult();
   Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()=="failed","owned refill removal/relocation cannot reconcile");
  }
  foreach(bool map in new[]{false,true})foreach(bool automatic in new[]{false,true}) {
   var f=new Fixture();if(map){f.Manager.IsInProgress=false;MegaCrit.Sts2.Core.Nodes.NRun.Instance.GlobalUi.MapScreen.IsOpen=true;}
   if(automatic)f.Potion.Usage=MegaCrit.Sts2.Core.Entities.Potions.PotionUsage.Automatic;
   var view=Parse(f.Service.ReadFull());Check(view.GetProperty("legal_actions").EnumerateArray().Any(a=>a.GetString()=="discard:0"),"discard available including automatic potions");
   if(automatic)Check(view.GetProperty("legal_actions").GetArrayLength()==1,"automatic potion cannot be manually used");
   var reply=f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"discard:0");Check(!reply.Terminal&&f.Service.Active&&!f.Service.AllowsChoices,"discard queued under exact owner");
   Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()=="waiting","discard waits for queue");
   f.Run.ActionQueueSynchronizer.Actions.Single().Start();Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()=="resolved"&&f.Player.PotionSlots[0] is null,"native discard settles");f.Service.Dispose();
  }
  foreach(string mode in new[]{"slot","turn","foreground","queue","early_completion","cancel","lost_enqueue","foreign_slot"}) {
   var f=new Fixture();var view=Parse(f.Service.ReadFull());if(mode=="lost_enqueue")f.Run.ActionQueueSynchronizer.ThrowAfterEnqueue=true;
   f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"discard:0");var action=f.Run.ActionQueueSynchronizer.Actions.Single();
   if(mode=="slot")f.Player.PotionSlots[0]=new FirePotion{Owner=f.Player};if(mode=="turn")f.Player.PlayerCombatState!.TurnNumber++;if(mode=="foreground")MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance.Blocker=new();if(mode=="queue")f.Run.ActionQueueSynchronizer=new();
   if(mode=="early_completion")action.ForgeCompletion();else if(mode=="cancel")action.Cancel();else action.Start();
   if(mode=="foreign_slot")f.Player.PotionSlots[1]=new BlockPotion{Owner=f.Player};
   Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()=="failed","discard rejects "+mode);bool rejected=false;try{f.Service.Dispose();}catch{rejected=true;}Check(rejected,"uncertain discard stays fenced");
  }
  foreach(bool cancel in new[]{false,true}) {
   var f=new Fixture();var gate=new TaskCompletionSource();f.Player.DiscardEffect=()=>gate.Task;var view=Parse(f.Service.ReadFull());f.Service.ApplyFull(view.GetProperty("decision_id").GetString()!,"discard:0");var action=f.Run.ActionQueueSynchronizer.Actions.Single();action.Start();
   Check(f.Player.PotionSlots[0] is null&&Parse(f.Service.ReadFull()).GetProperty("status").GetString()=="waiting","discard effect remains owned after physical removal");
   if(cancel)gate.SetCanceled();else gate.SetResult();
   Check(action.CompletionTask.IsCompletedSuccessfully&&action.Exception is null,"native cancellation fixture preserves successful outer completion");
   Check(Parse(f.Service.ReadFull()).GetProperty("status").GetString()==(cancel?"failed":"resolved"),"discard requires native execution success");
  }
  CombatPotions.ResetFixture();Console.WriteLine($"combat potions: {checks} checks passed");
 }
}
