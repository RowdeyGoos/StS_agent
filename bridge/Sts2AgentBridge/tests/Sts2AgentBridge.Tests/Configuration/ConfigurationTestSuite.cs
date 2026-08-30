using System;
using System.IO;
using System.Reflection;
using System.Runtime.Versioning;
using System.Security.Cryptography;
using System.Text;
using Sts2AgentBridge.Core.Configuration;

namespace Sts2AgentBridge.Tests.Configuration;

internal static class ConfigurationTestSuite
{
    private const string EnabledDocument =
        "{\"schema_version\":\"live_probe_v0_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}";

    private const string DisabledDocument =
        "{\"schema_version\":\"live_probe_v0_config_v1\",\"enabled\":false,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}";

    public static void Run()
    {
        CanonicalDocumentsPassExactly();
        CanonicalDocumentHashesMatchFreeze();
        MalformedDocumentsFailClosedFromTemporaryFixtures();
        FullLoadOrchestrationUsesOnlyATrustedDisposableTree();
        FullLoadFilesystemShapesFailClosed();
        FixedPathHelpersFailClosedOnUnsafeFilesystemShapes();
        BoundedReadHelperEnforcesTheExactCap();
    }

    private static void CanonicalDocumentsPassExactly()
    {
        byte[] enabledBytes = ReadThroughTemporaryFixture(Encoding.UTF8.GetBytes(EnabledDocument));
        TestAssert.Equal(129, enabledBytes.Length, "enabled config length");
        TestAssert.True(
            StrictConfigurationLoader.TryParseCanonicalDocument(enabledBytes, out bool enabled) && enabled,
            "enabled canonical config");

        byte[] disabledBytes = ReadThroughTemporaryFixture(Encoding.UTF8.GetBytes(DisabledDocument));
        TestAssert.Equal(130, disabledBytes.Length, "disabled config length");
        TestAssert.True(
            StrictConfigurationLoader.TryParseCanonicalDocument(disabledBytes, out bool disabled) && !disabled,
            "disabled canonical config");
    }

    private static void CanonicalDocumentHashesMatchFreeze()
    {
        TestAssert.Equal(
            "f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea",
            HashLowerHex(Encoding.UTF8.GetBytes(EnabledDocument)),
            "enabled config SHA-256");
        TestAssert.Equal(
            "132f4c49ee499a52b43d2f0d66edcba1bd78bd5b49777c270636246d85cd3b52",
            HashLowerHex(Encoding.UTF8.GetBytes(DisabledDocument)),
            "disabled config SHA-256");
    }

    private static void MalformedDocumentsFailClosedFromTemporaryFixtures()
    {
        string[] malformedText =
        {
            string.Empty,
            EnabledDocument + "\n",
            " " + EnabledDocument,
            EnabledDocument.Replace("\"enabled\":true", "\"enabled\":\"true\"", StringComparison.Ordinal),
            EnabledDocument.Replace("43117", "43118", StringComparison.Ordinal),
            EnabledDocument.Replace("127.0.0.1", "0.0.0.0", StringComparison.Ordinal),
            EnabledDocument.Replace("credential.hex", "other.hex", StringComparison.Ordinal),
            EnabledDocument.Replace("\"port\":43117", "\"port\":43117,\"port\":43117", StringComparison.Ordinal),
            EnabledDocument.Replace("\"port\":43117", "\"extra\":0,\"port\":43117", StringComparison.Ordinal),
            "{\"enabled\":true,\"schema_version\":\"live_probe_v0_config_v1\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}",
            "[]",
            "null",
        };

        foreach (string malformed in malformedText)
        {
            byte[] bytes = ReadThroughTemporaryFixture(Encoding.UTF8.GetBytes(malformed));
            TestAssert.False(
                StrictConfigurationLoader.TryParseCanonicalDocument(bytes, out _),
                "malformed config must fail");
        }

        byte[] bom = new byte[Encoding.UTF8.GetPreamble().Length + Encoding.UTF8.GetByteCount(EnabledDocument)];
        Encoding.UTF8.GetPreamble().CopyTo(bom, 0);
        Encoding.UTF8.GetBytes(EnabledDocument).CopyTo(bom, Encoding.UTF8.GetPreamble().Length);
        TestAssert.False(
            StrictConfigurationLoader.TryParseCanonicalDocument(ReadThroughTemporaryFixture(bom), out _),
            "BOM config must fail");

        TestAssert.False(
            StrictConfigurationLoader.TryParseCanonicalDocument(
                ReadThroughTemporaryFixture(new byte[] { 0xff, 0xfe, 0xfd }),
                out _),
            "invalid UTF-8 config must fail");
        TestAssert.False(
            StrictConfigurationLoader.TryParseCanonicalDocument(
                ReadThroughTemporaryFixture(new byte[StrictConfigurationLoader.MaximumConfigurationBytes + 1]),
                out _),
            "oversized config must fail");
    }

