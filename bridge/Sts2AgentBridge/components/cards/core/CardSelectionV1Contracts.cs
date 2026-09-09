using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace Sts2AgentBridge.Successors.CardSelectionV1;

public static class CardSelectionV1Limits
{
    public const string Version = "card_selection_v1";
    public const int ParentOrdinal = 1;
    public const int MaximumCandidates = 64;
    public const int MaximumDeckCards = 512;
    public const int MaximumSelectedCards = 8;
    public const int MaximumPendingReads = 256;
    public const int MaximumAcceptedActions = 10;
    public const int MaximumKeyLength = 128;
    public const int MaximumActionLength = 16;
}

public enum CardSelectionV1ParentKind
{
    Event = 1,
    Rest = 2,
}

public enum CardSelectionV1Operation
{
    Add = 1,
    Remove = 2,
    Upgrade = 3,
    Transform = 4,
    Enchant = 5,
}

public enum CardSelectionV1CommitMode
{
    AutoAtMax = 1,
    ExplicitConfirm = 2,
    PreviewConfirm = 3,
}

public enum CardSelectionV1Phase
{
    Selecting = 1,
    Preview = 2,
    Submitted = 3,
    Transient = 4,
}

public enum CardSelectionV1SurfaceStatus
{
    Missing = 1,
    Available = 2,
    Unsupported = 3,
}

public enum CardSelectionV1TaskState
{
    Incomplete = 1,
    Succeeded = 2,
    Canceled = 3,
    Faulted = 4,
}

public interface ICardSelectionV1ReadValue { }
public interface ICardSelectionV1ApplyValue { }

public interface ICardSelectionV1NativeAdapter : IDisposable
{
    CardSelectionV1SurfaceCapture CaptureSurface();
}

public sealed class CardSelectionV1ParentContext
{
    public CardSelectionV1ParentContext(
        string sessionNonce,
        CardSelectionV1ParentKind parentKind,
        string parentDecisionId,
        string parentActionId,
        object parentReceiptIdentity,
        object runIdentity,
        object playerIdentity,
        object roomIdentity,
        object mapIdentity,
        object parentOptionIdentity,
        object parentControllerIdentity,
        CardSelectionV1Operation operation,
        int minSelect,
        int maxSelect,
        CardSelectionV1CommitMode commitMode,
        int expectedDomainCount = 0,
        CardSelectionV1Enchantment? enchantment = null,
        bool allowRemovalParentAppend = false)
    {
        AllowRemovalParentAppend = allowRemovalParentAppend;
        SessionNonce = sessionNonce;
        ParentKind = parentKind;
        ParentDecisionId = parentDecisionId;
        ParentActionId = parentActionId;
        ParentReceiptIdentity = parentReceiptIdentity;
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RoomIdentity = roomIdentity;
        MapIdentity = mapIdentity;
        ParentOptionIdentity = parentOptionIdentity;
        ParentControllerIdentity = parentControllerIdentity;
        Operation = operation;
        MinSelect = minSelect;
        MaxSelect = maxSelect;
        CommitMode = commitMode;
        ExpectedDomainCount = expectedDomainCount;
        Enchantment = enchantment;
    }

    public bool AllowRemovalParentAppend { get; }
    public string SessionNonce { get; }
    public CardSelectionV1ParentKind ParentKind { get; }
    public string ParentDecisionId { get; }
    public string ParentActionId { get; }
    public object ParentReceiptIdentity { get; }
    public object RunIdentity { get; }
    public object PlayerIdentity { get; }
    public object RoomIdentity { get; }
    public object MapIdentity { get; }
    public object ParentOptionIdentity { get; }
    public object ParentControllerIdentity { get; }
    public CardSelectionV1Operation Operation { get; }
    public int MinSelect { get; }
    public int MaxSelect { get; }
    public CardSelectionV1CommitMode CommitMode { get; }
    public int ExpectedDomainCount { get; }
    public CardSelectionV1Enchantment? Enchantment { get; }
}

