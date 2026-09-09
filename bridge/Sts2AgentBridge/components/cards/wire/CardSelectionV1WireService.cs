using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Wire;

public sealed class CardSelectionV1WireService : IDisposable
{
    private readonly object _gate = new();
    private readonly int _ownerThreadId = Environment.CurrentManagedThreadId;
    private readonly string _nonce;
    private readonly CardSelectionParentV1Session _session;
    private readonly List<Accepted> _parentAccepted = new();
    private readonly List<Accepted> _childAccepted = new();
    private CardSelectionParentV1Observation? _parentReady;
    private CardSelectionV1Observation? _childReady;
    private int _childHistoryCount;
    private string? _childOperation;
    private int _childMin;
    private int _childMax;
    private string? _childCommitMode;
    private string? _parentKind;
    private string? _parentPolicy;
    private Dictionary<int, CandidateShape>? _candidateShape;
    private int[]? _candidateOrder;
    private bool _childResolved;
    private bool _inside;
    private bool _interfered;
    private bool _failed;
    private bool _disposed;
    private bool _cleanupFailed;

    public CardSelectionV1WireService(
        string sessionNonce,
        CardSelectionParentV1Session session)
    {
        if (!CardSelectionV1WireProtocol.IsLowerHex(sessionNonce, 32))
            throw new ArgumentException("Invalid wire nonce.", nameof(sessionNonce));
        _nonce = sessionNonce;
        _session = session ?? throw new ArgumentNullException(nameof(session));
    }

    public CardSelectionV1WireResponse Handle(
        string? method,
        string? route,
        byte[]? body)
    {
        lock (_gate)
        {
            if (_inside)
            {
                _interfered = true;
                _failed = true;
                return Error(500, "internal_failure");
            }
            if (_failed || _disposed || Environment.CurrentManagedThreadId != _ownerThreadId)
            {
                _failed = true;
                return Error(500, "internal_failure");
            }
            _inside = true;
            byte[]? encoded = null;
            try
            {
                object value;
                if (method == "GET" && route == CardSelectionV1WireProtocol.ParentRoute && Empty(body))
                {
                    value = _session.Read();
                    ValidateParentRead(value);
                }
                else if (method == "GET" && route == CardSelectionV1WireProtocol.ChildRoute && Empty(body))
                {
                    value = _session.ReadChild();
                    ValidateChildRead(value);
                }
                else if (method == "POST" && route == CardSelectionV1WireProtocol.ParentActionRoute &&
                    CardSelectionV1WireProtocol.TryParseAction(body, parent: true,
                        out string parentDecision, out string parentAction))
                {
                    if (!CanApplyParent(parentDecision, parentAction))
                        return Fail(400, "invalid_request");
                    _parentReady = null;
                    value = _session.Apply(parentDecision, parentAction);
                    ValidateParentApply(value, parentDecision, parentAction);
                }
                else if (method == "POST" && route == CardSelectionV1WireProtocol.ChildActionRoute &&
                    CardSelectionV1WireProtocol.TryParseAction(body, parent: false,
                        out string childDecision, out string childAction))
                {
                    if (!CanApplyChild(childDecision, childAction))
                        return Fail(400, "invalid_request");
                    _childReady = null;
                    value = _session.ApplyChild(childDecision, childAction);
                    ValidateChildApply(value, childDecision, childAction);
                }
                else return Fail(400, "invalid_request");

                if (_interfered || _disposed) return Fail(500, "internal_failure");
                encoded = CardSelectionV1WireCodec.Encode(value);
                var result = new CardSelectionV1WireResponse(200, encoded);
                Array.Clear(encoded);
                encoded = null;
                return result;
            }
            catch
            {
                return Fail(500, "internal_failure");
            }
            finally
            {
                if (encoded is not null) Array.Clear(encoded);
                _inside = false;
            }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (Environment.CurrentManagedThreadId != _ownerThreadId || _inside)
            {
                _failed = true;
                if (_inside) _interfered = true;
                throw new InvalidOperationException("Wire cleanup requires the owner outside Handle.");
            }
            if (_disposed)
            {
                if (_cleanupFailed) throw new InvalidOperationException("Wire cleanup failed.");
                return;
            }
            _disposed = true;
            _failed = true;
            _parentReady = null;
            _childReady = null;
            try { _session.Dispose(); }
            catch
            {
                _cleanupFailed = true;
                throw new InvalidOperationException("Wire cleanup failed.");
            }
        }
    }

