using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Hosting;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Core.Transport;

namespace Sts2AgentBridge.Tests.Transport;

internal sealed class FakeMonotonicClock : IMonotonicClock
{
    private long _timestamp;

    public FakeMonotonicClock(long frequency = 1_000)
    {
        Frequency = frequency;
    }

    public long Frequency { get; }

    public long GetTimestamp()
    {
        return Interlocked.Read(ref _timestamp);
    }

    public void Set(long timestamp)
    {
        Interlocked.Exchange(ref _timestamp, timestamp);
    }

    public void Advance(long ticks)
    {
        Interlocked.Add(ref _timestamp, ticks);
    }
}

internal sealed class RecordingPublicScreenService : IPublicScreenService
{
    private readonly Func<PublicScreenReadResult> _read;
    private int _calls;

    public RecordingPublicScreenService(Func<PublicScreenReadResult>? read = null)
    {
        _read = read ?? (() => PublicScreenReadResult.FromSnapshot(
            new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.MainMenu)));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicScreenReadResult Read()
    {
        Interlocked.Increment(ref _calls);
        return _read();
    }
}

internal sealed class RecordingPublicCombatDecisionService : IPublicCombatDecisionService
{
    private readonly Func<PublicCombatDecisionReadResult> _read;
    private int _calls;

    public RecordingPublicCombatDecisionService(Func<PublicCombatDecisionReadResult>? read = null)
    {
        _read = read ?? (() => PublicCombatDecisionReadResult.FromSnapshot(
            PublicCombatDecisionSnapshot.Waiting()));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicCombatDecisionReadResult Read()
    {
        Interlocked.Increment(ref _calls);
        return _read();
    }
}

internal sealed class RecordingPublicCombatActionService : IPublicCombatActionService
{
    private readonly Func<PublicCombatActionRequest, PublicCombatActionApplyResult> _apply;
    private int _calls;

    public RecordingPublicCombatActionService(
        Func<PublicCombatActionRequest, PublicCombatActionApplyResult>? apply = null)
    {
        _apply = apply ?? (request => PublicCombatActionApplyResult.FromRequest(
            PublicCombatActionApplyOutcome.Accepted,
            request));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicCombatActionRequest LastRequest { get; private set; }

    public PublicCombatActionApplyResult Apply(PublicCombatActionRequest request)
    {
        LastRequest = request;
        Interlocked.Increment(ref _calls);
        return _apply(request);
    }
}

internal sealed class RecordingPublicRewardDecisionService : IPublicRewardDecisionService
{
    private readonly Func<PublicRewardDecisionReadResult> _read;
    private int _calls;

    public RecordingPublicRewardDecisionService(Func<PublicRewardDecisionReadResult>? read = null)
    {
        _read = read ?? (() => PublicRewardDecisionReadResult.FromSnapshot(
            PublicRewardDecisionSnapshot.Waiting()));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicRewardDecisionReadResult Read()
    {
        Interlocked.Increment(ref _calls);
        return _read();
    }
}

internal sealed class RecordingPublicRewardActionService : IPublicRewardActionService
{
    private readonly Func<PublicRewardActionRequest, PublicRewardActionApplyResult> _apply;
    private int _calls;

    public RecordingPublicRewardActionService(
        Func<PublicRewardActionRequest, PublicRewardActionApplyResult>? apply = null)
    {
        _apply = apply ?? (request => PublicRewardActionApplyResult.FromRequest(
            PublicRewardActionApplyOutcome.Accepted,
            request));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicRewardActionRequest LastRequest { get; private set; }

    public PublicRewardActionApplyResult Apply(PublicRewardActionRequest request)
    {
        LastRequest = request;
        Interlocked.Increment(ref _calls);
        return _apply(request);
    }
}

internal sealed class RecordingPublicMapDecisionService : IPublicMapDecisionService
{
    private readonly Func<PublicMapDecisionReadResult> _read;
    private int _calls;

