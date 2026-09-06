using System;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

internal static class ShopDiagnosticTransportConfiguration
{
    private static ReadOnlySpan<byte> EnabledDocument =>
        "{\"schema_version\":\"shop_diagnostic_v1_transport_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    public static bool IsEnabled(ReadOnlySpan<byte> value) => value.SequenceEqual(EnabledDocument);
}
