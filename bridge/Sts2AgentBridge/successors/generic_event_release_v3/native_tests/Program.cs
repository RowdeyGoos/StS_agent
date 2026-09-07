using System;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Text;
using System.Threading.Tasks;
using HarmonyLib;
using Sts2AgentBridge.Successors.GenericEventV3;
using Sts2AgentBridge.Successors.GenericEventV3.Native;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV3;
internal static class ReleaseNativeTests
{
    private static int _checks;
    private static void Check(bool value) { _checks++; if (!value) throw new InvalidOperationException("native assertion " + _checks); }
    private static byte[] Configuration() => Encoding.UTF8.GetBytes("{\"schema_version\":\"generic_event_v3_transport_config_v1\",\"enabled\":true,\"flow_kind\":\"generic\",\"bind_address\":\"127.0.0.1\",\"port\":43117,\"token_file\":\"credential.hex\"}");
    private static byte[] Credential() => Encoding.ASCII.GetBytes(new string('a',64));
    internal static int Main()
    {
        try
        {
            BindingPolicy(); FactoryDefaultDeny(); RetainedFailedConstruction(); SessionConstructionCleanup(); FactoryDiagnosticOwnership(); CompetingRegistry();
            Console.WriteLine("{\"status\":\"passed\",\"suite\":\"generic_event_v3_native_release\",\"check_count\":" + _checks + "}"); return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
    private static void BindingPolicy()
    {
        var context = new object();
        bool Valid(string path, string identity, string mvid, object? actual, object? game, bool collectible=false) =>
            PinnedGenericEventHarmonyGuard.ValidBinding(path,identity,mvid,actual,game,collectible);
        string path=PinnedGenericEventHarmonyGuard.ExpectedPath, identity=PinnedGenericEventHarmonyGuard.ExpectedIdentity, mvid=PinnedGenericEventHarmonyGuard.ExpectedMvid;
        Check(Valid(path,identity,mvid,context,context));
        Check(!Valid(path+".other",identity,mvid,context,context));
        Check(!Valid(path,identity+" ",mvid,context,context));
        Check(!Valid(path,identity,Guid.Empty.ToString("D"),context,context));
        Check(!Valid(path,identity,mvid,null,null));
        Check(!Valid(path,identity,mvid,context,new object()));
        Check(!Valid(path,identity,mvid,context,context,true));
        // The isolated fixture uses the pinned game Harmony copy with target stubs.
        // Its copied location must still fail the production installation guard.
        Check(typeof(Harmony).Assembly.ManifestModule.ModuleVersionId.ToString("D") == mvid);
        Check(!PinnedGenericEventHarmonyGuard.Verify());
    }
    private static void FactoryDefaultDeny()
    {
        var factory=new ProductionGenericEventRuntimeFactory();
        byte[] config=Encoding.ASCII.GetBytes("{}"), credential=Credential();
        Check(factory.Create(config,credential) is null); Check(config.All(x=>x==0) && credential.All(x=>x==0));
        config=Configuration();credential=Credential();
        Check(factory.Create(config,credential) is null);Check(config.All(x=>x==0) && credential.All(x=>x==0));
        using var hooks=new GenericEventV3Hooks();
    }
    private static GenericEventV3WireService InvokeVerified(string nonce,object? owner=null)
    {
        try { return (GenericEventV3WireService)typeof(ProductionGenericEventRuntimeFactory).GetMethod("CreateVerifiedService",BindingFlags.NonPublic|BindingFlags.Static)!.Invoke(null,new object[]{nonce,owner??Activator.CreateInstance(typeof(ProductionGenericEventRuntimeFactory).GetNestedType("Runtime",BindingFlags.NonPublic)!,true)!})!; }
        catch(TargetInvocationException error) { throw error.InnerException!; }
    }
    private static void RetainedFailedConstruction()
    {
        bool rejectCleanup=true;int cleanupCalls=0;bool failed=false;
        try { _=new GenericEventV3Hooks(_=>throw new InvalidOperationException(),()=> {cleanupCalls++;if(rejectCleanup)throw new InvalidOperationException();}); }
        catch(AggregateException) { failed=true; }
        Check(failed && cleanupCalls==1);
        byte[] config=Configuration(),credential=Credential();
        GenericEventTransportRuntime? runtime=GenericEventTransportRuntime.Create(config,()=>credential,(_,nonce)=>InvokeVerified(nonce));
        Check(runtime is not null);Check(!runtime!.Start());Check(runtime.StopTransportAndJoin());
        Check(!runtime.DisposeServiceOnOwnerFrame() && !runtime.ServiceDisposed);
        int before=cleanupCalls;
        Check(!Task.Run(runtime.DisposeServiceOnOwnerFrame).GetAwaiter().GetResult());Check(cleanupCalls==before);
        rejectCleanup=false;Check(runtime.DisposeServiceOnOwnerFrame() && runtime.ServiceDisposed);
        Check(runtime.DisposeServiceOnOwnerFrame());
        using var hooks=new GenericEventV3Hooks();
    }
    private static void SessionConstructionCleanup()
    {
        GenericEventTransportFactoryFailure? retained=null;
        try { _=InvokeVerified("invalid"); }
        catch(GenericEventTransportFactoryFailure failure) { retained=failure; }
        Check(retained is not null);retained!.OwnerFrameCleanup();retained.OwnerFrameCleanup();
        using var hooks=new GenericEventV3Hooks();
    }
    private static void FactoryDiagnosticOwnership()
    {
        Type ownerType=typeof(ProductionGenericEventRuntimeFactory).GetNestedType("Runtime",BindingFlags.NonPublic)!;
        object owner=Activator.CreateInstance(ownerType,true)!;
        var read=(Func<GenericEventDiagnosticCode>)ownerType.GetMethod("ReadDiagnostic",BindingFlags.Instance|BindingFlags.NonPublic)!.CreateDelegate(typeof(Func<GenericEventDiagnosticCode>),owner);
        Check(read()==GenericEventDiagnosticCode.NotCaptured);
        var runtime=GenericEventTransportRuntime.Create(Configuration(),Credential,(_,nonce)=>InvokeVerified(nonce,owner),read)!;
        ownerType.GetMethod("Set",BindingFlags.Instance|BindingFlags.NonPublic)!.Invoke(owner,new object[]{runtime});
        var wrapper=(IGenericEventBootstrapRuntime)owner;
        var target=(PinnedGenericEventV3NativeAdapter)ownerType.GetField("_diagnosticTarget",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(owner)!;
        Check(target is not null && read()==GenericEventDiagnosticCode.NotCaptured);
        target!.Capture();Check(read()==GenericEventDiagnosticCode.ParentUnavailable);
        bool duplicate=false;
        try{ownerType.GetMethod("BindDiagnostic",BindingFlags.Instance|BindingFlags.NonPublic)!.Invoke(owner,new object[]{target});}
        catch(TargetInvocationException e)when(e.InnerException is InvalidOperationException){duplicate=true;}
        Check(duplicate);
        var original=typeof(MegaCrit.Sts2.Core.Events.EventOption).GetMethod("Chosen")!;
        var prefix=typeof(GenericEventV3Hooks).GetMethod("ChosenPrefix",BindingFlags.Static|BindingFlags.NonPublic)!;
        var foreign=new Harmony("diagnostic_fixture_foreign");foreign.Patch(original,new HarmonyMethod(prefix));
        Check(wrapper.StopTransportAndJoin());
        Check(!wrapper.DisposeServiceOnOwnerFrame()&&!wrapper.ServiceDisposed);
        Check(ReferenceEquals(ownerType.GetField("_diagnosticTarget",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(owner),target));
        Check(read()==GenericEventDiagnosticCode.ParentUnavailable);
        foreign.Unpatch(original,prefix);
        Check(wrapper.DisposeServiceOnOwnerFrame()&&wrapper.ServiceDisposed);
        Check(read()==GenericEventDiagnosticCode.NotCaptured && ownerType.GetField("_diagnosticTarget",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(owner) is null);
    }
    private static void CompetingRegistry()
    {
        Assembly actual=typeof(Harmony).Assembly;
        Check(PinnedGenericEventHarmonyGuard.ExclusiveBinding(actual,new[]{actual,typeof(ReleaseNativeTests).Assembly}));
        Check(!PinnedGenericEventHarmonyGuard.ExclusiveBinding(actual,Array.Empty<Assembly>()));
        Check(!PinnedGenericEventHarmonyGuard.ExclusiveBinding(actual,new[]{actual,actual}));
        Check(!PinnedGenericEventHarmonyGuard.ExclusiveBinding(actual,Enumerable.Repeat(actual,1025).ToArray()));
        Assembly competitor=AssemblyBuilder.DefineDynamicAssembly(new AssemblyName("0Harmony"),AssemblyBuilderAccess.RunAndCollect);
        Check(!PinnedGenericEventHarmonyGuard.ExclusiveBinding(actual,new[]{actual,competitor}));
    }
}
