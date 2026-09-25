using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.TreasureRelicPicking;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic;

namespace Sts2AgentBridge.Unified;

internal sealed partial class CampaignTreasureTransition
{
    private static readonly AsyncLocal<CampaignTreasureTransition?> AwardScope = new();
    private static readonly MethodInfo ClaimQueue = typeof(ActionQueueSynchronizer).GetMethod("RequestEnqueue", new[] { typeof(GameAction) })!;
    private static readonly MethodInfo Award = typeof(NTreasureRoomRelicCollection).GetMethod("AnimateRelicAwards", Private)!;
    private static readonly MethodInfo Mutable = typeof(RelicModel).GetMethod("ToMutable", Type.EmptyTypes)!;
    private static readonly MethodInfo Obtain = typeof(RelicCmd).GetMethod("Obtain", new[] { typeof(RelicModel), typeof(Player), typeof(int) })!;
    private static readonly FieldInfo ClaimPlayer = typeof(PickRelicAction).GetField("_player", Private)!;
    private static readonly FieldInfo ClaimIndex = typeof(PickRelicAction).GetField("_relicIndex", Private)!;
    private static readonly FieldInfo ClaimExecution = typeof(GameAction).GetField("_executionTask", Private)!;
    private static readonly FieldInfo OpenTicks = typeof(NTreasureRoomRelicCollection).GetField("_openedTicks", Private)!;
    private static readonly MethodInfo[] ClaimTargets = { ClaimQueue, Award, Mutable, Obtain };
    private readonly bool _full;
    private NTreasureRoomRelicHolder? _holder;
    private RelicModel? _offered, _obtainedRelic;
    private RelicModel[]? _beforeRelics;
    private GameAction? _claimAction;
    private Task? _awardTask;
    private Task<RelicModel>? _obtainTask;
    private bool _claimStarted, _claimExecuting, _awardSeen, _leavingClaim, _claimHooksClean;

