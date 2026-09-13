using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Core.Protocol;

public static class CanonicalProbeEncoder
{
    private const string ManifestCompatible =
        "{\"schema_version\":1,\"protocol\":\"live_probe_v0\",\"bridge_id\":\"sts2_agent_bridge\",\"bridge_version\":\"0.8.0\",\"mode\":\"live_probe_v0\",\"build_compatibility\":\"compatible\",\"target_build_manifest_id\":\"sts2-steam-main-build-23811903-macos-universal\",\"target_game_version\":\"v0.107.1\",\"target_steam_build_id\":\"23811903\",\"capabilities\":{\"observe_public_screen\":true,\"observe_decision\":true,\"apply\":true,\"profile_access\":false,\"privileged_state\":false,\"snapshot_restore\":false,\"bridge_filesystem_writes\":false,\"host_logging\":\"sanitized_existing_sink\",\"harmony_patches\":false,\"outbound_network\":false,\"hot_unload\":false}}";

    private const string ManifestLocked =
        "{\"schema_version\":1,\"protocol\":\"live_probe_v0\",\"bridge_id\":\"sts2_agent_bridge\",\"bridge_version\":\"0.8.0\",\"mode\":\"live_probe_v0\",\"build_compatibility\":\"incompatible_locked\",\"target_build_manifest_id\":\"sts2-steam-main-build-23811903-macos-universal\",\"target_game_version\":\"v0.107.1\",\"target_steam_build_id\":\"23811903\",\"capabilities\":{\"observe_public_screen\":false,\"observe_decision\":false,\"apply\":false,\"profile_access\":false,\"privileged_state\":false,\"snapshot_restore\":false,\"bridge_filesystem_writes\":false,\"host_logging\":\"sanitized_existing_sink\",\"harmony_patches\":false,\"outbound_network\":false,\"hot_unload\":false}}";

    private const string ScreenMainMenu =
        "{\"schema_version\":1,\"status\":\"ready\",\"screen_kind\":\"main_menu\",\"actionable\":false,\"candidates\":[]}";

    private const string ScreenSettings =
        "{\"schema_version\":1,\"status\":\"ready\",\"screen_kind\":\"settings\",\"actionable\":false,\"candidates\":[]}";

    private const string ScreenWaiting =
        "{\"schema_version\":1,\"status\":\"waiting\",\"screen_kind\":\"unknown\",\"actionable\":false,\"candidates\":[]}";

    private const string ScreenUnsupported =
        "{\"schema_version\":1,\"status\":\"unsupported\",\"screen_kind\":\"unknown\",\"actionable\":false,\"candidates\":[]}";

    public static byte[] EncodeHealthBody(string correlationId)
    {
        RequireCorrelationId(correlationId);
        byte[] body = EncodeAscii(
            "{\"schema_version\":1,\"lifecycle_state\":\"running\",\"correlation_id\":\"" +
            correlationId +
            "\"}");
        RequireLength(body, 100);
        return body;
    }

    public static byte[] EncodeManifestBody(ProbeMode mode)
    {
        string body = mode switch
        {
            ProbeMode.Compatible => ManifestCompatible,
            ProbeMode.IncompatibleLocked => ManifestLocked,
            _ => throw new ArgumentOutOfRangeException(nameof(mode)),
        };

        byte[] encoded = EncodeAscii(body);
        RequireLength(encoded, mode == ProbeMode.Compatible ? 604 : 616);
        return encoded;
    }

