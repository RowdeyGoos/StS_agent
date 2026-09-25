using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.GenericEventV7;

namespace MegaCrit.Sts2.Core.Models.Relics
{
    public sealed class PreciseScissors:OfferRelicFixture {public PreciseScissors(){Id.Entry="PRECISE_SCISSORS";DynamicVars["Cards"]=new(){IntValue=1};}}
    public sealed class PrecariousShears:OfferRelicFixture {public PrecariousShears(){Id.Entry="PRECARIOUS_SHEARS";DynamicVars["Cards"]=new(){IntValue=2};}}
    public sealed class Pomander:OfferRelicFixture {public Pomander(){Id.Entry="POMANDER";DynamicVars["Cards"]=new(){IntValue=1};}}
    public sealed class NewLeaf:OfferRelicFixture {public NewLeaf(){Id.Entry="NEW_LEAF";DynamicVars["Cards"]=new(){IntValue=1};}}
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static partial class CardPileCmd
    {
        public static Func<CardModel,bool,Task>? RemoveHandler;
        [MethodImpl(MethodImplOptions.NoInlining)]public static Task RemoveFromDeck(CardModel card,bool showPreview=true)=>RemoveHandler!(card,showPreview);
    }
}
internal static partial class Program
{
    private sealed class CompoundDeckFixture:IDisposable
    {
        internal readonly CompoundRewardFixture Parent;
        internal readonly TaskCompletionSource<IEnumerable<CardModel>> Selected=new();
        internal readonly TaskCompletionSource Creation=new(),Completion=new(),Mutation=new();
        internal readonly Control Container=new(){Visible=false},Preview=new();
        internal readonly NCardGrid Grid=new();
        internal readonly NBackButton Back=new(),PreviewBack=new();
        internal readonly NConfirmButton Confirm=new();
        internal readonly List<CardModel> Chosen=new();
        internal NCardGridSelectionScreen? Screen;
        internal bool DelayCreation,DelayCompletion,DelayMutation,RetainScreen,Fault,WrongRequest,WrongEffect,DirectRemoval,DirectGeneric,WrongTransformResult;
        internal int Inputs;
        internal readonly string Kind;
        internal readonly int Count;
        internal CardModel NewCard(string key){var card=new CardModel{Owner=Parent.World.Player,IsUpgradable=true};card.Id.Entry=key;return card;}
        internal CompoundDeckFixture(CompoundRewardFixture parent,string kind,bool nested=false,int index=0)
        {
            Parent=parent;Kind=kind;Count=kind=="shears"?2:1;
            var player=parent.World.Player;
            foreach(var card in player.Deck.Cards){card.IsUpgradable=true;card.IsRemovable=true;card.IsTransformable=true;}
            OfferRelicFixture relic=kind switch {"upgrade"=>new Pomander(),"transform"=>new NewLeaf(),"shears"=>new PrecariousShears(),_=>new PreciseScissors()};
            ((RelicReward)(nested?parent.Child:parent.Root).Rewards[index]).Relic=relic;
            relic.Handler=async()=>{
                var prefs=new CardSelectorPrefs(Count,Count){Prompt=kind=="transform"?CardSelectorPrefs.TransformSelectionPrompt:CardSelectorPrefs.RemoveSelectionPrompt};
                var selected=(kind=="upgrade"?await CardSelectCmd.FromDeckForUpgrade(player,prefs):
                    kind=="transform"?await CardSelectCmd.FromDeckForTransformation(player,prefs):
                    DirectGeneric?await CardSelectCmd.FromDeckGeneric(player,prefs,c=>c.IsRemovable):await CardSelectCmd.FromDeckForRemoval(player,prefs)).ToArray();
                foreach(var card in selected) {
                    var target=WrongEffect?parent.World.Cards.Last():card;
                    if(kind=="upgrade")target.UpgradeInternal();
                    else if(kind=="transform")await CardCmd.Transform(new[]{new CardTransformation(target)},new(),CardPreviewStyle.None);
                    else if(DirectRemoval)player.Deck.Cards.Remove(target);
                    else await CardPileCmd.RemoveFromDeck(target);
                }
                if(kind=="shears")player.Creature.LoseHpInternal(16,default);
                if(DelayCompletion)await Completion.Task;
                if(Fault)throw new InvalidOperationException("deck pickup fault");
            };
            Activate();
        }
        internal void Activate()
        {
            var player=Parent.World.Player;
            CardSelectCmd.Handler=(_,prefs)=>Select(prefs,"upgrade");
            CardSelectCmd.TransformHandler=(_,prefs,_)=>Select(prefs,"transform");
            CardSelectCmd.RemovalHandler=(p,prefs,_)=>CardSelectCmd.FromDeckGeneric(p,prefs,c=>c.IsRemovable);
            CardSelectCmd.GenericHandler=(_,prefs,_)=>Select(prefs,"remove");
            NDeckUpgradeSelectScreen.Factory=(cards,_,_)=>Create(new NDeckUpgradeSelectScreen(),cards);
            NDeckTransformSelectScreen.Factory=(cards,_,_)=>Create(new NDeckTransformSelectScreen(),cards);
            NDeckCardSelectScreen.Factory=(cards,_)=>Create(new NDeckCardSelectScreen(),cards);
            CardPileCmd.RemoveHandler=async(card,_)=>{player.Deck.Cards.Remove(card);if(DelayMutation)await Mutation.Task;};
            CardTransformation.Generator=card=>NewCard("TRANSFORMED_"+card.Id.Entry);
            CardCmd.Handler=async(values,rng,_)=>{
                var rows=new List<CardPileAddResult>();
                var generated=new List<(CardModel Card,int Index)>();
                foreach(var value in values) {
                    int index=player.Deck.Cards.IndexOf(value.Original);var initial=value.GetReplacement(rng);player.Deck.Cards.Remove(value.Original);generated.Add((initial,index));
                }
                foreach(var row in generated.OrderBy(v=>v.Index)) {
                    var initial=row.Card;List<AbstractModel>? modifications=null;
                    var final=MegaCrit.Sts2.Core.Hooks.Hook.ModifyCardBeingAddedToDeck(player.RunState,initial,ref modifications);
                    player.Deck.AddInternal(final,-1,false);
                    if(DelayMutation)await Mutation.Task;
                    rows.Add(new(){success=true,cardAdded=WrongTransformResult?NewCard("FOREIGN_RESULT"):final});
                }
                return rows.Count==0?Array.Empty<CardPileAddResult>():rows;
            };
        }
        private async Task<IEnumerable<CardModel>> Select(CardSelectorPrefs prefs,string kind)
        {
            if(DelayCreation)await Creation.Task;
            var player=Parent.World.Player;
            var cards=player.Deck.Cards.Where(c=>kind=="upgrade"?c.IsUpgradable:kind=="transform"?(int)c.Type!=6&&c.IsTransformable:c.IsRemovable).ToArray();
            if(kind=="remove")cards=cards.OrderBy(c=>(int)c.Type==5?-1:player.Deck.Cards.IndexOf(c)).ToArray();
            if(cards.Length<=prefs.MinSelect)return cards;
            NCardGridSelectionScreen screen=kind=="upgrade"?NDeckUpgradeSelectScreen.ShowScreen(cards,prefs,player.RunState):kind=="transform"?
                NDeckTransformSelectScreen.ShowScreen(cards,c=>new CardTransformation(c),prefs):NDeckCardSelectScreen.Create(cards,prefs);
            var result=(await screen.CardsSelected()).ToArray();
            if(RetainScreen){screen.Visible=true;if(!Parent.World.Overlays.Screens.Contains(screen))Parent.World.Overlays.Screens.Add(screen);}else Close();
            return WrongRequest?new[]{Parent.World.Cards.Last()}:result;
        }
        private T Create<T>(T screen,IReadOnlyList<CardModel> cards) where T:NCardGridSelectionScreen
        {
            Screen=screen;screen.SelectionTask=Selected.Task;bool single=Kind is "upgrade" or "transform";
            screen.Bind("%CardGrid",Grid);screen.Bind("%Close",Back);
            screen.Bind(Kind=="upgrade"?"%UpgradeSinglePreviewContainer":"%PreviewContainer",Container);
            if(Kind=="transform"){var preview=new NTransformPreview();preview.Bind("%Before",Preview);preview.Bind("%After",new Control());Container.Bind("TransformPreview",preview);}
            else Container.Bind(Kind=="upgrade"?"UpgradePreview":"%Cards",Kind=="upgrade"?new NUpgradePreview():Preview);
            Container.Bind(single?"Confirm":"%PreviewConfirm",Confirm);Container.Bind(single?"Cancel":"%PreviewCancel",PreviewBack);
            foreach(var card in cards.Reverse()) {
                var material=new ShaderMaterial();
                var holder=new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card,CardHighlight=new(){Material=material}},Hitbox=new NClickableControl()};
                holder.Selected=()=>{
                    Inputs++;
                    if(Chosen.Contains(card)){Chosen.Remove(card);material.Width=0;}else{Chosen.Add(card);material.Width=BitConverter.Int32BitsToSingle(1033476506);}
                    if(Chosen.Count==Count) {
                        Container.Visible=true;Back.IsEnabled=false;
                        if(Kind=="upgrade")Container.GetNodeOrNull<NUpgradePreview>("UpgradePreview")!.Card=card;
                        else foreach(var c in Chosen)Preview.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=c}});
                        foreach(var h in Grid.CurrentlyDisplayedCardHolders)((ShaderMaterial)h.CardNode!.CardHighlight.Material!).Width=0;
                    }
                };Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            PreviewBack.Clicked=()=>{Inputs++;Container.Visible=false;Back.IsEnabled=true;Chosen.Clear();Preview.Children.Clear();foreach(var h in Grid.CurrentlyDisplayedCardHolders)((ShaderMaterial)h.CardNode!.CardHighlight.Material!).Width=0;};
            Confirm.Clicked=()=>{Inputs++;Selected.SetResult(Chosen.ToArray());};
            Parent.World.Overlays.Screens.Add(screen);ActiveScreenContext.Instance.Current=screen;return screen;
        }
        internal void Close(){if(Screen is not null)Parent.World.Overlays.Screens.Remove(Screen);ActiveScreenContext.Instance.Current=Parent.World.Overlays.Screens.LastOrDefault()??(Control)Parent.World.Room;}
        internal GenericEventV7RewardRead Read(GenericEventV7Observation c)
        {for(int i=0;i<12;i++){var read=Parent.Read(c);if(read.Status!="waiting")return read;}return Parent.Read(c);}
        internal GenericEventV7RewardRead Act(GenericEventV7Observation c,string action){Read(c);Parent.Act(c,action);return Read(c);}
        public void Dispose()
        {
            CardSelectCmd.Handler=null;CardSelectCmd.TransformHandler=null;CardSelectCmd.RemovalHandler=null;CardSelectCmd.GenericHandler=null;
            NDeckUpgradeSelectScreen.Factory=null;NDeckTransformSelectScreen.Factory=null;NDeckCardSelectScreen.Factory=null;
            CardCmd.Handler=null;CardTransformation.Generator=null;CardPileCmd.RemoveHandler=null;MegaCrit.Sts2.Core.Hooks.Hook.Modifier=null;
        }
    }
    private static void CompoundDeckCases()
    {
        using(var f=new CompoundRewardFixture(tail:"curse")) {
            using var second=new CompoundDeckFixture(f,"upgrade",index:1);
            using var first=new CompoundDeckFixture(f,"remove");
            var c=f.Start();f.Act(c,"collect:0");first.Act(c,"select:0");
            Check(first.Act(c,"confirm").Phase=="rewards","first root selector returns to remaining reward");
            second.Activate();second.RetainScreen=true;f.Act(c,"collect:1");second.Act(c,"select:0");var last=second.Act(c,"confirm");
            Check(last.Status=="waiting","second sibling remains closing at root completion");second.Close();last=second.Read(c);
            Check(last.Status=="resolved"&&last.PriorResults.Count==6&&f.World.Session.Read().ParentReconciled==1,
                "retired first selector does not claim the next root selector; final curse follows both");
        }
        foreach(bool nestedRewards in new[]{false,true}) {
            using var f=new CompoundRewardFixture(tail:"curse");using var second=new CompoundDeckFixture(f,"upgrade",index:1){RetainScreen=true};
            using var first=nestedRewards?null:new CompoundOfferFixture(f,"lead");
            var c=f.Start();f.Act(c,"collect:0");
            if(nestedRewards){f.Act(c,"collect:0");f.Act(c,"collect:1");}else f.Act(c,"choose:0");
            var next=f.Act(c,"collect:1");Check(next.Status=="ready","next selector after "+(nestedRewards?"nested rewards":"card offer")+" "+next.Status);
            second.Act(c,"select:0");var read=second.Act(c,"confirm");
            Check(read.Status=="waiting","retired earlier reward/offer does not join sibling closing chain");
            second.Close();Check(second.Read(c).Status=="resolved","mixed sibling selector and final curse resolve");
        }
        foreach(string kind in new[]{"remove","shears","upgrade","transform"})foreach(string mode in new[]{"normal","auto","empty","nested","curse","creation","after","fault","closing","wrong_request","wrong_effect","foreign_deck"}) {
            using var f=new CompoundRewardFixture(tail:mode=="curse"?"curse":null);using var deck=new CompoundDeckFixture(f,kind,mode=="nested");
            deck.DelayCreation=mode=="creation";deck.DelayCompletion=mode=="after";deck.Fault=mode=="fault";deck.RetainScreen=mode=="closing";
            deck.WrongRequest=mode=="wrong_request";deck.WrongEffect=mode=="wrong_effect";
            if(mode is "auto" or "empty")f.World.Player.Deck.Cards.RemoveRange(mode=="empty"?0:1,f.World.Player.Deck.Cards.Count-(mode=="empty"?0:1));
            var c=f.Start();var read=f.Act(c,"collect:0");if(mode=="nested")read=f.Act(c,"collect:0");
            if(mode=="creation"){Check(read.Status=="waiting","compound selector request waits for native creation");deck.Creation.SetResult();}
            read=deck.Read(c);
            if(mode=="foreign_deck"){f.World.Player.Deck.Cards.Last().CurrentUpgradeLevel++;Check(deck.Read(c).Status=="unsupported","foreign survivor mutation rejected");continue;}
            if(mode is not ("auto" or "empty")) {
                Check(read.Status=="ready"&&read.Phase=="deck_"+(kind=="shears"?"remove":kind),"compound deck phase "+kind+" "+mode+" "+read.Status);
                deck.Act(c,"select:0");if(deck.Count==2)deck.Act(c,"select:1");
                if(mode=="normal"){deck.Act(c,"deselect:0");deck.Act(c,"select:0");}
                read=deck.Act(c,"confirm");
            }
            if(mode is "after" or "closing") {
                Check(read.Status=="waiting"&&f.World.Session.Read().ParentReconciled==0,"compound deck retains pending task/closing UI");
                if(mode=="after")deck.Completion.SetResult();else deck.Close();read=deck.Read(c);
            }
            if(mode is "fault" or "wrong_request" or "wrong_effect"){Check(read.Status=="unsupported","compound deck mismatch stops "+kind+" "+mode);continue;}
            if(mode is "nested" or "curse")read=f.Act(c,"collect:1");
            Check(read.Status=="resolved"&&f.World.Session.Read().ParentReconciled==1,"compound deck finishes parent "+kind+" "+mode+" "+read.Status);
        }
        foreach(string mode in new[]{"generic","direct","delay_remove","delay_transform","bad_transform","egg_transform","foreign_wait"}) {
            bool transform=mode.Contains("transform");using var f=new CompoundRewardFixture();using var deck=new CompoundDeckFixture(f,transform?"transform":"remove");
            deck.DirectGeneric=mode=="generic";deck.DirectRemoval=mode=="direct";deck.DelayMutation=mode.StartsWith("delay_")||mode=="foreign_wait";
            deck.WrongTransformResult=mode=="bad_transform";
            if(mode=="egg_transform")MegaCrit.Sts2.Core.Hooks.Hook.Modifier=(_,card)=>{card.UpgradeInternal();return card;};
            var c=f.Start();f.Act(c,"collect:0");deck.Act(c,"select:0");var read=deck.Act(c,"confirm");
            if(mode=="foreign_wait"){f.World.Player.Gold++;Check(deck.Read(c).Status=="unsupported","foreign mutation cannot enter delayed remove");continue;}
            if(mode.StartsWith("delay_")){Check(read.Status=="waiting","actual deck command task retained");deck.Mutation.SetResult();read=deck.Read(c);}
            Check(read.Status==(mode is "direct" or "bad_transform"?"unsupported":"resolved"),"compound command proof "+mode+" "+read.Status);
        }
    }
}
