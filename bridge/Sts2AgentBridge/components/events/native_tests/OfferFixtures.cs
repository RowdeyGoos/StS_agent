using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.GenericEventV7;

internal static partial class Program {
    internal sealed class OfferFixture:IDisposable {
        internal readonly TransformFixture World;
        internal readonly bool Bundle;
        internal readonly IReadOnlyList<CardModel>[] Offers;
        internal readonly Control Row=new(),Preview=new(){Visible=false},PreviewCards=new();
        internal readonly NConfirmButton Confirm=new();
        internal readonly NChoiceSelectionSkipButton Skip=new();
        internal Control Screen=null!;
        internal readonly List<NGridCardHolder> Holders=new();
        internal readonly List<NCardBundle> Bundles=new();
        internal readonly TaskCompletionSource Creation=new(),Completion=new(),Insertion=new();
        internal bool DelayCreation,DelayCompletion,PartialAddition,DeferChoice,DeferConfirm,LostChoice,LostConfirm,WrongRequest,WrongSelection,Fault,ExtraCard,Nested,CanSkip;
        internal Action? PendingChoice,PendingConfirm;
        internal int Choices,Confirms,Skips,Selected=-1;
        internal GenericEventV7Session Session=>World.Session;
        internal OfferFixture(bool bundle,int count=3,int width=2,int dialogue=1) {
            Bundle=bundle;Time.Ticks=1000;
            World=new TransformFixture("OFFER",1,domain:2,eventModel:new AncientEventModel());
            AncientLayout(World.Room,World.Model,dialogue);
            Offers=Enumerable.Range(0,count).Select(i=>(IReadOnlyList<CardModel>)Enumerable.Range(0,bundle?width:1).Select(j=>World.NewCard("Offer_"+i+"_"+j)).ToArray()).ToArray();
            World.Room.Layout.OptionButtons[0].Option.Callback=async()=>{
                World.OptionCalls++;
                var cards=bundle?(await CardSelectCmd.FromChooseABundleScreen(World.Player,Offers)).ToArray():
                    new[]{await CardSelectCmd.FromChooseACardScreen(new PlayerChoiceContext(),Offers.Select(o=>o[0]).ToArray(),World.Player,CanSkip)};
                cards=cards.Where(c=>c is not null).ToArray();
                for(int i=0;i<cards.Length;i++){World.Player.Deck.Cards.Add(cards[i]);if(PartialAddition&&i==0)await Insertion.Task;}
                if(ExtraCard)World.Player.Deck.Cards.Add(World.NewCard("Unexpected"));
                if(Nested)await CardSelectCmd.FromChooseABundleScreen(World.Player,Offers);
                if(DelayCompletion)await Completion.Task;if(Fault)throw new InvalidOperationException("late callback");
                World.Model.IsFinished=true;World.Room.Layout.OptionButtons.Clear();
                var option=new EventOption{TextKey="PROCEED",IsProceed=true,Callback=()=>{World.OptionCalls++;World.Map.IsOpen=true;World.Map.IsTravelEnabled=true;return Task.CompletedTask;}};
                var button=new NEventOptionButton{Option=option,Event=World.Model};button.Bind("%Text",new MegaRichTextLabel{Text="Proceed"});World.Room.Layout.OptionButtons.Add(button);
            };
            CardSelectCmd.OfferHandler=async(context,cards,player,skip)=>{
                if(DelayCreation)await Creation.Task;
                var screen=NChooseACardSelectionScreen.ShowScreen(cards,skip);var result=(await screen.CardsSelected()).ToArray();
                return WrongRequest?World.NewCard("Wrong"):result.SingleOrDefault()!;
            };
            CardSelectCmd.BundleHandler=async(player,offers)=>{
                if(DelayCreation)await Creation.Task;
                var screen=NChooseABundleSelectionScreen.ShowScreen(offers);var result=(await screen.CardsSelected()).Single();
                return WrongRequest?new[]{World.NewCard("Wrong")}:result;
            };
            NChooseACardSelectionScreen.Factory=(cards,skip)=>{
                var screen=new NChooseACardSelectionScreen();screen.Setup(cards,skip);screen.BindControls(Row);Screen=screen;screen.Bind("CardRow",Row);screen.BindSkip(Skip);screen.Bind("SkipButton",Skip);
                Skip.Clicked=()=>{Skips++;if(LostChoice)return;Action apply=()=>screen.Complete(WrongSelection?new[]{World.NewCard("Wrong")}:Array.Empty<CardModel>());if(DeferChoice)PendingChoice=apply;else apply();};
                foreach(var card in cards){int index=Holders.Count;var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card},Hitbox=new NClickableControl()};
                    holder.RewardPressed=()=>{Choices++;if(LostChoice)return;Action apply=()=>{Selected=index;screen.Complete(new[]{WrongSelection?World.NewCard("Wrong"):card});};if(DeferChoice)PendingChoice=apply;else apply();};Holders.Add(holder);Row.Children.Add(holder);}
                World.Overlays.Screens.Add(screen);return screen;
            };
            NChooseABundleSelectionScreen.Factory=offers=>{
                var screen=new NChooseABundleSelectionScreen();screen.Setup(offers);screen.BindControls(Row,Preview,PreviewCards,Confirm);Screen=screen;
                screen.Bind("%BundleRow",Row);screen.Bind("%BundlePreviewContainer",Preview);screen.Bind("%Cards",PreviewCards);screen.Bind("%Confirm",Confirm);
                foreach(var cards in offers){int index=Bundles.Count;var item=new NCardBundle{Bundle=cards,CardNodes=cards.Select(c=>new NCard{Model=c}).ToArray()};
                    item.Clicked=()=>{Choices++;if(LostChoice)return;Action apply=()=>{Selected=index;screen.Select(item);Row.Visible=false;Preview.Visible=true;foreach(var node in item.CardNodes)PreviewCards.Children.Add(new NPreviewCardHolder{CardNode=node});};if(DeferChoice)PendingChoice=apply;else apply();};Bundles.Add(item);Row.Children.Add(item);}
                Confirm.Clicked=()=>{Confirms++;if(LostConfirm)return;Action apply=()=>screen.Complete(new[]{WrongSelection?(IReadOnlyList<CardModel>)new[]{World.NewCard("Wrong")}:offers[Selected]});if(DeferConfirm)PendingConfirm=apply;else apply();};
                World.Overlays.Screens.Add(screen);return screen;
            };
        }
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation c)=>((GenericEventV7RewardChildRead)Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
        internal string Apply(GenericEventV7Observation c,string decision,string action)=>((GenericEventV7RewardChildApply)Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,decision,action)).Value.Outcome;
        internal void Act(GenericEventV7Observation c,string action){var r=Read(c);Check(r.Status=="ready","offer ready: "+r.Status);Check(Apply(c,r.DecisionId,action)=="accepted","offer input "+action);}
        internal static void Set(object target,string name,object value)=>target.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)!.SetValue(target,value);
        public void Dispose(){World.Dispose();CardSelectCmd.OfferHandler=null;CardSelectCmd.BundleHandler=null;NChooseACardSelectionScreen.Factory=null!;NChooseABundleSelectionScreen.Factory=null!;}
    }
    private sealed class OfferProbe:IGenericEventV7OfferAdapter {
        internal Action? OnDispose;public GenericEventV7OfferCapture Capture()=>new("choose",new[]{new GenericEventV7Offer(0,new[]{new GenericEventV7RewardCard(0,"ONE",0)})});
        public void Dispatch(string action){}public void Dispose()=>OnDispose?.Invoke();
    }
    private static void OptionalOfferTests() {
        foreach(bool skip in new[]{false,true})foreach(bool extra in new[]{false,true}) {
            using var f=new OfferFixture(false){CanSkip=true,ExtraCard=extra,DelayCompletion=true};var c=f.Start();
            Check(c.Child!.ContractVersion=="card_offer_v2"&&f.Read(c).LegalActions.SequenceEqual(new[]{"choose:0","choose:1","choose:2","skip"}),"optional domain");
            f.Act(c,skip?"skip":"choose:1");Check(f.Read(c).Status=="waiting","optional waits parent");f.Completion.SetResult();var r=f.Read(c);
            Check(r.Status=="resolved"&&r.SelectedSlot==(skip?(int?)null:1)&&r.PriorResults.Single().Result==(skip?"skipped":"collected"),"optional exact completion");
            Check(r.AdditionalCards!.Count==(extra?1:0)&&f.World.Player.Deck.Cards.Count==3+(skip?0:1)+(extra?1:0),"bounded additional observation");
            Check(f.Skips==(skip?1:0)&&f.Choices==(skip?0:1),"one native optional action");
            var p=f.Session.Read();Check(p.Effects=="unverified"&&p.CompletedCardChildren==1,"compound effect remains unverified");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","optional map");
        }
        foreach(string fault in new[]{"skip_node","skip_field","skip_disabled","skip_hidden","can_skip","early_extra","early_offered","wrong_request","wrong_selection","lost","two_extras","offered_extra","prepend","extra_owner","extra_level","extra_key","extra_replace","extra_remove","baseline_change"}) {
            using var f=new OfferFixture(false){CanSkip=true,ExtraCard=true,DelayCompletion=true};var c=f.Start();var r=f.Read(c);
            bool before=fault.StartsWith("skip_",StringComparison.Ordinal)||fault is "can_skip" or "early_extra" or "early_offered";
            switch(fault) {
                case "skip_node":f.Screen.Bind("SkipButton",new NChoiceSelectionSkipButton());break;
                case "skip_field":OfferFixture.Set(f.Screen,"_skipButton",new NChoiceSelectionSkipButton());break;
                case "skip_disabled":f.Skip.IsEnabled=false;break;case "skip_hidden":f.Skip.Visible=false;break;
                case "can_skip":OfferFixture.Set(f.Screen,"_canSkip",false);break;
                case "early_extra":f.World.Player.Deck.Cards.Add(f.World.NewCard("Early"));break;
                case "early_offered":f.World.Player.Deck.Cards.Add(f.Offers[1][0]);break;
                case "wrong_request":f.WrongRequest=true;break;case "wrong_selection":f.WrongSelection=true;break;case "lost":f.LostChoice=true;break;
            }
            string action=fault=="prepend"?"choose:1":"skip";
            Check((f.Apply(c,r.DecisionId,action)=="accepted")==!before,"optional stale "+fault);
            if(!before&&fault is not ("wrong_request" or "wrong_selection" or "lost")) {
                Check(f.Read(c).Status=="waiting","observe extra before tampering");var deck=f.World.Player.Deck.Cards;
                switch(fault) {
                    case "two_extras":deck.Add(f.World.NewCard("Second"));break;
                    case "offered_extra":deck[^1]=f.Offers[2][0];break;
                    case "prepend":(deck[3],deck[4])=(deck[4],deck[3]);break;
                    case "extra_owner":deck[^1].Owner=new();break;case "extra_level":deck[^1].CurrentUpgradeLevel++;break;
                    case "extra_key":deck[^1].Id.Entry="Changed";break;case "extra_replace":deck[^1]=f.World.NewCard("Unexpected");break;
                    case "extra_remove":deck.RemoveAt(deck.Count-1);break;case "baseline_change":deck[0].CurrentUpgradeLevel++;break;
                }
                f.Completion.SetResult();
            }
            var end=f.Read(c);for(int i=0;i<257&&end.Status=="waiting";i++)end=f.Read(c);
            Check(end.Status=="unsupported"&&f.Skips+f.Choices==(before?0:1),"bounded optional failure "+fault);
        }
        using(var f=new OfferFixture(false){CanSkip=true,ExtraCard=true,PartialAddition=true}) {
            var c=f.Start();f.Act(c,"choose:0");Check(f.Read(c).Status=="waiting"&&f.World.Player.Deck.Cards.Count==4,"chosen before extra");f.Insertion.SetResult();Check(f.Read(c).Status=="resolved","chosen then extra settles");
        }
        using(var f=new OfferFixture(false){CanSkip=true,ExtraCard=true,DeferChoice=true}) {
            var c=f.Start();f.Act(c,"skip");Check(f.Read(c).Status=="waiting"&&f.World.Player.Deck.Cards.Count==3,"deferred skip no effect");f.PendingChoice!();Check(f.Read(c).Status=="resolved"&&f.Skips==1,"deferred skip settles");
        }
    }
    private static void OfferTests() {
        foreach(bool bundle in new[]{false,true})foreach(int count in (bundle?new[]{1,3,5}:new[]{1,2,3}))foreach(int width in (bundle?new[]{1,2,8}:new[]{1}))foreach(int choice in Enumerable.Range(0,count)) {
            using var f=new OfferFixture(bundle,count,width);var c=f.Start();Check(c.Status=="child"&&c.Child!.Kind=="card_offer","offer admission "+c.Status+" "+f.World.Adapter.LastDiagnostic);
            var r=f.Read(c);Check(r.Offers!.Count==count&&r.LegalActions.Count==count,"public exact domain");f.Act(c,"choose:"+choice);
            if(bundle){Check(f.Read(c).Phase=="preview"&&f.World.Player.Deck.Cards.Count==3,"preview no effect");f.Act(c,"confirm");}
            Check(f.Read(c).Status=="resolved"&&f.World.Player.Deck.Cards.SequenceEqual(f.World.Cards.Concat(f.Offers[choice])),"exact ordered additions");
            Check(f.Choices==1&&f.Confirms==(bundle?1:0),"one native input per action");var p=f.Session.Read();Check(p.CompletedCardChildren==1&&p.Phase=="proceed","offer parent reconciliation");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","offer map return");
        }
        foreach(bool bundle in new[]{false,true})foreach(string fault in new[]{"row","source","domain","model","node","owner","hitbox","baseline_owner","baseline_order","hidden","disabled","clickable","late_fault","wrong_request","wrong_selection","extra","lost","nested"}) {
            if(bundle&&fault=="clickable")continue;
            using var f=new OfferFixture(bundle);var c=f.Start();var r=f.Read(c);
            switch(fault){
                case "row":f.Screen.Bind(bundle?"%BundleRow":"CardRow",new Control());break;
                case "source":OfferFixture.Set(f.Screen,"_completionSource",bundle?(object)new TaskCompletionSource<IEnumerable<IReadOnlyList<CardModel>>>():new TaskCompletionSource<IEnumerable<CardModel>>());break;
                case "domain":OfferFixture.Set(f.Screen,bundle?"_bundles":"_cards",bundle?(object)f.Offers.ToArray():f.Offers.Select(o=>o[0]).ToArray());break;
                case "model":f.Offers[0][0].Id.Entry="Changed";break;
                case "node":if(bundle)f.Bundles[0].CardNodes=Array.Empty<NCard>();else f.Holders[0].CardNode=new NCard{Model=f.Offers[0][0]};break;
                case "owner":f.Offers[0][0].Owner=new();break;
                case "hitbox":if(bundle)f.Bundles[0].Hitbox=new();else f.Holders[0].Hitbox=new();break;
                case "baseline_owner":f.World.Cards[0].Owner=new();break;
                case "baseline_order":f.World.Player.Deck.Cards.Reverse();break;
                case "hidden":if(bundle)f.Bundles[0].Hitbox.Visible=false;else f.Holders[0].Visible=false;break;
                case "disabled":if(bundle)f.Bundles[0].Hitbox.IsEnabled=false;else f.Holders[0].Hitbox.IsEnabled=false;break;
                case "clickable":f.Holders[0].SetClickable(false);break;
                case "late_fault":f.Fault=true;break;case "wrong_request":f.WrongRequest=true;break;case "wrong_selection":f.WrongSelection=true;break;
                case "extra":f.ExtraCard=true;break;case "lost":f.LostChoice=true;break;case "nested":f.Nested=true;break;
            }
            bool after=fault is "late_fault" or "wrong_request" or "wrong_selection" or "extra" or "lost" or "nested";
            var result=f.Apply(c,r.DecisionId,"choose:0");Check((result=="accepted")==after,"stale offer guard "+fault+" "+result);
            if(after&&bundle&&fault!="lost")f.Act(c,"confirm");
            var end=f.Read(c);for(int i=0;i<257&&end.Status=="waiting";i++)end=f.Read(c);
            Check(end.Status=="unsupported"&&f.Choices==(after?1:0),"offer failure bounded "+fault+" "+end.Status);
        }
        foreach(string fault in new[]{"container","backing","cards","confirm","holder","selected","source","lost_confirm"}) {
            using var f=new OfferFixture(true);var c=f.Start();f.Act(c,"choose:1");var r=f.Read(c);
            switch(fault){case "backing":OfferFixture.Set(f.Screen,"_bundlePreviewCards",new Control());break;case "container":f.Screen.Bind("%BundlePreviewContainer",new Control());break;case "cards":f.Screen.Bind("%Cards",new Control());break;case "confirm":f.Screen.Bind("%Confirm",new NConfirmButton());break;case "holder":f.PreviewCards.Children[0]=new NPreviewCardHolder{CardNode=f.Bundles[1].CardNodes[0]};break;case "selected":((NChooseABundleSelectionScreen)f.Screen).Select(f.Bundles[0]);break;case "source":OfferFixture.Set(f.Screen,"_completionSource",new TaskCompletionSource<IEnumerable<IReadOnlyList<CardModel>>>());break;case "lost_confirm":f.LostConfirm=true;break;}
            Check((f.Apply(c,r.DecisionId,"confirm")=="accepted")==f.LostConfirm,"preview stale "+fault);var end=f.Read(c);for(int i=0;i<257&&end.Status=="waiting";i++)end=f.Read(c);Check(end.Status=="unsupported"&&f.Confirms==(f.LostConfirm?1:0),"preview failure "+fault);
        }
        foreach(bool bundle in new[]{false,true}) {
            using var f=new OfferFixture(bundle){DelayCreation=true,DelayCompletion=true,PartialAddition=bundle,DeferChoice=true,DeferConfirm=bundle};Check(f.Start().Status=="waiting","creation wait");f.Creation.SetResult();var c=f.Session.Read();f.Act(c,"choose:1");Check(f.Read(c).Status=="waiting","deferred choice wait");f.PendingChoice!();if(bundle){f.Act(c,"confirm");Check(f.Read(c).Status=="waiting","deferred confirm wait");f.PendingConfirm!();Check(f.Read(c).Status=="waiting","partial addition wait");f.Insertion.SetResult();}Check(f.Read(c).Status=="waiting","chosen wait");f.Completion.SetResult();Check(f.Read(c).Status=="resolved","deferred completion");
        }
        using(var f=new OfferFixture(false)){Time.Ticks=350;Check(f.Start().Status=="waiting","native opening rejects 350");Time.Ticks=351;var c=f.Session.Read();Check(c.Status=="child","native opening allows 351");f.Act(c,"choose:0");Check(f.Read(c).Status=="resolved","opening final");}
        using(var f=new OfferFixture(false,4)){Check(f.Start().Status=="unsupported","native max three");}
        OptionalOfferTests();
        foreach(bool bundle in new[]{false,true}) {
            using var f=new OfferFixture(bundle);foreach(var card in f.Offers.SelectMany(o=>o))card.Id.Entry="SAME_KEY";
            var c=f.Start();f.Act(c,"choose:2");if(bundle)f.Act(c,"confirm");
            Check(f.Read(c).Status=="resolved"&&f.World.Player.Deck.Cards.Skip(3).SequenceEqual(f.Offers[2]),"duplicate public keys retain exact selected models");
        }
        using(var f=new OfferFixture(true)){f.Offers[1]=f.Offers[0];Check(f.Start().Status=="unsupported","reused offered model identities rejected");}
        foreach(int patch in new[]{24,25,26,27}) {
            bool failed=false;
            try{using var hooks=new Sts2AgentBridge.Successors.GenericEventV7.Native.GenericEventV7Hooks(n=>{if(n==patch)throw new InvalidOperationException("offer install failure");},null);}catch(InvalidOperationException){failed=true;}
            Check(failed,"offer partial install stopped");
            foreach(var target in new[]{typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromChooseACardScreen))!,typeof(NChooseACardSelectionScreen).GetMethod(nameof(NChooseACardSelectionScreen.ShowScreen))!,typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromChooseABundleScreen))!,typeof(NChooseABundleSelectionScreen).GetMethod(nameof(NChooseABundleSelectionScreen.ShowScreen))!})
                Check(HarmonyLib.Harmony.GetPatchInfo(target)?.Owners.Count is null or 0,"offer partial install exact rollback");
            using var recovered=new Sts2AgentBridge.Successors.GenericEventV7.Native.GenericEventV7Hooks();
        }
        foreach(int mode in new[]{0,1,2}){var adapter=new OfferProbe();var session=new GenericEventV7OfferSession(new string('e',32),false,1,adapter);adapter.OnDispose=()=>{try{if(mode==0)session.Read();else if(mode==1)session.Apply("bad","choose:0");else session.Dispose();}catch{}};bool failed=false;try{session.Dispose();}catch{failed=true;}Check(failed,"cleanup reentry failure");}
    }
}
