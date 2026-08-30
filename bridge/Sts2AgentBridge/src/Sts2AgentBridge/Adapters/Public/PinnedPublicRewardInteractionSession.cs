using System;
using System.Collections.Generic;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

internal sealed class PinnedPublicRewardParentTarget
{
    public PinnedPublicRewardParentTarget(
        int slot,
        NRewardButton button,
        Reward reward,
        PublicRewardItem projection,
        IReadOnlyList<CardModel> offeredCards)
    {
        Slot = slot;
        Button = button;
        Reward = reward;
        Projection = projection;
        OfferedCards = offeredCards;
    }

    public int Slot { get; }

    public NRewardButton Button { get; }

    public Reward Reward { get; }

    public PublicRewardItem Projection { get; }

    public IReadOnlyList<CardModel> OfferedCards { get; }
}

internal sealed class PinnedPublicRewardCardTarget
{
    public PinnedPublicRewardCardTarget(int slot, NCardHolder holder, CardModel model)
    {
        Slot = slot;
        Holder = holder;
        Model = model;
    }

    public int Slot { get; }

    public NCardHolder Holder { get; }

    public CardModel Model { get; }
}

internal sealed class PinnedPublicRewardPendingMutation
{
    public PinnedPublicRewardPendingMutation(
        PublicRewardActionKind kind,
        PublicRewardPlayer beforePlayer,
        PinnedPublicRewardParentTarget? parentTarget = null,
        PinnedPublicRewardCardTarget? cardTarget = null,
        int chosenCardCopiesBefore = -1)
    {
        Kind = kind;
        BeforePlayer = beforePlayer;
        ParentTarget = parentTarget;
        CardTarget = cardTarget;
        ChosenCardCopiesBefore = chosenCardCopiesBefore;
    }

    public PublicRewardActionKind Kind { get; }

    public PublicRewardPlayer BeforePlayer { get; }

    public PinnedPublicRewardParentTarget? ParentTarget { get; }

    public PinnedPublicRewardCardTarget? CardTarget { get; }

    public int ChosenCardCopiesBefore { get; }
}

internal sealed class PinnedPublicRewardInteractionSession
{
    private readonly object _gate = new();
    private readonly HashSet<string> _acceptedDecisionIds = new(StringComparer.Ordinal);
    private readonly List<Reward> _skippedCardRewards = new();

    private int _acceptedActionCount;
    private int _processAcceptedActionCount;
    private int _rewardSessionCount;
    private int _decisionRevision;
    private bool _observedReady;
    private bool _completedSession;
    private bool _unsupported;
    private string _currentDecisionId = string.Empty;
    private NRewardsScreen? _parentScreen;
    private PinnedPublicRewardParentTarget[] _parentTargets = Array.Empty<PinnedPublicRewardParentTarget>();
    private NCardRewardSelectionScreen? _cardScreen;
    private PinnedPublicRewardCardTarget[] _cardTargets = Array.Empty<PinnedPublicRewardCardTarget>();
    private NCardRewardAlternativeButton? _skipButton;
    private PinnedPublicRewardParentTarget? _activeCardReward;
    private PinnedPublicRewardPendingMutation? _pending;
    private Player? _player;
    private PublicRewardPlayer _lastPlayer;

    public int DecisionRevision
    {
        get
        {
            lock (_gate)
            {
                return _decisionRevision;
            }
        }
    }

    public bool ObservedReady
    {
        get
        {
            lock (_gate)
            {
                return _observedReady;
            }
        }
    }

    public bool IsUnsupported
    {
        get
        {
            lock (_gate)
            {
                return _unsupported;
            }
        }
    }

    public Player? Player
    {
        get
        {
            lock (_gate)
            {
                return _player;
            }
        }
    }

    public PublicRewardPlayer LastPlayer
    {
        get
        {
            lock (_gate)
            {
                return _lastPlayer;
            }
        }
    }

    public PinnedPublicRewardPendingMutation? Pending
    {
        get
        {
            lock (_gate)
            {
                return _pending;
            }
        }
    }

    public PinnedPublicRewardParentTarget? ActiveCardReward
    {
        get
        {
            lock (_gate)
            {
                return _activeCardReward;
            }
        }
    }

    public void PublishParent(
        PublicRewardDecisionSnapshot snapshot,
        NRewardsScreen screen,
        Player player,
        IReadOnlyList<PinnedPublicRewardParentTarget> targets)
    {
        lock (_gate)
        {
            _observedReady = true;
            _currentDecisionId = snapshot.DecisionId;
            _parentScreen = screen;
            _parentTargets = Copy(targets);
            _cardScreen = null;
            _cardTargets = Array.Empty<PinnedPublicRewardCardTarget>();
            _skipButton = null;
            _player = player;
            _lastPlayer = snapshot.Player;
        }
    }

