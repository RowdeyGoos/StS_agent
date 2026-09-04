using System;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicRoomActionApplier : IPublicRoomActionApplier
{
    private readonly PinnedPublicRoomDecisionReader _reader;
    private readonly object _gate = new();
    private readonly Dictionary<string, string> _acceptedByDecision = new(StringComparer.Ordinal);

    public PinnedPublicRoomActionApplier(PinnedPublicRoomDecisionReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
    }

#if STS2_AGENT_BRIDGE_TEST_SEAM
    private readonly Func<ulong>? _testRoomInstanceId;
    private readonly Action? _testClick;

    internal PinnedPublicRoomActionApplier(
        PinnedPublicRoomDecisionReader reader, Func<ulong> roomInstanceId, Action click)
        : this(reader)
    {
        _testRoomInstanceId = roomInstanceId;
        _testClick = click;
    }
#endif

    public PublicRoomActionApplyResult Apply(PublicRoomActionRequest request)
    {
        PublicRoomActionApplyOutcome? initialFailure = ReservationFailure(request.DecisionId);
        if (initialFailure.HasValue)
        {
            return Result(initialFailure.Value, request);
        }

        PublicRoomDecisionSnapshot snapshot = _reader.Read();
        if (snapshot.Status != PublicDecisionStatus.Ready ||
            !string.Equals(snapshot.DecisionId, request.DecisionId, StringComparison.Ordinal))
        {
            return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
        }

        PublicRoomCandidate? selected = null;
        foreach (PublicRoomCandidate candidate in snapshot.Candidates)
        {
            if (string.Equals(candidate.ActionId, request.ActionId, StringComparison.Ordinal))
            {
                selected = candidate;
                break;
            }
        }
        if (!selected.HasValue || !selected.Value.Enabled || !selected.Value.Supported ||
            !Contains(snapshot.LegalActions, request.ActionId) ||
            (!string.Equals(request.ActionId, PublicRoomActionRequest.ProceedActionId, StringComparison.Ordinal) &&
             selected.Value.CandidateIndex != request.CandidateIndex))
        {
            return Result(PublicRoomActionApplyOutcome.InvalidAction, request);
        }

#if STS2_AGENT_BRIDGE_TEST_SEAM
        if (_testClick is not null)
        {
            return ReserveAndApply(request, snapshot, selected.Value, _testRoomInstanceId!(), _testClick);
        }
#endif
        return snapshot.ScreenKind switch
        {
            "rest_site" => ApplyRestSite(request, snapshot, selected.Value),
            "event" => ApplyEvent(request, snapshot, selected.Value),
            _ => Result(PublicRoomActionApplyOutcome.StaleDecision, request),
        };
    }

    private PublicRoomActionApplyResult ApplyRestSite(
        PublicRoomActionRequest request,
        PublicRoomDecisionSnapshot snapshot,
        PublicRoomCandidate candidate)
    {
        NRestSiteRoom? room = NRun.Instance?.RestSiteRoom;
        if (!PinnedPublicRoomDecisionReader.IsVisible(room))
        {
            return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
        }

        if (candidate.Kind == PublicRoomCandidateKind.Proceed)
        {
            var proceed = room!.ProceedButton;
            if (!PinnedPublicRoomDecisionReader.IsVisible(proceed) || !proceed.IsEnabled)
            {
                return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
            }
            return ReserveAndClick(request, snapshot, candidate, room, proceed);
        }

        IReadOnlyList<RestSiteOption>? options = room!.Options;
        if (candidate.Kind != PublicRoomCandidateKind.RestHeal ||
            options is null || candidate.CandidateIndex < 0 ||
            candidate.CandidateIndex >= options.Count ||
            options[candidate.CandidateIndex] is not HealRestSiteOption option ||
            !option.IsEnabled ||
            !string.Equals(option.OptionId, candidate.StableId, StringComparison.Ordinal))
        {
            return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
        }

        NRestSiteButton? button = room.GetButtonForOption(option);
        if (!PinnedPublicRoomDecisionReader.IsVisible(button) || !button!.IsEnabled)
        {
            return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
        }
        return ReserveAndClick(request, snapshot, candidate, room, button);
    }

    private PublicRoomActionApplyResult ApplyEvent(
        PublicRoomActionRequest request,
        PublicRoomDecisionSnapshot snapshot,
        PublicRoomCandidate candidate)
    {
        NEventRoom? room = NRun.Instance?.EventRoom;
        NEventLayout? layout = room?.Layout;
        if (!PinnedPublicRoomDecisionReader.IsVisible(room) || room!.CustomEventNode is not null ||
            !PinnedPublicRoomDecisionReader.IsVisible(layout))
        {
            return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
        }

        var buttons = new List<NEventOptionButton>();
        foreach (NEventOptionButton? button in layout!.OptionButtons)
        {
            if (buttons.Count >= PublicRoomLimits.MaximumCandidates ||
                button is null || !GodotObject.IsInstanceValid(button))
            {
                return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
            }
            buttons.Add(button);
        }
        if (candidate.Kind != PublicRoomCandidateKind.EventOption ||
            candidate.CandidateIndex < 0 || candidate.CandidateIndex >= buttons.Count)
        {
            return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
        }

        NEventOptionButton selected = buttons[candidate.CandidateIndex];
        EventOption? option = selected.Option;
        if (!PinnedPublicRoomDecisionReader.IsVisible(selected) || !selected.IsEnabled ||
            option is null || option.IsLocked ||
            !string.Equals(option.TextKey, candidate.StableId, StringComparison.Ordinal) ||
            PinnedPublicRoomDecisionReader.IsDangerous(selected, option))
        {
            return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
        }
        return ReserveAndClick(request, snapshot, candidate, room, selected);
    }

    private PublicRoomActionApplyResult ReserveAndClick(
        PublicRoomActionRequest request,
        PublicRoomDecisionSnapshot snapshot,
        PublicRoomCandidate candidate,
        CanvasItem room,
        MegaCrit.Sts2.Core.Nodes.GodotExtensions.NClickableControl control)
    {
        return ReserveAndApply(request, snapshot, candidate, room.GetInstanceId(), control.ForceClick);
    }

    internal PublicRoomActionApplyResult ReserveAndApply(
        PublicRoomActionRequest request,
        PublicRoomDecisionSnapshot snapshot,
        PublicRoomCandidate candidate,
        ulong roomInstanceId,
        Action click)
    {
        // Re-read the active surface and full decision after resolving the
        // control, immediately before reservation/dispatch on the game thread.
        if (!_reader.Revalidate(snapshot, roomInstanceId))
        {
            return Result(PublicRoomActionApplyOutcome.StaleDecision, request);
        }
        PublicRoomActionApplyOutcome? failure = Reserve(request.DecisionId, request.ActionId);
        if (failure.HasValue)
        {
            return Result(failure.Value, request);
        }

        click();
        _reader.RecordAcceptedDecision(snapshot, candidate, roomInstanceId);
        return Result(PublicRoomActionApplyOutcome.Accepted, request);
    }

    private PublicRoomActionApplyOutcome? ReservationFailure(string decisionId)
    {
        lock (_gate)
        {
            if (_acceptedByDecision.ContainsKey(decisionId))
            {
                return PublicRoomActionApplyOutcome.AlreadyApplied;
            }
            if (_acceptedByDecision.Count >= PublicRoomActionBudget.MaximumAcceptedActions)
            {
                return PublicRoomActionApplyOutcome.ActionLimitReached;
            }
            return null;
        }
    }

    private PublicRoomActionApplyOutcome? Reserve(string decisionId, string actionId)
    {
        lock (_gate)
        {
            if (_acceptedByDecision.ContainsKey(decisionId))
            {
                return PublicRoomActionApplyOutcome.AlreadyApplied;
            }
            if (_acceptedByDecision.Count >= PublicRoomActionBudget.MaximumAcceptedActions)
            {
                return PublicRoomActionApplyOutcome.ActionLimitReached;
            }
            _acceptedByDecision.Add(decisionId, actionId);
            return null;
        }
    }

    private static bool Contains(IReadOnlyList<string> values, string expected)
    {
        foreach (string value in values)
        {
            if (string.Equals(value, expected, StringComparison.Ordinal))
            {
                return true;
            }
        }
        return false;
    }

    private static PublicRoomActionApplyResult Result(
        PublicRoomActionApplyOutcome outcome,
        PublicRoomActionRequest request) =>
        PublicRoomActionApplyResult.FromRequest(outcome, request);
}
