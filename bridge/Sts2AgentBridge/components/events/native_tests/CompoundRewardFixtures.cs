using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Entities.Rewards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;

namespace MegaCrit.Sts2.Core.Models.Relics
{
    public sealed class SmallCapsule:RelicModel
    {
        public Func<Task> Handler=()=>Task.CompletedTask;
        public SmallCapsule(){Id.Entry="SMALL_CAPSULE";}
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained()=>Handler();
    }
    public sealed class LostCoffer:RelicModel
    {
        public Func<Task> Handler=()=>Task.CompletedTask;
        public LostCoffer(){Id.Entry="LOST_COFFER";}
        [MethodImpl(MethodImplOptions.NoInlining)]public override Task AfterObtained()=>Handler();
    }
    public sealed class NeowsBones:RelicModel
    {
        public NeowsBones(){Id.Entry="NEOWS_BONES";DynamicVars["Curses"]=new(){IntValue=1};}
    }
}
internal static partial class Program
{
    private sealed class CompoundRewardFixture:IDisposable
    {
        internal readonly Fixture World=new("COMPOUND_REWARDS");
        internal readonly RestRewardsFixture.Synchronizer Sync=new();
        internal readonly TaskCompletionSource Delay=new();
        internal readonly RewardsSet Root,Child;
        internal readonly Dictionary<RewardsSet,NRewardsScreen> Screens=new();
        internal readonly Dictionary<RewardsSet,RestRewardsFixture.Synchronizer.Entry> Entries=new();
        internal readonly List<NRewardButton> Buttons=new();
        internal PaelsWing? Wing;
        internal bool DelayChild,ChildFault,ForeignTail;
        internal CompoundRewardFixture(bool sibling=false,bool cardReward=false,string? tail=null,bool smallCard=false)
        {
            foreach(var c in World.Cards)c.Owner=World.Player;
            RunManager.Instance=new(){State=(RunState)World.Player.RunState,RewardsSetSynchronizer=Sync};
            MegaCrit.Sts2.Core.Combat.CombatManager.Instance=new();NModalContainer.Instance=null;
            ActiveScreenContext.Instance=new(){Current=World.Room};
            Root=NewSet();Child=NewSet();
            RelicModel capsule=cardReward&&!smallCard?new LostCoffer{Handler=()=>Child.Offer()}:new SmallCapsule{Handler=()=>Child.Offer()};
            Add(Root,capsule);if(sibling||tail is not null)Add(Root,new OldCoin());
            if(cardReward){if(smallCard)Add(Child,new OldCoin());AddCard();}else {Add(Child,new OldCoin());Add(Child,new RelicModel());}
            World.Adapter.FullRewardsFactory=(binding,set)=>new GenericEventCompoundRewards(binding,set);
            NRewardsScreen.Factory=(set,_,_)=>{var screen=Screens[set];World.Overlays.Screens.Add(screen);ActiveScreenContext.Instance.Current=screen;return screen;};
            var neow=tail is not null?new NeowsBones():null;World.Room.Layout.OptionButtons[0].Option.Relic=neow;
            if(tail=="scalar")World.Player.Relics.Add(new LuckyFysh{Owner=World.Player});
            if(tail is "delayed" or "fault")CardPileCmd.AfterAdded=_=>Delay.Task;
            if(tail=="scalar")CardPileCmd.AfterAdded=card=>World.Player.Relics.OfType<LuckyFysh>().Single().AfterCardChangedPiles(card,(PileType)0,null);
            World.Room.Layout.OptionButtons[0].Option.Callback=async()=>{
                if(neow is not null){neow.Owner=World.Player;World.Player.Relics.Add(neow);}
                await Root.Offer();
                if(ForeignTail)World.Player.Gold++;
                if(tail is not null&&tail!="missing") {
                    for(int i=0;i<(tail=="two"?2:1);i++) {
                        var curse=new CardModel{Owner=World.Player,Type=tail=="wrong_type"?1:5};curse.Id.Entry="CURSE_"+i;
                        await CardPileCmd.Add(curse,PileType.Deck);
                    }
                    if(tail=="chosen")await Delay.Task;
                }
                World.Model.IsFinished=true;World.Room.Layout.OptionButtons.Clear();
                World.AddOption(new(){TextKey="PROCEED",IsProceed=true,Callback=()=>Task.CompletedTask});
            };
        }
        private void AddCard()
        {
            var card=new CardModel{Owner=World.Player};card.Id.Entry="NESTED_CARD";
            var reward=new CardReward{Player=World.Player,RewardsSetIndex=Child.Rewards.Count};var cards=new[]{new CardCreationResult(card)};
            reward.Setup(cards.ToList());Child.Rewards.Add(reward);
            var wing=new PaelsWing{Owner=World.Player,RewardsSacrificed=1};Wing=wing;World.Player.Relics.Add(wing);
            var options=new[]{new CardRewardAlternative("Skip",PostAlternateCardRewardAction.EndSelectionAndDoNotCompleteReward),
                new CardRewardAlternative("SACRIFICE",PostAlternateCardRewardAction.EndSelectionAndCompleteReward){OnSelect=wing.OnSacrifice}};
            var menu=new NCardRewardSelectionScreen();var row=new Control();menu.Bind("UI/CardRow",row);menu.Children.Add(row);
            row.Children.Add(new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card},RewardPressed=()=>menu.Complete(0)});
            menu.BindAlternatives(cards,options);
            NCardRewardSelectionScreen.Factory=(_,_)=>{World.Overlays.Screens.Add(menu);ActiveScreenContext.Instance.Current=menu;return menu;};
            var button=new NRewardButton{Reward=reward,Handler=async()=>{
                NCardRewardSelectionScreen.ShowScreen(cards,options);reward.BindMenu(menu);
                var index=await menu.OptionSelected();
                if(index==0){World.Player.Deck.Cards.Add(card);reward.SuccessfullySelected=true;}
                else {var option=options[index!.Value-cards.Length];await option.OnSelect();reward.SuccessfullySelected=option.AfterSelected==PostAlternateCardRewardAction.EndSelectionAndCompleteReward;}
                World.Overlays.Screens.Remove(menu);ActiveScreenContext.Instance.Current=Screens[Child];
                Sync.Complete(Entries[Child],RestRewardsFixture.Synchronizer.CompleteState.Completed);
                World.Overlays.Screens.Remove(Screens[Child]);ActiveScreenContext.Instance.Current=World.Overlays.Screens.LastOrDefault()??(Control)World.Room;
            }};
            Screens[Child].Children.Add(button);Buttons.Add(button);
        }
        private RewardsSet NewSet()
        {
            var set=new RewardsSet{Player=World.Player,DisallowSkipping=true};set.BindSynchronizer(Sync);
            var screen=new NRewardsScreen();screen.BindRewards(set,World.Player.RunState,false);screen.BindProceed(new NProceedButton{IsEnabled=false});Screens.Add(set,screen);
            var entry=new RestRewardsFixture.Synchronizer.Entry{set=set,completionSource=new()};Entries.Add(set,entry);
            set.OfferHandler=()=>{Sync.Current.rewardsStack.Add(entry);NRewardsScreen.ShowScreen(set,false,World.Player.RunState);return entry.completionSource.Task;};
            return set;
        }
        private void Add(RewardsSet set,RelicModel relic)
        {
            if(relic.Id.Entry.Length==0)relic.Id.Entry="PASSIVE";
            var reward=new RelicReward{Player=World.Player,Relic=relic,RewardsSetIndex=set.Rewards.Count};set.Rewards.Add(reward);
            var button=new NRewardButton{Reward=reward,Handler=async()=>{
                reward.ClaimedRelic=await RelicCmd.Obtain(reward.Relic!,World.Player);reward.SuccessfullySelected=true;
                if(set.Rewards.All(r=>r.SuccessfullySelected)) {
                    Sync.Complete(Entries[set],RestRewardsFixture.Synchronizer.CompleteState.Completed);
                    // Completing the inner set resumes and retires the outer UI
                    // before this last collection has returned.
                    if(ReferenceEquals(set,Child)&&DelayChild)await Delay.Task;
                    if(ReferenceEquals(set,Child)&&ChildFault)throw new InvalidOperationException("fixture collection fault");
                    World.Overlays.Screens.Remove(Screens[set]);
                    ActiveScreenContext.Instance.Current=World.Overlays.Screens.LastOrDefault()??(Control)World.Room;
                }
            }};
            Screens[set].Children.Add(button);Buttons.Add(button);
        }
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation c)
        {
            var read=((GenericEventV7RewardChildRead)World.Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
            if(read.Status=="ready"&&(read.Phase.StartsWith("deck_")||read.Phase is "card_offer" or "bundle_offer" or "bundle_preview")) {
                var binding=World.Adapter.InspectPending(c.Child.ParentDecisionId,c.Child.ParentActionId);
                var owner=(GenericEventCompoundRewards)binding.FullRewards!;
                var before=new Sts2AgentBridge.Items.Native.PinnedAutomaticRelicEffects.State(World.Player);
                var projection=new Sts2AgentBridge.Unified.FullNativeBackend().Project(World.Player,c.Child,read,owner);
                Check(projection.Actions.SequenceEqual(read.LegalActions)&&before.Same(new(World.Player)),"actual compound projection preserves complete action order and inventory");
            }
            return read;
        }
        internal GenericEventV7RewardRead Act(GenericEventV7Observation c,string action)
        {
            var read=Read(c);Check(read.Status=="ready"&&read.LegalActions.Contains(action),"compound legal "+action+" "+read.Status);
            var receipt=(GenericEventV7RewardChildApply)World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,read.DecisionId,action);
            Check(receipt.Value.Outcome=="accepted","compound accepted "+action+" "+receipt.Value.Outcome);return Read(c);
        }
        public void Dispose()
        {
            try{World.Dispose();}catch(InvalidOperationException){}
            NRewardsScreen.Factory=null;
            NCardRewardSelectionScreen.Factory=null;
            CardPileCmd.AfterAdded=null;
            // Failed production owners stop their process; fixture cases model
            // separate processes after checking exact hook removal.
            var method=typeof(RestRewardsFixture.Synchronizer).GetMethod("CompleteRewardsSet",BindingFlags.Instance|BindingFlags.NonPublic)!;
            Check(!(HarmonyLib.Harmony.GetPatchInfo(method)?.Owners.Any()??false),"compound completion observer removed");
            foreach(var hooked in new[]{typeof(RelicCmd).GetMethod("Obtain")!,typeof(PaelsWing).GetMethod("OnSacrifice")!})
                Check(!(HarmonyLib.Harmony.GetPatchInfo(hooked)?.Owners.Any()??false),"compound pickup/alternative observer removed");
            var preview=typeof(NGridCardHolder).GetMethod("UpdateCardModel",BindingFlags.Instance|BindingFlags.NonPublic)!;
            Check(!(HarmonyLib.Harmony.GetPatchInfo(preview)?.Owners.Any()??false),"compound grid preview observer removed after success or failure");
            typeof(GenericEventCompoundRewards).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);
            typeof(Sts2AgentBridge.Items.Native.PinnedRelicPickupChain).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);
            typeof(Sts2AgentBridge.Items.Native.PinnedCardAddJournal).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);
            typeof(Sts2AgentBridge.Items.Native.PinnedRewardAlternatives).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);
        }
    }
    private static void CompoundRewardCases()
    {
        CompoundOfferCases();
        CompoundAutomaticCases();
        CompoundDeckCases();
        CompoundRemainingCases();
        foreach(string tail in new[]{"curse","scalar","delayed","chosen","fault","missing","wrong_type","two"}) {
            using var f=new CompoundRewardFixture(tail:tail);var c=f.Start();Check(c.Child is not null,"compound tail admission "+tail+" "+System.Text.Json.JsonSerializer.Serialize(c));
            f.Act(c,"collect:0");f.Act(c,"collect:0");f.Act(c,"collect:1");
            var before=f.Read(c);var receipt=(GenericEventV7RewardChildApply)f.World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,before.DecisionId,"collect:1");
            Check(receipt.Value.Outcome is "accepted" or "uncertain","last native collection was dispatched once");var ending=f.Read(c);
            if(tail is "delayed" or "chosen" or "fault") {
                Check(ending.Status=="waiting"&&f.World.Session.Read().ParentReconciled==0,"curse Add and Chosen task both retained: "+tail);
                if(tail=="fault")f.Delay.SetException(new InvalidOperationException("curse callback fault"));else f.Delay.SetResult();ending=f.Read(c);
            }
            bool supported=tail is "curse" or "scalar" or "delayed" or "chosen";
            Check(ending.Status==(supported?"resolved":"unsupported"),"exact parent curse task and identity: "+tail+" "+ending.Status);
            if(supported)Check(f.World.Player.Deck.Cards.Last().Id.Entry=="CURSE_0"&&f.World.Session.Read().ParentReconciled==1,"curse completes before parent reconciliation");
        }
        using(var nested=new CompoundRewardFixture(cardReward:true)) {
            var child=nested.Start();nested.Act(child,"collect:0");var offer=nested.Act(child,"open:0");
            Check(offer.Status=="ready"&&offer.Phase=="card_reward"&&offer.LegalActions.Contains("sacrifice")&&offer.LegalActions.Contains("choose:0"),
                "nested reward advertises every native alternative");
            Check(nested.Act(child,"choose:0").Status=="resolved","nested card can finish without using the alternate");
        }
        CompoundSacrificeCases();
        using(var rejected=new CompoundRewardFixture()) {
            rejected.World.Adapter.FullRewardsFactory=(binding,set)=>{set.Player=null!;return new GenericEventCompoundRewards(binding,set);};
            var before=rejected.World.Session.Read();rejected.World.Session.Apply(before.DecisionId,"choose:0");
            Check(rejected.World.Session.Read().Status=="unsupported","constructor rejection fails event owner");
            var method=typeof(RestRewardsFixture.Synchronizer).GetMethod("CompleteRewardsSet",BindingFlags.Instance|BindingFlags.NonPublic)!;
            Check(!(HarmonyLib.Harmony.GetPatchInfo(method)?.Owners.Any()??false)&&
                typeof(GenericEventCompoundRewards).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.GetValue(null) is null,
                "constructor rejection removes otherwise unreachable native observer");
        }
        foreach(string mode in new[]{"cascade","sibling","delayed_collection","fault","foreign_tail","ancestor_swap","foreign_button"}) {
            using var f=new CompoundRewardFixture(mode=="sibling");f.DelayChild=mode=="delayed_collection";f.ChildFault=mode=="fault";f.ForeignTail=mode=="foreign_tail";
            var c=f.Start();Check(c.Child?.ContractVersion=="full_rewards_v2","one compound event child");
            var opened=f.Act(c,"collect:0");Check(opened.Status=="ready"&&opened.PriorResults.Count==0,"outer claim remains pending while nested reward ready: "+opened.Status+"/"+opened.Phase+"/"+opened.PriorResults.Count);
            if(mode=="ancestor_swap"){f.World.Overlays.Screens[0]=new NRewardsScreen();Check(f.Read(c).Status=="unsupported","replaced ancestor rejected before child input");continue;}
            if(mode=="foreign_button"){f.Buttons[1].ForeignGetReward();Check(f.Read(c).Status=="unsupported","foreign nested input poisons owner");continue;}
            var first=f.Act(c,"collect:0");Check(first.Status=="ready"&&first.PriorResults.Count==0,"later completed child receipt waits behind outer claim");
            var last=f.Act(c,"collect:1");
            if(mode=="sibling"){Check(last.Status=="ready"&&last.PriorResults.Count==3,"first invocation tree settles before sibling root input");last=f.Act(c,"collect:1");}
            if(mode=="delayed_collection"){Check(last.Status=="waiting"&&f.World.Session.Read().ParentReconciled==0,"outer Offer completion does not erase a pending inner collection");f.Delay.SetResult();last=f.Read(c);}
            if(mode is "fault" or "foreign_tail"){Check(last.Status is "unsupported" or "waiting","failed child/tail cannot complete parent");continue;}
            Check(last.Status=="resolved"&&last.PriorResults.Count==(mode=="sibling"?4:3),"exact compound receipts resolve after all tasks and overlays");
            var parent=f.World.Session.Read();Check(parent.ParentReconciled==1&&parent.ChildEpisodes==1&&parent.ChildAccepted==parent.ChildReconciled,"one event child retains complete invocation tree");
        }
    }
    private static void CompoundSacrificeCases()
    {
        foreach(string mode in new[]{"no_grant","passive","gold","upgrade","capacity","delayed","before_delayed","fault","missing","double","foreign","wrong_callback","curse","small"}) {
            using var f=new CompoundRewardFixture(cardReward:true,tail:mode=="curse"?"curse":null,smallCard:mode=="small");
            var player=f.World.Player;var wing=f.Wing!;int deck=player.Deck.Cards.Count,gold=player.Gold,slots=player.PotionSlots.Count;
            if(mode=="no_grant")wing.RewardsSacrificed=0;
            if(mode=="passive")wing.Grant=new RelicModel();
            if(mode=="upgrade"){wing.Grant=new Whetstone();foreach(var card in player.Deck.Cards)card.Type=1;}
            if(mode is "capacity" or "small")wing.Grant=new PotionBelt();
            if(mode is "delayed" or "fault")((OldCoin)wing.Grant).Gate=f.Delay.Task;
            if(mode=="before_delayed")wing.BeforeSacrifice=()=>f.Delay.Task;
            if(mode=="missing")wing.PreventGrant=true;
            if(mode=="double")wing.AfterSacrifice=async()=>{await RelicCmd.Obtain(new OldCoin(),player);};
            if(mode=="foreign")wing.AfterSacrifice=()=>{player.Gold++;return Task.CompletedTask;};
            var c=f.Start();f.Act(c,"collect:0");if(mode=="small")f.Act(c,"collect:0");var offer=f.Act(c,mode=="small"?"open:1":"open:0");
            Check(offer.LegalActions.Contains("sacrifice"),"compound Sacrifice stays public "+mode);
            if(mode=="wrong_callback") {
                // A different instance may not enter the retained callback.
                var other=new PaelsWing{Owner=player};
                wing.AfterSacrifice=()=>other.OnSacrifice();
            }
            var receipt=(GenericEventV7RewardChildApply)f.World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,offer.DecisionId,"sacrifice");
            Check(receipt.Value.Outcome is "accepted" or "uncertain","Sacrifice dispatched once "+mode);
            var after=f.Read(c);
            if(mode is "delayed" or "before_delayed" or "fault") {
                Check(after.Status=="waiting"&&f.World.Session.Read().ParentReconciled==0,"Sacrifice retains actual callback/pickup task "+mode);
                if(mode=="fault")f.Delay.SetException(new InvalidOperationException("fixture Sacrifice fault"));else f.Delay.SetResult();after=f.Read(c);
            }
            bool supported=mode is "no_grant" or "passive" or "gold" or "upgrade" or "capacity" or "delayed" or "before_delayed" or "curse" or "small";
            if(!supported){Check(after.Status=="unsupported"&&f.World.Session.Read().ParentReconciled==0,"invalid Sacrifice cannot complete parent "+mode);continue;}
            if(mode=="curse"){Check(after.Status=="ready","nested Sacrifice releases before root sibling");after=f.Act(c,"collect:1");}
            Check(after.Status=="resolved"&&f.World.Session.Read().ParentReconciled==1,"compound Sacrifice and parent complete "+mode+" "+after.Status);
            Check(player.Deck.Cards.Count==deck+(mode=="curse"?1:0),"Sacrifice never takes the displayed card "+mode);
            Check(player.Gold==gold+(mode is "gold" or "delayed" or "before_delayed" or "small"?300:mode=="curse"?600:0),"exact Sacrifice gold "+mode);
            Check(player.PotionSlots.Count==slots+(mode is "capacity" or "small"?2:0),"exact Sacrifice capacity "+mode);
            if(mode=="upgrade")Check(player.Deck.Cards.Take(2).All(card=>card.CurrentUpgradeLevel==1),"Sacrifice's Whetstone upgrades certified");
            Check(after.PriorResults.Count==(mode is "curse" or "small"?4:3),"ordered receipts include Sacrifice "+mode);
        }
    }
}
