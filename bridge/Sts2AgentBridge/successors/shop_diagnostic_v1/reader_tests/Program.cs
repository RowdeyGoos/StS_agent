using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading;
using DiagnosticStubs;
using Godot;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1.Tests;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int _checks;

    private static int Main()
    {
        try
        {
            Check(NativeReadyParity);
            Check(NativeShortCircuitParity);
            Check(NativeOfferParity);
            Check(NativeExceptionAndNoAction);
            Check(CoreReadyAndLowercaseParity);
            Check(CoreContextParity);
            Check(CoreDeckParity);
            Check(CoreOfferParity);
            Check(CoreInventoryParity);
            Check(SyntheticUnstockedCardParity);
            Check(RecorderAndCombinationGuards);
            Check(ValueMapAndCodecParity);
            Check(OnceOwnerAndCleanup);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"shop_diagnostic_v1_reader\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"shop_diagnostic_v1_reader\",\"check_count\":0}");
            return 1;
        }
    }

    private static void NativeReadyParity()
    {
        NativePair pair = NativePair.Read(g => { });
        Sequence(pair.OldLog, pair.NewLog);
        Equal(ShopV1SurfaceStatus.Available, pair.Old.Status);
        Equal(ShopDiagnosticSurfaceStatus.Available, pair.New.Status);
        Equal(pair.Old.Gold, pair.New.Gold);
        Equal(pair.Old.Deck.Count, pair.New.Deck.Count);
        Equal(pair.Old.Offers.Count, pair.New.Offers.Count);
        Equal(pair.Old.Offers[0].Slot, pair.New.Offers[0].Slot);
        Equal(pair.Old.Offers[0].StableKey, pair.New.Offers[0].StableKey);
        Equal(pair.Old.Offers[0].DisplayedPrice, pair.New.Offers[0].DisplayedPrice);
        True(pair.New.Offers[0].PurchaseActionReady);
        False(pair.NewLog.Any(x => x.StartsWith("ACTION:", StringComparison.Ordinal)));
        pair.DisposeOld();
    }

    private static void NativeShortCircuitParity()
    {
        NativePair roomMissing = NativePair.Read(g => NMerchantRoom.Instance = null);
        Sequence(roomMissing.OldLog, roomMissing.NewLog);
        Equal(ShopDiagnosticSurfaceStatus.Missing, roomMissing.New.Status);
        Equal(ShopDiagnosticReason.RoomUnavailable, roomMissing.Reason);

        NativePair invalidBack = NativePair.Read(g => g.Back.Valid = false);
        Sequence(invalidBack.OldLog, invalidBack.NewLog);
        Equal(ShopDiagnosticReason.BackControlUnavailable, invalidBack.Reason);
        Equal(ShopDiagnosticSurfaceStatus.Unsupported, invalidBack.New.Status);
    }

    private static void NativeOfferParity()
    {
        NativePair missingEntry = NativePair.Read(g => g.CardSlot.EntryValue = null);
        Sequence(missingEntry.OldLog, missingEntry.NewLog);
        Equal(ShopDiagnosticReason.OfferEntryUnavailable, missingEntry.Reason);

        NativePair badPrice = NativePair.Read(g => g.Label.TextValue = "01");
        Sequence(badPrice.OldLog, badPrice.NewLog);
        Equal(ShopDiagnosticReason.CostTextInvalid, badPrice.Reason);

        NativePair hidden = NativePair.Read(g => g.CardSlot.VisibleValue = false);
        Sequence(hidden.OldLog, hidden.NewLog);
        Equal(0, hidden.New.Offers.Count);
        Equal(ShopDiagnosticReason.None, hidden.Reason);
    }

    private static void NativeExceptionAndNoAction()
    {
        var throwing = new ThrowingAdapter();
        string json = Observe(throwing);
        Contains(json, "\"stage\":\"native_offers\"");
        Contains(json, "\"reason\":\"native_exception\"");
        False(json.Contains(ThrowingAdapter.Canary, StringComparison.Ordinal));
        Equal(1, throwing.Calls);
    }

    private static void CoreReadyAndLowercaseParity()
    {
        CapturePair pair = CapturePair.Ready("lower_key");
        Equal("ready", OriginalStatus(pair.Original));
        string json = Observe(new FixedAdapter(pair.Diagnostic));
        Contains(json, "\"shop_status\":\"ready\"");
        Contains(json, "\"stage\":\"complete\"");
        Contains(json, "\"reason\":\"none\"");
        ExactFiveFields(json);
    }

    private static void CoreContextParity()
    {
        AssertParity(CapturePair.Ready().With(gold: -1), "core_context", "gold_out_of_range");
        AssertParity(CapturePair.Ready().With(roomVisible: false), "core_context", "room_not_visible");
        AssertParity(CapturePair.Ready().With(foreground: true), "core_context", "foreground_blocked");
        AssertParity(CapturePair.Ready().With(mapOpen: true), "core_context", "map_open");
        AssertParity(CapturePair.Ready().With(inventoryOpen: false), "core_context", "initial_binding_invalid");
    }

    private static void CoreDeckParity()
    {
        CapturePair pair = CapturePair.Ready();
        pair.DiagnosticDeck[0] = new ShopDiagnosticDeckCard(new object(), "bad-key");
        pair.OriginalDeck[0] = new ShopV1DeckCardBinding(new object(), "bad-key");
        AssertParity(pair.Rebuild(), "core_deck", "deck_binding_invalid");
    }

    private static void CoreOfferParity()
    {
        AssertParity(CapturePair.Ready().With(offerKey: "bad-key"), "core_offers", "offer_key_invalid");
        AssertParity(CapturePair.Ready().With(offerVisible: false), "core_offers", "offer_not_visible");
        AssertParity(CapturePair.Ready().With(cardInDeck: true), "core_offers", "card_already_in_deck");
        AssertParity(CapturePair.Ready().WithDuplicateOfferIdentity(), "core_offers", "offer_identity_duplicate");
        AssertParity(CapturePair.Ready().WithNullOffer(), "core_offers", "projection_exception");
        AssertParity(CapturePair.Ready().WithInvalidKind(), "core_offers", "projection_exception");
    }

    private static void CoreInventoryParity()
    {
        AssertParity(CapturePair.Ready().With(inventoryVisible: false), "core_inventory", "inventory_not_visible");
        AssertParity(CapturePair.Ready().With(backEnabled: false), "core_inventory", "back_control_not_ready");
    }

    private static void SyntheticUnstockedCardParity()
    {
        CapturePair pair = CapturePair.Ready().With(stocked: false);
        Equal("ready", OriginalStatus(pair.Original));
        string json = Observe(new FixedAdapter(pair.Diagnostic));
        Contains(json, "\"shop_status\":\"ready\"");
    }

    private static void RecorderAndCombinationGuards()
    {
        string invalid = Observe(new InvalidRecorderAdapter());
        Contains(invalid, "\"stage\":\"native_context\"");
        Contains(invalid, "\"reason\":\"native_exception\"");
        Throws<InvalidOperationException>(() => Observe(new DisagreeingAdapter()));
    }

    private static void ValueMapAndCodecParity()
    {
        Assembly testAssembly = Assembly.GetExecutingAssembly();
        Assembly assembly = typeof(ShopDiagnosticService).Assembly;
        using System.IO.Stream stream = testAssembly.GetManifestResourceStream("diagnostic_values.json") ??
            throw new InvalidOperationException();
        using JsonDocument values = JsonDocument.Parse(stream);
        JsonElement root = values.RootElement;
        Equal(Enum.GetValues<ShopDiagnosticStage>().Length,
            root.GetProperty("stages").GetArrayLength());
        Equal(Enum.GetValues<ShopDiagnosticReason>().Length,
            root.GetProperty("reasons").GetArrayLength());
        string[] stageNames = root.GetProperty("stages").EnumerateArray()
            .Select(x => x.GetString() ?? throw new InvalidOperationException()).ToArray();
        string[] reasonNames = root.GetProperty("reasons").EnumerateArray()
            .Select(x => x.GetString() ?? throw new InvalidOperationException()).ToArray();
        var allowed = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty status in root.GetProperty("combinations").EnumerateObject())
        {
            foreach (JsonProperty stage in status.Value.EnumerateObject())
            {
                foreach (JsonElement reason in stage.Value.EnumerateArray())
                    allowed.Add(status.Name + "|" + stage.Name + "|" + reason.GetString());
            }
        }
        Type codec = assembly.GetType(
            "Sts2AgentBridge.Successors.ShopDiagnosticV1.ShopDiagnosticCodec",
            throwOnError: true)!;
        MethodInfo encode = codec.GetMethod("Encode", BindingFlags.Static | BindingFlags.NonPublic) ??
            throw new InvalidOperationException();
        foreach (string status in new[] { "ready", "waiting", "unsupported", "invalid" })
        {
            foreach (ShopDiagnosticStage stage in Enum.GetValues<ShopDiagnosticStage>())
            {
                foreach (ShopDiagnosticReason reason in Enum.GetValues<ShopDiagnosticReason>())
                {
                    bool accepted;
                    byte[]? encoded = null;
                    try
                    {
                        encoded = (byte[]?)encode.Invoke(null, new object[] { status, stage, reason });
                        accepted = true;
                    }
                    catch (TargetInvocationException ex) when (ex.InnerException is InvalidOperationException)
                    {
                        accepted = false;
                    }
                    string stageValue = stageNames[(int)stage - 1];
                    string reasonValue = reasonNames[(int)reason - 1];
                    if (encoded is not null)
                    {
                        using JsonDocument record = JsonDocument.Parse(encoded);
                        Equal(stageValue, record.RootElement.GetProperty("stage").GetString());
                        Equal(reasonValue, record.RootElement.GetProperty("reason").GetString());
                    }
                    bool expected = allowed.Contains(status + "|" + stageValue + "|" + reasonValue);
                    Equal(expected, accepted);
                    if (encoded is not null) Array.Clear(encoded);
                }
            }
        }
        Equal(66, allowed.Count);
    }

    private static void OnceOwnerAndCleanup()
    {
        var adapter = new FixedAdapter(CapturePair.Ready().Diagnostic);
        using var service = new ShopDiagnosticService(adapter);
        Exception? threadFailure = null;
        var thread = new Thread(() =>
        {
            try { service.Observe(); }
            catch (Exception ex) { threadFailure = ex; }
        });
        thread.Start();
        thread.Join();
        True(threadFailure is InvalidOperationException);
        _ = service.Observe();
        Equal(1, adapter.Calls);
        Throws<InvalidOperationException>(() => service.Observe());

        var reentrant = new ReentrantAdapter();
        using var reentrantService = new ShopDiagnosticService(reentrant);
        reentrant.Service = reentrantService;
        string json = Encoding.ASCII.GetString(reentrantService.Observe());
        Contains(json, "\"reason\":\"native_exception\"");
        Equal(1, reentrant.Calls);
    }

    private static void AssertParity(CapturePair pair, string stage, string reason)
    {
        Equal("unsupported", OriginalStatus(pair.Original));
        string json = Observe(new FixedAdapter(pair.Diagnostic));
        Contains(json, "\"shop_status\":\"unsupported\"");
        Contains(json, "\"stage\":\"" + stage + "\"");
        Contains(json, "\"reason\":\"" + reason + "\"");
    }

    private static string OriginalStatus(ShopV1SurfaceCapture capture)
    {
        var adapter = new OriginalAdapter(capture);
        using var session = new ShopV1Session(Nonce, adapter);
        IRoomFlowReadValue value = session.Read();
        return ((ShopV1Observation)value).Status;
    }

    private static string Observe(IShopDiagnosticAdapter adapter)
    {
        using var service = new ShopDiagnosticService(adapter);
        byte[] bytes = service.Observe();
        True(bytes.Length <= 512);
        string value = Encoding.ASCII.GetString(bytes);
        Array.Clear(bytes);
        return value;
    }

    private static void ExactFiveFields(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        string[] names = document.RootElement.EnumerateObject().Select(x => x.Name).ToArray();
        Sequence(new[] { "schema_version", "status", "shop_status", "stage", "reason" }, names);
    }

    private static void Check(Action action) { action(); _checks++; }
    private static void True(bool value) { if (!value) throw new InvalidOperationException(); }
    private static void False(bool value) => True(!value);
    private static void Equal<T>(T expected, T actual)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual)) throw new InvalidOperationException();
    }
    private static void Contains(string value, string expected)
    {
        if (!value.Contains(expected, StringComparison.Ordinal)) throw new InvalidOperationException();
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

    private sealed class FixedAdapter : IShopDiagnosticAdapter
    {
        private readonly ShopDiagnosticCapture _capture;
        internal FixedAdapter(ShopDiagnosticCapture capture) { _capture = capture; }
        internal int Calls { get; private set; }
        public ShopDiagnosticCapture CaptureSurface(IShopDiagnosticRecorder recorder)
        {
            Calls++;
            return _capture;
        }
    }

    private sealed class ThrowingAdapter : IShopDiagnosticAdapter
    {
        internal const string Canary = "DO_NOT_EMIT_CANARY";
        internal int Calls;
        public ShopDiagnosticCapture CaptureSurface(IShopDiagnosticRecorder recorder)
        {
            Calls++;
            recorder.Enter(ShopDiagnosticStage.NativeOffers);
            throw new InvalidOperationException(Canary);
        }
    }

    private sealed class InvalidRecorderAdapter : IShopDiagnosticAdapter
    {
        public ShopDiagnosticCapture CaptureSurface(IShopDiagnosticRecorder recorder)
        {
            recorder.Enter((ShopDiagnosticStage)999);
            return ShopDiagnosticCapture.Missing();
        }
    }

    private sealed class DisagreeingAdapter : IShopDiagnosticAdapter
    {
        public ShopDiagnosticCapture CaptureSurface(IShopDiagnosticRecorder recorder)
        {
            recorder.Reject(ShopDiagnosticReason.RunUnavailable);
            return CapturePair.Ready().Diagnostic;
        }
    }

    private sealed class ReentrantAdapter : IShopDiagnosticAdapter
    {
        internal ShopDiagnosticService? Service;
        internal int Calls;
        public ShopDiagnosticCapture CaptureSurface(IShopDiagnosticRecorder recorder)
        {
            Calls++;
            Service!.Dispose();
            return CapturePair.Ready().Diagnostic;
        }
    }

    private sealed class OriginalAdapter : IShopV1NativeAdapter
    {
        private readonly ShopV1SurfaceCapture _capture;
        internal OriginalAdapter(ShopV1SurfaceCapture capture) { _capture = capture; }
        public ShopV1SurfaceCapture CaptureSurface() => _capture;
        public ShopV1PendingCapture CapturePending(ShopV1PendingProbe pending) =>
            ShopV1PendingCapture.Unsupported();
    }

    private sealed class InertDispatch : IShopV1NativeDispatch
    {
        public ShopV1Completion Completion => ShopV1Completion.Pending;
        public void Invoke() => throw new InvalidOperationException();
        public void Dispose() { }
    }

    private sealed class CapturePair
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
        internal readonly InertDispatch Dispatch = new();
        internal List<ShopDiagnosticDeckCard> DiagnosticDeck = new();
        internal List<ShopV1DeckCardBinding> OriginalDeck = new();
        internal ShopDiagnosticCapture Diagnostic = null!;
        internal ShopV1SurfaceCapture Original = null!;
        private string _key = "Card_Key";
        private int _gold = 100;
        private bool _roomVisible = true;
        private bool _inventoryVisible = true;
        private bool _inventoryOpen = true;
        private bool _foreground;
        private bool _mapOpen;
        private bool _offerVisible = true;
        private bool _backEnabled = true;
        private bool _stocked = true;
        private bool _cardInDeck;
        private bool _duplicateIdentity;

        internal static CapturePair Ready(string key = "Card_Key")
        {
            var value = new CapturePair { _key = key };
            value.OriginalDeck.Add(new ShopV1DeckCardBinding(new object(), "Base_Key"));
            value.DiagnosticDeck.Add(new ShopDiagnosticDeckCard(new object(), "Base_Key"));
            return value.Rebuild();
        }

        internal CapturePair With(
            int? gold = null, bool? roomVisible = null, bool? inventoryVisible = null,
            bool? inventoryOpen = null, bool? foreground = null, bool? mapOpen = null,
            string? offerKey = null, bool? offerVisible = null, bool? backEnabled = null,
            bool? stocked = null, bool? cardInDeck = null, bool? duplicateIdentity = null)
        {
            if (gold.HasValue) _gold = gold.Value;
            if (roomVisible.HasValue) _roomVisible = roomVisible.Value;
            if (inventoryVisible.HasValue) _inventoryVisible = inventoryVisible.Value;
            if (inventoryOpen.HasValue) _inventoryOpen = inventoryOpen.Value;
            if (foreground.HasValue) _foreground = foreground.Value;
            if (mapOpen.HasValue) _mapOpen = mapOpen.Value;
            if (offerKey is not null) _key = offerKey;
            if (offerVisible.HasValue) _offerVisible = offerVisible.Value;
            if (backEnabled.HasValue) _backEnabled = backEnabled.Value;
            if (stocked.HasValue) _stocked = stocked.Value;
            if (cardInDeck.HasValue) _cardInDeck = cardInDeck.Value;
            if (duplicateIdentity.HasValue) _duplicateIdentity = duplicateIdentity.Value;
            return Rebuild();
        }

        internal CapturePair Rebuild()
        {
            if (_cardInDeck)
            {
                OriginalDeck = new List<ShopV1DeckCardBinding> { new(Card, _key) };
                DiagnosticDeck = new List<ShopDiagnosticDeckCard> { new(Card, _key) };
            }
            object control = _duplicateIdentity ? Slot : Hitbox;
            Original = new ShopV1SurfaceCapture(
                ShopV1SurfaceStatus.Available, Run, Room, InventoryNode, InventoryModel,
                Player, Map, _roomVisible, _inventoryVisible, _inventoryOpen, _foreground,
                _mapOpen, false, false, _gold, OriginalDeck,
                new[] { new ShopV1NativeOffer(0, ShopV1OfferKind.Card, _key, 40,
                    _stocked, _offerVisible, true, Slot, Entry, Card, control, Label, Dispatch) },
                new ShopV1NativeControl(Back, true, _backEnabled, () => { }),
                new ShopV1NativeControl(Merchant, true, true, null),
                new ShopV1NativeControl(Proceed, true, true, () => { }));
            Diagnostic = new ShopDiagnosticCapture(
                ShopDiagnosticSurfaceStatus.Available, Run, Room, InventoryNode, InventoryModel,
                Player, Map, _roomVisible, _inventoryVisible, _inventoryOpen, _foreground,
                _mapOpen, false, false, _gold, DiagnosticDeck,
                new[] { new ShopDiagnosticOffer(0, ShopDiagnosticOfferKind.Card, _key, 40,
                    _stocked, _offerVisible, true, Slot, Entry, Card, control, Label, true) },
                new ShopDiagnosticControl(Back, true, _backEnabled, true),
                new ShopDiagnosticControl(Merchant, true, true, false),
                new ShopDiagnosticControl(Proceed, true, true, true));
            return this;
        }

        internal CapturePair WithDuplicateOfferIdentity()
        {
            Rebuild();
            object slot2 = new();
            object entry2 = new();
            object card2 = new();
            object label2 = new();
            Original = new ShopV1SurfaceCapture(
                ShopV1SurfaceStatus.Available, Run, Room, InventoryNode, InventoryModel,
                Player, Map, true, true, true, false, false, false, false, 100,
                OriginalDeck,
                new[]
                {
                    new ShopV1NativeOffer(0, ShopV1OfferKind.Card, "Card_One", 40,
                        true, true, true, Slot, Entry, Card, Hitbox, Label, Dispatch),
                    new ShopV1NativeOffer(1, ShopV1OfferKind.Card, "Card_Two", 40,
                        true, true, true, slot2, entry2, card2, Hitbox, label2, new InertDispatch()),
                },
                new ShopV1NativeControl(Back, true, true, () => { }),
                new ShopV1NativeControl(Merchant, true, true, null),
                new ShopV1NativeControl(Proceed, true, true, () => { }));
            Diagnostic = new ShopDiagnosticCapture(
                ShopDiagnosticSurfaceStatus.Available, Run, Room, InventoryNode, InventoryModel,
                Player, Map, true, true, true, false, false, false, false, 100,
                DiagnosticDeck,
                new[]
                {
                    new ShopDiagnosticOffer(0, ShopDiagnosticOfferKind.Card, "Card_One", 40,
                        true, true, true, Slot, Entry, Card, Hitbox, Label, true),
                    new ShopDiagnosticOffer(1, ShopDiagnosticOfferKind.Card, "Card_Two", 40,
                        true, true, true, slot2, entry2, card2, Hitbox, label2, true),
                },
                new ShopDiagnosticControl(Back, true, true, true),
                new ShopDiagnosticControl(Merchant, true, true, false),
                new ShopDiagnosticControl(Proceed, true, true, true));
            return this;
        }

        internal CapturePair WithNullOffer()
        {
            Rebuild();
            Original = new ShopV1SurfaceCapture(
                ShopV1SurfaceStatus.Available, Run, Room, InventoryNode, InventoryModel,
                Player, Map, true, true, true, false, false, false, false, 100,
                OriginalDeck, new ShopV1NativeOffer[] { null! },
                new ShopV1NativeControl(Back, true, true, () => { }),
                new ShopV1NativeControl(Merchant, true, true, null),
                new ShopV1NativeControl(Proceed, true, true, () => { }));
            Diagnostic = new ShopDiagnosticCapture(
                ShopDiagnosticSurfaceStatus.Available, Run, Room, InventoryNode, InventoryModel,
                Player, Map, true, true, true, false, false, false, false, 100,
                DiagnosticDeck, new ShopDiagnosticOffer[] { null! },
                new ShopDiagnosticControl(Back, true, true, true),
                new ShopDiagnosticControl(Merchant, true, true, false),
                new ShopDiagnosticControl(Proceed, true, true, true));
            return this;
        }

        internal CapturePair WithInvalidKind()
        {
            Rebuild();
            Original = new ShopV1SurfaceCapture(
                ShopV1SurfaceStatus.Available, Run, Room, InventoryNode, InventoryModel,
                Player, Map, true, true, true, false, false, false, false, 100,
                OriginalDeck,
                new[] { new ShopV1NativeOffer(0, (ShopV1OfferKind)999, "Invalid_Kind", 40,
                    true, true, true, Slot, Entry, null, Hitbox, Label, null) },
                new ShopV1NativeControl(Back, true, true, () => { }),
                new ShopV1NativeControl(Merchant, true, true, null),
                new ShopV1NativeControl(Proceed, true, true, () => { }));
            Diagnostic = new ShopDiagnosticCapture(
                ShopDiagnosticSurfaceStatus.Available, Run, Room, InventoryNode, InventoryModel,
                Player, Map, true, true, true, false, false, false, false, 100,
                DiagnosticDeck,
                new[] { new ShopDiagnosticOffer(0, (ShopDiagnosticOfferKind)999,
                    "Invalid_Kind", 40, true, true, true, Slot, Entry, null,
                    Hitbox, Label, false) },
                new ShopDiagnosticControl(Back, true, true, true),
                new ShopDiagnosticControl(Merchant, true, true, false),
                new ShopDiagnosticControl(Proceed, true, true, true));
            return this;
        }
    }

    private sealed class NativePair
    {
        internal required ShopV1SurfaceCapture Old;
        internal required ShopDiagnosticCapture New;
        internal required string[] OldLog;
        internal required string[] NewLog;
        internal required ShopDiagnosticReason Reason;

        internal static NativePair Read(Action<NativeGraph> mutate)
        {
            NativeGraph oldGraph = NativeGraph.Create();
            mutate(oldGraph);
            AccessLog.Clear();
            ShopV1SurfaceCapture oldCapture = new PinnedShopV1NativeAdapter().CaptureSurface();
            string[] oldLog = AccessLog.Entries.ToArray();

            NativeGraph newGraph = NativeGraph.Create();
            mutate(newGraph);
            AccessLog.Clear();
            var recorder = new TestRecorder();
            ShopDiagnosticCapture newCapture = new ShopDiagnosticNativeAdapter().CaptureSurface(recorder);
            string[] newLog = AccessLog.Entries.ToArray();
            return new NativePair
            {
                Old = oldCapture,
                New = newCapture,
                OldLog = oldLog,
                NewLog = newLog,
                Reason = recorder.Reason,
            };
        }

        internal void DisposeOld()
        {
            foreach (ShopV1NativeOffer offer in Old.Offers) offer.PurchaseDispatch?.Dispose();
        }
    }

    private sealed class TestRecorder : IShopDiagnosticRecorder
    {
        internal ShopDiagnosticReason Reason = ShopDiagnosticReason.None;
        public void Enter(ShopDiagnosticStage stage) { }
        public void Reject(ShopDiagnosticReason reason) { if (Reason == ShopDiagnosticReason.None) Reason = reason; }
    }

    private sealed class NativeGraph
    {
        internal required NRun Run;
        internal required NMerchantRoom Room;
        internal required NMapScreen Map;
        internal required NMerchantInventory InventoryNode;
        internal required MerchantInventory InventoryModel;
        internal required Player Player;
        internal required MegaCrit.Sts2.Core.Rooms.MerchantRoom RoomModel;
        internal required NBackButton Back;
        internal required NMerchantButton Merchant;
        internal required NProceedButton Proceed;
        internal required NMerchantCard CardSlot;
        internal required Label Label;

        internal static NativeGraph Create()
        {
            var player = new Player();
            var roomModel = new MegaCrit.Sts2.Core.Rooms.MerchantRoom();
            var inventoryModel = new MerchantInventory { PlayerValue = player };
            roomModel.LocalInventoryValue = inventoryModel;
            player.RunStateValue.CurrentRoomValue = roomModel;
            var map = new NMapScreen { Tag = "map" };
            var overlays = new NOverlayStack { Tag = "overlays" };
            var global = new GlobalUiNode { Tag = "globalUi", MapScreenValue = map, OverlaysValue = overlays };
            var run = new NRun { Tag = "run", GlobalUiValue = global };
            var back = new NBackButton { Tag = "back" };
            var merchant = new NMerchantButton { Tag = "merchant" };
            var proceed = new NProceedButton { Tag = "proceed" };
            var label = new Label { Tag = "label", TextValue = "40" };
            var card = new CardModel();
            card.IdValue.EntryValue = "Card_Key";
            var creation = new CardCreationResult { CardValue = card };
            var entry = new MerchantCardEntry { CreationResultValue = creation };
            var hitbox = new NClickableControl { Tag = "hitbox" };
            var slot = new NMerchantCard
            {
                Tag = "slot0", EntryValue = entry, HitboxValue = hitbox, CostLabelValue = label,
            };
            var inventoryNode = new NMerchantInventory
            {
                Tag = "inventoryNode", InventoryValue = inventoryModel, BackValue = back,
                SlotsValue = new NMerchantSlot?[] { slot },
            };
            var room = new NMerchantRoom
            {
                Tag = "room", InventoryValue = inventoryNode, RoomValue = roomModel,
                MerchantButtonValue = merchant, ProceedButtonValue = proceed,
            };
            NRun.Instance = run;
            NMerchantRoom.Instance = room;
            NMapScreen.Instance = map;
            AccessLog.Clear();
            return new NativeGraph
            {
                Run = run, Room = room, Map = map, InventoryNode = inventoryNode,
                InventoryModel = inventoryModel, Player = player, RoomModel = roomModel,
                Back = back, Merchant = merchant, Proceed = proceed, CardSlot = slot, Label = label,
            };
        }
    }
}
