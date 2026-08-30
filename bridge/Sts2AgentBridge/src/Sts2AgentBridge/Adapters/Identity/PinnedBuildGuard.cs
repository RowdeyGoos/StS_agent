using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using MegaCrit.Sts2.Core.Modding;
using Sts2AgentBridge.Core.Hosting;

namespace Sts2AgentBridge.Adapters.Identity;

public sealed class PinnedBuildGuard
{
    public const string TargetBuildManifestId = "sts2-steam-main-build-23811903-macos-universal";
    public const string TargetGameVersion = "v0.107.1";
    public const string TargetSteamBuildId = "23811903";

    private const string ExpectedBasename = "sts2.dll";

    private static ReadOnlySpan<byte> ExpectedSha256 =>
    [
        0xe7, 0xce, 0xb8, 0x06, 0x69, 0xbf, 0xaf, 0x5c,
        0x8f, 0xcc, 0xab, 0xaa, 0x12, 0x6a, 0xe2, 0xbb,
        0x28, 0x3a, 0xba, 0x51, 0x4b, 0xe5, 0xb5, 0xb5,
        0x56, 0x12, 0x57, 0x9c, 0xfd, 0x28, 0x5f, 0x18,
    ];

    public BuildIdentityResult Evaluate()
    {
        byte[]? readBuffer = null;
        byte[]? digest = null;

        try
        {
            if (!OperatingSystem.IsMacOS() || RuntimeInformation.ProcessArchitecture != Architecture.Arm64)
            {
                return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
            }

            string assemblyPath = typeof(ModInitializerAttribute).Assembly.Location;
            if (!Path.IsPathFullyQualified(assemblyPath) ||
                !string.Equals(Path.GetFileName(assemblyPath), ExpectedBasename, StringComparison.Ordinal))
            {
                return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
            }

            var assemblyFile = new FileInfo(assemblyPath);
            if (assemblyFile.LinkTarget is not null)
            {
                return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
            }

            if (!assemblyFile.Exists)
            {
                return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
            }

            FileAttributes attributes = assemblyFile.Attributes;
            const FileAttributes rejectedKinds =
                FileAttributes.Directory | FileAttributes.Device | FileAttributes.ReparsePoint;
            if ((attributes & rejectedKinds) != 0)
            {
                return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
            }

            long preOpenLength = assemblyFile.Length;
            if (preOpenLength != BuildIdentityDecision.ExpectedAssemblyLength)
            {
                return new BuildIdentityResult(BuildIdentityStatus.IncompatibleLocked);
            }

            var stream = new FileStream(
                assemblyPath,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read);
            try
            {
                if (stream.Length != BuildIdentityDecision.ExpectedAssemblyLength)
                {
                    return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
                }

                readBuffer = new byte[64 * 1024];
                using IncrementalHash hasher = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
                long remaining = BuildIdentityDecision.ExpectedAssemblyLength;
                while (remaining > 0)
                {
                    int requested = (int)Math.Min(readBuffer.Length, remaining);
                    int read = stream.Read(readBuffer.AsSpan(0, requested));
                    if (read <= 0)
                    {
                        return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
                    }

                    hasher.AppendData(readBuffer.AsSpan(0, read));
                    remaining -= read;
                }

                digest = hasher.GetHashAndReset();
                if (stream.Length != BuildIdentityDecision.ExpectedAssemblyLength)
                {
                    return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
                }
            }
            finally
            {
                stream.Dispose();
            }

            assemblyFile.Refresh();
            if (assemblyFile.LinkTarget is not null ||
                !assemblyFile.Exists ||
                assemblyFile.Length != BuildIdentityDecision.ExpectedAssemblyLength)
            {
                return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
            }

            return digest.AsSpan().SequenceEqual(ExpectedSha256)
                ? new BuildIdentityResult(BuildIdentityStatus.Compatible)
                : new BuildIdentityResult(BuildIdentityStatus.IncompatibleLocked);
        }
        catch
        {
            return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
        }
        finally
        {
            if (readBuffer is not null)
            {
                CryptographicOperations.ZeroMemory(readBuffer);
            }

            if (digest is not null)
            {
                CryptographicOperations.ZeroMemory(digest);
            }
        }
    }
}
