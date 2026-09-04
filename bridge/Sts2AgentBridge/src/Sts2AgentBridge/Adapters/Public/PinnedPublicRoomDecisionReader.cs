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
    private readonly PublicRoomSurfaceLifecycle _lifecycle = new();

#if STS2_AGENT_BRIDGE_TEST_SEAM
    private readonly Func<PublicRoomSurface>? _testSurface;
    private readonly Func<int, PublicRoomDecisionSnapshot>? _testProjection;

    public PinnedPublicRoomDecisionReader() { }

    internal PinnedPublicRoomDecisionReader(
        Func<PublicRoomSurface> surface,
        Func<int, PublicRoomDecisionSnapshot> projection)
    {
        _testSurface = surface;
        _testProjection = projection;
    }
#endif

    public PublicRoomDecisionSnapshot Read()
    {
#if STS2_AGENT_BRIDGE_TEST_SEAM
        if (_testSurface is not null)
        {
            return _lifecycle.Observe(_testSurface()) ??
                _lifecycle.Project(_testProjection!(_lifecycle.RoomOrdinal));
        }
#endif
        NRun? run = NRun.Instance;
        if (run is null || !GodotObject.IsInstanceValid(run))
        {
            return _lifecycle.Observe(default)!.Value;
        }

        NRestSiteRoom? restSite = run.RestSiteRoom;
        bool hasRestSite = IsVisible(restSite);
        NEventRoom? eventRoom = run.EventRoom;
        bool hasEvent = IsVisible(eventRoom);
        CanvasItem? activeRoom = hasRestSite ? restSite : hasEvent ? eventRoom : null;
        var globalUi = run.GlobalUi;
        var map = globalUi is not null && GodotObject.IsInstanceValid(globalUi)
            ? globalUi.MapScreen : null;
        bool mapAvailable = map is not null && GodotObject.IsInstanceValid(map);
        var surface = new PublicRoomSurface(
            run.GetInstanceId(),
            activeRoom?.GetInstanceId(),
            hasRestSite ? "rest_site" : hasEvent ? "event" : "unknown",
            mapAvailable,
            mapAvailable && map!.IsOpen,
            mapAvailable && map!.IsTravelEnabled,
            mapAvailable && map!.IsTraveling,
            (hasRestSite && hasEvent) || HasNestedOverlay(run) ||
                (hasEvent && eventRoom!.CustomEventNode is not null));
        PublicRoomDecisionSnapshot? boundary = _lifecycle.Observe(surface);
        if (boundary.HasValue)
        {
            return boundary.Value;
        }

        PublicRoomDecisionSnapshot snapshot = hasRestSite
            ? ReadRestSite(restSite!, _lifecycle.RoomOrdinal)
            : ReadEvent(eventRoom!, _lifecycle.RoomOrdinal);
        return _lifecycle.Project(snapshot);
    }

    internal bool Revalidate(PublicRoomDecisionSnapshot expected, ulong roomInstanceId)
    {
        PublicRoomDecisionSnapshot current = Read();
        return current.Status == PublicDecisionStatus.Ready &&
            string.Equals(current.DecisionId, expected.DecisionId, StringComparison.Ordinal) &&
            _lifecycle.Matches(expected, roomInstanceId);
    }

    internal void RecordAcceptedDecision(
        PublicRoomDecisionSnapshot snapshot,
        PublicRoomCandidate candidate,
        ulong roomInstanceId) => _lifecycle.RecordAccepted(snapshot, candidate, roomInstanceId);

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
            PublicRoomCandidate candidate = CreateEventCandidate(
                index,
                option.TextKey,
                enabled,
                dangerous);
            candidates.Add(candidate);
            if (enabled)
            {
                legalActions.Add(candidate.ActionId);
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

    internal static PublicRoomCandidate CreateEventCandidate(
        int index,
        string stableId,
        bool enabled,
        bool dangerous)
    {
        string actionId = PublicRoomActionRequest.ChoiceActionIdFor(index);
        // A game event's final "proceed" option is still an indexed event choice.
        // The public IsProceed flag is reserved for the bridge's literal proceed action.
        return new PublicRoomCandidate(
            index,
            actionId,
            PublicRoomCandidateKind.EventOption,
            stableId,
            enabled,
            !dangerous,
            false,
            dangerous);
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

    private static bool HasNestedOverlay(NRun run)
    {
        NOverlayStack? overlays = run.GlobalUi?.Overlays;
        return overlays is not null && GodotObject.IsInstanceValid(overlays) && overlays.ScreenCount > 0;
    }
}

// Internal, public-surface evidence only. Instance IDs never enter the wire or hash.
internal readonly record struct PublicRoomSurface(
    ulong? RunInstanceId,
    ulong? RoomInstanceId,
    string ScreenKind,
    bool MapAvailable,
    bool MapOpen,
    bool TravelEnabled,
    bool Traveling,
    bool Unsupported);

internal sealed class PublicRoomSurfaceLifecycle
{
    private readonly record struct RoomIdentity(
        ulong RunInstanceId, ulong RoomInstanceId, string ScreenKind, int Ordinal);

    // Numeric identities only, with no eviction or reuse during this process.
    // Completion evidence is deliberately not retained alongside this registry.
    private readonly List<RoomIdentity> _roomIdentities = new();
    private ulong? _runInstanceId;
    private ulong? _roomInstanceId;
    private string _screenKind = "unknown";
    private PublicRoomDecisionSnapshot? _ready;
    private string? _pendingDecisionId;
    private bool _acceptedRestProceed;

    internal int RoomOrdinal { get; private set; } = -1;

    // Null means the underlying room may be projected. Every other result has
    // no candidates, including an inspection map over persistent room nodes.
    internal PublicRoomDecisionSnapshot? Observe(PublicRoomSurface surface)
    {
        // Absence is not a new incarnation. Keep confirmed identities
        // so the same room cannot obtain a fresh decision hash after a gap.
        // Only volatile readiness/completion evidence is invalidated here.
        if (!surface.RunInstanceId.HasValue || !surface.RoomInstanceId.HasValue ||
            !surface.MapAvailable)
        {
            ClearEvidence();
            return PublicRoomDecisionSnapshot.Waiting();
        }
        if (_runInstanceId != surface.RunInstanceId ||
            _roomInstanceId != surface.RoomInstanceId ||
            !string.Equals(_screenKind, surface.ScreenKind, StringComparison.Ordinal))
        {
            _runInstanceId = surface.RunInstanceId;
            _roomInstanceId = surface.RoomInstanceId;
            _screenKind = surface.ScreenKind;
            ClearEvidence();
            RoomOrdinal = ResolveRoomOrdinal(surface.RunInstanceId.Value,
                surface.RoomInstanceId.Value, surface.ScreenKind);
        }

        if (RoomOrdinal < 0 || surface.Unsupported)
        {
            ClearEvidence();
            return PublicRoomDecisionSnapshot.Unsupported(_screenKind, RoomOrdinal);
        }
        if (surface.Traveling)
        {
            ClearEvidence();
            return PublicRoomDecisionSnapshot.Waiting();
        }
        if (surface.MapOpen)
        {
            return _acceptedRestProceed && surface.TravelEnabled
                ? PublicRoomDecisionSnapshot.Complete(_screenKind, RoomOrdinal)
                : PublicRoomDecisionSnapshot.Waiting();
        }
        // Proceed can take several frames to open the map. Closing that map
        // does not make its already accepted persistent Proceed button eligible.
        if (_acceptedRestProceed)
        {
            return PublicRoomDecisionSnapshot.Waiting();
        }
        return null;
    }

    private int ResolveRoomOrdinal(ulong runInstanceId, ulong roomInstanceId, string screenKind)
    {
        foreach (RoomIdentity identity in _roomIdentities)
        {
            if (identity.RunInstanceId == runInstanceId && identity.RoomInstanceId == roomInstanceId)
            {
                // A known numeric pair cannot be relabeled to mint a new hash.
                return string.Equals(identity.ScreenKind, screenKind, StringComparison.Ordinal)
                    ? identity.Ordinal : -1;
            }
        }
        if (_roomIdentities.Count >= 1000)
        {
            return -1;
        }
        int ordinal = _roomIdentities.Count;
        _roomIdentities.Add(new RoomIdentity(runInstanceId, roomInstanceId, screenKind, ordinal));
        return ordinal;
    }

    internal PublicRoomDecisionSnapshot Project(PublicRoomDecisionSnapshot snapshot)
    {
        if (snapshot.Status != PublicDecisionStatus.Ready)
        {
            _ready = null;
            if (snapshot.Status == PublicDecisionStatus.Complete)
            {
                // Preserve the existing embedded-combat boundary only after an
                // accepted action in this very event. Disappearance is no proof.
                return _screenKind == "event" && _pendingDecisionId is not null
                    ? snapshot : PublicRoomDecisionSnapshot.Waiting();
            }
            return snapshot.Status == PublicDecisionStatus.Unsupported &&
                _screenKind == "rest_site" && _pendingDecisionId is not null
                ? PublicRoomDecisionSnapshot.Waiting() : snapshot;
        }
        if (string.Equals(_pendingDecisionId, snapshot.DecisionId, StringComparison.Ordinal))
        {
            _ready = null;
            return PublicRoomDecisionSnapshot.Waiting();
        }
        _pendingDecisionId = null;
        _ready = snapshot;
        return snapshot;
    }

    internal bool Matches(PublicRoomDecisionSnapshot snapshot, ulong roomInstanceId) =>
        _roomInstanceId == roomInstanceId && _ready.HasValue &&
        snapshot.Status == PublicDecisionStatus.Ready &&
        snapshot.RoomOrdinal == RoomOrdinal && snapshot.ScreenKind == _screenKind &&
        string.Equals(snapshot.DecisionId, _ready.Value.DecisionId, StringComparison.Ordinal);

    internal void RecordAccepted(
        PublicRoomDecisionSnapshot snapshot,
        PublicRoomCandidate candidate,
        ulong roomInstanceId)
    {
        if (!Matches(snapshot, roomInstanceId))
        {
            return;
        }
        _pendingDecisionId = snapshot.DecisionId;
        _acceptedRestProceed = snapshot.ScreenKind == "rest_site" &&
            candidate.Kind == PublicRoomCandidateKind.Proceed && candidate.Enabled &&
            candidate.Supported && candidate.IsProceed && !candidate.IsDangerous &&
            candidate.ActionId == PublicRoomActionRequest.ProceedActionId;
        _ready = null;
    }

    private void ClearEvidence()
    {
        _ready = null;
        _pendingDecisionId = null;
        _acceptedRestProceed = false;
    }
}
