using System;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1;

public delegate bool EventOrchestratorV1ForegroundGuard(
    EventOrchestratorV1AcceptedContext acceptedContext,
    object exactForegroundIdentity);

public sealed class EventOrchestratorV1ItemChildBroker : IEventOrchestratorV1ItemChildBroker
{
    private readonly object _gate = new();
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private readonly EventOrchestratorV1AcceptedContext _accepted;
    private readonly object _foreground;
    private readonly EventOrchestratorV1ForegroundGuard _guard;
    private readonly GuardedItemAdapter _adapter;
    private readonly ItemV1Session _session;
    private EventOrchestratorV1ChildStatus _status = EventOrchestratorV1ChildStatus.Active;
    private bool _inside;
    private bool _interfered;
    private bool _disposeRequested;
    private bool _disposed;

    public EventOrchestratorV1ItemChildBroker(
        EventOrchestratorV1ChildCorrelation correlation,
        EventOrchestratorV1AcceptedContext acceptedContext,
        object exactForegroundIdentity,
        IItemV1NativeAdapter nativeAdapter,
        EventOrchestratorV1ForegroundGuard foregroundGuard)
    {
        Correlation = correlation ?? throw new ArgumentNullException(nameof(correlation));
        _accepted = acceptedContext ?? throw new ArgumentNullException(nameof(acceptedContext));
        _foreground = exactForegroundIdentity ?? throw new ArgumentNullException(nameof(exactForegroundIdentity));
        _guard = foregroundGuard ?? throw new ArgumentNullException(nameof(foregroundGuard));
        if (!ReferenceEquals(correlation.ParentReceipt, acceptedContext.ParentReceipt) ||
            correlation.Kind != EventOrchestratorV1ChildKind.Item)
            throw new ArgumentException("Item child correlation mismatch.", nameof(correlation));
        _adapter = new GuardedItemAdapter(nativeAdapter ??
            throw new ArgumentNullException(nameof(nativeAdapter)));
        _session = new ItemV1Session(correlation.ParentReceipt.SessionNonce, _adapter);
    }

    public EventOrchestratorV1ChildCorrelation Correlation { get; }
    public EventOrchestratorV1ChildStatus Status { get { lock (_gate) return _status; } }

    public IItemV1ReadValue Read()
    {
        lock (_gate)
        {
            if (!Enter()) return FixedRead();
            try
            {
                if (!Authorize()) return FixedRead();
                _adapter.Begin();
                IItemV1ReadValue result = _session.Read();
                _adapter.End();
                if (_interfered) return FailRead();
                if (result is ItemV1ResolvedResult) _status = EventOrchestratorV1ChildStatus.Resolved;
                else if (result is ItemV1Observation value && value.Status == "unsupported")
                    _status = EventOrchestratorV1ChildStatus.Failed;
                return result;
            }
            catch { return FailRead(); }
            finally { _adapter.End(); ExitAndDrain(); }
        }
    }

    public IItemV1ApplyValue Apply(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (!Enter()) return FixedApply();
            try
            {
                if (!Authorize()) return FixedApply();
                _adapter.Begin();
                IItemV1ApplyValue result = _session.Apply(decisionId, actionId);
                _adapter.End();
                if (_interfered) return FailApply();
                if (result is ItemV1ApplyFailure) _status = EventOrchestratorV1ChildStatus.Failed;
                return result;
            }
            catch { return FailApply(); }
            finally { _adapter.End(); ExitAndDrain(); }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed) return;
            _status = EventOrchestratorV1ChildStatus.Failed;
            if (Environment.CurrentManagedThreadId != _owner)
            {
                _disposeRequested = true;
                throw new InvalidOperationException("Item child cleanup requires its owner thread.");
            }
            if (_inside)
            {
                _interfered = true;
                _disposeRequested = true;
                return;
            }
            _disposed = true;
            _adapter.End();
            _adapter.Clear();
        }
    }

    private bool Enter()
    {
        if (_inside) { _interfered = true; _status = EventOrchestratorV1ChildStatus.Failed; return false; }
        if (_disposed || _status != EventOrchestratorV1ChildStatus.Active ||
            Environment.CurrentManagedThreadId != _owner)
        {
            _status = EventOrchestratorV1ChildStatus.Failed;
            return false;
        }
        _inside = true;
        return true;
    }

    private void ExitAndDrain()
    {
        _inside = false;
        if (_disposeRequested && Environment.CurrentManagedThreadId == _owner)
        {
            _disposeRequested = false;
            _disposed = true;
            _status = EventOrchestratorV1ChildStatus.Failed;
            _adapter.End();
            _adapter.Clear();
        }
    }

    private bool Authorize()
    {
        bool valid;
        try { valid = _guard(_accepted, _foreground); }
        catch { valid = false; }
        if (!valid || _interfered)
        {
            _status = EventOrchestratorV1ChildStatus.Failed;
            return false;
        }
        return true;
    }

    private IItemV1ReadValue FailRead()
    {
        _status = EventOrchestratorV1ChildStatus.Failed;
        return FixedRead();
    }

    private IItemV1ApplyValue FailApply()
    {
        _status = EventOrchestratorV1ChildStatus.Failed;
        return FixedApply();
    }

    private IItemV1ReadValue FixedRead() =>
        new ItemV1Session(Correlation.ParentReceipt.SessionNonce,
            new UnsupportedItemAdapter()).Read();

    private IItemV1ApplyValue FixedApply() =>
        new ItemV1Session(Correlation.ParentReceipt.SessionNonce,
            new UnsupportedItemAdapter()).Apply(null, null);

    private sealed class GuardedItemAdapter : IItemV1NativeAdapter
    {
        private IItemV1NativeAdapter? _inner;
        private bool _authorized;
        internal GuardedItemAdapter(IItemV1NativeAdapter inner) => _inner = inner;
        internal void Begin() => _authorized = true;
        internal void End() => _authorized = false;
        internal void Clear() { _authorized = false; _inner = null; }
        public ItemV1SurfaceCapture CaptureSurface() => _authorized
            ? (_inner ?? throw new InvalidOperationException("Item child was disposed.")).CaptureSurface()
            : throw new InvalidOperationException("Item child is outside its guarded operation.");
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) => _authorized
            ? (_inner ?? throw new InvalidOperationException("Item child was disposed.")).CapturePending(pending)
            : throw new InvalidOperationException("Item child is outside its guarded operation.");
    }

    private sealed class UnsupportedItemAdapter : IItemV1NativeAdapter
    {
        public ItemV1SurfaceCapture CaptureSurface() => ItemV1SurfaceCapture.Unsupported();
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) =>
            throw new InvalidOperationException("Unsupported item child.");
    }
}

