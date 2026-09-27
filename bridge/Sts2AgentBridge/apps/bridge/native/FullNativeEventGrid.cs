using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using static Sts2AgentBridge.Unified.FullPublicGraph;
using static Sts2AgentBridge.Unified.FullNativeState;

namespace Sts2AgentBridge.Unified;

internal sealed partial class FullNativeBackend
{
    private JsonObject EventGrid(JsonElement child, JsonElement payload, GenericEventV7Binding binding)
    {
        var domain = binding.GridCard?.Domain ?? throw new AgentUnsupported();
        var candidates = payload.GetProperty("candidates").EnumerateArray().ToArray();
        Require(binding.Screen is not null && candidates.Length == domain.Length && candidates.Length is >= 2 and <= 128);
        _state.Bind(binding.Screen!);
        var subjects = new Dictionary<int, string>();
        for (int slot = 0; slot < domain.Length; slot++)
        {
            var card = domain[slot]; var row = candidates[slot];
            Require(row.GetProperty("slot").GetInt32() == slot && Text(row, "key") == card.Id.Entry &&
                row.GetProperty("upgrade_level").GetInt32() == card.CurrentUpgradeLevel && _state.Player.Deck.Cards.Contains(card));
            _state.Bind(card); subjects.Add(slot, _state.Ref("card", card));
        }
        foreach (var row in payload.GetProperty("legal_actions").EnumerateArray())
        {
            string action = row.GetString()!; var parts = action.Split(':');
            EventCommand(child, payload, action, parts[0] switch {
                "select" => "choose_event_card", "confirm" => "confirm_selection", _ => throw new AgentUnsupported()
            }, parts.Length == 2 ? subjects[int.Parse(parts[1])] : null);
        }
        var selected = payload.GetProperty("selected_slots").EnumerateArray().Select(s => subjects[s.GetInt32()]).ToArray();
        var enchantment = payload.GetProperty("enchantment");
        if (Text(child, "operation") == "enchant")
            Require(binding.Enchantment is {} expected && Text(enchantment, "key") == expected.Key &&
                enchantment.GetProperty("amount").GetInt32() == expected.Amount);
        else Require(binding.Enchantment is null && enchantment.ValueKind == JsonValueKind.Null);
        return Node("event", binding.EventModel.Id.Entry.ToLowerInvariant(), children: new[] {
            Node("selection", Text(child, "operation"), fields: new (string, object?)[] {
                ("minimum", 1), ("maximum", 1), ("manual_confirmation", true),
                ("modifier", binding.Enchantment?.Key.ToLowerInvariant()), ("amount", binding.Enchantment?.Amount)
            }, links: new (string, IEnumerable<string>)[] { ("options", subjects.Values), ("selected", selected) }) });
    }
}
