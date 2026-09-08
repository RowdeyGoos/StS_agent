using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.ItemV1;

public static class ItemV1CanonicalEncoder
{
    public static string ComputeDecisionId(
        string sessionNonce,
        IReadOnlyList<ItemV1Offer> offers,
        IReadOnlyList<string?> potionSlots,
        IReadOnlyList<string> legalActions)
    {
        var builder = new StringBuilder(1024);
        Append(builder, ItemV1Constants.Version);
        Append(builder, sessionNonce);
        Append(builder, ItemV1Constants.SurfaceOrdinal);
        Append(builder, offers.Count);
        foreach (ItemV1Offer offer in offers)
        {
            Append(builder, offer.Index);
            Append(builder, offer.Kind);
            Append(builder, offer.Key);
            Append(builder, offer.Enabled ? 1 : 0);
        }
        Append(builder, potionSlots.Count);
        foreach (string? slot in potionSlots)
        {
            Append(builder, slot is null ? 0 : 1);
            if (slot is not null)
            {
                Append(builder, slot);
            }
        }
        Append(builder, legalActions.Count);
        foreach (string action in legalActions)
        {
            Append(builder, action);
        }
        return Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(builder.ToString())))
            .ToLowerInvariant();
    }

    public static bool IsCanonicalDecisionId(string? value)
    {
        if (value is null || value.Length != 64)
        {
            return false;
        }
        foreach (char item in value)
        {
            if (!((item >= '0' && item <= '9') || (item >= 'a' && item <= 'f')))
            {
                return false;
            }
        }
        return true;
    }

    public static bool IsCanonicalSessionNonce(string? value)
    {
        if (value is null || value.Length != 32)
        {
            return false;
        }
        foreach (char item in value)
        {
            if (!((item >= '0' && item <= '9') || (item >= 'a' && item <= 'f')))
            {
                return false;
            }
        }
        return true;
    }

    public static bool IsStableKey(string? value)
    {
        if (value is null || value.Length < 1 || value.Length > ItemV1Constants.MaximumKeyLength)
        {
            return false;
        }
        foreach (char item in value)
        {
            if (!((item >= 'A' && item <= 'Z') ||
                  (item >= 'a' && item <= 'z') ||
                  (item >= '0' && item <= '9') || item == '_'))
            {
                return false;
            }
        }
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
