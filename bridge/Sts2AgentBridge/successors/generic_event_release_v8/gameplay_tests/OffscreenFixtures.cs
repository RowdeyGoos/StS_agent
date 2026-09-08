using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV7;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV8;

internal sealed class OffscreenGeometry
{
    internal readonly NCardGrid Grid;
    internal readonly Control Clip;
    internal readonly NGridCardHolder[] Holders;
    internal int DispatchCount;
    internal bool AllDispatchesBelow=true;
    internal readonly List<int> DispatchedSlots=new();
    private OffscreenGeometry(NCardGrid grid,Control clip,NGridCardHolder[] holders)
    {Grid=grid;Clip=clip;Holders=holders;}
    internal static OffscreenGeometry Configure(NDeckTransformSelectScreen screen,string mode="all_below")
    {
        var grid=screen.GetNodeOrNull<NCardGrid>("%CardGrid")!;
        var holders=grid.CurrentlyDisplayedCardHolders.ToArray();
        var scroll=grid.GetNodeOrNull<Control>("%ScrollContainer")!;
        grid.Size=new Vector2(1000,200);scroll.Position=new Vector2(0,0);
        grid.ClipContents=true;SetRect(grid,20,40,1000,200);
        var value=new OffscreenGeometry(grid,grid,holders);
        for(int i=0;i<holders.Length;i++)
        {
            int slot=i;var holder=holders[i];holder.FixtureParent=grid;holder.CardNode.FixtureParent=holder;holder.Hitbox.FixtureParent=holder;
            float y=mode=="all_below"?300+150*i:mode=="partial"?190:mode=="touching"?240:i==2?300:i==1?190:60;
            foreach(Control control in new Control[]{holder,holder.CardNode,holder.Hitbox})SetRect(control,30+100*(i%5),y,80,100);
            holder.FixtureBeforeGuiInput=()=>{value.DispatchCount++;value.DispatchedSlots.Add(slot);value.AllDispatchesBelow&=value.IsBelow(slot);};
        }
        if(mode=="missing_clip")grid.ClipContents=false;
        return value;
    }
    private static void SetRect(Control control,float x,float y,float width,float height)
    {control.FixtureRect=new Rect2(new Vector2(x,y),new Vector2(width,height));control.FixtureTransform=new Transform2D(new Vector2(1,0),new Vector2(0,1),new Vector2(x,y));}
    internal bool IsBelow(int slot)=>Clip.ClipContents&&new Control[]{Holders[slot],Holders[slot].CardNode,Holders[slot].Hitbox}.All(c=>
        c.GetGlobalRect().Position.Y>Clip.GetGlobalRect().Position.Y+Clip.GetGlobalRect().Size.Y);
    internal void Mutate(string mode,int slot=2)
    {
        var h=Holders[slot];var r=h.FixtureRect;
        switch(mode)
        {
            case "rectangle":h.FixtureRect=new Rect2(new Vector2(r.Position.X,r.Position.Y+1),r.Size);break;
            case "onscreen":h.FixtureRect=new Rect2(new Vector2(r.Position.X,60),r.Size);break;
            case "parent":h.FixtureParent=new Control{FixtureParent=Grid};break;
            case "clip":Clip.ClipContents=false;break;
            case "clip_rect":Clip.FixtureRect=new Rect2(Clip.FixtureRect.Position,new Vector2(1000,201));break;
            case "holder":Grid.CurrentlyDisplayedCardHolders[slot]=new NGridCardHolder{CardModel=h.CardModel,CardNode=h.CardNode,Hitbox=h.Hitbox};break;
            case "card":h.CardNode=new NCard{Model=h.CardModel};break;
            case "hitbox":h.Hitbox=new NClickableControl();break;
            case "model":h.CardModel=Holders[0].CardModel;break;
            case "canvas":h.FixtureCanvas=new Rid(2);break;
            case "zero_canvas":h.FixtureCanvas=new Rid(0);break;
            case "toplevel":h.FixtureTopLevel=true;break;
            case "rotation":h.FixtureTransform=new Transform2D(new Vector2(1,1),new Vector2(0,1),r.Position);break;
            case "reflection":h.FixtureTransform=new Transform2D(new Vector2(-1,0),new Vector2(0,1),r.Position);break;
            case "nan":h.FixtureRect=new Rect2(new Vector2(float.NaN,300),r.Size);break;
            case "zero":h.FixtureRect=new Rect2(r.Position,new Vector2(0,100));break;
            case "disabled":h.Hitbox.IsEnabled=false;break;
            case "invisible":h.Visible=false;break;
            case "missing":Grid.CurrentlyDisplayedCardHolders.RemoveAt(slot);break;
            case "duplicate":Grid.CurrentlyDisplayedCardHolders[slot]=Holders[0];break;
            case "scroll":Grid.GetNodeOrNull<Control>("%ScrollContainer")!.Position=new Vector2(0,-1);break;
            case "deep":Node parent=Grid;for(int i=0;i<33;i++)parent=new Control{FixtureParent=parent};h.FixtureParent=parent;break;
            case "cycle":h.FixtureParent=h;break;
            case "noncanvas":h.FixtureParent=new Node{FixtureParent=Grid};break;
            default:throw new InvalidOperationException("Unknown offscreen mutation.");
        }
    }
}

