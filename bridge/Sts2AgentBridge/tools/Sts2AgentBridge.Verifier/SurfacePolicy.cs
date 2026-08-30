using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Sts2AgentBridge.Verifier;

internal sealed class SurfacePolicy
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; set; } = string.Empty;

    [JsonPropertyName("production_assembly")]
    public string ProductionAssembly { get; set; } = string.Empty;

    [JsonPropertyName("allowed_direct_nonframework_references")]
    public string[] AllowedDirectNonframeworkReferences { get; set; } = Array.Empty<string>();

    [JsonPropertyName("forbidden_assembly_references")]
    public string[] ForbiddenAssemblyReferences { get; set; } = Array.Empty<string>();

    [JsonPropertyName("default_deny")]
    public DefaultDenyPolicy DefaultDeny { get; set; } = new();

    [JsonPropertyName("forbidden_namespace_prefixes")]
    public string[] ForbiddenNamespacePrefixes { get; set; } = Array.Empty<string>();

    [JsonPropertyName("forbidden_name_fragments")]
    public string[] ForbiddenNameFragments { get; set; } = Array.Empty<string>();

    [JsonPropertyName("allowed_route_literals")]
    public string[] AllowedRouteLiterals { get; set; } = Array.Empty<string>();

    [JsonPropertyName("game_godot")]
    public GameGodotPolicy GameGodot { get; set; } = new();

    [JsonPropertyName("reflection")]
    public ReflectionPolicy Reflection { get; set; } = new();

    [JsonPropertyName("configuration_structure")]
    public ConfigurationStructurePolicy ConfigurationStructure { get; set; } = new();

    [JsonPropertyName("build_guard_structure")]
    public BuildGuardStructurePolicy BuildGuardStructure { get; set; } = new();

    [JsonPropertyName("transport_structure")]
    public TransportStructurePolicy TransportStructure { get; set; } = new();

    [JsonPropertyName("release_structure")]
    public ReleaseStructurePolicy ReleaseStructure { get; set; } = new();

    [JsonPropertyName("network")]
    public NamespaceMemberPolicy Network { get; set; } = new();

    [JsonPropertyName("filesystem")]
    public FilesystemPolicy Filesystem { get; set; } = new();

    [JsonPropertyName("environment")]
    public EnvironmentPolicy Environment { get; set; } = new();

    public static SurfacePolicy Parse(ReadOnlySpan<byte> data)
    {
        var options = new JsonSerializerOptions
        {
            AllowTrailingCommas = false,
            PropertyNameCaseInsensitive = false,
            ReadCommentHandling = JsonCommentHandling.Disallow,
            UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        };

        SurfacePolicy? policy = JsonSerializer.Deserialize<SurfacePolicy>(data, options);
        if (policy is null || policy.SchemaVersion != "br0_forbidden_surface_v1")
        {
            throw new VerificationException("policy_schema");
        }

        policy.Validate();
        return policy;
    }

    private void Validate()
    {
        RequireExactSet(
            DefaultDeny.NamespaceFamilies,
            new[] { "System.IO", "System.Net" },
            "policy_default_namespace_families");
        RequireExactSet(
            DefaultDeny.ExternalAssemblies,
            new[] { "GodotSharp", "sts2" },
            "policy_default_external_assemblies");
        if (!DefaultDeny.RequireExactTypeClosure ||
            !DefaultDeny.RequireExactMemberClosure ||
            !DefaultDeny.RejectUnresolvedReferences)
        {
            throw new VerificationException("policy_default_deny_disabled");
        }

        if (ProductionAssembly != "Sts2AgentBridge" ||
            Network.NamespaceFamily != "System.Net" ||
            Filesystem.NamespaceFamily != "System.IO" ||
            ConfigurationStructure.SourceRelativePath !=
                "src/Sts2AgentBridge/Core/Configuration/StrictConfigurationLoader.cs" ||
            ConfigurationStructure.SourceSha256.Length != 64 ||
            ConfigurationStructure.TypeStructureSha256.Length != 64 ||
            BuildGuardStructure.SourceRelativePath !=
                "src/Sts2AgentBridge/Adapters/Identity/PinnedBuildGuard.cs" ||
            BuildGuardStructure.ExpectedAssemblyLength != 9_363_456 ||
            BuildGuardStructure.ReadBufferBytes != 65_536 ||
            BuildGuardStructure.ExpectedSha256 !=
                "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18" ||
            BuildGuardStructure.ExpectedBasename != "sts2.dll" ||
            BuildGuardStructure.TargetManifestId !=
                "sts2-steam-main-build-23811903-macos-universal" ||
            BuildGuardStructure.SourceSha256.Length != 64 ||
            BuildGuardStructure.TypeStructureSha256.Length != 64 ||
            TransportStructure.OwnerType !=
                "Sts2AgentBridge.Core.Transport.BoundedLoopbackServer" ||
            TransportStructure.TypeFamilyStructureSha256.Length != 64 ||
            ReleaseStructure.SourceRootRelativePath != "src/Sts2AgentBridge" ||
            ReleaseStructure.SourceFileCount != 43 ||
            string.IsNullOrWhiteSpace(GameGodot.DecisionReaderOwner) ||
            string.IsNullOrWhiteSpace(GameGodot.DecisionReaderIsinstType) ||
            string.IsNullOrWhiteSpace(GameGodot.CombatActionOwner) ||
            string.IsNullOrWhiteSpace(GameGodot.RewardDecisionReaderOwner) ||
            GameGodot.RewardDecisionReaderIsinstTypes.Length == 0 ||
            string.IsNullOrWhiteSpace(GameGodot.RewardActionOwner) ||
            string.IsNullOrWhiteSpace(GameGodot.RewardActionIsinstType) ||
            string.IsNullOrWhiteSpace(GameGodot.MapDecisionReaderOwner) ||
            string.IsNullOrWhiteSpace(GameGodot.MapDecisionReaderIsinstType) ||
            string.IsNullOrWhiteSpace(GameGodot.MapActionOwner) ||
            string.IsNullOrWhiteSpace(GameGodot.MapActionIsinstType) ||
            ReleaseStructure.SourceProjectionSha256.Length != 64 ||
            ReleaseStructure.AssemblyStructureSha256.Length != 64 ||
            !IsLowerHex(ConfigurationStructure.SourceSha256) ||
            !IsLowerHex(ConfigurationStructure.TypeStructureSha256) ||
            !IsLowerHex(BuildGuardStructure.SourceSha256) ||
            !IsLowerHex(BuildGuardStructure.TypeStructureSha256) ||
            !IsLowerHex(TransportStructure.TypeFamilyStructureSha256) ||
            !IsLowerHex(ReleaseStructure.SourceProjectionSha256) ||
            !IsLowerHex(ReleaseStructure.AssemblyStructureSha256))
        {
            throw new VerificationException("policy_identity");
        }

        RequireUnique(AllowedDirectNonframeworkReferences, "policy_direct_references");
        RequireUnique(ForbiddenAssemblyReferences, "policy_forbidden_references");
        RequireUnique(ForbiddenNamespacePrefixes, "policy_forbidden_namespaces");
        RequireUnique(ForbiddenNameFragments, "policy_forbidden_fragments");
        RequireUnique(AllowedRouteLiterals, "policy_routes");
        RequireUnique(GameGodot.AllowedTypes, "policy_game_types");
        RequireUnique(GameGodot.AllowedMembers, "policy_game_members");
        RequireUnique(GameGodot.AllowedOwnerTypes, "policy_game_owner_types");
        RequireUnique(GameGodot.AllowedPrivateInstanceFields, "policy_game_fields");
        RequireUnique(GameGodot.RewardDecisionReaderIsinstTypes, "policy_reward_reader_types");
        RequireUnique(Reflection.AllowedMembers, "policy_reflection_members");
        RequireUnique(Network.AllowedTypes, "policy_network_types");
        RequireUnique(Network.AllowedMembers, "policy_network_members");
        RequireUnique(Network.Owners, "policy_network_owners");
        RequireUnique(Filesystem.AllowedTypes, "policy_filesystem_types");
        RequireUnique(Filesystem.AllowedMembers, "policy_filesystem_members");

        RequireExactSet(
            AllowedDirectNonframeworkReferences,
            new[] { "GodotSharp", "sts2" },
            "policy_direct_references");
        RequireExactSet(
            AllowedRouteLiterals,
            new[]
            {
                "/probe/v0/health",
                "/probe/v0/manifest",
                "/probe/v0/public/screen",
                "/probe/v0/public/combat-decision",
                "/probe/v0/public/combat-action",
                "/probe/v0/public/reward-decision",
                "/probe/v0/public/reward-action",
                "/probe/v0/public/map-decision",
                "/probe/v0/public/map-action",
                "/probe/v0/public/room-decision",
                "/probe/v0/public/room-action",
            },
            "policy_routes");
        RequireExactSet(
            GameGodot.AllowedOwnerTypes,
            new[]
            {
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardParentTarget",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardCardTarget",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardInteractionSession",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardDecisionReader",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardActionApplier",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRoomDecisionReader",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRoomActionApplier",
            },
            "policy_game_owner_types");
        RequireExactSet(
            GameGodot.AllowedPrivateInstanceFields,
            new[]
            {
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardParentTarget.<Button>k__BackingField:MegaCrit.Sts2.Core.Nodes.Rewards.NRewardButton",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardParentTarget.<Reward>k__BackingField:MegaCrit.Sts2.Core.Rewards.Reward",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardParentTarget.<OfferedCards>k__BackingField:System.Collections.Generic.IReadOnlyList<MegaCrit.Sts2.Core.Models.CardModel>",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardCardTarget.<Holder>k__BackingField:MegaCrit.Sts2.Core.Nodes.Cards.Holders.NCardHolder",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardCardTarget.<Model>k__BackingField:MegaCrit.Sts2.Core.Models.CardModel",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardInteractionSession._skippedCardRewards:System.Collections.Generic.List<MegaCrit.Sts2.Core.Rewards.Reward>",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardInteractionSession._parentScreen:MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardInteractionSession._cardScreen:MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NCardRewardSelectionScreen",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardInteractionSession._skipButton:MegaCrit.Sts2.Core.Nodes.Screens.CardSelection.NCardRewardAlternativeButton",
                "Sts2AgentBridge.Adapters.Public.PinnedPublicRewardInteractionSession._player:MegaCrit.Sts2.Core.Entities.Players.Player",
            },
            "policy_game_fields");
    }

    private static void RequireUnique(IEnumerable<string> values, string code)
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (string value in values)
        {
            if (string.IsNullOrWhiteSpace(value) || !seen.Add(value))
            {
                throw new VerificationException(code);
            }
        }
    }

    private static void RequireExactSet(string[] actual, string[] expected, string code)
    {
        var actualSet = new HashSet<string>(actual, StringComparer.Ordinal);
        var expectedSet = new HashSet<string>(expected, StringComparer.Ordinal);
        if (actual.Length != actualSet.Count || !actualSet.SetEquals(expectedSet))
        {
            throw new VerificationException(code);
        }
    }

    private static bool IsLowerHex(string value)
    {
        foreach (char character in value)
        {
            if (character is not (>= '0' and <= '9') and not (>= 'a' and <= 'f'))
            {
                return false;
            }
        }

        return true;
    }
}

