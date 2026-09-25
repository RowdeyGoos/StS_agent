using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

// A policy-facing successor over the existing shop owner. Purchases/removal,
// prices, restocks, native effects and cleanup remain ShopV1Session's job.
internal sealed class ShopInteractiveSession : IDisposable
{
    internal const string DecisionRoute = "/probe/shop-v7/public/decision", ActionRoute = "/probe/shop-v7/public/action";
    private readonly string _nonce;
    private readonly IShopV1NativeAdapter _native;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private ShopV1Session? _core;
    private ShopV1Observation? _view;
    private ShopV1SurfaceCapture? _surface, _entrance;
    private PinnedShopPickupDispatch? _pickup;
    private DeckChoiceView? _choice;
    private CardModel[]? _expected;
    private JsonObject? _published, _terminal;
    private readonly JsonArray _completed = new();
    private string? _parentDecision, _parentAction, _innerDecision, _innerAction, _childDecision, _childAction;
    private bool _opening, _inside, _failed, _disposed, _dispatching;
    private int _reads, _actions, _revision;
    internal ShopInteractiveSession(string nonce, IShopV1NativeAdapter native) { _nonce = nonce; _native = native; }
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool ok)
    { if (!ok) { _failed = true; throw new InvalidOperationException("shop_interactive_boundary"); } }
    internal (ShopV1SurfaceCapture Surface, DeckChoiceView? Choice, ShopV1Observation? Core) Inspect(string decision)
    {
        Require(!_inside && !_failed && !_disposed && Environment.CurrentManagedThreadId == _thread &&
            _published?["decision_id"]?.GetValue<string>() == decision && _surface is not null);
        return (_surface!, _choice, _view);
    }
    internal byte[] Handle(bool post, string? decision, string? action)
    {
        try
        {
            Require(!_inside && !_failed && !_disposed && Environment.CurrentManagedThreadId == _thread);
            _inside = true; _dispatching = false;
            return Encoding.UTF8.GetBytes((post ? Apply(decision, action) : Read()).ToJsonString());
        }
        catch { _failed = true; return Encoding.UTF8.GetBytes(Value(post && _dispatching ? "uncertain" : "unsupported", "unknown").ToJsonString()); }
        finally { _inside = false; }
    }
    private JsonObject Value(string status, string phase) => new() {
        ["schema_version"] = 7, ["capability"] = "shop_v7", ["session_nonce"] = _nonce,
        ["status"] = status, ["phase"] = phase, ["completed"] = _completed.DeepClone() };
    private JsonObject Ready(string phase, IEnumerable<string> actions, JsonObject fields)
    {
        var value = Value("ready", phase);
        value["legal_actions"] = new JsonArray(actions.Select(a => (JsonNode?)JsonValue.Create(a)).ToArray());
        foreach (var field in fields) value[field.Key] = field.Value?.DeepClone();
        value["decision_id"] = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(_nonce + ":" + _revision + ":" + _view?.DecisionId + ":" + value.ToJsonString()))).ToLowerInvariant();
        return _published = value;
    }
    private ShopV1SurfaceCapture Capture()
    {
        var surface = _native.CaptureSurface();
        Require(surface.Status == ShopV1SurfaceStatus.Available && surface.RoomVisible && !surface.ForegroundBlocked &&
            !surface.MapOpen && !surface.MapTraveling && Foreground(surface));
        if (_surface is not null) Require(SameContext(_surface, surface));
        return surface;
    }
    private static bool Foreground(ShopV1SurfaceCapture surface) => NModalContainer.Instance?.OpenModal is null &&
        NCapstoneContainer.Instance is not { InUse: true } && (surface.InventoryOpen
            ? surface.InventoryNodeIdentity is NMerchantInventory inventory && ReferenceEquals(ActiveScreenContext.Instance.GetCurrentScreen(), inventory)
            : surface.RoomIdentity is NMerchantRoom room && ReferenceEquals(ActiveScreenContext.Instance.GetCurrentScreen(), room));
    private JsonObject Read()
    {
        Require(++_reads <= 4096);
        if (_terminal is not null) return _terminal;
        if (_core is null)
        {
            var surface = Capture();
            if (_opening)
            {
                Require(SameInventory(_entrance!, surface));
                if (!surface.InventoryOpen || !surface.InventoryVisible) return Value("waiting", "entrance");
                Settle(_parentDecision!, _parentAction!); _parentDecision = _parentAction = null; _opening = false;
            }
            _surface = surface;
            if (!surface.InventoryOpen)
            {
                Require(surface.MerchantControl is { Visible: true, Enabled: true, Dispatch: not null } && surface.ProceedControl is { Visible: true, Enabled: true, Dispatch: not null });
                return Ready("entrance", new[] { "open", "leave" }, new JsonObject { ["gold"] = surface.Gold });
            }
            _core = new ShopV1Session(_nonce, _native);
        }
        _view = _core.Read() as ShopV1Observation ?? throw new InvalidOperationException("Shop read unavailable.");
        Require(_view.Status is "ready" or "waiting" or "complete");
        if (_parentDecision is not null && _view.PriorResults.Any(r => r.DecisionId == _innerDecision && r.ActionId == _innerAction && r.Result == "reconciled"))
        {
            if (_childDecision is not null) { Require(_childAction is "confirm" or "cancel"); SettleChild(); }
            Settle(_parentDecision, _parentAction!); _parentDecision = _parentAction = _innerDecision = _innerAction = null; _pickup = null; _choice = null;
        }
        if (_view.Status == "complete") { Require(_parentDecision is null && _childDecision is null); return _terminal = Value("complete", "map"); }
        if (_view.Status == "waiting")
        {
            _pickup = _core.PendingPurchase as PinnedShopPickupDispatch;
            if (_pickup is null) return Value("waiting", "purchase");
            _choice = _pickup.ReadChoice();
            if (_choice is null) return Value("waiting", "selection");
            if (_childDecision is not null)
            {
                Require(_expected is not null && _choice.Selected.SequenceEqual(_expected)); SettleChild();
            }
            var legal = new List<string>();
            for (int i = 0; i < _choice.Domain.Length; i++)
                if (_choice.Selected.Contains(_choice.Domain[i])) legal.Add("deselect:" + i);
                else if (_choice.Selected.Length < _choice.Maximum) legal.Add("select:" + i);
            if (_choice.Selected.Length >= _choice.Minimum) legal.Add("confirm");
            if (_choice.Cancelable) legal.Add("cancel");
            Require(legal.Count > 0);
            return Ready("selection", legal, new JsonObject {
                ["minimum"] = _choice.Minimum, ["maximum"] = _choice.Maximum, ["cancelable"] = _choice.Cancelable,
                ["cards"] = new JsonArray(_choice.Domain.Select(c => (JsonNode?)new JsonObject { ["key"] = c.Id.Entry, ["upgrade_level"] = c.CurrentUpgradeLevel }).ToArray()),
                ["selected"] = new JsonArray(_choice.Selected.Select(c => (JsonNode?)JsonValue.Create(Array.IndexOf(_choice.Domain, c))).ToArray()) });
        }
        Require(_parentDecision is null && _childDecision is null);
        _choice = null; _surface = _core.Inspect(_view.DecisionId);
        Require(Foreground(_surface));
        return Ready(_view.Phase, _view.LegalActions, new JsonObject { ["gold"] = _view.Player.Gold,
            ["offers"] = new JsonArray(_view.Offers.Select(o => (JsonNode?)new JsonObject { ["slot"] = o.Slot,
                ["kind"] = o.Kind, ["key"] = o.Key, ["price"] = o.DisplayedPrice, ["enabled"] = o.Enabled, ["supported"] = o.Supported }).ToArray()) });
    }
    private JsonObject Apply(string? decision, string? action)
    {
        Require(_published is not null && decision == _published["decision_id"]?.GetValue<string>() && action is not null);
        var before = _surface!;
        var fresh = Read();
        Require(fresh["status"]?.GetValue<string>() == "ready" && fresh["decision_id"]?.GetValue<string>() == decision &&
            fresh["legal_actions"]!.AsArray().Any(a => a?.GetValue<string>() == action) && ++_actions <= 256);
        _published = null;
        string phase = fresh["phase"]!.GetValue<string>();
        if (phase == "entrance" && action == "open")
        {
            Require(SameInventory(before, _surface!) && ReferenceEquals(before.MerchantControl?.Identity, _surface!.MerchantControl?.Identity));
            _entrance = _surface; _parentDecision = decision; _parentAction = action; _opening = true; _dispatching = true;
            _surface!.MerchantControl!.Dispatch!();
        }
        else if (phase == "selection")
        {
            Require(_childDecision is null && _choice is not null && _pickup is not null);
            string[] parts = action!.Split(':'); CardModel? card = parts.Length == 2 ? _choice.Domain[int.Parse(parts[1])] : null;
            _expected = parts[0] switch { "select" => _choice.Selected.Append(card!).ToArray(), "deselect" => _choice.Selected.Where(c => !ReferenceEquals(c, card)).ToArray(), _ => null };
            _childDecision = decision; _childAction = action; _dispatching = true; _pickup.ApplyChoice(parts[0], card);
        }
        else
        {
            Require(_parentDecision is null);
            if (_core is null)
            {
                Require(action == "leave"); _core = new ShopV1Session(_nonce, _native, allowClosedEntry: true);
                _view = _core.Read() as ShopV1Observation; Require(_view is { Status: "ready" });
            }
            _parentDecision = decision; _parentAction = action; _innerDecision = _view!.DecisionId; _innerAction = action; _dispatching = true;
            var receipt = _core.Apply(_innerDecision, action);
            Require(receipt is RoomFlowDispatchReceipt accepted && accepted.DecisionId == _innerDecision && accepted.ActionId == action);
        }
        return new JsonObject { ["status"] = "accepted", ["decision_id"] = decision, ["action_id"] = action };
    }
    private static bool SameContext(ShopV1SurfaceCapture a, ShopV1SurfaceCapture b) => ReferenceEquals(a.RunIdentity, b.RunIdentity) &&
        ReferenceEquals(a.RoomIdentity, b.RoomIdentity) && ReferenceEquals(a.PlayerIdentity, b.PlayerIdentity) && ReferenceEquals(a.MapIdentity, b.MapIdentity) &&
        ReferenceEquals(a.InventoryNodeIdentity, b.InventoryNodeIdentity) && ReferenceEquals(a.InventoryModelIdentity, b.InventoryModelIdentity);
    private static bool SameInventory(ShopV1SurfaceCapture a, ShopV1SurfaceCapture b) => SameContext(a, b) && a.Gold == b.Gold &&
        a.Deck.Count == b.Deck.Count && a.Deck.Zip(b.Deck).All(p => ReferenceEquals(p.First.ModelIdentity, p.Second.ModelIdentity) && p.First.StableKey == p.Second.StableKey && p.First.UpgradeLevel == p.Second.UpgradeLevel) &&
        a.PotionSlots.Count == b.PotionSlots.Count && a.PotionSlots.Zip(b.PotionSlots).All(p => ReferenceEquals(p.First.ModelIdentity, p.Second.ModelIdentity) && p.First.StableKey == p.Second.StableKey) &&
        a.Relics.Count == b.Relics.Count && a.Relics.Zip(b.Relics).All(p => ReferenceEquals(p.First.ModelIdentity, p.Second.ModelIdentity) && p.First.StableKey == p.Second.StableKey);
    private void Settle(string decision, string action)
    { _completed.Add(new JsonObject { ["decision_id"] = decision, ["action_id"] = action, ["result"] = "reconciled" }); _revision++; }
    private void SettleChild() { Settle(_childDecision!, _childAction!); _childDecision = _childAction = null; _expected = null; }
    public void Dispose()
    {
        Require(Environment.CurrentManagedThreadId == _thread && !_inside);
        if (_disposed) return;
        _core?.Dispose(); Require(!_opening && _parentDecision is null && _childDecision is null); _disposed = true;
    }
}