public sealed class CardSelectionV1NativeControl
{
    public CardSelectionV1NativeControl(
        object identity,
        bool visible,
        bool enabled,
        Action dispatch)
    {
        Identity = identity;
        Visible = visible;
        Enabled = enabled;
        Dispatch = dispatch;
    }

    public object Identity { get; }
    public bool Visible { get; }
    public bool Enabled { get; }
    public Action Dispatch { get; }
}

public sealed class CardSelectionV1NativeCandidate
{
    public CardSelectionV1NativeCandidate(
        int slot,
        string stableKey,
        object holderIdentity,
        object modelIdentity,
        object cardNodeIdentity,
        int upgradeLevel,
        bool visible,
        bool enabled,
        bool selected,
        bool selectionSettled,
        Action selectDispatch)
    {
        Slot = slot;
        StableKey = stableKey;
        HolderIdentity = holderIdentity;
        ModelIdentity = modelIdentity;
        CardNodeIdentity = cardNodeIdentity;
        UpgradeLevel = upgradeLevel;
        Visible = visible;
        Enabled = enabled;
        Selected = selected;
        SelectionSettled = selectionSettled;
        SelectDispatch = selectDispatch;
    }

    public int Slot { get; }
    public string StableKey { get; }
    public object HolderIdentity { get; }
    public object ModelIdentity { get; }
    public object CardNodeIdentity { get; }
    public int UpgradeLevel { get; }
    public bool Visible { get; }
    public bool Enabled { get; }
    public bool Selected { get; }
    public bool SelectionSettled { get; }
    public Action SelectDispatch { get; }
}

// Native identity stays private to the adapter/session; only key and amount are public.
public sealed record CardSelectionV1Enchantment(object Identity, string Key, int Amount)
{
    public static bool Same(CardSelectionV1Enchantment? a, CardSelectionV1Enchantment? b) =>
        a is null || b is null ? a is null && b is null :
        ReferenceEquals(a.Identity, b.Identity) && a.Key == b.Key && a.Amount == b.Amount;
}

public sealed class CardSelectionV1DeckCard
{
    public CardSelectionV1DeckCard(object modelIdentity, string stableKey, int upgradeLevel,
        CardSelectionV1Enchantment? enchantment = null)
    {
        ModelIdentity = modelIdentity;
        StableKey = stableKey;
        UpgradeLevel = upgradeLevel;
        Enchantment = enchantment;
    }

    public CardSelectionV1Enchantment? Enchantment { get; }
    public object ModelIdentity { get; }
    public string StableKey { get; }
    public int UpgradeLevel { get; }
}

public sealed class CardSelectionV1Replacement
{
    public CardSelectionV1Replacement(
        object originalModelIdentity,
        object replacementModelIdentity,
        string replacementStableKey,
        int replacementUpgradeLevel)
    {
        OriginalModelIdentity = originalModelIdentity;
        ReplacementModelIdentity = replacementModelIdentity;
        ReplacementStableKey = replacementStableKey;
        ReplacementUpgradeLevel = replacementUpgradeLevel;
    }

    public object OriginalModelIdentity { get; }
    public object ReplacementModelIdentity { get; }
    public string ReplacementStableKey { get; }
    public int ReplacementUpgradeLevel { get; }
}

public sealed class CardSelectionV1SurfaceCapture
{
    private readonly ReadOnlyCollection<CardSelectionV1NativeCandidate> _candidates;
    private readonly ReadOnlyCollection<CardSelectionV1DeckCard> _deck;
    private readonly ReadOnlyCollection<object> _taskResultOriginals;
    private readonly ReadOnlyCollection<object> _previewOriginals;
    private readonly ReadOnlyCollection<CardSelectionV1Replacement> _replacements;

