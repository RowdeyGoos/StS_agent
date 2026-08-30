using System;

namespace Sts2AgentBridge.Core.Protocol;

public enum ProbeErrorKind
{
    InvalidRequest = 1,
    Unauthenticated = 2,
    Forbidden = 3,
    UnsupportedContent = 4,
    ReadOnly = 5,
    PayloadTooLarge = 6,
    RateLimited = 7,
    BackendFault = 8,
    BackendUnavailable = 9,
}

public readonly struct ProbeErrorDescriptor
{
    internal ProbeErrorDescriptor(
        int statusCode,
        string reasonPhrase,
        string code,
        bool retryable,
        string? additionalHeaderLine)
    {
        StatusCode = statusCode;
        ReasonPhrase = reasonPhrase;
        Code = code;
        Retryable = retryable;
        AdditionalHeaderLine = additionalHeaderLine;
    }

    public int StatusCode { get; }

    public string ReasonPhrase { get; }

    public string Code { get; }

    public bool Retryable { get; }

    internal string? AdditionalHeaderLine { get; }
}

public static class ProbeErrorCatalog
{
    public static ProbeErrorDescriptor Get(ProbeErrorKind kind)
    {
        return kind switch
        {
            ProbeErrorKind.InvalidRequest =>
                new ProbeErrorDescriptor(400, "Bad Request", "invalid_request", false, null),
            ProbeErrorKind.Unauthenticated =>
                new ProbeErrorDescriptor(401, "Unauthorized", "unauthenticated", false, "WWW-Authenticate: Bearer"),
            ProbeErrorKind.Forbidden =>
                new ProbeErrorDescriptor(403, "Forbidden", "forbidden", false, null),
            ProbeErrorKind.UnsupportedContent =>
                new ProbeErrorDescriptor(404, "Not Found", "unsupported_content", false, null),
            ProbeErrorKind.ReadOnly =>
                new ProbeErrorDescriptor(405, "Method Not Allowed", "read_only", false, "Allow: GET"),
            ProbeErrorKind.PayloadTooLarge =>
                new ProbeErrorDescriptor(413, "Payload Too Large", "payload_too_large", false, null),
            ProbeErrorKind.RateLimited =>
                new ProbeErrorDescriptor(429, "Too Many Requests", "rate_limited", true, "Retry-After: 1"),
            ProbeErrorKind.BackendFault =>
                new ProbeErrorDescriptor(500, "Internal Server Error", "backend_fault", false, null),
            ProbeErrorKind.BackendUnavailable =>
                new ProbeErrorDescriptor(503, "Service Unavailable", "backend_fault", true, null),
            _ => throw new ArgumentOutOfRangeException(nameof(kind)),
        };
    }
}
