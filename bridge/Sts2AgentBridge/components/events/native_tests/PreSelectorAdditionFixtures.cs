using System;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV7;

internal static partial class Program
{
    internal static CardModel AppendBeforeSelector(NEventLayout layout,Player player,string key="DECAY",Func<Task>? before=null)
    {
        var added=new CardModel {Owner=player,IsUpgradable=false,IsTransformable=false,Type=6};
        added.Id.Entry=key;
        var option=layout.OptionButtons[0].Option;var callback=option.Callback;
        option.Callback=async()=>{
            if(before is not null)await before();
            player.Deck.Cards.Add(added);
            await callback();
        };
        return added;
    }
    private static void FinishAdditionParent(GenericEventV7Session session)
    {
        var p=session.Read();Check(p.Phase=="proceed"&&p.CompletedCardChildren==1,"addition child completion retained");
        Check(session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","addition Proceed");
        Check(session.Read() is {Status:"complete",ParentReconciled:2,Effects:"unverified"},"addition map without parent effect claim");
    }
    private static void PreSelectorAdditionTests()
    {
        foreach(bool enchant in new[]{false,true})
        using(var f=new Fixture(enchant?"GRAVE_CONFRONT":"PRE_UPGRADE",enchant:enchant)) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player);
            var c=f.Start();Check(c.Status=="child","pre-addition selector admitted");f.Finish(c);
            Check(f.Player.Deck.Cards.Last()==extra&&extra.CurrentUpgradeLevel==0&&extra.Enchantment is null,"added card retained untouched");
            Check(f.Cards[0].CurrentUpgradeLevel==(enchant?0:1)&&(!enchant||f.Cards[0].Enchantment?.Amount==1),"selected-only child effect");
            FinishAdditionParent(f.Session);
        }
        using(var f=new Fixture("SELECT_ADDED_CARD")) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player,"ADDED_ATTACK");extra.IsUpgradable=true;
            CardSelectCmd.Handler=async(player,prefs)=>await NDeckUpgradeSelectScreen.ShowScreen(
                player.Deck.Cards.Where(c=>c.IsUpgradable).ToArray(),prefs,player.RunState).CardsSelected();
            var c=f.Start();var child=c.Child!;
            foreach(var action in new[]{"select:2","confirm"}) {
                var o=(CardSelectionV1Observation)f.Session.ReadCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal).Value;
                Check(f.Session.ApplyCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal,o.DecisionId,action).Value is CardSelectionV1DispatchReceipt,"added card native input");
            }
            Check(f.Session.ReadCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal).Value is CardSelectionV1ResolvedResult&&extra.CurrentUpgradeLevel==1&&f.Cards.All(c=>c.CurrentUpgradeLevel==0),"new eligible original can be selected exactly");
            FinishAdditionParent(f.Session);
        }
        using(var f=new MultiUpgradeFixture("TRIAL_MERCHANT_INNOCENT",2,3)) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player,"SHAME");
            f.PreSelectorAdditions=new[]{extra};
            var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");f.Act(c,"confirm");
            Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid&&f.Player.Deck.Cards.Last()==extra,"pre-curse fixed-two upgrade");
            FinishAdditionParent(f.Session);
        }
        using(var f=new TransformFixture("TRIAL_NONDESCRIPT_INNOCENT",2,3)) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player,"DOUBT");
            f.PreSelectorAdditions=new[]{extra};
            var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");f.Act(c,"confirm");
            Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid&&f.Player.Deck.Cards.Contains(extra),"pre-curse fixed-two transform");
            FinishAdditionParent(f.Session);
        }
        using(var f=new RemovalFixture("PRE_REMOVE",1,1,3)) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player);
            var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");
            Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.Player.Deck.Cards.Contains(extra),"pre-addition removal baseline");
            FinishAdditionParent(f.Session);
        }
        using(var f=new RewardFixture("PRE_ADD",1,1,3)) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player);
            var c=f.Start();f.Act(c,"select:0");
            Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.Player.Deck.Cards.Contains(extra),"pre-addition add-grid baseline");
            FinishAdditionParent(f.Session);
        }
        using(var f=new Fixture("DELAYED_PRE_ADD",enchant:true)) {
            var gate=new TaskCompletionSource();AppendBeforeSelector(f.Room.Layout,f.Player,before:()=>gate.Task);
            Check(f.Start().Status=="waiting","pre-addition owned callback waits");gate.SetResult();
            var c=f.Session.Read();Check(c.Status=="child","delayed request establishes one baseline");f.Finish(c);
        }
        foreach(string mutation in new[]{"upgrade","enchant","remove","reorder","replace","prepend","duplicate","owner","run","overflow"})
        using(var f=new Fixture("BAD_PRE_ADD",enchant:true)) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player);
            var option=f.Room.Layout.OptionButtons[0].Option;var callback=option.Callback;
            option.Callback=()=>{
                switch(mutation) {
                    case "upgrade":f.Cards[0].CurrentUpgradeLevel++;break;
                    case "enchant":Fixture.ApplyEnchantment(f.Cards[0],1);break;
                    case "remove":f.Player.Deck.Cards.RemoveAt(0);break;
                    case "reorder":f.Player.Deck.Cards.Reverse();break;
                    case "replace":f.Player.Deck.Cards[0]=new CardModel {Owner=f.Player};break;
                    case "prepend":f.Player.Deck.Cards.Insert(0,new CardModel {Owner=f.Player});break;
                    case "duplicate":f.Player.Deck.Cards.Add(f.Cards[0]);break;
                    case "owner":extra.Owner=new Player();break;
                    case "run":extra.RunOverride=new MegaCrit.Sts2.Core.Runs.FixtureRunState();break;
                    case "overflow":for(int i=0;i<512;i++)f.Player.Deck.Cards.Add(new CardModel {Owner=f.Player});break;
                }
                return callback();
            };
            Check(f.Start().Status=="unsupported"&&f.SelectCalls==0,"pre-addition rejects "+mutation);
        }
        foreach(string stage in new[]{"creation","selection","effect","late_owner","late_replace"})
        using(var f=new Fixture("LATE_ADD",enchant:true)) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player);
            if(stage=="creation") {
                var handler=CardSelectCmd.EnchantHandler!;
                CardSelectCmd.EnchantHandler=(cards,model,amount,prefs)=>{f.Player.Deck.Cards.Add(new CardModel {Owner=f.Player});return handler(cards,model,amount,prefs);};
                Check(f.Start().Status=="unsupported"&&f.SelectCalls==0,"addition after request before creation rejected");
                continue;
            }
            var c=f.Start();
            if(stage=="selection") {
                f.Player.Deck.Cards.Add(new CardModel {Owner=f.Player});Check(IsUnsupported(f,c)&&f.SelectCalls==0,"baseline never refreshes after admission");
            } else {
                f.AfterEffect=()=>{
                    if(stage=="late_owner")extra.Owner=new Player();
                    else if(stage=="late_replace") {var copy=new CardModel {Owner=f.Player};copy.Id.Entry=extra.Id.Entry;f.Player.Deck.Cards[^1]=copy;}
                    else f.Player.Deck.Cards.Add(new CardModel {Owner=f.Player});
                };
                f.SelectConfirm(c);Check(IsUnsupported(f,c),"post-selector changes remain unsupported: "+stage);
            }
        }
        foreach(bool existingEnchantment in new[]{false,true})
        using(var f=new Fixture("APPENDED_ENCHANTMENT_CHANGED")) {
            var extra=AppendBeforeSelector(f.Room.Layout,f.Player);
            if(existingEnchantment)Fixture.ApplyEnchantment(extra,1);
            var c=f.Start();f.AfterEffect=()=>Fixture.ApplyEnchantment(extra,1);
            f.SelectConfirm(c);
            Check(IsUnsupported(f,c),"upgrade cannot alter appended enchantment identity: "+existingEnchantment);
        }
    }
}
