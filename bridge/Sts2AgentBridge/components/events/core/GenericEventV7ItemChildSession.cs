using System;
using Sts2AgentBridge.Successors.ItemV1;
namespace Sts2AgentBridge.Successors.GenericEventV7;
public enum GenericEventV7ItemTaskState { Pending, Succeeded, Faulted, Canceled }
public sealed record GenericEventV7ItemTaskWitness(object Identity, GenericEventV7ItemTaskState State);
public sealed record GenericEventV7ItemCompletion(bool OwnershipValid, bool EffectStillValid,
    bool ScreenClosed, GenericEventV7ItemTaskWitness? Collection,
    GenericEventV7ItemTaskWitness? Offer, GenericEventV7ItemTaskWitness? Chosen);
public interface IGenericEventV7ItemNativeAdapter : IItemV1NativeAdapter, IDisposable {
    GenericEventV7ItemCompletion CaptureCompletion();
}
// One frozen local collection plus one bounded owner-completion gate.
public sealed class GenericEventV7ItemChildSession : IGenericEventV7ItemChildSession {
    private readonly object _gate = new();
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private readonly string _nonce;
    private readonly IGenericEventV7ItemNativeAdapter _adapter;
    private readonly GuardedAdapter _guard;
    private readonly ItemV1Session _session;
    private readonly GenericEventV7ItemTaskWitness?[] _tasks = new GenericEventV7ItemTaskWitness?[3];
    private bool _inside, _interfered, _unsupported, _accepted, _disposed;
    private int _reads;
    private ItemV1ResolvedResult? _local, _resolved;
    public GenericEventV7ItemChildSession(string sessionNonce, IGenericEventV7ItemNativeAdapter adapter) {
        _nonce=sessionNonce; _adapter=adapter ?? throw new ArgumentNullException(nameof(adapter));
        _guard=new GuardedAdapter(adapter); _session=new ItemV1Session(sessionNonce,_guard);
    }
    public string ContractVersion => "item_v1";
    private bool Enter() {
        if (_inside) { _interfered=true; _unsupported=true; return false; }
        if (_disposed || _unsupported || Environment.CurrentManagedThreadId != _owner) { _unsupported=true; return false; }
        _inside=true; _guard.Active=true; return true;
    }
    private void Exit() { _guard.Active=false; _inside=false; }
    private ItemV1Observation Fixed(string status) => ItemV1Observation.Fixed(_nonce,status);
    private ItemV1Observation Stop() { _unsupported=true; return Fixed("unsupported"); }
    public IItemV1ReadValue Read() {
        lock (_gate) {
            if (!Enter()) return Fixed("unsupported");
            try {
                if (_resolved is not null) return _resolved;
                if (!_accepted) {
                    var value=_session.Read();
                    if (_interfered) return Stop();
                    if (value is not ItemV1Observation observation) return Stop();
                    if (observation.Status == "unsupported") return Stop();
                    if (observation.Status == "ready" && observation.Offers.Count != 1) return Stop();
                    return value;
                }
                if (_reads >= ItemV1Constants.MaximumReconciliationReads) return Stop();
                _reads++;
                IItemV1ReadValue local=_local ?? _session.Read();
                // Always sample once per accepted post-dispatch read, even local waiting/unsupported.
                var completion=_adapter.CaptureCompletion();
                if (_interfered || completion is null || !completion.OwnershipValid) return Stop();
                if (!Task(0,completion.Collection) || !Task(1,completion.Offer) || !Task(2,completion.Chosen)) return Stop();
                if (local is ItemV1ResolvedResult done) _local ??= done;
                else if (local is not ItemV1Observation waiting || waiting.Status != "waiting") return Stop();
                if (_local is not null) {
                    if (!completion.EffectStillValid) return Stop();
                    if (completion.ScreenClosed && Succeeded(completion.Collection) && Succeeded(completion.Offer) && Succeeded(completion.Chosen)) {
                        _resolved=_local; return _resolved;
                    }
                }
                if (_reads == ItemV1Constants.MaximumReconciliationReads) return Stop();
                return Fixed("waiting");
            } catch { return Stop(); }
            finally { Exit(); }
        }
    }
    private static bool Succeeded(GenericEventV7ItemTaskWitness? t) => t?.State == GenericEventV7ItemTaskState.Succeeded;
    private bool Task(int index, GenericEventV7ItemTaskWitness? current) {
        var prior=_tasks[index];
        if (current is null) return prior is null;
        if (current.Identity is null || current.State is < GenericEventV7ItemTaskState.Pending or > GenericEventV7ItemTaskState.Canceled ||
            current.State is GenericEventV7ItemTaskState.Faulted or GenericEventV7ItemTaskState.Canceled) return false;
        if (prior is not null && (!ReferenceEquals(prior.Identity,current.Identity) ||
            prior.State != GenericEventV7ItemTaskState.Pending && prior.State != current.State)) return false;
        _tasks[index]=current; return true;
    }
    public IItemV1ApplyValue Apply(string? decisionId,string? actionId) {
        lock (_gate) {
            if (!Enter()) return new ItemV1ApplyFailure(_nonce,"unsupported");
            try {
                if (_accepted || _resolved is not null) return new ItemV1ApplyFailure(_nonce,"rejected");
                var result=_session.Apply(decisionId,actionId);
                if (_interfered) { _unsupported=true; return new ItemV1ApplyFailure(_nonce,"uncertain"); }
                if (result is ItemV1DispatchReceipt) _accepted=true;
                else if (result is ItemV1ApplyFailure failure && failure.Outcome != "rejected") _unsupported=true;
                return result;
            } catch { _unsupported=true; return new ItemV1ApplyFailure(_nonce,"uncertain"); }
            finally { Exit(); }
        }
    }
    public void Dispose() {
        lock (_gate) {
            if (_disposed) return;
            _unsupported=true;
            if (Environment.CurrentManagedThreadId != _owner || _inside) {
                _interfered=true; throw new InvalidOperationException("Item cleanup requires its idle owner.");
            }
            _guard.Active=false;
            _inside=true; _interfered=false;
            try {
                _adapter.Dispose(); // Retain ownership for retry if cleanup fails.
                if (_interfered) throw new InvalidOperationException("Reentrant item cleanup.");
                _guard.Revoked=true; _disposed=true;
            } finally { _inside=false; }
        }
    }
    private sealed class GuardedAdapter : IItemV1NativeAdapter {
        private readonly IItemV1NativeAdapter _inner;
        internal bool Active, Revoked;
        internal GuardedAdapter(IItemV1NativeAdapter inner) => _inner=inner;
        private void Check() { if (!Active || Revoked) throw new InvalidOperationException("Inactive item adapter."); }
        public ItemV1SurfaceCapture CaptureSurface() { Check(); var value=_inner.CaptureSurface();
            if (value.Status == ItemV1SurfaceStatus.Available && value.Offers.Count != 1) return ItemV1SurfaceCapture.Unsupported();
            return value;
        }
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe) { Check(); return _inner.CapturePending(probe); }
    }
}
