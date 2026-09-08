using System;
using System.Collections.Generic;
using System.Globalization;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.ItemWireV1;

public sealed class ItemWireV1Service
{
    private readonly object _gate = new();
    private readonly string _sessionNonce;
    private readonly ItemV1Session _session;
    private readonly byte[] _invalidRequest;
    private readonly byte[] _internalFailure;
    private readonly byte[] _rejected;
    private ItemWireV1Envelope? _publishedReady;
    private ItemWireV1AcceptedContext? _accepted;
    private bool _applyAttempted;
    private bool _terminalFailure;

    public ItemWireV1Service(string sessionNonce, IItemV1NativeAdapter adapter)
    {
        if (!ItemV1CanonicalEncoder.IsCanonicalSessionNonce(sessionNonce))
        {
            throw new ArgumentException("Session nonce is not canonical.", nameof(sessionNonce));
        }
        _sessionNonce = sessionNonce;
        _session = new ItemV1Session(sessionNonce, adapter ??
            throw new ArgumentNullException(nameof(adapter)));
        _invalidRequest = ItemWireV1Codec.EncodeFixedError(sessionNonce, "invalid_request");
        _internalFailure = ItemWireV1Codec.EncodeFixedError(sessionNonce, "internal_failure");
        _rejected = ItemWireV1Codec.Encode(new ItemWireV1Envelope(
            sessionNonce, "rejected"));
    }

    public byte[] Handle(
        string? method,
        string? route,
        string? decisionId,
        string? actionId)
    {
        lock (_gate)
        {
            if (string.Equals(method, "GET", StringComparison.Ordinal) &&
                string.Equals(route, ItemWireV1Protocol.DecisionRoute, StringComparison.Ordinal) &&
                decisionId is null && actionId is null)
            {
                if (_terminalFailure)
                {
                    return Copy(_internalFailure);
                }
                return HandleRead();
            }
            if (string.Equals(method, "POST", StringComparison.Ordinal) &&
                string.Equals(route, ItemWireV1Protocol.ActionRoute, StringComparison.Ordinal) &&
                ItemV1CanonicalEncoder.IsCanonicalDecisionId(decisionId) &&
                ItemWireV1Protocol.IsCanonicalActionId(actionId, out _))
            {
                if (_terminalFailure)
                {
                    return Copy(_internalFailure);
                }
                if (_applyAttempted)
                {
                    return Copy(_rejected);
                }
                _applyAttempted = true;
                return HandleApply(decisionId!, actionId!);
            }
            return Copy(_invalidRequest);
        }
    }

    private byte[] HandleRead()
    {
        try
        {
            IItemV1ReadValue value = _session.Read();
            if (value is ItemV1Observation observation)
            {
                ItemWireV1Envelope envelope = ProjectObservation(observation);
                byte[] encoded = ItemWireV1Codec.Encode(envelope);
                _publishedReady = envelope.Status == "ready" ? envelope : null;
                return encoded;
            }
            if (value is ItemV1ResolvedResult resolved)
            {
                ItemWireV1Envelope envelope = ProjectResolved(resolved);
                return ItemWireV1Codec.Encode(envelope);
            }
            _terminalFailure = true;
            return Copy(_internalFailure);
        }
        catch
        {
            _terminalFailure = true;
            return Copy(_internalFailure);
        }
    }

    private byte[] HandleApply(string decisionId, string actionId)
    {
        try
        {
            ItemWireV1Envelope? published = _publishedReady;
            IItemV1ApplyValue value = _session.Apply(decisionId, actionId);
            if (value is ItemV1DispatchReceipt receipt)
            {
                ItemWireV1AcceptedContext context = ValidateAccepted(receipt, published);
                var envelope = new ItemWireV1Envelope(
                    _sessionNonce, "accepted", receipt.DecisionId, receipt.ActionId);
                byte[] encoded = ItemWireV1Codec.Encode(envelope);
                _accepted = context;
                _publishedReady = null;
                return encoded;
            }
            if (value is ItemV1ApplyFailure failure)
            {
                string status = failure.Outcome switch
                {
                    "rejected" => "rejected",
                    "uncertain" => "uncertain",
                    "unsupported" => "unsupported",
                    _ => throw new InvalidOperationException("Unknown item apply result."),
                };
                _publishedReady = null;
                return ItemWireV1Codec.Encode(new ItemWireV1Envelope(
                    _sessionNonce, status));
            }
            _terminalFailure = true;
            return Copy(_internalFailure);
        }
        catch
        {
            _terminalFailure = true;
            return Copy(_internalFailure);
        }
    }

