using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.RoomFlowsV1;

internal static partial class Program
{
    private static CardModel AddCard(Player player, bool removable = true, bool clone = false, bool egg = false)
    {
        CardModel card = egg ? new ByrdonisEgg() : new CardModel();
        card.Owner = player; card.RunState = player.RunState; card.IsRemovable = removable;
        if (clone) card.Enchantment = new MegaCrit.Sts2.Core.Models.Enchantments.Clone { Card = card };
        player.Deck.Cards.Add(card); return card;
    }
    private static void Extended()
    {
        foreach (var action in new[] { "dig", "cook:0:2", "clone", "hatch" })
        {
            using var f = new Fixture(action);
            var before = f.Read().Options.Single(o => o.ActionId == Sts2AgentBridge.Rooms.Rest.RestV2Session.Kind(action));
            f.Begin(); Check(f.Read().Status == "waiting", "full action awaits room continuation: " + action);
            f.Room.Completion.SetResult(); var done = f.Read();
            Check(done.Status == "complete" && done.Result!.ActionId == action && done.Result.After == before.Counter + Sts2AgentBridge.Rooms.Rest.RestV2Session.Delta(action, before.Amount), "full rest effect: " + action);
            var deck = f.Room.Characters[0].Player.Deck.Cards;
            if (action.StartsWith("cook")) Check(deck.Count == 1 && !deck[0].IsRemovable, "exact cook originals removed");
            if (action == "hatch") Check(deck.Count(c => c is ByrdSwoop) == 2 && !deck.Any(c => c is ByrdonisEgg), "all eggs transformed");
        }
        using (var f = new Fixture("clone"))
        {
            f.Begin(); var player = f.Room.Characters[0].Player; player.RunState = new();
            foreach (var card in player.Deck.Cards) card.RunState = player.RunState;
            Check(f.Read().Status == "unsupported", "replaced run state stops pending effect");
        }
        using (var f = new Fixture("hatch"))
        {
            var duplicate = new HatchRestSiteOption(f.Room.Characters[0].Player);
            f.Room.Options.Add(duplicate); f.Room.Buttons.Add(duplicate, new() { Option = duplicate });
            Check(f.Read().Options.Count == 1, "equivalent Hatch options share one public action");
            f.Begin(); f.Room.Completion.SetResult(); Check(f.Read().Status == "complete", "multiple eggs can expose duplicate native options");
        }
        using (var f = new Fixture("clone"))
        {
            CardPileCmd.UpgradeAdded = true;
            try { f.Begin(); f.Room.Completion.SetResult(); Check(f.Read().Status == "complete", "native add modifiers admitted"); }
            finally { CardPileCmd.UpgradeAdded = false; }
        }
        using (var f = new Fixture("clone"))
        {
            f.Room.Characters[0].Player.Deck.Cards.Clear(); f.Begin(); f.Room.Completion.SetResult();
            Check(f.Read().Status == "complete", "zero clone targets");
        }
        using (var f = new Fixture("cook:0:2"))
        {
            f.Room.Completion.SetResult(); f.Begin(); Check(f.Read().Status == "complete", "synchronous selection completion recaptures foreground");
        }
        using (var f = new Fixture("cook:0:2"))
        {
            var ready = f.Read(); f.Room.Characters[0].Player.Deck.Cards[0].CurrentUpgradeLevel++;
            Check(f.Session.Apply(ready.DecisionId, f.Action) is RoomFlowApplyFailure { Outcome: "rejected" } && f.Button.Clicks == 0, "cook stale card rejected");
        }
        using (var f = new Fixture("cook:0:2"))
        {
            var ready = f.Read(); Check(f.Session.Apply(ready.DecisionId, "cook:0:1") is RoomFlowApplyFailure && f.Button.Clicks == 0, "unremovable cook target rejected");
        }
        using (var f = new Fixture("cook:0:2"))
        {
            f.Begin(); ((NDeckCardSelectScreen)f.Run.GlobalUi.Overlays.Top!).WrongSelection = true;
            Check(f.Read().Status is "waiting" or "unsupported", "wrong selector result cannot complete");
            Check(f.Read().Status == "unsupported", "wrong selector result stops");
        }
        using (var f = new Fixture("clone"))
        {
            f.Begin(); f.Room.Characters[0].Player.Deck.Cards[^1] = new CardModel { Owner = f.Room.Characters[0].Player, RunState = f.Room.Characters[0].Player.RunState };
            f.Room.Completion.SetResult(); Check(f.Read().Status == "unsupported", "unattributed clone replacement");
        }
        using (var f = new Fixture("hatch"))
        {
            f.Begin(); f.Room.Characters[0].Player.Deck.Cards[0] = new CardModel { Owner = f.Room.Characters[0].Player, RunState = f.Room.Characters[0].Player.RunState };
            f.Room.Completion.SetResult(); Check(f.Read().Status == "unsupported", "wrong hatch transform");
        }
        foreach (bool delayed in new[] { false, true })
        {
            using var f = new Fixture("dig");
            var relic = new SelectorRelic(delayed);
            ((DigRestSiteOption)f.Button.Option).Drawn = relic;
            AddCard(f.Room.Characters[0].Player); AddCard(f.Room.Characters[0].Player);
            f.Begin();
            if (delayed) relic.Gate.SetResult();
            Check(f.Read().Status == "waiting", "owned pickup selector progresses");
            f.Room.Completion.SetResult(); Check(f.Read().Status == "complete" && relic.Selected == 1, "dig scoped async pickup selector");
        }
    }
    private sealed class SelectorRelic(bool delayed) : RelicModel
    {
        public readonly TaskCompletionSource Gate = new();
        public int Selected;
        public override async Task AfterObtained()
        {
            if (delayed) await Gate.Task;
            var cards = await CardSelectCmd.Select(Owner!.Deck.Cards.ToArray(), 1);
            Selected = cards.Count();
        }
    }
    private static void InteractiveRestCases()
    {
        foreach (string action in new[] { "smith", "cook" })
        {
            using (var f = new Fixture(action, interactive: true))
            {
                var ready = f.Native.Capture().Options.Single(o => o.Public.ActionId == action);
                MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance.Blocker = new();
                bool rejected = false; try { f.Native.Begin(ready, action); } catch (InvalidOperationException) { rejected = true; }
                Check(rejected && f.Button.Clicks == 0, "foreground change rejects rest parent input");
            }
            using (var f = new Fixture(action, interactive: true))
            {
                f.Native.Begin(f.Native.Capture().Options.Single(o => o.Public.ActionId == action), action); f.Native.ReadChoice();
                MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance.Blocker = new();
                bool rejected = false; try { f.Native.ApplyChoice("cancel"); } catch (InvalidOperationException) { rejected = true; }
                Check(rejected && f.Run.GlobalUi.Overlays.ScreenCount == 1 && f.Execution?.IsCompleted == false, "foreground change rejects child input");
            }
            foreach (string stage in new[] { "before_choice", "cancel_not_restored", "successful_finish" })
            {
                using var f = new Fixture(action, interactive: true) { HoldRestore = stage == "cancel_not_restored" };
                f.Native.Begin(f.Native.Capture().Options.Single(o => o.Public.ActionId == action), action); f.Native.ReadChoice();
                if (stage != "before_choice")
                {
                    f.Native.ApplyChoice("cancel"); var progress = f.Native.Poll();
                    if (stage == "successful_finish") { Check(progress.Succeeded, "cancellation completed before Finish"); f.Native.Finish(); }
                }
                for (int attempt = 0; attempt < 2; attempt++)
                {
                    bool failed = false;
                    try { f.Native.Dispose(); } catch (InvalidOperationException) { failed = true; }
                    Check(failed == (stage != "successful_finish"), "only settled rest disposal succeeds; sticky otherwise: " + stage);
                }
            }
            using (var f = new Fixture(action, interactive: true))
            {
                var before = f.Native.Capture(); var selected = before.Options.Single(o => o.Public.ActionId == action);
                f.Native.Begin(selected, action); var choices = f.Native.ReadChoice()!;
                Check(choices.Selected.Length == 0 && choices.Cancelable, "interactive rest waits for policy");
                var chosen = action == "cook" ? choices.Domain : choices.Domain.Take(1).ToArray();
                foreach (var card in chosen) { f.Native.ReadChoice(); f.Native.ApplyChoice("select", card); }
                Check(!f.Native.Poll().Succeeded, "selection alone does not complete option");
                f.Native.ReadChoice(); f.Native.ApplyChoice("confirm");
                Check(!f.Native.Poll().Succeeded, "native result waits for rest continuation");
                f.Room.Completion.SetResult(); var result = f.Native.Poll();
                Check(result.Succeeded && !result.Cancelled && result.Counter == selected.Public.Counter + (action == "cook" ? 9 : 1), "interactive effect and exact task complete");
                f.Native.Finish();
            }
            foreach (bool partial in new[] { false, true })
            {
                using var f = new Fixture(action, interactive: true) { HoldRestore = true };
                var before = new Sts2AgentBridge.Rooms.Rest.RestNativeState(f.Room.Characters[0].Player);
                var selected = f.Native.Capture().Options.Single(o => o.Public.ActionId == action);
                f.Native.Begin(selected, action); var choice = f.Native.ReadChoice()!;
                if (partial) { f.Native.ApplyChoice("select", choice.Domain[0]); f.Native.ReadChoice(); }
                f.Native.ApplyChoice("cancel");
                var waiting = f.Native.Poll(); Check(!waiting.Succeeded && waiting.Cancelled, "cancel waits for options to be restored");
                f.Button.IsEnabled = true; var result = f.Native.Poll();
                Check(result.Succeeded && result.Cancelled && result.Counter == selected.Public.Counter, "cancel reports unchanged counter");
                Check(before.Equals(new Sts2AgentBridge.Rooms.Rest.RestNativeState(f.Room.Characters[0].Player)), "cancel preserves public inventory and vitals");
                f.Native.Finish();
            }
            foreach (string fault in new[] { "deck", "gold", "owner", "foreign_completion", "replaced_button", "unrequested_cancel", "faulted_task" })
            {
                using var f = new Fixture(action, interactive: true);
                var player = f.Room.Characters[0].Player;
                f.Native.Begin(f.Native.Capture().Options.Single(o => o.Public.ActionId == action), action); f.Native.ReadChoice();
                var screen = (NDeckCardSelectScreen)f.Run.GlobalUi.Overlays.Top!;
                if (fault == "unrequested_cancel") screen.Selected.SetResult(Array.Empty<CardModel>());
                else if (fault == "faulted_task") screen.Selected.SetException(new InvalidOperationException("fixture"));
                else f.Native.ApplyChoice("cancel");
                if (fault == "deck") player.Deck.Cards[0].CurrentUpgradeLevel++;
                if (fault == "gold") player.Gold++;
                if (fault == "owner") player.Deck.Cards[0].Owner = new();
                if (fault == "foreign_completion") f.Room.Continue(f.Button.Option);
                if (fault == "replaced_button") f.Room.Buttons[f.Button.Option] = new() { Option = f.Button.Option };
                bool rejected = false;
                try { f.Native.Poll(); } catch (InvalidOperationException) { rejected = true; }
                Check(rejected, "cancellation rejects wrong result or context: " + action + "/" + fault);
            }
        }
    }

}
