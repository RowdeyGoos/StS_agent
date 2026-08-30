using System;
using System.IO;
using System.Runtime.Versioning;
using System.Security.Cryptography;
using System.Text.Json;
using Sts2AgentBridge.Core.Identity;

namespace Sts2AgentBridge.Core.Configuration;

public sealed class StrictConfigurationLoader
{
    public const int MaximumConfigurationBytes = 512;

    private const string LibraryComponent = "Library";
    private const string ApplicationSupportComponent = "Application Support";
    private const string BridgeRootComponent = "Sts2AgentBridge";
    private const string MilestoneComponent = "r0a";
    private const string ConfigurationFileName = "config.json";
    private const string CredentialFileName = "credential.hex";

    private const UnixFileMode ProtectedDirectoryMode =
        UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute;

    private const UnixFileMode ProtectedFileMode =
        UnixFileMode.UserRead | UnixFileMode.UserWrite;

    private static ReadOnlySpan<byte> CanonicalEnabledDocument =>
        "{\"schema_version\":\"live_probe_v0_config_v1\",\"enabled\":true,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

    private static ReadOnlySpan<byte> CanonicalDisabledDocument =>
        "{\"schema_version\":\"live_probe_v0_config_v1\",\"enabled\":false,\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}"u8;

#if STS2_AGENT_BRIDGE_TEST_SEAM
    private static string? TestTrustedAnchorOverride = null;
#endif

    public ConfigurationLoadResult Load()
    {
        if (!OperatingSystem.IsMacOS())
        {
            return ConfigurationLoadResult.UnsupportedPlatform();
        }

        try
        {
            string userProfile = Environment.GetFolderPath(
                Environment.SpecialFolder.UserProfile,
                Environment.SpecialFolderOption.DoNotVerify);

#if STS2_AGENT_BRIDGE_TEST_SEAM
            userProfile = TestTrustedAnchorOverride ?? userProfile;
#endif

            if (string.IsNullOrEmpty(userProfile) || !Path.IsPathFullyQualified(userProfile))
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.UnsafePath);
            }

