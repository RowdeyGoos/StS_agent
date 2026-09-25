using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Potions;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Items.Native;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed partial class GenericEventCompoundRewards
{
    private readonly Dictionary<PinnedRelicPickupChain.Frame,PhialPickup> _phials=new();
    private static readonly AsyncLocal<Procurement?> PotionScope=new();
    private MethodInfo? _procureMethod,_potionInsertMethod;
    private sealed class Procurement
    {
        internal readonly PhialPickup Leaf;
        internal readonly PotionModel Potion;
        internal readonly string Key;
        internal readonly PinnedAutomaticRelicEffects.State Before;
        internal Task<PotionProcureResult>? Task;
        internal PotionProcureResult? Inserted;
        internal bool Entered,Restored,Success;
        internal PotionProcureFailureReason Reason;
        internal Procurement(PhialPickup leaf,PotionModel potion)
        {Leaf=leaf;Potion=potion;Key=potion.Id.Entry;Before=new(leaf.Owner._binding.Player);}
        internal bool Complete()
        {
            Leaf.Owner.Require(Task?.IsFaulted!=true&&Task?.IsCanceled!=true);
            if(Task?.IsCompletedSuccessfully!=true)return false;
            var result=Task.Result;
            Leaf.Owner.Require(result is not null&&ReferenceEquals(result.potion,Potion)&&Potion.Id.Entry==Key&&
                (Inserted is null?!Entered&&!result.success&&result.failureReason==PotionProcureFailureReason.NotAllowed:
                    ReferenceEquals(result,Inserted)&&result.success==Success&&result.failureReason==Reason));
            return true;
        }
    }
    private sealed class PhialPickup
    {
        internal readonly GenericEventCompoundRewards Owner;
        internal readonly PinnedRelicPickupChain.Frame Frame;
        internal readonly List<Procurement> Calls=new();
        internal PinnedAutomaticRelicEffects? Effects;
        private bool _cleaned;
        internal PhialPickup(GenericEventCompoundRewards owner,PinnedRelicPickupChain.Frame frame){Owner=owner;Frame=frame;}
        internal IDisposable Enter()
        {
            Owner.Require(Frame.Relic.DynamicVars["PotionSlots"].IntValue==1&&Frame.Relic.DynamicVars["Potions"].IntValue==2);
            Owner.ObserveProcurements();
            Effects=new(Owner._binding.Player,Frame.Relic,Owner.Context,new PinnedAutomaticRelicEffects.CompoundPolicy {
                Authority=()=>ReferenceEquals(Owner.NativePickup,Frame)&&Frame.Certificate is null,Capacity=1
            });
            return Effects.EnterLease();
        }
        internal Procurement Enter(PotionModel potion,Player player,int slot)
        {
            Owner.Require(Owner.Context()&&ReferenceEquals(player,Owner._binding.Player)&&ReferenceEquals(Owner.NativePickup,Frame)&&
                slot==-1&&PotionScope.Value is null&&potion.Owner is null&&potion.Id.Entry.Length>0&&Effects!.Valid()&&
                player.PotionSlots.Count==Frame.Before.Potions.Length+1&&Calls.Count<2&&Calls.All(c=>c.Complete())&&Calls.All(c=>!ReferenceEquals(c.Potion,potion)));
            var call=new Procurement(this,potion);Calls.Add(call);return call;
        }
        internal bool Valid()
        {
            if(_cleaned)return Frame.Certificate?.Same(new(Owner._binding.Player))==true;
            if(Effects?.Valid()!=true)return false;
            foreach(var call in Calls)Owner.Require(call.Task?.IsFaulted!=true&&call.Task?.IsCanceled!=true);
            return Frame.AfterTask?.IsCompletedSuccessfully!=true||Frame.ObtainTask?.IsCompletedSuccessfully!=true||
                Calls.Count==2&&Calls.All(c=>c.Complete())&&Owner._binding.Player.PotionSlots.Count==Frame.Before.Potions.Length+1;
        }
        internal void Dispose(){if(_cleaned)return;Effects?.Dispose();_cleaned=true;}
    }
    private void ObserveProcurements()
    {
        if(_procureMethod is not null)return;
        var procure=typeof(PotionCmd).GetMethod("TryToProcure",new[]{typeof(PotionModel),typeof(Player),typeof(int)})!;
        var insert=typeof(Player).GetMethod("AddPotionInternal",new[]{typeof(PotionModel),typeof(int),typeof(bool)})!;
        Require(procure is not null&&procure.ReturnType==typeof(Task<PotionProcureResult>)&&insert is not null&&insert.ReturnType==typeof(PotionProcureResult)&&
            new[]{procure,insert}.All(m=>!(Harmony.GetPatchInfo(m)?.Owners.Any()??false)));
        _procureMethod=procure;_potionInsertMethod=insert;
        _hooks.Patch(procure,new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(ProcurePrefix)),new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(ProcurePostfix)),
            finalizer:new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(ProcureFinalizer)));
        _hooks.Patch(insert,new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(PotionInsertPrefix)),new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(PotionInsertPostfix)),
            finalizer:new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(PotionInsertFinalizer)));
    }
    private bool PotionHooksValid()=>new[]{_procureMethod,_potionInsertMethod}.Where(m=>m is not null).All(m=>
        Harmony.GetPatchInfo(m!) is {} info&&info.Owners.Count==1&&info.Owners.Contains(_hooks.Id));
    private static void ProcurePrefix(PotionModel __0,Player __1,int __2,out Procurement? __state)
    {
        __state=null;var owner=Active;if(owner?.NativePickup is not {} frame||!owner._phials.TryGetValue(frame,out var leaf))return;
        __state=leaf.Enter(__0,__1,__2);PotionScope.Value=__state;
    }
    private static void ProcurePostfix(Task<PotionProcureResult> __result,Procurement? __state)
    {
        if(__state is not {} call)return;
        try{call.Leaf.Owner.Require(call.Task is null&&__result is not null);call.Task=__result;}
        finally{RestorePotion(call);}
    }
    private static void ProcureFinalizer(Exception? __exception,Procurement? __state)
    {if(__state is {} call){if(__exception is not null)call.Leaf.Owner.Fail();RestorePotion(call);}}
    private static void RestorePotion(Procurement call){if(call.Restored)return;call.Restored=true;PotionScope.Value=null;}
    private static void PotionInsertPrefix(Player __instance,PotionModel __0,int __1,bool __2,out Procurement? __state)
    {
        __state=PotionScope.Value;if(__state is not {} call)return;
        var leaf=call.Leaf;
        leaf.Owner.Require(leaf.Owner.Context()&&ReferenceEquals(leaf.Owner.NativePickup,leaf.Frame)&&!call.Entered&&
            ReferenceEquals(__instance,leaf.Owner._binding.Player)&&ReferenceEquals(__0,call.Potion)&&__1==-1&&!__2&&
            __0.Id.Entry==call.Key&&call.Before.Same(new(__instance))&&leaf.Effects!.Valid());call.Entered=true;
    }
    private static void PotionInsertPostfix(PotionProcureResult __result,Procurement? __state)
    {
        if(__state is not {} call)return;var owner=call.Leaf.Owner;
        int slot=Array.FindIndex(call.Before.Potions,p=>p.Model is null);
        owner.Require(__result is not null&&call.Inserted is null&&ReferenceEquals(__result.potion,call.Potion)&&call.Potion.Id.Entry==call.Key&&
            __result.success==(slot>=0)&&__result.failureReason==(slot>=0?PotionProcureFailureReason.None:PotionProcureFailureReason.TooFull));
        var expected=call.Before.Potions.ToArray();if(slot>=0)expected[slot]=(call.Potion,call.Key);
        call.Leaf.Effects!.CertifyPotions(call.Before,expected);
        call.Inserted=__result;call.Success=__result.success;call.Reason=__result.failureReason;
    }
    private static void PotionInsertFinalizer(Exception? __exception,Procurement? __state)
    {if(__exception is not null)__state?.Leaf.Owner.Fail();}
}
