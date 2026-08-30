namespace VerifierFixtures;

internal static class BadAllowedNetworkWrongOwner
{
    public static void Read() => _ = System.Net.IPAddress.Loopback;
}
