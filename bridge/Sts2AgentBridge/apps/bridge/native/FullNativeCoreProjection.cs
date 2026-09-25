using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Rooms.Rest;
using static Sts2AgentBridge.Unified.FullPublicGraph;
using static Sts2AgentBridge.Unified.FullNativeState;

namespace Sts2AgentBridge.Unified;

internal sealed partial class FullNativeBackend
{
    private void AdoptAcquisitions()
    {
        if (_router.ActiveObservationSource is CampaignNavigation navigation)
            foreach (var acquired in navigation.Acquisitions) _state.Adopt("relic", acquired.Offer, acquired.Relic);
    }
    private JsonObject Combat(JsonElement wire)
    {
        var context = _state.PublicCombat();
        var player = _state.Player.PlayerCombatState!;
        var enemies = CombatManager.Instance.DebugOnlyGetState()!.Enemies.Where(e => e.IsAlive).ToArray();
        foreach (var row in wire.GetProperty("legal_actions").EnumerateArray())
        {
            string id = Text(row, "action_id")!;
            if (Text(row, "kind") == "end_turn") Command("combat", Text(wire, "decision_id")!, id, "end_turn");
            else
            {
                var card = player.Hand.Cards[row.GetProperty("hand_index").GetInt32()];
                var target = row.GetProperty("target_index");
                Command("combat", Text(wire, "decision_id")!, id, "play_card", _state.Ref("card", card),
                    target.ValueKind == JsonValueKind.Null ? null : _state.Ref("enemy", enemies[target.GetInt32()]));
            }
        }
        PotionCommands(enemies);
        return context;
    }
    private void PotionCommands(MegaCrit.Sts2.Core.Entities.Creatures.Creature[] enemies)
    {
        using var potions = ReadWire("potion");
        Require(Text(potions.RootElement, "status") == "ready");
        foreach (var action in potions.RootElement.GetProperty("legal_actions").EnumerateArray())
        {
            string id = action.GetString()!; string[] parts = id.Split(':');
            var potion = _state.Player.PotionSlots[int.Parse(parts[1])] ?? throw new AgentUnsupported();
            Command("potion", Text(potions.RootElement, "decision_id")!, id, parts[0]=="discard"?"discard_potion":"use_potion", _state.Ref("potion", potion),
                parts.Length == 3 ? _state.Ref("enemy", enemies[int.Parse(parts[2])]) : null);
        }
    }

    private JsonObject Selection(JsonElement wire)
    {
        var context = _state.PublicCombat();
        var surface = _choice.PublicSurface(Text(wire, "decision_id")!);
        _state.Bind(surface.Identity);
        var cards = new List<JsonObject>();
        foreach (var card in surface.Cards)
        {
            _state.Bind(card.Model); _state.Bind(card.Holder); if (card.NativeHolder is not null) _state.Bind(card.NativeHolder);
            Require(card.Model is CardModel);
            if (surface.Pile == "offer") cards.Add(_state.Card((CardModel)card.Model));
        }
        foreach (var action in wire.GetProperty("legal_actions").EnumerateArray())
        {
            string id = action.GetString()!;
            if (id == "confirm") Command("choice", Text(wire, "decision_id")!, id, "confirm_selection");
            else
            {
                string[] parts = id.Split(':');
                Command("choice", Text(wire, "decision_id")!, id, parts[0] == "select" ? "select_card" : "deselect_card",
                    _state.Ref("card", surface.Cards[int.Parse(parts[1])].Model));
            }
        }
        context["children"]!.AsArray().Add(Node("selection", surface.Pile,
            fields: new (string, object?)[] { ("minimum", surface.MinSelect), ("maximum", surface.MaxSelect),
                ("manual_confirmation", surface.ManualConfirmation), ("cancelable", surface.Cancelable) }, children: cards,
            links: new[] {
                ("options", surface.Cards.Select(c => _state.Ref("card", c.Model))),
                ("selected", (surface.SelectedOrder ?? (surface.Pile == "offer" ? Array.Empty<object>() : throw new AgentUnsupported())).Select(c => _state.Ref("card", c))) }));
        return context;
    }

    private JsonObject Map(JsonElement wire)
    {
        var reachable = new List<string>();
        foreach (var action in wire.GetProperty("legal_actions").EnumerateArray())
        {
            var target = wire.GetProperty("candidates")[action.GetProperty("candidate_index").GetInt32()];
            string position = target.GetProperty("row").GetInt32() + ":" + target.GetProperty("col").GetInt32();
            Require(_state.MapCoordinates.TryGetValue(position, out var point));
            string reference = _state.Ref("node", point!); reachable.Add(reference);
            Command("map", Text(wire, "decision_id")!, Text(action, "action_id")!, "choose_map_node", reference);
        }
        PotionCommands(Array.Empty<MegaCrit.Sts2.Core.Entities.Creatures.Creature>());
        return Node("map", links: new[] { ("reachable", (IEnumerable<string>)reachable) });
    }