    public static byte[] EncodePublicCombatDecisionBody(PublicCombatDecisionSnapshot snapshot)
    {
        if (snapshot.Status == PublicDecisionStatus.Complete)
        {
            if (snapshot.Round < 1 || snapshot.Enemies.Count > 6 || snapshot.Hand.Count != 0 ||
                snapshot.LegalActions.Count != 0 || snapshot.DecisionId.Length != 0 ||
                snapshot.Player.MaxHp < 1 || snapshot.Player.Hp > snapshot.Player.MaxHp ||
                snapshot.Outcome is not PublicCombatOutcome.Victory and not PublicCombatOutcome.Defeat ||
                snapshot.Outcome == PublicCombatOutcome.Victory &&
                    (snapshot.Player.Hp < 1 || snapshot.Enemies.Count != 0) ||
                snapshot.Outcome == PublicCombatOutcome.Defeat && snapshot.Player.Hp != 0)
            {
                throw new ArgumentException("Public combat result exceeds the bounded contract.", nameof(snapshot));
            }

            var terminal = new StringBuilder(1024);
            terminal.Append("{\"schema_version\":1,\"status\":\"complete\",\"decision_kind\":\"combat\",\"actionable\":false,\"decision_id\":null,\"round\":");
            terminal.Append(snapshot.Round.ToString(CultureInfo.InvariantCulture));
            terminal.Append(",\"player\":{\"hp\":");
            AppendNonNegative(terminal, snapshot.Player.Hp);
            terminal.Append(",\"max_hp\":");
            AppendNonNegative(terminal, snapshot.Player.MaxHp);
            terminal.Append(",\"block\":");
            AppendNonNegative(terminal, snapshot.Player.Block);
            terminal.Append(",\"energy\":");
            AppendNonNegative(terminal, snapshot.Player.Energy);
            terminal.Append("},\"enemies\":[");
            for (int index = 0; index < snapshot.Enemies.Count; index++)
            {
                PublicCombatEnemy enemy = snapshot.Enemies[index];
                if (index != 0)
                {
                    terminal.Append(',');
                }
                if (enemy.Index != index || enemy.Intents.Count > 8 ||
                    enemy.MaxHp < 1 || enemy.Hp < 1 || enemy.Hp > enemy.MaxHp)
                {
                    throw new ArgumentException("Invalid public enemy projection.", nameof(snapshot));
                }
                terminal.Append("{\"index\":");
                terminal.Append(index.ToString(CultureInfo.InvariantCulture));
                terminal.Append(",\"id\":");
                AppendJsonString(terminal, enemy.Id);
                terminal.Append(",\"hp\":");
                AppendNonNegative(terminal, enemy.Hp);
                terminal.Append(",\"max_hp\":");
                AppendNonNegative(terminal, enemy.MaxHp);
                terminal.Append(",\"block\":");
                AppendNonNegative(terminal, enemy.Block);
                terminal.Append(",\"intents\":[");
                for (int intentIndex = 0; intentIndex < enemy.Intents.Count; intentIndex++)
                {
                    if (intentIndex != 0)
                    {
                        terminal.Append(',');
                    }
                    AppendJsonString(terminal, enemy.Intents[intentIndex]);
                }
                terminal.Append("]}");
            }
            terminal.Append("],\"hand\":[],\"legal_actions\":[],\"outcome\":\"");
            terminal.Append(snapshot.Outcome == PublicCombatOutcome.Victory ? "victory" : "defeat");
            terminal.Append("\"}");
            byte[] terminalBody = EncodeAscii(terminal.ToString());
            if (terminalBody.Length > LiveProbeLimits.MaximumResponseBodyBytes)
            {
                throw new InvalidOperationException("Public combat result exceeds the response limit.");
            }
            return terminalBody;
        }

        if (snapshot.Status != PublicDecisionStatus.Ready)
        {
            if (snapshot.Outcome != PublicCombatOutcome.None)
            {
                throw new ArgumentException("Unsupported public-decision outcome.", nameof(snapshot));
            }
            string status = snapshot.Status switch
            {
                PublicDecisionStatus.Waiting => "waiting",
                PublicDecisionStatus.Unsupported => "unsupported",
                _ => throw new ArgumentException("Unsupported public-decision state.", nameof(snapshot)),
            };
            return EncodeAscii(
                "{\"schema_version\":1,\"status\":\"" + status +
                "\",\"decision_kind\":\"combat\",\"actionable\":false,\"decision_id\":null,\"round\":0," +
                "\"player\":null,\"enemies\":[],\"hand\":[],\"legal_actions\":[]}");
        }

        if (snapshot.Round < 1 || snapshot.Enemies.Count > 6 || snapshot.Hand.Count > 10 ||
            snapshot.LegalActions.Count > 64 ||
            snapshot.Outcome != PublicCombatOutcome.None ||
            !PublicCombatDecisionIdentity.IsCanonical(snapshot.DecisionId))
        {
            throw new ArgumentException("Public combat decision exceeds the bounded contract.", nameof(snapshot));
        }

        var builder = new StringBuilder(2048);
        builder.Append("{\"schema_version\":1,\"status\":\"ready\",\"decision_kind\":\"combat\",\"actionable\":true,\"decision_id\":\"");
        builder.Append(snapshot.DecisionId);
        builder.Append("\",\"round\":");
        builder.Append(snapshot.Round.ToString(CultureInfo.InvariantCulture));
        builder.Append(",\"player\":{\"hp\":");
        AppendNonNegative(builder, snapshot.Player.Hp);
        builder.Append(",\"max_hp\":");
        AppendNonNegative(builder, snapshot.Player.MaxHp);
        builder.Append(",\"block\":");
        AppendNonNegative(builder, snapshot.Player.Block);
        builder.Append(",\"energy\":");
        AppendNonNegative(builder, snapshot.Player.Energy);
        builder.Append("},\"enemies\":[");
        for (int index = 0; index < snapshot.Enemies.Count; index++)
        {
            PublicCombatEnemy enemy = snapshot.Enemies[index];
            if (index != 0)
            {
                builder.Append(',');
            }
            if (enemy.Index != index || enemy.Intents.Count > 8)
            {
                throw new ArgumentException("Invalid public enemy projection.", nameof(snapshot));
            }
            builder.Append("{\"index\":");
            builder.Append(index.ToString(CultureInfo.InvariantCulture));
            builder.Append(",\"id\":");
            AppendJsonString(builder, enemy.Id);
            builder.Append(",\"hp\":");
            AppendNonNegative(builder, enemy.Hp);
            builder.Append(",\"max_hp\":");
            AppendNonNegative(builder, enemy.MaxHp);
            builder.Append(",\"block\":");
            AppendNonNegative(builder, enemy.Block);
            builder.Append(",\"intents\":[");
            for (int intentIndex = 0; intentIndex < enemy.Intents.Count; intentIndex++)
            {
                if (intentIndex != 0)
                {
                    builder.Append(',');
                }
                AppendJsonString(builder, enemy.Intents[intentIndex]);
            }
            builder.Append("]}");
        }

        builder.Append("],\"hand\":[");
        for (int index = 0; index < snapshot.Hand.Count; index++)
        {
            PublicCombatCard card = snapshot.Hand[index];
            if (index != 0)
            {
                builder.Append(',');
            }
            if (card.HandIndex != index)
            {
                throw new ArgumentException("Invalid public hand projection.", nameof(snapshot));
            }
            builder.Append("{\"hand_index\":");
            builder.Append(index.ToString(CultureInfo.InvariantCulture));
            builder.Append(",\"id\":");
            AppendJsonString(builder, card.Id);
            builder.Append(",\"type\":");
            AppendJsonString(builder, card.Type);
            builder.Append(",\"cost\":");
            AppendJsonString(builder, card.Cost);
            builder.Append(",\"target_type\":");
            AppendJsonString(builder, card.TargetType);
            builder.Append(",\"playable\":");
            builder.Append(card.Playable ? "true" : "false");
            builder.Append('}');
        }

        builder.Append("],\"legal_actions\":[");
        for (int index = 0; index < snapshot.LegalActions.Count; index++)
        {
            PublicDecisionAction action = snapshot.LegalActions[index];
            if (index != 0)
            {
                builder.Append(',');
            }
            if (action.Kind == PublicDecisionActionKind.EndTurn)
            {
                builder.Append("{\"action_id\":\"end_turn\",\"kind\":\"end_turn\",\"hand_index\":null,\"target_index\":null}");
                continue;
            }
            if (action.Kind != PublicDecisionActionKind.PlayCard ||
                action.HandIndex < 0 || action.HandIndex >= snapshot.Hand.Count ||
                action.TargetIndex >= snapshot.Enemies.Count)
            {
                throw new ArgumentException("Invalid public legal action.", nameof(snapshot));
            }
            builder.Append("{\"action_id\":\"play:");
            builder.Append(action.HandIndex.ToString(CultureInfo.InvariantCulture));
            if (action.TargetIndex >= 0)
            {
                builder.Append(':');
                builder.Append(action.TargetIndex.ToString(CultureInfo.InvariantCulture));
            }
            builder.Append("\",\"kind\":\"play_card\",\"hand_index\":");
            builder.Append(action.HandIndex.ToString(CultureInfo.InvariantCulture));
            builder.Append(",\"target_index\":");
            if (action.TargetIndex < 0)
            {
                builder.Append("null");
            }
            else
            {
                builder.Append(action.TargetIndex.ToString(CultureInfo.InvariantCulture));
            }
            builder.Append('}');
        }
        builder.Append("]}");

        byte[] body = EncodeAscii(builder.ToString());
        if (body.Length > LiveProbeLimits.MaximumResponseBodyBytes)
        {
            throw new InvalidOperationException("Public combat decision exceeds the response limit.");
        }
        return body;
    }

