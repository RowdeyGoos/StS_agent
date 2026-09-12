using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Core.Public;

internal static partial class Program
{
    private static void FillBelt(CombatItemsFixture f)
    {
        CombatManager.Instance!.IsInProgress=false;
        for(int i=0;i<8;i++){var potion=new PotionModel{Owner=f.World.Player};potion.Id.Entry="OLD_"+i;f.World.Player.PotionSlots[i]=potion;}
    }
    private static void PotionDiscardCases()
    {
        foreach(int slot in new[]{0,7}) {
            using var f=new CombatItemsFixture(4);FillBelt(f);
            var first=f.Reader.Read();
            Check(first.PotionSlots!.Count==8&&first.LegalActions.Contains("discard:"+slot),"full original belt exposes exact slot");
            var original=f.World.Player.PotionSlots.ToArray();
            PublicRewardActionRequest.TryCreate(first.DecisionId,"discard:"+slot,out var request);
            Check(f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.Accepted,"native discard accepted");
            Check(f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied,"discard cannot retry");
            var after=f.Reader.Read();Check(after.Status==PublicDecisionStatus.Ready&&after.DecisionRevision==1&&after.PotionSlots![slot] is null,"exact removal reconciled");
            Check(original[slot]!.HasBeenRemovedFromState&&original.Where((p,i)=>i!=slot).All(p=>f.World.Player.PotionSlots.Contains(p)),"other potion objects retained");
            PublicRewardActionRequest.TryCreate(after.DecisionId,"collect:0",out var collect);
            Check(f.Applier.Apply(collect).Outcome==PublicRewardActionApplyOutcome.Accepted,"collect only after discard");
            var collected=f.Reader.Read();Check(collected.Status==PublicDecisionStatus.Ready&&!collected.LegalActions.Contains("discard:"+slot)&&collected.LegalActions.Contains("discard:"+(slot==0?1:0)),"newly collected potion protected");
        }
        foreach(var mode in new[]{"owner","queued","removed","locked","combat","network","free","same_key"}) {
            using var f=new CombatItemsFixture(2);FillBelt(f);var first=f.Reader.Read();
            switch(mode){
                case "owner":f.World.Player.PotionSlots[0]!.Owner=new();break;
                case "queued":f.World.Player.PotionSlots[0]!.IsQueued=true;break;
                case "removed":f.World.Player.PotionSlots[0]!.HasBeenRemovedFromState=true;break;
                case "locked":f.World.Player.CanRemovePotions=false;break;
                case "combat":CombatManager.Instance!.IsInProgress=true;break;
                case "network":RunManager.Instance!.ActionQueueSynchronizer.SetNetwork(2);break;
                case "free":f.World.Player.PotionSlots[7]=null;break;
                case "same_key":var p=new PotionModel{Owner=f.World.Player};p.Id.Entry="OLD_0";f.World.Player.PotionSlots[0]=p;break;
            }
            PublicRewardActionRequest.TryCreate(first.DecisionId,"discard:0",out var action);
            Check(f.Applier.Apply(action).Outcome!=PublicRewardActionApplyOutcome.Accepted&&RunManager.Instance!.ActionQueueSynchronizer.Actions.Count==0,"stale discard withheld: "+mode);
        }
        foreach(var mode in new[]{"swap","offer_drop","offer_hide","offer_disabled","offer_model","queue","network","combat","locked","owner","key","deck","screen","fail","dispose","deadline"}) {
            using var f=new CombatItemsFixture(2);FillBelt(f);
            var queue=RunManager.Instance!.ActionQueueSynchronizer;queue.Handler=_=>{};
            var ready=f.Reader.Read();PublicRewardActionRequest.TryCreate(ready.DecisionId,"discard:0",out var request);
            Check(f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.Accepted,"queued discard reserved: "+mode);
            var native=queue.Actions.Single();Check(f.Reader.Read().Status==PublicDecisionStatus.Waiting,"queued discard waiting");
            var offer=f.Buttons.Single(b=>b.Reward is PotionReward);
            switch(mode){
                case "swap":var p=new PotionModel{Owner=f.World.Player};p.Id.Entry="OLD_0";f.World.Player.PotionSlots[0]=p;break;
                case "offer_drop":f.Screen.Children.Remove(offer);break;
                case "offer_hide":offer.Visible=false;break;
                case "offer_disabled":offer.IsEnabled=false;break;
                case "offer_model":((PotionReward)offer.Reward).Potion=new();break;
                case "queue":RunManager.Instance!.ActionQueueSynchronizer=new();break;
                case "network":queue.SetNetwork(3);break;
                case "combat":CombatManager.Instance!.IsInProgress=true;break;
                case "locked":f.World.Player.CanRemovePotions=false;break;
                case "owner":f.World.Player.PotionSlots[0]!.Owner=new();break;
                case "key":f.World.Player.PotionSlots[0]!.Id.Entry="CHANGED";break;
                case "deck":f.World.Player.Deck.Cards[0].CurrentUpgradeLevel++;break;
                case "screen":f.World.Overlays.Screens.Clear();break;
                case "fail":f.Reader.InteractionSession.FailClosed();break;
                case "dispose":bool threw=false;try{f.Reader.Dispose();}catch{threw=true;}Check(threw,"uncertain cleanup fails");break;
                case "deadline":typeof(Sts2AgentBridge.Adapters.Public.PinnedPublicPotionDiscard).GetField("_deadline",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance)!.SetValue(f.Reader.InteractionSession.Pending!.Discard,0d);break;
            }
            bool rejected=false;try{native.Execute();}catch{rejected=true;}
            Check(rejected&&native.DiscardCalls==0,"guard rejects before native slot lookup: "+mode);
            Check(f.Reader.Read().Status==PublicDecisionStatus.Unsupported,"guard failure stops session");
        }
        foreach(var mode in new[]{"delayed","fault","cancel","no_effect","wrong_slot","survivor","lost_before","lost_after","restore"}) {
            using var f=new CombatItemsFixture(2);FillBelt(f);var queue=RunManager.Instance!.ActionQueueSynchronizer;
            var old=f.World.Player.PotionSlots[0];
            queue.Handler=a=>{
                if(mode=="lost_before")throw new Exception("lost");
                a.Start();
                if(mode!="no_effect")a.Remove();
                if(mode=="wrong_slot")f.World.Player.PotionSlots[1]=null;
                if(mode=="survivor")f.World.Player.PotionSlots[1]=new();
                if(mode=="fault")a.Exception=new Exception("hook failure");
                if(mode=="cancel"){a.Completion.SetCanceled();return;}
                if(mode=="lost_after")throw new Exception("lost");
                if(mode is not ("delayed" or "restore"))a.Finish();
            };
            var ready=f.Reader.Read();PublicRewardActionRequest.TryCreate(ready.DecisionId,"discard:0",out var request);
            bool accepted=false;try{accepted=f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.Accepted;}catch{}
            Check(accepted==!mode.StartsWith("lost"),"native dispatch result: "+mode);
            Check(f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied&&queue.Actions.Count==1,"uncertain discard not repeated");
            var next=f.Reader.Read();
            if(mode is "delayed" or "restore"){
                Check(next.Status==PublicDecisionStatus.Waiting,"removed but native hook pending");
                if(mode=="restore")f.World.Player.PotionSlots[0]=old;
                queue.Actions[0].Finish();next=f.Reader.Read();
            }
            Check(next.Status==(mode=="delayed"?PublicDecisionStatus.Ready:PublicDecisionStatus.Unsupported),"exact discard task/effect: "+mode);
        }
    }
}
