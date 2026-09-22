using System;
using System.Runtime.CompilerServices;
using System.Text.Json;
using Sts2AgentBridge.Successors.ItemV1.Native;
using Sts2AgentBridge.Successors.ItemWireV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event;
using Sts2AgentBridge.Successors.RoomFlowsV1.Event.Native;
using Sts2AgentBridge.Successors.RoomReleaseV1;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;
using Sts2AgentBridge.Successors.CardSelectionV1.ParentNative;
using Sts2AgentBridge.Successors.CardSelectionV1.Wire;
using Sts2AgentBridge.Successors.CardSelectionReleaseV1;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using Sts2AgentBridge.Successors.GenericEventReleaseV10;

namespace Sts2AgentBridge.Unified;

// Construction is deliberately lazy: the router owns this object before any
// native adapter can acquire hooks, including partially failed construction.
internal sealed class NativeBridgeModule : IBridgeModule
{
    public Capability Capability { get; }
    private readonly string _nonce;
    private Func<BridgeRequest, ModuleReply>? _handle;
    private Action? _cleanup;
    private RoomFlowSelection _roomSelection;
    private bool _initialized, _disposed;
    private ReadStageTrace? _readTrace;
    public void SetReadTrace(ReadStageTrace? trace)=>_readTrace=trace;
    private void Stage(int value)=>_readTrace?.Mark(value);
    internal NativeBridgeModule(Capability capability, string nonce) { Capability = capability; _nonce = nonce; }
    public bool Owns(BridgeRequest request) => request.Capability == Capability ||
        Capability == Capability.Rooms && _roomSelection == RoomFlowSelection.Event && request.Capability == Capability.Items;
    public ModuleReply Handle(BridgeRequest request)
    {
        if (_disposed) throw new InvalidOperationException("Module disposed.");
        if (!_initialized) { _initialized = true; Initialize(); }
        return (_handle ?? throw new InvalidOperationException("Native module unavailable."))(request);
    }
    private void Initialize()
    {
        switch (Capability)
        {
            case Capability.Events:
                Stage(4);
                if (!PinnedGenericEventHarmonyGuard.Verify()) throw new InvalidOperationException("Native dependency mismatch.");
                InitializeEvents();
                break;
            case Capability.Cards:
                var cardsNative = new PinnedCardSelectionParentV1NativeAdapter();
                _cleanup = cardsNative.Dispose;
                var cards = new CardSelectionParentV1Session(_nonce, cardsNative);
                _cleanup = cards.Dispose;
                var cardWire = new CardSelectionV1WireService(_nonce, cards);
                _cleanup = cardWire.Dispose;
                CardSelectionReleaseSelection cardPolicy = CardSelectionReleaseSelection.Cheese;
                _handle = request =>
                {
                    byte[]? command = request.IsPost ? CardSelectionTransportServiceBody.Build(request.Decision!, request.Action!) : null;
                    CardSelectionV1WireResponse response;
                    try { response = cardWire.Handle(request.Method, request.Path, command); }
                    finally { if (command is not null) Array.Clear(command); }
                    byte[] body = response.Body;
                    using (var json = JsonDocument.Parse(body))
                        if (Text(json.RootElement, "policy") == "rest_smith_upgrade_one") cardPolicy = CardSelectionReleaseSelection.Smith;
                    var route = request.IsChild ? request.IsPost ? CardSelectionTransportRoute.ChildPost : CardSelectionTransportRoute.ChildGet :
                        request.IsPost ? CardSelectionTransportRoute.ParentPost : CardSelectionTransportRoute.ParentGet;
                    return Checked(body, (int)CardSelectionTerminalClassifier.Classify(route, cardPolicy, _nonce, response.StatusCode, body),
                        root => route == CardSelectionTransportRoute.ParentGet && Text(root, "kind") == "parent_resolved");
                };
                break;
            case Capability.Rooms:
                var shopNative = new PinnedShopV1NativeAdapter();
                RoomFlowWireService rooms;
                if (shopNative.CaptureSurface().Status == ShopV1SurfaceStatus.Available)
                {
                    _roomSelection = RoomFlowSelection.Shop;
                    var shop = new ShopV1Session(_nonce, shopNative); _cleanup = shop.Dispose;
                    rooms = new RoomFlowWireService(_nonce, shop);
                }
                else
                {
                    _roomSelection = RoomFlowSelection.Event;
                    var room = new EventV1Session(_nonce, new PinnedEventV1NativeAdapter(), new FrozenEventItemChildFactory());
                    _cleanup = room.Dispose;
                    rooms = new RoomFlowWireService(_nonce, room);
                }
                _cleanup = rooms.Dispose;
                _handle = request =>
                {
                    var route = request.Capability == Capability.Items ? request.IsPost ? RoomFlowTransportRoute.ItemPost : RoomFlowTransportRoute.ItemGet :
                        request.IsPost ? RoomFlowTransportRoute.ParentPost : RoomFlowTransportRoute.ParentGet;
                    byte[] body = rooms.Handle(request.Method, request.Path, request.Decision, request.Action);
                    return Checked(body, (int)RoomFlowTerminalClassifier.Classify(route, _roomSelection, _nonce, body),
                        root => route == RoomFlowTransportRoute.ParentGet && Text(root, "status") is "complete" or "resolved");
                };
                break;
            case Capability.Items:
                var items = new ItemWireV1Service(_nonce, new PinnedItemV1NativeAdapter());
                _handle = request =>
                {
                    byte[] body = items.Handle(request.Method, request.Path, request.Decision, request.Action);
                    var route = request.IsPost ? RoomFlowTransportRoute.ItemPost : RoomFlowTransportRoute.ItemGet;
                    return Checked(body, (int)RoomFlowTerminalClassifier.Classify(route, RoomFlowSelection.Event, _nonce, body),
                        root => !request.IsPost && Text(root, "status") == "resolved");
                };
                break;
            default: throw new InvalidOperationException("Unknown native module.");
        }
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private void InitializeEvents()
    {
                _cleanup = GenericEventV7Hooks.RecoverFailedInstallation;
                Stage(5);
                var native = new PinnedGenericEventV7NativeAdapter(incrementalHooks:true,readStage:Stage);
                _cleanup = native.Dispose;
                Stage(9);
                var events = new GenericEventV7Session(native, _nonce);
                _cleanup = events.Dispose;
                Stage(10);
                var eventWire = new GenericEventV7WireService(_nonce, events);
                _cleanup = eventWire.Dispose;
                _handle = request =>
                {
                    if(CoreBridgeModule.IsResumeItem(request)) {
                        var value=request.IsPost?native.ApplyResumeItem(request.Decision,request.Action):native.ReadResumeItem();
                        byte[] itemBody=GenericEventV7WireService.EncodeItem(value);
                        using var itemJson=JsonDocument.Parse(itemBody);
                        string? status=Text(itemJson.RootElement,"status")??Text(itemJson.RootElement,"outcome");
                        return new(itemBody,Terminal:status is not ("ready" or "waiting" or "accepted" or "resolved"));
                    }
                    byte[]? command = request.IsPost ? GenericEventTransportServiceBody.Build(request.Decision!, request.Action!,
                        request.ChildOrdinal, request.ParentDecision, request.ParentAction) : null;
                    byte[] body;
                    Stage(11);
                    try { body = eventWire.Handle(request.Method, request.Path, command); }
                    finally { if (command is not null) Array.Clear(command); }
                    var route = request.IsPost ? request.IsChild ? GenericEventTransportRoute.ChildPost : GenericEventTransportRoute.ParentPost : GenericEventTransportRoute.DecisionGet;
                    var classification = GenericEventTerminalClassifier.Classify(route, GenericEventReleaseSelection.Generic, _nonce, 200, body);
                    return Checked(body, (int)classification, root => !request.IsPost && Text(root, "kind") == "decision" &&
                        root.TryGetProperty("parent", out var parent) && parent.ValueKind == JsonValueKind.Object &&
                        Text(parent, "status") == "complete" && Text(parent, "phase") is "map_handoff" or "combat_handoff" or "combat_resume_handoff" or "run_won" or "run_abandoned") with { Diagnostic = native.LastDiagnostic, EventDiagnostic = true, CombatScope=native.CombatScope, CombatResume=native.CombatResume, CombatResumeDiagnostic=()=>native.CombatResumeDiagnostic, EventNonce=_nonce };
                };
    }
    private static string? Text(JsonElement value, string name) =>
        value.TryGetProperty(name, out var property) && property.ValueKind == JsonValueKind.String ? property.GetString() : null;
    private static ModuleReply Checked(byte[] body, int classification, Func<JsonElement, bool> complete)
    {
        try
        {
            if (classification == 0) throw new InvalidOperationException("Invalid native response.");
            using var json = JsonDocument.Parse(body);
            bool done = complete(json.RootElement);
            return new(body, Complete: done, Terminal: classification == 2 && !done);
        }
        catch { Array.Clear(body); throw; }
    }
    public void Dispose()
    {
        if (_disposed) return;
        _cleanup?.Invoke();
        _cleanup = null; _handle = null; _disposed = true;
    }
}
