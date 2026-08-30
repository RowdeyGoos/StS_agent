namespace VerifierFixtures;

internal static class BadGodotOverload
{
    public static void Log(object value) => Godot.GD.Print(value);
}
