using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using Sts2AgentBridge.Verifier;

internal static class CorrectivePolicyDelta
{
    private const string BaselinePolicySha256 =
        "6cde6aac22dd7a8e73416da9b75209ba44bb18d8c9be1e5d92e1d6b4d32af81f";
    private const string BaselineSessionPath =
        "bridge/Sts2AgentBridge/successors/room_flows_v1/shop/core/ShopV1Session.cs";
    private const string BaselineSessionSha256 =
        "8b11fd5f570a7ef8c8536386defe509c61c77ccd4de03e64bc61685c87b6863e";
    private const string CorrectedSessionPath =
        "bridge/Sts2AgentBridge/successors/shop_map_permission_v1/core/ShopV1Session.cs";

    private static readonly string[] ChangedBodyPrefixes =
    {
        "body|Sts2AgentBridge.Successors.RoomFlowsV1.Shop.ShopV1Session.ReconcileClose(",
        "body|Sts2AgentBridge.Successors.RoomFlowsV1.Shop.ShopV1Session.ReconcilePurchase(",
        "body|Sts2AgentBridge.Successors.RoomFlowsV1.Shop.ShopV1Session.TryProject(",
    };

    private const string UnchangedLeavePrefix =
        "body|Sts2AgentBridge.Successors.RoomFlowsV1.Shop.ShopV1Session.ReconcileLeave(";

    internal static void Verify(ShopMapPermissionReleasePolicy corrected)
    {
        ShopMapPermissionReleasePolicy baseline = LoadBaseline();
        VerifySources(baseline, corrected);
        VerifyInventory(baseline, corrected);
    }

