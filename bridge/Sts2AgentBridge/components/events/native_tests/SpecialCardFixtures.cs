using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;

internal static partial class Program
{
    private static CardModel SpecialFixtureCard(Fixture f,string key) {var card=new CardModel{Owner=f.Player};card.Id.Entry=key;return card;}
    private static void SpecialCardCases()
    {
        foreach(var mode in new[]{"embedded","ok","delayed","wrong_card","extra_card","survivor","owner","reward_replaced","card_replaced","screen_replaced","lost","early_map","late_domain"}) {
            using var f=new Fixture("SPECIAL_CARD");
            foreach(var existing in f.Cards)existing.Owner=f.Player;
            var run=(RunState)f.Player.RunState;
            var card=SpecialFixtureCard(f,"LANTERN_KEY");
            var reward=new SpecialCardReward(card,f.Player);
            var encounter=new EncounterModel();
            var state=new CombatState{Encounter=encounter,RunState=run};state.Players.Add(f.Player);
            var room=new CombatRoom{CombatState=state,ParentEventId=f.Model.Id};
            RunManager.Instance=new(){State=run};CombatManager.Instance=new(){State=null};
            if(mode=="embedded")PrepareEmbeddedCombat(f,state);
            f.Model.CombatEntry=(_,extras,_)=>{
                room.ExtraRewards.Add(f.Player,extras.ToList());run.CurrentRoom=room;
                CombatManager.Instance.State=state;
                if(mode=="embedded"){room.ShouldCreateCombat=false;f.Model.Node=null;}else NCombatRoom.Instance=new();
                NCombatRoom.Instance!.SetVisuals(room);
            };
            f.Room.Layout.OptionButtons[0].Option.Callback=()=>{f.Model.EnterCombatWithoutExitingEvent(mode=="embedded"?new EncounterModel():encounter,new Reward[]{reward},false);return Task.CompletedTask;};
            var eventReady=f.Session.Read();Check(f.Session.Apply(eventReady.DecisionId,"choose:0").Outcome=="accepted","special reward event dispatch");
            Check(f.Session.Read().Phase=="combat_handoff","special reward enters exact combat");
            if(mode=="late_domain") {
                room.ExtraRewards[f.Player][0]=new SpecialCardReward(card,f.Player);
                Check(!f.Adapter.CombatScope!(),"extra reward replacement stops combat lease");continue;
            }
            Check(f.Adapter.CombatScope!(),"special reward lease retains identity");
            // Event hooks are disposed before core owns combat/rewards.
            f.Adapter.Dispose();
            var screen=new NRewardsScreen();var button=new NRewardButton{Reward=reward};screen.Children.Add(button);f.Overlays.Screens.Add(screen);
            var reader=new PinnedPublicRewardDecisionReader();var applier=new PinnedPublicRewardActionApplier(reader);
            button.Handler=()=>{
                if(mode=="lost")throw new InvalidOperationException("lost dispatch");
                f.Player.Deck.Cards.Add(mode=="wrong_card"?SpecialFixtureCard(f,"LANTERN_KEY"):card);
                if(mode=="extra_card")f.Player.Deck.Cards.Add(SpecialFixtureCard(f,"EXTRA"));
                if(mode=="survivor")f.Player.Deck.Cards[0]=SpecialFixtureCard(f,f.Player.Deck.Cards[0].Id.Entry);
                if(mode=="owner")card.Owner=new();
                if(mode=="screen_replaced"){f.Overlays.Screens.Clear();f.Overlays.Screens.Add(new NRewardsScreen());}
                if(mode=="early_map")f.Map.IsOpen=true;
                reward.SuccessfullySelected=mode!="delayed";return Task.CompletedTask;
            };
            var ready=reader.Read();
            Check(ready.Status==PublicDecisionStatus.Ready&&ready.Rewards.Single().Kind==PublicRewardKind.SpecialCard&&ready.LegalActions[0]=="take:0","direct public special card claim");
            Check(PublicRewardActionRequest.TryCreate(ready.DecisionId,"take:0",out var action),"special claim parses");
            if(mode=="reward_replaced")button.Reward=new SpecialCardReward(card,f.Player);
            if(mode=="card_replaced")reward.ReplaceCard(SpecialFixtureCard(f,"LANTERN_KEY"));
            bool stopped=false;
            try {var accepted=applier.Apply(action);stopped=accepted.Outcome!=PublicRewardActionApplyOutcome.Accepted;}
            catch{stopped=true;}
            if(mode is "reward_replaced" or "card_replaced"){Check(stopped&&button.ForceClickCalls==0,"same-key replacement stops before dispatch");continue;}
            if(mode=="lost") {
                Check(stopped&&button.ForceClickCalls==1,"uncertain dispatch retained");
                Check(applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied&&button.ForceClickCalls==1,"uncertain special claim never retried");continue;
            }
            Check(!stopped&&button.ForceClickCalls==1,"one native special reward click");
            Check(applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied,"special replay blocked");
            var next=reader.Read();
            if(mode=="delayed") {Check(next.Status==PublicDecisionStatus.Waiting,"insertion waits for reward completion");reward.SuccessfullySelected=true;next=reader.Read();}
            if(mode is not ("embedded" or "ok" or "delayed")){Check(next.Status==PublicDecisionStatus.Unsupported,"incorrect special grant cannot reconcile: "+mode);continue;}
            Check(next.Status==PublicDecisionStatus.Ready&&next.DecisionRevision==1&&next.Player.DeckCount==ready.Player.DeckCount+1&&!next.LegalActions.Contains("take:0"),"exact grant reconciles once");
            Check(PublicRewardActionRequest.TryCreate(next.DecisionId,"proceed",out action)&&applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"reward proceed accepted");
            Check(reader.Read().Status==PublicDecisionStatus.Complete,"special card reward reaches map");
        }
        foreach(var mode in new[]{"foreign","owned","two","resume","potion","missing","wrong_list"}) {
            using var f=new Fixture("BAD_EXTRA");var run=(RunState)f.Player.RunState;
            var card=SpecialFixtureCard(f,"EXTRA");if(mode=="foreign")card.Owner=new();if(mode=="owned")f.Player.Deck.Cards.Add(card);
            Reward reward=mode=="potion"?new PotionReward{Player=f.Player,Potion=new()}:new SpecialCardReward(card,f.Player);
            var encounter=new EncounterModel();var state=new CombatState{Encounter=encounter,RunState=run};state.Players.Add(f.Player);
            var room=new CombatRoom{CombatState=state,ParentEventId=f.Model.Id};
            RunManager.Instance=new(){State=run};CombatManager.Instance=new(){State=null};
            f.Model.CombatEntry=(_,extras,_)=>{
                if(mode!="missing")room.ExtraRewards.Add(f.Player,mode=="wrong_list"?new(){new SpecialCardReward(card,f.Player)}:extras.ToList());
                run.CurrentRoom=room;CombatManager.Instance.State=state;NCombatRoom.Instance=new();NCombatRoom.Instance.SetVisuals(room);
            };
            f.Room.Layout.OptionButtons[0].Option.Callback=()=>{f.Model.EnterCombatWithoutExitingEvent(encounter,mode=="two"?new[]{reward,reward}:new[]{reward},mode=="resume");return Task.CompletedTask;};
            var ready=f.Session.Read();f.Session.Apply(ready.DecisionId,"choose:0");
            Check(f.Session.Read().Status=="unsupported","unsupported extra entry: "+mode);
        }
    }
}
