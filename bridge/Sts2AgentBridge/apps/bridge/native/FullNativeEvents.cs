using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Rooms;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using static Sts2AgentBridge.Unified.FullPublicGraph;
using static Sts2AgentBridge.Unified.FullNativeState;

namespace Sts2AgentBridge.Unified;

internal sealed partial class FullNativeBackend
{
    private bool _eventResume;
    private bool _resumeProjection;
    private BridgeRequest ResumeCommand(string? decision, string? action) => Request("resume_item", true, decision, action) with {
        ParentDecision = _eventOrigin?.Decision ?? throw new AgentUnsupported(), ParentAction = _eventOrigin.Action };
    private FullCapture ReadResumeItem()
    {
        using var document = ReadWire("resume_item"); var payload = document.RootElement;
        _resumeProjection = true;
        try
        {
            EventResults(payload);
            if (Text(payload, "status") is "waiting" or "resolved") return Waiting();
            Require(Text(payload, "status") == "ready");
            var adapter = _router.ActiveObservationSource is ValueTuple<PinnedGenericEventV7NativeAdapter, GenericEventV7Session> pair ? pair.Item1 : throw new AgentUnsupported();
            var binding = adapter.InspectResumeItem();
            _state.Begin(); _commands.Clear(); var run = _state.PublicRun(_history); _state.Bind(binding);
            Require(ReferenceEquals(binding.Player, _state.Player));
            var context = Text(payload, "version") == "item_policy_v1" ? EventItemPolicy(default, payload, binding) : EventItem(default, payload, binding);
            return new("ready", Decision(run, context, _commands.Select(c => (JsonObject)c.Candidate.DeepClone())), _commands.ToArray(), _state.Bindings, _completed.ToArray());
        }
        finally { _resumeProjection = false; }
    }

