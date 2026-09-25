using System;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Sts2AgentBridge.Successors.GenericEventReleaseV5;

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

internal static class FullAgentWire
{
    internal static JsonDocument Read(ModuleReply reply)
    {
        try
        {
            if (reply.Terminal)
            {
                if (reply.EventDiagnostic) throw FullReadFailure.NativeEvent(reply.Diagnostic);
                throw new AgentUnsupported();
            }
            // Parse(byte[]) retains that memory. Stream parsing gives the
            // document its own storage before the response buffer is wiped.
            using var input = new MemoryStream(reply.Body, writable: false);
            return JsonDocument.Parse(input);
        }
        finally { Array.Clear(reply.Body); }
    }
}

// Closed read-stage categories only: never expose exception messages, native
// objects, tokens or user data when an observation cannot be constructed.
internal enum FullReadStage { Native, Run, Deck, Relics, Potions, Map, Context, Graph }
internal sealed class FullReadFailure : Exception
{
    internal string Code { get; }
    private FullReadFailure(string code) => Code = code;
    internal static FullReadFailure NativeEvent(GenericEventDiagnosticCode diagnostic)
    {
        // Only fixed failure/ownership categories cross the shared boundary.
        // Never inspect the failed response body or expose exception messages.
        var bounded = diagnostic switch {
            GenericEventDiagnosticCode.NotCaptured or GenericEventDiagnosticCode.ParentReady or
            GenericEventDiagnosticCode.ParentUnavailable or GenericEventDiagnosticCode.ParentWaiting or
            GenericEventDiagnosticCode.ParentMap or GenericEventDiagnosticCode.ParentOverlay or
            GenericEventDiagnosticCode.ParentLayout or GenericEventDiagnosticCode.ParentTravel or
            GenericEventDiagnosticCode.ChildReady or GenericEventDiagnosticCode.MapReady or
            GenericEventDiagnosticCode.CaptureDisposed or GenericEventDiagnosticCode.CaptureException or
            GenericEventDiagnosticCode.PendingBindingFailed or GenericEventDiagnosticCode.PendingOwnership or
            GenericEventDiagnosticCode.PendingContext or GenericEventDiagnosticCode.PendingTaskFailed or
            GenericEventDiagnosticCode.PendingChosenEntry or GenericEventDiagnosticCode.PendingChosenTask or
            GenericEventDiagnosticCode.PendingChosenCompletion or GenericEventDiagnosticCode.PendingRequestTask or
            GenericEventDiagnosticCode.PendingScreen or GenericEventDiagnosticCode.PendingSelectorlessRequest or
            GenericEventDiagnosticCode.PendingOverlay or GenericEventDiagnosticCode.PendingDeck or
            GenericEventDiagnosticCode.PendingOffers or GenericEventDiagnosticCode.PendingProceed or
            GenericEventDiagnosticCode.PendingOwnerBinding or GenericEventDiagnosticCode.PendingOwnerHooks or
            GenericEventDiagnosticCode.PendingOwnerThread or GenericEventDiagnosticCode.PendingOwnerPatches => diagnostic,
            _ => GenericEventDiagnosticCode.DiagnosticUnavailable
        };
        return new("read_native_event_" + GenericEventDiagnosticCodec.Encode(bounded));
    }
    private FullReadFailure(FullReadStage stage) => Code = stage switch {
        FullReadStage.Native => "read_native_failed", FullReadStage.Run => "read_run_failed",
        FullReadStage.Deck => "read_deck_failed", FullReadStage.Relics => "read_relics_failed",
        FullReadStage.Potions => "read_potions_failed", FullReadStage.Map => "read_map_failed",
        FullReadStage.Context => "read_context_failed", FullReadStage.Graph => "read_graph_failed",
        _ => "agent_boundary_failed"
    };
    internal static T At<T>(FullReadStage stage, Func<T> read)
    {
        try { return read(); }
        catch (FullReadFailure) { throw; }
        catch { throw new FullReadFailure(stage); }
    }
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
