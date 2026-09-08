using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.ItemWireV1;

namespace Sts2AgentBridge.Successors.RoomFlowsV1;

public sealed class FrozenEventItemChildFactory : IEventItemChildFactory
{
    private readonly object _gate = new();
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private bool _created;

    public IEventItemChildBroker Create(RoomFlowDispatchReceipt parentReceipt, IItemV1NativeAdapter adapter)
    {
        lock (_gate)
        {
            if (_created || Environment.CurrentManagedThreadId != _owner)
                throw new InvalidOperationException("Child factory unavailable.");
            _created = true;
            return new FrozenEventItemChildBroker(parentReceipt, adapter);
        }
    }
}

// Owns one real frozen wire service/session. The monitor adds parent correlation,
// never a second item state machine or a claim about the event option's effect.
public sealed class FrozenEventItemChildBroker : IEventItemChildBroker
{
    private readonly object _gate = new();
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private ItemWireV1Service? _service;
    private GuardedAdapter? _adapter;
    private EventItemChildStatus _status;
    private Ready? _ready;
    private Accepted? _accepted;
    private bool _inside;
    private bool _interfered;
    private bool _postAttempted;
    private bool _disposed;

    public FrozenEventItemChildBroker(RoomFlowDispatchReceipt parentReceipt, IItemV1NativeAdapter adapter)
    {
        ParentReceipt = parentReceipt ?? throw new ArgumentNullException(nameof(parentReceipt));
        if (parentReceipt.FlowKind != "event")
            throw new ArgumentException("Event parent required.");
        _status = new EventItemChildActive(parentReceipt);
        _adapter = new GuardedAdapter(this, adapter ?? throw new ArgumentNullException(nameof(adapter)));
        _service = new ItemWireV1Service(parentReceipt.SessionNonce, _adapter);
    }

    public RoomFlowDispatchReceipt ParentReceipt { get; }
    public EventItemChildStatus Status { get { lock (_gate) return _status; } }

