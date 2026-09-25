// Executes the production coordinator and event-parent projection with the real
// generic-event session/wire. Game objects and their displayed values are inert
// seams; this is not a native localization or tooltip integration test.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using Sts2AgentBridge.Successors.GenericEventV7;
using Sts2AgentBridge.Successors.GenericEventV7.Native;
using static Sts2AgentBridge.Unified.FullPublicGraph;

namespace MegaCrit.Sts2.Core.Models
{
    internal sealed class FixtureText
    {
        internal string Text = "Neow";
        internal bool Present = true;
        internal bool FormatFails;
        internal int Formats;
        public bool Exists() => Present;
        public string GetFormattedText()
        {
            Formats++;
            return Present && !FormatFails ? Text : throw new InvalidOperationException("Unavailable localization text.");
        }
    }
    internal sealed class ModelId { public string Entry = "NEOW"; }
    internal class EventModel
    {
        public ModelId Id = new();
        public FixtureText Title = new();
        public FixtureText? Description;
    }
    internal sealed class AncientEventModel : EventModel {}
    internal class RelicModel { internal string Key = "lost_coffer"; }
    internal sealed class EventOption
    {
        public RelicModel? Relic;
        public JsonObject[] HoverTips = Array.Empty<JsonObject>();
    }
}
namespace MegaCrit.Sts2.Core.Models.Relics { internal sealed class NeowsBones : RelicModel {} }
namespace MegaCrit.Sts2.Core.Rooms { internal sealed class EventRoom { public EventModel LocalMutableEvent = null!; } }
namespace Sts2AgentBridge.Successors.GenericEventV7.Native
{
    internal sealed class GenericEventFullRewards { internal GenericEventFullRewards(object binding, object set) {} }
    internal sealed class PinnedGenericEventV7NativeAdapter : IGenericEventV7NativeAdapter
    {
        internal Func<object, object, GenericEventFullRewards>? FullRewardsFactory;
        internal readonly List<GenericEventV7NativeOption> Options = new();
        internal readonly Dictionary<object, EventOption> Displayed = new();
        internal int Inputs;
        internal bool Preparing;
        internal EventOption? InspectOption(object identity) => Displayed.GetValueOrDefault(identity);
        public GenericEventV7NativeCapture Capture() => Preparing
            ? new("preparing", false, Array.Empty<GenericEventV7NativeOption>()) : new("parent", false, Options);
        public void Dispatch(object identity, string nonce, string decision, string action) { Inputs++; throw new InvalidOperationException("Observation fixture cannot dispatch."); }
        public IGenericEventV7ChildSession CreateChild(object identity) => throw new InvalidOperationException();
        public void CompleteParent() => throw new InvalidOperationException();
        public void Dispose() {}
    }
}
namespace Sts2AgentBridge.Unified
{
    internal sealed class FixtureRun { internal object? CurrentRoom; }
    internal sealed partial class FullNativeState
    {
        internal FixtureRun Run = new();
        private readonly Dictionary<object, string> _references = new(ReferenceEqualityComparer.Instance);
        internal void Bind(object identity) {}
        internal string Ref(string kind, object identity)
        {
            if (!_references.TryGetValue(identity, out string? reference))
                _references.Add(identity, reference = kind + ":" + _references.Count);
            return reference;
        }
        internal JsonObject Relic(RelicModel relic) => Node("relic", relic.Key, Ref("relic", relic));
    }
    internal static class FullNativeDisplay
    {
        internal static JsonObject Hover(JsonObject value) => (JsonObject)value.DeepClone();
    }
    internal sealed partial class FullNativeBackend
    {
        private bool _resumeProjection = false;
        private BridgeRequest ResumeCommand(string? decision, string? action) => throw new AgentUnsupported();
        private JsonObject EventChild(PinnedGenericEventV7NativeAdapter adapter, JsonElement wire, EventModel model) => throw new AgentUnsupported();
        internal void SetEvent(EventModel model) => _state.Run.CurrentRoom = new EventRoom { LocalMutableEvent = model };
    }
    internal sealed partial class BridgeRouter
    {
        internal readonly PinnedGenericEventV7NativeAdapter? EventAdapter;
        internal readonly GenericEventV7Session? EventSession;
        internal readonly GenericEventV7WireService? EventWire;
        internal object? ActiveObservationSource => EventAdapter is null ? null : (EventAdapter, EventSession!);
        internal BridgeRouter(bool dialogue, RelicModel[] relics) : this(false)
        {
            EventAdapter = new();
            if (dialogue) EventAdapter.Options.Add(new(new object(), "ANCIENT_DIALOGUE.0", "Continue dialogue", true, false, false));
            else foreach (var relic in relics)
            {
                var identity = new object();
                EventAdapter.Options.Add(new(identity, relic.Key.ToUpperInvariant(), relic.Key, true, false, false));
                EventAdapter.Displayed.Add(identity, new EventOption { Relic = relic,
                    HoverTips = new[] { Node("tooltip", fields: new[] { ("description", (object?)"Displayed offer details") }) } });
            }
            const string nonce = "0123456789abcdef0123456789abcdef";
            EventSession = new(EventAdapter, nonce); EventWire = new(nonce, EventSession);
        }
        private ModuleReply DispatchEvent(BridgeRequest request)
        {
            if (request.Path == CampaignRoutes.FullDecision) return Json(new { status = "ready", surface = "event" });
            if (request.IsPost) throw new InvalidOperationException("No fixture policy input permitted.");
            return new(EventWire!.Handle("GET", request.Path, null));
        }
    }
}

