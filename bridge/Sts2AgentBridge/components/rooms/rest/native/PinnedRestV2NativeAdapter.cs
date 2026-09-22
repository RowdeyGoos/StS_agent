using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Environment = System.Environment;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace Sts2AgentBridge.Rooms.Rest;

// Observe the task produced by the real button path; never invoke OnSelect or
// alter relics directly. The hook is exclusive and owned until verified removal.
public sealed class PinnedRestV2NativeAdapter : IRestV2NativeAdapter
{
    private const string Owner = "sts2-agent-bridge.rest-v2";
    private static PinnedRestV2NativeAdapter? _active;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private readonly Harmony _harmony = new(Owner);
    private MethodInfo? _target;
    private static readonly MethodInfo Postfix = typeof(PinnedRestV2NativeAdapter).GetMethod(nameof(Observe), BindingFlags.Static | BindingFlags.NonPublic)!;
    private RestV2NativeOption? _selected;
    private NRestSiteRoom? _room;
    private Task? _task;
    private RestNativeEffect? _effect;
    private Player? _player;
    private object? _overlays, _character;
    private bool _failed, _disposed;
    public static bool IsAvailable => Valid(NRun.Instance?.RestSiteRoom) && NRun.Instance!.RestSiteRoom!.IsVisibleInTree();
    private static bool Valid(GodotObject? value) => value is not null && GodotObject.IsInstanceValid(value);
    private static void Require(bool value) { if (!value) throw new InvalidOperationException("rest_native_boundary"); }
    private void Check() => Require(!_disposed && !_failed && Environment.CurrentManagedThreadId == _thread);

    public RestV2Surface Capture()
    {
        Check();
        var run = NRun.Instance;
        var room = run?.RestSiteRoom;
        var map = run?.GlobalUi?.MapScreen;
        var overlays = run?.GlobalUi?.Overlays;
        Require(Valid(run) && Valid(room) && room!.GetType() == typeof(NRestSiteRoom) &&
            ReferenceEquals(room, NRestSiteRoom.Instance) && Valid(map) && Valid(overlays) &&
            room.Characters.Count == 1 && Valid(room.Characters[0]) && room.Characters[0].IsVisibleInTree());
        _overlays ??= overlays; _character ??= room!.Characters[0];
        Require(ReferenceEquals(overlays, _overlays) && ReferenceEquals(room!.Characters[0], _character));
        var player = room!.Characters[0].Player;
        Require(player is not null);
        bool foreground = room.IsVisibleInTree() && !map!.IsOpen && !map.IsTraveling && overlays!.ScreenCount == 0;
        var options = new List<RestV2NativeOption>();
        RestV2Card[] cards = Array.Empty<RestV2Card>();
        if (_selected is null)
        {
            Require(room.Options.Count <= 16);
            var state = new RestNativeState(player!); Require(state.Deck.Length <= 64);
            cards = state.PublicCards;
            foreach (var option in room.Options)
            {
                string? action = option.GetType() == typeof(LiftRestSiteOption) ? "lift" :
                    option.GetType() == typeof(KindleRestSiteOption) ? "kindle" :
                    option.GetType() == typeof(DigRestSiteOption) ? "dig" :
                    option.GetType() == typeof(CookRestSiteOption) ? "cook" :
                    option.GetType() == typeof(CloneRestSiteOption) ? "clone" :
                    option.GetType() == typeof(HatchRestSiteOption) ? "hatch" : null;
                if (action is null) continue;
                Require(ReferenceEquals(OptionOwner(option), player));
                // Each egg can contribute the same Hatch option; either one
                // hatches all eggs. Bind the first exact native controller.
                if (action == "hatch" && options.Any(o => o.Public.ActionId == action)) continue;
                object? relic = Anchor(action, player!, state);
                Require(relic is not null);
                var button = room.GetButtonForOption(option);
                Require(Valid(button) && button!.GetType() == typeof(NRestSiteButton) && ReferenceEquals(button.Option, option));
                options.Add(new(new(action, Counter(action, player!, relic!), foreground && option.IsEnabled && button!.IsEnabled && button.IsVisibleInTree(),
                    action == "clone" ? state.Clonable.Length : 0), option, relic!, button!, state));
            }
        }
        else
        {
            Require(ReferenceEquals(room, _room) && ReferenceEquals(OptionOwner((RestSiteOption)_selected.Option), player) &&
                _selected.Witness is RestNativeState bound && ReferenceEquals(bound.RunState, player!.RunState) &&
                (_selected.Public.ActionId == "hatch" || ReferenceEquals(_selected.Relic, Anchor(_selected.Public.ActionId, player!, null))));
        }
        return new(run!, player!, room, map!, foreground, options) { Cards = cards };
    }
    private static object? Anchor(string action, Player player, RestNativeState? state) => action switch {
        "lift" => player.GetRelic<Girya>(), "kindle" => player.GetRelic<PumpkinCandle>(), "dig" => player.GetRelic<Shovel>(),
        "cook" => player.GetRelic<MeatCleaver>(), "clone" => player.GetRelic<PaelsGrowth>(), "hatch" => state?.Eggs.FirstOrDefault()?.Model,
        _ => null };
    private static int Counter(string action, Player player, object relic) => action switch {
        "lift" => ((Girya)relic).TimesLifted, "kindle" => ((PumpkinCandle)relic).KindleCount,
        "dig" or "hatch" => player.Relics.Count, "clone" => player.Deck.Cards.Count, "cook" => player.Creature.MaxHp,
        _ => throw new InvalidOperationException("rest_relic") };
    private static object? OptionOwner(RestSiteOption option) =>
        typeof(RestSiteOption).GetProperty("Owner", BindingFlags.Instance | BindingFlags.NonPublic)?.GetValue(option);

