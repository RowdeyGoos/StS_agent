using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Sts2AgentBridge.Successors.ItemV1;
namespace Sts2AgentBridge.Successors.GenericEventV7;

public sealed record GenericEventV7RewardSettlement(int OfferIndex,int? SelectedSlot,string? Key,int? UpgradeLevel,string Result,string Kind="card");
public interface IGenericEventV7RewardSetAdapter : IDisposable {
    int OfferCount {get;}
    string CaptureState();
    IGenericEventV7RewardAdapter CreateEntry(int index);
    void SettleEntry(int index,bool selected);
    void Dismiss();
}
public interface IGenericEventV7MixedRewardSetAdapter : IGenericEventV7RewardSetAdapter {
    IReadOnlyList<string>? OfferKinds {get;}
    IItemV1NativeAdapter CreateItemEntry(int index);
    GenericEventV7ItemCompletion CaptureItemCompletion(int index);
    void SettleItem(int index);
}
// Entry completion verifies local choice/skip. Only this enclosing session may
// claim the generated set complete after the actual Offer and Chosen tasks finish.
public sealed class GenericEventV7CardRewardSetSession : IGenericEventV7RewardChildSession {
    private readonly string _nonce;
    private readonly IGenericEventV7RewardSetAdapter _adapter;
    private readonly int _count,_thread=Environment.CurrentManagedThreadId;
    private readonly List<GenericEventV7RewardSettlement> _settled=new();
    private readonly List<GenericEventV7PriorResult> _history=new();
    private readonly List<(string InnerDecision,string InnerAction,string Decision,string Action)> _receipts=new();
    private GenericEventV7CardRewardSession? _entry;
    private readonly IGenericEventV7MixedRewardSetAdapter? _mixed;
    private readonly string[]? _kinds;
    private ItemV1Session? _item;
    private ItemV1Observation? _itemPublished;
    private ItemV1DispatchReceipt? _itemReceipt;
    private GenericEventV7ItemTaskWitness? _itemTask;
    private GenericEventV7RewardRead? _inner,_published;
    private GenericEventV7RewardCard[]? _cards;
    private int _entryHistory,_reads;
    private bool _inside,_failed,_disposed,_interfered,_dismissed,_complete;
    private string _dismissDecision="";
    public GenericEventV7CardRewardSetSession(string nonce,IGenericEventV7RewardSetAdapter adapter) {
        _nonce=nonce;_adapter=adapter;_count=adapter.OfferCount;
        if(_count is <2 or >8)throw new ArgumentOutOfRangeException(nameof(adapter));
        if(adapter is IGenericEventV7MixedRewardSetAdapter mixed && mixed.OfferKinds is {} kinds) {
            _mixed=mixed;_kinds=kinds.ToArray();
            if(_kinds.Length!=_count||!_kinds.Contains("card")||!_kinds.Any(k=>k is "potion" or "relic")||_kinds.Any(k=>k is not ("card" or "potion" or "relic")))throw new ArgumentException("Mixed reward kinds required.");
        }
    }
    public string ContractVersion=>_mixed is null?"card_reward_set_v1":"mixed_reward_set_v1";
    private bool Enter(){if(_inside||_failed||_disposed||Environment.CurrentManagedThreadId!=_thread){if(_inside)_interfered=true;_failed=true;return false;}_inside=true;return true;}
    private string Action(string action)=>action=="open"?"open:"+_settled.Count:action=="skip"?"skip:"+_settled.Count:"choose:"+_settled.Count+":"+action[7..];
    private string Decision(string inner)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(_nonce+":"+_settled.Count+":"+inner))).ToLowerInvariant();
    private GenericEventV7RewardRead Value(string status,string phase,string decision="",IReadOnlyList<GenericEventV7RewardCard>? cards=null,bool skip=false,IReadOnlyList<string>? actions=null,ItemV1Observation? item=null)=>
        new(_nonce,status,phase,decision,cards??Array.Empty<GenericEventV7RewardCard>(),skip,actions??Array.Empty<string>(),
            Array.AsReadOnly(_history.ToArray()),null,_count,_settled.Count,Array.AsReadOnly(_settled.ToArray()),_kinds is null?null:Array.AsReadOnly(_kinds),item);
    private GenericEventV7RewardRead Stop(){_failed=true;return Value("unsupported","unsupported");}
    public GenericEventV7RewardRead Read() {
        if(!Enter())return Value("unsupported","unsupported");
        try {
            _published=null;
            if(_complete)return Value("resolved","complete");
            if(++_reads>256)return Stop();
            string state=_adapter.CaptureState();if(_failed||state=="unsupported")return Stop();
            if(_settled.Count==_count) {
                if(state=="complete") {
                    if(_settled.Any(x=>x.Result=="skipped")!=_dismissed)return Stop();
                    if(_dismissed)_history.Add(new(_dismissDecision,"dismiss","dismissed"));
                    _complete=true;return Value("resolved","complete");
                }
                if(state=="dismiss"&&!_dismissed){_published=Value("ready","dismiss",Decision("dismiss"),actions:new[]{"dismiss"});return _published;}
                return state=="waiting"?Value("waiting","waiting"):Stop();
            }
            if(state!="entry")return Stop();
            if(_kinds is not null && _kinds[_settled.Count]!="card")return ReadItem();
            _entry??=new GenericEventV7CardRewardSession(_nonce,new GuardedEntry(this,_adapter.CreateEntry(_settled.Count)),entry:true);
            if(_failed)return Stop();
            var read=_entry.Read();if(_failed)return Stop();
            if(read.PriorResults.Count<_entryHistory||read.PriorResults.Count>_receipts.Count)return Stop();
            for(int i=0;i<read.PriorResults.Count;i++) {
                var row=read.PriorResults[i];var receipt=_receipts[i];
                if(row.DecisionId!=receipt.InnerDecision||row.ActionId!=receipt.InnerAction)return Stop();
                if(i>=_entryHistory)_history.Add(new(receipt.Decision,receipt.Action,row.Result));
            }
            _entryHistory=read.PriorResults.Count;
            if(read.Status=="unsupported")return Stop();
            if(read.Status=="resolved") {
                if(_receipts.Count!=2||_entryHistory!=2||_cards is null)return Stop();
                int? slot=read.SelectedSlot;
                if(slot is {} n&&(n<0||n>=_cards.Length))return Stop();
                _adapter.SettleEntry(_settled.Count,slot is not null);if(_failed)return Stop();
                _settled.Add(new(_settled.Count,slot,slot is {} at?_cards[at].Key:null,slot is {} ix?_cards[ix].UpgradeLevel:null,slot is null?"skipped":"collected"));
                _entry.Dispose();if(_failed)return Stop();_entry=null;_inner=null;_cards=null;_receipts.Clear();_entryHistory=0;
                return Value("waiting","waiting");
            }
            if(read.Status=="waiting")return Value("waiting","waiting");
            if(read.Status!="ready"||read.Phase is not ("open" or "choose"))return Stop();
            if(read.Phase=="choose")_cards??=read.Cards.ToArray();
            _inner=read;_published=Value("ready",read.Phase,Decision(read.DecisionId),read.Cards,read.CanSkip,read.LegalActions.Select(Action).ToArray());return _published;
        }catch{return Stop();}finally{_inside=false;}
    }
    public GenericEventV7RewardReceipt Apply(string? decision,string? action) {
        GenericEventV7RewardReceipt Result(string outcome)=>new(_nonce,decision??"",action??"",outcome);
        if(!Enter())return Result("unsupported");
        try {
            if(_published is null||decision!=_published.DecisionId||!_published.LegalActions.Contains(action??""))return Result("rejected");
            _published=null;
            if(action=="dismiss") {
                _dismissed=true;_dismissDecision=decision!;_adapter.Dismiss();return Result(_failed?"uncertain":"accepted");
            }
            if(_kinds is not null && _settled.Count<_count && _kinds[_settled.Count]!="card") {
                if(_item is null||_itemPublished is null||_itemReceipt is not null)return Result("unsupported");
                var itemReceipt=_item.Apply(decision,action);
                if(_failed)return Result("uncertain");
                if(itemReceipt is ItemV1DispatchReceipt accepted){_itemReceipt=accepted;return Result("accepted");}
                _failed=true;return Result(itemReceipt is ItemV1ApplyFailure failure?failure.Outcome:"unsupported");
            }
            if(_entry is null||_inner is null||_receipts.Count>=2)return Result("unsupported");
            string local=_inner.LegalActions.Single(a=>Action(a)==action);
            var receipt=_entry.Apply(_inner.DecisionId,local);
            if(_failed)return Result("uncertain");
            if(receipt.Outcome=="accepted")_receipts.Add((receipt.DecisionId,local,decision!,action!));else _failed=true;
            return Result(receipt.Outcome);
        }catch{_failed=true;return Result("uncertain");}finally{_inside=false;}
    }
    private GenericEventV7RewardRead ReadItem() {
        int index=_settled.Count;
        _item??=new ItemV1Session(_nonce,new GuardedItem(this,_mixed!.CreateItemEntry(index)));
        if(_failed)return Stop();
        var read=_item.Read();if(_failed)return Stop();
        if(_itemReceipt is null) {
            if(read is not ItemV1Observation p||p.Status is not ("ready" or "waiting"))return Stop();
            if(p.Status=="waiting")return Value("waiting","waiting");
            if(p.Offers.Count!=1||p.Offers[0].Index!=index||p.Offers[0].Kind!=_kinds![index])return Stop();
            _itemPublished=p;_published=Value("ready","collect",p.DecisionId,actions:p.LegalActions,item:p);return _published;
        }
        var completion=_mixed!.CaptureItemCompletion(index);
        if(_failed||!completion.OwnershipValid||completion.Collection is not {} task||task.Identity is null||
            task.State is not (GenericEventV7ItemTaskState.Pending or GenericEventV7ItemTaskState.Succeeded)||
            _itemTask is not null&&(!ReferenceEquals(task.Identity,_itemTask.Identity)||_itemTask.State==GenericEventV7ItemTaskState.Succeeded&&task.State!=_itemTask.State))return Stop();
        _itemTask=task;
        if(read is ItemV1ResolvedResult done) {
            var offer=_itemPublished!.Offers[0];
            if(!completion.EffectStillValid||done.SessionNonce!=_nonce||done.DecisionId!=_itemReceipt.DecisionId||done.ActionId!=_itemReceipt.ActionId||
                done.OfferIndex!=index||done.Kind!=offer.Kind||done.Key!=offer.Key||done.Result!="collected")return Stop();
            if(task.State==GenericEventV7ItemTaskState.Succeeded) {
                _mixed.SettleItem(index);if(_failed)return Stop();
                _history.Add(new(done.DecisionId,done.ActionId,"collected"));
                _settled.Add(new(index,null,done.Key,null,"collected",done.Kind));
                _item=null;_itemPublished=null;_itemReceipt=null;_itemTask=null;
            }
        }else if(read is not ItemV1Observation {Status:"waiting"})return Stop();
        return Value("waiting","waiting");
    }
    private sealed class GuardedItem : IItemV1NativeAdapter {
        private readonly GenericEventV7CardRewardSetSession _owner;private readonly IItemV1NativeAdapter _inner;
        internal GuardedItem(GenericEventV7CardRewardSetSession owner,IItemV1NativeAdapter inner){_owner=owner;_inner=inner;}
        private void Check(){if(!_owner._inside||_owner._failed||_owner._disposed||Environment.CurrentManagedThreadId!=_owner._thread)throw new InvalidOperationException("Inactive mixed item entry.");}
        public ItemV1SurfaceCapture CaptureSurface(){
            Check();var value=_inner.CaptureSurface();Check();
            if(value.Status!=ItemV1SurfaceStatus.Available)return value;
            return ItemV1SurfaceCapture.Available(value.RunIdentity!,value.PlayerIdentity!,value.ScreenIdentity!,value.PotionCapacity,
                value.Offers.Select(o=>new ItemV1NativeOffer(o.Index,o.Kind,o.StableKey,o.Populated,o.AlreadySelected,o.ButtonVisible,o.ButtonEnabled,o.ButtonIdentity,o.RewardIdentity,o.OfferedModelIdentity,()=>{Check();o.Dispatch();Check();})).ToArray(),value.PotionSlots);
        }
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe){Check();var value=_inner.CapturePending(probe);Check();return value;}
    }
    public void Dispose() {
        if(_disposed)return;
        _failed=true;if(_inside||Environment.CurrentManagedThreadId!=_thread){_interfered=true;throw new InvalidOperationException("Idle reward-set owner required.");}
        _inside=true;_interfered=false;
        try{_entry?.Dispose();_adapter.Dispose();if(_interfered)throw new InvalidOperationException("Reentrant reward-set cleanup.");_disposed=true;}finally{_inside=false;}
    }
    private sealed class GuardedEntry : IGenericEventV7RewardAdapter {
        private readonly GenericEventV7CardRewardSetSession _owner;private readonly IGenericEventV7RewardAdapter _inner;
        private bool _disposed;
        internal GuardedEntry(GenericEventV7CardRewardSetSession owner,IGenericEventV7RewardAdapter inner){_owner=owner;_inner=inner;}
        private void Check(){if(_disposed||!_owner._inside||_owner._failed||_owner._disposed||Environment.CurrentManagedThreadId!=_owner._thread)throw new InvalidOperationException("Inactive reward set entry.");}
        public GenericEventV7RewardCapture Capture(){Check();var value=_inner.Capture();Check();return value;}
        public void Dispatch(string action){Check();_inner.Dispatch(action);Check();}
        public void Dispose(){if(_disposed)return;_inner.Dispose();_disposed=true;}
    }
}
