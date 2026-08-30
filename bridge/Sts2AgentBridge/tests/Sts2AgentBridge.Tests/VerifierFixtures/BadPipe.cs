namespace VerifierFixtures;

internal static class BadPipe
{
    public static System.IO.Pipes.PipeStream Keep(System.IO.Pipes.PipeStream value) => value;
}
