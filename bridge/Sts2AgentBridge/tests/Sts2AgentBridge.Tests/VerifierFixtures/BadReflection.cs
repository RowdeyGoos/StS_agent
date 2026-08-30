namespace VerifierFixtures;

internal static class BadReflection
{
    public static string Location() => typeof(string).Assembly.Location;
}
