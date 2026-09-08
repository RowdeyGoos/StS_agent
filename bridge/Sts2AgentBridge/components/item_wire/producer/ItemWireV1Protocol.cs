using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.ItemWireV1;

public static class ItemWireV1Protocol
{
    public const int SchemaVersion = 1;
    public const string Protocol = "item_probe_v1";
    public const string DecisionRoute = "/probe/item-v1/public/item-decision";
    public const string ActionRoute = "/probe/item-v1/public/item-action";
    public const int MaximumBodyBytes = 4096;

    public static bool IsCanonicalActionId(string? value, out int index)
    {
        index = -1;
        const string prefix = "collect:";
        if (value is null || !value.StartsWith(prefix, StringComparison.Ordinal) ||
            value.Length == prefix.Length)
        {
            return false;
        }
        ReadOnlySpan<char> digits = value.AsSpan(prefix.Length);
        if (digits.Length > 1 && digits[0] == '0')
        {
            return false;
        }
        int parsed = 0;
        foreach (char digit in digits)
        {
            if (digit < '0' || digit > '9')
            {
                return false;
            }
            parsed = checked(parsed * 10 + digit - '0');
            if (parsed > ItemV1Constants.MaximumRewardIndex)
            {
                return false;
            }
        }
        index = parsed;
        return true;
    }
}

internal sealed class ItemWireV1OfferDto
{
    public ItemWireV1OfferDto(int index, string kind, string key, bool enabled)
    {
        Index = index;
        Kind = kind;
        Key = key;
        Enabled = enabled;
    }

    public int Index { get; }
    public string Kind { get; }
    public string Key { get; }
    public bool Enabled { get; }
}

internal sealed class ItemWireV1Envelope
{
    private readonly ReadOnlyCollection<ItemWireV1OfferDto> _offers;
    private readonly ReadOnlyCollection<string?> _potionSlots;
    private readonly ReadOnlyCollection<string> _legalActions;

    public ItemWireV1Envelope(
        string sessionNonce,
        string status,
        string decisionId = "",
        string actionId = "",
        int offerIndex = -1,
        string kind = "",
        string key = "",
        string result = "",
        string code = "",
        IReadOnlyList<ItemWireV1OfferDto>? offers = null,
        IReadOnlyList<string?>? potionSlots = null,
        IReadOnlyList<string>? legalActions = null)
    {
        SessionNonce = sessionNonce;
        Status = status;
        DecisionId = decisionId;
        ActionId = actionId;
        OfferIndex = offerIndex;
        Kind = kind;
        Key = key;
        Result = result;
        Code = code;
        _offers = Copy(offers ?? Array.Empty<ItemWireV1OfferDto>());
        _potionSlots = Copy(potionSlots ?? Array.Empty<string?>());
        _legalActions = Copy(legalActions ?? Array.Empty<string>());
    }

    public string SessionNonce { get; }
    public string Status { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public int OfferIndex { get; }
    public string Kind { get; }
    public string Key { get; }
    public string Result { get; }
    public string Code { get; }
    public IReadOnlyList<ItemWireV1OfferDto> Offers => _offers;
    public IReadOnlyList<string?> PotionSlots => _potionSlots;
    public IReadOnlyList<string> LegalActions => _legalActions;

    private static ReadOnlyCollection<T> Copy<T>(IReadOnlyList<T> source)
    {
        var copy = new T[source.Count];
        for (int index = 0; index < source.Count; index++)
        {
            copy[index] = source[index];
        }
        return Array.AsReadOnly(copy);
    }
}

internal sealed class ItemWireV1AcceptedContext
{
    public ItemWireV1AcceptedContext(
        string decisionId,
        string actionId,
        int offerIndex,
        string kind,
        string key)
    {
        DecisionId = decisionId;
        ActionId = actionId;
        OfferIndex = offerIndex;
        Kind = kind;
        Key = key;
    }

    public string DecisionId { get; }
    public string ActionId { get; }
    public int OfferIndex { get; }
    public string Kind { get; }
    public string Key { get; }
}
