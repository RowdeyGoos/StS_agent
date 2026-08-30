using System;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicMapActionApplier : IPublicMapActionApplier
{
    private const int MaximumTraversedNodes = 2048;
    private readonly PinnedPublicMapDecisionReader _reader;
    private readonly object _gate = new();
    private readonly HashSet<string> _acceptedDecisionIds = new(StringComparer.Ordinal);

    public PinnedPublicMapActionApplier(PinnedPublicMapDecisionReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
    }

    public PublicMapActionApplyResult Apply(PublicMapActionRequest request)
    {
        PublicMapActionApplyOutcome? initialFailure = ReservationFailure(request.DecisionId);
        if (initialFailure.HasValue)
        {
            return Result(initialFailure.Value, request);
        }

        PublicMapDecisionSnapshot snapshot = _reader.Read();
        if (snapshot.Status != PublicDecisionStatus.Ready ||
            !string.Equals(snapshot.DecisionId, request.DecisionId, StringComparison.Ordinal))
        {
            return Result(PublicMapActionApplyOutcome.StaleDecision, request);
        }
        if (request.CandidateIndex < 0 || request.CandidateIndex >= snapshot.Candidates.Count ||
            request.CandidateIndex >= snapshot.LegalActions.Count ||
            !string.Equals(
                snapshot.LegalActions[request.CandidateIndex],
                request.ActionId,
                StringComparison.Ordinal))
        {
            return Result(PublicMapActionApplyOutcome.InvalidAction, request);
        }

        PublicMapCandidate candidate = snapshot.Candidates[request.CandidateIndex];
        NRun? run = NRun.Instance;
        var globalUi = run?.GlobalUi;
        NMapScreen? map = globalUi?.MapScreen;
        if (run is null || !GodotObject.IsInstanceValid(run) ||
            globalUi is null || !GodotObject.IsInstanceValid(globalUi) ||
            map is null || !GodotObject.IsInstanceValid(map) ||
            !map.IsOpen || !map.IsTravelEnabled || map.IsTraveling)
        {
            return Result(PublicMapActionApplyOutcome.StaleDecision, request);
        }

        NMapPoint? selectedNode = null;
        var pending = new List<Node> { map };
        for (int cursor = 0; cursor < pending.Count; cursor++)
        {
            if (pending.Count > MaximumTraversedNodes)
            {
                return Result(PublicMapActionApplyOutcome.StaleDecision, request);
            }
            Node node = pending[cursor];
            if (node is NMapPoint mapPointNode &&
                mapPointNode.State == MapPointState.Travelable &&
                mapPointNode.Point is MapPoint point &&
                point.coord.col == candidate.Col && point.coord.row == candidate.Row)
            {
                if (selectedNode is not null)
                {
                    return Result(PublicMapActionApplyOutcome.StaleDecision, request);
                }
                selectedNode = mapPointNode;
            }

            int childCount = node.GetChildCount(false);
            if (childCount < 0 || childCount > MaximumTraversedNodes - pending.Count)
            {
                return Result(PublicMapActionApplyOutcome.StaleDecision, request);
            }
            for (int index = 0; index < childCount; index++)
            {
                pending.Add(node.GetChild(index, false));
            }
        }
        if (selectedNode is null)
        {
            return Result(PublicMapActionApplyOutcome.StaleDecision, request);
        }

        PublicMapActionApplyOutcome? reservationFailure = Reserve(request.DecisionId);
        if (reservationFailure.HasValue)
        {
            return Result(reservationFailure.Value, request);
        }

        map.OnMapPointSelectedLocally(selectedNode);
        _reader.RecordAcceptedDestination(candidate);
        return Result(PublicMapActionApplyOutcome.Accepted, request);
    }

    private PublicMapActionApplyOutcome? ReservationFailure(string decisionId)
    {
        lock (_gate)
        {
            if (_acceptedDecisionIds.Contains(decisionId))
            {
                return PublicMapActionApplyOutcome.AlreadyApplied;
            }
            if (_acceptedDecisionIds.Count >= PublicMapActionBudget.MaximumAcceptedActions)
            {
                return PublicMapActionApplyOutcome.ActionLimitReached;
            }
            return null;
        }
    }

    private PublicMapActionApplyOutcome? Reserve(string decisionId)
    {
        lock (_gate)
        {
            PublicMapActionApplyOutcome? failure = ReservationFailure(decisionId);
            if (failure.HasValue)
            {
                return failure;
            }
            _acceptedDecisionIds.Add(decisionId);
            return null;
        }
    }

    private static PublicMapActionApplyResult Result(
        PublicMapActionApplyOutcome outcome,
        PublicMapActionRequest request) =>
        PublicMapActionApplyResult.FromRequest(outcome, request);
}
