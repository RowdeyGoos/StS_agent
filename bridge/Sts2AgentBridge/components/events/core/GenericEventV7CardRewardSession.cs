using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
namespace Sts2AgentBridge.Successors.GenericEventV7;

public sealed record GenericEventV7RewardCard(int Slot,string Key,int UpgradeLevel);
public sealed record GenericEventV7RewardCapture(string Phase,IReadOnlyList<GenericEventV7RewardCard> Cards,bool CanSkip);
public interface IGenericEventV7RewardAdapter : IDisposable {
    GenericEventV7RewardCapture Capture();
    void Dispatch(string action);
}
public interface IGenericEventV7RewardChildSession : IGenericEventV7ChildSession {
    GenericEventV7RewardRead Read();
    GenericEventV7RewardReceipt Apply(string? decision,string? action);
}
public sealed record GenericEventV7ItemPolicyOffer(int Index,string Kind,string Key,int CapacityGain,bool Settled);
public sealed record GenericEventV7ItemPolicyView(IReadOnlyList<GenericEventV7ItemPolicyOffer> Offers,IReadOnlyList<string?> PotionSlots,bool CanSkip);
public sealed record GenericEventV7RewardRead(string SessionNonce,string Status,string Phase,string DecisionId,
    IReadOnlyList<GenericEventV7RewardCard> Cards,bool CanSkip,IReadOnlyList<string> LegalActions,
    IReadOnlyList<GenericEventV7PriorResult> PriorResults,int? SelectedSlot,
    int OfferCount=1,int OfferIndex=0,IReadOnlyList<GenericEventV7RewardSettlement>? Settled=null,
    IReadOnlyList<string>? OfferKinds=null,Sts2AgentBridge.Successors.ItemV1.ItemV1Observation? Item=null,IReadOnlyList<GenericEventV7Offer>? Offers=null,IReadOnlyList<GenericEventV7RewardCard>? AdditionalCards=null,GenericEventV7SphereView? Sphere=null,GenericEventV7ItemPolicyView? ItemPolicy=null);
public sealed record GenericEventV7SphereView(int Divinations,string Tool,IReadOnlyList<bool> Hidden,IReadOnlyList<GenericEventV7SphereReward> Rewards);
public sealed record GenericEventV7SphereReward(int Slot,string Kind,string Key,int Amount,IReadOnlyList<GenericEventV7RewardCard> Cards);
public sealed record GenericEventV7RewardReceipt(string SessionNonce,string DecisionId,string ActionId,string Outcome);
public sealed record GenericEventV7RewardChildRead(GenericEventV7RewardRead Value,string Version="card_reward_v1"):GenericEventV7ChildRead(Version);
public sealed record GenericEventV7RewardChildApply(GenericEventV7RewardReceipt Value,string Version="card_reward_v1"):GenericEventV7ChildApply(Version);