    private void EventCommand(JsonElement child, JsonElement payload, string action, string kind, string? subject = null, string? target = null)
    {
        var request = _resumeProjection ? ResumeCommand(Text(payload, "decision_id"), action) : Request("event", true, Text(payload, "decision_id"), action) with {
            ChildOrdinal = child.GetProperty("ordinal").GetInt32(), ParentDecision = Text(child, "parent_decision_id"), ParentAction = Text(child, "parent_action_id") };
        _commands.Add(new(request, Candidate(_commands.Count, kind, subject, target)));
    }
    private JsonObject EventChild(PinnedGenericEventV7NativeAdapter adapter, JsonElement wire, EventModel model)
    {
        var child = wire.GetProperty("child"); var payload = wire.GetProperty("payload");
        var binding = adapter.InspectPending(Text(child, "parent_decision_id")!, Text(child, "parent_action_id")!);
        Require(ReferenceEquals(binding.Player, _state.Player) && ReferenceEquals(binding.EventModel, model));
        _state.Bind(binding); string kind = Text(child, "kind")!;
        if (kind == "full_rewards") {
            if(binding.FullRewards is GenericEventCompoundRewards compound) {
                var choice=EventCompoundChoice(child,payload,compound);if(choice is not null)return choice;
                var nested=compound.Inspect(Text(payload,"decision_id")!);
                return RewardContext(nested.Session,nested.View.DecisionId,nested.View.ScreenKind=="card_reward",
                    payload.GetProperty("legal_actions").EnumerateArray().Select(a=>a.GetString()!),
                    (action,semantic,subject,target)=>EventCommand(child,payload,action,semantic,subject,target));
            }
            var full=binding.FullRewards as GenericEventFullRewards ?? throw new AgentUnsupported();
            var rewards=full.Inspect(Text(payload,"decision_id")!);
            return RewardContext(rewards.Session,rewards.View.DecisionId,rewards.View.ScreenKind=="card_reward",
                payload.GetProperty("legal_actions").EnumerateArray().Select(a=>a.GetString()!),
                (action,semantic,subject,target)=>EventCommand(child,payload,action,semantic,subject,target));
        }
        if (kind == "item") return EventItem(child, payload, binding);
        if (kind == "crystal_sphere") return EventSphere(child, payload, binding);
        if (kind == "card_selection" && Text(child, "contract_version") == "card_grid_v1") return EventGrid(child, payload, binding);
        var children = new List<JsonObject>(); var links = new List<(string, IEnumerable<string>)>();
        var subjects = new Dictionary<int, string>();
        void Card(int slot, CardModel card, JsonElement view)
        {
            Require(Text(view, "key") == card.Id.Entry && view.GetProperty("upgrade_level").GetInt32() == card.CurrentUpgradeLevel);
            _state.Bind(card); string reference = _state.Ref("card", card); subjects.Add(slot, reference);
            if (!_state.Player.Deck.Cards.Contains(card)) children.Add(_state.Card(card));
        }
        if (kind == "card_selection")
        {
            Require(binding.Screen is not null);
            var grid = binding.Screen!.GetNodeOrNull<NCardGrid>("%CardGrid") ?? throw new AgentUnsupported();
            _state.Bind(binding.Screen); _state.Bind(grid);
            var candidates = payload.GetProperty("candidates").EnumerateArray().ToArray();
            var holders = grid.CurrentlyDisplayedCardHolders.ToArray(); Require(candidates.Length == holders.Length);
            foreach (var row in candidates)
            {
                int slot = row.GetProperty("slot").GetInt32(); var holder = holders[slot]; _state.Bind(holder);
                var card = holder.CardModel ?? throw new AgentUnsupported(); Require(binding.Originals.Contains(card)); Card(slot, card, row);
            }
            links.Add(("options", subjects.Values));
            links.Add(("selected", payload.GetProperty("selected_slots").EnumerateArray().Select(s => subjects[s.GetInt32()]).ToArray()));
            var selection = Node("selection", Text(child, "operation"), fields: new (string, object?)[] {
                ("minimum", child.GetProperty("min_select").GetInt32()), ("maximum", child.GetProperty("max_select").GetInt32()),
                ("manual_confirmation", Text(child, "commit_mode") != "auto_at_max") }, children: children, links: links);
            foreach (var row in payload.GetProperty("legal_actions").EnumerateArray())
            {
                string action = row.GetString()!; var parts = action.Split(':');
                EventCommand(child, payload, action, parts[0] switch { "select" => "choose_event_card", "deselect" => "deselect_card",
                    "confirm" => "confirm_selection", "cancel" => "cancel_selection", _ => throw new AgentUnsupported() },
                    parts.Length == 2 ? subjects[int.Parse(parts[1])] : null);
            }
            return Node("event", model.Id.Entry.ToLowerInvariant(), children: new[] { selection });
        }
        if (kind == "card_results")
        {
            var results = binding.Results ?? throw new AgentUnsupported();
            foreach (var row in payload.GetProperty("cards").EnumerateArray())
            { int slot = row.GetProperty("slot").GetInt32(); Card(slot, results.Results[slot].cardAdded, row); }
            links.Add(("results", subjects.Values));
        }
        else if (kind == "card_offer")
        {
            var offered = binding.Offer ?? throw new AgentUnsupported();
            foreach (var row in payload.GetProperty("offers").EnumerateArray())
            {
                int index = row.GetProperty("index").GetInt32(); var cards = offered.PublicOffer(index);
                var rows = row.GetProperty("cards").EnumerateArray().ToArray(); Require(cards.Count == rows.Length);
                var views = new List<JsonObject>();
                for (int i = 0; i < cards.Count; i++)
                { Require(Text(rows[i], "key") == cards[i].Id.Entry && rows[i].GetProperty("upgrade_level").GetInt32() == cards[i].CurrentUpgradeLevel); views.Add(_state.Card(cards[i])); }
                string reference = _state.Ref("offer", _state.Indexed(offered.DomainIdentity, "offer", index));
                subjects.Add(index, reference); children.Add(Node("offer", "cards", reference, children: views));
            }
            if (payload.GetProperty("selected_index").ValueKind == JsonValueKind.Number)
                links.Add(("selected", new[] { subjects[payload.GetProperty("selected_index").GetInt32()] }));
        }
        else if (kind == "card_reward") return EventRewards(child, payload, binding);
        else if (kind == "item_policy") return EventItemPolicy(child, payload, binding);
        else if (kind != "abandon_confirmation") throw new AgentUnsupported();
        foreach (var row in payload.GetProperty("legal_actions").EnumerateArray())
        {
            string action = row.GetString()!; var parts = action.Split(':');
            EventCommand(child, payload, action, parts[0] switch {
                "choose" or "select" => "choose_relic_reward", "confirm_abandon" when kind == "abandon_confirmation" => "abandon_run",
                "confirm" => "confirm_relic_selection", "cancel" => "cancel_selection", "skip" => "skip_reward",
                _ => throw new AgentUnsupported() }, parts.Length == 2 ? subjects[int.Parse(parts[1])] : null);
        }
        return Node(kind == "abandon_confirmation" ? "event" : "relic_choice", kind, children: children, links: links);
    }
    private JsonObject EventItem(JsonElement child, JsonElement value, GenericEventV7Binding binding)
    {
        if (Text(value, "version") == "item_set_v1") value = value.GetProperty("current");
        Require(Text(value, "status") == "ready");
        var root = binding.Item ?? throw new AgentUnsupported();
        var children = new List<JsonObject>(); var subjects = new Dictionary<int, string>();
        foreach (var row in value.GetProperty("offers").EnumerateArray())
        {
            int index = row.GetProperty("index").GetInt32();
            var item = root.Entries!.Single(e => e.Index == index);
            Require(Text(row, "key") == item.Key && item.Reward is not null);
            string reference = _state.Ref("reward", item.Reward!); subjects.Add(index, reference);
            var display = item.Model switch { PotionModel potion => _state.Potion(potion), RelicModel relic => _state.Relic(relic), _ => throw new AgentUnsupported() };
            children.Add(Node("reward", Text(row, "kind"), reference, children: new[] { display }));
        }
        foreach (var row in value.GetProperty("legal_actions").EnumerateArray())
        {
            string action = row.GetString()!; var parts = action.Split(':'); Require(parts[0] == "collect");
            int index = int.Parse(parts[1]); string itemKind = root.Entries!.Single(e => e.Index == index).Model is PotionModel ? "potion" : "relic";
            EventCommand(child, value, action, "claim_" + itemKind, subjects[index]);
        }
        return Node("rewards", children: children);
    }
    private JsonObject EventRewards(JsonElement child, JsonElement payload, GenericEventV7Binding binding)
    {
        var root = binding.Item ?? throw new AgentUnsupported();
        if (payload.TryGetProperty("item", out var item) && item.ValueKind == JsonValueKind.Object && Text(item, "status") == "ready")
            return EventItem(child, item, binding);
        if (Text(payload, "phase") == "dismiss")
        {
            Require(payload.GetProperty("legal_actions").EnumerateArray().Select(a => a.GetString()).SequenceEqual(new[] { "dismiss" }));
            EventCommand(child, payload, "dismiss", "leave_rewards"); return Node("rewards");
        }
        int offer = payload.TryGetProperty("offer_index", out var position) ? position.GetInt32() : 0;
        var entry = root.Entries![offer];
        var subjects = new Dictionary<int, string>(); var children = new List<JsonObject>();
        string reward = _state.Ref("reward", entry.Reward ?? throw new AgentUnsupported()); _state.Bind(entry.Reward!);
        string cardsKey = Text(child, "kind") == "item_policy" ? "card_options" : "cards";
        var cards = new List<JsonObject>();
        foreach (var row in payload.GetProperty(cardsKey).EnumerateArray())
        {
            int index = row.GetProperty("slot").GetInt32(); var card = entry.CardReward!.Originals[index];
            Require(Text(row, "key") == card.Id.Entry && row.GetProperty("upgrade_level").GetInt32() == card.CurrentUpgradeLevel);
            cards.Add(_state.Card(card)); subjects.Add(index, _state.Ref("card", card));
        }
        // Only the currently opened menu has card labels in this contract.
        children.Add(Node("reward", "card", reward, new (string, object?)[] { ("opened", cards.Count > 0) }, cards));
        foreach (var row in payload.GetProperty("legal_actions").EnumerateArray())
        {
            string action = row.GetString()!; var parts = action.Split(':');
            string actionKind = parts[0] switch { "open" => "open_reward", "choose" => "choose_reward_card", "skip" or "skip_card" => "skip_reward",
                "dismiss" => "leave_rewards", _ => throw new AgentUnsupported() };
            EventCommand(child, payload, action, actionKind, actionKind == "leave_rewards" ? null : reward,
                parts[0] == "choose" ? subjects[int.Parse(parts[^1])] : null);
        }
        return Node("rewards", children: children);
    }

