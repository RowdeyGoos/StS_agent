using System;
using System.Text;
using Sts2AgentBridge.Core.Hosting;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Core.Transport;

internal readonly record struct ProbeProcessingResult(bool ShouldRespond, byte[] Response)
{
    public static ProbeProcessingResult Silent()
    {
        return new ProbeProcessingResult(false, Array.Empty<byte>());
    }

    public static ProbeProcessingResult Respond(byte[] response)
    {
        return new ProbeProcessingResult(true, response);
    }
}

internal sealed class ProbeRequestProcessor
{
    private static ReadOnlySpan<byte> BearerPrefix => "Bearer "u8;

    private readonly ProbeMode _mode;
    private readonly string _processCorrelationId;
    private readonly FixedTimeAuthenticator _authenticator;
    private readonly MonotonicTokenBucket _authenticatedBucket;
    private readonly BoundedFrameWorkQueue? _frameQueue;
    private readonly IPublicScreenService? _publicScreenService;
    private readonly IPublicCombatDecisionService? _publicCombatDecisionService;
    private readonly IPublicCombatActionService? _publicCombatActionService;
    private readonly IPublicRewardDecisionService? _publicRewardDecisionService;
    private readonly IPublicRewardActionService? _publicRewardActionService;
    private readonly IPublicMapDecisionService? _publicMapDecisionService;
    private readonly IPublicMapActionService? _publicMapActionService;
    private readonly IPublicRoomDecisionService? _publicRoomDecisionService;
    private readonly IPublicRoomActionService? _publicRoomActionService;

    public ProbeRequestProcessor(
        ProbeMode mode,
        string processCorrelationId,
        FixedTimeAuthenticator authenticator,
        BoundedFrameWorkQueue? frameQueue,
        IPublicScreenService? publicScreenService,
        MonotonicTokenBucket authenticatedBucket,
        IPublicCombatDecisionService? publicCombatDecisionService = null,
        IPublicCombatActionService? publicCombatActionService = null,
        IPublicRewardDecisionService? publicRewardDecisionService = null,
        IPublicRewardActionService? publicRewardActionService = null,
        IPublicMapDecisionService? publicMapDecisionService = null,
        IPublicMapActionService? publicMapActionService = null,
        IPublicRoomDecisionService? publicRoomDecisionService = null,
        IPublicRoomActionService? publicRoomActionService = null)
    {
        if (mode is not ProbeMode.Compatible and not ProbeMode.IncompatibleLocked)
        {
            throw new ArgumentOutOfRangeException(nameof(mode));
        }

        if (!CorrelationIdGenerator.IsCanonical(processCorrelationId))
        {
            throw new ArgumentException("Invalid process correlation ID.", nameof(processCorrelationId));
        }

        if (mode == ProbeMode.Compatible)
        {
            if (frameQueue is null || publicScreenService is null ||
                publicCombatDecisionService is null || publicCombatActionService is null ||
                publicRewardDecisionService is null || publicRewardActionService is null ||
                publicMapDecisionService is null || publicMapActionService is null ||
                publicRoomDecisionService is null || publicRoomActionService is null)
            {
                throw new ArgumentException("Compatible mode requires every bounded public route.");
            }
        }
        else if (frameQueue is not null || publicScreenService is not null ||
            publicCombatDecisionService is not null || publicCombatActionService is not null ||
            publicRewardDecisionService is not null || publicRewardActionService is not null ||
            publicMapDecisionService is not null || publicMapActionService is not null ||
            publicRoomDecisionService is not null || publicRoomActionService is not null)
        {
            throw new ArgumentException("Locked mode cannot own a public-screen path.");
        }

        _mode = mode;
        _processCorrelationId = processCorrelationId;
        _authenticator = authenticator ?? throw new ArgumentNullException(nameof(authenticator));
        _frameQueue = frameQueue;
        _publicScreenService = publicScreenService;
        _publicCombatDecisionService = publicCombatDecisionService;
        _publicCombatActionService = publicCombatActionService;
        _publicRewardDecisionService = publicRewardDecisionService;
        _publicRewardActionService = publicRewardActionService;
        _publicMapDecisionService = publicMapDecisionService;
        _publicMapActionService = publicMapActionService;
        _publicRoomDecisionService = publicRoomDecisionService;
        _publicRoomActionService = publicRoomActionService;
        _authenticatedBucket = authenticatedBucket ?? throw new ArgumentNullException(nameof(authenticatedBucket));
    }

