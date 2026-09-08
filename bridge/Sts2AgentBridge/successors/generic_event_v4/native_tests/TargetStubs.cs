using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace Godot
{
    public class GodotObject
    {
        public bool InstanceValid { get; set; } = true;
        public static bool IsInstanceValid(GodotObject? value) => value is not null && FixtureTrace.Read(value,"valid",value.InstanceValid);
    }

    public class Node : GodotObject
    {
        public readonly List<Node> Children=new();
        public List<Node> GetChildren()=>Children;
        private readonly Dictionary<string, Node> _nodes = new(StringComparer.Ordinal);
        public bool Visible { get; set; } = true;
        public virtual bool IsVisibleInTree() => FixtureTrace.Read(this,"visible",Visible);
        public void Bind(string path, Node value) => _nodes[path] = value;
        public T? GetNodeOrNull<T>(string path) where T : Node =>
            _nodes.TryGetValue(path, out Node? value) ? value as T : null;
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
        public Variant GetShaderParameter(string _) => new(FixtureTrace.Read(this,"shader",Width));
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
    public static class CardSelectCmd {
        public static object? Selector { get; set; }
        public static int Calls;
        public static Func<MegaCrit.Sts2.Core.Entities.Players.Player,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>>>? Handler;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>> FromDeckForUpgrade(MegaCrit.Sts2.Core.Entities.Players.Player player,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs){Calls++;return Handler!(player,prefs);}
        public static Func<MegaCrit.Sts2.Core.Entities.Players.Player,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,Func<MegaCrit.Sts2.Core.Models.CardModel,bool>?,Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>>>? RemovalHandler;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>> FromDeckForRemoval(MegaCrit.Sts2.Core.Entities.Players.Player player,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs,Func<MegaCrit.Sts2.Core.Models.CardModel,bool>? filter=null) {Calls++;return RemovalHandler!(player,prefs,filter);}
        public static Func<MegaCrit.Sts2.Core.GameActions.Multiplayer.PlayerChoiceContext,List<MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult>,MegaCrit.Sts2.Core.Entities.Players.Player,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>>>? RewardHandler;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>> FromSimpleGridForRewards(MegaCrit.Sts2.Core.GameActions.Multiplayer.PlayerChoiceContext context,List<MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult> cards,MegaCrit.Sts2.Core.Entities.Players.Player player,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs){Calls++;return RewardHandler!(context,cards,player,prefs);}
    }
}

namespace MegaCrit.Sts2.Core.Models
{
    using MegaCrit.Sts2.Core.Entities.Players;
    public sealed class ModelId { private string _entry=string.Empty; public string Entry { get=>FixtureTrace.Read(this,"key",_entry); set=>_entry=value; } }
    public class EventModel
    {
        public Player? Owner { get; set; }
        public bool IsFinished { get; set; }
    }
    public class CardModel
    {
        public MegaCrit.Sts2.Core.Entities.Players.Player? Owner {get;set;}
        public MegaCrit.Sts2.Core.Runs.IRunState? RunOverride {get;set;}
        public MegaCrit.Sts2.Core.Runs.IRunState? RunState=>RunOverride??Owner?.RunState;
        public bool IsRemovable {get;set;}=true;
        public ModelId Id { get; } = new();
        private int _level; public int CurrentUpgradeLevel { get=>FixtureTrace.Read(this,"level",_level);set=>_level=value; }
        public bool IsUpgradable { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Entities.Players
{
    using MegaCrit.Sts2.Core.Models;
    public sealed class Deck { public List<CardModel> Cards { get; } = new(); }
    public sealed class Player { public Deck Deck { get; } = new(); private MegaCrit.Sts2.Core.Runs.IRunState _run=new MegaCrit.Sts2.Core.Runs.FixtureRunState(); public bool ThrowRunState {get;set;} public MegaCrit.Sts2.Core.Runs.IRunState RunState {get=>ThrowRunState?throw new InvalidOperationException("fixture getter"):_run;set=>_run=value;} }
}

namespace MegaCrit.Sts2.Core.Entities.RestSite
{
    public class RestSiteOption { public string OptionId { get; set; } = string.Empty; }
    public sealed class SmithRestSiteOption : RestSiteOption { public int SmithCount { get; set; } }
}

namespace MegaCrit.Sts2.Core.Events
{
    public sealed class EventOption {
        public string TextKey { get; set; } = string.Empty;
        public bool IsProceed {get;set;} public bool IsLocked {get;set;}
        public Func<MegaCrit.Sts2.Core.Entities.Players.Player,bool>? WillKillPlayer {get;set;}
        public Func<Task> Callback {get;set;}=()=>Task.CompletedTask;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public Task Chosen()=>Callback();
    }
}

namespace MegaCrit.Sts2.Core.Models.Events
{
    using MegaCrit.Sts2.Core.Entities.Players;
    public sealed class RoomFullOfCheese { public Player? Owner { get; set; } public bool IsFinished { get; set; } }
    public sealed class AromaOfChaos : MegaCrit.Sts2.Core.Models.EventModel { }
    public sealed class SapphireSeed : MegaCrit.Sts2.Core.Models.EventModel { }
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
    public sealed class GlobalUiState { public NMapScreen MapScreen { get; set; } = null!; public NOverlayStack Overlays { get; set; } = null!; }
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
    public class NClickableControl : Control { private bool _enabled=true; public bool IsEnabled { get=>FixtureTrace.Read(this,"enabled",_enabled);set=>_enabled=value; } }
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
    public class NCardHighlight : GodotObject { private object? _material; public object? Material { get=>FixtureTrace.Read(this,"material",_material);set=>_material=value; } }
    public class NCard : Control
    {
        public MegaCrit.Sts2.Core.Models.CardModel Model {get;set;}=null!;
        public static Vector2 defaultSize { get; set; } = new(200, 300);
        private NCardHighlight _highlight=null!; public NCardHighlight CardHighlight { get=>FixtureTrace.Read(this,"highlight",_highlight);set=>_highlight=value; }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Cards.Holders
{
    using Godot;
    using MegaCrit.Sts2.Core.Models;
    using MegaCrit.Sts2.Core.Nodes.Cards;
    using MegaCrit.Sts2.Core.Nodes.CommonUi;
    public class NCardHolder : Control { public static float smallScale { get; set; } = 1f;
        private NCard _cardNode=null!; public NCard CardNode {get=>FixtureTrace.Read(this,"card",_cardNode);set=>_cardNode=value;}
        public virtual CardModel CardModel=>CardNode.Model;
    }
    public class NPreviewCardHolder:NCardHolder { }
    public class NGridCardHolder : NCardHolder
    {
        private CardModel _cardModel=null!; public new CardModel CardModel { get=>FixtureTrace.Read(this,"model",_cardModel);set=>_cardModel=value; }
        private NClickableControl _hitbox=null!; public NClickableControl Hitbox { get=>FixtureTrace.Read(this,"hitbox",_hitbox);set=>_hitbox=value; }
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
    public class NDeckCardSelectScreen:NCardGridSelectionScreen {
        public static Func<IReadOnlyList<CardModel>,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,NDeckCardSelectScreen>? Factory;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NDeckCardSelectScreen Create(IReadOnlyList<CardModel> cards,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs)=>Factory!(cards,prefs);
    }
    public sealed class NSimpleCardSelectScreen : NCardGridSelectionScreen {
        public static Func<IReadOnlyList<MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult>,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,NSimpleCardSelectScreen>? Factory;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NSimpleCardSelectScreen Create(IReadOnlyList<MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult> cards,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs)=>Factory!(cards,prefs);
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NSimpleCardSelectScreen Create(IReadOnlyList<CardModel> cards,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs)=>new NSimpleCardSelectScreen();
    }
    public class NDeckUpgradeSelectScreen : NCardGridSelectionScreen {
        public Action<CardModel>? ClickHandler;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        protected virtual void OnCardClicked(CardModel card)=>ClickHandler!(card);
        public void DeliverClick(CardModel card)=>OnCardClicked(card);
        public static Func<IReadOnlyList<CardModel>,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,MegaCrit.Sts2.Core.Runs.IRunState,NDeckUpgradeSelectScreen>? Factory;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NDeckUpgradeSelectScreen ShowScreen(IReadOnlyList<CardModel> cards,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs,MegaCrit.Sts2.Core.Runs.IRunState run)=>Factory!(cards,prefs,run);
    }
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
    public sealed class NEventOptionButton : Control
    {
        private EventOption _option = null!;
        private object _event = null!;
        public EventOption Option { get => InstanceValid ? _option : throw new InvalidOperationException("Freed option getter"); set => _option=value; }
        public object Event { get => InstanceValid ? _event : throw new InvalidOperationException("Freed event getter"); set => _event=value; }
        public int ForceClickCalls { get; private set; }
        public bool IsEnabled {get;set;}=true;
        public Task? LastTask {get;private set;}
        public Action? DispatchOverride {get;set;}
        public void ForceClick() {ForceClickCalls++;if(DispatchOverride is not null)DispatchOverride();else LastTask=Option.Chosen();}
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
        public object? CustomEventNode { get; set; }
        public object? EmbeddedCombatRoom { get; set; }
        public MegaCrit.Sts2.Core.Nodes.Events.NEventLayout Layout {get;set;}=new();
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

namespace MegaCrit.Sts2.Core.Nodes.Events {
    public sealed class NEventLayout : Godot.Control {public List<NEventOptionButton> OptionButtons {get;}=new();}
}
namespace MegaCrit.Sts2.Core.CardSelection {
    public readonly record struct CardSelectorPrefs(int MinSelect,int MaxSelect,bool Cancelable=false,bool RequireManualConfirmation=false)
    {
        public Comparison<MegaCrit.Sts2.Core.Models.CardModel>? Comparison {get;init;}
        public bool UnpoweredPreviews {get;init;}
        public bool PretendCardsCanBePlayed {get;init;}
        public Func<MegaCrit.Sts2.Core.Models.CardModel,bool>? ShouldGlowGold {get;init;}
    }
}
namespace MegaCrit.Sts2.Core.Runs {
 public interface IRunState{} public sealed class FixtureRunState:IRunState{}
 public class RunState:IRunState {
  public Func<MegaCrit.Sts2.Core.Models.CardModel,MegaCrit.Sts2.Core.Models.CardModel>? CloneOverride;
  [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
  public MegaCrit.Sts2.Core.Models.CardModel CloneCard(MegaCrit.Sts2.Core.Models.CardModel card) { if(CloneOverride is not null)return CloneOverride(card);var clone=new MegaCrit.Sts2.Core.Models.CardModel {Owner=card.Owner,CurrentUpgradeLevel=card.CurrentUpgradeLevel};clone.Id.Entry=card.Id.Entry;return clone; }
 }
}
namespace MegaCrit.Sts2.addons.mega_text {public sealed class MegaRichTextLabel:Godot.Control{public string Text {get;set;}="";}}

namespace MegaCrit.Sts2.Core.GameActions.Multiplayer {public class PlayerChoiceContext { } public sealed class BlockingPlayerChoiceContext:PlayerChoiceContext { }}
namespace MegaCrit.Sts2.Core.Entities.Cards {
    public class CardCreationResult {
        public CardCreationResult(MegaCrit.Sts2.Core.Models.CardModel card){originalCard=card;}
        public readonly MegaCrit.Sts2.Core.Models.CardModel originalCard;
        public MegaCrit.Sts2.Core.Models.CardModel? ModifiedCard {get;set;}
        public MegaCrit.Sts2.Core.Models.CardModel Card=>ModifiedCard??originalCard;
    }
}

internal static class FixtureTrace
{
    internal static bool Enabled;
    internal static readonly List<string> Operations=new();
    internal static readonly Dictionary<object,string> Labels=new(System.Collections.Generic.ReferenceEqualityComparer.Instance);
    internal static readonly Dictionary<string,int> Counts=new();
    internal static readonly Dictionary<string,Func<int,object?,object?>> Scripts=new();
    internal static void Reset(){Enabled=false;Operations.Clear();Labels.Clear();Counts.Clear();Scripts.Clear();}
    internal static T Read<T>(object owner,string member,T value)
    {
        if(!Enabled)return value;
        string key=(Labels.TryGetValue(owner,out string? label)?label:owner.GetType().Name)+"."+member;
        Operations.Add(key);Counts.TryGetValue(key,out int count);Counts[key]=++count;
        return Scripts.TryGetValue(key,out var script)?(T)script(count,value)!:value;
    }
    internal static void Record(string name){if(Enabled)Operations.Add(name);}
}
