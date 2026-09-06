using System;
using System.Collections.Generic;

namespace DiagnosticStubs
{
    internal static class AccessLog
    {
        internal static readonly List<string> Entries = new();
        internal static void Add(string value) => Entries.Add(value);
        internal static void Clear() => Entries.Clear();
    }
}

namespace Godot
{
    public class GodotObject
    {
        public string Tag { get; set; } = "object";
        public bool Valid { get; set; } = true;
        public static bool IsInstanceValid(GodotObject? value)
        {
            DiagnosticStubs.AccessLog.Add("valid:" + (value?.Tag ?? "null"));
            return value is not null && value.Valid;
        }
    }

    public class Node : GodotObject { }

    public class Label : Node
    {
        public string? TextValue { get; set; } = "1";
        public string? Text
        {
            get { DiagnosticStubs.AccessLog.Add(Tag + ".Text"); return TextValue; }
        }
    }

    public readonly struct StringName
    {
        private readonly string _value;
        public StringName(string value) { _value = value; }
        public static implicit operator StringName(string value) => new(value);
        public override string ToString() => _value;
    }

    public sealed class InputEventAction : IDisposable
    {
        public StringName Action { get; set; }
        public bool Pressed { get; set; }
        public void Dispose() { }
    }
}

namespace MegaCrit.Sts2.Core.ControllerInput
{
    public static class MegaInput
    {
        public static readonly Godot.StringName select = "select";
    }
}

namespace MegaCrit.Sts2.Core.Models
{
    public sealed class ModelId
    {
        public string EntryValue { get; set; } = "KEY";
        public string Entry
        {
            get { DiagnosticStubs.AccessLog.Add("model.Id.Entry"); return EntryValue; }
        }
    }

    public class CardModel
    {
        public ModelId IdValue { get; } = new();
        public ModelId Id
        {
            get { DiagnosticStubs.AccessLog.Add("card.Id"); return IdValue; }
        }
    }

    public class RelicModel
    {
        public ModelId IdValue { get; } = new();
        public ModelId Id
        {
            get { DiagnosticStubs.AccessLog.Add("relic.Id"); return IdValue; }
        }
    }

    public class PotionModel
    {
        public ModelId IdValue { get; } = new();
        public ModelId Id
        {
            get { DiagnosticStubs.AccessLog.Add("potion.Id"); return IdValue; }
        }
    }
}

namespace MegaCrit.Sts2.Core.Entities.Players
{
    public sealed class PlayerDeck
    {
        public IList<MegaCrit.Sts2.Core.Models.CardModel?> CardsValue { get; set; } =
            new List<MegaCrit.Sts2.Core.Models.CardModel?>();
        public IList<MegaCrit.Sts2.Core.Models.CardModel?> Cards
        {
            get { DiagnosticStubs.AccessLog.Add("player.Deck.Cards"); return CardsValue; }
        }
    }

    public sealed class PlayerRunState
    {
        public object? CurrentRoomValue { get; set; }
        public object? CurrentRoom
        {
            get { DiagnosticStubs.AccessLog.Add("player.RunState.CurrentRoom"); return CurrentRoomValue; }
        }
    }

    public sealed class Player
    {
        public PlayerDeck DeckValue { get; } = new();
        public PlayerRunState RunStateValue { get; } = new();
        public int GoldValue { get; set; } = 100;
        public PlayerDeck Deck
        {
            get { DiagnosticStubs.AccessLog.Add("player.Deck"); return DeckValue; }
        }
        public PlayerRunState RunState
        {
            get { DiagnosticStubs.AccessLog.Add("player.RunState"); return RunStateValue; }
        }
        public int Gold
        {
            get { DiagnosticStubs.AccessLog.Add("player.Gold"); return GoldValue; }
        }
    }
}

namespace MegaCrit.Sts2.Core.Entities.Merchant
{
    public enum PurchaseStatus { Success = 1, Failure = 2 }

    public sealed class MerchantInventory
    {
        public MegaCrit.Sts2.Core.Entities.Players.Player? PlayerValue { get; set; }
        public MegaCrit.Sts2.Core.Entities.Players.Player? Player
        {
            get { DiagnosticStubs.AccessLog.Add("inventoryModel.Player"); return PlayerValue; }
        }
    }

    public class MerchantEntry { }

    public sealed class CardCreationResult
    {
        public MegaCrit.Sts2.Core.Models.CardModel? CardValue { get; set; }
        public MegaCrit.Sts2.Core.Models.CardModel? Card
        {
            get { DiagnosticStubs.AccessLog.Add("creation.Card"); return CardValue; }
        }
    }

    public sealed class MerchantCardEntry : MerchantEntry
    {
        public bool IsStockedValue { get; set; } = true;
        public CardCreationResult? CreationResultValue { get; set; }
        public bool IsStocked
        {
            get { DiagnosticStubs.AccessLog.Add("cardEntry.IsStocked"); return IsStockedValue; }
        }
        public CardCreationResult? CreationResult
        {
            get { DiagnosticStubs.AccessLog.Add("cardEntry.CreationResult"); return CreationResultValue; }
        }
        public event Action<PurchaseStatus, MerchantEntry>? PurchaseCompleted;
        public void Complete(PurchaseStatus status) => PurchaseCompleted?.Invoke(status, this);
    }

