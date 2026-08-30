using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Core.Public;

public readonly record struct PublicMapCandidate(
    int CandidateIndex,
    int Col,
    int Row,
    string Kind);

public readonly record struct PublicMapDecisionSnapshot(
    PublicDecisionStatus Status,
    string DecisionId,
    string ScreenKind,
    PublicMapCandidate? Destination,
    IReadOnlyList<PublicMapCandidate> Candidates,
    IReadOnlyList<string> LegalActions)
{
    public static PublicMapDecisionSnapshot Waiting() => new(
        PublicDecisionStatus.Waiting,
        string.Empty,
        "unknown",
        null,
        Array.Empty<PublicMapCandidate>(),
        Array.Empty<string>());

    public static PublicMapDecisionSnapshot Unsupported() => new(
        PublicDecisionStatus.Unsupported,
        string.Empty,
        "unknown",
        null,
        Array.Empty<PublicMapCandidate>(),
        Array.Empty<string>());

    public static PublicMapDecisionSnapshot Complete(PublicMapCandidate destination) => new(
        PublicDecisionStatus.Complete,
        string.Empty,
        "room",
        destination,
        Array.Empty<PublicMapCandidate>(),
        Array.Empty<string>());
}

public static class PublicMapDecisionIdentity
{
    public const int EncodedCharacterCount = 64;

    public static string Compute(PublicMapDecisionSnapshot snapshot)
    {
        if (snapshot.Status != PublicDecisionStatus.Ready)
        {
            throw new ArgumentException("Only a ready map decision has an identity.", nameof(snapshot));
        }

        var builder = new StringBuilder(256);
        Append(builder, snapshot.ScreenKind);
        Append(builder, snapshot.Candidates.Count);
        foreach (PublicMapCandidate candidate in snapshot.Candidates)
        {
            Append(builder, candidate.CandidateIndex);
            Append(builder, candidate.Col);
            Append(builder, candidate.Row);
            Append(builder, candidate.Kind);
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

public interface IPublicMapDecisionReader
{
    PublicMapDecisionSnapshot Read();
}

public interface IPublicMapDecisionService
{
    PublicMapDecisionReadResult Read();
}

public enum PublicMapDecisionReadOutcome
{
    Success = 1,
    BackendFault = 2,
}

public readonly record struct PublicMapDecisionReadResult
{
    private PublicMapDecisionReadResult(
        PublicMapDecisionReadOutcome outcome,
        PublicMapDecisionSnapshot snapshot)
    {
        Outcome = outcome;
        Snapshot = snapshot;
    }

    public PublicMapDecisionReadOutcome Outcome { get; }

    public PublicMapDecisionSnapshot Snapshot { get; }

    public bool IsSuccess => Outcome == PublicMapDecisionReadOutcome.Success;

    public static PublicMapDecisionReadResult FromSnapshot(PublicMapDecisionSnapshot snapshot) =>
        new(PublicMapDecisionReadOutcome.Success, snapshot);

    public static PublicMapDecisionReadResult BackendFault() =>
        new(PublicMapDecisionReadOutcome.BackendFault, default);
}

public sealed class PublicMapDecisionService : IPublicMapDecisionService
{
    private readonly IPublicMapDecisionReader _reader;

    public PublicMapDecisionService(IPublicMapDecisionReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
    }

    public PublicMapDecisionReadResult Read()
    {
        try
        {
            return PublicMapDecisionReadResult.FromSnapshot(_reader.Read());
        }
        catch (Exception)
        {
            return PublicMapDecisionReadResult.BackendFault();
        }
    }
}
