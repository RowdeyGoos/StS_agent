using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV7;

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
internal sealed class GenericEventReleasePolicy
{
    // Finalized only after two fresh candidate builds are byte-identical and
    // the extracted policy has completed independent review.
    internal const string ExpectedPolicySha256 = "00d5fae2cac6611efe455c978dfef900c0fbb5bb45321b05a29edfdd7707c8f6";
    internal const long ExpectedCandidateLength = 382464;
    internal const int ExpectedSourceCount = 56;

    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; set; }

    [JsonPropertyName("candidate_length")]
    public long CandidateLength { get; set; }

    [JsonPropertyName("candidate_sha256")]
    public string CandidateSha256 { get; set; } = string.Empty;

    [JsonPropertyName("source_projection_sha256")]
    public string SourceProjectionSha256 { get; set; } = string.Empty;

    [JsonPropertyName("metadata_projection_sha256")]
    public string MetadataProjectionSha256 { get; set; } = string.Empty;

    [JsonPropertyName("checked_method_bodies")]
    public int CheckedMethodBodies { get; set; }

    [JsonPropertyName("source_files")]
    public PolicySourceFile[] SourceFiles { get; set; } = Array.Empty<PolicySourceFile>();

    [JsonPropertyName("metadata_inventory")]
    public string[] MetadataInventory { get; set; } = Array.Empty<string>();

    internal static GenericEventReleasePolicy Parse(byte[] bytes)
    {
        GenericEventReleasePolicy? policy;
        try
        {
            policy = JsonSerializer.Deserialize<GenericEventReleasePolicy>(bytes, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = false,
            });
        }
        catch
        {
            throw new VerificationException("policy_invalid");
        }
        if (policy is null || policy.SchemaVersion != 1 ||
            policy.CandidateLength != ExpectedCandidateLength ||
            !IsSha(policy.CandidateSha256) || !IsSha(policy.SourceProjectionSha256) ||
            !IsSha(policy.MetadataProjectionSha256) || policy.CheckedMethodBodies <= 0 ||
            policy.SourceFiles.Length != ExpectedSourceCount || policy.MetadataInventory.Length == 0)
        {
            throw new VerificationException("policy_invalid");
        }
        RequireSorted(policy.SourceFiles.Select(file => file.Path), "policy_sources", unique: true);
        RequireSorted(policy.MetadataInventory, "policy_inventory", unique: false);
        foreach (PolicySourceFile file in policy.SourceFiles)
        {
            if (!IsRelativePath(file.Path) || !IsSha(file.Sha256))
            {
                throw new VerificationException("policy_sources");
            }
        }
        return policy;
    }

    private static void RequireSorted(IEnumerable<string> values, string code, bool unique)
    {
        string? previous = null;
        foreach (string value in values)
        {
            if (string.IsNullOrEmpty(value) || previous is not null &&
                StringComparer.Ordinal.Compare(previous, value) > (unique ? -1 : 0))
            {
                throw new VerificationException(code);
            }
            previous = value;
        }
    }

    private static bool IsRelativePath(string value) =>
        !string.IsNullOrEmpty(value) && !value.StartsWith("/", StringComparison.Ordinal) &&
        !value.StartsWith("\\", StringComparison.Ordinal) && !value.Contains("//", StringComparison.Ordinal) &&
        value.Split('/').All(part => part.Length > 0 && part is not "." and not "..");

    internal static bool IsSha(string value) =>
        value.Length == 64 && value.All(character =>
            character is >= '0' and <= '9' or >= 'a' and <= 'f');
}

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
internal sealed class PolicySourceFile
{
    [JsonPropertyName("path")]
    public string Path { get; set; } = string.Empty;

    [JsonPropertyName("sha256")]
    public string Sha256 { get; set; } = string.Empty;
}
