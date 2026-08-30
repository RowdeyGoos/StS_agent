using System;
using System.IO;
using System.Runtime.Versioning;
using MegaCrit.Sts2.Core.Modding;
using Sts2AgentBridge.Adapters.Identity;
using Sts2AgentBridge.Core.Hosting;

namespace Sts2AgentBridge.Tests.BuildIdentity;

internal static class BuildIdentityTestSuite
{
    public static void Run()
    {
        TestPinnedCopiedAssemblyIsCompatible();
        TestActualGuardFailureIoOnDisposableAssemblyCopy();
        TestCompatible();
        TestWrongSizeLocksWithoutRead();
        TestWrongSizeAfterReadIsUncertain();
        TestDigestMismatchLocks();
        TestUncertainInputsFailClosed();
        TestDefaultAndUndefinedResultsFailClosed();
    }

    private static void TestPinnedCopiedAssemblyIsCompatible()
    {
        BuildIdentityResult result = new PinnedBuildGuard().Evaluate();
        TestAssert.Equal(
            BuildIdentityStatus.Compatible,
            result.Status,
            "exact copied pinned sts2 assembly should pass the real guard");
    }

    private static void TestActualGuardFailureIoOnDisposableAssemblyCopy()
    {
        if (!OperatingSystem.IsMacOS())
        {
            return;
        }

        string assemblyPath = typeof(ModInitializerAttribute).Assembly.Location;
        byte[] original = File.ReadAllBytes(assemblyPath);
        UnixFileMode originalMode = File.GetUnixFileMode(assemblyPath);
        string backupPath = assemblyPath + ".r0a-test-backup-" + Guid.NewGuid().ToString("N");

        try
        {
            using (var stream = new FileStream(
                       assemblyPath,
                       FileMode.Open,
                       FileAccess.Write,
                       FileShare.ReadWrite))
            {
                stream.SetLength(original.Length - 1);
            }

            File.SetUnixFileMode(assemblyPath, 0);
            BuildIdentityResult wrongSize = new PinnedBuildGuard().Evaluate();
            TestAssert.Equal(
                BuildIdentityStatus.IncompatibleLocked,
                wrongSize.Status,
                "actual guard locks a wrong-size unreadable copy before content open");
            TestAssert.True(wrongSize.ListenerAllowed, "actual wrong-size guard result permits locked listener");
            RestoreAssemblyCopy(assemblyPath, original, originalMode);

            byte[] changed = (byte[])original.Clone();
            changed[^1] ^= 0x01;
            File.WriteAllBytes(assemblyPath, changed);
            File.SetUnixFileMode(assemblyPath, originalMode);
            BuildIdentityResult digestMismatch = new PinnedBuildGuard().Evaluate();
            TestAssert.Equal(
                BuildIdentityStatus.IncompatibleLocked,
                digestMismatch.Status,
                "actual guard locks a complete stable digest mismatch");
            RestoreAssemblyCopy(assemblyPath, original, originalMode);

            File.SetUnixFileMode(assemblyPath, 0);
            BuildIdentityResult unreadable = new PinnedBuildGuard().Evaluate();
            TestAssert.Equal(
                BuildIdentityStatus.Uncertain,
                unreadable.Status,
                "actual guard treats an exact-size read failure as uncertain");
            TestAssert.False(unreadable.ListenerAllowed, "actual read failure starts no listener");
            RestoreAssemblyCopy(assemblyPath, original, originalMode);

            File.Move(assemblyPath, backupPath);
            File.CreateSymbolicLink(assemblyPath, backupPath);
            BuildIdentityResult linked = new PinnedBuildGuard().Evaluate();
            TestAssert.Equal(
                BuildIdentityStatus.Uncertain,
                linked.Status,
                "actual guard treats a link at the loaded assembly path as uncertain");
            TestAssert.False(linked.ListenerAllowed, "actual linked assembly path starts no listener");
            File.Delete(assemblyPath);
            File.Move(backupPath, assemblyPath);
            RestoreAssemblyCopy(assemblyPath, original, originalMode);
        }
        finally
        {
            try
            {
                var current = new FileInfo(assemblyPath);
                if (current.LinkTarget is not null)
                {
                    File.Delete(assemblyPath);
                }
                else if (Directory.Exists(assemblyPath))
                {
                    Directory.Delete(assemblyPath);
                }

                if (File.Exists(backupPath))
                {
                    if (File.Exists(assemblyPath))
                    {
                        File.Delete(assemblyPath);
                    }

                    File.Move(backupPath, assemblyPath);
                }

                RestoreAssemblyCopy(assemblyPath, original, originalMode);
            }
            finally
            {
                Array.Clear(original, 0, original.Length);
            }
        }
    }

