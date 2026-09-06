using System;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Native;

internal sealed class BoundEventItemV1NativeAdapter : IItemV1NativeAdapter
{
    private const int MaximumTraversedNodes = 2048;
    private readonly NRun _run;
    private readonly Player _player;
    private readonly NEventRoom _room;
    private readonly NMapScreen _map;
    private readonly NRewardsScreen _screen;

    internal BoundEventItemV1NativeAdapter(
        NRun run,
        Player player,
        NEventRoom room,
        NMapScreen map,
        NRewardsScreen screen)
    {
        _run = run;
        _player = player;
        _room = room;
        _map = map;
        _screen = screen;
    }

    public ItemV1SurfaceCapture CaptureSurface()
    {
        if (!TryGetBoundContext(out NOverlayStack? overlays) ||
            overlays!.ScreenCount != 1 || !ReferenceEquals(overlays.Peek(), _screen) ||
            !GodotObject.IsInstanceValid(_screen) || !_screen.IsVisibleInTree())
            return ItemV1SurfaceCapture.Unsupported();
        if (!TryReadOffers(out List<ItemV1NativeOffer> offers))
            return ItemV1SurfaceCapture.Unsupported();
        if (offers.Count == 0) return ItemV1SurfaceCapture.Missing();
        if (!TryCopyPotionSlots(_player, out int capacity,
                out List<ItemV1PotionSlotBinding> slots))
            return ItemV1SurfaceCapture.Unsupported();
        return ItemV1SurfaceCapture.Available(
            _run, _player, _screen, capacity, offers, slots);
    }

    public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending)
    {
        if (!ReferenceEquals(NRun.Instance, _run) ||
            !ReferenceEquals(_run.EventRoom, _room) ||
            !ReferenceEquals(pending.RunIdentity, _run) ||
            !ReferenceEquals(pending.PlayerIdentity, _player) ||
            pending.RewardIdentity is not Reward reward)
            throw new InvalidOperationException("Item parent binding changed.");
        Player rewardPlayer = reward.Player;
        if (!ReferenceEquals(rewardPlayer, _player))
            throw new InvalidOperationException("Item player binding changed.");
        object offered;
        string offeredKey;
        object? claimed;
        string? claimedKey;
        if (pending.Kind == ItemV1ItemKind.Potion &&
            reward is PotionReward potionReward && potionReward.Potion is PotionModel potion)
        {
            offered = potion;
            offeredKey = potion.Id.Entry;
            PotionModel? claimedPotion = potionReward.ClaimedPotion;
            claimed = claimedPotion;
            claimedKey = claimedPotion?.Id.Entry;
        }
        else if (pending.Kind == ItemV1ItemKind.Relic &&
                 reward is RelicReward relicReward && relicReward.Relic is RelicModel relic)
        {
            offered = relic;
            offeredKey = relic.Id.Entry;
            RelicModel? claimedRelic = relicReward.ClaimedRelic;
            claimed = claimedRelic;
            claimedKey = claimedRelic?.Id.Entry;
        }
        else
        {
            throw new InvalidOperationException("Item reward binding changed.");
        }
        if (!TryCopyPotionSlots(_player, out int capacity,
                out List<ItemV1PotionSlotBinding> slots))
            throw new InvalidOperationException("Potion inventory is unsupported.");
        return new ItemV1PendingCapture(
            _run, _player, reward, offered, offeredKey,
            reward.SuccessfullySelected, claimed, claimedKey, capacity, slots);
    }

    private bool TryGetBoundContext(out NOverlayStack? overlays)
    {
        overlays = null;
        NRun? current = NRun.Instance;
        if (!ReferenceEquals(current, _run) || !GodotObject.IsInstanceValid(_run) ||
            !ReferenceEquals(_run.EventRoom, _room) || !GodotObject.IsInstanceValid(_room))
            return false;
        var globalUi = _run.GlobalUi;
        if (globalUi is null || !GodotObject.IsInstanceValid(globalUi) ||
            !ReferenceEquals(globalUi.MapScreen, _map) ||
            !GodotObject.IsInstanceValid(_map) || _map.IsOpen ||
            _map.IsTravelEnabled || _map.IsTraveling)
            return false;
        overlays = globalUi.Overlays;
        return overlays is not null && GodotObject.IsInstanceValid(overlays);
    }

    private bool TryReadOffers(out List<ItemV1NativeOffer> offers)
    {
        var buttons = new List<NRewardButton>();
        var pending = new List<Node> { _screen };
        for (int cursor = 0; cursor < pending.Count; cursor++)
        {
            if (pending.Count > MaximumTraversedNodes)
            {
                offers = new List<ItemV1NativeOffer>();
                return false;
            }
            Node node = pending[cursor];
            if (node is NRewardButton button)
            {
                if (!GodotObject.IsInstanceValid(button))
                {
                    offers = new List<ItemV1NativeOffer>();
                    return false;
                }
                bool visible = button.IsVisibleInTree();
                if (visible && buttons.Count >= ItemV1Constants.MaximumOffers)
                {
                    offers = new List<ItemV1NativeOffer>();
                    return false;
                }
                if (visible) buttons.Add(button);
            }
            if (!AppendChildren(node, pending))
            {
                offers = new List<ItemV1NativeOffer>();
                return false;
            }
        }
        offers = new List<ItemV1NativeOffer>(buttons.Count);
        foreach (NRewardButton button in buttons)
        {
            Reward? reward = button.Reward;
            if (reward is null || !ReferenceEquals(reward.Player, _player)) return false;
            ItemV1ItemKind kind;
            object model;
            string key;
            if (reward is PotionReward potionReward && potionReward.Potion is PotionModel potion)
            {
                kind = ItemV1ItemKind.Potion; model = potion; key = potion.Id.Entry;
            }
            else if (reward is RelicReward relicReward && relicReward.Relic is RelicModel relic)
            {
                kind = ItemV1ItemKind.Relic; model = relic; key = relic.Id.Entry;
            }
            else return false;
            offers.Add(new ItemV1NativeOffer(
                reward.RewardsSetIndex, kind, key, reward.IsPopulated,
                reward.SuccessfullySelected, button.IsVisibleInTree(), button.IsEnabled,
                button, reward, model, button.ForceClick));
        }
        return true;
    }

    private static bool TryCopyPotionSlots(
        Player player,
        out int capacity,
        out List<ItemV1PotionSlotBinding> slots)
    {
        capacity = player.MaxPotionCount;
        var source = player.PotionSlots;
        int count = source.Count;
        slots = new List<ItemV1PotionSlotBinding>();
        if (capacity < 0 || capacity > ItemV1Constants.MaximumPotionSlots || count != capacity)
            return false;
        slots.Capacity = count;
        for (int index = 0; index < count; index++)
        {
            PotionModel? potion = source[index];
            slots.Add(new ItemV1PotionSlotBinding(potion, potion?.Id.Entry));
        }
        return source.Count == count && player.MaxPotionCount == capacity;
    }

    private static bool AppendChildren(Node node, List<Node> pending)
    {
        int count = node.GetChildCount(false);
        if (count < 0 || count > MaximumTraversedNodes - pending.Count) return false;
        for (int index = 0; index < count; index++)
            pending.Add(node.GetChild(index, false));
        return true;
    }
}
