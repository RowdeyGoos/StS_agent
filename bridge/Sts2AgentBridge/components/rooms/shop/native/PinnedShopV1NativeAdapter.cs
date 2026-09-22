using System;
using System.Linq;
using Sts2AgentBridge.Successors.ItemV1;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

/// <summary>
/// Captures only the pinned public merchant surface. Every call must execute
/// on the Godot owner frame thread; this adapter performs no thread marshalling.
/// </summary>
public sealed class PinnedShopV1NativeAdapter : IShopV1NativeAdapter
{
    public ShopV1SurfaceCapture CaptureSurface()
    {
        if (!TryContext(out ShopContext? context))
            return ShopV1SurfaceCapture.Missing();
        if (!ReferenceEquals(context!.Player.RunState.CurrentRoom, context.RoomModel))
            return ShopV1SurfaceCapture.Unsupported();
        if (!TryCopyDeck(context.Player, out List<ShopV1DeckCardBinding> deck) ||
            !TryCopyPotionSlots(context.Player, out var potions) ||
            !TryCopyRelics(context.Player, out var relics) ||
            !TryControls(context, out ShopV1NativeControl? back,
                out ShopV1NativeControl? merchant, out ShopV1NativeControl? proceed))
            return ShopV1SurfaceCapture.Unsupported();
        if (!TryForeground(context, out bool blocked))
            return ShopV1SurfaceCapture.Unsupported();

        var offers = new List<ShopV1NativeOffer>();
        if (context.InventoryNode.IsOpen &&
            !TryOffers(context, offers))
            return ShopV1SurfaceCapture.Unsupported();

        return new ShopV1SurfaceCapture(
            ShopV1SurfaceStatus.Available,
            context.Run, context.RoomNode, context.InventoryNode,
            context.InventoryModel, context.Player, context.Map,
            context.RoomNode.IsVisibleInTree(),
            context.InventoryNode.IsVisibleInTree(), context.InventoryNode.IsOpen,
            blocked, context.Map.IsOpen, context.Map.IsTravelEnabled,
            context.Map.IsTraveling, context.Player.Gold, deck, offers,
            back, merchant, proceed, potions, relics, Enumerable.Range(0,potions.Count)
                .Where(i=>context.InventoryNode.IsOpen && !blocked && RemovalContext(context) && Sts2AgentBridge.Items.Native.PinnedPotionDiscard.Eligible(context.Player,i))
                .Select(i=>new ShopV1PotionDiscardBinding(i,new PinnedShopPotionDiscardDispatch(context.Player,i,()=>RemovalContext(context) && TryForeground(context,out bool foreground) && !foreground &&
                    MegaCrit.Sts2.Core.Nodes.CommonUi.NModalContainer.Instance?.OpenModal is null &&
                    (MegaCrit.Sts2.Core.Nodes.Screens.Capstones.NCapstoneContainer.Instance is not {} capstone || !capstone.InUse && capstone.CurrentCapstoneScreen is null)))).ToArray());
    }