    public static byte[] EncodePublicRewardDecisionBody(PublicRewardDecisionSnapshot snapshot)
    {
        if (snapshot.Status is PublicDecisionStatus.Waiting or PublicDecisionStatus.Unsupported)
        {
            if (snapshot.DecisionId.Length != 0 || snapshot.ScreenKind != "unknown" ||
                snapshot.Rewards.Count != 0 || snapshot.LegalActions.Count != 0 ||
                snapshot.DecisionRevision != 0)
            {
                throw new ArgumentException("Invalid inactive reward decision.", nameof(snapshot));
            }
            string status = snapshot.Status == PublicDecisionStatus.Waiting
                ? "waiting"
                : "unsupported";
            return EncodeAscii(
                "{\"schema_version\":1,\"status\":\"" + status +
                "\",\"decision_kind\":\"reward\",\"actionable\":false,\"decision_id\":null," +
                "\"screen_kind\":\"unknown\",\"player\":null,\"rewards\":[],\"legal_actions\":[]}");
        }

        ValidateRewardPlayer(snapshot.Player, nameof(snapshot));
        if (snapshot.Status == PublicDecisionStatus.Complete)
        {
            if (snapshot.DecisionId.Length != 0 || snapshot.ScreenKind != "map" ||
                snapshot.Rewards.Count != 0 || snapshot.LegalActions.Count != 0 ||
                snapshot.DecisionRevision < 0)
            {
                throw new ArgumentException("Invalid completed reward decision.", nameof(snapshot));
            }
            var completed = new StringBuilder(320);
            completed.Append("{\"schema_version\":1,\"status\":\"complete\",\"decision_kind\":\"reward\",\"actionable\":false,\"decision_id\":null,\"screen_kind\":\"map\",\"player\":");
            AppendRewardPlayer(completed, snapshot.Player);
            completed.Append(",\"rewards\":[],\"legal_actions\":[]}");
            return EncodeAscii(completed.ToString());
        }

        bool parent = snapshot.ScreenKind == "rewards";
        bool child = snapshot.ScreenKind == "card_reward";
        if (snapshot.Status != PublicDecisionStatus.Ready || (!parent && !child) ||
            !PublicRewardDecisionIdentity.IsCanonical(snapshot.DecisionId) ||
            snapshot.DecisionRevision < 0 || snapshot.Rewards.Count > 8 ||
            parent && (snapshot.LegalActions.Count < 1 || snapshot.LegalActions.Count > (snapshot.PotionSlots is null ? 9 : 17)) ||
            child && (snapshot.Rewards.Count != 1 || snapshot.LegalActions.Count is < 1 or > 6))
        {
            throw new ArgumentException("Reward decision exceeds the bounded contract.", nameof(snapshot));
        }

        var builder = new StringBuilder(1024);
        bool special = System.Linq.Enumerable.Any(snapshot.Rewards, r => r.Kind == PublicRewardKind.SpecialCard);
        builder.Append("{\"schema_version\":");
        bool items = snapshot.PotionSlots is not null || snapshot.ItemRewards || System.Linq.Enumerable.Any(snapshot.Rewards, r => r.Kind is PublicRewardKind.Potion or PublicRewardKind.Relic);
        if(snapshot.CapacityRewards&&snapshot.PotionSlots is null)throw new ArgumentException("Capacity schema needs potion slots.",nameof(snapshot));
        if(snapshot.HealingRewards&&!snapshot.CapacityRewards)throw new ArgumentException("Healing schema needs capacity fields.",nameof(snapshot));
        builder.Append(snapshot.HealingRewards ? "6" : snapshot.CapacityRewards ? "5" : snapshot.PotionSlots is not null ? "4" : items ? "3" : special ? "2" : "1");
        builder.Append(",\"status\":\"ready\",\"decision_kind\":\"reward\",\"actionable\":true,\"decision_id\":\"");
        builder.Append(snapshot.DecisionId);
        builder.Append("\",\"decision_revision\":");
        builder.Append(snapshot.DecisionRevision.ToString(CultureInfo.InvariantCulture));
        builder.Append(",\"screen_kind\":");
        AppendJsonString(builder, snapshot.ScreenKind);
        builder.Append(",\"player\":");
        AppendRewardPlayer(builder, snapshot.Player);
        builder.Append(",\"rewards\":[");
        int previousIndex = -1;
        for (int index = 0; index < snapshot.Rewards.Count; index++)
        {
            PublicRewardItem reward = snapshot.Rewards[index];
            if (reward.RewardIndex <= previousIndex || reward.Cards.Count > 5)
            {
                throw new ArgumentException("Invalid reward projection.", nameof(snapshot));
            }
            previousIndex = reward.RewardIndex;
            if (index != 0)
            {
                builder.Append(',');
            }
            builder.Append("{\"reward_slot\":");
            builder.Append(index.ToString(CultureInfo.InvariantCulture));
            builder.Append(",\"reward_index\":");
            AppendNonNegative(builder, reward.RewardIndex);
            builder.Append(",\"kind\":\"");
            builder.Append(reward.Kind == PublicRewardKind.Gold ? "gold" :
                reward.Kind == PublicRewardKind.Card ? "card" :
                reward.Kind == PublicRewardKind.SpecialCard ? "special_card" :
                reward.Kind == PublicRewardKind.Potion ? "potion" :
                reward.Kind == PublicRewardKind.Relic ? "relic" :
                reward.Kind == PublicRewardKind.Unsupported ? "unsupported" :
                throw new ArgumentException("Unsupported reward kind.", nameof(snapshot)));
            builder.Append("\",\"successfully_selected\":");
            builder.Append(reward.SuccessfullySelected ? "true" : "false");
            builder.Append(",\"gold_amount\":");
            if (reward.Kind == PublicRewardKind.Gold)
            {
                if (reward.Cards.Count != 0 || reward.CardSelectionCanSkip)
                {
                    throw new ArgumentException("Invalid gold reward projection.", nameof(snapshot));
                }
                AppendNonNegative(builder, reward.GoldAmount);
            }
            else if (reward.Kind is PublicRewardKind.Card or PublicRewardKind.SpecialCard)
            {
                if (reward.GoldAmount != 0 || reward.Cards.Count == 0 ||
                    reward.Kind == PublicRewardKind.SpecialCard && (!parent || reward.Cards.Count != 1 || reward.CardSelectionCanSkip))
                {
                    throw new ArgumentException("Invalid card reward projection.", nameof(snapshot));
                }
                builder.Append("null");
            }
            else
            {
                if (reward.GoldAmount != 0 || reward.Cards.Count != 0 ||
                    reward.CardSelectionCanSkip)
                {
                    throw new ArgumentException("Invalid unsupported reward projection.", nameof(snapshot));
                }
                builder.Append("null");
            }
            builder.Append(",\"cards\":[");
            for (int cardIndex = 0; cardIndex < reward.Cards.Count; cardIndex++)
            {
                if (cardIndex != 0)
                {
                    builder.Append(',');
                }
                AppendJsonString(builder, reward.Cards[cardIndex]);
            }
            builder.Append("],\"card_selection_can_skip\":");
            builder.Append(reward.CardSelectionCanSkip ? "true" : "false");
            if(reward.Kind is PublicRewardKind.Potion or PublicRewardKind.Relic) {
                if(!parent||string.IsNullOrEmpty(reward.ItemKey)||reward.ItemKey.Length>128||
                    !System.Linq.Enumerable.All(reward.ItemKey,c=>char.IsAsciiLetterOrDigit(c)||c=='_'))
                    throw new ArgumentException("Invalid item reward key.",nameof(snapshot));
            }else if(reward.ItemKey is not null)throw new ArgumentException("Unexpected item reward key.",nameof(snapshot));
            if(reward.PotionCapacityGain!=0 && (!snapshot.CapacityRewards || reward.Kind!=PublicRewardKind.Relic || reward.ItemKey!="POTION_BELT" || reward.PotionCapacityGain!=2))
                throw new ArgumentException("Invalid capacity reward.",nameof(snapshot));
            if(items) {
                builder.Append(",\"item_key\":");
                if(reward.ItemKey is null)builder.Append("null");else AppendJsonString(builder,reward.ItemKey);
            }
            if(reward.HealAmount<0 || reward.HealAmount!=0&&!snapshot.HealingRewards || snapshot.HealingRewards&&
                reward.HealAmount!=(reward.Kind==PublicRewardKind.Relic&&reward.ItemKey=="FAKE_LEES_WAFFLE"?snapshot.Player.MaxHp/10:0))
                throw new ArgumentException("Unsupported reward healing effect.",nameof(snapshot));
            if(snapshot.CapacityRewards) {
                builder.Append(",\"potion_capacity_gain\":");AppendNonNegative(builder,reward.PotionCapacityGain);
            }
            if(snapshot.HealingRewards) {
                builder.Append(",\"heal_amount\":");AppendNonNegative(builder,reward.HealAmount);
            }
            builder.Append('}');
        }
        builder.Append("],\"legal_actions\":[");
        Span<bool> seenRewardSlots = stackalloc bool[8];
        Span<bool> seenCardSlots = stackalloc bool[5];
        bool seenSkip = false;
        bool seenProceed = false;
        var actionIds=new System.Collections.Generic.HashSet<string>(StringComparer.Ordinal);
        for (int index = 0; index < snapshot.LegalActions.Count; index++)
        {
            if (index != 0)
            {
                builder.Append(',');
            }
            string actionId = snapshot.LegalActions[index];
            if(!actionIds.Add(actionId))throw new ArgumentException("Duplicate reward action.",nameof(snapshot));
            if (!PublicRewardActionRequest.TryCreate(
                    snapshot.DecisionId,
                    actionId,
                    out PublicRewardActionRequest action) ||
                actionId == PublicRewardActionRequest.SkipRewardsActionId)
            {
                throw new ArgumentException("Invalid public reward action.", nameof(snapshot));
            }
            ValidateRewardAction(
                snapshot,
                action,
                parent,
                seenRewardSlots,
                seenCardSlots,
                ref seenSkip,
                ref seenProceed);
            builder.Append("{\"action_id\":");
            AppendJsonString(builder, actionId);
            builder.Append(",\"kind\":");
            AppendJsonString(builder, RewardActionKind(action.Kind));
            builder.Append(",\"reward_slot\":");
            if (action.RewardSlot < 0)
            {
                builder.Append("null");
            }
            else
            {
                builder.Append(action.RewardSlot.ToString(CultureInfo.InvariantCulture));
            }
            builder.Append(",\"card_slot\":");
            if (action.CardSlot < 0)
            {
                builder.Append("null");
            }
            else
            {
                builder.Append(action.CardSlot.ToString(CultureInfo.InvariantCulture));
            }
            if(snapshot.PotionSlots is not null) {
                builder.Append(",\"potion_slot\":");
                if(action.PotionSlot<0)builder.Append("null");else AppendNonNegative(builder,action.PotionSlot);
            }
            builder.Append('}');
        }
        builder.Append(']');
        if(snapshot.PotionSlots is {} potions) {
            if(potions.Count>8)throw new ArgumentException("Potion slot bound.",nameof(snapshot));
            builder.Append(",\"potion_slots\":[");
            for(int i=0;i<potions.Count;i++) {
                if(i>0)builder.Append(',');
                var key=potions[i];
                if(key is null)builder.Append("null");
                else {if(key.Length is <1 or >128 || !System.Linq.Enumerable.All(key,c=>char.IsAsciiLetterOrDigit(c)||c=='_'))throw new ArgumentException("Invalid potion key.",nameof(snapshot));AppendJsonString(builder,key);}
            }
            builder.Append(']');
        }
        builder.Append('}');

        if (parent && !seenProceed || child && !RewardChildActionsAreComplete(
                snapshot,
                seenCardSlots,
                seenSkip))
        {
            throw new ArgumentException("Incomplete public reward action set.", nameof(snapshot));
        }

        byte[] body = EncodeAscii(builder.ToString());
        if (body.Length > LiveProbeLimits.MaximumResponseBodyBytes)
        {
            throw new InvalidOperationException("Public reward decision exceeds the response limit.");
        }
        return body;
    }

