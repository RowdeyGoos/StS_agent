using System;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2AgentBridge.Unified;

// OpenChest deliberately remains pending while the native relic chooser is open.
// Native single-player Skip leaves that UI task dormant forever. Reconcile its
// exact waiting state plus the completed Skip action/Proceed task; never invent
// completion. Reads never open the chest, enable Skip, or dispatch input.
internal sealed class CampaignTreasureTransition : IDisposable
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
    private static readonly MethodInfo Open = typeof(NTreasureRoom).GetMethod("OpenChest", Private)!;
    private static readonly MethodInfo Delay = typeof(NTreasureRoom).GetMethod("EnableSkipAfterDelay", Private)!;
    private static readonly MethodInfo Ftue = typeof(NTreasureRoom).GetMethod("RelicFtueCheck", Private)!;
    private static readonly FieldInfo Chest = typeof(NTreasureRoom).GetField("_chestButton", Private)!;
    private static readonly FieldInfo Room = typeof(NTreasureRoom).GetField("_room", Private)!;
    private static readonly FieldInfo Run = typeof(NTreasureRoom).GetField("_runState", Private)!;
    private static readonly FieldInfo Opened = typeof(NTreasureRoom).GetField("_hasChestBeenOpened", Private)!;
    private static readonly FieldInfo Choosing = typeof(NTreasureRoom).GetField("_isRelicCollectionOpen", Private)!;
    private static readonly FieldInfo Collection = typeof(NTreasureRoom).GetField("_relicCollection", Private)!;
    private static readonly FieldInfo Skipped = typeof(TreasureRoomRelicSynchronizer).GetField("_singleplayerSkipped", Private)!;
    private static CampaignTreasureTransition? _owner;
#if CAMPAIGN_TEST_SEAM
    internal static Action? BeforeCleanupForTest;
