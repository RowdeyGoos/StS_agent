using System;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV6;
internal static class GenericEventTransportConfiguration
{
    private static ReadOnlySpan<byte> Document => "{\"schema_version\":\"generic_event_v6_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"generic\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;
    internal static bool TryParse(ReadOnlySpan<byte> value, out GenericEventReleaseSelection selection)
    { selection = value.SequenceEqual(Document) ? GenericEventReleaseSelection.Generic : default; return selection == GenericEventReleaseSelection.Generic; }
}
