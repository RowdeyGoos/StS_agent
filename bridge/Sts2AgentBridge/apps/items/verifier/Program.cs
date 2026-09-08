using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;

namespace Sts2AgentBridge.Verifier;

internal static class Program
{
    public static int Main(string[] args)
    {
        try
        {
            Arguments parsed = Arguments.Parse(args);
            byte[] policyBytes = SafeFiles.ReadBoundedRegularFile(parsed.Policy, 4 * 1024 * 1024, "policy_boundary");
            string policySha = ItemReleaseProjectionBuilder.Sha(policyBytes);
            if (policySha != ItemReleasePolicy.ExpectedPolicySha256)
            {
                throw new VerificationException("policy_identity_mismatch");
            }
            ItemReleasePolicy policy = ItemReleasePolicy.Parse(policyBytes);
            byte[] candidate = SafeFiles.ReadBoundedRegularFile(parsed.Assembly, 64 * 1024 * 1024, "candidate_boundary");
            ItemReleaseVerificationReport report = ItemReleaseVerifier.Verify(
                candidate, parsed.SourceRoot, policy, enforceArtifactIdentity: true);
            Emit(new SortedDictionary<string, object?>(StringComparer.Ordinal)
            {
                ["assembly_sha256"] = report.AssemblySha256,
                ["checked_method_bodies"] = report.CheckedMethodBodies,
                ["metadata_projection_sha256"] = report.MetadataProjectionSha256,
                ["schema_version"] = 1,
                ["source_projection_sha256"] = report.SourceProjectionSha256,
                ["status"] = "passed",
                ["suite"] = "item_v1_release_surface",
            });
            return 0;
        }
        catch (InvocationException exception) { EmitFailure(exception.Code); return 2; }
        catch (BoundaryException exception) { EmitFailure(exception.Code); return 3; }
        catch (VerificationException exception) { EmitFailure(exception.Code); return 4; }
        catch { EmitFailure("internal_failure"); return 5; }
    }

    private static void EmitFailure(string code) => Emit(new SortedDictionary<string, object?>(StringComparer.Ordinal)
    {
        ["code"] = code,
        ["schema_version"] = 1,
        ["status"] = "failed",
    });

    private static void Emit(SortedDictionary<string, object?> value) =>
        Console.Out.WriteLine(JsonSerializer.Serialize(value));

    private sealed record Arguments(string Assembly, string SourceRoot, string Policy)
    {
        internal static Arguments Parse(string[] args)
        {
            if (args.Length != 6) throw new InvocationException("invalid_arguments");
            var values = new Dictionary<string, string>(StringComparer.Ordinal);
            for (int index = 0; index < args.Length; index += 2)
            {
                string key = args[index];
                if (key is not "--assembly" and not "--source-root" and not "--policy" ||
                    !values.TryAdd(key, args[index + 1]))
                    throw new InvocationException("invalid_arguments");
            }
            return new Arguments(
                Absolute(values, "--assembly"),
                Absolute(values, "--source-root"),
                Absolute(values, "--policy"));
        }

        private static string Absolute(Dictionary<string, string> values, string key)
        {
            if (!values.TryGetValue(key, out string? value) || !Path.IsPathFullyQualified(value) ||
                !string.Equals(Path.GetFullPath(value), value, StringComparison.Ordinal))
                throw new InvocationException("invalid_arguments");
            return value;
        }
    }

    private sealed class InvocationException : Exception
    {
        internal InvocationException(string code) : base(code) => Code = code;
        internal string Code { get; }
    }
}