    public static byte[] EncodePublicMapDecisionBody(PublicMapDecisionSnapshot snapshot)
    {
        if (snapshot.Status is PublicDecisionStatus.Waiting or PublicDecisionStatus.Unsupported)
        {
            if (snapshot.DecisionId.Length != 0 || snapshot.ScreenKind != "unknown" ||
                snapshot.Destination.HasValue || snapshot.Candidates.Count != 0 ||
                snapshot.LegalActions.Count != 0)
            {
                throw new ArgumentException("Invalid inactive map decision.", nameof(snapshot));
            }
            string status = snapshot.Status == PublicDecisionStatus.Waiting
                ? "waiting"
                : "unsupported";
            return EncodeAscii(
                "{\"schema_version\":1,\"status\":\"" + status +
                "\",\"decision_kind\":\"map\",\"actionable\":false,\"decision_id\":null," +
                "\"screen_kind\":\"unknown\",\"destination\":null,\"candidates\":[],\"legal_actions\":[]}");
        }

        if (snapshot.Status == PublicDecisionStatus.Complete)
        {
            if (snapshot.DecisionId.Length != 0 || snapshot.ScreenKind != "room" ||
                !snapshot.Destination.HasValue || snapshot.Candidates.Count != 0 ||
                snapshot.LegalActions.Count != 0)
            {
                throw new ArgumentException("Invalid completed map decision.", nameof(snapshot));
            }
            PublicMapCandidate destination = snapshot.Destination.Value;
            ValidateMapCandidate(destination, destination.CandidateIndex, nameof(snapshot));
            var completed = new StringBuilder(256);
            completed.Append("{\"schema_version\":1,\"status\":\"complete\",\"decision_kind\":\"map\",\"actionable\":false,\"decision_id\":null,\"screen_kind\":\"room\",\"destination\":");
            AppendMapCandidate(completed, destination);
            completed.Append(",\"candidates\":[],\"legal_actions\":[]}");
            return EncodeAscii(completed.ToString());
        }

        if (snapshot.Status != PublicDecisionStatus.Ready || snapshot.ScreenKind != "map" ||
            snapshot.Destination.HasValue ||
            !PublicMapDecisionIdentity.IsCanonical(snapshot.DecisionId) ||
            snapshot.Candidates.Count is < 1 or > 8 ||
            snapshot.LegalActions.Count != snapshot.Candidates.Count)
        {
            throw new ArgumentException("Map decision exceeds the bounded contract.", nameof(snapshot));
        }

        var builder = new StringBuilder(1024);
        builder.Append("{\"schema_version\":1,\"status\":\"ready\",\"decision_kind\":\"map\",\"actionable\":true,\"decision_id\":\"");
        builder.Append(snapshot.DecisionId);
        builder.Append("\",\"screen_kind\":\"map\",\"destination\":null,\"candidates\":[");
        for (int index = 0; index < snapshot.Candidates.Count; index++)
        {
            if (index != 0)
            {
                builder.Append(',');
            }
            PublicMapCandidate candidate = snapshot.Candidates[index];
            ValidateMapCandidate(candidate, index, nameof(snapshot));
            AppendMapCandidate(builder, candidate);
        }
        builder.Append("],\"legal_actions\":[");
        for (int index = 0; index < snapshot.LegalActions.Count; index++)
        {
            if (index != 0)
            {
                builder.Append(',');
            }
            string actionId = PublicMapActionRequest.ActionIdFor(index);
            if (!string.Equals(snapshot.LegalActions[index], actionId, StringComparison.Ordinal))
            {
                throw new ArgumentException("Invalid public map action.", nameof(snapshot));
            }
            builder.Append("{\"action_id\":\"");
            builder.Append(actionId);
            builder.Append("\",\"kind\":\"select_map_node\",\"candidate_index\":");
            builder.Append(index.ToString(CultureInfo.InvariantCulture));
            builder.Append('}');
        }
        builder.Append("]}");

        byte[] body = EncodeAscii(builder.ToString());
        if (body.Length > LiveProbeLimits.MaximumResponseBodyBytes)
        {
            throw new InvalidOperationException("Public map decision exceeds the response limit.");
        }
        return body;
    }

