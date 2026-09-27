// Real compound owners and production choice projection; public card formatting
// and the surrounding run graph are inert seams, not live localization evidence.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using static Sts2AgentBridge.Unified.FullPublicGraph;

namespace Sts2AgentBridge.Unified
{
    internal static class FullAgentRoutes {internal const int MaximumCandidates=2048;}
    internal sealed class FullNativeState
    {
        internal Player Player=null!;
        private readonly Dictionary<(string,object),string> _references=new();
        private readonly Dictionary<(object,string,int),object> _indexed=new();
        internal static void Require(bool good){if(!good)throw new AgentUnsupported();}
        internal void Bind(object value){}
        internal object Indexed(object owner,string kind,int index)
        {var key=(owner,kind,index);if(!_indexed.ContainsKey(key))_indexed.Add(key,new());return _indexed[key];}
        internal string Ref(string kind,object model)
        {var key=(kind,model);if(!_references.ContainsKey(key))_references.Add(key,kind+":"+_references.Count);return _references[key];}
        internal JsonObject Card(CardModel card)=>Node("card",card.Id.Entry.ToLowerInvariant(),Ref("card",card),fields:new (string,object?)[]{("upgrade_level",card.CurrentUpgradeLevel)});
    }
    internal sealed partial class FullNativeBackend
    {
        private readonly FullNativeState _state=new();
        private readonly List<(string Native,JsonObject Candidate)> _inputs=new();
        private static string? Text(JsonElement value,string key)=>value.TryGetProperty(key,out var field)&&field.ValueKind==JsonValueKind.String?field.GetString():null;
        private void EventCommand(JsonElement child,JsonElement payload,string action,string kind,string? subject=null,string? target=null)
        {
            FullNativeState.Require(child.GetProperty("ordinal").GetInt32()>0&&Text(child,"parent_decision_id")?.Length==64&&
                Text(child,"parent_action_id") is not null&&Text(payload,"decision_id")?.Length==64);
            _inputs.Add((action,Candidate(_inputs.Count,kind,subject,target)));
        }
        internal (JsonObject Decision, string[] Actions) ProjectGrid(GenericEventV7Binding binding, JsonElement wire)
        {
            _inputs.Clear(); _state.Player = binding.Player;
            var run = Node("run", children: new[] { Node("deck", children: binding.Player.Deck.Cards.Select(_state.Card)) });
            var context = EventGrid(wire.GetProperty("child"), wire.GetProperty("payload"), binding);
            var decision = Decision(run, context, _inputs.Select(i => i.Candidate)); Validate(decision);
            return (decision, _inputs.Select(i => i.Native).ToArray());
        }
        internal (JsonObject Decision,string[] Actions) Project(Player player,GenericEventV7Child child,GenericEventV7RewardRead read,GenericEventCompoundRewards owner)
        {
            _state.Player=player;
            var run=Node("run",children:new[]{Node("deck",children:player.Deck.Cards.Select(_state.Card))});
            using var descriptor=JsonDocument.Parse(JsonSerializer.Serialize(new {ordinal=child.Ordinal,parent_decision_id=child.ParentDecisionId,parent_action_id=child.ParentActionId}));
            using var payload=JsonDocument.Parse(JsonSerializer.Serialize(new {decision_id=read.DecisionId,phase=read.Phase,legal_actions=read.LegalActions}));
            var context=EventCompoundChoice(descriptor.RootElement,payload.RootElement,owner)??throw new AgentUnsupported();
            var decision=Decision(run,context,_inputs.Select(i=>i.Candidate));Validate(decision);
            return(decision,_inputs.Select(i=>i.Native).ToArray());
        }
    }
}
