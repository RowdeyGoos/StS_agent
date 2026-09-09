using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
internal static partial class Program {
    internal sealed class ResultsFixture:IDisposable {
        internal readonly TransformFixture World;
        internal readonly NButton Confirm=new();
        internal readonly List<CardPileAddResult> Results=new();
        internal NSimpleCardsViewScreen Screen=null!;
        internal readonly TaskCompletionSource Creation=new(),Completion=new();
        internal bool DelayCreation,DelayCompletion,Defer,Lost,SecondScreen;
        internal int Confirms;internal Action? Pending;
        internal NCapstoneContainer Container=>World.Run.GlobalUi.CapstoneContainer;
        internal GenericEventV7Session Session=>World.Session;
        internal ResultsFixture(int count=3,int dialogue=1) {
            World=new TransformFixture("RESULTS",1,domain:count,eventModel:new AncientEventModel());AncientLayout(World.Room,World.Model,dialogue);
            CardCmd.Handler=(_,_,_)=>{
                // Automatic change precedes ShowScreen; the acknowledgment owns only the resulting deck.
                for(int i=0;i<count;i++){World.Player.Deck.Cards.Remove(World.Cards[i]);var card=World.NewCard("Final_"+i);World.Player.Deck.Cards.Add(card);Results.Add(new CardPileAddResult{success=true,cardAdded=card});}
                return Task.FromResult<IEnumerable<CardPileAddResult>>(Results);
            };
            World.Room.Layout.OptionButtons[0].Option.Callback=async()=>{
                World.OptionCalls++;if(DelayCreation)await Creation.Task;
                var results=(await CardCmd.Transform(Array.Empty<CardTransformation>(),new MegaCrit.Sts2.Core.Random.Rng(),MegaCrit.Sts2.Core.Nodes.CommonUi.CardPreviewStyle.None)).ToList();Results.Clear();Results.AddRange(results);
                NSimpleCardsViewScreen.ShowScreen(Results,new MegaCrit.Sts2.Core.Localization.LocString("relics","RESULTS"));
                if(SecondScreen)NSimpleCardsViewScreen.ShowScreen(Results,new MegaCrit.Sts2.Core.Localization.LocString("relics","SECOND"));
                if(DelayCompletion)await Completion.Task;Finish(World);
            };
            NSimpleCardsViewScreen.Factory=(results,_)=>{Screen=new NSimpleCardsViewScreen();Screen.Setup(results,Confirm);Container.Open(Screen);return Screen;};
            Confirm.Clicked=()=>{Confirms++;if(Lost)return;Action close=()=>Container.Close();if(Defer)Pending=close;else close();};
        }
        internal GenericEventV7Observation Start()=>World.Start();
        internal GenericEventV7RewardRead Read(GenericEventV7Observation c)=>((GenericEventV7RewardChildRead)Session.ReadChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal)).Value;
        internal string Apply(GenericEventV7Observation c,string decision)=>((GenericEventV7RewardChildApply)Session.ApplyChild(c.Child!.ParentDecisionId,c.Child.ParentActionId,c.Child.Ordinal,decision,"confirm")).Value.Outcome;
        internal void Act(GenericEventV7Observation c){var r=Read(c);Check(r.Status=="ready","results ready "+r.Status);Check(Apply(c,r.DecisionId)=="accepted","results confirm");}
        public void Dispose(){World.Dispose();NSimpleCardsViewScreen.Factory=null;}
    }
    internal static void Finish(TransformFixture world){
        world.Model.IsFinished=true;world.Room.Layout.OptionButtons.Clear();var option=new EventOption{TextKey="PROCEED",IsProceed=true,Callback=()=>{world.OptionCalls++;world.Map.IsOpen=true;world.Map.IsTravelEnabled=true;return Task.CompletedTask;}};
        var button=new NEventOptionButton{Option=option,Event=world.Model};button.Bind("%Text",new MegaRichTextLabel{Text="Proceed"});world.Room.Layout.OptionButtons.Add(button);
    }
    internal static NCombatEventLayout CombatLayout(TransformFixture world){var layout=new NCombatEventLayout();layout.OptionButtons.AddRange(world.Room.Layout.OptionButtons);world.Room.Layout=layout;return layout;}
    private sealed class ResultsProbe:IGenericEventV7ResultsAdapter {
        internal Action? OnDispose;
        public GenericEventV7ResultsCapture Capture()=>new("ready",new[]{new GenericEventV7RewardCard(0,"CARD",0)});
        public void Confirm(){}public void Dispose()=>OnDispose?.Invoke();
    }
    private static void SurfaceTests(){
        foreach(int count in new[]{1,3,10,64}) {
            using var f=new ResultsFixture(count);var c=f.Start();Check(c.Status=="child"&&c.Child!.Kind=="card_results"&&c.Child.OfferCount==count,"results admission "+c.Status+" "+f.World.Adapter.LastDiagnostic);
            var read=f.Read(c);Check(read.Cards.Count==count&&read.Phase=="acknowledge","exact public results");f.Act(c);Check(f.Read(c).Status=="resolved"&&f.Confirms==1&&!f.Container.InUse,"results acknowledged");
            var p=f.Session.Read();Check(p.Phase=="proceed"&&p.CompletedCardChildren==1&&p.ParentReconciled==1&&p.Effects=="unverified","results parent reconciles");f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","results map return");
        }
        foreach(string fault in new[]{"button","backing","cards","results","model","owner","deck","capstone","container","overlay","hidden","disabled","lost","fault","foreign_close"}) {
            using var f=new ResultsFixture();var c=f.Start();var r=f.Read(c);
            switch(fault){
                case "button":f.Screen.Bind("ConfirmButton",new NButton());break;
                case "backing":OfferFixture.Set(f.Screen,"_confirmButton",new NButton());break;
                case "cards":typeof(NCardsViewScreen).GetField("_cards",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(f.Screen,f.Results.Select(x=>x.cardAdded).ToArray());break;
                case "results":f.Results.Reverse();break;
                case "model":f.Results[0].cardAdded.Id.Entry="Changed";break;
                case "owner":f.Results[0].cardAdded.Owner=new();break;
                case "deck":f.World.Player.Deck.Cards.Reverse();break;
                case "capstone":f.Container.Open(new NSimpleCardsViewScreen());break;
                case "container":f.World.Run.GlobalUi.CapstoneContainer=new();break;
                case "overlay":f.World.Overlays.Screens.Add(new Control());break;
                case "hidden":f.Confirm.Visible=false;break;case "disabled":f.Confirm.IsEnabled=false;break;
                case "lost":f.Lost=true;break;
                case "fault":f.World.Player.Deck.Cards.Add(f.World.NewCard("Foreign"));break;
                case "foreign_close":f.Container.Close();break;
            }
            Check((f.Apply(c,r.DecisionId)=="accepted")==f.Lost,"results stale boundary "+fault);
            var end=f.Read(c);for(int i=0;i<257&&end.Status=="waiting";i++)end=f.Read(c);
            Check(end.Status=="unsupported"&&f.Confirms==(f.Lost?1:0),"results fail closed "+fault+" "+end.Status);
        }
        using(var f=new ResultsFixture(){DelayCreation=true,DelayCompletion=true,Defer=true}) {
            Check(f.Start().Status=="waiting","results delayed creation");f.Creation.SetResult();var c=f.Session.Read();f.Act(c);Check(f.Read(c).Status=="waiting","deferred results close");f.Pending!();Check(f.Read(c).Status=="waiting","results waits real chosen");f.Completion.SetResult();Check(f.Read(c).Status=="resolved","results delayed completion");
        }
        using(var f=new ResultsFixture(){DelayCompletion=true}){var c=f.Start();f.Act(c);f.Completion.SetException(new InvalidOperationException());Check(f.Read(c).Status=="unsupported","late chosen fault");}
        foreach(int count in new[]{0,65}){using var f=new ResultsFixture(count);Check(f.Start().Status=="unsupported","results count guard");}
        using(var f=new ResultsFixture(){SecondScreen=true}){Check(f.Start().Status=="unsupported","second results rejected");}
        using(var f=new ResultsFixture()){f.Container.Open(new NSimpleCardsViewScreen());Check(f.Session.Read().Status=="unsupported"&&f.World.OptionCalls==0,"unowned capstone blocks parent");}
        foreach(string name in new[]{"PUNCH_OFF_NAB","OTHER_LAYOUT","HELD_OUT_LAYOUT"}) {
            using var world=new TransformFixture(name,1);CombatLayout(world);world.Room.Layout.OptionButtons[0].Option.Callback=()=>{world.OptionCalls++;Finish(world);return Task.CompletedTask;};
            var p=world.Start();Check(p.Status=="ready"&&p.Phase=="proceed"&&p.ParentReconciled==1,"combat visuals ordinary branch");world.Session.Apply(p.DecisionId,"choose:0");Check(world.Session.Read().Status=="complete","combat visuals map");
        }
        foreach(string fault in new[]{"started","replaced","missing","active_after","foreign_capstone"}) {
            using var world=new TransformFixture(fault,1);var layout=CombatLayout(world);var p=world.Session.Read();
            switch(fault){case "started":layout.HasCombatStarted=true;break;case "replaced":layout.EmbeddedCombatRoom=new();break;case "missing":layout.EmbeddedCombatRoom=null;break;case "foreign_capstone":world.Run.GlobalUi.CapstoneContainer.Open(new NSimpleCardsViewScreen());break;case "active_after":world.Room.Layout.OptionButtons[0].Option.Callback=()=>{world.OptionCalls++;layout.HasCombatStarted=true;return Task.CompletedTask;};break;}
            var receipt=world.Session.Apply(p.DecisionId,"choose:0");Check((receipt.Outcome=="accepted")== (fault=="active_after"),"combat boundary "+fault);Check(world.Session.Read().Status=="unsupported"&&world.OptionCalls==(fault=="active_after"?1:0),"combat no false handoff "+fault);
        }
        using(var f=new OfferFixture(false)){CombatLayout(f.World);var c=f.Start();f.Act(c,"choose:1");Check(f.Read(c).Status=="resolved","combat layout composes existing child");var p=f.Session.Read();f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","combat layout child map");}
        foreach(string variant in new[]{"success","started","replaced"}) {
            using var f=new ItemFixture("PUNCH_OFF_NAB","relic",index:0);var layout=new NCombatEventLayout();layout.OptionButtons.AddRange(f.Room.Layout.OptionButtons);f.Room.Layout=layout;
            var callback=layout.OptionButtons[0].Option.Callback;
            layout.OptionButtons[0].Option.Callback=async()=>{var injury=new CardModel{Owner=f.Player};injury.Id.Entry="INJURY";f.Player.Deck.Cards.Add(injury);await callback();};
            var c=f.Start();Check(c.Status=="child","Punch Off relic child");
            if(variant=="started")layout.HasCombatStarted=true;if(variant=="replaced")layout.EmbeddedCombatRoom=new();
            if(variant!="success"){Check(f.Child(c) is Sts2AgentBridge.Successors.ItemV1.ItemV1Observation {Status:"unsupported"}&&f.CollectCalls==0,"combat ownership during item child");continue;}
            f.Collect(c);Check(f.Child(c) is Sts2AgentBridge.Successors.ItemV1.ItemV1ResolvedResult&&f.Player.Deck.Cards.Last().Id.Entry=="INJURY","Punch Off relic and prior grant");var p=f.Session.Read();f.Session.Apply(p.DecisionId,"choose:0");Check(f.Session.Read().Status=="complete","Punch Off relic map");
        }
        using(var f=new ResultsFixture()) {var factory=NSimpleCardsViewScreen.Factory!;NSimpleCardsViewScreen.Factory=(cards,text)=>{factory(cards,text);return new NSimpleCardsViewScreen();};Check(f.Start().Status=="unsupported","returned screen must own capstone");}
        foreach(bool duplicate in new[]{false,true}) {
            using var f=new ResultsFixture();var factory=NSimpleCardsViewScreen.Factory!;
            NSimpleCardsViewScreen.Factory=(cards,text)=>{var result=factory(cards,text);if(duplicate)cards[1]=cards[0];else cards[0]=new CardPileAddResult{success=false,cardAdded=cards[0].cardAdded};return result;};
            Check(f.Start().Status=="unsupported","changed results before publication");
        }
        foreach(int mode in new[]{0,1,2}) {
            var adapter=new ResultsProbe();var session=new GenericEventV7ResultsSession(new string('e',32),1,adapter);
            adapter.OnDispose=()=>{try{if(mode==0)session.Read();else if(mode==1)session.Apply("bad","confirm");else session.Dispose();}catch{}};
            bool blocked=false;try{session.Dispose();}catch{blocked=true;}Check(blocked,"results cleanup reentry");
        }
        bool failed=false;try{using var hooks=new GenericEventV7Hooks(n=>{if(n==28)throw new InvalidOperationException();},null);}catch{failed=true;}Check(failed&&HarmonyLib.Harmony.GetPatchInfo(typeof(NSimpleCardsViewScreen).GetMethod(nameof(NSimpleCardsViewScreen.ShowScreen))!)?.Owners.Count is null or 0,"results hook rollback");using var clean=new GenericEventV7Hooks();
    }
}
