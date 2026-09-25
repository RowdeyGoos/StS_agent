using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using Sts2AgentBridge.Items.Native;
using Hook=MegaCrit.Sts2.Core.Hooks.Hook;

namespace MegaCrit.Sts2.Core.Entities.Cards {public enum CardPilePosition {Bottom=1}}
namespace MegaCrit.Sts2.Core.Models.Relics
{
    public sealed class LuckyFysh:RelicModel
    {
        public LuckyFysh(){Id.Entry="LUCKY_FYSH";}
        public Task Gate=Task.CompletedTask;
        [MethodImpl(MethodImplOptions.NoInlining)]public async Task AfterCardChangedPiles(CardModel card,PileType old,AbstractModel? clonedBy)
        {Owner!.Gold+=15;foreach(var fruit in Owner.Relics.OfType<DragonFruit>())await fruit.AfterGoldGained(Owner);await Gate;}
    }
    public sealed class DarkstonePeriapt:RelicModel
    {
        [MethodImpl(MethodImplOptions.NoInlining)]public Task AfterCardChangedPiles(CardModel card,PileType old,AbstractModel? clonedBy)
        {Owner!.Creature.SetMaxHpInternal(Owner.Creature.MaxHp+6);Owner.Creature.SetCurrentHpInternal(Owner.Creature.CurrentHp+6);return Task.CompletedTask;}
    }
    public sealed class BookOfFiveRings:RelicModel
    {
        [MethodImpl(MethodImplOptions.NoInlining)]public Task AfterCardChangedPiles(CardModel card,PileType old,AbstractModel? clonedBy)
        {Owner!.Creature.SetCurrentHpInternal(Math.Min(Owner.Creature.MaxHp,Owner.Creature.CurrentHp+3));return Task.CompletedTask;}
    }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static partial class CardPileCmd
    {
        public static Func<CardModel,Task>? AfterAdded;
        public static Func<CardModel,bool>? Prevent;
        public static bool WrongResult;
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static async Task<CardPileAddResult> Add(CardModel card,PileType pile,CardPilePosition position=CardPilePosition.Bottom,AbstractModel? source=null,bool skip=false)
            =>await Add(card,card.Owner!.Deck,position,source,skip);
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static async Task<CardPileAddResult> Add(CardModel card,CardPile pile,CardPilePosition position=CardPilePosition.Bottom,AbstractModel? source=null,bool skip=false)
            =>(await Add(new[]{card},pile,position,source,skip))[0];
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static async Task<IReadOnlyList<CardPileAddResult>> Add(IEnumerable<CardModel> cards,PileType pile,CardPilePosition position=CardPilePosition.Bottom,AbstractModel? source=null,bool skip=false)
            =>await Add(cards,cards.First().Owner!.Deck,position,source,skip);
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static async Task<IReadOnlyList<CardPileAddResult>> Add(IEnumerable<CardModel> cards,CardPile pile,CardPilePosition position=CardPilePosition.Bottom,AbstractModel? source=null,bool skip=false)
        {
            var results=new List<CardPileAddResult>();
            foreach(var card in cards) {
                if(Prevent?.Invoke(card)==true){results.Add(new(){cardAdded=card,success=false});continue;}
                List<AbstractModel>? modifying=null;var final=Hook.ModifyCardBeingAddedToDeck(card.RunState!,card,ref modifying);
                pile.AddInternal(final,-1,false);results.Add(new(){cardAdded=WrongResult?card:final,success=true,modifyingModels=modifying});
            }
            foreach(var result in results.Where(r=>r.success))if(AfterAdded is {} callback)await callback(result.cardAdded);
            return results;
        }
    }
}
internal static partial class Program
{
    private static void CardAddJournalCases()
    {
        CardAddEffectCases();
        foreach(string mode in new[]{"single","pile","list","array","modified","prevented","delayed","fault","wrong_result","foreign_insert","foreign_call","lazy","reentrant"}) {
            using var world=new FullRewardFixture();
            PinnedCardAddJournal? journal=null;bool authorized=false;int insertions=0,enumerations=0;
            var gate=new TaskCompletionSource();
            CardModel New(string key){var c=new CardModel{Owner=world.World.Player};c.Id.Entry=key;return c;}
            var first=New("ADD_FIRST");var second=New("ADD_SECOND");var modified=New("ADD_FIRST");modified.CurrentUpgradeLevel=1;
            IEnumerable<CardModel> Lazy(){enumerations++;yield return first;}
            Hook.Modifier=mode is "modified" or "wrong_result"?(_,_)=>modified:null;
            CardPileCmd.Prevent=mode=="prevented"?_=>true:null;CardPileCmd.WrongResult=mode=="wrong_result";
            CardPileCmd.AfterAdded=mode is "delayed" or "fault"?_=>gate.Task:
                mode=="reentrant"?async _=>{await CardPileCmd.Add(second,PileType.Deck);}:null;
            world.World.Room.Layout.OptionButtons[0].Option.Callback=async()=>{
                journal=new(world.World.Player,()=>true,cards=>authorized&&cards.Count<=2&&ReferenceEquals(cards[0],first),
                    (before,after)=>{
                        Check(before.Gold==after.Gold&&before.Hp==after.Hp&&before.MaxHp==after.MaxHp&&before.Relics.SequenceEqual(after.Relics)&&before.Potions.SequenceEqual(after.Potions),"add insertion changes only exact deck append");
                        insertions++;
                    });
                authorized=mode!="foreign_call";
                if(mode=="foreign_insert"){world.World.Player.Deck.AddInternal(first,-1,false);return;}
                if(mode=="lazy")await CardPileCmd.Add(Lazy(),PileType.Deck);
                else if(mode=="list")await CardPileCmd.Add(new List<CardModel>{first,second},PileType.Deck);
                else if(mode=="array")await CardPileCmd.Add(new[]{first,second},world.World.Player.Deck);
                else if(mode=="pile")await CardPileCmd.Add(first,world.World.Player.Deck);
                else await CardPileCmd.Add(first,PileType.Deck);
            };
            try {
                var before=world.World.Session.Read();world.World.Session.Apply(before.DecisionId,"choose:0");
                Check(journal is not null,"card add journal captured");
                if(mode is "delayed" or "fault") {
                    Check(insertions==1&&!journal!.Completed,"card insertion alone does not complete native Add task");
                    if(mode=="fault")gate.SetException(new InvalidOperationException("after-add fault"));else gate.SetResult();
                }
                bool failed=false,complete=false;try{complete=journal!.Completed;}catch{failed=true;}
                if(mode is "fault" or "wrong_result" or "foreign_insert" or "foreign_call" or "lazy" or "reentrant")
                    Check(failed||!complete,"uncertified card Add cannot complete: "+mode);
                else Check(complete&&journal!.Operations.Count==1&&insertions==(mode=="prevented"?0:mode is "list" or "array"?2:1),"native forwarding overloads form one exact operation: "+mode);
                if(mode=="lazy")Check(enumerations==0,"unknown native enumerable is never executed by observer");
            } finally {
                try{journal?.Dispose();}catch(InvalidOperationException){}
                Check(typeof(CardPileCmd).GetMethods().Where(m=>m.Name=="Add").All(m=>!(HarmonyLib.Harmony.GetPatchInfo(m)?.Owners.Any()??false)),"card Add observers removed");
                typeof(PinnedCardAddJournal).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);
                Hook.Modifier=null;CardPileCmd.AfterAdded=null;CardPileCmd.Prevent=null;CardPileCmd.WrongResult=false;
            }
        }
    }
    private static void CardAddEffectCases()
    {
        foreach(string mode in new[]{"effects","delayed","fault","foreign_gold","foreign_callback","changed_survivor"}) {
            using var world=new FullRewardFixture();var player=world.World.Player;player.Creature.CurrentHp=50;
            var gate=new TaskCompletionSource();var luck=new LuckyFysh{Owner=player};var stone=new DarkstonePeriapt{Owner=player};
            var book=new BookOfFiveRings{Owner=player};var fruit=new DragonFruit{Owner=player};player.Relics.AddRange(new RelicModel[]{luck,stone,book,fruit});
            foreach(var relic in player.Relics)relic.Id.Entry=relic.GetType().Name.ToUpperInvariant();
            if(mode is "delayed" or "fault")luck.Gate=gate.Task;
            var card=new CardModel{Owner=player};card.Id.Entry="INITIAL";
            var clone=new CardModel{Owner=player,IsUpgradable=true};clone.Id.Entry="INITIAL";
            Hook.Modifier=(_,_)=>{(mode=="changed_survivor"?world.World.Cards[0]:clone).UpgradeInternal();return clone;};
            CardPileCmd.AfterAdded=async added=>{await luck.AfterCardChangedPiles(added,(PileType)0,null);await stone.AfterCardChangedPiles(added,(PileType)0,null);await book.AfterCardChangedPiles(added,(PileType)0,null);};
            PinnedCardAddJournal? journal=null;PinnedAutomaticRelicEffects? effects=null;
            world.World.Room.Layout.OptionButtons[0].Option.Callback=async()=>{
                effects=new(player,()=>true,c=>journal?.OwnsAddedCard(c)==true,()=>journal?.InModification==true);
                journal=new(player,()=>true,cards=>effects.Valid()&&cards.Count==1&&ReferenceEquals(cards[0],card),effects.CertifyDeckAppend,effects.EnterLease);
                await CardPileCmd.Add(card,PileType.Deck);
            };
            try {
                var read=world.World.Session.Read();world.World.Session.Apply(read.DecisionId,"choose:0");
                Check(journal is not null&&effects is not null,"card add side effects owned");
                if(mode is "delayed" or "fault") {
                    Check(!journal!.Completed&&!effects!.CardEffectsCompleted,"actual callback task prevents premature effect completion");
                    if(mode=="fault")gate.SetException(new InvalidOperationException("callback failed"));else gate.SetResult();
                }
                if(mode=="foreign_gold")player.Gold++;
                if(mode=="foreign_callback")luck.AfterCardChangedPiles(clone,(PileType)0,null).GetAwaiter().GetResult();
                bool complete=false;try{complete=journal!.Completed&&effects!.CardEffectsCompleted;}catch(InvalidOperationException){}
                Check(complete==(mode is "effects" or "delayed"),"card add side effects cannot adopt foreign or failed changes: "+mode);
                if(complete)Check(player.Gold==114&&player.Creature.CurrentHp==60&&player.Creature.MaxHp==87&&ReferenceEquals(player.Deck.Cards.Last(),clone)&&clone.CurrentUpgradeLevel==1,
                    "exact Egg replacement and Lucky Fysh/Dragon Fruit/Darkstone/Book callbacks retained");
            } finally {
                try{journal?.Dispose();}catch(InvalidOperationException){}effects?.Dispose();
                typeof(PinnedCardAddJournal).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);
                Hook.Modifier=null;CardPileCmd.AfterAdded=null;
            }
        }
    }
}