    public sealed class MerchantRelicEntry : MerchantEntry
    {
        public bool IsStockedValue { get; set; } = true;
        public MegaCrit.Sts2.Core.Models.RelicModel? ModelValue { get; set; }
        public bool IsStocked
        {
            get { DiagnosticStubs.AccessLog.Add("relicEntry.IsStocked"); return IsStockedValue; }
        }
        public MegaCrit.Sts2.Core.Models.RelicModel? Model
        {
            get { DiagnosticStubs.AccessLog.Add("relicEntry.Model"); return ModelValue; }
        }
    }

    public sealed class MerchantPotionEntry : MerchantEntry
    {
        public bool IsStockedValue { get; set; } = true;
        public MegaCrit.Sts2.Core.Models.PotionModel? ModelValue { get; set; }
        public bool IsStocked
        {
            get { DiagnosticStubs.AccessLog.Add("potionEntry.IsStocked"); return IsStockedValue; }
        }
        public MegaCrit.Sts2.Core.Models.PotionModel? Model
        {
            get { DiagnosticStubs.AccessLog.Add("potionEntry.Model"); return ModelValue; }
        }
    }

    public sealed class MerchantCardRemovalEntry : MerchantEntry
    {
        public bool IsStockedValue { get; set; } = true;
        public bool IsStocked
        {
            get { DiagnosticStubs.AccessLog.Add("removalEntry.IsStocked"); return IsStockedValue; }
        }
    }
}

