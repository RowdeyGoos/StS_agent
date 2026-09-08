using System;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1;

public interface IEventItemChildFactory
{
    IEventItemChildBroker Create(RoomFlowDispatchReceipt parentReceipt, IItemV1NativeAdapter adapter);
}

public interface IEventItemChildBroker : IDisposable
{
    RoomFlowDispatchReceipt ParentReceipt { get; }
    EventItemChildStatus Status { get; }
    // Returned buffer transfers to caller; caller zeros it after parsing or transport.
    // Broker retains no response buffer and zeros any owned buffer if it cannot return it.
    byte[] Handle(string? method, string? route, string? decisionId, string? actionId);
}

public abstract class EventItemChildStatus
{
    protected EventItemChildStatus(RoomFlowDispatchReceipt parentReceipt)
    {
        ParentReceipt = parentReceipt ?? throw new ArgumentNullException(nameof(parentReceipt));
        if (parentReceipt.FlowKind != "event") throw new ArgumentException("Event parent required.");
    }
    public RoomFlowDispatchReceipt ParentReceipt { get; }
}

public sealed class EventItemChildActive(RoomFlowDispatchReceipt parentReceipt) : EventItemChildStatus(parentReceipt) { }
public sealed class EventItemChildResolved(RoomFlowDispatchReceipt parentReceipt) : EventItemChildStatus(parentReceipt) { }
public sealed class EventItemChildFailed : EventItemChildStatus
{
    public EventItemChildFailed(RoomFlowDispatchReceipt parentReceipt, RoomFlowApplyFailure failure) : base(parentReceipt)
    {
        if (failure is null || failure.FlowKind != "event" || failure.SessionNonce != parentReceipt.SessionNonce)
            throw new ArgumentException("Mismatched child failure.");
        Failure = failure;
    }
    public RoomFlowApplyFailure Failure { get; }
}
