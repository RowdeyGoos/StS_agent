using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV2;

public interface IGenericEventV2NativeAdapter : IDisposable
{
    GenericEventV2NativeCapture Capture();
    void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId);
    CardSelectionV1Session CreateChild(object admissionIdentity);
    void CompleteParent();
}
public sealed record GenericEventV2NativeOption(object Identity, string StableId,
    string RenderedText, bool Enabled, bool Dangerous, bool IsProceed);
public sealed record GenericEventV2NativeCapture(string Status, bool EventFinished,
    IReadOnlyList<GenericEventV2NativeOption> Options, object? ChildIdentity = null,
    GenericEventV2Admission? Admission = null);

// Native-only immutable description. Clients never construct an admission.
public sealed record GenericEventV2Admission(object Identity, string Operation,
    int MinSelect, int MaxSelect, string CommitMode, int DomainCount)
{
    public bool IsSupported => Identity is not null &&
        GenericEventV2Families.Supports(Operation, MinSelect, MaxSelect, CommitMode, DomainCount);
}

public static class GenericEventV2Families
{
    public static bool Supports(string operation, int minSelect, int maxSelect,
        string commitMode, int domainCount) => commitMode == "preview_confirm" &&
        domainCount <= 64 && domainCount > maxSelect &&
        ((operation == "upgrade" && minSelect == 1 && maxSelect == 1) ||
         (operation == "remove" && minSelect >= 1 && minSelect <= maxSelect && maxSelect <= 8));
}
