using System;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicRewardActionApplier : IPublicRewardActionApplier
{
    private readonly PinnedPublicRewardDecisionReader _reader;
    private readonly PinnedPublicRewardInteractionSession _session;

    public PinnedPublicRewardActionApplier(PinnedPublicRewardDecisionReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
        _session = reader.InteractionSession;
    }

    public PublicRewardActionApplyResult Apply(PublicRewardActionRequest request)
    {
        PublicRewardActionApplyOutcome? initialFailure =
            _session.ReservationFailure(request.DecisionId);
        if (initialFailure.HasValue)
        {
            return Result(initialFailure.Value, request);
        }

        PublicRewardDecisionSnapshot snapshot = _reader.Read();
        if (snapshot.Status != PublicDecisionStatus.Ready ||
            !string.Equals(snapshot.DecisionId, request.DecisionId, StringComparison.Ordinal))
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }
        if (!IsAdvertised(snapshot, request.ActionId))
        {
            return Result(PublicRewardActionApplyOutcome.InvalidAction, request);
        }

        return request.Kind switch
        {
            PublicRewardActionKind.ClaimGold => ApplyParentReward(request, snapshot, claimGold: true),
            PublicRewardActionKind.OpenCard => ApplyParentReward(request, snapshot, claimGold: false),
            PublicRewardActionKind.ChooseCard => ApplyCardChoice(request, snapshot),
            PublicRewardActionKind.SkipCard => ApplyCardSkip(request, snapshot),
            PublicRewardActionKind.Proceed => ApplyProceed(request, snapshot),
            _ => Result(PublicRewardActionApplyOutcome.InvalidAction, request),
        };
    }

    private PublicRewardActionApplyResult ApplyParentReward(
        PublicRewardActionRequest request,
        PublicRewardDecisionSnapshot snapshot,
        bool claimGold)
    {
        if (!_session.TryGetParentTarget(
                request.DecisionId,
                request.RewardSlot,
                out NRewardsScreen? screen,
                out PinnedPublicRewardParentTarget? target) ||
            screen is null || target is null || !IsTop(screen) ||
            !GodotObject.IsInstanceValid(target.Button) ||
            !target.Button.IsVisibleInTree() || !target.Button.IsEnabled ||
            !ReferenceEquals(target.Button.Reward, target.Reward) ||
            target.Reward.SuccessfullySelected ||
            claimGold && target.Reward is not GoldReward ||
            !claimGold && target.Reward is not CardReward)
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }

        var pending = new PinnedPublicRewardPendingMutation(
            claimGold ? PublicRewardActionKind.ClaimGold : PublicRewardActionKind.OpenCard,
            snapshot.Player,
            target);
        PublicRewardActionApplyOutcome? reservationFailure =
            _session.Begin(request.DecisionId, pending);
        if (reservationFailure.HasValue)
        {
            return Result(reservationFailure.Value, request);
        }

        target.Button.ForceClick();
        return Result(PublicRewardActionApplyOutcome.Accepted, request);
    }

    private PublicRewardActionApplyResult ApplyCardChoice(
        PublicRewardActionRequest request,
        PublicRewardDecisionSnapshot snapshot)
    {
        if (!_session.TryGetCardTarget(
                request.DecisionId,
                request.CardSlot,
                out NCardRewardSelectionScreen? screen,
                out PinnedPublicRewardCardTarget? target) ||
            screen is null || target is null || !IsTop(screen) ||
            !GodotObject.IsInstanceValid(target.Holder) ||
            !target.Holder.IsVisibleInTree() ||
            !ReferenceEquals(target.Holder.CardModel, target.Model))
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }

        NCardHolder? resolvedHolder;
        try
        {
            resolvedHolder = screen.GetCardHolder(target.Model);
        }
        catch
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }
        if (!ReferenceEquals(resolvedHolder, target.Holder))
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }

        PinnedPublicRewardParentTarget? parentTarget = _session.ActiveCardReward;
        if (parentTarget is null || parentTarget.Reward is not CardReward cardReward ||
            !ContainsOfferedModel(parentTarget, target.Model))
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }
        int chosenCopiesBefore = PinnedPublicRewardDecisionReader.CountCardCopies(
            cardReward.Player,
            target.Model.Id.Entry);
        var pending = new PinnedPublicRewardPendingMutation(
            PublicRewardActionKind.ChooseCard,
            snapshot.Player,
            parentTarget,
            target,
            chosenCopiesBefore);
        PublicRewardActionApplyOutcome? reservationFailure =
            _session.Begin(request.DecisionId, pending);
        if (reservationFailure.HasValue)
        {
            return Result(reservationFailure.Value, request);
        }

        Error emitted = target.Holder.EmitSignal(
            NCardHolder.SignalName.Pressed,
            target.Holder);
        if (emitted != Error.Ok)
        {
            throw new InvalidOperationException("The card-choice signal was not accepted.");
        }
        return Result(PublicRewardActionApplyOutcome.Accepted, request);
    }

    private PublicRewardActionApplyResult ApplyCardSkip(
        PublicRewardActionRequest request,
        PublicRewardDecisionSnapshot snapshot)
    {
        if (!_session.TryGetSkipTarget(
                request.DecisionId,
                out NCardRewardSelectionScreen? screen,
                out NCardRewardAlternativeButton? skipButton) ||
            screen is null || skipButton is null || !IsTop(screen) ||
            !GodotObject.IsInstanceValid(skipButton) ||
            !skipButton.IsVisibleInTree() || !skipButton.IsEnabled)
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }

        PinnedPublicRewardParentTarget? parentTarget = _session.ActiveCardReward;
        if (parentTarget is null || parentTarget.Reward is not CardReward cardReward ||
            !cardReward.CanSkip)
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }
        var pending = new PinnedPublicRewardPendingMutation(
            PublicRewardActionKind.SkipCard,
            snapshot.Player,
            parentTarget);
        PublicRewardActionApplyOutcome? reservationFailure =
            _session.Begin(request.DecisionId, pending);
        if (reservationFailure.HasValue)
        {
            return Result(reservationFailure.Value, request);
        }

        skipButton.ForceClick();
        return Result(PublicRewardActionApplyOutcome.Accepted, request);
    }

    private PublicRewardActionApplyResult ApplyProceed(
        PublicRewardActionRequest request,
        PublicRewardDecisionSnapshot snapshot)
    {
        if (!_session.TryGetParentScreen(request.DecisionId, out NRewardsScreen? screen) ||
            screen is null || !IsTop(screen))
        {
            return Result(PublicRewardActionApplyOutcome.StaleDecision, request);
        }

        var pending = new PinnedPublicRewardPendingMutation(
            PublicRewardActionKind.Proceed,
            snapshot.Player);
        PublicRewardActionApplyOutcome? reservationFailure =
            _session.Begin(request.DecisionId, pending);
        if (reservationFailure.HasValue)
        {
            return Result(reservationFailure.Value, request);
        }

        _ = RunManager.Instance.ProceedFromTerminalRewardsScreen();
        return Result(PublicRewardActionApplyOutcome.Accepted, request);
    }

    private static bool IsAdvertised(PublicRewardDecisionSnapshot snapshot, string actionId)
    {
        foreach (string legalAction in snapshot.LegalActions)
        {
            if (string.Equals(legalAction, actionId, StringComparison.Ordinal))
            {
                return true;
            }
        }
        return false;
    }

    private static bool IsTop(Node expected)
    {
        NOverlayStack? overlays = NOverlayStack.Instance;
        return overlays is not null && GodotObject.IsInstanceValid(overlays) &&
            overlays.ScreenCount > 0 && ReferenceEquals(overlays.Peek(), expected) &&
            GodotObject.IsInstanceValid(expected) && expected is CanvasItem visible &&
            visible.IsVisibleInTree();
    }

    private static bool ContainsOfferedModel(
        PinnedPublicRewardParentTarget target,
        CardModel model)
    {
        foreach (CardModel offered in target.OfferedCards)
        {
            if (string.Equals(offered.Id.Entry, model.Id.Entry, StringComparison.Ordinal))
            {
                return true;
            }
        }
        return false;
    }

    private static PublicRewardActionApplyResult Result(
        PublicRewardActionApplyOutcome outcome,
        PublicRewardActionRequest request) =>
        PublicRewardActionApplyResult.FromRequest(outcome, request);
}
