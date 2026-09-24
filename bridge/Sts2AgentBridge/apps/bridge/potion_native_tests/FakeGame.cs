// Inert native-shaped fixtures; the real adapter is separately compiled against
// the pinned game. These do not assert live game execution.
#pragma warning disable CS0067
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
namespace MegaCrit.Sts2.Core.Entities.Cards {
 public enum CardType {Attack} public enum TargetType {AnyEnemy,AnyPlayer,AllEnemies}
 public enum UnplayableReason {None}
 public class CardPile { public List<MegaCrit.Sts2.Core.Models.CardModel> Cards=new(); public event Action<MegaCrit.Sts2.Core.Models.CardModel>? CardAdded; }
}
namespace MegaCrit.Sts2.Core.Entities.Potions { public enum PotionUsage {None,CombatOnly,AnyTime,Automatic} }
namespace MegaCrit.Sts2.Core.Models {
 public class ModelId {public string Entry="STRIKE";}
 public class CardModel {public ModelId Id=new();public MegaCrit.Sts2.Core.Entities.Cards.CardType Type;public MegaCrit.Sts2.Core.Entities.Cards.TargetType TargetType;public EnergyCost EnergyCost=new();public bool CanPlay(out MegaCrit.Sts2.Core.Entities.Cards.UnplayableReason reason,out object? other){reason=0;other=null;return true;}}
 public class EnergyCost {public bool CostsX;public int GetAmountToSpend()=>1;}
 public class MonsterModel {public ModelId Id=new();public MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState? NextMove;}
 public class PotionModel {
  public ModelId Id=new(){Entry="FIRE_POTION"};public MegaCrit.Sts2.Core.Entities.Players.Player Owner=null!;
  public bool IsQueued,HasBeenRemovedFromState,PassesCustomUsabilityCheck=true;
  public MegaCrit.Sts2.Core.Entities.Potions.PotionUsage Usage=MegaCrit.Sts2.Core.Entities.Potions.PotionUsage.CombatOnly;
  public MegaCrit.Sts2.Core.Entities.Cards.TargetType TargetType=MegaCrit.Sts2.Core.Entities.Cards.TargetType.AnyEnemy;
  public Action? BeforeUse;public Func<Task>? Effect;
  public bool IsValidTarget(MegaCrit.Sts2.Core.Entities.Creatures.Creature? target)=>TargetType switch {
   MegaCrit.Sts2.Core.Entities.Cards.TargetType.AnyEnemy=>target is {IsAlive:true}&&!ReferenceEquals(target,Owner.Creature),
   MegaCrit.Sts2.Core.Entities.Cards.TargetType.AnyPlayer=>ReferenceEquals(target,Owner.Creature)&&target!.IsAlive,_=>target is null};
  public void EnqueueManualUse(MegaCrit.Sts2.Core.Entities.Creatures.Creature? target){BeforeUse?.Invoke();if(target is null&&IsValidTarget(Owner.Creature))target=Owner.Creature;IsQueued=true;MegaCrit.Sts2.Core.Runs.RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(new MegaCrit.Sts2.Core.GameActions.UsePotionAction(this,target,true));}
  public Task Use(){Owner.PotionSlots[Owner.PotionSlots.IndexOf(this)]=null;HasBeenRemovedFromState=true;return Effect?.Invoke()??Task.CompletedTask;}
 }
}
namespace MegaCrit.Sts2.Core.Models.Potions {
 public class FirePotion:MegaCrit.Sts2.Core.Models.PotionModel {}
 public class BlockPotion:MegaCrit.Sts2.Core.Models.PotionModel {public BlockPotion(){Id.Entry="BLOCK_POTION";TargetType=MegaCrit.Sts2.Core.Entities.Cards.TargetType.AnyPlayer;}}
 public class ExplosiveAmpoule:MegaCrit.Sts2.Core.Models.PotionModel {public ExplosiveAmpoule(){Id.Entry="EXPLOSIVE_AMPOULE";TargetType=MegaCrit.Sts2.Core.Entities.Cards.TargetType.AllEnemies;}}
 public class AttackPotion:MegaCrit.Sts2.Core.Models.PotionModel {public AttackPotion(){Id.Entry="ATTACK_POTION";}}
}
namespace MegaCrit.Sts2.Core.Entities.Players {
 public class Player {public MegaCrit.Sts2.Core.Entities.Creatures.Creature Creature=new(){CombatId=0};public PlayerCombatState? PlayerCombatState=new();public object RunState=null!;public int MaxPotionCount=3;public List<MegaCrit.Sts2.Core.Models.PotionModel?> PotionSlots=new(){null,null,null};public bool CanRemovePotions=true;}
 public class PlayerCombatState {public int Energy=3,TurnNumber=1;public MegaCrit.Sts2.Core.Combat.PlayerTurnPhase Phase;public MegaCrit.Sts2.Core.Entities.Cards.CardPile Hand=new(),PlayPile=new();}
}
namespace MegaCrit.Sts2.Core.Entities.Creatures {public enum CombatSide {Player,Enemy} public enum HpDisplay {Normal,InfiniteWithNumbers,InfiniteWithoutNumbers} public class Creature {public HpDisplay HpDisplay;public bool IsAlive=true;public int CurrentHp=50,MaxHp=50,Block;public uint? CombatId=1;public MegaCrit.Sts2.Core.Models.MonsterModel? Monster;}}
namespace MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine {public enum IntentType {Attack} public class Intent {public IntentType IntentType;} public class MoveState {public List<Intent> Intents=new();}}
namespace MegaCrit.Sts2.Core.Combat {
 public enum PlayerTurnPhase {Play,Other}
 public class CombatState {public List<MegaCrit.Sts2.Core.Entities.Players.Player> Players=new();public List<MegaCrit.Sts2.Core.Entities.Creatures.Creature> Enemies=new(),HittableEnemies=new();public int RoundNumber=1;public MegaCrit.Sts2.Core.Entities.Creatures.CombatSide CurrentSide;}
 public class CombatManager {public static CombatManager Instance=new();public CombatState State=new();public bool IsInProgress=true,IsOverOrEnding,PlayerActionsDisabled,ReadyToEnd;public CombatState DebugOnlyGetState()=>State;public bool IsPlayerReadyToEndTurn(MegaCrit.Sts2.Core.Entities.Players.Player p)=>ReadyToEnd;}
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.Overlays {public class NOverlayStack {public static NOverlayStack? Instance;public int ScreenCount;}}
namespace MegaCrit.Sts2.Core.Runs {
 public class RunManager {public static RunManager Instance=new();public MegaCrit.Sts2.Core.GameActions.Multiplayer.ActionQueueSynchronizer ActionQueueSynchronizer=new();public NetService NetService=new();public object Run=new();public bool IsAbandoned;public object DebugOnlyGetState()=>Run;}
 public class NetService {public int Type=1;}
}
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer {
 public class ActionQueueSynchronizer {
  public List<MegaCrit.Sts2.Core.GameActions.GameAction> Actions=new();public bool AutoExecute,ThrowAfterEnqueue;public Action? BeforeEnqueue;
  [MethodImpl(MethodImplOptions.NoInlining)] public void RequestEnqueue(MegaCrit.Sts2.Core.GameActions.GameAction action){BeforeEnqueue?.Invoke();Actions.Add(action);if(AutoExecute)action.Start();if(ThrowAfterEnqueue)throw new Exception("lost enqueue");}
 }
}
namespace MegaCrit.Sts2.Core.GameActions {
 public class GameAction {
  private Task? _executionTask;private TaskCompletionSource _completion=new();public Task CompletionTask=>_completion.Task;public Exception? Exception=>_executionTask?.Exception;
  public event Action<GameAction>? BeforeExecuted,BeforeCancelled;
  public void Start(){try{BeforeExecuted?.Invoke(this);_executionTask=ExecuteAction();}catch(Exception e){_executionTask=Task.FromException(e);}Observe();}
  private async void Observe(){try{await _executionTask!;}catch{}finally{_completion.TrySetResult();}}
  protected virtual Task ExecuteAction()=>Task.CompletedTask;
  public void Cancel()=>BeforeCancelled?.Invoke(this);
  public void ForgeCompletion()=>_completion.TrySetResult();
 }
 public class UsePotionAction:GameAction {
  public MegaCrit.Sts2.Core.Entities.Players.Player Player;public uint PotionIndex;public uint? TargetId;public bool WasEnqueuedInCombat;public MegaCrit.Sts2.Core.Entities.Creatures.Creature? Target;
  public UsePotionAction(MegaCrit.Sts2.Core.Models.PotionModel p,MegaCrit.Sts2.Core.Entities.Creatures.Creature? t,bool combat){Player=p.Owner;PotionIndex=(uint)Player.PotionSlots.IndexOf(p);Target=t;TargetId=t?.CombatId;WasEnqueuedInCombat=combat;}
  [MethodImpl(MethodImplOptions.NoInlining)]protected override Task ExecuteAction()=>Player.PotionSlots[(int)PotionIndex]!.Use();
 }
}

namespace Godot { public class GodotObject {public bool Valid=true;public static bool IsInstanceValid(GodotObject v)=>v.Valid;} }
namespace MegaCrit.Sts2.Core.Nodes.Rooms {public class NCombatRoom:Godot.GodotObject {public bool Visible=true;public bool IsVisibleInTree()=>Visible;}}
namespace MegaCrit.Sts2.Core.Nodes {public class NRun {public static NRun Instance=new();public MegaCrit.Sts2.Core.Nodes.Rooms.NCombatRoom CombatRoom=new();}}
namespace MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext {public class ActiveScreenContext {public static ActiveScreenContext Instance=new();public object? Blocker;public bool IsCurrent(object room)=>ReferenceEquals(Blocker??MegaCrit.Sts2.Core.Nodes.NRun.Instance.CombatRoom,room);}}
