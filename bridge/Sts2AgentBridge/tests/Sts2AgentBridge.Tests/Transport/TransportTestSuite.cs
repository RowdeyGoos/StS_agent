using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Core.Transport;

namespace Sts2AgentBridge.Tests.Transport;

internal static class TransportTestSuite
{
    public static void Run()
    {
        CanonicalRequestParsesWithoutGeneralHttpFeatures();
        EveryParserBoundIsExact();
        TokenBucketsUseInjectedMonotonicTicks();
        PreAuthenticationAdmissionIsWiredBeforeWorkerAllocation();
        RouterServesExactRoutesAndScreenOutcomes();
        ScreenQueueCapacityMapsToRateLimited();
        BoundedReceiverHandlesFragmentationAndOverflow();
        HandlerCapAndCancellationCloseSilently();
        AcceptedSocketHandlerSendsExactlyOneResponse();
        ProductionAcceptLoopBindsAcceptsRejectsCollisionAndJoins();
    }

    private static void CanonicalRequestParsesWithoutGeneralHttpFeatures()
    {
        byte[] request = Encoding.ASCII.GetBytes(TransportProcessorFixture.Request());
        ProbeRequestParseResult parsed = ProbeRequestParser.Parse(request);
        TestAssert.Equal(ProbeRequestParseStatus.Parsed, parsed.Status, "canonical parse status");
        TestAssert.True(parsed.Request.IsGet, "canonical GET");
        TestAssert.False(parsed.Request.IsPost, "canonical request is not POST");
        TestAssert.Equal(ParsedRouteTarget.Health, parsed.Request.RouteTarget, "canonical route");
        TestAssert.Equal(ParsedHostState.Exact, parsed.Request.HostState, "canonical host");
        TestAssert.Equal(1, parsed.Request.AuthorizationCount, "canonical authorization count");
        TestAssert.False(parsed.Request.HasOrigin, "canonical request has no Origin");

        string decisionId = new string('0', 64);
        byte[] actionRequest = Encoding.ASCII.GetBytes(
            TransportProcessorFixture.Request(
                target: "/probe/v0/public/combat-action",
                method: "POST",
                additionalHeaders: new[]
                {
                    "X-Sts2-Decision-Id: " + decisionId,
                    "X-Sts2-Action-Id: play:0:0",
                }));
        ProbeRequestParseResult parsedAction = ProbeRequestParser.Parse(actionRequest);
        TestAssert.Equal(ProbeRequestParseStatus.Parsed, parsedAction.Status, "canonical action parse status");
        TestAssert.True(parsedAction.Request.IsPost, "canonical action POST");
        TestAssert.Equal(1, parsedAction.Request.DecisionIdCount, "canonical decision ID count");
        TestAssert.Equal(1, parsedAction.Request.ActionIdCount, "canonical action ID count");

        ProbeRequestParseResult pipelined = ProbeRequestParser.Parse(
            Encoding.ASCII.GetBytes(
                TransportProcessorFixture.Request() + TransportProcessorFixture.Request()));
        TestAssert.Equal(ProbeRequestParseStatus.SilentClose, pipelined.Status, "pipelined bytes close silently");
    }

    private static void EveryParserBoundIsExact()
    {
        AssertRequestLineLength(127, ProbeRequestParseStatus.Parsed);
        AssertRequestLineLength(128, ProbeRequestParseStatus.Parsed);
        AssertRequestLineLength(129, ProbeRequestParseStatus.PayloadTooLarge);

        AssertTargetLength(63, ProbeRequestParseStatus.Parsed);
        AssertTargetLength(64, ProbeRequestParseStatus.Parsed);
        AssertTargetLength(65, ProbeRequestParseStatus.PayloadTooLarge);

        AssertHeaderNameLength(31, ProbeRequestParseStatus.InvalidRequest);
        AssertHeaderNameLength(32, ProbeRequestParseStatus.InvalidRequest);
        AssertHeaderNameLength(33, ProbeRequestParseStatus.PayloadTooLarge);

        AssertHeaderValueLength(511, ProbeRequestParseStatus.Parsed);
        AssertHeaderValueLength(512, ProbeRequestParseStatus.Parsed);
        AssertHeaderValueLength(513, ProbeRequestParseStatus.PayloadTooLarge);

        AssertHeaderCount(7, ProbeRequestParseStatus.InvalidRequest);
        AssertHeaderCount(8, ProbeRequestParseStatus.InvalidRequest);
        AssertHeaderCount(9, ProbeRequestParseStatus.PayloadTooLarge);

        AssertCompleteHeadLength(4_095, ProbeRequestParseStatus.InvalidRequest);
        AssertCompleteHeadLength(4_096, ProbeRequestParseStatus.InvalidRequest);
        AssertCompleteHeadLength(4_097, ProbeRequestParseStatus.PayloadTooLarge);
    }

