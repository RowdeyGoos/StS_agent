using System;
using System.Collections.Generic;
using System.Globalization;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicCombatDecisionReader : IPublicCombatDecisionReader
{
    private const int MaximumEnemies = 6;
    private const int MaximumHandCards = 10;
    private const int MaximumIntentsPerEnemy = 8;
    private const int MaximumLegalActions = 64;

    private bool _observedCombatInProgress;
    private PublicCombatDecisionSnapshot? _terminalSnapshot;

    public PublicCombatDecisionSnapshot Read()
    {
        CombatManager? manager = CombatManager.Instance;
        if (_terminalSnapshot.HasValue)
        {
            if (manager is null || !manager.IsInProgress || manager.IsOverOrEnding)
            {
                return _terminalSnapshot.Value;
            }

            _terminalSnapshot = null;
            _observedCombatInProgress = false;
        }

        if (manager is null)
        {
            return PublicCombatDecisionSnapshot.Waiting();
        }

        var combat = manager.DebugOnlyGetState();
        if (combat is null)
        {
            return PublicCombatDecisionSnapshot.Waiting();
        }

        if (combat.Players.Count != 1)
        {
            return PublicCombatDecisionSnapshot.Unsupported();
        }

        var player = combat.Players[0];
        var playerCombat = player?.PlayerCombatState;
        if (player is null || playerCombat is null)
        {
            return PublicCombatDecisionSnapshot.Unsupported();
        }

        var enemyModels = new List<PublicCombatEnemy>();
        var enemyCreatures = new List<Creature>();
        foreach (Creature creature in combat.Enemies)
        {
            if (!creature.IsAlive)
            {
                continue;
            }

            if (enemyModels.Count >= MaximumEnemies)
            {
                return PublicCombatDecisionSnapshot.Unsupported();
            }

            var intents = new List<string>();
            if (creature.Monster?.NextMove is MoveState move)
            {
                foreach (var intent in move.Intents)
                {
                    if (intents.Count >= MaximumIntentsPerEnemy)
                    {
                        return PublicCombatDecisionSnapshot.Unsupported();
                    }

                    intents.Add(intent.IntentType.ToString().ToLowerInvariant());
                }
            }

            int index = enemyModels.Count;
            enemyCreatures.Add(creature);
            enemyModels.Add(new PublicCombatEnemy(
                index,
                creature.Monster?.Id.Entry ?? "unknown",
                creature.CurrentHp,
                creature.MaxHp,
                creature.Block,
                intents));
        }

        if (manager.IsInProgress)
        {
            _observedCombatInProgress = true;
        }

        if (_observedCombatInProgress && manager.IsOverOrEnding && combat.RoundNumber >= 1)
        {
            PublicCombatOutcome outcome = !player.Creature.IsAlive
                ? PublicCombatOutcome.Defeat
                : enemyModels.Count == 0
                    ? PublicCombatOutcome.Victory
                    : PublicCombatOutcome.None;
            if (outcome != PublicCombatOutcome.None)
            {
                _terminalSnapshot = PublicCombatDecisionSnapshot.Complete(
                    combat.RoundNumber,
                    new PublicCombatPlayer(
                        player.Creature.CurrentHp,
                        player.Creature.MaxHp,
                        player.Creature.Block,
                        playerCombat.Energy),
                    enemyModels,
                    outcome);
                return _terminalSnapshot.Value;
            }
        }

        if (!manager.IsInProgress ||
            manager.PlayerActionsDisabled ||
            NOverlayStack.Instance?.ScreenCount > 0 ||
            combat.CurrentSide != CombatSide.Player ||
            playerCombat.Phase != PlayerTurnPhase.Play)
        {
            return PublicCombatDecisionSnapshot.Waiting();
        }

        var hand = new List<PublicCombatCard>();
        var legalActions = new List<PublicDecisionAction>();
        foreach (CardModel card in playerCombat.Hand.Cards)
        {
            if (hand.Count >= MaximumHandCards)
            {
                return PublicCombatDecisionSnapshot.Unsupported();
            }

            card.CanPlay(out UnplayableReason reason, out _);
            bool playable = reason == UnplayableReason.None;
            int handIndex = hand.Count;
            hand.Add(new PublicCombatCard(
                handIndex,
                card.Id.Entry,
                card.Type.ToString().ToLowerInvariant(),
                card.EnergyCost.CostsX
                    ? "X"
                    : card.EnergyCost.GetAmountToSpend().ToString(CultureInfo.InvariantCulture),
                card.TargetType.ToString().ToLowerInvariant(),
                playable));

            if (!playable)
            {
                continue;
            }

            if (card.TargetType == TargetType.AnyEnemy)
            {
                for (int enemyIndex = 0; enemyIndex < enemyCreatures.Count; enemyIndex++)
                {
                    bool isHittable = false;
                    foreach (Creature hittableEnemy in combat.HittableEnemies)
                    {
                        if (ReferenceEquals(hittableEnemy, enemyCreatures[enemyIndex]))
                        {
                            isHittable = true;
                            break;
                        }
                    }

                    if (isHittable)
                    {
                        legalActions.Add(new PublicDecisionAction(
                            PublicDecisionActionKind.PlayCard,
                            handIndex,
                            enemyIndex));
                    }
                }
            }
            else
            {
                legalActions.Add(new PublicDecisionAction(
                    PublicDecisionActionKind.PlayCard,
                    handIndex,
                    -1));
            }

            if (legalActions.Count >= MaximumLegalActions)
            {
                return PublicCombatDecisionSnapshot.Unsupported();
            }
        }

        legalActions.Add(new PublicDecisionAction(PublicDecisionActionKind.EndTurn, -1, -1));
        if (legalActions.Count > MaximumLegalActions)
        {
            return PublicCombatDecisionSnapshot.Unsupported();
        }

        var snapshot = new PublicCombatDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            combat.RoundNumber,
            new PublicCombatPlayer(
                player.Creature.CurrentHp,
                player.Creature.MaxHp,
                player.Creature.Block,
                playerCombat.Energy),
            enemyModels,
            hand,
            legalActions,
            PublicCombatOutcome.None);
        return snapshot with
        {
            DecisionId = PublicCombatDecisionIdentity.Compute(snapshot),
        };
    }

}
