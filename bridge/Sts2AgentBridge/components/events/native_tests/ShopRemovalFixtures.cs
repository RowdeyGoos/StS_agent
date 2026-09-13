using System;
using System.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

internal static partial class Program
{
    private sealed class ShopRemoveCapstone:ICapstoneScreen {}
    private static void ShopRemovalCases()
    {
        ShopRemovalCompletionOrderingCases();
        foreach(int count in new[]{1,3,64}) {
            using var f=new ShopRemoveFixture(count);f.Begin();
            Check(f.Entry.Subscribers==1&&f.Selects==0&&f.Confirms==0,"removal only opens owned selector");
            f.Dispatch.Advance();Check(f.Selects==1&&f.Confirms==0&&f.Player.Deck.Cards.Count==count,"exact card preview precedes commit");
            f.Dispatch.Advance();f.Dispatch.Advance();
            Check(f.Confirms==1&&f.Used==1&&f.Player.Gold==90&&!f.Player.Deck.Cards.Contains(f.Target),"single exact removal and debit");
            Check(f.Dispatch.Completion==ShopV1Completion.Succeeded&&!f.Dispatch.OwnsForeground,"wrapper callback and closed overlay certify completion");
            f.Dispatch.Dispose();f.Dispatch.Dispose();Check(f.Entry.Subscribers==0,"completed disposal detaches once");
        }
        foreach(string mode in new[]{"selecting_dispose","confirmed_dispose","cancel","wrong_preview","modal_before_select","modal_before_confirm","capstone_before_select","capstone_before_confirm","context","gold","card_level","card_owner","relic","potion","unremovable","foreign_overlay","duplicate_screen","bad_prefs","wrong_entry","throw_input","holder_replaced","confirm_replaced","wrong_counter","callback_modal","callback_context","certificate_throws"}) {
            using var f=new ShopRemoveFixture(3);f.Mode=mode;
            if(mode is "duplicate_screen" or "bad_prefs" or "wrong_entry" or "throw_input") {
                ShopRemoveThrows(f.Begin);ShopRemoveThrows(f.Dispatch.Dispose);ShopRemoveThrows(f.Dispatch.Dispose);
                Check(f.Selects==0&&f.Confirms==0,"invalid invocation never selects");continue;
            }
            f.Begin();
            bool afterSelect=mode is "confirmed_dispose" or "wrong_preview" or "modal_before_confirm" or "capstone_before_confirm" or "confirm_replaced" or "wrong_counter" or "callback_modal" or "callback_context" or "certificate_throws";
            if(afterSelect)f.Dispatch.Advance();
            switch(mode) {
                case "confirmed_dispose":f.Delay=true;f.Dispatch.Advance();break;
                case "cancel":f.Selection.SetResult(Array.Empty<CardModel>());f.Overlays.Screens.Clear();break;
                case "wrong_preview":((NPreviewCardHolder)f.PreviewCards.Children[0]).CardNode.Model=f.Cards[0];break;
                case "modal_before_select":case "modal_before_confirm":NModalContainer.Instance=new(){OpenModal=new object()};break;
                case "capstone_before_select":case "capstone_before_confirm":NCapstoneContainer.Instance!.CurrentCapstoneScreen=new ShopRemoveCapstone();break;
                case "context":f.Context=false;break;
                case "gold":f.Player.Gold--;break;
                case "card_level":f.Cards[0].CurrentUpgradeLevel++;break;
                case "card_owner":f.Cards[0].Owner=new Player();break;
                case "relic":var relic=new RelicModel{Owner=f.Player};relic.Id.Entry="EXTRA";f.Player.Relics.Add(relic);break;
                case "potion":var potion=new PotionModel{Owner=f.Player};potion.Id.Entry="EXTRA";f.Player.PotionSlots[0]=potion;break;
                case "unremovable":f.Target.IsRemovable=false;break;
                case "foreign_overlay":f.Overlays.Screens.Add(new object());break;
                case "holder_replaced":f.Grid.CurrentlyDisplayedCardHolders[0]=new();break;
                case "confirm_replaced":f.PreviewContainer.Bind("%PreviewConfirm",new NConfirmButton());break;
                case "wrong_counter":f.Dispatch.Advance();f.Used++;break;
                case "certificate_throws":f.Dispatch.Advance();f.CounterThrows=true;break;
            }
            if(mode is not ("selecting_dispose" or "confirmed_dispose" or "wrong_counter" or "certificate_throws"))ShopRemoveThrows(f.Dispatch.Advance);
            ShopRemoveThrows(f.Dispatch.Dispose);ShopRemoveThrows(f.Dispatch.Dispose);
            Check(f.Entry.Subscribers==0,"uncertain cleanup still detaches callback");
            Check(f.Confirms==(mode is "confirmed_dispose" or "wrong_counter" or "callback_modal" or "callback_context" or "certificate_throws"?1:0),"blocked removal never confirms or retries");
        }
    }
    private static void ShopRemovalCompletionOrderingCases()
    {
        foreach(string mode in new[]{"observer_last","callback_last","wrapper_last","both_pending","observer_fault","observer_cancel","observer_wrong","pending_dispose","pending_foreign_overlay","pending_context","pending_counter"}) {
            using var f=new ShopRemoveFixture(3);f.DelayObserver=true;
            f.Delay=mode is "callback_last" or "both_pending";
            f.DelayWrapper=mode=="wrapper_last";
            f.Begin();f.Dispatch.Advance();f.Dispatch.Advance();
            Check(f.Confirms==1&&f.Used==1&&f.Player.Gold==90&&!f.Player.Deck.Cards.Contains(f.Target),"native effect may precede observer: "+mode);
            Check(f.Screen.CardsSelectedCalls==2,"native caller and bridge have separate waiters");
            for(int i=0;i<3;i++) {
                f.Dispatch.Advance();
                Check(f.Dispatch.Completion==ShopV1Completion.Pending&&f.Confirms==1,"delayed observer waits without repeat input: "+mode);
            }
            if(mode is "observer_fault" or "observer_cancel" or "observer_wrong" or "pending_dispose" or "pending_foreign_overlay" or "pending_context" or "pending_counter") {
                switch(mode) {
                    case "observer_fault":f.Observer.SetException(new InvalidOperationException("fixture observer fault"));break;
                    case "observer_cancel":f.Observer.SetCanceled();break;
                    case "observer_wrong":f.Observer.SetResult(new[]{f.Cards[0]});break;
                    case "pending_foreign_overlay":f.Overlays.Screens.Add(new object());break;
                    case "pending_context":f.Context=false;break;
                    case "pending_counter":f.Used++;break;
                }
                if(mode is not ("pending_dispose" or "pending_counter"))ShopRemoveThrows(f.Dispatch.Advance);
                ShopRemoveThrows(f.Dispatch.Dispose);
                // A late observer cannot turn failed disposal into a clean handoff.
                if(!f.Observer.Task.IsCompleted)f.Observer.SetResult(new[]{f.Target});
                ShopRemoveThrows(f.Dispatch.Dispose);
                Check(f.Entry.Subscribers==0&&f.Confirms==1,"uncertain observer cleanup remains terminal: "+mode);
                continue;
            }
            if(mode=="both_pending") {
                f.Gate.SetResult();f.Dispatch.Advance();
                Check(f.Dispatch.Completion==ShopV1Completion.Pending,"callback may finish before independent observer");
            }
            f.Observer.SetResult(new[]{f.Target});f.Dispatch.Advance();
            if(mode is "callback_last" or "wrapper_last") {
                Check(f.Dispatch.Completion==ShopV1Completion.Pending,"observer does not substitute for purchase callback or wrapper");
                if(mode=="callback_last")f.Gate.SetResult();else f.WrapperGate.SetResult();
                f.Dispatch.Advance();
            }
            Check(f.Dispatch.Completion==ShopV1Completion.Succeeded&&f.Confirms==1,"both owned tasks settle before completion: "+mode);
            f.Dispatch.Dispose();f.Dispatch.Dispose();Check(f.Entry.Subscribers==0,"ordered completion releases callback");
        }
    }
    private static void ShopRemoveThrows(Action action){bool threw=false;try{action();}catch(InvalidOperationException){threw=true;}Check(threw,"removal fails explicitly");}
    private sealed class ShopRemoveFixture:IDisposable
    {
        private readonly MegaCrit.Sts2.Core.Nodes.NRun? _previousRun=MegaCrit.Sts2.Core.Nodes.NRun.Instance;
        internal readonly Player Player=new(){Gold=100};internal readonly MerchantInventory Inventory;
        internal readonly MerchantCardRemovalEntry Entry=new(){Cost=10};internal readonly NOverlayStack Overlays=new();
        internal readonly NDeckCardSelectScreen Screen=new();internal readonly NCardGrid Grid=new();
        internal readonly Control PreviewContainer=new(){Visible=false},PreviewCards=new();internal readonly NConfirmButton Confirm=new();
        internal readonly TaskCompletionSource<IEnumerable<CardModel>> Selection=new();internal readonly TaskCompletionSource Gate=new();
        internal readonly TaskCompletionSource<IEnumerable<CardModel>> Observer=new();internal readonly TaskCompletionSource WrapperGate=new();
        internal readonly CardModel[] Cards;internal CardModel Target=>Cards[^1];
        internal readonly PinnedShopRemovalDispatch Dispatch;internal readonly RemovePurchase Purchase;
        internal int Selects,Confirms,Used;internal bool Context=true,Delay,DelayObserver,DelayWrapper,CounterThrows;internal string Mode="";
        internal ShopRemoveFixture(int count) {
            NModalContainer.Instance=null;MegaCrit.Sts2.Core.Nodes.NRun.Instance=new(){GlobalUi=new(){CapstoneContainer=new()}};CardSelectCmd.Selector=null;
            Cards=Enumerable.Range(0,count).Select(i=>{var c=new CardModel{Owner=Player,IsRemovable=true};c.Id.Entry="CARD_"+i;return c;}).ToArray();Player.Deck.Cards.AddRange(Cards);
            Inventory=new(){Player=Player};Entry.SetPlayer(Player);Screen.SelectionTask=Selection.Task;
            Screen.SelectionTaskFactory=call=>DelayObserver&&call==2?Observer.Task:Selection.Task;
            Screen.Bind("%CardGrid",Grid);Screen.Bind("%PreviewContainer",PreviewContainer);PreviewContainer.Bind("%Cards",PreviewCards);PreviewContainer.Bind("%PreviewConfirm",Confirm);
            // Reverse display order to establish identity rather than a deck/grid index assumption.
            foreach(var card in Cards.Reverse()) {
                var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card,CardHighlight=new NCardHighlight{Material=new ShaderMaterial()}},Hitbox=new NClickableControl{IsEnabled=true}};
                holder.Selected=()=>{Selects++;PreviewContainer.Visible=true;PreviewCards.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=card}});};Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            Confirm.Clicked=()=>{Confirms++;Selection.SetResult(new[]{Target});Overlays.Screens.Clear();};
            NDeckCardSelectScreen.Factory=(_,_)=>Screen;
            Entry.Wrapper=async(inventory,ignore,cancelable)=>{
                if(Mode=="wrong_entry"){var wrong=new MerchantCardRemovalEntry();wrong.Wrapper=(_,_,_)=>Task.FromResult(false);return await wrong.OnTryPurchaseWrapper(inventory,false,true);}
                var prefs=new CardSelectorPrefs(1,1){Cancelable=true,RequireManualConfirmation=Mode!="bad_prefs"};
                var screen=NDeckCardSelectScreen.Create(Cards,prefs);if(Mode=="duplicate_screen")NDeckCardSelectScreen.Create(Cards,prefs);
                Overlays.Screens.Add(screen);var selected=await screen.CardsSelected();
                if(!selected.Any())return false;
                Player.Gold-=Entry.Cost;Player.Deck.Cards.Remove(selected.Single());Used++;Entry.Used=true;Entry.IsStocked=false;
                if(Delay)await Gate.Task;
                if(Mode=="callback_modal")NModalContainer.Instance=new(){OpenModal=new object()};if(Mode=="callback_context")Context=false;
                Entry.Complete(PurchaseStatus.Success);if(DelayWrapper)await WrapperGate.Task;return true;
            };
            Purchase=new RemovePurchase(this);Dispatch=new(Entry,Inventory,Player,Overlays,Purchase,()=>Context,()=>CounterThrows?throw new InvalidOperationException("counter unavailable"):Used);
        }
        internal void Begin(){Dispatch.SelectTarget(new(Target,Target.Id.Entry,Target.CurrentUpgradeLevel,true));Dispatch.Invoke();}
        public void Dispose(){try{Dispatch.Dispose();}catch(InvalidOperationException){}NModalContainer.Instance=null;MegaCrit.Sts2.Core.Nodes.NRun.Instance=_previousRun;NDeckCardSelectScreen.Factory=null;}
    }
    private sealed class RemovePurchase(ShopRemoveFixture fixture):IShopV1NativeDispatch
    {
        private ShopV1Completion _completion=ShopV1Completion.Pending;private bool _subscribed;
        public ShopV1Completion Completion=>_completion;
        public void Invoke(){fixture.Entry.PurchaseCompleted+=Completed;_subscribed=true;if(fixture.Mode=="throw_input")throw new InvalidOperationException();_=fixture.Entry.OnTryPurchaseWrapper(fixture.Inventory,false,true);}
        private void Completed(PurchaseStatus status,MerchantEntry entry){_completion=status==PurchaseStatus.Success&&ReferenceEquals(entry,fixture.Entry)?ShopV1Completion.Succeeded:ShopV1Completion.Invalid;}
        public void Dispose(){if(_subscribed){fixture.Entry.PurchaseCompleted-=Completed;_subscribed=false;}}
    }
}
