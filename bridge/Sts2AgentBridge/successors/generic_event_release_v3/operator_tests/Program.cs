using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Versioning;
using System.Text;
using Sts2AgentBridge.Successors.ItemBootstrapV1;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV3;

[SupportedOSPlatform("macos")]
internal static class Program
{
    private static readonly byte[] Generic = Encoding.ASCII.GetBytes(
        "{\"schema_version\":\"generic_event_v3_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"generic\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static readonly byte[] Credential = Encoding.ASCII.GetBytes(new string('a', 64));
    private static string _root = string.Empty;
    private static int _checks;

    internal static int Main(string[] arguments)
    {
        if (arguments.Length != 2 || arguments[0] != "--fixture-root" ||
            !GenericEventOperatorFiles.IsSyntheticHomeForTests(arguments[1]) ||
            Directory.Exists(arguments[1]) || File.Exists(arguments[1]))
            return 2;
        _root = arguments[1];
        try
        {
            Run(() => ExactEnabled(Generic));

            Run(DefaultDenyAndIsolation);
            Run(CredentialReservationAndBinding);
            Run(LeaseCleanupAndSurface);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"generic_event_v3_operator\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch
        {
            Console.Error.WriteLine("generic_event_v3_operator_tests_failed");
            return 1;
        }
        finally
        {
            Array.Clear(Generic); Array.Clear(Credential);
            try { if (Directory.Exists(_root)) Directory.Delete(_root, true); } catch { }
        }
    }

    private static void Run(Action action)
    {
        Reset(); action(); _checks++;
    }

    private static void ExactEnabled(byte[] expected)
    {
        Write(ConfigPath, expected);
        using ItemOperatorConfiguration lease = Present(GenericEventOperatorFiles.OpenEnabledForTests(_root));
        byte[] credential = Present(lease.ReadCredentialOnce());
        byte[] configuration = Present(lease.TakeConfiguration());
        Require(credential.SequenceEqual(Credential) && configuration.SequenceEqual(expected));
        Require(lease.ReadCredentialOnce() is null && lease.TakeConfiguration() is null);
        lease.Dispose();
        Require(credential.SequenceEqual(Credential) && configuration.SequenceEqual(expected));
        Array.Clear(credential); Array.Clear(configuration);
    }

    private static void DefaultDenyAndIsolation()
    {
        byte[][] rejected =
        {
            Encoding.ASCII.GetBytes("{\"schema_version\":\"generic_event_v3_transport_config_v1\",\"enabled\":false,\"flow_kind\":\"generic\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"),
            Encoding.ASCII.GetBytes("{\"schema_version\":\"generic_event_v3_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"rest\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"),
            Encoding.ASCII.GetBytes("{\"schema_version\":\"item_probe_v1_transport_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"),
            Generic.Concat(new byte[] { (byte)'\n' }).ToArray(),
        };
        foreach (byte[] value in rejected)
        {
            Write(ConfigPath, value);
            Require(GenericEventOperatorFiles.OpenEnabledForTests(_root) is null);
            Array.Clear(value);
        }
        File.Delete(ConfigPath);
        Require(GenericEventOperatorFiles.OpenEnabledForTests(_root) is null);

        string item = Path.Combine(BridgePath, "item_v1");
        Directory.CreateDirectory(item); File.SetUnixFileMode(item, DirectoryMode);
        Write(Path.Combine(item, "config.json"), Generic);
        Write(Path.Combine(item, "credential.hex"), Credential);
        Require(GenericEventOperatorFiles.OpenEnabledForTests(_root) is null);
    }

    private static void CredentialReservationAndBinding()
    {
        using ItemOperatorConfiguration invalid = Present(GenericEventOperatorFiles.OpenEnabledForTests(_root));
        Write(CredentialPath, Encoding.ASCII.GetBytes(new string('A', 64)));
        Require(invalid.ReadCredentialOnce() is null && invalid.ReadCredentialOnce() is null);

        Reset();
        ItemOperatorConfiguration replaced = Present(GenericEventOperatorFiles.OpenEnabledForTests(_root));
        string old = ConfigPath + ".old";
        File.Move(ConfigPath, old); Write(ConfigPath, Generic);
        Require(replaced.ReadCredentialOnce() is null && replaced.ReadCredentialOnce() is null);
        byte[] retained = Present(replaced.TakeConfiguration());
        Require(retained.SequenceEqual(Generic));
        Array.Clear(retained); replaced.Dispose();
    }

    private static void LeaseCleanupAndSurface()
    {
        ItemOperatorConfiguration lease = Present(GenericEventOperatorFiles.OpenEnabledForTests(_root));
        byte[] retained = Present(lease.RetainedConfigurationForTests);
        lease.Dispose(); lease.Dispose();
        Require(retained.All(value => value == 0));
        string[] methods = typeof(GenericEventOperatorFiles).GetMethods(
            BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
            .Select(method => method.Name).OrderBy(name => name, StringComparer.Ordinal).ToArray();
        Require(methods.SequenceEqual(new[] { "CloseAndNull", "FixedEquals", "IsExactEnabled", "IsSyntheticHome", "IsSyntheticHomeForTests", "OpenBelowHome", "OpenEnabled", "OpenEnabledForTests", "OpenFromAbsoluteHome", "get_GenericEnabled" }));
        Require(!GenericEventOperatorFiles.IsSyntheticHomeForTests("/private/tmp/a/b") &&
            !GenericEventOperatorFiles.IsSyntheticHomeForTests("/tmp/card-selection"));
    }

    private static void Reset()
    {
        if (Directory.Exists(_root)) Directory.Delete(_root, true);
        Directory.CreateDirectory(RoomPath);
        foreach (string path in new[] { _root, Path.Combine(_root, "Library"),
                     Path.Combine(_root, "Library", "Application Support"), BridgePath, RoomPath })
            File.SetUnixFileMode(path, DirectoryMode);
        Write(ConfigPath, Generic); Write(CredentialPath, Credential);
    }

    private static void Write(string path, byte[] value)
    {
        if (File.Exists(path)) File.Delete(path);
        File.WriteAllBytes(path, value); File.SetUnixFileMode(path, FileMode);
    }

    private static T Present<T>(T? value) where T : class => value ?? throw new InvalidOperationException();
    private static void Require(bool value) { if (!value) throw new InvalidOperationException(); }
    private static string BridgePath => Path.Combine(_root, "Library", "Application Support", "Sts2AgentBridge");
    private static string RoomPath => Path.Combine(BridgePath, "generic_event_v3");
    private static string ConfigPath => Path.Combine(RoomPath, "config.json");
    private static string CredentialPath => Path.Combine(RoomPath, "credential.hex");
    private const UnixFileMode DirectoryMode = UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute;
    private const UnixFileMode FileMode = UnixFileMode.UserRead | UnixFileMode.UserWrite;
}
