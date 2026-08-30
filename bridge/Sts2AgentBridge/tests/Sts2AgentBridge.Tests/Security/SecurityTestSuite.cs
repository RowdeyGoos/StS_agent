using System;
using System.Collections.Generic;
using System.Text;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Transport;
using Sts2AgentBridge.Tests.Transport;

namespace Sts2AgentBridge.Tests.Security;

internal static class SecurityTestSuite
{
    public static void Run()
    {
        SyntaxFramingAndAuthenticationPrecedenceIsExact();
        SecurityHeaderNamesAreCaseInsensitiveAndDuplicatesFail();
        AuthenticatedRateLimitPrecedesDisclosureChecks();
        RejectedRequestsNeverInvokeTheScreenService();
        FrozenMalformedCorpusAndDeterministicFuzzFailClosed();
        ResponsesContainNoCorsOrFixtureSensitiveText();
    }

    private static void SyntaxFramingAndAuthenticationPrecedenceIsExact()
    {
        AssertFreshStatus(
            413,
            TransportProcessorFixture.Request(
                host: "wrong-host",
                authorization: "wrong",
                additionalHeaders: new[] { "Content-Length: 0" }),
            "framing precedes authentication");
        AssertFreshStatus(
            413,
            TransportProcessorFixture.Request(
                authorization: "wrong",
                additionalHeaders: new[] { "tRaNsFeR-EnCoDiNg: chunked" }),
            "mixed-case framing precedes authentication");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                authorization: "wrong",
                additionalHeaders: new[] { "X-Unknown: value" }),
            "disallowed header precedes authentication");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                target: "/probe/v0/health?query=1",
                authorization: "wrong"),
            "query rejection precedes authentication");
        AssertFreshStatus(
            400,
            "GET /probe/v0/health HTTP/1.1\r\nHost:127.0.0.1:43117\r\n\r\n",
            "strict header delimiter");

        AssertFreshStatus(
            401,
            TransportProcessorFixture.Request(authorization: null),
            "missing authorization");
        AssertFreshStatus(
            401,
            TransportProcessorFixture.Request(
                additionalHeaders: new[]
                {
                    "Authorization: Bearer " + TransportProcessorFixture.Credential,
                }),
            "duplicate authorization");
        AssertFreshStatus(
            401,
            TransportProcessorFixture.Request(
                host: "wrong-host",
                method: "POST",
                target: "/unknown",
                authorization: "Basic " + TransportProcessorFixture.Credential,
                additionalHeaders: new[] { "Origin: https://fixture.invalid" }),
            "bad authorization hides host origin method and route");
        AssertFreshStatus(
            401,
            TransportProcessorFixture.Request(
                authorization: "Bearer " + TransportProcessorFixture.Credential.ToUpperInvariant()),
            "uppercase credential mismatch");
        AssertFreshStatus(
            401,
            TransportProcessorFixture.Request(
                authorization: "Bearer " + new string('0', 63)),
            "short credential");
        AssertFreshStatus(
            401,
            TransportProcessorFixture.Request(
                authorization: "Bearer " + new string('0', 64)),
            "wrong credential");

        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(host: null),
            "missing Host after valid authentication");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                additionalHeaders: new[] { "Host: 127.0.0.1:43117" }),
            "duplicate Host after valid authentication");
        AssertFreshStatus(
            403,
            TransportProcessorFixture.Request(host: "localhost:43117"),
            "wrong Host after valid authentication");
        AssertFreshStatus(
            403,
            TransportProcessorFixture.Request(
                additionalHeaders: new[] { "Origin: null" }),
            "any Origin after valid authentication");
        AssertFreshStatus(
            405,
            TransportProcessorFixture.Request(method: "POST"),
            "non-GET after valid authentication");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(target: "/probe/v0/public/combat-action"),
            "combat action requires POST");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                target: "/probe/v0/public/combat-action",
                method: "POST"),
            "combat action requires snapshot-bound headers");
        AssertFreshStatus(
            405,
            TransportProcessorFixture.Request(method: "get"),
            "method bytes are case-sensitive");
        AssertFreshStatus(
            404,
            TransportProcessorFixture.Request(target: "/probe/v0/unknown"),
            "unknown route");
        AssertFreshStatus(
            404,
            TransportProcessorFixture.Request(target: "/probe/v0/health/"),
            "trailing slash is not an alias");
        AssertFreshStatus(
            404,
            TransportProcessorFixture.Request(target: "/PROBE/v0/health"),
            "route bytes are case-sensitive");
        AssertFreshStatus(
            404,
            TransportProcessorFixture.Request(target: "/probe/v0/%68ealth"),
            "percent bytes are not decoded");

        using var locked = new TransportProcessorFixture(ProbeMode.IncompatibleLocked);
        TransportProcessorFixture.AssertStatus(
            404,
            locked.Process(
                TransportProcessorFixture.Request(target: "/probe/v0/public/screen")),
            "locked screen route is absent");
    }

    private static void SecurityHeaderNamesAreCaseInsensitiveAndDuplicatesFail()
    {
        string mixedCase =
            "GET /probe/v0/health HTTP/1.1\r\n" +
            "hOsT: 127.0.0.1:43117\r\n" +
            "aUtHoRiZaTiOn: Bearer " + TransportProcessorFixture.Credential + "\r\n" +
            "aCcEpT: application/json\r\n" +
            "cOnNeCtIoN: close\r\n" +
            "\r\n";
        using (var fixture = new TransportProcessorFixture())
        {
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodeHealthResponse(
                    TransportProcessorFixture.ProcessCorrelationId),
                fixture.Process(mixedCase).Response,
                "mixed-case accepted header names");
        }

        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                additionalHeaders: new[] { "Accept: */*", "aCcEpT: application/json" }),
            "duplicate Accept");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                additionalHeaders: new[] { "Connection: close", "cOnNeCtIoN: close" }),
            "duplicate Connection");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                target: "/probe/v0/public/combat-action",
                method: "POST",
                additionalHeaders: new[]
                {
                    "X-Sts2-Decision-Id: " + new string('0', 64),
                    "x-sTs2-DeCiSiOn-Id: " + new string('0', 64),
                    "X-Sts2-Action-Id: play:0",
                }),
            "duplicate decision ID");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                additionalHeaders: new[] { "Origin: null", "oRiGiN: null" }),
            "duplicate Origin");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                additionalHeaders: new[] { "Accept: text/plain" }),
            "invalid Accept value");
        AssertFreshStatus(
            400,
            TransportProcessorFixture.Request(
                additionalHeaders: new[] { "Connection: keep-alive" }),
            "keep-alive is rejected");
    }

    private static void AuthenticatedRateLimitPrecedesDisclosureChecks()
    {
        using (var fixture = new TransportProcessorFixture())
        {
            for (int index = 0; index < 10; index++)
            {
                TransportProcessorFixture.AssertStatus(
                    200,
                    fixture.Process(TransportProcessorFixture.Request()),
                    "authenticated burst request " + index);
            }

            TransportProcessorFixture.AssertStatus(
                429,
                fixture.Process(TransportProcessorFixture.Request()),
                "authenticated burst exhausted");
            TransportProcessorFixture.AssertStatus(
                429,
                fixture.Process(TransportProcessorFixture.Request(host: "wrong-host")),
                "rate limit precedes Host disclosure");
            TransportProcessorFixture.AssertStatus(
                401,
                fixture.Process(TransportProcessorFixture.Request(authorization: "wrong")),
                "authentication still precedes exhausted authenticated bucket");
        }

        using (var fixture = new TransportProcessorFixture())
        {
            for (int index = 0; index < 32; index++)
            {
                TransportProcessorFixture.AssertStatus(
                    401,
                    fixture.Process(TransportProcessorFixture.Request(authorization: "wrong")),
                    "invalid authentication does not consume bucket " + index);
            }

            for (int index = 0; index < 10; index++)
            {
                TransportProcessorFixture.AssertStatus(
                    200,
                    fixture.Process(TransportProcessorFixture.Request()),
                    "valid burst remains after bad auth " + index);
            }
        }
    }

    private static void RejectedRequestsNeverInvokeTheScreenService()
    {
        var service = new RecordingPublicScreenService();
        using var fixture = new TransportProcessorFixture(service: service);
        string target = "/probe/v0/public/screen";

        TransportProcessorFixture.AssertStatus(
            400,
            fixture.Process(
                TransportProcessorFixture.Request(
                    target: target,
                    additionalHeaders: new[] { "X-Unknown: value" })),
            "screen syntax rejection");
        TransportProcessorFixture.AssertStatus(
            401,
            fixture.Process(
                TransportProcessorFixture.Request(target: target, authorization: "wrong")),
            "screen authentication rejection");
        TransportProcessorFixture.AssertStatus(
            403,
            fixture.Process(
                TransportProcessorFixture.Request(target: target, host: "wrong-host")),
            "screen Host rejection");
        TransportProcessorFixture.AssertStatus(
            405,
            fixture.Process(
                TransportProcessorFixture.Request(target: target, method: "POST")),
            "screen method rejection");
        TestAssert.Equal(0, service.Calls, "rejected requests never invoke screen service");
        TestAssert.Equal(0, fixture.Queue!.OutstandingCount, "rejected requests never enter frame queue");
    }

    private static void FrozenMalformedCorpusAndDeterministicFuzzFailClosed()
    {
        var malformedCorpus = new (byte[] Bytes, ProbeRequestParseStatus Expected)[]
        {
            (Array.Empty<byte>(), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET / HTTP/1.1\n\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET / HTTP/1.0\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET  / HTTP/1.1\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET http://example/ HTTP/1.1\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET /?x=1 HTTP/1.1\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET /#x HTTP/1.1\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET / HTTP/1.1\r\nHost\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET / HTTP/1.1\r\nHost : value\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET / HTTP/1.1\r\nHost:\tvalue\r\n\r\n"), ProbeRequestParseStatus.InvalidRequest),
            (Encoding.ASCII.GetBytes("GET / HTTP/1.1\r\nContent-Length: 0\r\n\r\n"), ProbeRequestParseStatus.PayloadTooLarge),
            (Encoding.ASCII.GetBytes("GET / HTTP/1.1\r\nTE: trailers\r\n\r\n"), ProbeRequestParseStatus.PayloadTooLarge),
            (Encoding.ASCII.GetBytes("GET / HTTP/1.1\r\n\r\nextra"), ProbeRequestParseStatus.SilentClose),
            (new byte[] { (byte)'G', (byte)'E', (byte)'T', (byte)' ', 0xff, 13, 10, 13, 10 }, ProbeRequestParseStatus.InvalidRequest),
        };

        foreach ((byte[] bytes, ProbeRequestParseStatus expected) in malformedCorpus)
        {
            TestAssert.Equal(expected, ProbeRequestParser.Parse(bytes).Status, "frozen malformed corpus item");
        }

        var random = new Random(0x5a17_2026);
        for (int index = 0; index < 10_000; index++)
        {
            int length = index % (LiveProbeLimits.RequestHeadBufferBytes + 1);
            byte[] input = new byte[length];
            random.NextBytes(input);
            ProbeRequestParseResult first = ProbeRequestParser.Parse(input);
            ProbeRequestParseResult second = ProbeRequestParser.Parse(input);
            TestAssert.Equal(first, second, "deterministic fuzz parse " + index);
        }
    }

    private static void ResponsesContainNoCorsOrFixtureSensitiveText()
    {
        const string sensitiveTarget =
            "/fixture-secret-absolute-path-MegaCrit-Sts2-raw-request";
        using var fixture = new TransportProcessorFixture();
        ProbeProcessingResult first = fixture.Process(
            TransportProcessorFixture.Request(target: sensitiveTarget));
        ProbeProcessingResult second = fixture.Process(
            TransportProcessorFixture.Request(target: sensitiveTarget));
        TransportProcessorFixture.AssertStatus(404, first, "sensitive unknown route");
        TransportProcessorFixture.AssertStatus(404, second, "repeated sensitive unknown route");

        string firstText = Encoding.ASCII.GetString(first.Response);
        string secondText = Encoding.ASCII.GetString(second.Response);
        string[] forbidden =
        {
            "Access-Control-",
            "fixture-secret",
            "absolute-path",
            "MegaCrit",
            "raw-request",
            "Authorization",
            TransportProcessorFixture.Credential,
        };
        foreach (string value in forbidden)
        {
            TestAssert.False(firstText.Contains(value, StringComparison.Ordinal), "first response excludes " + value);
            TestAssert.False(secondText.Contains(value, StringComparison.Ordinal), "second response excludes " + value);
        }

        string firstCorrelation = ExtractCorrelationId(firstText);
        string secondCorrelation = ExtractCorrelationId(secondText);
        TestAssert.True(CorrelationIdGenerator.IsCanonical(firstCorrelation), "first request correlation ID");
        TestAssert.True(CorrelationIdGenerator.IsCanonical(secondCorrelation), "second request correlation ID");
        TestAssert.False(
            string.Equals(firstCorrelation, secondCorrelation, StringComparison.Ordinal),
            "request correlation IDs are fresh");

        string health = Encoding.ASCII.GetString(
            fixture.Process(TransportProcessorFixture.Request()).Response);
        TestAssert.False(health.Contains("Access-Control-", StringComparison.Ordinal), "success has no CORS headers");
    }

    private static void AssertFreshStatus(int status, string request, string message)
    {
        using var fixture = new TransportProcessorFixture();
        TransportProcessorFixture.AssertStatus(status, fixture.Process(request), message);
    }

    private static string ExtractCorrelationId(string response)
    {
        const string marker = "\"correlation_id\":\"";
        int start = response.IndexOf(marker, StringComparison.Ordinal);
        TestAssert.True(start >= 0, "response correlation marker");
        start += marker.Length;
        TestAssert.True(start <= response.Length - CorrelationIdGenerator.EncodedCharacterCount, "response correlation length");
        return response.Substring(start, CorrelationIdGenerator.EncodedCharacterCount);
    }
}
