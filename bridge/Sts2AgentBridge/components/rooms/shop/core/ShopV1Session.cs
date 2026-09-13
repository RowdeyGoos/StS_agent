using System;
using Sts2AgentBridge.Successors.ItemV1;
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
    private int _purchases, _discards;
    private readonly HashSet<int> _discardedSlots = new();
    private readonly HashSet<object> _originalPotions = new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _purchasedEntries = new(ReferenceEqualityComparer.Instance);
    private readonly Dictionary<object,ShopV1RestockWitness> _restocked = new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<object> _purchasedModels = new(ReferenceEqualityComparer.Instance);
    private bool AvailableGeneration(ShopV1NativeOffer offer) => !_purchasedEntries.Contains(offer.EntryIdentity) ||
        _restocked.TryGetValue(offer.EntryIdentity,out var witness) && ReferenceEquals(offer.StockModelIdentity,witness.ModelIdentity) &&
        offer.StableKey==witness.StableKey && offer.DisplayedPrice==witness.Price;
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
            if (pending.Probe.Kind is ShopV1ActionKind.PurchaseCard or ShopV1ActionKind.PurchasePotion or ShopV1ActionKind.PurchaseRelic or ShopV1ActionKind.RemoveCard)
            {
                _purchases++;
                _purchasedEntries.Add(pending.Probe.TargetEntryIdentity!);
                _restocked.Remove(pending.Probe.TargetEntryIdentity!);
                if(pending.Probe.TargetModelIdentity is {} purchasedModel)_purchasedModels.Add(purchasedModel);
            }

            if(pending.Probe.Kind==ShopV1ActionKind.DiscardPotion){_discards++;_discardedSlots.Add(pending.Probe.TargetSlot);}
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
        if (!BindOrMatch(capture, bind) || !ValidDeck(capture.Deck) || !ValidPotions(capture.PotionSlots) || !ValidRelics(capture.Relics))
        {
            return false;
        }

        var publicOffers = new List<ShopV1Offer>(capture.Offers.Count);
        var legalActions = new List<string>(capture.Offers.Count + 1);
        var removalCandidates = new List<ShopV1RemovalCandidate>();
        ShopV1NativeOffer? removalOffer=null;
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
                !controlRefs.Add(offer.ControlIdentity) || !labelRefs.Add(offer.LabelIdentity) ||
                !AvailableGeneration(offer))
            {
                return false;
            }

            if (offer.Kind == ShopV1OfferKind.Removal) { if (removalOffer is not null) return false; removalOffer=offer; }
            bool removalSupported=offer.Kind==ShopV1OfferKind.Removal && offer.Stocked && offer.PurchaseDispatch is IShopV1RemovalDispatch && offer.OfferedModelIdentity is null;
            bool supported = removalSupported || (offer.Kind is ShopV1OfferKind.Card or ShopV1OfferKind.Potion or ShopV1OfferKind.Relic) && offer.Stocked &&
                offer.OfferedModelIdentity is not null && offer.PurchaseDispatch is not null;
            if (offer.Kind == ShopV1OfferKind.Card || (offer.Kind is ShopV1OfferKind.Potion or ShopV1OfferKind.Relic) && (offer.OfferedModelIdentity is not null || offer.PurchaseDispatch is not null))
            {
                if (offer.OfferedModelIdentity is null || offer.PurchaseDispatch is null ||
                    !modelRefs.Add(offer.OfferedModelIdentity) || _purchasedModels.Contains(offer.OfferedModelIdentity) ||
                    ContainsIdentity(capture.Deck, offer.OfferedModelIdentity) ||
                    ContainsPotion(capture.PotionSlots, offer.OfferedModelIdentity) ||
                    ContainsRelic(capture.Relics, offer.OfferedModelIdentity))
                {
                    return false;
                }
            }
            else if (offer.OfferedModelIdentity is not null || offer.PurchaseDispatch is not null && !removalSupported)
            {
                return false;
            }

            if (offer.PotionCapacityGain != 0 && (offer.PotionCapacityGain != 2 || offer.Kind != ShopV1OfferKind.Relic || offer.StableKey != "POTION_BELT" || !supported)) return false;
            bool affordable = capture.Gold >= offer.DisplayedPrice;
            string kind = KindName(offer.Kind);
            publicOffers.Add(new ShopV1Offer(
                offer.Slot, kind, offer.StableKey, offer.DisplayedPrice,
                affordable, offer.Enabled, supported, offer.PotionCapacityGain));
            if (!_closeReconciled && _purchases < ShopV1Constants.MaximumPurchases && supported && !removalSupported && affordable && offer.Enabled &&
                (offer.Kind != ShopV1OfferKind.Potion || HasPotionSpace(capture.PotionSlots)) &&
                (offer.Kind != ShopV1OfferKind.Relic || RelicLegal(capture, offer)))
            {
                legalActions.Add(ShopV1CanonicalEncoder.PurchaseActionId(offer.Slot, offer.Kind));
            }
            previous = offer;
        }

        if(!_closeReconciled)foreach(var retained in _restocked) {
            bool seen=false;foreach(var offer in capture.Offers)if(ReferenceEquals(offer.EntryIdentity,retained.Key)&&AvailableGeneration(offer))seen=true;
            if(!seen)return false;
        }
        if (removalOffer?.PurchaseDispatch is IShopV1RemovalDispatch && removalOffer.Stocked) {
            for(int i=0;i<capture.Deck.Count;i++) if(capture.Deck[i].Removable)
                removalCandidates.Add(new(i,capture.Deck[i].StableKey,capture.Deck[i].UpgradeLevel));
            if(removalCandidates.Count>64) return false;
            if(!_closeReconciled && _purchases<ShopV1Constants.MaximumPurchases && removalOffer.Enabled && capture.Gold>=removalOffer.DisplayedPrice)
                foreach(var card in removalCandidates)legalActions.Add("remove:"+card.DeckSlot.ToString(System.Globalization.CultureInfo.InvariantCulture));
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
            int previousDiscard=-1;
        foreach(var discard in capture.Discards) {
            if(discard.Slot<=previousDiscard || discard.Slot>=capture.PotionSlots.Count || discard.Slot<0 || discard.Dispatch is null ||
                capture.PotionSlots[discard.Slot].ModelIdentity is null || HasPotionSpace(capture.PotionSlots))return false;
            previousDiscard=discard.Slot;
            if(_purchases<ShopV1Constants.MaximumPurchases && !_discardedSlots.Contains(discard.Slot) && _discards<8 && _originalPotions.Contains(capture.PotionSlots[discard.Slot].ModelIdentity!))
                legalActions.Add("discard:"+discard.Slot.ToString(System.Globalization.CultureInfo.InvariantCulture));
        }
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
            removalCandidates.Clear();
            legalActions.Add("leave");
        }

        var player = new ShopV1Player(capture.Gold, capture.Deck.Count, PotionKeys(capture.PotionSlots), RelicKeys(capture.Relics));
        string decisionId = ShopV1CanonicalEncoder.ComputeDecisionId(
            _sessionNonce, phase, player, publicOffers, legalActions, _priorResult, removalCandidates);
        var observation = new ShopV1Observation(
            _sessionNonce, "ready", phase, decisionId, player,
            publicOffers, legalActions, _priorResult, removalCandidates);
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

        if(actionId.StartsWith("discard:",StringComparison.Ordinal) && RoomFlowIdentity.IsActionId("shop",actionId)) {
            int index=actionId[^1]-'0';
            if(_discards>=8 || _discardedSlots.Contains(index) || _purchases>=ShopV1Constants.MaximumPurchases || !capture.InventoryOpen || HasPotionSpace(capture.PotionSlots))return null;
            foreach(var discard in capture.Discards)if(discard.Slot==index)purchaseDispatch=discard.Dispatch;
            if(purchaseDispatch is null)return null;
            kind=ShopV1ActionKind.DiscardPotion;targetSlot=index;targetModelIdentity=capture.PotionSlots[index].ModelIdentity;targetKey=capture.PotionSlots[index].StableKey!;
        }
        else if (actionId.StartsWith("remove:", StringComparison.Ordinal) && RoomFlowIdentity.IsActionId("shop",actionId))
        {
            int deckSlot=int.Parse(actionId.AsSpan(7),System.Globalization.CultureInfo.InvariantCulture);
            foreach(var offer in capture.Offers) if(offer.Kind==ShopV1OfferKind.Removal) { if(target is not null)return null; target=offer; }
            if(target is null || target.PurchaseDispatch is not IShopV1RemovalDispatch || !target.Stocked || !target.Visible || !target.Enabled ||
                _purchases>=ShopV1Constants.MaximumPurchases || _closeReconciled || !AvailableGeneration(target) ||
                capture.Gold<target.DisplayedPrice || deckSlot>=capture.Deck.Count || !capture.Deck[deckSlot].Removable) return null;
            kind=ShopV1ActionKind.RemoveCard;targetSlot=target.Slot;targetSlotIdentity=target.SlotIdentity;targetEntryIdentity=target.EntryIdentity;
            targetModelIdentity=capture.Deck[deckSlot].ModelIdentity;targetKey=capture.Deck[deckSlot].StableKey;price=target.DisplayedPrice;
            purchaseDispatch=target.PurchaseDispatch;
        }
        else if (ShopV1CanonicalEncoder.TryParsePurchaseAction(actionId, out int slot))
        {
            target = current.FindOffer(slot);
            if (_purchases >= ShopV1Constants.MaximumPurchases || _closeReconciled || target is null || !AvailableGeneration(target) ||
                (target.Kind is not (ShopV1OfferKind.Card or ShopV1OfferKind.Potion or ShopV1OfferKind.Relic)) ||
                actionId != ShopV1CanonicalEncoder.PurchaseActionId(slot, target.Kind) ||
                target.Kind == ShopV1OfferKind.Potion && !HasPotionSpace(capture.PotionSlots) ||
                target.Kind == ShopV1OfferKind.Relic && !RelicLegal(capture, target) || !target.Stocked ||
                !target.Visible || !target.Enabled || target.PurchaseDispatch is null ||
                target.OfferedModelIdentity is null || capture.Gold < target.DisplayedPrice)
            {
                return null;
            }
            kind = target.Kind == ShopV1OfferKind.Potion ? ShopV1ActionKind.PurchasePotion : target.Kind == ShopV1OfferKind.Relic ? ShopV1ActionKind.PurchaseRelic : ShopV1ActionKind.PurchaseCard;
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
            purchaseDispatch, capture.PotionSlots, capture.Relics, target?.PotionCapacityGain ?? 0);
        return new PendingAction(probe, control);
    }

    private void Dispatch(PendingAction pending)
    {
        if (pending.Probe.PurchaseDispatch is not null)
        {
            if(pending.Probe.Kind==ShopV1ActionKind.RemoveCard) {
                ShopV1DeckCardBinding? card=null;foreach(var c in pending.Probe.BeforeDeck)if(ReferenceEquals(c.ModelIdentity,pending.Probe.TargetModelIdentity))card=c;
                ((IShopV1RemovalDispatch)pending.Probe.PurchaseDispatch!).SelectTarget(card!);
            }
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
            !ValidDeck(capture.Deck) || !ValidPotions(capture.PotionSlots) || !ValidRelics(capture.Relics) ||
            pending.Probe.Kind != ShopV1ActionKind.Leave && !capture.RoomVisible)
        {
            LatchUnsupported();
            return FixedUnsupported();
        }

        return pending.Probe.Kind switch
        {
            ShopV1ActionKind.PurchaseCard or ShopV1ActionKind.PurchasePotion or ShopV1ActionKind.PurchaseRelic or ShopV1ActionKind.RemoveCard => ReconcilePurchase(pending, capture),
            ShopV1ActionKind.DiscardPotion => ReconcileDiscard(pending,capture),
            ShopV1ActionKind.CloseInventory => ReconcileClose(pending, capture),
            ShopV1ActionKind.Leave => ReconcileLeave(pending, capture),
            _ => FailUnsupported(),
        };
    }

    private IRoomFlowReadValue ReconcileDiscard(PendingAction pending,ShopV1PendingCapture capture) {
        var probe=pending.Probe;
        if(!capture.InventoryOpen||!capture.InventoryVisible||capture.ForegroundBlocked||capture.MapOpen||capture.MapTraveling||
            capture.Gold!=probe.BeforeGold||!SameDeck(probe.BeforeDeck,capture.Deck)||!SameRelics(probe.BeforeRelics,capture.Relics)||
            capture.PotionSlots.Count!=probe.BeforePotions.Count||capture.Completion is ShopV1Completion.Failed or ShopV1Completion.Invalid)return FailUnsupported();
        bool removed=capture.PotionSlots[probe.TargetSlot].ModelIdentity is null;
        for(int i=0;i<capture.PotionSlots.Count;i++) {
            var before=probe.BeforePotions[i];var after=capture.PotionSlots[i];
            if(i==probe.TargetSlot&&removed){if(after.StableKey is not null)return FailUnsupported();}
            else if(!ReferenceEquals(before.ModelIdentity,after.ModelIdentity)||before.StableKey!=after.StableKey)return FailUnsupported();
        }
        if(capture.Completion==ShopV1Completion.Succeeded)return removed?Resolve(pending,capture,"discard_potion"):FailUnsupported();
        return PendingOrTimeout();
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

        if(probe.Kind==ShopV1ActionKind.RemoveCard) {
            bool same=SameDeck(probe.BeforeDeck,capture.Deck), removed=ExactRemoval(probe.BeforeDeck,capture.Deck,probe.TargetModelIdentity!);
            bool paid=(long)capture.Gold==(long)probe.BeforeGold-probe.DisplayedPrice;
            if(!SamePotions(probe.BeforePotions,capture.PotionSlots)||!SameRelics(probe.BeforeRelics,capture.Relics)||
                (!same&&!removed)||capture.Gold!=probe.BeforeGold&&!paid||capture.TargetModelIdentity is not null||
                removed&&!paid||!capture.TargetStocked&&(!removed||!paid))return FailUnsupported();
            if(capture.Completion==ShopV1Completion.Succeeded)
                return removed&&paid&&!capture.TargetStocked?Resolve(pending,capture,"remove_card"):FailUnsupported();
            return PendingOrTimeout();
        }
        bool potionPurchase = probe.Kind == ShopV1ActionKind.PurchasePotion;
        bool relicPurchase = probe.Kind == ShopV1ActionKind.PurchaseRelic;
        bool deckSame = SameDeck(probe.BeforeDeck, capture.Deck);
        bool pickupDeck = probe.PurchaseDispatch is IShopV1PickupDispatch pickup && pickup.DeckMatches(capture.Deck,capture.Completion==ShopV1Completion.Succeeded);
        bool potionsSame = SamePotions(probe.BeforePotions, capture.PotionSlots);
        bool relicsSame = SameRelics(probe.BeforeRelics, capture.Relics);
        bool capacityExact = PotionCapacityExact(probe.BeforePotions, capture.PotionSlots, probe.PotionCapacityGain);
        if (relicPurchase ? (!deckSame && !pickupDeck) || (!potionsSame && !capacityExact)
            : !relicsSame || (potionPurchase ? !deckSame : !potionsSame)) return FailUnsupported();
        bool inventorySame = relicPurchase ? relicsSame : potionPurchase ? potionsSame : deckSame;
        bool inserted = relicPurchase
            ? ExactRelicInsertion(probe.BeforeRelics, capture.Relics, probe.TargetModelIdentity!, probe.TargetKey)
            : potionPurchase
                ? HasExactPotionInsertion(probe.BeforePotions, capture.PotionSlots, probe.TargetModelIdentity!, probe.TargetKey)
                : HasExactInsertion(probe.BeforeDeck, capture.Deck, probe.TargetModelIdentity!, probe.TargetKey);
        bool goldSame = capture.Gold == probe.BeforeGold;
        bool debitExact = (long)capture.Gold == (long)probe.BeforeGold - probe.DisplayedPrice;
        if (relicPurchase && (inserted && !debitExact || !potionsSame && !inserted)) return FailUnsupported();
        bool targetSame = capture.TargetStocked &&
            ReferenceEquals(capture.TargetModelIdentity, probe.TargetModelIdentity);
        bool targetCleared = !capture.TargetStocked && capture.TargetModelIdentity is null;
        bool targetRefilled = capture.TargetStocked && capture.TargetModelIdentity is {} refill &&
            !_purchasedModels.Contains(refill) && !ContainsIdentity(capture.Deck,refill) &&
            !ContainsPotion(capture.PotionSlots,refill) && !ContainsRelic(capture.Relics,refill);
        var witness=(probe.PurchaseDispatch as IShopV1RestockDispatch)?.Restocked;
        bool restockCertified=targetRefilled && witness is not null && ReferenceEquals(witness.ModelIdentity,capture.TargetModelIdentity) &&
            RoomFlowIdentity.IsStableKey(witness.StableKey) && witness.Price>=0;
        if(targetRefilled && (!inserted || !debitExact || relicPurchase && !capacityExact))return FailUnsupported();

        if (relicPurchase && targetCleared && (!inserted || !debitExact || !capacityExact)) return FailUnsupported();

        if ((!inventorySame && !inserted) || (!goldSame && !debitExact) ||
            (!targetSame && !targetCleared && !targetRefilled))
        {
            return FailUnsupported();
        }

        if (capture.Completion == ShopV1Completion.Succeeded)
        {
            if (!inserted || !debitExact || (!(targetCleared && witness is null) && !restockCertified) || relicPurchase && !capacityExact)
            {
                return FailUnsupported();
            }
            if(restockCertified)_restocked[probe.TargetEntryIdentity!]=witness!;
            return Resolve(pending, capture, relicPurchase ? "purchase_relic" : potionPurchase ? "purchase_potion" : "purchase_card");
        }
        return PendingOrTimeout();
    }

    private IRoomFlowReadValue ReconcileClose(
        PendingAction pending,
        ShopV1PendingCapture capture)
    {
        if (!SameDeck(pending.Probe.BeforeDeck, capture.Deck) ||
            !SamePotions(pending.Probe.BeforePotions, capture.PotionSlots) ||
            !SameRelics(pending.Probe.BeforeRelics, capture.Relics) ||
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
            !SamePotions(pending.Probe.BeforePotions, capture.PotionSlots) ||
            !SameRelics(pending.Probe.BeforeRelics, capture.Relics) ||
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
                new ShopV1Player(capture.Gold, capture.Deck.Count, PotionKeys(capture.PotionSlots), RelicKeys(capture.Relics)),
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
        if(_pending?.Probe.PurchaseDispatch is IShopV1AbortableDispatch abortable)abortable.Abort();
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
            foreach(var potion in capture.PotionSlots)if(potion.ModelIdentity is {} model)_originalPotions.Add(model);
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

    private static bool ValidRelics(IReadOnlyList<ShopV1RelicBinding> relics)
    {
        if (relics.Count > ShopV1Constants.MaximumRelics) return false;
        var models = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (var relic in relics)
            if (relic is null || relic.ModelIdentity is null || !RoomFlowIdentity.IsStableKey(relic.StableKey) || !models.Add(relic.ModelIdentity)) return false;
        return true;
    }
    private static bool ContainsRelic(IReadOnlyList<ShopV1RelicBinding> relics, object model)
    { foreach (var relic in relics) if (ReferenceEquals(relic.ModelIdentity, model)) return true; return false; }
    private static string[] RelicKeys(IReadOnlyList<ShopV1RelicBinding> relics)
    { var keys = new string[relics.Count]; for (int i=0;i<keys.Length;i++) keys[i]=relics[i].StableKey; return keys; }
    private static bool SameRelics(IReadOnlyList<ShopV1RelicBinding> before, IReadOnlyList<ShopV1RelicBinding> after)
    {
        if (before.Count != after.Count) return false;
        for (int i=0;i<before.Count;i++) if (!ReferenceEquals(before[i].ModelIdentity,after[i].ModelIdentity) || before[i].StableKey!=after[i].StableKey) return false;
        return true;
    }
    private static bool ExactRelicInsertion(IReadOnlyList<ShopV1RelicBinding> before, IReadOnlyList<ShopV1RelicBinding> after, object model, string key)
    {
        if (after.Count != before.Count+1) return false;
        for (int i=0;i<before.Count;i++) if (!ReferenceEquals(before[i].ModelIdentity,after[i].ModelIdentity) || before[i].StableKey!=after[i].StableKey) return false;
        return ReferenceEquals(after[before.Count].ModelIdentity,model) && after[before.Count].StableKey==key;
    }
    private static bool RelicLegal(ShopV1SurfaceCapture capture, ShopV1NativeOffer offer)
    {
        if (capture.Relics.Count >= ShopV1Constants.MaximumRelics || capture.PotionSlots.Count+offer.PotionCapacityGain>ItemV1Constants.MaximumPotionSlots) return false;
        foreach (var relic in capture.Relics) if (relic.StableKey==offer.StableKey) return false;
        return true;
    }
    private static bool PotionCapacityExact(IReadOnlyList<ItemV1PotionSlotBinding> before, IReadOnlyList<ItemV1PotionSlotBinding> after, int gain)
    {
        if (after.Count != before.Count+gain) return false;
        for (int i=0;i<before.Count;i++) if (!ReferenceEquals(before[i].ModelIdentity,after[i].ModelIdentity) || before[i].StableKey!=after[i].StableKey) return false;
        for (int i=before.Count;i<after.Count;i++) if (after[i].ModelIdentity is not null || after[i].StableKey is not null) return false;
        return true;
    }

    private static bool ValidPotions(IReadOnlyList<ItemV1PotionSlotBinding> slots)
    {
        if (slots.Count > ItemV1Constants.MaximumPotionSlots) return false;
        var models = new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (var slot in slots)
            if (slot is null || (slot.ModelIdentity is null ? slot.StableKey is not null :
                !RoomFlowIdentity.IsStableKey(slot.StableKey) || !models.Add(slot.ModelIdentity))) return false;
        return true;
    }
    private static bool ContainsPotion(IReadOnlyList<ItemV1PotionSlotBinding> slots, object identity)
    { foreach (var slot in slots) if (ReferenceEquals(slot.ModelIdentity, identity)) return true; return false; }
    private static bool HasPotionSpace(IReadOnlyList<ItemV1PotionSlotBinding> slots)
    { foreach (var slot in slots) if (slot.ModelIdentity is null) return true; return false; }
    private static string?[] PotionKeys(IReadOnlyList<ItemV1PotionSlotBinding> slots)
    { var keys = new string?[slots.Count]; for (int i=0;i<slots.Count;i++) keys[i]=slots[i].StableKey; return keys; }
    private static bool SamePotions(IReadOnlyList<ItemV1PotionSlotBinding> before, IReadOnlyList<ItemV1PotionSlotBinding> after)
    {
        if (before.Count != after.Count) return false;
        for (int i=0;i<before.Count;i++)
            if (!ReferenceEquals(before[i].ModelIdentity,after[i].ModelIdentity) || before[i].StableKey!=after[i].StableKey) return false;
        return true;
    }
    private static bool HasExactPotionInsertion(IReadOnlyList<ItemV1PotionSlotBinding> before,
        IReadOnlyList<ItemV1PotionSlotBinding> after, object model, string key)
    {
        if (before.Count != after.Count) return false;
        int inserted=0;
        int firstEmpty=-1;
        for (int i=0;i<before.Count;i++) if (before[i].ModelIdentity is null) { firstEmpty=i; break; }
        for (int i=0;i<before.Count;i++) {
            if (i==firstEmpty && ReferenceEquals(after[i].ModelIdentity,model) && after[i].StableKey==key) inserted++;
            else if (!ReferenceEquals(before[i].ModelIdentity,after[i].ModelIdentity) || before[i].StableKey!=after[i].StableKey) return false;
        }
        return inserted==1;
    }

    private static bool ValidDeck(IReadOnlyList<ShopV1DeckCardBinding> deck)
    {
        var identities=new HashSet<object>(ReferenceEqualityComparer.Instance);
        foreach (ShopV1DeckCardBinding card in deck)
        {
            if (card is null || card.ModelIdentity is null ||
                !RoomFlowIdentity.IsStableKey(card.StableKey) || card.UpgradeLevel<0 || !identities.Add(card.ModelIdentity)) return false;
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
            if (left[index].UpgradeLevel!=right[index].UpgradeLevel || left[index].Removable!=right[index].Removable || !ReferenceEquals(left[index].ModelIdentity, right[index].ModelIdentity) ||
                !string.Equals(left[index].StableKey, right[index].StableKey,
                    StringComparison.Ordinal)) return false;
        }
        return true;
    }

    private static bool ExactRemoval(IReadOnlyList<ShopV1DeckCardBinding> before,IReadOnlyList<ShopV1DeckCardBinding> after,object target)
    {
        if(after.Count!=before.Count-1)return false;
        var survivors=new List<ShopV1DeckCardBinding>();int removed=0;
        foreach(var card in before) {if(ReferenceEquals(card.ModelIdentity,target))removed++;else survivors.Add(card);}
        return removed==1 && SameDeck(survivors,after);
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
                card.UpgradeLevel!=before[beforeIndex].UpgradeLevel || card.Removable!=before[beforeIndex].Removable ||
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
        return SameDeck(left.Capture.Deck, right.Capture.Deck) && SamePotions(left.Capture.PotionSlots, right.Capture.PotionSlots) && SameRelics(left.Capture.Relics, right.Capture.Relics);
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
                !ReferenceEquals(x.OfferedModelIdentity, y.OfferedModelIdentity) || !ReferenceEquals(x.StockModelIdentity,y.StockModelIdentity) ||
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
        ShopV1ActionKind.PurchaseCard or ShopV1ActionKind.PurchasePotion or ShopV1ActionKind.PurchaseRelic or ShopV1ActionKind.RemoveCard or ShopV1ActionKind.DiscardPotion => "purchase_waiting",
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
