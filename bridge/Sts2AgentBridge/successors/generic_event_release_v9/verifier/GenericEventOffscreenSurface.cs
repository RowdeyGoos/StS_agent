using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV9;

// The exact policy binds complete IL bodies. This additional gate confines the
// newly admitted geometry reads to their reviewed adapter helper methods.
internal static class GenericEventOffscreenSurface
{
    internal const string Probe = "Sts2AgentBridge.Successors.GenericEventV7.Native.GenericEventV7TransformAdapter+ProbeGeometry";
    internal const string Node = Probe + "+NodeGeometry";
    private static readonly Dictionary<string,string[]> Readers = new(StringComparer.Ordinal)
    {
        ["member:Godot.Node.GetParent()"] = new[] { Probe+".TryBind(", Probe+".TryChain(", Node+".Matches(" },
        ["member:Godot.Control.get_ClipContents()"] = new[] { Probe+".TryBind(", Probe+".Matches(", Node+".TryBind(", Node+".Matches(" },
        ["member:Godot.Control.GetGlobalRect()"] = new[] { Probe+".TryRect(", Node+".TryBind(", Node+".Matches(" },
        ["member:Godot.CanvasItem.GetCanvas()"] = new[] { Probe+".TryBind(", Node+".TryBind(", Node+".Matches(" },
        ["member:Godot.CanvasItem.GetGlobalTransform()"] = new[] { Node+".TryBind(", Node+".Matches(" },
        ["member:Godot.CanvasItem.IsSetAsTopLevel()"] = new[] { Node+".TryBind(", Node+".Matches(" },
        ["member:Godot.Rid.get_IsValid()"] = new[] { Probe+".TryBind(" },
    };
    internal static IEnumerable<string> GeometryApis => Readers.Keys;
    internal static bool Forbidden(string owner,string target) =>
        Readers.TryGetValue(target,out var owners) && !owners.Any(prefix=>owner.StartsWith(prefix,StringComparison.Ordinal));
    internal static void AddCall(string owner,string target,int offset,ushort opcode,List<string> inventory)
    {
        if(!Readers.ContainsKey(target))return;
        if(Forbidden(owner,target))throw new VerificationException("offscreen_surface_forbidden");
        inventory.Add("offscreen_api|"+owner+"|"+offset.ToString(CultureInfo.InvariantCulture)+"|"+
            opcode.ToString(CultureInfo.InvariantCulture)+"|"+target);
    }
    internal static void Verify(string[] inventory)
    {
        var seen=new HashSet<string>(StringComparer.Ordinal);
        foreach(string row in inventory.Where(x=>x.StartsWith("offscreen_api|",StringComparison.Ordinal)))
        {
            string[] fields=row.Split('|');
            if(fields.Length!=5 || !int.TryParse(fields[2],NumberStyles.None,CultureInfo.InvariantCulture,out int offset) || offset<0 ||
                fields[3] is not "40" and not "111" || !Readers.ContainsKey(fields[4]) || Forbidden(fields[1],fields[4]))
                throw new VerificationException("offscreen_surface_forbidden");
            seen.Add(fields[4]);
        }
        if(!seen.SetEquals(Readers.Keys))throw new VerificationException("offscreen_surface_forbidden");
    }
}
