using System;
using System.Collections.Generic;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes.Events;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.Native;

internal sealed class ProductionEventOrchestratorV1ChildFactoryBuilder
    : IEventOrchestratorV1NativeChildFactoryBuilder
{
    internal static ProductionEventOrchestratorV1ChildFactoryBuilder Instance { get; } = new();
    private readonly RecordingBuilder _inner = new();
    public IEventOrchestratorV1ChildFactory CreateItem(EventOrchestratorV1ChildPolicy p,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent b, EventOption o, NEventOptionButton c) =>
        _inner.CreateItem(p, b, o, c);
    public IEventOrchestratorV1ChildFactory CreateCheese(EventOrchestratorV1ChildPolicy p,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent b, RoomFullOfCheese e,
        EventOption o, NEventOptionButton c) => _inner.CreateCheese(p, b, e, o, c);
}

internal sealed class RecordingBuilder : IEventOrchestratorV1NativeChildFactoryBuilder
{
    internal readonly List<RecordingFactory> Values = new();
    public IEventOrchestratorV1ChildFactory CreateItem(EventOrchestratorV1ChildPolicy p,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent b, EventOption o, NEventOptionButton c) =>
        Add(new RecordingFactory(p, b, o, c));
    public IEventOrchestratorV1ChildFactory CreateCheese(EventOrchestratorV1ChildPolicy p,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent b, RoomFullOfCheese e,
        EventOption o, NEventOptionButton c) => Add(new RecordingFactory(p, b, o, c));
    private RecordingFactory Add(RecordingFactory value) { Values.Add(value); return value; }
}

internal sealed class RecordingFactory : IEventOrchestratorV1ChildFactory
{
    private readonly PinnedEventOrchestratorV1NativeAdapter.BoundEvent _bound;
    private readonly EventOption _option;
    private readonly NEventOptionButton _button;
    internal RecordingFactory(EventOrchestratorV1ChildPolicy policy,
        PinnedEventOrchestratorV1NativeAdapter.BoundEvent bound,
        EventOption option, NEventOptionButton button) =>
        (Policy, _bound, _option, _button) = (policy, bound, option, button);
    public EventOrchestratorV1ChildPolicy Policy { get; }
    internal EventOrchestratorV1AcceptedContext? Accepted { get; private set; }
    internal object? Screen { get; private set; }
    internal bool Check() => Accepted is not null && Screen is not null &&
        PinnedEventOrchestratorV1NativeAdapter.Foreground(
            _bound, Accepted, Screen, _option, _button, Policy, this);
    public IEventOrchestratorV1ChildBroker Create(EventOrchestratorV1AcceptedContext accepted,
        EventOrchestratorV1ChildCorrelation correlation, object exactForegroundIdentity)
    {
        Accepted = accepted; Screen = exactForegroundIdentity;
        if (!Check()) throw new InvalidOperationException("guard");
        return Policy.ChildKind == EventOrchestratorV1ChildKind.Item
            ? new FakeItemBroker(correlation) : new FakeCardBroker(correlation);
    }
}

internal abstract class FakeBroker : IEventOrchestratorV1ChildBroker
{
    protected FakeBroker(EventOrchestratorV1ChildCorrelation correlation) => Correlation = correlation;
    public EventOrchestratorV1ChildCorrelation Correlation { get; }
    public EventOrchestratorV1ChildStatus Status => EventOrchestratorV1ChildStatus.Active;
    public void Dispose() { }
}

internal sealed class FakeItemBroker : FakeBroker, IEventOrchestratorV1ItemChildBroker
{
    internal FakeItemBroker(EventOrchestratorV1ChildCorrelation c) : base(c) { }
    public Sts2AgentBridge.Successors.ItemV1.IItemV1ReadValue Read() => throw new NotSupportedException();
    public Sts2AgentBridge.Successors.ItemV1.IItemV1ApplyValue Apply(string? d, string? a) => throw new NotSupportedException();
}

internal sealed class FakeCardBroker : FakeBroker, IEventOrchestratorV1CardChildBroker
{
    internal FakeCardBroker(EventOrchestratorV1ChildCorrelation c) : base(c) { }
    public Sts2AgentBridge.Successors.CardSelectionV1.ICardSelectionV1ReadValue Read() => throw new NotSupportedException();
    public Sts2AgentBridge.Successors.CardSelectionV1.ICardSelectionV1ApplyValue Apply(string? d, string? a) => throw new NotSupportedException();
}
