using System;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Cards.Combat;
using Sts2AgentBridge.Unified;

internal static class Program
{
    private static int _checks;
    private static void Check(bool b, string label) { _checks++; if (!b) throw new Exception(label); }
    private static JsonElement Wire(object obj) => JsonSerializer.SerializeToElement(obj);
    private static CardModel Card(string id, string variable, int amount)
    {
        var card = new CardModel { Id = new(id) };
        card.DynamicVars.Values.Add(new(variable, amount));
        if (id == "NEOWS_FURY") { card.DynamicVars.Values.Add(new("Cards", 2)); card.Keywords.Add(CardKeyword.Exhaust); }
        return card;
    }
    private sealed class Setup : IDisposable
    {
        internal readonly Player Player = new();
        internal readonly CombatState Combat = new();
        internal readonly RunState Run = new();
        internal readonly PinnedPublicRewardDecisionReader Rewards = new();
        internal readonly CombatCardChoiceService Choice = new();
        internal readonly AgentPublicReader Reader;
        internal readonly CardModel Fury = Card("NEOWS_FURY", "Damage", 10);
        internal readonly CardModel A = Card("STRIKE_IRONCLAD", "Damage", 6), B = Card("STRIKE_IRONCLAD", "Damage", 6);
        internal readonly CardModel Defend = Card("DEFEND_IRONCLAD", "Block", 5);
        internal Setup()
        {
            var first = new MapPoint { coord = new(0, 1), PointType = MapPointType.Monster };
            var next = new MapPoint { coord = new(0, 2), PointType = MapPointType.Monster };
            first.Children.Add(next); Run.Map = new() { StartingMapPoint = first, BossMapPoint = next, Points = new() { first, next } };
            Run.CurrentMapPoint = first; Run.Players.Add(Player); RunManager.Instance.State = Run;
            Player.Deck.Cards.AddRange(new[] { Card("NEOWS_FURY", "Damage", 10), Card("STRIKE_IRONCLAD", "Damage", 6),
                Card("STRIKE_IRONCLAD", "Damage", 6), Card("DEFEND_IRONCLAD", "Block", 5) });
            Player.PlayerCombatState.Hand.Add(Fury); Player.PlayerCombatState.DiscardPile.Add(A);
            Player.PlayerCombatState.DiscardPile.Add(B); Player.PlayerCombatState.DiscardPile.Add(Defend);
            Combat.Players.Add(Player);
            Combat.Enemies.Add(new() { CurrentHp = 40, MaxHp = 40, Monster = new() { Id = new("SIMPLE_ENEMY"),
                NextMove = new MoveState { Intents = new() { new AttackIntent { Damage = 6 } } } } });
            Rewards.InteractionSession.Player = Player;
            Reader = new(Rewards, Choice); CombatManager.Instance.Setup(Combat);
        }
        internal AgentCapture Capture(string family = "combat", JsonElement? wire = null) => Reader.Capture(family,
            wire ?? Wire(new { decision_id = new string('a', 64), legal_actions = new[] {
                new { action_id = "play:0:0", kind = "play_card", hand_index = (int?)0, target_index = (int?)0 },
                new { action_id = "end_turn", kind = "end_turn", hand_index = (int?)null, target_index = (int?)null } } }), new(), null);
        public void Dispose() => Reader.Dispose();
    }
    private static JsonNode Pile(AgentCapture view, string kind) => view.Observation["context"]!["piles"]!.AsArray().Single(p => p!["kind"]!.GetValue<string>() == kind)!;
    private static void Unsupported(Action action, string label) { bool rejected = false; try { action(); } catch (AgentUnsupported) { rejected = true; } Check(rejected, label); }
    private static int Main(string[] args)
    {
        try
        {
            if (args.SequenceEqual(new[] { "--emit" }))
            {
                Emit(); return 0;
            }
            using (var s = new Setup())
            {
                var first = s.Capture();
                Check(first.Observation["candidates"]!.AsArray().Count == 2, "complete legal command translation");
                Check(JsonNode.DeepEquals(first.Observation, s.Capture().Observation), "repeated public read invariant");
                s.Combat.Enemies.Add(new() { Monster = new(), CurrentHp = 12, MaxHp = 12 });
                var two = s.Capture(); string second = two.Observation["context"]!["enemies"]![1]!["ref"]!.GetValue<string>();
                s.Combat.Enemies[0].CurrentHp = 0;
                Check(s.Capture().Observation["context"]!["enemies"]![0]!["ref"]!.GetValue<string>() == second, "living enemy compaction retains identity");
            }
            using (var s = new Setup())
            {
                var pcs = s.Player.PlayerCombatState;
                pcs.DiscardPile.Cards.Clear(); pcs.DrawPile.Add(s.A); pcs.DrawPile.Add(s.B); pcs.DrawPile.Add(s.Defend);
                var before = s.Capture(); pcs.DrawPile.Cards.Reverse();
                Check(JsonNode.DeepEquals(before.Observation, s.Capture().Observation), "hidden draw permutation invisible");
                pcs.DrawPile.Cards.Remove(s.A); pcs.Hand.Add(s.A);
                var after = s.Capture(); string drawn = Pile(after, "hand")["cards"]!["value"]![1]!["ref"]!.GetValue<string>();
                Check(drawn.Length > 0 && Pile(after, "draw")["count"]!.GetValue<int>() == 2, "duplicate draw publicly rebound");
            }
            using (var s = new Setup())
            {
                s.Player.Creature.Powers.Add(new() { Id = new("STRENGTH_POWER"), DisplayAmount = 2 });
                Check(s.Capture().Observation["context"]!["powers"]!["value"]![0]!["definition_id"]!.GetValue<string>() == "strength", "power vocabulary suffix");
                s.Fury.DynamicVars.Values[0].PreviewValue = 7.5m;
                var damage = Pile(s.Capture(), "hand")["cards"]!["value"]![0]!["values"]!["value"]![0]!["amount"]!.GetValue<int>();
                Check(damage == 7, "native displayed integer rounding");
                s.Fury.Id = new("UNMAPPED_CARD"); Unsupported(() => s.Capture(), "unmapped mechanics unsupported");
            }
            using (var s = new Setup())
            {
                var card = Card("INFLAME", "StrengthPower", 2); card.Type = CardType.Power; card.EnergyCost.Value = 0;
                s.Player.PlayerCombatState.PlayPile.Add(card); s.Player.PlayerCombatState.PlayPile.Cards.Remove(card);
                card.Pile = null; card.EnergyCost.Value = 1; card.Play();
                var before = s.Capture(); card.DynamicVars.Values[0].PreviewValue = 999; card.CurrentUpgradeLevel = 3;
                var power = Pile(before, "powers")["cards"]!["value"]![0]!;
                Check(power["cost"]!["energy"]!["value"]!.GetValue<int>() == 0, "freeze before until-played cost cleanup");
                Check(JsonNode.DeepEquals(before.Observation, s.Capture().Observation), "detached private power mutations invisible");
            }
            using (var s = new Setup())
            {
                var reward = new CardReward { HiddenOffers = new[] { Card("STRIKE_IRONCLAD", "Damage", 6) } };
                var parent = new ParentTarget { Reward = reward }; s.Rewards.InteractionSession.Parents.Add(parent);
                var wire = Wire(new { decision_id = new string('a',64), screen_kind = "rewards", legal_actions = new[] { new { action_id = "open:0" }, new { action_id = "proceed" } } });
                var before = s.Capture("reward", wire); reward.HiddenOffers = new[] { Card("UNREVEALED", "Damage", 999) };
                Check(JsonNode.DeepEquals(before.Observation, s.Capture("reward", wire).Observation), "closed card reward never leaks offers");
                s.Rewards.InteractionSession.ActiveCardReward = parent;
                var offered = Card("STRIKE_IRONCLAD", "Damage", 6); s.Rewards.InteractionSession.Cards.Add(new() { Model = offered });
                var child = s.Capture("reward", Wire(new { decision_id = new string('a',64), screen_kind = "card_reward", legal_actions = new[] { new { action_id = "choose:0" }, new { action_id = "skip_card" } } }));
                string acquired = child.Observation["context"]!["entries"]![0]!["cards"]!["value"]![0]!["ref"]!.GetValue<string>();
                s.Player.Deck.Cards.Add(offered); reward.SuccessfullySelected = true;
                var after = s.Capture("reward", Wire(new { decision_id = new string('b',64), screen_kind = "rewards", legal_actions = new[] { new { action_id = "proceed" } } }));
                Check(after.Observation["run"]!["deck"]!["value"]!.AsArray().Any(c => c!["ref"]!.GetValue<string>() == acquired), "acquired card keeps public identity");
                Check(after.Observation["context"]!["entries"]![0]!["cards"]!["status"]!.GetValue<string>() == "not_applicable", "resolved payload removed");
            }
            using (var s = new Setup())
            {
                s.Player.PotionSlots[1] = new(); Unsupported(() => s.Capture(), "potion legality not silently removed");
            }
            using (var s = new Setup())
            {
                s.Combat.Enemies[0].HpDisplay=HpDisplay.InfiniteWithNumbers;
                Check(s.Capture().Observation["context"]!["enemies"]![0]!["hp"]!.GetValue<int>()==40,"agent preserves visible invincibility numbers");
                s.Combat.Enemies[0].HpDisplay=HpDisplay.InfiniteWithoutNumbers;
                Unsupported(()=>s.Capture(),"agent v1 rejects hidden enemy health");
                s.Combat.Enemies[0].HpDisplay=(HpDisplay)99;
                Unsupported(()=>s.Capture(),"agent v1 rejects unknown enemy display");
                s.Combat.Enemies[0].HpDisplay=HpDisplay.Normal;s.Player.Creature.HpDisplay=HpDisplay.InfiniteWithoutNumbers;
                Unsupported(()=>s.Capture(),"agent v1 rejects hidden player health");
            }
            foreach (string character in new[] { "IRONCLAD", "SILENT", "REGENT", "NECROBINDER", "DEFECT" })
                using (var s = new Setup())
                {
                    s.Player.Character.Id = new(character);
                    if (character == "DEFECT") { s.Player.PlayerCombatState.OrbQueue.Capacity = 3; s.Player.PlayerCombatState.OrbQueue.Orbs.Add(new()); }
                    var resources = s.Capture().Observation["context"]!["resources"]!;
                    Check(resources["stars"]!["status"]!.GetValue<string>() == (character == "REGENT" ? "known" : "not_applicable"), "five character star applicability");
                    Check(resources["osty"]!["status"]!.GetValue<string>() == (character == "NECROBINDER" ? "known" : "not_applicable"), "five character companion applicability");
                    if (character == "DEFECT") Check(resources["orbs"]!["value"]![0]!["kind"]!.GetValue<string>() == "lightning", "orb public vocabulary");
                }
            using (var s = new Setup())
            {
                s.Fury.Id = new("ZAP"); s.Fury.DynamicVars.Values.Clear();
                var view = s.Capture(); var resources = view.Observation["context"]!["resources"]!;
                Check(resources["orb_slots"]!["value"]!.GetValue<int>() == 0, "off-character visible channel keeps known zero resource");
                Check(Pile(view,"hand")["cards"]!["value"]![0]!["values"]!["value"]![0]!["key"]!.GetValue<string>() == "channel_lightning", "fixed mechanics beyond native dynamic vars");
            }
            using (var s = new Setup())
            {
                using var late = new AgentPublicReader(s.Rewards, s.Choice);
                Unsupported(() => late.Capture("combat", Wire(new { decision_id = new string('a',64) }), new(), null), "late power history unavailable");
            }
            Console.WriteLine(JsonSerializer.Serialize(new { status = "passed", checks = _checks, target_game_executed = false })); return 0;
        }
        catch (Exception e) { Console.Error.WriteLine(e); return 1; }
    }

