using System;

namespace Sts2AgentBridge.Core.Protocol;

public enum ProbeMode
{
    Compatible = 1,
    IncompatibleLocked = 2,
}

public enum ProbeRoute
{
    Health = 1,
    Manifest = 2,
    PublicScreen = 3,
    PublicCombatDecision = 4,
    PublicCombatAction = 5,
    PublicRewardDecision = 6,
    PublicRewardAction = 7,
    PublicMapDecision = 8,
    PublicMapAction = 9,
    PublicRoomDecision = 10,
    PublicRoomAction = 11,
}

public static class ProbeRouteCatalog
{
    public const string HealthPath = "/probe/v0/health";
    public const string ManifestPath = "/probe/v0/manifest";
    public const string PublicScreenPath = "/probe/v0/public/screen";
    public const string PublicCombatDecisionPath = "/probe/v0/public/combat-decision";
    public const string PublicCombatActionPath = "/probe/v0/public/combat-action";
    public const string PublicRewardDecisionPath = "/probe/v0/public/reward-decision";
    public const string PublicRewardActionPath = "/probe/v0/public/reward-action";
    public const string PublicMapDecisionPath = "/probe/v0/public/map-decision";
    public const string PublicMapActionPath = "/probe/v0/public/map-action";
    public const string PublicRoomDecisionPath = "/probe/v0/public/room-decision";
    public const string PublicRoomActionPath = "/probe/v0/public/room-action";

    private static readonly string[] CompatibleRoutePaths =
    {
        HealthPath,
        ManifestPath,
        PublicScreenPath,
        PublicCombatDecisionPath,
        PublicCombatActionPath,
        PublicRewardDecisionPath,
        PublicRewardActionPath,
        PublicMapDecisionPath,
        PublicMapActionPath,
        PublicRoomDecisionPath,
        PublicRoomActionPath,
    };

    private static readonly string[] LockedRoutePaths =
    {
        HealthPath,
        ManifestPath,
    };

    public static ReadOnlySpan<string> RegisteredRoutes(ProbeMode mode)
    {
        return mode switch
        {
            ProbeMode.Compatible => CompatibleRoutePaths,
            ProbeMode.IncompatibleLocked => LockedRoutePaths,
            _ => throw new ArgumentOutOfRangeException(nameof(mode)),
        };
    }

    public static bool TryResolve(
        ReadOnlySpan<char> requestTarget,
        ProbeMode mode,
        out ProbeRoute route)
    {
        if (mode is not ProbeMode.Compatible and not ProbeMode.IncompatibleLocked)
        {
            throw new ArgumentOutOfRangeException(nameof(mode));
        }

        if (requestTarget.SequenceEqual(HealthPath))
        {
            route = ProbeRoute.Health;
            return true;
        }

        if (requestTarget.SequenceEqual(ManifestPath))
        {
            route = ProbeRoute.Manifest;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicScreenPath))
        {
            route = ProbeRoute.PublicScreen;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicCombatDecisionPath))
        {
            route = ProbeRoute.PublicCombatDecision;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicCombatActionPath))
        {
            route = ProbeRoute.PublicCombatAction;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicRewardDecisionPath))
        {
            route = ProbeRoute.PublicRewardDecision;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicRewardActionPath))
        {
            route = ProbeRoute.PublicRewardAction;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicMapDecisionPath))
        {
            route = ProbeRoute.PublicMapDecision;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicMapActionPath))
        {
            route = ProbeRoute.PublicMapAction;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicRoomDecisionPath))
        {
            route = ProbeRoute.PublicRoomDecision;
            return true;
        }

        if (mode == ProbeMode.Compatible && requestTarget.SequenceEqual(PublicRoomActionPath))
        {
            route = ProbeRoute.PublicRoomAction;
            return true;
        }

        route = default;
        return false;
    }

    public static bool IsRegistered(ProbeRoute route, ProbeMode mode)
    {
        return route switch
        {
            ProbeRoute.Health => mode is ProbeMode.Compatible or ProbeMode.IncompatibleLocked,
            ProbeRoute.Manifest => mode is ProbeMode.Compatible or ProbeMode.IncompatibleLocked,
            ProbeRoute.PublicScreen => mode == ProbeMode.Compatible,
            ProbeRoute.PublicCombatDecision => mode == ProbeMode.Compatible,
            ProbeRoute.PublicCombatAction => mode == ProbeMode.Compatible,
            ProbeRoute.PublicRewardDecision => mode == ProbeMode.Compatible,
            ProbeRoute.PublicRewardAction => mode == ProbeMode.Compatible,
            ProbeRoute.PublicMapDecision => mode == ProbeMode.Compatible,
            ProbeRoute.PublicMapAction => mode == ProbeMode.Compatible,
            ProbeRoute.PublicRoomDecision => mode == ProbeMode.Compatible,
            ProbeRoute.PublicRoomAction => mode == ProbeMode.Compatible,
            _ => false,
        };
    }
}
