using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Cards;
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
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using NativeHook=MegaCrit.Sts2.Core.Hooks.Hook;

internal static partial class Program
{
    private sealed class FirstTransformEvent:EventModel{}
    private sealed class AnotherTransformEvent:EventModel{}
    private sealed class HeldOutTransformEvent:EventModel{}
    private sealed class TransformDerivedHitbox:NClickableControl{}
    internal sealed class TransformFixture:IDisposable
    {
        internal readonly Player Player=new();
        internal readonly RunState RunState=new();
        internal readonly CardModel[] Cards;
        internal readonly EventModel Model;
        internal readonly NEventRoom Room=new();
        internal readonly NMapScreen Map=new();
        internal readonly NOverlayStack Overlays=new();
        internal readonly NRun Run=new();
        internal readonly Control Preview=new(){Visible=false},Before=new(),After=new();
        internal readonly NTransformPreview TransformPreview=new();
        internal readonly NConfirmButton ConfirmButton=new(),RootConfirmButton=new(){Visible=false,IsEnabled=false};
        internal int PreviewCalls;
        internal bool LostPreview,UnexpectedEarlyPreview;
        internal Action? BeforePreview {get;set;}
        internal Action? AfterPreview {get;set;}
        private readonly Queue<Action> _previews=new();
        private readonly bool _delayedPreview,_partialPreview;
        internal readonly TaskCompletionSource CreationGate=new(),CompletionGate=new();
        internal readonly GenericEventV7Session Session;
        internal readonly List<CardModel> Selected=new(),InitialCards=new(),FinalCards=new(),Originals=new();
        internal readonly Queue<Action> Confirms=new();
        private readonly Queue<TaskCompletionSource> _insertions=new();
        internal NDeckTransformSelectScreen Screen=null!;
        internal NCardGrid Grid=null!;
        internal int OptionCalls,SelectCalls,ConfirmCalls,BatchCount;
        internal CardModel[] PreSelectorAdditions=Array.Empty<CardModel>();
        internal List<CardModel> InsertedOriginals=>Originals;
        internal int CompletedBatches {get;private set;}
        internal Control BeforeCards=>Before;internal Control AfterCards=>After;
        internal Action? BeforeCreate {get;set;}
        internal Action? BeforeConfirm {get;set;}
        internal Action? AfterRemoval {get;set;}
        internal Action? AfterInsertion {get;set;}
        internal Action? AfterEffect {get;set;}
        internal Func<CardModel,CardModel>? Generate,Modify;
        internal Func<List<CardPileAddResult>,IEnumerable<CardPileAddResult>>? Results;
        internal Func<IEnumerable<CardModel>,IEnumerable<CardModel>>? RequestResult,ScreenResult;
        internal int RepeatTransforms;
        internal bool ContinueWithUpgrade,ReuseCommandTask;
        private Task<IEnumerable<CardPileAddResult>>? _reusedTask;
        internal readonly List<CardModel> UpgradedOriginals=new();
        internal readonly List<CardModel> UpgradeClones=new();
        internal NDeckUpgradeSelectScreen UpgradeScreen=null!;
        internal NCardGrid UpgradeGrid=null!;
        internal bool LostConfirm,FaultCallback,CancelCallback,FaultCommand,CancelCommand,FaultAfterRemoval,FaultAfterInsertion,DuplicateChoice,NestedCommand;
        internal int? MinimumOverride;internal bool Cancelable;internal bool WrongDomain;
        private readonly int _count,_domain;
        private readonly bool _partialInsertion,_deferredConfirm;
        private readonly int[] _batches;
        private TaskCompletionSource<IEnumerable<CardModel>> _selected=new();
        internal TransformFixture(string name,int count,int domain=10,bool manual=false,int[]? batchSizes=null,bool delayedCreation=false,bool delayedCompletion=false,bool partialInsertion=false,bool substitute=false,bool deferredConfirm=false,string? nonce=null,EventModel? eventModel=null,int? minimum=null,bool delayedPreview=false,bool partialPreview=false)
        {
            _count=count;_domain=domain;MinimumOverride=minimum;_delayedPreview=delayedPreview;_partialPreview=partialPreview;_partialInsertion=partialInsertion;_deferredConfirm=deferredConfirm;_batches=batchSizes??new[]{count};
            Player.RunState=RunState;
            Cards=Enumerable.Range(0,domain+1).Select(i=>{var c=new CardModel{Owner=Player,IsUpgradable=true,IsTransformable=i<domain,Type=i==domain?6:0};c.Id.Entry="Card_"+i;return c;}).ToArray();Player.Deck.Cards.AddRange(Cards);
            Model=eventModel??(name=="FIRST_TRANSFORM"?new FirstTransformEvent():name=="ANOTHER_TRANSFORM"?new AnotherTransformEvent():new HeldOutTransformEvent());Model.Owner=Player;
            Run.EventRoom=Room;Run.GlobalUi=new GlobalUiState{MapScreen=Map,Overlays=Overlays};NRun.Instance=Run;NEventRoom.Instance=Room;NMapScreen.Instance=Map;
            EventOption option=null!;option=new EventOption{TextKey=name+".OPTION",Callback=async()=>{
                OptionCalls++;
                var values=(await CardSelectCmd.FromDeckForTransformation(Player,new CardSelectorPrefs(MinimumOverride??count,count,Cancelable,manual))).ToArray();
                int at=0;foreach(int size in _batches){var batch=values.Skip(at).Take(size).Select(c=>new CardTransformation(c));await CardCmd.Transform(batch,new Rng(),CardPreviewStyle.None);at+=size;}
                AfterEffect?.Invoke();if(delayedCompletion)await CompletionGate.Task;
                if(CancelCallback)throw new OperationCanceledException();if(FaultCallback)throw new InvalidOperationException("callback");
                if(RepeatTransforms>0)
                {
                    RepeatTransforms--;Selected.Clear();Before.Children.Clear();After.Children.Clear();Preview.Visible=false;_selected=new();
                    Room.Layout.OptionButtons.Clear();AddOption(new EventOption{TextKey=name+".NEXT."+RepeatTransforms,Callback=option.Callback});
                }
                else if(ContinueWithUpgrade)ShowUpgradeOption();
                else{Model.IsFinished=true;ShowProceed();}
            }};AddOption(option);
            CardSelectCmd.TransformHandler=async(player,prefs,factory)=>{
                if(delayedCreation)await CreationGate.Task;BeforeCreate?.Invoke();
                var screen=NDeckTransformSelectScreen.ShowScreen((WrongDomain?Cards.Take(_domain):Player.Deck.Cards.Where(c=>(int)c.Type!=6&&c.IsTransformable).Take(_domain)).ToArray(),factory??(c=>new CardTransformation(c)),prefs);
                var result=await screen.CardsSelected();return RequestResult?.Invoke(result)??result;
            };
            NDeckTransformSelectScreen.Factory=(cards,factory,prefs)=>CreateScreen(cards);
            CardTransformation.Generator=original=>{
                var card=Generate?.Invoke(original)??NewCard("Initial_"+original.Id.Entry);
                InitialCards.Add(card);return card;
            };
            NativeHook.Modifier=(run,initial)=>Modify?.Invoke(initial)??(substitute?NewCard("Final_"+initial.Id.Entry):initial);
            CardCmd.Handler=(values,rng,style)=>{
                var task=RunCommand(values,rng,style);
                if(!ReuseCommandTask)return task;
                if(_reusedTask is null){_reusedTask=task;return task;}
                var current=task.GetAwaiter().GetResult().ToArray();var old=(List<CardPileAddResult>)_reusedTask.Result;old.Clear();old.AddRange(current);return _reusedTask;
            };
            Session=new GenericEventV7Session(new PinnedGenericEventV7NativeAdapter(),nonce??new string('e',32));
        }
        internal CardModel NewCard(string key){var card=new CardModel{Owner=Player,IsUpgradable=true};card.Id.Entry=key;return card;}
        private async Task<IEnumerable<CardPileAddResult>> RunCommand(IEnumerable<CardTransformation> input,Rng rng,CardPreviewStyle style)
        {
            BatchCount++;var values=input.ToArray();var tuples=new List<(CardTransformation Value,int Index,CardModel Initial)>();
            foreach(var value in values)
            {
                int index=Player.Deck.Cards.IndexOf(value.Original);var initial=value.GetReplacement(rng);
                if(DuplicateChoice)_=value.GetReplacement(rng);
                Player.Deck.Cards.Remove(value.Original);tuples.Add((value,index,initial));
            }
            AfterRemoval?.Invoke();if(FaultAfterRemoval)throw new InvalidOperationException("after removal");
            tuples.Sort((a,b)=>a.Index.CompareTo(b.Index));var results=new List<CardPileAddResult>();
            foreach(var tuple in tuples)
            {
                List<AbstractModel>? modifiers=null;var final=NativeHook.ModifyCardBeingAddedToDeck(RunState,tuple.Initial,ref modifiers);
                if(NestedCommand){NestedCommand=false;await CardCmd.Transform(new[]{new CardTransformation(Cards[^1])},rng,style);}
                Player.Deck.AddInternal(final,-1,false);Originals.Add(tuple.Value.Original);FinalCards.Add(final);
                AfterInsertion?.Invoke();if(FaultAfterInsertion)throw new InvalidOperationException("after insertion");
                if(_partialInsertion){var gate=new TaskCompletionSource();_insertions.Enqueue(gate);await gate.Task;}
                results.Add(new CardPileAddResult{success=true,cardAdded=final,modifyingModels=modifiers});
            }
            if(CancelCommand)throw new OperationCanceledException();if(FaultCommand)throw new InvalidOperationException("command");
            CompletedBatches++;return Results?.Invoke(results)??results;
        }
        private void AddOption(EventOption option)
        {var button=new NEventOptionButton{Option=option,Event=Model};button.Bind("%Text",new MegaRichTextLabel{Text="Transform native option"});Room.Layout.OptionButtons.Add(button);}
        private void ShowProceed()
        {Room.Layout.OptionButtons.Clear();AddOption(new EventOption{TextKey="PROCEED",IsProceed=true,Callback=()=>{OptionCalls++;Map.IsOpen=true;Map.IsTravelEnabled=true;return Task.CompletedTask;}});}
        private NDeckTransformSelectScreen CreateScreen(IReadOnlyList<CardModel> cards)
        {
            Screen=new NDeckTransformSelectScreen{SelectionTask=_selected.Task};Grid=new NCardGrid();
            int rows=(cards.Count+3)/4;float height=rows*300+(rows-1)*40+400;Grid.Size=new Vector2(1000,height+100);Grid.Bind("%ScrollContainer",new Control{Size=new Vector2(1000,height),Position=new Vector2(0,50)});
            foreach(var card in cards)
            {
                var material=new ShaderMaterial();var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card,CardHighlight=new NCardHighlight{Material=material}},Hitbox=new TransformDerivedHitbox()};
                holder.Selected=()=>{SelectCalls++;Selected.Add(card);material.Width=BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits);RootConfirmButton.Visible=RootConfirmButton.IsEnabled=(MinimumOverride??_count)<_count&&Selected.Count>=(MinimumOverride??_count);if(Selected.Count==_count||UnexpectedEarlyPreview)OpenPreview();};Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            TransformPreview.Bind("%Before",Before);TransformPreview.Bind("%After",After);Preview.Bind("TransformPreview",TransformPreview);Preview.Bind("Confirm",ConfirmButton);Screen.Bind("%PreviewContainer",Preview);Screen.Bind("%CardGrid",Grid);Screen.Bind("Confirm",RootConfirmButton);
            RootConfirmButton.Clicked=()=>{PreviewCalls++;BeforePreview?.Invoke();if(LostPreview)return;if(_delayedPreview)_previews.Enqueue(OpenPreview);else OpenPreview();};
            ConfirmButton.Clicked=()=>{ConfirmCalls++;BeforeConfirm?.Invoke();if(LostConfirm)return;Action complete=()=>{Overlays.Screens.Clear();Screen.Visible=false;_selected.TrySetResult(ScreenResult?.Invoke(Selected)??Selected.ToArray());};if(_deferredConfirm)Confirms.Enqueue(complete);else complete();};Overlays.Screens.Add(Screen);return Screen;
        }
        private void OpenPreview()
        {
            Preview.Visible=true;var selected=Selected.ToArray();
            foreach(var original in selected)((ShaderMaterial)Grid.CurrentlyDisplayedCardHolders.Single(h=>ReferenceEquals(h.CardModel,original)).CardNode.CardHighlight.Material!).Width=0;
            void Add(CardModel original){Before.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=original}});After.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=original}});}
            int immediate=_partialPreview?Math.Min(MinimumOverride??1,selected.Length):selected.Length;
            foreach(var original in selected.Take(immediate))Add(original);
            if(immediate<selected.Length)_previews.Enqueue(()=>{foreach(var original in selected.Skip(immediate))Add(original);});
            AfterPreview?.Invoke();
        }
        internal void AdvancePreview(){if(_previews.Count==0)throw new InvalidOperationException("No pending preview");_previews.Dequeue()();}
        internal bool HasPendingPreview=>_previews.Count>0;
        internal Action? AfterUpgrade;
        internal void ShowUpgradeOption()
        {
            Room.Layout.OptionButtons.Clear();
            AddOption(new EventOption{TextKey="MIXED.UPGRADE",Callback=async()=>{
                OptionCalls++;var cards=await CardSelectCmd.FromDeckForUpgrade(Player,new CardSelectorPrefs(2,2,false,true));
                foreach(var card in cards){card.CurrentUpgradeLevel++;UpgradedOriginals.Add(card);}
                if(AfterUpgrade is not null)AfterUpgrade();else{Model.IsFinished=true;ShowProceed();}
            }});
            CardSelectCmd.Handler=async(player,prefs)=>await NDeckUpgradeSelectScreen.ShowScreen(player.Deck.Cards.Where(c=>c.IsUpgradable).ToArray(),prefs,RunState).CardsSelected();
            NDeckUpgradeSelectScreen.Factory=(cards,prefs,run)=>{
                var selected=new List<CardModel>();var tcs=new TaskCompletionSource<IEnumerable<CardModel>>();
                UpgradeScreen=new NDeckUpgradeSelectScreen{SelectionTask=tcs.Task};UpgradeGrid=new NCardGrid();
                int rows=(cards.Count+3)/4;float height=rows*300+(rows-1)*40+400;UpgradeGrid.Size=new Vector2(1000,height+100);UpgradeGrid.Bind("%ScrollContainer",new Control{Size=new Vector2(1000,height),Position=new Vector2(0,50)});
                var preview=new Control{Visible=false};var nodes=new Control();var confirm=new NConfirmButton();preview.Bind("Cards",nodes);preview.Bind("Confirm",confirm);
                foreach(var card in cards)
                {
                    var material=new ShaderMaterial();var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card,CardHighlight=new NCardHighlight{Material=material}},Hitbox=new TransformDerivedHitbox()};
                    holder.Selected=()=>{SelectCalls++;UpgradeScreen.DeliverClick(card);};UpgradeGrid.CurrentlyDisplayedCardHolders.Add(holder);
                }
                UpgradeScreen.ClickHandler=card=>{
                    selected.Add(card);((ShaderMaterial)UpgradeGrid.CurrentlyDisplayedCardHolders.Single(h=>ReferenceEquals(h.CardModel,card)).CardNode.CardHighlight.Material!).Width=BitConverter.Int32BitsToSingle(CardSelectionV1NativeRules.SelectedWidthBits);
                    if(selected.Count!=2)return;preview.Visible=true;
                    foreach(var original in selected){((ShaderMaterial)UpgradeGrid.CurrentlyDisplayedCardHolders.Single(h=>ReferenceEquals(h.CardModel,original)).CardNode.CardHighlight.Material!).Width=0;var clone=RunState.CloneCard(original);clone.CurrentUpgradeLevel++;UpgradeClones.Add(clone);nodes.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=clone}});}
                };
                confirm.Clicked=()=>{ConfirmCalls++;Overlays.Screens.Clear();UpgradeScreen.Visible=false;tcs.SetResult(selected.ToArray());};UpgradeScreen.Bind("%CardGrid",UpgradeGrid);UpgradeScreen.Bind("%UpgradeMultiPreviewContainer",preview);Overlays.Screens.Add(UpgradeScreen);return UpgradeScreen;
            };
        }
        internal void AdvanceConfirm(){if(Confirms.Count==0)throw new InvalidOperationException("No deferred confirm");Confirms.Dequeue()();}
        internal void AdvanceInsertion(){if(_insertions.Count==0)throw new InvalidOperationException("No pending insertion");_insertions.Dequeue().SetResult();}
        internal bool HasPendingInsertion=>_insertions.Count>0;
        internal bool CompletionValid=>Selected.Count>=(MinimumOverride??_count)&&Selected.Count<=_count&&Originals.Count>=Selected.Count&&Originals.Distinct(ReferenceEqualityComparer.Instance).Count()==Originals.Count&&
            Player.Deck.Cards.SequenceEqual(Cards.Concat(PreSelectorAdditions).Where(c=>!Originals.Contains(c)).Concat(FinalCards.Where(c=>!Originals.Contains(c))))&&FinalCards.Distinct(ReferenceEqualityComparer.Instance).Count()==FinalCards.Count&&
            Cards.Select((c,i)=>c.Id.Entry=="Card_"+i&&c.CurrentUpgradeLevel==(UpgradedOriginals.Contains(c)?1:0)).All(x=>x)&&
            UpgradedOriginals.All(c=>c.CurrentUpgradeLevel==1);
        internal GenericEventV7Observation Start(){var p=Session.Read();Check(p.Status=="ready","transform parent ready");Check(Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","transform parent dispatch");return Session.Read();}
        internal object Child(GenericEventV7Observation c)=>Session.ReadCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal).Value;
        internal void Act(GenericEventV7Observation c,string action){var o=(CardSelectionV1Observation)Child(c);Check(o.Status=="ready"&&o.LegalActions.Contains(action),"transform legal "+action+" was "+o.Status);Check(Session.ApplyCardChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,o.DecisionId,action).Value is CardSelectionV1DispatchReceipt,"transform dispatch "+action);}
        public void Dispose(){Session.Dispose();CardSelectCmd.Selector=null;CardCmd.Handler=null;NativeHook.Modifier=null;CardTransformation.Generator=null;NRun.Instance=null;NEventRoom.Instance=null;NMapScreen.Instance=null;}
    }
    private static void TransformTests()
    {
        foreach(string name in new[]{"FIRST_TRANSFORM","ANOTHER_TRANSFORM","HELD_OUT_TRANSFORM"})foreach(int count in new[]{1,2,8})foreach(bool manual in new[]{false,true})
        {
            using var f=new TransformFixture(name,count,manual:manual);var c=f.Start();Check(c.Status=="child","transform admission");foreach(int i in Enumerable.Range(0,count).Reverse())f.Act(c,"select:"+i);f.Act(c,"confirm");
            Check(f.Child(c) is CardSelectionV1ResolvedResult,"transform witnessed resolution");Check(f.CompletionValid,"transform actual append effect");var p=f.Session.Read();Check(p.Phase=="proceed"&&p.CompletedCardChildren==1,"transform cumulative completion");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete"&&f.OptionCalls==2&&f.SelectCalls==count&&f.ConfirmCalls==1,"transform exact dispatch counts");
        }
        foreach(int[] batches in new[]{new[]{1,1},new[]{1,2},new[]{2,1},Enumerable.Repeat(1,8).ToArray()})
        {int count=batches.Sum();using var f=new TransformFixture("BATCHES",count,batchSizes:batches,substitute:true);var c=f.Start();foreach(int i in Enumerable.Range(0,count).Reverse())f.Act(c,"select:"+i);f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid&&f.BatchCount==batches.Length,"sequential disjoint batches");Check(f.FinalCards.All(x=>!f.InitialCards.Contains(x)),"modifier final refs observed");}
        using(var f=new TransformFixture("DEFERRED",2,delayedCreation:true,delayedCompletion:true,partialInsertion:true,deferredConfirm:true))
        {Check(f.Start().Status=="waiting","transform waits creation");f.CreationGate.SetResult();var c=f.Session.Read();f.Act(c,"select:1");f.Act(c,"select:0");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation a&&a.Status=="waiting","confirm deferred");f.AdvanceConfirm();Check(f.Player.Deck.Cards.Count==f.Cards.Length-1,"remove all then one insert actual length");Check(f.Child(c) is CardSelectionV1Observation b&&b.Status=="waiting","partial inserted journal");f.AdvanceInsertion();Check(f.Child(c) is CardSelectionV1Observation d&&d.Status=="waiting","full deck waits command");f.AdvanceInsertion();Check(f.Child(c) is CardSelectionV1Observation e&&e.Status=="waiting","full effect waits callback");f.CompletionGate.SetResult();Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid,"all tasks complete");}
        foreach(string fault in new[]{"initial_baseline","initial_duplicate","initial_owner","initial_run","final_baseline","final_duplicate","final_other_initial","result_default","result_reverse","result_unknown","result_missing","result_array","duplicate_choice","nested","notification","notification_owner","notification_run","baseline_owner","baseline_run","order","published_level","callback","cancel_callback","command","cancel_command","removed_fault","inserted_fault","request","screen"})
        {
            using var f=new TransformFixture(fault,2);CardModel? reused=null;
            switch(fault)
            {
                case "initial_baseline":f.Generate=_=>f.Cards[^1];break;
                case "initial_duplicate":f.Generate=_=>reused??=f.NewCard("Shared");break;
                case "initial_owner":f.Generate=_=>new CardModel{Owner=new Player()};break;
                case "initial_run":f.Generate=_=>{var c=f.NewCard("WrongRun");c.RunOverride=new RunState();return c;};break;
                case "final_baseline":f.Modify=_=>f.Cards[^1];break;
                case "final_duplicate":f.Modify=_=>reused??=f.NewCard("Shared");break;
                case "final_other_initial":f.Modify=_=>f.InitialCards[1];break;
                case "result_default":f.Results=x=>new List<CardPileAddResult>{default,default};break;
                case "result_reverse":f.Results=x=>{x.Reverse();return x;};break;
                case "result_unknown":f.Results=x=>{x[0]=new CardPileAddResult{success=true,cardAdded=f.NewCard("Unknown")};return x;};break;
                case "result_missing":f.Results=x=>x.Take(1).ToList();break;
                case "result_array":f.Results=x=>x.ToArray();break;
                case "duplicate_choice":f.DuplicateChoice=true;break;
                case "nested":f.NestedCommand=true;break;
                case "notification":f.Player.Deck.CardAdded=_=>f.Player.Deck.Cards.Add(f.NewCard("Extra"));break;
                case "notification_owner":f.Player.Deck.CardAdded=card=>card.Owner=new Player();break;
                case "notification_run":f.Player.Deck.CardAdded=card=>card.RunOverride=new RunState();break;
                case "baseline_owner":f.Player.Deck.CardAdded=_=>f.Cards[^1].Owner=new Player();break;
                case "baseline_run":f.Player.Deck.CardAdded=_=>f.Cards[^1].RunOverride=new RunState();break;
                case "order":f.AfterEffect=()=>f.Player.Deck.Cards.Reverse();break;
                case "published_level":f.AfterEffect=()=>f.FinalCards[0].CurrentUpgradeLevel++;break;
                case "callback":f.FaultCallback=true;break;case "cancel_callback":f.CancelCallback=true;break;
                case "command":f.FaultCommand=true;break;case "cancel_command":f.CancelCommand=true;break;
                case "removed_fault":f.FaultAfterRemoval=true;break;case "inserted_fault":f.FaultAfterInsertion=true;break;
                case "request":f.RequestResult=_=>new[]{f.Cards[0],f.Cards[2]};break;
                case "screen":f.ScreenResult=_=>new[]{f.Cards[0],f.Cards[2]};break;
            }
            var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","transform rejects "+fault);Check(f.ConfirmCalls==1,"failed transform no retry");
        }
        foreach(string mutation in new[]{"holder","model","card","missing","extra","before","after","confirm"})
        {using var f=new TransformFixture(mutation,2);var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");_=f.Child(c);var h=(NPreviewCardHolder)f.Before.Children[0];switch(mutation){case "holder":f.Before.Children[0]=new NPreviewCardHolder{CardNode=h.CardNode};break;case "model":h.CardNode.Model=f.Cards[2];break;case "card":h.CardNode=new NCard{Model=f.Cards[0]};break;case "missing":f.Before.Children.RemoveAt(0);break;case "extra":f.Before.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=f.Cards[0]}});break;case "before":f.TransformPreview.Bind("%Before",new Control());break;case "after":f.TransformPreview.Bind("%After",new Control());break;case "confirm":f.Preview.Bind("Confirm",new NConfirmButton());break;}Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported"&&f.ConfirmCalls==0,"transform preview retention "+mutation);}
        foreach(string bad in new[]{"variable","cancelable","domain","predicate_type","predicate_flag"})
        {using var f=new TransformFixture(bad,2,bad=="domain"?2:10);if(bad=="variable")f.MinimumOverride=1;if(bad=="cancelable")f.Cancelable=true;if(bad=="predicate_type"){f.Cards[0].Type=6;f.WrongDomain=true;}if(bad=="predicate_flag"){f.Cards[0].IsTransformable=false;f.WrongDomain=true;}Check(f.Start().Status=="unsupported","transform admission rejects "+bad);}
        foreach(bool stale in new[]{false,true})
        {
            using var f=new TransformFixture("MIXED_TEMPORARIES",8,substitute:true);f.RepeatTransforms=1;f.ContinueWithUpgrade=true;
            var c=f.Start();
            for(int episode=0;episode<2;episode++)
            {
                foreach(int i in Enumerable.Range(0,8).Reverse())f.Act(c,"select:"+i);f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult,"mixed transform resolves");
                var p=f.Session.Read();Check(p.CompletedCardChildren==episode+1&&p.Status=="ready","mixed next family ready");f.Session.Apply(p.DecisionId,"choose:0");c=f.Session.Read();
            }
            Check(c.Status=="child"&&f.InitialCards.Count==16&&f.FinalCards.Count==16,"32 shared transform temporaries before upgrade");
            if(stale)f.RunState.CloneOverride=_=>f.InitialCards[0];
            f.Act(c,"select:0");f.Act(c,"select:1");
            if(stale)Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","stale transform temporary cannot become upgrade clone");
            else{f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult&&f.CompletionValid,"shared bound permits next upgrade");var p=f.Session.Read();Check(p.CompletedCardChildren==3&&p.Phase=="proceed","three mixed completions retained");}
        }
        using(var f=new TransformFixture("REUSED_TASK",1))
        {
            f.RepeatTransforms=1;f.ReuseCommandTask=true;var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1ResolvedResult,"first command task generation resolves");
            var parent=f.Session.Read();f.Session.Apply(parent.DecisionId,"choose:0");c=f.Session.Read();f.Act(c,"select:0");f.Act(c,"confirm");
            Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","successful task cannot certify later child generation");
        }
        TransformHookTests();
        using(var f=new TransformFixture("LOST",1)){f.LostConfirm=true;var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");for(int i=0;i<257;i++){var o=f.Child(c);if(i==256)Check(o is CardSelectionV1Observation x&&x.Status=="unsupported","transform pending bound");}Check(f.ConfirmCalls==1&&f.BatchCount==0,"transform lost confirm no retry");}
    }
}

