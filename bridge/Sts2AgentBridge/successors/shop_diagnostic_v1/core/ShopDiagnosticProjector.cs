using System.Collections.Generic;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

internal static class ShopDiagnosticProjector
{
    private const int MaximumOffers = 32;
    private const int MaximumDeckCards = 512;

    internal static string Project(
        ShopDiagnosticCapture capture,
        IShopDiagnosticRecorder recorder)
    {
        recorder.Enter(ShopDiagnosticStage.CoreSurface);
        if (capture.Status == ShopDiagnosticSurfaceStatus.Missing)
        {
            recorder.Reject(ShopDiagnosticReason.SurfaceMissing);
            return "waiting";
        }
        if (capture.Status != ShopDiagnosticSurfaceStatus.Available)
        {
            recorder.Reject(ShopDiagnosticReason.SurfaceUnsupported);
            return "unsupported";
        }

        recorder.Enter(ShopDiagnosticStage.CoreContext);
        if (!ValidContext(capture)) return Reject(recorder, ShopDiagnosticReason.ContextUnavailable);
        if (capture.Gold < 0) return Reject(recorder, ShopDiagnosticReason.GoldOutOfRange);
        if (capture.Deck.Count > MaximumDeckCards)
            return Reject(recorder, ShopDiagnosticReason.DeckCountOutOfRange);
        if (capture.Offers.Count > MaximumOffers)
            return Reject(recorder, ShopDiagnosticReason.OfferCountOutOfRange);
        if (!capture.RoomVisible) return Reject(recorder, ShopDiagnosticReason.RoomNotVisible);
        if (capture.ForegroundBlocked) return Reject(recorder, ShopDiagnosticReason.ForegroundBlocked);
        if (capture.MapOpen) return Reject(recorder, ShopDiagnosticReason.MapOpen);
        if (capture.MapTravelEnabled)
            return Reject(recorder, ShopDiagnosticReason.MapTravelEnabled);
        if (capture.MapTraveling) return Reject(recorder, ShopDiagnosticReason.MapTraveling);
        if (!capture.InventoryOpen)
            return Reject(recorder, ShopDiagnosticReason.InitialBindingInvalid);

        recorder.Enter(ShopDiagnosticStage.CoreDeck);
        if (!ValidDeck(capture.Deck))
            return Reject(recorder, ShopDiagnosticReason.DeckBindingInvalid);

        recorder.Enter(ShopDiagnosticStage.CoreOffers);
        var slots = new HashSet<int>();
        var slotRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var entryRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var controlRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var labelRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var modelRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        ShopDiagnosticOffer? previous = null;
        foreach (ShopDiagnosticOffer offer in capture.Offers)
        {
            if (offer.Slot is < 0 or >= MaximumOffers)
                return Reject(recorder, ShopDiagnosticReason.OfferSlotInvalid);
            if (previous is not null && offer.Slot <= previous.Slot)
                return Reject(recorder, ShopDiagnosticReason.OfferOrderInvalid);
            if (!slots.Add(offer.Slot))
                return Reject(recorder, ShopDiagnosticReason.OfferSlotInvalid);
            if (!IsStableKey(offer.StableKey))
                return Reject(recorder, ShopDiagnosticReason.OfferKeyInvalid);
            if (offer.DisplayedPrice < 0)
                return Reject(recorder, ShopDiagnosticReason.OfferPriceInvalid);
            if (!offer.Visible)
                return Reject(recorder, ShopDiagnosticReason.OfferNotVisible);
            if (offer.SlotIdentity is null || offer.EntryIdentity is null ||
                offer.ControlIdentity is null || offer.LabelIdentity is null)
                return Reject(recorder, ShopDiagnosticReason.OfferIdentityInvalid);
            if (!slotRefs.Add(offer.SlotIdentity) || !entryRefs.Add(offer.EntryIdentity) ||
                !controlRefs.Add(offer.ControlIdentity) || !labelRefs.Add(offer.LabelIdentity))
                return Reject(recorder, ShopDiagnosticReason.OfferIdentityDuplicate);

            if (offer.Kind == ShopDiagnosticOfferKind.Card)
            {
                if (offer.OfferedModelIdentity is null ||
                    !offer.PurchaseActionReady || !modelRefs.Add(offer.OfferedModelIdentity))
                    return Reject(recorder, ShopDiagnosticReason.CardBindingInvalid);
                if (ContainsIdentity(capture.Deck, offer.OfferedModelIdentity))
                    return Reject(recorder, ShopDiagnosticReason.CardAlreadyInDeck);
            }
            else if (offer.OfferedModelIdentity is not null || offer.PurchaseActionReady)
            {
                return Reject(recorder, ShopDiagnosticReason.NoncardBindingInvalid);
            }
            ValidateKind(offer.Kind);
            previous = offer;
        }

        recorder.Enter(ShopDiagnosticStage.CoreInventory);
        if (!capture.InventoryOpen)
            return Reject(recorder, ShopDiagnosticReason.InventoryNotOpen);
        if (!capture.InventoryVisible)
            return Reject(recorder, ShopDiagnosticReason.InventoryNotVisible);
        if (!ValidControl(capture.BackControl, requireAction: true))
            return Reject(recorder, ShopDiagnosticReason.BackControlNotReady);

        recorder.Enter(ShopDiagnosticStage.Complete);
        return "ready";
    }

    private static string Reject(IShopDiagnosticRecorder recorder, ShopDiagnosticReason reason)
    {
        recorder.Reject(reason);
        return "unsupported";
    }

    private static bool ValidContext(ShopDiagnosticCapture capture) =>
        capture.RunIdentity is not null && capture.RoomIdentity is not null &&
        capture.InventoryNodeIdentity is not null && capture.InventoryModelIdentity is not null &&
        capture.PlayerIdentity is not null && capture.MapIdentity is not null;

    private static bool ValidDeck(IReadOnlyList<ShopDiagnosticDeckCard> deck)
    {
        foreach (ShopDiagnosticDeckCard card in deck)
        {
            if (card is null || card.ModelIdentity is null || !IsStableKey(card.StableKey))
                return false;
        }
        return true;
    }

    private static bool ContainsIdentity(
        IReadOnlyList<ShopDiagnosticDeckCard> deck,
        object identity)
    {
        foreach (ShopDiagnosticDeckCard card in deck)
            if (ReferenceEquals(card.ModelIdentity, identity)) return true;
        return false;
    }

    private static bool ValidControl(ShopDiagnosticControl? control, bool requireAction) =>
        control is not null && control.Identity is not null && control.Visible && control.Enabled &&
        (!requireAction || control.ActionReady);

    private static void ValidateKind(ShopDiagnosticOfferKind kind)
    {
        _ = kind switch
        {
            ShopDiagnosticOfferKind.Card => true,
            ShopDiagnosticOfferKind.Relic => true,
            ShopDiagnosticOfferKind.Potion => true,
            ShopDiagnosticOfferKind.Removal => true,
            ShopDiagnosticOfferKind.Unknown => true,
            _ => throw new System.InvalidOperationException(),
        };
    }

    private static bool IsStableKey(string? value)
    {
        if (value is null || value.Length is < 1 or > 128) return false;
        foreach (char c in value)
        {
            bool allowed = c is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or
                >= '0' and <= '9' or '_';
            if (!allowed) return false;
        }
        return true;
    }
}
