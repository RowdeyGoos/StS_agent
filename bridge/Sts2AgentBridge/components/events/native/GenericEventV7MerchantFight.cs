using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Models.Potions;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// An explicit Foul Potion action, owned from native enqueue through the exact
// Fake Merchant callback. It cannot turn an unrelated combat into a handoff.
internal sealed class GenericEventV7MerchantFight : IDisposable {
    private static readonly AsyncLocal<GenericEventV7MerchantFight?> Scope=new();
    private static GenericEventV7MerchantFight? Active;
    private readonly Harmony _hooks=new("sts.bridge.merchant.fight."+Guid.NewGuid().ToString("N"));
    private readonly List<MethodBase> _targets=new();
    private readonly NRun _run;
    private readonly FakeMerchant _event;
    private readonly Player _player;
    private readonly IRunState _state;
    private readonly FoulPotion _potion;
    private readonly int _slot,_thread=Environment.CurrentManagedThreadId;
    private readonly Func<bool> _origin,_phaseOrigin;
    private readonly ActionQueueSynchronizer _queue;
    private readonly object _network;
    private readonly PotionModel?[] _potions;
    private readonly string?[] _potionKeys;
    private readonly CardSelectionV1DeckCard[] _deck;
    private readonly RelicModel[] _relics,_offers;
    private readonly string[] _relicKeys;
    private readonly int _gold,_capacity;
    private Task? _thrown,_execute;
    private GameAction? _action;
    private Task? _completion;
    private long _deadline;
    private bool _invoked,_entered,_thrownSeen,_executing,_disposed,_settled;
    private volatile bool _failed;
    internal GenericEventV7CombatHandoff? Combat {get;private set;}
    private static object? Network(ActionQueueSynchronizer queue)=>typeof(ActionQueueSynchronizer).GetField("_netService",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(queue);
    internal static bool Eligible(Player player,int slot) {
        if(CombatManager.Instance?.IsInProgress!=false||RunManager.Instance?.ActionQueueSynchronizer is not {} queue||Network(queue) is not MegaCrit.Sts2.Core.Multiplayer.Game.INetGameService net||(int)net.Type!=1||!player.CanRemovePotions||
            slot<0||slot>=player.PotionSlots.Count||player.PotionSlots.Count!=player.MaxPotionCount||player.MaxPotionCount>8||player.PotionSlots[slot] is not FoulPotion potion||potion.GetType()!=typeof(FoulPotion)||
            !ReferenceEquals(potion.Owner,player)||potion.IsQueued||potion.HasBeenRemovedFromState)return false;
        return typeof(FoulPotion).GetProperty("PassesCustomUsabilityCheck",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)?.GetValue(potion) is true;
    }
    internal GenericEventV7MerchantFight(NRun run,FakeMerchant model,Player player,int slot,Func<bool> origin,Func<bool> phaseOrigin,RelicModel[] offers) {
        if(!Eligible(player,slot)||!origin())throw new InvalidOperationException("Foul Potion unavailable.");
        _run=run;_event=model;_player=player;_state=player.RunState;_slot=slot;_potion=(FoulPotion)player.PotionSlots[slot]!;_origin=origin;_phaseOrigin=phaseOrigin;
        _queue=RunManager.Instance!.ActionQueueSynchronizer;_network=Network(_queue)!;_potions=player.PotionSlots.ToArray();_potionKeys=_potions.Select(p=>p?.Id.Entry).ToArray();
        _deck=GenericEventV7Binding.CopyDeck(player);_relics=player.Relics.ToArray();_relicKeys=_relics.Select(r=>r.Id.Entry).ToArray();_offers=offers.ToArray();_gold=player.Gold;_capacity=player.MaxPotionCount;
    }
    private bool Owner()=>!_failed&&!_disposed&&ReferenceEquals(Active,this)&&Environment.CurrentManagedThreadId==_thread&&Environment.TickCount64<=_deadline&&
        ReferenceEquals(NRun.Instance,_run)&&ReferenceEquals(RunManager.Instance?.DebugOnlyGetState(),_state)&&ReferenceEquals(_player.RunState,_state)&&ReferenceEquals(_event.Owner,_player)&&
        ReferenceEquals(RunManager.Instance?.ActionQueueSynchronizer,_queue)&&ReferenceEquals(Network(_queue),_network)&&_network is MegaCrit.Sts2.Core.Multiplayer.Game.INetGameService net&&(int)net.Type==1;
    private bool Inventory(bool complete) {
        var deck=GenericEventV7Binding.CopyDeck(_player);
        if(_player.Gold!=_gold||_player.MaxPotionCount!=_capacity||_player.PotionSlots.Count!=_potions.Length||!_player.Relics.SequenceEqual(_relics,ReferenceEqualityComparer.Instance)||
            _relics.Where((r,i)=>r.Id.Entry!=_relicKeys[i]||!ReferenceEquals(r.Owner,_player)).Any()||deck.Length!=_deck.Length||deck.Where((c,i)=>!GenericEventV7Binding.SameDeckCard(c,_deck[i])).Any())return false;
        for(int i=0;i<_potions.Length;i++) {
            var current=_player.PotionSlots[i];
            if(i==_slot&&_entered&&current is null){if(complete&&!_potion.HasBeenRemovedFromState)return false;continue;}
            if(complete&&i==_slot||!ReferenceEquals(current,_potions[i])||current?.Id.Entry!=_potionKeys[i]||current is not null&&!ReferenceEquals(current.Owner,_player))return false;
        }
        return true;
    }
    internal void Dispatch() {
        Require(!_invoked&&Active is null&&_origin()&&Eligible(_player,_slot));_invoked=true;_deadline=Environment.TickCount64+30000;Active=this;
        try {
            var actionType=typeof(GameAction).Assembly.GetType("MegaCrit.Sts2.Core.GameActions.UsePotionAction")!;
            Patch(typeof(ActionQueueSynchronizer).GetMethod("RequestEnqueue",new[]{typeof(GameAction)})!,nameof(EnqueuePrefix),null);
            Patch(actionType.GetMethod("ExecuteAction",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)!,nameof(ExecutePrefix),nameof(ExecutePostfix));
            Patch(typeof(FakeMerchant).GetMethod("FoulPotionThrown",new[]{typeof(FoulPotion)})!,nameof(ThrownPrefix),nameof(ThrownPostfix));
            Patch(typeof(EventModel).GetMethod("EnterCombatWithoutExitingEvent",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,null,new[]{typeof(EncounterModel),typeof(IReadOnlyList<Reward>),typeof(bool)},null)!,nameof(CombatPrefix),nameof(CombatPostfix));
            var previous=Scope.Value;try {
                Scope.Value=this;
                typeof(PotionModel).GetMethod("EnqueueManualUse",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)!.Invoke(_potion,new object?[]{null});
            }finally{Scope.Value=previous;}
            Require(_action is not null);
        }catch{Abort();throw;}
    }
    private void Patch(MethodInfo method,string prefix,string? postfix) {
        Require(method is not null&&!method.IsGenericMethod&&method.GetMethodBody() is not null);_targets.Add(method);
        _hooks.Patch(method,prefix:new HarmonyMethod(typeof(GenericEventV7MerchantFight),prefix),postfix:postfix is null?null:new HarmonyMethod(typeof(GenericEventV7MerchantFight),postfix));
    }
    private static void EnqueuePrefix(ActionQueueSynchronizer __instance,GameAction __0) {
        if(Scope.Value is not {} s)return;
        s.Require(s.Owner()&&ReferenceEquals(__instance,s._queue)&&s._action is null&&s._origin()&&s.Inventory(false)&&s._potion.IsQueued&&
            __0.GetType().FullName=="MegaCrit.Sts2.Core.GameActions.UsePotionAction"&&ReferenceEquals(Property(__0,"Player"),s._player)&&Convert.ToInt32(Property(__0,"PotionIndex"))==s._slot&&Property(__0,"WasEnqueuedInCombat") is false);
        s._action=__0;s._completion=__0.CompletionTask;__0.BeforeExecuted+=s.BeforeExecute;
    }
    private void BeforeExecute(GameAction action) {
        Require(Owner()&&ReferenceEquals(action,_action)&&!_entered&&_origin()&&Inventory(false)&&_potion.IsQueued&&!_potion.HasBeenRemovedFromState&&CombatManager.Instance?.IsInProgress==false&&_potion.PassesCustomUsabilityCheck);
        _entered=true;action.BeforeExecuted-=BeforeExecute;
    }
    private static void ExecutePrefix(GameAction __instance,out GenericEventV7MerchantFight? __state) {
        __state=null;if(Active is not {} s||!ReferenceEquals(__instance,s._action))return;
        s.Require(s.Owner()&&s._entered&&!s._executing&&s._origin()&&s.Inventory(false)&&ReferenceEquals(s._player.PotionSlots[s._slot],s._potion)&&s._potion.IsQueued&&!s._potion.HasBeenRemovedFromState&&s._player.CanRemovePotions&&s._potion.PassesCustomUsabilityCheck&&CombatManager.Instance?.IsInProgress==false&&(Scope.Value is null||ReferenceEquals(Scope.Value,s)));
        __state=Scope.Value;s._executing=true;Scope.Value=s;
    }
    private static void ExecutePostfix(GameAction __instance,Task __result,GenericEventV7MerchantFight? __state) {
        if(Active is {} s&&ReferenceEquals(__instance,s._action)){s._execute=__result;Scope.Value=__state;}
    }
    private static void ThrownPrefix(FakeMerchant __instance,FoulPotion __0,out GenericEventV7MerchantFight? __state) {
        __state=Scope.Value;if(__state is not {} s)return;
        s.Require(s.Owner()&&s._entered&&s._executing&&!s._thrownSeen&&!s._event.StartedFight&&ReferenceEquals(__instance,s._event)&&ReferenceEquals(__0,s._potion)&&s.Inventory(false));s._thrownSeen=true;
    }
    private static void ThrownPostfix(Task __result,GenericEventV7MerchantFight? __state){if(__state is {} s)s._thrown=__result;}
    private static void CombatPrefix(EventModel __instance,EncounterModel __0,IReadOnlyList<Reward> __1,bool __2,out GenericEventV7MerchantFight? __state) {
        __state=Scope.Value;if(__state is not {} s)return;
        s.Require(s.Owner()&&s._phaseOrigin()&&s.Inventory(false)&&s._thrownSeen&&s.Combat is null&&s._event.StartedFight&&ReferenceEquals(__instance,s._event)&&!__2&&__0.GetType().Name=="FakeMerchantEventEncounter"&&
            __1.Count==s._offers.Length+1&&__1.All(r=>r.GetType()==typeof(RelicReward))&&((RelicReward)__1[0]).Relic is {} rug&&rug.Id.Entry=="FAKE_MERCHANTS_RUG");
        for(int i=0;i<s._offers.Length;i++)s.Require(ReferenceEquals(((RelicReward)__1[i+1]).Relic,s._offers[i]));
        s.Combat=new(s._run,s._state,s._player,s._event,__0,__1,()=>s._thrown,()=>!s._failed);
    }
    private static void CombatPostfix(GenericEventV7MerchantFight? __state){if(__state?.Combat is {} combat)combat.Returned=true;}
    private static object? Property(object value,string name)=>value.GetType().GetProperty(name,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)?.GetValue(value);
    internal string Capture() {
        Require(Owner()&&(Combat is not null||_phaseOrigin())&&Inventory(false)&&_action is not null&&ReferenceEquals(_action.CompletionTask,_completion)&&_action.Exception is null&&_completion is {IsFaulted:false,IsCanceled:false}&&_execute is not {IsFaulted:true} and not {IsCanceled:true});
        if(_completion?.IsCompletedSuccessfully!=true)return "waiting";
        Require(_entered&&_execute?.IsCompletedSuccessfully==true&&_thrown?.IsCompletedSuccessfully==true&&Inventory(true)&&Combat is not null&&(int)_action!.State==5);
        string result=Combat!.Capture(out _);if(result=="combat")_settled=true;return result;
    }
    internal void Abort()=>_failed=true;
    public void Dispose() {
        if(_disposed){if(_failed)throw new InvalidOperationException("Merchant fight cleanup uncertain.");return;}
        try {Require(!_invoked||_settled&&Capture()=="combat");}
        catch{Abort();throw;}
        finally {
            _disposed=true;
            try{_hooks.UnpatchAll(_hooks.Id);if(_targets.Any(t=>Harmony.GetPatchInfo(t)?.Owners.Contains(_hooks.Id)==true))throw new InvalidOperationException("Merchant fight hooks retained.");}
            catch{Abort();throw;}
            finally{if(!_failed&&ReferenceEquals(Active,this))Active=null;}
        }
    }
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool ok){if(!ok){Abort();throw new InvalidOperationException("Merchant potion action lost ownership.");}}
}
