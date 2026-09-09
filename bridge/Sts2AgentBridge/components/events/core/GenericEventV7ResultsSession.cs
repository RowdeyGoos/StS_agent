using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
namespace Sts2AgentBridge.Successors.GenericEventV7;

public sealed record GenericEventV7ResultsCapture(string Status,IReadOnlyList<GenericEventV7RewardCard> Cards);
public interface IGenericEventV7ResultsAdapter:IDisposable {
    GenericEventV7ResultsCapture Capture();
    void Confirm();
}
// Acknowledges already displayed results. It does not certify the automatic transformation.
public sealed class GenericEventV7ResultsSession:IGenericEventV7RewardChildSession {
    private readonly IGenericEventV7ResultsAdapter _adapter;
    private readonly string _nonce;private readonly int _count,_thread=Environment.CurrentManagedThreadId;
    private GenericEventV7RewardCard[]? _cards;
    private string _decision="",_acceptedDecision="";
    private bool _inside,_interfered,_failed,_disposed,_attempted,_complete;private int _reads;
    public GenericEventV7ResultsSession(string nonce,int count,IGenericEventV7ResultsAdapter adapter){if(count is <1 or >64)throw new ArgumentException("Results count.");_nonce=nonce;_count=count;_adapter=adapter;}
    public string ContractVersion=>"card_results_v1";
    private bool Enter(){if(_inside)_interfered=true;if(_inside||_disposed||Environment.CurrentManagedThreadId!=_thread){_failed=true;return false;}_inside=true;return true;}
    private GenericEventV7RewardRead Value(string status)=>new(_nonce,status,status=="ready"?"acknowledge":status=="resolved"?"complete":status,status=="ready"?_decision:"",
        status is "ready" or "resolved"?_cards??Array.Empty<GenericEventV7RewardCard>():Array.Empty<GenericEventV7RewardCard>(),false,status=="ready"?new[]{"confirm"}:Array.Empty<string>(),
        _complete?new[]{new GenericEventV7PriorResult(_acceptedDecision,"confirm","acknowledged")}:Array.Empty<GenericEventV7PriorResult>(),null);
    public GenericEventV7RewardRead Read(){
        if(!Enter())return Value("unsupported");
        try {
            if(_failed)return Value("unsupported");if(_complete)return Value("resolved");
            if(++_reads>256)throw new InvalidOperationException();var capture=_adapter.Capture();if(_failed)throw new InvalidOperationException();
            if(capture.Status=="waiting")return Value("waiting");
            if(capture.Status=="resolved") {if(!_attempted||_cards is null)throw new InvalidOperationException();_complete=true;return Value("resolved");}
            if(capture.Status!="ready"||_attempted||capture.Cards.Count!=_count||capture.Cards.Where((c,i)=>c.Slot!=i||c.UpgradeLevel<0||c.Key.Length is <1 or >128||!c.Key.All(x=>char.IsAsciiLetterOrDigit(x)||x=='_')).Any())throw new InvalidOperationException();
            if(_cards is not null&&!_cards.SequenceEqual(capture.Cards))throw new InvalidOperationException();_cards=capture.Cards.ToArray();
            _decision=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(ContractVersion+":"+_nonce+":"+string.Join("|",_cards.Select(c=>c.Slot+":"+c.Key+":"+c.UpgradeLevel))))).ToLowerInvariant();return Value("ready");
        }catch{_failed=true;return Value("unsupported");}finally{_inside=false;}
    }
    public GenericEventV7RewardReceipt Apply(string? decision,string? action){
        GenericEventV7RewardReceipt Receipt(string outcome)=>new(_nonce,decision??"",action??"",outcome);
        var read=Read();if(read.Status!="ready"||decision!=read.DecisionId||action!="confirm")return Receipt("rejected");
        if(!Enter())return Receipt("unsupported");
        try{if(_attempted||_failed)return Receipt("rejected");_attempted=true;_acceptedDecision=decision!;_adapter.Confirm();return Receipt(_failed?"uncertain":"accepted");}
        catch{_failed=true;return Receipt("uncertain");}finally{_inside=false;}
    }
    public void Dispose(){if(_disposed)return;if(!Enter())throw new InvalidOperationException("Results cleanup ownership.");try{_adapter.Dispose();if(_interfered)throw new InvalidOperationException("Results cleanup interference.");_disposed=true;}finally{_inside=false;}}
}