    public RecordingPublicMapDecisionService(Func<PublicMapDecisionReadResult>? read = null)
    {
        _read = read ?? (() => PublicMapDecisionReadResult.FromSnapshot(
            PublicMapDecisionSnapshot.Waiting()));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicMapDecisionReadResult Read()
    {
        Interlocked.Increment(ref _calls);
        return _read();
    }
}

internal sealed class RecordingPublicMapActionService : IPublicMapActionService
{
    private readonly Func<PublicMapActionRequest, PublicMapActionApplyResult> _apply;
    private int _calls;

    public RecordingPublicMapActionService(
        Func<PublicMapActionRequest, PublicMapActionApplyResult>? apply = null)
    {
        _apply = apply ?? (request => PublicMapActionApplyResult.FromRequest(
            PublicMapActionApplyOutcome.Accepted,
            request));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicMapActionRequest LastRequest { get; private set; }

    public PublicMapActionApplyResult Apply(PublicMapActionRequest request)
    {
        LastRequest = request;
        Interlocked.Increment(ref _calls);
        return _apply(request);
    }
}

internal sealed class RecordingPublicRoomDecisionService : IPublicRoomDecisionService
{
    private readonly Func<PublicRoomDecisionReadResult> _read;
    private int _calls;

    public RecordingPublicRoomDecisionService(Func<PublicRoomDecisionReadResult>? read = null)
    {
        _read = read ?? (() => PublicRoomDecisionReadResult.FromSnapshot(
            PublicRoomDecisionSnapshot.Waiting()));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicRoomDecisionReadResult Read()
    {
        Interlocked.Increment(ref _calls);
        return _read();
    }
}

internal sealed class RecordingPublicRoomActionService : IPublicRoomActionService
{
    private readonly Func<PublicRoomActionRequest, PublicRoomActionApplyResult> _apply;
    private int _calls;

    public RecordingPublicRoomActionService(
        Func<PublicRoomActionRequest, PublicRoomActionApplyResult>? apply = null)
    {
        _apply = apply ?? (request => PublicRoomActionApplyResult.FromRequest(
            PublicRoomActionApplyOutcome.Accepted,
            request));
    }

    public int Calls => Volatile.Read(ref _calls);

    public PublicRoomActionRequest LastRequest { get; private set; }

    public PublicRoomActionApplyResult Apply(PublicRoomActionRequest request)
    {
        LastRequest = request;
        Interlocked.Increment(ref _calls);
        return _apply(request);
    }
}

internal sealed class TransportProcessorFixture : IDisposable
{
    public const string Credential =
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    public const string ProcessCorrelationId =
        "11111111111111111111111111111111";

    public TransportProcessorFixture(
        ProbeMode mode = ProbeMode.Compatible,
        RecordingPublicScreenService? service = null,
        RecordingPublicCombatDecisionService? decisionService = null,
        RecordingPublicCombatActionService? actionService = null,
        RecordingPublicRewardDecisionService? rewardDecisionService = null,
        RecordingPublicRewardActionService? rewardActionService = null,
        RecordingPublicMapDecisionService? mapDecisionService = null,
        RecordingPublicMapActionService? mapActionService = null,
        RecordingPublicRoomDecisionService? roomDecisionService = null,
        RecordingPublicRoomActionService? roomActionService = null)
    {
        byte[] secret = Encoding.ASCII.GetBytes(Credential);
        TestAssert.True(
            FixedTimeAuthenticator.TryCreate(secret, out FixedTimeAuthenticator? authenticator) &&
            authenticator is not null,
            "transport fixture authenticator");
        Authenticator = authenticator!;
        Clock = new FakeMonotonicClock();

        if (mode == ProbeMode.Compatible)
        {
            Queue = new BoundedFrameWorkQueue();
            Service = service ?? new RecordingPublicScreenService();
            DecisionService = decisionService ?? new RecordingPublicCombatDecisionService();
            ActionService = actionService ?? new RecordingPublicCombatActionService();
            RewardDecisionService = rewardDecisionService ?? new RecordingPublicRewardDecisionService();
            RewardActionService = rewardActionService ?? new RecordingPublicRewardActionService();
            MapDecisionService = mapDecisionService ?? new RecordingPublicMapDecisionService();
            MapActionService = mapActionService ?? new RecordingPublicMapActionService();
            RoomDecisionService = roomDecisionService ?? new RecordingPublicRoomDecisionService();
            RoomActionService = roomActionService ?? new RecordingPublicRoomActionService();
        }

        Processor = new ProbeRequestProcessor(
            mode,
            ProcessCorrelationId,
            Authenticator,
            Queue,
            Service,
            new MonotonicTokenBucket(
                LiveProbeLimits.AuthenticatedRefillPerSecond,
                LiveProbeLimits.AuthenticatedBurst,
                Clock),
            DecisionService,
            ActionService,
            RewardDecisionService,
            RewardActionService,
            MapDecisionService,
            MapActionService,
            RoomDecisionService,
            RoomActionService);
    }

