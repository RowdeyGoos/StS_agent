using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Parents;

public sealed class CardSelectionParentV1Session : IDisposable
{
    private readonly object _gate = new();
    private readonly int _ownerThreadId = Environment.CurrentManagedThreadId;
    private readonly string _nonce;
    private readonly ICardSelectionParentV1NativeAdapter _adapter;
    private readonly HashSet<string> _reserved = new(StringComparer.Ordinal);
    private BoundParent? _bound;
    private Published? _published;
    private ChildAdmission? _childAdmission;
    private CardSelectionV1Session? _child;
    private CardSelectionV1ResolvedResult? _childResult;
    private CardSelectionParentV1DispatchReceipt? _beginReceipt;
    private CardSelectionParentV1DispatchReceipt? _proceedReceipt;
    private CardSelectionParentV1ResolvedResult? _resolved;
    private string? _afterWitness;
    private bool _inside;
    private bool _interfered;
    private bool _unsupported;
    private bool _disposed;
    private bool _disposeRequested;
    private bool _cleanupFailed;
    private bool _adapterDisposeAttempted;
    private bool _childDisposeAttempted;
    private int _accepted;
    private int _pendingReads;

    public CardSelectionParentV1Session(
        string sessionNonce,
        ICardSelectionParentV1NativeAdapter adapter)
    {
        if (!IsLowerHex(sessionNonce, 32))
            throw new ArgumentException("The parent session nonce is invalid.", nameof(sessionNonce));
        _nonce = sessionNonce;
        _adapter = adapter ?? throw new ArgumentNullException(nameof(adapter));
    }

    public ICardSelectionParentV1ReadValue Read()
    {
        lock (_gate)
        {
            if (!Enter()) return Unsupported();
            ICardSelectionParentV1ReadValue result;
            try
            {
                result = ReadCore();
            }
            catch
            {
                LatchUnsupported();
                result = Unsupported();
            }
            finally
            {
                ExitAndDrain();
            }
            return result;
        }
    }

