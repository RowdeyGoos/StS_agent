namespace VerifierFixtures;

internal static class BadOutboundConnect
{
    public static void Connect(System.Net.Sockets.Socket socket) => socket.Connect("127.0.0.1", 43117);
}
