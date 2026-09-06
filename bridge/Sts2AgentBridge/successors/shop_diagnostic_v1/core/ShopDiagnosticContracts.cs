using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

public enum ShopDiagnosticStage
{
    NativeContext = 1,
    NativeDeck = 2,
    NativeControls = 3,
    NativeForeground = 4,
    NativeOffers = 5,
    CoreSurface = 6,
    CoreContext = 7,
    CoreDeck = 8,
    CoreOffers = 9,
    CoreInventory = 10,
    Complete = 11,
}

public enum ShopDiagnosticReason
{
    None = 1,
    RunUnavailable = 2,
    RoomUnavailable = 3,
    RoomSingletonMismatch = 4,
    GlobalUiUnavailable = 5,
    MapUnavailable = 6,
    MapSingletonMismatch = 7,
    InventoryNodeUnavailable = 8,
    RoomModelUnavailable = 9,
    InventoryModelUnavailable = 10,
    PlayerUnavailable = 11,
    InventoryModelMismatch = 12,
    CurrentRoomMismatch = 13,
    DeckCountOutOfRange = 14,
    DeckCardUnavailable = 15,
    DeckCountChanged = 16,
    BackControlUnavailable = 17,
    MerchantControlUnavailable = 18,
    ProceedControlUnavailable = 19,
    OverlayStackUnavailable = 20,
    OverlayCountOutOfRange = 21,
    OfferCountOutOfRange = 22,
    OfferSlotUnavailable = 23,
    OfferHitboxUnavailable = 24,
    OfferEntryUnavailable = 25,
    CardModelUnavailable = 26,
    RelicModelUnavailable = 27,
    PotionModelUnavailable = 28,
    CostLabelUnavailable = 29,
    CostTextInvalid = 30,
    NativeException = 31,
    SurfaceMissing = 32,
    SurfaceUnsupported = 33,
    ContextUnavailable = 34,
    GoldOutOfRange = 35,
    RoomNotVisible = 36,
    ForegroundBlocked = 37,
    MapOpen = 38,
    MapTravelEnabled = 39,
    MapTraveling = 40,
    InitialBindingInvalid = 41,
    DeckBindingInvalid = 42,
    OfferSlotInvalid = 43,
    OfferOrderInvalid = 44,
    OfferKeyInvalid = 45,
    OfferPriceInvalid = 46,
    OfferNotVisible = 47,
    OfferIdentityInvalid = 48,
    OfferIdentityDuplicate = 49,
    CardBindingInvalid = 50,
    CardAlreadyInDeck = 51,
    NoncardBindingInvalid = 52,
    InventoryNotOpen = 53,
    InventoryNotVisible = 54,
    BackControlNotReady = 55,
    ProjectionException = 56,
}

public enum ShopDiagnosticSurfaceStatus
{
    Missing = 1,
    Available = 2,
    Unsupported = 3,
}

public enum ShopDiagnosticOfferKind
{
    Card = 1,
    Relic = 2,
    Potion = 3,
    Removal = 4,
    Unknown = 5,
}

public interface IShopDiagnosticRecorder
{
    void Enter(ShopDiagnosticStage stage);
    void Reject(ShopDiagnosticReason reason);
}

public interface IShopDiagnosticAdapter
{
    ShopDiagnosticCapture CaptureSurface(IShopDiagnosticRecorder recorder);
}

public sealed class ShopDiagnosticDeckCard
{
    public ShopDiagnosticDeckCard(object modelIdentity, string stableKey)
    {
        ModelIdentity = modelIdentity;
        StableKey = stableKey;
    }

    public object ModelIdentity { get; }
    public string StableKey { get; }
}

public sealed class ShopDiagnosticControl
{
    public ShopDiagnosticControl(object identity, bool visible, bool enabled, bool actionReady)
    {
        Identity = identity;
        Visible = visible;
        Enabled = enabled;
        ActionReady = actionReady;
    }

    public object Identity { get; }
    public bool Visible { get; }
    public bool Enabled { get; }
    public bool ActionReady { get; }
}

public sealed class ShopDiagnosticOffer
{
    public ShopDiagnosticOffer(
        int slot,
        ShopDiagnosticOfferKind kind,
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
        bool purchaseActionReady)
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
        PurchaseActionReady = purchaseActionReady;
    }

    public int Slot { get; }
    public ShopDiagnosticOfferKind Kind { get; }
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
    public bool PurchaseActionReady { get; }
}

public sealed class ShopDiagnosticCapture
{
    private readonly ReadOnlyCollection<ShopDiagnosticDeckCard> _deck;
    private readonly ReadOnlyCollection<ShopDiagnosticOffer> _offers;

    public ShopDiagnosticCapture(
        ShopDiagnosticSurfaceStatus status,
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
        IReadOnlyList<ShopDiagnosticDeckCard> deck,
        IReadOnlyList<ShopDiagnosticOffer> offers,
        ShopDiagnosticControl? backControl,
        ShopDiagnosticControl? merchantControl,
        ShopDiagnosticControl? proceedControl)
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

    public ShopDiagnosticSurfaceStatus Status { get; }
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
    public IReadOnlyList<ShopDiagnosticDeckCard> Deck => _deck;
    public IReadOnlyList<ShopDiagnosticOffer> Offers => _offers;
    public ShopDiagnosticControl? BackControl { get; }
    public ShopDiagnosticControl? MerchantControl { get; }
    public ShopDiagnosticControl? ProceedControl { get; }

    public static ShopDiagnosticCapture Missing() => Fixed(ShopDiagnosticSurfaceStatus.Missing);
    public static ShopDiagnosticCapture Unsupported() => Fixed(ShopDiagnosticSurfaceStatus.Unsupported);

    private static ShopDiagnosticCapture Fixed(ShopDiagnosticSurfaceStatus status) =>
        new(status, null, null, null, null, null, null, false, false, false,
            false, false, false, false, 0, Array.Empty<ShopDiagnosticDeckCard>(),
            Array.Empty<ShopDiagnosticOffer>(), null, null, null);

    private static ReadOnlyCollection<T> Copy<T>(IReadOnlyList<T> source)
    {
        var copy = new T[source.Count];
        for (int index = 0; index < source.Count; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }
}
