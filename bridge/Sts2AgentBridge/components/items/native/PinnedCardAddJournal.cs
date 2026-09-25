using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2AgentBridge.Items.Native;

// Retain the actual Add invocation and its forwarding overloads. Observations
// of modification/insertion come through the existing generic-event hooks.
// Never enumerate an unknown native IEnumerable or call a card generator again.
internal sealed class PinnedCardAddJournal : IDisposable
{
    internal sealed class Entry
    {
        internal readonly CardModel Initial;
        internal readonly PinnedAutomaticRelicEffects.Card Before;
        internal CardModel? Final;
        internal PinnedAutomaticRelicEffects.Card? Modified,Inserted;
        internal Entry(CardModel card){Initial=card;Before=Copy(card);}
    }
    internal sealed class Operation
    {
        internal readonly PinnedCardAddJournal Owner;
        internal readonly Entry[] Entries;
        internal readonly object Input;
        internal readonly List<Call> Calls=new();
        internal Entry? Modifying,Inserting;
        internal bool InsertionEntered,Certified;
        internal Operation(PinnedCardAddJournal owner,object input,CardModel[] cards)
        {Owner=owner;Input=input;Entries=cards.Select(c=>new Entry(c)).ToArray();}
    }
    internal sealed class Call
    {
        internal readonly Operation Operation;
        internal readonly int Kind;
        internal readonly Call? Previous;
        internal Task? Task;
        internal IDisposable? Effects;
        internal bool Forwarded,Restored;
        internal Call(Operation operation,int kind,Call? previous){Operation=operation;Kind=kind;Previous=previous;}
    }
    internal sealed class Observation
    {
        internal readonly PinnedCardAddJournal Owner;
        internal readonly Operation Operation;
        internal readonly Entry Entry;
        internal Observation(PinnedCardAddJournal owner,Operation operation,Entry entry){Owner=owner;Operation=operation;Entry=entry;}
    }
    private static readonly AsyncLocal<Call?> Scope=new();
    private static PinnedCardAddJournal? Active;
    private static readonly MethodInfo[] AddMethods={
        Add(typeof(CardModel),typeof(PileType)),Add(typeof(CardModel),typeof(CardPile)),
        Add(typeof(IEnumerable<CardModel>),typeof(PileType)),Add(typeof(IEnumerable<CardModel>),typeof(CardPile))};
    private static MethodInfo Add(Type input,Type pile)=>typeof(CardPileCmd).GetMethod("Add",new[]{input,pile,typeof(CardPilePosition),typeof(AbstractModel),typeof(bool)})!;
    private readonly Player _player;
    private readonly object _run;
    private readonly Func<bool> _context;
    private readonly Func<IReadOnlyList<CardModel>,bool> _authorize;
    private readonly Action<PinnedAutomaticRelicEffects.State,PinnedAutomaticRelicEffects.State> _inserted;
    private readonly Func<IDisposable>? _enterEffects;
    private readonly Harmony _hooks=new("sts.bridge.card.add."+Guid.NewGuid().ToString("N"));
    private readonly List<MethodInfo> _targets=new();
    private readonly List<Operation> _operations=new();
    private PinnedAutomaticRelicEffects.Card[] _deck;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private bool _failed,_disposed;
    internal static bool IsActive=>Active is not null;
    internal bool InNativeScope=>Scope.Value is {} call&&ReferenceEquals(call.Operation.Owner,this);
    internal bool InModification=>InNativeScope&&Scope.Value!.Operation.Modifying is not null;
    internal bool OwnsAddedCard(CardModel card)=>InNativeScope&&Scope.Value!.Operation.Entries.Any(e=>e.Inserted is not null&&ReferenceEquals(e.Final,card));
    internal IReadOnlyList<Operation> Operations=>_operations;
    internal PinnedCardAddJournal(Player player,Func<bool> context,Func<IReadOnlyList<CardModel>,bool> authorize,
        Action<PinnedAutomaticRelicEffects.State,PinnedAutomaticRelicEffects.State> inserted,Func<IDisposable>? enterEffects=null)
    {
        _player=player;_run=player.RunState;_context=context;_authorize=authorize;_inserted=inserted;_enterEffects=enterEffects;_deck=new PinnedAutomaticRelicEffects.State(player).Deck;
        Require(Active is null&&Scope.Value is null&&context());Active=this;
        try {
            foreach(var method in AddMethods) {
                Require(method is not null&&method.GetMethodBody() is not null&&!(Harmony.GetPatchInfo(method)?.Owners.Any()??false));
                _targets.Add(method);_hooks.Patch(method,new HarmonyMethod(typeof(PinnedCardAddJournal),nameof(Prefix)),
                    new HarmonyMethod(typeof(PinnedCardAddJournal),nameof(Postfix)),finalizer:new HarmonyMethod(typeof(PinnedCardAddJournal),nameof(Finalizer)));
            }
        }catch(Exception error) {
            _failed=true;
            try{Unpatch();if(ReferenceEquals(Active,this))Active=null;}catch(Exception cleanup){throw new AggregateException("card_add_constructor_cleanup",error,cleanup);}
            throw;
        }
    }
    private bool Context()=>!_failed&&!_disposed&&ReferenceEquals(Active,this)&&_context()&&
        System.Environment.CurrentManagedThreadId==_thread&&ReferenceEquals(_player.RunState,_run)&&
        _targets.All(m=>Harmony.GetPatchInfo(m) is {} p&&p.Owners.Count==1&&p.Owners.Contains(_hooks.Id));
    private static PinnedAutomaticRelicEffects.Card Copy(CardModel card)=>new(card,card.Id.Entry,card.CurrentUpgradeLevel,card.Enchantment,card.Enchantment?.Id.Entry,card.Enchantment?.Amount??0);
    private bool Owned(CardModel card)=>ReferenceEquals(card.Owner,_player)&&ReferenceEquals(card.RunState,_run)&&card.Id.Entry.Length>0&&card.CurrentUpgradeLevel>=0;
    private bool Deck()=>_player.Deck.Cards.Select(Copy).SequenceEqual(_deck);
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool good){if(!good){_failed=true;throw new InvalidOperationException("card_add_boundary");}}
    internal void Fail()=>_failed=true;
    private static void Prefix(MethodBase __originalMethod,object __0,object __1,CardPilePosition __2,AbstractModel? __3,bool __4,out Call? __state)
    {
        __state=null;var owner=Active;if(owner is null)return;
        try {
            owner.Require(owner.Context()&&owner.Deck()&&__2==CardPilePosition.Bottom&&__3 is null&&!__4);
            int kind=Array.FindIndex(AddMethods,m=>Equals(m,__originalMethod));owner.Require(kind>=0);
            owner.Require(kind is 0 or 2?__1 is PileType.Deck:ReferenceEquals(__1,owner._player.Deck));
            Operation operation;var previous=Scope.Value;
            if(previous is not null) {
                operation=previous.Operation;
                owner.Require(ReferenceEquals(operation.Owner,owner)&&!operation.Certified&&!previous.Forwarded&&
                    (previous.Kind==0&&kind==1||previous.Kind is 1 or 2&&kind==3)&&operation.Modifying is null&&operation.Inserting is null);
                if(kind==1)owner.Require(ReferenceEquals(__0,operation.Input));
                if(previous.Kind==2)owner.Require(ReferenceEquals(__0,operation.Input));
                previous.Forwarded=true;
            } else {
                owner.Require(owner._operations.Count<16&&owner._operations.All(owner.Certify));
                CardModel[] cards=__0 switch {CardModel card=>new[]{card},CardModel[] values=>values.ToArray(),List<CardModel> values=>values.ToArray(),_=>throw new InvalidOperationException("card_add_unmaterialized_input")};
                owner.Require(cards.Length is >=1 and <=8&&cards.Distinct(ReferenceEqualityComparer.Instance).Count()==cards.Length&&
                    cards.All(c=>c is not null&&owner.Owned(c)&&!owner._deck.Any(d=>ReferenceEquals(d.Model,c)))&&owner._authorize(cards));
                operation=new(owner,__0,cards);owner._operations.Add(operation);
            }
            __state=new(operation,kind,previous);operation.Calls.Add(__state);Scope.Value=__state;
            if(previous is null)__state.Effects=owner._enterEffects?.Invoke();
        }catch{owner.Fail();throw;}
    }
    private static void Postfix(object __result,Call? __state)
    {
        if(__state is not {} call)return;var owner=call.Operation.Owner;
        try{owner.Require(owner.Context()&&call.Task is null&&__result is Task);call.Task=(Task)__result;}
        catch{owner.Fail();throw;}finally{Restore(call);}
    }
    private static void Finalizer(Exception? __exception,Call? __state)
    {if(__state is {} call){if(__exception is not null)call.Operation.Owner.Fail();Restore(call);}}
    private static void Restore(Call call)
    {if(!call.Restored){call.Restored=true;try{call.Effects?.Dispose();}catch{call.Operation.Owner.Fail();throw;}finally{Scope.Value=call.Previous;}}}
    private Operation Current()
    {
        Require(Context()&&Scope.Value is {Kind:3} call&&ReferenceEquals(call.Operation.Owner,this)&&
            ReferenceEquals(_operations.LastOrDefault(),call.Operation)&&!call.Operation.Certified);
        return Scope.Value!.Operation;
    }
    internal static Observation ModifyEntry(IRunState run,CardModel initial)
    {
        var owner=Active??throw new InvalidOperationException("card_add_owner");
        try {
            var operation=owner.Current();owner.Require(ReferenceEquals(run,owner._run)&&owner.Deck()&&operation.Modifying is null&&operation.Inserting is null);
            var entry=operation.Entries.SingleOrDefault(e=>ReferenceEquals(e.Initial,initial));
            owner.Require(entry is not null&&entry.Final is null&&entry.Before==Copy(initial));
            operation.Modifying=entry;return new(owner,operation,entry!);
        }catch{owner.Fail();throw;}
    }
    internal static void ModifyExit(Observation observation,CardModel final)
    {
        var owner=observation.Owner;
        try {
            var operation=owner.Current();var entry=observation.Entry;
            owner.Require(ReferenceEquals(operation,observation.Operation)&&ReferenceEquals(operation.Modifying,entry)&&owner.Deck()&&owner.Owned(final)&&
                !owner._deck.Any(c=>ReferenceEquals(c.Model,final))&&!operation.Entries.Any(e=>e.Final is not null&&ReferenceEquals(e.Final,final)));
            entry.Final=final;entry.Modified=Copy(final);operation.Modifying=null;operation.Inserting=entry;
        }catch{owner.Fail();throw;}
    }
    private PinnedAutomaticRelicEffects.State? _beforeInsertion;
    internal static Observation InsertEntry(CardPile pile,CardModel card,int index,bool silent)
    {
        var owner=Active??throw new InvalidOperationException("card_add_owner");
        try {
            var operation=owner.Current();var entry=operation.Inserting;
            owner.Require(entry is not null&&!operation.InsertionEntered&&ReferenceEquals(card,entry.Final)&&entry.Modified==Copy(card)&&owner.Owned(card)&&
                ReferenceEquals(pile,owner._player.Deck)&&index==-1&&!silent&&owner.Deck()&&owner._beforeInsertion is null);
            owner._beforeInsertion=new(owner._player);operation.InsertionEntered=true;return new(owner,operation,entry!);
        }catch{owner.Fail();throw;}
    }
    internal static void InsertExit(Observation observation)
    {
        var owner=observation.Owner;
        try {
            var operation=owner.Current();var entry=observation.Entry;var after=new PinnedAutomaticRelicEffects.State(owner._player);
            owner.Require(ReferenceEquals(operation,observation.Operation)&&ReferenceEquals(operation.Inserting,entry)&&operation.InsertionEntered&&
                after.Deck.Length==owner._deck.Length+1&&after.Deck.Take(owner._deck.Length).SequenceEqual(owner._deck)&&ReferenceEquals(after.Deck[^1].Model,entry.Final));
            owner._inserted(owner._beforeInsertion!,after);owner.Require(owner.Context());
            entry.Inserted=after.Deck[^1];owner._deck=after.Deck;owner._beforeInsertion=null;operation.Inserting=null;operation.InsertionEntered=false;
        }catch{owner.Fail();throw;}
    }
    private bool Certify(Operation operation)
    {
        Require(Context()&&Deck());if(operation.Certified)return true;
        Require(operation.Calls.Count is >=1 and <=3&&operation.Calls.All(c=>c.Task?.IsFaulted!=true&&c.Task?.IsCanceled!=true));
        if(operation.Calls.Any(c=>c.Task?.IsCompletedSuccessfully!=true))return false;
        Require(operation.Modifying is null&&operation.Inserting is null&&!operation.InsertionEntered&&_beforeInsertion is null&&
            operation.Calls.Last().Kind==3&&operation.Calls.Take(operation.Calls.Count-1).All(c=>c.Forwarded));
        if(operation.Input is CardModel[] array)Require(array.SequenceEqual(operation.Entries.Select(e=>e.Initial),ReferenceEqualityComparer.Instance));
        if(operation.Input is List<CardModel> list)Require(list.SequenceEqual(operation.Entries.Select(e=>e.Initial),ReferenceEqualityComparer.Instance));
        foreach(var call in operation.Calls) {
            IReadOnlyList<CardPileAddResult> results=call.Task switch {
                Task<CardPileAddResult> single=>new[]{single.Result},
                Task<IReadOnlyList<CardPileAddResult>> multiple when multiple.Result is List<CardPileAddResult> or CardPileAddResult[]=>multiple.Result,
                _=>throw new InvalidOperationException("card_add_result_type")};
            Require(results.Count==operation.Entries.Length);
            for(int i=0;i<results.Count;i++) {
                var result=results[i];var entry=operation.Entries[i];
                Require(result.success?entry.Inserted is not null&&ReferenceEquals(result.cardAdded,entry.Final):
                    entry.Final is null&&entry.Inserted is null&&ReferenceEquals(result.cardAdded,entry.Initial));
            }
        }
        operation.Certified=true;return true;
    }
    internal bool Completed
    {get{try{return Context()&&_operations.Count>0&&_operations.All(Certify)&&Deck();}catch{Fail();throw;}}}
    internal bool Valid()=>Context()&&Deck()&&_operations.All(o=>o.Calls.All(c=>c.Task?.IsFaulted!=true&&c.Task?.IsCanceled!=true));
    private void Unpatch(){_hooks.UnpatchAll(_hooks.Id);if(_targets.Any(m=>Harmony.GetPatchInfo(m)?.Owners.Contains(_hooks.Id)==true))throw new InvalidOperationException("card_add_cleanup");}
    public void Dispose()
    {
        if(_disposed){Require(!_failed);return;}
        Exception? failure=null;
        try{Require(Context()&&Scope.Value is null&&(_operations.Count==0||Completed));}catch(Exception error){failure=error;}
        try{Unpatch();}catch(Exception error){failure??=error;}
        _disposed=true;if(failure is not null){Fail();throw new InvalidOperationException("card_add_cleanup",failure);}
        Active=null;
    }
}
