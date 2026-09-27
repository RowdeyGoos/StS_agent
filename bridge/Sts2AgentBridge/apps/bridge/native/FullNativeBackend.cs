using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Cards.Combat;
using Sts2AgentBridge.Rooms.Rest;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;
using static Sts2AgentBridge.Unified.FullPublicGraph;
using static Sts2AgentBridge.Unified.FullNativeState;

namespace Sts2AgentBridge.Unified;

// The full public reader delegates mutations to the production router. It never
// clicks a control, queues a game action, or infers completion from acceptance.
internal sealed partial class FullNativeBackend : IFullAgentBackend
{
    private readonly BridgeRouter _router;
    private readonly PinnedPublicRewardDecisionReader _rewards;
    private readonly CombatCardChoiceService _choice;
    private readonly FullNativeState _state = new();
    private readonly List<FullCompletion> _completed = new();
    private readonly List<JsonObject> _history = new();
    private readonly Dictionary<FullCompletion, JsonObject> _pending = new();
    private readonly HashSet<FullCompletion> _settled = new();
    private readonly List<FullCommand> _commands = new();
    private BridgeRequest? _parent, _child;
    private BridgeRequest? _eventOrigin;
    private string _family = "navigation", _potionReturn = "combat";
    private string? _source;
    private bool _inChoice, _disposed;
    internal FullNativeBackend(BridgeRouter router, PinnedPublicRewardDecisionReader rewards, CombatCardChoiceService choice)
    { _router = router; _rewards = rewards; _choice = choice; }

    private static string Route(string family, bool post = false) => family switch {
        "navigation" => post ? CampaignRoutes.FullAction : CampaignRoutes.FullDecision,
        "reward" => post ? CampaignRoutes.FullRewardAction : CampaignRoutes.FullRewardDecision,
        "potion" => post ? CombatPotionRoutes.FullAction : CombatPotionRoutes.FullDecision,
        "choice" => post ? CombatCardChoiceService.ActionRouteV4 : CombatCardChoiceService.DecisionRouteV4,
        "rest" => post ? RestInteractiveSession.FullActionRoute : RestInteractiveSession.FullDecisionRoute,
        "shop" => post ? ShopInteractiveSession.FullActionRoute : ShopInteractiveSession.FullDecisionRoute,
        "event" => "/probe/generic-event-v7/public/" + (post ? "action" : "decision"),
        "resume" => CoreBridgeModule.EventCombatRoute,
        "resume_item" => post ? CoreBridgeModule.ResumeItemAction : CoreBridgeModule.ResumeItemRead,
        "combat" or "map" or "room" => "/probe/v0/public/" + family + (post ? "-action" : "-decision"),
        _ => throw new AgentUnsupported()
    };
    private static BridgeRequest Request(string family, bool post = false, string? decision = null, string? action = null) =>
        new(family is "rest" or "shop" ? Capability.Rooms : family == "event" ? Capability.Events : Capability.Core, Route(family, post), post, 0, 0, decision, action);
    private JsonDocument ReadWire(string family) => FullReadFailure.At(FullReadStage.Native,
        () => FullAgentWire.Read(_router.Dispatch(Request(family))));
    private static string? Text(JsonElement value, string key) => value.TryGetProperty(key, out var field) && field.ValueKind == JsonValueKind.String ? field.GetString() : null;
    private FullCapture Waiting() => new("waiting", null, Array.Empty<FullCommand>(), Array.Empty<object>(), _completed.ToArray());
    private FullCapture Complete(string outcome) => new("complete", null, Array.Empty<FullCommand>(), Array.Empty<object>(), _completed.ToArray(), outcome);
    private void Settle(BridgeRequest request)
    {
        var receipt = FullCompletion.For(request);
        if (_settled.Contains(receipt)) return; // Repeated retained native receipt.
        Require(_pending.Remove(receipt, out var action));
        _settled.Add(receipt);
        _completed.Add(receipt);
        var links = new List<(string, IEnumerable<string>)>();
        if (action!["subject"]?.GetValue<string>() is {} subject) links.Add(("history_subject", new[] { subject }));
        if (action["target"]?.GetValue<string>() is {} target) links.Add(("history_target", new[] { target }));
        _history.Add(Node("action", action["kind"]!.GetValue<string>(), links: links));
        Require(_history.Count <= FullAgentRoutes.MaximumActions);
    }
    private void Settle(ref BridgeRequest? request)
    { if (request is not null) Settle(request); request = null; }

