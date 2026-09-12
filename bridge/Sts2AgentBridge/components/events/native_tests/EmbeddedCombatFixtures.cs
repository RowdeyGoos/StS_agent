using System;
using System.Reflection;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;

internal static partial class Program
{
    private static void PrepareEmbeddedCombat(Fixture f,CombatState state)
    {
        var layout=new NCombatEventLayout();
        layout.OptionButtons.AddRange(f.Room.Layout.OptionButtons);
        f.Room.Layout=layout;f.Model.Node=layout;f.Model.LayoutType=1;
        f.Model.SetPreparedCombat(state);NCombatRoom.Instance=layout.EmbeddedCombatRoom;
        ((RunState)f.Player.RunState).CurrentRoom=new EventRoom{LocalMutableEvent=f.Model};
    }
    private static void EmbeddedCombatCases()
    {
        foreach(var mode in new[]{"ok","missing_state","prepared_encounter","prepared_run","prepared_player","prepared_node","layout_kind","ordinary_layout","parent","resume","active_state","active_encounter","active_node","creation_mode","active_visuals"}) {
            using var f=new Fixture("EMBEDDED_COMBAT");
            var run=(RunState)f.Player.RunState;
            var encounter=new EncounterModel();
            var state=new CombatState{Encounter=encounter,RunState=run};state.Players.Add(f.Player);
            PrepareEmbeddedCombat(f,state);
            var node=NCombatRoom.Instance!;
            RunManager.Instance=new(){State=run};CombatManager.Instance=new(){State=null};
            var room=new CombatRoom{CombatState=state,ParentEventId=f.Model.Id,ShouldCreateCombat=false};
            if(mode=="missing_state")typeof(EventModel).GetField("_combatStateForCombatLayout",BindingFlags.Instance|BindingFlags.NonPublic)!.SetValue(f.Model,null);
            if(mode=="prepared_encounter")state.Encounter=new();
            if(mode=="prepared_run")state.RunState=new RunState();
            if(mode=="prepared_player")state.Players[0]=new();
            if(mode=="prepared_node")NCombatRoom.Instance=new();
            if(mode=="layout_kind")f.Model.LayoutType=0;
            if(mode=="ordinary_layout") {
                var layout=new NEventLayout();layout.OptionButtons.AddRange(f.Room.Layout.OptionButtons);
                f.Room.Layout=layout;f.Model.Node=layout;
            }
            if(mode=="parent")run.CurrentRoom=new EventRoom{LocalMutableEvent=new EventModel()};
            int entries=0;
            f.Model.CombatEntry=(_,_,_)=>{
                entries++;f.Model.Node=null;if(f.Room.Layout is NCombatEventLayout layout)layout.HasCombatStarted=true;
                if(mode=="active_state")room.CombatState=new CombatState{Encounter=encounter,RunState=run};
                if(mode=="active_encounter")state.Encounter=new();
                if(mode=="active_node")NCombatRoom.Instance=new();
                if(mode=="creation_mode")room.ShouldCreateCombat=true;
                run.CurrentRoom=room;CombatManager.Instance.State=room.CombatState;
                NCombatRoom.Instance!.SetVisuals(mode=="active_visuals"?new object():room);
            };
            f.Room.Layout.OptionButtons[0].Option.Callback=()=>{f.Model.EnterCombatWithoutExitingEvent(new EncounterModel(),Array.Empty<Reward>(),mode=="resume");return Task.CompletedTask;};
            var ready=f.Session.Read();Check(ready.Status=="ready","embedded setup ready: "+mode);
            Check(f.Session.Apply(ready.DecisionId,"choose:0").Outcome=="accepted","embedded option dispatch: "+mode);
            var result=f.Session.Read();
            if(mode!="ok") {
                Check(result.Status=="unsupported"&&result.ParentReconciled==0,"embedded mismatch stopped: "+mode);
                Check(entries==1&&f.Adapter.CombatScope is null,"failed validation never transfers bridge ownership: "+mode);continue;
            }
            Check(result.Phase=="combat_handoff"&&result.ParentReconciled==1,"distinct ignored encounter argument transfers exact prepared combat");
            var scope=f.Adapter.CombatScope!;f.Adapter.Dispose();
            Check(scope(),"embedded combat survives event disposal and native node clearing");
            room.ShouldCreateCombat=true;Check(!scope(),"late creation mode replacement stops lease");room.ShouldCreateCombat=false;
            var replacement=new CombatState{Encounter=encounter,RunState=run};replacement.Players.Add(f.Player);
            room.CombatState=replacement;CombatManager.Instance.State=replacement;Check(!scope(),"same-encounter replacement state stops lease");
            room.CombatState=state;CombatManager.Instance.State=state;
            NCombatRoom.Instance=new();NCombatRoom.Instance.SetVisuals(room);Check(!scope(),"same-room replacement node stops lease");NCombatRoom.Instance=node;
            node.SetVisuals(new object());Check(!scope(),"late visuals replacement stops lease");node.SetVisuals(room);
            state.Encounter=new();Check(!scope(),"late encounter replacement stops lease");state.Encounter=encounter;
            Check(scope(),"exact embedded lease retained");
        }
    }
}
