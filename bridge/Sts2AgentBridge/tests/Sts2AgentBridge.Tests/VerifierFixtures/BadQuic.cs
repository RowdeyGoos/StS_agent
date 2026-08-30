#pragma warning disable CA2252
namespace VerifierFixtures;

internal static class BadQuic
{
    public static System.Net.Quic.QuicConnection Keep(System.Net.Quic.QuicConnection value) => value;
}
