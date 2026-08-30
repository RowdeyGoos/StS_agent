using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Core.Public;

public enum PublicDecisionStatus
{
    Ready = 1,
    Waiting = 2,
    Unsupported = 3,
    Complete = 4,
}

public enum PublicCombatOutcome
{
    None = 0,
    Victory = 1,
    Defeat = 2,
}

public enum PublicDecisionActionKind
{
    PlayCard = 1,
    EndTurn = 2,
}

public readonly record struct PublicCombatPlayer(
    int Hp,
    int MaxHp,
    int Block,
    int Energy);

public readonly record struct PublicCombatEnemy(
    int Index,
    string Id,
    int Hp,
    int MaxHp,
    int Block,
    IReadOnlyList<string> Intents);

public readonly record struct PublicCombatCard(
    int HandIndex,
    string Id,
    string Type,
    string Cost,
    string TargetType,
    bool Playable);

public readonly record struct PublicDecisionAction(
    PublicDecisionActionKind Kind,
    int HandIndex,
    int TargetIndex);

public readonly record struct PublicCombatDecisionSnapshot(
    PublicDecisionStatus Status,
    string DecisionId,
    int Round,
    PublicCombatPlayer Player,
    IReadOnlyList<PublicCombatEnemy> Enemies,
    IReadOnlyList<PublicCombatCard> Hand,
    IReadOnlyList<PublicDecisionAction> LegalActions,
    PublicCombatOutcome Outcome)
{
    public static PublicCombatDecisionSnapshot Waiting() => new(
        PublicDecisionStatus.Waiting,
        string.Empty,
        0,
        default,
        Array.Empty<PublicCombatEnemy>(),
        Array.Empty<PublicCombatCard>(),
        Array.Empty<PublicDecisionAction>(),
        PublicCombatOutcome.None);

    public static PublicCombatDecisionSnapshot Unsupported() => new(
        PublicDecisionStatus.Unsupported,
        string.Empty,
        0,
        default,
        Array.Empty<PublicCombatEnemy>(),
        Array.Empty<PublicCombatCard>(),
        Array.Empty<PublicDecisionAction>(),
        PublicCombatOutcome.None);

    public static PublicCombatDecisionSnapshot Complete(
        int round,
        PublicCombatPlayer player,
        IReadOnlyList<PublicCombatEnemy> enemies,
        PublicCombatOutcome outcome) => new(
            PublicDecisionStatus.Complete,
            string.Empty,
            round,
            player,
            enemies,
            Array.Empty<PublicCombatCard>(),
            Array.Empty<PublicDecisionAction>(),
            outcome);
}

public static class PublicCombatDecisionIdentity
{
    public const int EncodedCharacterCount = 64;

    public static string Compute(PublicCombatDecisionSnapshot snapshot)
    {
        if (snapshot.Status != PublicDecisionStatus.Ready)
        {
            throw new ArgumentException("Only a ready decision has an identity.", nameof(snapshot));
        }

        var builder = new StringBuilder(1024);
        Append(builder, snapshot.Round);
        Append(builder, snapshot.Player.Hp);
        Append(builder, snapshot.Player.MaxHp);
        Append(builder, snapshot.Player.Block);
        Append(builder, snapshot.Player.Energy);
        Append(builder, snapshot.Enemies.Count);
        foreach (PublicCombatEnemy enemy in snapshot.Enemies)
        {
            Append(builder, enemy.Index);
            Append(builder, enemy.Id);
            Append(builder, enemy.Hp);
            Append(builder, enemy.MaxHp);
            Append(builder, enemy.Block);
            Append(builder, enemy.Intents.Count);
            foreach (string intent in enemy.Intents)
            {
                Append(builder, intent);
            }
        }

        Append(builder, snapshot.Hand.Count);
        foreach (PublicCombatCard card in snapshot.Hand)
        {
            Append(builder, card.HandIndex);
            Append(builder, card.Id);
            Append(builder, card.Type);
            Append(builder, card.Cost);
            Append(builder, card.TargetType);
            Append(builder, card.Playable ? 1 : 0);
        }

        Append(builder, snapshot.LegalActions.Count);
        foreach (PublicDecisionAction action in snapshot.LegalActions)
        {
            Append(builder, (int)action.Kind);
            Append(builder, action.HandIndex);
            Append(builder, action.TargetIndex);
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

public interface IPublicCombatDecisionReader
{
    PublicCombatDecisionSnapshot Read();
}

public interface IPublicCombatDecisionService
{
    PublicCombatDecisionReadResult Read();
}

public enum PublicCombatDecisionReadOutcome
{
    Success = 1,
    BackendFault = 2,
}

public readonly record struct PublicCombatDecisionReadResult
{
    private PublicCombatDecisionReadResult(
        PublicCombatDecisionReadOutcome outcome,
        PublicCombatDecisionSnapshot snapshot)
    {
        Outcome = outcome;
        Snapshot = snapshot;
    }

    public PublicCombatDecisionReadOutcome Outcome { get; }

    public PublicCombatDecisionSnapshot Snapshot { get; }

    public bool IsSuccess => Outcome == PublicCombatDecisionReadOutcome.Success;

    public static PublicCombatDecisionReadResult FromSnapshot(PublicCombatDecisionSnapshot snapshot) =>
        new(PublicCombatDecisionReadOutcome.Success, snapshot);

    public static PublicCombatDecisionReadResult BackendFault() =>
        new(PublicCombatDecisionReadOutcome.BackendFault, default);
}

public sealed class PublicCombatDecisionService : IPublicCombatDecisionService
{
    private readonly IPublicCombatDecisionReader _reader;

    public PublicCombatDecisionService(IPublicCombatDecisionReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
    }

    public PublicCombatDecisionReadResult Read()
    {
        try
        {
            return PublicCombatDecisionReadResult.FromSnapshot(_reader.Read());
        }
        catch (Exception)
        {
            return PublicCombatDecisionReadResult.BackendFault();
        }
    }
}