internal static partial class Program
{
    private static void TransformHookTests()
    {
        var targets=new[]{
            typeof(CardSelectCmd).GetMethod(nameof(CardSelectCmd.FromDeckForTransformation))!,
            typeof(NDeckTransformSelectScreen).GetMethod(nameof(NDeckTransformSelectScreen.ShowScreen))!,
            typeof(CardCmd).GetMethod(nameof(CardCmd.Transform))!,
            typeof(CardTransformation).GetMethod(nameof(CardTransformation.GetReplacement))!,
            typeof(NativeHook).GetMethod(nameof(NativeHook.ModifyCardBeingAddedToDeck))!,
            typeof(CardPile).GetMethod(nameof(CardPile.AddInternal))!
        };
        foreach(var target in targets)
        {
            var foreign=new Harmony("fixture.transform.target");var prefix=typeof(Program).GetMethod(nameof(ForeignPrefix),System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static)!;
            using(var f=new TransformFixture("HOOK",1))
            {var c=f.Start();foreign.Patch(target,prefix:new HarmonyMethod(prefix));Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","transform exact patch ownership "+target.Name);}
            Check(Harmony.GetPatchInfo(target)?.Prefixes.Any(p=>p.PatchMethod==prefix)==true,"transform foreign patch preserved");foreign.Unpatch(target,prefix);
        }
        foreach(bool worker in new[]{false,true})
        {
            using var f=new TransformFixture("FOREIGN_COMMAND",1,deferredConfirm:true);var c=f.Start();f.Act(c,"select:0");f.Act(c,"confirm");
            Action invoke=()=>{try{CardCmd.Transform(new[]{new CardTransformation(f.Cards[0])},new Rng(),CardPreviewStyle.None).GetAwaiter().GetResult();}catch{}};
            if(worker)Task.Run(invoke).GetAwaiter().GetResult();else invoke();
            Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="unsupported","same selected original foreign command cannot consume confirm "+worker);
        }
        var old=new TransformFixture("OLD_COMMAND",2,partialInsertion:true);var child=old.Start();old.Act(child,"select:0");old.Act(child,"select:1");old.Act(child,"confirm");Check(old.HasPendingInsertion,"old command deferred");old.Dispose();
        using(var fresh=new TransformFixture("NEW_GENERATION",1))
        {var c=fresh.Start();old.AdvanceInsertion();Check(old.FinalCards.Count==2,"stale native continuation still ran");fresh.Act(c,"select:0");fresh.Act(c,"confirm");Check(fresh.Child(c) is CardSelectionV1ResolvedResult&&fresh.CompletionValid,"old command scope cannot attach new generation");}
        foreach(string mutation in new[]{"level","key","order","extra","remove","owner","run","baseline_owner","baseline_run"})
        {
            using var f=new TransformFixture("PUBLISHED",2,partialInsertion:true);var c=f.Start();f.Act(c,"select:0");f.Act(c,"select:1");f.Act(c,"confirm");Check(f.Child(c) is CardSelectionV1Observation o&&o.Status=="waiting","published insertion pending");
            switch(mutation){case "owner":f.FinalCards[0].Owner=new Player();break;case "run":f.FinalCards[0].RunOverride=new RunState();break;case "baseline_owner":f.Cards[^1].Owner=new Player();break;case "baseline_run":f.Cards[^1].RunOverride=new RunState();break;case "level":f.FinalCards[0].CurrentUpgradeLevel++;break;case "key":f.FinalCards[0].Id.Entry="Changed";break;case "order":f.Player.Deck.Cards.Reverse();break;case "extra":f.Player.Deck.Cards.Add(f.NewCard("Extra"));break;case "remove":f.Player.Deck.Cards.Remove(f.FinalCards[0]);break;}
            Check(f.Child(c) is CardSelectionV1Observation rejected&&rejected.Status=="unsupported","published witness rejects "+mutation);
        }
    }
}
