using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.GenericEventV7;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// A single generated set owns every menu. Completed entries remain witnesses;
// the active entry's full deck baseline includes all earlier verified insertions.
internal sealed class GenericEventV7CardRewardSetAdapter : IGenericEventV7RewardSetAdapter {
    private readonly GenericEventV7ItemState _root;
    private readonly Task _offer,_chosen;
    private readonly int _thread=Environment.CurrentManagedThreadId;
    private readonly List<bool> _settled=new();
    private int _active=-1;
    private bool _dismissed,_disposed;
    internal GenericEventV7CardRewardSetAdapter(GenericEventV7ItemState root) {
        _root=root;
        if(!root.Ready||!root.Domain()||root.OfferCount is <2 or >8||root.Entries!.Any(e=>e.CardReward is null))throw new InvalidOperationException("Card reward set unavailable.");
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
            if(i<_settled.Count&&!e.CardReward!.RetainResult(_settled[i]))return false;
        }
        return _active<0?_root.Entries![0].CardReward!.InitialDeck():Active.RetainDeck();
    }
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
        return Active.DismissReady()?"dismiss":"waiting";
    }
    public IGenericEventV7RewardAdapter CreateEntry(int index) {
        if(!Owned()||index!=_settled.Count||index!=_active+1||index>=OfferCount)throw new InvalidOperationException("Unsettled card reward entry.");
        _root.Entries![index].CardReward!.Start(batch:true,retainBaseline:index==0);_active=index;return new Entry(this,index);
    }
    public void SettleEntry(int index,bool selected) {
        if(!Owned()||index!=_active||index!=_settled.Count||Active.Capture().Phase!="complete"||!Active.RetainResult(selected))throw new InvalidOperationException("Card reward result changed.");
        _settled.Add(selected);
    }
    public void Dismiss() {
        if(_dismissed||CaptureState()!="dismiss")throw new InvalidOperationException("Card reward set dismissal unavailable.");
        _dismissed=true;Active.DismissSet();
    }
    public void Dispose() {
        if(_disposed)return;
        if(Environment.CurrentManagedThreadId!=_thread)throw new InvalidOperationException("Card reward set owner required.");
        foreach(var entry in _root.Entries!)entry.CardReward!.Dispose();_disposed=true;
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
