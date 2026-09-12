using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.CardSelectionV1;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// A single generated set owns every menu. Completed entries remain witnesses;
// the active entry's full deck baseline includes all earlier verified insertions.
internal sealed class GenericEventV7CardRewardSetAdapter : IGenericEventV7MixedRewardSetAdapter {
    private readonly GenericEventV7ItemState _root;
    private readonly Task _offer,_chosen;
    private readonly int _thread=Environment.CurrentManagedThreadId;
    private readonly List<bool> _settled=new();
    private int _active=-1;
    private CardSelectionV1DeckCard[] _deck;
    private readonly ItemV1PotionSlotBinding[]? _inventory;
    private readonly int _capacity;
    private readonly Dictionary<int,GenericEventV7ItemAdapter> _items=new();
    private readonly Dictionary<int,Task> _itemTasks=new();
    private readonly Dictionary<object,int> _potionSlots=new(ReferenceEqualityComparer.Instance);
    public IReadOnlyList<string>? OfferKinds {get;}

    private bool _dismissed,_disposed;
    internal GenericEventV7CardRewardSetAdapter(GenericEventV7ItemState root) {
        _root=root;
        if(!root.Ready||!root.Domain()||root.OfferCount is <2 or >8||!root.HasCards)throw new InvalidOperationException("Card reward set unavailable.");
        _deck=GenericEventV7Binding.CopyDeck(root.Binding.Player);
        if(root.IsMixed) {
            OfferKinds=Array.AsReadOnly(root.Entries!.Select(e=>e.CardReward is not null?"card":e.Kind==ItemV1ItemKind.Potion?"potion":"relic").ToArray());
            if(!GenericEventV7ItemAdapter.Slots(root.Binding.Player,out _capacity,out var slots)||!root.CapacityPlan())throw new InvalidOperationException("Mixed reward capacity unavailable.");
            _inventory=slots.ToArray();
        }
        _offer=root.OfferTask!;_chosen=root.Binding.ChosenTask!;
        foreach(var entry in root.Entries!){entry.OfferTask=_offer;entry.Screen=root.Screen;}
    }
    public int OfferCount=>_root.OfferCount;
    private GenericEventV7CardRewardAdapter Active=>_root.Entries![_active].CardReward!;
    private bool Owned() {
        if(_disposed||Environment.CurrentManagedThreadId!=_thread||!_root.Domain()||
            !ReferenceEquals(_root.OfferTask,_offer)||!ReferenceEquals(_root.Binding.ChosenTask,_chosen)||
            _offer.IsFaulted||_offer.IsCanceled||_chosen.IsFaulted||_chosen.IsCanceled)return false;
        for(int i=0;i<OfferCount;i++) {
            var e=_root.Entries![i];
            if(!ReferenceEquals(e.OfferTask,_offer)||!ReferenceEquals(e.Screen,_root.Screen)||e.FailedTask||
                i>_active&&(e.Dispatched||e.CollectionEntered||e.CollectionTask is not null))return false;
            if(i<_settled.Count&&e.CardReward is {} card&&!card.RetainResult(_settled[i]))return false;
        }
        if(!Inventory())return false;
        if(_active>=0&&_active==_settled.Count&&_root.Entries![_active].CardReward is {} active)return active.RetainDeck();
        var deck=GenericEventV7Binding.CopyDeck(_root.Binding.Player);
        return deck.Length==_deck.Length&&deck.Zip(_deck).All(pair=>ReferenceEquals(pair.First.ModelIdentity,pair.Second.ModelIdentity)&&
            pair.First.StableKey==pair.Second.StableKey&&pair.First.UpgradeLevel==pair.Second.UpgradeLevel&&CardSelectionV1Enchantment.Same(pair.First.Enchantment,pair.Second.Enchantment)&&
            pair.First.ModelIdentity is CardModel model&&ReferenceEquals(model.Owner,_root.Binding.Player)&&ReferenceEquals(model.RunState,_root.Binding.RunState));
    }
    private GenericEventV7CardRewardAdapter DismissCard=>_root.Entries!.Last(e=>e.CardReward is not null).CardReward!;
    public string CaptureState() {
        if(!Owned())return "unsupported";
        if(_settled.Count<OfferCount) {
            if((_offer.IsCompleted||_chosen.IsCompleted)&&_active!=OfferCount-1)return "unsupported";
            return "entry";
        }
        bool skipped=_settled.Any(selected=>!selected);
        if(!skipped||_dismissed) {
            if(_root.Binding.Overlays.ScreenCount!=0&&(!_root.Overlay()||_root.Binding.Overlays.ScreenCount!=1))return "unsupported";
            if(_offer.IsCompletedSuccessfully&&_chosen.IsCompletedSuccessfully)
                return _root.Binding.Overlays.ScreenCount==0?"complete":"unsupported";
            return "waiting";
        }
        if(_offer.IsCompleted||_chosen.IsCompleted)return "unsupported";
        return DismissCard.DismissReady()?"dismiss":"waiting";
    }
    public IGenericEventV7RewardAdapter CreateEntry(int index) {
        if(!Owned()||index!=_settled.Count||index!=_active+1||index>=OfferCount||_root.Entries![index].CardReward is null)throw new InvalidOperationException("Unsettled card reward entry.");
        _root.Entries![index].CardReward!.Start(batch:true,retainBaseline:index==0);_active=index;return new Entry(this,index);
    }
    public void SettleEntry(int index,bool selected) {
        if(!Owned()||index!=_active||index!=_settled.Count||Active.Capture().Phase!="complete"||!Active.RetainResult(selected))throw new InvalidOperationException("Card reward result changed.");
        _deck=GenericEventV7Binding.CopyDeck(_root.Binding.Player);_settled.Add(selected);
    }
    public void Dismiss() {
        if(_dismissed||CaptureState()!="dismiss")throw new InvalidOperationException("Card reward set dismissal unavailable.");
        _dismissed=true;DismissCard.DismissSet();
    }
    private bool Inventory() {
        if(_inventory is null)return true;
        if(!GenericEventV7ItemAdapter.Slots(_root.Binding.Player,out int capacity,out var slots)||!_root.CapacityMatches(_capacity,capacity)||slots.Count!=capacity)return false;
        var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
        for(int i=0;i<slots.Count;i++) {
            var before=i<_inventory.Length?_inventory[i]:new ItemV1PotionSlotBinding(null,null);var now=slots[i];
            if(ReferenceEquals(before.ModelIdentity,now.ModelIdentity)&&before.StableKey==now.StableKey)continue;
            if(before.ModelIdentity is not null||now.ModelIdentity is null||!seen.Add(now.ModelIdentity)||
                !_root.Entries!.Any(e=>e.CardReward is null&&e.Kind==ItemV1ItemKind.Potion&&e.Dispatched&&ReferenceEquals(e.Model,now.ModelIdentity)&&e.Key==now.StableKey))return false;
        }
        foreach(var pair in _itemTasks) {
            var e=_root.Entries![pair.Key];
            if(!e.Reward!.SuccessfullySelected||!ReferenceEquals(e.CollectionTask,pair.Value)||!pair.Value.IsCompletedSuccessfully)return false;
        }
        foreach(var pair in _potionSlots)if(!ReferenceEquals(slots[pair.Value].ModelIdentity,pair.Key))return false;
        foreach(var e in _root.Entries!) {
            if(e.CardReward is not null||!e.Reward!.SuccessfullySelected)continue;
            object? claimed=e.Reward is PotionReward potion?potion.ClaimedPotion:((RelicReward)e.Reward).ClaimedRelic;
            if(!e.Dispatched||!ReferenceEquals(claimed,e.Model)||e.Kind==ItemV1ItemKind.Potion&&!seen.Contains(e.Model!))return false;
        }
        return true;
    }
    public IItemV1NativeAdapter CreateItemEntry(int index) {
        if(OfferKinds is null||!Owned()||index!=_settled.Count||index!=_active+1||index>=OfferCount||_root.Entries![index].CardReward is not null)throw new InvalidOperationException("Unsettled mixed item entry.");
        var adapter=new GenericEventV7ItemAdapter(_root.Entries![index]);_items.Add(index,adapter);_active=index;return new ItemEntry(this,index,adapter);
    }
    public GenericEventV7ItemCompletion CaptureItemCompletion(int index) {
        if(!Owned()||index!=_active||index!=_settled.Count)throw new InvalidOperationException("Mixed item ownership lost.");
        return _items[index].CaptureCompletion();
    }
    public void SettleItem(int index) {
        var result=CaptureItemCompletion(index);
        if(!result.OwnershipValid||!result.EffectStillValid||result.Collection?.State!=GenericEventV7ItemTaskState.Succeeded)throw new InvalidOperationException("Mixed item result changed.");
        var e=_root.Entries![index];_itemTasks.Add(index,e.CollectionTask!);
        if(e.Kind==ItemV1ItemKind.Potion) {
            if(!GenericEventV7ItemAdapter.Slots(_root.Binding.Player,out _,out var slots))throw new InvalidOperationException("Mixed inventory unavailable.");
            int slot=slots.FindIndex(s=>ReferenceEquals(s.ModelIdentity,e.Model));if(slot<0)throw new InvalidOperationException("Mixed potion absent.");_potionSlots.Add(e.Model!,slot);
        }
        _settled.Add(true);
    }
    private sealed class ItemEntry : IItemV1NativeAdapter {
        private readonly GenericEventV7CardRewardSetAdapter _owner;private readonly int _index;private readonly GenericEventV7ItemAdapter _inner;
        internal ItemEntry(GenericEventV7CardRewardSetAdapter owner,int index,GenericEventV7ItemAdapter inner){_owner=owner;_index=index;_inner=inner;}
        private void Check(){if(_owner._active!=_index||!_owner.Owned())throw new InvalidOperationException("Inactive mixed item.");}
        public ItemV1SurfaceCapture CaptureSurface(){Check();return _inner.CaptureSurface();}
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe){Check();return _inner.CapturePending(probe);}
    }
    public void Dispose() {
        if(_disposed)return;
        if(Environment.CurrentManagedThreadId!=_thread)throw new InvalidOperationException("Card reward set owner required.");
        foreach(var entry in _root.Entries!)entry.CardReward?.Dispose();foreach(var item in _items.Values)item.Dispose();_disposed=true;
    }
    private sealed class Entry : IGenericEventV7RewardAdapter {
        private readonly GenericEventV7CardRewardSetAdapter _owner;private readonly int _index;private bool _disposed;
        internal Entry(GenericEventV7CardRewardSetAdapter owner,int index){_owner=owner;_index=index;}
        private void Check(){if(_disposed||_owner._active!=_index||!_owner.Owned())throw new InvalidOperationException("Inactive card reward entry.");}
        public GenericEventV7RewardCapture Capture(){Check();return _owner.Active.Capture();}
        public void Dispatch(string action){Check();_owner.Active.Dispatch(action);}
        public void Dispose()=>_disposed=true;
    }
}
