using System;
using System.Collections.Generic;
using System.Linq;
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

// A special reward inserts its specified mutable model directly; there is no chooser.
// Preserve every existing card so a same-key replacement or unrelated deck edit
// cannot masquerade as the requested grant.
internal sealed class PinnedPublicSpecialCardClaim
{
    internal static CardModel? Card(Reward reward) => reward.GetType() == typeof(SpecialCardReward)
        ? typeof(SpecialCardReward).GetField("_card", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)?.GetValue(reward) as CardModel : null;
    private readonly Player _player;
    private readonly object _run;
    private readonly CardModel _card;
    private readonly (CardModel Model, string Key, int Level, object? Enchantment, int Amount)[] _before;
    private readonly string _key;
    private readonly int _level;
    private readonly object? _enchantment;
    private readonly int _amount;
    internal PinnedPublicSpecialCardClaim(Player player, CardModel card)
    {
        _player=player;_run=player.RunState;_card=card;_key=card.Id.Entry;_level=card.CurrentUpgradeLevel;
        _enchantment=card.Enchantment;_amount=card.Enchantment?.Amount??0;
        var deck=player.Deck.Cards;
        if(deck.Count is <1 or >511 || !ReferenceEquals(card.Owner,player) || !ReferenceEquals(card.RunState,_run))
            throw new InvalidOperationException("Special card owner or deck unavailable.");
        _before=new (CardModel, string, int, object?, int)[deck.Count];
        var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
        for(int i=0;i<deck.Count;i++) {
            var c=deck[i];
            if(ReferenceEquals(c,card)||!seen.Add(c)||!ReferenceEquals(c.Owner,player)||!ReferenceEquals(c.RunState,_run))
                throw new InvalidOperationException("Special card baseline unavailable.");
            _before[i]=(c,c.Id.Entry,c.CurrentUpgradeLevel,c.Enchantment,c.Enchantment?.Amount??0);
        }
    }
    internal bool Valid(Reward reward, bool inserted)
    {
        if(!ReferenceEquals(reward.Player,_player)||!ReferenceEquals(_player.RunState,_run)||!ReferenceEquals(Card(reward),_card)||
            !ReferenceEquals(_card.Owner,_player)||!ReferenceEquals(_card.RunState,_run)||_card.Id.Entry!=_key||
            _card.CurrentUpgradeLevel!=_level||!ReferenceEquals(_card.Enchantment,_enchantment)||(_card.Enchantment?.Amount??0)!=_amount)return false;
        var deck=_player.Deck.Cards;
        if(deck.Count!=_before.Length+(inserted?1:0))return false;
        int index=0,added=0;
        foreach(var card in deck) {
            if(ReferenceEquals(card,_card)){added++;continue;}
            if(index>=_before.Length)return false;
            var old=_before[index++];
            if(!ReferenceEquals(card,old.Model)||card.Id.Entry!=old.Key||card.CurrentUpgradeLevel!=old.Level||
                !ReferenceEquals(card.Enchantment,old.Enchantment)||(card.Enchantment?.Amount??0)!=old.Amount||
                !ReferenceEquals(card.Owner,_player)||!ReferenceEquals(card.RunState,_run))return false;
        }
        return index==_before.Length&&added==(inserted?1:0);
    }
}

internal sealed class PinnedPublicRewardPendingMutation
{
    public PinnedPublicRewardPendingMutation(
        PublicRewardActionKind kind,
        PublicRewardPlayer beforePlayer,
        PinnedPublicRewardParentTarget? parentTarget = null,
        PinnedPublicRewardCardTarget? cardTarget = null,
        int chosenCardCopiesBefore = -1,
        PinnedPublicSpecialCardClaim? specialCard = null,
        NRewardsScreen? parentScreen = null,
        PinnedPublicItemRewardClaim? item = null,
        IReadOnlyList<PinnedPublicItemRewardClaim>? unclaimedPotions = null,
        PinnedPublicPotionDiscard? discard = null)
    {
        Kind = kind;
        BeforePlayer = beforePlayer;
        ParentTarget = parentTarget;
        CardTarget = cardTarget;
        ChosenCardCopiesBefore = chosenCardCopiesBefore;
        SpecialCard = specialCard; ParentScreen = parentScreen; Item=item; UnclaimedPotions=unclaimedPotions??Array.Empty<PinnedPublicItemRewardClaim>(); Discard=discard;
    }

