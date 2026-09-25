// The production coordinator and choice service execute here. Native projection
// and module endpoints are authored seams; this does not execute game assemblies.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Cards.Combat;
using static Sts2AgentBridge.Unified.FullPublicGraph;
namespace MegaCrit.Sts2.Core.Combat { internal sealed class Unused {} }
namespace MegaCrit.Sts2.Core.Models { internal sealed class Unused {} }
namespace Sts2AgentBridge.Adapters.Public { internal sealed class PinnedPublicRewardDecisionReader {} }
namespace Sts2AgentBridge.Rooms.Rest {internal class RestInteractiveSession {internal const string FullActionRoute="/rest/action",FullDecisionRoute="/rest/decision";}}
namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native {internal class ShopInteractiveSession {internal const string FullActionRoute="/shop/action",FullDecisionRoute="/shop/decision";}}
namespace Sts2AgentBridge.Unified {
 internal class AgentUnsupported:Exception {}
 internal enum Capability {Core,Rooms,Events}
 internal record BridgeRequest(Capability Capability,string Path,bool IsPost,int AuthorizationOffset,int AuthorizationLength,string? Decision=null,string? Action=null,int ChildOrdinal=0,string? ParentDecision=null,string? ParentAction=null) {internal bool IsChild=>ChildOrdinal!=0;}
 internal record struct ModuleReply(byte[] Body,bool Terminal=false,bool StaleWithoutMutation=false);
 internal static class CoreBridgeModule {internal const string EventCombatRoute="/resume",ResumeItemAction="/resume/item/action",ResumeItemRead="/resume/item/read"; internal static bool IsResumeItem(BridgeRequest request)=>false;}
 internal sealed class FullNativeState:IDisposable {
  internal static void Require(bool ok){if(!ok)throw new AgentUnsupported();}
  internal object[] Bindings=>Array.Empty<object>();internal void Begin(){}
  internal JsonObject PublicRun(List<JsonObject> history)=>Node("run",fields:new(string,object?)[]{("hp",80),("max_hp",80)});
  public void Dispose(){}
 }
 internal sealed partial class FullNativeBackend {
  private void AdoptAcquisitions() {}
  private bool _eventResume=false;
  private FullCapture ReadEvent()=>throw new AgentUnsupported();private FullCapture ReadResumeItem()=>throw new AgentUnsupported();
  private JsonObject Combat(JsonElement wire){Command(_router.Potion?"potion":"combat",Text(wire,"decision_id")!,_router.Discard?"discard:0":"end_turn",_router.Discard?"discard_potion":"end_turn");return Node("combat");}
  private JsonObject Selection(JsonElement wire){Command("choice",Text(wire,"decision_id")!,"select:0","select_card");return Node("combat");}
  private JsonObject Rewards(JsonElement wire)=>throw new AgentUnsupported();private JsonObject Map(JsonElement wire)=>throw new AgentUnsupported();
  private JsonObject Rest(JsonElement wire)=>throw new AgentUnsupported();private JsonObject Shop(JsonElement wire)=>throw new AgentUnsupported();private JsonObject Navigation(JsonElement wire)=>throw new AgentUnsupported();
 }
 internal sealed class DelayedChoice:ICombatCardChoiceAdapter {
  internal int Captures,Inputs;private readonly object _card=new(),_holder=new();internal bool Done;
  public ChoiceSurface Capture()=>new(this,"offer",0,1,false,++Captures>2,Done,Done,false,new[]{new ChoiceCard(_card,_holder,"STRIKE",0,false,true)},Done?new[]{_card}:Array.Empty<object>(),false);
  public void Toggle(int slot){if(slot!=0)throw new Exception();Inputs++;Done=true;}
  public void Confirm()=>throw new Exception();public void Dispose(){}
 }
 internal sealed class BridgeRouter {
  internal readonly bool Potion,Discard;internal readonly CombatCardChoiceService Choice;internal readonly DelayedChoice Adapter=new();
  internal int ParentPosts,ParentReadsWhileChildOwned;private bool _started;
  internal BridgeRouter(bool potion,bool discard=false){Potion=potion;Discard=discard;Choice=new(()=>Adapter.Done?null:Adapter,"coordinator");}
  private static ModuleReply Json(object value)=>new(JsonSerializer.SerializeToUtf8Bytes(value));
  internal ModuleReply Dispatch(BridgeRequest r){
   if(r.Path==CampaignRoutes.FullDecision)return Json(new{status="ready",surface="combat"});
   if(r.Path is CombatCardChoiceService.DecisionRouteV4 or CombatCardChoiceService.ActionRouteV4){var reply=r.IsPost?Choice.Apply(r.Decision!,r.Action!,4):Choice.Read(4);return new(reply.Body,reply.Terminal);}
   if(Choice.IsActive){ParentReadsWhileChildOwned++;return Json(new{status="failed",code="capability_busy"});}
   if(r.IsPost){ParentPosts++;_started=true;return Json(new{status="accepted",decision_id=r.Decision,action_id=r.Action});}
   if(_started&&!Adapter.Done)return Json(new{status="waiting"});
   if(r.Path==CombatPotionRoutes.FullDecision)return Json(new{status="resolved",decision_id="parent",action_id=Discard?"discard:0":"end_turn"});
   return Json(new{status="ready",decision_id=_started?"after":"parent"});
  }
 }
}
