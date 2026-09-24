using System;
using System.Text.Json;
using Sts2AgentBridge.Unified;
using Sts2AgentBridge.Cards.Combat;
internal static partial class Program {
 private sealed class PotionFixture:ICombatPotions {
  internal int Stage,Reads,Posts;internal bool Finish;internal Action? Completed;
  public bool Active=>Stage==1;
  private CombatPotionReply Reply(object value,bool terminal=false)=>new(JsonSerializer.SerializeToUtf8Bytes(value),Terminal:terminal);
  public CombatPotionReply Read(){Reads++;
   if(Stage==1){if(!Finish)return Reply(new{schema_version=1,protocol="combat_potions_v1",status="waiting"});Stage=2;Completed?.Invoke();return Reply(new{schema_version=1,protocol="combat_potions_v1",status="resolved",decision_id=Decision,action_id="use:0:0"});}
   return Reply(new{schema_version=1,protocol="combat_potions_v1",status="ready",decision_id=Decision,combat_decision_id=Decision,potions=new[]{new{slot=0,id="FIRE_POTION",supported=true}},legal_actions=new[]{"use:0:0"}});
  }
  public CombatPotionReply Apply(string decision,string action){Posts++;Stage=1;return Reply(new{schema_version=1,status="accepted",mutation_state="queued",decision_id=decision,action_id=action,reason="accepted"});}
  public void Dispose(){if(Active)throw new InvalidOperationException("pending potion");}
 }
 private static void CombatPotionOwnership(){
  foreach(bool eventCombat in new[]{false,true}){
   var f=new CoreFixture{CombatReady=true};var core=Core(f);var potion=new PotionFixture();core.BindPotions(potion);
   string phase="combat";
   var owner=new FakeModule(Capability.Events){Complete=true,CombatScope=()=>phase=="combat",CombatResume=()=>phase,EventNonce=Nonce};
   var router=new BridgeRouter(core,(_,_)=>owner);
   if(eventCombat)router.Handle(Request(Capability.Events,"/probe/generic-event-v7/public/decision"));
   Check(Body(router.Handle(Request(Capability.Core,CombatPotionRoutes.Decision))).Contains("FIRE_POTION"),"core potion observation");
   Check(Body(router.Handle(new(Capability.Core,CombatPotionRoutes.Action,true,0,64,Decision,"use:0:0"))).Contains("accepted"),"potion accepted through core");
   phase="resumed";
   foreach(var path in new[]{"/probe/v0/public/combat-decision","/probe/v0/public/combat-action","/probe/v0/public/map-decision",CombatCardChoiceService.DecisionRouteV3,CampaignRoutes.Decision,AgentSession.DecisionRoute})
    Check(Body(router.Handle(Request(Capability.Core,path))).Contains("capability_busy"),"pending potion fences "+path);
   Check(Body(router.Handle(Request(Capability.Events,"/probe/generic-event-v7/public/decision"))).Contains("capability_busy"),"pending potion fences other module");
   if(eventCombat){Check(Body(router.Handle(Request(Capability.Core,CoreBridgeModule.EventCombatRoute))).Contains("waiting")&&!owner.Disposed,"potion delays outer event cleanup");Check(!core.CanServiceResumeItem(),"pending potion cannot hand off item");}
   Check(Body(router.Handle(Request(Capability.Core,CombatPotionRoutes.Decision))).Contains("waiting"),"potion GET remains routable after native event ended");
   potion.Finish=true;Check(Body(router.Handle(Request(Capability.Core,CombatPotionRoutes.Decision))).Contains("resolved"),"exact potion completion before event handoff");
   if(eventCombat)Check(Body(router.Handle(Request(Capability.Core,CoreBridgeModule.EventCombatRoute))).Contains("resumed")&&owner.Disposed,"outer event cleans after potion");
   Check(potion.Posts==1&&!core.HasPendingAction,"one reconciled input releases core");router.Dispose();
  }
  {var f=new CoreFixture{CombatReady=true};var core=Core(f);var potion=new PotionFixture();core.BindPotions(potion);core.Handle(new(Capability.Core,"/probe/v0/public/combat-action",true,0,64,Decision,"end_turn"));Check(System.Text.Encoding.UTF8.GetString(core.Handle(Request(Capability.Core,CombatPotionRoutes.Decision)).Body).Contains("capability_busy")&&potion.Reads==0,"card owner fences potion adapter");}
  foreach(var bad in new[]{"use:8","use:0:6","use:00","use:0:00","use:0:0:0","discard:0"})
   Check(!BridgeRequestParser.TryParse(Head(CombatPotionRoutes.Action,bad),out _),"bounded potion action grammar "+bad);
  Check(BridgeRequestParser.TryParse(Head(CombatPotionRoutes.Action,"use:0:0"),out var parsed)&&parsed.IsPost&&parsed.Capability==Capability.Core,"versioned potion route uses existing auth parser");
 }
}