#endif
    private readonly Harmony _harmony = new("sts2.agent.campaign.treasure." + Guid.NewGuid().ToString("N"));
    private readonly NTreasureRoom _screen;
    private readonly NButton _chest;
    private readonly NProceedButton _skip;
    private readonly NTreasureRoomRelicCollection _collection;
    private readonly TreasureRoomRelicSynchronizer _synchronizer;
    private readonly object _relics;
    private readonly Task _pickingBegan, _pickingFinished;
    private readonly RunState _run;
    private readonly RunManager _manager;
    private readonly ActionQueueSynchronizer _queue;
    private readonly NRun _node;
    private readonly object _room, _player;
    private readonly int _act, _floor, _thread = System.Environment.CurrentManagedThreadId;
    private readonly long _deadline = System.Environment.TickCount64 + 30000;
    private Task? _openTask, _delayTask, _ftueTask;
    private CampaignRewardTransition? _leave;
    private bool _dispatching, _openCalled, _started, _skipped, _complete, _failed, _disposed, _cleanupFailed;
    internal bool Active => _started && !_complete;

    internal CampaignTreasureTransition(NTreasureRoom screen)
    {
        _screen = screen; _manager = RunManager.Instance; _queue = _manager.ActionQueueSynchronizer;
        _run = _manager.DebugOnlyGetState() ?? throw new InvalidOperationException("Missing treasure run.");
        _node = NRun.Instance ?? throw new InvalidOperationException("Missing treasure node.");
        Require(_run.Players.Count == 1 && _run.CurrentRoom is TreasureRoom);
        _room = _run.CurrentRoom!; _player = _run.Players[0]; _act = _run.CurrentActIndex; _floor = _run.TotalFloor;
        _chest = Chest.GetValue(screen) as NButton ?? throw new InvalidOperationException("Missing chest control.");
        _skip = screen.ProceedButton;
        _collection = Collection.GetValue(screen) as NTreasureRoomRelicCollection ?? throw new InvalidOperationException("Missing relic collection.");
        _synchronizer = _manager.TreasureRoomRelicSynchronizer;
        _relics = _synchronizer.CurrentRelics ?? throw new InvalidOperationException("Missing treasure offerings.");
        _pickingBegan = _collection.RelicPickingBegan(); _pickingFinished = _collection.RelicPickingFinished();
        Context(); Require(Opened.GetValue(_screen) is false && Choosing.GetValue(_screen) is false && Enabled(_chest));
    }
    private void Require(bool value) { if (!value) { _failed = true; throw new InvalidOperationException("Campaign treasure ownership failed."); } }
    private static bool Enabled(NButton button) => GodotObject.IsInstanceValid(button) && button.IsVisibleInTree() && button.IsEnabled;
    private void Context()
    {
        Require(!_disposed && !_failed && System.Environment.CurrentManagedThreadId == _thread && System.Environment.TickCount64 < _deadline &&
            ReferenceEquals(_manager, RunManager.Instance) && ReferenceEquals(_run, _manager.DebugOnlyGetState()) &&
            ReferenceEquals(_manager.ActionQueueSynchronizer, _queue) &&
            ReferenceEquals(_node, NRun.Instance) && ReferenceEquals(_run.CurrentRoom, _room) &&
            _run.CurrentActIndex == _act && _run.TotalFloor == _floor && _run.Players.Count == 1 && ReferenceEquals(_run.Players[0], _player) &&
            _run.Players[0].Creature.CurrentHp > 0 && !_manager.IsAbandoned && (int)_manager.NetService.Type == 1 &&
            _manager.debugAfterCombatRewardsOverride is null && ReferenceEquals(_node.TreasureRoom, _screen) &&
            GodotObject.IsInstanceValid(_screen) && _screen.IsVisibleInTree() && ReferenceEquals(Room.GetValue(_screen), _room) &&
            ReferenceEquals(Run.GetValue(_screen), _run) && ReferenceEquals(Chest.GetValue(_screen), _chest) &&
            ReferenceEquals(Collection.GetValue(_screen), _collection) && GodotObject.IsInstanceValid(_collection) &&
            ReferenceEquals(_manager.TreasureRoomRelicSynchronizer, _synchronizer) && ReferenceEquals(_synchronizer.CurrentRelics, _relics) &&
            ReferenceEquals(_collection.RelicPickingBegan(), _pickingBegan) && ReferenceEquals(_collection.RelicPickingFinished(), _pickingFinished) &&
            !_pickingBegan.IsCompleted && !_pickingFinished.IsCompleted && (_skipped || Skipped.GetValue(_synchronizer) is false) &&
            ReferenceEquals(_screen.ProceedButton, _skip) && _node.GlobalUi.Overlays.ScreenCount == 0 &&
            NModalContainer.Instance?.OpenModal is null && NCapstoneContainer.Instance is not { InUse: true } &&
            !_node.GlobalUi.MapScreen.IsTraveling && (_skipped || !_node.GlobalUi.MapScreen.IsOpen));
    }
    internal string Read()
    {
        Context();
        if (!_started) { Require(Opened.GetValue(_screen) is false && Choosing.GetValue(_screen) is false && Enabled(_chest)); return "open_chest"; }
        Require(ReferenceEquals(_owner, this) && _openTask is not null);
        foreach (var task in new[] { _openTask, _delayTask, _ftueTask }) Require(task?.IsFaulted != true && task?.IsCanceled != true);
        if (_skipped) {
            string destination = _leave!.Poll();
            if (destination == "waiting") return "waiting";
            Require(destination == "map" && !_openTask!.IsCompleted && Skipped.GetValue(_synchronizer) is true &&
                Opened.GetValue(_screen) is true && Choosing.GetValue(_screen) is true &&
                _delayTask?.IsCompletedSuccessfully == true && _ftueTask?.IsCompletedSuccessfully == true);
            _complete = true; return "map";
        }
        // Completion before our Skip would mean somebody else picked or skipped.
        Require(!_openTask!.IsCompleted);
        if (Opened.GetValue(_screen) is not true || Choosing.GetValue(_screen) is not true ||
            _delayTask?.IsCompletedSuccessfully != true || _ftueTask?.IsCompletedSuccessfully != true) return "waiting";
        Require(_skip.IsSkip);
        return Enabled(_skip) ? "skip_relic" : "waiting";
    }
    internal void Apply(string action)
    {
        Require(Read() == action && action is "open_chest" or "skip_relic");
        if (action == "skip_relic") {
            _leave = new CampaignRewardTransition(_screen, () => { Context(); return true; });
            _skipped = true;
            try { _leave.Dispatch(); } catch { _failed = true; throw; }
            return;
        }
        Require(_owner is null);
        foreach (var target in new[] { Open, Delay, Ftue }) Require(target is not null && !(Harmony.GetPatchInfo(target)?.Owners.Any() ?? false));
        _owner = this; _started = true;
        try {
            foreach (var target in new[] { Open, Delay, Ftue }) _harmony.Patch(target,
                new HarmonyMethod(typeof(CampaignTreasureTransition).GetMethod(nameof(BeforeTask), BindingFlags.Static | BindingFlags.NonPublic)),
                new HarmonyMethod(typeof(CampaignTreasureTransition).GetMethod(nameof(AfterTask), BindingFlags.Static | BindingFlags.NonPublic)));
            _dispatching = true;
            Require(_chest.EmitSignal(NClickableControl.SignalName.Released, _chest) == Error.Ok);
            Require(_openTask is not null);
        } catch { _failed = true; throw; } finally { _dispatching = false; }
    }
    private static void BeforeTask(NTreasureRoom __instance, MethodBase __originalMethod)
    {
        var o = _owner!; o.Context(); o.Require(ReferenceEquals(__instance, o._screen) && !o._skipped);
        if (__originalMethod == Open) { o.Require(o._dispatching && !o._openCalled); o._openCalled = true; }
        else o.Require(o._openCalled && (__originalMethod == Delay ? o._delayTask is null : o._ftueTask is null));
    }
    private static void AfterTask(MethodBase __originalMethod, Task __result)
    {
        var o = _owner!; o.Require(__result is not null);
        if (__originalMethod == Open) { o.Require(o._openTask is null); o._openTask = __result; }
        else if (__originalMethod == Delay) { o.Require(o._delayTask is null); o._delayTask = __result; }
        else { o.Require(o._ftueTask is null); o._ftueTask = __result; }
    }
    public void Dispose()
    {
        if (_disposed) { Require((!_started || _complete) && !_cleanupFailed); return; }
        // Successful native Skip deliberately retains the dormant chooser task.
        // Revalidate that exact settled state before dropping only our hooks.
        try { if (_complete) Require(Read() == "map"); }
        catch { _failed = true; _complete = false; }
        _disposed = true;
        try {
            try { _leave?.Dispose(); }
            finally {
#if CAMPAIGN_TEST_SEAM
                BeforeCleanupForTest?.Invoke();
#endif
                foreach (var target in new[] { Open, Delay, Ftue }) _harmony.Unpatch(target, HarmonyPatchType.All, _harmony.Id);
                foreach (var target in new[] { Open, Delay, Ftue })
                    if (Harmony.GetPatchInfo(target)?.Owners.Contains(_harmony.Id) == true) throw new InvalidOperationException("Treasure patch remains.");
                if (ReferenceEquals(_owner, this)) _owner = null;
            }
        } catch { _cleanupFailed = true; throw; }
        Require(!_started || _complete);
    }
}
