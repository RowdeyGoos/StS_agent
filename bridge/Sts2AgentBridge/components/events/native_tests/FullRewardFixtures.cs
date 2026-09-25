using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Rewards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;

internal static partial class Program
{
    private sealed class FullRewardFixture:IDisposable
    {
        internal readonly Fixture World=new("FULL_REWARD");
        internal readonly RestRewardsFixture.Synchronizer Sync=new();
        internal readonly NRewardsScreen Screen=new();
        internal readonly NCardRewardSelectionScreen Menu=new();
        internal readonly RewardsSet Set;
        internal readonly TaskCompletionSource Finish=new(),Callback=new(),Collection=new();
        internal readonly List<NRewardButton> Buttons=new();
        internal CardModel[] Cards=Array.Empty<CardModel>();
        internal CardRewardAlternative[] Options=Array.Empty<CardRewardAlternative>();
        internal CardReward? CardReward;
        internal PaelsWing? Wing;
        internal bool DelayCallback,DelayCollection;
        internal Action? AfterCollection;
        private readonly bool _compound;
        internal FullRewardFixture(string kind="card",int count=1,bool mandatory=false,bool compound=false)
        {
            _compound=compound;
            foreach(var c in World.Cards)c.Owner=World.Player;
            RunManager.Instance=new(){State=(RunState)World.Player.RunState,RewardsSetSynchronizer=Sync};
            MegaCrit.Sts2.Core.Combat.CombatManager.Instance=new();NModalContainer.Instance=null;
            ActiveScreenContext.Instance=new(){Current=World.Room};
            Set=new(){Player=World.Player,DisallowSkipping=mandatory};Set.BindSynchronizer(Sync);Screen.BindRewards(Set,World.Player.RunState,false);
            World.Adapter.FullRewardsFactory=(binding,set)=>compound?new GenericEventCompoundRewards(binding,set):new GenericEventFullRewards(binding,set);
            World.Room.Layout.OptionButtons[0].Option.Callback=async()=>{await Set.Offer();if(DelayCallback)await Callback.Task;World.Model.IsFinished=true;World.Room.Layout.OptionButtons.Clear();World.AddOption(new(){TextKey="PROCEED",IsProceed=true,Callback=()=>{World.Map.IsOpen=true;World.Map.IsTravelEnabled=true;return Task.CompletedTask;}});};
            for(int i=0;i<count;i++) {
                Reward reward;
                if(kind is "card" or "reroll" or "sacrifice") {
                    var card=new CardReward{Player=World.Player,RewardsSetIndex=i,CanReroll=kind=="reroll"};CardReward=card;SetCards("OLD",card);
                    Options=new[]{new CardRewardAlternative("Skip",PostAlternateCardRewardAction.EndSelectionAndDoNotCompleteReward)};
                    if(kind=="reroll") {
                        Options=Options.Append(new CardRewardAlternative("REROLL",PostAlternateCardRewardAction.DoNothing){OnSelect=card.RerollCallback}).ToArray();
                        card.RerollHandler=()=>{SetCards("NEW",card);Options=Options.Take(1).ToArray();Populate();};
                    }
                    if(kind=="sacrifice") {
                        Wing=new(){Owner=World.Player,RewardsSacrificed=1};World.Player.Relics.Add(Wing);
                        Options=Options.Append(new CardRewardAlternative("SACRIFICE",PostAlternateCardRewardAction.EndSelectionAndCompleteReward){OnSelect=Wing.OnSacrifice}).ToArray();
                    }
                    reward=card;
                } else if(kind=="relic")reward=new RelicReward{Player=World.Player,RewardsSetIndex=i,Relic=new OldCoin()};
                else if(kind=="special"){var card=new CardModel{Owner=World.Player};card.Id.Entry="SPECIAL";reward=new SpecialCardReward(card,World.Player){RewardsSetIndex=i};}
                else {var p=new PotionModel();p.Id.Entry="POTION_"+i;reward=new PotionReward{Player=World.Player,RewardsSetIndex=i,Potion=p};}
                Set.Rewards.Add(reward);var button=new NRewardButton{Reward=reward,Handler=()=>Collect(reward)};Buttons.Add(button);Screen.Children.Add(button);
            }
            Screen.BindProceed(new NProceedButton{IsEnabled=!mandatory,Clicked=Close});
            NRewardsScreen.Factory=(_,_,_)=>{World.Overlays.Screens.Add(Screen);ActiveScreenContext.Instance.Current=Screen;return Screen;};
            NCardRewardSelectionScreen.Factory=(_,_)=>{Populate();World.Overlays.Screens.Add(Menu);ActiveScreenContext.Instance.Current=Menu;return Menu;};
            Set.OfferHandler=()=>{if(count==0)return Task.CompletedTask;Sync.Current.rewardsStack.Add(new(){set=Set,completionSource=Finish});NRewardsScreen.ShowScreen(Set,false,World.Player.RunState);return Finish.Task;};
        }
        private void SetCards(string prefix,CardReward reward){Cards=Enumerable.Range(0,3).Select(i=>{var c=new CardModel{Owner=World.Player};c.Id.Entry=prefix+"_"+i;return c;}).ToArray();reward.Setup(Cards.Select(c=>new CardCreationResult(c)).ToList());}
        private void Populate()
        {
            Menu.Children.Clear();var row=new Control();Menu.Bind("UI/CardRow",row);Menu.Children.Add(row);
            for(int i=0;i<Cards.Length;i++){int index=i;var card=Cards[i];row.Children.Add(new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card},RewardPressed=()=>Menu.Complete(index)});}
            Menu.BindAlternatives(Cards.Select(c=>new CardCreationResult(c)).ToArray(),Options);
        }
        private async Task Collect(Reward reward)
        {
            if(reward is CardReward card) {
                var options=Options;var menu=NCardRewardSelectionScreen.ShowScreen(Cards.Select(c=>new CardCreationResult(c)).ToArray(),options);card.BindMenu(menu);
                while(true){int? index=await menu.OptionSelected();if(index<Cards.Length){World.Player.Deck.Cards.Add(Cards[index!.Value]);reward.SuccessfullySelected=true;break;}
                    var option=options[index!.Value-Cards.Length];await option.OnSelect();if(option.AfterSelected==PostAlternateCardRewardAction.DoNothing)continue;
                    reward.SuccessfullySelected=option.AfterSelected==PostAlternateCardRewardAction.EndSelectionAndCompleteReward;break;}
                World.Overlays.Screens.Remove(menu);ActiveScreenContext.Instance.Current=Screen;
            } else if(reward is RelicReward relic){relic.ClaimedRelic=await MegaCrit.Sts2.Core.Commands.RelicCmd.Obtain(relic.Relic,World.Player);reward.SuccessfullySelected=true;}
            else if(reward is SpecialCardReward){World.Player.Deck.Cards.Add(Sts2AgentBridge.Adapters.Public.PinnedPublicSpecialCardClaim.Card(reward)!);reward.SuccessfullySelected=true;}
            else if(reward is PotionReward potion){potion.Potion.Owner=World.Player;World.Player.PotionSlots[World.Player.PotionSlots.FindIndex(p=>p is null)]=potion.Potion;potion.ClaimedPotion=potion.Potion;reward.SuccessfullySelected=true;}
            AfterCollection?.Invoke();
            if(DelayCollection)await Collection.Task;
            if(Set.Rewards.All(r=>r.SuccessfullySelected))Close();
        }
        private void Close(){if(_compound)Sync.Complete(Sync.Current.rewardsStack.Single(e=>ReferenceEquals(e.set,Set)),Set.Rewards.All(r=>r.SuccessfullySelected)?RestRewardsFixture.Synchronizer.CompleteState.Completed:RestRewardsFixture.Synchronizer.CompleteState.Skipped);World.Overlays.Screens.Clear();Sync.Current.rewardsStack.Clear();ActiveScreenContext.Instance.Current=World.Room;Finish.TrySetResult();}
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation c)=>((GenericEventV7RewardChildRead)World.Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
        internal GenericEventV7RewardRead Act(GenericEventV7Observation c,string action){var view=Read(c);Check(view.Status=="ready"&&view.LegalActions.Contains(action),"full event legal "+action+" "+view.Status+"/"+view.Phase);var result=(GenericEventV7RewardChildApply)World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,view.DecisionId,action);Check(result.Value.Outcome=="accepted","full event accepted "+action+" "+result.Value.Outcome);return Read(c);}
        public void Dispose(){try{World.Dispose();}catch(InvalidOperationException){}NRewardsScreen.Factory=null;NCardRewardSelectionScreen.Factory=null;}
    }
    private static void FullRewardCases()
    {
        foreach(string kind in new[]{"card","reroll","sacrifice","relic","special","potion"}) {
            using var f=new FullRewardFixture(kind,compound:true);var c=f.Start();
            Check(c.Child?.ContractVersion=="full_rewards_v2","compound root admission "+kind+" "+c.Status);
            GenericEventV7RewardRead done;
            if(kind is "card" or "reroll" or "sacrifice"){f.Act(c,"open:0");if(kind=="reroll")f.Act(c,"reroll");done=f.Act(c,kind=="sacrifice"?"sacrifice":"choose:1");}
            else done=f.Act(c,kind=="special"?"take:0":"collect:0");
            Check(done.Status=="resolved","compound simple root resolves "+kind+" "+done.Status);
            Check(f.World.Session.Read().ParentReconciled==1,"compound parent waits for native root completion");
        }
        CompoundRewardCases();
        RelicPickupChainCases();
        NestedRewardBoundaryCases();
        NestedOfferCases();
        NestedRewardCascadeCase(false);
        NestedRewardCascadeCase(true);
        CertifiedCardMenuClosingCase();
        foreach(string kind in new[]{"card","reroll","sacrifice","relic","special","potion"})foreach(bool mandatory in new[]{false,true}) {
            using var f=new FullRewardFixture(kind,mandatory:mandatory);var c=f.Start();Check(c.Child?.ContractVersion=="full_rewards_v1","full event child admission "+kind+" "+c.Status);
            Check(f.Read(c).LegalActions.Contains("dismiss")==!mandatory,"mandatory rewards preserve native legality");
            GenericEventV7RewardRead done;
            if(kind is "card" or "reroll" or "sacrifice") {f.Act(c,"open:0");if(kind=="reroll")f.Act(c,"reroll");done=f.Act(c,kind=="sacrifice"?"sacrifice":"choose:1");}
            else done=f.Act(c,kind=="special"?"take:0":"collect:0");
            Check(done.Status=="resolved"&&done.PriorResults.Count>=1,"full event exact native completion "+kind+" "+done.Status);
            var parent=f.World.Session.Read();Check(parent.Status=="ready"&&parent.ParentReconciled==1&&parent.ChildAccepted==parent.ChildReconciled,"full reward receipts reconcile before event resumes");
        }
        foreach(string mode in new[]{"skip","callback","collection","fault","foreign_button","same_key","pending_cleanup"}) {
            using var f=new FullRewardFixture();f.DelayCallback=mode=="callback";f.DelayCollection=mode is "collection" or "fault";
            var c=f.Start();f.Act(c,"open:0");
            if(mode=="skip"){f.Act(c,"skip_card");Check(f.Act(c,"dismiss").Status=="resolved","explicit skip and dismissal resolve");continue;}
            if(mode=="foreign_button"){f.Buttons[0].ForeignGetReward();Check(f.Read(c).Status=="unsupported","foreign collection invalidates event owner");continue;}
            if(mode=="same_key"){var old=f.World.Player.Deck.Cards[0];var replacement=new CardModel{Owner=f.World.Player};replacement.Id.Entry=old.Id.Entry;f.World.Player.Deck.Cards[0]=replacement;Check(f.Read(c).Status=="unsupported","event rejects same-key replacement");continue;}
            if(mode=="pending_cleanup"){bool rejected=false;try{f.World.Session.Dispose();}catch{rejected=true;}Check(rejected,"pending event cleanup is not clean");continue;}
            var result=f.Act(c,"choose:0");Check(result.Status=="waiting"&&f.World.Session.Read().ParentReconciled==0,"event retains unfinished native task "+mode);
            if(mode=="callback")f.Callback.SetResult();else if(mode=="fault")f.Collection.SetException(new InvalidOperationException());else f.Collection.SetResult();
            Check(f.Read(c).Status==(mode=="fault"?"unsupported":"resolved"),"exact retained task result "+mode);
        }
        foreach(bool relic in new[]{false,true}) {
            using var f=new FullRewardFixture("special");
            if(relic){var original=new RelicModel{Owner=f.World.Player};original.Id.Entry="KEPT";f.World.Player.Relics.Add(original);f.AfterCollection=()=>{var replacement=new RelicModel{Owner=f.World.Player};replacement.Id.Entry="KEPT";f.World.Player.Relics[0]=replacement;};}
            else {var original=new PotionModel{Owner=f.World.Player};original.Id.Entry="KEPT";f.World.Player.PotionSlots[0]=original;f.AfterCollection=()=>{var replacement=new PotionModel{Owner=f.World.Player};replacement.Id.Entry="KEPT";f.World.Player.PotionSlots[0]=replacement;};}
            var c=f.Start();Check(f.Act(c,"take:0").Status=="unsupported","special card rejects unrelated same-key item replacement");
        }
        using(var empty=new FullRewardFixture(count:0)){var parent=empty.Start();Check(parent.Status=="ready"&&parent.ParentReconciled==1&&parent.ChildEpisodes==0,"empty native Offer needs no synthetic action");}
    }
    private static void NestedRewardBoundaryCases()
    {
        foreach (string mode in new[] { "cascade", "ancestor_swap", "set_swap", "early_certificate", "wrong_state", "duplicate", "task_fault", "pending_cleanup" })
        {
            using var f = new RestRewardsFixture(count: 0);
            var w = f.World;
            f.Sync.Current.rewardsStack.Add(new() { set = f.Set });
            w.Overlays.Screens.Add(f.Screen);
            var set = new RewardsSet { Player = w.Player };
            set.BindSynchronizer(f.Sync);
            var screen = new NRewardsScreen(); screen.BindRewards(set, w.Player.RunState, false);
            var reward = new PotionReward { Player = w.Player, Potion = new PotionModel() };
            reward.Potion.Id.Entry = "NESTED_POTION"; set.Rewards.Add(reward);
            var entry = new RestRewardsFixture.Synchronizer.Entry { set = set };
            var offer = new TaskCompletionSource(); var collection = new TaskCompletionSource();
            bool certified = false, tailRan = false;
            var child = new Sts2AgentBridge.Rooms.Rest.RestRewardContinuation(set, w.Player, w.Overlays, () => true,
                inventory: player => new Sts2AgentBridge.Items.Native.PinnedRewardInventory(player),
                ancestorSets: new[] { f.Set }, ancestorScreens: new Control[] { f.Screen });
            // Plain completion sources deliberately run the parent continuation
            // inline, as the pinned RewardsSetSynchronizer does.
            async Task Parent() { await offer.Task; f.Offer.SetResult(); }
            async Task Tail() { await f.Offer.Task; var curse = new CardModel { Owner = w.Player }; curse.Id.Entry = "LATER_CURSE"; w.Player.Deck.Cards.Add(curse); tailRan = true; }
            var tail = Tail(); var parent = Parent();
            async Task Collect()
            {
                reward.Potion.Owner = w.Player; w.Player.PotionSlots[0] = reward.Potion;
                reward.ClaimedPotion = reward.Potion; reward.SuccessfullySelected = true;
                child.CertifyNativeCompletion(f.Sync, entry, false); certified = true;
                f.Sync.Current.rewardsStack.Remove(entry);
                offer.SetResult();
                await collection.Task;
                w.Overlays.Screens.Remove(screen); ActiveScreenContext.Instance.Current = f.Screen;
            }
            var button = new NRewardButton { Reward = reward, Handler = Collect };
            screen.Children.Add(button); screen.BindProceed(new NProceedButton());
            child.Offering(offer.Task); f.Sync.Current.rewardsStack.Add(entry);
            child.ScreenEntering(set, false, w.Player.RunState);
            w.Overlays.Screens.Add(screen); ActiveScreenContext.Instance.Current = screen; child.ScreenEntered(screen);
            var ready = child.Read(); Check(ready.Status == Sts2AgentBridge.Core.Public.PublicDecisionStatus.Ready, "nested reward starts under exact ancestor");
            bool rejected = false;
            if (mode == "ancestor_swap") w.Overlays.Screens[0] = new NRewardsScreen();
            if (mode == "set_swap") f.Sync.Current.rewardsStack[0] = new() { set = f.Set };
            try {
                if (mode is "early_certificate" or "wrong_state") child.CertifyNativeCompletion(f.Sync, mode == "wrong_state" ? new RestRewardsFixture.Synchronizer.Entry { set = set } : entry, false);
                else child.Apply(ready.DecisionId, "collect:0");
            } catch (InvalidOperationException) { rejected = true; }
            if (mode is "ancestor_swap" or "set_swap" or "early_certificate" or "wrong_state") {
                Check(rejected && !certified && !tailRan && button.ForceClickCalls == 0, "nested reward rejects changed authority before input: " + mode);
                try { child.Dispose(); } catch (InvalidOperationException) { }
                // Dispose is intentionally failed for an unresolved frame.
                continue;
            }
            Check(!rejected && certified && tailRan && parent.IsCompletedSuccessfully && tail.IsCompletedSuccessfully,
                "nested last reward certifies before synchronous outer curse");
            Check(child.Read().Status == Sts2AgentBridge.Core.Public.PublicDecisionStatus.Waiting && !child.Completed,
                "completed Offer and certified effect still wait for overlay cleanup");
            if (mode == "duplicate") {
                try { child.CertifyNativeCompletion(f.Sync, entry, false); } catch (InvalidOperationException) { rejected = true; }
            } else if (mode == "task_fault") {
                collection.SetException(new InvalidOperationException());
                // Collection completion remains the compound owner's separate duty.
                Check(!child.Completed, "leaf effect proof does not certify a faulted collection");
            } else if (mode == "pending_cleanup") {
                try { child.Dispose(); } catch (InvalidOperationException) { rejected = true; }
            } else {
                collection.SetResult(); var complete = child.Read();
                Check(complete.Status == Sts2AgentBridge.Core.Public.PublicDecisionStatus.Complete && child.Completed &&
                    complete.Player.DeckCount + 1 == w.Player.Deck.Cards.Count, "leaf certificate survives only the later parent's deck mutation");
                child.Dispose();
            }
            Check(mode is "duplicate" or "pending_cleanup" ? rejected : !rejected, "nested closure boundary: " + mode);
            try { child.Dispose(); } catch (InvalidOperationException) { }
        }
    }

    private static void CertifiedCardMenuClosingCase()
    {
        using var f = new RestRewardsFixture(count:1,cards:true);
        var view=f.Child.Read();f.Child.Apply(view.DecisionId,"open:0");
        var menu=(NCardRewardSelectionScreen)f.World.Overlays.Screens[1];
        var holder=menu.GetNodeOrNull<Control>("UI/CardRow")!.GetChildren().OfType<NGridCardHolder>().First();
        var reward=(CardReward)f.Set.Rewards[0];
        holder.RewardPressed=()=>{
            f.World.Player.Deck.Cards.Add(holder.CardModel!);reward.SuccessfullySelected=true;
            f.Child.CertifyNativeCompletion(f.Sync,f.Sync.Current.rewardsStack[0],false);
            f.Sync.Current.rewardsStack.Clear();f.Offer.SetResult();
        };
        view=f.Child.Read();f.Child.Apply(view.DecisionId,"choose:0");
        Check(f.Child.EffectCertified && f.Child.Read().Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Waiting,
            "certified card choice waits with both exact reward and card menu retained");
        f.World.Overlays.Screens.Remove(f.Screen);
        Check(f.Child.Read().Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Waiting,
            "certified card menu remains owned after its reward screen retires");
        f.World.Overlays.Screens.Remove(menu);
        Check(f.Child.Read().Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Complete,"certified card menu closes exactly");
        f.Child.Dispose();
    }

    private sealed class CascadeRelicEffect : Sts2AgentBridge.Adapters.Public.IPinnedRelicRewardEffect
    {
        internal Task? Task;
        internal readonly Func<bool> Bound;
        internal CascadeRelicEffect(Func<bool> bound) => Bound = bound;
        public void Invoke(Action action) => action();
        public bool Valid(bool inserted) => Bound();
        public bool Completed => Task?.IsCompletedSuccessfully == true && Bound();
        public bool MatchesPlayer(Sts2AgentBridge.Core.Public.PublicRewardPlayer before, Sts2AgentBridge.Core.Public.PublicRewardPlayer after) => Completed && before == after;
        public void Dispose() { if (!Completed) throw new InvalidOperationException("fixture pickup is incomplete"); }
    }
    private static void NestedRewardCascadeCase(bool delayAfterReward)
    {
        using var f = new RestRewardsFixture(count: 0);
        var w = f.World; var rootSet = f.Set; var rootScreen = f.Screen;
        var rootEntry = new RestRewardsFixture.Synchronizer.Entry { set = rootSet };
        var childSet = new RewardsSet { Player = w.Player }; childSet.BindSynchronizer(f.Sync);
        var childEntry = new RestRewardsFixture.Synchronizer.Entry { set = childSet };
        var childScreen = new NRewardsScreen(); childScreen.BindRewards(childSet, w.Player.RunState, false);
        var relic = new RelicModel(); relic.Id.Entry = "COMPOUND_FIXTURE";
        var rootReward = new RelicReward { Player = w.Player, Relic = relic }; rootSet.Rewards.Add(rootReward);
        var potion = new PotionModel(); potion.Id.Entry = "CHILD_POTION";
        var childReward = new PotionReward { Player = w.Player, Potion = potion }; childSet.Rewards.Add(childReward);
        var childOffer = new TaskCompletionSource(); var afterReward = new TaskCompletionSource();
        var rootClose = new TaskCompletionSource(); var childClose = new TaskCompletionSource();
        Sts2AgentBridge.Rooms.Rest.RestRewardContinuation? child = null;
        var rootEffect = new CascadeRelicEffect(() => relic.Owner is null || ReferenceEquals(relic.Owner,w.Player) && w.Player.Relics.Contains(relic));
        var root = new Sts2AgentBridge.Rooms.Rest.RestRewardContinuation(rootSet,w.Player,w.Overlays,()=>true,
            inventory:p=>new Sts2AgentBridge.Items.Native.PinnedRewardInventory(p),relicEffect:_=>rootEffect);
        bool rootCertified=false,childCertified=false,tailRan=false;
        async Task Tail() { await f.Offer.Task; var curse=new CardModel {Owner=w.Player};curse.Id.Entry="BONES_CURSE";w.Player.Deck.Cards.Add(curse);tailRan=true; }
        var tail=Tail();
        async Task Pickup() { await childOffer.Task; }
        async Task CollectRoot()
        {
            relic.Owner=w.Player;w.Player.Relics.Add(relic);
            child=new(childSet,w.Player,w.Overlays,()=>true,inventory:p=>new Sts2AgentBridge.Items.Native.PinnedRewardInventory(p),
                ancestorSets:new[]{rootSet},ancestorScreens:new Control[]{rootScreen});
            child.Offering(childOffer.Task);f.Sync.Current.rewardsStack.Add(childEntry);
            child.ScreenEntering(childSet,false,w.Player.RunState);w.Overlays.Screens.Add(childScreen);ActiveScreenContext.Instance.Current=childScreen;child.ScreenEntered(childScreen);
            rootEffect.Task=Pickup();await rootEffect.Task;
            if(delayAfterReward)await afterReward.Task;
            rootReward.ClaimedRelic=relic;rootReward.SuccessfullySelected=true;
            root.CertifyNativeCompletion(f.Sync,rootEntry,false,child);rootCertified=true;
            f.Sync.Current.rewardsStack.Remove(rootEntry);f.Offer.SetResult();
            await rootClose.Task;
            w.Overlays.Screens.Remove(rootScreen);
        }
        async Task CollectChild()
        {
            potion.Owner=w.Player;w.Player.PotionSlots[0]=potion;childReward.ClaimedPotion=potion;childReward.SuccessfullySelected=true;
            child!.CertifyNativeCompletion(f.Sync,childEntry,false);childCertified=true;
            f.Sync.Current.rewardsStack.Remove(childEntry);childOffer.SetResult();
            await childClose.Task;w.Overlays.Screens.Remove(childScreen);
        }
        Task? rootCollection=null,childCollection=null;
        rootScreen.Children.Add(new NRewardButton{Reward=rootReward,Handler=()=>rootCollection=CollectRoot()});rootScreen.BindProceed(new NProceedButton());
        childScreen.Children.Add(new NRewardButton{Reward=childReward,Handler=()=>childCollection=CollectChild()});childScreen.BindProceed(new NProceedButton());
        root.Offering(f.Offer.Task);f.Sync.Current.rewardsStack.Add(rootEntry);root.ScreenEntering(rootSet,false,w.Player.RunState);
        w.Overlays.Screens.Add(rootScreen);ActiveScreenContext.Instance.Current=rootScreen;root.ScreenEntered(rootScreen);
        var view=root.Read();root.Apply(view.DecisionId,"collect:0");
        Check(child is not null && rootCollection is {IsCompleted:false},"parent collection retains exact nested pickup task");
        var childView=child!.Read();child.Apply(childView.DecisionId,"collect:0");
        Check(childCertified && !child.Completed && childCollection is {IsCompleted:false},"child certificate retains pending native UI task");
        if(delayAfterReward) {
            Check(!rootCertified && !tailRan,"pickup task alone cannot certify delayed AfterRewardTaken");
            afterReward.SetResult();
        }
        Check(rootCertified && tailRan && tail.IsCompletedSuccessfully && rootCollection is {IsCompleted:false},
            "child-to-parent certificates precede synchronous curse with both overlays retained");
        Check(w.Overlays.Screens.SequenceEqual(new object[]{rootScreen,childScreen}),"cascade retains exact ancestor and descendant screens");
        // Retire the outer screen first: completion and UI retirement need not
        // follow the same stack order. No new input is published in this period.
        Check(root.Read().Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Waiting,"certified parent waits under retained child overlay");
        rootClose.SetResult();
        Check(child.Read().Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Waiting &&
            root.Read().Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Waiting,"closing frames tolerate parent retirement before retained child closes");
        childClose.SetResult();ActiveScreenContext.Instance.Current=w.Room;
        Check(rootCollection!.IsCompletedSuccessfully && childCollection!.IsCompletedSuccessfully &&
            child.Read().Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Complete && root.Read().Status==Sts2AgentBridge.Core.Public.PublicDecisionStatus.Complete,
            "both certified frames close after tasks and ancestor overlays retire");
        child.Dispose();root.Dispose();
    }

}
