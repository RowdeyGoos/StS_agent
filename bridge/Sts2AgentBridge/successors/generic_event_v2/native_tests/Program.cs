using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
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
using Sts2AgentBridge.Successors.GenericEventV2;
using Sts2AgentBridge.Successors.GenericEventV2.Native;

internal static class Program
{
    private static int _checks;
    static void Check(bool okay,string name){_checks++;if(!okay)throw new Exception(name);}
    static void Main()
    {
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
            Check(f.Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal) is CardSelectionV1Observation o&&o.Status=="unsupported","callback failure rejects matching effect");
        }
        using(var f=new Fixture("WRONG_LINEAGE"))
        {
            var c=f.Start();Check(f.Session.ReadChild(new string('f',64),c.Child!.ParentActionId,c.Child.Ordinal) is CardSelectionV1Observation o&&o.Status=="unsupported","wrong child parent");
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
            Check(f.Session.ReadChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal) is CardSelectionV1Observation,"matching delta cannot finish callback");
            f.Gate.SetResult();Check(f.Session.ReadChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal) is CardSelectionV1ResolvedResult,"callback task finishes effect gate");
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
        RemovalTests();
        PatchOwnership();
        Console.WriteLine("generic native checks: "+_checks);
    }
    private static bool IsUnsupported(Fixture f,GenericEventV2Observation c)
    {
        var child=c.Child!;
        for(int i=0;i<2;i++)
            if(f.Session.ReadChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal) is CardSelectionV1Observation o&&o.Status=="unsupported")return true;
        return false;
    }
    private static async Task Orphan(Fixture f)
    {await f.Gate.Task;await CardSelectCmd.FromDeckForUpgrade(f.Player,new CardSelectorPrefs(1,1));}
    private static void ForeignPrefix(){}
    private static void PatchOwnership()
    {
        var target=typeof(EventOption).GetMethod(nameof(EventOption.Chosen))!;
        var prefix=typeof(Program).GetMethod(nameof(ForeignPrefix),System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static)!;
        foreach(string owner in new[]{"fixture.foreign","sts2agent.generic_event_v2"})
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
        bool rejected=false;try{using var hooks=new GenericEventV2Hooks();}catch(InvalidOperationException){rejected=true;}
        Check(rejected,"preexisting patch rejected");foreignBefore.Unpatch(target,prefix);
        bool failed=false;
        try{using var hooks=new GenericEventV2Hooks(n=>{if(n==2)throw new InvalidOperationException("partial install");},null);}
        catch(InvalidOperationException){failed=true;}
        Check(failed&&HarmonyLib.Harmony.GetPatchInfo(target)?.Owners.Count is null or 0,"partial installation rolls back exact owned hooks");
        int cleanupFailures=1;failed=false;
        try{using var hooks=new GenericEventV2Hooks(n=>throw new InvalidOperationException("partial install"),()=>{if(cleanupFailures-->0)throw new InvalidOperationException("cleanup failure");});}
        catch(AggregateException){failed=true;}
        Check(failed&&HarmonyLib.Harmony.GetPatchInfo(target)?.Prefixes.Count==1,"failed rollback retains discoverable owner lease");
        GenericEventV2Hooks.RecoverFailedInstallation();
        Check(HarmonyLib.Harmony.GetPatchInfo(target)?.Owners.Count is null or 0,"failed constructor cleanup recoverable");
        using(var hooks=new GenericEventV2Hooks())
        {
            bool protectedLease=false;try{GenericEventV2Hooks.RecoverFailedInstallation();}catch(InvalidOperationException){protectedLease=true;}
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
        internal GenericEventV2Session Session;
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
            Session=new GenericEventV2Session(new PinnedGenericEventV2NativeAdapter(),new string('a',32));
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
        internal GenericEventV2Observation Start()
        {
            var value=Session.Read();Check(value.Status=="ready","ready native option");
            Check(Session.Apply(value.DecisionId,"choose:0").Outcome=="accepted","parent accepted");return Session.Read();
        }
        internal void SelectConfirm(GenericEventV2Observation c)
        {
            var child=c.Child!;var o=(CardSelectionV1Observation)Session.ReadChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal);
            Check(o.LegalActions.Contains("select:0"),"initial real child select");
            Check(Session.ApplyChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal,o.DecisionId,"select:0") is CardSelectionV1DispatchReceipt,"select dispatch");
            o=(CardSelectionV1Observation)Session.ReadChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal);
            Check(o.LegalActions.Contains("confirm"),"original preview confirm");
            Check(Session.ApplyChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal,o.DecisionId,"confirm") is CardSelectionV1DispatchReceipt,"confirm dispatch");
        }
        internal void Finish(GenericEventV2Observation c)
        {
            SelectConfirm(c);var child=c.Child!;
            var r=Session.ReadChild(child.ParentDecisionId,child.ParentActionId,child.Ordinal);
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
        internal GenericEventV2Session Session;
        internal PinnedGenericEventV2NativeAdapter Adapter;
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
            Adapter=new PinnedGenericEventV2NativeAdapter();Session=new GenericEventV2Session(Adapter,new string('b',32));
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
        internal GenericEventV2Observation Start()
        {var value=Session.Read();Check(value.Status=="ready","removal ready");Check(Session.Apply(value.DecisionId,"choose:0").Outcome=="accepted","removal parent dispatch");return Session.Read();}
        internal ICardSelectionV1ReadValue Child(GenericEventV2Observation c)=>Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal);
        internal CardSelectionV1Observation Act(GenericEventV2Observation c,string action)
        {var o=(CardSelectionV1Observation)Child(c);Check(o.LegalActions.Contains(action),"removal legal "+action);Check(Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,action) is CardSelectionV1DispatchReceipt,"removal dispatch "+action);return o;}
        public void Dispose(){Session.Dispose();CardSelectCmd.Selector=null;NRun.Instance=null;NEventRoom.Instance=null;NMapScreen.Instance=null;}
    }

}
