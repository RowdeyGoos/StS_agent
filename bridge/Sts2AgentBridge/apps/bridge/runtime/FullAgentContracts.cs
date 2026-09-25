using System;
using System.Text.Json.Nodes;

namespace Sts2AgentBridge.Unified;

// A native action's exact existing contract remains its private dispatch binding.
internal sealed record FullCommand(BridgeRequest Request, JsonObject Candidate);
internal sealed record FullCompletion(string Decision, string Action, Capability Capability, string Path,
    int ChildOrdinal = 0, string? ParentDecision = null, string? ParentAction = null)
{
    internal static FullCompletion For(BridgeRequest request) => new(request.Decision!, request.Action!,
        request.Capability, request.Path, request.ChildOrdinal, request.ParentDecision, request.ParentAction);
}
internal sealed record FullCapture(string Status, JsonObject? Observation, FullCommand[] Commands,
    object[] Bindings, FullCompletion[] Completed, string? Outcome = null, string? Code = null);
internal interface IFullAgentBackend : IDisposable
{
    FullCapture Read();
    ModuleReply Apply(BridgeRequest command);
}

internal static class FullAgentRoutes
{
    internal const string Decision = "/probe/agent-v2/public/decision", Action = "/probe/agent-v2/public/action";
    internal const int MaximumBody = 2097152, MaximumActions = 8192, MaximumReads = 131072, MaximumCandidates = 2048;
    internal static bool IsAction(string? decision, string? action) =>
        decision is { Length: 64 } &&
        System.Linq.Enumerable.All(decision, c => c is >= '0' and <= '9' or >= 'a' and <= 'f') &&
        action?.StartsWith("action:", StringComparison.Ordinal) == true &&
        int.TryParse(action[7..], out int slot) && slot is >= 0 and < MaximumCandidates && action == "action:" + slot;
}
