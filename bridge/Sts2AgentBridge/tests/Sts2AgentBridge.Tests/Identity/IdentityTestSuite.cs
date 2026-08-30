using System;
using System.Collections.Generic;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using Sts2AgentBridge.Core.Identity;

namespace Sts2AgentBridge.Tests.Identity;

internal static class IdentityTestSuite
{
    private const string CanonicalCredential =
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    public static void Run()
    {
        FixedTimeAuthenticatorMatchesOnlyExactCanonicalBytes();
        MatchesCallsTheFrozenFixedTimePrimitive();
        MalformedCredentialsAreRejected();
        DisposingAuthenticatorZeroesOwnedSecret();
        CorrelationIdentifiersAreCanonicalAndFresh();
    }

    private static void MatchesCallsTheFrozenFixedTimePrimitive()
    {
        MethodInfo? matches = typeof(FixedTimeAuthenticator).GetMethod(
            nameof(FixedTimeAuthenticator.Matches),
            BindingFlags.Instance | BindingFlags.Public,
            binder: null,
            types: new[] { typeof(ReadOnlySpan<byte>) },
            modifiers: null);
        TestAssert.True(matches is not null, "exact Matches API exists");

        byte[]? il = matches!.GetMethodBody()?.GetILAsByteArray();
        TestAssert.True(il is not null, "Matches has an IL body");

        int exactCallCount = 0;
        for (int index = 0; index <= il!.Length - 5; index++)
        {
            if (il[index] != 0x28)
            {
                continue;
            }

            int token = il[index + 1] |
                (il[index + 2] << 8) |
                (il[index + 3] << 16) |
                (il[index + 4] << 24);
            MethodBase? target;
            try
            {
                target = matches.Module.ResolveMethod(token);
            }
            catch (ArgumentException)
            {
                continue;
            }

            if (target is MethodInfo method &&
                method.DeclaringType == typeof(CryptographicOperations) &&
                method.Name == nameof(CryptographicOperations.FixedTimeEquals) &&
                method.ReturnType == typeof(bool))
            {
                ParameterInfo[] parameters = method.GetParameters();
                if (parameters.Length == 2 &&
                    parameters[0].ParameterType == typeof(ReadOnlySpan<byte>) &&
                    parameters[1].ParameterType == typeof(ReadOnlySpan<byte>))
                {
                    exactCallCount++;
                }
            }
        }

        TestAssert.Equal(1, exactCallCount, "Matches calls exact FixedTimeEquals once");
    }

    private static void FixedTimeAuthenticatorMatchesOnlyExactCanonicalBytes()
    {
        byte[] credential = Encoding.ASCII.GetBytes(CanonicalCredential);
        TestAssert.True(
            FixedTimeAuthenticator.TryCreate(credential, out FixedTimeAuthenticator? authenticator) &&
            authenticator is not null,
            "canonical authenticator creation");
        FixedTimeAuthenticator validAuthenticator = authenticator!;

        using (validAuthenticator)
        {
            TestAssert.True(validAuthenticator.Matches(credential), "exact credential match");

            byte[] different = (byte[])credential.Clone();
            different[^1] = (byte)'e';
            TestAssert.False(validAuthenticator.Matches(different), "different credential mismatch");
            TestAssert.False(validAuthenticator.Matches(credential.AsSpan(0, 63)), "short credential mismatch");

            byte[] uppercase = Encoding.ASCII.GetBytes(CanonicalCredential.ToUpperInvariant());
            TestAssert.False(validAuthenticator.Matches(uppercase), "uppercase credential mismatch");
        }
    }

    private static void MalformedCredentialsAreRejected()
    {
        byte[] canonical = Encoding.ASCII.GetBytes(CanonicalCredential);
        TestAssert.False(
            FixedTimeAuthenticator.TryCreate(canonical.AsSpan(0, 63), out _),
            "short stored credential");

        byte[] tooLong = new byte[65];
        canonical.CopyTo(tooLong, 0);
        tooLong[^1] = (byte)'0';
        TestAssert.False(FixedTimeAuthenticator.TryCreate(tooLong, out _), "long stored credential");

        byte[] uppercase = Encoding.ASCII.GetBytes(CanonicalCredential.ToUpperInvariant());
        TestAssert.False(FixedTimeAuthenticator.TryCreate(uppercase, out _), "uppercase stored credential");

        byte[] invalid = (byte[])canonical.Clone();
        invalid[10] = (byte)'g';
        TestAssert.False(FixedTimeAuthenticator.TryCreate(invalid, out _), "non-hex stored credential");

        byte[] newline = new byte[65];
        canonical.CopyTo(newline, 0);
        newline[^1] = (byte)'\n';
        TestAssert.False(FixedTimeAuthenticator.TryCreate(newline, out _), "newline stored credential");
    }

    private static void DisposingAuthenticatorZeroesOwnedSecret()
    {
        byte[] credential = Encoding.ASCII.GetBytes(CanonicalCredential);
        TestAssert.True(
            FixedTimeAuthenticator.TryCreate(credential, out FixedTimeAuthenticator? authenticator) &&
            authenticator is not null,
            "authenticator for disposal test");
        FixedTimeAuthenticator validAuthenticator = authenticator!;

        FieldInfo? field = typeof(FixedTimeAuthenticator).GetField(
            "_credential",
            BindingFlags.Instance | BindingFlags.NonPublic);
        TestAssert.True(field is not null, "credential ownership field exists");
        byte[]? owned = (byte[]?)field!.GetValue(validAuthenticator);
        TestAssert.True(owned is not null, "owned credential buffer exists");
        TestAssert.False(ReferenceEquals(credential, owned), "authenticator owns a private copy");

        validAuthenticator.Dispose();
        validAuthenticator.Dispose();

        foreach (byte value in owned!)
        {
            TestAssert.Equal((byte)0, value, "disposed credential byte is zero");
        }

        TestAssert.True(field.GetValue(validAuthenticator) is null, "disposed credential reference cleared");
        TestAssert.False(validAuthenticator.Matches(credential), "disposed authenticator rejects");
    }

    private static void CorrelationIdentifiersAreCanonicalAndFresh()
    {
        var identifiers = new HashSet<string>(StringComparer.Ordinal);
        for (int index = 0; index < 128; index++)
        {
            string identifier = CorrelationIdGenerator.Create();
            TestAssert.True(CorrelationIdGenerator.IsCanonical(identifier), "canonical correlation ID");
            TestAssert.True(identifiers.Add(identifier), "correlation IDs are fresh in test sample");
        }

        TestAssert.False(CorrelationIdGenerator.IsCanonical(null), "null correlation ID");
        TestAssert.False(CorrelationIdGenerator.IsCanonical(string.Empty), "empty correlation ID");
        TestAssert.False(
            CorrelationIdGenerator.IsCanonical("0000000000000000000000000000000G"),
            "uppercase correlation ID");
        TestAssert.False(
            CorrelationIdGenerator.IsCanonical("000000000000000000000000000000000"),
            "long correlation ID");
    }
}
