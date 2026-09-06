using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace Godot
{
    public class GodotObject
    {
        public bool InstanceValid { get; set; } = true;
        public static bool IsInstanceValid(GodotObject? value) => value?.InstanceValid == true;
    }

    public class Node : GodotObject
    {
        private readonly Dictionary<string, Node> _nodes = new(StringComparer.Ordinal);
        private readonly List<Node> _children = new();
        public bool Visible { get; set; } = true;
        public virtual bool IsVisibleInTree() => Visible;
        public void Bind(string path, Node value) => _nodes[path] = value;
        public Node GetNode(string path) => _nodes[path];
        public T? GetNodeOrNull<T>(string path) where T : Node =>
            _nodes.TryGetValue(path, out Node? value) ? value as T : null;
        public void AddChild(Node child) => _children.Add(child);
        public int GetChildCount(bool includeInternal) => _children.Count;
        public Node GetChild(int index, bool includeInternal) => _children[index];
    }

    public class CanvasItem : Node { }
    public class Control : CanvasItem
    {
        public Vector2 Size { get; set; }
        public Vector2 Position { get; set; }
    }

    public readonly struct Vector2 : IEquatable<Vector2>
    {
        public Vector2(float x, float y) { X = x; Y = y; }
        public float X { get; }
        public float Y { get; }
        public bool Equals(Vector2 other) => X.Equals(other.X) && Y.Equals(other.Y);
        public override bool Equals(object? value) => value is Vector2 other && Equals(other);
        public override int GetHashCode() => HashCode.Combine(X, Y);
        public static Vector2 operator *(Vector2 value, float scale) => new(value.X * scale, value.Y * scale);
        public static bool operator ==(Vector2 left, Vector2 right) => left.Equals(right);
        public static bool operator !=(Vector2 left, Vector2 right) => !left.Equals(right);
    }

    public readonly struct Variant
    {
        private readonly float _value;
        public Variant(float value) => _value = value;
        public float AsSingle() => _value;
    }

    public class ShaderMaterial : GodotObject
    {
        public float Width { get; set; }
        public Variant GetShaderParameter(string _) => new(Width);
    }

    public sealed class InputEventAction : IDisposable
    {
        public string Action { get; set; } = string.Empty;
        public bool Pressed { get; set; }
        public void Dispose() { }
    }
}

namespace MegaCrit.Sts2.Core.ControllerInput
{
    public static class MegaInput { public static readonly string select = "select"; }
}

namespace MegaCrit.Sts2.Core.Commands
{
    public static class CardSelectCmd { public static object? Selector { get; set; } }
}

namespace MegaCrit.Sts2.Core.Models
{
    using MegaCrit.Sts2.Core.Entities.Players;
    public sealed class ModelId { public string Entry { get; set; } = string.Empty; }
    public class EventModel
    {
        public Player? Owner { get; set; }
        public bool IsFinished { get; set; }
    }
    public class CardModel
    {
        public ModelId Id { get; } = new();
        public int CurrentUpgradeLevel { get; set; }
        public bool IsUpgradable { get; set; }
    }
    public class PotionModel { public ModelId Id { get; } = new(); }
    public class RelicModel { public ModelId Id { get; } = new(); }
}

namespace MegaCrit.Sts2.Core.Entities.Players
{
    using MegaCrit.Sts2.Core.Models;
    public sealed class Deck { public List<CardModel> Cards { get; } = new(); }
    public sealed class Player
    {
        public Deck Deck { get; } = new();
        public int MaxPotionCount { get; set; }
        public List<PotionModel?> PotionSlots { get; } = new();
    }
}

namespace MegaCrit.Sts2.Core.Entities.RestSite
{
    public class RestSiteOption { public string OptionId { get; set; } = string.Empty; }
    public sealed class SmithRestSiteOption : RestSiteOption { public int SmithCount { get; set; } }
}

