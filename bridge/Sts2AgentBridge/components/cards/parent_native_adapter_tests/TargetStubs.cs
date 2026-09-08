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
        public bool Visible { get; set; } = true;
        public List<Node> Children { get; } = new();
        public virtual bool IsVisibleInTree() => Visible;
        public IEnumerable<Node> GetChildren() => Children;
    }

    public class CanvasItem : Node { }
    public class Control : CanvasItem { }
}

namespace MegaCrit.Sts2.Core.Models
{
    public class CardModel
    {
        public bool IsUpgradable { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Entities.Players
{
    using MegaCrit.Sts2.Core.Models;

    public sealed class Deck
    {
        public List<CardModel> Cards { get; } = new();
    }

    public class Player
    {
        public Deck Deck { get; } = new();
    }
}

namespace MegaCrit.Sts2.Core.Events
{
    public class EventOption
    {
        public string TextKey { get; set; } = string.Empty;
        public bool IsProceed { get; set; }
        public bool IsLocked { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Models.Events
{
    using MegaCrit.Sts2.Core.Entities.Players;

    public class RoomFullOfCheese
    {
        public Player? Owner { get; set; }
        public bool IsFinished { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Entities.RestSite
{
    public class RestSiteOption
    {
        public string OptionId { get; set; } = string.Empty;
        public bool IsEnabled { get; set; } = true;
    }

    public class SmithRestSiteOption : RestSiteOption
    {
        public int SmithCount { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.Map
{
    using Godot;

    public class NMapScreen : Control
    {
        public static NMapScreen? Instance { get; set; }
        public bool IsOpen { get; set; }
        public bool IsTravelEnabled { get; set; }
        public bool IsTraveling { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.Overlays
{
    using Godot;

    public class NOverlayStack : Node
    {
        public List<object> Screens { get; } = new();
        public int ScreenCount => Screens.Count;
        public object? Peek() => Screens.Count == 0 ? null : Screens[^1];
    }
}

namespace MegaCrit.Sts2.Core.Nodes
{
    using Godot;
    using MegaCrit.Sts2.Core.Nodes.Rooms;
    using MegaCrit.Sts2.Core.Nodes.Screens.Map;
    using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

    public sealed class GlobalUiState
    {
        public NMapScreen MapScreen { get; set; } = null!;
        public NOverlayStack Overlays { get; set; } = null!;
    }

    public class NRun : Node
    {
        public static NRun? Instance { get; set; }
        public GlobalUiState GlobalUi { get; set; } = null!;
        public NEventRoom? EventRoom { get; set; }
        public NRestSiteRoom? RestSiteRoom { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Events
{
    using Godot;
    using MegaCrit.Sts2.Core.Events;

    public class NEventLayout : Control
    {
        public List<NEventOptionButton> OptionButtons { get; } = new();
    }

    public class NEventOptionButton : Control
    {
        public EventOption Option { get; set; } = null!;
        public object Event { get; set; } = null!;
        public bool IsEnabled { get; set; } = true;
        public int Clicks { get; private set; }
        public bool ThrowClick { get; set; }
        public void ForceClick()
        {
            Clicks++;
            if (ThrowClick) throw new InvalidOperationException("click");
        }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.CommonUi
{
    using Godot;

    public class NProceedButton : Control
    {
        public bool IsEnabled { get; set; }
        public int Clicks { get; private set; }
        public void ForceClick() => Clicks++;
    }
}

namespace MegaCrit.Sts2.Core.Nodes.RestSite
{
    using Godot;
    using MegaCrit.Sts2.Core.Entities.Players;
    using MegaCrit.Sts2.Core.Entities.RestSite;

    public class NRestSiteCharacter : Control
    {
        public Player Player { get; set; } = null!;
    }

    public class NRestSiteButton : Control
    {
        public RestSiteOption Option { get; set; } = null!;
        public bool IsEnabled { get; set; } = true;
        public int Clicks { get; private set; }
        public bool ThrowClick { get; set; }
        public void ForceClick()
        {
            Clicks++;
            if (ThrowClick) throw new InvalidOperationException("click");
        }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Rooms
{
    using Godot;
    using MegaCrit.Sts2.Core.Entities.RestSite;
    using MegaCrit.Sts2.Core.Nodes.CommonUi;
    using MegaCrit.Sts2.Core.Nodes.Events;
    using MegaCrit.Sts2.Core.Nodes.RestSite;

    public class NEventRoom : Control
    {
        public static NEventRoom? Instance { get; set; }
        public NEventLayout Layout { get; set; } = null!;
        public object? CustomEventNode { get; set; }
        public object? EmbeddedCombatRoom { get; set; }
    }

    public class NRestSiteRoom : Control
    {
        private readonly Dictionary<RestSiteOption, NRestSiteButton> _buttons = new();
        public static NRestSiteRoom? Instance { get; set; }
        public List<NRestSiteCharacter> Characters { get; } = new();
        public NProceedButton ProceedButton { get; set; } = null!;
        public void AddOption(RestSiteOption option, NRestSiteButton button)
        {
            _buttons.Add(option, button);
            Children.Add(button);
        }
        public NRestSiteButton GetButtonForOption(RestSiteOption option) => _buttons[option];
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection
{
    using Godot;
    public class NSimpleCardSelectScreen : Control { }
    public class NDeckUpgradeSelectScreen : Control { }
}
