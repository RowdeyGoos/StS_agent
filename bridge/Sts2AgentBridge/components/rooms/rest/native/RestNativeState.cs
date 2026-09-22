using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using CloneEnchantment = MegaCrit.Sts2.Core.Models.Enchantments.Clone;

namespace Sts2AgentBridge.Rooms.Rest;

// Only current public inventory is captured. Relic pools and RNG are never read.
internal sealed class RestNativeState : IEquatable<RestNativeState>
{
    internal sealed record Card(CardModel Model, string Key, int Upgrade, bool Removable,
        EnchantmentModel? Enchantment, string? EnchantmentKey, decimal Amount)
    {
        internal static Card Read(CardModel c) => new(c, c.Id.Entry, c.CurrentUpgradeLevel, c.IsRemovable,
            c.Enchantment, c.Enchantment?.Id.Entry, c.Enchantment?.Amount ?? 0);
    }
    internal readonly Player Player;
    internal readonly object RunState;
    internal readonly Card[] Deck;
    internal readonly RelicModel[] Relics;
    internal readonly PotionModel?[] Potions;
    internal readonly int Gold, Hp, MaxHp;
    internal RestNativeState(Player player)
    {
        Player = player; RunState = player.RunState; Deck = player.Deck.Cards.Select(Card.Read).ToArray(); Relics = player.Relics.ToArray();
        Potions = player.PotionSlots.ToArray(); Gold = player.Gold; Hp = player.Creature.CurrentHp; MaxHp = player.Creature.MaxHp;
        if (Deck.Length > 128 || Relics.Length > 128 || Potions.Length > 8 ||
            Relics.Distinct(ReferenceEqualityComparer.Instance).Count() != Relics.Length || Relics.Any(r => !ReferenceEquals(r.Owner, player)) ||
            Deck.Select(c => c.Model).Distinct(ReferenceEqualityComparer.Instance).Count() != Deck.Length ||
            Deck.Any(c => !ReferenceEquals(c.Model.Owner, player) || !ReferenceEquals(c.Model.RunState, player.RunState)))
            throw new InvalidOperationException("rest_inventory_boundary");
    }
    internal RestV2Card[] PublicCards => Deck.Select((c, i) => new RestV2Card(i, c.Key, c.Upgrade, c.Removable)).ToArray();
    internal Card[] Eggs => Deck.Where(c => c.Model.GetType() == typeof(ByrdonisEgg)).ToArray();
    internal Card[] Clonable => Deck.Where(c => c.Enchantment?.GetType() == typeof(CloneEnchantment)).ToArray();
    public bool Equals(RestNativeState? other) => other is not null && ReferenceEquals(Player, other.Player) &&
        ReferenceEquals(RunState, other.RunState) && Gold == other.Gold && Hp == other.Hp && MaxHp == other.MaxHp && Deck.SequenceEqual(other.Deck) &&
        Relics.SequenceEqual(other.Relics, ReferenceEqualityComparer.Instance) && Potions.SequenceEqual(other.Potions, ReferenceEqualityComparer.Instance);
    public override bool Equals(object? other) => other is RestNativeState state && Equals(state);
    public override int GetHashCode() => System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(Player);
}
