using System;
using System.Text;
using Sts2AgentBridge.Core.Transport;
using Sts2AgentBridge.Successors.ItemTransportV1;
using Sts2AgentBridge.Successors.RoomReleaseV1;
using Sts2AgentBridge.Successors.CardSelectionReleaseV1;
using Sts2AgentBridge.Successors.GenericEventReleaseV10;

namespace Sts2AgentBridge.Unified;

internal enum Capability { Core, Items, Rooms, Cards, Events }

internal static class BridgeTransportLimits
{
    internal const int Port = 43117, Backlog = 8, MaximumHandlers = 4;
    internal const int MaximumRequestHead = 4096, RequestBufferSize = 4097, MaximumBody = 66560;
    internal const int MaximumReads = 16384, MaximumTotalPosts = 512;
    internal const int HeaderReadMilliseconds = 1000, ResponseWriteMilliseconds = 1000;
    internal const int ConnectionLifetimeMilliseconds = 2000, ShutdownJoinMilliseconds = 2000;
}

internal static class BridgeConfiguration
{
    internal static ReadOnlySpan<byte> Enabled => "{\"schema_version\":\"bridge_transport_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;
    internal static bool IsEnabled(ReadOnlySpan<byte> bytes) => bytes.SequenceEqual(Enabled);
}

internal sealed class BridgeTransportFactoryFailure : Exception
{
    internal BridgeTransportFactoryFailure(Action cleanup) : base("Owner-frame cleanup required.") => OwnerFrameCleanup = cleanup;
    internal Action OwnerFrameCleanup { get; }
}

internal sealed record BridgeRequest(Capability Capability, string Path, bool IsPost,
    int AuthorizationOffset, int AuthorizationLength, string? Decision = null, string? Action = null,
    int ChildOrdinal = 0, string? ParentDecision = null, string? ParentAction = null)
{
    internal string Method => IsPost ? "POST" : "GET";
    internal bool IsChild => ChildOrdinal != 0 || Path.StartsWith("/card-selection-v1/child", StringComparison.Ordinal);
    internal bool IsMetadata => Path is "/probe/v0/health" or "/probe/v0/manifest";
    internal bool CanStart => !IsPost && (Capability != Capability.Cards || Path == "/card-selection-v1/parent");
}

internal static class BridgeRequestParser
{
    // Each existing wire grammar remains authoritative. Parsing performs no native access.
    internal static bool TryParse(ReadOnlySpan<byte> head, out BridgeRequest request)
    {
        request = null!;
        int lineEnd = head.IndexOf("\r\n"u8);
        if (lineEnd < 0) return false;
        string[] first = Encoding.ASCII.GetString(head[..lineEnd]).Split(' ');
        if (first.Length != 3) return false;
        string path = first[1];
        if (GenericEventTransportRequestParser.TryParse(head, GenericEventReleaseSelection.Generic, out var events))
        {
            request = new(Capability.Events, path, events.IsPost, events.AuthorizationOffset, 64,
                Text(head, events.DecisionOffset, events.DecisionLength), Text(head, events.ActionOffset, events.ActionLength),
                events.ChildOrdinal, Text(head, events.ParentDecisionOffset, events.ParentDecisionLength),
                Text(head, events.ParentActionOffset, events.ParentActionLength));
            return true;
        }
        if (CardSelectionTransportRequestParser.TryParse(head, CardSelectionReleaseSelection.Cheese, out var cards))
        {
            request = new(Capability.Cards, path, cards.IsPost, cards.AuthorizationOffset, 64,
                Text(head, cards.DecisionOffset, cards.DecisionLength), Text(head, cards.ActionOffset, cards.ActionLength));
            return true;
        }
        if (ItemTransportRequestParser.TryParse(head, out var items))
        {
            request = new(Capability.Items, path, items.IsPost, items.AuthorizationOffset, 64,
                Text(head, items.DecisionOffset, items.DecisionLength), Text(head, items.ActionOffset, items.ActionLength));
            return true;
        }
        // Shop and event use different action alphabets on the same room routes.
        foreach (var selection in new[] { RoomFlowSelection.Shop, RoomFlowSelection.Event })
            if (RoomFlowTransportRequestParser.TryParse(head, selection, out var rooms))
            {
                request = new(Capability.Rooms, path, rooms.IsPost, rooms.AuthorizationOffset, 64,
                    Text(head, rooms.DecisionOffset, rooms.DecisionLength), Text(head, rooms.ActionOffset, rooms.ActionLength));
                return true;
            }
        var parsed = ProbeRequestParser.Parse(head);
        var core = parsed.Request;
        if (parsed.Status != ProbeRequestParseStatus.Parsed || core.RouteTarget == ParsedRouteTarget.Unknown ||
            core.HostState != ParsedHostState.Exact || core.HasOrigin || core.AuthorizationCount != 1 ||
            core.AuthorizationValueLength != 71 || !head.Slice(core.AuthorizationValueOffset, 7).SequenceEqual("Bearer "u8)) return false;
        bool action = core.RouteTarget is ParsedRouteTarget.PublicCombatAction or ParsedRouteTarget.PublicRewardAction or
            ParsedRouteTarget.PublicMapAction or ParsedRouteTarget.PublicRoomAction;
        if (action ? !core.IsPost || core.DecisionIdCount != 1 || core.ActionIdCount != 1 :
            !core.IsGet || core.DecisionIdCount != 0 || core.ActionIdCount != 0) return false;
        request = new(Capability.Core, path, action, core.AuthorizationValueOffset + 7, 64,
            Text(head, core.DecisionIdValueOffset, core.DecisionIdValueLength),
            Text(head, core.ActionIdValueOffset, core.ActionIdValueLength));
        return !action || CoreBridgeModule.IsValidAction(request);
    }
    private static string? Text(ReadOnlySpan<byte> source, int start, int length) =>
        length == 0 ? null : Encoding.ASCII.GetString(source.Slice(start, length));
}
