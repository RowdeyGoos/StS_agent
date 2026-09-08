using System;
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
            !TryControls(context, out ShopV1NativeControl? back,
                out ShopV1NativeControl? merchant, out ShopV1NativeControl? proceed))
            return ShopV1SurfaceCapture.Unsupported();
        if (!TryForeground(context, out bool blocked))
            return ShopV1SurfaceCapture.Unsupported();

        var offers = new List<ShopV1NativeOffer>();
        if (context.InventoryNode.IsOpen &&
            !TryOffers(context.InventoryNode, offers))
            return ShopV1SurfaceCapture.Unsupported();

        return new ShopV1SurfaceCapture(
            ShopV1SurfaceStatus.Available,
            context.Run, context.RoomNode, context.InventoryNode,
            context.InventoryModel, context.Player, context.Map,
            context.RoomNode.IsVisibleInTree(),
            context.InventoryNode.IsVisibleInTree(), context.InventoryNode.IsOpen,
            blocked, context.Map.IsOpen, context.Map.IsTravelEnabled,
            context.Map.IsTraveling, context.Player.Gold, deck, offers,
            back, merchant, proceed);
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
        if (!TryCopyDeck(context.Player, out List<ShopV1DeckCardBinding> deck) ||
            !TryControls(context, out _, out ShopV1NativeControl? merchant,
                out ShopV1NativeControl? proceed) ||
            !TryForeground(context, out bool blocked))
            throw new InvalidOperationException("Shop poststate is unsupported.");

        bool targetPresent = false;
        object? targetSlot = null;
        object? targetEntry = null;
        bool targetStocked = false;
        object? targetModel = null;
        if (pending.Kind == ShopV1ActionKind.PurchaseCard)
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
            blocked, context.Map.IsOpen, context.Map.IsTravelEnabled,
            context.Map.IsTraveling, context.Player.Gold, deck, merchant, proceed,
            targetPresent, targetSlot, targetEntry, targetStocked, targetModel,
            pending.PurchaseDispatch?.Completion ?? ShopV1Completion.Pending);
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
        NMerchantInventory inventory,
        List<ShopV1NativeOffer> offers)
    {
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
            else if (entry is MerchantRelicEntry relicEntry)
            {
                kind = ShopV1OfferKind.Relic;
                stocked = relicEntry.IsStocked;
                if (stocked)
                {
                    RelicModel? relic = relicEntry.Model;
                    if (relic is null) return false;
                    key = relic.Id.Entry;
                }
                else key = "unstocked_relic";
            }
            else if (entry is MerchantPotionEntry potionEntry)
            {
                kind = ShopV1OfferKind.Potion;
                stocked = potionEntry.IsStocked;
                if (stocked)
                {
                    PotionModel? potion = potionEntry.Model;
                    if (potion is null) return false;
                    key = potion.Id.Entry;
                }
                else key = "unstocked_potion";
            }
            else if (entry is MerchantCardRemovalEntry removalEntry)
            {
                kind = ShopV1OfferKind.Removal;
                key = "card_removal";
                stocked = removalEntry.IsStocked;
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
                !TryPrice(label.Text, out int price))
                return false;
            offers.Add(new ShopV1NativeOffer(
                slotIndex, kind, key, price, stocked, visible, hitbox.IsEnabled,
                slot, entry, model, hitbox, label, dispatch));
            slotIndex++;
        }
        return true;
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
            if (card is null) return false;
            deck.Add(new ShopV1DeckCardBinding(card, card.Id.Entry));
        }
        return cards.Count == count;
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

internal sealed class PinnedPurchaseDispatch : IShopV1NativeDispatch
{
    private readonly MerchantCardEntry _entry;
    private readonly NMerchantCard _slot;
    private ShopV1Completion _completion = ShopV1Completion.Pending;
    private bool _subscribed;
    private bool _invoked;
    private bool _disposed;

    internal PinnedPurchaseDispatch(MerchantCardEntry entry, NMerchantCard slot)
    {
        _entry = entry;
        _slot = slot;
    }

    public ShopV1Completion Completion => _completion;

    public void Invoke()
    {
        if (_disposed || _invoked)
            throw new InvalidOperationException("Purchase dispatch cannot be repeated.");
        _invoked = true;
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
        _completion = ShopV1Completion.Succeeded;
    }
}