internal static class OffscreenTests
{
    private static int _checks;
    private static void Check(bool condition,string label){_checks++;if(!condition)throw new InvalidOperationException(label);}
    internal static int Main()
    {
        try
        {
            foreach(string name in new[]{"FIRST_TRANSFORM","ANOTHER_TRANSFORM","HELD_OUT_TRANSFORM"})Success(name);
            foreach(string mode in new[]{"missing_clip","partial","touching"})Admission(mode,null);
            foreach(string mutation in new[]{"canvas","zero_canvas","toplevel","rotation","reflection","nan","zero","missing","duplicate","deep","cycle","noncanvas","invisible"})Admission("probe",mutation);
            foreach(string mutation in new[]{"rectangle","onscreen","parent","clip","clip_rect","holder","card","hitbox","model","canvas","toplevel","rotation","scroll","disabled","invisible"})Race(mutation);
            DeferredReassignment("model");DeferredReassignment("rectangle");Variable();NoFallback();
            Console.WriteLine("{\"status\":\"passed\",\"suite\":\"generic_event_v8_offscreen\",\"check_count\":"+_checks+"}");return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
    private static void Wrap(string mode,Action<OffscreenGeometry> configured)
    {
        var original=NDeckTransformSelectScreen.Factory!;
        NDeckTransformSelectScreen.Factory=(cards,factory,prefs)=>{var screen=original(cards,factory,prefs);configured(OffscreenGeometry.Configure(screen,mode));return screen;};
    }
    private static void Success(string name)
    {
        using var f=new global::Program.TransformFixture(name,1,domain:20);OffscreenGeometry g=null!;Wrap("probe",x=>g=x);
        var child=f.Start();Check(child.Status=="child","probe admitted");
        var observation=(CardSelectionV1Observation)f.Child(child);
        Check(observation.LegalActions.SequenceEqual(new[]{"select:2"}),"only wholly below candidate legal");
        Check(g.Grid.Size.Y==200&&g.Grid.CurrentlyDisplayedCardHolders.Count==20,"allocated oversized grid");
        f.Act(child,"select:2");Check(g.DispatchCount==1&&g.AllDispatchesBelow&&g.DispatchedSlots.SequenceEqual(new[]{2}),"actual GuiInput below clip");
        f.Act(child,"confirm");Check(f.Child(child) is CardSelectionV1ResolvedResult&&f.CompletionValid&&ReferenceEquals(f.Originals.Single(),f.Cards[2]),"exact offscreen original effect");
        var parent=f.Session.Read();Check(parent.CompletedCardChildren==1&&parent.Phase=="proceed","retained child completion");
        f.Session.Apply(parent.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete"&&f.OptionCalls==2&&f.SelectCalls==1&&f.ConfirmCalls==1,"map continuation counts");
    }
    private static void Admission(string mode,string? mutation)
    {
        using var f=new global::Program.TransformFixture("REJECT",1,domain:20);OffscreenGeometry g=null!;Wrap(mode,x=>{g=x;if(mutation is not null)x.Mutate(mutation);});
        var parent=f.Start();Check(parent.Status!="child","inadmissible geometry "+mode+mutation);
        for(int i=0;i<258&&parent.Status=="waiting";i++)parent=f.Session.Read();
        Check(parent.Status=="unsupported"&&f.SelectCalls==0&&g.DispatchCount==0,"bounded no-input admission "+mode+mutation);
    }
    private static void Race(string mutation)
    {
        using var f=new global::Program.TransformFixture("RACE",1,domain:20);OffscreenGeometry g=null!;Wrap("probe",x=>g=x);var child=f.Start();
        var observed=(CardSelectionV1Observation)f.Child(child);Check(observed.LegalActions.Contains("select:2"),"race advertised below");g.Mutate(mutation);
        _=f.Session.ApplyCardChild(child.Child!.ParentDecisionId,child.Child.ParentActionId,child.Child.Ordinal,observed.DecisionId,"select:2");
        Check(f.SelectCalls==0&&g.DispatchCount==0,"changed proof dispatch rejected "+mutation);
    }
    private static void DeferredReassignment(string mutation)
    {
        using var f=new global::Program.TransformFixture("DEFERRED",1,domain:20);OffscreenGeometry g=null!;Action? pending=null;
        Wrap("probe",x=>{g=x;x.Holders[2].FixtureGuiInputDispatch=action=>pending=action;});var child=f.Start();f.Act(child,"select:2");
        Check(pending is not null&&g.DispatchCount==1&&g.AllDispatchesBelow&&f.SelectCalls==0,"deferred actual below input");
        g.Mutate(mutation);try{pending!();}catch(InvalidOperationException error)when(mutation=="model"&&error.Message=="Sequence contains no matching element"){ }Check(f.Child(child) is CardSelectionV1Observation{Status:"unsupported"}&&f.ConfirmCalls==0,"deferred "+mutation+" cannot confirm");
    }
    private static void Variable()
    {
        using var f=new global::Program.TransformFixture("VARIABLE",3,domain:20,manual:true,minimum:1);OffscreenGeometry g=null!;Wrap("all_below",x=>g=x);var child=f.Start();
        f.Act(child,"select:4");f.Act(child,"preview");f.Act(child,"confirm");Check(f.Child(child) is CardSelectionV1ResolvedResult&&f.CompletionValid&&g.AllDispatchesBelow&&g.DispatchCount==1,"variable explicit preview remains witnessed");
    }
    private static void NoFallback()
    {
        using var f=new global::Program.TransformFixture("DISABLED",1,domain:20);OffscreenGeometry g=null!;Wrap("probe",x=>{g=x;x.Mutate("disabled");});
        var child=f.Start();Check(child.Status!="child"&&f.SelectCalls==0&&g.DispatchCount==0,"no on-screen fallback when offscreen disabled");
    }
}
