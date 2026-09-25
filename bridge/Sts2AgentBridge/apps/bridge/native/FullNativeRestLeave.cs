using System;
using System.Linq;
using MegaCrit.Sts2.Core.Nodes;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Rooms.Rest;
using static Sts2AgentBridge.Unified.FullNativeState;

namespace Sts2AgentBridge.Unified;

// Reuse the original room action's exact Proceed target and map reconciliation.
internal sealed class FullNativeRestLeave : IRestLeave
{
    private readonly PinnedPublicRoomDecisionReader _reader = new();
    private readonly PinnedPublicRoomActionApplier _apply;
    private bool _pending, _complete;
    internal FullNativeRestLeave() => _apply = new(_reader, 1);
    public string? ReadDecision(object room)
    {
        Require(!_pending && ReferenceEquals(NRun.Instance?.RestSiteRoom, room));
        var view = _reader.Read();
        return view.Status == PublicDecisionStatus.Ready && view.ScreenKind == "rest_site" && view.LegalActions.Contains("proceed") ? view.DecisionId : null;
    }
    public void Apply(string decision)
    {
        Require(!_pending && PublicRoomActionRequest.TryCreate(decision, "proceed", out _));
        PublicRoomActionRequest.TryCreate(decision, "proceed", out var request);
        _pending = true;
        var result = _apply.Apply(request);
        Require(result.Outcome == PublicRoomActionApplyOutcome.Accepted);
    }
    public bool Poll()
    {
        Require(_pending);
        var view = _reader.Read();
        Require(view.Status is PublicDecisionStatus.Waiting or PublicDecisionStatus.Ready or PublicDecisionStatus.Complete);
        return _complete = view.Status == PublicDecisionStatus.Complete && view.ScreenKind == "rest_site";
    }
    public void Dispose() => Require(!_pending || _complete);
}
