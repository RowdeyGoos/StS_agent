using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

[StructLayout(LayoutKind.Explicit, Size = 16)]
internal struct DarwinTimespec
{
    [FieldOffset(0)] internal long Seconds;
    [FieldOffset(8)] internal long Nanoseconds;
}

[StructLayout(LayoutKind.Explicit, Size = 144)]
internal struct DarwinStat
{
    [FieldOffset(0)] internal int Device;
    [FieldOffset(4)] internal ushort Mode;
    [FieldOffset(6)] internal ushort LinkCount;
    [FieldOffset(8)] internal ulong Inode;
    [FieldOffset(16)] internal uint UserId;
    [FieldOffset(20)] internal uint GroupId;
    [FieldOffset(24)] internal int SpecialDevice;
    [FieldOffset(32)] internal DarwinTimespec AccessTime;
    [FieldOffset(48)] internal DarwinTimespec ModificationTime;
    [FieldOffset(64)] internal DarwinTimespec ChangeTime;
    [FieldOffset(80)] internal DarwinTimespec BirthTime;
    [FieldOffset(96)] internal long Size;
    [FieldOffset(104)] internal long Blocks;
    [FieldOffset(112)] internal int BlockSize;
    [FieldOffset(116)] internal uint Flags;
    [FieldOffset(120)] internal uint Generation;
    [FieldOffset(124)] internal int Spare;
    [FieldOffset(128)] internal long Spare0;
    [FieldOffset(136)] internal long Spare1;
}

[StructLayout(LayoutKind.Explicit, Size = 72)]
internal struct DarwinPasswd
{
    [FieldOffset(0)] internal IntPtr Name;
    [FieldOffset(8)] internal IntPtr Password;
    [FieldOffset(16)] internal uint UserId;
    [FieldOffset(20)] internal uint GroupId;
    [FieldOffset(24)] internal long Change;
    [FieldOffset(32)] internal IntPtr Class;
    [FieldOffset(40)] internal IntPtr Gecos;
    [FieldOffset(48)] internal IntPtr Directory;
    [FieldOffset(56)] internal IntPtr Shell;
    [FieldOffset(64)] internal long Expire;
}

internal interface IDarwinReadOnlyNative
{
    int LastError { get; }
    uint GetUserId();
    uint GetEffectiveUserId();
    int GetPasswordRecord(uint uid, IntPtr record, IntPtr buffer, nuint bufferSize, IntPtr result);
    int Open(IntPtr path, int flags);
    int OpenAt(int directory, IntPtr path, int flags);
    int FileStat(int descriptor, out DarwinStat stat);
    int FileStatAt(int directory, IntPtr path, out DarwinStat stat, int flags);
    nint Read(int descriptor, IntPtr buffer, nuint count);
    int Close(int descriptor);
    IntPtr GetAcl(int descriptor, int type);
    int GetAclEntry(IntPtr acl, int entryId, out IntPtr entry);
    int GetAclTag(IntPtr entry, out int tag);
    int FreeAcl(IntPtr acl);
}

internal sealed class LibSystemDarwinReadOnlyNative : IDarwinReadOnlyNative
{
    private const string LibSystem = "/usr/lib/libSystem.B.dylib";

    internal static LibSystemDarwinReadOnlyNative Instance { get; } = new();

    private LibSystemDarwinReadOnlyNative()
    {
    }

    public int LastError => Marshal.GetLastPInvokeError();
    public uint GetUserId() => NativeGetUserId();
    public uint GetEffectiveUserId() => NativeGetEffectiveUserId();
    public int GetPasswordRecord(uint uid, IntPtr record, IntPtr buffer, nuint bufferSize, IntPtr result) =>
        NativeGetPasswordRecord(uid, record, buffer, bufferSize, result);
    public int Open(IntPtr path, int flags) => NativeOpen(path, flags);
    public int OpenAt(int directory, IntPtr path, int flags) => NativeOpenAt(directory, path, flags);
    public int FileStat(int descriptor, out DarwinStat stat) => NativeFileStat(descriptor, out stat);
    public int FileStatAt(int directory, IntPtr path, out DarwinStat stat, int flags) =>
        NativeFileStatAt(directory, path, out stat, flags);
    public nint Read(int descriptor, IntPtr buffer, nuint count) => NativeRead(descriptor, buffer, count);
    public int Close(int descriptor) => NativeClose(descriptor);
    public IntPtr GetAcl(int descriptor, int type) => NativeGetAcl(descriptor, type);
    public int GetAclEntry(IntPtr acl, int entryId, out IntPtr entry) => NativeGetAclEntry(acl, entryId, out entry);
    public int GetAclTag(IntPtr entry, out int tag) => NativeGetAclTag(entry, out tag);
    public int FreeAcl(IntPtr acl) => NativeFreeAcl(acl);

