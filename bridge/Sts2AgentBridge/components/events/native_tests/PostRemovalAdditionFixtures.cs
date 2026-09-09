using System;
using System.Linq;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV7;

internal static partial class Program
{
    internal static CardModel AppendAfterRemoval(RemovalFixture f,string key="ULTIMATE_STRIKE")
    {
        var added=new CardModel{Owner=f.Player};added.Id.Entry=key;
        f.AfterEffect=()=>f.Player.Deck.Cards.Add(added);
        return added;
    }
    private static void FinishRemoval(RemovalFixture f,GenericEventV7Observation child)
    {f.Act(child,"select:0");f.Act(child,"select:1");f.Act(child,"confirm");}
    private static bool RemovalUnsupported(RemovalFixture f,GenericEventV7Observation child)=>
        f.Child(child) is CardSelectionV1Observation {Status:"unsupported"};
    private static void PostRemovalAdditionTests()
    {
        // The session-wide clone registry includes legitimate outputs of earlier
        // transform children. Baseline membership must take precedence for them.
        foreach(bool baseline in new[]{true,false})
        using(var f=new RemovalFixture("PRIOR_TRANSFORM_IDENTITY",2,2,4)) {
            var extra=AppendAfterRemoval(f);
            var seen=(System.Collections.Generic.HashSet<object>)typeof(Sts2AgentBridge.Successors.GenericEventV7.Native.PinnedGenericEventV7NativeAdapter)
                .GetField("_previewClones",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!.GetValue(f.Adapter)!;
            seen.Add(baseline?f.Cards[2]:extra);
            var child=f.Start();FinishRemoval(f,child);
            Check(baseline ? f.Child(child) is CardSelectionV1ResolvedResult : RemovalUnsupported(f,child),
                "prior transform baseline allowed, nonbaseline clone grant rejected");
        }
        foreach(bool delayed in new[]{false,true})
        using(var f=new RemovalFixture("AMALGAMATOR_SHAPE",2,2,4,delayedCompletion:delayed))
        {
            var extra=AppendAfterRemoval(f);var child=f.Start();
            Check(child.Child!.ContractVersion=="card_remove_v2","removal contract explicitly versioned");
            FinishRemoval(f,child);
            if(delayed) {
                Check(f.Child(child) is CardSelectionV1Observation {Status:"waiting"},"grant does not finish pending Chosen");
                f.CompletionGate.SetResult();
            }
            Check(f.Child(child) is CardSelectionV1ResolvedResult r && r.SelectedCards.Count==2 &&
                r.ParentAddedCards is [{Key:"ULTIMATE_STRIKE",UpgradeLevel:0,Enchantment:null}],"separate public grant metadata");
            Check(f.Player.Deck.Cards.SequenceEqual(f.Cards.Skip(2).Append(extra)),"exact survivors plus appended grant");
            FinishAdditionParent(f.Session);
        }
        using(var f=new RemovalFixture("PRE_AND_POST",2,2,4)) {
            var before=AppendBeforeSelector(f.Room.Layout,f.Player);var after=AppendAfterRemoval(f);
            var child=f.Start();FinishRemoval(f,child);
            Check(f.Child(child) is CardSelectionV1ResolvedResult &&
                f.Player.Deck.Cards.SequenceEqual(f.Cards.Skip(2).Append(before).Append(after)),"distinct request baseline and parent grant");
        }
        foreach(string mutation in new[]{"missing_survivor","survivor_replace","survivor_enchant","selected_return","interleave","partial_remove","two_grants","foreign_owner","foreign_run","duplicate","overflow","fault"})
        using(var f=new RemovalFixture("INVALID_GRANT",2,2,4)) {
            var extra=AppendAfterRemoval(f);
            f.AfterEffect=()=>{
                f.Player.Deck.Cards.Add(extra);
                switch(mutation) {
                    case "missing_survivor":f.Player.Deck.Cards.Remove(f.Cards[2]);break;
                    case "survivor_replace":f.Player.Deck.Cards[0]=new CardModel{Owner=f.Player};break;
                    case "survivor_enchant":Fixture.ApplyEnchantment(f.Cards[2],1);break;
                    case "selected_return":f.Player.Deck.Cards[^1]=f.Cards[0];break;
                    case "interleave":f.Player.Deck.Cards.Remove(extra);f.Player.Deck.Cards.Insert(1,extra);break;
                    case "partial_remove":f.Player.Deck.Cards.Insert(0,f.Cards[0]);break;
                    case "two_grants":f.Player.Deck.Cards.Add(new CardModel{Owner=f.Player});break;
                    case "foreign_owner":extra.Owner=new Player();break;
                    case "foreign_run":extra.RunOverride=new MegaCrit.Sts2.Core.Runs.FixtureRunState();break;
                    case "duplicate":f.Player.Deck.Cards.Add(extra);break;
                    case "overflow":for(int i=0;i<512;i++)f.Player.Deck.Cards.Add(new CardModel{Owner=f.Player});break;
                    case "fault":f.FaultCallback=true;break;
                }
            };
            var child=f.Start();FinishRemoval(f,child);
            Check(RemovalUnsupported(f,child),"invalid removal/grant rejected: "+mutation);
        }
        foreach(string mutation in new[]{"remove","replace","key","upgrade","enchant","owner","run","survivor_order"})
        using(var f=new RemovalFixture("PENDING_GRANT_CHANGE",2,2,4,delayedCompletion:true)) {
            var extra=AppendAfterRemoval(f);var child=f.Start();FinishRemoval(f,child);
            Check(f.Child(child) is CardSelectionV1Observation {Status:"waiting"},"first appended snapshot retained");
            switch(mutation) {
                case "remove":f.Player.Deck.Cards.Remove(extra);break;
                case "replace":var replacement=new CardModel{Owner=f.Player};replacement.Id.Entry=extra.Id.Entry;f.Player.Deck.Cards[^1]=replacement;break;
                case "key":extra.Id.Entry="CHANGED";break;
                case "upgrade":extra.CurrentUpgradeLevel++;break;
                case "enchant":Fixture.ApplyEnchantment(extra,1);break;
                case "owner":extra.Owner=new Player();break;
                case "run":extra.RunOverride=new MegaCrit.Sts2.Core.Runs.FixtureRunState();break;
                case "survivor_order":f.Player.Deck.Cards.Reverse(0,2);break;
            }
            f.CompletionGate.SetResult();Check(RemovalUnsupported(f,child),"pending suffix invariant: "+mutation);
        }
        foreach(bool preview in new[]{false,true})
        using(var f=new RemovalFixture("EARLY_GRANT",2,2,4)) {
            var child=f.Start();if(preview){f.Act(child,"select:0");f.Act(child,"select:1");}
            f.Player.Deck.Cards.Add(new CardModel{Owner=f.Player});
            Check(RemovalUnsupported(f,child)&&f.ConfirmCalls==0,"grant forbidden before commit");
        }
    }
}
