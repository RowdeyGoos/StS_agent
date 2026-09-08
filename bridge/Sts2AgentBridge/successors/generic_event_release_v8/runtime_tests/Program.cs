using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using System;
using System.Linq;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.GenericEventV7;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV8;
internal static class Program
{
    private const string Nonce="0123456789abcdef0123456789abcdef";
    private static readonly string Id=new('a',64);
    private static readonly byte[] Config=Encoding.UTF8.GetBytes("{\"schema_version\":\"generic_event_v8_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"generic\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static int _checks;
    private static void Check(bool value){_checks++;if(!value)throw new InvalidOperationException("Assertion "+_checks);}
    private static void Spin(Func<bool> predicate){var s=Stopwatch.StartNew();while(!predicate()){if(s.ElapsedMilliseconds>2000)throw new TimeoutException();Thread.Sleep(1);}}
    private static GenericEventTransportRuntime Create(InertFixture.InertEvent? adapter=null)=>GenericEventTransportRuntime.Create((byte[])Config.Clone(),()=>Encoding.ASCII.GetBytes(new string('c',64)),(_,nonce)=>new GenericEventV7WireService(nonce,new GenericEventV7Session(adapter??new("FOREST_ARCHIVE"),nonce)))!;
    private static int Main()
    {
        try{ThreadPool.SetMinThreads(8,8);Protocol();Ownership();Budgets();QueueLate();DiagnosticQueue();DiagnosticCleanup();Classifiers();TypedClassifiers();NonceOwnership();Console.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="passed",suite="generic_event_release_runtime",check_count=_checks}));return 0;}
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
    private static byte[] Request(string action="",int ordinal=0)=>Encoding.ASCII.GetBytes((action==""?"GET /probe/generic-event-v7/public/decision":"POST /probe/generic-event-v7/public/action")+" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer "+new string('c',64)+"\r\nAccept: application/json\r\n"+(action==""?"":"X-Sts2-Decision-Id: "+Id+"\r\nX-Sts2-Action-Id: "+action+"\r\n"+(ordinal==0?"":"X-Sts2-Child-Ordinal: "+ordinal+"\r\nX-Sts2-Parent-Decision-Id: "+Id+"\r\nX-Sts2-Parent-Action-Id: choose:0\r\n"))+"Connection: close\r\n\r\n");
    private static bool Parse(byte[] request)=>GenericEventTransportRequestParser.TryParse(request,GenericEventReleaseSelection.Generic,out _);
    private static void Protocol()
    {
        Check(GenericEventTransportConfiguration.TryParse(Config,out var selection)&&selection==GenericEventReleaseSelection.Generic);
        Check(!GenericEventTransportConfiguration.TryParse(Config.Concat(new byte[]{10}).ToArray(),out _));Check(Parse(Request()));
        for(int i=0;i<8;i++)Check(Parse(Request("choose:"+i)));
        for(int i=0;i<64;i++)Check(Parse(Request("select:"+i,1)));
        for(int i=0;i<256;i++)Check(Parse(Request("collect:"+i,4)));
        foreach(string action in new[]{"collect:256","collect:00","collect:-1","collect:","collect:000","collect:999"})Check(!Parse(Request(action,1)));
        Check(GenericEventTransportServiceBody.Build(Id,"collect:255",4,Id,"choose:7").Length==248);
        Check(Request("collect:255",4).Length==481);
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
    private static void DiagnosticCleanup()
    {
        var field=typeof(GenericEventTransportRuntime).GetField("_diagnosticProvider",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!;
        var adapter=new InertFixture.InertEvent("FOREST_ARCHIVE"){ThrowFirstDispose=true};int samples=0;
        var runtime=GenericEventTransportRuntime.Create((byte[])Config.Clone(),()=>Encoding.ASCII.GetBytes(new string('c',64)),
            (_,nonce)=>new GenericEventV7WireService(nonce,new GenericEventV7Session(adapter,nonce)),()=>{samples++;return GenericEventDiagnosticCode.ParentReady;})!;
        Check(field.GetValue(runtime) is not null);runtime.StopTransportAndJoin();
        Check(!runtime.DisposeServiceOnOwnerFrame()&&field.GetValue(runtime) is not null);
        Check(runtime.DisposeServiceOnOwnerFrame()&&field.GetValue(runtime) is null&&samples==0);
        int cleanup=0;
        runtime=GenericEventTransportRuntime.Create((byte[])Config.Clone(),()=>Encoding.ASCII.GetBytes(new string('c',64)),
            (_,_)=>throw new GenericEventTransportFactoryFailure(()=>{if(++cleanup==1)throw new Exception();}),()=>{samples++;return GenericEventDiagnosticCode.ChildReady;})!;
        Check(runtime.TransportStopped&&!runtime.Start());
        Check(!runtime.DisposeServiceOnOwnerFrame()&&field.GetValue(runtime) is not null&&samples==0);
        Check(runtime.DisposeServiceOnOwnerFrame()&&field.GetValue(runtime) is null&&samples==0);
    }

    private static void DiagnosticQueue()
    {
        var expected = new[] { "none", "parent_ready", "parent_unavailable", "parent_waiting", "pending_binding_failed", "pending_ownership", "pending_context", "pending_task_failed", "pending_chosen_entry", "pending_chosen_task", "pending_chosen_completion", "pending_request_task", "pending_screen", "pending_selectorless_request", "pending_overlay", "pending_deck", "pending_offers", "pending_proceed", "prepare_binding", "prepare_screen", "prepare_external_selector", "prepare_deck", "prepare_foreground", "prepare_family", "prepare_grid_node", "prepare_grid_state", "prepare_holders", "prepare_candidates", "prepare_geometry", "prepare_preview_nodes", "prepare_preview_state", "prepare_confirm", "child_ready", "map_ready", "capture_disposed", "capture_exception", "diagnostic_unavailable", "candidate_expected_null", "candidate_expected_duplicate", "candidate_displayed_null", "candidate_unexpected_model", "candidate_displayed_duplicate", "candidate_model_null", "candidate_card_null", "candidate_hitbox_null", "candidate_highlight_null", "candidate_card_type", "candidate_card_invalid", "candidate_hitbox_type", "candidate_hitbox_invalid", "candidate_highlight_type", "candidate_highlight_invalid", "candidate_material_null", "candidate_material_kind", "candidate_material_type", "candidate_material_invalid", "candidate_stable_key", "candidate_domain_count", "candidate_domain_bounds", "candidate_snapshot_count", "candidate_holder_identity", "candidate_holder_type", "candidate_holder_invalid", "candidate_model_identity", "candidate_card_identity", "candidate_hitbox_identity", "candidate_highlight_identity", "candidate_material_identity", "candidate_key_changed", "candidate_level_changed", "candidate_shader_read", "candidate_highlight_unsettled", "candidate_initially_selected", "candidate_holder_invisible", "candidate_card_invisible", "candidate_hitbox_invisible", "candidate_enabled_read", "candidate_none_enabled" };
        for(int i=0;i<expected.Length;i++)
        {
            Check(GenericEventDiagnosticCodec.Encode((GenericEventDiagnosticCode)i)==expected[i]);
            Check(GenericEventDiagnosticCodec.Normalize((GenericEventDiagnosticCode)i)==(GenericEventDiagnosticCode)i);
            byte[] http=GenericEventTransportHttpEncoder.Wrap(Encoding.ASCII.GetBytes("{}"),(GenericEventDiagnosticCode)i);
            Check(Encoding.ASCII.GetString(http).EndsWith("X-Sts2-Native-Diagnostic: "+expected[i]+"\r\nConnection: close\r\n\r\n{}",StringComparison.Ordinal));Array.Clear(http);
        }
        Check(Enum.GetValues<GenericEventDiagnosticCode>().Length==78);
        Check((int)GenericEventDiagnosticCode.DiagnosticUnavailable==36);
        Check(GenericEventDiagnosticCodec.Normalize((GenericEventDiagnosticCode)78)==GenericEventDiagnosticCode.DiagnosticUnavailable);
        Check(GenericEventDiagnosticCodec.Encode((GenericEventDiagnosticCode)78)=="diagnostic_unavailable");
        Check(GenericEventDiagnosticCodec.Encode((GenericEventDiagnosticCode)(-1))=="diagnostic_unavailable");
        Check(GenericEventDiagnosticCodec.Normalize((GenericEventDiagnosticCode)int.MinValue)==GenericEventDiagnosticCode.DiagnosticUnavailable);
        Check(GenericEventDiagnosticCodec.Normalize((GenericEventDiagnosticCode)int.MaxValue)==GenericEventDiagnosticCode.DiagnosticUnavailable);
        Check(GenericEventDiagnosticCodec.Encode((GenericEventDiagnosticCode)int.MinValue)=="diagnostic_unavailable");
        Check(GenericEventDiagnosticCodec.Encode((GenericEventDiagnosticCode)int.MaxValue)=="diagnostic_unavailable");
        Check(GenericEventDiagnosticCodec.Encode((GenericEventDiagnosticCode)999)=="diagnostic_unavailable");
        Check(GenericEventDiagnosticCodec.Normalize((GenericEventDiagnosticCode)(-1))==GenericEventDiagnosticCode.DiagnosticUnavailable);
        using(var queue=new OwnedByteFrameQueue(()=>{}))
        {
            int calls=0,thread=0;GenericEventDiagnosticCode current=GenericEventDiagnosticCode.PrepareGeometry;
            var submit=Task.Run(()=>queue.Submit(()=>{calls++;thread=Environment.CurrentManagedThreadId;return new(200,Encoding.ASCII.GetBytes("first"),current);}));
            Spin(()=>queue.OutstandingCount==1);int owner=Environment.CurrentManagedThreadId;queue.DrainFrame();current=GenericEventDiagnosticCode.ChildReady;
            var response=submit.Result;Check(calls==1&&thread==owner);Check(response.Diagnostic==GenericEventDiagnosticCode.PrepareGeometry&&Encoding.ASCII.GetString(response.Value!)=="first");Array.Clear(response.Value!);
            queue.Stop();Check(queue.WaitForSettled(1000));
        }
        foreach(bool stop in new[]{false,true})
        {
            var queue=new OwnedByteFrameQueue(()=>{});using var entered=new ManualResetEventSlim();using var release=new ManualResetEventSlim();byte[] late=Encoding.ASCII.GetBytes("late diagnostic");
            var submit=Task.Run(()=>queue.Submit(()=>{entered.Set();release.Wait();return new(200,late,GenericEventDiagnosticCode.PrepareConfirm);}));
            Spin(()=>queue.OutstandingCount==1);var drain=Task.Run(()=>queue.DrainFrame());Check(entered.Wait(1000));if(stop)queue.Stop();
            var response=submit.Result;Check(response.Value is null&&response.Diagnostic==GenericEventDiagnosticCode.NotCaptured);release.Set();drain.Wait();Check(late.All(x=>x==0));queue.Stop();Check(queue.WaitForSettled(1000));queue.Dispose();
        }
    }

    private static void NonceOwnership()
    {
        var field=typeof(GenericEventTransportRuntime).GetField("_nonce",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!;
        foreach(string bad in new[]{"",new string('A',32),new string('e',31),new string('e',33),new string('g',32)}) {
            bool failed=false;try{GenericEventTransportRuntime.SetNextNonceForTests(bad);}catch(InvalidOperationException){failed=true;}Check(failed);
        }
        GenericEventTransportRuntime.SetNextNonceForTests(Nonce);
        bool duplicate=false;try{GenericEventTransportRuntime.SetNextNonceForTests(new string('f',32));}catch(InvalidOperationException){duplicate=true;}Check(duplicate);
        var runtime=Create();Check((string)field.GetValue(runtime)! == Nonce);runtime.StopTransportAndJoin();Check(runtime.DisposeServiceOnOwnerFrame());
        runtime=Create();Check((string)field.GetValue(runtime)! != Nonce);runtime.StopTransportAndJoin();Check(runtime.DisposeServiceOnOwnerFrame());
        GenericEventTransportRuntime.SetNextNonceForTests(Nonce);
        Check(GenericEventTransportRuntime.Create(Encoding.ASCII.GetBytes("{}"),()=>throw new Exception(),(_,_)=>throw new Exception()) is null);
        runtime=Create();Check((string)field.GetValue(runtime)! != Nonce);runtime.StopTransportAndJoin();Check(runtime.DisposeServiceOnOwnerFrame());
    }
    private static void TypedClassifiers()
    {
        object descriptor=new {ordinal=1,parent_decision_id=Id,parent_action_id="choose:0",kind="item",contract_version="item_v1",offer_count=1};
        TerminalClassification Classify(object payload,bool apply=false,object? child=null) {
            byte[] body=JsonSerializer.SerializeToUtf8Bytes(new{schema_version=1,protocol="generic_event_v7",session_nonce=Nonce,kind=apply?"action":"decision",
                parent=apply?null:(object)new{status="child",phase="child_active"},child=child??descriptor,payload});
            return GenericEventTerminalClassifier.Classify(apply?GenericEventTransportRoute.ChildPost:GenericEventTransportRoute.DecisionGet,GenericEventReleaseSelection.Generic,Nonce,200,body);
        }
        object Basic(string status)=>new{schema_version=1,protocol="item_probe_v1",version="item_v1",session_nonce=Nonce,surface_ordinal=1,status};
        Check(Classify(Basic("waiting"))==TerminalClassification.NonTerminal);
        Check(Classify(Basic("unsupported"))==TerminalClassification.Terminal);
        foreach(string status in new[]{"rejected","unsupported","uncertain"})Check(Classify(Basic(status),true)==TerminalClassification.Terminal);
        Check(Classify(Basic("accepted"),true)==TerminalClassification.Invalid);
        var accepted=new{schema_version=1,protocol="item_probe_v1",version="item_v1",session_nonce=Nonce,surface_ordinal=1,status="accepted",decision_id=Id,action_id="collect:255"};
        Check(Classify(accepted,true)==TerminalClassification.NonTerminal);
        Check(Classify(accepted)==TerminalClassification.Invalid);
        object Resolved(string version="item_v1",int index=255,string action="collect:255")=>new{schema_version=1,protocol="item_probe_v1",version,session_nonce=Nonce,surface_ordinal=1,status="resolved",decision_id=Id,action_id=action,offer_index=index,kind="relic",key="RELIC_A",result="collected"};
        Check(Classify(Resolved())==TerminalClassification.NonTerminal);
        Check(Classify(Resolved(),true)==TerminalClassification.Invalid);
        Check(Classify(Resolved("card_selection_v1"))==TerminalClassification.Invalid);
        Check(Classify(Resolved(index:254))==TerminalClassification.Invalid);
        Check(Classify(Resolved(action:"collect:256"))==TerminalClassification.Invalid);
        object Ready(string kind="relic",bool enabled=true,int count=1,int index=255,string action="collect:255")=>new{schema_version=1,protocol="item_probe_v1",version="item_v1",session_nonce=Nonce,surface_ordinal=1,status="ready",decision_id=Id,
            offers=Enumerable.Range(0,count).Select(_=>new{index,kind,key="RELIC_A",enabled}).ToArray(),potion_slots=new[]{"POTION_A"},legal_actions=new[]{action}};
        Check(Classify(Ready())==TerminalClassification.NonTerminal);
        Check(Classify(Ready(kind:"potion"))==TerminalClassification.Invalid);
        Check(Classify(Ready(enabled:false))==TerminalClassification.Invalid);
        Check(Classify(Ready(count:2))==TerminalClassification.Invalid);
        Check(Classify(Ready(index:254))==TerminalClassification.Invalid);
        Check(Classify(Ready(action:"select:0"))==TerminalClassification.Invalid);
        var transform=new{ordinal=1,parent_decision_id=Id,parent_action_id="choose:0",kind="card_selection",contract_version="card_transform_v2",operation="transform",min_select=2,max_select=2,commit_mode="preview_confirm",domain_count=3};
        object Card(string version,string kind="child_resolved",string status="resolved")=>new{schema_version=1,kind,version,session_nonce=Nonce,parent_ordinal=1,status};
        Check(Classify(Card("card_transform_v2"),child:transform)==TerminalClassification.NonTerminal);
        Check(Classify(Card("card_selection_v1"),child:transform)==TerminalClassification.Invalid);
        Check(Classify(Card("card_transform_v1"),child:transform)==TerminalClassification.Invalid);
        var variable=new{ordinal=1,parent_decision_id=Id,parent_action_id="choose:0",kind="card_selection",contract_version="card_transform_v2",operation="transform",min_select=1,max_select=3,commit_mode="preview_confirm",domain_count=4};
        Check(Classify(Card("card_transform_v2"),child:variable)==TerminalClassification.NonTerminal);
        Check(Classify(Card("card_transform_v2","child_observation","ready"),child:variable)==TerminalClassification.NonTerminal);
        Check(Classify(Card("card_transform_v2","child_observation","waiting"),child:variable)==TerminalClassification.NonTerminal);
        Check(Classify(Card("card_transform_v1"),child:variable)==TerminalClassification.Invalid);
        var old=new{ordinal=1,parent_decision_id=Id,parent_action_id="choose:0",kind="card_selection",contract_version="card_transform_v1",operation="transform",min_select=1,max_select=3,commit_mode="preview_confirm",domain_count=4};
        Check(Classify(Card("card_transform_v1"),child:old)==TerminalClassification.Invalid);
        foreach(string action in new[]{"preview","confirm"})foreach(string version in new[]{"card_transform_v1","card_transform_v2"})
        {
            object receipt=new{schema_version=1,kind="child_receipt",version,session_nonce=Nonce,parent_ordinal=1,decision_id=Id,action_id=action,outcome="accepted"};
            Check(Classify(receipt,true,variable)==(version=="card_transform_v2"?TerminalClassification.NonTerminal:TerminalClassification.Invalid));
        }
        foreach(string version in new[]{"card_transform_v1","card_transform_v2"})
        {
            object failure=new{schema_version=1,kind="child_failure",version,session_nonce=Nonce,parent_ordinal=1,outcome="uncertain"};
            Check(Classify(failure,true,variable)==(version=="card_transform_v2"?TerminalClassification.Terminal:TerminalClassification.Invalid));
        }
        Check(Classify(Card("card_transform_v2","child_observation","unsupported"),child:transform)==TerminalClassification.Terminal);
        Check(Classify(Resolved(),child:transform)==TerminalClassification.Invalid);
        Check(Classify(Card("card_transform_v2"))==TerminalClassification.Invalid);
    }

    private static void Classifiers()
    {
        foreach(string scenario in new[]{"FOREST_ARCHIVE","removal_fixed","reward_auto_fixed","reward_explicit_fixed","mixed_three"})
        {
            var adapter=new InertFixture.InertEvent(scenario);using var service=new GenericEventV7WireService(Nonce,new GenericEventV7Session(adapter,Nonce));int childResolved=0;
            for(int i=0;i<150;i++)
            {
                adapter.Advance();byte[] response=service.Handle("GET","/probe/generic-event-v7/public/decision",null);using var doc=JsonDocument.Parse(response);var root=doc.RootElement;var parent=root.GetProperty("parent");
                var classified=GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.DecisionGet,GenericEventReleaseSelection.Generic,Nonce,200,response);
                if(parent.GetProperty("status").GetString()=="complete"){Check(classified==TerminalClassification.Terminal&&childResolved==(scenario=="mixed_three"?3:1));break;}
                Check(classified==TerminalClassification.NonTerminal);
                bool child=root.GetProperty("child").ValueKind!=JsonValueKind.Null;var view=child?root.GetProperty("payload"):parent;
                if(child&&view.GetProperty("kind").GetString()=="child_resolved"){childResolved++;continue;}
                if(view.GetProperty("status").GetString()!="ready")continue;
                string id=view.GetProperty("decision_id").GetString()!,action=view.GetProperty("legal_actions")[0].GetString()!;var descriptor=root.GetProperty("child");
                var body=GenericEventTransportServiceBody.Build(id,action,child?descriptor.GetProperty("ordinal").GetInt32():0,child?descriptor.GetProperty("parent_decision_id").GetString():null,child?descriptor.GetProperty("parent_action_id").GetString():null);
                var receipt=service.Handle("POST","/probe/generic-event-v7/public/action",body);Check(GenericEventTerminalClassifier.Classify(child?GenericEventTransportRoute.ChildPost:GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,200,receipt)==TerminalClassification.NonTerminal);
            }
        }
        foreach(string outcome in new[]{"unsupported","uncertain","rejected"})
        {
            byte[] response=JsonSerializer.SerializeToUtf8Bytes(new {schema_version=1,protocol="generic_event_v7",session_nonce=Nonce,kind="action",parent=(object?)null,
                child=new {ordinal=1,parent_decision_id=Id,parent_action_id="choose:0",kind="card_selection",contract_version="card_selection_v1",operation="add",min_select=1,max_select=2,commit_mode="auto_at_max",domain_count=3},
                payload=new {schema_version=1,kind="child_failure",version="card_selection_v1",session_nonce=Nonce,parent_ordinal=1,outcome}});
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ChildPost,GenericEventReleaseSelection.Generic,Nonce,200,response)==TerminalClassification.Terminal);
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,200,response)==TerminalClassification.Invalid);
        }
        foreach(string outcome in new[]{"stale_decision","illegal_action","unsupported","uncertain","budget_exhausted"})
        {
            byte[] body=Encoding.UTF8.GetBytes("{\"schema_version\":1,\"protocol\":\"generic_event_v7\",\"session_nonce\":\""+Nonce+"\",\"kind\":\"action\",\"parent\":null,\"child\":null,\"payload\":{\"version\":\"generic_event_v7\",\"session_nonce\":\""+Nonce+"\",\"decision_id\":\""+Id+"\",\"action_id\":\"choose:0\",\"outcome\":\""+outcome+"\"}}");
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,200,body)==TerminalClassification.Terminal);
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,201,body)==TerminalClassification.Invalid);
            Check(GenericEventTerminalClassifier.Classify(GenericEventTransportRoute.ParentPost,GenericEventReleaseSelection.Generic,Nonce,200,body.Concat(new byte[]{32}).ToArray())==TerminalClassification.Invalid);
        }
    }
}
