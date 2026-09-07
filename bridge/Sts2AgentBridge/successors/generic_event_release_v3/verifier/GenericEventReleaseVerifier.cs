using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV3;

internal sealed record GenericEventReleaseVerificationReport(
    string AssemblySha256,
    string SourceProjectionSha256,
    string MetadataProjectionSha256,
    int CheckedMethodBodies);

internal static class GenericEventReleaseVerifier
{
    private const string ExpectedAssemblyName = "Sts2AgentBridgeGenericEventV3";
    private const string ExpectedAssemblyVersion = "1.0.0.0";
    private static readonly string[] ExpectedRoutes =
    {
        "/probe/generic-event-v3/public/action",
        "/probe/generic-event-v3/public/decision",
    };
    private static readonly string[] ExpectedRequestLines =
    {
        "GET /probe/generic-event-v3/public/decision HTTP/1.1",
        "POST /probe/generic-event-v3/public/action HTTP/1.1",
    };
    private static readonly HashSet<string> ExpectedNativeNames = new(StringComparer.Ordinal)
    {
        "getuid", "geteuid", "getpwuid_r", "open", "openat", "fstat", "fstatat",
        "read", "close", "acl_get_fd_np", "acl_get_entry", "acl_get_tag_type", "acl_free",
    };
    private const string ExpectedInitializer =
        "type:Sts2AgentBridge.Successors.GenericEventReleaseV3.GenericEventModEntry|" +
        "MegaCrit.Sts2.Core.Modding.ModInitializerAttribute..ctor(System.String)|" +
        "01000a496e697469616c697a650000";
    private const string ExpectedEntryType =
        "type_def|Sts2AgentBridge.Successors.GenericEventReleaseV3.GenericEventModEntry|1048961|System.Object|0|0";
    private const string ExpectedEntryMethodSuffix =
        "|Sts2AgentBridge.Successors.GenericEventReleaseV3.GenericEventModEntry.Initialize()|System.Void|0|0|0|150|0";

    internal static GenericEventReleaseVerificationReport Verify(
        byte[] candidate,
        string sourceRoot,
        GenericEventReleasePolicy policy,
        bool enforceArtifactIdentity)
    {
        GenericEventReleaseProjection projection = GenericEventReleaseProjectionBuilder.Build(candidate);
        VerifySemanticRules(projection);
        string sourceProjection = VerifySources(sourceRoot, policy.SourceFiles);
        if (projection.AssemblyName != ExpectedAssemblyName ||
            projection.AssemblyVersion != ExpectedAssemblyVersion ||
            projection.CheckedMethodBodies != policy.CheckedMethodBodies ||
            projection.MetadataProjectionSha256 != policy.MetadataProjectionSha256 ||
            !projection.Inventory.SequenceEqual(policy.MetadataInventory, StringComparer.Ordinal) ||
            sourceProjection != policy.SourceProjectionSha256)
        {
            throw new VerificationException("release_projection_mismatch");
        }
        if (enforceArtifactIdentity &&
            (projection.ArtifactLength != policy.CandidateLength ||
             projection.ArtifactSha256 != policy.CandidateSha256))
        {
            throw new VerificationException("candidate_identity_mismatch");
        }
        return new GenericEventReleaseVerificationReport(
            projection.ArtifactSha256,
            sourceProjection,
            projection.MetadataProjectionSha256,
            projection.CheckedMethodBodies);
    }

