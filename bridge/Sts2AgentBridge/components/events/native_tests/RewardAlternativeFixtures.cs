using System;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Entities.Rewards;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Items.Native;
using Sts2AgentBridge.Core.Public;

internal static partial class Program
{
    private sealed class AlternativesFixture:IDisposable
    {
        internal readonly CombatItemsFixture World;
        internal readonly NCardRewardSelectionScreen Menu=new();
        internal readonly CardReward Reward;
        internal readonly PaelsWing Wing;
        internal readonly TaskCompletionSource Gate=new();
        internal CardModel[] Cards=Array.Empty<CardModel>();
        internal CardRewardAlternative[] Options;
        internal int Clicks;
        private CardRewardAlternative Skip()=>new("Skip",PostAlternateCardRewardAction.EndSelectionAndDoNotCompleteReward);
        internal AlternativesFixture(string operation,int count=0,bool delayed=false,int items=0)
        {
            World=new(items);
            var player=World.World.Player;
            Reward=new(){Player=player,CanReroll=operation=="reroll",RewardsSetIndex=0};
            Wing=new(){Owner=player,RewardsSacrificed=count};
            if(operation=="sacrifice"){player.Relics.Add(Wing);if(delayed)((OldCoin)Wing.Grant).Gate=Gate.Task;}
            Options=new[]{Skip(),new CardRewardAlternative(operation.ToUpperInvariant(),operation=="reroll"?PostAlternateCardRewardAction.DoNothing:PostAlternateCardRewardAction.EndSelectionAndCompleteReward){OnSelect=operation=="reroll"?Reward.RerollCallback:Wing.OnSacrifice}};
            SetCards("OLD");Reward.RerollHandler=()=>{SetCards("NEW");Options=new[]{Skip()};PopulateMenu();};
            World.Reader.AlternativesFactory=(parent,screen)=>new PinnedRewardAlternatives(parent,screen);
            World.Reader.InventoryFactory=p=>new PinnedRewardInventory(p);
            var button=new NRewardButton{Reward=Reward};World.Screen.Children.Add(button);
            button.Handler=NativeChoice;
            ActiveScreenContext.Instance=new(){Current=World.Screen};
        }
        private void SetCards(string prefix)
        {Cards=Enumerable.Range(0,3).Select(i=>{var c=new CardModel{Owner=World.World.Player};c.Id.Entry=prefix+"_"+i;return c;}).ToArray();Reward.Setup(Cards.Select(c=>new CardCreationResult(c)).ToList());}
        private void PopulateMenu()
        {
            var row=new Control();Menu.Bind("UI/CardRow",row);Menu.Children.Clear();Menu.Children.Add(row);
            for(int i=0;i<Cards.Length;i++){int index=i;var card=Cards[i];row.Children.Add(new NGridCardHolder{CardModel=card,CardNode=new NCard{Model=card},RewardPressed=()=>Menu.Complete(index)});}
            Menu.BindAlternatives(Cards.Select(c=>new CardCreationResult(c)).ToArray(),Options);
        }
        private async Task NativeChoice()
        {
            Reward.BindMenu(Menu);PopulateMenu();World.World.Overlays.Screens.Add(Menu);ActiveScreenContext.Instance.Current=Menu;
            // The pinned CardReward keeps the original alternative table for
            // the invocation; Reroll recreates its visible controls.
            var initial=Options;
            while(true) {
                var index=await Menu.OptionSelected();Clicks++;
                if(index<Cards.Length){World.World.Player.Deck.Cards.Add(Cards[index!.Value]);Reward.SuccessfullySelected=true;break;}
                var option=initial[index!.Value-Cards.Length];await option.OnSelect();
                if(option.AfterSelected==PostAlternateCardRewardAction.DoNothing)continue;
                Reward.SuccessfullySelected=option.AfterSelected==PostAlternateCardRewardAction.EndSelectionAndCompleteReward;break;
            }
            World.World.Overlays.Screens.Remove(Menu);ActiveScreenContext.Instance.Current=World.Screen;
        }
        internal PublicRewardDecisionSnapshot Open()
        {var view=World.Reader.Read();Apply(view,view.LegalActions.First(a=>a.StartsWith("open:",StringComparison.Ordinal)));return World.Reader.Read();}
        internal void Apply(PublicRewardDecisionSnapshot view,string action)
        {PublicRewardActionRequest.TryCreate(view.DecisionId,action,out var request);Check(World.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.Accepted,"alternative fixture input accepted");}
        public void Dispose()
        {
            try{World.Reader.Dispose();}catch(InvalidOperationException){}
            typeof(PinnedRewardAlternatives).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);
            World.Dispose();
        }
    }
    private static void RewardAlternativeCases()
    {
        InheritedSacrificeCases();
        AutomaticRelicRewardCases();
        foreach(int eligible in new[]{0,1,2})foreach(bool unscoped in new[]{false,true})using(var f=new AlternativesFixture("sacrifice",1)) {
            var player=f.World.World.Player;
            for(int i=0;i<player.Deck.Cards.Count;i++)player.Deck.Cards[i].IsUpgradable=i<eligible;
            f.Wing.Grant=new Whetstone();
            var first=f.Open();f.Apply(first,"sacrifice");
            if(unscoped)player.Deck.Cards[^1].UpgradeInternal();
            bool failed=false;
            try {Check(f.World.Reader.Read().Status==PublicDecisionStatus.Ready&&f.Reward.SuccessfullySelected&&f.Wing.RewardsSacrificed==2,
                "Whetstone sacrifice reconciles the native model upgrade path");}
            catch(InvalidOperationException){failed=true;}
            Check(failed==unscoped,"only the retained pickup scope can certify a model upgrade");
            if(!unscoped)Check(player.Deck.Cards.Select((c,i)=>c.CurrentUpgradeLevel==(i<eligible?1:0)).All(x=>x),
                "Whetstone changes only eligible original cards");
            for(int i=0;i<2;i++) {
                bool cleanup=false;try{f.World.Reader.Dispose();}catch(InvalidOperationException){cleanup=true;}
                Check(cleanup==unscoped,"Whetstone cleanup preserves an unresolved failure");
            }
            Check(!(HarmonyLib.Harmony.GetPatchInfo(typeof(CardModel).GetMethod("UpgradeInternal")!)?.Owners.Any()??false),
                "Whetstone model upgrade hook is removed on success and failure");
        }
        using(var f=new AlternativesFixture("sacrifice",1,items:2)) {
            var player=f.World.World.Player;player.PotionSlots.RemoveRange(6,2);player.MaxPotionCount=6;
            var belt=new PotionBelt();belt.DynamicVars["PotionSlots"].IntValue=2;f.Wing.Grant=belt;
            var parent=f.World.Reader.Read();f.Apply(parent,parent.LegalActions.First(a=>a.StartsWith("collect:",StringComparison.Ordinal)));
            Check(f.World.Reader.Read().Status==PublicDecisionStatus.Ready,"prior item settles before sacrifice");
            var first=f.Open();f.Apply(first,"sacrifice");
            Check(f.World.Reader.Read().Status==PublicDecisionStatus.Ready&&player.PotionSlots.Count==8,"owned Potion Belt capacity preserves earlier settled item");
        }
        using(var f=new AlternativesFixture("sacrifice",1)) {
            var player=f.World.World.Player;player.Relics.Add(new DragonFruit{Owner=player});int hp=player.Creature.MaxHp;
            var first=f.Open();f.Apply(first,"sacrifice");
            Check(f.World.Reader.Read().Status==PublicDecisionStatus.Ready&&player.Creature.MaxHp==hp+1,"Old Coin retains owned Dragon Fruit callback");
        }
        foreach(bool duringOpen in new[]{true,false})using(var f=new AlternativesFixture("reroll")) {
            var first=duringOpen?f.World.Reader.Read():f.Open();
            f.Apply(first,duringOpen?"open:0":"skip_card");
            var player=f.World.World.Player;var original=player.Deck.Cards[0];var replacement=new CardModel{Owner=player};replacement.Id.Entry=original.Id.Entry;player.Deck.Cards[0]=replacement;
            Check(f.World.Reader.Read().Status==PublicDecisionStatus.Unsupported,"full reward open/skip rejects same-key inventory replacement");
        }
        using(var f=new AlternativesFixture("reroll")) {
            var first=f.Open();Check(first.LegalActions.Contains("reroll")&&first.LegalActions.Contains("skip_card"),"native alternatives identified by meaning");
            f.Apply(first,"reroll");var next=f.World.Reader.Read();
            Check(next.Status==PublicDecisionStatus.Ready&&next.DecisionId!=first.DecisionId&&!next.LegalActions.Contains("reroll")&&next.Rewards[0].Cards.All(c=>c.StartsWith("NEW",StringComparison.Ordinal)),"reroll binds fresh native offer and revision");
            f.Apply(next,"choose:1");Check(f.World.Reader.Read().Status==PublicDecisionStatus.Ready&&f.World.World.Player.Deck.Cards.Last().Id.Entry=="NEW_1"&&f.Clicks==2,"newly generated choice resolves through existing reader");
        }
        foreach(int before in new[]{0,1})using(var f=new AlternativesFixture("sacrifice",before,delayed:before==1)) {
            var first=f.Open();int gold=f.World.World.Player.Gold,deck=f.World.World.Player.Deck.Cards.Count;
            f.Apply(first,"sacrifice");
            if(before==1){Check(f.World.Reader.Read().Status==PublicDecisionStatus.Waiting&&!f.Reward.SuccessfullySelected,"sacrifice waits for nested relic task");f.Gate.SetResult();}
            var after=f.World.Reader.Read();Check(after.Status==PublicDecisionStatus.Ready&&f.Reward.SuccessfullySelected&&f.Wing.RewardsSacrificed==before+1&&f.World.World.Player.Deck.Cards.Count==deck,"sacrifice completes reward without a card");
            Check(f.World.World.Player.Gold==gold+(before==1?300:0)&&f.Clicks==1,"actual owned relic effect retained");
        }
        foreach(string mode in new[]{"button","option","gold","foreground","context","task_fault","unscoped_change"})using(var f=new AlternativesFixture("sacrifice",1,true)) {
            var first=f.Open();bool dispatched=mode is "task_fault" or "unscoped_change";
            if(dispatched)f.Apply(first,"sacrifice");
            if(mode=="button")f.Menu.AlternativeButtons.Children[1]=new NCardRewardAlternativeButton();
            if(mode=="option")f.Options[1]=new("SACRIFICE",PostAlternateCardRewardAction.EndSelectionAndCompleteReward){OnSelect=f.Wing.OnSacrifice};
            if(mode is "gold" or "unscoped_change")f.World.World.Player.Gold++;
            if(mode=="foreground")ActiveScreenContext.Instance.Blocker=new();
            if(mode=="context")((MegaCrit.Sts2.Core.Runs.RunState)f.World.World.Player.RunState).CurrentRoom=new();
            if(mode=="task_fault")f.Gate.SetException(new InvalidOperationException());
            if(mode=="unscoped_change")f.Gate.SetResult();
            bool failed=false;try{failed=f.World.Reader.Read().Status==PublicDecisionStatus.Unsupported;}catch(InvalidOperationException){failed=true;}
            Check(failed&&f.Clicks==(dispatched?1:0),"alternate identity/task/effect failure: "+mode);
        }
    }
    private static void InheritedSacrificeCases()
    {
        var declared=typeof(RelicModel).GetMethod("AfterObtained")!;
        foreach(bool conflicting in new[]{false,true})
        {
            using var f=new AlternativesFixture("sacrifice",1);
            var player=f.World.World.Player;int gold=player.Gold,deck=player.Deck.Cards.Count;
            var relic=new InheritedRewardRelic();f.Wing.Grant=relic;
            var ready=f.Open();
            var foreign=new HarmonyLib.Harmony("fixture.sacrifice.foreign."+Guid.NewGuid().ToString("N"));
            if(conflicting)foreign.Patch(declared,new HarmonyLib.HarmonyMethod(typeof(Program),nameof(RewardForeignPickupPrefix)));
            try
            {
                PublicRewardActionRequest.TryCreate(ready.DecisionId,"sacrifice",out var request);
                PublicRewardActionApplyOutcome? outcome=null;bool dispatchFailed=false;
                try{outcome=f.World.Applier.Apply(request).Outcome;}catch(InvalidOperationException){dispatchFailed=true;}
                if(conflicting)
                    Check((dispatchFailed||outcome!=PublicRewardActionApplyOutcome.Accepted)&&relic.Owner is null&&!player.Relics.Contains(relic),"conflicting inherited sacrifice hook prevents relic input");
                else
                    Check(!dispatchFailed&&outcome==PublicRewardActionApplyOutcome.Accepted&&f.World.Reader.Read().Status==PublicDecisionStatus.Ready&&f.Reward.SuccessfullySelected&&ReferenceEquals(relic.Owner,player)&&player.Relics.Count(r=>ReferenceEquals(r,relic))==1,"sacrifice reconciles an inherited passive callback");
                Check(f.Clicks==1&&player.Gold==gold&&player.Deck.Cards.Count==deck,"inherited sacrifice executes once without unrelated changes");
                for(int i=0;i<2;i++)
                {
                    bool failed=false;try{f.World.Reader.Dispose();}catch(InvalidOperationException){failed=true;}
                    Check(failed==conflicting&&f.Clicks==1,"inherited sacrifice cleanup preserves failure without replay");
                }
                var owners=HarmonyLib.Harmony.GetPatchInfo(declared)?.Owners;
                Check(conflicting?owners?.SequenceEqual(new[]{foreign.Id})==true:!(owners?.Any()??false),"sacrifice cleanup retains only a foreign declared hook");
            }
            finally{foreign.UnpatchAll(foreign.Id);}
        }
    }
    private static void AutomaticRelicRewardCases()
    {
        foreach(string kind in new[]{"inherited","mango","paint","coin","dragon","pending","foreign","fault","invalid_deck"}) {
            using var f=new CombatItemsFixture(1);var player=f.World.Player;var reward=(RelicReward)f.Rewards[0];
            RelicModel relic=kind=="inherited"?new InheritedRewardRelic():kind=="mango"?new Mango():kind=="paint"?new WarPaint():new OldCoin();relic.Id.Entry=kind.ToUpperInvariant();reward.Relic=relic;
            if(kind=="dragon") {var fruit=new DragonFruit{Owner=player};fruit.Id.Entry="DRAGON_FRUIT";player.Relics.Add(fruit);}
            var gate=new TaskCompletionSource();if(kind is "pending" or "foreign" or "fault")((OldCoin)relic).Gate=gate.Task;
            f.Reader.InventoryFactory=p=>new PinnedRewardInventory(p);f.Reader.RelicEffectFactory=PinnedRelicRewardEffect.Create;
            f.Buttons[0].Handler=async()=>{reward.ClaimedRelic=await MegaCrit.Sts2.Core.Commands.RelicCmd.Obtain(relic,player);reward.SuccessfullySelected=true;};
            var view=f.Reader.Read();int gold=player.Gold,hp=player.Creature.MaxHp;
            PublicRewardActionRequest.TryCreate(view.DecisionId,"collect:0",out var request);
            Check(f.Applier.Apply(request).Outcome==PublicRewardActionApplyOutcome.Accepted,"automatic terminal relic accepted once");
            if(kind=="invalid_deck")player.Deck.Cards[1]=player.Deck.Cards[0];
            if(kind is "pending" or "foreign" or "fault") {
                Check(f.Reader.Read().Status==PublicDecisionStatus.Waiting,"terminal relic waits for AfterObtained task");
                if(kind=="foreign")player.Deck.Cards[0]=new CardModel{Owner=player};
                if(kind=="fault")gate.SetException(new InvalidOperationException());else gate.SetResult();
            }
            bool failed=false;try{failed=f.Reader.Read().Status==PublicDecisionStatus.Unsupported;}catch(InvalidOperationException){failed=true;}
            Check(failed==(kind is "foreign" or "fault" or "invalid_deck"),"owned automatic terminal effect: "+kind);
            if(!failed){Check(player.Gold==gold+(kind is "coin" or "dragon" or "pending"?300:0),"terminal gold gain observed");if(kind is "mango" or "dragon")Check(player.Creature.MaxHp==hp+(kind=="mango"?14:1),"terminal HP effect observed");}
            for(int i=0;i<2;i++){bool cleanup=false;try{f.Reader.Dispose();}catch(InvalidOperationException){cleanup=true;}Check(cleanup==failed,"terminal relic cleanup result remains sticky");}
            Check(!(HarmonyLib.Harmony.GetPatchInfo(relic.GetType().GetMethod("AfterObtained")!)?.Owners.Any()??false)&&
                !(HarmonyLib.Harmony.GetPatchInfo(typeof(MegaCrit.Sts2.Core.Entities.Players.Player).GetProperty("Gold")!.SetMethod!)?.Owners.Any()??false),"terminal relic always removes its native hooks");
        }
    }
}
