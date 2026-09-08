using System;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.ItemTransportV1;

internal static class ItemTransportLimits
{
    public const int Port = 43117;
    public const int Backlog = 8;
    public const int MaximumHandlers = 4;
    public const int MaximumRequestHead = 4096;
    public const int RequestBufferSize = 4097;
    public const int MaximumBody = 4096;
    public const int HeaderReadMilliseconds = 1000;
    public const int ResponseWriteMilliseconds = 1000;
    public const int ConnectionLifetimeMilliseconds = 2000;
    public const int ShutdownJoinMilliseconds = 2000;
}

internal readonly record struct ParsedItemTransportRequest(
    bool IsPost,
    int AuthorizationOffset,
    int AuthorizationLength,
    int DecisionOffset,
    int DecisionLength,
    int ActionOffset,
    int ActionLength);

internal static class ItemTransportRequestParser
{
    private static ReadOnlySpan<byte> GetLine =>
        "GET /probe/item-v1/public/item-decision HTTP/1.1"u8;
    private static ReadOnlySpan<byte> PostLine =>
        "POST /probe/item-v1/public/item-action HTTP/1.1"u8;
    private static ReadOnlySpan<byte> HostLine => "Host: 127.0.0.1:43117"u8;
    private static ReadOnlySpan<byte> AuthorizationPrefix => "Authorization: Bearer "u8;
    private static ReadOnlySpan<byte> AcceptLine => "Accept: application/json"u8;
    private static ReadOnlySpan<byte> DecisionPrefix => "X-Sts2-Decision-Id: "u8;
    private static ReadOnlySpan<byte> ActionPrefix => "X-Sts2-Action-Id: "u8;
    private static ReadOnlySpan<byte> ConnectionLine => "Connection: close"u8;

    public static bool TryParse(
        ReadOnlySpan<byte> completeHead,
        out ParsedItemTransportRequest request)
    {
        request = default;
        if (completeHead.Length is < 4 or > ItemTransportLimits.MaximumRequestHead ||
            completeHead[^4] != (byte)'\r' || completeHead[^3] != (byte)'\n' ||
            completeHead[^2] != (byte)'\r' || completeHead[^1] != (byte)'\n')
        {
            return false;
        }

        Span<LineRange> lines = stackalloc LineRange[8];
        if (!TrySplitLines(completeHead, lines, out int count) || count is not (5 or 7))
        {
            return false;
        }
        bool isPost = completeHead[lines[0].Slice].SequenceEqual(PostLine);
        if (!isPost && !completeHead[lines[0].Slice].SequenceEqual(GetLine) ||
            !completeHead[lines[1].Slice].SequenceEqual(HostLine) ||
            !completeHead[lines[3].Slice].SequenceEqual(AcceptLine))
        {
            return false;
        }
        ReadOnlySpan<byte> authorization = completeHead[lines[2].Slice];
        if (authorization.Length != AuthorizationPrefix.Length + 64 ||
            !authorization[..AuthorizationPrefix.Length].SequenceEqual(AuthorizationPrefix) ||
            !IsLowerHex(authorization[AuthorizationPrefix.Length..]))
        {
            return false;
        }

        int decisionOffset = 0;
        int decisionLength = 0;
        int actionOffset = 0;
        int actionLength = 0;
        int connectionLine = 4;
        if (isPost)
        {
            if (count != 7)
            {
                return false;
            }
            ReadOnlySpan<byte> decision = completeHead[lines[4].Slice];
            ReadOnlySpan<byte> action = completeHead[lines[5].Slice];
            if (decision.Length != DecisionPrefix.Length + 64 ||
                !decision[..DecisionPrefix.Length].SequenceEqual(DecisionPrefix) ||
                !IsLowerHex(decision[DecisionPrefix.Length..]) ||
                action.Length <= ActionPrefix.Length ||
                !action[..ActionPrefix.Length].SequenceEqual(ActionPrefix) ||
                !IsCanonicalAction(action[ActionPrefix.Length..]))
            {
                return false;
            }
            decisionOffset = lines[4].Start + DecisionPrefix.Length;
            decisionLength = 64;
            actionOffset = lines[5].Start + ActionPrefix.Length;
            actionLength = action.Length - ActionPrefix.Length;
            connectionLine = 6;
        }
        else if (count != 5)
        {
            return false;
        }
        if (!completeHead[lines[connectionLine].Slice].SequenceEqual(ConnectionLine))
        {
            return false;
        }
        request = new ParsedItemTransportRequest(
            isPost,
            lines[2].Start + AuthorizationPrefix.Length,
            64,
            decisionOffset,
            decisionLength,
            actionOffset,
            actionLength);
        return true;
    }

    private static bool TrySplitLines(
        ReadOnlySpan<byte> source,
        Span<LineRange> lines,
        out int count)
    {
        count = 0;
        int start = 0;
        for (int index = 0; index < source.Length - 1; index++)
        {
            byte value = source[index];
            if (value is < 0x20 or > 0x7e)
            {
                if (value != (byte)'\r' || source[index + 1] != (byte)'\n')
                {
                    return false;
                }
                if (index == start)
                {
                    return index + 2 == source.Length;
                }
                if (count >= lines.Length)
                {
                    return false;
                }
                lines[count++] = new LineRange(start, index - start);
                start = index + 2;
                index++;
            }
        }
        return false;
    }

    private static bool IsLowerHex(ReadOnlySpan<byte> value)
    {
        foreach (byte item in value)
        {
            if (!((item >= (byte)'0' && item <= (byte)'9') ||
                  (item >= (byte)'a' && item <= (byte)'f')))
            {
                return false;
            }
        }
        return !value.IsEmpty;
    }

    private static bool IsCanonicalAction(ReadOnlySpan<byte> value)
    {
        if (!value.StartsWith("collect:"u8) || value.Length == 8)
        {
            return false;
        }
        ReadOnlySpan<byte> digits = value[8..];
        if (digits.Length > 1 && digits[0] == (byte)'0')
        {
            return false;
        }
        int parsed = 0;
        foreach (byte digit in digits)
        {
            if (digit < (byte)'0' || digit > (byte)'9')
            {
                return false;
            }
            parsed = (parsed * 10) + digit - (byte)'0';
            if (parsed > 255)
            {
                return false;
            }
        }
        return true;
    }

    private readonly record struct LineRange(int Start, int Length)
    {
        public Range Slice => Start..(Start + Length);
    }
}

internal static class ItemTransportHttpEncoder
{
    public static byte[] Wrap(byte[] body)
    {
        if (body.Length is < 1 or > ItemTransportLimits.MaximumBody)
        {
            throw new InvalidOperationException("Invalid service body length.");
        }
        byte[] header = Encoding.ASCII.GetBytes(
            "HTTP/1.1 200 OK\r\n" +
            "Content-Type: application/json; charset=utf-8\r\n" +
            "Content-Length: " + body.Length.ToString(CultureInfo.InvariantCulture) + "\r\n" +
            "Cache-Control: no-store\r\n" +
            "X-Content-Type-Options: nosniff\r\n" +
            "Connection: close\r\n\r\n");
        try
        {
            var response = new byte[header.Length + body.Length];
            header.CopyTo(response, 0);
            body.CopyTo(response, header.Length);
            return response;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(header);
        }
    }
}