    public ShopV1PendingCapture CapturePending(ShopV1PendingProbe pending)
    {
        if (!TryContext(out ShopContext? context) ||
            !ReferenceEquals(context!.Run, pending.RunIdentity))
            throw new InvalidOperationException("Shop run is unavailable.");
        if (!ReferenceEquals(context.RoomNode, pending.RoomIdentity) ||
            !ReferenceEquals(context.InventoryNode, pending.InventoryNodeIdentity) ||
            !ReferenceEquals(context.InventoryModel, pending.InventoryModelIdentity) ||
            !ReferenceEquals(context.Player, pending.PlayerIdentity) ||
            !ReferenceEquals(context.Map, pending.MapIdentity) ||
            !ReferenceEquals(context.Player.RunState.CurrentRoom, context.RoomModel))
            throw new InvalidOperationException("Shop context changed.");
        if(pending.Kind==ShopV1ActionKind.RemoveCard) {
            if(pending.PurchaseDispatch is not PinnedShopRemovalDispatch removal)throw new InvalidOperationException("Removal binding missing.");
            removal.Advance();
        }
        if(pending.PurchaseDispatch is PinnedShopPickupDispatch pickup)pickup.Advance();
        if (!TryCopyDeck(context.Player, out List<ShopV1DeckCardBinding> deck) ||
            !TryCopyPotionSlots(context.Player, out var potions) ||
            !TryCopyRelics(context.Player, out var relics) ||
            !TryControls(context, out _, out ShopV1NativeControl? merchant,
                out ShopV1NativeControl? proceed) ||
            !TryForeground(context, out bool blocked))
            throw new InvalidOperationException("Shop poststate is unsupported.");

        bool targetPresent = false;
        object? targetSlot = null;
        object? targetEntry = null;
        bool targetStocked = false;
        object? targetModel = null;
        if (pending.Kind is ShopV1ActionKind.PurchaseCard or ShopV1ActionKind.PurchasePotion or ShopV1ActionKind.PurchaseRelic or ShopV1ActionKind.RemoveCard)
        {
            if (!TryFindPurchaseTarget(context.InventoryNode, pending,
                    out targetPresent, out targetSlot, out targetEntry,
                    out targetStocked, out targetModel))
                throw new InvalidOperationException("Shop purchase binding changed.");
        }

        return new ShopV1PendingCapture(
            ShopV1SurfaceStatus.Available,
            context.Run, context.RoomNode, context.InventoryNode,
            context.InventoryModel, context.Player, context.Map,
            context.RoomNode.IsVisibleInTree(),
            context.InventoryNode.IsVisibleInTree(), context.InventoryNode.IsOpen,
            blocked && !(pending.PurchaseDispatch is PinnedShopRemovalDispatch ownedRemoval && ownedRemoval.OwnsForeground) && !(pending.PurchaseDispatch is PinnedShopPickupDispatch ownedPickup && ownedPickup.OwnsForeground), context.Map.IsOpen, context.Map.IsTravelEnabled,
            context.Map.IsTraveling, context.Player.Gold, deck, merchant, proceed,
            targetPresent, targetSlot, targetEntry, targetStocked, targetModel,
            pending.PurchaseDispatch?.Completion ?? ShopV1Completion.Pending, potions, relics);
    }

    private static bool TryContext(out ShopContext? context)
    {
        context = null;
        NRun? run = NRun.Instance;
        NMerchantRoom? room = NMerchantRoom.Instance;
        if (run is null || room is null || !GodotObject.IsInstanceValid(run) ||
            !GodotObject.IsInstanceValid(room) || !ReferenceEquals(NMerchantRoom.Instance, room))
            return false;
        var globalUi = run.GlobalUi;
        NMapScreen? map = globalUi?.MapScreen;
        NMerchantInventory? inventoryNode = room.Inventory;
        var roomModel = room.Room;
        MerchantInventory? inventoryModel = inventoryNode?.Inventory;
        Player? player = inventoryModel?.Player;
        if (globalUi is null || !GodotObject.IsInstanceValid(globalUi) ||
            map is null || !GodotObject.IsInstanceValid(map) ||
            !ReferenceEquals(NMapScreen.Instance, map) ||
            inventoryNode is null || !GodotObject.IsInstanceValid(inventoryNode) ||
            roomModel is null || inventoryModel is null || player is null ||
            !ReferenceEquals(roomModel.GetLocalInventory(), inventoryModel))
            return false;
        context = new ShopContext(
            run, room, inventoryNode, inventoryModel, player, roomModel, map, globalUi.Overlays);
        return true;
    }

    private static bool TryForeground(ShopContext context, out bool blocked)
    {
        NOverlayStack? overlays = context.Overlays;
        if (overlays is null || !GodotObject.IsInstanceValid(overlays) ||
            overlays.ScreenCount < 0)
        {
            blocked = false;
            return false;
        }
        blocked = overlays.ScreenCount != 0;
        return true;
    }

