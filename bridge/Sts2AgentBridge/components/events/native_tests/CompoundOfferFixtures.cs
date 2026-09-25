using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.GenericEventV7;

namespace MegaCrit.Sts2.Core.Models.Cards {public sealed class Injury:CardModel {public Injury(){Id.Entry="INJURY";Type=5;}}}
namespace MegaCrit.Sts2.Core.Models.Relics
{
    public abstract class OfferRelicFixture:RelicModel
    {
        public Func<Task> Handler=()=>Task.CompletedTask;
        [MethodImpl(MethodImplOptions.NoInlining)] public override Task AfterObtained()=>Handler();
    }
    public sealed class LeadPaperweight:OfferRelicFixture {public LeadPaperweight(){Id.Entry="LEAD_PAPERWEIGHT";}}
    public sealed class MassiveScroll:OfferRelicFixture {public MassiveScroll(){Id.Entry="MASSIVE_SCROLL";}}
    public sealed class HeftyTablet:OfferRelicFixture {public HeftyTablet(){Id.Entry="HEFTY_TABLET";}}
    public sealed class ScrollBoxes:OfferRelicFixture {public ScrollBoxes(){Id.Entry="SCROLL_BOXES";}}
}
internal static partial class Program
{
    private sealed class CompoundOfferFixture:IDisposable
    {
        internal readonly CompoundRewardFixture Parent;
        internal readonly IReadOnlyList<CardModel>[] Offers;
        internal readonly TaskCompletionSource Creation=new(),Completion=new(),Insertion=new();
        internal readonly Control Row=new(),Preview=new(){Visible=false},PreviewCards=new();
        internal readonly NConfirmButton Confirm=new();
        internal readonly NChoiceSelectionSkipButton Skip=new();
        internal Control? Screen;
        internal bool DelayCreation,DelayCompletion,DelayInsertion,Fault,RetainScreen,WrongRequest,WrongSelection;
        internal int Selected=-1,Clicks;
        internal CardModel Card(string key){var card=new CardModel{Owner=Parent.World.Player};card.Id.Entry=key;return card;}
        internal CompoundOfferFixture(CompoundRewardFixture parent,string kind,bool nested=false)
        {
            Parent=parent;Time.Ticks=1000;bool bundle=kind=="bundle";
            Offers=Enumerable.Range(0,3).Select(i=>(IReadOnlyList<CardModel>)Enumerable.Range(0,bundle?2:1).Select(j=>Card("OFFER_"+i+"_"+j)).ToArray()).ToArray();
            OfferRelicFixture relic=kind switch {"massive"=>new MassiveScroll(),"hefty"=>new HeftyTablet(),"bundle"=>new ScrollBoxes(),_=>new LeadPaperweight()};
            ((RelicReward)(nested?parent.Child:parent.Root).Rewards[0]).Relic=relic;
            relic.Handler=async()=>{
                CardModel[] chosen=bundle?(await CardSelectCmd.FromChooseABundleScreen(parent.World.Player,Offers)).ToArray():
                    new[]{await CardSelectCmd.FromChooseACardScreen(new PlayerChoiceContext(),Offers.Select(o=>o[0]).ToArray(),parent.World.Player,true)};
                chosen=chosen.Where(c=>c is not null).ToArray();
                if(kind=="hefty")await CardPileCmd.Add(chosen.Append(new MegaCrit.Sts2.Core.Models.Cards.Injury{Owner=parent.World.Player}).ToList(),PileType.Deck);
                else foreach(var card in chosen)await CardPileCmd.Add(card,PileType.Deck);
                if(DelayCompletion)await Completion.Task;
                if(Fault)throw new InvalidOperationException("pickup fault");
            };
            CardPileCmd.AfterAdded=_=>DelayInsertion?Insertion.Task:Task.CompletedTask;
            CardSelectCmd.OfferHandler=async(_,cards,_,skip)=>{
                if(DelayCreation)await Creation.Task;
                var screen=NChooseACardSelectionScreen.ShowScreen(cards,skip);var result=(await screen.CardsSelected()).ToArray();
                if(RetainScreen){screen.Visible=true;parent.World.Overlays.Screens.Add(screen);}else Close();return WrongRequest?Card("WRONG"):result.SingleOrDefault()!;
            };
            CardSelectCmd.BundleHandler=async(_,offers)=>{
                if(DelayCreation)await Creation.Task;
                var screen=NChooseABundleSelectionScreen.ShowScreen(offers);var result=(await screen.CardsSelected()).Single();
                if(RetainScreen){screen.Visible=true;parent.World.Overlays.Screens.Add(screen);}else Close();return WrongRequest?new[]{Card("WRONG")}:result;
            };
            NChooseACardSelectionScreen.Factory=(cards,skip)=>{
                var screen=new NChooseACardSelectionScreen();screen.Setup(cards,skip);screen.BindControls(Row);Screen=screen;screen.Bind("CardRow",Row);screen.BindSkip(Skip);screen.Bind("SkipButton",Skip);
                Skip.Clicked=()=>{Clicks++;screen.Complete(Array.Empty<CardModel>());};
                foreach(var card in cards){var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card},Hitbox=new NClickableControl()};
                    holder.RewardPressed=()=>{Clicks++;screen.Complete(new[]{WrongSelection?Card("WRONG"):card});};Row.Children.Add(holder);}
                parent.World.Overlays.Screens.Add(screen);ActiveScreenContext.Instance.Current=screen;return screen;
            };
            NChooseABundleSelectionScreen.Factory=offers=>{
                var screen=new NChooseABundleSelectionScreen();screen.Setup(offers);screen.BindControls(Row,Preview,PreviewCards,Confirm);Screen=screen;
                screen.Bind("%BundleRow",Row);screen.Bind("%BundlePreviewContainer",Preview);screen.Bind("%Cards",PreviewCards);screen.Bind("%Confirm",Confirm);
                foreach(var cards in offers){int index=Row.Children.Count;var item=new NCardBundle{Bundle=cards,CardNodes=cards.Select(c=>new NCard{Model=c}).ToArray()};
                    item.Clicked=()=>{Clicks++;Selected=index;screen.Select(item);Row.Visible=false;Preview.Visible=true;foreach(var node in item.CardNodes)PreviewCards.Children.Add(new NPreviewCardHolder{CardNode=node});};Row.Children.Add(item);}
                Confirm.Clicked=()=>{Clicks++;screen.Complete(new[]{WrongSelection?(IReadOnlyList<CardModel>)new[]{Card("WRONG")}:offers[Selected]});};
                parent.World.Overlays.Screens.Add(screen);ActiveScreenContext.Instance.Current=screen;return screen;
            };
        }
        internal void Close()
        {if(Screen is not null)Parent.World.Overlays.Screens.Remove(Screen);ActiveScreenContext.Instance.Current=Parent.World.Overlays.Screens.LastOrDefault()??(Control)Parent.World.Room;}
        public void Dispose()
        {
            CardSelectCmd.OfferHandler=null;CardSelectCmd.BundleHandler=null;NChooseACardSelectionScreen.Factory=null!;NChooseABundleSelectionScreen.Factory=null!;
            CardPileCmd.AfterAdded=null;CardPileCmd.Prevent=null;CardPileCmd.WrongResult=false;MegaCrit.Sts2.Core.Hooks.Hook.Modifier=null;
        }
    }
    private static void CompoundOfferCases()
    {
        foreach(string kind in new[]{"lead","massive","hefty","bundle"})foreach(bool skip in new[]{false,true}) {
            if(kind=="bundle"&&skip)continue;
            using var f=new CompoundRewardFixture();using var offer=new CompoundOfferFixture(f,kind);
            int before=f.World.Player.Deck.Cards.Count;var c=f.Start();var read=f.Act(c,"collect:0");
            Check(read.Status=="ready"&&read.Phase==(kind=="bundle"?"bundle_offer":"card_offer"),"compound actual offer phase "+kind);
            read=f.Act(c,skip?"skip":"choose:1");if(kind=="bundle"){Check(read.Phase=="bundle_preview","bundle exact preview");read=f.Act(c,"confirm");}
            Check(read.Status=="resolved"&&read.PriorResults.Count==(kind=="bundle"?3:2),"compound card pickup completes enclosing reward "+kind);
            Check(f.World.Player.Deck.Cards.Count-before==(kind=="bundle"?2:(skip?0:1)+(kind=="hefty"?1:0)),"actual chosen cards and optional Injury");
            Check(f.World.Session.Read().ParentReconciled==1,"card offer retains single parent event");
        }
        foreach(string mode in new[]{"nested","curse","creation","insertion","after","fault","closing","modified","prevented","wrong_request","wrong_selection","foreign_gold","ancestor"}) {
            using var f=new CompoundRewardFixture(tail:mode=="curse"?"curse":null);using var offer=new CompoundOfferFixture(f,"bundle",mode=="nested");
            offer.DelayCreation=mode=="creation";offer.DelayInsertion=mode=="insertion";offer.DelayCompletion=mode=="after";offer.Fault=mode=="fault";offer.RetainScreen=mode=="closing";
            offer.WrongRequest=mode=="wrong_request";offer.WrongSelection=mode=="wrong_selection";
            if(mode=="modified")MegaCrit.Sts2.Core.Hooks.Hook.Modifier=(_,card)=>{var clone=offer.Card(card.Id.Entry);clone.UpgradeInternal();return clone;};
            if(mode=="prevented")CardPileCmd.Prevent=_=>true;
            var c=f.Start();var read=f.Act(c,"collect:0");if(mode=="nested")read=f.Act(c,"collect:0");
            if(mode=="creation"){Check(read.Status=="waiting","native request creation retained");offer.Creation.SetResult();read=f.Read(c);}
            if(mode is "foreign_gold" or "ancestor") {
                if(mode=="foreign_gold")f.World.Player.Gold++;else f.World.Overlays.Screens[0]=new Control();
                Check(f.Read(c).Status=="unsupported","unowned offer state rejected: "+mode);continue;
            }
            f.Act(c,"choose:1");read=f.Read(c);
            var receipt=(GenericEventV7RewardChildApply)f.World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,read.DecisionId,"confirm");
            Check(receipt.Value.Outcome is "accepted" or "uncertain","offer input dispatched once "+mode);read=f.Read(c);
            if(mode is "insertion" or "after" or "closing") {
                Check(read.Status=="waiting"&&f.World.Session.Read().ParentReconciled==0,"unfinished native offer retained "+mode);
                if(mode=="insertion")offer.Insertion.SetResult();else if(mode=="after")offer.Completion.SetResult();else offer.Close();read=f.Read(c);
            }
            if(mode is "fault" or "wrong_request" or "wrong_selection"){Check(read.Status=="unsupported","failed offer cannot complete: "+mode);continue;}
            if(mode is "nested" or "curse")read=f.Act(c,"collect:1");
            Check(read.Status=="resolved","nested offer effect reconciliation "+mode+" "+read.Status);
            if(mode=="modified")Check(f.World.Player.Deck.Cards.TakeLast(2).All(c=>c.CurrentUpgradeLevel==1)&&offer.Offers.SelectMany(o=>o).All(c=>c.CurrentUpgradeLevel==0),"actual replacement models retained");
            Check(f.World.Session.Read().ParentReconciled==1,"nested offer parent completes "+mode);
        }
    }
}
