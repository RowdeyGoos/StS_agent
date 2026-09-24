using System;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;

internal static class CombatExecutionFixtures
{
    private sealed class Fixture
    {
        internal readonly CombatState Combat = new();
        internal readonly Player Player = new();
        internal readonly CardModel Card;
        internal readonly CombatManager Manager;
        internal readonly PinnedPublicCombatDecisionReader Reader = new();
        internal readonly PinnedPublicCombatActionApplier Applier;
        internal Fixture(bool endTurn = false)
        {
            NOverlayStack.Instance = null; RunManager.Instance = new();
            RunManager.Instance.ActionQueueSynchronizer.AutoComplete = false;
            Card = new CardModel { Owner = Player, Id = new ModelId { Entry = "NEOWS_FURY" } };
            Player.PlayerCombatState!.Hand.Cards.Add(Card); Combat.Players.Add(Player);
            var enemy = new Creature { CurrentHp = 46, MaxHp = 46 };
            Combat.Enemies.Add(enemy); Combat.HittableEnemies.Add(enemy);
            Manager = new CombatManager { State = Combat }; CombatManager.Instance = Manager;
            Applier = new(Reader);
            PublicCombatActionRequest.TryCreate(Reader.Read().DecisionId, endTurn ? "end_turn" : "play:0:0", out var request);
            if (Applier.Apply(request).Outcome != PublicCombatActionApplyOutcome.Accepted) throw new Exception("fixture dispatch");
        }
        internal GameAction Action => RunManager.Instance.ActionQueueSynchronizer.Actions[0];
        internal void EnterPlay() { Action.Start(); Player.PlayerCombatState!.PlayPile.Add(Card); }
    }

    internal static void Run(Action<bool, string> check)
    {
        var delayed = new Fixture();
        delayed.Combat.Enemies[0].CurrentHp -= 10;
        delayed.Player.PlayerCombatState!.Energy--;
        delayed.Player.PlayerCombatState.Hand.Cards.Clear();
        check(delayed.Reader.Read().Status == PublicDecisionStatus.Waiting, "changed public state cannot reconcile queued action");
        delayed.Reader.BeginObservedCombat();
        check(delayed.Reader.Read().Status == PublicDecisionStatus.Waiting, "begin notification cannot release queued ownership");
        delayed.EnterPlay();
        check(delayed.Reader.Read().Status == PublicDecisionStatus.Waiting, "executing card waits before selector exists");
        NOverlayStack.Instance = new() { Top = new object() };
        check(delayed.Reader.Read().Status == PublicDecisionStatus.Waiting, "parent waits while selector is open");
        NOverlayStack.Instance = null;
        check(delayed.Reader.Read().Status == PublicDecisionStatus.Waiting, "closed selector is not parent completion");
        delayed.Action.Finish();
        check(delayed.Reader.Read().Status == PublicDecisionStatus.Ready, "exact successful execution permits coherent next decision");
        check(RunManager.Instance.ActionQueueSynchronizer.Actions.Count == 1, "delayed stages retain one native dispatch");
        delayed.Reader.Dispose();

        foreach (bool defeat in new[] { false, true })
        {
            var terminal = new Fixture(); terminal.EnterPlay();
            terminal.Manager.IsOverOrEnding = true;
            if (defeat) terminal.Player.Creature.IsAlive = false; else terminal.Combat.Enemies[0].IsAlive = false;
            check(terminal.Reader.Read().Status == PublicDecisionStatus.Waiting, "terminal HP is not execution completion");
            terminal.Action.Finish();
            var done = terminal.Reader.Read();
            check(done.Status == PublicDecisionStatus.Complete && done.Outcome ==
                (defeat ? PublicCombatOutcome.Defeat : PublicCombatOutcome.Victory), "verified execution preserves real terminal outcome");
            terminal.Reader.Dispose();
        }

        foreach (string failure in new[] { "fault", "task_cancel", "action_cancel", "no_play", "no_start", "wrong_turn", "combat_changed" })
        {
            var failed = new Fixture();
            if (failure == "wrong_turn") failed.Player.PlayerCombatState!.TurnNumber++;
            if (failure != "no_start") failed.Action.Start();
            if (failure != "no_play") failed.Player.PlayerCombatState!.PlayPile.Add(failed.Card);
            if (failure == "action_cancel") failed.Action.Cancel();
            failed.Action.Finish(failure);
            if (failure == "combat_changed") failed.Manager.State = new();
            var service = new PublicCombatDecisionService(failed.Reader);
            check(!service.Read().IsSuccess, "failed exact execution cannot reconcile: " + failure);
            failed.Reader.BeginObservedCombat();
            check(!service.Read().IsSuccess, "failed ownership is sticky: " + failure);
            bool rejected = false; try { failed.Reader.Dispose(); } catch (InvalidOperationException) { rejected = true; }
            check(rejected, "failed action disposal cannot report clean completion: " + failure);
        }

        var ending = new Fixture(endTurn: true); ending.Action.Start(); ending.Action.Finish();
        ending.Player.Creature.Block = 9;
        check(ending.Reader.Read().Status == PublicDecisionStatus.Waiting, "end-turn task success waits for actual turn advancement");
        ending.Player.PlayerCombatState!.TurnNumber++; ending.Combat.CurrentSide = CombatSide.Enemy;
        check(ending.Reader.Read().Status == PublicDecisionStatus.Waiting, "end-turn still requires coherent player readiness");
        ending.Combat.CurrentSide = CombatSide.Player;
        check(ending.Reader.Read().Status == PublicDecisionStatus.Ready, "new player turn releases end-turn ownership");
        ending.Reader.Dispose();

        var pending = new Fixture();
        bool stopped = false; try { pending.Reader.Dispose(); } catch (InvalidOperationException) { stopped = true; }
        check(stopped, "queued action disposal fails closed");
        stopped = false; try { pending.Reader.Dispose(); } catch (InvalidOperationException) { stopped = true; }
        check(stopped, "repeated disposal cannot clean an unresolved action");
        CombatManager.Instance = null; NOverlayStack.Instance = null;
    }
}
