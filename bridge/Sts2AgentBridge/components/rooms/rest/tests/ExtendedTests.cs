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
}
