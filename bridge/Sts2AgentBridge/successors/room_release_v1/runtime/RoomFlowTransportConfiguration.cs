using System;

namespace Sts2AgentBridge.Successors.RoomReleaseV1;

internal static class RoomFlowTransportConfiguration
{
    private static ReadOnlySpan<byte> ShopDocument =>
        "{\"schema_version\":\"room_flows_v1_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"shop\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    private static ReadOnlySpan<byte> EventDocument =>
        "{\"schema_version\":\"room_flows_v1_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"event\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    public static bool TryParse(ReadOnlySpan<byte> value, out RoomFlowSelection selection)
    {
        if (value.SequenceEqual(ShopDocument))
        {
            selection = RoomFlowSelection.Shop;
            return true;
        }
        if (value.SequenceEqual(EventDocument))
        {
            selection = RoomFlowSelection.Event;
            return true;
        }
        selection = default;
        return false;
    }
}
