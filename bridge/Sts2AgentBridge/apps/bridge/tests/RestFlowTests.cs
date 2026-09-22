using System;
using System.Text.Json;
using Sts2AgentBridge.Rooms.Rest;
using Sts2AgentBridge.Successors.RoomFlowsV1;
using Sts2AgentBridge.Successors.RoomReleaseV1;

internal static class RestFlowTests
{
    internal static void Run(Action<bool, string> check)
    {
        foreach (string action in new[] { "lift", "kindle", "dig", "clone", "hatch", "cook:0:2" })
        {
            string nonce = new('a', 32);
            var native = new Native(action);
            using var wire = new RoomFlowWireService(nonce, new RestV2Session(nonce, native));
            byte[] Read() => wire.Handle("GET", RoomFlowWireProtocol.DecisionRoute, null, null);
            void Classify(byte[] body, RoomFlowTransportRoute route, TerminalClassification expected) =>
                check(RoomFlowTerminalClassifier.Classify(route, RoomFlowSelection.Rest, nonce, body) == expected, "rest classifier");
            var ready = Read(); Classify(ready, RoomFlowTransportRoute.ParentGet, TerminalClassification.NonTerminal);
            using var json = JsonDocument.Parse(ready);
            string decision = json.RootElement.GetProperty("decision_id").GetString()!;
            var receipt = wire.Handle("POST", RoomFlowWireProtocol.ActionRoute, decision, action);
            Classify(receipt, RoomFlowTransportRoute.ParentPost, TerminalClassification.NonTerminal);
            Classify(Read(), RoomFlowTransportRoute.ParentGet, TerminalClassification.NonTerminal);
            native.Done = true;
            var complete = Read(); Classify(complete, RoomFlowTransportRoute.ParentGet, TerminalClassification.Terminal);
            check(native.Finished && native.Begins == 1, "cleanup precedes rest handoff");
            check(RoomFlowTerminalClassifier.Classify(RoomFlowTransportRoute.ParentGet, RoomFlowSelection.Event, nonce, complete) == TerminalClassification.Invalid, "rest cannot masquerade as event");
            var duplicate = wire.Handle("POST", RoomFlowWireProtocol.ActionRoute, decision, action);
            using var failure = JsonDocument.Parse(duplicate);
            check(failure.RootElement.GetProperty("status").GetString() == "error" && native.Begins == 1, "rest terminal cannot redispatch");
        }
    }
    internal sealed class Native(string action) : IRestV2NativeAdapter
    {
        private readonly object _root = new(), _option = new(), _relic = new(), _button = new();
        public bool Done, Finished;
        public int Begins;
        private int Before => RestV2Session.Kind(action) == "cook" ? 60 : action == "clone" ? 3 : 0;
        private int Amount => action == "clone" ? 2 : 0;
        public RestV2Surface Capture() => new(_root, _root, _root, _root, true,
            Begins == 0 ? new[] { new RestV2NativeOption(new(RestV2Session.Kind(action), Before, true, Amount), _option, _relic, _button) } : Array.Empty<RestV2NativeOption>()) { Cards = Begins == 0 && RestV2Session.Kind(action) == "cook" ? new[] { new RestV2Card(0, "STRIKE", 0, true), new RestV2Card(1, "KEEP", 0, false), new RestV2Card(2, "DEFEND", 0, true) } : Array.Empty<RestV2Card>() };
        public void Begin(RestV2NativeOption option, string actionId) => Begins++;
        public RestV2Progress Poll() => new(Done, false, Before + RestV2Session.Delta(action, Amount));
        public void Finish() => Finished = true;
        public void Dispose() { }
    }
}
