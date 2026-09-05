using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

public static class ShopV1Constants
{
    public const string Version = "shop_v1";
    public const string FlowKind = "shop";
    public const int MaximumOffers = RoomFlowLimits.MaximumShopOffers;
    public const int MaximumDeckCards = RoomFlowLimits.MaximumDeckCards;
    public const int MaximumPendingReads = RoomFlowLimits.MaximumPendingReads;
    public const int MaximumReservations = 3;
    public const int MaximumActionLength = 32;
}

public sealed class ShopV1Player
{
    public ShopV1Player(int gold, int deckCount)
    {
        Gold = gold;
        DeckCount = deckCount;
    }

    public int Gold { get; }
    public int DeckCount { get; }
}

public sealed class ShopV1Offer
{
    public ShopV1Offer(
        int slot,
        string kind,
        string key,
        int displayedPrice,
        bool affordable,
        bool enabled,
        bool supported)
    {
        Slot = slot;
        Kind = kind;
        Key = key;
        DisplayedPrice = displayedPrice;
        Affordable = affordable;
        Enabled = enabled;
        Supported = supported;
    }

    public int Slot { get; }
    public string Kind { get; }
    public string Key { get; }
    public int DisplayedPrice { get; }
    public bool Affordable { get; }
    public bool Enabled { get; }
    public bool Supported { get; }
}

public sealed class ShopV1ReconciledAction
{
    internal ShopV1ReconciledAction(
        string sessionNonce,
        string decisionId,
        string actionId,
        string kind)
    {
        FlowKind = ShopV1Constants.FlowKind;
        SessionNonce = sessionNonce;
        ParentOrdinal = RoomFlowLimits.ParentOrdinal;
        DecisionId = decisionId;
        ActionId = actionId;
        Kind = kind;
        Result = "reconciled";
    }

    public string FlowKind { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Kind { get; }
    public string Result { get; }
}

public sealed class ShopV1Observation : IRoomFlowReadValue
{
    private readonly ReadOnlyCollection<ShopV1Offer> _offers;
    private readonly ReadOnlyCollection<string> _legalActions;
    private readonly ReadOnlyCollection<ShopV1ReconciledAction> _priorResults;

    internal ShopV1Observation(
        string sessionNonce,
        string status,
        string phase,
        string decisionId,
        ShopV1Player player,
        IReadOnlyList<ShopV1Offer> offers,
        IReadOnlyList<string> legalActions,
        ShopV1ReconciledAction? priorResult)
    {
        Version = ShopV1Constants.Version;
        FlowKind = ShopV1Constants.FlowKind;
        SessionNonce = sessionNonce;
        ParentOrdinal = RoomFlowLimits.ParentOrdinal;
        Status = status;
        Phase = phase;
        DecisionId = decisionId;
        Player = new ShopV1Player(player.Gold, player.DeckCount);
        _offers = Copy(offers);
        _legalActions = Copy(legalActions);
        _priorResults = priorResult is null
            ? Array.AsReadOnly(Array.Empty<ShopV1ReconciledAction>())
            : Array.AsReadOnly(new[] { priorResult });
    }

    public string Version { get; }
    public string FlowKind { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string Status { get; }
    public string Phase { get; }
    public string DecisionId { get; }
    public ShopV1Player Player { get; }
    public IReadOnlyList<ShopV1Offer> Offers => _offers;
    public IReadOnlyList<string> LegalActions => _legalActions;
    public IReadOnlyList<ShopV1ReconciledAction> PriorResults => _priorResults;

    internal static ShopV1Observation Fixed(
        string nonce,
        string status,
        string phase,
        ShopV1ReconciledAction? priorResult = null) =>
        new(nonce, status, phase, string.Empty, new ShopV1Player(0, 0),
            Array.Empty<ShopV1Offer>(), Array.Empty<string>(), priorResult);

    private static ReadOnlyCollection<T> Copy<T>(IReadOnlyList<T> source)
    {
        var copy = new T[source.Count];
        for (int index = 0; index < source.Count; index++)
        {
            copy[index] = source[index];
        }
        return Array.AsReadOnly(copy);
    }
}

public enum ShopV1SurfaceStatus
{
    Missing = 1,
    Available = 2,
    Unsupported = 3,
}

public enum ShopV1OfferKind
{
    Card = 1,
    Relic = 2,
    Potion = 3,
    Removal = 4,
    Unknown = 5,
}

public enum ShopV1Completion
{
    Pending = 1,
    Succeeded = 2,
    Failed = 3,
    Invalid = 4,
}

public enum ShopV1ActionKind
{
    PurchaseCard = 1,
    CloseInventory = 2,
    Leave = 3,
}

public interface IShopV1NativeDispatch : IDisposable
{
    ShopV1Completion Completion { get; }
    void Invoke();
}

public sealed class ShopV1DeckCardBinding
{
    public ShopV1DeckCardBinding(object modelIdentity, string stableKey)
    {
        ModelIdentity = modelIdentity;
        StableKey = stableKey;
    }

