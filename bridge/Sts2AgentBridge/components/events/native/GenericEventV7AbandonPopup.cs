using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.addons.mega_text;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// Own only the popup created by the selected event callback. Confirmation is a
// separate explicit action; the default policy chooses cancellation first.
internal sealed class GenericEventV7AbandonPopup : IGenericEventV7RewardChildSession
{
    private static readonly PropertyInfo? OnChosen=typeof(EventOption).GetProperty("OnChosen",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic);
    private static readonly PropertyInfo? DisableOnChosen=typeof(EventOption).GetProperty("DisableOnChosen",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic);
    private static bool? Disables(EventOption option)=>DisableOnChosen?.GetValue(option) as bool?;
    private static readonly MethodInfo? DoubleDown=typeof(MegaCrit.Sts2.Core.Models.Events.Trial).GetMethod("DoubleDown",BindingFlags.Instance|BindingFlags.NonPublic,null,Type.EmptyTypes,null);
    private static Delegate? Callback(EventOption option)=>OnChosen?.GetValue(option) as Delegate;
    internal static bool IsConfirmation(EventOption option,EventModel model) {
        var callback=Callback(option);
        return model.GetType()==typeof(MegaCrit.Sts2.Core.Models.Events.Trial)&&option.IsProceed&&Disables(option)==false&&
            DoubleDown?.ReturnType==typeof(Task)&&callback is Func<Task>&&callback.GetInvocationList().Length==1&&
            ReferenceEquals(callback.Target,model)&&callback.Method==DoubleDown;
    }
    private sealed record OptionState(NEventOptionButton Button,EventOption Option,MegaRichTextLabel Label,string Key,string Text,Delegate? Callback,bool Locked,bool Proceed,bool Enabled,bool Visible,bool WasChosen,bool? Disables,Func<MegaCrit.Sts2.Core.Entities.Players.Player,bool>? Danger);
    private readonly OptionState[] _options;
    internal readonly GenericEventV7Binding Binding;
    private readonly RunManager _manager;
    private readonly object _creature;
    private readonly NModalContainer _modal;
    private readonly CardSelectionV1DeckCard[] _deck;
    private readonly PotionModel?[] _potions;
    private readonly RelicModel[] _relics;
    private readonly string?[] _potionKeys;
    private readonly string[] _relicKeys;
    private readonly int _hp,_maxHp,_gold,_capacity,_thread=System.Environment.CurrentManagedThreadId;
    private NAbandonRunConfirmPopup? _popup;
    private NVerticalPopup? _vertical;
    private NPopupYesNoButton? _yes,_no;
    private Task? _task;
    private bool _entered,_inside,_disposed,_failed;
    private string? _action,_decision;
    private readonly List<GenericEventV7PriorResult> _results=new();
    internal bool Completed {get;private set;}
    internal void VerifyCompletion() {
        if(!Completed||!Owner()||_modal.OpenModal is not null||(_action=="cancel"?!Baseline():!_entered||_task?.IsCompletedSuccessfully!=true||!_manager.IsAbandoned||Binding.Player.Creature.CurrentHp!=0))
            throw new InvalidOperationException("Popup completion changed.");
    }
    internal void DisposeOwner() {
        if(_inside||System.Environment.CurrentManagedThreadId!=_thread||_failed||Binding.Failed)throw new InvalidOperationException("Popup cleanup is uncertain.");
        if(_action is not null)VerifyCompletion();
        _disposed=true;
    }
    internal bool Abandoned=>Completed&&_action=="confirm_abandon";
    internal object? Screen=>_popup;
    public string ContractVersion=>"abandon_confirmation_v1";
    internal GenericEventV7AbandonPopup(GenericEventV7Binding binding) {
        Binding=binding;_creature=binding.Player.Creature;
        _manager=RunManager.Instance??throw new InvalidOperationException("Run unavailable.");
        _modal=NModalContainer.Instance??throw new InvalidOperationException("Modal container unavailable.");
        if(!Valid(_modal)||_modal.OpenModal is not null||!binding.ContextValid(false)||binding.Overlays.ScreenCount!=0||
            !ReferenceEquals(_manager.DebugOnlyGetState(),binding.RunState)||_manager.IsAbandoned||(int)_manager.NetService.Type!=1)
            throw new InvalidOperationException("Event popup context unavailable.");
        _options=binding.Layout.OptionButtons.Take(9).Select(button=>new OptionState(button,button.Option,
            button.GetNodeOrNull<MegaRichTextLabel>("%Text")??throw new InvalidOperationException("Option label unavailable."),
            button.Option.TextKey,button.GetNodeOrNull<MegaRichTextLabel>("%Text")!.Text,Callback(button.Option),button.Option.IsLocked,button.Option.IsProceed,button.IsEnabled,button.IsVisibleInTree(),button.Option.WasChosen,Disables(button.Option),button.Option.WillKillPlayer)).ToArray();
        if(_options.Length is <1 or >8)throw new InvalidOperationException("Option count unavailable.");
        _deck=GenericEventV7Binding.CopyDeck(binding.Player);_potions=binding.Player.PotionSlots.ToArray();
        _potionKeys=_potions.Select(p=>p?.Id.Entry).ToArray();_relics=binding.Player.Relics.ToArray();_relicKeys=_relics.Select(r=>r.Id.Entry).ToArray();
        _hp=binding.Player.Creature.CurrentHp;_maxHp=binding.Player.Creature.MaxHp;_gold=binding.Player.Gold;_capacity=binding.Player.MaxPotionCount;
    }
    private static bool Valid(GodotObject? value)=>value is not null&&GodotObject.IsInstanceValid(value);
    private static T? Field<T>(object value,string name) where T:class=>value.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(value) as T;
    internal void Created(NAbandonRunConfirmPopup popup) {
        if(_popup is not null||popup is null||popup.GetType()!=typeof(NAbandonRunConfirmPopup)||!Valid(popup)||
            Field<object>(popup,"_mainMenuNode") is not null)throw new InvalidOperationException("Popup creation changed.");
        _popup=popup;
    }
    internal bool OwnsModal=>ReferenceEquals(NModalContainer.Instance,_modal)&&Valid(_modal)&&_popup is not null&&ReferenceEquals(_modal.OpenModal,_popup);
    private bool Owner()=>!_failed&&!Binding.Failed&&System.Environment.CurrentManagedThreadId==_thread&&GenericEventV7Hooks.Owns(Binding)&&
        ReferenceEquals(RunManager.Instance,_manager)&&ReferenceEquals(_manager.DebugOnlyGetState(),Binding.RunState)&&
        ReferenceEquals(Binding.Player.Creature,_creature)&&ReferenceEquals(Binding.Player.RunState,Binding.RunState)&&ReferenceEquals(Binding.EventModel.Owner,Binding.Player)&&
        (int)_manager.NetService.Type==1&&ReferenceEquals(NModalContainer.Instance,_modal)&&Valid(_modal)&&
        Binding.ChosenTask is {IsCompletedSuccessfully:true};
    private bool Baseline() {
        if(!Owner()||_manager.IsAbandoned||!Binding.ContextValid(false)||Binding.Overlays.ScreenCount!=0||
            Binding.Player.Creature.CurrentHp!=_hp||Binding.Player.Creature.MaxHp!=_maxHp||Binding.Player.Gold!=_gold||
            Binding.Player.MaxPotionCount!=_capacity)return false;
        var buttons=Binding.Layout.OptionButtons.Take(9).ToArray();
        if(buttons.Length!=_options.Length)return false;
        for(int i=0;i<_options.Length;i++) {
            var o=_options[i];
            if(!ReferenceEquals(buttons[i],o.Button)||!Valid(o.Button)||!ReferenceEquals(o.Button.Option,o.Option)||
                !ReferenceEquals(o.Button.Event,Binding.EventModel)||!Valid(o.Label)||!ReferenceEquals(o.Button.GetNodeOrNull<MegaRichTextLabel>("%Text"),o.Label)||
                o.Option.TextKey!=o.Key||o.Label.Text!=o.Text||!ReferenceEquals(Callback(o.Option),o.Callback)||o.Option.IsLocked!=o.Locked||o.Option.IsProceed!=o.Proceed||
                o.Button.IsEnabled!=o.Enabled||o.Button.IsVisibleInTree()!=o.Visible||o.Option.WasChosen!=o.WasChosen||Disables(o.Option)!=o.Disables||!ReferenceEquals(o.Option.WillKillPlayer,o.Danger))return false;
        }
        var deck=GenericEventV7Binding.CopyDeck(Binding.Player);
        if(deck.Length!=_deck.Length||deck.Where((c,i)=>!GenericEventV7Binding.SameDeckCard(c,_deck[i])).Any()||
            Binding.Player.PotionSlots.Count!=_potions.Length||Binding.Player.Relics.Count!=_relics.Length)return false;
        for(int i=0;i<_potions.Length;i++)if(!ReferenceEquals(Binding.Player.PotionSlots[i],_potions[i])||_potions[i]?.Id.Entry!=_potionKeys[i])return false;
        for(int i=0;i<_relics.Length;i++)if(!ReferenceEquals(Binding.Player.Relics[i],_relics[i])||_relics[i].Id.Entry!=_relicKeys[i])return false;
        return true;
    }
    private bool Controls() {
        if(!Baseline()||!OwnsModal||!Valid(_popup)||!_popup!.IsVisibleInTree())return false;
        var vertical=Field<NVerticalPopup>(_popup,"_verticalPopup");
        if(vertical is null||vertical.GetType()!=typeof(NVerticalPopup)||!Valid(vertical)||
            !ReferenceEquals(_popup.GetNodeOrNull<NVerticalPopup>("VerticalPopup"),vertical))return false;
        if(_vertical is null){_vertical=vertical;_yes=vertical.YesButton;_no=vertical.NoButton;}
        return ReferenceEquals(_vertical,vertical)&&ReferenceEquals(_yes,vertical.YesButton)&&ReferenceEquals(_no,vertical.NoButton)&&
            !ReferenceEquals(_yes,_no)&&Valid(_yes)&&Valid(_no)&&_yes!.IsVisibleInTree()&&_no!.IsVisibleInTree()&&_yes.IsEnabled&&_no.IsEnabled;
    }
    private GenericEventV7RewardRead Value(string status,string phase,string decision="",IReadOnlyList<string>? actions=null)=>
        new(Binding.Nonce,status,phase,decision,Array.Empty<GenericEventV7RewardCard>(),false,actions??Array.Empty<string>(),_results.ToArray(),null);
    private GenericEventV7RewardRead Stop(){_failed=true;Binding.Failed=true;return Value("unsupported","unsupported");}
    public GenericEventV7RewardRead Read() {
        if(_inside||_disposed||!Owner())return Stop();_inside=true;
        try {
            if(Completed){VerifyCompletion();return Value("resolved",Abandoned?"abandoned":"cancelled");}
            if(_action is null) {
                if(!Controls())return Stop();
                _decision??=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(Binding.Nonce+":"+Binding.Decision+":abandon"))).ToLowerInvariant();
                return Value("ready","confirm",_decision,new[]{"cancel","confirm_abandon"});
            }
            if(_modal.OpenModal is not null&&!OwnsModal)return Stop();
            if(_action=="cancel") {
                if(_task is not null||_entered||!Baseline())return Stop();
            }else {
                if(!_entered||_task is null||_task.IsFaulted||_task.IsCanceled)return Stop();
                if(!_task.IsCompletedSuccessfully)return Value("waiting","waiting");
                if(!_manager.IsAbandoned||Binding.Player.Creature.CurrentHp!=0)return Stop();
            }
            if(_modal.OpenModal is not null)return Value("waiting","waiting");
            _results.Add(new(_decision!,_action,_action=="cancel"?"cancelled":"abandoned"));Completed=true;
            return Value("resolved",Abandoned?"abandoned":"cancelled");
        }catch{return Stop();}finally{_inside=false;}
    }
    public GenericEventV7RewardReceipt Apply(string? decision,string? action) {
        GenericEventV7RewardReceipt Result(string outcome)=>new(Binding.Nonce,decision??"",action??"",outcome);
        if(_inside||_disposed||_failed){Stop();return Result("unsupported");}
        var read=Read();if(read.Status!="ready"||decision!=read.DecisionId||!read.LegalActions.Contains(action??""))return Result("rejected");
        _inside=true;_action=action;
        try {
            if(!Controls())throw new InvalidOperationException("Popup changed before input.");
            using(var scope=GenericEventV7Hooks.EnterPopup(this))(action=="cancel"?_no!:_yes!).ForceClick();
            if(_failed||Binding.Failed||action=="confirm_abandon"&&(!_entered||_task is null))throw new InvalidOperationException("Abandon callback absent.");
            return Result("accepted");
        }catch{Stop();return Result("uncertain");}finally{_inside=false;}
    }
    internal void EnterAbandon(RunManager manager) {
        if(!_inside||_action!="confirm_abandon"||_entered||!ReferenceEquals(manager,_manager)||!Controls())throw new InvalidOperationException("Unowned abandonment.");
        _entered=true;
    }
    internal void Returned(Task task) {
        if(!_entered||_task is not null||task is null)throw new InvalidOperationException("Abandon task replaced.");_task=task;
    }
    // The native adapter owns cleanup, including partially admitted popups.
    public void Dispose() { if(Completed)VerifyCompletion(); }
}
