using System;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Tests.Public;

internal static class ProcessBudgetMultiFloorTestHelper
{
    public static void Run()
    {
        TestAssert.Equal(3, PublicProcessActionBudget.MaximumFloors, "bounded floor count");
        TestAssert.Equal(
            48,
            PublicCombatActionBudget.MaximumAcceptedActionsPerCombat,
            "per-combat host-compatible action budget");
        TestAssert.Equal(
            144,
            PublicCombatActionBudget.MaximumAcceptedActions,
            "three-combat process action budget");
        TestAssert.Equal(
            3,
            PublicMapActionBudget.MaximumAcceptedActions,
            "three-map process action budget");
        TestAssert.Equal(
            210,
            PublicProcessActionBudget.MaximumAcceptedActions(
                PublicRewardActionBudget.MaximumAcceptedActionsPerProcess),
            "three-floor aggregate process action budget");
        TestAssert.Throws<ArgumentOutOfRangeException>(
            () => PublicProcessActionBudget.MaximumAcceptedActions(-1),
            "negative reward budget rejected");
    }
}