    private static bool TryControls(
        ShopContext context,
        out ShopV1NativeControl? back,
        out ShopV1NativeControl? merchant,
        out ShopV1NativeControl? proceed)
    {
        back = null;
        merchant = null;
        proceed = null;
        NBackButton? backNode = context.InventoryNode.GetNodeOrNull<NBackButton>("%BackButton");
        NMerchantButton? merchantNode = context.RoomNode.MerchantButton;
        NProceedButton? proceedNode = context.RoomNode.ProceedButton;
        if (backNode is null || merchantNode is null || proceedNode is null ||
            !GodotObject.IsInstanceValid(backNode) ||
            !GodotObject.IsInstanceValid(merchantNode) ||
            !GodotObject.IsInstanceValid(proceedNode))
            return false;
        back = Control(backNode, backNode.ForceClick);
        merchant = Control(merchantNode, null);
        proceed = Control(proceedNode, proceedNode.ForceClick);
        return true;
    }

    private static ShopV1NativeControl Control(
        NClickableControl control,
        Action? dispatch) =>
        new(control, control.IsVisibleInTree(), control.IsEnabled, dispatch);

    private static bool TryOffers(
        ShopContext context, List<ShopV1NativeOffer> offers)
    {
        var inventory=context.InventoryNode;var player=context.Player;
        int slotIndex = 0;
        foreach (NMerchantSlot? slot in inventory.GetAllSlots())
        {
            if (slotIndex >= ShopV1Constants.MaximumOffers || slot is null ||
                !GodotObject.IsInstanceValid(slot))
                return false;
            NClickableControl? hitbox = slot.Hitbox;
            MerchantEntry? entry = slot.Entry;
            if (hitbox is null || entry is null || !GodotObject.IsInstanceValid(hitbox))
                return false;
            bool visible = slot.IsVisibleInTree() && hitbox.IsVisibleInTree();
            if (!visible)
            {
                slotIndex++;
                continue;
            }
            ShopV1OfferKind kind;
            string key;
            bool stocked;
            object? model = null;
            IShopV1NativeDispatch? dispatch = null;
            int capacityGain = 0;
            if (slot is NMerchantCard cardSlot && entry is MerchantCardEntry cardEntry)
            {
                kind = ShopV1OfferKind.Card;
                stocked = cardEntry.IsStocked;
                if (stocked)
                {
                    CardModel? card = cardEntry.CreationResult?.Card;
                    if (card is null) return false;
                    key = card.Id.Entry;
                    model = card;
                    dispatch = new PinnedPurchaseDispatch(cardEntry, cardSlot);
                }
                else key = "unstocked_card";
            }
            else if (slot is NMerchantRelic relicSlot && entry is MerchantRelicEntry relicEntry)
            {
                kind = ShopV1OfferKind.Relic;
                stocked = relicEntry.IsStocked;
                if (stocked)
                {
                    RelicModel? relic = relicEntry.Model;
                    if (relic is null || !ShopRelicRules.Ready(relicEntry, player)) return false;
                    key = relic.Id.Entry;
                    if (ShopRelicRules.TryEffect(relic, out capacityGain) || PinnedShopPickupDispatch.Supports(relic)) {
                        model = relic;
                        dispatch = new PinnedPurchaseDispatch(relicEntry, relicSlot);
                        if(PinnedShopPickupDispatch.Supports(relic)) {
                            if(!RemovalContext(context)||player.Deck.Cards.Count is <1 or >64){dispatch=null;model=null;}
                            else dispatch=new PinnedShopPickupDispatch(player,relic,context.Overlays!,dispatch,()=>RemovalContext(context));
                        }
                    }
                }
                else key = "unstocked_relic";
            }
            else if (slot is NMerchantPotion potionSlot && entry is MerchantPotionEntry potionEntry)
            {
                kind = ShopV1OfferKind.Potion;
                stocked = potionEntry.IsStocked;
                if (stocked)
                {
                    PotionModel? potion = potionEntry.Model;
                    if (potion is null || !ShopPotionOwnership.Ready(potionEntry, player)) return false;
                    key = potion.Id.Entry;
                    model = potion;
                    dispatch = new PinnedPurchaseDispatch(potionEntry, potionSlot);
                }
                else key = "unstocked_potion";
            }
            else if (slot is NMerchantCardRemoval removalSlot && entry is MerchantCardRemovalEntry removalEntry)
            {
                kind = ShopV1OfferKind.Removal;
                key = "card_removal";
                stocked = removalEntry.IsStocked;
                if(stocked && RemovalContext(context) && ShopPotionOwnership.LocalEntry(removalEntry,player) &&
                    player.Deck.Cards.Count(c=>c.IsRemovable) is >=1 and <=64)
                    dispatch=new PinnedShopRemovalDispatch(removalEntry,context.InventoryModel,player,context.Overlays!,
                        new PinnedPurchaseDispatch(removalEntry,removalSlot),()=>RemovalContext(context),()=>player.ExtraFields.CardShopRemovalsUsed);
            }
            else
            {
                kind = ShopV1OfferKind.Unknown;
                key = "unknown";
                stocked = false;
            }
            if (kind != ShopV1OfferKind.Unknown && !stocked)
            {
                dispatch?.Dispose();
                slotIndex++;
                continue;
            }
            Node? labelNode = slot.GetNodeOrNull("%CostLabel");
            if (labelNode is not Label label || !GodotObject.IsInstanceValid(label) ||
                !TryPrice(label.Text, out int price) || dispatch is not null && price != entry.Cost)
                return false;
            offers.Add(new ShopV1NativeOffer(
                slotIndex, kind, key, price, stocked, visible, hitbox.IsEnabled,
                slot, entry, model, hitbox, label, dispatch, capacityGain, model ?? (entry as MerchantRelicEntry)?.Model));
            slotIndex++;
        }
        return true;
    }

