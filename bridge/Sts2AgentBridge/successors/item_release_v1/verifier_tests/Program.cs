using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Verifier;

internal static class Program
{
    private static readonly string[] ProductionSources =
    {
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/lifecycle/ItemBootstrapLifecycle.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/native/GodotItemFrameConnector.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/native/ItemBootstrapHost.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/native/ModEntry.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/native/PinnedItemBuildGuard.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/native/ProductionItemBootstrapSupport.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/native/ProductionItemRuntimeFactory.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/operator/DarwinReadOnly.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/operator/ItemOperatorConfiguration.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/operator/ItemOperatorFiles.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/operator/ItemPinnedFileIdentity.cs",
        "bridge/Sts2AgentBridge/successors/item_transport_v1/runtime/ItemTransportConfiguration.cs",
        "bridge/Sts2AgentBridge/successors/item_transport_v1/runtime/ItemTransportProtocol.cs",
        "bridge/Sts2AgentBridge/successors/item_transport_v1/runtime/ItemTransportRuntime.cs",
        "bridge/Sts2AgentBridge/successors/item_transport_v1/runtime/OwnedByteFrameQueue.cs",
        "bridge/Sts2AgentBridge/successors/item_transport_v1/runtime/kernel/FixedTimeAuthenticator.cs",
        "bridge/Sts2AgentBridge/successors/item_transport_v1/runtime/kernel/MonotonicTokenBucket.cs",
        "bridge/Sts2AgentBridge/successors/item_v1/core/ItemV1CanonicalEncoder.cs",
        "bridge/Sts2AgentBridge/successors/item_v1/core/ItemV1Contracts.cs",
        "bridge/Sts2AgentBridge/successors/item_v1/core/ItemV1Session.cs",
        "bridge/Sts2AgentBridge/successors/item_v1/native/PinnedItemV1NativeAdapter.cs",
        "bridge/Sts2AgentBridge/successors/item_wire_v1/producer/ItemWireV1Codec.cs",
        "bridge/Sts2AgentBridge/successors/item_wire_v1/producer/ItemWireV1Protocol.cs",
        "bridge/Sts2AgentBridge/successors/item_wire_v1/producer/ItemWireV1Service.cs",
    };
    private static int _checks;