    public void Begin(RestV2NativeOption option, string action)
    {
        Check(); Require(_selected is null && _active is null);
        var surface = Capture();
        Require(surface.Foreground && surface.Options.Any(x => x.Public == option.Public &&
            x.Public.Enabled && ReferenceEquals(x.Option, option.Option) && ReferenceEquals(x.Relic, option.Relic) && ReferenceEquals(x.Button, option.Button) && Equals(x.Witness, option.Witness)));
        Require(RestV2Session.Actions(surface.Options.Select(o => o.Public).ToArray(), surface.Cards).Contains(action));
        _selected = option; _room = (NRestSiteRoom)surface.Room; _player = (Player)surface.Player;
        _target = typeof(NRestSiteRoom).GetMethod("AfterSelectingOptionAsync", BindingFlags.Instance | BindingFlags.NonPublic,
            null, new[] { typeof(RestSiteOption) }, null);
        Require(_target is not null && _target.ReturnType == typeof(Task) && Harmony.GetPatchInfo(_target)?.Owners.Count is not > 0);
        _active = this; // Retain cleanup ownership even if Patch throws partway through.
        _harmony.Patch(_target!, postfix: new HarmonyMethod(Postfix));
        Require(ExactPatch());
        if (option.Public.ActionId is not ("lift" or "kindle"))
        {
            var run = (NRun)surface.Run;
            _effect = new((RestSiteOption)option.Option, action, (RestNativeState)option.Witness!, (NOverlayStack)_overlays!,
                () => ReferenceEquals(NRun.Instance, run) && ReferenceEquals(run.RestSiteRoom, _room) && ReferenceEquals(NRestSiteRoom.Instance, _room) &&
                    Valid(_room) && _room!.IsVisibleInTree() && _room.Characters.Count == 1 && ReferenceEquals(_room.Characters[0], _character) &&
                    ReferenceEquals(_room.Characters[0].Player, _player) && ReferenceEquals(run.GlobalUi.MapScreen, surface.Map) &&
                    !run.GlobalUi.MapScreen.IsOpen && !run.GlobalUi.MapScreen.IsTraveling && ReferenceEquals(run.GlobalUi.Overlays, _overlays));
            _effect.Install();
        }
        ((NRestSiteButton)option.Button).ForceClick();
        Check();
    }
    private static void Observe(NRestSiteRoom __instance, RestSiteOption __0, Task __result)
    {
        var active = _active;
        if (active is null) return;
        if (Environment.CurrentManagedThreadId != active._thread || active._task is not null ||
            !ReferenceEquals(__instance, active._room) || !ReferenceEquals(__0, active._selected?.Option) || __result is null)
        { active._failed = true; return; }
        active._task = __result;
    }
    private bool ExactPatch()
    {
        var p = _target is null ? null : Harmony.GetPatchInfo(_target);
        return ReferenceEquals(_active, this) && p is not null && p.Prefixes.Count == 0 && p.Transpilers.Count == 0 &&
            p.Finalizers.Count == 0 && p.Postfixes.Count == 1 && p.Postfixes[0].owner == Owner && p.Postfixes[0].PatchMethod == Postfix;
    }
    public RestV2Progress Poll()
    {
        Check(); Require(_selected is not null && ExactPatch());
        _effect?.Advance();
        bool completed = _task?.Status == TaskStatus.RanToCompletion && (_effect is null || _effect.Completed);
        if (completed) _effect?.Verify();
        return new(completed, _task?.IsFaulted == true || _task?.IsCanceled == true, Counter(_selected!.Public.ActionId, _player!, _selected.Relic));
    }
    public void Finish() { Check(); Require(_task?.Status == TaskStatus.RanToCompletion && ExactPatch()); _effect?.Verify(); _effect?.Dispose(); RemoveHook(); }
    private void RemoveHook()
    {
        if (!ReferenceEquals(_active, this)) return;
        var p = Harmony.GetPatchInfo(_target!);
        Require(p is null || !p.Prefixes.Concat(p.Postfixes).Concat(p.Transpilers).Concat(p.Finalizers).Any(x => x.PatchMethod == Postfix && x.owner != Owner));
        _harmony.Unpatch(_target!, Postfix);
        p = Harmony.GetPatchInfo(_target!);
        Require(p is null || !p.Prefixes.Concat(p.Postfixes).Concat(p.Transpilers).Concat(p.Finalizers).Any(x => x.owner == Owner || x.PatchMethod == Postfix));
        _active = null;
    }
    public void Dispose()
    {
        Require(Environment.CurrentManagedThreadId == _thread);
        if (_disposed) return;
        _effect?.Dispose(); RemoveHook(); _disposed = true;
    }
}
