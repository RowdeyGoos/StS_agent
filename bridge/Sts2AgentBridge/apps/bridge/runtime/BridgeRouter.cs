using System;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using Sts2AgentBridge.Successors.GenericEventReleaseV10;
using Sts2AgentBridge.Successors.CardSelectionReleaseV1;

namespace Sts2AgentBridge.Unified;

internal readonly record struct ModuleReply(byte[] Body, bool Complete = false, bool Terminal = false,
    GenericEventDiagnosticCode Diagnostic = GenericEventDiagnosticCode.NotCaptured, bool EventDiagnostic = false,
    bool StaleWithoutMutation = false, Func<bool>? CombatScope = null);
internal readonly record struct BridgeReply(byte[] Response, bool Terminal, bool StaleWithoutMutation = false);

internal interface IBridgeModule : IDisposable
{
    Capability Capability { get; }
    bool Owns(BridgeRequest request);
    ModuleReply Handle(BridgeRequest request);
}

internal sealed class BridgeRouter : IDisposable
{
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private readonly Func<Capability, string, IBridgeModule> _factory;
    private readonly CoreBridgeModule _core;
    private IBridgeModule? _active;
    private int _sessions;
    private bool _failed, _disposed;

    internal BridgeRouter(CoreBridgeModule core, Func<Capability, string, IBridgeModule> factory)
    { _core = core; _factory = factory; }

    internal BridgeReply Handle(BridgeRequest request)
    {
        if (_disposed || _failed || Environment.CurrentManagedThreadId != _owner) return Fail();
        try
        {
            if (request.IsMetadata) return Wrap(_core.Handle(request));
            if (_active is not null && !_active.Owns(request)) return Busy();
            if (_active is null && request.Capability != Capability.Core)
            {
                if (_core.HasPendingAction) return Busy();
                if (!request.CanStart || _sessions >= 64) return Fail();
                _sessions++;
                _active = _factory(request.Capability, Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant());
                if (_active is null || _active.Capability != request.Capability || !_active.Owns(request)) return Fail();
            }
            if (_active is null) return Wrap(_core.Handle(request));
            ModuleReply reply = _active.Handle(request);
            try
            {
                if (reply.Terminal) _failed = true;
                else if (reply.Complete)
                {
                    // Keep the cleanup owner if disposal fails. No replacement native session
                    // may be created until its hooks and bindings have actually been released.
                    _active.Dispose();
                    _active = null;
                    if(reply.CombatScope is not null)_core.BindCombatScope(reply.CombatScope);
                }
                return Wrap(reply);
            }
            catch { Array.Clear(reply.Body); throw; }
        }
        catch { return Fail(); }
    }

    private BridgeReply Wrap(ModuleReply reply)
    {
        try
        {
            if (reply.Terminal) _failed = true;
            return new(reply.EventDiagnostic ? GenericEventTransportHttpEncoder.Wrap(reply.Body, reply.Diagnostic) : CardSelectionTransportHttpEncoder.Wrap(reply.Body), _failed,
                !_failed && reply.StaleWithoutMutation);
        }
        finally { Array.Clear(reply.Body); }
    }
    private BridgeReply Fail()
    {
        _failed = true;
        return Wrap(new("{\"schema_version\":1,\"kind\":\"error\",\"code\":\"bridge_stopped\"}"u8.ToArray(), Terminal: true));
    }
    private static BridgeReply Busy() => new(GenericEventTransportHttpEncoder.Wrap(
        "{\"schema_version\":1,\"kind\":\"error\",\"code\":\"capability_busy\"}"u8.ToArray()), false);
    public void Dispose()
    {
        if (Environment.CurrentManagedThreadId != _owner) throw new InvalidOperationException("Owner frame required.");
        if (_disposed) return;
        _failed = true;
        _active?.Dispose();
        _active = null;
        _core.Dispose();
        _disposed = true;
    }
}
