using System;
using System.Text;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

internal static class ShopDiagnosticCodec
{
    internal static byte[] Encode(string shopStatus, ShopDiagnosticStage stage, ShopDiagnosticReason reason)
    {
        if (!Allowed(shopStatus, stage, reason)) throw new InvalidOperationException();
        string value = "{\"schema_version\":1,\"status\":\"passed\",\"shop_status\":\"" +
            shopStatus + "\",\"stage\":\"" + Stage(stage) + "\",\"reason\":\"" +
            Reason(reason) + "\"}";
        if (value.Length > 512) throw new InvalidOperationException();
        return Encoding.ASCII.GetBytes(value);
    }

    private static bool Allowed(
        string shopStatus,
        ShopDiagnosticStage stage,
        ShopDiagnosticReason reason)
    {
        if (shopStatus == "ready")
            return stage == ShopDiagnosticStage.Complete && reason == ShopDiagnosticReason.None;
        if (shopStatus == "waiting")
        {
            return stage == ShopDiagnosticStage.CoreSurface &&
                    reason == ShopDiagnosticReason.SurfaceMissing ||
                stage == ShopDiagnosticStage.NativeContext &&
                    reason is >= ShopDiagnosticReason.RunUnavailable and
                        <= ShopDiagnosticReason.InventoryModelMismatch;
        }
        if (shopStatus != "unsupported") return false;
        return stage switch
        {
            ShopDiagnosticStage.NativeContext =>
                reason is ShopDiagnosticReason.CurrentRoomMismatch or
                    ShopDiagnosticReason.NativeException,
            ShopDiagnosticStage.NativeDeck =>
                reason is >= ShopDiagnosticReason.DeckCountOutOfRange and
                    <= ShopDiagnosticReason.DeckCountChanged ||
                reason == ShopDiagnosticReason.NativeException,
            ShopDiagnosticStage.NativeControls =>
                reason is >= ShopDiagnosticReason.BackControlUnavailable and
                    <= ShopDiagnosticReason.ProceedControlUnavailable ||
                reason == ShopDiagnosticReason.NativeException,
            ShopDiagnosticStage.NativeForeground =>
                reason is ShopDiagnosticReason.OverlayStackUnavailable or
                    ShopDiagnosticReason.OverlayCountOutOfRange or
                    ShopDiagnosticReason.NativeException,
            ShopDiagnosticStage.NativeOffers =>
                reason is >= ShopDiagnosticReason.OfferCountOutOfRange and
                    <= ShopDiagnosticReason.CostTextInvalid ||
                reason == ShopDiagnosticReason.NativeException,
            ShopDiagnosticStage.CoreSurface =>
                reason is ShopDiagnosticReason.SurfaceUnsupported or
                    ShopDiagnosticReason.ProjectionException,
            ShopDiagnosticStage.CoreContext =>
                reason is >= ShopDiagnosticReason.ContextUnavailable and
                    <= ShopDiagnosticReason.InitialBindingInvalid ||
                reason is ShopDiagnosticReason.DeckCountOutOfRange or
                    ShopDiagnosticReason.OfferCountOutOfRange or
                    ShopDiagnosticReason.ProjectionException,
            ShopDiagnosticStage.CoreDeck =>
                reason is ShopDiagnosticReason.DeckBindingInvalid or
                    ShopDiagnosticReason.ProjectionException,
            ShopDiagnosticStage.CoreOffers =>
                reason is >= ShopDiagnosticReason.OfferSlotInvalid and
                    <= ShopDiagnosticReason.NoncardBindingInvalid ||
                reason == ShopDiagnosticReason.ProjectionException,
            ShopDiagnosticStage.CoreInventory =>
                reason is >= ShopDiagnosticReason.InventoryNotOpen and
                    <= ShopDiagnosticReason.BackControlNotReady ||
                reason == ShopDiagnosticReason.ProjectionException,
            _ => false,
        };
    }

    private static string Stage(ShopDiagnosticStage value) => value switch
    {
        ShopDiagnosticStage.NativeContext => "native_context",
        ShopDiagnosticStage.NativeDeck => "native_deck",
        ShopDiagnosticStage.NativeControls => "native_controls",
        ShopDiagnosticStage.NativeForeground => "native_foreground",
        ShopDiagnosticStage.NativeOffers => "native_offers",
        ShopDiagnosticStage.CoreSurface => "core_surface",
        ShopDiagnosticStage.CoreContext => "core_context",
        ShopDiagnosticStage.CoreDeck => "core_deck",
        ShopDiagnosticStage.CoreOffers => "core_offers",
        ShopDiagnosticStage.CoreInventory => "core_inventory",
        ShopDiagnosticStage.Complete => "complete",
        _ => throw new InvalidOperationException(),
    };

