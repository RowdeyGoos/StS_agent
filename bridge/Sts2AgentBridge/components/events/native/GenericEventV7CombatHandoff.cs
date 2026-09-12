using G = Sts2AgentBridge.Successors.GenericEventReleaseV5.GenericEventDiagnosticCode;
using D = Sts2AgentBridge.Successors.GenericEventV7.GenericEventV7ResumeDiagnostic;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Nodes;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// An entry callback is not a completed combat. This lease certifies only the
// exact combat requested by the event and any owned resume-time item child.
internal sealed class GenericEventV7CombatHandoff
{
    private readonly GenericEventV7Binding _binding;
    private readonly EncounterModel _encounter;
    private readonly CombatState? _preparedState;
    private readonly NCombatRoom? _preparedNode;
    private readonly Reward[] _extraRewards;
    private readonly object?[] _extraModels;
    private readonly string?[] _extraKeys;
    private readonly int[] _extraLevels, _extraIndices;
    private List<Reward>? _roomExtras;
    private static CardModel? SpecialCard(Reward reward)=>reward.GetType()==typeof(SpecialCardReward)
        ? typeof(SpecialCardReward).GetField("_card",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(reward) as CardModel:null;
    private bool ExtraValid(int index)
    {
        var reward=_extraRewards[index];
        if(!ReferenceEquals(reward.Player,_binding.Player)||reward.RewardsSetIndex!=_extraIndices[index]||
            reward.SuccessfullySelected||reward.ParentRewardSet is not null)return false;
        object? model=reward.GetType()==typeof(PotionReward)?((PotionReward)reward).Potion:
            reward.GetType()==typeof(RelicReward)?((RelicReward)reward).Relic:SpecialCard(reward);
        if(model is null)return _extraModels[index] is null&&!reward.IsPopulated&&reward.GetType()!=typeof(SpecialCardReward);
        string key=model is PotionModel potion?potion.Id.Entry:model is RelicModel relic?relic.Id.Entry:((CardModel)model).Id.Entry;
        if(!reward.IsPopulated||!GenericEventV7ItemState.ValidKey(key))return false;
        if(_extraModels[index] is null) {
            for(int i=0;i<_extraModels.Length;i++)if(ReferenceEquals(_extraModels[i],model))return false;
            _extraModels[index]=model;_extraKeys[index]=key;_extraLevels[index]=(model as CardModel)?.CurrentUpgradeLevel??0;
        }
        if(!ReferenceEquals(_extraModels[index],model)||_extraKeys[index]!=key)return false;
        if(model is CardModel card)return card.CurrentUpgradeLevel==_extraLevels[index]&&card.Enchantment is null&&
            ReferenceEquals(card.Owner,_binding.Player)&&ReferenceEquals(card.RunState,_binding.RunState)&&!_binding.Player.Deck.Cards.Any(c=>ReferenceEquals(c,card));
        if(reward is PotionReward p)return p.ClaimedPotion is null&&!_binding.Player.PotionSlots.Any(potion=>ReferenceEquals(potion,model));
        return ((RelicModel)model).Owner is null&&((RelicReward)reward).ClaimedRelic is null&&!_binding.Player.Relics.Any(relic=>ReferenceEquals(relic,model));
    }
    private bool ExtraRewardsValid(CombatRoom room) {
        if(room.ExtraRewards.Count==0)return _extraRewards.Length==0;
        if(room.ExtraRewards.Count!=1||!room.ExtraRewards.TryGetValue(_binding.Player,out var extras)||extras.Count!=_extraRewards.Length)return false;
        if(_roomExtras is not null&&!ReferenceEquals(extras,_roomExtras))return false;
        for(int i=0;i<extras.Count;i++)if(!ReferenceEquals(extras[i],_extraRewards[i])||!ExtraValid(i))return false;
        _roomExtras=extras;return true;
    }
    private CombatRoom? _room;
    private CombatState? _state;
    private NCombatRoom? _node;
    internal bool Returned;
    internal readonly bool Resumes;
    private readonly EventRoom? _eventRoom;
    private Task? _resumeTask;
    private bool _resumeSeen;
    private NEventRoom? _resumedNode;
    private MegaCrit.Sts2.Core.Nodes.Events.NEventLayout? _resumedLayout;
    private IGenericEventV7ItemChildSession? _item;
    private bool _itemResolved;
    private GenericEventV7ItemCompletion? _settledCompletion;
    private Sts2AgentBridge.Successors.ItemV1.ItemV1PotionSlotBinding[]? _settledSlots;
    private int _settledCapacity;
    private void SettleItem() {
        _settledCompletion=_itemCompletion!();
        if(!GenericEventV7ItemAdapter.Slots(_binding.Player,out _settledCapacity,out var slots))throw new InvalidOperationException("Settled inventory unavailable.");
        _settledSlots=slots.ToArray();_itemResolved=true;
    }
    private bool SettlementValid(GenericEventV7ItemCompletion now) {
        if(_settledCompletion is not {} old||!ReferenceEquals(now.Collection?.Identity,old.Collection?.Identity)||
            !ReferenceEquals(now.Offer?.Identity,old.Offer?.Identity)||!ReferenceEquals(now.Chosen?.Identity,old.Chosen?.Identity)||
            !GenericEventV7ItemAdapter.Slots(_binding.Player,out int capacity,out var slots)||capacity!=_settledCapacity||slots.Count!=_settledSlots!.Length)return false;
        for(int i=0;i<slots.Count;i++)if(!ReferenceEquals(slots[i].ModelIdentity,_settledSlots[i].ModelIdentity)||slots[i].StableKey!=_settledSlots[i].StableKey)return false;
        return true;
    }
    private Func<GenericEventV7ItemCompletion>? _itemCompletion;
    internal GenericEventV7Binding Binding=>_binding;
    internal bool Started=>_resumeSeen;
    internal Task? ResumeTask=>_resumeTask;
    internal bool Owns(GenericEventV7Binding binding)=>_resumeSeen&&ReferenceEquals(binding,_binding);
    internal D ResumeDiagnostic {get;private set;}
    private string Reject(D diagnostic){if(ResumeDiagnostic==D.none)ResumeDiagnostic=diagnostic;return "unsupported";}
    internal bool ItemContextValid()=>ItemContextDiagnostic()==D.none;
    private D ItemContextDiagnostic() {
        var run=RunManager.Instance?.DebugOnlyGetState();
        if(!_resumeSeen||_binding.Failed||!ReferenceEquals(run,_binding.RunState)||!ReferenceEquals(NRun.Instance,_binding.Run))return D.context_owner;
        if(!ReferenceEquals(run!.CurrentRoom,_eventRoom)&&!ReferenceEquals(run.CurrentRoom,_room))return D.context_room;
        if(!ReferenceEquals(_binding.EventModel.Owner,_binding.Player)||!ReferenceEquals(_binding.Player.RunState,run)||
            !ReferenceEquals(_eventRoom!.LocalMutableEvent,_binding.EventModel))return D.context_owner;
        if(!GodotObject.IsInstanceValid(_binding.Run)||!GodotObject.IsInstanceValid(_binding.Map)||!GodotObject.IsInstanceValid(_binding.Overlays)||
            !ReferenceEquals(MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen.Instance,_binding.Map)||
            !ReferenceEquals(_binding.Run.GlobalUi?.Overlays,_binding.Overlays)||!ReferenceEquals(_binding.Run.GlobalUi?.MapScreen,_binding.Map))return D.context_ui;
        if(_binding.Map.IsOpen)return D.context_map_open;
        if(_binding.Map.IsTraveling)return D.context_traveling;
        // Native combat completion enables travel before the finished parent resumes.
        if(_binding.Map.IsTravelEnabled&&!_binding.EventModel.IsFinished)return D.context_travel_enabled;
        if(!GenericEventV7Binding.CapstoneReady())return D.context_capstone;
        if(MegaCrit.Sts2.Core.Commands.CardSelectCmd.Selector is not null)return D.context_selector;
        if(_resumeTask is not null&&(_resumeTask.IsFaulted||_resumeTask.IsCanceled))return D.context_task;
        if(_resumedNode is not null&&(!ReferenceEquals(NEventRoom.Instance,_resumedNode)||!ReferenceEquals(_binding.Run.EventRoom,_resumedNode)||
                !GodotObject.IsInstanceValid(_resumedNode)||!ReferenceEquals(_resumedNode.Layout,_resumedLayout)||
                _resumedLayout is null||!GodotObject.IsInstanceValid(_resumedLayout)||
                !ReferenceEquals(_binding.EventModel.Node,_resumedLayout)||_resumedNode.CustomEventNode is not null))return D.context_node;
        return D.none;
    }

    internal object ReadItem() {
        if(ResumeStatus()!="item"||_item is null)throw new InvalidOperationException("Resume item unavailable.");
        var value=_item.Read();
        if(value is Sts2AgentBridge.Successors.ItemV1.ItemV1ResolvedResult||value is GenericEventV7ItemSetRead {Status:"resolved"})SettleItem();
        return value;
    }
    internal object ApplyItem(string? decision,string? action) {
        if(ResumeStatus()!="item"||_item is null||_itemResolved)throw new InvalidOperationException("Resume item unavailable.");
        return _item.Apply(decision,action);
    }
    internal void DisposeItem(){_item?.Dispose();_item=null;}

    internal MethodInfo ResumeMethod {
        get {
            var method=_binding.EventModel.GetType().GetMethod("Resume",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,
                null,new[]{typeof(AbstractRoom)},null)??throw new InvalidOperationException("Resume callback unavailable.");
            // Harmony requires the declaration, not an inherited reflected handle.
            return method.DeclaringType!.GetMethod("Resume",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.DeclaredOnly,
                null,new[]{typeof(AbstractRoom)},null)!;
        }
    }
    internal GenericEventV7CombatHandoff(GenericEventV7Binding binding, EncounterModel encounter,
        IReadOnlyList<Reward> rewards, bool resume)
    {
        if(rewards is null || rewards.Count>8 || resume&&rewards.Count!=0 || encounter is null || !binding.ContextValid(false) ||
            binding.Option.IsProceed || binding.RequestSeen || binding.Item is not null ||
            binding.Offer is not null || binding.Results is not null)
            throw new InvalidOperationException("Unsupported event combat entry.");
        _binding=binding;_encounter=encounter;Resumes=resume;
        // The pinned native entry branches on LayoutType (Combat = 1).
        if(((int)binding.EventModel.LayoutType==1)!=(binding.Layout is MegaCrit.Sts2.Core.Nodes.Events.NCombatEventLayout))
            throw new InvalidOperationException("Event combat layout mismatch.");
        if(binding.Layout is MegaCrit.Sts2.Core.Nodes.Events.NCombatEventLayout layout) {
            // Combat-layout entry reuses EventModel's state created before the
            // option is selected; the newly supplied encounter argument is ignored.
            var state=typeof(EventModel).GetField("_combatStateForCombatLayout",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(binding.EventModel) as CombatState;
            var prepared=typeof(EventModel).GetField("_mutableEncounter",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(binding.EventModel) as EncounterModel;
            var node=layout.EmbeddedCombatRoom;
            if(resume||state is null||prepared is null||node is null||node.GetType()!=typeof(NCombatRoom)||!GodotObject.IsInstanceValid(node)||
                !ReferenceEquals(node,binding.EmbeddedRoom)||!ReferenceEquals(node,NCombatRoom.Instance)||
                !ReferenceEquals(binding.EventModel.Node,layout)||!ReferenceEquals(state.Encounter,prepared)||
                !ReferenceEquals(state.RunState,binding.RunState)||state.Players.Count!=1||!ReferenceEquals(state.Players[0],binding.Player)||
                !ReferenceEquals(RunManager.Instance?.DebugOnlyGetState(),binding.RunState)||
                binding.RunState.CurrentRoom is not EventRoom parent||!ReferenceEquals(parent.LocalMutableEvent,binding.EventModel))
                throw new InvalidOperationException("Prepared event combat unavailable.");
            _preparedState=state;_preparedNode=node;_encounter=prepared;
        }
        _extraRewards=new Reward[rewards.Count];_extraModels=new object?[rewards.Count];_extraKeys=new string?[rewards.Count];
        _extraLevels=new int[rewards.Count];_extraIndices=new int[rewards.Count];
        var identities=new HashSet<object>(ReferenceEqualityComparer.Instance);
        bool specialSeen=false;
        for(int i=0;i<rewards.Count;i++) {
            var reward=rewards[i];
            if(reward is null||!identities.Add(reward)||reward.GetType()!=typeof(SpecialCardReward)&&reward.GetType()!=typeof(PotionReward)&&reward.GetType()!=typeof(RelicReward))
                throw new InvalidOperationException("Unsupported extra combat reward.");
            if(reward.GetType()==typeof(SpecialCardReward)){if(specialSeen)throw new InvalidOperationException("Multiple special extras unsupported.");specialSeen=true;}
            _extraRewards[i]=reward;_extraIndices[i]=reward.RewardsSetIndex;
            if(!ExtraValid(i))throw new InvalidOperationException("Extra combat reward ownership unavailable.");
        }
        if(resume) {
            _eventRoom=RunManager.Instance?.DebugOnlyGetState()?.CurrentRoom as EventRoom;
            if(_eventRoom is null||!ReferenceEquals(_eventRoom.LocalMutableEvent,binding.EventModel)||
                ResumeMethod.IsStatic||ResumeMethod.IsGenericMethod||ResumeMethod.ReturnType!=typeof(Task))
                throw new InvalidOperationException("Exact event resume callback unavailable.");
        }
    }
    internal string Capture(out G diagnostic)
    {
        diagnostic=G.CombatWaitingCallback;
        if(!Returned || _binding.ChosenTask is null)return "waiting";
        diagnostic=G.CombatCallbackFailed;
        if(_binding.ChosenTask.IsFaulted||_binding.ChosenTask.IsCanceled||_binding.Failed)return "unsupported";
        diagnostic=G.CombatWaitingCallback;
        if(!_binding.ChosenTask.IsCompletedSuccessfully)return "waiting";
        var run=RunManager.Instance?.DebugOnlyGetState();
        var state=CombatManager.Instance?.DebugOnlyGetState();
        diagnostic=G.CombatRunOwner;
        if(run is null || !ReferenceEquals(run,_binding.RunState) || !ReferenceEquals(NRun.Instance,_binding.Run))return "unsupported";
        diagnostic=G.CombatWaitingRoom;
        if(run.CurrentRoom is not CombatRoom room || state is null)return "waiting";
        diagnostic=G.CombatRewards;
        if(!ExtraRewardsValid(room))return "unsupported";
        diagnostic=G.CombatEncounter;
        if(!ReferenceEquals(room.Encounter,_encounter))return "unsupported";
        diagnostic=G.CombatState;
        if(!ReferenceEquals(room.CombatState,state)||!ReferenceEquals(state.Encounter,_encounter)||!ReferenceEquals(state.RunState,run)||
            _preparedState is not null&&(!ReferenceEquals(state,_preparedState)||room.ShouldCreateCombat))return "unsupported";
        diagnostic=G.CombatParent;
        if(room.ShouldResumeParentEventAfterCombat!=Resumes||!Equals(room.ParentEventId,_binding.EventModel.Id))return "unsupported";
        diagnostic=G.CombatPlayers;
        if(state.Players.Count!=1||!ReferenceEquals(state.Players[0],_binding.Player))return "unsupported";
        if(_room is null){
            diagnostic=G.CombatWaitingNode;
            var node=NCombatRoom.Instance;
            if(node is null)return "waiting";
            if(_preparedNode is not null&&!ReferenceEquals(node,_preparedNode)){diagnostic=G.CombatIdentity;return "unsupported";}
            _room=room;_state=state;_node=node;
        }
        diagnostic=G.CombatIdentity;
        if(!SameCombat())return "unsupported";
        if(CombatManager.Instance!.IsInProgress&&!CombatManager.Instance.IsOverOrEnding) {
            diagnostic=G.CombatReady;return Resumes?"combat_resume":"combat";
        }
        diagnostic=G.CombatWaitingEnd;return "waiting";
    }
    internal void EnterResume(EventModel model, AbstractRoom room)
    {
        if(!Resumes||_resumeSeen||!ReferenceEquals(model,_binding.EventModel)||!ReferenceEquals(room,_room)||
            _state is null||!ReferenceEquals(RunManager.Instance?.DebugOnlyGetState(),_binding.RunState)||
            !ReferenceEquals(_binding.Player.RunState,_binding.RunState)||!ReferenceEquals(_state.RunState,_binding.RunState)||
            !ReferenceEquals(_binding.RunState.CurrentRoom,_eventRoom)||!ReferenceEquals(NRun.Instance,_binding.Run)||
            !ReferenceEquals(model.Owner,_binding.Player)||!ReferenceEquals(_eventRoom!.LocalMutableEvent,model)||
            // CombatRoom.Exit removes player creatures before EventRoom.Resume. The
            // retained room/state and event owner prove identity after that cleanup.
            (_state.Players.Count!=0&&(_state.Players.Count!=1||!ReferenceEquals(_state.Players[0],_binding.Player)))||
            !ReferenceEquals(_room!.CombatState,_state)||!ReferenceEquals(_room.Encounter,_encounter)||
            !_room.ShouldResumeParentEventAfterCombat||!Equals(_room.ParentEventId,model.Id))
            throw new InvalidOperationException("Unexpected event resume invocation.");
        _resumeSeen=true;
    }
    internal void CaptureResumeTask(Task task)
    {
        if(!_resumeSeen||task is null||_resumeTask is not null)throw new InvalidOperationException("Resume task replaced.");
        _resumeTask=task;
    }
    internal void FailResume(D diagnostic=D.callback_entry){if(ResumeDiagnostic==D.none)ResumeDiagnostic=diagnostic;_binding.Failed=true;}
    internal string ResumeStatus()
    {
        if(!Resumes||_binding.Failed)return Reject(D.binding_failed);
        var run=RunManager.Instance?.DebugOnlyGetState();
        if(!ReferenceEquals(run,_binding.RunState)||!ReferenceEquals(NRun.Instance,_binding.Run)||
            !ReferenceEquals(_binding.Player.RunState,run)||!ReferenceEquals(_binding.EventModel.Owner,_binding.Player))return Reject(D.run_owner);
        if(!_resumeSeen) {
            if(SameCombat())return CombatManager.Instance!.IsInProgress&&!CombatManager.Instance.IsOverOrEnding?"combat":"waiting";
            return ReferenceEquals(run!.CurrentRoom,_eventRoom)?"waiting":Reject(D.combat_identity);
        }
        if(_resumeTask is null||_resumeTask.IsFaulted||_resumeTask.IsCanceled)return Reject(D.resume_task);
        var context=ItemContextDiagnostic();if(context!=D.none)return Reject(context);
        if(_binding.Item is {} reward) {
            if(!reward.Overlay()||reward.FailedTask)return Reject(D.item_offer);
            if(_item is null) {
                if(!reward.Ready)return "waiting";
                if(!reward.Domain()||reward.HasCards)return Reject(D.item_domain);
                string nodeStatus=NodeStatus();
                if(nodeStatus!="resumed")return nodeStatus;
                if(reward.OfferCount>1) {
                    var adapter=new GenericEventV7ItemSetAdapter(reward);
                    _item=new GenericEventV7ItemSetSession(_binding.Nonce,adapter);
                    _itemCompletion=()=>adapter.CaptureCompletion(reward.OfferCount-1);
                }else {
                    var adapter=new GenericEventV7ItemAdapter(reward);
                    _item=new GenericEventV7ItemChildSession(_binding.Nonce,adapter);_itemCompletion=adapter.CaptureCompletion;
                }
            }
            if(!_itemResolved)return "item";
            // A resolved child remains subject to its inventory/task/context evidence until handoff.
            var completion=_itemCompletion!();
            if(!SettlementValid(completion)||!completion.OwnershipValid||!completion.EffectStillValid||!completion.ScreenClosed||
                completion.Collection?.State!=GenericEventV7ItemTaskState.Succeeded||completion.Offer?.State!=GenericEventV7ItemTaskState.Succeeded||
                completion.Chosen?.State!=GenericEventV7ItemTaskState.Succeeded)return Reject(D.item_settlement);
        } else if(_binding.Overlays.ScreenCount!=0)return Reject(D.unexpected_overlay);
        if(!_resumeTask.IsCompletedSuccessfully)return "waiting";
        if(_binding.Overlays.ScreenCount!=0)return Reject(D.unexpected_overlay);
        return NodeStatus();
    }
    private string NodeStatus() {
        var run=RunManager.Instance?.DebugOnlyGetState();var node=NEventRoom.Instance;
        if(!ReferenceEquals(run!.CurrentRoom,_eventRoom))return ReferenceEquals(run.CurrentRoom,_room)?"waiting":Reject(D.node_room);
        if(node is null||ReferenceEquals(node,_binding.Room))return "waiting";
        if(node.GetType()!=typeof(NEventRoom)||!GodotObject.IsInstanceValid(node)||!ReferenceEquals(_binding.Run.EventRoom,node))return Reject(D.node_identity);
        if(node.Layout is null||!GodotObject.IsInstanceValid(node.Layout)||!ReferenceEquals(_binding.EventModel.Node,node.Layout))return Reject(D.node_layout);
        if(!ReferenceEquals(_eventRoom!.LocalMutableEvent,_binding.EventModel))return Reject(D.node_event);
        if(!node.IsVisibleInTree()||node.CustomEventNode is not null)return Reject(D.node_visibility);
        if(!GenericEventV7Binding.CombatLayoutReady(node))return Reject(D.node_combat_layout);
        if(!GodotObject.IsInstanceValid(_binding.Run)||!GodotObject.IsInstanceValid(_binding.Map)||!GodotObject.IsInstanceValid(_binding.Overlays)||
            !ReferenceEquals(MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen.Instance,_binding.Map)||
            !ReferenceEquals(_binding.Run.GlobalUi?.Overlays,_binding.Overlays)||!ReferenceEquals(_binding.Run.GlobalUi?.MapScreen,_binding.Map))return Reject(D.node_ui);
        if(_binding.Map.IsOpen||_binding.Map.IsTraveling||_binding.Map.IsTravelEnabled&&!_binding.EventModel.IsFinished)return Reject(D.node_travel);
        if(_resumedNode is not null&&(!ReferenceEquals(_resumedNode,node)||!ReferenceEquals(_resumedLayout,node.Layout)))return Reject(D.node_replaced);
        _resumedNode=node;_resumedLayout=node.Layout;return "resumed";
    }
    internal bool SameCombat()
    {
        var run=RunManager.Instance?.DebugOnlyGetState();
        return _room is not null && _state is not null && _node is not null &&
            (_preparedState is null||ReferenceEquals(_state,_preparedState)&&ReferenceEquals(_node,_preparedNode)&&!_room.ShouldCreateCombat) &&
            _node.GetType()==typeof(NCombatRoom)&&GodotObject.IsInstanceValid(_node)&&ReferenceEquals(NCombatRoom.Instance,_node)&&
            ReferenceEquals(typeof(NCombatRoom).GetField("_visuals",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(_node),_room)&& ReferenceEquals(NRun.Instance,_binding.Run)&&
            ReferenceEquals(run,_binding.RunState)&&ReferenceEquals(run!.CurrentRoom,_room)&&
            ReferenceEquals(CombatManager.Instance?.DebugOnlyGetState(),_state)&&
            ExtraRewardsValid(_room)&&ReferenceEquals(_room.CombatState,_state)&&ReferenceEquals(_room.Encounter,_encounter)&&
            ReferenceEquals(_state.RunState,run)&&ReferenceEquals(_binding.EventModel.Owner,_binding.Player)&&ReferenceEquals(_binding.Player.RunState,run)&&ReferenceEquals(_state.Encounter,_encounter)&&
            _room.ShouldResumeParentEventAfterCombat==Resumes&&Equals(_room.ParentEventId,_binding.EventModel.Id)&&
            _state.Players.Count==1&&ReferenceEquals(_state.Players[0],_binding.Player);
    }
}