    public PublicRewardActionKind Kind { get; }

    public PublicRewardPlayer BeforePlayer { get; }

    public PinnedPublicRewardParentTarget? ParentTarget { get; }

    public PinnedPublicRewardCardTarget? CardTarget { get; }

    public int ChosenCardCopiesBefore { get; }
    internal PinnedPublicSpecialCardClaim? SpecialCard { get; }
    internal NRewardsScreen? ParentScreen { get; }
    internal PinnedPublicItemRewardClaim? Item { get; }
    internal PinnedPublicPotionDiscard? Discard { get; }
    internal IReadOnlyList<PinnedPublicItemRewardClaim> UnclaimedPotions { get; }
    internal System.Threading.Tasks.Task? ProceedTask { get; set; }
    internal bool UnclaimedPotionsValid() {foreach(var potion in UnclaimedPotions)if(!potion.Unclaimed)return false;return true;}
}

internal sealed class PinnedPublicRewardInteractionSession
{
    private readonly object _gate = new();
    private readonly HashSet<string> _acceptedDecisionIds = new(StringComparer.Ordinal);
    private readonly List<Reward> _skippedCardRewards = new();
    private readonly List<PinnedPublicRewardParentTarget> _specialTargets = new();

    private PotionModel?[]? _initialPotions;
    private string?[]? _initialPotionKeys;
    internal bool CanDiscard(Player player,int slot) => _initialPotions is not null && slot>=0 && slot<_initialPotions.Length &&
        player.CanRemovePotions && player.PotionSlots.Count==_initialPotions.Length &&
        _initialPotions[slot] is {} potion && ReferenceEquals(player.PotionSlots[slot],potion) &&
        potion.Id.Entry==_initialPotionKeys![slot] && ReferenceEquals(potion.Owner,player) && !potion.IsQueued && !potion.HasBeenRemovedFromState;
    private Dictionary<Reward,(int Ordinal,int Native)>? _itemDomain;
    private readonly List<(Reward Reward,NRewardButton Button,object Model,string Key)> _itemTargets=new();
    private readonly List<PinnedPublicItemRewardClaim> _settledItems=new();
    internal bool CapacityRewards {get;private set;}
    internal bool HealingRewards {get;private set;}
    internal bool UsesItemIndices => _itemDomain is not null;
    internal bool SettledItemsValid() {
        var growth=_pending?.Item;
        int capacity=growth is {PotionCapacityGain:>0} && growth.Valid(true)?growth.ResultCapacity:-1;
        return _settledItems.TrueForAll(item=>item.SettledValid(capacity));
    }
    internal void SettleItem(PinnedPublicItemRewardClaim item) {
        item.Settle();
        if(item.PotionCapacityGain>0) {
            foreach(var settled in _settledItems)settled.AcceptCapacity(item.ResultCapacity);
            Array.Resize(ref _initialPotions,item.ResultCapacity);
            Array.Resize(ref _initialPotionKeys,item.ResultCapacity);
        }
        _settledItems.Add(item);
    }
    internal bool ForceRewardOrdinals;
    internal void BindRewardDomain(List<(NRewardButton Button,Reward Reward)> rows)
    {
        if(_itemDomain is null&&(ForceRewardOrdinals||rows.Exists(row=>row.Reward.GetType()==typeof(PotionReward)||row.Reward.GetType()==typeof(RelicReward)))) {
            if(!PinnedPublicItemRewardClaim.Slots(rows[0].Reward.Player,out _initialPotions))throw new InvalidOperationException("Potion inventory unavailable.");
            _initialPotionKeys=_initialPotions.Select(PinnedPublicItemRewardClaim.Key).ToArray();
            _itemDomain=new(ReferenceEqualityComparer.Instance);
            for(int i=0;i<rows.Count;i++)_itemDomain.Add(rows[i].Reward,(i,rows[i].Reward.RewardsSetIndex));
        }
        if(_itemDomain is null)return;
        HealingRewards |= rows.Any(row=>PinnedPublicItemRewardClaim.HealingReward(row.Reward));
        CapacityRewards |= HealingRewards || rows.Any(row=>PinnedPublicItemRewardClaim.CapacityGain(row.Reward)>0);
        foreach(var row in rows)if(!_itemDomain.TryGetValue(row.Reward,out var entry)||entry.Native!=row.Reward.RewardsSetIndex)
            throw new InvalidOperationException("Item reward domain replaced.");
        foreach(var reward in _itemDomain.Keys)if(!reward.SuccessfullySelected&&!WasSkipped(reward)&&!rows.Exists(row=>ReferenceEquals(row.Reward,reward)))
            throw new InvalidOperationException("Uncollected reward disappeared.");
        rows.Sort((left,right)=>_itemDomain[left.Reward].Ordinal.CompareTo(_itemDomain[right.Reward].Ordinal));
    }
    internal int RewardIndex(Reward reward) => _itemDomain is null?reward.RewardsSetIndex:_itemDomain[reward].Ordinal;

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
            foreach(var old in _itemTargets) {
                if(!ReferenceEquals(PinnedPublicItemRewardClaim.Model(old.Reward),old.Model)||PinnedPublicItemRewardClaim.Key(old.Model)!=old.Key||
                    !ReferenceEquals(old.Reward.Player,player))throw new InvalidOperationException("Item reward model changed.");
                foreach(var target in targets)if(ReferenceEquals(target.Reward,old.Reward)&&!ReferenceEquals(target.Button,old.Button))
                    throw new InvalidOperationException("Item reward button changed.");
            }
            foreach(var target in targets)if(target.Projection.Kind is PublicRewardKind.Potion or PublicRewardKind.Relic&&
                !_itemTargets.Exists(old=>ReferenceEquals(old.Reward,target.Reward))) {
                if(_itemTargets.Count>=8)throw new InvalidOperationException("Item reward domain limit.");
                _itemTargets.Add((target.Reward,target.Button,PinnedPublicItemRewardClaim.Model(target.Reward)!,target.Projection.ItemKey!));
            }
            foreach(var old in _specialTargets) {
                var card=old.OfferedCards[0];
                if(!ReferenceEquals(PinnedPublicSpecialCardClaim.Card(old.Reward),card)||card.Id.Entry!=old.Projection.Cards[0]||
                    !ReferenceEquals(old.Reward.Player,player)||!ReferenceEquals(card.Owner,player)||!ReferenceEquals(card.RunState,player.RunState))
                    throw new InvalidOperationException("Special reward identity changed.");
                bool found=false;
                foreach(var target in targets)if(target.Projection.RewardIndex==old.Projection.RewardIndex) {
                    if(!ReferenceEquals(target.Reward,old.Reward)||!ReferenceEquals(target.Button,old.Button))
                        throw new InvalidOperationException("Special reward replaced.");
                    found=true;
                }
                if(!found&&!old.Reward.SuccessfullySelected)throw new InvalidOperationException("Special reward disappeared.");
            }
            foreach(var target in targets)if(target.Reward.GetType()==typeof(SpecialCardReward)&&
                !_specialTargets.Exists(old=>ReferenceEquals(old.Reward,target.Reward)))_specialTargets.Add(target);
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
            _specialTargets.Clear();
            _itemDomain=null;CapacityRewards=false;HealingRewards=false;_initialPotions=null;_initialPotionKeys=null;_itemTargets.Clear();_settledItems.Clear();
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
            _settledItems.Clear();
        }
    }

    public void ObserveComplete(PublicRewardPlayer player)
    {
        lock (_gate)
        {
            _lastPlayer = player;
            _completedSession = true;
            _settledItems.Clear();
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
            _pending?.Discard?.Abort();
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
