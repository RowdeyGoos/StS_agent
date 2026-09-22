using System;
using System.Text;

namespace Sts2AgentBridge.Successors.RoomFlowsV1;

public interface IRoomFlowReadValue { }
public interface IRoomFlowApplyValue { }

public interface IRoomFlowSession : IDisposable
{
    string FlowKind { get; }
    IRoomFlowReadValue Read();
    IRoomFlowApplyValue Apply(string? decisionId, string? actionId);
}

public static class RoomFlowLimits
{
    public const int ParentOrdinal = 1;
    public const int MaximumResponseBytes = 65536;
    public const int MaximumPendingReads = 256;
    public const int MaximumEventTextBytes = 1024;
    public const int MaximumEventCandidates = 8;
    public const int MaximumShopOffers = 32;
    public const int MaximumDeckCards = 512;
    public const int MaximumParentActions = 12;
}

public static class RoomFlowIdentity
{
    public static bool IsNonce(string? value) => IsLowerHex(value, 32);
    public static bool IsDecisionId(string? value) => IsLowerHex(value, 64);
    public static bool IsFlowKind(string? value) => value is "shop" or "event" or "rest";

    public static bool IsLowerHex(string? value, int length)
    {
        if (value is null || value.Length != length) return false;
        foreach (char c in value)
            if (!(c is >= '0' and <= '9' or >= 'a' and <= 'f')) return false;
        return true;
    }

    public static bool IsActionId(string? flowKind, string? value)
    {
        if (flowKind == "rest") {
            if (value is "lift" or "kindle" or "dig" or "clone" or "hatch") return true;
            var parts = value?.Split(':');
            return parts is { Length: 3 } && parts[0] == "cook" &&
                int.TryParse(parts[1], out int first) && int.TryParse(parts[2], out int second) &&
                first >= 0 && first < second && second < 64 &&
                first.ToString(System.Globalization.CultureInfo.InvariantCulture) == parts[1] &&
                second.ToString(System.Globalization.CultureInfo.InvariantCulture) == parts[2];
        }
        if (flowKind == "shop" && value is "inventory:close" or "leave") return true;
        string prefix;
        int maximum;
        if (flowKind == "shop") { prefix = value?.StartsWith("buy:relic:", StringComparison.Ordinal) == true ? "buy:relic:" : value?.StartsWith("buy:potion:", StringComparison.Ordinal) == true ? "buy:potion:" : "buy:card:"; maximum = 31; }
        else if (flowKind == "event") { prefix = "choose:"; maximum = 7; }
        else return false;
        if(flowKind=="shop" && value?.StartsWith("discard:",StringComparison.Ordinal)==true){prefix="discard:";maximum=7;}
        if(flowKind=="shop" && value?.StartsWith("remove:",StringComparison.Ordinal)==true){prefix="remove:";maximum=511;}
        if (value is null || !value.StartsWith(prefix, StringComparison.Ordinal)) return false;
        ReadOnlySpan<char> digits = value.AsSpan(prefix.Length);
        if (digits.Length < 1 || digits.Length > (maximum==511?3:2) || (digits.Length > 1 && digits[0] == '0')) return false;
        int index = 0;
        foreach (char c in digits)
        {
            if (c is < '0' or > '9') return false;
            index = index * 10 + c - '0';
        }
        return index <= maximum;
    }

    public static bool IsStableKey(string? value)
    {
        if (value is null || value.Length is < 1 or > 128) return false;
        foreach (char c in value)
            if (!(c is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '_')) return false;
        return true;
    }

    public static bool IsEventStableId(string? value)
    {
        if (value is null || value.Length is < 1 or > 96) return false;
        foreach (char c in value)
            if (c is < ' ' or > '~') return false;
        return true;
    }

    public static bool IsRenderedText(string? value)
    {
        if (string.IsNullOrEmpty(value)) return false;
        foreach (char c in value)
            if ((char.IsControl(c) && c != '\n') || c == '\u007f') return false;
        try { return new UTF8Encoding(false, true).GetByteCount(value) <= RoomFlowLimits.MaximumEventTextBytes; }
        catch (EncoderFallbackException) { return false; }
    }
}

public sealed class RoomFlowDispatchReceipt : IRoomFlowApplyValue
{
    public RoomFlowDispatchReceipt(string flowKind, string sessionNonce, string decisionId, string actionId)
    {
        if (!RoomFlowIdentity.IsFlowKind(flowKind) || !RoomFlowIdentity.IsNonce(sessionNonce) ||
            !RoomFlowIdentity.IsDecisionId(decisionId) || !RoomFlowIdentity.IsActionId(flowKind, actionId))
            throw new ArgumentException("Invalid receipt identity.");
        FlowKind = flowKind; SessionNonce = sessionNonce; DecisionId = decisionId; ActionId = actionId;
    }
    public string FlowKind { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal => RoomFlowLimits.ParentOrdinal;
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Outcome => "accepted";
}

public sealed class RoomFlowApplyFailure : IRoomFlowApplyValue
{
    public RoomFlowApplyFailure(string flowKind, string sessionNonce, string outcome)
    {
        if (!RoomFlowIdentity.IsFlowKind(flowKind) || !RoomFlowIdentity.IsNonce(sessionNonce) ||
            outcome is not ("rejected" or "uncertain" or "unsupported"))
            throw new ArgumentException("Invalid failure identity.");
        FlowKind = flowKind; SessionNonce = sessionNonce; Outcome = outcome;
    }
    public string FlowKind { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal => RoomFlowLimits.ParentOrdinal;
    public string Outcome { get; }
}
