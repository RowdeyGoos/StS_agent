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
        internal FullRewardFixture(string kind="card",int count=1,bool mandatory=false)
        {
            foreach(var c in World.Cards)c.Owner=World.Player;
            RunManager.Instance=new(){State=(RunState)World.Player.RunState,RewardsSetSynchronizer=Sync};
            MegaCrit.Sts2.Core.Combat.CombatManager.Instance=new();NModalContainer.Instance=null;
            ActiveScreenContext.Instance=new(){Current=World.Room};
            Set=new(){Player=World.Player,DisallowSkipping=mandatory};Set.BindSynchronizer(Sync);Screen.BindRewards(Set,World.Player.RunState,false);
            World.Adapter.FullRewardsFactory=(binding,set)=>new GenericEventFullRewards(binding,set);
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
            Set.OfferHandler=()=>{if(count==0)return Task.CompletedTask;Sync.Current.rewardsStack.Add(new(){set=Set});NRewardsScreen.ShowScreen(Set,false,World.Player.RunState);return Finish.Task;};
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
        private void Close(){World.Overlays.Screens.Clear();Sync.Current.rewardsStack.Clear();ActiveScreenContext.Instance.Current=World.Room;Finish.TrySetResult();}
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation c)=>((GenericEventV7RewardChildRead)World.Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
        internal GenericEventV7RewardRead Act(GenericEventV7Observation c,string action){var view=Read(c);Check(view.Status=="ready"&&view.LegalActions.Contains(action),"full event legal "+action+" "+view.Status+"/"+view.Phase);var result=(GenericEventV7RewardChildApply)World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,view.DecisionId,action);Check(result.Value.Outcome=="accepted","full event accepted "+action+" "+result.Value.Outcome);return Read(c);}
        public void Dispose(){try{World.Dispose();}catch(InvalidOperationException){}NRewardsScreen.Factory=null;NCardRewardSelectionScreen.Factory=null;}
    }
    private static void FullRewardCases()
    {
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
}
