using System;
using System.Security.Cryptography;

namespace Sts2AgentBridge.Core.Identity;

public sealed class FixedTimeAuthenticator : IDisposable
{
    public const int CredentialLength = 64;

    private readonly object _gate = new();
    private byte[]? _credential;

    private FixedTimeAuthenticator(byte[] credential)
    {
        _credential = credential;
    }

    public static bool TryCreate(
        ReadOnlySpan<byte> canonicalCredential,
        out FixedTimeAuthenticator? authenticator)
    {
        if (!IsCanonicalCredential(canonicalCredential))
        {
            authenticator = null;
            return false;
        }

        authenticator = new FixedTimeAuthenticator(canonicalCredential.ToArray());
        return true;
    }

    public static bool IsCanonicalCredential(ReadOnlySpan<byte> credential)
    {
        if (credential.Length != CredentialLength)
        {
            return false;
        }

        foreach (byte value in credential)
        {
            if (!IsLowerHex(value))
            {
                return false;
            }
        }

        return true;
    }

    public bool Matches(ReadOnlySpan<byte> candidate)
    {
        lock (_gate)
        {
            if (_credential is null || candidate.Length != CredentialLength)
            {
                return false;
            }

            return CryptographicOperations.FixedTimeEquals(candidate, _credential);
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_credential is null)
            {
                return;
            }

            CryptographicOperations.ZeroMemory(_credential);
            _credential = null;
        }
    }

    private static bool IsLowerHex(byte value)
    {
        return (value >= (byte)'0' && value <= (byte)'9') ||
            (value >= (byte)'a' && value <= (byte)'f');
    }
}
