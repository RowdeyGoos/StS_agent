using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Events.Custom.CrystalSphereEvent;
using MegaCrit.Sts2.Core.Nodes.Events.Custom.CrystalSphere;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Entities.Rewards;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static partial class Program {
    internal sealed class SphereFixture:IDisposable {
        internal readonly TransformFixture World=new("SPHERE",1,domain:3,nonce:new string('e',32));
        internal GenericEventV7Session Session=>World.Session;
        internal readonly CrystalSphereMinigame Game;
        internal readonly NCrystalSphereScreen Screen=new();
        internal readonly Control Cells=new();
        internal readonly NButton Small=new(),Big=new();
        internal readonly NProceedButton Proceed=new(){IsEnabled=false},Dismiss=new(){IsEnabled=true};
        internal readonly TaskCompletionSource BoardDone=new(),OfferDone=new();
        internal readonly RewardsSet Set;
        internal readonly List<NRewardButton> Buttons=new();
        internal NRewardsScreen RewardScreen=null!;
        internal int Reveals,Tools,Purchases,Choices,Skips,Leaves;
        internal Action? Pending;
        internal bool Delay,WrongCount,WrongFog,Curse,FreeRewards;
        internal Action? AfterReward,AfterReveal=null;
        internal SphereFixture(string rewards="",int count=2) {
            RunManager.Instance!.State=World.RunState;
            Game=new(World.Player){DivinationCount=count};Set=new(){Player=World.Player};Screen.Initialize(Game);
            Screen.Bind("%Cells",Cells);Screen.Bind("%SmallDivinationButton",Small);Screen.Bind("%BigDivinationButton",Big);Screen.Bind("%ProceedButton",Proceed);
            for(int i=0;i<121;i++)Cells.Children.Add(new NCrystalSphereCell{Entity=Game.cells[i%11,i/11]});
            Small.Clicked=()=>{Tools++;Game.CrystalSphereTool=CrystalSphereMinigame.CrystalSphereToolType.Small;};Big.Clicked=()=>{Tools++;Game.CrystalSphereTool=CrystalSphereMinigame.CrystalSphereToolType.Big;};
            NCrystalSphereScreen.Factory=_=>World.Overlays.Screens.Add(Screen);
            Game.Click=cell=>{
                Reveals++;Game.DivinationCount-=WrongCount?2:1;var done=new TaskCompletionSource();
                Action effect=()=>{
                    for(int x=0;x<11;x++)for(int y=0;y<11;y++)if(Game.CrystalSphereTool==CrystalSphereMinigame.CrystalSphereToolType.Small?x==cell.X&&y==cell.Y:Math.Abs(x-cell.X)<=1&&Math.Abs(y-cell.Y)<=1)Game.cells[x,y].IsHidden=false;
                    if(WrongFog)Game.cells[10,10].IsHidden=false;
                    if(Curse)_=MegaCrit.Sts2.Core.Commands.CardPileCmd.AddCurseToDeck<MegaCrit.Sts2.Core.Models.Cards.Doubt>(World.Player);
                    AfterReveal?.Invoke();if(Game.DivinationCount==0)BoardDone.TrySetResult();done.SetResult();
                };if(Delay)Pending=effect;else effect();return done.Task;
            };
            foreach(char kind in rewards) {
                Reward r;
                if(kind=='g')r=new GoldReward{Amount=7};
                else if(kind=='p'){var potion=new PotionModel();potion.Id.Entry="SPHERE_POTION";r=new PotionReward{Potion=potion};}
                else if(kind=='r'){var relic=new RelicModel();relic.Id.Entry="SPHERE_RELIC";r=new RelicReward{Relic=relic};}
                else {var card=new CardModel{Owner=World.Player};card.Id.Entry="SPHERE_CARD";var reward=new CardReward();reward.Setup(new(){new(card)});r=reward;}
                r.Player=World.Player;r.RewardsSetIndex=Set.Rewards.Count;Set.Rewards.Add(r);
            }
            World.Room.Layout.OptionButtons[0].Option.Callback=async()=>{NCrystalSphereScreen.ShowScreen(Game);await BoardDone.Task;await Set.Offer();World.Model.IsFinished=true;World.Map.IsTravelEnabled=true;Proceed.IsEnabled=true;};
            Set.OfferHandler=async()=>{if(Set.Rewards.Count>0){NRewardsScreen.ShowScreen(Set,false,World.Player.RunState);await OfferDone.Task;}};
            NRewardsScreen.Factory=(_,_,_)=>{
                RewardScreen=new();RewardScreen.BindProceed(Dismiss);
                foreach(var reward in Set.Rewards){var b=new NRewardButton{Reward=reward};b.Handler=()=>Collect(b);Buttons.Add(b);RewardScreen.Children.Add(b);}
                Dismiss.Clicked=Close;World.Overlays.Screens.Add(RewardScreen);return RewardScreen;
            };
            RunManager.Instance!.ProceedHandler=()=>{Leaves++;World.Map.IsOpen=true;return Task.CompletedTask;};
            NCardRewardSelectionScreen.Factory=(cards,alternatives)=>{
                var menu=new NCardRewardSelectionScreen();var row=new Control();var alternate=new Control();
                foreach(var card in cards){var holder=new NGridCardHolder{CardModel=card.Card,CardNode=new NCard{Model=card.Card}};holder.RewardPressed=()=>{Choices++;menu.Complete(0);};row.Children.Add(holder);}
                var skip=new NCardRewardAlternativeButton();skip.Clicked=()=>{Skips++;menu.Complete(cards.Count);};alternate.Children.Add(skip);
                menu.Children.Add(row);menu.Children.Add(alternate);menu.Bind("UI/CardRow",row);menu.Bind("UI/RewardAlternatives",alternate);World.Overlays.Screens.Add(menu);return menu;
            };
        }
        private void Close(){World.Overlays.Screens.Remove(RewardScreen);RewardScreen.Visible=false;if(FreeRewards){RewardScreen.InstanceValid=false;foreach(var b in Buttons)b.InstanceValid=false;}OfferDone.TrySetResult();}
        private async Task Collect(NRewardButton button) {
            Purchases++;var reward=button.Reward;
            if(reward is GoldReward g)World.Player.Gold+=g.Amount;
            else if(reward is PotionReward p){int slot=World.Player.PotionSlots.FindIndex(p=>p is null);p.Potion.Owner=World.Player;World.Player.PotionSlots[slot]=p.Potion;p.ClaimedPotion=p.Potion;}
            else if(reward is RelicReward r){r.Relic.Owner=World.Player;World.Player.Relics.Add(r.Relic);r.ClaimedRelic=r.Relic;}
            else if(reward is CardReward c) {
                var offers=c.Cards.Select(c=>new CardCreationResult(c)).ToList();var menu=NCardRewardSelectionScreen.ShowScreen(offers,new List<CardRewardAlternative>{new("Skip",PostAlternateCardRewardAction.Skip)});
                int? result=await menu.OptionSelected();World.Overlays.Screens.Remove(menu);menu.Visible=false;
                if(result is null||result==offers.Count){AfterReward?.Invoke();return;}
                World.Player.Deck.Cards.Add(offers[result.Value].Card);
            }
            reward.SuccessfullySelected=true;AfterReward?.Invoke();if(Set.Rewards.All(r=>r.SuccessfullySelected))Close();
        }
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation parent)=>((GenericEventV7RewardChildRead)Session.ReadChild(parent.Child!.ParentDecisionId,parent.Child.ParentActionId,parent.Child.Ordinal)).Value;
        internal void Act(GenericEventV7Observation parent,string action,string expected="accepted") {
            var read=Read(parent);Check(read.Status=="ready"&&read.LegalActions.Contains(action),"sphere legal "+action+" "+read.Status+"/"+read.Phase);
            var result=(GenericEventV7RewardChildApply)Session.ApplyChild(parent.Child!.ParentDecisionId,parent.Child.ParentActionId,parent.Child.Ordinal,read.DecisionId,action);Check(result.Value.Outcome==expected,"sphere receipt "+action+" "+result.Value.Outcome);
        }
        internal void Board(GenericEventV7Observation parent,bool big=true){if(big)Act(parent,"tool:big");while(Game.DivinationCount>0){var read=Read(parent);Act(parent,read.LegalActions.First(a=>a.StartsWith("reveal:")));}}
        internal void Exit(GenericEventV7Observation parent) {
            var final=Read(parent);Check(final.Status=="resolved","sphere resolved callback "+final.Status+"/"+final.Phase+" count "+Game.DivinationCount+" rewards "+Set.Rewards.Count);var leave=Session.Read();Check(leave.Phase=="proceed","sphere native proceed");Check(Session.Apply(leave.DecisionId,"choose:0").Outcome=="accepted","sphere leave accepted");Check(Session.Read().Status=="complete"&&World.Map.IsOpen&&Leaves==1&&World.Overlays.ScreenCount==0&&World.Overlays.RemoveCalls==1,"sphere actionable map");
        }
        public void Dispose(){try{World.Dispose();}catch(InvalidOperationException){ }NCrystalSphereScreen.Factory=null;NRewardsScreen.Factory=null;NCardRewardSelectionScreen.Factory=null;RunManager.Instance!.ProceedHandler=null;}
    }
    private static void SphereCases() {
        foreach(string failure in new[]{"foreign","extra","no_remove","throws","inventory","map","travel","owner"}) {
            using var f=new SphereFixture();var p=f.Start();f.Board(p);Check(f.Read(p).Status=="resolved","cleanup starts after callback");
            var leave=f.Session.Read();Check(f.Session.Apply(leave.DecisionId,"choose:0").Outcome=="accepted","cleanup leave accepted once");
            if(failure=="foreign")f.World.Overlays.Screens[0]=new Control();
            if(failure=="extra")f.World.Overlays.Screens.Add(new Control());
            if(failure=="no_remove")f.World.Overlays.OnRemove=_=>{};
            if(failure=="throws")f.World.Overlays.OnRemove=_=>throw new InvalidOperationException();
            if(failure is "inventory" or "map")f.World.Overlays.OnRemove=screen=>{f.World.Overlays.Screens.Remove(screen);if(failure=="inventory")f.World.Player.Gold++;else f.World.Map.IsOpen=false;};
            if(failure is "travel" or "owner")f.World.Overlays.OnRemove=screen=>{f.World.Overlays.Screens.Remove(screen);if(failure=="travel")f.World.Map.IsTraveling=true;else f.Game.SetOwner(new());};
            Check(f.Session.Read().Status=="unsupported","cleanup failure blocks handoff "+failure);
            int removes=f.World.Overlays.RemoveCalls;bool first=false,second=false;
            try{f.Session.Dispose();}catch{first=true;}try{f.Session.Dispose();}catch{second=true;}
            Check(first&&second&&f.World.Overlays.RemoveCalls==removes&&removes==(failure is "foreign" or "extra"?0:1),"cleanup not retried "+failure);
        }
        foreach(bool big in new[]{false,true})foreach(string rewards in new[]{"","g","p","r","c","gpcr","gggggggg"}) {
            using var f=new SphereFixture(rewards);var p=f.Start();Check(p.Child?.ContractVersion=="crystal_sphere_v1","sphere admission");f.Board(p,big);
            for(int i=0;i<30&&f.Read(p).Status=="ready";i++){var r=f.Read(p);f.Act(p,r.LegalActions[0]);}
            f.Exit(p);Check(f.Reveals==2&&f.World.Player.Gold==99+7*rewards.Count(c=>c=='g'),"sphere exact effects");
        }
        foreach(string reward in new[]{"g","c","p","r"})using(var f=new SphereFixture(reward){FreeRewards=true}){var p=f.Start();f.Board(p);while(f.Read(p).Status=="ready")f.Act(p,f.Read(p).LegalActions[0]);f.Exit(p);Check(!f.RewardScreen.InstanceValid,"retired reward node unused "+reward);}
        using(var f=new SphereFixture("ggcc",10)){foreach(var r in f.Set.Rewards)r.RewardsSetIndex=0;var p=f.Start();f.Board(p);while(f.Read(p).Status=="ready")f.Act(p,f.Read(p).LegalActions[0]);f.Exit(p);Check(f.Purchases==4,"sphere repeated gold/card indices");}
        using(var f=new SphereFixture("g")){var p=f.Start();f.Board(p);f.AfterReward=()=>{((GoldReward)f.Set.Rewards[0]).Amount++;f.World.Player.Gold++;};f.Act(p,"reward:claim:0");Check(f.Read(p).Status=="unsupported","published gold amount retained");}
        using(var f=new SphereFixture("c")){var card=((CardReward)f.Set.Rewards[0]).Cards.Single();card.CurrentUpgradeLevel=3;var p=f.Start();f.Board(p);var ready=f.Read(p);Check(ready.Sphere!.Rewards[0].Cards[0].UpgradeLevel==3,"sphere publishes actual card upgrade");card.CurrentUpgradeLevel=4;Check(f.Read(p).Status=="unsupported","sphere old projection cannot rebind level");}
        using(var f=new SphereFixture("c")){var p=f.Start();f.Board(p);f.Act(p,"reward:open:0");f.World.Overlays.Screens[0]=new Control();Check(f.Read(p).Status=="unsupported","retained base sphere beneath cards");}
        using(var f=new SphereFixture()){var p=f.Start();f.AfterReveal=()=>{var c=new CardModel{Owner=f.World.Player};c.Id.Entry="DOUBT";f.World.Player.Deck.Cards.Add(c);};f.Act(p,"reveal:0");Check(f.Read(p).Status=="unsupported","unwitnessed Doubt not absorbed");}
        using(var f=new SphereFixture("c")){var p=f.Start();f.Board(p);f.Act(p,"reward:open:0");f.Act(p,"reward:skip_card");f.Act(p,"dismiss");f.Exit(p);Check(f.Skips==1&&f.Choices==0,"sphere skip/dismiss");}
        using(var f=new SphereFixture(){Delay=true}){var p=f.Start();f.Act(p,"reveal:0");Check(f.Read(p).Status=="waiting"&&f.Reveals==1,"sphere delayed no repeat");f.Pending!();Check(f.Read(p).Status=="ready","sphere delayed settle");f.Delay=false;f.Board(p,false);f.Exit(p);}
        using(var f=new SphereFixture(){Curse=true}){var p=f.Start();f.Board(p);f.Exit(p);Check(f.World.Player.Deck.Cards.Count(c=>c.Id.Entry=="DOUBT")==2,"sphere native curse grant");}
        foreach(string bad in new[]{"count","fog","owner","cell","inventory","overlay","late_relic","late_potion","late_gold"}){
            using var f=new SphereFixture("g");var p=f.Start();var ready=f.Read(p);
            if(bad=="count")f.WrongCount=true;if(bad=="fog")f.WrongFog=true;
            if(bad=="owner")f.Game.SetOwner(new());if(bad=="cell")((NCrystalSphereCell)f.Cells.Children[0]).Entity=new(){X=0,Y=0};
            if(bad=="inventory")f.World.Player.Gold++;
            if(bad=="overlay")f.World.Overlays.Screens.Add(new Control());
            if(bad.StartsWith("late")){f.Board(p);f.AfterReward=()=>{if(bad=="late_relic")f.World.Player.Relics.Add(new());else if(bad=="late_potion")f.World.Player.PotionSlots[0]=new();else f.World.Player.Gold++;};f.Act(p,"reward:claim:0");}
            else if(bad is "count" or "fog")f.Act(p,"reveal:0");
            Check(f.Read(p).Status=="unsupported","sphere rejects "+bad);
        }
        using(var f=new SphereFixture()){var p=f.Start();var ready=f.Read(p);f.Game.cells[3,3].Item=new object();Check(f.Read(p).DecisionId==ready.DecisionId,"hidden item absent from projection");bool a=false,b=false;try{f.Session.Dispose();}catch{a=true;}try{f.Session.Dispose();}catch{b=true;}Check(a&&b,"sphere cleanup remains failed");}
    }
}
