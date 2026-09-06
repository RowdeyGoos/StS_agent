using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV1;

public interface IGenericEventV1NativeAdapter : IDisposable
{
    GenericEventV1NativeCapture Capture();
    void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId);
    CardSelectionV1Session CreateChild();
    void CompleteParent();
}
public sealed record GenericEventV1NativeOption(object Identity, string StableId,
    string RenderedText, bool Enabled, bool Dangerous, bool IsProceed);
public sealed record GenericEventV1NativeCapture(string Status, bool EventFinished,
    IReadOnlyList<GenericEventV1NativeOption> Options, object? ChildIdentity = null,
    int DomainCount = 0);
