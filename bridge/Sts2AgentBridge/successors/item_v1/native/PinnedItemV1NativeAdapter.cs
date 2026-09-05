using System;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rewards;

namespace Sts2AgentBridge.Successors.ItemV1.Native;

/// <summary>
/// Captures the pinned public UI surface. A future composition must invoke every
/// member on the Godot frame thread; this adapter performs no thread marshalling.
/// </summary>
public sealed class PinnedItemV1NativeAdapter : IItemV1NativeAdapter
{
    private const int MaximumTraversedNodes = 2048;

    public ItemV1SurfaceCapture CaptureSurface()
    {
        NRun? run = NRun.Instance;
        if (run is null || !GodotObject.IsInstanceValid(run))
        {
            return ItemV1SurfaceCapture.Missing();
        }
        var globalUi = run.GlobalUi;
        if (globalUi is null || !GodotObject.IsInstanceValid(globalUi))
        {
            return ItemV1SurfaceCapture.Missing();
        }
        var map = globalUi.MapScreen;
        if (map is null || !GodotObject.IsInstanceValid(map))
        {
            return ItemV1SurfaceCapture.Missing();
        }
        if (map.IsOpen || map.IsTraveling)
        {
            return ItemV1SurfaceCapture.Unsupported();
        }
        NOverlayStack? overlays = globalUi.Overlays;
        if (overlays is null || !GodotObject.IsInstanceValid(overlays) ||
            overlays.ScreenCount == 0)
        {
            return ItemV1SurfaceCapture.Missing();
        }
        object? top = overlays.Peek();
        if (top is not NRewardsScreen screen ||
            !GodotObject.IsInstanceValid(screen) || !screen.IsVisibleInTree())
        {
            return ItemV1SurfaceCapture.Missing();
        }

        var buttons = new List<NRewardButton>();
        var pending = new List<Node> { screen };
        for (int cursor = 0; cursor < pending.Count; cursor++)
        {
            if (pending.Count > MaximumTraversedNodes)
            {
                return ItemV1SurfaceCapture.Unsupported();
            }
            Node node = pending[cursor];
            if (node is NRewardButton button)
            {
                if (!GodotObject.IsInstanceValid(button))
                {
                    return ItemV1SurfaceCapture.Unsupported();
                }
                if (button.IsVisibleInTree())
                {
                    buttons.Add(button);
                    if (buttons.Count > ItemV1Constants.MaximumOffers)
                    {
                        return ItemV1SurfaceCapture.Unsupported();
                    }
                }
            }
            if (!AppendChildren(node, pending))
            {
                return ItemV1SurfaceCapture.Unsupported();
            }
        }
        if (buttons.Count == 0)
        {
            return ItemV1SurfaceCapture.Missing();
        }

        Player? player = null;
        var offers = new List<ItemV1NativeOffer>(buttons.Count);
        foreach (NRewardButton button in buttons)
        {
            Reward? reward = button.Reward;
            if (reward is null)
            {
                return ItemV1SurfaceCapture.Unsupported();
            }

            ItemV1ItemKind kind;
            object model;
            string key;
            if (reward is PotionReward potionReward && potionReward.Potion is PotionModel potion)
            {
                kind = ItemV1ItemKind.Potion;
                model = potion;
                key = potion.Id.Entry;
            }
            else if (reward is RelicReward relicReward && relicReward.Relic is RelicModel relic)
            {
                kind = ItemV1ItemKind.Relic;
                model = relic;
                key = relic.Id.Entry;
            }
            else
            {
                return ItemV1SurfaceCapture.Unsupported();
            }
            Player? rewardPlayer = reward.Player;
            if (rewardPlayer is null)
            {
                return ItemV1SurfaceCapture.Unsupported();
            }
            if (player is null)
            {
                player = rewardPlayer;
            }
            else if (!ReferenceEquals(player, rewardPlayer))
            {
                return ItemV1SurfaceCapture.Unsupported();
            }
            offers.Add(new ItemV1NativeOffer(
                reward.RewardsSetIndex,
                kind,
                key,
                reward.IsPopulated,
                reward.SuccessfullySelected,
                button.IsVisibleInTree(),
                button.IsEnabled,
                button,
                reward,
                model,
                button.ForceClick));
        }
        if (player is null)
        {
            return ItemV1SurfaceCapture.Missing();
        }
        if (!TryCopyPotionSlots(player, out int capacity,
                out List<ItemV1PotionSlotBinding> slots))
        {
            return ItemV1SurfaceCapture.Unsupported();
        }
        return ItemV1SurfaceCapture.Available(
            run, player, screen, capacity, offers, slots);
    }

    public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending)
    {
        NRun? run = NRun.Instance;
        if (run is null || !GodotObject.IsInstanceValid(run) ||
            !ReferenceEquals(run, pending.RunIdentity) ||
            pending.RewardIdentity is not Reward reward ||
            pending.PlayerIdentity is not Player expectedPlayer)
        {
            throw new InvalidOperationException("Item context is unavailable.");
        }
        Player player = reward.Player;
        object offered;
        string offeredKey;
        object? claimed;
        string? claimedKey;
        if (pending.Kind == ItemV1ItemKind.Potion &&
            reward is PotionReward potionReward && potionReward.Potion is PotionModel potion)
        {
            offered = potion;
            offeredKey = potion.Id.Entry;
            claimed = potionReward.ClaimedPotion;
            claimedKey = potionReward.ClaimedPotion?.Id.Entry;
        }
        else if (pending.Kind == ItemV1ItemKind.Relic &&
                 reward is RelicReward relicReward && relicReward.Relic is RelicModel relic)
        {
            offered = relic;
            offeredKey = relic.Id.Entry;
            claimed = relicReward.ClaimedRelic;
            claimedKey = relicReward.ClaimedRelic?.Id.Entry;
        }
        else
        {
            throw new InvalidOperationException("Item binding changed.");
        }
        if (!ReferenceEquals(player, expectedPlayer))
        {
            throw new InvalidOperationException("Player binding changed.");
        }
        if (!TryCopyPotionSlots(player, out int capacity,
                out List<ItemV1PotionSlotBinding> slots))
        {
            throw new InvalidOperationException("Potion inventory is unsupported.");
        }
        return new ItemV1PendingCapture(
            run,
            player,
            reward,
            offered,
            offeredKey,
            reward.SuccessfullySelected,
            claimed,
            claimedKey,
            capacity,
            slots);
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
        if (capacity < 0 || capacity > ItemV1Constants.MaximumPotionSlots ||
            count != capacity)
        {
            return false;
        }
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
        if (count < 0 || count > MaximumTraversedNodes - pending.Count)
        {
            return false;
        }
        for (int index = 0; index < count; index++)
        {
            pending.Add(node.GetChild(index, false));
        }
        return true;
    }
}
