using System;
using System.Linq;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Rooms.Rest;

internal static partial class Program
{
    private sealed class RestLeaveFixture : IRestLeave
    {
        internal string? Decision = new string('a', 64);
        internal int Inputs, Polls;
        internal bool Complete, Lost, Disposed;
        public string? ReadDecision(object room) => Decision;
        public void Apply(string decision) { Check(decision == Decision, "exact rest Proceed token"); Inputs++; if (Lost) throw new InvalidOperationException(); }
        public bool Poll() { Polls++; return Complete; }
        public void Dispose() { Disposed = true; if (Inputs != 0 && !Complete) throw new InvalidOperationException(); }
    }
    private static void RestLeaveCases()
    {
        foreach (string mode in new[] { "complete", "stale", "lost", "pending", "unavailable" })
        {
            using var f = new Fixture("lift", interactive: true);
            var leave = new RestLeaveFixture();
            var session = new RestInteractiveSession(Nonce, f.Native, leave);
            if (mode == "unavailable") leave.Decision = null;
            var before = InteractiveRead(session);
            Check(before["schema_version"]!.GetValue<int>() == 4 &&
                before["legal_actions"]!.AsArray().Any(a => a!.GetValue<string>() == "leave") == (mode != "unavailable"), "rest Proceed follows native legality");
            if (mode == "stale") leave.Decision = new string('b', 64);
            if (mode == "lost") leave.Lost = true;
            var result = JsonNode.Parse(session.Handle(true, before["decision_id"]!.GetValue<string>(), "leave"))!;
            Check(result["status"]!.GetValue<string>() == (mode is "stale" or "unavailable" ? "rejected" : mode == "lost" ? "uncertain" : "accepted"), "rest leave boundary " + mode);
            if (mode == "complete")
            {
                Check(InteractiveRead(session)["status"]!.GetValue<string>() == "waiting", "rest Leave awaits actual map handoff");
                leave.Complete = true;
                var done = InteractiveRead(session);
                Check(done["status"]!.GetValue<string>() == "complete" && done["completed"]!.AsArray().Count == 1 &&
                    done["completed"]![0]!["action_id"]!.GetValue<string>() == "leave", "rest Leave exact receipt");
                int polls = leave.Polls;
                Check(InteractiveRead(session).ToJsonString() == done.ToJsonString() && leave.Polls == polls, "rest Leave terminal retention");
            }
            bool failed = false; try { session.Dispose(); } catch (InvalidOperationException) { failed = true; }
            Check(failed == (mode is "lost" or "pending") && leave.Disposed, "rest unresolved Leave cannot hand off");
            Check(leave.Inputs == (mode is "stale" or "unavailable" ? 0 : 1) && f.Button.Clicks == 0, "rest Leave never invokes a rest option");
        }
    }
    private static int ServeInteractive(string option)
    {
        using var f = new Fixture(option, interactive: true);
        using var session = new RestInteractiveSession(Nonce, f.Native);
        string? line;
        while ((line = Console.ReadLine()) is not null)
        {
            var input = JsonNode.Parse(line)!;
            bool post = input["method"]!.GetValue<string>() == "POST";
            if (!post && f.Execution?.IsCompletedSuccessfully == true) f.Room.Completion.TrySetResult();
            byte[] body = session.Handle(post, input["decision"]?.GetValue<string>(), input["action"]?.GetValue<string>());
            Console.WriteLine(System.Text.Encoding.UTF8.GetString(body));
        }
        return 0;
    }
    private static JsonObject InteractiveRead(RestInteractiveSession session) => JsonNode.Parse(session.Handle(false, null, null))!.AsObject();
    private static void InteractiveApply(RestInteractiveSession session, JsonObject view, string action)
    {
        var reply = JsonNode.Parse(session.Handle(true, view["decision_id"]!.GetValue<string>(), action))!;
        Check(reply["status"]!.GetValue<string>() == "accepted", "interactive wire accepts once: " + action);
    }
    private static void InteractiveWireCases()
    {
        LargeRestHandoff();
        FullRestCapacityCases();
        RestLeaveCases();
        using (var f = new Fixture("heal", interactive: true))
        {
            var session = new RestInteractiveSession(Nonce, f.Native);
            try
            {
                var snapshot = new Sts2AgentBridge.Core.Public.PublicRewardDecisionSnapshot(
                    Sts2AgentBridge.Core.Public.PublicDecisionStatus.Ready, new string('a', 64), "rewards", default,
                    new[] { new Sts2AgentBridge.Core.Public.PublicRewardItem(0, Sts2AgentBridge.Core.Public.PublicRewardKind.Card, false, 0, new[] { "HIDDEN_ONE" }, true) }, new[] { "open:0" });
                RestRewardContinuation.FixtureView = snapshot;
                InteractiveApply(session, InteractiveRead(session), "option:heal");
                var ready = InteractiveRead(session);
                RestRewardContinuation.FixtureView = snapshot with { DecisionId = new string('b', 64), Player = new(5, 60, 20, 0) };
                var reply = JsonNode.Parse(session.Handle(true, ready["decision_id"]!.GetValue<string>(), "reward:open:0"))!;
                Check(reply["status"]!.GetValue<string>() == "rejected", "stale inner reward binding rejects before input despite identical outer public summary");
            }
            finally { RestRewardContinuation.FixtureView = null; try { session.Dispose(); } catch (InvalidOperationException) { } }
        }
        using (var f = new Fixture("heal", interactive: true))
        {
            var session = new RestInteractiveSession(Nonce, f.Native);
            try
            {
                var snapshot = new Sts2AgentBridge.Core.Public.PublicRewardDecisionSnapshot(
                    Sts2AgentBridge.Core.Public.PublicDecisionStatus.Ready, new string('a', 64), "rewards", default,
                    new[] { new Sts2AgentBridge.Core.Public.PublicRewardItem(0, Sts2AgentBridge.Core.Public.PublicRewardKind.Card, false, 0, new[] { "HIDDEN_ONE" }, true) }, new[] { "open:0" });
                RestRewardContinuation.FixtureView = snapshot;
                InteractiveApply(session, InteractiveRead(session), "option:heal");
                string before = InteractiveRead(session).ToJsonString();
                RestRewardContinuation.FixtureView = snapshot with { DecisionId = new string('b', 64), Rewards = new[] { snapshot.Rewards[0] with { Cards = new[] { "HIDDEN_TWO" } } } };
                Check(InteractiveRead(session).ToJsonString() == before && !before.Contains("HIDDEN_"), "unopened card offers do not affect public rest decision or identity");
                RestRewardContinuation.FixtureView = snapshot with { ScreenKind = "card_reward", LegalActions = new[] { "choose:0", "skip" } };
                Check(InteractiveRead(session).ToJsonString().Contains("HIDDEN_ONE"), "opened native card reward is public");
                RestRewardContinuation.FixtureView = null; f.Room.Completion.SetResult();
                Check(InteractiveRead(session)["status"]!.GetValue<string>() == "complete", "heal fixture completes after reward owner");
            }
            finally { RestRewardContinuation.FixtureView = null; session.Dispose(); }
        }
        foreach (string mode in new[] { "wrong_counter", "modal" })
        {
            using var f = new Fixture("lift", interactive: true);
            var session = new RestInteractiveSession(Nonce, f.Native);
            InteractiveApply(session, InteractiveRead(session), "option:lift");
            if (mode == "wrong_counter") f.Room.Characters[0].Player.GetRelic<MegaCrit.Sts2.Core.Models.Relics.Girya>()!.TimesLifted = 0;
            else MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance.Blocker = new();
            f.Room.Completion.SetResult();
            Check(InteractiveRead(session)["status"]!.GetValue<string>() == "unsupported", "completed task alone cannot settle rest: " + mode);
            try { session.Dispose(); } catch (InvalidOperationException) { }
        }
        foreach (string kind in new[] { "smith", "cook" }) foreach (string mode in new[] { "cancel_empty", "cancel_selected", "confirm" })
        {
            using var f = new Fixture(kind, interactive: true);
            using var session = new RestInteractiveSession(Nonce, f.Native);
            var initial = InteractiveRead(session); Check(initial["phase"]!.GetValue<string>() == "option", "interactive option");
            InteractiveApply(session, initial, "option:" + kind);
            var child = InteractiveRead(session);
            Check(child["phase"]!.GetValue<string>() == "selection" && child["completed"]!.AsArray().Count == 0, "parent pending through child");
            if (mode != "cancel_empty")
            {
                int count = mode == "confirm" && kind == "cook" ? 2 : 1;
                for (int i = 0; i < count; i++)
                {
                    InteractiveApply(session, child, "select:" + i); child = InteractiveRead(session);
                    Check(child["completed"]!.AsArray().Count == 1 && child["completed"]![0]!["action_id"]!.GetValue<string>() == "select:" + i,
                        "selection reconciles without completing parent");
                }
            }
            InteractiveApply(session, child, mode == "confirm" ? "confirm" : "cancel");
            if (mode == "confirm")
            {
                Check(InteractiveRead(session)["status"]!.GetValue<string>() == "waiting", "selected effect waits for native room continuation");
                f.Room.Completion.SetResult();
            }
            var done = InteractiveRead(session);
            Check(done["status"]!.GetValue<string>() == "complete" && done["completed"]!.AsArray().Count == 2, "child and parent completed after native return");
            Check(done["completed"]![1]!["result"]!.GetValue<string>() == (mode == "confirm" ? "reconciled" : "cancelled"), "cancellation is explicit");
            Check(f.Button.Clicks == 1 && InteractiveRead(session).ToJsonString() == done.ToJsonString(), "stable terminal does not repeat parent");
        }
        foreach (string mode in new[] { "stale", "illegal", "foreground", "lost" })
        {
            using var f = new Fixture("smith", interactive: true);
            var session = new RestInteractiveSession(Nonce, f.Native);
            var ready = InteractiveRead(session);
            if (mode == "foreground") MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance.Blocker = new();
            if (mode == "lost") f.Button.Click = () => throw new InvalidOperationException();
            string id = mode == "stale" ? new string('0', 64) : ready["decision_id"]!.GetValue<string>();
            var reply = JsonNode.Parse(session.Handle(true, id, mode == "illegal" ? "option:unknown" : "option:smith"))!;
            Check(reply["status"]!.GetValue<string>() == (mode == "lost" ? "uncertain" : "rejected"), "precise dispatch failure: " + mode);
            session.Handle(true, id, "option:smith"); Check(f.Button.Clicks == (mode == "lost" ? 1 : 0), "no retry after failure");
            bool cleanupFailed = false; try { session.Dispose(); } catch (InvalidOperationException) { cleanupFailed = true; }
            Check(cleanupFailed == (mode == "lost"), "cleanup cannot hide uncertain dispatch");
        }
    }

