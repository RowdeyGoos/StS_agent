using System;
using System.Collections.Generic;

namespace Sts2AgentBridge.Tests;

internal static class TestAssert
{
    public static void True(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    public static void False(bool condition, string message)
    {
        True(!condition, message);
    }

    public static void Equal<T>(T expected, T actual, string message)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
        {
            throw new InvalidOperationException($"{message}: expected={expected}; actual={actual}");
        }
    }

    public static void SequenceEqual(ReadOnlySpan<byte> expected, ReadOnlySpan<byte> actual, string message)
    {
        if (!expected.SequenceEqual(actual))
        {
            throw new InvalidOperationException($"{message}: byte sequences differ");
        }
    }

    public static TException Throws<TException>(Action action, string message)
        where TException : Exception
    {
        try
        {
            action();
        }
        catch (TException exception)
        {
            return exception;
        }

        throw new InvalidOperationException($"{message}: expected {typeof(TException).Name}");
    }
}
