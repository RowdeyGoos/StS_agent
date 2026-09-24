using System;
using System.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;

internal static partial class Program
{
    private static void CombatItemCases()
    {
        EmptyTerminalRewardCases();
        SkippedPotionCases();
        PotionDiscardCases();
        PotionCapacityCases();
        HealingRewardCases();
        MaxHpRewardCases();
        FakeMangoRewardCases();
        ModifiedGoldRewardCases();
        ExpandedTerminalRewardCases();
        foreach(int count in new[]{1,2,3,8})foreach(bool compact in new[]{false,true}) {
            using var f=new CombatItemsFixture(count);
            var reader=f.Reader;var applier=f.Applier;
            var first=reader.Read();Check(first.Status==PublicDecisionStatus.Ready&&first.ItemRewards&&first.Rewards.Count==count,"item screen has bounded stable indices");
            int completed=0;
            while(completed<count) {
                var ready=reader.Read();
                Check(ready.Rewards.Select(r=>r.RewardIndex).Distinct().Count()==ready.Rewards.Count,"duplicate native type indices are disambiguated");
                string action=ready.LegalActions.First(a=>a.StartsWith("collect:",StringComparison.Ordinal));
                int slot=int.Parse(action[8..]);var target=ready.Rewards[slot];
                Check(PublicRewardActionRequest.TryCreate(ready.DecisionId,action,out var request)&&applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.Accepted,"one item dispatch");
                Check(applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied,"duplicate collection rejected");
                if(compact)f.Screen.Children.RemoveAll(n=>n is NRewardButton b&&b.Reward.SuccessfullySelected);
                var after=reader.Read();completed++;
                Check(after.Status==PublicDecisionStatus.Ready&&after.DecisionRevision==completed,"exact inventory insertion reconciles");
                Check(after.Rewards.All(r=>r.RewardIndex!=target.RewardIndex||r.SuccessfullySelected),"stable item identity survives compaction");
            }
            var done=reader.Read();Check(PublicRewardActionRequest.TryCreate(done.DecisionId,"proceed",out var proceed)&&applier.Apply(proceed).Outcome==PublicRewardActionApplyOutcome.Accepted,"all item rewards proceed");
            Check(reader.Read().Status==PublicDecisionStatus.Complete,"item rewards reach map");
            // Item retention ends after the verified reward session. Consuming a
            // potion in the next combat must not poison the next reward reader.
            f.World.Player.PotionSlots[0]=null;f.World.Map.IsOpen=false;
            var next=new NRewardsScreen();var gold=new GoldReward{Player=f.World.Player,RewardsSetIndex=0,Amount=3};next.Children.Add(new NRewardButton{Reward=gold});
            f.World.Overlays.Screens.Clear();f.World.Overlays.Screens.Add(next);
            var fresh=reader.Read();Check(fresh.Status==PublicDecisionStatus.Ready&&!fresh.ItemRewards&&fresh.DecisionRevision>done.DecisionRevision,
                "fresh reward session after legal potion consumption has a new process revision");
        }
        foreach(var mode in new[]{"full","late_full","delayed","wrong_claim","wrong_potion","replace_model","replace_reward","replace_button","drop","reorder","native_index","nested","empty_overlay","deck_change","capacity","relic_replace","settled_move","lost","early_map","foreign_relic"}) {
            using var f=new CombatItemsFixture(2);
            var first=f.Reader.Read();var potion=f.Rewards.OfType<PotionReward>().Single();var relic=f.Rewards.OfType<RelicReward>().Single();
            var button=f.Buttons.Single(b=>ReferenceEquals(b.Reward,potion));
            if(mode=="full")for(int i=0;i<f.World.Player.PotionSlots.Count;i++){var occupied=new PotionModel();occupied.Id.Entry="EXISTING_"+i;f.World.Player.PotionSlots[i]=occupied;}
            if(mode=="foreign_relic")relic.Relic.Owner=new();
            if(mode=="replace_model")potion.Potion=new PotionModel{ }; // same key substitution
            if(mode=="replace_model")potion.Potion.Id.Entry="POTION_1";
            if(mode=="replace_reward")button.Reward=new PotionReward{Player=f.World.Player,Potion=potion.Potion,RewardsSetIndex=2};
            if(mode=="replace_button"){f.Screen.Children.Remove(button);f.Screen.Children.Add(new NRewardButton{Reward=potion});}
            if(mode=="drop")f.Screen.Children.Remove(button);
            if(mode=="reorder")f.Screen.Children.Reverse();
            if(mode=="native_index")potion.RewardsSetIndex=6;
            if(mode is "replace_model" or "replace_reward" or "replace_button" or "drop" or "native_index" or "foreign_relic") {
                bool rejected=false;try{rejected=f.Reader.Read().Status==PublicDecisionStatus.Unsupported;}catch{rejected=true;}
                Check(rejected&&f.Buttons.All(b=>b.ForceClickCalls==0),"item identity rejection before input: "+mode);continue;
            }
            var ready=f.Reader.Read();
            if(mode=="full") {Check(ready.Status==PublicDecisionStatus.Ready&&ready.LegalActions.All(a=>a!="collect:0"),"full potion inventory withholds collection");continue;}
            string action=mode=="relic_replace"?"collect:1":"collect:0";
            if(mode=="late_full")for(int i=0;i<f.World.Player.PotionSlots.Count;i++){var occupied=new PotionModel();occupied.Id.Entry="EXISTING_"+i;f.World.Player.PotionSlots[i]=occupied;}
            var chosen=mode=="relic_replace"?f.Buttons.Single(b=>ReferenceEquals(b.Reward,relic)):button;
            var original=chosen.Handler;
            chosen.Handler=()=>{
                if(mode=="lost")throw new InvalidOperationException("lost input");
                original();
                if(mode=="delayed")potion.SuccessfullySelected=false;
                if(mode=="wrong_claim")potion.ClaimedPotion=new PotionModel();
                if(mode=="wrong_potion")f.World.Player.PotionSlots[0]=new PotionModel();
                if(mode=="nested")f.World.Overlays.Screens.Add(new Control());
                if(mode=="empty_overlay")f.World.Overlays.Screens.Clear();
                if(mode=="deck_change")f.World.Player.Deck.Cards[0].CurrentUpgradeLevel++;
                if(mode=="capacity")f.World.Player.MaxPotionCount++;
                if(mode=="relic_replace")f.World.Player.Relics[^1]=new RelicModel{Owner=f.World.Player};
                if(mode=="early_map")f.World.Map.IsOpen=true;
                return Task.CompletedTask;
            };
            PublicRewardActionRequest.TryCreate(ready.DecisionId,action,out var request);
            bool failed=false;try{failed=f.Applier.Apply(request).Outcome!=PublicRewardActionApplyOutcome.Accepted;}catch{failed=true;}
            if(mode=="late_full"){Check(failed&&chosen.ForceClickCalls==0,"inventory fills between observation and input");continue;}
            if(mode=="lost"){Check(failed&&f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied&&chosen.ForceClickCalls==1,"lost item dispatch cannot retry");continue;}
            Check(!failed&&chosen.ForceClickCalls==1,"item accepted once: "+mode);
            var after=f.Reader.Read();
            if(mode=="delayed"){Check(after.Status==PublicDecisionStatus.Waiting,"item insertion precedes reward completion");potion.SuccessfullySelected=true;after=f.Reader.Read();}
            if(mode is "delayed" or "reorder" or "settled_move")Check(after.Status==PublicDecisionStatus.Ready&&after.DecisionRevision==1,"original item reconciled: "+mode);
            else {Check(after.Status==PublicDecisionStatus.Unsupported,"incorrect item effect stops: "+mode);continue;}
            if(mode=="settled_move") {f.World.Player.PotionSlots[0]=null;f.World.Player.PotionSlots[1]=potion.Potion;Check(f.Reader.Read().Status==PublicDecisionStatus.Unsupported,"settled potion retained through parent proceed");}
        }
        foreach(var mode in new[]{"wrong_player","linked","duplicate","too_many","multiple_special","resume","changed_list","changed_reward","changed_model","missing","native_index","foreign_owner"}) {
            using var f=new CombatItemsFixture(2,start:false);
            if(mode=="wrong_player")f.Rewards[0].Player=new();
            if(mode=="linked")f.Rewards[0].ParentRewardSet=new();
            if(mode=="duplicate")f.Rewards[1]=f.Rewards[0];
            if(mode=="too_many")while(f.Rewards.Count<9)f.Rewards.Add(new PotionReward{Player=f.World.Player,RewardsSetIndex=2,IsPopulated=false});
            if(mode=="multiple_special") {
                f.Rewards[0]=new SpecialCardReward(SpecialFixtureCard(f.World,"FIRST"),f.World.Player);
                f.Rewards[1]=new SpecialCardReward(SpecialFixtureCard(f.World,"SECOND"),f.World.Player);
            }
            bool entered=f.Enter(mode=="resume");
            if(mode is "wrong_player" or "linked" or "duplicate" or "too_many" or "multiple_special" or "resume"){Check(!entered,"unsupported extra entries: "+mode);continue;}
            Check(entered,"deferred extra item entry accepted");f.Populate();Check(f.World.Adapter.CombatScope!(),"generated item becomes bound");
            switch(mode) {
                case "changed_list": f.Room.ExtraRewards[f.World.Player]=f.Rewards.ToList();break;
                case "changed_reward": f.Room.ExtraRewards[f.World.Player][0]=new RelicReward{Player=f.World.Player};break;
                case "changed_model": ((RelicReward)f.Rewards[0]).Relic=new();break;
                case "missing": f.Room.ExtraRewards[f.World.Player].RemoveAt(0);break;
                case "native_index": f.Rewards[0].RewardsSetIndex=7;break;
                case "foreign_owner": ((RelicReward)f.Rewards[0]).Relic.Owner=new();break;
            }
            Check(!f.World.Adapter.CombatScope!(),"retained extra item identity: "+mode);
        }
    }
    private static void EmptyTerminalRewardCases()
    {
        foreach (string mode in new[]{"ok","loading","button_loading","nonterminal","set_player","foreign_player","multiple_players","abandoned","screen_run","active_run","room",
            "replace_set","replace_player","replace_run","replace_room","replace_manager","append_reward","extra_overlay","replace_button","disable_button"})
        {
            using var f = new CombatItemsFixture(0, start:false);
            var run = (RunState)f.World.Player.RunState;
            run.Players.Add(f.World.Player);
            run.CurrentRoom = f.Room;
            var set = new RewardsSet { Player=f.World.Player, Room=f.Room };
            f.Screen.BindRewards(set, run);
            var button = new MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton {IsEnabled=true};
            f.Screen.BindProceed(button);
            f.World.Overlays.Screens.Add(f.Screen);
            var transition = new EmptyRewardTransition();
            var applier = new PinnedPublicRewardActionApplier(f.Reader, screen => {
                Check(ReferenceEquals(screen, f.Screen), "empty reward dispatch retains its native screen");
                return transition;
            });
            if (mode == "nonterminal") f.Screen.BindRewards(set, run, false);
            if (mode == "set_player") set.Player = new();
            if (mode == "foreign_player") set.Player = new(){RunState=run};
            if (mode == "multiple_players") run.Players.Add(new(){RunState=run});
            if (mode == "abandoned") RunManager.Instance!.IsAbandoned=true;
            if (mode == "screen_run") f.Screen.BindRewards(set, new RunState());
            if (mode == "active_run") RunManager.Instance!.State = new();
            if (mode == "room") set.Room = new AbstractRoom();
            if (mode == "loading") set.Rewards.Add(new GoldReward {Player=f.World.Player, Amount=3, RewardsSetIndex=0});
            if (mode == "button_loading") button.IsEnabled=false;
            var first = f.Reader.Read();
            if (mode == "button_loading") {
                Check(first.Status == PublicDecisionStatus.Waiting, "empty reward waits for native Proceed enablement");
                button.IsEnabled=true;
                Check(f.Reader.Read().Status == PublicDecisionStatus.Ready, "empty reward becomes ready when Proceed is enabled");
                continue;
            }
            if (mode == "loading") {
                Check(first.Status == PublicDecisionStatus.Waiting, "unrendered nonempty reward set cannot publish Proceed");
                f.Screen.Children.Add(new NRewardButton {Reward=set.Rewards[0]});
                Check(f.Reader.Read().Status == PublicDecisionStatus.Ready, "loaded original reward remains readable");
                continue;
            }
            if (mode is "nonterminal" or "set_player" or "foreign_player" or "multiple_players" or "abandoned" or "screen_run" or "active_run" or "room") {
                Check(first.Status == PublicDecisionStatus.Unsupported && transition.Dispatches == 0, "invalid empty reward owner before input: " + mode);
                continue;
            }
            Check(first.Status == PublicDecisionStatus.Ready && first.Rewards.Count == 0 &&
                first.LegalActions.SequenceEqual(new[]{"proceed"}) && first.Player.Gold == f.World.Player.Gold,
                "fresh empty terminal screen exposes only Proceed for the exact set owner: " + mode);
            switch (mode) {
                case "replace_set": f.Screen.BindRewards(new RewardsSet {Player=f.World.Player, Room=f.Room}, run); break;
                case "replace_player": set.Player=new(){RunState=run}; break;
                case "replace_run": var other=new RunState{CurrentRoom=f.Room};set.Player.RunState=other;RunManager.Instance!.State=other;f.Screen.BindRewards(set,other);break;
                case "replace_room": set.Room=new AbstractRoom();run.CurrentRoom=set.Room;break;
                case "replace_manager": RunManager.Instance=new(){State=run};break;
                case "append_reward": set.Rewards.Add(new GoldReward {Player=f.World.Player});break;
                case "extra_overlay": f.World.Overlays.Screens.Insert(0,new Control());break;
                case "replace_button": f.Screen.BindProceed(new(){IsEnabled=true});break;
                case "disable_button": button.IsEnabled=false;break;
            }
            Check(PublicRewardActionRequest.TryCreate(first.DecisionId, "proceed", out var request), "empty reward request parses");
            var result = applier.Apply(request);
            if (mode != "ok") {
                Check(result.Outcome != PublicRewardActionApplyOutcome.Accepted && transition.Dispatches == 0,
                    "empty reward identity is revalidated before dispatch: " + mode);
                continue;
            }
            Check(result.Outcome == PublicRewardActionApplyOutcome.Accepted && transition.Dispatches == 1,
                "empty terminal reward dispatches exactly once");
            Check(applier.Apply(request).Outcome == PublicRewardActionApplyOutcome.AlreadyApplied && transition.Dispatches == 1,
                "empty reward Proceed is never retried");
            Check(f.Reader.Read().Status == PublicDecisionStatus.Waiting, "accepted Proceed waits for native transition");
            transition.Complete = true;
            var complete = f.Reader.Read();
            Check(complete.Status == PublicDecisionStatus.Complete && complete.ScreenKind == "ending" && transition.Disposed,
                "empty reward completion retains ending destination after transition cleanup");
        }
    }
    private sealed class EmptyRewardTransition : IPublicRewardTransition
    {
        internal int Dispatches;
        internal bool Complete, Disposed;
        public void Dispatch() => Dispatches++;
        public string Poll() => Complete ? "ending" : "waiting";
        public void Dispose() => Disposed=true;
    }
    private static void SkippedPotionCases()
    {
        foreach(var mode in new[]{"full","available","inventory","model","claimed","selected","deck","capacity","fault","cancel","lost","delay","no_map","foreign_screen"}) {
            using var f=new CombatItemsFixture(2);
            if(mode=="full")for(int i=0;i<8;i++){var p=new PotionModel();p.Id.Entry="EXISTING_"+i;f.World.Player.PotionSlots[i]=p;}
            var first=f.Reader.Read();
            // Collect the relic first; the potion stays visibly unclaimed.
            PublicRewardActionRequest.TryCreate(first.DecisionId,"collect:1",out var relic);
            Check(f.Applier.Apply(relic).Outcome==PublicRewardActionApplyOutcome.Accepted,"relic before skipped potion");
            var ready=f.Reader.Read();
            var potion=f.Rewards.OfType<PotionReward>().Single();
            var task=new TaskCompletionSource();
            var manager=RunManager.Instance!;
            manager.ProceedHandler=()=>{
                if(mode=="lost")throw new InvalidOperationException("lost proceed");
                if(mode=="inventory") {var p=new PotionModel();p.Id.Entry="OTHER";f.World.Player.PotionSlots[0]=p;}
                if(mode=="model"){var p=new PotionModel();p.Id.Entry=potion.Potion.Id.Entry;potion.Potion=p;}
                if(mode=="claimed")potion.ClaimedPotion=potion.Potion;
                if(mode=="selected")potion.SuccessfullySelected=true;
                if(mode=="deck")f.World.Player.Deck.Cards[0].CurrentUpgradeLevel++;
                if(mode=="capacity")f.World.Player.MaxPotionCount--;
                if(mode=="foreign_screen"){f.World.Overlays.Screens.Clear();f.World.Overlays.Screens.Add(new Control());return task.Task;}
                f.World.Overlays.Screens.Clear();
                if(mode!="no_map")f.World.Map.IsOpen=true;
                return mode=="fault"?Task.FromException(new Exception("failed")):mode=="cancel"?Task.FromCanceled(new System.Threading.CancellationToken(true)):
                    mode is "delay" or "no_map"?task.Task:Task.CompletedTask;
            };
            PublicRewardActionRequest.TryCreate(ready.DecisionId,"proceed",out var proceed);
            bool accepted=false;try{accepted=f.Applier.Apply(proceed).Outcome==PublicRewardActionApplyOutcome.Accepted;}catch{}
            Check(accepted==(mode!="lost")&&manager.ProceedCalls==1,"one native potion-skip exit: "+mode);
            Check(f.Applier.Apply(proceed).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied&&manager.ProceedCalls==1,"uncertain exit never repeats");
            if(mode=="lost")continue;
            var after=f.Reader.Read();
            if(mode is "delay" or "no_map") {
                Check(after.Status==PublicDecisionStatus.Waiting,"wait for exact exit task/map");
                task.SetResult();f.World.Map.IsOpen=true;after=f.Reader.Read();
            }
            Check(after.Status==(mode is "full" or "available" or "delay" or "no_map"?PublicDecisionStatus.Complete:PublicDecisionStatus.Unsupported),"verify unclaimed potion and unchanged inventory: "+mode);
            Check(f.Buttons.Single(b=>b.Reward is PotionReward).ForceClickCalls==0,"skipping sends no potion click");
        }
    }
    private static void ExpandedTerminalRewardCases()
    {
        foreach(int count in new[]{10,32})foreach(bool compact in new[]{false,true}) {
            // Populate the terminal screen directly: the event-entry extra-reward
            // bound is a separate contract, not the terminal reader's bound.
            using var f=new CombatItemsFixture(0);
            for(int i=0;i<count;i++) {
                var relic=new RelicModel();relic.Id.Entry="EXPANDED_"+i;
                var reward=new RelicReward{Player=f.World.Player,RewardsSetIndex=3,IsPopulated=true,Relic=relic};
                var button=new NRewardButton{Reward=reward};
                button.Handler=()=>{reward.ClaimedRelic=relic;relic.Owner=f.World.Player;f.World.Player.Relics.Add(relic);reward.SuccessfullySelected=true;return Task.CompletedTask;};
                f.Screen.Children.Add(button);f.Buttons.Add(button);
            }
            for(int claimed=0;claimed<count;claimed++) {
                var ready=f.Reader.Read();
                Check(ready.Status==PublicDecisionStatus.Ready&&ready.ExpandedRewards,"expanded terminal screen stays schema nine through compaction");
                // Choose from the far end to exercise multi-digit slots.
                string action=ready.LegalActions.Last(a=>a.StartsWith("collect:",StringComparison.Ordinal));
                Check(PublicRewardActionRequest.TryCreate(ready.DecisionId,action,out var request)&&f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.Accepted,"expanded exact pickup accepted");
                if(compact)f.Screen.Children.RemoveAll(n=>n is NRewardButton b&&b.Reward.SuccessfullySelected);
                var after=f.Reader.Read();
                Check(after.Status==PublicDecisionStatus.Ready&&after.DecisionRevision==claimed+1&&after.ExpandedRewards,"expanded pickup reconciles once");
                Check(f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.AlreadyApplied,"expanded replay rejected");
            }
            var done=f.Reader.Read();PublicRewardActionRequest.TryCreate(done.DecisionId,"proceed",out var exit);
            Check(f.Applier.Apply(exit).Outcome==PublicRewardActionApplyOutcome.Accepted&&f.Reader.Read().Status==PublicDecisionStatus.Complete,"expanded screen completes to map");
            Check(f.Buttons.All(b=>b.ForceClickCalls==1),"every expanded target input once");
        }
        using(var f=new CombatItemsFixture(0)) {
            for(int i=0;i<33;i++)f.Screen.Children.Add(new NRewardButton{Reward=new GoldReward{Player=f.World.Player,RewardsSetIndex=i,Amount=1}});
            Check(f.Reader.Read().Status==PublicDecisionStatus.Unsupported,"thirty-three rewards rejected before input");
        }
    }

