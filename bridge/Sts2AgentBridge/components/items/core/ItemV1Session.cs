using System;
using System.Collections.Generic;
using System.Globalization;

namespace Sts2AgentBridge.Successors.ItemV1;

public sealed class ItemV1Session
{
    private readonly object _gate = new();
    private readonly string _sessionNonce;
    private readonly IItemV1NativeAdapter _adapter;
    private object? _boundRun;
    private object? _boundPlayer;
    private object? _boundScreen;
    private PublishedDecision? _published;
    private PendingAction? _pending;
    private ItemV1ResolvedResult? _resolved;
    private bool _reserved;
    private bool _dispatching;
    private bool _accepted;
    private bool _unsupported;
    private int _reconciliationReads;

    public ItemV1Session(string sessionNonce, IItemV1NativeAdapter adapter)
    {
        if (!ItemV1CanonicalEncoder.IsCanonicalSessionNonce(sessionNonce))
        {
            throw new ArgumentException("The session nonce is not canonical.", nameof(sessionNonce));
        }
        _sessionNonce = sessionNonce;
        _adapter = adapter ?? throw new ArgumentNullException(nameof(adapter));
    }

    public int ReservedDispatchCount
    {
        get
        {
            lock (_gate)
            {
                return _reserved ? 1 : 0;
            }
        }
    }

    public IItemV1ReadValue Read()
    {
        lock (_gate)
        {
            if (_resolved is not null)
            {
                return _resolved;
            }
            if (_unsupported)
            {
                return FixedObservation("unsupported");
            }
            if (_dispatching)
            {
                return FixedObservation("waiting");
            }
            if (_reserved)
            {
                return _accepted ? Reconcile() : FixedObservation("unsupported");
            }
            return ObserveReadySurface();
        }
    }

