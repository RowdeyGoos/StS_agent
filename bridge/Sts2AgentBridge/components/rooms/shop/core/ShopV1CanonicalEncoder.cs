using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

public static class ShopV1CanonicalEncoder
{
    public static string ComputeDecisionId(
        string sessionNonce,
        string phase,
        ShopV1Player player,
        IReadOnlyList<ShopV1Offer> offers,
        IReadOnlyList<string> legalActions,
        ShopV1ReconciledAction? priorResult, IReadOnlyList<ShopV1RemovalCandidate>? removalCandidates = null)
    {
        var builder = new StringBuilder(4096);
        Append(builder, ShopV1Constants.Version);
        Append(builder, ShopV1Constants.FlowKind);
        Append(builder, sessionNonce);
        Append(builder, RoomFlowLimits.ParentOrdinal);
        Append(builder, phase);
        Append(builder, player.Gold);
        Append(builder, player.DeckCount);
        Append(builder, player.PotionSlots.Count);
        foreach (string? potion in player.PotionSlots) Append(builder, potion ?? string.Empty);
        Append(builder, player.Relics.Count);
        foreach (string relic in player.Relics) Append(builder, relic);
        Append(builder, offers.Count);
        foreach (ShopV1Offer offer in offers)
        {
            Append(builder, offer.Slot);
            Append(builder, offer.Kind);
            Append(builder, offer.Key);
            Append(builder, offer.DisplayedPrice);
            Append(builder, offer.Affordable ? 1 : 0);
            Append(builder, offer.Enabled ? 1 : 0);
            Append(builder, offer.Supported ? 1 : 0);
            Append(builder, offer.PotionCapacityGain);
        }
        Append(builder, removalCandidates?.Count ?? 0);
        if (removalCandidates is not null) foreach(var card in removalCandidates) { Append(builder,card.DeckSlot); Append(builder,card.Key); Append(builder,card.UpgradeLevel); }
        Append(builder, legalActions.Count);
        foreach (string action in legalActions) Append(builder, action);
        Append(builder, priorResult is null ? 0 : 1);
        if (priorResult is not null)
        {
            Append(builder, priorResult.DecisionId);
            Append(builder, priorResult.ActionId);
            Append(builder, priorResult.Kind);
            Append(builder, priorResult.Result);
        }
        return Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(builder.ToString())))
            .ToLowerInvariant();
    }

    public static string PurchaseActionId(int slot, ShopV1OfferKind kind = ShopV1OfferKind.Card) =>
        (kind == ShopV1OfferKind.Potion ? "buy:potion:" : kind == ShopV1OfferKind.Relic ? "buy:relic:" : "buy:card:") + slot.ToString(CultureInfo.InvariantCulture);

    public static bool TryParsePurchaseAction(string? actionId, out int slot)
    {
        slot = -1;
        string prefix = actionId?.StartsWith("buy:relic:", StringComparison.Ordinal) == true ? "buy:relic:" : actionId?.StartsWith("buy:potion:", StringComparison.Ordinal) == true ? "buy:potion:" : "buy:card:";
        if (actionId is null || !actionId.StartsWith(prefix, StringComparison.Ordinal))
        {
            return false;
        }
        ReadOnlySpan<char> suffix = actionId.AsSpan(prefix.Length);
        if (suffix.Length == 0 || suffix.Length > 2 || suffix[0] == '0' && suffix.Length > 1)
        {
            return false;
        }
        int value = 0;
        foreach (char c in suffix)
        {
            if (c is < '0' or > '9') return false;
            value = checked(value * 10 + c - '0');
        }
        if (value < 0 || value >= ShopV1Constants.MaximumOffers) return false;
        slot = value;
        return true;
    }

    private static void Append(StringBuilder builder, int value)
    {
        builder.Append(value.ToString(CultureInfo.InvariantCulture));
        builder.Append(';');
    }

    private static void Append(StringBuilder builder, string value)
    {
        builder.Append(value.Length.ToString(CultureInfo.InvariantCulture));
        builder.Append(':');
        builder.Append(value);
        builder.Append(';');
    }
}
