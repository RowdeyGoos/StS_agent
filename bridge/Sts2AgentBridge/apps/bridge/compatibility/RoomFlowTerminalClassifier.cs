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
using Sts2AgentBridge.Successors.ItemWireV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.RoomReleaseV1;

internal enum TerminalClassification
{
    Invalid = 0,
    NonTerminal = 1,
    Terminal = 2,
}

internal static class RoomFlowTerminalClassifier
{
    public static TerminalClassification Classify(
        RoomFlowTransportRoute route,
        RoomFlowSelection selection,
        string nonce,
        byte[] body)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(body);
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object) return TerminalClassification.Invalid;
            var properties = new List<JsonProperty>();
            foreach (JsonProperty property in root.EnumerateObject()) properties.Add(property);
            return route is RoomFlowTransportRoute.ItemGet or RoomFlowTransportRoute.ItemPost
                ? Item(route, properties, nonce)
                : Parent(route, properties, selection, nonce);
        }
        catch (JsonException)
        {
            return TerminalClassification.Invalid;
        }
    }

    private static TerminalClassification Parent(
        RoomFlowTransportRoute route,
        IReadOnlyList<JsonProperty> p,
        RoomFlowSelection selection,
        string nonce)
    {
        string flow = selection == RoomFlowSelection.Shop ? "shop" : "event";
        if (p.Count < 7 || !Number(p[0], "schema_version", 1) ||
            !Text(p[1], "protocol", "room_flows_v1") ||
            !Text(p[2], "version", flow == "shop" ? "shop_v6" : flow + "_v1") ||
            !Text(p[3], "flow_kind", flow) || !Text(p[4], "session_nonce", nonce) ||
            !Number(p[5], "parent_ordinal", 1) || p[6].Name != "status" ||
            p[6].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        string? status = p[6].Value.GetString();
        bool allowed = route switch
        {
            RoomFlowTransportRoute.ParentGet when selection == RoomFlowSelection.Shop =>
                status is "ready" or "waiting" or "unsupported" or "complete" or "error",
            RoomFlowTransportRoute.ParentGet =>
                status is "ready" or "waiting" or "unsupported" or "item_child" or "resolved" or "error",
            RoomFlowTransportRoute.ParentPost =>
                status is "accepted" or "rejected" or "uncertain" or "unsupported" or "error",
            _ => false,
        };
        if (!allowed) return TerminalClassification.Invalid;
        int expected = status switch
        {
            "accepted" => 9,
            "rejected" or "uncertain" => 7,
            "error" => 8,
            "resolved" when selection == RoomFlowSelection.Event => 10,
            "ready" or "waiting" or "complete" when selection == RoomFlowSelection.Shop => 14,
            "ready" or "waiting" or "item_child" when selection == RoomFlowSelection.Event => 11,
            _ => -1,
        };
        if (status == "unsupported")
        {
            bool fixedFailure = p.Count == 7;
            bool observation = selection == RoomFlowSelection.Shop
                ? p.Count == 14 && ParentTailNames(p, selection, status)
                : p.Count == 11 && ParentTailNames(p, selection, status);
            bool valid = route == RoomFlowTransportRoute.ParentGet ? observation : fixedFailure;
            return valid
                ? TerminalClassification.Terminal
                : TerminalClassification.Invalid;
        }
        if (p.Count != expected || !ParentTailNames(p, selection, status!))
            return TerminalClassification.Invalid;
        if (status == "error" && !ErrorCode(p[7])) return TerminalClassification.Invalid;
        return status is "complete" or "resolved" or "rejected" or "uncertain" or "unsupported" or "error"
            ? TerminalClassification.Terminal
            : TerminalClassification.NonTerminal;
    }

    private static bool ParentTailNames(
        IReadOnlyList<JsonProperty> p,
        RoomFlowSelection selection,
        string status)
    {
        if (status == "accepted") return Names(p, 7, "decision_id", "action_id");
        if (status == "error") return Names(p, 7, "code");
        if (status is "rejected" or "uncertain") return p.Count == 7;
        if (status == "resolved") return Names(p, 7, "decision_id", "action_id", "result");
        return selection == RoomFlowSelection.Shop
            ? Names(p, 7, "phase", "decision_id", "player", "offers", "removal_candidates", "legal_actions", "prior_results")
            : Names(p, 7, "phase", "decision_id", "candidates", "legal_actions");
    }

    private static TerminalClassification Item(
        RoomFlowTransportRoute route,
        IReadOnlyList<JsonProperty> p,
        string nonce)
    {
        if (p.Count < 6 || !Number(p[0], "schema_version", 1) ||
            !Text(p[1], "protocol", "item_probe_v1") || !Text(p[2], "version", "item_v1") ||
            !Text(p[3], "session_nonce", nonce) || !Number(p[4], "surface_ordinal", 1) ||
            p[5].Name != "status" || p[5].Value.ValueKind != JsonValueKind.String)
            return TerminalClassification.Invalid;
        string? status = p[5].Value.GetString();
        bool allowed = route switch
        {
            RoomFlowTransportRoute.ItemGet =>
                status is "waiting" or "ready" or "unsupported" or "resolved" or "error",
            RoomFlowTransportRoute.ItemPost =>
                status is "accepted" or "rejected" or "uncertain" or "unsupported" or "error",
            _ => false,
        };
        if (!allowed) return TerminalClassification.Invalid;
        bool shape = status switch
        {
            "waiting" or "unsupported" or "rejected" or "uncertain" => p.Count == 6,
            "ready" => p.Count == 10 && Names(p, 6, "decision_id", "offers", "potion_slots", "legal_actions"),
            "accepted" => p.Count == 8 && Names(p, 6, "decision_id", "action_id"),
            "resolved" => p.Count == 12 && Names(p, 6, "decision_id", "action_id", "offer_index", "kind", "key", "result"),
            "error" => p.Count == 7 && Names(p, 6, "code"),
            _ => false,
        };
        if (!shape || status == "error" && !ErrorCode(p[6]))
            return TerminalClassification.Invalid;
        return status is "unsupported" or "rejected" or "uncertain" or "error"
            ? TerminalClassification.Terminal
            : TerminalClassification.NonTerminal;
    }

    private static bool Names(IReadOnlyList<JsonProperty> p, int start, params string[] names)
    {
        if (p.Count != start + names.Length) return false;
        for (int index = 0; index < names.Length; index++)
            if (p[start + index].Name != names[index]) return false;
        return true;
    }

    private static bool Text(JsonProperty p, string name, string expected) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.String &&
        p.Value.GetString() == expected;

    private static bool Number(JsonProperty p, string name, int expected) =>
        p.Name == name && p.Value.ValueKind == JsonValueKind.Number &&
        p.Value.TryGetInt32(out int value) && value == expected;

    private static bool ErrorCode(JsonProperty p) =>
        p.Name == "code" && p.Value.ValueKind == JsonValueKind.String &&
        p.Value.GetString() is "invalid_request" or "internal_failure";
}