    [SupportedOSPlatform("macos")]
    private static void RestoreAssemblyCopy(
        string assemblyPath,
        byte[] original,
        UnixFileMode originalMode)
    {
        if (File.Exists(assemblyPath))
        {
            File.SetUnixFileMode(assemblyPath, originalMode);
        }

        File.WriteAllBytes(assemblyPath, original);
        File.SetUnixFileMode(assemblyPath, originalMode);
    }

    private static void TestCompatible()
    {
        BuildIdentityResult result = BuildIdentityDecision.Classify(CompatibleFacts());
        TestAssert.Equal(BuildIdentityStatus.Compatible, result.Status, "exact build should be compatible");
        TestAssert.True(result.ListenerAllowed, "compatible build should allow listener");
        TestAssert.True(result.PublicScreenAllowed, "compatible build should allow public reader");
    }

    private static void TestWrongSizeLocksWithoutRead()
    {
        BuildIdentityFacts facts = CompatibleFacts() with
        {
            PreOpenLength = BuildIdentityDecision.ExpectedAssemblyLength - 1,
            ContentReadAttempted = false,
            ContentReadComplete = false,
        };
        BuildIdentityResult result = BuildIdentityDecision.Classify(facts);
        TestAssert.Equal(BuildIdentityStatus.IncompatibleLocked, result.Status, "wrong pre-open size should lock");
        TestAssert.True(result.ListenerAllowed, "known mismatch should allow locked listener");
        TestAssert.False(result.PublicScreenAllowed, "known mismatch must disable reader");
    }

    private static void TestWrongSizeAfterReadIsUncertain()
    {
        BuildIdentityFacts facts = CompatibleFacts() with
        {
            PreOpenLength = BuildIdentityDecision.ExpectedAssemblyLength - 1,
            ContentReadAttempted = true,
        };
        TestAssert.Equal(
            BuildIdentityStatus.Uncertain,
            BuildIdentityDecision.Classify(facts).Status,
            "wrong-size content read violates the bounded decision path");
    }

    private static void TestDigestMismatchLocks()
    {
        BuildIdentityFacts facts = CompatibleFacts() with { DigestMatches = false };
        TestAssert.Equal(
            BuildIdentityStatus.IncompatibleLocked,
            BuildIdentityDecision.Classify(facts).Status,
            "complete stable digest mismatch should lock");
    }

    private static void TestUncertainInputsFailClosed()
    {
        BuildIdentityFacts baseline = CompatibleFacts();
        BuildIdentityFacts[] uncertain =
        {
            baseline with { PlatformSupported = false },
            baseline with { AbsolutePath = false },
            baseline with { BasenameMatches = false },
            baseline with { LinkTargetAbsent = false },
            baseline with { Exists = false },
            baseline with { RegularFile = false },
            baseline with { ContentReadComplete = false },
            baseline with { OpenHandleLength = 0 },
            baseline with { PostReadLinkTargetAbsent = false },
            baseline with { PostReadPathLength = 0 },
            baseline with { ReadFailed = true },
        };

        foreach (BuildIdentityFacts facts in uncertain)
        {
            BuildIdentityResult result = BuildIdentityDecision.Classify(facts);
            TestAssert.Equal(BuildIdentityStatus.Uncertain, result.Status, "ambiguous build input must be uncertain");
            TestAssert.False(result.ListenerAllowed, "uncertain identity must start no listener");
        }
    }

    private static void TestDefaultAndUndefinedResultsFailClosed()
    {
        BuildIdentityResult defaultResult = default;
        TestAssert.Equal(BuildIdentityStatus.Uncertain, defaultResult.Status, "default identity is uncertain");
        TestAssert.False(defaultResult.ListenerAllowed, "default identity starts no listener");
        TestAssert.False(defaultResult.PublicScreenAllowed, "default identity starts no public reader");

        var undefinedResult = new BuildIdentityResult((BuildIdentityStatus)999);
        TestAssert.False(undefinedResult.ListenerAllowed, "undefined identity starts no listener");
        TestAssert.False(undefinedResult.PublicScreenAllowed, "undefined identity starts no public reader");
    }

    private static BuildIdentityFacts CompatibleFacts() => new(
        PlatformSupported: true,
        AbsolutePath: true,
        BasenameMatches: true,
        LinkTargetAbsent: true,
        Exists: true,
        RegularFile: true,
        PreOpenLength: BuildIdentityDecision.ExpectedAssemblyLength,
        ContentReadAttempted: true,
        ContentReadComplete: true,
        OpenHandleLength: BuildIdentityDecision.ExpectedAssemblyLength,
        PostReadLinkTargetAbsent: true,
        PostReadPathLength: BuildIdentityDecision.ExpectedAssemblyLength,
        DigestMatches: true,
        ReadFailed: false);
}
