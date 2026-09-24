using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicCombatDecisionReader : IPublicCombatDecisionReader, IDisposable
{
    private const int MaximumEnemies = 6;
    private const int MaximumHandCards = 10;
    private const int MaximumIntentsPerEnemy = 8;
    private const int MaximumLegalActions = 64;

    private bool _observedCombatInProgress;
    private PublicCombatDecisionSnapshot? _terminalSnapshot;
    private PendingAction? _pending;
    private bool _disposed, _failed;

    // Public HP/energy/hand changes can precede an asynchronous card selector.
    // Keep the exact queued action until its execution (not just its receipt)
    // finishes, while the existing choice service owns any nested input.
    private sealed class PendingAction : IDisposable
    {
        private static readonly FieldInfo ExecutionTask = typeof(GameAction).GetField(
            "_executionTask", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException("Combat execution task unavailable.");
        internal readonly GameAction Action;
        internal readonly CombatState Combat;
        private readonly CardModel? _card;
        private readonly CardPile _playPile;
        private readonly int _turn;
        private bool _started, _cancelled, _enteredPlay, _wrongTurn;

        internal PendingAction(GameAction action, CardModel? card, CombatState combat)
        {
            Action = action; Combat = combat; _card = card;
            var state = combat.Players[0].PlayerCombatState!;
            _playPile = state.PlayPile; _turn = state.TurnNumber;
            action.BeforeExecuted += Started;
            action.BeforeCancelled += Cancelled;
            _playPile.CardAdded += EnteredPlay;
        }
        private void Started(GameAction _) {
            _started = true;
            _wrongTurn = Combat.Players[0].PlayerCombatState?.TurnNumber != _turn;
        }
        private void Cancelled(GameAction _) => _cancelled = true;
        private void EnteredPlay(CardModel card) { if (ReferenceEquals(card, _card)) _enteredPlay = true; }
        internal bool IsPending(CombatManager manager)
        {
            if (_cancelled || _wrongTurn || Action.Exception is not null ||
                !ReferenceEquals(manager.DebugOnlyGetState(), Combat))
                throw new InvalidOperationException("Owned combat action failed.");
            if (!Action.CompletionTask.IsCompleted) return true;
            // GameAction's completion source succeeds even when its internal
            // execution task faults or is cancelled. Inspect both pinned tasks.
            if (!_started || !Action.CompletionTask.IsCompletedSuccessfully ||
                ExecutionTask.GetValue(Action) is not Task { IsCompletedSuccessfully: true } ||
                _card is not null && !_enteredPlay)
                throw new InvalidOperationException("Owned combat action did not complete.");
            // EndPlayerTurnAction only starts the turn transition; its task can
            // finish before the old player phase has left the screen.
            return _card is null && !manager.IsOverOrEnding &&
                Combat.Players[0].PlayerCombatState!.TurnNumber <= _turn;
        }
        public void Dispose()
        {
            Action.BeforeExecuted -= Started;
            Action.BeforeCancelled -= Cancelled;
            _playPile.CardAdded -= EnteredPlay;
        }
    }

    internal void TrackAction(GameAction action, CardModel? card, CombatState combat)
    {
        if (_disposed || _failed || _pending is not null)
            throw new InvalidOperationException("Combat action already owned.");
        _pending = new PendingAction(action, card, combat);
    }
    // Returning to an already observed native object must retain its identity:
    // BeginObservedCombat and waiting periods cannot make an old action reusable.
    private readonly ConditionalWeakTable<object, string> _combatScopes = new();

    // Called only after the unified event transfer certifies an in-progress
    // exact combat. Do not reuse a prior encounter's terminal observation.
    public void BeginObservedCombat() {_terminalSnapshot=null;_observedCombatInProgress=true;}

    public PublicCombatDecisionSnapshot Read()
    {
        if (_disposed || _failed) throw new InvalidOperationException("Combat reader stopped.");
        CombatManager? manager = CombatManager.Instance;
        if (_pending is not null)
        {
            try
            {
                if (manager is null) throw new InvalidOperationException("Owned combat disappeared.");
                if (_pending.IsPending(manager)) return PublicCombatDecisionSnapshot.Waiting();
                _pending.Dispose(); _pending = null;
            }
            catch { _failed = true; throw; }
        }
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
        if (player.Creature.HpDisplay is not (HpDisplay.Normal or HpDisplay.InfiniteWithNumbers))
            return PublicCombatDecisionSnapshot.Unsupported();

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
            if (creature.HpDisplay is not (HpDisplay.Normal or HpDisplay.InfiniteWithNumbers or HpDisplay.InfiniteWithoutNumbers))
                return PublicCombatDecisionSnapshot.Unsupported();
            bool infinite = creature.HpDisplay == HpDisplay.InfiniteWithoutNumbers;

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
                infinite ? 0 : creature.CurrentHp,
                infinite ? 0 : creature.MaxHp,
                creature.Block,
                intents,
                infinite ? PublicEnemyHealthDisplay.Infinite : PublicEnemyHealthDisplay.Numeric));
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
            DecisionId = PublicCombatDecisionIdentity.Compute(snapshot,
                _combatScopes.GetValue(combat, _ => Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant())),
        };
    }

    public void Dispose()
    {
        bool unresolved = _pending is not null || _failed;
        _failed |= unresolved;
        _pending?.Dispose(); _pending = null; _disposed = true;
        if (unresolved) throw new InvalidOperationException("Unreconciled combat action on disposal.");
    }

}
