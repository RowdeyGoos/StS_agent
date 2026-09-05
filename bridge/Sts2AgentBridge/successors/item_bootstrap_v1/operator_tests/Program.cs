using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1.OperatorTests;

[SupportedOSPlatform("macos")]
internal static class Program
{
    private static readonly byte[] Enabled = Encoding.ASCII.GetBytes(
        "{\"schema_version\":\"item_probe_v1_transport_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static readonly byte[] Disabled = Encoding.ASCII.GetBytes(
        "{\"schema_version\":\"item_probe_v1_transport_config_v1\",\"enabled\":false,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static readonly byte[] Credential = Encoding.ASCII.GetBytes(new string('b', 64));
    private static int _checks;
    private static string _root = string.Empty;

    public static int Main(string[] args)
    {
        if (args.Length != 2 || args[0] != "--fixture-root" ||
            !ItemOperatorFiles.IsSyntheticHomeForTests(args[1]) || Directory.Exists(args[1]) || File.Exists(args[1]))
            return 2;
        _root = args[1];
        try
        {
            Directory.CreateDirectory(_root);
            File.SetUnixFileMode(_root, PrivateDirectoryMode);
            Run(LayoutAndApi);
            Run(ActualSuccessAndOwnership);
            Run(ConfigurationRejections);
            Run(FilesystemRejections);
            Run(ActualNonBlockingFifo);
            Run(ActualAclPolicy);
            Run(CredentialRevalidationAndReservation);
            Run(MetadataAndReadMutation);
            Run(EintrBounds);
            Run(CleanupFailures);
            Run(PinnedIdentity);
            Run(HomeAndPathValidation);
            Run(AclBoundsAndCanaries);
            Console.WriteLine(
                "{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"item_v1_operator\",\"check_count\":" +
                _checks + "}");
            return 0;
        }
        catch
        {
            Console.Error.WriteLine("item_v1_operator_tests_failed");
            return 1;
        }
        finally
        {
            DarwinReadOnly.Zero(Enabled);
            DarwinReadOnly.Zero(Disabled);
            DarwinReadOnly.Zero(Credential);
            TryRemoveAcl(ConfigPath);
            try
            {
                if (Directory.Exists(_root))
                    Directory.Delete(_root, true);
            }
            catch
            {
            }
        }
    }

    private static void Run(Action check)
    {
        ResetTree();
        check();
        _checks++;
    }

    private static void LayoutAndApi()
    {
        Require(Marshal.SizeOf<DarwinTimespec>() == 16, "timespec layout");
        Require(Marshal.SizeOf<DarwinStat>() == 144, "stat layout");
        Require(Marshal.SizeOf<DarwinPasswd>() == 72, "passwd layout");
        Require(Marshal.OffsetOf<DarwinStat>(nameof(DarwinStat.Mode)).ToInt32() == 4, "mode offset");
        Require(Marshal.OffsetOf<DarwinStat>(nameof(DarwinStat.Inode)).ToInt32() == 8, "inode offset");
        Require(Marshal.OffsetOf<DarwinStat>(nameof(DarwinStat.ModificationTime)).ToInt32() == 48, "mtime offset");
        Require(Marshal.OffsetOf<DarwinStat>(nameof(DarwinStat.Size)).ToInt32() == 96, "size offset");
        Require(Marshal.OffsetOf<DarwinPasswd>(nameof(DarwinPasswd.Directory)).ToInt32() == 48, "home offset");
        Require(!ItemOperatorFiles.IsSyntheticHomeForTests("/private/tmp/x/y"), "nested seam rejected");
        Require(!ItemOperatorFiles.IsSyntheticHomeForTests("/tmp/operator"), "alternate root rejected");

        string[] configMethods = typeof(ItemOperatorConfiguration)
            .GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
            .Select(method => method.Name)
            .OrderBy(name => name, StringComparer.Ordinal)
            .ToArray();
        Require(configMethods.SequenceEqual(new[] { "Dispose", "ReadCredentialOnce", "TakeConfiguration", "get_RetainedConfigurationForTests" }), "lease API");
        Require(typeof(ItemOperatorConfiguration).GetFields(BindingFlags.Instance | BindingFlags.Public).Length == 0,
            "no public fields");
    }

    private static void ActualSuccessAndOwnership()
    {
        ItemOperatorConfiguration lease = Present(ItemOperatorFiles.OpenEnabledForTests(_root), "enabled open");
        byte[] credential = Present(lease.ReadCredentialOnce(), "credential exact");
        byte[] configuration = Present(lease.TakeConfiguration(), "configuration exact");
        Require(credential.SequenceEqual(Credential), "credential exact");
        Require(configuration.SequenceEqual(Enabled), "configuration exact");
        Require(lease.ReadCredentialOnce() is null && lease.TakeConfiguration() is null, "one shot transfers");
        lease.Dispose();
        lease.Dispose();
        Require(credential.SequenceEqual(Credential) && configuration.SequenceEqual(Enabled), "transferred ownership retained");
        Array.Clear(credential);
        Array.Clear(configuration);

        lease = Present(ItemOperatorFiles.OpenEnabledForTests(_root), "second independent lease");
        byte[] retained = Present(lease.RetainedConfigurationForTests, "retained config seam");
        lease.Dispose();
        Require(retained.All(value => value == 0), "untransferred config zeroed");

        lease = Present(ItemOperatorFiles.OpenEnabledForTests(_root), "third independent lease");
        byte[] taken = Present(lease.TakeConfiguration(), "take before dispose");
        lease.Dispose();
        Require(taken.SequenceEqual(Enabled), "take before dispose");
        Array.Clear(taken);
    }

    private static void ConfigurationRejections()
    {
        WritePrivate(ConfigPath, Disabled);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "disabled rejected");
        WritePrivate(ConfigPath, Encoding.ASCII.GetBytes(
            "{\"schema_version\":\"live_probe_v0_config_v1\",\"enabled\":true}"));
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "old schema rejected");
        byte[] newline = Enabled.Concat(new byte[] { (byte)'\n' }).ToArray();
        WritePrivate(ConfigPath, newline);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "newline rejected");
        Array.Clear(newline);
        WritePrivate(ConfigPath, new byte[513]);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "oversize rejected");
        WritePrivate(ConfigPath, Array.Empty<byte>());
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "empty rejected");
        File.Delete(ConfigPath);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "missing rejected");
    }

    private static void FilesystemRejections()
    {
        File.SetUnixFileMode(BridgePath,
            UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute |
            UnixFileMode.GroupRead | UnixFileMode.GroupExecute);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "bridge exact mode");
        File.SetUnixFileMode(BridgePath, PrivateDirectoryMode);

        File.SetUnixFileMode(ConfigPath, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.GroupRead);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "config exact mode");
        File.SetUnixFileMode(ConfigPath, PrivateFileMode);

        string real = ConfigPath + ".real";
        File.Move(ConfigPath, real);
        File.CreateSymbolicLink(ConfigPath, real);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "symlink rejected");
        File.Delete(ConfigPath);
        File.Move(real, ConfigPath);

        File.Delete(ConfigPath);
        Directory.CreateDirectory(ConfigPath);
        File.SetUnixFileMode(ConfigPath, PrivateDirectoryMode);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "nonregular rejected");
        Directory.Delete(ConfigPath);
    }

    private static void ActualAclPolicy()
    {
        RunChmod("+a", "everyone deny writeextattr", ConfigPath);
        using (ItemOperatorConfiguration? lease = ItemOperatorFiles.OpenEnabledForTests(_root))
            Require(lease is not null, "deny ACL accepted");
        RunChmod("-a#", "0", ConfigPath);

        RunChmod("+a", "everyone allow read", ConfigPath);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root) is null, "allow ACL rejected");
        RunChmod("-a#", "0", ConfigPath);
    }

    private static void ActualNonBlockingFifo()
    {
        string fifo = Path.Combine(_root, "fifo");
        RunMkfifo(fifo);
        var native = new FifoTrackingNative(LibSystemDarwinReadOnlyNative.Instance);
        Require(DarwinReadOnly.TryGetIdentity(native, out uint effectiveUserId), "fifo identity");
        var stopwatch = Stopwatch.StartNew();
        Task<bool> attempt = Task.Run(() =>
        {
            var descriptors = new DarwinDescriptorLease(native, effectiveUserId);
            try
            {
                if (!descriptors.TryOpenSyntheticHome(_root))
                    return true;
                return descriptors.TryOpenFile(
                    "fifo", DarwinDescriptorPolicy.PrivateFile, out HeldDescriptor? _);
            }
            finally
            {
                _ = descriptors.CloseAll();
            }
        });
        Require(attempt.Wait(TimeSpan.FromSeconds(2)), "fifo open bounded");
        stopwatch.Stop();
        Require(!attempt.Result && stopwatch.Elapsed < TimeSpan.FromSeconds(2), "fifo nonregular rejected");
        int expectedFlags = DarwinReadOnly.OpenReadOnly | DarwinReadOnly.OpenNonBlocking |
            DarwinReadOnly.OpenCloseOnExec | DarwinReadOnly.OpenNoFollow;
        Require(native.FifoOpened && native.FifoFlags == expectedFlags && native.FifoCloseCount == 1,
            "fifo nonblocking flags and close");
        File.Delete(fifo);
    }

    private static void CredentialRevalidationAndReservation()
    {
        ItemOperatorConfiguration lease = Present(
            ItemOperatorFiles.OpenEnabledForTests(_root), "open before replacement");
        string old = ConfigPath + ".old";
        File.Move(ConfigPath, old);
        WritePrivate(ConfigPath, Enabled);
        Require(lease.ReadCredentialOnce() is null, "parent-name replacement rejected");
        Require(lease.ReadCredentialOnce() is null, "failed credential attempt reserved");
        byte[] configuration = Present(lease.TakeConfiguration(), "config transfer remains exact");
        Require(configuration.SequenceEqual(Enabled), "config transfer remains exact");
        Array.Clear(configuration);
        lease.Dispose();
        File.Delete(ConfigPath);
        File.Move(old, ConfigPath);

        lease = Present(ItemOperatorFiles.OpenEnabledForTests(_root), "open before invalid credential");
        WritePrivate(CredentialPath, Encoding.ASCII.GetBytes(new string('B', 64)));
        Require(lease.ReadCredentialOnce() is null && lease.ReadCredentialOnce() is null, "uppercase and retry rejected");
        lease.Dispose();

        foreach (int length in new[] { 63, 65 })
        {
            WritePrivate(CredentialPath, Enumerable.Repeat((byte)'b', length).ToArray());
            lease = Present(ItemOperatorFiles.OpenEnabledForTests(_root), "open before credential length");
            Require(lease.ReadCredentialOnce() is null, "credential length rejected");
            lease.Dispose();
        }
        File.Delete(CredentialPath);
        lease = Present(ItemOperatorFiles.OpenEnabledForTests(_root), "open before missing credential");
        Require(lease.ReadCredentialOnce() is null, "missing credential rejected");
        lease.Dispose();
    }

    private static void MetadataAndReadMutation()
    {
        var mutated = new MutatingStatNative(LibSystemDarwinReadOnlyNative.Instance, mutateAtConfigStatCall: 3);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, mutated) is null, "read mutation rejected");
        Require(mutated.CloseCount == 6, "mutation cleanup complete");

        var wrongOwner = new MutatingStatNative(LibSystemDarwinReadOnlyNative.Instance, mutateAtConfigStatCall: 1)
        {
            Mutation = static stat => { stat.UserId = uint.MaxValue; return stat; },
        };
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, wrongOwner) is null, "wrong owner rejected");

        var special = new MutatingStatNative(LibSystemDarwinReadOnlyNative.Instance, mutateAtConfigStatCall: 1)
        {
            Mutation = static stat => { stat.Mode = (ushort)((stat.Mode & 0x0fff) | DarwinReadOnly.DirectoryType); return stat; },
        };
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, special) is null, "special type rejected");

        var linked = new MutatingStatNative(LibSystemDarwinReadOnlyNative.Instance, mutateAtConfigStatCall: 1)
        {
            Mutation = static stat => { stat.LinkCount = 2; return stat; },
        };
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, linked) is null, "hard link count rejected");
    }

    private static void EintrBounds()
    {
        var eight = new InterruptingNative(LibSystemDarwinReadOnlyNative.Instance, 8);
        using (ItemOperatorConfiguration? lease = ItemOperatorFiles.OpenEnabledForTests(_root, eight))
            Require(lease is not null && eight.Interruptions == 8, "eight EINTR retries accepted");

        var nine = new InterruptingNative(LibSystemDarwinReadOnlyNative.Instance, 9);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, nine) is null && nine.Interruptions == 9,
            "ninth EINTR fails");

        var openEight = new InterruptingOpenNative(LibSystemDarwinReadOnlyNative.Instance, 8);
        using (ItemOperatorConfiguration? lease = ItemOperatorFiles.OpenEnabledForTests(_root, openEight))
            Require(lease is not null && openEight.Interruptions == 8, "open EINTR bound");
    }

    private static void CleanupFailures()
    {
        var closing = new CloseFailureNative(LibSystemDarwinReadOnlyNative.Instance);
        ItemOperatorConfiguration lease = Present(
            ItemOperatorFiles.OpenEnabledForTests(_root, closing), "open with deferred close failure");
        byte[]? credential = lease.ReadCredentialOnce();
        Require(credential is null, "close failure rejects credential");
        Require(closing.CloseCount == 7, "all descriptors close despite failure");
        lease.Dispose();

        var free = new AclNative(LibSystemDarwinReadOnlyNative.Instance, DarwinReadOnly.AclExtendedDeny, 1)
        {
            FailFree = true,
        };
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, free) is null && free.FreeCount == 1,
            "acl free failure rejected");
    }

    private static void PinnedIdentity()
    {
        string path = Path.Combine(_root, "pinned.bin");
        byte[] contents = Encoding.ASCII.GetBytes("synthetic-pinned-image");
        WritePrivate(path, contents);
        string digest = Convert.ToHexString(SHA256.HashData(contents)).ToLowerInvariant();
        Require(ItemPinnedFileIdentity.VerifyForTests(_root, "pinned.bin", contents.Length, digest),
            "synthetic pinned identity");
        Require(!ItemPinnedFileIdentity.VerifyForTests(_root, "pinned.bin", contents.Length + 1, digest),
            "pinned length mismatch");
        Require(!ItemPinnedFileIdentity.VerifyForTests(_root, "pinned.bin", contents.Length, new string('0', 64)),
            "pinned digest mismatch");
        Require(!ItemPinnedFileIdentity.Verify("/does/not/exist/sts2.dll", 1, new string('0', 64)),
            "arbitrary production tuple rejected early");
        Array.Clear(contents);
    }

    private static void HomeAndPathValidation()
    {
        Require(DarwinReadOnly.TryParseAbsolutePath("/Users/example", out string[] components) &&
            components.SequenceEqual(new[] { "Users", "example" }), "canonical home");
        foreach (string invalid in new[] { "relative", "/Users//example", "/Users/./example", "/Users/../example", "/Users/example/", "/Users/ex\nample" })
            Require(!DarwinReadOnly.TryParseAbsolutePath(invalid, out _), "invalid home");
        Require(!DarwinReadOnly.TryParseAbsolutePath("/" + new string('x', 256), out _), "component bound");

        var password = new PasswordNative("/Users/example", 501);
        Require(DarwinReadOnly.TryResolveHome(password, 501, out components) &&
            components.SequenceEqual(new[] { "Users", "example" }), "passwd home extraction");
        Require(password.PasswordCalls == 1, "single passwd lookup");
        password.ReturnedUserId = 502;
        Require(!DarwinReadOnly.TryResolveHome(password, 501, out _), "passwd uid mismatch");
        password.ReturnOutsideBuffer = true;
        Require(!DarwinReadOnly.TryResolveHome(password, 501, out _), "passwd pointer bound");

        var invalidUtf8 = new PasswordNative(new byte[] { (byte)'/', 0xff }, 501);
        Require(!DarwinReadOnly.TryResolveHome(invalidUtf8, 501, out _), "passwd UTF-8 rejected");
        var missingNul = new PasswordNative(Encoding.ASCII.GetBytes("/Users/example"), 501)
        {
            OmitTerminator = true,
        };
        Require(!DarwinReadOnly.TryResolveHome(missingNul, 501, out _), "passwd terminator required");
        byte[] overBoundHome = Enumerable.Repeat((byte)'x', 1025).ToArray();
        overBoundHome[0] = (byte)'/';
        var overBound = new PasswordNative(overBoundHome, 501);
        Require(!DarwinReadOnly.TryResolveHome(overBound, 501, out _), "passwd 1024-byte bound");
        Array.Clear(overBoundHome);

        var ancestor = new DarwinStat { Mode = DarwinReadOnly.DirectoryType | 0x1ed, UserId = 0 };
        Require(DarwinDescriptorLease.ValidatePolicy(ancestor, DarwinDescriptorPolicy.AncestorDirectory, 501),
            "root-owned ancestor accepted");
        ancestor.UserId = 502;
        Require(!DarwinDescriptorLease.ValidatePolicy(ancestor, DarwinDescriptorPolicy.AncestorDirectory, 501),
            "foreign ancestor rejected");
        ancestor.UserId = 501;
        ancestor.Mode |= 0x10;
        Require(!DarwinDescriptorLease.ValidatePolicy(ancestor, DarwinDescriptorPolicy.AncestorDirectory, 501),
            "writable ancestor rejected");
        ancestor.Mode = DarwinReadOnly.DirectoryType | 0x9ed;
        Require(!DarwinDescriptorLease.ValidatePolicy(ancestor, DarwinDescriptorPolicy.AncestorDirectory, 501),
            "special-bit ancestor rejected");
    }

    private static void AclBoundsAndCanaries()
    {
        var deny = new AclNative(LibSystemDarwinReadOnlyNative.Instance, DarwinReadOnly.AclExtendedDeny, 169);
        using (ItemOperatorConfiguration? lease = ItemOperatorFiles.OpenEnabledForTests(_root, deny))
            Require(lease is not null, "169 deny ACL entries accepted");
        Require(deny.FreeCount > 0, "ACL allocations freed");

        var tooMany = new AclNative(LibSystemDarwinReadOnlyNative.Instance, DarwinReadOnly.AclExtendedDeny, 170);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, tooMany) is null, "170th ACL entry rejected");

        var allow = new AclNative(LibSystemDarwinReadOnlyNative.Instance, DarwinReadOnly.AclExtendedAllow, 1);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, allow) is null, "injected allow rejected");

        var throwing = new ThrowingNative(LibSystemDarwinReadOnlyNative.Instance);
        Require(ItemOperatorFiles.OpenEnabledForTests(_root, throwing) is null, "native exception contained");
    }

    private static void ResetTree()
    {
        TryRemoveAcl(ConfigPath);
        foreach (string child in Directory.EnumerateFileSystemEntries(_root))
        {
            try
            {
                File.SetUnixFileMode(child, PrivateDirectoryMode);
            }
            catch
            {
            }
            if (Directory.Exists(child) && !File.GetAttributes(child).HasFlag(FileAttributes.ReparsePoint))
                Directory.Delete(child, true);
            else
                File.Delete(child);
        }
        Directory.CreateDirectory(LibraryPath);
        Directory.CreateDirectory(ApplicationSupportPath);
        Directory.CreateDirectory(BridgePath);
        Directory.CreateDirectory(ItemPath);
        File.SetUnixFileMode(_root, PrivateDirectoryMode);
        File.SetUnixFileMode(LibraryPath, PrivateDirectoryMode);
        File.SetUnixFileMode(ApplicationSupportPath, PrivateDirectoryMode);
        File.SetUnixFileMode(BridgePath, PrivateDirectoryMode);
        File.SetUnixFileMode(ItemPath, PrivateDirectoryMode);
        WritePrivate(ConfigPath, Enabled);
        WritePrivate(CredentialPath, Credential);
    }

    private static void WritePrivate(string path, byte[] bytes)
    {
        File.WriteAllBytes(path, bytes);
        File.SetUnixFileMode(path, PrivateFileMode);
    }

    private static void RunChmod(string operation, string acl, string path)
    {
        var start = new ProcessStartInfo("/bin/chmod")
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        start.ArgumentList.Add(operation);
        start.ArgumentList.Add(acl);
        start.ArgumentList.Add(path);
        using Process? process = Process.Start(start);
        if (process is null)
            throw new InvalidOperationException();
        if (!WaitForExitOrKill(process))
            throw new InvalidOperationException();
        _ = process.StandardOutput.ReadToEnd();
        _ = process.StandardError.ReadToEnd();
        Require(process.ExitCode == 0, "synthetic ACL setup");
    }

    private static void RunMkfifo(string path)
    {
        var start = new ProcessStartInfo("/usr/bin/mkfifo")
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        start.ArgumentList.Add("-m");
        start.ArgumentList.Add("600");
        start.ArgumentList.Add(path);
        using Process? process = Process.Start(start);
        if (process is null)
            throw new InvalidOperationException();
        if (!WaitForExitOrKill(process))
            throw new InvalidOperationException();
        _ = process.StandardOutput.ReadToEnd();
        _ = process.StandardError.ReadToEnd();
        Require(process.ExitCode == 0, "synthetic FIFO setup");
    }

    private static bool WaitForExitOrKill(Process process)
    {
        if (process.WaitForExit(2000))
            return true;
        try
        {
            process.Kill(entireProcessTree: true);
            _ = process.WaitForExit(1000);
        }
        catch
        {
        }
        return false;
    }

    private static void TryRemoveAcl(string path)
    {
        if (string.IsNullOrEmpty(path) || !File.Exists(path))
            return;
        try
        {
            RunChmod("-a#", "0", path);
        }
        catch
        {
        }
    }

    private static void Require(bool condition, string label)
    {
        if (!condition)
            throw new InvalidOperationException(label);
    }

    private static T Present<T>(T? value, string label) where T : class
    {
        if (value is null)
            throw new InvalidOperationException(label);
        return value;
    }

    private static UnixFileMode PrivateDirectoryMode =>
        UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute;
    private static UnixFileMode PrivateFileMode => UnixFileMode.UserRead | UnixFileMode.UserWrite;
    private static string LibraryPath => Path.Combine(_root, "Library");
    private static string ApplicationSupportPath => Path.Combine(LibraryPath, "Application Support");
    private static string BridgePath => Path.Combine(ApplicationSupportPath, "Sts2AgentBridge");
    private static string ItemPath => Path.Combine(BridgePath, "item_v1");
    private static string ConfigPath => Path.Combine(ItemPath, "config.json");
    private static string CredentialPath => Path.Combine(ItemPath, "credential.hex");
}

