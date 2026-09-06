using System;
using System.Collections.Generic;
using System.Text.Json;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Native.Tests;

internal static class Program
{
    private static int _checks;

    private static int Main(string[] args)
    {
        if (args.Length != 0) return 2;
        try
        {
            ExactRuntimeTypes();
            HighlightEndpoints();
            HighlightIntermediateValues();
            StableKeys();
            CheeseGeometry();
            CheesePolicy();
            SmithPolicy();
            Console.WriteLine(JsonSerializer.Serialize(new SortedDictionary<string, object>
            {
                ["check_count"] = _checks,
                ["schema_version"] = 1,
                ["status"] = "passed",
                ["suite"] = "card_selection_v1_native",
            }));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error.GetType().Name + ":" + error.Message);
            return 1;
        }
    }

    private static void ExactRuntimeTypes()
    {
        var exact = new BaseWitness();
        True(CardSelectionV1NativeRules.IsExactRuntimeType(exact, typeof(BaseWitness)));
        False(CardSelectionV1NativeRules.IsExactRuntimeType(new DerivedWitness(), typeof(BaseWitness)));
        False(CardSelectionV1NativeRules.IsExactRuntimeType(null, typeof(BaseWitness)));
    }

    private static void HighlightEndpoints()
    {
        Equal(CardSelectionV1HighlightEndpoint.Unselected,
            CardSelectionV1NativeRules.ClassifyHighlight(0f));
        Equal(CardSelectionV1HighlightEndpoint.Selected,
            CardSelectionV1NativeRules.ClassifyHighlight(
                BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits)));
    }

    private static void HighlightIntermediateValues()
    {
        Equal(CardSelectionV1HighlightEndpoint.Transient,
            CardSelectionV1NativeRules.ClassifyHighlight(0.01f));
        Equal(CardSelectionV1HighlightEndpoint.Transient,
            CardSelectionV1NativeRules.ClassifyHighlight(-0f));
        Equal(CardSelectionV1HighlightEndpoint.Transient,
            CardSelectionV1NativeRules.ClassifyHighlight(float.NaN));
    }

    private static void StableKeys()
    {
        True(CardSelectionV1NativeRules.IsStableKey("BASH_2"));
        False(CardSelectionV1NativeRules.IsStableKey(""));
        False(CardSelectionV1NativeRules.IsStableKey("BASH-2"));
        False(CardSelectionV1NativeRules.IsStableKey(new string('A', 129)));
    }

    private static void CheeseGeometry()
    {
        True(CardSelectionV1NativeRules.TryCheeseGeometry(
            920f, 1060f, 0f, 900f, 200f, 300f, 20, out int columns, out int rows));
        Equal(4, columns);
        Equal(2, rows);
        True(CardSelectionV1NativeRules.TryCheeseGeometry(
            920f, 1060f, 70f, 1200f, 200f, 300f, 20, out _, out _));
        False(CardSelectionV1NativeRules.TryCheeseGeometry(
            920f, 1059f, 0f, 900f, 200f, 300f, 20, out _, out _));
        False(CardSelectionV1NativeRules.TryCheeseGeometry(
            920f, 1060f, 0f, 700f, 200f, 300f, 20, out _, out _));
        False(CardSelectionV1NativeRules.TryCheeseGeometry(
            0f, 1060f, 0f, 900f, 200f, 300f, 20, out _, out _));
        False(CardSelectionV1NativeRules.TryCheeseGeometry(
            920f, 1060f, 0f, 900f, 200f, 300f, -1, out _, out _));
    }

    private static void CheesePolicy()
    {
        True(CardSelectionV1NativeRules.IsCheesePolicy(Context(
            CardSelectionV1ParentKind.Event, CardSelectionV1Operation.Add,
            2, 2, CardSelectionV1CommitMode.AutoAtMax, 8)));
        False(CardSelectionV1NativeRules.IsCheesePolicy(Context(
            CardSelectionV1ParentKind.Event, CardSelectionV1Operation.Add,
            1, 2, CardSelectionV1CommitMode.AutoAtMax, 8)));
        False(CardSelectionV1NativeRules.IsCheesePolicy(Context(
            CardSelectionV1ParentKind.Event, CardSelectionV1Operation.Add,
            2, 2, CardSelectionV1CommitMode.AutoAtMax, 7)));
    }

    private static void SmithPolicy()
    {
        False(CardSelectionV1NativeRules.IsSmithPolicy(Context(
            CardSelectionV1ParentKind.Rest, CardSelectionV1Operation.Upgrade,
            1, 1, CardSelectionV1CommitMode.PreviewConfirm, 0)));
        True(CardSelectionV1NativeRules.IsSmithPolicy(Context(
            CardSelectionV1ParentKind.Rest, CardSelectionV1Operation.Upgrade,
            1, 1, CardSelectionV1CommitMode.PreviewConfirm, 64)));
        False(CardSelectionV1NativeRules.IsSmithPolicy(Context(
            CardSelectionV1ParentKind.Rest, CardSelectionV1Operation.Upgrade,
            1, 2, CardSelectionV1CommitMode.PreviewConfirm, 2)));
        False(CardSelectionV1NativeRules.IsSmithPolicy(Context(
            CardSelectionV1ParentKind.Event, CardSelectionV1Operation.Upgrade,
            1, 1, CardSelectionV1CommitMode.PreviewConfirm, 1)));
        False(CardSelectionV1NativeRules.IsSmithPolicy(Context(
            CardSelectionV1ParentKind.Rest, CardSelectionV1Operation.Upgrade,
            1, 1, CardSelectionV1CommitMode.PreviewConfirm, 65)));
    }

    private static CardSelectionV1ParentContext Context(
        CardSelectionV1ParentKind parentKind,
        CardSelectionV1Operation operation,
        int min,
        int max,
        CardSelectionV1CommitMode mode,
        int domain) => new(
            new string('a', 64), parentKind, "parent-decision", "choice:0",
            new object(), new object(), new object(), new object(), new object(),
            new object(), new object(), operation, min, max, mode, domain);

    private class BaseWitness { }
    private sealed class DerivedWitness : BaseWitness { }

    private static void True(bool value)
    {
        _checks++;
        if (!value) throw new InvalidOperationException("Expected true.");
    }

    private static void False(bool value)
    {
        _checks++;
        if (value) throw new InvalidOperationException("Expected false.");
    }

    private static void Equal<T>(T expected, T actual) where T : notnull
    {
        _checks++;
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException($"Expected {expected}; got {actual}.");
    }
}
