using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Entities.Rewards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static partial class Program {
    internal sealed class CardRewardFixture:IDisposable {
        internal readonly ItemFixture World;
        internal GenericEventV7Session Session=>World.Session;
        internal readonly CardReward Reward;
        internal readonly List<CardCreationResult> Offers=new();
        internal readonly List<CardRewardAlternative> Alternatives=new(){new("Skip",PostAlternateCardRewardAction.Skip)};
        internal readonly CardModel[] Cards;
        internal readonly Control Row=new(),AlternateRow=new();
        internal NCardRewardSelectionScreen Menu=null!;
        internal NCardRewardAlternativeButton Skip=new();
        internal NProceedButton Dismiss=new(){IsEnabled=true};
        internal int Opens,Choices,Skips,Dismisses;
        internal TaskCompletionSource Finish=new(),OfferGate=new(),CollectionGate=new(),ChoiceGate=new();
        internal bool DelayCollection=false,DelayChoice=false;
        internal bool DelayOffer,WrongResult,WrongInsertion,ExtraAddition,FaultCollection,DuplicateMenu,DuplicateTask,NoResult;
        internal Action? BeforeMenu=null;
        internal Action? PendingInput;
        internal bool DeferInput;
        internal CardRewardFixture(int count=3) {
            World=new ItemFixture("CARD_REWARD","relic");World.Set.DisallowSkipping=false;
            Cards=Enumerable.Range(0,count).Select(i=>new CardModel{Owner=World.Player}).ToArray();
            foreach(var card in Cards){card.Id.Entry="SAME_CARD";Offers.Add(new(card));}
            Reward=new CardReward{Player=World.Player,RewardsSetIndex=1};Reward.Setup(Offers);World.Reward=Reward;
            World.Set.OfferHandler=async()=>{
                World.Set.Rewards.Add(Reward);NRewardsScreen.ShowScreen(World.Set,false,World.Player.RunState);
                await Finish.Task;if(DelayOffer)await OfferGate.Task;World.ItemCompletions=1;
            };
            NRewardsScreen.Factory=(set,terminal,run)=>{
                World.Screen=new NRewardsScreen();World.Button=new NRewardButton{Reward=Reward,Handler=Collect};World.Screen.Children.Add(World.Button);
                Dismiss.Clicked=()=>{Dismisses++;World.Overlays.Screens.Clear();World.Screen.Visible=false;Finish.SetResult();};World.Screen.BindProceed(Dismiss);
                World.Overlays.Screens.Add(World.Screen);return World.Screen;
            };
            NCardRewardSelectionScreen.Factory=(options,alternatives)=>{
                Menu=new NCardRewardSelectionScreen();Row.Children.Clear();AlternateRow.Children.Clear();
                foreach(var c in options) {
                    var h=new NGridCardHolder{CardModel=c.Card,CardNode=new NCard{Model=c.Card}};
                    h.RewardPressed=()=>{Choices++;Action deliver=()=>Menu.Complete(NoResult?null:WrongResult?(Array.IndexOf(Cards,h.CardModel)+1)%Cards.Length:Array.IndexOf(Cards,h.CardModel));if(DeferInput)PendingInput=deliver;else deliver();};
                    Row.Children.Add(h);
                }
                Skip.Clicked=()=>{Skips++;Menu.Complete(options.Count);};if(alternatives.Count>0)AlternateRow.Children.Add(Skip);
                Menu.Bind("UI/CardRow",Row);Menu.Bind("UI/RewardAlternatives",AlternateRow);World.Overlays.Screens.Add(Menu);return Menu;
            };
        }
        private async Task Collect() {
            Opens++;BeforeMenu?.Invoke();var screen=NCardRewardSelectionScreen.ShowScreen(Offers,Alternatives);
            if(DuplicateMenu)NCardRewardSelectionScreen.ShowScreen(Offers,Alternatives);
            var task=screen.OptionSelected();if(DuplicateTask)_=screen.OptionSelected();
            int? selected=await task;if(DelayChoice)await ChoiceGate.Task;
            World.Overlays.Screens.Remove(screen);screen.Visible=false;
            if(selected is {} slot&&slot<Cards.Length) {
                var card=Cards[slot];World.Player.Deck.Cards.Add(WrongInsertion?new CardModel{Owner=World.Player}:card);
                if(ExtraAddition)World.Player.Deck.Cards.Add(new CardModel{Owner=World.Player});
                Offers.RemoveAt(slot);Reward.SuccessfullySelected=true;
                World.Overlays.Screens.Clear();World.Screen.Visible=false;
                if(!DelayCollection)Finish.SetResult();
            }
            if(DelayCollection){await CollectionGate.Task;if(selected<Cards.Length)Finish.TrySetResult();}
            if(FaultCollection)throw new InvalidOperationException("fixture collection fault");
        }
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation c)=>((GenericEventV7RewardChildRead)Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
        internal void Act(GenericEventV7Observation c,string action,string expected="accepted") {
            var read=Read(c);Check(read.Status=="ready"&&read.LegalActions.Contains(action),"reward legal "+action);
            var outcome=(GenericEventV7RewardChildApply)Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,read.DecisionId,action);
            Check(outcome.Value.Outcome==expected,"reward accepted "+action+" actual "+outcome.Value.Outcome+" count "+Cards.Length+" duplicate "+DuplicateMenu+"/"+DuplicateTask);
        }
        public void Dispose(){World.Dispose();NCardRewardSelectionScreen.Factory=null;}
    }
    private static void CardRewardTests() {
        foreach(int count in new[]{1,3,5})foreach(bool skip in new[]{false,true}) {
            using var f=new CardRewardFixture(count);var c=f.Start();Check(c.Child!.ContractVersion=="card_reward_v1","card reward admission");
            f.Act(c,"open");Check(f.Read(c).Phase=="choose","owned menu ready");
            f.Act(c,skip?"skip":"choose:"+(count-1));
            if(skip){Check(!f.Reward.SuccessfullySelected&&f.Read(c).Phase=="dismiss"&&f.World.Overlays.ScreenCount==1,"skip is not completion");f.Act(c,"dismiss");}
            var done=f.Read(c);Check(done.Status=="resolved"&&done.SelectedSlot==(skip?null:count-1)&&done.PriorResults.Count==(skip?3:2),"exact reward completion");
            Check(f.Choices==(skip?0:1)&&f.Skips==(skip?1:0)&&f.Dismisses==(skip?1:0),"one native input each");
            var parent=f.Session.Read();Check(parent.Phase=="proceed"&&parent.CompletedCardChildren==1,"parent resumed");f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","reward map");
        }
        foreach(string bad in new[]{"wrong_result","wrong_insertion","extra","fault","null","holder","node","can_skip","alternative","task","menu","domain","owner"}) {
            using var f=new CardRewardFixture();var c=f.Start();
            if(bad=="task")f.DuplicateTask=true;if(bad=="menu")f.DuplicateMenu=true;
            f.Act(c,"open",bad is "task" or "menu"?"uncertain":"accepted");
            if(bad is "task" or "menu"){Check(f.Read(c).Status=="unsupported","duplicate owned menu/task rejected");continue;}
            Check(f.Read(c).Phase=="choose","bind chooser before mutation");
            if(bad=="owner")f.World.Player.Deck.Cards[0].Owner=new MegaCrit.Sts2.Core.Entities.Players.Player();
            if(bad=="holder")f.Row.Children[0]=new NGridCardHolder{CardModel=f.Cards[0],CardNode=new NCard{Model=f.Cards[0]}};
            if(bad=="node")((NGridCardHolder)f.Row.Children[0]).CardNode.Model=f.Cards[1];
            if(bad=="can_skip")f.Reward.CanSkip=false;
            if(bad=="alternative")f.Alternatives[0].OnSelect=()=>Task.CompletedTask;
            if(bad=="domain")f.Offers.Reverse();
            if(bad is "holder" or "node" or "can_skip" or "alternative" or "domain" or "owner") {
                var read=f.Read(c);for(int i=0;i<260&&read.Status=="waiting";i++)read=f.Read(c);
                Check(read.Status=="unsupported"&&f.Choices==0,"mutated chooser cannot dispatch "+bad);continue;
            }
            f.WrongResult=bad=="wrong_result";f.WrongInsertion=bad=="wrong_insertion";f.ExtraAddition=bad=="extra";f.FaultCollection=bad=="fault";f.NoResult=bad=="null";
            f.Act(c,"choose:0");Check(f.Read(c).Status=="unsupported"&&f.Choices==1,"failed reward cannot resolve "+bad);
        }
        using(var f=new CardRewardFixture(){DelayOffer=true}) {
            var c=f.Start();f.Act(c,"open");f.Act(c,"choose:0");Check(f.Read(c).Status=="waiting","card insertion waits Offer");
            f.OfferGate.SetResult();Check(f.Read(c).Status=="resolved","actual Offer finishes");
        }
        using(var f=new CardRewardFixture(){DeferInput=true}) {
            var c=f.Start();f.Act(c,"open");f.Act(c,"choose:0");Check(f.Read(c).Status=="waiting"&&f.Choices==1,"deferred choice waits without retry");f.PendingInput!();Check(f.Read(c).Status=="resolved","deferred reward resolves");
        }
        foreach(bool collection in new[]{false,true}) {
            using var f=new CardRewardFixture(){DelayCollection=collection,DelayChoice=!collection};
            var c=f.Start();f.Act(c,"open");f.Act(c,"choose:0");Check(f.Read(c).Status=="waiting","actual collection unfinished");
            if(collection)f.CollectionGate.SetResult();else f.ChoiceGate.SetResult();
            Check(f.Read(c).Status=="resolved","actual collection completed");
        }
        foreach(string constraint in new[]{"no_skip","disallow","no_alternative","disabled","callback"}) {
            using var f=new CardRewardFixture();
            if(constraint=="no_skip")f.Reward.CanSkip=false;
            if(constraint=="disallow")f.World.Set.DisallowSkipping=true;
            if(constraint=="no_alternative")f.Alternatives.Clear();
            if(constraint=="disabled")f.Skip.IsEnabled=false;
            if(constraint=="callback")f.Alternatives[0].OnSelect=()=>Task.CompletedTask;
            var c=f.Start();f.Act(c,"open",constraint=="callback"?"uncertain":"accepted");var read=f.Read(c);
            if(constraint=="callback")Check(read.Status=="unsupported","nondefault alternative rejected");
            else if(constraint=="disabled"){Check(read.Status=="waiting","native disabled alternative waits");f.Skip.IsEnabled=true;Check(f.Read(c).CanSkip,"native alternative enabled");}
            else {Check(read.Status=="ready"&&!read.CanSkip&&!read.LegalActions.Contains("skip"),"skip native legality");f.Act(c,"choose:0");Check(f.Read(c).Status=="resolved","forced reward choice");}
        }
        foreach(string late in new[]{"owner","order","remove","level","selected"}) {
            using var f=new CardRewardFixture(){DelayOffer=true};var c=f.Start();f.Act(c,"open");f.Act(c,"choose:0");
            Check(f.Read(c).Status=="waiting","retain insertion while parent waits");
            var deck=f.World.Player.Deck.Cards;
            if(late=="owner")deck[0].Owner=new MegaCrit.Sts2.Core.Entities.Players.Player();
            if(late=="order")deck.Reverse();
            if(late=="remove")deck.Remove(f.Cards[0]);
            if(late=="level")deck[0].CurrentUpgradeLevel++;
            if(late=="selected")f.Cards[0].CurrentUpgradeLevel++;
            f.OfferGate.SetResult();Check(f.Read(c).Status=="unsupported","retained deck effect rejects "+late);
        }
        foreach(int patch in new[]{21,22}) {
            bool failed=false;
            try {using var hooks=new Sts2AgentBridge.Successors.GenericEventV7.Native.GenericEventV7Hooks(n=>{if(n==patch)throw new InvalidOperationException("new hook rollback");},null);}
            catch(InvalidOperationException){failed=true;}
            Check(failed,"card menu partial install fails");
            foreach(string method in new[]{"ShowScreen","OptionSelected"})
                Check(HarmonyLib.Harmony.GetPatchInfo(typeof(NCardRewardSelectionScreen).GetMethod(method)!)?.Owners.Count is null or 0,"new hook rollback removes owned patch");
        }
    }
}
