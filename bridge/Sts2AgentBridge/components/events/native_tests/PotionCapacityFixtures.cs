using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Core.Public;

internal static partial class Program
{
    private static void CapacityBelt(CombatItemsFixture f,int size,bool free=false)
    {
        FillBelt(f);f.World.Player.PotionSlots.RemoveRange(size,8-size);f.World.Player.MaxPotionCount=size;
        if(free)f.World.Player.PotionSlots[size-1]=null;
        foreach(var relic in f.Rewards.OfType<RelicReward>())relic.Relic=new PotionBelt();
    }
    private static void GrowBelt(CombatItemsFixture f,int count=2)
    {
        f.World.Player.MaxPotionCount+=count;for(int i=0;i<count;i++)f.World.Player.PotionSlots.Add(null);
    }
    private static void PotionCapacityCases()
    {
        foreach(int size in new[]{0,1,3,6})foreach(bool prior in new[]{false,true}) {
            if(prior&&size==0)continue;
            using var f=new CombatItemsFixture(2);CapacityBelt(f,size,prior);
            var ready=f.Reader.Read();Check(ready.CapacityRewards&&ready.Rewards.Single(r=>r.Kind==PublicRewardKind.Relic).PotionCapacityGain==2,"capacity effect advertised");
            var original=f.World.Player.PotionSlots.ToArray();
            if(prior){PublicRewardActionRequest.TryCreate(ready.DecisionId,"collect:0",out var p);Check(f.Applier.Apply(p).Outcome==PublicRewardActionApplyOutcome.Accepted,"potion before capacity grant");ready=f.Reader.Read();}
            var button=f.Buttons.Single(b=>b.Reward is RelicReward);var handler=button.Handler;
            button.Handler=()=>{handler!();GrowBelt(f);return Task.CompletedTask;};
            PublicRewardActionRequest.TryCreate(ready.DecisionId,"collect:1",out var action);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"capacity relic one click");
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied,"capacity pickup no retry");
            var after=f.Reader.Read();Check(after.Status==PublicDecisionStatus.Ready&&after.PotionSlots!.Count==size+2&&after.CapacityRewards,"exact two empty slots reconciled");
            Check(after.PotionSlots!.Skip(size).All(p=>p is null)&&original.Where(p=>p is not null).All(p=>f.World.Player.PotionSlots.Contains(p)),"survivor potion objects preserved");
            Check(!f.Reader.InteractionSession.CanDiscard(f.World.Player,size),"new capacity slot not original inventory");
            if(prior)Check(!f.Reader.InteractionSession.CanDiscard(f.World.Player,size-1),"earlier collected potion remains protected");
            else {PublicRewardActionRequest.TryCreate(after.DecisionId,"collect:0",out var p);Check(f.Applier.Apply(p).Outcome==PublicRewardActionApplyOutcome.Accepted,"waiting potion fits after gain");after=f.Reader.Read();}
            PublicRewardActionRequest.TryCreate(after.DecisionId,"proceed",out var exit);Check(f.Applier.Apply(exit).Outcome==PublicRewardActionApplyOutcome.Accepted&&f.Reader.Read().Status==PublicDecisionStatus.Complete,"capacity pickup to map");
        }
        foreach(var mode in new[]{"one","three","filled","swap","shrink","deck","other_relic","late_var","lost","delay","retention","retention_grow","overflow","spoof"}) {
            using var f=new CombatItemsFixture(2);CapacityBelt(f,mode=="overflow"?7:3);
            var reward=f.Rewards.OfType<RelicReward>().Single();
            if(mode=="spoof"){reward.Relic=new RelicModel();reward.Relic.Id.Entry="POTION_BELT";}
            var ready=f.Reader.Read();
            if(mode=="overflow") {Check(ready.Status==PublicDecisionStatus.Ready&&!ready.LegalActions.Contains("collect:1"),"capacity bound withholds input");continue;}
            var button=f.Buttons.Single(b=>b.Reward is RelicReward);var handler=button.Handler;
            button.Handler=()=>{
                handler!();GrowBelt(f,mode=="one"?1:mode=="three"?3:2);
                if(mode=="filled")f.World.Player.PotionSlots[^1]=new();
                if(mode=="swap")f.World.Player.PotionSlots[0]=new();
                if(mode=="shrink"){f.World.Player.PotionSlots.RemoveAt(0);f.World.Player.MaxPotionCount--;}
                if(mode=="deck")f.World.Player.Deck.Cards[0].CurrentUpgradeLevel++;
                if(mode=="other_relic")f.World.Player.Relics.Add(new(){Owner=f.World.Player});
                if(mode=="late_var")reward.Relic.DynamicVars["PotionSlots"].IntValue=3;
                if(mode=="lost")throw new Exception("lost dispatch");
                if(mode=="delay")reward.SuccessfullySelected=false;
                return Task.CompletedTask;
            };
            PublicRewardActionRequest.TryCreate(ready.DecisionId,"collect:1",out var action);
            bool accepted=false;try{accepted=f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted;}catch{}
            Check(accepted==(mode!="lost"),"capacity dispatch once: "+mode);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied&&button.ForceClickCalls==1,"no repeated capacity collection");
            bool failed=false;PublicRewardDecisionSnapshot after=default;try{after=f.Reader.Read();failed=after.Status==PublicDecisionStatus.Unsupported;}catch{failed=true;}
            if(mode=="delay"){Check(after.Status==PublicDecisionStatus.Waiting,"growth before reward completion waits");reward.SuccessfullySelected=true;after=f.Reader.Read();}
            if(mode is "delay" or "retention" or "retention_grow" or "lost") {
                // A caller losing the dispatch receipt does not authorize a retry;
                // if read again the exact completed native effect is observable.
                Check(after.Status==PublicDecisionStatus.Ready,"capacity effect available: "+mode);
                if(mode=="retention"){f.World.Player.PotionSlots.RemoveAt(4);f.World.Player.MaxPotionCount--;}
                if(mode=="retention_grow")GrowBelt(f,1);
                if(mode.StartsWith("retention"))Check(f.Reader.Read().Status==PublicDecisionStatus.Unsupported,"settled belt capacity retained without prior potion");
            }else Check(failed,"unexpected capacity effect rejected: "+mode);
        }
    }
}
