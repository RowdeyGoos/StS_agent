using System;
using System.Globalization;
using System.Text;

namespace Sts2AgentBridge.Successors.RoomReleaseV1;

internal static class RoomFlowTransportLimits
{
    public const int Port = 43117;
    public const int Backlog = 8;
    public const int MaximumHandlers = 4;
    public const int MaximumRequestHead = 4096;
    public const int RequestBufferSize = 4097;
    public const int MaximumParentBody = 65536;
    public const int MaximumItemBody = 4096;
    public const int MaximumReads = 1024;
    public const int MaximumShopParentPosts = 3;
    public const int MaximumEventParentPosts = 12;
    public const int MaximumEventItemPosts = 1;
    public const int HeaderReadMilliseconds = 1000;
    public const int ResponseWriteMilliseconds = 1000;
    public const int ConnectionLifetimeMilliseconds = 2000;
    public const int ShutdownJoinMilliseconds = 2000;
}

internal enum RoomFlowTransportRoute
{
    ParentGet = 1,
    ParentPost = 2,
    ItemGet = 3,
    ItemPost = 4,
}

internal readonly record struct ParsedRoomFlowTransportRequest(
    RoomFlowTransportRoute Route,
    int AuthorizationOffset,
    int AuthorizationLength,
    int DecisionOffset,
    int DecisionLength,
    int ActionOffset,
    int ActionLength)
{
    public bool IsPost => Route is RoomFlowTransportRoute.ParentPost or RoomFlowTransportRoute.ItemPost;
    public bool IsItem => Route is RoomFlowTransportRoute.ItemGet or RoomFlowTransportRoute.ItemPost;
}

internal static class RoomFlowTransportRequestParser
{
    private static ReadOnlySpan<byte> ParentGetLine =>
        "GET /probe/room-flows-v1/public/decision HTTP/1.1"u8;
    private static ReadOnlySpan<byte> ParentPostLine =>
        "POST /probe/room-flows-v1/public/action HTTP/1.1"u8;
    private static ReadOnlySpan<byte> ItemGetLine =>
        "GET /probe/item-v1/public/item-decision HTTP/1.1"u8;
    private static ReadOnlySpan<byte> ItemPostLine =>
        "POST /probe/item-v1/public/item-action HTTP/1.1"u8;
    private static ReadOnlySpan<byte> HostLine => "Host: 127.0.0.1:43117"u8;
    private static ReadOnlySpan<byte> AuthorizationPrefix => "Authorization: Bearer "u8;
    private static ReadOnlySpan<byte> AcceptLine => "Accept: application/json"u8;
    private static ReadOnlySpan<byte> DecisionPrefix => "X-Sts2-Decision-Id: "u8;
    private static ReadOnlySpan<byte> ActionPrefix => "X-Sts2-Action-Id: "u8;
    private static ReadOnlySpan<byte> ConnectionLine => "Connection: close"u8;