internal class ForwardingNative : IDarwinReadOnlyNative
{
    protected ForwardingNative(IDarwinReadOnlyNative inner) => Inner = inner;
    protected IDarwinReadOnlyNative Inner { get; }
    protected int SyntheticError { get; set; }
    public virtual int LastError => SyntheticError != 0 ? SyntheticError : Inner.LastError;
    public virtual uint GetUserId() => Inner.GetUserId();
    public virtual uint GetEffectiveUserId() => Inner.GetEffectiveUserId();
    public virtual int GetPasswordRecord(uint uid, IntPtr record, IntPtr buffer, nuint bufferSize, IntPtr result) => Inner.GetPasswordRecord(uid, record, buffer, bufferSize, result);
    public virtual int Open(IntPtr path, int flags) => Inner.Open(path, flags);
    public virtual int OpenAt(int directory, IntPtr path, int flags) => Inner.OpenAt(directory, path, flags);
    public virtual int FileStat(int descriptor, out DarwinStat stat) => Inner.FileStat(descriptor, out stat);
    public virtual int FileStatAt(int directory, IntPtr path, out DarwinStat stat, int flags) => Inner.FileStatAt(directory, path, out stat, flags);
    public virtual nint Read(int descriptor, IntPtr buffer, nuint count) => Inner.Read(descriptor, buffer, count);
    public virtual int Close(int descriptor) => Inner.Close(descriptor);
    public virtual IntPtr GetAcl(int descriptor, int type) => Inner.GetAcl(descriptor, type);
    public virtual int GetAclEntry(IntPtr acl, int entryId, out IntPtr entry) => Inner.GetAclEntry(acl, entryId, out entry);
    public virtual int GetAclTag(IntPtr entry, out int tag) => Inner.GetAclTag(entry, out tag);
    public virtual int FreeAcl(IntPtr acl) => Inner.FreeAcl(acl);
}

