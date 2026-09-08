using System;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.GenericEventV5;
namespace Sts2AgentBridge.Successors.GenericEventV6;
public interface IGenericEventV6ChildSession : IDisposable { string ContractVersion { get; } }
public interface IGenericEventV6CardChildSession : IGenericEventV6ChildSession {
    ICardSelectionV1ReadValue Read();
    ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId);
}
public interface IGenericEventV6ItemChildSession : IGenericEventV6ChildSession {
    IItemV1ReadValue Read();
    IItemV1ApplyValue Apply(string? decisionId, string? actionId);
}
public abstract record GenericEventV6ChildRead(string ContractVersion);
public sealed record GenericEventV6CardRead(string Version, ICardSelectionV1ReadValue Value) : GenericEventV6ChildRead(Version);
public sealed record GenericEventV6ItemRead(IItemV1ReadValue Value) : GenericEventV6ChildRead("item_v1");
public abstract record GenericEventV6ChildApply(string ContractVersion);
public sealed record GenericEventV6CardApply(string Version, ICardSelectionV1ApplyValue Value) : GenericEventV6ChildApply(Version);
public sealed record GenericEventV6ItemApply(IItemV1ApplyValue Value) : GenericEventV6ChildApply("item_v1");
public sealed class GenericEventV6CardChildSession : IGenericEventV6CardChildSession {
    private readonly IGenericEventV5ChildSession _session;
    public GenericEventV6CardChildSession(IGenericEventV5ChildSession session) {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        if (session.ContractVersion is not ("card_selection_v1" or "card_transform_v1"))
            throw new ArgumentException("Unknown card contract.", nameof(session));
    }
    public string ContractVersion => _session.ContractVersion;
    public ICardSelectionV1ReadValue Read() => _session.Read();
    public ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId) => _session.Apply(decisionId, actionId);
    public void Dispose() => _session.Dispose();
}
