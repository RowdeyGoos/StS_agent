using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Core.Public;

public readonly record struct PublicRewardPlayer(
    int Hp,
    int MaxHp,
    int Gold,
    int DeckCount);

public enum PublicRewardKind
{
    Gold = 1,
    Card = 2,
    Unsupported = 3,
}

public readonly record struct PublicRewardItem(
    int RewardIndex,
    PublicRewardKind Kind,
    bool SuccessfullySelected,
    int GoldAmount,
    IReadOnlyList<string> Cards,
    bool CardSelectionCanSkip);

public readonly record struct PublicRewardDecisionSnapshot(
    PublicDecisionStatus Status,
    string DecisionId,
    string ScreenKind,
    PublicRewardPlayer Player,
    IReadOnlyList<PublicRewardItem> Rewards,
    IReadOnlyList<string> LegalActions,
    int DecisionRevision = 0)
{
    public static PublicRewardDecisionSnapshot Waiting() => new(
        PublicDecisionStatus.Waiting,
        string.Empty,
        "unknown",
        default,
        Array.Empty<PublicRewardItem>(),
        Array.Empty<string>());

    public static PublicRewardDecisionSnapshot Unsupported() => new(
        PublicDecisionStatus.Unsupported,
        string.Empty,
        "unknown",
        default,
        Array.Empty<PublicRewardItem>(),
        Array.Empty<string>());

    public static PublicRewardDecisionSnapshot Complete(
        PublicRewardPlayer player,
        int decisionRevision = 0) => new(
        PublicDecisionStatus.Complete,
        string.Empty,
        "map",
        player,
        Array.Empty<PublicRewardItem>(),
        Array.Empty<string>(),
        decisionRevision);
}

public static class PublicRewardDecisionIdentity
{
    public const int EncodedCharacterCount = 64;

    public static string Compute(PublicRewardDecisionSnapshot snapshot)
    {
        if (snapshot.Status != PublicDecisionStatus.Ready)
        {
            throw new ArgumentException("Only a ready reward decision has an identity.", nameof(snapshot));
        }

        var builder = new StringBuilder(512);
        Append(builder, snapshot.ScreenKind);
        Append(builder, snapshot.DecisionRevision);
        Append(builder, snapshot.Player.Hp);
        Append(builder, snapshot.Player.MaxHp);
        Append(builder, snapshot.Player.Gold);
        Append(builder, snapshot.Player.DeckCount);
        Append(builder, snapshot.Rewards.Count);
        foreach (PublicRewardItem reward in snapshot.Rewards)
        {
            Append(builder, reward.RewardIndex);
            Append(builder, (int)reward.Kind);
            Append(builder, reward.SuccessfullySelected ? 1 : 0);
            Append(builder, reward.GoldAmount);
            Append(builder, reward.CardSelectionCanSkip ? 1 : 0);
            Append(builder, reward.Cards.Count);
            foreach (string card in reward.Cards)
            {
                Append(builder, card);
            }
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

public interface IPublicRewardDecisionReader
{
    PublicRewardDecisionSnapshot Read();
}

public interface IPublicRewardDecisionService
{
    PublicRewardDecisionReadResult Read();
}

public enum PublicRewardDecisionReadOutcome
{
    Success = 1,
    BackendFault = 2,
}

public readonly record struct PublicRewardDecisionReadResult
{
    private PublicRewardDecisionReadResult(
        PublicRewardDecisionReadOutcome outcome,
        PublicRewardDecisionSnapshot snapshot)
    {
        Outcome = outcome;
        Snapshot = snapshot;
    }

    public PublicRewardDecisionReadOutcome Outcome { get; }

    public PublicRewardDecisionSnapshot Snapshot { get; }

    public bool IsSuccess => Outcome == PublicRewardDecisionReadOutcome.Success;

    public static PublicRewardDecisionReadResult FromSnapshot(PublicRewardDecisionSnapshot snapshot) =>
        new(PublicRewardDecisionReadOutcome.Success, snapshot);

    public static PublicRewardDecisionReadResult BackendFault() =>
        new(PublicRewardDecisionReadOutcome.BackendFault, default);
}

public sealed class PublicRewardDecisionService : IPublicRewardDecisionService
{
    private readonly IPublicRewardDecisionReader _reader;

    public PublicRewardDecisionService(IPublicRewardDecisionReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
    }

    public PublicRewardDecisionReadResult Read()
    {
        try
        {
            return PublicRewardDecisionReadResult.FromSnapshot(_reader.Read());
        }
        catch (Exception)
        {
            return PublicRewardDecisionReadResult.BackendFault();
        }
    }
}
