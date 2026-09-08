using System;
using System.Linq;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Cards.Combat;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

internal static class Program
{
    private static int _checks;
    private static void Check(bool value, string label) { _checks++; if (!value) throw new Exception(label); }
    private static JsonElement Read(ChoiceReply reply) { using var json = JsonDocument.Parse(reply.Body); return json.RootElement.Clone(); }
    private static string Status(ChoiceReply reply) => Read(reply).GetProperty("status").GetString()!;
    private static void Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--wire")
        {
            var fixture = new Fixture(min: 0, max: 2, count: 3, manual: true);
            while (Console.ReadLine() is string line)
            {
                using var input = JsonDocument.Parse(line); var request = input.RootElement;
                var reply = request.GetProperty("method").GetString() == "GET" ? fixture.Service.Read() :
                    fixture.Service.Apply(request.GetProperty("decision_id").GetString()!, request.GetProperty("action_id").GetString()!);
                Console.WriteLine(Encoding.UTF8.GetString(reply.Body));
            }
            fixture.Service.Dispose(); return;
        }
        OptionalAndMultiple(); BindingFailures(); DispatchAndCompletionFailures();
        Console.WriteLine("{\"status\":\"passed\",\"suite\":\"combat_choice_native\",\"checks\":" + _checks + "}");
    }
    private static void OptionalAndMultiple()
    {
        var zero = new Fixture(); zero.Act("confirm");
        var empty = Read(zero.Service.Read());
        Check(empty.GetProperty("status").GetString() == "complete" && empty.GetProperty("selected_slots").GetArrayLength() == 0, "native optional zero completion");
        Check(!zero.Service.IsActive && zero.Confirm.Calls == 1 && zero.Holders.Sum(h => h.Calls) == 0, "zero is one confirm and releases ownership");
        Check(Status(zero.Service.Read()) == "waiting", "completed selector never adopted again");
        for (int count = 1; count <= 8; count++)
        {
            var fixedCount = new Fixture(count, count, count + 1, false);
            for (int i = 0; i < count; i++) { fixedCount.Act("select:" + i); if (i < count - 1) fixedCount.Ready(); }
            var done = Read(fixedCount.Service.Read());
            Check(done.GetProperty("status").GetString() == "complete" && done.GetProperty("reconciled").GetInt32() == count, "auto count " + count);
        }
        var variable = new Fixture(1, 3, 4, true); variable.Act("select:0"); variable.Ready(); variable.Act("confirm");
        Check(Status(variable.Service.Read()) == "complete", "positive early confirm");
        var toggle = new Fixture(0, 2, 3, true); toggle.Act("select:0"); toggle.Ready(); toggle.Act("deselect:0"); toggle.Ready();
        toggle.Act("select:2"); toggle.Ready(); toggle.Act("confirm");
        var result = Read(toggle.Service.Read());
        Check(result.GetProperty("selected_slots")[0].GetInt32() == 2 && result.GetProperty("reconciled").GetInt32() == 4, "deselection verified before reselection");
        var optional = new Fixture(); optional.Act("select:0");
        Check(Status(optional.Service.Read()) == "complete", "Neow-style optional one auto completion");
        var clamped = new Fixture(2, 3, 1, true); clamped.Act("select:0"); clamped.Ready(); clamped.Act("confirm");
        Check(Status(clamped.Service.Read()) == "complete", "native min/max clamp to displayed domain");
    }
    private static void BindingFailures()
    {
        foreach (var mutation in new Action<Fixture>[] {
            f => f.Run.GlobalUi.MapScreen.IsOpen = true,
            f => NRun.Instance = new NRun(),
            f => f.Run.GlobalUi.Overlays.Top = new object(),
            f => f.Grid.CurrentlyDisplayedCardHolders.Reverse(),
            f => f.Holders[0].CardModel = f.Models[1],
            f => f.Holders[0].CardNode = new NCard { Model = f.Models[0] },
            f => f.Models[0].Owner = new Player(),
            f => f.Models[0].CurrentUpgradeLevel++,
            f => CardSelectCmd.Selector = new object(),
            f => f.Screen.Selected.Add(f.Models[1]) })
        {
            var fixture = new Fixture(); string decision = fixture.Ready().GetProperty("decision_id").GetString()!;
            mutation(fixture);
            Check(fixture.Service.Apply(decision, "select:0").Terminal, "changed binding fails closed");
            Check(fixture.Holders.Sum(h => h.Calls) == 0 && fixture.Confirm.Calls == 0, "changed binding no input");
        }
        var hidden = new Fixture(pile: PileType.Draw);
        var failure = hidden.Service.Read();
        Check(failure.Terminal && !Encoding.UTF8.GetString(failure.Body).Contains("STRIKE"), "draw order never projected");
        var disabled = new Fixture(); disabled.Holders[0].Hitbox.IsEnabled = false;
        Check(!disabled.Ready().GetProperty("legal_actions").EnumerateArray().Any(a => a.GetString() == "select:0"), "disabled target not offered");
        var unclickable = new Fixture(); unclickable.Holders[0].SetClickable(false);
        Check(!unclickable.Ready().GetProperty("legal_actions").EnumerateArray().Any(a => a.GetString() == "select:0"), "native unclickable target not offered");
        var minimum = new Fixture(1, 2, 3, true);
        Check(!minimum.Ready().GetProperty("legal_actions").EnumerateArray().Any(a => a.GetString() == "confirm"), "no invented zero confirmation");
    }
    private static void DispatchAndCompletionFailures()
    {
        var deferred = new Fixture(0, 2, 3, true) { Defer = true };
        deferred.Act("select:0"); Check(Status(deferred.Service.Read()) == "waiting", "deferred selection not reconciled early");
        deferred.Pending!(); deferred.Pending = null;
        Check(deferred.Ready().GetProperty("reconciled").GetInt32() == 1, "deferred exact selection reconciles");
        var delayed = new Fixture { DelayCompletion = true };
        delayed.Act("select:0");
        var waiting = Read(delayed.Service.Read());
        Check(waiting.GetProperty("status").GetString() == "waiting" && waiting.GetProperty("reconciled").GetInt32() == 0,
            "auto maximum waits for native completion after visible selection");
        delayed.Pending!();
        Check(Status(delayed.Service.Read()) == "complete", "delayed auto completion reconciles once");
        var lost = new Fixture { Throw = true }; var d = lost.Ready().GetProperty("decision_id").GetString()!;
        Check(lost.Service.Apply(d, "select:0").Terminal, "uncertain dispatch terminal");
        Check(lost.Service.Apply(d, "select:0").Terminal && lost.Holders[0].Calls == 1, "uncertain mutation never retried");
        var duplicate = new Fixture(0, 2, 3, true); var id = duplicate.Ready().GetProperty("decision_id").GetString()!;
        Check(Status(duplicate.Service.Apply(id, "select:0")) == "accepted", "first input accepted");
        Check(duplicate.Service.Apply(id, "select:0").Terminal && duplicate.Holders[0].Calls == 1, "pending duplicate rejected");
        var wrong = new Fixture { WrongResult = true }; wrong.Act("select:0");
        Check(wrong.Service.Read().Terminal, "wrong native task result rejected");
        var cancel = new Fixture(); cancel.Ready(); cancel.Screen.Cancel(); cancel.Run.GlobalUi.Overlays.Top = null;
        Check(cancel.Service.Read().Terminal, "external cancellation is not optional zero confirmation");
        var stuck = new Fixture(0, 2, 3, true) { Defer = true }; stuck.Act("select:0");
        ChoiceReply last = default;
        for (int i = 0; i < 201; i++) last = stuck.Service.Read();
        Check(last.Terminal && stuck.Holders[0].Calls == 1, "bounded reconciliation without retry");
    }
    private sealed class Fixture
    {
        internal NRun Run = new(); internal NCombatPileCardSelectScreen Screen = new();
        internal NCardGrid Grid = new(); internal NConfirmButton Confirm = new();
        internal CardModel[] Models; internal NGridCardHolder[] Holders; internal CombatCardChoiceService Service;
        internal bool Defer, Throw, WrongResult, DelayCompletion; internal Action? Pending;
        internal Fixture(int min = 0, int max = 1, int count = 3, bool manual = false, PileType pile = PileType.Discard)
        {
            NRun.Instance = Run; NOverlayStack.Instance = Run.GlobalUi.Overlays; Run.GlobalUi.Overlays.Top = Screen;
            var player = new Player(); var cards = new CardPile { Type = pile };
            player.Piles[pile] = cards; CombatManager.Instance = new(); CombatManager.Instance.State.Players.Add(player);
            CardSelectCmd.Selector = null;
            Models = Enumerable.Range(0, count).Select(i => new CardModel { Owner = player, Id = new ModelId { Entry = "STRIKE_" + i } }).ToArray();
            cards.Cards.AddRange(Models);
            Screen.Init(cards, new CardSelectorPrefs { MinSelect = min, MaxSelect = max, RequireManualConfirmation = manual });
            Screen.Nodes["%CardGrid"] = Grid; Screen.Nodes["%Confirm"] = Confirm;
            void Complete() { Screen.Result(WrongResult ? new[] { new CardModel() } : Screen.Selected.ToArray()); Run.GlobalUi.Overlays.Top = null; }
            Confirm.Click = Complete; Confirm.IsEnabled = min == 0;
            Holders = Models.Select(model => new NGridCardHolder { CardModel = model, CardNode = new NCard { Model = model } }).ToArray();
            foreach (var holder in Holders)
                holder.Click = () => {
                    void Select() {
                        if (!Screen.Selected.Remove(holder.CardModel)) Screen.Selected.Add(holder.CardModel);
                        if (!manual && Screen.Selected.Count == Math.Min(max, count))
                        { if (DelayCompletion) Pending = Complete; else Complete(); }
                        Confirm.IsEnabled = manual && Screen.Selected.Count >= Math.Min(min, count);
                    }
                    if (Defer) Pending = Select; else Select();
                    if (Throw) throw new Exception("native failure details must not escape");
                };
            Grid.CurrentlyDisplayedCardHolders.AddRange(Holders);
            Service = new CombatCardChoiceService(PinnedCombatCardChoiceAdapter.TryCreate, new string('a', 32));
        }
        internal JsonElement Ready() { var value = Read(Service.Read()); Check(value.GetProperty("status").GetString() == "ready", "ready selector"); return value; }
        internal void Act(string action) {
            var ready = Ready(); Check(ready.GetProperty("legal_actions").EnumerateArray().Any(a => a.GetString() == action), "advertised " + action);
            Check(Status(Service.Apply(ready.GetProperty("decision_id").GetString()!, action)) == "accepted", "accepted " + action);
        }
    }
}
