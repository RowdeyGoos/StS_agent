using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

namespace Sts2AgentBridge.Adapters.Public;

internal interface IPinnedClosingOverlay
{
    bool EffectCertified { get; }
    bool ClosingOwnerValid { get; }
    PinnedOverlayPrefix Ancestors { get; }
    IReadOnlyList<Control> ClosingScreens { get; }
}

// Ancestors are supplied by the enclosing native owner, never adopted from an
// already-open screen. Both their order and identity remain part of authority.
internal sealed class PinnedOverlayPrefix
{
    private readonly NOverlayStack _stack;
    private readonly Control[] _ancestors;
    private static readonly FieldInfo Entries = typeof(NOverlayStack).GetField("_overlays", BindingFlags.Instance | BindingFlags.NonPublic)!;
    internal int Depth => _ancestors.Length;
    internal PinnedOverlayPrefix(NOverlayStack stack, IReadOnlyList<Control>? ancestors = null)
    {
        _stack = stack; _ancestors = ancestors?.ToArray() ?? Array.Empty<Control>();
        if (Entries is null || _ancestors.Length > 4 ||
            _ancestors.Distinct(ReferenceEqualityComparer.Instance).Count() != _ancestors.Length ||
            _ancestors.Any(a => a is null || !GodotObject.IsInstanceValid(a)))
            throw new InvalidOperationException("overlay_ancestor_boundary");
    }
    private object[] Current()
    {
        if (!GodotObject.IsInstanceValid(_stack) || Entries.GetValue(_stack) is not IList entries || entries.Count != _stack.ScreenCount || entries.Count > 6)
            throw new InvalidOperationException("overlay_stack_boundary");
        return entries.Cast<object>().ToArray();
    }
    internal bool Bare => Matches(Array.Empty<Control>());
    internal bool MatchesClosing(Control screen, IReadOnlyList<IPinnedClosingOverlay> descendants)
    {
        var expected = ClosingPath(new[] { screen }, descendants);
        if (expected is null) return false;
        var current = Current();
        return expected.Count == current.Length && expected.Select((value,i) => GodotObject.IsInstanceValid(value) && ReferenceEquals(value, current[i])).All(v => v);
    }
    private List<Control>? ClosingPath(IReadOnlyList<Control> screens, IReadOnlyList<IPinnedClosingOverlay> descendants)
    {
        var expected = _ancestors.Concat(screens).ToList();
        if (screens.Count is < 1 or > 2 || descendants.Count > 4) return null;
        foreach (var child in descendants)
        {
            if (!child.EffectCertified || !child.ClosingOwnerValid || child.ClosingScreens.Count is < 1 or > 2 ||
                child.Ancestors._ancestors.Length != expected.Count ||
                !child.Ancestors._ancestors.Select((ancestor,i) => ReferenceEquals(ancestor, expected[i])).All(v => v)) return null;
            expected.AddRange(child.ClosingScreens);
        }
        return expected.Distinct(ReferenceEqualityComparer.Instance).Count() == expected.Count ? expected : null;
    }
    internal bool Retiring(Control screen, IReadOnlyList<IPinnedClosingOverlay> descendants)
        => Retiring(new[] { screen }, descendants);
    internal bool Retiring(IReadOnlyList<Control> screens, IReadOnlyList<IPinnedClosingOverlay> descendants)
    {
        var path = ClosingPath(screens, descendants);
        return path is not null && RetainedSubsequence(Current(), path);
    }
    private static bool RetainedSubsequence(object[] current, IReadOnlyList<Control> path)
    {
        int index = 0;
        foreach (var value in current)
        {
            while (index < path.Count && !ReferenceEquals(value, path[index])) index++;
            if (index == path.Count || !GodotObject.IsInstanceValid(path[index])) return false;
            index++;
        }
        return true;
    }
    internal bool Matches(params Control[] descendants)
    {
        var current = Current();
        return current.Length == Depth + descendants.Length &&
            _ancestors.Concat(descendants).Select((screen, i) =>
                GodotObject.IsInstanceValid(screen) && ReferenceEquals(current[i], screen)).All(v => v);
    }
    // Certified frames can retire out of order. Remaining controls must still
    // be an ordered subset of the exact owned ancestors; no input uses this rule.
    internal bool Closed(Control screen)
    {
        var current = Current();
        return current.Length <= Depth && !current.Any(c => ReferenceEquals(c, screen)) && RetainedSubsequence(current, _ancestors);
    }
}