    private void ValidateParentRead(object value)
    {
        if (value is CardSelectionParentV1Observation observation)
        {
            ParentCommon(observation.Version, observation.SessionNonce, observation.ParentOrdinal);
            if (observation.Status == "ready")
            {
                bool initial = observation.Phase == "initial" && observation.ParentKind is "event" or "rest" &&
                    observation.Policy is "cheese_gorge_add_two" or "rest_smith_upgrade_one" &&
                    observation.DecisionId.Length == 64 &&
                    observation.LegalActions.Count == 1 && observation.LegalActions[0] == "begin" &&
                    _parentAccepted.Count == 0 && !_childResolved;
                bool after = observation.Phase == "after" && observation.ParentKind is "event" or "rest" &&
                    observation.Policy is "cheese_gorge_add_two" or "rest_smith_upgrade_one" &&
                    observation.DecisionId.Length == 64 &&
                    observation.LegalActions.Count == 1 && observation.LegalActions[0] == "proceed" &&
                    _parentAccepted.Count == 1 && _parentAccepted[0].ActionId == "begin" && _childResolved;
                if ((!initial && !after) ||
                    !CardSelectionV1WireProtocol.IsLowerHex(observation.DecisionId, 64) ||
                    !ValidPolicyPair(observation.ParentKind, observation.Policy) ||
                    DecisionUsed(observation.DecisionId))
                    throw new InvalidOperationException();
                if (initial)
                {
                    _parentKind ??= observation.ParentKind;
                    _parentPolicy ??= observation.Policy;
                }
                else if (_parentKind != observation.ParentKind || _parentPolicy != observation.Policy)
                    throw new InvalidOperationException();
                _parentReady = observation;
                return;
            }
            bool fixedPair = observation.Status == "waiting" &&
                    observation.Phase is "initial" or "transient" or "card_child" or "after" or "exit" ||
                observation.Status == "unsupported" && observation.Phase == "unsupported";
            if (!fixedPair ||
                observation.ParentKind.Length != 0 || observation.Policy.Length != 0 ||
                observation.DecisionId.Length != 0 || observation.LegalActions.Count != 0)
                throw new InvalidOperationException();
            _parentReady = null;
            if (observation.Status == "unsupported") _failed = true;
            return;
        }
        if (value is CardSelectionParentV1ResolvedResult resolved)
        {
            ParentCommon(resolved.Version, resolved.SessionNonce, resolved.ParentOrdinal);
            if (resolved.Status != "resolved" || resolved.Result != "map_handoff" ||
                _parentAccepted.Count != 2 || !_childResolved ||
                resolved.BeginDecisionId != _parentAccepted[0].DecisionId ||
                resolved.BeginActionId != "begin" ||
                resolved.ProceedDecisionId != _parentAccepted[1].DecisionId ||
                resolved.ProceedActionId != "proceed")
                throw new InvalidOperationException();
            _parentReady = null;
            return;
        }
        throw new InvalidOperationException();
    }

    private void ValidateParentApply(object value, string decision, string action)
    {
        if (value is CardSelectionParentV1DispatchReceipt receipt)
        {
            ParentCommon(receipt.Version, receipt.SessionNonce, receipt.ParentOrdinal);
            if (receipt.Outcome != "accepted" || receipt.DecisionId != decision ||
                receipt.ActionId != action || _parentAccepted.Count >= 2 ||
                (_parentAccepted.Count == 0 ? action != "begin" : action != "proceed"))
                throw new InvalidOperationException();
            _parentAccepted.Add(new Accepted(decision, action));
            return;
        }
        if (value is CardSelectionParentV1ApplyFailure failure)
        {
            ParentCommon(failure.Version, failure.SessionNonce, failure.ParentOrdinal);
            if (failure.Outcome is not ("rejected" or "unsupported" or "uncertain"))
                throw new InvalidOperationException();
            _failed = true;
            return;
        }
        throw new InvalidOperationException();
    }