    private static JsonObject Event(string kind, string? subject, string? target = null, bool selected = false) => new() {
        ["kind"] = kind, ["subject"] = new JsonObject { ["status"] = subject is null ? "not_applicable" : "known", ["value"] = subject },
        ["target"] = new JsonObject { ["status"] = target is null ? "not_applicable" : "known", ["value"] = target },
        ["values"] = selected ? new JsonArray(new JsonObject { ["key"] = "selected", ["amount"] = 1 }) : new JsonArray() };
    private static void Emit()
    {
        using var s = new Setup(); var history = new JsonArray();
        var initial = s.Capture(); Console.WriteLine(initial.Observation.ToJsonString());
        string source = initial.Commands[0].Candidate["subject"]!.GetValue<string>();
        string enemy = initial.Commands[0].Candidate["target"]!.GetValue<string>();
        s.Player.PlayerCombatState.Hand.Cards.Clear(); s.Player.PlayerCombatState.PlayPile.Add(s.Fury);
        s.Combat.Enemies[0].CurrentHp -= 10; s.Player.PlayerCombatState.Energy--;
        history.Add(Event("card_played", source, enemy));
        var cards = new[] { s.A, s.B, s.Defend }; var surface = new object(); var holders = cards.Select(_ => new object()).ToArray();
        for (int selected = 0; selected <= 2; selected++)
        {
            s.Choice.Surface = new(surface, "discard", 0, 2, true,
                cards.Select((c, i) => new ChoiceCard(c, holders[i])).ToArray(), cards.Take(selected).Cast<object>().ToArray());
            string[] actions = (selected == 2 ? new[] { "deselect:0", "deselect:1", "confirm" } :
                Enumerable.Range(0, 3).Select(i => (i < selected ? "deselect:" : "select:") + i).Append("confirm").ToArray());
            var view = s.Reader.Capture("choice", Wire(new { decision_id = new string('a',64), legal_actions = actions }), history, source);
            Console.WriteLine(view.Observation.ToJsonString());
            if (selected < 2) history.Add(Event("card_selected", view.Observation["context"]!["options"]![selected]!.GetValue<string>(), selected: true));
        }
        history.Add(Event("selection_confirmed", null));
        var pcs = s.Player.PlayerCombatState;
        pcs.DiscardPile.Cards.Remove(s.A); pcs.DiscardPile.Cards.Remove(s.B); pcs.Hand.Add(s.A); pcs.Hand.Add(s.B);
        pcs.PlayPile.Cards.Clear(); pcs.ExhaustPile.Add(s.Fury);
        var final = s.Reader.Capture("combat", Wire(new { decision_id = new string('b',64), legal_actions = new[] {
            new { action_id = "play:0:0", kind = "play_card", hand_index = (int?)0, target_index = (int?)0 },
            new { action_id = "play:1:0", kind = "play_card", hand_index = (int?)1, target_index = (int?)0 },
            new { action_id = "end_turn", kind = "end_turn", hand_index = (int?)null, target_index = (int?)null } } }), history, null);
        Console.WriteLine(final.Observation.ToJsonString());
    }
}