    internal static ShopMapPermissionReleasePolicy LoadBaseline()
    {
        Assembly assembly = Assembly.GetExecutingAssembly();
        using Stream stream = assembly.GetManifestResourceStream("baseline.room_release_policy.json")
            ?? throw new VerificationException("corrective_delta_mismatch");
        using var memory = new MemoryStream();
        stream.CopyTo(memory);
        byte[] bytes = memory.ToArray();
        if (ShopMapPermissionReleaseProjectionBuilder.Sha(bytes) != BaselinePolicySha256)
            throw new VerificationException("corrective_delta_mismatch");
        ShopMapPermissionReleasePolicy? policy;
        try
        {
            policy = JsonSerializer.Deserialize<ShopMapPermissionReleasePolicy>(bytes,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = false });
        }
        catch
        {
            throw new VerificationException("corrective_delta_mismatch");
        }
        return policy ?? throw new VerificationException("corrective_delta_mismatch");
    }

    private static void VerifySources(
        ShopMapPermissionReleasePolicy baseline,
        ShopMapPermissionReleasePolicy corrected)
    {
        if (baseline.SourceFiles.Length != 37 || corrected.SourceFiles.Length != 37)
            throw new VerificationException("corrective_delta_mismatch");
        var oldFiles = baseline.SourceFiles.ToDictionary(value => value.Path, StringComparer.Ordinal);
        var newFiles = corrected.SourceFiles.ToDictionary(value => value.Path, StringComparer.Ordinal);
        if (!oldFiles.Remove(BaselineSessionPath, out PolicySourceFile? oldSession) ||
            oldSession.Sha256 != BaselineSessionSha256 ||
            !newFiles.Remove(CorrectedSessionPath, out PolicySourceFile? newSession) ||
            newSession.Sha256 == BaselineSessionSha256 ||
            oldFiles.ContainsKey(CorrectedSessionPath) || newFiles.ContainsKey(BaselineSessionPath) ||
            oldFiles.Count != 36 || newFiles.Count != 36)
            throw new VerificationException("corrective_delta_mismatch");
        foreach ((string path, PolicySourceFile oldFile) in oldFiles)
        {
            if (!newFiles.TryGetValue(path, out PolicySourceFile? newFile) ||
                newFile.Sha256 != oldFile.Sha256)
                throw new VerificationException("corrective_delta_mismatch");
        }
    }

    private static void VerifyInventory(
        ShopMapPermissionReleasePolicy baseline,
        ShopMapPermissionReleasePolicy corrected)
    {
        if (baseline.CheckedMethodBodies != corrected.CheckedMethodBodies ||
            baseline.CheckedMethodBodies != 931)
            throw new VerificationException("corrective_delta_mismatch");
        foreach (string prefix in ChangedBodyPrefixes)
        {
            string oldBody = RequireSingle(baseline.MetadataInventory, prefix);
            string newBody = RequireSingle(corrected.MetadataInventory, prefix);
            if (oldBody == newBody)
                throw new VerificationException("corrective_delta_mismatch");
        }
        if (RequireSingle(baseline.MetadataInventory, UnchangedLeavePrefix) !=
            RequireSingle(corrected.MetadataInventory, UnchangedLeavePrefix))
            throw new VerificationException("corrective_delta_mismatch");

        string[] oldStable = baseline.MetadataInventory.Where(IsStableRow).ToArray();
        string[] newStable = corrected.MetadataInventory.Where(IsStableRow).ToArray();
        if (!oldStable.SequenceEqual(newStable, StringComparer.Ordinal))
            throw new VerificationException("corrective_delta_mismatch");

        VerifyIdentityRows(baseline.MetadataInventory, corrected.MetadataInventory);
        if (RequireSingle(baseline.MetadataInventory, "metadata_raw|") ==
            RequireSingle(corrected.MetadataInventory, "metadata_raw|") ||
            RequireSingle(baseline.MetadataInventory, "module|") ==
            RequireSingle(corrected.MetadataInventory, "module|"))
            throw new VerificationException("corrective_delta_mismatch");
    }

    private static bool IsStableRow(string row) =>
        !ChangedBodyPrefixes.Any(prefix => row.StartsWith(prefix, StringComparison.Ordinal)) &&
        !row.StartsWith("metadata_raw|", StringComparison.Ordinal) &&
        !row.StartsWith("module|", StringComparison.Ordinal) &&
        !row.StartsWith("section|", StringComparison.Ordinal) &&
        !row.StartsWith("field_def|<PrivateImplementationDetails>.", StringComparison.Ordinal);

    private static void VerifyIdentityRows(
        IReadOnlyList<string> baseline,
        IReadOnlyList<string> corrected)
    {
        VerifyModule(RequireSingle(baseline, "module|"));
        VerifyModule(RequireSingle(corrected, "module|"));
        _ = RequireSingle(baseline, "metadata_raw|");
        _ = RequireSingle(corrected, "metadata_raw|");

        var oldSections = Sections(baseline);
        var newSections = Sections(corrected);
        if (oldSections.Count != 3 || newSections.Count != 3 ||
            !oldSections.Keys.OrderBy(value => value, StringComparer.Ordinal).SequenceEqual(
                new[] { ".reloc", ".rsrc", ".text" }, StringComparer.Ordinal) ||
            oldSections[".rsrc"] != newSections[".rsrc"])
            throw new VerificationException("corrective_delta_mismatch");
        string[] oldText = oldSections[".text"].Split('|');
        string[] newText = newSections[".text"].Split('|');
        string[] oldReloc = oldSections[".reloc"].Split('|');
        string[] newReloc = newSections[".reloc"].Split('|');
        if (oldText.Length != 6 || newText.Length != 6 ||
            !int.TryParse(oldText[2], out int oldVirtualSize) ||
            !int.TryParse(newText[2], out int newVirtualSize) || newVirtualSize != oldVirtualSize - 24 ||
            oldText[3] != newText[3] || oldText[4] != newText[4] || oldText[5] == newText[5] ||
            oldReloc.Length != 6 || newReloc.Length != 6 ||
            !oldReloc.Take(5).SequenceEqual(newReloc.Take(5), StringComparer.Ordinal) ||
            oldReloc[5] == newReloc[5])
            throw new VerificationException("corrective_delta_mismatch");

        var oldFields = PrivateImplementationFields(baseline);
        var newFields = PrivateImplementationFields(corrected);
        if (oldFields.Count != 18 || newFields.Count != 18 ||
            !oldFields.Keys.OrderBy(value => value, StringComparer.Ordinal).SequenceEqual(
                newFields.Keys.OrderBy(value => value, StringComparer.Ordinal), StringComparer.Ordinal))
            throw new VerificationException("corrective_delta_mismatch");
        foreach (string key in oldFields.Keys)
        {
            string[] oldField = oldFields[key];
            string[] newField = newFields[key];
            if (oldField.Length != 7 || newField.Length != 7 ||
                !oldField.Take(5).SequenceEqual(newField.Take(5), StringComparer.Ordinal) ||
                oldField[6] != newField[6] ||
                !int.TryParse(oldField[5], out int oldRva) ||
                !int.TryParse(newField[5], out int newRva) || newRva != oldRva - 24)
                throw new VerificationException("corrective_delta_mismatch");
        }
    }

    private static void VerifyModule(string module)
    {
        string[] fields = module.Split('|');
        if (fields.Length != 5 || fields[1] != "Sts2AgentBridgeRoomFlowsV1.dll" ||
            !Guid.TryParse(fields[2], out _) || fields[3].Length != 0 || fields[4].Length != 0)
            throw new VerificationException("corrective_delta_mismatch");
    }

    private static Dictionary<string, string> Sections(IReadOnlyList<string> rows) =>
        rows.Where(row => row.StartsWith("section|", StringComparison.Ordinal))
            .ToDictionary(row => row.Split('|')[1], StringComparer.Ordinal);

    private static Dictionary<string, string[]> PrivateImplementationFields(IReadOnlyList<string> rows) =>
        rows.Where(row => row.StartsWith("field_def|<PrivateImplementationDetails>.", StringComparison.Ordinal))
            .Select(row => row.Split('|'))
            .ToDictionary(fields => fields[1], StringComparer.Ordinal);

    private static string RequireSingle(IReadOnlyList<string> rows, string prefix)
    {
        string[] matches = rows.Where(row => row.StartsWith(prefix, StringComparison.Ordinal)).ToArray();
        if (matches.Length != 1)
            throw new VerificationException("corrective_delta_mismatch");
        return matches[0];
    }
}
