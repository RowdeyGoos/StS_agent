using System;
using System.Linq;
namespace Sts2AgentBridge.Unified;

internal readonly record struct CombatPotionReply(byte[] Body, bool Terminal = false, bool StaleWithoutMutation = false);
internal interface ICombatPotions : IDisposable
{
    bool Active { get; }
    CombatPotionReply Read();
    CombatPotionReply Apply(string decision, string action);
}
internal static class CombatPotionRoutes
{
    internal const string Decision = "/probe/combat-potions-v1/public/decision", Action = "/probe/combat-potions-v1/public/action";
    internal static bool IsAction(string? decision, string? action) => decision is { Length: 64 } &&
        decision.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f') && action is { Length: 5 or 7 } &&
        action.StartsWith("use:", StringComparison.Ordinal) && action[4] is >= '0' and <= '7' &&
        (action.Length == 5 || action[5] == ':' && action[6] is >= '0' and <= '5');
}
