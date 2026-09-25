using System;
using Environment = System.Environment;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Items.Native;
using Sts2AgentBridge.Rooms.Rest;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// One event child owns the complete invocation tree. Native reward sets remain
// separate frames, never separate event admissions or fabricated event bindings.
internal sealed partial class GenericEventCompoundRewards : IGenericFullRewardSession
{
    internal sealed class RewardFrame
    {
        internal readonly GenericEventCompoundRewards Owner;
        internal readonly RewardsSet Set;
        internal readonly RewardFrame? Parent;
        internal readonly PinnedRelicPickupChain.Frame? Pickup;
        internal readonly RestRewardContinuation Controller;
        internal readonly PinnedAutomaticRelicEffects.State Before;
        internal readonly List<Task> Collections=new();
        internal NRewardsScreen? Screen;
        internal Task? Offer,Collection;
        internal NCardRewardSelectionScreen? Menu;
        internal Task<int?>? MenuTask;
        internal Receipt? Pending;
        internal bool OfferEntered,Entered,MenuEntering,TaskEntering;
        internal PublicRewardDecisionSnapshot View;
        internal PinnedAutomaticRelicEffects.State? Certificate;
        internal RewardFrame(GenericEventCompoundRewards owner,RewardsSet set,RewardFrame? parent,PinnedRelicPickupChain.Frame? pickup)
        {
            Owner=owner;Set=set;Parent=parent;Pickup=pickup;Before=new(owner._binding.Player);
            var ancestors=parent is null?Array.Empty<RewardFrame>():owner.Path(parent);
            Controller=new(set,owner._binding.Player,owner._binding.Overlays,owner.Context,
                (target,screen)=>new PinnedRewardAlternatives(target,screen),p=>new PinnedRewardInventory(p),
                reward=>owner.Effect(this,reward),ancestors.Select(f=>f.Set).ToArray(),ancestors.Select(f=>(Control)f.Screen!).ToArray());
        }
    }
    internal sealed class Receipt
    {
        internal readonly string Decision,Action;
        internal readonly int Revision;
        internal readonly RewardFrame Frame;
        internal bool Done;
        internal Receipt(string decision,string action,int revision,RewardFrame frame){Decision=decision;Action=action;Revision=revision;Frame=frame;}
    }
    private sealed class Lease : IDisposable
    {
        private Action? _release;
        internal Lease(Action release)=>_release=release;
        public void Dispose(){var release=_release;_release=null;release?.Invoke();}
    }
    private static readonly AsyncLocal<RewardFrame?> Native=new();
    private static GenericEventCompoundRewards? Active;
    private readonly GenericEventV7Binding _binding;
    private readonly RelicModel? _optionRelic;
    private readonly List<RewardFrame> _frames=new();
    private readonly List<Receipt> _receipts=new();
    private readonly List<GenericEventV7PriorResult> _history=new();
    private readonly Harmony _hooks=new("sts.bridge.compound.rewards."+Guid.NewGuid().ToString("N"));
    private readonly MethodInfo _completeMethod;
    private readonly object _synchronizer;
    private readonly int _thread=Environment.CurrentManagedThreadId;
    private readonly long _deadline=Environment.TickCount64+300000;
    private RewardFrame? _published;
    private string? _decision;
    private int _generation,_reads,_attempts;
    private bool _failed,_disposed,_complete,_inside;
    internal RewardFrame Root {get;}
    public NRewardsScreen? Screen=>Root.Screen;
    public int OfferCount=>Root.Set.Rewards.Count;
    public string ContractVersion=>"full_rewards_v2";
    public bool InNativeScope=>Native.Value?.Owner==this;
    internal GenericEventCompoundRewards(GenericEventV7Binding binding,RewardsSet set)
    {
        _binding=binding;_optionRelic=binding.Option.Relic;Require(Active is null&&binding.ItemContextValid());
        _synchronizer=RunManager.Instance!.RewardsSetSynchronizer;
        _completeMethod=_synchronizer.GetType().GetMethod("CompleteRewardsSet",BindingFlags.Instance|BindingFlags.NonPublic)!;
        Require(_completeMethod is not null&&_completeMethod.GetParameters().Length==2&&_completeMethod.ReturnType==typeof(void)&&
            !(Harmony.GetPatchInfo(_completeMethod)?.Owners.Any()??false));
        Active=this;
        try{_hooks.Patch(_completeMethod,new HarmonyMethod(typeof(GenericEventCompoundRewards),nameof(Completing)));
            Root=new(this,set,null,null);_frames.Add(Root);}
        catch(Exception error) {
            Fail();
            try {
                _hooks.UnpatchAll(_hooks.Id);
                if(Harmony.GetPatchInfo(_completeMethod)?.Owners.Contains(_hooks.Id)==true)
                    throw new InvalidOperationException("compound_reward_constructor_cleanup");
                if(ReferenceEquals(Active,this))Active=null;
            } catch(Exception cleanup) {throw new AggregateException("compound_reward_constructor_cleanup",error,cleanup);}
            throw;
        }
    }
    private bool Context()=>!_failed&&!_disposed&&!_binding.Failed&&Environment.CurrentManagedThreadId==_thread&&
        Environment.TickCount64<=_deadline&&ReferenceEquals(Active,this)&&RemovalHooksValid()&&_binding.ItemContextValid()&&ReferenceEquals(_binding.Option.Relic,_optionRelic)&&
        _binding.ChosenTask?.IsFaulted!=true&&_binding.ChosenTask?.IsCanceled!=true&&
        ReferenceEquals(RunManager.Instance?.RewardsSetSynchronizer,_synchronizer)&&
        Harmony.GetPatchInfo(_completeMethod) is {} patches&&patches.Owners.Count==1&&patches.Owners.Contains(_hooks.Id);
    private void Fail(){_failed=true;_binding.Failed=true;}
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool good){if(!good){Fail();throw new InvalidOperationException("event_compound_reward_boundary");}}
    private RewardFrame[] Path(RewardFrame frame)
    {var path=new List<RewardFrame>();for(var f=frame;f is not null;f=f.Parent)path.Add(f);path.Reverse();return path.ToArray();}
    internal IDisposable EnterOffer(RewardsSet set,out RewardFrame frame)
    {
        Require(Context());
        if(!Root.OfferEntered){Require(ReferenceEquals(set,Root.Set)&&Native.Value is null);frame=Root;}
        else {
            var pickup=NativePickup;Require(pickup is not null&&InNativeScope&&_frames.Count<5);
            var parent=Native.Value!;Require(parent.Certificate is null&&parent.Pending is not null&&parent.Screen is not null&&
                !ReferenceEquals(parent.Set,set)&&_frames.All(f=>!ReferenceEquals(f.Set,set))&&CanOpenRewards(pickup!));
            BeforePickupAdvance(pickup!);Require(Expected(pickup!).Same(new(_binding.Player)));
            frame=new(this,set,parent,pickup);_frames.Add(frame);
        }
        Require(!frame.OfferEntered);frame.OfferEntered=true;
        var previous=Native.Value;Native.Value=frame;
        return new Lease(()=>Native.Value=previous);
    }
    internal RewardFrame CurrentFrame(){Require(Context()&&Native.Value is {} frame&&ReferenceEquals(frame.Owner,this));return Native.Value!;}
    public void Offering(Task task)=>Offering(CurrentFrame(),task);
    internal void Offering(RewardFrame frame,Task task){Require(Context()&&frame.Offer is null&&task is not null);frame.Offer=task;frame.Controller.Offering(task);}
    public void ScreenEntering(RewardsSet set,bool terminal,IRunState run)
    {var frame=CurrentFrame();Require(ReferenceEquals(frame.Set,set)&&frame.Screen is null);frame.Controller.ScreenEntering(set,terminal,run);}
    public void ScreenEntered(NRewardsScreen screen)=>ScreenEntered(CurrentFrame(),screen);
    internal void ScreenEntered(RewardFrame frame,NRewardsScreen screen)
    {Require(Context()&&frame.Screen is null);frame.Controller.ScreenEntered(screen);frame.Screen=screen;if(ReferenceEquals(frame,Root))_binding.ScreenSeen=true;}
    public void CollectionEntering(NRewardButton button)
    {
        var frame=CurrentFrame();Require(frame.Pending is not null&&!frame.Entered&&
            (frame.Collection is null||frame.Collection.IsCompletedSuccessfully)&&
            ReferenceEquals(frame.Controller.Reader?.InteractionSession.Pending?.ParentTarget?.Button,button));
        frame.Entered=true;frame.Collection=null;frame.Menu=null;frame.MenuTask=null;
    }
    public void CollectionReturned(Task task)=>CollectionReturned(CurrentFrame(),task);
    internal void CollectionReturned(RewardFrame frame,Task task)
    {Require(Context()&&frame.Entered&&frame.Collection is null&&task is not null);frame.Collection=task;frame.Collections.Add(task);}
    public void MenuEntering(IReadOnlyList<CardCreationResult> cards,IReadOnlyList<CardRewardAlternative> options)
    {
        var frame=CurrentFrame();Require(frame.Entered&&frame.Menu is null&&!frame.MenuEntering&&frame.Pending?.Action.StartsWith("open:",StringComparison.Ordinal)==true);
        var reward=frame.Controller.Reader!.InteractionSession.Pending?.ParentTarget?.Reward as CardReward;
        Require(reward is not null&&cards.Count is >=1 and <=5&&cards.Select(c=>c.Card).SequenceEqual(reward.Cards)&&options.Count is >=1 and <=3);frame.MenuEntering=true;
    }
    public void MenuEntered(NCardRewardSelectionScreen screen)=>MenuEntered(CurrentFrame(),screen);
    internal void MenuEntered(RewardFrame frame,NCardRewardSelectionScreen screen)
    {Require(Context()&&frame.MenuEntering&&frame.Menu is null);frame.Menu=screen;frame.MenuEntering=false;}
    public void TaskEntering(NCardRewardSelectionScreen screen)
    {
        var frame=CurrentFrame();Require(ReferenceEquals(frame.Menu,screen)&&!frame.TaskEntering&&
            (frame.MenuTask is null||frame.Pending?.Action=="reroll"&&frame.MenuTask.IsCompletedSuccessfully));frame.TaskEntering=true;
    }
    public void TaskEntered(Task<int?> task)=>TaskEntered(CurrentFrame(),task);
    internal void TaskEntered(RewardFrame frame,Task<int?> task)
    {Require(Context()&&frame.TaskEntering&&task is not null&&!ReferenceEquals(task,frame.MenuTask));frame.MenuTask=task;frame.TaskEntering=false;}
    private static object? Field(object value,string name)=>value.GetType().GetField(name,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)?.GetValue(value);
    private static void Completing(object __instance,object __0,object __1)
    {
        var owner=Active;if(owner is null)return;
        try {
            owner.Require(owner.Context()&&ReferenceEquals(__instance,owner._synchronizer));
            var frame=owner._frames.SingleOrDefault(f=>ReferenceEquals(f.Set,Field(__0,"set")));
            owner.Require(frame is not null&&frame.Certificate is null&&__1.GetType().IsEnum&&__1.ToString() is "Completed" or "Skipped");
            owner.BeforeRewardCertificate(frame!);
            var descendants=owner.ClosingDescendants(frame!);
            frame!.Controller.CertifyNativeCompletion(__instance,__0,__1.ToString()=="Skipped",descendants);
            frame.Certificate=new(owner._binding.Player);
            owner.RewardCertified(frame);
        }catch{owner.Fail();throw;}
    }
    private IPinnedClosingOverlay[] ClosingDescendants(RewardFrame frame)=>_frames.Where(f=>!f.Controller.Completed&&!ReferenceEquals(f,frame)&&Path(f).Contains(frame)&&f.Controller.EffectCertified&&
            f.Screen is not null&&!f.Controller.Ancestors.Closed(f.Screen))
        .Select(f=>(IPinnedClosingOverlay)f.Controller).Concat(ClosingOffers(frame)).Concat(ClosingDecks(frame)).ToArray();
    private void BeforeRewardCertificate(RewardFrame frame){foreach(var effect in _effects.Where(e=>ReferenceEquals(e.RewardFrame,frame)&&e.Active))Require(effect.Completed);}
    private void RewardCertified(RewardFrame frame)
    {if(frame.Pickup is {} pickup)AcceptRewardCertificate(pickup,frame);if(ReferenceEquals(frame,Root))PrepareParentTail();}
    private GenericEventV7RewardRead Value(string status,string phase,IReadOnlyList<string>? actions=null)=>new(_binding.Nonce,status,phase,status=="ready"?_decision!:"",
        Array.Empty<GenericEventV7RewardCard>(),false,actions??Array.Empty<string>(),_history.ToArray(),null);
    public GenericEventV7RewardRead Read()
    {
        if(_inside||_disposed||_failed){Fail();return Value("unsupported","unsupported");}_inside=true;
        try{return ReadCore();}catch{Fail();return Value("unsupported","unsupported");}finally{_inside=false;}
    }
    private GenericEventV7RewardRead ReadCore()
    {
        Require(Context()&&++_reads<=2048);
        ReleaseSettledPickups();
        if(_tailEffects is not null)Require(_tailEffects.Valid());
        if(_complete)return Value("resolved","complete");
        ReadOffers();ReadDecks();
        foreach(var frame in _frames)Require(frame.Offer?.IsFaulted!=true&&frame.Offer?.IsCanceled!=true&&
            frame.Collections.All(t=>!t.IsFaulted&&!t.IsCanceled)&&frame.MenuTask?.IsFaulted!=true&&frame.MenuTask?.IsCanceled!=true);
        foreach(var frame in _frames.Where(f=>f.Certificate is not null)) {
            if(!frame.Controller.Completed)frame.Controller.Read();
            if(frame.Controller.Completed&&frame.Collections.All(t=>t.IsCompletedSuccessfully)&&frame.Pending is {} closing){closing.Done=true;frame.Pending=null;}
        }
        while(_history.Count<_receipts.Count&&_receipts[_history.Count].Done){var r=_receipts[_history.Count];_history.Add(new(r.Decision,r.Action,"completed"));}
        if(Root.Controller.Completed) {
            if(_frames.Any(f=>!f.Controller.Completed||f.Collections.Any(t=>!t.IsCompletedSuccessfully))||_offers.Any(o=>o.View?.Status!="resolved")||_decks.Any(d=>!d.Done)||_binding.ChosenTask?.IsCompletedSuccessfully!=true||!ParentTailComplete())return Value("waiting","waiting");
            Require(_receipts.Count==_history.Count);_complete=true;return Value("resolved","complete");
        }
        if(_frames.Any(f=>f.Certificate is not null&&!f.Controller.Completed))return Value("waiting","waiting");
        var current=_frames.LastOrDefault(f=>f.Certificate is null);Require(current is not null);
        var leaf=ReadLeaf();if(leaf is not null)return leaf;
        current!.View=current.Controller.Read();
        if(current.View.Status==PublicDecisionStatus.Waiting)return Value("waiting","waiting");
        Require(current.View.Status==PublicDecisionStatus.Ready);
        if(current.View.ScreenKind=="card_reward")Require(current.Menu is not null&&current.MenuTask is {IsCompleted:false});
        if(current.Pending is {} pending) {
            bool native=pending.Action.StartsWith("open:",StringComparison.Ordinal)||pending.Action=="reroll"
                ?current.Entered&&current.Collection is not null&&current.MenuTask is {IsCompleted:false}
                :current.Collection is null||current.Collection.IsCompletedSuccessfully;
            if(current.View.DecisionRevision<=pending.Revision||!native)return Value("waiting","waiting");
            pending.Done=true;current.Pending=null;
            if(current.Pickup is {} pickup)_expected[pickup]=new(_binding.Player);
            while(_history.Count<_receipts.Count&&_receipts[_history.Count].Done){var r=_receipts[_history.Count];_history.Add(new(r.Decision,r.Action,"completed"));}
        }
        // Sacrifice currently owns its own Obtain observer. A nested pickup
        // already owns that boundary, so it cannot offer this input safely.
        var actions=current.View.LegalActions.Where(a=>a!="proceed"&&(a!="sacrifice"||current.Pickup is null)).ToList();if(current.Controller.CanDismiss(current.View))actions.Add("dismiss");
        Require(actions.Count>0&&actions.All(a=>GenericEventV7FullRewardRules.PhaseAction(current.View.ScreenKind,a,true)));
        Publish(current,current.View.DecisionId);return Value("ready",current.View.ScreenKind,actions);
    }
    private void Publish(RewardFrame frame,string nativeDecision)
    {
        _published=frame;_publishedOffer=null;_publishedDeck=null;
        _decision=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(ContractVersion+":"+_binding.Nonce+":"+_frames.IndexOf(frame)+":"+_generation+":"+nativeDecision))).ToLowerInvariant();
    }
    public GenericEventV7RewardReceipt Apply(string? decision,string? action)
    {
        GenericEventV7RewardReceipt Reply(string outcome)=>new(_binding.Nonce,decision??"",action??"",outcome);
        if(_inside||_disposed||_failed)return Reply("unsupported");_inside=true;
        try {
            var current=ReadCore();if(current.Status!="ready"||current.DecisionId!=decision||!current.LegalActions.Contains(action??""))return Reply("rejected");
            Require(++_attempts<=40&&Native.Value is null);
            if(ApplyLeaf(decision!,action!)){_generation++;return Reply("accepted");}
            var frame=_published!;Require(frame.Pending is null);
            var receipt=new Receipt(decision!,action!,frame.View.DecisionRevision,frame);frame.Pending=receipt;_receipts.Add(receipt);
            if(action!.StartsWith("open:",StringComparison.Ordinal)||action.StartsWith("claim:",StringComparison.Ordinal)||action.StartsWith("collect:",StringComparison.Ordinal)||action.StartsWith("take:",StringComparison.Ordinal))frame.Entered=false;
            Native.Value=frame;
            try{frame.Controller.Apply(frame.View.DecisionId,action);}finally{Native.Value=null;}
            ReleaseSettledPickups();
            _generation++;Require(Context());return Reply("accepted");
        }catch{Fail();return Reply("uncertain");}finally{_inside=false;}
    }
    internal (PinnedPublicRewardInteractionSession Session,PublicRewardDecisionSnapshot View) Inspect(string decision)
    {var read=Read();Require(read.Status=="ready"&&read.DecisionId==decision&&_published is not null);return(_published!.Controller.Reader!.InteractionSession,_published.View);}
    public void Dispose()
    {
        if(_disposed){Require(_complete&&!_failed);return;}
        Exception? failure=null;
        try{Require(!_inside&&_complete&&Context());}catch(Exception error){failure=error;}
        foreach(var frame in _frames.AsEnumerable().Reverse())try{frame.Controller.Dispose();}catch(Exception error){failure??=error;}
        try{DisposePickups();}catch(Exception error){failure??=error;}
        try{DisposeOffers();}catch(Exception error){failure??=error;}
        try{DisposeDecks();}catch(Exception error){failure??=error;}
        try{_tailAdds?.Dispose();}catch(Exception error){failure??=error;}
        try{_tailEffects?.Dispose();}catch(Exception error){failure??=error;}
        try{_hooks.UnpatchAll(_hooks.Id);Require(Harmony.GetPatchInfo(_completeMethod)?.Owners.Contains(_hooks.Id)!=true&&(_removeMethod is null||Harmony.GetPatchInfo(_removeMethod)?.Owners.Contains(_hooks.Id)!=true));}catch(Exception error){failure??=error;}
        _disposed=true;if(failure is not null){Fail();throw new InvalidOperationException("compound_reward_cleanup",failure);}Active=null;
    }
}
