using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Sts2AgentBridge.Successors.ItemV1;

namespace Sts2AgentBridge.Successors.ItemV1.Tests;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private const string OtherNonce = "1123456789abcdef0123456789abcdef";
    private const string Canary = "ITEM_V1_EXCEPTION_CANARY";
    private static int _checks;

    private static int Main()
    {
        Run("canonical_and_immutable", CanonicalAndImmutable);
        Run("relic_async_and_closed_overlay", RelicAsyncAndClosedOverlay);
        Run("potion_async_and_inventory_integrity", PotionAsyncAndInventoryIntegrity);
        Run("full_inventory_and_exact_action_binding", FullInventoryAndExactActionBinding);
        Run("stale_public_and_reference_bindings", StalePublicAndReferenceBindings);
        Run("surface_binding_and_input_rejection", SurfaceBindingAndInputRejection);
        Run("caps_unknown_and_waiting", CapsUnknownAndWaiting);
        Run("reservation_reentrancy_and_throw", ReservationReentrancyAndThrow);
        Run("poll_exhaustion_and_stable_result", PollExhaustionAndStableResult);
        Run("malformed_capture_and_fixed_failures", MalformedCaptureAndFixedFailures);
        Console.WriteLine(
            "{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"item_v1_core\",\"check_count\":" +
            _checks + "}");
        return 0;
    }

    private static void CanonicalAndImmutable()
    {
        var adapter = new FakeAdapter();
        object existing = new();
        var slots = new List<ItemV1PotionSlotBinding>
        {
            new(existing, "Existing_1"),
            new(null, null),
        };
        var offers = new List<ItemV1NativeOffer>
        {
            Offer(7, ItemV1ItemKind.Potion, "Potion_A", enabled: true),
            Offer(2, ItemV1ItemKind.Relic, "Relic_B", enabled: false),
        };
        adapter.Surface = Surface(adapter, offers, slots, 2);
        var session = new ItemV1Session(Nonce, adapter);
        ItemV1Observation ready = Ready(session.Read());
        Check(ready.Version == "item_v1" && ready.SurfaceOrdinal == 1,
            "version and surface");
        Check(ready.Offers.Select(item => item.Index).SequenceEqual(new[] { 2, 7 }),
            "native index order");
        Check(ready.LegalActions.SequenceEqual(new[] { "collect:7" }), "legal action");
        Check(ready.PotionSlots.SequenceEqual(new string?[] { "Existing_1", null }),
            "slot projection");
        Check(ItemV1CanonicalEncoder.IsCanonicalDecisionId(ready.DecisionId), "digest shape");
        Check(PublicPropertyNames(typeof(ItemV1Observation)).SequenceEqual(new[]
        {
            "DecisionId", "LegalActions", "Offers", "PotionSlots", "SessionNonce",
            "Status", "SurfaceOrdinal", "Version",
        }), "observation output exact fields");
        Check(PublicPropertyNames(typeof(ItemV1Offer)).SequenceEqual(new[]
        {
            "Enabled", "Index", "Key", "Kind",
        }), "offer output exact fields");

        string baseline = ready.DecisionId;
        Check(baseline == "043f9b2cb7b40fb84738bb69e2a70018fcc1d139a0db0005da21db5f43f07859",
            "canonical digest fixture");
        Check(baseline == ItemV1CanonicalEncoder.ComputeDecisionId(
            Nonce, ready.Offers, ready.PotionSlots, ready.LegalActions), "digest repeat");
        Check(baseline != ItemV1CanonicalEncoder.ComputeDecisionId(
            OtherNonce, ready.Offers, ready.PotionSlots, ready.LegalActions), "nonce sensitivity");
        Check(baseline != ItemV1CanonicalEncoder.ComputeDecisionId(
            Nonce,
            new[] { new ItemV1Offer(2, "relic", "Relic_B", false),
                    new ItemV1Offer(8, "potion", "Potion_A", true) },
            ready.PotionSlots, ready.LegalActions), "index sensitivity");
        Check(baseline != ItemV1CanonicalEncoder.ComputeDecisionId(
            Nonce,
            new[] { new ItemV1Offer(2, "relic", "Relic_C", false),
                    new ItemV1Offer(7, "potion", "Potion_A", true) },
            ready.PotionSlots, ready.LegalActions), "key sensitivity");
        Check(baseline != ItemV1CanonicalEncoder.ComputeDecisionId(
            Nonce,
            new[] { new ItemV1Offer(2, "relic", "Relic_B", true),
                    new ItemV1Offer(7, "potion", "Potion_A", true) },
            ready.PotionSlots, ready.LegalActions), "enabled sensitivity");
        Check(baseline != ItemV1CanonicalEncoder.ComputeDecisionId(
            Nonce, ready.Offers, new string?[] { null, "Existing_1" }, ready.LegalActions),
            "slot order sensitivity");
        Check(baseline != ItemV1CanonicalEncoder.ComputeDecisionId(
            Nonce, ready.Offers, new string?[] { "Existing_1", null, null },
            ready.LegalActions), "capacity sensitivity");
        Check(baseline != ItemV1CanonicalEncoder.ComputeDecisionId(
            Nonce, ready.Offers, ready.PotionSlots, new[] { "collect:8" }),
            "legal sensitivity");

        offers.Clear();
        slots[0] = new ItemV1PotionSlotBinding(new object(), "Changed");
        Check(ready.Offers.Count == 2 && ready.PotionSlots[0] == "Existing_1",
            "capture and observation copies");
        ExpectThrows<NotSupportedException>(
            () => ((IList<ItemV1Offer>)ready.Offers).Add(new ItemV1Offer(9, "relic", "X", true)),
            "offer collection immutable");
        ExpectThrows<NotSupportedException>(
            () => ((IList<string?>)ready.PotionSlots)[0] = "mutated",
            "slot collection immutable");
        ExpectThrows<NotSupportedException>(
            () => ((IList<string>)ready.LegalActions)[0] = "collect:2",
            "legal collection immutable");
        ExpectThrows<ArgumentException>(() => new ItemV1Session("ABC", adapter),
            "nonce rejected");
    }

    private static void RelicAsyncAndClosedOverlay()
    {
        var adapter = new FakeAdapter();
        object model = new();
        ItemV1NativeOffer offer = Offer(5, ItemV1ItemKind.Relic, "Relic_1", model: model,
            dispatch: () => adapter.Surface = ItemV1SurfaceCapture.Missing());
        adapter.Surface = Surface(adapter, new[] { offer }, EmptySlots(2), 2);
        adapter.PendingFactory = probe => Pending(adapter, probe, selected: false,
            claimed: model, claimedKey: "Relic_1", slots: EmptySlots(2), capacity: 2);
        var session = new ItemV1Session(Nonce, adapter);
        ItemV1Observation ready = Ready(session.Read());
        ItemV1DispatchReceipt receipt = Accepted(session.Apply(ready.DecisionId, "collect:5"));
        Check(receipt.DecisionId == ready.DecisionId && receipt.ActionId == "collect:5",
            "correlated receipt");
        Check(PublicPropertyNames(typeof(ItemV1DispatchReceipt)).SequenceEqual(new[]
        {
            "ActionId", "DecisionId", "Outcome", "SessionNonce", "SurfaceOrdinal", "Version",
        }), "receipt output exact fields");
        Check(PublicPropertyNames(typeof(ItemV1ApplyFailure)).SequenceEqual(new[]
        {
            "Outcome", "SessionNonce", "SurfaceOrdinal", "Version",
        }), "apply failure output exact fields");
        Check(Status(session.Read()) == "waiting", "claim before selected waits");
        adapter.PendingFactory = probe => Pending(adapter, probe, selected: true,
            claimed: model, claimedKey: "Relic_1", slots: EmptySlots(2), capacity: 2);
        ItemV1ResolvedResult result = Resolved(session.Read());
        Check(result.DecisionId == ready.DecisionId && result.ActionId == "collect:5" &&
              result.OfferIndex == 5 && result.Kind == "relic" &&
              result.Key == "Relic_1" && result.Result == "collected", "relic result");
        Check(PublicPropertyNames(typeof(ItemV1ResolvedResult)).SequenceEqual(new[]
        {
            "ActionId", "DecisionId", "Key", "Kind", "OfferIndex", "Result",
            "SessionNonce", "SurfaceOrdinal", "Version",
        }), "resolved output exact fields");

        var mismatch = new FakeAdapter();
        object offered = new();
        object sameKeyDifferent = new();
        mismatch.Surface = Surface(mismatch,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Same_Key", model: offered) },
            EmptySlots(1), 1);
        mismatch.PendingFactory = probe => Pending(mismatch, probe, true,
            sameKeyDifferent, "Same_Key", EmptySlots(1), 1);
        var mismatchSession = new ItemV1Session(Nonce, mismatch);
        ItemV1Observation mismatchReady = Ready(mismatchSession.Read());
        Accepted(mismatchSession.Apply(mismatchReady.DecisionId, "collect:1"));
        Check(Status(mismatchSession.Read()) == "unsupported", "same-key object rejected");
    }

    private static void PotionAsyncAndInventoryIntegrity()
    {
        object existing = new();
        object offered = new();
        var before = new[]
        {
            new ItemV1PotionSlotBinding(existing, "Existing"),
            new ItemV1PotionSlotBinding(null, null),
            new ItemV1PotionSlotBinding(null, null),
        };
        var inserted = new[]
        {
            new ItemV1PotionSlotBinding(existing, "Existing"),
            new ItemV1PotionSlotBinding(offered, "Potion_New"),
            new ItemV1PotionSlotBinding(null, null),
        };
        var adapter = new FakeAdapter();
        adapter.Surface = Surface(adapter,
            new[] { Offer(3, ItemV1ItemKind.Potion, "Potion_New", model: offered) },
            before, 3);
        adapter.PendingFactory = probe => Pending(adapter, probe, false, offered,
            "Potion_New", inserted, 3);
        var session = new ItemV1Session(Nonce, adapter);
        ItemV1Observation ready = Ready(session.Read());
        Accepted(session.Apply(ready.DecisionId, "collect:3"));
        Check(Status(session.Read()) == "waiting", "anticipated insertion waits for selected");
        adapter.PendingFactory = probe => Pending(adapter, probe, true, offered,
            "Potion_New", inserted, 3);
        ItemV1ResolvedResult result = Resolved(session.Read());
        Check(result.Kind == "potion" && result.OfferIndex == 3, "potion resolved");

        CheckPotionFailure(before, currentCapacity: 2, new[]
        {
            new ItemV1PotionSlotBinding(existing, "Existing"),
            new ItemV1PotionSlotBinding(offered, "Potion_New"),
        }, offered, offered, "Potion_New", true, "capacity drift");
        CheckPotionFailure(before, 3, new[]
        {
            new ItemV1PotionSlotBinding(new object(), "Existing"),
            new ItemV1PotionSlotBinding(offered, "Potion_New"),
            new ItemV1PotionSlotBinding(null, null),
        }, offered, offered, "Potion_New", false, "same-key existing replacement");
        CheckPotionFailure(before, 3, new[]
        {
            new ItemV1PotionSlotBinding(existing, "Existing"),
            new ItemV1PotionSlotBinding(offered, "Potion_New"),
            new ItemV1PotionSlotBinding(offered, "Potion_New"),
        }, offered, offered, "Potion_New", false, "multiple insertions");
        CheckPotionFailure(before, 3, before, offered, offered, "Potion_New", true,
            "selected without insertion");
        CheckPotionFailure(before, 3, inserted, offered, new object(), "Potion_New", true,
            "claimed different object");
    }

    private static void FullInventoryAndExactActionBinding()
    {
        object held = new();
        var full = new[] { new ItemV1PotionSlotBinding(held, "Held") };
        var potionOnly = new FakeAdapter();
        int potionDispatch = 0;
        potionOnly.Surface = Surface(potionOnly, new[]
        {
            Offer(1, ItemV1ItemKind.Potion, "Potion", dispatch: () => potionDispatch++),
        }, full, 1);
        var potionSession = new ItemV1Session(Nonce, potionOnly);
        Check(Status(potionSession.Read()) == "unsupported" && potionDispatch == 0,
            "full potion-only unsupported");

        var mixed = new FakeAdapter();
        int relicDispatch = 0;
        potionDispatch = 0;
        mixed.Surface = Surface(mixed, new[]
        {
            Offer(1, ItemV1ItemKind.Potion, "Potion", dispatch: () => potionDispatch++),
            Offer(9, ItemV1ItemKind.Relic, "Relic", dispatch: () => relicDispatch++),
        }, full, 1);
        var mixedSession = new ItemV1Session(Nonce, mixed);
        ItemV1Observation mixedReady = Ready(mixedSession.Read());
        Check(mixedReady.LegalActions.SequenceEqual(new[] { "collect:9" }),
            "full mixed advertises relic only");
        Accepted(mixedSession.Apply(mixedReady.DecisionId, "collect:9"));
        Check(relicDispatch == 1 && potionDispatch == 0, "full mixed exact target");

        var disabled = new FakeAdapter();
        int disabledDispatch = 0;
        int laterDispatch = 0;
        disabled.Surface = Surface(disabled, new[]
        {
            Offer(2, ItemV1ItemKind.Relic, "Disabled", enabled: false,
                dispatch: () => disabledDispatch++),
            Offer(6, ItemV1ItemKind.Relic, "Enabled", dispatch: () => laterDispatch++),
        }, EmptySlots(1), 1);
        var disabledSession = new ItemV1Session(Nonce, disabled);
        ItemV1Observation disabledReady = Ready(disabledSession.Read());
        Check(disabledReady.LegalActions.SequenceEqual(new[] { "collect:6" }),
            "disabled first action list");
        Accepted(disabledSession.Apply(disabledReady.DecisionId, "collect:6"));
        Check(disabledDispatch == 0 && laterDispatch == 1, "disabled first exact target");

        var zero = new FakeAdapter();
        zero.Surface = Surface(zero,
            new[] { Offer(0, ItemV1ItemKind.Potion, "Potion") },
            Array.Empty<ItemV1PotionSlotBinding>(), 0);
        Check(Status(new ItemV1Session(Nonce, zero).Read()) == "unsupported",
            "zero-capacity potion unsupported");
    }

    private static void StalePublicAndReferenceBindings()
    {
        foreach (Action<FakeAdapter, ItemV1SurfaceCapture> mutate in new Action<FakeAdapter, ItemV1SurfaceCapture>[]
        {
            (fake, old) => fake.Surface = Surface(fake, old.Offers, old.PotionSlots,
                old.PotionCapacity, screen: new object()),
            (fake, old) => fake.Surface = Surface(fake,
                new[] { Clone(old.Offers[0], button: new object()) }, old.PotionSlots,
                old.PotionCapacity),
            (fake, old) => fake.Surface = Surface(fake,
                new[] { Clone(old.Offers[0], reward: new object()) }, old.PotionSlots,
                old.PotionCapacity),
            (fake, old) => fake.Surface = Surface(fake,
                new[] { Clone(old.Offers[0], model: new object()) }, old.PotionSlots,
                old.PotionCapacity),
            (fake, old) => fake.Surface = Surface(fake,
                new[] { Clone(old.Offers[0], key: "Relic_Changed") }, old.PotionSlots,
                old.PotionCapacity),
            (fake, old) => fake.Surface = Surface(fake,
                new[] { Clone(old.Offers[0], enabled: false) }, old.PotionSlots,
                old.PotionCapacity),
            (fake, old) => fake.Surface = Surface(fake, old.Offers,
                new[] { new ItemV1PotionSlotBinding(new object(), "Filled") }, 1),
        })
        {
            var adapter = new FakeAdapter();
            int dispatches = 0;
            adapter.Surface = Surface(adapter,
                new[] { Offer(4, ItemV1ItemKind.Relic, "Relic", dispatch: () => dispatches++) },
                EmptySlots(1), 1);
            ItemV1SurfaceCapture baseline = adapter.Surface;
            var session = new ItemV1Session(Nonce, adapter);
            ItemV1Observation ready = Ready(session.Read());
            mutate(adapter, baseline);
            Check(ApplyFailure(session.Apply(ready.DecisionId, "collect:4")).Outcome ==
                  "unsupported" && dispatches == 0 && session.ReservedDispatchCount == 0,
                "stale binding performs zero dispatch");
        }
    }

    private static void SurfaceBindingAndInputRejection()
    {
        var adapter = new FakeAdapter();
        adapter.Surface = ItemV1SurfaceCapture.Missing();
        var session = new ItemV1Session(Nonce, adapter);
        Check(Status(session.Read()) == "waiting", "missing waits");
        adapter.Surface = Surface(adapter,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(1), 1);
        Ready(session.Read());
        adapter.Surface = ItemV1SurfaceCapture.Missing();
        Check(Status(session.Read()) == "waiting", "bound missing waits");
        adapter.Surface = Surface(adapter,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(1), 1,
            screen: new object());
        Check(Status(session.Read()) == "unsupported", "different screen latches");
        int calls = adapter.SurfaceCalls;
        Check(Status(session.Read()) == "unsupported" && adapter.SurfaceCalls == calls,
            "latched surface does not reread");

        var invalid = new FakeAdapter();
        invalid.Surface = Surface(invalid,
            new[] { Offer(7, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(1), 1);
        var invalidSession = new ItemV1Session(Nonce, invalid);
        ItemV1Observation ready = Ready(invalidSession.Read());
        Check(ApplyFailure(invalidSession.Apply("bad", "collect:7")).Outcome == "rejected",
            "invalid decision rejected");
        Check(ApplyFailure(invalidSession.Apply(ready.DecisionId, "collect:07")).Outcome ==
              "rejected", "leading zero rejected");
        Check(invalid.Dispatches == 0 && invalidSession.ReservedDispatchCount == 0,
            "invalid requests do not reserve");
    }

    private static void CapsUnknownAndWaiting()
    {
        var empty = new FakeAdapter();
        empty.Surface = Surface(empty, Array.Empty<ItemV1NativeOffer>(), EmptySlots(1), 1);
        Check(Status(new ItemV1Session(Nonce, empty).Read()) == "waiting", "zero offers waits");

        var disabled = new FakeAdapter();
        disabled.Surface = Surface(disabled,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic", enabled: false) },
            EmptySlots(1), 1);
        Check(Status(new ItemV1Session(Nonce, disabled).Read()) == "waiting",
            "all disabled waits");

        var maximum = new FakeAdapter();
        var maxOffers = Enumerable.Range(248, 8)
            .Select(index => Offer(index, ItemV1ItemKind.Relic, "Relic_" + index))
            .ToArray();
        maximum.Surface = Surface(maximum, maxOffers,
            Enumerable.Range(0, 8)
                .Select(index => new ItemV1PotionSlotBinding(new object(), "Potion_" + index))
                .ToArray(), 8);
        ItemV1Observation maxReady = Ready(new ItemV1Session(Nonce, maximum).Read());
        Check(maxReady.Offers.Count == 8 && maxReady.LegalActions.Count == 8 &&
              maxReady.Offers[^1].Index == 255, "maximum bounds accepted");
        var maximumKey = new FakeAdapter();
        maximumKey.Surface = Surface(maximumKey,
            new[] { Offer(0, ItemV1ItemKind.Relic, new string('A', 128)) },
            EmptySlots(1), 1);
        Ready(new ItemV1Session(Nonce, maximumKey).Read());

        var malformedCaptures = new List<ItemV1SurfaceCapture>
        {
            Surface(new FakeAdapter(), Enumerable.Range(0, 9)
                .Select(index => Offer(index, ItemV1ItemKind.Relic, "R_" + index)).ToArray(),
                EmptySlots(1), 1),
            Surface(new FakeAdapter(),
                new[] { Offer(256, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(1), 1),
            Surface(new FakeAdapter(),
                new[] { Offer(-1, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(1), 1),
            Surface(new FakeAdapter(), new[]
            {
                Offer(1, ItemV1ItemKind.Relic, "A"),
                Offer(1, ItemV1ItemKind.Potion, "B"),
            }, EmptySlots(1), 1),
            Surface(new FakeAdapter(),
                new[] { Offer(1, ItemV1ItemKind.Unsupported, "Unknown") }, EmptySlots(1), 1),
            Surface(new FakeAdapter(),
                new[] { Offer(1, ItemV1ItemKind.Relic, "not-valid") }, EmptySlots(1), 1),
            Surface(new FakeAdapter(),
                new[] { Offer(1, ItemV1ItemKind.Relic, new string('A', 129)) },
                EmptySlots(1), 1),
            Surface(new FakeAdapter(),
                new[] { Offer(1, ItemV1ItemKind.Relic, "Relic", populated: false) },
                EmptySlots(1), 1),
            Surface(new FakeAdapter(),
                new[] { Offer(1, ItemV1ItemKind.Relic, "Relic", selected: true) },
                EmptySlots(1), 1),
            Surface(new FakeAdapter(),
                new[] { Offer(1, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(8), 9),
            Surface(new FakeAdapter(),
                new[] { Offer(1, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(1), 2),
            Surface(new FakeAdapter(), new[]
            {
                Offer(1, ItemV1ItemKind.Relic, "Relic"),
                Offer(2, ItemV1ItemKind.Unsupported, "Unknown"),
            }, EmptySlots(1), 1),
        };
        foreach (string binding in new[] { "button", "reward", "model" })
        {
            object shared = new();
            ItemV1NativeOffer first = Offer(1, ItemV1ItemKind.Relic, "First",
                button: binding == "button" ? shared : null,
                reward: binding == "reward" ? shared : null,
                model: binding == "model" ? shared : null);
            ItemV1NativeOffer second = Offer(2, ItemV1ItemKind.Relic, "Second",
                button: binding == "button" ? shared : null,
                reward: binding == "reward" ? shared : null,
                model: binding == "model" ? shared : null);
            malformedCaptures.Add(Surface(new FakeAdapter(), new[] { first, second },
                EmptySlots(1), 1));
        }
        foreach (ItemV1SurfaceCapture malformed in malformedCaptures)
        {
            var adapter = new FakeAdapter { Surface = malformed };
            Check(Status(new ItemV1Session(Nonce, adapter).Read()) == "unsupported",
                "malformed bound rejected");
        }
    }

    private static void ReservationReentrancyAndThrow()
    {
        var adapter = new FakeAdapter();
        ItemV1Session? session = null;
        IItemV1ReadValue? reentrantRead = null;
        IItemV1ApplyValue? reentrantApply = null;
        Action dispatch = () =>
        {
            adapter.Dispatches++;
            reentrantRead = session!.Read();
            reentrantApply = session.Apply(Enumerable.Repeat('0', 64).Aggregate("",
                (text, value) => text + value), "collect:1");
        };
        object model = new();
        adapter.Surface = Surface(adapter,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic", model: model, dispatch: dispatch) },
            EmptySlots(1), 1);
        adapter.PendingFactory = probe => Pending(adapter, probe, false, null, null,
            EmptySlots(1), 1);
        session = new ItemV1Session(Nonce, adapter);
        ItemV1Observation ready = Ready(session.Read());
        Accepted(session.Apply(ready.DecisionId, "collect:1"));
        Check(Status(reentrantRead!) == "waiting" &&
              ApplyFailure(reentrantApply!).Outcome == "rejected" &&
              adapter.Dispatches == 1 && session.ReservedDispatchCount == 1,
            "reservation precedes reentrant calls");
        Check(ApplyFailure(session.Apply(ready.DecisionId, "collect:1")).Outcome == "rejected" &&
              adapter.Dispatches == 1, "duplicate dispatch rejected");

        var throwing = new FakeAdapter();
        int throwingDispatches = 0;
        throwing.Surface = Surface(throwing,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic", dispatch: () =>
            {
                throwingDispatches++;
                throw new InvalidOperationException(Canary);
            }) }, EmptySlots(1), 1);
        var throwingSession = new ItemV1Session(Nonce, throwing);
        ItemV1Observation throwReady = Ready(throwingSession.Read());
        IItemV1ApplyValue uncertain = throwingSession.Apply(
            throwReady.DecisionId, "collect:1");
        Check(ApplyFailure(uncertain).Outcome == "uncertain" &&
              !ApplyFailure(uncertain).Outcome.Contains(Canary, StringComparison.Ordinal) &&
              throwingSession.ReservedDispatchCount == 1, "throw fixed uncertain");
        Check(Status(throwingSession.Read()) == "unsupported" && throwing.PendingCalls == 0,
            "uncertain never resolves");
        Check(ApplyFailure(throwingSession.Apply(throwReady.DecisionId, "collect:1")).Outcome ==
              "rejected" && throwingDispatches == 1, "throw cannot retry");
    }

    private static void PollExhaustionAndStableResult()
    {
        var exhausting = new FakeAdapter();
        exhausting.Surface = Surface(exhausting,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(1), 1);
        exhausting.PendingFactory = probe => Pending(exhausting, probe, false, null, null,
            EmptySlots(1), 1);
        var session = new ItemV1Session(Nonce, exhausting);
        ItemV1Observation ready = Ready(session.Read());
        Accepted(session.Apply(ready.DecisionId, "collect:1"));
        for (int read = 1; read < 256; read++)
        {
            Check(Status(session.Read()) == "waiting", "pre-limit wait " + read);
        }
        Check(Status(session.Read()) == "unsupported" && exhausting.PendingCalls == 256,
            "read 256 expires");
        Check(Status(session.Read()) == "unsupported" && exhausting.PendingCalls == 256,
            "expired latch no reread");

        var exact = new FakeAdapter();
        object model = new();
        exact.Surface = Surface(exact,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic", model: model) }, EmptySlots(1), 1);
        exact.PendingFactory = probe => Pending(exact, probe,
            selected: exact.PendingCalls >= 256, claimed: exact.PendingCalls >= 256 ? model : null,
            claimedKey: exact.PendingCalls >= 256 ? "Relic" : null,
            slots: EmptySlots(1), capacity: 1);
        var exactSession = new ItemV1Session(Nonce, exact);
        ItemV1Observation exactReady = Ready(exactSession.Read());
        Accepted(exactSession.Apply(exactReady.DecisionId, "collect:1"));
        for (int read = 1; read < 256; read++)
        {
            Check(Status(exactSession.Read()) == "waiting", "exact-limit wait " + read);
        }
        ItemV1ResolvedResult resolved = Resolved(exactSession.Read());
        int calls = exact.PendingCalls;
        Check(ReferenceEquals(resolved, exactSession.Read()) && exact.PendingCalls == calls,
            "resolved stable and no reread");
    }

    private static void MalformedCaptureAndFixedFailures()
    {
        var throwingSurface = new FakeAdapter
        {
            SurfaceFactory = () => throw new InvalidOperationException(Canary),
        };
        var throwingSurfaceSession = new ItemV1Session(Nonce, throwingSurface);
        IItemV1ReadValue surfaceFailure = throwingSurfaceSession.Read();
        Check(Status(surfaceFailure) == "unsupported" &&
              !PublicStrings(surfaceFailure).Any(value => value.Contains(Canary,
                  StringComparison.Ordinal)), "surface exception canary excluded");
        int throwingSurfaceCalls = throwingSurface.SurfaceCalls;
        Check(Status(throwingSurfaceSession.Read()) == "unsupported" &&
              throwingSurface.SurfaceCalls == throwingSurfaceCalls,
            "surface exception latched no reread");

        var nullSurface = new FakeAdapter { SurfaceFactory = () => null! };
        var nullSession = new ItemV1Session(Nonce, nullSurface);
        Check(Status(nullSession.Read()) == "unsupported", "null surface fixed failure");
        int calls = nullSurface.SurfaceCalls;
        Check(Status(nullSession.Read()) == "unsupported" && nullSurface.SurfaceCalls == calls,
            "null surface latch");

        var nullOffer = new FakeAdapter();
        nullOffer.Surface = Surface(nullOffer, new ItemV1NativeOffer[] { null! },
            EmptySlots(1), 1);
        Check(Status(new ItemV1Session(Nonce, nullOffer).Read()) == "unsupported",
            "null offer fixed failure");
        var nullSlot = new FakeAdapter();
        nullSlot.Surface = Surface(nullSlot,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic") },
            new ItemV1PotionSlotBinding[] { null! }, 1);
        Check(Status(new ItemV1Session(Nonce, nullSlot).Read()) == "unsupported",
            "null slot fixed failure");

        var applyNull = new FakeAdapter();
        applyNull.Surface = Surface(applyNull,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic") }, EmptySlots(1), 1);
        var applySession = new ItemV1Session(Nonce, applyNull);
        ItemV1Observation ready = Ready(applySession.Read());
        applyNull.SurfaceFactory = () => null!;
        Check(ApplyFailure(applySession.Apply(ready.DecisionId, "collect:1")).Outcome ==
              "unsupported" && applyNull.Dispatches == 0, "null recapture no dispatch");

        var pendingNull = ReadyPendingSession(out ItemV1Session pendingSession,
            out FakeAdapter pendingAdapter, out object pendingModel);
        pendingAdapter.PendingFactory = _ => null!;
        Check(Status(pendingSession.Read()) == "unsupported", "null pending fixed failure");
        int pendingCalls = pendingAdapter.PendingCalls;
        Check(Status(pendingSession.Read()) == "unsupported" &&
              pendingAdapter.PendingCalls == pendingCalls, "null pending latch");

        ReadyPendingSession(out ItemV1Session throwingPending,
            out FakeAdapter throwingPendingAdapter, out _);
        throwingPendingAdapter.PendingFactory = _ =>
            throw new InvalidOperationException(Canary);
        IItemV1ReadValue pendingFailure = throwingPending.Read();
        Check(Status(pendingFailure) == "unsupported" &&
              !PublicStrings(pendingFailure).Any(value => value.Contains(Canary,
                  StringComparison.Ordinal)), "pending exception canary excluded");
        int throwingPendingCalls = throwingPendingAdapter.PendingCalls;
        Check(Status(throwingPending.Read()) == "unsupported" &&
              throwingPendingAdapter.PendingCalls == throwingPendingCalls,
            "pending exception latched no reread");

        foreach ((object? claimed, string? key, string label) in new[]
        {
            ((object?)null, "Relic", "null model nonnull key"),
            (new object(), (string?)null, "nonnull model null key"),
            (new object(), "Wrong", "nonnull model wrong key"),
        })
        {
            ReadyPendingSession(out ItemV1Session asymmetric, out FakeAdapter fake,
                out object offered);
            fake.PendingFactory = probe => Pending(fake, probe, false, claimed, key,
                EmptySlots(1), 1);
            Check(Status(asymmetric.Read()) == "unsupported", label);
            int reads = fake.PendingCalls;
            Check(Status(asymmetric.Read()) == "unsupported" && fake.PendingCalls == reads,
                label + " latched");
        }

        ReadyPendingSession(out ItemV1Session selectedNoClaim, out FakeAdapter selectedFake,
            out _);
        selectedFake.PendingFactory = probe => Pending(selectedFake, probe, true, null, null,
            EmptySlots(1), 1);
        Check(Status(selectedNoClaim.Read()) == "unsupported", "selected null claim");

        foreach ((Action<FakeAdapter> mutate, string label) in new[]
        {
            ((Action<FakeAdapter>)(fake => fake.PendingRun = new object()), "changed retained run"),
            (fake => fake.PendingPlayer = new object(), "changed retained player"),
            (fake => fake.PendingReward = new object(), "changed retained reward"),
            (fake => fake.PendingOffered = new object(), "changed retained offered model"),
        })
        {
            ReadyPendingSession(out ItemV1Session bindingSession, out FakeAdapter bindingFake,
                out _);
            mutate(bindingFake);
            Check(Status(bindingSession.Read()) == "unsupported", label);
            int reads = bindingFake.PendingCalls;
            Check(Status(bindingSession.Read()) == "unsupported" &&
                  bindingFake.PendingCalls == reads, label + " latched no reread");
        }
    }

    private static void CheckPotionFailure(
        IReadOnlyList<ItemV1PotionSlotBinding> before,
        int currentCapacity,
        IReadOnlyList<ItemV1PotionSlotBinding> current,
        object offered,
        object? claimed,
        string? claimedKey,
        bool selected,
        string label)
    {
        var adapter = new FakeAdapter();
        adapter.Surface = Surface(adapter,
            new[] { Offer(3, ItemV1ItemKind.Potion, "Potion_New", model: offered) },
            before, before.Count);
        adapter.PendingFactory = probe => Pending(adapter, probe, selected, claimed,
            claimedKey, current, currentCapacity);
        var session = new ItemV1Session(Nonce, adapter);
        ItemV1Observation ready = Ready(session.Read());
        Accepted(session.Apply(ready.DecisionId, "collect:3"));
        Check(Status(session.Read()) == "unsupported", label);
    }

    private static ItemV1Observation ReadyPendingSession(
        out ItemV1Session session,
        out FakeAdapter adapter,
        out object model)
    {
        adapter = new FakeAdapter();
        model = new object();
        adapter.Surface = Surface(adapter,
            new[] { Offer(1, ItemV1ItemKind.Relic, "Relic", model: model) },
            EmptySlots(1), 1);
        session = new ItemV1Session(Nonce, adapter);
        ItemV1Observation ready = Ready(session.Read());
        Accepted(session.Apply(ready.DecisionId, "collect:1"));
        return ready;
    }

    private static ItemV1SurfaceCapture Surface(
        FakeAdapter owner,
        IReadOnlyList<ItemV1NativeOffer> offers,
        IReadOnlyList<ItemV1PotionSlotBinding> slots,
        int capacity,
        object? run = null,
        object? player = null,
        object? screen = null)
    {
        owner.Remember(offers);
        return ItemV1SurfaceCapture.Available(
            run ?? owner.Run,
            player ?? owner.Player,
            screen ?? owner.Screen,
            capacity,
            offers,
            slots);
    }

    private static ItemV1NativeOffer Offer(
        int index,
        ItemV1ItemKind kind,
        string key,
        bool enabled = true,
        bool populated = true,
        bool selected = false,
        object? button = null,
        object? reward = null,
        object? model = null,
        Action? dispatch = null) =>
        new(index, kind, key, populated, selected, true, enabled,
            button ?? new object(), reward ?? new object(), model ?? new object(),
            dispatch ?? (() => { }));

    private static ItemV1NativeOffer Clone(
        ItemV1NativeOffer source,
        object? button = null,
        object? reward = null,
        object? model = null,
        string? key = null,
        bool? enabled = null) =>
        new(source.Index, source.Kind, key ?? source.StableKey, source.Populated,
            source.AlreadySelected, source.ButtonVisible, enabled ?? source.ButtonEnabled,
            button ?? source.ButtonIdentity, reward ?? source.RewardIdentity,
            model ?? source.OfferedModelIdentity, source.Dispatch);

    private static ItemV1PotionSlotBinding[] EmptySlots(int count) =>
        Enumerable.Range(0, count).Select(_ => new ItemV1PotionSlotBinding(null, null)).ToArray();

    private static ItemV1PendingCapture Pending(
        FakeAdapter owner,
        ItemV1PendingProbe probe,
        bool selected,
        object? claimed,
        string? claimedKey,
        IReadOnlyList<ItemV1PotionSlotBinding> slots,
        int capacity) =>
        new(owner.PendingRun ?? probe.RunIdentity,
            owner.PendingPlayer ?? probe.PlayerIdentity,
            owner.PendingReward ?? probe.RewardIdentity,
            owner.PendingOffered ?? probe.OfferedModelIdentity,
            owner.PendingOfferedKey ?? owner.StableKeyFor(probe.OfferedModelIdentity),
            selected, claimed, claimedKey, capacity, slots);

    private static ItemV1Observation Ready(IItemV1ReadValue value)
    {
        Check(value is ItemV1Observation { Status: "ready" }, "expected ready");
        return (ItemV1Observation)value;
    }

    private static ItemV1ResolvedResult Resolved(IItemV1ReadValue value)
    {
        Check(value is ItemV1ResolvedResult, "expected resolved");
        return (ItemV1ResolvedResult)value;
    }

    private static string Status(IItemV1ReadValue value)
    {
        Check(value is ItemV1Observation, "expected observation");
        return ((ItemV1Observation)value).Status;
    }

    private static ItemV1DispatchReceipt Accepted(IItemV1ApplyValue value)
    {
        Check(value is ItemV1DispatchReceipt { Outcome: "accepted" }, "expected accepted");
        return (ItemV1DispatchReceipt)value;
    }

    private static ItemV1ApplyFailure ApplyFailure(IItemV1ApplyValue value)
    {
        Check(value is ItemV1ApplyFailure, "expected apply failure");
        return (ItemV1ApplyFailure)value;
    }

    private static IEnumerable<string> PublicPropertyNames(Type type) =>
        type.GetProperties(BindingFlags.Instance | BindingFlags.Public)
            .Select(property => property.Name).OrderBy(name => name, StringComparer.Ordinal);

    private static IEnumerable<string> PublicStrings(object value) =>
        value.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public)
            .Where(property => property.PropertyType == typeof(string))
            .Select(property => (string?)property.GetValue(value) ?? string.Empty);

    private static void Run(string name, Action action)
    {
        try
        {
            action();
            _checks++;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(name + ": " + exception.GetType().Name + ": " +
                exception.Message);
            throw;
        }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    private static void ExpectThrows<T>(Action action, string message) where T : Exception
    {
        try
        {
            action();
        }
        catch (T)
        {
            return;
        }
        throw new InvalidOperationException(message);
    }

    private sealed class FakeAdapter : IItemV1NativeAdapter
    {
        public object Run { get; } = new();
        public object Player { get; } = new();
        public object Screen { get; } = new();
        public ItemV1SurfaceCapture Surface { get; set; } = ItemV1SurfaceCapture.Missing();
        public Func<ItemV1SurfaceCapture>? SurfaceFactory { get; set; }
        public Func<ItemV1PendingProbe, ItemV1PendingCapture>? PendingFactory { get; set; }
        public object? PendingRun { get; set; }
        public object? PendingPlayer { get; set; }
        public object? PendingReward { get; set; }
        public object? PendingOffered { get; set; }
        public string? PendingOfferedKey { get; set; }
        public int SurfaceCalls { get; private set; }
        public int PendingCalls { get; private set; }
        public int Dispatches { get; set; }
        private readonly List<(object Model, string Key)> _keys = new();

        public void Remember(IReadOnlyList<ItemV1NativeOffer> offers)
        {
            foreach (ItemV1NativeOffer offer in offers)
            {
                if (offer is not null)
                {
                    _keys.Add((offer.OfferedModelIdentity, offer.StableKey));
                }
            }
        }

        public string StableKeyFor(object model)
        {
            for (int index = _keys.Count - 1; index >= 0; index--)
            {
                if (ReferenceEquals(_keys[index].Model, model))
                {
                    return _keys[index].Key;
                }
            }
            return string.Empty;
        }

        public ItemV1SurfaceCapture CaptureSurface()
        {
            SurfaceCalls++;
            return SurfaceFactory is null ? Surface : SurfaceFactory();
        }

        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending)
        {
            PendingCalls++;
            return PendingFactory is null
                ? Pending(this, pending, false, null, null, EmptySlots(1), 1)
                : PendingFactory(pending);
        }
    }
}
