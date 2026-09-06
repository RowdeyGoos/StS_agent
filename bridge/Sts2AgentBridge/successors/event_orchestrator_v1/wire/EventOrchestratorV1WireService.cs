using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1;

public sealed class EventOrchestratorV1WireService : IDisposable
{
    public const string DecisionRoute="/probe/event-orchestrator-v1/public/decision";
    public const string ActionRoute="/probe/event-orchestrator-v1/public/action";
    private readonly object _gate=new();
    private readonly int _owner=Environment.CurrentManagedThreadId;
    private readonly string _nonce;
    private readonly EventOrchestratorV1WireValidation _validation;
    private EventOrchestratorV1ChildEnvelope? _completedEnvelope;
    private readonly IEventOrchestratorV1Session _session;
    private readonly HashSet<string> _decisions=new(StringComparer.Ordinal);
    private readonly List<(string Decision,string Action)> _childAccepted=new();
    private string? _ready;
    private string[] _legal=Array.Empty<string>();
    private RoomFlowDispatchReceipt? _parentReceipt;
    private IEventOrchestratorV1ChildBroker? _child;
    private EventOrchestratorV1ChildCorrelation? _correlation;
    private EventOrchestratorV1ChildEnvelope? _envelope;
    private bool _resolvedPayloadEmitted;
    private bool _inside,_failed,_disposed,_cleanupFailed,_interfered;
    private int _parentAttempts,_totalAttempts,_lastOrdinal,_reads;
    private byte[]? _terminal;

