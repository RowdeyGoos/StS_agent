using System;
using Sts2AgentBridge.Core.Protocol;

namespace Sts2AgentBridge.Core.Transport;

internal enum ProbeRequestParseStatus
{
    Parsed = 1,
    InvalidRequest = 2,
    PayloadTooLarge = 3,
    SilentClose = 4,
}

internal enum ParsedHostState
{
    Missing = 1,
    Exact = 2,
    Wrong = 3,
    Duplicate = 4,
}

internal enum ParsedRouteTarget
{
    Unknown = 1,
    Health = 2,
    Manifest = 3,
    PublicScreen = 4,
    PublicCombatDecision = 5,
    PublicCombatAction = 6,
    PublicRewardDecision = 7,
    PublicRewardAction = 8,
    PublicMapDecision = 9,
    PublicMapAction = 10,
    PublicRoomDecision = 11,
    PublicRoomAction = 12,
    CombatChoiceDecision = 13,
    CombatChoiceAction = 14,
    EventCombatDecision = 15,
    EventResumeItemDecision = 16,
    EventResumeItemAction = 17,
}

internal readonly record struct ParsedProbeRequest(
    bool IsGet,
    bool IsPost,
    ParsedRouteTarget RouteTarget,
    ParsedHostState HostState,
    bool HasOrigin,
    int AuthorizationValueOffset,
    int AuthorizationValueLength,
    int AuthorizationCount,
    int DecisionIdValueOffset,
    int DecisionIdValueLength,
    int DecisionIdCount,
    int ActionIdValueOffset,
    int ActionIdValueLength,
    int ActionIdCount);

internal readonly record struct ProbeRequestParseResult(
    ProbeRequestParseStatus Status,
    ParsedProbeRequest Request)
{
    public static ProbeRequestParseResult Parsed(ParsedProbeRequest request)
    {
        return new ProbeRequestParseResult(ProbeRequestParseStatus.Parsed, request);
    }

    public static ProbeRequestParseResult Invalid()
    {
        return new ProbeRequestParseResult(ProbeRequestParseStatus.InvalidRequest, default);
    }

    public static ProbeRequestParseResult TooLarge()
    {
        return new ProbeRequestParseResult(ProbeRequestParseStatus.PayloadTooLarge, default);
    }

    public static ProbeRequestParseResult Silent()
    {
        return new ProbeRequestParseResult(ProbeRequestParseStatus.SilentClose, default);
    }
}

internal static class ProbeRequestParser
{
    private static ReadOnlySpan<byte> HttpVersion => "HTTP/1.1"u8;
    private static ReadOnlySpan<byte> GetMethod => "GET"u8;
    private static ReadOnlySpan<byte> PostMethod => "POST"u8;
    private static ReadOnlySpan<byte> ExpectedHost => "127.0.0.1:43117"u8;
    private static ReadOnlySpan<byte> AcceptAny => "*/*"u8;
    private static ReadOnlySpan<byte> AcceptJson => "application/json"u8;
    private static ReadOnlySpan<byte> CloseValue => "close"u8;

