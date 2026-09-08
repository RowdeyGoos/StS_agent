using System;

namespace Sts2AgentBridge.Successors.ItemBootstrapV1;

internal sealed class ItemOperatorConfiguration : IDisposable
{
    private readonly object _gate = new();
    private DarwinDescriptorLease? _descriptors;
    private byte[]? _configuration;
    private bool _credentialReserved;
    private bool _disposed;

    internal ItemOperatorConfiguration(DarwinDescriptorLease descriptors, byte[] configuration)
    {
        _descriptors = descriptors;
        _configuration = configuration;
    }

    internal byte[]? TakeConfiguration()
    {
        lock (_gate)
        {
            if (_disposed || _configuration is null)
                return null;
            byte[] configuration = _configuration;
            _configuration = null;
            return configuration;
        }
    }

#if ITEM_BOOTSTRAP_TEST_SEAM
    internal byte[]? RetainedConfigurationForTests
    {
        get
        {
            lock (_gate)
                return _configuration;
        }
    }
#endif

    internal byte[]? ReadCredentialOnce()
    {
        lock (_gate)
        {
            if (_disposed || _credentialReserved || _descriptors is null)
                return null;
            _credentialReserved = true;
            DarwinDescriptorLease descriptors = _descriptors;
            _descriptors = null;
            byte[] credential = Array.Empty<byte>();
            bool success = false;
            try
            {
                if (!descriptors.RevalidateAll() ||
                    !descriptors.TryOpenFile("credential.hex", DarwinDescriptorPolicy.PrivateFile, out HeldDescriptor? held) ||
                    held is null ||
                    !descriptors.TryReadStable(held, 64, 64, out credential) ||
                    !IsCredential(credential) ||
                    !descriptors.RevalidateAll())
                    return null;
                success = true;
            }
            catch
            {
                return null;
            }
            finally
            {
                bool clean = descriptors.CloseAll();
                if (!clean)
                    success = false;
                if (!success)
                    DarwinReadOnly.Zero(credential);
            }
            return success ? credential : null;
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed)
                return;
            _disposed = true;
            DarwinReadOnly.Zero(_configuration);
            _configuration = null;
            DarwinDescriptorLease? descriptors = _descriptors;
            _descriptors = null;
            if (descriptors is not null)
                _ = descriptors.CloseAll();
        }
    }

    private static bool IsCredential(byte[] credential)
    {
        if (credential.Length != 64)
            return false;
        foreach (byte value in credential)
        {
            if (!((value >= (byte)'0' && value <= (byte)'9') ||
                  (value >= (byte)'a' && value <= (byte)'f')))
                return false;
        }
        return true;
    }
}