internal static partial class Program
{
    private static void EventParentCases()
    {
        foreach (bool dialogue in new[] { true, false })
        foreach (string description in new[] { "missing", "present", "null" })
        {
            var text = description == "null" ? null : new FixtureText { Present = description == "present", Text = "Displayed event description" };
            var model = new AncientEventModel { Description = text };
            var router = new Sts2AgentBridge.Unified.BridgeRouter(dialogue, new[] {
                new RelicModel { Key = "lost_coffer" }, new RelicModel { Key = "neows_torment" }, new RelicModel { Key = "cursed_pearl" } });
            using var backend = new Sts2AgentBridge.Unified.FullNativeBackend(router, new Sts2AgentBridge.Adapters.Public.PinnedPublicRewardDecisionReader(), router.Choice);
            backend.SetEvent(model);
            router.EventAdapter!.Preparing = true;
            Check(backend.Read().Status == "waiting", "native preparation has no policy decision");
            router.EventAdapter.Preparing = false;
            var frame = backend.Read();
            Check(frame.Status == "ready" && frame.Completed.Length == 0, "first ancient parent is ready without completed input");
            Validate(frame.Observation!);
            Check(frame.Commands.Length == (dialogue ? 1 : 3), "only visible native choices are actionable");
            Check(frame.Commands.Select(c => c.Candidate["kind"]!.GetValue<string>()).All(k => k == (dialogue ? "choose_event_option" : "choose_ancient_relic")), "dialogue and relic semantics stay distinct");
            Check(frame.Commands.Select(c => c.Request.Action).SequenceEqual(Enumerable.Range(0, frame.Commands.Length).Select(i => "choose:" + i)), "commands retain exact native option positions");
            var fields = frame.Observation!["context"]!["fields"]!.AsArray();
            var projected = fields.Single(f => f!["key"]!.GetValue<string>() == "description")!["value"]?.GetValue<string>();
            Check(projected == (description == "present" ? text!.Text : null), "only existing descriptions are formatted");
            Check(text?.Formats == (description == "present" ? 1 : 0) || text is null, "missing localization is never formatted");
            Check(model.Title.Formats == 1 && router.EventAdapter.Inputs == 0, "title preserved and projection is read-only");
            var counts = router.EventSession!.Read();
            Check(counts.ParentAttempted == 0 && counts.ParentAccepted == 0 && counts.ParentReconciled == 0 && counts.TotalAttempted == 0, "ready projection preserves 0/0/0 accounting");
            router.EventWire!.Dispose();
        }
        {
            var router = new Sts2AgentBridge.Unified.BridgeRouter(false, new RelicModel[] { new MegaCrit.Sts2.Core.Models.Relics.NeowsBones() });
            using var backend = new Sts2AgentBridge.Unified.FullNativeBackend(router, new Sts2AgentBridge.Adapters.Public.PinnedPublicRewardDecisionReader(), router.Choice);
            backend.SetEvent(new AncientEventModel());
            bool rejected = false;
            try { backend.Read(); } catch (Sts2AgentBridge.Unified.FullReadFailure e) { rejected = e.Code == "read_context_failed"; }
            Check(rejected && router.EventAdapter!.Inputs == 0, "unsupported compound pickup still rejects before input");
            router.EventWire!.Dispose();
        }
        foreach (bool titleFailure in new[] { false, true })
        {
            var router = new Sts2AgentBridge.Unified.BridgeRouter(true, Array.Empty<RelicModel>());
            using var backend = new Sts2AgentBridge.Unified.FullNativeBackend(router, new Sts2AgentBridge.Adapters.Public.PinnedPublicRewardDecisionReader(), router.Choice);
            var model = new AncientEventModel { Description = new FixtureText { FormatFails = !titleFailure } };
            model.Title.Present = !titleFailure;
            backend.SetEvent(model);
            bool rejected = false;
            try { backend.Read(); } catch (Sts2AgentBridge.Unified.FullReadFailure e) { rejected = e.Code == "read_context_failed"; }
            Check(rejected && router.EventAdapter!.Inputs == 0, "actual title/description formatting errors still stop before input");
            router.EventWire!.Dispose();
        }
    }
}
