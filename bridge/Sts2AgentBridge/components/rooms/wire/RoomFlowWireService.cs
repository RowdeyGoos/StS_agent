using System;
using System.Collections.Generic;
using System.Linq;
using Sts2AgentBridge.Rooms.Rest;
using Sts2AgentBridge.Successors.ItemWireV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

namespace Sts2AgentBridge.Successors.RoomFlowsV1;

public static class RoomFlowWireProtocol
{
    public const string DecisionRoute = "/probe/room-flows-v1/public/decision";
    public const string ActionRoute = "/probe/room-flows-v1/public/action";
}

public sealed class RoomFlowWireService : IDisposable
{
    private readonly object _gate = new();
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private readonly string _nonce;
    private readonly IRoomFlowSession _session;
    private IRoomFlowReadValue? _published;
    private IRoomFlowReadValue? _terminal;
    private bool _interfered;
    private bool _cleanupFailed;
    private RoomFlowDispatchReceipt? _accepted;
    private string? _acceptedPhase;
    private bool _shopReconciled;
    private bool _childPublished;
    private bool _inside;
    private bool _failed;
    private bool _disposed;
    private int _attempted;
    private int _restBefore, _restDelta;

    public RoomFlowWireService(string nonce, ShopV1Session session) : this(nonce, (IRoomFlowSession)session) { }
    public RoomFlowWireService(string nonce, EventV1Session session) : this(nonce, (IRoomFlowSession)session) { }
    public RoomFlowWireService(string nonce, RestV2Session session) : this(nonce, (IRoomFlowSession)session) { }
    private RoomFlowWireService(string nonce, IRoomFlowSession session)
    {
        if (!RoomFlowIdentity.IsNonce(nonce)) throw new ArgumentException("Invalid nonce.");
        _nonce = nonce;
        _session = session ?? throw new ArgumentNullException(nameof(session));
    }

