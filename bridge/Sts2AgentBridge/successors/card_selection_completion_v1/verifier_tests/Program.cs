using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal static class Program
{
    // Exact sorted closure of the explicit production Compile items. Hash and
    // artifact pins are finalized only after the implementation source freezes.
    private static readonly string[] ProductionSources =
    {
        "bridge/Sts2AgentBridge/successors/card_selection_completion_v1/native/PinnedCardSelectionV1NativeAdapter.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/lifecycle/CardSelectionBootstrapLifecycle.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/native/CardSelectionBootstrapHost.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/native/CardSelectionBootstrapSupport.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/native/CardSelectionGodotFrameConnector.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/native/CardSelectionModEntry.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/native/ConfiguredCardSelectionParentV1NativeAdapter.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/native/ProductionCardSelectionRuntimeFactory.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/operator/CardSelectionOperatorFiles.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/runtime/CardSelectionTransportConfiguration.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/runtime/CardSelectionTransportContracts.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/runtime/CardSelectionTransportProtocol.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/runtime/CardSelectionTransportRuntime.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_release_v1/runtime/OwnedByteFrameQueue.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/core/CardSelectionV1Contracts.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/core/CardSelectionV1Session.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/native/CardSelectionV1NativeRules.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/parent_native/CardSelectionParentV1NativeRules.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/parent_native/PinnedCardSelectionParentV1NativeAdapter.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/parents/CardSelectionParentV1Contracts.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/parents/CardSelectionParentV1Session.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/wire/CardSelectionV1WireCodec.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/wire/CardSelectionV1WireProtocol.cs",
        "bridge/Sts2AgentBridge/successors/card_selection_v1/wire/CardSelectionV1WireService.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/native/PinnedItemBuildGuard.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/operator/DarwinReadOnly.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/operator/ItemOperatorConfiguration.cs",
        "bridge/Sts2AgentBridge/successors/item_bootstrap_v1/operator/ItemPinnedFileIdentity.cs",
        "bridge/Sts2AgentBridge/successors/item_transport_v1/runtime/kernel/FixedTimeAuthenticator.cs",
        "bridge/Sts2AgentBridge/successors/item_transport_v1/runtime/kernel/MonotonicTokenBucket.cs",
    };
    private const string ExpectedSourceProjectionSha256 =
        "4c6c3fc0b09d3e49de3390d8fc52308b2b7a170d7852ccec2d61c5e129337510";
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
                ["suite"] = "card_selection_v1_release_verifier",
            }));
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"card_selection_v1_release_verifier\"}");
            return 1;
        }
    }

    private static void Extract(string candidatePath, string sourceRoot, string outputPath)
    {
        byte[] candidate = SafeFiles.ReadBoundedRegularFile(candidatePath, 64 * 1024 * 1024, "candidate");
        CardSelectionReleaseProjection projection = CardSelectionReleaseProjectionBuilder.Build(candidate);
        CardSelectionReleaseVerifier.VerifySemanticRules(projection);
        PolicySourceFile[] sources = ProductionSources.Select(path => new PolicySourceFile
        {
            Path = path,
            Sha256 = CardSelectionReleaseProjectionBuilder.Sha(File.ReadAllBytes(Path.Combine(sourceRoot, path))),
        }).ToArray();
        string sourceProjection = SourceProjection(sources);
        if (sourceProjection != ExpectedSourceProjectionSha256)
            throw new InvalidOperationException("source projection mismatch");
        var policy = new CardSelectionReleasePolicy
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
        string json = JsonSerializer.Serialize(policy) + "\n";
        File.WriteAllText(outputPath, json, new UTF8Encoding(false));
    }

    private static void Run(string candidatePath, string sourceRoot, string policyPath)
    {
        byte[] candidate = File.ReadAllBytes(candidatePath);
        CardSelectionReleasePolicy policy = CardSelectionReleasePolicy.Parse(File.ReadAllBytes(policyPath));
        CardSelectionReleaseProjection projection = CardSelectionReleaseProjectionBuilder.Build(candidate);
        CardSelectionReleaseVerifier.VerifySemanticRules(projection);
        Pass();
        CardSelectionReleaseVerificationReport report = CardSelectionReleaseVerifier.Verify(candidate, sourceRoot, policy, true);
        Check(report.AssemblySha256 == policy.CandidateSha256 &&
            report.SourceProjectionSha256 == policy.SourceProjectionSha256);

        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            AssemblyName = "Sts2AgentBridgeCardSelectionV0",
        }), "assembly_identity_forbidden");

        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            Routes = projection.Routes.Concat(new[] { "/card-selection-v1/unknown" })
                .OrderBy(value => value, StringComparer.Ordinal).ToArray(),
        }), "route_surface_forbidden");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            RequestLines = projection.RequestLines[..^1],
        }), "request_line_surface_forbidden");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            ForbiddenReferences = new[] { "forbidden|owner|0|System.Diagnostics.Process.Start" },
        }), "runtime_surface_forbidden");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            SensitiveReferences = new[] { "sensitive|owner|0|0028|method:Type.Synthetic()" },
        }), "test_seam_reachable");
        string[] orphanedToken = projection.Inventory.ToArray();
        int parameterRow = Array.FindIndex(orphanedToken,
            value => value.StartsWith("parameter|", StringComparison.Ordinal));
        if (parameterRow < 0) throw new InvalidOperationException("parameter row absent");
        string[] parameterFields = orphanedToken[parameterRow].Split('|');
        parameterFields[1] = "06ffffff";
        orphanedToken[parameterRow] = string.Join('|', parameterFields);
        Array.Sort(orphanedToken, StringComparer.Ordinal);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            Inventory = orphanedToken,
        }), "metadata_token_linkage");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            CriticalReferences = projection.CriticalReferences[..^1],
        }), "critical_flow_forbidden");
        string[] changedCritical = projection.CriticalReferences.ToArray();
        int factoryEdge = Array.FindIndex(changedCritical, value => value.Contains(
            "ProductionCardSelectionRuntimeFactory", StringComparison.Ordinal));
        if (factoryEdge < 0) throw new InvalidOperationException("factory edge absent");
        changedCritical[factoryEdge] = changedCritical[factoryEdge].Replace(
            "ProductionCardSelectionRuntimeFactory", "UnselectedCardSelectionRuntimeFactory",
            StringComparison.Ordinal);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            CriticalReferences = changedCritical,
        }), "critical_flow_forbidden");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            NativeImports = projection.NativeImports[..^1],
        }), "native_import_surface");
        string[] changedNative = projection.NativeImports.ToArray();
        changedNative[0] = changedNative[0].Replace("/usr/lib/libSystem.B.dylib", "libc", StringComparison.Ordinal);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            NativeImports = changedNative,
        }), "native_import_surface");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            InitializerAttributes = projection.InitializerAttributes.Concat(new[]
            {
                "method:Unexpected.Initialize()|System.Runtime.CompilerServices.ModuleInitializerAttribute..ctor()|01000000",
            }).OrderBy(value => value, StringComparer.Ordinal).ToArray(),
        }), "initializer_or_friend_surface");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(projection with
        {
            Inventory = projection.Inventory.Concat(new[]
            {
                "method_def|06ffffff|Sts2AgentBridge.Successors.CardSelectionReleaseV1.CardSelectionModEntry.Initialize(System.String)|System.Void|0|1|0|150|0",
            }).OrderBy(value => value, StringComparer.Ordinal).ToArray(),
        }), "initializer_or_friend_surface");

        var changedPolicy = CopyPolicy(policy);
        changedPolicy.MetadataInventory = policy.MetadataInventory[..^1];
        Reject(() => CardSelectionReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "release_projection_mismatch");
        changedPolicy = CopyPolicy(policy);
        changedPolicy.CheckedMethodBodies++;
        Reject(() => CardSelectionReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "release_projection_mismatch");
        byte[] malformed = candidate[..128];
        Reject(() => CardSelectionReleaseProjectionBuilder.Build(malformed), "candidate_metadata_invalid", "candidate_pe_shape", "candidate_projection_invalid");

        var requestLineMutations = new List<byte[]>();
        foreach ((string expected, string replacement) in new[]
        {
            ("GET /card-selection-v1/child HTTP/1.1", "GET /card-selection-v1/chil0 HTTP/1.1"),
            ("GET /card-selection-v1/parent HTTP/1.1", "GET /card-selection-v1/paren0 HTTP/1.1"),
            ("POST /card-selection-v1/child/action HTTP/1.1", "POST /card-selection-v1/child/actio0 HTTP/1.1"),
            ("POST /card-selection-v1/parent/action HTTP/1.1", "POST /card-selection-v1/parent/actio0 HTTP/1.1"),
        })
        {
            byte[] mutation = candidate.ToArray();
            ReplaceAscii(mutation, expected, replacement);
            requestLineMutations.Add(mutation);
            Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(
                CardSelectionReleaseProjectionBuilder.Build(mutation)), "request_line_surface_forbidden");
        }

        byte[] nativeLastError = PeMutations.ChangeNativeFlags(candidate, callingConvention: false);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(CardSelectionReleaseProjectionBuilder.Build(nativeLastError)), "native_import_surface");
        byte[] nativeConvention = PeMutations.ChangeNativeFlags(candidate, callingConvention: true);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(CardSelectionReleaseProjectionBuilder.Build(nativeConvention)), "native_import_surface");
        byte[] testName = PeMutations.ChangeMethodNameToSynthetic(candidate);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(CardSelectionReleaseProjectionBuilder.Build(testName)),
            "test_seam_reachable", "test_seam_shape");
        byte[] initializer = PeMutations.ChangeInitializerAttributeName(candidate);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(CardSelectionReleaseProjectionBuilder.Build(initializer)), "initializer_or_friend_surface");
        byte[] forbiddenReference = PeMutations.ChangeCalledTypeNamespaceToReflection(candidate);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(CardSelectionReleaseProjectionBuilder.Build(forbiddenReference)), "runtime_surface_forbidden");
        byte[] assemblyDefinition = PeMutations.ChangeAssemblyDefinitionName(candidate);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(
            CardSelectionReleaseProjectionBuilder.Build(assemblyDefinition)), "assembly_identity_forbidden");
        byte[] wrapperBypass = PeMutations.ChangeCriticalTypeName(
            candidate, "ConfiguredCardSelectionParentV1NativeAdapter");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(
            CardSelectionReleaseProjectionBuilder.Build(wrapperBypass)), "critical_flow_forbidden");
        byte[] frameBypass = PeMutations.ChangeCriticalTypeName(
            candidate, "CardSelectionV1WireService");
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(
            CardSelectionReleaseProjectionBuilder.Build(frameBypass)), "critical_flow_forbidden");
        byte[] configuredAdapterBypass = PeMutations.ChangeFactorySessionAdapterLocal(candidate);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(
            CardSelectionReleaseProjectionBuilder.Build(configuredAdapterBypass)), "critical_flow_forbidden");
        byte[] submittedCallbackBypass = PeMutations.ChangeSubmittedCallbackTarget(candidate);
        Reject(() => CardSelectionReleaseVerifier.VerifySemanticRules(
            CardSelectionReleaseProjectionBuilder.Build(submittedCallbackBypass)), "critical_flow_forbidden");
        byte[] opcode = PeMutations.ChangeBenignOpcode(candidate);
        Reject(() => CardSelectionReleaseVerifier.Verify(opcode, sourceRoot, policy, false), "release_projection_mismatch");
        byte[] memberReference = PeMutations.ChangeMemberReferenceName(candidate);
        Reject(() => CardSelectionReleaseVerifier.Verify(memberReference, sourceRoot, policy, false),
            "release_projection_mismatch", "candidate_projection_invalid");
        byte[] assemblyReference = PeMutations.ChangeAssemblyReferenceName(candidate);
        Reject(() => CardSelectionReleaseVerifier.Verify(assemblyReference, sourceRoot, policy, false),
            "release_projection_mismatch", "candidate_projection_invalid");
        ProductionReject(nativeConvention, sourceRoot, policyPath, "native_import_surface");
        ProductionReject(testName, sourceRoot, policyPath, "test_seam_reachable", "test_seam_shape");
        ProductionReject(initializer, sourceRoot, policyPath, "initializer_or_friend_surface");
        ProductionReject(forbiddenReference, sourceRoot, policyPath, "runtime_surface_forbidden");
        ProductionReject(assemblyDefinition, sourceRoot, policyPath, "assembly_identity_forbidden");
        ProductionReject(wrapperBypass, sourceRoot, policyPath, "critical_flow_forbidden");
        ProductionReject(frameBypass, sourceRoot, policyPath, "critical_flow_forbidden");
        ProductionReject(configuredAdapterBypass, sourceRoot, policyPath, "critical_flow_forbidden");
        ProductionReject(submittedCallbackBypass, sourceRoot, policyPath, "critical_flow_forbidden");
        foreach (byte[] mutation in requestLineMutations)
            ProductionReject(mutation, sourceRoot, policyPath, "request_line_surface_forbidden");

        changedPolicy = CopyPolicy(policy);
        changedPolicy.SourceFiles = policy.SourceFiles[..^1];
        Reject(() => CardSelectionReleasePolicy.Parse(Serialize(changedPolicy)), "policy_sources", "policy_invalid");
        changedPolicy = CopyPolicy(policy);
        changedPolicy.SourceFiles = policy.SourceFiles.Concat(new[]
        {
            new PolicySourceFile { Path = "extra.cs", Sha256 = new string('0', 64) },
        }).OrderBy(source => source.Path, StringComparer.Ordinal).ToArray();
        Reject(() => CardSelectionReleasePolicy.Parse(Serialize(changedPolicy)), "policy_sources", "policy_invalid");
        changedPolicy = CopyPolicy(policy);
        changedPolicy.SourceFiles[0].Sha256 = new string('0', 64);
        Reject(() => CardSelectionReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "source_hash_mismatch");

        string temp = Path.Combine("/private/tmp", "card-selection-release-source-link-" + Guid.NewGuid().ToString("N"));
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
            Reject(() => CardSelectionReleaseVerifier.Verify(candidate, temp, policy, false), "source_boundary");
        }
        finally
        {
            Directory.Delete(temp, true);
        }

        byte[] invalidPolicy = File.ReadAllBytes(policyPath);
        invalidPolicy[0] = (byte)'[';
        Reject(() => CardSelectionReleasePolicy.Parse(invalidPolicy), "policy_invalid");
        ProductionPolicyReject(candidatePath, sourceRoot, invalidPolicy);
        changedPolicy = CopyPolicy(policy);
        changedPolicy.CandidateSha256 = new string('0', 64);
        Reject(() => CardSelectionReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, true), "candidate_identity_mismatch");
        changedPolicy = CopyPolicy(policy);
        int body = Array.FindIndex(changedPolicy.MetadataInventory, value => value.StartsWith("body|", StringComparison.Ordinal));
        changedPolicy.MetadataInventory[body] += "0";
        Array.Sort(changedPolicy.MetadataInventory, StringComparer.Ordinal);
        Reject(() => CardSelectionReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "release_projection_mismatch");
        changedPolicy = CopyPolicy(policy);
        int member = Array.FindIndex(changedPolicy.MetadataInventory, value => value.StartsWith("member_ref|", StringComparison.Ordinal));
        changedPolicy.MetadataInventory[member] += "0";
        Array.Sort(changedPolicy.MetadataInventory, StringComparer.Ordinal);
        Reject(() => CardSelectionReleaseVerifier.Verify(candidate, sourceRoot, changedPolicy, false), "release_projection_mismatch");
        ParentSymlinkReject(candidate, sourceRoot, policyPath);
    }

    private static CardSelectionReleasePolicy CopyPolicy(CardSelectionReleasePolicy source) => new()
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

    private static byte[] Serialize(CardSelectionReleasePolicy policy) =>
        Encoding.UTF8.GetBytes(JsonSerializer.Serialize(policy));

    private static void ProductionReject(
        byte[] candidate,
        string sourceRoot,
        string policyPath,
        params string[] codes)
    {
        string temp = Path.Combine("/private/tmp", "card-selection-release-mutated-" + Guid.NewGuid().ToString("N") + ".dll");
        File.WriteAllBytes(temp, candidate);
        try
        {
            (int exit, string output) = InvokeProduction(temp, sourceRoot, policyPath);
            Check(exit == 4 && codes.Any(code =>
                output.Contains("\"code\":\"" + code + "\"", StringComparison.Ordinal)));
        }
        finally { File.Delete(temp); }
    }

    private static void ProductionPolicyReject(string candidatePath, string sourceRoot, byte[] policy)
    {
        string temp = Path.Combine("/private/tmp", "card-selection-release-policy-" + Guid.NewGuid().ToString("N") + ".json");
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
            int exit = Sts2AgentBridge.Successors.CardSelectionReleaseV1.Program.Main(new[]
            {
                "--assembly", candidate, "--source-root", sourceRoot, "--policy", policy,
            });
            return (exit, output.ToString());
        }
        finally { Console.SetOut(prior); }
    }

    private static void ParentSymlinkReject(byte[] candidate, string sourceRoot, string policyPath)
    {
        string root = Path.Combine("/private/tmp", "card-selection-release-parent-link-" + Guid.NewGuid().ToString("N"));
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
        return CardSelectionReleaseProjectionBuilder.Sha(Encoding.UTF8.GetBytes(value));
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