    private static void TokenBucketsUseInjectedMonotonicTicks()
    {
        var clock = new FakeMonotonicClock();
        var bucket = new MonotonicTokenBucket(2.0, 3.0, clock);
        TestAssert.True(bucket.TryConsume(), "bucket token 1");
        TestAssert.True(bucket.TryConsume(), "bucket token 2");
        TestAssert.True(bucket.TryConsume(), "bucket token 3");
        TestAssert.False(bucket.TryConsume(), "empty bucket");

        clock.Advance(499);
        TestAssert.False(bucket.TryConsume(), "fractional token is insufficient");
        clock.Advance(1);
        TestAssert.True(bucket.TryConsume(), "fractional refills accumulate exactly");

        clock.Set(100);
        TestAssert.False(bucket.TryConsume(), "negative elapsed time is clamped");
        clock.Advance(100_000);
        TestAssert.True(bucket.TryConsume(), "large refill token 1");
        TestAssert.True(bucket.TryConsume(), "large refill token 2");
        TestAssert.True(bucket.TryConsume(), "large refill token 3");
        TestAssert.False(bucket.TryConsume(), "large refill is clamped to capacity");
    }

    private static void RouterServesExactRoutesAndScreenOutcomes()
    {
        using (var fixture = new TransportProcessorFixture())
        {
            ProbeProcessingResult health = fixture.Process(TransportProcessorFixture.Request());
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodeHealthResponse(TransportProcessorFixture.ProcessCorrelationId),
                health.Response,
                "health response");

            ProbeProcessingResult manifest = fixture.Process(
                TransportProcessorFixture.Request(target: "/probe/v0/manifest"));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodeManifestResponse(ProbeMode.Compatible),
                manifest.Response,
                "compatible manifest response");

