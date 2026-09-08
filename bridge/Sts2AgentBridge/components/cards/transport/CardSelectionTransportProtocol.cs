using System;
using System.Globalization;
using System.Text;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal static class CardSelectionTransportLimits
{
    internal const int Port = 43117;
    internal const int Backlog = 8;
    internal const int MaximumHandlers = 4;
    internal const int MaximumRequestHead = 1024;
    internal const int RequestBufferSize = 1025;
    internal const int MaximumBody = 65536;
    internal const int MaximumReads = 1024;
    internal const int MaximumParentPosts = 2;
    internal const int MaximumChildPosts = 10;
    internal const int HeaderReadMilliseconds = 1000;
    internal const int ResponseWriteMilliseconds = 1000;
    internal const int ConnectionLifetimeMilliseconds = 2000;
    internal const int ShutdownJoinMilliseconds = 2000;
}

internal enum CardSelectionTransportRoute
{
    ParentGet = 1,
    ParentPost = 2,
    ChildGet = 3,
    ChildPost = 4,
}

internal readonly record struct ParsedCardSelectionTransportRequest(
    CardSelectionTransportRoute Route,
    int AuthorizationOffset,
    int AuthorizationLength,
    int DecisionOffset,
    int DecisionLength,
    int ActionOffset,
    int ActionLength)
{
    internal bool IsPost => Route is CardSelectionTransportRoute.ParentPost or CardSelectionTransportRoute.ChildPost;
    internal bool IsChild => Route is CardSelectionTransportRoute.ChildGet or CardSelectionTransportRoute.ChildPost;
}

internal static class CardSelectionTransportRequestParser
{
    private static ReadOnlySpan<byte> ParentGetLine => "GET /card-selection-v1/parent HTTP/1.1"u8;
    private static ReadOnlySpan<byte> ParentPostLine => "POST /card-selection-v1/parent/action HTTP/1.1"u8;
    private static ReadOnlySpan<byte> ChildGetLine => "GET /card-selection-v1/child HTTP/1.1"u8;
    private static ReadOnlySpan<byte> ChildPostLine => "POST /card-selection-v1/child/action HTTP/1.1"u8;
    private static ReadOnlySpan<byte> HostLine => "Host: 127.0.0.1:43117"u8;
    private static ReadOnlySpan<byte> AuthorizationPrefix => "Authorization: Bearer "u8;
    private static ReadOnlySpan<byte> AcceptLine => "Accept: application/json"u8;
    private static ReadOnlySpan<byte> DecisionPrefix => "X-Sts2-Decision-Id: "u8;
    private static ReadOnlySpan<byte> ActionPrefix => "X-Sts2-Action-Id: "u8;
    private static ReadOnlySpan<byte> ConnectionLine => "Connection: close"u8;

    internal static bool TryParse(
        ReadOnlySpan<byte> completeHead,
        CardSelectionReleaseSelection selection,
        out ParsedCardSelectionTransportRequest request)
    {
        request = default;
        if (selection is not CardSelectionReleaseSelection.Cheese and not CardSelectionReleaseSelection.Smith ||
            completeHead.Length is < 4 or > CardSelectionTransportLimits.MaximumRequestHead ||
            !completeHead[^4..].SequenceEqual("\r\n\r\n"u8)) return false;

        Span<LineRange> lines = stackalloc LineRange[8];
        if (!TrySplitLines(completeHead, lines, out int count) || count is not (5 or 7) ||
            !TryRoute(completeHead[lines[0].Slice], out CardSelectionTransportRoute route) ||
            !completeHead[lines[1].Slice].SequenceEqual(HostLine) ||
            !completeHead[lines[3].Slice].SequenceEqual(AcceptLine)) return false;

        ReadOnlySpan<byte> authorization = completeHead[lines[2].Slice];
        if (authorization.Length != AuthorizationPrefix.Length + 64 ||
            !authorization[..AuthorizationPrefix.Length].SequenceEqual(AuthorizationPrefix) ||
            !IsLowerHex(authorization[AuthorizationPrefix.Length..])) return false;

        bool post = route is CardSelectionTransportRoute.ParentPost or CardSelectionTransportRoute.ChildPost;
        int decisionOffset = 0, decisionLength = 0, actionOffset = 0, actionLength = 0;
        int connectionIndex = 4;
        if (post)
        {
            if (count != 7) return false;
            ReadOnlySpan<byte> decision = completeHead[lines[4].Slice];
            ReadOnlySpan<byte> action = completeHead[lines[5].Slice];
            ReadOnlySpan<byte> actionValue = action.Length > ActionPrefix.Length
                ? action[ActionPrefix.Length..] : ReadOnlySpan<byte>.Empty;
            if (decision.Length != DecisionPrefix.Length + 64 ||
                !decision[..DecisionPrefix.Length].SequenceEqual(DecisionPrefix) ||
                !IsLowerHex(decision[DecisionPrefix.Length..]) ||
                action.Length <= ActionPrefix.Length ||
                !action[..ActionPrefix.Length].SequenceEqual(ActionPrefix) ||
                !IsCanonicalAction(route, actionValue)) return false;
            decisionOffset = lines[4].Start + DecisionPrefix.Length;
            decisionLength = 64;
            actionOffset = lines[5].Start + ActionPrefix.Length;
            actionLength = actionValue.Length;
            connectionIndex = 6;
        }
        else if (count != 5) return false;

        if (!completeHead[lines[connectionIndex].Slice].SequenceEqual(ConnectionLine)) return false;
        request = new(route, lines[2].Start + AuthorizationPrefix.Length, 64,
            decisionOffset, decisionLength, actionOffset, actionLength);
        return true;
    }

