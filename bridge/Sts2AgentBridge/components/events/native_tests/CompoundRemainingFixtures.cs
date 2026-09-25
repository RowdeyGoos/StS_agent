using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Potions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.GenericEventV7;

namespace MegaCrit.Sts2.Core.Models.Relics
{
    public sealed class LeafyPoultice:OfferRelicFixture {public LeafyPoultice(){Id.Entry="LEAFY_POULTICE";}}
    public sealed class LargeCapsule:OfferRelicFixture {public LargeCapsule(){Id.Entry="LARGE_CAPSULE";DynamicVars["Relics"]=new(){IntValue=2};}}
    public sealed class PhialHolster:OfferRelicFixture {public PhialHolster(){Id.Entry="PHIAL_HOLSTER";DynamicVars["PotionSlots"]=new(){IntValue=1};DynamicVars["Potions"]=new(){IntValue=2};}}
}
namespace MegaCrit.Sts2.Core.Entities.Potions
{
    public enum PotionProcureFailureReason {None,TooFull,NotAllowed}
    public sealed class PotionProcureResult {public bool success;public PotionModel potion=null!;public PotionProcureFailureReason failureReason;}
}
namespace MegaCrit.Sts2.Core.Entities.Players
{
    public sealed partial class Creature
    {
        [MethodImpl(MethodImplOptions.NoInlining)]public void LoseHpInternal(decimal amount,int props)
        {CurrentHp=Math.Max(CurrentHp-(int)Math.Min(amount,999999999m),0);}
    }
    public sealed partial class Player
    {
        [MethodImpl(MethodImplOptions.NoInlining)]public PotionProcureResult AddPotionInternal(PotionModel potion,int slotIndex=-1,bool silent=false)
        {
            int slot=slotIndex<0?PotionSlots.FindIndex(p=>p is null):slotIndex;
            if(slot<0||PotionSlots[slot] is not null)return new(){potion=potion,failureReason=PotionProcureFailureReason.TooFull};
            potion.Owner=this;PotionSlots[slot]=potion;return new(){potion=potion,success=true};
        }
    }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static class PotionCmd
    {
        public static bool Prevent,WrongResult,DirectInsertion;
        public static Func<PotionModel,Task>? After;
        [MethodImpl(MethodImplOptions.NoInlining)]public static async Task<PotionProcureResult> TryToProcure(PotionModel potion,Player player,int slotIndex=-1)
        {
            if(Prevent)return new(){potion=potion,failureReason=PotionProcureFailureReason.NotAllowed};
            PotionProcureResult result;
            if(DirectInsertion){potion.Owner=player;player.PotionSlots[0]=potion;result=new(){potion=potion,success=true};}
            else result=player.AddPotionInternal(potion,slotIndex);
            if(result.success&&After is not null)await After(potion);
            return WrongResult?new(){potion=new PotionModel(),success=result.success,failureReason=result.failureReason}:result;
        }
    }
}
internal static partial class Program
{
    private static void CompoundRemainingCases()
    {
        foreach(string mode in new[]{"two","one","none","delay","fault","wrong","missing","egg","foreign","full_hp","hp_delay","hp_fault"}) {
            using var f=new CompoundRewardFixture();using var native=new CompoundDeckFixture(f,"transform");
            var player=f.World.Player;player.Creature.CurrentHp=mode is "full_hp" or "hp_delay" or "hp_fault"?player.Creature.MaxHp:40;
            var damageGate=new TaskCompletionSource();
            var basics=mode=="none"?Array.Empty<CardModel>():f.World.Cards.Take(mode=="one"?1:2).ToArray();
            for(int i=0;i<basics.Length;i++){basics[i].Rarity="Basic";basics[i].Tags=new[]{i==0?"Strike":"Defend"};}
            var leaf=new LeafyPoultice();((RelicReward)f.Root.Rewards[0]).Relic=leaf;
            native.DelayMutation=mode is "delay" or "fault" or "foreign";
            if(mode=="egg")MegaCrit.Sts2.Core.Hooks.Hook.Modifier=(_,card)=>{card.UpgradeInternal();return card;};
            leaf.Handler=async()=>{
                int maximum=player.Creature.MaxHp-12;
                if(player.Creature.CurrentHp>maximum) {
                    player.Creature.LoseHpInternal(player.Creature.CurrentHp-maximum,default);
                    if(mode is "hp_delay" or "hp_fault")await damageGate.Task;
                }
                player.Creature.SetMaxHpInternal(maximum);
                if(mode!="missing")await CardCmd.Transform((mode=="wrong"?new[]{f.World.Cards.Last()}:basics).Select(c=>new CardTransformation(c)).ToList(),new(),default);
            };
            var c=f.Start();var start=f.Read(c);
            var receipt=(GenericEventV7RewardChildApply)f.World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,start.DecisionId,"collect:0");
            Check(receipt.Value.Outcome is "accepted" or "uncertain","Leafy native input once "+mode);var read=f.Read(c);
            if(mode is "hp_delay" or "hp_fault") {
                Check(read.Status=="waiting"&&player.Creature.CurrentHp==player.Creature.MaxHp-12,"native health loss retained before maximum changes");
                if(mode=="hp_fault")damageGate.SetException(new InvalidOperationException("damage task fault"));else damageGate.SetResult();read=f.Read(c);
            }
            if(mode is "delay" or "fault" or "foreign") {
                Check(read.Status=="waiting","automatic transform retains actual command task");
                if(mode=="foreign"){player.Gold++;Check(f.Read(c).Status=="unsupported","foreign automatic-transform scalar rejected");continue;}
                if(mode=="fault")native.Mutation.SetException(new InvalidOperationException("transform fault"));else native.Mutation.SetResult();read=f.Read(c);
            }
            Check(read.Status==(mode is "fault" or "wrong" or "missing" or "hp_fault"?"unsupported":"resolved"),"Leafy Poultice "+mode+" "+read.Status);
            if(read.Status=="resolved")Check(basics.All(b=>!player.Deck.Cards.Contains(b))&&player.Deck.Cards.Count==3&&f.World.Session.Read().ParentReconciled==1,"exact automatic targets retain parent");
        }
        foreach(string mode in new[]{"normal","upgrades","capacity","child_delay","child_fault","add_delay","add_fault","wrong_add","missing_child","missing_add","foreign","forbidden_child","curse","egg","prevented"}) {
            using var f=new CompoundRewardFixture(tail:mode=="curse"?"curse":null);var player=f.World.Player;
            var gate=new TaskCompletionSource();var capsule=new LargeCapsule();((RelicReward)f.Root.Rewards[0]).Relic=capsule;
            var coin=new OldCoin{Gate=mode is "child_delay" or "child_fault"?gate.Task:Task.CompletedTask};
            var second=mode=="upgrades"?(RelicModel)new Whetstone():mode=="capacity"?new PotionBelt():mode=="forbidden_child"?new LeadPaperweight():new RelicModel();
            if(second.Id.Entry.Length==0)second.Id.Entry="SECOND_CAPSULE_RELIC";
            CardModel Basic(string tag){var card=new CardModel{Owner=player,Rarity="Basic",Tags=new[]{tag},IsUpgradable=true};card.Id.Entry="BASIC_"+tag.ToUpperInvariant();return card;}
            capsule.Handler=async()=>{
                await RelicCmd.Obtain(coin,player);if(mode!="missing_child")await RelicCmd.Obtain(second,player);
                if(mode=="foreign")player.Gold++;
                await CardPileCmd.Add(Basic(mode=="wrong_add"?"Defend":"Strike"),PileType.Deck);
                if(mode!="missing_add")await CardPileCmd.Add(Basic("Defend"),PileType.Deck);
            };
            if(mode is "add_delay" or "add_fault")CardPileCmd.AfterAdded=_=>gate.Task;
            if(mode=="egg")MegaCrit.Sts2.Core.Hooks.Hook.Modifier=(_,card)=>{card.UpgradeInternal();return card;};
            if(mode=="prevented")CardPileCmd.Prevent=_=>true;
            var c=f.Start();var start=f.Read(c);
            var receipt=(GenericEventV7RewardChildApply)f.World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,start.DecisionId,"collect:0");
            Check(receipt.Value.Outcome is "accepted" or "uncertain","capsule dispatch once");var read=f.Read(c);
            if(mode.EndsWith("delay")||mode.EndsWith("fault")) {
                Check(read.Status=="waiting","capsule awaits actual task "+mode);
                if(mode.EndsWith("fault"))gate.SetException(new InvalidOperationException("capsule fault"));else gate.SetResult();read=f.Read(c);
            }
            if(mode=="curse")read=f.Act(c,"collect:1");
            bool bad=mode is "child_fault" or "add_fault" or "wrong_add" or "missing_child" or "missing_add" or "foreign" or "forbidden_child";
            Check(read.Status==(bad?"unsupported":"resolved"),"Large Capsule "+mode+" "+read.Status);
            if(!bad)Check(player.Deck.Cards.Count==(mode=="prevented"?3:mode=="curse"?6:5)&&f.World.Session.Read().ParentReconciled==1,"capsule exact cards and final parent");
            CardPileCmd.AfterAdded=null;CardPileCmd.Prevent=null;MegaCrit.Sts2.Core.Hooks.Hook.Modifier=null;
        }
        foreach(string mode in new[]{"normal","full","prevented","delay","fault","wrong_result","direct","extra","missing","capacity","foreign","curse"}) {
            using var f=new CompoundRewardFixture(tail:mode=="curse"?"curse":null);var player=f.World.Player;
            var gate=new TaskCompletionSource();var phial=new PhialHolster();((RelicReward)f.Root.Rewards[0]).Relic=phial;
            PotionModel Potion(string key){var potion=new PotionModel();potion.Id.Entry=key;return potion;}
            if(mode=="full")for(int i=0;i<3;i++){var potion=Potion("OLD_"+i);potion.Owner=player;player.PotionSlots[i]=potion;}
            var potions=new[]{Potion("GRANTED_A"),Potion("GRANTED_B"),Potion("EXTRA")};
            PotionCmd.Prevent=mode=="prevented";PotionCmd.WrongResult=mode=="wrong_result";PotionCmd.DirectInsertion=mode=="direct";
            PotionCmd.After=mode is "delay" or "fault" or "foreign"?_=>gate.Task:null;
            phial.Handler=async()=>{
                player.AddToMaxPotionCount(mode=="capacity"?2:1);
                foreach(var potion in potions.Take(mode=="extra"?3:mode=="missing"?1:2))await PotionCmd.TryToProcure(potion,player);
            };
            var c=f.Start();var start=f.Read(c);
            var receipt=(GenericEventV7RewardChildApply)f.World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,start.DecisionId,"collect:0");
            Check(receipt.Value.Outcome is "accepted" or "uncertain","phial dispatched once");var read=f.Read(c);
            if(mode is "delay" or "fault" or "foreign") {
                Check(read.Status=="waiting","actual procurement callback awaits completion");
                if(mode=="foreign"){player.Gold++;read=f.Read(c);}else{if(mode=="fault")gate.SetException(new InvalidOperationException("procurement fault"));else gate.SetResult();read=f.Read(c);}
            }
            if(mode=="curse")read=f.Act(c,"collect:1");
            bool bad=mode is "fault" or "wrong_result" or "direct" or "extra" or "missing" or "capacity" or "foreign";
            Check(read.Status==(bad?"unsupported":"resolved"),"Phial Holster "+mode+" "+read.Status);
            if(!bad)Check(player.PotionSlots.Count==4&&player.PotionSlots.Count(p=>p is not null)==(mode=="full"?4:mode=="prevented"?0:2)&&f.World.Session.Read().ParentReconciled==1,"actual potion outcomes and exact capacity");
            PotionCmd.Prevent=false;PotionCmd.WrongResult=false;PotionCmd.DirectInsertion=false;PotionCmd.After=null;
        }
    }
}
