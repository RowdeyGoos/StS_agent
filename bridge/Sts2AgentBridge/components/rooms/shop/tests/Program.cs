using System;
using Sts2AgentBridge.Successors.ItemV1;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Tests;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int _checks;

    private static int Main()
    {
        try
        {
            Check(DiscardPurchases);
            Check(RestockedPurchases);
            Check(RemovalPurchases);
            Check(RelicPurchases);
            Check(PotionPurchases);
            Check(MultiplePurchases);
            Check(PurchaseCloseLeave);
            Check(ZeroPurchaseCloseLeave);
            Check(PurchaseWaitingAndContradictions);
            Check(StaleAndMalformedSurfaces);
            Check(LimitsAndActionGrammar);
            Check(PendingLimitFinalRead);
            Check(DispatchFailureAndNoRetry);
            Check(ReentrantCaptureGuards);
            Check(ReentrantDispatchGuards);
            Check(OwnerThreadGate);
            Check(CleanupFailures);
            Check(OutputShapeAndImmutability);
            Check(CanonicalDigest);
            Check(MapTravelPermissionRepair);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"shop_map_permission_v1_core\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"shop_map_permission_v1_core\",\"check_count\":0}");
            return 1;
        }
    }

    private static void DiscardPurchases() {
        var f=new MultiplePurchaseFixture(2){AllowDiscards=true};foreach(var offer in f.Offers)offer.Kind=ShopV1OfferKind.Potion;
        f.Potions.Add(new(new object(),"OLD_0"));f.Potions.Add(new(new object(),"OLD_1"));
        using(var session=new ShopV1Session(Nonce,f)) {
            var ready=Obs(session.Read());Sequence(new[]{"discard:0","discard:1","inventory:close"},ready.LegalActions);
            Receipt(session.Apply(ready.DecisionId,"discard:0"));ready=Obs(session.Read());Equal(100,ready.Player.Gold);Equal("discard_potion",ready.PriorResults[0].Kind);
            Receipt(session.Apply(ready.DecisionId,"buy:potion:0"));ready=Obs(session.Read());Sequence(new[]{"discard:1","inventory:close"},ready.LegalActions);
            Receipt(session.Apply(ready.DecisionId,"discard:1"));ready=Obs(session.Read());Receipt(session.Apply(ready.DecisionId,"buy:potion:1"));
            ready=Obs(session.Read());Sequence(new[]{"inventory:close"},ready.LegalActions);Equal(2,f.Discards);Equal(2,f.Purchases);
        }
        foreach(string mode in new[]{"gold","deck","relic","wrong_slot","same_key","stale"}) {
            f=new MultiplePurchaseFixture(1){AllowDiscards=true};f.Potions.Add(new(new object(),"OLD_0"));f.Potions.Add(new(new object(),"OLD_1"));
            using var session=new ShopV1Session(Nonce,f);var ready=Obs(session.Read());var target=f.Potions[0];
            if(mode=="stale"){f.Potions[0]=new(new object(),"OLD_0");Equal("unsupported",Failure(session.Apply(ready.DecisionId,"discard:0")).Outcome);Equal(0,f.Discards);continue;}
            Receipt(session.Apply(ready.DecisionId,"discard:0"));
            if(mode=="gold")f.Gold--;if(mode=="deck")f.Deck.Clear();if(mode=="relic")f.Relics.Add(new(new object(),"NEW"));
            if(mode=="wrong_slot"){f.Potions[0]=target;f.Potions[1]=new(null,null);}if(mode=="same_key")f.Potions[0]=new(new object(),"OLD_0");
            Equal("unsupported",Obs(session.Read()).Status);Equal(1,f.Discards);
        }
    }
    private static void RestockedPurchases()
    {
        foreach(var kind in new[]{ShopV1OfferKind.Card,ShopV1OfferKind.Potion,ShopV1OfferKind.Relic}) {
            var f=new MultiplePurchaseFixture(1){Restock=true};f.Offers[0].Kind=kind;
            for(int i=0;i<8;i++)f.Potions.Add(new(null,null));
            using var session=new ShopV1Session(Nonce,f);
            for(int i=0;i<8;i++) {
                var ready=Obs(session.Read());Equal("ready",ready.Status);Equal(10+i,ready.Offers[0].DisplayedPrice);
                f.Gold=1000; // Re-observe gold before reserving this transaction.
                ready=Obs(session.Read());Receipt(session.Apply(ready.DecisionId,ready.LegalActions[0]));
            }
            var capped=Obs(session.Read());Sequence(new[]{"inventory:close"},capped.LegalActions);
            Receipt(session.Apply(capped.DecisionId,"inventory:close"));capped=Obs(session.Read());Receipt(session.Apply(capped.DecisionId,"leave"));Equal("complete",Obs(session.Read()).Status);
        }
        foreach(string mode in new[]{"model","key","price","absent","debit","old_model","cleared","hidden"}) {
            var f=new MultiplePurchaseFixture(1){Restock=true};using var session=new ShopV1Session(Nonce,f);
            var ready=Obs(session.Read());var old=f.Offers[0].Card;Receipt(session.Apply(ready.DecisionId,"buy:card:0"));
            var offer=f.Offers[0];
            if(mode is "cleared" or "hidden")offer.Stocked=false;
            if(mode=="model")offer.Card=new();
            if(mode=="key")offer.KeyOverride="OTHER";
            if(mode=="price")offer.Price++;
            if(mode=="absent")offer.Restocked=null;
            if(mode=="debit")f.Gold--;
            if(mode=="old_model")offer.Card=old;
            Equal("unsupported",Obs(session.Read()).Status);Equal(1,f.Purchases);
        }
    }
    private static MultiplePurchaseFixture RemovalFixture()
    {
        var f=new MultiplePurchaseFixture(2);f.Offers[1].Kind=ShopV1OfferKind.Removal;
        f.Deck.Add(new(new object(),"REMOVE_ME",1,true));f.Deck.Add(new(new object(),"KEEP",0,true));
        f.Potions.Add(new(new object(),"OLD_POTION"));f.Relics.Add(new(new object(),"OLD_RELIC"));return f;
    }
    private static void RemovalPurchases()
    {
        var f=RemovalFixture();
        using(var session=new ShopV1Session(Nonce,f)) {
            var ready=Obs(session.Read());Sequence(new[]{"buy:card:0","remove:1","remove:2","inventory:close"},ready.LegalActions);
            Equal(1,ready.RemovalCandidates[0].UpgradeLevel);Equal(1,ready.RemovalCandidates[0].DeckSlot);
            Equal("rejected",Failure(session.Apply(ready.DecisionId,"remove:0")).Outcome);Equal(0,f.Purchases);
            Receipt(session.Apply(ready.DecisionId,"remove:1"));ready=Obs(session.Read());Equal("ready",ready.Status);
            Equal("remove_card",ready.PriorResults[0].Kind);Equal(2,ready.Player.DeckCount);Equal(90,ready.Player.Gold);
            Sequence(new[]{"buy:card:0","inventory:close"},ready.LegalActions);Equal(0,ready.RemovalCandidates.Count);
            Receipt(session.Apply(ready.DecisionId,"buy:card:0"));ready=Obs(session.Read());Equal(3,ready.Player.DeckCount);
            Receipt(session.Apply(ready.DecisionId,"inventory:close"));ready=Obs(session.Read());Receipt(session.Apply(ready.DecisionId,"leave"));Equal("complete",Obs(session.Read()).Status);
        }
        foreach(string mode in new[]{"stale_model","stale_level","stale_eligible","wrong_card","same_key_wrong_card","missing","extra","reordered","survivor_level","debit","unpaid","stock","relic","potion","pending"}) {
            f=RemovalFixture();using var session=new ShopV1Session(Nonce,f);var ready=Obs(session.Read());
            var target=f.Deck[1];var keep=f.Deck[2];
            if(mode.StartsWith("stale")) {
                f.Deck[1]=new(mode=="stale_model"?new object():target.ModelIdentity,target.StableKey,mode=="stale_level"?2:1,mode!="stale_eligible");
                Equal("unsupported",Failure(session.Apply(ready.DecisionId,"remove:1")).Outcome);Equal(0,f.Purchases);continue;
            }
            Receipt(session.Apply(ready.DecisionId,"remove:1"));
            switch(mode) {
                case "wrong_card":f.Deck[1]=target;break;
                case "same_key_wrong_card":f.Deck[1]=new(new object(),keep.StableKey,keep.UpgradeLevel,keep.Removable);break;
                case "missing":f.Deck.Insert(1,target);break;
                case "extra":f.Deck.RemoveAt(1);break;
                case "reordered":f.Deck.Reverse();break;
                case "survivor_level":f.Deck[1]=new(keep.ModelIdentity,keep.StableKey,1,true);break;
                case "debit":f.Gold--;break;
                case "unpaid":f.Gold=100;break;
                case "stock":f.Offers[1].Stocked=true;break;
                case "relic":f.Relics.Clear();break;
                case "potion":f.Potions.Clear();break;
                case "pending":f.Offers[1].State=ShopV1Completion.Pending;break;
            }
            if(mode=="pending"){Equal("waiting",Obs(session.Read()).Status);f.Offers[1].State=ShopV1Completion.Succeeded;Equal("ready",Obs(session.Read()).Status);}
            else {Equal("unsupported",Obs(session.Read()).Status);Equal("unsupported",Failure(session.Apply(ready.DecisionId,"remove:1")).Outcome);}
            Equal(1,f.Purchases);
        }
        foreach(string mode in new[]{"empty","poor","many","duplicate_service"}) {
            f=RemovalFixture();if(mode=="empty")f.Deck.RemoveRange(1,2);if(mode=="poor")f.Gold=0;
            if(mode=="many")for(int i=0;i<63;i++)f.Deck.Add(new(new object(),"CARD_"+i,0,true));
            if(mode=="duplicate_service")f.Offers[0].Kind=ShopV1OfferKind.Removal;
            using var session=new ShopV1Session(Nonce,f);var ready=Obs(session.Read());
            if(mode is "many" or "duplicate_service")Equal("unsupported",ready.Status);
            else Equal(false,ready.LegalActions.Any(a=>a.StartsWith("remove:")));
        }
    }

    private static MultiplePurchaseFixture RelicFixture(bool belt=false)
    {
        var f=new MultiplePurchaseFixture(1);f.Offers[0].Kind=ShopV1OfferKind.Relic;
        if(belt){f.Offers[0].KeyOverride="POTION_BELT";f.Offers[0].CapacityGain=2;}
        f.Relics.Add(new(new object(),"OLD_RELIC"));f.Potions.Add(new(new object(),"OLD_POTION"));
        return f;
    }
    private static void RelicPurchases()
    {
        foreach(bool belt in new[]{false,true}) {
            var f=RelicFixture(belt);using var session=new ShopV1Session(Nonce,f);
            var ready=Obs(session.Read());Receipt(session.Apply(ready.DecisionId,"buy:relic:0"));ready=Obs(session.Read());
            Equal("ready",ready.Status);Equal("purchase_relic",ready.PriorResults[0].Kind);Equal(90,ready.Player.Gold);
            Sequence(new[]{"OLD_RELIC",belt?"POTION_BELT":"RELIC_0"},ready.Player.Relics);
            Equal(belt?3:1,ready.Player.PotionSlots.Count);Equal("OLD_POTION",ready.Player.PotionSlots[0]);
            Equal(1,f.Disposals);Receipt(session.Apply(ready.DecisionId,"inventory:close"));ready=Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId,"leave"));Equal("complete",Obs(session.Read()).Status);
        }
        // Native relic purchase debits first, appends before AfterObtained, then signals completion.
        {
            var f=RelicFixture(true);f.Delay=true;using var session=new ShopV1Session(Nonce,f);var ready=Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId,"buy:relic:0"));Equal("waiting",Obs(session.Read()).Status);
            f.Gold=90;Equal("waiting",Obs(session.Read()).Status);
            f.Relics.Add(new(f.Offers[0].Card,"POTION_BELT"));Equal("waiting",Obs(session.Read()).Status);
            f.Potions.Add(new(null,null));f.Potions.Add(new(null,null));Equal("waiting",Obs(session.Read()).Status);
            f.Offers[0].Stocked=false;f.Offers[0].State=ShopV1Completion.Succeeded;
            Equal("ready",Obs(session.Read()).Status);Equal(1,f.Purchases);Equal(1,f.Disposals);
        }
        foreach(bool appended in new[]{false,true}) {
            var f=RelicFixture(true);f.Delay=true;using var session=new ShopV1Session(Nonce,f);var ready=Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId,"buy:relic:0"));f.Offers[0].Stocked=false;
            if(appended){f.Gold=90;f.Relics.Add(new(f.Offers[0].Card,"POTION_BELT"));}
            Equal("unsupported",Obs(session.Read()).Status);Equal(1,f.Disposals);
        }
        foreach(bool capacityFirst in new[]{false,true}) {
            var f=RelicFixture(true);f.Delay=true;using var session=new ShopV1Session(Nonce,f);var ready=Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId,"buy:relic:0"));
            if(capacityFirst){f.Gold=90;f.Potions.Add(new(null,null));f.Potions.Add(new(null,null));}
            else f.Relics.Add(new(f.Offers[0].Card,"POTION_BELT"));
            Equal("unsupported",Obs(session.Read()).Status);Equal(1,f.Purchases);Equal(1,f.Disposals);
        }
        foreach(string mode in new[]{"stale","missing","wrong_model","wrong_key","wrong_order","extra","survivor","deck","potion","missing_capacity","filled_capacity","extra_capacity","debit","card_survivor","potion_survivor","close_survivor"}) {
            var f=RelicFixture(true);using var session=new ShopV1Session(Nonce,f);
            if(mode=="card_survivor"){f.Offers[0].Kind=ShopV1OfferKind.Card;f.Offers[0].CapacityGain=0;}
            if(mode=="potion_survivor"){f.Offers[0].Kind=ShopV1OfferKind.Potion;f.Offers[0].CapacityGain=0;f.Potions.Add(new(null,null));}
            var ready=Obs(session.Read());
            if(mode=="stale"){f.Relics[0]=new(new object(),"OLD_RELIC");Equal("unsupported",Failure(session.Apply(ready.DecisionId,"buy:relic:0")).Outcome);Equal(0,f.Purchases);continue;}
            string action=mode=="card_survivor"?"buy:card:0":mode=="potion_survivor"?"buy:potion:0":mode=="close_survivor"?"inventory:close":"buy:relic:0";
            Receipt(session.Apply(ready.DecisionId,action));
            switch(mode) {
                case "missing":f.Relics.RemoveAt(1);break;
                case "wrong_model":f.Relics[1]=new(new object(),"POTION_BELT");break;
                case "wrong_key":f.Relics[1]=new(f.Offers[0].Card,"WRONG");break;
                case "wrong_order":f.Relics.Reverse();break;
                case "extra":f.Relics.Add(new(new object(),"EXTRA"));break;
                case "survivor":case "card_survivor":case "potion_survivor":case "close_survivor":f.Relics[0]=new(new object(),"OLD_RELIC");break;
                case "deck":f.Deck.Add(new(new object(),"EXTRA"));break;
                case "potion":f.Potions[0]=new(new object(),"OLD_POTION");break;
                case "missing_capacity":f.Potions.RemoveAt(2);break;
                case "filled_capacity":f.Potions[1]=new(new object(),"EXTRA");break;
                case "extra_capacity":f.Potions.Add(new(null,null));break;
                case "debit":f.Gold--;break;
            }
            Equal("unsupported",Obs(session.Read()).Status);Equal("unsupported",Failure(session.Apply(ready.DecisionId,action)).Outcome);
            Equal(mode=="close_survivor"?0:1,f.Purchases);
        }
        foreach(string mode in new[]{"full","owned","max_relics","bad_gain","wrong_kind","wrong_gain_key","duplicate_identity"}) {
            var f=RelicFixture(true);
            if(mode=="full")for(int i=0;i<6;i++)f.Potions.Add(new(null,null));
            if(mode=="owned")f.Relics.Add(new(new object(),"POTION_BELT"));
            if(mode=="max_relics")for(int i=1;i<128;i++)f.Relics.Add(new(new object(),"R_"+i));
            if(mode=="bad_gain")f.Offers[0].CapacityGain=1;
            if(mode=="wrong_kind")f.Offers[0].Kind=ShopV1OfferKind.Card;
            if(mode=="wrong_gain_key")f.Offers[0].KeyOverride="OTHER";
            if(mode=="duplicate_identity")f.Relics.Add(f.Relics[0]);
            using var session=new ShopV1Session(Nonce,f);var ready=Obs(session.Read());
            if(mode is "full" or "owned" or "max_relics")Sequence(new[]{"inventory:close"},ready.LegalActions);else Equal("unsupported",ready.Status);
            Equal(0,f.Purchases);
        }
    }

    private static MultiplePurchaseFixture PotionFixture()
    {
        var f=new MultiplePurchaseFixture(3);
        foreach(var offer in f.Offers)offer.Kind=ShopV1OfferKind.Potion;
        f.Potions.Add(new(new object(),"OLD_POTION"));f.Potions.Add(new(null,null));f.Potions.Add(new(null,null));
        return f;
    }
    private static void PotionPurchases()
    {
        var f=PotionFixture();
        using(var session=new ShopV1Session(Nonce,f)) {
            var ready=Obs(session.Read());
            Equal("rejected",Failure(session.Apply(ready.DecisionId,"buy:card:0")).Outcome);Equal(0,f.Purchases);
            for(int i=0;i<2;i++) {
                Receipt(session.Apply(ready.DecisionId,"buy:potion:"+i));ready=Obs(session.Read());
                Equal("purchase_potion",ready.PriorResults[0].Kind);Equal(i+1,f.Disposals);Equal(1,ready.Player.DeckCount);
                Equal("POTION_"+i,ready.Player.PotionSlots[i+1]);Equal("OLD_POTION",ready.Player.PotionSlots[0]);
            }
            Sequence(new[]{"inventory:close"},ready.LegalActions);Equal(80,ready.Player.Gold);
            Receipt(session.Apply(ready.DecisionId,"inventory:close"));ready=Obs(session.Read());Receipt(session.Apply(ready.DecisionId,"leave"));
            Equal("complete",Obs(session.Read()).Status);Equal(2,f.Purchases);
        }
        foreach(string mode in new[]{"stale","capacity","survivor","wrong_model","wrong_key","wrong_slot","missing","deck","debit","pending","card_survivor","close_survivor"}) {
            f=PotionFixture();using var session=new ShopV1Session(Nonce,f);
            if(mode=="card_survivor")f.Offers[0].Kind=ShopV1OfferKind.Card;
            var ready=Obs(session.Read());
            if(mode=="stale") {
                f.Potions[0]=new(new object(),"OLD_POTION");Equal("unsupported",Failure(session.Apply(ready.DecisionId,"buy:potion:0")).Outcome);Equal(0,f.Purchases);continue;
            }
            string action=mode=="card_survivor"?"buy:card:0":mode=="close_survivor"?"inventory:close":"buy:potion:0";
            Receipt(session.Apply(ready.DecisionId,action));
            switch(mode) {
                case "capacity":f.Potions.Add(new(null,null));break;
                case "survivor":case "card_survivor":case "close_survivor":f.Potions[0]=new(new object(),"OLD_POTION");break;
                case "wrong_model":f.Potions[1]=new(new object(),"POTION_0");break;
                case "wrong_key":f.Potions[1]=new(f.Offers[0].Card,"WRONG");break;
                case "wrong_slot":f.Potions[2]=f.Potions[1];f.Potions[1]=new(null,null);break;
                case "missing":f.Potions[1]=new(null,null);break;
                case "deck":f.Deck.Add(new(new object(),"EXTRA"));break;
                case "debit":f.Gold--;break;
                case "pending":f.Gold=100;f.Offers[0].State=ShopV1Completion.Pending;break;
            }
            if(mode=="pending") {
                Equal("waiting",Obs(session.Read()).Status);Equal(0,f.Disposals);
                f.Gold=90;f.Offers[0].State=ShopV1Completion.Succeeded;Equal("ready",Obs(session.Read()).Status);Equal(1,f.Disposals);
            } else {
                Equal("unsupported",Obs(session.Read()).Status);
                Equal("unsupported",Failure(session.Apply(ready.DecisionId,action)).Outcome);Equal(mode=="close_survivor"?0:1,f.Purchases);
            }
        }
        foreach(string mode in new[]{"full","duplicate","malformed","too_many"}) {
            f=PotionFixture();
            if(mode=="full")for(int i=1;i<3;i++)f.Potions[i]=new(new object(),"FULL_"+i);
            if(mode=="duplicate")f.Potions[1]=f.Potions[0];
            if(mode=="malformed")f.Potions[1]=new(null,"INVALID");
            if(mode=="too_many")for(int i=0;i<6;i++)f.Potions.Add(new(null,null));
            using var session=new ShopV1Session(Nonce,f);var ready=Obs(session.Read());
            if(mode=="full")Sequence(new[]{"inventory:close"},ready.LegalActions);else Equal("unsupported",ready.Status);
            Equal(0,f.Purchases);
        }
    }

    private static void MultiplePurchases()
    {
        foreach(int count in new[]{0,1,2,8}) {
            var f=new MultiplePurchaseFixture();using var session=new ShopV1Session(Nonce,f);
            var ready=Obs(session.Read());string initial=ready.DecisionId;
            for(int i=0;i<count;i++) {
                Equal("accepted",Receipt(session.Apply(ready.DecisionId,"buy:card:"+i)).Outcome);
                ready=Obs(session.Read());Equal("ready",ready.Status);Equal(i+1,f.Disposals);
                Equal("purchase_card",ready.PriorResults[0].Kind);Equal(100-10*(i+1),ready.Player.Gold);
                Equal(i+2,ready.Player.DeckCount);Equal("rejected",Failure(session.Apply(initial,"buy:card:0")).Outcome);
            }
            if(count==8)Sequence(new[]{"inventory:close"},ready.LegalActions);
            Receipt(session.Apply(ready.DecisionId,"inventory:close"));ready=Obs(session.Read());Receipt(session.Apply(ready.DecisionId,"leave"));
            Equal("complete",Obs(session.Read()).Status);Equal(count,f.Purchases);Equal(1,f.Closes);Equal(1,f.Leaves);
        }
        var restocked=new MultiplePurchaseFixture();
        using(var session=new ShopV1Session(Nonce,restocked)) {
            var r=Obs(session.Read());Receipt(session.Apply(r.DecisionId,"buy:card:0"));r=Obs(session.Read());
            restocked.Offers[0].Stocked=true;restocked.Offers[0].Card=new object();
            Equal("unsupported",Obs(session.Read()).Status);
            Equal("unsupported",Failure(session.Apply(r.DecisionId,"buy:card:1")).Outcome);Equal(1,restocked.Purchases);
        }
        foreach(string failure in new[]{"debit","dispatch","cleanup","delayed"}) {
            var f=new MultiplePurchaseFixture();var session=new ShopV1Session(Nonce,f);
            var r=Obs(session.Read());Receipt(session.Apply(r.DecisionId,"buy:card:0"));r=Obs(session.Read());
            f.BadDebitAt=failure=="debit"?2:-1;f.FailAt=failure=="dispatch"?2:-1;f.BadCleanupAt=failure=="cleanup"?2:-1;f.Delay=failure=="delayed";
            var receipt=session.Apply(r.DecisionId,"buy:card:1");
            if(failure=="dispatch")Equal("uncertain",Failure(receipt).Outcome);
            else Equal("accepted",Receipt(receipt).Outcome);
            var next=Obs(session.Read());
            if(failure=="delayed") {Equal("waiting",next.Status);Equal(1,f.Disposals);f.Settle(f.Pending!);next=Obs(session.Read());Equal("ready",next.Status);}
            else {Equal("unsupported",next.Status);Equal(0,f.Closes);Equal("unsupported",Failure(session.Apply(r.DecisionId,"buy:card:1")).Outcome);}
            if(failure=="cleanup")Throws<InvalidOperationException>(session.Dispose);else session.Dispose();
            Equal(2,f.Purchases);
        }
    }

    private static void PurchaseCloseLeave()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Equal("ready", ready.Status); Equal("inventory_browse", ready.Phase);
        Sequence(new[] { "buy:card:7", "inventory:close" }, ready.LegalActions);
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
        Equal("accepted", receipt.Outcome); Equal(1, f.Dispatch.InvokeCount);
        Equal("purchase_waiting", Obs(session.Read()).Phase);
        f.CompletePurchase();
        ShopV1Observation afterPurchase = Obs(session.Read());
        Equal("ready", afterPurchase.Status); Equal(1, afterPurchase.PriorResults.Count);
        Equal("purchase_card", afterPurchase.PriorResults[0].Kind);
        Sequence(new[] { "inventory:close" }, afterPurchase.LegalActions);
        RoomFlowDispatchReceipt closeReceipt = Receipt(session.Apply(
            afterPurchase.DecisionId, "inventory:close"));
        Equal("accepted", closeReceipt.Outcome); Equal(1, f.BackCount);
        ShopV1Observation leaveReady = Obs(session.Read());
        Equal("room_ready_to_leave", leaveReady.Phase);
        Equal("inventory_close", leaveReady.PriorResults[0].Kind);
        Sequence(new[] { "leave" }, leaveReady.LegalActions);
        Receipt(session.Apply(leaveReady.DecisionId, "leave"));
        Equal(1, f.ProceedCount);
        ShopV1Observation complete = Obs(session.Read());
        Equal("complete", complete.Status); Equal("complete", complete.Phase);
        Equal("leave", complete.PriorResults[0].Kind);
        Empty(complete.LegalActions); Empty(complete.Offers);
        int reads = f.Adapter.SurfaceCalls;
        f.MapOpen = false; f.MapTravelEnabled = false;
        Equal("complete", Obs(session.Read()).Status);
        Equal(reads, f.Adapter.SurfaceCalls);
        Equal("rejected", Failure(session.Apply(leaveReady.DecisionId, "leave")).Outcome);
        session.Dispose();
        Equal("unsupported", Obs(session.Read()).Status);
    }

    private static void ZeroPurchaseCloseLeave()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Receipt(session.Apply(ready.DecisionId, "inventory:close"));
        ShopV1Observation leave = Obs(session.Read());
        Equal(0, f.Dispatch.InvokeCount); Equal("inventory_close", leave.PriorResults[0].Kind);
        Receipt(session.Apply(leave.DecisionId, "leave"));
        Equal("complete", Obs(session.Read()).Status);
    }

    private static void PurchaseWaitingAndContradictions()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
        f.Gold -= f.Price;
        Equal("waiting", Obs(session.Read()).Status);
        f.Dispatch.CompletionValue = ShopV1Completion.Succeeded;
        f.Deck.Add(new ShopV1DeckCardBinding(f.Card, f.CardKey));
        f.Stocked = false; f.TargetModel = null;
        Equal("ready", Obs(session.Read()).Status);

        var insertionFirst = new Fixture();
        using var insertionSession = new ShopV1Session(Nonce, insertionFirst.Adapter);
        ShopV1Observation insertionReady = Obs(insertionSession.Read());
        Receipt(insertionSession.Apply(insertionReady.DecisionId, "buy:card:7"));
        insertionFirst.Deck.Add(new ShopV1DeckCardBinding(
            insertionFirst.Card, insertionFirst.CardKey));
        Equal("waiting", Obs(insertionSession.Read()).Status);
        insertionFirst.Gold -= insertionFirst.Price;
        insertionFirst.Stocked = false; insertionFirst.TargetModel = null;
        Equal("waiting", Obs(insertionSession.Read()).Status);
        insertionFirst.Dispatch.CompletionValue = ShopV1Completion.Succeeded;
        Equal("ready", Obs(insertionSession.Read()).Status);

        var wrong = new Fixture();
        using var wrongSession = new ShopV1Session(Nonce, wrong.Adapter);
        ShopV1Observation wrongReady = Obs(wrongSession.Read());
        Receipt(wrongSession.Apply(wrongReady.DecisionId, "buy:card:7"));
        wrong.Dispatch.CompletionValue = ShopV1Completion.Succeeded;
        wrong.Gold -= wrong.Price;
        wrong.Deck.Add(new ShopV1DeckCardBinding(new object(), wrong.CardKey));
        wrong.Stocked = false; wrong.TargetModel = null;
        Equal("unsupported", Obs(wrongSession.Read()).Status);

        var restock = new Fixture();
        using var restockSession = new ShopV1Session(Nonce, restock.Adapter);
        ShopV1Observation restockReady = Obs(restockSession.Read());
        Receipt(restockSession.Apply(restockReady.DecisionId, "buy:card:7"));
        restock.Dispatch.CompletionValue = ShopV1Completion.Succeeded;
        restock.Gold -= restock.Price;
        restock.Deck.Add(new ShopV1DeckCardBinding(restock.Card, restock.CardKey));
        Equal("unsupported", Obs(restockSession.Read()).Status);
    }

    private static void StaleAndMalformedSurfaces()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        f.Gold++;
        Equal("unsupported", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
        Equal(0, f.Dispatch.InvokeCount);

        foreach (ShopV1SurfaceCapture malformed in new[]
        {
            SurfaceWithOffers(Enumerable.Range(0, 33).Select(i => NativeOffer(i)).ToArray()),
            SurfaceWithDeck(Enumerable.Range(0, 513).Select(i =>
                new ShopV1DeckCardBinding(new object(), "C" + i)).ToArray()),
            SurfaceWithOffers(new[] { NativeOffer(1), NativeOffer(1) }),
            SurfaceWithOffers(new ShopV1NativeOffer[] { null! }),
            SurfaceWithDeck(new ShopV1DeckCardBinding[] { null! }),
        })
        {
            var adapter = new FakeAdapter { SurfaceFactory = () => malformed };
            using var bad = new ShopV1Session(Nonce, adapter);
            Equal("unsupported", Obs(bad.Read()).Status);
        }

        var nullPending = new Fixture();
        nullPending.Adapter.PendingFactory = _ => null!;
        using var pendingSession = new ShopV1Session(Nonce, nullPending.Adapter);
        ShopV1Observation pendingReady = Obs(pendingSession.Read());
        Receipt(pendingSession.Apply(pendingReady.DecisionId, "buy:card:7"));
        Equal("unsupported", Obs(pendingSession.Read()).Status);

        var blocked = new Fixture { ForegroundBlocked = true };
        using var blockedSession = new ShopV1Session(Nonce, blocked.Adapter);
        Equal("unsupported", Obs(blockedSession.Read()).Status);
        var traveling = new Fixture { MapTraveling = true };
        using var travelingSession = new ShopV1Session(Nonce, traveling.Adapter);
        Equal("unsupported", Obs(travelingSession.Read()).Status);
    }

    private static void LimitsAndActionGrammar()
    {
        var f = new Fixture();
        f.CardKey = new string('A', 128);
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Equal(2, ready.LegalActions.Count);
        Equal("rejected", Failure(session.Apply(ready.DecisionId, "buy:card:07")).Outcome);
        Equal("rejected", Failure(session.Apply(ready.DecisionId, "buy:card:32")).Outcome);
        Equal("rejected", Failure(session.Apply(ready.DecisionId, "BUY:card:7")).Outcome);
        Equal(1, f.Adapter.SurfaceCalls);

        var badKey = new Fixture { CardKey = new string('A', 129) };
        using var bad = new ShopV1Session(Nonce, badKey.Adapter);
        Equal("unsupported", Obs(bad.Read()).Status);

        var mixed = new Fixture();
        mixed.ExtraOffers.Add(NativeOffer(1, ShopV1OfferKind.Relic, enabled: true));
        mixed.ExtraOffers.Add(NativeOffer(3, ShopV1OfferKind.Potion, enabled: true));
        mixed.CardSlot = 31;
        using var mixedSession = new ShopV1Session(Nonce, mixed.Adapter);
        ShopV1Observation mixedReady = Obs(mixedSession.Read());
        Equal(3, mixedReady.Offers.Count);
        Sequence(new[] { "buy:card:31", "inventory:close" }, mixedReady.LegalActions);
    }

    private static void PendingLimitFinalRead()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
        for (int i = 1; i < ShopV1Constants.MaximumPendingReads; i++)
            Equal("waiting", Obs(session.Read()).Status);
        f.CompletePurchase();
        Equal("ready", Obs(session.Read()).Status);

        var timeout = new Fixture();
        using var timed = new ShopV1Session(Nonce, timeout.Adapter);
        ShopV1Observation timedReady = Obs(timed.Read());
        Receipt(timed.Apply(timedReady.DecisionId, "buy:card:7"));
        for (int i = 1; i < ShopV1Constants.MaximumPendingReads; i++) Obs(timed.Read());
        Equal("unsupported", Obs(timed.Read()).Status);
        Equal(1, timeout.Dispatch.InvokeCount);
    }

    private static void DispatchFailureAndNoRetry()
    {
        var f = new Fixture();
        f.Dispatch.InvokeAction = () => throw new InvalidOperationException("CANARY");
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Equal("uncertain", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
        Equal(1, f.Dispatch.InvokeCount); Equal(1, f.Dispatch.DisposeCount);
        Equal("unsupported", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
        Equal(1, f.Dispatch.InvokeCount);
    }

    private static void ReentrantCaptureGuards()
    {
        var f = new Fixture();
        ShopV1Session? session = null;
        int callback = 0;
        f.Adapter.SurfaceFactory = () =>
        {
            if (callback++ == 0) Obs(session!.Read());
            return f.Surface();
        };
        using (session = new ShopV1Session(Nonce, f.Adapter))
        {
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(1, f.Adapter.SurfaceCalls);
        }

        var apply = new Fixture();
        ShopV1Session? applySession = null;
        using (applySession = new ShopV1Session(Nonce, apply.Adapter))
        {
            ShopV1Observation ready = Obs(applySession.Read());
            apply.Adapter.SurfaceFactory = () =>
            {
                Equal("rejected", Failure(applySession.Apply(ready.DecisionId, "buy:card:7")).Outcome);
                return apply.Surface();
            };
            Equal("unsupported", Failure(applySession.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            Equal(0, apply.Dispatch.InvokeCount);
        }

        var disposed = new Fixture();
        ShopV1Session? disposedSession = null;
        using (disposedSession = new ShopV1Session(Nonce, disposed.Adapter))
        {
            ShopV1Observation ready = Obs(disposedSession.Read());
            disposed.Adapter.SurfaceFactory = () =>
            {
                disposedSession.Dispose();
                return disposed.Surface();
            };
            Equal("unsupported", Failure(disposedSession.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            Equal(0, disposed.Dispatch.InvokeCount);
        }
    }

    private static void ReentrantDispatchGuards()
    {
        var f = new Fixture();
        ShopV1Session? session = null;
        using (session = new ShopV1Session(Nonce, f.Adapter))
        {
            ShopV1Observation ready = Obs(session.Read());
            f.Dispatch.InvokeAction = () =>
            {
                Equal("waiting", Obs(session.Read()).Status);
                Equal("rejected", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            };
            Equal("uncertain", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            Equal(1, f.Dispatch.InvokeCount);
        }

        var disposed = new Fixture();
        ShopV1Session? disposedSession = null;
        using (disposedSession = new ShopV1Session(Nonce, disposed.Adapter))
        {
            ShopV1Observation ready = Obs(disposedSession.Read());
            disposed.Dispatch.InvokeAction = disposedSession.Dispose;
            Equal("uncertain", Failure(disposedSession.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            Equal(1, disposed.Dispatch.InvokeCount); Equal(1, disposed.Dispatch.DisposeCount);
        }
    }

    private static void OwnerThreadGate()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        IRoomFlowReadValue? result = null;
        var thread = new Thread(() => result = session.Read());
        thread.Start(); thread.Join();
        Equal("unsupported", Obs(result!).Status);
        Equal(0, f.Adapter.SurfaceCalls);
        Equal("unsupported", Obs(session.Read()).Status);
    }

    private static void CleanupFailures()
    {
        var f = new Fixture();
        var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
        f.CompletePurchase();
        f.Dispatch.ThrowOnDispose = true;
        Equal("unsupported", Obs(session.Read()).Status);
        Throws<InvalidOperationException>(session.Dispose);

        var pending = new Fixture();
        var pendingSession = new ShopV1Session(Nonce, pending.Adapter);
        ShopV1Observation pendingReady = Obs(pendingSession.Read());
        Receipt(pendingSession.Apply(pendingReady.DecisionId, "buy:card:7"));
        pendingSession.Dispose();
        Equal(1, pending.Dispatch.DisposeCount);
        Equal("unsupported", Obs(pendingSession.Read()).Status);

        var reentrant = new Fixture();
        var reentrantSession = new ShopV1Session(Nonce, reentrant.Adapter);
        ShopV1Observation reentrantReady = Obs(reentrantSession.Read());
        Receipt(reentrantSession.Apply(reentrantReady.DecisionId, "buy:card:7"));
        reentrant.CompletePurchase();
        reentrant.Dispatch.DisposeAction = () =>
        {
            Equal("waiting", Obs(reentrantSession.Read()).Status);
            Equal("rejected", Failure(reentrantSession.Apply(
                reentrantReady.DecisionId, "buy:card:7")).Outcome);
            reentrantSession.Dispose();
        };
        Equal("unsupported", Obs(reentrantSession.Read()).Status);
        Equal(1, reentrant.Dispatch.DisposeCount);
        Throws<InvalidOperationException>(reentrantSession.Dispose);
    }

    private static void OutputShapeAndImmutability()
    {
        ExactProperties(typeof(ShopV1Player), "DeckCount", "Gold", "PotionSlots", "Relics");
        ExactProperties(typeof(ShopV1Offer), "Affordable", "DisplayedPrice", "Enabled", "Key", "Kind", "Slot", "Supported", "PotionCapacityGain");
        ExactProperties(typeof(ShopV1ReconciledAction), "ActionId", "DecisionId", "FlowKind", "Kind", "ParentOrdinal", "Result", "SessionNonce");
        ExactProperties(typeof(ShopV1Observation), "DecisionId", "FlowKind", "LegalActions", "Offers", "RemovalCandidates", "ParentOrdinal", "Phase", "Player", "PriorResults", "SessionNonce", "Status", "Version");
        ExactProperties(typeof(RoomFlowDispatchReceipt), "ActionId", "DecisionId", "FlowKind", "Outcome", "ParentOrdinal", "SessionNonce");
        ExactProperties(typeof(RoomFlowApplyFailure), "FlowKind", "Outcome", "ParentOrdinal", "SessionNonce");

        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Throws<NotSupportedException>(() => ((IList<string>)ready.LegalActions).Add("leave"));
        Throws<NotSupportedException>(() => ((IList<ShopV1Offer>)ready.Offers).Clear());
        Equal("ready", ready.Status); Equal(2, ready.LegalActions.Count);
    }

    private static void CanonicalDigest()
    {
        var f = new Fixture();
        using var a = new ShopV1Session(Nonce, f.Adapter);
        string first = Obs(a.Read()).DecisionId;
        using var b = new ShopV1Session(Nonce, f.Adapter);
        Equal(first, Obs(b.Read()).DecisionId);
        f.Gold++;
        using var c = new ShopV1Session(Nonce, f.Adapter);
        NotEqual(first, Obs(c.Read()).DecisionId);
    }

    private static void MapTravelPermissionRepair()
    {
        var full = new Fixture { MapTravelEnabled = true };
        using (var session = new ShopV1Session(Nonce, full.Adapter))
        {
            ShopV1Observation ready = Obs(session.Read());
            Equal("ready", ready.Status);
            Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
            Equal(1, full.Dispatch.InvokeCount);
            full.CompletePurchase();
            ShopV1Observation purchased = Obs(session.Read());
            Equal("ready", purchased.Status);
            Equal("purchase_card", purchased.PriorResults[0].Kind);
            Receipt(session.Apply(purchased.DecisionId, "inventory:close"));
            Equal(1, full.BackCount);
            ShopV1Observation leave = Obs(session.Read());
            Equal("room_ready_to_leave", leave.Phase);
            Equal(true, full.MapTravelEnabled);
            Receipt(session.Apply(leave.DecisionId, "leave"));
            Equal(1, full.ProceedCount);
            Equal("complete", Obs(session.Read()).Status);
        }

        foreach (bool mapOpen in new[] { true, false })
        {
            var invalid = new Fixture { MapTravelEnabled = true };
            if (mapOpen) invalid.MapOpen = true;
            else invalid.MapTraveling = true;
            using var session = new ShopV1Session(Nonce, invalid.Adapter);
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(0, invalid.Dispatch.InvokeCount);
            Equal(0, invalid.BackCount);
        }

        foreach (bool mapOpen in new[] { true, false })
        {
            var stale = new Fixture { MapTravelEnabled = true };
            using var session = new ShopV1Session(Nonce, stale.Adapter);
            ShopV1Observation ready = Obs(session.Read());
            if (mapOpen) stale.MapOpen = true;
            else stale.MapTraveling = true;
            Equal("unsupported", Failure(session.Apply(
                ready.DecisionId, "inventory:close")).Outcome);
            Equal(0, stale.BackCount);
            Equal(0, stale.Dispatch.InvokeCount);
        }

        foreach (bool mapOpen in new[] { true, false })
        {
            var changed = new Fixture { MapTravelEnabled = true };
            using var session = new ShopV1Session(Nonce, changed.Adapter);
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
            if (mapOpen) changed.MapOpen = true;
            else changed.MapTraveling = true;
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(1, changed.Dispatch.InvokeCount);
        }

        foreach (bool mapOpen in new[] { true, false })
        {
            var changed = new Fixture { MapTravelEnabled = true };
            using var session = new ShopV1Session(Nonce, changed.Adapter);
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "inventory:close"));
            if (mapOpen) changed.MapOpen = true;
            else changed.MapTraveling = true;
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(1, changed.BackCount);
        }

        var intercepted = new Fixture
        {
            MapTravelEnabled = true,
            ProceedOpensMap = false,
        };
        using (var session = new ShopV1Session(Nonce, intercepted.Adapter))
        {
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "inventory:close"));
            ShopV1Observation leave = Obs(session.Read());
            Receipt(session.Apply(leave.DecisionId, "leave"));
            Equal(1, intercepted.ProceedCount);
            Equal("unsupported", Obs(session.Read()).Status);
            int reads = intercepted.Adapter.PendingCalls;
            intercepted.MapOpen = true;
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(reads, intercepted.Adapter.PendingCalls);
            Equal("unsupported", Failure(session.Apply(leave.DecisionId, "leave")).Outcome);
            Equal(1, intercepted.ProceedCount);
        }

        var disabledWait = new Fixture
        {
            MapTravelEnabled = true,
            ProceedOpensMap = false,
        };
        using (var session = new ShopV1Session(Nonce, disabledWait.Adapter))
        {
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "inventory:close"));
            ShopV1Observation leave = Obs(session.Read());
            disabledWait.MapTravelEnabled = false;
            Receipt(session.Apply(leave.DecisionId, "leave"));
            Equal("waiting", Obs(session.Read()).Status);
        }

        foreach (bool traveling in new[] { false, true })
        {
            var invalid = new Fixture
            {
                MapTravelEnabled = true,
                ProceedOpensMap = false,
            };
            using var session = new ShopV1Session(Nonce, invalid.Adapter);
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "inventory:close"));
            ShopV1Observation leave = Obs(session.Read());
            Receipt(session.Apply(leave.DecisionId, "leave"));
            invalid.MapOpen = true;
            invalid.MapTravelEnabled = traveling;
            invalid.MapTraveling = traveling;
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(1, invalid.ProceedCount);
        }
    }

    private static ShopV1SurfaceCapture SurfaceWithOffers(IReadOnlyList<ShopV1NativeOffer> offers) =>
        new Fixture().Surface(offers: offers);

    private static ShopV1SurfaceCapture SurfaceWithDeck(IReadOnlyList<ShopV1DeckCardBinding> deck) =>
        new Fixture().Surface(deck: deck);

    private static ShopV1NativeOffer NativeOffer(
        int slot,
        ShopV1OfferKind kind = ShopV1OfferKind.Relic,
        bool enabled = false)
    {
        object? model = kind == ShopV1OfferKind.Card ? new object() : null;
        var dispatch = kind == ShopV1OfferKind.Card ? new FakeDispatch() : null;
        return new ShopV1NativeOffer(slot, kind, "KEY_" + slot, 10, true, true,
            enabled, new object(), new object(), model, new object(), new object(), dispatch);
    }

    private static ShopV1Observation Obs(IRoomFlowReadValue value) =>
        value as ShopV1Observation ?? throw new InvalidOperationException();

    private static RoomFlowDispatchReceipt Receipt(IRoomFlowApplyValue value) =>
        value as RoomFlowDispatchReceipt ?? throw new InvalidOperationException();

    private static RoomFlowApplyFailure Failure(IRoomFlowApplyValue value) =>
        value as RoomFlowApplyFailure ?? throw new InvalidOperationException();

    private static void ExactProperties(Type type, params string[] expected)
    {
        string[] actual = type.GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Select(property => property.Name).OrderBy(name => name, StringComparer.Ordinal).ToArray();
        Array.Sort(expected, StringComparer.Ordinal);
        Sequence(expected, actual);
    }

    private static void Empty<T>(IReadOnlyList<T> values) => Equal(0, values.Count);

    private static void Check(Action check)
    {
        check();
        _checks++;
    }

    private static void Equal<T>(T expected, T actual)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException();
    }

    private static void NotEqual<T>(T left, T right)
    {
        if (EqualityComparer<T>.Default.Equals(left, right))
            throw new InvalidOperationException();
    }

    private static void Sequence<T>(IReadOnlyList<T> expected, IReadOnlyList<T> actual)
    {
        Equal(expected.Count, actual.Count);
        for (int i = 0; i < expected.Count; i++) Equal(expected[i], actual[i]);
    }

    private static void Throws<T>(Action action) where T : Exception
    {
        try { action(); }
        catch (T) { return; }
        throw new InvalidOperationException();
    }

    private sealed class Fixture
    {
        internal readonly object Run = new();
        internal readonly object Room = new();
        internal readonly object InventoryNode = new();
        internal readonly object InventoryModel = new();
        internal readonly object Player = new();
        internal readonly object Map = new();
        internal readonly object Back = new();
        internal readonly object Merchant = new();
        internal readonly object Proceed = new();
        internal readonly object Slot = new();
        internal readonly object Entry = new();
        internal readonly object Hitbox = new();
        internal readonly object Label = new();
        internal readonly object Card = new();
        internal readonly FakeAdapter Adapter;
        internal readonly FakeDispatch Dispatch = new();
        internal readonly List<ShopV1DeckCardBinding> Deck = new();
        internal readonly List<ShopV1NativeOffer> ExtraOffers = new();
        internal int Gold = 100;
        internal int Price = 45;
        internal int CardSlot = 7;
        internal string CardKey = "STRIKE_RED";
        internal bool InventoryOpen = true;
        internal bool ForegroundBlocked;
        internal bool MapOpen;
        internal bool MapTravelEnabled;
        internal bool MapTraveling;
        internal bool RoomVisible = true;
        internal bool ProceedOpensMap = true;
        internal bool Stocked = true;
        internal object? TargetModel;
        internal int BackCount;
        internal int ProceedCount;

        internal Fixture()
        {
            TargetModel = Card;
            Deck.Add(new ShopV1DeckCardBinding(new object(), "BASH"));
            Adapter = new FakeAdapter
            {
                SurfaceFactory = () => Surface(),
                PendingFactory = Pending,
            };
        }

        internal ShopV1SurfaceCapture Surface(
            IReadOnlyList<ShopV1NativeOffer>? offers = null,
            IReadOnlyList<ShopV1DeckCardBinding>? deck = null)
        {
            var actualOffers = offers ?? Offers();
            return new ShopV1SurfaceCapture(
                ShopV1SurfaceStatus.Available, Run, Room, InventoryNode,
                InventoryModel, Player, Map, RoomVisible, InventoryOpen, InventoryOpen,
                ForegroundBlocked, MapOpen, MapTravelEnabled, MapTraveling,
                Gold, deck ?? Deck, actualOffers,
                new ShopV1NativeControl(Back, true, true, () =>
                {
                    BackCount++; InventoryOpen = false;
                }),
                new ShopV1NativeControl(Merchant, true, true, null),
                new ShopV1NativeControl(Proceed, true, true, () =>
                {
                    ProceedCount++;
                    if (ProceedOpensMap)
                    {
                        MapOpen = true; MapTravelEnabled = true;
                        RoomVisible = false;
                    }
                }));
        }

        internal ShopV1PendingCapture Pending(ShopV1PendingProbe probe) =>
            new(
                ShopV1SurfaceStatus.Available, Run, Room, InventoryNode,
                InventoryModel, Player, Map, RoomVisible, InventoryOpen, InventoryOpen,
                ForegroundBlocked, MapOpen, MapTravelEnabled, MapTraveling,
                Gold, Deck,
                new ShopV1NativeControl(Merchant, true, true, null),
                new ShopV1NativeControl(Proceed, true, true, () => { }),
                probe.Kind == ShopV1ActionKind.PurchaseCard,
                probe.Kind == ShopV1ActionKind.PurchaseCard ? Slot : null,
                probe.Kind == ShopV1ActionKind.PurchaseCard ? Entry : null,
                Stocked, TargetModel, Dispatch.Completion);

        internal IReadOnlyList<ShopV1NativeOffer> Offers()
        {
            if (!InventoryOpen) return Array.Empty<ShopV1NativeOffer>();
            var offers = new List<ShopV1NativeOffer>(ExtraOffers);
            if (Stocked)
            {
                offers.Add(new ShopV1NativeOffer(
                    CardSlot, ShopV1OfferKind.Card, CardKey, Price, true, true,
                    true, Slot, Entry, TargetModel, Hitbox, Label, Dispatch));
            }
            offers.Sort((left, right) => left.Slot.CompareTo(right.Slot));
            return offers;
        }

        internal void CompletePurchase()
        {
            Dispatch.CompletionValue = ShopV1Completion.Succeeded;
            Gold -= Price;
            Deck.Add(new ShopV1DeckCardBinding(Card, CardKey));
            Stocked = false;
            TargetModel = null;
        }
    }

    private sealed class FakeAdapter : IShopV1NativeAdapter
    {
        internal Func<ShopV1SurfaceCapture> SurfaceFactory = ShopV1SurfaceCapture.Missing;
        internal Func<ShopV1PendingProbe, ShopV1PendingCapture> PendingFactory =
            _ => ShopV1PendingCapture.Missing();
        internal int SurfaceCalls;
        internal int PendingCalls;

        public ShopV1SurfaceCapture CaptureSurface()
        {
            SurfaceCalls++;
            return SurfaceFactory();
        }

        public ShopV1PendingCapture CapturePending(ShopV1PendingProbe pending)
        {
            PendingCalls++;
            return PendingFactory(pending);
        }
    }

    private sealed class FakeDispatch : IShopV1NativeDispatch
    {
        internal int InvokeCount;
        internal int DisposeCount;
        internal Action? InvokeAction;
        internal Action? DisposeAction;
        internal bool ThrowOnDispose;
        internal ShopV1Completion CompletionValue = ShopV1Completion.Pending;

        public ShopV1Completion Completion => CompletionValue;

        public void Invoke()
        {
            InvokeCount++;
            InvokeAction?.Invoke();
        }

        public void Dispose()
        {
            DisposeCount++;
            DisposeAction?.Invoke();
            if (ThrowOnDispose) throw new InvalidOperationException("CANARY");
        }
    }
}
