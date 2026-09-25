using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using Sts2AgentBridge.Items.Native;

internal static partial class Program
{
    private sealed class PickupLease : IDisposable
    {
        private readonly Action _exit;
        internal PickupLease(Action exit)=>_exit=exit;
        public void Dispose()=>_exit();
    }
    private sealed class SequentialPickupRelic : RelicModel
    {
        internal RelicModel[] Children=Array.Empty<RelicModel>();
        internal Task? ExternalOffer;
        internal Action? AfterChildren;
        [MethodImpl(MethodImplOptions.NoInlining)]public override async Task AfterObtained()
        {
            if(ExternalOffer is {} offer)await offer;
            else foreach(var child in Children)await RelicCmd.Obtain(child,Owner!);
            AfterChildren?.Invoke();
        }
    }
    private static void RelicPickupChainCases()
    {
        foreach(string mode in new[]{"shared_task","asynchronous","deferred_entry","external_child","external_async_child","external_foreign","completed_frame","child_fault","cleanup_failure","wrong_child","owner_lost","foreign_effect"})
        {
            using var world=new Fixture("PICKUP_CHAIN");var player=world.Player;
            foreach(var card in world.Cards)card.Owner=player;
            var gate=new TaskCompletionSource();var entry=new TaskCompletionSource();var offer=new TaskCompletionSource();
            RelicModel first=mode is "asynchronous" or "external_async_child" or "child_fault" or "owner_lost" or "foreign_effect" ? new OldCoin{Gate=gate.Task} : new RelicModel();
            first.Id.Entry="FIRST";var second=new RelicModel();second.Id.Entry="SECOND";
            var root=new SequentialPickupRelic{Children=new[]{first,second}};root.Id.Entry="ROOT";
            if(mode.StartsWith("external_",StringComparison.Ordinal))root.ExternalOffer=offer.Task;
            var effects=new Dictionary<PinnedRelicPickupChain.Frame,PinnedAutomaticRelicEffects>();
            var expected=new Dictionary<PinnedRelicPickupChain.Frame,PinnedAutomaticRelicEffects.State>();
            int cleaned=0,certified=0;bool owner=true,advanced=false;
            PinnedRelicPickupChain? chain=null;
            chain=new(player,root,()=>owner,
                (parent,child)=>ReferenceEquals(parent.Relic,root)&&mode!="wrong_child"&&root.Children.Contains(child),
                frame=>{
                    if(frame.Parent is {} parent)Check(expected[parent].Same(frame.Before),"child starts at the preceding exact certified inventory");
                    expected[frame]=new(player);
                    if(ReferenceEquals(frame.Relic,root))return new PickupLease(()=>{});
                    var observer=new PinnedAutomaticRelicEffects(player,frame.Relic,()=>owner);effects.Add(frame,observer);
                    var old=observer.Enter();return new PickupLease(()=>PinnedAutomaticRelicEffects.Exit(old));
                },
                frame=>effects.TryGetValue(frame,out var effect)?effect.Valid():expected[frame].Same(new(player)),
                frame=>{
                    if(effects.TryGetValue(frame,out var effect)){effect.Dispose();effects.Remove(frame);cleaned++;}
                    if(mode=="cleanup_failure"&&ReferenceEquals(frame.Relic,first))throw new InvalidOperationException("fixture cleanup failed");
                },
                frame=>{certified++;if(frame.Parent is {} parent)expected[parent]=frame.Certificate!;});
            root.AfterChildren=()=>{chain.BeforeAdvance(chain.NativeFrame!);Check(chain.Root!.Children.All(c=>c.Certificate is not null),"last direct pickup is certified before the next parent effect");advanced=true;};
            Task<RelicModel>? obtain=null;Task? caller=null;
            async Task Delayed(){await entry.Task;obtain=RelicCmd.Obtain(root,player);await obtain;}
            bool failed=false;
            try {
                chain.Invoke(()=>{if(mode=="deferred_entry")caller=Delayed();else obtain=RelicCmd.Obtain(root,player);});
                if(mode=="deferred_entry"){Check(chain.Root is null&&!chain.Completed,"delayed native entry remains pending under actual dispatch context");entry.SetResult();Check(caller!.IsCompletedSuccessfully,"deferred caller completes");}
                if(mode.StartsWith("external_",StringComparison.Ordinal)) {
                    Check(chain.NativeFrame is null&&chain.Root is {Entered:true,AfterTask.IsCompleted:false},"root awaits an owned reward outside the next input context");
                    if(mode=="external_foreign")_ = RelicCmd.Obtain(first,player);
                    else {
                        Task<RelicModel>? childTask=null;
                        chain.InvokeChildInput(chain.Root!,()=>childTask=RelicCmd.Obtain(first,player));
                        if(mode=="external_async_child") {Check(childTask is {IsCompleted:false}&&!chain.Completed,"new input retains asynchronous child task");gate.SetResult();}
                        Check(childTask!.IsCompletedSuccessfully&&chain.NativeFrame is null,"child input restores caller context");
                        chain.InvokeChildInput(chain.Root!,()=>childTask=RelicCmd.Obtain(second,player));
                        Check(childTask!.IsCompletedSuccessfully,"second owned child input completes");
                        offer.SetResult();
                    }
                }
                if(mode is "asynchronous" or "child_fault" or "owner_lost" or "foreign_effect") {
                    Check(chain.Root!.Children.Count==1&&!chain.Completed&&second.Owner is null,"unfinished first pickup prevents successor entry");
                    if(mode=="owner_lost")owner=false;
                    if(mode=="foreign_effect")player.Gold++;
                    if(mode=="child_fault")gate.SetException(new InvalidOperationException("fixture pickup fault"));else gate.SetResult();
                }
                if(mode=="completed_frame")chain.InvokeChildInput(chain.Root!,()=>throw new Exception("completed frame input must not execute"));
                Check(chain.Completed,"successful native invocation tree completed");
            }catch(InvalidOperationException){failed=true;}
            bool expectedFailure=mode is "child_fault" or "cleanup_failure" or "wrong_child" or "owner_lost" or "foreign_effect" or "external_foreign" or "completed_frame";
            Check(failed==expectedFailure,"pickup chain outcome: "+mode);
            if(!failed) {
                Check(advanced&&certified==3&&cleaned==2&&obtain!.IsCompletedSuccessfully&&ReferenceEquals(obtain.Result,root),"exact root and both child results retained");
                Check(player.Relics.TakeLast(3).SequenceEqual(new[]{root,first,second}),"actual sequential relic identities retained");
                if(mode is "shared_task" or "deferred_entry")Check(ReferenceEquals(chain.Root!.Children[0].AfterTask,chain.Root.Children[1].AfterTask),"native shared completed task is legal across distinct invocations");
            } else if(mode!="completed_frame")Check(second.Owner is null&&!advanced,"failed predecessor prevents next native pickup/effect");
            for(int i=0;i<2;i++) {bool cleanupFailed=false;try{chain.Dispose();}catch(InvalidOperationException){cleanupFailed=true;}Check(cleanupFailed==expectedFailure,"pickup cleanup remains sticky");}
            foreach(var method in new[]{typeof(RelicCmd).GetMethod("Obtain")!,typeof(RelicModel).GetMethod("AfterObtained")!,typeof(SequentialPickupRelic).GetMethod("AfterObtained")!,typeof(OldCoin).GetMethod("AfterObtained")!})
                Check(!(HarmonyLib.Harmony.GetPatchInfo(method)?.Owners.Any()??false),"pickup tree always removes exact owned hooks");
            // A failed production owner stops its host. Each fixture gets the
            // equivalent fresh process; no production reset is exposed.
            typeof(PinnedRelicPickupChain).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);
        }
    }
}