    internal static void VerifySemanticRules(GenericEventReleaseProjection projection)
    {
        if (projection.AssemblyName != ExpectedAssemblyName ||
            projection.AssemblyVersion != ExpectedAssemblyVersion)
        {
            throw new VerificationException("assembly_identity_forbidden");
        }
        if (!projection.Routes.SequenceEqual(ExpectedRoutes, StringComparer.Ordinal))
        {
            throw new VerificationException("route_surface_forbidden");
        }
        if (!projection.RequestLines.SequenceEqual(ExpectedRequestLines, StringComparer.Ordinal))
        {
            throw new VerificationException("request_line_surface_forbidden");
        }
        if (projection.ForbiddenReferences.Length != 0)
        {
            throw new VerificationException("runtime_surface_forbidden");
        }
        if (projection.SensitiveReferences.Length != 0)
        {
            throw new VerificationException("test_seam_reachable");
        }
        if (projection.Inventory.Any(row => row.StartsWith("resource|", StringComparison.Ordinal) ||
            row.StartsWith("file|", StringComparison.Ordinal) || row.StartsWith("exported_type|", StringComparison.Ordinal)))
            throw new VerificationException("additional_payload_forbidden");
        VerifyMethodTokenLinks(projection.Inventory, projection.CheckedMethodBodies);
        VerifyCriticalFlow(projection.CriticalReferences, projection.Inventory);
        GenericEventDiagnosticSurface.Verify(projection.Inventory, projection.CriticalReferences);
        string[] native = projection.NativeImports;
        if (native.Length != 13)
        {
            throw new VerificationException("native_import_surface");
        }
        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (string row in native)
        {
            string[] fields = row.Split('|');
            if (fields.Length != 5 ||
                !fields[1].StartsWith(
                    "Sts2AgentBridge.Successors.ItemBootstrapV1.LibSystemDarwinReadOnlyNative.Native",
                    StringComparison.Ordinal) ||
                fields[2] != "/usr/lib/libSystem.B.dylib" ||
                !ExpectedNativeNames.Contains(fields[3]) || !names.Add(fields[3]) ||
                !int.TryParse(fields[4], out int attributes) ||
                !HasExpectedImportFlags(fields[3], attributes))
            {
                throw new VerificationException("native_import_surface");
            }
        }
        if (!names.SetEquals(ExpectedNativeNames))
        {
            throw new VerificationException("native_import_surface");
        }
        if (!projection.InitializerAttributes.SequenceEqual(new[] { ExpectedInitializer }, StringComparer.Ordinal) ||
            !projection.Inventory.Contains(ExpectedEntryType, StringComparer.Ordinal) ||
            projection.Inventory.Count(value => value.StartsWith("method_def|", StringComparison.Ordinal) &&
                value.EndsWith(ExpectedEntryMethodSuffix, StringComparison.Ordinal)) != 1 ||
            projection.Inventory.Count(value => value.StartsWith(
                "method_def|", StringComparison.Ordinal) && value.Contains(
                "|Sts2AgentBridge.Successors.GenericEventReleaseV3.GenericEventModEntry.",
                StringComparison.Ordinal)) != 1 ||
            projection.Inventory.Any(value =>
            value.StartsWith("attribute|", StringComparison.Ordinal) &&
            value.Contains("System.Runtime.CompilerServices.InternalsVisibleToAttribute", StringComparison.Ordinal)))
        {
            throw new VerificationException("initializer_or_friend_surface");
        }
        string[] testNamed = projection.Inventory.Where(value =>
            value.StartsWith("method_def|", StringComparison.Ordinal) &&
            (value.Contains("ForTests(", StringComparison.Ordinal) ||
             value.Contains("Synthetic", StringComparison.Ordinal) ||
             value.Contains("IsAllowedTestEndpoint(", StringComparison.Ordinal))).ToArray();
        if (testNamed.Length != 0)
        {
            throw new VerificationException("test_seam_shape");
        }
    }