    public static byte[] EncodePublicRoomDecisionBody(PublicRoomDecisionSnapshot snapshot)
    {
        if (snapshot.Status == PublicDecisionStatus.Waiting)
        {
            if (snapshot.DecisionId.Length != 0 || snapshot.ScreenKind != "unknown" ||
                snapshot.Phase != "unknown" || snapshot.RoomOrdinal != -1 ||
                snapshot.Candidates.Count != 0 || snapshot.LegalActions.Count != 0)
            {
                throw new ArgumentException("Invalid waiting room decision.", nameof(snapshot));
            }
            return EncodeAscii(
                "{\"schema_version\":1,\"status\":\"waiting\",\"decision_kind\":\"room\",\"actionable\":false," +
                "\"decision_id\":null,\"screen_kind\":\"unknown\",\"phase\":\"unknown\"," +
                "\"room_ordinal\":null,\"candidates\":[],\"legal_actions\":[]}");
        }

        if (snapshot.Status == PublicDecisionStatus.Unsupported)
        {
            bool unknown = snapshot.ScreenKind == "unknown" && snapshot.RoomOrdinal == -1;
            bool detected = IsRoomScreenKind(snapshot.ScreenKind) &&
                snapshot.RoomOrdinal is >= 0 and <= 999;
            if (snapshot.DecisionId.Length != 0 || snapshot.Phase != "unsupported" ||
                (!unknown && !detected) || snapshot.Candidates.Count != 0 ||
                snapshot.LegalActions.Count != 0)
            {
                throw new ArgumentException("Invalid unsupported room decision.", nameof(snapshot));
            }
            var unsupported = new StringBuilder(240);
            unsupported.Append("{\"schema_version\":1,\"status\":\"unsupported\",\"decision_kind\":\"room\",\"actionable\":false,\"decision_id\":null,\"screen_kind\":");
            AppendJsonString(unsupported, snapshot.ScreenKind);
            unsupported.Append(",\"phase\":\"unsupported\",\"room_ordinal\":");
            if (snapshot.RoomOrdinal < 0)
            {
                unsupported.Append("null");
            }
            else
            {
                unsupported.Append(snapshot.RoomOrdinal.ToString(CultureInfo.InvariantCulture));
            }
            unsupported.Append(",\"candidates\":[],\"legal_actions\":[]}");
            return EncodeAscii(unsupported.ToString());
        }

        if (snapshot.Status == PublicDecisionStatus.Complete)
        {
            if (snapshot.DecisionId.Length != 0 || !IsRoomScreenKind(snapshot.ScreenKind) ||
                snapshot.Phase != "complete" || snapshot.RoomOrdinal is < 0 or > 999 ||
                snapshot.Candidates.Count != 0 || snapshot.LegalActions.Count != 0)
            {
                throw new ArgumentException("Invalid completed room decision.", nameof(snapshot));
            }
            var completed = new StringBuilder(240);
            completed.Append("{\"schema_version\":1,\"status\":\"complete\",\"decision_kind\":\"room\",\"actionable\":false,\"decision_id\":null,\"screen_kind\":");
            AppendJsonString(completed, snapshot.ScreenKind);
            completed.Append(",\"phase\":\"complete\",\"room_ordinal\":");
            completed.Append(snapshot.RoomOrdinal.ToString(CultureInfo.InvariantCulture));
            completed.Append(",\"candidates\":[],\"legal_actions\":[]}");
            return EncodeAscii(completed.ToString());
        }

        if (snapshot.Status != PublicDecisionStatus.Ready ||
            !PublicRoomDecisionIdentity.IsCanonical(snapshot.DecisionId) ||
            !IsRoomScreenKind(snapshot.ScreenKind) || !IsRoomPhase(snapshot.Phase) ||
            snapshot.RoomOrdinal is < 0 or > 999 ||
            snapshot.Candidates.Count is < 1 or > PublicRoomLimits.MaximumCandidates ||
            snapshot.LegalActions.Count is < 1 or > PublicRoomLimits.MaximumCandidates)
        {
            throw new ArgumentException("Room decision exceeds the bounded contract.", nameof(snapshot));
        }
        ValidateRoomLegalActions(snapshot, nameof(snapshot));

        var builder = new StringBuilder(1536);
        builder.Append("{\"schema_version\":1,\"status\":\"ready\",\"decision_kind\":\"room\",\"actionable\":true,\"decision_id\":\"");
        builder.Append(snapshot.DecisionId);
        builder.Append("\",\"screen_kind\":");
        AppendJsonString(builder, snapshot.ScreenKind);
        builder.Append(",\"phase\":");
        AppendJsonString(builder, snapshot.Phase);
        builder.Append(",\"room_ordinal\":");
        builder.Append(snapshot.RoomOrdinal.ToString(CultureInfo.InvariantCulture));
        builder.Append(",\"candidates\":[");
        for (int index = 0; index < snapshot.Candidates.Count; index++)
        {
            if (index != 0)
            {
                builder.Append(',');
            }
            PublicRoomCandidate candidate = snapshot.Candidates[index];
            ValidateRoomCandidate(candidate, index, snapshot.ScreenKind, nameof(snapshot));
            builder.Append("{\"candidate_index\":");
            builder.Append(index.ToString(CultureInfo.InvariantCulture));
            builder.Append(",\"action_id\":");
            AppendJsonString(builder, candidate.ActionId);
            builder.Append(",\"kind\":");
            AppendJsonString(builder, RoomCandidateKind(candidate.Kind));
            builder.Append(",\"stable_id\":");
            AppendJsonString(builder, candidate.StableId);
            builder.Append(",\"enabled\":");
            builder.Append(candidate.Enabled ? "true" : "false");
            builder.Append(",\"supported\":");
            builder.Append(candidate.Supported ? "true" : "false");
            builder.Append(",\"is_proceed\":");
            builder.Append(candidate.IsProceed ? "true" : "false");
            builder.Append(",\"is_dangerous\":");
            builder.Append(candidate.IsDangerous ? "true" : "false");
            builder.Append('}');
        }
        builder.Append("],\"legal_actions\":[");
        for (int index = 0; index < snapshot.LegalActions.Count; index++)
        {
            if (index != 0)
            {
                builder.Append(',');
            }
            string actionId = snapshot.LegalActions[index];
            if (!PublicRoomActionRequest.TryCreate(snapshot.DecisionId, actionId, out _))
            {
                throw new ArgumentException("Invalid public room action.", nameof(snapshot));
            }
            int candidateIndex = FindRoomCandidate(snapshot.Candidates, actionId);
            if (candidateIndex < 0 || !snapshot.Candidates[candidateIndex].Enabled ||
                !snapshot.Candidates[candidateIndex].Supported)
            {
                throw new ArgumentException("Room action is not backed by an enabled candidate.", nameof(snapshot));
            }
            builder.Append("{\"action_id\":");
            AppendJsonString(builder, actionId);
            builder.Append(",\"kind\":\"");
            builder.Append(actionId == PublicRoomActionRequest.ProceedActionId
                ? "proceed_room"
                : "choose_room_option");
            builder.Append("\",\"candidate_index\":");
            builder.Append(candidateIndex.ToString(CultureInfo.InvariantCulture));
            builder.Append('}');
        }
        builder.Append("]}");

        byte[] body = EncodeAscii(builder.ToString());
        if (body.Length > LiveProbeLimits.MaximumResponseBodyBytes)
        {
            throw new InvalidOperationException("Public room decision exceeds the response limit.");
        }
        return body;
    }

    public static byte[] EncodePublicScreenBody(PublicScreenSnapshot snapshot)
    {
        string body = (snapshot.Status, snapshot.ScreenKind) switch
        {
            (PublicScreenStatus.Ready, PublicScreenKind.MainMenu) => ScreenMainMenu,
            (PublicScreenStatus.Ready, PublicScreenKind.Settings) => ScreenSettings,
            (PublicScreenStatus.Waiting, PublicScreenKind.Unknown) => ScreenWaiting,
            (PublicScreenStatus.Unsupported, PublicScreenKind.Unknown) => ScreenUnsupported,
            _ => throw new ArgumentException("Unsupported public-screen state.", nameof(snapshot)),
        };

        byte[] encoded = EncodeAscii(body);
        int expectedLength = snapshot.Status switch
        {
            PublicScreenStatus.Ready when snapshot.ScreenKind == PublicScreenKind.MainMenu => 98,
            PublicScreenStatus.Ready => 97,
            PublicScreenStatus.Waiting => 98,
            PublicScreenStatus.Unsupported => 102,
            _ => throw new ArgumentException("Unsupported public-screen state.", nameof(snapshot)),
        };
        RequireLength(encoded, expectedLength);
        return encoded;
    }

