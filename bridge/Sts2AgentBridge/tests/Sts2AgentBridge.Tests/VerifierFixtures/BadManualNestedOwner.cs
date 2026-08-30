namespace VerifierFixtures;

internal static class BadManualNestedOwner
{
    internal sealed class ManualState
    {
        public static void DisposeSocket(System.Net.Sockets.Socket socket) => socket.Dispose();
    }
}
