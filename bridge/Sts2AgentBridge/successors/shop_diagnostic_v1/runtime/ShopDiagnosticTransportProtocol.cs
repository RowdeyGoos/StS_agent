using System;
using System.Globalization;
using System.Text;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

internal static class ShopDiagnosticTransportLimits
{
    public const int Port = 43117;
    public const int Backlog = 8;
    public const int MaximumHandlers = 4;
    public const int MaximumRequestHead = 4096;
    public const int RequestBufferSize = 4097;
    public const int MaximumBody = 512;
    public const int HeaderReadMilliseconds = 1000;
    public const int ResponseWriteMilliseconds = 1000;
    public const int ConnectionLifetimeMilliseconds = 2000;
    public const int ShutdownJoinMilliseconds = 2000;
}

internal readonly record struct ParsedShopDiagnosticRequest(
    int AuthorizationOffset,
    int AuthorizationLength);

internal static class ShopDiagnosticTransportRequestParser
{
    private static ReadOnlySpan<byte> RequestLine =>
        "GET /probe/shop-diagnostic-v1/public/diagnostic HTTP/1.1"u8;
    private static ReadOnlySpan<byte> HostLine => "Host: 127.0.0.1:43117"u8;
    private static ReadOnlySpan<byte> AuthorizationPrefix => "Authorization: Bearer "u8;
    private static ReadOnlySpan<byte> AcceptLine => "Accept: application/json"u8;
    private static ReadOnlySpan<byte> ConnectionLine => "Connection: close"u8;

    public static bool TryParse(
        ReadOnlySpan<byte> completeHead,
        out ParsedShopDiagnosticRequest request)
    {
        request = default;
        if (completeHead.Length is < 4 or > ShopDiagnosticTransportLimits.MaximumRequestHead ||
            !completeHead[^4..].SequenceEqual("\r\n\r\n"u8))
        {
            return false;
        }

        Span<LineRange> lines = stackalloc LineRange[5];
        if (!TrySplitLines(completeHead, lines, out int count) || count != 5 ||
            !completeHead[lines[0].Slice].SequenceEqual(RequestLine) ||
            !completeHead[lines[1].Slice].SequenceEqual(HostLine) ||
            !completeHead[lines[3].Slice].SequenceEqual(AcceptLine) ||
            !completeHead[lines[4].Slice].SequenceEqual(ConnectionLine))
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

        request = new ParsedShopDiagnosticRequest(
            lines[2].Start + AuthorizationPrefix.Length,
            64);
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

internal static class ShopDiagnosticTransportHttpEncoder
{
    public static byte[] Wrap(byte[] body)
    {
        if (body.Length is < 1 or > ShopDiagnosticTransportLimits.MaximumBody)
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
