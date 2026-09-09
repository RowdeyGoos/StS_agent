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
using Sts2AgentBridge.Successors.ItemV1;
internal static partial class Program {
    internal sealed class CardRewardSetFixture:IDisposable {
        internal readonly ItemFixture World;
        internal GenericEventV7Session Session=>World.Session;
        internal readonly CardReward[] Rewards;
        internal readonly Reward[] AllRewards;
        internal readonly List<int> Collected=new();
        internal readonly CardModel[][] Cards;
        internal readonly List<CardCreationResult>[] Offers;
        internal readonly List<CardRewardAlternative> Alternatives=new(){new("Skip",PostAlternateCardRewardAction.Skip)};
        internal readonly List<NRewardButton> Buttons=new();
        internal readonly List<int> Opened=new(),Chosen=new(),Skipped=new();
        internal readonly TaskCompletionSource Finish=new(),OfferGate=new(),CollectionGate=new();
        internal NProceedButton Dismiss=new(){IsEnabled=true};
        internal NCardRewardSelectionScreen Menu=null!;
        internal Control Row=new();
        internal int Dismisses;
        internal bool DelayOffer=false,DelayCollection=false,WrongInsertion=false,FaultCollection=false,DeferInput=false;
        internal Action? PendingInput=null,BeforeScreen=null;
        internal CardRewardSetFixture(int count=3,bool chosenDelay=false,string[]? kinds=null) {
            count=kinds?.Length??count;
            World=new ItemFixture("CARD_REWARD_SET","relic",delayedChosen:chosenDelay);World.Set.DisallowSkipping=false;
            Cards=Enumerable.Range(0,count).Select(i=>Enumerable.Range(0,kinds is not null?3:i%3==0?1:i%3==1?3:5).Select(_=>new CardModel{Owner=World.Player}).ToArray()).ToArray();
            foreach(var cards in Cards)foreach(var card in cards)card.Id.Entry="SAME_CARD";
            Offers=Cards.Select(cards=>cards.Select(c=>new CardCreationResult(c)).ToList()).ToArray();
            Rewards=Offers.Select(list=>{var r=new CardReward{Player=World.Player,RewardsSetIndex=5};r.Setup(list);return r;}).ToArray();World.Reward=Rewards[0];
            AllRewards=Rewards.Cast<Reward>().ToArray();
            if(kinds is not null)for(int i=0;i<count;i++) {
                if(kinds[i]=="potion")AllRewards[i]=new PotionReward{Player=World.Player,RewardsSetIndex=5,Potion=new PotionModel()};
                if(kinds[i]=="relic")AllRewards[i]=new RelicReward{Player=World.Player,RewardsSetIndex=5,Relic=new RelicModel()};
            }
            foreach(var reward in AllRewards){if(reward is PotionReward potion)potion.Potion.Id.Entry="SAME_POTION";if(reward is RelicReward relic)relic.Relic.Id.Entry="SAME_RELIC";}
            World.Reward=AllRewards[0];
            World.Set.OfferHandler=async()=>{
                World.Set.Rewards.AddRange(AllRewards);BeforeScreen?.Invoke();NRewardsScreen.ShowScreen(World.Set,false,World.Player.RunState);
                await Finish.Task;if(DelayOffer)await OfferGate.Task;World.ItemCompletions=1;
            };
            NRewardsScreen.Factory=(set,terminal,run)=>{
                World.Screen=new NRewardsScreen();Buttons.Clear();
                for(int i=0;i<count;i++){int index=i;var button=new NRewardButton{Reward=AllRewards[i],Handler=()=>Collect(index)};Buttons.Add(button);World.Screen.Children.Add(button);}
                World.Button=Buttons[0];Dismiss.Clicked=()=>{Dismisses++;World.Overlays.Screens.Clear();World.Screen.Visible=false;Finish.SetResult();};World.Screen.BindProceed(Dismiss);
                World.Overlays.Screens.Add(World.Screen);return World.Screen;
            };
            NCardRewardSelectionScreen.Factory=(options,alternatives)=>{
                int index=Array.FindIndex(Offers,list=>ReferenceEquals(list,options));var menu=new NCardRewardSelectionScreen();Menu=menu;Row=new Control();var alt=new Control();
                for(int i=0;i<options.Count;i++) {
                    int slot=i;var h=new NGridCardHolder{CardModel=options[i].Card,CardNode=new NCard{Model=options[i].Card}};
                    h.RewardPressed=()=>{Chosen.Add(index);Action deliver=()=>menu.Complete(slot);if(DeferInput)PendingInput=deliver;else deliver();};Row.Children.Add(h);
                }
                if(alternatives.Count>0)alt.Children.Add(new NCardRewardAlternativeButton{Clicked=()=>{Skipped.Add(index);menu.Complete(options.Count);}});
                menu.Bind("UI/CardRow",Row);menu.Bind("UI/RewardAlternatives",alt);World.Overlays.Screens.Add(menu);return menu;
            };
        }
        private async Task Collect(int index) {
            if(AllRewards[index] is PotionReward potion) {
                Collected.Add(index);int slot=World.Player.PotionSlots.FindIndex(p=>p is null);World.Player.PotionSlots[slot]=potion.Potion;potion.ClaimedPotion=potion.Potion;potion.SuccessfullySelected=true;
            }else if(AllRewards[index] is RelicReward relic) {
                Collected.Add(index);relic.ClaimedRelic=relic.Relic;relic.SuccessfullySelected=true;
            }else {
            Opened.Add(index);var menu=NCardRewardSelectionScreen.ShowScreen(Offers[index],Alternatives);int? result=await menu.OptionSelected();
            World.Overlays.Screens.Remove(menu);menu.Visible=false;
            if(result is {} slot&&slot<Cards[index].Length) {
                World.Player.Deck.Cards.Add(WrongInsertion?new CardModel{Owner=World.Player}:Cards[index][slot]);
                Offers[index].RemoveAt(slot);Rewards[index].SuccessfullySelected=true;
                World.Screen.Children.Remove(Buttons[index]);Buttons[index].InstanceValid=false;
            }
            }
            if(AllRewards[index].SuccessfullySelected){World.Screen.Children.Remove(Buttons[index]);Buttons[index].InstanceValid=false;}
            bool all=AllRewards.All(r=>r.SuccessfullySelected);
            if(all){World.Overlays.Screens.Clear();World.Screen.Visible=false;}
            if(DelayCollection)await CollectionGate.Task;
            if(FaultCollection)throw new InvalidOperationException("collection fault");
            if(all)Finish.SetResult();
        }
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation c)=>((GenericEventV7RewardChildRead)Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
        internal GenericEventV7RewardRead Ready(GenericEventV7Observation c) {
            var read=Read(c);for(int i=0;i<4&&read.Status=="waiting";i++)read=Read(c);return read;
        }
        internal void Act(GenericEventV7Observation c,string action) {
            var r=Ready(c);Check(r.Status=="ready"&&r.LegalActions.Contains(action),"set legal "+action+" "+r.Status+"/"+r.Phase);
            var receipt=(GenericEventV7RewardChildApply)Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,r.DecisionId,action);
            Check(receipt.ContractVersion==c.Child.ContractVersion&&receipt.Value.Outcome=="accepted","set accepted "+action);
        }
        public void Dispose(){World.Dispose();NCardRewardSelectionScreen.Factory=null;}
    }
    private static void CardRewardSetTests() {
        MixedRewardSetTests();
        foreach(int count in new[]{2,3,8})foreach(string mode in new[]{"collect","mixed","skip"}) {
            using var f=new CardRewardSetFixture(count);var c=f.Start();Check(c.Child!.ContractVersion=="card_reward_set_v1"&&c.Child.OfferCount==count,"set admission");
            for(int i=0;i<count;i++) {
                f.Act(c,"open:"+i);var r=f.Read(c);Check(r.Cards.Count==f.Cards[i].Length&&r.OfferIndex==i,"exact generated menu");
                bool skip=mode=="skip"||mode=="mixed"&&i==0;f.Act(c,skip?"skip:"+i:"choose:"+i+":"+(f.Cards[i].Length-1));
                r=f.Read(c);Check(r.Status=="waiting"&&r.Settled!.Count==i+1&&r.PriorResults.Count==2*(i+1),"independent menu result");
                Check(f.Session.Read().CompletedCardChildren==0,"set not prematurely complete");
            }
            if(mode!="collect"){Check(f.Read(c).Phase=="dismiss"&&f.World.Overlays.ScreenCount==1,"skipped rewards need final dismissal");f.Act(c,"dismiss");}
            var done=f.Read(c);Check(done.Status=="resolved"&&done.PriorResults.Count==2*count+(mode=="collect"?0:1),"complete set");
            Check(f.Opened.SequenceEqual(Enumerable.Range(0,count))&&f.Dismisses==(mode=="collect"?0:1),"bounded original inputs");
            Check(done.Settled!.Select(x=>x.OfferIndex).SequenceEqual(Enumerable.Range(0,count)),"ordered set results");
            var parent=f.Session.Read();Check(parent.CompletedCardChildren==1&&parent.Phase=="proceed","set parent resumed");f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","set map");
        }
        foreach(string mutation in new[]{"owner","level","claim","reorder","remove","offers","task","button"}) {
            using var f=new CardRewardSetFixture();var c=f.Start();f.Act(c,"open:0");f.Act(c,"choose:0:0");Check(f.Read(c).Settled!.Count==1,"first result retained");
            f.Act(c,"open:1");Check(f.Read(c).Phase=="choose","second original menu");
            if(mutation=="owner")f.Cards[0][0].Owner=new MegaCrit.Sts2.Core.Entities.Players.Player();
            if(mutation=="level")f.Cards[0][0].CurrentUpgradeLevel++;
            if(mutation=="claim")f.Rewards[0].SuccessfullySelected=false;
            if(mutation=="reorder")f.World.Player.Deck.Cards.Reverse();
            if(mutation=="remove")f.World.Player.Deck.Cards.Remove(f.Cards[0][0]);
            if(mutation=="offers")f.Offers[2].Reverse();
            if(mutation=="task")f.Buttons[0].ForeignGetReward();
            if(mutation=="button")f.Row.Children[0]=new NGridCardHolder{CardModel=f.Cards[1][0],CardNode=new NCard{Model=f.Cards[1][0]}};
            var read=f.Read(c);Check(read.Status=="unsupported"&&read.Settled!.Count==1&&f.Chosen.Count==1,"retained result cannot change "+mutation);
        }
        foreach(string delay in new[]{"collection","offer","chosen","deferred"}) {
            using var f=new CardRewardSetFixture(2,chosenDelay:delay=="chosen"){DelayCollection=delay=="collection",DelayOffer=delay=="offer",DeferInput=delay=="deferred"};var c=f.Start();
            f.Act(c,"open:0");f.Act(c,"choose:0:0");
            if(delay is "collection" or "deferred") {
                Check(f.Read(c).Status=="waiting"&&f.Read(c).Settled!.Count==0,"actual menu still pending");
                if(delay=="collection")f.CollectionGate.SetResult();else{f.PendingInput!();f.DeferInput=false;}
            }
            Check(f.Read(c).Settled!.Count==1,"first settled before parent");f.Act(c,"open:1");f.Act(c,"choose:1:0");Check(f.Read(c).Settled!.Count==2,"all menus settled");
            if(delay is "offer" or "chosen") {
                Check(f.Read(c).Status=="waiting","actual parent task required");
                if(delay=="offer")f.OfferGate.SetResult();else f.World.AdvanceChosen();
            }
            Check(f.Read(c).Status=="resolved","set actual tasks completed");
        }
        foreach(string change in new[]{"remove","order","upgrade","add"}) {
            using var f=new CardRewardSetFixture();var c=f.Start();var deck=f.World.Player.Deck.Cards;
            if(change=="remove")deck.RemoveAt(0);
            if(change=="order")deck.Reverse();
            if(change=="upgrade")deck[0].CurrentUpgradeLevel++;
            if(change=="add")deck.Add(new CardModel{Owner=f.World.Player});
            Check(f.Read(c).Status=="unsupported"&&f.Opened.Count==0,"entry zero retains admission baseline "+change);
        }
        foreach(string change in new[]{"duplicate_reward","duplicate_card","unknown","linked","empty","oversized"}) {
            using var f=new CardRewardSetFixture(change=="oversized"?9:3);
            f.BeforeScreen=()=>{
                if(change=="duplicate_reward")f.World.Set.Rewards[1]=f.Rewards[0];
                if(change=="duplicate_card")f.Offers[1][0]=new CardCreationResult(f.Cards[0][0]);
                if(change=="unknown")f.World.Set.Rewards[1]=new UnknownItemReward();
                if(change=="linked")f.Rewards[1].ParentRewardSet=new LinkedRewardSet();
                if(change=="empty")f.Offers[2].Clear();
            };
            Check(f.Start().Status=="unsupported"&&f.Opened.Count==0,"unsupported set domain "+change);
        }
        foreach(string interference in new[]{"read","apply","dispose"}) {
            var adapter=new ReentrantRewardSet();using var session=new GenericEventV7CardRewardSetSession(new string('e',32),adapter);
            var read=session.Read();adapter.Entry.BeforeCapture=()=>{
                if(interference=="read")session.Read();
                if(interference=="apply")session.Apply(read.DecisionId,"open:0");
                if(interference=="dispose")try{session.Dispose();}catch(InvalidOperationException){}
            };
            var result=session.Apply(read.DecisionId,"open:0");
            Check(result.Outcome!="accepted"&&adapter.Entry.Dispatches==0&&session.Read().Status=="unsupported","outer interference blocks entry dispatch "+interference);
        }
    }
    private static void MixedRewardSetTests() {
        var shapes=new[]{new[]{"card","potion"},new[]{"potion","card"},new[]{"potion","card","potion"},new[]{"card","relic","card","potion","relic","card","potion","relic"}};
        foreach(var kinds in shapes)foreach(bool skip in new[]{false,true}) {
            using var f=new CardRewardSetFixture(kinds:kinds);var c=f.Start();Check(c.Child?.ContractVersion=="mixed_reward_set_v1","mixed admission");int actions=0;
            for(int i=0;i<kinds.Length;i++) {
                var read=f.Ready(c);Check(read.OfferKinds!.SequenceEqual(kinds)&&read.OfferIndex==i,"mixed exact order");
                if(kinds[i]=="card"){f.Act(c,"open:"+i);f.Act(c,skip?"skip:"+i:"choose:"+i+":0");actions+=2;}
                else {Check(read.Item!.Offers[0].Index==i&&read.Item.Offers[0].Kind==kinds[i],"mixed item identity");f.Act(c,"collect:"+i);actions++;}
                var settled=f.Read(c);Check(settled.Settled!.Count==i+1&&settled.PriorResults.Count==actions&&settled.Settled[i].Kind==kinds[i],"typed local settlement");
                Check(f.Session.Read().CompletedCardChildren==0,"mixed root remains owned");
            }
            if(skip){Check(f.Read(c).Phase=="dismiss","mixed final dismissal");f.Act(c,"dismiss");actions++;}
            var done=f.Read(c);Check(done.Status=="resolved"&&done.PriorResults.Count==actions,"mixed exact completion");
            var parent=f.Session.Read();Check(parent.CompletedCardChildren==1&&parent.CompletedItemChildren==0,"mixed one episode");
            f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","mixed map handoff");
            Check(f.Collected.Count==kinds.Count(k=>k!="card")&&f.Opened.Count==kinds.Count(k=>k=="card"),"mixed bounded inputs");
        }
        foreach(string change in new[]{"deck_before","deck_after_item","slot_during_menu","claim","slot_move","slot_remove","task","future","capacity"}) {
            using var f=new CardRewardSetFixture(kinds:new[]{"potion","card","potion"}){DelayOffer=true};var c=f.Start();
            if(change=="deck_before")f.World.Player.Deck.Cards[0].CurrentUpgradeLevel++;
            else {
                f.Act(c,"collect:0");Check(f.Read(c).Settled!.Count==1,"first mixed potion settled");
                if(change=="deck_after_item")f.World.Player.Deck.Cards.Add(new CardModel{Owner=f.World.Player});
                else {
                    f.Act(c,"open:1");
                    if(change=="slot_during_menu")f.World.Player.PotionSlots[1]=null;
                    else {
                        f.Act(c,"choose:1:0");Check(f.Read(c).Settled!.Count==2,"mixed card settled");
                        if(change=="future")f.Buttons[2].ForeignGetReward();
                        else {
                            f.Act(c,"collect:2");Check(f.Read(c).Settled!.Count==3,"second mixed potion settled");
                            if(change=="claim")((PotionReward)f.AllRewards[0]).ClaimedPotion=null;
                            if(change=="slot_move")(f.World.Player.PotionSlots[1],f.World.Player.PotionSlots[2])=(f.World.Player.PotionSlots[2],f.World.Player.PotionSlots[1]);
                            if(change=="slot_remove")f.World.Player.PotionSlots[1]=null;
                            if(change=="task")f.Buttons[0].ForeignGetReward();
                            if(change=="capacity")f.World.Player.MaxPotionCount++;
                        }
                    }
                }
            }
            Check(f.Read(c).Status=="unsupported"&&f.Session.Read().CompletedCardChildren==0,"mixed retained invariant "+change);
        }
        foreach(string delay in new[]{"collection","offer","chosen","fault","cancel"}) {
            using var f=new CardRewardSetFixture(kinds:new[]{"potion","card"},chosenDelay:delay=="chosen"){DelayCollection=delay is "collection" or "fault" or "cancel",DelayOffer=delay=="offer"};var c=f.Start();f.Act(c,"collect:0");
            if(delay is "collection" or "fault" or "cancel") {
                Check(f.Read(c).Status=="waiting"&&f.Read(c).Settled!.Count==0,"mixed actual collection pending");
                if(delay=="fault")f.CollectionGate.SetException(new InvalidOperationException("fault"));
                else if(delay=="cancel")f.CollectionGate.SetCanceled();else f.CollectionGate.SetResult();
                if(delay!="collection"){Check(f.Read(c).Status=="unsupported","mixed failed collection");continue;}
            }
            Check(f.Read(c).Settled!.Count==1,"mixed item reconciled before parent");f.Act(c,"open:1");f.Act(c,"choose:1:0");Check(f.Read(c).Settled!.Count==2,"mixed entries complete");
            if(delay is "offer" or "chosen"){Check(f.Read(c).Status=="waiting","mixed actual parent pending");if(delay=="offer")f.OfferGate.SetResult();else f.World.AdvanceChosen();}
            Check(f.Read(c).Status=="resolved","mixed actual completion gate");
        }
        foreach(string interference in new[]{"read","apply","dispose"}) {
            var adapter=new ReentrantMixedSet();using var session=new GenericEventV7CardRewardSetSession(new string('e',32),adapter);var read=session.Read();
            adapter.BeforeCapture=()=>{if(interference=="read")session.Read();if(interference=="apply")session.Apply(read.DecisionId,"collect:0");if(interference=="dispose")try{session.Dispose();}catch(InvalidOperationException){}};
            var receipt=session.Apply(read.DecisionId,"collect:0");
            Check(receipt.Outcome!="accepted"&&adapter.Collections==0&&session.Read().Status=="unsupported","mixed reentry before input "+interference);
        }
        {
            var adapter=new ReentrantMixedSet();var session=new GenericEventV7CardRewardSetSession(new string('e',32),adapter);session.Read();adapter.OnDispose=()=>session.Read();bool failed=false;
            try{session.Dispose();}catch(InvalidOperationException){failed=true;}
            Check(failed&&session.Read().Status=="unsupported","mixed cleanup interference cannot release");adapter.OnDispose=null;session.Dispose();
        }
        using(var full=new CardRewardSetFixture(kinds:new[]{"card","potion","potion","potion"}))Check(full.Start().Status=="unsupported"&&full.Opened.Count==0,"mixed capacity before input");
    }
    private sealed class ReentrantMixedSet : IGenericEventV7MixedRewardSetAdapter,IItemV1NativeAdapter {
        public int OfferCount=>2;public IReadOnlyList<string>? OfferKinds=>new[]{"potion","card"};
        internal Action? BeforeCapture,OnDispose;internal int Collections;
        private readonly object _run=new(),_player=new(),_screen=new(),_button=new(),_reward=new(),_model=new();
        public string CaptureState()=>"entry";
        public IGenericEventV7RewardAdapter CreateEntry(int index)=>throw new InvalidOperationException();
        public IItemV1NativeAdapter CreateItemEntry(int index)=>this;
        public void SettleEntry(int index,bool selected)=>throw new InvalidOperationException();
        public void SettleItem(int index)=>throw new InvalidOperationException();
        public GenericEventV7ItemCompletion CaptureItemCompletion(int index)=>throw new InvalidOperationException();
        public void Dismiss()=>throw new InvalidOperationException();
        public void Dispose()=>OnDispose?.Invoke();
        public ItemV1SurfaceCapture CaptureSurface(){BeforeCapture?.Invoke();return ItemV1SurfaceCapture.Available(_run,_player,_screen,1,
            new[]{new ItemV1NativeOffer(0,ItemV1ItemKind.Potion,"POTION",true,false,true,true,_button,_reward,_model,()=>Collections++)},new[]{new ItemV1PotionSlotBinding(null,null)});}
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe)=>throw new InvalidOperationException();
    }
    private sealed class ReentrantRewardSet : IGenericEventV7RewardSetAdapter {
        internal readonly ReentrantRewardEntry Entry=new();
        public int OfferCount=>2;
        public string CaptureState()=>"entry";
        public IGenericEventV7RewardAdapter CreateEntry(int index)=>Entry;
        public void SettleEntry(int index,bool selected)=>throw new InvalidOperationException();
        public void Dismiss()=>throw new InvalidOperationException();
        public void Dispose(){}
    }
    private sealed class ReentrantRewardEntry : IGenericEventV7RewardAdapter {
        internal Action? BeforeCapture;internal int Dispatches;
        public GenericEventV7RewardCapture Capture(){BeforeCapture?.Invoke();return new("open",Array.Empty<GenericEventV7RewardCard>(),false);}
        public void Dispatch(string action){Dispatches++;}
        public void Dispose(){}
    }
}