public sealed class EventOrchestratorV1CardChildBroker : IEventOrchestratorV1CardChildBroker
{
    private readonly object _gate = new();
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private readonly EventOrchestratorV1AcceptedContext _accepted;
    private readonly object _foreground;
    private readonly EventOrchestratorV1ForegroundGuard _guard;
    private readonly GuardedCardAdapter _adapter;
    private readonly CardSelectionV1Session _session;
    private EventOrchestratorV1ChildStatus _status = EventOrchestratorV1ChildStatus.Active;
    private bool _inside;
    private bool _interfered;
    private bool _disposeRequested;
    private bool _disposed;
    private bool _sessionDisposeAttempted;
    private bool _cleanupComplete;

    public EventOrchestratorV1CardChildBroker(
        EventOrchestratorV1ChildCorrelation correlation,
        EventOrchestratorV1AcceptedContext acceptedContext,
        object exactForegroundIdentity,
        ICardSelectionV1NativeAdapter nativeAdapter,
        EventOrchestratorV1ForegroundGuard foregroundGuard)
    {
        Correlation = correlation ?? throw new ArgumentNullException(nameof(correlation));
        _accepted = acceptedContext ?? throw new ArgumentNullException(nameof(acceptedContext));
        _foreground = exactForegroundIdentity ?? throw new ArgumentNullException(nameof(exactForegroundIdentity));
        _guard = foregroundGuard ?? throw new ArgumentNullException(nameof(foregroundGuard));
        if (!ReferenceEquals(correlation.ParentReceipt, acceptedContext.ParentReceipt) ||
            correlation.Kind != EventOrchestratorV1ChildKind.CardSelection ||
            acceptedContext.ChildPolicy is null ||
            acceptedContext.ChildPolicy.ChildKind != EventOrchestratorV1ChildKind.CardSelection)
            throw new ArgumentException("Card child correlation mismatch.", nameof(correlation));

        _adapter = new GuardedCardAdapter(nativeAdapter ??
            throw new ArgumentNullException(nameof(nativeAdapter)));
        EventOrchestratorV1ChildPolicy policy = acceptedContext.ChildPolicy;
        var context = new CardSelectionV1ParentContext(
            correlation.ParentReceipt.SessionNonce,
            CardSelectionV1ParentKind.Event,
            correlation.ParentReceipt.DecisionId,
            correlation.ParentReceipt.ActionId,
            correlation,
            acceptedContext.RunIdentity,
            acceptedContext.PlayerIdentity,
            acceptedContext.RoomIdentity,
            acceptedContext.MapIdentity,
            acceptedContext.OptionIdentity,
            acceptedContext.ControllerIdentity,
            policy.CardOperation,
            policy.MinSelect,
            policy.MaxSelect,
            policy.CardCommitMode,
            policy.ExpectedDomainCount);
        _session = new CardSelectionV1Session(context, _adapter);
    }

    public EventOrchestratorV1ChildCorrelation Correlation { get; }
    public EventOrchestratorV1ChildStatus Status { get { lock (_gate) return _status; } }