    public EventOrchestratorV1WireService(string nonce,IEventOrchestratorV1Session session)
    {
        if(!RoomFlowIdentity.IsNonce(nonce))throw new ArgumentException("Invalid nonce.");
        _nonce=nonce;_validation=new(nonce);_session=session??throw new ArgumentNullException(nameof(session));
        if(session.FlowKind!="event")throw new ArgumentException("Event session required.");
    }
    public byte[] Handle(string? method,string? route,byte[]? body)
    {
        lock(_gate)
        {
            if(_inside){_interfered=true;return Fail("internal_failure");}
            if(_failed||_disposed||Environment.CurrentManagedThreadId!=_owner)return Fail("internal_failure");
            _inside=true;byte[]? result=null;
            try
            {
                if(method=="GET"&&route==DecisionRoute&&body is null)
                {
                    if(++_reads>2048)return Fail("invalid_request");
                    if(_terminal is not null)return (byte[])_terminal.Clone();
                    result=Read();
                }
                else if(method=="POST"&&route==ActionRoute&&body is {Length:>0 and <=4096})result=Apply(body);
                else return Fail("invalid_request");
                if(_interfered||_disposed){Array.Clear(result);result=null;return Fail("internal_failure");}
                byte[] transfer=result;result=null;return transfer;
            }
            catch(RequestValidationException){return Fail("invalid_request");}
            catch{return Fail("internal_failure");}
            finally{if(result is not null)Array.Clear(result);_inside=false;}
        }
    }
    private byte[] Read()
    {
        _ready=null;_legal=Array.Empty<string>();
        if(_child is not null&&!_resolvedPayloadEmitted)return ReadChild();
        if(_child is not null)
        {
            Require(ReferenceEquals(_child.Correlation,_correlation)&&_child.Status==EventOrchestratorV1ChildStatus.Resolved);
            // Only now may the parent dispose and resume the resolved child.
        }
        object value=_session.Read();
        if(_child is not null)
        {
            Require(!ReferenceEquals(_session.ActiveChild,_child));
            _completedEnvelope=_envelope;_validation.ResetChild();
            _child=null;_correlation=null;_envelope=null;_resolvedPayloadEmitted=false;_childAccepted.Clear();
        }
        if(value is EventOrchestratorV1Observation x)
        {
            Require(x.SessionNonce==_nonce&&x.Version==EventOrchestratorV1Limits.Version&&x.ParentOrdinal==1&&x.FlowKind=="event");
            if(x.Status=="child")
            {
                Require(x.Phase=="child"&&x.Child is not null&&x.Candidates.Count==0&&x.LegalActions.Count==0&&x.DecisionId=="");
                var broker=_session.ActiveChild;Require(broker is not null&&_parentReceipt is not null);
                var c=broker!.Correlation;
                Require(ReferenceEquals(c.ParentReceipt,_parentReceipt)&&c.ChildOrdinal==_lastOrdinal+1&&c.ChildOrdinal<=4);
                Require((c.Kind==EventOrchestratorV1ChildKind.Item&&broker is IEventOrchestratorV1ItemChildBroker)||(c.Kind==EventOrchestratorV1ChildKind.CardSelection&&broker is IEventOrchestratorV1CardChildBroker));
                Require(c.ParentReceipt.SessionNonce==_nonce&&Same(x.Child!,c)&&broker.Status==EventOrchestratorV1ChildStatus.Active);
                _child=broker;_correlation=c;_envelope=x.Child;_lastOrdinal=c.ChildOrdinal;return ReadChild();
            }
            Require(x.Child is null&&_session.ActiveChild is null);
            Require((x.Status=="ready"&&x.Phase is "choose_option" or "proceed")||(x.Status=="waiting"&&x.Phase=="waiting")||(x.Status=="unsupported"&&x.Phase=="unsupported"));
            if(x.Status=="ready")Publish(x.DecisionId,x.LegalActions);
            else Require(x.DecisionId==""&&x.Candidates.Count==0&&x.LegalActions.Count==0);
            if(x.Status=="unsupported")_failed=true;
        }
        else if(value is EventOrchestratorV1ResolvedResult done)
        {
            Require(done.SessionNonce==_nonce&&done.Version==EventOrchestratorV1Limits.Version&&done.ParentOrdinal==1&&done.FlowKind=="event"&&done.Result=="map_handoff"&&_parentReceipt is not null&&done.DecisionId==_parentReceipt.DecisionId&&done.ActionId==_parentReceipt.ActionId);
        }
        else throw new InvalidOperationException();
        _validation.Parent(value,_parentReceipt,_completedEnvelope);
        byte[] wrapped=EventOrchestratorV1WireCodec.Wrap(_nonce,null,EventOrchestratorV1WireCodec.Parent(_nonce,value));
        if(value is EventOrchestratorV1ResolvedResult)_terminal=(byte[])wrapped.Clone();
        return wrapped;
    }
    private byte[] ReadChild()
    {
        Require(_child is not null&&_correlation is not null&&_envelope is not null&&ReferenceEquals(_session.ActiveChild,_child)&&ReferenceEquals(_child.Correlation,_correlation));
        object value=_child switch {IEventOrchestratorV1ItemChildBroker b=>b.Read(),IEventOrchestratorV1CardChildBroker b=>b.Read(),_=>throw new InvalidOperationException()};
        byte[] payload=EncodeChild(value);
        try
        {
            using JsonDocument document=JsonDocument.Parse(payload);var x=document.RootElement;
            _validation.Child(x,false,_childAccepted);CommonChild(x);string status=x.GetProperty("status").GetString()!;
            if(status=="ready")Publish(x.GetProperty("decision_id").GetString()!,x.GetProperty("legal_actions").EnumerateArray().Select(a=>a.GetString()!).ToArray());
            else Require(status is "waiting" or "resolved" or "unsupported");
            ValidateHistory(x,status);
            if(status=="resolved")Require(_child.Status==EventOrchestratorV1ChildStatus.Resolved&&_childAccepted.Count>0);
            else if(status=="unsupported")_failed=true;
            else Require(_child.Status==EventOrchestratorV1ChildStatus.Active);
            byte[] result=EventOrchestratorV1WireCodec.Wrap(_nonce,_envelope,payload);payload=Array.Empty<byte>();
            if(status=="resolved")_resolvedPayloadEmitted=true;
            return result;
        }
        finally{Array.Clear(payload);}
    }
    private (string Decision,string Action) ValidateRequest(byte[] body)
    {
        try
        {
        using JsonDocument d=JsonDocument.Parse(body,new JsonDocumentOptions{MaxDepth=12});var x=d.RootElement;
        Keys(x,"decision_id","action_id","child");string decision=Text(x,"decision_id"),action=Text(x,"action_id");
        Require(_ready is not null&&decision==_ready&&_legal.Contains(action)&&RoomFlowIdentity.IsDecisionId(decision)&&!_decisions.Contains(decision)&&_totalAttempts<52);
        JsonElement c=x.GetProperty("child");
        if(_child is null)Require(c.ValueKind==JsonValueKind.Null&&_parentAttempts<12&&RoomFlowIdentity.IsActionId("event",action));
        else
        {
            Keys(c,"kind","child_ordinal","parent_decision_id","parent_action_id");
            Require(!_resolvedPayloadEmitted&&_envelope is not null&&Text(c,"kind")==_envelope.Kind&&c.GetProperty("child_ordinal").TryGetInt32(out int ordinal)&&ordinal==_envelope.ChildOrdinal&&Text(c,"parent_decision_id")==_envelope.ParentDecisionId&&Text(c,"parent_action_id")==_envelope.ParentActionId&&ReferenceEquals(_session.ActiveChild,_child)&&ReferenceEquals(_child.Correlation,_correlation));
            Require(_childAccepted.Count<(_correlation!.Kind==EventOrchestratorV1ChildKind.Item?1:10));
        }
            return (decision,action);
        }
        catch { throw new RequestValidationException(); }
    }
    private sealed class RequestValidationException : Exception { }
    private byte[] Apply(byte[] body)
    {
        var (decision,action)=ValidateRequest(body);
        _decisions.Add(decision);_ready=null;_legal=Array.Empty<string>();_totalAttempts++;
        if(_child is null)
        {
            _parentAttempts++;object result=_session.Apply(decision,action);
            _validation.Parent(result,_parentReceipt,_completedEnvelope);
            if(result is RoomFlowDispatchReceipt r){Require(r.FlowKind=="event"&&r.SessionNonce==_nonce&&r.DecisionId==decision&&r.ActionId==action);_parentReceipt=r;_completedEnvelope=null;}
            else if(result is RoomFlowApplyFailure f){Require(f.FlowKind=="event"&&f.SessionNonce==_nonce&&f.Outcome is "rejected" or "uncertain" or "unsupported");_failed=true;}
            else throw new InvalidOperationException();
            return EventOrchestratorV1WireCodec.Wrap(_nonce,null,EventOrchestratorV1WireCodec.Parent(_nonce,result));
        }
        object childResult=_child switch {IEventOrchestratorV1ItemChildBroker b=>b.Apply(decision,action),IEventOrchestratorV1CardChildBroker b=>b.Apply(decision,action),_=>throw new InvalidOperationException()};
        byte[] payload=EncodeChild(childResult);
        try
        {
            using JsonDocument doc=JsonDocument.Parse(payload);var r=doc.RootElement;_validation.Child(r,true,_childAccepted);CommonChild(r);
            string status=Text(r,_correlation!.Kind==EventOrchestratorV1ChildKind.Item?"status":"outcome");
            if(status=="accepted"){Require(Text(r,"decision_id")==decision&&Text(r,"action_id")==action);_childAccepted.Add((decision,action));}
            else _failed=true;
            var wrapped=EventOrchestratorV1WireCodec.Wrap(_nonce,_envelope,payload);payload=Array.Empty<byte>();return wrapped;
        }
        finally{Array.Clear(payload);}
    }
    private byte[] EncodeChild(object value)=>_correlation!.Kind==EventOrchestratorV1ChildKind.Item?EventOrchestratorV1WireCodec.Item(value):EventOrchestratorV1WireCodec.Card(value);
    private void CommonChild(JsonElement x)
    {
        Require(x.GetProperty("schema_version").GetInt32()==1&&Text(x,"session_nonce")==_nonce);
        if(_correlation!.Kind==EventOrchestratorV1ChildKind.Item)Require(Text(x,"version")=="item_v1"&&Text(x,"protocol")=="item_probe_v1"&&x.GetProperty("surface_ordinal").GetInt32()==1);
        else Require(Text(x,"version")=="card_selection_v1"&&x.GetProperty("parent_ordinal").GetInt32()==1);
    }
    private void ValidateHistory(JsonElement x,string status)
    {
        if(_correlation!.Kind==EventOrchestratorV1ChildKind.Item)
        {
            if(status=="resolved")Require(_childAccepted.Count==1&&Text(x,"decision_id")==_childAccepted[0].Decision&&Text(x,"action_id")==_childAccepted[0].Action&&Text(x,"result")=="collected");
            return;
        }
        var history=x.GetProperty("prior_results");Require(history.GetArrayLength()<=_childAccepted.Count);
        int i=0;foreach(var row in history.EnumerateArray()){Require(Text(row,"decision_id")==_childAccepted[i].Decision&&Text(row,"action_id")==_childAccepted[i].Action);i++;}
        if(status is "ready" or "resolved")Require(i==_childAccepted.Count);
        if(status=="ready")Require(Text(x,"operation")=="add"&&Text(x,"commit_mode")=="auto_at_max"&&x.GetProperty("min_select").GetInt32()==2&&x.GetProperty("max_select").GetInt32()==2&&x.GetProperty("candidates").GetArrayLength()==8);
        if(status=="resolved")Require(Text(x,"operation")=="add"&&x.GetProperty("selected_cards").GetArrayLength()==2&&_childAccepted.Count==2);
    }
    private void Publish(string decision,IReadOnlyList<string> legal)
    {Require(RoomFlowIdentity.IsDecisionId(decision)&&!_decisions.Contains(decision)&&legal.Count is >0 and <=65&&legal.Distinct(StringComparer.Ordinal).Count()==legal.Count);_ready=decision;_legal=legal.ToArray();}
    private static bool Same(EventOrchestratorV1ChildEnvelope e,EventOrchestratorV1ChildCorrelation c)=>e.Kind==(c.Kind==EventOrchestratorV1ChildKind.Item?"item":"card_selection")&&e.ChildOrdinal==c.ChildOrdinal&&e.ParentDecisionId==c.ParentReceipt.DecisionId&&e.ParentActionId==c.ParentReceipt.ActionId;
    private static string Text(JsonElement e,string key){var p=e.GetProperty(key);Require(p.ValueKind==JsonValueKind.String);return p.GetString()!;}
    private static void Keys(JsonElement e,params string[] expected){Require(e.ValueKind==JsonValueKind.Object);var seen=new HashSet<string>(StringComparer.Ordinal);foreach(var p in e.EnumerateObject())Require(seen.Add(p.Name)&&expected.Contains(p.Name));Require(seen.Count==expected.Length);}
    private static void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool condition){if(!condition)throw new InvalidOperationException("Invalid event wire state.");}
    private byte[] Fail(string code){_failed=true;_ready=null;_legal=Array.Empty<string>();return EventOrchestratorV1WireCodec.Error(_nonce,code);}
    public void Dispose()
    {
        lock(_gate)
        {
            if(_inside||Environment.CurrentManagedThreadId!=_owner){_failed=true;if(_inside)_interfered=true;throw new InvalidOperationException("Owner cleanup required.");}
            if(_disposed&&!_cleanupFailed)return;
            _disposed=true;_failed=true;_ready=null;_legal=Array.Empty<string>();
            if(_terminal is not null)Array.Clear(_terminal);_terminal=null;
            try{_session.Dispose();_cleanupFailed=false;_child=null;_correlation=null;_envelope=null;}
            catch{_cleanupFailed=true;throw;}
        }
    }
}
