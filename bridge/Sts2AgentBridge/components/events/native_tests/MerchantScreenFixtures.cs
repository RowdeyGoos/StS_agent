using System;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Events.Custom;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static partial class Program
{
    internal sealed class MerchantFixture:IDisposable {
        internal readonly Fixture World=new("CUSTOM_MERCHANT");
        internal readonly FakeMerchant Model;
        internal readonly NFakeMerchant Screen=new();
        internal readonly NBackButton Back=new();
        internal readonly NProceedButton Proceed=new(){IsEnabled=true};
        internal readonly Control Blocker=new();
        internal int Opens,Closes,Leaves;
        internal bool Delay;internal Action? Pending;
        internal Action<MerchantRelicEntry>? AfterPurchase;
        internal GenericEventV7Session Session=>World.Session;
        internal MerchantFixture() {
            foreach(var card in World.Player.Deck.Cards)card.Owner=World.Player;
            Model=new(){Owner=World.Player};Model.Inventory.Player=World.Player;
            ((RunState)World.Player.RunState).CurrentRoom=new EventRoom{LocalMutableEvent=Model};
            World.Room.CustomEventNode=Screen;World.Map.IsTravelEnabled=true;
            Screen.Inventory.Inventory=Model.Inventory;Screen.Inventory.Bind("%BackButton",Back);
            Screen.Initialize(Model,Proceed,Blocker);
            Screen.MerchantButton.Clicked=()=>{Opens++;Screen.Inventory.IsOpen=true;Screen.MerchantButton.IsEnabled=false;Proceed.IsEnabled=false;};
            Back.Clicked=()=>{Closes++;Screen.Inventory.IsOpen=false;Screen.MerchantButton.IsEnabled=true;Proceed.IsEnabled=true;};
            Proceed.Clicked=()=>{Leaves++;World.Map.IsOpen=true;};
            for(int i=0;i<6;i++) {
                var entry=new MerchantRelicEntry{Cost=10};entry.SetPlayer(World.Player);entry.Model.Id.Entry="FAKE_RELIC_"+i;
                var slot=new NMerchantRelic{Entry=entry};slot.Bind("%CostLabel",new Label{Text="10"});Screen.Inventory.Slots.Add(slot);
                slot.Purchase=()=>{
                    Action effect=()=>{World.Player.Gold-=entry.Cost;entry.Model.Owner=World.Player;World.Player.Relics.Add(entry.Model);entry.IsStocked=false;AfterPurchase?.Invoke(entry);entry.Complete(PurchaseStatus.Success);};
                    if(Delay)Pending=effect;else effect();
                };
            }
        }
        internal GenericEventV7Observation Act(string stablePrefix) {
            var read=Session.Read();Check(read.Status=="ready","merchant ready "+read.Status);
            var option=read.Candidates.First(c=>c.StableId.StartsWith(stablePrefix,StringComparison.Ordinal));
            Check(Session.Apply(read.DecisionId,option.ActionId).Outcome=="accepted","merchant dispatch");return Session.Read();
        }
        public void Dispose(){try{World.Dispose();}catch(InvalidOperationException){/* Unresolved mutations deliberately fail cleanup. */}}
    }
    private static void MerchantScreenCases() {
        foreach(int count in new[]{0,1,6})using(var f=new MerchantFixture()) {
            f.Act("FAKE_MERCHANT.OPEN");
            for(int i=0;i<count;i++)f.Act("FAKE_MERCHANT.BUY");
            var leave=f.Act("FAKE_MERCHANT.CLOSE");Check(leave.Phase=="proceed","custom close reconciled");
            var done=f.Act("FAKE_MERCHANT.LEAVE");Check(done.Status=="complete"&&done.ParentReconciled==count+3&&f.World.Map.IsOpen,"custom merchant map");
            Check(f.World.Player.Relics.Count==count&&f.World.Player.Gold==99-10*count&&f.Opens==1&&f.Closes==1&&f.Leaves==1,"exact custom effects");
            Check(f.Screen.Inventory.Slots.All(s=>s.Entry.Subscribers==0),"merchant cleanup subscriptions");
        }
        foreach(var mode in new[]{"entry_owner","price","label","slot","entry","model","owner","overlay","map","block","gold","deck","potion","event","fight","old_relic","duplicate_reply","wrong_gold","extra_relic","pending","dispose"})using(var f=new MerchantFixture()) {
            f.Act("FAKE_MERCHANT.OPEN");var ready=f.Session.Read();var slot=f.Screen.Inventory.Slots[0];var entry=(MerchantRelicEntry)slot.Entry;
            switch(mode) {
                case "entry_owner":entry.SetPlayer(new());break;
                case "price":entry.Cost++;break;
                case "label":slot.GetNodeOrNull<Label>("%CostLabel")!.Text="11";break;
                case "slot":f.Screen.Inventory.Slots[0]=new(){Entry=entry};break;
                case "entry":slot.Entry=new MerchantRelicEntry();break;
                case "model":entry.Model=new();entry.Model.Id.Entry="FAKE_RELIC_0";break;
                case "owner":entry.Model.Owner=new();break;
                case "overlay":f.World.Overlays.Screens.Add(new Control());break;
                case "map":f.World.Map.IsOpen=true;break;
                case "block":f.Blocker.MouseFilter=Control.MouseFilterEnum.Stop;break;
                case "gold":f.World.Player.Gold++;break;
                case "deck":f.World.Player.Deck.Cards.RemoveAt(0);break;
                case "potion":f.World.Player.PotionSlots[0]=new();break;
                case "event":((EventRoom)f.World.Player.RunState.CurrentRoom!).LocalMutableEvent=new();break;
                case "fight":f.Model.StartedFight=true;break;
                case "pending":case "dispose":f.Delay=true;break;
                case "wrong_gold":f.AfterPurchase=_=>f.World.Player.Gold++;break;
                case "extra_relic":f.AfterPurchase=_=>f.World.Player.Relics.Add(new(){Owner=f.World.Player});break;
            }
            var receipt=f.Session.Apply(ready.DecisionId,"choose:0");
            if(mode is "pending" or "dispose") {
                Check(receipt.Outcome=="accepted"&&f.Session.Read().Status=="waiting"&&slot.Inputs==1,"pending purchase waits");
                if(mode=="dispose") {bool threw=false;try{f.Session.Dispose();}catch{threw=true;}Check(threw,"pending merchant disposal fails");threw=false;try{f.Session.Dispose();}catch{threw=true;}Check(threw,"pending merchant disposal remains failed");Check(entry.Subscribers==0,"failed disposal still detaches callback");}
                else {f.Pending!();Check(f.Session.Read().Status=="ready"&&slot.Inputs==1,"delayed purchase reconciles once");}
            }else if(mode is "old_relic" or "duplicate_reply") {
                Check(receipt.Outcome=="accepted"&&f.Session.Read().Status=="ready","purchase settled");
                if(mode=="old_relic")f.World.Player.Relics[0].Owner=new();else entry.Complete(PurchaseStatus.Success);
                if(mode=="old_relic")Check(f.Session.Read().Status=="unsupported","settled relic retained");
                else Check(f.Session.Apply(ready.DecisionId,"choose:0").Outcome!="accepted"&&slot.Inputs==1,"stale purchase not replayed");
            }else if(mode is "wrong_gold" or "extra_relic")Check(receipt.Outcome=="accepted"&&f.Session.Read().Status=="unsupported","incorrect purchase stops");
            else Check(receipt.Outcome!="accepted"&&slot.Inputs==0,"stale/illegal custom input stopped "+mode);
        }
    }
}