    private JsonObject Rewards(JsonElement wire) => RewardContext(_rewards.InteractionSession, Text(wire, "decision_id")!,
        Text(wire, "screen_kind") == "card_reward", wire.GetProperty("legal_actions").EnumerateArray().Select(a => Text(a, "action_id")!).ToArray(),
        (action, kind, subject, target) => Command("reward", Text(wire, "decision_id")!, action, kind, subject, target));

    private JsonObject RewardContext(PinnedPublicRewardInteractionSession session, string decision, bool child,
        IEnumerable<string> actions, Action<string, string, string?, string?> command)
    {
        Require(ReferenceEquals(session.Player, _state.Player));
        var entries = new List<JsonObject>();
        var subjects = new Dictionary<int, (string Ref, string Kind)>();
        var offers = new Dictionary<int, string>();
        if (child)
        {
            var parent = session.ActiveCardReward ?? throw new AgentUnsupported();
            _state.Bind(parent.Reward); string reference = _state.Ref("reward", parent.Reward);
            var cards = new List<JsonObject>();
            for (int index = 0; session.TryGetCardTarget(decision, index, out var screen, out var target); index++)
            {
                Require(index < 5); _state.Bind(screen!); _state.Bind(target!.Holder);
                cards.Add(_state.Card(target.Model)); offers.Add(index, _state.Ref("card", target.Model));
            }
            Require(cards.Count > 0); subjects.Add(0, (reference, "card"));
            entries.Add(Node("reward", "card", reference, new (string, object?)[] { ("opened", true), ("resolved", false) }, cards));
        }
        else
        {
            for (int index = 0; session.TryGetParentTarget(decision, index, out var screen, out var target); index++)
            {
                Require(index < 32); _state.Bind(screen!); _state.Bind(target!.Button); _state.Bind(target.Reward);
                string reference = _state.Ref("reward", target.Reward);
                string kind = target.Reward switch { GoldReward => "gold", CardReward => "card", SpecialCardReward => "special_card", PotionReward => "potion", RelicReward => "relic", _ => throw new AgentUnsupported() };
                bool resolved = target.Reward.SuccessfullySelected || session.WasSkipped(target.Reward);
                var children = new List<JsonObject>();
                if (!resolved && kind is "potion" or "relic")
                    children.Add(PinnedPublicItemRewardClaim.Model(target.Reward) switch {
                        PotionModel potion => _state.Potion(potion), RelicModel relic => _state.Relic(relic), _ => throw new AgentUnsupported() });
                if (!resolved && kind == "special_card") { var card = PinnedPublicSpecialCardClaim.Card(target.Reward) ?? throw new AgentUnsupported(); children.Add(_state.Card(card)); offers.Add(index, _state.Ref("card", card)); }
                subjects.Add(index, (reference, kind));
                // Closed card offers are precomputed private state and stay out.
                entries.Add(Node("reward", kind, reference, new (string, object?)[] {
                    ("opened", false), ("resolved", resolved), ("amount", !resolved && target.Reward is GoldReward gold ? gold.Amount : null) }, children));
            }
        }
        foreach (string action in actions)
        {
            var parts = action.Split(':');
            switch (parts[0])
            {
                case "claim": case "collect":
                    var item = subjects[int.Parse(parts[1])]; command(action, "claim_" + item.Kind, item.Ref, null); break;
                case "open": command(action, "open_reward", subjects[int.Parse(parts[1])].Ref, null); break;
                case "take": command(action, "choose_reward_card", subjects[int.Parse(parts[1])].Ref, offers[int.Parse(parts[1])]); break;
                case "choose": command(action, "choose_reward_card", subjects[0].Ref, offers[int.Parse(parts[1])]); break;
                case "skip_card": command(action, "skip_reward", subjects[0].Ref, null); break;
                case "reroll": command(action, "reroll_card_reward", subjects[0].Ref, null); break;
                case "sacrifice": command(action, "sacrifice_card_reward", subjects[0].Ref, null); break;
                case "proceed": case "dismiss": command(action, "leave_rewards", null, null); break;
                case "discard":
                    var potion = _state.Player.PotionSlots[int.Parse(parts[1])] ?? throw new AgentUnsupported();
                    command(action, "discard_potion", _state.Ref("potion", potion), null); break;
                case "skip_remaining": command(action, "skip_reward", null, null); break;
                default: throw new AgentUnsupported();
            }
        }
        return Node("rewards", children: entries);
    }

