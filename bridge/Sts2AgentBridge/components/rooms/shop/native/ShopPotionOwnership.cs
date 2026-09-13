using System;
using System.Reflection;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

// MerchantEntry retains the player its purchase callback will debit and mutate.
internal static class ShopPotionOwnership
{
    private static readonly FieldInfo? EntryPlayer = typeof(MerchantEntry).GetField(
        "_player", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);

    internal static bool LocalEntry(MerchantEntry entry, Player player) =>
        EntryPlayer is { IsStatic: false } && EntryPlayer.FieldType == typeof(Player) &&
        ReferenceEquals(EntryPlayer.GetValue(entry), player);

    internal static bool Ready(MerchantPotionEntry entry, Player player) =>
        LocalEntry(entry, player) && entry.IsStocked && entry.Model is not null && entry.Model.Owner is null;

    // Procurement assigns the owner before gold debit and before stock clearing.
    internal static bool Pending(MerchantPotionEntry entry, Player player) =>
        LocalEntry(entry, player) && (entry.Model is null || entry.Model.Owner is null ||
            ReferenceEquals(entry.Model.Owner, player));
}