    private static void VerifyMethodTokenLinks(string[] inventory, int checkedBodies)
    {
        var methods = new HashSet<string>(StringComparer.Ordinal);
        foreach (string row in inventory.Where(value => value.StartsWith("method_def|", StringComparison.Ordinal)))
        {
            string[] fields = row.Split('|');
            if (fields.Length != 9 || !IsMethodToken(fields[1]) || !methods.Add(fields[1]))
                throw new VerificationException("metadata_token_linkage");
        }
        var bodies = new HashSet<string>(StringComparer.Ordinal);
        foreach (string row in inventory.Where(value => value.StartsWith("body|", StringComparison.Ordinal)))
        {
            string[] fields = row.Split('|');
            if (fields.Length != 3 || !methods.Contains(fields[1]) ||
                !GenericEventReleasePolicy.IsSha(fields[2]) || !bodies.Add(fields[1]))
                throw new VerificationException("metadata_token_linkage");
        }
        if (bodies.Count != checkedBodies)
            throw new VerificationException("metadata_token_linkage");
        foreach (string row in inventory.Where(value => value.StartsWith("parameter|", StringComparison.Ordinal)))
        {
            string[] fields = row.Split('|');
            if (fields.Length != 5 || !methods.Contains(fields[1]))
                throw new VerificationException("metadata_token_linkage");
        }
    }

    private static bool IsMethodToken(string value) =>
        value.Length == 8 && value.StartsWith("06", StringComparison.Ordinal) &&
        value.All(character => character is >= '0' and <= '9' or >= 'a' and <= 'f');

