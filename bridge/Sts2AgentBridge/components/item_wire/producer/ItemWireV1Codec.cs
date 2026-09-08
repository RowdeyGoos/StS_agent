using System;
using System.Globalization;
using System.Text;

namespace Sts2AgentBridge.Successors.ItemWireV1;

internal static class ItemWireV1Codec
{
    public static byte[] Encode(ItemWireV1Envelope envelope)
    {
        var builder = new StringBuilder(4096);
        builder.Append("{\"schema_version\":1,\"protocol\":\"item_probe_v1\",\"version\":\"item_v1\",\"session_nonce\":\"");
        builder.Append(envelope.SessionNonce);
        builder.Append("\",\"surface_ordinal\":1,\"status\":\"");
        builder.Append(envelope.Status);
        builder.Append('"');
        switch (envelope.Status)
        {
            case "waiting":
            case "unsupported":
            case "rejected":
            case "uncertain":
                break;
            case "ready":
                builder.Append(",\"decision_id\":\"");
                builder.Append(envelope.DecisionId);
                builder.Append("\",\"offers\":[");
                for (int index = 0; index < envelope.Offers.Count; index++)
                {
                    if (index > 0)
                    {
                        builder.Append(',');
                    }
                    ItemWireV1OfferDto offer = envelope.Offers[index];
                    builder.Append("{\"index\":");
                    builder.Append(offer.Index.ToString(CultureInfo.InvariantCulture));
                    builder.Append(",\"kind\":\"");
                    builder.Append(offer.Kind);
                    builder.Append("\",\"key\":\"");
                    builder.Append(offer.Key);
                    builder.Append("\",\"enabled\":");
                    builder.Append(offer.Enabled ? "true" : "false");
                    builder.Append('}');
                }
                builder.Append("],\"potion_slots\":[");
                for (int index = 0; index < envelope.PotionSlots.Count; index++)
                {
                    if (index > 0)
                    {
                        builder.Append(',');
                    }
                    string? slot = envelope.PotionSlots[index];
                    if (slot is null)
                    {
                        builder.Append("null");
                    }
                    else
                    {
                        builder.Append('"');
                        builder.Append(slot);
                        builder.Append('"');
                    }
                }
                builder.Append("],\"legal_actions\":[");
                for (int index = 0; index < envelope.LegalActions.Count; index++)
                {
                    if (index > 0)
                    {
                        builder.Append(',');
                    }
                    builder.Append('"');
                    builder.Append(envelope.LegalActions[index]);
                    builder.Append('"');
                }
                builder.Append(']');
                break;
            case "accepted":
                AppendCorrelation(builder, envelope);
                break;
            case "resolved":
                AppendCorrelation(builder, envelope);
                builder.Append(",\"offer_index\":");
                builder.Append(envelope.OfferIndex.ToString(CultureInfo.InvariantCulture));
                builder.Append(",\"kind\":\"");
                builder.Append(envelope.Kind);
                builder.Append("\",\"key\":\"");
                builder.Append(envelope.Key);
                builder.Append("\",\"result\":\"");
                builder.Append(envelope.Result);
                builder.Append('"');
                break;
            case "error":
                builder.Append(",\"code\":\"");
                builder.Append(envelope.Code);
                builder.Append('"');
                break;
            default:
                throw new InvalidOperationException("Unknown item response status.");
        }
        builder.Append('}');
        byte[] result = Encoding.UTF8.GetBytes(builder.ToString());
        if (result.Length > ItemWireV1Protocol.MaximumBodyBytes)
        {
            throw new InvalidOperationException("Item response exceeds the fixed body bound.");
        }
        return result;
    }

    public static byte[] EncodeFixedError(string nonce, string code)
    {
        string selected = code == "invalid_request" ? "invalid_request" : "internal_failure";
        string body =
            "{\"schema_version\":1,\"protocol\":\"item_probe_v1\",\"version\":\"item_v1\",\"session_nonce\":\"" +
            nonce +
            "\",\"surface_ordinal\":1,\"status\":\"error\",\"code\":\"" +
            selected + "\"}";
        return Encoding.ASCII.GetBytes(body);
    }

    private static void AppendCorrelation(StringBuilder builder, ItemWireV1Envelope envelope)
    {
        builder.Append(",\"decision_id\":\"");
        builder.Append(envelope.DecisionId);
        builder.Append("\",\"action_id\":\"");
        builder.Append(envelope.ActionId);
        builder.Append('"');
    }
}
