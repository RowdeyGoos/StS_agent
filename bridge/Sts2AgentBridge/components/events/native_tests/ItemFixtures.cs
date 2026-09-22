using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.CardSelectionV1;

internal static partial class Program
{
    private sealed class UnknownItemReward:Reward { internal int Reads; public override bool IsPopulated {get{Reads++;throw new InvalidOperationException("unreviewed getter");}set{}} }
    private sealed class DerivedRewardButton:NRewardButton{}
    private sealed class FirstItemEvent:EventModel{}
    private sealed class AnotherItemEvent:EventModel{}
    private sealed class HeldOutItemEvent:EventModel{}
    internal sealed class ItemFixture:IDisposable
    {
        private readonly TransformFixture _world;
        internal Player Player=>_world.Player;
        internal EventModel Model=>_world.Model;
        internal NEventRoom Room=>_world.Room;
        internal NMapScreen Map=>_world.Map;
        internal NOverlayStack Overlays=>_world.Overlays;
        internal NRun Run=>_world.Run;
        internal GenericEventV7Session Session=>_world.Session;
        internal NRewardsScreen Screen=null!;
        internal NRewardButton Button=null!;
        internal Reward Reward=null!;
        internal RewardsSet Set=null!;
        internal object Offered=null!;
        private readonly string _name,_kind;
        private readonly string[]? _itemKinds;
        internal readonly List<NRewardButton> Buttons=new();
        private readonly int _index,_repeat;
        private readonly bool _creation,_collection,_offer,_chosen,_mixed;
        private readonly Func<Task> _transform;
        private TaskCompletionSource _creationGate=new(),_collectionGate=new(),_offerGate=new(),_chosenGate=new(),_screenDone=new();
        private int _itemOptionCalls;
        internal int OptionCalls=>_itemOptionCalls+_world.OptionCalls;
        internal int CollectCalls,ItemCompletions;
        internal int SelectCalls=>_world.SelectCalls;
        internal int ConfirmCalls=>_world.ConfirmCalls;
        internal bool HasPendingCreation,HasPendingCollection,HasPendingOffer,HasPendingChosen;
        internal bool Terminal,ExtraReward,HiddenExtraButton,Linked,WrongPlayer,WrongRun,Shortcut,DuplicateScreen,FaultCollection,FaultOffer,FaultChosen,CancelCollection,CancelOffer,CancelChosen;
        internal Action? BeforeScreen=null,AfterScreen=null,BeforeCollection=null,AfterCollection=null;
        internal bool DisableDuringRelease,DerivedButton,PolicyInventory;
        internal readonly List<Reward> CompletedRewards=new();
        internal readonly List<Task> CollectionTasks=new();
        internal ItemFixture(string name,string kind,int index=7,bool delayedCreation=false,bool delayedCollection=false,bool delayedOffer=false,bool delayedChosen=false,int repeatItems=1,bool mixed=false,int? transformMinimum=null,int transformMaximum=1,string[]? itemKinds=null)
        {
            _name=name;_kind=kind;_itemKinds=itemKinds;_index=index;_repeat=repeatItems;_creation=delayedCreation;_collection=delayedCollection;_offer=delayedOffer;_chosen=delayedChosen;_mixed=mixed;
            EventModel model=name=="FIRST_ITEM"?new FirstItemEvent():name=="ANOTHER_ITEM"?new AnotherItemEvent():new HeldOutItemEvent();
            _world=new TransformFixture("ITEM_WORLD",transformMaximum,manual:transformMinimum is not null,nonce:new string('e',32),eventModel:model,minimum:transformMinimum);
            _transform=Room.Layout.OptionButtons[0].Option.Callback;
            var existing=new PotionModel();existing.Id.Entry="ExistingPotion";Player.PotionSlots[0]=existing;
            NRewardsScreen.Factory=(set,terminal,run)=>{
                Screen=new NRewardsScreen();Buttons.Clear();
                foreach(var reward in set.Rewards) {
                    var button=DerivedButton?new DerivedRewardButton{Reward=reward}:new NRewardButton{Reward=reward};
                    Screen.Children.Add(button);Buttons.Add(button);
                    button.Handler=()=>CollectEntry(reward,button);
                    button.DispatchOverride=()=>{if(DisableDuringRelease)button.IsEnabled=false;button.LastTask=button.ForeignGetReward();if(button.LastTask is not null)CollectionTasks.Add(button.LastTask);};
                }
                Button=Buttons[0];
                if(HiddenExtraButton)Screen.Children.Add(new NRewardButton{Reward=Reward,Visible=false});
                if(!set.DisallowSkipping)Screen.BindProceed(new MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton{IsEnabled=true,Clicked=()=>{Overlays.Screens.Clear();Screen.Visible=false;Screen.InstanceValid=false;_screenDone.SetResult();}});
                Overlays.Screens.Add(Screen);AfterScreen?.Invoke();return Screen;
            };
            ShowItem();
        }
        private void AddOption(EventOption option)
        {var button=new NEventOptionButton{Event=Model,Option=option};button.Bind("%Text",new MegaRichTextLabel{Text="Generic item option"});Room.Layout.OptionButtons.Add(button);}
        private void ShowItem()
        {
            Model.IsFinished=false;Room.Layout.OptionButtons.Clear();
            _creationGate=new();_collectionGate=new();_offerGate=new();_chosenGate=new();_screenDone=new();
            if(_kind=="potion"){var model=new PotionModel();model.Id.Entry="OfferedPotion";Offered=model;Reward=new PotionReward{Potion=model,Player=Player,RewardsSetIndex=_index};}
            else{var model=new RelicModel();model.Id.Entry="OfferedRelic";Offered=model;Reward=new RelicReward{Relic=model,Player=Player,RewardsSetIndex=_index};}
            Set=new RewardsSet{Player=Player,DisallowSkipping=true};Set.OfferHandler=Offer;
            AddOption(new EventOption{TextKey=_name+".ITEM",Callback=async()=>{
                _itemOptionCalls++;await Set.Offer();
                if(_chosen){HasPendingChosen=true;await _chosenGate.Task;HasPendingChosen=false;}
                if(CancelChosen)throw new OperationCanceledException();if(FaultChosen)throw new InvalidOperationException("chosen fault");
                if(_mixed&&ItemCompletions==1){_world.AfterUpgrade=ShowTransform;_world.ShowUpgradeOption();}
                else if(!PolicyInventory&&ItemCompletions<_repeat)ShowItem();else ShowProceed();
            }});
        }
        private void ShowTransform()
        {Room.Layout.OptionButtons.Clear();AddOption(new EventOption{TextKey="ITEM.MIXED.TRANSFORM",Callback=async()=>{await _transform();ShowItem();}});}
        private void ShowProceed()
        {Model.IsFinished=true;Room.Layout.OptionButtons.Clear();AddOption(new EventOption{TextKey="PROCEED",IsProceed=true,Callback=()=>{_itemOptionCalls++;Map.IsOpen=true;Map.IsTravelEnabled=true;return Task.CompletedTask;}});}
        private async Task Offer()
        {
            if(_creation){HasPendingCreation=true;await _creationGate.Task;HasPendingCreation=false;}
            // Real Offer may generate asynchronously; list is empty at request entry.
            if(Linked)Reward.ParentRewardSet=new LinkedRewardSet();
            if(WrongPlayer)Reward.Player=new Player();
            Set.Rewards.Add(Reward);
            if(_itemKinds is not null)for(int i=1;i<_itemKinds.Length;i++) {
                if(_itemKinds[i]=="potion"){var potion=new PotionModel();potion.Id.Entry="OfferedPotion";Set.Rewards.Add(new PotionReward{Player=Player,Potion=potion,RewardsSetIndex=2});}
                else{var relic=new RelicModel();relic.Id.Entry="OfferedRelic";Set.Rewards.Add(new RelicReward{Player=Player,Relic=relic,RewardsSetIndex=3});}
            }
            if(ExtraReward)for(int i=0;i<8;i++)Set.Rewards.Add(new RelicReward{Player=Player,Relic=new RelicModel(),RewardsSetIndex=3});
            BeforeScreen?.Invoke();if(Shortcut)return;
            NRewardsScreen.ShowScreen(Set,Terminal,WrongRun?new MegaCrit.Sts2.Core.Runs.FixtureRunState():Player.RunState);
            if(DuplicateScreen)NRewardsScreen.ShowScreen(Set,false,Player.RunState);
            await _screenDone.Task;
            if(_offer){HasPendingOffer=true;await _offerGate.Task;HasPendingOffer=false;}
            if(CancelOffer)throw new OperationCanceledException();if(FaultOffer)throw new InvalidOperationException("offer fault");
        }
        private async Task CollectEntry(Reward reward,NRewardButton button)
        {
            CollectCalls++;BeforeCollection?.Invoke();
            if(_collection){HasPendingCollection=true;await _collectionGate.Task;HasPendingCollection=false;}
            if(CancelCollection)throw new OperationCanceledException();if(FaultCollection)throw new InvalidOperationException("collection fault");
            if(reward is PotionReward p){p.ClaimedPotion=p.Potion;int at=Player.PotionSlots.FindIndex(x=>x is null);if(at>=0)Player.PotionSlots[at]=p.Potion;}
            else{var r=(RelicReward)reward;r.ClaimedRelic=r.Relic;}
            if(PolicyInventory) {
                if(reward is PotionReward ownedPotion)ownedPotion.Potion.Owner=Player;
                else if(reward is RelicReward ownedRelic && ownedRelic.Relic is not MegaCrit.Sts2.Core.Models.Relics.PotionBelt){ownedRelic.Relic.Owner=Player;Player.Relics.Add(ownedRelic.Relic);}
            }
            reward.SuccessfullySelected=true;ItemCompletions++;CompletedRewards.Add(reward);
            // Native reward claimed removes/frees its control and nonterminal screen.
            Screen.Children.Remove(button);button.InstanceValid=false;
            bool done=Set.Rewards.All(x=>x.SuccessfullySelected);
            if(done){Overlays.Screens.Clear();Screen.Visible=false;Screen.InstanceValid=false;}
            AfterCollection?.Invoke();if(done)_screenDone.SetResult();
        }
        internal void AdvanceCreation(){_creationGate.SetResult();}
        internal void AdvanceCollection(){_collectionGate.SetResult();}
        internal void AdvanceOffer(){_offerGate.SetResult();}
        internal void AdvanceChosen(){_chosenGate.SetResult();}
        internal bool CompletionValid=>ItemCompletions==CompletedRewards.Count&&CompletedRewards.All(r=>r.SuccessfullySelected&&
            (r is PotionReward p&&ReferenceEquals(p.ClaimedPotion,p.Potion)&&Player.PotionSlots.Any(s=>ReferenceEquals(s,p.Potion))||
             r is RelicReward relic&&ReferenceEquals(relic.ClaimedRelic,relic.Relic)))&&(!_mixed||_world.CompletionValid&&_world.UpgradedOriginals.Count==2);
        internal GenericEventV7Observation Start(){var p=Session.Read();Check(p.Status=="ready","item parent ready");Check(Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","item parent dispatched");return Session.Read();}
        internal IItemV1ReadValue Child(GenericEventV7Observation c)=>((GenericEventV7ItemRead)Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
        internal IItemV1ApplyValue Collect(GenericEventV7Observation c)
        {var o=(ItemV1Observation)Child(c);Check(o.Status=="ready","item local ready");return ((GenericEventV7ItemApply)Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,"collect:"+_index)).Value;}
        public void Dispose(){RewardsSet.testSelector=null;NRewardsScreen.Factory=null;_world.Dispose();}
    }
    private static void ItemTests()
    {
        foreach(string name in new[]{"FIRST_ITEM","ANOTHER_ITEM","HELD_OUT_ITEM"})foreach(string kind in new[]{"potion","relic"})foreach(int index in new[]{0,7,255})
        {
            using var f=new ItemFixture(name,kind,index);RetireBeforeChosen(f.Room.Layout);var c=f.Start();Check(c.Status=="child"&&c.Child!.Kind=="item","owned singleton item");
            Check(f.Collect(c) is ItemV1DispatchReceipt,"item accepted");Check(f.Child(c) is ItemV1ResolvedResult,"item resolved");Check(f.CompletionValid,"exact item effect");
            var p=f.Session.Read();Check(p.CompletedItemChildren==1&&p.CompletedCardChildren==0&&p.Phase=="proceed","item counter");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete"&&f.OptionCalls==2&&f.CollectCalls==1,"item complete dispatch counts");
        }
        using(var f=new ItemFixture("DERIVED_BUTTON","relic")){f.DerivedButton=true;var c=f.Start();Check(f.Collect(c) is ItemV1DispatchReceipt,"typed derived reward control");Check(f.Child(c) is ItemV1ResolvedResult,"derived control exact owned collection");}
        using(var f=new ItemFixture("RELEASE_DISABLED","relic")){f.DisableDuringRelease=true;var c=f.Start();Check(f.Collect(c) is ItemV1DispatchReceipt,"release may disable exact ticket");Check(f.Child(c) is ItemV1ResolvedResult,"disabled release resolves");}
        using(var f=new ItemFixture("DELAYED","potion",delayedCreation:true,delayedCollection:true,delayedOffer:true,delayedChosen:true))
        {
            Check(f.Set.Rewards.Count==0,"initial empty pre-generation domain");Check(f.Start().Status=="waiting","generation waiting");f.AdvanceCreation();var c=f.Session.Read();Check(c.Status=="child","generated singleton admitted");f.Collect(c);
            Check(f.Child(c) is ItemV1Observation o&&o.Status=="waiting","collection pending");f.AdvanceCollection();Check(f.Child(c) is ItemV1Observation a&&a.Status=="waiting","offer pending after freed controls");f.AdvanceOffer();Check(f.Child(c) is ItemV1Observation b&&b.Status=="waiting","chosen pending");f.AdvanceChosen();Check(f.Child(c) is ItemV1ResolvedResult&&f.CompletionValid,"all actual tasks finish");
        }
        using(var f=new ItemFixture("UNKNOWN_KIND","relic")){var unknown=new UnknownItemReward{Player=f.Player};f.Reward=unknown;Check(f.Start().Status=="unsupported"&&unknown.Reads==0&&f.Overlays.ScreenCount==1,"unsupported reward getter never observed and original screen runs");}
        foreach(string bad in new[]{"extra","linked","terminal","test","wrong_player","wrong_run","shortcut","duplicate","full","hidden"})
        {
            using var f=new ItemFixture("BAD_"+bad,"potion");
            if(bad=="extra")f.ExtraReward=true;if(bad=="linked")f.Linked=true;if(bad=="terminal")f.Terminal=true;if(bad=="test")RewardsSet.testSelector=_=>Task.CompletedTask;
            if(bad=="wrong_player")f.WrongPlayer=true;if(bad=="wrong_run")f.WrongRun=true;if(bad=="shortcut")f.Shortcut=true;if(bad=="duplicate")f.DuplicateScreen=true;if(bad=="hidden")f.HiddenExtraButton=true;
            if(bad=="full")for(int i=0;i<f.Player.PotionSlots.Count;i++)f.Player.PotionSlots[i]=f.Player.PotionSlots[0];
            var c=f.Start();if(bad=="hidden")for(int i=0;i<260&&c.Status=="waiting";i++)c=f.Session.Read();
            Check(c.Status=="unsupported"&&f.CollectCalls==0,"item exclusion "+bad);
        }
        foreach(string mutation in new[]{"model","key","claim","owner","domain","potion","capacity","foreground"})
        {
            using var f=new ItemFixture("MUTATION","potion",delayedOffer:true);var c=f.Start();f.Collect(c);Check(f.Child(c) is ItemV1Observation,"local effect waits Offer");
            var reward=(PotionReward)f.Reward;
            if(mutation=="model")reward.Potion=new PotionModel();if(mutation=="key")reward.Potion.Id.Entry="Changed";if(mutation=="claim")reward.ClaimedPotion=new PotionModel();if(mutation=="owner")reward.Player=new Player();if(mutation=="domain")f.Set.Rewards.Clear();if(mutation=="potion")f.Player.PotionSlots[0]=null;if(mutation=="capacity")f.Player.MaxPotionCount++;if(mutation=="foreground")f.Overlays.Screens.Add(new NRewardsScreen());
            Check(f.Child(c) is ItemV1Observation o&&o.Status=="unsupported","late mutation rejected "+mutation);Check(f.Session.Read().CompletedItemChildren==0,"late mutation no completion");
        }
        foreach(string task in new[]{"collection","offer","chosen"})foreach(bool cancel in new[]{false,true})
        {
            using var f=new ItemFixture("TASK_FAIL","relic");if(task=="collection"){f.FaultCollection=!cancel;f.CancelCollection=cancel;}if(task=="offer"){f.FaultOffer=!cancel;f.CancelOffer=cancel;}if(task=="chosen"){f.FaultChosen=!cancel;f.CancelChosen=cancel;}
            var c=f.Start();f.Collect(c);Check(f.Child(c) is ItemV1Observation o&&o.Status=="unsupported","native task failure "+task+cancel);
        }
        foreach(bool finish in new[]{false,true})
        {
            using var f=new ItemFixture("BUDGET","relic",delayedOffer:true);var c=f.Start();f.Collect(c);
            for(int i=0;i<255;i++)Check(f.Child(c) is ItemV1Observation o&&o.Status=="waiting","item bounded read "+i);
            if(finish)f.AdvanceOffer();var result=f.Child(c);Check(finish?result is ItemV1ResolvedResult:result is ItemV1Observation ended&&ended.Status=="unsupported","item read256 exact boundary");
            int calls=f.CollectCalls;f.Child(c);Check(f.CollectCalls==calls,"no redispatch on terminal reread");
        }
        using(var f=new ItemFixture("REPEAT","relic",repeatItems:2))
        {
            for(int i=0;i<2;i++){var c=f.Start();f.Collect(c);Check(f.Child(c) is ItemV1ResolvedResult,"repeat item actual generation");}
            Check(f.CollectionTasks.Count==2&&ReferenceEquals(f.CollectionTasks[0],f.CollectionTasks[1]),"cached completed collection Task reused legitimately");Check(f.Session.Read().CompletedItemChildren==2,"repeat item counter");
        }
        using(var f=new ItemFixture("FOREIGN","relic"))
        {var c=f.Start();f.Button.DispatchOverride=()=>{};Check(f.Collect(c) is ItemV1ApplyFailure,"missing GetReward invocation fails without retry");_=f.Button.ForeignGetReward();Check(f.Session.Read().Status=="unsupported"&&f.Button.ForceClickCalls==1,"late unowned callback cannot supply dispatch");}
        foreach(bool collection in new[]{false,true})
        {
            using var f=new ItemFixture("STALE_SCOPE","relic",repeatItems:2);
            ExecutionContext? captured=null;
            if(collection)f.BeforeCollection=()=>captured=ExecutionContext.Capture();else f.BeforeScreen=()=>captured=ExecutionContext.Capture();
            var first=f.Start();var oldSet=f.Set;var oldButton=f.Button;f.Collect(first);Check(f.Child(first) is ItemV1ResolvedResult,"old item resolved before stale invocation");
            f.BeforeScreen=null;f.BeforeCollection=null;
            var second=f.Start();Check(second.Status=="child","new item generation armed");
            int originalCalls=0;
            if(collection)oldButton.Handler=()=>{originalCalls++;return Task.CompletedTask;};else oldSet.OfferHandler=()=>{originalCalls++;return Task.CompletedTask;};
            ExecutionContext.Run(captured!,_=>{if(collection)_=oldButton.ForeignGetReward();else _=oldSet.Offer();},null);
            Check(originalCalls==1,"stale observed original still executes");
            Check(f.Child(second) is ItemV1Observation o&&o.Status=="unsupported","stale item scope poisons current generation");
            Check(f.Session.Read().CompletedItemChildren==1,"prior item completion survives stale scope");
        }
        ItemHookTests();
    }
    private static GenericEventV7ItemSetRead SetRead(ItemFixture f,GenericEventV7Observation c)=>(GenericEventV7ItemSetRead)f.Child(c);
    private static void SetCollect(ItemFixture f,GenericEventV7Observation c) {
        var read=SetRead(f,c);var o=(ItemV1Observation)read.Current!;
        Check(read.Status=="ready"&&o.Offers[0].Index==read.Collected.Count,"next exact set entry");
        Check(((GenericEventV7ItemApply)f.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,o.LegalActions[0])).Value is ItemV1DispatchReceipt,"set collection accepted");
    }
    private static void ItemSetTests() {
        foreach(var kinds in new[]{new[]{"potion","potion"},new[]{"potion","potion","relic","relic"},Enumerable.Repeat("relic",8).ToArray()}) {
            using var f=new ItemFixture("ITEM_SET",kinds[0],index:kinds[0]=="potion"?2:3,itemKinds:kinds);
            var c=f.Start();Check(c.Status=="child"&&c.Child!.ContractVersion=="item_set_v1"&&c.Child.OfferCount==kinds.Length,"multi item admission");
            for(int i=0;i<kinds.Length;i++) {
                SetCollect(f,c);var read=SetRead(f,c);
                Check(read.Collected.Count==i+1&&read.Status==(i==kinds.Length-1?"resolved":"ready"),"each collection settles once");
                Check(f.Session.Read().ChildReconciled==i+1,"cumulative set accounting");
            }
            Check(f.CompletionValid&&f.CollectCalls==kinds.Length,"all exact set effects");
            var parent=f.Session.Read();Check(parent.CompletedItemChildren==1&&parent.ChildAccepted==kinds.Length,"one set child several actions");
            f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","set map continuation");
        }
        foreach(string delay in new[]{"collection","offer","chosen"}) {
            using var f=new ItemFixture("DELAY_SET","relic",itemKinds:new[]{"relic","relic"},delayedCollection:delay=="collection",delayedOffer:delay=="offer",delayedChosen:delay=="chosen");
            var c=f.Start();SetCollect(f,c);
            if(delay=="collection"){Check(SetRead(f,c).Status=="waiting"&&f.CollectCalls==1,"pending first collection never advances");f.AdvanceCollection();}
            Check(SetRead(f,c).Status=="ready","settled first collection exposes second");SetCollect(f,c);
            if(delay=="offer"||delay=="chosen") {
                var wait=SetRead(f,c);Check(wait.Status=="waiting"&&wait.Collected.Count==2&&f.Session.Read().CompletedItemChildren==0,"effects cannot fake owner completion");
                if(delay=="offer")f.AdvanceOffer();else f.AdvanceChosen();
            }
            Check(SetRead(f,c).Status=="resolved","actual set tasks finish");
        }
        foreach(string fault in new[]{"domain","model","key","claim","rollback","relocate","inventory","capacity","foreign_button","duplicate_button","future_selected","index","task"}) {
            using var f=new ItemFixture("BAD_SET","potion",itemKinds:new[]{"potion","relic"});
            var c=f.Start();SetCollect(f,c);Check(SetRead(f,c).Status=="ready","first effect retained before fault");
            var second=(RelicReward)f.Set.Rewards[1];
            switch(fault) {
                case "domain":f.Set.Rewards.Reverse();break;
                case "model":second.Relic=new RelicModel();break;
                case "key":second.Relic.Id.Entry="Changed";break;
                case "claim":((PotionReward)f.Reward).ClaimedPotion=new PotionModel();break;
                case "rollback":f.Reward.SuccessfullySelected=false;((PotionReward)f.Reward).ClaimedPotion=null;break;
                case "relocate":f.Player.PotionSlots[2]=f.Player.PotionSlots[1];f.Player.PotionSlots[1]=null;break;
                case "inventory":f.Player.PotionSlots[1]=null;break;
                case "capacity":f.Player.MaxPotionCount++;break;
                case "foreign_button":f.Screen.Children.Add(new NRewardButton{Reward=new RelicReward()});break;
                case "duplicate_button":f.Screen.Children.Add(new NRewardButton{Reward=second});break;
                case "future_selected":second.SuccessfullySelected=true;break;
                case "index":second.RewardsSetIndex++;break;
                case "task":f.FaultCollection=true;SetCollect(f,c);break;
            }
            var stopped=SetRead(f,c);Check(stopped.Status=="unsupported"&&stopped.Collected.Count==1,"set rejects "+fault);
            Check(f.CollectCalls==(fault=="task"?2:1)&&f.Session.Read().CompletedItemChildren==0,"no retry or false batch completion");
        }
        foreach(string fault in new[]{"rollback","claim","relocate"}) {
            using var f=new ItemFixture("SET_LATE_RETENTION","potion",itemKinds:new[]{"potion","relic"},delayedOffer:true);
            var c=f.Start();SetCollect(f,c);SetCollect(f,c);
            Check(SetRead(f,c) is {Status:"waiting",Collected.Count:2},"both local effects wait actual Offer");
            if(fault=="rollback")f.Reward.SuccessfullySelected=false;
            if(fault=="claim")((PotionReward)f.Reward).ClaimedPotion=null;
            if(fault=="relocate"){f.Player.PotionSlots[2]=f.Player.PotionSlots[1];f.Player.PotionSlots[1]=null;}
            f.AdvanceOffer();Check(SetRead(f,c) is {Status:"unsupported",Collected.Count:2},"earlier effect retained through final gate "+fault);
            Check(f.Session.Read().CompletedItemChildren==0&&f.CollectCalls==2,"failed set retains per-item credit without completion");
        }
        using(var f=new ItemFixture("SET_FULL","potion",itemKinds:new[]{"potion","potion","potion"})) {
            Check(f.Start().Status=="unsupported"&&f.CollectCalls==0,"enough capacity for entire potion set before first input");
        }
        using(var f=new ItemFixture("SET_SHARED_MODEL","potion",itemKinds:new[]{"potion","potion"})) {
            f.BeforeScreen=()=>((PotionReward)f.Set.Rewards[1]).Potion=((PotionReward)f.Reward).Potion;
            Check(f.Start().Status=="unsupported"&&f.CollectCalls==0,"ambiguous shared offered model rejected");
        }
    }
    private static void ItemHookTests()
    {
        var targets=new[]{typeof(RewardsSet).GetMethod(nameof(RewardsSet.Offer))!,typeof(NRewardsScreen).GetMethod(nameof(NRewardsScreen.ShowScreen))!,typeof(NRewardButton).GetMethod("GetReward",BindingFlags.Instance|BindingFlags.NonPublic)!};
        var prefix=new HarmonyMethod(typeof(Program).GetMethod(nameof(ItemForeignPatch),BindingFlags.Static|BindingFlags.NonPublic)!);
        foreach(var target in targets)
        {
            var foreign=new Harmony("fixture.item.foreign");foreign.Patch(target,prefix:prefix);
            bool failed=false;try{using var hooks=new GenericEventV7Hooks();}catch{failed=true;}
            Check(failed&&Harmony.GetPatchInfo(target)!.Owners.Contains("fixture.item.foreign"),"item foreign hook preserved");foreign.Unpatch(target,prefix.method);
        }
        for(int at=16;at<=18;at++)
        {
            bool failed=false;try{using var hooks=new GenericEventV7Hooks(i=>{if(i==at)throw new InvalidOperationException("fixture install");},null);}catch{failed=true;}
            Check(failed&&targets.All(t=>Harmony.GetPatchInfo(t)?.Owners.Count is null or 0),"item partial install rollback "+at);
            bool cleanup=true;try{using var hooks=new GenericEventV7Hooks(i=>{if(i==at)throw new InvalidOperationException("fixture install");},()=>{if(cleanup)throw new InvalidOperationException("fixture cleanup");});}catch{}
            Check(targets.Any(t=>Harmony.GetPatchInfo(t)?.Owners.Count>0),"item failed rollback retained");cleanup=false;GenericEventV7Hooks.RecoverFailedInstallation();Check(targets.All(t=>Harmony.GetPatchInfo(t)?.Owners.Count is null or 0),"item cleanup recovery "+at);
        }
    }
    private static void ItemForeignPatch(){}
}