    public object ModelIdentity { get; }
    public string StableKey { get; }
}

public sealed class ShopV1NativeControl
{
    public ShopV1NativeControl(
        object identity,
        bool visible,
        bool enabled,
        Action? dispatch)
    {
        Identity = identity;
        Visible = visible;
        Enabled = enabled;
        Dispatch = dispatch;
    }

    public object Identity { get; }
    public bool Visible { get; }
    public bool Enabled { get; }
    public Action? Dispatch { get; }
}

public sealed class ShopV1NativeOffer
{
    public ShopV1NativeOffer(
        int slot,
        ShopV1OfferKind kind,
        string stableKey,
        int displayedPrice,
        bool stocked,
        bool visible,
        bool enabled,
        object slotIdentity,
        object entryIdentity,
        object? offeredModelIdentity,
        object controlIdentity,
        object labelIdentity,
        IShopV1NativeDispatch? purchaseDispatch)
    {
        Slot = slot;
        Kind = kind;
        StableKey = stableKey;
        DisplayedPrice = displayedPrice;
        Stocked = stocked;
        Visible = visible;
        Enabled = enabled;
        SlotIdentity = slotIdentity;
        EntryIdentity = entryIdentity;
        OfferedModelIdentity = offeredModelIdentity;
        ControlIdentity = controlIdentity;
        LabelIdentity = labelIdentity;
        PurchaseDispatch = purchaseDispatch;
    }

    public int Slot { get; }
    public ShopV1OfferKind Kind { get; }
    public string StableKey { get; }
    public int DisplayedPrice { get; }
    public bool Stocked { get; }
    public bool Visible { get; }
    public bool Enabled { get; }
    public object SlotIdentity { get; }
    public object EntryIdentity { get; }
    public object? OfferedModelIdentity { get; }
    public object ControlIdentity { get; }
    public object LabelIdentity { get; }
    public IShopV1NativeDispatch? PurchaseDispatch { get; }
}

public sealed class ShopV1SurfaceCapture
{
    private readonly ReadOnlyCollection<ShopV1DeckCardBinding> _deck;
    private readonly ReadOnlyCollection<ShopV1NativeOffer> _offers;

    public ShopV1SurfaceCapture(
        ShopV1SurfaceStatus status,
        object? runIdentity,
        object? roomIdentity,
        object? inventoryNodeIdentity,
        object? inventoryModelIdentity,
        object? playerIdentity,
        object? mapIdentity,
        bool roomVisible,
        bool inventoryVisible,
        bool inventoryOpen,
        bool foregroundBlocked,
        bool mapOpen,
        bool mapTravelEnabled,
        bool mapTraveling,
        int gold,
        IReadOnlyList<ShopV1DeckCardBinding> deck,
        IReadOnlyList<ShopV1NativeOffer> offers,
        ShopV1NativeControl? backControl,
        ShopV1NativeControl? merchantControl,
        ShopV1NativeControl? proceedControl)
    {
        Status = status;
        RunIdentity = runIdentity;
        RoomIdentity = roomIdentity;
        InventoryNodeIdentity = inventoryNodeIdentity;
        InventoryModelIdentity = inventoryModelIdentity;
        PlayerIdentity = playerIdentity;
        MapIdentity = mapIdentity;
        RoomVisible = roomVisible;
        InventoryVisible = inventoryVisible;
        InventoryOpen = inventoryOpen;
        ForegroundBlocked = foregroundBlocked;
        MapOpen = mapOpen;
        MapTravelEnabled = mapTravelEnabled;
        MapTraveling = mapTraveling;
        Gold = gold;
        _deck = Copy(deck);
        _offers = Copy(offers);
        BackControl = backControl;
        MerchantControl = merchantControl;
        ProceedControl = proceedControl;
    }

