namespace VerifierFixtures;

internal static class BadNetworkAdjacentOverload
{
    public static int Receive(System.Net.Sockets.Socket socket, byte[] buffer) => socket.Receive(buffer);
}
