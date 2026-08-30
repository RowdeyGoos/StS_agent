using System;
using System.Collections.Generic;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicCombatActionApplier : IPublicCombatActionApplier
{
    private readonly IPublicCombatDecisionReader _reader;
    private readonly object _gate = new();
    private readonly HashSet<string> _acceptedDecisionIds = new(StringComparer.Ordinal);

    public PinnedPublicCombatActionApplier(IPublicCombatDecisionReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
    }

    public PublicCombatActionApplyResult Apply(PublicCombatActionRequest request)
    {
        PublicCombatActionApplyOutcome? initialFailure = ReservationFailure(request.DecisionId);
        if (initialFailure.HasValue)
        {
            return Result(initialFailure.Value, request);
        }

        PublicCombatDecisionSnapshot snapshot = _reader.Read();
        if (snapshot.Status != PublicDecisionStatus.Ready ||
            !string.Equals(snapshot.DecisionId, request.DecisionId, StringComparison.Ordinal))
        {
            return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
        }

        bool advertised = false;
        foreach (PublicDecisionAction action in snapshot.LegalActions)
        {
            if (request.IsEndTurn
                    ? action.Kind == PublicDecisionActionKind.EndTurn
                    : action.Kind == PublicDecisionActionKind.PlayCard &&
                      action.HandIndex == request.HandIndex &&
                      action.TargetIndex == request.TargetIndex)
            {
                advertised = true;
                break;
            }
        }
        if (!advertised)
        {
            return Result(PublicCombatActionApplyOutcome.InvalidAction, request);
        }

        CombatManager? manager = CombatManager.Instance;
        if (manager is null || !manager.IsInProgress || manager.PlayerActionsDisabled)
        {
            return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
        }

        var combat = manager.DebugOnlyGetState();
        if (combat is null || combat.Players.Count != 1)
        {
            return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
        }

        var player = combat.Players[0];
        var playerCombat = player?.PlayerCombatState;
        if (player is null || playerCombat is null || !player.Creature.IsAlive ||
            combat.CurrentSide != CombatSide.Player ||
            playerCombat.Phase != PlayerTurnPhase.Play)
        {
            return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
        }

        if (request.IsEndTurn)
        {
            if (manager.IsPlayerReadyToEndTurn(player))
            {
                return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
            }

            PublicCombatActionApplyOutcome? reservationFailure = Reserve(request.DecisionId);
            if (reservationFailure.HasValue)
            {
                return Result(reservationFailure.Value, request);
            }

            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(
                new EndPlayerTurnAction(player, playerCombat.TurnNumber));
            return Result(PublicCombatActionApplyOutcome.Accepted, request);
        }

        if (request.HandIndex < 0 || request.HandIndex >= playerCombat.Hand.Cards.Count)
        {
            return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
        }

        CardModel card = playerCombat.Hand.Cards[request.HandIndex];
        if (!card.CanPlay(out UnplayableReason reason, out _) || reason != UnplayableReason.None)
        {
            return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
        }

        Creature? target = null;
        if (card.TargetType == TargetType.AnyEnemy)
        {
            var aliveEnemies = new List<Creature>();
            foreach (Creature enemy in combat.Enemies)
            {
                if (enemy.IsAlive)
                {
                    aliveEnemies.Add(enemy);
                }
            }

            if (request.TargetIndex < 0 || request.TargetIndex >= aliveEnemies.Count)
            {
                return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
            }

            target = aliveEnemies[request.TargetIndex];
            bool hittable = false;
            foreach (Creature candidate in combat.HittableEnemies)
            {
                if (ReferenceEquals(candidate, target))
                {
                    hittable = true;
                    break;
                }
            }
            if (!hittable)
            {
                return Result(PublicCombatActionApplyOutcome.StaleDecision, request);
            }
        }
        else if (request.TargetIndex >= 0)
        {
            return Result(PublicCombatActionApplyOutcome.InvalidAction, request);
        }

        PublicCombatActionApplyOutcome? playReservationFailure = Reserve(request.DecisionId);
        if (playReservationFailure.HasValue)
        {
            return Result(playReservationFailure.Value, request);
        }

        RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(
            new PlayCardAction(card, target));
        return Result(PublicCombatActionApplyOutcome.Accepted, request);
    }

    private PublicCombatActionApplyOutcome? ReservationFailure(string decisionId)
    {
        lock (_gate)
        {
            if (_acceptedDecisionIds.Contains(decisionId))
            {
                return PublicCombatActionApplyOutcome.AlreadyApplied;
            }
            if (_acceptedDecisionIds.Count >= PublicCombatActionBudget.MaximumAcceptedActions)
            {
                return PublicCombatActionApplyOutcome.ActionLimitReached;
            }
            return null;
        }
    }

    private PublicCombatActionApplyOutcome? Reserve(string decisionId)
    {
        lock (_gate)
        {
            if (_acceptedDecisionIds.Contains(decisionId))
            {
                return PublicCombatActionApplyOutcome.AlreadyApplied;
            }
            if (_acceptedDecisionIds.Count >= PublicCombatActionBudget.MaximumAcceptedActions)
            {
                return PublicCombatActionApplyOutcome.ActionLimitReached;
            }
            _acceptedDecisionIds.Add(decisionId);
            return null;
        }
    }

    private static PublicCombatActionApplyResult Result(
        PublicCombatActionApplyOutcome outcome,
        PublicCombatActionRequest request)
    {
        return PublicCombatActionApplyResult.FromRequest(outcome, request);
    }
}
