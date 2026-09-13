using System;
using System.Reflection;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using Sts2AgentBridge.Items.Native;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

internal static class ShopRelicRules
{
    internal static bool Ready(MerchantRelicEntry entry, Player player) =>
        ShopPotionOwnership.LocalEntry(entry, player) && entry.IsStocked && entry.Model is not null && entry.Model.Owner is null;
    internal static bool Pending(MerchantRelicEntry entry, Player player) =>
        ShopPotionOwnership.LocalEntry(entry, player) && (entry.Model is null || entry.Model.Owner is null || ReferenceEquals(entry.Model.Owner, player));

    // Base AfterObtained is a completed task in the pinned build. Overrides may
    // open selectors or change inventory; only the exact known capacity effect is admitted.
    internal static bool TryEffect(RelicModel relic, out int capacityGain)
    {
        capacityGain = 0;
        if (relic.GetType() == typeof(PotionBelt)) {
            try { capacityGain = PinnedPotionCapacity.Gain(relic); return capacityGain == 2; }
            catch (InvalidOperationException) { return false; }
        }
        var method = relic.GetType().GetMethod("AfterObtained", BindingFlags.Instance | BindingFlags.Public,
            null, Type.EmptyTypes, null);
        return method?.DeclaringType == typeof(RelicModel) && method.ReturnType == typeof(Task) && !method.IsGenericMethod;
    }
}
