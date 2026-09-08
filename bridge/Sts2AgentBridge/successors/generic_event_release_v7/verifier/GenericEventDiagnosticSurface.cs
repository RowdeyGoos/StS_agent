using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV7;

// Bounded interpretation of metadata and a literal switch, never CLR execution.
// This independently verifies the vocabulary and cache-only accessor in addition
// to the exact whole-assembly and method-body policy.
internal static class GenericEventDiagnosticSurface
{
    internal const string Prefix = "Sts2AgentBridge.Successors.GenericEventReleaseV7.";
    internal const string FrozenPrefix = "Sts2AgentBridge.Successors.GenericEventReleaseV5.";
    internal const string Native = "Sts2AgentBridge.Successors.GenericEventV7.Native.PinnedGenericEventV7NativeAdapter";
    internal const string EnumType = FrozenPrefix + "GenericEventDiagnosticCode";
    private static readonly string[] Names = { "NotCaptured","ParentReady","ParentUnavailable","ParentWaiting","PendingBindingFailed","PendingOwnership","PendingContext","PendingTaskFailed","PendingChosenEntry","PendingChosenTask","PendingChosenCompletion","PendingRequestTask","PendingScreen","PendingSelectorlessRequest","PendingOverlay","PendingDeck","PendingOffers","PendingProceed","PrepareBinding","PrepareScreen","PrepareExternalSelector","PrepareDeck","PrepareForeground","PrepareFamily","PrepareGridNode","PrepareGridState","PrepareHolders","PrepareCandidates","PrepareGeometry","PreparePreviewNodes","PreparePreviewState","PrepareConfirm","ChildReady","MapReady","CaptureDisposed","CaptureException","DiagnosticUnavailable","CandidateExpectedNull","CandidateExpectedDuplicate","CandidateDisplayedNull","CandidateUnexpectedModel","CandidateDisplayedDuplicate","CandidateModelNull","CandidateCardNull","CandidateHitboxNull","CandidateHighlightNull","CandidateCardType","CandidateCardInvalid","CandidateHitboxType","CandidateHitboxInvalid","CandidateHighlightType","CandidateHighlightInvalid","CandidateMaterialNull","CandidateMaterialKind","CandidateMaterialType","CandidateMaterialInvalid","CandidateStableKey","CandidateDomainCount","CandidateDomainBounds","CandidateSnapshotCount","CandidateHolderIdentity","CandidateHolderType","CandidateHolderInvalid","CandidateModelIdentity","CandidateCardIdentity","CandidateHitboxIdentity","CandidateHighlightIdentity","CandidateMaterialIdentity","CandidateKeyChanged","CandidateLevelChanged","CandidateShaderRead","CandidateHighlightUnsettled","CandidateInitiallySelected","CandidateHolderInvisible","CandidateCardInvisible","CandidateHitboxInvisible","CandidateEnabledRead","CandidateNoneEnabled" };
    private static readonly string[] Words = { "none","parent_ready","parent_unavailable","parent_waiting","pending_binding_failed","pending_ownership","pending_context","pending_task_failed","pending_chosen_entry","pending_chosen_task","pending_chosen_completion","pending_request_task","pending_screen","pending_selectorless_request","pending_overlay","pending_deck","pending_offers","pending_proceed","prepare_binding","prepare_screen","prepare_external_selector","prepare_deck","prepare_foreground","prepare_family","prepare_grid_node","prepare_grid_state","prepare_holders","prepare_candidates","prepare_geometry","prepare_preview_nodes","prepare_preview_state","prepare_confirm","child_ready","map_ready","capture_disposed","capture_exception","diagnostic_unavailable","candidate_expected_null","candidate_expected_duplicate","candidate_displayed_null","candidate_unexpected_model","candidate_displayed_duplicate","candidate_model_null","candidate_card_null","candidate_hitbox_null","candidate_highlight_null","candidate_card_type","candidate_card_invalid","candidate_hitbox_type","candidate_hitbox_invalid","candidate_highlight_type","candidate_highlight_invalid","candidate_material_null","candidate_material_kind","candidate_material_type","candidate_material_invalid","candidate_stable_key","candidate_domain_count","candidate_domain_bounds","candidate_snapshot_count","candidate_holder_identity","candidate_holder_type","candidate_holder_invalid","candidate_model_identity","candidate_card_identity","candidate_hitbox_identity","candidate_highlight_identity","candidate_material_identity","candidate_key_changed","candidate_level_changed","candidate_shader_read","candidate_highlight_unsettled","candidate_initially_selected","candidate_holder_invisible","candidate_card_invisible","candidate_hitbox_invisible","candidate_enabled_read","candidate_none_enabled" };