internal sealed class DefaultDenyPolicy
{
    [JsonPropertyName("namespace_families")]
    public string[] NamespaceFamilies { get; set; } = Array.Empty<string>();

    [JsonPropertyName("external_assemblies")]
    public string[] ExternalAssemblies { get; set; } = Array.Empty<string>();

    [JsonPropertyName("require_exact_type_closure")]
    public bool RequireExactTypeClosure { get; set; }

    [JsonPropertyName("require_exact_member_closure")]
    public bool RequireExactMemberClosure { get; set; }

    [JsonPropertyName("reject_unresolved_references")]
    public bool RejectUnresolvedReferences { get; set; }
}

internal sealed class GameGodotPolicy
{
    [JsonPropertyName("allowed_types")]
    public string[] AllowedTypes { get; set; } = Array.Empty<string>();

    [JsonPropertyName("allowed_members")]
    public string[] AllowedMembers { get; set; } = Array.Empty<string>();

    [JsonPropertyName("allowed_owner_types")]
    public string[] AllowedOwnerTypes { get; set; } = Array.Empty<string>();

    [JsonPropertyName("allowed_private_instance_fields")]
    public string[] AllowedPrivateInstanceFields { get; set; } = Array.Empty<string>();

    [JsonPropertyName("reader_owner")]
    public string ReaderOwner { get; set; } = string.Empty;