    private static void LargeRestHandoff()
    {
        using var f = new Fixture("clone", interactive: true);
        var player = f.Room.Characters[0].Player;
        player.Deck.Cards.Clear();
        for (int i = 0; i < 54; i++) AddCard(player, clone: i < 32);
        using (var option = new RestInteractiveSession(Nonce, leave: new RestLeaveFixture()))
        {
            InteractiveApply(option, InteractiveRead(option), "option:clone");
            f.Room.Options.Clear(); f.Room.Buttons.Clear(); f.Room.Completion.SetResult();
            var done = InteractiveRead(option);
            Check(done["status"]!.GetValue<string>() == "complete" && done["completed"]!.AsArray().Count == 1 &&
                player.Deck.Cards.Count == 86, "Clone completes exactly before regenerated large rest");
        }
        var leave = new RestLeaveFixture();
        using var next = new RestInteractiveSession(Nonce, leave: leave);
        var ready = InteractiveRead(next);
        Check(ready["status"]!.GetValue<string>() == "ready" && ready["cards"]!.AsArray().Count == 86 &&
            ready["legal_actions"]!.AsArray().Single()!.GetValue<string>() == "leave",
            "regenerated 86-card rest exposes native Proceed");
        InteractiveApply(next, ready, "leave"); leave.Complete = true;
        Check(InteractiveRead(next)["status"]!.GetValue<string>() == "complete" && leave.Inputs == 1 && f.Button.Clicks == 1,
            "large rest handoff leaves once without replaying Clone");
    }

