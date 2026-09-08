using System;
using System.Reflection;
using System.Runtime.Loader;
using HarmonyLib;
using MegaCrit.Sts2.Core.Modding;
using Sts2AgentBridge.Successors.ItemBootstrapV1;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV6;

internal static class PinnedGenericEventHarmonyGuard
{
    internal const string ExpectedPath = "/Users/rowdeygoos/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64/0Harmony.dll";
    internal const long ExpectedLength = 2328064;
    internal const string ExpectedSha256 = "ef1898322c9f5c86dc1b0758b272a9c440823b4a41ca9a0b82a3aa6b3d206387";
    internal const string ExpectedIdentity = "0Harmony, Version=2.4.2.0, Culture=neutral, PublicKeyToken=null";
    internal const string ExpectedMvid = "6b813929-656e-4f25-9e34-f25e7084505d";
    private const int MaximumAssemblies = 1024;

    internal static bool Verify()
    {
        try
        {
            if (!DarwinReadOnly.IsSupportedPlatform()) return false;
            Assembly actual = typeof(Harmony).Assembly;
            Assembly game = typeof(ModInitializerAttribute).Assembly;
            AssemblyLoadContext? context = AssemblyLoadContext.GetLoadContext(actual);
            AssemblyLoadContext? gameContext = AssemblyLoadContext.GetLoadContext(game);
            if (!ValidBinding(actual.Location, actual.FullName, actual.ManifestModule.ModuleVersionId.ToString("D"),
                    context, gameContext, context?.IsCollectible ?? true)) return false;
            if (!ExclusiveBinding(actual)) return false;
            if (!VerifyFile(actual.Location)) return false;
            // Do not admit a competing binding that appeared during the file read.
            return ExclusiveBinding(actual) && ReferenceEquals(context, AssemblyLoadContext.GetLoadContext(actual));
        }
        catch { return false; }
    }

    internal static bool ValidBinding(string path, string? identity, string mvid,
        object? context, object? gameContext, bool collectible) =>
        path == ExpectedPath && identity == ExpectedIdentity && mvid == ExpectedMvid &&
        context is not null && ReferenceEquals(context, gameContext) && !collectible;

    private static bool ExclusiveBinding(Assembly actual)
    {
        return ExclusiveBinding(actual, AppDomain.CurrentDomain.GetAssemblies());
    }

    internal static bool ExclusiveBinding(Assembly actual, Assembly[] assemblies)
    {
        if (assemblies.Length is < 1 or > MaximumAssemblies) return false;
        int matches = 0;
        foreach (Assembly assembly in assemblies)
        {
            if (!string.Equals(assembly.GetName().Name, "0Harmony", StringComparison.OrdinalIgnoreCase)) continue;
            if (!ReferenceEquals(assembly, actual)) return false;
            matches++;
        }
        return matches == 1;
    }

    private static bool VerifyFile(string path)
    {
        if (path != ExpectedPath || !DarwinReadOnly.TryParseAbsolutePath(path, out string[] components) ||
            !DarwinReadOnly.TryGetIdentity(LibSystemDarwinReadOnlyNative.Instance, out uint user)) return false;
        var descriptors = new DarwinDescriptorLease(LibSystemDarwinReadOnlyNative.Instance, user);
        byte[] digest = Convert.FromHexString(ExpectedSha256);
        try
        {
            if (!descriptors.TryOpenRoot()) return false;
            for (int index = 0; index < components.Length - 1; index++)
                if (!descriptors.TryOpenDirectory(components[index], DarwinDescriptorPolicy.AncestorDirectory)) return false;
            if (!descriptors.TryOpenFile(components[^1], DarwinDescriptorPolicy.PinnedFile, out HeldDescriptor? held) ||
                held is null || !descriptors.TryVerifyHash(held, ExpectedLength, digest) ||
                !descriptors.RevalidateAll()) return false;
            return descriptors.CloseAll();
        }
        catch { return false; }
        finally { Array.Clear(digest); _ = descriptors.CloseAll(); }
    }
}
