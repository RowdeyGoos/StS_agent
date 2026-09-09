using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV7;

public interface IGenericEventV7NativeAdapter : IDisposable
{
    // While a parent action is pending, "parent" requires its owned Chosen
    // task to have succeeded and all child/overlay work to have settled. An owned
    // ancient dialogue action instead requires its exact next native line.
    // Option identities stay stable for the lifetime of each native control.
    GenericEventV7NativeCapture Capture();
    void Dispatch(object candidateIdentity, string nonce, string decisionId, string actionId);
    IGenericEventV7ChildSession CreateChild(object admissionIdentity);
    void CompleteParent();
}
public sealed record GenericEventV7NativeOption(object Identity, string StableId,
    string RenderedText, bool Enabled, bool Dangerous, bool IsProceed);
public sealed record GenericEventV7NativeCapture(string Status, bool EventFinished,
    IReadOnlyList<GenericEventV7NativeOption> Options, object? ChildIdentity = null,
    GenericEventV7Admission? Admission = null);

// Native-only closed admission family; identity never crosses the wire.
public abstract record GenericEventV7Admission(object Identity) {
    public bool IsSupported => Identity is not null && (this switch {
        GenericEventV7CardAdmission c => GenericEventV7Families.Supports(c.Operation,c.MinSelect,c.MaxSelect,c.CommitMode,c.DomainCount),
        GenericEventV7OfferAdmission o => o.OfferCount is >=1 and <=5,
        GenericEventV7RewardAdmission r => r.OfferCount is >=1 and <=8 && (!r.Mixed || r.OfferCount>=2),
        GenericEventV7ItemAdmission i => i.OfferCount is >= 1 and <= 8,
        _ => false });
}
public sealed record GenericEventV7CardAdmission(object AdmissionIdentity, string Operation,
    int MinSelect, int MaxSelect, string CommitMode, int DomainCount) : GenericEventV7Admission(AdmissionIdentity);
public sealed record GenericEventV7OfferAdmission(object AdmissionIdentity,int OfferCount,bool Bundle):GenericEventV7Admission(AdmissionIdentity);
public sealed record GenericEventV7RewardAdmission(object AdmissionIdentity,int OfferCount=1,bool Mixed=false) : GenericEventV7Admission(AdmissionIdentity);
public sealed record GenericEventV7ItemAdmission(object AdmissionIdentity, int OfferCount) : GenericEventV7Admission(AdmissionIdentity);

public static class GenericEventV7Families
{
    public static string ContractVersion(string operation, int maxSelect = 1, int minSelect = 1) => minSelect == 0 ? (operation=="add"?"card_add_v2":"card_transform_v3") : operation == "remove" ? "card_remove_v2" : operation == "enchant" ? (maxSelect>1?"card_enchant_v2":"card_enchant_v1") : operation == "transform" ? "card_transform_v2" : "card_selection_v1";
    public static bool Supports(string operation, int minSelect, int maxSelect,
        string commitMode, int domainCount) => minSelect==0
        ? domainCount is >=1 and <=64 && maxSelect>=1 &&
          (operation=="add" && maxSelect<=15 && commitMode=="explicit_confirm" || operation=="transform" && maxSelect<=8 && commitMode=="preview_confirm")
        : domainCount <= 64 && domainCount > maxSelect &&
        minSelect >= 1 && minSelect <= maxSelect && maxSelect <= 8 &&
        ((operation == "enchant" && minSelect == maxSelect && commitMode == "preview_confirm") ||
         (operation == "upgrade" && minSelect == maxSelect && commitMode == "preview_confirm") ||
         (operation is "remove" or "transform" && commitMode == "preview_confirm") ||
         (operation == "add" && commitMode is "auto_at_max" or "explicit_confirm"));
}
