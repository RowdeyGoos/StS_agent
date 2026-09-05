using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.ItemWireV1.Tests;

internal static class Program
{
    private const string Nonce = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private const int MaximumCommandCharacters = 1024;
    private const int MaximumCommands = 512;
    private static int _checkCount;

    private static int Main(string[] arguments)
    {
        if (arguments.Length == 2 && arguments[0] == "--fixture")
        {
            return RunFixture(arguments[1]);
        }
        if (arguments.Length != 0)
        {
            return 2;
        }
        Run("request_validation", RequestValidation);
        Run("waiting_and_ready_encoding", WaitingAndReadyEncoding);
        Run("potion_success", PotionSuccess);
        Run("relic_success", RelicSuccess);
        Run("delayed_and_closed_overlay", DelayedAndClosedOverlay);
        Run("full_belt_and_stale", FullBeltAndStale);
        Run("uncertain_and_replay", UncertainAndReplay);
        Run("reentrant_dispatch", ReentrantDispatch);
        Run("maximum_body_and_canonical_actions", MaximumBodyAndCanonicalActions);
        Console.WriteLine(
            "{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"item_v1_wire_producer\",\"check_count\":" +
            _checkCount + "}");
        return 0;
    }

    private static int RunFixture(string name)
    {
        if (!FixtureScenario.IsKnown(name))
        {
            return 2;
        }
        var adapter = new FixtureScenario(name);
        var service = new ItemWireV1Service(Nonce, adapter);
        int commands = 0;
        int decisionReads = 0;
        while (true)
        {
            string? line = ReadBoundedLine(Console.In, MaximumCommandCharacters);
            if (line is null)
            {
                break;
            }
            commands++;
            if (commands > MaximumCommands)
            {
                return 2;
            }
            FixtureCommand command = ParseCommand(line);
            if (command.Method == "GET" &&
                command.Route == ItemWireV1Protocol.DecisionRoute)
            {
                decisionReads++;
            }
            byte[] response = service.Handle(
                command.Method, command.Route, command.DecisionId, command.ActionId);
            Stream output = Console.OpenStandardOutput();
            output.Write(response, 0, response.Length);
            output.WriteByte((byte)'\n');
            output.Flush();
        }
        Console.Error.Write(
            "{\"dispatch_count\":" + adapter.DispatchCount +
            ",\"last_action_index\":" + adapter.LastActionIndex +
            ",\"read_count\":" + decisionReads + "}\n");
        return 0;
    }

    private static void RequestValidation()
    {
        var adapter = new FixtureScenario("relic_success");
        var service = new ItemWireV1Service(Nonce, adapter);
        string invalid = Fixed("error", ",\"code\":\"invalid_request\"");
        foreach ((string? method, string? route, string? decision, string? action) in new[]
        {
            ((string?)"get", ItemWireV1Protocol.DecisionRoute, null, null),
            ("GET", "/wrong", null, null),
            ("GET", ItemWireV1Protocol.DecisionRoute, new string('0', 64), null),
            ("POST", ItemWireV1Protocol.ActionRoute, null, null),
            ("POST", ItemWireV1Protocol.ActionRoute, new string('0', 64), "collect:01"),
            ("POST", ItemWireV1Protocol.ActionRoute, new string('0', 64), "collect:256"),
        })
        {
            byte[] body = service.Handle(method, route, decision, action);
            Check(Text(body) == invalid, "fixed invalid request");
        }
        Check(adapter.SurfaceCalls == 0 && adapter.DispatchCount == 0,
            "invalid request avoids core");
        byte[] mutable = service.Handle("bad", "bad", null, null);
        mutable[0] = (byte)'X';
        Check(Text(service.Handle("bad", "bad", null, null)) == invalid,
            "fixed error copy");
    }

