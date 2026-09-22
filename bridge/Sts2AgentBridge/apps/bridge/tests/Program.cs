using Sts2AgentBridge.Successors.GenericEventReleaseV5;
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
using Sts2AgentBridge.Cards.Combat;
using System.Text.Json;

internal static partial class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static readonly string Token = new('a', 64), Decision = new('b', 64);
    private static int _checks;
    private static void Check(bool test, string label) { _checks++; if (!test) throw new Exception(label); }
    private static BridgeRequest Request(Capability c, string path, bool post = false) => new(c, path, post, 0, 64, post ? Decision : null, post ? "choose:0" : null);
    private static CoreBridgeModule Core(CoreFixture f) => new(Nonce, f, f, f, f, f, f, f, f, f, f.Choice);
    private static string Body(BridgeReply reply) => Encoding.UTF8.GetString(reply.Response);
    private static int Main(string[] args)
    {
        try
        {
            if (args.Length == 2 && args[0] == "--serve-shop") return ServeShop(args[1]);
            if (args.Length == 2 && args[0] == "--serve-rest") return ServeRest(args[1]);
            if (args.SequenceEqual(new[] { "--serve" })) return Serve();
            if (args.SequenceEqual(new[] { "--serve-read-timeout" })) return Serve(readTimeout:true);
            if (args.SequenceEqual(new[] { "--serve-combat" })) return Serve(true);
            if (args.SequenceEqual(new[] { "--serve-combat-map" })) return Serve(true, true);
            if (args.SequenceEqual(new[] { "--serve-healing-relic" })) return Serve(true,true,itemRewards:true,healingRelic:true);
            if (args.SequenceEqual(new[] { "--serve-capacity-potions" })) return Serve(true,true,capacityPotions:true);
            if (args.SequenceEqual(new[] { "--serve-replace-potions" })) return Serve(true,true,replacePotions:true);
            if (args.SequenceEqual(new[] { "--serve-full-potions" })) return Serve(true,true,fullPotions:true);
            if (args.SequenceEqual(new[] { "--serve-combat-items" })) return Serve(true,true,itemRewards:true);
            if (args.SequenceEqual(new[] { "--serve-special-card" })) return Serve(true,true,specialCard:true);
            if (args.SequenceEqual(new[] { "--serve-resume-items" })) return Serve(eventResume:true,resumeItems:true);
            if (args.SequenceEqual(new[] { "--serve-event-resume" })) return Serve(eventResume:true);
            RestFlowTests.Run(Check); EventBoundaryTests.Run(Check); EventCombatTransfer(); EventCombatResume(); ResumeItemRouting(); Ownership(); CleanupFailure(); CoreHandoff(); CombatChoiceHandoff(); Parser(); ResumeDiagnostics(); ReadDispatchFailures(); SocketHandoff(); StaleRecovery(); LostResponse(); DuplicatePost(); RepeatedCombatIdentities();
            Console.WriteLine("{\"status\":\"passed\",\"suite\":\"unified_bridge\",\"checks\":" + _checks + "}");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
    private static int Serve(bool combat = false, bool rewards = false, bool eventResume=false,bool resumeItems=false,bool specialCard=false,bool itemRewards=false,bool fullPotions=false,bool replacePotions=false,bool capacityPotions=false,bool readTimeout=false,bool healingRelic=false)
    {
        var fixture = eventResume?new CoreFixture{CombatReady=true,MapReady=true}:combat ? CombatScenario() : new CoreFixture { Reject = true, MapReady = true };
        fixture.HealingRelicScenario=healingRelic;fixture.RewardScenario = rewards;fixture.SpecialCardScenario=specialCard;fixture.ItemRewardScenario=itemRewards;fixture.FullPotionScenario=fullPotions;fixture.ReplacePotionScenario=replacePotions;fixture.CapacityPotionScenario=capacityPotions;
        var (runtime, port) = Start((capability, _) => resumeItems?new ResumeItemModule(fixture):eventResume?new FakeModule(capability){Complete=true,CombatScope=()=>fixture.CombatAccepted==0,CombatResume=()=>fixture.CombatAccepted==0?"combat":"resumed",EventNonce=Nonce}:new FakeModule(capability) { AutoComplete = true }, fixture);
        Console.WriteLine("{\"port\":" + port + "}");
        var stop = Task.Run(Console.ReadLine);
        var until = DateTime.UtcNow.AddSeconds(30);
        while (!stop.IsCompleted && DateTime.UtcNow < until) { if(!readTimeout)runtime.DrainFrame(); Thread.Sleep(1); }
        Stop(runtime);
        return 0;
    }
    private static void EventCombatTransfer()
    {
        foreach(var mode in new[]{"complete","changed","dispose_failure","invalid_transfer"}) {
            bool valid=mode!="invalid_transfer";int begins=0;
            var f=CombatScenario();f.Stage=0;
            var core=new CoreBridgeModule(Nonce,f,f,f,f,f,f,f,f,f,f.Choice,()=>{begins++;});
            var eventModule=new FakeModule(Capability.Events){Complete=true,FailDispose=mode=="dispose_failure",CombatScope=()=>valid};
            var router=new BridgeRouter(core,(_,_)=>eventModule);
            var events=Request(Capability.Events,"/probe/generic-event-v7/public/decision");
            var reply=router.Handle(events);
            if(mode is "dispose_failure" or "invalid_transfer") {
                Check(reply.Terminal&&begins==0,"failed transfer cannot arm combat: "+mode);
                Check(router.Handle(events).Terminal,"failed transfer cannot restart event");
                eventModule.FailDispose=false;router.Dispose();continue;
            }
            Check(!reply.Terminal&&eventModule.Disposed&&begins==1&&core.HasPendingAction,"clean event transfers once and resets combat observation");
            Check(Body(router.Handle(events)).Contains("capability_busy"),"combat scope blocks a new event");
            Check(Body(router.Handle(Request(Capability.Core,"/probe/v0/public/reward-decision"))).Contains("capability_busy"),"rewards blocked until combat terminal");
            if(mode=="changed") {
                valid=false;Check(router.Handle(Request(Capability.Core,"/probe/v0/public/combat-decision")).Terminal,"changed combat latches host failure");
                valid=true;Check(router.Handle(events).Terminal,"restoring identity does not retry failed handoff");
            } else {
                Check(!router.Handle(Request(Capability.Core,"/probe/v0/public/combat-decision")).Terminal&&core.HasPendingAction,"ready combat retains scope");
                f.Stage=3;Check(Body(router.Handle(Request(Capability.Core,"/probe/v0/public/combat-decision"))).Contains("complete")&&!core.HasPendingAction,"matching combat terminal releases scope");
                Check(!router.Handle(Request(Capability.Core,"/probe/v0/public/reward-decision")).Terminal,"reward observation admitted after matching terminal");
            }
            router.Dispose();
        }
    }
    private static void EventCombatResume()
    {
        foreach(var mode in new[]{"resume","dispose_failure","chooser","bad_nonce","unsupported","terminal_before_resume"}) {
            string phase="combat";var f=mode is "chooser" or "terminal_before_resume"?CombatScenario():new CoreFixture{CombatReady=true};
            var core=Core(f);
            var owner=new FakeModule(Capability.Events){Complete=true,CombatScope=()=>phase=="combat",CombatResume=()=>phase,EventNonce=mode=="bad_nonce"?"bad":Nonce};
            var router=new BridgeRouter(core,(_,_)=>owner);
            var eventRead=Request(Capability.Events,"/probe/generic-event-v7/public/decision");
            var entry=router.Handle(eventRead);
            if(mode=="bad_nonce") {Check(entry.Terminal&&!owner.Disposed,"invalid resume nonce retains cleanup owner");router.Dispose();continue;}
            Check(!entry.Terminal&&!owner.Disposed&&core.HasPendingAction,"resume hook owner retained through combat");
            if(mode=="chooser") {f.Stage=1;router.Handle(Request(Capability.Core,CombatCardChoiceService.DecisionRoute));}
            else if(mode=="terminal_before_resume") {f.Stage=3;router.Handle(Request(Capability.Core,"/probe/v0/public/combat-decision"));Check(core.HasPendingAction,"victory alone cannot release event owner");}
            else router.Handle(new(Capability.Core,"/probe/v0/public/combat-action",true,0,64,Decision,"end_turn"));
            phase="waiting";
            Check(!router.Handle(Request(Capability.Core,"/probe/v0/public/combat-decision")).Terminal,"room-switch race waits for owned resume");
            int applies=f.CombatAccepted;
            var stale=router.Handle(new(Capability.Core,"/probe/v0/public/combat-action",true,0,64,Decision,"end_turn"));
            Check(!stale.Terminal&&stale.StaleWithoutMutation&&f.CombatAccepted==applies,"room-switch POST rejected without mutation");
            Check(Body(router.Handle(eventRead)).Contains("capability_busy"),"event cannot restart while resume is pending");
            Check(Body(router.Handle(Request(Capability.Core,CoreBridgeModule.EventCombatRoute))).Contains("waiting"),"continuation callable through pending combat action");
            phase=mode=="unsupported"?"unsupported":"resumed";owner.FailDispose=mode=="dispose_failure";
            var done=router.Handle(Request(Capability.Core,CoreBridgeModule.EventCombatRoute));
            if(mode is "chooser" or "dispose_failure" or "unsupported") {
                Check(done.Terminal&&!owner.Disposed,"unresolved chooser, failed callback or cleanup cannot resume: "+mode);
                owner.FailDispose=false;
            } else Check(!done.Terminal&&owner.Disposed&&!core.HasPendingAction&&Body(done).Contains("resumed"),"verified callback and cleanup release pending combat");
            router.Dispose();
        }
    }
    private static void ResumeItemRouting()
    {
        foreach(var mode in new[]{"complete","terminal","premature_complete","chooser"}) {
            string phase="combat";var f=mode=="chooser"?CombatScenario():new CoreFixture{CombatReady=true};
            var core=Core(f);var module=new FakeModule(Capability.Events){Complete=true,CombatScope=()=>phase=="combat",CombatResume=()=>phase,EventNonce=Nonce};
            using var router=new BridgeRouter(core,(_,_)=>module);
            var item=Request(Capability.Core,CoreBridgeModule.ResumeItemRead);
            router.Handle(Request(Capability.Events,"/probe/generic-event-v7/public/decision"));
            int calls=module.Calls;
            Check(Body(router.Handle(item)).Contains("capability_busy")&&module.Calls==calls,"item cannot be adopted during combat");
            if(mode=="chooser"){f.Stage=1;router.Handle(Request(Capability.Core,CombatCardChoiceService.DecisionRoute));}
            phase="item";module.Complete=mode=="premature_complete";module.Terminal=mode=="terminal";
            var response=router.Handle(item);
            if(mode=="chooser")Check(Body(response).Contains("capability_busy")&&module.Calls==calls,"active combat chooser blocks resume items");
            else if(mode is "terminal" or "premature_complete")Check(response.Terminal&&!module.Disposed,"child failure or premature parent release stops");
            else {
                Check(!response.Terminal&&module.Calls==calls+1&&!module.Disposed&&core.HasPendingAction,"item retains event and combat owners");
                Check(Body(router.Handle(Request(Capability.Core,"/probe/v0/public/map-decision"))).Contains("capability_busy"),"map blocked during item");
                Check(Body(router.Handle(Request(Capability.Items,"/probe/item-v1/public/item-decision"))).Contains("capability_busy"),"standalone item cannot replace resume child");
                phase="resumed";
                Check(!router.Handle(Request(Capability.Core,CoreBridgeModule.EventCombatRoute)).Terminal&&module.Disposed&&!core.HasPendingAction,"only resume verification releases item parent");
            }
        }
        Check(BridgeRequestParser.TryParse(Head(CoreBridgeModule.ResumeItemRead),out _),"resume item GET grammar");
        Check(BridgeRequestParser.TryParse(Head(CoreBridgeModule.ResumeItemAction,"collect:7"),out var parsed)&&parsed.IsPost,"resume item POST grammar");
        Check(!BridgeRequestParser.TryParse(Head(CoreBridgeModule.ResumeItemAction,"collect:256"),out _),"bounded resume item index");
        Check(!BridgeRequestParser.TryParse(Head(CoreBridgeModule.ResumeItemAction,"end_turn"),out _),"resume item rejects combat command");
        Check(!BridgeRequestParser.TryParse(Head("/probe/event-combat-v1/public/decision"),out _),"old continuation protocol not silently broadened");
    }
    private sealed class ResumeItemModule(CoreFixture core) : IBridgeModule
    {
        private bool _collected,_resolved;
        private readonly Sts2AgentBridge.Successors.ItemV1.ItemV1Offer[] _offers={new(7,"potion","RESUME_POTION",true)};
        private readonly string?[] _slots={null,null};
        private readonly string[] _actions={"collect:7"};
        public Capability Capability=>Capability.Events;
        public bool Owns(BridgeRequest r)=>r.Capability==Capability.Events;
        private string DecisionId=>Sts2AgentBridge.Successors.ItemV1.ItemV1CanonicalEncoder.ComputeDecisionId(Nonce,_offers,_slots,_actions);
        public ModuleReply Handle(BridgeRequest r) {
            if(!CoreBridgeModule.IsResumeItem(r))return new("{\"status\":\"resolved\"}"u8.ToArray(),Complete:true,EventDiagnostic:true,
                CombatScope:()=>core.CombatAccepted==0,CombatResume:()=>core.CombatAccepted==0?"combat":_resolved?"resumed":"item",EventNonce:Nonce);
            object value;
            if(r.IsPost) {
                Check(!_collected&&r.Decision==DecisionId&&r.Action=="collect:7","socket exact resume collection command");_collected=true;
                value=new Sts2AgentBridge.Successors.ItemV1.ItemV1DispatchReceipt(Nonce,DecisionId,"collect:7");
            } else if(_collected) {
                _resolved=true;value=new Sts2AgentBridge.Successors.ItemV1.ItemV1ResolvedResult(Nonce,DecisionId,"collect:7",7,"potion","RESUME_POTION");
            } else value=new Sts2AgentBridge.Successors.ItemV1.ItemV1Observation(Nonce,"ready",DecisionId,_offers,_slots,_actions);
            return new(Sts2AgentBridge.Successors.GenericEventV7.GenericEventV7WireService.EncodeItem(value));
        }
        public void Dispose(){}
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
        foreach (var (kind, action) in new[] { ("combat", "end_turn"), ("reward", "proceed"), ("map", "select:0"), ("room", "proceed") })
        {
            var fixture = new CoreFixture { Reject = true };
            var module = Core(fixture);
            using var rejected = new BridgeRouter(module, (c,_) => new FakeModule(c));
            var stale = new BridgeRequest(Capability.Core, "/probe/v0/public/" + kind + "-action", true, 0, 64, Decision, action);
            var reply = rejected.Handle(stale);
            Check(!reply.Terminal && Body(reply).Contains("stale_decision"), "safe stale rejection preserves host: " + kind);
            Check(!module.HasPendingAction, "stale rejection does not create a mutation fence: " + kind);
            Check(!rejected.Handle(Request(Capability.Core, "/probe/v0/public/" + kind + "-decision")).Terminal, "fresh observation after stale rejection: " + kind);
            Check(!rejected.Handle(next).Terminal, "stale rejection permits clean handoff: " + kind);
        }
        using var fault = new BridgeRouter(Core(new CoreFixture { Fault = true }), (c,_) => new FakeModule(c));
        Check(fault.Handle(post).Terminal && fault.Handle(next).Terminal, "backend fault remains terminal");
    }
    private static CoreFixture CombatScenario()
    {
        var core = new CoreFixture { Scenario = true };
        var selection = new ChoiceFixture { OnDispose = () => core.Stage = 2 };
        core.Choice = new CombatCardChoiceService(() => core.Stage == 1 ? selection : null, Nonce);
        return core;
    }
    private static void CombatChoiceHandoff()
    {
        var fixture = CombatScenario(); int factories = 0;
        var module = Core(fixture);
        using var router = new BridgeRouter(module, (c,_) => { factories++; return new FakeModule(c); });
        router.Handle(new(Capability.Core,"/probe/v0/public/combat-action",true,0,64,Decision,"play:0:0"));
        Check(module.HasPendingAction && fixture.Stage == 1, "accepted combat parent retained");
        var ready = module.Handle(Request(Capability.Core,CombatCardChoiceService.DecisionRoute));
        using var parsed = JsonDocument.Parse(ready.Body);
        string choiceDecision = parsed.RootElement.GetProperty("decision_id").GetString()!;
        Check(Body(router.Handle(Request(Capability.Core,"/probe/v0/public/combat-decision"))).Contains("capability_busy"), "nested choice owns core gameplay");
        var events = Request(Capability.Events,"/probe/generic-event-v7/public/decision");
        Check(Body(router.Handle(events)).Contains("capability_busy") && factories == 0, "choice blocks foreign module creation");
        Check(!router.Handle(new(Capability.Core,CombatCardChoiceService.ActionRoute,true,0,64,choiceDecision,"select:0")).Terminal, "nested choice input accepted");
        Check(Body(router.Handle(Request(Capability.Core,CombatCardChoiceService.DecisionRoute))).Contains("selection_verified"), "exact child completion");
        Check(module.HasPendingAction && Body(router.Handle(events)).Contains("capability_busy"), "child cleanup does not reconcile parent card");
        router.Handle(Request(Capability.Core,"/probe/v0/public/combat-decision"));
        Check(!module.HasPendingAction, "fresh combat decision reconciles parent");
        Check(!router.Handle(events).Terminal && factories == 1, "completed combat reconciliation releases ownership");
        foreach (bool failDispose in new[] { false, true })
        {
            var child = new ChoiceFixture { FailDispose = failDispose, Throw = !failDispose };
            var service = new CombatCardChoiceService(() => child,Nonce);
            var f = new CoreFixture { Choice = service }; var failed = Core(f);
            var observation = failed.Handle(Request(Capability.Core,CombatCardChoiceService.DecisionRoute));
            using var value = JsonDocument.Parse(observation.Body);
            var action = new BridgeRequest(Capability.Core,CombatCardChoiceService.ActionRoute,true,0,64,
                value.RootElement.GetProperty("decision_id").GetString(),"select:0");
            var reply = failed.Handle(action);
            if (failDispose) reply = failed.Handle(Request(Capability.Core,CombatCardChoiceService.DecisionRoute));
            Check(reply.Terminal && failed.HasPendingAction && child.Calls == 1, "uncertainty or failed child cleanup retains owner");
            child.FailDispose = false; failed.Dispose();
        }
    }
    private sealed class ChoiceFixture : ICombatCardChoiceAdapter
    {
        private readonly object _identity = new(), _model = new(), _holder = new();
        internal bool Closed, FailDispose, Throw; internal int Calls; internal Action OnDispose = () => { };
        public ChoiceSurface Capture() => new(_identity,"discard",0,1,false,true,Closed,Closed,false,
            new[] { new ChoiceCard(_model,_holder,"STRIKE",0,Closed,true) },Closed ? new[] { _model } : Array.Empty<object>(),true);
        public void Toggle(int slot) { Calls++; Closed = true; if (Throw) throw new Exception(); }
        public void Confirm() => throw new Exception("not used by this scenario");
        public void Dispose() { if (FailDispose) throw new Exception(); OnDispose(); }
    }
    private static void Parser()
    {
        foreach (string action in new[] { "lift", "kindle", "dig", "clone", "hatch", "cook:0:2", "cook:1:63" })
            Check(BridgeRequestParser.TryParse(Head("/probe/room-flows-v1/public/action", action), out var rest) && rest.Capability == Capability.Rooms && rest.Action == action, "rest request grammar");
        foreach (string action in new[] { "lift:0", "kindle:0", "cook", "cook:2:0", "cook:0:0", "cook:00:1", "cook:0:64", "Lift", "kindle ", "lift\r\nOrigin: evil" })
            Check(!BridgeRequestParser.TryParse(Head("/probe/room-flows-v1/public/action", action), out _), "rest request rejected");
        string lineage="X-Sts2-Child-Ordinal: 1\r\nX-Sts2-Parent-Decision-Id: "+Decision+"\r\nX-Sts2-Parent-Action-Id: choose:0\r\n";
        foreach(string action in new[]{"cancel","confirm_abandon","tool:small","tool:big","reveal:0","reveal:120","reward:claim:7","reward:collect:7","reward:open:7","reward:choose:4","reward:skip_card","dismiss"}) {
            Check(BridgeRequestParser.TryParse(Head("/probe/generic-event-v7/public/action",action,extra:lineage),out var parsed)&&parsed.IsPost,"sphere child header "+action);
            Check(!BridgeRequestParser.TryParse(Head("/probe/generic-event-v7/public/action",action),out _),"sphere action not parent "+action);
        }
        foreach(string action in new[]{"tool:huge","reveal:121","reveal:00","reward:claim:8","reward:choose:5","reward:open:00","tool:big\r\nOrigin: evil"})
            Check(!BridgeRequestParser.TryParse(Head("/probe/generic-event-v7/public/action",action,extra:lineage),out _),"sphere header bounded "+action);
        foreach (string path in new[] { "/probe/combat-choice-v1/public/decision", "/probe/v0/public/map-decision", "/probe/item-v1/public/item-decision", "/probe/room-flows-v1/public/decision", "/card-selection-v1/parent", "/probe/generic-event-v7/public/decision" })
            Check(BridgeRequestParser.TryParse(Head(path), out _), "existing route grammar " + path);
        Check(!BridgeRequestParser.TryParse(Head("/probe/v0/public/map-decision", extra: "Origin: https://example.com\r\n"), out _), "origin rejected");
        Check(!BridgeRequestParser.TryParse(Head("/probe/generic-event-v7/public/decision", extra: "Content-Length: 0\r\n"), out _), "framing rejected");
        Check(!BridgeRequestParser.TryParse(Head("/probe/v0/public/map-action", "select:99"), out _), "invalid core action rejected before dispatch");
    }
    private static byte[] Head(string path, string? action = null, string? token = null, string extra = "", string? decision = null) => Encoding.ASCII.GetBytes(
        (action is null ? "GET " : "POST ") + path + " HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer " + (token ?? Token) +
        "\r\nAccept: application/json\r\n" + (action is null ? "" : "X-Sts2-Decision-Id: " + (decision ?? Decision) + "\r\nX-Sts2-Action-Id: " + action + "\r\n") + extra + "Connection: close\r\n\r\n");
    private static (BridgeTransportRuntime Runtime, int Port) Start(Func<Capability,string,IBridgeModule> factory, CoreFixture? core = null)
    {
        var runtime = BridgeTransportRuntime.Create(BridgeConfiguration.Enabled.ToArray(), () => Encoding.ASCII.GetBytes(Token), n => new BridgeRouter(Core(core ?? new()), factory))!;
        var listener = new TcpListener(IPAddress.Loopback, 0); listener.Start();
        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        Check(runtime.StartForTests(listener), "shared listener starts"); return (runtime, port);
    }
    private static string Exchange(BridgeTransportRuntime runtime, int port, byte[] request, bool drain = true)
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
        while (!task.IsCompleted && DateTime.UtcNow < deadline) { if(drain) runtime.DrainFrame(); Thread.Sleep(1); }
        Check(task.IsCompleted, "bounded socket exchange"); return task.GetAwaiter().GetResult();
    }
    private static void Stop(BridgeTransportRuntime runtime)
    { Check(runtime.StopTransportAndJoin(), "listener joined"); Check(runtime.DisposeServiceOnOwnerFrame(), "owner-frame cleanup"); Check(runtime.IsFullyStopped, "fully stopped"); }
    private static void ResumeDiagnostics() {
        foreach(var code in Enum.GetValues<GenericEventDiagnosticCode>()) {
            var text=GenericEventDiagnosticCodec.Encode(code);
            Check(GenericEventDiagnosticCodec.Normalize(code)==code&&System.Text.RegularExpressions.Regex.IsMatch(text,"^[a-z_]{1,33}$"),"closed bounded diagnostic vocabulary");
            if(code!=GenericEventDiagnosticCode.DiagnosticUnavailable)Check(text!="diagnostic_unavailable","defined diagnostic has explicit wire mapping");
        }
        Check(GenericEventDiagnosticCodec.Normalize((GenericEventDiagnosticCode)999)==GenericEventDiagnosticCode.DiagnosticUnavailable,"unknown diagnostic normalized");

        foreach(var code in new[]{Sts2AgentBridge.Successors.GenericEventV7.GenericEventV7ResumeDiagnostic.callback_parent_retained,
            (Sts2AgentBridge.Successors.GenericEventV7.GenericEventV7ResumeDiagnostic)999}) {
            var core=Core(new());core.BindCombatScope(()=>true,()=>"unsupported",Nonce,()=>code);
            var reply=core.Handle(Request(Capability.Core,"/probe/event-combat-v2/public/decision"));
            using var body=JsonDocument.Parse(reply.Body);
            Check(reply.Terminal&&body.RootElement.GetProperty("code").GetString()=="backend_fault","resume diagnostic remains terminal backend failure");
            Check(body.RootElement.GetProperty("resume_diagnostic").GetString()==(code==(Sts2AgentBridge.Successors.GenericEventV7.GenericEventV7ResumeDiagnostic)999?"diagnostic_unavailable":"callback_parent_retained"),"closed resume vocabulary including unknown enum");
            Array.Clear(reply.Body);core.Dispose();
        }
    }
    private static void ReadDispatchFailures()
    {
        foreach(var mode in new[]{"before", "after", "stages", "fault", "post", "unauthenticated"})
        {
            int created=0;FakeModule? module=null;
            var (runtime,port)=Start((capability,_)=>{
                created++;
                if(mode=="after")Thread.Sleep(700);
                if(mode=="fault")throw new InvalidOperationException("private exception text");
                return module=new FakeModule(capability){ReadWork=mode=="stages"?trace=>{trace!.Mark(4);Thread.Sleep(100);trace.Mark(8);Thread.Sleep(600);}:null};
            });
            string path=mode=="post"?"/probe/generic-event-v7/public/action":"/probe/generic-event-v7/public/decision";
            string reply=Exchange(runtime,port,Head(path,mode=="post"?"choose:0":null,
                mode=="unauthenticated"?new string('c',64):null),drain:mode is "after" or "stages" or "fault");
            if(mode is "before" or "after" or "stages") {
                string code=mode=="before"?"dispatch_timeout_before_claim":"dispatch_timeout_after_claim";
                Check(reply.Contains("\"code\":\""+code+"\"")&&!reply.Contains(Token)&&!reply.Contains("private exception text"),"bounded authenticated read diagnostic: "+mode);
                // The diagnostic is sent before the authenticated cleanup tail publishes terminal.
                Check(SpinWait.SpinUntil(()=>runtime.IsTerminalOrStopping,1000),"diagnostic cleanup publishes terminal");
                using var parsed=JsonDocument.Parse(reply.Split("\r\n\r\n",2)[1]);
                var stages=parsed.RootElement.GetProperty("stages").EnumerateArray().ToArray();
                string active=mode=="before"?"dispatch":mode=="after"?"module_create":"hook_install";
                Check(stages.Count(x=>x.GetProperty("active").GetBoolean())==1&&stages.Single(x=>x.GetProperty("active").GetBoolean()).GetProperty("stage").GetString()==active,"snapshot identifies active initialization stage");
                Check(stages.Length<=15&&stages.All(x=>x.GetProperty("elapsed_ms").GetInt32() is >=0 and <=3000),"timings bounded");
                if(mode=="stages")Check(stages.Single(x=>x.GetProperty("stage").GetString()=="harmony_guard").GetProperty("elapsed_ms").GetInt32()>=50,"completed stage duration retained");
            } else if(mode=="post")Check(reply==""&&runtime.IsTerminalOrStopping,"post timeout remains silent and terminal");
            else if(mode=="unauthenticated")Check(reply==""&&!runtime.IsTerminalOrStopping,"unauthenticated request gets no diagnostic");
            else Check(reply.Contains("bridge_stopped")&&!reply.Contains("private exception text")&&runtime.IsTerminalOrStopping,"router fault remains bounded and terminal");
            if(mode is "before" or "post" or "unauthenticated")Check(created==0,"unclaimed work creates no native module");
            Stop(runtime);
            Check(module is null||module.Disposed,"late module cleaned on owner frame");
        }
        foreach(var status in Enum.GetValues<OwnedByteDispatchStatus>())
            Check(BridgeTransportRuntime.ReadDispatchFailure(status).StartsWith("dispatch_",StringComparison.Ordinal),"closed dispatch vocabulary");
        Check(BridgeTransportRuntime.ReadDispatchFailure((OwnedByteDispatchStatus)999)=="dispatch_invalid_result","unknown dispatch cannot inject text");
    }
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
    private static void StaleRecovery()
    {
        var core = new CoreFixture { Reject = true, CombatReady = true };
        var (runtime, port) = Start((c,_) => new FakeModule(c), core);
        var action = Head("/probe/v0/public/combat-action", "end_turn");
        Check(Exchange(runtime, port, action).Contains("stale_decision") && core.CombatAccepted == 0, "stale response has no accepted mutation");
        Check(Exchange(runtime, port, Head("/probe/v0/public/combat-decision")).Contains(Decision), "fresh ready observation can retain the same identity");
        core.Reject = false;
        Check(Exchange(runtime, port, action).Contains("accepted") && core.CombatAccepted == 1, "known rejected identity can be revalidated and accepted");
        Check(runtime.ReservedParentPosts == 2, "stale attempts still consume the process budget");
        Check(Exchange(runtime, port, action) == "" && core.CombatAccepted == 1 && runtime.IsTerminalOrStopping, "accepted identity cannot execute twice");
        Stop(runtime);

        core = new CoreFixture { Reject = true };
        (runtime, port) = Start((c,_) => new FakeModule(c), core);
        runtime.DropNextPostResponseForTests = true;
        Check(Exchange(runtime, port, action) == "" && core.CombatAccepted == 0 && runtime.IsTerminalOrStopping, "lost stale receipt still stops the host");
        Stop(runtime);
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
        private ReadStageTrace? _trace;
        internal Action<ReadStageTrace?>? ReadWork;
        public void SetReadTrace(ReadStageTrace? trace)=>_trace=trace;
        internal Func<bool>? CombatScope;
        internal Func<string>? CombatResume; internal string? EventNonce;
        public bool Owns(BridgeRequest request) => request.Capability == capability || OwnItems && request.Capability == Capability.Items;
        public ModuleReply Handle(BridgeRequest request)
        {
            Calls++; if (request.IsPost) Posts++;
            else ReadWork?.Invoke(_trace);
            if (AutoComplete && Calls >= 2) Complete = true;
            return new(Encoding.ASCII.GetBytes("{\"status\":\"" + (Complete ? "resolved" : request.IsPost ? "accepted" : "ready") + "\"}"), Complete, Terminal, EventDiagnostic: capability == Capability.Events, CombatScope: CombatScope, CombatResume: CombatResume, EventNonce: EventNonce);
        }
        public void Dispose() { DisposeAttempts++; if (FailDispose) throw new InvalidOperationException(); Disposed = true; }
    }
    private static void RepeatedCombatIdentities()
    {
        var snapshot=new PublicCombatDecisionSnapshot(PublicDecisionStatus.Ready,"",1,new(80,80,0,3),
            new[]{new PublicCombatEnemy(0,"DUMMY",75,75,0,Array.Empty<string>())},
            new[]{new PublicCombatCard(0,"BLUDGEON","attack","3","anyenemy",true)},
            new[]{new PublicDecisionAction(PublicDecisionActionKind.PlayCard,0,0)},PublicCombatOutcome.None);
        string first=PublicCombatDecisionIdentity.Compute(snapshot,new string('a',32));
        string second=PublicCombatDecisionIdentity.Compute(snapshot,new string('b',32));
        Check(first!=second&&PublicCombatDecisionIdentity.IsCanonical(first)&&PublicCombatDecisionIdentity.IsCanonical(second),"scoped identities remain opaque canonical wire values");
        foreach(bool loseReceipt in new[]{false,true}) {
            var fixture=new CoreFixture{CombatOverride=snapshot with {DecisionId=first}};
            var (runtime,port)=Start((c,n)=>new FakeModule(c),fixture);
            Check(Exchange(runtime,port,Head("/probe/v0/public/combat-decision")).Contains(first),"first scoped ready read");
            runtime.DropNextPostResponseForTests=loseReceipt;
            string receipt=Exchange(runtime,port,Head("/probe/v0/public/combat-action","play:0:0",decision:first));
            if(loseReceipt) {
                Check(receipt==""&&runtime.IsTerminalOrStopping&&fixture.CombatAccepted==1,"lost first-combat receipt remains terminal");
                fixture.CombatOverride=snapshot with {DecisionId=second};
                string afterStop="";
                try{afterStop=Exchange(runtime,port,Head("/probe/v0/public/combat-action","play:0:0",decision:second));}catch(SocketException){}
                Check(afterStop==""&&fixture.CombatAccepted==1,"new combat identity cannot bypass a failed runtime");
            } else {
                Check(receipt.Contains("accepted"),"first combat action delivered");
                fixture.CombatOverride=PublicCombatDecisionSnapshot.Complete(3,new(80,80,0,0),Array.Empty<PublicCombatEnemy>(),PublicCombatOutcome.Victory);
                Check(Exchange(runtime,port,Head("/probe/v0/public/combat-decision")).Contains("complete"),"first combat reconciled before next encounter");
                fixture.CombatOverride=snapshot with {DecisionId=second};
                Check(Exchange(runtime,port,Head("/probe/v0/public/combat-decision")).Contains(second),"second identical combat has fresh ready identity");
                Check(Exchange(runtime,port,Head("/probe/v0/public/combat-action","play:0:0",decision:second)).Contains("accepted")&&fixture.CombatAccepted==2,"listener accepts both encounters without clearing reservations");
                Check(runtime.ReservedParentPosts==2,"both combat actions retain process budget accounting");
                Check(Exchange(runtime,port,Head("/probe/v0/public/combat-action","play:0:0",decision:first))==""&&runtime.IsTerminalOrStopping&&fixture.CombatAccepted==2,"old-combat action replay still terminates without dispatch");
            }
            Stop(runtime);
        }
    }
    private sealed class CoreFixture : IPublicScreenService, IPublicCombatDecisionService, IPublicCombatActionService,
        IPublicRewardDecisionService, IPublicRewardActionService, IPublicMapDecisionService, IPublicMapActionService,
        IPublicRoomDecisionService, IPublicRoomActionService
    {
        internal CombatCardChoiceService? Choice; internal bool Scenario; internal int Stage;
        internal bool RewardScenario, RewardWaited, Skipped, SpecialCardScenario, ItemRewardScenario, FullPotionScenario, ReplacePotionScenario, CapacityPotionScenario, HealingRelicScenario; internal int RewardStep;
        internal bool MapComplete, MapReady, Reject, Fault, CombatReady; internal int Applies, CombatAccepted;
        internal PublicCombatDecisionSnapshot? CombatOverride;
        PublicScreenReadResult IPublicScreenService.Read() => PublicScreenReadResult.BackendFault();
        PublicCombatDecisionReadResult IPublicCombatDecisionService.Read() => PublicCombatDecisionReadResult.FromSnapshot(CombatOverride ?? (Scenario ? ScenarioSnapshot() : CombatReady
            ? new(PublicDecisionStatus.Ready, Decision, 1, new(80,80,0,0), new[] { new PublicCombatEnemy(0,"SLIME",8,8,0,Array.Empty<string>()) }, Array.Empty<PublicCombatCard>(), new[] { new PublicDecisionAction(PublicDecisionActionKind.EndTurn,-1,-1) }, PublicCombatOutcome.None)
            : PublicCombatDecisionSnapshot.Waiting()));
        private PublicCombatDecisionSnapshot ScenarioSnapshot() => Stage switch {
            0 => new(PublicDecisionStatus.Ready, Decision, 1, new(80,80,0,1),
                new[] { new PublicCombatEnemy(0,"SLIME",8,8,0,Array.Empty<string>()) },
                new[] { new PublicCombatCard(0,"NEOWS_FURY","attack","1","anyenemy",true) },
                new[] { new PublicDecisionAction(PublicDecisionActionKind.PlayCard,0,0), new PublicDecisionAction(PublicDecisionActionKind.EndTurn,-1,-1) }, PublicCombatOutcome.None),
            2 => new(PublicDecisionStatus.Ready, new string('e',64), 1, new(80,80,0,0),
                new[] { new PublicCombatEnemy(0,"SLIME",1,8,0,Array.Empty<string>()) }, Array.Empty<PublicCombatCard>(),
                new[] { new PublicDecisionAction(PublicDecisionActionKind.EndTurn,-1,-1) }, PublicCombatOutcome.None),
            3 => PublicCombatDecisionSnapshot.Complete(2,new(80,80,0,0),Array.Empty<PublicCombatEnemy>(),PublicCombatOutcome.Victory),
            _ => PublicCombatDecisionSnapshot.Waiting() };
        private PublicRewardDecisionSnapshot RewardSnapshot()
        {
            if (Stage != 3 || !RewardWaited) { RewardWaited = true; return PublicRewardDecisionSnapshot.Waiting(); }
            if(CapacityPotionScenario) {
                var p=new PublicRewardPlayer(80,80,RewardStep==0?99:113,RewardStep>=6&&!Skipped?11:10);
                if(RewardStep==7)return PublicRewardDecisionSnapshot.Complete(p,7);
                var all=new[]{new PublicRewardItem(0,PublicRewardKind.Gold,false,14,Array.Empty<string>(),false),
                    new PublicRewardItem(1,PublicRewardKind.Card,RewardStep==6&&!Skipped,0,new[]{"ANGER","BASH"},true),
                    new PublicRewardItem(2,PublicRewardKind.Potion,false,0,Array.Empty<string>(),false,"POTION"),
                    new PublicRewardItem(3,PublicRewardKind.Potion,false,0,Array.Empty<string>(),false,"POTION"),
                    new PublicRewardItem(4,PublicRewardKind.Relic,false,0,Array.Empty<string>(),false,"POTION_BELT",2)};
                var rows=all.Where(r=>RewardStep==5?r.RewardIndex==1:
                    r.RewardIndex switch {0=>RewardStep==0,1=>true,2=>RewardStep<3,3=>RewardStep<4,_=>RewardStep<2}).ToArray();
                string[] capacityActions=RewardStep switch {
                    0=>new[]{"claim:0","open:1","collect:4","discard:0","discard:1","proceed"},
                    1=>new[]{"open:0","collect:3","discard:0","discard:1","proceed"},
                    2=>new[]{"open:0","collect:1","collect:2","proceed"},
                    3=>new[]{"open:0","collect:1","proceed"},4=>new[]{"open:0","proceed"},
                    5=>new[]{"choose:0","choose:1","skip_card"},_=>new[]{"proceed"}};
                string?[] belt=RewardStep<2?new[]{"OLD_0","OLD_1"}:new[]{"OLD_0","OLD_1",RewardStep>=3?"POTION":null,RewardStep>=4?"POTION":null};
                return new(PublicDecisionStatus.Ready,(RewardStep+10).ToString("x64"),RewardStep==5?"card_reward":"rewards",p,rows,capacityActions,RewardStep,true,belt,true);
            }
            if(ReplacePotionScenario) {
                var p=new PublicRewardPlayer(80,80,RewardStep==0?99:113,RewardStep>=4&&!Skipped?11:10);
                if(RewardStep==9)return PublicRewardDecisionSnapshot.Complete(p,9);
                var all=new[]{new PublicRewardItem(0,PublicRewardKind.Gold,false,14,Array.Empty<string>(),false),
                    new PublicRewardItem(1,PublicRewardKind.Card,false,0,new[]{"ANGER","BASH"},true),
                    new PublicRewardItem(2,PublicRewardKind.Potion,false,0,Array.Empty<string>(),false,"POTION"),
                    new PublicRewardItem(3,PublicRewardKind.Potion,false,0,Array.Empty<string>(),false,"POTION"),
                    new PublicRewardItem(4,PublicRewardKind.Relic,false,0,Array.Empty<string>(),false,"RELIC")};
                var rows=all.Where(r=>RewardStep==3?r.RewardIndex==1:
                    r.RewardIndex switch {0=>RewardStep==0,1=>RewardStep<4,2=>RewardStep<6,3=>RewardStep<8,_=>RewardStep<2}).ToArray();
                string[] replacementActions=RewardStep switch {
                    0=>new[]{"claim:0","open:1","collect:4","discard:0","discard:1","proceed"},
                    1=>new[]{"open:0","collect:3","discard:0","discard:1","proceed"},
                    2=>new[]{"open:0","discard:0","discard:1","proceed"},
                    3=>new[]{"choose:0","choose:1","skip_card"},
                    4=>new[]{"discard:0","discard:1","proceed"},
                    5=>new[]{"collect:0","collect:1","proceed"},
                    6=>new[]{"discard:1","proceed"},7=>new[]{"collect:0","proceed"},_=>new[]{"proceed"}};
                string?[] belt={RewardStep==5?null:RewardStep>=6?"POTION":"OLD_0",RewardStep==7?null:RewardStep>=8?"POTION":"OLD_1"};
                return new(PublicDecisionStatus.Ready,(RewardStep+10).ToString("x64"),RewardStep==3?"card_reward":"rewards",p,rows,replacementActions,RewardStep,true,belt);
            }
            if(FullPotionScenario) {
                var fullPlayer=new PublicRewardPlayer(80,80,RewardStep==0?99:113,RewardStep>=4&&!Skipped?11:10);
                if(RewardStep==5)return PublicRewardDecisionSnapshot.Complete(fullPlayer,5);
                var all=new[]{new PublicRewardItem(0,PublicRewardKind.Gold,false,14,Array.Empty<string>(),false),
                    new PublicRewardItem(1,PublicRewardKind.Card,RewardStep==4&&!Skipped,0,new[]{"ANGER","BASH"},true),
                    new PublicRewardItem(2,PublicRewardKind.Potion,false,0,Array.Empty<string>(),false,"POTION"),
                    new PublicRewardItem(3,PublicRewardKind.Potion,false,0,Array.Empty<string>(),false,"POTION"),
                    new PublicRewardItem(4,PublicRewardKind.Relic,false,0,Array.Empty<string>(),false,"RELIC")};
                var rows=all.Where(r=>RewardStep==3?r.RewardIndex==1:r.RewardIndex is 1 or 2 or 3 || RewardStep==0 || RewardStep==1&&r.RewardIndex==4).ToArray();
                string[] fullActions=RewardStep switch {
                    0=>new[]{"claim:0","open:1","collect:4","proceed"},
                    1=>new[]{"open:0","collect:3","proceed"},2=>new[]{"open:0","proceed"},
                    3=>new[]{"choose:0","choose:1","skip_card"},_=>new[]{"proceed"}};
                return new(PublicDecisionStatus.Ready,(RewardStep+10).ToString("x64"),RewardStep==3?"card_reward":"rewards",fullPlayer,rows,fullActions,RewardStep,true);
            }
            if(ItemRewardScenario) {
                var itemPlayer=new PublicRewardPlayer(HealingRelicScenario?(RewardStep>=4?41:33):80,80,RewardStep==0?99:113,RewardStep>=6&&!Skipped?11:10);
                if(RewardStep==7)return PublicRewardDecisionSnapshot.Complete(itemPlayer,7);
                var all=new[]{new PublicRewardItem(0,PublicRewardKind.Gold,false,14,Array.Empty<string>(),false),
                    new PublicRewardItem(1,PublicRewardKind.Card,RewardStep==6&&!Skipped,0,new[]{"ANGER","BASH"},true),
                    new PublicRewardItem(2,PublicRewardKind.Potion,false,0,Array.Empty<string>(),false,"POTION"),
                    new PublicRewardItem(3,PublicRewardKind.Potion,false,0,Array.Empty<string>(),false,"POTION"),
                    new PublicRewardItem(4,PublicRewardKind.Relic,false,0,Array.Empty<string>(),false,HealingRelicScenario?"FAKE_LEES_WAFFLE":"RELIC",0,HealingRelicScenario?8:0)};
                var rows=all.Where(r=>RewardStep==0 || r.RewardIndex==1 || RewardStep<=r.RewardIndex-1).ToArray();
                string[] itemActions=RewardStep switch {
                    0=>new[]{"claim:0","open:1","collect:2","collect:3","collect:4","proceed"},
                    1=>new[]{"open:0","collect:1","collect:2","collect:3","proceed"},
                    2=>new[]{"open:0","collect:1","collect:2","proceed"},
                    3=>new[]{"open:0","collect:1","proceed"},4=>new[]{"open:0","proceed"},
                    5=>new[]{"choose:0","choose:1","skip_card"},_=>new[]{"proceed"}};
                return new(PublicDecisionStatus.Ready,(RewardStep+10).ToString("x64"),RewardStep==5?"card_reward":"rewards",itemPlayer,rows,itemActions,RewardStep,true,HealingRelicScenario?new string?[]{RewardStep>=2?"POTION":null,RewardStep>=3?"POTION":null,null}:null,HealingRelicScenario,HealingRelicScenario);
            }
            if(SpecialCardScenario) {
                var specialPlayer=new PublicRewardPlayer(80,80,RewardStep==0?99:113,
                    10+(RewardStep>=2?1:0)+(RewardStep>=4&&!Skipped?1:0));
                if(RewardStep==5)return PublicRewardDecisionSnapshot.Complete(specialPlayer,5);
                var ordinary=new PublicRewardItem(1,PublicRewardKind.Card,RewardStep==4&&!Skipped,0,new[]{"ANGER","BASH"},true);
                var special=new PublicRewardItem(4,PublicRewardKind.SpecialCard,RewardStep>=2,0,new[]{"LANTERN_KEY"},false);
                var rows=RewardStep==0?new[]{new PublicRewardItem(0,PublicRewardKind.Gold,false,14,Array.Empty<string>(),false),ordinary,special}:
                    RewardStep==3?new[]{ordinary}:new[]{ordinary,special};
                string[] specialActions=RewardStep switch {
                    0=>new[]{"claim:0","open:1","take:2","proceed"},1=>new[]{"open:0","take:1","proceed"},
                    2=>new[]{"open:0","proceed"},3=>new[]{"choose:0","choose:1","skip_card"},_=>new[]{"proceed"}};
                return new(PublicDecisionStatus.Ready,(RewardStep+10).ToString("x64"),RewardStep==3?"card_reward":"rewards",
                    specialPlayer,rows,specialActions,RewardStep);
            }
            var player = new PublicRewardPlayer(80,80,RewardStep == 0 ? 99 : 113,RewardStep >= 3 && !Skipped ? 11 : 10);
            if (RewardStep == 4) return PublicRewardDecisionSnapshot.Complete(player,4);
            var card = new PublicRewardItem(1,PublicRewardKind.Card,RewardStep == 3 && !Skipped,0,new[] { "ANGER","BASH" },true);
            var rewards = RewardStep == 0 ? new[] { new PublicRewardItem(0,PublicRewardKind.Gold,false,14,Array.Empty<string>(),false),card } : new[] { card };
            string[] actions = RewardStep switch { 0 => new[] { "claim:0","open:1","proceed" }, 1 => new[] { "open:0","proceed" },
                2 => new[] { "choose:0","choose:1","skip_card" }, _ => new[] { "proceed" } };
            return new(PublicDecisionStatus.Ready,(RewardStep+10).ToString("x64"),RewardStep == 2 ? "card_reward" : "rewards",player,rewards,actions,RewardStep);
        }
        PublicRewardDecisionReadResult IPublicRewardDecisionService.Read() => PublicRewardDecisionReadResult.FromSnapshot(RewardScenario ? RewardSnapshot() : PublicRewardDecisionSnapshot.Waiting());
        PublicMapDecisionReadResult IPublicMapDecisionService.Read() => PublicMapDecisionReadResult.FromSnapshot(MapComplete ? PublicMapDecisionSnapshot.Complete(new(0,0,1,"unknown")) : MapReady || RewardScenario && RewardStep == (CapacityPotionScenario?7:ReplacePotionScenario?9:FullPotionScenario?5:ItemRewardScenario?7:SpecialCardScenario?5:4)
            ? new(PublicDecisionStatus.Ready, Decision, "map", null, new[] { new PublicMapCandidate(0,2,3,"monster") }, new[] { "select:0" })
            : PublicMapDecisionSnapshot.Waiting());
        PublicRoomDecisionReadResult IPublicRoomDecisionService.Read() => PublicRoomDecisionReadResult.FromSnapshot(PublicRoomDecisionSnapshot.Waiting());
        PublicCombatActionApplyResult IPublicCombatActionService.Apply(PublicCombatActionRequest r) { if (!Reject) { CombatAccepted++; if (Scenario) Stage++; } return PublicCombatActionApplyResult.FromRequest(Reject ? PublicCombatActionApplyOutcome.StaleDecision : PublicCombatActionApplyOutcome.Accepted,r); }
        PublicRewardActionApplyResult IPublicRewardActionService.Apply(PublicRewardActionRequest r)
        {
            if (RewardScenario)
            {
                var state = RewardSnapshot();
                Check(r.DecisionId == state.DecisionId && state.LegalActions.Contains(r.ActionId), "actual reward codec decision/action binding");
                Skipped = Skipped || r.ActionId == "skip_card";
                RewardStep++;
            }
            return PublicRewardActionApplyResult.FromRequest(Reject ? PublicRewardActionApplyOutcome.StaleDecision : PublicRewardActionApplyOutcome.Accepted,r);
        }
        PublicRoomActionApplyResult IPublicRoomActionService.Apply(PublicRoomActionRequest r) => PublicRoomActionApplyResult.FromRequest(Reject ? PublicRoomActionApplyOutcome.StaleDecision : PublicRoomActionApplyOutcome.Accepted,r);
        PublicMapActionApplyResult IPublicMapActionService.Apply(PublicMapActionRequest r) { Applies++; return Fault ? PublicMapActionApplyResult.BackendFault() : PublicMapActionApplyResult.FromRequest(Reject ? PublicMapActionApplyOutcome.StaleDecision : PublicMapActionApplyOutcome.Accepted,r); }
    }
}