    public FullCapture Read() => FullReadFailure.At(FullReadStage.Context, ReadCore);
    private FullCapture ReadCore()
    {
        Require(!_disposed); _completed.Clear();
        for (int transition = 0; transition < 8; transition++)
        {
            string family = _inChoice ? "choice" : _family;
            if (family == "event") return ReadEvent();
            if (_eventResume && family == "combat")
            {
                using var resumed = ReadWire("resume");
                string? phase = Text(resumed.RootElement, "status");
                if (phase == "item") return ReadResumeItem();
                if (phase == "resumed") { Settle(ref _parent); _eventResume = false; _family = "event"; continue; }
                if (phase == "waiting") return Waiting();
                Require(phase == "combat");
            }
            using var document = ReadWire(family);
            var wire = document.RootElement;
            string? status = Text(wire, "status");
            if (family is "rest" or "shop")
            {
                foreach (var row in wire.GetProperty("completed").EnumerateArray())
                {
                    Require(Text(row, "result") is "reconciled" or "cancelled");
                    Settle(Request(family, true, Text(row, "decision_id"), Text(row, "action_id")));
                }
                // Deliver certified receipts before touching a successor
                // surface that may be unsupported. Cleanup already succeeded
                // in the room owner; a later read cannot revoke completion.
                if (status == "complete") { _family = "navigation"; return Waiting(); }
                Require(status is "ready" or "waiting");
                return status == "waiting" ? Waiting() : Ready(family, wire);
            }
            if (family == "navigation")
            {
                if (_parent is not null && Text(wire, "completed_decision_id") == _parent.Decision) Settle(ref _parent);
                if (status == "waiting") return Waiting();
                Require(status == "ready");
                string? surface = Text(wire, "surface");
                if (surface is "combat" or "map" or "rewards" or "rest" or "shop" or "event")
                { _family = surface == "rewards" ? "reward" : surface; continue; }
                return Ready(family, wire);
            }
            if (status == "waiting")
            {
                if (family is "combat" or "potion" && _parent is not null &&
                    !(family=="potion"&&_parent.Action?.StartsWith("discard:",StringComparison.Ordinal)==true))
                {
                    using var choice = ReadWire("choice");
                    _inChoice = _choice.IsActive;
                    if (Text(choice.RootElement, "status") == "ready")
                    { Require(_inChoice); return Ready("choice", choice.RootElement); }
                    Require(Text(choice.RootElement, "status") == "waiting");
                }
                return Waiting();
            }
            if (family == "potion")
            {
                Require(status == "resolved" && _parent is not null &&
                    Text(wire, "decision_id") == _parent.Decision && Text(wire, "action_id") == _parent.Action);
                Settle(ref _parent); _family = _potionReturn; continue;
            }
            if (status == "complete")
            {
                if (family == "choice")
                {
                    Require(_child is not null && Text(wire, "result") == "selection_verified");
                    Settle(ref _child); _inChoice = false; continue;
                }
                Settle(ref _parent);
                if (family == "combat")
                {
                    if (Text(wire, "outcome") == "defeat") return Complete("defeat");
                    Require(Text(wire, "outcome") == "victory");
                    if (_eventResume) return Waiting();
                    _family = "reward";
                }
                else _family = "navigation";
                continue;
            }
            Require(status == "ready");
            var pending = family == "choice" ? _child : _parent;
            if (pending is not null)
            {
                if (Text(wire, "decision_id") == pending.Decision) return Waiting();
                if (family == "choice") Settle(ref _child); else Settle(ref _parent);
            }
            return Ready(family, wire);
        }
        throw new AgentUnsupported();
    }
    private FullCapture Ready(string family, JsonElement wire)
    {
        FullReadFailure.At(FullReadStage.Run, () => { _state.Begin(); return true; }); _commands.Clear();
        AdoptAcquisitions();
        // Allocate run identities first, including map targets and deck cards.
        var run = FullReadFailure.At(FullReadStage.Run, () => _state.PublicRun(_history));
        var context = FullReadFailure.At(FullReadStage.Context, () => family switch {
            "combat" => Combat(wire), "choice" => Selection(wire), "reward" => Rewards(wire),
            "map" => Map(wire), "rest" => Rest(wire), "shop" => Shop(wire), "navigation" => Navigation(wire),
            _ => throw new AgentUnsupported()
        });
        Require(_commands.Count is > 0 and <= FullAgentRoutes.MaximumCandidates);
        return new("ready", Decision(run, context, _commands.Select(c => (JsonObject)c.Candidate.DeepClone())),
            _commands.ToArray(), _state.Bindings, _completed.ToArray());
    }
    private void Command(string family, string decision, string action, string kind, string? subject = null, string? target = null) =>
        _commands.Add(new(Request(family, true, decision, action), Candidate(_commands.Count, kind, subject, target)));
    public ModuleReply Apply(BridgeRequest request)
    {
        Require(!_disposed);
        var command = _commands.Single(c => c.Request == request);
        var reply = _router.Dispatch(request);
        if ((request.Capability == Capability.Events || CoreBridgeModule.IsResumeItem(request)) && !reply.Terminal)
        {
            byte[] eventReceiptBody = reply.Body;
            try
            {
                using var eventReceipt = JsonDocument.Parse(reply.Body);
                var payload = request.Capability == Capability.Events ? eventReceipt.RootElement.GetProperty("payload") : eventReceipt.RootElement;
                Require((Text(payload, "outcome") ?? Text(payload, "status")) == "accepted" &&
                    Text(payload, "decision_id") == request.Decision && Text(payload, "action_id") == request.Action);
                reply = reply with { Body = JsonSerializer.SerializeToUtf8Bytes(new {
                    status = "accepted", decision_id = request.Decision, action_id = request.Action }) };
            }
            finally { Array.Clear(eventReceiptBody); }
        }
        if (!reply.Terminal && !reply.StaleWithoutMutation)
        {
            using var document = JsonDocument.Parse(reply.Body);
            var root = document.RootElement;
            Require(Text(root, "status") == "accepted" && Text(root, "decision_id") == request.Decision && Text(root, "action_id") == request.Action);
            _pending.Add(FullCompletion.For(request), (JsonObject)command.Candidate.DeepClone());
            if (request.Capability == Capability.Events && !request.IsChild) _eventOrigin = request;
            if (request.Path is RestInteractiveSession.FullActionRoute or ShopInteractiveSession.FullActionRoute || request.Capability == Capability.Events || CoreBridgeModule.IsResumeItem(request)) { }
            else if (_inChoice) { Require(_child is null); _child = request; }
            else
            {
                Require(_parent is null); _parent = request;
                _source = command.Candidate["subject"]?.GetValue<string>();
                if (request.Path == CombatPotionRoutes.FullAction) { _potionReturn = _family; _family = "potion"; }
            }
        }
        return reply;
    }
    public void Dispose()
    { _state.Dispose(); Require(_pending.Count == 0); _disposed = true; }
}
