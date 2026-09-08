using System;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV10;

internal sealed class VerificationException : Exception
{
    internal VerificationException(string code) : base(code) => Code = code;

    internal string Code { get; }
}

internal sealed class BoundaryException : Exception
{
    internal BoundaryException(string code) : base(code) => Code = code;

    internal string Code { get; }
}