    public static byte[] EncodeErrorBody(ProbeErrorKind kind, string correlationId)
    {
        RequireCorrelationId(correlationId);
        ProbeErrorDescriptor descriptor = ProbeErrorCatalog.Get(kind);
        byte[] body = EncodeAscii(
            "{\"schema_version\":1,\"code\":\"" +
            descriptor.Code +
            "\",\"retryable\":" +
            (descriptor.Retryable ? "true" : "false") +
            ",\"mutation_state\":\"none\",\"correlation_id\":\"" +
            correlationId +
            "\"}");

        if (body.Length > LiveProbeLimits.MaximumErrorBodyBytes)
        {
            throw new InvalidOperationException("Canonical error body exceeds the frozen limit.");
        }

        return body;
    }

    public static byte[] EncodeHealthResponse(string correlationId)
    {
        return EncodeResponse(200, "OK", EncodeHealthBody(correlationId), null);
    }

    public static byte[] EncodeManifestResponse(ProbeMode mode)
    {
        return EncodeResponse(200, "OK", EncodeManifestBody(mode), null);
    }

    public static byte[] EncodePublicScreenResponse(PublicScreenSnapshot snapshot)
    {
        return EncodeResponse(200, "OK", EncodePublicScreenBody(snapshot), null);
    }

    public static byte[] EncodePublicCombatDecisionResponse(PublicCombatDecisionSnapshot snapshot)
    {
        return EncodeResponse(200, "OK", EncodePublicCombatDecisionBody(snapshot), null);
    }

    public static byte[] EncodePublicCombatActionBody(PublicCombatActionApplyResult result)
    {
        if (result.IsBackendFault ||
            !PublicCombatActionRequest.TryCreate(
                result.DecisionId,
                result.ActionId,
                out _))
        {
            throw new ArgumentException("Invalid public combat action result.", nameof(result));
        }

        string status;
        string mutationState;
        string reason;
        switch (result.Outcome)
        {
            case PublicCombatActionApplyOutcome.Accepted:
                status = "accepted";
                mutationState = "queued";
                reason = "accepted";
                break;
            case PublicCombatActionApplyOutcome.StaleDecision:
                status = "rejected";
                mutationState = "none";
                reason = "stale_decision";
                break;
            case PublicCombatActionApplyOutcome.InvalidAction:
                status = "rejected";
                mutationState = "none";
                reason = "invalid_action";
                break;
            case PublicCombatActionApplyOutcome.AlreadyApplied:
                status = "rejected";
                mutationState = "none";
                reason = "already_applied";
                break;
            case PublicCombatActionApplyOutcome.ActionLimitReached:
                status = "rejected";
                mutationState = "none";
                reason = "action_limit_reached";
                break;
            default:
                throw new ArgumentException("Invalid public combat action outcome.", nameof(result));
        }

        byte[] body = EncodeAscii(
            "{\"schema_version\":1,\"status\":\"" + status +
            "\",\"mutation_state\":\"" + mutationState +
            "\",\"decision_id\":\"" + result.DecisionId +
            "\",\"action_id\":\"" + result.ActionId +
            "\",\"reason\":\"" + reason + "\"}");
        if (body.Length > LiveProbeLimits.MaximumResponseBodyBytes)
        {
            throw new InvalidOperationException("Public combat action exceeds the response limit.");
        }
        return body;
    }

    public static byte[] EncodePublicCombatActionResponse(PublicCombatActionApplyResult result)
    {
        return EncodeResponse(200, "OK", EncodePublicCombatActionBody(result), null);
    }

    public static byte[] EncodePublicRewardDecisionResponse(PublicRewardDecisionSnapshot snapshot)
    {
        return EncodeResponse(200, "OK", EncodePublicRewardDecisionBody(snapshot), null);
    }

    public static byte[] EncodePublicRewardActionBody(PublicRewardActionApplyResult result)
    {
        if (result.IsBackendFault ||
            !PublicRewardActionRequest.TryCreate(result.DecisionId, result.ActionId, out _))
        {
            throw new ArgumentException("Invalid public reward action result.", nameof(result));
        }

        string status;
        string mutationState;
        string reason;
        switch (result.Outcome)
        {
            case PublicRewardActionApplyOutcome.Accepted:
                status = "accepted";
                mutationState = "applied";
                reason = "accepted";
                break;
            case PublicRewardActionApplyOutcome.StaleDecision:
                status = "rejected";
                mutationState = "none";
                reason = "stale_decision";
                break;
            case PublicRewardActionApplyOutcome.InvalidAction:
                status = "rejected";
                mutationState = "none";
                reason = "invalid_action";
                break;
            case PublicRewardActionApplyOutcome.AlreadyApplied:
                status = "rejected";
                mutationState = "none";
                reason = "already_applied";
                break;
            case PublicRewardActionApplyOutcome.ActionLimitReached:
                status = "rejected";
                mutationState = "none";
                reason = "action_limit_reached";
                break;
            default:
                throw new ArgumentException("Invalid public reward action outcome.", nameof(result));
        }

        return EncodeAscii(
            "{\"schema_version\":1,\"status\":\"" + status +
            "\",\"mutation_state\":\"" + mutationState +
            "\",\"decision_id\":\"" + result.DecisionId +
            "\",\"action_id\":\"" + result.ActionId +
            "\",\"reason\":\"" + reason + "\"}");
    }

    public static byte[] EncodePublicRewardActionResponse(PublicRewardActionApplyResult result)
    {
        return EncodeResponse(200, "OK", EncodePublicRewardActionBody(result), null);
    }

    public static byte[] EncodePublicMapDecisionResponse(PublicMapDecisionSnapshot snapshot)
    {
        return EncodeResponse(200, "OK", EncodePublicMapDecisionBody(snapshot), null);
    }

    public static byte[] EncodePublicMapActionBody(PublicMapActionApplyResult result)
    {
        if (result.IsBackendFault ||
            !PublicMapActionRequest.TryCreate(result.DecisionId, result.ActionId, out _))
        {
            throw new ArgumentException("Invalid public map action result.", nameof(result));
        }

        string status;
        string mutationState;
        string reason;
        switch (result.Outcome)
        {
            case PublicMapActionApplyOutcome.Accepted:
                status = "accepted";
                mutationState = "applied";
                reason = "accepted";
                break;
            case PublicMapActionApplyOutcome.StaleDecision:
                status = "rejected";
                mutationState = "none";
                reason = "stale_decision";
                break;
            case PublicMapActionApplyOutcome.InvalidAction:
                status = "rejected";
                mutationState = "none";
                reason = "invalid_action";
                break;
            case PublicMapActionApplyOutcome.AlreadyApplied:
                status = "rejected";
                mutationState = "none";
                reason = "already_applied";
                break;
            case PublicMapActionApplyOutcome.ActionLimitReached:
                status = "rejected";
                mutationState = "none";
                reason = "action_limit_reached";
                break;
            default:
                throw new ArgumentException("Invalid public map action outcome.", nameof(result));
        }

        return EncodeAscii(
            "{\"schema_version\":1,\"status\":\"" + status +
            "\",\"mutation_state\":\"" + mutationState +
            "\",\"decision_id\":\"" + result.DecisionId +
            "\",\"action_id\":\"" + result.ActionId +
            "\",\"reason\":\"" + reason + "\"}");
    }

    public static byte[] EncodePublicMapActionResponse(PublicMapActionApplyResult result)
    {
        return EncodeResponse(200, "OK", EncodePublicMapActionBody(result), null);
    }