    private sealed class CombatItemsFixture : IDisposable
    {
        internal readonly Fixture World=new("COMBAT_ITEMS");
        internal readonly List<Reward> Rewards=new();
        internal readonly List<NRewardButton> Buttons=new();
        internal readonly NRewardsScreen Screen=new();
        internal readonly PinnedPublicRewardDecisionReader Reader=new();
        internal readonly PinnedPublicRewardActionApplier Applier;
        internal readonly CombatRoom Room;
        private readonly EncounterModel _encounter=new();
        internal CombatItemsFixture(int count,bool start=true)
        {
            Applier=new(Reader);foreach(var card in World.Cards)card.Owner=World.Player;
            World.Player.MaxPotionCount=8;World.Player.PotionSlots.Clear();for(int i=0;i<8;i++)World.Player.PotionSlots.Add(null);
            var run=(RunState)World.Player.RunState;
            var state=new CombatState{Encounter=_encounter,RunState=run};state.Players.Add(World.Player);
            Room=new(){CombatState=state,ParentEventId=World.Model.Id};
            RunManager.Instance=new(){State=run};CombatManager.Instance=new(){State=null};
            for(int i=0;i<count;i++)Rewards.Add(i%2==0?new RelicReward{Player=World.Player,RewardsSetIndex=3,IsPopulated=false}:new PotionReward{Player=World.Player,RewardsSetIndex=2,IsPopulated=false});
            World.Model.CombatEntry=(_,extras,_)=>{Room.ExtraRewards[World.Player]=extras.ToList();run.CurrentRoom=Room;CombatManager.Instance.State=state;NCombatRoom.Instance=new();NCombatRoom.Instance.SetVisuals(Room);};
            if(!start)return;
            Check(Enter(),"Punch Off deferred relic/potion entries enter combat");Populate();Check(World.Adapter.CombatScope!(),"post-generation extra identities retained");World.Adapter.Dispose();
            foreach(var reward in Rewards) {
                var button=new NRewardButton{Reward=reward};Buttons.Add(button);Screen.Children.Add(button);
                button.Handler=()=>{
                    if(reward is PotionReward p){p.ClaimedPotion=p.Potion;p.Potion.Owner=World.Player;World.Player.PotionSlots[World.Player.PotionSlots.FindIndex(x=>x is null)]=p.Potion;}
                    else {var r=(RelicReward)reward;r.ClaimedRelic=r.Relic;r.Relic.Owner=World.Player;World.Player.Relics.Add(r.Relic);}
                    reward.SuccessfullySelected=true;return Task.CompletedTask;
                };
            }
            World.Overlays.Screens.Add(Screen);
        }
        internal bool Enter(bool resume=false) {
            World.Room.Layout.OptionButtons[0].Option.Callback=()=>{World.Model.EnterCombatWithoutExitingEvent(_encounter,Rewards,resume);return Task.CompletedTask;};
            var ready=World.Session.Read();World.Session.Apply(ready.DecisionId,"choose:0");return World.Session.Read().Phase=="combat_handoff";
        }
        internal void Populate() {
            for(int i=0;i<Rewards.Count;i++) {
                if(Rewards[i] is PotionReward p){p.Potion=new();p.Potion.Id.Entry="POTION_"+i;}
                else {var r=(RelicReward)Rewards[i];r.Relic=new();r.Relic.Id.Entry="RELIC_"+i;}
                Rewards[i].IsPopulated=true;
            }
        }
        public void Dispose()=>World.Dispose();
    }
}