            string trustedAnchor = Path.GetFullPath(userProfile);
            if (!TryAppendFixedComponent(trustedAnchor, LibraryComponent, out string libraryPath) ||
                !TryAppendFixedComponent(libraryPath, ApplicationSupportComponent, out string applicationSupportPath) ||
                !TryAppendFixedComponent(applicationSupportPath, BridgeRootComponent, out string bridgeRootPath) ||
                !TryAppendFixedComponent(bridgeRootPath, MilestoneComponent, out string milestonePath) ||
                !TryAppendFixedComponent(milestonePath, ConfigurationFileName, out string configurationPath) ||
                !TryAppendFixedComponent(milestonePath, CredentialFileName, out string credentialPath))
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.UnsafePath);
            }

            ComponentCheckResult directoryCheck = CheckDirectory(libraryPath, null);
            if (directoryCheck != ComponentCheckResult.Safe)
            {
                return FromDirectoryFailure(directoryCheck);
            }

            directoryCheck = CheckDirectory(applicationSupportPath, null);
            if (directoryCheck != ComponentCheckResult.Safe)
            {
                return FromDirectoryFailure(directoryCheck);
            }

            directoryCheck = CheckDirectory(bridgeRootPath, ProtectedDirectoryMode);
            if (directoryCheck != ComponentCheckResult.Safe)
            {
                return FromDirectoryFailure(directoryCheck);
            }

            directoryCheck = CheckDirectory(milestonePath, ProtectedDirectoryMode);
            if (directoryCheck != ComponentCheckResult.Safe)
            {
                return FromDirectoryFailure(directoryCheck);
            }

            ComponentCheckResult configurationCheck = CheckFile(configurationPath, ProtectedFileMode);
            if (configurationCheck == ComponentCheckResult.Missing)
            {
                return ConfigurationLoadResult.Missing(ConfigurationErrorCode.MissingConfiguration);
            }

            if (configurationCheck == ComponentCheckResult.WrongMode)
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.InvalidPermissions);
            }

            if (configurationCheck != ComponentCheckResult.Safe)
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.UnsafePath);
            }

            FileInfo configurationInfo = new(configurationPath);
            if (configurationInfo.LinkTarget is not null)
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.UnsafePath);
            }

            if (!TryReadBoundedFile(
                    configurationInfo,
                    configurationPath,
                    MaximumConfigurationBytes,
                    out byte[] configurationBuffer,
                    out int configurationLength))
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.InvalidConfiguration);
            }

            bool enabled;
            try
            {
                if (!TryParseCanonicalDocument(
                        configurationBuffer.AsSpan(0, configurationLength),
                        out enabled))
                {
                    return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.InvalidConfiguration);
                }
            }
            finally
            {
                CryptographicOperations.ZeroMemory(configurationBuffer);
            }

            if (!enabled)
            {
                return ConfigurationLoadResult.Disabled();
            }

            ComponentCheckResult credentialCheck = CheckFile(credentialPath, ProtectedFileMode);
            if (credentialCheck == ComponentCheckResult.Missing)
            {
                return ConfigurationLoadResult.Missing(ConfigurationErrorCode.MissingCredential);
            }

            if (credentialCheck == ComponentCheckResult.WrongMode)
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.InvalidPermissions);
            }

            if (credentialCheck != ComponentCheckResult.Safe)
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.UnsafePath);
            }

            FileInfo credentialInfo = new(credentialPath);
            if (credentialInfo.LinkTarget is not null)
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.UnsafePath);
            }

            if (!TryReadBoundedFile(
                    credentialInfo,
                    credentialPath,
                    FixedTimeAuthenticator.CredentialLength,
                    out byte[] credentialBuffer,
                    out int credentialLength))
            {
                return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.InvalidCredential);
            }

            try
            {
                if (!FixedTimeAuthenticator.TryCreate(
                        credentialBuffer.AsSpan(0, credentialLength),
                        out FixedTimeAuthenticator? authenticator) ||
                    authenticator is null)
                {
                    return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.InvalidCredential);
                }

                return ConfigurationLoadResult.Enabled(new LoadedBridgeConfiguration(authenticator));
            }
            finally
            {
                CryptographicOperations.ZeroMemory(credentialBuffer);
            }
        }
        catch (Exception)
        {
            return ConfigurationLoadResult.Invalid(ConfigurationErrorCode.ReadFailure);
        }
    }

    public static bool TryParseCanonicalDocument(
        ReadOnlySpan<byte> document,
        out bool enabled)
    {
        enabled = false;
        if (document.Length == 0 || document.Length > MaximumConfigurationBytes)
        {
            return false;
        }

        bool schemaSeen = false;
        bool enabledSeen = false;
        bool bindAddressSeen = false;
        bool portSeen = false;
        bool tokenFileSeen = false;
        bool parsedEnabled = false;

        try
        {
            var reader = new Utf8JsonReader(
                document,
                new JsonReaderOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Disallow,
                    MaxDepth = 2,
                });

            if (!reader.Read() || reader.TokenType != JsonTokenType.StartObject)
            {
                return false;
            }

            while (reader.Read())
            {
                if (reader.TokenType == JsonTokenType.EndObject)
                {
                    break;
                }

                if (reader.TokenType != JsonTokenType.PropertyName)
                {
                    return false;
                }

                string? propertyName = reader.GetString();
                if (!reader.Read())
                {
                    return false;
                }

                switch (propertyName)
                {
                    case "schema_version":
                        if (schemaSeen ||
                            reader.TokenType != JsonTokenType.String ||
                            !reader.ValueTextEquals("live_probe_v0_config_v1"))
                        {
                            return false;
                        }

                        schemaSeen = true;
                        break;

                    case "enabled":
                        if (enabledSeen ||
                            reader.TokenType is not JsonTokenType.True and not JsonTokenType.False)
                        {
                            return false;
                        }

                        parsedEnabled = reader.TokenType == JsonTokenType.True;
                        enabledSeen = true;
                        break;

                    case "bind_address":
                        if (bindAddressSeen ||
                            reader.TokenType != JsonTokenType.String ||
                            !reader.ValueTextEquals("127.0.0.1"))
                        {
                            return false;
                        }

                        bindAddressSeen = true;
                        break;

                    case "port":
                        if (portSeen ||
                            reader.TokenType != JsonTokenType.Number ||
                            !reader.TryGetInt32(out int port) ||
                            port != 43117)
                        {
                            return false;
                        }

                        portSeen = true;
                        break;

                    case "token_file":
                        if (tokenFileSeen ||
                            reader.TokenType != JsonTokenType.String ||
                            !reader.ValueTextEquals("credential.hex"))
                        {
                            return false;
                        }

                        tokenFileSeen = true;
                        break;

                    default:
                        return false;
                }
            }

            if (!schemaSeen || !enabledSeen || !bindAddressSeen || !portSeen || !tokenFileSeen)
            {
                return false;
            }

            if (reader.TokenType != JsonTokenType.EndObject || reader.Read())
            {
                return false;
            }
        }
        catch (JsonException)
        {
            return false;
        }

        bool isCanonical = parsedEnabled
            ? document.SequenceEqual(CanonicalEnabledDocument)
            : document.SequenceEqual(CanonicalDisabledDocument);
        if (isCanonical)
        {
            enabled = parsedEnabled;
        }

        return isCanonical;
    }

    private static ConfigurationLoadResult FromDirectoryFailure(ComponentCheckResult result)
    {
        return result switch
        {
            ComponentCheckResult.Missing =>
                ConfigurationLoadResult.Missing(ConfigurationErrorCode.MissingConfiguration),
            ComponentCheckResult.WrongMode =>
                ConfigurationLoadResult.Invalid(ConfigurationErrorCode.InvalidPermissions),
            _ => ConfigurationLoadResult.Invalid(ConfigurationErrorCode.UnsafePath),
        };
    }

    [SupportedOSPlatform("macos")]
    private static ComponentCheckResult CheckDirectory(
        string path,
        UnixFileMode? requiredMode)
    {
        var info = new DirectoryInfo(path);
        if (info.LinkTarget is not null)
        {
            return ComponentCheckResult.Unsafe;
        }

        if (!info.Exists)
        {
            return ComponentCheckResult.Missing;
        }

        FileAttributes attributes = info.Attributes;
        if ((attributes & FileAttributes.Directory) == 0 ||
            (attributes & (FileAttributes.ReparsePoint | FileAttributes.Device)) != 0)
        {
            return ComponentCheckResult.Unsafe;
        }

        if (requiredMode.HasValue && File.GetUnixFileMode(path) != requiredMode.Value)
        {
            return ComponentCheckResult.WrongMode;
        }

        return ComponentCheckResult.Safe;
    }

    [SupportedOSPlatform("macos")]
    private static ComponentCheckResult CheckFile(
        string path,
        UnixFileMode requiredMode)
    {
        var info = new FileInfo(path);
        if (info.LinkTarget is not null)
        {
            return ComponentCheckResult.Unsafe;
        }

        if (!info.Exists)
        {
            return ComponentCheckResult.Missing;
        }

        FileAttributes attributes = info.Attributes;
        if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint | FileAttributes.Device)) != 0)
        {
            return ComponentCheckResult.Unsafe;
        }

        if (File.GetUnixFileMode(path) != requiredMode)
        {
            return ComponentCheckResult.WrongMode;
        }

        return ComponentCheckResult.Safe;
    }

    private static bool TryReadBoundedFile(
        FileInfo info,
        string path,
        int maximumBytes,
        out byte[] buffer,
        out int length)
    {
        buffer = Array.Empty<byte>();
        length = 0;

        if (info.LinkTarget is not null || !info.Exists)
        {
            return false;
        }

        long preOpenLength = info.Length;
        if (preOpenLength < 0 || preOpenLength > maximumBytes)
        {
            return false;
        }

        byte[] localBuffer = new byte[maximumBytes + 1];
        try
        {
            using var stream = new FileStream(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read);

            if (stream.Length != preOpenLength || stream.Length > maximumBytes)
            {
                return false;
            }

            int total = 0;
            while (total < localBuffer.Length)
            {
                int read = stream.Read(localBuffer.AsSpan(total));
                if (read == 0)
                {
                    break;
                }

                total += read;
            }

            if (!IsCompleteBoundedRead(preOpenLength, total, maximumBytes))
            {
                return false;
            }

            info.Refresh();
            if (info.LinkTarget is not null || !info.Exists || info.Length != preOpenLength)
            {
                return false;
            }

            buffer = localBuffer;
            length = total;
            return true;
        }
        finally
        {
            if (!ReferenceEquals(buffer, localBuffer))
            {
                CryptographicOperations.ZeroMemory(localBuffer);
            }
        }
    }

    private static bool IsCompleteBoundedRead(
        long expectedLength,
        int actualLength,
        int maximumBytes)
    {
        return actualLength <= maximumBytes && actualLength == expectedLength;
    }

    private static bool TryAppendFixedComponent(
        string parent,
        string component,
        out string path)
    {
        string normalizedParent = Path.GetFullPath(parent);
        string combined = Path.Combine(normalizedParent, component);
        string normalized = Path.GetFullPath(combined);
        string expected = normalizedParent.EndsWith(Path.DirectorySeparatorChar)
            ? normalizedParent + component
            : normalizedParent + Path.DirectorySeparatorChar + component;

        if (!string.Equals(normalized, expected, StringComparison.Ordinal))
        {
            path = string.Empty;
            return false;
        }

        path = normalized;
        return true;
    }

    private enum ComponentCheckResult
    {
        Safe = 1,
        Missing = 2,
        Unsafe = 3,
        WrongMode = 4,
    }
}
