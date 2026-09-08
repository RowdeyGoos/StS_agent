using System;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using Sts2AgentBridge.Successors.GenericEventV6;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV6;
internal static class NativeSocketFixture
{
    internal static int Run(string scenario)
    {
        if(scenario.StartsWith("native_item",StringComparison.Ordinal)||scenario is "native_transform" or "native_multi_upgrade" or "native_lost_item")return RunCurrent(scenario);
        string native=scenario switch { "native_binding_wait"=>"BINDING_WAIT", "native_selector_wait" or "native_selector_release"=>"SELECTOR_WAIT", "native_normal" or "native_campaign"=>"NORMAL", "native_derived_hitbox"=>"DERIVED_HITBOX", "native_candidate_card_type"=>"CANDIDATE_CARD_TYPE", "native_unsupported"=>"UNSUPPORTED", _=>throw new ArgumentException("Unknown fixture.") };
        DiagnosticFixture? fixture=null;int owner=Environment.CurrentManagedThreadId,samples=0;bool providerOwner=true,released=false;
        var runtime=GenericEventTransportRuntime.Create((byte[])SocketFixture.Configuration.Clone(),()=>Encoding.ASCII.GetBytes(new string('c',64)),
            (_,nonce)=>{fixture=new DiagnosticFixture(nonce,native);
                if(scenario=="native_campaign") {
                    var upper=new MegaCrit.Sts2.Core.Nodes.Events.NEventOptionButton { Event=fixture.Inner.Model,
                        Option=new MegaCrit.Sts2.Core.Events.EventOption {TextKey="UPPER",Callback=()=>throw new InvalidOperationException("Wrong campaign option")}};
                    upper.Bind("%Text",new MegaCrit.Sts2.addons.mega_text.MegaRichTextLabel{Text="Upper choice"});
                    fixture.Inner.Room.Layout.OptionButtons.Insert(0,upper);
                }
                return new GenericEventV6WireService(nonce,fixture.Session);},()=>{
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
        runtime.StopTransportAndJoin();
        bool gameplayValid=scenario!="native_derived_hitbox"||fixture!.DerivedHitboxCompletionValid;
        bool cleaned=runtime.DisposeServiceOnOwnerFrame();
        Console.Error.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="fixture_complete",parent_dispatches=fixture!.OptionCalls,
            card_dispatches=fixture.SelectCalls+fixture.ConfirmCalls,parent_post_count=runtime.ReservedParentPosts,child_post_count=runtime.ReservedChildPosts,
            read_count=runtime.ReadSubmissionCount,diagnostic_samples=samples,diagnostic_owner=providerOwner,transport_stopped=runtime.TransportStopped,service_disposed=cleaned}));
        fixture.Dispose();return cleaned&&runtime.TransportStopped&&gameplayValid?0:4;
    }
    private static int RunCurrent(string scenario) {
        IDisposable? fixture=null;GenericEventV6Session? session=null;
        Func<int> parents=()=>0,children=()=>0;Func<bool> valid=()=>true;Action<int> advance=_=>{};
        int samples=0,owner=Environment.CurrentManagedThreadId;bool ownerSamples=true;bool released=false;
        bool item=scenario.StartsWith("native_item",StringComparison.Ordinal)||scenario=="native_lost_item";
        if(item)GenericEventTransportRuntime.SetNextNonceForTests(new string('e',32));
        var runtime=GenericEventTransportRuntime.Create((byte[])SocketFixture.Configuration.Clone(),()=>Encoding.ASCII.GetBytes(new string('c',64)),(_,nonce)=>{
            if(item) {
                var f=new global::Program.ItemFixture("SOCKET_HELD_OUT",scenario is "native_item_relic" or "native_item_repeat"?"relic":"potion",
                    delayedCollection:scenario=="native_item_collection",delayedOffer:scenario is "native_item_offer" or "native_item_late_effect",
                    delayedChosen:scenario=="native_item_chosen",repeatItems:scenario is "native_item_repeat" or "native_item_mixed"?2:1,mixed:scenario=="native_item_mixed");
                fixture=f;session=f.Session;f.FaultOffer=scenario=="native_item_failure";
                global::Program.RetireBeforeChosen(f.Room.Layout);
                parents=()=>f.OptionCalls;children=()=>f.CollectCalls+f.SelectCalls+f.ConfirmCalls;
                valid=()=>scenario is "native_item_failure" or "native_item_late_effect" or "native_lost_item"||f.CompletionValid;
                advance=reads=>{if(released||reads<3)return;
                    if(f.HasPendingCollection){released=true;f.AdvanceCollection();}
                    else if(f.HasPendingOffer){released=true;if(scenario=="native_item_late_effect")f.Player.PotionSlots[0]=null;else f.AdvanceOffer();}
                    else if(f.HasPendingChosen){released=true;f.AdvanceChosen();}
                };
            } else if(scenario=="native_transform") {
                var f=new global::Program.TransformFixture("SOCKET_TRANSFORM",2,substitute:true,nonce:nonce);fixture=f;session=f.Session;
                global::Program.RetireBeforeChosen(f.Room.Layout);parents=()=>f.OptionCalls;children=()=>f.SelectCalls+f.ConfirmCalls;valid=()=>f.CompletionValid;
            } else if(scenario=="native_multi_upgrade") {
                var f=new global::Program.MultiUpgradeFixture("SOCKET_UPGRADE",2,nonce:nonce);fixture=f;session=f.Session;
                global::Program.RetireBeforeChosen(f.Room.Layout);parents=()=>f.OptionCalls;children=()=>f.SelectCalls+f.ConfirmCalls;valid=()=>f.CompletionValid;
            } else throw new ArgumentException("Unknown native socket scenario.");
            return new GenericEventV6WireService(nonce,session);
        },()=>{samples++;ownerSamples&=Environment.CurrentManagedThreadId==owner;
            // Fixture sessions own their native adapter; the read-only field is known pure core source.
            var native=(Sts2AgentBridge.Successors.GenericEventV6.Native.PinnedGenericEventV6NativeAdapter)typeof(GenericEventV6Session)
                .GetField("_native",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!.GetValue(session)!;
            return native.LastDiagnostic;
        })!;
        if(scenario=="native_lost_item")runtime.AfterAuthenticatedReservationForTests=()=>{if(runtime.ReservedChildPosts==1)runtime.DropNextPostResponseForTests=true;};
        var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();if(!runtime.StartForTests(listener))return 3;
        Console.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="ready",port=((IPEndPoint)listener.LocalEndpoint).Port}));
        var time=Stopwatch.StartNew();
        while(!runtime.IsTerminalOrStopping&&time.Elapsed.TotalSeconds<30){runtime.DrainFrame();advance(runtime.ReadSubmissionCount);Thread.Sleep(1);}
        runtime.StopTransportAndJoin();bool gameplayValid=valid();bool cleaned=runtime.DisposeServiceOnOwnerFrame();
        Console.Error.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="fixture_complete",parent_dispatches=parents(),card_dispatches=children(),
            parent_post_count=runtime.ReservedParentPosts,child_post_count=runtime.ReservedChildPosts,read_count=runtime.ReadSubmissionCount,
            diagnostic_samples=samples,diagnostic_owner=ownerSamples,transport_stopped=runtime.TransportStopped,service_disposed=cleaned}));
        fixture!.Dispose();return cleaned&&runtime.TransportStopped&&gameplayValid?0:4;
    }
}
