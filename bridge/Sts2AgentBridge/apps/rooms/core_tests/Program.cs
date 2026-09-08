using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Tests;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int _checks;

    private static int Main()
    {
        try
        {
            Check(PurchaseCloseLeave);
            Check(ZeroPurchaseCloseLeave);
            Check(PurchaseWaitingAndContradictions);
            Check(StaleAndMalformedSurfaces);
            Check(LimitsAndActionGrammar);
            Check(PendingLimitFinalRead);
            Check(DispatchFailureAndNoRetry);
            Check(ReentrantCaptureGuards);
            Check(ReentrantDispatchGuards);
            Check(OwnerThreadGate);
            Check(CleanupFailures);
            Check(OutputShapeAndImmutability);
            Check(CanonicalDigest);
            Check(MapTravelPermissionRepair);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"shop_map_permission_v1_core\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"shop_map_permission_v1_core\",\"check_count\":0}");
            return 1;
        }
    }

    private static void PurchaseCloseLeave()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Equal("ready", ready.Status); Equal("inventory_browse", ready.Phase);
        Sequence(new[] { "buy:card:7", "inventory:close" }, ready.LegalActions);
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
        Equal("accepted", receipt.Outcome); Equal(1, f.Dispatch.InvokeCount);
        Equal("purchase_waiting", Obs(session.Read()).Phase);
        f.CompletePurchase();
        ShopV1Observation afterPurchase = Obs(session.Read());
        Equal("ready", afterPurchase.Status); Equal(1, afterPurchase.PriorResults.Count);
        Equal("purchase_card", afterPurchase.PriorResults[0].Kind);
        Sequence(new[] { "inventory:close" }, afterPurchase.LegalActions);
        RoomFlowDispatchReceipt closeReceipt = Receipt(session.Apply(
            afterPurchase.DecisionId, "inventory:close"));
        Equal("accepted", closeReceipt.Outcome); Equal(1, f.BackCount);
        ShopV1Observation leaveReady = Obs(session.Read());
        Equal("room_ready_to_leave", leaveReady.Phase);
        Equal("inventory_close", leaveReady.PriorResults[0].Kind);
        Sequence(new[] { "leave" }, leaveReady.LegalActions);
        Receipt(session.Apply(leaveReady.DecisionId, "leave"));
        Equal(1, f.ProceedCount);
        ShopV1Observation complete = Obs(session.Read());
        Equal("complete", complete.Status); Equal("complete", complete.Phase);
        Equal("leave", complete.PriorResults[0].Kind);
        Empty(complete.LegalActions); Empty(complete.Offers);
        int reads = f.Adapter.SurfaceCalls;
        f.MapOpen = false; f.MapTravelEnabled = false;
        Equal("complete", Obs(session.Read()).Status);
        Equal(reads, f.Adapter.SurfaceCalls);
        Equal("rejected", Failure(session.Apply(leaveReady.DecisionId, "leave")).Outcome);
        session.Dispose();
        Equal("unsupported", Obs(session.Read()).Status);
    }

    private static void ZeroPurchaseCloseLeave()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Receipt(session.Apply(ready.DecisionId, "inventory:close"));
        ShopV1Observation leave = Obs(session.Read());
        Equal(0, f.Dispatch.InvokeCount); Equal("inventory_close", leave.PriorResults[0].Kind);
        Receipt(session.Apply(leave.DecisionId, "leave"));
        Equal("complete", Obs(session.Read()).Status);
    }

    private static void PurchaseWaitingAndContradictions()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
        f.Gold -= f.Price;
        Equal("waiting", Obs(session.Read()).Status);
        f.Dispatch.CompletionValue = ShopV1Completion.Succeeded;
        f.Deck.Add(new ShopV1DeckCardBinding(f.Card, f.CardKey));
        f.Stocked = false; f.TargetModel = null;
        Equal("ready", Obs(session.Read()).Status);

        var insertionFirst = new Fixture();
        using var insertionSession = new ShopV1Session(Nonce, insertionFirst.Adapter);
        ShopV1Observation insertionReady = Obs(insertionSession.Read());
        Receipt(insertionSession.Apply(insertionReady.DecisionId, "buy:card:7"));
        insertionFirst.Deck.Add(new ShopV1DeckCardBinding(
            insertionFirst.Card, insertionFirst.CardKey));
        Equal("waiting", Obs(insertionSession.Read()).Status);
        insertionFirst.Gold -= insertionFirst.Price;
        insertionFirst.Stocked = false; insertionFirst.TargetModel = null;
        Equal("waiting", Obs(insertionSession.Read()).Status);
        insertionFirst.Dispatch.CompletionValue = ShopV1Completion.Succeeded;
        Equal("ready", Obs(insertionSession.Read()).Status);

        var wrong = new Fixture();
        using var wrongSession = new ShopV1Session(Nonce, wrong.Adapter);
        ShopV1Observation wrongReady = Obs(wrongSession.Read());
        Receipt(wrongSession.Apply(wrongReady.DecisionId, "buy:card:7"));
        wrong.Dispatch.CompletionValue = ShopV1Completion.Succeeded;
        wrong.Gold -= wrong.Price;
        wrong.Deck.Add(new ShopV1DeckCardBinding(new object(), wrong.CardKey));
        wrong.Stocked = false; wrong.TargetModel = null;
        Equal("unsupported", Obs(wrongSession.Read()).Status);

        var restock = new Fixture();
        using var restockSession = new ShopV1Session(Nonce, restock.Adapter);
        ShopV1Observation restockReady = Obs(restockSession.Read());
        Receipt(restockSession.Apply(restockReady.DecisionId, "buy:card:7"));
        restock.Dispatch.CompletionValue = ShopV1Completion.Succeeded;
        restock.Gold -= restock.Price;
        restock.Deck.Add(new ShopV1DeckCardBinding(restock.Card, restock.CardKey));
        Equal("unsupported", Obs(restockSession.Read()).Status);
    }

    private static void StaleAndMalformedSurfaces()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        f.Gold++;
        Equal("unsupported", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
        Equal(0, f.Dispatch.InvokeCount);

        foreach (ShopV1SurfaceCapture malformed in new[]
        {
            SurfaceWithOffers(Enumerable.Range(0, 33).Select(i => NativeOffer(i)).ToArray()),
            SurfaceWithDeck(Enumerable.Range(0, 513).Select(i =>
                new ShopV1DeckCardBinding(new object(), "C" + i)).ToArray()),
            SurfaceWithOffers(new[] { NativeOffer(1), NativeOffer(1) }),
            SurfaceWithOffers(new ShopV1NativeOffer[] { null! }),
            SurfaceWithDeck(new ShopV1DeckCardBinding[] { null! }),
        })
        {
            var adapter = new FakeAdapter { SurfaceFactory = () => malformed };
            using var bad = new ShopV1Session(Nonce, adapter);
            Equal("unsupported", Obs(bad.Read()).Status);
        }

        var nullPending = new Fixture();
        nullPending.Adapter.PendingFactory = _ => null!;
        using var pendingSession = new ShopV1Session(Nonce, nullPending.Adapter);
        ShopV1Observation pendingReady = Obs(pendingSession.Read());
        Receipt(pendingSession.Apply(pendingReady.DecisionId, "buy:card:7"));
        Equal("unsupported", Obs(pendingSession.Read()).Status);

        var blocked = new Fixture { ForegroundBlocked = true };
        using var blockedSession = new ShopV1Session(Nonce, blocked.Adapter);
        Equal("unsupported", Obs(blockedSession.Read()).Status);
        var traveling = new Fixture { MapTraveling = true };
        using var travelingSession = new ShopV1Session(Nonce, traveling.Adapter);
        Equal("unsupported", Obs(travelingSession.Read()).Status);
    }

    private static void LimitsAndActionGrammar()
    {
        var f = new Fixture();
        f.CardKey = new string('A', 128);
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Equal(2, ready.LegalActions.Count);
        Equal("rejected", Failure(session.Apply(ready.DecisionId, "buy:card:07")).Outcome);
        Equal("rejected", Failure(session.Apply(ready.DecisionId, "buy:card:32")).Outcome);
        Equal("rejected", Failure(session.Apply(ready.DecisionId, "BUY:card:7")).Outcome);
        Equal(1, f.Adapter.SurfaceCalls);

        var badKey = new Fixture { CardKey = new string('A', 129) };
        using var bad = new ShopV1Session(Nonce, badKey.Adapter);
        Equal("unsupported", Obs(bad.Read()).Status);

        var mixed = new Fixture();
        mixed.ExtraOffers.Add(NativeOffer(1, ShopV1OfferKind.Relic, enabled: true));
        mixed.ExtraOffers.Add(NativeOffer(3, ShopV1OfferKind.Potion, enabled: true));
        mixed.CardSlot = 31;
        using var mixedSession = new ShopV1Session(Nonce, mixed.Adapter);
        ShopV1Observation mixedReady = Obs(mixedSession.Read());
        Equal(3, mixedReady.Offers.Count);
        Sequence(new[] { "buy:card:31", "inventory:close" }, mixedReady.LegalActions);
    }

    private static void PendingLimitFinalRead()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
        for (int i = 1; i < ShopV1Constants.MaximumPendingReads; i++)
            Equal("waiting", Obs(session.Read()).Status);
        f.CompletePurchase();
        Equal("ready", Obs(session.Read()).Status);

        var timeout = new Fixture();
        using var timed = new ShopV1Session(Nonce, timeout.Adapter);
        ShopV1Observation timedReady = Obs(timed.Read());
        Receipt(timed.Apply(timedReady.DecisionId, "buy:card:7"));
        for (int i = 1; i < ShopV1Constants.MaximumPendingReads; i++) Obs(timed.Read());
        Equal("unsupported", Obs(timed.Read()).Status);
        Equal(1, timeout.Dispatch.InvokeCount);
    }

    private static void DispatchFailureAndNoRetry()
    {
        var f = new Fixture();
        f.Dispatch.InvokeAction = () => throw new InvalidOperationException("CANARY");
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Equal("uncertain", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
        Equal(1, f.Dispatch.InvokeCount); Equal(1, f.Dispatch.DisposeCount);
        Equal("unsupported", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
        Equal(1, f.Dispatch.InvokeCount);
    }

    private static void ReentrantCaptureGuards()
    {
        var f = new Fixture();
        ShopV1Session? session = null;
        int callback = 0;
        f.Adapter.SurfaceFactory = () =>
        {
            if (callback++ == 0) Obs(session!.Read());
            return f.Surface();
        };
        using (session = new ShopV1Session(Nonce, f.Adapter))
        {
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(1, f.Adapter.SurfaceCalls);
        }

        var apply = new Fixture();
        ShopV1Session? applySession = null;
        using (applySession = new ShopV1Session(Nonce, apply.Adapter))
        {
            ShopV1Observation ready = Obs(applySession.Read());
            apply.Adapter.SurfaceFactory = () =>
            {
                Equal("rejected", Failure(applySession.Apply(ready.DecisionId, "buy:card:7")).Outcome);
                return apply.Surface();
            };
            Equal("unsupported", Failure(applySession.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            Equal(0, apply.Dispatch.InvokeCount);
        }

        var disposed = new Fixture();
        ShopV1Session? disposedSession = null;
        using (disposedSession = new ShopV1Session(Nonce, disposed.Adapter))
        {
            ShopV1Observation ready = Obs(disposedSession.Read());
            disposed.Adapter.SurfaceFactory = () =>
            {
                disposedSession.Dispose();
                return disposed.Surface();
            };
            Equal("unsupported", Failure(disposedSession.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            Equal(0, disposed.Dispatch.InvokeCount);
        }
    }

    private static void ReentrantDispatchGuards()
    {
        var f = new Fixture();
        ShopV1Session? session = null;
        using (session = new ShopV1Session(Nonce, f.Adapter))
        {
            ShopV1Observation ready = Obs(session.Read());
            f.Dispatch.InvokeAction = () =>
            {
                Equal("waiting", Obs(session.Read()).Status);
                Equal("rejected", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            };
            Equal("uncertain", Failure(session.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            Equal(1, f.Dispatch.InvokeCount);
        }

        var disposed = new Fixture();
        ShopV1Session? disposedSession = null;
        using (disposedSession = new ShopV1Session(Nonce, disposed.Adapter))
        {
            ShopV1Observation ready = Obs(disposedSession.Read());
            disposed.Dispatch.InvokeAction = disposedSession.Dispose;
            Equal("uncertain", Failure(disposedSession.Apply(ready.DecisionId, "buy:card:7")).Outcome);
            Equal(1, disposed.Dispatch.InvokeCount); Equal(1, disposed.Dispatch.DisposeCount);
        }
    }

    private static void OwnerThreadGate()
    {
        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        IRoomFlowReadValue? result = null;
        var thread = new Thread(() => result = session.Read());
        thread.Start(); thread.Join();
        Equal("unsupported", Obs(result!).Status);
        Equal(0, f.Adapter.SurfaceCalls);
        Equal("unsupported", Obs(session.Read()).Status);
    }

    private static void CleanupFailures()
    {
        var f = new Fixture();
        var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
        f.CompletePurchase();
        f.Dispatch.ThrowOnDispose = true;
        Equal("unsupported", Obs(session.Read()).Status);
        Throws<InvalidOperationException>(session.Dispose);

        var pending = new Fixture();
        var pendingSession = new ShopV1Session(Nonce, pending.Adapter);
        ShopV1Observation pendingReady = Obs(pendingSession.Read());
        Receipt(pendingSession.Apply(pendingReady.DecisionId, "buy:card:7"));
        pendingSession.Dispose();
        Equal(1, pending.Dispatch.DisposeCount);
        Equal("unsupported", Obs(pendingSession.Read()).Status);

        var reentrant = new Fixture();
        var reentrantSession = new ShopV1Session(Nonce, reentrant.Adapter);
        ShopV1Observation reentrantReady = Obs(reentrantSession.Read());
        Receipt(reentrantSession.Apply(reentrantReady.DecisionId, "buy:card:7"));
        reentrant.CompletePurchase();
        reentrant.Dispatch.DisposeAction = () =>
        {
            Equal("waiting", Obs(reentrantSession.Read()).Status);
            Equal("rejected", Failure(reentrantSession.Apply(
                reentrantReady.DecisionId, "buy:card:7")).Outcome);
            reentrantSession.Dispose();
        };
        Equal("unsupported", Obs(reentrantSession.Read()).Status);
        Equal(1, reentrant.Dispatch.DisposeCount);
        Throws<InvalidOperationException>(reentrantSession.Dispose);
    }

    private static void OutputShapeAndImmutability()
    {
        ExactProperties(typeof(ShopV1Player), "DeckCount", "Gold");
        ExactProperties(typeof(ShopV1Offer), "Affordable", "DisplayedPrice", "Enabled", "Key", "Kind", "Slot", "Supported");
        ExactProperties(typeof(ShopV1ReconciledAction), "ActionId", "DecisionId", "FlowKind", "Kind", "ParentOrdinal", "Result", "SessionNonce");
        ExactProperties(typeof(ShopV1Observation), "DecisionId", "FlowKind", "LegalActions", "Offers", "ParentOrdinal", "Phase", "Player", "PriorResults", "SessionNonce", "Status", "Version");
        ExactProperties(typeof(RoomFlowDispatchReceipt), "ActionId", "DecisionId", "FlowKind", "Outcome", "ParentOrdinal", "SessionNonce");
        ExactProperties(typeof(RoomFlowApplyFailure), "FlowKind", "Outcome", "ParentOrdinal", "SessionNonce");

        var f = new Fixture();
        using var session = new ShopV1Session(Nonce, f.Adapter);
        ShopV1Observation ready = Obs(session.Read());
        Throws<NotSupportedException>(() => ((IList<string>)ready.LegalActions).Add("leave"));
        Throws<NotSupportedException>(() => ((IList<ShopV1Offer>)ready.Offers).Clear());
        Equal("ready", ready.Status); Equal(2, ready.LegalActions.Count);
    }

    private static void CanonicalDigest()
    {
        var f = new Fixture();
        using var a = new ShopV1Session(Nonce, f.Adapter);
        string first = Obs(a.Read()).DecisionId;
        using var b = new ShopV1Session(Nonce, f.Adapter);
        Equal(first, Obs(b.Read()).DecisionId);
        f.Gold++;
        using var c = new ShopV1Session(Nonce, f.Adapter);
        NotEqual(first, Obs(c.Read()).DecisionId);
    }

    private static void MapTravelPermissionRepair()
    {
        var full = new Fixture { MapTravelEnabled = true };
        using (var session = new ShopV1Session(Nonce, full.Adapter))
        {
            ShopV1Observation ready = Obs(session.Read());
            Equal("ready", ready.Status);
            Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
            Equal(1, full.Dispatch.InvokeCount);
            full.CompletePurchase();
            ShopV1Observation purchased = Obs(session.Read());
            Equal("ready", purchased.Status);
            Equal("purchase_card", purchased.PriorResults[0].Kind);
            Receipt(session.Apply(purchased.DecisionId, "inventory:close"));
            Equal(1, full.BackCount);
            ShopV1Observation leave = Obs(session.Read());
            Equal("room_ready_to_leave", leave.Phase);
            Equal(true, full.MapTravelEnabled);
            Receipt(session.Apply(leave.DecisionId, "leave"));
            Equal(1, full.ProceedCount);
            Equal("complete", Obs(session.Read()).Status);
        }

        foreach (bool mapOpen in new[] { true, false })
        {
            var invalid = new Fixture { MapTravelEnabled = true };
            if (mapOpen) invalid.MapOpen = true;
            else invalid.MapTraveling = true;
            using var session = new ShopV1Session(Nonce, invalid.Adapter);
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(0, invalid.Dispatch.InvokeCount);
            Equal(0, invalid.BackCount);
        }

        foreach (bool mapOpen in new[] { true, false })
        {
            var stale = new Fixture { MapTravelEnabled = true };
            using var session = new ShopV1Session(Nonce, stale.Adapter);
            ShopV1Observation ready = Obs(session.Read());
            if (mapOpen) stale.MapOpen = true;
            else stale.MapTraveling = true;
            Equal("unsupported", Failure(session.Apply(
                ready.DecisionId, "inventory:close")).Outcome);
            Equal(0, stale.BackCount);
            Equal(0, stale.Dispatch.InvokeCount);
        }

        foreach (bool mapOpen in new[] { true, false })
        {
            var changed = new Fixture { MapTravelEnabled = true };
            using var session = new ShopV1Session(Nonce, changed.Adapter);
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "buy:card:7"));
            if (mapOpen) changed.MapOpen = true;
            else changed.MapTraveling = true;
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(1, changed.Dispatch.InvokeCount);
        }

        foreach (bool mapOpen in new[] { true, false })
        {
            var changed = new Fixture { MapTravelEnabled = true };
            using var session = new ShopV1Session(Nonce, changed.Adapter);
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "inventory:close"));
            if (mapOpen) changed.MapOpen = true;
            else changed.MapTraveling = true;
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(1, changed.BackCount);
        }

        var intercepted = new Fixture
        {
            MapTravelEnabled = true,
            ProceedOpensMap = false,
        };
        using (var session = new ShopV1Session(Nonce, intercepted.Adapter))
        {
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "inventory:close"));
            ShopV1Observation leave = Obs(session.Read());
            Receipt(session.Apply(leave.DecisionId, "leave"));
            Equal(1, intercepted.ProceedCount);
            Equal("unsupported", Obs(session.Read()).Status);
            int reads = intercepted.Adapter.PendingCalls;
            intercepted.MapOpen = true;
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(reads, intercepted.Adapter.PendingCalls);
            Equal("unsupported", Failure(session.Apply(leave.DecisionId, "leave")).Outcome);
            Equal(1, intercepted.ProceedCount);
        }

        var disabledWait = new Fixture
        {
            MapTravelEnabled = true,
            ProceedOpensMap = false,
        };
        using (var session = new ShopV1Session(Nonce, disabledWait.Adapter))
        {
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "inventory:close"));
            ShopV1Observation leave = Obs(session.Read());
            disabledWait.MapTravelEnabled = false;
            Receipt(session.Apply(leave.DecisionId, "leave"));
            Equal("waiting", Obs(session.Read()).Status);
        }

        foreach (bool traveling in new[] { false, true })
        {
            var invalid = new Fixture
            {
                MapTravelEnabled = true,
                ProceedOpensMap = false,
            };
            using var session = new ShopV1Session(Nonce, invalid.Adapter);
            ShopV1Observation ready = Obs(session.Read());
            Receipt(session.Apply(ready.DecisionId, "inventory:close"));
            ShopV1Observation leave = Obs(session.Read());
            Receipt(session.Apply(leave.DecisionId, "leave"));
            invalid.MapOpen = true;
            invalid.MapTravelEnabled = traveling;
            invalid.MapTraveling = traveling;
            Equal("unsupported", Obs(session.Read()).Status);
            Equal(1, invalid.ProceedCount);
        }
    }

    private static ShopV1SurfaceCapture SurfaceWithOffers(IReadOnlyList<ShopV1NativeOffer> offers) =>
        new Fixture().Surface(offers: offers);

    private static ShopV1SurfaceCapture SurfaceWithDeck(IReadOnlyList<ShopV1DeckCardBinding> deck) =>
        new Fixture().Surface(deck: deck);

    private static ShopV1NativeOffer NativeOffer(
        int slot,
        ShopV1OfferKind kind = ShopV1OfferKind.Relic,
        bool enabled = false)
    {
        object? model = kind == ShopV1OfferKind.Card ? new object() : null;
        var dispatch = kind == ShopV1OfferKind.Card ? new FakeDispatch() : null;
        return new ShopV1NativeOffer(slot, kind, "KEY_" + slot, 10, true, true,
            enabled, new object(), new object(), model, new object(), new object(), dispatch);
    }

    private static ShopV1Observation Obs(IRoomFlowReadValue value) =>
        value as ShopV1Observation ?? throw new InvalidOperationException();

    private static RoomFlowDispatchReceipt Receipt(IRoomFlowApplyValue value) =>
        value as RoomFlowDispatchReceipt ?? throw new InvalidOperationException();

    private static RoomFlowApplyFailure Failure(IRoomFlowApplyValue value) =>
        value as RoomFlowApplyFailure ?? throw new InvalidOperationException();

    private static void ExactProperties(Type type, params string[] expected)
    {
        string[] actual = type.GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Select(property => property.Name).OrderBy(name => name, StringComparer.Ordinal).ToArray();
        Array.Sort(expected, StringComparer.Ordinal);
        Sequence(expected, actual);
    }

    private static void Empty<T>(IReadOnlyList<T> values) => Equal(0, values.Count);

    private static void Check(Action check)
    {
        check();
        _checks++;
    }

    private static void Equal<T>(T expected, T actual)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException();
    }

    private static void NotEqual<T>(T left, T right)
    {
        if (EqualityComparer<T>.Default.Equals(left, right))
            throw new InvalidOperationException();
    }

    private static void Sequence<T>(IReadOnlyList<T> expected, IReadOnlyList<T> actual)
    {
        Equal(expected.Count, actual.Count);
        for (int i = 0; i < expected.Count; i++) Equal(expected[i], actual[i]);
    }

    private static void Throws<T>(Action action) where T : Exception
    {
        try { action(); }
        catch (T) { return; }
        throw new InvalidOperationException();
    }

    private sealed class Fixture
    {
        internal readonly object Run = new();
        internal readonly object Room = new();
        internal readonly object InventoryNode = new();
        internal readonly object InventoryModel = new();
        internal readonly object Player = new();
        internal readonly object Map = new();
        internal readonly object Back = new();
        internal readonly object Merchant = new();
        internal readonly object Proceed = new();
        internal readonly object Slot = new();
        internal readonly object Entry = new();
        internal readonly object Hitbox = new();
        internal readonly object Label = new();
        internal readonly object Card = new();
        internal readonly FakeAdapter Adapter;
        internal readonly FakeDispatch Dispatch = new();
        internal readonly List<ShopV1DeckCardBinding> Deck = new();
        internal readonly List<ShopV1NativeOffer> ExtraOffers = new();
        internal int Gold = 100;
        internal int Price = 45;
        internal int CardSlot = 7;
        internal string CardKey = "STRIKE_RED";
        internal bool InventoryOpen = true;
        internal bool ForegroundBlocked;
        internal bool MapOpen;
        internal bool MapTravelEnabled;
        internal bool MapTraveling;
        internal bool RoomVisible = true;
        internal bool ProceedOpensMap = true;
        internal bool Stocked = true;
        internal object? TargetModel;
        internal int BackCount;
        internal int ProceedCount;

        internal Fixture()
        {
            TargetModel = Card;
            Deck.Add(new ShopV1DeckCardBinding(new object(), "BASH"));
            Adapter = new FakeAdapter
            {
                SurfaceFactory = () => Surface(),
                PendingFactory = Pending,
            };
        }

        internal ShopV1SurfaceCapture Surface(
            IReadOnlyList<ShopV1NativeOffer>? offers = null,
            IReadOnlyList<ShopV1DeckCardBinding>? deck = null)
        {
            var actualOffers = offers ?? Offers();
            return new ShopV1SurfaceCapture(
                ShopV1SurfaceStatus.Available, Run, Room, InventoryNode,
                InventoryModel, Player, Map, RoomVisible, InventoryOpen, InventoryOpen,
                ForegroundBlocked, MapOpen, MapTravelEnabled, MapTraveling,
                Gold, deck ?? Deck, actualOffers,
                new ShopV1NativeControl(Back, true, true, () =>
                {
                    BackCount++; InventoryOpen = false;
                }),
                new ShopV1NativeControl(Merchant, true, true, null),
                new ShopV1NativeControl(Proceed, true, true, () =>
                {
                    ProceedCount++;
                    if (ProceedOpensMap)
                    {
                        MapOpen = true; MapTravelEnabled = true;
                        RoomVisible = false;
                    }
                }));
        }

        internal ShopV1PendingCapture Pending(ShopV1PendingProbe probe) =>
            new(
                ShopV1SurfaceStatus.Available, Run, Room, InventoryNode,
                InventoryModel, Player, Map, RoomVisible, InventoryOpen, InventoryOpen,
                ForegroundBlocked, MapOpen, MapTravelEnabled, MapTraveling,
                Gold, Deck,
                new ShopV1NativeControl(Merchant, true, true, null),
                new ShopV1NativeControl(Proceed, true, true, () => { }),
                probe.Kind == ShopV1ActionKind.PurchaseCard,
                probe.Kind == ShopV1ActionKind.PurchaseCard ? Slot : null,
                probe.Kind == ShopV1ActionKind.PurchaseCard ? Entry : null,
                Stocked, TargetModel, Dispatch.Completion);

        internal IReadOnlyList<ShopV1NativeOffer> Offers()
        {
            if (!InventoryOpen) return Array.Empty<ShopV1NativeOffer>();
            var offers = new List<ShopV1NativeOffer>(ExtraOffers);
            if (Stocked)
            {
                offers.Add(new ShopV1NativeOffer(
                    CardSlot, ShopV1OfferKind.Card, CardKey, Price, true, true,
                    true, Slot, Entry, TargetModel, Hitbox, Label, Dispatch));
            }
            offers.Sort((left, right) => left.Slot.CompareTo(right.Slot));
            return offers;
        }

        internal void CompletePurchase()
        {
            Dispatch.CompletionValue = ShopV1Completion.Succeeded;
            Gold -= Price;
            Deck.Add(new ShopV1DeckCardBinding(Card, CardKey));
            Stocked = false;
            TargetModel = null;
        }
    }

    private sealed class FakeAdapter : IShopV1NativeAdapter
    {
        internal Func<ShopV1SurfaceCapture> SurfaceFactory = ShopV1SurfaceCapture.Missing;
        internal Func<ShopV1PendingProbe, ShopV1PendingCapture> PendingFactory =
            _ => ShopV1PendingCapture.Missing();
        internal int SurfaceCalls;
        internal int PendingCalls;

        public ShopV1SurfaceCapture CaptureSurface()
        {
            SurfaceCalls++;
            return SurfaceFactory();
        }

        public ShopV1PendingCapture CapturePending(ShopV1PendingProbe pending)
        {
            PendingCalls++;
            return PendingFactory(pending);
        }
    }

    private sealed class FakeDispatch : IShopV1NativeDispatch
    {
        internal int InvokeCount;
        internal int DisposeCount;
        internal Action? InvokeAction;
        internal Action? DisposeAction;
        internal bool ThrowOnDispose;
        internal ShopV1Completion CompletionValue = ShopV1Completion.Pending;

        public ShopV1Completion Completion => CompletionValue;

        public void Invoke()
        {
            InvokeCount++;
            InvokeAction?.Invoke();
        }

        public void Dispose()
        {
            DisposeCount++;
            DisposeAction?.Invoke();
            if (ThrowOnDispose) throw new InvalidOperationException("CANARY");
        }
    }
}
