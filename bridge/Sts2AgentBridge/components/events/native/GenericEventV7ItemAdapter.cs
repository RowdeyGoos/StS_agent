using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.ItemV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// Derived inventory/surface projections from the frozen ItemV1 native adapter;
// authority comes from the owned generic Offer/creation/collection invocations.
internal sealed class GenericEventV7ItemAdapter : IGenericEventV7ItemNativeAdapter
{
    private readonly GenericEventV7ItemState _state;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private readonly ItemV1PotionSlotBinding[] _baseline;
    private readonly int _capacity;
    private bool _disposed;
    internal GenericEventV7ItemAdapter(GenericEventV7ItemState state)
    {
        _state=state;
        if(!state.Ready||!state.TryButton(out _)||!Slots(state.Binding.Player,out _capacity,out var slots))throw new InvalidOperationException("Item unavailable.");
        _baseline=slots.ToArray();
        if(_capacity+state.CapacityGain>8)throw new InvalidOperationException("Potion capacity bound.");
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
            using(var scope=GenericEventV7Hooks.EnterItemCollection(_state))_state.Button!.ForceClick();
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
        var current=Pending();
        if(_state.CapacityGain>0&&!CapacityEffect(current,false))throw new InvalidOperationException("Capacity pickup changed inventory.");
        return current;
    }
    private ItemV1PendingCapture Pending()
    {
        object? claimed=_state.Reward is PotionReward p?p.ClaimedPotion:((RelicReward)_state.Reward!).ClaimedRelic;
        string? key=claimed is PotionModel potion?potion.Id.Entry:claimed is RelicModel relic?relic.Id.Entry:null;
        if(!Slots(_state.Binding.Player,out int capacity,out var slots))throw new InvalidOperationException("Potion inventory changed.");
        return new ItemV1PendingCapture(_state.Binding.Run,_state.Binding.Player,_state.Reward!,_state.Model!,_state.Key,
            _state.Reward!.SuccessfullySelected,claimed,key,capacity,slots);
    }
    public GenericEventV7ItemCompletion CaptureCompletion()
    {
        try
        {
            bool owned=Owned()&&_state.Dispatched&&_state.CollectionEntered;
            bool effect=owned&&Effect(Pending());
            return new GenericEventV7ItemCompletion(owned,effect,owned&&_state.Binding.Overlays.ScreenCount==0,
                Witness(_state.CollectionTask),Witness(_state.OfferTask),Witness(_state.Binding.ItemParentTask));
        }
        catch{_state.Binding.Failed=true;return new GenericEventV7ItemCompletion(false,false,false,null,null,null);}
    }
    private bool Effect(ItemV1PendingCapture p)
    {
        if(!p.SuccessfullySelected||!ReferenceEquals(p.ClaimedModelIdentity,_state.Model)||p.ClaimedStableKey!=_state.Key)return false;
        if(_state.Kind==ItemV1ItemKind.Relic)return _state.CapacityGain==0||CapacityEffect(p,true);
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
    private bool CapacityEffect(ItemV1PendingCapture current,bool complete)
    {
        int gain=current.PotionCapacity-_capacity;
        if(current.PotionSlots.Count!=current.PotionCapacity ||
            (complete?gain!=_state.CapacityGain:gain!=0&&gain!=_state.CapacityGain))return false;
        for(int i=0;i<current.PotionSlots.Count;i++) {
            var now=current.PotionSlots[i];
            if(i>=_baseline.Length) {if(now.ModelIdentity is not null||now.StableKey is not null)return false;}
            else if(!ReferenceEquals(now.ModelIdentity,_baseline[i].ModelIdentity)||now.StableKey!=_baseline[i].StableKey)return false;
        }
        if(complete && (_state.Model is not RelicModel relic || !ReferenceEquals(relic.Owner,_state.Binding.Player)||
            _state.Binding.Player.Relics.Count(r=>ReferenceEquals(r,relic))!=1))return false;
        return true;
    }
    private bool SameBaseline(int capacity,IReadOnlyList<ItemV1PotionSlotBinding> slots)
    {
        if(capacity!=_capacity||slots.Count!=_baseline.Length)return false;
        for(int i=0;i<slots.Count;i++)if(!ReferenceEquals(slots[i].ModelIdentity,_baseline[i].ModelIdentity)||slots[i].StableKey!=_baseline[i].StableKey)return false;
        return true;
    }
    private static GenericEventV7ItemTaskWitness? Witness(System.Threading.Tasks.Task? task)=>task is null?null:new(task,
        task.IsCanceled?GenericEventV7ItemTaskState.Canceled:task.IsFaulted?GenericEventV7ItemTaskState.Faulted:
        task.IsCompletedSuccessfully?GenericEventV7ItemTaskState.Succeeded:GenericEventV7ItemTaskState.Pending);
    internal static bool Slots(Player player,out int capacity,out List<ItemV1PotionSlotBinding> slots)
    {
        capacity=player.MaxPotionCount;var source=player.PotionSlots;int count=source.Count;slots=new();
        if(capacity<0||capacity>8||count!=capacity)return false;
        for(int i=0;i<count;i++)
        {var potion=source[i];string? key=potion?.Id.Entry;if(potion is not null&&(key is null||!GenericEventV7ItemState.ValidKey(key)))return false;slots.Add(new(potion,key));}
        return source.Count==count&&player.MaxPotionCount==capacity;
    }
    public void Dispose()
    {if(_disposed)return;if(System.Environment.CurrentManagedThreadId!=_thread)throw new InvalidOperationException("Owner thread required.");_disposed=true;}
}


// Exact generated entries share the Offer and screen. No reward generation,
// native collection or parent-completion task is manufactured by this adapter.
internal sealed class GenericEventV7ItemSetAdapter : IGenericEventV7ItemSetNativeAdapter {
    private readonly GenericEventV7ItemState _root;
    private readonly ItemV1PotionSlotBinding[] _baseline;
    private readonly int _capacity, _thread=System.Environment.CurrentManagedThreadId;
    private readonly List<GenericEventV7ItemAdapter> _adapters=new();
    private readonly Dictionary<object,int> _settledPotionSlots=new(ReferenceEqualityComparer.Instance);
    private readonly Dictionary<GenericEventV7ItemState,System.Threading.Tasks.Task> _settled=new();
    private readonly System.Threading.Tasks.Task _offerTask, _chosenTask;
    private bool _disposed;
    internal GenericEventV7ItemSetAdapter(GenericEventV7ItemState root) {
        _root=root;
        if(!root.Domain()||!root.Ready||!GenericEventV7ItemAdapter.Slots(root.Binding.Player,out _capacity,out var slots))throw new InvalidOperationException("Item set unavailable.");
        _baseline=slots.ToArray();_offerTask=root.OfferTask!;_chosenTask=root.Binding.ItemParentTask!;
        if(!root.CapacityPlan())throw new InvalidOperationException("Item-set capacity unavailable.");
        foreach(var entry in root.Entries!){entry.Screen=root.Screen;entry.OfferTask=root.OfferTask;}
    }
    public int OfferCount=>_root.OfferCount;
    private bool Owned()=>!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&_root.Domain()&&_root.Overlay()&&
        ReferenceEquals(_root.OfferTask,_offerTask)&&ReferenceEquals(_root.Binding.ItemParentTask,_chosenTask)&&
        _root.Entries!.All(e=>!e.FailedTask&&ReferenceEquals(e.OfferTask,_offerTask))&&_root.Binding.ItemParentTask is {IsFaulted:false,IsCanceled:false}&&Inventory();
    private bool Inventory() {
        if(!GenericEventV7ItemAdapter.Slots(_root.Binding.Player,out int capacity,out var slots)||!_root.CapacityMatches(_capacity,capacity)||slots.Count!=capacity)return false;
        var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
        for(int i=0;i<slots.Count;i++) {
            var before=i<_baseline.Length?_baseline[i]:new ItemV1PotionSlotBinding(null,null);var now=slots[i];
            if(ReferenceEquals(before.ModelIdentity,now.ModelIdentity)&&before.StableKey==now.StableKey)continue;
            if(before.ModelIdentity is not null||now.ModelIdentity is null||!seen.Add(now.ModelIdentity)||
                !_root.Entries!.Any(e=>e.Kind==ItemV1ItemKind.Potion&&e.Dispatched&&ReferenceEquals(e.Model,now.ModelIdentity)&&e.Key==now.StableKey))return false;
        }
        foreach(var pair in _settled) {
            if(!pair.Key.Reward!.SuccessfullySelected||!ReferenceEquals(pair.Key.CollectionTask,pair.Value)||!pair.Value.IsCompletedSuccessfully)return false;
        }
        foreach(var pair in _settledPotionSlots)if(!ReferenceEquals(slots[pair.Value].ModelIdentity,pair.Key))return false;
        foreach(var e in _root.Entries!) {
            if(!e.Reward!.SuccessfullySelected)continue;
            object? claimed=e.Reward is PotionReward p?p.ClaimedPotion:((RelicReward)e.Reward).ClaimedRelic;
            if(!e.Dispatched||!ReferenceEquals(claimed,e.Model)||e.Kind==ItemV1ItemKind.Potion&&!seen.Contains(e.Model!))return false;
        }
        return true;
    }
    public IItemV1NativeAdapter CreateEntry(int index) {
        if(!Owned()||index!=_adapters.Count||index<0||index>=OfferCount||
            _root.Entries!.Take(index).Any(e=>!e.Reward!.SuccessfullySelected||e.CollectionTask?.IsCompletedSuccessfully!=true))throw new InvalidOperationException("Unsettled item-set entry.");
        var adapter=new GenericEventV7ItemAdapter(_root.Entries![index]);_adapters.Add(adapter);
        return new Entry(this,adapter);
    }
    public GenericEventV7ItemCompletion CaptureCompletion(int index) {
        if(!Owned()||index!=_adapters.Count-1)throw new InvalidOperationException("Item-set ownership lost.");
        var result=_adapters[index].CaptureCompletion();
        if(result.OwnershipValid&&result.EffectStillValid&&result.Collection?.State==GenericEventV7ItemTaskState.Succeeded) {
            var entry=_root.Entries![index];_settled.TryAdd(entry,entry.CollectionTask!);
            if(entry.Kind==ItemV1ItemKind.Potion&&!_settledPotionSlots.ContainsKey(entry.Model!)) {
                if(!GenericEventV7ItemAdapter.Slots(_root.Binding.Player,out _,out var slots))throw new InvalidOperationException("Settled inventory unavailable.");
                int at=slots.FindIndex(s=>ReferenceEquals(s.ModelIdentity,entry.Model));
                if(at<0)throw new InvalidOperationException("Settled potion absent.");_settledPotionSlots.Add(entry.Model!,at);
            }
        }
        return result;
    }
    public void Dispose(){
        if(_disposed)return;
        if(System.Environment.CurrentManagedThreadId!=_thread)throw new InvalidOperationException("Item-set owner required.");
        foreach(var adapter in _adapters)adapter.Dispose();_disposed=true;
    }
    private sealed class Entry : IItemV1NativeAdapter {
        private readonly GenericEventV7ItemSetAdapter _owner;private readonly GenericEventV7ItemAdapter _entry;
        internal Entry(GenericEventV7ItemSetAdapter owner,GenericEventV7ItemAdapter entry){_owner=owner;_entry=entry;}
        public ItemV1SurfaceCapture CaptureSurface(){if(!_owner.Owned())return ItemV1SurfaceCapture.Unsupported();return _entry.CaptureSurface();}
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe){if(!_owner.Owned())throw new InvalidOperationException("Item-set effect changed.");return _entry.CapturePending(probe);}
    }
}
