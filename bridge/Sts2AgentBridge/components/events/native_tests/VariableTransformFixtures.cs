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
    internal static MegaCrit.Sts2.Core.Nodes.Events.NAncientEventLayout AncientLayout(MegaCrit.Sts2.Core.Nodes.Rooms.NEventRoom room, MegaCrit.Sts2.Core.Models.EventModel model,int lines=3) {
        var layout=new MegaCrit.Sts2.Core.Nodes.Events.NAncientEventLayout();
        layout.OptionButtons.AddRange(room.Layout.OptionButtons);room.Layout=layout;
        layout.Setup((MegaCrit.Sts2.Core.Models.AncientEventModel)model,lines);return layout;
    }
    private static void OptionalEventTests()
    {
        foreach(int count in new[]{0,1,7,15}) {
            using var f=new RewardFixture("SEA_GLASS",0,15,15,manual:true,eventModel:new MegaCrit.Sts2.Core.Models.AncientEventModel());
            var layout=AncientLayout(f.Room,f.Model);
            for(int line=0;line<2;line++) {
                var p=f.Session.Read();Check(p.Status=="ready"&&p.Candidates.Count==1&&p.Candidates[0].RenderedText=="Continue dialogue","ancient dialogue exposed");
                Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","dialogue dispatched");
                Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome!="accepted","dialogue never retried");
                Check(f.Session.Read().ParentReconciled==line+1&&layout.Advances==line+1&&f.OptionCalls==0,"dialogue exact next line");
            }
            var c=f.Start();Check(c.Status=="child"&&c.Child!.ContractVersion=="card_add_v2","optional add version "+c.Status+" "+f.Adapter.LastDiagnostic+" "+c.Child?.ContractVersion);
            for(int i=0;i<count;i++)f.Act(c,"select:"+i);
            Check(f.Child(c) is CardSelectionV1Observation o&&o.LegalActions.Contains("confirm"),"optional add explicit confirm including max");
            f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult done&&done.SelectedCards.Count==count,"optional add resolved count");
            Check(f.Player.Deck.Cards.Count==3+count&&f.ConfirmCalls==1&&f.SelectCalls==count,"optional add exact deck");
            var p2=f.Session.Read();Check(p2.Phase=="proceed"&&p2.CompletedCardChildren==1,"ancient proceed after child");f.Session.Apply(p2.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","ancient map return");
        }
        using(var f=new RewardFixture("POST_PICKUP",0,15,15,manual:true,eventModel:new MegaCrit.Sts2.Core.Models.AncientEventModel())) {
            var layout=AncientLayout(f.Room,f.Model,1);var originalList=layout.Lines;
            f.AfterEffect=()=>layout.Setup((MegaCrit.Sts2.Core.Models.AncientEventModel)f.Model,3);
            var c=f.Start();f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult,"post-pickup child finishes");
            for(int i=0;i<2;i++) {
                var p=f.Session.Read();Check(p.Status=="ready"&&p.Phase=="choose_option"&&p.LegalActions.SequenceEqual(new[]{"choose:0"})&&p.CompletedCardChildren==1,"post-pickup dialogue before Proceed "+p.Status+" "+p.Phase+" "+p.CompletedCardChildren);
                Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","post-pickup dialogue input");
            }
            Check(ReferenceEquals(layout.Lines,originalList)&&layout.Advances==2,"same native dialogue list reused");
            var end=f.Session.Read();Check(end.Phase=="proceed"&&end.ParentReconciled==3,"post-pickup dialogue reconciles");f.Session.Apply(end.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","post-pickup map");
        }
        foreach(int domain in new[]{1,4,6,10})foreach(int count in new[]{0,1,Math.Min(6,domain)}.Distinct()) {
            using var f=new TransformFixture("CLAWS",6,domain,manual:true,minimum:0,eventModel:new MegaCrit.Sts2.Core.Models.AncientEventModel());
            AncientLayout(f.Room,f.Model,1);
            var c=f.Start();Check(c.Status=="child"&&c.Child!.ContractVersion=="card_transform_v3","optional transform version "+domain+" "+count+" "+c.Status+" "+f.Adapter.LastDiagnostic+" "+c.Child?.ContractVersion);
            for(int i=0;i<count;i++)f.Act(c,"select:"+i);
            if(count<6)f.Act(c,"preview");
            f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult done&&done.SelectedCards.Count==count,"optional transform resolved count");
            Check(f.BatchCount==1&&f.CompletedBatches==1&&f.Originals.Count==count&&f.Player.Deck.Cards.Count==domain+1,"optional transform exact native command");
            var p=f.Session.Read();f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","optional transform map return");
        }
        foreach(string failure in new[]{"no_command","duplicate_command","list_result","fault","wrong_request","deck_mutation","lost_preview","lost_confirm"}) {
            using var f=new TransformFixture("EMPTY_FAILURE",6,manual:true,minimum:0,batchSizes:failure=="no_command"?Array.Empty<int>():failure=="duplicate_command"?new[]{0,0}:new[]{0});
            if(failure=="list_result")f.Results=x=>x;
            if(failure=="fault")f.FaultCommand=true;
            if(failure=="wrong_request")f.RequestResult=_=>new[]{f.Cards[0]};
            if(failure=="deck_mutation")f.AfterEffect=()=>f.Cards[0].CurrentUpgradeLevel++;
            f.LostPreview=failure=="lost_preview";f.LostConfirm=failure=="lost_confirm";
            var c=f.Start();f.Act(c,"preview");if(!f.LostPreview)f.Act(c,"confirm");
            object result=f.Child(c);for(int i=0;i<257&&result is CardSelectionV1Observation {Status:"waiting"};i++)result=f.Child(c);
            Check(result is CardSelectionV1Observation {Status:"unsupported"},"empty transform fails closed "+failure);
            Check(f.PreviewCalls==1&&f.ConfirmCalls<2,"optional input never retried");
        }
        foreach(bool transform in new[]{false,true}) {
            if(transform) {
                using var f=new TransformFixture("EMPTY_DELAY",6,manual:true,minimum:0,delayedCompletion:true,delayedPreview:true);
                var c=f.Start();f.Act(c,"preview");Check(f.Child(c) is CardSelectionV1Observation {Status:"waiting"},"empty preview waits");f.AdvancePreview();f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation {Status:"waiting"},"empty transform waits chosen");f.CompletionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult,"empty transform late chosen");
            } else {
                using var f=new RewardFixture("EMPTY_DELAY",0,15,15,manual:true,delayedCompletion:true);var c=f.Start();f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation {Status:"waiting"},"empty add waits chosen");f.CompletionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult,"empty add late chosen");
            }
        }
        foreach(string mutation in new[]{"deferred","jump","line_domain","hitbox","hidden","disabled","overlay","lost"}) {
            using var f=new RewardFixture("ANCIENT",0,15,15,manual:true,eventModel:new MegaCrit.Sts2.Core.Models.AncientEventModel());
            var layout=AncientLayout(f.Room,f.Model);layout.Defer=true;
            var p=f.Session.Read();
            if(mutation=="hidden")layout.Hitbox.Visible=false;
            if(mutation=="disabled")layout.Hitbox.IsEnabled=false;
            if(mutation is "hidden" or "disabled") {Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome!="accepted"&&layout.Advances==0,"stale dialogue blocked");continue;}
            f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="waiting","dialogue pending");
            switch(mutation) {
                case "deferred":layout.Pending!();Check(f.Session.Read().Status=="ready"&&layout.Advances==1,"deferred dialogue reconciles");continue;
                case "jump":layout.Line=2;break;
                case "line_domain":layout.Lines[0]=new object();break;
                case "hitbox":layout.Bind("%DialogueHitbox",new MegaCrit.Sts2.Core.Nodes.Events.NAncientDialogueHitbox());break;
                case "overlay":f.Overlays.Screens.Add(new Godot.Control());break;
            }
            var end=f.Session.Read();for(int i=0;i<257&&end.Status=="waiting";i++)end=f.Session.Read();
            Check(end.Status=="unsupported"&&layout.Advances==1,"ancient ownership failure "+mutation);
        }
        foreach(var bounds in new[]{(-1,15,true),(0,16,true),(0,15,false),(1,15,true)}) {
            using var f=new RewardFixture("INVALID_OPTIONAL",bounds.Item1,bounds.Item2,20,manual:bounds.Item3);Check(f.Start().Status=="unsupported","scoped optional add limits");
        }
    }
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
        foreach(var invalid in new[]{(-1,3,true),(1,3,false),(4,3,true),(1,9,true)})
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
