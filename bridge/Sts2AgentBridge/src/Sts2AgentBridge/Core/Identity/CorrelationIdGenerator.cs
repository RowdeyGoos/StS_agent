using System;
using System.Security.Cryptography;

namespace Sts2AgentBridge.Core.Identity;

public static class CorrelationIdGenerator
{
    public const int RandomByteCount = 16;
    public const int EncodedCharacterCount = 32;

    public static string Create()
    {
        Span<byte> random = stackalloc byte[RandomByteCount];
        Span<char> encoded = stackalloc char[EncodedCharacterCount];
        RandomNumberGenerator.Fill(random);

        for (int index = 0; index < random.Length; index++)
        {
            byte value = random[index];
            encoded[index * 2] = EncodeNibble(value >> 4);
            encoded[(index * 2) + 1] = EncodeNibble(value & 0x0f);
        }

        CryptographicOperations.ZeroMemory(random);
        return new string(encoded);
    }

    public static bool IsCanonical(string? value)
    {
        if (value is null || value.Length != EncodedCharacterCount)
        {
            return false;
        }

        foreach (char character in value)
        {
            if (!IsLowerHex(character))
            {
                return false;
            }
        }

        return true;
    }

    private static char EncodeNibble(int value)
    {
        return (char)(value < 10 ? '0' + value : 'a' + (value - 10));
    }

    private static bool IsLowerHex(char value)
    {
        return (value >= '0' && value <= '9') || (value >= 'a' && value <= 'f');
    }
}
