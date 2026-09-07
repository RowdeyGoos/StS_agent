using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV3;

public interface IGenericEventV3NativeAdapter : IDisposable
{
    GenericEventV3NativeCapture Capture();
    void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId);
    CardSelectionV1Session CreateChild(object admissionIdentity);
    void CompleteParent();
}
public sealed record GenericEventV3NativeOption(object Identity, string StableId,
    string RenderedText, bool Enabled, bool Dangerous, bool IsProceed);
public sealed record GenericEventV3NativeCapture(string Status, bool EventFinished,
    IReadOnlyList<GenericEventV3NativeOption> Options, object? ChildIdentity = null,
    GenericEventV3Admission? Admission = null);

// Native-only immutable description. Clients never construct an admission.
public sealed record GenericEventV3Admission(object Identity, string Operation,
    int MinSelect, int MaxSelect, string CommitMode, int DomainCount)
{
    public bool IsSupported => Identity is not null &&
        GenericEventV3Families.Supports(Operation, MinSelect, MaxSelect, CommitMode, DomainCount);
}

public static class GenericEventV3Families
{
    public static bool Supports(string operation, int minSelect, int maxSelect,
        string commitMode, int domainCount) => domainCount <= 64 && domainCount > maxSelect &&
        minSelect >= 1 && minSelect <= maxSelect && maxSelect <= 8 &&
        ((operation == "upgrade" && minSelect == 1 && maxSelect == 1 && commitMode == "preview_confirm") ||
         (operation == "remove" && commitMode == "preview_confirm") ||
         (operation == "add" && commitMode is "auto_at_max" or "explicit_confirm"));
}
