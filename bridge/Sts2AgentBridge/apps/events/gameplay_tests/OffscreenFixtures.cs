using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV10;

internal sealed class OffscreenGeometry
{
    internal readonly NCardGrid Grid;
    internal readonly NGridCardHolder[] Holders;
    internal int DispatchCount;
    internal readonly List<int> DispatchedSlots=new();
    private OffscreenGeometry(NCardGrid grid)
    { Grid=grid; Holders=grid.CurrentlyDisplayedCardHolders.ToArray(); }
    internal static OffscreenGeometry Configure(NDeckTransformSelectScreen screen,string mode="direct")
    {
        var value=new OffscreenGeometry(screen.GetNodeOrNull<NCardGrid>("%CardGrid")!);
        // Selection is tested with no clipping parent.
        value.Grid.ClipContents=false;
        for(int i=0;i<value.Holders.Length;i++)
        {
            int slot=i;
            value.Holders[i].FixtureBeforeGuiInput=()=>{value.DispatchCount++;value.DispatchedSlots.Add(slot);};
        }
        return value;
    }
    internal void Mutate(string mode)
    {
        var holder=Holders[15];
        switch(mode)
        {
            case "disabled":holder.Hitbox.IsEnabled=false;break;
            case "holder":Grid.CurrentlyDisplayedCardHolders[15]=new NGridCardHolder{CardModel=holder.CardModel,CardNode=holder.CardNode,Hitbox=holder.Hitbox};break;
            case "model":holder.CardModel=Holders[0].CardModel;break;
            default:throw new InvalidOperationException("Unknown target mutation.");
        }
    }
}

internal static class OffscreenTests
{
    private static int _checks;
    private static void Check(bool condition,string label){_checks++;if(!condition)throw new InvalidOperationException(label);}
    private static void Wrap(Action<OffscreenGeometry> configure)
    {
        var factory=NDeckTransformSelectScreen.Factory!;
        NDeckTransformSelectScreen.Factory=(cards,creator,prefs)=>{var screen=factory(cards,creator,prefs);configure(OffscreenGeometry.Configure(screen));return screen;};
    }
    internal static int Main()
    {
        try
        {
            Success(20);Success(16);Missing();Disabled();Reassigned();Deferred();
            Console.WriteLine("{\"status\":\"passed\",\"suite\":\"generic_event_v10_card16\",\"check_count\":"+_checks+"}");return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
    private static void Success(int domain)
    {
        using var f=new global::Program.TransformFixture("CARD16",1,domain:domain);
        OffscreenGeometry target=null!;Wrap(x=>target=x);
        var child=f.Start();Check(child.Status=="child","card16 admitted without clip");
        var observation=(CardSelectionV1Observation)f.Child(child);
        Check(observation.LegalActions.SequenceEqual(new[]{"select:15"}),"only card16 offered");
        f.Act(child,"select:15");
        Check(target.DispatchCount==1&&target.DispatchedSlots.SequenceEqual(new[]{15}),"actual native input on holder16");
        Check(f.Preview.Visible&&f.Selected.Count==1&&ReferenceEquals(f.Selected[0],f.Cards[15]),"card16 opens preview");
        Check(f.Before.Children.Count==1&&f.Before.Children[0] is NPreviewCardHolder holder&&ReferenceEquals(holder.CardNode.Model,f.Cards[15]),"preview exact card16 original");
        f.Act(child,"confirm");
        Check(f.Child(child) is CardSelectionV1ResolvedResult&&f.CompletionValid&&ReferenceEquals(f.Originals.Single(),f.Cards[15]),"card16 exact transformation");
        var parent=f.Session.Read();Check(parent.CompletedCardChildren==1&&parent.Phase=="proceed","child reconciled");
        f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete"&&f.SelectCalls==1&&f.ConfirmCalls==1,"map continuation");
    }
    private static void Missing()
    {
        using var f=new global::Program.TransformFixture("MISSING",1,domain:15);OffscreenGeometry target=null!;Wrap(x=>target=x);
        var parent=f.Start();Check(parent.Status!="child"&&f.SelectCalls==0&&target.DispatchCount==0,"missing card16 does not click another");
    }
    private static void Disabled()
    {
        using var f=new global::Program.TransformFixture("DISABLED",1,domain:20);OffscreenGeometry target=null!;Wrap(x=>{target=x;x.Mutate("disabled");});
        var parent=f.Start();Check(parent.Status!="child"&&f.SelectCalls==0&&target.DispatchCount==0,"disabled card16 does not click another");
    }
    private static void Reassigned()
    {
        using var f=new global::Program.TransformFixture("REASSIGNED",1,domain:20);OffscreenGeometry target=null!;Wrap(x=>target=x);
        var child=f.Start();var observation=(CardSelectionV1Observation)f.Child(child);target.Mutate("holder");
        f.Session.ApplyCardChild(child.Child!.ParentDecisionId,child.Child.ParentActionId,child.Child.Ordinal,observation.DecisionId,"select:15");
        Check(f.SelectCalls==0&&target.DispatchCount==0,"replaced target not clicked");
    }
    private static void Deferred()
    {
        using var f=new global::Program.TransformFixture("DEFERRED",1,domain:20);OffscreenGeometry target=null!;Action? pending=null;
        Wrap(x=>{target=x;x.Holders[15].FixtureGuiInputDispatch=action=>pending=action;});
        var child=f.Start();f.Act(child,"select:15");Check(pending is not null&&target.DispatchedSlots.SequenceEqual(new[]{15}),"one deferred input to card16");
        target.Mutate("model");try{pending!();}catch(InvalidOperationException error)when(error.Message=="Sequence contains no matching element"){}
        Check(f.Child(child) is CardSelectionV1Observation{Status:"unsupported"}&&f.ConfirmCalls==0,"wrong original not confirmed");
    }
}