    internal static void AddEnum(MetadataReader reader, TypeDefinition definition, string name, List<string> inventory)
    {
        if (name != EnumType) return;
        if (definition.GetFields().Count != 79 || definition.BaseType.IsNil ||
            MetadataNames.EntityTypeName(reader,definition.BaseType,new MetadataNames()) != "System.Enum") Fail();
        foreach (var handle in definition.GetFields())
        {
            var field = reader.GetFieldDefinition(handle);
            string fieldName = reader.GetString(field.Name);
            if (field.DecodeSignature(new MetadataNames(),null) != (fieldName == "value__" ? "System.Int32" : EnumType)) Fail();
            if (fieldName == "value__") continue;
            if (field.GetDefaultValue().IsNil) Fail();
            var value = reader.GetConstant(field.GetDefaultValue());
            var blob = reader.GetBlobReader(value.Value);
            if (value.TypeCode != ConstantTypeCode.Int32 || blob.Length != 4) Fail();
            inventory.Add("diagnostic_enum|" + fieldName + "|" + blob.ReadInt32().ToString(CultureInfo.InvariantCulture));
        }
    }

    internal static void AddMethod(string owner, IReadOnlyList<IlInstruction> instructions,
        MetadataReader reader, Func<int,string> describe, int exceptionCount, List<string> inventory)
    {
        if (owner == Native + ".get_LastDiagnostic()")
        {
            if (exceptionCount != 0 || instructions.Count != 3 || instructions[0].OpCode != 0x0002 ||
                instructions[1].OpCode != 0x007b || instructions[1].MetadataToken is not int token ||
                describe(token) != "field:" + Native + ".<LastDiagnostic>k__BackingField" || instructions[2].OpCode != 0x002a) Fail();
            inventory.Add("diagnostic_accessor|cached_field_only");
        }
        if (owner != FrozenPrefix + "GenericEventDiagnosticCodec.Encode(" + EnumType + ")") return;
        if (exceptionCount != 0 || instructions.Count > 512 ||
            instructions.Count(i => i.OpCode == 0x0045) != 1 ||
            instructions.Single(i => i.OpCode == 0x0045).SwitchTargets.Length != 78 ||
            instructions.Any(i => i.OpCode is not (0x0000 or 0x0002 or 0x0006 or 0x000a or 0x002a or 0x002b or 0x0038 or 0x0045 or 0x0072))) Fail();
        for (int value = 0; value < 78; value++)
            inventory.Add("diagnostic_mapping|" + value.ToString(CultureInfo.InvariantCulture) + "|" + Evaluate(instructions, reader, value));
        if (Evaluate(instructions, reader, -1) != "diagnostic_unavailable" ||
            Evaluate(instructions, reader, 78) != "diagnostic_unavailable" ||
            Evaluate(instructions, reader, int.MinValue) != "diagnostic_unavailable" ||
            Evaluate(instructions, reader, int.MaxValue) != "diagnostic_unavailable") Fail();
        inventory.Add("diagnostic_mapping_default|diagnostic_unavailable");
    }

    private static string Evaluate(IReadOnlyList<IlInstruction> instructions, MetadataReader reader, int argument)
    {
        var offsets = instructions.Select((i,n) => (i.Offset,n)).ToDictionary(x => x.Offset,x => x.n);
        var stack = new Stack<object>(); object? local = null; int pc = 0;
        for (int step = 0; step < 512 && pc >= 0 && pc < instructions.Count; step++)
        {
            var instruction = instructions[pc++];
            switch (instruction.OpCode)
            {
                case 0x0000: break;
                case 0x0002: stack.Push(argument); break;
                case 0x0006: stack.Push(local ?? throw new VerificationException("diagnostic_surface_forbidden")); break;
                case 0x000a: local = stack.Pop(); break;
                case 0x0045:
                    if (stack.Pop() is not int selector) Fail();
                    else if (selector >= 0 && selector < instruction.SwitchTargets.Length) pc = offsets[instruction.SwitchTargets[selector]];
                    break;
                case 0x0072: stack.Push(reader.GetUserString(MetadataTokens.UserStringHandle(instruction.MetadataToken!.Value))); break;
                case 0x002b: case 0x0038: pc = offsets[instruction.BranchTarget!.Value]; break;
                case 0x002a:
                    if (stack.Count == 1 && stack.Pop() is string text) return text;
                    Fail(); break;
                default: Fail(); break;
            }
        }
        throw new VerificationException("diagnostic_surface_forbidden");
    }