    public ProbeProcessingResult Process(ReadOnlySpan<byte> completeHead)
    {
        ProbeRequestParseResult parsed = ProbeRequestParser.Parse(completeHead);
        switch (parsed.Status)
        {
            case ProbeRequestParseStatus.SilentClose:
                return ProbeProcessingResult.Silent();
            case ProbeRequestParseStatus.PayloadTooLarge:
                return Error(ProbeErrorKind.PayloadTooLarge);
            case ProbeRequestParseStatus.InvalidRequest:
                return Error(ProbeErrorKind.InvalidRequest);
            case ProbeRequestParseStatus.Parsed:
                break;
            default:
                return Error(ProbeErrorKind.BackendFault);
        }

        ParsedProbeRequest request = parsed.Request;
        if (request.AuthorizationCount != 1 ||
            request.AuthorizationValueOffset < 0 ||
            request.AuthorizationValueLength != BearerPrefix.Length + FixedTimeAuthenticator.CredentialLength ||
            request.AuthorizationValueOffset > completeHead.Length - request.AuthorizationValueLength)
        {
            return Error(ProbeErrorKind.Unauthenticated);
        }

        ReadOnlySpan<byte> authorization = completeHead.Slice(
            request.AuthorizationValueOffset,
            request.AuthorizationValueLength);
        if (!authorization[..BearerPrefix.Length].SequenceEqual(BearerPrefix) ||
            !_authenticator.Matches(authorization[BearerPrefix.Length..]))
        {
            return Error(ProbeErrorKind.Unauthenticated);
        }

        if (!_authenticatedBucket.TryConsume())
        {
            return Error(ProbeErrorKind.RateLimited);
        }

        if (request.HostState is ParsedHostState.Missing or ParsedHostState.Duplicate)
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        if (request.HostState == ParsedHostState.Wrong || request.HasOrigin)
        {
            return Error(ProbeErrorKind.Forbidden);
        }

        if (!TryResolveRegisteredRoute(request.RouteTarget, out ProbeRoute route))
        {
            return Error(ProbeErrorKind.UnsupportedContent);
        }

        if (route is ProbeRoute.PublicCombatAction or ProbeRoute.PublicRewardAction or
            ProbeRoute.PublicMapAction or ProbeRoute.PublicRoomAction)
        {
            if (!request.IsPost)
            {
                return Error(ProbeErrorKind.InvalidRequest);
            }
            if (request.DecisionIdCount != 1 || request.ActionIdCount != 1)
            {
                return Error(ProbeErrorKind.InvalidRequest);
            }
        }
        else
        {
            if (!request.IsGet)
            {
                return Error(ProbeErrorKind.ReadOnly);
            }
            if (request.DecisionIdCount != 0 || request.ActionIdCount != 0)
            {
                return Error(ProbeErrorKind.InvalidRequest);
            }
        }

        try
        {
            return route switch
            {
                ProbeRoute.Health =>
                    ProbeProcessingResult.Respond(
                        CanonicalProbeEncoder.EncodeHealthResponse(_processCorrelationId)),
                ProbeRoute.Manifest =>
                    ProbeProcessingResult.Respond(
                        CanonicalProbeEncoder.EncodeManifestResponse(_mode)),
                ProbeRoute.PublicScreen => ProcessPublicScreen(),
                ProbeRoute.PublicCombatDecision => ProcessPublicCombatDecision(),
                ProbeRoute.PublicCombatAction => ProcessPublicCombatAction(completeHead, request),
                ProbeRoute.PublicRewardDecision => ProcessPublicRewardDecision(),
                ProbeRoute.PublicRewardAction => ProcessPublicRewardAction(completeHead, request),
                ProbeRoute.PublicMapDecision => ProcessPublicMapDecision(),
                ProbeRoute.PublicMapAction => ProcessPublicMapAction(completeHead, request),
                ProbeRoute.PublicRoomDecision => ProcessPublicRoomDecision(),
                ProbeRoute.PublicRoomAction => ProcessPublicRoomAction(completeHead, request),
                _ => Error(ProbeErrorKind.BackendFault),
            };
        }
        catch
        {
            return Error(ProbeErrorKind.BackendFault);
        }
    }

