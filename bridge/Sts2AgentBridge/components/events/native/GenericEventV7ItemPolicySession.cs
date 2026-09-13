using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Items.Native;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// One owned item screen. Discard and collection are separate, reconciled native
// actions. Native Proceed dismisses every remaining unclaimed entry explicitly.
internal sealed class GenericEventV7ItemPolicySession : IGenericEventV7RewardChildSession
{
    private readonly GenericEventV7ItemState _root;
    private readonly Task _offer,_parent;
    private readonly HashSet<object> _originalPotions=new(ReferenceEqualityComparer.Instance);
    private readonly Dictionary<int,Task> _collected=new();
    private readonly List<GenericEventV7PriorResult> _history=new();
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private CardSelectionV1DeckCard[] _deck;
    private ItemV1PotionSlotBinding[] _slots;
    private RelicModel[] _relics;
    private GenericEventV7ItemAdapter? _collection;
    private GenericEventV7CardRewardAdapter? _card;
    private readonly Dictionary<int,bool> _cardResults=new();
    private bool _cardChosen;
    private PinnedPotionDiscard? _discard;
    private NProceedButton? _proceed;
    private string? _decision,_action;
    private int _index,_reads,_attempts;
    private bool _dismissed,_done,_inside,_disposed,_failed;
    public string ContractVersion=>"item_policy_v1";
    internal GenericEventV7ItemPolicySession(GenericEventV7ItemState root) {
        _root=root;
        if(!CanStart(root))throw new InvalidOperationException("Item policy domain unavailable.");
        _offer=root.OfferTask!;_parent=root.Binding.ItemParentTask!;
        foreach(var e in root.Entries!){e.OfferTask=_offer;e.Screen=root.Screen;}
        _deck=GenericEventV7Binding.CopyDeck(root.Binding.Player);_slots=Slots();_relics=root.Binding.Player.Relics.ToArray();
        foreach(var slot in _slots)if(slot.ModelIdentity is {} model)_originalPotions.Add(model);
    }
    internal static bool CanStart(GenericEventV7ItemState root) {
        if(!root.Ready||!root.Domain()||!GenericEventV7ItemAdapter.Slots(root.Binding.Player,out int capacity,out var slots))return false;
        var player=root.Binding.Player;
        if(slots.Where(s=>s.ModelIdentity is not null).Select(s=>s.ModelIdentity).Distinct(ReferenceEqualityComparer.Instance).Count()!=slots.Count(s=>s.ModelIdentity is not null)||
            player.PotionSlots.Any(p=>p is not null&&!ReferenceEquals(p.Owner,player))||player.Relics.Any(r=>!ReferenceEquals(r.Owner,player)))return false;
        foreach(var e in root.Entries!) {
            if(e.CardReward is not null)continue;
            if(e.Key=="POTION_BELT"&&e.CapacityGain!=2)return false;
            if(e.Model is PotionModel p&&(p.Owner is not null||player.PotionSlots.Any(x=>ReferenceEquals(x,p))))return false;
            if(e.Model is RelicModel r&&(r.Owner is not null||player.Relics.Any(x=>ReferenceEquals(x,r))))return false;
        }
        if(!root.DisallowSkipping)return true;
        int gain=root.Entries!.Sum(e=>e.CapacityGain);
        int replaceable=Enumerable.Range(0,capacity).Count(i=>PinnedPotionDiscard.Eligible(player,i));
        return capacity+gain<=8&&root.Entries.Count(e=>e.CardReward is null&&e.Kind==ItemV1ItemKind.Potion)<=slots.Count(s=>s.ModelIdentity is null)+gain+replaceable;
    }
    private bool InventoryOwners() {
        var player=_root.Binding.Player;
        if(player.PotionSlots.Any(p=>p is not null&&!ReferenceEquals(p.Owner,player))||player.Relics.Any(r=>!ReferenceEquals(r.Owner,player)))return false;
        foreach(var e in _root.Entries!) {
            if(e.CardReward is not null)continue;
            object? owner=e.Model is PotionModel p?p.Owner:((RelicModel)e.Model!).Owner;
            int count=e.Model is PotionModel ? player.PotionSlots.Count(p=>ReferenceEquals(p,e.Model)):player.Relics.Count(r=>ReferenceEquals(r,e.Model));
            bool absent=owner is null&&count==0, acquired=ReferenceEquals(owner,player)&&count==1;
            if(!e.Dispatched?!absent:e.Reward!.SuccessfullySelected?!acquired:!absent&&!acquired)return false;
        }
        return true;
    }
    private ItemV1PotionSlotBinding[] Slots(){if(!GenericEventV7ItemAdapter.Slots(_root.Binding.Player,out _,out var slots))throw new InvalidOperationException("Potion inventory unavailable.");return slots.ToArray();}
    private bool SameDeck(){var deck=GenericEventV7Binding.CopyDeck(_root.Binding.Player);return deck.Length==_deck.Length&&deck.Select((c,i)=>GenericEventV7Binding.SameDeckCard(c,_deck[i])).All(x=>x);}
    private bool SameSlots(){var now=Slots();return now.Length==_slots.Length&&now.Select((s,i)=>ReferenceEquals(s.ModelIdentity,_slots[i].ModelIdentity)&&s.StableKey==_slots[i].StableKey).All(x=>x);}
    private bool Baseline()=>(_card is not null?_card.RetainDeck():SameDeck())&&SameSlots()&&_root.Binding.Player.Relics.SequenceEqual(_relics,ReferenceEqualityComparer.Instance);
    private bool Owned()=>NModalContainer.Instance?.OpenModal is null&&!_failed&&!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&_root.Domain()&&(_card is not null?_card.RetainDeck():_root.Overlay())&&InventoryOwners()&&
        ReferenceEquals(_root.OfferTask,_offer)&&ReferenceEquals(_root.Binding.ItemParentTask,_parent)&&!_offer.IsFaulted&&!_offer.IsCanceled&&!_parent.IsFaulted&&!_parent.IsCanceled&&
        _collected.All(p=>(_cardResults.TryGetValue(p.Key,out bool selected)?_root.Entries![p.Key].CardReward!.RetainResult(selected):(_root.Entries![p.Key].Reward!.SuccessfullySelected&&ReferenceEquals(_root.Entries[p.Key].Reward is PotionReward potion?potion.ClaimedPotion:((RelicReward)_root.Entries[p.Key].Reward!).ClaimedRelic,_root.Entries[p.Key].Model)))&&ReferenceEquals(_root.Entries[p.Key].CollectionTask,p.Value)&&p.Value.IsCompletedSuccessfully);
    private bool DismissReady() {
        var screen=_root.Screen;var overlays=_root.Binding.Overlays;
        if(_root.DisallowSkipping||screen is null||!GodotObject.IsInstanceValid(screen)||!screen.IsVisibleInTree()||overlays.ScreenCount!=1||!ReferenceEquals(overlays.Peek(),screen))return false;
        var button=screen.GetNodeOrNull<NProceedButton>("ProceedButton");
        if(button is null||!GodotObject.IsInstanceValid(button)||!ReferenceEquals(screen.GetType().GetField("_proceedButton",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(screen),button))return false;
        if(_proceed is not null&&!ReferenceEquals(_proceed,button))throw new InvalidOperationException("Reward dismissal replaced.");_proceed=button;
        return button.IsEnabled&&button.IsVisibleInTree();
    }
    private string[] Actions() {
        if(_card is not null){var card=_card.Capture();if(card.Phase!="choose")throw new InvalidOperationException("Card menu not ready.");return card.Cards.Select(c=>"choose:"+c.Slot).Concat(card.CanSkip?new[]{"skip_card"}:Array.Empty<string>()).ToArray();}
        var actions=new List<string>();var slots=Slots();int capacity=slots.Length;
        for(int i=0;i<_root.Entries!.Length;i++) {
            var e=_root.Entries[i];if(_collected.ContainsKey(i))continue;
            if(!e.TryButton(out _))throw new InvalidOperationException("Item control changed.");
            if(e.CardReward is not null|| (e.Kind==ItemV1ItemKind.Potion?slots.Any(s=>s.ModelIdentity is null):capacity+e.CapacityGain<=8))actions.Add("collect:"+i);
        }
        for(int i=0;i<slots.Length;i++)if(slots[i].ModelIdentity is {} model&&_originalPotions.Contains(model)&&PinnedPotionDiscard.Eligible(_root.Binding.Player,i))actions.Add("discard:"+i);
        if(DismissReady())actions.Add("skip_remaining");
        return actions.ToArray();
    }
    private GenericEventV7RewardRead Value(string status) {
        bool ready=status=="ready";string[] actions=ready?Actions():Array.Empty<string>();
        var offers=ready?_root.Entries!.Select((e,i)=>new GenericEventV7ItemPolicyOffer(i,e.CardReward is not null?"card":e.Kind==ItemV1ItemKind.Potion?"potion":"relic",e.CardReward is not null?"CARD_REWARD":e.Key,e.CapacityGain,_collected.ContainsKey(i))).ToArray():Array.Empty<GenericEventV7ItemPolicyOffer>();
        var slots=ready?Slots().Select(s=>s.StableKey).ToArray():Array.Empty<string?>();
        var menu=ready&&_card is not null?_card.Capture():null;
        if(ready)_decision=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(_root.Binding.Nonce+":item-policy:"+_history.Count+":"+string.Join("|",actions)+":"+string.Join("|",slots)+":"+string.Join("|",menu?.Cards.Select(c=>$"{c.Slot}:{c.Key}:{c.UpgradeLevel}")??Array.Empty<string>())))).ToLowerInvariant();
        return new(_root.Binding.Nonce,status,status=="resolved"?"complete":status=="ready"?(menu is not null?"choose_card":"items"):status,ready?_decision!:"",menu?.Cards??Array.Empty<GenericEventV7RewardCard>(),menu?.CanSkip??false,actions,_history.ToArray(),null,
            ItemPolicy:new(offers,slots,!_root.DisallowSkipping));
    }
    private GenericEventV7RewardRead Stop(){Abort();return Value("unsupported");}
    internal void Abort(){_failed=true;_root.Binding.Failed=true;_discard?.Abort();}
    public GenericEventV7RewardRead Read() {
        if(_inside||_disposed||_failed||System.Environment.CurrentManagedThreadId!=_thread)return Stop();_inside=true;
        try {
            if(++_reads>256||!Owned())return Stop();
            if(_card is not null) {
                var card=_card.Capture();if(card.Phase=="unsupported"||!SameSlots()||!_root.Binding.Player.Relics.SequenceEqual(_relics,ReferenceEqualityComparer.Instance))return Stop();
                if(card.Phase=="choose") {if(_action is not null)FinishAction("opened");return Value("ready");}
                if(card.Phase!="complete")return Value("waiting");
                if(!_card.RetainResult(_cardChosen))return Stop();
                _collected.Add(_index,_root.Entries![_index].CollectionTask!);_cardResults.Add(_index,_cardChosen);_deck=GenericEventV7Binding.CopyDeck(_root.Binding.Player);_card=null;FinishAction(_cardChosen?"collected":"card_skipped");
            }
            if(_discard is not null) {
                int state=_discard.Read();if(state<0)return Stop();if(state==0)return Value("waiting");
                _discard.Dispose();_discard=null;_slots=Slots();FinishAction("discarded");
            }
            if(_collection is not null) {
                var c=_collection.CaptureCompletion();if(!c.OwnershipValid||c.Collection?.State is GenericEventV7ItemTaskState.Canceled or GenericEventV7ItemTaskState.Faulted)return Stop();
                if(c.Collection?.State!=GenericEventV7ItemTaskState.Succeeded)return Value("waiting");
                if(!c.EffectStillValid||!SameDeck())return Stop();
                var entry=_root.Entries![_index];var relics=_root.Binding.Player.Relics.ToArray();
                if(entry.Kind==ItemV1ItemKind.Relic) {
                    if(entry.CapacityGain==0&&!SameSlots())return Stop();
                    if(relics.Length!=_relics.Length+1||!relics.Take(_relics.Length).SequenceEqual(_relics,ReferenceEqualityComparer.Instance)||
                        !ReferenceEquals(relics[^1],entry.Model)||!ReferenceEquals(relics[^1].Owner,_root.Binding.Player))return Stop();
                }else if(!relics.SequenceEqual(_relics,ReferenceEqualityComparer.Instance))return Stop();
                _collected.Add(_index,entry.CollectionTask!);_collection.Dispose();_collection=null;_slots=Slots();_relics=relics;FinishAction("collected");
            }
            if(!Baseline())return Stop();
            if(_dismissed||_collected.Count==_root.OfferCount&&!_cardResults.Values.Any(x=>!x)) {
                if(_root.Entries!.Where((e,i)=>!_collected.ContainsKey(i)).Any(e=>e.Reward!.SuccessfullySelected||e.Dispatched||e.CollectionTask is not null))return Stop();
                if(!_offer.IsCompletedSuccessfully||!_parent.IsCompletedSuccessfully)return Value("waiting");
                if(_root.Binding.Overlays.ScreenCount!=0)return Stop();
                if(_action is not null)FinishAction("skipped");_done=true;return Value("resolved");
            }
            if(_offer.IsCompleted||_parent.IsCompleted||_done)return Stop();
            return Value("ready");
        }catch{return Stop();}finally{_inside=false;}
    }
    private void FinishAction(string result){if(_action is null||_decision is null)throw new InvalidOperationException("Unreserved reward action.");_history.Add(new(_decision,_action,result));_action=null;}
    public GenericEventV7RewardReceipt Apply(string? decision,string? action) {
        GenericEventV7RewardReceipt Result(string outcome)=>new(_root.Binding.Nonce,decision??"",action??"",outcome);
        var ready=Read();if(ready.Status!="ready"||decision!=ready.DecisionId||!ready.LegalActions.Contains(action??""))return Result("rejected");
        if(_attempts>=25||_inside||!Baseline()){Abort();return Result("unsupported");}_attempts++;_inside=true;_action=action;
        try {
            if(_card is not null) {_cardChosen=action!="skip_card";_card.Dispatch(_cardChosen?action!:"skip");}
            else if(action=="skip_remaining") {if(!DismissReady())throw new InvalidOperationException();_dismissed=true;_proceed!.ForceClick();}
            else if(action!.StartsWith("discard:",StringComparison.Ordinal)) {
                int slot=action[^1]-'0';_discard=new(_root.Binding.Player,slot,()=>Owned()&&_root.Binding.Overlays.ScreenCount==1&&ReferenceEquals(_root.Binding.Overlays.Peek(),_root.Screen));_discard.Dispatch();
            } else {
                _index=action[^1]-'0';var entry=_root.Entries![_index];
                if(entry.CardReward is {} card){_card=card;card.Start(batch:true);card.Dispatch("open");return Result("accepted");}
                _collection=new(entry);
                var surface=_collection.CaptureSurface();if(surface.Offers.Count!=1)throw new InvalidOperationException();surface.Offers[0].Dispatch();
            }
            return Result("accepted");
        }catch{Abort();return Result("uncertain");}finally{_inside=false;}
    }
    public void Dispose() {
        if(_disposed){if(_failed)throw new InvalidOperationException("Item policy cleanup uncertain.");return;}
        try {
            if(!_done||!Owned()||!Baseline())throw new InvalidOperationException("Item policy unresolved.");
            foreach(var entry in _root.Entries!)entry.CardReward?.Dispose();_collection?.Dispose();_discard?.Dispose();_disposed=true;
        } catch {
            Abort();_disposed=true;
            try{_collection?.Dispose();}finally{_discard?.Dispose();}
            throw;
        }
    }
}