    private static void WaitingAndReadyEncoding()
    {
        var delayed = new FixtureScenario("delayed");
        var service = new ItemWireV1Service(Nonce, delayed);
        Check(Text(Get(service)) == Fixed("waiting"), "waiting exact");
        Check(Text(Get(service)) == Fixed("waiting"), "second waiting exact");
        string ready = Text(Get(service));
        using JsonDocument document = JsonDocument.Parse(ready);
        JsonElement root = document.RootElement;
        Check(ready.Length <= ItemWireV1Protocol.MaximumBodyBytes &&
              ready.All(character => character <= 0x7f) && !ready.Contains('\\') &&
              root.GetProperty("status").GetString() == "ready", "ready encoding");
        Check(PropertyNames(root).SequenceEqual(new[]
        {
            "schema_version", "protocol", "version", "session_nonce", "surface_ordinal",
            "status", "decision_id", "offers", "potion_slots", "legal_actions",
        }), "ready member order");
        Check(root.GetProperty("offers")[0].GetProperty("index").GetInt32() == 5 &&
              root.GetProperty("legal_actions")[0].GetString() == "collect:5",
            "ready native index");
    }

    private static void PotionSuccess()
    {
        var adapter = new FixtureScenario("potion_success");
        var service = new ItemWireV1Service(Nonce, adapter);
        string ready = Text(Get(service));
        (string decision, string action) = Correlation(ready);
        Check(action == "collect:3", "potion action");
        string accepted = Text(Post(service, decision, action));
        Check(accepted == Correlated("accepted", decision, action), "accepted exact");
        string resolved = Text(Get(service));
        Check(resolved == ResolvedBody(decision, action, 3, "potion", "Potion_Synthetic"),
            "potion resolved exact");
        Check(adapter.DispatchCount == 1 && adapter.LastActionIndex == 3,
            "potion dispatched once");
    }

    private static void RelicSuccess()
    {
        var adapter = new FixtureScenario("relic_success");
        var service = new ItemWireV1Service(Nonce, adapter);
        (string decision, string action) = Correlation(Text(Get(service)));
        Check(action == "collect:7", "relic action");
        Check(Text(Post(service, decision, action)) == Correlated("accepted", decision, action),
            "relic accepted");
        Check(Text(Get(service)) == ResolvedBody(
            decision, action, 7, "relic", "Relic_Synthetic"), "relic resolved");
    }

    private static void DelayedAndClosedOverlay()
    {
        var delayed = new FixtureScenario("delayed");
        var delayedService = new ItemWireV1Service(Nonce, delayed);
        Get(delayedService);
        Get(delayedService);
        (string decision, string action) = Correlation(Text(Get(delayedService)));
        Check(Text(Post(delayedService, decision, action)) ==
              Correlated("accepted", decision, action), "delayed accepted");
        Check(Text(Get(delayedService)) == Fixed("waiting") &&
              Text(Get(delayedService)) == Fixed("waiting") &&
              Text(Get(delayedService)) == ResolvedBody(
                  decision, action, 5, "potion", "Potion_Delayed"),
            "delayed reconciliation");

        var closed = new FixtureScenario("overlay_closed");
        var closedService = new ItemWireV1Service(Nonce, closed);
        (decision, action) = Correlation(Text(Get(closedService)));
        Check(Text(Post(closedService, decision, action)) ==
              Correlated("accepted", decision, action), "closed accepted");
        Check(Text(Get(closedService)) == ResolvedBody(
            decision, action, 9, "relic", "Relic_Closed"), "closed retained result");
        Check(closed.SurfaceAfterDispatchIsMissing, "closed fixture surface");
    }

    private static void FullBeltAndStale()
    {
        var full = new FixtureScenario("full_belt");
        var fullService = new ItemWireV1Service(Nonce, full);
        Check(Text(Get(fullService)) == Fixed("unsupported") && full.DispatchCount == 0,
            "full belt unsupported");

        var stale = new FixtureScenario("stale");
        var staleService = new ItemWireV1Service(Nonce, stale);
        (string decision, string action) = Correlation(Text(Get(staleService)));
        Check(Text(Post(staleService, decision, action)) == Fixed("unsupported") &&
              stale.DispatchCount == 0, "stale zero dispatch");
    }

