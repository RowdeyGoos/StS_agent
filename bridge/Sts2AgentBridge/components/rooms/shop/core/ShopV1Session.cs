using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop;

public sealed class ShopV1Session : IRoomFlowSession
{
    private readonly object _gate = new();
    private readonly int _ownerThreadId = Environment.CurrentManagedThreadId;
    private readonly string _sessionNonce;
    private readonly IShopV1NativeAdapter _adapter;
    private readonly HashSet<string> _reservedDecisionIds = new(StringComparer.Ordinal);
    private object? _boundRun;
    private object? _boundRoom;
    private object? _boundInventoryNode;
    private object? _boundInventoryModel;
    private object? _boundPlayer;
    private object? _boundMap;
    private PublishedDecision? _published;
    private PendingAction? _pending;
    private ShopV1ReconciledAction? _priorResult;
    private ShopV1Observation? _completed;
    private bool _purchaseUsed;
    private bool _closeReconciled;
    private bool _dispatching;
    private bool _inside;
    private bool _interfered;
    private bool _accepted;
    private bool _unsupported;
    private bool _disposed;
    private bool _cleanupFailed;
    private int _reservations;
    private int _pendingReads;

    public ShopV1Session(string sessionNonce, IShopV1NativeAdapter adapter)
    {
        if (!RoomFlowIdentity.IsNonce(sessionNonce))
        {
            throw new ArgumentException("The session nonce is not canonical.", nameof(sessionNonce));
        }
        _sessionNonce = sessionNonce;
        _adapter = adapter ?? throw new ArgumentNullException(nameof(adapter));
    }

    public string FlowKind => ShopV1Constants.FlowKind;

    public IRoomFlowReadValue Read()
    {
        lock (_gate)
        {
            if (_inside)
            {
                _interfered = true;
                return FixedWaiting(PendingPhase());
            }
            if (Environment.CurrentManagedThreadId != _ownerThreadId)
            {
                LatchOffOwner();
                return FixedUnsupported();
            }
            if (_disposed || _unsupported)
            {
                return FixedUnsupported();
            }
            if (_completed is not null)
            {
                return _completed;
            }
            if (_dispatching)
            {
                return FixedWaiting(PendingPhase());
            }
            if (_pending is not null)
            {
                return _accepted ? Reconcile() : FixedUnsupported();
            }
            return ObserveReadySurface();
        }
    }

