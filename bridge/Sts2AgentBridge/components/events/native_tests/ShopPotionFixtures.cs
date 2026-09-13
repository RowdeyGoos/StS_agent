using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

internal static partial class Program
{
    private static void ShopPotionOwnershipCases()
    {
        var player=new Player();var foreign=new Player();
        var entry=new MerchantPotionEntry();entry.SetPlayer(player);
        Check(ShopPotionOwnership.Ready(entry,player),"unowned local potion offer");
        Check(ShopPotionOwnership.Pending(entry,player),"unowned pending offer");
        entry.Model!.Owner=foreign;
        Check(!ShopPotionOwnership.Ready(entry,player),"foreign-owned offer rejected before dispatch");
        Check(!ShopPotionOwnership.Pending(entry,player),"foreign owner rejected during procurement");
        entry.Model.Owner=player;
        Check(!ShopPotionOwnership.Ready(entry,player),"already-owned local potion cannot be purchased");
        Check(ShopPotionOwnership.Pending(entry,player),"procured exact local owner may precede debit");
        entry.Model.Owner=null;entry.SetPlayer(foreign);
        Check(!ShopPotionOwnership.Ready(entry,player),"foreign merchant entry rejected before dispatch");
        Check(!ShopPotionOwnership.Pending(entry,player),"changed merchant owner rejected while pending");
        entry.Model=null;
        Check(!ShopPotionOwnership.Pending(entry,player),"cleared stock cannot hide foreign entry owner");
        entry.SetPlayer(player);
        Check(ShopPotionOwnership.Pending(entry,player),"cleared local entry allowed for effect verification");
        Check(!ShopPotionOwnership.Ready(entry,player),"cleared entry cannot advertise purchase");
        entry.Model=new PotionModel();entry.IsStocked=false;
        Check(!ShopPotionOwnership.Ready(entry,player),"unstocked entry cannot advertise purchase");
        entry.SetPlayer(null!);
        Check(!ShopPotionOwnership.Pending(entry,player),"missing entry owner rejected");
    }
}
