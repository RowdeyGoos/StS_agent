using System;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Identity;

namespace Sts2AgentBridge.Unified;

// Original public services retain their native identity, legality and action budgets.
// The host adds cross-capability fencing around an accepted asynchronous action.
internal sealed class CoreBridgeModule : IDisposable
{
    private readonly string _correlation;
    private readonly IPublicScreenService _screen;
    private string? _pendingPath, _pendingDecision;
    internal bool HasPendingAction => _pendingPath is not null;
    private readonly IPublicCombatDecisionService _combatRead;
    private readonly IPublicCombatActionService _combatApply;
    private readonly IPublicRewardDecisionService _rewardRead;
    private readonly IPublicRewardActionService _rewardApply;
    private readonly IPublicMapDecisionService _mapRead;
    private readonly IPublicMapActionService _mapApply;
    private readonly IPublicRoomDecisionService _roomRead;
    private readonly IPublicRoomActionService _roomApply;
    internal CoreBridgeModule(string correlation, IPublicScreenService screen,
        IPublicCombatDecisionService combatRead, IPublicCombatActionService combatApply,
        IPublicRewardDecisionService rewardRead, IPublicRewardActionService rewardApply,
        IPublicMapDecisionService mapRead, IPublicMapActionService mapApply,
        IPublicRoomDecisionService roomRead, IPublicRoomActionService roomApply)
    {
        _correlation = correlation; _screen = screen;
        _combatRead = combatRead; _combatApply = combatApply;
        _rewardRead = rewardRead; _rewardApply = rewardApply;
        _mapRead = mapRead; _mapApply = mapApply;
        _roomRead = roomRead; _roomApply = roomApply;
    }
    internal static bool IsValidAction(BridgeRequest r) => r.Path switch
    {
        "/probe/v0/public/combat-action" => PublicCombatActionRequest.TryCreate(r.Decision!, r.Action!, out _),
        "/probe/v0/public/reward-action" => PublicRewardActionRequest.TryCreate(r.Decision!, r.Action!, out _),
        "/probe/v0/public/map-action" => PublicMapActionRequest.TryCreate(r.Decision!, r.Action!, out _),
        "/probe/v0/public/room-action" => PublicRoomActionRequest.TryCreate(r.Decision!, r.Action!, out _),
        _ => false,
    };
    internal ModuleReply Handle(BridgeRequest r)
    {
        if (r.Path == "/probe/v0/health") return new(CanonicalProbeEncoder.EncodeHealthBody(_correlation));
        if (r.Path == "/probe/v0/manifest")
        {
            byte[] old = CanonicalProbeEncoder.EncodeManifestBody(ProbeMode.Compatible);
            try { return new(Encoding.ASCII.GetBytes(Encoding.ASCII.GetString(old)
                .Replace("\"bridge_version\":\"0.8.0\"", "\"bridge_version\":\"1.0.0\"")
                .Replace("\"harmony_patches\":false", "\"harmony_patches\":true"))); }
            finally { Array.Clear(old); }
        }
        if (HasPendingAction && (r.IsPost || r.Path != _pendingPath))
            return new("{\"schema_version\":1,\"kind\":\"error\",\"code\":\"capability_busy\"}"u8.ToArray());
        byte[] body;
        switch (r.Path)
        {
            case "/probe/v0/public/screen":
                var screen = _screen.Read();
                if (!screen.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicScreenBody(screen.Snapshot); break;
            case "/probe/v0/public/combat-decision":
                var combat = _combatRead.Read();
                if (!combat.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicCombatDecisionBody(combat.Snapshot); break;
            case "/probe/v0/public/combat-action":
                if (!PublicCombatActionRequest.TryCreate(r.Decision!, r.Action!, out var combatAction)) return Fault();
                var combatResult = _combatApply.Apply(combatAction);
                if (combatResult.IsBackendFault) return Fault();
                body = CanonicalProbeEncoder.EncodePublicCombatActionBody(combatResult); break;
            case "/probe/v0/public/reward-decision":
                var reward = _rewardRead.Read();
                if (!reward.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicRewardDecisionBody(reward.Snapshot); break;
            case "/probe/v0/public/reward-action":
                if (!PublicRewardActionRequest.TryCreate(r.Decision!, r.Action!, out var rewardAction)) return Fault();
                var rewardResult = _rewardApply.Apply(rewardAction);
                if (rewardResult.IsBackendFault) return Fault();
                body = CanonicalProbeEncoder.EncodePublicRewardActionBody(rewardResult); break;
            case "/probe/v0/public/map-decision":
                var map = _mapRead.Read();
                if (!map.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicMapDecisionBody(map.Snapshot); break;
            case "/probe/v0/public/map-action":
                if (!PublicMapActionRequest.TryCreate(r.Decision!, r.Action!, out var mapAction)) return Fault();
                var mapResult = _mapApply.Apply(mapAction);
                if (mapResult.IsBackendFault) return Fault();
                body = CanonicalProbeEncoder.EncodePublicMapActionBody(mapResult); break;
            case "/probe/v0/public/room-decision":
                var room = _roomRead.Read();
                if (!room.IsSuccess) return Fault();
                body = CanonicalProbeEncoder.EncodePublicRoomDecisionBody(room.Snapshot); break;
            case "/probe/v0/public/room-action":
                if (!PublicRoomActionRequest.TryCreate(r.Decision!, r.Action!, out var roomAction)) return Fault();
                var roomResult = _roomApply.Apply(roomAction);
                if (roomResult.IsBackendFault) return Fault();
                body = CanonicalProbeEncoder.EncodePublicRoomActionBody(roomResult); break;
            default: return Fault();
        }
        try
        {
            using var json = JsonDocument.Parse(body);
            var root = json.RootElement;
            if (r.IsPost)
            {
                if (root.GetProperty("status").GetString() != "accepted") return new(body, Terminal: true);
                _pendingPath = r.Path.Replace("-action", "-decision");
                _pendingDecision = r.Decision;
            }
            else if (_pendingPath == r.Path)
            {
                string? status = root.GetProperty("status").GetString();
                if (status == "complete" || status == "ready" && root.GetProperty("decision_id").GetString() != _pendingDecision)
                    _pendingPath = _pendingDecision = null;
                else if (status != "ready" && status != "waiting") return new(body, Terminal: true);
            }
            return new(body);
        }
        catch { Array.Clear(body); throw; }
    }
    private ModuleReply Fault() => new(CanonicalProbeEncoder.EncodeErrorBody(ProbeErrorKind.BackendFault, _correlation), Terminal: true);
    public void Dispose() { }
}
