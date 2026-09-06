using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
using Sts2AgentBridge.Successors.EventOrchestratorV1;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Successors.EventOrchestratorV1.CoreTests;

internal static class Program
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";
    private static int _checks;

    private static int Main()
    {
        try
        {
            Check("ordinary_transition", OrdinaryTransition);
            Check("bound_transient", BoundTransient);
            Check("cheese_child", CheeseChild);
            Check("factory_replacement", FactoryReplacement);
            Check("recapture_binding", RecaptureBinding);
            Check("dispatch_uncertain", DispatchUncertain);
            Check("stable_key_aba", StableKeyAba);
            Check("proceed_exit", ProceedExit);
            Check("four_child_cap", FourChildCap);
            Check("child_cleanup_failure", ChildCleanupFailure);
            Check("reentry", Reentry);
            Check("malformed_capability", MalformedCapability);
            Check("capability_matrix", CapabilityMatrix);
            Check("unsupported_filter", UnsupportedFilter);
            Check("supported_card_requires_child", SupportedCardRequiresChild);
            Check("classification_change", ClassificationChange);
            Check("generic_multi_card", GenericMultiCard);
            Check("domain_canonical_binding", DomainCanonicalBinding);
            Check("catalog_boundary", CatalogBoundary);
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"event_card_operations_v1_core\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch
        {
            Console.WriteLine("{\"schema_version\":1,\"status\":\"failed\",\"suite\":\"event_card_operations_v1_core\",\"check_count\":" + _checks + "}");
            return 1;
        }
    }

    private static void Check(string name, Action test)
    {
        test();
        _checks++;
        GC.KeepAlive(name);
    }

    private static void OrdinaryTransition()
    {
        var f1 = FakeFactory.Item(); var f2 = FakeFactory.Item();
        int dispatch = 0;
        Surface p1 = new("A", f1, () => dispatch++);
        Surface p2 = new("B", f2);
        using var adapter = new FakeAdapter(p1.Parent(), p1.Parent(), p2.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation first = Ready(session.Read());
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(first.DecisionId, "choose:0"));
        EventOrchestratorV1Observation second = Ready(session.Read());
        Require(dispatch == 1 && receipt.ActionId == "choose:0");
        Require(second.PriorResult?.Result == EventOrchestratorV1Limits.OptionTransitionResult);
        Require(second.PriorResult!.DecisionId == receipt.DecisionId && second.Child is null);
    }

    private static void BoundTransient()
    {
        var f1 = FakeFactory.Item(); var f2 = FakeFactory.Item();
        Surface p1 = new("A", f1); Surface p2 = new("B", f2);
        using (var adapter = new FakeAdapter(p1.Parent(), p1.Parent(), p1.Transient(), p2.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation ready = Ready(session.Read());
            Receipt(session.Apply(ready.DecisionId, "choose:0"));
            Require(Observation(session.Read()).Status == "waiting");
            Require(Ready(session.Read()).PriorResult?.Result == "option_transition");
        }
        using (var adapter = new FakeAdapter(p1.Parent(), p1.Parent(), EventOrchestratorV1SurfaceCapture.Missing()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation ready = Ready(session.Read());
            Receipt(session.Apply(ready.DecisionId, "choose:0"));
            Require(Observation(session.Read()).Status == "unsupported");
        }
    }

    private static void CheeseChild()
    {
        FakeFactory cheese = FakeFactory.Cheese(); FakeFactory next = FakeFactory.Item();
        Surface p1 = new("ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE", cheese);
        Surface p2 = new("NEXT", next);
        object screen = new();
        using var adapter = new FakeAdapter(p1.Parent(), p1.Parent(), p1.Child(screen), p2.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(ready.DecisionId, "choose:0"));
        EventOrchestratorV1Observation child = Observation(session.Read());
        Require(child.Status == "child" && child.Child?.Kind == "card_selection");
        Require(child.Child!.ChildOrdinal == 1 && cheese.Calls == 1);
        Require(ReferenceEquals(cheese.Accepted?.ParentReceipt, receipt));
        cheese.Broker!.Current = EventOrchestratorV1ChildStatus.Resolved;
        EventOrchestratorV1Observation after = Ready(session.Read());
        Require(after.PriorResult?.Result == "child_completed");
        Require(after.PriorResult!.Child?.ChildOrdinal == 1 && cheese.Broker.Disposed);
    }

    private static void FactoryReplacement()
    {
        EventOrchestratorV1ChildPolicy policy = EventOrchestratorV1ChildPolicy.ItemReward();
        var expected = new FakeFactory(policy); var foreign = new FakeFactory(policy);
        Surface p = new("A", expected);
        using var adapter = new FakeAdapter(p.Parent(), p.Parent(), p.Child(new object(), foreign));
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "unsupported");
        Require(expected.Calls == 0 && foreign.Calls == 0);
    }

    private static void RecaptureBinding()
    {
        EventOrchestratorV1ChildPolicy policy = EventOrchestratorV1ChildPolicy.ItemReward();
        var f1 = new FakeFactory(policy); var f2 = new FakeFactory(policy);
        Surface first = new("A", f1); Surface changed = new("A", f2,
            button: first.Button, option: first.Option, controller: first.Controller);
        using var adapter = new FakeAdapter(first.Parent(), changed.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        RoomFlowApplyFailure failure = Failure(session.Apply(ready.DecisionId, "choose:0"));
        Require(failure.Outcome == "unsupported" && first.DispatchCount == 0);
    }

    private static void DispatchUncertain()
    {
        var factory = FakeFactory.Item();
        Surface p = new("A", factory, () => throw new InvalidOperationException());
        using var adapter = new FakeAdapter(p.Parent(), p.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Require(Failure(session.Apply(ready.DecisionId, "choose:0")).Outcome == "uncertain");
        Require(factory.Calls == 0 && session.ReservedDispatchCount == 1);
        Require(Failure(session.Apply(ready.DecisionId, "choose:0")).Outcome == "rejected");
    }

    private static void StableKeyAba()
    {
        Surface a = new("A", FakeFactory.Item()); Surface b = new("B", FakeFactory.Item());
        Surface again = new("A", FakeFactory.Item());
        using var adapter = new FakeAdapter(a.Parent(), a.Parent(), b.Parent(), b.Parent(), again.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation first = Ready(session.Read());
        Receipt(session.Apply(first.DecisionId, "choose:0"));
        EventOrchestratorV1Observation second = Ready(session.Read());
        Receipt(session.Apply(second.DecisionId, "choose:0"));
        EventOrchestratorV1Observation final = Observation(session.Read());
        Require(final.Status == "waiting" && final.LegalActions.Count == 0);
    }

    private static void ProceedExit()
    {
        Surface proceed = Surface.Proceed();
        using var adapter = new FakeAdapter(proceed.Parent(), proceed.Parent());
        adapter.Exits.Enqueue(new EventOrchestratorV1ExitCapture(
            Surface.Run, Surface.Player, Surface.Room, Surface.Map, false, false, false));
        adapter.Exits.Enqueue(new EventOrchestratorV1ExitCapture(
            Surface.Run, Surface.Player, Surface.Room, Surface.Map, true, true, false));
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        RoomFlowDispatchReceipt receipt = Receipt(session.Apply(ready.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "waiting");
        var resolved = (EventOrchestratorV1ResolvedResult)session.Read();
        Require(resolved.Result == "map_handoff" && resolved.DecisionId == receipt.DecisionId);
        Require(resolved.PriorResult?.Result == "map_handoff");
    }

    private static void FourChildCap()
    {
        var factories = new FakeFactory[5]; var surfaces = new Surface[5];
        var captures = new List<EventOrchestratorV1SurfaceCapture>();
        for (int i = 0; i < 5; i++)
        {
            factories[i] = FakeFactory.Item();
            surfaces[i] = new Surface("K" + i, factories[i]);
            captures.Add(surfaces[i].Parent());
            captures.Add(surfaces[i].Parent());
            captures.Add(surfaces[i].Child(new object()));
        }
        using var adapter = new FakeAdapter(captures.ToArray());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation current = Ready(session.Read());
        for (int i = 0; i < 4; i++)
        {
            Receipt(session.Apply(current.DecisionId, "choose:0"));
            Require(Observation(session.Read()).Status == "child");
            factories[i].Broker!.Current = EventOrchestratorV1ChildStatus.Resolved;
            current = Ready(session.Read());
        }
        Receipt(session.Apply(current.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "unsupported");
        Require(session.ChildEpisodeCount == 4 && factories[4].Calls == 0);
    }

    private static void ChildCleanupFailure()
    {
        FakeFactory f = FakeFactory.Item(); f.ThrowDispose = true;
        Surface p = new("A", f); Surface after = new("B", FakeFactory.Item());
        using var adapter = new FakeAdapter(p.Parent(), p.Parent(), p.Child(new object()), after.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "child");
        f.Broker!.Current = EventOrchestratorV1ChildStatus.Resolved;
        Require(Observation(session.Read()).Status == "unsupported");
    }

    private static void Reentry()
    {
        FakeFactory f = FakeFactory.Item();
        EventOrchestratorV1Session? session = null;
        Surface p = new("A", f, () => { _ = session!.Read(); });
        using var adapter = new FakeAdapter(p.Parent(), p.Parent());
        using (session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation ready = Ready(session.Read());
            Require(Failure(session.Apply(ready.DecisionId, "choose:0")).Outcome == "uncertain");
            Require(session.ReservedDispatchCount == 1);
        }
    }

    private static void MalformedCapability()
    {
        FakeFactory cheese = FakeFactory.Cheese();
        Surface wrong = new("ORDINARY", cheese);
        using (var adapter = new FakeAdapter(wrong.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
            Require(Observation(session.Read()).Status == "unsupported");

        Surface none = new("ORDINARY", null);
        using (var adapter = new FakeAdapter(none.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
            Require(Observation(session.Read()).Status == "unsupported");
    }

    private static void CapabilityMatrix()
    {
        FakeFactory item = FakeFactory.Item();
        FakeFactory card = FakeFactory.Card("REMOVE_TWO", "remove_two",
            CardSelectionV1Operation.Remove, 2, 2,
            CardSelectionV1CommitMode.PreviewConfirm,
            EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 4, 8, 5);
        ExpectUnsupported(new Surface("PROCEED", null, proceed: true,
            capability: EventOrchestratorV1CapabilityKind.Proceed, domainCount: 1));
        ExpectUnsupported(new Surface("ITEM", item,
            capability: EventOrchestratorV1CapabilityKind.OrdinaryItemEligible,
            domainCount: 1));
        ExpectUnsupported(new Surface("WRONG_KEY", card,
            capability: EventOrchestratorV1CapabilityKind.SupportedCardSelection));
        ExpectUnsupported(new Surface("REMOVE_TWO", null,
            capability: EventOrchestratorV1CapabilityKind.SupportedCardSelection,
            domainCount: 5));
        ExpectUnsupported(new Surface("ITEM", item,
            capability: EventOrchestratorV1CapabilityKind.UnsupportedCardSelection));
        ExpectUnsupported(new Surface("ITEM", item,
            capability: (EventOrchestratorV1CapabilityKind)999));
        ExpectUnsupported(new Surface("REMOVE_TWO", card,
            capability: EventOrchestratorV1CapabilityKind.SupportedCardSelection,
            domainCount: 4));
        ExpectUnsupported(new Surface("REMOVE_TWO", card,
            capability: EventOrchestratorV1CapabilityKind.OrdinaryItemEligible,
            domainCount: 0));
    }

    private static void UnsupportedFilter()
    {
        Surface unsupported = new("KNOWN_CARD", null,
            capability: EventOrchestratorV1CapabilityKind.UnsupportedCardSelection);
        using (var adapter = new FakeAdapter(unsupported.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation value = Observation(session.Read());
            Require(value.Status == "unsupported" && unsupported.DispatchCount == 0);
        }

        Surface supported = new("ORDINARY", FakeFactory.Item());
        EventOrchestratorV1SurfaceCapture mixed = Surface.Parent(unsupported, supported);
        using (var adapter = new FakeAdapter(mixed, mixed))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation value = Ready(session.Read());
            Require(value.Candidates.Count == 2 && value.LegalActions.Count == 1 &&
                value.LegalActions[0] == "choose:1");
            Require(value.Candidates[0].Enabled &&
                value.Candidates[0].ChildPolicy ==
                    EventOrchestratorV1Limits.UnsupportedCardPolicy &&
                value.Candidates[0].ChildDomainCount == 0);
            Require(Failure(session.Apply(value.DecisionId, "choose:0")).Outcome ==
                "rejected");
            Receipt(session.Apply(value.DecisionId, "choose:1"));
            Require(unsupported.DispatchCount == 0 && supported.DispatchCount == 1);
        }

        foreach (Surface blocked in new[]
        {
            new Surface("DISABLED_CARD", null,
                capability: EventOrchestratorV1CapabilityKind.UnsupportedCardSelection,
                enabled: false),
            new Surface("LOCKED_CARD", null,
                capability: EventOrchestratorV1CapabilityKind.UnsupportedCardSelection,
                locked: true),
            new Surface("DANGEROUS_CARD", null,
                capability: EventOrchestratorV1CapabilityKind.UnsupportedCardSelection,
                dangerous: true),
        })
        {
            using var adapter = new FakeAdapter(blocked.Parent());
            using var session = new EventOrchestratorV1Session(Nonce, adapter);
            Require(Observation(session.Read()).Status == "unsupported" &&
                blocked.DispatchCount == 0);
        }
    }

    private static void SupportedCardRequiresChild()
    {
        FakeFactory card = FakeFactory.Card("REMOVE_ONE", "remove_one",
            CardSelectionV1Operation.Remove, 1, 1,
            CardSelectionV1CommitMode.PreviewConfirm,
            EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 1, 8, 4);
        Surface first = new("REMOVE_ONE", card);
        Surface changed = new("AFTER", FakeFactory.Item());
        using var adapter = new FakeAdapter(
            first.Parent(), first.Parent(), changed.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Receipt(session.Apply(ready.DecisionId, "choose:0"));
        Require(Observation(session.Read()).Status == "unsupported" &&
            card.Calls == 0 && first.DispatchCount == 1);
    }

    private static void GenericMultiCard()
    {
        FakeFactory factory = FakeFactory.Card("REMOVE_THREE", "remove_three",
            CardSelectionV1Operation.Remove, 2, 3,
            CardSelectionV1CommitMode.PreviewConfirm,
            EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 3, 16, 7);
        Surface first = new("REMOVE_THREE", factory);
        Surface after = new("AFTER", FakeFactory.Item());
        object screen = new();
        using var adapter = new FakeAdapter(
            first.Parent(), first.Parent(), first.Child(screen), after.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Require(ready.Candidates[0].ChildPolicy == "remove_three" &&
            ready.Candidates[0].ChildDomainCount == 7);
        RoomFlowDispatchReceipt receipt = Receipt(
            session.Apply(ready.DecisionId, "choose:0"));
        EventOrchestratorV1Observation child = Observation(session.Read());
        Require(child.Status == "child" && child.Child?.Kind == "card_selection" &&
            factory.Calls == 1 &&
            ReferenceEquals(factory.Accepted?.ChildPolicy, factory.Policy));
        factory.Broker!.Current = EventOrchestratorV1ChildStatus.Resolved;
        EventOrchestratorV1Observation next = Ready(session.Read());
        Require(next.PriorResult?.DecisionId == receipt.DecisionId &&
            next.PriorResult.Result == EventOrchestratorV1Limits.ChildCompletedResult);
    }

    private static void ClassificationChange()
    {
        Surface first = new("KNOWN", FakeFactory.Item());
        Surface changed = new("KNOWN", null,
            button: first.Button, option: first.Option,
            controller: first.Controller,
            capability: EventOrchestratorV1CapabilityKind.UnsupportedCardSelection);
        using var adapter = new FakeAdapter(first.Parent(), changed.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        EventOrchestratorV1Observation ready = Ready(session.Read());
        Require(Failure(session.Apply(ready.DecisionId, "choose:0")).Outcome ==
            "unsupported");
        Require(first.DispatchCount == 0 && changed.DispatchCount == 0 &&
            session.ReservedDispatchCount == 0);
    }

    private static void DomainCanonicalBinding()
    {
        EventOrchestratorV1CardPolicyDefinition definition =
            EventOrchestratorV1CardPolicyDefinition.CreateForTests(
                "upgrade_many", "UPGRADE_MANY", CardSelectionV1Operation.Upgrade,
                1, 3, CardSelectionV1CommitMode.PreviewConfirm,
                EventOrchestratorV1CardDomainSource.ExistingDeckOriginals, 4, 8);
        FakeFactory four = new(definition.Bind(4));
        FakeFactory five = new(definition.Bind(5));
        Surface s4 = new("UPGRADE_MANY", four);
        Surface s5 = new("UPGRADE_MANY", five,
            button: s4.Button, option: s4.Option, controller: s4.Controller);
        string id4;
        using (var adapter = new FakeAdapter(s4.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
            id4 = Ready(session.Read()).DecisionId;
        string id5;
        using (var adapter = new FakeAdapter(s5.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
            id5 = Ready(session.Read()).DecisionId;
        Require(id4 ==
            "7d5f36104237366b59b8ed6e53f83f458017eef8f0a663f4b1fa25445e932adf" &&
            id4 != id5);

        using (var adapter = new FakeAdapter(s4.Parent(), s5.Parent()))
        using (var session = new EventOrchestratorV1Session(Nonce, adapter))
        {
            EventOrchestratorV1Observation ready = Ready(session.Read());
            Require(Failure(session.Apply(ready.DecisionId, "choose:0")).Outcome ==
                "unsupported");
            Require(s4.DispatchCount == 0 && s5.DispatchCount == 0);
        }
    }

    private static void CatalogBoundary()
    {
        Require(EventOrchestratorV1CardPolicyCatalog.Definitions.Count == 3);
        Require(EventOrchestratorV1CardPolicyCatalog.TryGet(
            EventOrchestratorV1Limits.CheeseGorgeAddTwoPolicy,
            out EventOrchestratorV1CardPolicyDefinition? row) && row is not null);
        Require(row!.ParentStableId ==
            "ROOM_FULL_OF_CHEESE.pages.INITIAL.options.GORGE");
        Require(EventOrchestratorV1CardPolicyCatalog.TryGet(
            "aroma_maintain_control_upgrade_one",
            out EventOrchestratorV1CardPolicyDefinition? aroma) && aroma is not null &&
            aroma.ParentStableId ==
                "AROMA_OF_CHAOS.pages.INITIAL.options.MAINTAIN_CONTROL" &&
            aroma.Operation == CardSelectionV1Operation.Upgrade &&
            aroma.MinSelect == 1 && aroma.MaxSelect == 1 &&
            aroma.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
            aroma.MinimumDomainCount == 2 && aroma.MaximumDomainCount == 64);
        Require(EventOrchestratorV1CardPolicyCatalog.TryGet(
            "sapphire_eat_upgrade_one",
            out EventOrchestratorV1CardPolicyDefinition? sapphire) &&
            sapphire is not null && sapphire.ParentStableId ==
                "SAPPHIRE_SEED.pages.INITIAL.options.EAT" &&
            sapphire.Operation == CardSelectionV1Operation.Upgrade &&
            sapphire.DomainSource ==
                EventOrchestratorV1CardDomainSource.ExistingDeckOriginals);
        Require(!EventOrchestratorV1CardPolicyCatalog.TryGet(
            "remove_three", out EventOrchestratorV1CardPolicyDefinition? missing) &&
            missing is null);
        bool immutable = false;
        try
        {
            ((IList<EventOrchestratorV1CardPolicyDefinition>)
                EventOrchestratorV1CardPolicyCatalog.Definitions)[0] = row;
        }
        catch (NotSupportedException) { immutable = true; }
        Require(immutable);
        bool rejected = false;
        try
        {
            _ = EventOrchestratorV1CardPolicyDefinition.CreateForTests(
                "bad-policy", "BAD", CardSelectionV1Operation.Add, 1, 1,
                CardSelectionV1CommitMode.AutoAtMax,
                EventOrchestratorV1CardDomainSource.GeneratedAtAdmission, 1, 1);
        }
        catch (ArgumentException) { rejected = true; }
        Require(rejected);
    }

    private static void ExpectUnsupported(Surface surface)
    {
        using var adapter = new FakeAdapter(surface.Parent());
        using var session = new EventOrchestratorV1Session(Nonce, adapter);
        Require(Observation(session.Read()).Status == "unsupported" &&
            surface.DispatchCount == 0);
    }

    private static EventOrchestratorV1Observation Observation(IRoomFlowReadValue value) =>
        value as EventOrchestratorV1Observation ?? throw new InvalidOperationException();
    private static EventOrchestratorV1Observation Ready(IRoomFlowReadValue value)
    {
        EventOrchestratorV1Observation result = Observation(value);
        Require(result.Status == "ready");
        return result;
    }
    private static RoomFlowDispatchReceipt Receipt(IRoomFlowApplyValue value) =>
        value as RoomFlowDispatchReceipt ?? throw new InvalidOperationException();
    private static RoomFlowApplyFailure Failure(IRoomFlowApplyValue value) =>
        value as RoomFlowApplyFailure ?? throw new InvalidOperationException();
    private static void Require(bool value)
    {
        if (!value) throw new InvalidOperationException();
    }

    private sealed class FakeAdapter : IEventOrchestratorV1NativeAdapter
    {
        private readonly Queue<EventOrchestratorV1SurfaceCapture> _captures;
        internal readonly Queue<EventOrchestratorV1ExitCapture> Exits = new();
        internal FakeAdapter(params EventOrchestratorV1SurfaceCapture[] captures) =>
            _captures = new Queue<EventOrchestratorV1SurfaceCapture>(captures);
        public EventOrchestratorV1SurfaceCapture CaptureSurface() => _captures.Dequeue();
        public EventOrchestratorV1ExitCapture CaptureExit(EventOrchestratorV1ExitProbe pending) => Exits.Dequeue();
        public void Dispose() { }
    }

    private sealed class Surface
    {
        internal static readonly object Run = new();
        internal static readonly object Player = new();
        internal static readonly object Room = new();
        internal static readonly object Map = new();
        internal static readonly object Event = new();
        internal readonly object Button;
        internal readonly object Option;
        internal readonly object Controller;
        internal readonly string Key;
        internal readonly FakeFactory? Factory;
        internal readonly bool IsProceed;
        internal readonly EventOrchestratorV1CapabilityKind Capability;
        internal readonly int DomainCount;
        internal readonly bool Visible;
        internal readonly bool Enabled;
        internal readonly bool Locked;
        internal readonly bool Dangerous;
        private readonly Action? _dispatch;
        internal int DispatchCount;

        internal Surface(string key, FakeFactory? factory, Action? dispatch = null,
            object? button = null, object? option = null, object? controller = null,
            bool proceed = false,
            EventOrchestratorV1CapabilityKind? capability = null,
            int? domainCount = null,
            bool visible = true,
            bool enabled = true,
            bool locked = false,
            bool dangerous = false)
        {
            Key = key; Factory = factory; _dispatch = dispatch; IsProceed = proceed;
            Capability = capability ?? (proceed
                ? EventOrchestratorV1CapabilityKind.Proceed
                : factory?.Policy.ChildKind == EventOrchestratorV1ChildKind.CardSelection
                    ? EventOrchestratorV1CapabilityKind.SupportedCardSelection
                    : EventOrchestratorV1CapabilityKind.OrdinaryItemEligible);
            DomainCount = domainCount ??
                (Capability == EventOrchestratorV1CapabilityKind.SupportedCardSelection
                    ? factory?.Policy.ExpectedDomainCount ?? 0 : 0);
            Visible = visible; Enabled = enabled; Locked = locked; Dangerous = dangerous;
            Button = button ?? new object(); Option = option ?? new object(); Controller = controller ?? new object();
        }

        internal static Surface Proceed() => new("PROCEED", null, proceed: true);

        internal EventOrchestratorV1SurfaceCapture Parent()
        {
            return EventOrchestratorV1SurfaceCapture.Parent(
                Run, Player, Room, Map, Event, IsProceed, false, false, false,
                new[] { Candidate(0) });
        }

        internal static EventOrchestratorV1SurfaceCapture Parent(params Surface[] surfaces)
        {
            var candidates = new EventOrchestratorV1NativeCandidate[surfaces.Length];
            for (int index = 0; index < surfaces.Length; index++)
                candidates[index] = surfaces[index].Candidate(index);
            return EventOrchestratorV1SurfaceCapture.Parent(
                Run, Player, Room, Map, Event, false, false, false, false,
                candidates);
        }

        private EventOrchestratorV1NativeCandidate Candidate(int index) => new(
            index, Key, "text", Visible, Enabled, Locked, Dangerous, IsProceed,
            Button, Option, Controller,
            () => { DispatchCount++; _dispatch?.Invoke(); },
            Capability, DomainCount, Factory?.Policy, Factory);

        internal EventOrchestratorV1SurfaceCapture Child(object screen, FakeFactory? factory = null)
        {
            FakeFactory exact = factory ?? Factory ?? throw new InvalidOperationException();
            return EventOrchestratorV1SurfaceCapture.Child(
                Run, Player, Room, Map, Event, screen, exact.Policy, exact);
        }

        internal EventOrchestratorV1SurfaceCapture Transient() =>
            EventOrchestratorV1SurfaceCapture.Transient(Run, Player, Room, Map, Event);
    }

    private sealed class FakeFactory : IEventOrchestratorV1ChildFactory
    {
        internal FakeFactory(EventOrchestratorV1ChildPolicy policy) => Policy = policy;
        internal static FakeFactory Item() => new(EventOrchestratorV1ChildPolicy.ItemReward());
        internal static FakeFactory Cheese() => new(EventOrchestratorV1ChildPolicy.CheeseGorgeAddTwo());
        internal static FakeFactory Card(
            string stableId,
            string policyId,
            CardSelectionV1Operation operation,
            int minSelect,
            int maxSelect,
            CardSelectionV1CommitMode commitMode,
            EventOrchestratorV1CardDomainSource domainSource,
            int minimumDomainCount,
            int maximumDomainCount,
            int expectedDomainCount)
        {
            EventOrchestratorV1CardPolicyDefinition definition =
                EventOrchestratorV1CardPolicyDefinition.CreateForTests(
                    policyId, stableId, operation, minSelect, maxSelect,
                    commitMode, domainSource, minimumDomainCount,
                    maximumDomainCount);
            return new FakeFactory(definition.Bind(expectedDomainCount));
        }
        public EventOrchestratorV1ChildPolicy Policy { get; }
        internal int Calls;
        internal EventOrchestratorV1AcceptedContext? Accepted;
        internal FakeBroker? Broker;
        internal bool ThrowDispose;
        public IEventOrchestratorV1ChildBroker Create(
            EventOrchestratorV1AcceptedContext acceptedContext,
            EventOrchestratorV1ChildCorrelation correlation,
            object exactForegroundIdentity)
        {
            Calls++; Accepted = acceptedContext;
            Broker = Policy.ChildKind == EventOrchestratorV1ChildKind.Item
                ? new FakeItemBroker(correlation, ThrowDispose)
                : new FakeCardBroker(correlation, ThrowDispose);
            return Broker;
        }
    }

    private abstract class FakeBroker : IEventOrchestratorV1ChildBroker
    {
        private int _disposeFailures;
        internal FakeBroker(EventOrchestratorV1ChildCorrelation correlation,
            bool throwDispose)
        { Correlation = correlation; _disposeFailures = throwDispose ? 1 : 0; }
        public EventOrchestratorV1ChildCorrelation Correlation { get; }
        internal EventOrchestratorV1ChildStatus Current = EventOrchestratorV1ChildStatus.Active;
        public EventOrchestratorV1ChildStatus Status => Current;
        internal bool Disposed;
        public void Dispose()
        {
            Disposed = true;
            if (_disposeFailures-- > 0) throw new InvalidOperationException();
        }
    }

    private sealed class FakeItemBroker : FakeBroker, IEventOrchestratorV1ItemChildBroker
    {
        internal FakeItemBroker(EventOrchestratorV1ChildCorrelation correlation, bool fail) : base(correlation, fail) { }
        Sts2AgentBridge.Successors.ItemV1.IItemV1ReadValue IEventOrchestratorV1ItemChildBroker.Read() => throw new NotSupportedException();
        Sts2AgentBridge.Successors.ItemV1.IItemV1ApplyValue IEventOrchestratorV1ItemChildBroker.Apply(string? d, string? a) => throw new NotSupportedException();
    }

    private sealed class FakeCardBroker : FakeBroker, IEventOrchestratorV1CardChildBroker
    {
        internal FakeCardBroker(EventOrchestratorV1ChildCorrelation correlation, bool fail) : base(correlation, fail) { }
        Sts2AgentBridge.Successors.CardSelectionV1.ICardSelectionV1ReadValue IEventOrchestratorV1CardChildBroker.Read() => throw new NotSupportedException();
        Sts2AgentBridge.Successors.CardSelectionV1.ICardSelectionV1ApplyValue IEventOrchestratorV1CardChildBroker.Apply(string? d, string? a) => throw new NotSupportedException();
    }
}
