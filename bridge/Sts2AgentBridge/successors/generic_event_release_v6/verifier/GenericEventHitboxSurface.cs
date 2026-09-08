using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV6;

// Static IL proof only: the candidate and Godot are never loaded or invoked.
internal static class GenericEventHitboxSurface
{
    private const string Reward = "Sts2AgentBridge.Successors.GenericEventV6.Native.GenericEventV6RewardAdapter";
    private const string Enum = "Sts2AgentBridge.Successors.GenericEventReleaseV5.GenericEventDiagnosticCode";
    internal const string Helper = Reward + ".CandidateHitboxValid(MegaCrit.Sts2.Core.Nodes.GodotExtensions.NClickableControl," + Enum + "&)";
    private const string Validity = "member:Godot.GodotObject.IsInstanceValid(Godot.GodotObject)";

    internal static void AddMethod(string owner, IReadOnlyList<IlInstruction> instructions,
        Func<int,string> describe, int exceptionCount, List<string> inventory)
    {
        if (owner != Helper) return;
        ushort[] shape = { 0x0003,0x001f,0x0054,0x0002,0x0028,0x002d,0x0003,0x001f,0x0054,0x0016,0x002a,0x0017,0x002a };
        if (exceptionCount != 0 || instructions.Count != shape.Length ||
            !instructions.Select(i=>i.OpCode).SequenceEqual(shape) ||
            instructions[1].IntegerConstant != 27 || instructions[7].IntegerConstant != 49 ||
            instructions[4].MetadataToken is not int token || describe(token) != Validity ||
            instructions[5].BranchTarget != instructions[11].Offset) Fail();
        inventory.Add("hitbox_helper|required_liveness_only|27|49");
    }

    internal static void AddCall(string owner,string target,int offset,ushort opcode,List<string> inventory)
    {
        if (target == "method:"+Helper || target.StartsWith("method:"+Reward+".CandidateValid(",StringComparison.Ordinal))
            inventory.Add("hitbox_call|"+owner+"|"+offset.ToString(CultureInfo.InvariantCulture)+"|"+opcode.ToString(CultureInfo.InvariantCulture)+"|"+target);
    }

    internal static void Verify(string[] inventory)
    {
        if (!inventory.Where(x=>x.StartsWith("hitbox_helper|",StringComparison.Ordinal))
            .SequenceEqual(new[]{"hitbox_helper|required_liveness_only|27|49"},StringComparer.Ordinal)) Fail();
        var calls=inventory.Where(x=>x.StartsWith("hitbox_call|",StringComparison.Ordinal)).Select(x=>x.Split('|')).ToArray();
        if (calls.Length!=9 || calls.Any(x=>x.Length!=5 || x[3]!="40")) Fail();
        var helper=calls.Where(x=>x[4]=="method:"+Helper).ToArray();
        if (helper.Length!=2 || helper.Count(x=>x[1].StartsWith(Reward+".TryCreateBindings(",StringComparison.Ordinal))!=1 ||
            helper.Count(x=>x[1].StartsWith(Reward+".TryCaptureBindings(",StringComparison.Ordinal))!=1) Fail();
        var exact=calls.Where(x=>x[4]!="method:"+Helper).ToArray();
        string[] creation={"MegaCrit.Sts2.Core.Nodes.Cards.NCard","MegaCrit.Sts2.Core.Nodes.Cards.NCardHighlight","Godot.ShaderMaterial"};
        string[] snapshot=creation.Append("MegaCrit.Sts2.Core.Nodes.Cards.Holders.NGridCardHolder").ToArray();
        CheckTypes(exact,Reward+".TryCreateBindings(",creation);
        CheckTypes(exact,Reward+".TryCaptureBindings(",snapshot);
    }

    private static void CheckTypes(string[][] calls,string owner,string[] types)
    {
        string prefix="method:"+Reward+".CandidateValid(!!0,"+Enum+","+Enum+","+Enum+"&)";
        string[] expected=types.Select(t=>prefix+"<"+t+">").OrderBy(x=>x,StringComparer.Ordinal).ToArray();
        if (!calls.Where(x=>x[1].StartsWith(owner,StringComparison.Ordinal)).Select(x=>x[4])
            .OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(expected,StringComparer.Ordinal)) Fail();
    }
    private static void Fail()=>throw new VerificationException("hitbox_surface_forbidden");
}
