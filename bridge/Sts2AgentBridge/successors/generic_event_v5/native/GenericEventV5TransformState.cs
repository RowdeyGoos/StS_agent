using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;
using Sts2AgentBridge.Successors.CardTransformV1;
namespace Sts2AgentBridge.Successors.GenericEventV5.Native;

internal sealed class GenericEventV5TransformState
{
    private readonly GenericEventV5Binding _binding;
    private object[]? _selected;
    private readonly List<Command> _commands=new();
    private readonly List<CardTransformV1Insertion> _insertions=new();
    private readonly List<object> _removed=new();
    private bool _closed;
    internal GenericEventV5TransformState(GenericEventV5Binding binding)=>_binding=binding;
    internal bool Authorized=>_selected is not null;
    internal void Fail()=>_binding.Failed=true;
    internal void Close()=>_closed=true;
    private void Require(bool condition){if(!condition){Fail();throw new InvalidOperationException("Unowned transformation observation.");}}
    private void Context()=>Require(!_closed&&!_binding.Failed&&_binding.MatchesChildBinding());
    internal void Reserve(IReadOnlyList<object> originals)
    {
        Context();Require(_selected is null&&originals.Count==_binding.Prefs.MaxSelect&&_binding.MatchesCurrentDeck());
        var set=new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach(var original in originals)Require(original is CardModel&&set.Add(original)&&_binding.Originals.Any(o=>ReferenceEquals(o,original)));
        _selected=originals.ToArray();
    }
    internal Command Begin()
    {
        Context();Require(Authorized&&_commands.Count<8);
        Refresh();Require(_commands.Count==0||_commands[^1].State==CardTransformV1CommandState.Succeeded);
        Require(ExpectedDeck());
        var command=new Command(this,GenericEventV5Binding.CopyDeck(_binding.Player));_commands.Add(command);return command;
    }
    internal void BindTask(Command command,Task<IEnumerable<CardPileAddResult>> task)
    {Context();Require(Current(command)&&task is not null&&command.Task is null&&_binding.ObservedCommandTasks.Count<32&&_binding.ObservedCommandTasks.Add(task));command.Task=task;Refresh();}
    internal void CommandFault(Command command){command.State=CardTransformV1CommandState.Faulted;Fail();}
    private bool Current(Command command)=>_commands.Count>0&&ReferenceEquals(_commands[^1],command)&&ReferenceEquals(command.Owner,this);
    private bool OwnedCard(CardModel? card)=>card is not null&&ReferenceEquals(card.Owner,_binding.Player)&&ReferenceEquals(card.RunState,_binding.RunState)&&CardSelectionV1NativeRules.IsStableKey(card.Id.Entry)&&card.CurrentUpgradeLevel>=0;
    private bool Baseline(CardModel card)=>_binding.PreDispatchDeck.Any(c=>ReferenceEquals(c.ModelIdentity,card));
    internal CardModel ChoiceEntry(Command command,CardTransformation transformation)
    {
        Context();Require(Current(command)&&!command.Frozen&&command.PendingChoice is null&&command.Choices.Count<_selected!.Length);
        var original=transformation.Original;
        Require(!transformation.IsInCombat&&OwnedCard(original)&&_selected!.Any(o=>ReferenceEquals(o,original))&&
            !_commands.Any(c=>c.Choices.Any(x=>ReferenceEquals(x.Original,original))));
        // Earlier iterations remove their originals before the next native choice.
        Require(Matches(command.Start,command.Choices.Select(c=>(object)c.Original),Array.Empty<CardTransformV1Insertion>()));
        command.PendingChoice=original;return original;
    }
    internal void ChoiceExit(Command command,CardModel original,CardModel initial)
    {
        Context();Require(Current(command)&&ReferenceEquals(command.PendingChoice,original)&&OwnedCard(initial)&&!Baseline(initial)&&
            !_binding.ObservedPreviewClones.Contains(initial)&&_binding.ObservedPreviewClones.Count<64);
        _binding.ObservedPreviewClones.Add(initial);
        command.Choices.Add(new Choice(original,initial));command.PendingChoice=null;
    }
    internal Choice ModifyEntry(Command command,IRunState run,CardModel initial)
    {
        Context();Require(Current(command)&&ReferenceEquals(run,_binding.RunState)&&command.PendingChoice is null&&command.PendingFinal is null&&command.PendingInsertion is null);
        if(!command.Frozen)
        {
            Require(command.Choices.Count>0&&Matches(command.Start,command.Choices.Select(c=>(object)c.Original),Array.Empty<CardTransformV1Insertion>()));
            command.Frozen=true;_removed.AddRange(command.Choices.Select(c=>(object)c.Original));
        }
        Require(ExpectedDeck());
        var choice=command.Choices.SingleOrDefault(c=>ReferenceEquals(c.Initial,initial));
        Require(choice is not null&&choice.Final is null&&OwnedCard(initial)&&initial.Id.Entry==choice.InitialKey&&initial.CurrentUpgradeLevel==choice.InitialLevel);
        command.PendingFinal=choice;return choice!;
    }
    internal void ModifyExit(Command command,Choice choice,CardModel final)
    {
        Context();Require(Current(command)&&ReferenceEquals(command.PendingFinal,choice)&&OwnedCard(final)&&!Baseline(final)&&ExpectedDeck()&&
            (!ReferenceEquals(final,choice.Initial)?!_binding.ObservedPreviewClones.Contains(final):true)&&
            !_commands.Any(c=>c.Choices.Any(x=>ReferenceEquals(x.Final,final))));
        if(!ReferenceEquals(final,choice.Initial)){Require(_binding.ObservedPreviewClones.Count<64);_binding.ObservedPreviewClones.Add(final);}
        choice.Final=final;choice.FinalKey=final.Id.Entry;choice.FinalLevel=final.CurrentUpgradeLevel;
        command.PendingFinal=null;command.PendingInsertion=choice;
    }
    internal Choice InsertionEntry(Command command,CardPile pile,CardModel final,int index,bool silent)
    {
        Context();var choice=command.PendingInsertion;
        Require(Current(command)&&command.Frozen&&choice is not null&&!command.Inserting&&ReferenceEquals(pile,_binding.Player.Deck)&&
            ReferenceEquals(final,choice.Final)&&index==-1&&!silent&&ExpectedDeck()&&OwnedCard(final)&&
            final.Id.Entry==choice.FinalKey&&final.CurrentUpgradeLevel==choice.FinalLevel);
        command.Inserting=true;return choice!;
    }
    internal void InsertionExit(Command command,Choice choice)
    {
        Context();Require(Current(command)&&command.Inserting&&ReferenceEquals(command.PendingInsertion,choice));
        var row=new CardTransformV1Insertion(_insertions.Count+1,choice.Original,choice.Final!,choice.FinalKey!,choice.FinalLevel);
        Require(Matches(_binding.PreDispatchDeck,_removed,_insertions.Append(row)));
        command.Insertions.Add(row);_insertions.Add(row);command.PendingInsertion=null;command.Inserting=false;
    }
    private bool ExpectedDeck()=>Matches(_binding.PreDispatchDeck,_removed,_insertions);
    private bool Matches(IReadOnlyList<CardSelectionV1DeckCard> baseline,IEnumerable<object> removed,IEnumerable<CardTransformV1Insertion> inserted)
    {
        var remove=new HashSet<object>(removed,ReferenceEqualityComparer.Instance);
        var expected=baseline.Where(c=>!remove.Contains(c.ModelIdentity)).Select(c=>new CardSelectionV1DeckCard(c.ModelIdentity,c.StableKey,c.UpgradeLevel)).ToList();
        expected.AddRange(inserted.Select(c=>new CardSelectionV1DeckCard(c.FinalIdentity,c.FinalStableKey,c.FinalUpgradeLevel)));
        var actual=GenericEventV5Binding.CopyDeck(_binding.Player);
        return actual.Length==expected.Count&&actual.All(c=>c.ModelIdentity is CardModel model&&OwnedCard(model))&&!actual.Where((c,i)=>!ReferenceEquals(c.ModelIdentity,expected[i].ModelIdentity)||c.StableKey!=expected[i].StableKey||c.UpgradeLevel!=expected[i].UpgradeLevel).Any();
    }
    private void Refresh()
    {
        foreach(var command in _commands)
        {
            if(command.State is CardTransformV1CommandState.Succeeded or CardTransformV1CommandState.Canceled or CardTransformV1CommandState.Faulted)continue;
            var task=command.Task;if(task is null||!task.IsCompleted)continue;
            if(task.IsCanceled){command.State=CardTransformV1CommandState.Canceled;Fail();continue;}
            if(!task.IsCompletedSuccessfully){command.State=CardTransformV1CommandState.Faulted;Fail();continue;}
            Require(command.Frozen&&command.PendingChoice is null&&command.PendingFinal is null&&command.PendingInsertion is null&&!command.Inserting&&command.Insertions.Count==command.Choices.Count);
            Require(task.Result is List<CardPileAddResult>);
            var result=(List<CardPileAddResult>)task.Result;Require(result.Count==command.Insertions.Count&&result.Count<=_binding.Prefs.MaxSelect);
            var rows=new List<CardTransformV1CommandResult>();
            for(int i=0;i<result.Count;i++)
            {var value=result[i];Require(value.success&&value.cardAdded is not null&&ReferenceEquals(value.cardAdded,command.Insertions[i].FinalIdentity));rows.Add(new(value.success,value.cardAdded!));}
            command.Results=rows.ToArray();command.State=CardTransformV1CommandState.Succeeded;
        }
    }
    internal CardTransformV1EffectWitness Capture()
    {
        Context();Refresh();Require(ExpectedDeck());
        return new(_commands.Where(c=>c.Frozen).Select(c=>new CardTransformV1CommandWitness(c,c.Choices.Select(x=>(object)x.Original).ToArray(),c.State,true,c.Insertions.ToArray(),c.Results.ToArray())).ToArray(),_removed.ToArray(),_insertions.ToArray());
    }
    internal bool Complete
    {get{Refresh();return Authorized&&!_binding.Failed&&_commands.Count>0&&_commands.All(c=>c.State==CardTransformV1CommandState.Succeeded)&&_removed.Count==_selected!.Length&&_insertions.Count==_selected.Length;}}
    internal sealed class Command
    {
        internal readonly GenericEventV5TransformState Owner;
        internal readonly CardSelectionV1DeckCard[] Start;
        internal readonly List<Choice> Choices=new();
        internal readonly List<CardTransformV1Insertion> Insertions=new();
        internal CardTransformV1CommandResult[] Results=Array.Empty<CardTransformV1CommandResult>();
        internal Task<IEnumerable<CardPileAddResult>>? Task;
        internal CardTransformV1CommandState State=CardTransformV1CommandState.Running;
        internal CardModel? PendingChoice;
        internal Choice? PendingFinal,PendingInsertion;
        internal bool Frozen,Inserting;
        internal Command(GenericEventV5TransformState owner,CardSelectionV1DeckCard[] start){Owner=owner;Start=start;}
    }
    internal sealed class Choice
    {
        internal readonly CardModel Original,Initial;
        internal readonly string InitialKey;
        internal readonly int InitialLevel;
        internal CardModel? Final;
        internal string? FinalKey;
        internal int FinalLevel;
        internal Choice(CardModel original,CardModel initial){Original=original;Initial=initial;InitialKey=initial.Id.Entry;InitialLevel=initial.CurrentUpgradeLevel;}
    }
}
