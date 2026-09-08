using System;
using Sts2AgentBridge.Successors.ItemBootstrapV1;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal static class CardSelectionOperatorFiles
{
    internal static ItemOperatorConfiguration? OpenEnabled()
    {
        if (!DarwinReadOnly.IsSupportedPlatform())
            return null;
        IDarwinReadOnlyNative native = LibSystemDarwinReadOnlyNative.Instance;
        if (!DarwinReadOnly.TryGetIdentity(native, out uint effectiveUserId) ||
            !DarwinReadOnly.TryResolveHome(native, effectiveUserId, out string[] homeComponents))
            return null;
        return OpenFromAbsoluteHome(native, effectiveUserId, homeComponents);
    }

#if CARD_SELECTION_RELEASE_TEST_SEAM
    internal static ItemOperatorConfiguration? OpenEnabledForTests(
        string fixtureHome,
        IDarwinReadOnlyNative? native = null)
    {
        native ??= LibSystemDarwinReadOnlyNative.Instance;
        if (!IsSyntheticHome(fixtureHome) ||
            !DarwinReadOnly.TryGetIdentity(native, out uint effectiveUserId))
            return null;
        var descriptors = new DarwinDescriptorLease(native, effectiveUserId);
        try
        {
            if (!descriptors.TryOpenSyntheticHome(fixtureHome))
            {
                _ = descriptors.CloseAll();
                return null;
            }
            return OpenBelowHome(descriptors);
        }
        catch
        {
            _ = descriptors.CloseAll();
            return null;
        }
    }

    internal static bool IsSyntheticHomeForTests(string path) => IsSyntheticHome(path);
#endif

    private static ItemOperatorConfiguration? OpenFromAbsoluteHome(
        IDarwinReadOnlyNative native,
        uint effectiveUserId,
        string[] homeComponents)
    {
        var descriptors = new DarwinDescriptorLease(native, effectiveUserId);
        try
        {
            if (homeComponents.Length == 0 && effectiveUserId != 0)
                return CloseAndNull(descriptors);
            if (!descriptors.TryOpenRoot())
                return CloseAndNull(descriptors);
            for (int index = 0; index < homeComponents.Length; index++)
            {
                DarwinDescriptorPolicy policy = index == homeComponents.Length - 1
                    ? DarwinDescriptorPolicy.OwnedDirectory
                    : DarwinDescriptorPolicy.AncestorDirectory;
                if (!descriptors.TryOpenDirectory(homeComponents[index], policy))
                    return CloseAndNull(descriptors);
            }
            return OpenBelowHome(descriptors);
        }
        catch
        {
            return CloseAndNull(descriptors);
        }
    }

    private static ItemOperatorConfiguration? OpenBelowHome(DarwinDescriptorLease descriptors)
    {
        byte[] configuration = Array.Empty<byte>();
        try
        {
            if (!descriptors.TryOpenDirectory("Library", DarwinDescriptorPolicy.OwnedDirectory) ||
                !descriptors.TryOpenDirectory("Application Support", DarwinDescriptorPolicy.OwnedDirectory) ||
                !descriptors.TryOpenDirectory("Sts2AgentBridge", DarwinDescriptorPolicy.PrivateDirectory) ||
                !descriptors.TryOpenDirectory("card_selection_v1", DarwinDescriptorPolicy.PrivateDirectory) ||
                !descriptors.TryOpenFile("config.json", DarwinDescriptorPolicy.PrivateFile, out HeldDescriptor? config) ||
                config is null ||
                !descriptors.TryReadStable(config, 1, 512, out configuration) ||
                !IsExactEnabled(configuration) ||
                !descriptors.RevalidateAll())
            {
                DarwinReadOnly.Zero(configuration);
                return CloseAndNull(descriptors);
            }
            var result = new ItemOperatorConfiguration(descriptors, configuration);
            configuration = Array.Empty<byte>();
            return result;
        }
        catch
        {
            DarwinReadOnly.Zero(configuration);
            return CloseAndNull(descriptors);
        }
    }

    private static bool IsExactEnabled(byte[] bytes) =>
        FixedEquals(bytes, CheeseEnabled) || FixedEquals(bytes, SmithEnabled);

    private static ReadOnlySpan<byte> CheeseEnabled =>
        "{\"schema_version\":\"card_selection_v1_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"cheese\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    private static ReadOnlySpan<byte> SmithEnabled =>
        "{\"schema_version\":\"card_selection_v1_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"smith\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    private static bool FixedEquals(ReadOnlySpan<byte> value, ReadOnlySpan<byte> expected)
    {
        if (value.Length != expected.Length)
            return false;
        int difference = 0;
        for (int index = 0; index < value.Length; index++)
            difference |= value[index] ^ expected[index];
        return difference == 0;
    }

    private static ItemOperatorConfiguration? CloseAndNull(DarwinDescriptorLease descriptors)
    {
        _ = descriptors.CloseAll();
        return null;
    }

#if CARD_SELECTION_RELEASE_TEST_SEAM
    private static bool IsSyntheticHome(string path)
    {
        const string prefix = "/private/tmp/";
        if (string.IsNullOrEmpty(path) || !path.StartsWith(prefix, StringComparison.Ordinal))
            return false;
        string leaf = path[prefix.Length..];
        return leaf.Length is >= 1 and <= 128 && leaf != "." && leaf != ".." &&
            leaf.IndexOf('/') < 0 && leaf.IndexOf('\0') < 0 &&
            leaf.IndexOf('\n') < 0 && leaf.IndexOf('\r') < 0;
    }
#endif
}
