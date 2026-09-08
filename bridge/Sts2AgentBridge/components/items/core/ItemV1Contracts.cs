using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace Sts2AgentBridge.Successors.ItemV1;

public static class ItemV1Constants
{
    public const string Version = "item_v1";
    public const int SurfaceOrdinal = 1;
    public const int MaximumOffers = 8;
    public const int MaximumPotionSlots = 8;
    public const int MaximumRewardIndex = 255;
    public const int MaximumKeyLength = 128;
    public const int MaximumReconciliationReads = 256;
}

public enum ItemV1ItemKind
{
    Potion = 1,
    Relic = 2,
    Unsupported = 3,
}

public sealed class ItemV1Offer
{
    public ItemV1Offer(int index, string kind, string key, bool enabled)
    {
        Index = index;
        Kind = kind;
        Key = key;
        Enabled = enabled;
    }

    public int Index { get; }
    public string Kind { get; }
    public string Key { get; }
    public bool Enabled { get; }
}

public interface IItemV1ReadValue
{
}

public sealed class ItemV1Observation : IItemV1ReadValue
{
    private readonly ReadOnlyCollection<ItemV1Offer> _offers;
    private readonly ReadOnlyCollection<string?> _potionSlots;
    private readonly ReadOnlyCollection<string> _legalActions;

