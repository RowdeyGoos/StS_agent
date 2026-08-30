#pragma warning disable SYSLIB1054
namespace VerifierFixtures;

internal static class BadPInvoke
{
    [System.Runtime.InteropServices.DllImport("forbidden")]
    private static extern int Invoke();

    public static int Run() => Invoke();
}