    public static ProbeRequestParseResult Parse(ReadOnlySpan<byte> completeHead)
    {
        if (completeHead.Length > LiveProbeLimits.MaximumRequestHeadBytes)
        {
            return ProbeRequestParseResult.TooLarge();
        }

        if (completeHead.Length < 4)
        {
            return ProbeRequestParseResult.Invalid();
        }

        int terminatorOffset = FindHeaderTerminator(completeHead);
        if (terminatorOffset < 0)
        {
            return ProbeRequestParseResult.Invalid();
        }

        if (terminatorOffset + 4 != completeHead.Length)
        {
            return ProbeRequestParseResult.Silent();
        }

        int firstLineEnd = FindCrlf(completeHead, 0);
        if (firstLineEnd < 0)
        {
            return ProbeRequestParseResult.Invalid();
        }

        bool tooLarge = firstLineEnd > LiveProbeLimits.MaximumRequestLineBytes;
        bool invalid = false;
        bool hasFraming = false;

        ReadOnlySpan<byte> requestLine = completeHead[..firstLineEnd];
        bool isGet = false;
        bool isPost = false;
        ParsedRouteTarget routeTarget = ParsedRouteTarget.Unknown;
        ParseRequestLine(requestLine, ref tooLarge, ref invalid, ref isGet, ref isPost, ref routeTarget);

        int authorizationOffset = 0;
        int authorizationLength = 0;
        int authorizationCount = 0;
        int decisionIdOffset = 0;
        int decisionIdLength = 0;
        int decisionIdCount = 0;
        int actionIdOffset = 0;
        int actionIdLength = 0;
        int actionIdCount = 0;
        int hostCount = 0;
        bool hostExact = false;
        bool hasOrigin = false;
        bool originSeen = false;
        bool acceptSeen = false;
        bool connectionSeen = false;
        int headerCount = 0;
        int cursor = firstLineEnd + 2;

        while (cursor < completeHead.Length)
        {
            int lineEnd = FindCrlf(completeHead, cursor);
            if (lineEnd < 0)
            {
                invalid = true;
                break;
            }

            if (lineEnd == cursor)
            {
                if (lineEnd + 2 != completeHead.Length)
                {
                    invalid = true;
                }

                cursor = lineEnd + 2;
                break;
            }

            headerCount++;
            if (headerCount > LiveProbeLimits.MaximumHeaderCount)
            {
                tooLarge = true;
            }

            ReadOnlySpan<byte> line = completeHead[cursor..lineEnd];
            int colon = line.IndexOf((byte)':');
            if (colon <= 0)
            {
                invalid = true;
                cursor = lineEnd + 2;
                continue;
            }

            ReadOnlySpan<byte> name = line[..colon];
            if (name.Length > LiveProbeLimits.MaximumHeaderNameBytes)
            {
                tooLarge = true;
            }

            if (!IsHeaderName(name))
            {
                invalid = true;
            }

            if (colon + 1 >= line.Length || line[colon + 1] != (byte)' ')
            {
                invalid = true;
                cursor = lineEnd + 2;
                continue;
            }

            ReadOnlySpan<byte> value = line[(colon + 2)..];
            if (value.Length > LiveProbeLimits.MaximumHeaderValueBytes)
            {
                tooLarge = true;
            }

            if (!IsHeaderValue(value))
            {
                invalid = true;
            }

            if (IsFramingHeader(name))
            {
                hasFraming = true;
            }
            else if (AsciiEqualsIgnoreCase(name, "Authorization"u8))
            {
                authorizationCount++;
                if (authorizationCount == 1)
                {
                    authorizationOffset = cursor + colon + 2;
                    authorizationLength = value.Length;
                }
            }
            else if (AsciiEqualsIgnoreCase(name, "Host"u8))
            {
                hostCount++;
                if (hostCount == 1)
                {
                    hostExact = value.SequenceEqual(ExpectedHost);
                }
            }
            else if (AsciiEqualsIgnoreCase(name, "X-Sts2-Decision-Id"u8))
            {
                decisionIdCount++;
                if (decisionIdCount == 1)
                {
                    decisionIdOffset = cursor + colon + 2;
                    decisionIdLength = value.Length;
                }
            }
            else if (AsciiEqualsIgnoreCase(name, "X-Sts2-Action-Id"u8))
            {
                actionIdCount++;
                if (actionIdCount == 1)
                {
                    actionIdOffset = cursor + colon + 2;
                    actionIdLength = value.Length;
                }
            }
            else if (AsciiEqualsIgnoreCase(name, "Origin"u8))
            {
                if (originSeen)
                {
                    invalid = true;
                }

                originSeen = true;
                hasOrigin = true;
            }
            else if (AsciiEqualsIgnoreCase(name, "Accept"u8))
            {
                if (acceptSeen)
                {
                    invalid = true;
                }

                acceptSeen = true;
                if (!value.SequenceEqual(AcceptAny) && !value.SequenceEqual(AcceptJson))
                {
                    invalid = true;
                }
            }
            else if (AsciiEqualsIgnoreCase(name, "Connection"u8))
            {
                if (connectionSeen)
                {
                    invalid = true;
                }

                connectionSeen = true;
                if (!value.SequenceEqual(CloseValue))
                {
                    invalid = true;
                }
            }
            else
            {
                invalid = true;
            }

            cursor = lineEnd + 2;
        }

        if (cursor != completeHead.Length)
        {
            invalid = true;
        }

        if (hasFraming || tooLarge)
        {
            return ProbeRequestParseResult.TooLarge();
        }

        if (invalid)
        {
            return ProbeRequestParseResult.Invalid();
        }

        ParsedHostState hostState = hostCount switch
        {
            0 => ParsedHostState.Missing,
            1 when hostExact => ParsedHostState.Exact,
            1 => ParsedHostState.Wrong,
            _ => ParsedHostState.Duplicate,
        };

        return ProbeRequestParseResult.Parsed(
            new ParsedProbeRequest(
                isGet,
                isPost,
                routeTarget,
                hostState,
                hasOrigin,
                authorizationOffset,
                authorizationLength,
                authorizationCount,
                decisionIdOffset,
                decisionIdLength,
                decisionIdCount,
                actionIdOffset,
                actionIdLength,
                actionIdCount));
    }

