using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Unified;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static readonly string Token = new('a', 64), Decision = new('b', 64);
    private static int _checks;
    private static void Check(bool test, string label) { _checks++; if (!test) throw new Exception(label); }
    private static BridgeRequest Request(Capability c, string path, bool post = false) => new(c, path, post, 0, 64, post ? Decision : null, post ? "choose:0" : null);
    private static CoreBridgeModule Core(CoreFixture f) => new(Nonce, f, f, f, f, f, f, f, f, f);
    private static string Body(BridgeReply reply) => Encoding.UTF8.GetString(reply.Response);
    private static int Main(string[] args)
    {
        try
        {
            if (args.SequenceEqual(new[] { "--serve" })) return Serve();
            Ownership(); CleanupFailure(); CoreHandoff(); Parser(); SocketHandoff(); LostResponse(); DuplicatePost();
            Console.WriteLine("{\"status\":\"passed\",\"suite\":\"unified_bridge\",\"checks\":" + _checks + "}");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
    private static int Serve()
    {
        var (runtime, port) = Start((capability, _) => new FakeModule(capability) { AutoComplete = true });
        Console.WriteLine("{\"port\":" + port + "}");
        var stop = Task.Run(Console.ReadLine);
        var until = DateTime.UtcNow.AddSeconds(30);
        while (!stop.IsCompleted && DateTime.UtcNow < until) { runtime.DrainFrame(); Thread.Sleep(1); }
        Stop(runtime);
        return 0;
    }
    private static void Ownership()
    {
        var created = new List<FakeModule>(); var nonces = new HashSet<string>();
        using var router = new BridgeRouter(Core(new()), (c,n) => { Check(nonces.Add(n), "new nonce per session"); var m = new FakeModule(c); created.Add(m); return m; });
        var events = Request(Capability.Events, "/probe/generic-event-v7/public/decision");
        router.Handle(events);
        Check(Body(router.Handle(Request(Capability.Items, "/probe/item-v1/public/item-decision"))).Contains("capability_busy"), "event owns child");
        Check(created.Count == 1 && created[0].Calls == 1, "busy route never creates or calls another native module");
        Check(Body(router.Handle(Request(Capability.Core, "/probe/v0/manifest"))).Contains("1.0.0"), "metadata reports unified release");
        created[0].Complete = true; router.Handle(events);
        Check(created[0].Disposed, "complete releases native hooks");
        router.Handle(Request(Capability.Rooms, "/probe/room-flows-v1/public/decision"));
        created[1].OwnItems = true;
        router.Handle(Request(Capability.Items, "/probe/item-v1/public/item-decision"));
        Check(created.Count == 2 && created[1].Calls == 2, "room-owned item child uses its parent");
        created[1].Terminal = true;
        Check(router.Handle(Request(Capability.Rooms, "/probe/room-flows-v1/public/decision")).Terminal, "native uncertainty latches failure");
        Check(router.Handle(events).Terminal && created.Count == 2, "failure cannot become handoff");
    }
    private static void CleanupFailure()
    {
        var module = new FakeModule(Capability.Events) { Complete = true, FailDispose = true };
        var router = new BridgeRouter(Core(new()), (_,_) => module);
        Check(router.Handle(Request(Capability.Events, "/probe/generic-event-v7/public/decision")).Terminal, "failed cleanup stops handoff");
        try { router.Dispose(); throw new Exception("expected cleanup failure"); } catch (InvalidOperationException) { }
        module.FailDispose = false; router.Dispose();
        Check(module.Disposed && module.DisposeAttempts == 3, "cleanup owner retained for owner-frame retry");
    }
    private static void CoreHandoff()
    {
        var core = new CoreFixture(); int factories = 0;
        using var router = new BridgeRouter(Core(core), (c,_) => { factories++; return new FakeModule(c); });
        var post = new BridgeRequest(Capability.Core, "/probe/v0/public/map-action", true, 0, 64, Decision, "select:0");
        Check(!router.Handle(post).Terminal && core.Applies == 1, "base map action accepted");
        var next = Request(Capability.Events, "/probe/generic-event-v7/public/decision");
        Check(Body(router.Handle(next)).Contains("capability_busy") && factories == 0, "pending core action blocks native session creation");
        router.Handle(Request(Capability.Core, "/probe/v0/public/map-decision"));
        Check(Body(router.Handle(next)).Contains("capability_busy"), "waiting is not reconciliation");
        core.MapComplete = true;
        Check(!router.Handle(Request(Capability.Core, "/probe/v0/public/map-decision")).Terminal, "base map completion observed");
        Check(!router.Handle(next).Terminal && factories == 1, "base-to-event handoff");
        using var rejected = new BridgeRouter(Core(new CoreFixture { Reject = true }), (c,_) => new FakeModule(c));
        Check(rejected.Handle(post).Terminal, "base rejected action fails closed");
    }
    private static void Parser()
    {
        foreach (string path in new[] { "/probe/v0/public/map-decision", "/probe/item-v1/public/item-decision", "/probe/room-flows-v1/public/decision", "/card-selection-v1/parent", "/probe/generic-event-v7/public/decision" })
            Check(BridgeRequestParser.TryParse(Head(path), out _), "existing route grammar " + path);
        Check(!BridgeRequestParser.TryParse(Head("/probe/v0/public/map-decision", extra: "Origin: https://example.com\r\n"), out _), "origin rejected");
        Check(!BridgeRequestParser.TryParse(Head("/probe/generic-event-v7/public/decision", extra: "Content-Length: 0\r\n"), out _), "framing rejected");
        Check(!BridgeRequestParser.TryParse(Head("/probe/v0/public/map-action", "select:99"), out _), "invalid core action rejected before dispatch");
    }
    private static byte[] Head(string path, string? action = null, string? token = null, string extra = "") => Encoding.ASCII.GetBytes(
        (action is null ? "GET " : "POST ") + path + " HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer " + (token ?? Token) +
        "\r\nAccept: application/json\r\n" + (action is null ? "" : "X-Sts2-Decision-Id: " + Decision + "\r\nX-Sts2-Action-Id: " + action + "\r\n") + extra + "Connection: close\r\n\r\n");
    private static (BridgeTransportRuntime Runtime, int Port) Start(Func<Capability,string,IBridgeModule> factory)
    {
        var runtime = BridgeTransportRuntime.Create(BridgeConfiguration.Enabled.ToArray(), () => Encoding.ASCII.GetBytes(Token), n => new BridgeRouter(Core(new()), factory))!;
        var listener = new TcpListener(IPAddress.Loopback, 0); listener.Start();
        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        Check(runtime.StartForTests(listener), "shared listener starts"); return (runtime, port);
    }
    private static string Exchange(BridgeTransportRuntime runtime, int port, byte[] request)
    {
        var task = Task.Run(() =>
        {
            using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
            socket.ReceiveTimeout = 3000; socket.SendTimeout = 3000;
            socket.Connect(IPAddress.Loopback, port);
            int sent = 0; while (sent < request.Length) sent += socket.Send(request.AsSpan(sent));
            socket.Shutdown(SocketShutdown.Send);
            var bytes = new List<byte>(); byte[] buffer = new byte[8192];
            try { int size; while ((size = socket.Receive(buffer)) > 0) bytes.AddRange(buffer.Take(size)); } catch (SocketException) { }
            return Encoding.UTF8.GetString(bytes.ToArray());
        });
        var deadline = DateTime.UtcNow.AddSeconds(5);
        while (!task.IsCompleted && DateTime.UtcNow < deadline) { runtime.DrainFrame(); Thread.Sleep(1); }
        Check(task.IsCompleted, "bounded socket exchange"); return task.GetAwaiter().GetResult();
    }
    private static void Stop(BridgeTransportRuntime runtime)
    { Check(runtime.StopTransportAndJoin(), "listener joined"); Check(runtime.DisposeServiceOnOwnerFrame(), "owner-frame cleanup"); Check(runtime.IsFullyStopped, "fully stopped"); }
    private static void SocketHandoff()
    {
        var modules = new List<FakeModule>();
        var (runtime, port) = Start((c,_) => { var m = new FakeModule(c); modules.Add(m); return m; });
        Check(Exchange(runtime, port, Head("/probe/generic-event-v7/public/decision", token: new string('c',64))) == "" && modules.Count == 0, "authentication precedes native creation");
        foreach (var (capability, path) in new[] { (Capability.Events,"/probe/generic-event-v7/public/decision"), (Capability.Cards,"/card-selection-v1/parent"), (Capability.Rooms,"/probe/room-flows-v1/public/decision"), (Capability.Items,"/probe/item-v1/public/item-decision") })
        {
            Check(Exchange(runtime, port, Head(path)).Contains("ready"), "module available on same listener " + capability);
            modules[^1].Complete = true;
            Check(Exchange(runtime, port, Head(path)).Contains("resolved") && modules[^1].Disposed && !runtime.IsTerminalOrStopping, "successful completion keeps host running");
        }
        Check(Exchange(runtime, port, Head("/probe/v0/public/map-decision")).Contains("waiting"), "feature-to-core handoff on same listener");
        Stop(runtime);
    }
    private static void LostResponse()
    {
        var module = new FakeModule(Capability.Events); var (runtime,port) = Start((_,_) => module);
        Exchange(runtime,port,Head("/probe/generic-event-v7/public/decision"));
        runtime.DropNextPostResponseForTests = true;
        Check(Exchange(runtime,port,Head("/probe/generic-event-v7/public/action","choose:0")) == "", "lost action response");
        Check(module.Posts == 1 && runtime.IsTerminalOrStopping, "lost response forbids retry and handoff"); Stop(runtime);
    }
    private static void DuplicatePost()
    {
        var module = new FakeModule(Capability.Events); var (runtime,port) = Start((_,_) => module);
        Exchange(runtime,port,Head("/probe/generic-event-v7/public/decision"));
        Exchange(runtime,port,Head("/probe/generic-event-v7/public/action","choose:0"));
        Check(Exchange(runtime,port,Head("/probe/generic-event-v7/public/action","choose:0")) == "", "duplicate closed");
        Check(module.Posts == 1 && runtime.IsTerminalOrStopping, "one native dispatch only"); Stop(runtime);
    }
    private sealed class FakeModule(Capability capability) : IBridgeModule
    {
        public Capability Capability => capability;
        internal bool Complete, Terminal, OwnItems, Disposed, FailDispose, AutoComplete;
        internal int Calls, Posts, DisposeAttempts;
        public bool Owns(BridgeRequest request) => request.Capability == capability || OwnItems && request.Capability == Capability.Items;
        public ModuleReply Handle(BridgeRequest request)
        {
            Calls++; if (request.IsPost) Posts++;
            if (AutoComplete && Calls >= 2) Complete = true;
            return new(Encoding.ASCII.GetBytes("{\"status\":\"" + (Complete ? "resolved" : request.IsPost ? "accepted" : "ready") + "\"}"), Complete, Terminal, EventDiagnostic: capability == Capability.Events);
        }
        public void Dispose() { DisposeAttempts++; if (FailDispose) throw new InvalidOperationException(); Disposed = true; }
    }
    private sealed class CoreFixture : IPublicScreenService, IPublicCombatDecisionService, IPublicCombatActionService,
        IPublicRewardDecisionService, IPublicRewardActionService, IPublicMapDecisionService, IPublicMapActionService,
        IPublicRoomDecisionService, IPublicRoomActionService
    {
        internal bool MapComplete, Reject; internal int Applies;
        PublicScreenReadResult IPublicScreenService.Read() => PublicScreenReadResult.BackendFault();
        PublicCombatDecisionReadResult IPublicCombatDecisionService.Read() => PublicCombatDecisionReadResult.FromSnapshot(PublicCombatDecisionSnapshot.Waiting());
        PublicRewardDecisionReadResult IPublicRewardDecisionService.Read() => PublicRewardDecisionReadResult.FromSnapshot(PublicRewardDecisionSnapshot.Waiting());
        PublicMapDecisionReadResult IPublicMapDecisionService.Read() => PublicMapDecisionReadResult.FromSnapshot(MapComplete ? PublicMapDecisionSnapshot.Complete(new(0,0,1,"unknown")) : PublicMapDecisionSnapshot.Waiting());
        PublicRoomDecisionReadResult IPublicRoomDecisionService.Read() => PublicRoomDecisionReadResult.FromSnapshot(PublicRoomDecisionSnapshot.Waiting());
        PublicCombatActionApplyResult IPublicCombatActionService.Apply(PublicCombatActionRequest r) => PublicCombatActionApplyResult.FromRequest(PublicCombatActionApplyOutcome.Accepted,r);
        PublicRewardActionApplyResult IPublicRewardActionService.Apply(PublicRewardActionRequest r) => PublicRewardActionApplyResult.FromRequest(PublicRewardActionApplyOutcome.Accepted,r);
        PublicRoomActionApplyResult IPublicRoomActionService.Apply(PublicRoomActionRequest r) => PublicRoomActionApplyResult.FromRequest(PublicRoomActionApplyOutcome.Accepted,r);
        PublicMapActionApplyResult IPublicMapActionService.Apply(PublicMapActionRequest r) { Applies++; return PublicMapActionApplyResult.FromRequest(Reject ? PublicMapActionApplyOutcome.StaleDecision : PublicMapActionApplyOutcome.Accepted,r); }
    }
}
