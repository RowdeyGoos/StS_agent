using System;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal static class ItemPinnedFileIdentity
{
    private const string StsName = "sts2.dll";
    private const long StsLength = 9363456;
    private const string StsDigest = "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18";
    private const string GodotName = "GodotSharp.dll";
    private const long GodotLength = 5613568;
    private const string GodotDigest = "0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289";

    internal static bool Verify(string assemblyPath, long expectedLength, string expectedSha256)
    {
        if (!DarwinReadOnly.IsSupportedPlatform() ||
            !IsPinnedTuple(assemblyPath, expectedLength, expectedSha256, out string[] components))
            return false;
        IDarwinReadOnlyNative native = LibSystemDarwinReadOnlyNative.Instance;
        if (!DarwinReadOnly.TryGetIdentity(native, out uint effectiveUserId))
            return false;
        return VerifyAbsolute(native, effectiveUserId, components, expectedLength, expectedSha256);
    }

#if ITEM_BOOTSTRAP_TEST_SEAM
    internal static bool VerifyForTests(
        string fixtureHome,
        string relativeName,
        long expectedLength,
        string expectedSha256,
        IDarwinReadOnlyNative? native = null)
    {
        native ??= LibSystemDarwinReadOnlyNative.Instance;
        byte[] digest = Array.Empty<byte>();
        if (!ItemOperatorFiles.IsSyntheticHomeForTests(fixtureHome) ||
            !IsSingleComponent(relativeName) ||
            expectedLength < 0 ||
            !TryDecodeDigest(expectedSha256, out digest) ||
            !DarwinReadOnly.TryGetIdentity(native, out uint effectiveUserId))
        {
            return false;
        }
        var descriptors = new DarwinDescriptorLease(native, effectiveUserId);
        try
        {
            if (!descriptors.TryOpenSyntheticHome(fixtureHome) ||
                !descriptors.TryOpenFile(relativeName, DarwinDescriptorPolicy.PinnedFile, out HeldDescriptor? held) ||
                held is null ||
                !descriptors.TryVerifyHash(held, expectedLength, digest) ||
                !descriptors.RevalidateAll())
                return false;
            return descriptors.CloseAll();
        }
        catch
        {
            return false;
        }
        finally
        {
            DarwinReadOnly.Zero(digest);
            _ = descriptors.CloseAll();
        }
    }
#endif

    private static bool VerifyAbsolute(
        IDarwinReadOnlyNative native,
        uint effectiveUserId,
        string[] components,
        long expectedLength,
        string expectedSha256)
    {
        if (!TryDecodeDigest(expectedSha256, out byte[] digest))
            return false;
        var descriptors = new DarwinDescriptorLease(native, effectiveUserId);
        try
        {
            if (!descriptors.TryOpenRoot())
                return false;
            for (int index = 0; index < components.Length - 1; index++)
            {
                if (!descriptors.TryOpenDirectory(components[index], DarwinDescriptorPolicy.AncestorDirectory))
                    return false;
            }
            if (!descriptors.TryOpenFile(components[^1], DarwinDescriptorPolicy.PinnedFile, out HeldDescriptor? held) ||
                held is null ||
                !descriptors.TryVerifyHash(held, expectedLength, digest) ||
                !descriptors.RevalidateAll())
                return false;
            return descriptors.CloseAll();
        }
        catch
        {
            return false;
        }
        finally
        {
            DarwinReadOnly.Zero(digest);
            _ = descriptors.CloseAll();
        }
    }

    private static bool IsPinnedTuple(
        string path,
        long expectedLength,
        string expectedDigest,
        out string[] components)
    {
        components = Array.Empty<string>();
        if (!DarwinReadOnly.TryParseAbsolutePath(path, out string[] parsed) || parsed.Length == 0)
            return false;
        string name = parsed[^1];
        bool valid =
            (name == StsName && expectedLength == StsLength && expectedDigest == StsDigest) ||
            (name == GodotName && expectedLength == GodotLength && expectedDigest == GodotDigest);
        if (!valid)
            return false;
        components = parsed;
        return true;
    }

    private static bool TryDecodeDigest(string value, out byte[] digest)
    {
        digest = Array.Empty<byte>();
        if (value is null || value.Length != 64)
            return false;
        byte[] result = new byte[32];
        for (int index = 0; index < result.Length; index++)
        {
            int high = Hex(value[index * 2]);
            int low = Hex(value[index * 2 + 1]);
            if (high < 0 || low < 0)
            {
                Array.Clear(result);
                return false;
            }
            result[index] = (byte)((high << 4) | low);
        }
        digest = result;
        return true;
    }

    private static int Hex(char value)
    {
        if (value >= '0' && value <= '9')
            return value - '0';
        if (value >= 'a' && value <= 'f')
            return value - 'a' + 10;
        return -1;
    }

    private static bool IsSingleComponent(string value) =>
        !string.IsNullOrEmpty(value) && value != "." && value != ".." &&
        value.IndexOf('/') < 0 && value.IndexOf('\0') < 0 &&
        value.IndexOf('\n') < 0 && value.IndexOf('\r') < 0;
}
