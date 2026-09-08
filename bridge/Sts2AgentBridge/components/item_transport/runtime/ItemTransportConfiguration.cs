using System;

namespace Sts2AgentBridge.Successors.ItemTransportV1;

internal enum ItemTransportConfigurationState
{
    Invalid = 0,
    Enabled = 1,
    Disabled = 2,
}

internal static class ItemTransportConfiguration
{
    private static ReadOnlySpan<byte> EnabledDocument =>
        "{\"schema_version\":\"item_probe_v1_transport_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    private static ReadOnlySpan<byte> DisabledDocument =>
        "{\"schema_version\":\"item_probe_v1_transport_config_v1\",\"enabled\":false,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    public static ItemTransportConfigurationState Parse(ReadOnlySpan<byte> value)
    {
        if (value.SequenceEqual(EnabledDocument))
        {
            return ItemTransportConfigurationState.Enabled;
        }
        if (value.SequenceEqual(DisabledDocument))
        {
            return ItemTransportConfigurationState.Disabled;
        }
        return ItemTransportConfigurationState.Invalid;
    }
}
