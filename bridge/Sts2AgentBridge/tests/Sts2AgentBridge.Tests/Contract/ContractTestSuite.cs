using System;
using System.Text;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Tests.Contract;

internal static class ContractTestSuite
{
    private const string ZeroCorrelationId = "00000000000000000000000000000000";

    public static void Run()
    {
        CanonicalBodiesAreByteExact();
        CanonicalHttpResponsesAreByteExact();
        RoutesAreModeScopedAndExact();
        InvalidContractStatesFailClosed();
        ContractArtifactBindingTestSuite.Run();
    }

    private static void CanonicalBodiesAreByteExact()
    {
        AssertBody(
            "health_running",
            "{\"schema_version\":1,\"lifecycle_state\":\"running\",\"correlation_id\":\"00000000000000000000000000000000\"}",
            100,
            CanonicalProbeEncoder.EncodeHealthBody(ZeroCorrelationId));

        AssertBody(
            "manifest_compatible",
            "{\"schema_version\":1,\"protocol\":\"live_probe_v0\",\"bridge_id\":\"sts2_agent_bridge\",\"bridge_version\":\"0.8.0\",\"mode\":\"live_probe_v0\",\"build_compatibility\":\"compatible\",\"target_build_manifest_id\":\"sts2-steam-main-build-23811903-macos-universal\",\"target_game_version\":\"v0.107.1\",\"target_steam_build_id\":\"23811903\",\"capabilities\":{\"observe_public_screen\":true,\"observe_decision\":true,\"apply\":true,\"profile_access\":false,\"privileged_state\":false,\"snapshot_restore\":false,\"bridge_filesystem_writes\":false,\"host_logging\":\"sanitized_existing_sink\",\"harmony_patches\":false,\"outbound_network\":false,\"hot_unload\":false}}",
            604,
            CanonicalProbeEncoder.EncodeManifestBody(ProbeMode.Compatible));

        AssertBody(
            "manifest_locked",
            "{\"schema_version\":1,\"protocol\":\"live_probe_v0\",\"bridge_id\":\"sts2_agent_bridge\",\"bridge_version\":\"0.8.0\",\"mode\":\"live_probe_v0\",\"build_compatibility\":\"incompatible_locked\",\"target_build_manifest_id\":\"sts2-steam-main-build-23811903-macos-universal\",\"target_game_version\":\"v0.107.1\",\"target_steam_build_id\":\"23811903\",\"capabilities\":{\"observe_public_screen\":false,\"observe_decision\":false,\"apply\":false,\"profile_access\":false,\"privileged_state\":false,\"snapshot_restore\":false,\"bridge_filesystem_writes\":false,\"host_logging\":\"sanitized_existing_sink\",\"harmony_patches\":false,\"outbound_network\":false,\"hot_unload\":false}}",
            616,
            CanonicalProbeEncoder.EncodeManifestBody(ProbeMode.IncompatibleLocked));

        AssertBody(
            "screen_main_menu",
            "{\"schema_version\":1,\"status\":\"ready\",\"screen_kind\":\"main_menu\",\"actionable\":false,\"candidates\":[]}",
            98,
            CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.MainMenu)));
        AssertBody(
            "screen_settings",
            "{\"schema_version\":1,\"status\":\"ready\",\"screen_kind\":\"settings\",\"actionable\":false,\"candidates\":[]}",
            97,
            CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.Settings)));
        AssertBody(
            "screen_waiting",
            "{\"schema_version\":1,\"status\":\"waiting\",\"screen_kind\":\"unknown\",\"actionable\":false,\"candidates\":[]}",
            98,
            CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Waiting, PublicScreenKind.Unknown)));
        AssertBody(
            "screen_unsupported",
            "{\"schema_version\":1,\"status\":\"unsupported\",\"screen_kind\":\"unknown\",\"actionable\":false,\"candidates\":[]}",
            102,
            CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Unsupported, PublicScreenKind.Unknown)));

        string readyDecision =
            "{\"schema_version\":1,\"status\":\"ready\",\"decision_kind\":\"combat\",\"actionable\":true,\"decision_id\":\"" + new string('0', 64) + "\",\"round\":1," +
            "\"player\":{\"hp\":42,\"max_hp\":80,\"block\":5,\"energy\":2}," +
            "\"enemies\":[{\"index\":0,\"id\":\"CULTIST\",\"hp\":48,\"max_hp\":48,\"block\":0,\"intents\":[\"Attack\"]}]," +
            "\"hand\":[{\"hand_index\":0,\"id\":\"STRIKE_IRONCLAD\",\"type\":\"Attack\",\"cost\":\"1\",\"target_type\":\"AnyEnemy\",\"playable\":true}]," +
            "\"legal_actions\":[{\"action_id\":\"play:0:0\",\"kind\":\"play_card\",\"hand_index\":0,\"target_index\":0},{\"action_id\":\"end_turn\",\"kind\":\"end_turn\",\"hand_index\":null,\"target_index\":null}]}";
        PublicCombatDecisionSnapshot readySnapshot = ReadyDecisionSnapshot();
        AssertBody(
            "combat_decision_ready",
            readyDecision,
            Encoding.ASCII.GetByteCount(readyDecision),
            CanonicalProbeEncoder.EncodePublicCombatDecisionBody(readySnapshot));
        AssertBody(
            "combat_decision_waiting",
            "{\"schema_version\":1,\"status\":\"waiting\",\"decision_kind\":\"combat\",\"actionable\":false,\"decision_id\":null,\"round\":0,\"player\":null,\"enemies\":[],\"hand\":[],\"legal_actions\":[]}",
            168,
            CanonicalProbeEncoder.EncodePublicCombatDecisionBody(PublicCombatDecisionSnapshot.Waiting()));
        AssertBody(
            "combat_decision_unsupported",
            "{\"schema_version\":1,\"status\":\"unsupported\",\"decision_kind\":\"combat\",\"actionable\":false,\"decision_id\":null,\"round\":0,\"player\":null,\"enemies\":[],\"hand\":[],\"legal_actions\":[]}",
            172,
            CanonicalProbeEncoder.EncodePublicCombatDecisionBody(PublicCombatDecisionSnapshot.Unsupported()));
        string completedCombat =
            "{\"schema_version\":1,\"status\":\"complete\",\"decision_kind\":\"combat\",\"actionable\":false,\"decision_id\":null,\"round\":3," +
            "\"player\":{\"hp\":61,\"max_hp\":80,\"block\":0,\"energy\":2}," +
            "\"enemies\":[],\"hand\":[],\"legal_actions\":[],\"outcome\":\"victory\"}";
        AssertBody(
            "combat_decision_complete",
            completedCombat,
            Encoding.ASCII.GetByteCount(completedCombat),
            CanonicalProbeEncoder.EncodePublicCombatDecisionBody(
                PublicCombatDecisionSnapshot.Complete(
                    3,
                    new PublicCombatPlayer(61, 80, 0, 2),
                    Array.Empty<PublicCombatEnemy>(),
                    PublicCombatOutcome.Victory)));

        PublicCombatActionRequest.TryCreate(
            new string('0', 64),
            "play:0:0",
            out PublicCombatActionRequest actionRequest);
        var acceptedAction = PublicCombatActionApplyResult.FromRequest(
            PublicCombatActionApplyOutcome.Accepted,
            actionRequest);
        string acceptedBody =
            "{\"schema_version\":1,\"status\":\"accepted\",\"mutation_state\":\"queued\",\"decision_id\":\"" +
            new string('0', 64) +
            "\",\"action_id\":\"play:0:0\",\"reason\":\"accepted\"}";
        AssertBody(
            "combat_action_accepted",
            acceptedBody,
            Encoding.ASCII.GetByteCount(acceptedBody),
            CanonicalProbeEncoder.EncodePublicCombatActionBody(acceptedAction));

        string readyReward =
            "{\"schema_version\":1,\"status\":\"ready\",\"decision_kind\":\"reward\",\"actionable\":true,\"decision_id\":\"" + new string('0', 64) + "\"," +
            "\"decision_revision\":0," +
            "\"screen_kind\":\"rewards\",\"player\":{\"hp\":74,\"max_hp\":80,\"gold\":99,\"deck_count\":10}," +
            "\"rewards\":[{\"reward_slot\":0,\"reward_index\":0,\"kind\":\"gold\",\"successfully_selected\":false,\"gold_amount\":18,\"cards\":[],\"card_selection_can_skip\":false}," +
            "{\"reward_slot\":1,\"reward_index\":1,\"kind\":\"card\",\"successfully_selected\":false,\"gold_amount\":null,\"cards\":[\"ANGER\",\"BASH\"],\"card_selection_can_skip\":true}," +
            "{\"reward_slot\":2,\"reward_index\":2,\"kind\":\"unsupported\",\"successfully_selected\":false,\"gold_amount\":null,\"cards\":[],\"card_selection_can_skip\":false}]," +
            "\"legal_actions\":[{\"action_id\":\"claim:0\",\"kind\":\"claim_gold\",\"reward_slot\":0,\"card_slot\":null}," +
            "{\"action_id\":\"open:1\",\"kind\":\"open_card\",\"reward_slot\":1,\"card_slot\":null}," +
            "{\"action_id\":\"proceed\",\"kind\":\"proceed\",\"reward_slot\":null,\"card_slot\":null}]}";
        AssertBody(
            "reward_decision_ready",
            readyReward,
            Encoding.ASCII.GetByteCount(readyReward),
            CanonicalProbeEncoder.EncodePublicRewardDecisionBody(ReadyRewardSnapshot()));
        AssertBody(
            "reward_decision_waiting",
            "{\"schema_version\":1,\"status\":\"waiting\",\"decision_kind\":\"reward\",\"actionable\":false,\"decision_id\":null,\"screen_kind\":\"unknown\",\"player\":null,\"rewards\":[],\"legal_actions\":[]}",
            172,
            CanonicalProbeEncoder.EncodePublicRewardDecisionBody(PublicRewardDecisionSnapshot.Waiting()));
        AssertBody(
            "reward_decision_unsupported",
            "{\"schema_version\":1,\"status\":\"unsupported\",\"decision_kind\":\"reward\",\"actionable\":false,\"decision_id\":null,\"screen_kind\":\"unknown\",\"player\":null,\"rewards\":[],\"legal_actions\":[]}",
            176,
            CanonicalProbeEncoder.EncodePublicRewardDecisionBody(PublicRewardDecisionSnapshot.Unsupported()));
        string completedReward =
            "{\"schema_version\":1,\"status\":\"complete\",\"decision_kind\":\"reward\",\"actionable\":false,\"decision_id\":null,\"screen_kind\":\"map\"," +
            "\"player\":{\"hp\":74,\"max_hp\":80,\"gold\":99,\"deck_count\":10},\"rewards\":[],\"legal_actions\":[]}";
        AssertBody(
            "reward_decision_complete",
            completedReward,
            Encoding.ASCII.GetByteCount(completedReward),
            CanonicalProbeEncoder.EncodePublicRewardDecisionBody(
                PublicRewardDecisionSnapshot.Complete(new PublicRewardPlayer(74, 80, 99, 10))));

        PublicRewardActionRequest.TryCreate(
            new string('0', 64),
            PublicRewardActionRequest.ProceedActionId,
            out PublicRewardActionRequest rewardActionRequest);
        var acceptedRewardAction = PublicRewardActionApplyResult.FromRequest(
            PublicRewardActionApplyOutcome.Accepted,
            rewardActionRequest);
        string acceptedRewardBody =
            "{\"schema_version\":1,\"status\":\"accepted\",\"mutation_state\":\"applied\",\"decision_id\":\"" +
            new string('0', 64) +
            "\",\"action_id\":\"proceed\",\"reason\":\"accepted\"}";
        AssertBody(
            "reward_action_accepted",
            acceptedRewardBody,
            Encoding.ASCII.GetByteCount(acceptedRewardBody),
            CanonicalProbeEncoder.EncodePublicRewardActionBody(acceptedRewardAction));

        string readyMap =
            "{\"schema_version\":1,\"status\":\"ready\",\"decision_kind\":\"map\",\"actionable\":true,\"decision_id\":\"" + new string('0', 64) + "\"," +
            "\"screen_kind\":\"map\",\"destination\":null,\"candidates\":[{\"candidate_index\":0,\"col\":2,\"row\":3,\"kind\":\"monster\"}," +
            "{\"candidate_index\":1,\"col\":4,\"row\":3,\"kind\":\"shop\"}]," +
            "\"legal_actions\":[{\"action_id\":\"select:0\",\"kind\":\"select_map_node\",\"candidate_index\":0}," +
            "{\"action_id\":\"select:1\",\"kind\":\"select_map_node\",\"candidate_index\":1}]}";
        AssertBody(
            "map_decision_ready",
            readyMap,
            Encoding.ASCII.GetByteCount(readyMap),
            CanonicalProbeEncoder.EncodePublicMapDecisionBody(ReadyMapSnapshot()));
        string waitingMap =
            "{\"schema_version\":1,\"status\":\"waiting\",\"decision_kind\":\"map\",\"actionable\":false,\"decision_id\":null," +
            "\"screen_kind\":\"unknown\",\"destination\":null,\"candidates\":[],\"legal_actions\":[]}";
        AssertBody(
            "map_decision_waiting",
            waitingMap,
            Encoding.ASCII.GetByteCount(waitingMap),
            CanonicalProbeEncoder.EncodePublicMapDecisionBody(PublicMapDecisionSnapshot.Waiting()));
        string completeMap =
            "{\"schema_version\":1,\"status\":\"complete\",\"decision_kind\":\"map\",\"actionable\":false,\"decision_id\":null," +
            "\"screen_kind\":\"room\",\"destination\":{\"candidate_index\":1,\"col\":4,\"row\":3,\"kind\":\"shop\"}," +
            "\"candidates\":[],\"legal_actions\":[]}";
        AssertBody(
            "map_decision_complete",
            completeMap,
            Encoding.ASCII.GetByteCount(completeMap),
            CanonicalProbeEncoder.EncodePublicMapDecisionBody(
                PublicMapDecisionSnapshot.Complete(new PublicMapCandidate(1, 4, 3, "shop"))));

        PublicMapActionRequest.TryCreate(
            new string('0', 64),
            "select:1",
            out PublicMapActionRequest mapActionRequest);
        var acceptedMapAction = PublicMapActionApplyResult.FromRequest(
            PublicMapActionApplyOutcome.Accepted,
            mapActionRequest);
        string acceptedMapBody =
            "{\"schema_version\":1,\"status\":\"accepted\",\"mutation_state\":\"applied\",\"decision_id\":\"" +
            new string('0', 64) +
            "\",\"action_id\":\"select:1\",\"reason\":\"accepted\"}";
        AssertBody(
            "map_action_accepted",
            acceptedMapBody,
            Encoding.ASCII.GetByteCount(acceptedMapBody),
            CanonicalProbeEncoder.EncodePublicMapActionBody(acceptedMapAction));

        string readyRoom =
            "{\"schema_version\":1,\"status\":\"ready\",\"decision_kind\":\"room\",\"actionable\":true,\"decision_id\":\"" + new string('0', 64) + "\"," +
            "\"screen_kind\":\"rest_site\",\"phase\":\"choose_or_proceed\",\"room_ordinal\":4," +
            "\"candidates\":[{\"candidate_index\":0,\"action_id\":\"choose:0\",\"kind\":\"rest_heal\",\"stable_id\":\"heal\",\"enabled\":true,\"supported\":true,\"is_proceed\":false,\"is_dangerous\":false}," +
            "{\"candidate_index\":1,\"action_id\":\"choose:1\",\"kind\":\"rest_unsupported\",\"stable_id\":\"smith\",\"enabled\":true,\"supported\":false,\"is_proceed\":false,\"is_dangerous\":false}," +
            "{\"candidate_index\":2,\"action_id\":\"proceed\",\"kind\":\"proceed\",\"stable_id\":\"proceed\",\"enabled\":true,\"supported\":true,\"is_proceed\":true,\"is_dangerous\":false}]," +
            "\"legal_actions\":[{\"action_id\":\"choose:0\",\"kind\":\"choose_room_option\",\"candidate_index\":0},{\"action_id\":\"proceed\",\"kind\":\"proceed_room\",\"candidate_index\":2}]}";
        AssertBody(
            "room_decision_ready",
            readyRoom,
            Encoding.ASCII.GetByteCount(readyRoom),
            CanonicalProbeEncoder.EncodePublicRoomDecisionBody(ReadyRoomSnapshot()));
        string waitingRoom =
            "{\"schema_version\":1,\"status\":\"waiting\",\"decision_kind\":\"room\",\"actionable\":false,\"decision_id\":null," +
            "\"screen_kind\":\"unknown\",\"phase\":\"unknown\",\"room_ordinal\":null,\"candidates\":[],\"legal_actions\":[]}";
        AssertBody(
            "room_decision_waiting",
            waitingRoom,
            Encoding.ASCII.GetByteCount(waitingRoom),
            CanonicalProbeEncoder.EncodePublicRoomDecisionBody(PublicRoomDecisionSnapshot.Waiting()));
        string unsupportedRoom =
            "{\"schema_version\":1,\"status\":\"unsupported\",\"decision_kind\":\"room\",\"actionable\":false,\"decision_id\":null," +
            "\"screen_kind\":\"event\",\"phase\":\"unsupported\",\"room_ordinal\":4,\"candidates\":[],\"legal_actions\":[]}";
        AssertBody(
            "room_decision_unsupported",
            unsupportedRoom,
            Encoding.ASCII.GetByteCount(unsupportedRoom),
            CanonicalProbeEncoder.EncodePublicRoomDecisionBody(
                PublicRoomDecisionSnapshot.Unsupported("event", 4)));
        string completeRoom =
            "{\"schema_version\":1,\"status\":\"complete\",\"decision_kind\":\"room\",\"actionable\":false,\"decision_id\":null," +
            "\"screen_kind\":\"rest_site\",\"phase\":\"complete\",\"room_ordinal\":4,\"candidates\":[],\"legal_actions\":[]}";
        AssertBody(
            "room_decision_complete",
            completeRoom,
            Encoding.ASCII.GetByteCount(completeRoom),
            CanonicalProbeEncoder.EncodePublicRoomDecisionBody(
                PublicRoomDecisionSnapshot.Complete("rest_site", 4)));

        PublicRoomActionRequest.TryCreate(
            new string('0', 64),
            PublicRoomActionRequest.ProceedActionId,
            out PublicRoomActionRequest roomActionRequest);
        var acceptedRoomAction = PublicRoomActionApplyResult.FromRequest(
            PublicRoomActionApplyOutcome.Accepted,
            roomActionRequest);
        string acceptedRoomBody =
            "{\"schema_version\":1,\"status\":\"accepted\",\"mutation_state\":\"applied\",\"decision_id\":\"" +
            new string('0', 64) +
            "\",\"action_id\":\"proceed\",\"reason\":\"accepted\"}";
        AssertBody(
            "room_action_accepted",
            acceptedRoomBody,
            Encoding.ASCII.GetByteCount(acceptedRoomBody),
            CanonicalProbeEncoder.EncodePublicRoomActionBody(acceptedRoomAction));

        PublicCombatActionRequest.TryCreate(
            new string('1', 64),
            "end_turn",
            out PublicCombatActionRequest endTurnRequest);
        var limitedAction = PublicCombatActionApplyResult.FromRequest(
            PublicCombatActionApplyOutcome.ActionLimitReached,
            endTurnRequest);
        string limitedBody =
            "{\"schema_version\":1,\"status\":\"rejected\",\"mutation_state\":\"none\",\"decision_id\":\"" +
            new string('1', 64) +
            "\",\"action_id\":\"end_turn\",\"reason\":\"action_limit_reached\"}";
        AssertBody(
            "combat_action_limited",
            limitedBody,
            Encoding.ASCII.GetByteCount(limitedBody),
            CanonicalProbeEncoder.EncodePublicCombatActionBody(limitedAction));

        foreach (ErrorExpectation expectation in ErrorExpectations())
        {
            string expected =
                "{\"schema_version\":1,\"code\":\"" + expectation.Code +
                "\",\"retryable\":" + (expectation.Retryable ? "true" : "false") +
                ",\"mutation_state\":\"none\",\"correlation_id\":\"" + ZeroCorrelationId + "\"}";
            AssertBody(
                "error_" + expectation.StatusCode,
                expected,
                expectation.BodyLength,
                CanonicalProbeEncoder.EncodeErrorBody(expectation.Kind, ZeroCorrelationId));
        }
    }

    private static void CanonicalHttpResponsesAreByteExact()
    {
        AssertResponse(
            200,
            "OK",
            CanonicalProbeEncoder.EncodeHealthBody(ZeroCorrelationId),
            null,
            CanonicalProbeEncoder.EncodeHealthResponse(ZeroCorrelationId));
        AssertResponse(
            200,
            "OK",
            CanonicalProbeEncoder.EncodeManifestBody(ProbeMode.Compatible),
            null,
            CanonicalProbeEncoder.EncodeManifestResponse(ProbeMode.Compatible));
        AssertResponse(
            200,
            "OK",
            CanonicalProbeEncoder.EncodeManifestBody(ProbeMode.IncompatibleLocked),
            null,
            CanonicalProbeEncoder.EncodeManifestResponse(ProbeMode.IncompatibleLocked));

        var snapshots = new[]
        {
            new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.MainMenu),
            new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.Settings),
            new PublicScreenSnapshot(PublicScreenStatus.Waiting, PublicScreenKind.Unknown),
            new PublicScreenSnapshot(PublicScreenStatus.Unsupported, PublicScreenKind.Unknown),
        };
        foreach (PublicScreenSnapshot snapshot in snapshots)
        {
            AssertResponse(
                200,
                "OK",
                CanonicalProbeEncoder.EncodePublicScreenBody(snapshot),
                null,
                CanonicalProbeEncoder.EncodePublicScreenResponse(snapshot));
        }

        PublicCombatDecisionSnapshot decision = ReadyDecisionSnapshot();
        AssertResponse(
            200,
            "OK",
            CanonicalProbeEncoder.EncodePublicCombatDecisionBody(decision),
            null,
            CanonicalProbeEncoder.EncodePublicCombatDecisionResponse(decision));

        PublicCombatActionRequest.TryCreate(
            new string('0', 64),
            "play:0:0",
            out PublicCombatActionRequest actionRequest);
        var accepted = PublicCombatActionApplyResult.FromRequest(
            PublicCombatActionApplyOutcome.Accepted,
            actionRequest);
        AssertResponse(
            200,
            "OK",
            CanonicalProbeEncoder.EncodePublicCombatActionBody(accepted),
            null,
            CanonicalProbeEncoder.EncodePublicCombatActionResponse(accepted));

        foreach (ErrorExpectation expectation in ErrorExpectations())
        {
            AssertResponse(
                expectation.StatusCode,
                expectation.ReasonPhrase,
                CanonicalProbeEncoder.EncodeErrorBody(expectation.Kind, ZeroCorrelationId),
                expectation.AdditionalHeaderLine,
                CanonicalProbeEncoder.EncodeErrorResponse(expectation.Kind, ZeroCorrelationId));
        }
    }

    private static void RoutesAreModeScopedAndExact()
    {
        ReadOnlySpan<string> compatible = ProbeRouteCatalog.RegisteredRoutes(ProbeMode.Compatible);
        TestAssert.Equal(11, compatible.Length, "compatible route count");
        TestAssert.Equal(ProbeRouteCatalog.HealthPath, compatible[0], "health route order");
        TestAssert.Equal(ProbeRouteCatalog.ManifestPath, compatible[1], "manifest route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicScreenPath, compatible[2], "screen route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicCombatDecisionPath, compatible[3], "decision route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicCombatActionPath, compatible[4], "action route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicRewardDecisionPath, compatible[5], "reward decision route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicRewardActionPath, compatible[6], "reward action route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicMapDecisionPath, compatible[7], "map decision route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicMapActionPath, compatible[8], "map action route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicRoomDecisionPath, compatible[9], "room decision route order");
        TestAssert.Equal(ProbeRouteCatalog.PublicRoomActionPath, compatible[10], "room action route order");

        ReadOnlySpan<string> locked = ProbeRouteCatalog.RegisteredRoutes(ProbeMode.IncompatibleLocked);
        TestAssert.Equal(2, locked.Length, "locked route count");
        TestAssert.Equal(ProbeRouteCatalog.HealthPath, locked[0], "locked health route");
        TestAssert.Equal(ProbeRouteCatalog.ManifestPath, locked[1], "locked manifest route");

        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.HealthPath, ProbeMode.Compatible, out ProbeRoute health) &&
            health == ProbeRoute.Health,
            "health route resolution");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.ManifestPath, ProbeMode.IncompatibleLocked, out ProbeRoute manifest) &&
            manifest == ProbeRoute.Manifest,
            "manifest route resolution");
        TestAssert.False(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicScreenPath, ProbeMode.IncompatibleLocked, out _),
            "locked mode omits screen route");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicCombatDecisionPath, ProbeMode.Compatible, out ProbeRoute decision) &&
            decision == ProbeRoute.PublicCombatDecision,
            "combat decision route resolution");
        TestAssert.False(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicCombatDecisionPath, ProbeMode.IncompatibleLocked, out _),
            "locked mode omits combat decision route");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicCombatActionPath, ProbeMode.Compatible, out ProbeRoute action) &&
            action == ProbeRoute.PublicCombatAction,
            "combat action route resolution");
        TestAssert.False(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicCombatActionPath, ProbeMode.IncompatibleLocked, out _),
            "locked mode omits combat action route");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicRewardDecisionPath, ProbeMode.Compatible, out ProbeRoute rewardDecision) &&
            rewardDecision == ProbeRoute.PublicRewardDecision,
            "reward decision route resolution");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicRewardActionPath, ProbeMode.Compatible, out ProbeRoute rewardAction) &&
            rewardAction == ProbeRoute.PublicRewardAction,
            "reward action route resolution");
        TestAssert.False(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicRewardActionPath, ProbeMode.IncompatibleLocked, out _),
            "locked mode omits reward action route");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicMapDecisionPath, ProbeMode.Compatible, out ProbeRoute mapDecision) &&
            mapDecision == ProbeRoute.PublicMapDecision,
            "map decision route resolution");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicMapActionPath, ProbeMode.Compatible, out ProbeRoute mapAction) &&
            mapAction == ProbeRoute.PublicMapAction,
            "map action route resolution");
        TestAssert.False(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicMapActionPath, ProbeMode.IncompatibleLocked, out _),
            "locked mode omits map action route");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicRoomDecisionPath, ProbeMode.Compatible, out ProbeRoute roomDecision) &&
            roomDecision == ProbeRoute.PublicRoomDecision,
            "room decision route resolution");
        TestAssert.True(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicRoomActionPath, ProbeMode.Compatible, out ProbeRoute roomAction) &&
            roomAction == ProbeRoute.PublicRoomAction,
            "room action route resolution");
        TestAssert.False(
            ProbeRouteCatalog.TryResolve(ProbeRouteCatalog.PublicRoomActionPath, ProbeMode.IncompatibleLocked, out _),
            "locked mode omits room action route");
        TestAssert.False(
            ProbeRouteCatalog.TryResolve("/probe/v0/health/", ProbeMode.Compatible, out _),
            "trailing slash is not an alias");
        TestAssert.False(
            ProbeRouteCatalog.TryResolve("/PROBE/v0/health", ProbeMode.Compatible, out _),
            "routes are case-sensitive");
    }

    private static void InvalidContractStatesFailClosed()
    {
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodeHealthBody("ABC"),
            "invalid health correlation ID");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodeErrorBody(ProbeErrorKind.InvalidRequest, new string('A', 32)),
            "uppercase error correlation ID");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicScreenBody(default),
            "default screen snapshot");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicScreenBody(
                new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.Unknown)),
            "invalid ready/unknown screen pair");
        TestAssert.Throws<ArgumentOutOfRangeException>(
            () => CanonicalProbeEncoder.EncodeManifestBody((ProbeMode)99),
            "unknown bridge mode");
        TestAssert.Throws<ArgumentOutOfRangeException>(
            () => ProbeErrorCatalog.Get((ProbeErrorKind)99),
            "unknown error kind");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicCombatDecisionBody(default),
            "default combat decision snapshot");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicCombatDecisionBody(
                PublicCombatDecisionSnapshot.Complete(
                    1,
                    new PublicCombatPlayer(80, 80, 0, 0),
                    new[] { new PublicCombatEnemy(0, "NIBBIT", 43, 43, 0, Array.Empty<string>()) },
                    PublicCombatOutcome.Victory)),
            "victory cannot retain a living enemy");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicCombatActionBody(default),
            "default combat action result");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicRewardDecisionBody(default),
            "default reward decision snapshot");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicRewardActionBody(default),
            "default reward action result");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicMapDecisionBody(default),
            "default map decision snapshot");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicMapActionBody(default),
            "default map action result");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicRoomDecisionBody(default),
            "default room decision snapshot");
        TestAssert.Throws<ArgumentException>(
            () => CanonicalProbeEncoder.EncodePublicRoomActionBody(default),
            "default room action result");
    }

    private static void AssertBody(string name, string expected, int expectedLength, byte[] actual)
    {
        byte[] expectedBytes = Encoding.ASCII.GetBytes(expected);
        TestAssert.Equal(expectedLength, expectedBytes.Length, name + " expected byte count");
        TestAssert.Equal(expectedLength, actual.Length, name + " actual byte count");
        TestAssert.SequenceEqual(expectedBytes, actual, name + " canonical body");
    }

    private static void AssertResponse(
        int statusCode,
        string reasonPhrase,
        byte[] body,
        string? additionalHeaderLine,
        byte[] actual)
    {
        string header =
            "HTTP/1.1 " + statusCode + " " + reasonPhrase + "\r\n" +
            "Content-Type: application/json; charset=utf-8\r\n" +
            "Content-Length: " + body.Length + "\r\n" +
            "Cache-Control: no-store\r\n" +
            "X-Content-Type-Options: nosniff\r\n" +
            (additionalHeaderLine is null ? string.Empty : additionalHeaderLine + "\r\n") +
            "Connection: close\r\n" +
            "\r\n";
        byte[] headerBytes = Encoding.ASCII.GetBytes(header);
        byte[] expected = new byte[headerBytes.Length + body.Length];
        headerBytes.AsSpan().CopyTo(expected);
        body.AsSpan().CopyTo(expected.AsSpan(headerBytes.Length));
        TestAssert.SequenceEqual(expected, actual, "complete HTTP response " + statusCode);
    }

    private static ErrorExpectation[] ErrorExpectations()
    {
        return new[]
        {
            new ErrorExpectation(ProbeErrorKind.InvalidRequest, 400, "Bad Request", "invalid_request", false, 139, null),
            new ErrorExpectation(ProbeErrorKind.Unauthenticated, 401, "Unauthorized", "unauthenticated", false, 139, "WWW-Authenticate: Bearer"),
            new ErrorExpectation(ProbeErrorKind.Forbidden, 403, "Forbidden", "forbidden", false, 133, null),
            new ErrorExpectation(ProbeErrorKind.UnsupportedContent, 404, "Not Found", "unsupported_content", false, 143, null),
            new ErrorExpectation(ProbeErrorKind.ReadOnly, 405, "Method Not Allowed", "read_only", false, 133, "Allow: GET"),
            new ErrorExpectation(ProbeErrorKind.PayloadTooLarge, 413, "Payload Too Large", "payload_too_large", false, 141, null),
            new ErrorExpectation(ProbeErrorKind.RateLimited, 429, "Too Many Requests", "rate_limited", true, 135, "Retry-After: 1"),
            new ErrorExpectation(ProbeErrorKind.BackendFault, 500, "Internal Server Error", "backend_fault", false, 137, null),
            new ErrorExpectation(ProbeErrorKind.BackendUnavailable, 503, "Service Unavailable", "backend_fault", true, 136, null),
        };
    }

    private static PublicCombatDecisionSnapshot ReadyDecisionSnapshot()
    {
        return new PublicCombatDecisionSnapshot(
            PublicDecisionStatus.Ready,
            new string('0', 64),
            1,
            new PublicCombatPlayer(42, 80, 5, 2),
            new[]
            {
                new PublicCombatEnemy(0, "CULTIST", 48, 48, 0, new[] { "Attack" }),
            },
            new[]
            {
                new PublicCombatCard(0, "STRIKE_IRONCLAD", "Attack", "1", "AnyEnemy", true),
            },
            new[]
            {
                new PublicDecisionAction(PublicDecisionActionKind.PlayCard, 0, 0),
                new PublicDecisionAction(PublicDecisionActionKind.EndTurn, -1, -1),
            },
            PublicCombatOutcome.None);
    }

    private static PublicRewardDecisionSnapshot ReadyRewardSnapshot()
    {
        return new PublicRewardDecisionSnapshot(
            PublicDecisionStatus.Ready,
            new string('0', 64),
            "rewards",
            new PublicRewardPlayer(74, 80, 99, 10),
            new[]
            {
                new PublicRewardItem(0, PublicRewardKind.Gold, false, 18, Array.Empty<string>(), false),
                new PublicRewardItem(1, PublicRewardKind.Card, false, 0, new[] { "ANGER", "BASH" }, true),
                new PublicRewardItem(2, PublicRewardKind.Unsupported, false, 0, Array.Empty<string>(), false),
            },
            new[]
            {
                PublicRewardActionRequest.ClaimGoldActionIdFor(0),
                PublicRewardActionRequest.OpenCardActionIdFor(1),
                PublicRewardActionRequest.ProceedActionId,
            });
    }

    private static PublicMapDecisionSnapshot ReadyMapSnapshot()
    {
        return new PublicMapDecisionSnapshot(
            PublicDecisionStatus.Ready,
            new string('0', 64),
            "map",
            null,
            new[]
            {
                new PublicMapCandidate(0, 2, 3, "monster"),
                new PublicMapCandidate(1, 4, 3, "shop"),
            },
            new[] { "select:0", "select:1" });
    }

    private static PublicRoomDecisionSnapshot ReadyRoomSnapshot()
    {
        return new PublicRoomDecisionSnapshot(
            PublicDecisionStatus.Ready,
            new string('0', 64),
            "rest_site",
            "choose_or_proceed",
            4,
            new[]
            {
                new PublicRoomCandidate(
                    0,
                    "choose:0",
                    PublicRoomCandidateKind.RestHeal,
                    "heal",
                    true,
                    true,
                    false,
                    false),
                new PublicRoomCandidate(
                    1,
                    "choose:1",
                    PublicRoomCandidateKind.RestUnsupported,
                    "smith",
                    true,
                    false,
                    false,
                    false),
                new PublicRoomCandidate(
                    2,
                    "proceed",
                    PublicRoomCandidateKind.Proceed,
                    "proceed",
                    true,
                    true,
                    true,
                    false),
            },
            new[] { "choose:0", "proceed" });
    }

    private readonly record struct ErrorExpectation(
        ProbeErrorKind Kind,
        int StatusCode,
        string ReasonPhrase,
        string Code,
        bool Retryable,
        int BodyLength,
        string? AdditionalHeaderLine);
}
