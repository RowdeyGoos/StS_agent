using System;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

namespace Sts2AgentBridge.Unified;

// Campaign-only entry to the existing leave operation. Purchases and inventory
// opening are never exposed through this wrapper.
internal sealed class CampaignShopTransition : IPublicRewardTransition
{
    private readonly ShopV1Session _session;
    private readonly Func<bool> _context;
    private readonly string _decision;
    private readonly long _deadline = Environment.TickCount64 + 30000;
    private bool _started, _complete, _disposed, _cleanupFailed;

    internal CampaignShopTransition(string nonce, IShopV1NativeAdapter adapter, Func<bool> context)
    {
        _context = context;
        _session = new ShopV1Session(nonce, adapter, allowClosedEntry: true);
        try {
            Check(_context());
            var value = _session.Read() as ShopV1Observation;
            Check(value is { Status: "ready", Phase: "room_ready_to_leave" } &&
                value.LegalActions.Count == 1 && value.LegalActions[0] == "leave");
            _decision = value!.DecisionId!;
        } catch { _session.Dispose(); throw; }
    }
    private static void Check(bool value) { if (!value) throw new InvalidOperationException("Campaign shop transition failed."); }
    private void Context() => Check(!_disposed && Environment.TickCount64 < _deadline && _context());
    public void Dispatch()
    {
        Context(); Check(!_started); _started = true;
        Check(_session.Apply(_decision, "leave") is RoomFlowDispatchReceipt { Outcome: "accepted" });
    }
    public string Poll()
    {
        Context(); Check(_started);
        var value = _session.Read() as ShopV1Observation;
        Check(value is not null);
        if (value!.Status == "waiting") return "waiting";
        Check(value.Status == "complete" && value.PriorResults.Count == 1 &&
            value.PriorResults[0].DecisionId == _decision && value.PriorResults[0].Kind == "leave");
        _complete = true;
        return "map";
    }
    public void Dispose()
    {
        if (!_disposed) {
            _disposed = true;
            try { _session.Dispose(); } catch { _cleanupFailed = true; throw; }
        }
        Check(_complete && !_cleanupFailed);
    }
}