    public static int FindHeaderTerminator(ReadOnlySpan<byte> value)
    {
        for (int index = 0; index <= value.Length - 4; index++)
        {
            if (value[index] == (byte)'\r' &&
                value[index + 1] == (byte)'\n' &&
                value[index + 2] == (byte)'\r' &&
                value[index + 3] == (byte)'\n')
            {
                return index;
            }
        }

        return -1;
    }

    private static void ParseRequestLine(
        ReadOnlySpan<byte> line,
        ref bool tooLarge,
        ref bool invalid,
        ref bool isGet,
        ref bool isPost,
        ref ParsedRouteTarget routeTarget)
    {
        if (!IsRequestLine(line))
        {
            invalid = true;
            return;
        }

        int firstSpace = line.IndexOf((byte)' ');
        if (firstSpace <= 0)
        {
            invalid = true;
            return;
        }

        int relativeSecondSpace = line[(firstSpace + 1)..].IndexOf((byte)' ');
        if (relativeSecondSpace <= 0)
        {
            invalid = true;
            return;
        }

        int secondSpace = firstSpace + 1 + relativeSecondSpace;
        ReadOnlySpan<byte> method = line[..firstSpace];
        ReadOnlySpan<byte> target = line[(firstSpace + 1)..secondSpace];
        ReadOnlySpan<byte> version = line[(secondSpace + 1)..];

        if (!IsMethod(method) || !version.SequenceEqual(HttpVersion))
        {
            invalid = true;
        }

        if (target.Length > LiveProbeLimits.MaximumRequestTargetBytes)
        {
            tooLarge = true;
        }

        if (target.IsEmpty ||
            target[0] != (byte)'/' ||
            target.IndexOf((byte)'?') >= 0 ||
            target.IndexOf((byte)'#') >= 0 ||
            target.IndexOf((byte)' ') >= 0)
        {
            invalid = true;
        }

        isGet = method.SequenceEqual(GetMethod);
        isPost = method.SequenceEqual(PostMethod);
        if (target.SequenceEqual("/probe/v0/health"u8))
        {
            routeTarget = ParsedRouteTarget.Health;
        }
        else if (target.SequenceEqual("/probe/v0/manifest"u8))
        {
            routeTarget = ParsedRouteTarget.Manifest;
        }
        else if (target.SequenceEqual("/probe/v0/public/screen"u8))
        {
            routeTarget = ParsedRouteTarget.PublicScreen;
        }
        else if (target.SequenceEqual("/probe/v0/public/combat-decision"u8))
        {
            routeTarget = ParsedRouteTarget.PublicCombatDecision;
        }
        else if (target.SequenceEqual("/probe/v0/public/combat-action"u8))
        {
            routeTarget = ParsedRouteTarget.PublicCombatAction;
        }
        else if (target.SequenceEqual("/probe/v0/public/reward-decision"u8))
        {
            routeTarget = ParsedRouteTarget.PublicRewardDecision;
        }
        else if (target.SequenceEqual("/probe/v0/public/reward-action"u8))
        {
            routeTarget = ParsedRouteTarget.PublicRewardAction;
        }
        else if (target.SequenceEqual("/probe/v0/public/map-decision"u8))
        {
            routeTarget = ParsedRouteTarget.PublicMapDecision;
        }
        else if (target.SequenceEqual("/probe/v0/public/map-action"u8))
        {
            routeTarget = ParsedRouteTarget.PublicMapAction;
        }
        else if (target.SequenceEqual("/probe/v0/public/room-decision"u8))
        {
            routeTarget = ParsedRouteTarget.PublicRoomDecision;
        }
        else if (target.SequenceEqual("/probe/v0/public/room-action"u8))
        {
            routeTarget = ParsedRouteTarget.PublicRoomAction;
        }
        else if (target.SequenceEqual("/probe/event-combat-v2/public/item-decision"u8))
        { routeTarget = ParsedRouteTarget.EventResumeItemDecision; }
        else if (target.SequenceEqual("/probe/event-combat-v2/public/item-action"u8))
        { routeTarget = ParsedRouteTarget.EventResumeItemAction; }
        else if (target.SequenceEqual("/probe/event-combat-v2/public/decision"u8))
        {
            routeTarget = ParsedRouteTarget.EventCombatDecision;
        }
        else if (target.SequenceEqual("/probe/combat-choice-v1/public/decision"u8))
        {
            routeTarget = ParsedRouteTarget.CombatChoiceDecision;
        }
        else if (target.SequenceEqual("/probe/combat-choice-v1/public/action"u8))
        {
            routeTarget = ParsedRouteTarget.CombatChoiceAction;
        }
        else
        {
            routeTarget = ParsedRouteTarget.Unknown;
        }
    }

