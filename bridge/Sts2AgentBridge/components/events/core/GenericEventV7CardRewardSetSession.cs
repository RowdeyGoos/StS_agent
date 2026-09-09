using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
namespace Sts2AgentBridge.Successors.GenericEventV7;

public sealed record GenericEventV7RewardSettlement(int OfferIndex,int? SelectedSlot,string? Key,int? UpgradeLevel,string Result);
public interface IGenericEventV7RewardSetAdapter : IDisposable {
    int OfferCount {get;}
    string CaptureState();
    IGenericEventV7RewardAdapter CreateEntry(int index);
    void SettleEntry(int index,bool selected);
    void Dismiss();
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
    private GenericEventV7RewardRead? _inner,_published;
    private GenericEventV7RewardCard[]? _cards;
    private int _entryHistory,_reads;
    private bool _inside,_failed,_disposed,_interfered,_dismissed,_complete;
    private string _dismissDecision="";
    public GenericEventV7CardRewardSetSession(string nonce,IGenericEventV7RewardSetAdapter adapter) {
        _nonce=nonce;_adapter=adapter;_count=adapter.OfferCount;
        if(_count is <2 or >8)throw new ArgumentOutOfRangeException(nameof(adapter));
    }
    public string ContractVersion=>"card_reward_set_v1";
    private bool Enter(){if(_inside||_failed||_disposed||Environment.CurrentManagedThreadId!=_thread){if(_inside)_interfered=true;_failed=true;return false;}_inside=true;return true;}
    private string Action(string action)=>action=="open"?"open:"+_settled.Count:action=="skip"?"skip:"+_settled.Count:"choose:"+_settled.Count+":"+action[7..];
    private string Decision(string inner)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(_nonce+":"+_settled.Count+":"+inner))).ToLowerInvariant();
    private GenericEventV7RewardRead Value(string status,string phase,string decision="",IReadOnlyList<GenericEventV7RewardCard>? cards=null,bool skip=false,IReadOnlyList<string>? actions=null)=>
        new(_nonce,status,phase,decision,cards??Array.Empty<GenericEventV7RewardCard>(),skip,actions??Array.Empty<string>(),
            Array.AsReadOnly(_history.ToArray()),null,_count,_settled.Count,Array.AsReadOnly(_settled.ToArray()));
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
            if(_entry is null||_inner is null||_receipts.Count>=2)return Result("unsupported");
            string local=_inner.LegalActions.Single(a=>Action(a)==action);
            var receipt=_entry.Apply(_inner.DecisionId,local);
            if(_failed)return Result("uncertain");
            if(receipt.Outcome=="accepted")_receipts.Add((receipt.DecisionId,local,decision!,action!));else _failed=true;
            return Result(receipt.Outcome);
        }catch{_failed=true;return Result("uncertain");}finally{_inside=false;}
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
