using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using Sts2AgentBridge.Successors.GenericEventV5;

internal static partial class GenericEventV5NativeIntegrationHost
{
    private static int RunTransform(string scenario)
    {
        var cases = new Dictionary<string, (string Name, int Count, int Domain, bool Manual, int[]? Batches)>
        {
            ["T_FIRST"] = ("FIRST_TRANSFORM", 1, 4, false, null),
            ["T_ANOTHER"] = ("ANOTHER_TRANSFORM", 2, 5, true, null),
            ["T_HELD_OUT"] = ("HELD_OUT_TRANSFORM", 2, 5, false, null),
            ["T_EIGHT"] = ("HELD_OUT_TRANSFORM", 8, 9, true, null),
            ["T_SINGLETONS"] = ("HELD_OUT_TRANSFORM", 2, 5, false, new[] { 1, 1 }),
            ["T_MIXED_BATCHES"] = ("HELD_OUT_TRANSFORM", 3, 5, true, new[] { 1, 2 }),
        };
        string[] pairCases = { "T_SUBSTITUTE", "T_PARTIAL", "T_DELAYED_CREATION", "T_DELAYED_COMPLETION",
            "T_DEFERRED_CONFIRM", "T_FOREIGN_PREVIEW", "T_REPLACED_PREVIEW", "T_NOTIFICATION",
            "T_BAD_RESULT", "T_CALLBACK_FAULT", "T_COMMAND_FAULT", "T_OWNER_NOTIFICATION", "T_RUN_NOTIFICATION" };
        foreach (string name in pairCases) cases.Add(name, ("HELD_OUT_TRANSFORM", 2, 5, false, null));
        cases.Add("T_MIXED", ("HELD_OUT_TRANSFORM", 8, 9, true, null));
        cases.Add("T_MIXED_BAD_UPGRADE", ("HELD_OUT_TRANSFORM", 8, 9, true, null));
        if (!cases.TryGetValue(scenario, out var config)) return 2;
        using var fixture = new Program.TransformFixture(config.Name, config.Count, config.Domain,
            manual: config.Manual, batchSizes: config.Batches,
            delayedCreation: scenario == "T_DELAYED_CREATION", delayedCompletion: scenario == "T_DELAYED_COMPLETION",
            partialInsertion: scenario == "T_PARTIAL", substitute: scenario is "T_SUBSTITUTE" or "T_MIXED" or "T_MIXED_BAD_UPGRADE",
            deferredConfirm: scenario == "T_DEFERRED_CONFIRM");
        if (scenario is "T_MIXED" or "T_MIXED_BAD_UPGRADE")
        { fixture.RepeatTransforms = 1; fixture.ContinueWithUpgrade = true; }
        if (scenario == "T_NOTIFICATION") fixture.Player.Deck.CardAdded = _ => fixture.Player.Deck.Cards.Add(fixture.NewCard("Extra"));
        if (scenario == "T_OWNER_NOTIFICATION") fixture.Player.Deck.CardAdded = card => card.Owner = new MegaCrit.Sts2.Core.Entities.Players.Player();
        if (scenario == "T_RUN_NOTIFICATION") fixture.Player.Deck.CardAdded = card => card.RunOverride = new MegaCrit.Sts2.Core.Runs.RunState();
        if (scenario == "T_BAD_RESULT") fixture.Results = rows => { rows.Reverse(); return rows; };
        if (scenario == "T_CALLBACK_FAULT") fixture.FaultCallback = true;
        if (scenario == "T_COMMAND_FAULT") fixture.FaultCommand = true;
        Program.RetireBeforeChosen(fixture.Room.Layout);
        var baseline = fixture.Player.Deck.Cards.ToArray();
        var baselineKeys = baseline.Select(c => c.Id.Entry).ToArray();
        var baselineLevels = baseline.Select(c => c.CurrentUpgradeLevel).ToArray();
        using var wire = new GenericEventV5WireService(new string('e', 32), fixture.Session);
        bool releasedCreation = false, releasedCompletion = false, mutatedPreview = false;
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
            var remaining = fixture.Player.Deck.Cards.ToArray();
            var known = baseline.Concat(fixture.FinalCards).ToArray();
            Console.WriteLine(JsonSerializer.Serialize(new {
                body = Convert.ToBase64String(response), event_type = fixture.Model.GetType().Name,
                upgraded_cards = baseline.Count(c => c.CurrentUpgradeLevel == 1),
                map_open = fixture.Map.IsOpen, overlay_count = fixture.Overlays.ScreenCount,
                chosen_calls = fixture.OptionCalls, select_calls = fixture.SelectCalls,
                confirm_calls = fixture.ConfirmCalls, preview_calls = 0,
                baseline_keys = baselineKeys, baseline_levels = baselineLevels,
                remaining_originals = remaining.Select(c => Array.FindIndex(baseline, original => ReferenceEquals(original, c))).ToArray(),
                remaining_keys = remaining.Select(c => c.Id.Entry).ToArray(),
                remaining_levels = remaining.Select(c => c.CurrentUpgradeLevel).ToArray(),
                offer_keys = Array.Empty<string>(), offer_levels = Array.Empty<int>(), slot_offer_indices = Array.Empty<int>(),
                deck_originals = remaining.Select(c => Array.FindIndex(known, original => ReferenceEquals(original, c))).ToArray(),
                multi_completion_valid = false, derived_hitboxes_retained = false,
                transform_originals = fixture.Originals.Select(c => Array.FindIndex(known, original => ReferenceEquals(original, c))).ToArray(),
                transform_final_keys = fixture.FinalCards.Select(c => c.Id.Entry).ToArray(),
                transform_final_levels = fixture.FinalCards.Select(c => c.CurrentUpgradeLevel).ToArray(),
                transform_batches = fixture.CompletedBatches, transform_completion_valid = fixture.CompletionValid,
            }));
            using var reply = JsonDocument.Parse(response);
            var parent = reply.RootElement.GetProperty("parent");
            var payload = reply.RootElement.GetProperty("payload");
            if (parent.ValueKind == JsonValueKind.Object && parent.GetProperty("status").GetString() == "waiting" &&
                scenario == "T_DELAYED_CREATION" && !releasedCreation)
            { releasedCreation = true; fixture.CreationGate.SetResult(); }
            if (parent.ValueKind == JsonValueKind.Object && parent.GetProperty("status").GetString() == "child" &&
                payload.ValueKind == JsonValueKind.Object && payload.GetProperty("status").GetString() == "waiting")
            {
                // Each release follows a real waiting response. In particular the final
                // insertion remains pending until the controller has seen the full deck.
                if (scenario == "T_PARTIAL" && fixture.HasPendingInsertion) fixture.AdvanceInsertion();
                if (scenario == "T_DEFERRED_CONFIRM" && fixture.Confirms.Count > 0) fixture.AdvanceConfirm();
                if (scenario == "T_DELAYED_COMPLETION" && fixture.ConfirmCalls == 1 && !releasedCompletion)
                { releasedCompletion = true; fixture.CompletionGate.SetResult(); }
            }
            if (!mutatedPreview && scenario is "T_FOREIGN_PREVIEW" or "T_REPLACED_PREVIEW" &&
                reply.RootElement.GetProperty("kind").GetString() == "decision" && payload.ValueKind == JsonValueKind.Object &&
                payload.GetProperty("phase").GetString() == "preview")
            {
                mutatedPreview = true;
                var holder = (NPreviewCardHolder)fixture.Before.Children[0];
                if (scenario == "T_FOREIGN_PREVIEW") holder.CardNode.Model = fixture.Cards[0];
                else fixture.Before.Children[0] = new NPreviewCardHolder { CardNode = holder.CardNode };
            }
            if (!mutatedPreview && scenario == "T_MIXED_BAD_UPGRADE" &&
                parent.ValueKind == JsonValueKind.Object && parent.GetProperty("child_episodes").GetInt32() == 3 &&
                payload.ValueKind == JsonValueKind.Object && payload.GetProperty("phase").GetString() == "preview")
            {
                mutatedPreview = true;
                fixture.UpgradeGrid.CurrentlyDisplayedCardHolders[0].CardModel = fixture.NewCard("Foreign");
            }
            if (body is not null) Array.Clear(body);
            Array.Clear(response);
        }
        return 4;
    }
}
