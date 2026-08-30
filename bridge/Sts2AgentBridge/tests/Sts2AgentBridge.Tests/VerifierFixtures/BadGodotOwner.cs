namespace VerifierFixtures;

internal static class BadGodotOwner
{
    public static void Log(string message) => Godot.GD.Print(message);
}
