using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using NativeHook = MegaCrit.Sts2.Core.Hooks.Hook;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// Explicit, exclusive eighteen-method observational patch scope. Originals always run.
public sealed class GenericEventV7Hooks : IDisposable
{
    private const string Owner = "sts2agent.generic_event_v7";
    private static GenericEventV7Hooks? _installed;
    private static GenericEventV7Binding? _armed;
    [ThreadStatic] private static GenericEventV7MultiUpgradeState? PreviewScope;
    private static readonly AsyncLocal<GenericEventV7Binding?> Dispatch = new();
    private static readonly AsyncLocal<GenericEventV7Binding?> Parent = new();
    private static readonly AsyncLocal<GenericEventV7Binding?> Request = new();
    private static readonly AsyncLocal<GenericEventV7TransformState.Command?> CommandScope = new();
    private static readonly AsyncLocal<GenericEventV7ItemState?> CollectionScope=new();
    private readonly Harmony _harmony = new(Owner);
    private readonly List<MethodInfo> _methods = new();
    private readonly Dictionary<MethodInfo,MethodInfo[]> _patchMethods = new();
    private bool _disposed;
    private bool _installationComplete;
    private readonly Action? _cleanupProbe;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    public GenericEventV7Hooks() : this(null,null) { }
    internal GenericEventV7Hooks(Action<int>? afterPatch,Action? cleanupProbe)
    {
        _cleanupProbe=cleanupProbe;
        if (_installed is not null) throw new InvalidOperationException("Generic event hooks already owned.");
        var targets = new[] {
            typeof(EventOption).GetMethod(nameof(EventOption.Chosen),Type.EmptyTypes)!,
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromDeckForUpgrade),new[]{typeof(Player),typeof(CardSelectorPrefs)})!,
            typeof(NDeckUpgradeSelectScreen).GetMethod(nameof(NDeckUpgradeSelectScreen.ShowScreen),new[]{typeof(IReadOnlyList<CardModel>),typeof(CardSelectorPrefs),typeof(IRunState)})!,
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromDeckForRemoval),new[]{typeof(Player),typeof(CardSelectorPrefs),typeof(Func<CardModel,bool>)})!,
            typeof(NDeckCardSelectScreen).GetMethod(nameof(NDeckCardSelectScreen.Create),new[]{typeof(IReadOnlyList<CardModel>),typeof(CardSelectorPrefs)})!,
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromSimpleGridForRewards),new[]{typeof(PlayerChoiceContext),typeof(List<CardCreationResult>),typeof(Player),typeof(CardSelectorPrefs)})!,
            typeof(NSimpleCardSelectScreen).GetMethod(nameof(NSimpleCardSelectScreen.Create),new[]{typeof(IReadOnlyList<CardCreationResult>),typeof(CardSelectorPrefs)})!,
            typeof(NDeckUpgradeSelectScreen).GetMethod("OnCardClicked",BindingFlags.Instance|BindingFlags.NonPublic,null,new[]{typeof(CardModel)},null)!,
            typeof(RunState).GetMethod(nameof(RunState.CloneCard),new[]{typeof(CardModel)})!,
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromDeckForTransformation),new[]{typeof(Player),typeof(CardSelectorPrefs),typeof(Func<CardModel,CardTransformation>)})!,
            typeof(NDeckTransformSelectScreen).GetMethod(nameof(NDeckTransformSelectScreen.ShowScreen),new[]{typeof(IReadOnlyList<CardModel>),typeof(Func<CardModel,CardTransformation>),typeof(CardSelectorPrefs)})!,
            typeof(CardCmd).GetMethod(nameof(CardCmd.Transform),new[]{typeof(IEnumerable<CardTransformation>),typeof(Rng),typeof(CardPreviewStyle)})!,
            typeof(CardTransformation).GetMethod(nameof(CardTransformation.GetReplacement),new[]{typeof(Rng)})!,
            typeof(NativeHook).GetMethod(nameof(NativeHook.ModifyCardBeingAddedToDeck),new[]{typeof(IRunState),typeof(CardModel),typeof(List<AbstractModel>).MakeByRefType()})!,
            typeof(CardPile).GetMethod(nameof(CardPile.AddInternal),new[]{typeof(CardModel),typeof(int),typeof(bool)})!,
            typeof(RewardsSet).GetMethod(nameof(RewardsSet.Offer),Type.EmptyTypes)!,
            typeof(NRewardsScreen).GetMethod(nameof(NRewardsScreen.ShowScreen),new[]{typeof(RewardsSet),typeof(bool),typeof(IRunState)})!,
            typeof(NRewardButton).GetMethod("GetReward",BindingFlags.Instance|BindingFlags.NonPublic,null,Type.EmptyTypes,null)!
        };
        if (targets.Any(t => t is null || Harmony.GetPatchInfo(t)?.Owners.Count > 0))
            throw new InvalidOperationException("Hook targets unavailable or already patched.");
        Type[] returns={typeof(Task<IEnumerable<CardModel>>),typeof(NDeckTransformSelectScreen),typeof(Task<IEnumerable<CardPileAddResult>>),typeof(CardModel),typeof(CardModel),typeof(void)};
        for(int i=9;i<15;i++)
            if(!targets[i].IsPublic||targets[i].IsStatic!=(i!=12&&i!=14)||targets[i].ReturnType!=returns[i-9]||targets[i].IsGenericMethod)
                throw new InvalidOperationException("Transformation hook signature mismatch.");
        if(!targets[15].IsPublic||targets[15].IsStatic||targets[15].ReturnType!=typeof(Task)||targets[15].IsGenericMethod||
            !targets[16].IsPublic||!targets[16].IsStatic||targets[16].ReturnType!=typeof(NRewardsScreen)||targets[16].IsGenericMethod||
            !targets[17].IsPrivate||targets[17].IsStatic||targets[17].ReturnType!=typeof(Task)||targets[17].IsGenericMethod)
            throw new InvalidOperationException("Item hook signature mismatch.");
        string[] names = {"Chosen","Upgrade","Screen","Removal","RemovalScreen","Reward","RewardScreen","MultiClick","Clone","TransformRequest","TransformScreen","TransformCommand","TransformChoice","TransformModify","TransformInsert","ItemOffer","ItemScreen","ItemCollection"};
        _installed=this;
        try
        {
            for (int i=0;i<targets.Length;i++)
            {
                _methods.Add(targets[i]);
                var methods=new[]{Hook(names[i]+"Prefix"),Hook(names[i]+"Postfix"),Hook(names[i]+"Finalizer")};
                _patchMethods.Add(targets[i],methods);
                _harmony.Patch(targets[i],new HarmonyMethod(methods[0]),new HarmonyMethod(methods[1]),finalizer:new HarmonyMethod(methods[2]));
                afterPatch?.Invoke(i+1);
            }
            _installationComplete=true;
        }
        catch(Exception installationError)
        {
            try
            {
                UnpatchOwn();
                if (!HasOwnedHooks()) _installed=null;
            }
            catch(Exception cleanupError)
            {
                throw new AggregateException("Installation failed with retained hooks; call RecoverFailedInstallation on the owner thread.",installationError,cleanupError);
            }
            throw;
        }
    }
    // A constructor that could not roll back cannot return its lease. Expose
    // only that failed-installation lease for explicit, retryable cleanup.
    public static void RecoverFailedInstallation()
    {
        var failed=_installed;
        if(failed is null)return;
        if(failed._installationComplete)throw new InvalidOperationException("An active successful hook lease owns cleanup.");
        failed.Dispose();
    }
    private static MethodInfo Hook(string name) => typeof(GenericEventV7Hooks).GetMethod(name,BindingFlags.Static|BindingFlags.NonPublic)!;
    internal static void Arm(GenericEventV7Binding binding)
    {
        if (_installed is null || _installed._disposed || Environment.CurrentManagedThreadId != _installed._thread || _armed is not null)
            throw new InvalidOperationException("Generic event hook reservation unavailable.");
        _armed = binding;
    }
    internal static bool Owns(GenericEventV7Binding binding) => ReferenceEquals(_armed,binding) &&
        _installed is not null && !_installed._disposed && Environment.CurrentManagedThreadId==_installed._thread && _installed.ExactPatches();
    private bool ExactPatches() => _methods.All(method =>
    {
        var info=Harmony.GetPatchInfo(method);var hooks=_patchMethods[method];
        return info is not null && info.Prefixes.Count==1 && info.Postfixes.Count==1 &&
            info.Finalizers.Count==1 && info.Transpilers.Count==0 &&
            info.Prefixes[0].owner==Owner && info.Prefixes[0].PatchMethod==hooks[0] &&
            info.Postfixes[0].owner==Owner && info.Postfixes[0].PatchMethod==hooks[1] &&
            info.Finalizers[0].owner==Owner && info.Finalizers[0].PatchMethod==hooks[2];
    });
    private bool HasOwnedHooks()=>_methods.Any(method=>AllPatches(method).Any(p=>
        p.owner==Owner && _patchMethods[method].Contains(p.PatchMethod)));
    private static IEnumerable<HarmonyLib.Patch> AllPatches(MethodInfo method)
    {
        var info=Harmony.GetPatchInfo(method);
        return info is null ? Array.Empty<HarmonyLib.Patch>() : info.Prefixes.Concat(info.Postfixes).Concat(info.Finalizers).Concat(info.Transpilers);
    }
    private void UnpatchOwn()
    {
        _cleanupProbe?.Invoke();
        if(_methods.Any(method=>AllPatches(method).Any(p=>p.owner!=Owner && _patchMethods[method].Contains(p.PatchMethod))))
            throw new InvalidOperationException("Foreign owner reused an owned hook; retain ownership for cleanup.");
        foreach(var method in _methods)
            foreach(var patch in _patchMethods[method]) _harmony.Unpatch(method,patch);
    }
    internal static void Close(GenericEventV7Binding binding)
    {
        binding.Closed = true;
        binding.MultiUpgrade?.Close();
        binding.Transform?.Close();
        if(binding.Item is {} item)item.Closed=true;
        if (ReferenceEquals(_armed,binding)) _armed = null;
    }
    internal static IDisposable EnterDispatch(GenericEventV7Binding binding)
    {
        if (!Owns(binding) || Dispatch.Value is not null || Parent.Value is not null)
            throw new InvalidOperationException("Dispatch scope unavailable.");
        Dispatch.Value=binding;
        return new DispatchScope(binding);
    }
    private sealed class DispatchScope : IDisposable
    {
        private readonly GenericEventV7Binding _binding;
        internal DispatchScope(GenericEventV7Binding binding)=>_binding=binding;

    public void Dispose()
        {
            if (!ReferenceEquals(Dispatch.Value,_binding)) _binding.Failed=true;
            Dispatch.Value=null;
        }
    }
    private sealed class State
    {
        internal GenericEventV7Binding? Binding;
        internal GenericEventV7Binding? Previous;
        internal bool Restored;
    }
    private static void ChosenPrefix(EventOption __instance, out State __state)
    {
        __state = new State {Previous=Parent.Value};
        var binding = Parent.Value ?? Dispatch.Value;
        if (binding is null) { if (_armed is not null) _armed.Failed=true; return; }
        __state.Binding = binding;
        try
        {
            if (!Owns(binding) || binding.Closed || binding.ChosenSeen || !ReferenceEquals(__instance,binding.Option))
            { binding.Failed = true; return; }
            binding.ChosenSeen = true; Parent.Value = binding;
        }
        catch { binding.Failed=true; }
    }
    private static void ChosenPostfix(Task __result, State? __state)
    {
        if (__state?.Binding is { } b && !b.Failed)
        { if (__result is null || b.ChosenTask is not null) b.Failed=true; else b.ChosenTask=__result; }
        RestoreParent(__state);
    }
    private static void ChosenFinalizer(Exception? __exception, State? __state)
    { if (__exception is not null && __state?.Binding is { } b) b.Failed=true; RestoreParent(__state); }
    private static void RestoreParent(State? state)
    { if (state is not null && !state.Restored) { Parent.Value=state.Previous; state.Restored=true; } }
    // A stale captured invocation must invalidate the active generation too;
    // it cannot silently operate alongside a newly armed item child.
    private static void FailItem(GenericEventV7Binding? binding)
    {
        if(binding is not null)binding.Failed=true;
        if(_armed is not null&&!ReferenceEquals(_armed,binding))_armed.Failed=true;
    }
    internal static IDisposable EnterItemCollection(GenericEventV7ItemState item)
    {
        if(!item.Context()||CollectionScope.Value is not null||!item.Dispatched||item.CollectionEntered)
            throw new InvalidOperationException("Collection scope unavailable.");
        CollectionScope.Value=item;return new ItemScope(item);
    }
    private sealed class ItemScope : IDisposable
    {
        private readonly GenericEventV7ItemState _item;
        internal ItemScope(GenericEventV7ItemState item)=>_item=item;
        public void Dispose(){if(!ReferenceEquals(CollectionScope.Value,_item))FailItem(_item.Binding);CollectionScope.Value=null;}
    }
    private static void ItemOfferPrefix(RewardsSet __instance,out State __state)
    {
        var b=Parent.Value;__state=new State{Binding=b,Previous=Request.Value};
        if(b is null){FailItem(null);return;}
        try
        {
            if(!Owns(b)||b.Closed||b.RequestSeen||Request.Value is not null||!b.ContextValid(false)||
                !ReferenceEquals(__instance.Player,b.Player)||RewardsSet.testSelector is not null)
            {FailItem(b);return;}
            b.RequestSeen=true;b.Item=new GenericEventV7ItemState(b,__instance);Request.Value=b;
        }
        catch{FailItem(b);}
    }
    private static void ItemOfferPostfix(Task __result,State? __state)
    {
        if(__state?.Binding is {} b&&!b.Failed)
        {if(b.Item is not {} item||item.OfferTask is not null||__result is null)FailItem(b);else item.OfferTask=__result;}
        RestoreRequest(__state);
    }
    private static void ItemOfferFinalizer(Exception? __exception,State? __state)
    {if(__exception is not null&&__state?.Binding is {} b)FailItem(b);RestoreRequest(__state);}
    private static void ItemScreenPrefix(RewardsSet __0,bool __1,IRunState __2,out State __state)
    {
        var b=Request.Value;__state=new State{Binding=b};
        if(b is null){FailItem(null);return;}
        try
        {
            if(!Owns(b)||b.Closed||!ReferenceEquals(Parent.Value,b)||b.Item is not {} item||b.ScreenSeen||item.ScreenEntered||
                !ReferenceEquals(item.Set,__0)||__1||!ReferenceEquals(__2,b.RunState)||!item.BindDomain())
            {FailItem(b);return;}
            item.ScreenEntered=true;b.ScreenSeen=true;
        }
        catch{FailItem(b);}
    }
    private static void ItemScreenPostfix(NRewardsScreen __result,State? __state)
    {
        if(__state?.Binding is not {} b||b.Failed)return;
        try
        {
            if(b.Item is not {} item||!item.ScreenEntered||item.Screen is not null||__result is null||
                __result.GetType()!=typeof(NRewardsScreen)||!Godot.GodotObject.IsInstanceValid(__result)||!item.Domain())FailItem(b);
            else item.Screen=__result;
        }
        catch{FailItem(b);}
    }
    private static void ItemScreenFinalizer(Exception? __exception,State? __state)
    {if(__exception is not null&&__state?.Binding is {} b)FailItem(b);}
    private static void ItemCollectionPrefix(NRewardButton __instance,out State __state)
    {
        var item=CollectionScope.Value;__state=new State{Binding=item?.Binding};
        if(item is null){FailItem(null);return;}
        try
        {
            if(!item.Domain()||!item.Dispatched||item.CollectionEntered||!ReferenceEquals(item.Button,__instance))
            {FailItem(item.Binding);return;}
            item.CollectionEntered=true;
        }
        catch{FailItem(item.Binding);}
    }
    private static void ItemCollectionPostfix(Task __result,State? __state)
    {
        if(__state?.Binding is {} b&&!b.Failed)
        {if(b.Item is not {} item||!item.CollectionEntered||item.CollectionTask is not null||__result is null)FailItem(b);else item.CollectionTask=__result;}
    }
    private static void ItemCollectionFinalizer(Exception? __exception,State? __state)
    {if(__exception is not null&&__state?.Binding is {} b)FailItem(b);}
    private static void UpgradePrefix(Player __0, CardSelectorPrefs __1, out State __state)
    {
        __state = new State {Previous=Request.Value};
        var b = Parent.Value;
        if (b is null) { if (_armed is not null) _armed.Failed=true; return; }
        __state.Binding=b;
        try
        {
            if (!Owns(b) || b.Closed || b.RequestSeen || !ReferenceEquals(__0,b.Player) || !b.ContextValid(false))
            { b.Failed=true; return; }
            b.RequestSeen=true; b.Prefs=__1; b.Operation=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Upgrade;
            if (__1.MinSelect<1 || __1.MinSelect!=__1.MaxSelect || __1.MaxSelect>8 || __1.Cancelable) b.Failed=true;
            Request.Value=b;
        }
        catch { b.Failed=true; }
    }
    private static void UpgradePostfix(Task<IEnumerable<CardModel>> __result, State? __state)
    {
        if (__state?.Binding is { } b && !b.Failed)
        { if (__result is null || b.RequestTask is not null) b.Failed=true; else b.RequestTask=__result; }
        RestoreRequest(__state);
    }
    private static void UpgradeFinalizer(Exception? __exception, State? __state)
    { if (__exception is not null && __state?.Binding is { } b) b.Failed=true; RestoreRequest(__state); }
    private static void RestoreRequest(State? state)
    { if (state is not null && !state.Restored) { Request.Value=state.Previous; state.Restored=true; } }
    private static void ScreenPrefix(IReadOnlyList<CardModel> __0, CardSelectorPrefs __1, IRunState __2, out State __state)
    {
        __state=new State {Binding=Request.Value};
        var b = Request.Value;
        if (b is null) { if (_armed is not null) _armed.Failed=true; return; }
        try
        {
            if (!Owns(b) || b.Closed || b.ScreenSeen || !b.ContextValid(false) ||
                b.Operation!=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Upgrade || !ReferenceEquals(Parent.Value,b) ||
                !ReferenceEquals(__2,b.RunState) || !b.SamePrefs(__1) ||
                !b.MatchesCurrentDeck() || __0.Count<=b.Prefs.MaxSelect || __0.Count>64 ||
                (b.Prefs.MaxSelect>1 && __2.GetType()!=typeof(RunState)))
            { b.Failed=true; return; }
            b.ScreenSeen=true;
            var originals=new CardModel[__0.Count];
            for(int i=0;i<originals.Length;i++) originals[i]=__0[i];
            if (originals.Any(c=>c is null || !c.IsUpgradable) ||
                originals.Distinct(ReferenceEqualityComparer.Instance).Count()!=originals.Length ||
                originals.Any(c=>!b.PreDispatchDeck.Any(d=>ReferenceEquals(d.ModelIdentity,c))))
            { b.Failed=true; return; }
            b.Originals=originals;
        }
        catch { b.Failed=true; }
    }
    private static void ScreenPostfix(NDeckUpgradeSelectScreen __result, State? __state)
    {
        if (__state?.Binding is { } b && !b.Failed)
        {
            if (__result is null || b.Screen is not null || __result.GetType()!=typeof(NDeckUpgradeSelectScreen)) b.Failed=true;
            else {b.Screen=__result;if(b.Prefs.MaxSelect>1)b.MultiUpgrade=new GenericEventV7MultiUpgradeState(b);}
        }
    }
    private static void ScreenFinalizer(Exception? __exception, State? __state)
    { if (__exception is not null && __state?.Binding is { } b) b.Failed=true; }
    private static void RemovalPrefix(Player __0, CardSelectorPrefs __1, Func<CardModel,bool>? __2, out State __state)
    {
        __state=new State {Previous=Request.Value};
        var b=Parent.Value;
        if(b is null) {if(_armed is not null)_armed.Failed=true;return;}
        __state.Binding=b;
        try
        {
            if(!Owns(b)||b.Closed||b.RequestSeen||!ReferenceEquals(__0,b.Player)||!b.ContextValid(false))
            {b.Failed=true;return;}
            b.RequestSeen=true;b.Prefs=__1;b.RemovalPredicate=__2;
            b.Operation=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Remove;
            if(__1.Cancelable||__1.MinSelect<1||__1.MinSelect>__1.MaxSelect||__1.MaxSelect>8)b.Failed=true;
            Request.Value=b;
        }
        catch {b.Failed=true;}
    }
    private static void RemovalPostfix(Task<IEnumerable<CardModel>> __result,State? __state)=>UpgradePostfix(__result,__state);
    private static void RemovalFinalizer(Exception? __exception,State? __state)=>UpgradeFinalizer(__exception,__state);
    private static void RemovalScreenPrefix(IReadOnlyList<CardModel> __0,CardSelectorPrefs __1,out State __state)
    {
        __state=new State {Binding=Request.Value};var b=Request.Value;
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        try
        {
            if(!Owns(b)||b.Closed||b.ScreenSeen||!ReferenceEquals(Parent.Value,b)||!b.ContextValid(false)||
                b.Operation!=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Remove||
                !b.SamePrefs(__1)||!b.MatchesCurrentDeck()||__0.Count<=b.Prefs.MaxSelect||__0.Count>64)
            {b.Failed=true;return;}
            b.ScreenSeen=true;
            var originals=new CardModel[__0.Count];for(int i=0;i<originals.Length;i++)originals[i]=__0[i];
            if(originals.Any(c=>c is null||!c.IsRemovable)||originals.Distinct(ReferenceEqualityComparer.Instance).Count()!=originals.Length||
                originals.Any(c=>!b.PreDispatchDeck.Any(d=>ReferenceEquals(d.ModelIdentity,c))))
            {b.Failed=true;return;}
            b.Originals=originals;
        }
        catch {b.Failed=true;}
    }
    private static void RemovalScreenPostfix(NDeckCardSelectScreen __result,State? __state)
    {
        if(__state?.Binding is not { } b||b.Failed)return;
        try
        {
            if(__result is null||b.Screen is not null||__result.GetType()!=typeof(NDeckCardSelectScreen)||
                !b.ContextValid(false)||!b.MatchesCurrentDeck())b.Failed=true;
            else b.Screen=__result;
        }
        catch {b.Failed=true;}
    }
    private static void RemovalScreenFinalizer(Exception? __exception,State? __state)=>ScreenFinalizer(__exception,__state);
    private static void RewardPrefix(PlayerChoiceContext __0,List<CardCreationResult> __1,Player __2,CardSelectorPrefs __3,out State __state)
    {
        __state=new State {Previous=Request.Value};var b=Parent.Value;
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        __state.Binding=b;
        try
        {
            if(!Owns(b)||b.Closed||b.RequestSeen||__0 is null||__1 is null||!ReferenceEquals(__2,b.Player)||!b.ContextValid(false)||!b.MatchesCurrentDeck())
            {b.Failed=true;return;}
            b.RequestSeen=true;b.Prefs=__3;b.RewardContext=__0;
            b.Operation=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Add;
            if(__3.Cancelable||__3.MinSelect<1||__3.MinSelect>__3.MaxSelect||__3.MaxSelect>8||!b.CaptureOffers(__1))b.Failed=true;
            Request.Value=b;
        }
        catch {b.Failed=true;}
    }
    private static void RewardPostfix(Task<IEnumerable<CardModel>> __result,State? __state)=>UpgradePostfix(__result,__state);
    private static void RewardFinalizer(Exception? __exception,State? __state)=>UpgradeFinalizer(__exception,__state);
    private static void RewardScreenPrefix(IReadOnlyList<CardCreationResult> __0,CardSelectorPrefs __1,out State __state)
    {
        __state=new State {Binding=Request.Value};var b=Request.Value;
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        try
        {
            if(!Owns(b)||b.Closed||b.ScreenSeen||!ReferenceEquals(Parent.Value,b)||!b.ContextValid(false)||
                b.Operation!=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Add||
                !ReferenceEquals(__0,b.RewardList)||!b.MatchesOffers()||!b.SamePrefs(__1)||!b.MatchesCurrentDeck())
            {b.Failed=true;return;}
            b.ScreenSeen=true;
        }
        catch {b.Failed=true;}
    }
    private static void RewardScreenPostfix(NSimpleCardSelectScreen __result,State? __state)
    {
        if(__state?.Binding is not { } b||b.Failed)return;
        try
        {
            if(__result is null||b.Screen is not null||__result.GetType()!=typeof(NSimpleCardSelectScreen)||
                !b.ContextValid(false)||!b.MatchesCurrentDeck()||!b.MatchesOffers())b.Failed=true;
            else b.Screen=__result;
        }
        catch {b.Failed=true;}
    }
    private static void RewardScreenFinalizer(Exception? __exception,State? __state)=>ScreenFinalizer(__exception,__state);
    private sealed class PreviewState
    {
        internal GenericEventV7MultiUpgradeState? Current,Previous;
        internal bool Entered,Restored;
    }
    private static void MultiClickPrefix(NDeckUpgradeSelectScreen __instance,CardModel __0,out PreviewState __state)
    {
        __state=new PreviewState {Previous=PreviewScope};
        var multi=_armed?.MultiUpgrade;
        if(multi is null)return;
        __state.Current=multi;
        try
        {
            if(PreviewScope is not null||!multi.Begin(__instance,__0)){multi.Fail();return;}
            __state.Entered=true;PreviewScope=multi;
        }
        catch {multi.Fail();}
    }
    private static void MultiClickPostfix(PreviewState? __state)=>EndPreview(__state,false);
    private static void MultiClickFinalizer(Exception? __exception,PreviewState? __state)=>EndPreview(__state,__exception is not null);
    private static void EndPreview(PreviewState? state,bool faulted)
    {
        if(state is null)return;
        if(state.Restored){if(faulted)state.Current?.Fail();return;}
        try {if(state.Entered)state.Current!.End(faulted);else if(faulted)state.Current?.Fail();}
        catch {state.Current?.Fail();}
        finally {PreviewScope=state.Previous;state.Restored=true;}
    }
    private sealed class CloneState
    {
        internal GenericEventV7MultiUpgradeState? Current;
        internal CardModel? Original;
        internal bool Entered;
    }
    private static void ClonePrefix(RunState __instance,CardModel __0,out CloneState __state)
    {
        __state=new CloneState {Current=PreviewScope,Original=__0};
        if(__state.Current is not { } multi)return;
        try {__state.Entered=multi.CloneEntry(__instance,__0);}
        catch {multi.Fail();}
    }
    private static void ClonePostfix(CardModel __result,CloneState? __state)
    {
        if(__state is not {Entered:true,Current:{ } multi})return;
        try {multi.CloneExit(__state.Original!,__result);}catch{multi.Fail();}
    }
    private static void CloneFinalizer(Exception? __exception,CloneState? __state)
    {if(__exception is not null)__state?.Current?.Fail();}

    private static void TransformRequestPrefix(Player __0,CardSelectorPrefs __1,Func<CardModel,CardTransformation>? __2,out State __state)
    {
        __state=new State {Previous=Request.Value};var b=Parent.Value;
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        __state.Binding=b;
        try
        {
            if(!Owns(b)||b.Closed||b.RequestSeen||!ReferenceEquals(__0,b.Player)||!b.ContextValid(false)||!b.MatchesCurrentDeck())
            {b.Failed=true;return;}
            b.RequestSeen=true;b.Prefs=__1;b.TransformFunction=__2;
            b.Operation=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Transform;
            if(__1.Cancelable||__1.MinSelect<1||__1.MinSelect>__1.MaxSelect||__1.MaxSelect>8||(__1.MinSelect<__1.MaxSelect&&!__1.RequireManualConfirmation))b.Failed=true;
            Request.Value=b;
        }
        catch{b.Failed=true;}
    }
    private static void TransformRequestPostfix(Task<IEnumerable<CardModel>> __result,State? __state)=>UpgradePostfix(__result,__state);
    private static void TransformRequestFinalizer(Exception? __exception,State? __state)=>UpgradeFinalizer(__exception,__state);
    private static void TransformScreenPrefix(IReadOnlyList<CardModel> __0,Func<CardModel,CardTransformation> __1,CardSelectorPrefs __2,out State __state)
    {
        __state=new State {Binding=Request.Value};var b=Request.Value;
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        try
        {
            if(!Owns(b)||b.Closed||b.ScreenSeen||!ReferenceEquals(Parent.Value,b)||!b.ContextValid(false)||
                b.Operation!=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Transform||
                !b.SamePrefs(__2)||!b.MatchesCurrentDeck()||__0.Count<=b.Prefs.MaxSelect||__0.Count>64||__1 is null||
                (b.TransformFunction is not null&&!ReferenceEquals(__1,b.TransformFunction)))
            {b.Failed=true;return;}
            b.ScreenSeen=true;
            var originals=new CardModel[__0.Count];for(int i=0;i<originals.Length;i++)originals[i]=__0[i];
            var eligible=b.PreDispatchDeck.Select(d=>(CardModel)d.ModelIdentity).Where(c=>(int)c.Type!=6&&c.IsTransformable).ToArray();
            if(originals.Length!=eligible.Length||originals.Where((c,i)=>c is null||!ReferenceEquals(c,eligible[i])||
                !ReferenceEquals(c.Owner,b.Player)||!ReferenceEquals(c.RunState,b.RunState)).Any())
            {b.Failed=true;return;}
            b.Originals=originals;b.EffectiveTransformFunction=__1;
        }
        catch{b.Failed=true;}
    }
    private static void TransformScreenPostfix(NDeckTransformSelectScreen __result,State? __state)
    {
        if(__state?.Binding is not { } b||b.Failed)return;
        try
        {
            if(__result is null||b.Screen is not null||__result.GetType()!=typeof(NDeckTransformSelectScreen)||!b.ContextValid(false)||!b.MatchesCurrentDeck())b.Failed=true;
            else{b.Screen=__result;b.Transform=new GenericEventV7TransformState(b);}
        }
        catch{b.Failed=true;}
    }
    private static void TransformScreenFinalizer(Exception? __exception,State? __state)=>ScreenFinalizer(__exception,__state);
    private sealed class CommandObservation
    {
        internal GenericEventV7TransformState? Owner;
        internal GenericEventV7TransformState.Command? Current,Previous;
        internal bool Restored;
    }
    private static void TransformCommandPrefix(out CommandObservation __state)
    {
        __state=new CommandObservation {Previous=CommandScope.Value};var b=Parent.Value;
        var owner=b?.Transform??_armed?.Transform;
        if(owner is null)return;
        __state.Owner=owner;
        try
        {
            if(b?.Transform!=owner||CommandScope.Value is not null||!owner.Authorized){owner.Fail();return;}
            __state.Current=owner.Begin();CommandScope.Value=__state.Current;
        }
        catch{owner.Fail();}
    }
    private static void TransformCommandPostfix(Task<IEnumerable<CardPileAddResult>> __result,CommandObservation? __state)
    {
        try{if(__state?.Current is { } c)__state.Owner!.BindTask(c,__result);}
        catch{__state?.Owner?.Fail();}
        finally{RestoreCommand(__state);}
    }
    private static void TransformCommandFinalizer(Exception? __exception,CommandObservation? __state)
    {if(__exception is not null)__state?.Owner?.Fail();RestoreCommand(__state);}
    private static void RestoreCommand(CommandObservation? state)
    {if(state is not null&&!state.Restored){CommandScope.Value=state.Previous;state.Restored=true;}}
    private sealed class TransformObservation
    {
        internal GenericEventV7TransformState? Owner;
        internal GenericEventV7TransformState.Command? Command;
        internal CardModel? Original;
        internal GenericEventV7TransformState.Choice? Choice;
    }
    private static TransformObservation ObserveTransform()
    {
        var c=CommandScope.Value;var owner=c?.Owner??_armed?.Transform;
        // Other generic families keep ordinary native behavior.
        if(owner is null)return new TransformObservation();
        if(c is null){if(owner.Authorized)owner.Fail();return new TransformObservation {Owner=owner};}
        return new TransformObservation {Owner=owner,Command=c};
    }
    private static void TransformChoicePrefix(CardTransformation __instance,out TransformObservation __state)
    {
        __state=ObserveTransform();if(__state.Command is not { } c)return;
        try{__state.Original=__state.Owner!.ChoiceEntry(c,__instance);}catch{__state.Owner!.Fail();}
    }
    private static void TransformChoicePostfix(CardModel __result,TransformObservation? __state)
    {if(__state?.Command is not { } c||__state.Original is null)return;try{__state.Owner!.ChoiceExit(c,__state.Original,__result);}catch{__state.Owner!.Fail();}}
    private static void TransformChoiceFinalizer(Exception? __exception,TransformObservation? __state)
    {if(__exception is not null)__state?.Owner?.Fail();}
    private static void TransformModifyPrefix(IRunState __0,CardModel __1,out TransformObservation __state)
    {
        __state=ObserveTransform();if(__state.Command is not { } c)return;
        try{__state.Choice=__state.Owner!.ModifyEntry(c,__0,__1);}catch{__state.Owner!.Fail();}
    }
    private static void TransformModifyPostfix(CardModel __result,TransformObservation? __state)
    {if(__state?.Command is not { } c||__state.Choice is null)return;try{__state.Owner!.ModifyExit(c,__state.Choice,__result);}catch{__state.Owner!.Fail();}}
    private static void TransformModifyFinalizer(Exception? __exception,TransformObservation? __state)=>TransformChoiceFinalizer(__exception,__state);
    private static void TransformInsertPrefix(CardPile __instance,CardModel __0,int __1,bool __2,out TransformObservation __state)
    {
        __state=ObserveTransform();if(__state.Command is not { } c)return;
        try{__state.Choice=__state.Owner!.InsertionEntry(c,__instance,__0,__1,__2);}catch{__state.Owner!.Fail();}
    }
    private static void TransformInsertPostfix(TransformObservation? __state)
    {if(__state?.Command is not { } c||__state.Choice is null)return;try{__state.Owner!.InsertionExit(c,__state.Choice);}catch{__state.Owner!.Fail();}}
    private static void TransformInsertFinalizer(Exception? __exception,TransformObservation? __state)=>TransformChoiceFinalizer(__exception,__state);
    public void Dispose()
    {
        if (_disposed) return;
        if (Environment.CurrentManagedThreadId != _thread) throw new InvalidOperationException("Hook cleanup requires owner thread.");
        if (_armed is not null) { _armed.Failed=true; _armed.Closed=true; _armed.MultiUpgrade?.Close(); _armed.Transform?.Close(); _armed=null; }
        UnpatchOwn();
        if (HasOwnedHooks())
            throw new InvalidOperationException("Owned hooks remain installed.");
        _disposed=true;
        if (ReferenceEquals(_installed,this)) _installed=null;
    }
}