    private static bool TryCopyRelics(Player player, out List<ShopV1RelicBinding> relics)
    {
        var source = player.Relics;
        int count = source.Count;
        relics = new List<ShopV1RelicBinding>();
        if (count > ShopV1Constants.MaximumRelics) return false;
        for (int i=0;i<count;i++) {
            RelicModel? relic = source[i];
            if (relic is null || !ReferenceEquals(relic.Owner,player)) return false;
            relics.Add(new ShopV1RelicBinding(relic,relic.Id.Entry));
        }
        return source.Count == count;
    }

    private static bool TryCopyPotionSlots(Player player, out List<ItemV1PotionSlotBinding> slots)
    {
        int capacity=player.MaxPotionCount;
        var source=player.PotionSlots;
        slots=new List<ItemV1PotionSlotBinding>();
        if (capacity<0 || capacity>ItemV1Constants.MaximumPotionSlots || source.Count!=capacity) return false;
        for (int i=0;i<capacity;i++) {
            PotionModel? potion=source[i];
            if (potion is not null && !ReferenceEquals(potion.Owner,player)) return false;
            slots.Add(new ItemV1PotionSlotBinding(potion,potion?.Id.Entry));
        }
        return source.Count==capacity && player.MaxPotionCount==capacity;
    }

    private static bool TryFindPurchaseTarget(
        NMerchantInventory inventory,
        ShopV1PendingProbe pending,
        out bool present,
        out object? slotIdentity,
        out object? entryIdentity,
        out bool stocked,
        out object? modelIdentity)
    {
        present = false;
        slotIdentity = null;
        entryIdentity = null;
        stocked = false;
        modelIdentity = null;
        int slotIndex = 0;
        foreach (NMerchantSlot? slot in inventory.GetAllSlots())
        {
            if (slotIndex >= ShopV1Constants.MaximumOffers || slot is null ||
                !GodotObject.IsInstanceValid(slot))
                return false;
            if (slotIndex == pending.TargetSlot)
            {
                present = true;
                slotIdentity = slot;
                MerchantEntry? entry = slot.Entry;
                entryIdentity = entry;
                if (slot is NMerchantCard && entry is MerchantCardEntry cardEntry)
                {
                    stocked = cardEntry.IsStocked;
                    modelIdentity = cardEntry.CreationResult?.Card;
                }
                else if (slot is NMerchantRelic && entry is MerchantRelicEntry relicEntry)
                {
                    if (!ShopRelicRules.Pending(relicEntry, (Player)pending.PlayerIdentity)) return false;
                    stocked = relicEntry.IsStocked;
                    modelIdentity = relicEntry.Model;
                }
                else if(slot is NMerchantCardRemoval && entry is MerchantCardRemovalEntry removalEntry)
                {
                    if(!ShopPotionOwnership.LocalEntry(removalEntry,(Player)pending.PlayerIdentity))return false;
                    stocked=removalEntry.IsStocked;modelIdentity=null;
                }
                else if (slot is NMerchantPotion && entry is MerchantPotionEntry potionEntry)
                {
                    if (!ShopPotionOwnership.Pending(potionEntry, (Player)pending.PlayerIdentity)) return false;
                    stocked = potionEntry.IsStocked;
                    modelIdentity = potionEntry.Model;
                }
            }
            slotIndex++;
        }
        return true;
    }

