// Inert API fixtures. The actual adapter is compiled here; no game assemblies execute.
#pragma warning disable CS0414, CS0649
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
namespace Godot
{
    public class GodotObject : IDisposable { public bool Valid = true; public static bool IsInstanceValid(GodotObject o) => o.Valid; public void Dispose() { } }
    public class Node : GodotObject
    {
        public Dictionary<string, Node> Nodes = new(); public bool Visible = true;
        public T? GetNodeOrNull<T>(string name) where T : Node => Nodes.GetValueOrDefault(name) as T;
        public bool IsVisibleInTree() => Visible;
    }
    public class Control : Node { }
    public class InputEventAction : GodotObject { public string Action = ""; public bool Pressed; }
}
namespace MegaCrit.Sts2.Core.CardSelection
{
    public struct CardSelectorPrefs { public int MinSelect, MaxSelect; public bool RequireManualConfirmation, Cancelable; }
}
namespace MegaCrit.Sts2.Core.ControllerInput { public static class MegaInput { public static string select = "select"; } }
namespace MegaCrit.Sts2.Core.Commands { public static class CardSelectCmd { public static object? Selector; } }
namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum PileType { None, Draw, Hand, Discard, Exhaust, Play, Deck }
    public class CardPile { public PileType Type; public List<MegaCrit.Sts2.Core.Models.CardModel> Cards = new(); }
    public static class PileTypeExtensions { public static CardPile GetPile(this PileType type, MegaCrit.Sts2.Core.Entities.Players.Player p) => p.Piles[type]; }
}
namespace MegaCrit.Sts2.Core.Entities.Players
{
    public class Player { public object? PlayerCombatState = new(); public Dictionary<MegaCrit.Sts2.Core.Entities.Cards.PileType, MegaCrit.Sts2.Core.Entities.Cards.CardPile> Piles = new(); }
}
namespace MegaCrit.Sts2.Core.Models
{
    public class ModelId { public string Entry = "STRIKE"; }
    public class CardModel { public ModelId Id = new(); public int CurrentUpgradeLevel; public MegaCrit.Sts2.Core.Entities.Players.Player Owner = null!; }
}
namespace MegaCrit.Sts2.Core.Combat
{
    public class CombatState { public List<MegaCrit.Sts2.Core.Entities.Players.Player> Players = new(); }
    public class CombatManager { public static CombatManager? Instance; public bool IsInProgress = true, IsOverOrEnding; public CombatState State = new(); public CombatState DebugOnlyGetState() => State; }
}
namespace MegaCrit.Sts2.Core.Nodes
{
    public class NRun : Godot.Control { public static NRun? Instance; public GlobalUi GlobalUi = new(); }
    public class GlobalUi { public MegaCrit.Sts2.Core.Nodes.Screens.Overlays.NOverlayStack Overlays = new(); public MapScreen MapScreen = new(); }
    public class MapScreen : Godot.Control { public bool IsOpen, IsTraveling; }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.Overlays
{
    public class NOverlayStack : Godot.Control { public static NOverlayStack? Instance; public object? Top; public int ScreenCount => Top is null ? 0 : 1; public object? Peek() => Top; }
}
namespace MegaCrit.Sts2.Core.Nodes.Cards
{
    public class NCard : Godot.Control { public MegaCrit.Sts2.Core.Models.CardModel Model = null!; }
    public class NCardGrid : Godot.Control
    {
        public bool IsAnimatingOut;
        public List<MegaCrit.Sts2.Core.Nodes.Cards.Holders.NGridCardHolder> CurrentlyDisplayedCardHolders = new();
        public IEnumerable<MegaCrit.Sts2.Core.Models.CardModel> CurrentlyDisplayedCards => CurrentlyDisplayedCardHolders.Select(h => h.CardModel);
    }
}
namespace MegaCrit.Sts2.Core.Nodes.CommonUi
{
    public class NConfirmButton : Godot.Control { public bool IsEnabled = true; public Action Click = () => { }; public int Calls; public void ForceClick() { Calls++; Click(); } }
}
namespace MegaCrit.Sts2.Core.Nodes.Cards.Holders
{
    public class Hitbox : Godot.Control { public bool IsEnabled = true; }
    public class NCardHolder : Godot.Control
    {
        private bool _isClickable = true;
        public void SetClickable(bool value) => _isClickable = value;
    }
    public class NGridCardHolder : NCardHolder
    {
        public MegaCrit.Sts2.Core.Models.CardModel CardModel = null!;
        public MegaCrit.Sts2.Core.Nodes.Cards.NCard? CardNode;
        public Hitbox Hitbox = new(); public Action Click = () => { }; public int Calls;
        public void _GuiInput(Godot.InputEventAction input) { if (input.Action != "select" || !input.Pressed) throw new Exception(); Calls++; Click(); }
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection
{
    using MegaCrit.Sts2.Core.CardSelection;
    using MegaCrit.Sts2.Core.Entities.Cards;
    using MegaCrit.Sts2.Core.Models;
    public class NCardGridSelectionScreen : Godot.Control
    {
        protected readonly TaskCompletionSource<IEnumerable<CardModel>> _completionSource = new();
        public void Result(IEnumerable<CardModel> result) => _completionSource.SetResult(result);
        public void Cancel() => _completionSource.SetCanceled();
    }
    public class NCombatPileCardSelectScreen : NCardGridSelectionScreen
    {
        private CardPile _pile = null!; private CardSelectorPrefs _prefs; private object _filter = new();
        private HashSet<CardModel> _selectedCards = new();
        public HashSet<CardModel> Selected => _selectedCards;
        public void Init(CardPile pile, CardSelectorPrefs prefs) { _pile = pile; _prefs = prefs; }
    }
}
