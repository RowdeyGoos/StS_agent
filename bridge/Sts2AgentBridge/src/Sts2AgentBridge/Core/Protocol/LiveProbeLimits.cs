namespace Sts2AgentBridge.Core.Protocol;

public static class LiveProbeLimits
{
    public const int SchemaVersion = 1;
    public const string ProtocolName = "live_probe_v0";
    public const string ListenerAddress = "127.0.0.1";
    public const int ListenerPort = 43117;
    public const int ListenerBacklog = 8;
    public const int MaximumConcurrentConnections = 4;
    public const double PreAuthenticationRefillPerSecond = 32.0;
    public const double PreAuthenticationBurst = 16.0;
    public const double AuthenticatedRefillPerSecond = 20.0;
    public const double AuthenticatedBurst = 10.0;
    public const int MaximumRequestLineBytes = 128;
    public const int MaximumRequestHeadBytes = 4096;
    public const int RequestHeadBufferBytes = 4097;
    public const int MaximumHeaderCount = 8;
    public const int MaximumHeaderNameBytes = 32;
    public const int MaximumHeaderValueBytes = 512;
    public const int MaximumRequestTargetBytes = 64;
    public const int MaximumErrorBodyBytes = 512;
    public const int MaximumResponseBodyBytes = 4096;
    public const int HeaderReadTimeoutMilliseconds = 1000;
    public const int ResponseWriteTimeoutMilliseconds = 1000;
    public const int TotalConnectionLifetimeMilliseconds = 2000;
    public const int MaximumOutstandingScreenReads = 2;
    public const int MaximumGameThreadWorkPerFrame = 2;
    public const int GameThreadQueueWaitMilliseconds = 250;
    public const int GameThreadResultWaitMilliseconds = 500;
    public const int WorkerShutdownJoinMilliseconds = 2000;
}
