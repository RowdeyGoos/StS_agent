using System;
using System.IO;

namespace Sts2AgentBridge.Verifier;

internal static class SafeFiles
{
    internal static byte[] ReadBoundedRegularFile(string path, int maximumBytes, string code)
    {
        FileInfo info;
        try
        {
            RequireNoLinkAncestors(path, includeLeaf: false, code);
            info = new FileInfo(path);
            info.Refresh();
        }
        catch
        {
            throw new BoundaryException(code);
        }
        if (!info.Exists || info.LinkTarget is not null ||
            (info.Attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint | FileAttributes.Device)) != 0 ||
            info.Length is <= 0 || info.Length > maximumBytes)
        {
            throw new BoundaryException(code);
        }
        byte[] bytes;
        try
        {
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            if (stream.Length != info.Length)
            {
                throw new BoundaryException(code);
            }
            bytes = new byte[checked((int)stream.Length)];
            int offset = 0;
            while (offset < bytes.Length)
            {
                int count = stream.Read(bytes, offset, bytes.Length - offset);
                if (count == 0)
                {
                    throw new BoundaryException(code);
                }
                offset += count;
            }
            if (stream.ReadByte() != -1)
            {
                throw new BoundaryException(code);
            }
        }
        catch (BoundaryException)
        {
            throw;
        }
        catch
        {
            throw new BoundaryException(code);
        }
        info.Refresh();
        if (!info.Exists || info.LinkTarget is not null || info.Length != bytes.Length)
        {
            throw new BoundaryException(code);
        }
        return bytes;
    }

    internal static void RequireNoLinkAncestors(string path, bool includeLeaf, string code)
    {
        string full;
        try { full = Path.GetFullPath(path); }
        catch { throw new BoundaryException(code); }
        string? root = Path.GetPathRoot(full);
        if (string.IsNullOrEmpty(root)) throw new BoundaryException(code);
        string relative = full[root.Length..];
        string[] parts = relative.Split(Path.DirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries);
        string current = root;
        int count = includeLeaf ? parts.Length : Math.Max(0, parts.Length - 1);
        for (int index = 0; index < count; index++)
        {
            current = Path.Combine(current, parts[index]);
            var info = new DirectoryInfo(current);
            try { info.Refresh(); }
            catch { throw new BoundaryException(code); }
            if (!info.Exists || info.LinkTarget is not null ||
                (info.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new BoundaryException(code);
        }
    }
}
