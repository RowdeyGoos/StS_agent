using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicRewardDecisionReader : IPublicRewardDecisionReader, IDisposable
{
    private const int MaximumTraversedNodes = 2048;
    private const int MaximumRewards = 8;
    private const int MaximumCardsPerReward = 5;

    private readonly PinnedPublicRewardInteractionSession _session = new();

    private readonly Func<bool>? _nestedScope;
    private readonly NRewardsScreen? _nestedScreen;
    private readonly Func<bool>? _nestedClosed;
    public PinnedPublicRewardDecisionReader() { }
    internal PinnedPublicRewardDecisionReader(NRewardsScreen screen,Func<bool> scope,Func<bool> closed) {_nestedScreen=screen;_nestedScope=scope;_nestedClosed=closed;_session.ForceRewardOrdinals=true;}
    internal PinnedPublicRewardInteractionSession InteractionSession => _session;

    public void Dispose()
    {
        bool pendingDiscard=_session.Pending?.Discard is not null;
        _session.FailClosed();
        if(pendingDiscard)throw new InvalidOperationException("Unresolved potion discard at cleanup.");
    }

    public PublicRewardDecisionSnapshot Read()
    {
        if (_nestedScope is not null && !_nestedScope())return FailClosed();
        if (_session.IsUnsupported || !_session.SettledItemsValid())
        {
            return FailClosed();
        }

        if(_nestedClosed?.Invoke()==true) {
            if(_session.Pending is {} nestedPending)ReconcileNestedClosed(nestedPending);
            if(_session.IsUnsupported)return FailClosed();
            return _session.Pending is null?PublicRewardDecisionSnapshot.Complete(ProjectPlayer(_session.Player!),_session.DecisionRevision):PublicRewardDecisionSnapshot.Waiting();
        }
        var proceeding=_session.Pending;
        if(proceeding?.Kind==PublicRewardActionKind.Proceed &&
            (!proceeding.UnclaimedPotionsValid()||proceeding.ProceedTask is null||proceeding.ProceedTask.IsFaulted||proceeding.ProceedTask.IsCanceled))return FailClosed();

        if(_session.Pending?.Discard is {} discard) {
            var state=discard.Read();
            if(state<0)return FailClosed();
            if(state==0)return PublicRewardDecisionSnapshot.Waiting();
            _session.ResolveClaim(ProjectPlayer(_session.Player!));
            return ReadParent(discard.Screen);
        }

        NRun? run = NRun.Instance;
        if (run is null || !GodotObject.IsInstanceValid(run))
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        var globalUi = run.GlobalUi;
        if (globalUi is null || !GodotObject.IsInstanceValid(globalUi))
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        var map = globalUi.MapScreen;
        if (map is not null && GodotObject.IsInstanceValid(map) && map.IsOpen &&
            _session.ObservedReady)
        {
            Player? terminalPlayer = _session.Player;
            if (terminalPlayer is null)
            {
                return FailClosed();
            }

            PublicRewardPlayer projected = ProjectPlayer(terminalPlayer);
            PinnedPublicRewardPendingMutation? pendingAtMap = _session.Pending;
            if (pendingAtMap is not null)
            {
                if (pendingAtMap.Kind != PublicRewardActionKind.Proceed ||
                    !SamePlayer(projected, pendingAtMap.BeforePlayer))
                {
                    return FailClosed();
                }
                if(!pendingAtMap.ProceedTask!.IsCompletedSuccessfully)return PublicRewardDecisionSnapshot.Waiting();
                _session.ResolveProceed(projected);
            }
            else
            {
                _session.ObserveComplete(projected);
            }
            return PublicRewardDecisionSnapshot.Complete(
                projected,
                _session.DecisionRevision);
        }

        NOverlayStack? overlays = globalUi.Overlays;
        if(proceeding?.Kind==PublicRewardActionKind.Proceed && proceeding.UnclaimedPotions.Count>0 &&
            overlays is not null && overlays.ScreenCount>0 &&
            (overlays.ScreenCount!=1||!ReferenceEquals(overlays.Peek(),proceeding.ParentScreen)))return FailClosed();
        if (_session.Pending?.Item is not null && (overlays is null || overlays.ScreenCount != (_nestedScreen is null?1:2) ||
            !ReferenceEquals(overlays.Peek(),_session.Pending.ParentScreen)))return FailClosed();
        if (overlays is null || !GodotObject.IsInstanceValid(overlays) || overlays.ScreenCount == 0)
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        object? topOverlay = overlays.Peek();
        if (topOverlay is not Node top || top is not CanvasItem topCanvas ||
            !GodotObject.IsInstanceValid(top) || !topCanvas.IsVisibleInTree())
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        PinnedPublicRewardPendingMutation? pending = _session.Pending;
        if (pending is not null)
        {
            return Reconcile(pending, top);
        }

        if (top is NRewardsScreen rewardsScreen)
        {
            return ReadParent(rewardsScreen);
        }
        if (top is NCardRewardSelectionScreen cardScreen && _session.ActiveCardReward is not null)
        {
            return ReadChild(cardScreen);
        }

        return PublicRewardDecisionSnapshot.Waiting();
    }

    // Offer completion can free the screen/buttons before the next read. The
    // owned nested caller verifies its collection Task; use retained effect data.
    private void ReconcileNestedClosed(PinnedPublicRewardPendingMutation pending) {
        var target=pending.ParentTarget;var player=_session.Player;
        if(target is null||player is null){FailClosed();return;}
        var after=ProjectPlayer(player);
        bool good=pending.Kind switch {
            PublicRewardActionKind.ClaimGold=>target.Reward is GoldReward gold&&target.Reward.SuccessfullySelected&&gold.Amount==target.Projection.GoldAmount&&SameHealth(after,pending.BeforePlayer)&&after.DeckCount==pending.BeforePlayer.DeckCount&&(long)after.Gold==(long)pending.BeforePlayer.Gold+target.Projection.GoldAmount,
            PublicRewardActionKind.CollectItem=>target.Reward.SuccessfullySelected&&pending.Item?.Completed==true&&SamePlayer(after,pending.BeforePlayer),
            PublicRewardActionKind.ChooseCard=>target.Reward.SuccessfullySelected&&pending.CardTarget is {} card&&SameHealth(after,pending.BeforePlayer)&&after.Gold==pending.BeforePlayer.Gold&&after.DeckCount==pending.BeforePlayer.DeckCount+1&&CountCardCopies(player,card.Model.Id.Entry)==pending.ChosenCardCopiesBefore+1,
            PublicRewardActionKind.SkipCard=>!target.Reward.SuccessfullySelected&&SamePlayer(after,pending.BeforePlayer),
            _=>false};
        if(!good){FailClosed();return;}
        if(pending.Kind==PublicRewardActionKind.CollectItem)_session.SettleItem(pending.Item!);
        if(pending.Kind==PublicRewardActionKind.ChooseCard)_session.ResolveChoice(after);
        else if(pending.Kind==PublicRewardActionKind.SkipCard)_session.ResolveSkip(after);
        else _session.ResolveClaim(after);
    }
    private PublicRewardDecisionSnapshot Reconcile(
        PinnedPublicRewardPendingMutation pending,
        Node top)
    {
        return pending.Kind switch
        {
            PublicRewardActionKind.ClaimGold => ReconcileClaim(pending, top),
            PublicRewardActionKind.ClaimSpecialCard => ReconcileSpecialCard(pending, top),
            PublicRewardActionKind.CollectItem => ReconcileItem(pending, top),
            PublicRewardActionKind.OpenCard => ReconcileOpen(pending, top),
            PublicRewardActionKind.ChooseCard => ReconcileChoice(pending, top),
            PublicRewardActionKind.SkipCard => ReconcileSkip(pending, top),
            PublicRewardActionKind.Proceed => PublicRewardDecisionSnapshot.Waiting(),
            _ => FailClosed(),
        };
    }

    private PublicRewardDecisionSnapshot ReconcileItem(PinnedPublicRewardPendingMutation pending, Node top)
    {
        var target=pending.ParentTarget;var item=pending.Item;
        if(target is null||item is null||!ReferenceEquals(top,pending.ParentScreen)||top is not NRewardsScreen screen||
            !ReferenceEquals(target.Button.Reward,target.Reward))return FailClosed();
        if(!target.Reward.SuccessfullySelected) {
            if(!ContainsNode(screen,target.Button)||(!item.Valid(false)&&!item.Valid(true)))return FailClosed();
            return PublicRewardDecisionSnapshot.Waiting();
        }
        var player=ProjectPlayer(target.Reward.Player);
        if(!item.Completed||!SamePlayer(player,pending.BeforePlayer))return FailClosed();
        _session.SettleItem(item);_session.ResolveClaim(player);
        return ReadParent(screen);
    }

    private PublicRewardDecisionSnapshot ReconcileSpecialCard(PinnedPublicRewardPendingMutation pending, Node top)
    {
        var target=pending.ParentTarget;
        if(target is null||pending.SpecialCard is null||!ReferenceEquals(top,pending.ParentScreen)||top is not NRewardsScreen screen ||
            !ReferenceEquals(target.Button.Reward,target.Reward)||target.Reward.ParentRewardSet is not null)
            return FailClosed();
        if(!target.Reward.SuccessfullySelected) {
            // The insertion may precede reward completion. Never dispatch again.
            if(!ContainsNode(screen,target.Button)||(!pending.SpecialCard.Valid(target.Reward,false)&&!pending.SpecialCard.Valid(target.Reward,true)))return FailClosed();
            return PublicRewardDecisionSnapshot.Waiting();
        }
        var after=ProjectPlayer(target.Reward.Player);
        if(!pending.SpecialCard.Valid(target.Reward,true)||!SameHealth(after,pending.BeforePlayer)||
            after.Gold!=pending.BeforePlayer.Gold||after.DeckCount!=pending.BeforePlayer.DeckCount+1)return FailClosed();
        _session.ResolveClaim(after);
        return ReadParent(screen);
    }

    private PublicRewardDecisionSnapshot ReconcileClaim(
        PinnedPublicRewardPendingMutation pending,
        Node top)
    {
        PinnedPublicRewardParentTarget? target = pending.ParentTarget;
        if (target is null || target.Reward is not GoldReward gold ||
            top is not NRewardsScreen screen)
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        if (ContainsNode(screen, target.Button) && !target.Reward.SuccessfullySelected)
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        PublicRewardPlayer after = ProjectPlayer(target.Reward.Player);
        if (!SameHealth(after, pending.BeforePlayer) ||
            after.DeckCount != pending.BeforePlayer.DeckCount ||
            (long)after.Gold != (long)pending.BeforePlayer.Gold + gold.Amount)
        {
            return FailClosed();
        }

        _session.ResolveClaim(after);
        return ReadParent(screen);
    }

    private PublicRewardDecisionSnapshot ReconcileOpen(
        PinnedPublicRewardPendingMutation pending,
        Node top)
    {
        PinnedPublicRewardParentTarget? target = pending.ParentTarget;
        if (target is null || target.Reward is not CardReward ||
            top is not NCardRewardSelectionScreen screen)
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        PublicRewardPlayer after = ProjectPlayer(target.Reward.Player);
        if (!SamePlayer(after, pending.BeforePlayer))
        {
            return FailClosed();
        }

        _session.ResolveOpen(after);
        return ReadChild(screen);
    }

    private PublicRewardDecisionSnapshot ReconcileChoice(
        PinnedPublicRewardPendingMutation pending,
        Node top)
    {
        PinnedPublicRewardParentTarget? parentTarget = pending.ParentTarget;
        PinnedPublicRewardCardTarget? cardTarget = pending.CardTarget;
        if (parentTarget is null || cardTarget is null ||
            top is not NRewardsScreen screen)
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        if (ContainsNode(screen, parentTarget.Button) &&
            !parentTarget.Reward.SuccessfullySelected)
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        Player player = parentTarget.Reward.Player;
        PublicRewardPlayer after = ProjectPlayer(player);
        int chosenCopiesAfter = CountCardCopies(player, cardTarget.Model.Id.Entry);
        if (!SameHealth(after, pending.BeforePlayer) ||
            after.Gold != pending.BeforePlayer.Gold ||
            after.DeckCount != pending.BeforePlayer.DeckCount + 1 ||
            chosenCopiesAfter != pending.ChosenCardCopiesBefore + 1)
        {
            return FailClosed();
        }

        _session.ResolveChoice(after);
        return ReadParent(screen);
    }

    private PublicRewardDecisionSnapshot ReconcileSkip(
        PinnedPublicRewardPendingMutation pending,
        Node top)
    {
        PinnedPublicRewardParentTarget? target = pending.ParentTarget;
        if (target is null || top is not NRewardsScreen screen)
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        PublicRewardPlayer after = ProjectPlayer(target.Reward.Player);
        if (!SamePlayer(after, pending.BeforePlayer))
        {
            return FailClosed();
        }

        _session.ResolveSkip(after);
        return ReadParent(screen);
    }

    private PublicRewardDecisionSnapshot ReadParent(NRewardsScreen screen)
    {
        if(_nestedScreen is not null) {
            if(!ReferenceEquals(screen,_nestedScreen))return FailClosed();
            if(_nestedClosed!.Invoke())return PublicRewardDecisionSnapshot.Complete(ProjectPlayer(_session.Player!),_session.DecisionRevision);
        }
        if (!GodotObject.IsInstanceValid(screen) || !screen.IsVisibleInTree())
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }
        if (!_session.PrepareParentScreen(screen))
        {
            return FailClosed();
        }

        if (!TryCollectParentTargets(
                screen,
                out List<PinnedPublicRewardParentTarget> targets,
                out bool waiting))
        {
            return waiting ? PublicRewardDecisionSnapshot.Waiting() : FailClosed();
        }

        Player? player = targets.Count > 0 ? targets[0].Reward.Player : _session.Player;
        if (player is null)
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        var rewards = new List<PublicRewardItem>(targets.Count);
        var legalActions = new List<string>(targets.Count + 1);
        foreach (PinnedPublicRewardParentTarget target in targets)
        {
            rewards.Add(target.Projection);
            if (target.Reward.SuccessfullySelected || _session.WasSkipped(target.Reward))
            {
                continue;
            }
            if (target.Reward is GoldReward)
            {
                legalActions.Add(PublicRewardActionRequest.ClaimGoldActionIdFor(target.Slot));
            }
            else if (target.Projection.Kind is PublicRewardKind.Potion or PublicRewardKind.Relic)
            {
                if(new PinnedPublicItemRewardClaim(target.Reward).HasCapacity)
                    legalActions.Add(PublicRewardActionRequest.CollectItemActionIdFor(target.Slot));
            }
            else if (target.Reward.GetType() == typeof(SpecialCardReward))
            {
                legalActions.Add(PublicRewardActionRequest.ClaimSpecialCardActionIdFor(target.Slot));
            }
            else if (target.Reward is CardReward)
            {
                legalActions.Add(PublicRewardActionRequest.OpenCardActionIdFor(target.Slot));
            }
        }
        if(_nestedScreen is null && _session.UsesItemIndices && targets.Any(t=>t.Projection.Kind==PublicRewardKind.Potion&&!t.Reward.SuccessfullySelected) &&
            PinnedPublicItemRewardClaim.Slots(player,out var belt)&&belt.Length>0&&belt.All(p=>p is not null)&&
            MegaCrit.Sts2.Core.Combat.CombatManager.Instance?.IsInProgress==false && PinnedPublicPotionDiscard.SingleplayerQueue()) {
            for(int slot=0;slot<belt.Length;slot++)if(_session.CanDiscard(player,slot))legalActions.Add("discard:"+slot);
        }
        if(_nestedScreen is null)legalActions.Add(PublicRewardActionRequest.ProceedActionId);

        PublicRewardPlayer projectedPlayer = ProjectPlayer(player);
        var snapshot = new PublicRewardDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "rewards",
            projectedPlayer,
            rewards,
            legalActions,
            _session.DecisionRevision, _session.UsesItemIndices, PotionKeys(player), _session.CapacityRewards);
        snapshot = snapshot with
        {
            DecisionId = PublicRewardDecisionIdentity.Compute(snapshot),
        };
        _session.PublishParent(snapshot, screen, player, targets);
        return snapshot;
    }

    private string?[]? PotionKeys(Player player) {
        if(!_session.UsesItemIndices)return null;
        if(!PinnedPublicItemRewardClaim.Slots(player,out var slots))throw new InvalidOperationException("Potion inventory unavailable.");
        return slots.Select(PinnedPublicItemRewardClaim.Key).ToArray();
    }

    private PublicRewardDecisionSnapshot ReadChild(NCardRewardSelectionScreen screen)
    {
        PinnedPublicRewardParentTarget? parentTarget = _session.ActiveCardReward;
        if (parentTarget is null || parentTarget.Reward is not CardReward cardReward ||
            !GodotObject.IsInstanceValid(screen) || !screen.IsVisibleInTree())
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }

        if (!TryCollectVisibleCardTargets(
                screen,
                parentTarget,
                out List<PinnedPublicRewardCardTarget> cardTargets))
        {
            return PublicRewardDecisionSnapshot.Waiting();
        }
        if (cardTargets.Count == 0 || cardTargets.Count > MaximumCardsPerReward)
        {
            return FailClosed();
        }

        if (!TryFindSkipButton(
                screen,
                cardReward.CanSkip,
                out NCardRewardAlternativeButton? skipButton,
                out bool waiting))
        {
            return waiting ? PublicRewardDecisionSnapshot.Waiting() : FailClosed();
        }

        var legalActions = new List<string>(cardTargets.Count + 1);
        foreach (PinnedPublicRewardCardTarget target in cardTargets)
        {
            legalActions.Add(PublicRewardActionRequest.ChooseCardActionIdFor(target.Slot));
        }
        bool skipAvailable = cardReward.CanSkip && skipButton is not null;
        if (skipAvailable)
        {
            legalActions.Add(PublicRewardActionRequest.SkipCardActionId);
        }

        Player player = cardReward.Player;
        PublicRewardPlayer projectedPlayer = ProjectPlayer(player);
        var snapshot = new PublicRewardDecisionSnapshot(
            PublicDecisionStatus.Ready,
            string.Empty,
            "card_reward",
            projectedPlayer,
            new[] { parentTarget.Projection with { CardSelectionCanSkip = skipAvailable } },
            legalActions,
            _session.DecisionRevision, _session.UsesItemIndices, PotionKeys(cardReward.Player), _session.CapacityRewards);
        snapshot = snapshot with
        {
            DecisionId = PublicRewardDecisionIdentity.Compute(snapshot),
        };
        _session.PublishChild(snapshot, screen, player, cardTargets, skipButton);
        return snapshot;
    }

    private static bool TryCollectVisibleCardTargets(
        NCardRewardSelectionScreen screen,
        PinnedPublicRewardParentTarget parentTarget,
        out List<PinnedPublicRewardCardTarget> targets)
    {
        targets = new List<PinnedPublicRewardCardTarget>(parentTarget.OfferedCards.Count);
        var holders = new List<NCardHolder>();
        var pending = new List<Node> { screen };
        for (int cursor = 0; cursor < pending.Count; cursor++)
        {
            if (pending.Count > MaximumTraversedNodes)
            {
                return false;
            }
            Node node = pending[cursor];
            if (node is NCardHolder holder && GodotObject.IsInstanceValid(holder) &&
                holder.IsVisibleInTree() && holder.CardModel is not null)
            {
                if (holders.Count >= MaximumCardsPerReward)
                {
                    return false;
                }
                holders.Add(holder);
            }
            if (!AppendChildren(node, pending))
            {
                return false;
            }
        }
        if (holders.Count != parentTarget.OfferedCards.Count)
        {
            return false;
        }

        var used = new bool[holders.Count];
        for (int cardSlot = 0; cardSlot < parentTarget.OfferedCards.Count; cardSlot++)
        {
            string offeredId = parentTarget.OfferedCards[cardSlot].Id.Entry;
            int match = -1;
            for (int holderIndex = 0; holderIndex < holders.Count; holderIndex++)
            {
                CardModel? displayed = holders[holderIndex].CardModel;
                if (!used[holderIndex] && displayed is not null &&
                    string.Equals(displayed.Id.Entry, offeredId, StringComparison.Ordinal))
                {
                    match = holderIndex;
                    break;
                }
            }
            if (match < 0)
            {
                return false;
            }
            used[match] = true;
            NCardHolder matchedHolder = holders[match];
            CardModel? displayedModel = matchedHolder.CardModel;
            if (displayedModel is null)
            {
                return false;
            }
            targets.Add(new PinnedPublicRewardCardTarget(
                cardSlot,
                matchedHolder,
                displayedModel));
        }
        return true;
    }

    private bool TryCollectParentTargets(
        NRewardsScreen screen,
        out List<PinnedPublicRewardParentTarget> targets,
        out bool waiting)
    {
        targets = new List<PinnedPublicRewardParentTarget>();
        waiting = false;
        var unsorted = new List<(NRewardButton Button, Reward Reward)>();
        var pending = new List<Node> { screen };
        for (int cursor = 0; cursor < pending.Count; cursor++)
        {
            if (pending.Count > MaximumTraversedNodes)
            {
                return false;
            }

            Node node = pending[cursor];
            if (node is NRewardButton button)
            {
                if (!GodotObject.IsInstanceValid(button))
                {
                    return false;
                }
                if (!button.IsVisibleInTree())
                {
                    if (!AppendChildren(node, pending))
                    {
                        return false;
                    }
                    continue;
                }
                if (!button.IsEnabled)
                {
                    waiting = true;
                    return false;
                }
                Reward? reward = button.Reward;
                if (reward is null)
                {
                    return false;
                }
                foreach ((NRewardButton _, Reward existing) in unsorted)
                {
                    if (ReferenceEquals(existing, reward))
                    {
                        return false;
                    }
                }
                if (unsorted.Count >= MaximumRewards)
                {
                    return false;
                }
                unsorted.Add((button, reward));
            }

            if (!AppendChildren(node, pending))
            {
                return false;
            }
        }

        for (int index = 1; index < unsorted.Count; index++)
        {
            (NRewardButton Button, Reward Reward) current = unsorted[index];
            int insertion = index - 1;
            while (insertion >= 0 &&
                unsorted[insertion].Reward.RewardsSetIndex > current.Reward.RewardsSetIndex)
            {
                unsorted[insertion + 1] = unsorted[insertion];
                insertion--;
            }
            unsorted[insertion + 1] = current;
        }
        _session.BindRewardDomain(unsorted);
        Player? player = null;
        int previousIndex = -1;
        for (int slot = 0; slot < unsorted.Count; slot++)
        {
            (NRewardButton button, Reward reward) = unsorted[slot];
            if (!reward.IsPopulated || reward.RewardsSetIndex < 0 ||
                _session.RewardIndex(reward) == previousIndex)
            {
                return false;
            }
            previousIndex = _session.RewardIndex(reward);
            int rewardIndex=previousIndex;
            if (player is null)
            {
                player = reward.Player;
            }
            else if (!ReferenceEquals(player, reward.Player))
            {
                return false;
            }

            if (reward is GoldReward gold)
            {
                if (gold.Amount < 0)
                {
                    return false;
                }
                targets.Add(new PinnedPublicRewardParentTarget(
                    slot,
                    button,
                    reward,
                    new PublicRewardItem(
                        rewardIndex,
                        PublicRewardKind.Gold,
                        reward.SuccessfullySelected,
                        gold.Amount,
                        Array.Empty<string>(),
                        false),
                    Array.Empty<CardModel>()));
                continue;
            }

            if (reward.GetType() == typeof(PotionReward) || reward.GetType() == typeof(RelicReward))
            {
                var model=PinnedPublicItemRewardClaim.Model(reward);var key=PinnedPublicItemRewardClaim.Key(model);
                if(!PinnedPublicItemRewardClaim.ValidKey(key)||reward.ParentRewardSet is not null)return false;
                if(!reward.SuccessfullySelected)_=new PinnedPublicItemRewardClaim(reward);
                targets.Add(new PinnedPublicRewardParentTarget(slot,button,reward,
                    new PublicRewardItem(rewardIndex,model is PotionModel?PublicRewardKind.Potion:PublicRewardKind.Relic,
                        reward.SuccessfullySelected,0,Array.Empty<string>(),false,key,PinnedPublicItemRewardClaim.CapacityGain(reward)),Array.Empty<CardModel>()));
                continue;
            }

            if (reward.GetType() == typeof(SpecialCardReward))
            {
                var card=PinnedPublicSpecialCardClaim.Card(reward);
                if(card is null||reward.ParentRewardSet is not null||!ReferenceEquals(card.Owner,reward.Player)||
                    !ReferenceEquals(card.RunState,reward.Player.RunState))return false;
                if(!reward.SuccessfullySelected) {
                    var baseline=new PinnedPublicSpecialCardClaim(reward.Player,card);
                    if(!baseline.Valid(reward,false))return false;
                }
                targets.Add(new PinnedPublicRewardParentTarget(slot,button,reward,
                    new PublicRewardItem(rewardIndex,PublicRewardKind.SpecialCard,reward.SuccessfullySelected,
                        0,new[]{card.Id.Entry},false),new[]{card}));
                continue;
            }

            if (reward is CardReward cardReward)
            {
                var models = new List<CardModel>();
                var cardIds = new List<string>();
                foreach (CardModel card in cardReward.Cards)
                {
                    if (models.Count >= MaximumCardsPerReward)
                    {
                        return false;
                    }
                    models.Add(card);
                    cardIds.Add(card.Id.Entry);
                }
                if (models.Count == 0)
                {
                    waiting = true;
                    return false;
                }
                targets.Add(new PinnedPublicRewardParentTarget(
                    slot,
                    button,
                    reward,
                    new PublicRewardItem(
                        rewardIndex,
                        PublicRewardKind.Card,
                        reward.SuccessfullySelected,
                        0,
                        cardIds,
                        cardReward.CanSkip),
                    models));
                continue;
            }

            targets.Add(new PinnedPublicRewardParentTarget(
                slot,
                button,
                reward,
                new PublicRewardItem(
                    rewardIndex,
                    PublicRewardKind.Unsupported,
                    reward.SuccessfullySelected,
                    0,
                    Array.Empty<string>(),
                    false),
                Array.Empty<CardModel>()));
        }
        return true;
    }

    private bool TryFindSkipButton(
        Node root,
        bool canSkip,
        out NCardRewardAlternativeButton? skipButton,
        out bool waiting)
    {
        skipButton = null;
        waiting = false;
        int visibleAlternativeCount = 0;
        var pending = new List<Node> { root };
        for (int cursor = 0; cursor < pending.Count; cursor++)
        {
            if (pending.Count > MaximumTraversedNodes)
            {
                return false;
            }
            Node node = pending[cursor];
            if (node is NCardRewardAlternativeButton candidate)
            {
                if (!GodotObject.IsInstanceValid(candidate))
                {
                    return false;
                }
                if (!candidate.IsVisibleInTree())
                {
                    if (!AppendChildren(node, pending))
                    {
                        return false;
                    }
                    continue;
                }
                if (!candidate.IsEnabled)
                {
                    waiting = true;
                    return false;
                }
                visibleAlternativeCount++;
                if (visibleAlternativeCount > 2)
                {
                    return false;
                }
                if (skipButton is null && canSkip)
                {
                    skipButton = candidate;
                }
            }
            if (!AppendChildren(node, pending))
            {
                return false;
            }
        }

        if (!canSkip && skipButton is not null)
        {
            return false;
        }
        return true;
    }

    private static bool AppendChildren(Node node, List<Node> pending)
    {
        int childCount = node.GetChildCount(false);
        if (childCount < 0 || childCount > MaximumTraversedNodes - pending.Count)
        {
            return false;
        }
        for (int index = 0; index < childCount; index++)
        {
            pending.Add(node.GetChild(index, false));
        }
        return true;
    }

    internal static bool ContainsNode(Node root, Node candidate)
    {
        var pending = new List<Node> { root };
        for (int cursor = 0; cursor < pending.Count; cursor++)
        {
            if (pending.Count > MaximumTraversedNodes)
            {
                return false;
            }
            Node node = pending[cursor];
            if (ReferenceEquals(node, candidate))
            {
                return true;
            }
            if (!AppendChildren(node, pending))
            {
                return false;
            }
        }
        return false;
    }

    private static PublicRewardPlayer ProjectPlayer(Player player)
    {
        var creature = player.Creature;
        return new PublicRewardPlayer(
            creature.CurrentHp,
            creature.MaxHp,
            player.Gold,
            player.Deck.Cards.Count);
    }

    internal static int CountCardCopies(Player player, string cardId)
    {
        int count = 0;
        foreach (CardModel card in player.Deck.Cards)
        {
            if (string.Equals(card.Id.Entry, cardId, StringComparison.Ordinal))
            {
                count++;
            }
        }
        return count;
    }

    private static bool SameHealth(PublicRewardPlayer left, PublicRewardPlayer right) =>
        left.Hp == right.Hp && left.MaxHp == right.MaxHp;

    private static bool SamePlayer(PublicRewardPlayer left, PublicRewardPlayer right) =>
        SameHealth(left, right) &&
        left.Gold == right.Gold &&
        left.DeckCount == right.DeckCount;

    private PublicRewardDecisionSnapshot FailClosed()
    {
        _session.FailClosed();
        return PublicRewardDecisionSnapshot.Unsupported();
    }
}
