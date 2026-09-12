using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Events.Custom.CrystalSphereEvent;
using MegaCrit.Sts2.Core.Nodes.Events.Custom.CrystalSphere;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// One owned event callback spans the board, generated rewards and native exit.
// Hidden item models, positions, textures and RNG are never inspected here.
internal sealed class GenericEventV7SphereSession:IGenericEventV7RewardChildSession {
    internal readonly GenericEventV7Binding Binding;
    private readonly CrystalSphereMinigame _game;
    internal NCrystalSphereScreen? Screen;
    private readonly CrystalSphereCell[,] _cells;
    private NCrystalSphereCell[]? _controls;
    private NButton? _small,_big;
    private NProceedButton? _proceed;
    private Control? _container;
    private bool[]? _fog;
    private int _count,_tool;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private Task? _click,_chosen,_collection;
    private readonly List<Task> _receipts=new();
    private readonly List<Task<IEnumerable<CardPileAddResult>>> _curses=new();
    private int _curseCalls;
    internal void CurseEntering(object player){Require(Context()&&ReferenceEquals(player,Binding.Player)&&_pending?.StartsWith("reveal:",StringComparison.Ordinal)==true&&++_curseCalls<=8);}
    internal void CurseReturned(Task<IEnumerable<CardPileAddResult>> task){Require(_curses.Count<_curseCalls&&!_curses.Contains(task));_curses.Add(task);}
    private readonly object _exitChoice=new();
    internal bool Exited {get;private set;}
    private bool _inside,_failed,_disposed,_cleanupFailed,_left;
    internal bool Completed {get;private set;}
    private string? _pending;
    private string _decision="",_acceptedDecision="";
    private GenericEventV7RewardRead? _published;
    private readonly List<GenericEventV7PriorResult> _history=new();
    private int _reads,_actions;
    private CardSelectionV1DeckCard[] _deck;
    private int _gold;
    private PotionModel?[] _potions;
    private RelicModel[] _relics;
    private RewardsSet? _set;
    private Reward[]? _rewards;
    internal Task? OfferTask;
    internal NRewardsScreen? RewardScreen;
    private PinnedPublicRewardDecisionReader? _reader;
    private PinnedPublicRewardActionApplier? _applier;
    private PublicRewardDecisionSnapshot _rewardView;
    private NRewardButton? _expectedButton;
    private NCardRewardSelectionScreen? _menu;
    private Task<int?>? _menuTask;
    private CardModel? _selectedCard;
    private int? _selectedResult;
    private Reward? _expectedReward;
    private int _goldGain;
    private PinnedPublicItemRewardClaim? _claim;
    private string?[] _potionKeys;
    private string[] _relicKeys;
    internal GenericEventV7SphereSession(GenericEventV7Binding b,CrystalSphereMinigame game) {
        Binding=b;_game=game;
        Require(b.ContextValid(false)&&ReferenceEquals(Field<object>(game,"_owner"),b.Player));
        _cells=Field<CrystalSphereCell[,]>(game,"cells");Require(_cells.GetLength(0)==11&&_cells.GetLength(1)==11);
        _deck=GenericEventV7Binding.CopyDeck(b.Player);_gold=b.Player.Gold;_potions=b.Player.PotionSlots.ToArray();_relics=b.Player.Relics.ToArray();_potionKeys=_potions.Select(p=>p?.Id.Entry).ToArray();_relicKeys=_relics.Select(r=>r.Id.Entry).ToArray();
    }
    internal static T Field<T>(object obj,string name)=>(T)(obj.GetType().GetField(name,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance)?.GetValue(obj)??throw new InvalidOperationException("Sphere binding missing."));
    private void Require(bool value,[System.Runtime.CompilerServices.CallerLineNumber]int line=0){if(!value){_failed=true;Binding.Failed=true;throw new InvalidOperationException("Crystal sphere ownership/effect lost at "+line);}}
    private static bool Valid(GodotObject? obj)=>obj is not null&&GodotObject.IsInstanceValid(obj);
    public string ContractVersion=>"crystal_sphere_v1";
    internal bool Admitted=>Screen is not null&&!_failed;
    internal void ScreenShown() {
        Require(Screen is null&&Binding.Overlays.ScreenCount==1&&Binding.Overlays.Peek() is NCrystalSphereScreen);
        Screen=(NCrystalSphereScreen)Binding.Overlays.Peek()!;Require(Screen.GetType()==typeof(NCrystalSphereScreen)&&ReferenceEquals(Field<object>(Screen,"_entity"),_game));
        _container=Screen.GetNodeOrNull<Control>("%Cells");_small=Screen.GetNodeOrNull<NButton>("%SmallDivinationButton");_big=Screen.GetNodeOrNull<NButton>("%BigDivinationButton");_proceed=Screen.GetNodeOrNull<NProceedButton>("%ProceedButton");
        Require(Valid(_container)&&Valid(_small)&&Valid(_big)&&Valid(_proceed));
        _controls=_container!.GetChildren().OfType<NCrystalSphereCell>().OrderBy(c=>c.Entity.Y*11+c.Entity.X).ToArray();Require(_controls.Length==121);
        _fog=Fog();_count=_game.DivinationCount;_tool=(int)_game.CrystalSphereTool;Require(_count is >=1 and <=20&&_tool is 1 or 2);
    }
    private bool[] Fog() {
        Require(ReferenceEquals(Field<object>(_game,"cells"),_cells));var fog=new bool[121];var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
        for(int i=0;i<121;i++){var cell=_cells[i%11,i/11];var control=_controls![i];Require(cell is not null&&seen.Add(cell)&&cell.X==i%11&&cell.Y==i/11&&Valid(control)&&ReferenceEquals(control.Entity,cell));fog[i]=cell!.IsHidden;}
        return fog;
    }
    private bool Context() {
        if(_disposed||_failed||Binding.Failed||Binding.Closed||System.Environment.CurrentManagedThreadId!=_thread||!GenericEventV7Hooks.Owns(Binding)||!Binding.ContextValid(true)||
            !ReferenceEquals(Field<object>(_game,"_owner"),Binding.Player)||Binding.Map.IsTraveling)return false;
        if(_chosen is not null&&!ReferenceEquals(_chosen,Binding.ChosenTask))return false;
        if(Binding.ChosenTask?.IsFaulted==true||Binding.ChosenTask?.IsCanceled==true||OfferTask?.IsFaulted==true||OfferTask?.IsCanceled==true||_receipts.Any(t=>!t.IsCompletedSuccessfully))return false;
        if(!_left&&(!ControlsBound()||!Valid(Screen)||!ReferenceEquals(Field<object>(Screen!,"_entity"),_game)||Binding.Map.IsOpen))return false;
        return true;
    }
    private bool ControlsBound()=>Screen is not null&&ReferenceEquals(Screen.GetNodeOrNull<Control>("%Cells"),_container)&&
        ReferenceEquals(Screen.GetNodeOrNull<NButton>("%SmallDivinationButton"),_small)&&ReferenceEquals(Screen.GetNodeOrNull<NButton>("%BigDivinationButton"),_big)&&ReferenceEquals(Screen.GetNodeOrNull<NProceedButton>("%ProceedButton"),_proceed)&&
        Valid(_container)&&_controls is not null&&_container!.GetChildren().OfType<NCrystalSphereCell>().OrderBy(c=>c.Entity.Y*11+c.Entity.X).SequenceEqual(_controls);
    private bool BaseOverlay(){var overlays=Field<System.Collections.IList>(Binding.Overlays,"_overlays");return overlays.Count>=1&&ReferenceEquals(overlays[0],Screen)&&(overlays.Count<2||ReferenceEquals(overlays[1],RewardScreen));}
    private bool Top(object value,int count)=>Binding.Overlays.ScreenCount==count&&ReferenceEquals(Binding.Overlays.Peek(),value);
    internal void OfferEntered(RewardsSet set) {Require(Context()&&_count>=0&&_set is null&&ReferenceEquals(set.Player,Binding.Player)&&!set.DisallowSkipping);_set=set;}
    internal void Offering(Task task){Require(_set is not null&&OfferTask is null);OfferTask=task;}
    internal void RewardScreenEntering(RewardsSet set,bool terminal,object run){Require(Context()&&ReferenceEquals(set,_set)&&!terminal&&ReferenceEquals(run,Binding.RunState)&&RewardScreen is null);}
    internal void RewardsShown(NRewardsScreen screen) {
        Require(Context()&&RewardScreen is null&&_set is not null&&_set.Rewards.Count is >=1 and <=8&&Top(screen,2));RewardScreen=screen;_rewards=_set!.Rewards.ToArray();
        Require(_rewards.Distinct(ReferenceEqualityComparer.Instance).Count()==_rewards.Length&&_rewards.All(r=>ReferenceEquals(r.Player,Binding.Player)&&!r.SuccessfullySelected&&r.IsPopulated&&r.ParentRewardSet is null&&r.GetType()==typeof(GoldReward)||ReferenceEquals(r.Player,Binding.Player)&&!r.SuccessfullySelected&&r.IsPopulated&&r.ParentRewardSet is null&&(r.GetType()==typeof(CardReward)||r.GetType()==typeof(PotionReward)||r.GetType()==typeof(RelicReward))));
        _reader=new(screen,RewardScope,RewardsClosed);_applier=new(_reader);
    }
    private bool RewardsClosed()=>OfferTask?.IsCompletedSuccessfully==true&&Top(Screen!,1);
    private bool RewardScope()=>Context()&&BaseOverlay()&&_set is not null&&_rewards is not null&&_set.Rewards.SequenceEqual(_rewards)&&
        (Top(RewardScreen!,2)||_menu is not null&&Top(_menu,3)||RewardsClosed());
    internal void CollectionEntering(NRewardButton button){Require(Context()&&ReferenceEquals(button,_expectedButton)&&_collection is null);}
    internal void CollectionReturned(Task task){Require(_expectedButton is not null&&_collection is null);_collection=task;}
    internal void MenuEntering(){Require(Context()&&_pending?.StartsWith("reward:open:",StringComparison.Ordinal)==true&&_menu is null);}
    internal void MenuShown(NCardRewardSelectionScreen menu){Require(_menu is null&&Top(menu,3));_menu=menu;}
    internal void MenuTaskEntering(NCardRewardSelectionScreen menu){Require(ReferenceEquals(menu,_menu)||_menu is null);}
    internal void MenuTaskReturned(Task<int?> task){Require(_menuTask is null);_menuTask=task;}
    private void Inventory(bool reward=false,bool reveal=false) {
        var player=Binding.Player;var now=GenericEventV7Binding.CopyDeck(player);int extra=now.Length-_deck.Length;
        Require(extra>=0&&(reveal?extra==_curses.Count&&_curseCalls==_curses.Count&&_curses.All(t=>t.IsCompletedSuccessfully):reward?extra<=1:extra==0));
        for(int i=0;i<_deck.Length;i++)Require(GenericEventV7Binding.SameDeckCard(_deck[i],now[i]));
        for(int i=0;i<now.Length;i++)Require(now[i].ModelIdentity is CardModel c&&ReferenceEquals(c.Owner,player)&&ReferenceEquals(c.RunState,Binding.RunState));
        for(int i=_deck.Length;i<now.Length;i++)Require(reveal?now[i].StableKey=="DOUBT"&&_curses[i-_deck.Length].Result.Count()==1&&_curses[i-_deck.Length].Result.Single().success&&ReferenceEquals(now[i].ModelIdentity,_curses[i-_deck.Length].Result.Single().cardAdded):ReferenceEquals(now[i].ModelIdentity,_selectedCard));
        bool collect=reward&&_pending?.StartsWith("reward:collect:",StringComparison.Ordinal)==true;
        int gain=reward&&_pending?.StartsWith("reward:claim:",StringComparison.Ordinal)==true?_goldGain:0;
        if(gain!=0)Require(_expectedReward is GoldReward gold&&gold.Amount==gain);
        Require(player.Gold==_gold+gain);
        if(collect)Require(_claim?.Completed==true);
        else Require(player.MaxPotionCount==_potions.Length&&player.PotionSlots.SequenceEqual(_potions)&&player.Relics.SequenceEqual(_relics));
        for(int i=0;i<_potions.Length;i++)Require(_potions[i]?.Id.Entry==_potionKeys[i]);
        for(int i=0;i<_relics.Length;i++)Require(_relics[i].Id.Entry==_relicKeys[i]);
        foreach(var relic in _relics)Require(ReferenceEquals(relic.Owner,player)&&player.Relics.Count(r=>ReferenceEquals(r,relic))==1);
        foreach(var potion in _potions)if(potion is not null)Require(ReferenceEquals(potion.Owner,player)&&player.PotionSlots.Count(p=>ReferenceEquals(p,potion))==1);
    }
    private void Baseline(){_deck=GenericEventV7Binding.CopyDeck(Binding.Player);_gold=Binding.Player.Gold;_potions=Binding.Player.PotionSlots.ToArray();_relics=Binding.Player.Relics.ToArray();_potionKeys=_potions.Select(p=>p?.Id.Entry).ToArray();_relicKeys=_relics.Select(r=>r.Id.Entry).ToArray();}
    private void Settled(){_history.Add(new(_acceptedDecision,_pending!,"completed"));_pending=null;_published=null;_decision="";}
    private GenericEventV7RewardRead Value(string status,string? phase=null,IReadOnlyList<string>? actions=null,GenericEventV7SphereView? board=null) =>new(Binding.Nonce,status,phase??status,status=="ready"?_decision:"",Array.Empty<GenericEventV7RewardCard>(),false,actions??Array.Empty<string>(),_history.ToArray(),null,Sphere:board);
    public GenericEventV7RewardRead Read() {
        if(_inside){_failed=true;return Value("unsupported");}_inside=true;
        try{return ReadCore();}catch{_failed=true;Binding.Failed=true;return Value("unsupported");}finally{_inside=false;}
    }
    private GenericEventV7RewardRead ReadCore() {
        Require(Context()&&++_reads<=512);_chosen??=Binding.ChosenTask;
        if(Completed)return Value("resolved","complete");
        if(_pending is {} pending) {
            if(pending.StartsWith("reveal:",StringComparison.Ordinal)) {
                Require(_click is not null&&!_click.IsFaulted&&!_click.IsCanceled);if(!_click!.IsCompleted)return Value("waiting");
                var f=Fog();int slot=int.Parse(pending.AsSpan(7));Require(_game.DivinationCount==_count-1&&(int)_game.CrystalSphereTool==_tool);
                for(int i=0;i<121;i++){bool clear=_tool==1?i==slot:Math.Abs(i%11-slot%11)<=1&&Math.Abs(i/11-slot/11)<=1;Require(f[i]==(_fog![i]&&!clear));}
                Inventory(reveal:true);_receipts.AddRange(_curses);_curses.Clear();_curseCalls=0;Baseline();_fog=f;_count=_game.DivinationCount;_receipts.Add(_click);_click=null;Settled();
            }else if(pending.StartsWith("tool:",StringComparison.Ordinal)) {
                Require(_game.DivinationCount==_count&&Fog().SequenceEqual(_fog!)&&(int)_game.CrystalSphereTool==(pending=="tool:big"?2:1));Inventory();_tool=(int)_game.CrystalSphereTool;Settled();
            }else if(pending=="proceed") {
                Require(_click is not null&&!_click.IsFaulted&&!_click.IsCanceled);if(!_click!.IsCompleted||!Binding.Map.IsOpen||!Binding.Map.IsTravelEnabled||Binding.Overlays.ScreenCount!=0)return Value("waiting");
                Inventory();Require(_chosen?.IsCompletedSuccessfully==true);_receipts.Add(_click);_click=null;Settled();Completed=true;return Value("resolved","complete");
            }else if(pending=="dismiss") {
                if(!RewardsClosed())return Value("waiting");Inventory();Settled();
            }else {
                Require(RewardScope()&&_reader is not null);
                bool opening=pending.StartsWith("reward:open:",StringComparison.Ordinal);
                if(_collection is not null){Require(!_collection.IsFaulted&&!_collection.IsCanceled);if(!opening&&!_collection.IsCompleted)return Value("waiting");}
                var result=_reader!.Read();Require(result.Status!=PublicDecisionStatus.Unsupported);
                if(result.Status==PublicDecisionStatus.Waiting||_reader.InteractionSession.Pending is not null)return Value("waiting");
                if(!opening&&_menuTask is not null)Require(_menuTask.IsCompletedSuccessfully&&_menuTask.Result==_selectedResult);
                Inventory(reward:true);Baseline();
                if(!opening){if(_collection is not null)_receipts.Add(_collection);_collection=null;_expectedButton=null;_menu=null;_menuTask=null;_selectedCard=null;}
                _rewardView=result;Settled();
            }
        }
        if(_count>0) {
            Require(Top(Screen!,1)&&Screen!.IsVisibleInTree()&&_game.DivinationCount==_count&&(int)_game.CrystalSphereTool==_tool&&Fog().SequenceEqual(_fog!));Inventory();
            var actions=new List<string>();
            if(_tool==1&&Enabled(_big))actions.Add("tool:big");
            for(int i=0;i<121;i++)if(_fog![i]&&Enabled(_controls![i]))actions.Add("reveal:"+i);
            if(_tool==2&&Enabled(_small))actions.Add("tool:small");
            return Ready("board",actions,new(_count,_tool==1?"small":"big",_fog!.ToArray(),Array.Empty<GenericEventV7SphereReward>()));
        }
        if(_reader is not null&&!RewardsClosed()) {
            Require(RewardScope());Inventory();var view=_reader.Read();Require(view.Status!=PublicDecisionStatus.Unsupported);if(view.Status!=PublicDecisionStatus.Ready)return Value("waiting");_rewardView=view;
            var actions=view.LegalActions.Select(a=>"reward:"+a).ToList();
            if(view.ScreenKind=="rewards"&&!_set!.DisallowSkipping&&_rewards!.All(r=>r.SuccessfullySelected||r is CardReward&&_reader.InteractionSession.WasSkipped(r))) {
                var dismiss=RewardScreen!.GetNodeOrNull<NProceedButton>("ProceedButton");if(Enabled(dismiss))actions.Add("dismiss");
            }
            Require(actions.Count>0);
            var rows=view.Rewards.Select((r,i)=>new GenericEventV7SphereReward(i,r.Kind.ToString().ToLowerInvariant(),r.ItemKey??"",r.GoldAmount,r.Cards.Select((key,j)=>ProjectRewardCard(view,i,j,key)).ToArray())).ToArray();
            return Ready(view.ScreenKind=="rewards"?"rewards":"cards",actions,new(0,_tool==1?"small":"big",_fog!.ToArray(),rows));
        }
        if(_set is not null)Require(OfferTask?.IsCompletedSuccessfully==true);
        if(_chosen?.IsCompletedSuccessfully!=true||!Binding.EventModel.IsFinished||!Enabled(_proceed)||!Top(Screen!,1)||!Binding.Map.IsTravelEnabled)return Value("waiting");
        Inventory();Completed=true;return Value("resolved","complete");
    }
    private GenericEventV7RewardCard ProjectRewardCard(PublicRewardDecisionSnapshot view,int rewardSlot,int cardSlot,string key) {
        CardModel model;
        if(view.ScreenKind=="rewards") {Require(_reader!.InteractionSession.TryGetParentTarget(view.DecisionId,rewardSlot,out _,out var target));model=target!.OfferedCards[cardSlot];}
        else {Require(_reader!.InteractionSession.TryGetCardTarget(view.DecisionId,cardSlot,out _,out var target));model=target!.Model;}
        Require(model.Id.Entry==key);return new(cardSlot,key,model.CurrentUpgradeLevel);
    }
    private static bool Enabled(Control? c)=>Valid(c)&&c!.IsVisibleInTree()&&(c is NClickableControl n&&n.IsEnabled||c is NProceedButton p&&p.IsEnabled);
    private GenericEventV7RewardRead Ready(string phase,IReadOnlyList<string> actions,GenericEventV7SphereView board) {
        Require(actions.Count is >=1 and <=123);
        string stamp=phase+":"+_actions+":"+board.Divinations+":"+board.Tool+":"+string.Join("",board.Hidden.Select(b=>b?'1':'0'))+":"+string.Join("|",actions)+":"+_rewardView.DecisionId+":"+string.Join("|",board.Rewards.Select(r=>r.Slot+":"+r.Kind+":"+r.Key+":"+r.Amount+":"+string.Join(",",r.Cards.Select(c=>c.Slot+":"+c.Key+":"+c.UpgradeLevel))));
        string decision=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(ContractVersion+":"+Binding.Nonce+":"+stamp))).ToLowerInvariant();
        if(_published is not null)Require(_decision==decision);_decision=decision;return _published=Value("ready",phase,actions,board);
    }
    public GenericEventV7RewardReceipt Apply(string? decision,string? action) {
        GenericEventV7RewardReceipt Receipt(string result)=>new(Binding.Nonce,decision??"",action??"",result);
        if(_inside||_pending is not null||_disposed)return Receipt("rejected");
        var read=Read();if(read.Status!="ready"||decision!=read.DecisionId||!read.LegalActions.Contains(action??""))return Receipt("rejected");
        try {
            Require(++_actions<=40);_pending=action;_acceptedDecision=decision!;_published=null;
            if(action=="tool:small")_small!.ForceClick();else if(action=="tool:big")_big!.ForceClick();
            else if(action!.StartsWith("reveal:",StringComparison.Ordinal)) {
                int slot=int.Parse(action.AsSpan(7));var previous=GenericEventV7Hooks.SphereClick.Value;GenericEventV7Hooks.SphereClick.Value=this;
                try{_click=(Task)typeof(NCrystalSphereScreen).GetMethod("OnCellClicked",BindingFlags.Instance|BindingFlags.NonPublic)!.Invoke(Screen,new object[]{_controls![slot]})!;}finally{GenericEventV7Hooks.SphereClick.Value=previous;}
            }else if(action=="proceed") {
                _left=true;_click=(Task)typeof(MegaCrit.Sts2.Core.Runs.RunManager).GetMethod("ProceedFromTerminalRewardsScreen")!.Invoke(MegaCrit.Sts2.Core.Runs.RunManager.Instance,null)!;
            }else if(action=="dismiss") {RewardScreen!.GetNodeOrNull<NProceedButton>("ProceedButton")!.ForceClick();}
            else {
                string native=action[7..];Require(PublicRewardActionRequest.TryCreate(_rewardView.DecisionId,native,out var request));
                if(request.Kind is PublicRewardActionKind.ClaimGold or PublicRewardActionKind.OpenCard or PublicRewardActionKind.CollectItem) {
                    Require(_reader!.InteractionSession.TryGetParentTarget(request.DecisionId,request.RewardSlot,out _,out var target));_expectedButton=target!.Button;_expectedReward=target.Reward;_goldGain=target.Reward is GoldReward gold?gold.Amount:0;if(request.Kind==PublicRewardActionKind.CollectItem)_claim=new(target.Reward);
                }
                if(request.Kind==PublicRewardActionKind.ChooseCard){Require(_reader!.InteractionSession.TryGetCardTarget(request.DecisionId,request.CardSlot,out _,out var target));_selectedCard=target!.Model;_selectedResult=request.CardSlot;}
                if(request.Kind==PublicRewardActionKind.SkipCard)_selectedResult=_reader!.InteractionSession.ActiveCardReward!.OfferedCards.Count;
                Require(_applier!.Apply(request).Outcome==PublicRewardActionApplyOutcome.Accepted);
                if(request.Kind is PublicRewardActionKind.ClaimGold or PublicRewardActionKind.OpenCard or PublicRewardActionKind.CollectItem)Require(_collection is not null);
            }
            return Receipt("accepted");
        }catch{_failed=true;Binding.Failed=true;return Receipt("uncertain");}
    }
    internal GenericEventV7NativeCapture CaptureExit() {
        Require(Context()&&Completed&&_chosen?.IsCompletedSuccessfully==true);Inventory();
        if(_left) {
            Require(_click is not null&&!_click.IsFaulted&&!_click.IsCanceled);
            if(!_click!.IsCompleted||!Binding.Map.IsOpen||!Binding.Map.IsTravelEnabled)return new("waiting",false,Array.Empty<GenericEventV7NativeOption>());
            // Native Proceed opens the map without removing this completed overlay.
            // Only its exact retained instance may pass to parent-owned disposal.
            Require(Binding.Overlays.ScreenCount==0||Top(Screen!,1)&&Valid(Screen)&&ControlsBound()&&ReferenceEquals(Field<object>(Screen!,"_entity"),_game));
            Exited=true;return new("map",false,Array.Empty<GenericEventV7NativeOption>());
        }
        Require(Top(Screen!,1));return new("parent",true,new[]{new GenericEventV7NativeOption(_exitChoice,"CRYSTAL_SPHERE.LEAVE","Leave",Enabled(_proceed)&&Binding.Map.IsTravelEnabled,false,true)});
    }
    internal void DispatchExit(object identity) {
        Require(ReferenceEquals(identity,_exitChoice)&&!_left&&CaptureExit().Options.Single().Enabled);
        _left=true;_click=(Task)typeof(MegaCrit.Sts2.Core.Runs.RunManager).GetMethod("ProceedFromTerminalRewardsScreen")!.Invoke(MegaCrit.Sts2.Core.Runs.RunManager.Instance,null)!;
    }
    // The parent owns cleanup through its separate native exit.
    public void Dispose(){ }
    internal void DisposeOwner() {
        if(_cleanupFailed)throw new InvalidOperationException("Sphere cleanup previously failed.");if(_disposed)return;
        if(!Exited){_cleanupFailed=true;throw new InvalidOperationException("Crystal sphere callback or exit is unresolved.");}
        try {
            Require(Context()&&Binding.Map.IsOpen&&Binding.Map.IsTravelEnabled&&_click?.IsCompletedSuccessfully==true);Inventory();
            if(Binding.Overlays.ScreenCount!=0) {
                Require(Top(Screen!,1)&&Valid(Screen)&&ControlsBound()&&ReferenceEquals(Field<object>(Screen!,"_entity"),_game));
                // Set the sticky guard before native cleanup: failure must never retry removal.
                _cleanupFailed=true;
                Binding.Overlays.Remove(Screen!);
            }
            Require(Context()&&Binding.Overlays.ScreenCount==0&&Binding.Map.IsOpen&&Binding.Map.IsTravelEnabled);Inventory();
            _reader?.Dispose();_disposed=true;_cleanupFailed=false;
        }catch{_cleanupFailed=true;throw;}
    }
}