    private static void FullRestCapacityCases()
    {
        foreach (var (full, count, supported) in new[] { (false, 64, true), (false, 65, false), (true, 128, true), (true, 129, false) })
        {
            using var f = new Fixture("lift", interactive: true);
            var player = f.Room.Characters[0].Player;
            for (int i = 0; i < count; i++) AddCard(player);
            using var session = new RestInteractiveSession(Nonce, leave: full ? new RestLeaveFixture() : null);
            var view = InteractiveRead(session);
            Check(view["status"]!.GetValue<string>() == (supported ? "ready" : "unsupported") && f.Button.Clicks == 0,
                "rest profile retains explicit starting-deck capacity");
            if (full && !supported) Check(view["code"]!.GetValue<string>() == "rest_deck_capacity", "closed deck capacity diagnostic");
        }
        foreach (string mode in new[] { "boundary", "overflow", "changed" })
        {
            using var f = new Fixture("clone", interactive: true);
            var player = f.Room.Characters[0].Player; player.Deck.Cards.Clear();
            for (int i = 0; i < 86; i++) AddCard(player, clone: i < (mode == "overflow" ? 43 : 42));
            using var session = new RestInteractiveSession(Nonce, leave: new RestLeaveFixture());
            var ready = InteractiveRead(session);
            if (mode == "overflow")
            {
                Check(ready["status"]!.GetValue<string>() == "unsupported" && ready["code"]!.GetValue<string>() == "rest_clone_capacity" &&
                    f.Button.Clicks == 0 && player.Deck.Cards.Count == 86, "predictable 129-card Clone stops before any input");
                continue;
            }
            if (mode == "changed")
            {
                AddCard(player, clone: true);
                var reply = JsonNode.Parse(session.Handle(true, ready["decision_id"]!.GetValue<string>(), "option:clone"))!;
                Check(reply["status"]!.GetValue<string>() == "rejected" && reply["code"]!.GetValue<string>() == "rest_clone_capacity" &&
                    f.Button.Clicks == 0 && player.Deck.Cards.Count == 87, "fresh dispatch rechecks Clone capacity before input");
                continue;
            }
            InteractiveApply(session, ready, "option:clone"); f.Room.Completion.SetResult();
            Check(InteractiveRead(session)["status"]!.GetValue<string>() == "complete" && player.Deck.Cards.Count == 128 &&
                f.Button.Clicks == 1, "Clone reaches exact supported inventory boundary");
        }
        foreach (string kind in new[] { "cook", "smith" })
        {
            using var f = new Fixture(kind, interactive: true);
            var player = f.Room.Characters[0].Player; player.Deck.Cards.Clear();
            for (int i = 0; i < 128; i++) AddCard(player);
            var originals = player.Deck.Cards.ToArray(); int maxHp = player.Creature.MaxHp;
            using var session = new RestInteractiveSession(Nonce, leave: new RestLeaveFixture());
            InteractiveApply(session, InteractiveRead(session), "option:" + kind);
            var choice = InteractiveRead(session);
            Check(choice["cards"]!.AsArray().Count == 128 && choice["legal_actions"]!.AsArray().Any(a => a!.GetValue<string>() == "select:127"),
                "full rest publishes complete large selector domain");
            InteractiveApply(session, choice, "select:127"); choice = InteractiveRead(session);
            if (kind == "cook") { InteractiveApply(session, choice, "select:0"); choice = InteractiveRead(session); }
            InteractiveApply(session, choice, "confirm"); f.Room.Completion.SetResult();
            Check(InteractiveRead(session)["status"]!.GetValue<string>() == "complete", "large rest selection and parent reconcile");
            if (kind == "cook") Check(player.Deck.Cards.SequenceEqual(originals.Skip(1).Take(126)) && player.Creature.MaxHp == maxHp + 9,
                "large Cook removes only endpoint originals");
            else Check(player.Deck.Cards.SequenceEqual(originals) && originals[127].CurrentUpgradeLevel == 1 && originals.Take(127).All(c => c.CurrentUpgradeLevel == 0),
                "large Smith upgrades only the selected original");
        }
    }
}
