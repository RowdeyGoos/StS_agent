using System;
using System.Collections.Generic;

namespace Godot
{
    public class GodotObject
    {
        public bool InstanceValid { get; set; } = true;
        public static bool IsInstanceValid(GodotObject? value) => value?.InstanceValid == true;
    }
    public class Node : GodotObject
    {
        private readonly List<Node> _children = new();
        public bool Visible { get; set; } = true;
        public Dictionary<string, Node> Named { get; } = new(StringComparer.Ordinal);
        public virtual bool IsVisibleInTree() => Visible;
        public Node GetNode(string path) => Named[path];
        public void AddChild(Node child) => _children.Add(child);
        public int GetChildCount(bool includeInternal) => _children.Count;
        public Node GetChild(int index, bool includeInternal) => _children[index];
    }
    public class CanvasItem : Node { }
    public class Control : CanvasItem { }
}

namespace MegaCrit.Sts2.addons.mega_text
{
    public class MegaRichTextLabel : Godot.Control { public string Text { get; set; } = string.Empty; }
}

namespace MegaCrit.Sts2.Core.Entities.Players
{
    using MegaCrit.Sts2.Core.Models;
    public class Player
    {
        public int MaxPotionCount { get; set; }
        public List<PotionModel?> PotionSlots { get; } = new();
    }
}

namespace MegaCrit.Sts2.Core.Events
{
    using MegaCrit.Sts2.Core.Entities.Players;
    public class EventOption
    {
        public string TextKey { get; set; } = string.Empty;
        public bool IsProceed { get; set; }
        public bool IsLocked { get; set; }
        public Func<Player, bool>? WillKillPlayer { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Models
{
    using MegaCrit.Sts2.Core.Entities.Players;
    public class EventModel
    {
        public Player? Owner { get; set; }
        public bool IsFinished { get; set; }
    }
    public sealed class ModelId { public string Entry { get; set; } = string.Empty; }
    public class PotionModel { public ModelId Id { get; set; } = new(); }
    public class RelicModel { public ModelId Id { get; set; } = new(); }
}

namespace MegaCrit.Sts2.Core.Models.Events
{
    public class RoomFullOfCheese : MegaCrit.Sts2.Core.Models.EventModel { }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.Map
{
    public class NMapScreen : Godot.Control
    {
        public static NMapScreen? Instance { get; set; }
        public bool IsOpen { get; set; }
        public bool IsTravelEnabled { get; set; }
        public bool IsTraveling { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.Overlays
{
    public class NOverlayStack : Godot.Node
    {
        public List<object> Screens { get; } = new();
        public int ScreenCount => Screens.Count;
        public object? Peek() => Screens.Count == 0 ? null : Screens[^1];
    }
}

namespace MegaCrit.Sts2.Core.Nodes
{
    using MegaCrit.Sts2.Core.Nodes.Rooms;
    using MegaCrit.Sts2.Core.Nodes.Screens.Map;
    using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
    public class GlobalUiState : Godot.Node
    {
        public NMapScreen MapScreen { get; set; } = null!;
        public NOverlayStack Overlays { get; set; } = null!;
    }
    public class NRun : Godot.Node
    {
        public static NRun? Instance { get; set; }
        public GlobalUiState GlobalUi { get; set; } = null!;
        public NEventRoom? EventRoom { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Events
{
    using MegaCrit.Sts2.Core.Events;
    using MegaCrit.Sts2.Core.Models;
    public class NEventLayout : Godot.Control
    {
        public List<NEventOptionButton> OptionButtons { get; } = new();
    }
    public class NEventOptionButton : Godot.Control
    {
        public EventOption Option { get; set; } = null!;
        public EventModel Event { get; set; } = null!;
        public bool IsEnabled { get; set; } = true;
        public bool ThrowClick { get; set; }
        public int Clicks { get; private set; }
        public void ForceClick()
        {
            Clicks++;
            if (ThrowClick) throw new InvalidOperationException("click");
        }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Rooms
{
    using MegaCrit.Sts2.Core.Nodes.Events;
    public class NEventRoom : Godot.Control
    {
        public static NEventRoom? Instance { get; set; }
        public NEventLayout Layout { get; set; } = null!;
        public object? CustomEventNode { get; set; }
        public object? EmbeddedCombatRoom { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens
{
    public class NRewardsScreen : Godot.Control { }
}

namespace MegaCrit.Sts2.Core.Rewards
{
    using MegaCrit.Sts2.Core.Entities.Players;
    using MegaCrit.Sts2.Core.Models;
    public abstract class Reward
    {
        public Player Player { get; set; } = null!;
        public int RewardsSetIndex { get; set; }
        public bool IsPopulated { get; set; } = true;
        public bool SuccessfullySelected { get; set; }
    }
    public sealed class PotionReward : Reward
    {
        public PotionModel? Potion { get; set; }
        public PotionModel? ClaimedPotion { get; set; }
    }
    public sealed class RelicReward : Reward
    {
        public RelicModel? Relic { get; set; }
        public RelicModel? ClaimedRelic { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Rewards
{
    using MegaCrit.Sts2.Core.Rewards;
    public class NRewardButton : Godot.Control
    {
        public Reward Reward { get; set; } = null!;
        public bool IsEnabled { get; set; } = true;
        public int Clicks { get; private set; }
        public void ForceClick()
        {
            Clicks++;
            Reward.SuccessfullySelected = true;
            if (Reward is PotionReward potion && potion.Potion is not null)
            {
                potion.ClaimedPotion = potion.Potion;
                int empty = potion.Player.PotionSlots.FindIndex(static p => p is null);
                if (empty >= 0) potion.Player.PotionSlots[empty] = potion.Potion;
            }
            else if (Reward is RelicReward relic) relic.ClaimedRelic = relic.Relic;
        }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection
{
    public class NSimpleCardSelectScreen : Godot.Control { }
}
