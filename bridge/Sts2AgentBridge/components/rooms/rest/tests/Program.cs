using System;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using Sts2AgentBridge.Rooms.Rest;
using Sts2AgentBridge.Successors.RoomFlowsV1;

internal static partial class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int _checks;
    private static void Check(bool value, string label) { _checks++; if (!value) throw new Exception(label); }
    private static MethodInfo Target => typeof(NRestSiteRoom).GetMethod("AfterSelectingOptionAsync", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static void Foreign() { }
    private sealed class Fixture : IDisposable
    {
        public readonly NRun Run = new();
        public NRestSiteRoom Room => Run.RestSiteRoom;
        public readonly RestV2Session Session;
        public readonly RoomFlowWireService Wire;
        public readonly NRestSiteButton Button;
        public readonly string Action;
        public Fixture(string action = "lift", int count = 0)
        {
            Action = action; NRun.Instance = Run; NRestSiteRoom.Instance = Room;
            var player = Room.Characters[0].Player;
            player.GetRelic<Girya>()!.TimesLifted = count;
            player.GetRelic<PumpkinCandle>()!.KindleCount = count;
            RestSiteOption option = RestV2Session.Kind(action) switch {
                "lift" => new LiftRestSiteOption(player), "kindle" => new KindleRestSiteOption(player), "dig" => new DigRestSiteOption(player),
                "cook" => new CookRestSiteOption(player), "clone" => new CloneRestSiteOption(player), "hatch" => new HatchRestSiteOption(player),
                _ => throw new ArgumentException() };
            if (RestV2Session.Kind(action) == "cook") { AddCard(player); AddCard(player, removable: false); AddCard(player); }
            if (action == "clone") { AddCard(player, clone: true); AddCard(player); AddCard(player, clone: true); }
            if (action == "hatch") { AddCard(player, egg: true); AddCard(player); AddCard(player, egg: true); }
            async Task Execute() { if (await option.OnSelect()) Room.Continue(option); }
            Button = new() { Option = option, Click = () => { _ = Execute(); } };
            Room.Options.Add(option); Room.Buttons.Add(option, Button);
            Session = new(Nonce, new PinnedRestV2NativeAdapter()); Wire = new(Nonce, Session);
        }
        public RestV2Observation Read() => (RestV2Observation)Session.Read();
        public void Begin()
        {
            var ready = Read(); Check(ready.Status == "ready", "ready");
            Check(Session.Apply(ready.DecisionId, Action) is RoomFlowDispatchReceipt, "accepted");
        }
        public void Dispose() { Wire.Dispose(); Check(Harmony.GetPatchInfo(Target)?.Owners.Count is not > 0, "hook removed"); }
    }
    public static int Main(string[] args)
    {
        try
        {
            if (args.Length == 2 && args[0] == "--wire") return Serve(args[1]);
            Extended();
            foreach (var pair in new[] { ("lift", 0), ("lift", 2), ("kindle", 0), ("kindle", 9) })
            {
                using var f = new Fixture(pair.Item1, pair.Item2); f.Begin();
                Check(f.Read().Status == "waiting", "counter change is not task completion");
                f.Room.Completion.SetResult(); var done = f.Read();
                Check(done.Status == "complete" && done.Result!.Before == pair.Item2 && done.Result.After == pair.Item2 + RestV2Session.Delta(pair.Item1), "exact effect");
                Check(f.Button.Clicks == 1 && f.Read() == done, "one dispatch and stable terminal");
            }
            RejectBefore(f => f.Button.IsEnabled = false, "disabled");
            RejectBefore(f => f.Run.GlobalUi.MapScreen.IsOpen = true, "map open");
            RejectBefore(f => f.Room.Characters[0].Player.GetRelic<Girya>()!.TimesLifted++, "stale counter");
            RejectBefore(f => f.Room.Characters[0].Player.Girya = new Girya(), "same-valued replaced relic");
            RejectBefore(f => f.Room.Buttons[f.Button.Option] = new() { Option = f.Button.Option }, "replaced controller");
            RejectBefore(f => f.Run.RestSiteRoom = new(), "replaced room");
            RejectBefore(f => f.Run.GlobalUi.MapScreen = new(), "replaced map");
            RejectBefore(f => f.Room.Characters[0].Player = new(), "replaced player");
            RejectBefore(f => f.Run.GlobalUi.Overlays.ScreenCount = 1, "overlay");
            FailPending(f => f.Room.Completion.SetException(new Exception("native")), "faulted task");
            FailPending(f => f.Room.Completion.SetCanceled(), "canceled task");
            FailPending(f => { f.Room.Completion.SetResult(); f.Room.Characters[0].Player.GetRelic<Girya>()!.TimesLifted++; }, "wrong delta");
            FailPending(f => { f.Room.Completion.SetResult(); f.Run.GlobalUi.MapScreen.IsOpen = true; }, "wrong completion surface");
            FailPending(f => f.Room.Continue(f.Button.Option), "duplicate native continuation");
            FailPending(f => new NRestSiteRoom().Continue(f.Button.Option), "foreign room continuation");
            FailPending(f => f.Room.Continue(new KindleRestSiteOption(f.Room.Characters[0].Player)), "foreign option continuation");
            FailPending(f => f.Room.Characters[0].Player.Girya = new Girya(), "pending replaced relic");
            using (var f = new Fixture())
            {
                f.Begin(); for (int i = 0; i < 256; i++) Check(f.Read().Status == "waiting", "bounded pending");
                Check(f.Read().Status == "unsupported", "pending limit");
            }
            using (var f = new Fixture())
            {
                var r = f.Read(); Check(f.Session.Apply(r.DecisionId, "kindle") is RoomFlowApplyFailure { Outcome: "rejected" }, "unadvertised action");
                Check(f.Button.Clicks == 0, "no unsupported input");
            }
            using (var f = new Fixture())
            {
                f.Begin(); Check(f.Session.Apply(new string('a', 64), "lift") is RoomFlowApplyFailure, "duplicate action");
                Check(f.Button.Clicks == 1 && f.Read().Status == "unsupported", "duplicate stops");
            }
            using (var f = new Fixture())
            {
                var foreign = new Harmony("rest-test-foreign");
                foreign.Patch(Target, prefix: new HarmonyMethod(typeof(Program).GetMethod(nameof(Foreign), BindingFlags.Static | BindingFlags.NonPublic)!));
                try { var r = f.Read(); Check(f.Session.Apply(r.DecisionId, "lift") is RoomFlowApplyFailure, "foreign hook"); Check(f.Button.Clicks == 0, "foreign prevents click"); }
                finally { foreign.UnpatchAll("rest-test-foreign"); }
            }
            using (var f = new Fixture())
            {
                f.Begin(); f.Room.Options.Clear(); f.Room.Buttons.Clear(); f.Room.Completion.SetResult();
                Check(f.Read().Status == "complete", "native option regeneration permitted");
            }
            using (var f = new Fixture())
            {
                f.Begin();
                var hook = typeof(PinnedRestV2NativeAdapter).GetMethod("Observe", BindingFlags.Static | BindingFlags.NonPublic)!;
                var foreign = new Harmony("rest-test-reused-hook");
                foreign.Patch(Target, postfix: new HarmonyMethod(hook));
                f.Room.Completion.SetResult(); Check(f.Read().Status == "unsupported", "lost hook exclusivity");
                bool cleanupFailed = false;
                try { f.Session.Dispose(); } catch (InvalidOperationException) { cleanupFailed = true; }
                Check(cleanupFailed, "foreign ownership prevents false cleanup success");
                foreign.Unpatch(Target, HarmonyPatchType.All, "rest-test-reused-hook");
                f.Session.Dispose();
            }
            using (var f = new Fixture())
            {
                f.Button.Click = () => { f.Room.Characters[0].Player.GetRelic<Girya>()!.TimesLifted++; };
                f.Begin(); Check(f.Read().Status == "waiting", "no continuation cannot complete");
            }
            using (var f = new Fixture())
            {
                f.Button.Click = () => { Check(f.Read().Status == "unsupported", "reentrant read"); };
                var r = f.Read(); Check(f.Session.Apply(r.DecisionId, "lift") is RoomFlowApplyFailure { Outcome: "uncertain" }, "reentrant dispatch uncertain");
                Check(f.Button.Clicks == 1 && f.Read().Status == "unsupported", "reentrant failure sticky");
            }
            using (var f = new Fixture())
            {
                var read = Task.Run(f.Read).GetAwaiter().GetResult(); Check(read.Status == "unsupported", "off-thread stops");
                Check(f.Read().Status == "unsupported", "thread failure sticky");
            }
            Console.WriteLine(JsonSerializer.Serialize(new { status = "passed", checks = _checks, native_game_executed = false })); return 0;
        }
        catch (Exception e) { Console.Error.WriteLine(e); return 1; }
    }
    private static void RejectBefore(Action<Fixture> change, string label)
    {
        using var f = new Fixture(); var r = f.Read(); change(f);
        Check(f.Session.Apply(r.DecisionId, "lift") is RoomFlowApplyFailure, label);
        Check(f.Button.Clicks == 0, "no stale input");
    }
    private static void FailPending(Action<Fixture> change, string label)
    {
        using var f = new Fixture(); f.Begin(); change(f); Check(f.Read().Status == "unsupported", label);
        Check(f.Button.Clicks == 1, "no retry");
    }
    private static int Serve(string action)
    {
        using var f = new Fixture(action, action == "lift" ? 2 : 9);
        string? line;
        while ((line = Console.ReadLine()) is not null)
        {
            using var command = JsonDocument.Parse(line); var c = command.RootElement;
            string method = c.GetProperty("method").GetString()!;
            var bytes = f.Wire.Handle(method, method == "GET" ? RoomFlowWireProtocol.DecisionRoute : RoomFlowWireProtocol.ActionRoute,
                c.GetProperty("decision").GetString(), c.GetProperty("action").GetString());
            Console.WriteLine(System.Text.Encoding.UTF8.GetString(bytes));
            if (method == "GET" && f.Button.Clicks == 1 && !f.Room.Completion.Task.IsCompleted) f.Room.Completion.SetResult();
        }
        Check(f.Button.Clicks == 1, "client one action"); return 0;
    }
}