    private static bool TryCopyDeck(
        Player player,
        out List<ShopV1DeckCardBinding> deck)
    {
        var cards = player.Deck.Cards;
        int count = cards.Count;
        deck = new List<ShopV1DeckCardBinding>();
        if (count < 0 || count > ShopV1Constants.MaximumDeckCards)
            return false;
        deck.Capacity = count;
        for (int index = 0; index < count; index++)
        {
            CardModel? card = cards[index];
            if (card is null || !ReferenceEquals(card.Owner,player) || !ReferenceEquals(card.RunState,player.RunState)) return false;
            deck.Add(new ShopV1DeckCardBinding(card, card.Id.Entry,card.CurrentUpgradeLevel,card.IsRemovable));
        }
        return cards.Count == count;
    }

    private static bool RemovalContext(ShopContext retained)
    {
        var manager=MegaCrit.Sts2.Core.Runs.RunManager.Instance;
        return TryContext(out var current) && current is not null && manager is not null &&
            (int)manager.NetService.Type==1 && !manager.IsAbandoned && ReferenceEquals(manager.DebugOnlyGetState(),retained.Player.RunState) &&
            MegaCrit.Sts2.Core.Context.LocalContext.IsMe(retained.Player) && retained.Player.Creature.CurrentHp>0 &&
            ReferenceEquals(current.Run,retained.Run)&&ReferenceEquals(current.RoomNode,retained.RoomNode)&&ReferenceEquals(current.Player,retained.Player)&&
            ReferenceEquals(current.InventoryNode,retained.InventoryNode)&&ReferenceEquals(current.InventoryModel,retained.InventoryModel)&&
            ReferenceEquals(current.Map,retained.Map)&&ReferenceEquals(current.Overlays,retained.Overlays)&&
            ReferenceEquals(retained.Run.MerchantRoom,retained.RoomNode)&&ReferenceEquals(retained.Player.RunState.CurrentRoom,retained.RoomModel)&&
            retained.InventoryNode.IsOpen&&!retained.Map.IsOpen&&!retained.Map.IsTraveling;
    }

    private static bool TryPrice(string? text, out int value)
    {
        value = 0;
        if (string.IsNullOrEmpty(text) || text.Length > 10 ||
            text.Length > 1 && text[0] == '0')
            return false;
        foreach (char c in text)
        {
            if (c is < '0' or > '9') return false;
            int digit = c - '0';
            if (value > (int.MaxValue - digit) / 10) return false;
            value = value * 10 + digit;
        }
        return true;
    }

    private sealed class ShopContext
    {
        internal ShopContext(
            NRun run, NMerchantRoom roomNode, NMerchantInventory inventoryNode,
            MerchantInventory inventoryModel, Player player,
            MegaCrit.Sts2.Core.Rooms.MerchantRoom roomModel,
            NMapScreen map, NOverlayStack? overlays)
        {
            Run = run;
            RoomNode = roomNode;
            InventoryNode = inventoryNode;
            InventoryModel = inventoryModel;
            Player = player;
            RoomModel = roomModel;
            Map = map;
            Overlays = overlays;
        }