    public IRoomFlowApplyValue Apply(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (_inside)
            {
                _interfered = true;
                return Failure("rejected");
            }
            if (Environment.CurrentManagedThreadId != _ownerThreadId)
            {
                LatchOffOwner();
                return Failure("unsupported");
            }
            if (_disposed || _unsupported)
            {
                return Failure("unsupported");
            }
            if (_completed is not null)
            {
                return Failure("rejected");
            }
            if (_dispatching || _pending is not null || _published is null ||
                !RoomFlowIdentity.IsDecisionId(decisionId) ||
                string.IsNullOrEmpty(actionId) || actionId.Length > ShopV1Constants.MaximumActionLength ||
                !string.Equals(_published.Observation.DecisionId, decisionId,
                    StringComparison.Ordinal) ||
                !_published.HasAction(actionId) ||
                _reservedDecisionIds.Contains(decisionId!))
            {
                return Failure("rejected");
            }

            ShopV1SurfaceCapture capture;
            PublishedDecision? recaptured;
            try
            {
                _inside = true;
                capture = _adapter.CaptureSurface();
                if (_disposed || _interfered ||
                    !TryProject(capture, bind: false, out recaptured) ||
                    recaptured is null || !SamePublished(_published, recaptured) ||
                    !string.Equals(recaptured.Observation.DecisionId, decisionId,
                        StringComparison.Ordinal))
                {
                    LatchUnsupported();
                    return Failure("unsupported");
                }
            }
            catch
            {
                LatchUnsupported();
                return Failure("unsupported");
            }
            finally
            {
                _inside = false;
            }

            PendingAction? pending = BuildPending(recaptured, decisionId!, actionId);
            if (pending is null || _reservations >= ShopV1Constants.MaximumReservations)
            {
                return Failure("rejected");
            }

            _pending = pending;
            _pendingReads = 0;
            _accepted = false;
            _dispatching = true;
            _published = null;
            _priorResult = null;
            _reservations++;
            _reservedDecisionIds.Add(decisionId!);
            if (pending.Probe.Kind == ShopV1ActionKind.PurchaseCard)
            {
                _purchaseUsed = true;
            }

            try
            {
                _inside = true;
                Dispatch(pending);
                if (_disposed || _interfered)
                    throw new InvalidOperationException("Shop dispatch was interrupted.");
                _accepted = true;
                return new RoomFlowDispatchReceipt(
                    FlowKind, _sessionNonce, decisionId!, actionId);
            }
            catch
            {
                _unsupported = true;
                ReleasePending();
                return Failure("uncertain");
            }
            finally
            {
                _inside = false;
                _dispatching = false;
            }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (Environment.CurrentManagedThreadId != _ownerThreadId)
                throw new InvalidOperationException("Shop cleanup requires the owner thread.");
            if (_disposed)
            {
                if (_cleanupFailed)
                {
                    throw new InvalidOperationException("Shop cleanup failed.");
                }
                return;
            }
            _disposed = true;
            _unsupported = true;
            _published = null;
            _completed = null;
            if (_inside)
            {
                _interfered = true;
                return;
            }
            ReleasePending();
            if (_cleanupFailed)
            {
                throw new InvalidOperationException("Shop cleanup failed.");
            }
        }
    }

    private IRoomFlowReadValue ObserveReadySurface()
    {
        try
        {
            _inside = true;
            ShopV1SurfaceCapture capture = _adapter.CaptureSurface();
            if (_disposed || _interfered)
            {
                LatchUnsupported();
                return FixedUnsupported();
            }
            if (capture.Status == ShopV1SurfaceStatus.Missing)
            {
                _published = null;
                return FixedWaiting(_closeReconciled
                    ? "room_ready_to_leave" : "inventory_browse");
            }
            if (!TryProject(capture, bind: true, out PublishedDecision? decision) ||
                decision is null)
            {
                LatchUnsupported();
                return FixedUnsupported();
            }
            _published = decision;
            return decision.Observation;
        }
        catch
        {
            LatchUnsupported();
            return FixedUnsupported();
        }
        finally
        {
            _inside = false;
        }
    }

    private bool TryProject(
        ShopV1SurfaceCapture capture,
        bool bind,
        out PublishedDecision? decision)
    {
        decision = null;
        if (capture.Status != ShopV1SurfaceStatus.Available ||
            !ValidContext(capture) || capture.Gold < 0 ||
            capture.Deck.Count > ShopV1Constants.MaximumDeckCards ||
            capture.Offers.Count > ShopV1Constants.MaximumOffers ||
            !capture.RoomVisible || capture.ForegroundBlocked ||
            capture.MapOpen || capture.MapTraveling)
        {
            return false;
        }
        if (!BindOrMatch(capture, bind) || !ValidDeck(capture.Deck))
        {
            return false;
        }

        var publicOffers = new List<ShopV1Offer>(capture.Offers.Count);
        var legalActions = new List<string>(capture.Offers.Count + 1);
        var slots = new HashSet<int>();
        var slotRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var entryRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var controlRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var labelRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        var modelRefs = new HashSet<object>(ReferenceEqualityComparer.Instance);
        ShopV1NativeOffer? previous = null;

        foreach (ShopV1NativeOffer offer in capture.Offers)
        {
            if (offer.Slot is < 0 or >= ShopV1Constants.MaximumOffers ||
                previous is not null && offer.Slot <= previous.Slot ||
                !slots.Add(offer.Slot) || !RoomFlowIdentity.IsStableKey(offer.StableKey) ||
                offer.DisplayedPrice < 0 || !offer.Visible ||
                offer.SlotIdentity is null || offer.EntryIdentity is null ||
                offer.ControlIdentity is null || offer.LabelIdentity is null ||
                !slotRefs.Add(offer.SlotIdentity) || !entryRefs.Add(offer.EntryIdentity) ||
                !controlRefs.Add(offer.ControlIdentity) || !labelRefs.Add(offer.LabelIdentity))
            {
                return false;
            }

            bool supported = offer.Kind == ShopV1OfferKind.Card && offer.Stocked &&
                offer.OfferedModelIdentity is not null && offer.PurchaseDispatch is not null;
            if (offer.Kind == ShopV1OfferKind.Card)
            {
                if (offer.OfferedModelIdentity is null || offer.PurchaseDispatch is null ||
                    !modelRefs.Add(offer.OfferedModelIdentity) ||
                    ContainsIdentity(capture.Deck, offer.OfferedModelIdentity))
                {
                    return false;
                }
            }
            else if (offer.OfferedModelIdentity is not null || offer.PurchaseDispatch is not null)
            {
                return false;
            }

            bool affordable = capture.Gold >= offer.DisplayedPrice;
            string kind = KindName(offer.Kind);
            publicOffers.Add(new ShopV1Offer(
                offer.Slot, kind, offer.StableKey, offer.DisplayedPrice,
                affordable, offer.Enabled, supported));
            if (!_closeReconciled && !_purchaseUsed && supported && affordable && offer.Enabled)
            {
                legalActions.Add(ShopV1CanonicalEncoder.PurchaseActionId(offer.Slot));
            }
            previous = offer;
        }

        string phase;
        if (!_closeReconciled)
        {
            if (!capture.InventoryOpen || !capture.InventoryVisible ||
                !ValidEnabledControl(capture.BackControl, requireDispatch: true))
            {
                return false;
            }
            phase = "inventory_browse";
            legalActions.Add("inventory:close");
        }
        else
        {
            if (capture.InventoryOpen ||
                !ValidEnabledControl(capture.MerchantControl, requireDispatch: false) ||
                !ValidEnabledControl(capture.ProceedControl, requireDispatch: true))
            {
                return false;
            }
            phase = "room_ready_to_leave";
            publicOffers.Clear();
            legalActions.Add("leave");
        }

        var player = new ShopV1Player(capture.Gold, capture.Deck.Count);
        string decisionId = ShopV1CanonicalEncoder.ComputeDecisionId(
            _sessionNonce, phase, player, publicOffers, legalActions, _priorResult);
        var observation = new ShopV1Observation(
            _sessionNonce, "ready", phase, decisionId, player,
            publicOffers, legalActions, _priorResult);
        decision = new PublishedDecision(observation, capture);
        return true;
    }

    private PendingAction? BuildPending(
        PublishedDecision current,
        string decisionId,
        string actionId)
    {
        ShopV1SurfaceCapture capture = current.Capture;
        ShopV1ActionKind kind;
        ShopV1NativeOffer? target = null;
        ShopV1NativeControl? control = null;
        int targetSlot = -1;
        object? targetSlotIdentity = null;
        object? targetEntryIdentity = null;
        object? targetModelIdentity = null;
        string targetKey = string.Empty;
        int price = 0;
        IShopV1NativeDispatch? purchaseDispatch = null;

        if (ShopV1CanonicalEncoder.TryParsePurchaseAction(actionId, out int slot))
        {
            target = current.FindOffer(slot);
            if (_purchaseUsed || _closeReconciled || target is null ||
                target.Kind != ShopV1OfferKind.Card || !target.Stocked ||
                !target.Visible || !target.Enabled || target.PurchaseDispatch is null ||
                target.OfferedModelIdentity is null || capture.Gold < target.DisplayedPrice)
            {
                return null;
            }
            kind = ShopV1ActionKind.PurchaseCard;
            targetSlot = target.Slot;
            targetSlotIdentity = target.SlotIdentity;
            targetEntryIdentity = target.EntryIdentity;
            targetModelIdentity = target.OfferedModelIdentity;
            targetKey = target.StableKey;
            price = target.DisplayedPrice;
            purchaseDispatch = target.PurchaseDispatch;
        }
        else if (string.Equals(actionId, "inventory:close", StringComparison.Ordinal))
        {
            if (_closeReconciled || !capture.InventoryOpen ||
                !ValidEnabledControl(capture.BackControl, requireDispatch: true))
            {
                return null;
            }
            kind = ShopV1ActionKind.CloseInventory;
            control = capture.BackControl;
        }
        else if (string.Equals(actionId, "leave", StringComparison.Ordinal))
        {
            if (!_closeReconciled || capture.InventoryOpen ||
                !ValidEnabledControl(capture.ProceedControl, requireDispatch: true))
            {
                return null;
            }
            kind = ShopV1ActionKind.Leave;
            control = capture.ProceedControl;
        }
        else
        {
            return null;
        }

        var probe = new ShopV1PendingProbe(
            kind, capture.RunIdentity!, capture.RoomIdentity!,
            capture.InventoryNodeIdentity!, capture.InventoryModelIdentity!,
            capture.PlayerIdentity!, capture.MapIdentity!, decisionId, actionId,
            capture.Gold, capture.Deck, targetSlot, targetSlotIdentity,
            targetEntryIdentity, targetModelIdentity, targetKey, price,
            purchaseDispatch);
        return new PendingAction(probe, control);
    }

    private void Dispatch(PendingAction pending)
    {
        if (pending.Probe.Kind == ShopV1ActionKind.PurchaseCard)
        {
            pending.Probe.PurchaseDispatch!.Invoke();
        }
        else
        {
            pending.Control!.Dispatch!();
        }
    }

    private IRoomFlowReadValue Reconcile()
    {
        PendingAction pending = _pending!;
        ShopV1PendingCapture capture;
        try
        {
            _inside = true;
            capture = _adapter.CapturePending(pending.Probe);
            if (capture is null || _disposed || _interfered)
            {
                LatchUnsupported();
                return FixedUnsupported();
            }
        }
        catch
        {
            LatchUnsupported();
            return FixedUnsupported();
        }
        finally
        {
            _inside = false;
        }

        _pendingReads++;
        if (capture.Status == ShopV1SurfaceStatus.Missing)
        {
            return PendingOrTimeout();
        }
        if (capture.Status != ShopV1SurfaceStatus.Available ||
            !SameContext(capture, pending.Probe) || capture.Gold < 0 ||
            capture.Deck.Count > ShopV1Constants.MaximumDeckCards ||
            !ValidDeck(capture.Deck) ||
            pending.Probe.Kind != ShopV1ActionKind.Leave && !capture.RoomVisible)
        {
            LatchUnsupported();
            return FixedUnsupported();
        }

        return pending.Probe.Kind switch
        {
            ShopV1ActionKind.PurchaseCard => ReconcilePurchase(pending, capture),
            ShopV1ActionKind.CloseInventory => ReconcileClose(pending, capture),
            ShopV1ActionKind.Leave => ReconcileLeave(pending, capture),
            _ => FailUnsupported(),
        };
    }

    private IRoomFlowReadValue ReconcilePurchase(
        PendingAction pending,
        ShopV1PendingCapture capture)
    {
        ShopV1PendingProbe probe = pending.Probe;
        if (!capture.InventoryOpen || !capture.InventoryVisible ||
            capture.ForegroundBlocked || capture.MapOpen ||
            capture.MapTraveling ||
            !capture.TargetPresent ||
            !ReferenceEquals(capture.TargetSlotIdentity, probe.TargetSlotIdentity) ||
            !ReferenceEquals(capture.TargetEntryIdentity, probe.TargetEntryIdentity))
        {
            return FailUnsupported();
        }
        if (capture.Completion is ShopV1Completion.Failed or ShopV1Completion.Invalid)
        {
            return FailUnsupported();
        }

        bool deckSame = SameDeck(probe.BeforeDeck, capture.Deck);
        bool inserted = HasExactInsertion(
            probe.BeforeDeck, capture.Deck, probe.TargetModelIdentity!, probe.TargetKey);
        bool goldSame = capture.Gold == probe.BeforeGold;
        bool debitExact = (long)capture.Gold == (long)probe.BeforeGold - probe.DisplayedPrice;
        bool targetSame = capture.TargetStocked &&
            ReferenceEquals(capture.TargetModelIdentity, probe.TargetModelIdentity);
        bool targetCleared = !capture.TargetStocked && capture.TargetModelIdentity is null;

        if ((!deckSame && !inserted) || (!goldSame && !debitExact) ||
            (!targetSame && !targetCleared))
        {
            return FailUnsupported();
        }

        if (capture.Completion == ShopV1Completion.Succeeded)
        {
            if (!inserted || !debitExact || !targetCleared)
            {
                return FailUnsupported();
            }
            return Resolve(pending, capture, "purchase_card");
        }
        return PendingOrTimeout();
    }

    private IRoomFlowReadValue ReconcileClose(
        PendingAction pending,
        ShopV1PendingCapture capture)
    {
        if (!SameDeck(pending.Probe.BeforeDeck, capture.Deck) ||
            capture.Gold != pending.Probe.BeforeGold ||
            capture.MapOpen || capture.MapTraveling)
        {
            return FailUnsupported();
        }
        if (capture.InventoryOpen)
        {
            return capture.ForegroundBlocked
                ? FailUnsupported() : PendingOrTimeout();
        }
        if (capture.ForegroundBlocked ||
            !ValidEnabledControl(capture.MerchantControl, requireDispatch: false) ||
            !ValidEnabledControl(capture.ProceedControl, requireDispatch: true))
        {
            return PendingOrTimeout();
        }
        _closeReconciled = true;
        return Resolve(pending, capture, "inventory_close");
    }

    private IRoomFlowReadValue ReconcileLeave(
        PendingAction pending,
        ShopV1PendingCapture capture)
    {
        if (!SameDeck(pending.Probe.BeforeDeck, capture.Deck) ||
            capture.Gold != pending.Probe.BeforeGold || capture.InventoryOpen)
        {
            return FailUnsupported();
        }
        if (capture.ForegroundBlocked)
        {
            return FailUnsupported();
        }
        if (capture.MapOpen && capture.MapTravelEnabled && !capture.MapTraveling)
        {
            return Resolve(pending, capture, "leave");
        }
        if (!capture.MapOpen && !capture.MapTravelEnabled && !capture.MapTraveling)
        {
            return PendingOrTimeout();
        }
        return FailUnsupported();
    }

    private IRoomFlowReadValue Resolve(
        PendingAction pending,
        ShopV1PendingCapture capture,
        string kind)
    {
        if (pending.Probe.PurchaseDispatch is not null)
        {
            bool wasInside = _inside;
            try
            {
                _inside = true;
                pending.Probe.PurchaseDispatch.Dispose();
                if (_disposed || _interfered)
                    throw new InvalidOperationException("Shop cleanup was interrupted.");
            }
            catch
            {
                _cleanupFailed = true;
                _unsupported = true;
                _pending = null;
                return FixedUnsupported();
            }
            finally
            {
                _inside = wasInside;
            }
        }
        _priorResult = new ShopV1ReconciledAction(
            _sessionNonce, pending.Probe.DecisionId, pending.Probe.ActionId, kind);
        _pending = null;
        _accepted = false;
        _pendingReads = 0;
        if (pending.Probe.Kind == ShopV1ActionKind.Leave)
        {
            _published = null;
            _completed = new ShopV1Observation(
                _sessionNonce, "complete", "complete", string.Empty,
                new ShopV1Player(capture.Gold, capture.Deck.Count),
                Array.Empty<ShopV1Offer>(), Array.Empty<string>(), _priorResult);
            return _completed;
        }
        return ObserveReadySurface();
    }

    private IRoomFlowReadValue PendingOrTimeout()
    {
        if (_pendingReads >= ShopV1Constants.MaximumPendingReads)
        {
            return FailUnsupported();
        }
        return FixedWaiting(PendingPhase());
    }

    private IRoomFlowReadValue FailUnsupported()
    {
        LatchUnsupported();
        return FixedUnsupported();
    }

    private void LatchUnsupported()
    {
        _unsupported = true;
        _published = null;
        ReleasePending();
    }

    private void LatchOffOwner()
    {
        _unsupported = true;
        _published = null;
    }

    private void ReleasePending()
    {
        IShopV1NativeDispatch? dispatch = _pending?.Probe.PurchaseDispatch;
        _pending = null;
        _accepted = false;
        if (dispatch is null) return;
        bool wasInside = _inside;
        try
        {
            _inside = true;
            dispatch.Dispose();
        }
        catch
        {
            _cleanupFailed = true;
        }
        finally
        {
            _inside = wasInside;
        }
    }

    private bool BindOrMatch(ShopV1SurfaceCapture capture, bool bind)
    {
        if (_boundRun is null)
        {
            if (!bind || _closeReconciled || !capture.InventoryOpen) return false;
            _boundRun = capture.RunIdentity;
            _boundRoom = capture.RoomIdentity;
            _boundInventoryNode = capture.InventoryNodeIdentity;
            _boundInventoryModel = capture.InventoryModelIdentity;
            _boundPlayer = capture.PlayerIdentity;
            _boundMap = capture.MapIdentity;
            return true;
        }
        return ReferenceEquals(_boundRun, capture.RunIdentity) &&
            ReferenceEquals(_boundRoom, capture.RoomIdentity) &&
            ReferenceEquals(_boundInventoryNode, capture.InventoryNodeIdentity) &&
            ReferenceEquals(_boundInventoryModel, capture.InventoryModelIdentity) &&
            ReferenceEquals(_boundPlayer, capture.PlayerIdentity) &&
            ReferenceEquals(_boundMap, capture.MapIdentity);
    }

    private static bool ValidContext(ShopV1SurfaceCapture capture) =>
        capture.RunIdentity is not null && capture.RoomIdentity is not null &&
        capture.InventoryNodeIdentity is not null && capture.InventoryModelIdentity is not null &&
        capture.PlayerIdentity is not null && capture.MapIdentity is not null;

    private static bool SameContext(
        ShopV1PendingCapture capture,
        ShopV1PendingProbe probe) =>
        ReferenceEquals(capture.RunIdentity, probe.RunIdentity) &&
        ReferenceEquals(capture.RoomIdentity, probe.RoomIdentity) &&
        ReferenceEquals(capture.InventoryNodeIdentity, probe.InventoryNodeIdentity) &&
        ReferenceEquals(capture.InventoryModelIdentity, probe.InventoryModelIdentity) &&
        ReferenceEquals(capture.PlayerIdentity, probe.PlayerIdentity) &&
        ReferenceEquals(capture.MapIdentity, probe.MapIdentity);

    private static bool ValidDeck(IReadOnlyList<ShopV1DeckCardBinding> deck)
    {
        foreach (ShopV1DeckCardBinding card in deck)
        {
            if (card is null || card.ModelIdentity is null ||
                !RoomFlowIdentity.IsStableKey(card.StableKey)) return false;
        }
        return true;
    }

    private static bool ContainsIdentity(
        IReadOnlyList<ShopV1DeckCardBinding> deck,
        object identity)
    {
        foreach (ShopV1DeckCardBinding card in deck)
            if (ReferenceEquals(card.ModelIdentity, identity)) return true;
        return false;
    }

    private static bool SameDeck(
        IReadOnlyList<ShopV1DeckCardBinding> left,
        IReadOnlyList<ShopV1DeckCardBinding> right)
    {
        if (left.Count != right.Count) return false;
        for (int index = 0; index < left.Count; index++)
        {
            if (!ReferenceEquals(left[index].ModelIdentity, right[index].ModelIdentity) ||
                !string.Equals(left[index].StableKey, right[index].StableKey,
                    StringComparison.Ordinal)) return false;
        }
        return true;
    }

    private static bool HasExactInsertion(
        IReadOnlyList<ShopV1DeckCardBinding> before,
        IReadOnlyList<ShopV1DeckCardBinding> after,
        object insertedIdentity,
        string insertedKey)
    {
        if (after.Count != before.Count + 1) return false;
        int beforeIndex = 0;
        int insertionCount = 0;
        for (int afterIndex = 0; afterIndex < after.Count; afterIndex++)
        {
            ShopV1DeckCardBinding card = after[afterIndex];
            if (ReferenceEquals(card.ModelIdentity, insertedIdentity) &&
                string.Equals(card.StableKey, insertedKey, StringComparison.Ordinal))
            {
                insertionCount++;
                continue;
            }
            if (beforeIndex >= before.Count ||
                !ReferenceEquals(card.ModelIdentity, before[beforeIndex].ModelIdentity) ||
                !string.Equals(card.StableKey, before[beforeIndex].StableKey,
                    StringComparison.Ordinal)) return false;
            beforeIndex++;
        }
        return insertionCount == 1 && beforeIndex == before.Count;
    }

    private static bool ValidEnabledControl(
        ShopV1NativeControl? control,
        bool requireDispatch) =>
        control is not null && control.Identity is not null &&
        control.Visible && control.Enabled &&
        (!requireDispatch || control.Dispatch is not null);

    private static string KindName(ShopV1OfferKind kind) => kind switch
    {
        ShopV1OfferKind.Card => "card",
        ShopV1OfferKind.Relic => "relic",
        ShopV1OfferKind.Potion => "potion",
        ShopV1OfferKind.Removal => "removal",
        ShopV1OfferKind.Unknown => "unknown",
        _ => throw new InvalidOperationException("Unknown shop offer kind."),
    };

    private static bool SamePublished(PublishedDecision left, PublishedDecision right)
    {
        ShopV1Observation a = left.Observation;
        ShopV1Observation b = right.Observation;
        if (!string.Equals(a.DecisionId, b.DecisionId, StringComparison.Ordinal) ||
            !string.Equals(a.Phase, b.Phase, StringComparison.Ordinal) ||
            a.Player.Gold != b.Player.Gold || a.Player.DeckCount != b.Player.DeckCount ||
            a.Offers.Count != b.Offers.Count || a.LegalActions.Count != b.LegalActions.Count ||
            !SameSurfaceIdentity(left.Capture, right.Capture)) return false;
        for (int i = 0; i < a.LegalActions.Count; i++)
            if (!string.Equals(a.LegalActions[i], b.LegalActions[i], StringComparison.Ordinal)) return false;
        for (int i = 0; i < a.Offers.Count; i++)
        {
            ShopV1Offer x = a.Offers[i];
            ShopV1Offer y = b.Offers[i];
            if (x.Slot != y.Slot || x.DisplayedPrice != y.DisplayedPrice ||
                x.Affordable != y.Affordable || x.Enabled != y.Enabled ||
                x.Supported != y.Supported ||
                !string.Equals(x.Kind, y.Kind, StringComparison.Ordinal) ||
                !string.Equals(x.Key, y.Key, StringComparison.Ordinal)) return false;
        }
        return SameDeck(left.Capture.Deck, right.Capture.Deck);
    }

    private static bool SameSurfaceIdentity(ShopV1SurfaceCapture a, ShopV1SurfaceCapture b)
    {
        if (!ReferenceEquals(a.RunIdentity, b.RunIdentity) ||
            !ReferenceEquals(a.RoomIdentity, b.RoomIdentity) ||
            !ReferenceEquals(a.InventoryNodeIdentity, b.InventoryNodeIdentity) ||
            !ReferenceEquals(a.InventoryModelIdentity, b.InventoryModelIdentity) ||
            !ReferenceEquals(a.PlayerIdentity, b.PlayerIdentity) ||
            !ReferenceEquals(a.MapIdentity, b.MapIdentity) ||
            !SameControl(a.BackControl, b.BackControl) ||
            !SameControl(a.MerchantControl, b.MerchantControl) ||
            !SameControl(a.ProceedControl, b.ProceedControl) ||
            a.Offers.Count != b.Offers.Count) return false;
        for (int i = 0; i < a.Offers.Count; i++)
        {
            ShopV1NativeOffer x = a.Offers[i];
            ShopV1NativeOffer y = b.Offers[i];
            if (!ReferenceEquals(x.SlotIdentity, y.SlotIdentity) ||
                !ReferenceEquals(x.EntryIdentity, y.EntryIdentity) ||
                !ReferenceEquals(x.OfferedModelIdentity, y.OfferedModelIdentity) ||
                !ReferenceEquals(x.ControlIdentity, y.ControlIdentity) ||
                !ReferenceEquals(x.LabelIdentity, y.LabelIdentity)) return false;
        }
        return true;
    }

    private static bool SameControl(ShopV1NativeControl? a, ShopV1NativeControl? b) =>
        a is null && b is null || a is not null && b is not null &&
        ReferenceEquals(a.Identity, b.Identity) && a.Visible == b.Visible && a.Enabled == b.Enabled;

    private string PendingPhase() => _pending?.Probe.Kind switch
    {
        ShopV1ActionKind.PurchaseCard => "purchase_waiting",
        ShopV1ActionKind.CloseInventory => "close_waiting",
        ShopV1ActionKind.Leave => "leave_waiting",
        _ => "unknown",
    };

    private ShopV1Observation FixedWaiting(string phase) =>
        ShopV1Observation.Fixed(_sessionNonce, "waiting", phase, _priorResult);

    private ShopV1Observation FixedUnsupported() =>
        ShopV1Observation.Fixed(_sessionNonce, "unsupported", "unknown", _priorResult);

    private RoomFlowApplyFailure Failure(string outcome) =>
        new(FlowKind, _sessionNonce, outcome);

    private sealed class PublishedDecision
    {
        internal PublishedDecision(ShopV1Observation observation, ShopV1SurfaceCapture capture)
        {
            Observation = observation;
            Capture = capture;
        }

        internal ShopV1Observation Observation { get; }
        internal ShopV1SurfaceCapture Capture { get; }

        internal bool HasAction(string actionId)
        {
            foreach (string legal in Observation.LegalActions)
                if (string.Equals(legal, actionId, StringComparison.Ordinal)) return true;
            return false;
        }

        internal ShopV1NativeOffer? FindOffer(int slot)
        {
            foreach (ShopV1NativeOffer offer in Capture.Offers)
                if (offer.Slot == slot) return offer;
            return null;
        }
    }

    private sealed class PendingAction
    {
        internal PendingAction(ShopV1PendingProbe probe, ShopV1NativeControl? control)
        {
            Probe = probe;
            Control = control;
        }

        internal ShopV1PendingProbe Probe { get; }
        internal ShopV1NativeControl? Control { get; }
    }
}
