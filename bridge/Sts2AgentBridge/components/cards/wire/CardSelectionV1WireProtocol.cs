using System;
using System.Text;
using System.Text.Json;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Wire;

public static class CardSelectionV1WireProtocol
{
    public const int SchemaVersion = 1;
    public const int MaximumRequestBytes = 256;
    public const int MaximumResponseBytes = 65536;
    public const string ParentRoute = "/card-selection-v1/parent";
    public const string ParentActionRoute = "/card-selection-v1/parent/action";
    public const string ChildRoute = "/card-selection-v1/child";
    public const string ChildActionRoute = "/card-selection-v1/child/action";

    internal static bool TryParseAction(
        byte[]? body,
        bool parent,
        out string decisionId,
        out string actionId)
    {
        decisionId = string.Empty;
        actionId = string.Empty;
        if (body is null || body.Length is < 1 or > MaximumRequestBytes) return false;
        try
        {
            var reader = new Utf8JsonReader(body, new JsonReaderOptions {
                AllowTrailingCommas = false, CommentHandling = JsonCommentHandling.Disallow });
            if (!reader.Read() || reader.TokenType != JsonTokenType.StartObject ||
                !reader.Read() || reader.TokenType != JsonTokenType.PropertyName ||
                !reader.ValueTextEquals("decision_id") || !reader.Read() ||
                reader.TokenType != JsonTokenType.String)
                return false;
            decisionId = reader.GetString() ?? string.Empty;
            if (!reader.Read() || reader.TokenType != JsonTokenType.PropertyName ||
                !reader.ValueTextEquals("action_id") || !reader.Read() ||
                reader.TokenType != JsonTokenType.String)
                return false;
            actionId = reader.GetString() ?? string.Empty;
            if (!reader.Read() || reader.TokenType != JsonTokenType.EndObject || reader.Read())
                return false;
            if (!IsLowerHex(decisionId, 64) ||
                !(parent ? IsParentAction(actionId) : IsChildAction(actionId)))
                return false;
            string canonical = "{\"decision_id\":\"" + decisionId +
                "\",\"action_id\":\"" + actionId + "\"}";
            return body.AsSpan().SequenceEqual(Encoding.UTF8.GetBytes(canonical));
        }
        catch (JsonException) { return false; }
        catch (DecoderFallbackException) { return false; }
    }

    internal static bool IsChildAction(string? value)
    {
        if (value is "preview" or "confirm") return true;
        if (value is null || !value.StartsWith("select:", StringComparison.Ordinal)) return false;
        ReadOnlySpan<char> digits = value.AsSpan(7);
        if (digits.Length is < 1 or > 2 || (digits.Length > 1 && digits[0] == '0')) return false;
        int slot = 0;
        foreach (char c in digits)
        {
            if (c is < '0' or > '9') return false;
            slot = slot * 10 + c - '0';
        }
        return slot < CardSelectionV1Limits.MaximumCandidates;
    }

    internal static bool IsLowerHex(string? value, int length)
    {
        if (value is null || value.Length != length) return false;
        foreach (char c in value)
            if (c is not (>= '0' and <= '9') and not (>= 'a' and <= 'f')) return false;
        return true;
    }

    private static bool IsParentAction(string value) => value is "begin" or "proceed";
}

public sealed class CardSelectionV1WireResponse
{
    private readonly byte[] _body;

    internal CardSelectionV1WireResponse(int statusCode, byte[] body)
    {
        StatusCode = statusCode;
        _body = (byte[])body.Clone();
    }

    public int StatusCode { get; }
    public byte[] Body => (byte[])_body.Clone();
}
