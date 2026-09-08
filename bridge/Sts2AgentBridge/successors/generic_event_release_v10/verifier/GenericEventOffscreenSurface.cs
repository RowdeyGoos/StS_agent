using System;
using System.Collections.Generic;
using System.Linq;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV10;

// The direct-slot test has no geometry certificate. Former geometry APIs are
// forbidden from every caller, including the earlier certificate helper names.
internal static class GenericEventOffscreenSurface
{
    private static readonly HashSet<string> Readers = new(StringComparer.Ordinal)
    {
        "member:Godot.Node.GetParent()",
        "member:Godot.Control.get_ClipContents()",
        "member:Godot.Control.GetGlobalRect()",
        "member:Godot.CanvasItem.GetCanvas()",
        "member:Godot.CanvasItem.GetGlobalTransform()",
        "member:Godot.CanvasItem.IsSetAsTopLevel()",
        "member:Godot.Rid.get_IsValid()",
    };
    internal static IEnumerable<string> GeometryApis => Readers;
    internal static bool Forbidden(string owner, string target) => Readers.Contains(target);
    internal static void AddCall(string owner, string target, int offset, ushort opcode, List<string> inventory)
    {
        if (Forbidden(owner, target)) throw new VerificationException("offscreen_surface_forbidden");
    }
    internal static void Verify(string[] inventory)
    {
        if (inventory.Any(row => row.StartsWith("offscreen_api|", StringComparison.Ordinal)))
            throw new VerificationException("offscreen_surface_forbidden");
    }
}
