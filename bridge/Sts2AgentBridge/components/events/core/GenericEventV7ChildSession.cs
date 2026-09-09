using System;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.GenericEventV5;
namespace Sts2AgentBridge.Successors.GenericEventV7;
public interface IGenericEventV7ChildSession : IDisposable { string ContractVersion { get; } }
public interface IGenericEventV7CardChildSession : IGenericEventV7ChildSession {
    ICardSelectionV1ReadValue Read();
    ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId);
}
public interface IGenericEventV7ItemChildSession : IGenericEventV7ChildSession {
    IItemV1ReadValue Read();
    IItemV1ApplyValue Apply(string? decisionId, string? actionId);
}
public abstract record GenericEventV7ChildRead(string ContractVersion);
public sealed record GenericEventV7CardRead(string Version, ICardSelectionV1ReadValue Value) : GenericEventV7ChildRead(Version);
public sealed record GenericEventV7ItemRead(IItemV1ReadValue Value) : GenericEventV7ChildRead("item_v1");
public abstract record GenericEventV7ChildApply(string ContractVersion);
public sealed record GenericEventV7CardApply(string Version, ICardSelectionV1ApplyValue Value) : GenericEventV7ChildApply(Version);
public sealed record GenericEventV7ItemApply(IItemV1ApplyValue Value) : GenericEventV7ChildApply("item_v1");
public sealed class GenericEventV7CardChildSession : IGenericEventV7CardChildSession {
    private readonly IGenericEventV5ChildSession _session;
    public GenericEventV7CardChildSession(IGenericEventV5ChildSession session) {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        if (session.ContractVersion is not ("card_selection_v1" or "card_transform_v2" or "card_enchant_v1" or "card_remove_v2"))
            throw new ArgumentException("Unknown card contract.", nameof(session));
    }
    public string ContractVersion => _session.ContractVersion;
    public ICardSelectionV1ReadValue Read() => _session.Read();
    public ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId) => _session.Apply(decisionId, actionId);
    public void Dispose() => _session.Dispose();
}

public sealed class GenericEventV7EnchantChildSession : IGenericEventV5ChildSession
{
    private readonly CardSelectionV1Session _session;
    public GenericEventV7EnchantChildSession(CardSelectionV1ParentContext context, ICardSelectionV1NativeAdapter adapter)
    {
        if (context.Operation != CardSelectionV1Operation.Enchant) throw new ArgumentException("Expected enchantment context.");
        _session = new CardSelectionV1Session(context, adapter);
    }
    public string ContractVersion => "card_enchant_v1";
    public ICardSelectionV1ReadValue Read() => _session.Read();
    public ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId) => _session.Apply(decisionId, actionId);
    public void Dispose() => _session.Dispose();
}

public sealed class GenericEventV7RemovalChildSession : IGenericEventV5ChildSession
{
    private readonly CardSelectionV1Session _session;
    public GenericEventV7RemovalChildSession(CardSelectionV1ParentContext context, ICardSelectionV1NativeAdapter adapter)
    {
        if(context.Operation!=CardSelectionV1Operation.Remove || !context.AllowRemovalParentAppend)
            throw new ArgumentException("Expected removal v2 context.");
        _session=new CardSelectionV1Session(context,adapter);
    }
    public string ContractVersion => "card_remove_v2";
    public ICardSelectionV1ReadValue Read()=>_session.Read();
    public ICardSelectionV1ApplyValue Apply(string? decisionId,string? actionId)=>_session.Apply(decisionId,actionId);
    public void Dispose()=>_session.Dispose();
}
