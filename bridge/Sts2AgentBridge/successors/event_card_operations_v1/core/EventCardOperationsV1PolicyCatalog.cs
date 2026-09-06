using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1;

// Production policy rows are isolated here so adding an independently accepted
// native caller never changes the frozen structural contracts.
public static class EventOrchestratorV1CardPolicyCatalog
{
    private static readonly EventOrchestratorV1CardPolicyDefinition Cheese = new(
        EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo,
        EventOrchestratorV1Limits.CheeseGorgeAddTwoPolicy,
        "ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE",
        CardSelectionV1Operation.Add, 2, 2,
        CardSelectionV1CommitMode.AutoAtMax,
        EventOrchestratorV1CardDomainSource.GeneratedAtAdmission, 8, 8);
    private static readonly EventOrchestratorV1CardPolicyDefinition AromaMaintainControl = new(
        EventOrchestratorV1ChildPolicyKind.EventCardSelection,
        "aroma_maintain_control_upgrade_one",
        "AROMA_OF_CHAOS.pages.INITIAL.options.MAINTAIN_CONTROL",
        CardSelectionV1Operation.Upgrade, 1, 1,
        CardSelectionV1CommitMode.PreviewConfirm,
        EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 2, 64);
    private static readonly EventOrchestratorV1CardPolicyDefinition SapphireEat = new(
        EventOrchestratorV1ChildPolicyKind.EventCardSelection,
        "sapphire_eat_upgrade_one",
        "SAPPHIRE_SEED.pages.INITIAL.options.EAT",
        CardSelectionV1Operation.Upgrade, 1, 1,
        CardSelectionV1CommitMode.PreviewConfirm,
        EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 2, 64);
    private static readonly IReadOnlyList<EventOrchestratorV1CardPolicyDefinition> Rows =
        BuildRows();

    public static IReadOnlyList<EventOrchestratorV1CardPolicyDefinition> Definitions => Rows;

    // Rows are added only after their exact native caller evidence is accepted.
    public static bool TryGet(
        string? policyId,
        out EventOrchestratorV1CardPolicyDefinition? definition)
    {
        foreach (EventOrchestratorV1CardPolicyDefinition row in Rows)
        {
            if (string.Equals(policyId, row.PolicyId, StringComparison.Ordinal))
            {
                definition = row;
                return true;
            }
        }
        definition = null;
        return false;
    }

    private static IReadOnlyList<EventOrchestratorV1CardPolicyDefinition> BuildRows()
    {
        EventOrchestratorV1CardPolicyDefinition[] rows =
            { Cheese, AromaMaintainControl, SapphireEat };
        var policyIds = new HashSet<string>(StringComparer.Ordinal);
        var stableIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (EventOrchestratorV1CardPolicyDefinition row in rows)
            if (!policyIds.Add(row.PolicyId) || !stableIds.Add(row.ParentStableId))
                throw new InvalidOperationException("Duplicate event card policy row.");
        return Array.AsReadOnly(rows);
    }
}
