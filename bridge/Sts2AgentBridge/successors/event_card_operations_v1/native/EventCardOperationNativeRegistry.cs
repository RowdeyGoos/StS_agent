using System;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Native;

internal enum EventCardOperationEventClass
{
    Ordinary = 1,
    SelectedAroma = 2,
    SelectedSapphire = 3,
    KnownUnsupported = 4,
}

// Closed, exact-type native classification derived from the accepted positive
// caller census. Only the two separately selected option rows are enabled.
internal static class EventCardOperationNativeRegistry
{
    internal const string AromaSupportedKey =
        "AROMA_OF_CHAOS.pages.INITIAL.options.MAINTAIN_CONTROL";
    internal const string AromaUnsupportedKey =
        "AROMA_OF_CHAOS.pages.INITIAL.options.LET_GO";
    internal const string SapphireSupportedKey =
        "SAPPHIRE_SEED.pages.INITIAL.options.EAT";
    internal const string SapphireUnsupportedKey =
        "SAPPHIRE_SEED.pages.INITIAL.options.PLANT";

    internal static EventCardOperationEventClass Classify(EventModel model)
    {
        Type type = model.GetType();
        if (type == typeof(AromaOfChaos))
            return EventCardOperationEventClass.SelectedAroma;
        if (type == typeof(SapphireSeed))
            return EventCardOperationEventClass.SelectedSapphire;
        if (type == typeof(RoomFullOfCheese))
            return EventCardOperationEventClass.Ordinary;
        // `is` is deliberate only on the rejection side: subclasses of every
        // closed caller remain unsupported and can never inherit item behavior.
        if (model is AromaOfChaos or SapphireSeed or RoomFullOfCheese or
            Amalgamator or BattlewornDummy or BrainLeech or Bugslayer or
            ByrdonisNest or DoorsOfLightAndDark or EndlessConveyor or
            FieldOfManSizedHoles or GraveOfTheForgotten or InfestedAutomaton or
            LuminousChoir or MorphicGrove or Reflections or SelfHelpBook or
            SlipperyBridge or SpiralingWhirlpool or SpiritGrafter or
            StoneOfAllTime or Symbiote or TabletOfTruth or TheLegendsWereTrue or
            TinkerTime or TrashHeap or Trial or WarHistorianRepy or
            WaterloggedScriptorium or Wellspring or WhisperingHollow or
            WoodCarvings or ZenWeaver)
            return EventCardOperationEventClass.KnownUnsupported;
        return EventCardOperationEventClass.Ordinary;
    }

    internal static bool TryGetSelectedDefinition(
        EventCardOperationEventClass eventClass,
        string key,
        out EventOrchestratorV1CardPolicyDefinition? definition,
        out bool knownUnsupported)
    {
        definition = null;
        knownUnsupported = false;
        string? policyId = null;
        switch (eventClass)
        {
            case EventCardOperationEventClass.SelectedAroma:
                if (string.Equals(key, AromaSupportedKey, StringComparison.Ordinal))
                    policyId = "aroma_maintain_control_upgrade_one";
                else if (string.Equals(key, AromaUnsupportedKey, StringComparison.Ordinal))
                    knownUnsupported = true;
                else return false;
                break;
            case EventCardOperationEventClass.SelectedSapphire:
                if (string.Equals(key, SapphireSupportedKey, StringComparison.Ordinal))
                    policyId = "sapphire_eat_upgrade_one";
                else if (string.Equals(key, SapphireUnsupportedKey, StringComparison.Ordinal))
                    knownUnsupported = true;
                else return false;
                break;
            default:
                return false;
        }
        return knownUnsupported ||
            EventOrchestratorV1CardPolicyCatalog.TryGet(policyId, out definition) &&
            definition is not null;
    }
}
