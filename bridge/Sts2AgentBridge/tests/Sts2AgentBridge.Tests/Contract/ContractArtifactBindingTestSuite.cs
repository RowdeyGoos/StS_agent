using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Core.Configuration;
using Sts2AgentBridge.Core.Hosting;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Tests.Contract;

internal static class ContractArtifactBindingTestSuite
{
    private const string ZeroCorrelationId = "00000000000000000000000000000000";

    private const string EnabledConfiguration =
        "{\"schema_version\":\"live_probe_v0_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}";

    private const string DisabledConfiguration =
        "{\"schema_version\":\"live_probe_v0_config_v1\",\"enabled\":false,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}";

    private const string EnabledConfigurationSha256 =
        "f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea";

    private const string DisabledConfigurationSha256 =
        "132f4c49ee499a52b43d2f0d66edcba1bd78bd5b49777c270636246d85cd3b52";

    private static readonly string[] LimitPropertyNames =
    {
        "schema_version",
        "listener_address",
        "listener_port",
        "listener_backlog",
        "maximum_concurrent_connections",
        "pre_authentication_refill_per_second",
        "pre_authentication_burst",
        "authenticated_refill_per_second",
        "authenticated_burst",
        "maximum_request_line_bytes",
        "maximum_request_head_bytes",
        "request_head_buffer_bytes",
        "maximum_header_count",
        "maximum_header_name_bytes",
        "maximum_header_value_bytes",
        "maximum_request_target_bytes",
        "maximum_error_body_bytes",
        "maximum_response_body_bytes",
        "header_read_timeout_ms",
        "response_write_timeout_ms",
        "total_connection_lifetime_ms",
        "maximum_outstanding_screen_reads",
        "maximum_game_thread_work_per_frame",
        "game_thread_queue_wait_ms",
        "game_thread_result_wait_ms",
        "worker_shutdown_join_ms",
        "maximum_configuration_bytes",
        "configuration_overflow_buffer_bytes",
        "credential_bytes",
        "credential_overflow_buffer_bytes",
    };

    public static void Run()
    {
        string contractRoot = ResolveCopiedContractRoot();
        VectorArtifactsMatchProductionBytes(contractRoot);
        LimitsArtifactMatchesProductionConstants(contractRoot);
        ConfigurationArtifactsMatchBytesHashesAndParser(contractRoot);
    }

    private static string ResolveCopiedContractRoot()
    {
        string outputRoot = Path.GetFullPath(AppContext.BaseDirectory);
        string contractRoot = Path.GetFullPath(
            Path.Combine(outputRoot, "ContractArtifacts", "live_probe_v0"));
        string containmentPrefix = outputRoot.EndsWith(Path.DirectorySeparatorChar)
            ? outputRoot
            : outputRoot + Path.DirectorySeparatorChar;

        TestAssert.True(
            contractRoot.StartsWith(containmentPrefix, StringComparison.Ordinal),
            "copied contract root remains inside the test output");
        TestAssert.True(Directory.Exists(contractRoot), "copied contract root exists");
        return contractRoot;
    }

