using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;

namespace Sts2AgentBridge.Items.Native;

// One actual Obtain invocation tree. Invocation identity, not Task identity,
// distinguishes pickups: native no-op callbacks share Task.CompletedTask.
// Effects belong to the caller; this owner retains exact native task/result
// boundaries and requires predecessor certification before a successor starts.
internal sealed class PinnedRelicPickupChain : IDisposable
{
    internal sealed class Frame
    {
        internal readonly PinnedRelicPickupChain Owner;
        internal readonly Frame? Parent;
        internal readonly RelicModel Relic;
        internal readonly MethodInfo Method;
        internal readonly PinnedAutomaticRelicEffects.State Before;
        internal readonly List<Frame> Children = new();
        internal Task<RelicModel>? ObtainTask;
        internal Task? AfterTask;
        internal PinnedAutomaticRelicEffects.State? Certificate;
        internal bool Entered, EffectsCleaned;
        internal Frame(PinnedRelicPickupChain owner, Frame? parent, RelicModel relic)
        {
            Owner=owner; Parent=parent; Relic=relic;
            Method=Declared(relic.GetType().GetMethod("AfterObtained",Type.EmptyTypes)!);
            Before=new(owner._player);
        }
    }
    private sealed class Invocation
    {
        internal Frame Frame=null!;
        internal Frame? Previous;
        internal IDisposable? Effects;
        internal bool Restored;
    }
    private static readonly AsyncLocal<Frame?> Scope=new();
    private static readonly AsyncLocal<PinnedRelicPickupChain?> Dispatch=new();
    private static PinnedRelicPickupChain? Active;
    private static readonly MethodInfo Obtain=typeof(RelicCmd).GetMethod("Obtain",new[]{typeof(RelicModel),typeof(Player),typeof(int)})!;
    private readonly Player _player;
    private readonly RelicModel _root;
    private readonly Func<bool> _context;
    private readonly Func<Frame,RelicModel,bool> _allowChild;
    private readonly Func<Frame,IDisposable> _enterEffects;
    private readonly Func<Frame,bool> _effectsValid;
    private readonly Action<Frame> _cleanupEffects,_certified;
    private readonly Harmony _hooks=new("sts.bridge.relic.pickup."+Guid.NewGuid().ToString("N"));
    private readonly HashSet<MethodInfo> _targets=new();
    private readonly List<Frame> _frames=new();
    private readonly int _thread=Environment.CurrentManagedThreadId;
    private bool _invoked,_failed,_disposed;
    internal Frame? Root {get;private set;}
    internal Frame? NativeFrame=>Scope.Value is {} f&&ReferenceEquals(f.Owner,this)?f:null;
    internal IReadOnlyList<Frame> Frames=>_frames;
    internal PinnedRelicPickupChain(Player player,RelicModel root,Func<bool> context,
        Func<Frame,RelicModel,bool> allowChild,Func<Frame,IDisposable> enterEffects,
        Func<Frame,bool> effectsValid,Action<Frame> cleanupEffects,Action<Frame> certified)
    {
        _player=player;_root=root;_context=context;_allowChild=allowChild;
        _enterEffects=enterEffects;_effectsValid=effectsValid;_cleanupEffects=cleanupEffects;_certified=certified;
        Require(context()&&root.Owner is null);
    }
    private bool Context()=>!_failed&&!_disposed&&Environment.CurrentManagedThreadId==_thread&&_context();
    private bool Hooks()=>_targets.All(m=>Harmony.GetPatchInfo(m) is {} p&&p.Owners.Count==1&&p.Owners.Contains(_hooks.Id));
    private static MethodInfo Declared(MethodInfo method)=>method.DeclaringType!.GetMethod(method.Name,
        BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static|BindingFlags.Instance|BindingFlags.DeclaredOnly,
        null,method.GetParameters().Select(p=>p.ParameterType).ToArray(),null)!;
    private void Patch(MethodInfo method,string prefix,string postfix,string finalizer)
    {
        method=Declared(method);
        if(_targets.Contains(method)){Require(Hooks());return;}
        Require(method.GetMethodBody() is not null&&!(Harmony.GetPatchInfo(method)?.Owners.Any()??false));
        _targets.Add(method);
        _hooks.Patch(method,new HarmonyMethod(typeof(PinnedRelicPickupChain),prefix),
            new HarmonyMethod(typeof(PinnedRelicPickupChain),postfix),finalizer:new HarmonyMethod(typeof(PinnedRelicPickupChain),finalizer));
    }
    internal void Invoke(Action input)
    {
        Require(Context()&&!_invoked&&Active is null&&Scope.Value is null&&Dispatch.Value is null);
        _invoked=true;Active=this;
        try {
            Patch(Obtain,nameof(ObtainPrefix),nameof(ObtainPostfix),nameof(ObtainFinalizer));
            Dispatch.Value=this;try{input();}finally{Dispatch.Value=null;}
            Require(Context()&&Hooks());
        } catch {_failed=true;throw;}
    }
    // A reward opened by an awaiting pickup receives its next input on a new
    // owner-frame callback. Reenter only that retained, unfinished invocation;
    // never adopt an ambient or already-completed pickup.
    internal void InvokeChildInput(Frame parent,Action input)
    {
        using var scope=EnterChildContinuation(parent);
        try {input();Require(Context()&&Hooks());}
        catch{_failed=true;throw;}
    }
    // A native alternative callback may resume under the collection's captured
    // execution context. Reenter at that exact callback, not at its UI click.
    internal IDisposable EnterChildContinuation(Frame parent)
    {
        Require(Context()&&_invoked&&Hooks()&&Scope.Value is null&&Dispatch.Value is null&&
            ReferenceEquals(parent.Owner,this)&&_frames.Contains(parent)&&parent.Entered&&parent.Certificate is null&&
            parent.AfterTask is {IsCompleted:false}&&parent.ObtainTask is {IsCompleted:false});
        Scope.Value=parent;
        return new ContinuationScope(this,parent);
    }
    private sealed class ContinuationScope:IDisposable
    {
        private PinnedRelicPickupChain? _owner;
        private readonly Frame _parent;
        internal ContinuationScope(PinnedRelicPickupChain owner,Frame parent){_owner=owner;_parent=parent;}
        public void Dispose()
        {
            if(_owner is not {} owner)return;_owner=null;
            try{owner.Require(owner.Context()&&owner.Hooks()&&ReferenceEquals(Scope.Value,_parent));}
            finally{Scope.Value=null;}
        }
    }
    // Call before a parent's next native effect (for example Large Capsule's
    // card addition). A pending/faulted predecessor never becomes a handoff.
    internal void BeforeAdvance(Frame frame)
    {
        Require(Context()&&ReferenceEquals(frame.Owner,this)&&ReferenceEquals(NativeFrame,frame)&&
            frame.Entered&&frame.Certificate is null&&Hooks());
        if(frame.Children.LastOrDefault() is {} previous)Require(TryCertify(previous));
    }
    private static void ObtainPrefix(RelicModel __0,Player __1,int __2,out Invocation? __state)
    {
        __state=null;var owner=Scope.Value?.Owner??Dispatch.Value??Active;if(owner is null)return;
        try {
            owner.Require(owner.Context()&&owner.Hooks()&&ReferenceEquals(__1,owner._player)&&__2==-1&&__0.Owner is null&&owner._frames.Count<8);
            var parent=owner.NativeFrame;
            if(parent is null)owner.Require(ReferenceEquals(Dispatch.Value,owner)&&owner.Root is null&&ReferenceEquals(__0,owner._root));
            else {owner.BeforeAdvance(parent);owner.Require(parent.Children.Count<2&&owner._allowChild(parent,__0));}
            var frame=new Frame(owner,parent,__0);
            owner.Require(frame.Method.ReturnType==typeof(Task)&&!frame.Method.IsStatic&&!frame.Method.IsGenericMethod&&
                frame.Method.DeclaringType!.Assembly==typeof(RelicModel).Assembly);
            owner.Patch(frame.Method,nameof(AfterPrefix),nameof(AfterPostfix),nameof(AfterFinalizer));
            owner._frames.Add(frame);if(parent is null)owner.Root=frame;else parent.Children.Add(frame);
            __state=new Invocation{Frame=frame,Previous=Scope.Value};Scope.Value=frame;
        }catch{owner._failed=true;throw;}
    }
    private static void ObtainPostfix(Task<RelicModel> __result,Invocation? __state)
    {
        if(__state is not {} call)return;var owner=call.Frame.Owner;
        try {owner.Require(owner.Context()&&call.Frame.ObtainTask is null&&__result is not null);call.Frame.ObtainTask=__result;}
        catch{owner._failed=true;throw;}
        finally{Restore(call);}
    }
    private static void ObtainFinalizer(Exception? __exception,Invocation? __state)
    {if(__state is {} call){if(__exception is not null)call.Frame.Owner._failed=true;Restore(call);}}
    private static void Restore(Invocation call)
    {if(!call.Restored){Scope.Value=call.Previous;call.Restored=true;}}
    private static void AfterPrefix(RelicModel __instance,MethodBase __originalMethod,out Invocation? __state)
    {
        __state=null;var frame=Scope.Value;if(frame is null)return;var owner=frame.Owner;
        try {
            owner.Require(owner.Context()&&owner.Hooks()&&!frame.Entered&&ReferenceEquals(__instance,frame.Relic)&&
                Equals(__originalMethod,frame.Method)&&frame.Before.AddedRelic(new(owner._player),frame.Relic));
            frame.Entered=true;__state=new Invocation{Frame=frame};
            __state.Effects=owner._enterEffects(frame);
            owner.Require(__state.Effects is not null);
        }catch{owner._failed=true;throw;}
    }
    private static void AfterPostfix(Task __result,Invocation? __state)
    {
        if(__state is not {} call)return;var owner=call.Frame.Owner;
        try {owner.Require(owner.Context()&&call.Frame.AfterTask is null&&__result is not null);call.Frame.AfterTask=__result;}
        catch{owner._failed=true;throw;}
        finally{ExitEffects(call);}
    }
    private static void AfterFinalizer(Exception? __exception,Invocation? __state)
    {if(__state is {} call){if(__exception is not null)call.Frame.Owner._failed=true;ExitEffects(call);}}
    private static void ExitEffects(Invocation call)
    {
        if(call.Restored)return;call.Restored=true;
        try{call.Effects?.Dispose();}catch{call.Frame.Owner._failed=true;throw;}
    }
    internal bool TryCertify(Frame frame)
    {
        try{return Certify(frame);}catch{_failed=true;throw;}
    }
    private bool Certify(Frame frame)
    {
        Require(Context()&&ReferenceEquals(frame.Owner,this)&&_frames.Contains(frame)&&Hooks());
        if(frame.Certificate is not null)return true;
        Require(frame.AfterTask?.IsFaulted!=true&&frame.AfterTask?.IsCanceled!=true&&
            frame.ObtainTask?.IsFaulted!=true&&frame.ObtainTask?.IsCanceled!=true);
        if(frame.AfterTask?.IsCompletedSuccessfully!=true||frame.ObtainTask?.IsCompletedSuccessfully!=true)return false;
        Require(frame.Entered&&ReferenceEquals(frame.ObtainTask.Result,frame.Relic)&&ReferenceEquals(frame.Relic.Owner,_player)&&
            _player.Relics.Count(r=>ReferenceEquals(r,frame.Relic))==1);
        foreach(var child in frame.Children)Require(TryCertify(child));
        Require(_effectsValid(frame));
        var after=new PinnedAutomaticRelicEffects.State(_player);
        _cleanupEffects(frame);frame.EffectsCleaned=true;
        Require(Context()&&after.Same(new(_player))&&Hooks());
        frame.Certificate=after;_certified(frame);
        Require(Context()&&after.Same(new(_player)));return true;
    }
    internal bool Completed=>Root is {} root&&TryCertify(root);
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool condition)
    {if(!condition){_failed=true;throw new InvalidOperationException("relic_pickup_chain_boundary");}}
    public void Dispose()
    {
        if(_disposed){Require(!_failed);return;}
        bool complete=false;Exception? failure=null;
        try {Require(Context());complete=!_invoked||Completed;Require(complete);}
        catch(Exception error){_failed=true;failure=error;}
        foreach(var frame in _frames.AsEnumerable().Reverse().Where(f=>!f.EffectsCleaned))
            try{_cleanupEffects(frame);frame.EffectsCleaned=true;}catch(Exception error){_failed=true;failure??=error;}
        try {_hooks.UnpatchAll(_hooks.Id);Require(!_targets.Any(m=>Harmony.GetPatchInfo(m)?.Owners.Contains(_hooks.Id)==true));}
        catch(Exception error){_failed=true;failure??=error;}
        _disposed=true;if(complete&&!_failed&&ReferenceEquals(Active,this))Active=null;
        if(failure is not null)throw new InvalidOperationException("relic_pickup_chain_cleanup",failure);
        Require(complete&&!_failed);
    }
}
