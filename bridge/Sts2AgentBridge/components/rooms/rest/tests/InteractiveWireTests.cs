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
}
