using System;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV7;

internal static partial class Program
{
    private static void VariableTransformTests()
    {
        foreach(string name in new[]{"FIRST_TRANSFORM","ANOTHER_TRANSFORM","HELD_OUT_TRANSFORM"})
        foreach(var counts in new[]{(1,3,1),(1,3,2),(1,3,3),(2,4,2),(2,4,3),(2,4,4),(1,8,7),(1,8,8)})
        {
            var (min,max,chosen)=counts;
            using var f=new TransformFixture(name,max,manual:true,minimum:min,substitute:true);
            var c=f.Start();Check(c.Status=="child","variable admission");
            foreach(int i in Enumerable.Range(0,chosen).Reverse())f.Act(c,"select:"+i);
            if(chosen<max)f.Act(c,"preview");
            f.Act(c,"confirm");
            Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid,"variable exact effect");
            Check(f.Originals.Count==chosen&&f.Selected.All(o=>f.Originals.Contains(o))&&f.PreviewCalls==(chosen<max?1:0)&&f.ConfirmCalls==1,"variable exact native actions");
            var p=f.Session.Read();Check(p.CompletedCardChildren==1&&p.Phase=="proceed","variable cumulative");
            f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","variable proceed");
        }
        foreach(bool partial in new[]{false,true})
        {
            using var f=new TransformFixture("PREVIEW_DELAY",4,manual:true,minimum:1,delayedPreview:!partial,partialPreview:partial);
            var c=f.Start();f.Act(c,"select:2");f.Act(c,"select:0");f.Act(c,"select:1");
            f.BeforePreview=()=>{f.RootConfirmButton.InstanceValid=false;f.RootConfirmButton.Visible=false;f.RootConfirmButton.IsEnabled=false;};
            f.Act(c,"preview");Check(f.HasPendingPreview,"preview pending fixture");
            Check(f.Child(c) is CardSelectionV1Observation wait&&wait.Status=="waiting","partial preview waits exact count");
            f.AdvancePreview();f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid,"retired root receipt accepted");
        }
        using(var f=new TransformFixture("EARLY",3,manual:true,minimum:1))
        {f.UnexpectedEarlyPreview=true;var c=f.Start();f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported"&&f.ConfirmCalls==0&&f.PreviewCalls==0,"unrequested early preview rejected");}
        using(var f=new TransformFixture("LATER_EARLY",3,manual:true,minimum:1))
        {var c=f.Start();f.Act(c,"select:0");_=f.Child(c);f.RootConfirmButton.ForceClick();Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported"&&f.ConfirmCalls==0,"foreign early preview after reconciled selection rejected");}
        using(var f=new TransformFixture("MINIMUM",4,manual:true,minimum:2))
        {
            var c=f.Start();Check(!f.RootConfirmButton.Visible&&!f.RootConfirmButton.IsEnabled,"hidden root admitted");f.Act(c,"select:0");
            var o=(CardSelectionV1Observation)f.Child(c);Check(!o.LegalActions.Contains("preview"),"preview below minimum unavailable");
            f.Act(c,"select:1");f.RootConfirmButton.IsEnabled=false;o=(CardSelectionV1Observation)f.Child(c);
            Check(o.Status=="ready"&&!o.LegalActions.Contains("preview")&&f.PreviewCalls==0,"disabled preview not dispatched");
            f.RootConfirmButton.IsEnabled=true;f.Act(c,"preview");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult,"re-enabled native preview");
        }
        foreach(string mutation in new[]{"root_replaced","root_invalid","root_hidden","root_disabled","foreign","duplicate","holder","card","model","extra","final","selection"})
        {
            using var f=new TransformFixture(mutation,4,manual:true,minimum:1,partialPreview:mutation=="foreign");
            var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");
            var decision=(CardSelectionV1Observation)f.Child(c);
            if(mutation.StartsWith("root_",StringComparison.Ordinal))
            {
                switch(mutation){case "root_replaced":f.Screen.Bind("Confirm",new NConfirmButton());break;case "root_invalid":f.RootConfirmButton.InstanceValid=false;break;case "root_hidden":f.RootConfirmButton.Visible=false;break;case "root_disabled":f.RootConfirmButton.IsEnabled=false;break;}
                _=f.Session.ApplyCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,decision.DecisionId,"preview");
                Check(f.PreviewCalls==0&&f.ConfirmCalls==0,"stale root rejected "+mutation);continue;
            }
            if(mutation=="selection")
            {
                ((ShaderMaterial)f.Grid.CurrentlyDisplayedCardHolders[2].CardNode.CardHighlight.Material!).Width=BitConverter.Int32BitsToSingle(Sts2AgentBridge.Successors.CardSelectionV1.Native.CardSelectionV1NativeRules.SelectedWidthBits);
                _=f.Session.ApplyCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,decision.DecisionId,"preview");
                Check(f.PreviewCalls==0,"unexpected selection rejected");continue;
            }
            f.Act(c,"preview");if(mutation!="foreign")_=f.Child(c);
            var holder=(NPreviewCardHolder)f.Before.Children[0];
            switch(mutation)
            {
                case "foreign":holder.CardNode.Model=f.Cards[2];break;
                case "duplicate":f.Before.Children[1]=new NPreviewCardHolder{CardNode=holder.CardNode};break;
                case "holder":f.Before.Children[0]=new NPreviewCardHolder{CardNode=holder.CardNode};break;
                case "card":holder.CardNode=new NCard{Model=f.Cards[0]};break;
                case "model":holder.CardNode.Model=f.Cards[2];break;
                case "extra":f.Before.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=f.Cards[2]}});break;
                case "final":f.Preview.Bind("Confirm",new NConfirmButton());break;
            }
            Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported"&&f.ConfirmCalls==0,"variable preview mutation "+mutation);
        }
        foreach(var invalid in new[]{(0,3,true),(1,3,false),(4,3,true),(1,9,true)})
        {using var f=new TransformFixture("INVALID",invalid.Item2,manual:invalid.Item3,minimum:invalid.Item1);Check(f.Start().Status=="unsupported","variable invalid admission");}
        foreach(bool final in new[]{false,true})
        {
            using var f=new TransformFixture("LOST",3,manual:true,minimum:1);var c=f.Start();f.Act(c,"select:0");
            f.LostPreview=!final;f.LostConfirm=final;f.Act(c,"preview");if(final)f.Act(c,"confirm");
            object? last=null;for(int i=0;i<257;i++){last=f.Child(c);if(last is CardSelectionV1Observation o&&o.Status=="unsupported")break;}
            Check(last is CardSelectionV1Observation stopped&&stopped.Status=="unsupported"&&f.PreviewCalls==1&&f.ConfirmCalls==(final?1:0),"lost variable dispatch no retry");
        }
        using(var f=new TransformFixture("LATE_TASK",3,manual:true,minimum:1,delayedCompletion:true))
        {var c=f.Start();f.Act(c,"select:0");f.Act(c,"preview");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="waiting","variable effect waits chosen");f.CompletionGate.SetException(new InvalidOperationException("late"));Check(f.Child(c) is CardSelectionV1Observation stopped&&stopped.Status=="unsupported","variable late task fault");}
    }
}