    private void ValidateChildRead(object value)
    {
        if (value is CardSelectionParentV1ChildUnavailable unavailable)
        {
            ChildCommon(unavailable.Version, unavailable.SessionNonce, 1);
            if (unavailable.Status != "unsupported" || unavailable.Phase != "unsupported")
                throw new InvalidOperationException();
            _childReady = null;
            _failed = true;
            return;
        }
        if (value is CardSelectionV1Observation observation)
        {
            ChildCommon(observation.Version, observation.SessionNonce, observation.ParentOrdinal);
            ValidateHistory(observation.PriorResults);
            if (observation.Status == "ready")
            {
                if (observation.Phase is not ("selecting" or "preview") ||
                    observation.Operation is not ("add" or "remove" or "upgrade" or "transform") ||
                    observation.CommitMode is not ("auto_at_max" or "explicit_confirm" or "preview_confirm") ||
                    observation.MinSelect is < 1 or > 8 || observation.MaxSelect is < 1 or > 8 ||
                    observation.MinSelect > observation.MaxSelect ||
                    !CardSelectionV1WireProtocol.IsLowerHex(observation.DecisionId, 64) ||
                    observation.Candidates.Count is < 1 or > 64 ||
                    observation.SelectedSlots.Count > observation.MaxSelect ||
                    observation.LegalActions.Count == 0 || DecisionUsed(observation.DecisionId))
                    throw new InvalidOperationException();
                ValidateCandidates(observation.Candidates, observation.SelectedSlots);
                ValidateLegalActions(observation);
                int selectedResults = CountSelectedResults(observation.PriorResults);
                if (selectedResults != observation.SelectedSlots.Count)
                    throw new InvalidOperationException();
                if (_childOperation is null)
                {
                    _childOperation = observation.Operation;
                    _childMin = observation.MinSelect;
                    _childMax = observation.MaxSelect;
                    _childCommitMode = observation.CommitMode;
                    BindCandidateShape(observation.Candidates);
                }
                else if (_childOperation != observation.Operation || _childMin != observation.MinSelect ||
                         _childMax != observation.MaxSelect ||
                         _childCommitMode != observation.CommitMode)
                    throw new InvalidOperationException();
                ValidatePolicyChild(observation);
                ValidateCandidateShape(observation.Candidates);
                ValidateSelectionHistory(observation.SelectedSlots);
                _childReady = observation;
                return;
            }
            bool fixedPair = observation.Status == "waiting" &&
                    observation.Phase is "selecting" or "submitted" or "transient" ||
                observation.Status == "unsupported" && observation.Phase == "unsupported";
            if (!fixedPair ||
                observation.Operation.Length != 0 || observation.CommitMode.Length != 0 ||
                observation.MinSelect != 0 || observation.MaxSelect != 0 ||
                observation.DecisionId.Length != 0 || observation.Candidates.Count != 0 ||
                observation.SelectedSlots.Count != 0 || observation.LegalActions.Count != 0)
                throw new InvalidOperationException();
            _childReady = null;
            if (observation.Status == "unsupported") _failed = true;
            return;
        }
        if (value is CardSelectionV1ResolvedResult resolved)
        {
            ChildCommon(resolved.Version, resolved.SessionNonce, resolved.ParentOrdinal);
            ValidateHistory(resolved.PriorResults);
            if (resolved.ParentAddedCards.Count!=0 || resolved.Status != "resolved" || resolved.Phase != "complete" ||
                resolved.Operation != _childOperation || _childOperation is null ||
                resolved.PriorResults.Count != _childAccepted.Count ||
                resolved.SelectedCards.Count < _childMin || resolved.SelectedCards.Count > _childMax ||
                resolved.SelectedCards.Count != CountSelectedResults(resolved.PriorResults) ||
                !ValidCommitSequence())
                throw new InvalidOperationException();
            ValidateSelectedCards(resolved.SelectedCards);
            ValidateResolvedCards(resolved.SelectedCards);
            _childReady = null;
            _childResolved = true;
            return;
        }
        throw new InvalidOperationException();
    }