    public bool PrepareParentScreen(NRewardsScreen screen)
    {
        lock (_gate)
        {
            if (_parentScreen is null)
            {
                _parentScreen = screen;
                _rewardSessionCount = 1;
                return true;
            }
            if (ReferenceEquals(_parentScreen, screen))
            {
                return true;
            }
            if (!_completedSession ||
                _rewardSessionCount >= PublicRewardActionBudget.MaximumRewardSessionsPerProcess)
            {
                return false;
            }

            _rewardSessionCount++;
            _acceptedActionCount = 0;
            _acceptedDecisionIds.Clear();
            _skippedCardRewards.Clear();
            _decisionRevision = 0;
            _completedSession = false;
            _currentDecisionId = string.Empty;
            _parentScreen = screen;
            _parentTargets = Array.Empty<PinnedPublicRewardParentTarget>();
            _cardScreen = null;
            _cardTargets = Array.Empty<PinnedPublicRewardCardTarget>();
            _skipButton = null;
            _activeCardReward = null;
            _pending = null;
            return true;
        }
    }

    public void PublishChild(
        PublicRewardDecisionSnapshot snapshot,
        NCardRewardSelectionScreen screen,
        Player player,
        IReadOnlyList<PinnedPublicRewardCardTarget> targets,
        NCardRewardAlternativeButton? skipButton)
    {
        lock (_gate)
        {
            _observedReady = true;
            _currentDecisionId = snapshot.DecisionId;
            _cardScreen = screen;
            _cardTargets = Copy(targets);
            _skipButton = skipButton;
            _player = player;
            _lastPlayer = snapshot.Player;
        }
    }

    public PublicRewardActionApplyOutcome? ReservationFailure(string decisionId)
    {
        lock (_gate)
        {
            if (_acceptedDecisionIds.Contains(decisionId))
            {
                return PublicRewardActionApplyOutcome.AlreadyApplied;
            }
            if (_acceptedActionCount >= PublicRewardActionBudget.MaximumAcceptedActionsPerSession ||
                _processAcceptedActionCount >= PublicRewardActionBudget.MaximumAcceptedActionsPerProcess)
            {
                return PublicRewardActionApplyOutcome.ActionLimitReached;
            }
            return null;
        }
    }

    public bool TryGetParentTarget(
        string decisionId,
        int rewardSlot,
        out NRewardsScreen? screen,
        out PinnedPublicRewardParentTarget? target)
    {
        lock (_gate)
        {
            screen = null;
            target = null;
            if (_pending is not null ||
                !string.Equals(_currentDecisionId, decisionId, StringComparison.Ordinal) ||
                rewardSlot < 0 || rewardSlot >= _parentTargets.Length)
            {
                return false;
            }

            PinnedPublicRewardParentTarget candidate = _parentTargets[rewardSlot];
            if (candidate.Slot != rewardSlot || _parentScreen is null)
            {
                return false;
            }
            screen = _parentScreen;
            target = candidate;
            return true;
        }
    }

    public bool TryGetParentScreen(string decisionId, out NRewardsScreen? screen)
    {
        lock (_gate)
        {
            screen = null;
            if (_pending is not null ||
                !string.Equals(_currentDecisionId, decisionId, StringComparison.Ordinal) ||
                _parentScreen is null)
            {
                return false;
            }
            screen = _parentScreen;
            return true;
        }
    }

    public bool TryGetCardTarget(
        string decisionId,
        int cardSlot,
        out NCardRewardSelectionScreen? screen,
        out PinnedPublicRewardCardTarget? target)
    {
        lock (_gate)
        {
            screen = null;
            target = null;
            if (_pending is not null ||
                !string.Equals(_currentDecisionId, decisionId, StringComparison.Ordinal) ||
                cardSlot < 0 || cardSlot >= _cardTargets.Length)
            {
                return false;
            }

            PinnedPublicRewardCardTarget candidate = _cardTargets[cardSlot];
            if (candidate.Slot != cardSlot || _cardScreen is null)
            {
                return false;
            }
            screen = _cardScreen;
            target = candidate;
            return true;
        }
    }

    public bool TryGetSkipTarget(
        string decisionId,
        out NCardRewardSelectionScreen? screen,
        out NCardRewardAlternativeButton? skipButton)
    {
        lock (_gate)
        {
            screen = null;
            skipButton = null;
            if (_pending is not null ||
                !string.Equals(_currentDecisionId, decisionId, StringComparison.Ordinal) ||
                _cardScreen is null || _skipButton is null)
            {
                return false;
            }
            screen = _cardScreen;
            skipButton = _skipButton;
            return true;
        }
    }