    internal static void AddCall(string owner, string target, int offset, List<string> inventory)
    {
        if (target == "method:" + Native + ".get_LastDiagnostic()" ||
            target == "method:" + Native + ".set_LastDiagnostic(" + EnumType + ")" ||
            target == "method:" + Prefix + "GenericEventTransportRuntime.CaptureDiagnostic()" ||
            target == "member:System.Func<" + EnumType + ">.Invoke()" ||
            target == "method:" + FrozenPrefix + "GenericEventDiagnosticCodec.Encode(" + EnumType + ")")
            inventory.Add("diagnostic_call|" + owner + "|" + offset.ToString(CultureInfo.InvariantCulture) + "|" + target);
    }

    internal static void Verify(string[] inventory, string[] critical)
    {
        string[] diagnosticTypes = inventory.Where(x => x.StartsWith("type_def|", StringComparison.Ordinal))
            .Select(x => x.Split('|')[1]).Where(x => x.EndsWith(".GenericEventDiagnosticCode", StringComparison.Ordinal) ||
                x.EndsWith(".GenericEventDiagnosticCodec", StringComparison.Ordinal)).OrderBy(x => x, StringComparer.Ordinal).ToArray();
        if (!diagnosticTypes.SequenceEqual(new[] { EnumType, FrozenPrefix + "GenericEventDiagnosticCodec" }, StringComparer.Ordinal)) Fail();
        string[] expected = Names.Select((name,index) => "diagnostic_enum|" + name + "|" + index.ToString(CultureInfo.InvariantCulture))
            .Concat(Words.Select((word,index) => "diagnostic_mapping|" + index.ToString(CultureInfo.InvariantCulture) + "|" + word))
            .Concat(new[]{"diagnostic_accessor|cached_field_only", "diagnostic_mapping_default|diagnostic_unavailable"})
            .OrderBy(x => x,StringComparer.Ordinal).ToArray();
        if (!inventory.Where(x => x.StartsWith("diagnostic_",StringComparison.Ordinal) && !x.StartsWith("diagnostic_call|",StringComparison.Ordinal))
            .OrderBy(x => x,StringComparer.Ordinal).SequenceEqual(expected,StringComparer.Ordinal)) Fail();
        var calls = inventory.Where(x => x.StartsWith("diagnostic_call|",StringComparison.Ordinal)).Select(x => x.Split('|')).ToArray();
        if (calls.Any(x => x.Length != 4) || calls.Length != 6) Fail();
        RequireCalls(calls, Native + ".get_LastDiagnostic()", Prefix + "ProductionGenericEventRuntimeFactory+Runtime.ReadDiagnostic()", 1);
        RequireCalls(calls, Native + ".set_LastDiagnostic(" + EnumType + ")", Native + ".Capture()", 2);
        RequireCalls(calls, "System.Func<" + EnumType + ">.Invoke()", Prefix + "GenericEventTransportRuntime.CaptureDiagnostic()", 1);
        RequireCalls(calls, FrozenPrefix + "GenericEventDiagnosticCodec.Encode(" + EnumType + ")", Prefix + "GenericEventTransportHttpEncoder.Wrap(System.Byte[]," + EnumType + ")", 1);
        var sample = calls.Where(x => x[3] == "method:" + Prefix + "GenericEventTransportRuntime.CaptureDiagnostic()").ToArray();
        var handle = critical.Where(x => x.Contains(".GenericEventV7WireService.Handle(",StringComparison.Ordinal)).Select(x => x.Split('|')).ToArray();
        if (sample.Length != 1 || handle.Length != 1 || sample[0][1] != handle[0][1] ||
            !int.TryParse(sample[0][2],out int after) || !int.TryParse(handle[0][2],out int before) || after <= before) Fail();
    }

    private static void RequireCalls(string[][] calls,string target,string owner,int count)
    {
        var found = calls.Where(x => x[3] == "method:"+target || x[3] == "member:"+target).ToArray();
        if (found.Length != count || found.Any(x => x[1] != owner)) Fail();
    }
    private static void Fail() => throw new VerificationException("diagnostic_surface_forbidden");
}
