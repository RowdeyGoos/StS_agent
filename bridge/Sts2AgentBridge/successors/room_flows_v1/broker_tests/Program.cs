using System;
using System.Text.Json;
using System.Threading.Tasks;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.ItemWireV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;
internal static class Program
{
 const string Nonce = "0123456789abcdef0123456789abcdef";
 static int Checks;
 static void Check(bool value) { Checks++; if (!value) throw new InvalidOperationException("Fixture failed: " + Checks); }
 static RoomFlowDispatchReceipt Parent() => new("event", Nonce, new string('a', 64), "choose:0");
 static JsonElement Parse(byte[] body) { try { using var doc = JsonDocument.Parse(body); return doc.RootElement.Clone(); } finally { Array.Clear(body); } }
 static JsonElement Get(IEventItemChildBroker b) => Parse(b.Handle("GET", ItemWireV1Protocol.DecisionRoute, null, null));
 static JsonElement Post(IEventItemChildBroker b, JsonElement r) => Parse(b.Handle("POST", ItemWireV1Protocol.ActionRoute, r.GetProperty("decision_id").GetString(), "collect:0"));
 static string Status(JsonElement v) => v.GetProperty("status").GetString()!;
 public static int Main()
 {
  try
  {
   Check(!RoomFlowIdentity.IsRenderedText(""));
   Check(RoomFlowIdentity.IsRenderedText("[b]Hello[/b]\n\u4e16\u754c\ud83d\ude00"));
   Check(!RoomFlowIdentity.IsRenderedText("\ud800"));
   Check(!RoomFlowIdentity.IsRenderedText("a\u0085b"));
   Check(RoomFlowIdentity.IsRenderedText(new string('x', 1024)));
   Check(!RoomFlowIdentity.IsRenderedText(new string('x', 1025)));
   Check(!RoomFlowIdentity.IsRenderedText(new string('\u00e9', 513)));
   foreach (string action in new[] { "choose:00", "choose:8", "choose:-1", "leave", "choose:0\n" })
   { bool threw = false; try { _ = new RoomFlowDispatchReceipt("event", Nonce, new string('a',64), action); } catch (ArgumentException) { threw=true; } Check(threw); }
   foreach (ItemV1ItemKind kind in new[] { ItemV1ItemKind.Relic, ItemV1ItemKind.Potion })
   {
    var n = new Fake { Kind=kind }; var p=Parent(); using var b=new FrozenEventItemChildBroker(p,n);
    Check(ReferenceEquals(p,b.ParentReceipt) && ReferenceEquals(p,b.Status.ParentReceipt) && n.Reads==0);
    var r=Get(b); Check(Status(r)=="ready"); Check(Status(Post(b,r))=="accepted");
    Check(n.Dispatches==1 && b.Status is EventItemChildActive);
    Check(Status(Get(b))=="waiting"); n.Resolved=true; Check(Status(Get(b))=="resolved");
    EventItemChildStatus resolved=b.Status; int reads=n.Reads;
    Check(resolved is EventItemChildResolved && ReferenceEquals(p,resolved.ParentReceipt));
    Check(Status(Post(b,r))=="error"); _=Task.Run(()=>Get(b)).GetAwaiter().GetResult(); b.Dispose();
    Check(ReferenceEquals(b.Status,resolved) && n.Dispatches==1 && n.Reads==reads);
   }
   {
    var n=new Fake(); using var b=new FrozenEventItemChildBroker(Parent(),n);
    byte[] a=b.Handle("GET",ItemWireV1Protocol.DecisionRoute,null,null), c=b.Handle("GET",ItemWireV1Protocol.DecisionRoute,null,null);
    Check(!ReferenceEquals(a,c) && a.AsSpan().SequenceEqual(c)); Array.Clear(a); Check(Status(Parse(c))=="ready");
    var direct=new ItemWireV1Service(Nonce,new Fake()); byte[] expected=direct.Handle("GET",ItemWireV1Protocol.DecisionRoute,null,null);
    byte[] actual=b.Handle("GET",ItemWireV1Protocol.DecisionRoute,null,null);
    Check(actual.AsSpan().SequenceEqual(expected)); Array.Clear(actual); Array.Clear(expected);
   }
   foreach (string mode in new[] {"unsupported","throw","replace","reenter_capture","reenter_dispatch","dispose_dispatch"})
   {
    var n=new Fake(); using var b=new FrozenEventItemChildBroker(Parent(),n); var r=Get(b);
    if(mode=="unsupported")n.Unsupported=true;
    if(mode=="throw")n.Throw=true;
    if(mode=="replace")n.Screen=new object();
    if(mode=="reenter_capture")n.OnCapture=()=>{_=Get(b);};
    if(mode=="reenter_dispatch")n.OnDispatch=()=>{_=Get(b);};
    if(mode=="dispose_dispatch")n.OnDispatch=b.Dispose;
    _=Post(b,r); Check(b.Status is EventItemChildFailed);
    if(mode is "throw" or "reenter_capture" or "reenter_dispatch" or "dispose_dispatch")
     Check(((EventItemChildFailed)b.Status).Failure.Outcome=="uncertain");
    int reads=n.Reads, dispatches=n.Dispatches; EventItemChildStatus failure=b.Status;
    _=Get(b); _=Post(b,r); Check(n.Reads==reads && n.Dispatches==dispatches && ReferenceEquals(failure,b.Status));
    Check(dispatches==(mode is "throw" or "reenter_dispatch" or "dispose_dispatch"?1:0));
   }
   {
    var n=new Fake(); using var b=new FrozenEventItemChildBroker(Parent(),n);
    _=Post(b,Get(b)); n.OnPending=()=>{_=Get(b);};
    Check(Status(Get(b))=="error"); Check(b.Status is EventItemChildFailed && n.Dispatches==1);
    int reads=n.Reads; _=Get(b); Check(n.Reads==reads);
   }
   {
    var n=new Fake(); using var b=new FrozenEventItemChildBroker(Parent(),n);
    _=Parse(b.Handle("POST",ItemWireV1Protocol.ActionRoute,new string('a',64),"collect:0"));
    Check(b.Status is EventItemChildFailed && n.Reads==0);
   }
   {
    var n=new Fake(); using var b=new FrozenEventItemChildBroker(Parent(),n);
    _=Task.Run(()=>Get(b)).GetAwaiter().GetResult(); Check(b.Status is EventItemChildFailed && n.Reads==0);
   }
   {
    var f=new FrozenEventItemChildFactory(); using var first=f.Create(Parent(),new Fake()); bool threw=false;
    try{_=f.Create(Parent(),new Fake());}catch(InvalidOperationException){threw=true;} Check(threw);
   }
   foreach(bool resolve in new[]{true,false})
   {
    var n=new Fake(); using var b=new FrozenEventItemChildBroker(Parent(),n); _=Post(b,Get(b));
    for(int i=0;i<255;i++)Check(Status(Get(b))=="waiting");
    n.Resolved=resolve; Check(Status(Get(b))==(resolve?"resolved":"unsupported"));
    Check(n.PendingReads==256 && n.Dispatches==1);
   }
   Console.WriteLine("room_flows_broker_checks="+Checks);return 0;
  }
  catch(Exception e){Console.Error.WriteLine(e.Message);return 1;}
 }
 sealed class Fake:IItemV1NativeAdapter
 {
  readonly object Run=new(),Player=new(),Reward=new(),Model=new(),Button=new();
  public object Screen=new(); public ItemV1ItemKind Kind=ItemV1ItemKind.Relic;
  public bool Resolved,Unsupported,Throw; public Action? OnCapture,OnDispatch,OnPending;public int Reads,PendingReads,Dispatches;
  public ItemV1SurfaceCapture CaptureSurface()
  {
   Reads++;OnCapture?.Invoke();if(Unsupported)return ItemV1SurfaceCapture.Unsupported();
   return ItemV1SurfaceCapture.Available(Run,Player,Screen,1,
    new[]{new ItemV1NativeOffer(0,Kind,"FIXTURE_ITEM",true,false,true,true,Button,Reward,Model,
     ()=>{Dispatches++;OnDispatch?.Invoke();if(Throw)throw new Exception("private fixture detail");})},
    new[]{new ItemV1PotionSlotBinding(null,null)});
  }
  public ItemV1PendingCapture CapturePending(ItemV1PendingProbe pending)
  {
   Reads++;PendingReads++;OnPending?.Invoke();
   return new ItemV1PendingCapture(Run,Player,Reward,Model,"FIXTURE_ITEM",Resolved,
    Resolved?Model:null,Resolved?"FIXTURE_ITEM":null,1,
    new[]{new ItemV1PotionSlotBinding(Resolved&&Kind==ItemV1ItemKind.Potion?Model:null,Resolved&&Kind==ItemV1ItemKind.Potion?"FIXTURE_ITEM":null)});
  }
 }
}
