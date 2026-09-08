using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.ItemV1;
namespace Sts2AgentBridge.Successors.GenericEventV6.Native;

// Derived inventory/surface projections from the frozen ItemV1 native adapter;
// authority comes from the owned generic Offer/creation/collection invocations.
internal sealed class GenericEventV6ItemAdapter : IGenericEventV6ItemNativeAdapter
{
    private readonly GenericEventV6ItemState _state;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private readonly ItemV1PotionSlotBinding[] _baseline;
    private readonly int _capacity;
    private bool _disposed;
    internal GenericEventV6ItemAdapter(GenericEventV6ItemState state)
    {
        _state=state;
        if(!state.Ready||!state.TryButton(out _)||!Slots(state.Binding.Player,out _capacity,out var slots))throw new InvalidOperationException("Item unavailable.");
        _baseline=slots.ToArray();
        if(state.Kind==ItemV1ItemKind.Potion&&!slots.Exists(s=>s.ModelIdentity is null))throw new InvalidOperationException("Potion capacity unavailable.");
    }
    private bool Owned()=>!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&_state.Domain()&&_state.Overlay()&&!_state.FailedTask;
    public ItemV1SurfaceCapture CaptureSurface()
    {
        if(!Owned()||_state.Dispatched||_state.Reward!.SuccessfullySelected||!_state.TryButton(out var button)||
            !Slots(_state.Binding.Player,out int capacity,out var slots)||!SameBaseline(capacity,slots))return ItemV1SurfaceCapture.Unsupported();
        return ItemV1SurfaceCapture.Available(_state.Binding.Run,_state.Binding.Player,_state.Screen!,capacity,
            new[]{new ItemV1NativeOffer(_state.Index,_state.Kind,_state.Key,true,false,true,true,button!,_state.Reward!,_state.Model!,Dispatch)},slots);
    }
    private void Dispatch()
    {
        if(CaptureSurface().Status!=ItemV1SurfaceStatus.Available)throw new InvalidOperationException("Stale item control.");
        _state.Dispatched=true;
        try
        {
            using(var scope=GenericEventV6Hooks.EnterItemCollection(_state))_state.Button!.ForceClick();
            // The retained release path invokes GetReward synchronously. A missed
            // invocation has no later global fallback or second dispatch.
            if(!_state.CollectionEntered||_state.CollectionTask is null)throw new InvalidOperationException("Collection invocation absent.");
        }
        catch{_state.Binding.Failed=true;throw;}
    }
    public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending)
    {
        if(!Owned()||!_state.Dispatched||!ReferenceEquals(pending.RunIdentity,_state.Binding.Run)||
            !ReferenceEquals(pending.PlayerIdentity,_state.Binding.Player)||!ReferenceEquals(pending.RewardIdentity,_state.Reward)||
            !ReferenceEquals(pending.OfferedModelIdentity,_state.Model)||pending.Kind!=_state.Kind)
            throw new InvalidOperationException("Item ownership lost.");
        return Pending();
    }
    private ItemV1PendingCapture Pending()
    {
        object? claimed=_state.Reward is PotionReward p?p.ClaimedPotion:((RelicReward)_state.Reward!).ClaimedRelic;
        string? key=claimed is PotionModel potion?potion.Id.Entry:claimed is RelicModel relic?relic.Id.Entry:null;
        if(!Slots(_state.Binding.Player,out int capacity,out var slots))throw new InvalidOperationException("Potion inventory changed.");
        return new ItemV1PendingCapture(_state.Binding.Run,_state.Binding.Player,_state.Reward!,_state.Model!,_state.Key,
            _state.Reward!.SuccessfullySelected,claimed,key,capacity,slots);
    }
    public GenericEventV6ItemCompletion CaptureCompletion()
    {
        try
        {
            bool owned=Owned()&&_state.Dispatched&&_state.CollectionEntered;
            bool effect=owned&&Effect(Pending());
            return new GenericEventV6ItemCompletion(owned,effect,owned&&_state.Binding.Overlays.ScreenCount==0,
                Witness(_state.CollectionTask),Witness(_state.OfferTask),Witness(_state.Binding.ChosenTask));
        }
        catch{_state.Binding.Failed=true;return new GenericEventV6ItemCompletion(false,false,false,null,null,null);}
    }
    private bool Effect(ItemV1PendingCapture p)
    {
        if(!p.SuccessfullySelected||!ReferenceEquals(p.ClaimedModelIdentity,_state.Model)||p.ClaimedStableKey!=_state.Key)return false;
        if(_state.Kind==ItemV1ItemKind.Relic)return true;
        if(p.PotionCapacity!=_capacity||p.PotionSlots.Count!=_baseline.Length)return false;
        int inserted=0;
        for(int i=0;i<_baseline.Length;i++)
        {
            var before=_baseline[i];var now=p.PotionSlots[i];
            if(before.ModelIdentity is null&&ReferenceEquals(now.ModelIdentity,_state.Model)&&now.StableKey==_state.Key){inserted++;continue;}
            if(!ReferenceEquals(before.ModelIdentity,now.ModelIdentity)||before.StableKey!=now.StableKey)return false;
        }
        return inserted==1;
    }
    private bool SameBaseline(int capacity,IReadOnlyList<ItemV1PotionSlotBinding> slots)
    {
        if(capacity!=_capacity||slots.Count!=_baseline.Length)return false;
        for(int i=0;i<slots.Count;i++)if(!ReferenceEquals(slots[i].ModelIdentity,_baseline[i].ModelIdentity)||slots[i].StableKey!=_baseline[i].StableKey)return false;
        return true;
    }
    private static GenericEventV6ItemTaskWitness? Witness(System.Threading.Tasks.Task? task)=>task is null?null:new(task,
        task.IsCanceled?GenericEventV6ItemTaskState.Canceled:task.IsFaulted?GenericEventV6ItemTaskState.Faulted:
        task.IsCompletedSuccessfully?GenericEventV6ItemTaskState.Succeeded:GenericEventV6ItemTaskState.Pending);
    internal static bool Slots(Player player,out int capacity,out List<ItemV1PotionSlotBinding> slots)
    {
        capacity=player.MaxPotionCount;var source=player.PotionSlots;int count=source.Count;slots=new();
        if(capacity<0||capacity>8||count!=capacity)return false;
        for(int i=0;i<count;i++)
        {var potion=source[i];string? key=potion?.Id.Entry;if(potion is not null&&(key is null||!GenericEventV6ItemState.ValidKey(key)))return false;slots.Add(new(potion,key));}
        return source.Count==count&&player.MaxPotionCount==capacity;
    }
    public void Dispose()
    {if(_disposed)return;if(System.Environment.CurrentManagedThreadId!=_thread)throw new InvalidOperationException("Owner thread required.");_disposed=true;}
}
