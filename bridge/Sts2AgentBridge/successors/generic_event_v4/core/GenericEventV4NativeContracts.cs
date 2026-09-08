using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV4;

public interface IGenericEventV4NativeAdapter : IDisposable
{
    GenericEventV4NativeCapture Capture();
    void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId);
    CardSelectionV1Session CreateChild(object admissionIdentity);
    void CompleteParent();
}
public sealed record GenericEventV4NativeOption(object Identity, string StableId,
    string RenderedText, bool Enabled, bool Dangerous, bool IsProceed);
public sealed record GenericEventV4NativeCapture(string Status, bool EventFinished,
    IReadOnlyList<GenericEventV4NativeOption> Options, object? ChildIdentity = null,
    GenericEventV4Admission? Admission = null);

// Native-only immutable description. Clients never construct an admission.
public sealed record GenericEventV4Admission(object Identity, string Operation,
    int MinSelect, int MaxSelect, string CommitMode, int DomainCount)
{
    public bool IsSupported => Identity is not null &&
        GenericEventV4Families.Supports(Operation, MinSelect, MaxSelect, CommitMode, DomainCount);
}

public static class GenericEventV4Families
{
    public static bool Supports(string operation, int minSelect, int maxSelect,
        string commitMode, int domainCount) => domainCount <= 64 && domainCount > maxSelect &&
        minSelect >= 1 && minSelect <= maxSelect && maxSelect <= 8 &&
        ((operation == "upgrade" && minSelect == maxSelect && commitMode == "preview_confirm") ||
         (operation == "remove" && commitMode == "preview_confirm") ||
         (operation == "add" && commitMode is "auto_at_max" or "explicit_confirm"));
}