    public byte[] Handle(string? method, string? route, string? decisionId, string? actionId)
    {
        lock (_gate)
        {
            if (_inside)
            {
                _interfered = true;
                return Error("internal_failure");
            }
            if (_disposed || Environment.CurrentManagedThreadId != _owner ||
                _status is not EventItemChildActive)
            {
                Fail("unsupported");
                return Error("internal_failure");
            }
            bool get = method == "GET" && route == ItemWireV1Protocol.DecisionRoute &&
                decisionId is null && actionId is null;
            bool post = method == "POST" && route == ItemWireV1Protocol.ActionRoute &&
                RoomFlowIdentity.IsDecisionId(decisionId) &&
                ItemWireV1Protocol.IsCanonicalActionId(actionId, out _);
            if (!get && !post)
            {
                Fail("rejected");
                return Error("invalid_request");
            }
            if (post)
            {
                bool priorPost = _postAttempted;
                _postAttempted = true;
                if (priorPost || _ready is null || _ready.Decision != decisionId ||
                    Array.IndexOf(_ready.Actions, actionId) < 0)
                {
                    Fail("rejected");
                    return Error("invalid_request");
                }
            }
            byte[]? owned = null;
            _inside = true;
            try
            {
                owned = _service!.Handle(method, route, decisionId, actionId);
                EnsureActive();
                Observe(owned, post, decisionId, actionId);
                byte[] returned = owned;
                owned = null; // Caller now owns and must zero this exact frozen response.
                return returned;
            }
            catch
            {
                Fail(post ? "uncertain" : "unsupported");
                return Error("internal_failure");
            }
            finally
            {
                if (owned is not null) Array.Clear(owned);
                _inside = false;
            }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed) return;
            _disposed = true;
            if (_inside)
                _interfered = true;
            else if (Environment.CurrentManagedThreadId != _owner)
                Fail("unsupported");
            else if (_status is EventItemChildActive)
                Fail("unsupported");
            _ready = null;
            _accepted = null;
            _service = null;
            _adapter?.Detach();
            _adapter = null;
        }
    }

    private void EnsureActive()
    {
        if (_disposed || _interfered || !_inside || Environment.CurrentManagedThreadId != _owner ||
            _status is not EventItemChildActive)
            throw new InvalidOperationException("Child unavailable.");
    }

    private void Observe(byte[] body, bool post, string? decision, string? action)
    {
        if (body.Length is < 1 or > ItemWireV1Protocol.MaximumBodyBytes)
            throw new InvalidOperationException("Invalid child body.");
        using JsonDocument document = JsonDocument.Parse(body, new JsonDocumentOptions { MaxDepth = 6 });
        JsonElement root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object ||
            Number(root, "schema_version") != 1 || Text(root, "protocol") != "item_probe_v1" ||
            Text(root, "version") != "item_v1" ||
            Text(root, "session_nonce") != ParentReceipt.SessionNonce ||
            Number(root, "surface_ordinal") != 1)
            throw new InvalidOperationException("Mismatched child identity.");
        string status = Text(root, "status");
        switch (status)
        {
            case "ready":
                Shape(root, "decision_id", "offers", "potion_slots", "legal_actions");
                if (post || _accepted is not null) throw new InvalidOperationException();
                _ready = ReadReady(root);
                break;
            case "accepted":
                Shape(root, "decision_id", "action_id");
                if (!post || _ready is null || _accepted is not null ||
                    Text(root, "decision_id") != decision || Text(root, "action_id") != action ||
                    _ready.Decision != decision ||
                    !ItemWireV1Protocol.IsCanonicalActionId(action, out int index))
                    throw new InvalidOperationException();
                ItemV1Offer? offer = Array.Find(_ready.Offers, value => value.Index == index);
                if (offer is null || Array.IndexOf(_ready.Actions, action) < 0)
                    throw new InvalidOperationException();
                _accepted = new Accepted(decision!, action!, offer.Index, offer.Kind, offer.Key);
                _ready = null;
                break;
            case "resolved":
                Shape(root, "decision_id", "action_id", "offer_index", "kind", "key", "result");
                Accepted? accepted = _accepted;
                if (post || accepted is null || Text(root, "decision_id") != accepted.Decision ||
                    Text(root, "action_id") != accepted.Action || Number(root, "offer_index") != accepted.Index ||
                    Text(root, "kind") != accepted.Kind || Text(root, "key") != accepted.Key ||
                    Text(root, "result") != "collected")
                    throw new InvalidOperationException();
                _status = new EventItemChildResolved(ParentReceipt);
                _ready = null;
                break;
            case "waiting":
                Shape(root);
                if (post) throw new InvalidOperationException();
                _ready = null;
                break;
            case "rejected":
            case "uncertain":
            case "unsupported":
                Shape(root);
                Fail(status);
                break;
            case "error":
                Shape(root, "code");
                if (Text(root, "code") is not ("invalid_request" or "internal_failure"))
                    throw new InvalidOperationException();
                Fail(post ? "uncertain" : "unsupported");
                break;
            default:
                throw new InvalidOperationException("Unknown child status.");
        }
    }

    private Ready ReadReady(JsonElement root)
    {
        string decision = Text(root, "decision_id");
        if (!RoomFlowIdentity.IsDecisionId(decision)) throw new InvalidOperationException();
        JsonElement source = root.GetProperty("offers");
        if (source.ValueKind != JsonValueKind.Array || source.GetArrayLength() is < 1 or > 8)
            throw new InvalidOperationException();
        var offers = new List<ItemV1Offer>();
        int last = -1;
        foreach (JsonElement offer in source.EnumerateArray())
        {
            Exact(offer, new[] { "index", "kind", "key", "enabled" });
            int index = Number(offer, "index");
            string kind = Text(offer, "kind"), key = Text(offer, "key");
            if (index <= last || index > 255 || kind is not ("relic" or "potion") ||
                !RoomFlowIdentity.IsStableKey(key)) throw new InvalidOperationException();
            offers.Add(new ItemV1Offer(index, kind, key, offer.GetProperty("enabled").GetBoolean()));
            last = index;
        }
        JsonElement slotSource = root.GetProperty("potion_slots");
        if (slotSource.ValueKind != JsonValueKind.Array || slotSource.GetArrayLength() > 8)
            throw new InvalidOperationException();
        var slots = new List<string?>();
        foreach (JsonElement slot in slotSource.EnumerateArray())
        {
            string? key = slot.ValueKind == JsonValueKind.Null ? null : slot.GetString();
            if (key is not null && !RoomFlowIdentity.IsStableKey(key)) throw new InvalidOperationException();
            slots.Add(key);
        }
        JsonElement actionSource = root.GetProperty("legal_actions");
        if (actionSource.ValueKind != JsonValueKind.Array || actionSource.GetArrayLength() is < 1 or > 8)
            throw new InvalidOperationException();
        var expected = new List<string>();
        foreach (ItemV1Offer offer in offers)
            if (offer.Enabled && (offer.Kind == "relic" || slots.Contains(null)))
                expected.Add("collect:" + offer.Index.ToString(System.Globalization.CultureInfo.InvariantCulture));
        var actions = new List<string>();
        foreach (JsonElement value in actionSource.EnumerateArray()) actions.Add(value.GetString()!);
        if (actions.Count != expected.Count) throw new InvalidOperationException();
        for (int i = 0; i < actions.Count; i++)
            if (actions[i] != expected[i]) throw new InvalidOperationException();
        if (ItemV1CanonicalEncoder.ComputeDecisionId(ParentReceipt.SessionNonce, offers, slots, actions) != decision)
            throw new InvalidOperationException();
        return new Ready(decision, offers.ToArray(), actions.ToArray());
    }

    private void Fail(string outcome)
    {
        if (_status is EventItemChildActive)
            _status = new EventItemChildFailed(ParentReceipt,
                new RoomFlowApplyFailure("event", ParentReceipt.SessionNonce, outcome));
        _ready = null;
        _accepted = null;
    }

    private byte[] Error(string code) => Encoding.UTF8.GetBytes(
        "{\"schema_version\":1,\"protocol\":\"item_probe_v1\",\"version\":\"item_v1\",\"session_nonce\":\"" +
        ParentReceipt.SessionNonce + "\",\"surface_ordinal\":1,\"status\":\"error\",\"code\":\"" + code + "\"}");

    private static string Text(JsonElement value, string key) =>
        value.GetProperty(key).GetString() ?? throw new InvalidOperationException();
    private static int Number(JsonElement value, string key) => value.GetProperty(key).GetInt32();

    private static void Shape(JsonElement root, params string[] extra)
    {
        var names = new List<string> { "schema_version", "protocol", "version", "session_nonce", "surface_ordinal", "status" };
        names.AddRange(extra);
        Exact(root, names);
    }
    private static void Exact(JsonElement root, IReadOnlyList<string> names)
    {
        if (root.ValueKind != JsonValueKind.Object) throw new InvalidOperationException();
        int index = 0;
        foreach (JsonProperty property in root.EnumerateObject())
        {
            if (index >= names.Count || property.Name != names[index++]) throw new InvalidOperationException();
        }
        if (index != names.Count) throw new InvalidOperationException();
    }

    private sealed record Ready(string Decision, ItemV1Offer[] Offers, string[] Actions);
    private sealed record Accepted(string Decision, string Action, int Index, string Kind, string Key);

    // Guards both sides of native callbacks: reentry during recapture cannot
    // return a dispatchable binding after the broker has already failed.
    private sealed class GuardedAdapter(FrozenEventItemChildBroker owner, IItemV1NativeAdapter adapter)
        : IItemV1NativeAdapter
    {
        private IItemV1NativeAdapter? _inner = adapter;
        public void Detach() => _inner = null;
        public ItemV1SurfaceCapture CaptureSurface()
        {
            owner.EnsureActive();
            ItemV1SurfaceCapture value = _inner!.CaptureSurface();
            owner.EnsureActive();
            if (value.Status != ItemV1SurfaceStatus.Available) return value;
            var offers = new List<ItemV1NativeOffer>();
            foreach (ItemV1NativeOffer offer in value.Offers)
            {
                Action dispatch = () =>
                {
                    owner.EnsureActive();
                    offer.Dispatch();
                    owner.EnsureActive();
                };
                offers.Add(new ItemV1NativeOffer(offer.Index, offer.Kind, offer.StableKey,
                    offer.Populated, offer.AlreadySelected, offer.ButtonVisible, offer.ButtonEnabled,
                    offer.ButtonIdentity, offer.RewardIdentity, offer.OfferedModelIdentity, dispatch));
            }
            return ItemV1SurfaceCapture.Available(value.RunIdentity!, value.PlayerIdentity!,
                value.ScreenIdentity!, value.PotionCapacity, offers, value.PotionSlots);
        }
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe)
        {
            owner.EnsureActive();
            ItemV1PendingCapture value = _inner!.CapturePending(probe);
            owner.EnsureActive();
            return value;
        }
    }
}