    private ProbeProcessingResult ProcessPublicCombatAction(
        ReadOnlySpan<byte> completeHead,
        ParsedProbeRequest request)
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicCombatActionService is null ||
            request.DecisionIdValueOffset < 0 || request.DecisionIdValueLength != 64 ||
            request.DecisionIdValueOffset > completeHead.Length - request.DecisionIdValueLength ||
            request.ActionIdValueOffset < 0 || request.ActionIdValueLength < 6 ||
            request.ActionIdValueLength > 8 ||
            request.ActionIdValueOffset > completeHead.Length - request.ActionIdValueLength)
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        string decisionId = Encoding.ASCII.GetString(completeHead.Slice(
            request.DecisionIdValueOffset,
            request.DecisionIdValueLength));
        string actionId = Encoding.ASCII.GetString(completeHead.Slice(
            request.ActionIdValueOffset,
            request.ActionIdValueLength));
        if (!PublicCombatActionRequest.TryCreate(decisionId, actionId, out PublicCombatActionRequest action))
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        FrameDispatchResult<PublicCombatActionApplyResult> dispatch =
            _frameQueue.Submit(() => _publicCombatActionService.Apply(action));
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }
        if (dispatch.Status != FrameDispatchStatus.Success || dispatch.Value.IsBackendFault)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicCombatActionResponse(dispatch.Value));
    }

    private ProbeProcessingResult ProcessPublicRewardAction(
        ReadOnlySpan<byte> completeHead,
        ParsedProbeRequest request)
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicRewardActionService is null ||
            request.DecisionIdValueOffset < 0 || request.DecisionIdValueLength != 64 ||
            request.DecisionIdValueOffset > completeHead.Length - request.DecisionIdValueLength ||
            request.ActionIdValueOffset < 0 || request.ActionIdValueLength is < 6 or > 12 ||
            request.ActionIdValueOffset > completeHead.Length - request.ActionIdValueLength)
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        string decisionId = Encoding.ASCII.GetString(completeHead.Slice(
            request.DecisionIdValueOffset,
            request.DecisionIdValueLength));
        string actionId = Encoding.ASCII.GetString(completeHead.Slice(
            request.ActionIdValueOffset,
            request.ActionIdValueLength));
        if (!PublicRewardActionRequest.TryCreate(decisionId, actionId, out PublicRewardActionRequest action))
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        FrameDispatchResult<PublicRewardActionApplyResult> dispatch =
            _frameQueue.Submit(() => _publicRewardActionService.Apply(action));
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }
        if (dispatch.Status != FrameDispatchStatus.Success || dispatch.Value.IsBackendFault)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicRewardActionResponse(dispatch.Value));
    }

    private ProbeProcessingResult ProcessPublicMapAction(
        ReadOnlySpan<byte> completeHead,
        ParsedProbeRequest request)
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicMapActionService is null ||
            request.DecisionIdValueOffset < 0 || request.DecisionIdValueLength != 64 ||
            request.DecisionIdValueOffset > completeHead.Length - request.DecisionIdValueLength ||
            request.ActionIdValueOffset < 0 || request.ActionIdValueLength != 8 ||
            request.ActionIdValueOffset > completeHead.Length - request.ActionIdValueLength)
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        string decisionId = Encoding.ASCII.GetString(completeHead.Slice(
            request.DecisionIdValueOffset,
            request.DecisionIdValueLength));
        string actionId = Encoding.ASCII.GetString(completeHead.Slice(
            request.ActionIdValueOffset,
            request.ActionIdValueLength));
        if (!PublicMapActionRequest.TryCreate(decisionId, actionId, out PublicMapActionRequest action))
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        FrameDispatchResult<PublicMapActionApplyResult> dispatch =
            _frameQueue.Submit(() => _publicMapActionService.Apply(action));
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }
        if (dispatch.Status != FrameDispatchStatus.Success || dispatch.Value.IsBackendFault)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicMapActionResponse(dispatch.Value));
    }

    private ProbeProcessingResult ProcessPublicRoomAction(
        ReadOnlySpan<byte> completeHead,
        ParsedProbeRequest request)
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicRoomActionService is null ||
            request.DecisionIdValueOffset < 0 || request.DecisionIdValueLength != 64 ||
            request.DecisionIdValueOffset > completeHead.Length - request.DecisionIdValueLength ||
            request.ActionIdValueOffset < 0 || request.ActionIdValueLength is < 7 or > 8 ||
            request.ActionIdValueOffset > completeHead.Length - request.ActionIdValueLength)
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        string decisionId = Encoding.ASCII.GetString(completeHead.Slice(
            request.DecisionIdValueOffset,
            request.DecisionIdValueLength));
        string actionId = Encoding.ASCII.GetString(completeHead.Slice(
            request.ActionIdValueOffset,
            request.ActionIdValueLength));
        if (!PublicRoomActionRequest.TryCreate(decisionId, actionId, out PublicRoomActionRequest action))
        {
            return Error(ProbeErrorKind.InvalidRequest);
        }

        FrameDispatchResult<PublicRoomActionApplyResult> dispatch =
            _frameQueue.Submit(() => _publicRoomActionService.Apply(action));
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }
        if (dispatch.Status != FrameDispatchStatus.Success || dispatch.Value.IsBackendFault)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicRoomActionResponse(dispatch.Value));
    }

    private ProbeProcessingResult ProcessPublicScreen()
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicScreenService is null)
        {
            return Error(ProbeErrorKind.UnsupportedContent);
        }

        FrameDispatchResult<PublicScreenReadResult> dispatch =
            _frameQueue.Submit(_publicScreenService.Read);
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }

        if (dispatch.Status != FrameDispatchStatus.Success)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        PublicScreenReadResult result = dispatch.Value;
        if (!result.IsSuccess)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicScreenResponse(result.Snapshot));
    }

    private ProbeProcessingResult ProcessPublicCombatDecision()
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicCombatDecisionService is null)
        {
            return Error(ProbeErrorKind.UnsupportedContent);
        }

        FrameDispatchResult<PublicCombatDecisionReadResult> dispatch =
            _frameQueue.Submit(_publicCombatDecisionService.Read);
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }

        if (dispatch.Status != FrameDispatchStatus.Success)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        PublicCombatDecisionReadResult result = dispatch.Value;
        if (!result.IsSuccess)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicCombatDecisionResponse(result.Snapshot));
    }

    private ProbeProcessingResult ProcessPublicRewardDecision()
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicRewardDecisionService is null)
        {
            return Error(ProbeErrorKind.UnsupportedContent);
        }

        FrameDispatchResult<PublicRewardDecisionReadResult> dispatch =
            _frameQueue.Submit(_publicRewardDecisionService.Read);
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }
        if (dispatch.Status != FrameDispatchStatus.Success)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        PublicRewardDecisionReadResult result = dispatch.Value;
        if (!result.IsSuccess)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicRewardDecisionResponse(result.Snapshot));
    }

    private ProbeProcessingResult ProcessPublicMapDecision()
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicMapDecisionService is null)
        {
            return Error(ProbeErrorKind.UnsupportedContent);
        }

        FrameDispatchResult<PublicMapDecisionReadResult> dispatch =
            _frameQueue.Submit(_publicMapDecisionService.Read);
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }
        if (dispatch.Status != FrameDispatchStatus.Success)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        PublicMapDecisionReadResult result = dispatch.Value;
        if (!result.IsSuccess)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicMapDecisionResponse(result.Snapshot));
    }

    private ProbeProcessingResult ProcessPublicRoomDecision()
    {
        if (_mode != ProbeMode.Compatible || _frameQueue is null || _publicRoomDecisionService is null)
        {
            return Error(ProbeErrorKind.UnsupportedContent);
        }

        FrameDispatchResult<PublicRoomDecisionReadResult> dispatch =
            _frameQueue.Submit(_publicRoomDecisionService.Read);
        if (dispatch.Status == FrameDispatchStatus.Busy)
        {
            return Error(ProbeErrorKind.RateLimited);
        }
        if (dispatch.Status != FrameDispatchStatus.Success)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        PublicRoomDecisionReadResult result = dispatch.Value;
        if (!result.IsSuccess)
        {
            return Error(ProbeErrorKind.BackendUnavailable);
        }

        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodePublicRoomDecisionResponse(result.Snapshot));
    }

    private bool TryResolveRegisteredRoute(
        ParsedRouteTarget target,
        out ProbeRoute route)
    {
        route = target switch
        {
            ParsedRouteTarget.Health => ProbeRoute.Health,
            ParsedRouteTarget.Manifest => ProbeRoute.Manifest,
            ParsedRouteTarget.PublicScreen => ProbeRoute.PublicScreen,
            ParsedRouteTarget.PublicCombatDecision => ProbeRoute.PublicCombatDecision,
            ParsedRouteTarget.PublicCombatAction => ProbeRoute.PublicCombatAction,
            ParsedRouteTarget.PublicRewardDecision => ProbeRoute.PublicRewardDecision,
            ParsedRouteTarget.PublicRewardAction => ProbeRoute.PublicRewardAction,
            ParsedRouteTarget.PublicMapDecision => ProbeRoute.PublicMapDecision,
            ParsedRouteTarget.PublicMapAction => ProbeRoute.PublicMapAction,
            ParsedRouteTarget.PublicRoomDecision => ProbeRoute.PublicRoomDecision,
            ParsedRouteTarget.PublicRoomAction => ProbeRoute.PublicRoomAction,
            _ => default,
        };

        return route != default && ProbeRouteCatalog.IsRegistered(route, _mode);
    }

    private static ProbeProcessingResult Error(ProbeErrorKind kind)
    {
        string correlationId = CorrelationIdGenerator.Create();
        return ProbeProcessingResult.Respond(
            CanonicalProbeEncoder.EncodeErrorResponse(kind, correlationId));
    }
}
