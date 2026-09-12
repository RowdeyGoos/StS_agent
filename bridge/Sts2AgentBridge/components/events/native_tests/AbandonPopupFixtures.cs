using System;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static partial class Program {
    internal sealed class AbandonFixture:IDisposable {
        internal readonly Fixture World=new("ABANDON");
        internal GenericEventV7Session Session=>World.Session;
        internal readonly NModalContainer Modal=new();
        internal readonly RunManager Manager=new();
        internal NAbandonRunConfirmPopup Popup=null!;
        internal int Cancels,Abandons;
        internal bool Delay,Fault,NoEffect,Duplicate,MainMenu,CleanupFailed;
        internal bool StrictCleanup=false;
        internal readonly TaskCompletionSource Completion=new();
        internal AbandonFixture() {
            RunManager.Instance=Manager;Manager.State=(RunState)World.Player.RunState;NModalContainer.Instance=Modal;
            Manager.AbandonHandler=()=>{Abandons++;if(Fault)return Task.FromException(new Exception("abandon failed"));if(Delay)return Completion.Task;Finish();return Task.CompletedTask;};
            NAbandonRunConfirmPopup.Factory=()=>{
                Popup=new();var no=Popup.Vertical.NoButton.Clicked;Popup.Vertical.NoButton.Clicked=()=>{Cancels++;no!();};return Popup;
            };
            var trial=(MegaCrit.Sts2.Core.Models.Events.Trial)World.Model;
            World.Room.Layout.OptionButtons[0].Option.Callback=trial.PopupCallback;
            World.Room.Layout.OptionButtons[0].Option.WillKillPlayer=_=>true;
            World.Room.Layout.OptionButtons[0].Option.IsProceed=true;
            trial.PopupHandler=()=>{
                Modal.Add(NAbandonRunConfirmPopup.Create(MainMenu?new MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu():null),true);
                if(Duplicate)NAbandonRunConfirmPopup.Create(null);return Task.CompletedTask;
            };
            var accept=new EventOption{TextKey="ABANDON.ACCEPT",Callback=()=>{
                World.Model.IsFinished=true;World.Room.Layout.OptionButtons.Clear();
                World.AddOption(new EventOption{IsProceed=true,TextKey="ABANDON.PROCEED",Callback=()=>{World.Map.IsOpen=true;World.Map.IsTravelEnabled=true;return Task.CompletedTask;}});return Task.CompletedTask;
            }};
            World.AddOption(accept);
        }
        internal void Finish(){if(!NoEffect){Manager.IsAbandoned=true;World.Player.Creature.CurrentHp=0;}Completion.TrySetResult();}
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation parent)=>((GenericEventV7RewardChildRead)Session.ReadChild(parent.Child!.ParentDecisionId,parent.Child.ParentActionId,parent.Child.Ordinal)).Value;
        internal string Act(GenericEventV7Observation parent,string action,string? decision=null) {
            decision??=Read(parent).DecisionId;var c=parent.Child!;
            return ((GenericEventV7RewardChildApply)Session.ApplyChild(c.ParentDecisionId,c.ParentActionId,c.Ordinal,decision,action)).Value.Outcome;
        }
        public void Dispose(){try{World.Dispose();}catch(InvalidOperationException){CleanupFailed=true;try{World.Adapter.Dispose();}catch(InvalidOperationException){}if(StrictCleanup)throw new InvalidOperationException("Custom screen cleanup failed.");}finally{NModalContainer.Instance=null;NAbandonRunConfirmPopup.Factory=null;RunManager.Instance=null;}}
    }
    private static void AbandonPopupCases() {
        using(var f=new AbandonFixture()) {
            var initial=f.Session.Read();Check(initial.Candidates[0].IsDangerous&&initial.Candidates[0].Discovery=="abandon_confirmation"&&initial.LegalActions.Contains("choose:0"),"exact native callback admits confirmation while retaining danger");var c=f.Start();Check(c.Child?.Kind=="abandon_confirmation","owned modal admitted");
            var r=f.Read(c);Check(r.LegalActions.SequenceEqual(new[]{"cancel","confirm_abandon"}),"cancel is first default action");
            Check(f.Act(c,"cancel")=="accepted","cancel dispatch");r=f.Read(c);
            Check(r.Status=="resolved"&&r.Phase=="cancelled"&&f.Cancels==1&&f.Abandons==0,"unchanged cancellation certified");
            var back=f.Session.Read();Check(back.Status=="ready"&&back.Candidates.Count==2&&back.DecisionId!=initial.DecisionId,"same native options receive fresh decision after cancel");
            Check(f.Session.Apply(initial.DecisionId,"choose:0").Outcome=="stale_decision","pre-popup decision never reusable");
        }
        foreach(bool delay in new[]{false,true})using(var f=new AbandonFixture{Delay=delay}) {
            var c=f.Start();Check(f.Act(c,"confirm_abandon")=="accepted","explicit confirmation dispatch");
            if(delay){Check(f.Read(c).Status=="waiting","owned native task must complete");f.Finish();}
            var r=f.Read(c);Check(r.Status=="resolved"&&r.Phase=="abandoned"&&r.PriorResults.Count==1,"exact abandonment outcome");
            var end=f.Session.Read();Check(end.Status=="complete"&&end.Phase=="run_abandoned"&&end.ParentReconciled==1&&end.CompletedCardChildren==0&&end.PriorResults.Single().Result=="run_abandoned","terminal result without map or card claim");
            Check(f.Abandons==1&&f.World.Player.Creature.CurrentHp==0&&!f.World.Map.IsOpen,"one native abandonment");
        }
        foreach(var mode in new[]{"foreign_modal","button","gold","deck","network","manager","lost_callback","fault","no_effect","cancel_effect","cancel_task","reentry","wrong_thread","cancelled_task","duplicate_input"})using(var f=new AbandonFixture()) {
            var c=f.Start();var r=f.Read(c);string action=mode.StartsWith("cancel_")?"cancel":"confirm_abandon";
            switch(mode) {
                case "foreign_modal":f.Modal.OpenModal=new Control();break;
                case "button":f.Popup.Vertical.YesButton=new();break;
                case "gold":f.World.Player.Gold++;break;
                case "deck":f.World.Player.Deck.Cards.Reverse();break;
                case "network":((MegaCrit.Sts2.Core.Multiplayer.Game.FixtureNetService)f.Manager.NetService).Type=2;break;
                case "manager":RunManager.Instance=new();break;
                case "lost_callback":f.Popup.Vertical.YesButton.Clicked=()=>f.Modal.Clear();break;
                case "fault":f.Fault=true;break;
                case "no_effect":f.NoEffect=true;break;
                case "cancel_effect":f.Popup.Vertical.NoButton.Clicked=()=>{f.World.Player.Gold++;f.Modal.Clear();};break;
                case "cancel_task":f.Popup.Vertical.NoButton.Clicked=()=>{f.Manager.Abandon();f.Modal.Clear();};break;
                case "reentry":f.Popup.Vertical.YesButton.Clicked=()=>{f.Read(c);f.Manager.Abandon();};break;
                case "wrong_thread":Task.Run(()=>f.Read(c)).GetAwaiter().GetResult();break;
                case "cancelled_task":f.Manager.AbandonHandler=()=>Task.FromCanceled(new System.Threading.CancellationToken(true));break;
                case "duplicate_input":var original=f.Popup.Vertical.YesButton.Clicked;f.Popup.Vertical.YesButton.Clicked=()=>{original!();f.Manager.Abandon();};break;
            }
            string outcome=f.Act(c,action,r.DecisionId);
            Check(outcome!="accepted"||f.Read(c).Status=="unsupported","invalid popup stops "+mode);
            Check(f.Session.Read().Status!="complete"&&f.Session.Read().ParentReconciled==0,"no terminal reconciliation "+mode);
            Check(f.Abandons<=(mode=="duplicate_input"?2:1),"bounded native input "+mode);
        }
        foreach(var mutation in new[]{"options","label","callback","chosen","modal"})using(var f=new AbandonFixture()) {
            var c=f.Start();Check(f.Act(c,"cancel")=="accepted","cancel before boundary mutation");
            Check(f.Read(c).Status=="resolved","initial cancellation outcome");
            switch(mutation) {
                case "options":f.World.Room.Layout.OptionButtons.Reverse();break;
                case "label":f.World.Room.Layout.OptionButtons[0].GetNodeOrNull<MegaCrit.Sts2.addons.mega_text.MegaRichTextLabel>("%Text")!.Text="changed";break;
                case "callback":f.World.Room.Layout.OptionButtons[0].Option.Callback=()=>Task.CompletedTask;break;
                case "chosen":f.World.Room.Layout.OptionButtons[0].Option.WasChosen=false;break;
                case "modal":f.Modal.OpenModal=new Control();break;
            }
            Check(f.Session.Read().Status=="unsupported","completion revalidates cancelled parent "+mutation);
            f.Dispose();Check(f.CleanupFailed,"changed completion fails cleanup "+mutation);
        }
        foreach(bool confirm in new[]{false,true})using(var f=new AbandonFixture{Delay=true}) {
            var c=f.Start();Check(f.Act(c,"confirm_abandon")=="accepted","pending abandonment admitted");
            if(confirm){f.Finish();Check(f.Read(c).Status=="resolved","initial abandonment complete");f.World.Player.Creature.CurrentHp=1;}
            f.Dispose();Check(f.CleanupFailed,"pending or changed abandonment cannot cleanly release");
        }
        using(var f=new AbandonFixture()) {
            f.World.Room.Layout.OptionButtons[0].Option.Callback=()=>Task.CompletedTask;
            Check(f.Session.Read().Status=="unsupported","same label cannot admit a different lethal Proceed callback");
        }
        foreach(var mode in new[]{"preexisting","main_menu","duplicate"})using(var f=new AbandonFixture()) {
            if(mode=="preexisting"){f.Modal.OpenModal=new Control();Check(f.Session.Read().Status=="unsupported","unowned modal hides parent");continue;}
            f.MainMenu=mode=="main_menu";f.Duplicate=mode=="duplicate";
            var r=f.Session.Read();f.Session.Apply(r.DecisionId,"choose:0");Check(f.Session.Read().Status=="unsupported","unowned popup creation "+mode);
        }
    }
}
