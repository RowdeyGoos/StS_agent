using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Event.Tests;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int _checks;

    private static int Main()
    {
        try
        {
            Run("ready_and_canonical", ReadyAndCanonical);
            Run("rendered_text_bounds", RenderedTextBounds);
            Run("null_capture_is_fixed_failure", NullCaptureIsFixedFailure);
            Run("invalid_candidates", InvalidCandidates);
            Run("stale_before_reservation", StaleBeforeReservation);
            Run("capture_reentry_guard", CaptureReentryGuard);
            Run("capture_dispose_before_reservation", CaptureDisposeBeforeReservation);
            Run("owner_thread_guard", OwnerThreadGuard);
            Run("reentrant_dispatch", ReentrantDispatch);
            Run("uncertain_is_terminal", UncertainIsTerminal);
            Run("unchanged_projection_waits", UnchangedProjectionWaits);
            Run("changed_projection_unseen_only", ChangedProjectionUnseenOnly);
            Run("text_only_change_does_not_progress", TextOnlyChangeDoesNotProgress);
            Run("aba_key_never_renews", AbaKeyNeverRenews);
            Run("pending_read_cap", PendingReadCap);
            Run("final_allowed_pending_read", FinalAllowedPendingRead);
            Run("proceed_map_handoff", ProceedMapHandoff);
            Run("proceed_wrong_transition", ProceedWrongTransition);
            Run("nonfinal_map_never_completes", NonfinalMapNeverCompletes);
            Run("item_child_lifecycle", ItemChildLifecycle);
            Run("item_child_requires_parent", ItemChildRequiresParent);
            Run("item_child_must_be_first_transition", ItemChildMustBeFirstTransition);
            Run("item_child_after_final_ready_rejected", ItemChildAfterFinalReadyRejected);
            Run("item_child_failure", ItemChildFailure);
            Run("item_child_receipt_mismatch", ItemChildReceiptMismatch);
            Run("item_factory_reentry_guard", ItemFactoryReentryGuard);
            Run("item_factory_dispose_guard", ItemFactoryDisposeGuard);
            Run("item_factory_dispose_failure_observable", ItemFactoryDisposeFailureObservable);
            Run("post_child_text_only_waits", PostChildTextOnlyWaits);
            Run("single_child_only", SingleChildOnly);
            Run("parent_action_cap", ParentActionCap);
            Run("identity_change_fails", IdentityChangeFails);
            Run("dispose_releases_child", DisposeReleasesChild);
            Run("dispose_failure_observable", DisposeFailureObservable);
            Run("off_thread_dispose_drains_on_owner", OffThreadDisposeDrainsOnOwner);
            Run("dispose_suppresses_resolved", DisposeSuppressesResolved);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"room_flows_v1_event\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception.GetType().Name + ": " + exception.Message);
            return 1;
        }
    }

    private static void ReadyAndCanonical()
    {
        var ids = new Identities();
        var candidates = new List<EventV1NativeCandidate>
        {
            Candidate(0, "GAIN_GOLD", "[gold]Gain[/gold]\n100 gold"),
            Candidate(1, "LEAVE", "Leave", dangerous: true),
        };
        var capture = Parent(ids, candidates);
        var adapter = new FakeAdapter(capture);
        var session = Session(adapter);
        EventV1Observation first = Observation(session.Read(), "ready");
        Equal("event_v1", first.Version);
        Equal("event", first.FlowKind);
        Equal(1, first.ParentOrdinal);
        Equal("choose_option", first.Phase);
        Equal(2, first.Candidates.Count);
        Equal("[gold]Gain[/gold]\n100 gold", first.Candidates[0].RenderedText);
        Equal(1, first.LegalActions.Count);
        Equal("choose:0", first.LegalActions[0]);
        True(RoomFlowIdentity.IsDecisionId(first.DecisionId));
        EventV1Observation second = Observation(session.Read(), "ready");
        Equal(first.DecisionId, second.DecisionId);
        string changed = ReadyId(Parent(ids,
            new[] { Candidate(0, "GAIN_GOLD", "Gain 101 gold") }));
        NotEqual(first.DecisionId, changed);
        candidates.Clear();
        Equal(2, first.Candidates.Count);
    }

    private static void RenderedTextBounds()
    {
        string exact = new('é', RoomFlowLimits.MaximumEventTextBytes / 2);
        True(RoomFlowIdentity.IsRenderedText(exact));
        foreach (string invalid in new[]
        {
            string.Empty,
            "bad\0text",
            "bad\rtext",
            "bad\ttext",
            new string('\ud800', 1),
            new string('x', RoomFlowLimits.MaximumEventTextBytes + 1),
        })
        {
            var session = Session(new FakeAdapter(Parent(
                new Identities(), new[] { Candidate(0, "A", invalid) })));
            Observation(session.Read(), "unsupported");
        }
    }

    private static void NullCaptureIsFixedFailure()
    {
        var adapter = new FakeAdapter(Parent(new Identities(),
            new[] { Candidate(0, "A", "text") })) { ReturnNullSurface = true };
        Observation(Session(adapter).Read(), "unsupported");
        var ids = new Identities();
        var exitAdapter = new FakeAdapter(FinalParent(ids));
        var exitSession = Session(exitAdapter);
        EventV1Observation ready = Ready(exitSession);
        Receipt(exitSession.Apply(ready.DecisionId, "choose:0"));
        exitAdapter.ReturnNullExit = true;
        Observation(exitSession.Read(), "unsupported");
    }

    private static void InvalidCandidates()
    {
        var ids = new Identities();
        Observation(Session(new FakeAdapter(Parent(ids, new[]
        {
            Candidate(0, "DUP", "one"), Candidate(1, "DUP", "two"),
        }))).Read(), "unsupported");
        Observation(Session(new FakeAdapter(Parent(ids,
            new[] { Candidate(1, "A", "text") }))).Read(), "unsupported");
        Observation(Session(new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "bad\nkey", "text") }))).Read(), "unsupported");
        Observation(Session(new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "text", proceed: true) }))).Read(), "unsupported");
        Observation(Session(new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "WRONG", "Proceed", proceed: true) }, finished: true))).Read(), "unsupported");
        var tooMany = new List<EventV1NativeCandidate>();
        for (int index = 0; index <= RoomFlowLimits.MaximumEventCandidates; index++)
            tooMany.Add(Candidate(index, "K" + index, "text"));
        Observation(Session(new FakeAdapter(Parent(ids, tooMany))).Read(), "unsupported");
    }

    private static void StaleBeforeReservation()
    {
        var ids = new Identities();
        int dispatches = 0;
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "first", dispatch: () => dispatches++) }));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        adapter.Current = Parent(ids,
            new[] { Candidate(0, "A", "changed", dispatch: () => dispatches++) });
        Failure(session.Apply(ready.DecisionId, "choose:0"), "unsupported");
        Equal(0, dispatches);
        Equal(0, session.ReservedDispatchCount);
        EventV1Observation changed = Ready(session);
        NotEqual(ready.DecisionId, changed.DecisionId);
    }

    private static void CaptureReentryGuard()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "text") }));
        var session = Session(adapter);
        IRoomFlowReadValue? nestedRead = null;
        IRoomFlowApplyValue? nestedApply = null;
        adapter.BeforeSurface = () =>
        {
            adapter.BeforeSurface = null;
            nestedRead = session.Read();
            nestedApply = session.Apply(new string('0', 64), "choose:0");
        };
        Ready(session);
        Observation(nestedRead!, "waiting");
        Failure(nestedApply!, "rejected");
        Equal(0, session.ReservedDispatchCount);
    }

    private static void CaptureDisposeBeforeReservation()
    {
        var ids = new Identities();
        int dispatches = 0;
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "text", dispatch: () => dispatches++) }));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        adapter.BeforeSurface = () =>
        {
            adapter.BeforeSurface = null;
            session.Dispose();
        };
        Failure(session.Apply(ready.DecisionId, "choose:0"), "unsupported");
        Equal(0, session.ReservedDispatchCount);
        Equal(0, dispatches);
        Observation(session.Read(), "unsupported");
    }

    private static void OwnerThreadGuard()
    {
        var adapter = new FakeAdapter(Parent(new Identities(),
            new[] { Candidate(0, "A", "text") }));
        var session = Session(adapter);
        IRoomFlowReadValue? result = null;
        var thread = new System.Threading.Thread(() => result = session.Read());
        thread.Start();
        thread.Join();
        Observation(result!, "unsupported");
        Equal(0, adapter.SurfaceReads);
        Observation(session.Read(), "unsupported");
    }

    private static void ReentrantDispatch()
    {
        var ids = new Identities();
        EventV1Session? session = null;
        string nestedRead = "";
        string nestedApply = "";
        EventV1Observation? published = null;
        Action dispatch = () =>
        {
            nestedRead = Observation(session!.Read(), "waiting").Status;
            nestedApply = Failure(session.Apply(
                published!.DecisionId, published.LegalActions[0]), "rejected").Outcome;
        };
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "text", dispatch: dispatch) }));
        session = Session(adapter);
        published = Ready(session);
        Receipt(session.Apply(published.DecisionId, "choose:0"));
        Equal("waiting", nestedRead);
        Equal("rejected", nestedApply);
        Equal(1, session.ReservedDispatchCount);
    }

    private static void UncertainIsTerminal()
    {
        var ids = new Identities();
        int dispatches = 0;
        var adapter = new FakeAdapter(Parent(ids, new[]
        {
            Candidate(0, "A", "text", dispatch: () =>
            {
                dispatches++;
                throw new InvalidOperationException("private-canary");
            }),
        }));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Failure(session.Apply(ready.DecisionId, "choose:0"), "uncertain");
        Equal(1, dispatches);
        Equal(1, session.ReservedDispatchCount);
        Observation(session.Read(), "unsupported");
        Failure(session.Apply(ready.DecisionId, "choose:0"), "rejected");
        Equal(1, dispatches);
    }

    private static void UnchangedProjectionWaits()
    {
        var ids = new Identities();
        EventV1SurfaceCapture same = Parent(ids, new[]
        {
            Candidate(0, "A", "a"), Candidate(1, "B", "b"),
        });
        var adapter = new FakeAdapter(same);
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = same;
        Observation(session.Read(), "waiting");
        Equal(1, session.ReservedDispatchCount);
    }

    private static void ChangedProjectionUnseenOnly()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var session = Session(adapter);
        EventV1Observation first = Ready(session);
        Receipt(session.Apply(first.DecisionId, "choose:0"));
        adapter.Current = Parent(ids, new[]
        {
            Candidate(0, "A", "a changed"), Candidate(1, "B", "b"),
        });
        EventV1Observation next = Ready(session);
        Equal(2, next.Candidates.Count);
        Equal(1, next.LegalActions.Count);
        Equal("choose:1", next.LegalActions[0]);
        Failure(session.Apply(next.DecisionId, "choose:0"), "rejected");
        Receipt(session.Apply(next.DecisionId, "choose:1"));
        Equal(2, session.ReservedDispatchCount);
    }

    private static void TextOnlyChangeDoesNotProgress()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids, new[]
        {
            Candidate(0, "A", "a"), Candidate(1, "B", "b"),
        }));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = Parent(ids, new[]
        {
            Candidate(0, "A", "a changed"), Candidate(1, "B", "b changed"),
        });
        Observation(session.Read(), "waiting");
    }

    private static void AbaKeyNeverRenews()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var session = Session(adapter);
        EventV1Observation a = Ready(session);
        Receipt(session.Apply(a.DecisionId, "choose:0"));
        adapter.Current = Parent(ids, new[] { Candidate(0, "B", "b") });
        EventV1Observation b = Ready(session);
        Receipt(session.Apply(b.DecisionId, "choose:0"));
        adapter.Current = Parent(ids, new[] { Candidate(0, "A", "a newest") });
        Observation(session.Read(), "waiting");
    }

    private static void PendingReadCap()
    {
        var ids = new Identities();
        EventV1SurfaceCapture same = Parent(ids, new[] { Candidate(0, "A", "a") });
        var adapter = new FakeAdapter(same);
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        for (int read = 1; read < RoomFlowLimits.MaximumPendingReads; read++)
            Observation(session.Read(), "waiting");
        Observation(session.Read(), "unsupported");
    }

    private static void FinalAllowedPendingRead()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(FinalParent(ids));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Exit = Exit(ids, false, false, false);
        for (int read = 1; read < RoomFlowLimits.MaximumPendingReads; read++)
            Observation(session.Read(), "waiting");
        adapter.Exit = Exit(ids, true, true, false);
        Resolved(session.Read(), ready);
    }

    private static void ProceedMapHandoff()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(FinalParent(ids));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Equal("proceed", ready.Phase);
        True(ready.Candidates[0].IsProceed);
        RoomFlowDispatchReceipt receipt = Receipt(
            session.Apply(ready.DecisionId, "choose:0"));
        adapter.Exit = Exit(ids, false, false, false);
        Observation(session.Read(), "waiting");
        adapter.Exit = Exit(ids, true, true, false);
        EventV1ResolvedResult result = Resolved(session.Read(), ready);
        Equal(receipt.DecisionId, result.DecisionId);
        Equal("map_handoff", result.Result);
        Same(result, session.Read());
    }

    private static void ProceedWrongTransition()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(FinalParent(ids));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Exit = Exit(ids, true, false, false);
        Observation(session.Read(), "unsupported");
    }

    private static void NonfinalMapNeverCompletes()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = EventV1SurfaceCapture.Unsupported();
        Observation(session.Read(), "unsupported");
    }

    private static void ItemChildLifecycle()
    {
        var ids = new Identities();
        var itemAdapter = new FakeItemAdapter();
        object childIdentity = new();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = ItemChild(ids, childIdentity, itemAdapter);
        Observation(session.Read(), "item_child");
        Same(factory.Broker, session.ActiveItemChild);
        Same(receipt, factory.ParentReceipt);
        Same(itemAdapter, factory.Adapter);
        factory.Broker!.SetStatus(new EventItemChildResolved(receipt));
        Observation(session.Read(), "waiting");
        True(factory.Broker.Disposed);
        True(session.ActiveItemChild is null);
        adapter.Current = Parent(ids, new[] { Candidate(0, "B", "b") });
        Ready(session);
        Equal(1, factory.CreateCount);
    }

    private static void ItemChildRequiresParent()
    {
        var ids = new Identities();
        var factory = new FakeChildFactory();
        var session = Session(new FakeAdapter(ItemChild(
            ids, new object(), new FakeItemAdapter())), factory);
        Observation(session.Read(), "unsupported");
        Equal(0, factory.CreateCount);
    }

    private static void ItemChildMustBeFirstTransition()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation first = Ready(session);
        Receipt(session.Apply(first.DecisionId, "choose:0"));
        adapter.Current = Parent(ids, new[] { Candidate(0, "B", "b") });
        Ready(session);
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "unsupported");
        Equal(0, factory.CreateCount);
    }

    private static void ItemChildAfterFinalReadyRejected()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation first = Ready(session);
        Receipt(session.Apply(first.DecisionId, "choose:0"));
        adapter.Current = FinalParent(ids);
        Ready(session);
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "unsupported");
        Equal(0, factory.CreateCount);
    }

    private static void ItemChildFailure()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "item_child");
        factory.Broker!.SetStatus(new EventItemChildFailed(
            receipt, new RoomFlowApplyFailure("event", Nonce, "uncertain")));
        Observation(session.Read(), "unsupported");
        True(factory.Broker.Disposed);
    }

    private static void ItemChildReceiptMismatch()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory { CopyReceipt = true };
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "unsupported");
        Equal(1, factory.CreateCount);
    }

    private static void ItemFactoryReentryGuard()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        IRoomFlowReadValue? nestedRead = null;
        IRoomFlowApplyValue? nestedApply = null;
        factory.DuringCreate = () =>
        {
            nestedRead = session.Read();
            nestedApply = session.Apply(ready.DecisionId, "choose:0");
        };
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "item_child");
        Observation(nestedRead!, "waiting");
        Failure(nestedApply!, "rejected");
        Equal(1, factory.CreateCount);
    }

    private static void ItemFactoryDisposeGuard()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        factory.DuringCreate = session.Dispose;
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "unsupported");
        True(factory.Broker!.Disposed);
        True(session.ActiveItemChild is null);
    }

    private static void ItemFactoryDisposeFailureObservable()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory { ThrowOnDispose = true };
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        factory.DuringCreate = session.Dispose;
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        bool threw = false;
        try { session.Read(); }
        catch (InvalidOperationException exception)
        {
            threw = exception.Message == "Event child cleanup failed.";
        }
        True(threw);
        True(session.ActiveItemChild is null);
        session.Dispose();
    }

    private static void PostChildTextOnlyWaits()
    {
        var ids = new Identities();
        var original = new[]
        {
            Candidate(0, "A", "a"), Candidate(1, "B", "b"),
        };
        var adapter = new FakeAdapter(Parent(ids, original));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        RoomFlowDispatchReceipt receipt = Receipt(
            session.Apply(ready.DecisionId, "choose:0"));
        object child = new();
        adapter.Current = ItemChild(ids, child, new FakeItemAdapter());
        Observation(session.Read(), "item_child");
        factory.Broker!.SetStatus(new EventItemChildResolved(receipt));
        adapter.Current = Parent(ids, new[]
        {
            Candidate(0, "A", "new a"), Candidate(1, "B", "new b"),
        });
        Observation(session.Read(), "waiting");
    }

    private static void SingleChildOnly()
    {
        var ids = new Identities();
        object firstChild = new();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation first = Ready(session);
        RoomFlowDispatchReceipt firstReceipt = Receipt(
            session.Apply(first.DecisionId, "choose:0"));
        adapter.Current = ItemChild(ids, firstChild, new FakeItemAdapter());
        Observation(session.Read(), "item_child");
        factory.Broker!.SetStatus(new EventItemChildResolved(firstReceipt));
        Observation(session.Read(), "waiting");
        adapter.Current = Parent(ids, new[] { Candidate(0, "B", "b") });
        EventV1Observation second = Ready(session);
        Receipt(session.Apply(second.DecisionId, "choose:0"));
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "unsupported");
        Equal(1, factory.CreateCount);
    }

    private static void ParentActionCap()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "K0", "text 0") }));
        var session = Session(adapter);
        for (int action = 0; action < RoomFlowLimits.MaximumParentActions; action++)
        {
            adapter.Current = Parent(ids,
                new[] { Candidate(0, "K" + action, "text " + action) });
            EventV1Observation ready = Ready(session);
            Receipt(session.Apply(ready.DecisionId, "choose:0"));
        }
        adapter.Current = Parent(ids,
            new[] { Candidate(0, "K12", "text 12") });
        Observation(session.Read(), "waiting");
        Equal(RoomFlowLimits.MaximumParentActions, session.ReservedDispatchCount);
    }

    private static void IdentityChangeFails()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var session = Session(adapter);
        Ready(session);
        adapter.Current = Parent(new Identities(),
            new[] { Candidate(0, "A", "a") });
        Observation(session.Read(), "unsupported");
    }

    private static void DisposeReleasesChild()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "item_child");
        session.Dispose();
        session.Dispose();
        True(factory.Broker!.Disposed);
        Equal(1, factory.Broker.DisposeCount);
        True(session.ActiveItemChild is null);
        Observation(session.Read(), "unsupported");
    }

    private static void DisposeFailureObservable()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory { ThrowOnDispose = true };
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "item_child");
        bool threw = false;
        try { session.Dispose(); }
        catch (InvalidOperationException) { threw = true; }
        True(threw);
        Observation(session.Read(), "unsupported");
    }

    private static void OffThreadDisposeDrainsOnOwner()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(Parent(ids,
            new[] { Candidate(0, "A", "a") }));
        var factory = new FakeChildFactory();
        var session = Session(adapter, factory);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Current = ItemChild(ids, new object(), new FakeItemAdapter());
        Observation(session.Read(), "item_child");
        var thread = new System.Threading.Thread(session.Dispose);
        thread.Start();
        thread.Join();
        True(!factory.Broker!.Disposed);
        True(session.ActiveItemChild is null);
        session.Dispose();
        True(factory.Broker.Disposed);
        Equal(1, factory.Broker.DisposeCount);
    }

    private static void DisposeSuppressesResolved()
    {
        var ids = new Identities();
        var adapter = new FakeAdapter(FinalParent(ids));
        var session = Session(adapter);
        EventV1Observation ready = Ready(session);
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        adapter.Exit = Exit(ids, true, true, false);
        EventV1ResolvedResult result = Resolved(session.Read(), ready);
        Same(result, session.Read());
        session.Dispose();
        Observation(session.Read(), "unsupported");
    }

    private static EventV1Session Session(
        FakeAdapter adapter,
        FakeChildFactory? factory = null) =>
        new(Nonce, adapter, factory ?? new FakeChildFactory());

    private static EventV1NativeCandidate Candidate(
        int index,
        string key,
        string text,
        bool visible = true,
        bool enabled = true,
        bool locked = false,
        bool dangerous = false,
        bool proceed = false,
        Action? dispatch = null,
        object? button = null,
        object? option = null) =>
        new(index, key, text, visible, enabled, locked, dangerous, proceed,
            button ?? new object(), option ?? new object(), dispatch ?? (() => { }));

    private static EventV1SurfaceCapture Parent(
        Identities ids,
        IReadOnlyList<EventV1NativeCandidate> candidates,
        bool finished = false) =>
        EventV1SurfaceCapture.Parent(
            ids.Run, ids.Player, ids.Room, ids.Map, finished,
            false, false, false, candidates);

    private static EventV1SurfaceCapture FinalParent(Identities ids) =>
        Parent(ids, new[]
        {
            Candidate(0, EventV1Constants.ProceedStableId, "Proceed", proceed: true),
        }, finished: true);

    private static EventV1SurfaceCapture ItemChild(
        Identities ids,
        object childIdentity,
        IItemV1NativeAdapter adapter) =>
        EventV1SurfaceCapture.ItemChild(
            ids.Run, ids.Player, ids.Room, ids.Map, childIdentity, adapter);

    private static EventV1ExitCapture Exit(
        Identities ids,
        bool open,
        bool enabled,
        bool traveling) =>
        new(ids.Run, ids.Player, ids.Room, ids.Map, open, enabled, traveling);

    private static string ReadyId(EventV1SurfaceCapture capture)
    {
        var session = Session(new FakeAdapter(capture));
        return Ready(session).DecisionId;
    }

    private static EventV1Observation Ready(EventV1Session session) =>
        Observation(session.Read(), "ready");

    private static EventV1Observation Observation(IRoomFlowReadValue value, string status)
    {
        if (value is not EventV1Observation observation)
            throw new InvalidOperationException("Expected event observation.");
        Equal(status, observation.Status);
        return observation;
    }

    private static EventV1ResolvedResult Resolved(
        IRoomFlowReadValue value,
        EventV1Observation ready)
    {
        if (value is not EventV1ResolvedResult result)
            throw new InvalidOperationException("Expected event resolved result.");
        Equal(ready.DecisionId, result.DecisionId);
        return result;
    }

    private static RoomFlowDispatchReceipt Receipt(IRoomFlowApplyValue value)
    {
        if (value is not RoomFlowDispatchReceipt receipt)
            throw new InvalidOperationException("Expected accepted receipt.");
        Equal("accepted", receipt.Outcome);
        return receipt;
    }

    private static RoomFlowApplyFailure Failure(IRoomFlowApplyValue value, string outcome)
    {
        if (value is not RoomFlowApplyFailure failure)
            throw new InvalidOperationException("Expected apply failure.");
        Equal(outcome, failure.Outcome);
        return failure;
    }

    private static void Run(string name, Action action)
    {
        try { action(); _checks++; }
        catch (Exception exception)
        {
            throw new InvalidOperationException(name + ": " + exception.Message, exception);
        }
    }

    private static void True(bool value)
    {
        if (!value) throw new InvalidOperationException("Expected true.");
    }

    private static void Same(object? expected, object? actual)
    {
        if (!ReferenceEquals(expected, actual))
            throw new InvalidOperationException("Expected reference identity.");
    }

    private static void Equal<T>(T expected, T actual)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException("Expected " + expected + ", got " + actual + ".");
    }

    private static void NotEqual<T>(T left, T right)
    {
        if (EqualityComparer<T>.Default.Equals(left, right))
            throw new InvalidOperationException("Expected distinct values.");
    }

    private sealed class Identities
    {
        internal object Run { get; } = new();
        internal object Player { get; } = new();
        internal object Room { get; } = new();
        internal object Map { get; } = new();
    }

    private sealed class FakeAdapter : IEventV1NativeAdapter
    {
        internal FakeAdapter(EventV1SurfaceCapture current)
        {
            Current = current;
            Exit = current.RunIdentity is not null
                ? new EventV1ExitCapture(current.RunIdentity, current.PlayerIdentity!,
                    current.RoomIdentity!, current.MapIdentity!, false, false, false)
                : new EventV1ExitCapture(new object(), new object(), new object(),
                    new object(), false, false, false);
        }

        internal EventV1SurfaceCapture Current { get; set; }
        internal EventV1ExitCapture Exit { get; set; }
        internal int SurfaceReads { get; private set; }
        internal int ExitReads { get; private set; }
        internal Action? BeforeSurface { get; set; }
        internal bool ReturnNullSurface { get; set; }
        internal bool ReturnNullExit { get; set; }

        public EventV1SurfaceCapture CaptureSurface()
        {
            SurfaceReads++;
            BeforeSurface?.Invoke();
            if (ReturnNullSurface) return null!;
            return Current;
        }

        public EventV1ExitCapture CaptureExit(EventV1ExitProbe pending)
        {
            ExitReads++;
            if (ReturnNullExit) return null!;
            return Exit;
        }
    }

    private sealed class FakeChildFactory : IEventItemChildFactory
    {
        internal int CreateCount { get; private set; }
        internal FakeChildBroker? Broker { get; private set; }
        internal RoomFlowDispatchReceipt? ParentReceipt { get; private set; }
        internal IItemV1NativeAdapter? Adapter { get; private set; }
        internal bool CopyReceipt { get; set; }
        internal bool ThrowOnDispose { get; set; }
        internal Action? DuringCreate { get; set; }

        public IEventItemChildBroker Create(
            RoomFlowDispatchReceipt parentReceipt,
            IItemV1NativeAdapter adapter)
        {
            CreateCount++;
            DuringCreate?.Invoke();
            ParentReceipt = parentReceipt;
            Adapter = adapter;
            RoomFlowDispatchReceipt actual = CopyReceipt
                ? new RoomFlowDispatchReceipt(parentReceipt.FlowKind,
                    parentReceipt.SessionNonce, parentReceipt.DecisionId,
                    parentReceipt.ActionId)
                : parentReceipt;
            Broker = new FakeChildBroker(actual) { ThrowOnDispose = ThrowOnDispose };
            return Broker;
        }
    }

    private sealed class FakeChildBroker : IEventItemChildBroker
    {
        private EventItemChildStatus _status;

        internal FakeChildBroker(RoomFlowDispatchReceipt receipt)
        {
            ParentReceipt = receipt;
            _status = new EventItemChildActive(receipt);
        }

        public RoomFlowDispatchReceipt ParentReceipt { get; }
        public EventItemChildStatus Status => _status;
        internal bool Disposed { get; private set; }
        internal int DisposeCount { get; private set; }
        internal bool ThrowOnDispose { get; set; }

        internal void SetStatus(EventItemChildStatus status) => _status = status;

        public byte[] Handle(string? method, string? route, string? decisionId, string? actionId) =>
            new byte[] { 1, 2, 3 };

        public void Dispose()
        {
            DisposeCount++;
            Disposed = true;
            if (ThrowOnDispose) throw new InvalidOperationException("dispose-canary");
        }
    }

    private sealed class FakeItemAdapter : IItemV1NativeAdapter
    {
        public ItemV1SurfaceCapture CaptureSurface() => ItemV1SurfaceCapture.Missing();
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending) =>
            throw new InvalidOperationException("No pending item action.");
    }
}
