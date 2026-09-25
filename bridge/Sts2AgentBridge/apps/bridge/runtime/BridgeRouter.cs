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
    bool StaleWithoutMutation = false, Func<bool>? CombatScope = null, Func<string>? CombatResume = null, string? EventNonce = null, bool EventResumed = false, Func<Sts2AgentBridge.Successors.GenericEventV7.GenericEventV7ResumeDiagnostic>? CombatResumeDiagnostic=null);
internal readonly record struct BridgeReply(byte[] Response, bool Terminal, bool StaleWithoutMutation = false);

// Per-read fixed vocabulary timing; contains no game values or request data.
internal sealed class ReadStageTrace
{
    private static readonly string[] Names={"dispatch","router","module_create","module_handle","harmony_guard","event_adapter","hook_targets","hook_validation","hook_install","event_session","event_wire","event_read","hook_prepare","native_capture","reply"};
    private readonly object _gate=new();
    private readonly long[] _ticks=new long[Names.Length];
    private int _stage;
    private long _since=System.Diagnostics.Stopwatch.GetTimestamp();
    internal void Mark(int stage) {
        if(stage<0||stage>=Names.Length)return;
        lock(_gate){long now=System.Diagnostics.Stopwatch.GetTimestamp();_ticks[_stage]+=now-_since;_since=now;_stage=stage;}
    }
    internal object[] Snapshot() {
        lock(_gate) {
            long now=System.Diagnostics.Stopwatch.GetTimestamp();var rows=new System.Collections.Generic.List<object>();
            for(int i=0;i<Names.Length;i++) {
                long ticks=_ticks[i]+(i==_stage?now-_since:0);
                if(ticks>0)rows.Add(new {stage=Names[i],elapsed_ms=(int)Math.Clamp(ticks*1000.0/System.Diagnostics.Stopwatch.Frequency,0,3000),active=i==_stage});
            }
            return rows.ToArray();
        }
    }
}

internal interface IBridgeModule : IDisposable
{
    Capability Capability { get; }
    bool Owns(BridgeRequest request);
    ModuleReply Handle(BridgeRequest request);
    object? ObservationSource => null;
    void SetReadTrace(ReadStageTrace? trace) {}
}

internal sealed class BridgeRouter : IDisposable
{
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private readonly Func<Capability, string, IBridgeModule> _factory;
    private readonly CoreBridgeModule _core;
    private IBridgeModule? _active;
    private int _sessions;
    private bool _failed, _disposed, _resumingCombat;
    private FullAgentSession? _full;
    internal object? ActiveObservationSource => _active?.ObservationSource ?? _core.ObservationSource;
    internal void BindFullAgent(FullAgentSession session)
    { if (_full is not null || _sessions != 0 || _core.HasPendingAction) throw new InvalidOperationException("Late full-agent binding."); _full = session; }

    internal BridgeRouter(CoreBridgeModule core, Func<Capability, string, IBridgeModule> factory)
    { _core = core; _factory = factory; }

    internal BridgeReply Handle(BridgeRequest request,ReadStageTrace? trace=null)
    {
        if (_disposed || _failed || Environment.CurrentManagedThreadId != _owner) return Wrap(Fail());
        try
        {
            if (request.Path is FullAgentRoutes.Decision or FullAgentRoutes.Action)
            {
                if (_full is null || !_full.Active && (_active is not null || _core.HasPendingAction)) return Wrap(Busy());
                return Wrap(_full.Handle(request), full: true);
            }
            if (_full?.Active == true && !request.IsMetadata) return Wrap(Busy());
            return Wrap(Dispatch(request, trace));
        }
        catch { return Wrap(Fail()); }
    }

