using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Verifier;

internal sealed record ShopMapPermissionReleaseVerificationReport(
    string AssemblySha256,
    string SourceProjectionSha256,
    string MetadataProjectionSha256,
    int CheckedMethodBodies);

internal static class ShopMapPermissionReleaseVerifier
{
    private const string ExpectedAssemblyName = "Sts2AgentBridgeRoomFlowsV1";
    private const string ExpectedAssemblyVersion = "1.0.0.0";
    private static readonly string[] ExpectedRoutes =
    {
        "/probe/item-v1/public/item-action",
        "/probe/item-v1/public/item-decision",
        "/probe/room-flows-v1/public/action",
        "/probe/room-flows-v1/public/decision",
    };
    private static readonly HashSet<string> ExpectedNativeNames = new(StringComparer.Ordinal)
    {
        "getuid", "geteuid", "getpwuid_r", "open", "openat", "fstat", "fstatat",
        "read", "close", "acl_get_fd_np", "acl_get_entry", "acl_get_tag_type", "acl_free",
    };
    private const string ExpectedInitializer =
        "type:Sts2AgentBridge.Successors.RoomReleaseV1.RoomFlowModEntry|" +
        "MegaCrit.Sts2.Core.Modding.ModInitializerAttribute..ctor(System.String)|" +
        "01000a496e697469616c697a650000";
    private const string ExpectedEntryType =
        "type_def|Sts2AgentBridge.Successors.RoomReleaseV1.RoomFlowModEntry|1048961|System.Object|0|0";
    private const string ExpectedEntryMethod =
        "method_def|Sts2AgentBridge.Successors.RoomReleaseV1.RoomFlowModEntry.Initialize()|System.Void|0|0|0|150|0";

    internal static ShopMapPermissionReleaseVerificationReport Verify(
        byte[] candidate,
        string sourceRoot,
        ShopMapPermissionReleasePolicy policy,
        bool enforceArtifactIdentity)
    {
        ShopMapPermissionReleaseProjection projection = ShopMapPermissionReleaseProjectionBuilder.Build(candidate);
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
        return new ShopMapPermissionReleaseVerificationReport(
            projection.ArtifactSha256,
            sourceProjection,
            projection.MetadataProjectionSha256,
            projection.CheckedMethodBodies);
    }

    internal static void VerifySemanticRules(ShopMapPermissionReleaseProjection projection)
    {
        if (!projection.Routes.SequenceEqual(ExpectedRoutes, StringComparer.Ordinal))
        {
            throw new VerificationException("route_surface_forbidden");
        }
        if (projection.ForbiddenReferences.Length != 0)
        {
            throw new VerificationException("runtime_surface_forbidden");
        }
        if (projection.SensitiveReferences.Length != 0)
        {
            throw new VerificationException("test_seam_reachable");
        }
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
            !projection.Inventory.Contains(ExpectedEntryMethod, StringComparer.Ordinal) ||
            projection.Inventory.Count(value => value.StartsWith(
                "method_def|Sts2AgentBridge.Successors.RoomReleaseV1.RoomFlowModEntry.",
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
            string sha = ShopMapPermissionReleaseProjectionBuilder.Sha(bytes);
            if (sha != source.Sha256)
            {
                throw new VerificationException("source_hash_mismatch");
            }
            projection.Append(sha).Append("  ./").Append(source.Path).Append('\n');
        }
        return ShopMapPermissionReleaseProjectionBuilder.Sha(Encoding.UTF8.GetBytes(projection.ToString()));
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