    public CardSelectionV1SurfaceCapture(
        CardSelectionV1SurfaceStatus status,
        object? parentReceiptIdentity,
        object? runIdentity,
        object? playerIdentity,
        object? roomIdentity,
        object? mapIdentity,
        object? parentOptionIdentity,
        object? parentControllerIdentity,
        object? screenIdentity,
        object? completionTaskIdentity,
        object? previewIdentity,
        CardSelectionV1ParentKind parentKind,
        CardSelectionV1Operation operation,
        int minSelect,
        int maxSelect,
        CardSelectionV1CommitMode commitMode,
        CardSelectionV1Phase phase,
        bool selectorTop,
        bool selectorClosed,
        bool previewOpen,
        bool completeDomain,
        int completeDomainCount,
        bool completeDeck,
        CardSelectionV1TaskState taskState,
        bool effectCompletionObserved,
        IReadOnlyList<object> taskResultOriginals,
        IReadOnlyList<object> previewOriginals,
        IReadOnlyList<CardSelectionV1NativeCandidate> candidates,
        IReadOnlyList<CardSelectionV1DeckCard> deck,
        IReadOnlyList<CardSelectionV1Replacement> replacements,
        CardSelectionV1NativeControl? previewControl,
        CardSelectionV1NativeControl? confirmControl,
        CardSelectionV1Enchantment? enchantment = null)
    {
        Status = status;
        ParentReceiptIdentity = parentReceiptIdentity;
        RunIdentity = runIdentity;
        PlayerIdentity = playerIdentity;
        RoomIdentity = roomIdentity;
        MapIdentity = mapIdentity;
        ParentOptionIdentity = parentOptionIdentity;
        ParentControllerIdentity = parentControllerIdentity;
        ScreenIdentity = screenIdentity;
        CompletionTaskIdentity = completionTaskIdentity;
        PreviewIdentity = previewIdentity;
        ParentKind = parentKind;
        Operation = operation;
        MinSelect = minSelect;
        MaxSelect = maxSelect;
        CommitMode = commitMode;
        Phase = phase;
        SelectorTop = selectorTop;
        SelectorClosed = selectorClosed;
        PreviewOpen = previewOpen;
        CompleteDomain = completeDomain;
        CompleteDomainCount = completeDomainCount;
        CompleteDeck = completeDeck;
        TaskState = taskState;
        EffectCompletionObserved = effectCompletionObserved;
        _taskResultOriginals = Copy(taskResultOriginals);
        _previewOriginals = Copy(previewOriginals);
        _candidates = Copy(candidates);
        _deck = Copy(deck);
        _replacements = Copy(replacements);
        PreviewControl = previewControl;
        ConfirmControl = confirmControl;
        Enchantment = enchantment;
    }

    public CardSelectionV1SurfaceStatus Status { get; }
    public object? ParentReceiptIdentity { get; }
    public object? RunIdentity { get; }
    public object? PlayerIdentity { get; }
    public object? RoomIdentity { get; }
    public object? MapIdentity { get; }
    public object? ParentOptionIdentity { get; }
    public object? ParentControllerIdentity { get; }
    public object? ScreenIdentity { get; }
    public object? CompletionTaskIdentity { get; }
    public object? PreviewIdentity { get; }
    public CardSelectionV1ParentKind ParentKind { get; }
    public CardSelectionV1Operation Operation { get; }
    public int MinSelect { get; }
    public int MaxSelect { get; }
    public CardSelectionV1CommitMode CommitMode { get; }
    public CardSelectionV1Phase Phase { get; }
    public bool SelectorTop { get; }
    public bool SelectorClosed { get; }
    public bool PreviewOpen { get; }
    public bool CompleteDomain { get; }
    public int CompleteDomainCount { get; }
    public bool CompleteDeck { get; }
    public CardSelectionV1TaskState TaskState { get; }
    public bool EffectCompletionObserved { get; }
    public IReadOnlyList<object> TaskResultOriginals => _taskResultOriginals;
    public IReadOnlyList<object> PreviewOriginals => _previewOriginals;
    public IReadOnlyList<CardSelectionV1NativeCandidate> Candidates => _candidates;
    public IReadOnlyList<CardSelectionV1DeckCard> Deck => _deck;
    public IReadOnlyList<CardSelectionV1Replacement> Replacements => _replacements;
    public CardSelectionV1NativeControl? PreviewControl { get; }
    public CardSelectionV1NativeControl? ConfirmControl { get; }
    public CardSelectionV1Enchantment? Enchantment { get; }

