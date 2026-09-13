using System;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Runs;

internal static class CombatIdentityFixtures
{
    private static CombatState Encounter()
    {
        var state=new CombatState();var player=new Player();state.Players.Add(player);
        for(int i=0;i<4;i++)player.PlayerCombatState!.Hand.Cards.Add(new CardModel{Owner=player,Id=new ModelId{Entry="BLUDGEON"}});
        var enemy=new Creature{CurrentHp=75,MaxHp=75,Monster=new MonsterModel{Id=new ModelId{Entry="DUMMY"}}};
        state.Enemies.Add(enemy);state.HittableEnemies.Add(enemy);return state;
    }
    private static PublicCombatActionRequest Play(string decision)
    {
        if(!PublicCombatActionRequest.TryCreate(decision,"play:0:0",out var request))throw new Exception("fixture action");
        return request;
    }
    internal static void Run(Action<bool,string> check)
    {
        NOverlayStack.Instance=null;RunManager.Instance=new();
        var first=Encounter();var second=Encounter();var manager=new CombatManager{State=first};CombatManager.Instance=manager;
        var reader=new PinnedPublicCombatDecisionReader();var applier=new PinnedPublicCombatActionApplier(reader);
        var a=reader.Read();check(a.Status==PublicDecisionStatus.Ready,"first native combat ready");
        check(applier.Apply(Play(a.DecisionId)).Outcome==PublicCombatActionApplyOutcome.Accepted,"first native action accepted");
        manager.State=second;reader.BeginObservedCombat();var b=reader.Read();
        check(applier.Apply(Play(b.DecisionId)).Outcome==PublicCombatActionApplyOutcome.Accepted,"second identical native combat accepts its own first action");
        check(a.DecisionId!=b.DecisionId,"different native combat objects have distinct decision identities");
        check(RunManager.Instance.ActionQueueSynchronizer.Actions.Count==2,"exactly one native action per combat");
        reader.BeginObservedCombat();check(reader.Read().DecisionId==b.DecisionId,"duplicate begin notification cannot renew action identity");
        check(applier.Apply(Play(b.DecisionId)).Outcome==PublicCombatActionApplyOutcome.AlreadyApplied,"same-combat replay remains blocked");
        check(applier.Apply(Play(a.DecisionId)).Outcome==PublicCombatActionApplyOutcome.AlreadyApplied,"old accepted action remains blocked");
        manager.State=first;check(reader.Read().DecisionId==a.DecisionId,"returning native object keeps its old identity");
        manager.State=second;manager.PlayerActionsDisabled=true;check(reader.Read().Status==PublicDecisionStatus.Waiting,"disabled actions wait");
        manager.PlayerActionsDisabled=false;check(reader.Read().DecisionId==b.DecisionId,"waiting interval does not renew identity");
        second.Players[0].PlayerCombatState!.Energy=2;var changed=reader.Read();
        check(changed.DecisionId!=b.DecisionId,"public-state change still changes decision");
        manager.State=Encounter();var third=reader.Read();check(third.DecisionId!=a.DecisionId&&third.DecisionId!=b.DecisionId,"ordinary combat also gets a distinct identity without event begin");
        check(applier.Apply(Play(changed.DecisionId)).Outcome==PublicCombatActionApplyOutcome.StaleDecision,"unaccepted prior-combat decision is stale");
        check(RunManager.Instance.ActionQueueSynchronizer.Actions.Count==2,"rejected old/replayed requests dispatch nothing");
        var anotherReader=new PinnedPublicCombatDecisionReader();check(anotherReader.Read().DecisionId!=third.DecisionId,"independent reader lifetimes cannot share a decision identity");
        RunManager.Instance.ActionQueueSynchronizer.ThrowAfterEnqueue=true;
        var service=new PublicCombatActionService(applier);
        check(service.Apply(Play(third.DecisionId)).IsBackendFault,"uncertain native enqueue reports backend fault");
        RunManager.Instance.ActionQueueSynchronizer.ThrowAfterEnqueue=false;reader.BeginObservedCombat();
        check(service.Apply(Play(reader.Read().DecisionId)).Outcome==PublicCombatActionApplyOutcome.AlreadyApplied,"begin notification cannot retry uncertain enqueue");
        check(RunManager.Instance.ActionQueueSynchronizer.Actions.Count==3,"uncertain native action queued at most once");
        CombatManager.Instance=null;NOverlayStack.Instance=null;
    }
}