    public ShopV1SurfaceStatus Status { get; }
    public object? RunIdentity { get; }
    public object? RoomIdentity { get; }
    public object? InventoryNodeIdentity { get; }
    public object? InventoryModelIdentity { get; }
    public object? PlayerIdentity { get; }
    public object? MapIdentity { get; }
    public bool RoomVisible { get; }
    public bool InventoryVisible { get; }
    public bool InventoryOpen { get; }
    public bool ForegroundBlocked { get; }
    public bool MapOpen { get; }
    public bool MapTravelEnabled { get; }
    public bool MapTraveling { get; }
    public int Gold { get; }
    public IReadOnlyList<ShopV1DeckCardBinding> Deck => _deck;
    public IReadOnlyList<ShopV1NativeOffer> Offers => _offers;
    public ShopV1NativeControl? BackControl { get; }
    public ShopV1NativeControl? MerchantControl { get; }
    public ShopV1NativeControl? ProceedControl { get; }

    public static ShopV1SurfaceCapture Missing() => Fixed(ShopV1SurfaceStatus.Missing);
    public static ShopV1SurfaceCapture Unsupported() => Fixed(ShopV1SurfaceStatus.Unsupported);

    private static ShopV1SurfaceCapture Fixed(ShopV1SurfaceStatus status) =>
        new(status, null, null, null, null, null, null,
            false, false, false, false, false, false, false, 0,
            Array.Empty<ShopV1DeckCardBinding>(), Array.Empty<ShopV1NativeOffer>(),
            null, null, null);

    private static ReadOnlyCollection<T> Copy<T>(IReadOnlyList<T> source)
    {
        var copy = new T[source.Count];
        for (int index = 0; index < source.Count; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }
}

public sealed class ShopV1PendingProbe
{
    internal ShopV1PendingProbe(
        ShopV1ActionKind kind,
        object runIdentity,
        object roomIdentity,
        object inventoryNodeIdentity,
        object inventoryModelIdentity,
        object playerIdentity,
        object mapIdentity,
        string decisionId,
        string actionId,
        int beforeGold,
        IReadOnlyList<ShopV1DeckCardBinding> beforeDeck,
        int targetSlot,
        object? targetSlotIdentity,
        object? targetEntryIdentity,
        object? targetModelIdentity,
        string targetKey,
        int displayedPrice,
        IShopV1NativeDispatch? purchaseDispatch)
    {
        Kind = kind;
        RunIdentity = runIdentity;
        RoomIdentity = roomIdentity;
        InventoryNodeIdentity = inventoryNodeIdentity;
        InventoryModelIdentity = inventoryModelIdentity;
        PlayerIdentity = playerIdentity;
        MapIdentity = mapIdentity;
        DecisionId = decisionId;
        ActionId = actionId;
        BeforeGold = beforeGold;
        BeforeDeck = ShopV1SurfaceCaptureCopy.Copy(beforeDeck);
        TargetSlot = targetSlot;
        TargetSlotIdentity = targetSlotIdentity;
        TargetEntryIdentity = targetEntryIdentity;
        TargetModelIdentity = targetModelIdentity;
        TargetKey = targetKey;
        DisplayedPrice = displayedPrice;
        PurchaseDispatch = purchaseDispatch;
    }

    public ShopV1ActionKind Kind { get; }
    public object RunIdentity { get; }
    public object RoomIdentity { get; }
    public object InventoryNodeIdentity { get; }
    public object InventoryModelIdentity { get; }
    public object PlayerIdentity { get; }
    public object MapIdentity { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public int BeforeGold { get; }
    public IReadOnlyList<ShopV1DeckCardBinding> BeforeDeck { get; }
    public int TargetSlot { get; }
    public object? TargetSlotIdentity { get; }
    public object? TargetEntryIdentity { get; }
    public object? TargetModelIdentity { get; }
    public string TargetKey { get; }
    public int DisplayedPrice { get; }
    public IShopV1NativeDispatch? PurchaseDispatch { get; }
}

public sealed class ShopV1PendingCapture
{
    private readonly ReadOnlyCollection<ShopV1DeckCardBinding> _deck;

