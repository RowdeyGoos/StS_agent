using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

namespace Sts2AgentBridge.Rooms.Rest;

// Interactive successor on the same room module. One owned rest option may
// yield several policy decisions; acceptance is credited only after each exact
// selection/reward reconciles, and the parent only after native return/cleanup.
internal sealed class RestInteractiveSession : IDisposable
{
    internal const string DecisionRoute = "/probe/rest-v3/public/decision";
    internal const string ActionRoute = "/probe/rest-v3/public/action";
    private readonly PinnedRestV2NativeAdapter _native;
    private readonly string _nonce;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private RestV2Surface? _bound, _surface;
    private RestV2NativeOption? _option;
    private DeckChoiceView? _choice;
    private PublicRewardDecisionSnapshot _rewards;
    private JsonObject? _published, _terminal;
    private string? _parentDecision, _parentAction, _childDecision, _childAction;
    private CardModel[]? _expected;
    private readonly JsonArray _completed = new();
    private int _revision, _reads, _actions;
    private bool _failed, _disposed, _inside, _dispatching;
    internal RestInteractiveSession(string nonce, PinnedRestV2NativeAdapter? native = null)
    { _nonce = nonce; _native = native ?? new(interactive: true); }
    internal bool Complete => _terminal?["status"]?.GetValue<string>() == "complete";
    internal static bool ValidAction(string? action) => action is not null && action.Length <= 64 &&
        (action is "confirm" or "cancel" || action.StartsWith("option:", StringComparison.Ordinal) ||
         action.StartsWith("select:", StringComparison.Ordinal) || action.StartsWith("deselect:", StringComparison.Ordinal) ||
         action.StartsWith("reward:", StringComparison.Ordinal)) && action.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '_' or ':');
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool value) { if (!value) { _failed = true; throw new InvalidOperationException("rest_interactive_boundary"); } }
    private void Enter()
    { Require(!_inside && !_failed && !_disposed && Environment.CurrentManagedThreadId == _thread); _inside = true; }
    internal byte[] Handle(bool post, string? decision, string? action)
    {
        try
        {
            Enter();
            _dispatching = false;
            var value = post ? Apply(decision, action) : Read();
            return Encoding.UTF8.GetBytes(value.ToJsonString());
        }
        catch
        {
            _failed = true;
            return Encoding.UTF8.GetBytes(Value(post ? _dispatching ? "uncertain" : "rejected" : "unsupported", "unknown").ToJsonString());
        }
        finally { _inside = false; }
    }
    private JsonObject Value(string status, string phase) => new()
    {
        ["schema_version"] = 3, ["capability"] = "rest_v3", ["session_nonce"] = _nonce,
        ["status"] = status, ["phase"] = phase, ["completed"] = _completed.DeepClone()
    };
    private JsonObject Ready(string phase, IEnumerable<string> actions, JsonObject fields)
    {
        var value = Value("ready", phase);
        value["legal_actions"] = new JsonArray(actions.Select(a => (JsonNode?)JsonValue.Create(a)).ToArray());
        foreach (var pair in fields) value[pair.Key] = pair.Value?.DeepClone();
        value["parent_action"] = _parentAction;
        value["decision_id"] = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(_nonce + ":" + _revision + ":" + value.ToJsonString()))).ToLowerInvariant();
        _published = value;
        return value;
    }
    private JsonObject Read()
    {
        Require(++_reads <= 4096);
        if (_terminal is not null) return _terminal;
        _surface = _native.Capture(); _bound ??= _surface;
        Require(ReferenceEquals(_surface.Run, _bound.Run) && ReferenceEquals(_surface.Player, _bound.Player) &&
            ReferenceEquals(_surface.Room, _bound.Room) && ReferenceEquals(_surface.Map, _bound.Map));
        if (_option is null)
        {
            if (!_surface.Foreground) return Value("waiting", "option");
            var actions = _surface.Options.Where(o => o.Public.Enabled).Select(o => "option:" + o.Public.ActionId).ToArray();
            Require(actions.Length > 0);
            return Ready("option", actions, new()
            {
                ["options"] = new JsonArray(_surface.Options.Select(o => (JsonNode?)new JsonObject
                    { ["kind"] = o.Public.ActionId, ["enabled"] = o.Public.Enabled, ["counter"] = o.Public.Counter, ["amount"] = o.Public.Amount }).ToArray()),
                ["cards"] = new JsonArray(_surface.Cards.Select(c => (JsonNode?)new JsonObject
                    { ["slot"] = c.Slot, ["key"] = c.Key, ["upgrade"] = c.Upgrade, ["removable"] = c.Removable }).ToArray())
            });
        }
        var progress = _native.Poll(); Require(!progress.Failed);
        if (progress.Succeeded)
        {
            Require(_childAction is null || _childAction is "confirm" or "cancel" || _childAction.StartsWith("reward:", StringComparison.Ordinal));
            Require(_native.Capture().Foreground);
            if (!progress.Cancelled && _option.Public.ActionId is not ("smith" or "heal"))
                Require(progress.Counter == checked(_option.Public.Counter + RestV2Session.Delta(_option.Public.ActionId, _option.Public.Amount)));
            _native.Finish();
            if (_childAction is not null) SettleChild();
            Settle(_parentDecision!, _parentAction!, progress.Cancelled ? "cancelled" : "reconciled");
            _terminal = Value("complete", "rest");
            return _terminal;
        }
        _choice = _native.ReadChoice();
        if (_choice is {} choice)
        {
            if (_childAction is not null)
            {
                Require(_expected is not null && _expected.Length == choice.Selected.Length && _expected.All(choice.Selected.Contains));
                SettleChild();
            }
            var actions = new List<string>();
            var cards = new JsonArray();
            for (int i = 0; i < choice.Domain.Length; i++)
            {
                var card = choice.Domain[i]; bool selected = choice.Selected.Contains(card);
                cards.Add(new JsonObject { ["slot"] = i, ["key"] = card.Id.Entry, ["upgrade"] = card.CurrentUpgradeLevel, ["selected"] = selected });
                if (selected) actions.Add("deselect:" + i);
                else if (choice.Selected.Length < choice.Maximum) actions.Add("select:" + i);
            }
            if (choice.Selected.Length >= choice.Minimum) actions.Add("confirm");
            if (choice.Cancelable) actions.Add("cancel");
            return Ready("selection", actions, new() { ["cards"] = cards, ["minimum"] = choice.Minimum, ["maximum"] = choice.Maximum, ["cancelable"] = choice.Cancelable });
        }
        if (_native.Rewards is {} rewards && !rewards.Completed)
        {
            _rewards = rewards.Read();
            if (_rewards.Status == PublicDecisionStatus.Ready)
            {
                if (_childAction is not null)
                {
                    Require(_childAction.StartsWith("reward:", StringComparison.Ordinal));
                    SettleChild();
                }
                var actions = _rewards.LegalActions.Select(a => "reward:" + a).ToList();
                if (rewards.CanDismiss(_rewards)) actions.Add("reward:dismiss");
                Require(actions.Count > 0);
                return Ready("rewards", actions, new()
                {
                    ["screen_kind"] = _rewards.ScreenKind,
                    ["rewards"] = new JsonArray(_rewards.Rewards.Select(r => (JsonNode?)new JsonObject
                    {
                        ["slot"] = r.RewardIndex, ["kind"] = r.Kind.ToString().ToLowerInvariant(), ["selected"] = r.SuccessfullySelected,
                        ["key"] = r.ItemKey, ["cards"] = new JsonArray((_rewards.ScreenKind == "card_reward" ? r.Cards : Array.Empty<string>()).Select(c => (JsonNode?)JsonValue.Create(c)).ToArray())
                    }).ToArray())
                });
            }
        }
        return Value("waiting", "effect");
    }
    private JsonObject Apply(string? decision, string? action)
    {
        Require(_published is not null && ValidAction(action) && _published["decision_id"]!.GetValue<string>() == decision);
        var oldSurface = _surface; var oldChoice = _choice; string priorReward = _rewards.DecisionId;
        string before = _published.ToJsonString(); var fresh = Read();
        Require(fresh.ToJsonString() == before && fresh["legal_actions"]!.AsArray().Any(a => a!.GetValue<string>() == action) && _actions < 128);
        if (_option is null)
        {
            Require(oldSurface is not null && SameOptions(oldSurface, _surface!));
            _option = _surface!.Options.Single(o => "option:" + o.Public.ActionId == action);
            _parentDecision = decision; _parentAction = action;
        }
        else
        {
            Require(_childAction is null); _childDecision = decision; _childAction = action;
            if (action!.StartsWith("reward:", StringComparison.Ordinal)) Require(priorReward == _rewards.DecisionId);
            if (_choice is {} choice)
            {
                Require(oldChoice is not null && oldChoice.Domain.SequenceEqual(choice.Domain) && oldChoice.Selected.SequenceEqual(choice.Selected));
                if (action!.StartsWith("select:", StringComparison.Ordinal)) _expected = choice.Selected.Append(choice.Domain[int.Parse(action[7..])]).ToArray();
                else if (action.StartsWith("deselect:", StringComparison.Ordinal)) _expected = choice.Selected.Where(c => !ReferenceEquals(c, choice.Domain[int.Parse(action[9..])])).ToArray();
            }
        }
        _actions++; _revision++; _completed.Clear(); _published = null;
        _dispatching = true;
        if (_childAction is null) _native.Begin(_option!, _option!.Public.ActionId);
        else if (action!.StartsWith("reward:", StringComparison.Ordinal)) _native.Rewards!.Apply(_rewards.DecisionId, action[7..]);
        else
        {
            var parts = action!.Split(':');
            _native.ApplyChoice(parts[0], parts.Length == 2 ? _choice!.Domain[int.Parse(parts[1])] : null);
        }
        var receipt = Value("accepted", "action"); receipt["decision_id"] = decision; receipt["action_id"] = action;
        return receipt;
    }
    private static bool SameOptions(RestV2Surface a, RestV2Surface b) => a.Cards.SequenceEqual(b.Cards) && a.Options.Count == b.Options.Count &&
        a.Options.Zip(b.Options).All(p => p.First.Public == p.Second.Public && ReferenceEquals(p.First.Option, p.Second.Option) &&
            ReferenceEquals(p.First.Button, p.Second.Button) && ReferenceEquals(p.First.Relic, p.Second.Relic) && Equals(p.First.Witness, p.Second.Witness));
    private void SettleChild() { Settle(_childDecision!, _childAction!, "reconciled"); _childDecision = _childAction = null; _expected = null; }
    private void Settle(string decision, string action, string result)
    { _completed.Add(new JsonObject { ["decision_id"] = decision, ["action_id"] = action, ["result"] = result }); _revision++; }
    public void Dispose()
    {
        Require(Environment.CurrentManagedThreadId == _thread && !_inside);
        if (_disposed) return;
        _native.Dispose(); _disposed = true;
    }
}