    private static void UncertainAndReplay()
    {
        var uncertain = new FixtureScenario("uncertain");
        var service = new ItemWireV1Service(Nonce, uncertain);
        (string decision, string action) = Correlation(Text(Get(service)));
        Check(Text(Post(service, decision, action)) == Fixed("uncertain") &&
              uncertain.DispatchCount == 1, "uncertain fixed");
        Check(Text(Post(service, decision, action)) == Fixed("rejected") &&
              uncertain.DispatchCount == 1, "uncertain replay rejected");
        Check(Text(Get(service)) == Fixed("unsupported"), "uncertain cannot resolve");

        var wrong = new FixtureScenario("relic_success");
        var wrongService = new ItemWireV1Service(Nonce, wrong);
        (decision, action) = Correlation(Text(Get(wrongService)));
        Check(Text(Post(wrongService, decision, "collect:255")) == Fixed("rejected") &&
              wrong.DispatchCount == 0, "unadvertised action rejected");
        Check(Text(Post(wrongService, decision, action)) == Fixed("rejected") &&
              wrong.DispatchCount == 0 && wrong.SurfaceCalls == 1,
            "valid post attempt is not retried");
    }

    private static void MaximumBodyAndCanonicalActions()
    {
        var maximum = new MaximumAdapter();
        var service = new ItemWireV1Service(Nonce, maximum);
        byte[] body = Get(service);
        Check(body.Length <= ItemWireV1Protocol.MaximumBodyBytes, "maximum body bound");
        using JsonDocument document = JsonDocument.Parse(body);
        Check(document.RootElement.GetProperty("offers").GetArrayLength() == 8 &&
              document.RootElement.GetProperty("potion_slots").GetArrayLength() == 8 &&
              document.RootElement.GetProperty("legal_actions").GetArrayLength() == 8,
            "maximum counts");
        Check(ItemWireV1Protocol.IsCanonicalActionId("collect:0", out int zero) && zero == 0 &&
              ItemWireV1Protocol.IsCanonicalActionId("collect:255", out int max) && max == 255 &&
              !ItemWireV1Protocol.IsCanonicalActionId("collect:00", out _) &&
              !ItemWireV1Protocol.IsCanonicalActionId("collect:-1", out _),
            "canonical action grammar");
    }

    private static void ReentrantDispatch()
    {
        var adapter = new ReentrantAdapter();
        var service = new ItemWireV1Service(Nonce, adapter);
        adapter.Service = service;
        (string decision, string action) = Correlation(Text(Get(service)));
        adapter.DecisionId = decision;
        adapter.ActionId = action;
        Check(Text(Post(service, decision, action)) ==
              Correlated("accepted", decision, action), "reentrant outer accepted");
        Check(adapter.InnerRead == Fixed("waiting") &&
              adapter.InnerPost == Fixed("rejected") &&
              adapter.DispatchCount == 1, "reentrant calls fixed");
        string resolved = Text(Get(service));
        Check(resolved == ResolvedBody(
            decision, action, 11, "relic", "Relic_Reentrant"),
            "reentrant later resolved: " + resolved);
    }

    private static byte[] Get(ItemWireV1Service service) =>
        service.Handle("GET", ItemWireV1Protocol.DecisionRoute, null, null);

    private static byte[] Post(ItemWireV1Service service, string decision, string action) =>
        service.Handle("POST", ItemWireV1Protocol.ActionRoute, decision, action);

    private static string Fixed(string status, string suffix = "") =>
        "{\"schema_version\":1,\"protocol\":\"item_probe_v1\",\"version\":\"item_v1\",\"session_nonce\":\"" +
        Nonce + "\",\"surface_ordinal\":1,\"status\":\"" + status + "\"" + suffix + "}";

    private static string Correlated(string status, string decision, string action) =>
        Fixed(status, ",\"decision_id\":\"" + decision + "\",\"action_id\":\"" + action + "\"");

    private static string ResolvedBody(
        string decision, string action, int index, string kind, string key) =>
        Correlated("resolved", decision, action)[..^1] +
        ",\"offer_index\":" + index + ",\"kind\":\"" + kind +
        "\",\"key\":\"" + key + "\",\"result\":\"collected\"}";

