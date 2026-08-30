namespace VerifierFixtures;

internal static class BadFilesystemAdjacentOverload
{
    public static int ReadByte(System.IO.FileStream stream) => stream.ReadByte();
}
