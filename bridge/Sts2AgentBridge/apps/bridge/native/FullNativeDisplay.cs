using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using static Sts2AgentBridge.Unified.FullPublicGraph;

namespace Sts2AgentBridge.Unified;

// Native descriptions are display facts, not reconstructed headless CardSpecs.
// In particular an adjusted damage preview never becomes spec.base_damage.
internal static class FullNativeDisplay
{
    // Only uncovered fragments reach this method. These pinned fields select
    // the displayed texture/banner; no generated reward, extent or RNG is read.
    internal static string SphereFragment(object? item)
    {
        object? Field(string name) => item!.GetType().GetField(name,
            BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)?.GetValue(item);
        return item?.GetType().Name switch {
            null => "empty",
            "CrystalSphereCardReward" => Field("_rarity")?.ToString() switch {
                "Common" => "card_common", "Uncommon" => "card_uncommon", "Rare" => "card_rare", _ => throw new AgentUnsupported() },
            "CrystalSpherePotion" => Field("_rarity")?.ToString() switch {
                "Common" => "potion_common", "Rare" => "potion_rare", _ => throw new AgentUnsupported() },
            "CrystalSphereGold" => Field("_isBig") switch {
                false => "gold_small", true => "gold_big", _ => throw new AgentUnsupported() },
            "CrystalSphereCurse" => "curse", "CrystalSphereRelic" => "relic", _ => throw new AgentUnsupported() };
    }
    internal static JsonObject Hover(IHoverTip tip) => tip switch {
        HoverTip text => Node("tooltip", fields: new (string, object?)[] { ("title", text.Title), ("description", text.Description) }),
        CardHoverTip card => Node("card_preview", children: new[] { Card(card.Card) }),
        _ => throw new AgentUnsupported()
    };
    private static readonly MethodInfo ExtraCardArguments = typeof(CardModel).GetMethod("AddExtraArgsToDescription",
        BindingFlags.Instance | BindingFlags.NonPublic, null, new[] { typeof(LocString) }, null)
        ?? throw new InvalidOperationException("Missing pinned description formatter.");

    internal static string CardKey(CardModel card) => card.Id.Entry switch
    { "STRIKE_IRONCLAD" => "strike", "DEFEND_IRONCLAD" => "defend", _ => card.Id.Entry.ToLowerInvariant() };

    internal static JsonObject Card(CardModel card, string? reference = null)
    {
        // The native card formatter uses these same arguments. All preview and
        // formatting writes target detached variables, never the card's cache.
        var variables = card.DynamicVars.Clone(card);
        card.UpdateDynamicVarPreview(CardPreviewMode.Normal, null, variables);
        var description = card.Description;
        variables.AddTo(description);
        ExtraCardArguments.Invoke(card, new object[] { description });
        description.Add(new IfUpgradedVar(card.IsUpgraded ? UpgradeDisplay.Upgraded : UpgradeDisplay.Normal));
        description.Add("OnTable", card.Pile?.Type is PileType.Hand or PileType.Play);
        description.Add("InCombat", CombatManager.Instance.IsInProgress && card.Pile?.IsCombatPile == true);
        description.Add("IsTargeting", false);
        description.Add("TargetType", card.TargetType.ToString());
        description.Add("GainsBlock", card.GainsBlock);
        description.Add("IsOstyAlive", card.IsMutable && card.Owner?.IsOstyAlive == true);
        string prefix = EnergyIconHelper.GetPrefix(card);
        description.Add("energyPrefix", prefix);
        description.Add("singleStarIcon", "[img]res://images/packed/sprite_fonts/star_icon.png[/img]");
        foreach (var value in variables.Values.OfType<EnergyVar>()) value.ColorPrefix = prefix;

        var children = new List<JsonObject>();
        var preview = new List<(string, object?)>();
        // These are conventional native displayed attack/block labels. Other
        // mechanics remain in the formatted description, without exporting every
        // dynamic variable (which need not itself be displayed).
        foreach (var value in variables.Values)
            if (value.Name is "Damage" or "Block")
            {
                if (Math.Abs(value.PreviewValue) > int.MaxValue) throw new AgentUnsupported();
                preview.Add((value.Name == "Damage" ? "damage" : "block", (int)value.PreviewValue));
            }
        children.Add(Node("preview", "native_display", fields: preview));
        foreach (var keyword in card.Keywords.OrderBy(k => k.ToString(), StringComparer.Ordinal))
            children.Add(Node("keyword", keyword.ToString().ToLowerInvariant()));
        if (card.Enchantment is {} enchantment)
            children.Add(Node("enchantment", enchantment.Id.Entry.ToLowerInvariant(), fields: new (string, object?)[] {
                ("title", enchantment.Title.GetFormattedText()), ("description", enchantment.DynamicDescription.GetFormattedText()),
                ("show_counter", enchantment.ShowAmount), ("display_counter", enchantment.ShowAmount ? enchantment.DisplayAmount : null) }));
        if (card.Affliction is {} affliction)
            children.Add(Node("affliction", affliction.Id.Entry.ToLowerInvariant(), fields: new (string, object?)[] {
                ("title", affliction.Title.GetFormattedText()), ("description", affliction.DynamicDescription.GetFormattedText()) }));
        int energy = card.EnergyCost.GetWithModifiers(CostModifiers.All), stars = card.GetStarCostWithModifiers();
        return Node("card", CardKey(card), reference, new (string, object?)[] {
            ("upgrade_level", card.CurrentUpgradeLevel), ("energy", energy < 0 ? null : energy),
            ("energy_x", card.EnergyCost.CostsX), ("stars", stars < 0 ? null : stars), ("stars_x", card.HasStarCostX),
            ("title", card.Title), ("description", description.GetFormattedText()),
            ("rarity", card.Rarity.ToString().ToLowerInvariant()), ("type", card.Type.ToString().ToLowerInvariant()),
            ("target_type", card.TargetType.ToString().ToLowerInvariant()),
            ("retain", card.ShouldRetainThisTurn), ("sly", card.IsSlyThisTurn), ("replay", card.GetEnchantedReplayCount()) }, children);
    }

    internal static JsonObject Relic(RelicModel relic, string reference)
    {
        var tip = relic.HoverTip;
        return Node("relic", relic.Id.Entry.ToLowerInvariant(), reference, new (string, object?)[] {
            ("show_counter", relic.ShowCounter), ("display_counter", relic.ShowCounter ? relic.DisplayAmount : null),
            ("status", relic.Status.ToString().ToLowerInvariant()), ("title", tip.Title), ("description", tip.Description) });
    }

    internal static JsonObject Potion(PotionModel potion, string reference) =>
        Node("potion", potion.Id.Entry.ToLowerInvariant(), reference, new (string, object?)[] {
            ("title", potion.Title.GetFormattedText()), ("description", potion.DynamicDescription.GetFormattedText()),
            ("target_type", potion.TargetType.ToString().ToLowerInvariant()) });
}
