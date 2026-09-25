using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using static Sts2AgentBridge.Unified.FullPublicGraph;
using static Sts2AgentBridge.Unified.FullNativeState;

namespace Sts2AgentBridge.Unified;

internal sealed partial class FullNativeBackend
{
    private FullCapture ReadEvent()
    {
        using var document = ReadWire("event");
        var wire = document.RootElement;
        var parent = wire.GetProperty("parent");
        Require(Text(wire, "kind") == "decision");
        EventResults(parent);
        string? status = Text(parent, "status");
        if (status == "complete")
        {
            string? phase = Text(parent, "phase");
            if (phase is "run_won" or "run_abandoned") return Complete(phase == "run_won" ? "victory" : "run_abandoned");
            Require(phase is "map_handoff" or "combat_handoff" or "combat_resume_handoff");
            // Resume ownership is retained by the router until the actual
            // event callback and any owned reward have completed.
            _eventResume = phase == "combat_resume_handoff";
            _family = phase == "map_handoff" ? "map" : "combat";
            return Waiting();
        }
        Require(status is "waiting" or "ready" or "child");
        if (status == "waiting") return Waiting();
        if (status == "child")
        {
            var payload = wire.GetProperty("payload");
            EventResults(payload, wire.GetProperty("child"));
            if (Text(payload, "status") == "resolved") return Waiting();
            if (Text(payload, "status") == "waiting") return Waiting();
            Require(Text(payload, "status") == "ready");
        }
        _state.Begin(); _commands.Clear();
        var run = _state.PublicRun(_history);
        var source = _router.ActiveObservationSource is ValueTuple<PinnedGenericEventV7NativeAdapter, GenericEventV7Session> pair
            ? pair : throw new AgentUnsupported();
        source.Item1.FullRewardsFactory ??= (binding,set) => new GenericEventFullRewards(binding,set);
        var room = _state.Run.CurrentRoom as EventRoom ?? throw new AgentUnsupported();
        _state.Bind(room); _state.Bind(room.LocalMutableEvent);
        var context = status == "ready" ? EventParent(source.Item1, source.Item2, parent, room.LocalMutableEvent) : EventChild(source.Item1, wire, room.LocalMutableEvent);
        Require(_commands.Count is > 0 and <= FullAgentRoutes.MaximumCandidates);
        return new("ready", Decision(run, context, _commands.Select(c => (JsonObject)c.Candidate.DeepClone())),
            _commands.ToArray(), _state.Bindings, _completed.ToArray());
    }
    private void EventResults(JsonElement value, JsonElement? child = null)
    {
        BridgeRequest Receipt(JsonElement row) => _resumeProjection ? ResumeCommand(Text(row, "decision_id"), Text(row, "action_id")) : Request("event", true, Text(row, "decision_id"), Text(row, "action_id")) with {
            ChildOrdinal = child?.GetProperty("ordinal").GetInt32() ?? 0,
            ParentDecision = child is {} lineage ? Text(lineage, "parent_decision_id") : null,
            ParentAction = child is {} origin ? Text(origin, "parent_action_id") : null };
        if (value.TryGetProperty("prior_results", out var rows))
            foreach (var row in rows.EnumerateArray())
                Settle(Receipt(row));
        if (Text(value, "status") == "resolved" && Text(value, "action_id") is {} action)
            Settle(Receipt(value));
        // Ordered item sets retain a receipt for every settled original entry.
        if (Text(value, "version") == "item_set_v1")
        {
            foreach (var item in value.GetProperty("collected").EnumerateArray()) EventResults(item, child);
            if (value.GetProperty("current").ValueKind == JsonValueKind.Object) EventResults(value.GetProperty("current"), child);
        }
        if (Text(value, "version") == "mixed_reward_set_v1" && value.GetProperty("item").ValueKind == JsonValueKind.Object)
            EventResults(value.GetProperty("item"), child);
    }
    private JsonObject EventParent(PinnedGenericEventV7NativeAdapter adapter, GenericEventV7Session session, JsonElement wire, EventModel model)
    {
        string decision = Text(wire, "decision_id")!;
        var native = session.InspectParent(decision);
        var rows = wire.GetProperty("candidates").EnumerateArray().ToArray();
        Require(rows.Length == native.Options.Count);
        var options = new List<JsonObject>();
        var legal = wire.GetProperty("legal_actions").EnumerateArray().Select(a => a.GetString()).ToHashSet();
        for (int i = 0; i < rows.Length; i++)
        {
            var row = rows[i]; var option = native.Options[i]; _state.Bind(option.Identity);
            Require(Text(row, "stable_id") == option.StableId && Text(row, "rendered_text") == option.RenderedText);
            string reference = _state.Ref("option", option.Identity);
            var displayed = adapter.InspectOption(option.Identity);
            // This relic chains mandatory relic pickups and later curse additions;
            // the ordinary Offer owner cannot certify that compound parent.
            // Reject the complete frame before choosing an irreversible option.
            Require(!legal.Contains(Text(row,"action_id")) || displayed?.Relic is not MegaCrit.Sts2.Core.Models.Relics.NeowsBones);
            var details = displayed?.HoverTips.Select(FullNativeDisplay.Hover).ToList() ?? new List<JsonObject>();
            if (displayed?.Relic is {} relic) details.Add(_state.Relic(relic));
            options.Add(Node("option", option.StableId.ToLowerInvariant(), reference, new (string, object?)[] {
                ("text", option.RenderedText), ("enabled", option.Enabled), ("dangerous", option.Dangerous),
                ("proceed", option.IsProceed), ("abandon_confirmation", option.OpensAbandonConfirmation) }, details));
            if (legal.Contains(Text(row, "action_id")))
                Command("event", decision, Text(row, "action_id")!, option.IsProceed ? "leave_event" :
                    model is AncientEventModel && displayed?.Relic is not null ? "choose_ancient_relic" : "choose_event_option", reference);
        }
        // NEventRoom also skips absent localization entries. Ancients may use
        // their dialogue layout without an INITIAL description in the table.
        var description = model.Description;
        return Node("event", model.Id.Entry.ToLowerInvariant(), fields: new (string, object?)[] {
            ("phase", "options"), ("title", model.Title.GetFormattedText()),
            ("description", description?.Exists() == true ? description.GetFormattedText() : null) }, children: options);
    }
}
