using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Core.Public;

internal static partial class Program
{
    private sealed class UnknownGoldHook : AbstractModel
    {
        public override decimal ModifyGoldGained(MegaCrit.Sts2.Core.Entities.Players.Player player,decimal amount)=>0m;
    }
    private sealed class UnknownGoldAfterHook : AbstractModel
    {
        public override Task AfterGoldGained(MegaCrit.Sts2.Core.Entities.Players.Player player)=>Task.CompletedTask;
    }
    private static void ModifiedGoldRewardCases()
    {
        foreach(int amount in new[]{0,1,3,4,14,15,43})foreach(bool compact in new[]{false,true})foreach(bool melted in new[]{false,true}) {
            using var f=new CombatItemsFixture(1);var player=f.World.Player;var run=(MegaCrit.Sts2.Core.Runs.RunState)player.RunState;
            run.Players.Add(player);var hat=new BowlerHat{Owner=player,IsMelted=melted};player.Relics.Add(hat);
            var reward=new GoldReward{Player=player,Amount=amount,RewardsSetIndex=1};var button=f.Buttons[0];button.Reward=reward;
            int gain=melted?amount:amount*5/4;
            button.Handler=()=>{player.Gold+=gain;reward.SuccessfullySelected=true;if(compact){f.Screen.Children.Remove(button);button.InstanceValid=false;}return Task.CompletedTask;};
            var first=f.Reader.Read();
            Check(first.Status==PublicDecisionStatus.Ready&&first.ModifiedGoldRewards==!melted&&
                first.Rewards[0].GoldAmount==amount&&(first.Rewards[0].GoldGain??amount)==gain,"native gold modifier projection and truncation");
            PublicRewardActionRequest.TryCreate(first.DecisionId,"claim:0",out var action);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"modified gold dispatch once");
            var after=f.Reader.Read();
            Check(after.Status==PublicDecisionStatus.Ready&&after.Player.Gold==99+gain&&after.ModifiedGoldRewards==!melted,"modified gold reconciles with native completion and compaction");
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied&&button.ForceClickCalls==1,"gold never repeats");
        }
        foreach(var mode in new[]{"wrong_gain","hp","deck","potion","relic","hat_var","hat_melt","amount","unselected_freed","delayed","foreign_screen","hook_added","same_key_replaced","manager","node","active_run"}) {
            using var f=new CombatItemsFixture(1);var player=f.World.Player;var run=(MegaCrit.Sts2.Core.Runs.RunState)player.RunState;
            run.Players.Add(player);var hat=new BowlerHat{Owner=player};player.Relics.Add(hat);
            var reward=new GoldReward{Player=player,Amount=15,RewardsSetIndex=1};var button=f.Buttons[0];button.Reward=reward;
            button.Handler=()=>{player.Gold+=mode=="wrong_gain"?15:18;reward.SuccessfullySelected=mode is not ("delayed" or "unselected_freed");
                if(mode=="hp")player.Creature.CurrentHp--;
                if(mode=="deck")player.Deck.Cards[0].CurrentUpgradeLevel++;
                if(mode=="potion")player.PotionSlots[0]=new(){Owner=player};
                if(mode=="relic")player.Relics.Add(new(){Owner=player});
                if(mode=="hat_var")hat.DynamicVars["GoldIncrease"].BaseValue=2m;
                if(mode=="hat_melt")hat.IsMelted=true;
                if(mode=="amount")reward.Amount++;
                if(mode=="unselected_freed"){f.Screen.Children.Remove(button);button.InstanceValid=false;}
                if(mode=="foreign_screen"){f.World.Overlays.Screens.Clear();f.World.Overlays.Screens.Add(new MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen());}
                if(mode=="hook_added")run.ExtraListeners.Add(new UnknownGoldHook());
                if(mode=="same_key_replaced")player.Relics[0]=new BowlerHat{Owner=player};
                if(mode=="manager")MegaCrit.Sts2.Core.Runs.RunManager.Instance=new(){State=run};
                if(mode=="node")MegaCrit.Sts2.Core.Nodes.NRun.Instance=new();
                if(mode=="active_run")MegaCrit.Sts2.Core.Runs.RunManager.Instance!.State=new();
                return Task.CompletedTask;};
            var first=f.Reader.Read();PublicRewardActionRequest.TryCreate(first.DecisionId,"claim:0",out var action);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"gold adversarial dispatch");
            bool failed=false;PublicRewardDecisionSnapshot after=default;try{after=f.Reader.Read();failed=after.Status==PublicDecisionStatus.Unsupported;}catch{failed=true;}
            if(mode=="delayed") {Check(after.Status==PublicDecisionStatus.Waiting,"gold gain alone is not completion");reward.SuccessfullySelected=true;Check(f.Reader.Read().Status==PublicDecisionStatus.Ready,"gold native completion resolves");}
            else Check(failed,"gold rejects unexpected effect or identity: "+mode);
            try{f.Applier.Apply(action);}catch{}Check(button.ForceClickCalls==1,"gold failed action not retried");
        }
        foreach(var mode in new[]{"spoof","owner","variable","duplicate","unknown_modifier","unknown_after","overflow","late_replace","late_var","late_melt","late_manager","late_node","late_run"}) {
            using var f=new CombatItemsFixture(1);var player=f.World.Player;var run=(MegaCrit.Sts2.Core.Runs.RunState)player.RunState;
            run.Players.Add(player);var hat=new BowlerHat{Owner=player};player.Relics.Add(hat);
            var reward=new GoldReward{Player=player,Amount=15,RewardsSetIndex=1};var button=f.Buttons[0];button.Reward=reward;
            var first=f.Reader.Read();
            if(mode=="spoof"){player.Relics[0]=new(){Owner=player};player.Relics[0].Id.Entry="BOWLER_HAT";}
            if(mode=="owner")hat.Owner=new();
            if(mode is "variable" or "late_var")hat.DynamicVars["GoldIncrease"].BaseValue=2m;
            if(mode=="duplicate")player.Relics.Add(new BowlerHat{Owner=player});
            if(mode=="unknown_modifier")run.ExtraListeners.Add(new UnknownGoldHook());
            if(mode=="unknown_after")run.ExtraListeners.Add(new UnknownGoldAfterHook());
            if(mode=="overflow")player.Gold=int.MaxValue-10;
            if(mode=="late_replace")player.Relics[0]=new BowlerHat{Owner=player};
            if(mode=="late_melt")hat.IsMelted=true;
            if(mode=="late_manager")MegaCrit.Sts2.Core.Runs.RunManager.Instance=new(){State=run};
            if(mode=="late_node")MegaCrit.Sts2.Core.Nodes.NRun.Instance=new();
            if(mode=="late_run")MegaCrit.Sts2.Core.Runs.RunManager.Instance!.State=new();
            bool failed=false;try {
                if(mode.StartsWith("late",StringComparison.Ordinal)){PublicRewardActionRequest.TryCreate(first.DecisionId,"claim:0",out var action);failed=f.Applier.Apply(action).Outcome!=PublicRewardActionApplyOutcome.Accepted;}
                else failed=f.Reader.Read().Status==PublicDecisionStatus.Unsupported;
            }catch{failed=true;}
            Check(failed&&button.ForceClickCalls==0,"gold rejects unsupported pre-input state: "+mode);
        }
    }

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

    private static void FakeMangoRewardCases()
    {
        foreach(var mode in new[]{"ok","compact","delayed","missing_hp","extra_hp","missing_max","extra_max","gold","deck","potion","model","owner","variable","spoof","wrong_key","cap","late_variable","late_cap"}) {
            using var f=new CombatItemsFixture(1);var player=f.World.Player;
            player.Creature.CurrentHp=18;player.Creature.MaxHp=80;
            var reward=(RelicReward)f.Rewards[0];reward.Relic=new FakeMango();
            var first=f.Reader.Read();
            Check(first.FakeMangoRewards&&first.ExpandedRewards&&first.Rewards[0].MaxHpGain==3&&first.Rewards[0].HealAmount==3,"Fake Mango projects exact native effect");
            Check(PublicRewardDecisionIdentity.Compute(first)!=PublicRewardDecisionIdentity.Compute(first with {FakeMangoRewards=false}),"Fake Mango schema binds identity");
            var button=f.Buttons[0];var handler=button.Handler;
            if(mode=="spoof"){reward.Relic=new RelicModel();reward.Relic.Id.Entry="FAKE_MANGO";}
            if(mode=="wrong_key")reward.Relic.Id.Entry="STRAWBERRY";
            if(mode is "variable" or "late_variable")reward.Relic.DynamicVars["MaxHp"].BaseValue=7m;
            if(mode is "cap" or "late_cap")player.Creature.MaxHp=999999998;
            if(mode is "spoof" or "wrong_key" or "variable" or "cap" or "late_variable" or "late_cap") {
                bool failed=false;try {
                    if(mode.StartsWith("late_",StringComparison.Ordinal)) {
                        PublicRewardActionRequest.TryCreate(first.DecisionId,"collect:0",out var request);
                        failed=f.Applier.Apply(request).Outcome!=PublicRewardActionApplyOutcome.Accepted;
                    }else failed=f.Reader.Read().Status==PublicDecisionStatus.Unsupported;
                }catch{failed=true;}
                Check(failed&&button.ForceClickCalls==0,"Fake Mango identity rejects before input: "+mode);continue;
            }
            button.Handler=()=>{handler!();player.Creature.CurrentHp=mode=="missing_hp"?18:mode=="extra_hp"?22:21;
                player.Creature.MaxHp=mode=="missing_max"?80:mode=="extra_max"?84:83;
                if(mode=="gold")player.Gold++;
                if(mode=="deck")player.Deck.Cards[0].CurrentUpgradeLevel++;
                if(mode=="potion")player.PotionSlots[0]=new();
                if(mode=="model")reward.Relic=new FakeMango();
                if(mode=="owner")reward.Relic.Owner=new();
                if(mode=="delayed")reward.SuccessfullySelected=false;
                if(mode=="compact"){f.Screen.Children.Remove(button);button.InstanceValid=false;}
                return Task.CompletedTask;};
            PublicRewardActionRequest.TryCreate(first.DecisionId,"collect:0",out var action);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"Fake Mango dispatches once");
            var after=f.Reader.Read();
            if(mode=="delayed"){Check(after.Status==PublicDecisionStatus.Waiting,"Fake Mango awaits native reward completion");reward.SuccessfullySelected=true;after=f.Reader.Read();}
            if(mode is "ok" or "compact" or "delayed") {
                Check(after.Status==PublicDecisionStatus.Ready&&after.FakeMangoRewards&&after.Player.Hp==21&&after.Player.MaxHp==83,"Fake Mango reconciles and retains schema");
                PublicRewardActionRequest.TryCreate(after.DecisionId,"proceed",out var exit);
                Check(f.Applier.Apply(exit).Outcome==PublicRewardActionApplyOutcome.Accepted&&f.Reader.Read().Status==PublicDecisionStatus.Complete,"Fake Mango exits normally");
            }else Check(after.Status==PublicDecisionStatus.Unsupported,"Fake Mango rejects wrong effect: "+mode);
            try{f.Applier.Apply(action);}catch{}
            Check(button.ForceClickCalls==1,"Fake Mango never retries");
        }
    }

    private static void MaxHpRewardCases()
    {
        foreach(var (hp,max) in new[]{(33,80),(80,80),(1,9),(2056,2064),(999999985,999999992)})foreach(bool compact in new[]{false,true}) {
            using var f=new CombatItemsFixture(1);
            var player=f.World.Player;player.Creature.CurrentHp=hp;player.Creature.MaxHp=max;
            var reward=(RelicReward)f.Rewards[0];reward.Relic=new Strawberry();
            var first=f.Reader.Read();
            Check(first.MaxHpRewards&&first.HealingRewards&&first.Rewards[0].MaxHpGain==7&&first.Rewards[0].HealAmount==7,"Strawberry declares exact max HP and healing");
            Check(PublicRewardDecisionIdentity.Compute(first)!=PublicRewardDecisionIdentity.Compute(first with {MaxHpRewards=false}),"max HP schema binds decision identity");
            Check(PublicRewardDecisionIdentity.Compute(first)!=PublicRewardDecisionIdentity.Compute(first with {Rewards=new[]{first.Rewards[0] with {MaxHpGain=8}}}),"max HP amount binds decision identity");
            var button=f.Buttons[0];var handler=button.Handler;
            button.Handler=()=>{handler!();player.Creature.MaxHp=max+7;player.Creature.CurrentHp=hp+7;
                if(compact){f.Screen.Children.Remove(button);button.InstanceValid=false;}return Task.CompletedTask;};
            PublicRewardActionRequest.TryCreate(first.DecisionId,"collect:0",out var action);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"Strawberry pickup accepted once");
            var after=f.Reader.Read();
            Check(after.Status==PublicDecisionStatus.Ready&&after.MaxHpRewards&&after.Player.Hp==hp+7&&after.Player.MaxHp==max+7,"Strawberry reconciles exact health with optional button compaction");
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied&&button.ForceClickCalls==1,"Strawberry is never retried");
            PublicRewardActionRequest.TryCreate(after.DecisionId,"proceed",out var exit);
            Check(f.Applier.Apply(exit).Outcome==PublicRewardActionApplyOutcome.Accepted&&f.Reader.Read().Status==PublicDecisionStatus.Complete,"Strawberry reward exits normally");
        }
        foreach(var mode in new[]{"hp_missing","hp_extra","max_missing","max_extra","gold","deck","potion","relic","claimed","model","key","variable","foreign_overlay","early_free","delayed","ordinary_gain"}) {
            using var f=new CombatItemsFixture(1);var player=f.World.Player;
            player.Creature.CurrentHp=33;player.Creature.MaxHp=80;
            var reward=(RelicReward)f.Rewards[0];reward.Relic=new Strawberry();
            if(mode=="ordinary_gain"){reward.Relic=new RelicModel();reward.Relic.Id.Entry="PASSIVE";}
            var first=f.Reader.Read();var button=f.Buttons[0];var handler=button.Handler;
            button.Handler=()=>{
                handler!();player.Creature.CurrentHp=mode=="hp_missing"?33:mode=="hp_extra"?41:40;
                player.Creature.MaxHp=mode=="max_missing"?80:mode=="max_extra"?88:87;
                if(mode=="gold")player.Gold++;
                if(mode=="deck")player.Deck.Cards[0].CurrentUpgradeLevel++;
                if(mode=="potion")player.PotionSlots[0]=new();
                if(mode=="relic")player.Relics.Add(new(){Owner=player});
                if(mode=="claimed")reward.ClaimedRelic=new();
                if(mode=="model")reward.Relic=new Strawberry();
                if(mode=="key")reward.Relic.Id.Entry="CHANGED";
                if(mode=="variable")reward.Relic.DynamicVars["MaxHp"].BaseValue=8m;
                if(mode=="foreign_overlay")f.World.Overlays.Screens.Add(new MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen());
                if(mode is "early_free" or "delayed")reward.SuccessfullySelected=false;
                if(mode=="early_free"){f.Screen.Children.Remove(button);button.InstanceValid=false;}
                return Task.CompletedTask;
            };
            PublicRewardActionRequest.TryCreate(first.DecisionId,"collect:0",out var action);
            Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted,"Strawberry effect dispatches once");
            PublicRewardDecisionSnapshot after=default;bool failed=false;
            try{after=f.Reader.Read();failed=after.Status==PublicDecisionStatus.Unsupported;}catch{failed=true;}
            if(mode=="delayed") {
                Check(after.Status==PublicDecisionStatus.Waiting,"health change alone does not complete Strawberry");
                reward.SuccessfullySelected=true;after=f.Reader.Read();
                Check(after.Status==PublicDecisionStatus.Ready&&after.Player.Hp==40&&after.Player.MaxHp==87,"native reward completion reconciles delayed Strawberry");
            }else Check(failed,"unexpected Strawberry mutation rejected: "+mode);
            try{f.Applier.Apply(action);}catch{}
            Check(button.ForceClickCalls==1,"failed Strawberry action never retried");
        }
        foreach(var mode in new[]{"spoof","wrong_var","wrong_key","overflow","native_cap","late_var","late_key","late_cap"}) {
            using var f=new CombatItemsFixture(1);var reward=(RelicReward)f.Rewards[0];reward.Relic=new Strawberry();
            var first=f.Reader.Read();
            if(mode=="spoof"){reward.Relic=new RelicModel();reward.Relic.Id.Entry="STRAWBERRY";}
            if(mode is "wrong_var" or "late_var")reward.Relic.DynamicVars["MaxHp"].BaseValue=8m;
            if(mode is "wrong_key" or "late_key")reward.Relic.Id.Entry="PASSIVE";
            if(mode=="overflow")f.World.Player.Creature.MaxHp=int.MaxValue-6;
            if(mode is "native_cap" or "late_cap")f.World.Player.Creature.MaxHp=999999995;
            bool failed=false;
            try {
                if(mode.StartsWith("late",StringComparison.Ordinal)) {
                    PublicRewardActionRequest.TryCreate(first.DecisionId,"collect:0",out var action);
                    failed=f.Applier.Apply(action).Outcome!=PublicRewardActionApplyOutcome.Accepted;
                } else failed=f.Reader.Read().Status==PublicDecisionStatus.Unsupported;
            }catch{failed=true;}
            Check(failed&&f.Buttons[0].ForceClickCalls==0,"Strawberry identity rejected before input: "+mode);
        }
        // Another percentage-healing relic may precede or follow max-HP growth.
        foreach(bool waffleFirst in new[]{false,true}) {
            using var f=new CombatItemsFixture(3);var player=f.World.Player;
            player.Creature.CurrentHp=33;player.Creature.MaxHp=85;
            ((RelicReward)f.Rewards[0]).Relic=new Strawberry();
            ((RelicReward)f.Rewards[2]).Relic=new FakeLeesWaffle();
            foreach(var button in f.Buttons.Where(b=>b.Reward is RelicReward)) {
                var handler=button.Handler;button.Handler=()=>{handler!();var model=((RelicReward)button.Reward).Relic;
                    if(model is Strawberry){player.Creature.MaxHp+=7;player.Creature.CurrentHp+=7;}
                    else player.Creature.CurrentHp=Math.Min(player.Creature.MaxHp,player.Creature.CurrentHp+player.Creature.MaxHp/10);
                    f.Screen.Children.Remove(button);button.InstanceValid=false;return Task.CompletedTask;};
            }
            foreach(var key in waffleFirst?new[]{"FAKE_LEES_WAFFLE","STRAWBERRY"}:new[]{"STRAWBERRY","FAKE_LEES_WAFFLE"}) {
                var ready=f.Reader.Read();Check(ready.Status==PublicDecisionStatus.Ready,"mixed health rewards remain ready");
                int slot=ready.Rewards.ToList().FindIndex(r=>r.ItemKey==key);
                PublicRewardActionRequest.TryCreate(ready.DecisionId,"collect:"+slot,out var action);
                Check(f.Applier.Apply(action).Outcome==PublicRewardActionApplyOutcome.Accepted&&f.Reader.Read().Status==PublicDecisionStatus.Ready,"mixed health pickup reconciles: "+key);
            }
            Check(player.Creature.MaxHp==92&&player.Creature.CurrentHp==(waffleFirst?48:49),"percentage healing uses max HP at pickup");
        }
    }
}