    private static bool TryRoute(ReadOnlySpan<byte> line, out CardSelectionTransportRoute route)
    {
        if (line.SequenceEqual(ParentGetLine)) route = CardSelectionTransportRoute.ParentGet;
        else if (line.SequenceEqual(ParentPostLine)) route = CardSelectionTransportRoute.ParentPost;
        else if (line.SequenceEqual(ChildGetLine)) route = CardSelectionTransportRoute.ChildGet;
        else if (line.SequenceEqual(ChildPostLine)) route = CardSelectionTransportRoute.ChildPost;
        else { route = default; return false; }
        return true;
    }

    private static bool IsCanonicalAction(CardSelectionTransportRoute route, ReadOnlySpan<byte> value) =>
        route == CardSelectionTransportRoute.ParentPost
            ? value.SequenceEqual("begin"u8) || value.SequenceEqual("proceed"u8)
            : route == CardSelectionTransportRoute.ChildPost &&
                (value.SequenceEqual("preview"u8) || value.SequenceEqual("confirm"u8) ||
                 CanonicalIndexed(value, "select:"u8, 63));

    private static bool CanonicalIndexed(ReadOnlySpan<byte> value, ReadOnlySpan<byte> prefix, int maximum)
    {
        if (!value.StartsWith(prefix) || value.Length == prefix.Length) return false;
        ReadOnlySpan<byte> digits = value[prefix.Length..];
        if (digits.Length > 1 && digits[0] == (byte)'0') return false;
        int parsed = 0;
        foreach (byte digit in digits)
        {
            if (digit is < (byte)'0' or > (byte)'9') return false;
            parsed = checked(parsed * 10 + digit - (byte)'0');
            if (parsed > maximum) return false;
        }
        return true;
    }

    private static bool TrySplitLines(ReadOnlySpan<byte> source, Span<LineRange> lines, out int count)
    {
        count = 0;
        int start = 0;
        for (int index = 0; index < source.Length - 1; index++)
        {
            byte value = source[index];
            if (value is < 0x20 or > 0x7e)
            {
                if (value != (byte)'\r' || source[index + 1] != (byte)'\n') return false;
                if (index == start) return index + 2 == source.Length;
                if (count >= lines.Length) return false;
                lines[count++] = new(start, index - start);
                start = index + 2;
                index++;
            }
        }
        return false;
    }

    private static bool IsLowerHex(ReadOnlySpan<byte> value)
    {
        foreach (byte item in value)
            if (!((item >= (byte)'0' && item <= (byte)'9') ||
                  (item >= (byte)'a' && item <= (byte)'f'))) return false;
        return !value.IsEmpty;
    }

    private readonly record struct LineRange(int Start, int Length)
    {
        internal Range Slice => Start..(Start + Length);
    }
}

internal static class CardSelectionTransportServiceBody
{
    internal static byte[] Build(string decision, string action) =>
        Encoding.ASCII.GetBytes("{\"decision_id\":\"" + decision +
            "\",\"action_id\":\"" + action + "\"}");
}

internal static class CardSelectionTransportHttpEncoder
{
    internal static byte[] Wrap(byte[] body)
    {
        if (body.Length is < 1 or > CardSelectionTransportLimits.MaximumBody)
            throw new InvalidOperationException("Invalid service body length.");
        byte[] header = Encoding.ASCII.GetBytes(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: " +
            body.Length.ToString(CultureInfo.InvariantCulture) +
            "\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n");
        try
        {
            var response = new byte[header.Length + body.Length];
            header.CopyTo(response, 0);
            body.CopyTo(response, header.Length);
            return response;
        }
        finally { Array.Clear(header); }
    }
}