    public static byte[] EncodePublicRoomDecisionResponse(PublicRoomDecisionSnapshot snapshot)
    {
        return EncodeResponse(200, "OK", EncodePublicRoomDecisionBody(snapshot), null);
    }

    public static byte[] EncodePublicRoomActionBody(PublicRoomActionApplyResult result)
    {
        if (result.IsBackendFault ||
            !PublicRoomActionRequest.TryCreate(result.DecisionId, result.ActionId, out _))
        {
            throw new ArgumentException("Invalid public room action result.", nameof(result));
        }

        string status;
        string mutationState;
        string reason;
        switch (result.Outcome)
        {
            case PublicRoomActionApplyOutcome.Accepted:
                status = "accepted";
                mutationState = "applied";
                reason = "accepted";
                break;
            case PublicRoomActionApplyOutcome.StaleDecision:
                status = "rejected";
                mutationState = "none";
                reason = "stale_decision";
                break;
            case PublicRoomActionApplyOutcome.InvalidAction:
                status = "rejected";
                mutationState = "none";
                reason = "invalid_action";
                break;
            case PublicRoomActionApplyOutcome.AlreadyApplied:
                status = "rejected";
                mutationState = "none";
                reason = "already_applied";
                break;
            case PublicRoomActionApplyOutcome.ActionLimitReached:
                status = "rejected";
                mutationState = "none";
                reason = "action_limit_reached";
                break;
            default:
                throw new ArgumentException("Invalid public room action outcome.", nameof(result));
        }

        return EncodeAscii(
            "{\"schema_version\":1,\"status\":\"" + status +
            "\",\"mutation_state\":\"" + mutationState +
            "\",\"decision_id\":\"" + result.DecisionId +
            "\",\"action_id\":\"" + result.ActionId +
            "\",\"reason\":\"" + reason + "\"}");
    }

    public static byte[] EncodePublicRoomActionResponse(PublicRoomActionApplyResult result)
    {
        return EncodeResponse(200, "OK", EncodePublicRoomActionBody(result), null);
    }

    public static byte[] EncodeErrorResponse(ProbeErrorKind kind, string correlationId)
    {
        ProbeErrorDescriptor descriptor = ProbeErrorCatalog.Get(kind);
        return EncodeResponse(
            descriptor.StatusCode,
            descriptor.ReasonPhrase,
            EncodeErrorBody(kind, correlationId),
            descriptor.AdditionalHeaderLine);
    }

    private static byte[] EncodeResponse(
        int statusCode,
        string reasonPhrase,
        ReadOnlySpan<byte> body,
        string? additionalHeaderLine)
    {
        if (body.Length > LiveProbeLimits.MaximumResponseBodyBytes)
        {
            throw new InvalidOperationException("Canonical response body exceeds the frozen limit.");
        }

        string header =
            "HTTP/1.1 " + statusCode.ToString(CultureInfo.InvariantCulture) + " " + reasonPhrase + "\r\n" +
            "Content-Type: application/json; charset=utf-8\r\n" +
            "Content-Length: " + body.Length.ToString(CultureInfo.InvariantCulture) + "\r\n" +
            "Cache-Control: no-store\r\n" +
            "X-Content-Type-Options: nosniff\r\n" +
            (additionalHeaderLine is null ? string.Empty : additionalHeaderLine + "\r\n") +
            "Connection: close\r\n" +
            "\r\n";

        byte[] headerBytes = EncodeAscii(header);
        byte[] response = new byte[headerBytes.Length + body.Length];
        headerBytes.AsSpan().CopyTo(response);
        body.CopyTo(response.AsSpan(headerBytes.Length));
        return response;
    }

    private static byte[] EncodeAscii(string value)
    {
        return Encoding.ASCII.GetBytes(value);
    }

