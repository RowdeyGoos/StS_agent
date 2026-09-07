using System;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using Sts2AgentBridge.Successors.GenericEventV3;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV4;
internal static class NativeSocketFixture
{
    internal static int Run(string scenario)
    {
        string native=scenario switch { "native_binding_wait"=>"BINDING_WAIT", "native_selector_wait" or "native_selector_release"=>"SELECTOR_WAIT", "native_normal"=>"NORMAL", "native_candidate_card_type"=>"CANDIDATE_CARD_TYPE", "native_unsupported"=>"UNSUPPORTED", _=>throw new ArgumentException("Unknown fixture.") };
        DiagnosticFixture? fixture=null;int owner=Environment.CurrentManagedThreadId,samples=0;bool providerOwner=true,released=false;
        var runtime=GenericEventTransportRuntime.Create((byte[])SocketFixture.Configuration.Clone(),()=>Encoding.ASCII.GetBytes(new string('c',64)),
            (_,nonce)=>{fixture=new DiagnosticFixture(nonce,native);return new GenericEventV3WireService(nonce,fixture.Session);},()=>{
                samples++;providerOwner &= Environment.CurrentManagedThreadId==owner;return fixture!.Adapter.LastDiagnostic;
            })!;
        var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();if(!runtime.StartForTests(listener))return 3;
        Console.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="ready",port=((IPEndPoint)listener.LocalEndpoint).Port}));
        var time=Stopwatch.StartNew();
        while(!runtime.IsTerminalOrStopping&&time.Elapsed.TotalSeconds<30)
        {
            fixture!.Advance();runtime.DrainFrame();
            if(scenario=="native_selector_release"&&!released&&samples>=3){fixture.RestoreGeometry();released=true;}
            Thread.Sleep(1);
        }
        runtime.StopTransportAndJoin();bool cleaned=runtime.DisposeServiceOnOwnerFrame();
        Console.Error.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="fixture_complete",parent_dispatches=fixture!.OptionCalls,
            card_dispatches=fixture.SelectCalls+fixture.ConfirmCalls,parent_post_count=runtime.ReservedParentPosts,child_post_count=runtime.ReservedChildPosts,
            read_count=runtime.ReadSubmissionCount,diagnostic_samples=samples,diagnostic_owner=providerOwner,transport_stopped=runtime.TransportStopped,service_disposed=cleaned}));
        fixture.Dispose();return cleaned&&runtime.TransportStopped?0:4;
    }
}