    [JsonPropertyName("reader_isinst_type")]
    public string ReaderIsinstType { get; set; } = string.Empty;

    [JsonPropertyName("decision_reader_owner")]
    public string DecisionReaderOwner { get; set; } = string.Empty;

    [JsonPropertyName("decision_reader_isinst_type")]
    public string DecisionReaderIsinstType { get; set; } = string.Empty;

    [JsonPropertyName("combat_action_owner")]
    public string CombatActionOwner { get; set; } = string.Empty;

    [JsonPropertyName("reward_decision_reader_owner")]
    public string RewardDecisionReaderOwner { get; set; } = string.Empty;

    [JsonPropertyName("reward_decision_reader_isinst_types")]
    public string[] RewardDecisionReaderIsinstTypes { get; set; } = Array.Empty<string>();

    [JsonPropertyName("reward_action_owner")]
    public string RewardActionOwner { get; set; } = string.Empty;

    [JsonPropertyName("reward_action_isinst_type")]
    public string RewardActionIsinstType { get; set; } = string.Empty;

    [JsonPropertyName("map_decision_reader_owner")]
    public string MapDecisionReaderOwner { get; set; } = string.Empty;

    [JsonPropertyName("map_decision_reader_isinst_type")]
    public string MapDecisionReaderIsinstType { get; set; } = string.Empty;

