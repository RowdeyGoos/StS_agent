using System.Collections.Generic;
using Godot;
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

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

/// <summary>
/// Reads the pinned passive merchant surface. Calls must execute on the Godot
/// owner frame thread. This type has no action dispatch or subscription path.
/// </summary>
public sealed class ShopDiagnosticNativeAdapter : IShopDiagnosticAdapter
{
    public ShopDiagnosticCapture CaptureSurface(IShopDiagnosticRecorder recorder)
    {
        recorder.Enter(ShopDiagnosticStage.NativeContext);
        if (!TryContext(recorder, out ShopContext? context))
            return ShopDiagnosticCapture.Missing();
        if (!ReferenceEquals(context!.Player.RunState.CurrentRoom, context.RoomModel))
            return Reject(recorder, ShopDiagnosticReason.CurrentRoomMismatch);

        recorder.Enter(ShopDiagnosticStage.NativeDeck);
        if (!TryCopyDeck(context.Player, recorder, out List<ShopDiagnosticDeckCard> deck))
            return ShopDiagnosticCapture.Unsupported();

        recorder.Enter(ShopDiagnosticStage.NativeControls);
        if (!TryControls(context, recorder, out ShopDiagnosticControl? back,
                out ShopDiagnosticControl? merchant, out ShopDiagnosticControl? proceed))
            return ShopDiagnosticCapture.Unsupported();

        recorder.Enter(ShopDiagnosticStage.NativeForeground);
        if (!TryForeground(context, recorder, out bool blocked))
            return ShopDiagnosticCapture.Unsupported();

        recorder.Enter(ShopDiagnosticStage.NativeOffers);
        var offers = new List<ShopDiagnosticOffer>();
        if (context.InventoryNode.IsOpen && !TryOffers(context.InventoryNode, recorder, offers))
            return ShopDiagnosticCapture.Unsupported();

        return new ShopDiagnosticCapture(
            ShopDiagnosticSurfaceStatus.Available,
            context.Run, context.RoomNode, context.InventoryNode,
            context.InventoryModel, context.Player, context.Map,
            context.RoomNode.IsVisibleInTree(),
            context.InventoryNode.IsVisibleInTree(), context.InventoryNode.IsOpen,
            blocked, context.Map.IsOpen, context.Map.IsTravelEnabled,
            context.Map.IsTraveling, context.Player.Gold, deck, offers,
            back, merchant, proceed);
    }

    private static bool TryContext(
        IShopDiagnosticRecorder recorder,
        out ShopContext? context)
    {
        context = null;
        NRun? run = NRun.Instance;
        NMerchantRoom? room = NMerchantRoom.Instance;
        if (run is null)
            return Fail(recorder, ShopDiagnosticReason.RunUnavailable);
        if (room is null)
            return Fail(recorder, ShopDiagnosticReason.RoomUnavailable);
        if (!GodotObject.IsInstanceValid(run))
            return Fail(recorder, ShopDiagnosticReason.RunUnavailable);
        if (!GodotObject.IsInstanceValid(room))
            return Fail(recorder, ShopDiagnosticReason.RoomUnavailable);
        if (!ReferenceEquals(NMerchantRoom.Instance, room))
            return Fail(recorder, ShopDiagnosticReason.RoomSingletonMismatch);

        var globalUi = run.GlobalUi;
        NMapScreen? map = globalUi?.MapScreen;
        NMerchantInventory? inventoryNode = room.Inventory;
        var roomModel = room.Room;
        MerchantInventory? inventoryModel = inventoryNode?.Inventory;
        Player? player = inventoryModel?.Player;
        if (globalUi is null || !GodotObject.IsInstanceValid(globalUi))
            return Fail(recorder, ShopDiagnosticReason.GlobalUiUnavailable);
        if (map is null || !GodotObject.IsInstanceValid(map))
            return Fail(recorder, ShopDiagnosticReason.MapUnavailable);
        if (!ReferenceEquals(NMapScreen.Instance, map))
            return Fail(recorder, ShopDiagnosticReason.MapSingletonMismatch);
        if (inventoryNode is null || !GodotObject.IsInstanceValid(inventoryNode))
            return Fail(recorder, ShopDiagnosticReason.InventoryNodeUnavailable);
        if (roomModel is null)
            return Fail(recorder, ShopDiagnosticReason.RoomModelUnavailable);
        if (inventoryModel is null)
            return Fail(recorder, ShopDiagnosticReason.InventoryModelUnavailable);
        if (player is null)
            return Fail(recorder, ShopDiagnosticReason.PlayerUnavailable);
        if (!ReferenceEquals(roomModel.GetLocalInventory(), inventoryModel))
            return Fail(recorder, ShopDiagnosticReason.InventoryModelMismatch);

        context = new ShopContext(
            run, room, inventoryNode, inventoryModel, player, roomModel, map, globalUi.Overlays);
        return true;
    }

