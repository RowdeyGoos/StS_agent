using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using Sts2AgentBridge.Successors.GenericEventV7;

// Real native fixture controls and observer hooks; preview gates are released
// only after Python receives an actual waiting response.
internal static partial class GenericEventV7NativeIntegrationHost
{
    private static int RunVariableTransform(string scenario)
    {
        var cases = new Dictionary<string, (string Name, int Min, int Max, int Domain)>
        {
            ["V_FIRST"] = ("FIRST_TRANSFORM", 1, 3, 5),
            ["V_ANOTHER"] = ("ANOTHER_TRANSFORM", 2, 4, 6),
            ["V_HELD_OUT"] = ("HELD_OUT_TRANSFORM", 1, 3, 5),
            ["V_INTERMEDIATE"] = ("HELD_OUT_TRANSFORM", 1, 4, 6),
            ["V_MAX"] = ("HELD_OUT_TRANSFORM", 1, 3, 5),
            ["V_EIGHT"] = ("HELD_OUT_TRANSFORM", 2, 8, 9),
            ["V_EIGHT_EARLY"] = ("HELD_OUT_TRANSFORM", 2, 8, 9),
            ["V_MIN_NEGATIVE"] = ("HELD_OUT_TRANSFORM", -1, 3, 5),
            ["V_OPTIONAL"] = ("CLAWS",0,6,6),
            ["V_OPTIONAL_SMALL"] = ("CLAWS",0,6,1),
            ["V_MIN_GT_MAX"] = ("HELD_OUT_TRANSFORM", 4, 3, 5),
        };
        foreach (string name in new[] { "V_DELAYED_PREVIEW", "V_PARTIAL_PREVIEW", "V_FOREIGN_PREVIEW",
            "V_REPLACED_PREVIEW", "V_UNEXPECTED_EARLY", "V_LOST_PREVIEW", "V_DISABLED_ROOT",
            "V_REPLACED_ROOT", "V_RETIRED_ROOT", "V_FAULT_COMMAND", "V_SUBSTITUTE", "V_PARTIAL_EFFECT",
            "V_DELAYED_COMPLETION", "V_DEFERRED_CONFIRM", "V_MIXED", "V_MIXED_BAD_UPGRADE", "V_MANUAL_FALSE", "V_REOPEN_PREVIEW", "V_LATE_TASK_FAULT" })
            cases.Add(name, ("HELD_OUT_TRANSFORM", 1, 4, 6));
        if (!cases.TryGetValue(scenario, out var config)) return 2;
        using var fixture = new Program.TransformFixture(config.Name, config.Max, config.Domain,
            manual: scenario != "V_MANUAL_FALSE", minimum: config.Min,
            delayedPreview: scenario == "V_DELAYED_PREVIEW", partialPreview: scenario == "V_PARTIAL_PREVIEW",
            delayedCompletion: scenario is "V_DELAYED_COMPLETION" or "V_LATE_TASK_FAULT", partialInsertion: scenario == "V_PARTIAL_EFFECT",
            substitute: scenario == "V_SUBSTITUTE", deferredConfirm: scenario == "V_DEFERRED_CONFIRM",eventModel:scenario.StartsWith("V_OPTIONAL",StringComparison.Ordinal)?new MegaCrit.Sts2.Core.Models.AncientEventModel():null);
        if(scenario.StartsWith("V_OPTIONAL",StringComparison.Ordinal))Program.AncientLayout(fixture.Room,fixture.Model);
        fixture.LostPreview = scenario == "V_LOST_PREVIEW";
        fixture.UnexpectedEarlyPreview = scenario == "V_UNEXPECTED_EARLY";
        fixture.FaultCommand = scenario == "V_FAULT_COMMAND";
        fixture.ContinueWithUpgrade = scenario is "V_MIXED" or "V_MIXED_BAD_UPGRADE";
        Program.RetireBeforeChosen(fixture.Room.Layout);
        var baseline = fixture.Player.Deck.Cards.ToArray();
        var baselineKeys = baseline.Select(c => c.Id.Entry).ToArray();
        var baselineLevels = baseline.Select(c => c.CurrentUpgradeLevel).ToArray();
        using var wire = new GenericEventV7WireService(new string('e', 32), fixture.Session);
        bool changed = false, releasedCompletion = false;
        for (int count = 0; count < 2200; count++)
        {
            string? line = ReadLineBounded();
            if (line is null) return 0;
            using var document = JsonDocument.Parse(line);
            var request = document.RootElement;
            if (!request.EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "method", "route", "body" })) return 3;
            byte[]? body = request.GetProperty("body").ValueKind == JsonValueKind.Null ? null :
                Convert.FromBase64String(request.GetProperty("body").GetString()!);
            byte[] response = CheckedHandle(wire,request.GetProperty("method").GetString(), request.GetProperty("route").GetString(), body);
            var remaining = fixture.Player.Deck.Cards.ToArray();
            var known = baseline.Concat(fixture.FinalCards).ToArray();
            Console.WriteLine(JsonSerializer.Serialize(new {
                body = Convert.ToBase64String(response), event_type = fixture.Model.GetType().Name,
                upgraded_cards = baseline.Count(c => c.CurrentUpgradeLevel == 1),
                map_open = fixture.Map.IsOpen, overlay_count = fixture.Overlays.ScreenCount,
                chosen_calls = fixture.OptionCalls, select_calls = fixture.SelectCalls,
                confirm_calls = fixture.ConfirmCalls, preview_calls = fixture.PreviewCalls,
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
                preview_holder_count = fixture.Before.Children.Count,
                selected_originals = fixture.Selected.Select(c => Array.FindIndex(baseline, original => ReferenceEquals(original, c))).ToArray(),
            }));
            using var reply = JsonDocument.Parse(response);
            var parent = reply.RootElement.GetProperty("parent");
            var payload = reply.RootElement.GetProperty("payload");
            bool decision = reply.RootElement.GetProperty("kind").GetString() == "decision";
            if (decision && parent.ValueKind == JsonValueKind.Object && parent.GetProperty("status").GetString() == "child" &&
                payload.ValueKind == JsonValueKind.Object && payload.GetProperty("status").GetString() == "waiting")
            {
                if (fixture.HasPendingPreview && scenario is "V_DELAYED_PREVIEW" or "V_PARTIAL_PREVIEW") fixture.AdvancePreview();
                if (scenario == "V_PARTIAL_EFFECT" && fixture.HasPendingInsertion) fixture.AdvanceInsertion();
                if (scenario == "V_DEFERRED_CONFIRM" && fixture.Confirms.Count > 0) fixture.AdvanceConfirm();
                if (scenario is "V_DELAYED_COMPLETION" or "V_LATE_TASK_FAULT" && fixture.ConfirmCalls == 1 && !releasedCompletion)
                { releasedCompletion = true; if (scenario == "V_LATE_TASK_FAULT") fixture.CompletionGate.SetException(new InvalidOperationException("late")); else fixture.CompletionGate.SetResult(); }
            }
            if (!changed && decision && payload.ValueKind == JsonValueKind.Object &&
                payload.GetProperty("status").GetString() == "ready")
            {
                string? phase = payload.GetProperty("phase").GetString();
                if (phase == "selecting" && payload.GetProperty("legal_actions").EnumerateArray().Any(v => v.GetString() == "preview") &&
                    scenario is "V_DISABLED_ROOT" or "V_REPLACED_ROOT")
                {
                    changed = true;
                    if (scenario == "V_DISABLED_ROOT") fixture.RootConfirmButton.IsEnabled = false;
                    else fixture.Screen.Bind("Confirm", new NConfirmButton());
                }
                if (phase == "preview" && scenario is "V_FOREIGN_PREVIEW" or "V_REPLACED_PREVIEW")
                {
                    changed = true;
                    var holder = (NPreviewCardHolder)fixture.Before.Children[0];
                    if (scenario == "V_FOREIGN_PREVIEW") holder.CardNode.Model = fixture.Cards[0];
                    else fixture.Before.Children[0] = new NPreviewCardHolder { CardNode = holder.CardNode };
                }
                if (phase == "preview" && scenario == "V_REOPEN_PREVIEW")
                { changed = true; fixture.Preview.Visible = false; }
                if (phase == "preview" && scenario == "V_MIXED_BAD_UPGRADE" && parent.GetProperty("child_episodes").GetInt32() == 2)
                { changed = true; fixture.UpgradeGrid.CurrentlyDisplayedCardHolders[0].CardModel = fixture.NewCard("Foreign"); }
            }
            if (!changed && scenario == "V_RETIRED_ROOT" && body is not null)
            {
                using var action = JsonDocument.Parse(body);
                if (action.RootElement.GetProperty("action_id").GetString() == "preview")
                { changed = true; fixture.RootConfirmButton.InstanceValid = false; }
            }
            if (body is not null) Array.Clear(body);
            Array.Clear(response);
        }
        return 4;
    }
}
