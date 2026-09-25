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
internal interface IFullPotions : ICombatPotions
{
    bool AllowsChoices { get; }
    bool ChoiceOwnerAlive { get; }
    CombatPotionReply ReadFull();
    CombatPotionReply ApplyFull(string decision, string action);
}
internal static class CombatPotionRoutes
{
    internal const string Decision = "/probe/combat-potions-v1/public/decision", Action = "/probe/combat-potions-v1/public/action";
    internal const string FullDecision = "/probe/potions-v2/public/decision", FullAction = "/probe/potions-v2/public/action";
    internal static bool IsFullAction(string? decision,string? action) => IsAction(decision,action)||
        decision is {Length:64}&&decision.All(c=>c is >= '0' and <= '9' or >= 'a' and <= 'f')&&
        action is {Length:9}&&action.StartsWith("discard:",StringComparison.Ordinal)&&action[8] is >= '0' and <= '7';
    internal static bool IsAction(string? decision, string? action) => decision is { Length: 64 } &&
        decision.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f') && action is { Length: 5 or 7 } &&
        action.StartsWith("use:", StringComparison.Ordinal) && action[4] is >= '0' and <= '7' &&
        (action.Length == 5 || action[5] == ':' && action[6] is >= '0' and <= '5');
}
