using System;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Native;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Native;

internal sealed class ProductionEventOrchestratorV1ChildFactoryBuilder
    : IEventOrchestratorV1NativeChildFactoryBuilder
{
    internal static ProductionEventOrchestratorV1ChildFactoryBuilder Instance { get; } = new();
    private ProductionEventOrchestratorV1ChildFactoryBuilder() { }

    public IEventOrchestratorV1ChildFactory CreateItem(
        EventOrchestratorV1ChildPolicy policy,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
        EventOption option,
        NEventOptionButton button) => new ItemFactory(policy, bound, option, button);

    public IEventOrchestratorV1ChildFactory CreateCheese(
        EventOrchestratorV1ChildPolicy policy,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
        RoomFullOfCheese eventModel,
        EventOption option,
        NEventOptionButton button) => new CheeseFactory(policy, bound, eventModel, option, button);

    private abstract class FactoryBase : IEventOrchestratorV1ChildFactory
    {
        protected FactoryBase(EventOrchestratorV1ChildPolicy policy,
            PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
            EventOption option, NEventOptionButton button) =>
            (Policy, Bound, Option, Button) = (policy, bound, option, button);
        public EventOrchestratorV1ChildPolicy Policy { get; }
        protected PinnedEventOrchestratorV1NativeAdapter.BoundEvent Bound { get; }
        protected EventOption Option { get; }
        protected NEventOptionButton Button { get; }
        protected bool Guard(EventOrchestratorV1AcceptedContext accepted, object screen) =>
            PinnedEventOrchestratorV1NativeAdapter.Foreground(
                Bound, accepted, screen, Option, Button, Policy, this);
        public abstract IEventOrchestratorV1ChildBroker Create(
            EventOrchestratorV1AcceptedContext acceptedContext,
            EventOrchestratorV1ChildCorrelation correlation,
            object exactForegroundIdentity);
    }

    private sealed class ItemFactory : FactoryBase
    {
        internal ItemFactory(EventOrchestratorV1ChildPolicy policy,
            PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
            EventOption option, NEventOptionButton button)
            : base(policy, bound, option, button) { }

        public override IEventOrchestratorV1ChildBroker Create(
            EventOrchestratorV1AcceptedContext accepted,
            EventOrchestratorV1ChildCorrelation correlation,
            object exactForegroundIdentity)
        {
            if (Policy.PolicyKind != EventOrchestratorV1ChildPolicyKind.ItemReward ||
                correlation.Kind != EventOrchestratorV1ChildKind.Item ||
                exactForegroundIdentity is not NRewardsScreen screen ||
                screen.GetType() != typeof(NRewardsScreen) || !Guard(accepted, screen))
                throw new InvalidOperationException("Item child binding changed.");
            return new EventOrchestratorV1ItemChildBroker(
                correlation, accepted, screen,
                new BoundEventItemV1NativeAdapter(
                    Bound.Run, Bound.Player, Bound.Room, Bound.Map, screen),
                Guard);
        }
    }

    private sealed class CheeseFactory : FactoryBase
    {
        private readonly RoomFullOfCheese _eventModel;
        internal CheeseFactory(EventOrchestratorV1ChildPolicy policy,
            PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
            RoomFullOfCheese eventModel, EventOption option, NEventOptionButton button)
            : base(policy, bound, option, button) => _eventModel = eventModel;

        public override IEventOrchestratorV1ChildBroker Create(
            EventOrchestratorV1AcceptedContext accepted,
            EventOrchestratorV1ChildCorrelation correlation,
            object exactForegroundIdentity)
        {
            if (Policy.PolicyKind != EventOrchestratorV1ChildPolicyKind.CheeseGorgeAddTwo ||
                correlation.Kind != EventOrchestratorV1ChildKind.CardSelection ||
                exactForegroundIdentity is not NSimpleCardSelectScreen screen ||
                screen.GetType() != typeof(NSimpleCardSelectScreen) ||
                !ReferenceEquals(_eventModel, Bound.Event) || !Guard(accepted, screen))
                throw new InvalidOperationException("Cheese child binding changed.");
            var context = new CardSelectionV1ParentContext(
                correlation.ParentReceipt.SessionNonce,
                CardSelectionV1ParentKind.Event,
                correlation.ParentReceipt.DecisionId,
                correlation.ParentReceipt.ActionId,
                correlation,
                Bound.Run,
                Bound.Player,
                Bound.Room,
                Bound.Map,
                Option,
                Button,
                Policy.CardOperation,
                Policy.MinSelect,
                Policy.MaxSelect,
                Policy.CardCommitMode,
                Policy.ExpectedDomainCount);
            PinnedCardSelectionV1NativeAdapter adapter =
                PinnedCardSelectionV1NativeAdapter.CreateRoomFullOfCheese(
                    context, Bound.Run, Bound.Player, Bound.Room, Bound.Map,
                    _eventModel, Option, Button, screen);
            try
            {
                return new EventOrchestratorV1CardChildBroker(
                    correlation, accepted, screen, adapter, Guard);
            }
            catch
            {
                adapter.Dispose();
                throw;
            }
        }
    }
}