    [JsonPropertyName("map_action_owner")]
    public string MapActionOwner { get; set; } = string.Empty;

    [JsonPropertyName("map_action_isinst_type")]
    public string MapActionIsinstType { get; set; } = string.Empty;

    [JsonPropertyName("dispatcher_constructor_owner")]
    public string DispatcherConstructorOwner { get; set; } = string.Empty;

    [JsonPropertyName("dispatcher_dispose_owner")]
    public string DispatcherDisposeOwner { get; set; } = string.Empty;

    [JsonPropertyName("logger_info_owner")]
    public string LoggerInfoOwner { get; set; } = string.Empty;

    [JsonPropertyName("logger_error_owner")]
    public string LoggerErrorOwner { get; set; } = string.Empty;

    [JsonPropertyName("initializer_owner")]
    public string InitializerOwner { get; set; } = string.Empty;

    [JsonPropertyName("initializer_method")]
    public string InitializerMethod { get; set; } = string.Empty;
}

internal sealed class ReflectionPolicy
{
    [JsonPropertyName("owner")]
    public string Owner { get; set; } = string.Empty;

    [JsonPropertyName("type_token")]
    public string TypeToken { get; set; } = string.Empty;

    [JsonPropertyName("allowed_members")]
    public string[] AllowedMembers { get; set; } = Array.Empty<string>();
}

internal sealed class ConfigurationStructurePolicy
{
    [JsonPropertyName("source_relative_path")]
    public string SourceRelativePath { get; set; } = string.Empty;

    [JsonPropertyName("source_sha256")]
    public string SourceSha256 { get; set; } = string.Empty;

