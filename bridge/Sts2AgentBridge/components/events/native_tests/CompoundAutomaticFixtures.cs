using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Items.Native;
using Sts2AgentBridge.Successors.GenericEventV7;

namespace MegaCrit.Sts2.Core.Models.Cards
{
    public sealed class Greed:CardModel {public Greed(){Id.Entry="GREED";Type=5;}}
    public sealed class NeowsFury:CardModel {public NeowsFury(){Id.Entry="NEOWS_FURY";}}
}
namespace MegaCrit.Sts2.Core.Models.Relics
{
    public sealed class GoldenPearl:OfferRelicFixture {public GoldenPearl(){Id.Entry="GOLDEN_PEARL";}}
    public sealed class NutritiousOyster:OfferRelicFixture {public NutritiousOyster(){Id.Entry="NUTRITIOUS_OYSTER";}}
    public sealed class SilkenTress:OfferRelicFixture {public SilkenTress(){Id.Entry="SILKEN_TRESS";}}
    public sealed class ArcaneScroll:OfferRelicFixture {public ArcaneScroll(){Id.Entry="ARCANE_SCROLL";}}
    public sealed class NeowsTorment:OfferRelicFixture {public NeowsTorment(){Id.Entry="NEOWS_TORMENT";}}
    public sealed class CursedPearl:OfferRelicFixture {public CursedPearl(){Id.Entry="CURSED_PEARL";}}
    public sealed class NeowsTalisman:OfferRelicFixture {public NeowsTalisman(){Id.Entry="NEOWS_TALISMAN";}}
}
internal static partial class Program
{
    private static void CompoundAutomaticCases()
    {
        foreach(string kind in new[]{"gold","hp","lose_gold","rare","empty_rare","egg_generation","foreign_generation_upgrade","fury","greed","upgrade","dragon_fruit","nested","curse","delay","fault","wrong_add","extra_add","wrong_upgrade","foreign_gold"}) {
            using var f=new CompoundRewardFixture(tail:kind=="curse"?"curse":null);
            var player=f.World.Player;player.Gold=20;player.Creature.CurrentHp=50;
            var gate=new TaskCompletionSource();
            OfferRelicFixture relic=kind switch {"hp"=>new NutritiousOyster(),"lose_gold"=>new SilkenTress(),"rare" or "empty_rare" or "egg_generation" or "foreign_generation_upgrade"=>new ArcaneScroll(),
                "fury"=>new NeowsTorment(),"upgrade" or "wrong_upgrade"=>new NeowsTalisman(),"gold" or "dragon_fruit"=>new GoldenPearl(),_=>new CursedPearl()};
            Check(!PinnedAutomaticRelicEffects.Supports(relic),"compound support does not broaden legacy automatic pickups");
            var target=(RelicReward)(kind=="nested"?f.Child:f.Root).Rewards[0];target.Relic=relic;
            var basic=f.World.Cards[0];basic.Rarity="Basic";basic.Tags=new[]{"Strike"};basic.IsUpgradable=true;
            var untouched=f.World.Cards[1];untouched.IsUpgradable=true;
            var fruit=new DragonFruit{Owner=player};fruit.Id.Entry="DRAGON_FRUIT";
            if(kind=="dragon_fruit")player.Relics.Add(fruit);
            if(kind is "delay" or "fault")CardPileCmd.AfterAdded=_=>gate.Task;
            relic.Handler=async()=>{
                if(relic is NeowsTalisman){(kind=="wrong_upgrade"?untouched:basic).UpgradeInternal();return;}
                if(relic is NutritiousOyster){player.Creature.SetMaxHpInternal(player.Creature.MaxHp+11);player.Creature.SetCurrentHpInternal(player.Creature.CurrentHp+11);return;}
                if(relic is SilkenTress){player.Gold=0;return;}
                if(relic is GoldenPearl){player.Gold+=150;if(kind=="dragon_fruit")await fruit.AfterGoldGained(player);return;}
                if(kind=="empty_rare")return;
                CardModel card=relic is ArcaneScroll?new CardModel{Rarity="Rare"}:relic is NeowsTorment?new NeowsFury():new Greed();
                if(kind=="wrong_add")card=new Injury();
                card.Owner=player;if(card.Id.Entry.Length==0)card.Id.Entry="NATIVE_RARE";
                if(kind is "egg_generation" or "foreign_generation_upgrade") {
                    // CardFactory's TryModifyCardRewardOptions runs the Egg on
                    // the generated model before the actual Add call begins.
                    card.IsUpgradable=true;(kind=="egg_generation"?card:untouched).UpgradeInternal();
                }
                await CardPileCmd.Add(card,PileType.Deck);
                if(kind=="extra_add")await CardPileCmd.Add(new Greed{Owner=player},PileType.Deck);
                if(relic is CursedPearl)player.Gold+=333;
                if(kind=="foreign_gold")await gate.Task;
            };
            var c=f.Start();var read=f.Read(c);
            if(kind=="nested"){f.Act(c,"collect:0");read=f.Read(c);}
            var receipt=(GenericEventV7RewardChildApply)f.World.Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,read.DecisionId,"collect:0");
            Check(receipt.Value.Outcome is "accepted" or "uncertain","automatic native pickup dispatched once "+kind);read=f.Read(c);
            if(kind is "delay" or "fault") {
                Check(read.Status=="waiting"&&f.World.Session.Read().ParentReconciled==0,"native addition callback remains pending");
                if(kind=="fault")gate.SetException(new InvalidOperationException("pickup add fault"));else gate.SetResult();read=f.Read(c);
            }
            if(kind is "wrong_add" or "extra_add" or "wrong_upgrade" or "fault" or "foreign_generation_upgrade") {Check(read.Status=="unsupported","automatic pickup failure stops: "+kind);continue;}
            if(kind is "nested" or "curse")read=f.Act(c,"collect:1");
            if(kind=="foreign_gold") {
                Check(read.Status=="waiting","parent native callback still pending");
                player.Gold++;Check(f.Read(c).Status=="unsupported","foreign mutation cannot enter pending pickup certificate");continue;
            }
            Check(read.Status=="resolved"&&f.World.Session.Read().ParentReconciled==1,"automatic pickup completes one compound event: "+kind+" "+read.Status);
            if(kind=="gold")Check(player.Gold==170,"exact observed native gain");
            if(kind=="lose_gold")Check(player.Gold==0,"native gold loss certified");
            if(kind=="hp")Check(player.Creature.CurrentHp==61,"native maximum-health heal certified");
            if(kind=="upgrade")Check(basic.CurrentUpgradeLevel==1&&untouched.CurrentUpgradeLevel==0,"only actual basic tagged target upgraded");
            if(kind=="egg_generation")Check(player.Deck.Cards.Last().Id.Entry=="NATIVE_RARE"&&player.Deck.Cards.Last().CurrentUpgradeLevel==1&&untouched.CurrentUpgradeLevel==0,"actual pre-add Egg result frozen at Add input");
        }
    }
}