    private static bool TryForeground(
        ShopContext context,
        IShopDiagnosticRecorder recorder,
        out bool blocked)
    {
        NOverlayStack? overlays = context.Overlays;
        if (overlays is null || !GodotObject.IsInstanceValid(overlays))
        {
            blocked = false;
            return Fail(recorder, ShopDiagnosticReason.OverlayStackUnavailable);
        }
        if (overlays.ScreenCount < 0)
        {
            blocked = false;
            return Fail(recorder, ShopDiagnosticReason.OverlayCountOutOfRange);
        }
        blocked = overlays.ScreenCount != 0;
        return true;
    }

    private static bool TryControls(
        ShopContext context,
        IShopDiagnosticRecorder recorder,
        out ShopDiagnosticControl? back,
        out ShopDiagnosticControl? merchant,
        out ShopDiagnosticControl? proceed)
    {
        back = null;
        merchant = null;
        proceed = null;
        NBackButton? backNode = context.InventoryNode.GetNodeOrNull<NBackButton>("%BackButton");
        NMerchantButton? merchantNode = context.RoomNode.MerchantButton;
        NProceedButton? proceedNode = context.RoomNode.ProceedButton;
        if (backNode is null)
            return Fail(recorder, ShopDiagnosticReason.BackControlUnavailable);
        if (merchantNode is null)
            return Fail(recorder, ShopDiagnosticReason.MerchantControlUnavailable);
        if (proceedNode is null)
            return Fail(recorder, ShopDiagnosticReason.ProceedControlUnavailable);
        if (!GodotObject.IsInstanceValid(backNode))
            return Fail(recorder, ShopDiagnosticReason.BackControlUnavailable);
        if (!GodotObject.IsInstanceValid(merchantNode))
            return Fail(recorder, ShopDiagnosticReason.MerchantControlUnavailable);
        if (!GodotObject.IsInstanceValid(proceedNode))
            return Fail(recorder, ShopDiagnosticReason.ProceedControlUnavailable);
        back = Control(backNode, actionReady: true);
        merchant = Control(merchantNode, actionReady: false);
        proceed = Control(proceedNode, actionReady: true);
        return true;
    }

    private static ShopDiagnosticControl Control(
        NClickableControl control,
        bool actionReady) =>
        new(control, control.IsVisibleInTree(), control.IsEnabled, actionReady);

