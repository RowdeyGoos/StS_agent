using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using static Sts2AgentBridge.Unified.FullPublicGraph;
using static Sts2AgentBridge.Unified.FullNativeState;

namespace Sts2AgentBridge.Unified;

internal sealed partial class FullNativeBackend
{
    private JsonObject? EventCompoundChoice(JsonElement child,JsonElement payload,GenericEventCompoundRewards full)
    {
        var (offer,deck)=full.InspectChoice(Text(payload,"decision_id")!);
        var actions=payload.GetProperty("legal_actions").EnumerateArray().Select(a=>a.GetString()!).ToArray();
        if(deck is not null) {
            var view=deck.View??throw new AgentUnsupported();
            Require(Text(payload,"phase")=="deck_"+deck.Kind&&deck.Screen is not null);
            _state.Bind(deck.Screen!);_state.Bind(deck.Pickup);
            foreach(var card in view.Domain){Require(_state.Player.Deck.Cards.Contains(card));_state.Bind(card);}
            foreach(string action in actions) {
                var parts=action.Split(':');
                EventCommand(child,payload,action,parts[0] switch {
                    "select"=>"choose_event_card","deselect"=>"deselect_card","confirm"=>"confirm_selection",_=>throw new AgentUnsupported()
                },parts.Length==2?_state.Ref("card",view.Domain[int.Parse(parts[1])]):null);
            }
            return Node("event","compound_reward",children:new[]{Node("selection",deck.Kind,fields:new (string,object?)[]{
                ("minimum",view.Minimum),("maximum",view.Maximum),("manual_confirmation",true),("cancelable",false)
            },links:new[]{("options",view.Domain.Select(c=>_state.Ref("card",c))),("selected",view.Selected.Select(c=>_state.Ref("card",c)))})});
        }
        if(offer is null)return null;
        var adapter=offer.Adapter;var read=offer.View??throw new AgentUnsupported();
        string phase=adapter.Bundle?(read.Phase=="preview"?"bundle_preview":"bundle_offer"):"card_offer";
        Require(Text(payload,"phase")==phase&&read.Status=="ready"&&adapter.Screen is not null&&actions.SequenceEqual(read.LegalActions));
        _state.Bind(adapter.Screen!);_state.Bind(adapter.DomainIdentity);_state.Bind(offer.Pickup);
        var children=new List<JsonObject>();var references=new Dictionary<int,string>();
        for(int i=0;i<adapter.Count;i++) {
            var cards=adapter.PublicOffer(i);
            string reference=_state.Ref("offer",_state.Indexed(adapter.DomainIdentity,"offer",i));references.Add(i,reference);
            children.Add(Node("offer","cards",reference,children:cards.Select(_state.Card)));
        }
        foreach(string action in actions) {
            var parts=action.Split(':');
            EventCommand(child,payload,action,parts[0] switch {
                "choose"=>"choose_relic_reward","confirm"=>"confirm_relic_selection","skip"=>"skip_reward",_=>throw new AgentUnsupported()
            },parts.Length==2?references[int.Parse(parts[1])]:null);
        }
        var links=new List<(string,IEnumerable<string>)>();
        if(read.SelectedSlot is {} selected)links.Add(("selected",new[]{references[selected]}));
        return Node("relic_choice",phase,children:children,links:links);
    }
}
