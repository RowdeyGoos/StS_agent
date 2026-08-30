using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Core.Public;

public static class PublicRoomLimits
{
    public const int MaximumCandidates = 8;
    public const int MaximumStableIdLength = 96;
}

public enum PublicRoomCandidateKind
{
    RestHeal = 1,
    RestUnsupported = 2,
    EventOption = 3,
    Proceed = 4,
}

public readonly record struct PublicRoomCandidate(
    int CandidateIndex,
    string ActionId,
    PublicRoomCandidateKind Kind,
    string StableId,
    bool Enabled,
    bool Supported,
    bool IsProceed,
    bool IsDangerous);

public readonly record struct PublicRoomDecisionSnapshot(
    PublicDecisionStatus Status,
    string DecisionId,
    string ScreenKind,
    string Phase,
    int RoomOrdinal,
    IReadOnlyList<PublicRoomCandidate> Candidates,
    IReadOnlyList<string> LegalActions)
{
    public static PublicRoomDecisionSnapshot Waiting() => new(
        PublicDecisionStatus.Waiting,
        string.Empty,
        "unknown",
        "unknown",
        -1,
        Array.Empty<PublicRoomCandidate>(),
        Array.Empty<string>());

    public static PublicRoomDecisionSnapshot Unsupported(
        string screenKind = "unknown",
        int roomOrdinal = -1) => new(
        PublicDecisionStatus.Unsupported,
        string.Empty,
        screenKind,
        "unsupported",
        roomOrdinal,
        Array.Empty<PublicRoomCandidate>(),
        Array.Empty<string>());

    public static PublicRoomDecisionSnapshot Complete(
        string screenKind,
        int roomOrdinal) => new(
        PublicDecisionStatus.Complete,
        string.Empty,
        screenKind,
        "complete",
        roomOrdinal,
        Array.Empty<PublicRoomCandidate>(),
        Array.Empty<string>());
}

public static class PublicRoomDecisionIdentity
{
    public const int EncodedCharacterCount = 64;

    public static string Compute(PublicRoomDecisionSnapshot snapshot)
    {
        if (snapshot.Status != PublicDecisionStatus.Ready)
        {
            throw new ArgumentException("Only a ready room decision has an identity.", nameof(snapshot));
        }

        var builder = new StringBuilder(512);
        Append(builder, snapshot.ScreenKind);
        Append(builder, snapshot.Phase);
        Append(builder, snapshot.RoomOrdinal);
        Append(builder, snapshot.Candidates.Count);
        foreach (PublicRoomCandidate candidate in snapshot.Candidates)
        {
            Append(builder, candidate.CandidateIndex);
            Append(builder, candidate.ActionId);
            Append(builder, (int)candidate.Kind);
            Append(builder, candidate.StableId);
            Append(builder, candidate.Enabled ? 1 : 0);
            Append(builder, candidate.Supported ? 1 : 0);
            Append(builder, candidate.IsProceed ? 1 : 0);
            Append(builder, candidate.IsDangerous ? 1 : 0);
        }

        Append(builder, snapshot.LegalActions.Count);
        foreach (string action in snapshot.LegalActions)
        {
            Append(builder, action);
        }

        byte[] content = Encoding.UTF8.GetBytes(builder.ToString());
        byte[] digest = SHA256.HashData(content);
        return Convert.ToHexString(digest).ToLowerInvariant();
    }

    public static bool IsCanonical(string value)
    {
        if (value is null || value.Length != EncodedCharacterCount)
        {
            return false;
        }

        foreach (char item in value)
        {
            if (!((item >= '0' && item <= '9') || (item >= 'a' && item <= 'f')))
            {
                return false;
            }
        }
        return true;
    }

    public static bool IsBoundedPublicId(string value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > PublicRoomLimits.MaximumStableIdLength)
        {
            return false;
        }

        foreach (char item in value)
        {
            if (item < 0x20 || item > 0x7e)
            {
                return false;
            }
        }
        return true;
    }

    private static void Append(StringBuilder builder, int value)
    {
        builder.Append(value.ToString(CultureInfo.InvariantCulture));
        builder.Append(';');
    }

    private static void Append(StringBuilder builder, string value)
    {
        builder.Append(value.Length.ToString(CultureInfo.InvariantCulture));
        builder.Append(':');
        builder.Append(value);
        builder.Append(';');
    }
}

public interface IPublicRoomDecisionReader
{
    PublicRoomDecisionSnapshot Read();
}

public interface IPublicRoomDecisionService
{
    PublicRoomDecisionReadResult Read();
}

public enum PublicRoomDecisionReadOutcome
{
    Success = 1,
    BackendFault = 2,
}

public readonly record struct PublicRoomDecisionReadResult
{
    private PublicRoomDecisionReadResult(
        PublicRoomDecisionReadOutcome outcome,
        PublicRoomDecisionSnapshot snapshot)
    {
        Outcome = outcome;
        Snapshot = snapshot;
    }

    public PublicRoomDecisionReadOutcome Outcome { get; }

    public PublicRoomDecisionSnapshot Snapshot { get; }

    public bool IsSuccess => Outcome == PublicRoomDecisionReadOutcome.Success;

    public static PublicRoomDecisionReadResult FromSnapshot(PublicRoomDecisionSnapshot snapshot) =>
        new(PublicRoomDecisionReadOutcome.Success, snapshot);

    public static PublicRoomDecisionReadResult BackendFault() =>
        new(PublicRoomDecisionReadOutcome.BackendFault, default);
}

public sealed class PublicRoomDecisionService : IPublicRoomDecisionService
{
    private readonly IPublicRoomDecisionReader _reader;

    public PublicRoomDecisionService(IPublicRoomDecisionReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
    }

    public PublicRoomDecisionReadResult Read()
    {
        try
        {
            return PublicRoomDecisionReadResult.FromSnapshot(_reader.Read());
        }
        catch (Exception)
        {
            return PublicRoomDecisionReadResult.BackendFault();
        }
    }
}