            ProbeProcessingResult screen = fixture.ProcessScreen(
                TransportProcessorFixture.Request(target: "/probe/v0/public/screen"));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicScreenResponse(
                    new PublicScreenSnapshot(PublicScreenStatus.Ready, PublicScreenKind.MainMenu)),
                screen.Response,
                "screen response");
            TestAssert.Equal(1, fixture.Service!.Calls, "one public-screen service call");

            ProbeProcessingResult decision = fixture.ProcessScreen(
                TransportProcessorFixture.Request(target: "/probe/v0/public/combat-decision"));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicCombatDecisionResponse(
                    PublicCombatDecisionSnapshot.Waiting()),
                decision.Response,
                "combat decision response");
            TestAssert.Equal(1, fixture.DecisionService!.Calls, "one combat-decision service call");

            string decisionId = new string('0', 64);
            PublicCombatActionRequest.TryCreate(
                decisionId,
                "play:0:0",
                out PublicCombatActionRequest actionRequest);
            ProbeProcessingResult action = fixture.ProcessScreen(
                TransportProcessorFixture.Request(
                    target: "/probe/v0/public/combat-action",
                    method: "POST",
                    additionalHeaders: new[]
                    {
                        "X-Sts2-Decision-Id: " + decisionId,
                        "X-Sts2-Action-Id: play:0:0",
                    }));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicCombatActionResponse(
                    PublicCombatActionApplyResult.FromRequest(
                        PublicCombatActionApplyOutcome.Accepted,
                        actionRequest)),
                action.Response,
                "combat action response");
            TestAssert.Equal(1, fixture.ActionService!.Calls, "one combat-action service call");
            TestAssert.Equal(actionRequest, fixture.ActionService.LastRequest, "exact combat action request");

            ProbeProcessingResult rewardDecision = fixture.ProcessScreen(
                TransportProcessorFixture.Request(target: "/probe/v0/public/reward-decision"));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicRewardDecisionResponse(
                    PublicRewardDecisionSnapshot.Waiting()),
                rewardDecision.Response,
                "reward decision response");
            TestAssert.Equal(1, fixture.RewardDecisionService!.Calls, "one reward-decision service call");

            PublicRewardActionRequest.TryCreate(
                decisionId,
                PublicRewardActionRequest.ProceedActionId,
                out PublicRewardActionRequest rewardActionRequest);
            ProbeProcessingResult rewardAction = fixture.ProcessScreen(
                TransportProcessorFixture.Request(
                    target: "/probe/v0/public/reward-action",
                    method: "POST",
                    additionalHeaders: new[]
                    {
                        "X-Sts2-Decision-Id: " + decisionId,
                        "X-Sts2-Action-Id: proceed",
                    }));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicRewardActionResponse(
                    PublicRewardActionApplyResult.FromRequest(
                        PublicRewardActionApplyOutcome.Accepted,
                        rewardActionRequest)),
                rewardAction.Response,
                "reward action response");
            TestAssert.Equal(1, fixture.RewardActionService!.Calls, "one reward-action service call");
            TestAssert.Equal(
                rewardActionRequest,
                fixture.RewardActionService.LastRequest,
                "exact reward action request");

            ProbeProcessingResult mapDecision = fixture.ProcessScreen(
                TransportProcessorFixture.Request(target: "/probe/v0/public/map-decision"));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicMapDecisionResponse(
                    PublicMapDecisionSnapshot.Waiting()),
                mapDecision.Response,
                "map decision response");
            TestAssert.Equal(1, fixture.MapDecisionService!.Calls, "one map-decision service call");

            PublicMapActionRequest.TryCreate(
                decisionId,
                "select:0",
                out PublicMapActionRequest mapActionRequest);
            ProbeProcessingResult mapAction = fixture.ProcessScreen(
                TransportProcessorFixture.Request(
                    target: "/probe/v0/public/map-action",
                    method: "POST",
                    additionalHeaders: new[]
                    {
                        "X-Sts2-Decision-Id: " + decisionId,
                        "X-Sts2-Action-Id: select:0",
                    }));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicMapActionResponse(
                    PublicMapActionApplyResult.FromRequest(
                        PublicMapActionApplyOutcome.Accepted,
                        mapActionRequest)),
                mapAction.Response,
                "map action response");
            TestAssert.Equal(1, fixture.MapActionService!.Calls, "one map-action service call");
            TestAssert.Equal(mapActionRequest, fixture.MapActionService.LastRequest, "exact map action request");

            ProbeProcessingResult roomDecision = fixture.ProcessScreen(
                TransportProcessorFixture.Request(target: "/probe/v0/public/room-decision"));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicRoomDecisionResponse(
                    PublicRoomDecisionSnapshot.Waiting()),
                roomDecision.Response,
                "room decision response");
            TestAssert.Equal(1, fixture.RoomDecisionService!.Calls, "one room-decision service call");

            fixture.Clock.Advance(50);

            PublicRoomActionRequest.TryCreate(
                decisionId,
                PublicRoomActionRequest.ProceedActionId,
                out PublicRoomActionRequest roomActionRequest);
            ProbeProcessingResult roomAction = fixture.ProcessScreen(
                TransportProcessorFixture.Request(
                    target: "/probe/v0/public/room-action",
                    method: "POST",
                    additionalHeaders: new[]
                    {
                        "X-Sts2-Decision-Id: " + decisionId,
                        "X-Sts2-Action-Id: proceed",
                    }));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodePublicRoomActionResponse(
                    PublicRoomActionApplyResult.FromRequest(
                        PublicRoomActionApplyOutcome.Accepted,
                        roomActionRequest)),
                roomAction.Response,
                "room action response");
            TestAssert.Equal(1, fixture.RoomActionService!.Calls, "one room-action service call");
            TestAssert.Equal(roomActionRequest, fixture.RoomActionService.LastRequest, "exact room action request");
        }

        using (var fixture = new TransportProcessorFixture(ProbeMode.IncompatibleLocked))
        {
            ProbeProcessingResult manifest = fixture.Process(
                TransportProcessorFixture.Request(target: "/probe/v0/manifest"));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodeManifestResponse(ProbeMode.IncompatibleLocked),
                manifest.Response,
                "locked manifest response");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(TransportProcessorFixture.Request(target: "/probe/v0/public/screen")),
                "locked screen route");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(
                    TransportProcessorFixture.Request(target: "/probe/v0/public/combat-decision")),
                "locked combat decision route");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(
                    TransportProcessorFixture.Request(
                        target: "/probe/v0/public/combat-action",
                        method: "POST")),
                "locked combat action route");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(
                    TransportProcessorFixture.Request(target: "/probe/v0/public/reward-decision")),
                "locked reward decision route");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(
                    TransportProcessorFixture.Request(
                        target: "/probe/v0/public/reward-action",
                        method: "POST")),
                "locked reward action route");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(
                    TransportProcessorFixture.Request(target: "/probe/v0/public/map-decision")),
                "locked map decision route");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(
                    TransportProcessorFixture.Request(
                        target: "/probe/v0/public/map-action",
                        method: "POST")),
                "locked map action route");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(
                    TransportProcessorFixture.Request(target: "/probe/v0/public/room-decision")),
                "locked room decision route");
            TransportProcessorFixture.AssertStatus(
                404,
                fixture.Process(
                    TransportProcessorFixture.Request(
                        target: "/probe/v0/public/room-action",
                        method: "POST")),
                "locked room action route");
        }

        var backendFaultService = new RecordingPublicScreenService(
            PublicScreenReadResult.BackendFault);
        using (var fixture = new TransportProcessorFixture(service: backendFaultService))
        {
            TransportProcessorFixture.AssertStatus(
                503,
                fixture.ProcessScreen(
                    TransportProcessorFixture.Request(target: "/probe/v0/public/screen")),
                "reader backend fault");
        }

        var throwingService = new RecordingPublicScreenService(
            () => throw new InvalidOperationException("fixture-secret-path-request-game-type"));
        using (var fixture = new TransportProcessorFixture(service: throwingService))
        {
            TransportProcessorFixture.AssertStatus(
                503,
                fixture.ProcessScreen(
                    TransportProcessorFixture.Request(target: "/probe/v0/public/screen")),
                "thrown service fault");
        }

        using (var fixture = new TransportProcessorFixture())
        {
            fixture.Queue!.Stop();
            TransportProcessorFixture.AssertStatus(
                503,
                fixture.Process(
                    TransportProcessorFixture.Request(target: "/probe/v0/public/screen")),
                "stopped dispatcher queue");
            TestAssert.Equal(0, fixture.Service!.Calls, "unavailable queue never invokes service");
        }
    }

    private static void PreAuthenticationAdmissionIsWiredBeforeWorkerAllocation()
    {
        using var fixture = new TransportProcessorFixture();
        var preAuthenticationClock = new FakeMonotonicClock();
        using var server = new BoundedLoopbackServer(
            ProbeMode.Compatible,
            TransportProcessorFixture.ProcessCorrelationId,
            fixture.Authenticator,
            fixture.Queue,
            fixture.Service,
            preAuthenticationClock,
            new FakeMonotonicClock(),
            fixture.DecisionService,
            fixture.ActionService,
            fixture.RewardDecisionService,
            fixture.RewardActionService,
            fixture.MapDecisionService,
            fixture.MapActionService,
            fixture.RoomDecisionService,
            fixture.RoomActionService);

        for (int index = 0; index < 16; index++)
        {
            TestAssert.True(server.TryAdmitAcceptedConnection(), "pre-auth burst token " + index);
        }

        TestAssert.False(server.TryAdmitAcceptedConnection(), "pre-auth burst exhaustion is silent admission failure");

        MethodInfo? acceptLoop = typeof(BoundedLoopbackServer).GetMethod(
            "AcceptLoopAsync",
            BindingFlags.Instance | BindingFlags.NonPublic);
        TestAssert.True(acceptLoop is not null, "exact accept loop method");
        AsyncStateMachineAttribute? stateMachine =
            acceptLoop!.GetCustomAttribute<AsyncStateMachineAttribute>();
        TestAssert.True(stateMachine is not null, "accept loop async state machine");
        MethodInfo? moveNext = stateMachine!.StateMachineType.GetMethod(
            "MoveNext",
            BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
        TestAssert.True(moveNext is not null, "accept loop MoveNext");

        var calls = ResolveCalledMethods(moveNext!);
        int admissionIndex = FindCall(
            calls,
            typeof(BoundedLoopbackServer),
            "TryAdmitAcceptedConnection");
        int disposeIndex = FindCall(calls, typeof(Socket), nameof(Socket.Dispose));
        int handlerIndex = FindCall(
            calls,
            typeof(BoundedLoopbackServer),
            "HandleAcceptedSocketAsync");
        TestAssert.True(admissionIndex >= 0, "accept loop calls pre-auth admission");
        TestAssert.True(disposeIndex > admissionIndex, "denied accepted socket has a silent dispose path");
        TestAssert.True(handlerIndex > disposeIndex, "pre-auth admission and rejection precede worker allocation");
    }

    private static void BoundedReceiverHandlesFragmentationAndOverflow()
    {
        using var fixture = new TransportProcessorFixture();
        using var server = new BoundedLoopbackServer(
            ProbeMode.Compatible,
            TransportProcessorFixture.ProcessCorrelationId,
            fixture.Authenticator,
            fixture.Queue,
            fixture.Service,
            fixture.DecisionService,
            fixture.ActionService,
            fixture.RewardDecisionService,
            fixture.RewardActionService,
            fixture.MapDecisionService,
            fixture.MapActionService,
            fixture.RoomDecisionService,
            fixture.RoomActionService);

        using (SocketPair pair = SocketPair.Create())
        {
            Task<ReceivedHead> receive = server.ReceiveBoundedHeadAsync(pair.Server, CancellationToken.None);
            byte[] request = Encoding.ASCII.GetBytes(TransportProcessorFixture.Request());
            for (int offset = 0; offset < request.Length; offset += 7)
            {
                int length = Math.Min(7, request.Length - offset);
                SendAll(pair.Client, request.AsSpan(offset, length));
            }

            ReceivedHead result = receive.GetAwaiter().GetResult();
            TestAssert.Equal(ReceivedHeadStatus.Complete, result.Status, "fragmented complete head");
            TestAssert.Equal(request.Length, result.Length, "fragmented complete length");
            TestAssert.SequenceEqual(
                request,
                result.Buffer!.AsSpan(0, result.Length),
                "fragmented complete bytes");
            CryptographicOperations.ZeroMemory(result.Buffer!);
        }

        using (SocketPair pair = SocketPair.Create())
        {
            Task<ReceivedHead> receive = server.ReceiveBoundedHeadAsync(pair.Server, CancellationToken.None);
            SendAll(pair.Client, new byte[LiveProbeLimits.RequestHeadBufferBytes]);
            ReceivedHead result = receive.GetAwaiter().GetResult();
            TestAssert.Equal(ReceivedHeadStatus.SilentClose, result.Status, "unterminated 4097-byte head");
        }

        using (SocketPair pair = SocketPair.Create())
        {
            Task<ReceivedHead> receive = server.ReceiveBoundedHeadAsync(pair.Server, CancellationToken.None);
            byte[] oversizedComplete = BuildCompleteHead(4_097);
            SendAll(pair.Client, oversizedComplete);
            ReceivedHead result = receive.GetAwaiter().GetResult();
            TestAssert.Equal(ReceivedHeadStatus.PayloadTooLarge, result.Status, "complete 4097-byte head");
        }

        using (SocketPair pair = SocketPair.Create())
        {
            Task<ReceivedHead> receive = server.ReceiveBoundedHeadAsync(pair.Server, CancellationToken.None);
            SendAll(pair.Client, Encoding.ASCII.GetBytes(TransportProcessorFixture.Request() + "x"));
            ReceivedHead result = receive.GetAwaiter().GetResult();
            TestAssert.Equal(ReceivedHeadStatus.SilentClose, result.Status, "buffered byte after terminator");
        }

        using (SocketPair pair = SocketPair.Create())
        {
            Task<ReceivedHead> receive = server.ReceiveBoundedHeadAsync(pair.Server, CancellationToken.None);
            pair.Client.Shutdown(SocketShutdown.Both);
            ReceivedHead result = receive.GetAwaiter().GetResult();
            TestAssert.Equal(ReceivedHeadStatus.SilentClose, result.Status, "early disconnect");
        }
    }

    private static void HandlerCapAndCancellationCloseSilently()
    {
        using var fixture = new TransportProcessorFixture();
        using var server = new BoundedLoopbackServer(
            ProbeMode.Compatible,
            TransportProcessorFixture.ProcessCorrelationId,
            fixture.Authenticator,
            fixture.Queue,
            fixture.Service,
            fixture.DecisionService,
            fixture.ActionService,
            fixture.RewardDecisionService,
            fixture.RewardActionService,
            fixture.MapDecisionService,
            fixture.MapActionService,
            fixture.RoomDecisionService,
            fixture.RoomActionService);
        using var cancellation = new CancellationTokenSource();
        var occupiedPairs = new List<SocketPair>();
        var occupiedHandlers = new List<Task>();
        try
        {
            for (int index = 0; index < LiveProbeLimits.MaximumConcurrentConnections; index++)
            {
                SocketPair pair = SocketPair.Create();
                occupiedPairs.Add(pair);
                occupiedHandlers.Add(
                    server.HandleAcceptedSocketAsync(pair.Server, cancellation.Token));
            }

            using (SocketPair overflow = SocketPair.Create())
            {
                Task rejected = server.HandleAcceptedSocketAsync(
                    overflow.Server,
                    CancellationToken.None);
                TestAssert.True(rejected.Wait(TimeSpan.FromSeconds(1)), "fifth handler is rejected immediately");
                overflow.Client.ReceiveTimeout = 1_000;
                int received = overflow.Client.Receive(new byte[1], SocketFlags.None);
                TestAssert.Equal(0, received, "handler overflow closes without response");
            }

            cancellation.Cancel();
            TestAssert.True(
                Task.WaitAll(occupiedHandlers.ToArray(), TimeSpan.FromSeconds(1)),
                "cancellation closes four occupied handlers");
            foreach (SocketPair pair in occupiedPairs)
            {
                pair.Client.ReceiveTimeout = 1_000;
                int received = pair.Client.Receive(new byte[1], SocketFlags.None);
                TestAssert.Equal(0, received, "canceled handler closes without response");
            }
        }
        finally
        {
            cancellation.Cancel();
            foreach (SocketPair pair in occupiedPairs)
            {
                pair.Dispose();
            }
        }

        using (SocketPair pair = SocketPair.Create())
        using (var alreadyCanceled = new CancellationTokenSource())
        {
            alreadyCanceled.Cancel();
            ReceivedHead result = server.ReceiveBoundedHeadAsync(
                    pair.Server,
                    alreadyCanceled.Token)
                .GetAwaiter()
                .GetResult();
            TestAssert.Equal(ReceivedHeadStatus.SilentClose, result.Status, "header deadline cancellation is silent");
        }

        using (SocketPair pair = SocketPair.Create())
        using (var alreadyCanceled = new CancellationTokenSource())
        {
            alreadyCanceled.Cancel();
            Task handler = server.HandleAcceptedSocketAsync(pair.Server, alreadyCanceled.Token);
            TestAssert.True(handler.Wait(TimeSpan.FromSeconds(1)), "canceled total lifetime completes handler");
            pair.Client.ReceiveTimeout = 1_000;
            int received = pair.Client.Receive(new byte[1], SocketFlags.None);
            TestAssert.Equal(0, received, "canceled total lifetime closes without response");
        }
    }

    private static void ScreenQueueCapacityMapsToRateLimited()
    {
        using var fixture = new TransportProcessorFixture();
        string request = TransportProcessorFixture.Request(target: "/probe/v0/public/screen");
        Task<ProbeProcessingResult> first = Task.Run(() => fixture.Process(request));
        Task<ProbeProcessingResult> second = Task.Run(() => fixture.Process(request));
        bool filled = SpinWait.SpinUntil(
            () => fixture.Queue!.OutstandingCount == 2,
            TimeSpan.FromSeconds(1));
        TestAssert.True(filled, "two screen-read slots fill");

        TransportProcessorFixture.AssertStatus(
            429,
            fixture.Process(request),
            "third screen read is rate limited");
        TestAssert.Equal(0, fixture.Service!.Calls, "full queue invokes no screen service");

        fixture.Queue!.Stop();
        TestAssert.True(first.Wait(TimeSpan.FromSeconds(1)), "first queued request cancels");
        TestAssert.True(second.Wait(TimeSpan.FromSeconds(1)), "second queued request cancels");
        TransportProcessorFixture.AssertStatus(503, first.Result, "first canceled screen request");
        TransportProcessorFixture.AssertStatus(503, second.Result, "second canceled screen request");
    }

    private static void AcceptedSocketHandlerSendsExactlyOneResponse()
    {
        using var fixture = new TransportProcessorFixture();
        using var server = new BoundedLoopbackServer(
            ProbeMode.Compatible,
            TransportProcessorFixture.ProcessCorrelationId,
            fixture.Authenticator,
            fixture.Queue,
            fixture.Service,
            fixture.DecisionService,
            fixture.ActionService,
            fixture.RewardDecisionService,
            fixture.RewardActionService,
            fixture.MapDecisionService,
            fixture.MapActionService,
            fixture.RoomDecisionService,
            fixture.RoomActionService);

        using (SocketPair pair = SocketPair.Create())
        {
            Task handler = server.HandleAcceptedSocketAsync(pair.Server, CancellationToken.None);
            SendAll(pair.Client, Encoding.ASCII.GetBytes(TransportProcessorFixture.Request()));
            byte[] response = ReceiveUntilClose(pair.Client);
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodeHealthResponse(TransportProcessorFixture.ProcessCorrelationId),
                response,
                "accepted socket exact response");
            TestAssert.True(handler.Wait(TimeSpan.FromSeconds(3)), "accepted socket handler completes");
        }

        using (SocketPair pair = SocketPair.Create())
        {
            Task handler = server.HandleAcceptedSocketAsync(pair.Server, CancellationToken.None);
            SendAll(pair.Client, Encoding.ASCII.GetBytes(TransportProcessorFixture.Request()));
            pair.Client.Dispose();
            TestAssert.True(handler.Wait(TimeSpan.FromSeconds(3)), "partial response disconnect is contained");
        }
    }

    private static void ProductionAcceptLoopBindsAcceptsRejectsCollisionAndJoins()
    {
        using var fixture = new TransportProcessorFixture(ProbeMode.IncompatibleLocked);
        var testListener = new TcpListener(IPAddress.Loopback, 0);
        using var server = new BoundedLoopbackServer(
            ProbeMode.IncompatibleLocked,
            TransportProcessorFixture.ProcessCorrelationId,
            fixture.Authenticator,
            null,
            null,
            testListener,
            new FakeMonotonicClock(),
            new FakeMonotonicClock());
        server.Start();
        var endpoint = (IPEndPoint)testListener.LocalEndpoint;

        using (var client = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp))
        {
            client.Connect(endpoint);
            SendAll(client, Encoding.ASCII.GetBytes(TransportProcessorFixture.Request()));
            TestAssert.SequenceEqual(
                CanonicalProbeEncoder.EncodeHealthResponse(TransportProcessorFixture.ProcessCorrelationId),
                ReceiveUntilClose(client),
                "production accept loop exact response on assigned loopback port");
        }

        var collisionListener = new TcpListener(IPAddress.Loopback, endpoint.Port);
        using (var collision = new BoundedLoopbackServer(
                   ProbeMode.IncompatibleLocked,
                   TransportProcessorFixture.ProcessCorrelationId,
                   fixture.Authenticator,
                   null,
                   null,
                   collisionListener,
                   new FakeMonotonicClock(),
                   new FakeMonotonicClock()))
        {
            bool rejected = false;
            try
            {
                collision.Start();
            }
            catch (SocketException)
            {
                rejected = true;
            }

            TestAssert.True(rejected, "accept-loop port collision fails closed");
        }

        server.StopAccepting();
        TestAssert.True(
            server.StopAndJoin(TimeSpan.FromSeconds(2)),
            "accept loop cancels and joins within the frozen bound");
        TestAssert.True(
            server.StopAndJoin(TimeSpan.Zero),
            "accept-loop join is idempotent after completion");

        using var afterStop = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        bool portReleased = false;
        try
        {
            afterStop.Connect(endpoint);
        }
        catch (SocketException)
        {
            portReleased = true;
        }

        TestAssert.True(portReleased, "accept loop releases the assigned port after join");
    }

    private static void AssertRequestLineLength(int length, ProbeRequestParseStatus expected)
    {
        int methodLength = length - 12;
        string head = new string('A', methodLength) + " /x HTTP/1.1\r\n\r\n";
        TestAssert.Equal(
            expected,
            ProbeRequestParser.Parse(Encoding.ASCII.GetBytes(head)).Status,
            "request-line length " + length);
    }

    private static void AssertTargetLength(int length, ProbeRequestParseStatus expected)
    {
        string target = "/" + new string('a', length - 1);
        string head = "GET " + target + " HTTP/1.1\r\n\r\n";
        TestAssert.Equal(
            expected,
            ProbeRequestParser.Parse(Encoding.ASCII.GetBytes(head)).Status,
            "request-target length " + length);
    }

    private static void AssertHeaderNameLength(int length, ProbeRequestParseStatus expected)
    {
        string head = "GET /x HTTP/1.1\r\n" + new string('X', length) + ": value\r\n\r\n";
        TestAssert.Equal(
            expected,
            ProbeRequestParser.Parse(Encoding.ASCII.GetBytes(head)).Status,
            "header-name length " + length);
    }

    private static void AssertHeaderValueLength(int length, ProbeRequestParseStatus expected)
    {
        string head = "GET /x HTTP/1.1\r\nOrigin: " + new string('a', length) + "\r\n\r\n";
        TestAssert.Equal(
            expected,
            ProbeRequestParser.Parse(Encoding.ASCII.GetBytes(head)).Status,
            "header-value length " + length);
    }

    private static void AssertHeaderCount(int count, ProbeRequestParseStatus expected)
    {
        var builder = new StringBuilder("GET /x HTTP/1.1\r\n");
        for (int index = 0; index < count; index++)
        {
            builder.Append('X').Append(index).Append(": value\r\n");
        }

        builder.Append("\r\n");
        TestAssert.Equal(
            expected,
            ProbeRequestParser.Parse(Encoding.ASCII.GetBytes(builder.ToString())).Status,
            "header count " + count);
    }

    private static void AssertCompleteHeadLength(int length, ProbeRequestParseStatus expected)
    {
        byte[] head = BuildCompleteHead(length);
        TestAssert.Equal(length, head.Length, "constructed complete-head length");
        TestAssert.Equal(
            expected,
            ProbeRequestParser.Parse(head).Status,
            "complete-head length " + length);
    }

    private static byte[] BuildCompleteHead(int length)
    {
        const string requestLine = "GET /x HTTP/1.1\r\n";
        const string terminator = "\r\n";
        var headers = new string[8];
        int fixedLength = requestLine.Length + terminator.Length;
        for (int index = 0; index < headers.Length; index++)
        {
            string prefix = "X" + index + ": ";
            fixedLength += prefix.Length + 2;
            headers[index] = prefix;
        }

        int remaining = length - fixedLength;
        if (remaining < 0 || remaining > headers.Length * LiveProbeLimits.MaximumHeaderValueBytes)
        {
            throw new ArgumentOutOfRangeException(nameof(length));
        }

        var builder = new StringBuilder(length);
        builder.Append(requestLine);
        for (int index = 0; index < headers.Length; index++)
        {
            int valueLength = Math.Min(LiveProbeLimits.MaximumHeaderValueBytes, remaining);
            remaining -= valueLength;
            builder.Append(headers[index]).Append('a', valueLength).Append("\r\n");
        }

        builder.Append(terminator);
        return Encoding.ASCII.GetBytes(builder.ToString());
    }

    private static void SendAll(Socket socket, ReadOnlySpan<byte> content)
    {
        int sent = 0;
        while (sent < content.Length)
        {
            sent += socket.Send(content[sent..], SocketFlags.None);
        }
    }

    private static byte[] ReceiveUntilClose(Socket socket)
    {
        socket.ReceiveTimeout = 3_000;
        var response = new List<byte>();
        byte[] buffer = new byte[1_024];
        while (true)
        {
            int received = socket.Receive(buffer, SocketFlags.None);
            if (received == 0)
            {
                return response.ToArray();
            }

            response.AddRange(buffer.AsSpan(0, received).ToArray());
        }
    }

    private static List<MethodBase> ResolveCalledMethods(MethodInfo method)
    {
        byte[]? il = method.GetMethodBody()?.GetILAsByteArray();
        TestAssert.True(il is not null, "method has IL body");
        var calls = new List<MethodBase>();
        for (int index = 0; index <= il!.Length - 5; index++)
        {
            if (il[index] is not 0x28 and not 0x6f)
            {
                continue;
            }

            int token = il[index + 1] |
                (il[index + 2] << 8) |
                (il[index + 3] << 16) |
                (il[index + 4] << 24);
            try
            {
                MethodBase? target = method.Module.ResolveMethod(
                    token,
                    method.DeclaringType?.GetGenericArguments(),
                    method.GetGenericArguments());
                if (target is not null)
                {
                    calls.Add(target);
                }
            }
            catch (ArgumentException)
            {
            }
        }

        return calls;
    }

    private static int FindCall(
        IReadOnlyList<MethodBase> calls,
        Type declaringType,
        string name)
    {
        for (int index = 0; index < calls.Count; index++)
        {
            MethodBase call = calls[index];
            if (call.DeclaringType == declaringType && call.Name == name)
            {
                return index;
            }
        }

        return -1;
    }

    private sealed class SocketPair : IDisposable
    {
        private SocketPair(Socket client, Socket server)
        {
            Client = client;
            Server = server;
        }

        public Socket Client { get; }

        public Socket Server { get; }

        public static SocketPair Create()
        {
            var listener = new TcpListener(IPAddress.Loopback, 0);
            listener.Start(1);
            try
            {
                var endpoint = (IPEndPoint)listener.LocalEndpoint;
                var client = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                client.Connect(endpoint);
                Socket server = listener.AcceptSocket();
                return new SocketPair(client, server);
            }
            finally
            {
                listener.Stop();
            }
        }

        public void Dispose()
        {
            Client.Dispose();
            Server.Dispose();
        }
    }
}