    private static ReadOnlyCollection<T> Copy<T>(IReadOnlyList<T> source)
    {
        ArgumentNullException.ThrowIfNull(source);
        var copy = new T[source.Count];
        for (int index = 0; index < source.Count; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }
}

public sealed class CardSelectionV1Candidate
{
    internal CardSelectionV1Candidate(
        int slot,
        string key,
        int upgradeLevel,
        bool visible,
        bool enabled,
        bool selected)
    {
        Slot = slot;
        Key = key;
        UpgradeLevel = upgradeLevel;
        Visible = visible;
        Enabled = enabled;
        Selected = selected;
    }

    public int Slot { get; }
    public string Key { get; }
    public int UpgradeLevel { get; }
    public bool Visible { get; }
    public bool Enabled { get; }
    public bool Selected { get; }
}

public sealed class CardSelectionV1ActionResult
{
    internal CardSelectionV1ActionResult(
        string decisionId,
        string actionId,
        string result)
    {
        DecisionId = decisionId;
        ActionId = actionId;
        Result = result;
    }

    public string DecisionId { get; }
    public string ActionId { get; }
    public string Result { get; }
}

public sealed class CardSelectionV1EnchantmentEffect
{
    internal CardSelectionV1EnchantmentEffect(string key, int amount) { Key = key; Amount = amount; }
    public string Key { get; }
    public int Amount { get; }
}

public sealed class CardSelectionV1Observation : ICardSelectionV1ReadValue
{
    private readonly ReadOnlyCollection<CardSelectionV1Candidate> _candidates;
    private readonly ReadOnlyCollection<int> _selectedSlots;
    private readonly ReadOnlyCollection<string> _legalActions;
    private readonly ReadOnlyCollection<CardSelectionV1ActionResult> _priorResults;