    private JsonObject EventItemPolicy(JsonElement child, JsonElement payload, GenericEventV7Binding binding)
    {
        var root = binding.Item ?? throw new AgentUnsupported();
        var owner = binding.ItemPolicy ?? throw new AgentUnsupported();
        int? active = owner.InspectCardIndex(Text(payload, "decision_id")!);
        var rewards = new Dictionary<int, string>(); var cards = new Dictionary<int, string>(); var children = new List<JsonObject>();
        foreach (var row in payload.GetProperty("offers").EnumerateArray())
        {
            int index = row.GetProperty("index").GetInt32(); var entry = root.Entries![index];
            string kind = Text(row, "kind")!; bool settled = row.GetProperty("settled").GetBoolean();
            string reference = _state.Ref("reward", entry.Reward!); _state.Bind(entry.Reward!); rewards.Add(index, reference);
            Require(Text(row, "key") == (entry.CardReward is not null ? "CARD_REWARD" : entry.Key));
            var details = new List<JsonObject>();
            if (active == index)
                foreach (var offered in payload.GetProperty("card_options").EnumerateArray())
                {
                    int slot = offered.GetProperty("slot").GetInt32(); var card = entry.CardReward!.Originals[slot];
                    Require(Text(offered, "key") == card.Id.Entry && offered.GetProperty("upgrade_level").GetInt32() == card.CurrentUpgradeLevel);
                    details.Add(_state.Card(card)); cards.Add(slot, _state.Ref("card", card));
                }
            else if (!settled && entry.Model is PotionModel potion) details.Add(_state.Potion(potion));
            else if (!settled && entry.Model is RelicModel relic) details.Add(_state.Relic(relic));
            children.Add(Node("reward", kind, reference, new (string, object?)[] { ("resolved", settled), ("opened", active == index) }, details));
        }
        foreach (var row in payload.GetProperty("legal_actions").EnumerateArray())
        {
            string action = row.GetString()!; var parts = action.Split(':');
            if (parts[0] == "collect")
            {
                int index = int.Parse(parts[1]); var entry = root.Entries![index];
                EventCommand(child, payload, action, entry.CardReward is not null ? "open_reward" : entry.Model is PotionModel ? "claim_potion" : "claim_relic", rewards[index]);
            }
            else if (parts[0] == "choose" || action == "skip_card")
            { Require(active is not null); EventCommand(child, payload, action, action == "skip_card" ? "skip_reward" : "choose_reward_card", rewards[active!.Value], parts[0] == "choose" ? cards[int.Parse(parts[1])] : null); }
            else if (parts[0] == "discard")
            { var potion = _state.Player.PotionSlots[int.Parse(parts[1])] ?? throw new AgentUnsupported(); EventCommand(child, payload, action, "discard_potion", _state.Ref("potion", potion)); }
            else if (action == "skip_remaining") EventCommand(child, payload, action, "leave_rewards");
            else throw new AgentUnsupported();
        }
        return Node("rewards", children: children);
    }

