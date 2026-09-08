using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV6;

public interface IGenericEventV6NativeAdapter : IDisposable
{
    GenericEventV6NativeCapture Capture();
    void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId);
    IGenericEventV6ChildSession CreateChild(object admissionIdentity);
    void CompleteParent();
}
public sealed record GenericEventV6NativeOption(object Identity, string StableId,
    string RenderedText, bool Enabled, bool Dangerous, bool IsProceed);
public sealed record GenericEventV6NativeCapture(string Status, bool EventFinished,
    IReadOnlyList<GenericEventV6NativeOption> Options, object? ChildIdentity = null,
    GenericEventV6Admission? Admission = null);

// Native-only closed admission family; identity never crosses the wire.
public abstract record GenericEventV6Admission(object Identity) {
    public bool IsSupported => Identity is not null && (this switch {
        GenericEventV6CardAdmission c => GenericEventV6Families.Supports(c.Operation,c.MinSelect,c.MaxSelect,c.CommitMode,c.DomainCount),
        GenericEventV6ItemAdmission i => i.OfferCount == 1,
        _ => false });
}
public sealed record GenericEventV6CardAdmission(object AdmissionIdentity, string Operation,
    int MinSelect, int MaxSelect, string CommitMode, int DomainCount) : GenericEventV6Admission(AdmissionIdentity);
public sealed record GenericEventV6ItemAdmission(object AdmissionIdentity, int OfferCount) : GenericEventV6Admission(AdmissionIdentity);

public static class GenericEventV6Families
{
    public static string ContractVersion(string operation) => operation == "transform" ? "card_transform_v1" : "card_selection_v1";
    public static bool Supports(string operation, int minSelect, int maxSelect,
        string commitMode, int domainCount) => domainCount <= 64 && domainCount > maxSelect &&
        minSelect >= 1 && minSelect <= maxSelect && maxSelect <= 8 &&
        ((operation is "upgrade" or "transform" && minSelect == maxSelect && commitMode == "preview_confirm") ||
         (operation == "remove" && commitMode == "preview_confirm") ||
         (operation == "add" && commitMode is "auto_at_max" or "explicit_confirm"));
}