    private void ValidateChildApply(object value, string decision, string action)
    {
        if (value is CardSelectionV1DispatchReceipt receipt)
        {
            ChildCommon(receipt.Version, receipt.SessionNonce, receipt.ParentOrdinal);
            if (receipt.Outcome != "accepted" || receipt.DecisionId != decision ||
                receipt.ActionId != action || _childAccepted.Count >= 10)
                throw new InvalidOperationException();
            _childAccepted.Add(new Accepted(decision, action));
            return;
        }
        if (value is CardSelectionV1ApplyFailure failure)
        {
            ChildCommon(failure.Version, failure.SessionNonce, failure.ParentOrdinal);
            if (failure.Outcome is not ("rejected" or "unsupported" or "uncertain"))
                throw new InvalidOperationException();
            _failed = true;
            return;
        }
        if (value is CardSelectionParentV1ChildApplyFailure parentFailure)
        {
            ChildCommon(parentFailure.Version, parentFailure.SessionNonce, 1);
            if (parentFailure.Outcome is not ("rejected" or "unsupported" or "uncertain"))
                throw new InvalidOperationException();
            _failed = true;
            return;
        }
        throw new InvalidOperationException();
    }

    private bool CanApplyParent(string decision, string action) =>
        _parentReady is not null && _parentReady.Status == "ready" &&
        _parentReady.DecisionId == decision && _parentReady.LegalActions.Count == 1 &&
        _parentReady.LegalActions[0] == action;

    private bool CanApplyChild(string decision, string action)
    {
        if (_childReady is null || _childReady.Status != "ready" ||
            _childReady.DecisionId != decision) return false;
        foreach (string legal in _childReady.LegalActions)
            if (legal == action) return true;
        return false;
    }

    private void ValidateHistory(IReadOnlyList<CardSelectionV1ActionResult> history)
    {
        if (history.Count < _childHistoryCount || history.Count > _childAccepted.Count)
            throw new InvalidOperationException();
        for (int index = 0; index < history.Count; index++)
        {
            CardSelectionV1ActionResult item = history[index];
            Accepted accepted = _childAccepted[index];
            string expected = accepted.ActionId.StartsWith("select:", StringComparison.Ordinal)
                ? "selected" : accepted.ActionId == "preview" ? "previewed" : "committed";
            if (item.DecisionId != accepted.DecisionId || item.ActionId != accepted.ActionId ||
                item.Result != expected) throw new InvalidOperationException();
        }
        _childHistoryCount = history.Count;
    }

    private static void ValidateCandidates(
        IReadOnlyList<CardSelectionV1Candidate> candidates,
        IReadOnlyList<int> selectedSlots)
    {
        var slots = new HashSet<int>();
        var candidateSelected = new HashSet<int>();
        foreach (CardSelectionV1Candidate candidate in candidates)
        {
            if (candidate is null || candidate.Slot is < 0 or >= 64 || !slots.Add(candidate.Slot) ||
                !IsStableKey(candidate.Key) || candidate.UpgradeLevel < 0)
                throw new InvalidOperationException();
            if (candidate.Selected) candidateSelected.Add(candidate.Slot);
        }
        var declaredSelected = new HashSet<int>();
        foreach (int slot in selectedSlots)
            if (!slots.Contains(slot) || !declaredSelected.Add(slot))
                throw new InvalidOperationException();
        if (!candidateSelected.SetEquals(declaredSelected)) throw new InvalidOperationException();
    }

    private static void ValidateSelectedCards(IReadOnlyList<CardSelectionV1Candidate> cards)
    {
        var slots = new HashSet<int>();
        foreach (CardSelectionV1Candidate card in cards)
            if (card is null || card.Slot is < 0 or >= 64 || !slots.Add(card.Slot) ||
                !IsStableKey(card.Key) || card.UpgradeLevel < 0 || !card.Selected)
                throw new InvalidOperationException();
    }