    internal object OfferIdentity { get; } = new();
    internal RelicModel? ObtainedRelic => _claimHooksClean && _obtainTask?.IsCompletedSuccessfully == true ? _obtainedRelic : null;
    internal RelicModel? OfferedRelic { get { Require(_full && Read() == "relic"); return _offered; } }
    private void CaptureRelic()
    {
        var holder = _collection.SingleplayerRelicHolder;
        Require(Enabled(holder) && holder.Relic?.Model is not null &&
            ActiveScreenContext.Instance.IsCurrent(_screen) && OpenTicks.GetValue(_collection) is ulong ticks && Time.GetTicksMsec() > ticks + 200);
        _holder ??= holder; _offered ??= holder.Relic.Model;
        Require(ReferenceEquals(holder, _holder) && ReferenceEquals(holder.Relic.Model, _offered) &&
            _synchronizer.CurrentRelics is { Count: 1 } relics && ReferenceEquals(relics[0], _offered) && holder.Index == 0);
    }
    private void Claim()
    {
        CaptureRelic();
        Require(!_claimStarted && !_skipped && ReferenceEquals(_owner, this));
        foreach (var target in ClaimTargets) Require(target is not null && !(Harmony.GetPatchInfo(target)?.Owners.Any() ?? false));
        _beforeRelics = _run.Players[0].Relics.ToArray(); _claimStarted = true;
        try
        {
            ClaimPatch(ClaimQueue, nameof(BeforeClaimQueue));
            ClaimPatch(Award, nameof(BeforeAward), nameof(AfterAward));
            ClaimPatch(Mutable, nameof(BeforeMutable), nameof(AfterMutable));
            ClaimPatch(Obtain, nameof(BeforeObtain), nameof(AfterObtain));
            _dispatching = true;
            Require(_holder!.EmitSignal(NClickableControl.SignalName.Released, _holder) == Error.Ok && _claimAction is not null);
        }
        catch { _failed = true; throw; }
        finally { _dispatching = false; }
    }
    private void ClaimPatch(MethodInfo target, string prefix, string? postfix = null) => _harmony.Patch(target,
        new HarmonyMethod(typeof(CampaignTreasureTransition).GetMethod(prefix, BindingFlags.Static | BindingFlags.NonPublic)),
        postfix is null ? null : new HarmonyMethod(typeof(CampaignTreasureTransition).GetMethod(postfix, BindingFlags.Static | BindingFlags.NonPublic)));
    private static void BeforeClaimQueue(ActionQueueSynchronizer __instance, GameAction action)
    {
        var o = _owner!; o.Context();
        o.Require(o._dispatching && o._claimAction is null && ReferenceEquals(__instance, o._queue) &&
            action.GetType() == typeof(PickRelicAction) && ReferenceEquals(ClaimPlayer.GetValue(action), o._player) &&
            ClaimIndex.GetValue(action) is 0 && ((PickRelicAction)action).TestSynchronizer is null);
        o._claimAction = action; action.BeforeExecuted += o.BeforeClaim; action.BeforeCancelled += o.CancelClaim;
    }
    private void BeforeClaim(GameAction action)
    {
        Context(); CaptureRelic();
        Require(ReferenceEquals(action, _claimAction) && !_claimExecuting &&
            ReferenceEquals(ClaimPlayer.GetValue(action), _player) && ClaimIndex.GetValue(action) is 0 &&
            ((PickRelicAction)action).TestSynchronizer is null);
        _claimExecuting = true;
    }
    private void CancelClaim(GameAction _) { _failed = true; }
    private static void BeforeAward(NTreasureRoomRelicCollection __instance, List<RelicPickingResult> results, out CampaignTreasureTransition? __state)
    {
        var o = _owner!; o.Context();
        o.Require(o._claimExecuting && !o._awardSeen && ReferenceEquals(__instance, o._collection) && results.Count == 1 &&
            ReferenceEquals(results[0].player, o._player) && ReferenceEquals(results[0].relic, o._offered) &&
            results[0].type != RelicPickingResultType.Skipped && results[0].fight is null);
        o._awardSeen = true; __state = AwardScope.Value; AwardScope.Value = o;
    }
    private static void AfterAward(Task __result, CampaignTreasureTransition? __state)
    { var o = AwardScope.Value!; AwardScope.Value = __state; o.Require(o._awardTask is null && __result is not null); o._awardTask = __result; }
    private static void BeforeMutable(RelicModel __instance, out CampaignTreasureTransition? __state)
    {
        __state = AwardScope.Value; if (__state is not {} o) return;
        o.Context(); o.Require(o._obtainedRelic is null && ReferenceEquals(__instance, o._offered));
    }
    private static void AfterMutable(RelicModel __result, CampaignTreasureTransition? __state)
    { if (__state is {} o) { o.Require(__result is not null && !ReferenceEquals(__result, o._offered)); o._obtainedRelic = __result; } }
    private static void BeforeObtain(RelicModel relic, Player player, int index, out CampaignTreasureTransition? __state)
    {
        __state = AwardScope.Value; if (__state is not {} o) return;
        o.Context(); o.Require(o._obtainTask is null && ReferenceEquals(relic, o._obtainedRelic) && ReferenceEquals(player, o._player) && index == -1);
    }
    private static void AfterObtain(Task<RelicModel> __result, CampaignTreasureTransition? __state)
    { if (__state is {} o) { o.Require(__result is not null); o._obtainTask = __result; } }
    private string ReadClaim()
    {
        Require(_claimAction is not null && _claimAction.Exception is null && _awardTask?.IsFaulted != true &&
            _awardTask?.IsCanceled != true && _obtainTask?.IsFaulted != true && _obtainTask?.IsCanceled != true);
        if (!_claimAction!.CompletionTask.IsCompletedSuccessfully || _awardTask?.IsCompletedSuccessfully != true ||
            _obtainTask?.IsCompletedSuccessfully != true || !_openTask!.IsCompletedSuccessfully) return "waiting";
        Require(_claimExecuting && ClaimExecution.GetValue(_claimAction) is Task { IsCompletedSuccessfully: true } &&
            _pickingBegan.IsCompletedSuccessfully && _pickingFinished.IsCompletedSuccessfully &&
            Choosing.GetValue(_screen) is false && Opened.GetValue(_screen) is true && !_skip.IsSkip &&
            ReferenceEquals(_obtainTask.Result, _obtainedRelic) && ReferenceEquals(_obtainedRelic!.Owner, _player));
        var relics = _run.Players[0].Relics;
        Require(relics.Count == _beforeRelics!.Length + 1 && ReferenceEquals(relics[^1], _obtainedRelic) &&
            _beforeRelics.Select((r, i) => ReferenceEquals(r, relics[i])).All(same => same));
        CleanupClaim();
        if (!_leavingClaim) { Require(ActiveScreenContext.Instance.IsCurrent(_screen)); return Enabled(_skip) ? "proceed" : "waiting"; }
        string destination = _leave!.Poll();
        if (destination == "map") _complete = true;
        return destination;
    }
    private void CleanupClaim()
    {
        if (!_claimStarted || _claimHooksClean) return;
        foreach (var target in ClaimTargets) _harmony.Unpatch(target, HarmonyPatchType.All, _harmony.Id);
        foreach (var target in ClaimTargets) Require(Harmony.GetPatchInfo(target)?.Owners.Contains(_harmony.Id) != true);
        // Unsettled queued actions retain their revocation guard after disposal.
        if (_obtainTask?.IsCompletedSuccessfully == true && _claimAction?.CompletionTask.IsCompletedSuccessfully == true)
        { _claimAction.BeforeExecuted -= BeforeClaim; _claimAction.BeforeCancelled -= CancelClaim; }
        _claimHooksClean = true;
    }
}