    public ICardSelectionV1ReadValue Read()
    {
        lock (_gate)
        {
            if (!Enter()) return UnsupportedRead();
            try
            {
                if (!Authorize()) return UnsupportedRead();
                _adapter.Begin();
                ICardSelectionV1ReadValue result = _session.Read();
                _adapter.End();
                if (_interfered) return FailRead();
                if (result is CardSelectionV1ResolvedResult)
                    _status = EventOrchestratorV1ChildStatus.Resolved;
                else if (result is CardSelectionV1Observation value && value.Status == "unsupported")
                    _status = EventOrchestratorV1ChildStatus.Failed;
                return result;
            }
            catch { return FailRead(); }
            finally { _adapter.End(); ExitAndDrain(); }
        }
    }

    public ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (!Enter()) return UnsupportedApply();
            try
            {
                if (!Authorize()) return UnsupportedApply();
                _adapter.Begin();
                ICardSelectionV1ApplyValue result = _session.Apply(decisionId, actionId);
                _adapter.End();
                if (_interfered) return FailApply();
                if (result is CardSelectionV1ApplyFailure)
                    _status = EventOrchestratorV1ChildStatus.Failed;
                return result;
            }
            catch { return FailApply(); }
            finally { _adapter.End(); ExitAndDrain(); }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_cleanupComplete) return;
            _status = EventOrchestratorV1ChildStatus.Failed;
            if (Environment.CurrentManagedThreadId != _owner)
            {
                _disposeRequested = true;
                throw new InvalidOperationException("Card child cleanup requires its owner thread.");
            }
            if (_inside)
            {
                _interfered = true;
                _disposeRequested = true;
                return;
            }
            _disposed = true;
            _adapter.End();
            FinishCleanup();
        }
    }

    private bool Enter()
    {
        if (_inside) { _interfered = true; _status = EventOrchestratorV1ChildStatus.Failed; return false; }
        if (_disposed || _status != EventOrchestratorV1ChildStatus.Active ||
            Environment.CurrentManagedThreadId != _owner)
        {
            _status = EventOrchestratorV1ChildStatus.Failed;
            return false;
        }
        _inside = true;
        return true;
    }

    private void ExitAndDrain()
    {
        _inside = false;
        if (_disposeRequested && Environment.CurrentManagedThreadId == _owner)
        {
            _disposeRequested = false;
            _disposed = true;
            _status = EventOrchestratorV1ChildStatus.Failed;
            try { FinishCleanup(); }
            catch { }
        }
    }

    private void FinishCleanup()
    {
        if (_cleanupComplete) return;
        if (!_sessionDisposeAttempted)
        {
            _sessionDisposeAttempted = true;
            _session.Dispose();
        }
        else
        {
            _adapter.Dispose();
        }
        _cleanupComplete = true;
    }

    private bool Authorize()
    {
        bool valid;
        try { valid = _guard(_accepted, _foreground); }
        catch { valid = false; }
        if (!valid || _interfered)
        {
            _status = EventOrchestratorV1ChildStatus.Failed;
            return false;
        }
        return true;
    }

    private ICardSelectionV1ReadValue FailRead()
    {
        _status = EventOrchestratorV1ChildStatus.Failed;
        return UnsupportedRead();
    }

    private ICardSelectionV1ApplyValue FailApply()
    {
        _status = EventOrchestratorV1ChildStatus.Failed;
        return UnsupportedApply();
    }

    private ICardSelectionV1ReadValue UnsupportedRead()
    {
        _status = EventOrchestratorV1ChildStatus.Failed;
        _adapter.Fail();
        _adapter.Begin();
        try { return _session.Read(); }
        finally { _adapter.End(); }
    }

    private ICardSelectionV1ApplyValue UnsupportedApply()
    {
        _status = EventOrchestratorV1ChildStatus.Failed;
        _adapter.Fail();
        _adapter.Begin();
        try { return _session.Apply(null, null); }
        finally { _adapter.End(); }
    }

    private sealed class GuardedCardAdapter : ICardSelectionV1NativeAdapter
    {
        private ICardSelectionV1NativeAdapter? _inner;
        private bool _authorized;
        private bool _failed;
        internal GuardedCardAdapter(ICardSelectionV1NativeAdapter inner) => _inner = inner;
        internal void Begin() => _authorized = true;
        internal void End() => _authorized = false;
        internal void Fail() => _failed = true;
        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            if (!_authorized || _inner is null)
                throw new InvalidOperationException("Card child is outside its guarded operation.");
            if (_failed) throw new InvalidOperationException("Card child foreground changed.");
            return _inner.CaptureSurface();
        }
        public void Dispose()
        {
            ICardSelectionV1NativeAdapter? inner = _inner;
            _authorized = false;
            if (inner is null) return;
            inner.Dispose();
            _inner = null;
        }
    }
}
