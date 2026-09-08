using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using Sts2AgentBridge.Successors.ItemV1;
using Sts2AgentBridge.Successors.GenericEventV7;
internal static class Program {
    private const string Nonce="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private static int _checks;
    private static void Check(bool value,string name) { _checks++; if(!value) throw new Exception(name); }
    private static string Status(IItemV1ReadValue value) => value is ItemV1ResolvedResult ? "resolved" : ((ItemV1Observation)value).Status;
    private static GenericEventV7ItemChildSession Start(Fixture fixture) {
        var session=new GenericEventV7ItemChildSession(Nonce,fixture);
        var ready=(ItemV1Observation)session.Read();
        Check(ready.Status=="ready" && ready.Offers.Count==1,"singleton ready");
        Check(session.Apply(ready.DecisionId,ready.LegalActions[0]) is ItemV1DispatchReceipt,"accepted");
        return session;
    }
    private static void Main() {
        foreach (bool potion in new[]{false,true}) {
            using var f=new Fixture(potion); using var s=Start(f);
            Check(Status(s.Read())=="resolved","success");
            int pending=f.PendingCalls,completion=f.CompletionCalls;
            for(int i=0;i<3;i++) Check(Status(s.Read())=="resolved","terminal stable");
            Check(f.PendingCalls==pending && f.CompletionCalls==completion && f.Dispatches==1,"terminal no sampling");
            Check(s.Apply("x","collect:7") is ItemV1ApplyFailure,"terminal no apply");
        }
        foreach(int localAt in new[]{1,255,256}) {
            using var f=new Fixture(false){LocalAt=localAt,CompletionAt=256}; using var s=Start(f);
            for(int read=1;read<=256;read++) Check(Status(s.Read())==(read==256?"resolved":"waiting"),"same budget completion256");
            Check(f.CompletionCalls==256 && f.PendingCalls==localAt,"cache only local result");
        }
        foreach(int localAt in new[]{1,256,257}) {
            using var f=new Fixture(false){LocalAt=localAt,CompletionAt=257}; using var s=Start(f);
            for(int read=1;read<=256;read++) Check(Status(s.Read())==(read==256?"unsupported":"waiting"),"pending boundary256");
            for(int i=0;i<3;i++) Check(Status(s.Read())=="unsupported","latched budget");
            Check(f.CompletionCalls==256 && f.PendingCalls==Math.Min(localAt,256),"no257 native sample");
        }
        foreach(bool potion in new[]{false,true}) {
            using var f=new Fixture(potion){CompletionAt=4}; using var s=Start(f);
            Check(Status(s.Read())=="waiting","locally resolved withheld");
            f.BadEffect=true;
            Check(Status(s.Read())=="unsupported" && f.CompletionCalls==2,"fresh late effect validation");
        }
        for(int role=0;role<3;role++) foreach(string mutation in new[]{"missing","identity","fault","cancel","terminal_change","ownership","unknown"}) {
            using var f=new Fixture(false){CompletionAt=10}; using var s=Start(f);
            int capturedRole=role;
            f.Override=(r,c)=> r==1 ? f.Replace(c,capturedRole,new(f.Tasks[capturedRole],GenericEventV7ItemTaskState.Succeeded)) :
                mutation=="ownership" ? c with{OwnershipValid=false} :
                f.Replace(c,capturedRole,mutation switch {
                    "missing"=>null, "identity"=>new(new EqualIdentity(),GenericEventV7ItemTaskState.Pending),
                    "fault"=>new(f.Tasks[capturedRole],GenericEventV7ItemTaskState.Faulted),
                    "cancel"=>new(f.Tasks[capturedRole],GenericEventV7ItemTaskState.Canceled),
                    "unknown"=>new(f.Tasks[capturedRole],(GenericEventV7ItemTaskState)99),
                    _=>new(f.Tasks[capturedRole],GenericEventV7ItemTaskState.Pending)});
            Check(Status(s.Read())=="waiting","first role observed");
            Check(Status(s.Read())=="unsupported","bad task witness");
        }
        using(var f=new Fixture(false){CompletionAt=3}) using(var s=Start(f)) {
            f.Override=(r,c)=>r<3 ? c with{Collection=null,Offer=null,Chosen=null} : c;
            Check(Status(s.Read())=="waiting" && Status(s.Read())=="waiting" && Status(s.Read())=="resolved","missing then synchronous all completed");
        }
        foreach(string bad in new[]{"model","key","slot","run"}) {
            using var f=new Fixture(true){BadPending=bad}; using var s=Start(f);
            Check(Status(s.Read())=="unsupported" && f.CompletionCalls==1,"actual frozen pending predicate");
        }
        using(var f=new Fixture(true){Full=true}) using(var s=new GenericEventV7ItemChildSession(Nonce,f))
            Check(Status(s.Read())=="unsupported","full potion belt cannot act");
        using(var f=new Fixture(false){Extra=true}) using(var s=new GenericEventV7ItemChildSession(Nonce,f))
            Check(Status(s.Read())=="unsupported","whole domain singleton");
        using(var f=new Fixture(false){ThrowDispatch=true}) using(var s=new GenericEventV7ItemChildSession(Nonce,f)) {
            var r=(ItemV1Observation)s.Read();
            Check(s.Apply(r.DecisionId,"collect:7") is ItemV1ApplyFailure {Outcome:"uncertain"},"uncertain dispatch");
            s.Apply(r.DecisionId,"collect:7"); Check(f.Dispatches==1 && Status(s.Read())=="unsupported","no retry");
        }
        using(var f=new Fixture(false){FailCleanup=true}) {
            var s=Start(f); bool threw=false; try{s.Dispose();}catch{threw=true;}
            Check(threw && f.DisposeCalls==1,"cleanup retains failure");
            s.Dispose();s.Dispose(); Check(f.DisposeCalls==2 && Status(s.Read())=="unsupported","cleanup retry once");
        }
        using(var f=new Fixture(false)) using(var s=Start(f)) {
            var thread=new Thread(()=>Check(Status(s.Read())=="unsupported","wrong thread"));thread.Start();thread.Join();
            Check(f.CompletionCalls==0 && Status(s.Read())=="unsupported","wrong thread no native");
        }
        using(var f=new Fixture(false)) using(var s=Start(f)) {
            f.Override=(r,c)=>{s.Read();return c;};
            Check(Status(s.Read())=="unsupported" && f.Dispatches==1,"reentrant capture latches");
        }
        using(var f=new Fixture(false)) {
            var s=Start(f);f.OnDispose=()=>s.Dispose();bool threw=false;
            try{s.Dispose();}catch{threw=true;}
            Check(threw && f.DisposeCalls==1,"nested cleanup no recursive native call");
            f.OnDispose=null;s.Dispose();Check(f.DisposeCalls==2,"external cleanup retry");
        }
        foreach(bool failParent in new[]{false,true}) {
            using var native=new Parent{FailParent=failParent}; using var s=new GenericEventV7Session(native,Nonce);
            var p=s.Read();s.Apply(p.DecisionId,"choose:0");var child=s.Read().Child!;
            var item=(ItemV1Observation)((GenericEventV7ItemRead)s.ReadChild(child.ParentDecisionId,child.ParentActionId,1)).Value;
            s.ApplyChild(child.ParentDecisionId,child.ParentActionId,1,item.DecisionId,"collect:7");
            Check(s.Read().CompletedItemChildren==0,"snapshot before resolution");
            for(int n=0;n<3;n++)Check(((GenericEventV7ItemRead)s.ReadChild(child.ParentDecisionId,child.ParentActionId,1)).Value is ItemV1ResolvedResult,"core terminal repeat");
            var next=s.Read();
            Check(next.CompletedItemChildren==1 && next.CompletedCardChildren==0 && next.ChildReconciled==1,"exact cumulative item credit");
            Check(next.Status==(failParent?"unsupported":"ready") && next.PriorResults.Count==(failParent?0:1),"parent gate history");
            if(!failParent){s.Apply(next.DecisionId,"choose:0");var end=s.Read();Check(end.Status=="complete"&&end.CompletedItemChildren==1&&end.Effects=="unverified","Proceed preserves completion");}
        }
        Console.WriteLine($"Item consumer assertions passed: {_checks}");
    }
    private sealed class EqualIdentity { public override bool Equals(object? o)=>o is EqualIdentity; public override int GetHashCode()=>1; }
    private sealed class Fixture : IGenericEventV7ItemNativeAdapter {
        private readonly bool _potion;
        internal readonly object Run=new(),Player=new(),Screen=new(),Model=new(),Reward=new(),Button=new(),Existing=new();
        internal readonly object[] Tasks={new EqualIdentity(),new EqualIdentity(),new EqualIdentity()};
        internal int Dispatches,PendingCalls,CompletionCalls,DisposeCalls,LocalAt=1,CompletionAt=1;
        internal bool BadEffect,Full,Extra,ThrowDispatch,FailCleanup;
        internal string? BadPending;
        internal Action? OnDispose;
        internal Func<int,GenericEventV7ItemCompletion,GenericEventV7ItemCompletion>? Override;
        internal Fixture(bool potion)=>_potion=potion;
        public ItemV1SurfaceCapture CaptureSurface() {
            var offer=new ItemV1NativeOffer(7,_potion?ItemV1ItemKind.Potion:ItemV1ItemKind.Relic,"ITEM",true,false,true,true,Button,Reward,Model,
                ()=>{Dispatches++;if(ThrowDispatch)throw new Exception();});
            return ItemV1SurfaceCapture.Available(Run,Player,Screen,2,Extra?new[]{offer,offer}:new[]{offer},Slots(false));
        }
        private ItemV1PotionSlotBinding[] Slots(bool claimed)=>new[]{new ItemV1PotionSlotBinding(Existing,"BASE"),
            new ItemV1PotionSlotBinding(Full?Existing:claimed?Model:null,Full?"BASE":claimed?"ITEM":null)};
        public ItemV1PendingCapture CapturePending(ItemV1PendingProbe probe) {
            PendingCalls++;bool done=PendingCalls>=LocalAt;
            var slots=Slots(done&&_potion);
            if(BadPending=="slot")slots[0]=new(new object(),"BASE");
            return new(BadPending=="run"?new object():Run,Player,Reward,Model,"ITEM",done,
                done?(BadPending=="model"?new object():Model):null,done?(BadPending=="key"?"OTHER":"ITEM"):null,2,slots);
        }
        public GenericEventV7ItemCompletion CaptureCompletion() {
            CompletionCalls++;var state=CompletionCalls>=CompletionAt?GenericEventV7ItemTaskState.Succeeded:GenericEventV7ItemTaskState.Pending;
            var c=new GenericEventV7ItemCompletion(true,!BadEffect,CompletionCalls>=CompletionAt,new(Tasks[0],state),new(Tasks[1],state),new(Tasks[2],state));
            return Override?.Invoke(CompletionCalls,c)??c;
        }
        internal GenericEventV7ItemCompletion Replace(GenericEventV7ItemCompletion c,int index,GenericEventV7ItemTaskWitness? t)=>index switch{0=>c with{Collection=t},1=>c with{Offer=t},_=>c with{Chosen=t}};
        public void Dispose(){DisposeCalls++;OnDispose?.Invoke();if(FailCleanup&&DisposeCalls==1)throw new Exception();}
    }
    private sealed class Parent : IGenericEventV7NativeAdapter {
        private readonly object _option=new(),_admission=new(),_screen=new();
        private readonly Fixture _item=new(false);private bool _chosen,_done,_map;
        internal bool FailParent;
        public GenericEventV7NativeCapture Capture()=>_map?new("map",true,Array.Empty<GenericEventV7NativeOption>()):
            _chosen&&!_done?new("child",false,Array.Empty<GenericEventV7NativeOption>(),_screen,new GenericEventV7ItemAdmission(_admission,1)):
            new("parent",_done,new[]{new GenericEventV7NativeOption(_option,_done?"PROCEED":"ITEM","Choice",true,false,_done)});
        public void Dispatch(object identity,string nonce,string decision,string action){if(_done)_map=true;else _chosen=true;}
        public IGenericEventV7ChildSession CreateChild(object identity)=>new GenericEventV7ItemChildSession(Nonce,_item);
        public void CompleteParent(){if(FailParent)throw new Exception();_done=true;}
        public void Dispose(){}
    }
}
