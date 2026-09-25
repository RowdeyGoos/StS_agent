using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
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

// The event owns Offer and every native collection task. The shared reward
// reader owns the individual inventory effects and visible reward controls.
internal sealed class GenericEventFullRewards : IGenericFullRewardSession
{
    private static readonly AsyncLocal<GenericEventFullRewards?> Scope=new();
    private readonly GenericEventV7Binding _binding;
    private readonly RestRewardContinuation _child;
    private readonly int _thread=Environment.CurrentManagedThreadId;
    private readonly List<GenericEventV7PriorResult> _history=new();
    private Task? _offer,_collection;
    private NCardRewardSelectionScreen? _menu;
    private Task<int?>? _menuTask;
    private CardReward? _menuReward;
    private PublicRewardDecisionSnapshot _view;
    private string? _pending,_pendingDecision;
    private int _revision,_reads,_attempts;
    private bool _entered,_menuEntering,_taskEntering,_failed,_disposed,_complete,_inside;
    private long _deadline;
    public NRewardsScreen? Screen {get;private set;}
    public int OfferCount {get;private set;}
    public string ContractVersion=>"full_rewards_v1";
    public bool InNativeScope=>ReferenceEquals(Scope.Value,this);
    internal GenericEventFullRewards(GenericEventV7Binding binding,RewardsSet set)
    {
        _binding=binding;
        _child=new(set,binding.Player,binding.Overlays,Context,
            (parent,screen)=>new PinnedRewardAlternatives(parent,screen),
            player=>new PinnedRewardInventory(player),PinnedRelicRewardEffect.Create);
    }
    private bool Context()=>!_failed&&!_disposed&&!_binding.Failed&&Environment.CurrentManagedThreadId==_thread&&
        (_deadline==0||Environment.TickCount64<=_deadline)&&_binding.ItemContextValid()&&
        _binding.ChosenTask?.IsFaulted!=true&&_binding.ChosenTask?.IsCanceled!=true;
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool good){if(!good){_failed=true;_binding.Failed=true;throw new InvalidOperationException("event_full_reward_boundary");}}
    public void Offering(Task task){Require(Context()&&_offer is null&&task is not null);_offer=task;_child.Offering(task);}
    public void ScreenEntering(RewardsSet set,bool terminal,IRunState run){Require(Context()&&Screen is null&&!_binding.ScreenSeen);_binding.ScreenSeen=true;_child.ScreenEntering(set,terminal,run);OfferCount=set.Rewards.Count;}
    public void ScreenEntered(NRewardsScreen screen){Require(Context()&&Screen is null);_child.ScreenEntered(screen);Screen=screen;}
    public void CollectionEntering(NRewardButton button)
    {
        Require(Context()&&InNativeScope&&_pending is not null&&!_entered&&
            (_collection is null||_collection.IsCompletedSuccessfully)&&
            ReferenceEquals(_child.Reader?.InteractionSession.Pending?.ParentTarget?.Button,button));
        _entered=true;_collection=null;_menu=null;_menuTask=null;_menuReward=null;
    }
    public void CollectionReturned(Task task){Require(Context()&&InNativeScope&&_entered&&_collection is null&&task is not null);_collection=task;}
    public void MenuEntering(IReadOnlyList<CardCreationResult> cards,IReadOnlyList<CardRewardAlternative> options)
    {
        Require(Context()&&InNativeScope&&_entered&&_menu is null&&!_menuEntering&&_pending?.StartsWith("open:",StringComparison.Ordinal)==true);
        _menuReward=_child.Reader!.InteractionSession.Pending?.ParentTarget?.Reward as CardReward;
        Require(_menuReward is not null&&cards.Select(c=>c.Card).SequenceEqual(_menuReward.Cards)&&cards.Count is >=1 and <=5&&options.Count is >=1 and <=3);
        _menuEntering=true;
    }
    public void MenuEntered(NCardRewardSelectionScreen screen){Require(Context()&&InNativeScope&&_menuEntering&&_menu is null);_menu=screen;_menuEntering=false;}
    public void TaskEntering(NCardRewardSelectionScreen screen)
    {
        Require(Context()&&InNativeScope&&ReferenceEquals(_menu,screen)&&!_taskEntering&&
            (_menuTask is null||_pending=="reroll"&&_menuTask.IsCompletedSuccessfully));
        _taskEntering=true;
    }
    public void TaskEntered(Task<int?> task){Require(Context()&&InNativeScope&&_taskEntering&&task is not null&&!ReferenceEquals(task,_menuTask));_menuTask=task;_taskEntering=false;}
    private GenericEventV7RewardRead Value(string status,string phase,IReadOnlyList<string>? actions=null)=>
        new(_binding.Nonce,status,phase,status=="ready"?_view.DecisionId:"",Array.Empty<GenericEventV7RewardCard>(),false,
            actions??Array.Empty<string>(),_history.ToArray(),null);
    public GenericEventV7RewardRead Read()
    {
        if(_inside||_disposed||_failed){_failed=true;_binding.Failed=true;return Value("unsupported","unsupported");}
        _inside=true;
        try{return ReadCore();}catch{_failed=true;_binding.Failed=true;return Value("unsupported","unsupported");}finally{_inside=false;}
    }
    private GenericEventV7RewardRead ReadCore()
    {
        Require(Context()&&++_reads<=1024&&_collection?.IsFaulted!=true&&_collection?.IsCanceled!=true&&_menuTask?.IsFaulted!=true&&_menuTask?.IsCanceled!=true);
        if(_complete)return Value("resolved","complete");
        _view=_child.Read();
        if(_view.Status==PublicDecisionStatus.Waiting&&!_child.Completed)return Value("waiting","waiting");
        if(_view.ScreenKind=="card_reward")Require(_menu is not null&&_menuTask is {IsCompleted:false});
        if(_pending is not null) {
            bool effectDone=_child.Completed||_view.Status==PublicDecisionStatus.Ready&&_view.DecisionRevision>_revision;
            bool nativeDone=_pending.StartsWith("open:",StringComparison.Ordinal)||_pending=="reroll" ? _entered&&_collection is not null&&_menuTask is {IsCompleted:false} : _collection is null||_collection.IsCompletedSuccessfully;
            if(!effectDone||!nativeDone)return Value("waiting","waiting");
            _history.Add(new(_pendingDecision!,_pending,"completed"));_pending=null;_pendingDecision=null;_deadline=0;
        }
        if(_child.Completed) {
            if(_offer?.IsCompletedSuccessfully!=true||_binding.ChosenTask?.IsCompletedSuccessfully!=true)return Value("waiting","waiting");
            _complete=true;return Value("resolved","complete");
        }
        Require(_view.Status==PublicDecisionStatus.Ready);
        var actions=_view.LegalActions.Where(a=>a!="proceed").ToList();if(_child.CanDismiss(_view))actions.Add("dismiss");
        Require(actions.Count>0&&actions.All(GenericEventV7FullRewardRules.Action));
        return Value("ready",_view.ScreenKind,actions);
    }
    public GenericEventV7RewardReceipt Apply(string? decision,string? action)
    {
        GenericEventV7RewardReceipt Receipt(string outcome)=>new(_binding.Nonce,decision??"",action??"",outcome);
        if(_inside||_disposed||_failed)return Receipt("unsupported");
        _inside=true;
        try {
            var current=ReadCore();
            if(current.Status!="ready"||current.DecisionId!=decision||!current.LegalActions.Contains(action??""))return Receipt("rejected");
            Require(_pending is null&&++_attempts<=40&&Scope.Value is null);
            _pending=action;_pendingDecision=decision;_revision=_view.DecisionRevision;_deadline=Environment.TickCount64+15000;
            if(action!.StartsWith("open:",StringComparison.Ordinal)||action.StartsWith("claim:",StringComparison.Ordinal)||action.StartsWith("collect:",StringComparison.Ordinal)||action.StartsWith("take:",StringComparison.Ordinal))_entered=false;
            Scope.Value=this;try{_child.Apply(decision!,action);}finally{Scope.Value=null;}
            Require(Context());return Receipt("accepted");
        } catch {_failed=true;_binding.Failed=true;return Receipt("uncertain");}
        finally {_inside=false;}
    }
    internal (PinnedPublicRewardInteractionSession Session,PublicRewardDecisionSnapshot View) Inspect(string decision)
    {var current=Read();Require(current.Status=="ready"&&current.DecisionId==decision&&_pending is null);return (_child.Reader!.InteractionSession,_view);}
    public void Dispose()
    {
        if(_disposed){Require(_complete&&!_failed);return;}
        try{Require(!_inside&&Environment.CurrentManagedThreadId==_thread);try{Require(_complete&&!_failed);}finally{_child.Dispose();}}
        catch{_failed=true;_binding.Failed=true;throw;}
        finally{_disposed=true;}
    }
}