    [DllImport(LibSystem, EntryPoint = "getuid", CallingConvention = CallingConvention.Cdecl)]
    private static extern uint NativeGetUserId();

    [DllImport(LibSystem, EntryPoint = "geteuid", CallingConvention = CallingConvention.Cdecl)]
    private static extern uint NativeGetEffectiveUserId();

    [DllImport(LibSystem, EntryPoint = "getpwuid_r", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetPasswordRecord(
        uint uid,
        IntPtr record,
        IntPtr buffer,
        nuint bufferSize,
        IntPtr result);

    [DllImport(LibSystem, EntryPoint = "open", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern int NativeOpen(IntPtr path, int flags);

    [DllImport(LibSystem, EntryPoint = "openat", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern int NativeOpenAt(int directory, IntPtr path, int flags);

    [DllImport(LibSystem, EntryPoint = "fstat", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern int NativeFileStat(int descriptor, out DarwinStat stat);

    [DllImport(LibSystem, EntryPoint = "fstatat", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern int NativeFileStatAt(int directory, IntPtr path, out DarwinStat stat, int flags);

    [DllImport(LibSystem, EntryPoint = "read", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern nint NativeRead(int descriptor, IntPtr buffer, nuint count);

    [DllImport(LibSystem, EntryPoint = "close", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern int NativeClose(int descriptor);

    [DllImport(LibSystem, EntryPoint = "acl_get_fd_np", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern IntPtr NativeGetAcl(int descriptor, int type);

    [DllImport(LibSystem, EntryPoint = "acl_get_entry", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern int NativeGetAclEntry(IntPtr acl, int entryId, out IntPtr entry);

    [DllImport(LibSystem, EntryPoint = "acl_get_tag_type", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern int NativeGetAclTag(IntPtr entry, out int tag);

    [DllImport(LibSystem, EntryPoint = "acl_free", CallingConvention = CallingConvention.Cdecl, SetLastError = true)]
    private static extern int NativeFreeAcl(IntPtr acl);
}

internal static class DarwinReadOnly
{
    internal const int OpenReadOnly = 0;
    internal const int OpenNonBlocking = 0x4;
    internal const int OpenNoFollow = 0x100;
    internal const int OpenDirectory = 0x100000;
    internal const int OpenCloseOnExec = 0x1000000;
#if ITEM_BOOTSTRAP_TEST_SEAM
    internal const int OpenNoFollowAny = 0x20000000;
#endif
    internal const int AtSymlinkNoFollow = 0x20;
    internal const int Interrupted = 4;
    internal const int NoEntry = 2;
    internal const int InvalidArgument = 22;
    internal const int AclTypeExtended = 0x100;
    internal const int AclFirstEntry = 0;
    internal const int AclNextEntry = -1;
    internal const int AclExtendedAllow = 1;
    internal const int AclExtendedDeny = 2;
    internal const int TypeMask = 0xf000;
    internal const int DirectoryType = 0x4000;
    internal const int RegularType = 0x8000;
    internal const int PermissionMask = 0x0fff;
    internal const int GroupOtherWrite = 0x12;
    internal const int SpecialBits = 0x0e00;
    internal const int MaxEintrRetries = 8;
    internal const int MaxAclEntries = 169;

    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    internal static bool IsSupportedPlatform() =>
        OperatingSystem.IsMacOS() && RuntimeInformation.ProcessArchitecture == Architecture.Arm64;

    internal static bool TryGetIdentity(IDarwinReadOnlyNative native, out uint effectiveUserId)
    {
        effectiveUserId = 0;
        try
        {
            uint real = native.GetUserId();
            uint effective = native.GetEffectiveUserId();
            if (real != effective)
                return false;
            effectiveUserId = effective;
            return true;
        }
        catch
        {
            return false;
        }
    }

    internal static bool TryResolveHome(
        IDarwinReadOnlyNative native,
        uint effectiveUserId,
        out string[] components)
    {
        components = Array.Empty<string>();
        const int recordSize = 72;
        const int bufferSize = 16384;
        IntPtr record = IntPtr.Zero;
        IntPtr buffer = IntPtr.Zero;
        IntPtr result = IntPtr.Zero;
        try
        {
            record = Marshal.AllocHGlobal(recordSize);
            buffer = Marshal.AllocHGlobal(bufferSize);
            result = Marshal.AllocHGlobal(IntPtr.Size);
            ZeroUnmanaged(record, recordSize);
            ZeroUnmanaged(buffer, bufferSize);
            ZeroUnmanaged(result, IntPtr.Size);
            int rc = native.GetPasswordRecord(effectiveUserId, record, buffer, bufferSize, result);
            if (rc != 0 || Marshal.ReadIntPtr(result) != record)
                return false;
            DarwinPasswd password = Marshal.PtrToStructure<DarwinPasswd>(record);
            if (password.UserId != effectiveUserId || !TryCopyHome(buffer, bufferSize, password.Directory, out byte[]? homeBytes))
                return false;
            try
            {
                string home = StrictUtf8.GetString(homeBytes);
                return TryParseAbsolutePath(home, out components);
            }
            catch
            {
                return false;
            }
            finally
            {
                Array.Clear(homeBytes);
            }
        }
        catch
        {
            return false;
        }
        finally
        {
            if (result != IntPtr.Zero)
            {
                ZeroUnmanaged(result, IntPtr.Size);
                Marshal.FreeHGlobal(result);
            }
            if (buffer != IntPtr.Zero)
            {
                ZeroUnmanaged(buffer, bufferSize);
                Marshal.FreeHGlobal(buffer);
            }
            if (record != IntPtr.Zero)
            {
                ZeroUnmanaged(record, recordSize);
                Marshal.FreeHGlobal(record);
            }
        }
    }

    internal static bool TryParseAbsolutePath(string path, out string[] components)
    {
        components = Array.Empty<string>();
        if (string.IsNullOrEmpty(path) || path[0] != '/' || path.IndexOf('\0') >= 0 ||
            path.IndexOf('\n') >= 0 || path.IndexOf('\r') >= 0)
            return false;
        byte[] allBytes;
        try
        {
            allBytes = StrictUtf8.GetBytes(path);
        }
        catch
        {
            return false;
        }
        if (allBytes.Length > 1024)
            return false;
        string[] raw = path.Split('/');
        if (raw.Length == 2 && raw[0].Length == 0 && raw[1].Length == 0)
        {
            components = Array.Empty<string>();
            return true;
        }
        if (raw.Length < 2 || raw[0].Length != 0 || raw.Length - 1 > 32)
            return false;
        string[] parsed = new string[raw.Length - 1];
        for (int index = 1; index < raw.Length; index++)
        {
            string component = raw[index];
            if (component.Length == 0 || component == "." || component == "..")
                return false;
            byte[] bytes;
            try
            {
                bytes = StrictUtf8.GetBytes(component);
            }
            catch
            {
                return false;
            }
            if (bytes.Length == 0 || bytes.Length > 255)
                return false;
            parsed[index - 1] = component;
        }
        components = parsed;
        return true;
    }

    internal static bool TryOpen(IDarwinReadOnlyNative native, string path, int flags, out int descriptor)
    {
        descriptor = -1;
        using NativeText text = new(path);
        for (int retries = 0; ; retries++)
        {
            int value = native.Open(text.Pointer, flags);
            if (value >= 0)
            {
                descriptor = value;
                return true;
            }
            if (native.LastError != Interrupted || retries >= MaxEintrRetries)
                return false;
        }
    }

    internal static bool TryOpenAt(
        IDarwinReadOnlyNative native,
        int parent,
        string name,
        int flags,
        out int descriptor)
    {
        descriptor = -1;
        using NativeText text = new(name);
        for (int retries = 0; ; retries++)
        {
            int value = native.OpenAt(parent, text.Pointer, flags);
            if (value >= 0)
            {
                descriptor = value;
                return true;
            }
            if (native.LastError != Interrupted || retries >= MaxEintrRetries)
                return false;
        }
    }

    internal static bool TryFileStat(IDarwinReadOnlyNative native, int descriptor, out DarwinStat stat)
    {
        stat = default;
        for (int retries = 0; ; retries++)
        {
            int rc = native.FileStat(descriptor, out DarwinStat value);
            if (rc == 0)
            {
                stat = value;
                return true;
            }
            if (rc != -1 || native.LastError != Interrupted || retries >= MaxEintrRetries)
                return false;
        }
    }

    internal static bool TryFileStatAt(
        IDarwinReadOnlyNative native,
        int parent,
        string name,
        out DarwinStat stat)
    {
        stat = default;
        using NativeText text = new(name);
        for (int retries = 0; ; retries++)
        {
            int rc = native.FileStatAt(parent, text.Pointer, out DarwinStat value, AtSymlinkNoFollow);
            if (rc == 0)
            {
                stat = value;
                return true;
            }
            if (rc != -1 || native.LastError != Interrupted || retries >= MaxEintrRetries)
                return false;
        }
    }

    internal static bool ValidateAcl(IDarwinReadOnlyNative native, int descriptor)
    {
        IntPtr acl;
        try
        {
            int retries = 0;
            while (true)
            {
                acl = native.GetAcl(descriptor, AclTypeExtended);
                if (acl != IntPtr.Zero)
                    break;
                int error = native.LastError;
                if (error == NoEntry)
                    return true;
                if (error != Interrupted || retries >= MaxEintrRetries)
                    return false;
                retries++;
            }
        }
        catch
        {
            return false;
        }

        bool valid = true;
        try
        {
            int entryId = AclFirstEntry;
            int accepted = 0;
            while (true)
            {
                int rc;
                IntPtr entry;
                int error = 0;
                int retries = 0;
                while (true)
                {
                    rc = native.GetAclEntry(acl, entryId, out entry);
                    if (rc != -1)
                        break;
                    error = native.LastError;
                    if (error != Interrupted || retries >= MaxEintrRetries)
                        break;
                    retries++;
                }
                if (rc == -1 && error == InvalidArgument)
                    break;
                if (rc != 0 || entry == IntPtr.Zero || accepted >= MaxAclEntries)
                {
                    valid = false;
                    break;
                }

                int tag;
                retries = 0;
                while (true)
                {
                    rc = native.GetAclTag(entry, out tag);
                    if (rc != -1 || native.LastError != Interrupted || retries >= MaxEintrRetries)
                        break;
                    retries++;
                }
                if (rc != 0 || tag != AclExtendedDeny)
                {
                    valid = false;
                    break;
                }
                accepted++;
                entryId = AclNextEntry;
            }
        }
        catch
        {
            valid = false;
        }
        finally
        {
            try
            {
                if (native.FreeAcl(acl) != 0)
                    valid = false;
            }
            catch
            {
                valid = false;
            }
        }
        return valid;
    }

    internal static bool IsSameObject(in DarwinStat left, in DarwinStat right) =>
        left.Device == right.Device && left.Inode == right.Inode &&
        (left.Mode & TypeMask) == (right.Mode & TypeMask);

    internal static bool IsSameStableFile(in DarwinStat left, in DarwinStat right) =>
        IsSameObject(left, right) &&
        left.Mode == right.Mode &&
        left.UserId == right.UserId &&
        left.LinkCount == right.LinkCount &&
        left.Size == right.Size &&
        SameTime(left.ModificationTime, right.ModificationTime) &&
        SameTime(left.ChangeTime, right.ChangeTime);

    internal static void Zero(byte[]? bytes)
    {
        if (bytes is not null)
            Array.Clear(bytes);
    }

    private static bool TryCopyHome(IntPtr buffer, int bufferSize, IntPtr home, out byte[] bytes)
    {
        bytes = Array.Empty<byte>();
        long start = buffer.ToInt64();
        long pointer = home.ToInt64();
        long end = start + bufferSize;
        if (pointer < start || pointer >= end)
            return false;
        int available = (int)Math.Min(end - pointer, 1025);
        int length = -1;
        for (int index = 0; index < available; index++)
        {
            if (Marshal.ReadByte(home, index) == 0)
            {
                length = index;
                break;
            }
        }
        if (length <= 0 || length > 1024)
            return false;
        bytes = new byte[length];
        Marshal.Copy(home, bytes, 0, length);
        return true;
    }

    private static bool SameTime(DarwinTimespec left, DarwinTimespec right) =>
        left.Seconds == right.Seconds && left.Nanoseconds == right.Nanoseconds;

    private static void ZeroUnmanaged(IntPtr pointer, int size)
    {
        for (int index = 0; index < size; index++)
            Marshal.WriteByte(pointer, index, 0);
    }

    private sealed class NativeText : IDisposable
    {
        private readonly int _size;
        private IntPtr _pointer;

        internal NativeText(string value)
        {
            byte[] bytes = StrictUtf8.GetBytes(value);
            _size = checked(bytes.Length + 1);
            _pointer = Marshal.AllocHGlobal(_size);
            Marshal.Copy(bytes, 0, _pointer, bytes.Length);
            Marshal.WriteByte(_pointer, bytes.Length, 0);
            Array.Clear(bytes);
        }

        internal IntPtr Pointer => _pointer;

        public void Dispose()
        {
            if (_pointer == IntPtr.Zero)
                return;
            ZeroUnmanaged(_pointer, _size);
            Marshal.FreeHGlobal(_pointer);
            _pointer = IntPtr.Zero;
        }
    }
}

internal enum DarwinDescriptorPolicy
{
    AncestorDirectory,
    OwnedDirectory,
    PrivateDirectory,
    PrivateFile,
    PinnedFile,
}

internal sealed class DarwinDescriptorLease : IDisposable
{
    private readonly IDarwinReadOnlyNative _native;
    private readonly uint _effectiveUserId;
    private readonly List<HeldDescriptor> _held = new();
    private bool _closed;

    internal DarwinDescriptorLease(IDarwinReadOnlyNative native, uint effectiveUserId)
    {
        _native = native;
        _effectiveUserId = effectiveUserId;
    }

    internal int LastDescriptor => _held.Count == 0 ? -1 : _held[^1].Descriptor;
    internal int LastDirectoryDescriptor
    {
        get
        {
            for (int index = _held.Count - 1; index >= 0; index--)
            {
                if (_held[index].Policy != DarwinDescriptorPolicy.PrivateFile &&
                    _held[index].Policy != DarwinDescriptorPolicy.PinnedFile)
                    return _held[index].Descriptor;
            }
            return -1;
        }
    }
    internal int Count => _held.Count;

    internal bool TryOpenRoot()
    {
        if (!DarwinReadOnly.TryOpen(
                _native,
                "/",
                DarwinReadOnly.OpenReadOnly | DarwinReadOnly.OpenCloseOnExec |
                DarwinReadOnly.OpenNoFollow | DarwinReadOnly.OpenDirectory,
                out int descriptor))
            return false;
        return TryHold(descriptor, -1, null, DarwinDescriptorPolicy.AncestorDirectory, false);
    }

#if ITEM_BOOTSTRAP_TEST_SEAM
    internal bool TryOpenSyntheticHome(string path)
    {
        if (!DarwinReadOnly.TryOpen(
                _native,
                path,
                DarwinReadOnly.OpenReadOnly | DarwinReadOnly.OpenCloseOnExec |
                DarwinReadOnly.OpenNoFollowAny | DarwinReadOnly.OpenDirectory,
                out int descriptor))
            return false;
        return TryHold(descriptor, -1, null, DarwinDescriptorPolicy.PrivateDirectory, false);
    }
#endif

    internal bool TryOpenDirectory(string name, DarwinDescriptorPolicy policy)
    {
        int parent = LastDirectoryDescriptor;
        if (parent < 0 || !DarwinReadOnly.TryOpenAt(
                _native,
                parent,
                name,
                DarwinReadOnly.OpenReadOnly | DarwinReadOnly.OpenCloseOnExec |
                DarwinReadOnly.OpenNoFollow | DarwinReadOnly.OpenDirectory,
                out int descriptor))
            return false;
        return TryHold(descriptor, parent, name, policy, false);
    }

    internal bool TryOpenFile(string name, DarwinDescriptorPolicy policy, out HeldDescriptor? held)
    {
        held = null;
        int parent = LastDirectoryDescriptor;
        if (parent < 0 || !DarwinReadOnly.TryOpenAt(
                _native,
                parent,
                name,
                DarwinReadOnly.OpenReadOnly | DarwinReadOnly.OpenCloseOnExec |
                DarwinReadOnly.OpenNoFollow | DarwinReadOnly.OpenNonBlocking,
                out int descriptor))
            return false;
        if (!TryHold(descriptor, parent, name, policy, true))
            return false;
        held = _held[^1];
        return true;
    }

    internal bool TryReadStable(HeldDescriptor held, int minimum, int maximum, out byte[] bytes)
    {
        bytes = Array.Empty<byte>();
        if (!TryValidate(held, out DarwinStat before) ||
            (held.RequireUnchanged && !DarwinReadOnly.IsSameStableFile(held.Initial, before)) ||
            before.Size < minimum || before.Size > maximum)
            return false;
        int length = checked((int)before.Size);
        byte[] result = new byte[length];
        IntPtr scratch = IntPtr.Zero;
        try
        {
            scratch = Marshal.AllocHGlobal(Math.Max(1, length));
            int offset = 0;
            int eintrRetries = 0;
            while (offset < length)
            {
                nint count = _native.Read(held.Descriptor, IntPtr.Add(scratch, offset), (nuint)(length - offset));
                if (count == -1 && _native.LastError == DarwinReadOnly.Interrupted &&
                    eintrRetries < DarwinReadOnly.MaxEintrRetries)
                {
                    eintrRetries++;
                    continue;
                }
                if (count <= 0 || count > length - offset)
                    return false;
                offset += checked((int)count);
            }
            nint eof = _native.Read(held.Descriptor, scratch, 1);
            while (eof == -1 && _native.LastError == DarwinReadOnly.Interrupted &&
                   eintrRetries < DarwinReadOnly.MaxEintrRetries)
            {
                eintrRetries++;
                eof = _native.Read(held.Descriptor, scratch, 1);
            }
            if (eof != 0)
                return false;
            Marshal.Copy(scratch, result, 0, length);
            if (!TryValidate(held, out DarwinStat after) || !DarwinReadOnly.IsSameStableFile(before, after))
                return false;
            bytes = result;
            result = Array.Empty<byte>();
            return true;
        }
        catch
        {
            return false;
        }
        finally
        {
            DarwinReadOnly.Zero(result);
            if (scratch != IntPtr.Zero)
            {
                for (int index = 0; index < Math.Max(1, length); index++)
                    Marshal.WriteByte(scratch, index, 0);
                Marshal.FreeHGlobal(scratch);
            }
        }
    }

    internal bool TryVerifyHash(HeldDescriptor held, long expectedLength, byte[] expectedDigest)
    {
        if (!TryValidate(held, out DarwinStat before) ||
            (held.RequireUnchanged && !DarwinReadOnly.IsSameStableFile(held.Initial, before)) ||
            before.Size != expectedLength || expectedLength < 0)
            return false;
        const int bufferSize = 65536;
        byte[] managed = new byte[bufferSize];
        byte[] digest = Array.Empty<byte>();
        GCHandle pinned = default;
        bool isPinned = false;
        try
        {
            pinned = GCHandle.Alloc(managed, GCHandleType.Pinned);
            isPinned = true;
            IntPtr buffer = pinned.AddrOfPinnedObject();
            using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            long remaining = expectedLength;
            int eintrRetries = 0;
            while (remaining > 0)
            {
                int wanted = (int)Math.Min(bufferSize, remaining);
                nint count = _native.Read(held.Descriptor, buffer, (nuint)wanted);
                if (count == -1 && _native.LastError == DarwinReadOnly.Interrupted &&
                    eintrRetries < DarwinReadOnly.MaxEintrRetries)
                {
                    eintrRetries++;
                    continue;
                }
                if (count <= 0 || count > wanted)
                    return false;
                int actual = checked((int)count);
                Marshal.Copy(buffer, managed, 0, actual);
                hash.AppendData(managed, 0, actual);
                Array.Clear(managed, 0, actual);
                remaining -= actual;
            }
            nint eof = _native.Read(held.Descriptor, buffer, 1);
            while (eof == -1 && _native.LastError == DarwinReadOnly.Interrupted &&
                   eintrRetries < DarwinReadOnly.MaxEintrRetries)
            {
                eintrRetries++;
                eof = _native.Read(held.Descriptor, buffer, 1);
            }
            if (eof != 0)
                return false;
            digest = hash.GetHashAndReset();
            if (!CryptographicOperations.FixedTimeEquals(digest, expectedDigest))
                return false;
            return TryValidate(held, out DarwinStat after) && DarwinReadOnly.IsSameStableFile(before, after);
        }
        catch
        {
            return false;
        }
        finally
        {
            DarwinReadOnly.Zero(managed);
            DarwinReadOnly.Zero(digest);
            if (isPinned)
                pinned.Free();
        }
    }

    internal bool RevalidateAll()
    {
        if (_closed)
            return false;
        foreach (HeldDescriptor held in _held)
        {
            if (!TryValidate(held, out DarwinStat current))
                return false;
            if (held.RequireUnchanged && !DarwinReadOnly.IsSameStableFile(held.Initial, current))
                return false;
        }
        return true;
    }

    internal bool CloseAll()
    {
        if (_closed)
            return true;
        _closed = true;
        bool clean = true;
        for (int index = _held.Count - 1; index >= 0; index--)
        {
            try
            {
                if (_native.Close(_held[index].Descriptor) != 0)
                    clean = false;
            }
            catch
            {
                clean = false;
            }
        }
        _held.Clear();
        return clean;
    }

    public void Dispose()
    {
        _ = CloseAll();
    }

    private bool TryHold(
        int descriptor,
        int parent,
        string? name,
        DarwinDescriptorPolicy policy,
        bool requireUnchanged)
    {
        var candidate = new HeldDescriptor(descriptor, parent, name, policy, default, requireUnchanged);
        if (!TryValidate(candidate, out DarwinStat stat))
        {
            try
            {
                _ = _native.Close(descriptor);
            }
            catch
            {
            }
            return false;
        }
        _held.Add(new HeldDescriptor(descriptor, parent, name, policy, stat, requireUnchanged));
        return true;
    }

    private bool TryValidate(HeldDescriptor held, out DarwinStat stat)
    {
        stat = default;
        try
        {
            if (!DarwinReadOnly.TryFileStat(_native, held.Descriptor, out stat) ||
                !ValidatePolicy(stat, held.Policy, _effectiveUserId) ||
                !DarwinReadOnly.ValidateAcl(_native, held.Descriptor))
                return false;
            if (held.ParentDescriptor >= 0 && held.Name is not null)
            {
                if (!DarwinReadOnly.TryFileStatAt(_native, held.ParentDescriptor, held.Name, out DarwinStat named) ||
                    !DarwinReadOnly.IsSameObject(stat, named))
                    return false;
            }
            return true;
        }
        catch
        {
            return false;
        }
    }

    internal static bool ValidatePolicy(in DarwinStat stat, DarwinDescriptorPolicy policy, uint effectiveUserId)
    {
        int type = stat.Mode & DarwinReadOnly.TypeMask;
        int permissions = stat.Mode & DarwinReadOnly.PermissionMask;
        if ((permissions & DarwinReadOnly.SpecialBits) != 0)
            return false;
        switch (policy)
        {
            case DarwinDescriptorPolicy.AncestorDirectory:
                return type == DarwinReadOnly.DirectoryType &&
                    (stat.UserId == 0 || stat.UserId == effectiveUserId) &&
                    (permissions & DarwinReadOnly.GroupOtherWrite) == 0;
            case DarwinDescriptorPolicy.OwnedDirectory:
                return type == DarwinReadOnly.DirectoryType && stat.UserId == effectiveUserId &&
                    (permissions & DarwinReadOnly.GroupOtherWrite) == 0;
            case DarwinDescriptorPolicy.PrivateDirectory:
                return type == DarwinReadOnly.DirectoryType && stat.UserId == effectiveUserId && permissions == 0x1c0;
            case DarwinDescriptorPolicy.PrivateFile:
                return type == DarwinReadOnly.RegularType && stat.UserId == effectiveUserId &&
                    permissions == 0x180 && stat.LinkCount == 1;
            case DarwinDescriptorPolicy.PinnedFile:
                return type == DarwinReadOnly.RegularType &&
                    (stat.UserId == 0 || stat.UserId == effectiveUserId) &&
                    (permissions & DarwinReadOnly.GroupOtherWrite) == 0 && stat.LinkCount == 1;
            default:
                return false;
        }
    }
}

internal sealed class HeldDescriptor
{
    internal HeldDescriptor(
        int descriptor,
        int parentDescriptor,
        string? name,
        DarwinDescriptorPolicy policy,
        DarwinStat initial,
        bool requireUnchanged)
    {
        Descriptor = descriptor;
        ParentDescriptor = parentDescriptor;
        Name = name;
        Policy = policy;
        Initial = initial;
        RequireUnchanged = requireUnchanged;
    }

    internal int Descriptor { get; }
    internal int ParentDescriptor { get; }
    internal string? Name { get; }
    internal DarwinDescriptorPolicy Policy { get; }
    internal DarwinStat Initial { get; }
    internal bool RequireUnchanged { get; }
}
