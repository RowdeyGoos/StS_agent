namespace VerifierFixtures;

internal static class BadEnvironmentCurrentDirectory
{
    public static string Read() => System.Environment.CurrentDirectory;
}