    internal ItemV1Observation(
        string sessionNonce,
        string status,
        string decisionId,
        IReadOnlyList<ItemV1Offer> offers,
        IReadOnlyList<string?> potionSlots,
        IReadOnlyList<string> legalActions)
    {
        Version = ItemV1Constants.Version;
        SessionNonce = sessionNonce;
        SurfaceOrdinal = ItemV1Constants.SurfaceOrdinal;
        Status = status;
        DecisionId = decisionId;
        _offers = Copy(offers);
        _potionSlots = Copy(potionSlots);
        _legalActions = Copy(legalActions);
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int SurfaceOrdinal { get; }
    public string Status { get; }
    public string DecisionId { get; }
    public IReadOnlyList<ItemV1Offer> Offers => _offers;
    public IReadOnlyList<string?> PotionSlots => _potionSlots;
    public IReadOnlyList<string> LegalActions => _legalActions;

    internal static ItemV1Observation Fixed(string nonce, string status) =>
        new(nonce, status, string.Empty, Array.Empty<ItemV1Offer>(),
            Array.Empty<string?>(), Array.Empty<string>());

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

public sealed class ItemV1ResolvedResult : IItemV1ReadValue
{
    internal ItemV1ResolvedResult(
        string sessionNonce,
        string decisionId,
        string actionId,
        int offerIndex,
        string kind,
        string key)
    {
        Version = ItemV1Constants.Version;
        SessionNonce = sessionNonce;
        SurfaceOrdinal = ItemV1Constants.SurfaceOrdinal;
        DecisionId = decisionId;
        ActionId = actionId;
        OfferIndex = offerIndex;
        Kind = kind;
        Key = key;
        Result = "collected";
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int SurfaceOrdinal { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public int OfferIndex { get; }
    public string Kind { get; }
    public string Key { get; }
    public string Result { get; }
}

public interface IItemV1ApplyValue
{
}

public sealed class ItemV1DispatchReceipt : IItemV1ApplyValue
{
    internal ItemV1DispatchReceipt(string sessionNonce, string decisionId, string actionId)
    {
        Version = ItemV1Constants.Version;
        SessionNonce = sessionNonce;
        SurfaceOrdinal = ItemV1Constants.SurfaceOrdinal;
        DecisionId = decisionId;
        ActionId = actionId;
        Outcome = "accepted";
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int SurfaceOrdinal { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Outcome { get; }
}

public sealed class ItemV1ApplyFailure : IItemV1ApplyValue
{
    internal ItemV1ApplyFailure(string sessionNonce, string outcome)
    {
        Version = ItemV1Constants.Version;
        SessionNonce = sessionNonce;
        SurfaceOrdinal = ItemV1Constants.SurfaceOrdinal;
        Outcome = outcome;
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int SurfaceOrdinal { get; }
    public string Outcome { get; }
}

public enum ItemV1SurfaceStatus
{
    Missing = 1,
    Available = 2,
    Unsupported = 3,
}

public sealed class ItemV1PotionSlotBinding
{
    public ItemV1PotionSlotBinding(object? modelIdentity, string? stableKey)
    {
        ModelIdentity = modelIdentity;
        StableKey = stableKey;
    }

    public object? ModelIdentity { get; }
    public string? StableKey { get; }
}

public sealed class ItemV1NativeOffer
{
    public ItemV1NativeOffer(
        int index,
        ItemV1ItemKind kind,
        string stableKey,
        bool populated,
        bool alreadySelected,
        bool buttonVisible,
        bool buttonEnabled,
        object buttonIdentity,
        object rewardIdentity,
        object offeredModelIdentity,
        Action dispatch)
    {
        Index = index;
        Kind = kind;
        StableKey = stableKey;
        Populated = populated;
        AlreadySelected = alreadySelected;
        ButtonVisible = buttonVisible;
        ButtonEnabled = buttonEnabled;
        ButtonIdentity = buttonIdentity;
        RewardIdentity = rewardIdentity;
        OfferedModelIdentity = offeredModelIdentity;
        Dispatch = dispatch;
    }

    public int Index { get; }
    public ItemV1ItemKind Kind { get; }
    public string StableKey { get; }
    public bool Populated { get; }
    public bool AlreadySelected { get; }
    public bool ButtonVisible { get; }
    public bool ButtonEnabled { get; }
    public object ButtonIdentity { get; }
    public object RewardIdentity { get; }
    public object OfferedModelIdentity { get; }
    public Action Dispatch { get; }
}

public sealed class ItemV1SurfaceCapture
{
    private readonly ReadOnlyCollection<ItemV1NativeOffer> _offers;
    private readonly ReadOnlyCollection<ItemV1PotionSlotBinding> _potionSlots;

    private ItemV1SurfaceCapture(
        ItemV1SurfaceStatus status,
        object? runIdentity,
        object? playerIdentity,
        object? screenIdentity,
        int potionCapacity,
        IReadOnlyList<ItemV1NativeOffer> offers,
        IReadOnlyList<ItemV1PotionSlotBinding> potionSlots)
    {
        Status = status;
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        ScreenIdentity = screenIdentity;
        PotionCapacity = potionCapacity;
        _offers = Copy(offers);
        _potionSlots = Copy(potionSlots);
    }

    public ItemV1SurfaceStatus Status { get; }
    public object? RunIdentity { get; }
    public object? PlayerIdentity { get; }
    public object? ScreenIdentity { get; }
    public int PotionCapacity { get; }
    public IReadOnlyList<ItemV1NativeOffer> Offers => _offers;
    public IReadOnlyList<ItemV1PotionSlotBinding> PotionSlots => _potionSlots;

    public static ItemV1SurfaceCapture Missing() =>
        new(ItemV1SurfaceStatus.Missing, null, null, null, 0,
            Array.Empty<ItemV1NativeOffer>(), Array.Empty<ItemV1PotionSlotBinding>());

    public static ItemV1SurfaceCapture Unsupported() =>
        new(ItemV1SurfaceStatus.Unsupported, null, null, null, 0,
            Array.Empty<ItemV1NativeOffer>(), Array.Empty<ItemV1PotionSlotBinding>());

    public static ItemV1SurfaceCapture Available(
        object runIdentity,
        object playerIdentity,
        object screenIdentity,
        int potionCapacity,
        IReadOnlyList<ItemV1NativeOffer> offers,
        IReadOnlyList<ItemV1PotionSlotBinding> potionSlots) =>
        new(ItemV1SurfaceStatus.Available, runIdentity, playerIdentity, screenIdentity,
            potionCapacity, offers, potionSlots);

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

public sealed class ItemV1PendingProbe
{
    internal ItemV1PendingProbe(
        object runIdentity,
        object playerIdentity,
        object rewardIdentity,
        object offeredModelIdentity,
        ItemV1ItemKind kind)
    {
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RewardIdentity = rewardIdentity;
        OfferedModelIdentity = offeredModelIdentity;
        Kind = kind;
    }

    public object RunIdentity { get; }
    public object PlayerIdentity { get; }
    public object RewardIdentity { get; }
    public object OfferedModelIdentity { get; }
    public ItemV1ItemKind Kind { get; }
}

public sealed class ItemV1PendingCapture
{
    private readonly ReadOnlyCollection<ItemV1PotionSlotBinding> _potionSlots;

    public ItemV1PendingCapture(
        object runIdentity,
        object playerIdentity,
        object rewardIdentity,
        object offeredModelIdentity,
        string offeredStableKey,
        bool successfullySelected,
        object? claimedModelIdentity,
        string? claimedStableKey,
        int potionCapacity,
        IReadOnlyList<ItemV1PotionSlotBinding> potionSlots)
    {
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RewardIdentity = rewardIdentity;
        OfferedModelIdentity = offeredModelIdentity;
        OfferedStableKey = offeredStableKey;
        SuccessfullySelected = successfullySelected;
        ClaimedModelIdentity = claimedModelIdentity;
        ClaimedStableKey = claimedStableKey;
        PotionCapacity = potionCapacity;
        var copy = new ItemV1PotionSlotBinding[potionSlots.Count];
        for (int index = 0; index < potionSlots.Count; index++)
        {
            copy[index] = potionSlots[index];
        }
        _potionSlots = Array.AsReadOnly(copy);
    }

    public object RunIdentity { get; }
    public object PlayerIdentity { get; }
    public object RewardIdentity { get; }
    public object OfferedModelIdentity { get; }
    public string OfferedStableKey { get; }
    public bool SuccessfullySelected { get; }
    public object? ClaimedModelIdentity { get; }
    public string? ClaimedStableKey { get; }
    public int PotionCapacity { get; }
    public IReadOnlyList<ItemV1PotionSlotBinding> PotionSlots => _potionSlots;
}

public interface IItemV1NativeAdapter
{
    ItemV1SurfaceCapture CaptureSurface();
    ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending);
}
