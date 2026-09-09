using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Rewards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed class GenericEventV7CardRewardAdapter : IGenericEventV7RewardAdapter {
    private static readonly Func<Task> DefaultSkip=new CardRewardAlternative("Skip",(PostAlternateCardRewardAction)1).OnSelect;
    private readonly GenericEventV7ItemState _root;
    private readonly CardReward _reward;
    private readonly List<CardCreationResult> _offers;
    private readonly CardCreationResult[] _entries;
    private readonly CardModel[] _models;
    private CardSelectionV1DeckCard[] _deck;
    private readonly CardSelectionV1DeckCard[] _cards;
    private bool _batch;
    internal IReadOnlyList<CardModel> Originals=>Array.AsReadOnly(_models);
    private readonly bool _canSkip;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private Task? _offerTask,_chosenTask,_collectionTask;
    private Task<int?>? _optionTask;
    private TaskCompletionSource<int?>? _completionSource;
    private NCardRewardSelectionScreen? _menu;
    private IReadOnlyList<CardRewardAlternative>? _alternatives;
    private Func<Task>? _skipCallback;
    private NGridCardHolder[]? _holders;
    private NCardRewardAlternativeButton? _skip;
    private NProceedButton? _dismiss;
    private string _phase="open";
    private int? _selected;
    private bool _entered,_taskEntered,_disposed,_effectSeen,_removedSeen;
    private int _insertion=-1;
    internal GenericEventV7CardRewardAdapter(GenericEventV7ItemState root,CardReward reward) {
        _root=root;_reward=reward;_canSkip=reward.CanSkip;
        _offers=Field<List<CardCreationResult>>(reward,"_cards");
        if(_offers.Count is <1 or >5)throw new InvalidOperationException("Unsupported card-reward count.");
        _entries=_offers.ToArray();_models=_entries.Select(e=>e.Card).ToArray();
        _deck=GenericEventV7Binding.CopyDeck(root.Binding.Player);
        if(_deck.Length>=512||_entries.Distinct(ReferenceEqualityComparer.Instance).Count()!=_entries.Length||
            _models.Distinct(ReferenceEqualityComparer.Instance).Count()!=_models.Length||_models.Any(c=>_deck.Any(d=>ReferenceEquals(d.ModelIdentity,c))))throw new InvalidOperationException("Ambiguous reward originals.");
        _cards=_models.Select(c=>new CardSelectionV1DeckCard(c,c.Id.Entry,c.CurrentUpgradeLevel,GenericEventV7Binding.CopyEnchantment(c))).ToArray();
        if(!DeckOwned()||!Domain())throw new InvalidOperationException("Reward domain unavailable.");
    }
    private static T Field<T>(object target,string name) where T:class=>
        target.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(target) as T ?? throw new InvalidOperationException("Pinned reward field unavailable.");
    private static bool Valid(GodotObject node)=>GodotObject.IsInstanceValid(node);
    private static bool Same(CardSelectionV1DeckCard a,CardSelectionV1DeckCard b)=>ReferenceEquals(a.ModelIdentity,b.ModelIdentity)&&a.StableKey==b.StableKey&&a.UpgradeLevel==b.UpgradeLevel&&CardSelectionV1Enchantment.Same(a.Enchantment,b.Enchantment);
    internal bool Domain() {
        if(!ReferenceEquals(Field<List<CardCreationResult>>(_reward,"_cards"),_offers)||_reward.CanSkip!=_canSkip)return false;
        bool removed=_selected is not null&&_offers.Count==_entries.Length-1;
        if(_removedSeen&&!removed)return false;
        if(_offers.Count!=_entries.Length&&!removed)return false;
        for(int i=0,j=0;i<_entries.Length;i++) {
            var model=_models[i];var c=_cards[i];
            if(!ReferenceEquals(_entries[i].Card,model)||!ReferenceEquals(model.Owner,_root.Binding.Player)||!ReferenceEquals(model.RunState,_root.Binding.RunState)||
                model.Id.Entry!=c.StableKey||model.CurrentUpgradeLevel!=c.UpgradeLevel||!GenericEventV7ItemState.ValidKey(c.StableKey)||c.UpgradeLevel<0||!CardSelectionV1Enchantment.Same(GenericEventV7Binding.CopyEnchantment(model),c.Enchantment))return false;
            if(removed&&i==_selected)continue;
            if(!ReferenceEquals(_offers[j++],_entries[i]))return false;
        }
        if(removed)_removedSeen=true;
        return true;
    }
    internal void Start(bool batch=false,bool retainBaseline=false){
        if(_offerTask is not null||!_root.Ready)throw new InvalidOperationException("Reward lease unavailable.");
        _batch=batch;if(batch&&!retainBaseline)_deck=GenericEventV7Binding.CopyDeck(_root.Binding.Player);
        if(!DeckOwned())throw new InvalidOperationException("Reward deck ownership changed.");
        _offerTask=_root.OfferTask;_chosenTask=_root.Binding.ChosenTask;
    }
    internal bool InitialDeck()=>!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&Domain()&&Deck(out bool effect)&&!effect;
    internal bool RetainDeck()=>Owned()&&Deck(out _);
    internal bool RetainResult(bool selected)=>Owned()&&ReferenceEquals(_collectionTask,_root.CollectionTask)&&
        _collectionTask is {IsCompletedSuccessfully:true}&&_optionTask is {IsCompletedSuccessfully:true}&&
        _optionTask.Result==(_selected??_models.Length)&&(_selected is not null)==selected&&
        _reward.SuccessfullySelected==selected&&_removedSeen==selected;
    internal void MenuEntering(IReadOnlyList<CardCreationResult> options,IReadOnlyList<CardRewardAlternative> alternatives) {
        if(_entered||_phase!="opening"||!ReferenceEquals(options,_offers)||!Domain()||alternatives.Count>1)throw new InvalidOperationException("Unexpected reward menu.");
        if(alternatives.Count==1) {
            var a=alternatives[0];
            if(a.GetType()!=typeof(CardRewardAlternative)||a.OptionId!="Skip"||(int)a.AfterSelected!=1||a.OnSelect!=DefaultSkip)throw new InvalidOperationException("Unsupported reward alternative.");
            _skipCallback=a.OnSelect;
        }
        _alternatives=alternatives;_entered=true;
    }
    internal void MenuEntered(NCardRewardSelectionScreen menu) {
        if(!_entered||_menu is not null||menu.GetType()!=typeof(NCardRewardSelectionScreen)||!Valid(menu)||!ReferenceEquals(Field<IReadOnlyList<CardCreationResult>>(menu,"_options"),_offers))throw new InvalidOperationException("Reward menu identity changed.");
        _menu=menu;
    }
    internal void TaskEntering(NCardRewardSelectionScreen menu) {
        if(!ReferenceEquals(menu,_menu)||_taskEntered||_phase!="opening")throw new InvalidOperationException("Unexpected reward choice task.");_taskEntered=true;
    }
    internal void TaskEntered(Task<int?> task){if(!_taskEntered||_optionTask is not null||task is null)throw new InvalidOperationException("Choice task absent.");_optionTask=task;_completionSource=Field<TaskCompletionSource<int?>>(_menu!,"_completionSource");}
    private bool Owned()=>!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&_root.Domain()&&
        ReferenceEquals(_offerTask,_root.OfferTask)&&ReferenceEquals(_chosenTask,_root.Binding.ChosenTask)&&
        Good(_offerTask)&&Good(_chosenTask)&&(_root.CollectionTask is null||Good(_root.CollectionTask))&&(_optionTask is null||Good(_optionTask));
    private static bool Good(Task? task)=>task is not null&&!task.IsFaulted&&!task.IsCanceled;
    private bool Top(GodotObject target,int count)=>_root.Binding.Overlays.ScreenCount==count&&ReferenceEquals(_root.Binding.Overlays.Peek(),target)&&Valid(target);
    private bool DeckOwned()=>_deck.All(c=>c.ModelIdentity is CardModel model&&ReferenceEquals(model.Owner,_root.Binding.Player)&&ReferenceEquals(model.RunState,_root.Binding.RunState));
    private bool Deck(out bool complete) {
        complete=false;if(!DeckOwned())return false;var now=GenericEventV7Binding.CopyDeck(_root.Binding.Player);
        bool added=_selected is not null&&now.Length==_deck.Length+1;
        if(now.Length!=_deck.Length&&!added||_effectSeen&&!added)return false;
        int at=added?Array.FindIndex(now,c=>ReferenceEquals(c.ModelIdentity,_models[_selected!.Value])):-1;
        if(added&&(at<0||_insertion>=0&&at!=_insertion||!Same(now[at],_cards[_selected!.Value])))return false;
        for(int i=0,j=0;i<now.Length;i++){if(i==at)continue;if(!Same(now[i],_deck[j++]))return false;}
        if(added){_effectSeen=true;_insertion=at;complete=true;}
        return true;
    }
    private bool MenuReady() {
        if(_menu is null||_optionTask is null||!Top(_menu,2)||!_menu.IsVisibleInTree()||_optionTask.IsCompleted||
            !ReferenceEquals(Field<IReadOnlyList<CardCreationResult>>(_menu,"_options"),_offers)||
            !ReferenceEquals(Field<IReadOnlyList<CardRewardAlternative>>(_menu,"_extraOptions"),_alternatives)||
            !ReferenceEquals(Field<TaskCompletionSource<int?>>(_menu,"_completionSource"),_completionSource))return false;
        var row=_menu.GetNodeOrNull<Control>("UI/CardRow");var alt=_menu.GetNodeOrNull<Control>("UI/RewardAlternatives");
        if(row is null||alt is null||!Valid(row)||!Valid(alt)||row.GetChildCount(false)!=_models.Length||_alternatives is null||alt.GetChildCount(false)!=_alternatives.Count)return false;
        var holders=new NGridCardHolder[_models.Length];
        for(int i=0;i<holders.Length;i++) {
            if(row.GetChild(i,false) is not NGridCardHolder h||!Valid(h)||!h.IsVisibleInTree()||!ReferenceEquals(h.CardModel,_models[i])||h.CardNode is not {} node||!Valid(node)||!ReferenceEquals(node.Model,_models[i])||!ReferenceEquals(_menu.GetCardHolder(_models[i]),h))return false;
            holders[i]=h;
        }
        if(_holders is not null&&!_holders.SequenceEqual(holders))throw new InvalidOperationException("Reward holder replaced.");_holders??=holders;
        var clickable=typeof(NCardHolder).GetField("_isClickable",BindingFlags.Instance|BindingFlags.NonPublic);
        if(clickable is null||holders.Any(h=>clickable.GetValue(h) is not true))return false;
        if(_alternatives.Count==1) {
            var a=_alternatives[0];
            if(a.OptionId!="Skip"||(int)a.AfterSelected!=1||!ReferenceEquals(a.OnSelect,_skipCallback))throw new InvalidOperationException("Reward alternative changed.");
            if(alt.GetChild(0,false) is not NCardRewardAlternativeButton button||!Valid(button))return false;
            if(_skip is not null&&!ReferenceEquals(_skip,button))throw new InvalidOperationException("Skip control replaced.");_skip??=button;
            if(_canSkip&&!_root.DisallowSkipping&&(!button.IsEnabled||!button.IsVisibleInTree()))return false;
        }
        return true;
    }
    internal bool DismissReady() {
        if(!Top(_root.Screen!,1)||!_root.Screen!.IsVisibleInTree())return false;
        var button=_root.Screen.GetNodeOrNull<NProceedButton>("ProceedButton");
        if(button is null||!Valid(button)||!ReferenceEquals(Field<NProceedButton>(_root.Screen,"_proceedButton"),button))return false;
        if(_dismiss is not null&&!ReferenceEquals(_dismiss,button))throw new InvalidOperationException("Dismiss control replaced.");_dismiss??=button;
        return button.IsVisibleInTree()&&button.IsEnabled&&!_root.DisallowSkipping;
    }
    public GenericEventV7RewardCapture Capture() {
        GenericEventV7RewardCapture Value(string phase,bool skip=false)=>new(phase,phase=="choose"?_cards.Select((c,i)=>new GenericEventV7RewardCard(i,c.StableKey,c.UpgradeLevel)).ToArray():Array.Empty<GenericEventV7RewardCard>(),skip);
        if(!Owned()||!Deck(out bool effect))return Value("unsupported");
        if(_phase=="open")return Value(_root.TryButton(out _)?"open":"waiting");
        if(_root.CollectionTask is null)return Value("unsupported");
        _collectionTask??=_root.CollectionTask;if(!ReferenceEquals(_collectionTask,_root.CollectionTask))return Value("unsupported");
        if(_phase is "opening" or "choose") {
            if(_reward.SuccessfullySelected||effect||_root.CollectionTask.IsCompleted)return Value("unsupported");
            if(!MenuReady())return Value("waiting");_phase="choose";
            return Value("choose",_canSkip&&!_root.DisallowSkipping&&_skip is {IsEnabled:true}&&_skip.IsVisibleInTree());
        }
        if(_phase is "chosen" or "skipped" or "dismiss" or "dismissing") {
            if(_optionTask is null||_menu is null)return Value("unsupported");
            if(!_optionTask.IsCompleted)return Value(MenuReady()?"waiting":"unsupported");
            if(_optionTask.Result!=(_selected??_models.Length))return Value("unsupported");
            if(_phase=="chosen") {
                if(_root.Binding.Overlays.ScreenCount!=0&&!(Top(_menu,2)||Top(_root.Screen!,1)))return Value("unsupported");
                if(_batch&&_collectionTask.IsCompletedSuccessfully)
                    return Value(effect&&_reward.SuccessfullySelected&&_removedSeen&&(Top(_root.Screen!,1)||_root.Binding.Overlays.ScreenCount==0)?"complete":"unsupported");
                if(_collectionTask.IsCompletedSuccessfully&&_offerTask!.IsCompletedSuccessfully&&_chosenTask!.IsCompletedSuccessfully)
                    return Value(effect&&_reward.SuccessfullySelected&&_removedSeen&&_root.Binding.Overlays.ScreenCount==0?"complete":"unsupported");
                return Value("waiting");
            }
            if(effect||_reward.SuccessfullySelected||_removedSeen)return Value("unsupported");
            if(!_collectionTask.IsCompleted)return Value("waiting");
            if(_batch)return Value(Top(_root.Screen!,1)?"complete":"unsupported");
            if(_phase=="dismissing")return Value(_offerTask!.IsCompletedSuccessfully&&_chosenTask!.IsCompletedSuccessfully&&_root.Binding.Overlays.ScreenCount==0?"complete":"waiting");
            if(!DismissReady())return Value("waiting");_phase="dismiss";return Value("dismiss");
        }
        return Value("unsupported");
    }
    public void Dispatch(string action) {
        var capture=Capture();
        if(action=="open"&&capture.Phase=="open") {
            _phase="opening";_root.Dispatched=true;
            using(GenericEventV7Hooks.EnterItemCollection(_root))_root.Button!.ForceClick();
            if(!_root.CollectionEntered||_root.CollectionTask is null)throw new InvalidOperationException("Owned reward opening absent.");return;
        }
        if(capture.Phase=="choose") {
            if(action=="skip"&&capture.CanSkip){_phase="skipped";_skip!.ForceClick();return;}
            if(action.StartsWith("choose:",StringComparison.Ordinal)&&int.TryParse(action.AsSpan(7),out int slot)&&slot>=0&&slot<_models.Length) {
                _selected=slot;_phase="chosen";
                if(_holders![slot].EmitSignal(NCardHolder.SignalName.Pressed,_holders[slot])!=Error.Ok)throw new InvalidOperationException("Reward input failed.");return;
            }
        }
        if(action=="dismiss"&&capture.Phase=="dismiss"){_phase="dismissing";_dismiss!.ForceClick();return;}
        throw new InvalidOperationException("Stale reward action.");
    }
    internal void DismissSet(){if(!_batch||!Owned()||!DismissReady())throw new InvalidOperationException("Set dismissal unavailable.");_dismiss!.ForceClick();}
    public void Dispose(){if(System.Environment.CurrentManagedThreadId!=_thread)throw new InvalidOperationException("Reward owner required.");_disposed=true;}
}
