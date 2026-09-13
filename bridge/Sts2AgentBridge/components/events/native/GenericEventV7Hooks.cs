using G = Sts2AgentBridge.Successors.GenericEventReleaseV5.GenericEventDiagnosticCode;
using D = Sts2AgentBridge.Successors.GenericEventV7.GenericEventV7ResumeDiagnostic;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
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
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using NativeHook = MegaCrit.Sts2.Core.Hooks.Hook;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// Explicit, exclusive observational patch scope. Originals always run.
public sealed class GenericEventV7Hooks : IDisposable
{
    private const string Owner = "sts2agent.generic_event_v7";
    private static GenericEventV7Hooks? _installed;
    private static GenericEventV7Binding? _armed;
    [ThreadStatic] private static GenericEventV7MultiUpgradeState? PreviewScope;
    internal static readonly AsyncLocal<GenericEventV7SphereSession?> SphereClick=new();
    private static readonly AsyncLocal<GenericEventV7Binding?> Dispatch = new();
    private static readonly AsyncLocal<GenericEventV7Binding?> Parent = new();
    private static readonly AsyncLocal<GenericEventV7Binding?> Request = new();
    private static readonly AsyncLocal<GenericEventV7TransformState.Command?> CommandScope = new();
    private static readonly AsyncLocal<GenericEventV7ItemState?> CollectionScope=new();
    private readonly Harmony _harmony = new(Owner);
    private readonly List<MethodInfo> _methods = new();
    private readonly Dictionary<MethodInfo,MethodInfo[]> _patchMethods = new();
    private GenericEventV7CombatHandoff? _resume;
    private readonly HashSet<MethodInfo> _resumeItems=new();
    private bool _disposed;
    private bool _installationComplete;
    private readonly Action? _cleanupProbe;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private MethodInfo[] _targets=Array.Empty<MethodInfo>();
    private string[] _names=Array.Empty<string>();
    private int _nextPatch;
    private readonly Action<int>? _afterPatch;
    private bool _installationFailed;
    public GenericEventV7Hooks() : this(null,null) { }
    private readonly Action<int>? _readStage;
    public GenericEventV7Hooks(bool incremental,Action<int>? readStage=null) : this(null,null,incremental,readStage) { }
    internal GenericEventV7Hooks(Action<int>? afterPatch,Action? cleanupProbe,bool incremental=false,Action<int>? readStage=null)
    {
        _readStage=readStage;_readStage?.Invoke(6);
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
            typeof(NRewardButton).GetMethod("GetReward",BindingFlags.Instance|BindingFlags.NonPublic,null,Type.EmptyTypes,null)!,
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromDeckForEnchantment),new[]{typeof(IReadOnlyList<CardModel>),typeof(EnchantmentModel),typeof(int),typeof(CardSelectorPrefs)})!,
            typeof(NDeckEnchantSelectScreen).GetMethod(nameof(NDeckEnchantSelectScreen.ShowScreen),new[]{typeof(IReadOnlyList<CardModel>),typeof(EnchantmentModel),typeof(int),typeof(CardSelectorPrefs)})!,
            typeof(NCardRewardSelectionScreen).GetMethod(nameof(NCardRewardSelectionScreen.ShowScreen),new[]{typeof(IReadOnlyList<CardCreationResult>),typeof(IReadOnlyList<CardRewardAlternative>)})!,
            typeof(NCardRewardSelectionScreen).GetMethod(nameof(NCardRewardSelectionScreen.OptionSelected),Type.EmptyTypes)!,
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromDeckGeneric),new[]{typeof(Player),typeof(CardSelectorPrefs),typeof(Func<CardModel,bool>),typeof(Func<CardModel,int>)})!,
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromChooseACardScreen),new[]{typeof(PlayerChoiceContext),typeof(IReadOnlyList<CardModel>),typeof(Player),typeof(bool)})!,
            typeof(NChooseACardSelectionScreen).GetMethod(nameof(NChooseACardSelectionScreen.ShowScreen),new[]{typeof(IReadOnlyList<CardModel>),typeof(bool)})!,
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromChooseABundleScreen),new[]{typeof(Player),typeof(IReadOnlyList<IReadOnlyList<CardModel>>)})!,
            typeof(NChooseABundleSelectionScreen).GetMethod(nameof(NChooseABundleSelectionScreen.ShowScreen),new[]{typeof(IReadOnlyList<IReadOnlyList<CardModel>>)})!,
            typeof(NSimpleCardsViewScreen).GetMethod(nameof(NSimpleCardsViewScreen.ShowScreen),new[]{typeof(List<CardPileAddResult>),typeof(MegaCrit.Sts2.Core.Localization.LocString)})!,
            typeof(EventModel).GetMethod("EnterCombatWithoutExitingEvent",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,null,new[]{typeof(EncounterModel),typeof(IReadOnlyList<Reward>),typeof(bool)},null)!,
            typeof(MegaCrit.Sts2.Core.Nodes.Events.Custom.CrystalSphere.NCrystalSphereScreen).GetMethod("ShowScreen")!,
            typeof(CardPileCmd).GetMethod("AddCursesToDeck")!,
            typeof(NAbandonRunConfirmPopup).GetMethod("Create",new[]{typeof(MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu)})!,
            typeof(RunManager).GetMethod("AbandonInternal",BindingFlags.Instance|BindingFlags.NonPublic,null,Type.EmptyTypes,null)!,
            typeof(MegaCrit.Sts2.Core.Multiplayer.Game.ActChangeSynchronizer).GetMethod("SetLocalPlayerReady",Type.EmptyTypes)!
        };
        _readStage?.Invoke(7);
        if (targets.Any(t => t is null || Harmony.GetPatchInfo(t)?.Owners.Count > 0))
            throw new InvalidOperationException("Hook targets unavailable or already patched.");
        if(!targets[31].IsPublic||!targets[31].IsStatic||targets[31].IsGenericMethod||targets[31].ReturnType!=typeof(NAbandonRunConfirmPopup)||
            !targets[32].IsPrivate||targets[32].IsStatic||targets[32].IsGenericMethod||targets[32].ReturnType!=typeof(Task))throw new InvalidOperationException("Abandon popup signature mismatch.");
        if(targets[28].IsStatic||targets[28].IsGenericMethod||targets[28].ReturnType!=typeof(void))throw new InvalidOperationException("Combat entry signature mismatch.");
        if(!targets[27].IsPublic||!targets[27].IsStatic||targets[27].IsGenericMethod||targets[27].ReturnType!=typeof(NCardsViewScreen))throw new InvalidOperationException("Results screen signature mismatch.");
        Type[] offerReturns={typeof(Task<CardModel>),typeof(NChooseACardSelectionScreen),typeof(Task<IEnumerable<CardModel>>),typeof(NChooseABundleSelectionScreen)};
        for(int i=23;i<27;i++)
            if(!targets[i].IsPublic||!targets[i].IsStatic||targets[i].IsGenericMethod||targets[i].ReturnType!=offerReturns[i-23])
                throw new InvalidOperationException("Card offer hook signature mismatch.");
        Type[] returns={typeof(Task<IEnumerable<CardModel>>),typeof(NDeckTransformSelectScreen),typeof(Task<IEnumerable<CardPileAddResult>>),typeof(CardModel),typeof(CardModel),typeof(void)};
        for(int i=9;i<15;i++)
            if(!targets[i].IsPublic||targets[i].IsStatic!=(i!=12&&i!=14)||targets[i].ReturnType!=returns[i-9]||targets[i].IsGenericMethod)
                throw new InvalidOperationException("Transformation hook signature mismatch.");
        if(!targets[15].IsPublic||targets[15].IsStatic||targets[15].ReturnType!=typeof(Task)||targets[15].IsGenericMethod||
            !targets[16].IsPublic||!targets[16].IsStatic||targets[16].ReturnType!=typeof(NRewardsScreen)||targets[16].IsGenericMethod||
            !targets[17].IsPrivate||targets[17].IsStatic||targets[17].ReturnType!=typeof(Task)||targets[17].IsGenericMethod)
            throw new InvalidOperationException("Item hook signature mismatch.");
        if (!targets[18].IsPublic || !targets[18].IsStatic || targets[18].IsGenericMethod || targets[18].ReturnType != typeof(Task<IEnumerable<CardModel>>) ||
            !targets[19].IsPublic || !targets[19].IsStatic || targets[19].IsGenericMethod || targets[19].ReturnType != typeof(NDeckEnchantSelectScreen))
            throw new InvalidOperationException("Enchantment hook signature mismatch.");
        if(!targets[20].IsStatic||!targets[20].IsPublic||targets[20].ReturnType!=typeof(NCardRewardSelectionScreen)||
            targets[21].IsStatic||!targets[21].IsPublic||targets[21].ReturnType!=typeof(Task<int?>))throw new InvalidOperationException("Card reward hook signature mismatch.");
        if(!targets[22].IsStatic||!targets[22].IsPublic||targets[22].IsGenericMethod||targets[22].ReturnType!=typeof(Task<IEnumerable<CardModel>>))
            throw new InvalidOperationException("Generic deck hook signature mismatch.");
        string[] names = {"Chosen","Upgrade","Screen","Removal","RemovalScreen","Reward","RewardScreen","MultiClick","Clone","TransformRequest","TransformScreen","TransformCommand","TransformChoice","TransformModify","TransformInsert","ItemOffer","ItemScreen","ItemCollection","EnchantRequest","EnchantScreen","CardMenu","CardMenuTask","GenericDeck","OfferRequest","OfferScreen","BundleRequest","BundleScreen","ResultsScreen","CombatEntry","SphereScreen","SphereCurse","AbandonPopup","AbandonTask","ActReady"};
        _targets=targets;_names=names;_afterPatch=afterPatch;
        _installed=this;
        if(!incremental)InstallNext(targets.Length);
    }
    // Each production read installs at most one hook. No binding may be armed
    // until all targets are installed and exact ownership is checked again.
    internal bool PrepareNext()
    {
        if(_disposed||_installationFailed||Environment.CurrentManagedThreadId!=_thread||!ReferenceEquals(_installed,this))
            throw new InvalidOperationException("Hook preparation unavailable.");
        if(_installationComplete)return true;
        InstallNext(1);
        return _installationComplete;
    }
    private void InstallNext(int count)
    {
        try
        {
            if(!ExactPatches())throw new InvalidOperationException("Partial hook ownership changed.");
            for (int end=Math.Min(_targets.Length,_nextPatch+count);_nextPatch<end;_nextPatch++)
            {
                int i=_nextPatch;var targets=_targets;var names=_names;
                if(Harmony.GetPatchInfo(targets[i])?.Owners.Count>0)throw new InvalidOperationException("Hook target acquired during preparation.");
                if(i is >=15 and <=17)_resumeItems.Add(targets[i]);
                _methods.Add(targets[i]);
                var methods=new[]{Hook(names[i]+"Prefix"),Hook(names[i]+"Postfix"),Hook(names[i]+"Finalizer")};
                _patchMethods.Add(targets[i],methods);
                _readStage?.Invoke(8);
                _harmony.Patch(targets[i],new HarmonyMethod(methods[0]),new HarmonyMethod(methods[1]),finalizer:new HarmonyMethod(methods[2]));
                _afterPatch?.Invoke(i+1);
            }
            if(!ExactPatches())throw new InvalidOperationException("Hook ownership changed during preparation.");
            _installationComplete=_nextPatch==_targets.Length;
        }
        catch(Exception installationError)
        {
            _installationFailed=true;
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
        if(!failed._installationFailed)throw new InvalidOperationException("An active hook lease owns cleanup.");
        failed.Dispose();
    }
    private static MethodInfo Hook(string name) => typeof(GenericEventV7Hooks).GetMethod(name,BindingFlags.Static|BindingFlags.NonPublic)!;
    internal static void Arm(GenericEventV7Binding binding)
    {
        if (_installed is null || _installed._disposed || !_installed._installationComplete || Environment.CurrentManagedThreadId != _installed._thread || _armed is not null)
            throw new InvalidOperationException("Generic event hook reservation unavailable.");
        _armed = binding;
    }
    internal static bool Owns(GenericEventV7Binding binding)=>OwnershipDiagnostic(binding)==G.NotCaptured;
    internal static G OwnershipDiagnostic(GenericEventV7Binding binding) {
        if(!ReferenceEquals(_armed,binding))return G.PendingOwnerBinding;
        if(_installed is null||_installed._disposed)return G.PendingOwnerHooks;
        if(Environment.CurrentManagedThreadId!=_installed._thread)return G.PendingOwnerThread;
        return _installed.ExactPatches()?G.NotCaptured:G.PendingOwnerPatches;
    }
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
    private void WatchResume(GenericEventV7CombatHandoff combat)
    {
        var method=combat.ResumeMethod;
        if(_resume is not null||Harmony.GetPatchInfo(method)?.Owners.Count>0)throw new InvalidOperationException("Resume hook already owned.");
        _resume=combat;
        var patches=new[]{Hook("ResumePrefix"),Hook("ResumePostfix"),Hook("ResumeFinalizer")};
        _methods.Add(method);_patchMethods.Add(method,patches);
        _harmony.Patch(method,new HarmonyMethod(patches[0]),new HarmonyMethod(patches[1]),finalizer:new HarmonyMethod(patches[2]));
    }
    internal void PauseForCombat()
    {
        if(_resume is null||_armed is not null||!ExactPatches())throw new InvalidOperationException("Resume transfer unavailable.");
        _cleanupProbe?.Invoke();
        if(!ExactPatches())throw new InvalidOperationException("Hook ownership changed during combat transfer cleanup.");
        foreach(var method in _methods.ToArray()) {
            if(method==_resume.ResumeMethod||_resumeItems.Contains(method))continue;
            foreach(var patch in _patchMethods[method])_harmony.Unpatch(method,patch);
            if(AllPatches(method).Any(p=>p.owner==Owner&&_patchMethods[method].Contains(p.PatchMethod)))
                throw new InvalidOperationException("Event hooks remain active during combat.");
            _methods.Remove(method);_patchMethods.Remove(method);
        }
    }
    private D _resumeDiagnostic;
    internal D ResumeDiagnostic=>_resumeDiagnostic!=D.none?_resumeDiagnostic:_resume?.ResumeDiagnostic??D.hooks_owner;
    private void RecordResumeFailure(D diagnostic)
    {
        if(_resumeDiagnostic!=D.none)return;
        var prior=_resume?.ResumeDiagnostic??D.none;
        _resumeDiagnostic=prior==D.none?diagnostic:prior;
    }
    internal string ResumeStatus()
    {
        try {
            if(_disposed||Environment.CurrentManagedThreadId!=_thread||!ExactPatches()||_resume is null){RecordResumeFailure(D.hooks_owner);return "unsupported";}
            return _resume.ResumeStatus();
        }catch{RecordResumeFailure(D.read_exception);return "unsupported";}
    }
    internal static bool OwnsResume(GenericEventV7Binding binding)=>_installed is { _disposed:false } h&&
        Environment.CurrentManagedThreadId==h._thread&&h.ExactPatches()&&h._resume?.Owns(binding)==true;
    internal object ReadResumeItem()=>CheckedResume().ReadItem();
    internal object ApplyResumeItem(string? decision,string? action)=>CheckedResume().ApplyItem(decision,action);
    private GenericEventV7CombatHandoff CheckedResume() {
        if(_resume is null||!OwnsResume(_resume.Binding))throw new InvalidOperationException("Resume owner unavailable.");
        return _resume;
    }
    private static void ResumePrefix(EventModel __instance,AbstractRoom __0,out State __state)
    {
        var resume=_installed?._resume;__state=new State{Previous=Parent.Value,Binding=resume?.Binding};
        try {
            if(resume is null||_installed is null||Environment.CurrentManagedThreadId!=_installed._thread||!_installed.ExactPatches()){
                resume?.FailResume(D.callback_owner);throw new InvalidOperationException();
            }
            if(Parent.Value is not null){resume.FailResume(ReferenceEquals(Parent.Value,resume.Binding)?D.callback_parent_retained:D.callback_parent);throw new InvalidOperationException();}
            resume.EnterResume(__instance,__0);Parent.Value=resume.Binding;
        }catch{resume?.FailResume();}
    }
    private static void ResumePostfix(Task __result,State? __state)
    {try{__state?.Binding?.Combat?.CaptureResumeTask(__result);}catch{__state?.Binding?.Combat?.FailResume(D.callback_task);}finally{RestoreParent(__state);}}
    private static void ResumeFinalizer(Exception? __exception,State? __state)
    {if(__exception is not null)__state?.Binding?.Combat?.FailResume(D.callback_exception);RestoreParent(__state);}
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
        internal GenericEventV7ItemState? Item;
        internal bool Restored;
    }
    private static void CombatEntryPrefix(EventModel __instance,EncounterModel __0,IReadOnlyList<Reward> __1,bool __2,out State __state)
    {
        __state=new State {Binding=Parent.Value};
        if(__state.Binding is not {} b){if(_armed is not null)_armed.Failed=true;return;}
        try {
            if(!Owns(b)||!ReferenceEquals(b.EventModel,__instance)||b.Combat is not null)throw new InvalidOperationException();
            b.Combat=new GenericEventV7CombatHandoff(b,__0,__1,__2);
            if(__2)_installed!.WatchResume(b.Combat);
        }catch {b.Failed=true;}
    }
    private static void CombatEntryPostfix(State? __state) {if(__state?.Binding?.Combat is {} combat)combat.Returned=true;}
    private static void CombatEntryFinalizer(Exception? __exception,State? __state) {if(__exception is not null&&__state?.Binding is {} b)b.Failed=true;}
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
        if(_installed?._resume is {} resume&&resume.Started)resume.FailResume(D.item_callback);
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
    private static readonly AsyncLocal<GenericEventV7AbandonPopup?> PopupDispatch=new();
    internal static IDisposable EnterPopup(GenericEventV7AbandonPopup popup) {
        if(PopupDispatch.Value is not null||!Owns(popup.Binding))throw new InvalidOperationException("Popup dispatch ownership unavailable.");
        PopupDispatch.Value=popup;return new PopupScope(popup);
    }
    private sealed class PopupScope : IDisposable {
        private readonly GenericEventV7AbandonPopup _popup;
        internal PopupScope(GenericEventV7AbandonPopup popup)=>_popup=popup;
        public void Dispose(){if(!ReferenceEquals(PopupDispatch.Value,_popup))_popup.Binding.Failed=true;PopupDispatch.Value=null;}
    }
    private static void ActReadyPrefix(object __instance,out State __state) {
        var b=Parent.Value;__state=new State{Binding=b};if(b is null)return;
        try{if(!Owns(b)||b.Terminal is not null)throw new InvalidOperationException("Terminal owner changed.");b.Terminal=new(b,__instance);b.RequestSeen=true;}catch{b.Failed=true;throw;}
    }
    private static void ActReadyPostfix(State? __state)=>__state?.Binding?.Terminal?.ReadyReturned();
    private static void ActReadyFinalizer(Exception? __exception,State? __state){if(__exception is not null&&__state?.Binding is {} b){b.Terminal?.Abort();b.Failed=true;}}
    private static void AbandonPopupPrefix(MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu? __0,out State __state) {
        var b=Parent.Value;__state=new State{Binding=b};if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        try{if(__0 is not null||!Owns(b)||b.RequestSeen||!b.ContextValid(false))throw new InvalidOperationException();b.Abandon=new(b);b.RequestSeen=true;}
        catch{b.Failed=true;}
    }
    private static void AbandonPopupPostfix(MegaCrit.Sts2.Core.Nodes.CommonUi.NAbandonRunConfirmPopup __result,State? __state) {
        if(__state?.Binding is {} b&&!b.Failed)try{b.Abandon!.Created(__result);}catch{b.Failed=true;}
    }
    private static void AbandonPopupFinalizer(Exception? __exception,State? __state)=>ItemCollectionFinalizer(__exception,__state);
    private static void AbandonTaskPrefix(RunManager __instance,out State __state) {
        var popup=PopupDispatch.Value;__state=new State{Binding=popup?.Binding};
        if(popup is null){if(_armed is not null)_armed.Failed=true;return;}
        try{popup.EnterAbandon(__instance);}catch{popup.Binding.Failed=true;}
    }
    private static void AbandonTaskPostfix(Task __result,State? __state) {
        if(__state?.Binding is {} b&&!b.Failed)try{b.Abandon!.Returned(__result);}catch{b.Failed=true;}
    }
    private static void AbandonTaskFinalizer(Exception? __exception,State? __state)=>ItemCollectionFinalizer(__exception,__state);
    private static void SphereCursePrefix(IEnumerable<CardModel> __0,Player __1,out State __state){
        var sphere=SphereClick.Value;__state=new State{Binding=sphere?.Binding};if(sphere is null)return;
        try{if(!ReferenceEquals(_armed?.Sphere,sphere))throw new InvalidOperationException();sphere.CurseEntering(__1);}catch{FailItem(sphere.Binding);}
    }
    private static void SphereCursePostfix(Task<IEnumerable<CardPileAddResult>> __result,State? __state){try{__state?.Binding?.Sphere?.CurseReturned(__result);}catch{FailItem(__state?.Binding);}}
    private static void SphereCurseFinalizer(Exception? __exception,State? __state)=>ItemCollectionFinalizer(__exception,__state);
    private static void SphereScreenPrefix(MegaCrit.Sts2.Core.Events.Custom.CrystalSphereEvent.CrystalSphereMinigame __0,out State __state) {
        var b=Parent.Value;__state=new State{Binding=b};
        try{if(b is null||!Owns(b)||b.Sphere is not null||b.RequestSeen||!b.ContextValid(false))throw new InvalidOperationException();b.Sphere=new(b,__0);}catch{FailItem(b);}
    }
    private static void SphereScreenPostfix(State? __state){try{__state?.Binding?.Sphere?.ScreenShown();}catch{FailItem(__state?.Binding);}}
    private static void SphereScreenFinalizer(Exception? __exception,State? __state)=>ItemCollectionFinalizer(__exception,__state);
    private static void ItemOfferPrefix(RewardsSet __instance,out State __state)
    {
        var b=Parent.Value;__state=new State{Binding=b,Previous=Request.Value};
        if(b is null){FailItem(null);return;}
        if(b.Sphere is {} sphere){try{sphere.OfferEntered(__instance);Request.Value=b;}catch{FailItem(b);}return;}
        try
        {
            if(!b.ItemContextValid()||b.RequestSeen||Request.Value is not null||
                !ReferenceEquals(__instance.Player,b.Player)||RewardsSet.testSelector is not null)
            {FailItem(b);return;}
            b.RequestSeen=true;b.Item=new GenericEventV7ItemState(b,__instance);Request.Value=b;
        }
        catch{FailItem(b);}
    }
    private static void ItemOfferPostfix(Task __result,State? __state)
    {
        if(__state?.Binding?.Sphere is {} sphere){try{sphere.Offering(__result);}catch{FailItem(__state.Binding);}RestoreRequest(__state);return;}
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
        if(b.Sphere is {} sphere){try{sphere.RewardScreenEntering(__0,__1,__2);}catch{FailItem(b);}return;}
        try
        {
            if(!b.ItemContextValid()||!ReferenceEquals(Parent.Value,b)||b.Item is not {} item||b.ScreenSeen||item.ScreenEntered||
                !ReferenceEquals(item.Set,__0)||__1||!ReferenceEquals(__2,b.RunState)||!item.BindDomain())
            {FailItem(b);return;}
            item.ScreenEntered=true;b.ScreenSeen=true;
        }
        catch{FailItem(b);}
    }
    private static void ItemScreenPostfix(NRewardsScreen __result,State? __state)
    {
        if(__state?.Binding is not {} b||b.Failed)return;
        if(b.Sphere is {} sphere){try{sphere.RewardsShown(__result);}catch{FailItem(b);}return;}
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
        var item=CollectionScope.Value;__state=new State{Binding=item?.Binding,Item=item};
        if(_armed?.Sphere is {} sphere){__state.Binding=_armed;try{sphere.CollectionEntering(__instance);}catch{FailItem(_armed);}return;}
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
        if(__state?.Binding?.Sphere is {} sphere){try{sphere.CollectionReturned(__result);}catch{FailItem(__state.Binding);}return;}
        if(__state?.Binding is {} b&&!b.Failed)
        {if(__state?.Item is not {} item||!item.CollectionEntered||item.CollectionTask is not null||__result is null)FailItem(b);else item.CollectionTask=__result;}
    }
    private static void ItemCollectionFinalizer(Exception? __exception,State? __state)
    {if(__exception is not null&&__state?.Binding is {} b)FailItem(b);}
    private static void CardMenuPrefix(IReadOnlyList<CardCreationResult> __0,IReadOnlyList<CardRewardAlternative> __1,out State __state) {
        var item=CollectionScope.Value;__state=new State{Binding=item?.Binding,Item=item};
        if(_armed?.Sphere is {} sphere){__state.Binding=_armed;try{sphere.MenuEntering();}catch{FailItem(_armed);}return;}
        if(item?.CardReward is not {} reward){FailItem(item?.Binding);return;}
        try{if(!item.Context()||!item.CollectionEntered)throw new InvalidOperationException();reward.MenuEntering(__0,__1);}catch{FailItem(item.Binding);}
    }
    private static void CardMenuPostfix(NCardRewardSelectionScreen __result,State? __state) {
        if(__state?.Binding?.Sphere is {} sphere){try{sphere.MenuShown(__result);}catch{FailItem(__state.Binding);}return;}
        if(__state?.Item is not {} item||item.Binding.Failed)return;
        try{item.CardReward!.MenuEntered(__result);}catch{FailItem(item.Binding);}
    }
    private static void CardMenuFinalizer(Exception? __exception,State? __state)=>ItemCollectionFinalizer(__exception,__state);
    private static void CardMenuTaskPrefix(NCardRewardSelectionScreen __instance,out State __state) {
        var item=CollectionScope.Value;__state=new State{Binding=item?.Binding,Item=item};
        if(_armed?.Sphere is {} sphere){__state.Binding=_armed;try{sphere.MenuTaskEntering(__instance);}catch{FailItem(_armed);}return;}
        if(item?.CardReward is not {} reward){FailItem(item?.Binding);return;}
        try{if(!item.Context())throw new InvalidOperationException();reward.TaskEntering(__instance);}catch{FailItem(item.Binding);}
    }
    private static void CardMenuTaskPostfix(Task<int?> __result,State? __state) {
        if(__state?.Binding?.Sphere is {} sphere){try{sphere.MenuTaskReturned(__result);}catch{FailItem(__state.Binding);}return;}
        if(__state?.Item is not {} item||item.Binding.Failed)return;
        try{item.CardReward!.TaskEntered(__result);}catch{FailItem(item.Binding);}
    }
    private static void CardMenuTaskFinalizer(Exception? __exception,State? __state)=>ItemCollectionFinalizer(__exception,__state);
    private static void EnchantRequestPrefix(IReadOnlyList<CardModel> __0, EnchantmentModel __1, int __2, CardSelectorPrefs __3, out State __state)
    {
        __state = new State { Previous=Request.Value };
        var b=Parent.Value;
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        __state.Binding=b;
        try
        {
            if(!Owns(b)||b.Closed||b.RequestSeen||!b.ContextValid(false)||!b.BindSelectionDeck()||
                __0 is null||__1 is null||__2<1||__3.MinSelect<1||__3.MinSelect!=__3.MaxSelect||__3.MaxSelect>8||__3.Cancelable||
                !ReferenceEquals(__1.CanonicalInstance,__1)||
                !Sts2AgentBridge.Successors.CardSelectionV1.Native.CardSelectionV1NativeRules.IsStableKey(__1.Id.Entry)||
                __0.Count<=__3.MaxSelect||__0.Count>64)
            {b.Failed=true;return;}
            b.RequestSeen=true;b.Prefs=__3;
            b.Operation=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Enchant;
            b.EnchantmentModel=__1;b.Enchantment=new(__1,__1.Id.Entry,__2);
            var originals=__0.ToArray();
            if(originals.Distinct(ReferenceEqualityComparer.Instance).Count()!=originals.Length||
                originals.Any(c=>c is null||c.Enchantment is not null||!__1.CanEnchant(c)||
                    !ReferenceEquals(c.Owner,b.Player)||!ReferenceEquals(c.RunState,b.RunState)||
                    !b.SelectionDeck.Any(d=>ReferenceEquals(d.ModelIdentity,c))))
            {b.Failed=true;return;}
            b.Originals=b.SelectionDeck.Select(d=>(CardModel)d.ModelIdentity).Where(c=>originals.Contains(c,ReferenceEqualityComparer.Instance)).ToArray();
            Request.Value=b;
        }
        catch{b.Failed=true;}
    }
    private static void EnchantRequestPostfix(Task<IEnumerable<CardModel>> __result,State? __state)=>UpgradePostfix(__result,__state);
    private static void EnchantRequestFinalizer(Exception? __exception,State? __state)=>UpgradeFinalizer(__exception,__state);
    private static void EnchantScreenPrefix(IReadOnlyList<CardModel> __0,EnchantmentModel __1,int __2,CardSelectorPrefs __3,out State __state)
    {
        __state=new State {Binding=Request.Value};var b=Request.Value;
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        try
        {
            if(!Owns(b)||b.Closed||b.ScreenSeen||!ReferenceEquals(Parent.Value,b)||!b.ContextValid(false)||
                b.Operation!=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Enchant||
                __0 is null||!ReferenceEquals(__1,b.EnchantmentModel)||
                b.Enchantment?.Amount!=__2||!b.SamePrefs(__3)||!b.MatchesCurrentDeck()||
                __0.Count!=b.Originals.Length||__0.Where((c,i)=>!ReferenceEquals(c,b.Originals[i])||c.Enchantment is not null||!__1.CanEnchant(c)).Any())
            {b.Failed=true;return;}
            b.ScreenSeen=true;
        }
        catch{b.Failed=true;}
    }
    private static void EnchantScreenPostfix(NDeckEnchantSelectScreen __result,State? __state)
    {
        if(__state?.Binding is not {} b||b.Failed)return;
        if(__result is null||__result.GetType()!=typeof(NDeckEnchantSelectScreen)||b.Screen is not null)b.Failed=true;
        else b.Screen=__result;
    }
    private static void EnchantScreenFinalizer(Exception? __exception,State? __state)=>ScreenFinalizer(__exception,__state);
    private static void UpgradePrefix(Player __0, CardSelectorPrefs __1, out State __state)
    {
        __state = new State {Previous=Request.Value};
        var b = Parent.Value;
        if (b is null) { if (_armed is not null) _armed.Failed=true; return; }
        __state.Binding=b;
        try
        {
            if (!Owns(b) || b.Closed || b.RequestSeen || !ReferenceEquals(__0,b.Player) || !b.ContextValid(false)||!b.BindSelectionDeck())
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
                originals.Any(c=>!b.SelectionDeck.Any(d=>ReferenceEquals(d.ModelIdentity,c))))
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
    // The native prompt classifies intent, not success. Only the observed
    // transformation journal can establish a completed effect.
    private static bool TransformPrompt(CardSelectorPrefs prefs)
    {
        var expected=CardSelectorPrefs.TransformSelectionPrompt;
        return prefs.Prompt is {} prompt && prompt.LocTable==expected.LocTable && prompt.LocEntryKey==expected.LocEntryKey;
    }
    private static void GenericDeckPrefix(Player __0,CardSelectorPrefs __1,Func<CardModel,bool>? __2,Func<CardModel,int>? __3,out State __state)
    {
        __state=new State {Previous=Request.Value};var b=Parent.Value;
        // Removal forwards through FromDeckGeneric. Its outer request retains
        // ownership and its own completion task; do not admit a second child.
        if(b is not null&&ReferenceEquals(Request.Value,b)&&b.Operation==Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Remove)
        {
            if(!Owns(b)||b.Closed||!ReferenceEquals(__0,b.Player)||!b.SamePrefs(__1)||b.ScreenSeen)b.Failed=true;
            return;
        }
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        __state.Binding=b;
        try
        {
            if(!Owns(b)||b.Closed||b.RequestSeen||!ReferenceEquals(__0,b.Player)||!b.ContextValid(false)||!b.BindSelectionDeck()||
                !TransformPrompt(__1)||__1.MinSelect!=1||__1.MaxSelect!=1||__1.Cancelable)
            {b.Failed=true;return;}
            b.RequestSeen=true;b.Prefs=__1;b.GenericDeckTransform=true;
            b.Operation=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Transform;
            Request.Value=b;
        }
        catch{b.Failed=true;}
    }
    private static void GenericDeckPostfix(Task<IEnumerable<CardModel>> __result,State? __state)=>UpgradePostfix(__result,__state);
    private static void GenericDeckFinalizer(Exception? __exception,State? __state)=>UpgradeFinalizer(__exception,__state);
    private static void RemovalPrefix(Player __0, CardSelectorPrefs __1, Func<CardModel,bool>? __2, out State __state)
    {
        __state=new State {Previous=Request.Value};
        var b=Parent.Value;
        if(b is null) {if(_armed is not null)_armed.Failed=true;return;}
        __state.Binding=b;
        try
        {
            if(!Owns(b)||b.Closed||b.RequestSeen||!ReferenceEquals(__0,b.Player)||!b.ContextValid(false)||!b.BindSelectionDeck())
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
                (b.Operation!=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Remove&&!b.GenericDeckTransform)||
                (b.GenericDeckTransform&&!TransformPrompt(__1))||!b.SamePrefs(__1)||!b.MatchesCurrentDeck()||__0.Count<=b.Prefs.MaxSelect||__0.Count>64)
            {b.Failed=true;return;}
            b.ScreenSeen=true;
            var originals=new CardModel[__0.Count];for(int i=0;i<originals.Length;i++)originals[i]=__0[i];
            if(originals.Any(c=>c is null||(b.GenericDeckTransform?!c.IsTransformable:!c.IsRemovable)||!ReferenceEquals(c.Owner,b.Player)||!ReferenceEquals(c.RunState,b.RunState))||originals.Distinct(ReferenceEqualityComparer.Instance).Count()!=originals.Length||
                originals.Any(c=>!b.SelectionDeck.Any(d=>ReferenceEquals(d.ModelIdentity,c))))
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
            else {b.Screen=__result;if(b.GenericDeckTransform)b.Transform=new GenericEventV7TransformState(b);}
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
            if(!Owns(b)||b.Closed||b.RequestSeen||__0 is null||__1 is null||!ReferenceEquals(__2,b.Player)||!b.ContextValid(false)||!b.BindSelectionDeck())
            {b.Failed=true;return;}
            b.RequestSeen=true;b.Prefs=__3;b.RewardContext=__0;
            b.Operation=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Add;
            if(__3.Cancelable||__3.MinSelect<0||__3.MinSelect>__3.MaxSelect||__3.MaxSelect<1||__3.MaxSelect>(__3.MinSelect==0?15:8)||(__3.MinSelect==0&&!__3.RequireManualConfirmation)||!b.CaptureOffers(__1))b.Failed=true;
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
            if(!Owns(b)||b.Closed||b.RequestSeen||!ReferenceEquals(__0,b.Player)||!b.ContextValid(false)||!b.BindSelectionDeck())
            {b.Failed=true;return;}
            b.RequestSeen=true;b.Prefs=__1;b.TransformFunction=__2;
            b.Operation=Sts2AgentBridge.Successors.CardSelectionV1.CardSelectionV1Operation.Transform;
            if(__1.Cancelable||__1.MinSelect<0||__1.MinSelect>__1.MaxSelect||__1.MaxSelect<1||__1.MaxSelect>8||(__1.MinSelect<__1.MaxSelect&&!__1.RequireManualConfirmation))b.Failed=true;
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
                !b.SamePrefs(__2)||!b.MatchesCurrentDeck()||(b.Prefs.MinSelect==0?__0.Count<1:__0.Count<=b.Prefs.MaxSelect)||__0.Count>64||__1 is null||
                (b.TransformFunction is not null&&!ReferenceEquals(__1,b.TransformFunction)))
            {b.Failed=true;return;}
            b.ScreenSeen=true;
            var originals=new CardModel[__0.Count];for(int i=0;i<originals.Length;i++)originals[i]=__0[i];
            var eligible=b.SelectionDeck.Select(d=>(CardModel)d.ModelIdentity).Where(c=>(int)c.Type!=6&&c.IsTransformable).ToArray();
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
    private static void ResultsScreenPrefix(List<CardPileAddResult> __0,out State __state) {
        var b=Parent.Value;__state=new State{Binding=b};
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        try {
            if(!Owns(b)||b.Failed||b.Closed||b.RequestSeen||b.ScreenSeen||b.Results is not null||b.Item is not null||b.Offer is not null||
                !b.ContextValid(false)||b.Overlays.ScreenCount!=0)throw new InvalidOperationException();
            b.RequestSeen=true;b.Results=new GenericEventV7ResultsAdapter(b,__0);
        }catch{b.Failed=true;}
    }
    private static void ResultsScreenPostfix(NCardsViewScreen __result,State? __state) {
        if(__state?.Binding is not {} b||b.Failed)return;try{b.Results!.BindScreen(__result);}catch{b.Failed=true;}
    }
    private static void ResultsScreenFinalizer(Exception? __exception,State? __state)=>ScreenFinalizer(__exception,__state);
    private static void OfferRequestPrefix(PlayerChoiceContext __0,IReadOnlyList<CardModel> __1,Player __2,bool __3,out State __state) {
        OfferEntry(__2,__1,false,__0 is not null,out __state,__3);
    }
    private static void BundleRequestPrefix(Player __0,IReadOnlyList<IReadOnlyList<CardModel>> __1,out State __state) {
        OfferEntry(__0,__1,true,true,out __state);
    }
    private static void OfferEntry(Player player,object domain,bool bundle,bool legal,out State state,bool canSkip=false) {
        state=new State{Previous=Request.Value};var b=Parent.Value;state.Binding=b;
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        try {
            if(!legal||!Owns(b)||b.RequestSeen||b.Item is not null||!ReferenceEquals(player,b.Player)||!b.BindSelectionDeck())throw new InvalidOperationException();
            IReadOnlyList<CardModel>[] offers;
            if(bundle) {if(domain is not IReadOnlyList<IReadOnlyList<CardModel>> lists||lists.Count is <1 or >5||lists.Any(o=>o is null||o.Count is <1 or >8))throw new InvalidOperationException();offers=lists.ToArray();}
            else {if(domain is not IReadOnlyList<CardModel> cards||cards.Count is <1 or >3)throw new InvalidOperationException();offers=cards.Select(c=>(IReadOnlyList<CardModel>)new[]{c}).ToArray();}
            b.RequestSeen=true;b.Offer=new GenericEventV7OfferAdapter(b,domain,offers,bundle,canSkip);Request.Value=b;
        }catch{b.Failed=true;}
    }
    private static void OfferRequestPostfix(Task<CardModel> __result,State? __state)=>OfferTask(__result,__state);
    private static void BundleRequestPostfix(Task<IEnumerable<CardModel>> __result,State? __state)=>OfferTask(__result,__state);
    private static void OfferTask(Task result,State? state) {
        if(state?.Binding is {} b&&!b.Failed) {
            if(b.Offer is null||b.Offer.RequestTask is not null||result is null)b.Failed=true;else b.Offer.RequestTask=result;
        }
    }
    private static void OfferRequestFinalizer(Exception? __exception,State? __state)=>UpgradeFinalizer(__exception,__state);
    private static void BundleRequestFinalizer(Exception? __exception,State? __state)=>UpgradeFinalizer(__exception,__state);
    private static void OfferScreenPrefix(IReadOnlyList<CardModel> __0,bool __1,out State __state)=>OfferScreenEntry(__0,__1,false,out __state);
    private static void BundleScreenPrefix(IReadOnlyList<IReadOnlyList<CardModel>> __0,out State __state)=>OfferScreenEntry(__0,false,true,out __state);
    private static void OfferScreenEntry(object domain,bool canSkip,bool bundle,out State state) {
        var b=Request.Value;state=new State{Binding=b};
        if(b is null){if(_armed is not null)_armed.Failed=true;return;}
        try {if(!Owns(b)||!ReferenceEquals(Parent.Value,b)||b.Offer is null||b.Offer.Bundle!=bundle)throw new InvalidOperationException();b.Offer.EnterScreen(domain,canSkip);}catch{b.Failed=true;}
    }
    private static void OfferScreenPostfix(NChooseACardSelectionScreen __result,State? __state)=>OfferScreenExit(__result,__state);
    private static void BundleScreenPostfix(NChooseABundleSelectionScreen __result,State? __state)=>OfferScreenExit(__result,__state);
    private static void OfferScreenExit(Godot.Control result,State? state) {
        if(state?.Binding is not {} b||b.Failed)return;try{b.Offer!.BindScreen(result);}catch{b.Failed=true;}
    }
    private static void OfferScreenFinalizer(Exception? __exception,State? __state)=>ScreenFinalizer(__exception,__state);
    private static void BundleScreenFinalizer(Exception? __exception,State? __state)=>ScreenFinalizer(__exception,__state);
    public void Dispose()
    {
        if (_disposed) return;
        if (Environment.CurrentManagedThreadId != _thread) throw new InvalidOperationException("Hook cleanup requires owner thread.");
        if (_armed is not null) { _armed.Failed=true; _armed.Closed=true; _armed.MultiUpgrade?.Close(); _armed.Transform?.Close(); _armed=null; }
        _resume?.DisposeItem();
        UnpatchOwn();
        if (HasOwnedHooks())
            throw new InvalidOperationException("Owned hooks remain installed.");
        _disposed=true;
        if (ReferenceEquals(_installed,this)) _installed=null;
    }
}