    private JsonObject Rest(JsonElement wire)
    {
        var session = _router.ActiveObservationSource as RestInteractiveSession ?? throw new AgentUnsupported();
        string decision = Text(wire, "decision_id")!;
        var native = session.Inspect(decision);
        Require(ReferenceEquals(native.Surface.Player, _state.Player));
        _state.Bind(native.Surface.Room); _state.Bind(native.Surface.Map);
        string phase = Text(wire, "phase")!;
        var children = new List<JsonObject>();
        if (phase == "rewards")
        {
            var rewards = native.Rewards ?? throw new AgentUnsupported();
            children.Add(RewardContext((rewards.Reader ?? throw new AgentUnsupported()).InteractionSession, native.RewardDecision, Text(wire, "screen_kind") == "card_reward",
                wire.GetProperty("legal_actions").EnumerateArray().Select(a => a.GetString()![7..]),
                (action, kind, subject, target) => Command("rest", decision, "reward:" + action, kind, subject, target)));
        }
        else if (phase == "selection")
        {
            var choice = native.Choice ?? throw new AgentUnsupported();
            foreach (var card in choice.Domain) { Require(_state.Player.Deck.Cards.Contains(card)); _state.Bind(card); }
            string source = Text(wire, "parent_action")!;
            bool cook = source == "option:cook";
            bool relic = !cook && source != "option:smith";
            children.Add(Node("selection", source[7..], fields: new (string, object?)[] {
                ("minimum", choice.Minimum), ("maximum", choice.Maximum), ("cancelable", choice.Cancelable), ("manual_confirmation", true) },
                links: new[] { ("options", choice.Domain.Select(c => _state.Ref("card", c))), ("selected", choice.Selected.Select(c => _state.Ref("card", c))) }));
            foreach (var row in wire.GetProperty("legal_actions").EnumerateArray())
            {
                string action = row.GetString()!; var parts = action.Split(':');
                string kind = parts[0] switch {
                    "confirm" => cook ? "confirm_cook" : relic ? "confirm_relic_selection" : "confirm_selection", "cancel" => "cancel_selection",
                    "select" => cook ? "choose_cook_card" : relic ? "choose_relic_card" : "choose_upgrade",
                    "deselect" => cook ? "deselect_cook_card" : relic ? "deselect_relic_card" : "deselect_card",
                    _ => throw new AgentUnsupported() };
                Command("rest", decision, action, kind, parts.Length == 2 ? _state.Ref("card", choice.Domain[int.Parse(parts[1])]) : null);
            }
            if (relic) return Node("relic_choice", "card_grid", fields: new (string, object?)[] {
                ("minimum", choice.Minimum), ("maximum", choice.Maximum), ("cancelable", choice.Cancelable) },
                links: new[] { ("options", choice.Domain.Select(c => _state.Ref("card", c))), ("selected", choice.Selected.Select(c => _state.Ref("card", c))) });
        }
        else
        {
            Require(phase == "option");
            foreach (var option in native.Surface.Options)
            {
                _state.Bind(option.Option); _state.Bind(option.Button); _state.Bind(option.Relic);
                string reference = _state.Ref("option", option.Option);
                children.Add(Node("option", option.Public.ActionId, reference, new (string, object?)[] {
                    ("enabled", option.Public.Enabled), ("counter", option.Public.Counter), ("amount", option.Public.Amount) }));
                if (!option.Public.Enabled) continue;
                string kind = option.Public.ActionId switch { "heal" => "rest", "smith" => "smith", "hatch" => "hatch", "lift" => "lift", "dig" => "dig", _ => "use_rest_relic" };
                // Standard rest commands have no subject in the shared contract.
                Command("rest", decision, "option:" + option.Public.ActionId, kind, kind == "use_rest_relic" ? reference : null);
            }
            if (wire.GetProperty("legal_actions").EnumerateArray().Any(a => a.GetString() == "leave")) Command("rest", decision, "leave", "leave_rest");
        }
        return Node("rest", fields: new (string, object?)[] { ("phase", phase) }, children: children);
    }

    private JsonObject Navigation(JsonElement wire)
    {
        string surface = Text(wire, "surface")!;
        Require(surface is "treasure" or "shop");
        RelicModel? relic = wire.GetProperty("legal_actions").EnumerateArray().Any(a => a.GetString() == "claim_relic")
            ? (_router.ActiveObservationSource as CampaignNavigation)?.OfferedRelic ?? throw new AgentUnsupported() : null;
        string? relicRef = relic is null ? null : _state.Ref("relic", ((CampaignNavigation)_router.ActiveObservationSource!).OfferIdentity);
        if (relic is not null) _state.Bind(relic);
        foreach (var row in wire.GetProperty("legal_actions").EnumerateArray())
        {
            string action = row.GetString()!;
            Command("navigation", Text(wire, "decision_id")!, action, action switch {
                "open_chest" => "open_chest", "skip_relic" => "leave_treasure", "claim_relic" => "claim_treasure_relic",
                "proceed" when surface == "treasure" => "leave_treasure", "proceed" when surface == "shop" => "leave_shop",
                _ => throw new AgentUnsupported() }, action == "claim_relic" ? relicRef : null);
        }
        return Node(surface, children: relic is null ? Array.Empty<JsonObject>() : new[] { FullNativeDisplay.Relic(relic, relicRef!) });
    }
}
