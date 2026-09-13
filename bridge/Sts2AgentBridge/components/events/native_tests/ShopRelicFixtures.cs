using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

internal static partial class Program
{
    private class PassiveShopRelic:RelicModel {}
    private class SelectorShopRelic:RelicModel {public override Task AfterObtained()=>Task.CompletedTask;}
    private sealed class InheritedSelectorShopRelic:SelectorShopRelic {}
    private static void ShopRelicCases()
    {
        Check(ShopRelicRules.TryEffect(new PassiveShopRelic(),out int gain)&&gain==0,"inherited base callback supported");
        Check(!ShopRelicRules.TryEffect(new SelectorShopRelic(),out _),"custom pickup callback excluded");
        Check(!ShopRelicRules.TryEffect(new InheritedSelectorShopRelic(),out _),"inherited custom callback excluded");
        var belt=new PotionBelt();belt.DynamicVars["PotionSlots"].IntValue=2;
        Check(ShopRelicRules.TryEffect(belt,out gain)&&gain==2,"exact Potion Belt capacity supported");
        belt.DynamicVars["PotionSlots"].IntValue=3;
        Check(!ShopRelicRules.TryEffect(belt,out _),"changed capacity excluded");
        var player=new Player();var foreign=new Player();var entry=new MerchantRelicEntry();entry.SetPlayer(player);
        Check(ShopRelicRules.Ready(entry,player),"unowned local relic ready");
        Check(ShopRelicRules.Pending(entry,player),"unowned relic pending");
        entry.Model.Owner=player;
        Check(!ShopRelicRules.Ready(entry,player),"owned offer cannot dispatch");
        Check(ShopRelicRules.Pending(entry,player),"local appended relic pending");
        entry.Model.Owner=foreign;
        Check(!ShopRelicRules.Ready(entry,player)&&!ShopRelicRules.Pending(entry,player),"foreign model rejected");
        entry.Model=null!;
        Check(ShopRelicRules.Pending(entry,player)&&!ShopRelicRules.Ready(entry,player),"cleared local entry pending only");
        entry.SetPlayer(foreign);
        Check(!ShopRelicRules.Pending(entry,player),"cleared stock retains entry owner check");
        entry.Model=new RelicModel();entry.SetPlayer(player);entry.IsStocked=false;
        Check(!ShopRelicRules.Ready(entry,player),"unstocked relic cannot dispatch");
    }
}
