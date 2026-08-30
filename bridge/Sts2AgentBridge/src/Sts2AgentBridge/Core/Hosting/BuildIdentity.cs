using System;

namespace Sts2AgentBridge.Core.Hosting;

public enum BuildIdentityStatus
{
    Uncertain = 0,
    Compatible = 1,
    IncompatibleLocked = 2,
}

public readonly record struct BuildIdentityResult(BuildIdentityStatus Status)
{
    public bool ListenerAllowed =>
        Status is BuildIdentityStatus.Compatible or BuildIdentityStatus.IncompatibleLocked;

    public bool PublicScreenAllowed => Status == BuildIdentityStatus.Compatible;
}

public readonly record struct BuildIdentityFacts(
    bool PlatformSupported,
    bool AbsolutePath,
    bool BasenameMatches,
    bool LinkTargetAbsent,
    bool Exists,
    bool RegularFile,
    long PreOpenLength,
    bool ContentReadAttempted,
    bool ContentReadComplete,
    long OpenHandleLength,
    bool PostReadLinkTargetAbsent,
    long PostReadPathLength,
    bool DigestMatches,
    bool ReadFailed);

public static class BuildIdentityDecision
{
    public const long ExpectedAssemblyLength = 9_363_456;

    public static BuildIdentityResult Classify(BuildIdentityFacts facts)
    {
        if (!facts.PlatformSupported ||
            !facts.AbsolutePath ||
            !facts.BasenameMatches ||
            !facts.LinkTargetAbsent ||
            !facts.Exists ||
            !facts.RegularFile ||
            facts.ReadFailed)
        {
            return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
        }

        if (facts.PreOpenLength != ExpectedAssemblyLength)
        {
            return facts.ContentReadAttempted
                ? new BuildIdentityResult(BuildIdentityStatus.Uncertain)
                : new BuildIdentityResult(BuildIdentityStatus.IncompatibleLocked);
        }

        if (!facts.ContentReadAttempted ||
            !facts.ContentReadComplete ||
            facts.OpenHandleLength != ExpectedAssemblyLength ||
            !facts.PostReadLinkTargetAbsent ||
            facts.PostReadPathLength != ExpectedAssemblyLength)
        {
            return new BuildIdentityResult(BuildIdentityStatus.Uncertain);
        }

        return new BuildIdentityResult(
            facts.DigestMatches
                ? BuildIdentityStatus.Compatible
                : BuildIdentityStatus.IncompatibleLocked);
    }
}