    private ItemWireV1Envelope ProjectObservation(ItemV1Observation observation)
    {
        ValidateCommon(observation.Version, observation.SessionNonce,
            observation.SurfaceOrdinal);
        if (observation.Status is "waiting" or "unsupported")
        {
            if (observation.DecisionId.Length != 0 || observation.Offers.Count != 0 ||
                observation.PotionSlots.Count != 0 || observation.LegalActions.Count != 0)
            {
                throw new InvalidOperationException("Inactive item observation is not empty.");
            }
            return new ItemWireV1Envelope(_sessionNonce, observation.Status);
        }
        if (observation.Status != "ready" ||
            !ItemV1CanonicalEncoder.IsCanonicalDecisionId(observation.DecisionId) ||
            observation.Offers.Count is < 1 or > ItemV1Constants.MaximumOffers ||
            observation.PotionSlots.Count > ItemV1Constants.MaximumPotionSlots ||
            observation.LegalActions.Count is < 1 or > ItemV1Constants.MaximumOffers)
        {
            throw new InvalidOperationException("Ready item observation is invalid.");
        }

        var offers = new List<ItemWireV1OfferDto>(observation.Offers.Count);
        int previousIndex = -1;
        foreach (ItemV1Offer offer in observation.Offers)
        {
            if (offer.Index < 0 || offer.Index > ItemV1Constants.MaximumRewardIndex ||
                offer.Index <= previousIndex ||
                offer.Kind is not ("potion" or "relic") ||
                !ItemV1CanonicalEncoder.IsStableKey(offer.Key))
            {
                throw new InvalidOperationException("Item offer is invalid.");
            }
            previousIndex = offer.Index;
            offers.Add(new ItemWireV1OfferDto(
                offer.Index, offer.Kind, offer.Key, offer.Enabled));
        }
        foreach (string? slot in observation.PotionSlots)
        {
            if (slot is not null && !ItemV1CanonicalEncoder.IsStableKey(slot))
            {
                throw new InvalidOperationException("Potion slot is invalid.");
            }
        }

        int previousOfferPosition = -1;
        int actionPosition = 0;
        var expectedActions = new List<string>(observation.Offers.Count);
        bool hasEmptyPotionSlot = HasEmptyPotionSlot(observation.PotionSlots);
        foreach (ItemV1Offer offer in observation.Offers)
        {
            if (offer.Enabled && (offer.Kind == "relic" || hasEmptyPotionSlot))
            {
                expectedActions.Add("collect:" +
                    offer.Index.ToString(CultureInfo.InvariantCulture));
            }
        }
        if (expectedActions.Count != observation.LegalActions.Count)
        {
            throw new InvalidOperationException("Legal actions are incomplete.");
        }
        foreach (string action in observation.LegalActions)
        {
            if (!ItemWireV1Protocol.IsCanonicalActionId(action, out int actionIndex))
            {
                throw new InvalidOperationException("Legal action is invalid.");
            }
            int offerPosition = FindOffer(observation.Offers, actionIndex);
            if (offerPosition <= previousOfferPosition ||
                !observation.Offers[offerPosition].Enabled ||
                observation.Offers[offerPosition].Kind == "potion" &&
                !hasEmptyPotionSlot ||
                !string.Equals(action, expectedActions[actionPosition],
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException("Legal action does not match its offer.");
            }
            previousOfferPosition = offerPosition;
            actionPosition++;
        }
        string recomputed = ItemV1CanonicalEncoder.ComputeDecisionId(
            _sessionNonce, observation.Offers, observation.PotionSlots,
            observation.LegalActions);
        if (!string.Equals(recomputed, observation.DecisionId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Item decision digest mismatch.");
        }
        return new ItemWireV1Envelope(
            _sessionNonce,
            "ready",
            observation.DecisionId,
            offers: offers,
            potionSlots: observation.PotionSlots,
            legalActions: observation.LegalActions);
    }

    private ItemWireV1AcceptedContext ValidateAccepted(
        ItemV1DispatchReceipt receipt,
        ItemWireV1Envelope? published)
    {
        ValidateCommon(receipt.Version, receipt.SessionNonce, receipt.SurfaceOrdinal);
        if (receipt.Outcome != "accepted" || published is null ||
            !string.Equals(receipt.DecisionId, published.DecisionId,
                StringComparison.Ordinal) ||
            !Contains(published.LegalActions, receipt.ActionId) ||
            !ItemWireV1Protocol.IsCanonicalActionId(receipt.ActionId, out int index))
        {
            throw new InvalidOperationException("Accepted item receipt is not correlated.");
        }
        int position = FindOffer(published.Offers, index);
        ItemWireV1OfferDto offer = published.Offers[position];
        return new ItemWireV1AcceptedContext(
            receipt.DecisionId, receipt.ActionId, offer.Index, offer.Kind, offer.Key);
    }

    private ItemWireV1Envelope ProjectResolved(ItemV1ResolvedResult result)
    {
        ValidateCommon(result.Version, result.SessionNonce, result.SurfaceOrdinal);
        ItemWireV1AcceptedContext? accepted = _accepted;
        if (accepted is null || result.Result != "collected" ||
            !string.Equals(result.DecisionId, accepted.DecisionId,
                StringComparison.Ordinal) ||
            !string.Equals(result.ActionId, accepted.ActionId, StringComparison.Ordinal) ||
            result.OfferIndex != accepted.OfferIndex ||
            !string.Equals(result.Kind, accepted.Kind, StringComparison.Ordinal) ||
            !string.Equals(result.Key, accepted.Key, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Resolved item result is not correlated.");
        }
        return new ItemWireV1Envelope(
            _sessionNonce,
            "resolved",
            result.DecisionId,
            result.ActionId,
            result.OfferIndex,
            result.Kind,
            result.Key,
            result.Result);
    }

    private void ValidateCommon(string version, string nonce, int ordinal)
    {
        if (version != ItemV1Constants.Version ||
            !string.Equals(nonce, _sessionNonce, StringComparison.Ordinal) ||
            ordinal != ItemV1Constants.SurfaceOrdinal)
        {
            throw new InvalidOperationException("Item common fields are invalid.");
        }
    }

    private static int FindOffer(IReadOnlyList<ItemV1Offer> offers, int index)
    {
        for (int position = 0; position < offers.Count; position++)
        {
            if (offers[position].Index == index)
            {
                return position;
            }
        }
        throw new InvalidOperationException("Item action has no offer.");
    }

    private static int FindOffer(IReadOnlyList<ItemWireV1OfferDto> offers, int index)
    {
        for (int position = 0; position < offers.Count; position++)
        {
            if (offers[position].Index == index)
            {
                return position;
            }
        }
        throw new InvalidOperationException("Item action has no offer.");
    }

    private static bool Contains(IReadOnlyList<string> values, string expected)
    {
        foreach (string value in values)
        {
            if (string.Equals(value, expected, StringComparison.Ordinal))
            {
                return true;
            }
        }
        return false;
    }

    private static bool HasEmptyPotionSlot(IReadOnlyList<string?> slots)
    {
        foreach (string? slot in slots)
        {
            if (slot is null)
            {
                return true;
            }
        }
        return false;
    }

    private static byte[] Copy(byte[] source)
    {
        var copy = new byte[source.Length];
        source.CopyTo(copy, 0);
        return copy;
    }
}
