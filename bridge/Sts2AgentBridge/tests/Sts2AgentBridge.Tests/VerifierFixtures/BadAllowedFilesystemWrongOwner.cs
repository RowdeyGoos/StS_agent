namespace VerifierFixtures;

internal static class BadAllowedFilesystemWrongOwner
{
    public static string Normalize(string path) => System.IO.Path.GetFullPath(path);
}