    public IItemV1ApplyValue Apply(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (_reserved || _unsupported || _published is null)
            {
                return FixedApplyFailure("rejected");
            }
            if (!ItemV1CanonicalEncoder.IsCanonicalDecisionId(decisionId) ||
                !string.Equals(_published.Observation.DecisionId, decisionId,
                    StringComparison.Ordinal) ||
                actionId is null || !_published.HasAction(actionId))
            {
                return FixedApplyFailure("rejected");
            }

            ItemV1SurfaceCapture current;
            PublishedDecision? recaptured;
            try
            {
                current = _adapter.CaptureSurface();
                if (!TryProject(current, bind: false, out recaptured) ||
                    recaptured is null || !SamePublished(_published, recaptured) ||
                    !string.Equals(recaptured.Observation.DecisionId, decisionId,
                        StringComparison.Ordinal))
                {
                    LatchUnsupported();
                    return FixedApplyFailure("unsupported");
                }
            }
            catch
            {
                LatchUnsupported();
                return FixedApplyFailure("unsupported");
            }

            ItemV1NativeOffer? selected = recaptured.FindByAction(actionId);
            if (selected is null || selected.AlreadySelected || !selected.ButtonVisible ||
                !selected.ButtonEnabled ||
                selected.Kind == ItemV1ItemKind.Potion && !HasEmptySlot(current.PotionSlots))
            {
                LatchUnsupported();
                return FixedApplyFailure("unsupported");
            }

            _pending = new PendingAction(
                current.RunIdentity!, current.PlayerIdentity!, selected.RewardIdentity,
                selected.OfferedModelIdentity, selected.Kind, selected.StableKey,
                selected.Index, decisionId!, actionId, current.PotionCapacity,
                current.PotionSlots);
            _reserved = true;
            _dispatching = true;
            _published = null;
            try
            {
                selected.Dispatch();
                _accepted = true;
                return new ItemV1DispatchReceipt(_sessionNonce, decisionId!, actionId);
            }
            catch
            {
                _unsupported = true;
                return FixedApplyFailure("uncertain");
            }
            finally
            {
                _dispatching = false;
            }
        }
    }

    private IItemV1ReadValue ObserveReadySurface()
    {
        try
        {
            ItemV1SurfaceCapture capture = _adapter.CaptureSurface();
            if (capture.Status == ItemV1SurfaceStatus.Missing)
            {
                _published = null;
                return FixedObservation("waiting");
            }
            if (!TryProject(capture, bind: true, out PublishedDecision? decision) ||
                decision is null)
            {
                LatchUnsupported();
                return FixedObservation("unsupported");
            }
            if (decision.Observation.Status == "waiting")
            {
                _published = null;
                return decision.Observation;
            }
            _published = decision;
            return decision.Observation;
        }
        catch
        {
            LatchUnsupported();
            return FixedObservation("unsupported");
        }
    }

    private bool TryProject(
        ItemV1SurfaceCapture capture,
        bool bind,
        out PublishedDecision? decision)
    {
        decision = null;
        if (capture.Status != ItemV1SurfaceStatus.Available ||
            capture.RunIdentity is null || capture.PlayerIdentity is null ||
            capture.ScreenIdentity is null)
        {
            return false;
        }
        if (_boundRun is null)
        {
            if (!bind)
            {
                return false;
            }
            _boundRun = capture.RunIdentity;
            _boundPlayer = capture.PlayerIdentity;
            _boundScreen = capture.ScreenIdentity;
        }
        else if (!ReferenceEquals(_boundRun, capture.RunIdentity) ||
                 !ReferenceEquals(_boundPlayer, capture.PlayerIdentity) ||
                 !ReferenceEquals(_boundScreen, capture.ScreenIdentity))
        {
            return false;
        }
        if (capture.PotionCapacity < 0 ||
            capture.PotionCapacity > ItemV1Constants.MaximumPotionSlots ||
            capture.PotionSlots.Count != capture.PotionCapacity ||
            capture.Offers.Count > ItemV1Constants.MaximumOffers)
        {
            return false;
        }

        var publicSlots = new string?[capture.PotionSlots.Count];
        for (int index = 0; index < capture.PotionSlots.Count; index++)
        {
            ItemV1PotionSlotBinding slot = capture.PotionSlots[index];
            if ((slot.ModelIdentity is null) != (slot.StableKey is null) ||
                slot.StableKey is not null && !ItemV1CanonicalEncoder.IsStableKey(slot.StableKey))
            {
                return false;
            }
            publicSlots[index] = slot.StableKey;
        }

        if (capture.Offers.Count == 0)
        {
            decision = PublishedDecision.Waiting(_sessionNonce, capture);
            return true;
        }

        var ordered = new ItemV1NativeOffer[capture.Offers.Count];
        for (int index = 0; index < ordered.Length; index++)
        {
            ordered[index] = capture.Offers[index];
        }
        Array.Sort(ordered, static (left, right) => left.Index.CompareTo(right.Index));
        var offers = new ItemV1Offer[ordered.Length];
        var actions = new List<string>(ordered.Length);
        var actionTargets = new List<ItemV1NativeOffer>(ordered.Length);
        bool hasEmptySlot = HasEmptySlot(capture.PotionSlots);
        bool hasRelic = false;
        bool hasPotion = false;
        bool anyControlEnabled = false;
        for (int index = 0; index < ordered.Length; index++)
        {
            ItemV1NativeOffer offer = ordered[index];
            if (offer.Index < 0 || offer.Index > ItemV1Constants.MaximumRewardIndex ||
                index > 0 && ordered[index - 1].Index == offer.Index ||
                offer.Kind == ItemV1ItemKind.Unsupported ||
                !offer.Populated || offer.AlreadySelected || !offer.ButtonVisible ||
                offer.ButtonIdentity is null || offer.RewardIdentity is null ||
                offer.OfferedModelIdentity is null || offer.Dispatch is null ||
                !ItemV1CanonicalEncoder.IsStableKey(offer.StableKey) ||
                HasDuplicateBindings(ordered, index))
            {
                return false;
            }
            string kind;
            if (offer.Kind == ItemV1ItemKind.Potion)
            {
                kind = "potion";
                hasPotion = true;
            }
            else if (offer.Kind == ItemV1ItemKind.Relic)
            {
                kind = "relic";
                hasRelic = true;
            }
            else
            {
                return false;
            }
            offers[index] = new ItemV1Offer(offer.Index, kind, offer.StableKey,
                offer.ButtonEnabled);
            anyControlEnabled |= offer.ButtonEnabled;
            if (offer.ButtonEnabled && (offer.Kind == ItemV1ItemKind.Relic || hasEmptySlot))
            {
                actions.Add("collect:" + offer.Index.ToString(CultureInfo.InvariantCulture));
                actionTargets.Add(offer);
            }
        }

        if (hasPotion && !hasRelic && !hasEmptySlot)
        {
            return false;
        }
        if (!anyControlEnabled || actions.Count == 0)
        {
            decision = PublishedDecision.Waiting(_sessionNonce, capture);
            return true;
        }

        string identity = ItemV1CanonicalEncoder.ComputeDecisionId(
            _sessionNonce, offers, publicSlots, actions);
        var observation = new ItemV1Observation(
            _sessionNonce, "ready", identity, offers, publicSlots, actions);
        decision = new PublishedDecision(
            observation, capture, ordered, actions, actionTargets);
        return true;
    }

    private IItemV1ReadValue Reconcile()
    {
        try
        {
            return ReconcileCore();
        }
        catch
        {
            LatchUnsupported();
            return FixedObservation("unsupported");
        }
    }

    private IItemV1ReadValue ReconcileCore()
    {
        PendingAction? pending = _pending;
        if (pending is null)
        {
            LatchUnsupported();
            return FixedObservation("unsupported");
        }
        _reconciliationReads++;
        ItemV1PendingCapture current = _adapter.CapturePending(pending.Probe);
        if (!ReferenceEquals(current.RunIdentity, pending.RunIdentity) ||
            !ReferenceEquals(current.PlayerIdentity, pending.PlayerIdentity) ||
            !ReferenceEquals(current.RewardIdentity, pending.RewardIdentity) ||
            !ReferenceEquals(current.OfferedModelIdentity, pending.OfferedModelIdentity) ||
            !string.Equals(current.OfferedStableKey, pending.StableKey, StringComparison.Ordinal) ||
            !ItemV1CanonicalEncoder.IsStableKey(current.OfferedStableKey))
        {
            return FailReconciliation();
        }

        bool claimedExact = current.ClaimedModelIdentity is not null &&
            ReferenceEquals(current.ClaimedModelIdentity, pending.OfferedModelIdentity) &&
            string.Equals(current.ClaimedStableKey, pending.StableKey, StringComparison.Ordinal);
        if ((current.ClaimedModelIdentity is null) != (current.ClaimedStableKey is null) ||
            current.ClaimedModelIdentity is not null && !claimedExact)
        {
            return FailReconciliation();
        }

        bool resolved;
        if (pending.Kind == ItemV1ItemKind.Relic)
        {
            resolved = current.SuccessfullySelected && claimedExact;
            if (current.SuccessfullySelected && !claimedExact)
            {
                return FailReconciliation();
            }
        }
        else if (pending.Kind == ItemV1ItemKind.Potion)
        {
            if (!TryPotionDelta(pending, current, out int inserted))
            {
                return FailReconciliation();
            }
            resolved = current.SuccessfullySelected && claimedExact && inserted == 1;
            if (current.SuccessfullySelected && !resolved)
            {
                return FailReconciliation();
            }
        }
        else
        {
            return FailReconciliation();
        }

        if (resolved)
        {
            _resolved = new ItemV1ResolvedResult(
                _sessionNonce, pending.DecisionId, pending.ActionId, pending.OfferIndex,
                pending.Kind == ItemV1ItemKind.Potion ? "potion" : "relic",
                pending.StableKey);
            return _resolved;
        }
        if (_reconciliationReads >= ItemV1Constants.MaximumReconciliationReads)
        {
            return FailReconciliation();
        }
        return FixedObservation("waiting");
    }

    private static bool TryPotionDelta(
        PendingAction pending,
        ItemV1PendingCapture current,
        out int inserted)
    {
        inserted = 0;
        if (current.PotionCapacity != pending.PotionCapacity ||
            current.PotionSlots.Count != pending.BeforePotionSlots.Count)
        {
            return false;
        }
        for (int index = 0; index < pending.BeforePotionSlots.Count; index++)
        {
            ItemV1PotionSlotBinding before = pending.BeforePotionSlots[index];
            ItemV1PotionSlotBinding after = current.PotionSlots[index];
            if (before.ModelIdentity is not null)
            {
                if (!ReferenceEquals(before.ModelIdentity, after.ModelIdentity) ||
                    !string.Equals(before.StableKey, after.StableKey, StringComparison.Ordinal))
                {
                    return false;
                }
            }
            else if (after.ModelIdentity is null)
            {
                if (after.StableKey is not null)
                {
                    return false;
                }
            }
            else if (ReferenceEquals(after.ModelIdentity, pending.OfferedModelIdentity) &&
                     string.Equals(after.StableKey, pending.StableKey, StringComparison.Ordinal))
            {
                inserted++;
                if (inserted > 1)
                {
                    return false;
                }
            }
            else
            {
                return false;
            }
        }
        return true;
    }

    private static bool SamePublished(PublishedDecision left, PublishedDecision right)
    {
        if (!string.Equals(left.Observation.DecisionId, right.Observation.DecisionId,
                StringComparison.Ordinal) ||
            !ReferenceEquals(left.Capture.RunIdentity, right.Capture.RunIdentity) ||
            !ReferenceEquals(left.Capture.PlayerIdentity, right.Capture.PlayerIdentity) ||
            !ReferenceEquals(left.Capture.ScreenIdentity, right.Capture.ScreenIdentity) ||
            left.OrderedOffers.Count != right.OrderedOffers.Count ||
            left.Capture.PotionSlots.Count != right.Capture.PotionSlots.Count)
        {
            return false;
        }
        for (int index = 0; index < left.OrderedOffers.Count; index++)
        {
            ItemV1NativeOffer before = left.OrderedOffers[index];
            ItemV1NativeOffer after = right.OrderedOffers[index];
            if (!ReferenceEquals(before.ButtonIdentity, after.ButtonIdentity) ||
                !ReferenceEquals(before.RewardIdentity, after.RewardIdentity) ||
                !ReferenceEquals(before.OfferedModelIdentity, after.OfferedModelIdentity) ||
                before.Index != after.Index || before.Kind != after.Kind ||
                before.ButtonVisible != after.ButtonVisible ||
                before.ButtonEnabled != after.ButtonEnabled ||
                before.Populated != after.Populated ||
                before.AlreadySelected != after.AlreadySelected ||
                !string.Equals(before.StableKey, after.StableKey, StringComparison.Ordinal))
            {
                return false;
            }
        }
        for (int index = 0; index < left.Capture.PotionSlots.Count; index++)
        {
            ItemV1PotionSlotBinding before = left.Capture.PotionSlots[index];
            ItemV1PotionSlotBinding after = right.Capture.PotionSlots[index];
            if (!ReferenceEquals(before.ModelIdentity, after.ModelIdentity) ||
                !string.Equals(before.StableKey, after.StableKey, StringComparison.Ordinal))
            {
                return false;
            }
        }
        return true;
    }

    private static bool HasDuplicateBindings(ItemV1NativeOffer[] offers, int index)
    {
        for (int previous = 0; previous < index; previous++)
        {
            if (ReferenceEquals(offers[previous].ButtonIdentity, offers[index].ButtonIdentity) ||
                ReferenceEquals(offers[previous].RewardIdentity, offers[index].RewardIdentity) ||
                ReferenceEquals(offers[previous].OfferedModelIdentity,
                    offers[index].OfferedModelIdentity))
            {
                return true;
            }
        }
        return false;
    }

    private static bool HasEmptySlot(IReadOnlyList<ItemV1PotionSlotBinding> slots)
    {
        foreach (ItemV1PotionSlotBinding slot in slots)
        {
            if (slot.ModelIdentity is null && slot.StableKey is null)
            {
                return true;
            }
        }
        return false;
    }

    private IItemV1ReadValue FailReconciliation()
    {
        LatchUnsupported();
        return FixedObservation("unsupported");
    }

    private void LatchUnsupported()
    {
        _unsupported = true;
        _published = null;
    }

    private ItemV1Observation FixedObservation(string status) =>
        ItemV1Observation.Fixed(_sessionNonce, status);

    private ItemV1ApplyFailure FixedApplyFailure(string outcome) =>
        new(_sessionNonce, outcome);

    private sealed class PublishedDecision
    {
        private readonly string[] _actions;
        private readonly ItemV1NativeOffer[] _actionTargets;

        public PublishedDecision(
            ItemV1Observation observation,
            ItemV1SurfaceCapture capture,
            IReadOnlyList<ItemV1NativeOffer> orderedOffers,
            IReadOnlyList<string> actions,
            IReadOnlyList<ItemV1NativeOffer> actionTargets)
        {
            Observation = observation;
            Capture = capture;
            var offers = new ItemV1NativeOffer[orderedOffers.Count];
            for (int index = 0; index < orderedOffers.Count; index++)
            {
                offers[index] = orderedOffers[index];
            }
            OrderedOffers = Array.AsReadOnly(offers);
            _actions = new string[actions.Count];
            _actionTargets = new ItemV1NativeOffer[actionTargets.Count];
            for (int index = 0; index < actions.Count; index++)
            {
                _actions[index] = actions[index];
                _actionTargets[index] = actionTargets[index];
            }
        }

        public ItemV1Observation Observation { get; }
        public ItemV1SurfaceCapture Capture { get; }
        public IReadOnlyList<ItemV1NativeOffer> OrderedOffers { get; }

        public bool HasAction(string action)
        {
            foreach (string value in _actions)
            {
                if (string.Equals(value, action, StringComparison.Ordinal))
                {
                    return true;
                }
            }
            return false;
        }

        public ItemV1NativeOffer? FindByAction(string action)
        {
            for (int index = 0; index < _actions.Length; index++)
            {
                if (string.Equals(_actions[index], action, StringComparison.Ordinal))
                {
                    return _actionTargets[index];
                }
            }
            return null;
        }

        public static PublishedDecision Waiting(
            string nonce,
            ItemV1SurfaceCapture capture) =>
            new(ItemV1Observation.Fixed(nonce, "waiting"), capture,
                Array.Empty<ItemV1NativeOffer>(), Array.Empty<string>(),
                Array.Empty<ItemV1NativeOffer>());
    }

    private sealed class PendingAction
    {
        private readonly ItemV1PotionSlotBinding[] _beforePotionSlots;

        public PendingAction(
            object runIdentity,
            object playerIdentity,
            object rewardIdentity,
            object offeredModelIdentity,
            ItemV1ItemKind kind,
            string stableKey,
            int offerIndex,
            string decisionId,
            string actionId,
            int potionCapacity,
            IReadOnlyList<ItemV1PotionSlotBinding> beforePotionSlots)
        {
            RunIdentity = runIdentity;
            PlayerIdentity = playerIdentity;
            RewardIdentity = rewardIdentity;
            OfferedModelIdentity = offeredModelIdentity;
            Kind = kind;
            StableKey = stableKey;
            OfferIndex = offerIndex;
            DecisionId = decisionId;
            ActionId = actionId;
            PotionCapacity = potionCapacity;
            _beforePotionSlots = new ItemV1PotionSlotBinding[beforePotionSlots.Count];
            for (int index = 0; index < beforePotionSlots.Count; index++)
            {
                ItemV1PotionSlotBinding slot = beforePotionSlots[index];
                _beforePotionSlots[index] = new ItemV1PotionSlotBinding(
                    slot.ModelIdentity, slot.StableKey);
            }
            BeforePotionSlots = Array.AsReadOnly(_beforePotionSlots);
            Probe = new ItemV1PendingProbe(runIdentity, playerIdentity, rewardIdentity,
                offeredModelIdentity, kind);
        }

        public object RunIdentity { get; }
        public object PlayerIdentity { get; }
        public object RewardIdentity { get; }
        public object OfferedModelIdentity { get; }
        public ItemV1ItemKind Kind { get; }
        public string StableKey { get; }
        public int OfferIndex { get; }
        public string DecisionId { get; }
        public string ActionId { get; }
        public int PotionCapacity { get; }
        public IReadOnlyList<ItemV1PotionSlotBinding> BeforePotionSlots { get; }
        public ItemV1PendingProbe Probe { get; }
    }
}