    private static void VerifyCriticalFlow(string[] references, string[] inventory)
    {
        if (references.Length != 9)
        {
            throw new VerificationException("critical_flow_forbidden");
        }
        const string guardedFactory = "Sts2AgentBridge.Successors.GenericEventReleaseV3.ProductionGenericEventRuntimeFactory.CreateService(Sts2AgentBridge.Successors.GenericEventReleaseV3.GenericEventReleaseSelection,System.String,Sts2AgentBridge.Successors.GenericEventReleaseV3.ProductionGenericEventRuntimeFactory+Runtime)";
        string[] guards = references.Where(value => Target(value).Contains(".PinnedGenericEventHarmonyGuard.Verify(", StringComparison.Ordinal)).ToArray();
        string[] entries = references.Where(value => Target(value).Contains(".ProductionGenericEventRuntimeFactory.CreateVerifiedService(", StringComparison.Ordinal)).ToArray();
        if (guards.Length != 1 || entries.Length != 1 || Owner(guards[0]) != guardedFactory ||
            Owner(entries[0]) != guardedFactory || Opcode(guards[0]) != 0x0028 ||
            Opcode(entries[0]) != 0x0028 || Offset(guards[0]) >= Offset(entries[0]))
            throw new VerificationException("critical_flow_forbidden");
        string factory = "critical|Sts2AgentBridge.Successors.GenericEventReleaseV3.ProductionGenericEventRuntimeFactory.CreateVerifiedService(";
        string runtime = "critical|Sts2AgentBridge.Successors.GenericEventReleaseV3.GenericEventTransportRuntime+";
        string[] construction = references.Where(value => value.StartsWith(factory, StringComparison.Ordinal) && Target(value).Contains("..ctor(",StringComparison.Ordinal)).ToArray();
        string[] dispatch = references.Where(value => value.StartsWith(runtime, StringComparison.Ordinal) &&
            Target(value).Contains(".GenericEventV3WireService.Handle(", StringComparison.Ordinal)).ToArray();
        string[] submissions = references.Where(value =>
            Target(value).Contains(".OwnedByteFrameQueue.Submit(", StringComparison.Ordinal)).ToArray();
        string[] callbacks = references.Where(value =>
            Target(value).Contains(".<HandleSocketAsync>b__", StringComparison.Ordinal)).ToArray();
        if (construction.Length != 3 || dispatch.Length != 1 || submissions.Length != 1 || callbacks.Length != 1 ||
            construction.Count(value => Target(value).Contains(".PinnedGenericEventV3NativeAdapter..ctor(", StringComparison.Ordinal)) != 1 ||
            construction.Count(value => Target(value).Contains(".GenericEventV3Session..ctor(", StringComparison.Ordinal)) != 1 ||
            construction.Count(value => Target(value).Contains(".GenericEventV3WireService..ctor(", StringComparison.Ordinal)) != 1)
        {
            throw new VerificationException("critical_flow_forbidden");
        }
        int pinned = Offset(construction.Single(value => Target(value).Contains(
            ".PinnedGenericEventV3NativeAdapter..ctor(", StringComparison.Ordinal)));
        int session = Offset(construction.Single(value => Target(value).Contains(
            ".GenericEventV3Session..ctor(", StringComparison.Ordinal)));
        int service = Offset(construction.Single(value => Target(value).Contains(
            ".GenericEventV3WireService..ctor(", StringComparison.Ordinal)));
        string pinnedRow = construction.Single(value => Target(value).Contains(
            ".PinnedGenericEventV3NativeAdapter..ctor(", StringComparison.Ordinal));
        string sessionRow = construction.Single(value => Target(value).Contains(
            ".GenericEventV3Session..ctor(", StringComparison.Ordinal));
        string serviceRow = construction.Single(value => Target(value).Contains(
            ".GenericEventV3WireService..ctor(", StringComparison.Ordinal));
        if (!(pinned < session && session < service) ||
            Opcode(pinnedRow) != 0x0073 ||
            Opcode(sessionRow) != 0x0073 || Opcode(serviceRow) != 0x0073 ||
            OutputLocal(pinnedRow) < 0 ||
            OutputLocal(sessionRow) < 0 || InputLocal(serviceRow) != OutputLocal(sessionRow))
        {
            throw new VerificationException("critical_flow_forbidden");
        }
        string[] bindings = references.Where(value => Target(value).Contains(".BindDiagnostic(",StringComparison.Ordinal)).ToArray();
        string[][] aliases = inventory.Where(value => value.StartsWith("construction_alias|",StringComparison.Ordinal)).Select(value => value.Split('|')).ToArray();
        if (bindings.Length != 1 || Owner(bindings[0]) != Owner(pinnedRow) ||
            Opcode(bindings[0]) is not (0x0028 or 0x006f) || InputLocal(bindings[0]) != OutputLocal(pinnedRow) ||
            !(pinned < Offset(bindings[0]) && Offset(bindings[0]) < session) || aliases.Length != 1 ||
            aliases[0].Length != 5 || aliases[0][1] != Owner(pinnedRow) ||
            !int.TryParse(aliases[0][2],out int aliasOffset) || !(pinned < aliasOffset && aliasOffset < Offset(bindings[0])) ||
            !int.TryParse(aliases[0][3],out int aliasInput) || aliasInput != OutputLocal(pinnedRow) ||
            !int.TryParse(aliases[0][4],out int aliasOutput) || aliasOutput != InputLocal(sessionRow))
            throw new VerificationException("critical_flow_forbidden");
        string callback = callbacks[0];
        string submission = submissions[0];
        string handle = dispatch[0];
        if (Opcode(callback) != 0xfe06 || Owner(callback) != Owner(submission) ||
            Offset(callback) >= Offset(submission) || Target(callback) != "method:" + Owner(handle) ||
            NextOpcode(callback) != 0x0073 ||
            !NextTarget(callback).StartsWith("member:System.Func<", StringComparison.Ordinal) ||
            !NextTarget(callback).Contains("..ctor(System.Object,System.IntPtr)", StringComparison.Ordinal) ||
            NextTwoOpcode(callback) is not (0x0028 or 0x006f) ||
            NextTwoTarget(callback) != Target(submission))
        {
            throw new VerificationException("critical_flow_forbidden");
        }
    }

    private static int Offset(string row)
    {
        string[] fields = row.Split('|');
        return fields.Length == 11 && int.TryParse(fields[2], out int value)
            ? value : throw new VerificationException("critical_flow_forbidden");
    }

