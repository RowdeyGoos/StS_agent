using System;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using Sts2AgentBridge.Successors.GenericEventV7;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV10;
internal static class NativeSocketFixture
{
    internal static int Run(string scenario)
    {
        if(scenario.StartsWith("native_offscreen",StringComparison.Ordinal))return OffscreenSocketFixture.Run(scenario);
        if(scenario.StartsWith("native_item",StringComparison.Ordinal)||scenario.StartsWith("native_variable",StringComparison.Ordinal)||scenario is "native_transform" or "native_multi_upgrade" or "native_lost_item" or "native_aroma")return RunCurrent(scenario);
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
                return new GenericEventV7WireService(nonce,fixture.Session);},()=>{
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
        IDisposable? fixture=null;GenericEventV7Session? session=null;
        Func<int> parents=()=>0,children=()=>0;Func<bool> valid=()=>true;Action<int> advance=_=>{};
        int samples=0,owner=Environment.CurrentManagedThreadId;bool ownerSamples=true;bool released=false;int dropAt=0;int stopAfterReads=0;long lastFrame=0;
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
            } else if(scenario.StartsWith("native_variable",StringComparison.Ordinal)||scenario=="native_aroma") {
                int maximum=scenario=="native_aroma"?1:scenario is "native_variable_min" or "native_variable_max"?3:scenario is "native_variable_eight" or "native_variable_eight_early"?8:4;
                int minimum=scenario is "native_variable_eight" or "native_variable_eight_early"?2:1;
                var f=new global::Program.TransformFixture("AROMA_SHAPED_HELD_OUT",maximum,maximum+2,manual:scenario!="native_aroma",minimum:minimum,
                    partialPreview:scenario=="native_variable_partial",substitute:true,nonce:nonce);
                fixture=f;session=f.Session;f.ContinueWithUpgrade=scenario=="native_variable_mixed";
                global::Program.RetireBeforeChosen(f.Room.Layout);
                if(scenario=="native_aroma") {
                    var lower=new MegaCrit.Sts2.Core.Nodes.Events.NEventOptionButton { Event=f.Model,
                        Option=new MegaCrit.Sts2.Core.Events.EventOption{TextKey="LOWER",Callback=()=>throw new InvalidOperationException("Wrong campaign option")}};
                    lower.Bind("%Text",new MegaCrit.Sts2.addons.mega_text.MegaRichTextLabel{Text="Leave"});f.Room.Layout.OptionButtons.Add(lower);
                }
                parents=()=>f.OptionCalls;children=()=>f.SelectCalls+f.PreviewCalls+f.ConfirmCalls;
                valid=()=>scenario.Contains("oldtag",StringComparison.Ordinal)||scenario.Contains("lost",StringComparison.Ordinal)||
                    f.CompletionValid&&f.PreviewCalls==(scenario is "native_aroma" or "native_variable_max" or "native_variable_eight"?0:1);
                advance=reads=>{if(scenario=="native_variable_partial"&&!released&&reads>=6&&f.HasPendingPreview){released=true;f.AdvancePreview();}};
                dropAt=scenario=="native_variable_lost_preview"?3:scenario=="native_variable_lost_confirm"?4:0;
                stopAfterReads=scenario=="native_variable_oldtag_ready"?2:scenario=="native_variable_oldtag_resolved"?6:0;
            } else if(scenario=="native_transform") {
                var f=new global::Program.TransformFixture("SOCKET_TRANSFORM",2,substitute:true,nonce:nonce);fixture=f;session=f.Session;
                global::Program.RetireBeforeChosen(f.Room.Layout);parents=()=>f.OptionCalls;children=()=>f.SelectCalls+f.ConfirmCalls;valid=()=>f.CompletionValid;
            } else if(scenario=="native_multi_upgrade") {
                var f=new global::Program.MultiUpgradeFixture("SOCKET_UPGRADE",2,nonce:nonce);fixture=f;session=f.Session;
                global::Program.RetireBeforeChosen(f.Room.Layout);parents=()=>f.OptionCalls;children=()=>f.SelectCalls+f.ConfirmCalls;valid=()=>f.CompletionValid;
            } else throw new ArgumentException("Unknown native socket scenario.");
            if(scenario!="native_multi_upgrade")OffscreenSocketFixture.ConfigureAllScreens();
            return new GenericEventV7WireService(nonce,session);
        },()=>{samples++;ownerSamples&=Environment.CurrentManagedThreadId==owner;
            // Fixture sessions own their native adapter; the read-only field is known pure core source.
            var native=(Sts2AgentBridge.Successors.GenericEventV7.Native.PinnedGenericEventV7NativeAdapter)typeof(GenericEventV7Session)
                .GetField("_native",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!.GetValue(session)!;
            return native.LastDiagnostic;
        })!;
        if(scenario=="native_lost_item")dropAt=1;
        if(dropAt>0)runtime.AfterAuthenticatedReservationForTests=()=>{if(runtime.ReservedChildPosts==dropAt)runtime.DropNextPostResponseForTests=true;};
        var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();if(!runtime.StartForTests(listener))return 3;
        Console.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="ready",port=((IPEndPoint)listener.LocalEndpoint).Port}));
        var time=Stopwatch.StartNew();
        while(!runtime.IsTerminalOrStopping&&time.Elapsed.TotalSeconds<30){
            if(runtime.DrainFrame())lastFrame=time.ElapsedMilliseconds;
            advance(runtime.ReadSubmissionCount);
            // A deliberately malformed host envelope ends the client locally. Let its
            // final authenticated response settle, then close this inert fixture only.
            if(stopAfterReads>0&&runtime.ReadSubmissionCount>=stopAfterReads&&time.ElapsedMilliseconds-lastFrame>=500)break;
            Thread.Sleep(1);
        }
        runtime.StopTransportAndJoin();bool gameplayValid=valid();bool cleaned=runtime.DisposeServiceOnOwnerFrame();
        Console.Error.WriteLine(JsonSerializer.Serialize(new{schema_version=1,status="fixture_complete",parent_dispatches=parents(),card_dispatches=children(),
            parent_post_count=runtime.ReservedParentPosts,child_post_count=runtime.ReservedChildPosts,read_count=runtime.ReadSubmissionCount,
            diagnostic_samples=samples,diagnostic_owner=ownerSamples,transport_stopped=runtime.TransportStopped,service_disposed=cleaned}));
        fixture!.Dispose();return cleaned&&runtime.TransportStopped&&gameplayValid?0:4;
    }
}