    // Internal delegation enters precisely the same ownership/cleanup path as
    // ordinary requests, but returns the body before HTTP framing.
    internal ModuleReply Dispatch(BridgeRequest request, ReadStageTrace? trace = null)
    {
        trace?.Mark(1);
        if (_disposed || _failed || Environment.CurrentManagedThreadId != _owner) return Fail();
        try
        {
            if (request.IsMetadata) return _core.Handle(request);
            if(_resumingCombat) {
                if(request.Capability!=Capability.Core)return Busy();
                if(CoreBridgeModule.IsResumeItem(request)) {
                    if(!_core.CanServiceResumeItem())return Busy();
                    var itemReply=_active!.Handle(request);
                    // Child completion never disposes the callback observer or releases combat ownership.
                    if(itemReply.Complete||itemReply.EventResumed) {Array.Clear(itemReply.Body);return Fail();}
                    return itemReply;
                }
                var combatReply=_core.Handle(request);
                try {
                    if(combatReply.EventResumed) {
                        _active!.Dispose();_active=null;
                        _core.ReleaseEventCombat();_resumingCombat=false;
                    }
                    return combatReply;
                }catch{Array.Clear(combatReply.Body);throw;}
            }
            if (_active is not null && !_active.Owns(request)) return Busy();
            if (_active is null && request.Capability != Capability.Core)
            {
                if (_core.HasPendingAction) return Busy();
                if (!request.CanStart || _sessions >= 64) return Fail();
                _sessions++;
                trace?.Mark(2);
                _active = _factory(request.Capability, Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant());
                if (_active is null || _active.Capability != request.Capability || !_active.Owns(request)) return Fail();
            }
            if (_active is null) return _core.Handle(request);
            trace?.Mark(3);_active.SetReadTrace(trace);
            ModuleReply reply;
            try{reply=_active.Handle(request);}finally{_active.SetReadTrace(null);}
            trace?.Mark(14);
            try
            {
                if (reply.Terminal) _failed = true;
                else if (reply.Complete)
                {
                    // Keep the cleanup owner if disposal fails. No replacement native session
                    // may be created until its hooks and bindings have actually been released.
                    if(reply.CombatResume is not null) {
                        if(reply.CombatScope is null)throw new InvalidOperationException("Missing event combat scope.");
                        _core.BindCombatScope(reply.CombatScope,reply.CombatResume,reply.EventNonce,reply.CombatResumeDiagnostic);
                        _resumingCombat=true;
                    } else {
                        _active.Dispose();_active=null;
                        if(reply.CombatScope is not null)_core.BindCombatScope(reply.CombatScope);
                    }
                }
                return reply;
            }
            catch { Array.Clear(reply.Body); throw; }
        }
        catch { return Fail(); }
    }

    private BridgeReply Wrap(ModuleReply reply, bool full = false)
    {
        try
        {
            if (reply.Terminal) _failed = true;
            return new(reply.EventDiagnostic ? GenericEventTransportHttpEncoder.Wrap(reply.Body, reply.Diagnostic) : CardSelectionTransportHttpEncoder.Wrap(reply.Body,
                full ? FullAgentRoutes.MaximumBody : CardSelectionTransportLimits.MaximumBody), _failed,
                !_failed && reply.StaleWithoutMutation);
        }
        finally { Array.Clear(reply.Body); }
    }
    private ModuleReply Fail()
    {
        _failed = true;
        return new("{\"schema_version\":1,\"kind\":\"error\",\"code\":\"bridge_stopped\"}"u8.ToArray(), Terminal: true);
    }
    private static ModuleReply Busy() => new("{\"schema_version\":1,\"kind\":\"error\",\"code\":\"capability_busy\"}"u8.ToArray());
    public void Dispose()
    {
        if (Environment.CurrentManagedThreadId != _owner) throw new InvalidOperationException("Owner frame required.");
        if (_disposed) return;
        _failed = true;
        var failures = new System.Collections.Generic.List<Exception>();
        try { _active?.Dispose(); _active = null; } catch (Exception error) { failures.Add(error); }
        try { _full?.Dispose(); } catch (Exception error) { failures.Add(error); }
        try { _core.Dispose(); } catch (Exception error) { failures.Add(error); }
        if (failures.Count > 0) throw new InvalidOperationException("Bridge cleanup failed; ownership is not released.", new AggregateException(failures));
        _disposed = true;
    }
}