    public byte[] Handle(string? method, string? route, string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (_inside)
            {
                _interfered = true;
                return RoomFlowWireCodec.Error(_nonce, _session.FlowKind, "internal_failure");
            }
            if (_failed || _disposed || Environment.CurrentManagedThreadId != _owner)
                return Error();
            _inside = true;
            byte[]? owned = null;
            try
            {
                if (route is ItemWireV1Protocol.DecisionRoute or ItemWireV1Protocol.ActionRoute)
                {
                    if (_session is not EventV1Session eventSession || !_childPublished ||
                        eventSession.ActiveItemChild is not IEventItemChildBroker child ||
                        _accepted is null || !ReferenceEquals(child.ParentReceipt, _accepted))
                        return Error();
                    owned = child.Handle(method, route, decisionId, actionId);
                    if (child.Status is EventItemChildFailed) _failed = true;
                }
                else if (method == "GET" && route == RoomFlowWireProtocol.DecisionRoute &&
                    decisionId is null && actionId is null)
                {
                    IRoomFlowReadValue value = _terminal ?? _session.Read();
                    ValidateRead(value);
                    owned = RoomFlowWireCodec.Encode(_nonce, _session.FlowKind, value);
                    _published = value;
                    if (value is EventV1ResolvedResult || value is ShopV1Observation { Status: "complete" } || value is RestV2Observation { Status: "complete" })
                        _terminal = value;
                }
                else if (method == "POST" && route == RoomFlowWireProtocol.ActionRoute &&
                    RoomFlowIdentity.IsDecisionId(decisionId) && RoomFlowIdentity.IsActionId(_session.FlowKind, actionId))
                {
                    if (!CanApply(decisionId!, actionId!) || _attempted >= (_session.FlowKind == "shop" ? ShopV1Constants.MaximumReservations : 12))
                        return Error("invalid_request");
                    _attempted++; // Reserve before invoking the real module.
                    string phase = _published switch { ShopV1Observation shop => shop.Phase, RestV2Observation rest => rest.Phase, EventV1Observation ev => ev.Phase, _ => throw new InvalidOperationException() };
                    if (_published is RestV2Observation restReady)
                    {
                        var option = restReady.Options.Single(o => o.ActionId == RestV2Session.Kind(actionId!));
                        _restBefore = option.Counter; _restDelta = RestV2Session.Delta(actionId!, option.Amount);
                    }
                    _published = null;
                    IRoomFlowApplyValue result = _session.Apply(decisionId, actionId);
                    if (result is RoomFlowDispatchReceipt receipt)
                    {
                        Common(receipt.FlowKind, receipt.SessionNonce, receipt.ParentOrdinal);
                        if (receipt.DecisionId != decisionId || receipt.ActionId != actionId) return Error();
                        _accepted = receipt; _acceptedPhase = phase; _shopReconciled = false;
                    }
                    else if (result is RoomFlowApplyFailure failure)
                    {
                        Common(failure.FlowKind, failure.SessionNonce, failure.ParentOrdinal);
                        _failed = true;
                    }
                    else return Error();
                    owned = RoomFlowWireCodec.Encode(_nonce, _session.FlowKind, result);
                }
                else return Error("invalid_request");
                if (_disposed || _interfered || _failed && owned is null) return Error();
                byte[] returned = owned!;
                owned = null;
                return returned;
            }
            catch { return Error(); }
            finally
            {
                if (owned is not null) Array.Clear(owned);
                _inside = false;
            }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (Environment.CurrentManagedThreadId != _owner || _inside)
            {
                _failed = true;
                if (_inside) _interfered = true;
                throw new InvalidOperationException("Owner thread outside request required for cleanup.");
            }
            if (_disposed)
            {
                if (_cleanupFailed) throw new InvalidOperationException("Room flow cleanup failed.");
                return;
            }
            _disposed = true; _failed = true; _published = null; _accepted = null; _terminal = null;
            try { _session.Dispose(); }
            catch { _cleanupFailed = true; throw; }
        }
    }

    private byte[] Error(string code = "internal_failure")
    {
        _failed = true; _published = null;
        return RoomFlowWireCodec.Error(_nonce, _session.FlowKind, code);
    }

    private bool CanApply(string decision, string action)
    {
        if (_childPublished || _terminal is not null) return false;
        if (_published is RestV2Observation rest)
            return _accepted is null && rest.Status == "ready" && rest.DecisionId == decision && Contains(rest.LegalActions, action);
        if (_published is ShopV1Observation shop)
            return shop.Status == "ready" && shop.DecisionId == decision &&
                Contains(shop.LegalActions, action) && (_accepted is null || _shopReconciled);
        if (_published is EventV1Observation ev)
            return ev.Status == "ready" && ev.DecisionId == decision && Contains(ev.LegalActions, action);
        return false;
    }

    private void ValidateRead(IRoomFlowReadValue value)
    {
        _childPublished = false;
        if (value is RestV2Observation rest && _session.FlowKind == "rest")
        {
            Common("rest", rest.SessionNonce, 1);
            if (rest.Status == "ready")
            {
                if (_accepted is not null || rest.Phase != "choose_option" || rest.Result is not null ||
                    rest.Options.Count is < 1 or > 6 || rest.Options.Select(x => x.ActionId).Distinct().Count() != rest.Options.Count ||
                    rest.Options.Any(x => !RestV2Session.ValidCounter(x.ActionId, x.Counter) || x.Amount is < 0 or > 64 || x.ActionId != "clone" && x.Amount != 0) ||
                    !rest.LegalActions.SequenceEqual(RestV2Session.Actions(rest.Options, rest.Cards)) ||
                    rest.LegalActions.Count == 0 || RestV2Session.Digest(_nonce, rest.Options, rest.Cards) != rest.DecisionId)
                    throw new InvalidOperationException();
            }
            else
            {
                if (rest.DecisionId != "" || rest.Options.Count != 0 || rest.Cards.Count != 0 || rest.LegalActions.Count != 0) throw new InvalidOperationException();
                if (rest.Status == "complete")
                {
                    var r = rest.Result;
                    if (rest.Phase != "complete" || _accepted is null || r is null || r.DecisionId != _accepted.DecisionId ||
                        r.ActionId != _accepted.ActionId || !RestV2Session.ValidCounter(RestV2Session.Kind(r.ActionId), r.Before) ||
                        r.Before != _restBefore || r.After != checked(_restBefore + _restDelta)) throw new InvalidOperationException();
                }
                else if (rest.Result is not null || !(rest.Status == "waiting" && rest.Phase == (_accepted is null ? "unknown" : "action_waiting") ||
                    rest.Status == "unsupported" && rest.Phase == "unknown")) throw new InvalidOperationException();
            }
            if (rest.Status == "unsupported") _failed = true;
            return;
        }
        if (value is ShopV1Observation shop && _session.FlowKind == "shop")
        {
            Common(shop.FlowKind, shop.SessionNonce, shop.ParentOrdinal);
            if (shop.Version != ShopV1Constants.Version || shop.Offers.Count > 32 || shop.PriorResults.Count > 1 ||
                shop.Player.Gold < 0 || shop.Player.DeckCount is < 0 or > 512) throw new InvalidOperationException();
            if (shop.Status is not ("waiting" or "unsupported" or "ready" or "complete")) throw new InvalidOperationException();
            if (shop.PriorResults.Count == 1)
            {
                ShopV1ReconciledAction prior = shop.PriorResults[0];
                Common(prior.FlowKind, prior.SessionNonce, prior.ParentOrdinal);
                if (_accepted is null || prior.DecisionId != _accepted.DecisionId ||
                    prior.ActionId != _accepted.ActionId || prior.Result != "reconciled" ||
                    prior.Kind != Kind(prior.ActionId)) throw new InvalidOperationException();
                _shopReconciled = true;
            }
            if (shop.Status == "complete" && (!_shopReconciled || _accepted?.ActionId != "leave"))
                throw new InvalidOperationException();
            if (shop.Status == "ready")
            {
                if (!RoomFlowIdentity.IsDecisionId(shop.DecisionId) ||
                    ShopV1CanonicalEncoder.ComputeDecisionId(_nonce, shop.Phase, shop.Player, shop.Offers,
                    shop.LegalActions, shop.PriorResults.Count == 0 ? null : shop.PriorResults[0], shop.RemovalCandidates) != shop.DecisionId)
                    throw new InvalidOperationException();
            }
            else if (shop.DecisionId.Length != 0 || shop.Offers.Count != 0 || shop.LegalActions.Count != 0)
                throw new InvalidOperationException();
            if (shop.Status == "unsupported") _failed = true;
            return;
        }
        if (value is EventV1Observation ev && _session is EventV1Session eventSession)
        {
            Common(ev.FlowKind, ev.SessionNonce, ev.ParentOrdinal);
            if (ev.Version != "event_v1" || ev.Candidates.Count > 8 ||
                ev.Status is not ("waiting" or "unsupported" or "ready" or "item_child"))
                throw new InvalidOperationException();
            if (ev.Status == "ready")
            {
                if (!RoomFlowIdentity.IsDecisionId(ev.DecisionId) ||
                    EventV1CanonicalEncoder.ComputeDecisionId(_nonce, ev.Phase, ev.Candidates, ev.LegalActions) != ev.DecisionId)
                    throw new InvalidOperationException();
            }
            else if (ev.DecisionId.Length != 0 || ev.Candidates.Count != 0 || ev.LegalActions.Count != 0)
                throw new InvalidOperationException();
            if (ev.Status == "item_child")
            {
                if (_accepted is null || _acceptedPhase != "choose_option" ||
                    eventSession.ActiveItemChild is not IEventItemChildBroker child ||
                    !ReferenceEquals(child.ParentReceipt, _accepted)) throw new InvalidOperationException();
                _childPublished = true;
            }
            if (ev.Status == "unsupported") _failed = true;
            return;
        }
        if (value is EventV1ResolvedResult resolved && _session.FlowKind == "event")
        {
            Common(resolved.FlowKind, resolved.SessionNonce, resolved.ParentOrdinal);
            if (resolved.Version != "event_v1" || _accepted is null || _acceptedPhase != "proceed" ||
                resolved.DecisionId != _accepted.DecisionId || resolved.ActionId != _accepted.ActionId ||
                resolved.Result != "map_handoff") throw new InvalidOperationException();
            return;
        }
        throw new InvalidOperationException();
    }

    private void Common(string flow, string nonce, int ordinal)
    {
        if (flow != _session.FlowKind || nonce != _nonce || ordinal != 1) throw new InvalidOperationException();
    }
    internal static string Kind(string action) => action == "leave" ? "leave" :
        action == "inventory:close" ? "inventory_close" : action.StartsWith("discard:",StringComparison.Ordinal)?"discard_potion":action.StartsWith("remove:",StringComparison.Ordinal)?"remove_card": action.StartsWith("buy:potion:", StringComparison.Ordinal) ? "purchase_potion" : action.StartsWith("buy:relic:", StringComparison.Ordinal) ? "purchase_relic" : "purchase_card";
    private static bool Contains(IReadOnlyList<string> values, string action)
    {
        foreach (string value in values) if (value == action) return true;
        return false;
    }
}