    private static void AppendNonNegative(StringBuilder builder, int value)
    {
        if (value < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(value));
        }
        builder.Append(value.ToString(CultureInfo.InvariantCulture));
    }

    private static void ValidateRewardPlayer(PublicRewardPlayer player, string parameterName)
    {
        if (player.MaxHp < 1 || player.Hp < 1 || player.Hp > player.MaxHp ||
            player.Gold < 0 || player.DeckCount < 1)
        {
            throw new ArgumentException("Invalid reward player projection.", parameterName);
        }
    }

    private static string RewardActionKind(PublicRewardActionKind kind) => kind switch
    {
        PublicRewardActionKind.ClaimGold => "claim_gold",
        PublicRewardActionKind.ClaimSpecialCard => "claim_special_card",
        PublicRewardActionKind.CollectItem => "collect_item",
        PublicRewardActionKind.DiscardPotion => "discard_potion",
        PublicRewardActionKind.OpenCard => "open_card",
        PublicRewardActionKind.ChooseCard => "choose_card",
        PublicRewardActionKind.SkipCard => "skip_card",
        PublicRewardActionKind.Proceed => "proceed",
        _ => throw new ArgumentOutOfRangeException(nameof(kind)),
    };

    private static void ValidateRewardAction(
        PublicRewardDecisionSnapshot snapshot,
        PublicRewardActionRequest action,
        bool parent,
        Span<bool> seenRewardSlots,
        Span<bool> seenCardSlots,
        ref bool seenSkip,
        ref bool seenProceed)
    {
        switch (action.Kind)
        {
            case PublicRewardActionKind.DiscardPotion:
                if(!parent||snapshot.PotionSlots is not {} potions||potions.Count==0||potions.Count>8||
                    System.Linq.Enumerable.Any(potions,p=>p is null)||action.PotionSlot<0||action.PotionSlot>=potions.Count||
                    !System.Linq.Enumerable.Any(snapshot.Rewards,r=>r.Kind==PublicRewardKind.Potion&&!r.SuccessfullySelected))
                    throw new ArgumentException("Invalid potion discard action.",nameof(snapshot));
                return;
            case PublicRewardActionKind.ClaimGold:
            case PublicRewardActionKind.ClaimSpecialCard:
            case PublicRewardActionKind.CollectItem:
            case PublicRewardActionKind.OpenCard:
                if (!parent || action.RewardSlot < 0 ||
                    action.RewardSlot >= snapshot.Rewards.Count ||
                    seenRewardSlots[action.RewardSlot])
                {
                    throw new ArgumentException("Invalid parent reward action.", nameof(snapshot));
                }
                PublicRewardItem reward = snapshot.Rewards[action.RewardSlot];
                if(action.Kind==PublicRewardActionKind.CollectItem && reward.PotionCapacityGain>0 && (snapshot.PotionSlots is null || snapshot.PotionSlots.Count+reward.PotionCapacityGain>8))
                    throw new ArgumentException("Capacity gain exceeds slot bound.",nameof(snapshot));
                bool kindMatches = action.Kind == PublicRewardActionKind.ClaimGold
                    ? reward.Kind == PublicRewardKind.Gold
                    : action.Kind == PublicRewardActionKind.ClaimSpecialCard
                        ? reward.Kind == PublicRewardKind.SpecialCard : action.Kind == PublicRewardActionKind.CollectItem
                            ? reward.Kind is PublicRewardKind.Potion or PublicRewardKind.Relic : reward.Kind == PublicRewardKind.Card;
                if (!kindMatches || reward.SuccessfullySelected)
                {
                    throw new ArgumentException("Reward action does not match its slot.", nameof(snapshot));
                }
                seenRewardSlots[action.RewardSlot] = true;
                return;
            case PublicRewardActionKind.ChooseCard:
                if (parent || action.CardSlot < 0 ||
                    action.CardSlot >= snapshot.Rewards[0].Cards.Count ||
                    seenCardSlots[action.CardSlot])
                {
                    throw new ArgumentException("Invalid card choice action.", nameof(snapshot));
                }
                seenCardSlots[action.CardSlot] = true;
                return;
            case PublicRewardActionKind.SkipCard:
                if (parent || seenSkip || !snapshot.Rewards[0].CardSelectionCanSkip)
                {
                    throw new ArgumentException("Invalid card skip action.", nameof(snapshot));
                }
                seenSkip = true;
                return;
            case PublicRewardActionKind.Proceed:
                if (!parent || seenProceed)
                {
                    throw new ArgumentException("Invalid reward proceed action.", nameof(snapshot));
                }
                seenProceed = true;
                return;
            default:
                throw new ArgumentException("Unsupported public reward action.", nameof(snapshot));
        }
    }

    private static bool RewardChildActionsAreComplete(
        PublicRewardDecisionSnapshot snapshot,
        ReadOnlySpan<bool> seenCardSlots,
        bool seenSkip)
    {
        PublicRewardItem reward = snapshot.Rewards[0];
        if (reward.Kind != PublicRewardKind.Card ||
            seenSkip != reward.CardSelectionCanSkip)
        {
            return false;
        }
        for (int index = 0; index < reward.Cards.Count; index++)
        {
            if (!seenCardSlots[index])
            {
                return false;
            }
        }
        return true;
    }

    private static void ValidateMapCandidate(
        PublicMapCandidate candidate,
        int expectedIndex,
        string parameterName)
    {
        if (candidate.CandidateIndex != expectedIndex || candidate.Col is < 0 or > 15 ||
            candidate.Row is < 0 or > 31 ||
            candidate.Kind is not "unknown" and not "shop" and not "treasure" and not "rest_site" and
                not "monster" and not "elite" and not "boss" and not "ancient")
        {
            throw new ArgumentException("Invalid public map candidate.", parameterName);
        }
    }

    private static bool IsRoomScreenKind(string value) =>
        value is "rest_site" or "event";

    private static bool IsRoomPhase(string value) =>
        value is "choose_option" or "proceed" or "choose_or_proceed";

    private static string RoomCandidateKind(PublicRoomCandidateKind kind) => kind switch
    {
        PublicRoomCandidateKind.RestHeal => "rest_heal",
        PublicRoomCandidateKind.RestUnsupported => "rest_unsupported",
        PublicRoomCandidateKind.EventOption => "event_option",
        PublicRoomCandidateKind.Proceed => "proceed",
        _ => throw new ArgumentOutOfRangeException(nameof(kind)),
    };

    private static void ValidateRoomCandidate(
        PublicRoomCandidate candidate,
        int expectedIndex,
        string screenKind,
        string parameterName)
    {
        bool actionMatches = candidate.IsProceed
            ? candidate.ActionId == PublicRoomActionRequest.ProceedActionId
            : candidate.ActionId == PublicRoomActionRequest.ChoiceActionIdFor(expectedIndex);
        bool kindMatches = candidate.Kind switch
        {
            PublicRoomCandidateKind.RestHeal =>
                screenKind == "rest_site" && candidate.Supported && !candidate.IsProceed &&
                !candidate.IsDangerous,
            PublicRoomCandidateKind.RestUnsupported =>
                screenKind == "rest_site" && !candidate.Supported && !candidate.IsProceed &&
                !candidate.IsDangerous,
            PublicRoomCandidateKind.EventOption =>
                screenKind == "event" && !candidate.IsProceed &&
                candidate.Supported == !candidate.IsDangerous,
            PublicRoomCandidateKind.Proceed =>
                screenKind == "rest_site" && candidate.Enabled && candidate.Supported &&
                candidate.IsProceed && !candidate.IsDangerous,
            _ => false,
        };
        if (candidate.CandidateIndex != expectedIndex || !actionMatches || !kindMatches ||
            !PublicRoomDecisionIdentity.IsBoundedPublicId(candidate.StableId) ||
            candidate.IsDangerous && candidate.Enabled)
        {
            throw new ArgumentException("Invalid public room candidate.", parameterName);
        }
    }

    private static void ValidateRoomLegalActions(
        PublicRoomDecisionSnapshot snapshot,
        string parameterName)
    {
        Span<bool> seen = stackalloc bool[PublicRoomLimits.MaximumCandidates];
        foreach (string actionId in snapshot.LegalActions)
        {
            int candidateIndex = FindRoomCandidate(snapshot.Candidates, actionId);
            if (candidateIndex < 0 || seen[candidateIndex] ||
                !snapshot.Candidates[candidateIndex].Enabled ||
                !snapshot.Candidates[candidateIndex].Supported)
            {
                throw new ArgumentException("Invalid public room legal-action set.", parameterName);
            }
            seen[candidateIndex] = true;
        }
        for (int index = 0; index < snapshot.Candidates.Count; index++)
        {
            PublicRoomCandidate candidate = snapshot.Candidates[index];
            if (candidate.Enabled && candidate.Supported != seen[index])
            {
                throw new ArgumentException("Invalid public room legal-action completeness.", parameterName);
            }
        }
    }

    private static int FindRoomCandidate(
        IReadOnlyList<PublicRoomCandidate> candidates,
        string actionId)
    {
        for (int index = 0; index < candidates.Count; index++)
        {
            if (string.Equals(candidates[index].ActionId, actionId, StringComparison.Ordinal))
            {
                return index;
            }
        }
        return -1;
    }

    private static void AppendMapCandidate(StringBuilder builder, PublicMapCandidate candidate)
    {
        builder.Append("{\"candidate_index\":");
        builder.Append(candidate.CandidateIndex.ToString(CultureInfo.InvariantCulture));
        builder.Append(",\"col\":");
        builder.Append(candidate.Col.ToString(CultureInfo.InvariantCulture));
        builder.Append(",\"row\":");
        builder.Append(candidate.Row.ToString(CultureInfo.InvariantCulture));
        builder.Append(",\"kind\":");
        AppendJsonString(builder, candidate.Kind);
        builder.Append('}');
    }

    private static void AppendRewardPlayer(StringBuilder builder, PublicRewardPlayer player)
    {
        builder.Append("{\"hp\":");
        AppendNonNegative(builder, player.Hp);
        builder.Append(",\"max_hp\":");
        AppendNonNegative(builder, player.MaxHp);
        builder.Append(",\"gold\":");
        AppendNonNegative(builder, player.Gold);
        builder.Append(",\"deck_count\":");
        AppendNonNegative(builder, player.DeckCount);
        builder.Append('}');
    }

    private static void AppendJsonString(StringBuilder builder, string value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > 128)
        {
            throw new ArgumentException("Public identifier is empty or too long.", nameof(value));
        }

        builder.Append('"');
        foreach (char item in value)
        {
            switch (item)
            {
                case '"':
                    builder.Append("\\\"");
                    break;
                case '\\':
                    builder.Append("\\\\");
                    break;
                default:
                    if (item < 0x20 || item > 0x7e)
                    {
                        throw new ArgumentException("Public identifier must be printable ASCII.", nameof(value));
                    }
                    builder.Append(item);
                    break;
            }
        }
        builder.Append('"');
    }

    private static void RequireCorrelationId(string correlationId)
    {
        if (!CorrelationIdGenerator.IsCanonical(correlationId))
        {
            throw new ArgumentException("Correlation ID must be 32 lowercase hexadecimal characters.", nameof(correlationId));
        }
    }

    private static void RequireLength(ReadOnlySpan<byte> value, int expected)
    {
        if (value.Length != expected)
        {
            throw new InvalidOperationException("Canonical body length invariant failed.");
        }
    }
}
