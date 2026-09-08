using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1.ParentNative;

internal static class Program
{
    private static int _checks;

    public static int Main()
    {
        try
        {
            WitnessIsCanonicalAndTextFree();
            WitnessBindsStructuralState();
            ReferenceOrderIsExact();
            SmithDomainIsBounded();
            InvalidInputsFailClosed();
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"card_selection_parent_v1_native\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static void WitnessIsCanonicalAndTextFree()
    {
        StructuralEntry[] entries = { new("GORGE", "EventOption", true, true, false, false) };
        string a = CardSelectionParentV1NativeRules.StructuralWitness("cheese", "initial", entries);
        string b = CardSelectionParentV1NativeRules.StructuralWitness("cheese", "initial", entries);
        Equal(a, b, "stable witness");
        True(a.Length == 64, "witness length");
        foreach (char c in a) True(c is >= '0' and <= '9' or >= 'a' and <= 'f', "lower hex");
        Pass();
    }

    private static void WitnessBindsStructuralState()
    {
        var a = new[] { new StructuralEntry("GORGE", "EventOption", true, true, false, false) };
        var key = new[] { new StructuralEntry("LEAVE", "EventOption", true, true, false, false) };
        var visible = new[] { new StructuralEntry("GORGE", "EventOption", false, true, false, false) };
        string original = CardSelectionParentV1NativeRules.StructuralWitness("cheese", "initial", a);
        NotEqual(original, CardSelectionParentV1NativeRules.StructuralWitness("cheese", "initial", key), "key");
        NotEqual(original, CardSelectionParentV1NativeRules.StructuralWitness("cheese", "initial", visible), "visible");
        NotEqual(original, CardSelectionParentV1NativeRules.StructuralWitness("cheese", "child", a), "phase");
        NotEqual(original, CardSelectionParentV1NativeRules.StructuralWitness("smith", "initial", a), "policy");
        Pass();
    }

    private static void ReferenceOrderIsExact()
    {
        object a = new(), b = new();
        True(CardSelectionParentV1NativeRules.SameReferences(new[] { a, b }, new[] { a, b }), "same");
        False(CardSelectionParentV1NativeRules.SameReferences(new[] { a, b }, new[] { b, a }), "order");
        False(CardSelectionParentV1NativeRules.SameReferences(new[] { a }, new[] { a, b }), "count");
        Pass();
    }

    private static void SmithDomainIsBounded()
    {
        False(CardSelectionParentV1NativeRules.ValidSmithDomainCount(0), "zero");
        True(CardSelectionParentV1NativeRules.ValidSmithDomainCount(1), "one");
        True(CardSelectionParentV1NativeRules.ValidSmithDomainCount(64), "maximum");
        False(CardSelectionParentV1NativeRules.ValidSmithDomainCount(65), "overflow");
        Pass();
    }

    private static void InvalidInputsFailClosed()
    {
        Throws(() => CardSelectionParentV1NativeRules.StructuralWitness("", "initial", Array.Empty<StructuralEntry>()), "empty policy");
        Throws(() => CardSelectionParentV1NativeRules.StructuralWitness("cheese", "", Array.Empty<StructuralEntry>()), "empty phase");
        Throws(() => CardSelectionParentV1NativeRules.StructuralWitness("cheese", "initial",
            new[] { new StructuralEntry("bad key", "EventOption", true, true, false, false) }), "space key");
        var many = new List<StructuralEntry>();
        for (int i = 0; i < 65; i++) many.Add(new StructuralEntry("K", "T", true, true, false, false));
        Throws(() => CardSelectionParentV1NativeRules.StructuralWitness("cheese", "initial", many), "entry cap");
        Pass();
    }

    private static void Pass() => _checks++;
    private static void True(bool value, string name) { if (!value) throw new InvalidOperationException(name); }
    private static void False(bool value, string name) => True(!value, name);
    private static void Equal(string a, string b, string name) => True(a == b, name);
    private static void NotEqual(string a, string b, string name) => True(a != b, name);
    private static void Throws(Action action, string name)
    {
        try { action(); }
        catch (InvalidOperationException) { return; }
        throw new InvalidOperationException(name);
    }
}
