using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.ItemV1;

internal static partial class Program
{
    internal static void FillEventBelt(Player player,int size=3,int free=0)
    {
        player.PotionSlots.Clear();player.MaxPotionCount=size;
        for(int i=0;i<size;i++){var p=new PotionModel{Owner=player};p.Id.Entry="OLD_"+i;player.PotionSlots.Add(i<size-free?p:null);}
    }
    internal static void ApplyBeltPickup(Player player,Reward reward,int count=2)
    {
        if(reward is not RelicReward r||r.Relic is not PotionBelt)return;
        r.Relic.Owner=player;player.Relics.Add(r.Relic);
        player.MaxPotionCount+=count;for(int i=0;i<count;i++)player.PotionSlots.Add(null);
    }
    internal static void ConfigureEventCapacity(ItemFixture f,int[] indices,int size=3,int free=0)
    {
        FillEventBelt(f.Player,size,free);
        f.BeforeScreen=()=>{foreach(int index in indices)((RelicReward)f.Set.Rewards[index]).Relic=new PotionBelt();};
        f.AfterCollection=()=>ApplyBeltPickup(f.Player,f.CompletedRewards.Last());
    }
    private static IItemV1ApplyValue EventCollect(ItemFixture f,GenericEventV7Observation c,ItemV1Observation o)=>
        ((GenericEventV7ItemApply)f.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,o.LegalActions[0])).Value;
    private static void EventCapacityCases()
    {
        foreach(var kinds in new[]{new[]{"relic"},new[]{"relic","potion","potion"},new[]{"relic","relic","potion","potion","potion","potion"},new[]{"potion","relic","potion"}}) {
            using var f=new ItemFixture("EVENT_CAPACITY",kinds[0],itemKinds:kinds);
            ConfigureEventCapacity(f,kinds.Select((k,i)=>(k,i)).Where(x=>x.k=="relic").Select(x=>x.i).ToArray(),free:kinds[0]=="potion"?1:0);
            var initial=f.Player.PotionSlots.ToArray();var c=f.Start();Check(c.Status=="child","ordered capacity plan admitted");
            for(int i=0;i<kinds.Length;i++) {
                var read=f.Child(c);var current=read is GenericEventV7ItemSetRead set?set.Current:read;
                Check(current is ItemV1Observation {Status:"ready"},"capacity entry ready");
                var o=(ItemV1Observation)current!;Check(o.PotionSlots.Count==f.Player.MaxPotionCount,"existing wire shows current capacity");
                Check(EventCollect(f,c,o) is ItemV1DispatchReceipt,"capacity entry accepted");
                var after=f.Child(c);Check(after is ItemV1ResolvedResult||after is GenericEventV7ItemSetRead {Status:"ready" or "resolved"},"capacity entry reconciled");
            }
            Check(f.Player.MaxPotionCount==3+2*kinds.Count(k=>k=="relic"),"exact gained capacity");
            Check(initial.Where(p=>p is not null).All(p=>f.Player.PotionSlots.Contains(p)),"initial potion models survive");
            var parent=f.Session.Read();Check(parent.Phase=="proceed"&&parent.CompletedItemChildren==1,"capacity event returns to Proceed");
            f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete"&&f.CompletionValid,"capacity event to map");
        }
        using(var f=new ItemFixture("CAPACITY_AFTER_POTION","potion",itemKinds:new[]{"potion","relic"})) {
            PreparePolicy(f,false);ConfigureEventCapacity(f,new[]{1});
            var c=f.Start();Check(c.Child?.Kind=="item_policy","policy reorders capacity before blocked potion");
            PolicyAct(f,c,"collect:1");PolicyRead(f,c);PolicyAct(f,c,"collect:0");Check(PolicyRead(f,c).Status=="resolved","capacity-first policy resolves native offer");
            var parent=f.Session.Read();f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","reordered capacity to map");
        }
        foreach(var mode in new[]{"overflow","too_many","one","three","filled","survivor","spoof","late_value","late_shrink","late_grow","delayed","lost"}) {
            var kinds=mode=="before"?new[]{"potion","relic"}:mode=="too_many"?new[]{"relic","relic","relic"}:new[]{"relic","potion"};
            using var f=new ItemFixture("EVENT_BAD_CAPACITY",kinds[0],itemKinds:kinds,delayedOffer:mode.StartsWith("late_"),delayedCollection:mode=="delayed");
            ConfigureEventCapacity(f,kinds.Select((k,i)=>(k,i)).Where(x=>x.k=="relic").Select(x=>x.i).ToArray(),size:mode=="overflow"?7:3);
            if(mode=="spoof")f.BeforeScreen=()=>{((RelicReward)f.Set.Rewards[0]).Relic=new RelicModel();((RelicReward)f.Set.Rewards[0]).Relic.Id.Entry="POTION_BELT";};
            f.AfterCollection=()=>{
                var reward=f.CompletedRewards.Last();ApplyBeltPickup(f.Player,reward,mode=="one"?1:mode=="three"?3:2);
                if(reward is RelicReward r) {
                    if(mode=="filled")f.Player.PotionSlots[^1]=new();
                    if(mode=="survivor")f.Player.PotionSlots[0]=new();
                    if(mode=="late_value")r.Relic.DynamicVars["PotionSlots"].IntValue=3;
                    if(mode=="lost")throw new InvalidOperationException("lost collection");
                }
            };
            var c=f.Start();
            if(mode is "before" or "overflow" or "too_many" or "spoof") {Check(c.Status=="unsupported"&&f.CollectCalls==0,"impossible ordered capacity plan stops: "+mode);continue;}
            var o=(ItemV1Observation)((GenericEventV7ItemSetRead)f.Child(c)).Current!;
            EventCollect(f,c,o);var after=f.Child(c);
            if(mode=="delayed") {Check(after is GenericEventV7ItemSetRead {Status:"waiting"},"capacity native task waits");f.AdvanceCollection();after=f.Child(c);}
            if(mode is "delayed" or "late_shrink" or "late_grow") {
                Check(after is GenericEventV7ItemSetRead {Status:"ready"},"valid capacity pickup ready");
                if(mode=="delayed")continue;
                o=(ItemV1Observation)((GenericEventV7ItemSetRead)after).Current!;EventCollect(f,c,o);
                Check(f.Child(c) is GenericEventV7ItemSetRead {Status:"waiting"},"offer completion remains owned");
                if(mode=="late_shrink"){f.Player.PotionSlots.RemoveAt(f.Player.PotionSlots.Count-1);f.Player.MaxPotionCount--;}
                else {f.Player.PotionSlots.Add(null);f.Player.MaxPotionCount++;}
                after=f.Child(c);
            }
            Check(after is GenericEventV7ItemSetRead {Status:"unsupported"},"bad capacity effect stops: "+mode);
            Check(EventCollect(f,c,o) is ItemV1ApplyFailure,"capacity failure cannot retry");
        }
        foreach(var mode in new[]{"already_owned","foreign_owner","late_owner","late_remove","late_duplicate"}) {
            using var f=new ItemFixture("EVENT_CAPACITY_OWNER","relic",itemKinds:new[]{"relic","potion"});
            ConfigureEventCapacity(f,new[]{0});var configure=f.BeforeScreen;
            f.BeforeScreen=()=>{configure!();var belt=((RelicReward)f.Set.Rewards[0]).Relic;
                if(mode=="already_owned"){belt.Owner=f.Player;f.Player.Relics.Add(belt);}
                if(mode=="foreign_owner")belt.Owner=new Player();};
            var c=f.Start();
            if(mode is "already_owned" or "foreign_owner"){Check(c.Status=="unsupported"&&f.CollectCalls==0,"owned capacity offer rejected");continue;}
            var o=(ItemV1Observation)((GenericEventV7ItemSetRead)f.Child(c)).Current!;EventCollect(f,c,o);
            Check(f.Child(c) is GenericEventV7ItemSetRead {Status:"ready"},"capacity owner settled before next pickup");
            var model=((RelicReward)f.Set.Rewards[0]).Relic;
            if(mode=="late_owner")model.Owner=new Player();
            if(mode=="late_remove")f.Player.Relics.Remove(model);
            if(mode=="late_duplicate")f.Player.Relics.Add(model);
            Check(f.Child(c) is GenericEventV7ItemSetRead {Status:"unsupported"}&&f.CollectCalls==1,"settled capacity relic must remain owned exactly once");
        }
        foreach(bool skip in new[]{false,true}) {
            using var f=new CardRewardSetFixture(kinds:new[]{"relic","card","potion","potion"});
            FillEventBelt(f.World.Player);
            f.BeforeScreen=()=>((RelicReward)f.AllRewards[0]).Relic=new PotionBelt();
            f.AfterItemCollection=reward=>ApplyBeltPickup(f.World.Player,reward);
            var c=f.Start();Check(c.Status=="child","mixed capacity admitted");
            f.Act(c,"collect:0");Check(f.Read(c).Settled!.Count==1,"mixed capacity settled");
            f.Act(c,"open:1");f.Act(c,skip?"skip:1":"choose:1:0");
            Check(f.Read(c).Settled!.Count==2,"card after capacity settled");
            f.Act(c,"collect:2");f.Read(c);f.Act(c,"collect:3");f.Read(c);var after=f.Read(c);
            if(skip){Check(after.Phase=="dismiss","mixed skipped card dismissal");f.Act(c,"dismiss");after=f.Read(c);}
            Check(after.Status=="resolved"&&f.World.Player.MaxPotionCount==5,"mixed card/item capacity completes: "+skip+" "+after.Status+" "+after.Phase+" capacity="+f.World.Player.MaxPotionCount);
            var parent=f.Session.Read();f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","mixed capacity map return");
        }
    }
}