    private JsonObject EventSphere(JsonElement child, JsonElement payload, GenericEventV7Binding binding)
    {
        var sphere = binding.Sphere ?? throw new AgentUnsupported();
        string decision = Text(payload, "decision_id")!;
        var board = payload.GetProperty("board");
        var cells = sphere.InspectCells(decision);
        var hidden = board.GetProperty("hidden").EnumerateArray().Select(v => v.GetBoolean()).ToArray();
        Require(cells.Length == 121 && cells.Select(c => c.Hidden).SequenceEqual(hidden));
        var children = new List<JsonObject>();
        foreach (var cell in cells)
        {
            _state.Bind(cell.Identity);
            // Item data is available only for the uncovered square. Never ask
            // for its extent, position, reward model, subscriptions or RNG.
            string fragment = cell.Hidden ? "hidden" : FullNativeDisplay.SphereFragment(cell.Fragment);
            children.Add(Node("cell", fragment, _state.Ref("cell", cell.Identity), new (string, object?)[] { ("x", cell.X), ("y", cell.Y), ("hidden", cell.Hidden) }));
        }
        var actions = payload.GetProperty("legal_actions").EnumerateArray().Select(a => a.GetString()!).ToArray();
        if (Text(payload, "phase") is "rewards" or "cards")
        {
            var rewards = sphere.InspectRewards(decision);
            children.Add(RewardContext(rewards.Session, rewards.View.DecisionId, rewards.View.ScreenKind == "card_reward",
                actions.Select(a => a.StartsWith("reward:", StringComparison.Ordinal) ? a[7..] : a),
                (action, kind, subject, target) => EventCommand(child, payload, action == "dismiss" ? action : "reward:" + action, kind, subject, target)));
        }
        else foreach (string action in actions)
        {
            string reference = _state.Ref("option", _state.Indexed(sphere, "option", action switch {
                "tool:small" => 121, "tool:big" => 122, "proceed" => 123, _ => int.Parse(action[7..]) }));
            string label = action.StartsWith("reveal:", StringComparison.Ordinal) ? "reveal_" + action[7..] : action.Replace(':', '_');
            children.Add(Node("option", label, reference));
            EventCommand(child, payload, action, action == "proceed" ? "leave_event" : "choose_event_option", reference);
        }
        return Node("event", "crystal_sphere", fields: new (string, object?)[] { ("divinations", board.GetProperty("divinations").GetInt32()), ("tool", Text(board, "tool")) }, children: children);
    }
}
