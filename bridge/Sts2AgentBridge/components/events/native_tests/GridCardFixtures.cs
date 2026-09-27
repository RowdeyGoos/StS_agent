using System;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;

internal static partial class Program
{
    private sealed class GridEventFixture : IDisposable
    {
        internal readonly Fixture Event;
        internal InteractiveChoiceFixture Surface = null!;
        internal GenericEventV7Observation Parent = null!;
        internal bool RejectCleanup;
        internal GridEventFixture(int count, bool enchant = true, bool full = true, bool delayed = false)
        {
            Event = new Fixture("GRID_EVENT", domain: count, enchant: enchant, effectDelayed: delayed);
            Event.Model.Id.Entry = "GRID_EVENT";
            // Keep the 128-card endpoint inside the declared full-run deck bound.
            if (count == 128) Event.Player.Deck.Cards.Remove(Event.Cards[^1]);
            foreach (var card in Event.Cards) card.Owner = Event.Player;
            while (Event.Player.Deck.Cards.Count < 105)
            { var c = new CardModel { Owner = Event.Player, IsUpgradable = false }; c.Id.Entry = "SURVIVOR"; Event.Player.Deck.Cards.Add(c); }
            Event.Adapter.FullCardGrid = full;
            Event.Enchantment.Amount = 1;
            NDeckEnchantSelectScreen.Factory = (cards, model, amount, prefs) => {
                Surface = new(enchant: true, count: count, window: 25, maximumDomain: 128,
                    owner: Event.Player, domain: cards.ToArray(), overlays: Event.Overlays, enchantment: model);
                ((NDeckEnchantSelectScreen)Surface.Screen).Setup(model, amount, prefs);
                return (NDeckEnchantSelectScreen)Surface.Screen;
            };
            NDeckUpgradeSelectScreen.Factory = (cards, prefs, run) => {
                Surface = new(smith: true, count: count, window: 25, maximumDomain: 128,
                    owner: Event.Player, domain: cards.ToArray(), overlays: Event.Overlays);
                return (NDeckUpgradeSelectScreen)Surface.Screen;
            };
        }
        internal GenericEventV7Binding Binding => (GenericEventV7Binding)typeof(PinnedGenericEventV7NativeAdapter)
            .GetField("_pending", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(Event.Adapter)!;
        internal void Start() { Parent = Event.Start(); }
        internal ICardSelectionV1ReadValue Read() => Event.Session.ReadCardChild(Parent.Child!.ParentDecisionId, Parent.Child.ParentActionId, Parent.Child.Ordinal).Value;
        internal ICardSelectionV1ApplyValue Act(string action)
        {
            var ready = (CardSelectionV1Observation)Read();
            return Event.Session.ApplyCardChild(Parent.Child!.ParentDecisionId, Parent.Child.ParentActionId, Parent.Child.Ordinal, ready.DecisionId, action).Value;
        }
        internal ICardSelectionV1ReadValue Drain()
        {
            for (int i = 0; i < 180; i++)
            {
                var read = Read();
                if (read is not CardSelectionV1Observation { Status: "waiting" }) return read;
                Surface.ScrollFrame(); Surface.Animate(); Surface.FlushFreedPreviews();
            }
            throw new InvalidOperationException("Grid fixture did not settle.");
        }
        public void Dispose()
        {
            bool rejected = false;
            try { Event.Dispose(); } catch (InvalidOperationException) { rejected = true; }
            Check(rejected == RejectCleanup, "grid disposal preserves clean or failed ownership");
        }
    }
    private static void GridCardCases()
    {
        foreach (bool enchant in new[] { true, false }) foreach (int count in new[] { 48, 65, 128 })
        {
            using var f = new GridEventFixture(count, enchant, delayed: true);
            f.Start(); Check(f.Parent.Child?.ContractVersion == "card_grid_v1", "full event admits independent model grid");
            var ready = (CardSelectionV1Observation)f.Read();
            Check(ready.Candidates.Count == count && ready.LegalActions.Count == count && f.Surface.Inputs == 0 && f.Surface.Grid.FixturePanInputs == 0,
                "all public originals exposed without observation-time input");
            // The display order is reversed; slot zero is initially unallocated.
            Check(f.Surface.Grid.CurrentlyDisplayedCardHolders.All(h => !ReferenceEquals(h.CardModel, f.Event.Cards[0])), "target initially unallocated");
            Check(f.Act("select:0") is CardSelectionV1DispatchReceipt, "semantic selection accepted once");
            var preview = f.Drain() as CardSelectionV1Observation;
            Check(preview?.Phase == "preview" && preview.SelectedSlots.SequenceEqual(new[] { 0 }) && f.Surface.Inputs == 1 && f.Surface.Commits == 0,
                "bounded native navigation reaches exact original preview");
            Check(f.Act("confirm") is CardSelectionV1DispatchReceipt, "preview confirm accepted once");
            Check(f.Read() is CardSelectionV1Observation { Status: "waiting" } && f.Surface.Commits == 1, "effect cannot settle before chosen task");
            f.Event.Gate.SetResult();
            Check(f.Drain() is CardSelectionV1ResolvedResult { PriorResults.Count: 2 }, "exact effect and parent task settle");
            Check(f.Event.Cards[0].CurrentUpgradeLevel == (enchant ? 0 : 1) &&
                (enchant ? f.Event.Cards[0].Enchantment is { Amount: 1 } : f.Event.Cards[0].Enchantment is null) &&
                f.Event.Player.Deck.Cards.Skip(1).All(c => c.CurrentUpgradeLevel == 0 && c.Enchantment is null), "only chosen original changed");
            var parent = f.Event.Session.Read();
            Check(parent.Status == "ready" && parent.ParentReconciled == 1 && parent.ChildReconciled == 2, "nested receipts reconciled before proceed");
        }
        foreach (int count in new[] { 48, 65 })
        {
            using var f = new GridEventFixture(count, full: false); f.Start();
            Check(f.Parent.Status == (count == 65 ? "unsupported" : "waiting") && f.Parent.Child is null,
                "legacy contract retains allocated domain and 64-card bounds");
        }
        foreach (string mode in new[] { "survivor", "domain", "holder", "enchant_model", "wrong_effect", "effect_replaced", "foreign_overlay", "nested_overlay", "lost_confirm" })
        {
            using var f = new GridEventFixture(48, delayed: true); f.Start();
            f.RejectCleanup = mode != "lost_confirm";
            Check(f.Act("select:0") is CardSelectionV1DispatchReceipt, "adversarial selection accepted");
            if (mode is "survivor" or "domain" or "holder" or "enchant_model")
            {
                if (mode == "survivor") f.Event.Player.Deck.Cards[^1].CurrentUpgradeLevel++;
                if (mode == "domain") f.Surface.Grid.FixtureCards.Reverse();
                if (mode == "holder") f.Surface.Grid.CurrentlyDisplayedCardHolders[0].CardNode = new();
                if (mode == "enchant_model") f.Surface.Screen.GetType().GetField("_enchantmentAmount", BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(f.Surface.Screen, 9);
                Check(f.Read() is CardSelectionV1Observation { Status: "unsupported" } && f.Surface.Commits == 0, "changed pre-input binding rejected: " + mode);
                continue;
            }
            Check(f.Drain() is CardSelectionV1Observation { Phase: "preview" }, "adversarial exact preview");
            if (mode == "wrong_effect") f.Event.AfterEffect = () => f.Event.Cards[1].CurrentUpgradeLevel++;
            var confirm = (CardSelectionV1Observation)f.Read();
            _ = f.Act("confirm");
            var pending = f.Read();
            if (mode == "effect_replaced") Fixture.ApplyEnchantment(f.Event.Cards[0], 1);
            if (mode == "foreign_overlay") f.Event.Overlays.Screens.Add(new Godot.Control());
            if (mode == "nested_overlay") { f.Event.Overlays.Screens.Add(f.Surface.Screen); f.Event.Overlays.Screens.Add(new Godot.Control()); }
            if (mode == "lost_confirm")
            {
                var repeat = f.Event.Session.ApplyCardChild(f.Parent.Child!.ParentDecisionId, f.Parent.Child.ParentActionId, 1, confirm.DecisionId, "confirm").Value;
                Check(repeat is CardSelectionV1ApplyFailure && f.Surface.Commits == 1, "lost receipt never replays confirmation");
                f.Event.Gate.SetResult(); Check(f.Drain() is CardSelectionV1ResolvedResult, "original confirmation may reconcile");
                f.Event.Session.Read();
            }
            else
            {
                Check((mode == "wrong_effect" ? pending : f.Read()) is CardSelectionV1Observation { Status: "unsupported" }, "changed pending owner cannot settle: " + mode);
                f.Event.Overlays.Screens.Clear(); f.Event.Gate.SetResult();
                Check(f.Read() is CardSelectionV1Observation { Status: "unsupported" }, "failed ownership cannot recover after obstruction clears");
            }
        }
        {
            using var f = new GridEventFixture(48, delayed: true); f.Start();
            _ = f.Act("select:0"); _ = f.Drain(); _ = f.Act("confirm");
            Check(f.Read() is CardSelectionV1Observation { Status: "waiting" } && f.Surface.Commits == 1, "owned confirm dispatch precedes closing wait");
            f.Event.Overlays.Screens.Add(f.Surface.Screen); f.Event.Gate.SetResult();
            Check(f.Read() is CardSelectionV1Observation { Status: "waiting" }, "completed callback waits for retained selector closure");
            f.Event.Overlays.Screens.Clear();
            Check(f.Read() is CardSelectionV1ResolvedResult, "only exact retained selector may finish closing");
            _ = f.Event.Session.Read();
        }
        foreach (bool enchant in new[] { true, false })
        {
            using var f = new GridEventFixture(128, enchant);
            using var wire = new GenericEventV7WireService(new string('a', 32), f.Event.Session);
            JsonDocument ReadWire() => JsonDocument.Parse(wire.Handle("GET", GenericEventV7WireService.DecisionRoute, null));
            void PostWire(JsonElement root, string action, bool child)
            {
                var view = root.GetProperty(child ? "payload" : "parent");
                var owner = child ? root.GetProperty("child") : default;
                using var response = JsonDocument.Parse(wire.Handle("POST", GenericEventV7WireService.ActionRoute,
                    JsonSerializer.SerializeToUtf8Bytes(new { decision_id = view.GetProperty("decision_id").GetString(), action_id = action,
                        child = child ? new { ordinal = owner.GetProperty("ordinal").GetInt32(),
                            parent_decision_id = owner.GetProperty("parent_decision_id").GetString(),
                            parent_action_id = owner.GetProperty("parent_action_id").GetString() } : null })));
                Check(response.RootElement.GetProperty("payload").GetProperty("outcome").GetString() == "accepted", "real native wire accepts once");
            }
            using (var parent = ReadWire()) PostWire(parent.RootElement, "choose:0", false);
            var projection = new Sts2AgentBridge.Unified.FullNativeBackend();
            using (var selecting = ReadWire())
            {
                var projected = projection.ProjectGrid(f.Binding, selecting.RootElement);
                var choices = projected.Decision["candidates"]!.AsArray();
                Check(projected.Actions.SequenceEqual(Enumerable.Range(0, 128).Select(i => "select:" + i)) && choices.Count == 128,
                    "actual native wire and production graph retain all 128 model slots");
                var deck = projected.Decision["run"]!["children"]![0]!["children"]!.AsArray();
                Check(choices[0]!["subject"]!.GetValue<string>() == deck[0]!["ref"]!.GetValue<string>() &&
                    choices[127]!["subject"]!.GetValue<string>() == deck[127]!["ref"]!.GetValue<string>(),
                    "graph endpoints reference exact originals independently of recycled holders");
                var fields = projected.Decision["context"]!["children"]![0]!["fields"]!.AsArray();
                Check(fields.Single(v => v!["key"]!.GetValue<string>() == "modifier")!["value"]?.GetValue<string>() == (enchant ? "sown" : null) &&
                    fields.Single(v => v!["key"]!.GetValue<string>() == "amount")!["value"]?.GetValue<int>() == (enchant ? 1 : null),
                    "shared policy sees the exact pending enchantment and amount");
                PostWire(selecting.RootElement, "select:0", true);
            }
            bool confirmed = false, resolved = false;
            for (int read = 0; read < 180 && !resolved; read++)
            {
                f.Surface.ScrollFrame(); f.Surface.Animate(); f.Surface.FlushFreedPreviews();
                using var next = ReadWire(); var payload = next.RootElement.GetProperty("payload");
                string status = payload.GetProperty("status").GetString()!;
                if (status == "waiting") continue;
                if (status == "resolved") { resolved = true; break; }
                Check(status == "ready" && !confirmed, "only exact preview permits confirmation");
                Check(projection.ProjectGrid(f.Binding, next.RootElement).Actions.SequenceEqual(new[] { "confirm" }), "production graph maps exact preview confirmation");
                PostWire(next.RootElement, "confirm", true); confirmed = true;
            }
            Check(confirmed && resolved && f.Surface.Inputs == 1 && f.Surface.Commits == 1, "real native wire settles one selected effect");
            using var done = ReadWire();
            Check(done.RootElement.GetProperty("parent").GetProperty("parent_reconciled").GetInt32() == 1,
                "real wire retains completed parent receipt");
        }
    }
}