    private static void ValidateLegalActions(CardSelectionV1Observation observation)
    {
        var actions = new HashSet<string>(StringComparer.Ordinal);
        foreach (string action in observation.LegalActions)
        {
            if (!actions.Add(action) || !CardSelectionV1WireProtocol.IsChildAction(action))
                throw new InvalidOperationException();
            if (action.StartsWith("select:", StringComparison.Ordinal))
            {
                int slot = int.Parse(action.AsSpan(7), System.Globalization.CultureInfo.InvariantCulture);
                CardSelectionV1Candidate? match = null;
                foreach (CardSelectionV1Candidate candidate in observation.Candidates)
                    if (candidate.Slot == slot) { match = candidate; break; }
                if (match is null || !match.Visible || !match.Enabled || match.Selected ||
                    observation.SelectedSlots.Count >= observation.MaxSelect)
                    throw new InvalidOperationException();
            }
            else if (action == "preview")
            {
                if (observation.CommitMode != "preview_confirm" || observation.Phase != "selecting" ||
                    observation.SelectedSlots.Count < observation.MinSelect ||
                    observation.SelectedSlots.Count > observation.MaxSelect)
                    throw new InvalidOperationException();
            }
            else if (action == "confirm")
            {
                bool explicitMode = observation.CommitMode == "explicit_confirm" && observation.Phase == "selecting";
                bool previewMode = observation.CommitMode == "preview_confirm" && observation.Phase == "preview";
                if ((!explicitMode && !previewMode) || observation.SelectedSlots.Count < observation.MinSelect ||
                    observation.SelectedSlots.Count > observation.MaxSelect)
                    throw new InvalidOperationException();
            }
        }
        if (observation.MinSelect == observation.MaxSelect &&
            observation.SelectedSlots.Count < observation.MinSelect && actions.Contains("confirm"))
            throw new InvalidOperationException();

        foreach (CardSelectionV1Candidate candidate in observation.Candidates)
        {
            string selection = "select:" + candidate.Slot.ToString(
                System.Globalization.CultureInfo.InvariantCulture);
            bool expected = observation.Phase == "selecting" && candidate.Visible &&
                candidate.Enabled && !candidate.Selected &&
                observation.SelectedSlots.Count < observation.MaxSelect;
            if (actions.Contains(selection) != expected) throw new InvalidOperationException();
        }
    }

    private void ValidatePolicyChild(CardSelectionV1Observation observation)
    {
        bool cheese = _parentKind == "event" && _parentPolicy == "cheese_gorge_add_two" &&
            observation.Operation == "add" && observation.CommitMode == "auto_at_max" &&
            observation.MinSelect == 2 && observation.MaxSelect == 2 &&
            observation.Candidates.Count == 8;
        bool smith = _parentKind == "rest" && _parentPolicy == "rest_smith_upgrade_one" &&
            observation.Operation == "upgrade" && observation.CommitMode == "preview_confirm" &&
            observation.MinSelect == 1 && observation.MaxSelect == 1;
        if (!cheese && !smith) throw new InvalidOperationException();
    }

    private void BindCandidateShape(IReadOnlyList<CardSelectionV1Candidate> candidates)
    {
        _candidateShape = new Dictionary<int, CandidateShape>();
        _candidateOrder = new int[candidates.Count];
        int index = 0;
        foreach (CardSelectionV1Candidate candidate in candidates)
        {
            _candidateShape.Add(candidate.Slot,
                new CandidateShape(candidate.Key, candidate.UpgradeLevel));
            _candidateOrder[index++] = candidate.Slot;
        }
    }

    private void ValidateCandidateShape(IReadOnlyList<CardSelectionV1Candidate> candidates)
    {
        if (_candidateShape is null || _candidateOrder is null ||
            candidates.Count != _candidateShape.Count || candidates.Count != _candidateOrder.Length)
            throw new InvalidOperationException();
        for (int index = 0; index < candidates.Count; index++)
        {
            CardSelectionV1Candidate candidate = candidates[index];
            if (candidate.Slot != _candidateOrder[index]) throw new InvalidOperationException();
            if (!_candidateShape.TryGetValue(candidate.Slot, out CandidateShape? shape) ||
                shape.Key != candidate.Key || shape.UpgradeLevel != candidate.UpgradeLevel)
                throw new InvalidOperationException();
        }
    }