    private static int FindCrlf(ReadOnlySpan<byte> value, int start)
    {
        for (int index = start; index <= value.Length - 2; index++)
        {
            if (value[index] == (byte)'\r' && value[index + 1] == (byte)'\n')
            {
                return index;
            }
        }

        return -1;
    }

    private static bool IsRequestLine(ReadOnlySpan<byte> value)
    {
        foreach (byte item in value)
        {
            if (item < 0x20 || item > 0x7e)
            {
                return false;
            }
        }

        return true;
    }

    private static bool IsMethod(ReadOnlySpan<byte> value)
    {
        if (value.IsEmpty)
        {
            return false;
        }

        foreach (byte item in value)
        {
            bool alphaNumeric =
                (item >= (byte)'A' && item <= (byte)'Z') ||
                (item >= (byte)'a' && item <= (byte)'z') ||
                (item >= (byte)'0' && item <= (byte)'9');
            bool symbol = item is
                (byte)'!' or (byte)'#' or (byte)'$' or (byte)'%' or (byte)'&' or
                (byte)'\'' or (byte)'*' or (byte)'+' or (byte)'-' or (byte)'.' or
                (byte)'^' or (byte)'_' or (byte)'`' or (byte)'|' or (byte)'~';
            if (!alphaNumeric && !symbol)
            {
                return false;
            }
        }

        return true;
    }

    private static bool IsHeaderName(ReadOnlySpan<byte> value)
    {
        return IsMethod(value);
    }

    private static bool IsHeaderValue(ReadOnlySpan<byte> value)
    {
        foreach (byte item in value)
        {
            if (item < 0x20 || item > 0x7e)
            {
                return false;
            }
        }

        return true;
    }

    private static bool IsFramingHeader(ReadOnlySpan<byte> name)
    {
        return AsciiEqualsIgnoreCase(name, "Content-Length"u8) ||
            AsciiEqualsIgnoreCase(name, "Transfer-Encoding"u8) ||
            AsciiEqualsIgnoreCase(name, "Expect"u8) ||
            AsciiEqualsIgnoreCase(name, "Trailer"u8) ||
            AsciiEqualsIgnoreCase(name, "TE"u8) ||
            AsciiEqualsIgnoreCase(name, "Upgrade"u8);
    }

    private static bool AsciiEqualsIgnoreCase(
        ReadOnlySpan<byte> left,
        ReadOnlySpan<byte> right)
    {
        if (left.Length != right.Length)
        {
            return false;
        }

        for (int index = 0; index < left.Length; index++)
        {
            byte leftValue = left[index];
            byte rightValue = right[index];
            if (leftValue >= (byte)'A' && leftValue <= (byte)'Z')
            {
                leftValue = (byte)(leftValue + ((byte)'a' - (byte)'A'));
            }

            if (rightValue >= (byte)'A' && rightValue <= (byte)'Z')
            {
                rightValue = (byte)(rightValue + ((byte)'a' - (byte)'A'));
            }

            if (leftValue != rightValue)
            {
                return false;
            }
        }

        return true;
    }
}
