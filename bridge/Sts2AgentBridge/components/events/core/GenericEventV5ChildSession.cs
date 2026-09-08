using System;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV5;
public interface IGenericEventV5ChildSession : IDisposable
{
    string ContractVersion { get; }
    ICardSelectionV1ReadValue Read();
    ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId);
}
public sealed record GenericEventV5ChildRead(string ContractVersion, ICardSelectionV1ReadValue Value);
public sealed record GenericEventV5ChildApply(string ContractVersion, ICardSelectionV1ApplyValue Value);
public sealed class GenericEventV5FrozenChildSession : IGenericEventV5ChildSession
{
    private readonly CardSelectionV1Session _session;
    public GenericEventV5FrozenChildSession(CardSelectionV1Session session) => _session = session ?? throw new ArgumentNullException(nameof(session));
    public string ContractVersion => "card_selection_v1";
    public ICardSelectionV1ReadValue Read() => _session.Read();
    public ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId) => _session.Apply(decisionId, actionId);
    public void Dispose() => _session.Dispose();
}