    [JsonPropertyName("type_structure_sha256")]
    public string TypeStructureSha256 { get; set; } = string.Empty;
}

internal sealed class BuildGuardStructurePolicy
{
    [JsonPropertyName("source_relative_path")]
    public string SourceRelativePath { get; set; } = string.Empty;

    [JsonPropertyName("source_sha256")]
    public string SourceSha256 { get; set; } = string.Empty;

    [JsonPropertyName("type_structure_sha256")]
    public string TypeStructureSha256 { get; set; } = string.Empty;

    [JsonPropertyName("expected_assembly_length")]
    public long ExpectedAssemblyLength { get; set; }

    [JsonPropertyName("read_buffer_bytes")]
    public int ReadBufferBytes { get; set; }

    [JsonPropertyName("expected_sha256")]
    public string ExpectedSha256 { get; set; } = string.Empty;

    [JsonPropertyName("expected_basename")]
    public string ExpectedBasename { get; set; } = string.Empty;

    [JsonPropertyName("target_manifest_id")]
    public string TargetManifestId { get; set; } = string.Empty;
}

internal sealed class TransportStructurePolicy
{
    [JsonPropertyName("owner_type")]
    public string OwnerType { get; set; } = string.Empty;

    [JsonPropertyName("type_family_structure_sha256")]
    public string TypeFamilyStructureSha256 { get; set; } = string.Empty;
}

internal sealed class ReleaseStructurePolicy
{
    [JsonPropertyName("source_root_relative_path")]
    public string SourceRootRelativePath { get; set; } = string.Empty;

    [JsonPropertyName("source_file_count")]
    public int SourceFileCount { get; set; }

    [JsonPropertyName("source_projection_sha256")]
    public string SourceProjectionSha256 { get; set; } = string.Empty;

    [JsonPropertyName("assembly_structure_sha256")]
    public string AssemblyStructureSha256 { get; set; } = string.Empty;
}

internal class NamespaceMemberPolicy
{
    [JsonPropertyName("namespace_family")]
    public string NamespaceFamily { get; set; } = string.Empty;

    [JsonPropertyName("allowed_types")]
    public string[] AllowedTypes { get; set; } = Array.Empty<string>();

    [JsonPropertyName("allowed_members")]
    public string[] AllowedMembers { get; set; } = Array.Empty<string>();

    [JsonPropertyName("owners")]
    public string[] Owners { get; set; } = Array.Empty<string>();

    [JsonPropertyName("required_constants")]
    public Dictionary<string, JsonElement> RequiredConstants { get; set; } = new(StringComparer.Ordinal);
}

internal sealed class FilesystemPolicy : NamespaceMemberPolicy
{
    [JsonPropertyName("configuration_owner")]
    public string ConfigurationOwner { get; set; } = string.Empty;

    [JsonPropertyName("build_guard_owner")]
    public string BuildGuardOwner { get; set; } = string.Empty;

    [JsonPropertyName("required_file_mode")]
    public string RequiredFileMode { get; set; } = string.Empty;

    [JsonPropertyName("required_file_access")]
    public string RequiredFileAccess { get; set; } = string.Empty;

    [JsonPropertyName("required_file_share")]
    public string RequiredFileShare { get; set; } = string.Empty;

    [JsonPropertyName("require_link_check_before_use")]
    public bool RequireLinkCheckBeforeUse { get; set; }
}

internal sealed class EnvironmentPolicy
{
    [JsonPropertyName("owner")]
    public string Owner { get; set; } = string.Empty;

    [JsonPropertyName("allowed_member")]
    public string AllowedMember { get; set; } = string.Empty;

    [JsonPropertyName("required_special_folder")]
    public string RequiredSpecialFolder { get; set; } = string.Empty;

    [JsonPropertyName("required_option")]
    public string RequiredOption { get; set; } = string.Empty;
}

internal sealed class VerificationException : Exception
{
    public VerificationException(string code)
        : base(code)
    {
        Code = code;
    }

    public string Code { get; }
}
