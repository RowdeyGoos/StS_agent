using System;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.GenericEventV7;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Nodes.Rewards;

// This driver observes real native fixture tasks and dispatches only through wire.
internal static partial class GenericEventV7NativeIntegrationHost
{
    private static int RunItem(string scenario)
    {
        if (!new[] { "I_SET_TWO", "I_SET_MIXED", "I_SET_EIGHT", "I_SET_COLLECTION", "I_SET_OFFER", "I_SET_CHOSEN", "I_SET_LATE_SLOT", "I_FIRST", "I_ANOTHER", "I_HELD_OUT", "I_RELIC", "I_INDEX255",
            "I_DELAYED_CREATION", "I_DELAYED_COLLECTION", "I_DELAYED_OFFER", "I_DELAYED_CHOSEN",
            "I_REPEAT", "I_MIXED", "I_MIXED_VARIABLE", "I_RELIC_FIRST", "I_RELIC_ANOTHER", "I_FULL", "I_EXTRA",
            "I_HIDDEN", "I_LINKED", "I_TERMINAL", "I_TASK_FAULT", "I_LATE_CLAIM", "I_LATE_SLOT",
            "I_RELEASE_DISABLED", "I_DERIVED", "I_REPLACED_BUTTON" }.Contains(scenario)) return 2;
        bool creation = scenario == "I_DELAYED_CREATION", collection = scenario is "I_DELAYED_COLLECTION" or "I_SET_COLLECTION",
            offer = scenario is "I_DELAYED_OFFER" or "I_SET_OFFER" or "I_LATE_CLAIM" or "I_LATE_SLOT", chosen = scenario is "I_DELAYED_CHOSEN" or "I_SET_CHOSEN";
        string name = scenario is "I_FIRST" or "I_RELIC_FIRST" ? "FIRST_ITEM" : scenario is "I_ANOTHER" or "I_RELIC_ANOTHER" ? "ANOTHER_ITEM" : "HELD_OUT_ITEM";
        string kind = scenario is "I_SET_EIGHT" or "I_RELIC" or "I_REPEAT" or "I_RELIC_FIRST" or "I_RELIC_ANOTHER" ? "relic" : "potion";
        string[]? kinds=scenario.StartsWith("I_SET_",StringComparison.Ordinal)?
            scenario=="I_SET_EIGHT"?Enumerable.Repeat("relic",8).ToArray():
            scenario=="I_SET_MIXED"?new[]{"potion","potion","relic","relic"}:new[]{"potion","potion"}:null;
        using var fixture = new Program.ItemFixture(name, kind, index: kinds is not null?(kind=="potion"?2:3):scenario == "I_INDEX255" ? 255 : 7,
            delayedCreation: creation, delayedCollection: collection, delayedOffer: offer, delayedChosen: chosen,
            repeatItems: scenario is "I_REPEAT" or "I_MIXED" or "I_MIXED_VARIABLE" ? 2 : 1,
            mixed: scenario is "I_MIXED" or "I_MIXED_VARIABLE",
            transformMinimum: scenario == "I_MIXED_VARIABLE" ? 1 : null,
            transformMaximum: scenario == "I_MIXED_VARIABLE" ? 3 : 1,itemKinds:kinds);
        if (scenario == "I_FULL")
            for (int i = 0; i < fixture.Player.PotionSlots.Count; i++) fixture.Player.PotionSlots[i] = fixture.Player.PotionSlots[0];
        fixture.ExtraReward = scenario == "I_EXTRA";
        fixture.HiddenExtraButton = scenario == "I_HIDDEN";
        fixture.Linked = scenario == "I_LINKED";
        fixture.Terminal = scenario == "I_TERMINAL";
        fixture.FaultOffer = scenario == "I_TASK_FAULT";
        fixture.DisableDuringRelease = scenario == "I_RELEASE_DISABLED";
        fixture.DerivedButton = scenario == "I_DERIVED";
        Program.RetireBeforeChosen(fixture.Room.Layout);
        var baseline = fixture.Player.Deck.Cards.ToArray();
        var keys = baseline.Select(c => c.Id.Entry).ToArray();
        var levels = baseline.Select(c => c.CurrentUpgradeLevel).ToArray();
        using var wire = new GenericEventV7WireService(new string('e', 32), fixture.Session);
        bool creationReleased = false, collectionReleased = false, offerReleased = false, chosenReleased = false;
        bool mutated = false;
        for (int count = 0; count < 2200; count++)
        {
            string? line = ReadLineBounded();
            if (line is null) return 0;
            using var requestDoc = JsonDocument.Parse(line);
            var request = requestDoc.RootElement;
            if (!request.EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "method", "route", "body" })) return 3;
            byte[]? body = request.GetProperty("body").ValueKind == JsonValueKind.Null ? null :
                Convert.FromBase64String(request.GetProperty("body").GetString()!);
            byte[] response = wire.Handle(request.GetProperty("method").GetString(), request.GetProperty("route").GetString(), body);
            Console.WriteLine(JsonSerializer.Serialize(new {
                body = Convert.ToBase64String(response), event_type = fixture.Model.GetType().Name,
                map_open = fixture.Map.IsOpen, overlay_count = fixture.Overlays.ScreenCount,
                chosen_calls = fixture.OptionCalls, collect_calls = fixture.CollectCalls,
                completion_valid = fixture.CompletionValid, item_completions = fixture.ItemCompletions,
                baseline_keys = keys, baseline_levels = levels,
                remaining_keys = fixture.Player.Deck.Cards.Select(c => c.Id.Entry).ToArray(),
                remaining_levels = fixture.Player.Deck.Cards.Select(c => c.CurrentUpgradeLevel).ToArray(),
            }));
            using var reply = JsonDocument.Parse(response);
            var value = reply.RootElement;
            if (value.GetProperty("kind").GetString() == "decision")
            {
                var parent = value.GetProperty("parent");
                if (creation && !creationReleased && fixture.HasPendingCreation && parent.GetProperty("status").GetString() == "waiting")
                { creationReleased = true; fixture.AdvanceCreation(); }
                var child = value.GetProperty("child");
                var payload = value.GetProperty("payload");
                if (child.ValueKind == JsonValueKind.Object && child.GetProperty("kind").GetString() == "item" &&
                    payload.ValueKind == JsonValueKind.Object && payload.GetProperty("status").GetString() == "waiting" && fixture.CollectCalls > 0)
                {
                    if (collection && !collectionReleased && fixture.HasPendingCollection) { collectionReleased = true; fixture.AdvanceCollection(); }
                    else if (offer && !offerReleased && fixture.HasPendingOffer)
                    {
                        offerReleased = true;
                        if (scenario == "I_LATE_CLAIM") ((PotionReward)fixture.Reward).ClaimedPotion = new PotionModel();
                        else if (scenario == "I_LATE_SLOT") fixture.Player.PotionSlots[0] = null;
                        else fixture.AdvanceOffer();
                    }
                    else if (chosen && !chosenReleased && fixture.HasPendingChosen) { chosenReleased = true; fixture.AdvanceChosen(); }
                }
            }
            if(!mutated&&scenario=="I_SET_LATE_SLOT"&&fixture.CollectCalls==1&&value.GetProperty("kind").GetString()=="decision"&&
                value.GetProperty("payload").ValueKind==JsonValueKind.Object&&value.GetProperty("payload").GetProperty("status").GetString()=="ready") {
                mutated=true;fixture.Player.PotionSlots[1]=null;
            }
            if (!mutated && scenario == "I_REPLACED_BUTTON" && value.GetProperty("kind").GetString() == "decision" &&
                value.GetProperty("child").ValueKind == JsonValueKind.Object &&
                value.GetProperty("payload").GetProperty("status").GetString() == "ready")
            {
                mutated = true;
                fixture.Screen.Children[0] = new NRewardButton { Reward = fixture.Reward };
            }
            if (body is not null) Array.Clear(body);
            Array.Clear(response);
        }
        return 4;
    }

    private static int RunCardReward(string scenario) {
        if(!new[]{"CR_ONE","CR_FIVE","CR_SKIP","CR_OFFER","CR_COLLECTION","CR_CHOICE","CR_DEFERRED","CR_WRONG","CR_OWNER","CR_DISABLED"}.Contains(scenario))return 2;
        using var f=new Program.CardRewardFixture(scenario=="CR_ONE"?1:scenario=="CR_FIVE"?5:3) {
            DelayOffer=scenario=="CR_OFFER",DelayCollection=scenario=="CR_COLLECTION",DelayChoice=scenario=="CR_CHOICE",
            DeferInput=scenario=="CR_DEFERRED",WrongInsertion=scenario=="CR_WRONG"
        };
        if(scenario=="CR_DISABLED")f.Skip.IsEnabled=false;
        Program.RetireBeforeChosen(f.World.Room.Layout);
        int baseline=f.World.Player.Deck.Cards.Count;
        using var wire=new GenericEventV7WireService(new string('e',32),f.Session);
        bool released=false;
        for(int count=0;count<2200;count++) {
            string? line=ReadLineBounded();if(line is null)return 0;
            using var doc=JsonDocument.Parse(line);var request=doc.RootElement;
            if(!request.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"method","route","body"}))return 3;
            byte[]? body=request.GetProperty("body").ValueKind==JsonValueKind.Null?null:Convert.FromBase64String(request.GetProperty("body").GetString()!);
            byte[] response=wire.Handle(request.GetProperty("method").GetString(),request.GetProperty("route").GetString(),body);
            Console.WriteLine(JsonSerializer.Serialize(new {
                body=Convert.ToBase64String(response),map_open=f.World.Map.IsOpen,overlay_count=f.World.Overlays.ScreenCount,
                opens=f.Opens,choices=f.Choices,skips=f.Skips,dismisses=f.Dismisses,
                added_slots=f.World.Player.Deck.Cards.Skip(baseline).Select(c=>Array.FindIndex(f.Cards,o=>ReferenceEquals(o,c))).ToArray()
            }));
            using var reply=JsonDocument.Parse(response);var value=reply.RootElement;
            if(!released&&value.GetProperty("kind").GetString()=="decision"&&value.GetProperty("child").ValueKind==JsonValueKind.Object) {
                var payload=value.GetProperty("payload");
                if(scenario=="CR_OWNER"&&payload.GetProperty("phase").GetString()=="choose") {
                    released=true;f.World.Player.Deck.Cards[0].Owner=new MegaCrit.Sts2.Core.Entities.Players.Player();
                }
                if(payload.GetProperty("status").GetString()=="waiting") {
                    if(scenario=="CR_DISABLED"&&f.Opens==1){released=true;f.Skip.IsEnabled=true;}
                    if(f.Choices==1) {
                        released=true;
                        if(scenario=="CR_OFFER")f.OfferGate.SetResult();
                        if(scenario=="CR_COLLECTION")f.CollectionGate.SetResult();
                        if(scenario=="CR_CHOICE")f.ChoiceGate.SetResult();
                        if(scenario=="CR_DEFERRED")f.PendingInput!();
                    }
                }
            }
            if(body is not null)Array.Clear(body);Array.Clear(response);
        }
        return 4;
    }
}
