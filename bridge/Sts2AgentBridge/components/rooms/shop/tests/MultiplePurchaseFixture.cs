using System;
using Sts2AgentBridge.Successors.ItemV1;
using System.Collections.Generic;
using System.Linq;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

// Shared by core and actual-listener fixtures; never executes target-game code.
internal sealed class MultiplePurchaseFixture : IShopV1NativeAdapter
{
    private readonly object _run=new(),_room=new(),_inventory=new(),_inventoryModel=new(),_player=new(),_map=new(),_back=new(),_merchant=new(),_proceed=new();
    internal sealed class Offer(MultiplePurchaseFixture owner,int index) : IShopV1RemovalDispatch, IShopV1RestockDispatch {
        internal readonly object Slot=new(),Entry=new(),Hitbox=new(),Label=new();
        internal object Card=new();
        internal readonly int Index=index;
        internal ShopV1OfferKind Kind=ShopV1OfferKind.Card;
        internal string? KeyOverride;
        internal int CapacityGain;
        public ShopV1RestockWitness? Restocked {get;internal set;}
        internal object? RemovalTarget;
        public void SelectTarget(ShopV1DeckCardBinding card){RemovalTarget=card.ModelIdentity;}
        internal string Key=>KeyOverride??(Kind==ShopV1OfferKind.Relic?"RELIC_":Kind==ShopV1OfferKind.Potion?"POTION_":"CARD_")+Index;
        internal int Price=10;
        internal bool Stocked=true;
        internal ShopV1Completion State=ShopV1Completion.Pending;
        public ShopV1Completion Completion=>State;
        public void Invoke(){owner.Purchases++;if(owner.FailAt==owner.Purchases)throw new InvalidOperationException("purchase uncertain");if(!owner.Delay)owner.Settle(this);else owner.Pending=this;}
        public void Dispose(){owner.Disposals++;if(owner.BadCleanupAt==owner.Purchases)throw new InvalidOperationException("cleanup failed");}
    }
    internal readonly Offer[] Offers;
    internal readonly List<ShopV1DeckCardBinding> Deck=new(){new(new object(),"OLD")};
    internal readonly List<ItemV1PotionSlotBinding> Potions=new();
    internal readonly List<ShopV1RelicBinding> Relics=new();
    internal int Gold=100,Purchases,Disposals,Closes,Leaves,Discards;
    internal int FailAt=-1,BadCleanupAt=-1,BadDebitAt=-1,PriceAfterFirst=-1;
    internal bool Delay=false,Closed,MapOpen,Restock,AllowDiscards;
    internal Offer? Pending;
    internal MultiplePurchaseFixture(int count=9){Offers=Enumerable.Range(0,count).Select(i=>new Offer(this,i)).ToArray();}
    internal void Settle(Offer offer){Gold-=offer.Price+(BadDebitAt==Purchases?1:0);if(offer.Kind==ShopV1OfferKind.Potion){int slot=Potions.FindIndex(p=>p.ModelIdentity is null);if(slot<0)throw new InvalidOperationException("no potion space");Potions[slot]=new(offer.Card,offer.Key);}else if(offer.Kind==ShopV1OfferKind.Relic){Relics.Add(new(offer.Card,offer.Key));for(int i=0;i<offer.CapacityGain;i++)Potions.Add(new(null,null));}else if(offer.Kind==ShopV1OfferKind.Removal){ownerRemove(offer);}else Deck.Add(new(offer.Card,offer.Key));offer.Stocked=false;if(Restock && offer.Kind!=ShopV1OfferKind.Removal){offer.Card=new();if(offer.Kind==ShopV1OfferKind.Relic)offer.KeyOverride="RELIC_GEN_"+Purchases;offer.Price++;offer.Stocked=true;offer.Restocked=new(offer.Card,offer.Key,offer.Price);}offer.State=ShopV1Completion.Succeeded;Pending=null;if(Purchases==1&&PriceAfterFirst>=0)Offers[1].Price=PriceAfterFirst;}
    private void ownerRemove(Offer offer){int index=Deck.FindIndex(c=>ReferenceEquals(c.ModelIdentity,offer.RemovalTarget));if(index<0)throw new InvalidOperationException();Deck.RemoveAt(index);}
    private sealed class Discard(MultiplePurchaseFixture owner,int slot) : IShopV1NativeDispatch {
        private bool done;
        public ShopV1Completion Completion=>done?ShopV1Completion.Succeeded:ShopV1Completion.Pending;
        public void Invoke(){owner.Discards++;owner.Potions[slot]=new(null,null);done=true;}
        public void Dispose(){owner.Disposals++;}
    }
    private ShopV1NativeControl Merchant()=>new(_merchant,true,Closed,null);
    private ShopV1NativeControl Proceed()=>new(_proceed,true,Closed,()=>{Leaves++;MapOpen=true;});
    public ShopV1SurfaceCapture CaptureSurface()=>new(ShopV1SurfaceStatus.Available,_run,_room,_inventory,_inventoryModel,_player,_map,
        !MapOpen,!Closed,!Closed,false,MapOpen,MapOpen,false,Gold,Deck,
        Closed?Array.Empty<ShopV1NativeOffer>():Offers.Where(o=>o.Stocked).Select(o=>new ShopV1NativeOffer(o.Index,o.Kind,o.Key,o.Price,true,true,true,o.Slot,o.Entry,o.Kind==ShopV1OfferKind.Removal?null:o.Card,o.Hitbox,o.Label,o,o.CapacityGain)).ToArray(),
        new ShopV1NativeControl(_back,true,!Closed,()=>{Closes++;Closed=true;}),Merchant(),Proceed(),Potions,Relics,AllowDiscards&&!Closed&&Potions.All(p=>p.ModelIdentity is not null)?Enumerable.Range(0,Potions.Count).Select(i=>new ShopV1PotionDiscardBinding(i,new Discard(this,i))).ToArray():null);
    public ShopV1PendingCapture CapturePending(ShopV1PendingProbe probe) {
        var offer=(probe.Kind is ShopV1ActionKind.PurchaseCard or ShopV1ActionKind.PurchasePotion or ShopV1ActionKind.PurchaseRelic or ShopV1ActionKind.RemoveCard)?Offers[probe.TargetSlot]:null;
        return new(ShopV1SurfaceStatus.Available,_run,_room,_inventory,_inventoryModel,_player,_map,!MapOpen,!Closed,!Closed,false,MapOpen,MapOpen,false,Gold,Deck,Merchant(),Proceed(),
            offer is not null,offer?.Slot,offer?.Entry,offer?.Stocked??false,offer?.Stocked==true&&offer.Kind!=ShopV1OfferKind.Removal?offer.Card:null,offer?.State??probe.PurchaseDispatch?.Completion??ShopV1Completion.Pending,Potions,Relics);
    }
}
