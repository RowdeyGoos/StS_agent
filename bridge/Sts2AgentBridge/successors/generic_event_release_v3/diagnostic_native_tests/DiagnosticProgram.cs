using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV3;
using Sts2AgentBridge.Successors.GenericEventV3.Native;
using Sts2AgentBridge.Successors.GenericEventReleaseV3;

internal static class DiagnosticProgram
{
    private static int _checks;
    private static readonly HashSet<GenericEventDiagnosticCode> Seen=new();
    private static void Check(bool value,string name){_checks++;if(!value)throw new InvalidOperationException(name);}
    internal static GenericEventV3Binding Binding(Program.RewardFixture f)=>(GenericEventV3Binding)typeof(PinnedGenericEventV3NativeAdapter).GetField("_pending",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(f.Adapter)!;
    private static void Dispatch(Program.RewardFixture f)
    {var p=f.Session.Read();Check(p.Status=="ready","diagnostic parent initially ready");Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","diagnostic parent accepted");}
    private static void Observe(Program.RewardFixture f,GenericEventDiagnosticCode expected,string status)
    {
        int actions=f.OptionCalls+f.SelectCalls+f.ConfirmCalls;
        var capture=f.Adapter.Capture();
        Check(capture.Status==status && f.Adapter.LastDiagnostic==expected,"native gate "+expected);
        Check(actions==f.OptionCalls+f.SelectCalls+f.ConfirmCalls,"capture never dispatches "+expected);Seen.Add(expected);
    }
    private static void NativeCase(GenericEventDiagnosticCode code,string status,Action<Program.RewardFixture,GenericEventV3Binding> mutation)
    {using var f=new Program.RewardFixture("GATE",2,2,8);Dispatch(f);mutation(f,Binding(f));Observe(f,code,status);}
    private static void PrepareCase(GenericEventDiagnosticCode code,Action<Program.RewardFixture,GenericEventV3Binding> mutation)
    {
        using var f=new Program.RewardFixture("PREPARE",2,2,8);Dispatch(f);var b=Binding(f);mutation(f,b);
        var prior=f.Adapter.LastDiagnostic;
        Check(!GenericEventV3RewardAdapter.IsReady(b,f.Screen,out var observed)&&observed==code,"selector gate "+code);
        Check(f.Adapter.LastDiagnostic==prior,"preparation alone never publishes "+code);Seen.Add(code);
    }
    internal static int Main()
    {
        try
        {
            using(var f=new Program.RewardFixture("INITIAL",2,2,8))
            {
                Check(f.Adapter.LastDiagnostic==GenericEventDiagnosticCode.NotCaptured,"initial passive none");Seen.Add(GenericEventDiagnosticCode.NotCaptured);
                Observe(f,GenericEventDiagnosticCode.ParentReady,"parent");f.Map.IsOpen=true;Observe(f,GenericEventDiagnosticCode.ParentUnavailable,"unsupported");
            }
            NativeCase(GenericEventDiagnosticCode.PendingBindingFailed,"unsupported",(f,b)=>{b.Failed=true;f.Player.ThrowRunState=true;});
            NativeCase(GenericEventDiagnosticCode.PendingOwnership,"unsupported",(f,b)=>{GenericEventV3Hooks.Close(b);f.Player.ThrowRunState=true;});
            NativeCase(GenericEventDiagnosticCode.PendingContext,"unsupported",(f,b)=>f.Room.Layout=new MegaCrit.Sts2.Core.Nodes.Events.NEventLayout());
            NativeCase(GenericEventDiagnosticCode.PendingTaskFailed,"unsupported",(f,b)=>b.ChosenTask=Task.FromException(new InvalidOperationException("fixture")));
            NativeCase(GenericEventDiagnosticCode.PendingChosenEntry,"waiting",(f,b)=>{b.RequestSeen=false;b.ChosenSeen=false;b.ChosenTask=null;f.Overlays.Screens.Clear();});
            NativeCase(GenericEventDiagnosticCode.PendingChosenTask,"waiting",(f,b)=>{b.ChosenTask=null;});
            NativeCase(GenericEventDiagnosticCode.PendingChosenCompletion,"waiting",(f,b)=>{b.RequestSeen=false;f.Overlays.Screens.Clear();});
            NativeCase(GenericEventDiagnosticCode.PendingRequestTask,"waiting",(f,b)=>b.RequestTask=null);
            NativeCase(GenericEventDiagnosticCode.PendingScreen,"waiting",(f,b)=>b.Screen=null);
            NativeCase(GenericEventDiagnosticCode.PendingSelectorlessRequest,"unsupported",(f,b)=>{b.Screen=null;b.RequestTask=Task.FromResult<IEnumerable<CardModel>>(Array.Empty<CardModel>());});
            NativeCase(GenericEventDiagnosticCode.PendingOverlay,"unsupported",(f,b)=>f.Overlays.Screens.Clear());
            NativeCase(GenericEventDiagnosticCode.PendingDeck,"unsupported",(f,b)=>f.BaselineCards[0].CurrentUpgradeLevel++);
            NativeCase(GenericEventDiagnosticCode.PendingOffers,"unsupported",(f,b)=>f.ResultEntries[0].ModifiedCard=f.OfferCards[1]);
            NativeCase(GenericEventDiagnosticCode.PendingProceed,"waiting",(f,b)=>{b.Option.IsProceed=true;b.RequestSeen=false;f.Overlays.Screens.Clear();});
            NativeCase(GenericEventDiagnosticCode.MapReady,"map",(f,b)=>{b.Option.IsProceed=true;b.RequestSeen=false;b.ChosenTask=Task.CompletedTask;f.Overlays.Screens.Clear();f.Map.IsOpen=true;f.Map.IsTravelEnabled=true;});
            NativeCase(GenericEventDiagnosticCode.ParentWaiting,"waiting",(f,b)=>{b.RequestSeen=false;b.ChosenTask=Task.CompletedTask;f.Overlays.Screens.Clear();f.Room.Layout.OptionButtons.Clear();});
            NativeCase(GenericEventDiagnosticCode.PrepareFamily,"waiting",(f,b)=>{b.Screen=new NCardGridSelectionScreen();f.Overlays.Screens.Clear();f.Overlays.Screens.Add(b.Screen);});
            NativeCase(GenericEventDiagnosticCode.CaptureException,"unsupported",(f,b)=>f.Player.ThrowRunState=true);
            using(var f=new Program.RewardFixture("DISPOSED",2,2,8)){f.Adapter.Dispose();Observe(f,GenericEventDiagnosticCode.CaptureDisposed,"unsupported");}
            PrepareCase(GenericEventDiagnosticCode.PrepareBinding,(f,b)=>b.Failed=true);
            PrepareCase(GenericEventDiagnosticCode.PrepareScreen,(f,b)=>f.Screen.Visible=false);
            PrepareCase(GenericEventDiagnosticCode.PrepareExternalSelector,(f,b)=>CardSelectCmd.Selector=new object());
            PrepareCase(GenericEventDiagnosticCode.PrepareDeck,(f,b)=>f.BaselineCards[0].CurrentUpgradeLevel++);
            PrepareCase(GenericEventDiagnosticCode.PrepareForeground,(f,b)=>f.Model.IsFinished=true);
            PrepareCase(GenericEventDiagnosticCode.PrepareGridNode,(f,b)=>f.Screen.Bind("%CardGrid",new Control()));
            PrepareCase(GenericEventDiagnosticCode.PrepareGridState,(f,b)=>f.Grid.IsAnimatingOut=true);
            PrepareCase(GenericEventDiagnosticCode.PrepareHolders,(f,b)=>f.Grid.CurrentlyDisplayedCardHolders.Add(f.Grid.CurrentlyDisplayedCardHolders[0]));
            PrepareCase(GenericEventDiagnosticCode.PrepareCandidates,(f,b)=>f.Grid.CurrentlyDisplayedCardHolders[0].CardModel=new CardModel());
            PrepareCase(GenericEventDiagnosticCode.PrepareGeometry,(f,b)=>f.Grid.Size=new Vector2(1,1));
            PrepareCase(GenericEventDiagnosticCode.PrepareConfirm,(f,b)=>f.ConfirmButton.IsEnabled=true);
            using(var f=new Program.RemovalFixture("PREVIEW_NODES",1,2,5))
            {var c=f.Start();f.Screen.Bind("%PreviewContainer",new Control());var capture=f.Adapter.Capture();Check(capture.Status=="waiting"&&f.Adapter.LastDiagnostic==GenericEventDiagnosticCode.PreparePreviewNodes,"missing preview node gate");Seen.Add(GenericEventDiagnosticCode.PreparePreviewNodes);}
            using(var f=new Program.RemovalFixture("PREVIEW_STATE",1,2,5))
            {var c=f.Start();f.PreviewContainer.Visible=true;var capture=f.Adapter.Capture();Check(capture.Status=="waiting"&&f.Adapter.LastDiagnostic==GenericEventDiagnosticCode.PreparePreviewState,"preview initial state gate");Seen.Add(GenericEventDiagnosticCode.PreparePreviewState);}
            HistoryAndConstructor();
            var expected=Enum.GetValues<GenericEventDiagnosticCode>().Where(c=>c!=GenericEventDiagnosticCode.DiagnosticUnavailable).ToHashSet();
            Check(expected.SetEquals(Seen),"all native diagnostic codes covered: "+string.Join(",",expected.Except(Seen)));
            Console.WriteLine("generic diagnostic native checks: "+_checks+"; codes: "+Seen.Count);return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
    private static void HistoryAndConstructor()
    {
        using(var d=new DiagnosticFixture(new string('d',32),"BINDING_WAIT"))
        {
            Dispatch(d.Inner);Observe(d.Inner,GenericEventDiagnosticCode.PendingScreen,"waiting");
            int calls=CardSelectCmd.Calls;d.Inner.Player.ThrowRunState=true;
            for(int i=0;i<20;i++)Check(d.Adapter.LastDiagnostic==GenericEventDiagnosticCode.PendingScreen,"passive cached diagnostic does not read throwing game state");
            Check(calls==CardSelectCmd.Calls,"passive diagnostic never invokes request");d.Inner.Player.ThrowRunState=false;d.ReleaseCreation();Observe(d.Inner,GenericEventDiagnosticCode.ChildReady,"child");
        }
        using(var d=new DiagnosticFixture(new string('e',32),"SELECTOR_WAIT"))
        {
            Dispatch(d.Inner);var result=d.Session.Read();Check(result.Status=="waiting"&&d.Adapter.LastDiagnostic==GenericEventDiagnosticCode.PrepareGeometry,"actual geometry wait published");
            for(int i=0;i<256;i++)result=d.Session.Read();
            Check(result.Status=="unsupported"&&result.ChildEpisodes==0&&d.Adapter.LastDiagnostic==GenericEventDiagnosticCode.PrepareGeometry,"core pending budget retains last completed native capture gate");
        }
        using(var d=new DiagnosticFixture(new string('f',32),"SELECTOR_WAIT"))
        {
            Dispatch(d.Inner);Observe(d.Inner,GenericEventDiagnosticCode.PrepareGeometry,"waiting");d.RestoreGeometry();
            var capture=d.Adapter.Capture();Check(capture.Status=="child"&&d.Adapter.LastDiagnostic==GenericEventDiagnosticCode.ChildReady,"recovered geometry resets diagnostic");Seen.Add(GenericEventDiagnosticCode.ChildReady);
            d.Inner.Grid.Size=new Vector2(1,1);bool rejected=false;
            try{d.Adapter.CreateChild(capture.Admission!.Identity);}catch(InvalidOperationException){rejected=true;}
            Check(rejected&&d.Adapter.LastDiagnostic==GenericEventDiagnosticCode.ChildReady,"child constructor failure cannot overwrite completed capture history");
        }
        using(var d=new DiagnosticFixture(new string('1',32),"NORMAL"))
        {
            var c=d.Inner.Start();Check(c.Status=="child"&&d.Adapter.LastDiagnostic==GenericEventDiagnosticCode.ChildReady,"child readiness published");
            int taskCalls=d.Inner.Screen.CardsSelectedCalls;d.Inner.Act(c,"select:1");d.Inner.Act(c,"select:0");
            Check(d.Inner.Child(c) is CardSelectionV1ResolvedResult&&d.Inner.Screen.CardsSelectedCalls==taskCalls,"diagnostics add no task getter reads or effect changes");
            var p=d.Session.Read();Check(p.Phase=="proceed"&&d.Adapter.LastDiagnostic==GenericEventDiagnosticCode.ParentReady,"parent next capture resets diagnostic");
            d.Session.Apply(p.DecisionId,"choose:0");Check(d.Session.Read().Status=="complete"&&d.Adapter.LastDiagnostic==GenericEventDiagnosticCode.MapReady,"map capture resets diagnostic");
            Check(d.OptionCalls==2&&d.SelectCalls==2&&d.ConfirmCalls==0,"exact original dispatch counts unchanged");
        }
    }
}
