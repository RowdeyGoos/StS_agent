using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
using Sts2AgentBridge.Successors.GenericEventV6;
using Sts2AgentBridge.Successors.GenericEventV6.Native;

internal static partial class Program
{
    private static int _checks;
    static void Check(bool okay,string name){_checks++;if(!okay)throw new Exception(name);}
    static void Main(string[] args)
    {
        if(args.SequenceEqual(new[]{"--baseline"})){BaselineRetirement();return;}
        if(args.Length!=0)throw new ArgumentException("Unknown fixture mode.");
        foreach(string identity in new[]{"FIRST_EVENT","ANOTHER_EVENT","HELD_OUT_EVENT"})
            foreach(bool manual in new[]{false,true})
            {
                using var f=new Fixture(identity,manual:manual);
                var c=f.Start();Check(c.Status=="child","generic child "+identity);
                f.Finish(c);Check(f.Cards[0].CurrentUpgradeLevel==1,"exact effect");
                var parent=f.Session.Read();Check(parent.Phase=="proceed"&&parent.ParentReconciled==1,"parent callback completion");
                var apply=f.Session.Apply(parent.DecisionId,"choose:0");Check(apply.Outcome=="accepted","proceed accepted");
                Check(f.Session.Read().Status=="complete","map handoff");
            }
        using(var f=new Fixture("DELAYED",delayed:true))
        {
            var first=f.Start();Check(first.Status=="waiting","before child async wait");
            Check(first.ParentAttempted==1&&first.ParentAccepted==1&&first.Effects=="unverified","pre-child accounting");
            f.Gate.SetResult();var c=f.Session.Read();Check(c.Status=="child","async owned creation");f.Finish(c);
        }
        using(var f=new Fixture("UNSUPPORTED_COUNT",count:2))
        {var value=f.Start();Check(value.Status=="unsupported"&&value.ParentAccepted==1,"unsupported after accepted dispatch");}
        using(var f=new Fixture("CANCELABLE",cancelable:true))
        {Check(f.Start().Status=="unsupported","cancelable rejected");}
        using(var f=new Fixture("SHORTCUT",shortcut:true))
        {Check(f.Start().Status=="unsupported","request without screen never ordinary");}
        using(var f=new Fixture("WRONG_RUN",wrongRun:true))
        {Check(f.Start().Status=="unsupported","wrong creation runstate");}
        using(var f=new Fixture("CHANGED_DECK",mutateBefore:true))
        {Check(f.Start().Status=="unsupported","whole baseline deck unchanged admission");}
        using(var f=new Fixture("CALLBACK_FAULT",faultAfter:true))
        {
            var c=f.Start();f.SelectConfirm(c);
            Check(f.Session.ReadCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal).Value is CardSelectionV1Observation o&&o.Status=="unsupported","callback failure rejects matching effect");
        }
        using(var f=new Fixture("WRONG_LINEAGE"))
        {
            var c=f.Start();Check(f.Session.ReadCardChild(new string('f',64),c.Child!.ParentActionId,c.Child.Ordinal).Value is CardSelectionV1Observation o&&o.Status=="unsupported","wrong child parent");
            Check(f.Session.Read().Status=="unsupported","wrong lineage terminal");
        }
        using(var f=new Fixture("STALE_ACTION"))
        {
            var p=f.Session.Read();Check(f.Session.Apply(new string('f',64),"choose:0").Outcome=="stale_decision","stale outer action");
            Check(f.Session.Apply(p.DecisionId,"choose:7").Outcome=="illegal_action","illegal outer action");
            Check(f.Session.Read().ParentAttempted==0,"invalid actions no dispatch");
        }
        using(var f=new Fixture("REQUEST_DELAY",requestDelayed:true))
        {
            Check(f.Start().Status=="waiting","incomplete request may await screen");
            f.Gate.SetResult();var c=f.Session.Read();Check(c.Status=="child","asynchronous request scope retained");f.Finish(c);
        }
        using(var f=new Fixture("EFFECT_DELAY",effectDelayed:true))
        {
            var c=f.Start();f.SelectConfirm(c);var child=c.Child!;
            Check(f.Session.ReadCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal).Value is CardSelectionV1Observation,"matching delta cannot finish callback");
            f.Gate.SetResult();Check(f.Session.ReadCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal).Value is CardSelectionV1ResolvedResult,"callback task finishes effect gate");
        }
        using(var f=new Fixture("SECOND_REQUEST",secondRequest:true))
        {var c=f.Start();f.SelectConfirm(c);Check(IsUnsupported(f,c),"second request rejected");}
        using(var f=new Fixture("HELPER_MISMATCH",mismatchRequest:true))
        {var c=f.Start();f.SelectConfirm(c);Check(IsUnsupported(f,c),"helper selected originals must match even exact deck delta");}
        using(var f=new Fixture("CAUGHT_HELPER_FAULT",catchRequestFault:true))
        {var c=f.Start();f.SelectConfirm(c);Check(IsUnsupported(f,c),"caught helper fault cannot pass callback success");}
        using(var f=new Fixture("WRONG_PREFS",mismatchPrefs:true))
        {Check(f.Start().Status=="unsupported","all rule-bearing prefs consistent");}
        using(var f=new Fixture("WRONG_PLAYER",wrongPlayer:true))
        {Check(f.Start().Status=="unsupported","wrong command player");}
        using(var f=new Fixture("THROWING_CONTEXT",throwingGetter:true))
        {Check(f.Start().Status=="unsupported"&&CardSelectCmd.Calls==1,"observational getter failure still runs original");}
        using(var f=new Fixture("FOREIGN_SAME_OPTION"))
        {
            var button=f.Room.Layout.OptionButtons[0];button.DispatchOverride=()=>{};
            Check(f.Start().Status=="waiting","deferred controller without callback waits");
            _=button.Option.Chosen();Check(f.Session.Read().Status=="unsupported","same option outside dispatch scope cannot claim receipt");
        }
        using(var f=new Fixture("REPLACED_SCREEN"))
        {
            var c=f.Start();f.Overlays.Screens[0]=new NDeckUpgradeSelectScreen();
            Check(IsUnsupported(f,c),"replacement selector rejected");
        }
        using(var f=new Fixture("CANCELED_CALLBACK",delayed:true))
        {Check(f.Start().Status=="waiting","cancel fixture waiting");f.Gate.SetCanceled();Check(f.Session.Read().Status=="unsupported","canceled parent callback");}
        using(var f=new Fixture("WRONG_OPTION"))
        {
            var button=f.Room.Layout.OptionButtons[0];button.DispatchOverride=()=>new EventOption().Chosen();
            Check(f.Start().Status=="unsupported","foreign option under dispatch scope");
        }
        using(var f=new Fixture("CLOSED_INVOCATION"))
        {
            var first=f.Room.Layout.OptionButtons[0].Option;var real=first.Callback;
            first.Callback=()=>
            {
                _=Orphan(f);
                f.Room.Layout.OptionButtons.Clear();f.AddOption(new EventOption{TextKey="NEXT.OPTION",Callback=real});
                return Task.CompletedTask;
            };
            var next=f.Start();Check(next.Status=="ready"&&next.ParentReconciled==1,"ordinary page completion");
            Check(f.Session.Apply(next.DecisionId,"choose:0").Outcome=="accepted","new invocation accepted");
            var c=f.Session.Read();Check(c.Status=="child","new owned child");
            f.Gate.SetResult();Check(IsUnsupported(f,c),"closed async invocation never adopted by new child");
        }
        using(var f=new Fixture("TASK_RETENTION"))
        {
            var c=f.Start();var screen=(NDeckUpgradeSelectScreen)f.Overlays.Peek()!;
            int calls=screen.CardsSelectedCalls;
            screen.SelectionTask=Task.FromResult<IEnumerable<CardModel>>(new[]{f.Cards[1]});
            f.Finish(c);
            Check(screen.CardsSelectedCalls==calls,"retained selection task read once, replacement getter never adopted");
            Check(f.Cards[0].CurrentUpgradeLevel==1&&f.Cards[1].CurrentUpgradeLevel==0,"replacement task cannot change original effect");
        }
        RewardTests();
        RemovalTests();
        PatchOwnership();
        LifecycleTests();
        Check(_checks==745,"preserved predecessor assertion count");
        MultiUpgradeTests();
        TransformTests();
        ItemTests();
        Console.WriteLine("generic native checks: "+_checks);
    }
    internal static void RetireButton(NEventLayout layout,NEventOptionButton button)
    {
        layout.OptionButtons.Remove(button);
        button.InstanceValid=false;
    }
    internal static NEventOptionButton RetireBeforeChosen(NEventLayout layout)
    {
        var button=layout.OptionButtons[0];var option=button.Option;
        button.DispatchOverride=()=>{RetireButton(layout,button);_=option.Chosen();};
        return button;
    }
    private static void BaselineRetirement()
    {
        using var f=new RewardFixture("RETIRED_BASELINE",2,2,8);
        var button=f.Room.Layout.OptionButtons[0];var first=f.Session.Read();
        Check(first.Status=="ready","baseline initial option");
        Check(f.Session.Apply(first.DecisionId,"choose:0").Outcome=="accepted","baseline parent accepted");
        Check(f.Overlays.ScreenCount==1 && f.SelectCalls==0,"baseline chooser opened without card dispatch");
        RetireButton(f.Room.Layout,button);
        var result=f.Session.Read();
        Check(result.Status=="unsupported" && result.ChildEpisodes==0,"frozen freed-button rejection reproduced");
        Check(button.ForceClickCalls==1,"baseline one parent click");
        Console.WriteLine("generic lifecycle baseline checks: "+_checks);
    }
    private static void CompleteProceed(GenericEventV6Session session,NEventLayout layout)
    {
        var parent=session.Read();Check(parent.Phase=="proceed","retired callback reaches Proceed");
        var button=layout.OptionButtons[0];
        Check(session.Apply(parent.DecisionId,"choose:0").Outcome=="accepted","fresh Proceed clicked");
        Check(session.Read().Status=="complete" && button.ForceClickCalls==1,"retired callback map handoff once");
    }
    private static void LifecycleTests()
    {
        int preserved=_checks;Check(preserved==550,"all frozen native assertions retained");
        foreach(bool beforeChosen in new[]{false,true})
        {
            using(var f=new Fixture("RETIRED_UPGRADE"))
            {
                var button=beforeChosen?RetireBeforeChosen(f.Room.Layout):f.Room.Layout.OptionButtons[0];
                var p=f.Session.Read();Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","retired upgrade parent");
                if(!beforeChosen)RetireButton(f.Room.Layout,button);
                var c=f.Session.Read();Check(c.Status=="child","retired upgrade child");f.Finish(c);
                Check(button.ForceClickCalls==1 && f.OptionCalls==1,"retired upgrade never reclicked");CompleteProceed(f.Session,f.Room.Layout);
            }
            using(var f=new RemovalFixture("RETIRED_REMOVE",1,2,5))
            {
                var button=beforeChosen?RetireBeforeChosen(f.Room.Layout):f.Room.Layout.OptionButtons[0];
                var p=f.Session.Read();Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","retired removal parent");
                if(!beforeChosen)RetireButton(f.Room.Layout,button);
                var c=f.Session.Read();Check(c.Status=="child","retired removal child");f.Act(c,"select:1");f.Act(c,"preview");f.Act(c,"confirm");
                Check(f.Child(c) is CardSelectionV1ResolvedResult && button.ForceClickCalls==1,"retired removal resolves");CompleteProceed(f.Session,f.Room.Layout);
            }
            foreach(bool manual in new[]{false,true})using(var f=new RewardFixture("RETIRED_REWARD",1,2,8,manual))
            {
                var button=beforeChosen?RetireBeforeChosen(f.Room.Layout):f.Room.Layout.OptionButtons[0];
                var p=f.Session.Read();Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","retired reward parent");
                if(!beforeChosen)RetireButton(f.Room.Layout,button);
                var c=f.Session.Read();Check(c.Status=="child","retired reward child");
                var binding=(GenericEventV6Binding)typeof(GenericEventV6Hooks).GetField("_armed",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static)!.GetValue(null)!;
                Check(ReferenceEquals(binding.Controller,button)&&ReferenceEquals(binding.Context().ParentControllerIdentity,button),"same opaque retired receipt retained");
                f.Act(c,"select:1");if(manual)f.Act(c,"confirm");else f.Act(c,"select:0");
                Check(f.Child(c) is CardSelectionV1ResolvedResult && button.ForceClickCalls==1,"retired reward resolves");CompleteProceed(f.Session,f.Room.Layout);
            }
        }
        foreach(bool requestDelay in new[]{false,true})using(var f=new Fixture("RETIRED_DELAY",delayed:!requestDelay,requestDelayed:requestDelay))
        {
            var button=RetireBeforeChosen(f.Room.Layout);Check(f.Start().Status=="waiting","retired delayed request waits");f.Gate.SetResult();
            var c=f.Session.Read();Check(c.Status=="child","retired delayed request binds");f.Finish(c);Check(button.ForceClickCalls==1,"delayed no reclick");CompleteProceed(f.Session,f.Room.Layout);
        }
        using(var f=new Fixture("RETIRED_UPGRADE_COMPLETION",effectDelayed:true))
        {RetireBeforeChosen(f.Room.Layout);var c=f.Start();f.SelectConfirm(c);Check(f.Session.ReadCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal).Value is CardSelectionV1Observation w&&w.Status=="waiting","retired upgrade completion waits");f.Gate.SetResult();Check(f.Session.ReadCardChild(c.Child.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal).Value is CardSelectionV1ResolvedResult,"retired upgrade completion resolves");CompleteProceed(f.Session,f.Room.Layout);}
        using(var f=new RemovalFixture("RETIRED_REMOVE_DELAY",1,2,5,delayedCreation:true,delayedCompletion:true))
        {RetireBeforeChosen(f.Room.Layout);Check(f.Start().Status=="waiting","retired removal creation waits");f.CreationGate.SetResult();var c=f.Session.Read();f.Act(c,"select:1");f.Act(c,"preview");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation w&&w.Status=="waiting","retired removal completion waits");f.CompletionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult,"retired removal completes");CompleteProceed(f.Session,f.Room.Layout);}
        using(var f=new RewardFixture("RETIRED_REWARD_DELAY",1,2,8,delayedCreation:true,partialAdd:true,delayedCompletion:true))
        {RetireBeforeChosen(f.Room.Layout);Check(f.Start().Status=="waiting","retired reward creation waits");f.CreationGate.SetResult();var c=f.Session.Read();f.Act(c,"select:1");f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation w&&w.Status=="waiting","retired partial add waits");f.AdditionGate.SetResult();Check(f.Child(c) is CardSelectionV1Observation w2&&w2.Status=="waiting","retired reward callback waits");f.CompletionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult,"retired reward completes");CompleteProceed(f.Session,f.Room.Layout);}
        using(var f=new Fixture("RETIRED_ORDINARY"))
        {
            var button=f.Room.Layout.OptionButtons[0];var option=button.Option;
            option.Callback=()=>{f.AddOption(new EventOption{TextKey="NEXT.OPTION",Callback=()=>Task.CompletedTask});return Task.CompletedTask;};RetireBeforeChosen(f.Room.Layout);
            var next=f.Start();Check(next.Status=="ready"&&next.ParentReconciled==1&&button.ForceClickCalls==1,"ordinary retired parent reconciles");
        }
        LifecycleNegatives();
    }
    private static void LifecycleNegatives()
    {
        using(var f=new RewardFixture("INVALID_INITIAL",2,2,8))
        {var p=f.Session.Read();var button=f.Room.Layout.OptionButtons[0];button.InstanceValid=false;Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="unsupported"&&button.ForceClickCalls==0,"invalid predispatch button never clicked");}
        foreach(string mutation in new[]{"event","option","run","player","layout","map","deck","offer","duplicate"})using(var f=new RewardFixture("RETIRED_MUTATION",2,2,8))
        {
            var option=f.Room.Layout.OptionButtons[0].Option;RetireBeforeChosen(f.Room.Layout);
            f.BeforeCreate=()=>{
                switch(mutation){
                case "event": f.Model.Owner=null;break;
                case "option": option.TextKey="CHANGED";break;
                case "run": NRun.Instance=new NRun();break;
                case "player": f.Player.RunState=new FixtureRunState();break;
                case "layout": f.Room.Layout=new NEventLayout();break;
                case "map": NMapScreen.Instance=new NMapScreen();break;
                case "deck": f.BaselineCards[0].CurrentUpgradeLevel++;break;
                case "offer": f.ResultEntries[0].ModifiedCard=f.OfferCards[1];break;
                case "duplicate": f.DuplicateCreate=true;break;
                }
            };
            Check(f.Start().Status=="unsupported"&&f.SelectCalls==0,"retired binding rejects "+mutation);
        }
        using(var f=new RewardFixture("RETIRED_FOREIGN",2,2,8))
        {
            var button=f.Room.Layout.OptionButtons[0];var option=button.Option;
            button.DispatchOverride=()=>{RetireButton(f.Room.Layout,button);_=new EventOption().Chosen();_=option.Chosen();};
            Check(f.Start().Status=="unsupported"&&f.SelectCalls==0,"retired foreign callback cannot acquire scope");
        }
        using(var f=new RewardFixture("RETIRED_SCOPE_LOSS",2,2,8))
        {
            var clean=System.Threading.ExecutionContext.Capture()!;var button=f.Room.Layout.OptionButtons[0];var option=button.Option;
            button.DispatchOverride=()=>{RetireButton(f.Room.Layout,button);System.Threading.ExecutionContext.Run(clean,_=>{_=option.Chosen();},null);};
            Check(f.Start().Status=="unsupported"&&f.Overlays.ScreenCount==1&&f.SelectCalls==0,"context-lost callback opens chooser but is never adopted");
        }
        using(var f=new RewardFixture("RETIRED_LINEAGE",2,2,8))
        {RetireBeforeChosen(f.Room.Layout);var c=f.Start();Check(f.Session.ReadCardChild(c.Child!.ParentDecisionId,"choose:1",c.Child.Ordinal).Value is CardSelectionV1Observation o&&o.Status=="unsupported"&&f.SelectCalls==0,"retired receipt rejects foreign child lineage");}
    }

    private static bool IsUnsupported(Fixture f,GenericEventV6Observation c)
    {
        var child=c.Child!;
        for(int i=0;i<2;i++)
            if(f.Session.ReadCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal).Value is CardSelectionV1Observation o&&o.Status=="unsupported")return true;
        return false;
    }
    private static async Task Orphan(Fixture f)
    {await f.Gate.Task;await CardSelectCmd.FromDeckForUpgrade(f.Player,new CardSelectorPrefs(1,1));}
    private static void ForeignPrefix(){}
    private static void PatchOwnership()
    {
        var target=typeof(EventOption).GetMethod(nameof(EventOption.Chosen))!;
        var prefix=typeof(Program).GetMethod(nameof(ForeignPrefix),System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static)!;
        foreach(string owner in new[]{"fixture.foreign","sts2agent.generic_event_v6"})
        {
            var foreign=new HarmonyLib.Harmony(owner);
            using(var f=new Fixture("PATCH_INTRUSION"))
            {
                var c=f.Start();foreign.Patch(target,prefix:new HarmonyLib.HarmonyMethod(prefix));
                Check(IsUnsupported(f,c),"exact hook triple rejects intrusion "+owner);
            }
            Check(HarmonyLib.Harmony.GetPatchInfo(target)?.Prefixes.Any(p=>p.PatchMethod==prefix)==true,"precise cleanup preserves foreign hook "+owner);
            foreign.Unpatch(target,prefix);
        }
        var foreignBefore=new HarmonyLib.Harmony("fixture.preexisting");foreignBefore.Patch(target,prefix:new HarmonyLib.HarmonyMethod(prefix));
        bool rejected=false;try{using var hooks=new GenericEventV6Hooks();}catch(InvalidOperationException){rejected=true;}
        Check(rejected,"preexisting patch rejected");foreignBefore.Unpatch(target,prefix);
        bool failed=false;
        try{using var hooks=new GenericEventV6Hooks(n=>{if(n==2)throw new InvalidOperationException("partial install");},null);}
        catch(InvalidOperationException){failed=true;}
        Check(failed&&HarmonyLib.Harmony.GetPatchInfo(target)?.Owners.Count is null or 0,"partial installation rolls back exact owned hooks");
        int cleanupFailures=1;failed=false;
        try{using var hooks=new GenericEventV6Hooks(n=>throw new InvalidOperationException("partial install"),()=>{if(cleanupFailures-->0)throw new InvalidOperationException("cleanup failure");});}
        catch(AggregateException){failed=true;}
        Check(failed&&HarmonyLib.Harmony.GetPatchInfo(target)?.Prefixes.Count==1,"failed rollback retains discoverable owner lease");
        GenericEventV6Hooks.RecoverFailedInstallation();
        Check(HarmonyLib.Harmony.GetPatchInfo(target)?.Owners.Count is null or 0,"failed constructor cleanup recoverable");
        using(var hooks=new GenericEventV6Hooks())
        {
            bool protectedLease=false;try{GenericEventV6Hooks.RecoverFailedInstallation();}catch(InvalidOperationException){protectedLease=true;}
            Check(protectedLease,"failed-install recovery cannot close active successful lease");
        }
    }
    private sealed class FirstEvent:EventModel{}
    private sealed class SecondEvent:EventModel{}
    private sealed class HeldOutEvent:EventModel{}
    internal sealed class Fixture:IDisposable
    {
        internal readonly Player Player=new();
        internal readonly CardModel[] Cards={new(){IsUpgradable=true},new(){IsUpgradable=true},new(){IsUpgradable=false}};
        internal readonly EventModel Model;
        internal readonly NEventRoom Room=new();internal readonly NMapScreen Map=new();internal readonly NOverlayStack Overlays=new();
        internal readonly NRun Run=new();
        internal readonly TaskCompletionSource Gate=new();
        private readonly TaskCompletionSource<IEnumerable<CardModel>> _selected=new();
        private readonly Control _previewContainer=new(){Visible=false};
        private readonly NUpgradePreview _preview=new();
        private readonly NConfirmButton _confirm=new();
        internal GenericEventV6Session Session;
        internal int OptionCalls,SelectCalls,ConfirmCalls;
        internal Fixture(string name,bool manual=false,int count=1,bool cancelable=false,bool delayed=false,bool shortcut=false,bool wrongRun=false,bool mutateBefore=false,bool faultAfter=false,bool requestDelayed=false,bool effectDelayed=false,bool secondRequest=false,bool mismatchRequest=false,bool catchRequestFault=false,bool mismatchPrefs=false,bool wrongPlayer=false,bool throwingGetter=false)
        {
            for(int i=0;i<Cards.Length;i++){Cards[i].Id.Entry="Card_"+i;Player.Deck.Cards.Add(Cards[i]);}
            Model=name=="FIRST_EVENT"?new FirstEvent():name=="ANOTHER_EVENT"?new SecondEvent():new HeldOutEvent();
            Model.Owner=Player;
            Run.EventRoom=Room;Run.GlobalUi=new GlobalUiState{MapScreen=Map,Overlays=Overlays};
            NRun.Instance=Run;NEventRoom.Instance=Room;NMapScreen.Instance=Map;
            var option=new EventOption{TextKey=name+".OPTION"};
            option.Callback=async()=>
            {
                OptionCalls++;
                if(delayed)await Gate.Task;
                if(mutateBefore)Cards[2].CurrentUpgradeLevel++;
                if(throwingGetter)Player.ThrowRunState=true;
                IEnumerable<CardModel> selected;
                try {selected=await CardSelectCmd.FromDeckForUpgrade(wrongPlayer?new Player():Player,new CardSelectorPrefs(count,count,cancelable,manual));}
                catch when(catchRequestFault) {selected=new[]{Cards[0]};}
                foreach(var card in mismatchRequest?new[]{Cards[0]}:selected)card.CurrentUpgradeLevel++;
                if(effectDelayed)await Gate.Task;
                if(secondRequest)await CardSelectCmd.FromDeckForUpgrade(Player,new CardSelectorPrefs(1,1));
                if(faultAfter)throw new InvalidOperationException("fixture callback failure");
                Model.IsFinished=true;ShowProceed();
            };
            AddOption(option);
            CardSelectCmd.Calls=0;
            CardSelectCmd.Handler=async(player,prefs)=>
            {
                if(shortcut)return new[]{Cards[0]};
                if(requestDelayed)await Gate.Task;
                var screen=NDeckUpgradeSelectScreen.ShowScreen(Cards.Where(c=>c.IsUpgradable).ToArray(),
                    mismatchPrefs?prefs with {UnpoweredPreviews=true}:prefs,
                    wrongRun?new FixtureRunState():player.RunState);
                var values=await screen.CardsSelected();
                if(catchRequestFault)throw new InvalidOperationException("fixture request failure");
                return mismatchRequest?new[]{Cards[1]}:values;
            };
            NDeckUpgradeSelectScreen.Factory=(cards,prefs,run)=>CreateScreen(cards);
            Session=new GenericEventV6Session(new PinnedGenericEventV6NativeAdapter(),new string('a',32));
        }
        internal void AddOption(EventOption option)
        {
            var button=new NEventOptionButton{Option=option,Event=Model};
            button.Bind("%Text",new MegaRichTextLabel{Text="Native option"});Room.Layout.OptionButtons.Add(button);
        }
        private void ShowProceed()
        {
            Room.Layout.OptionButtons.Clear();
            AddOption(new EventOption{TextKey="PROCEED",IsProceed=true,Callback=()=>{OptionCalls++;Map.IsOpen=true;Map.IsTravelEnabled=true;return Task.CompletedTask;}});
        }
        private NDeckUpgradeSelectScreen CreateScreen(IReadOnlyList<CardModel> cards)
        {
            var screen=new NDeckUpgradeSelectScreen{SelectionTask=_selected.Task};var grid=new NCardGrid();
            int rows=(cards.Count+3)/4;float content=rows*300+(rows-1)*40;float scrollHeight=content+400;
            grid.Size=new Vector2(1000,scrollHeight+100);grid.Bind("%ScrollContainer",new Control{Size=new Vector2(1000,scrollHeight),Position=new Vector2(0,50)});
            foreach(var card in cards)
            {
                var material=new ShaderMaterial();var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{CardHighlight=new NCardHighlight{Material=material}},Hitbox=new NClickableControl()};
                holder.Selected=()=>{SelectCalls++;material.Width=BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits);_preview.Card=card;_previewContainer.Visible=true;};
                grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            screen.Bind("%CardGrid",grid);_previewContainer.Bind("UpgradePreview",_preview);_previewContainer.Bind("Confirm",_confirm);screen.Bind("%UpgradeSinglePreviewContainer",_previewContainer);
            _confirm.Clicked=()=>{ConfirmCalls++;Overlays.Screens.Clear();screen.Visible=false;_selected.SetResult(new[]{_preview.Card!});};
            Overlays.Screens.Add(screen);return screen;
        }
        internal GenericEventV6Observation Start()
        {
            var value=Session.Read();Check(value.Status=="ready","ready native option");
            Check(Session.Apply(value.DecisionId,"choose:0").Outcome=="accepted","parent accepted");return Session.Read();
        }
        internal void SelectConfirm(GenericEventV6Observation c)
        {
            var child=c.Child!;var o=(CardSelectionV1Observation)Session.ReadCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal).Value;
            Check(o.LegalActions.Contains("select:0"),"initial real child select");
            Check(Session.ApplyCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal,o.DecisionId,"select:0").Value is CardSelectionV1DispatchReceipt,"select dispatch");
            o=(CardSelectionV1Observation)Session.ReadCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal).Value;
            Check(o.LegalActions.Contains("confirm"),"original preview confirm");
            Check(Session.ApplyCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal,o.DecisionId,"confirm").Value is CardSelectionV1DispatchReceipt,"confirm dispatch");
        }
        internal void Finish(GenericEventV6Observation c)
        {
            SelectConfirm(c);var child=c.Child!;
            var r=Session.ReadCardChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal).Value;
            Check(r is CardSelectionV1ResolvedResult,"actual frozen child resolved");
        }
        public void Dispose(){Session.Dispose();CardSelectCmd.Selector=null;NRun.Instance=null;NEventRoom.Instance=null;NMapScreen.Instance=null;}
    }
    private static void RemovalTests()
    {
        foreach(var spec in new[]{("FIRST_REMOVAL",2,2,new[]{1,0},false),("ANOTHER_REMOVAL",1,3,new[]{2,0},true),("HELD_OUT_REMOVAL",1,3,new[]{3,1,0},false),("MAX_REMOVAL",8,8,Enumerable.Range(0,8).Reverse().ToArray(),false)})
        {
            using var f=new RemovalFixture(spec.Item1,spec.Item2,spec.Item3);var c=f.Start();Check(c.Status=="child","removal admitted");
            foreach(int index in spec.Item4)f.Act(c,"select:"+index);
            if(spec.Item5)f.Act(c,"preview");
            f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult,"removal resolved");
            Check(f.Player.Deck.Cards.SequenceEqual(f.Cards.Where((_,i)=>!spec.Item4.Contains(i))),"exact original removal and survivor order");
            var p=f.Session.Read();Check(p.Phase=="proceed","removal parent continued");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","removal map");
        }
        using(var f=new RemovalFixture("DELAYED",1,3,delayedCreation:true,delayedCompletion:true))
        {Check(f.Start().Status=="waiting","deferred removal creation");f.CreationGate.SetResult();var c=f.Session.Read();Check(c.Status=="child","delayed creation bound");f.Act(c,"select:1");f.Act(c,"preview");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="waiting","effect alone awaits callback");f.CompletionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult,"delayed callback completed");}
        using(var f=new RemovalFixture("WRONG_REQUEST",1,1))
        {f.RequestResult=_=>new[]{f.Cards[1]};var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","wrong request original");}
        using(var f=new RemovalFixture("DUPLICATE_REQUEST_RESULT",1,2))
        {f.RequestResult=v=>new[]{v.First(),v.First()};var c=f.Start();f.Act(c,"select:0");f.Act(c,"preview");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","duplicate request originals");}
        using(var f=new RemovalFixture("PREVIEW_FOREIGN",1,1))
        {var c=f.Start();f.Act(c,"select:0");((NPreviewCardHolder)f.PreviewCards.Children[0]).CardNode.Model=f.Cards[1];Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","foreign preview original before confirm");Check(f.ConfirmCalls==0,"foreign preview no confirm");}
        using(var f=new RemovalFixture("PREVIEW_REPLACE",1,1))
        {var c=f.Start();f.Act(c,"select:0");_=f.Child(c);f.PreviewCards.Children[0]=new NPreviewCardHolder{CardNode=new NCard{Model=f.Cards[0]}};Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","replacement preview holder");}
        using(var f=new RemovalFixture("EXTRA_DELTA",1,1))
        {f.AfterEffect=()=>f.Cards[2].CurrentUpgradeLevel++;var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","unrelated upgrade delta");}
        using(var f=new RemovalFixture("DUP_SCREEN",1,1)){f.DuplicateCreate=true;Check(f.Start().Status=="unsupported","duplicate removal creation");}
        using(var f=new RemovalFixture("WRONG_PLAYER",1,1)){f.WrongPlayer=true;Check(f.Start().Status=="unsupported","wrong removal player");}
        using(var f=new RemovalFixture("PREF_CHANGE",1,1)){f.ChangePrefs=true;Check(f.Start().Status=="unsupported","changed removal prefs");}
        using(var f=new RemovalFixture("BASELINE_CHANGE",1,1)){f.BeforeCreate=()=>f.Cards[9].CurrentUpgradeLevel++;Check(f.Start().Status=="unsupported","removal entire baseline unchanged");}
        using(var f=new RemovalFixture("SHORTCUT",1,1)){f.Shortcut=true;Check(f.Start().Status=="unsupported","removal shortcut unsupported");}
        using(var f=new RemovalFixture("FAULT",1,1)){f.FaultRequest=true;var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","removal request fault");}
        using(var f=new RemovalFixture("PARTIAL_PREVIEW",1,3))
        {
            var c=f.Start();f.Act(c,"select:2");f.Act(c,"select:0");f.Act(c,"select:1");
            var tail=f.PreviewCards.Children.Skip(1).ToArray();f.PreviewCards.Children.RemoveRange(1,2);
            Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="waiting","partial preview construction waits without binding subset");
            f.PreviewCards.Children.AddRange(tail);f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult,"complete deferred preview resolves");
        }
        using(var f=new RemovalFixture("SCREEN_ENUM_BOUND",1,1))
        {
            int yielded=0;f.ScreenResult=_=>Many();f.RequestResult=_=>new[]{f.Cards[0]};
            IEnumerable<CardModel> Many(){for(int i=0;i<10;i++){yielded++;yield return f.Cards[i];}}
            var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported"&&yielded==2,"screen enumerable bounded admitted max+1");
        }
        using(var f=new RemovalFixture("REQUEST_ENUM_BOUND",1,1))
        {
            int yielded=0;f.IgnoreRequestForEffect=true;f.RequestResult=_=>Many();
            IEnumerable<CardModel> Many(){for(int i=0;i<10;i++){yielded++;yield return f.Cards[i];}}
            var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported"&&yielded==2,"request enumerable bounded admitted max+1");
        }
        using(var f=new RemovalFixture("FAULT_CALLBACK",1,1)){f.FaultCallback=true;var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","removal callback fault despite matching effect");}
        using(var f=new RemovalFixture("AFTER_CREATION_CONTEXT",1,1)){f.AfterCreate=()=>NEventRoom.Instance=new NEventRoom();Check(f.Start().Status=="unsupported","context after creation rejected");}
        using(var f=new RemovalFixture("WORKER_CHOSEN",1,1))
        {var button=f.Room.Layout.OptionButtons[0];button.DispatchOverride=()=>Task.Run(()=>{_=button.Option.Chosen();}).GetAwaiter().GetResult();Check(f.Start().Status=="unsupported","worker-thread inherited dispatch rejected");}
    }
    private sealed class FirstRemovalEvent:EventModel{}
    private sealed class AnotherRemovalEvent:EventModel{}
    private sealed class HeldOutRemovalEvent:EventModel{}
    internal sealed class RemovalFixture:IDisposable
    {
        internal readonly Player Player=new();
        internal readonly CardModel[] Cards;
        internal readonly EventModel Model;
        internal readonly NEventRoom Room=new();internal readonly NMapScreen Map=new();internal readonly NOverlayStack Overlays=new();
        internal readonly NRun Run=new();
        internal readonly TaskCompletionSource CreationGate=new(),CompletionGate=new();
        internal readonly TaskCompletionSource<IEnumerable<CardModel>> SelectedTask=new();
        internal readonly Control PreviewContainer=new(){Visible=false},PreviewCards=new();
        internal readonly NConfirmButton PreviewButton=new(){IsEnabled=false},ConfirmButton=new();
        internal readonly List<CardModel> Selected=new();
        internal NDeckCardSelectScreen Screen=null!;
        internal NCardGrid Grid=null!;
        internal GenericEventV6Session Session;
        internal PinnedGenericEventV6NativeAdapter Adapter;
        internal int OptionCalls,SelectCalls,PreviewCalls,ConfirmCalls;
        internal Func<IEnumerable<CardModel>,IEnumerable<CardModel>>? RequestResult,ScreenResult;
        internal bool IgnoreRequestForEffect=false;
        internal Action? BeforeCreate,AfterCreate,AfterEffect;
        internal bool FaultRequest,FaultCallback,DuplicateCreate,WrongPlayer,ChangePrefs,Shortcut;
        internal RemovalFixture(string name,int minSelect,int maxSelect,int domainCount=10,bool delayedCreation=false,bool delayedCompletion=false)
        {
            Cards=Enumerable.Range(0,domainCount).Select(i=>new CardModel{IsRemovable=true,IsUpgradable=true}).ToArray();
            for(int i=0;i<Cards.Length;i++){Cards[i].Id.Entry="Card_"+i;Player.Deck.Cards.Add(Cards[i]);}
            Model=name=="FIRST_REMOVAL"?new FirstRemovalEvent():name=="ANOTHER_REMOVAL"?new AnotherRemovalEvent():new HeldOutRemovalEvent();Model.Owner=Player;
            Run.EventRoom=Room;Run.GlobalUi=new GlobalUiState{MapScreen=Map,Overlays=Overlays};NRun.Instance=Run;NEventRoom.Instance=Room;NMapScreen.Instance=Map;
            AddOption(new EventOption{TextKey=name+".OPTION",Callback=async()=>{
                OptionCalls++;
                var selected=await CardSelectCmd.FromDeckForRemoval(WrongPlayer?new Player():Player,new CardSelectorPrefs(minSelect,maxSelect),null);
                foreach(var card in IgnoreRequestForEffect?Selected:selected)Player.Deck.Cards.Remove(card);
                AfterEffect?.Invoke();
                if(delayedCompletion)await CompletionGate.Task;
                if(FaultCallback)throw new InvalidOperationException("callback fault");
                Model.IsFinished=true;ShowProceed();
            }});
            CardSelectCmd.Selector=null;CardSelectCmd.Calls=0;
            CardSelectCmd.RemovalHandler=async(player,prefs,filter)=>{
                if(delayedCreation)await CreationGate.Task;
                BeforeCreate?.Invoke();
                if(Shortcut)return new[]{Cards[0]};
                var originals=Cards.Where(c=>c.IsRemovable&&(filter?.Invoke(c)??true)).ToArray();
                var screen=NDeckCardSelectScreen.Create(originals,ChangePrefs?prefs with{UnpoweredPreviews=true}:prefs);
                if(DuplicateCreate)NDeckCardSelectScreen.Create(originals,prefs);
                AfterCreate?.Invoke();
                Overlays.Screens.Add(screen);
                var selected=await screen.CardsSelected();
                if(FaultRequest)throw new InvalidOperationException("request fault");
                return RequestResult?.Invoke(selected)??selected;
            };
            NDeckCardSelectScreen.Factory=(cards,prefs)=>CreateScreen(cards,prefs);
            Adapter=new PinnedGenericEventV6NativeAdapter();Session=new GenericEventV6Session(Adapter,new string('b',32));
        }
        private void AddOption(EventOption option)
        {var button=new NEventOptionButton{Option=option,Event=Model};button.Bind("%Text",new MegaRichTextLabel{Text="Removal native option"});Room.Layout.OptionButtons.Add(button);}
        private void ShowProceed()
        {Room.Layout.OptionButtons.Clear();AddOption(new EventOption{TextKey="PROCEED",IsProceed=true,Callback=()=>{OptionCalls++;Map.IsOpen=true;Map.IsTravelEnabled=true;return Task.CompletedTask;}});}
        private NDeckCardSelectScreen CreateScreen(IReadOnlyList<CardModel> cards,CardSelectorPrefs prefs)
        {
            Screen=new NDeckCardSelectScreen{SelectionTask=SelectedTask.Task};Grid=new NCardGrid();
            int rows=(cards.Count+3)/4;float content=rows*300+(rows-1)*40;float height=content+400;
            Grid.Size=new Vector2(1000,height+100);Grid.Bind("%ScrollContainer",new Control{Size=new Vector2(1000,height),Position=new Vector2(0,50)});
            foreach(var card in cards)
            {
                var material=new ShaderMaterial();var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card,CardHighlight=new NCardHighlight{Material=material}},Hitbox=new NClickableControl()};
                holder.Selected=()=>{
                    SelectCalls++;Selected.Add(card);material.Width=BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits);
                    PreviewButton.IsEnabled=prefs.MinSelect!=prefs.MaxSelect&&Selected.Count>=prefs.MinSelect;
                    if(Selected.Count==prefs.MaxSelect)OpenPreview();
                };Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            Screen.Bind("%CardGrid",Grid);Screen.Bind("%PreviewContainer",PreviewContainer);Screen.Bind("%Confirm",PreviewButton);
            PreviewContainer.Bind("%Cards",PreviewCards);PreviewContainer.Bind("%PreviewConfirm",ConfirmButton);
            PreviewButton.Clicked=OpenPreview;
            ConfirmButton.Clicked=()=>{ConfirmCalls++;Overlays.Screens.Clear();Screen.Visible=false;SelectedTask.SetResult(ScreenResult?.Invoke(Selected)??Selected.ToArray());};
            return Screen;
        }
        private void OpenPreview()
        {
            PreviewCalls++;PreviewContainer.Visible=true;PreviewCards.Children.Clear();
            foreach(var original in Selected)PreviewCards.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=original}});
            foreach(var holder in Grid.CurrentlyDisplayedCardHolders)((ShaderMaterial)holder.CardNode.CardHighlight.Material!).Width=0;
        }
        internal GenericEventV6Observation Start()
        {var value=Session.Read();Check(value.Status=="ready","removal ready");Check(Session.Apply(value.DecisionId,"choose:0").Outcome=="accepted","removal parent dispatch");return Session.Read();}
        internal ICardSelectionV1ReadValue Child(GenericEventV6Observation c)=>Session.ReadCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal).Value;
        internal CardSelectionV1Observation Act(GenericEventV6Observation c,string action)
        {var o=(CardSelectionV1Observation)Child(c);Check(o.LegalActions.Contains(action),"removal legal "+action);Check(Session.ApplyCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,action).Value is CardSelectionV1DispatchReceipt,"removal dispatch "+action);return o;}
        public void Dispose(){Session.Dispose();CardSelectCmd.Selector=null;NRun.Instance=null;NEventRoom.Instance=null;NMapScreen.Instance=null;}
    }

    private static void RewardTests()
    {
        foreach(var spec in new[]{("FIRST_REWARD",1,2,new[]{2,0},false,false),("ANOTHER_REWARD",1,3,new[]{3,1},true,true),("HELD_OUT_REWARD",1,3,new[]{3,1,0},false,true),("MAX_REWARD",8,8,Enumerable.Range(0,8).Reverse().ToArray(),false,false),("MANUAL_MAX",8,8,Enumerable.Range(0,8).Reverse().ToArray(),true,false)})
        {
            using var f=new RewardFixture(spec.Item1,spec.Item2,spec.Item3,9,spec.Item5,spec.Item6);var c=f.Start();Check(c.Status=="child","reward admitted");
            foreach(int index in spec.Item4)f.Act(c,"select:"+index);
            if(spec.Item5)f.Act(c,"confirm");
            Check(f.Child(c) is CardSelectionV1ResolvedResult,"reward resolved");
            Check(f.Player.Deck.Cards.SequenceEqual(f.BaselineCards.Concat(spec.Item4.Select(i=>f.DisplayedOffers[i]))),"exact selected originals added after sorted slots");
            var p=f.Session.Read();Check(p.Phase=="proceed","reward parent continued");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","reward map");
        }
        using(var f=new RewardFixture("DELAY",1,2,delayedCreation:true,partialAdd:true,delayedCompletion:true))
        {Check(f.Start().Status=="waiting","reward creation delayed");f.CreationGate.SetResult();var c=f.Session.Read();f.Act(c,"select:2");f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="waiting"&&f.Player.Deck.Cards.Count==4,"partial add waits");f.AdditionGate.SetResult();Check(f.Child(c) is CardSelectionV1Observation wait&&wait.Status=="waiting","complete delta waits Chosen");f.CompletionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult,"delayed reward resolves");}
        using(var f=new RewardFixture("WRONG_OWNER",1,1)){f.OfferCards[0].Owner=new Player();Check(f.Start().Status=="unsupported","offer owner mismatch");}
        using(var f=new RewardFixture("WRONG_RUN",1,1)){f.OfferCards[0].RunOverride=new FixtureRunState();Check(f.Start().Status=="unsupported","offer run mismatch");}
        using(var f=new RewardFixture("BASELINE_OFFER",1,1)){f.ResultEntries[0]=new CardCreationResult(f.BaselineCards[0]);Check(f.Start().Status=="unsupported","preexisting baseline offer");}
        using(var f=new RewardFixture("DUP_ENTRY",1,1)){f.ResultEntries[1]=f.ResultEntries[0];Check(f.Start().Status=="unsupported","duplicate result entry");}
        using(var f=new RewardFixture("DUP_CARD",1,1)){f.ResultEntries[1]=new CardCreationResult(f.OfferCards[0]);Check(f.Start().Status=="unsupported","duplicate effective card");}
        using(var f=new RewardFixture("NULL_CONTEXT",1,1)){f.NullContext=true;Check(f.Start().Status=="unsupported","null choice context");}
        using(var f=new RewardFixture("WRONG_PLAYER",1,1)){f.WrongPlayer=true;Check(f.Start().Status=="unsupported","wrong explicit request player");}
        using(var f=new RewardFixture("REPLACED_LIST",1,1)){f.ReplaceList=true;Check(f.Start().Status=="unsupported","creation copied request list rejected");}
        using(var f=new RewardFixture("CHANGE_PREF",1,1)){f.ChangePrefs=true;Check(f.Start().Status=="unsupported","reward prefs changed");}
        using(var f=new RewardFixture("MUTATE_PROJECTION",1,1)){f.BeforeCreate=()=>f.ResultEntries[0].ModifiedCard=new CardModel{Owner=f.Player};Check(f.Start().Status=="unsupported","changed effective card between request creation");}
        using(var f=new RewardFixture("MUTATE_ENTRY",1,1)){f.BeforeReturn=()=>f.ResultEntries[0]=new CardCreationResult(f.OfferCards[0]);Check(f.Start().Status=="unsupported","entry replaced during creation");}
        using(var f=new RewardFixture("LATE_PROJECTION",1,2)){var c=f.Start();f.ResultEntries[0].ModifiedCard=f.OfferCards[1];Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","projection rechecked child lifetime");}
        using(var f=new RewardFixture("PLAIN_GRID",1,1)){f.PlainOverload=true;Check(f.Start().Status=="unsupported","plain CardModel overload never admitted");}
        using(var f=new RewardFixture("DUP_CREATE",1,1)){f.DuplicateCreate=true;Check(f.Start().Status=="unsupported","duplicate reward screen");}
        using(var f=new RewardFixture("SHORTCUT",1,1)){f.Shortcut=true;Check(f.Start().Status=="unsupported","selectorless reward shortcut");}
        using(var f=new RewardFixture("WRONG_RESULT",1,1)){f.RequestResult=_=>new[]{f.OfferCards[1]};var c=f.Start();f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","wrong reward task original");}
        using(var f=new RewardFixture("EARLY_ADDITION",1,2)){var c=f.Start();f.Player.Deck.Cards.Add(f.OfferCards[0]);Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","early add before submission");}
        using(var f=new RewardFixture("EXTRA_ADDITION",1,1)){f.AfterEffect=()=>f.Player.Deck.Cards.Add(f.OfferCards[9]);var c=f.Start();f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","unselected extra add");}
        using(var f=new RewardFixture("BASELINE_UPGRADE",1,1)){f.AfterEffect=()=>f.BaselineCards[0].CurrentUpgradeLevel++;var c=f.Start();f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","baseline upgraded during add");}
        using(var f=new RewardFixture("REVOKED_PARTIAL",1,2,partialAdd:true)){var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");_=f.Child(c);f.Player.Deck.Cards.Remove(f.OfferCards[0]);Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","partial add revoked");}
        using(var f=new RewardFixture("FAULT_REQUEST",1,1)){f.FaultRequest=true;var c=f.Start();f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","reward request fault");}
        using(var f=new RewardFixture("FAULT_CHOSEN",1,1)){f.FaultCallback=true;var c=f.Start();f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","reward Chosen fault despite add");}
    }
    private sealed class FirstRewardEvent:EventModel{}
    private sealed class AnotherRewardEvent:EventModel{}
    private sealed class HeldOutRewardEvent:EventModel{}
    internal sealed class RewardFixture:IDisposable
    {
        internal readonly Player Player=new();
        internal readonly CardModel[] BaselineCards,OfferCards;
        internal readonly List<CardCreationResult> ResultEntries;
        internal CardModel[] DisplayedOffers=Array.Empty<CardModel>();
        internal readonly EventModel Model;
        internal readonly NEventRoom Room=new();internal readonly NMapScreen Map=new();internal readonly NOverlayStack Overlays=new();
        internal readonly NRun Run=new();
        internal readonly TaskCompletionSource CreationGate=new(),AdditionGate=new(),CompletionGate=new();
        internal readonly TaskCompletionSource<IEnumerable<CardModel>> SelectedTask=new();
        internal readonly NConfirmButton ConfirmButton=new(){IsEnabled=false};
        internal readonly List<CardModel> Selected=new();
        internal NSimpleCardSelectScreen Screen=null!;internal NCardGrid Grid=null!;
        internal GenericEventV6Session Session;internal PinnedGenericEventV6NativeAdapter Adapter;
        internal int OptionCalls,SelectCalls,ConfirmCalls;
        internal Func<IEnumerable<CardModel>,IEnumerable<CardModel>>? RequestResult=null,ScreenResult=null;
        internal Action? BeforeRequest=null,BeforeCreate=null,BeforeReturn=null,BeforeEffect=null,AfterFirstAdd=null,AfterEffect=null;
        internal bool WrongPlayer=false,NullContext=false,ChangePrefs=false,Shortcut=false,FaultRequest=false,FaultCallback=false,PlainOverload=false,DuplicateCreate=false,ReplaceList=false,IgnoreRequestForEffect=false,NoAddition=false;
        internal RewardFixture(string name,int minSelect,int maxSelect,int domainCount=10,bool manual=false,bool sortedOffers=false,bool delayedCreation=false,bool partialAdd=false,bool delayedCompletion=false,string? nonce=null)
        {
            BaselineCards=Enumerable.Range(0,3).Select(i=>new CardModel{Owner=Player}).ToArray();
            for(int i=0;i<BaselineCards.Length;i++){BaselineCards[i].Id.Entry="Baseline_"+i;Player.Deck.Cards.Add(BaselineCards[i]);}
            OfferCards=Enumerable.Range(0,domainCount).Select(i=>new CardModel{Owner=Player}).ToArray();
            for(int i=0;i<OfferCards.Length;i++)OfferCards[i].Id.Entry="Reward_"+i;
            ResultEntries=OfferCards.Select(c=>new CardCreationResult(c)).ToList();
            Model=name=="FIRST_REWARD"?new FirstRewardEvent():name=="ANOTHER_REWARD"?new AnotherRewardEvent():new HeldOutRewardEvent();Model.Owner=Player;
            Run.EventRoom=Room;Run.GlobalUi=new GlobalUiState{MapScreen=Map,Overlays=Overlays};NRun.Instance=Run;NEventRoom.Instance=Room;NMapScreen.Instance=Map;
            AddOption(new EventOption{TextKey=name+".OPTION",Callback=async()=>{
                OptionCalls++;BeforeRequest?.Invoke();
                var prefs=new CardSelectorPrefs(minSelect,maxSelect,false,manual);
                if(sortedOffers)prefs=prefs with{Comparison=(a,b)=>string.CompareOrdinal(b.Id.Entry,a.Id.Entry)};
                var chosen=await CardSelectCmd.FromSimpleGridForRewards(NullContext?null!:new BlockingPlayerChoiceContext(),ResultEntries,WrongPlayer?new Player():Player,prefs);
                var selected=(IgnoreRequestForEffect?Selected:chosen).ToArray();BeforeEffect?.Invoke();
                if(!NoAddition)
                {
                    for(int i=0;i<selected.Length;i++)
                    {
                        Player.Deck.Cards.Add(selected[i]);
                        if(i==0&&partialAdd){AfterFirstAdd?.Invoke();await AdditionGate.Task;}
                    }
                }
                AfterEffect?.Invoke();if(delayedCompletion)await CompletionGate.Task;
                if(FaultCallback)throw new InvalidOperationException("reward callback fault");
                Model.IsFinished=true;ShowProceed();
            }});
            CardSelectCmd.Selector=null;CardSelectCmd.Calls=0;
            CardSelectCmd.RewardHandler=async(context,cards,player,prefs)=>{
                if(delayedCreation)await CreationGate.Task;BeforeCreate?.Invoke();
                if(Shortcut)return new[]{OfferCards[0]};
                if(PlainOverload){var plain=NSimpleCardSelectScreen.Create(OfferCards,prefs);Overlays.Screens.Add(plain);return new[]{OfferCards[0]};}
                var screen=NSimpleCardSelectScreen.Create(ReplaceList?cards.ToList():cards,ChangePrefs?prefs with{UnpoweredPreviews=true}:prefs);
                if(DuplicateCreate)NSimpleCardSelectScreen.Create(cards,prefs);
                Overlays.Screens.Add(screen);var selected=await screen.CardsSelected();
                if(FaultRequest)throw new InvalidOperationException("reward request fault");
                return RequestResult?.Invoke(selected)??selected;
            };
            NSimpleCardSelectScreen.Factory=(cards,prefs)=>CreateScreen(cards,prefs);
            Adapter=new PinnedGenericEventV6NativeAdapter();Session=new GenericEventV6Session(Adapter,nonce??new string('c',32));
        }
        private void AddOption(EventOption option)
        {var button=new NEventOptionButton{Option=option,Event=Model};button.Bind("%Text",new MegaRichTextLabel{Text="Reward native option"});Room.Layout.OptionButtons.Add(button);}
        private void ShowProceed()
        {Room.Layout.OptionButtons.Clear();AddOption(new EventOption{TextKey="PROCEED",IsProceed=true,Callback=()=>{OptionCalls++;Map.IsOpen=true;Map.IsTravelEnabled=true;return Task.CompletedTask;}});}
        private NSimpleCardSelectScreen CreateScreen(IReadOnlyList<CardCreationResult> cards,CardSelectorPrefs prefs)
        {
            Screen=new NSimpleCardSelectScreen{SelectionTask=SelectedTask.Task};Grid=new NCardGrid();
            var offered=cards.Select(c=>c.Card).ToList();if(prefs.Comparison is not null)offered.Sort(prefs.Comparison);DisplayedOffers=offered.ToArray();
            int rows=(offered.Count+3)/4;float content=rows*300+(rows-1)*40;float height=content+400;
            Grid.Size=new Vector2(1000,height+100);Grid.Bind("%ScrollContainer",new Control{Size=new Vector2(1000,height),Position=new Vector2(0,50)});
            foreach(var card in offered)
            {
                var material=new ShaderMaterial();var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card,CardHighlight=new NCardHighlight{Material=material}},Hitbox=new NClickableControl()};
                holder.Selected=()=>{
                    SelectCalls++;Selected.Add(card);material.Width=BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits);
                    ConfirmButton.IsEnabled=prefs.RequireManualConfirmation&&Selected.Count>=prefs.MinSelect;
                    if(!prefs.RequireManualConfirmation&&Selected.Count>=prefs.MaxSelect)CompleteSelection();
                };Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            Screen.Bind("%CardGrid",Grid);Screen.Bind("%Confirm",ConfirmButton);
            ConfirmButton.Clicked=()=>{ConfirmCalls++;CompleteSelection();};BeforeReturn?.Invoke();return Screen;
        }
        private void CompleteSelection()
        {Overlays.Screens.Clear();Screen.Visible=false;SelectedTask.SetResult(ScreenResult?.Invoke(Selected)??Selected.ToArray());}
        internal GenericEventV6Observation Start()
        {var value=Session.Read();Check(value.Status=="ready","reward ready");Check(Session.Apply(value.DecisionId,"choose:0").Outcome=="accepted","reward parent dispatch");return Session.Read();}
        internal ICardSelectionV1ReadValue Child(GenericEventV6Observation c)=>Session.ReadCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal).Value;
        internal CardSelectionV1Observation Act(GenericEventV6Observation c,string action)
        {var o=(CardSelectionV1Observation)Child(c);Check(o.LegalActions.Contains(action),"reward legal "+action);Check(Session.ApplyCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,action).Value is CardSelectionV1DispatchReceipt,"reward dispatch "+action);return o;}
        public void Dispose(){Session.Dispose();CardSelectCmd.Selector=null;NRun.Instance=null;NEventRoom.Instance=null;NMapScreen.Instance=null;}
    }

}

internal static class NativeCardFixtureExtensions
{
    internal static GenericEventV6CardRead ReadCardChild(this GenericEventV6Session s,string d,string a,int n)=>(GenericEventV6CardRead)s.ReadChild(d,a,n);
    internal static GenericEventV6CardApply ApplyCardChild(this GenericEventV6Session s,string d,string a,int n,string? decision,string? action)=>(GenericEventV6CardApply)s.ApplyChild(d,a,n,decision,action);
}
