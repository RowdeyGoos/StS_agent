using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Core.Public;

internal static partial class Program
{
    private static void HealingRewardCases()
    {
        foreach(var (hp,max) in new[]{(33,80),(33,85),(78,80),(80,80),(1,9)}) {
            using var f=new CombatItemsFixture(1);
            var player=f.World.Player;player.Creature.CurrentHp=hp;player.Creature.MaxHp=max;
            var reward=(RelicReward)f.Rewards[0];reward.Relic=new FakeLeesWaffle();
            var ready=f.Reader.Read();
            Check(ready.HealingRewards&&ready.CapacityRewards&&ready.Rewards[0].HealAmount==max/10,"exact healing declaration");
            var button=f.Buttons[0];var handler=button.Handler;
            button.Handler=()=>{
                handler!();player.Creature.CurrentHp=Math.Min(hp+max/10,max);
                // The native last pickup frees its button and fades the panel,
                // while the exact terminal overlay remains until Proceed.
                f.Screen.Children.Remove(button);button.InstanceValid=false;
                return Task.CompletedTask;
            };
            PublicRewardActionRequest.TryCreate(ready.DecisionId,"collect:0",out var action);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"healing pickup accepted");
            var after=f.Reader.Read();
            Check(after.Status==PublicDecisionStatus.Ready&&after.Player.Hp==Math.Min(hp+max/10,max)&&after.Rewards.Count==0&&after.HealingRewards,"freed final button reconciles exact heal");
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied&&button.ForceClickCalls==1,"healing pickup replay blocked");
            PublicRewardActionRequest.TryCreate(after.DecisionId,"proceed",out var exit);
            Check(f.Applier.Apply(exit).Outcome==PublicRewardActionApplyOutcome.Accepted&&f.Reader.Read().Status==PublicDecisionStatus.Complete,"healing terminal Proceed to map");
        }
        foreach(var mode in new[]{"missing","extra","max_hp","gold","deck","potion","relic","claimed","model","key","variable","foreign_overlay","early_free","delayed","ordinary_heal"}) {
            using var f=new CombatItemsFixture(1);
            var player=f.World.Player;player.Creature.CurrentHp=33;player.Creature.MaxHp=80;
            var reward=(RelicReward)f.Rewards[0];reward.Relic=new FakeLeesWaffle();
            if(mode=="ordinary_heal"){reward.Relic=new RelicModel();reward.Relic.Id.Entry="PASSIVE";}
            var ready=f.Reader.Read();var button=f.Buttons[0];var handler=button.Handler;
            button.Handler=()=>{
                handler!();player.Creature.CurrentHp=mode=="missing"?33:mode=="extra"?42:41;
                if(mode=="max_hp")player.Creature.MaxHp++;
                if(mode=="gold")player.Gold++;
                if(mode=="deck")player.Deck.Cards[0].CurrentUpgradeLevel++;
                if(mode=="potion")player.PotionSlots[0]=new();
                if(mode=="relic")player.Relics.Add(new(){Owner=player});
                if(mode=="claimed")reward.ClaimedRelic=new();
                if(mode=="model")reward.Relic=new FakeLeesWaffle();
                if(mode=="key")reward.Relic.Id.Entry="CHANGED";
                if(mode=="variable")reward.Relic.DynamicVars["Heal"].BaseValue=11m;
                if(mode=="foreign_overlay")f.World.Overlays.Screens.Add(new MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen());
                if(mode is "early_free" or "delayed")reward.SuccessfullySelected=false;
                if(mode=="early_free"){f.Screen.Children.Remove(button);button.InstanceValid=false;}
                return Task.CompletedTask;
            };
            PublicRewardActionRequest.TryCreate(ready.DecisionId,"collect:0",out var action);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"bad effect dispatched once");
            PublicRewardDecisionSnapshot after=default;bool failed=false;
            try{after=f.Reader.Read();failed=after.Status==PublicDecisionStatus.Unsupported;}catch{failed=true;}
            if(mode=="delayed") {
                Check(after.Status==PublicDecisionStatus.Waiting,"heal before native reward completion remains pending");
                reward.SuccessfullySelected=true;after=f.Reader.Read();
                Check(after.Status==PublicDecisionStatus.Ready&&after.Player.Hp==41,"native completion resolves pending heal");
            }else Check(failed,"unexpected healing mutation rejected: "+mode);
            try{f.Applier.Apply(action);}catch{}
            Check(button.ForceClickCalls==1,"failed healing action never retried");
        }
        foreach(var mode in new[]{"spoof","wrong_var","wrong_key"}) {
            using var f=new CombatItemsFixture(1);var reward=(RelicReward)f.Rewards[0];reward.Relic=new FakeLeesWaffle();
            if(mode=="spoof"){reward.Relic=new RelicModel();reward.Relic.Id.Entry="FAKE_LEES_WAFFLE";}
            if(mode=="wrong_var")reward.Relic.DynamicVars["Heal"].BaseValue=20m;
            if(mode=="wrong_key")reward.Relic.Id.Entry="PASSIVE";
            bool failed=false;try{failed=f.Reader.Read().Status==PublicDecisionStatus.Unsupported;}catch{failed=true;}
            Check(failed&&f.Buttons[0].ForceClickCalls==0,"healing identity preflight rejects: "+mode);
        }
    }
}
