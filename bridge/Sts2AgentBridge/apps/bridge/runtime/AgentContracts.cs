using System;
using System.Text.Json;
using System.Text.Json.Nodes;
namespace Sts2AgentBridge.Unified;

// Public data and private dispatch bindings have deliberately separate lifetimes.
internal sealed record AgentCommand(string Action, JsonObject Candidate);
internal sealed record AgentCapture(JsonObject Observation, AgentCommand[] Commands, object[] Bindings);
internal interface IAgentPublicReader : IDisposable
{
    string InitialFamily();
    AgentCapture Capture(string family, JsonElement legacy, JsonArray history, string? source);
}
internal sealed class AgentUnsupported : Exception { }
