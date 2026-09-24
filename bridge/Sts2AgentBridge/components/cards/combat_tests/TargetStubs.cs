// Inert API fixtures. The actual adapter is compiled here; no game assemblies execute.
#pragma warning disable CS0414, CS0649
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
namespace Godot
{
    public enum Error { Ok, Failed }
    public class GodotObject : IDisposable { public bool Valid = true; public static bool IsInstanceValid(GodotObject o) => o.Valid; public void Dispose() { } }
    public class Node : GodotObject
    {
        public Dictionary<string, Node> Nodes = new(); public bool Visible = true;
        public List<Node> Children = new();
        public IEnumerable<Node> GetChildren() => Children;
        public int GetChildCount() => Children.Count;
        public T? GetNodeOrNull<T>(string name) where T : Node => Nodes.GetValueOrDefault(name) as T;
        public bool IsVisibleInTree() => Visible;
    }
    public class Control : Node { }
    public class InputEventAction : GodotObject { public string Action = ""; public bool Pressed; }
    public static class Time { public static ulong Ticks = 1000; public static ulong GetTicksMsec() => Ticks; }
}
namespace MegaCrit.Sts2.Core.CardSelection
{
    public struct CardSelectorPrefs { public int MinSelect, MaxSelect; public bool RequireManualConfirmation, Cancelable; }
}
namespace MegaCrit.Sts2.Core.ControllerInput { public static class MegaInput { public static string select = "select"; } }
namespace MegaCrit.Sts2.Core.Commands { public static class CardSelectCmd { public static object? Selector; } }
namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum UnplayableReason { None, Energy }
    public enum CardType { Attack }
    public enum TargetType { AnyEnemy, Self }
    public enum PileType { None, Draw, Hand, Discard, Exhaust, Play, Deck }
    public class CardPile { public PileType Type; public List<MegaCrit.Sts2.Core.Models.CardModel> Cards = new(); public event Action<MegaCrit.Sts2.Core.Models.CardModel>? CardAdded; public void Add(MegaCrit.Sts2.Core.Models.CardModel card) { Cards.Add(card); CardAdded?.Invoke(card); } }
    public static class PileTypeExtensions { public static CardPile GetPile(this PileType type, MegaCrit.Sts2.Core.Entities.Players.Player p) => p.Piles[type]; }
}
namespace MegaCrit.Sts2.Core.Entities.Players
{
    public class Player { public PlayerCombatState? PlayerCombatState = new(); public MegaCrit.Sts2.Core.Entities.Creatures.Creature Creature = new(); public Dictionary<MegaCrit.Sts2.Core.Entities.Cards.PileType, MegaCrit.Sts2.Core.Entities.Cards.CardPile> Piles = new(); }
    public class PlayerCombatState { public int Energy=3,TurnNumber=1; public MegaCrit.Sts2.Core.Combat.PlayerTurnPhase Phase=MegaCrit.Sts2.Core.Combat.PlayerTurnPhase.Play; public MegaCrit.Sts2.Core.Entities.Cards.CardPile Hand=new(),PlayPile=new(); }
}
namespace MegaCrit.Sts2.Core.Models
{
    public class ModelId { public string Entry = "STRIKE"; }
    public class CardModel { public ModelId Id = new(); public int CurrentUpgradeLevel; public MegaCrit.Sts2.Core.Entities.Players.Player Owner = null!; public MegaCrit.Sts2.Core.Entities.Cards.CardType Type=MegaCrit.Sts2.Core.Entities.Cards.CardType.Attack; public MegaCrit.Sts2.Core.Entities.Cards.TargetType TargetType=MegaCrit.Sts2.Core.Entities.Cards.TargetType.AnyEnemy; public EnergyCost EnergyCost=new(); public bool Playable=true; public bool CanPlay(out MegaCrit.Sts2.Core.Entities.Cards.UnplayableReason reason,out object? auxiliary){reason=Playable?MegaCrit.Sts2.Core.Entities.Cards.UnplayableReason.None:MegaCrit.Sts2.Core.Entities.Cards.UnplayableReason.Energy;auxiliary=null;return Playable;} }
    public class EnergyCost {public bool CostsX;public int Amount=3;public int GetAmountToSpend()=>Amount;}
    public class MonsterModel {public ModelId Id=new();public MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState? NextMove;}
}
namespace MegaCrit.Sts2.Core.Entities.Creatures {public enum CombatSide {Player,Enemy} public enum HpDisplay {Normal,InfiniteWithNumbers,InfiniteWithoutNumbers} public class Creature {public HpDisplay HpDisplay;public bool IsAlive=true;public int CurrentHp=80,MaxHp=80,Block;public MegaCrit.Sts2.Core.Models.MonsterModel? Monster;}}
namespace MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine {public class MoveState {public List<Intent> Intents=new();} public class Intent {public IntentType IntentType=IntentType.Attack;} public enum IntentType {Attack}}
namespace MegaCrit.Sts2.Core.Combat
{
    public enum PlayerTurnPhase {Play,Other}
    public class CombatState { public List<MegaCrit.Sts2.Core.Entities.Players.Player> Players = new(); public List<MegaCrit.Sts2.Core.Entities.Creatures.Creature> Enemies=new(),HittableEnemies=new();public int RoundNumber=1;public MegaCrit.Sts2.Core.Entities.Creatures.CombatSide CurrentSide=MegaCrit.Sts2.Core.Entities.Creatures.CombatSide.Player; }
    public class CombatManager { public static CombatManager? Instance; public bool IsInProgress = true, IsOverOrEnding,PlayerActionsDisabled,ReadyToEnd; public CombatState State = new(); public CombatState DebugOnlyGetState() => State;public bool IsPlayerReadyToEndTurn(MegaCrit.Sts2.Core.Entities.Players.Player p)=>ReadyToEnd; }
}
namespace MegaCrit.Sts2.Core.GameActions
{
    public class GameAction
    {
        private Task? _executionTask;
        private readonly TaskCompletionSource _completion = new();
        public Task CompletionTask => _completion.Task;
        public Exception? Exception => _executionTask?.Exception;
        public event Action<GameAction>? BeforeExecuted, BeforeCancelled;
        public void Start() { _executionTask = new TaskCompletionSource().Task; BeforeExecuted?.Invoke(this); }
        public void Cancel() { BeforeCancelled?.Invoke(this); }
        public void Finish(string outcome = "success") {
            _executionTask = outcome == "fault" ? Task.FromException(new Exception("execution")) :
                outcome == "task_cancel" ? Task.FromCanceled(new System.Threading.CancellationToken(true)) : Task.CompletedTask;
            _completion.SetResult(); // Mirrors the pinned native finally, even on failure.
        }
    }
    public class PlayCardAction : GameAction {public PlayCardAction(MegaCrit.Sts2.Core.Models.CardModel card,MegaCrit.Sts2.Core.Entities.Creatures.Creature? target){Card=card;Target=target;}public MegaCrit.Sts2.Core.Models.CardModel Card;public object? Target;}
    public class EndPlayerTurnAction : GameAction {public EndPlayerTurnAction(MegaCrit.Sts2.Core.Entities.Players.Player p,int turn){}}
}
namespace MegaCrit.Sts2.Core.Runs
{
    public class RunManager {public static RunManager Instance=new();public QueueSynchronizer ActionQueueSynchronizer=new();}
    public class QueueSynchronizer {
        public List<MegaCrit.Sts2.Core.GameActions.GameAction> Actions=new();public bool ThrowAfterEnqueue,AutoComplete=true;
        public void RequestEnqueue(MegaCrit.Sts2.Core.GameActions.GameAction action){
            Actions.Add(action);
            if(AutoComplete){action.Start();if(action is MegaCrit.Sts2.Core.GameActions.PlayCardAction play)play.Card.Owner.PlayerCombatState!.PlayPile.Add(play.Card);action.Finish();}
            if(ThrowAfterEnqueue)throw new InvalidOperationException("uncertain enqueue");
        }
    }
}
namespace MegaCrit.Sts2.Core.Nodes
{
    public class NRun : Godot.Control { public static NRun? Instance; public GlobalUi GlobalUi = new(); }
    public class GlobalUi { public MegaCrit.Sts2.Core.Nodes.Screens.Overlays.NOverlayStack Overlays = new(); public MapScreen MapScreen = new(); }
    public class MapScreen : Godot.Control { public bool IsOpen, IsTraveling; }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.Overlays
{
    public class NOverlayStack : Godot.Control { public static NOverlayStack? Instance; public object? Top; public int ScreenCount => Top is null ? 0 : 1; public object? Peek() => Top; }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext
{
    public class ActiveScreenContext {
        public static ActiveScreenContext Instance = new(); public object? Blocker;
        public bool IsCurrent(object screen) => ReferenceEquals(Blocker ?? MegaCrit.Sts2.Core.Nodes.Screens.Overlays.NOverlayStack.Instance?.Peek(), screen);
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Cards
{
    public class NCard : Godot.Control { public MegaCrit.Sts2.Core.Models.CardModel Model = null!; }
    public class NCardGrid : Godot.Control
    {
        public bool IsAnimatingOut;
        public List<MegaCrit.Sts2.Core.Nodes.Cards.Holders.NGridCardHolder> CurrentlyDisplayedCardHolders = new();
        public IEnumerable<MegaCrit.Sts2.Core.Models.CardModel> CurrentlyDisplayedCards => CurrentlyDisplayedCardHolders.Select(h => h.CardModel);
    }
}
namespace MegaCrit.Sts2.Core.Nodes.CommonUi
{
    public class NConfirmButton : Godot.Control { public bool IsEnabled = true; public Action Click = () => { }; public int Calls; public void ForceClick() { Calls++; Click(); } }
}
namespace MegaCrit.Sts2.Core.Nodes.Combat { public class NPeekButton : Godot.Control { public bool IsPeeking; } }
namespace MegaCrit.Sts2.Core.Nodes.Cards.Holders
{
    public class Hitbox : Godot.Control { public bool IsEnabled = true; }
    public class NCardHolder : Godot.Control
    {
        public static class SignalName { public static string Pressed = "pressed"; }
        private bool _isClickable = true;
        public void SetClickable(bool value) => _isClickable = value;
    }
    public class NGridCardHolder : NCardHolder
    {
        public MegaCrit.Sts2.Core.Models.CardModel CardModel = null!;
        public MegaCrit.Sts2.Core.Nodes.Cards.NCard? CardNode;
        public Hitbox Hitbox = new(); public Action Click = () => { }; public int Calls;
        public int SignalCalls, QueuedCalls;
        public Action? DeferredInput;
        public bool DeferInput;
        public Godot.Error SignalError = Godot.Error.Ok;
        public Godot.Error EmitSignal(string signal, NCardHolder holder) {
            if (signal != SignalName.Pressed || !ReferenceEquals(holder, this)) throw new Exception();
            Calls++; SignalCalls++; Click(); return SignalError;
        }
        public void _GuiInput(Godot.InputEventAction input) {
            if (input.Action != "select" || !input.Pressed) throw new Exception();
            Calls++; if (DeferInput) { QueuedCalls++; DeferredInput = Click; } else Click();
        }
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection
{
    using MegaCrit.Sts2.Core.CardSelection;
    using MegaCrit.Sts2.Core.Entities.Cards;
    using MegaCrit.Sts2.Core.Models;
    public class NChooseACardSelectionScreen : Godot.Control
    {
        private TaskCompletionSource<IEnumerable<CardModel>> _completionSource = new();
        private IReadOnlyList<CardModel> _cards = Array.Empty<CardModel>();
        private bool _canSkip, _screenComplete, _cardSelected;
        private ulong _openedTicks;
        public void Init(IReadOnlyList<CardModel> cards, bool skip = false, ulong opened = 0)
        { _cards = cards; _canSkip = skip; _openedTicks = opened; }
        public void Result(IEnumerable<CardModel> result) { _screenComplete = _cardSelected = true; _completionSource.SetResult(result); }
        public void Cancel() => _completionSource.SetCanceled();
        public void ReplaceTask() => _completionSource = new();
    }
    public class NCardGridSelectionScreen : Godot.Control
    {
        protected readonly TaskCompletionSource<IEnumerable<CardModel>> _completionSource = new();
        public void Result(IEnumerable<CardModel> result) => _completionSource.SetResult(result);
        public void Cancel() => _completionSource.SetCanceled();
    }
    public class NCombatPileCardSelectScreen : NCardGridSelectionScreen
    {
        private CardPile _pile = null!; private CardSelectorPrefs _prefs; private object _filter = new();
        private HashSet<CardModel> _selectedCards = new();
        public HashSet<CardModel> Selected => _selectedCards;
        public void Init(CardPile pile, CardSelectorPrefs prefs) { _pile = pile; _prefs = prefs; }
    }
}