        internal NRun Run { get; }
        internal NMerchantRoom RoomNode { get; }
        internal NMerchantInventory InventoryNode { get; }
        internal MerchantInventory InventoryModel { get; }
        internal Player Player { get; }
        internal MegaCrit.Sts2.Core.Rooms.MerchantRoom RoomModel { get; }
        internal NMapScreen Map { get; }
        internal NOverlayStack? Overlays { get; }
    }
}

internal sealed class PinnedPurchaseDispatch : IShopV1RestockDispatch
{
    private readonly MerchantEntry _entry;
    private readonly NMerchantSlot _slot;
    private ShopV1Completion _completion = ShopV1Completion.Pending;
    private bool _subscribed;
    private bool _invoked;
    private bool _disposed;

    internal PinnedPurchaseDispatch(MerchantEntry entry, NMerchantSlot slot)
    {
        _entry = entry;
        _slot = slot;
    }

    public ShopV1RestockWitness? Restocked {get;private set;}
    private object? _originalModel;
    private object? Model()=>_entry is MerchantCardEntry card?card.CreationResult?.Card:
        _entry is MerchantPotionEntry potion?potion.Model:_entry is MerchantRelicEntry relic?relic.Model:null;
    public ShopV1Completion Completion => _completion;

    public void Invoke()
    {
        if (_disposed || _invoked)
            throw new InvalidOperationException("Purchase dispatch cannot be repeated.");
        _invoked = true;
        _originalModel=Model();
        _entry.PurchaseCompleted += OnPurchaseCompleted;
        _subscribed = true;
        using var input = new InputEventAction
        {
            Action = MegaInput.select,
            Pressed = true,
        };
        _slot._GuiInput(input);
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        if (_subscribed)
        {
            _entry.PurchaseCompleted -= OnPurchaseCompleted;
            _subscribed = false;
        }
    }

    private void OnPurchaseCompleted(PurchaseStatus status, MerchantEntry entry)
    {
        if (_disposed) return;
        if (_completion != ShopV1Completion.Pending ||
            status != PurchaseStatus.Success || !ReferenceEquals(entry, _entry))
        {
            _completion = ShopV1Completion.Invalid;
            return;
        }
        try {
            var model=Model();
            if(model is not null && !ReferenceEquals(model,_originalModel)) {
                string? key=model is CardModel card?card.Id.Entry:model is PotionModel potion?potion.Id.Entry:(model as RelicModel)?.Id.Entry;
                if(!_entry.IsStocked || !RoomFlowIdentity.IsStableKey(key) || _entry.Cost<0)throw new InvalidOperationException("Invalid restock result.");
                Restocked=new(model,key!,_entry.Cost);
            }
            _completion = ShopV1Completion.Succeeded;
        } catch {_completion=ShopV1Completion.Invalid;}
    }
}

internal sealed class PinnedShopPotionDiscardDispatch : IShopV1NativeDispatch, IShopV1AbortableDispatch {
    private readonly MegaCrit.Sts2.Core.Entities.Players.Player _player;
    private readonly int _slot;private readonly Func<bool> _context;
    private Sts2AgentBridge.Items.Native.PinnedPotionDiscard? _discard;
    internal PinnedShopPotionDiscardDispatch(MegaCrit.Sts2.Core.Entities.Players.Player player,int slot,Func<bool> context){_player=player;_slot=slot;_context=context;}
    public void Invoke(){if(_discard is not null)throw new InvalidOperationException("Duplicate discard.");_discard=new(_player,_slot,_context);_discard.Dispatch();}
    public ShopV1Completion Completion=>_discard?.Read() switch {1=>ShopV1Completion.Succeeded,0=>ShopV1Completion.Pending,_=>ShopV1Completion.Invalid};
    public void Abort()=>_discard?.Abort();
    public void Dispose()=>_discard?.Dispose();
}
