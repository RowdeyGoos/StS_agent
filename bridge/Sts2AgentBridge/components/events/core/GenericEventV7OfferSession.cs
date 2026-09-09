using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
namespace Sts2AgentBridge.Successors.GenericEventV7;

public sealed record GenericEventV7Offer(int Index,IReadOnlyList<GenericEventV7RewardCard> Cards);
public sealed record GenericEventV7OfferCapture(string Phase,IReadOnlyList<GenericEventV7Offer> Offers,IReadOnlyList<GenericEventV7RewardCard>? AdditionalCards=null);
public interface IGenericEventV7OfferAdapter:IDisposable {
    GenericEventV7OfferCapture Capture();
    void Dispatch(string action);
}
// A direct card choice or a bundle choice followed by its native confirmation.
public sealed class GenericEventV7OfferSession:IGenericEventV7RewardChildSession {
    private readonly IGenericEventV7OfferAdapter _adapter;
    private readonly string _nonce;private readonly bool _bundle,_canSkip;private readonly int _count;
    private readonly int _thread=Environment.CurrentManagedThreadId;
    private readonly List<GenericEventV7PriorResult> _history=new();
    private GenericEventV7Offer[]? _offers;
    private GenericEventV7RewardCard[] _additional=Array.Empty<GenericEventV7RewardCard>();
    private string _phase="choose",_decision="",_pending="",_pendingDecision="";
    private int? _selected;private int _reads,_attempts;
    private bool _inside,_failed,_disposed,_interfered;
    public GenericEventV7OfferSession(string nonce,bool bundle,int count,IGenericEventV7OfferAdapter adapter,bool canSkip=false) {
        if(count is <1 or >5 || canSkip&&(bundle||count>3))throw new ArgumentException("Offer count unavailable.");
        _nonce=nonce;_bundle=bundle;_count=count;_adapter=adapter;_canSkip=canSkip;
    }
    public string ContractVersion=>_bundle?"bundle_offer_v1":_canSkip?"card_offer_v2":"card_offer_v1";
    private bool Enter(){if(_inside)_interfered=true;if(_inside||_disposed||Environment.CurrentManagedThreadId!=_thread){_failed=true;return false;}_inside=true;return true;}
    private string[] Actions()=>_phase=="choose"?Enumerable.Range(0,_count).Select(i=>"choose:"+i).Concat(_canSkip?new[]{"skip"}:Array.Empty<string>()).ToArray():new[]{"confirm"};
    private GenericEventV7RewardRead Value(string status)=>new(_nonce,status,status=="ready"?_phase:status=="resolved"?"complete":status,
        status=="ready"?_decision:"",Array.Empty<GenericEventV7RewardCard>(),false,status=="ready"?Actions():Array.Empty<string>(),
        _history.ToArray(),status is "ready" or "resolved"?_selected:null,Offers:status is "ready" or "resolved"?_offers:Array.Empty<GenericEventV7Offer>(),AdditionalCards:status=="resolved"?_additional:Array.Empty<GenericEventV7RewardCard>());
    public GenericEventV7RewardRead Read(){
        if(!Enter())return Value("unsupported");
        try {
            if(_failed)return Value("unsupported");if(_phase=="complete")return Value("resolved");
            if(++_reads>256)throw new InvalidOperationException();
            var capture=_adapter.Capture();if(_failed||capture.Phase=="unsupported")throw new InvalidOperationException();
            if((capture.AdditionalCards?.Count??0)>0&&capture.Phase!="complete")throw new InvalidOperationException("Early grant metadata.");
            if(capture.Phase=="waiting")return Value("waiting");
            if(_pending!="") {
                string expected=_pending=="confirm"||!_bundle?"complete":"preview";
                if(capture.Phase!=expected)throw new InvalidOperationException("Choice did not advance.");
                _history.Add(new(_pendingDecision,_pending,_pending=="skip"?"skipped":_pending=="confirm"||!_bundle?"collected":"previewed"));_pending="";_phase=expected;
            }
            if(capture.Phase!=_phase)throw new InvalidOperationException("Unowned offer phase.");
            if(_phase=="complete") {
                var additional=capture.AdditionalCards??Array.Empty<GenericEventV7RewardCard>();
                if(additional.Count>(_canSkip?1:0)||additional.Where((c,i)=>c.Slot!=i||!Key(c.Key)||c.UpgradeLevel<0).Any())throw new InvalidOperationException("Invalid grant metadata.");
                _additional=additional.ToArray();return Value("resolved");
            }
            if(capture.Offers.Count!=_count||capture.Offers.Where((o,i)=>o.Index!=i||o.Cards.Count<1||o.Cards.Count>(_bundle?8:1)||o.Cards.Where((c,j)=>c.Slot!=j||c.UpgradeLevel<0||!Key(c.Key)).Any()).Any())throw new InvalidOperationException("Invalid offer domain.");
            var copy=capture.Offers.Select(o=>new GenericEventV7Offer(o.Index,o.Cards.ToArray())).ToArray();
            if(_offers is not null&&!Same(_offers,copy))throw new InvalidOperationException("Offer changed.");_offers=copy;
            _decision=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(ContractVersion+":"+_nonce+":"+_attempts+":"+_phase+":"+string.Join("|",copy.Select(o=>o.Index+":"+string.Join(",",o.Cards.Select(c=>c.Key+":"+c.UpgradeLevel))))))).ToLowerInvariant();
            return Value("ready");
        }catch{_failed=true;return Value("unsupported");}finally{_inside=false;}
    }
    internal static bool Same(IReadOnlyList<GenericEventV7Offer> a,IReadOnlyList<GenericEventV7Offer> b)=>a.Count==b.Count&&!a.Where((o,i)=>o.Index!=b[i].Index||!o.Cards.SequenceEqual(b[i].Cards)).Any();
    private static bool Key(string s)=>s.Length is >0 and <=128&&s.All(c=>char.IsAsciiLetterOrDigit(c)||c=='_');
    public GenericEventV7RewardReceipt Apply(string? decision,string? action){
        GenericEventV7RewardReceipt Result(string outcome)=>new(_nonce,decision??"",action??"",outcome);
        var read=Read();if(read.Status!="ready"||decision!=read.DecisionId||!read.LegalActions.Contains(action??""))return Result("rejected");
        if(!Enter())return Result("unsupported");
        try {
            if(_failed||_pending!=""||_attempts>=(_bundle?2:1))return Result("rejected");
            _attempts++;_pending=action!;_pendingDecision=decision!;
            if(action!.StartsWith("choose:",StringComparison.Ordinal))_selected=action[7]-'0';
            _adapter.Dispatch(action);return Result(_failed?"uncertain":"accepted");
        }catch{_failed=true;return Result("uncertain");}finally{_inside=false;}
    }
    public void Dispose(){if(_disposed)return;if(!Enter())throw new InvalidOperationException("Offer cleanup ownership.");try{_adapter.Dispose();if(_interfered)throw new InvalidOperationException();_disposed=true;}finally{_inside=false;}}
}