    private static string Reason(ShopDiagnosticReason value) => value switch
    {
        ShopDiagnosticReason.None => "none",
        ShopDiagnosticReason.RunUnavailable => "run_unavailable",
        ShopDiagnosticReason.RoomUnavailable => "room_unavailable",
        ShopDiagnosticReason.RoomSingletonMismatch => "room_singleton_mismatch",
        ShopDiagnosticReason.GlobalUiUnavailable => "global_ui_unavailable",
        ShopDiagnosticReason.MapUnavailable => "map_unavailable",
        ShopDiagnosticReason.MapSingletonMismatch => "map_singleton_mismatch",
        ShopDiagnosticReason.InventoryNodeUnavailable => "inventory_node_unavailable",
        ShopDiagnosticReason.RoomModelUnavailable => "room_model_unavailable",
        ShopDiagnosticReason.InventoryModelUnavailable => "inventory_model_unavailable",
        ShopDiagnosticReason.PlayerUnavailable => "player_unavailable",
        ShopDiagnosticReason.InventoryModelMismatch => "inventory_model_mismatch",
        ShopDiagnosticReason.CurrentRoomMismatch => "current_room_mismatch",
        ShopDiagnosticReason.DeckCountOutOfRange => "deck_count_out_of_range",
        ShopDiagnosticReason.DeckCardUnavailable => "deck_card_unavailable",
        ShopDiagnosticReason.DeckCountChanged => "deck_count_changed",
        ShopDiagnosticReason.BackControlUnavailable => "back_control_unavailable",
        ShopDiagnosticReason.MerchantControlUnavailable => "merchant_control_unavailable",
        ShopDiagnosticReason.ProceedControlUnavailable => "proceed_control_unavailable",
        ShopDiagnosticReason.OverlayStackUnavailable => "overlay_stack_unavailable",
        ShopDiagnosticReason.OverlayCountOutOfRange => "overlay_count_out_of_range",
        ShopDiagnosticReason.OfferCountOutOfRange => "offer_count_out_of_range",
        ShopDiagnosticReason.OfferSlotUnavailable => "offer_slot_unavailable",
        ShopDiagnosticReason.OfferHitboxUnavailable => "offer_hitbox_unavailable",
        ShopDiagnosticReason.OfferEntryUnavailable => "offer_entry_unavailable",
        ShopDiagnosticReason.CardModelUnavailable => "card_model_unavailable",
        ShopDiagnosticReason.RelicModelUnavailable => "relic_model_unavailable",
        ShopDiagnosticReason.PotionModelUnavailable => "potion_model_unavailable",
        ShopDiagnosticReason.CostLabelUnavailable => "cost_label_unavailable",
        ShopDiagnosticReason.CostTextInvalid => "cost_text_invalid",
        ShopDiagnosticReason.NativeException => "native_exception",
        ShopDiagnosticReason.SurfaceMissing => "surface_missing",
        ShopDiagnosticReason.SurfaceUnsupported => "surface_unsupported",
        ShopDiagnosticReason.ContextUnavailable => "context_unavailable",
        ShopDiagnosticReason.GoldOutOfRange => "gold_out_of_range",
        ShopDiagnosticReason.RoomNotVisible => "room_not_visible",
        ShopDiagnosticReason.ForegroundBlocked => "foreground_blocked",
        ShopDiagnosticReason.MapOpen => "map_open",
        ShopDiagnosticReason.MapTravelEnabled => "map_travel_enabled",
        ShopDiagnosticReason.MapTraveling => "map_traveling",
        ShopDiagnosticReason.InitialBindingInvalid => "initial_binding_invalid",
        ShopDiagnosticReason.DeckBindingInvalid => "deck_binding_invalid",
        ShopDiagnosticReason.OfferSlotInvalid => "offer_slot_invalid",
        ShopDiagnosticReason.OfferOrderInvalid => "offer_order_invalid",
        ShopDiagnosticReason.OfferKeyInvalid => "offer_key_invalid",
        ShopDiagnosticReason.OfferPriceInvalid => "offer_price_invalid",
        ShopDiagnosticReason.OfferNotVisible => "offer_not_visible",
        ShopDiagnosticReason.OfferIdentityInvalid => "offer_identity_invalid",
        ShopDiagnosticReason.OfferIdentityDuplicate => "offer_identity_duplicate",
        ShopDiagnosticReason.CardBindingInvalid => "card_binding_invalid",
        ShopDiagnosticReason.CardAlreadyInDeck => "card_already_in_deck",
        ShopDiagnosticReason.NoncardBindingInvalid => "noncard_binding_invalid",
        ShopDiagnosticReason.InventoryNotOpen => "inventory_not_open",
        ShopDiagnosticReason.InventoryNotVisible => "inventory_not_visible",
        ShopDiagnosticReason.BackControlNotReady => "back_control_not_ready",
        ShopDiagnosticReason.ProjectionException => "projection_exception",
        _ => throw new InvalidOperationException(),
    };
}