// One generated CardReward, its menu, and (after native Skip) explicit dismissal.
public sealed class GenericEventV7CardRewardSession : IGenericEventV7RewardChildSession {
    private readonly IGenericEventV7RewardAdapter _adapter;
    private readonly string _nonce;
    private readonly bool _entry;
    private readonly int _thread=Environment.CurrentManagedThreadId;
    private readonly List<GenericEventV7PriorResult> _history=new();
    private GenericEventV7RewardCapture? _published;
    private GenericEventV7RewardCard[]? _cards;
    private string _decision="",_pendingDecision="",_pendingAction="",_phase="open";
    private int? _selected;
    private bool _inside,_failed,_disposed,_interfered;
    private int _reads,_attempts;
    public GenericEventV7CardRewardSession(string nonce,IGenericEventV7RewardAdapter adapter,bool entry=false){_nonce=nonce;_adapter=adapter;_entry=entry;}
    public string ContractVersion=>_entry?"card_reward_entry_v1":"card_reward_v1";
    private bool Enter(){if(_inside||_failed||_disposed||Environment.CurrentManagedThreadId!=_thread){if(_inside)_interfered=true;_failed=true;return false;}_inside=true;return true;}
    private GenericEventV7RewardRead Value(string status,string phase)=>new(_nonce,status,phase,status=="ready"?_decision:"",
        status=="ready"&&phase=="choose"?Array.AsReadOnly(_cards!):Array.Empty<GenericEventV7RewardCard>(),
        status=="ready"&&phase=="choose"&&_published!.CanSkip,
        status=="ready"?Actions(_published!):Array.Empty<string>(),Array.AsReadOnly(_history.ToArray()),status=="resolved"?_selected:null);
    private GenericEventV7RewardRead Stop(){_failed=true;return Value("unsupported","unsupported");}
    private static string[] Actions(GenericEventV7RewardCapture c)=>c.Phase=="open"?new[]{"open"}:c.Phase=="dismiss"?new[]{"dismiss"}:
        c.Cards.Select(x=>"choose:"+x.Slot).Concat(c.CanSkip?new[]{"skip"}:Array.Empty<string>()).ToArray();
    public GenericEventV7RewardRead Read(){
        if(!Enter())return Value("unsupported","unsupported");
        try {
            if(_phase=="complete")return Value("resolved","complete");
            if(++_reads>256)return Stop();
            var capture=_adapter.Capture();if(_failed||capture.Phase=="unsupported")return Stop();
            if(capture.Phase=="waiting")return Value("waiting","waiting");
            if(_pendingAction!="") {
                string expected=_pendingAction=="open"?"choose":_pendingAction=="skip"&&!_entry?"dismiss":"complete";
                if(capture.Phase!=expected)return Stop();
                _history.Add(new(_pendingDecision,_pendingAction,_pendingAction=="open"?"opened":_pendingAction=="skip"?"skipped":_pendingAction=="dismiss"?"dismissed":"collected"));
                _phase=expected;_pendingAction="";
            }
            if(capture.Phase!=_phase)return Stop();
            if(_phase=="complete")return Value("resolved","complete");
            if(_phase=="choose") {
                if(capture.Cards.Count is <1 or >5||capture.Cards.Where((x,i)=>x.Slot!=i||x.UpgradeLevel<0||!Key(x.Key)).Any())return Stop();
                _cards??=capture.Cards.ToArray();if(!_cards.SequenceEqual(capture.Cards))return Stop();
            } else if(capture.Cards.Count!=0||capture.CanSkip)return Stop();
            _published=capture;
            _decision=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(_nonce+":"+_attempts+":"+_phase+":"+capture.CanSkip+":"+string.Join("|",capture.Cards.Select(c=>c.Slot+":"+c.Key+":"+c.UpgradeLevel))))).ToLowerInvariant();
            return Value("ready",_phase);
        }catch{return Stop();}finally{_inside=false;}
    }
    private static bool Key(string s)=>s.Length is >0 and <=128&&s.All(c=>c is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9' or '_');
    public GenericEventV7RewardReceipt Apply(string? decision,string? action){
        GenericEventV7RewardReceipt Result(string outcome)=>new(_nonce,decision??"",action??"",outcome);
        if(!Enter())return Result("unsupported");
        try {
            if(_pendingAction!=""||_published is null||decision!=_decision||!Actions(_published).Contains(action??""))return Result("rejected");
            if(_attempts>=3)return Result("unsupported");
            var current=_adapter.Capture();
            if(_failed||current.Phase!=_published.Phase||current.CanSkip!=_published.CanSkip||!current.Cards.SequenceEqual(_published.Cards)){_failed=true;return Result("unsupported");}
            _attempts++;_pendingAction=action!;_pendingDecision=decision!;
            if(action!.StartsWith("choose:",StringComparison.Ordinal))_selected=int.Parse(action.AsSpan(7));
            _published=null;_decision="";
            _adapter.Dispatch(action);if(_failed)return Result("uncertain");return Result("accepted");
        }catch{_failed=true;return Result("uncertain");}finally{_inside=false;}
    }
    public void Dispose(){
        if(_disposed)return;
        if(_inside||Environment.CurrentManagedThreadId!=_thread){_interfered=true;_failed=true;throw new InvalidOperationException("Idle reward owner required.");}
        _failed=true;_inside=true;_interfered=false;
        try{_adapter.Dispose();if(_interfered)throw new InvalidOperationException("Reentrant reward cleanup.");_disposed=true;}finally{_inside=false;}
    }
}

public static class GenericEventV7SphereRules {
    public static bool Action(string? action)=>action is "tool:small" or "tool:big" or "dismiss" or "reward:skip_card" ||
        Enumerable.Range(0,121).Any(i=>action=="reveal:"+i)||
        Enumerable.Range(0,8).Any(i=>action=="reward:claim:"+i||action=="reward:collect:"+i||action=="reward:open:"+i)||
        Enumerable.Range(0,5).Any(i=>action=="reward:choose:"+i);
}
