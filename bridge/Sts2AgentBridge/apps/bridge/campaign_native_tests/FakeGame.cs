// Authored inert fixtures. The production build separately checks native types.
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Rooms;
namespace Godot {
 public enum Error {Ok,Failed}
 public class GodotObject {public bool Valid=true;public static bool IsInstanceValid(GodotObject? o)=>o?.Valid==true;}
 public class Node:GodotObject {public readonly List<Node> Children=new();public int GetChildCount(bool _)=>Children.Count;public Node GetChild(int index,bool _)=>Children[index];}
 public class Control:Node {public bool Visible=true;public bool IsVisibleInTree()=>Visible;public NProceedButton? Button;public T? GetNodeOrNull<T>(string _) where T:class=>Button as T;}
}
namespace MegaCrit.Sts2.Core.Nodes.GodotExtensions {
 public class NClickableControl:Godot.Control {public static class SignalName {public const string Released="released";}}
 public class NButton:NClickableControl {public bool IsEnabled=true;public Action? Released;public Godot.Error EmitSignal(string _,object __){Released?.Invoke();return Godot.Error.Ok;}}
}
namespace MegaCrit.Sts2.Core.Nodes.CommonUi {
 public class NProceedButton:MegaCrit.Sts2.Core.Nodes.GodotExtensions.NButton {public bool IsSkip;}
 public sealed class NModalContainer {public static NModalContainer? Instance;public object? OpenModal;}
}
namespace MegaCrit.Sts2.Core.Nodes.Screens {public sealed class NRewardsScreen:Godot.Control {
 private bool _isTerminal=true;private MegaCrit.Sts2.Core.Runs.RunState? _runState;
 public void Bind(MegaCrit.Sts2.Core.Runs.RunState run,bool terminal=true){_runState=run;_isTerminal=terminal;}
}}
namespace MegaCrit.Sts2.Core.Nodes.Screens.Capstones {public sealed class NCapstoneContainer {public static NCapstoneContainer? Instance;public bool InUse;}}
namespace MegaCrit.Sts2.Core.Nodes.Rooms {
 public sealed class NTreasureRoom:Godot.Control {
  public NProceedButton ProceedButton=new(){Visible=false,IsEnabled=false};
  private MegaCrit.Sts2.Core.Nodes.GodotExtensions.NButton _chestButton=new();
  private TreasureRoom? _room;private MegaCrit.Sts2.Core.Runs.RunState? _runState;
  private readonly MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic.NTreasureRoomRelicCollection _relicCollection=new();
  private bool _hasChestBeenOpened,_isRelicCollectionOpen;
  public readonly TaskCompletionSource OpenGate=new(),DelayGate=new();public Task FtueTask=Task.CompletedTask;
  public bool CompleteOpenOnSkip;public int Opens,Skips;public Action? OnOpen;
  public bool IsChoosing=>_isRelicCollectionOpen;
  public MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic.NTreasureRoomRelicCollection Collection=>_relicCollection;
  public Func<MegaCrit.Sts2.Core.GameActions.GameAction>? SkipAction;
  public MegaCrit.Sts2.Core.Nodes.GodotExtensions.NButton ChestButton=>_chestButton;
  public void Bind(MegaCrit.Sts2.Core.Runs.RunState run) {
   _runState=run;_room=(TreasureRoom)run.CurrentRoom!;
   _chestButton.Released=()=>{_=OpenChest();_chestButton.IsEnabled=false;};
   ProceedButton.Released=()=>{Skips++;var manager=MegaCrit.Sts2.Core.Runs.RunManager.Instance;
    manager.ActionQueueSynchronizer.RequestEnqueue(SkipAction?.Invoke()??new MegaCrit.Sts2.Core.GameActions.PickRelicAction(_runState.Players[0],null));
    if(CompleteOpenOnSkip)OpenGate.TrySetResult();_=manager.ProceedFromTerminalRewardsScreen();};
  }
  public void ShowSkip(){ProceedButton.Visible=ProceedButton.IsEnabled=true;DelayGate.TrySetResult();}
  public void MarkOpened()=>_hasChestBeenOpened=true;
  [MethodImpl(MethodImplOptions.NoInlining)]private Task OpenChest() {
   Opens++;_hasChestBeenOpened=_isRelicCollectionOpen=true;ProceedButton.IsSkip=true;
   _=RelicFtueCheck();_=EnableSkipAfterDelay();OnOpen?.Invoke();return OpenGate.Task;
  }
  [MethodImpl(MethodImplOptions.NoInlining)]private Task EnableSkipAfterDelay()=>DelayGate.Task;
  [MethodImpl(MethodImplOptions.NoInlining)]private Task RelicFtueCheck()=>FtueTask;
 }
 public sealed class NEventRoom:Godot.Control {}
 public sealed class NMapRoom:Godot.Control {}
 public sealed class NMerchantRoom:Godot.Control {public MerchantInventory Inventory=new();}
 public sealed class MerchantInventory {public bool IsOpen;}
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic {
 public sealed class NTreasureRoomRelicCollection:Godot.Control {
  public readonly TaskCompletionSource Began=new(),Finished=new();
  public Task RelicPickingBegan()=>Began.Task;public Task RelicPickingFinished()=>Finished.Task;
 }
}
namespace MegaCrit.Sts2.Core.Multiplayer.Game {
 public sealed class TreasureRoomRelicSynchronizer {
  private bool _singleplayerSkipped;public object? CurrentRelics=new();public bool Skipped=>_singleplayerSkipped;
  public void OnPicked(Player player,int? index){if(index is null)_singleplayerSkipped=true;}
 }
}
namespace MegaCrit.Sts2.Core.Nodes {
 public sealed class Overlays {public readonly List<object> Screens=new();public int ScreenCount=>Screens.Count;public object? Peek()=>Screens.Count==0?null:Screens[^1];}
 public sealed class GlobalUi:Godot.Control {public Screens.Map.NMapScreen MapScreen=new();public Overlays Overlays=new();}
 public sealed class NRun:Godot.Control {public static NRun? Instance;public GlobalUi GlobalUi=new();public NTreasureRoom? TreasureRoom;public NEventRoom? EventRoom;public NMapRoom? MapRoom;public Godot.Control? RestSiteRoom;public NMerchantRoom? MerchantRoom;}
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.Map {
 public sealed class NMapScreen:Godot.Control {public bool IsOpen,IsTraveling,IsTravelEnabled;}
 public sealed class NMapPoint:Godot.Node {public MegaCrit.Sts2.Core.Map.MapPointState State;public MegaCrit.Sts2.Core.Map.MapPoint? Point;}
}
namespace MegaCrit.Sts2.Core.Map {
 public enum MapPointState {Travelable,Visited}
 public enum MapPointType {Unknown,Shop,Treasure,RestSite,Monster,Elite,Boss,Ancient}
 public sealed class MapPoint {public (int col,int row) coord;public MapPointType PointType;}
}
namespace MegaCrit.Sts2.Core.Entities.Players {
 public sealed class Creature {public int CurrentHp=10000,MaxHp=10000;}
 public sealed record ModelId(string Entry);
 public sealed class Character {public ModelId Id=new("IRONCLAD");}
 public sealed class Player {public Creature Creature=new();public Character Character=new();}
}
namespace MegaCrit.Sts2.Core.Rooms {
 public enum RoomType {Boss,Monster,Map,Event,Treasure}
 public class AbstractRoom {public RoomType RoomType;public bool IsVictoryRoom;}
 public sealed class EventRoom:AbstractRoom {public EventRoom(){RoomType=RoomType.Event;}}
 public sealed class MapRoom:AbstractRoom {public MapRoom(){RoomType=RoomType.Map;}}
 public sealed class TreasureRoom:AbstractRoom {public TreasureRoom(){RoomType=RoomType.Treasure;}}
 public sealed class MerchantRoom:AbstractRoom {}
}
namespace MegaCrit.Sts2.Core.Runs {
 public sealed class MapPoint {public int coord;}
 public sealed class ActMap {public MapPoint? SecondBossMapPoint;public MapPoint BossMapPoint=new();}
 public sealed class RunState {public readonly List<Player> Players=new();public AbstractRoom? CurrentRoom;public int CurrentActIndex,TotalFloor=1,AscensionLevel,CurrentMapCoord;public ActMap Map=new();}
 public sealed class NetService {public int Type=1;}
 public sealed class RunManager {
  public static RunManager Instance=new();public RunState? State;public bool IsAbandoned;public NetService NetService=new();public Action? debugAfterCombatRewardsOverride;
  public MegaCrit.Sts2.Core.GameActions.Multiplayer.ActionQueueSynchronizer ActionQueueSynchronizer=new();
  public MegaCrit.Sts2.Core.Multiplayer.Game.TreasureRoomRelicSynchronizer TreasureRoomRelicSynchronizer=new();
  public Func<Task>? Next,Proceed;
  public RunState? DebugOnlyGetState()=>State;
  [MethodImpl(MethodImplOptions.NoInlining)]public Task EnterNextAct()=>Next?.Invoke()??Task.CompletedTask;
  [MethodImpl(MethodImplOptions.NoInlining)]public Task ProceedFromTerminalRewardsScreen()=>Proceed?.Invoke()??Task.CompletedTask;
 }
}
namespace MegaCrit.Sts2.Core.GameActions {
 public class GameAction {
  private Task? _executionTask;
  public Exception? Exception;public TaskCompletionSource Completion=new();public Task CompletionTask=>Completion.Task;
  public event Action<GameAction>? BeforeExecuted,BeforeCancelled;
  public void Cancel()=>BeforeCancelled?.Invoke(this);
  public void Execute(){BeforeExecuted?.Invoke(this);_executionTask=ExecuteInner();}
  protected virtual Task ExecuteAction()=>MegaCrit.Sts2.Core.Runs.RunManager.Instance.EnterNextAct();
  private async Task ExecuteInner(){try{await ExecuteAction();}catch(Exception e){Exception=e;throw;}finally{Completion.TrySetResult();}}
 }
 public sealed class VoteToMoveToNextActAction:GameAction {private readonly Player _player;public VoteToMoveToNextActAction(Player p){_player=p;}}
 public sealed class PickRelicAction:GameAction {
  private readonly Player _player;private readonly int? _relicIndex;
  public MegaCrit.Sts2.Core.Multiplayer.Game.TreasureRoomRelicSynchronizer? TestSynchronizer;
  public PickRelicAction(Player player,int? index){_player=player;_relicIndex=index;}
  protected override Task ExecuteAction(){(TestSynchronizer??MegaCrit.Sts2.Core.Runs.RunManager.Instance.TreasureRoomRelicSynchronizer).OnPicked(_player,_relicIndex);return Task.CompletedTask;}
 }
}
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer {
 public sealed class ActionQueueSynchronizer {public Action<MegaCrit.Sts2.Core.GameActions.GameAction>? Enqueue;[MethodImpl(MethodImplOptions.NoInlining)]public void RequestEnqueue(MegaCrit.Sts2.Core.GameActions.GameAction action){if(Enqueue is {} callback)callback(action);else action.Execute();}}
}
namespace MegaCrit.Sts2.Core.Combat {public sealed class CombatManager {public static CombatManager? Instance;public bool IsInProgress,IsOverOrEnding;}}
namespace Sts2AgentBridge.Core.Public {public interface IPublicRewardTransition:IDisposable {void Dispatch();string Poll();}}
namespace Sts2AgentBridge.Unified {internal sealed record BridgeRequest(bool IsPost,string? Decision=null,string? Action=null);internal sealed record ModuleReply(byte[] Body,bool Terminal=false);}
namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native {
 public sealed class PinnedShopV1NativeAdapter:IShopV1NativeAdapter {
  public static IShopV1NativeAdapter Current=null!;
  public ShopV1SurfaceCapture CaptureSurface()=>Current.CaptureSurface();
  public ShopV1PendingCapture CapturePending(ShopV1PendingProbe pending)=>Current.CapturePending(pending);
 }
}