    private static bool TryOffers(
        NMerchantInventory inventory,
        IShopDiagnosticRecorder recorder,
        List<ShopDiagnosticOffer> offers)
    {
        int slotIndex = 0;
        foreach (NMerchantSlot? slot in inventory.GetAllSlots())
        {
            if (slotIndex >= 32)
                return Fail(recorder, ShopDiagnosticReason.OfferCountOutOfRange);
            if (slot is null || !GodotObject.IsInstanceValid(slot))
                return Fail(recorder, ShopDiagnosticReason.OfferSlotUnavailable);
            NClickableControl? hitbox = slot.Hitbox;
            MerchantEntry? entry = slot.Entry;
            if (hitbox is null)
                return Fail(recorder, ShopDiagnosticReason.OfferHitboxUnavailable);
            if (entry is null)
                return Fail(recorder, ShopDiagnosticReason.OfferEntryUnavailable);
            if (!GodotObject.IsInstanceValid(hitbox))
                return Fail(recorder, ShopDiagnosticReason.OfferHitboxUnavailable);
            bool visible = slot.IsVisibleInTree() && hitbox.IsVisibleInTree();
            if (!visible)
            {
                slotIndex++;
                continue;
            }

            ShopDiagnosticOfferKind kind;
            string key;
            bool stocked;
            object? model = null;
            bool purchaseActionReady = false;
            if (slot is NMerchantCard && entry is MerchantCardEntry cardEntry)
            {
                kind = ShopDiagnosticOfferKind.Card;
                stocked = cardEntry.IsStocked;
                if (stocked)
                {
                    CardModel? card = cardEntry.CreationResult?.Card;
                    if (card is null)
                        return Fail(recorder, ShopDiagnosticReason.CardModelUnavailable);
                    key = card.Id.Entry;
                    model = card;
                    purchaseActionReady = true;
                }
                else key = "unstocked_card";
            }
            else if (entry is MerchantRelicEntry relicEntry)
            {
                kind = ShopDiagnosticOfferKind.Relic;
                stocked = relicEntry.IsStocked;
                if (stocked)
                {
                    RelicModel? relic = relicEntry.Model;
                    if (relic is null)
                        return Fail(recorder, ShopDiagnosticReason.RelicModelUnavailable);
                    key = relic.Id.Entry;
                }
                else key = "unstocked_relic";
            }
            else if (entry is MerchantPotionEntry potionEntry)
            {
                kind = ShopDiagnosticOfferKind.Potion;
                stocked = potionEntry.IsStocked;
                if (stocked)
                {
                    PotionModel? potion = potionEntry.Model;
                    if (potion is null)
                        return Fail(recorder, ShopDiagnosticReason.PotionModelUnavailable);
                    key = potion.Id.Entry;
                }
                else key = "unstocked_potion";
            }
            else if (entry is MerchantCardRemovalEntry removalEntry)
            {
                kind = ShopDiagnosticOfferKind.Removal;
                key = "card_removal";
                stocked = removalEntry.IsStocked;
            }
            else
            {
                kind = ShopDiagnosticOfferKind.Unknown;
                key = "unknown";
                stocked = false;
            }

            if (kind != ShopDiagnosticOfferKind.Unknown && !stocked)
            {
                slotIndex++;
                continue;
            }
            Node? labelNode = slot.GetNodeOrNull("%CostLabel");
            if (labelNode is not Label label || !GodotObject.IsInstanceValid(label))
                return Fail(recorder, ShopDiagnosticReason.CostLabelUnavailable);
            if (!TryPrice(label.Text, out int price))
                return Fail(recorder, ShopDiagnosticReason.CostTextInvalid);
            offers.Add(new ShopDiagnosticOffer(
                slotIndex, kind, key, price, stocked, visible, hitbox.IsEnabled,
                slot, entry, model, hitbox, label, purchaseActionReady));
            slotIndex++;
        }
        return true;
    }

    private static bool TryCopyDeck(
        Player player,
        IShopDiagnosticRecorder recorder,
        out List<ShopDiagnosticDeckCard> deck)
    {
        var cards = player.Deck.Cards;
        int count = cards.Count;
        deck = new List<ShopDiagnosticDeckCard>();
        if (count < 0 || count > 512)
            return Fail(recorder, ShopDiagnosticReason.DeckCountOutOfRange);
        deck.Capacity = count;
        for (int index = 0; index < count; index++)
        {
            CardModel? card = cards[index];
            if (card is null)
                return Fail(recorder, ShopDiagnosticReason.DeckCardUnavailable);
            deck.Add(new ShopDiagnosticDeckCard(card, card.Id.Entry));
        }
        if (cards.Count != count)
            return Fail(recorder, ShopDiagnosticReason.DeckCountChanged);
        return true;
    }

    private static bool TryPrice(string? text, out int value)
    {
        value = 0;
        if (string.IsNullOrEmpty(text) || text.Length > 10 ||
            text.Length > 1 && text[0] == '0') return false;
        foreach (char c in text)
        {
            if (c is < '0' or > '9') return false;
            int digit = c - '0';
            if (value > (int.MaxValue - digit) / 10) return false;
            value = value * 10 + digit;
        }
        return true;
    }

    private static bool Fail(IShopDiagnosticRecorder recorder, ShopDiagnosticReason reason)
    {
        recorder.Reject(reason);
        return false;
    }

    private static ShopDiagnosticCapture Reject(
        IShopDiagnosticRecorder recorder,
        ShopDiagnosticReason reason)
    {
        recorder.Reject(reason);
        return ShopDiagnosticCapture.Unsupported();
    }

    private sealed class ShopContext
    {
        internal ShopContext(
            NRun run,
            NMerchantRoom roomNode,
            NMerchantInventory inventoryNode,
            MerchantInventory inventoryModel,
            Player player,
            MegaCrit.Sts2.Core.Rooms.MerchantRoom roomModel,
            NMapScreen map,
            NOverlayStack? overlays)
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
