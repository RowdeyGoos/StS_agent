using System;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Rooms.Rest;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomReleaseV1;
using Sts2AgentBridge.Unified;

internal static partial class Program
{
    private static int ServeRest(string action)
    {
        var fixture = new RestFlowTests.Native(action) { Done = true };
        var (runtime, port) = Start((_, nonce) => new RestModule(nonce, fixture), new CoreFixture { MapReady = true });
        Console.WriteLine(JsonSerializer.Serialize(new { port }));
        var stop = Task.Run(Console.ReadLine);
        var until = DateTime.UtcNow.AddSeconds(30);
        while (!stop.IsCompleted && DateTime.UtcNow < until) { runtime.DrainFrame(); Thread.Sleep(1); }
        Stop(runtime);
        Check(fixture.Begins == 1 && fixture.Finished, "rest socket completed once");
        return 0;
    }
    private sealed class RestModule : IBridgeModule
    {
        private readonly string _nonce;
        private readonly RoomFlowWireService _wire;
        public RestModule(string nonce, RestFlowTests.Native native) { _nonce = nonce; _wire = new(nonce, new RestV2Session(nonce, native)); }
        public Capability Capability => Capability.Rooms;
        public bool Owns(BridgeRequest request) => request.Capability == Capability.Rooms;
        public ModuleReply Handle(BridgeRequest request)
        {
            var route = request.IsPost ? RoomFlowTransportRoute.ParentPost : RoomFlowTransportRoute.ParentGet;
            byte[] body = _wire.Handle(request.Method, request.Path, request.Decision, request.Action);
            var classification = RoomFlowTerminalClassifier.Classify(route, RoomFlowSelection.Rest, _nonce, body);
            Check(classification != TerminalClassification.Invalid, "rest socket classifier");
            using var json = JsonDocument.Parse(body);
            bool complete = json.RootElement.GetProperty("status").GetString() == "complete";
            return new(body, Complete: complete, Terminal: !complete && classification == TerminalClassification.Terminal);
        }
        public void Dispose() => _wire.Dispose();
    }
}