    public ShopV1PendingCapture(
        ShopV1SurfaceStatus status,
        object? runIdentity,
        object? roomIdentity,
        object? inventoryNodeIdentity,
        object? inventoryModelIdentity,
        object? playerIdentity,
        object? mapIdentity,
        bool roomVisible,
        bool inventoryVisible,
        bool inventoryOpen,
        bool foregroundBlocked,
        bool mapOpen,
        bool mapTravelEnabled,
        bool mapTraveling,
        int gold,
        IReadOnlyList<ShopV1DeckCardBinding> deck,
        ShopV1NativeControl? merchantControl,
        ShopV1NativeControl? proceedControl,
        bool targetPresent,
        object? targetSlotIdentity,
        object? targetEntryIdentity,
        bool targetStocked,
        object? targetModelIdentity,
        ShopV1Completion completion)
    {
        Status = status;
        RunIdentity = runIdentity;
        RoomIdentity = roomIdentity;
        InventoryNodeIdentity = inventoryNodeIdentity;
        InventoryModelIdentity = inventoryModelIdentity;
        PlayerIdentity = playerIdentity;
        MapIdentity = mapIdentity;
        RoomVisible = roomVisible;
        InventoryVisible = inventoryVisible;
        InventoryOpen = inventoryOpen;
        ForegroundBlocked = foregroundBlocked;
        MapOpen = mapOpen;
        MapTravelEnabled = mapTravelEnabled;
        MapTraveling = mapTraveling;
        Gold = gold;
        _deck = ShopV1SurfaceCaptureCopy.Copy(deck);
        MerchantControl = merchantControl;
        ProceedControl = proceedControl;
        TargetPresent = targetPresent;
        TargetSlotIdentity = targetSlotIdentity;
        TargetEntryIdentity = targetEntryIdentity;
        TargetStocked = targetStocked;
        TargetModelIdentity = targetModelIdentity;
        Completion = completion;
    }

    public ShopV1SurfaceStatus Status { get; }
    public object? RunIdentity { get; }
    public object? RoomIdentity { get; }
    public object? InventoryNodeIdentity { get; }
    public object? InventoryModelIdentity { get; }
    public object? PlayerIdentity { get; }
    public object? MapIdentity { get; }
    public bool RoomVisible { get; }
    public bool InventoryVisible { get; }
    public bool InventoryOpen { get; }
    public bool ForegroundBlocked { get; }
    public bool MapOpen { get; }
    public bool MapTravelEnabled { get; }
    public bool MapTraveling { get; }
    public int Gold { get; }
    public IReadOnlyList<ShopV1DeckCardBinding> Deck => _deck;
    public ShopV1NativeControl? MerchantControl { get; }
    public ShopV1NativeControl? ProceedControl { get; }
    public bool TargetPresent { get; }
    public object? TargetSlotIdentity { get; }
    public object? TargetEntryIdentity { get; }
    public bool TargetStocked { get; }
    public object? TargetModelIdentity { get; }
    public ShopV1Completion Completion { get; }

    public static ShopV1PendingCapture Missing() => Fixed(ShopV1SurfaceStatus.Missing);
    public static ShopV1PendingCapture Unsupported() => Fixed(ShopV1SurfaceStatus.Unsupported);

    private static ShopV1PendingCapture Fixed(ShopV1SurfaceStatus status) =>
        new(status, null, null, null, null, null, null, false, false, false,
            false, false, false, false, 0, Array.Empty<ShopV1DeckCardBinding>(),
            null, null, false, null, null, false, null, ShopV1Completion.Pending);
}

public interface IShopV1NativeAdapter
{
    ShopV1SurfaceCapture CaptureSurface();
    ShopV1PendingCapture CapturePending(ShopV1PendingProbe pending);
}

internal static class ShopV1SurfaceCaptureCopy
{
    internal static ReadOnlyCollection<T> Copy<T>(IReadOnlyList<T> source)
    {
        var copy = new T[source.Count];
        for (int index = 0; index < source.Count; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }
}
