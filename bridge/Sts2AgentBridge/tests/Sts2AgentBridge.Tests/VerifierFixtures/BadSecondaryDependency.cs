namespace VerifierFixtures;

internal static class BadSecondaryDependency
{
    public static int Read() => VerifierBadDependency.Marker.Value;
}
