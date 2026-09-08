using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV5;

public interface IGenericEventV5NativeAdapter : IDisposable
{
    GenericEventV5NativeCapture Capture();
    void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId);
    IGenericEventV5ChildSession CreateChild(object admissionIdentity);
    void CompleteParent();
}
public sealed record GenericEventV5NativeOption(object Identity, string StableId,
    string RenderedText, bool Enabled, bool Dangerous, bool IsProceed);
public sealed record GenericEventV5NativeCapture(string Status, bool EventFinished,
    IReadOnlyList<GenericEventV5NativeOption> Options, object? ChildIdentity = null,
    GenericEventV5Admission? Admission = null);

// Native-only immutable description. Clients never construct an admission.
public sealed record GenericEventV5Admission(object Identity, string Operation,
    int MinSelect, int MaxSelect, string CommitMode, int DomainCount)
{
    public bool IsSupported => Identity is not null &&
        GenericEventV5Families.Supports(Operation, MinSelect, MaxSelect, CommitMode, DomainCount);
}

public static class GenericEventV5Families
{
    public static string ContractVersion(string operation) => operation == "transform" ? "card_transform_v1" : "card_selection_v1";
    public static bool Supports(string operation, int minSelect, int maxSelect,
        string commitMode, int domainCount) => domainCount <= 64 && domainCount > maxSelect &&
        minSelect >= 1 && minSelect <= maxSelect && maxSelect <= 8 &&
        ((operation is "upgrade" or "transform" && minSelect == maxSelect && commitMode == "preview_confirm") ||
         (operation == "remove" && commitMode == "preview_confirm") ||
         (operation == "add" && commitMode is "auto_at_max" or "explicit_confirm"));
}
