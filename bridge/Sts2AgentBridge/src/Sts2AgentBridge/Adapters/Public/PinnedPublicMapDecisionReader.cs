using System;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicMapDecisionReader : IPublicMapDecisionReader
{
    private const int MaximumTraversedNodes = 2048;
    private const int MaximumCandidates = 8;
    private PublicMapCandidate? _acceptedDestination;

    public PublicMapDecisionSnapshot Read()
    {
        NRun? run = NRun.Instance;
        if (run is null || !GodotObject.IsInstanceValid(run))
        {
            return PublicMapDecisionSnapshot.Waiting();
        }

        var globalUi = run.GlobalUi;
        if (globalUi is null || !GodotObject.IsInstanceValid(globalUi))
        {
            return PublicMapDecisionSnapshot.Waiting();
        }

        NMapScreen? map = globalUi.MapScreen;
        if (map is null || !GodotObject.IsInstanceValid(map))
        {
            return PublicMapDecisionSnapshot.Waiting();
        }

        if (_acceptedDestination.HasValue && !map.IsOpen)
        {
            return PublicMapDecisionSnapshot.Complete(_acceptedDestination.Value);
        }

        if (!map.IsOpen || !map.IsTravelEnabled || map.IsTraveling)
        {
            return PublicMapDecisionSnapshot.Waiting();
        }

        var candidates = new List<PublicMapCandidate>();
        var pending = new List<Node> { map };
        for (int cursor = 0; cursor < pending.Count; cursor++)
        {
            if (pending.Count > MaximumTraversedNodes)
            {
                return PublicMapDecisionSnapshot.Unsupported();
            }

            Node node = pending[cursor];
            if (node is NMapPoint mapPointNode && mapPointNode.State == MapPointState.Travelable)
            {
                MapPoint? point = mapPointNode.Point;
                if (point is null)
                {
                    return PublicMapDecisionSnapshot.Unsupported();
                }
                string kind = point.PointType switch
                {
                    MapPointType.Unknown => "unknown",
                    MapPointType.Shop => "shop",
                    MapPointType.Treasure => "treasure",
                    MapPointType.RestSite => "rest_site",
                    MapPointType.Monster => "monster",
                    MapPointType.Elite => "elite",
                    MapPointType.Boss => "boss",
                    MapPointType.Ancient => "ancient",
                    _ => string.Empty,
                };
                if (candidates.Count >= MaximumCandidates ||
                    point.coord.col is < 0 or > 15 || point.coord.row is < 0 or > 31 ||
                    kind.Length == 0)
                {
                    return PublicMapDecisionSnapshot.Unsupported();
                }

                foreach (PublicMapCandidate existing in candidates)
                {
                    if (existing.Col == point.coord.col && existing.Row == point.coord.row)
                    {
                        return PublicMapDecisionSnapshot.Unsupported();
                    }
                }
                candidates.Add(new PublicMapCandidate(
                    0,
                    point.coord.col,
                    point.coord.row,
                    kind));
            }

            int childCount = node.GetChildCount(false);
            if (childCount < 0 || childCount > MaximumTraversedNodes - pending.Count)
            {
                return PublicMapDecisionSnapshot.Unsupported();
            }
            for (int index = 0; index < childCount; index++)
            {
                pending.Add(node.GetChild(index, false));
            }
        }

        if (candidates.Count == 0)
        {
            return PublicMapDecisionSnapshot.Waiting();
        }

        candidates.Sort(static (left, right) =>
        {
            int row = left.Row.CompareTo(right.Row);
            return row != 0 ? row : left.Col.CompareTo(right.Col);
        });
        var indexed = new List<PublicMapCandidate>(candidates.Count);
        var legalActions = new List<string>(candidates.Count);
        for (int index = 0; index < candidates.Count; index++)
        {
            PublicMapCandidate candidate = candidates[index] with { CandidateIndex = index };
            indexed.Add(candidate);
            legalActions.Add(PublicMapActionRequest.ActionIdFor(index));
        }

        var snapshot = new PublicMapDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "map",
            null,
            indexed,
            legalActions);
        return snapshot with { DecisionId = PublicMapDecisionIdentity.Compute(snapshot) };
    }

    public void RecordAcceptedDestination(PublicMapCandidate destination)
    {
        _acceptedDestination = destination;
    }
}
