using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.GenericEventV3.Native;

internal static class CandidateProgram
{
    private static int _checks;
    private static void Check(bool value,string message){_checks++;if(!value)throw new InvalidOperationException(message);}
    private sealed class HiddenCard:NCard { }
    private sealed class HiddenHitbox:NClickableControl { }
    private sealed class HiddenHighlight:NCardHighlight { }
    private sealed class HiddenMaterial:ShaderMaterial { }
    private sealed class HiddenHolder:NGridCardHolder { }
    private sealed class TrackedList<T>:IReadOnlyList<T>
    {
        internal readonly List<T> Values;
        private readonly string _name;
        internal TrackedList(string name,IEnumerable<T> values){_name=name;Values=values.ToList();}
        public int Count=>FixtureTrace.Read(this,"count",Values.Count);
        public T this[int index]{get{FixtureTrace.Record(_name+".index");return Values[index];}}
        public IEnumerator<T> GetEnumerator(){FixtureTrace.Record(_name+".enumerate");foreach(T value in Values){FixtureTrace.Record(_name+".next");yield return value;}FixtureTrace.Record(_name+".end");}
        IEnumerator IEnumerable.GetEnumerator()=>GetEnumerator();
    }
    private sealed class Input
    {
        internal readonly TrackedList<NGridCardHolder> Holders;
        internal readonly TrackedList<CardModel> Expected;
        internal Input(int count=3)
        {
            FixtureTrace.Reset();
            var models=Enumerable.Range(0,count).Select(i=>{var m=new CardModel();m.Id.Entry="CARD_"+i;return m;}).ToArray();
            Expected=new("expected",models);
            Holders=new("holders",models.Select(m=>new NGridCardHolder {CardModel=m,CardNode=new NCard {Model=m,CardHighlight=new NCardHighlight {Material=new ShaderMaterial()}},Hitbox=new NClickableControl(),Selected=()=>FixtureTrace.Record("dispatch")}));
        }
        internal NGridCardHolder H(int i=0)=>Holders.Values[i];
        internal CardModel M(int i=0)=>Expected.Values[i];
        internal ShaderMaterial Material(int i=0)=>(ShaderMaterial)H(i).CardNode.CardHighlight.Material!;
        internal void Label()
        {
            FixtureTrace.Labels[Holders]="holders";FixtureTrace.Labels[Expected]="expected";
            for(int i=0;i<Holders.Values.Count;i++)
            {
                var h=H(i);FixtureTrace.Labels[h]="h"+i;
                if(h.CardNode is {} c){FixtureTrace.Labels[c]="c"+i;if(c.CardHighlight is {} hi){FixtureTrace.Labels[hi]="hi"+i;if(hi.Material is {} mat)FixtureTrace.Labels[mat]="mat"+i;}}
                if(h.Hitbox is {} hit)FixtureTrace.Labels[hit]="hit"+i;
            }
            for(int i=0;i<Expected.Values.Count;i++)if(Expected.Values[i] is {} m){FixtureTrace.Labels[m]="m"+i;FixtureTrace.Labels[m.Id]="id"+i;}
        }
    }
    private sealed record Projection(bool Success,string? Exception,string[] Operations,string[] Candidates,int Diagnostic);
    private static Projection Bind(Input input)
    {
        input.Label();FixtureTrace.Enabled=true;
        MethodInfo method=typeof(GenericEventV3RewardAdapter).GetMethod("TryCreateBindings",BindingFlags.Static|BindingFlags.NonPublic)!;
        object?[] args=method.GetParameters().Length==4?new object?[]{input.Holders,input.Expected,null,null}:new object?[]{input.Holders,input.Expected,null,null,null};
        bool success=false;string? exception=null;
        try{success=(bool)method.Invoke(null,args)!;}catch(TargetInvocationException e){exception=e.InnerException!.GetType().Name;}
        finally{FixtureTrace.Enabled=false;}
        var candidates=(CardSelectionV1NativeCandidate[]?)args[3]??Array.Empty<CardSelectionV1NativeCandidate>();
        return new(success,exception,FixtureTrace.Operations.ToArray(),candidates.Select(c=>c is null?"null":$"{c.Slot}:{FixtureTrace.Labels[c.ModelIdentity]}:{c.StableKey}:{c.UpgradeLevel}:{c.Visible}:{c.Enabled}:{c.Selected}:{c.SelectionSettled}").ToArray(),args.Length==5&&args[4] is not null?Convert.ToInt32(args[4]):-1);
    }
    private static Input Case(int code)
    {
        var x=new Input(code==58?1:3);var h=x.H();var c=h.CardNode;var hi=c.CardHighlight;var mat=x.Material();
        switch(code)
        {
            case 37:x.Expected.Values[0]=null!;break;
            case 38:x.Expected.Values.Add(x.M());break;
            case 39:h.CardModel=null!;break;
            case 40:h.CardModel=new CardModel();break;
            case 41:x.H(1).CardModel=x.M();break;
            case 42:FixtureTrace.Scripts["h0.model"]=(n,v)=>n==2?null:v;break;
            case 43:h.CardNode=null!;break;
            case 44:h.Hitbox=null!;break;
            case 45:c.CardHighlight=null!;break;
            case 46:h.CardNode=new HiddenCard {Model=c.Model,CardHighlight=hi};break;
            case 47:c.InstanceValid=false;break;
            case 48:h.Hitbox=new HiddenHitbox();break;
            case 49:h.Hitbox.InstanceValid=false;break;
            case 50:c.CardHighlight=new HiddenHighlight {Material=mat};break;
            case 51:hi.InstanceValid=false;break;
            case 52:hi.Material=null;break;
            case 53:hi.Material=new object();break;
            case 54:hi.Material=new HiddenMaterial();break;
            case 55:mat.InstanceValid=false;break;
            case 56:x.M().Id.Entry="bad key";break;
            case 57:var extra=new CardModel();extra.Id.Entry="EXTRA";x.Expected.Values.Add(extra);break;
            case 58:break;
            case 59:FixtureTrace.Scripts["holders.count"]=(n,v)=>n==5?2:v;break;
            case 60:FixtureTrace.Scripts["holders.count"]=(n,v)=>{if(n==5)x.Holders.Values[0]=new NGridCardHolder();return v;};break;
            case 61:x.Holders.Values[0]=new HiddenHolder {CardModel=h.CardModel,CardNode=c,Hitbox=h.Hitbox};break;
            case 62:h.InstanceValid=false;break;
            case 63:FixtureTrace.Scripts["h0.model"]=(n,v)=>n==3?new CardModel():v;break;
            case 64:FixtureTrace.Scripts["h0.card"]=(n,v)=>n==2?new NCard():v;break;
            case 65:FixtureTrace.Scripts["h0.hitbox"]=(n,v)=>n==2?new NClickableControl():v;break;
            case 66:FixtureTrace.Scripts["c0.highlight"]=(n,v)=>n==2?new NCardHighlight():v;break;
            case 67:FixtureTrace.Scripts["hi0.material"]=(n,v)=>n==2?new ShaderMaterial():v;break;
            case 68:FixtureTrace.Scripts["id0.key"]=(n,v)=>n==3?"CHANGED":v;break;
            case 69:FixtureTrace.Scripts["m0.level"]=(n,v)=>n==2?1:v;break;
            case 70:FixtureTrace.Scripts["mat0.shader"]=(_,_)=>throw new InvalidOperationException();break;
            case 71:mat.Width=0.04f;break;
            case 72:mat.Width=BitConverter.Int32BitsToSingle(1033476506);break;
            case 73:h.Visible=false;break;
            case 74:c.Visible=false;break;
            case 75:h.Hitbox.Visible=false;break;
            case 76:FixtureTrace.Scripts["hit0.enabled"]=(_,_)=>throw new InvalidOperationException();break;
            case 77:foreach(var item in x.Holders.Values)item.Hitbox.IsEnabled=false;break;
        }
        return x;
    }
    private static void ThrowLeaf(int code)
    {
#if !BASELINE
        FixtureTrace.Reset();using var f=new Program.RewardFixture("THROW_LEAF",2,2,8);
        var p=f.Session.Read();Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="accepted","parent dispatch");
        var b=(GenericEventV3Binding)typeof(PinnedGenericEventV3NativeAdapter).GetField("_pending",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(f.Adapter)!;
        var h=f.Grid.CurrentlyDisplayedCardHolders[0];object target=code==70?h.CardNode.CardHighlight.Material!:h.Hitbox;
        FixtureTrace.Labels[target]="throw";FixtureTrace.Scripts[code==70?"throw.shader":"throw.enabled"]=(_,_)=>throw new InvalidOperationException();FixtureTrace.Enabled=true;
        bool ready=GenericEventV3RewardAdapter.IsReady(b,f.Screen,out var diagnostic);FixtureTrace.Enabled=false;
        Check(!ready&&Convert.ToInt32(diagnostic)==code,"active throwing leaf");
        Check(f.OptionCalls==1&&f.SelectCalls==0&&f.ConfirmCalls==0,"throwing leaf passive");
        FixtureTrace.Reset();
#endif
    }
    private static void Leaves()
    {
        for(int code=37;code<=77;code++)
        {
            if(code is 70 or 76){ThrowLeaf(code);continue;}
            var result=Bind(Case(code));
            Check(!result.Success&&result.Exception is null,"leaf false "+code);
#if !BASELINE
            Check(result.Diagnostic==code,"leaf code "+code+" got "+result.Diagnostic);
#endif
            if(code is 46 or 48 or 50 or 54 or 61)
            {string key=code switch {46=>"c0.valid",48=>"hit0.valid",50=>"hi0.valid",54=>"mat0.valid",_=>"h0.valid"};Check(!result.Operations.Contains(key),"type precedes liveness "+code);}
            if(code is >=52 and <=55)Check(result.Operations.Count(x=>x=="hi0.material")==1,"single material property "+code);
            if(code==42)Check(result.Operations.Count(x=>x=="h0.model")==2&&result.Operations.Contains("c0.highlight"),"second model read preserves upfront reads");
            if(code==68)Check(result.Operations.Count(x=>x=="id0.key")==3,"validation constructor snapshot key reads");
        }
        FixtureTrace.Reset();
    }
    private static Dictionary<string,object> Traces()
    {
        var result=new Dictionary<string,object>();
        foreach(string name in new[]{"success","invisible_then_transient","transient_then_structural","selected_invisible","holder_hidden","card_hidden","hitbox_hidden","all_disabled","partly_enabled","late_shader_throw","late_enabled_throw","card_type","second_model_null","constructor_key_change"})
        {
            var x=new Input();
            switch(name)
            {
                case "invisible_then_transient":x.H().Visible=false;x.Material(2).Width=.04f;break;
                case "transient_then_structural":x.Material().Width=.04f;FixtureTrace.Scripts["h2.model"]=(n,v)=>n==3?new CardModel():v;break;
                case "selected_invisible":x.Material().Width=BitConverter.Int32BitsToSingle(1033476506);x.H().Visible=false;break;
                case "holder_hidden":x.H().Visible=false;break;
                case "card_hidden":x.H().CardNode.Visible=false;break;
                case "hitbox_hidden":x.H().Hitbox.Visible=false;break;
                case "all_disabled":foreach(var h in x.Holders.Values)h.Hitbox.IsEnabled=false;break;
                case "partly_enabled":x.H().Hitbox.IsEnabled=false;break;
                case "late_shader_throw":FixtureTrace.Scripts["mat2.shader"]=(_,_)=>throw new InvalidOperationException();break;
                case "late_enabled_throw":FixtureTrace.Scripts["hit2.enabled"]=(_,_)=>throw new InvalidOperationException();break;
                case "card_type":x.H().CardNode=new HiddenCard{Model=x.M(),CardHighlight=x.H().CardNode.CardHighlight};break;
                case "second_model_null":FixtureTrace.Scripts["h0.model"]=(n,v)=>n==2?null:v;break;
                case "constructor_key_change":FixtureTrace.Scripts["id0.key"]=(n,v)=>n==2?"CONSTRUCTOR_KEY":v;break;
            }
            Projection v=Bind(x);
            Check(!v.Operations.Contains("dispatch"),"preparation never dispatches");
            if(name is "success" or "partly_enabled")Check(v.Success&&v.Exception is null,"trace success");
            else Check(!v.Success,"trace failure");
            if(name=="holder_hidden")Check(!v.Operations.Contains("c0.visible")&&!v.Operations.Contains("hit0.visible"),"holder short circuit");
            if(name=="card_hidden")Check(!v.Operations.Contains("hit0.visible"),"card short circuit");
#if !BASELINE
            if(name=="invisible_then_transient")Check(v.Diagnostic==71,"deferred settlement first");
            if(name=="transient_then_structural")Check(v.Diagnostic==63,"structural failure first");
            if(name=="selected_invisible")Check(v.Diagnostic==72,"selected before visibility");
#endif
            result[name]=new {v.Success,v.Exception,v.Operations,v.Candidates};
        }
        FixtureTrace.Reset();return result;
    }
    internal static int Main(string[] args)
    {
        try
        {
            if(args.Length==1&&args[0]=="--trace"){Console.WriteLine(JsonSerializer.Serialize(Traces()));return 0;}
            if(args.Length!=0)throw new ArgumentException();
#if BASELINE
            var traces=Traces();Console.WriteLine("frozen v3 trace checks: "+_checks+"; trace scenarios: "+traces.Count);return 0;
#else
            Leaves();var traces=Traces();Console.WriteLine("candidate native checks: "+_checks+"; leaf codes: 41; trace scenarios: "+traces.Count);return 0;
#endif
        }
        catch(Exception e){Console.Error.WriteLine(e);return 1;}
    }
}