namespace MegaCrit.Sts2.Core.Rooms
{
    public sealed class MerchantRoom
    {
        public MegaCrit.Sts2.Core.Entities.Merchant.MerchantInventory? LocalInventoryValue { get; set; }
        public MegaCrit.Sts2.Core.Entities.Merchant.MerchantInventory? GetLocalInventory()
        {
            DiagnosticStubs.AccessLog.Add("roomModel.GetLocalInventory");
            return LocalInventoryValue;
        }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.GodotExtensions
{
    public class NClickableControl : Godot.GodotObject
    {
        public bool VisibleValue { get; set; } = true;
        public bool EnabledValue { get; set; } = true;
        public bool IsVisibleInTree()
        {
            DiagnosticStubs.AccessLog.Add(Tag + ".IsVisibleInTree");
            return VisibleValue;
        }
        public bool IsEnabled
        {
            get { DiagnosticStubs.AccessLog.Add(Tag + ".IsEnabled"); return EnabledValue; }
        }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.CommonUi
{
    public class NBackButton : MegaCrit.Sts2.Core.Nodes.GodotExtensions.NClickableControl
    {
        public void ForceClick() { DiagnosticStubs.AccessLog.Add("ACTION:back"); }
    }
    public class NProceedButton : MegaCrit.Sts2.Core.Nodes.GodotExtensions.NClickableControl
    {
        public void ForceClick() { DiagnosticStubs.AccessLog.Add("ACTION:proceed"); }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.Map
{
    public sealed class NMapScreen : Godot.GodotObject
    {
        private static NMapScreen? _instance;
        public static NMapScreen? Instance
        {
            get { DiagnosticStubs.AccessLog.Add("NMapScreen.Instance"); return _instance; }
            set { _instance = value; }
        }
        public bool IsOpenValue { get; set; }
        public bool IsTravelEnabledValue { get; set; }
        public bool IsTravelingValue { get; set; }
        public bool IsOpen { get { DiagnosticStubs.AccessLog.Add("map.IsOpen"); return IsOpenValue; } }
        public bool IsTravelEnabled { get { DiagnosticStubs.AccessLog.Add("map.IsTravelEnabled"); return IsTravelEnabledValue; } }
        public bool IsTraveling { get { DiagnosticStubs.AccessLog.Add("map.IsTraveling"); return IsTravelingValue; } }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.Overlays
{
    public sealed class NOverlayStack : Godot.GodotObject
    {
        public int ScreenCountValue { get; set; }
        public int ScreenCount
        {
            get { DiagnosticStubs.AccessLog.Add("overlays.ScreenCount"); return ScreenCountValue; }
        }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Screens.Shops
{
    using MegaCrit.Sts2.Core.Entities.Merchant;
    using MegaCrit.Sts2.Core.Nodes.CommonUi;
    using MegaCrit.Sts2.Core.Nodes.GodotExtensions;

    public class NMerchantSlot : Godot.Node
    {
        public NClickableControl? HitboxValue { get; set; }
        public MerchantEntry? EntryValue { get; set; }
        public Godot.Node? CostLabelValue { get; set; }
        public bool VisibleValue { get; set; } = true;
        public NClickableControl? Hitbox { get { DiagnosticStubs.AccessLog.Add(Tag + ".Hitbox"); return HitboxValue; } }
        public MerchantEntry? Entry { get { DiagnosticStubs.AccessLog.Add(Tag + ".Entry"); return EntryValue; } }
        public bool IsVisibleInTree() { DiagnosticStubs.AccessLog.Add(Tag + ".IsVisibleInTree"); return VisibleValue; }
        public Godot.Node? GetNodeOrNull(string path) { DiagnosticStubs.AccessLog.Add(Tag + ".GetNodeOrNull:" + path); return CostLabelValue; }
    }

    public sealed class NMerchantCard : NMerchantSlot
    {
        public void _GuiInput(Godot.InputEventAction input) { DiagnosticStubs.AccessLog.Add("ACTION:card"); }
    }

    public sealed class NMerchantInventory : Godot.GodotObject
    {
        public bool IsOpenValue { get; set; } = true;
        public bool VisibleValue { get; set; } = true;
        public MerchantInventory? InventoryValue { get; set; }
        public NBackButton? BackValue { get; set; }
        public IReadOnlyList<NMerchantSlot?> SlotsValue { get; set; } = Array.Empty<NMerchantSlot?>();
        public bool IsOpen { get { DiagnosticStubs.AccessLog.Add("inventoryNode.IsOpen"); return IsOpenValue; } }
        public MerchantInventory? Inventory { get { DiagnosticStubs.AccessLog.Add("inventoryNode.Inventory"); return InventoryValue; } }
        public bool IsVisibleInTree() { DiagnosticStubs.AccessLog.Add("inventoryNode.IsVisibleInTree"); return VisibleValue; }
        public T? GetNodeOrNull<T>(string path) where T : Godot.GodotObject
        {
            DiagnosticStubs.AccessLog.Add("inventoryNode.GetNodeOrNull:" + path);
            return BackValue as T;
        }
        public IEnumerable<NMerchantSlot?> GetAllSlots()
        {
            DiagnosticStubs.AccessLog.Add("inventoryNode.GetAllSlots");
            return SlotsValue;
        }
    }

    public sealed class NMerchantButton : NClickableControl { }
}

namespace MegaCrit.Sts2.Core.Nodes
{
    public sealed class GlobalUiNode : Godot.GodotObject
    {
        public MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen? MapScreenValue { get; set; }
        public MegaCrit.Sts2.Core.Nodes.Screens.Overlays.NOverlayStack? OverlaysValue { get; set; }
        public MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen? MapScreen
        {
            get { DiagnosticStubs.AccessLog.Add("globalUi.MapScreen"); return MapScreenValue; }
        }
        public MegaCrit.Sts2.Core.Nodes.Screens.Overlays.NOverlayStack? Overlays
        {
            get { DiagnosticStubs.AccessLog.Add("globalUi.Overlays"); return OverlaysValue; }
        }
    }

    public sealed class NRun : Godot.GodotObject
    {
        private static NRun? _instance;
        public static NRun? Instance
        {
            get { DiagnosticStubs.AccessLog.Add("NRun.Instance"); return _instance; }
            set { _instance = value; }
        }
        public GlobalUiNode? GlobalUiValue { get; set; }
        public GlobalUiNode? GlobalUi
        {
            get { DiagnosticStubs.AccessLog.Add("run.GlobalUi"); return GlobalUiValue; }
        }
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Rooms
{
    public sealed class NMerchantRoom : Godot.GodotObject
    {
        private static NMerchantRoom? _instance;
        public static NMerchantRoom? Instance
        {
            get { DiagnosticStubs.AccessLog.Add("NMerchantRoom.Instance"); return _instance; }
            set { _instance = value; }
        }
        public MegaCrit.Sts2.Core.Nodes.Screens.Shops.NMerchantInventory? InventoryValue { get; set; }
        public MegaCrit.Sts2.Core.Rooms.MerchantRoom? RoomValue { get; set; }
        public MegaCrit.Sts2.Core.Nodes.Screens.Shops.NMerchantButton? MerchantButtonValue { get; set; }
        public MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton? ProceedButtonValue { get; set; }
        public bool VisibleValue { get; set; } = true;
        public MegaCrit.Sts2.Core.Nodes.Screens.Shops.NMerchantInventory? Inventory
        {
            get { DiagnosticStubs.AccessLog.Add("room.Inventory"); return InventoryValue; }
        }
        public MegaCrit.Sts2.Core.Rooms.MerchantRoom? Room
        {
            get { DiagnosticStubs.AccessLog.Add("room.Room"); return RoomValue; }
        }
        public MegaCrit.Sts2.Core.Nodes.Screens.Shops.NMerchantButton? MerchantButton
        {
            get { DiagnosticStubs.AccessLog.Add("room.MerchantButton"); return MerchantButtonValue; }
        }
        public MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton? ProceedButton
        {
            get { DiagnosticStubs.AccessLog.Add("room.ProceedButton"); return ProceedButtonValue; }
        }
        public bool IsVisibleInTree() { DiagnosticStubs.AccessLog.Add("room.IsVisibleInTree"); return VisibleValue; }
    }
}
