using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Transport;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal enum TerminalClassification
{
    Invalid = 0,
    NonTerminal = 1,
    Terminal = 2,
}

internal static class CardSelectionTerminalClassifier
{
    internal static TerminalClassification Classify(
        CardSelectionTransportRoute route,
        CardSelectionReleaseSelection selection,
        string nonce,
        int statusCode,
        byte[] body)
    {
        byte[]? canonical = null;
        try
        {
            if (!Enum.IsDefined(route) || !Enum.IsDefined(selection) ||
                !LowerHex(nonce, 32) || body.Length is < 1 or > CardSelectionTransportLimits.MaximumBody)
                return TerminalClassification.Invalid;
            foreach (byte value in body)
                if (value is < 0x20 or > 0x7e) return TerminalClassification.Invalid;
            using JsonDocument document = JsonDocument.Parse(body, new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 64,
            });
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object) return TerminalClassification.Invalid;
            canonical = JsonSerializer.SerializeToUtf8Bytes(root);
            if (!canonical.AsSpan().SequenceEqual(body)) return TerminalClassification.Invalid;
            var properties = new List<JsonProperty>();
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in root.EnumerateObject())
            {
                if (!names.Add(property.Name)) return TerminalClassification.Invalid;
                properties.Add(property);
            }
            if (properties.Count < 2 || !Number(properties[0], "schema_version", 1) ||
                properties[1].Name != "kind" || properties[1].Value.ValueKind != JsonValueKind.String)
                return TerminalClassification.Invalid;
            string? kind = properties[1].Value.GetString();
            if (kind == "error") return Error(statusCode, properties);
            if (statusCode != 200) return TerminalClassification.Invalid;
            return route switch
            {
                CardSelectionTransportRoute.ParentGet => ParentGet(selection, nonce, kind, properties),
                CardSelectionTransportRoute.ParentPost => ParentPost(nonce, kind, properties),
                CardSelectionTransportRoute.ChildGet => ChildGet(selection, nonce, kind, properties),
                CardSelectionTransportRoute.ChildPost => ChildPost(nonce, kind, properties),
                _ => TerminalClassification.Invalid,
            };
        }
        catch (JsonException) { return TerminalClassification.Invalid; }
        catch (NotSupportedException) { return TerminalClassification.Invalid; }
        finally { if (canonical is not null) CryptographicOperations.ZeroMemory(canonical); }
    }

    private static TerminalClassification Error(int statusCode, IReadOnlyList<JsonProperty> p)
    {
        if (!Names(p, "schema_version", "kind", "status", "code") ||
            !Text(p[1], "kind", "error") || !Text(p[2], "status", "error") ||
            p[3].Value.ValueKind != JsonValueKind.String) return TerminalClassification.Invalid;
        string? code = p[3].Value.GetString();
        return statusCode == 400 && code == "invalid_request" ||
               statusCode == 500 && code == "internal_failure"
            ? TerminalClassification.Terminal : TerminalClassification.Invalid;
    }

    private static TerminalClassification ParentGet(
        CardSelectionReleaseSelection selection, string nonce, string? kind,
        IReadOnlyList<JsonProperty> p)
    {
        if (kind == "parent_resolved")
        {
            if (!Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "status", "result", "begin_decision_id", "begin_action_id",
                    "proceed_decision_id", "proceed_action_id") ||
                !ParentCommon(p, nonce) || !Text(p[5], "status", "resolved") ||
                !Text(p[6], "result", "map_handoff") ||
                !HexText(p[7], "begin_decision_id", 64) || !Text(p[8], "begin_action_id", "begin") ||
                !HexText(p[9], "proceed_decision_id", 64) || !Text(p[10], "proceed_action_id", "proceed"))
                return TerminalClassification.Invalid;
            return TerminalClassification.Terminal;
        }
        if (kind != "parent_observation" ||
            !Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                "status", "phase", "parent_kind", "policy", "decision_id", "legal_actions") ||
            !ParentCommon(p, nonce) || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        string? status = p[5].Value.GetString();
        string? phase = StringValue(p[6]);
        if (status == "ready")
        {
            bool pair = selection == CardSelectionReleaseSelection.Cheese
                ? Text(p[7], "parent_kind", "event") && Text(p[8], "policy", "cheese_gorge_add_two")
                : selection == CardSelectionReleaseSelection.Smith &&
                  Text(p[7], "parent_kind", "rest") && Text(p[8], "policy", "rest_smith_upgrade_one");
            bool action = phase == "initial" ? SingleText(p[10], "legal_actions", "begin") :
                phase == "after" && SingleText(p[10], "legal_actions", "proceed");
            return pair && action && HexText(p[9], "decision_id", 64)
                ? TerminalClassification.NonTerminal : TerminalClassification.Invalid;
        }
        bool fixedShape = Text(p[7], "parent_kind", "") && Text(p[8], "policy", "") &&
            Text(p[9], "decision_id", "") && EmptyArray(p[10], "legal_actions");
        if (!fixedShape) return TerminalClassification.Invalid;
        if (status == "waiting" && phase is ("initial" or "transient" or "card_child" or "after" or "exit"))
            return TerminalClassification.NonTerminal;
        if (status == "unsupported" && phase == "unsupported") return TerminalClassification.Terminal;
        return TerminalClassification.Invalid;
    }

    private static TerminalClassification ParentPost(
        string nonce, string? kind, IReadOnlyList<JsonProperty> p)
    {
        if (kind == "parent_receipt")
        {
            if (!Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "decision_id", "action_id", "outcome") || !ParentCommon(p, nonce) ||
                !HexText(p[5], "decision_id", 64) || !ParentAction(p[6]) ||
                !Text(p[7], "outcome", "accepted")) return TerminalClassification.Invalid;
            return TerminalClassification.NonTerminal;
        }
        if (kind != "parent_failure" ||
            !Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal", "outcome") ||
            !ParentCommon(p, nonce) || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        return p[5].Value.GetString() is "rejected" or "unsupported" or "uncertain"
            ? TerminalClassification.Terminal : TerminalClassification.Invalid;
    }

    private static TerminalClassification ChildGet(
        CardSelectionReleaseSelection selection, string nonce, string? kind,
        IReadOnlyList<JsonProperty> p)
    {
        if (kind == "child_resolved")
        {
            if (!Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "status", "phase", "operation", "selected_cards", "prior_results") ||
                !ChildCommon(p, nonce) || !Text(p[5], "status", "resolved") ||
                !Text(p[6], "phase", "complete") || !SelectionOperation(selection, p[7]) ||
                !ResolvedCards(selection, p[8]) || !ResolvedHistory(selection, p[9]))
                return TerminalClassification.Invalid;
            return TerminalClassification.NonTerminal;
        }
        if (kind != "child_observation" ||
            !Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                "status", "phase", "operation", "commit_mode", "min_select", "max_select",
                "decision_id", "candidates", "selected_slots", "legal_actions", "prior_results") ||
            !ChildCommon(p, nonce) || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        string? status = p[5].Value.GetString();
        string? phase = StringValue(p[6]);
        if (status == "ready")
        {
            bool policy = selection == CardSelectionReleaseSelection.Cheese
                ? Text(p[7], "operation", "add") && Text(p[8], "commit_mode", "auto_at_max") &&
                  Number(p[9], "min_select", 2) && Number(p[10], "max_select", 2)
                : selection == CardSelectionReleaseSelection.Smith &&
                  Text(p[7], "operation", "upgrade") && Text(p[8], "commit_mode", "preview_confirm") &&
                  Number(p[9], "min_select", 1) && Number(p[10], "max_select", 1);
            return policy && phase is ("selecting" or "preview") &&
                HexText(p[11], "decision_id", 64) && Candidates(p[12], 1, 64, false) &&
                SelectedSlots(p[13]) && LegalActions(p[14]) && History(p[15])
                ? TerminalClassification.NonTerminal : TerminalClassification.Invalid;
        }
        bool fixedShape = Text(p[7], "operation", "") && Text(p[8], "commit_mode", "") &&
            Number(p[9], "min_select", 0) && Number(p[10], "max_select", 0) &&
            Text(p[11], "decision_id", "") && EmptyArray(p[12], "candidates") &&
            EmptyArray(p[13], "selected_slots") && EmptyArray(p[14], "legal_actions") &&
            History(p[15]);
        if (!fixedShape) return TerminalClassification.Invalid;
        if (status == "waiting" && phase is ("selecting" or "submitted" or "transient"))
            return TerminalClassification.NonTerminal;
        if (status == "unsupported" && phase == "unsupported") return TerminalClassification.Terminal;
        return TerminalClassification.Invalid;
    }

    private static TerminalClassification ChildPost(
        string nonce, string? kind, IReadOnlyList<JsonProperty> p)
    {
        if (kind == "child_receipt")
        {
            if (!Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal",
                    "decision_id", "action_id", "outcome") || !ChildCommon(p, nonce) ||
                !HexText(p[5], "decision_id", 64) || !ChildAction(p[6]) ||
                !Text(p[7], "outcome", "accepted")) return TerminalClassification.Invalid;
            return TerminalClassification.NonTerminal;
        }
        if (kind != "child_failure" ||
            !Names(p, "schema_version", "kind", "version", "session_nonce", "parent_ordinal", "outcome") ||
            !ChildCommon(p, nonce) || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        return p[5].Value.GetString() is "rejected" or "unsupported" or "uncertain"
            ? TerminalClassification.Terminal : TerminalClassification.Invalid;
    }

    private static bool ParentCommon(IReadOnlyList<JsonProperty> p, string nonce) =>
        Text(p[2], "version", "card_selection_parent_v1") &&
        Text(p[3], "session_nonce", nonce) && Number(p[4], "parent_ordinal", 1);

    private static bool ChildCommon(IReadOnlyList<JsonProperty> p, string nonce) =>
        Text(p[2], "version", "card_selection_v1") &&
        Text(p[3], "session_nonce", nonce) && Number(p[4], "parent_ordinal", 1);

    private static bool SelectionOperation(CardSelectionReleaseSelection selection, JsonProperty p) =>
        selection == CardSelectionReleaseSelection.Cheese
            ? Text(p, "operation", "add")
            : selection == CardSelectionReleaseSelection.Smith && Text(p, "operation", "upgrade");

    private static bool ParentAction(JsonProperty p) => p.Name == "action_id" &&
        p.Value.ValueKind == JsonValueKind.String && p.Value.GetString() is ("begin" or "proceed");

    private static bool ChildAction(JsonProperty p)
    {
        if (p.Name != "action_id" || p.Value.ValueKind != JsonValueKind.String) return false;
        string? value = p.Value.GetString();
        return value is not null && ChildActionValue(value);
    }

    private static bool ChildActionValue(string value)
    {
        if (value is "preview" or "confirm") return true;
        if (!value.StartsWith("select:", StringComparison.Ordinal)) return false;
        string suffix = value[7..];
        if (suffix.Length is < 1 or > 2 || suffix.Length > 1 && suffix[0] == '0') return false;
        int slot = 0;
        foreach (char c in suffix)
        {
            if (c is < '0' or > '9') return false;
            slot = slot * 10 + c - '0';
        }
        return slot < 64;
    }

    private static bool Candidates(JsonProperty property, int minimum, int maximum, bool requireSelected)
    {
        if (property.Value.ValueKind != JsonValueKind.Array ||
            property.Value.GetArrayLength() is < 0 or > 64 ||
            property.Value.GetArrayLength() < minimum || property.Value.GetArrayLength() > maximum)
            return false;
        var slots = new HashSet<int>();
        foreach (JsonElement item in property.Value.EnumerateArray())
        {
            if (!Object(item, out List<JsonProperty>? p) ||
                !Names(p, "slot", "key", "upgrade_level", "visible", "enabled", "selected") ||
                !Int(p[0], "slot", 0, 63, out int slot) || !slots.Add(slot) ||
                !StableKey(p[1], "key") || !Int(p[2], "upgrade_level", 0, int.MaxValue, out _) ||
                !Boolean(p[3], "visible") || !Boolean(p[4], "enabled") || !Boolean(p[5], "selected") ||
                requireSelected && !p[5].Value.GetBoolean())
                return false;
        }
        return true;
    }

    private static bool SelectedSlots(JsonProperty property)
    {
        if (property.Name != "selected_slots" || property.Value.ValueKind != JsonValueKind.Array ||
            property.Value.GetArrayLength() > 8) return false;
        var slots = new HashSet<int>();
        foreach (JsonElement item in property.Value.EnumerateArray())
            if (item.ValueKind != JsonValueKind.Number || !item.TryGetInt32(out int slot) ||
                slot is < 0 or > 63 || !slots.Add(slot)) return false;
        return true;
    }

    private static bool LegalActions(JsonProperty property)
    {
        if (property.Name != "legal_actions" || property.Value.ValueKind != JsonValueKind.Array ||
            property.Value.GetArrayLength() > 65) return false;
        var actions = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonElement item in property.Value.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.String) return false;
            string? value = item.GetString();
            if (value is null || !actions.Add(value) || !ChildActionValue(value)) return false;
        }
        return true;
    }

    private static bool History(JsonProperty property)
    {
        if (property.Name != "prior_results" || property.Value.ValueKind != JsonValueKind.Array ||
            property.Value.GetArrayLength() > 10) return false;
        var decisions = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonElement item in property.Value.EnumerateArray())
        {
            if (!Object(item, out List<JsonProperty>? p) ||
                !Names(p, "decision_id", "action_id", "result") ||
                !HexText(p[0], "decision_id", 64) || !decisions.Add(p[0].Value.GetString()!) ||
                p[1].Value.ValueKind != JsonValueKind.String || p[2].Value.ValueKind != JsonValueKind.String)
                return false;
            string? action = p[1].Value.GetString();
            string? result = p[2].Value.GetString();
            if (action is null || !ChildActionValue(action) || result != ResultFor(action)) return false;
        }
        return true;
    }

    private static bool ResolvedCards(CardSelectionReleaseSelection selection, JsonProperty property)
    {
        int count = selection == CardSelectionReleaseSelection.Cheese ? 2 : 1;
        return property.Name == "selected_cards" && Candidates(property, count, count, true);
    }

    private static bool ResolvedHistory(CardSelectionReleaseSelection selection, JsonProperty property)
    {
        if (!History(property)) return false;
        JsonElement.ArrayEnumerator values = property.Value.EnumerateArray();
        if (selection == CardSelectionReleaseSelection.Cheese)
        {
            if (property.Value.GetArrayLength() != 2) return false;
            foreach (JsonElement item in values)
                if (!item.GetProperty("action_id").GetString()!.StartsWith("select:", StringComparison.Ordinal))
                    return false;
            return true;
        }
        if (selection != CardSelectionReleaseSelection.Smith || property.Value.GetArrayLength() != 2)
            return false;
        values.MoveNext();
        JsonElement first = values.Current;
        values.MoveNext();
        JsonElement second = values.Current;
        return first.GetProperty("action_id").GetString()!.StartsWith("select:", StringComparison.Ordinal) &&
            second.GetProperty("action_id").GetString() == "confirm";
    }

    private static bool Object(JsonElement value, out List<JsonProperty> properties)
    {
        properties = new List<JsonProperty>();
        if (value.ValueKind != JsonValueKind.Object) return false;
        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in value.EnumerateObject())
        {
            if (!names.Add(property.Name)) return false;
            properties.Add(property);
        }
        return true;
    }

    private static bool Int(JsonProperty property, string name, int minimum, int maximum, out int value)
    {
        value = 0;
        return property.Name == name && property.Value.ValueKind == JsonValueKind.Number &&
            property.Value.TryGetInt32(out value) && value >= minimum && value <= maximum;
    }

    private static bool Boolean(JsonProperty property, string name) =>
        property.Name == name && property.Value.ValueKind is JsonValueKind.True or JsonValueKind.False;

    private static bool StableKey(JsonProperty property, string name)
    {
        if (property.Name != name || property.Value.ValueKind != JsonValueKind.String) return false;
        string? value = property.Value.GetString();
        if (value is null || value.Length is < 1 or > 128) return false;
        foreach (char c in value)
            if (!(c is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9' or '_')) return false;
        return true;
    }

    private static string ResultFor(string action) =>
        action.StartsWith("select:", StringComparison.Ordinal) ? "selected" :
        action == "preview" ? "previewed" : "committed";

    private static bool Names(IReadOnlyList<JsonProperty> p, params string[] names)
    {
        if (p.Count != names.Length) return false;
        for (int index = 0; index < names.Length; index++)
            if (p[index].Name != names[index]) return false;
        return true;
    }

    private static bool Text(JsonProperty p, string name, string expected) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.String && p.Value.GetString() == expected;

    private static string? StringValue(JsonProperty p) =>
        p.Value.ValueKind == JsonValueKind.String ? p.Value.GetString() : null;

    private static bool Number(JsonProperty p, string name, int expected) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.Number &&
        p.Value.TryGetInt32(out int value) && value == expected;

    private static bool Array(JsonProperty p, string name) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.Array;

    private static bool EmptyArray(JsonProperty p, string name) =>
        Array(p, name) && p.Value.GetArrayLength() == 0;

    private static bool SingleText(JsonProperty p, string name, string expected)
    {
        if (!Array(p, name) || p.Value.GetArrayLength() != 1) return false;
        JsonElement item = p.Value[0];
        return item.ValueKind == JsonValueKind.String && item.GetString() == expected;
    }

    private static bool HexText(JsonProperty p, string name, int length) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.String && LowerHex(p.Value.GetString(), length);

    private static bool LowerHex(string? value, int length)
    {
        if (value is null || value.Length != length) return false;
        foreach (char c in value)
            if (c is not (>= '0' and <= '9') and not (>= 'a' and <= 'f')) return false;
        return true;
    }
}