    public ICardSelectionParentV1ApplyValue Apply(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (!Enter()) return Failure("unsupported");
            ICardSelectionParentV1ApplyValue result;
            try
            {
                result = ApplyCore(decisionId, actionId);
            }
            catch
            {
                LatchUnsupported();
                result = Failure("unsupported");
            }
            finally
            {
                ExitAndDrain();
            }
            return result;
        }
    }

    public ICardSelectionV1ReadValue ReadChild()
    {
        lock (_gate)
        {
            if (!Enter()) return ChildUnsupported();
            ICardSelectionV1ReadValue result;
            try
            {
                result = ReadChildCore();
            }
            catch
            {
                LatchUnsupported();
                result = ChildUnsupported();
            }
            finally
            {
                ExitAndDrain();
            }
            return result;
        }
    }

    public ICardSelectionV1ApplyValue ApplyChild(string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (!Enter()) return ChildFailure("unsupported");
            ICardSelectionV1ApplyValue result;
            try
            {
                if (_unsupported || _disposed || _child is null || _childResult is not null)
                    result = ChildFailure("unsupported");
                else
                    result = _child.Apply(decisionId, actionId);
                if (result is CardSelectionV1ApplyFailure childFailure &&
                    childFailure.Outcome is "unsupported" or "uncertain")
                    LatchUnsupported();
                if (_interfered)
                {
                    LatchUnsupported();
                    result = ChildFailure("unsupported");
                }
            }
            catch
            {
                LatchUnsupported();
                result = ChildFailure("uncertain");
            }
            finally
            {
                ExitAndDrain();
            }
            return result;
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (Environment.CurrentManagedThreadId != _ownerThreadId)
                throw new InvalidOperationException("Parent cleanup requires the owner thread.");
            if (_inside)
            {
                _interfered = true;
                _disposeRequested = true;
                return;
            }
            _disposeRequested = true;
            CleanupOwned();
            if (_cleanupFailed)
                throw new InvalidOperationException("Parent cleanup failed.");
        }
    }

    private ICardSelectionParentV1ReadValue ReadCore()
    {
        if (_unsupported || _disposed) return Unsupported();
        if (_resolved is not null) return _resolved;
        if (_proceedReceipt is not null)
            return ReadExit();
        if (_childResult is not null)
            return ReadAfter();
        if (_beginReceipt is not null)
            return ReadForChild();
        return ReadInitial();
    }

    private ICardSelectionParentV1ReadValue ReadInitial()
    {
        CardSelectionParentV1SurfaceCapture capture;
        try { capture = Capture(); }
        catch { return FailRead(); }
        if (_interfered) return FailRead();
        if (capture.Status == CardSelectionParentV1SurfaceStatus.Missing)
            return _bound is null ? Waiting("initial") : FailRead();
        if (!TryValidateInitial(capture, out BoundParent? bound))
            return FailRead();
        _bound ??= bound;
        if (!SameBound(_bound!, capture) || !SamePolicy(_bound!.Policy, capture.Policy))
            return FailRead();
        var actions = new[] { CardSelectionParentV1Limits.BeginAction };
        string decision = DecisionId(capture, actions);
        _published = new Published(capture, decision, actions[0], capture.BeginControl!);
        return Observation(capture, "ready", "initial", decision, actions);
    }

    private ICardSelectionParentV1ApplyValue ApplyCore(string? decisionId, string? actionId)
    {
        if (_unsupported || _disposed || _published is null ||
            !IsLowerHex(decisionId, 64) || string.IsNullOrEmpty(actionId) ||
            !string.Equals(_published.DecisionId, decisionId, StringComparison.Ordinal) ||
            !string.Equals(_published.ActionId, actionId, StringComparison.Ordinal) ||
            _reserved.Contains(decisionId!) ||
            _accepted >= CardSelectionParentV1Limits.MaximumAcceptedActions)
            return Failure("rejected");

        CardSelectionParentV1SurfaceCapture capture;
        try { capture = Capture(); }
        catch { return FailApply("unsupported"); }
        if (_interfered || !SamePublished(_published, capture))
            return FailApply("unsupported");

        _reserved.Add(decisionId!);
        _accepted++;
        _published = null;
        _pendingReads = 0;
        var receipt = new CardSelectionParentV1DispatchReceipt(_nonce, decisionId!, actionId!);
        try
        {
            captureControl(capture, actionId!)!.Dispatch();
            if (_interfered || _disposeRequested)
                throw new InvalidOperationException("Parent dispatch was interrupted.");
        }
        catch
        {
            LatchUnsupported();
            return Failure("uncertain");
        }

        if (string.Equals(actionId, CardSelectionParentV1Limits.BeginAction,
                StringComparison.Ordinal))
            _beginReceipt = receipt;
        else
            _proceedReceipt = receipt;
        return receipt;
    }

    private ICardSelectionParentV1ReadValue ReadForChild()
    {
        if (!PendingBudget()) return Unsupported();
        CardSelectionParentV1SurfaceCapture capture = Capture();
        if (_interfered) return FailRead();
        if (_childAdmission is null && ValidatePreChildTransient(capture))
            return Waiting("transient");
        if (!ValidateChildCapture(capture))
            return FailRead();

        if (string.Equals(_bound!.InitialWitness, capture.StructuralWitness,
                StringComparison.Ordinal))
            return FailRead();

        if (_childAdmission is null)
            _childAdmission = new ChildAdmission(
                capture.ScreenIdentity!, capture.ChildFactory!, capture.StructuralWitness);
        else if (!ReferenceEquals(_childAdmission.ScreenIdentity, capture.ScreenIdentity) ||
                 !ReferenceEquals(_childAdmission.Factory, capture.ChildFactory) ||
                 _childAdmission.StructuralWitness != capture.StructuralWitness)
            return FailRead();
        return Waiting("card_child");
    }

    private ICardSelectionV1ReadValue ReadChildCore()
    {
        if (_childResult is not null) return _childResult;
        if (_unsupported || _disposed || _beginReceipt is null)
            return ChildUnsupported();
        bool created = false;
        if (_child is null)
        {
            if (_childAdmission is null) return ChildWaiting();
            CardSelectionParentV1SurfaceCapture capture = Capture();
            if (_interfered || !ValidateChildCapture(capture) ||
                capture.StructuralWitness != _childAdmission.StructuralWitness ||
                !ReferenceEquals(capture.ScreenIdentity, _childAdmission.ScreenIdentity) ||
                !ReferenceEquals(capture.ChildFactory, _childAdmission.Factory))
                return FailChildRead();

            var context = new CardSelectionV1ParentContext(
                _nonce,
                _bound!.Policy.ParentKind,
                _beginReceipt.DecisionId,
                _beginReceipt.ActionId,
                _beginReceipt,
                _bound.RunIdentity,
                _bound.PlayerIdentity,
                _bound.RoomIdentity,
                _bound.MapIdentity,
                _bound.ParentOptionIdentity,
                _bound.ParentControllerIdentity,
                _bound.Policy.Operation,
                _bound.Policy.MinSelect,
                _bound.Policy.MaxSelect,
                _bound.Policy.CommitMode,
                _bound.Policy.ExpectedDomainCount);

            ICardSelectionV1NativeAdapter? native = null;
            ScreenBoundAdapter? guarded = null;
            try
            {
                native = _childAdmission.Factory.Create(context, _childAdmission.ScreenIdentity);
                if (native is null) throw new InvalidOperationException("Missing child adapter.");
                if (_interfered) throw new InvalidOperationException("Child factory reentered.");
                guarded = new ScreenBoundAdapter(native, _childAdmission.ScreenIdentity);
                native = null;
                _child = new CardSelectionV1Session(context, guarded);
                guarded = null;
                created = true;
            }
            catch
            {
                DisposeOwnedAfterConstructionFailure(guarded ?? native);
                return FailChildRead();
            }
        }

        ICardSelectionV1ReadValue result = _child.Read();
        if (_interfered) return FailChildRead();
        if (created && (result is not CardSelectionV1Observation initial ||
            initial.Status != "ready" || initial.Phase != "selecting" ||
            initial.SelectedSlots.Count != 0 || initial.PriorResults.Count != 0))
            return FailChildRead();
        if (result is CardSelectionV1ResolvedResult resolved)
        {
            _childResult = resolved;
            _childAdmission = null;
        }
        else if (result is CardSelectionV1Observation observation &&
                 observation.Status == "unsupported")
        {
            return FailChildRead();
        }
        else if (_childResult is null && result is CardSelectionV1Observation ready &&
                 ready.Status == "ready" && _childResult is null &&
                 _childDisposeAttempted == false && ready.PriorResults.Count == 0 &&
                 ready.SelectedSlots.Count != 0)
        {
            return FailChildRead();
        }
        return result;
    }

    private ICardSelectionParentV1ReadValue ReadAfter()
    {
        if (!PendingBudget()) return Unsupported();
        CardSelectionParentV1SurfaceCapture capture = Capture();
        if (_interfered) return FailRead();
        if (_afterWitness is null && ValidateAfterTransient(capture))
            return Waiting("after");
        if (!ValidateAfter(capture)) return FailRead();
        _afterWitness ??= capture.StructuralWitness;
        if (!string.Equals(_afterWitness, capture.StructuralWitness, StringComparison.Ordinal))
            return FailRead();
        var actions = new[] { CardSelectionParentV1Limits.ProceedAction };
        string decision = DecisionId(capture, actions);
        _published = new Published(capture, decision, actions[0], capture.ProceedControl!);
        return Observation(capture, "ready", "after", decision, actions);
    }

    private ICardSelectionParentV1ReadValue ReadExit()
    {
        if (!PendingBudget()) return Unsupported();
        CardSelectionParentV1SurfaceCapture capture = Capture();
        if (_interfered) return FailRead();
        if (!ValidateCommon(capture) || capture.Status != CardSelectionParentV1SurfaceStatus.Available)
            return FailRead();
        if (capture.Phase == CardSelectionParentV1Phase.After && ValidateAfter(capture) &&
            capture.StructuralWitness == _afterWitness)
            return Waiting("exit");
        if (ValidateExitTransient(capture))
            return Waiting("exit");
        if (capture.Phase != CardSelectionParentV1Phase.Exit || !capture.NoActiveOverlay ||
            !capture.MapOpen || !capture.TravelEnabled || capture.Traveling ||
            !capture.EffectCompletionObserved || capture.ScreenIdentity is not null ||
            capture.ChildFactory is not null || capture.BeginControl is not null ||
            capture.ProceedControl is not null)
            return FailRead();
        _resolved = new CardSelectionParentV1ResolvedResult(
            _nonce,
            _beginReceipt!.DecisionId,
            _beginReceipt.ActionId,
            _proceedReceipt!.DecisionId,
            _proceedReceipt.ActionId);
        return _resolved;
    }

    private bool TryValidateInitial(CardSelectionParentV1SurfaceCapture capture, out BoundParent? bound)
    {
        bound = null;
        if (capture.Status != CardSelectionParentV1SurfaceStatus.Available ||
            capture.Phase != CardSelectionParentV1Phase.Initial || !ValidPolicy(capture.Policy) ||
            !ValidWitness(capture.StructuralWitness) || capture.RunIdentity is null ||
            capture.PlayerIdentity is null || capture.RoomIdentity is null ||
            capture.MapIdentity is null || capture.ParentOptionIdentity is null ||
            capture.ParentControllerIdentity is null || !capture.NoActiveOverlay ||
            capture.MapOpen || capture.TravelEnabled || capture.Traveling || capture.EventFinished ||
            capture.EventProceedSingleton || capture.RestControlsRestored ||
            capture.EffectCompletionObserved || capture.ScreenIdentity is not null ||
            capture.ChildFactory is not null || !ValidEnabled(capture.BeginControl) ||
            (capture.ProceedControl is not null && capture.ProceedControl.Enabled))
            return false;
        bound = new BoundParent(capture);
        return true;
    }

    private bool ValidateAfter(CardSelectionParentV1SurfaceCapture capture)
    {
        if (!ValidateCommon(capture) || capture.Status != CardSelectionParentV1SurfaceStatus.Available ||
            capture.Phase != CardSelectionParentV1Phase.After || !capture.NoActiveOverlay ||
            capture.MapOpen || capture.Traveling || !capture.EffectCompletionObserved ||
            capture.ScreenIdentity is not null || capture.ChildFactory is not null ||
            capture.BeginControl is not null || !ValidEnabled(capture.ProceedControl) ||
            string.Equals(_bound!.InitialWitness, capture.StructuralWitness, StringComparison.Ordinal))
            return false;
        if (_bound.Policy.ParentKind == CardSelectionV1ParentKind.Event)
            return !capture.TravelEnabled && capture.EventFinished &&
                capture.EventProceedSingleton && !capture.RestControlsRestored;
        return capture.TravelEnabled && !capture.EventFinished &&
            !capture.EventProceedSingleton && capture.RestControlsRestored;
    }

    private bool ValidateChildCapture(CardSelectionParentV1SurfaceCapture capture) =>
        ValidateCommon(capture) && capture.Status == CardSelectionParentV1SurfaceStatus.Available &&
        capture.Phase == CardSelectionParentV1Phase.Child && capture.ScreenIdentity is not null &&
        capture.ChildFactory is not null && capture.BeginControl is null &&
        capture.ProceedControl is null && !capture.NoActiveOverlay && !capture.MapOpen &&
        !capture.TravelEnabled && !capture.Traveling && !capture.EventFinished &&
        !capture.EventProceedSingleton && !capture.RestControlsRestored &&
        !capture.EffectCompletionObserved;

    private bool ValidatePreChildTransient(CardSelectionParentV1SurfaceCapture capture) =>
        ValidateCommon(capture) && capture.Status == CardSelectionParentV1SurfaceStatus.Available &&
        capture.Phase == CardSelectionParentV1Phase.Transient && !capture.MapOpen &&
        !capture.TravelEnabled && !capture.Traveling && !capture.EventFinished &&
        !capture.EventProceedSingleton && !capture.RestControlsRestored &&
        !capture.EffectCompletionObserved && capture.ScreenIdentity is null &&
        capture.ChildFactory is null && capture.BeginControl is null &&
        capture.ProceedControl is null &&
        !string.Equals(_bound!.InitialWitness, capture.StructuralWitness,
            StringComparison.Ordinal);

    private bool ValidateAfterTransient(CardSelectionParentV1SurfaceCapture capture) =>
        ValidateCommon(capture) && capture.Status == CardSelectionParentV1SurfaceStatus.Available &&
        capture.Phase == CardSelectionParentV1Phase.Transient && capture.NoActiveOverlay &&
        !capture.MapOpen && !capture.TravelEnabled && !capture.Traveling &&
        !capture.EventFinished && !capture.EventProceedSingleton &&
        !capture.RestControlsRestored && !capture.EffectCompletionObserved &&
        capture.ScreenIdentity is null && capture.ChildFactory is null &&
        capture.BeginControl is null && capture.ProceedControl is null &&
        !string.Equals(_bound!.InitialWitness, capture.StructuralWitness,
            StringComparison.Ordinal);

    private bool ValidateExitTransient(CardSelectionParentV1SurfaceCapture capture)
    {
        if (!ValidateCommon(capture) || capture.Status != CardSelectionParentV1SurfaceStatus.Available ||
            capture.Phase != CardSelectionParentV1Phase.Transient || !capture.NoActiveOverlay ||
            capture.MapOpen || capture.Traveling || !capture.EffectCompletionObserved ||
            capture.ScreenIdentity is not null || capture.ChildFactory is not null ||
            capture.BeginControl is not null || capture.ProceedControl is not null ||
            !string.Equals(capture.StructuralWitness, _afterWitness, StringComparison.Ordinal))
            return false;
        return _bound!.Policy.ParentKind == CardSelectionV1ParentKind.Event
            ? !capture.TravelEnabled && capture.EventFinished &&
                capture.EventProceedSingleton && !capture.RestControlsRestored
            : capture.TravelEnabled && !capture.EventFinished &&
                !capture.EventProceedSingleton && capture.RestControlsRestored;
    }

    private bool ValidateCommon(CardSelectionParentV1SurfaceCapture capture) =>
        _bound is not null && ValidWitness(capture.StructuralWitness) &&
        SameBound(_bound, capture) && SamePolicy(_bound.Policy, capture.Policy);

    private static bool SameBound(BoundParent bound, CardSelectionParentV1SurfaceCapture capture) =>
        ReferenceEquals(bound.RunIdentity, capture.RunIdentity) &&
        ReferenceEquals(bound.PlayerIdentity, capture.PlayerIdentity) &&
        ReferenceEquals(bound.RoomIdentity, capture.RoomIdentity) &&
        ReferenceEquals(bound.MapIdentity, capture.MapIdentity) &&
        ReferenceEquals(bound.ParentOptionIdentity, capture.ParentOptionIdentity) &&
        ReferenceEquals(bound.ParentControllerIdentity, capture.ParentControllerIdentity);

    private static bool ValidPolicy(CardSelectionParentV1Policy? policy)
    {
        if (policy is null || string.IsNullOrEmpty(policy.ParentStableKey)) return false;
        return policy.Kind switch
        {
            CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo =>
                policy.ParentKind == CardSelectionV1ParentKind.Event &&
                policy.ParentStableKey == CardSelectionParentV1Limits.CheeseGorgeStableKey &&
                policy.SmithCount == 0 && policy.Operation == CardSelectionV1Operation.Add &&
                policy.MinSelect == 2 && policy.MaxSelect == 2 &&
                policy.CommitMode == CardSelectionV1CommitMode.AutoAtMax &&
                policy.ExpectedDomainCount == 8,
            CardSelectionParentV1PolicyKind.RestSmithUpgradeOne =>
                policy.ParentKind == CardSelectionV1ParentKind.Rest &&
                policy.ParentStableKey == CardSelectionParentV1Limits.SmithStableKey &&
                policy.SmithCount == 1 && policy.Operation == CardSelectionV1Operation.Upgrade &&
                policy.MinSelect == 1 && policy.MaxSelect == 1 &&
                policy.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
                policy.ExpectedDomainCount is >= 1 and <= CardSelectionV1Limits.MaximumCandidates,
            _ => false,
        };
    }

    private static bool SamePolicy(CardSelectionParentV1Policy a, CardSelectionParentV1Policy? b) =>
        b is not null && a.Kind == b.Kind && a.ParentKind == b.ParentKind &&
        a.ParentStableKey == b.ParentStableKey && a.SmithCount == b.SmithCount &&
        a.Operation == b.Operation && a.MinSelect == b.MinSelect &&
        a.MaxSelect == b.MaxSelect && a.CommitMode == b.CommitMode &&
        a.ExpectedDomainCount == b.ExpectedDomainCount;

    private bool SamePublished(Published published, CardSelectionParentV1SurfaceCapture capture)
    {
        bool validPhase = published.ActionId == CardSelectionParentV1Limits.BeginAction
            ? TryValidateInitial(capture, out _)
            : ValidateAfter(capture);
        if (!validPhase || !SameBound(_bound!, capture) ||
            !SameCaptureShape(published.Capture, capture) ||
            capture.Status != CardSelectionParentV1SurfaceStatus.Available ||
            capture.Phase != published.Capture.Phase ||
            capture.StructuralWitness != published.Capture.StructuralWitness ||
            !SamePolicy(published.Capture.Policy, capture.Policy)) return false;
        CardSelectionParentV1NativeControl? control = captureControl(capture, published.ActionId);
        return control is not null && control.Visible && control.Enabled &&
            ReferenceEquals(control.Identity, published.Control.Identity) &&
            ReferenceEquals(control.Dispatch, published.Control.Dispatch);
    }

    private static bool SameCaptureShape(
        CardSelectionParentV1SurfaceCapture left,
        CardSelectionParentV1SurfaceCapture right) =>
        left.Status == right.Status && left.Phase == right.Phase &&
        left.StructuralWitness == right.StructuralWitness &&
        left.NoActiveOverlay == right.NoActiveOverlay &&
        left.MapOpen == right.MapOpen && left.TravelEnabled == right.TravelEnabled &&
        left.Traveling == right.Traveling && left.EventFinished == right.EventFinished &&
        left.EventProceedSingleton == right.EventProceedSingleton &&
        left.RestControlsRestored == right.RestControlsRestored &&
        left.EffectCompletionObserved == right.EffectCompletionObserved &&
        ReferenceEquals(left.RunIdentity, right.RunIdentity) &&
        ReferenceEquals(left.PlayerIdentity, right.PlayerIdentity) &&
        ReferenceEquals(left.RoomIdentity, right.RoomIdentity) &&
        ReferenceEquals(left.MapIdentity, right.MapIdentity) &&
        ReferenceEquals(left.ParentOptionIdentity, right.ParentOptionIdentity) &&
        ReferenceEquals(left.ParentControllerIdentity, right.ParentControllerIdentity) &&
        ReferenceEquals(left.ScreenIdentity, right.ScreenIdentity) &&
        ReferenceEquals(left.ChildFactory, right.ChildFactory) &&
        SameControl(left.BeginControl, right.BeginControl) &&
        SameControl(left.ProceedControl, right.ProceedControl);

    private static bool SameControl(
        CardSelectionParentV1NativeControl? left,
        CardSelectionParentV1NativeControl? right)
    {
        if (left is null || right is null) return left is null && right is null;
        return left.Visible == right.Visible && left.Enabled == right.Enabled &&
            ReferenceEquals(left.Identity, right.Identity) &&
            ReferenceEquals(left.Dispatch, right.Dispatch);
    }

    private static CardSelectionParentV1NativeControl? captureControl(
        CardSelectionParentV1SurfaceCapture capture, string actionId) =>
        actionId == CardSelectionParentV1Limits.BeginAction
            ? capture.BeginControl : capture.ProceedControl;

    private static bool ValidEnabled(CardSelectionParentV1NativeControl? control) =>
        control is not null && control.Identity is not null && control.Visible && control.Enabled &&
        control.Dispatch is not null;

    private CardSelectionParentV1SurfaceCapture Capture()
    {
        CardSelectionParentV1SurfaceCapture capture = _adapter.CaptureSurface();
        return capture ?? throw new InvalidOperationException("Missing parent capture.");
    }

    private bool PendingBudget()
    {
        if (++_pendingReads <= CardSelectionParentV1Limits.MaximumPendingReads) return true;
        LatchUnsupported();
        return false;
    }

    private CardSelectionParentV1Observation Observation(
        CardSelectionParentV1SurfaceCapture capture,
        string status,
        string phase,
        string decision,
        IReadOnlyList<string> actions) =>
        new(_nonce, status, phase,
            capture.Policy.ParentKind == CardSelectionV1ParentKind.Event ? "event" : "rest",
            capture.Policy.Kind == CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo
                ? "cheese_gorge_add_two" : "rest_smith_upgrade_one",
            decision, actions);

    private string DecisionId(CardSelectionParentV1SurfaceCapture capture, IReadOnlyList<string> actions)
    {
        var text = new StringBuilder();
        Append(text, _nonce);
        Append(text, ((int)capture.Policy.Kind).ToString(CultureInfo.InvariantCulture));
        Append(text, ((int)capture.Policy.ParentKind).ToString(CultureInfo.InvariantCulture));
        Append(text, capture.Policy.SmithCount.ToString(CultureInfo.InvariantCulture));
        Append(text, ((int)capture.Policy.Operation).ToString(CultureInfo.InvariantCulture));
        Append(text, capture.Policy.MinSelect.ToString(CultureInfo.InvariantCulture));
        Append(text, capture.Policy.MaxSelect.ToString(CultureInfo.InvariantCulture));
        Append(text, ((int)capture.Policy.CommitMode).ToString(CultureInfo.InvariantCulture));
        Append(text, capture.Policy.ExpectedDomainCount.ToString(CultureInfo.InvariantCulture));
        Append(text, ((int)capture.Phase).ToString(CultureInfo.InvariantCulture));
        Append(text, capture.StructuralWitness);
        Append(text, capture.Policy.ParentStableKey);
        for (int i = 0; i < actions.Count; i++) Append(text, actions[i]);
        byte[] bytes = Encoding.ASCII.GetBytes(text.ToString());
        byte[] digest = SHA256.HashData(bytes);
        CryptographicOperations.ZeroMemory(bytes);
        return Convert.ToHexString(digest).ToLowerInvariant();
    }

    private static void Append(StringBuilder builder, string value) =>
        builder.Append(value.Length.ToString(CultureInfo.InvariantCulture)).Append(':').Append(value);

    private bool Enter()
    {
        if (_inside)
        {
            _interfered = true;
            return false;
        }
        if (Environment.CurrentManagedThreadId != _ownerThreadId)
        {
            LatchUnsupported();
            return false;
        }
        if (_disposed || _cleanupFailed) return false;
        _inside = true;
        return true;
    }

    private void ExitAndDrain()
    {
        _inside = false;
        if (_interfered) LatchUnsupported();
        if (_disposeRequested) CleanupOwned();
    }

    private void CleanupOwned()
    {
        _disposed = true;
        _unsupported = true;
        _published = null;
        _childAdmission = null;
        Exception? failure = null;
        bool priorInterference = _interfered;
        _interfered = false;
        _inside = true;
        try
        {
            if (!_childDisposeAttempted && _child is not null)
            {
                _childDisposeAttempted = true;
                try { _child.Dispose(); }
                catch (Exception error) { failure = error; }
            }
            if (!_adapterDisposeAttempted)
            {
                _adapterDisposeAttempted = true;
                try { _adapter.Dispose(); }
                catch (Exception error) { failure ??= error; }
            }
        }
        finally
        {
            _inside = false;
            bool cleanupInterference = _interfered;
            _interfered = priorInterference || cleanupInterference;
            if (cleanupInterference)
                failure ??= new InvalidOperationException("Parent cleanup was reentered.");
        }
        if (failure is not null) _cleanupFailed = true;
    }

    private void LatchUnsupported()
    {
        _unsupported = true;
        _published = null;
        _childAdmission = null;
    }

    private ICardSelectionParentV1ReadValue FailRead()
    {
        LatchUnsupported();
        return Unsupported();
    }

    private ICardSelectionParentV1ApplyValue FailApply(string outcome)
    {
        LatchUnsupported();
        return Failure(outcome);
    }

    private ICardSelectionV1ReadValue FailChildRead()
    {
        LatchUnsupported();
        return ChildUnsupported();
    }

    private CardSelectionParentV1Observation Waiting(string phase) =>
        CardSelectionParentV1Observation.Fixed(_nonce, "waiting", phase);
    private CardSelectionParentV1Observation Unsupported() =>
        CardSelectionParentV1Observation.Fixed(_nonce, "unsupported", "unsupported");
    private CardSelectionParentV1ApplyFailure Failure(string outcome) => new(_nonce, outcome);

    private CardSelectionParentV1ChildUnavailable ChildWaiting() => new(_nonce);
    private CardSelectionParentV1ChildUnavailable ChildUnsupported() => new(_nonce);
    private CardSelectionParentV1ChildApplyFailure ChildFailure(string outcome) =>
        new(_nonce, outcome);

    private static bool ValidWitness(string? value) =>
        IsLowerHex(value, CardSelectionParentV1Limits.MaximumWitnessLength);

    private static bool IsLowerHex(string? value, int length)
    {
        if (value is null || value.Length != length) return false;
        foreach (char c in value)
            if (c is not (>= '0' and <= '9') and not (>= 'a' and <= 'f')) return false;
        return true;
    }

    private void DisposeOwnedAfterConstructionFailure(IDisposable? value)
    {
        if (value is null) return;
        try { value.Dispose(); }
        catch { _cleanupFailed = true; }
    }

    private sealed record BoundParent(
        CardSelectionParentV1Policy Policy,
        object RunIdentity,
        object PlayerIdentity,
        object RoomIdentity,
        object MapIdentity,
        object ParentOptionIdentity,
        object ParentControllerIdentity,
        string InitialWitness)
    {
        internal BoundParent(CardSelectionParentV1SurfaceCapture capture) : this(
            capture.Policy, capture.RunIdentity!, capture.PlayerIdentity!, capture.RoomIdentity!,
            capture.MapIdentity!, capture.ParentOptionIdentity!, capture.ParentControllerIdentity!,
            capture.StructuralWitness) { }
    }

    private sealed record Published(
        CardSelectionParentV1SurfaceCapture Capture,
        string DecisionId,
        string ActionId,
        CardSelectionParentV1NativeControl Control);

    private sealed record ChildAdmission(
        object ScreenIdentity,
        ICardSelectionParentV1ChildFactory Factory,
        string StructuralWitness);

    private sealed class ScreenBoundAdapter : ICardSelectionV1NativeAdapter
    {
        private readonly ICardSelectionV1NativeAdapter _inner;
        private readonly object _screen;

        internal ScreenBoundAdapter(ICardSelectionV1NativeAdapter inner, object screen)
        {
            _inner = inner;
            _screen = screen;
        }

        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            CardSelectionV1SurfaceCapture capture = _inner.CaptureSurface();
            if (capture is not null && capture.Status == CardSelectionV1SurfaceStatus.Available &&
                !ReferenceEquals(capture.ScreenIdentity, _screen))
                throw new InvalidOperationException("The child screen identity changed.");
            return capture!;
        }

        public void Dispose() => _inner.Dispose();
    }
}
