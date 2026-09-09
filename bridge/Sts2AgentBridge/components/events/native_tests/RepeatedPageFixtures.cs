using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.addons.mega_text;
using Sts2AgentBridge.Successors.GenericEventV7;

internal static partial class Program
{
    // Mirrors the inspected ordinary SetOptions path: clear old controllers,
    // allocate new options/controllers, then finish the owned Chosen callback.
    // No game assemblies execute and no HP/gold effects are claimed.
    internal sealed class RepeatedPageFixture : IDisposable
    {
        internal readonly Fixture Native = new("REPEATED_PAGE");
        internal GenericEventV7Session Session => Native.Session;
        internal readonly TaskCompletionSource Completion = new();
        internal readonly List<NEventOptionButton> Buttons = new();
        internal int Lingers;
        internal bool Delayed, Fault, Canceled, Alternate, Dangerous;
        internal string Refresh = "fresh";
        internal bool Waiting => Delayed && Lingers == 1 && !Completion.Task.IsCompleted;
        internal RepeatedPageFixture()
        {
            Clear();
            Add("IMMERSE", () => { Native.OptionCalls++; ShowLoop(); return Task.CompletedTask; });
        }
        private void Clear()
        {
            foreach (var b in Native.Room.Layout.OptionButtons.ToArray()) RetireButton(Native.Room.Layout,b);
        }
        private void Add(string key, Func<Task> callback, bool proceed = false)
        {
            Native.AddOption(new EventOption { TextKey=key, Callback=callback, IsProceed=proceed,
                WillKillPlayer=key is "LINGER" or "OTHER" ? _ => Dangerous : null });
            Buttons.Add(Native.Room.Layout.OptionButtons.Last());
        }
        private void ShowLoop()
        {
            Clear();
            Add(Alternate && Lingers % 2 == 1 ? "OTHER" : "LINGER", Linger);
            Add("EXIT_BATHS", () => {
                Native.OptionCalls++; Native.Model.IsFinished=true; Clear();
                Add("PROCEED", () => { Native.OptionCalls++; Native.Map.IsOpen=true;
                    Native.Map.IsTravelEnabled=true; return Task.CompletedTask; }, true);
                return Task.CompletedTask;
            });
        }
        private async Task Linger()
        {
            Native.OptionCalls++; Lingers++;
            var previous=Native.Room.Layout.OptionButtons.ToArray();
            if (Refresh is "fresh" or "partial" or "old" or "invalid") ShowLoop();
            if (Refresh == "label") previous[0].GetNodeOrNull<MegaRichTextLabel>("%Text")!.Text="Changed text";
            if (Refresh == "flags") previous[0].IsEnabled=false;
            if (Refresh == "partial") {
                previous[1].InstanceValid=true;
                Native.Room.Layout.OptionButtons[1]=previous[1];
            }
            if (Refresh == "old") {
                Clear(); Buttons[0].InstanceValid=true; Native.Room.Layout.OptionButtons.Add(Buttons[0]);
            }
            if (Refresh == "invalid") Native.Room.Layout.OptionButtons[0].Option.TextKey="";
            if (Delayed && Lingers == 1) await Completion.Task;
            if (Fault) throw new InvalidOperationException("owned callback fault");
            if (Canceled) throw new OperationCanceledException();
        }
        internal GenericEventV7Observation Act(string action="choose:0")
        {
            var p=Session.Read(); Check(p.Status=="ready","repeat ready");
            Check(Session.Apply(p.DecisionId,action).Outcome=="accepted","repeat dispatch");
            return Session.Read();
        }
        public void Dispose() => Native.Dispose();
    }

