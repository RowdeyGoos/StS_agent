using System;
using System.Linq;
using System.Text.Json;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Cards.Combat;

internal sealed class HandFixture
{
    internal readonly NRun Run=new();
    internal readonly Player Player=new();
    internal readonly NPlayerHand Hand=new();
    internal readonly CardModel[] Cards;
    internal readonly CombatCardChoiceService Service;
    internal HandFixture(int min=1,int max=2,bool upgrade=false)
    {
        Run.CombatRoom=NCombatRoom.Instance=new();Run.CombatRoom.Ui.Hand=Hand;ActiveScreenContext.Instance=new();
        NRun.Instance=Run; NOverlayStack.Instance=Run.GlobalUi.Overlays; NPlayerHand.Instance=Hand;
        CombatManager.Instance=new();CombatManager.Instance.State.Players.Add(Player);CardSelectCmd.Selector=null;
        Cards=Enumerable.Range(0,3).Select(i=>new CardModel{Owner=Player,Id=new ModelId{Entry="STRIKE"}}).ToArray();
        Player.Piles[PileType.Hand]=new(){Type=PileType.Hand,Cards=Cards.ToList()};
        Hand.Init(Cards,new CardSelectorPrefs{MinSelect=min,MaxSelect=max},upgrade);
        Service=new(PinnedCombatCardChoiceAdapter.TryCreate,new string('a',32));
    }
    internal JsonElement Read()=>CombatOfferFixture.Parse(Service.Read(4));
    internal ChoiceReply Act(string action)=>Service.Apply(Read().GetProperty("decision_id").GetString()!,action,4);
}
internal static class CombatHandFixtures
{
    internal static void Run(Action<bool,string> check)
    {
        foreach(bool upgrade in new[]{false,true}) {
            var f=new HandFixture(max:upgrade?1:2,upgrade:upgrade);
            check(f.Read().GetProperty("pile").GetString()=="hand","hand selection advertised");
            check(!f.Act("select:0").Terminal && f.Read().GetProperty("selected_slots")[0].GetInt32()==0,"native holder transfer reconciled");
            check(!f.Act("deselect:0").Terminal && f.Read().GetProperty("selected_slots").GetArrayLength()==0,"recreated hand holder bound after deselect");
            f.Act("select:2");f.Read();f.Act("confirm");
            var result=f.Read();check(result.GetProperty("status").GetString()=="complete"&&result.GetProperty("reconciled").GetInt32()==4&&result.GetProperty("selected_slots")[0].GetInt32()==2,"exact hand task and close verified");
        }
        var replaced=new HandFixture(); replaced.Act("select:0");
        replaced.Hand.Selected.Holders[0].CardNode=new NCard{Model=replaced.Cards[0]};
        check(replaced.Service.Read(4).Terminal,"same-model card-node substitution during transfer rejected");
        var zero=new HandFixture(min:0);zero.Act("confirm");check(zero.Read().GetProperty("status").GetString()=="complete","optional empty hand result");
        foreach(var change in new Action<HandFixture>[] {
            f=>ActiveScreenContext.Instance.Blocker=new object(), f=>f.Run.CombatRoom=new(), f=>f.Hand.ReplaceTask(), f=>f.Cards[0].Owner=new Player(), f=>f.Cards[0].CurrentUpgradeLevel++,
            f=>f.Run.GlobalUi.MapScreen.IsOpen=true, f=>f.Hand.ActiveHolders[0]=new NHandCardHolder{CardNode=new NCard{Model=f.Cards[0]}},
            f=>f.Hand.ActiveHolders[0].CardNode=new NCard{Model=f.Cards[0]}, f=>f.Hand.PeekButton.IsPeeking=true,
            f=>f.Hand.Finish(new[]{f.Cards[0]}) }) {
            var f=new HandFixture();string id=f.Read().GetProperty("decision_id").GetString()!;var holders=f.Hand.ActiveHolders.ToArray();change(f);
            check(f.Service.Apply(id,"select:0",4).Terminal&&holders.Sum(h=>h.Calls)==0,"changed hand context rejected without input");
        }
        foreach(int version in new[]{1,2,3}) {var f=new HandFixture();check(f.Service.Read(version).Terminal,"old choice protocol retains hand exclusion");}
        NPlayerHand.Instance=null;
    }
}
