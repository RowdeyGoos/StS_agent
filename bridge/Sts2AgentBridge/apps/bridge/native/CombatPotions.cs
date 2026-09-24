using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading.Tasks;
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

// A bounded first slice: native effects run unchanged; selectors, random card
// generation and autoplay are deliberately not advertised by this protocol.
internal sealed class CombatPotions : ICombatPotions
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
    private bool _failed, _disposed;
    public bool Active => _pending is not null || _failed;
    internal CombatPotions(PinnedPublicCombatDecisionReader combat) => _combat = combat;
#if COMBAT_POTION_TEST_SEAM
    internal static void ResetFixture() => Execution.ResetFixture();
#endif
    private string Identity(object? value) => value is null ? "" : _identities.GetValue(value, _ => Guid.NewGuid().ToString("N"));
    private sealed record Choice(int Slot, PotionModel Potion, Creature? Target, int? TargetIndex, string Action);
    private sealed record View(string Decision, string CombatDecision, RunManager RunManager, CombatManager Manager,
        CombatState Combat, Player Player, PotionModel?[] Slots, Dictionary<string, Choice> Choices, object[] Inventory, object Net, object Run, ActionQueueSynchronizer Queue, int Turn, NRun Node, NCombatRoom Room);
    private static byte[] Json(object value) => JsonSerializer.SerializeToUtf8Bytes(value);
    private static bool Allowed(PotionModel potion) => potion.GetType().Assembly == typeof(PotionModel).Assembly &&
        potion.GetType().Namespace == "MegaCrit.Sts2.Core.Models.Potions" && Supported.Contains(potion.GetType().Name);
    private static bool Ready(CombatManager manager, CombatState combat, Player player) => manager.IsInProgress && !manager.IsOverOrEnding &&
        !manager.PlayerActionsDisabled && combat.CurrentSide == CombatSide.Player && player.Creature.IsAlive &&
        player.PlayerCombatState?.Phase == PlayerTurnPhase.Play && !manager.IsPlayerReadyToEndTurn(player) &&
        (NOverlayStack.Instance?.ScreenCount ?? 0) == 0 && NRun.Instance?.CombatRoom is { } room &&
        GodotObject.IsInstanceValid(room) && room.IsVisibleInTree() && ActiveScreenContext.Instance.IsCurrent(room);
    private View? Capture()
    {
        var snapshot = _combat.Read();
        if (snapshot.Status != PublicDecisionStatus.Ready) return null;
        var manager = CombatManager.Instance;
        var combat = manager.DebugOnlyGetState();
        var run = RunManager.Instance;
        if (combat is null || combat.Players.Count != 1 || run is null || (int)run.NetService.Type != 1 || run.IsAbandoned)
            throw new InvalidOperationException("Potion solo run unavailable.");
        var player = combat.Players[0];
        if (!ReferenceEquals(run.DebugOnlyGetState(), player.RunState)) throw new InvalidOperationException("Potion run changed.");
        if (!Ready(manager, combat, player)) return null;
        if (player.MaxPotionCount is < 0 or > 8 || player.PotionSlots.Count != player.MaxPotionCount)
            throw new InvalidOperationException("Potion capacity unsupported.");
        var slots = player.PotionSlots.ToArray();
        var enemies = combat.Enemies.Where(e => e.IsAlive).ToArray();
        if (enemies.Length > 6) throw new InvalidOperationException("Potion targets unsupported.");
        var actions = new Dictionary<string, Choice>(StringComparer.Ordinal);
        var inventory = new List<object>();
        for (int slot = 0; slot < slots.Length; slot++) {
            var potion = slots[slot];
            if (potion is null) continue;
            if (!ReferenceEquals(potion.Owner, player) || potion.HasBeenRemovedFromState) throw new InvalidOperationException("Potion owner changed.");
            bool supported = Allowed(potion);
            inventory.Add(new { slot, id = potion.Id.Entry, supported });
            if (!supported || !player.CanRemovePotions || potion.IsQueued || !potion.PassesCustomUsabilityCheck ||
                potion.Usage is not (PotionUsage.CombatOnly or PotionUsage.AnyTime)) continue;
            if (potion.TargetType == TargetType.AnyEnemy) {
                for (int i = 0; i < enemies.Length; i++)
                    if (enemies[i].CombatId is not null && combat.HittableEnemies.Contains(enemies[i]) && potion.IsValidTarget(enemies[i])) {
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
            combat = snapshot.DecisionId, scope = new[] { Identity(manager), Identity(combat), Identity(run), Identity(player.RunState), Identity(player), Identity(run.NetService), Identity(run.ActionQueueSynchronizer), Identity(NRun.Instance), Identity(NRun.Instance!.CombatRoom) },
            slots = slots.Select(Identity).ToArray(), enemies = enemies.Select(Identity).ToArray(), inventory,
            actions = actions.Keys.ToArray()
        }))).ToLowerInvariant();
        return new(decision, snapshot.DecisionId, run, manager, combat, player, slots, actions, inventory.ToArray(),
            run.NetService, player.RunState, run.ActionQueueSynchronizer, player.PlayerCombatState!.TurnNumber, NRun.Instance!, NRun.Instance!.CombatRoom!);
    }
    private void Check() {
        if (_disposed || _failed || Environment.CurrentManagedThreadId != _thread) throw new InvalidOperationException("Potion service stopped.");
    }
    private CombatPotionReply Fault() { _failed = true; return new(Json(new { schema_version = 1, protocol = "combat_potions_v1", status = "failed", code = "native_potion_failed" }), Terminal: true); }
    public CombatPotionReply Read()
    {
        try {
            Check();
            if (_pending is { } pending) {
                if (!pending.Complete()) return new(Json(new { schema_version = 1, protocol = "combat_potions_v1", status = "waiting" }));
                // Cleanup succeeds before any completion or ownership handoff.
                pending.Dispose();
                _pending = null;
                return new(Json(new { schema_version = 1, protocol = "combat_potions_v1", status = "resolved", decision_id = pending.View.Decision, action_id = pending.Choice.Action }));
            }
            var view = Capture();
            return view is null ? new(Json(new { schema_version = 1, protocol = "combat_potions_v1", status = "waiting" })) :
                new(Json(new { schema_version = 1, protocol = "combat_potions_v1", status = "ready", decision_id = view.Decision,
                    combat_decision_id = view.CombatDecision, potions = view.Inventory, legal_actions = view.Choices.Keys.ToArray() }));
        } catch { return Fault(); }
    }
    public CombatPotionReply Apply(string decision, string action)
    {
        try {
            Check();
            if (_pending is not null || _used.Count >= 256 || !CombatPotionRoutes.IsAction(decision, action)) return Fault();
            var view = Capture();
            if (view is null || view.Decision != decision || _used.Contains(decision))
                return new(Json(new { schema_version = 1, status = "rejected", mutation_state = "none", decision_id = decision, action_id = action, reason = "stale_decision" }), StaleWithoutMutation: true);
            if (!view.Choices.TryGetValue(action, out var choice)) return Fault();
            _used.Add(decision);
            _pending = new Execution(view, choice);
            _pending.Dispatch();
            return new(Json(new { schema_version = 1, status = "accepted", mutation_state = "queued", decision_id = decision, action_id = action, reason = "accepted" }));
        } catch { return Fault(); }
    }
    public void Dispose()
    {
        _pending?.Dispose();
        if (_failed) throw new InvalidOperationException("Potion service failed.");
        _disposed = true;
    }
    private sealed class Execution : IDisposable
    {
        private static Execution? _owner;
#if COMBAT_POTION_TEST_SEAM
        internal static void ResetFixture() {
            // Only fixture teardown after an asserted fail-closed case. A real
            // unresolved owner keeps its guards until the process exits.
            if (_owner is { } owner)
                foreach (var method in new[] { QueueMethod, ExecuteMethod }) owner._harmony.Unpatch(method, HarmonyPatchType.All, owner._harmony.Id);
            _owner = null;
        }
#endif
        private static readonly MethodInfo QueueMethod = typeof(ActionQueueSynchronizer).GetMethod("RequestEnqueue", new[] { typeof(GameAction) })!;
        private static readonly MethodInfo ExecuteMethod = typeof(UsePotionAction).GetMethod("ExecuteAction", BindingFlags.Instance | BindingFlags.NonPublic)!;
        private static readonly FieldInfo ExecutionTask = typeof(GameAction).GetField("_executionTask", BindingFlags.Instance | BindingFlags.NonPublic)!;
        private readonly Harmony _harmony = new("sts2.agent.combat.potion." + Guid.NewGuid().ToString("N"));
        internal readonly View View;
        internal readonly Choice Choice;
        private readonly int _thread = Environment.CurrentManagedThreadId;
        private readonly long _deadline = Environment.TickCount64 + 30000;
        private UsePotionAction? _action;
        private Task? _completion, _execution;
        private bool _dispatching, _started, _failed, _complete, _disposed;
        internal Execution(View view, Choice choice) { View = view; Choice = choice; }
        private void Require(bool ok) { if (!ok) { _failed = true; throw new InvalidOperationException("Owned potion execution failed."); } }
        private bool OwnerContext() => ReferenceEquals(NRun.Instance, View.Node) && ReferenceEquals(RunManager.Instance, View.RunManager) && ReferenceEquals(CombatManager.Instance, View.Manager) &&
            ReferenceEquals(View.Manager.DebugOnlyGetState(), View.Combat) && ReferenceEquals(View.RunManager.DebugOnlyGetState(), View.Run) &&
            ReferenceEquals(View.Player.RunState, View.Run) && ReferenceEquals(View.RunManager.NetService, View.Net) && (int)View.RunManager.NetService.Type == 1 &&
            !View.RunManager.IsAbandoned && ReferenceEquals(View.RunManager.ActionQueueSynchronizer, View.Queue) &&
            View.Combat.Players.Count == 1 && ReferenceEquals(View.Combat.Players[0], View.Player);
        private bool Inventory(bool consumed) => View.Player.MaxPotionCount == View.Slots.Length && View.Player.PotionSlots.Count == View.Slots.Length &&
            Enumerable.Range(0, View.Slots.Length).All(i => ReferenceEquals(View.Player.PotionSlots[i], consumed && i == Choice.Slot ? null : View.Slots[i]));
        private void BeforeEffect() {
            Require(!_failed && !_disposed && Environment.CurrentManagedThreadId == _thread && Environment.TickCount64 < _deadline && OwnerContext() &&
                ReferenceEquals(View.Node.CombatRoom, View.Room) && Ready(View.Manager, View.Combat, View.Player) && View.Player.PlayerCombatState!.TurnNumber == View.Turn && Inventory(false) &&
                ReferenceEquals(Choice.Potion.Owner, View.Player) && !Choice.Potion.HasBeenRemovedFromState && Choice.Potion.IsQueued &&
                View.Player.CanRemovePotions && Choice.Potion.PassesCustomUsabilityCheck && Choice.Potion.IsValidTarget(Choice.Target) &&
                (Choice.TargetIndex is null || Choice.Target!.IsAlive && View.Combat.HittableEnemies.Contains(Choice.Target) && Choice.Target.CombatId == _action?.TargetId));
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
            o.Require(ReferenceEquals(use.Player, o.View.Player) && use.PotionIndex == o.Choice.Slot && use.WasEnqueuedInCombat && use.TargetId == o.Choice.Target?.CombatId);
            o._action = use; o._completion = use.CompletionTask;
            use.BeforeCancelled += o.Cancelled;
            o.BeforeEffect();
        }
        private static void BeforeExecute(UsePotionAction __instance) {
            var o = _owner;
            if (o is null || !ReferenceEquals(__instance, o._action)) return;
            o.Require(!o._started); o.BeforeEffect(); o._started = true;
        }
        private static void AfterExecute(UsePotionAction __instance, Task __result) {
            var o = _owner;
            if (o is null || !ReferenceEquals(__instance, o._action)) return;
            o.Require(o._started && o._execution is null && __result is not null); o._execution = __result;
        }
        private void Cancelled(GameAction _) => _failed = true;
        internal bool Complete() {
            Require(!_failed && !_disposed && Environment.CurrentManagedThreadId == _thread && Environment.TickCount64 < _deadline && OwnerContext() &&
                _action is not null && ReferenceEquals(_action.CompletionTask, _completion) && _action.Exception is null &&
                _completion is not null && !_completion.IsCanceled && !_completion.IsFaulted &&
                (_execution is null || !_execution.IsCanceled && !_execution.IsFaulted));
            if (!_completion!.IsCompleted) return false;
            Require(_started && _execution is { IsCompletedSuccessfully: true } && ExecutionTask.GetValue(_action) is Task { IsCompletedSuccessfully: true } &&
                Choice.Potion.HasBeenRemovedFromState && Inventory(true));
            return _complete = true;
        }
        public void Dispose() {
            if (_disposed) return;
            // Never remove the execution guard from an action that can still
            // drain from the native queue after a host timeout or failed cleanup.
            if (!_complete || _failed) { _failed = true; throw new InvalidOperationException("Unsettled potion ownership."); }
            bool clean = true;
            try {
                foreach (var method in new[] { QueueMethod, ExecuteMethod }) _harmony.Unpatch(method, HarmonyPatchType.All, _harmony.Id);
                foreach (var method in new[] { QueueMethod, ExecuteMethod })
                    if (Harmony.GetPatchInfo(method)?.Owners.Contains(_harmony.Id) == true) clean = false;
                if (_action is not null) _action.BeforeCancelled -= Cancelled;
            } catch { _failed = true; throw; }
            if (!clean) { _failed = true; throw new InvalidOperationException("Unsettled potion ownership."); }
            if (ReferenceEquals(_owner, this)) _owner = null;
            _disposed = true;
        }
    }
}
