using System;
using System.Linq;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.GenericEventV3;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV2;
internal static class Program
{
    private const string Nonce="0123456789abcdef0123456789abcdef";
    private static readonly string Id=new('a',64);
    private static readonly byte[] Config=Encoding.UTF8.GetBytes("{\"schema_version\":\"generic_event_v3_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"generic\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static int _checks;
    private static void Check(bool value){_checks++;if(!value)throw new InvalidOperationException("Assertion "+_checks);}
    private static void Spin(Func<bool> predicate){var s=Stopwatch.StartNew();while(!predicate()){if(s.ElapsedMilliseconds>2000)throw new TimeoutException();Thread.Sleep(1);}}
    private static GenericEventTransportRuntime Create(InertFixture.InertEvent? adapter=null)=>GenericEventTransportRuntime.Create((byte[])Config.Clone(),()=>Encoding.ASCII.GetBytes(new string('c',64)),(_,nonce)=>new GenericEventV3WireService(nonce,new GenericEventV3Session(adapter??new("FOREST_ARCHIVE"),nonce)))!;
    private static int Main()
    {
        try{ThreadPool.SetMinThreads(8,8);Protocol();Ownership();Budgets();QueueLate();Classifiers();Console.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="passed",suite="generic_event_release_runtime",check_count=_checks}));return 0;}
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
    private static byte[] Request(string action="",int ordinal=0)=>Encoding.ASCII.GetBytes((action==""?"GET /probe/generic-event-v3/public/decision":"POST /probe/generic-event-v3/public/action")+" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "+new string('c',64)+"\r\nAccept: application/json\r\n"+(action==""?"":"X-Sts2-Decision-Id: "+Id+"\r\nX-Sts2-Action-Id: "+action+"\r\n"+(ordinal==0?"":"X-Sts2-Child-Ordinal: "+ordinal+"\r\nX-Sts2-Parent-Decision-Id: "+Id+"\r\nX-Sts2-Parent-Action-Id: choose:0\r\n"))+"Connection: close\r\n\r\n");
    private static bool Parse(byte[] request)=>GenericEventTransportRequestParser.TryParse(request,GenericEventReleaseSelection.Generic,out _);
    private static void Protocol()
    {
        Check(GenericEventTransportConfiguration.TryParse(Config,out var selection)&&selection==GenericEventReleaseSelection.Generic);
        Check(!GenericEventTransportConfiguration.TryParse(Config.Concat(new byte[]{10}).ToArray(),out _));Check(Parse(Request()));
        for(int i=0;i<8;i++)Check(Parse(Request("choose:"+i)));
        for(int i=0;i<64;i++)Check(Parse(Request("select:"+i,1)));
        for(int i=1;i<=4;i++){Check(Parse(Request("preview",i)));Check(Parse(Request("confirm",i)));}
        foreach(string action in new[]{"choose:8","select:0","begin","choose:00"})Check(!Parse(Request(action)));
        foreach(string action in new[]{"select:64","select:00","select:-1","choose:0","CONFIRM","confirm\r\nX: x"})Check(!Parse(Request(action,1)));
        foreach(string original in new[]{"Host: 127.0.0.1:43117","Accept: application/json","Connection: close","Authorization: Bearer"})Check(!Parse(Encoding.ASCII.GetBytes(Encoding.ASCII.GetString(Request()).Replace(original,original+" "))));
        Check(!Parse(Request("confirm",5)));Check(!Parse(Request().Concat(new byte[]{1}).ToArray()));
        var request=Request("select:63",4);Check(GenericEventTransportRequestParser.TryParse(request,selection,out var parsed)&&parsed.ChildOrdinal==4&&parsed.IsChild);
        using var body=JsonDocument.Parse(GenericEventTransportServiceBody.Build(Id,"select:63",4,Id,"choose:0"));Check(body.RootElement.GetProperty("child").GetProperty("ordinal").GetInt32()==4);
    }
    private static void Ownership()
    {
        byte[] config=(byte[])Config.Clone(),token=Encoding.ASCII.GetBytes(new string('c',64));int calls=0;
        var runtime=GenericEventTransportRuntime.Create(config,()=>token,(_,_)=>throw new GenericEventTransportFactoryFailure(()=>{if(++calls==1)throw new Exception();}));
        Check(runtime is not null && runtime.TransportStopped && !runtime.ServiceDisposed);Check(config.All(x=>x==0)&&token.All(x=>x==0));
        Check(!Task.Run(()=>runtime!.DisposeServiceOnOwnerFrame()).Result&&calls==0);Check(!runtime!.DisposeServiceOnOwnerFrame()&&calls==1&&!runtime.ServiceDisposed);
        Check(runtime.DisposeServiceOnOwnerFrame()&&calls==2&&runtime.IsFullyStopped);Check(runtime.DisposeServiceOnOwnerFrame()&&calls==2);Check(!runtime.Start());
        var adapter=new InertFixture.InertEvent("FOREST_ARCHIVE"){ThrowFirstDispose=true};runtime=Create(adapter);Check(runtime.StopTransportAndJoin());Check(!runtime.DisposeServiceOnOwnerFrame()&&adapter.DisposeCalls==1);Check(runtime.DisposeServiceOnOwnerFrame()&&adapter.DisposeCalls==2);
        byte[] invalid=Encoding.ASCII.GetBytes("{}");int reads=0;Check(GenericEventTransportRuntime.Create(invalid,()=>{reads++;return token;},(_,_)=>throw new Exception()) is null&&reads==0&&invalid.All(x=>x==0));
    }
    private static void Budgets()
    {
        var runtime=Create();for(int i=0;i<12;i++)Check(runtime.ReservePostForTests(GenericEventTransportRoute.ParentPost,i.ToString(),"choose:0"));
        Check(!runtime.ReservePostForTests(GenericEventTransportRoute.ParentPost,"new","choose:0"));
        for(int i=0;i<40;i++)Check(runtime.ReservePostForTests(GenericEventTransportRoute.ChildPost,i.ToString(),"select:0"));
        Check(!runtime.ReservePostForTests(GenericEventTransportRoute.ChildPost,"new","select:0"));runtime.StopTransportAndJoin();Check(runtime.DisposeServiceOnOwnerFrame());
        runtime=Create();Check(runtime.ReservePostForTests(GenericEventTransportRoute.ParentPost,Id,"choose:0"));Check(!runtime.ReservePostForTests(GenericEventTransportRoute.ParentPost,Id,"choose:0"));
        for(int i=0;i<2048;i++)if(!runtime.ReserveReadForTests())throw new Exception("Read budget early");Check(!runtime.ReserveReadForTests());runtime.StopTransportAndJoin();Check(runtime.DisposeServiceOnOwnerFrame());
    }
    private static void QueueLate()
    {
        var queue=new OwnedByteFrameQueue(()=>{});byte[] late=Encoding.ASCII.GetBytes("late canary");using var entered=new ManualResetEventSlim();using var release=new ManualResetEventSlim();
        var submit=Task.Run(()=>queue.Submit(()=>{entered.Set();release.Wait();return new OwnedServiceResponse(200,late);}));Spin(()=>queue.OutstandingCount==1);var drain=Task.Run(()=>queue.DrainFrame());Check(entered.Wait(1000));
        var result=submit.Result;Check(result.Status==OwnedByteDispatchStatus.TimedOutAfterClaim&&result.Value is null);release.Set();drain.Wait();Check(late.All(x=>x==0));queue.Stop();Check(queue.WaitForSettled(1000));queue.Dispose();
    }
    private static void Classifiers()
    {
        foreach(string scenario in new[]{"FOREST_ARCHIVE","removal_fixed","reward_auto_fixed","reward_explicit_fixed","mixed_three"})
        {
            var adapter=new InertFixture.InertEvent(scenario);using var service=new GenericEventV3WireService(Nonce,new GenericEventV3Session(adapter,Nonce));int childResolved=0;
            for(int i=0;i<150;i++)
            {
                adapter.Advance();byte[] response=service.Handle("GET","/probe/generic-event-v3/public/decision",null);using var doc=JsonDocument.Parse(response);var root=doc.RootElement;var parent=root.GetProperty("parent");
                var classified=GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.DecisionGet,GenericEventReleaseSelection.Generic,Nonce,200,response);
                if(parent.GetProperty("status").GetString()=="complete"){Check(classified==TerminalClassification.Terminal&&childResolved==(scenario=="mixed_three"?3:1));break;}
                Check(classified==TerminalClassification.NonTerminal);
                bool child=root.GetProperty("child").ValueKind!=JsonValueKind.Null;var view=child?root.GetProperty("payload"):parent;
                if(child&&view.GetProperty("kind").GetString()=="child_resolved"){childResolved++;continue;}
                if(view.GetProperty("status").GetString()!="ready")continue;
                string id=view.GetProperty("decision_id").GetString()!,action=view.GetProperty("legal_actions")[0].GetString()!;var descriptor=root.GetProperty("child");
                var body=GenericEventTransportServiceBody.Build(id,action,child?descriptor.GetProperty("ordinal").GetInt32():0,child?descriptor.GetProperty("parent_decision_id").GetString():null,child?descriptor.GetProperty("parent_action_id").GetString():null);
                var receipt=service.Handle("POST","/probe/generic-event-v3/public/action",body);Check(GenericEventTerminalClassifier.Classify(child?GenericEventTransportRoute.ChildPost:GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,200,receipt)==TerminalClassification.NonTerminal);
            }
        }
        foreach(string outcome in new[]{"unsupported","uncertain","rejected"})
        {
            byte[] response=JsonSerializer.SerializeToUtf8Bytes(new {schema_version=1,protocol="generic_event_v3",session_nonce=Nonce,kind="action",parent=(object?)null,
                child=new {ordinal=1,parent_decision_id=Id,parent_action_id="choose:0",operation="add",min_select=1,max_select=2,commit_mode="auto_at_max",domain_count=3},
                payload=new {schema_version=1,kind="child_failure",version="card_selection_v1",session_nonce=Nonce,parent_ordinal=1,outcome}});
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ChildPost,GenericEventReleaseSelection.Generic,Nonce,200,response)==TerminalClassification.Terminal);
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,200,response)==TerminalClassification.Invalid);
        }
        foreach(string outcome in new[]{"stale_decision","illegal_action","unsupported","uncertain","budget_exhausted"})
        {
            byte[] body=Encoding.UTF8.GetBytes("{\"schema_version\":1,\"protocol\":\"generic_event_v3\",\"session_nonce\":\""+Nonce+"\",\"kind\":\"action\",\"parent\":null,\"child\":null,\"payload\":{\"version\":\"generic_event_v3\",\"session_nonce\":\""+Nonce+"\",\"decision_id\":\""+Id+"\",\"action_id\":\"choose:0\",\"outcome\":\""+outcome+"\"}}");
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,200,body)==TerminalClassification.Terminal);
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,201,body)==TerminalClassification.Invalid);
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,200,body.Concat(new byte[]{32}).ToArray())==TerminalClassification.Invalid);
        }
    }
}