    public FixedTimeAuthenticator Authenticator { get; }

    public FakeMonotonicClock Clock { get; }

    public BoundedFrameWorkQueue? Queue { get; }

    public RecordingPublicScreenService? Service { get; }

    public RecordingPublicCombatDecisionService? DecisionService { get; }

    public RecordingPublicCombatActionService? ActionService { get; }

    public RecordingPublicRewardDecisionService? RewardDecisionService { get; }

    public RecordingPublicRewardActionService? RewardActionService { get; }

    public RecordingPublicMapDecisionService? MapDecisionService { get; }

    public RecordingPublicMapActionService? MapActionService { get; }

    public RecordingPublicRoomDecisionService? RoomDecisionService { get; }

    public RecordingPublicRoomActionService? RoomActionService { get; }

    public ProbeRequestProcessor Processor { get; }

    public void Dispose()
    {
        Queue?.Stop();
        Authenticator.Dispose();
    }

    public ProbeProcessingResult Process(string request)
    {
        return Processor.Process(Encoding.ASCII.GetBytes(request));
    }

    public ProbeProcessingResult ProcessScreen(string request)
    {
        if (Queue is null)
        {
            return Process(request);
        }

        Task<ProbeProcessingResult> task = Task.Run(() => Process(request));
        bool queued = SpinWait.SpinUntil(
            () => Queue.OutstandingCount == 1 || task.IsCompleted,
            TimeSpan.FromSeconds(1));
        TestAssert.True(queued, "screen request should queue or complete");
        if (!task.IsCompleted)
        {
            bool drained = SpinWait.SpinUntil(
                () =>
                {
                    Queue.DrainFrame();
                    return task.IsCompleted;
                },
                TimeSpan.FromMilliseconds(200));
            TestAssert.True(drained, "screen request should drain");
        }

        return task.GetAwaiter().GetResult();
    }

    public static string Request(
        string target = "/probe/v0/health",
        string method = "GET",
        string? host = "127.0.0.1:43117",
        string? authorization = "Bearer " + Credential,
        params string[] additionalHeaders)
    {
        var builder = new StringBuilder();
        builder.Append(method).Append(' ').Append(target).Append(" HTTP/1.1\r\n");
        if (host is not null)
        {
            builder.Append("Host: ").Append(host).Append("\r\n");
        }

        if (authorization is not null)
        {
            builder.Append("Authorization: ").Append(authorization).Append("\r\n");
        }

        foreach (string header in additionalHeaders)
        {
            builder.Append(header).Append("\r\n");
        }

        builder.Append("\r\n");
        return builder.ToString();
    }

    public static void AssertStatus(int status, ProbeProcessingResult result, string message)
    {
        TestAssert.True(result.ShouldRespond, message + " should respond");
        string prefix = "HTTP/1.1 " + status + " ";
        TestAssert.True(
            Encoding.ASCII.GetString(result.Response).StartsWith(prefix, StringComparison.Ordinal),
            message + " status");
    }
}
