using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Rewards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;

namespace Sts2AgentBridge.Items.Native;

internal interface IPinnedAlternativePickup:IDisposable
{
    IDisposable EnterCallback();
    bool Complete(bool expectsRelic);
    int CertifiedCapacity {get;}
}

// Bind the already-created native menu. Generating alternatives here would run
// gameplay hooks again. Reroll and Sacrifice retain their actual callback Tasks.
internal sealed class PinnedRewardAlternatives : IPinnedRewardAlternatives
{
    private static readonly AsyncLocal<PinnedRewardAlternatives?> Scope=new();
    private static PinnedRewardAlternatives? Active;
    private readonly CardReward _reward;
    private readonly NCardRewardSelectionScreen _screen;
    private readonly Player _player;
    private readonly RunManager _manager;
    private readonly NRun _node;
    private readonly object _run,_room;
    private readonly CardRewardAlternative[] _options;
    private readonly (string Id,Func<Task> Callback,PostAlternateCardRewardAction After)[] _optionValues;
    private readonly NCardRewardAlternativeButton[] _buttons;
    private readonly Control _container;
    private readonly TaskCompletionSource<int?> _selection;
    private readonly CardModel[] _cards;
    private readonly PinnedAutomaticRelicEffects.State _before;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private readonly Harmony _hooks=new("sts.bridge.reward.alternative."+Guid.NewGuid().ToString("N"));
    private readonly List<MethodInfo> _targets=new();
    private CardRewardAlternative? _chosen;
    private Task? _callback;
    private Task<RelicModel>? _obtain;
    private RelicModel? _relic;
    private PinnedAutomaticRelicEffects? _effects;
    private readonly Func<IPinnedAlternativePickup>? _pickupFactory;
    private IPinnedAlternativePickup? _pickup;
    private IDisposable? _pickupScope;
    private Task? _effectTask;
    private int _sacrificed;
    private long _deadline;
    private bool _invoked,_entered,_rerolled,_complete,_failed,_disposed;
    public IReadOnlyList<CardModel> RerolledCards {get;private set;}=Array.Empty<CardModel>();
    public int CertifiedCapacity=>_invoked&&Owner()?(_pickup?.CertifiedCapacity??
        (_relic?.GetType()==typeof(PotionBelt)&&_effects?.Valid()==true?_player.PotionSlots.Count:-1)):-1;
    private static object? Field(object value,string name)=>value.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(value);
    internal PinnedRewardAlternatives(PinnedPublicRewardParentTarget parent,NCardRewardSelectionScreen screen,Func<IPinnedAlternativePickup>? pickupFactory=null)
    {
        _pickupFactory=pickupFactory;
        _reward=(CardReward)parent.Reward;_screen=screen;_player=_reward.Player;_manager=RunManager.Instance??throw new InvalidOperationException("reward_manager");_node=NRun.Instance!;
        _run=_player.RunState;_room=_player.RunState.CurrentRoom!;_before=new(_player);_cards=parent.OfferedCards.ToArray();
        _options=((IReadOnlyList<CardRewardAlternative>)Field(screen,"_extraOptions")!).ToArray();
        _optionValues=_options.Select(o=>(o.OptionId,o.OnSelect,o.AfterSelected)).ToArray();
        _container=(Control)Field(screen,"_rewardAlternativesContainer")!;
        _selection=(TaskCompletionSource<int?>)Field(screen,"_completionSource")!;
        _buttons=_container.GetChildren().OfType<NCardRewardAlternativeButton>().ToArray();
        Require(_options.Length<=2&&_buttons.Length==_options.Length&&_options.Select(o=>o.OptionId).Distinct().Count()==_options.Length);
        foreach(var option in _options) {
            bool valid=option.OptionId switch {
                "Skip"=>_reward.CanSkip&&option.AfterSelected==PostAlternateCardRewardAction.EndSelectionAndDoNotCompleteReward,
                "REROLL"=>_reward.CanReroll&&option.AfterSelected==PostAlternateCardRewardAction.DoNothing,
                "SACRIFICE"=>option.OnSelect.Target is PaelsWing wing&&ReferenceEquals(wing.Owner,_player)&&_player.Relics.Contains(wing)&&option.OnSelect.Method.Name=="OnSacrifice"&&option.AfterSelected==PostAlternateCardRewardAction.EndSelectionAndCompleteReward,
                _=>false};
            Require(valid&&option.OnSelect.Method.DeclaringType?.Assembly==typeof(CardReward).Assembly);
        }
        Require(_options.Any(o=>o.OptionId=="Skip")==_reward.CanSkip);
        Read();
    }
    private bool Owner()=>!_failed&&!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&ReferenceEquals(RunManager.Instance,_manager)&&
        ReferenceEquals(_manager.DebugOnlyGetState(),_run)&&ReferenceEquals(NRun.Instance,_node)&&ReferenceEquals(_player.RunState,_run)&&
        ReferenceEquals(_player.RunState.CurrentRoom,_room)&&ReferenceEquals(_reward.Player,_player)&&(_deadline==0||System.Environment.TickCount64<=_deadline);
    private bool Foreground()=>Owner()&&NModalContainer.Instance?.OpenModal is null&&NCapstoneContainer.Instance?.InUse!=true&&
        ReferenceEquals(ActiveScreenContext.Instance.GetCurrentScreen(),_screen)&&ReferenceEquals(_node.GlobalUi.Overlays.Peek(),_screen)&&
        ReferenceEquals(Field(_reward,"_currentlyShownScreen"),_screen)&&GodotObject.IsInstanceValid(_screen)&&_screen.IsVisibleInTree();
    public IReadOnlyList<string> Read()
    {
        Require(!_invoked&&Foreground()&&_before.Same(new(_player))&&!_selection.Task.IsCompleted&&
            ReferenceEquals(Field(_screen,"_completionSource"),_selection)&&ReferenceEquals(Field(_screen,"_rewardAlternativesContainer"),_container)&&
            ((IReadOnlyList<CardRewardAlternative>)Field(_screen,"_extraOptions")!).SequenceEqual(_options)&&
            _options.Select(o=>(o.OptionId,o.OnSelect,o.AfterSelected)).SequenceEqual(_optionValues)&&
            _container.GetChildren().OfType<NCardRewardAlternativeButton>().SequenceEqual(_buttons)&&_buttons.All(b=>GodotObject.IsInstanceValid(b)&&b.IsVisibleInTree()&&b.IsEnabled)&&
            _reward.Cards.SequenceEqual(_cards));
        return _options.Where(o=>o.OptionId!="Skip").Select(o=>o.OptionId.ToLowerInvariant()).ToArray();
    }
    public NCardRewardAlternativeButton? Skip=>Array.FindIndex(_options,o=>o.OptionId=="Skip") is int i&&i>=0?_buttons[i]:null;
    public void Dispatch(string action)
    {
        Require(Read().Contains(action)&&Active is null);
        int index=Array.FindIndex(_options,o=>o.OptionId==action.ToUpperInvariant());_chosen=_options[index];
        _invoked=true;_deadline=System.Environment.TickCount64+15000;Active=this;
        if(_chosen.OnSelect.Target is PaelsWing wing)_sacrificed=wing.RewardsSacrificed;
        try {
            Patch(_chosen.OnSelect.Method,nameof(CallbackPrefix),nameof(CallbackPostfix),nameof(CallbackFinalizer));
            if(action=="reroll")Patch(typeof(CardReward).GetMethod("Reroll")!,nameof(RerollPrefix),nameof(RerollPostfix));
            else {
                _pickup=_pickupFactory?.Invoke();
                if(_pickup is null)Patch(typeof(RelicCmd).GetMethod("Obtain",new[]{typeof(RelicModel),typeof(Player),typeof(int)})!,nameof(ObtainPrefix),nameof(ObtainPostfix));
            }
            _buttons[index].ForceClick();Require(!_failed);
        } catch {_failed=true;throw;}
    }
    private static void CallbackPrefix(object __instance,out PinnedRewardAlternatives? __state)
    {
        __state=Active;if(__state is not {} s)return;
        s.Require(s.Owner()&&s.Foreground()&&!s._entered&&ReferenceEquals(__instance,s._chosen!.OnSelect.Target)&&s._selection.Task.IsCompletedSuccessfully&&
            s._selection.Task.Result==s._cards.Length+Array.IndexOf(s._options,s._chosen)&&s._before.Same(new(s._player))&&Scope.Value is null);
        s._entered=true;Scope.Value=s;s._pickupScope=s._pickup?.EnterCallback();
    }
    private static void CallbackPostfix(Task __result,PinnedRewardAlternatives? __state)
    {if(__state is {} s){try{s.Require(__result is not null);s._callback=__result;}finally{s.ExitCallback();}}}
    private static void CallbackFinalizer(Exception? __exception,PinnedRewardAlternatives? __state)
    {if(__state is {} s){if(__exception is not null)s._failed=true;s.ExitCallback();}}
    private void ExitCallback()
    {var scope=_pickupScope;_pickupScope=null;try{scope?.Dispose();}finally{Scope.Value=null;}}
    private static void RerollPrefix(CardReward __instance,out PinnedRewardAlternatives? __state)
    {__state=Scope.Value;if(__state is {} s)s.Require(s.Owner()&&ReferenceEquals(__instance,s._reward)&&!s._rerolled&&__instance.CanReroll);}
    private static void RerollPostfix(PinnedRewardAlternatives? __state)
    {if(__state is {} s){s._rerolled=true;s.RerolledCards=s._reward.Cards.ToArray();s.Require(s.RerolledCards.Count is >=1 and <=5&&!s.RerolledCards.Any(c=>s._cards.Contains(c)));}}
    private static void ObtainPrefix(RelicModel __0,Player __1,int __2,out PinnedRewardAlternatives? __state)
    {
        __state=Scope.Value;if(__state is not {} s)return;
        s.Require(s.Owner()&&s._chosen!.OptionId=="SACRIFICE"&&s._relic is null&&ReferenceEquals(__1,s._player)&&__2==-1&&__0.Owner is null&&
            s._before.Same(new(s._player))&&PinnedAutomaticRelicEffects.Supports(__0));
        s._relic=__0;s.Patch(__0.GetType().GetMethod("AfterObtained",Type.EmptyTypes)!,nameof(EffectPrefix),nameof(EffectPostfix));
    }
    private static void ObtainPostfix(Task<RelicModel> __result,PinnedRewardAlternatives? __state)
    {if(__state is {} s){s.Require(__result is not null);s._obtain=__result;}}
    private static void EffectPrefix(RelicModel __instance,out PinnedAutomaticRelicEffects? __state)
    {
        __state=null;var s=Scope.Value;if(s is null)return;
        s.Require(s.Owner()&&ReferenceEquals(__instance,s._relic)&&s._effects is null&&s._before.AddedRelic(new(s._player),__instance));
        s._effects=new(s._player,__instance,s.Owner);__state=s._effects.Enter();
    }
    private static void EffectPostfix(Task __result,PinnedAutomaticRelicEffects? __state)
    {var s=Scope.Value;if(s is null)return;PinnedAutomaticRelicEffects.Exit(__state);s.Require(__result is not null);s._effectTask=__result;}
    public bool Poll()
    {
        Require(_invoked&&Owner()&&ExactHooks()&&_callback?.IsFaulted!=true&&_callback?.IsCanceled!=true&&_obtain?.IsFaulted!=true&&_obtain?.IsCanceled!=true&&
            _effectTask?.IsFaulted!=true&&_effectTask?.IsCanceled!=true);
        if(_callback?.IsCompletedSuccessfully!=true)return false;
        if(_chosen!.OptionId=="REROLL") {
            Require(_rerolled&&!_reward.CanReroll&&!_reward.SuccessfullySelected&&Foreground()&&_before.Same(new(_player))&&_reward.Cards.SequenceEqual(RerolledCards));
            if(ReferenceEquals(Field(_screen,"_completionSource"),_selection))return false;
            Require(Field(_screen,"_completionSource") is TaskCompletionSource<int?> next&&!next.Task.IsCompleted);
        } else {
            var wing=(PaelsWing)_chosen.OnSelect.Target!;
            Require(ReferenceEquals(wing.Owner,_player)&&wing.RewardsSacrificed==_sacrificed+1);
            bool gains=wing.RewardsSacrificed%wing.DynamicVars["Sacrifices"].IntValue==0;
            if(_pickup is {} pickup)Require(pickup.Complete(gains));
            else Require(gains ? _relic is not null&&_obtain?.IsCompletedSuccessfully==true&&ReferenceEquals(_obtain.Result,_relic)&&_effectTask?.IsCompletedSuccessfully==true&&_effects?.Valid()==true : _relic is null&&_before.Same(new(_player)));
            if(!_reward.SuccessfullySelected)return false;
        }
        _complete=true;return true;
    }
    private void Patch(MethodInfo method,string prefix,string postfix,string? finalizer=null)
    {
        Require(method is not null&&method.GetMethodBody() is not null&&!(Harmony.GetPatchInfo(method)?.Owners.Any()??false));
        _targets.Add(method);_hooks.Patch(method,new HarmonyMethod(typeof(PinnedRewardAlternatives),prefix),new HarmonyMethod(typeof(PinnedRewardAlternatives),postfix),
            finalizer:finalizer is null?null:new HarmonyMethod(typeof(PinnedRewardAlternatives),finalizer));
    }
    private bool ExactHooks()=>_targets.All(m=>Harmony.GetPatchInfo(m) is {} p&&p.Owners.Count==1&&p.Owners.Contains(_hooks.Id));
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool condition){if(!condition){_failed=true;throw new InvalidOperationException("reward_alternative_boundary");}}
    public void Dispose()
    {
        if(_disposed){Require(!_failed);return;}
        bool clean=!_failed&&(!_invoked||_complete);
        _disposed=true;
        try {try {try {_effects?.Dispose();}finally{_pickup?.Dispose();}}
            finally {_hooks.UnpatchAll(_hooks.Id);Require(!_targets.Any(m=>Harmony.GetPatchInfo(m)?.Owners.Contains(_hooks.Id)==true));}}
        catch {_failed=true;throw;}
        finally {if(clean&&!_failed&&ReferenceEquals(Active,this))Active=null;}
        Require(clean);
    }
}