    private void ValidateSelectionHistory(IReadOnlyList<int> selectedSlots)
    {
        var expected = new HashSet<int>();
        foreach (Accepted accepted in _childAccepted)
            if (accepted.ActionId.StartsWith("select:", StringComparison.Ordinal))
                expected.Add(int.Parse(accepted.ActionId.AsSpan(7),
                    System.Globalization.CultureInfo.InvariantCulture));
        if (selectedSlots.Count != expected.Count) throw new InvalidOperationException();
        foreach (int slot in selectedSlots)
            if (!expected.Remove(slot)) throw new InvalidOperationException();
        if (expected.Count != 0) throw new InvalidOperationException();
    }

    private void ValidateResolvedCards(IReadOnlyList<CardSelectionV1Candidate> cards)
    {
        if (_candidateShape is null) throw new InvalidOperationException();
        var slots = new HashSet<int>();
        foreach (Accepted accepted in _childAccepted)
            if (accepted.ActionId.StartsWith("select:", StringComparison.Ordinal))
                slots.Add(int.Parse(accepted.ActionId.AsSpan(7),
                    System.Globalization.CultureInfo.InvariantCulture));
        if (cards.Count != slots.Count) throw new InvalidOperationException();
        foreach (CardSelectionV1Candidate card in cards)
            if (!slots.Remove(card.Slot) ||
                !_candidateShape.TryGetValue(card.Slot, out CandidateShape? shape) ||
                shape.Key != card.Key || shape.UpgradeLevel != card.UpgradeLevel)
                throw new InvalidOperationException();
        if (slots.Count != 0) throw new InvalidOperationException();
    }

    private bool ValidCommitSequence()
    {
        if (_childAccepted.Count == 0) return false;
        Accepted last = _childAccepted[^1];
        if (_childCommitMode == "auto_at_max")
            return last.ActionId.StartsWith("select:", StringComparison.Ordinal) &&
                CountSelectedActions() == _childMax;
        return (_childCommitMode is "explicit_confirm" or "preview_confirm") &&
            last.ActionId == "confirm";
    }

    private int CountSelectedActions()
    {
        int count = 0;
        foreach (Accepted accepted in _childAccepted)
            if (accepted.ActionId.StartsWith("select:", StringComparison.Ordinal)) count++;
        return count;
    }

    private bool DecisionUsed(string decision)
    {
        foreach (Accepted accepted in _parentAccepted)
            if (accepted.DecisionId == decision) return true;
        foreach (Accepted accepted in _childAccepted)
            if (accepted.DecisionId == decision) return true;
        return false;
    }

    private static int CountSelectedResults(IReadOnlyList<CardSelectionV1ActionResult> values)
    {
        int count = 0;
        foreach (CardSelectionV1ActionResult value in values) if (value.Result == "selected") count++;
        return count;
    }

    private void ParentCommon(string version, string nonce, int ordinal)
    {
        if (version != CardSelectionParentV1Limits.Version || nonce != _nonce || ordinal != 1)
            throw new InvalidOperationException();
    }
    private void ChildCommon(string version, string nonce, int ordinal)
    {
        if (version != CardSelectionV1Limits.Version || nonce != _nonce || ordinal != 1)
            throw new InvalidOperationException();
    }
    private static bool ValidPolicyPair(string parentKind, string policy) =>
        parentKind == "event" && policy == "cheese_gorge_add_two" ||
        parentKind == "rest" && policy == "rest_smith_upgrade_one";
    private static bool IsStableKey(string? value)
    {
        if (value is null || value.Length is < 1 or > 128) return false;
        foreach (char c in value)
            if (c is not (>= 'a' and <= 'z') and not (>= 'A' and <= 'Z') and
                not (>= '0' and <= '9') and not '_') return false;
        return true;
    }
    private static bool Empty(byte[]? body) => body is null || body.Length == 0;
    private CardSelectionV1WireResponse Fail(int status, string code)
    { _failed = true; _parentReady = null; _childReady = null; return Error(status, code); }
    private static CardSelectionV1WireResponse Error(int status, string code) =>
        CreateError(status, code);
    private static CardSelectionV1WireResponse CreateError(int status, string code)
    {
        byte[] body = CardSelectionV1WireCodec.Error(code);
        try { return new CardSelectionV1WireResponse(status, body); }
        finally { Array.Clear(body); }
    }
    private sealed record Accepted(string DecisionId, string ActionId);
    private sealed record CandidateShape(string Key, int UpgradeLevel);
}