    private static void RepeatedPageTests()
    {
        foreach (bool alternate in new[]{false,true})
        using (var f=new RepeatedPageFixture {Alternate=alternate}) {
            var first=f.Act(); var second=f.Act(); var third=f.Act();
            Check(first.Candidates[0].StableId==third.Candidates[0].StableId,"same keys may return");
            Check(first.Candidates[0].RenderedText==third.Candidates[0].RenderedText,"identical labels allowed");
            Check(new[]{first.DecisionId,second.DecisionId,third.DecisionId}.Distinct().Count()==3,"new decision per completed choice");
            Check(f.Session.Read().DecisionId==third.DecisionId,"stable repeated read");
            Check(f.Session.Apply(first.DecisionId,"choose:0").Outcome=="stale_decision"&&f.Native.OptionCalls==3,"old decision never repeats input");
            Check(f.Act("choose:1").Phase=="proceed","exit after two lingers");
            var done=f.Act(); Check(done.Status=="complete"&&done.ParentReconciled==5,"repeat through map");
            Check(done.Effects=="unverified"&&done.PriorResults.Take(4).All(r=>r.Result=="option_transition"),"no fabricated effect verification");
            Check(f.Buttons.Sum(b=>b.ForceClickCalls)==5&&f.Buttons.All(b=>b.ForceClickCalls<=1),"exactly once per control");
        }
        using (var f=new RepeatedPageFixture {Delayed=true}) {
            f.Act(); var p=f.Session.Read();
            Check(f.Act().Status=="waiting","fresh page awaits callback");
            Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="unsupported"&&f.Native.OptionCalls==2,"pending cannot dispatch again");
            f.Completion.SetResult();
            Check(f.Session.Read() is {Status:"ready",ParentReconciled:2},"settled repeat becomes ready");
        }
        foreach (string refresh in new[]{"unchanged","label","flags","partial","old"})
        using (var f=new RepeatedPageFixture {Refresh=refresh}) {
            f.Act(); Check(f.Act().Status=="waiting","old controls cannot prove progress: "+refresh);
            for (int i=0;i<GenericEventV7Limits.MaximumPendingReads;i++) f.Session.Read();
            Check(f.Session.Read() is {Status:"unsupported",ParentAccepted:2,ParentReconciled:1},"bounded stale page stop: "+refresh);
            Check(f.Native.OptionCalls==2,"stale controls never retried");
        }
        foreach (string failure in new[]{"fault","cancel","invalid"})
        using (var f=new RepeatedPageFixture {Fault=failure=="fault",Canceled=failure=="cancel",Refresh=failure=="invalid"?"invalid":"fresh"}) {
            f.Act(); Check(f.Act() is {Status:"unsupported",ParentAccepted:2,ParentReconciled:1},"failed or malformed new page cannot reconcile: "+failure);
        }
        using (var f=new RepeatedPageFixture()) {
            f.Act(); var p=f.Session.Read(); f.Dangerous=true;
            Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="unsupported"&&f.Native.OptionCalls==1,"changed danger revalidated before dispatch");
        }
        using (var f=new RepeatedPageFixture()) {
            f.Act(); f.Dangerous=true; var p=f.Session.Read();
            Check(p.LegalActions.SequenceEqual(new[]{"choose:1"}),"dangerous repeat is masked");
            Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="illegal_action"&&f.Native.OptionCalls==1,"dangerous repeat never dispatched");
        }
        using (var f=new RepeatedPageFixture()) {
            f.Act(); var p=f.Session.Read(); var option=f.Native.Room.Layout.OptionButtons[0].Option;
            f.Native.Room.Layout.OptionButtons.Clear(); f.Native.AddOption(option);
            Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="unsupported"&&f.Native.OptionCalls==1,"replacement between read and apply rejected");
        }
        using (var f=new RepeatedPageFixture()) {
            for (int i=0;i<GenericEventV7Limits.MaximumParentActions;i++) f.Act();
            var p=f.Session.Read(); Check(f.Session.Apply(p.DecisionId,"choose:0").Outcome=="budget_exhausted","repeat action cap");
            Check(f.Native.OptionCalls==12&&f.Session.Read().ParentReconciled==12,"no thirteenth input");
        }
    }
}