    public static bool TryParse(
        ReadOnlySpan<byte> completeHead,
        RoomFlowSelection selection,
        out ParsedRoomFlowTransportRequest request)
    {
        request = default;
        if (completeHead.Length is < 4 or > RoomFlowTransportLimits.MaximumRequestHead ||
            !completeHead[^4..].SequenceEqual("\r\n\r\n"u8))
        {
            return false;
        }

        Span<LineRange> lines = stackalloc LineRange[8];
        if (!TrySplitLines(completeHead, lines, out int count) || count is not (5 or 7) ||
            !TryRoute(completeHead[lines[0].Slice], selection, out RoomFlowTransportRoute route) ||
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

        bool post = route is RoomFlowTransportRoute.ParentPost or RoomFlowTransportRoute.ItemPost;
        int decisionOffset = 0;
        int decisionLength = 0;
        int actionOffset = 0;
        int actionLength = 0;
        int connectionIndex = 4;
        if (post)
        {
            if (count != 7)
            {
                return false;
            }
            ReadOnlySpan<byte> decision = completeHead[lines[4].Slice];
            ReadOnlySpan<byte> action = completeHead[lines[5].Slice];
            ReadOnlySpan<byte> actionValue = action.Length > ActionPrefix.Length
                ? action[ActionPrefix.Length..]
                : ReadOnlySpan<byte>.Empty;
            if (decision.Length != DecisionPrefix.Length + 64 ||
                !decision[..DecisionPrefix.Length].SequenceEqual(DecisionPrefix) ||
                !IsLowerHex(decision[DecisionPrefix.Length..]) ||
                action.Length <= ActionPrefix.Length ||
                !action[..ActionPrefix.Length].SequenceEqual(ActionPrefix) ||
                !IsCanonicalAction(route, selection, actionValue))
            {
                return false;
            }
            decisionOffset = lines[4].Start + DecisionPrefix.Length;
            decisionLength = 64;
            actionOffset = lines[5].Start + ActionPrefix.Length;
            actionLength = actionValue.Length;
            connectionIndex = 6;
        }
        else if (count != 5)
        {
            return false;
        }

        if (!completeHead[lines[connectionIndex].Slice].SequenceEqual(ConnectionLine))
        {
            return false;
        }
        request = new ParsedRoomFlowTransportRequest(
            route,
            lines[2].Start + AuthorizationPrefix.Length,
            64,
            decisionOffset,
            decisionLength,
            actionOffset,
            actionLength);
        return true;
    }

    private static bool TryRoute(
        ReadOnlySpan<byte> line,
        RoomFlowSelection selection,
        out RoomFlowTransportRoute route)
    {
        if (line.SequenceEqual(ParentGetLine)) route = RoomFlowTransportRoute.ParentGet;
        else if (line.SequenceEqual(ParentPostLine)) route = RoomFlowTransportRoute.ParentPost;
        else if (selection == RoomFlowSelection.Event && line.SequenceEqual(ItemGetLine))
            route = RoomFlowTransportRoute.ItemGet;
        else if (selection == RoomFlowSelection.Event && line.SequenceEqual(ItemPostLine))
            route = RoomFlowTransportRoute.ItemPost;
        else
        {
            route = default;
            return false;
        }
        return true;
    }

    private static bool IsCanonicalAction(
        RoomFlowTransportRoute route,
        RoomFlowSelection selection,
        ReadOnlySpan<byte> value)
    {
        if (route == RoomFlowTransportRoute.ItemPost)
            return CanonicalIndexed(value, "collect:"u8, 255);
        if (selection == RoomFlowSelection.Event)
            return CanonicalIndexed(value, "choose:"u8, 7);
        return value.SequenceEqual("inventory:close"u8) || value.SequenceEqual("leave"u8) ||
            CanonicalIndexed(value, "buy:card:"u8, 31) || CanonicalIndexed(value, "buy:potion:"u8, 31) || CanonicalIndexed(value, "buy:relic:"u8, 31) || CanonicalIndexed(value, "remove:"u8, 511) || CanonicalIndexed(value,"discard:"u8,7);
    }

    private static bool CanonicalIndexed(ReadOnlySpan<byte> value, ReadOnlySpan<byte> prefix, int maximum)
    {
        if (!value.StartsWith(prefix) || value.Length == prefix.Length)
            return false;
        ReadOnlySpan<byte> digits = value[prefix.Length..];
        if (digits.Length > 1 && digits[0] == (byte)'0')
            return false;
        int parsed = 0;
        foreach (byte digit in digits)
        {
            if (digit is < (byte)'0' or > (byte)'9') return false;
            parsed = checked((parsed * 10) + digit - (byte)'0');
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
                  (item >= (byte)'a' && item <= (byte)'f'))) return false;
        }
        return !value.IsEmpty;
    }

    private readonly record struct LineRange(int Start, int Length)
    {
        public Range Slice => Start..(Start + Length);
    }
}

internal static class RoomFlowTransportHttpEncoder
{
    public static byte[] Wrap(RoomFlowTransportRoute route, byte[] body)
    {
        int maximum = route is RoomFlowTransportRoute.ItemGet or RoomFlowTransportRoute.ItemPost
            ? RoomFlowTransportLimits.MaximumItemBody
            : RoomFlowTransportLimits.MaximumParentBody;
        if (body.Length is < 1 || body.Length > maximum)
            throw new InvalidOperationException("Invalid service body length.");
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
            Array.Clear(header);
        }
    }
}
