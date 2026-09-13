using System;
using System.Linq;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Entities.Players;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static partial class Program {
    private static GenericEventV7RewardRead PolicyRead(ItemFixture f,GenericEventV7Observation c)=>((GenericEventV7RewardChildRead)f.Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
    private static void PolicyAct(ItemFixture f,GenericEventV7Observation c,string action) {
        var o=PolicyRead(f,c);Check(o.Status=="ready"&&o.LegalActions.Contains(action),"policy advertised "+action);
        var receipt=((GenericEventV7RewardChildApply)f.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,action)).Value;
        Check(receipt.Outcome=="accepted","policy accepted "+action);
    }
    internal static void PreparePolicy(ItemFixture f,bool skip=true) {
        f.PolicyInventory=true;f.Set.DisallowSkipping=!skip;FillEventBelt(f.Player);
        CombatManager.Instance=new(){IsInProgress=false};RunManager.Instance=new(){State=(RunState)f.Player.RunState};
    }
    private static void ItemPolicyCases() {
        foreach(string mode in new[]{"skip","replace","relic_then_skip","two_replacements","mandatory"}) {
            var kinds=mode=="relic_then_skip"?new[]{"relic","potion"}:mode=="two_replacements"?new[]{"potion","potion"}:new[]{"potion"};
            using var f=new ItemFixture("POLICY_"+mode,kinds[0],itemKinds:kinds);PreparePolicy(f,mode!="mandatory");
            var original=f.Player.PotionSlots.ToArray();var c=f.Start();Check(c.Child?.Kind=="item_policy","owned full belt policy child");
            if(mode=="skip")PolicyAct(f,c,"skip_remaining");
            else if(mode=="relic_then_skip"){PolicyAct(f,c,"collect:0");Check(PolicyRead(f,c).Status=="ready","relic before skip");PolicyAct(f,c,"skip_remaining");}
            else for(int i=0;i<kinds.Length;i++) {
                PolicyAct(f,c,"discard:"+i);Check(PolicyRead(f,c).PriorResults.Last().Result=="discarded","discard independently reconciled");
                PolicyAct(f,c,"collect:"+i);PolicyRead(f,c);
            }
            var end=PolicyRead(f,c);Check(end.Status=="resolved","policy native screen/callback closed");
            Check(f.Player.PotionSlots.Skip(mode=="skip"||mode=="relic_then_skip"?0:kinds.Length).SequenceEqual(original.Skip(mode=="skip"||mode=="relic_then_skip"?0:kinds.Length)),"unreplaced original potions retained");
            var p=f.Session.Read();Check(p.CompletedItemChildren==1&&p.Phase=="proceed","policy completes parent");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","policy map handoff");
        }
        foreach(bool skip in new[]{false,true}) {
            using var f=new CardRewardSetFixture(kinds:new[]{"potion","card","potion"});PreparePolicy(f.World);
            f.AfterItemCollection=reward=>{if(reward is MegaCrit.Sts2.Core.Rewards.PotionReward potion)potion.Potion.Owner=f.World.Player;};
            var c=f.Start();Check(c.Child?.Kind=="item_policy","mixed full-belt policy admitted");
            PolicyAct(f.World,c,"collect:1");var menu=PolicyRead(f.World,c);Check(menu.Phase=="choose_card"&&menu.Cards.Count==3,"mixed policy exposes native cards");
            PolicyAct(f.World,c,skip?"skip_card":"choose:2");PolicyRead(f.World,c);
            PolicyAct(f.World,c,"discard:0");PolicyRead(f.World,c);PolicyAct(f.World,c,"collect:0");PolicyRead(f.World,c);
            PolicyAct(f.World,c,"skip_remaining");Check(PolicyRead(f.World,c).Status=="resolved","mixed choose/skip/replacement/native dismissal");
        }
        foreach(bool remove in new[]{false,true}) {
            var f=new CardRewardSetFixture(kinds:new[]{"potion","card","potion"});PreparePolicy(f.World);
            try {
                var c=f.Start();PolicyAct(f.World,c,"collect:1");PolicyRead(f.World,c);PolicyAct(f.World,c,"choose:0");PolicyRead(f.World,c);
                var selected=f.World.Player.Deck.Cards.Last();if(remove)f.World.Player.Deck.Cards.Remove(selected);else selected.CurrentUpgradeLevel++;
                Check(PolicyRead(f.World,c).Status=="unsupported","settled mixed card effect retained");
            }finally{try{f.Dispose();}catch(InvalidOperationException){}}
        }
        foreach(string bad in new[]{"ordinary_relic_slots","ordinary_relic_capacity","foreign_offer","original_owner","settled_owner","settled_claim","queued_cancel"}) {
            var f=new ItemFixture("POLICY_BAD", "relic",itemKinds:new[]{"relic","potion"});PreparePolicy(f);
            try {
            if(bad=="foreign_offer")f.BeforeScreen=()=>((RelicModel)f.Offered).Owner=new Player();
            if(bad=="ordinary_relic_slots")f.AfterCollection=()=>f.Player.PotionSlots[1]=null;
            if(bad=="ordinary_relic_capacity")f.AfterCollection=()=>{f.Player.PotionSlots.Add(null);f.Player.MaxPotionCount++;};
            var c=f.Start();if(bad=="foreign_offer"){Check(c.Status=="unsupported","foreign item offer rejected before input");continue;}
            if(bad=="original_owner")f.Player.PotionSlots[1]!.Owner=new Player();
            else if(bad=="queued_cancel") {
                MegaCrit.Sts2.Core.GameActions.DiscardPotionGameAction? queued=null;RunManager.Instance!.ActionQueueSynchronizer.Handler=a=>queued=a;
                PolicyAct(f,c,"discard:0");f.Player.PotionSlots[1]=null;Check(PolicyRead(f,c).Status=="unsupported","changed queued belt stops");
                try{queued!.Execute();}catch{}Check(!f.Player.PotionSlots[0]!.HasBeenRemovedFromState,"failed policy prevents queued discard");continue;
            }else {PolicyAct(f,c,"collect:0");if(bad is "settled_owner" or "settled_claim"){Check(PolicyRead(f,c).Status=="ready","ordinary relic settled");if(bad=="settled_owner")((RelicModel)f.Offered).Owner=new Player();else ((MegaCrit.Sts2.Core.Rewards.RelicReward)f.Reward).ClaimedRelic=new RelicModel();}}
            Check(PolicyRead(f,c).Status=="unsupported","item policy mutation rejected "+bad);
            }finally{try{f.Dispose();}catch(InvalidOperationException){Check(true,"failed policy cannot cleanly hand off");}}
        }
    }
}