internal sealed class InterruptingNative : ForwardingNative
{
    private readonly int _target;
    internal InterruptingNative(IDarwinReadOnlyNative inner, int target) : base(inner) => _target = target;
    internal int Interruptions { get; private set; }
    public override nint Read(int descriptor, IntPtr buffer, nuint count)
    {
        if (Interruptions < _target)
        {
            Interruptions++;
            SyntheticError = DarwinReadOnly.Interrupted;
            return -1;
        }
        SyntheticError = 0;
        return base.Read(descriptor, buffer, count);
    }
}

internal sealed class InterruptingOpenNative : ForwardingNative
{
    private readonly int _target;
    internal InterruptingOpenNative(IDarwinReadOnlyNative inner, int target) : base(inner) => _target = target;
    internal int Interruptions { get; private set; }
    public override int Open(IntPtr path, int flags)
    {
        if (Interruptions < _target)
        {
            Interruptions++;
            SyntheticError = DarwinReadOnly.Interrupted;
            return -1;
        }
        SyntheticError = 0;
        return base.Open(path, flags);
    }
}

internal sealed class CloseFailureNative : ForwardingNative
{
    internal CloseFailureNative(IDarwinReadOnlyNative inner) : base(inner) { }
    internal int CloseCount { get; private set; }
    public override int Close(int descriptor)
    {
        CloseCount++;
        int actual = base.Close(descriptor);
        return CloseCount == 1 && actual == 0 ? -1 : actual;
    }
}

