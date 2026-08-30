namespace VerifierFixtures;

internal static class BadFileWrite
{
    public static void Write(string path) => System.IO.File.WriteAllText(path, "forbidden");
}
