using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace Godot
{
    public enum Error {Ok,Failed}

    public class GodotObject
    {
        public bool InstanceValid { get; set; } = true;
        public static bool IsInstanceValid(GodotObject? value) => value is not null && FixtureTrace.Read(value,"valid",value.InstanceValid);
    }

    public class Node : GodotObject
    {
        public Node? FixtureParent {get;set;}
        public Node? GetParent()=>GeometryTrace.Read(this,"parent",FixtureParent);
        public readonly List<Node> Children=new();
        public List<Node> GetChildren()=>Children;
        public int GetChildCount(bool includeInternal=false)=>Children.Count;
        public Node GetChild(int index,bool includeInternal=false)=>Children[index];
        private readonly Dictionary<string, Node> _nodes = new(StringComparer.Ordinal);
        public bool Visible { get; set; } = true;
        public virtual bool IsVisibleInTree() => FixtureTrace.Read(this,"visible",Visible);
        public void Bind(string path, Node value) => _nodes[path] = value;
        public T? GetNodeOrNull<T>(string path) where T : Node =>
            _nodes.TryGetValue(path, out Node? value) ? value as T : null;
    }

    public class CanvasItem : Node
    {
        public Rid FixtureCanvas {get;set;}=new Rid(1);
        public Transform2D FixtureTransform {get;set;}=new(new Vector2(1,0),new Vector2(0,1),new Vector2(0,0));
        public bool FixtureTopLevel {get;set;}
        public Rid GetCanvas()=>GeometryTrace.Read(this,"canvas",FixtureCanvas);
        public Transform2D GetGlobalTransform()=>GeometryTrace.Read(this,"transform",FixtureTransform);
        public bool IsSetAsTopLevel()=>GeometryTrace.Read(this,"top_level",FixtureTopLevel);
    }
    public readonly record struct Rid(ulong Id) {public bool IsValid=>Id!=0;}
    public readonly record struct Rect2(Vector2 Position,Vector2 Size);
    public readonly record struct Transform2D(Vector2 X,Vector2 Y,Vector2 Origin);
    public class Control : CanvasItem
    {
        private Vector2 _size; public Vector2 Size { get=>GeometryTrace.Read(this,"size",_size); set=>_size=value; }
        private Vector2 _position; public Vector2 Position { get=>GeometryTrace.Read(this,"position",_position); set=>_position=value; }
        private bool _clipContents; public bool ClipContents {get=>GeometryTrace.Read(this,"clip",_clipContents);set=>_clipContents=value;}
        public Rect2 FixtureRect {get;set;}
        public Rect2 GetGlobalRect()=>GeometryTrace.Read(this,"rect",FixtureRect);
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
        public static Func<IReadOnlyList<MegaCrit.Sts2.Core.Models.CardModel>,MegaCrit.Sts2.Core.Models.EnchantmentModel,int,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>>>? EnchantHandler;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>> FromDeckForEnchantment(IReadOnlyList<MegaCrit.Sts2.Core.Models.CardModel> cards,MegaCrit.Sts2.Core.Models.EnchantmentModel enchantment,int amount,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs)
        { Calls++; return EnchantHandler!(cards,enchantment,amount,prefs); }
        public static object? Selector { get; set; }
        public static Func<MegaCrit.Sts2.Core.Entities.Players.Player,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,Func<MegaCrit.Sts2.Core.Models.CardModel,MegaCrit.Sts2.Core.Entities.Cards.CardTransformation>?,Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>>>? TransformHandler;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>> FromDeckForTransformation(MegaCrit.Sts2.Core.Entities.Players.Player player,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs,Func<MegaCrit.Sts2.Core.Models.CardModel,MegaCrit.Sts2.Core.Entities.Cards.CardTransformation>? factory=null){Calls++;return TransformHandler!(player,prefs,factory);}
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
    public class PotionModel { public ModelId Id {get;}=new(); }
    public class RelicModel { public ModelId Id {get;}=new(); }
    public class AbstractModel {}
    public class EnchantmentModel
    {
        public ModelId Id {get;}=new();
        public int Amount {get;set;}
        public CardModel? Card {get;set;}
        public EnchantmentModel CanonicalInstance => this;
        public Func<CardModel,bool>? Eligible;
        public bool CanEnchant(CardModel card)=>Eligible?.Invoke(card)??card.Enchantment is null;
    }
    public class CardModel
    {
        public EnchantmentModel? Enchantment {get;set;}
        public bool IsEnchantmentPreview {get;set;}
        public MegaCrit.Sts2.Core.Entities.Players.Player? Owner {get;set;}
        public MegaCrit.Sts2.Core.Runs.IRunState? RunOverride {get;set;}
        public MegaCrit.Sts2.Core.Runs.IRunState? RunState=>RunOverride??Owner?.RunState;
        public bool IsRemovable {get;set;}=true;
        public int Type {get;set;}
        public bool IsTransformable {get;set;}=true;
        public ModelId Id { get; } = new();
        private int _level; public int CurrentUpgradeLevel { get=>FixtureTrace.Read(this,"level",_level);set=>_level=value; }
        public bool IsUpgradable { get; set; }
    }
}

namespace MegaCrit.Sts2.Core.Entities.Players
{
    using MegaCrit.Sts2.Core.Models;
    public sealed class Deck : MegaCrit.Sts2.Core.Entities.Cards.CardPile {}
    public sealed class Player { public int MaxPotionCount {get;set;}=3; public List<PotionModel?> PotionSlots {get;}=new(){null,null,null}; public Deck Deck { get; } = new(); private MegaCrit.Sts2.Core.Runs.IRunState _run=new MegaCrit.Sts2.Core.Runs.FixtureRunState(); public bool ThrowRunState {get;set;} public MegaCrit.Sts2.Core.Runs.IRunState RunState {get=>ThrowRunState?throw new InvalidOperationException("fixture getter"):_run;set=>_run=value;} }
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
    public sealed class NProceedButton : Control { public bool IsEnabled { get; set; } public Action? Clicked; public void ForceClick() => Clicked?.Invoke(); }
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
        private bool _isClickable=true;
        public void SetClickable(bool value) => _isClickable=value;
        protected bool InputClickable => _isClickable;
        private NCard _cardNode=null!; public NCard CardNode {get=>FixtureTrace.Read(this,"card",_cardNode);set=>_cardNode=value;}
        public virtual CardModel CardModel=>CardNode.Model;
        public static class SignalName { public const string Pressed="Pressed"; }
        public Action? RewardPressed;
        public Godot.Error EmitSignal(string name,NCardHolder holder){if(name!=SignalName.Pressed||!ReferenceEquals(holder,this))return Godot.Error.Failed;RewardPressed?.Invoke();return Godot.Error.Ok;}

    }
    public class NPreviewCardHolder:NCardHolder { }
    public class NGridCardHolder : NCardHolder
    {
        private CardModel _cardModel=null!; public new CardModel CardModel { get=>FixtureTrace.Read(this,"model",_cardModel);set=>_cardModel=value; }
        private NClickableControl _hitbox=null!; public NClickableControl Hitbox { get=>FixtureTrace.Read(this,"hitbox",_hitbox);set=>_hitbox=value; }
        public Action? Selected { get; set; }
        public int FixtureGuiInputCalls {get;private set;}
        public Action? FixtureBeforeGuiInput {get;set;}
        public Action<Action>? FixtureGuiInputDispatch {get;set;}
        public void _GuiInput(InputEventAction _) {FixtureGuiInputCalls++;FixtureBeforeGuiInput?.Invoke();if(!InputClickable)return;if(FixtureGuiInputDispatch is null)Selected?.Invoke();else FixtureGuiInputDispatch(()=>Selected?.Invoke());}
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
    public sealed class NDeckEnchantSelectScreen : NCardGridSelectionScreen
    {
        private EnchantmentModel _enchantment=null!;
        private int _enchantmentAmount;
        private MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs _prefs;
        public void Setup(EnchantmentModel enchantment,int amount,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs)
        {_enchantment=enchantment;_enchantmentAmount=amount;_prefs=prefs;}
        public object[] ReadFixtureFields()=>new object[]{_enchantment,_enchantmentAmount,_prefs};
        public static Func<IReadOnlyList<CardModel>,EnchantmentModel,int,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,NDeckEnchantSelectScreen>? Factory;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NDeckEnchantSelectScreen ShowScreen(IReadOnlyList<CardModel> cards,EnchantmentModel enchantment,int amount,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs)=>Factory!(cards,enchantment,amount,prefs);
    }
    public class NEnchantPreview : Control
    {
        private Control _before=null!,_after=null!;
        public void Setup(Control before,Control after){_before=before;_after=after;}
        public object[] ReadFixtureFields()=>new object[]{_before,_after};
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
        private int _yOffset; public int YOffset { get=>GeometryTrace.Read(this,"y_offset",_yOffset); set=>_yOffset=value; }
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

namespace MegaCrit.Sts2.Core.Random {public class Rng {}}
namespace MegaCrit.Sts2.Core.Nodes.CommonUi {public enum CardPreviewStyle {None=0}}
namespace MegaCrit.Sts2.Core.Nodes.Cards {public class NTransformPreview:Godot.Control {}}
namespace MegaCrit.Sts2.Core.Entities.Cards
{
    using MegaCrit.Sts2.Core.Models;
    public enum PileType {Deck=6}
    public class CardPile
    {
        public List<CardModel> Cards {get;}=new();
        public PileType Type=>PileType.Deck;
        public Action<CardModel>? CardAdded;public Action? ContentsChanged;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public void AddInternal(CardModel card,int index,bool silent)
        {if(Cards.Contains(card))throw new InvalidOperationException("duplicate");if(index<0)Cards.Add(card);else Cards.Insert(index,card);if(!silent){CardAdded?.Invoke(card);ContentsChanged?.Invoke();}}
    }
    public struct CardPileAddResult {public bool success;public CardModel cardAdded;public List<AbstractModel>? modifyingModels;}
    public readonly struct CardTransformation
    {
        public CardTransformation(CardModel original):this(original,null){}
        public CardTransformation(CardModel original,CardModel? replacement){Original=original;Replacement=replacement;}
        public CardModel Original {get;}
        public CardModel? Replacement {get;}
        public bool IsInCombat=>false;
        public static Func<CardModel,CardModel>? Generator;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public CardModel GetReplacement(MegaCrit.Sts2.Core.Random.Rng rng)=>Replacement??Generator!(Original);
    }
}
namespace MegaCrit.Sts2.Core.Hooks
{
    using MegaCrit.Sts2.Core.Models;
    public static class Hook
    {
        public static Func<MegaCrit.Sts2.Core.Runs.IRunState,CardModel,CardModel>? Modifier;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static CardModel ModifyCardBeingAddedToDeck(MegaCrit.Sts2.Core.Runs.IRunState run,CardModel card,ref List<AbstractModel>? models)=>Modifier?.Invoke(run,card)??card;
    }
}
namespace MegaCrit.Sts2.Core.Commands
{
    using MegaCrit.Sts2.Core.Entities.Cards;
    using MegaCrit.Sts2.Core.Models;
    public static class CardCmd
    {
        public static Func<IEnumerable<CardTransformation>,MegaCrit.Sts2.Core.Random.Rng,MegaCrit.Sts2.Core.Nodes.CommonUi.CardPreviewStyle,Task<IEnumerable<CardPileAddResult>>>? Handler;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static Task<IEnumerable<CardPileAddResult>> Transform(IEnumerable<CardTransformation> values,MegaCrit.Sts2.Core.Random.Rng rng,MegaCrit.Sts2.Core.Nodes.CommonUi.CardPreviewStyle style)=>Handler!(values,rng,style);
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection
{
    using MegaCrit.Sts2.Core.Models;
    using MegaCrit.Sts2.Core.Entities.Cards;
    public class NDeckTransformSelectScreen:NCardGridSelectionScreen
    {
        public static Func<IReadOnlyList<CardModel>,Func<CardModel,CardTransformation>,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs,NDeckTransformSelectScreen>? Factory;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NDeckTransformSelectScreen ShowScreen(IReadOnlyList<CardModel> cards,Func<CardModel,CardTransformation> factory,MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs)=>Factory!(cards,factory,prefs);
    }
}

namespace MegaCrit.Sts2.Core.Rewards
{
    using MegaCrit.Sts2.Core.Entities.Players;
    using MegaCrit.Sts2.Core.Models;
    public class LinkedRewardSet { }
    public class Reward
    {
        public Player Player {get;set;}=null!;
        public LinkedRewardSet? ParentRewardSet {get;set;}
        public int RewardsSetIndex {get;set;}
        public virtual bool IsPopulated {get;set;}=true;
        public bool SuccessfullySelected {get;set;}
    }
    public class CardReward:Reward {
        private List<MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult> _cards=new();
        public bool CanSkip {get;set;}=true;
        public override bool IsPopulated {get=>_cards.Count>0;set{}}
        public IEnumerable<CardModel> Cards=>System.Linq.Enumerable.Select(_cards,x=>x.Card);
        public void Setup(List<MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult> cards)=>_cards=cards;
    }
    public sealed class PotionReward:Reward { public PotionModel Potion {get;set;}=null!;public PotionModel? ClaimedPotion {get;set;} }
    public sealed class RelicReward:Reward { public RelicModel Relic {get;set;}=null!;public RelicModel? ClaimedRelic {get;set;} }
    public class RewardsSet
    {
        public Player Player {get;set;}=null!;
        public List<Reward> Rewards {get;set;}=new();
        public bool DisallowSkipping {get;set;}
        public static Func<RewardsSet,Task>? testSelector;
        public Func<Task> OfferHandler {get;set;}=()=>Task.CompletedTask;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public Task Offer()=>OfferHandler();
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens
{
    using Godot;
    using MegaCrit.Sts2.Core.Rewards;
    using MegaCrit.Sts2.Core.Runs;
    public class NRewardsScreen:Control
    {
        private MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton? _proceedButton;
        public void BindProceed(MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton button){_proceedButton=button;Bind("ProceedButton",button);}
        public bool ProceedBound=>_proceedButton is not null;
        public static Func<RewardsSet,bool,IRunState,NRewardsScreen>? Factory;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NRewardsScreen ShowScreen(RewardsSet set,bool terminal,IRunState run)=>Factory!(set,terminal,run);
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Rewards
{
    using Godot;
    using MegaCrit.Sts2.Core.Rewards;
    public class NRewardButton:Control
    {
        private Reward _reward=null!;
        public Reward Reward {get=>InstanceValid?_reward:throw new InvalidOperationException("retired reward button");set=>_reward=value;}
        public bool IsEnabled {get;set;}=true;
        public Func<Task> Handler {get;set;}=()=>Task.CompletedTask;
        public Action? DispatchOverride;
        public int ForceClickCalls;
        public Task? LastTask;
        public void ForceClick(){ForceClickCalls++;if(DispatchOverride is not null)DispatchOverride();else LastTask=GetReward();}
        public Task ForeignGetReward()=>GetReward();
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        private Task GetReward()=>Handler();
    }
}

namespace MegaCrit.Sts2.Core.Entities.Rewards { public enum PostAlternateCardRewardAction {None,Skip} }
namespace MegaCrit.Sts2.Core.Entities.CardRewardAlternatives {
    using MegaCrit.Sts2.Core.Entities.Rewards;
    public class CardRewardAlternative {
        public string OptionId {get;}
        public Func<Task> OnSelect {get;set;}
        public PostAlternateCardRewardAction AfterSelected {get;set;}
        public CardRewardAlternative(string id,PostAlternateCardRewardAction after){OptionId=id;AfterSelected=after;OnSelect=()=>Task.CompletedTask;}
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection {
    using Godot;
    using MegaCrit.Sts2.Core.Models;
    using MegaCrit.Sts2.Core.Entities.Cards;
    using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
    using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
    public class NCardRewardAlternativeButton:Control {public bool IsEnabled {get;set;}=true;public Action? Clicked;public void ForceClick()=>Clicked?.Invoke();}
    public class NCardRewardSelectionScreen:Control {
        private IReadOnlyList<CardCreationResult> _options=Array.Empty<CardCreationResult>();
        private IReadOnlyList<CardRewardAlternative> _extraOptions=Array.Empty<CardRewardAlternative>();
        private TaskCompletionSource<int?> _completionSource=new();
        public static Func<IReadOnlyList<CardCreationResult>,IReadOnlyList<CardRewardAlternative>,NCardRewardSelectionScreen>? Factory;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NCardRewardSelectionScreen ShowScreen(IReadOnlyList<CardCreationResult> options,IReadOnlyList<CardRewardAlternative> alternatives){var screen=Factory!(options,alternatives);screen._options=options;screen._extraOptions=alternatives;return screen;}
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public async Task<int?> OptionSelected(){_completionSource=new();return await _completionSource.Task;}
        public void Complete(int? slot)=>_completionSource.SetResult(slot);
        public bool HasOptions=>_options.Count>0||_extraOptions.Count>0;
        public NCardHolder? GetCardHolder(CardModel model)=>System.Linq.Enumerable.FirstOrDefault(System.Linq.Enumerable.OfType<NGridCardHolder>(GetNodeOrNull<Control>("UI/CardRow")!.Children),h=>ReferenceEquals(h.CardModel,model));
    }
}

// Geometry-only scripts do not alter the retained generic fixture trace.
internal static class GeometryTrace
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
}
