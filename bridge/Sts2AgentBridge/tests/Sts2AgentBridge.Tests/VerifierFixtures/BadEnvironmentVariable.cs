namespace VerifierFixtures;

internal static class BadEnvironmentVariable
{
    public static string? Read() => System.Environment.GetEnvironmentVariable("STS2_BAD_FIXTURE");
}