    private static void VectorArtifactsMatchProductionBytes(string contractRoot)
    {
        var expected = new Dictionary<string, byte[]>(StringComparer.Ordinal);

        AddVector(
            expected,
            "health_running",
            CanonicalProbeEncoder.EncodeHealthBody(ZeroCorrelationId),
            CanonicalProbeEncoder.EncodeHealthResponse(ZeroCorrelationId));
        AddVector(
            expected,
            "manifest_compatible",
            CanonicalProbeEncoder.EncodeManifestBody(ProbeMode.Compatible),
            CanonicalProbeEncoder.EncodeManifestResponse(ProbeMode.Compatible));
        AddVector(
            expected,
            "manifest_locked",
            CanonicalProbeEncoder.EncodeManifestBody(ProbeMode.IncompatibleLocked),
            CanonicalProbeEncoder.EncodeManifestResponse(ProbeMode.IncompatibleLocked));
        AddVector(
            expected,
            "screen_main_menu",
            CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.MainMenu)),
            CanonicalProbeEncoder.EncodePublicScreenResponse(
                new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.MainMenu)));
        AddVector(
            expected,
            "screen_settings",
            CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.Settings)),
            CanonicalProbeEncoder.EncodePublicScreenResponse(
                new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.Settings)));
        AddVector(
            expected,
            "screen_waiting",
            CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Waiting, PublicScreenKind.Unknown)),
            CanonicalProbeEncoder.EncodePublicScreenResponse(
                new PublicScreenSnapshot(PublicScreenStatus.Waiting, PublicScreenKind.Unknown)));
        AddVector(
            expected,
            "screen_unsupported",
            CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Unsupported, PublicScreenKind.Unknown)),
            CanonicalProbeEncoder.EncodePublicScreenResponse(
                new PublicScreenSnapshot(PublicScreenStatus.Unsupported, PublicScreenKind.Unknown)));

        AddErrorVector(expected, "error_400", ProbeErrorKind.InvalidRequest);
        AddErrorVector(expected, "error_401", ProbeErrorKind.Unauthenticated);
        AddErrorVector(expected, "error_403", ProbeErrorKind.Forbidden);
        AddErrorVector(expected, "error_404", ProbeErrorKind.UnsupportedContent);
        AddErrorVector(expected, "error_405", ProbeErrorKind.ReadOnly);
        AddErrorVector(expected, "error_413", ProbeErrorKind.PayloadTooLarge);
        AddErrorVector(expected, "error_429", ProbeErrorKind.RateLimited);
        AddErrorVector(expected, "error_500", ProbeErrorKind.BackendFault);
        AddErrorVector(expected, "error_503", ProbeErrorKind.BackendUnavailable);

        string vectorRoot = Path.Combine(contractRoot, "vectors");
        TestAssert.True(Directory.Exists(vectorRoot), "copied vector root exists");
        string[] artifactPaths = Directory.GetFiles(vectorRoot, "*", SearchOption.AllDirectories);
        string[] actualNames = new string[artifactPaths.Length];
        for (int index = 0; index < artifactPaths.Length; index++)
        {
            actualNames[index] = Path.GetRelativePath(vectorRoot, artifactPaths[index])
                .Replace(Path.DirectorySeparatorChar, '/');
        }

        string[] expectedNames = new string[expected.Count];
        expected.Keys.CopyTo(expectedNames, 0);
        Array.Sort(actualNames, StringComparer.Ordinal);
        Array.Sort(expectedNames, StringComparer.Ordinal);
        TestAssert.Equal(
            string.Join("\n", expectedNames),
            string.Join("\n", actualNames),
            "copied vector artifact inventory");

        foreach (string fileName in expectedNames)
        {
            byte[] artifact = File.ReadAllBytes(Path.Combine(vectorRoot, fileName));
            TestAssert.SequenceEqual(expected[fileName], artifact, "golden vector " + fileName);
        }
    }

    private static void AddVector(
        IDictionary<string, byte[]> expected,
        string baseName,
        byte[] body,
        byte[] response)
    {
        expected.Add(baseName + ".json", body);
        expected.Add(baseName + ".http", response);
    }

    private static void AddErrorVector(
        IDictionary<string, byte[]> expected,
        string baseName,
        ProbeErrorKind kind)
    {
        AddVector(
            expected,
            baseName,
            CanonicalProbeEncoder.EncodeErrorBody(kind, ZeroCorrelationId),
            CanonicalProbeEncoder.EncodeErrorResponse(kind, ZeroCorrelationId));
    }

    private static void LimitsArtifactMatchesProductionConstants(string contractRoot)
    {
        byte[] artifact = File.ReadAllBytes(Path.Combine(contractRoot, "limits.json"));
        using JsonDocument document = JsonDocument.Parse(
            artifact,
            new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 2,
            });
        JsonElement root = document.RootElement;
        TestAssert.Equal(JsonValueKind.Object, root.ValueKind, "limits root kind");

        var actualNames = new List<string>();
        foreach (JsonProperty property in root.EnumerateObject())
        {
            actualNames.Add(property.Name);
        }

        TestAssert.Equal(
            string.Join("\n", LimitPropertyNames),
            string.Join("\n", actualNames),
            "limits property inventory and order");

        AssertString(
            root,
            "schema_version",
            LiveProbeLimits.ProtocolName + "_limits_v" + LiveProbeLimits.SchemaVersion);
        AssertString(root, "listener_address", LiveProbeLimits.ListenerAddress);
        AssertInteger(root, "listener_port", LiveProbeLimits.ListenerPort);
        AssertInteger(root, "listener_backlog", LiveProbeLimits.ListenerBacklog);
        AssertInteger(root, "maximum_concurrent_connections", LiveProbeLimits.MaximumConcurrentConnections);
        AssertNumber(root, "pre_authentication_refill_per_second", LiveProbeLimits.PreAuthenticationRefillPerSecond);
        AssertNumber(root, "pre_authentication_burst", LiveProbeLimits.PreAuthenticationBurst);
        AssertNumber(root, "authenticated_refill_per_second", LiveProbeLimits.AuthenticatedRefillPerSecond);
        AssertNumber(root, "authenticated_burst", LiveProbeLimits.AuthenticatedBurst);
        AssertInteger(root, "maximum_request_line_bytes", LiveProbeLimits.MaximumRequestLineBytes);
        AssertInteger(root, "maximum_request_head_bytes", LiveProbeLimits.MaximumRequestHeadBytes);
        AssertInteger(root, "request_head_buffer_bytes", LiveProbeLimits.RequestHeadBufferBytes);
        AssertInteger(root, "maximum_header_count", LiveProbeLimits.MaximumHeaderCount);
        AssertInteger(root, "maximum_header_name_bytes", LiveProbeLimits.MaximumHeaderNameBytes);
        AssertInteger(root, "maximum_header_value_bytes", LiveProbeLimits.MaximumHeaderValueBytes);
        AssertInteger(root, "maximum_request_target_bytes", LiveProbeLimits.MaximumRequestTargetBytes);
        AssertInteger(root, "maximum_error_body_bytes", LiveProbeLimits.MaximumErrorBodyBytes);
        AssertInteger(root, "maximum_response_body_bytes", LiveProbeLimits.MaximumResponseBodyBytes);
        AssertInteger(root, "header_read_timeout_ms", LiveProbeLimits.HeaderReadTimeoutMilliseconds);
        AssertInteger(root, "response_write_timeout_ms", LiveProbeLimits.ResponseWriteTimeoutMilliseconds);
        AssertInteger(root, "total_connection_lifetime_ms", LiveProbeLimits.TotalConnectionLifetimeMilliseconds);
        AssertInteger(root, "maximum_outstanding_screen_reads", LiveProbeLimits.MaximumOutstandingScreenReads);
        AssertInteger(root, "maximum_game_thread_work_per_frame", LiveProbeLimits.MaximumGameThreadWorkPerFrame);
        AssertInteger(root, "game_thread_queue_wait_ms", LiveProbeLimits.GameThreadQueueWaitMilliseconds);
        AssertInteger(root, "game_thread_result_wait_ms", LiveProbeLimits.GameThreadResultWaitMilliseconds);
        AssertInteger(root, "worker_shutdown_join_ms", LiveProbeLimits.WorkerShutdownJoinMilliseconds);
        AssertInteger(root, "maximum_configuration_bytes", StrictConfigurationLoader.MaximumConfigurationBytes);
        AssertInteger(
            root,
            "configuration_overflow_buffer_bytes",
            StrictConfigurationLoader.MaximumConfigurationBytes + 1);
        AssertInteger(root, "credential_bytes", FixedTimeAuthenticator.CredentialLength);
        AssertInteger(
            root,
            "credential_overflow_buffer_bytes",
            FixedTimeAuthenticator.CredentialLength + 1);

        TestAssert.Equal(
            LiveProbeLimits.MaximumOutstandingScreenReads,
            BoundedFrameWorkQueue.Capacity,
            "queue capacity consumes the frozen limit");
        TestAssert.Equal(
            LiveProbeLimits.MaximumGameThreadWorkPerFrame,
            BoundedFrameWorkQueue.WorkPerFrame,
            "per-frame queue work consumes the frozen limit");
        TestAssert.Equal(
            LiveProbeLimits.GameThreadQueueWaitMilliseconds,
            BoundedFrameWorkQueue.QueueWaitMilliseconds,
            "queue admission wait consumes the frozen limit");
        TestAssert.Equal(
            LiveProbeLimits.GameThreadResultWaitMilliseconds,
            BoundedFrameWorkQueue.ResultWaitMilliseconds,
            "queue result wait consumes the frozen limit");
        TestAssert.Equal(
            TimeSpan.FromMilliseconds(LiveProbeLimits.WorkerShutdownJoinMilliseconds),
            BridgeRuntime.ShutdownJoinTimeout,
            "runtime shutdown join consumes the frozen limit");
    }

    private static void ConfigurationArtifactsMatchBytesHashesAndParser(string contractRoot)
    {
        AssertConfigurationArtifact(
            contractRoot,
            "config_enabled.json",
            EnabledConfiguration,
            EnabledConfigurationSha256,
            true);
        AssertConfigurationArtifact(
            contractRoot,
            "config_disabled.json",
            DisabledConfiguration,
            DisabledConfigurationSha256,
            false);
    }

    private static void AssertConfigurationArtifact(
        string contractRoot,
        string fileName,
        string expectedDocument,
        string expectedSha256,
        bool expectedEnabled)
    {
        byte[] artifact = File.ReadAllBytes(Path.Combine(contractRoot, fileName));
        byte[] expectedBytes = Encoding.UTF8.GetBytes(expectedDocument);
        TestAssert.SequenceEqual(expectedBytes, artifact, fileName + " exact bytes");

        string actualSha256 = Convert.ToHexString(SHA256.HashData(artifact)).ToLowerInvariant();
        TestAssert.Equal(expectedSha256, actualSha256, fileName + " SHA-256");

        TestAssert.True(
            StrictConfigurationLoader.TryParseCanonicalDocument(artifact, out bool enabled),
            fileName + " parser accepts canonical bytes");
        TestAssert.Equal(expectedEnabled, enabled, fileName + " parser enabled value");
    }

    private static void AssertString(JsonElement root, string name, string expected)
    {
        TestAssert.True(root.TryGetProperty(name, out JsonElement property), name + " exists");
        TestAssert.Equal(JsonValueKind.String, property.ValueKind, name + " JSON kind");
        TestAssert.Equal(expected, property.GetString(), name + " value");
    }

    private static void AssertInteger(JsonElement root, string name, int expected)
    {
        TestAssert.True(root.TryGetProperty(name, out JsonElement property), name + " exists");
        TestAssert.Equal(JsonValueKind.Number, property.ValueKind, name + " JSON kind");
        TestAssert.True(property.TryGetInt32(out int actual), name + " is an Int32");
        TestAssert.Equal(expected, actual, name + " value");
    }

    private static void AssertNumber(JsonElement root, string name, double expected)
    {
        TestAssert.True(root.TryGetProperty(name, out JsonElement property), name + " exists");
        TestAssert.Equal(JsonValueKind.Number, property.ValueKind, name + " JSON kind");
        TestAssert.Equal(expected, property.GetDouble(), name + " value");
    }
}
