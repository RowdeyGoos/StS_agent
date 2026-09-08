using System;
using System.Diagnostics;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV10;

internal static class OffscreenSocketFixture
{
    // Inert fixture setup only: preserve the original screen factory, configure
    // its public geometry before the actual observational ShowScreen hook runs.
    internal static void ConfigureAllScreens()
    {
        var original=NDeckTransformSelectScreen.Factory ?? throw new InvalidOperationException("Missing inert factory.");
        NDeckTransformSelectScreen.Factory=(cards,factory,prefs)=>{
            var screen=original(cards,factory,prefs);
            OffscreenGeometry.Configure(screen,"all_below");
            return screen;
        };
    }

    internal static int Run(string scenario)
    {
        if(scenario is not ("native_offscreen_success" or "native_offscreen_missing" or "native_offscreen_disabled" or
            "native_offscreen_reassign" or "native_offscreen_deferred_reassign" or "native_offscreen_lost"))throw new ArgumentException("Unknown card16 fixture.");
        global::Program.TransformFixture? fixture=null;
        OffscreenGeometry? geometry=null;
        int samples=0,owner=Environment.CurrentManagedThreadId;
        bool ownerSamples=true,changed=false;Action? deferred=null;
        var runtime=GenericEventTransportRuntime.Create((byte[])SocketFixture.Configuration.Clone(),
            ()=>Encoding.ASCII.GetBytes(new string('c',64)),(_,nonce)=>{
                fixture=new global::Program.TransformFixture("CARD16_HELD_OUT",1,scenario=="native_offscreen_missing"?15:20,substitute:true,nonce:nonce);
                global::Program.RetireBeforeChosen(fixture.Room.Layout);
                var lower=new MegaCrit.Sts2.Core.Nodes.Events.NEventOptionButton { Event=fixture.Model,
                    Option=new MegaCrit.Sts2.Core.Events.EventOption{TextKey="LEAVE",Callback=()=>throw new InvalidOperationException("Wrong initial option.")}};
                lower.Bind("%Text",new MegaCrit.Sts2.addons.mega_text.MegaRichTextLabel{Text="Leave"});
                fixture.Room.Layout.OptionButtons.Add(lower);
                var original=NDeckTransformSelectScreen.Factory!;
                NDeckTransformSelectScreen.Factory=(cards,factory,prefs)=>{
                    var screen=original(cards,factory,prefs);
                    geometry=OffscreenGeometry.Configure(screen);
                    if(scenario=="native_offscreen_disabled")geometry.Mutate("disabled");
                    if(scenario=="native_offscreen_deferred_reassign")geometry.Holders[15].FixtureGuiInputDispatch=action=>deferred=action;
                    return screen;
                };
                return new GenericEventV7WireService(nonce,fixture.Session);
            },()=>{
                samples++;ownerSamples&=Environment.CurrentManagedThreadId==owner;
                var native=(PinnedGenericEventV7NativeAdapter)typeof(GenericEventV7Session)
                    .GetField("_native",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!.GetValue(fixture!.Session)!;
                return native.LastDiagnostic;
            })!;
        if(scenario=="native_offscreen_lost")runtime.AfterAuthenticatedReservationForTests=()=>{
            if(runtime.ReservedChildPosts==1)runtime.DropNextPostResponseForTests=true;
        };
        var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();if(!runtime.StartForTests(listener))return 3;
        Console.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="ready",port=((IPEndPoint)listener.LocalEndpoint).Port}));
        var time=Stopwatch.StartNew();
        while(!runtime.IsTerminalOrStopping&&time.Elapsed.TotalSeconds<30)
        {
            runtime.DrainFrame();
            if(!changed&&runtime.ReadSubmissionCount>=2&&scenario is "native_offscreen_reassign")
            {
                changed=true;
                geometry!.Mutate("holder");
            }
            if(!changed&&scenario=="native_offscreen_deferred_reassign"&&deferred is not null)
            {
                changed=true;geometry!.Mutate("model");
                try { deferred(); }
                catch(InvalidOperationException error) when(error.Message=="Sequence contains no matching element") { }
            }
            Thread.Sleep(1);
        }
        runtime.StopTransportAndJoin();
        bool positive=scenario=="native_offscreen_success";
        bool dispatched=positive||scenario is "native_offscreen_lost" or "native_offscreen_deferred_reassign";
        bool valid=geometry is not null&&geometry.DispatchCount==(dispatched?1:0)&&
            geometry.DispatchedSlots.SequenceEqual(dispatched?new[]{15}:Array.Empty<int>())&&
            fixture!.SelectCalls==(dispatched?1:0)&&fixture.ConfirmCalls==(positive?1:0)&&
            (!positive||(fixture.CompletionValid&&fixture.Originals.Count==1&&ReferenceEquals(fixture.Originals[0],fixture.Cards[15])&&fixture.Map.IsOpen));
        bool cleaned=runtime.DisposeServiceOnOwnerFrame();
        Console.Error.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="fixture_complete",parent_dispatches=fixture!.OptionCalls,
            card_dispatches=fixture.SelectCalls+fixture.PreviewCalls+fixture.ConfirmCalls,
            parent_post_count=runtime.ReservedParentPosts,child_post_count=runtime.ReservedChildPosts,
            read_count=runtime.ReadSubmissionCount,diagnostic_samples=samples,diagnostic_owner=ownerSamples,
            transport_stopped=runtime.TransportStopped,service_disposed=cleaned}));
        fixture.Dispose();return valid&&cleaned&&runtime.TransportStopped?0:4;
    }
}
