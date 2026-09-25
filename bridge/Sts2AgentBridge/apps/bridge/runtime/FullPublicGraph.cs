using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Sts2AgentBridge.Unified;

// The same explicitly constructed Node/Field/Link vocabulary as full_run_v2.
// Native objects and command tokens never pass through this serializer.
internal static class FullPublicGraph
{
    private static bool IsReference(string value)
    {
        int colon = value.IndexOf(':');
        if (colon < 1 || colon == value.Length - 1 || value[..colon] is not
            ("card" or "relic" or "potion" or "enemy" or "power" or "orb" or "reward" or "node" or "option" or "offer" or "cell")) return false;
        for (int i = colon + 1; i < value.Length; i++) if (value[i] is < '0' or > '9') return false;
        return true;
    }
    private static readonly HashSet<string> Actions = new(("play_card end_turn select_card deselect_card confirm_selection cancel_selection " +
        "choose_map_node claim_gold choose_reward_card skip_reward claim_potion claim_relic leave_rewards rest smith hatch choose_upgrade leave_rest " +
        "use_potion discard_potion buy_shop_item begin_shop_removal choose_shop_removal leave_shop open_chest claim_treasure_relic leave_treasure " +
        "choose_event_option leave_event choose_event_card choose_ancient_relic choose_relic_card deselect_relic_card confirm_relic_selection choose_relic_reward " +
        "lift dig use_rest_relic choose_cook_card deselect_cook_card confirm_cook choose_extra_reward reroll_card_reward sacrifice_card_reward " +
        "continue_act abandon_run open_reward close_reward open_shop close_shop").Split(' '), StringComparer.Ordinal);
    private static void Require(bool condition) { if (!condition) throw new AgentUnsupported(); }
    private static void Shape(JsonObject value, params string[] names) => Require(value.Count == names.Length && names.All(value.ContainsKey));
    private static string String(JsonNode? value) => value?.GetValue<string>() ?? throw new AgentUnsupported();
    internal static void Validate(JsonObject decision)
    {
        Shape(decision, "schema", "profile", "run", "context", "candidates");
        Require(String(decision["schema"]) == "sts_public_decision_v2" && String(decision["profile"]) == "full_run_v2");
        var definitions = new HashSet<string>(StringComparer.Ordinal);
        var links = new List<(string Key, string[] Targets)>();
        int nodes = 0;
        void Visit(JsonObject node, int depth)
        {
            Require(depth <= 24 && ++nodes <= 32768);
            Shape(node, "kind", "definition_id", "ref", "fields", "links", "children");
            Require(String(node["kind"]).Length > 0 && String(node["definition_id"]).Length > 0);
            if (node["ref"] is {} reference) { string id = String(reference); Require(IsReference(id) && definitions.Add(id)); }
            var keys = new HashSet<string>(StringComparer.Ordinal);
            foreach (var row in node["fields"]!.AsArray())
            {
                var field = row!.AsObject(); Shape(field, "key", "value");
                string key = String(field["key"]); Require(key.Length > 0 && keys.Add(key));
                if (field["value"] is not {} scalar) continue;
                Require(scalar is JsonValue);
                var value = (JsonValue)scalar;
                bool text = value.TryGetValue<string>(out var word);
                Require(text ? word!.Length <= 8192 && !IsReference(word) : value.TryGetValue<int>(out _) || value.TryGetValue<bool>(out _));
            }
            keys.Clear();
            foreach (var row in node["links"]!.AsArray())
            {
                var link = row!.AsObject(); Shape(link, "key", "targets");
                string key = String(link["key"]); Require(key.Length > 0 && keys.Add(key));
                string[] targets = link["targets"]!.AsArray().Select(String).ToArray();
                Require(targets.All(IsReference)); links.Add((key, targets));
            }
            foreach (var child in node["children"]!.AsArray()) Visit(child!.AsObject(), depth + 1);
        }
        Require(String(decision["run"]!["kind"]) == "run");
        Visit(decision["run"]!.AsObject(), 0); Visit(decision["context"]!.AsObject(), 0);
        foreach (var link in links)
            Require(link.Key is "history_subject" or "history_target" || link.Targets.All(definitions.Contains));
        var candidates = decision["candidates"]!.AsArray();
        Require(candidates.Count is > 0 and <= FullAgentRoutes.MaximumCandidates);
        var semantic = new HashSet<(string, string?, string?)>();
        for (int i = 0; i < candidates.Count; i++)
        {
            var action = candidates[i]!.AsObject(); Shape(action, "ref", "kind", "subject", "target");
            string kind = String(action["kind"]);
            string? subject = action["subject"]?.GetValue<string>(), target = action["target"]?.GetValue<string>();
            Require(String(action["ref"]) == "action:" + i && Actions.Contains(kind) &&
                (subject is null || definitions.Contains(subject)) && (target is null || definitions.Contains(target)) && semantic.Add((kind, subject, target)));
        }
    }
    internal static JsonObject Node(string kind, string? definition = null, string? reference = null,
        IEnumerable<(string Key, object? Value)>? fields = null, IEnumerable<JsonObject>? children = null,
        IEnumerable<(string Key, IEnumerable<string> Targets)>? links = null)
    {
        var values = new JsonArray();
        var keys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var (key, value) in fields ?? Array.Empty<(string, object?)>())
        {
            if (key.Length == 0 || !keys.Add(key) || value is not (null or string or int or bool))
                throw new AgentUnsupported();
            if (value is string text && text.Length > 8192) throw new AgentUnsupported();
            values.Add(new JsonObject { ["key"] = key, ["value"] = JsonSerializer.SerializeToNode(value) });
        }
        keys.Clear();
        var edges = new JsonArray();
        foreach (var (key, targets) in links ?? Array.Empty<(string, IEnumerable<string>)>())
        {
            if (key.Length == 0 || !keys.Add(key)) throw new AgentUnsupported();
            edges.Add(new JsonObject { ["key"] = key, ["targets"] = new JsonArray(targets.Select(s => (JsonNode?)JsonValue.Create(s)).ToArray()) });
        }
        return new JsonObject
        {
            ["kind"] = kind, ["definition_id"] = definition ?? kind, ["ref"] = reference,
            ["fields"] = values, ["links"] = edges,
            ["children"] = new JsonArray((children ?? Array.Empty<JsonObject>()).Select(n => (JsonNode)n).ToArray())
        };
    }

    internal static JsonObject Candidate(int slot, string kind, string? subject = null, string? target = null) =>
        new() { ["ref"] = "action:" + slot, ["kind"] = kind, ["subject"] = subject, ["target"] = target };

    internal static JsonObject Decision(JsonObject run, JsonObject context, IEnumerable<JsonObject> candidates) =>
        new() { ["schema"] = "sts_public_decision_v2", ["profile"] = "full_run_v2", ["run"] = run,
            ["context"] = context, ["candidates"] = new JsonArray(candidates.Select(c => (JsonNode)c).ToArray()) };
}
