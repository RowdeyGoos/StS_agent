using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using Sts2AgentBridge.Successors.GenericEventV7;

// Full production hooks/native card adapter/core/wire composition against inert
// target stubs. Python drives every native control; no fixture Finish shortcut.
internal static partial class GenericEventV7NativeIntegrationHost
{
    // Exercise the same response boundary as NativeBridgeModule for every real
    // adapter/core/wire exchange, including pending and rejected action paths.
    private static byte[] CheckedHandle(GenericEventV7WireService wire,string? method,string? route,byte[]? body) {
        using var request=body is null?null:JsonDocument.Parse(body);
        var kind=method=="GET"?Sts2AgentBridge.Successors.GenericEventReleaseV10.GenericEventTransportRoute.DecisionGet:
            request!.RootElement.GetProperty("child").ValueKind==JsonValueKind.Null?
                Sts2AgentBridge.Successors.GenericEventReleaseV10.GenericEventTransportRoute.ParentPost:
                Sts2AgentBridge.Successors.GenericEventReleaseV10.GenericEventTransportRoute.ChildPost;
        var response=wire.Handle(method,route,body);
        using var document=JsonDocument.Parse(response);var root=document.RootElement;
        var classification=Sts2AgentBridge.Successors.GenericEventReleaseV10.GenericEventTerminalClassifier.Classify(kind,
            Sts2AgentBridge.Successors.GenericEventReleaseV10.GenericEventReleaseSelection.Generic,root.GetProperty("session_nonce").GetString()!,200,response);
        if(classification==Sts2AgentBridge.Successors.GenericEventReleaseV10.TerminalClassification.Invalid)
            throw new InvalidOperationException("Production event response classifier rejected the native wire response.");
        // A resolved child still belongs to its parent. Only parent completion or
        // a failure can stop/release this module; waiting must never do so.
        string envelope=root.GetProperty("kind").GetString()!;
        JsonElement value=envelope=="decision" && root.GetProperty("child").ValueKind==JsonValueKind.Null
            ?root.GetProperty("parent"):root.GetProperty("payload");
        string? status=value.TryGetProperty("outcome",out var outcome)?outcome.GetString():
            value.TryGetProperty("status",out var state)?state.GetString():null;
        bool terminal=envelope=="error" || status is "complete" or "unsupported" or "uncertain" or "rejected" or "stale_decision" or "illegal_action" or "budget_exhausted";
        if((classification==Sts2AgentBridge.Successors.GenericEventReleaseV10.TerminalClassification.Terminal)!=terminal)
            throw new InvalidOperationException("Production event terminal ownership mismatch.");
        return response;
    }
    private sealed class DerivedRewardHitbox : NClickableControl { }
    private static readonly Dictionary<string, (string Name, int Min, int Max, int Domain, bool Creation, bool Completion)> RemovalCases = new()
    {
        ["ENCHANT_MULTI_TWO"] = ("FIRST_REMOVAL", 2, 2, 20, false, false),
        ["ENCHANT_MULTI_EIGHT"] = ("HELD_OUT_REMOVAL", 8, 8, 20, false, false),
        ["R_POST_ADD"] = ("FIRST_REMOVAL", 2, 2, 5, false, false),
        ["R_POST_ADD_DELAY"] = ("FIRST_REMOVAL", 2, 2, 5, false, true),
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
        ["A_DERIVED"] = ("HELD_OUT_REWARD", 2, 2, 5, false, false, false, false, false),
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
    private static readonly Dictionary<string, (string Name, int Count, int Domain, bool Manual, bool Creation, bool Completion, bool Click, bool Preview)> MultiCases = new()
    {
        ["U_PRE_ADD"] = ("TRIAL_MERCHANT_INNOCENT", 2, 5, false, false, false, false, false),
        ["U_ALLOCATED"] = ("HELD_OUT_MULTI", 2, 20, false, false, false, true, false),
        ["U_FIRST"] = ("FIRST_MULTI", 2, 5, false, false, false, false, false),
        ["U_ANOTHER"] = ("ANOTHER_MULTI", 2, 5, true, false, false, false, false),
        ["U_HELD_OUT"] = ("HELD_OUT_MULTI", 2, 5, false, false, false, false, false),
        ["U_EIGHT"] = ("HELD_OUT_MULTI", 8, 9, true, false, false, false, false),
        ["U_DELAYED_CREATION"] = ("HELD_OUT_MULTI", 2, 5, false, true, false, false, false),
        ["U_DELAYED_COMPLETION"] = ("HELD_OUT_MULTI", 2, 5, false, false, true, false, false),
        ["U_DEFERRED"] = ("HELD_OUT_MULTI", 2, 5, false, false, false, true, false),
        ["U_FOREIGN_PREVIEW"] = ("HELD_OUT_MULTI", 2, 5, false, false, false, false, false),
        ["U_REPLACED_PREVIEW"] = ("HELD_OUT_MULTI", 2, 5, false, false, false, false, false),
        ["U_PARTIAL_EFFECT"] = ("HELD_OUT_MULTI", 2, 5, false, false, false, false, false),
        ["U_PARTIAL"] = ("HELD_OUT_MULTI", 2, 5, false, false, false, false, true),
    };
    private static int Main(string[] args)
    {
        if (args.Length != 1) return 2;
        if (args[0].StartsWith("P_", StringComparison.Ordinal)) return RunRepeatedPage(args[0]);
        if (args[0].StartsWith("V_", StringComparison.Ordinal)) return RunVariableTransform(args[0]);
        if (args[0].StartsWith("T_", StringComparison.Ordinal)) return RunTransform(args[0]);
        if (args[0].StartsWith("CRS_", StringComparison.Ordinal)) return RunCardRewardSet(args[0]);
        if (args[0].StartsWith("CR_", StringComparison.Ordinal)) return RunCardReward(args[0]);
        if (args[0].StartsWith("I_", StringComparison.Ordinal)) return RunItem(args[0]);
        bool enchanting = args[0].StartsWith("ENCHANT_", StringComparison.Ordinal);
        bool multiUpgrading = MultiCases.TryGetValue(args[0], out var multiConfig);
        bool removing = RemovalCases.TryGetValue(args[0], out var config);
        bool adding = RewardCases.TryGetValue(args[0], out var rewardConfig);
        if (!enchanting && !multiUpgrading && !removing && !adding && !new[] { "FIRST_EVENT", "ANOTHER_EVENT", "HELD_OUT_EVENT", "DELAYED", "ALLOCATED_UPGRADE" }.Contains(args[0])) return 2;
        var upgrade = removing || adding || multiUpgrading ? null : new Program.Fixture(args[0], delayed: args[0] == "DELAYED", domain: args[0] is "ALLOCATED_UPGRADE" or "ENCHANT_ALLOCATED" ? 20 : 2, enchant: enchanting, effectDelayed: args[0] == "ENCHANT_DELAY");
        if (args[0] == "ENCHANT_WRONG_EFFECT") upgrade!.AfterEffect = () => upgrade.Cards[0].Enchantment!.Amount++;
        var removal = removing ? new Program.RemovalFixture(config.Name, config.Min, config.Max, config.Domain,
            delayedCreation: config.Creation, delayedCompletion: config.Completion,enchant:enchanting) : null;
        var reward = adding ? new Program.RewardFixture(rewardConfig.Name, rewardConfig.Min, rewardConfig.Max, rewardConfig.Domain,
            manual: rewardConfig.Manual, sortedOffers: rewardConfig.Sorted, delayedCreation: rewardConfig.Creation,
            partialAdd: rewardConfig.Partial, delayedCompletion: rewardConfig.Completion) : null;
        NClickableControl[]? retainedHitboxes = null;
        if (reward is not null && args[0] == "A_DERIVED")
            reward.BeforeReturn = () => {
                var holders = reward.Grid.CurrentlyDisplayedCardHolders;
                foreach (var holder in holders) holder.Hitbox = new DerivedRewardHitbox();
                retainedHitboxes = holders.Select(h => h.Hitbox).ToArray();
            };
        var multi = multiUpgrading ? new Program.MultiUpgradeFixture(multiConfig.Name, multiConfig.Count, multiConfig.Domain,
            manual: multiConfig.Manual, delayedCreation: multiConfig.Creation, delayedCompletion: multiConfig.Completion,
            deferredClick: multiConfig.Click, deferredPreview: multiConfig.Preview) : null;
        if (multi is not null && args[0] == "U_PARTIAL_EFFECT") multi.PartialEffect = true;
        if (args[0] is "ALLOCATED_UPGRADE" or "U_ALLOCATED") Program.LimitUpgradeViewport();
        using var fixture = (IDisposable?)upgrade ?? (IDisposable?)removal ?? (IDisposable?)reward ?? multi!;
        var session = upgrade?.Session ?? removal?.Session ?? reward?.Session ?? multi!.Session;
        var player = upgrade?.Player ?? removal?.Player ?? reward?.Player ?? multi!.Player;
        var model = upgrade?.Model ?? removal?.Model ?? reward?.Model ?? multi!.Model;
        var map = upgrade?.Map ?? removal?.Map ?? reward?.Map ?? multi!.Map;
        var overlays = upgrade?.Overlays ?? removal?.Overlays ?? reward?.Overlays ?? multi!.Overlays;
        if (args[0] is "ENCHANT_PRE_ADD" or "ENCHANT_POST_ADD" or "ENCHANT_PRE_ADD_OWNER" or "U_PRE_ADD") {
            var added=Program.AppendBeforeSelector((upgrade?.Room ?? multi!.Room).Layout,player,
                multi is null?"DECAY":"SHAME");
            if(multi is not null)multi.PreSelectorAdditions=new[]{added};
            if(args[0]=="ENCHANT_POST_ADD") upgrade!.AfterEffect=()=>player.Deck.Cards.Add(new CardModel {Owner=player});
            if(args[0]=="ENCHANT_PRE_ADD_OWNER") upgrade!.AfterEffect=()=>added.Owner=new MegaCrit.Sts2.Core.Entities.Players.Player();
        }
        if (args[0] is "R_POST_ADD" or "R_POST_ADD_DELAY") Program.AppendAfterRemoval(removal!);
        Program.RetireBeforeChosen((upgrade?.Room ?? removal?.Room ?? reward?.Room ?? multi!.Room).Layout);
        var baseline = player.Deck.Cards.ToArray();
        var baselineKeys = baseline.Select(c => c.Id.Entry).ToArray();
        var baselineLevels = baseline.Select(c => c.CurrentUpgradeLevel).ToArray();
        using var wire = new GenericEventV7WireService(new string(multiUpgrading ? 'd' : adding ? 'c' : removing ? 'b' : 'a', 32), session);
        bool releasedCreation = false, releasedCompletion = false, releasedAddition = false, mutatedPreview = false;
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
            var remaining = player.Deck.Cards.ToArray();
            var offers = reward?.OfferCards ?? Array.Empty<CardModel>();
            var displayed = reward?.DisplayedOffers ?? Array.Empty<CardModel>();
            var allOriginals = baseline.Concat(offers).ToArray();
            Console.WriteLine(JsonSerializer.Serialize(new {
                body = Convert.ToBase64String(response), event_type = model.GetType().Name,
                upgraded_cards = baseline.Count(c => c.CurrentUpgradeLevel == 1),
                map_open = map.IsOpen, overlay_count = overlays.ScreenCount,
                chosen_calls = upgrade?.OptionCalls ?? removal?.OptionCalls ?? reward?.OptionCalls ?? multi!.OptionCalls,
                select_calls = upgrade?.SelectCalls ?? removal?.SelectCalls ?? reward?.SelectCalls ?? multi!.SelectCalls,
                confirm_calls = upgrade?.ConfirmCalls ?? removal?.ConfirmCalls ?? reward?.ConfirmCalls ?? multi!.ConfirmCalls,
                preview_calls = removal?.PreviewCalls ?? 0,
                baseline_keys = baselineKeys, baseline_levels = baselineLevels,
                remaining_originals = remaining.Select(c => Array.FindIndex(baseline, original => ReferenceEquals(original, c))).ToArray(),
                remaining_keys = remaining.Select(c => c.Id.Entry).ToArray(),
                remaining_levels = remaining.Select(c => c.CurrentUpgradeLevel).ToArray(),
                offer_keys = offers.Select(c => c.Id.Entry).ToArray(), offer_levels = offers.Select(c => c.CurrentUpgradeLevel).ToArray(),
                slot_offer_indices = displayed.Select(c => Array.FindIndex(offers, original => ReferenceEquals(original, c))).ToArray(),
                deck_originals = remaining.Select(c => Array.FindIndex(allOriginals, original => ReferenceEquals(original, c))).ToArray(),
                multi_completion_valid = multi?.CompletionValid ?? false,
                derived_hitboxes_retained = retainedHitboxes is not null && reward!.Grid.CurrentlyDisplayedCardHolders.Select(h => h.Hitbox).SequenceEqual(retainedHitboxes),
                enchantment_keys = remaining.Select(c => c.Enchantment?.Id.Entry).ToArray(),
                enchantment_amounts = remaining.Select(c => c.Enchantment?.Amount).ToArray(),
            }));
            using var reply = JsonDocument.Parse(response);
            var parent = reply.RootElement.GetProperty("parent");
            if (!releasedCreation && parent.ValueKind == JsonValueKind.Object && parent.GetProperty("status").GetString() == "waiting")
            {
                if (multi is not null && multiConfig.Creation) { releasedCreation = true; multi.CreationGate.SetResult(); }
                if (upgrade is not null && args[0] == "DELAYED") { releasedCreation = true; upgrade.Gate.SetResult(); }
                if (removal is not null && config.Creation) { releasedCreation = true; removal.CreationGate.SetResult(); }
                if (reward is not null && rewardConfig.Creation) { releasedCreation = true; reward.CreationGate.SetResult(); }
            }
            var payload = reply.RootElement.GetProperty("payload");
            if (args[0] == "ENCHANT_DELAY" && !releasedCompletion && payload.ValueKind == JsonValueKind.Object &&
                payload.TryGetProperty("status",out var status) && status.GetString() == "waiting" && upgrade!.ConfirmCalls == 1)
            {releasedCompletion=true;upgrade.Gate.SetResult();}
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
            if (multi is not null && parent.ValueKind == JsonValueKind.Object && parent.GetProperty("status").GetString() == "child" &&
                payload.ValueKind == JsonValueKind.Object && payload.GetProperty("status").GetString() == "waiting")
            {
                if (args[0] == "U_PARTIAL_EFFECT" && multi.ConfirmCalls == 1 && !releasedAddition)
                { releasedAddition = true; multi.AdditionGate.SetResult(); }
                if (multiConfig.Click && multi.ConfirmCalls == 0) multi.AdvanceClick();
                if (multiConfig.Preview && multi.SelectCalls == multiConfig.Count && multi.ConfirmCalls == 0) multi.AdvancePreview();
                if (multiConfig.Completion && multi.ConfirmCalls == 1 && !releasedCompletion)
                { releasedCompletion = true; multi.CompletionGate.SetResult(); }
            }
            if (multi is not null && !mutatedPreview && args[0] is "U_FOREIGN_PREVIEW" or "U_REPLACED_PREVIEW" &&
                reply.RootElement.GetProperty("kind").GetString() == "decision" &&
                payload.ValueKind == JsonValueKind.Object && payload.GetProperty("phase").GetString() == "preview")
            {
                mutatedPreview = true;
                var holder = (NPreviewCardHolder)multi.PreviewCards.Children[0];
                if (args[0] == "U_FOREIGN_PREVIEW") holder.CardNode.Model = multi.Cards[0];
                else multi.PreviewCards.Children[0] = new NPreviewCardHolder { CardNode = holder.CardNode };
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
