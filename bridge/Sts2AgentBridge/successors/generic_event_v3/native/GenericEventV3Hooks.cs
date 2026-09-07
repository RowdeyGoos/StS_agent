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
namespace Sts2AgentBridge.Successors.GenericEventV3.Native;

// Explicit, exclusive seven-method observational patch scope. Originals always run.
public sealed class GenericEventV3Hooks : IDisposable
{
    private const string Owner = "sts2agent.generic_event_v3";
    private static GenericEventV3Hooks? _installed;
    private static GenericEventV3Binding? _armed;
    private static readonly AsyncLocal<GenericEventV3Binding?> Dispatch = new();
    private static readonly AsyncLocal<GenericEventV3Binding?> Parent = new();
    private static readonly AsyncLocal<GenericEventV3Binding?> Request = new();
    private readonly Harmony _harmony = new(Owner);
    private readonly List<MethodInfo> _methods = new();
    private readonly Dictionary<MethodInfo,MethodInfo[]> _patchMethods = new();
    private bool _disposed;
    private bool _installationComplete;
    private readonly Action? _cleanupProbe;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    public GenericEventV3Hooks() : this(null,null) { }
    internal GenericEventV3Hooks(Action<int>? afterPatch,Action? cleanupProbe)
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
            typeof(NSimpleCardSelectScreen).GetMethod(nameof(NSimpleCardSelectScreen.Create),new[]{typeof(IReadOnlyList<CardCreationResult>),typeof(CardSelectorPrefs)})!
        };
        if (targets.Any(t => t is null || Harmony.GetPatchInfo(t)?.Owners.Count > 0))
            throw new InvalidOperationException("Hook targets unavailable or already patched.");
        string[] names = {"Chosen","Upgrade","Screen","Removal","RemovalScreen","Reward","RewardScreen"};
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
    private static MethodInfo Hook(string name) => typeof(GenericEventV3Hooks).GetMethod(name,BindingFlags.Static|BindingFlags.NonPublic)!;
    internal static void Arm(GenericEventV3Binding binding)
    {
        if (_installed is null || _installed._disposed || Environment.CurrentManagedThreadId != _installed._thread || _armed is not null)
            throw new InvalidOperationException("Generic event hook reservation unavailable.");
        _armed = binding;
    }
    internal static bool Owns(GenericEventV3Binding binding) => ReferenceEquals(_armed,binding) &&
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
    internal static void Close(GenericEventV3Binding binding)
    {
        binding.Closed = true;
        if (ReferenceEquals(_armed,binding)) _armed = null;
    }
    internal static IDisposable EnterDispatch(GenericEventV3Binding binding)
    {
        if (!Owns(binding) || Dispatch.Value is not null || Parent.Value is not null)
            throw new InvalidOperationException("Dispatch scope unavailable.");
        Dispatch.Value=binding;
        return new DispatchScope(binding);
    }
    private sealed class DispatchScope : IDisposable
    {
        private readonly GenericEventV3Binding _binding;
        internal DispatchScope(GenericEventV3Binding binding)=>_binding=binding;
        public void Dispose()
        {
            if (!ReferenceEquals(Dispatch.Value,_binding)) _binding.Failed=true;
            Dispatch.Value=null;
        }
    }
    private sealed class State
    {
        internal GenericEventV3Binding? Binding;
        internal GenericEventV3Binding? Previous;
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
            if (__1.MinSelect!=1 || __1.MaxSelect!=1 || __1.Cancelable) b.Failed=true;
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
                !b.MatchesCurrentDeck() || __0.Count is <2 or >64)
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
            else b.Screen=__result;
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
    public void Dispose()
    {
        if (_disposed) return;
        if (Environment.CurrentManagedThreadId != _thread) throw new InvalidOperationException("Hook cleanup requires owner thread.");
        if (_armed is not null) { _armed.Failed=true; _armed.Closed=true; _armed=null; }
        UnpatchOwn();
        if (HasOwnedHooks())
            throw new InvalidOperationException("Owned hooks remain installed.");
        _disposed=true;
        if (ReferenceEquals(_installed,this)) _installed=null;
    }
}