    private static byte[] ReadThroughTemporaryFixture(byte[] content)
    {
        string fixtureRoot = Path.Combine(
            Path.GetTempPath(),
            "sts2-agent-r0a-config-test-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(fixtureRoot);
        string fixturePath = Path.Combine(fixtureRoot, "fixture.json");

        try
        {
            File.WriteAllBytes(fixturePath, content);
            return File.ReadAllBytes(fixturePath);
        }
        finally
        {
            Directory.Delete(fixtureRoot, recursive: true);
        }
    }

    private static void FullLoadOrchestrationUsesOnlyATrustedDisposableTree()
    {
        if (!OperatingSystem.IsMacOS())
        {
            return;
        }

        using (var fixture = new ConfigurationFixture())
        using (ConfigurationLoadResult result = InvokeTrustedAnchorLoad(fixture.TrustedAnchor))
        {
            AssertLoadResult(
                result,
                ConfigurationLoadStatus.Missing,
                ConfigurationErrorCode.MissingConfiguration,
                "missing config");
        }

        using (var fixture = new ConfigurationFixture())
        {
            fixture.WriteConfiguration(DisabledDocument);
            Directory.CreateDirectory(fixture.CredentialPath);
            using ConfigurationLoadResult result = InvokeTrustedAnchorLoad(fixture.TrustedAnchor);
            AssertLoadResult(
                result,
                ConfigurationLoadStatus.Disabled,
                ConfigurationErrorCode.None,
                "disabled config with deliberately unusable credential path");
        }

        using (var fixture = new ConfigurationFixture())
        {
            fixture.WriteConfiguration(EnabledDocument + "\n");
            using ConfigurationLoadResult result = InvokeTrustedAnchorLoad(fixture.TrustedAnchor);
            AssertLoadResult(
                result,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.InvalidConfiguration,
                "non-canonical config");
        }

        using (var fixture = new ConfigurationFixture())
        {
            fixture.WriteConfiguration(EnabledDocument);
            using ConfigurationLoadResult result = InvokeTrustedAnchorLoad(fixture.TrustedAnchor);
            AssertLoadResult(
                result,
                ConfigurationLoadStatus.Missing,
                ConfigurationErrorCode.MissingCredential,
                "enabled config without credential");
        }

        using (var fixture = new ConfigurationFixture())
        {
            fixture.WriteConfiguration(EnabledDocument);
            fixture.WriteCredential(new string('A', 64));
            using ConfigurationLoadResult result = InvokeTrustedAnchorLoad(fixture.TrustedAnchor);
            AssertLoadResult(
                result,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.InvalidCredential,
                "uppercase credential");
        }

        using (var fixture = new ConfigurationFixture())
        {
            const string credential = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
            byte[] credentialBytes = Encoding.ASCII.GetBytes(credential);
            fixture.WriteConfiguration(EnabledDocument);
            fixture.WriteCredential(credential);

            ConfigurationLoadResult result = InvokeTrustedAnchorLoad(fixture.TrustedAnchor);
            AssertLoadResult(
                result,
                ConfigurationLoadStatus.Enabled,
                ConfigurationErrorCode.None,
                "enabled config");
            LoadedBridgeConfiguration configuration = result.Configuration
                ?? throw new InvalidOperationException("enabled load did not return a configuration");
            TestAssert.Equal("127.0.0.1", configuration.BindAddress, "fixed bind address");
            TestAssert.Equal(43117, configuration.Port, "fixed listener port");
            TestAssert.True(
                configuration.Authenticator.Matches(credentialBytes),
                "exact lowercase credential authenticates");

            result.Dispose();
            TestAssert.False(
                configuration.Authenticator.Matches(credentialBytes),
                "disposing the load result disposes the retained secret");
            result.Dispose();
            CryptographicOperations.ZeroMemory(credentialBytes);
        }
    }

    private static void FullLoadFilesystemShapesFailClosed()
    {
        if (!OperatingSystem.IsMacOS())
        {
            return;
        }

        UnixFileMode directoryMode =
            UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute;
        UnixFileMode fileMode = UnixFileMode.UserRead | UnixFileMode.UserWrite;

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            File.SetUnixFileMode(fixture.BridgeRootPath, directoryMode | UnixFileMode.GroupRead);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.InvalidPermissions,
                "bridge-root mode");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            File.SetUnixFileMode(fixture.MilestonePath, directoryMode | UnixFileMode.GroupExecute);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.InvalidPermissions,
                "milestone mode");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            File.SetUnixFileMode(fixture.ConfigurationPath, fileMode | UnixFileMode.GroupRead);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.InvalidPermissions,
                "config mode");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            File.SetUnixFileMode(fixture.CredentialPath, fileMode | UnixFileMode.GroupRead);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.InvalidPermissions,
                "credential mode");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            Directory.Delete(fixture.BridgeRootPath, recursive: true);
            string target = Path.Combine(fixture.TrustedAnchor, "bridge-target");
            Directory.CreateDirectory(target);
            Directory.CreateSymbolicLink(fixture.BridgeRootPath, target);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.UnsafePath,
                "bridge-root symlink");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            Directory.Delete(fixture.MilestonePath, recursive: true);
            string target = Path.Combine(fixture.TrustedAnchor, "milestone-target");
            Directory.CreateDirectory(target);
            Directory.CreateSymbolicLink(fixture.MilestonePath, target);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.UnsafePath,
                "milestone symlink");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            File.Delete(fixture.ConfigurationPath);
            string target = Path.Combine(fixture.TrustedAnchor, "config-target");
            File.WriteAllText(target, EnabledDocument, Encoding.UTF8);
            File.SetUnixFileMode(target, fileMode);
            File.CreateSymbolicLink(fixture.ConfigurationPath, target);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.UnsafePath,
                "config symlink");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            File.Delete(fixture.CredentialPath);
            string target = Path.Combine(fixture.TrustedAnchor, "credential-target");
            File.WriteAllText(target, new string('a', 64), Encoding.ASCII);
            File.SetUnixFileMode(target, fileMode);
            File.CreateSymbolicLink(fixture.CredentialPath, target);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Invalid,
                ConfigurationErrorCode.UnsafePath,
                "credential symlink");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            Directory.Delete(fixture.BridgeRootPath, recursive: true);
            File.WriteAllBytes(fixture.BridgeRootPath, new byte[] { 1 });
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Missing,
                ConfigurationErrorCode.MissingConfiguration,
                "regular file cannot enable a directory component");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            File.Delete(fixture.ConfigurationPath);
            Directory.CreateDirectory(fixture.ConfigurationPath);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Missing,
                ConfigurationErrorCode.MissingConfiguration,
                "directory cannot enable a config file");
        }

        using (var fixture = ConfigurationFixture.CreateEnabled())
        {
            File.Delete(fixture.CredentialPath);
            Directory.CreateDirectory(fixture.CredentialPath);
            AssertRejectedLoad(
                fixture,
                ConfigurationLoadStatus.Missing,
                ConfigurationErrorCode.MissingCredential,
                "directory cannot enable a credential file");
        }
    }

    [SupportedOSPlatform("macos")]
    private static void AssertRejectedLoad(
        ConfigurationFixture fixture,
        ConfigurationLoadStatus expectedStatus,
        ConfigurationErrorCode expectedError,
        string message)
    {
        using ConfigurationLoadResult result = InvokeTrustedAnchorLoad(fixture.TrustedAnchor);
        AssertLoadResult(result, expectedStatus, expectedError, message);
        TestAssert.False(result.IsEnabled, message + " must fail closed");
        TestAssert.True(result.Configuration is null, message + " must not expose configuration");
    }

    private static void AssertLoadResult(
        ConfigurationLoadResult result,
        ConfigurationLoadStatus expectedStatus,
        ConfigurationErrorCode expectedError,
        string message)
    {
        TestAssert.Equal(expectedStatus, result.Status, message + " status");
        TestAssert.Equal(expectedError, result.ErrorCode, message + " error");
    }

    private static ConfigurationLoadResult InvokeTrustedAnchorLoad(string trustedAnchor)
    {
        FieldInfo field = typeof(StrictConfigurationLoader).GetField(
                "TestTrustedAnchorOverride",
                BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException("Missing configuration test seam");
        TestAssert.True(field.GetValue(null) is null, "configuration test seam starts reset");
        try
        {
            field.SetValue(null, trustedAnchor);
            return new StrictConfigurationLoader().Load();
        }
        finally
        {
            field.SetValue(null, null);
            TestAssert.True(field.GetValue(null) is null, "configuration test seam is reset");
        }
    }

    private static void FixedPathHelpersFailClosedOnUnsafeFilesystemShapes()
    {
        if (!OperatingSystem.IsMacOS())
        {
            return;
        }

        string fixtureRoot = Path.Combine(
            Path.GetTempPath(),
            "sts2-agent-r0a-config-shape-test-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(fixtureRoot);
        string safeDirectory = Path.Combine(fixtureRoot, "safe-directory");
        string wrongModeDirectory = Path.Combine(fixtureRoot, "wrong-mode-directory");
        string directoryLink = Path.Combine(fixtureRoot, "directory-link");
        string safeFile = Path.Combine(fixtureRoot, "safe-file");
        string wrongModeFile = Path.Combine(fixtureRoot, "wrong-mode-file");
        string fileLink = Path.Combine(fixtureRoot, "file-link");
        UnixFileMode directoryMode =
            UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute;
        UnixFileMode fileMode = UnixFileMode.UserRead | UnixFileMode.UserWrite;

        try
        {
            Directory.CreateDirectory(safeDirectory);
            Directory.CreateDirectory(wrongModeDirectory);
            File.SetUnixFileMode(safeDirectory, directoryMode);
            File.SetUnixFileMode(
                wrongModeDirectory,
                directoryMode | UnixFileMode.GroupRead | UnixFileMode.GroupExecute);
            Directory.CreateSymbolicLink(directoryLink, safeDirectory);

            File.WriteAllBytes(safeFile, new byte[] { 1 });
            File.WriteAllBytes(wrongModeFile, new byte[] { 2 });
            File.SetUnixFileMode(safeFile, fileMode);
            File.SetUnixFileMode(wrongModeFile, fileMode | UnixFileMode.GroupRead);
            File.CreateSymbolicLink(fileLink, safeFile);

            TestAssert.Equal("Safe", InvokeComponentCheck("CheckDirectory", safeDirectory, directoryMode), "0700 directory");
            TestAssert.Equal("WrongMode", InvokeComponentCheck("CheckDirectory", wrongModeDirectory, directoryMode), "non-0700 directory");
            TestAssert.Equal("Unsafe", InvokeComponentCheck("CheckDirectory", directoryLink, directoryMode), "directory symlink");
            TestAssert.False(
                InvokeComponentCheck("CheckDirectory", safeFile, directoryMode) == "Safe",
                "regular file cannot satisfy a directory component");
            TestAssert.Equal(
                "Missing",
                InvokeComponentCheck("CheckDirectory", Path.Combine(fixtureRoot, "missing"), directoryMode),
                "missing directory");

            TestAssert.Equal("Safe", InvokeComponentCheck("CheckFile", safeFile, fileMode), "0600 regular file");
            TestAssert.Equal("WrongMode", InvokeComponentCheck("CheckFile", wrongModeFile, fileMode), "non-0600 file");
            TestAssert.Equal("Unsafe", InvokeComponentCheck("CheckFile", fileLink, fileMode), "file symlink");
            TestAssert.False(
                InvokeComponentCheck("CheckFile", safeDirectory, fileMode) == "Safe",
                "directory cannot satisfy a file component");
            TestAssert.Equal(
                "Missing",
                InvokeComponentCheck("CheckFile", Path.Combine(fixtureRoot, "missing-file"), fileMode),
                "missing file");

            MethodInfo append = RequirePrivateStaticMethod("TryAppendFixedComponent");
            object?[] safeAppend = { fixtureRoot, "child", null };
            TestAssert.True((bool)(append.Invoke(null, safeAppend) ?? false), "fixed child remains contained");
            TestAssert.Equal(Path.Combine(fixtureRoot, "child"), safeAppend[2] as string, "fixed child path");
            object?[] escapingAppend = { fixtureRoot, "../escape", null };
            TestAssert.False((bool)(append.Invoke(null, escapingAppend) ?? true), "escaping component is rejected");
            TestAssert.Equal(string.Empty, escapingAppend[2] as string, "rejected component exposes no path");
        }
        finally
        {
            Directory.Delete(fixtureRoot, recursive: true);
        }
    }

    private static void BoundedReadHelperEnforcesTheExactCap()
    {
        TestAssert.True(InvokeCompleteReadCheck(0, 0, 0), "empty read is complete");
        TestAssert.True(InvokeCompleteReadCheck(4, 4, 4), "exact-cap read is complete");
        TestAssert.False(InvokeCompleteReadCheck(4, 3, 4), "short read is incomplete");
        TestAssert.False(InvokeCompleteReadCheck(5, 5, 4), "cap-plus-one read is incomplete");

        string fixtureRoot = Path.Combine(
            Path.GetTempPath(),
            "sts2-agent-r0a-config-read-test-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(fixtureRoot);
        string emptyFile = Path.Combine(fixtureRoot, "empty");
        string exactFile = Path.Combine(fixtureRoot, "exact");
        string oversizeFile = Path.Combine(fixtureRoot, "oversize");
        string linkFile = Path.Combine(fixtureRoot, "link");
        byte[] exactContent = { 1, 2, 3, 4 };

        try
        {
            File.WriteAllBytes(emptyFile, Array.Empty<byte>());
            File.WriteAllBytes(exactFile, exactContent);
            File.WriteAllBytes(oversizeFile, new byte[] { 1, 2, 3, 4, 5 });
            File.CreateSymbolicLink(linkFile, exactFile);

            (bool empty, byte[] emptyBuffer, int emptyLength) = InvokeBoundedRead(emptyFile, 0);
            try
            {
                TestAssert.True(empty, "empty regular file is a complete zero-byte read");
                TestAssert.Equal(0, emptyLength, "empty read length");
            }
            finally
            {
                CryptographicOperations.ZeroMemory(emptyBuffer);
            }

            (bool exact, byte[] buffer, int length) = InvokeBoundedRead(exactFile, 4);
            try
            {
                TestAssert.True(exact, "exact-cap regular file is readable");
                TestAssert.Equal(4, length, "exact-cap read length");
                TestAssert.SequenceEqual(exactContent, buffer.AsSpan(0, length), "exact-cap read bytes");
            }
            finally
            {
                CryptographicOperations.ZeroMemory(buffer);
            }

            (bool oversize, byte[] oversizeBuffer, int oversizeLength) = InvokeBoundedRead(oversizeFile, 4);
            TestAssert.False(oversize, "cap-plus-one file is rejected before transfer");
            TestAssert.Equal(0, oversizeLength, "oversize read exposes no length");
            TestAssert.Equal(0, oversizeBuffer.Length, "oversize read exposes no buffer");

            (bool linked, byte[] linkedBuffer, int linkedLength) = InvokeBoundedRead(linkFile, 4);
            TestAssert.False(linked, "symlink is rejected before transfer");
            TestAssert.Equal(0, linkedLength, "symlink read exposes no length");
            TestAssert.Equal(0, linkedBuffer.Length, "symlink read exposes no buffer");
        }
        finally
        {
            Directory.Delete(fixtureRoot, recursive: true);
        }
    }

    private static string InvokeComponentCheck(string methodName, string path, UnixFileMode mode)
    {
        object? result = RequirePrivateStaticMethod(methodName).Invoke(null, new object?[] { path, mode });
        return result?.ToString() ?? string.Empty;
    }

    private static (bool Success, byte[] Buffer, int Length) InvokeBoundedRead(string path, int cap)
    {
        object?[] arguments = { new FileInfo(path), path, cap, null, 0 };
        bool success = (bool)(RequirePrivateStaticMethod("TryReadBoundedFile").Invoke(null, arguments) ?? false);
        return (success, (byte[])(arguments[3] ?? Array.Empty<byte>()), (int)(arguments[4] ?? 0));
    }

    private static bool InvokeCompleteReadCheck(long expectedLength, int actualLength, int cap)
    {
        object? result = RequirePrivateStaticMethod("IsCompleteBoundedRead").Invoke(
            null,
            new object?[] { expectedLength, actualLength, cap });
        return (bool)(result ?? false);
    }

    private static MethodInfo RequirePrivateStaticMethod(string name)
    {
        return typeof(StrictConfigurationLoader).GetMethod(
                name,
                BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException("Missing configuration helper: " + name);
    }

    private static string HashLowerHex(byte[] value)
    {
        return Convert.ToHexString(SHA256.HashData(value)).ToLowerInvariant();
    }

    [SupportedOSPlatform("macos")]
    private sealed class ConfigurationFixture : IDisposable
    {
        private const string ValidCredential =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

        public ConfigurationFixture()
        {
            TrustedAnchor = Path.Combine(
                Path.GetTempPath(),
                "sts2-agent-r0a-config-load-test-" + Guid.NewGuid().ToString("N"));
            LibraryPath = Path.Combine(TrustedAnchor, "Library");
            ApplicationSupportPath = Path.Combine(LibraryPath, "Application Support");
            BridgeRootPath = Path.Combine(ApplicationSupportPath, "Sts2AgentBridge");
            MilestonePath = Path.Combine(BridgeRootPath, "r0a");
            ConfigurationPath = Path.Combine(MilestonePath, "config.json");
            CredentialPath = Path.Combine(MilestonePath, "credential.hex");

            Directory.CreateDirectory(MilestonePath);
            File.SetUnixFileMode(
                BridgeRootPath,
                UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            File.SetUnixFileMode(
                MilestonePath,
                UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
        }

        public string TrustedAnchor { get; }

        public string LibraryPath { get; }

        public string ApplicationSupportPath { get; }

        public string BridgeRootPath { get; }

        public string MilestonePath { get; }

        public string ConfigurationPath { get; }

        public string CredentialPath { get; }

        public static ConfigurationFixture CreateEnabled()
        {
            var fixture = new ConfigurationFixture();
            fixture.WriteConfiguration(EnabledDocument);
            fixture.WriteCredential(ValidCredential);
            return fixture;
        }

        public void WriteConfiguration(string document)
        {
            File.WriteAllText(ConfigurationPath, document, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            File.SetUnixFileMode(
                ConfigurationPath,
                UnixFileMode.UserRead | UnixFileMode.UserWrite);
        }

        public void WriteCredential(string credential)
        {
            File.WriteAllText(CredentialPath, credential, Encoding.ASCII);
            File.SetUnixFileMode(
                CredentialPath,
                UnixFileMode.UserRead | UnixFileMode.UserWrite);
        }

        public void Dispose()
        {
            Directory.Delete(TrustedAnchor, recursive: true);
        }
    }
}
