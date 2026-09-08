using System;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal static class CardSelectionTransportConfiguration
{
    private static ReadOnlySpan<byte> CheeseDocument =>
        "{\"schema_version\":\"card_selection_v1_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"cheese\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    private static ReadOnlySpan<byte> SmithDocument =>
        "{\"schema_version\":\"card_selection_v1_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"smith\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    internal static bool TryParse(ReadOnlySpan<byte> value, out CardSelectionReleaseSelection selection)
    {
        if (value.SequenceEqual(CheeseDocument))
        {
            selection = CardSelectionReleaseSelection.Cheese;
            return true;
        }
        if (value.SequenceEqual(SmithDocument))
        {
            selection = CardSelectionReleaseSelection.Smith;
            return true;
        }
        selection = default;
        return false;
    }
}
