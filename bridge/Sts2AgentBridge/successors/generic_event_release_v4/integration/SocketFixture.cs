using System;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using Sts2AgentBridge.Successors.GenericEventV3;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV4;
internal static class SocketFixture
{
    internal static readonly byte[] Configuration=Encoding.UTF8.GetBytes("{\"schema_version\":\"generic_event_v3_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"generic\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static int Main(string[] args)
    {
        if(args.Length!=2 || args[0]!="--fixture")return 2;
        string scenario=args[1];
        if(scenario.StartsWith("native_",StringComparison.Ordinal))return NativeSocketFixture.Run(scenario);
        int owner=Environment.CurrentManagedThreadId,samples=0;bool providerOwner=true;
        int drop=scenario=="lost_parent" ? -1 : scenario=="lost_auto" ? 2 : scenario=="lost_explicit" ? 3 : 0;
        string underlying=scenario=="lost_parent" ? "FOREST_ARCHIVE" : scenario=="lost_auto" ? "reward_auto_fixed" : scenario=="lost_explicit" ? "reward_explicit_fixed" : scenario.StartsWith("provider_",StringComparison.Ordinal)?"FOREST_ARCHIVE":scenario;
        var adapter=new InertFixture.InertEvent(underlying);
        var runtime=GenericEventTransportRuntime.Create((byte[])Configuration.Clone(),()=>Encoding.ASCII.GetBytes(new string('c',64)),
            (_,nonce)=>new GenericEventV3WireService(nonce,new GenericEventV3Session(adapter,nonce)),()=>{
                samples++;providerOwner &= Environment.CurrentManagedThreadId==owner;
                if(scenario=="provider_throw")throw new InvalidOperationException("Synthetic provider fault.");
                return scenario=="provider_invalid"?(GenericEventDiagnosticCode)999:GenericEventDiagnosticCode.NotCaptured;
            })!;
        var listener=new TcpListener(IPAddress.Loopback,0);
        listener.Start();
        if(!runtime.StartForTests(listener))return 3;
        runtime.AfterAuthenticatedReservationForTests=()=>{
            if(drop==-1 && runtime.ReservedParentPosts==1 || drop>0 && runtime.ReservedChildPosts==drop)runtime.DropNextPostResponseForTests=true;
        };
        Console.WriteLine(JsonSerializer.Serialize(new {schema_version=1,status="ready",port=((IPEndPoint)listener.LocalEndpoint).Port}));
        var time=Stopwatch.StartNew();
        while(!runtime.IsTerminalOrStopping && time.Elapsed.TotalSeconds<30){adapter.Advance();runtime.DrainFrame();Thread.Sleep(1);}
        runtime.StopTransportAndJoin();
        bool cleaned=runtime.DisposeServiceOnOwnerFrame();
        Console.Error.WriteLine(JsonSerializer.Serialize(new {schema_version=1,status="fixture_complete",parent_dispatches=adapter.Dispatches,
            card_dispatches=adapter.CardDispatches,parent_post_count=runtime.ReservedParentPosts,child_post_count=runtime.ReservedChildPosts,
            read_count=runtime.ReadSubmissionCount,diagnostic_samples=samples,diagnostic_owner=providerOwner,transport_stopped=runtime.TransportStopped,service_disposed=cleaned}));
        return cleaned && runtime.TransportStopped ? 0 : 4;
    }
}
