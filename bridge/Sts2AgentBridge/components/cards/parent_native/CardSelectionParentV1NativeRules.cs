using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.CardSelectionV1.ParentNative;

internal static class CardSelectionParentV1NativeRules
{
    internal const int MaximumStructuralEntries = 64;

    internal static string StructuralWitness(
        string policy,
        string phase,
        IReadOnlyList<StructuralEntry> entries)
    {
        ArgumentNullException.ThrowIfNull(policy);
        ArgumentNullException.ThrowIfNull(phase);
        ArgumentNullException.ThrowIfNull(entries);
        if (!AsciiToken(policy, 64) || !AsciiToken(phase, 32) ||
            entries.Count > MaximumStructuralEntries)
            throw new InvalidOperationException("Invalid structural witness input.");
        using var stream = new MemoryStream();
        Append(stream, policy);
        Append(stream, phase);
        WriteInt(stream, entries.Count);
        foreach (StructuralEntry entry in entries)
        {
            if (!AsciiToken(entry.StableKey, 128) || !AsciiToken(entry.TypeName, 256))
                throw new InvalidOperationException("Invalid structural entry.");
            Append(stream, entry.StableKey);
            Append(stream, entry.TypeName);
            stream.WriteByte(entry.Visible ? (byte)1 : (byte)0);
            stream.WriteByte(entry.Enabled ? (byte)1 : (byte)0);
            stream.WriteByte(entry.Locked ? (byte)1 : (byte)0);
            stream.WriteByte(entry.Proceed ? (byte)1 : (byte)0);
        }
        return Convert.ToHexString(SHA256.HashData(stream.ToArray())).ToLowerInvariant();
    }

    internal static bool SameReferences(IReadOnlyList<object> left, IReadOnlyList<object> right)
    {
        if (left.Count != right.Count) return false;
        for (int i = 0; i < left.Count; i++)
            if (!ReferenceEquals(left[i], right[i])) return false;
        return true;
    }

    internal static bool ValidSmithDomainCount(int value) => value is >= 1 and <= 64;

    private static bool AsciiToken(string value, int maximum)
    {
        if (value.Length is 0 || value.Length > maximum) return false;
        foreach (char c in value)
            if (c < 0x21 || c > 0x7e) return false;
        return true;
    }

    private static void Append(Stream stream, string value)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(value);
        WriteInt(stream, bytes.Length);
        stream.Write(bytes, 0, bytes.Length);
    }

    private static void WriteInt(Stream stream, int value)
    {
        stream.WriteByte((byte)(value >> 24));
        stream.WriteByte((byte)(value >> 16));
        stream.WriteByte((byte)(value >> 8));
        stream.WriteByte((byte)value);
    }
}

internal readonly record struct StructuralEntry(
    string StableKey,
    string TypeName,
    bool Visible,
    bool Enabled,
    bool Locked,
    bool Proceed);
