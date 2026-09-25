using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;
using static Sts2AgentBridge.Unified.FullPublicGraph;
using static Sts2AgentBridge.Unified.FullNativeState;

namespace Sts2AgentBridge.Unified;

internal sealed partial class FullNativeBackend
{
    private JsonObject Shop(JsonElement wire)
    {
        var owner = _router.ActiveObservationSource as ShopInteractiveSession ?? throw new AgentUnsupported();
        string decision = Text(wire, "decision_id")!;
        var native = owner.Inspect(decision);
        Require(ReferenceEquals(native.Surface.PlayerIdentity, _state.Player));
        _state.Bind(native.Surface.RoomIdentity ?? throw new AgentUnsupported()); _state.Bind(native.Surface.InventoryModelIdentity ?? throw new AgentUnsupported()); _state.Bind(native.Surface.InventoryNodeIdentity ?? throw new AgentUnsupported());
        string phase = Text(wire, "phase")!;
        if(phase=="rewards") {
            var rewards=owner.RewardSource as Sts2AgentBridge.Rooms.Rest.RestRewardContinuation??throw new AgentUnsupported();
            return RewardContext((rewards.Reader??throw new AgentUnsupported()).InteractionSession,owner.RewardDecision,Text(wire,"screen_kind")=="card_reward",
                wire.GetProperty("legal_actions").EnumerateArray().Select(a=>a.GetString()![7..]),
                (action,kind,subject,target)=>Command("shop",decision,"reward:"+action,kind,subject,target));
        }
        var children = new List<JsonObject>(); var offers = new Dictionary<int, string>();
        if (native.Choice is {} choice)
        {
            foreach (var card in choice.Domain) { Require(_state.Player.Deck.Cards.Contains(card)); _state.Bind(card); }
            foreach (string action in wire.GetProperty("legal_actions").EnumerateArray().Select(a => a.GetString()!))
            {
                string[] parts = action.Split(':');
                Command("shop", decision, action, parts[0] switch { "select" => "choose_relic_card", "deselect" => "deselect_relic_card",
                    "confirm" => phase=="removal_confirmation"?"confirm_selection":"confirm_relic_selection", "cancel" => "cancel_selection", _ => throw new AgentUnsupported() },
                    parts.Length == 2 ? _state.Ref("card", choice.Domain[int.Parse(parts[1])]) : null);
            }
            return Node(phase=="removal_confirmation"?"shop_removal":"relic_choice", "card_grid", fields: new (string, object?)[] { ("minimum", choice.Minimum), ("maximum", choice.Maximum), ("cancelable", choice.Cancelable) },
                links: new[] { ("options", choice.Domain.Select(c => _state.Ref("card", c))), ("selected", choice.Selected.Select(c => _state.Ref("card", c))) });
        }
        foreach (var offer in native.Surface.Offers)
        {
            _state.Bind(offer.EntryIdentity); if (offer.StockModelIdentity is {} stock) _state.Bind(stock); _state.Bind(offer.ControlIdentity); _state.Bind(offer.LabelIdentity);
            string reference = _state.Ref("offer", offer.EntryIdentity); offers.Add(offer.Slot, reference);
            var display = offer.StockModelIdentity switch {
                CardModel card => new[] { _state.Card(card) }, PotionModel potion => new[] { _state.Potion(potion) },
                RelicModel relic => new[] { _state.Relic(relic) }, null => Array.Empty<JsonObject>(), _ => throw new AgentUnsupported() };
            var publicOffer = native.Core?.Offers.Single(o => o.Slot == offer.Slot);
            children.Add(Node("offer", offer.Kind.ToString().ToLowerInvariant(), reference, new (string, object?)[] {
                ("price", offer.DisplayedPrice), ("enabled", offer.Enabled), ("affordable", native.Surface.Gold >= offer.DisplayedPrice),
                ("supported", publicOffer?.Supported ?? false) }, display));
        }
        foreach (var control in new[] { native.Surface.BackControl, native.Surface.MerchantControl, native.Surface.ProceedControl })
            if (control is not null) _state.Bind(control.Identity);
        foreach (string action in wire.GetProperty("legal_actions").EnumerateArray().Select(a => a.GetString()!))
        {
            string[] parts = action.Split(':');
            string? subject = parts[0] switch {
                "buy" => offers[int.Parse(parts[^1])], "remove" => _state.Ref("card", native.Surface.Deck[int.Parse(parts[1])].ModelIdentity),
                "discard" => _state.Ref("potion", native.Surface.PotionSlots[int.Parse(parts[1])].ModelIdentity!), _ => null };
            Command("shop", decision, action, parts[0] switch {
                "buy" => "buy_shop_item", "remove" => "choose_shop_removal", "discard" => "discard_potion", "open" => "open_shop",
                "inventory" when action == "inventory:close" => "close_shop", "leave" => "leave_shop", _ => throw new AgentUnsupported() }, subject);
        }
        return Node("shop", fields: new (string, object?)[] { ("stage", phase) }, children: children);
    }
}