    public PublicRewardActionApplyOutcome? Begin(
        string decisionId,
        PinnedPublicRewardPendingMutation pending)
    {
        lock (_gate)
        {
            PublicRewardActionApplyOutcome? failure = ReservationFailure(decisionId);
            if (failure.HasValue)
            {
                return failure;
            }
            if (_pending is not null ||
                !string.Equals(_currentDecisionId, decisionId, StringComparison.Ordinal))
            {
                return PublicRewardActionApplyOutcome.StaleDecision;
            }

            _acceptedDecisionIds.Add(decisionId);
            _acceptedActionCount++;
            _processAcceptedActionCount++;
            _pending = pending;
            if (pending.Kind == PublicRewardActionKind.OpenCard)
            {
                _activeCardReward = pending.ParentTarget;
            }
            return null;
        }
    }

    public void ResolveClaim(PublicRewardPlayer player)
    {
        lock (_gate)
        {
            Resolve(player);
        }
    }

    public void ResolveOpen(PublicRewardPlayer player)
    {
        lock (_gate)
        {
            Resolve(player);
        }
    }

    public void ResolveChoice(PublicRewardPlayer player)
    {
        lock (_gate)
        {
            _activeCardReward = null;
            Resolve(player);
        }
    }

    public void ResolveSkip(PublicRewardPlayer player)
    {
        lock (_gate)
        {
            if (_activeCardReward is not null)
            {
                _skippedCardRewards.Add(_activeCardReward.Reward);
            }
            _activeCardReward = null;
            Resolve(player);
        }
    }

    public void ResolveProceed(PublicRewardPlayer player)
    {
        lock (_gate)
        {
            Resolve(player);
            _completedSession = true;
        }
    }

    public void ObserveComplete(PublicRewardPlayer player)
    {
        lock (_gate)
        {
            _lastPlayer = player;
            _completedSession = true;
        }
    }

    public bool WasSkipped(Reward reward)
    {
        lock (_gate)
        {
            foreach (Reward skipped in _skippedCardRewards)
            {
                if (ReferenceEquals(skipped, reward))
                {
                    return true;
                }
            }
            return false;
        }
    }

    public void FailClosed()
    {
        lock (_gate)
        {
            _unsupported = true;
            _currentDecisionId = string.Empty;
            _parentTargets = Array.Empty<PinnedPublicRewardParentTarget>();
            _cardTargets = Array.Empty<PinnedPublicRewardCardTarget>();
        }
    }

#if STS2_AGENT_BRIDGE_TEST_SEAM
    internal bool BeginSessionForTest()
    {
        lock (_gate)
        {
            if (_rewardSessionCount >= PublicRewardActionBudget.MaximumRewardSessionsPerProcess)
            {
                return false;
            }
            _rewardSessionCount++;
            _acceptedActionCount = 0;
            _acceptedDecisionIds.Clear();
            _decisionRevision = 0;
            _completedSession = false;
            _currentDecisionId = string.Empty;
            _pending = null;
            return true;
        }
    }

    internal void SeedDecisionForTest(string decisionId)
    {
        lock (_gate)
        {
            _currentDecisionId = decisionId;
        }
    }

    internal int AcceptedDecisionCountForTest
    {
        get
        {
            lock (_gate)
            {
                return _acceptedDecisionIds.Count;
            }
        }
    }
#endif

    private void Resolve(PublicRewardPlayer player)
    {
        _pending = null;
        _currentDecisionId = string.Empty;
        _decisionRevision++;
        _lastPlayer = player;
        _parentTargets = Array.Empty<PinnedPublicRewardParentTarget>();
        _cardTargets = Array.Empty<PinnedPublicRewardCardTarget>();
    }

    private static PinnedPublicRewardParentTarget[] Copy(
        IReadOnlyList<PinnedPublicRewardParentTarget> targets)
    {
        var copy = new PinnedPublicRewardParentTarget[targets.Count];
        for (int index = 0; index < targets.Count; index++)
        {
            copy[index] = targets[index];
        }
        return copy;
    }

    private static PinnedPublicRewardCardTarget[] Copy(
        IReadOnlyList<PinnedPublicRewardCardTarget> targets)
    {
        var copy = new PinnedPublicRewardCardTarget[targets.Count];
        for (int index = 0; index < targets.Count; index++)
        {
            copy[index] = targets[index];
        }
        return copy;
    }
}
