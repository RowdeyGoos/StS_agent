using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.TreasureRelicPicking;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic;

namespace Sts2AgentBridge.Unified;

internal sealed partial class CampaignTreasureTransition
{
    private static readonly MethodInfo EmptyCompletion=typeof(TreasureRoomRelicSynchronizer).GetMethod("CompleteWithNoRelics")!;
    private readonly bool _empty;
    private bool _emptySeen,_emptyDispatching;
    private Task? _emptyAward;
    private RelicModel[]? _emptyRelics;
    private void InstallEmpty()
    {
        foreach(var target in new[]{EmptyCompletion,Award})Require(target is not null&&!(Harmony.GetPatchInfo(target)?.Owners.Any()??false));
        _emptyRelics=_run.Players[0].Relics.ToArray();
        ClaimPatch(EmptyCompletion,nameof(BeforeEmpty),nameof(AfterEmpty));
        ClaimPatch(Award,nameof(BeforeEmptyAward),nameof(AfterEmptyAward));
    }
    private static void BeforeEmpty(TreasureRoomRelicSynchronizer __instance)
    {
        var o=_owner!;o.Context();o.Require(o._empty&&o._started&&o._openCalled&&!o._emptySeen&&
            ReferenceEquals(__instance,o._synchronizer)&&__instance.CurrentRelics is null or {Count:0});
        o._emptySeen=true;o._emptyDispatching=true;
    }
    private static void AfterEmpty(){var o=_owner!;o.Require(o._emptyDispatching&&o._emptyAward is not null);o._emptyDispatching=false;}
    private static void BeforeEmptyAward(NTreasureRoomRelicCollection __instance,List<RelicPickingResult> results)
    {var o=_owner!;o.Context();o.Require(o._emptyDispatching&&o._emptyAward is null&&ReferenceEquals(__instance,o._collection)&&results.Count==0);}
    private static void AfterEmptyAward(Task __result){var o=_owner!;o.Require(__result is not null);o._emptyAward=__result;}
    private string ReadEmpty()
    {
        Require(_emptyAward?.IsFaulted!=true&&_emptyAward?.IsCanceled!=true&&_run.Players[0].Relics.SequenceEqual(_emptyRelics!));
        if(!_emptySeen||_emptyAward?.IsCompletedSuccessfully!=true||_openTask?.IsCompletedSuccessfully!=true||
            !_pickingBegan.IsCompletedSuccessfully||!_pickingFinished.IsCompletedSuccessfully)return "waiting";
        // Native cancels its delayed Skip task once the automatic empty award
        // begins, then enables ordinary Proceed after the chest animation.
        Require(!_emptyDispatching&&Opened.GetValue(_screen) is true&&Choosing.GetValue(_screen) is false&&
            _synchronizer.CurrentRelics is null&&_ftueTask?.IsCompletedSuccessfully==true&&!_skip.IsSkip&&
            !_collection.SingleplayerRelicHolder.IsVisibleInTree());
        if(!_leavingClaim){Require(ActiveScreenContext.Instance.IsCurrent(_screen));return Enabled(_skip)?"proceed":"waiting";}
        string destination=_leave!.Poll();if(destination=="map")_complete=true;return destination;
    }
    private void CleanupEmpty()
    {
        if(!_empty)return;
        foreach(var target in new[]{EmptyCompletion,Award})_harmony.Unpatch(target,HarmonyPatchType.All,_harmony.Id);
        foreach(var target in new[]{EmptyCompletion,Award})Require(Harmony.GetPatchInfo(target)?.Owners.Contains(_harmony.Id)!=true);
    }
}
