using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Event;

public static class EventV1CanonicalEncoder
{
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    public static string ComputeDecisionId(
        string sessionNonce,
        string phase,
        IReadOnlyList<EventV1Candidate> candidates,
        IReadOnlyList<string> legalActions)
    {
        using var stream = new MemoryStream();
        WriteString(stream, EventV1Constants.Version);
        WriteString(stream, EventV1Constants.FlowKind);
        WriteString(stream, sessionNonce);
        WriteInt32(stream, RoomFlowLimits.ParentOrdinal);
        WriteString(stream, phase);
        WriteInt32(stream, candidates.Count);
        foreach (EventV1Candidate candidate in candidates)
        {
            WriteInt32(stream, candidate.CandidateIndex);
            WriteString(stream, candidate.ActionId);
            WriteString(stream, candidate.StableId);
            WriteString(stream, candidate.RenderedText);
            stream.WriteByte(candidate.Enabled ? (byte)1 : (byte)0);
            stream.WriteByte(candidate.IsDangerous ? (byte)1 : (byte)0);
            stream.WriteByte(candidate.IsProceed ? (byte)1 : (byte)0);
        }
        WriteInt32(stream, legalActions.Count);
        foreach (string action in legalActions) WriteString(stream, action);
        return Convert.ToHexString(SHA256.HashData(stream.ToArray())).ToLowerInvariant();
    }

    public static string ComputeTransitionId(
        string sessionNonce,
        string phase,
        IReadOnlyList<EventV1Candidate> candidates,
        IReadOnlyList<string> legalActions)
    {
        using var stream = new MemoryStream();
        WriteString(stream, EventV1Constants.Version);
        WriteString(stream, EventV1Constants.FlowKind);
        WriteString(stream, sessionNonce);
        WriteInt32(stream, RoomFlowLimits.ParentOrdinal);
        WriteString(stream, phase);
        WriteInt32(stream, candidates.Count);
        foreach (EventV1Candidate candidate in candidates)
        {
            WriteInt32(stream, candidate.CandidateIndex);
            WriteString(stream, candidate.ActionId);
            WriteString(stream, candidate.StableId);
            stream.WriteByte(candidate.Enabled ? (byte)1 : (byte)0);
            stream.WriteByte(candidate.IsDangerous ? (byte)1 : (byte)0);
            stream.WriteByte(candidate.IsProceed ? (byte)1 : (byte)0);
        }
        WriteInt32(stream, legalActions.Count);
        foreach (string action in legalActions) WriteString(stream, action);
        return Convert.ToHexString(SHA256.HashData(stream.ToArray())).ToLowerInvariant();
    }

    public static string ActionIdFor(int candidateIndex) =>
        "choose:" + candidateIndex.ToString(System.Globalization.CultureInfo.InvariantCulture);

    private static void WriteString(Stream stream, string value)
    {
        byte[] bytes = StrictUtf8.GetBytes(value);
        WriteInt32(stream, bytes.Length);
        stream.Write(bytes, 0, bytes.Length);
    }

    private static void WriteInt32(Stream stream, int value)
    {
        stream.WriteByte((byte)((uint)value >> 24));
        stream.WriteByte((byte)((uint)value >> 16));
        stream.WriteByte((byte)((uint)value >> 8));
        stream.WriteByte((byte)value);
    }
}