internal sealed class MutatingStatNative : ForwardingNative
{
    private readonly int _mutateAt;
    private int _configDescriptor = -1;
    private int _configStats;
    internal MutatingStatNative(IDarwinReadOnlyNative inner, int mutateAtConfigStatCall) : base(inner)
    {
        _mutateAt = mutateAtConfigStatCall;
        Mutation = static stat => { stat.ChangeTime.Nanoseconds++; return stat; };
    }
    internal Func<DarwinStat, DarwinStat> Mutation { get; init; }
    internal int CloseCount { get; private set; }
    public override int OpenAt(int directory, IntPtr path, int flags)
    {
        int descriptor = base.OpenAt(directory, path, flags);
        if (descriptor >= 0 && Marshal.PtrToStringUTF8(path) == "config.json")
            _configDescriptor = descriptor;
        return descriptor;
    }
    public override int FileStat(int descriptor, out DarwinStat stat)
    {
        int rc = base.FileStat(descriptor, out stat);
        if (rc == 0 && descriptor == _configDescriptor && ++_configStats == _mutateAt)
            stat = Mutation(stat);
        return rc;
    }
    public override int Close(int descriptor)
    {
        CloseCount++;
        return base.Close(descriptor);
    }
}

internal sealed class AclNative : ForwardingNative
{
    private readonly int _tag;
    private readonly int _entries;
    private readonly Dictionary<IntPtr, int> _positions = new();
    private int _configDescriptor = -1;
    private long _nextAcl = 10000;
    internal AclNative(IDarwinReadOnlyNative inner, int tag, int entries) : base(inner) { _tag = tag; _entries = entries; }
    internal bool FailFree { get; init; }
    internal int FreeCount { get; private set; }
    public override int OpenAt(int directory, IntPtr path, int flags)
    {
        int descriptor = base.OpenAt(directory, path, flags);
        if (descriptor >= 0 && Marshal.PtrToStringUTF8(path) == "config.json")
            _configDescriptor = descriptor;
        return descriptor;
    }
    public override IntPtr GetAcl(int descriptor, int type)
    {
        if (descriptor != _configDescriptor)
        {
            SyntheticError = 0;
            return base.GetAcl(descriptor, type);
        }
        SyntheticError = 0;
        IntPtr acl = new(++_nextAcl);
        _positions.Add(acl, 0);
        return acl;
    }
    public override int GetAclEntry(IntPtr acl, int entryId, out IntPtr entry)
    {
        if (!_positions.TryGetValue(acl, out int position))
        {
            SyntheticError = 0;
            return base.GetAclEntry(acl, entryId, out entry);
        }
        if ((entryId == DarwinReadOnly.AclFirstEntry && position != 0) ||
            (entryId != DarwinReadOnly.AclFirstEntry && entryId != DarwinReadOnly.AclNextEntry))
        {
            SyntheticError = DarwinReadOnly.InvalidArgument;
            entry = IntPtr.Zero;
            return -1;
        }
        if (position >= _entries)
        {
            SyntheticError = DarwinReadOnly.InvalidArgument;
            entry = IntPtr.Zero;
            return -1;
        }
        SyntheticError = 0;
        entry = new IntPtr(20000 + position);
        _positions[acl] = position + 1;
        return 0;
    }
    public override int GetAclTag(IntPtr entry, out int tag) { SyntheticError = 0; tag = _tag; return 0; }
    public override int FreeAcl(IntPtr acl)
    {
        if (!_positions.Remove(acl))
        {
            SyntheticError = 0;
            return base.FreeAcl(acl);
        }
        FreeCount++;
        SyntheticError = 0;
        return FailFree ? -1 : 0;
    }
}

