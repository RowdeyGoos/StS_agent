using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Successors.GenericEventV3;

// Full production hooks/native card adapter/core/wire composition against inert
// target stubs. Python drives every native control; no fixture Finish shortcut.
internal static class GenericEventV3NativeIntegrationHost
{
    private static readonly Dictionary<string, (string Name, int Min, int Max, int Domain, bool Creation, bool Completion)> RemovalCases = new()
    {
        ["R_FIRST"] = ("FIRST_REMOVAL", 2, 2, 5, false, false),
        ["R_ANOTHER"] = ("ANOTHER_REMOVAL", 1, 3, 5, false, false),
        ["R_HELD_OUT"] = ("HELD_OUT_REMOVAL", 1, 3, 5, false, false),
        ["R_VARIABLE_TWO"] = ("HELD_OUT_REMOVAL", 1, 3, 5, false, false),
        ["R_EIGHT"] = ("HELD_OUT_REMOVAL", 8, 8, 9, false, false),
        ["R_DELAYED_CREATION"] = ("HELD_OUT_REMOVAL", 2, 2, 5, true, false),
        ["R_DELAYED_COMPLETION"] = ("HELD_OUT_REMOVAL", 2, 2, 5, false, true),
    };
    private static readonly Dictionary<string, (string Name, int Min, int Max, int Domain, bool Manual, bool Sorted, bool Creation, bool Partial, bool Completion)> RewardCases = new()
    {
        ["A_FIRST"] = ("FIRST_REWARD", 2, 2, 5, false, false, false, false, false),
        ["A_ANOTHER"] = ("ANOTHER_REWARD", 1, 3, 5, true, false, false, false, false),
        ["A_HELD_OUT"] = ("HELD_OUT_REWARD", 1, 3, 5, false, true, false, false, false),
        ["A_EXPLICIT_FIXED"] = ("HELD_OUT_REWARD", 2, 2, 5, true, false, false, false, false),
        ["A_EXPLICIT_MAX"] = ("HELD_OUT_REWARD", 1, 3, 5, true, false, false, false, false),
        ["A_AUTO_EIGHT"] = ("HELD_OUT_REWARD", 8, 8, 9, false, true, false, false, false),
        ["A_EXPLICIT_EIGHT"] = ("HELD_OUT_REWARD", 8, 8, 9, true, false, false, false, false),
        ["A_DELAYED_CREATION"] = ("HELD_OUT_REWARD", 2, 2, 5, false, false, true, false, false),
        ["A_PARTIAL"] = ("HELD_OUT_REWARD", 2, 2, 5, false, false, false, true, true),
        ["A_DELAYED_COMPLETION"] = ("HELD_OUT_REWARD", 2, 2, 5, true, false, false, false, true),
    };
    private static int Main(string[] args)
    {
        if (args.Length != 1) return 2;
        bool removing = RemovalCases.TryGetValue(args[0], out var config);
        bool adding = RewardCases.TryGetValue(args[0], out var rewardConfig);
        if (!removing && !adding && !new[] { "FIRST_EVENT", "ANOTHER_EVENT", "HELD_OUT_EVENT", "DELAYED" }.Contains(args[0])) return 2;
        var upgrade = removing || adding ? null : new Program.Fixture(args[0], delayed: args[0] == "DELAYED");
        var removal = removing ? new Program.RemovalFixture(config.Name, config.Min, config.Max, config.Domain,
            delayedCreation: config.Creation, delayedCompletion: config.Completion) : null;
        var reward = adding ? new Program.RewardFixture(rewardConfig.Name, rewardConfig.Min, rewardConfig.Max, rewardConfig.Domain,
            manual: rewardConfig.Manual, sortedOffers: rewardConfig.Sorted, delayedCreation: rewardConfig.Creation,
            partialAdd: rewardConfig.Partial, delayedCompletion: rewardConfig.Completion) : null;
        using var fixture = (IDisposable?)upgrade ?? (IDisposable?)removal ?? reward!;
        var session = upgrade?.Session ?? removal?.Session ?? reward!.Session;
        var player = upgrade?.Player ?? removal?.Player ?? reward!.Player;
        var model = upgrade?.Model ?? removal?.Model ?? reward!.Model;
        var map = upgrade?.Map ?? removal?.Map ?? reward!.Map;
        var overlays = upgrade?.Overlays ?? removal?.Overlays ?? reward!.Overlays;
        var room = upgrade?.Room ?? removal?.Room ?? reward!.Room;
        var dispatchedButton = room.Layout.OptionButtons[0];
        bool buttonRetired = false;
        var baseline = player.Deck.Cards.ToArray();
        var baselineKeys = baseline.Select(c => c.Id.Entry).ToArray();
        var baselineLevels = baseline.Select(c => c.CurrentUpgradeLevel).ToArray();
        using var wire = new GenericEventV3WireService(new string(adding ? 'c' : removing ? 'b' : 'a', 32), session);
        bool releasedCreation = false, releasedCompletion = false, releasedAddition = false;
        for (int count = 0; count < 2200; count++)
        {
            string? line = ReadLineBounded();
            if (line is null) return 0;
            using var document = JsonDocument.Parse(line);
            var request = document.RootElement;
            if (!request.EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "method", "route", "body" })) return 3;
            byte[]? body = request.GetProperty("body").ValueKind == JsonValueKind.Null ? null :
                Convert.FromBase64String(request.GetProperty("body").GetString()!);
            byte[] response = wire.Handle(request.GetProperty("method").GetString(), request.GetProperty("route").GetString(), body);
            // Model ClearOptions + the following Godot free before the next host read.
            if (!buttonRetired && request.GetProperty("method").GetString() == "POST")
            {
                room.Layout.OptionButtons.Remove(dispatchedButton);
                dispatchedButton.InstanceValid = false;
                buttonRetired = true;
            }
            var remaining = player.Deck.Cards.ToArray();
            var offers = reward?.OfferCards ?? Array.Empty<CardModel>();
            var displayed = reward?.DisplayedOffers ?? Array.Empty<CardModel>();
            var allOriginals = baseline.Concat(offers).ToArray();
            Console.WriteLine(JsonSerializer.Serialize(new {
                body = Convert.ToBase64String(response), event_type = model.GetType().Name,
                upgraded_cards = baseline.Count(c => c.CurrentUpgradeLevel == 1),
                map_open = map.IsOpen, overlay_count = overlays.ScreenCount,
                chosen_calls = upgrade?.OptionCalls ?? removal?.OptionCalls ?? reward!.OptionCalls,
                select_calls = upgrade?.SelectCalls ?? removal?.SelectCalls ?? reward!.SelectCalls,
                confirm_calls = upgrade?.ConfirmCalls ?? removal?.ConfirmCalls ?? reward!.ConfirmCalls,
                preview_calls = removal?.PreviewCalls ?? 0,
                baseline_keys = baselineKeys, baseline_levels = baselineLevels,
                remaining_originals = remaining.Select(c => Array.FindIndex(baseline, original => ReferenceEquals(original, c))).ToArray(),
                remaining_keys = remaining.Select(c => c.Id.Entry).ToArray(),
                remaining_levels = remaining.Select(c => c.CurrentUpgradeLevel).ToArray(),
                offer_keys = offers.Select(c => c.Id.Entry).ToArray(), offer_levels = offers.Select(c => c.CurrentUpgradeLevel).ToArray(),
                slot_offer_indices = displayed.Select(c => Array.FindIndex(offers, original => ReferenceEquals(original, c))).ToArray(),
                deck_originals = remaining.Select(c => Array.FindIndex(allOriginals, original => ReferenceEquals(original, c))).ToArray(),
            }));
            using var reply = JsonDocument.Parse(response);
            var parent = reply.RootElement.GetProperty("parent");
            if (!releasedCreation && parent.ValueKind == JsonValueKind.Object && parent.GetProperty("status").GetString() == "waiting")
            {
                if (upgrade is not null && args[0] == "DELAYED") { releasedCreation = true; upgrade.Gate.SetResult(); }
                if (removal is not null && config.Creation) { releasedCreation = true; removal.CreationGate.SetResult(); }
                if (reward is not null && rewardConfig.Creation) { releasedCreation = true; reward.CreationGate.SetResult(); }
            }
            var payload = reply.RootElement.GetProperty("payload");
            if (removal is not null && config.Completion && !releasedCompletion &&
                parent.ValueKind == JsonValueKind.Object && parent.GetProperty("status").GetString() == "child" &&
                payload.ValueKind == JsonValueKind.Object && payload.GetProperty("status").GetString() == "waiting")
            { releasedCompletion = true; removal.CompletionGate.SetResult(); }
            if (reward is not null && parent.ValueKind == JsonValueKind.Object && parent.GetProperty("status").GetString() == "child" &&
                payload.ValueKind == JsonValueKind.Object && payload.GetProperty("status").GetString() == "waiting")
            {
                if (rewardConfig.Partial && !releasedAddition && remaining.Length > baseline.Length)
                { releasedAddition = true; reward.AdditionGate.SetResult(); }
                else if (rewardConfig.Completion && !releasedCompletion)
                { releasedCompletion = true; reward.CompletionGate.SetResult(); }
            }
            if (body is not null) Array.Clear(body);
            Array.Clear(response);
        }
        return 4;
    }
    private static string? ReadLineBounded()
    {
        var buffer = new char[8192]; int count = 0;
        while (true)
        {
            int c = Console.Read();
            if (c < 0) return count == 0 ? null : throw new InvalidOperationException("Truncated request.");
            if (c == '\n') return new string(buffer, 0, count);
            if (count == buffer.Length) throw new InvalidOperationException("Oversized request.");
            buffer[count++] = (char)c;
        }
    }
}
