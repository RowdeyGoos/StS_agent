using System;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Potions;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
internal static partial class Program {
    private static void MerchantFightCases() {
        foreach(string mode in new[]{"success","delayed_queue","delayed_dialogue","slot_after_guard","illegal","node","relic_owner","wrong_rewards","dispose_pending"}) {
            using var f=new MerchantFixture();var player=f.World.Player;var state=(RunState)player.RunState;f.Model.Node=f.Screen;
            RunManager.Instance=new(){State=state};CombatManager.Instance=new(){IsInProgress=false};
            var potion=new FoulPotion{Owner=player};player.PotionSlots[0]=potion;
            var old=new RelicModel{Owner=player};old.Id.Entry="OLD_RELIC";player.Relics.Add(old);
            UsePotionAction? queued=null;var dialogue=new TaskCompletionSource();int entries=0;
            if(mode is "delayed_queue" or "slot_after_guard" or "illegal" or "dispose_pending")RunManager.Instance.ActionQueueSynchronizer.GeneralHandler=a=>queued=(UsePotionAction)a;
            if(mode=="slot_after_guard")RunManager.Instance.ActionQueueSynchronizer.GeneralHandler=a=>{queued=(UsePotionAction)a;a.BeforeExecuted+=_=>player.PotionSlots[0]=new FoulPotion{Owner=player};};
            f.Model.FoulHandler=async _=>{
                if(mode is "delayed_dialogue" or "node" or "relic_owner")await dialogue.Task;
                f.Model.StartedFight=true;var rug=new RelicModel();rug.Id.Entry="FAKE_MERCHANTS_RUG";
                var extras=new[]{new RelicReward{Player=player,Relic=rug}}.Concat(f.Screen.Inventory.Slots.Select(s=>new RelicReward{Player=player,Relic=((MegaCrit.Sts2.Core.Entities.Merchant.MerchantRelicEntry)s.Entry).Model})).Cast<Reward>().ToArray();
                if(mode=="wrong_rewards")extras=extras.Take(1).ToArray();
                f.Model.EnterCombatWithoutExitingEvent(new FakeMerchantEventEncounter(),extras,false);
            };
            f.Model.CombatEntry=(encounter,rewards,resume)=>{
                entries++;var combat=new CombatState{Encounter=encounter,RunState=state};combat.Players.Add(player);
                var room=new CombatRoom{CombatState=combat,ParentEventId=f.Model.Id};room.ExtraRewards[player]=rewards.ToList();
                state.CurrentRoom=room;CombatManager.Instance.State=combat;CombatManager.Instance.IsInProgress=true;
                NCombatRoom.Instance=new();NCombatRoom.Instance.SetVisuals(room);f.Model.Node=null;
            };
            try {
                var ready=f.Session.Read();var choice=ready.Candidates.Single(c=>c.StableId=="FAKE_MERCHANT.FOUL_POTION.0");
                Check(f.Session.Apply(ready.DecisionId,choice.ActionId).Outcome=="accepted","explicit native Foul Potion dispatch");
                if(mode=="illegal")potion.Legal=false;
                if(mode=="dispose_pending") {
                    try{f.Session.Dispose();}catch{}try{queued!.Execute().GetAwaiter().GetResult();}catch{}
                    Check(!potion.HasBeenRemovedFromState&&entries==0,"aborted merchant action stays guarded");continue;
                }
                if(queued is not null)try{queued.Execute().GetAwaiter().GetResult();}catch{}
                if(mode is "delayed_dialogue" or "node" or "relic_owner") {
                    Check(f.Session.Read().Status=="waiting","native merchant dialogue pending");
                    if(mode=="node")f.World.Room.CustomEventNode=new Godot.Control();
                    if(mode=="relic_owner")old.Owner=new();
                    dialogue.SetResult();
                }
                var result=f.Session.Read();
                if(mode is "success" or "delayed_queue" or "delayed_dialogue") {
                    Check(result.Phase=="combat_handoff"&&result.ParentReconciled==1&&entries==1&&potion.HasBeenRemovedFromState,"potion consumption and exact combat handoff");
                    var scope=f.World.Adapter.CombatScope!;f.World.Adapter.Dispose();Check(scope(),"custom combat lease survives successful owner cleanup");
                }else Check(result.Status=="unsupported"&&result.ParentReconciled==0,"merchant fight mutation stops "+mode);
            }finally{typeof(GenericEventV7MerchantFight).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);}
        }
    }
}