internal sealed class ThrowingNative : ForwardingNative
{
    internal ThrowingNative(IDarwinReadOnlyNative inner) : base(inner) { }
    public override int FileStat(int descriptor, out DarwinStat stat)
    {
        stat = default;
        throw new InvalidOperationException("operator-canary");
    }
}

internal sealed class FifoTrackingNative : ForwardingNative
{
    private int _fifoDescriptor = -1;

    internal FifoTrackingNative(IDarwinReadOnlyNative inner) : base(inner) { }
    internal bool FifoOpened { get; private set; }
    internal int FifoFlags { get; private set; }
    internal int FifoCloseCount { get; private set; }

    public override int OpenAt(int directory, IntPtr path, int flags)
    {
        int descriptor = base.OpenAt(directory, path, flags);
        if (Marshal.PtrToStringUTF8(path) == "fifo")
        {
            FifoOpened = descriptor >= 0;
            FifoFlags = flags;
            _fifoDescriptor = descriptor;
        }
        return descriptor;
    }

    public override int Close(int descriptor)
    {
        if (descriptor == _fifoDescriptor)
            FifoCloseCount++;
        return base.Close(descriptor);
    }
}

internal sealed class PasswordNative : IDarwinReadOnlyNative
{
    private readonly byte[] _home;
    internal PasswordNative(string home, uint userId) : this(Encoding.UTF8.GetBytes(home), userId) { }
    internal PasswordNative(byte[] home, uint userId) { _home = home.ToArray(); ReturnedUserId = userId; }
    internal int PasswordCalls { get; private set; }
    internal uint ReturnedUserId { get; set; }
    internal bool ReturnOutsideBuffer { get; set; }
    internal bool OmitTerminator { get; init; }
    public int LastError => 0;
    public uint GetUserId() => ReturnedUserId;
    public uint GetEffectiveUserId() => ReturnedUserId;
    public int GetPasswordRecord(uint uid, IntPtr record, IntPtr buffer, nuint bufferSize, IntPtr result)
    {
        PasswordCalls++;
        if (_home.Length + 1 > (int)bufferSize)
            return 34;
        if (OmitTerminator)
        {
            for (int index = 0; index < (int)bufferSize; index++)
                Marshal.WriteByte(buffer, index, (byte)'x');
        }
        Marshal.Copy(_home, 0, buffer, _home.Length);
        if (!OmitTerminator)
            Marshal.WriteByte(buffer, _home.Length, 0);
        var value = new DarwinPasswd { UserId = ReturnedUserId, Directory = ReturnOutsideBuffer ? IntPtr.Add(buffer, checked((int)bufferSize)) : buffer };
        Marshal.StructureToPtr(value, record, false);
        Marshal.WriteIntPtr(result, record);
        return 0;
    }
    public int Open(IntPtr path, int flags) => throw new NotSupportedException();
    public int OpenAt(int directory, IntPtr path, int flags) => throw new NotSupportedException();
    public int FileStat(int descriptor, out DarwinStat stat) => throw new NotSupportedException();
    public int FileStatAt(int directory, IntPtr path, out DarwinStat stat, int flags) => throw new NotSupportedException();
    public nint Read(int descriptor, IntPtr buffer, nuint count) => throw new NotSupportedException();
    public int Close(int descriptor) => throw new NotSupportedException();
    public IntPtr GetAcl(int descriptor, int type) => throw new NotSupportedException();
    public int GetAclEntry(IntPtr acl, int entryId, out IntPtr entry) => throw new NotSupportedException();
    public int GetAclTag(IntPtr entry, out int tag) => throw new NotSupportedException();
    public int FreeAcl(IntPtr acl) => throw new NotSupportedException();
}
