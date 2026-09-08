using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV7;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV9;

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
            DiagnosticStages();
            Console.WriteLine("{\"status\":\"passed\",\"suite\":\"generic_event_v9_offscreen\",\"check_count\":"+_checks+"}");return 0;
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
    // These calls execute the actual release adapter against inert targets.
    // Reflection is confined to this test assembly for defensive helpers which
    // successful production candidate binding deliberately makes unreachable.
    private static readonly HashSet<GenericEventDiagnosticCode> _diagnostics=new();
    private static readonly BindingFlags Hidden=BindingFlags.NonPublic|BindingFlags.Public|BindingFlags.Static|BindingFlags.Instance;
    private static readonly Type Adapter=typeof(GenericEventV7TransformAdapter);
    private delegate bool MatchCall(ref GenericEventDiagnosticCode diagnostic);
    private delegate CardSelectionV1NativeCandidate[] MaskCall(CardSelectionV1NativeCandidate[] candidates,ref GenericEventDiagnosticCode diagnostic);
    private static GenericEventDiagnosticCode Last(global::Program.TransformFixture fixture)=>( (PinnedGenericEventV7NativeAdapter)typeof(GenericEventV7Session).GetField("_native",Hidden)!.GetValue(fixture.Session)!).LastDiagnostic;
    private static void Diagnostic(GenericEventDiagnosticCode got,GenericEventDiagnosticCode expected,string label)
    {Check(got==expected,label+" diagnostic: "+got+" expected "+expected);_diagnostics.Add(got);}
    private static Control Scroll(OffscreenGeometry g)=>g.Grid.GetNodeOrNull<Control>("%ScrollContainer")!;
    private static void NativeDiagnostic(GenericEventDiagnosticCode expected,Action<OffscreenGeometry> mutation,string label)
    {
        GeometryTrace.Reset();var size=NCard.defaultSize;var scale=NCardHolder.smallScale;
        try
        {
            using var f=new global::Program.TransformFixture("DIAGNOSTIC",1,domain:20);OffscreenGeometry g=null!;
            Wrap("probe",x=>{g=x;mutation(x);});var parent=f.Start();
            Check(parent.Status=="waiting"&&f.SelectCalls==0&&g.DispatchCount==0,label+" refuses without input");
            Diagnostic(Last(f),expected,label);
        }
        finally {GeometryTrace.Reset();NCard.defaultSize=size;NCardHolder.smallScale=scale;}
    }
    private static void DiagnosticStages()
    {
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryScrollMissing,g=>g.Grid.Bind("%ScrollContainer",new Node()),"missing scroll");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryScrollInvalid,g=>Scroll(g).InstanceValid=false,"invalid scroll");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryScrollInvisible,g=>Scroll(g).Visible=false,"invisible scroll");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryScrollSize,g=>Scroll(g).Size=new Vector2(0,0),"zero scroll");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryScrollPosition,g=>Scroll(g).Position=new Vector2(float.NaN,0),"nan position");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryGridSize,g=>g.Grid.Size=new Vector2(0,200),"zero grid");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryCardSize,g=>NCard.defaultSize=new Vector2(0,300),"zero card size");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryYOffset,g=>g.Grid.YOffset=-1,"negative offset");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryColumns,g=>Scroll(g).Size=new Vector2(1,200),"no columns");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryScrollHeightMismatch,g=>Scroll(g).Size=new Vector2(1000,1),"scroll height mismatch");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryScrollPositionMismatch,g=>Scroll(g).Position=new Vector2(0,1),"scroll position mismatch");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryClipSearchInvalid,g=>{g.Grid.ClipContents=false;g.Grid.FixtureParent=new Control{InstanceValid=false};},"invalid clip search");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryClipSearchCycle,g=>{g.Grid.ClipContents=false;g.Grid.FixtureParent=g.Grid;},"clip search cycle");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryClipSearchDepth,g=>{g.Grid.ClipContents=false;Node at=g.Grid;for(int i=0;i<33;i++){var n=new Control();at.FixtureParent=n;at=n;}},"clip search depth");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryClipMissing,g=>g.Grid.ClipContents=false,"missing clip");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryClipRect,g=>g.Grid.FixtureRect=new Rect2(default,default),"clip zero rect");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryCanvasInvalid,g=>g.Grid.FixtureCanvas=new Rid(0),"invalid clip canvas");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryChainInvalid,g=>g.Holders[2].FixtureParent=new Control{InstanceValid=false,FixtureParent=g.Grid},"invalid chain");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryChainNonCanvas,g=>g.Mutate("noncanvas"),"noncanvas chain");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryChainCycle,g=>g.Mutate("cycle"),"chain cycle");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryChainDepth,g=>g.Mutate("deep"),"chain depth");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryChainUnreached,g=>g.Holders[2].FixtureParent=null,"unreached clip");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryTopLevel,g=>g.Mutate("toplevel"),"top level");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryCanvasMismatch,g=>g.Mutate("canvas"),"canvas mismatch");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryTransform,g=>g.Mutate("rotation"),"rotated basis");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryNodeRect,g=>g.Mutate("nan"),"nonfinite ancestor rect");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryControlRect,g=>g.Mutate("zero"),"nonpositive candidate rect");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryNoneEligible,g=>g.Mutate("disabled"),"no eligible below card");
        // Earliest predicate is deterministic when several independent checks fail.
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryScrollSize,g=>{Scroll(g).Size=default;Scroll(g).Position=new Vector2(float.NaN,0);g.Grid.Size=default;g.Grid.YOffset=-1;g.Grid.ClipContents=false;},"layout first failure");
        NativeDiagnostic(GenericEventDiagnosticCode.GeometryTopLevel,g=>{g.Mutate("toplevel");g.Mutate("canvas");g.Mutate("rotation");},"chain first failure");
        foreach(var entry in new (string Member,GenericEventDiagnosticCode Code)[]{("size",GenericEventDiagnosticCode.GeometryScrollSize),("position",GenericEventDiagnosticCode.GeometryScrollPosition)})
            NativeDiagnostic(entry.Code,g=>{GeometryTrace.Labels[Scroll(g)]="throw";GeometryTrace.Scripts["throw."+entry.Member]=(_,_)=>throw new InvalidOperationException("inert getter");GeometryTrace.Enabled=true;},"throw scroll "+entry.Member);
        foreach(var entry in new (string Member,GenericEventDiagnosticCode Code)[]{("y_offset",GenericEventDiagnosticCode.GeometryYOffset),("rect",GenericEventDiagnosticCode.GeometryClipRect),("canvas",GenericEventDiagnosticCode.GeometryCanvasInvalid),("top_level",GenericEventDiagnosticCode.GeometryTopLevel),("transform",GenericEventDiagnosticCode.GeometryTransform),("clip",GenericEventDiagnosticCode.GeometryClipMissing)})
            NativeDiagnostic(entry.Code,g=>{GeometryTrace.Labels[g.Grid]="throw";GeometryTrace.Scripts["throw."+entry.Member]=(_,_)=>throw new InvalidOperationException("inert getter");GeometryTrace.Enabled=true;},"throw grid "+entry.Member);
        DefensiveAndRetainedStages();DiagnosticReset();DepthBoundary();
        Check(_diagnostics.SetEquals(Enumerable.Range(78,37).Select(i=>(GenericEventDiagnosticCode)i)),"all 37 appended diagnostic stages execute");
    }
    private static void DefensiveAndRetainedStages()
    {
        using var f=new global::Program.TransformFixture("HELPER_STAGES",1,domain:20);OffscreenGeometry g=null!;Wrap("probe",x=>g=x);
        Check(f.Start().Status=="child","defensive helper setup admitted");
        object?[] bindingArgs={g.Holders,f.Cards.Take(20).ToArray(),null,null};
        Check((bool)Adapter.GetMethod("TryCreateBindings",Hidden)!.Invoke(null,bindingArgs)!,"actual candidate bindings");
        var bindings=(Array)bindingArgs[2]!;var candidates=(CardSelectionV1NativeCandidate[])bindingArgs[3]!;
        var gridType=Adapter.GetNestedType("GridGeometry",Hidden)!;
        object?[] countArgs={g.Grid,Array.CreateInstance(bindings.GetType().GetElementType()!,1),null,GenericEventDiagnosticCode.NotCaptured};
        Check(!(bool)gridType.GetMethod("TryBind",Hidden)!.Invoke(null,countArgs)!,"defensive candidate count rejected");
        Diagnostic((GenericEventDiagnosticCode)countArgs[3]!,GenericEventDiagnosticCode.GeometryCandidateCount,"candidate count");
        object?[] args={g.Grid,bindings,null,GenericEventDiagnosticCode.NotCaptured};
        Check((bool)gridType.GetMethod("TryBind",Hidden)!.Invoke(null,args)!,"actual retained proof bound");
        object geometry=args[2]!;object probe=gridType.GetProperty("Probe",Hidden)!.GetValue(geometry)!;
        var match=(MatchCall)probe.GetType().GetMethod("Matches",Hidden,null,new[]{typeof(GenericEventDiagnosticCode).MakeByRefType()},null)!.CreateDelegate(typeof(MatchCall),probe);
        var mask=(MaskCall)probe.GetType().GetMethod("Mask",Hidden,null,new[]{typeof(CardSelectionV1NativeCandidate[]),typeof(GenericEventDiagnosticCode).MakeByRefType()},null)!.CreateDelegate(typeof(MaskCall),probe);
        GenericEventDiagnosticCode diagnostic=GenericEventDiagnosticCode.NotCaptured;
        try {mask(Array.Empty<CardSelectionV1NativeCandidate>(),ref diagnostic);Check(false,"mask mismatch throws");}
        catch(InvalidOperationException){Diagnostic(diagnostic,GenericEventDiagnosticCode.GeometryMaskCount,"mask count");}
        var holder=g.Holders[2];var originalParent=holder.FixtureParent;var originalRect=holder.FixtureRect;var originalTransform=holder.FixtureTransform;
        foreach(var entry in new (string Mode,GenericEventDiagnosticCode Code)[]{("clip",GenericEventDiagnosticCode.GeometryClipChanged),("parent",GenericEventDiagnosticCode.GeometryParentChanged),("rotation",GenericEventDiagnosticCode.GeometryTransformChanged),("rectangle",GenericEventDiagnosticCode.GeometryRectChanged),("node_clip",GenericEventDiagnosticCode.GeometryNodeClipChanged)})
        {
            if(entry.Mode=="node_clip")holder.ClipContents=true;else g.Mutate(entry.Mode);
            Check(!match(ref diagnostic),"retained proof rejects "+entry.Mode);Diagnostic(diagnostic,entry.Code,"retained "+entry.Mode);
            g.Clip.ClipContents=true;holder.ClipContents=false;holder.FixtureParent=originalParent;holder.FixtureRect=originalRect;holder.FixtureTransform=originalTransform;
        }
        var initial=Adapter.GetMethod("InitialCandidatesValid",Hidden,null,new[]{typeof(IReadOnlyList<CardSelectionV1NativeCandidate>),typeof(GenericEventDiagnosticCode).MakeByRefType()},null)!;
        foreach(bool selected in new[]{true,false})
        {
            var c=candidates[0];var invalid=new CardSelectionV1NativeCandidate(c.Slot,c.StableKey,c.HolderIdentity,c.ModelIdentity,c.CardNodeIdentity,c.UpgradeLevel,false,c.Enabled,selected,c.SelectionSettled,c.SelectDispatch);
            object?[] initialArgs={new[]{invalid},GenericEventDiagnosticCode.NotCaptured};
            Check(!(bool)initial.Invoke(null,initialArgs)!,"invalid initial candidate rejected");
            Diagnostic((GenericEventDiagnosticCode)initialArgs[1]!,selected?GenericEventDiagnosticCode.GeometryInitiallySelected:GenericEventDiagnosticCode.GeometryCandidateInvisible,"initial candidate precedence");
        }
        Check(g.DispatchCount==0&&f.SelectCalls==0,"all helper negatives have no card input");
        // One retained Probe.Matches pass, with exactly one clip read plus each
        // retained node read; no second diagnostic-specific geometry sampling.
        GeometryTrace.Reset();GeometryTrace.Enabled=true;Check(match(ref diagnostic),"unchanged proof still matches");
        Check(GeometryTrace.Operations.Count(x=>x.EndsWith(".rect",StringComparison.Ordinal))==1+1+20*(2+3+3),"retained sampling count");GeometryTrace.Reset();
    }
    private static void DiagnosticReset()
    {
        using var f=new global::Program.TransformFixture("DIAGNOSTIC_RESET",1,domain:20);OffscreenGeometry g=null!;Vector2 good=default;
        Wrap("probe",x=>{g=x;good=Scroll(x).Size;Scroll(x).Size=new Vector2(1000,1);});
        Check(f.Start().Status=="waiting","diagnostic reset initially waits");Diagnostic(Last(f),GenericEventDiagnosticCode.GeometryScrollHeightMismatch,"reset failure");
        Scroll(g).Size=good;var child=f.Session.Read();Check(child.Status=="child"&&Last(f)==GenericEventDiagnosticCode.ChildReady,"successful read clears geometry diagnostic");
        f.Act(child,"select:2");f.Act(child,"confirm");_=f.Child(child);var parent=f.Session.Read();f.Session.Apply(parent.DecisionId,"choose:0");
        Check(f.Session.Read().Status=="complete"&&Last(f)==GenericEventDiagnosticCode.MapReady,"parent completion resets diagnostic");
    }
    private static void DepthBoundary()
    {
        using var f=new global::Program.TransformFixture("DEPTH_BOUNDARY",1,domain:20);OffscreenGeometry g=null!;
        Wrap("probe",x=>{g=x;Node parent=x.Grid;for(int i=0;i<30;i++)parent=new Control{FixtureParent=parent};x.Holders[2].FixtureParent=parent;});
        Check(f.Start().Status=="child"&&g.DispatchCount==0,"clip at chain depth32 admitted");
    }

}
