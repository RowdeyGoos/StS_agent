using System;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Runs;
internal static partial class Program {
    private static void TerminalCases() {
        foreach(string mode in new[]{"success","delayed_vote","delayed_win","no_effect","fault","abandoned","wrong_player","stale_gold","dispose_pending"}) {
            var f=new Fixture("TERMINAL");var manager=new RunManager{State=(RunState)f.Player.RunState};RunManager.Instance=manager;
            f.Model.Node=f.Room.Layout;manager.State.CurrentRoom=new MegaCrit.Sts2.Core.Rooms.EventRoom{LocalMutableEvent=f.Model,IsVictoryRoom=true};
            manager.ActChangeSynchronizer.Player=mode=="wrong_player"?new():f.Player;
            var completion=new TaskCompletionSource();GameAction? queued=null;int wins=0;
            if(mode is "delayed_vote" or "stale_gold" or "dispose_pending")manager.ActionQueueSynchronizer.GeneralHandler=a=>queued=a;
            manager.WinHandler=()=>{wins++;if(mode=="fault")return Task.FromException(new InvalidOperationException());
                if(mode=="delayed_win")return completion.Task;
                if(mode!="no_effect")f.Player.Creature.CurrentHp=0;
                if(mode=="abandoned")manager.IsAbandoned=true;return Task.CompletedTask;};
            f.Room.Layout.OptionButtons[0].Option.Callback=()=>{manager.ActChangeSynchronizer.SetLocalPlayerReady();return Task.CompletedTask;};
            bool cleanupFailed=false;
            try {
                var ready=f.Session.Read();Check(ready.Status=="ready","terminal dialogue available");
                var receipt=f.Session.Apply(ready.DecisionId,"choose:0");
                if(mode=="wrong_player"){Check(receipt.Outcome is "uncertain" or "accepted","foreign vote callback captured");Check(f.Session.Read().Status=="unsupported"&&wins==0,"foreign vote never executed");continue;}
                Check(receipt.Outcome=="accepted","terminal dialogue dispatched once");
                if(mode is "delayed_vote" or "stale_gold" or "dispose_pending") {
                    Check(f.Session.Read().Status=="waiting"&&wins==0,"queued vote not victory");
                    if(mode=="stale_gold")f.Player.Gold--;
                    if(mode=="dispose_pending"){try{f.Session.Dispose();}catch(InvalidOperationException){cleanupFailed=true;}}
                    bool rejected=false;try{((VoteToMoveToNextActAction)queued!).Execute();}catch(InvalidOperationException){rejected=true;}
                    if(mode!="delayed_vote"){Check(rejected&&wins==0,"expired vote guard prevents progression");continue;}
                }
                if(mode=="delayed_win"){Check(f.Session.Read().Status=="waiting","vote completion is not victory");f.Player.Creature.CurrentHp=0;completion.SetResult();}
                var result=f.Session.Read();
                Check(result.Status==(mode is "success" or "delayed_vote" or "delayed_win"?"complete":"unsupported"),"terminal exact result: "+mode);
                if(result.Status=="complete")Check(result.Phase=="run_won"&&result.PriorResults.Count==1&&result.PriorResults[0].Result=="run_won"&&!f.Map.IsOpen,"native victory without map handoff");
            } finally {
                try{f.Dispose();}catch(InvalidOperationException){cleanupFailed=true;}
                Check(cleanupFailed==(mode is not ("success" or "delayed_vote" or "delayed_win")),"terminal cleanup outcome: "+mode);
                RunManager.Instance=null;
            }
        }
    }
}