    private static int Opcode(string row) => ParseInt(row, 3, System.Globalization.NumberStyles.HexNumber);
    private static int InputLocal(string row) => ParseInt(row, 4, System.Globalization.NumberStyles.Integer);
    private static int OutputLocal(string row) => ParseInt(row, 5, System.Globalization.NumberStyles.Integer);
    private static string Owner(string row) => Fields(row)[1];
    private static string Target(string row) => Fields(row)[6];
    private static int NextOpcode(string row) => ParseInt(row, 7, System.Globalization.NumberStyles.HexNumber);
    private static string NextTarget(string row) => Fields(row)[8];
    private static int NextTwoOpcode(string row) => ParseInt(row, 9, System.Globalization.NumberStyles.HexNumber);
    private static string NextTwoTarget(string row) => Fields(row)[10];

    private static int ParseInt(string row, int index, System.Globalization.NumberStyles style)
    {
        string[] fields = Fields(row);
        return int.TryParse(fields[index], style, System.Globalization.CultureInfo.InvariantCulture, out int value)
            ? value : throw new VerificationException("critical_flow_forbidden");
    }

    private static string[] Fields(string row)
    {
        string[] fields = row.Split('|');
        return fields.Length == 11 ? fields : throw new VerificationException("critical_flow_forbidden");
    }

    private static bool HasExpectedImportFlags(string name, int attributes)
    {
        const int Cdecl = 0x0200;
        const int SupportsLastError = 0x0040;
        if ((attributes & 0x0700) != Cdecl)
        {
            return false;
        }
        bool expectedLastError = name is not "getuid" and not "geteuid" and not "getpwuid_r";
        return (attributes & SupportsLastError) != 0 == expectedLastError;
    }

    private static string VerifySources(string sourceRoot, IReadOnlyList<PolicySourceFile> sources)
    {
        string normalizedRoot;
        try
        {
            normalizedRoot = Path.GetFullPath(sourceRoot);
        }
        catch
        {
            throw new BoundaryException("source_root_boundary");
        }
        var root = new DirectoryInfo(normalizedRoot);
        SafeFiles.RequireNoLinkAncestors(normalizedRoot, includeLeaf: true, "source_root_boundary");
        if (!root.Exists || root.LinkTarget is not null)
        {
            throw new BoundaryException("source_root_boundary");
        }
        string prefix = normalizedRoot.EndsWith(Path.DirectorySeparatorChar)
            ? normalizedRoot : normalizedRoot + Path.DirectorySeparatorChar;
        var projection = new StringBuilder();
        foreach (PolicySourceFile source in sources)
        {
            string path = Path.GetFullPath(Path.Combine(
                normalizedRoot,
                source.Path.Replace('/', Path.DirectorySeparatorChar)));
            if (!path.StartsWith(prefix, StringComparison.Ordinal))
            {
                throw new BoundaryException("source_boundary");
            }
            RequireNoLinkComponents(normalizedRoot, source.Path);
            byte[] bytes = SafeFiles.ReadBoundedRegularFile(path, 1024 * 1024, "source_boundary");
            string sha = GenericEventReleaseProjectionBuilder.Sha(bytes);
            if (sha != source.Sha256)
            {
                throw new VerificationException("source_hash_mismatch");
            }
            projection.Append(sha).Append("  ./").Append(source.Path).Append('\n');
        }
        return GenericEventReleaseProjectionBuilder.Sha(Encoding.UTF8.GetBytes(projection.ToString()));
    }

    private static void RequireNoLinkComponents(string root, string relative)
    {
        string current = root;
        string[] parts = relative.Split('/');
        for (int index = 0; index < parts.Length - 1; index++)
        {
            current = Path.Combine(current, parts[index]);
            var directory = new DirectoryInfo(current);
            if (!directory.Exists || directory.LinkTarget is not null ||
                (directory.Attributes & FileAttributes.ReparsePoint) != 0)
            {
                throw new BoundaryException("source_boundary");
            }
        }
    }
}