    internal CardSelectionV1Observation(
        string sessionNonce,
        string status,
        string phase,
        string operation,
        string commitMode,
        int minSelect,
        int maxSelect,
        string decisionId,
        IReadOnlyList<CardSelectionV1Candidate> candidates,
        IReadOnlyList<int> selectedSlots,
        IReadOnlyList<string> legalActions,
        IReadOnlyList<CardSelectionV1ActionResult> priorResults,
        CardSelectionV1Enchantment? enchantment = null)
    {
        Version = CardSelectionV1Limits.Version;
        SessionNonce = sessionNonce;
        ParentOrdinal = CardSelectionV1Limits.ParentOrdinal;
        Status = status;
        Phase = phase;
        Operation = operation;
        CommitMode = commitMode;
        MinSelect = minSelect;
        MaxSelect = maxSelect;
        DecisionId = decisionId;
        _candidates = Copy(candidates);
        _selectedSlots = Copy(selectedSlots);
        _legalActions = Copy(legalActions);
        _priorResults = Copy(priorResults);
        Enchantment = enchantment is null ? null : new CardSelectionV1EnchantmentEffect(enchantment.Key, enchantment.Amount);
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string Status { get; }
    public string Phase { get; }
    public string Operation { get; }
    public string CommitMode { get; }
    public int MinSelect { get; }
    public int MaxSelect { get; }
    public string DecisionId { get; }
    public IReadOnlyList<CardSelectionV1Candidate> Candidates => _candidates;
    public IReadOnlyList<int> SelectedSlots => _selectedSlots;
    public IReadOnlyList<string> LegalActions => _legalActions;
    public IReadOnlyList<CardSelectionV1ActionResult> PriorResults => _priorResults;
    public CardSelectionV1EnchantmentEffect? Enchantment { get; }

    internal static CardSelectionV1Observation Fixed(
        string nonce,
        string status,
        string phase,
        IReadOnlyList<CardSelectionV1ActionResult> priorResults) =>
        new(nonce, status, phase, string.Empty, string.Empty, 0, 0, string.Empty,
            Array.Empty<CardSelectionV1Candidate>(), Array.Empty<int>(),
            Array.Empty<string>(), priorResults);

    private static ReadOnlyCollection<T> Copy<T>(IReadOnlyList<T> source)
    {
        var copy = new T[source.Count];
        for (int index = 0; index < source.Count; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }
}

public sealed class CardSelectionV1ParentAddedCard
{
    internal CardSelectionV1ParentAddedCard(CardSelectionV1DeckCard card)
    {
        Key=card.StableKey; UpgradeLevel=card.UpgradeLevel;
        Enchantment=card.Enchantment is {} e ? new CardSelectionV1EnchantmentEffect(e.Key,e.Amount) : null;
    }
    public string Key { get; }
    public int UpgradeLevel { get; }
    public CardSelectionV1EnchantmentEffect? Enchantment { get; }
}

public sealed class CardSelectionV1ResolvedResult : ICardSelectionV1ReadValue
{
    private readonly ReadOnlyCollection<CardSelectionV1Candidate> _selectedCards;
    private readonly ReadOnlyCollection<CardSelectionV1ActionResult> _priorResults;

    internal CardSelectionV1ResolvedResult(
        string sessionNonce,
        string operation,
        IReadOnlyList<CardSelectionV1Candidate> selectedCards,
        IReadOnlyList<CardSelectionV1ActionResult> priorResults,
        CardSelectionV1Enchantment? enchantment = null,
        IReadOnlyList<CardSelectionV1DeckCard>? parentAddedCards = null)
    {
        var additions=new List<CardSelectionV1ParentAddedCard>();
        foreach(var card in parentAddedCards ?? Array.Empty<CardSelectionV1DeckCard>()) additions.Add(new(card));
        ParentAddedCards=additions.AsReadOnly();
        Version = CardSelectionV1Limits.Version;
        SessionNonce = sessionNonce;
        ParentOrdinal = CardSelectionV1Limits.ParentOrdinal;
        Status = "resolved";
        Phase = "complete";
        Operation = operation;
        _selectedCards = Copy(selectedCards);
        _priorResults = Copy(priorResults);
        Enchantment = enchantment is null ? null : new CardSelectionV1EnchantmentEffect(enchantment.Key, enchantment.Amount);
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string Status { get; }
    public string Phase { get; }
    public string Operation { get; }
    public IReadOnlyList<CardSelectionV1ParentAddedCard> ParentAddedCards { get; }
    public IReadOnlyList<CardSelectionV1Candidate> SelectedCards => _selectedCards;
    public IReadOnlyList<CardSelectionV1ActionResult> PriorResults => _priorResults;
    public CardSelectionV1EnchantmentEffect? Enchantment { get; }

    private static ReadOnlyCollection<T> Copy<T>(IReadOnlyList<T> source)
    {
        var copy = new T[source.Count];
        for (int index = 0; index < source.Count; index++) copy[index] = source[index];
        return Array.AsReadOnly(copy);
    }
}

public sealed class CardSelectionV1DispatchReceipt : ICardSelectionV1ApplyValue
{
    internal CardSelectionV1DispatchReceipt(
        string sessionNonce,
        string decisionId,
        string actionId)
    {
        Version = CardSelectionV1Limits.Version;
        SessionNonce = sessionNonce;
        ParentOrdinal = CardSelectionV1Limits.ParentOrdinal;
        DecisionId = decisionId;
        ActionId = actionId;
        Outcome = "accepted";
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string DecisionId { get; }
    public string ActionId { get; }
    public string Outcome { get; }
}

public sealed class CardSelectionV1ApplyFailure : ICardSelectionV1ApplyValue
{
    internal CardSelectionV1ApplyFailure(string sessionNonce, string outcome)
    {
        Version = CardSelectionV1Limits.Version;
        SessionNonce = sessionNonce;
        ParentOrdinal = CardSelectionV1Limits.ParentOrdinal;
        Outcome = outcome;
    }

    public string Version { get; }
    public string SessionNonce { get; }
    public int ParentOrdinal { get; }
    public string Outcome { get; }
}
