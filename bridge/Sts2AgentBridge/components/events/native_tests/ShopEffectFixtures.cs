using System;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Entities.Rewards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;
using Sts2AgentBridge.Successors.ItemV1;

internal static partial class Program
{
    private static void ShopForeignPickupPrefix() { }
    private sealed class ShopEffectsFixture:IDisposable
    {
        internal readonly Fixture World=new("SHOP_EFFECT");
        internal readonly RestRewardsFixture.Synchronizer Sync=new();
        internal readonly NRewardsScreen Screen=new();
        internal readonly RewardsSet Set;
        internal readonly TaskCompletionSource Offer=new();
        internal readonly PickupPurchase Purchase;
        internal readonly IShopV1ObservedDispatch Dispatch;
        internal readonly RelicModel Relic;
        internal bool Context=true;
        internal TaskCompletionSource? CardInsertion;
        internal ShopEffectsFixture(string kind,bool delayed=false,bool initialPotion=false)
        {
            World.Adapter.Dispose();foreach(var c in World.Cards)c.Owner=World.Player;
            World.Player.Gold=100;World.Player.PotionSlots.Clear();for(int i=0;i<5;i++)World.Player.PotionSlots.Add(null);World.Player.MaxPotionCount=5;
            if(initialPotion){var potion=new PotionModel{Owner=World.Player};potion.Id.Entry="KEPT";World.Player.PotionSlots[0]=potion;}
            RunManager.Instance=new(){State=(RunState)World.Player.RunState,RewardsSetSynchronizer=Sync};
            ActiveScreenContext.Instance=new(){Current=World.Room};NModalContainer.Instance=null;
            Relic=kind switch{"cauldron"=>new Cauldron(),"orrery"=>new Orrery(),"mango"=>new Mango(),"paint"=>new WarPaint(),"passive"=>new RelicModel(),"inherited_passive"=>new PassiveShopRelic(),_=>new OldCoin()};
            Relic.Id.Entry=kind.ToUpperInvariant();
            if(kind=="dragon")World.Player.Relics.Add(new DragonFruit{Owner=World.Player});
            Set=new(){Player=World.Player};Set.BindSynchronizer(Sync);Screen.BindRewards(Set,World.Player.RunState,false);
            for(int i=0;i<5;i++) {
                Reward reward;
                if(kind=="orrery") {
                    var cardReward=new CardReward{Player=World.Player,RewardsSetIndex=i};
                    var cards=Enumerable.Range(0,3).Select(j=>{var c=new CardModel{Owner=World.Player};c.Id.Entry="OFFER_"+i+"_"+j;return c;}).ToArray();
                    cardReward.Setup(cards.Select(c=>new CardCreationResult(c)).ToList());reward=cardReward;
                    var button=new NRewardButton{Reward=reward,Handler=()=>Choose(cardReward,cards)};Screen.Children.Add(button);
                } else {
                    var potion=new PotionModel();potion.Id.Entry="POTION_"+i;
                    var potionReward=new PotionReward{Player=World.Player,Potion=potion,RewardsSetIndex=i};reward=potionReward;
                    Screen.Children.Add(new NRewardButton{Reward=reward,Handler=()=>{
                        potion.Owner=World.Player;World.Player.PotionSlots[World.Player.PotionSlots.FindIndex(p=>p is null)]=potion;
                        potionReward.ClaimedPotion=potion;potionReward.SuccessfullySelected=true;if(Set.Rewards.All(r=>r.SuccessfullySelected))Close();return Task.CompletedTask;
                    }});
                }
                Set.Rewards.Add(reward);
            }
            Screen.BindProceed(new NProceedButton{IsEnabled=true,Clicked=Close});
            NRewardsScreen.Factory=(_,_,_)=>{World.Overlays.Screens.Add(Screen);ActiveScreenContext.Instance.Current=Screen;return Screen;};
            Set.OfferHandler=()=>{Sync.Current.rewardsStack.Add(new(){set=Set});NRewardsScreen.ShowScreen(Set,false,World.Player.RunState);return Offer.Task;};
            if(Relic is Cauldron cauldron)cauldron.Handler=()=>Set.Offer();if(Relic is Orrery orrery)orrery.Handler=()=>Set.Offer();
            Purchase=new(World.Player,Relic){Delay=delayed?new():null};
            Dispatch=PinnedShopEffectDispatch.Create(World.Player,Relic,World.Overlays,Purchase,()=>Context,10)!;
        }
        private async Task Choose(CardReward reward,CardModel[] cards)
        {
            var menu=new NCardRewardSelectionScreen();var row=new Control();menu.Bind("UI/CardRow",row);menu.Children.Add(row);reward.BindMenu(menu);
            for(int i=0;i<cards.Length;i++){int index=i;var card=cards[i];row.Children.Add(new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card},RewardPressed=()=>menu.Complete(index)});}
            menu.BindAlternatives(cards.Select(c=>new CardCreationResult(c)).ToArray(),new[]{new CardRewardAlternative("Skip",PostAlternateCardRewardAction.EndSelectionAndDoNotCompleteReward)});
            World.Overlays.Screens.Add(menu);ActiveScreenContext.Instance.Current=menu;
            int? selected=await menu.OptionSelected();
            if(selected<cards.Length){if(CardInsertion is {} delay)await delay.Task;World.Player.Deck.Cards.Add(cards[selected!.Value]);reward.SuccessfullySelected=true;}
            World.Overlays.Screens.Remove(menu);ActiveScreenContext.Instance.Current=Screen;
            if(Set.Rewards.All(r=>r.SuccessfullySelected))Close();
        }
        private void Close(){World.Overlays.Screens.Clear();Sync.Current.rewardsStack.Clear();ActiveScreenContext.Instance.Current=World.Room;Offer.TrySetResult();}
        public void Dispose(){try{Dispatch.Dispose();}catch(InvalidOperationException){}NRewardsScreen.Factory=null;World.Dispose();}
    }
    private static void ShopEffectCases()
    {
        ShopEffectSessionCases();
        using(var f=new ShopEffectsFixture("inherited_passive"))
        {
            var method=typeof(RelicModel).GetMethod("AfterObtained")!;
            var foreign=new HarmonyLib.Harmony("fixture.shop.foreign."+Guid.NewGuid().ToString("N"));
            foreign.Patch(method,new HarmonyLib.HarmonyMethod(typeof(Program),nameof(ShopForeignPickupPrefix)));
            try
            {
                bool rejected=false;try{f.Dispatch.Invoke();}catch(InvalidOperationException){rejected=true;}
                Check(rejected&&f.Purchase.Task is null&&f.World.Player.Gold==100&&f.Relic.Owner is null,"inherited foreign pickup hook rejects before purchase input");
                for(int i=0;i<2;i++)
                {
                    rejected=false;try{f.Dispatch.Dispose();}catch(InvalidOperationException){rejected=true;}
                    Check(rejected&&f.Purchase.Disposed,"failed inherited hook ownership remains stopped after cleanup");
                }
                Check(HarmonyLib.Harmony.GetPatchInfo(method)?.Owners.SequenceEqual(new[]{foreign.Id})==true,"shop cleanup preserves the foreign declared hook");
            }
            finally {foreign.UnpatchAll(foreign.Id);}
        }
        foreach(string kind in new[]{"passive","inherited_passive","mango","paint","coin","dragon"})foreach(bool delayed in new[]{false,true}) {
            using var f=new ShopEffectsFixture(kind,delayed);int hp=f.World.Player.Creature.MaxHp;
            f.Dispatch.Invoke();if(delayed){Check(f.Dispatch.Completion==ShopV1Completion.Pending,"shop effect waits for payment");f.Purchase.Delay!.SetResult();}
            Check(f.Dispatch.Completion==ShopV1Completion.Succeeded,"automatic native shop effect settles "+kind);
            Check(f.World.Player.Gold==(kind is "coin" or "dragon"?390:90)&&f.World.Player.Relics.Contains(f.Relic),"one native payment and relic acquisition");
            if(kind=="mango")Check(f.World.Player.Creature.MaxHp==hp+14,"native HP effect observed");
            if(kind=="dragon")Check(f.World.Player.Creature.MaxHp==hp+1,"gold-triggered HP effect observed");
            if(kind=="paint")Check(f.World.Cards.Take(2).All(c=>c.CurrentUpgradeLevel==1),"native automatic upgrades observed");
            var declared=f.Relic.GetType().GetMethod("AfterObtained")!.DeclaringType!.GetMethod("AfterObtained")!;
            Check(HarmonyLib.Harmony.GetPatchInfo(declared) is {} hooks&&hooks.Owners.Count==1&&hooks.Owners.Single().StartsWith("sts.bridge.shop.effect.",StringComparison.Ordinal),"shop owns the declared pickup method before disposal");
            f.Dispatch.Dispose();f.Dispatch.Dispose();Check(f.Purchase.Disposed,"automatic shop cleanup complete");
            Check(!(HarmonyLib.Harmony.GetPatchInfo(declared)?.Owners.Any()??false),"declared pickup hook removed after shop completion");
        }
        foreach(string kind in new[]{"cauldron","orrery"})foreach(bool dismiss in new[]{false,true}) {
            using var f=new ShopEffectsFixture(kind);int deck=f.World.Player.Deck.Cards.Count;
            f.Dispatch.Invoke();Check(f.Dispatch.Completion==ShopV1Completion.Pending&&f.Dispatch.OwnsForeground,"shop parent waits for owned reward screen");
            for(int i=0;i<(dismiss?1:5);i++) {
                var view=f.Dispatch.ReadRewards()!;Check(view.Ready&&view.Actions.Contains("dismiss"),"nested shop rewards are policy decisions: "+kind+"/"+i+"/"+System.Text.Json.JsonSerializer.Serialize(view));
                if(dismiss){f.Dispatch.ApplyReward(view.Decision,"dismiss");break;}
                f.Dispatch.ApplyReward(view.Decision,(kind=="cauldron"?"collect:":"open:")+i);
                if(kind=="orrery") {view=f.Dispatch.ReadRewards()!;Check(view.Ready&&view.ScreenKind=="card_reward","shop card menu remains nested");f.Dispatch.ApplyReward(view.Decision,"choose:1");}
            }
            Check(f.Dispatch.Completion==ShopV1Completion.Succeeded&&f.World.Player.Gold==90,"purchase waits for final reward and native return");
            Check(f.World.Player.Deck.Cards.Count==deck+(!dismiss&&kind=="orrery"?5:0)&&f.World.Player.PotionSlots.Count(p=>p is not null)==(!dismiss&&kind=="cauldron"?5:0),"exact policy-selected shop rewards retained");
            f.Dispatch.Dispose();f.Dispatch.Dispose();
        }
        foreach(bool replace in new[]{false,true}) {
            using var f=new ShopEffectsFixture("orrery",initialPotion:true);
            f.Dispatch.Invoke();var view=f.Dispatch.ReadRewards()!;f.Dispatch.ApplyReward(view.Decision,"open:0");view=f.Dispatch.ReadRewards()!;
            f.CardInsertion=new();f.Dispatch.ApplyReward(view.Decision,"choose:1");Check(!f.Dispatch.ReadRewards()!.Ready,"shop purchase waits for delayed exact card insertion");
            if(replace){var other=new PotionModel{Owner=f.World.Player};other.Id.Entry="KEPT";f.World.Player.PotionSlots[0]=other;}
            f.CardInsertion.SetResult();f.CardInsertion=null;
            bool rejected=false;try{view=f.Dispatch.ReadRewards()!;}catch(InvalidOperationException){rejected=true;}
            Check(rejected==replace,"delayed shop choice preserves exact potion inventory");
            if(!replace){f.Dispatch.ApplyReward(view.Decision,"dismiss");Check(f.Dispatch.Completion==ShopV1Completion.Succeeded,"delayed choice returns to retained purchase");}
        }
        foreach(string mode in new[]{"context","gold","pending","same_key_open","same_key_choose","offer_fault"}) {
            using var f=new ShopEffectsFixture("orrery");f.Dispatch.Invoke();
            var view=f.Dispatch.ReadRewards()!;
            if(mode.StartsWith("same_key",StringComparison.Ordinal)){
                f.Dispatch.ApplyReward(view.Decision,"open:0");
                if(mode=="same_key_choose"){view=f.Dispatch.ReadRewards()!;f.Dispatch.ApplyReward(view.Decision,"choose:0");}
                var old=f.World.Player.Deck.Cards[0];var card=new CardModel{Owner=f.World.Player};card.Id.Entry=old.Id.Entry;f.World.Player.Deck.Cards[0]=card;
            }
            if(mode=="context")f.Context=false;if(mode=="gold")f.World.Player.Gold++;if(mode=="offer_fault")f.Offer.SetException(new InvalidOperationException());
            bool rejected=false;try{if(mode=="pending")f.Dispatch.Dispose();else f.Dispatch.Advance();}catch(InvalidOperationException){rejected=true;}
            Check(rejected,"shop effect failure stops: "+mode);
            for(int i=0;i<2;i++){rejected=false;try{f.Dispatch.Dispose();}catch(InvalidOperationException){rejected=true;}Check(rejected&&f.Purchase.Disposed,"failed shop cleanup remains sticky and detaches purchase");}
        }
    }
    // Keep the real purchase, nested reward and outer shop owners together:
    // finishing a reward input must not finish the still-open purchase.
    private sealed class ShopEffectAdapter : IShopV1NativeAdapter
    {
        private readonly ShopEffectsFixture _fixture;
        private readonly NMerchantRoom _room=new();
        private readonly NMerchantInventory _inventory=new();
        private readonly object _inventoryModel=new(),_slot=new(),_entry=new(),_hitbox=new(),_label=new(),_back=new(),_merchant=new(),_proceed=new();
        private bool _stocked=true,_closed,_mapOpen;
        internal ShopEffectAdapter(ShopEffectsFixture fixture)
        {
            _fixture=fixture;
            MegaCrit.Sts2.Core.Nodes.NRun.Instance=new(){GlobalUi=new(){CapstoneContainer=new(),Overlays=fixture.World.Overlays}};
            ActiveScreenContext.Instance.Current=_inventory;
            fixture.Purchase.After=()=>{_stocked=false;ActiveScreenContext.Instance.Current=_inventory;};
        }
        private ShopV1DeckCardBinding[] Deck()=>_fixture.World.Player.Deck.Cards.Select(c=>new ShopV1DeckCardBinding(c,c.Id.Entry,c.CurrentUpgradeLevel)).ToArray();
        private ItemV1PotionSlotBinding[] Potions()=>_fixture.World.Player.PotionSlots.Select(p=>new ItemV1PotionSlotBinding(p,p?.Id.Entry)).ToArray();
        private ShopV1RelicBinding[] Relics()=>_fixture.World.Player.Relics.Select(r=>new ShopV1RelicBinding(r,r.Id.Entry)).ToArray();
        private ShopV1NativeControl Merchant()=>new(_merchant,true,_closed,()=>{_closed=false;ActiveScreenContext.Instance.Current=_inventory;});
        private ShopV1NativeControl Proceed()=>new(_proceed,true,_closed,()=>_mapOpen=true);
        public ShopV1SurfaceCapture CaptureSurface()=>new(ShopV1SurfaceStatus.Available,
            _fixture.World.Player.RunState,_room,_inventory,_inventoryModel,_fixture.World.Player,_fixture.World.Map,
            !_mapOpen,!_closed,!_closed,false,_mapOpen,_mapOpen,false,_fixture.World.Player.Gold,Deck(),
            _stocked&&!_closed?new[]{new ShopV1NativeOffer(0,ShopV1OfferKind.Relic,_fixture.Relic.Id.Entry,10,true,true,true,_slot,_entry,_fixture.Relic,_hitbox,_label,_fixture.Dispatch)}:Array.Empty<ShopV1NativeOffer>(),
            new(_back,true,!_closed,()=>{_closed=true;ActiveScreenContext.Instance.Current=_room;}),Merchant(),Proceed(),Potions(),Relics());
        public ShopV1PendingCapture CapturePending(ShopV1PendingProbe probe)
        {
            bool purchase=probe.Kind==ShopV1ActionKind.PurchaseRelic;
            var completion=purchase?_fixture.Dispatch.Completion:ShopV1Completion.Pending;
            return new(ShopV1SurfaceStatus.Available,_fixture.World.Player.RunState,_room,_inventory,_inventoryModel,_fixture.World.Player,_fixture.World.Map,
                !_mapOpen,!_closed,!_closed,false,_mapOpen,_mapOpen,false,_fixture.World.Player.Gold,Deck(),Merchant(),Proceed(),
                purchase,purchase?_slot:null,purchase?_entry:null,_stocked,purchase&&_stocked?_fixture.Relic:null,completion,Potions(),Relics());
        }
    }
    private static void ShopEffectSessionCases()
    {
        foreach(string kind in new[]{"passive","inherited_passive","coin","cauldron","orrery"})foreach(bool dismiss in new[]{false,true})
        {
            using var fixture=new ShopEffectsFixture(kind);
            var adapter=new ShopEffectAdapter(fixture);
            using var session=new ShopInteractiveSession("0123456789abcdef0123456789abcdef",adapter,true);
            System.Text.Json.Nodes.JsonObject Apply(System.Text.Json.Nodes.JsonObject before,string action)
            {
                Check(before["decision_id"] is not null,"shop action premise "+kind+"/"+action+": "+before);
                return ShopApply(session,before,action);
            }
            var view=ShopRead(session);
            Check(view["status"]!.GetValue<string>()=="ready","shop effect initial surface "+kind+": "+view);
            Check(Apply(view,"buy:relic:0")["status"]!.GetValue<string>()=="accepted","v8 native relic purchase accepted");
            int children=0;
            view=ShopRead(session);
            if(kind is "cauldron" or "orrery")
            {
                Check(view["phase"]!.GetValue<string>()=="rewards"&&view["completed"]!.AsArray().Count==0,"shop purchase remains pending behind native rewards");
                for(int i=0;i<(dismiss?1:5);i++)
                {
                    string action=dismiss?"reward:dismiss":(kind=="cauldron"?"reward:collect:":"reward:open:")+i;
                    Check(Apply(view,action)["status"]!.GetValue<string>()=="accepted","nested shop reward accepted once");children++;
                    view=ShopRead(session);
                    Check(view["status"]!.GetValue<string>()=="ready","shop reward follow-up "+kind+"/"+i+"/"+action+": "+view);
                    if(!dismiss&&kind=="orrery")
                    {
                        Check(view["completed"]!.AsArray().Count==children&&view["phase"]!.GetValue<string>()=="rewards","opening a card reward reconciles only its child");
                        Check(Apply(view,"reward:choose:1")["status"]!.GetValue<string>()=="accepted","nested shop card chosen");children++;
                        view=ShopRead(session);
                    }
                    if(!dismiss&&i<4)Check(view["completed"]!.AsArray().Count==children&&view["phase"]!.GetValue<string>()=="rewards","later rewards retain the same purchase");
                }
            }
            Check(view["status"]!.GetValue<string>()=="ready"&&view["completed"]!.AsArray().Count==children+1&&
                view["completed"]![children]!["action_id"]!.GetValue<string>()=="buy:relic:0","all child receipts precede the purchase receipt");
            Check(fixture.Purchase.Disposed&&fixture.World.Player.Gold==(kind=="coin"?390:90),"outer owner verifies price/effects and disposes purchase");
            Check(Apply(view,"inventory:close")["status"]!.GetValue<string>()=="accepted","shop closes after nested pickup");
            view=ShopRead(session);
            Check(view["status"]!.GetValue<string>()=="ready","shop closed surface "+kind+": "+view);
            Check(Apply(view,"leave")["status"]!.GetValue<string>()=="accepted","shop leaves after nested pickup");
            view=ShopRead(session);
            Check(view["status"]!.GetValue<string>()=="complete"&&view["completed"]!.AsArray().Count==children+3,"nested pickup hands off cleanly to map");
        }
    }
}
