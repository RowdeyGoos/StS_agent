using System;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicRoomDecisionReader : IPublicRoomDecisionReader
{
    private bool _observedReady;
    private string _lastScreenKind = "unknown";
    private int _lastRoomOrdinal = -1;
    private string? _pendingDecisionId;
    private ulong? _activeRoomInstanceId;
    private int _nextRoomOrdinal;

    public PublicRoomDecisionSnapshot Read()
    {
        NRun? run = NRun.Instance;
        if (run is null || !GodotObject.IsInstanceValid(run))
        {
            return PublicRoomDecisionSnapshot.Waiting();
        }

        NRestSiteRoom? restSite = run.RestSiteRoom;
        bool hasRestSite = IsVisible(restSite);
        NEventRoom? eventRoom = run.EventRoom;
        bool hasEvent = IsVisible(eventRoom);
        if (hasRestSite && hasEvent)
        {
            return PublicRoomDecisionSnapshot.Unsupported();
        }

        if (!hasRestSite && !hasEvent)
        {
            return _observedReady
                ? PublicRoomDecisionSnapshot.Complete(_lastScreenKind, _lastRoomOrdinal)
                : PublicRoomDecisionSnapshot.Waiting();
        }

        CanvasItem activeRoom = hasRestSite ? restSite! : eventRoom!;
        int roomOrdinal = ResolveRoomOrdinal(activeRoom);
        if (roomOrdinal < 0)
        {
            return PublicRoomDecisionSnapshot.Unsupported(
                hasRestSite ? "rest_site" : "event");
        }

        if (HasNestedOverlay(run))
        {
            return PublicRoomDecisionSnapshot.Unsupported(
                hasRestSite ? "rest_site" : "event",
                roomOrdinal);
        }

        PublicRoomDecisionSnapshot snapshot = hasRestSite
            ? ReadRestSite(restSite!, roomOrdinal)
            : ReadEvent(eventRoom!, roomOrdinal);
        if (snapshot.Status != PublicDecisionStatus.Ready)
        {
            if (snapshot.Status == PublicDecisionStatus.Unsupported &&
                _pendingDecisionId is not null &&
                string.Equals(snapshot.ScreenKind, "rest_site", StringComparison.Ordinal))
            {
                return PublicRoomDecisionSnapshot.Waiting();
            }
            return snapshot;
        }

        if (string.Equals(_pendingDecisionId, snapshot.DecisionId, StringComparison.Ordinal))
        {
            return PublicRoomDecisionSnapshot.Waiting();
        }

        _pendingDecisionId = null;
        _observedReady = true;
        _lastScreenKind = snapshot.ScreenKind;
        _lastRoomOrdinal = snapshot.RoomOrdinal;
        return snapshot;
    }

    public void RecordAcceptedDecision(string decisionId)
    {
        if (!PublicRoomDecisionIdentity.IsCanonical(decisionId))
        {
            throw new ArgumentException("The accepted room decision identity is not canonical.", nameof(decisionId));
        }
        _pendingDecisionId = decisionId;
    }

    private static PublicRoomDecisionSnapshot ReadRestSite(
        NRestSiteRoom room,
        int roomOrdinal)
    {
        IReadOnlyList<RestSiteOption>? options = room.Options;
        if (options is null || options.Count > PublicRoomLimits.MaximumCandidates)
        {
            return PublicRoomDecisionSnapshot.Unsupported("rest_site", roomOrdinal);
        }

        var candidates = new List<PublicRoomCandidate>();
        var legalActions = new List<string>();
        for (int index = 0; index < options.Count; index++)
        {
            RestSiteOption? option = options[index];
            if (option is null || !PublicRoomDecisionIdentity.IsBoundedPublicId(option.OptionId))
            {
                return PublicRoomDecisionSnapshot.Unsupported("rest_site", roomOrdinal);
            }

            NRestSiteButton? button = room.GetButtonForOption(option);
            bool enabled = option.IsEnabled && IsVisible(button) && button!.IsEnabled;
            bool supported = option is HealRestSiteOption;
            string actionId = PublicRoomActionRequest.ChoiceActionIdFor(index);
            candidates.Add(new PublicRoomCandidate(
                index,
                actionId,
                supported ? PublicRoomCandidateKind.RestHeal : PublicRoomCandidateKind.RestUnsupported,
                option.OptionId,
                enabled,
                supported,
                false,
                false));
            if (enabled && supported)
            {
                legalActions.Add(actionId);
            }
        }

        var proceed = room.ProceedButton;
        if (IsVisible(proceed) && proceed.IsEnabled)
        {
            if (candidates.Count >= PublicRoomLimits.MaximumCandidates)
            {
                return PublicRoomDecisionSnapshot.Unsupported("rest_site", roomOrdinal);
            }
            candidates.Add(new PublicRoomCandidate(
                candidates.Count,
                PublicRoomActionRequest.ProceedActionId,
                PublicRoomCandidateKind.Proceed,
                PublicRoomActionRequest.ProceedActionId,
                true,
                true,
                true,
                false));
            legalActions.Add(PublicRoomActionRequest.ProceedActionId);
        }

        if (legalActions.Count == 0)
        {
            return PublicRoomDecisionSnapshot.Unsupported("rest_site", roomOrdinal);
        }

        string phase = legalActions.Contains(PublicRoomActionRequest.ProceedActionId)
            ? legalActions.Count == 1 ? "proceed" : "choose_or_proceed"
            : "choose_option";
        var snapshot = new PublicRoomDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "rest_site",
            phase,
            roomOrdinal,
            candidates,
            legalActions);
        return snapshot with { DecisionId = PublicRoomDecisionIdentity.Compute(snapshot) };
    }

    private static PublicRoomDecisionSnapshot ReadEvent(
        NEventRoom room,
        int roomOrdinal)
    {
        if (room.CustomEventNode is not null)
        {
            return PublicRoomDecisionSnapshot.Unsupported("event", roomOrdinal);
        }

        NEventLayout? layout = room.Layout;
        if (!IsVisible(layout))
        {
            return IsVisible(room.EmbeddedCombatRoom)
                ? PublicRoomDecisionSnapshot.Complete("event", roomOrdinal)
                : PublicRoomDecisionSnapshot.Waiting();
        }

        var candidates = new List<PublicRoomCandidate>();
        var legalActions = new List<string>();
        foreach (NEventOptionButton? button in layout!.OptionButtons)
        {
            if (candidates.Count >= PublicRoomLimits.MaximumCandidates ||
                button is null || !GodotObject.IsInstanceValid(button))
            {
                return PublicRoomDecisionSnapshot.Unsupported("event", roomOrdinal);
            }

            EventOption? option = button.Option;
            if (option is null || !PublicRoomDecisionIdentity.IsBoundedPublicId(option.TextKey))
            {
                return PublicRoomDecisionSnapshot.Unsupported("event", roomOrdinal);
            }

            bool dangerous = IsDangerous(button, option);
            bool enabled = button.IsVisibleInTree() && button.IsEnabled && !option.IsLocked && !dangerous;
            int index = candidates.Count;
            string actionId = PublicRoomActionRequest.ChoiceActionIdFor(index);
            candidates.Add(new PublicRoomCandidate(
                index,
                actionId,
                PublicRoomCandidateKind.EventOption,
                option.TextKey,
                enabled,
                !dangerous,
                option.IsProceed,
                dangerous));
            if (enabled)
            {
                legalActions.Add(actionId);
            }
        }

        if (candidates.Count == 0)
        {
            return PublicRoomDecisionSnapshot.Waiting();
        }
        if (legalActions.Count == 0)
        {
            return PublicRoomDecisionSnapshot.Unsupported("event", roomOrdinal);
        }

        var snapshot = new PublicRoomDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "event",
            "choose_option",
            roomOrdinal,
            candidates,
            legalActions);
        return snapshot with { DecisionId = PublicRoomDecisionIdentity.Compute(snapshot) };
    }

    internal static bool IsDangerous(NEventOptionButton button, EventOption option)
    {
        Func<MegaCrit.Sts2.Core.Entities.Players.Player, bool>? predicate = option.WillKillPlayer;
        if (predicate is null)
        {
            return false;
        }
        return button.Event is null || button.Event.Owner is null || predicate(button.Event.Owner);
    }

    internal static bool IsVisible(CanvasItem? item) =>
        item is not null && GodotObject.IsInstanceValid(item) && item.IsVisibleInTree();

    private int ResolveRoomOrdinal(CanvasItem room)
    {
        ulong instanceId = room.GetInstanceId();
        if (_activeRoomInstanceId == instanceId)
        {
            return _lastRoomOrdinal;
        }
        if (_nextRoomOrdinal > 999)
        {
            return -1;
        }
        _activeRoomInstanceId = instanceId;
        _pendingDecisionId = null;
        _lastRoomOrdinal = _nextRoomOrdinal;
        _nextRoomOrdinal++;
        return _lastRoomOrdinal;
    }

    private static bool HasNestedOverlay(NRun run)
    {
        NOverlayStack? overlays = run.GlobalUi?.Overlays;
        return overlays is not null && GodotObject.IsInstanceValid(overlays) && overlays.ScreenCount > 0;
    }
}
