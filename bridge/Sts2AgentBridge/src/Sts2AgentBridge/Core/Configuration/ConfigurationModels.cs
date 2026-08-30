using System;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Protocol;

namespace Sts2AgentBridge.Core.Configuration;

public enum ConfigurationLoadStatus
{
    Enabled = 1,
    Disabled = 2,
    Missing = 3,
    Invalid = 4,
    UnsupportedPlatform = 5,
}

public enum ConfigurationErrorCode
{
    None = 0,
    UnsupportedPlatform = 1,
    MissingConfiguration = 2,
    UnsafePath = 3,
    InvalidPermissions = 4,
    InvalidConfiguration = 5,
    MissingCredential = 6,
    InvalidCredential = 7,
    ReadFailure = 8,
}

public sealed class LoadedBridgeConfiguration : IDisposable
{
    internal LoadedBridgeConfiguration(FixedTimeAuthenticator authenticator)
    {
        Authenticator = authenticator ?? throw new ArgumentNullException(nameof(authenticator));
    }

    public string BindAddress => LiveProbeLimits.ListenerAddress;

    public int Port => LiveProbeLimits.ListenerPort;

    public FixedTimeAuthenticator Authenticator { get; }

    public void Dispose()
    {
        Authenticator.Dispose();
    }
}

public sealed class ConfigurationLoadResult : IDisposable
{
    private ConfigurationLoadResult(
        ConfigurationLoadStatus status,
        ConfigurationErrorCode errorCode,
        LoadedBridgeConfiguration? configuration)
    {
        Status = status;
        ErrorCode = errorCode;
        Configuration = configuration;
    }

    public ConfigurationLoadStatus Status { get; }

    public ConfigurationErrorCode ErrorCode { get; }

    public LoadedBridgeConfiguration? Configuration { get; }

    public bool IsEnabled => Status == ConfigurationLoadStatus.Enabled;

    internal static ConfigurationLoadResult Enabled(LoadedBridgeConfiguration configuration)
    {
        return new ConfigurationLoadResult(ConfigurationLoadStatus.Enabled, ConfigurationErrorCode.None, configuration);
    }

    internal static ConfigurationLoadResult Disabled()
    {
        return new ConfigurationLoadResult(ConfigurationLoadStatus.Disabled, ConfigurationErrorCode.None, null);
    }

    internal static ConfigurationLoadResult Missing(ConfigurationErrorCode errorCode)
    {
        return new ConfigurationLoadResult(ConfigurationLoadStatus.Missing, errorCode, null);
    }

    internal static ConfigurationLoadResult Invalid(ConfigurationErrorCode errorCode)
    {
        return new ConfigurationLoadResult(ConfigurationLoadStatus.Invalid, errorCode, null);
    }

    internal static ConfigurationLoadResult UnsupportedPlatform()
    {
        return new ConfigurationLoadResult(
            ConfigurationLoadStatus.UnsupportedPlatform,
            ConfigurationErrorCode.UnsupportedPlatform,
            null);
    }

    public void Dispose()
    {
        Configuration?.Dispose();
    }
}
