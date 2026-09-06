using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading;
using Sts2AgentBridge.Successors.EventOrchestratorV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;

internal static class Program
{
    private const string Nonce="0123456789abcdef0123456789abcdef";
    private static int _checks;
    private static void Main()
    {
        InvalidRequests(); ReceiptsAndFailures(); Lifecycle(); PendingLimits();
        Console.WriteLine(JsonSerializer.Serialize(new {schema_version=1,status="passed",suite="event_orchestrator_v1_wire",check_count=_checks}));
    }
    private static void Check(bool condition){if(!condition)throw new InvalidOperationException("Wire fixture failed.");}
    private static JsonElement Decode(byte[] bytes){try{using var d=JsonDocument.Parse(bytes);return d.RootElement.Clone();}finally{Array.Clear(bytes);}}
    private static JsonElement Read(EventOrchestratorV1WireService s)=>Decode(s.Handle("GET",EventOrchestratorV1WireService.DecisionRoute,null));
    private static byte[] Body(string decision,string action="choose:0",string child="null")=>Encoding.UTF8.GetBytes("{\"decision_id\":\""+decision+"\",\"action_id\":\""+action+"\",\"child\":"+child+"}");
    private static JsonElement Post(EventOrchestratorV1WireService s,byte[] bytes){try{return Decode(s.Handle("POST",EventOrchestratorV1WireService.ActionRoute,bytes));}finally{Array.Clear(bytes);}}
    private static string Decision(EventOrchestratorV1WireService s)=>Read(s).GetProperty("payload").GetProperty("decision_id").GetString()!;
    private static void Error(JsonElement e,string code)=>Check(e.GetProperty("payload").GetProperty("code").GetString()==code&&e.GetProperty("child").ValueKind==JsonValueKind.Null);
    private static void InvalidRequests()
    {
        foreach(var request in new (string Method,string Route,byte[]? Body)[]{
            ("GET","/wrong",null),("DELETE",EventOrchestratorV1WireService.DecisionRoute,null),
            ("GET",EventOrchestratorV1WireService.DecisionRoute,Array.Empty<byte>()),
            ("POST",EventOrchestratorV1WireService.ActionRoute,Array.Empty<byte>()),
            ("POST",EventOrchestratorV1WireService.ActionRoute,new byte[]{0xff}),
            ("POST",EventOrchestratorV1WireService.ActionRoute,new byte[4097]),
        })
        {
            using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
            Error(Decode(service.Handle(request.Method,request.Route,request.Body)),"invalid_request");
            Check(session.Applies==0);_checks++;
        }
        foreach(string mutation in new[]{"duplicate","extra","wrong_decision","illegal_action","child","unpublished"})
        {
            using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
            string id=mutation=="unpublished"?new string('a',64):Decision(service);
            byte[] body=Body(id);
            if(mutation=="duplicate")body=Encoding.UTF8.GetBytes("{\"decision_id\":\""+id+"\","+Encoding.UTF8.GetString(body)[1..]);
            if(mutation=="extra")body=Encoding.UTF8.GetBytes(Encoding.UTF8.GetString(body)[..^1]+",\"extra\":true}");
            if(mutation=="wrong_decision")body=Body(new string('f',64));
            if(mutation=="illegal_action")body=Body(id,"choose:7");
            if(mutation=="child")body=Body(id,"choose:0","{}");
            Error(Post(service,body),"invalid_request");Check(session.Applies==0);_checks++;
        }
        {
            using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
            string id=Decision(service);Check(Post(service,Body(id)).GetProperty("payload").GetProperty("status").GetString()=="accepted");
            Error(Post(service,Body(id)),"invalid_request");Check(session.Applies==1&&session.Adapter.Dispatches==1);_checks++;
        }
    }
    private static void ReceiptsAndFailures()
    {
        foreach(string variant in new[]{"nonce","decision","throw"})
        {
            using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
            string id=Decision(service);
            session.ApplyOverride=(d,a)=>variant=="throw"?throw new InvalidOperationException():new RoomFlowDispatchReceipt("event",variant=="nonce"?new string('b',32):Nonce,variant=="decision"?new string('c',64):d!,a!);
            Error(Post(service,Body(id)),"internal_failure");Error(Read(service),"internal_failure");Check(session.Applies==1);_checks++;
        }
        {
            using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
            session.ReadOverride=()=>throw new InvalidOperationException();Error(Read(service),"internal_failure");Check(session.Applies==0);_checks++;
        }
        {
            using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
            string id=Decision(service);Post(service,Body(id));
            using var other=new Fake("SECOND");session.ReadOverride=other.Read;
            Error(Read(service),"internal_failure");Check(session.Applies==1);_checks++;
        }
    }
    private static void Lifecycle()
    {
        {
            var session=new Fake();var service=new EventOrchestratorV1WireService(Nonce,session);session.ThrowFirstDispose=true;
            bool threw=false;try{service.Dispose();}catch(InvalidOperationException){threw=true;}
            Check(threw&&session.Disposes==1);service.Dispose();Check(session.Disposes==2);service.Dispose();Check(session.Disposes==2);_checks++;
        }
        {
            using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
            session.ReadOverride=()=>{Error(Read(service),"internal_failure");return session.Core.Read();};
            Error(Read(service),"internal_failure");Check(session.Applies==0);_checks++;
        }
        {
            using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
            JsonElement result=default;var worker=new Thread(()=>result=Read(service));worker.Start();worker.Join();
            Error(result,"internal_failure");Error(Read(service),"internal_failure");Check(session.Applies==0);_checks++;
        }
    }
    private static void PendingLimits()
    {
        using var session=new Fake();using var service=new EventOrchestratorV1WireService(Nonce,session);
        using var missingCore=new EventOrchestratorV1Session(Nonce,new Missing());
        var value=missingCore.Read();session.ReadOverride=()=>value;
        for(int i=0;i<2048;i++)Check(Read(service).GetProperty("payload").GetProperty("status").GetString()=="waiting");
        Error(Read(service),"invalid_request");Check(session.Applies==0);_checks++;
    }
    private sealed class Fake : IEventOrchestratorV1Session
    {
        internal Fake(string key="INITIAL"){Adapter=new Adapter(key);Core=new EventOrchestratorV1Session(Nonce,Adapter);}
        internal Adapter Adapter {get;}
        internal EventOrchestratorV1Session Core {get;}
        internal Func<IRoomFlowReadValue>? ReadOverride;
        internal Func<string?,string?,IRoomFlowApplyValue>? ApplyOverride;
        internal bool ThrowFirstDispose;
        internal int Applies,Disposes;
        public string FlowKind=>"event";
        public IEventOrchestratorV1ChildBroker? ActiveChild=>Core.ActiveChild;
        public IRoomFlowReadValue Read()=>ReadOverride?.Invoke()??Core.Read();
        public IRoomFlowApplyValue Apply(string? d,string? a){Applies++;return ApplyOverride?.Invoke(d,a)??Core.Apply(d,a);}
        public void Dispose(){Disposes++;if(ThrowFirstDispose&&Disposes==1)throw new InvalidOperationException();Core.Dispose();}
    }
    private sealed class Adapter : IEventOrchestratorV1NativeAdapter
    {
        private readonly object _run=new(),_player=new(),_room=new(),_map=new(),_event=new();
        private readonly EventOrchestratorV1NativeCandidate _candidate;
        internal int Dispatches;
        internal Adapter(string key)
        {
            var policy=EventOrchestratorV1ChildPolicy.ItemReward();var factory=new Factory(policy);
            _candidate=new(0,key,"Choose",true,true,false,false,false,new object(),new object(),new object(),()=>Dispatches++,policy,factory);
        }
        public EventOrchestratorV1SurfaceCapture CaptureSurface()=>EventOrchestratorV1SurfaceCapture.Parent(_run,_player,_room,_map,_event,false,false,false,false,new[]{_candidate});
        public EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending)=>throw new InvalidOperationException();
        public void Dispose(){}
    }
    private sealed class Factory : IEventOrchestratorV1ChildFactory
    {
        internal Factory(EventOrchestratorV1ChildPolicy policy)=>Policy=policy;
        public EventOrchestratorV1ChildPolicy Policy{get;}
        public IEventOrchestratorV1ChildBroker Create(EventOrchestratorV1AcceptedContext a,EventOrchestratorV1ChildCorrelation c,object s)=>throw new InvalidOperationException();
    }
    private sealed class Missing : IEventOrchestratorV1NativeAdapter
    {
        public EventOrchestratorV1SurfaceCapture CaptureSurface()=>EventOrchestratorV1SurfaceCapture.Missing();
        public EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending)=>throw new InvalidOperationException();
        public void Dispose(){}
    }
}
