using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1;

public static class EventOrchestratorV1CanonicalEncoder
{
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    public static string ActionIdFor(int index) =>
        "choose:" + index.ToString(CultureInfo.InvariantCulture);

    public static string ComputeDecisionId(
        string nonce,
        string phase,
        IReadOnlyList<EventOrchestratorV1Candidate> candidates,
        IReadOnlyList<string> legalActions)
    {
        using var stream = new MemoryStream();
        WriteString(stream, EventOrchestratorV1Limits.Version);
        WriteString(stream, nonce);
        WriteString(stream, phase);
        WriteInt(stream, candidates.Count);
        foreach (EventOrchestratorV1Candidate candidate in candidates)
        {
            WriteInt(stream, candidate.CandidateIndex);
            WriteString(stream, candidate.ActionId);
            WriteString(stream, candidate.StableId);
            WriteString(stream, candidate.RenderedText);
            stream.WriteByte(candidate.Enabled ? (byte)1 : (byte)0);
            stream.WriteByte(candidate.IsDangerous ? (byte)1 : (byte)0);
            stream.WriteByte(candidate.IsProceed ? (byte)1 : (byte)0);
            WriteString(stream, candidate.ChildPolicy);
        }
        WriteInt(stream, legalActions.Count);
        foreach (string action in legalActions) WriteString(stream, action);
        return Hash(stream);
    }

    internal static string ComputeStructuralId(
        string nonce,
        string phase,
        IReadOnlyList<EventOrchestratorV1Candidate> candidates)
    {
        using var stream = new MemoryStream();
        WriteString(stream, EventOrchestratorV1Limits.Version);
        WriteString(stream, nonce);
        WriteString(stream, phase);
        WriteInt(stream, candidates.Count);
        foreach (EventOrchestratorV1Candidate candidate in candidates)
        {
            WriteInt(stream, candidate.CandidateIndex);
            WriteString(stream, candidate.ActionId);
            WriteString(stream, candidate.StableId);
            stream.WriteByte(candidate.Enabled ? (byte)1 : (byte)0);
            stream.WriteByte(candidate.IsDangerous ? (byte)1 : (byte)0);
            stream.WriteByte(candidate.IsProceed ? (byte)1 : (byte)0);
            WriteString(stream, candidate.ChildPolicy);
        }
        return Hash(stream);
    }

    private static string Hash(MemoryStream stream) =>
        Convert.ToHexString(SHA256.HashData(stream.ToArray())).ToLowerInvariant();

    private static void WriteString(Stream stream, string value)
    {
        byte[] bytes = StrictUtf8.GetBytes(value);
        WriteInt(stream, bytes.Length);
        stream.Write(bytes, 0, bytes.Length);
        Array.Clear(bytes);
    }

    private static void WriteInt(Stream stream, int value)
    {
        stream.WriteByte((byte)((uint)value >> 24));
        stream.WriteByte((byte)((uint)value >> 16));
        stream.WriteByte((byte)((uint)value >> 8));
        stream.WriteByte((byte)value);
    }
}