    public static int Main(string[] args)
    {
        try
        {
            if (args.Length == 4 && args[0] == "--extract-policy")
            {
                Extract(args[1], args[2], args[3]);
                return 0;
            }
            if (args.Length != 6 || args[0] != "--candidate" ||
                args[2] != "--source-root" || args[4] != "--policy")
                throw new InvalidOperationException("invalid test invocation");
            Run(args[1], args[3], args[5]);
            Console.WriteLine(JsonSerializer.Serialize(new SortedDictionary<string, object>(StringComparer.Ordinal)
            {
                ["check_count"] = _checks,
                ["schema_version"] = 1,
                ["status"] = "passed",
                ["suite"] = "item_v1_release_verifier",
            }));
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"item_v1_release_verifier\"}");
            return 1;
        }
    }

    private static void Extract(string candidatePath, string sourceRoot, string outputPath)
    {
        byte[] candidate = SafeFiles.ReadBoundedRegularFile(candidatePath, 64 * 1024 * 1024, "candidate");
        ItemReleaseProjection projection = ItemReleaseProjectionBuilder.Build(candidate);
        ItemReleaseVerifier.VerifySemanticRules(projection);
        PolicySourceFile[] sources = ProductionSources.Select(path => new PolicySourceFile
        {
            Path = path,
            Sha256 = ItemReleaseProjectionBuilder.Sha(File.ReadAllBytes(Path.Combine(sourceRoot, path))),
        }).ToArray();
        string sourceProjection = SourceProjection(sources);
        if (sourceProjection != "131404a87a94800c1e9dbda3ef936abf44452befb5f41643b8b392cf6909ba88")
            throw new InvalidOperationException("source projection mismatch");
        var policy = new ItemReleasePolicy
        {
            SchemaVersion = 1,
            CandidateLength = projection.ArtifactLength,
            CandidateSha256 = projection.ArtifactSha256,
            SourceProjectionSha256 = sourceProjection,
            MetadataProjectionSha256 = projection.MetadataProjectionSha256,
            CheckedMethodBodies = projection.CheckedMethodBodies,
            SourceFiles = sources,
            MetadataInventory = projection.Inventory,
        };
        string json = JsonSerializer.Serialize(policy, new JsonSerializerOptions { WriteIndented = true }) + "\n";
        File.WriteAllText(outputPath, json, new UTF8Encoding(false));
    }

    private static void Run(string candidatePath, string sourceRoot, string policyPath)
    {
        byte[] candidate = File.ReadAllBytes(candidatePath);
        ItemReleasePolicy policy = ItemReleasePolicy.Parse(File.ReadAllBytes(policyPath));
        ItemReleaseProjection projection = ItemReleaseProjectionBuilder.Build(candidate);
        ItemReleaseVerifier.VerifySemanticRules(projection);
        Pass();
        ItemReleaseVerificationReport report = ItemReleaseVerifier.Verify(candidate, sourceRoot, policy, true);
        Check(report.AssemblySha256 == policy.CandidateSha256 &&
            report.SourceProjectionSha256 == policy.SourceProjectionSha256);

        Reject(() => ItemReleaseVerifier.VerifySemanticRules(projection with
        {
            Routes = new[] { "/probe/item-v1/public/item-action", "/probe/item-v1/public/item-decision", "/probe/v0/run" },
        }), "route_surface_forbidden");
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(projection with
        {
            ForbiddenReferences = new[] { "forbidden|owner|0|System.Diagnostics.Process.Start" },
        }), "runtime_surface_forbidden");
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(projection with
        {
            SensitiveReferences = Array.Empty<string>(),
        }), "test_seam_reachable");
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(projection with
        {
            SensitiveReferences = new[] { projection.SensitiveReferences[0], "sensitive|owner|0|0028|method:Sts2AgentBridge.Successors.ItemTransportV1.ItemTransportRuntime.IsAllowedTestEndpoint(System.Net.IPEndPoint)" },
        }), "test_seam_reachable");
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(projection with
        {
            NativeImports = projection.NativeImports[..^1],
        }), "native_import_surface");
        string[] changedNative = projection.NativeImports.ToArray();
        changedNative[0] = changedNative[0].Replace("/usr/lib/libSystem.B.dylib", "libc", StringComparison.Ordinal);
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(projection with
        {
            NativeImports = changedNative,
        }), "native_import_surface");

        var changedPolicy = CopyPolicy(policy);
        changedPolicy.MetadataInventory = policy.MetadataInventory[..^1];
        Reject(() => ItemReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "release_projection_mismatch");
        changedPolicy = CopyPolicy(policy);
        changedPolicy.CheckedMethodBodies++;
        Reject(() => ItemReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "release_projection_mismatch");
        byte[] malformed = candidate[..128];
        Reject(() => ItemReleaseProjectionBuilder.Build(malformed), "candidate_metadata_invalid", "candidate_pe_shape", "candidate_projection_invalid");

        byte[] routeMutation = candidate.ToArray();
        ReplaceAscii(routeMutation, "/probe/item-v1/public/item-decision", "/probe/item-v1/public/item-decisi0n");
        ItemReleaseProjection routeProjection = ItemReleaseProjectionBuilder.Build(routeMutation);
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(routeProjection), "route_surface_forbidden");

        byte[] nativeLastError = PeMutations.ChangeNativeFlags(candidate, callingConvention: false);
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(ItemReleaseProjectionBuilder.Build(nativeLastError)), "native_import_surface");
        byte[] nativeConvention = PeMutations.ChangeNativeFlags(candidate, callingConvention: true);
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(ItemReleaseProjectionBuilder.Build(nativeConvention)), "native_import_surface");
        byte[] incomingCall = PeMutations.RedirectInitializerCall(candidate);
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(ItemReleaseProjectionBuilder.Build(incomingCall)), "test_seam_reachable");
        byte[] functionPointer = PeMutations.RedirectFunctionPointer(candidate, useLoadToken: false);
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(ItemReleaseProjectionBuilder.Build(functionPointer)), "test_seam_reachable");
        byte[] loadToken = PeMutations.RedirectFunctionPointer(candidate, useLoadToken: true);
        Reject(() => ItemReleaseVerifier.VerifySemanticRules(ItemReleaseProjectionBuilder.Build(loadToken)), "test_seam_reachable");
        byte[] opcode = PeMutations.ChangeBenignOpcode(candidate);
        Reject(() => ItemReleaseVerifier.Verify(opcode, sourceRoot, policy, false), "release_projection_mismatch");
        byte[] memberReference = PeMutations.ChangeMemberReferenceName(candidate);
        Reject(() => ItemReleaseVerifier.Verify(memberReference, sourceRoot, policy, false),
            "release_projection_mismatch", "candidate_projection_invalid");
        ProductionReject(nativeConvention, sourceRoot, policyPath, "native_import_surface");
        ProductionReject(incomingCall, sourceRoot, policyPath, "test_seam_reachable");

        changedPolicy = CopyPolicy(policy);
        changedPolicy.SourceFiles = policy.SourceFiles[..^1];
        Reject(() => ItemReleasePolicy.Parse(Serialize(changedPolicy)), "policy_sources", "policy_invalid");
        changedPolicy = CopyPolicy(policy);
        changedPolicy.SourceFiles = policy.SourceFiles.Concat(new[]
        {
            new PolicySourceFile { Path = "extra.cs", Sha256 = new string('0', 64) },
        }).OrderBy(source => source.Path, StringComparer.Ordinal).ToArray();
        Reject(() => ItemReleasePolicy.Parse(Serialize(changedPolicy)), "policy_sources", "policy_invalid");
        changedPolicy = CopyPolicy(policy);
        changedPolicy.SourceFiles[0].Sha256 = new string('0', 64);
        Reject(() => ItemReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "source_hash_mismatch");

        string temp = Path.Combine("/private/tmp", "item-release-source-link-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temp);
        try
        {
            foreach (PolicySourceFile source in policy.SourceFiles)
            {
                string destination = Path.Combine(temp, source.Path);
                Directory.CreateDirectory(Path.GetDirectoryName(destination) ?? throw new InvalidOperationException());
                File.Copy(Path.Combine(sourceRoot, source.Path), destination);
            }
            string linked = Path.Combine(temp, policy.SourceFiles[0].Path);
            File.Delete(linked);
            File.CreateSymbolicLink(linked, Path.Combine(sourceRoot, policy.SourceFiles[0].Path));
            Reject(() => ItemReleaseVerifier.Verify(candidate, temp, policy, false), "source_boundary");
        }
        finally
        {
            Directory.Delete(temp, true);
        }

        byte[] invalidPolicy = File.ReadAllBytes(policyPath);
        invalidPolicy[0] = (byte)'[';
        Reject(() => ItemReleasePolicy.Parse(invalidPolicy), "policy_invalid");
        ProductionPolicyReject(candidatePath, sourceRoot, invalidPolicy);
        changedPolicy = CopyPolicy(policy);
        changedPolicy.CandidateSha256 = new string('0', 64);
        Reject(() => ItemReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, true), "candidate_identity_mismatch");
        changedPolicy = CopyPolicy(policy);
        int body = Array.FindIndex(changedPolicy.MetadataInventory, value => value.StartsWith("body|", StringComparison.Ordinal));
        changedPolicy.MetadataInventory[body] += "0";
        Array.Sort(changedPolicy.MetadataInventory, StringComparer.Ordinal);
        Reject(() => ItemReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "release_projection_mismatch");
        changedPolicy = CopyPolicy(policy);
        int member = Array.FindIndex(changedPolicy.MetadataInventory, value => value.StartsWith("member_ref|", StringComparison.Ordinal));
        changedPolicy.MetadataInventory[member] += "0";
        Array.Sort(changedPolicy.MetadataInventory, StringComparer.Ordinal);
        Reject(() => ItemReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "release_projection_mismatch");
        ParentSymlinkReject(candidate, sourceRoot, policyPath);
    }

    private static ItemReleasePolicy CopyPolicy(ItemReleasePolicy source) => new()
    {
        SchemaVersion = source.SchemaVersion,
        CandidateLength = source.CandidateLength,
        CandidateSha256 = source.CandidateSha256,
        SourceProjectionSha256 = source.SourceProjectionSha256,
        MetadataProjectionSha256 = source.MetadataProjectionSha256,
        CheckedMethodBodies = source.CheckedMethodBodies,
        SourceFiles = source.SourceFiles.Select(file => new PolicySourceFile { Path = file.Path, Sha256 = file.Sha256 }).ToArray(),
        MetadataInventory = source.MetadataInventory.ToArray(),
    };

    private static byte[] Serialize(ItemReleasePolicy policy) =>
        Encoding.UTF8.GetBytes(JsonSerializer.Serialize(policy));

    private static void ProductionReject(byte[] candidate, string sourceRoot, string policyPath, string code)
    {
        string temp = Path.Combine("/private/tmp", "item-release-mutated-" + Guid.NewGuid().ToString("N") + ".dll");
        File.WriteAllBytes(temp, candidate);
        try
        {
            (int exit, string output) = InvokeProduction(temp, sourceRoot, policyPath);
            Check(exit == 4 && output.Contains("\"code\":\"" + code + "\"", StringComparison.Ordinal));
        }
        finally { File.Delete(temp); }
    }

    private static void ProductionPolicyReject(string candidatePath, string sourceRoot, byte[] policy)
    {
        string temp = Path.Combine("/private/tmp", "item-release-policy-" + Guid.NewGuid().ToString("N") + ".json");
        File.WriteAllBytes(temp, policy);
        try
        {
            (int exit, string output) = InvokeProduction(candidatePath, sourceRoot, temp);
            Check(exit == 4 && output.Contains("\"code\":\"policy_identity_mismatch\"", StringComparison.Ordinal));
        }
        finally { File.Delete(temp); }
    }

    private static (int Exit, string Output) InvokeProduction(string candidate, string sourceRoot, string policy)
    {
        TextWriter prior = Console.Out;
        using var output = new StringWriter();
        try
        {
            Console.SetOut(output);
            int exit = Sts2AgentBridge.Verifier.Program.Main(new[]
            {
                "--assembly", candidate, "--source-root", sourceRoot, "--policy", policy,
            });
            return (exit, output.ToString());
        }
        finally { Console.SetOut(prior); }
    }

    private static void ParentSymlinkReject(byte[] candidate, string sourceRoot, string policyPath)
    {
        string root = Path.Combine("/private/tmp", "item-release-parent-link-" + Guid.NewGuid().ToString("N"));
        string real = Path.Combine(root, "real");
        string alias = Path.Combine(root, "alias");
        Directory.CreateDirectory(real);
        File.WriteAllBytes(Path.Combine(real, "candidate.dll"), candidate);
        Directory.CreateSymbolicLink(alias, real);
        try
        {
            (int exit, string output) = InvokeProduction(Path.Combine(alias, "candidate.dll"), sourceRoot, policyPath);
            Check(exit == 3 && output.Contains("\"code\":\"candidate_boundary\"", StringComparison.Ordinal));
        }
        finally { Directory.Delete(root, true); }
    }

    private static string SourceProjection(IEnumerable<PolicySourceFile> files)
    {
        string value = string.Concat(files.Select(file => file.Sha256 + "  ./" + file.Path + "\n"));
        return ItemReleaseProjectionBuilder.Sha(Encoding.UTF8.GetBytes(value));
    }

    private static void ReplaceAscii(byte[] bytes, string oldValue, string newValue)
    {
        byte[] oldBytes = Encoding.ASCII.GetBytes(oldValue);
        byte[] newBytes = Encoding.ASCII.GetBytes(newValue);
        if (oldBytes.Length != newBytes.Length) throw new InvalidOperationException();
        int found = -1;
        for (int index = 0; index <= bytes.Length - oldBytes.Length; index++)
        {
            if (!bytes.AsSpan(index, oldBytes.Length).SequenceEqual(oldBytes)) continue;
            if (found >= 0) throw new InvalidOperationException("duplicate literal");
            found = index;
        }
        if (found < 0) throw new InvalidOperationException("literal absent");
        newBytes.CopyTo(bytes, found);
    }

    private static void Pass() => _checks++;

    private static void Check(bool value)
    {
        if (!value) throw new InvalidOperationException("check failed");
        Pass();
    }

    private static void Reject(Action action, params string[] codes)
    {
        try { action(); }
        catch (VerificationException exception) when (codes.Contains(exception.Code, StringComparer.Ordinal)) { Pass(); return; }
        catch (BoundaryException exception) when (codes.Contains(exception.Code, StringComparer.Ordinal)) { Pass(); return; }
        throw new InvalidOperationException("expected rejection after check " + _checks);
    }
}
