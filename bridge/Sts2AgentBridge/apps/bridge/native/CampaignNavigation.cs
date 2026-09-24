using System;
using System.Collections.Generic;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

namespace Sts2AgentBridge.Unified;

// Public routing facts, not a second gameplay model or a reset API. The run
// binding is private; policies see only scene kind, act/floor and current HP.
internal sealed class CampaignNavigation : ICampaignNavigation
{
    private RunState? _run;
    private MegaCrit.Sts2.Core.Entities.Players.Player? _player;
    private readonly string _id=Guid.NewGuid().ToString("N");
    private readonly Dictionary<object,Dictionary<string,string>> _rooms=new(ReferenceEqualityComparer.Instance);
    private IPublicRewardTransition? _pending;
    private CampaignTreasureTransition? _treasure;
    private string? _pendingDecision, _completed;
    private readonly HashSet<string> _used=new(StringComparer.Ordinal);
    private bool _stopped;
    public bool Active=>_pending is not null||_treasure?.Active==true;
    public ModuleReply Handle(BridgeRequest request)
    {
        if(_stopped)return Fault();
        try {
            if(request.IsPost) {
                if(_pending is not null||request.Action is null||_run is null||
                    !_rooms.TryGetValue(_run.CurrentRoom!,out var actions)||!actions.TryGetValue(request.Action,out var decision)||
                    decision!=request.Decision||_used.Contains(decision))return Fault();
                var node=NRun.Instance;
                if(!Context()||node is null||node.GlobalUi.MapScreen.IsOpen)return Fault();
                if(_treasure is not null&&request.Action is "open_chest" or "skip_relic") {
                    _used.Add(decision);_pendingDecision=decision;
                    _treasure.Apply(request.Action);
                    return Receipt(decision,request.Action);
                }
                if(request.Action=="proceed"&&node.MerchantRoom is {} closedShop&&closedShop.IsVisibleInTree()&&!closedShop.Inventory.IsOpen&&_run.CurrentRoom is MerchantRoom) {
                    var ownerRoom=_run.CurrentRoom;
                    _pending=new CampaignShopTransition(_id,new PinnedShopV1NativeAdapter(),()=>Context()&&
                        ReferenceEquals(NRun.Instance,node)&&ReferenceEquals(_run.CurrentRoom,ownerRoom)&&
                        NModalContainer.Instance?.OpenModal is null&&NCapstoneContainer.Instance is not {InUse:true});
                } else return Fault();
                _used.Add(decision);_pendingDecision=decision;
                _pending.Dispatch();
                return Receipt(decision,request.Action);
            }
            if(_pending is not null) {
                string destination=_pending.Poll();
                if(destination=="waiting")return View("waiting","unknown");
                if(destination!="map")return Fault();
                _pending.Dispose();_pending=null;_completed=_pendingDecision;_pendingDecision=null;
            }
            if(_treasure is not null) {
                string phase=_treasure.Read();
                if(phase=="waiting")return View("waiting","treasure");
                if(phase is "skip_relic" or "map"&&_pendingDecision is not null) {_completed=_pendingDecision;_pendingDecision=null;}
                if(phase=="map") {_treasure.Dispose();_treasure=null;}
                else return View("ready","treasure",phase);
            }
            var manager=RunManager.Instance;var current=manager?.DebugOnlyGetState();var run=NRun.Instance;
            if(current is null||run is null)return View("waiting","unknown");
            _run??=current;
            if(_player is null&&_run.Players.Count==1)_player=_run.Players[0];
            if(!Context())return Fault();
            if(NModalContainer.Instance?.OpenModal is not null||NCapstoneContainer.Instance is {InUse:true})return View("unsupported","overlay");
            var ui=run.GlobalUi;
            if(ui is null)return View("waiting","unknown");
            bool rewards=ui.Overlays.ScreenCount==1&&ui.Overlays.Peek() is NRewardsScreen;
            if(ui.Overlays.ScreenCount!=0&&!rewards)return View("unsupported","overlay");
            if(ui.MapScreen.IsTraveling)return View("waiting","unknown");
            // Native reward Proceed opens the map without popping its reward
            // overlay. The map is then the foreground decision until travel.
            if(ui.MapScreen.IsOpen)return View(ui.MapScreen.IsTravelEnabled?"ready":"waiting","map");
            if(rewards)return View("ready","rewards");
            if(CombatManager.Instance is {IsInProgress:true,IsOverOrEnding:false})return View("ready","combat");
            if(run.EventRoom is {} ev&&ev.IsVisibleInTree()&&_run.CurrentRoom is EventRoom)return View("ready","event");
            if(run.RestSiteRoom is {} rest&&rest.IsVisibleInTree())return View("ready","rest");
            if(run.MerchantRoom is {} shop&&shop.IsVisibleInTree())return View("ready","shop");
            if(run.TreasureRoom is {} chest&&chest.IsVisibleInTree()) {
                _treasure=new CampaignTreasureTransition(chest);
                return View("ready","treasure",_treasure.Read());
            }
            return View("waiting","unknown");
        }catch {return Fault();}
    }
    private bool Context()=>_run is not null&&ReferenceEquals(RunManager.Instance?.DebugOnlyGetState(),_run)&&
        !RunManager.Instance.IsAbandoned&&(int)RunManager.Instance.NetService.Type==1&&_run.Players.Count==1&&ReferenceEquals(_player,_run.Players[0])&&
        _run.CurrentActIndex is >=0 and <=2&&_run.TotalFloor is >=0 and <=80;
    private ModuleReply View(string status,string surface,string? action=null)
    {
        string? decision=null;
        if(status=="ready"&&(surface=="treasure"||surface=="shop"&&NRun.Instance?.MerchantRoom?.Inventory.IsOpen==false)) {
            object room=_run!.CurrentRoom!;
            if(!_rooms.TryGetValue(room,out var actions)) {
                if(_rooms.Count>=80)return Fault();
                _rooms.Add(room,actions=new(StringComparer.Ordinal));
            }
            action??="proceed";
            if(!actions.TryGetValue(action,out decision))actions.Add(action,decision=Convert.ToHexString(System.Security.Cryptography.RandomNumberGenerator.GetBytes(32)).ToLowerInvariant());
            if(_used.Contains(decision))return Fault();
        }
        var player=_run?.Players[0];
        return new(JsonSerializer.SerializeToUtf8Bytes(new{schema_version=1,protocol="campaign_v2",status,surface,run_id=_id,
            act_index=_run?.CurrentActIndex,floor=_run?.TotalFloor,character=player?.Character.Id.Entry.ToLowerInvariant(),
            ascension=_run?.AscensionLevel,room_kind=_run?.CurrentRoom?.RoomType.ToString().ToLowerInvariant(),
            hp=player?.Creature.CurrentHp,max_hp=player?.Creature.MaxHp,
            decision_id=decision,legal_actions=decision is null?Array.Empty<string>():new[]{action!},completed_decision_id=_completed}));
    }
    private static ModuleReply Receipt(string decision,string action)=>new(JsonSerializer.SerializeToUtf8Bytes(new{schema_version=1,protocol="campaign_v2",status="accepted",decision_id=decision,action_id=action}));
    private ModuleReply Fault(){_stopped=true;return new(JsonSerializer.SerializeToUtf8Bytes(new{schema_version=1,protocol="campaign_v2",status="failed",code=_treasure is null?"campaign_context_failed":"campaign_treasure_failed"}),Terminal:true);}
    public void Dispose(){_stopped=true;try{_pending?.Dispose();}finally{_treasure?.Dispose();}}
}
