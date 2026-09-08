using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.CardTransformV2;
using Sts2AgentBridge.Successors.GenericEventV5;

internal static class Program
{
    private static int _checks;
    private static void Check(bool value, string label) { _checks++; if (!value) throw new Exception(label); }
    private static void Status(Fixture f,string expected) => Check(f.Session.Read() is CardSelectionV1Observation o && o.Status==expected, expected);
    private static void Done(Fixture f) => Check(f.Session.Read() is CardSelectionV1ResolvedResult, "resolved");
    private static void Main()
    {
        for(int count=1;count<=8;count++)
        {
            using var f=new Fixture(count);f.Start();
            for(int n=0;n<=count;n++) { f.Set(f.Command(f.Slots,n,CardTransformV2CommandState.Running));Status(f,"waiting"); }
            f.Set(f.Command(f.Slots,count,CardTransformV2CommandState.Succeeded));Status(f,"waiting");
            f.Complete=true;Done(f);Done(f);Check(f.ConfirmCalls==1,"one confirm");
        }
        using(var f=new Fixture(2,legacy:true)) {f.Start();f.Set(f.Command(f.Slots,1,CardTransformV2CommandState.Running));Status(f,"unsupported");}
        using(var f=new Fixture(2)) {f.Start();f.Set(f.Command(f.Slots,0,CardTransformV2CommandState.NotStarted,false));Status(f,"waiting");f.Set(f.Command(f.Slots,2,CardTransformV2CommandState.Succeeded));f.Complete=true;Done(f);}
        using(var f=new Fixture(3))
        {
            f.Start();var first=f.Command(new[]{2},1,CardTransformV2CommandState.Running,identity:f.CommandIds[0]);f.Set(first);Status(f,"waiting");
            var second=f.Command(new[]{0},1,CardTransformV2CommandState.Succeeded,identity:f.CommandIds[1],offset:1);
            var third=f.Command(new[]{1},1,CardTransformV2CommandState.Succeeded,identity:f.CommandIds[2],offset:2);
            f.Set(first with {State=CardTransformV2CommandState.Succeeded,CompletedResults=first.Insertions.Select(x=>new CardTransformV2CommandResult(true,x.FinalIdentity)).ToArray()},second,third);
            f.Complete=true;Done(f);Check(f.Deck[^3].StableKey=="Final_2"&&f.Deck[^2].StableKey=="Final_0","native order not selection order");
        }
        foreach(string fault in new[]{"legacy","removed_missing","removed_extra","removed_duplicate","unknown_insert","wrong_order","baseline_mutation","final_level","final_key","final_ref","duplicate_original","duplicate_final","baseline_final","bad_ordinal","bad_original","notstarted_effect","running_results","succeeded_partial","false_result","foreign_result","missing_result","result_order","faulted","canceled","parallel","overlap","reused_command"})
        {
            using var f=new Fixture(2);f.Start();var c=f.Command(f.Slots,2,CardTransformV2CommandState.Succeeded);f.Set(c);
            switch(fault)
            {
                case "legacy": f.LegacyReplacement=true;break;
                case "removed_missing": f.Effect=f.Effect with {RemovedOriginals=new[]{f.Models[0]}};break;
                case "removed_extra": f.Effect=f.Effect with {RemovedOriginals=new[]{f.Models[0],f.Models[1],f.Models[2]}};break;
                case "removed_duplicate": f.Effect=f.Effect with {RemovedOriginals=new[]{f.Models[0],f.Models[0]}};break;
                case "unknown_insert": f.Deck.Add(new(new object(),"Unknown",0));break;
                case "wrong_order": f.Deck.Reverse();break;
                case "baseline_mutation": f.Deck[0]=new(f.Deck[0].ModelIdentity,f.Deck[0].StableKey,1);break;
                case "final_level": f.Deck[^1]=new(f.Deck[^1].ModelIdentity,f.Deck[^1].StableKey,1);break;
                case "final_key": f.Deck[^1]=new(f.Deck[^1].ModelIdentity,"Changed",0);break;
                case "final_ref": f.Deck[^1]=new(new object(),f.Deck[^1].StableKey,0);break;
                case "duplicate_original": c=c with {Insertions=new[]{c.Insertions[0],c.Insertions[1] with {OriginalIdentity=c.Insertions[0].OriginalIdentity}}};f.Set(c);break;
                case "duplicate_final": c=c with {Insertions=new[]{c.Insertions[0],c.Insertions[1] with {FinalIdentity=c.Insertions[0].FinalIdentity}}};f.Set(c);break;
                case "baseline_final": c=c with {Insertions=new[]{c.Insertions[0] with {FinalIdentity=f.Models[2]},c.Insertions[1]}};f.Set(c);break;
                case "bad_ordinal": c=c with {Insertions=new[]{c.Insertions[0] with {Ordinal=2},c.Insertions[1]}};f.Set(c);break;
                case "bad_original": c=c with {OriginalIdentities=new[]{f.Models[0],f.Models[2]}};f.Set(c);break;
                case "notstarted_effect": f.Set(c with {State=CardTransformV2CommandState.NotStarted});break;
                case "running_results": f.Set(c with {State=CardTransformV2CommandState.Running});break;
                case "succeeded_partial": f.Set(f.Command(f.Slots,1,CardTransformV2CommandState.Succeeded));break;
                case "false_result": f.Set(c with {CompletedResults=new[]{new CardTransformV2CommandResult(false,c.Insertions[0].FinalIdentity),c.CompletedResults[1]}});break;
                case "foreign_result": f.Set(c with {CompletedResults=new[]{new CardTransformV2CommandResult(true,new object()),c.CompletedResults[1]}});break;
                case "missing_result": f.Set(c with {CompletedResults=Array.Empty<CardTransformV2CommandResult>()});break;
                case "result_order": f.Set(c with {CompletedResults=c.CompletedResults.Reverse().ToArray()});break;
                case "faulted": f.Set(c with {State=CardTransformV2CommandState.Faulted,CompletedResults=Array.Empty<CardTransformV2CommandResult>()});break;
                case "canceled": f.Set(c with {State=CardTransformV2CommandState.Canceled,CompletedResults=Array.Empty<CardTransformV2CommandResult>()});break;
                case "parallel": f.Set(f.Command(new[]{0},1,CardTransformV2CommandState.Running),f.Command(new[]{1},1,CardTransformV2CommandState.Succeeded,identity:f.CommandIds[1],offset:1));break;
                case "overlap": f.Set(f.Command(new[]{0},1,CardTransformV2CommandState.Succeeded),f.Command(new[]{0},1,CardTransformV2CommandState.Succeeded,identity:f.CommandIds[1],offset:1));break;
                case "reused_command": f.Set(f.Command(new[]{0},1,CardTransformV2CommandState.Succeeded),f.Command(new[]{1},1,CardTransformV2CommandState.Succeeded,offset:1));break;
            }
            Status(f,"unsupported");Check(f.ConfirmCalls==1,"no retry "+fault);
        }
        foreach(string fault in new[]{"null_command","unknown_state","notstarted_removed","succeeded_not_removed","empty_domain","global_missing","global_extra","global_mapping"})
        {
            using var f=new Fixture(2);f.Start();var c=f.Command(f.Slots,2,CardTransformV2CommandState.Succeeded);f.Set(c);
            switch(fault)
            {
                case "null_command": f.Set(c with {CommandIdentity=null!});break;
                case "unknown_state": f.Set(c with {State=(CardTransformV2CommandState)99});break;
                case "notstarted_removed": f.Set(f.Command(f.Slots,0,CardTransformV2CommandState.NotStarted));break;
                case "succeeded_not_removed": f.Set(c with {AllOriginalsRemoved=false});break;
                case "empty_domain": f.Set(c with {OriginalIdentities=Array.Empty<object>()});break;
                case "global_missing": f.Effect=f.Effect with {OrderedCommittedInsertions=new[]{c.Insertions[0]}};break;
                case "global_extra": f.Effect=f.Effect with {OrderedCommittedInsertions=c.Insertions.Concat(new[]{c.Insertions[0]}).ToArray()};break;
                case "global_mapping": f.Effect=f.Effect with {OrderedCommittedInsertions=new[]{c.Insertions[0] with {FinalStableKey="Changed"},c.Insertions[1]}};break;
            }
            Status(f,"unsupported");
        }
        using(var f=new Fixture(2))
        {
            f.Start();var c=f.Command(f.Slots,2,CardTransformV2CommandState.Succeeded);f.Set(c);Status(f,"waiting");
            var changed=c.Insertions.Select(x=>x with {FinalIdentity=new object()}).ToArray();
            f.Set(c with {Insertions=changed,CompletedResults=changed.Select(x=>new CardTransformV2CommandResult(true,x.FinalIdentity)).ToArray()});Status(f,"unsupported");
        }
        foreach(string change in new[]{"command","domain","row","shrink","flag","state","result"})
        {
            using var f=new Fixture(2);f.Start();var c=f.Command(f.Slots,1,CardTransformV2CommandState.Running);f.Set(c);Status(f,"waiting");
            switch(change)
            {
                case "command": c=c with {CommandIdentity=new object()};break;
                case "domain": c=c with {OriginalIdentities=c.OriginalIdentities.Reverse().ToArray()};break;
                case "row": c=c with {Insertions=new[]{c.Insertions[0] with {FinalIdentity=new object()}}};break;
                case "shrink": c=c with {Insertions=Array.Empty<CardTransformV2Insertion>()};break;
                case "flag": c=f.Command(f.Slots,0,CardTransformV2CommandState.Running,false);break;
                case "state": c=f.Command(f.Slots,0,CardTransformV2CommandState.NotStarted,false);break;
                case "result": c=c with {CompletedResults=new[]{new CardTransformV2CommandResult(true,c.Insertions[0].FinalIdentity)}};break;
            }
            f.Set(c);Status(f,"unsupported");
        }
        using(var f=new Fixture(2))
        {
            f.Start();var c=f.Command(f.Slots,1,CardTransformV2CommandState.Running);var mutable=c.Insertions.ToList();c=c with {Insertions=mutable};f.Set(c);Status(f,"waiting");
            mutable[0]=mutable[0] with {FinalIdentity=new object()};f.Set(c);Status(f,"unsupported");
        }
        using(var f=new Fixture(2))
        {
            f.Start();var c=f.Command(f.Slots,1,CardTransformV2CommandState.Running);var mutable=c.OriginalIdentities.ToList();f.Set(c with {OriginalIdentities=mutable});Status(f,"waiting");
            mutable.Clear();f.Set(c);Status(f,"waiting");
        }
        using(var f=new Fixture(2))
        {
            f.Start();for(int n=0;n<255;n++)Status(f,"waiting");f.Set(f.Command(f.Slots,1,CardTransformV2CommandState.Running));Status(f,"waiting");
            int reads=f.Captures;Status(f,"unsupported");Check(f.Captures==reads,"257th no capture despite progress");Check(f.ConfirmCalls==1,"budget no retry");
        }
        using(var f=new Fixture(2)) {f.Effect=new(Array.Empty<CardTransformV2CommandWitness>(),new[]{f.Models[0]},Array.Empty<CardTransformV2Insertion>());Status(f,"unsupported");}
        using(var f=new Fixture(2)) {f.Start();var overflow=new RepeatingList<object>(f.Models[0]);f.Effect=new(Array.Empty<CardTransformV2CommandWitness>(),overflow,Array.Empty<CardTransformV2Insertion>());Status(f,"unsupported");Check(overflow.Reads==9,"bounded max+1");}
        foreach(var spec in new[]{(0,0,3),(2,1,3),(9,9,10),(2,2,2),(2,2,65)})
        {bool rejected=false;try{using var f=new Fixture(2,min:spec.Item1,max:spec.Item2,domain:spec.Item3);}catch(ArgumentException){rejected=true;}Check(rejected,"invalid constructor bounds");}
        VariableCases();
        Console.WriteLine($"CardTransformV2 tests passed: {_checks} assertions");
    }
    private static void VariableCases()
    {
        for(int min=1;min<=8;min++)for(int max=min;max<=8;max++)
            foreach(int count in new[]{min,(min+max)/2,max}.Distinct())
            {
                using var f=new Fixture(count,min:min,max:max);f.Start();
                Check(f.PreviewCalls==(count<max?1:0),"explicit preview only below max");
                var command=f.Command(f.Slots,count,CardTransformV2CommandState.Succeeded);f.Set(command);f.Complete=true;
                var done=f.Session.Read() as CardSelectionV1ResolvedResult;
                Check(done is not null&&done.SelectedCards.Count==count,"exact chosen count");
                Check(done!.PriorResults.Count==count+(count<max?2:1),"exact action history");
                Check(done.PriorResults.Count(r=>r.ActionId=="preview")==f.PreviewCalls,"preview history");
                Check(f.Deck.Take(f.Models.Length-count).Select(x=>x.ModelIdentity).SequenceEqual(f.Baseline.Where(x=>!f.Slots.Contains(Array.IndexOf(f.Models,x.ModelIdentity))).Select(x=>x.ModelIdentity)),"unselected survivors retained");
                Done(f);Check(f.ConfirmCalls==1,"no repeated commit");
            }
        foreach(bool late in new[]{false,true})
        {
            using var f=new Fixture(1,min:1,max:3);f.Act("select:0");if(late)Status(f,"ready");f.ForcePreview=true;
            Status(f,"unsupported");Status(f,"unsupported");Check(f.PreviewCalls==0&&f.ConfirmCalls==0&&f.SelectCalls==1,"unrequested preview never confirmed");
        }
        using(var f=new Fixture(1,min:1,max:3))
        {
            f.Act("select:0");f.Act("preview");Status(f,"ready");f.HidePreview=true;Status(f,"unsupported");Check(f.SelectCalls==1&&f.PreviewCalls==1&&f.ConfirmCalls==0,"selection cannot reopen after explicit preview");
        }
        using(var f=new Fixture(2,min:2,max:4))
        {
            f.Act("select:0");var read=(CardSelectionV1Observation)f.Session.Read();Check(!read.LegalActions.Contains("preview"),"no preview below minimum");
            Check(f.Session.Apply(read.DecisionId,"preview") is CardSelectionV1ApplyFailure,"below-min apply rejected");Check(f.PreviewCalls==0,"no invented dispatch");
        }
        foreach(bool invisible in new[]{false,true})using(var f=new Fixture(1,min:1,max:3))
        {
            f.Act("select:0");f.PreviewEnabled=invisible;f.PreviewVisible=!invisible;
            var read=(CardSelectionV1Observation)f.Session.Read();Check(!read.LegalActions.Contains("preview")&&read.LegalActions.Contains("select:1"),"unavailable preview can continue selecting");
        }
        using(var f=new Fixture(1,min:1,max:3))
        {
            f.Act("select:0");var read=(CardSelectionV1Observation)f.Session.Read();f.ReplacePreviewControl=true;
            Check(f.Session.Apply(read.DecisionId,"preview") is CardSelectionV1ApplyFailure {Outcome:"unsupported"},"stale preview control");Check(f.PreviewCalls==0,"stale control no dispatch");
        }
        using(var f=new Fixture(1,min:1,max:3))
        {
            f.Act("select:0");var read=(CardSelectionV1Observation)f.Session.Read();f.ThrowPreview=true;
            Check(f.Session.Apply(read.DecisionId,"preview") is CardSelectionV1ApplyFailure {Outcome:"uncertain"},"lost preview dispatch");
            Check(f.Session.Apply(read.DecisionId,"preview") is CardSelectionV1ApplyFailure,"no retry uncertain preview");Check(f.PreviewCalls==1&&f.ConfirmCalls==0,"one uncertain preview");
        }
        using(var f=new Fixture(3,min:2,max:4))
        {
            foreach(int slot in f.Slots)f.Act("select:"+slot);f.Act("preview");f.PreviewSlots=new[]{f.Slots[0],f.Slots[1]};f.PreviewTransient=true;
            Status(f,"waiting");Check(f.ConfirmCalls==0,"minimum partial membership is not complete");
            f.PreviewSlots=null;f.PreviewTransient=false;f.Act("confirm");f.Set(f.Command(f.Slots,3,CardTransformV2CommandState.Succeeded));f.Complete=true;Done(f);
        }
        foreach(int[] bad in new[]{new[]{0,0},new[]{0,3}})using(var f=new Fixture(2,min:1,max:3))
        {
            foreach(int slot in f.Slots)f.Act("select:"+slot);f.Act("preview");f.PreviewSlots=bad;Status(f,"unsupported");Check(f.ConfirmCalls==0,"foreign or duplicate preview withheld");
        }
    }
    private sealed class RepeatingList<T>(T value):IReadOnlyList<T>
    {
        internal int Reads;public int Count=>1;public T this[int i]=>value;
        public IEnumerator<T> GetEnumerator(){for(int i=0;i<100;i++){Reads++;yield return value;}}
        IEnumerator IEnumerable.GetEnumerator()=>GetEnumerator();
    }
    private sealed class Adapter(Fixture f):ICardTransformV2NativeAdapter,ICardSelectionV1NativeAdapter
    {
        public CardTransformV2SurfaceCapture CaptureSurface(){f.Captures++;return new(f.Surface(),f.Effect);}
        CardSelectionV1SurfaceCapture ICardSelectionV1NativeAdapter.CaptureSurface(){f.Captures++;return f.Surface();}
        public void Dispose(){f.Disposals++;}
    }
    private sealed class Fixture:IDisposable
    {
        internal readonly IGenericEventV5ChildSession Session;
        internal readonly object[] Models,Finals,CommandIds=Enumerable.Range(0,8).Select(_=>new object()).ToArray();
        private readonly object[] _holders,_nodes;private readonly Action[] _select;private readonly Action _confirmDispatch;private readonly Action _previewDispatch;private readonly object _previewControl=new();
        internal readonly int[] Slots;private readonly int _count;private readonly object _identity=new(),_preview=new(),_confirm=new();
        private readonly List<int> _selected=new();private readonly CardSelectionV1ParentContext _context;
        internal List<CardSelectionV1DeckCard> Deck;internal readonly CardSelectionV1DeckCard[] Baseline;
        internal bool Complete,LegacyReplacement,ForcePreview,PreviewTransient,ReplacePreviewControl,ThrowPreview,HidePreview;internal bool PreviewVisible=true,PreviewEnabled=true;internal int[]? PreviewSlots;private bool _confirmed,_requestedPreview;internal int ConfirmCalls,PreviewCalls,SelectCalls,Captures,Disposals;
        internal CardTransformV2EffectWitness Effect=new(Array.Empty<CardTransformV2CommandWitness>(),Array.Empty<object>(),Array.Empty<CardTransformV2Insertion>());
        internal Fixture(int count,bool legacy=false,int? min=null,int? max=null,int? domain=null)
        {
            _confirmDispatch=Confirm;_previewDispatch=()=>{PreviewCalls++;_requestedPreview=true;if(ThrowPreview)throw new InvalidOperationException();};_count=count;int n=domain??(max??count)+2;Models=Enumerable.Range(0,n).Select(_=>new object()).ToArray();Finals=Enumerable.Range(0,n).Select(_=>new object()).ToArray();
            _holders=Models.Select(_=>new object()).ToArray();_nodes=Models.Select(_=>new object()).ToArray();_select=Enumerable.Range(0,n).Select<int,Action>(i=>()=>{SelectCalls++;_selected.Add(i);}).ToArray();
            Slots=Enumerable.Range(0,count).Reverse().ToArray();Baseline=Models.Select((m,i)=>new CardSelectionV1DeckCard(m,"Card_"+i,0)).ToArray();Deck=Baseline.ToList();
            _context=new(new string('a',32),CardSelectionV1ParentKind.Event,new string('b',64),"choose:0",_identity,_identity,_identity,_identity,_identity,_identity,_identity,
                CardSelectionV1Operation.Transform,min??count,max??count,CardSelectionV1CommitMode.PreviewConfirm,n);
            var adapter=new Adapter(this);Session=legacy?new GenericEventV5FrozenChildSession(new CardSelectionV1Session(_context,adapter)):new CardTransformV2Session(_context,adapter);
        }
        internal void Start()
        {
            foreach(int i in Slots)Act("select:"+i);
            if(_count<_context.MaxSelect)Act("preview");
            Act("confirm");Check(ConfirmCalls==1,"real confirm dispatch");
        }
        internal void Act(string action)
        {
            var o=Session.Read() as CardSelectionV1Observation;Check(o is {Status:"ready"}&&o.LegalActions.Contains(action),"advertised "+action);
            Check(Session.Apply(o!.DecisionId,action) is CardSelectionV1DispatchReceipt,"accepted "+action);
        }
        internal CardTransformV2CommandWitness Command(int[] slots,int inserted,CardTransformV2CommandState state,bool removed=true,object? identity=null,int offset=0)
        {
            var rows=slots.Take(inserted).Select((slot,i)=>new CardTransformV2Insertion(offset+i+1,Models[slot],Finals[slot],"Final_"+slot,0)).ToArray();
            return new(identity??CommandIds[0],slots.Select(i=>Models[i]).ToArray(),state,removed,rows,
                state==CardTransformV2CommandState.Succeeded?rows.Select(x=>new CardTransformV2CommandResult(true,x.FinalIdentity)).ToArray():Array.Empty<CardTransformV2CommandResult>());
        }
        internal void Set(params CardTransformV2CommandWitness[] commands)
        {
            var removed=commands.Where(c=>c.AllOriginalsRemoved).SelectMany(c=>c.OriginalIdentities).ToArray();var rows=commands.SelectMany(c=>c.Insertions).ToArray();Effect=new(commands,removed,rows);
            Deck=Baseline.Where(c=>!removed.Any(x=>ReferenceEquals(x,c.ModelIdentity))).Concat(rows.Select(x=>new CardSelectionV1DeckCard(x.FinalIdentity,x.FinalStableKey,x.FinalUpgradeLevel))).ToList();
        }
        internal CardSelectionV1SurfaceCapture Surface()
        {
            bool preview=!_confirmed&&!HidePreview&&(ForcePreview||_requestedPreview||_selected.Count==_context.MaxSelect);
            var candidates=Models.Select((m,i)=>new CardSelectionV1NativeCandidate(i,"Card_"+i,_holders[i],m,_nodes[i],0,true,true,_selected.Contains(i),true,_select[i])).ToArray();
            return new(CardSelectionV1SurfaceStatus.Available,_identity,_identity,_identity,_identity,_identity,_identity,_identity,_identity,_identity,
                preview?_preview:null,CardSelectionV1ParentKind.Event,CardSelectionV1Operation.Transform,_context.MinSelect,_context.MaxSelect,CardSelectionV1CommitMode.PreviewConfirm,
                _confirmed?CardSelectionV1Phase.Submitted:PreviewTransient?CardSelectionV1Phase.Transient:preview?CardSelectionV1Phase.Preview:CardSelectionV1Phase.Selecting,!_confirmed,_confirmed,preview,true,Models.Length,true,
                _confirmed?CardSelectionV1TaskState.Succeeded:CardSelectionV1TaskState.Incomplete,Complete,
                _confirmed?_selected.Select(i=>Models[i]).ToArray():Array.Empty<object>(),preview?(PreviewSlots??_selected.ToArray()).Select(i=>Models[i]).ToArray():Array.Empty<object>(),candidates,Deck,
                LegacyReplacement?new[]{new CardSelectionV1Replacement(Models[0],Finals[0],"Final_0",0)}:Array.Empty<CardSelectionV1Replacement>(),new CardSelectionV1NativeControl(ReplacePreviewControl?new object():_previewControl,PreviewVisible,PreviewEnabled,_previewDispatch),
                preview?new CardSelectionV1NativeControl(_confirm,true,true,_confirmDispatch):null);
        }
        private void Confirm(){_confirmed=true;ConfirmCalls++;}
        public void Dispose()=>Session.Dispose();
    }
}
