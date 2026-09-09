using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
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
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;

internal static partial class Program
{
    private sealed class FirstMultiEvent:EventModel{}
    private sealed class AnotherMultiEvent:EventModel{}
    private sealed class HeldOutMultiEvent:EventModel{}
    private sealed class MultiDerivedHitbox:NClickableControl{}
    internal sealed class MultiUpgradeFixture:IDisposable
    {
        internal readonly Player Player=new();
        internal readonly RunState RunState=new();
        internal readonly CardModel[] Cards;
        internal readonly EventModel Model;
        internal readonly NEventRoom Room=new();
        internal readonly NMapScreen Map=new();
        internal readonly NOverlayStack Overlays=new();
        internal readonly NRun Run=new();
        internal readonly Control Preview=new(){Visible=false};
        internal readonly Control PreviewCards=new();
        internal readonly NConfirmButton ConfirmButton=new();
        internal readonly TaskCompletionSource CreationGate=new(),CompletionGate=new(),AdditionGate=new();
        internal readonly GenericEventV7Session Session;
        internal readonly List<CardModel> Selected=new(),Clones=new();
        internal readonly Queue<Action> Clicks=new();
        internal NDeckUpgradeSelectScreen Screen=null!;
        internal NCardGrid Grid=null!;
        internal int OptionCalls,SelectCalls,ConfirmCalls;
        internal CardModel[] PreSelectorAdditions=Array.Empty<CardModel>();
        internal Action? BeforeCreate {get;set;}
        internal Action? BeforeClick {get;set;}
        internal Action? AfterClone {get;set;}
        internal Action? AfterEffect {get;set;}
        internal Action? BeforeConfirm {get;set;}
        internal Func<CardModel,CardModel>? CloneArgument;
        internal Func<CardModel,RunState>? CloneRun;
        internal Func<IEnumerable<CardModel>,IEnumerable<CardModel>>? ScreenResult,RequestResult;
        internal bool RepeatOnce;
        internal bool SkipClone,DuplicateClone,DuplicateCallback,WrongScreen,WorkerClone,PartialEffect,FaultCallback,FaultRequest,CancelCallback,LostConfirm;
        internal int? MinimumOverride;
        private readonly int _count,_domain;
        private readonly bool _deferredClick,_deferredPreview;
        private TaskCompletionSource<IEnumerable<CardModel>> _selected=new();
        private readonly List<Node> _previewTail=new();
        internal MultiUpgradeFixture(string name,int count,int domain=10,bool manual=false,bool delayedCreation=false,bool delayedCompletion=false,bool deferredClick=false,bool deferredPreview=false,string? nonce=null)
        {
            _count=count;_domain=domain;_deferredClick=deferredClick;_deferredPreview=deferredPreview;
            Player.RunState=RunState;
            Cards=Enumerable.Range(0,domain+1).Select(i=>{var c=new CardModel{Owner=Player,IsUpgradable=i<domain};c.Id.Entry="Card_"+i;return c;}).ToArray();
            Player.Deck.Cards.AddRange(Cards);
            Model=name=="FIRST_MULTI"?new FirstMultiEvent():name=="ANOTHER_MULTI"?new AnotherMultiEvent():new HeldOutMultiEvent();Model.Owner=Player;
            Run.EventRoom=Room;Run.GlobalUi=new GlobalUiState{MapScreen=Map,Overlays=Overlays};
            NRun.Instance=Run;NEventRoom.Instance=Room;NMapScreen.Instance=Map;
            var option=new EventOption{TextKey=name+".OPTION"};
            option.Callback=async()=>{
                OptionCalls++;
                var values=await CardSelectCmd.FromDeckForUpgrade(Player,new CardSelectorPrefs(MinimumOverride??count,count,false,manual));
                var effect=values.ToArray();
                if(PartialEffect&&effect.Length>0){effect[0].CurrentUpgradeLevel++;await AdditionGate.Task;foreach(var card in effect.Skip(1))card.CurrentUpgradeLevel++;}
                else foreach(var card in effect)card.CurrentUpgradeLevel++;
                AfterEffect?.Invoke();
                if(delayedCompletion)await CompletionGate.Task;
                if(CancelCallback)throw new OperationCanceledException();
                if(FaultCallback)throw new InvalidOperationException("callback fault");
                if(RepeatOnce)
                {
                    RepeatOnce=false;Room.Layout.OptionButtons.Clear();
                    _selected=new();Selected.Clear();Clones.Clear();PreviewCards.Children.Clear();Preview.Visible=false;
                    AddOption(new EventOption{TextKey=name+".NEXT",Callback=option.Callback});
                }
                else {Model.IsFinished=true;ShowProceed();}
            };
            AddOption(option);
            CardSelectCmd.Handler=async(player,prefs)=>{
                if(delayedCreation)await CreationGate.Task;
                BeforeCreate?.Invoke();
                var screen=NDeckUpgradeSelectScreen.ShowScreen(Cards.Take(_domain).ToArray(),prefs,player.RunState);
                var result=await screen.CardsSelected();
                if(FaultRequest)throw new InvalidOperationException("request fault");
                return RequestResult?.Invoke(result)??result;
            };
            NDeckUpgradeSelectScreen.Factory=(cards,prefs,run)=>CreateScreen(cards);
            Session=new GenericEventV7Session(new PinnedGenericEventV7NativeAdapter(),nonce??new string('d',32));
        }
        private void AddOption(EventOption option)
        {
            var button=new NEventOptionButton{Option=option,Event=Model};
            button.Bind("%Text",new MegaRichTextLabel{Text="Multi native option"});Room.Layout.OptionButtons.Add(button);
        }
        private void ShowProceed()
        {
            Room.Layout.OptionButtons.Clear();AddOption(new EventOption{TextKey="PROCEED",IsProceed=true,Callback=()=>{OptionCalls++;Map.IsOpen=true;Map.IsTravelEnabled=true;return Task.CompletedTask;}});
        }
        private NDeckUpgradeSelectScreen CreateScreen(IReadOnlyList<CardModel> cards)
        {
            Screen=new NDeckUpgradeSelectScreen{SelectionTask=_selected.Task};Grid=new NCardGrid();
            int rows=(cards.Count+3)/4;float height=rows*300+(rows-1)*40+400;
            Grid.Size=new Vector2(1000,height+100);Grid.Bind("%ScrollContainer",new Control{Size=new Vector2(1000,height),Position=new Vector2(0,50)});
            foreach(var card in cards)
            {
                var material=new ShaderMaterial();var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card,CardHighlight=new NCardHighlight{Material=material}},Hitbox=new MultiDerivedHitbox()};
                holder.Selected=()=>{
                    SelectCalls++;
                    Action invoke=()=>{BeforeClick?.Invoke();if(WrongScreen){var foreign=new NDeckUpgradeSelectScreen{ClickHandler=Screen.ClickHandler};foreign.DeliverClick(card);}else Screen.DeliverClick(card);if(DuplicateCallback)Screen.DeliverClick(card);};
                    if(_deferredClick)Clicks.Enqueue(invoke);else invoke();
                };
                Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            Screen.ClickHandler=card=>{
                Selected.Add(card);
                ((ShaderMaterial)Grid.CurrentlyDisplayedCardHolders.Single(h=>ReferenceEquals(h.CardModel,card)).CardNode.CardHighlight.Material!).Width=BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits);
                if(Selected.Count!=_count)return;
                Preview.Visible=true;
                foreach(var original in Selected)
                {
                    ((ShaderMaterial)Grid.CurrentlyDisplayedCardHolders.Single(h=>ReferenceEquals(h.CardModel,original)).CardNode.CardHighlight.Material!).Width=0;
                    if(SkipClone)continue;
                    var argument=CloneArgument?.Invoke(original)??original;
                    var run=CloneRun?.Invoke(original)??RunState;
                    var clone=WorkerClone?Task.Run(()=>run.CloneCard(argument)).GetAwaiter().GetResult():run.CloneCard(argument);
                    Clones.Add(clone);clone.CurrentUpgradeLevel++;AfterClone?.Invoke();
                    if(DuplicateClone)_=run.CloneCard(argument);
                    var holder=new NPreviewCardHolder{CardNode=new NCard{Model=clone}};
                    if(_deferredPreview&&PreviewCards.Children.Count>0)_previewTail.Add(holder);else PreviewCards.Children.Add(holder);
                }
            };
            Preview.Bind("Cards",PreviewCards);Preview.Bind("Confirm",ConfirmButton);Screen.Bind("%UpgradeMultiPreviewContainer",Preview);Screen.Bind("%CardGrid",Grid);
            ConfirmButton.Clicked=()=>{ConfirmCalls++;BeforeConfirm?.Invoke();if(LostConfirm)return;Overlays.Screens.Clear();Screen.Visible=false;_selected.TrySetResult(ScreenResult?.Invoke(Selected)??Selected.ToArray());};
            Overlays.Screens.Add(Screen);return Screen;
        }
        internal void AdvanceClick(){if(Clicks.Count==0)throw new InvalidOperationException("No deferred callback.");Clicks.Dequeue()();}
        internal void AdvancePreview(){PreviewCards.Children.AddRange(_previewTail);_previewTail.Clear();}
        internal bool CompletionValid=>Player.Deck.Cards.SequenceEqual(Cards.Concat(PreSelectorAdditions))&&Selected.Count==_count&&Selected.Distinct(ReferenceEqualityComparer.Instance).Count()==_count&&Cards.Select((card,index)=>card.Id.Entry=="Card_"+index&&card.CurrentUpgradeLevel==(Selected.Contains(card)?1:0)).All(x=>x);
        internal GenericEventV7Observation Start()
        {var p=Session.Read();Check(p.Status=="ready","multi parent ready");Check(Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","multi parent dispatch");return Session.Read();}
        internal object Child(GenericEventV7Observation c)=>Session.ReadCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal).Value;
        internal void Act(GenericEventV7Observation c,string action)
        {var o=(CardSelectionV1Observation)Child(c);Check(o.Status=="ready"&&o.LegalActions.Contains(action),"multi legal "+action+" was "+o.Status);Check(Session.ApplyCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,action).Value is CardSelectionV1DispatchReceipt,"multi dispatch "+action);}
        public void Dispose(){Session.Dispose();CardSelectCmd.Selector=null;NRun.Instance=null;NEventRoom.Instance=null;NMapScreen.Instance=null;}
    }
    // Inert allocated holders below a deliberately small viewport. This tests
    // admission/dispatch, not native clipping or allocation behavior in a live game.
    internal static void LimitUpgradeViewport()
    {
        var create=NDeckUpgradeSelectScreen.Factory!;
        NDeckUpgradeSelectScreen.Factory=(cards,prefs,run)=>{
            var screen=create(cards,prefs,run);
            var grid=screen.GetNodeOrNull<NCardGrid>("%CardGrid")!;
            grid.Size=new Vector2(1000,500);
            for(int i=0;i<grid.CurrentlyDisplayedCardHolders.Count;i++)
                grid.CurrentlyDisplayedCardHolders[i].Position=new Vector2((i%4)*240,80+(i/4)*340);
            return screen;
        };
    }
    private static void UpgradeHolderInputTests()
    {
        object Child(Fixture f,GenericEventV7Observation c)=>f.Session.ReadCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal).Value;
        void Act(Fixture f,GenericEventV7Observation c,string action)
        {
            var o=(CardSelectionV1Observation)Child(f,c);
            Check(o.Status=="ready"&&o.LegalActions.Contains(action),"allocated upgrade legal "+action);
            Check(f.Session.ApplyCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,action).Value is CardSelectionV1DispatchReceipt,"allocated upgrade dispatch");
        }
        foreach(int slot in new[]{0,15,19})
        {
            using var f=new Fixture("ALLOCATED_UPGRADE",domain:20);LimitUpgradeViewport();
            var c=f.Start();Check(c.Status=="child","large upgrade domain admitted");
            var grid=((NDeckUpgradeSelectScreen)f.Overlays.Screens[0]).GetNodeOrNull<NCardGrid>("%CardGrid")!;
            grid.Size=new Vector2(800,400);grid.GetNodeOrNull<Control>("%ScrollContainer")!.Position=new Vector2(0,-100);
            Act(f,c,"select:"+slot);Act(f,c,"confirm");
            Check(Child(f,c) is CardSelectionV1ResolvedResult,"allocated upgrade exact resolution");
            Check(f.Cards.Select((card,index)=>card.CurrentUpgradeLevel==(index==slot?1:0)).All(x=>x),"only requested original upgraded");
            Check(f.SelectCalls==1&&f.ConfirmCalls==1,"allocated upgrade exactly once");
        }
        foreach(string mutation in new[]{"unclickable","disabled","hidden","holder","hitbox","grid","domain","animating"})
        {
            using var f=new Fixture("ALLOCATED_MUTATION",domain:20);LimitUpgradeViewport();
            var c=f.Start();var o=(CardSelectionV1Observation)Child(f,c);
            var screen=(NDeckUpgradeSelectScreen)f.Overlays.Screens[0];var grid=screen.GetNodeOrNull<NCardGrid>("%CardGrid")!;
            var h=grid.CurrentlyDisplayedCardHolders[15];
            switch(mutation){case "unclickable":h.SetClickable(false);break;case "disabled":h.Hitbox.IsEnabled=false;break;case "hidden":h.Visible=false;break;case "holder":h.CardModel=f.Cards[19];break;case "hitbox":h.Hitbox=new MultiDerivedHitbox();break;case "grid":screen.Bind("%CardGrid",new NCardGrid());break;case "domain":grid.CurrentlyDisplayedCardHolders.RemoveAt(19);break;case "animating":grid.IsAnimatingOut=true;break;}
            f.Session.ApplyCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,"select:15");
            Check(f.SelectCalls==0&&f.ConfirmCalls==0,"changed allocated target never dispatched: "+mutation);
        }
        using(var f=new Fixture("UNCLICKABLE_ADMISSION",domain:20))
        {
            LimitUpgradeViewport();var create=NDeckUpgradeSelectScreen.Factory!;
            NDeckUpgradeSelectScreen.Factory=(cards,prefs,run)=>{var screen=create(cards,prefs,run);foreach(var h in screen.GetNodeOrNull<NCardGrid>("%CardGrid")!.CurrentlyDisplayedCardHolders)h.SetClickable(false);return screen;};
            Check(f.Start().Status=="waiting"&&f.SelectCalls==0,"no clickable holder waits without admission");
            ((NDeckUpgradeSelectScreen)f.Overlays.Screens[0]).GetNodeOrNull<NCardGrid>("%CardGrid")!.CurrentlyDisplayedCardHolders[15].SetClickable(true);
            var c=f.Session.Read();Check(c.Status=="child","native enable admits selector");Act(f,c,"select:15");Act(f,c,"confirm");
            Check(Child(f,c) is CardSelectionV1ResolvedResult,"native enabled target resolves");
        }
        using(var f=new MultiUpgradeFixture("ALLOCATED_MULTI",2,20,deferredClick:true))
        {
            LimitUpgradeViewport();var c=f.Start();Check(c.Status=="child","large multi domain admitted");
            foreach(int slot in new[]{15,19})
            {
                f.Act(c,"select:"+slot);
                Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="waiting","allocated deferred input waits");
                f.Grid.Size=new Vector2(800,400);f.Grid.GetNodeOrNull<Control>("%ScrollContainer")!.Position=new Vector2(0,-500);
                f.AdvanceClick();
            }
            f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid,"allocated multi exact resolution");
            Check(f.Selected.SequenceEqual(new[]{f.Cards[15],f.Cards[19]})&&f.SelectCalls==2&&f.ConfirmCalls==1,"allocated multi exact originals once");
        }
        using(var f=new MultiUpgradeFixture("ALLOCATED_UNCLICKABLE",2,20,deferredClick:true))
        {
            LimitUpgradeViewport();var c=f.Start();f.Act(c,"select:15");f.Grid.CurrentlyDisplayedCardHolders[15].SetClickable(false);f.AdvanceClick();
            Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","deferred native clickability revalidated");
            Check(f.SelectCalls==1&&f.ConfirmCalls==0&&f.Cards.All(card=>card.CurrentUpgradeLevel==0),"unclickable deferred callback stops before further input or effect");
        }
    }
    private static void MultiUpgradeTests()
    {
        foreach(string name in new[]{"FIRST_MULTI","ANOTHER_MULTI","HELD_OUT_MULTI"})
        foreach(int count in new[]{2,8})foreach(bool manual in new[]{false,true})
        {
            using var f=new MultiUpgradeFixture(name,count,10,manual);var c=f.Start();Check(c.Status=="child","multi admission");
            foreach(int index in Enumerable.Range(0,count).Reverse())f.Act(c,"select:"+index);
            f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult,"multi exact frozen resolution");Check(f.CompletionValid,"multi exact effect");
            var p=f.Session.Read();Check(p.Phase=="proceed"&&p.CompletedCardChildren==1,"multi cumulative resolution");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete"&&f.OptionCalls==2&&f.SelectCalls==count&&f.ConfirmCalls==1,"multi map and native counts");
        }
        using(var f=new MultiUpgradeFixture("DEFERRED",2,deferredClick:true,deferredPreview:true,delayedCreation:true,delayedCompletion:true))
        {
            Check(f.Start().Status=="waiting","multi delayed creation");f.CreationGate.SetResult();var c=f.Session.Read();
            f.Act(c,"select:1");Check(f.Child(c) is CardSelectionV1Observation a&&a.Status=="waiting","ticket pending");f.AdvanceClick();
            f.Act(c,"select:0");Check(f.Child(c) is CardSelectionV1Observation b&&b.Status=="waiting","final ticket pending");f.AdvanceClick();
            Check(f.Child(c) is CardSelectionV1Observation d&&d.Status=="waiting","partial preview not frozen");f.AdvancePreview();f.Act(c,"confirm");
            Check(f.Child(c) is CardSelectionV1Observation e&&e.Status=="waiting","multi waits chosen task");f.CompletionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid,"multi delayed resolution");
        }
        using(var f=new MultiUpgradeFixture("PARTIAL_EFFECT",2)){f.PartialEffect=true;var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation p&&p.Status=="waiting","multi monotonic partial effect");f.AdditionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult,"partial effect completes");}
        using(var f=new MultiUpgradeFixture("VARIABLE",3)){f.MinimumOverride=2;Check(f.Start().Status=="unsupported","variable upgrades excluded");}
        using(var f=new MultiUpgradeFixture("SHORT_DOMAIN",2,2)){Check(f.Start().Status=="unsupported","auto shortcut domain excluded");}
        foreach(string fault in new[]{"missing","duplicate","wrong_original","baseline_clone","same_clone","wrong_run","worker","duplicate_callback","wrong_screen"})
        {
            using var f=new MultiUpgradeFixture(fault,2);CardModel? retained=null;
            switch(fault){case "missing":f.SkipClone=true;break;case "duplicate":f.DuplicateClone=true;break;case "wrong_original":f.CloneArgument=_=>f.Cards[2];break;case "baseline_clone":f.RunState.CloneOverride=_=>f.Cards[10];break;case "same_clone":f.RunState.CloneOverride=c=>{if(retained is null){retained=new CardModel();retained.Id.Entry=c.Id.Entry;}return retained;};break;case "wrong_run":f.CloneRun=_=>new RunState();break;case "worker":f.WorkerClone=true;break;case "duplicate_callback":f.DuplicateCallback=true;break;case "wrong_screen":f.WrongScreen=true;break;}
            var c=f.Start();f.Act(c,"select:0");if(fault is not ("duplicate_callback" or "wrong_screen"))f.Act(c,"select:1");
            Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","multi rejects "+fault);Check(f.ConfirmCalls==0,"no confirm "+fault);
        }
        foreach(string mutation in new[]{"holder","card","hitbox","grid","invisible","disabled","original"})
        {
            using var f=new MultiUpgradeFixture(mutation,2,deferredClick:true);var c=f.Start();f.Act(c,"select:0");var h=f.Grid.CurrentlyDisplayedCardHolders[0];
            switch(mutation){case "holder":f.Grid.CurrentlyDisplayedCardHolders[0]=new NGridCardHolder{CardModel=h.CardModel,CardNode=h.CardNode,Hitbox=h.Hitbox};break;case "card":h.CardNode=new NCard{Model=f.Cards[0]};break;case "hitbox":h.Hitbox=new MultiDerivedHitbox();break;case "grid":f.Screen.Bind("%CardGrid",new NCardGrid());break;case "invisible":h.Hitbox.Visible=false;break;case "disabled":h.Hitbox.IsEnabled=false;break;case "original":f.Cards[0].Id.Entry="Changed";break;}
            try{f.AdvanceClick();}catch(NullReferenceException){}
            Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","deferred ticket retention "+mutation);Check(f.ConfirmCalls==0,"retention no confirm");
        }
        foreach(string mutation in new[]{"foreign","holder","card","clone","swap","invisible","dead","extra","missing","confirm"})
        {
            using var f=new MultiUpgradeFixture(mutation,2);var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");_=f.Child(c);var h=(NPreviewCardHolder)f.PreviewCards.Children[0];
            switch(mutation){case "foreign":h.CardNode.Model=f.Cards[0];break;case "holder":f.PreviewCards.Children[0]=new NPreviewCardHolder{CardNode=h.CardNode};break;case "card":h.CardNode=new NCard{Model=h.CardNode.Model};break;case "clone":h.CardNode.Model!.CurrentUpgradeLevel++;break;case "swap":var other=(NPreviewCardHolder)f.PreviewCards.Children[1];(h.CardNode.Model,other.CardNode.Model)=(other.CardNode.Model,h.CardNode.Model);break;case "invisible":h.Visible=false;break;case "dead":h.InstanceValid=false;break;case "extra":f.PreviewCards.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=f.Clones[0]}});break;case "missing":f.PreviewCards.Children.RemoveAt(0);break;case "confirm":f.Preview.Bind("Confirm",new NConfirmButton());break;}
            Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","preview retention "+mutation);Check(f.ConfirmCalls==0,"bad preview never confirmed");
        }
        foreach(string fault in new[]{"request","screen","unselected","plus_two","reorder","callback","cancel","request_fault"})
        {
            using var f=new MultiUpgradeFixture(fault,2);
            switch(fault){case "request":f.RequestResult=_=>new[]{f.Cards[0],f.Cards[2]};break;case "screen":f.ScreenResult=_=>new[]{f.Cards[0],f.Cards[2]};break;case "unselected":f.AfterEffect=()=>f.Cards[2].CurrentUpgradeLevel++;break;case "plus_two":f.AfterEffect=()=>f.Cards[0].CurrentUpgradeLevel++;break;case "reorder":f.AfterEffect=()=>f.Player.Deck.Cards.Reverse();break;case "callback":f.FaultCallback=true;break;case "cancel":f.CancelCallback=true;break;case "request_fault":f.FaultRequest=true;break;}
            var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","multi completion "+fault);
        }
        using(var f=new MultiUpgradeFixture("FOREIGN_CLICK",2)){var c=f.Start();f.Screen.DeliverClick(f.Cards[0]);Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","observed click never authorizes itself");}
        using(var f=new MultiUpgradeFixture("LOST_CONFIRM",2)){f.LostConfirm=true;var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");f.Act(c,"confirm");for(int i=0;i<3;i++)Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="waiting","lost confirm waits");Check(f.ConfirmCalls==1,"lost confirm never retried");}
        using(var f=new MultiUpgradeFixture("STALE_GENERATION",2))
        {
            f.RepeatOnce=true;var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");var old=f.Clones.ToArray();
            f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult,"first generation resolves");
            var parent=f.Session.Read();Check(parent.Status=="ready"&&parent.CompletedCardChildren==1,"second option available");
            f.Session.Apply(parent.DecisionId,"choose:0");var next=f.Session.Read();
            f.RunState.CloneOverride=card=>old[ReferenceEquals(card,f.Cards[0])?0:1];
            f.Act(next,"select:0");f.Act(next,"select:1");
            Check(f.Child(next) is CardSelectionV1Observation o&&o.Status=="unsupported","previous generation clone rejected");Check(f.ConfirmCalls==1,"stale generation never confirmed");
        }
        using(var f=new MultiUpgradeFixture("EXTRA_CLONE",2))
        {var c=f.Start();f.AfterClone=()=>{_=f.RunState.CloneCard(f.Cards[2]);};f.Act(c,"select:0");f.Act(c,"select:1");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","extra scoped clone rejected");}
        using(var f=new MultiUpgradeFixture("CALLBACK_CONTEXT",2,deferredClick:true))
        {var c=f.Start();f.Act(c,"select:0");NEventRoom.Instance=new NEventRoom();f.AdvanceClick();Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","callback exact context retained");}
        using(var f=new MultiUpgradeFixture("LOST_CALLBACK",2,deferredClick:true))
        {var c=f.Start();f.Act(c,"select:0");for(int i=0;i<3;i++)Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="waiting","lost callback waiting");Check(f.SelectCalls==1&&f.ConfirmCalls==0,"lost callback cannot redispatch");}
        foreach(var target in new[]{typeof(NDeckUpgradeSelectScreen).GetMethod("OnCardClicked",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!,typeof(RunState).GetMethod(nameof(RunState.CloneCard))!})
        {
            var foreign=new Harmony("fixture.newtarget");var prefix=typeof(Program).GetMethod(nameof(ForeignPrefix),System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static)!;
            using(var f=new MultiUpgradeFixture("HOOK_INTRUSION",2))
            {var c=f.Start();foreign.Patch(target,prefix:new HarmonyMethod(prefix));Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","new target hook intrusion");}
            Check(Harmony.GetPatchInfo(target)?.Prefixes.Any(p=>p.PatchMethod==prefix)==true,"foreign new target hook preserved");foreign.Unpatch(target,prefix);
        }
        for(int stop=8;stop<=15;stop++)
        {
            int at=stop,failCleanup=1;bool failed=false;
            try{using var hooks=new GenericEventV7Hooks(n=>{if(n==at)throw new InvalidOperationException("new target install fault");},()=>{if(failCleanup-->0)throw new InvalidOperationException("inert unpatch failure");});}catch(AggregateException){failed=true;}
            Check(failed,"new target failed rollback ownership retained");GenericEventV7Hooks.RecoverFailedInstallation();using var clean=new GenericEventV7Hooks();
        }
        for(int stop=1;stop<=15;stop++)
        {int at=stop;bool failed=false;try{using var hooks=new GenericEventV7Hooks(n=>{if(n==at)throw new InvalidOperationException("inert install fault");},null);}catch(InvalidOperationException){failed=true;}Check(failed,"each new hook rollback "+stop);using var clean=new GenericEventV7Hooks();}
        using(var f=new RewardFixture("DERIVED_REWARD",2,2))
        {f.BeforeReturn=()=>{foreach(var h in f.Grid.CurrentlyDisplayedCardHolders)h.Hitbox=new MultiDerivedHitbox();};var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");Check(f.Child(c) is CardSelectionV1ResolvedResult,"v5 derived reward hitbox retained");}
    }
}
