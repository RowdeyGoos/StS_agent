using System;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV10;
public enum GenericEventReleaseSelection { Generic = 1 }
public sealed class GenericEventTransportFactoryFailure : Exception
{
    public GenericEventTransportFactoryFailure(Action ownerFrameCleanup)
        : base("Native construction retained owner-frame cleanup.") => OwnerFrameCleanup = ownerFrameCleanup ?? throw new ArgumentNullException(nameof(ownerFrameCleanup));
    public Action OwnerFrameCleanup { get; }
}
