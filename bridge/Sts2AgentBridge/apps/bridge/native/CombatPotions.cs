using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading.Tasks;
using System.Threading;
using HarmonyLib;
using GodotObject = Godot.GodotObject;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Potions;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Unified;

// Native effects run unchanged. The legacy route retains its original allowlist;
// v2 also owns native selectors, generated potions and noncombat map use.
internal sealed class CombatPotions : IFullPotions
{
    private static readonly HashSet<string> Supported = new(StringComparer.Ordinal) {
        "BloodPotion", "BlockPotion", "DexterityPotion", "EnergyPotion", "ExplosiveAmpoule",
        "FirePotion", "FlexPotion", "FruitJuice", "HeartOfIron", "LiquidBronze", "RegenPotion",
        "SpeedPotion", "StrengthPotion", "VulnerablePotion", "WeakPotion"
    };
    private readonly PinnedPublicCombatDecisionReader _combat;
    private readonly ConditionalWeakTable<object, string> _identities = new();
    private readonly HashSet<string> _used = new(StringComparer.Ordinal);
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private Execution? _pending;
    private DiscardExecution? _discard;
    private bool _failed, _disposed, _full;
    private string Protocol => _full ? "potions_v2" : "combat_potions_v1";
    public bool ChoiceOwnerAlive => _full && !_failed && !_disposed && _pending?.ChoiceOwnerAlive == true;
    public bool AllowsChoices => _full && _pending?.AllowsChoices == true && !_failed;
    public CombatPotionReply ReadFull() { if (_pending is not null && !_full) return Fault(); _full = true; return ReadCore(); }
    public CombatPotionReply ApplyFull(string decision, string action) { if (_pending is not null && !_full) return Fault(); _full = true; return ApplyCore(decision, action); }
    public bool Active => _pending is not null || _discard is not null || _failed;
    internal CombatPotions(PinnedPublicCombatDecisionReader combat) => _combat = combat;
#if COMBAT_POTION_TEST_SEAM
    internal static void ResetFixture() => Execution.ResetFixture();
#endif
    private string Identity(object? value) => value is null ? "" : _identities.GetValue(value, _ => Guid.NewGuid().ToString("N"));
    private sealed record Choice(int Slot, PotionModel Potion, Creature? Target, int? TargetIndex, string Action);
    private sealed record View(string Decision, string CombatDecision, RunManager RunManager, CombatManager Manager,
        CombatState? Combat, Player Player, PotionModel?[] Slots, Dictionary<string, Choice> Choices, object[] Inventory, object Net, object Run, ActionQueueSynchronizer Queue, int Turn, NRun Node, NCombatRoom? Room, object Location, object Map, bool InCombat);
    private static byte[] Json(object value) => JsonSerializer.SerializeToUtf8Bytes(value);
    private bool Allowed(PotionModel potion) => potion.GetType().Assembly == typeof(PotionModel).Assembly &&
        potion.GetType().Namespace == "MegaCrit.Sts2.Core.Models.Potions" && (_full || Supported.Contains(potion.GetType().Name));
    private static bool Ready(CombatManager manager, CombatState combat, Player player) => manager.IsInProgress && !manager.IsOverOrEnding &&
        !manager.PlayerActionsDisabled && combat.CurrentSide == CombatSide.Player && player.Creature.IsAlive &&
        player.PlayerCombatState?.Phase == PlayerTurnPhase.Play && !manager.IsPlayerReadyToEndTurn(player) &&
        (NOverlayStack.Instance?.ScreenCount ?? 0) == 0 && NRun.Instance?.CombatRoom is { } room &&
        GodotObject.IsInstanceValid(room) && room.IsVisibleInTree() && ActiveScreenContext.Instance.IsCurrent(room);
    // AnyTime potions are available at an actionable map between owned room
    // interactions. The map must be foreground; retained background rewards are inert.
    private static bool OutsideReady(NRun node, Player player) => !CombatManager.Instance.IsInProgress && player.Creature.IsAlive &&
        node.GlobalUi.MapScreen.IsOpen && node.GlobalUi.MapScreen.IsTravelEnabled && !node.GlobalUi.MapScreen.IsTraveling &&
        ActiveScreenContext.Instance.IsCurrent(node.GlobalUi.MapScreen);
    private View? Capture()
    {
        if (!_full && _combat.Read().Status != PublicDecisionStatus.Ready) return null;
        var manager = CombatManager.Instance;
        var run = RunManager.Instance;
        var state = run?.DebugOnlyGetState();
        var node = NRun.Instance;
        if (state is null || node is null || state.Players.Count != 1 || (int)run!.NetService.Type != 1 || run.IsAbandoned)
            throw new InvalidOperationException("Potion solo run unavailable.");
        bool inCombat = manager.IsInProgress;
        var combat = inCombat ? manager.DebugOnlyGetState() : null;
        var player = state.Players[0];
        string publicDecision;
        if (inCombat) {
            var snapshot = _combat.Read();
            if (snapshot.Status != PublicDecisionStatus.Ready) return null;
            if (combat is null || combat.Players.Count != 1 || !ReferenceEquals(combat.Players[0], player))
                throw new InvalidOperationException("Potion combat changed.");
            if (!Ready(manager, combat, player)) return null;
            publicDecision = snapshot.DecisionId;
        } else {
            if (!_full || !OutsideReady(node, player)) return null;
            publicDecision = $"map:{state.CurrentActIndex}:{state.TotalFloor}:{player.Creature.CurrentHp}:{player.Creature.MaxHp}";
        }
        if (!ReferenceEquals(state, player.RunState) || state.CurrentRoom is null) throw new InvalidOperationException("Potion run changed.");
        if (player.MaxPotionCount is < 0 or > 8 || player.PotionSlots.Count != player.MaxPotionCount)
            throw new InvalidOperationException("Potion capacity unsupported.");
        var slots = player.PotionSlots.ToArray();
        var enemies = combat?.Enemies.Where(e => e.IsAlive).ToArray() ?? Array.Empty<Creature>();
        if (enemies.Length > 6) throw new InvalidOperationException("Potion targets unsupported.");
        var actions = new Dictionary<string, Choice>(StringComparer.Ordinal);
        var inventory = new List<object>();
        for (int slot = 0; slot < slots.Length; slot++) {
            var potion = slots[slot];
            if (potion is null) continue;
            if (!ReferenceEquals(potion.Owner, player) || potion.HasBeenRemovedFromState) throw new InvalidOperationException("Potion owner changed.");
            bool supported = Allowed(potion);
            inventory.Add(new { slot, id = potion.Id.Entry, supported });
            if (_full && supported && player.CanRemovePotions && !potion.IsQueued && potion.Usage != PotionUsage.None) {
                string discard=$"discard:{slot}";actions.Add(discard,new(slot,potion,null,null,discard));
            }
            if (!supported || !player.CanRemovePotions || potion.IsQueued || !potion.PassesCustomUsabilityCheck ||
                potion.Usage is not (PotionUsage.CombatOnly or PotionUsage.AnyTime) || !inCombat && potion.Usage != PotionUsage.AnyTime) continue;
            if (potion.TargetType == TargetType.AnyEnemy) {
                for (int i = 0; i < enemies.Length; i++)
                    if (enemies[i].CombatId is not null && combat!.HittableEnemies.Contains(enemies[i]) && potion.IsValidTarget(enemies[i])) {
                        string action = $"use:{slot}:{i}";
                        actions.Add(action, new(slot, potion, enemies[i], i, action));
                    }
            } else {
                // EnqueueManualUse substitutes the owner for valid self targets.
                Creature? target = potion.IsValidTarget(player.Creature) ? player.Creature : null;
                if (potion.IsValidTarget(target)) {
                    string action = $"use:{slot}";
                    actions.Add(action, new(slot, potion, target, null, action));
                }
            }
        }
        string decision = Convert.ToHexString(SHA256.HashData(Json(new {
            combat = publicDecision, scope = new[] { Identity(manager), Identity(combat), Identity(run), Identity(player.RunState), Identity(player), Identity(run.NetService), Identity(run.ActionQueueSynchronizer), Identity(NRun.Instance), Identity(NRun.Instance!.CombatRoom), Identity(state.CurrentRoom), Identity(node.GlobalUi.MapScreen) },
            slots = slots.Select(Identity).ToArray(), enemies = enemies.Select(Identity).ToArray(), inventory,
            actions = actions.Keys.ToArray()
        }))).ToLowerInvariant();
        return new(decision, publicDecision, run, manager, combat, player, slots, actions, inventory.ToArray(),
            run.NetService, player.RunState, run.ActionQueueSynchronizer, player.PlayerCombatState?.TurnNumber ?? 0, node, inCombat ? node.CombatRoom : null, state.CurrentRoom, node.GlobalUi.MapScreen, inCombat);
    }
    private void Check() {
        if (_disposed || _failed || Environment.CurrentManagedThreadId != _thread) throw new InvalidOperationException("Potion service stopped.");
    }
    private CombatPotionReply Fault() { _failed = true; return new(Json(new { schema_version = 1, protocol = Protocol, status = "failed", code = "native_potion_failed" }), Terminal: true); }
    public CombatPotionReply Read() { if ((_pending is not null || _discard is not null) && _full) return Fault(); _full = false; return ReadCore(); }
    private CombatPotionReply ReadCore()
    {
        try {
            Check();
            if (_discard is {} discard) {
                if (!discard.Complete()) return new(Json(new { schema_version=1,protocol=Protocol,status="waiting" }));
                discard.Dispose();_discard=null;
                return new(Json(new { schema_version=1,protocol=Protocol,status="resolved",decision_id=discard.View.Decision,action_id=discard.Choice.Action }));
            }
            if (_pending is { } pending) {
                if (!pending.Complete()) return new(Json(new { schema_version = 1, protocol = Protocol, status = "waiting" }));
                // Cleanup succeeds before any completion or ownership handoff.
                pending.Dispose();
                _pending = null;
                return new(Json(new { schema_version = 1, protocol = Protocol, status = "resolved", decision_id = pending.View.Decision, action_id = pending.Choice.Action }));
            }
            var view = Capture();
            return view is null ? new(Json(new { schema_version = 1, protocol = Protocol, status = "waiting" })) :
                new(Json(new { schema_version = 1, protocol = Protocol, status = "ready", decision_id = view.Decision,
                    combat_decision_id = view.CombatDecision, potions = view.Inventory, legal_actions = view.Choices.Keys.ToArray() }));
        } catch { return Fault(); }
    }
    public CombatPotionReply Apply(string decision, string action) { if ((_pending is not null || _discard is not null) && _full) return Fault(); _full = false; return ApplyCore(decision, action); }
    private CombatPotionReply ApplyCore(string decision, string action)
    {
        try {
            Check();
            if (_pending is not null || _discard is not null || _used.Count >= 256 || !(_full?CombatPotionRoutes.IsFullAction(decision,action):CombatPotionRoutes.IsAction(decision, action))) return Fault();
            var view = Capture();
            if (view is null || view.Decision != decision || _used.Contains(decision))
                return new(Json(new { schema_version = 1, status = "rejected", mutation_state = "none", decision_id = decision, action_id = action, reason = "stale_decision" }), StaleWithoutMutation: true);
            if (!view.Choices.TryGetValue(action, out var choice)) return Fault();
            _used.Add(decision);
            if (action.StartsWith("discard:",StringComparison.Ordinal)){_discard=new(view,choice);_discard.Dispatch();}
            else {_pending = new Execution(view, choice, _full);_pending.Dispatch();}
            return new(Json(new { schema_version = 1, status = "accepted", mutation_state = "queued", decision_id = decision, action_id = action, reason = "accepted" }));
        } catch { return Fault(); }
    }
    public void Dispose()
    {
        _discard?.Dispose();_pending?.Dispose();
        if (_failed) throw new InvalidOperationException("Potion service failed.");
        _disposed = true;
    }
    private sealed class DiscardExecution : IDisposable
    {
        internal readonly View View;
        internal readonly Choice Choice;
        private readonly DiscardPotionGameAction _action;
        private static readonly FieldInfo ExecutionTask=typeof(GameAction).GetField("_executionTask",BindingFlags.Instance|BindingFlags.NonPublic)!;
        private Task? _execution;
        private readonly Task _completion;
        private readonly int _thread=Environment.CurrentManagedThreadId;
        private readonly long _deadline=Environment.TickCount64+30000;
        private readonly string[] _keys;
        private bool _dispatched,_entered,_failed,_complete,_disposed;
        internal DiscardExecution(View view,Choice choice){View=view;Choice=choice;_keys=view.Slots.Select(p=>p?.Id.Entry??"").ToArray();_action=new(view.Player,(uint)choice.Slot,view.InCombat);_completion=_action.CompletionTask;}
        private void Require(bool value){if(!value){_failed=true;throw new InvalidOperationException("potion_discard_boundary");}}
        private bool Context()=>!_failed&&!_disposed&&Environment.CurrentManagedThreadId==_thread&&Environment.TickCount64<_deadline&&
            ReferenceEquals(RunManager.Instance,View.RunManager)&&ReferenceEquals(CombatManager.Instance,View.Manager)&&ReferenceEquals(NRun.Instance,View.Node)&&
            ReferenceEquals(View.RunManager.DebugOnlyGetState(),View.Run)&&ReferenceEquals(View.Player.RunState,View.Run)&&
            View.RunManager.DebugOnlyGetState() is {} run&&ReferenceEquals(run.CurrentRoom,View.Location)&&run.Players.Count==1&&ReferenceEquals(run.Players[0],View.Player)&&
            ReferenceEquals(View.RunManager.NetService,View.Net)&&(int)View.RunManager.NetService.Type==1&&!View.RunManager.IsAbandoned&&ReferenceEquals(View.RunManager.ActionQueueSynchronizer,View.Queue)&&
            ReferenceEquals(View.Node.GlobalUi.MapScreen,View.Map)&&
            (View.InCombat?ReferenceEquals(View.Manager.DebugOnlyGetState(),View.Combat)&&ReferenceEquals(View.Node.CombatRoom,View.Room)&&Ready(View.Manager,View.Combat!,View.Player)&&View.Player.PlayerCombatState!.TurnNumber==View.Turn:OutsideReady(View.Node,View.Player))&&
            View.Player.MaxPotionCount==View.Slots.Length&&View.Player.PotionSlots.Count==View.Slots.Length&&View.Player.CanRemovePotions;
        private bool Inventory(bool removed)=>Enumerable.Range(0,View.Slots.Length).All(i=> {
            var expected=removed&&i==Choice.Slot?null:View.Slots[i];var actual=View.Player.PotionSlots[i];
            return ReferenceEquals(expected,actual)&&(actual is null||ReferenceEquals(actual.Owner,View.Player)&&!actual.HasBeenRemovedFromState&&actual.Id.Entry==_keys[i]);
        });
        internal void Dispatch(){Require(Context()&&!_dispatched&&Inventory(false)&&!Choice.Potion.IsQueued);_dispatched=true;_action.BeforeExecuted+=Before;_action.BeforeCancelled+=Cancelled;try{View.Queue.RequestEnqueue(_action);}catch{_failed=true;throw;}}
        private void Before(GameAction action){Require(ReferenceEquals(action,_action)&&Context()&&_dispatched&&!_entered&&Inventory(false)&&!Choice.Potion.IsQueued);_entered=true;_action.BeforeExecuted-=Before;}
        private void Cancelled(GameAction action){_failed=true;}
        internal bool Complete(){Require(Context()&&_dispatched&&ReferenceEquals(_action.CompletionTask,_completion)&&_action.Exception is null&&!_completion.IsFaulted&&!_completion.IsCanceled);
            if(_entered){var task=ExecutionTask.GetValue(_action) as Task;Require(task is not null&&(_execution is null||ReferenceEquals(_execution,task))&&!task.IsFaulted&&!task.IsCanceled);_execution=task;}
            bool removed=_entered&&Choice.Potion.HasBeenRemovedFromState;Require(Inventory(removed));
            if(!_completion.IsCompleted)return false;
            Require(_entered&&removed&&_execution?.IsCompletedSuccessfully==true&&(int)_action.State==5);_complete=true;return true;}
        public void Dispose(){if(_disposed){Require(!_failed&&_complete);return;}if(!_complete){_failed=true;throw new InvalidOperationException("unresolved_potion_discard");}_action.BeforeExecuted-=Before;_action.BeforeCancelled-=Cancelled;_disposed=true;Require(!_failed);}
    }
    private sealed class Execution : IDisposable
    {
        private static Execution? _owner;
        private static readonly AsyncLocal<Execution?> Scope = new();
#if COMBAT_POTION_TEST_SEAM
        internal static void ResetFixture() {
            // Only fixture teardown after an asserted fail-closed case. A real
            // unresolved owner keeps its guards until the process exits.
            if (_owner is { } owner)
                foreach (var method in new[] { QueueMethod, ExecuteMethod, AddPotionMethod, RemovePotionMethod }) owner._harmony.Unpatch(method, HarmonyPatchType.All, owner._harmony.Id);
            _owner = null;
        }
#endif
        private static readonly MethodInfo QueueMethod = typeof(ActionQueueSynchronizer).GetMethod("RequestEnqueue", new[] { typeof(GameAction) })!;
        private static readonly MethodInfo ExecuteMethod = typeof(UsePotionAction).GetMethod("ExecuteAction", BindingFlags.Instance | BindingFlags.NonPublic)!;
        private static readonly FieldInfo ExecutionTask = typeof(GameAction).GetField("_executionTask", BindingFlags.Instance | BindingFlags.NonPublic)!;
        private static readonly MethodInfo AddPotionMethod = typeof(Player).GetMethod("AddPotionInternal", new[] { typeof(PotionModel), typeof(int), typeof(bool) })!;
        private static readonly MethodInfo RemovePotionMethod = typeof(Player).GetMethod("RemoveUsedPotionInternal", new[] { typeof(PotionModel) })!;
        private readonly PotionModel?[] _effects;
        private readonly HashSet<PotionModel> _removed = new(ReferenceEqualityComparer.Instance);
        internal bool ChoiceOwnerAlive => !_failed && !_disposed && Environment.CurrentManagedThreadId == _thread &&
            Environment.TickCount64 < _deadline && OwnerContext() && _action?.Exception is null &&
            _completion is not null && !_completion.IsFaulted && !_completion.IsCanceled &&
            _execution?.IsFaulted != true && _execution?.IsCanceled != true;
        internal bool AllowsChoices => _started && !_failed && !_disposed && _action?.State == MegaCrit.Sts2.Core.Entities.Actions.GameActionState.GatheringPlayerChoice && _action.PlayerChoiceContext is not null && _completion?.IsCompleted == false;
        private readonly bool _full;
        private readonly Harmony _harmony = new("sts2.agent.combat.potion." + Guid.NewGuid().ToString("N"));
        internal readonly View View;
        internal readonly Choice Choice;
        private readonly int _thread = Environment.CurrentManagedThreadId;
        private readonly long _deadline = Environment.TickCount64 + 30000;
        private UsePotionAction? _action;
        private Task? _completion, _execution;
        private bool _dispatching, _started, _failed, _complete, _disposed;
        internal Execution(View view, Choice choice, bool full) { View = view; Choice = choice; _full = full; _effects = view.Slots.ToArray(); }
        private void Require(bool ok) { if (!ok) { _failed = true; throw new InvalidOperationException("Owned potion execution failed."); } }
        private bool OwnerContext() => ReferenceEquals(View.Node.GlobalUi.MapScreen, View.Map) && ReferenceEquals(NRun.Instance, View.Node) && ReferenceEquals(RunManager.Instance, View.RunManager) && ReferenceEquals(CombatManager.Instance, View.Manager) &&
            (View.InCombat ? ReferenceEquals(View.Manager.DebugOnlyGetState(), View.Combat) : !View.Manager.IsInProgress) && ReferenceEquals(View.RunManager.DebugOnlyGetState(), View.Run) &&
            ReferenceEquals(View.Player.RunState, View.Run) && ReferenceEquals(View.RunManager.NetService, View.Net) && (int)View.RunManager.NetService.Type == 1 &&
            !View.RunManager.IsAbandoned && ReferenceEquals(View.RunManager.ActionQueueSynchronizer, View.Queue) &&
            (View.Combat is null || View.Combat.Players.Count == 1 && ReferenceEquals(View.Combat.Players[0], View.Player)) &&
            View.RunManager.DebugOnlyGetState() is { } state && ReferenceEquals(state.CurrentRoom, View.Location) && state.Players.Count == 1 && ReferenceEquals(state.Players[0], View.Player);
        private bool Inventory(bool consumed) => View.Player.MaxPotionCount == View.Slots.Length && View.Player.PotionSlots.Count == View.Slots.Length &&
            Enumerable.Range(0, View.Slots.Length).All(i => {
                var expected = consumed && i == Choice.Slot ? null : View.Slots[i];
                if (_full) expected = _effects[i];
                var actual = View.Player.PotionSlots[i];
                return ReferenceEquals(actual, expected) && (actual is null || ReferenceEquals(actual.Owner, View.Player) && !actual.HasBeenRemovedFromState);
            }) && View.Player.PotionSlots.Where(p => p is not null).Distinct(ReferenceEqualityComparer.Instance).Count() == View.Player.PotionSlots.Count(p => p is not null);
        private void BeforeEffect() {
            Require(!_failed && !_disposed && Environment.CurrentManagedThreadId == _thread && Environment.TickCount64 < _deadline && OwnerContext() &&
                (View.InCombat ? ReferenceEquals(View.Node.CombatRoom, View.Room) && Ready(View.Manager, View.Combat!, View.Player) && View.Player.PlayerCombatState!.TurnNumber == View.Turn : OutsideReady(View.Node, View.Player) && Choice.Potion.Usage == PotionUsage.AnyTime) && Inventory(false) &&
                ReferenceEquals(Choice.Potion.Owner, View.Player) && !Choice.Potion.HasBeenRemovedFromState && Choice.Potion.IsQueued &&
                View.Player.CanRemovePotions && Choice.Potion.PassesCustomUsabilityCheck && Choice.Potion.IsValidTarget(Choice.Target) &&
                (Choice.TargetIndex is null || Choice.Target!.IsAlive && View.Combat!.HittableEnemies.Contains(Choice.Target) && Choice.Target.CombatId == _action?.TargetId));
        }
        internal void Dispatch() {
            Require(_owner is null && QueueMethod is not null && ExecuteMethod is not null && ExecutionTask is not null);
            // Event-combat owners may already observe the queue. Our guards are
            // scoped to the one captured action and never absorb their children.
            _owner = this;
            try {
                _harmony.Patch(QueueMethod, new HarmonyMethod(typeof(Execution).GetMethod(nameof(BeforeQueue), BindingFlags.Static | BindingFlags.NonPublic)));
                _harmony.Patch(ExecuteMethod, new HarmonyMethod(typeof(Execution).GetMethod(nameof(BeforeExecute), BindingFlags.Static | BindingFlags.NonPublic)),
                    new HarmonyMethod(typeof(Execution).GetMethod(nameof(AfterExecute), BindingFlags.Static | BindingFlags.NonPublic)));
                if (_full) {
                    _harmony.Patch(AddPotionMethod, postfix: new HarmonyMethod(typeof(Execution).GetMethod(nameof(AfterAddPotion), BindingFlags.Static | BindingFlags.NonPublic)));
                    _harmony.Patch(RemovePotionMethod, new HarmonyMethod(typeof(Execution).GetMethod(nameof(BeforeRemovePotion), BindingFlags.Static | BindingFlags.NonPublic)),
                        new HarmonyMethod(typeof(Execution).GetMethod(nameof(AfterRemovePotion), BindingFlags.Static | BindingFlags.NonPublic)));
                }
                _dispatching = true;
                Choice.Potion.EnqueueManualUse(Choice.Target);
                Require(_action is not null && _completion is not null);
            } catch { _failed = true; throw; } finally { _dispatching = false; }
        }
        private static void BeforeQueue(ActionQueueSynchronizer __instance, GameAction action) {
            var o = _owner;
            if (o is null || !o._dispatching) return;
            o.Require(o._action is null && ReferenceEquals(__instance, o.View.Queue) && action.GetType() == typeof(UsePotionAction));
            var use = (UsePotionAction)action;
            o.Require(ReferenceEquals(use.Player, o.View.Player) && use.PotionIndex == o.Choice.Slot && use.WasEnqueuedInCombat == o.View.InCombat && use.TargetId == o.Choice.Target?.CombatId);
            o._action = use; o._completion = use.CompletionTask;
            use.BeforeCancelled += o.Cancelled;
            o.BeforeEffect();
        }
        private static void BeforeExecute(UsePotionAction __instance, out Execution? __state) {
            __state = Scope.Value;
            var o = _owner;
            if (o is null || !ReferenceEquals(__instance, o._action)) return;
            o.Require(!o._started); o.BeforeEffect(); o._started = true; Scope.Value = o;
        }
        private static void AfterExecute(UsePotionAction __instance, Task __result, Execution? __state) {
            Scope.Value = __state;
            var o = _owner;
            if (o is null || !ReferenceEquals(__instance, o._action)) return;
            o.Require(o._started && o._execution is null && __result is not null); o._execution = __result;
        }
        private static void AfterAddPotion(Player __instance, PotionModel __0) {
            if (Scope.Value is not { } o || !o._full) return;
            o.Require(o.OwnerContext() && ReferenceEquals(__instance, o.View.Player) && __0 is not null &&
                !o.View.Slots.Any(p => ReferenceEquals(p, __0)));
            int slot = Array.FindIndex(__instance.PotionSlots.ToArray(), p => ReferenceEquals(p, __0));
            if (slot >= 0) { o.Require(o._effects[slot] is null); o._effects[slot] = __0; o.Require(o.Inventory(true)); }
        }
        private static void BeforeRemovePotion(Player __instance, PotionModel potion, out int __state) {
            __state = -1; if (Scope.Value is not { } o || !o._full) return;
            o.Require(o._started && !o._disposed && !o._failed && o.OwnerContext() && ReferenceEquals(__instance, o.View.Player) && o.Inventory(false));
            __state = Array.FindIndex(o._effects, p => ReferenceEquals(p, potion)); o.Require(__state >= 0);
        }
        private static void AfterRemovePotion(Player __instance, PotionModel potion, int __state) {
            if (__state < 0 || Scope.Value is not { } o) return;
            o.Require(ReferenceEquals(__instance, o.View.Player) && __instance.PotionSlots[__state] is null);
            o._effects[__state] = null; o.Require(o._removed.Add(potion) && o.Inventory(true));
        }
        private void Cancelled(GameAction _) => _failed = true;
        internal bool Complete() {
            Require(!_failed && !_disposed && Environment.CurrentManagedThreadId == _thread && Environment.TickCount64 < _deadline && OwnerContext() &&
                _action is not null && ReferenceEquals(_action.CompletionTask, _completion) && _action.Exception is null &&
                _completion is not null && !_completion.IsCanceled && !_completion.IsFaulted &&
                (_execution is null || !_execution.IsCanceled && !_execution.IsFaulted));
            if (!_completion!.IsCompleted) return false;
            Require(_started && _execution is { IsCompletedSuccessfully: true } && ExecutionTask.GetValue(_action) is Task { IsCompletedSuccessfully: true } &&
                Choice.Potion.HasBeenRemovedFromState && _removed.All(p => p.HasBeenRemovedFromState) && Inventory(true));
            return _complete = true;
        }
        public void Dispose() {
            if (_disposed) return;
            // Never remove the execution guard from an action that can still
            // drain from the native queue after a host timeout or failed cleanup.
            if (!_complete || _failed) { _failed = true; throw new InvalidOperationException("Unsettled potion ownership."); }
            bool clean = true;
            try {
                foreach (var method in new[] { QueueMethod, ExecuteMethod, AddPotionMethod, RemovePotionMethod }) _harmony.Unpatch(method, HarmonyPatchType.All, _harmony.Id);
                foreach (var method in new[] { QueueMethod, ExecuteMethod, AddPotionMethod, RemovePotionMethod })
                    if (Harmony.GetPatchInfo(method)?.Owners.Contains(_harmony.Id) == true) clean = false;
                if (_action is not null) _action.BeforeCancelled -= Cancelled;
            } catch { _failed = true; throw; }
            if (!clean) { _failed = true; throw new InvalidOperationException("Unsettled potion ownership."); }
            if (ReferenceEquals(_owner, this)) _owner = null;
            _disposed = true;
        }
    }
}