    private static (string Decision, string Action) Correlation(string ready)
    {
        using JsonDocument document = JsonDocument.Parse(ready);
        JsonElement root = document.RootElement;
        Check(root.GetProperty("status").GetString() == "ready", "correlation ready");
        return (
            root.GetProperty("decision_id").GetString()!,
            root.GetProperty("legal_actions")[0].GetString()!);
    }

    private static IEnumerable<string> PropertyNames(JsonElement value)
    {
        foreach (JsonProperty property in value.EnumerateObject())
        {
            yield return property.Name;
        }
    }

    private static string Text(byte[] body) => Encoding.UTF8.GetString(body);

    private static string? ReadBoundedLine(TextReader reader, int maximum)
    {
        var builder = new StringBuilder(Math.Min(maximum, 256));
        while (true)
        {
            int value = reader.Read();
            if (value < 0)
            {
                return builder.Length == 0 ? null : builder.ToString();
            }
            if (value == '\n')
            {
                return builder.ToString();
            }
            if (value == '\r' || value > 0x7f || builder.Length >= maximum)
            {
                throw new InvalidDataException("Invalid fixture command.");
            }
            builder.Append((char)value);
        }
    }

    private static FixtureCommand ParseCommand(string line)
    {
        using JsonDocument document = JsonDocument.Parse(line, new JsonDocumentOptions
        {
            AllowTrailingCommas = false,
            CommentHandling = JsonCommentHandling.Disallow,
            MaxDepth = 4,
        });
        JsonElement root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object ||
            !PropertyNames(root).SequenceEqual(new[]
            {
                "method", "route", "decision_id", "action_id",
            }))
        {
            throw new InvalidDataException("Invalid fixture command shape.");
        }
        return new FixtureCommand(
            RequiredString(root.GetProperty("method")),
            RequiredString(root.GetProperty("route")),
            OptionalString(root.GetProperty("decision_id")),
            OptionalString(root.GetProperty("action_id")));
    }

    private static string RequiredString(JsonElement value) =>
        value.ValueKind == JsonValueKind.String && value.GetString() is string result
            ? result
            : throw new InvalidDataException("Invalid fixture string.");

    private static string? OptionalString(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Null => null,
        JsonValueKind.String => value.GetString(),
        _ => throw new InvalidDataException("Invalid fixture optional string."),
    };

    private static void Run(string name, Action action)
    {
        try
        {
            action();
            _checkCount++;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(name + ": " + exception.GetType().Name + ": " +
                exception.Message);
            throw;
        }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    private sealed record FixtureCommand(
        string Method,
        string Route,
        string? DecisionId,
        string? ActionId);

    private sealed class FixtureScenario : IItemV1NativeAdapter
    {
        private readonly string _name;
        private readonly object _run = new();
        private readonly object _player = new();
        private readonly object _screen = new();
        private readonly object _changedScreen = new();
        private readonly object _button = new();
        private readonly object _reward = new();
        private readonly object _model = new();
        private readonly object _held = new();
        private readonly object[] _maximumButtons = NewIdentities();
        private readonly object[] _maximumRewards = NewIdentities();
        private readonly object[] _maximumModels = NewIdentities();
        private readonly object[] _maximumSlotModels = NewIdentities();
        private bool _dispatched;
        private int _pendingReads;

        public FixtureScenario(string name)
        {
            _name = name;
        }

        public int SurfaceCalls { get; private set; }
        public int DispatchCount { get; private set; }
        public int LastActionIndex { get; private set; } = -1;
        public bool SurfaceAfterDispatchIsMissing =>
            _name == "overlay_closed" && _dispatched &&
            CaptureSurface().Status == ItemV1SurfaceStatus.Missing;

        public static bool IsKnown(string value) => value is
            "potion_success" or "relic_success" or "delayed" or "full_belt" or
            "stale" or "uncertain" or "overlay_closed" or "bounds_ready";

        public ItemV1SurfaceCapture CaptureSurface()
        {
            SurfaceCalls++;
            if (_name == "delayed" && SurfaceCalls <= 2)
            {
                return ItemV1SurfaceCapture.Missing();
            }
            if (_name == "overlay_closed" && _dispatched)
            {
                return ItemV1SurfaceCapture.Missing();
            }
            if (_name == "bounds_ready")
            {
                return MaximumSurface(
                    _run, _player, _screen,
                    _maximumButtons, _maximumRewards, _maximumModels,
                    _maximumSlotModels, Dispatch);
            }
            (int index, ItemV1ItemKind kind, string key) = Definition();
            bool full = _name == "full_belt";
            var slots = full
                ? new[] { new ItemV1PotionSlotBinding(_held, "Potion_Held") }
                : new[]
                {
                    new ItemV1PotionSlotBinding(_held, "Potion_Held"),
                    new ItemV1PotionSlotBinding(null, null),
                };
            var offer = new ItemV1NativeOffer(
                index, kind, key, true, false, true, true,
                _button, _reward, _model, () => Dispatch(index));
            object screen = _name == "stale" && SurfaceCalls > 1 ? _changedScreen : _screen;
            return ItemV1SurfaceCapture.Available(
                _run, _player, screen, slots.Length, new[] { offer }, slots);
        }

        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending)
        {
            _pendingReads++;
            if (_name == "bounds_ready")
            {
                int offerPosition = Array.IndexOf(
                    _maximumModels, pending.OfferedModelIdentity);
                if (offerPosition < 0)
                {
                    throw new InvalidOperationException("Unknown maximum offer model.");
                }
                string maximumKey = new string((char)('A' + offerPosition), 128);
                var maximumSlots = new ItemV1PotionSlotBinding[8];
                for (int index = 0; index < maximumSlots.Length; index++)
                {
                    maximumSlots[index] = new ItemV1PotionSlotBinding(
                        _maximumSlotModels[index],
                        new string((char)('a' + index), 128));
                }
                return new ItemV1PendingCapture(
                    pending.RunIdentity,
                    pending.PlayerIdentity,
                    pending.RewardIdentity,
                    pending.OfferedModelIdentity,
                    maximumKey,
                    true,
                    pending.OfferedModelIdentity,
                    maximumKey,
                    maximumSlots.Length,
                    maximumSlots);
            }
            (int _, ItemV1ItemKind kind, string key) = Definition();
            bool resolved = _name != "delayed" || _pendingReads >= 3;
            object? claimed = resolved ? _model : null;
            string? claimedKey = resolved ? key : null;
            ItemV1PotionSlotBinding[] slots;
            if (kind == ItemV1ItemKind.Potion)
            {
                slots = new[]
                {
                    new ItemV1PotionSlotBinding(_held, "Potion_Held"),
                    new ItemV1PotionSlotBinding(resolved ? _model : null,
                        resolved ? key : null),
                };
            }
            else
            {
                slots = new[]
                {
                    new ItemV1PotionSlotBinding(_held, "Potion_Held"),
                    new ItemV1PotionSlotBinding(null, null),
                };
            }
            return new ItemV1PendingCapture(
                pending.RunIdentity,
                pending.PlayerIdentity,
                pending.RewardIdentity,
                pending.OfferedModelIdentity,
                key,
                resolved,
                claimed,
                claimedKey,
                slots.Length,
                slots);
        }

        private void Dispatch(int index)
        {
            DispatchCount++;
            LastActionIndex = index;
            _dispatched = true;
            if (_name == "uncertain")
            {
                throw new InvalidOperationException("SYNTHETIC_DISPATCH_CANARY");
            }
        }

        private (int Index, ItemV1ItemKind Kind, string Key) Definition() => _name switch
        {
            "potion_success" => (3, ItemV1ItemKind.Potion, "Potion_Synthetic"),
            "relic_success" => (7, ItemV1ItemKind.Relic, "Relic_Synthetic"),
            "delayed" => (5, ItemV1ItemKind.Potion, "Potion_Delayed"),
            "full_belt" => (4, ItemV1ItemKind.Potion, "Potion_Full"),
            "stale" => (6, ItemV1ItemKind.Relic, "Relic_Stale"),
            "uncertain" => (8, ItemV1ItemKind.Relic, "Relic_Uncertain"),
            "overlay_closed" => (9, ItemV1ItemKind.Relic, "Relic_Closed"),
            _ => throw new InvalidOperationException("Unknown fixture scenario."),
        };
    }

    private sealed class MaximumAdapter : IItemV1NativeAdapter
    {
        private readonly object _run = new();
        private readonly object _player = new();
        private readonly object _screen = new();
        private readonly object[] _buttons = NewIdentities();
        private readonly object[] _rewards = NewIdentities();
        private readonly object[] _models = NewIdentities();
        private readonly object[] _slotModels = NewIdentities();

        public ItemV1SurfaceCapture CaptureSurface()
        {
            return MaximumSurface(
                _run, _player, _screen, _buttons, _rewards, _models,
                _slotModels, _ => { });
        }

        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) =>
            throw new InvalidOperationException("No maximum fixture action.");
    }

    private sealed class ReentrantAdapter : IItemV1NativeAdapter
    {
        private readonly object _run = new();
        private readonly object _player = new();
        private readonly object _screen = new();
        private readonly object _button = new();
        private readonly object _reward = new();
        private readonly object _model = new();
        private int _pendingReads;

        public ItemWireV1Service? Service { get; set; }
        public string DecisionId { get; set; } = string.Empty;
        public string ActionId { get; set; } = string.Empty;
        public string InnerRead { get; private set; } = string.Empty;
        public string InnerPost { get; private set; } = string.Empty;
        public int DispatchCount { get; private set; }

        public ItemV1SurfaceCapture CaptureSurface()
        {
            var offer = new ItemV1NativeOffer(
                11, ItemV1ItemKind.Relic, "Relic_Reentrant",
                true, false, true, true,
                _button, _reward, _model, Dispatch);
            return ItemV1SurfaceCapture.Available(
                _run, _player, _screen, 0, new[] { offer },
                Array.Empty<ItemV1PotionSlotBinding>());
        }

        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending)
        {
            _pendingReads++;
            bool selected = _pendingReads >= 1;
            return new ItemV1PendingCapture(
                pending.RunIdentity,
                pending.PlayerIdentity,
                pending.RewardIdentity,
                pending.OfferedModelIdentity,
                "Relic_Reentrant",
                selected,
                selected ? pending.OfferedModelIdentity : null,
                selected ? "Relic_Reentrant" : null,
                0,
                Array.Empty<ItemV1PotionSlotBinding>());
        }

        private void Dispatch()
        {
            DispatchCount++;
            ItemWireV1Service service = Service ??
                throw new InvalidOperationException("Missing reentrant service.");
            InnerRead = Text(Get(service));
            InnerPost = Text(Post(service, DecisionId, ActionId));
        }
    }

    private static ItemV1SurfaceCapture MaximumSurface(
        object run,
        object player,
        object screen,
        IReadOnlyList<object> buttons,
        IReadOnlyList<object> rewards,
        IReadOnlyList<object> models,
        IReadOnlyList<object> slotModels,
        Action<int> dispatch)
    {
        var offers = new ItemV1NativeOffer[8];
        for (int index = 0; index < offers.Length; index++)
        {
            int nativeIndex = 248 + index;
            offers[index] = new ItemV1NativeOffer(
                nativeIndex,
                ItemV1ItemKind.Relic,
                new string((char)('A' + index), 128),
                true,
                false,
                true,
                true,
                buttons[index],
                rewards[index],
                models[index],
                () => dispatch(nativeIndex));
        }
        var slots = Enumerable.Range(0, 8)
            .Select(index => new ItemV1PotionSlotBinding(
                slotModels[index], new string((char)('a' + index), 128)))
            .ToArray();
        return ItemV1SurfaceCapture.Available(
            run, player, screen, 8, offers, slots);
    }

    private static object[] NewIdentities() =>
        Enumerable.Range(0, 8).Select(_ => new object()).ToArray();
}