namespace MegaCrit.Sts2.Core.Events
{
    using MegaCrit.Sts2.Core.Entities.Players;
    public sealed class EventOption
    {
        public string TextKey { get; set; } = string.Empty;
        public bool IsProceed { get; set; }
        public bool IsLocked { get; set; }
        public Func<Player, bool>? WillKillPlayer { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Models.Events
{
    using MegaCrit.Sts2.Core.Entities.Players;
    public sealed class RoomFullOfCheese : MegaCrit.Sts2.Core.Models.EventModel { }
    public sealed class AromaOfChaos : MegaCrit.Sts2.Core.Models.EventModel { }
    public sealed class SapphireSeed : MegaCrit.Sts2.Core.Models.EventModel { }
    public class Amalgamator : MegaCrit.Sts2.Core.Models.EventModel { }
    public class BattlewornDummy : MegaCrit.Sts2.Core.Models.EventModel { }
    public class BrainLeech : MegaCrit.Sts2.Core.Models.EventModel { }
    public class Bugslayer : MegaCrit.Sts2.Core.Models.EventModel { }
    public class ByrdonisNest : MegaCrit.Sts2.Core.Models.EventModel { }
    public class DoorsOfLightAndDark : MegaCrit.Sts2.Core.Models.EventModel { }
    public class EndlessConveyor : MegaCrit.Sts2.Core.Models.EventModel { }
    public class FieldOfManSizedHoles : MegaCrit.Sts2.Core.Models.EventModel { }
    public class GraveOfTheForgotten : MegaCrit.Sts2.Core.Models.EventModel { }
    public class InfestedAutomaton : MegaCrit.Sts2.Core.Models.EventModel { }
    public class LuminousChoir : MegaCrit.Sts2.Core.Models.EventModel { }
    public class MorphicGrove : MegaCrit.Sts2.Core.Models.EventModel { }
    public class Reflections : MegaCrit.Sts2.Core.Models.EventModel { }
    public class SelfHelpBook : MegaCrit.Sts2.Core.Models.EventModel { }
    public class SlipperyBridge : MegaCrit.Sts2.Core.Models.EventModel { }
    public class SpiralingWhirlpool : MegaCrit.Sts2.Core.Models.EventModel { }
    public class SpiritGrafter : MegaCrit.Sts2.Core.Models.EventModel { }
    public class StoneOfAllTime : MegaCrit.Sts2.Core.Models.EventModel { }
    public class Symbiote : MegaCrit.Sts2.Core.Models.EventModel { }
    public class TabletOfTruth : MegaCrit.Sts2.Core.Models.EventModel { }
    public class TheLegendsWereTrue : MegaCrit.Sts2.Core.Models.EventModel { }
    public class TinkerTime : MegaCrit.Sts2.Core.Models.EventModel { }
    public class TrashHeap : MegaCrit.Sts2.Core.Models.EventModel { }
    public class Trial : MegaCrit.Sts2.Core.Models.EventModel { }
    public class WarHistorianRepy : MegaCrit.Sts2.Core.Models.EventModel { }
    public class WaterloggedScriptorium : MegaCrit.Sts2.Core.Models.EventModel { }
    public class Wellspring : MegaCrit.Sts2.Core.Models.EventModel { }
    public class WhisperingHollow : MegaCrit.Sts2.Core.Models.EventModel { }
    public class WoodCarvings : MegaCrit.Sts2.Core.Models.EventModel { }
    public class ZenWeaver : MegaCrit.Sts2.Core.Models.EventModel { }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.Map
{
    using Godot;
    public sealed class NMapScreen : Control
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
    public sealed class NOverlayStack : Node
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
    public sealed class GlobalUiState : Node { public NMapScreen MapScreen { get; set; } = null!; public NOverlayStack Overlays { get; set; } = null!; }
    public sealed class NRun : Node
    {
        public static NRun? Instance { get; set; }
        public GlobalUiState GlobalUi { get; set; } = null!;
        public NEventRoom? EventRoom { get; set; }
        public NRestSiteRoom? RestSiteRoom { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.CommonUi
{
    using Godot;
    public class NClickableControl : Control { public bool IsEnabled { get; set; } = true; }
    public sealed class NProceedButton : Control { public bool IsEnabled { get; set; } public void ForceClick() { } }
    public class NConfirmButton : Control
    {
        public bool IsEnabled { get; set; } = true;
        public Action? Clicked { get; set; }
        public void ForceClick() => Clicked?.Invoke();
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Cards
{
    using Godot;
    public class NCardHighlight : GodotObject { public object? Material { get; set; } }
    public class NCard : Control
    {
        public static Vector2 defaultSize { get; set; } = new(200, 300);
        public NCardHighlight CardHighlight { get; set; } = null!;
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Cards.Holders
{
    using Godot;
    using MegaCrit.Sts2.Core.Models;
    using MegaCrit.Sts2.Core.Nodes.Cards;
    using MegaCrit.Sts2.Core.Nodes.CommonUi;
    public class NCardHolder : Control { public static float smallScale { get; set; } = 1f; }
    public class NGridCardHolder : NCardHolder
    {
        public CardModel CardModel { get; set; } = null!;
        public NCard CardNode { get; set; } = null!;
        public NClickableControl Hitbox { get; set; } = null!;
        public Action? Selected { get; set; }
        public void _GuiInput(InputEventAction _) => Selected?.Invoke();
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection
{
    using Godot;
    using MegaCrit.Sts2.Core.Models;
    using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
    public class NCardGridSelectionScreen : Control
    {
        public Task<IEnumerable<CardModel>> SelectionTask { get; set; } = null!;
        public int CardsSelectedCalls { get; private set; }
        public Task<IEnumerable<CardModel>> CardsSelected()
        {
            CardsSelectedCalls++;
            return SelectionTask;
        }
    }
    public sealed class NSimpleCardSelectScreen : NCardGridSelectionScreen { }
    public class NDeckUpgradeSelectScreen : NCardGridSelectionScreen { }
    public class NCardGrid : Control
    {
        public List<NGridCardHolder> CurrentlyDisplayedCardHolders { get; } = new();
        public bool IsAnimatingOut { get; set; }
        public int YOffset { get; set; }
    }
    public class NUpgradePreview : Control { public CardModel? Card { get; set; } }
}

namespace MegaCrit.Sts2.Core.Nodes.Events
{
    using Godot;
    using MegaCrit.Sts2.Core.Events;
    using MegaCrit.Sts2.Core.Models;
    public sealed class NEventLayout : Control
    {
        public List<NEventOptionButton> OptionButtons { get; } = new();
    }
    public sealed class NEventOptionButton : Control
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

namespace MegaCrit.Sts2.Core.Nodes.RestSite
{
    using Godot;
    using MegaCrit.Sts2.Core.Entities.RestSite;
    public sealed class NRestSiteButton : Control
    {
        public RestSiteOption Option { get; set; } = null!;
        public bool IsEnabled { get; set; } = true;
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Rooms
{
    using System.Collections.Generic;
    using Godot;
    using MegaCrit.Sts2.Core.Entities.RestSite;
    using MegaCrit.Sts2.Core.Nodes.CommonUi;
    using MegaCrit.Sts2.Core.Nodes.RestSite;
    public sealed class NEventRoom : Control
    {
        public static NEventRoom? Instance { get; set; }
        public MegaCrit.Sts2.Core.Nodes.Events.NEventLayout Layout { get; set; } = null!;
        public object? CustomEventNode { get; set; }
        public object? EmbeddedCombatRoom { get; set; }
    }
    public sealed class NRestSiteRoom : Control
    {
        private readonly Dictionary<RestSiteOption, NRestSiteButton> _buttons = new();
        public static NRestSiteRoom? Instance { get; set; }
        public NProceedButton ProceedButton { get; set; } = null!;
        public void AddOption(RestSiteOption option, NRestSiteButton button) => _buttons.Add(option, button);
        public NRestSiteButton GetButtonForOption(RestSiteOption option) => _buttons[option];
    }
}

namespace MegaCrit.Sts2.Core.Nodes.GodotExtensions { }

namespace MegaCrit.Sts2.addons.mega_text
{
    public sealed class MegaRichTextLabel : Godot.Control
    {
        public string Text { get; set; } = string.Empty;
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens
{
    public sealed class NRewardsScreen : Godot.Control { }
}
