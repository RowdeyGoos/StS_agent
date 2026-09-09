using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using Sts2AgentBridge.Successors.CardSelectionV1;

internal static class Program
{
    private static int _checks;

    public static int Main()
    {
        try
        {
            EventOperationsAtOneAndTwo();
            Throws<ArgumentException>(() => new Fixture(CardSelectionV1Operation.Enchant, 1, 1,
                CardSelectionV1CommitMode.PreviewConfirm).Session(),
                "legacy context cannot admit enchantment without its descriptor");
            CheeseTwoOfEightAuto();
            PreviewModesAndRestGuard();
            InitialAdmissionGuards();
            DomainAndBoundGuards();
            StaleForeignAndRedraw();
            UncertainKthDispatch();
            CompletionAndEffectBoundaries();
            TransformWitnessBoundaries();
            EffectPrefixAndSelectionMonotonicity();
            TaskAndTransientBoundaries();
            MaximumAcceptedSequence();
            PendingBoundAndNoAdoption();
            ReentryOwnerAndDisposal();
            ImmutableCanonicalPublicSurface();
            BoundsAndMalformedCaptures();
            Console.WriteLine("{\"schema_version\":1,\"status\":\"passed\",\"suite\":\"card_selection_v1_core\",\"check_count\":" + _checks + "}");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception.ToString());
            return 1;
        }
    }

    // The original families support these multi-card modes. Enchant uses a
    // separate single-card preview contract exercised by native event fixtures.
    private static void EventOperationsAtOneAndTwo()
    {
        foreach (CardSelectionV1Operation operation in new[] { CardSelectionV1Operation.Add, CardSelectionV1Operation.Remove,
            CardSelectionV1Operation.Upgrade, CardSelectionV1Operation.Transform })
        foreach (int count in new[] { 1, 2 })
        {
            var fixture = new Fixture(operation, count, count,
                CardSelectionV1CommitMode.ExplicitConfirm);
            using var session = fixture.Session();
            for (int slot = 0; slot < count; slot++)
            {
                CardSelectionV1Observation ready = Ready(session.Read());
                Equal(count - slot, ready.LegalActions.Count(a => a.StartsWith("select:", StringComparison.Ordinal)), "remaining select count");
                if (slot == 0 && count == 2) False(ready.LegalActions.Contains("confirm"), "no early exact-two confirm");
                Accepted(session.Apply(ready.DecisionId, "select:" + slot));
                fixture.Selected[slot] = true;
                CardSelectionV1Observation after = Ready(session.Read());
                Equal(slot + 1, after.PriorResults.Count, "select history count");
            }
            CardSelectionV1Observation confirm = Ready(session.Read());
            True(confirm.LegalActions.SequenceEqual(new[] { "confirm" }), "exact confirm action");
            Accepted(session.Apply(confirm.DecisionId, "confirm"));
            fixture.CompleteExact(Enumerable.Range(0, count).ToArray(), effectObserved: true);
            CardSelectionV1ResolvedResult result = Resolved(session.Read());
            Equal(OperationName(operation), result.Operation, "resolved operation");
            Equal(count, result.SelectedCards.Count, "resolved selected count");
            Equal(count + 1, result.PriorResults.Count, "resolved history count");
            Same(result, session.Read(), "resolved terminal stable");
        }
        Pass();
    }

    private static void CheeseTwoOfEightAuto()
    {
        var fixture = new Fixture(CardSelectionV1Operation.Add, 2, 2,
            CardSelectionV1CommitMode.AutoAtMax, candidateCount: 8,
            expectedDomainCount: 8);
        using var session = fixture.Session();
        CardSelectionV1Observation first = Ready(session.Read());
        Equal(8, first.Candidates.Count, "complete cheese domain");
        False(first.LegalActions.Contains("confirm"), "auto mode no confirm");
        Accepted(session.Apply(first.DecisionId, "select:3"));
        fixture.Selected[3] = true;
        CardSelectionV1Observation second = Ready(session.Read());
        Equal(7, second.LegalActions.Count, "seven remaining cheese actions");
        False(second.LegalActions.Contains("confirm"), "no early confirmation");
        Accepted(session.Apply(second.DecisionId, "select:6"));
        fixture.Selected[6] = true;
        fixture.TaskState = CardSelectionV1TaskState.Succeeded;
        fixture.TaskResult = new[] { fixture.Models[6], fixture.Models[3] };
        fixture.SelectorTop = false;
        fixture.SelectorClosed = true;
        fixture.Phase = CardSelectionV1Phase.Submitted;
        fixture.ApplyExactEffect(new[] { 3, 6 });
        fixture.EffectCompletionObserved = true;
        CardSelectionV1ResolvedResult result = Resolved(session.Read());
        True(result.SelectedCards.Select(c => c.Slot).SequenceEqual(new[] { 3, 6 }), "unordered task result canonical slot order");
        Pass();
    }

    private static void PreviewModesAndRestGuard()
    {
        var direct = new Fixture(CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.PreviewConfirm,
            parentKind: CardSelectionV1ParentKind.Rest);
        using (var session = direct.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            direct.Selected[0] = true;
            direct.EnterPreview(new[] { 0 });
            CardSelectionV1Observation preview = Ready(session.Read());
            Equal("preview", preview.Phase, "direct preview phase");
            True(preview.LegalActions.SequenceEqual(new[] { "confirm" }), "preview confirm action");
            Accepted(session.Apply(preview.DecisionId, "confirm"));
            direct.CompleteExact(new[] { 0 }, true);
            Resolved(session.Read());
        }

        var ranged = new Fixture(CardSelectionV1Operation.Transform, 1, 2,
            CardSelectionV1CommitMode.PreviewConfirm, candidateCount: 3);
        using (var session = ranged.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            ranged.Selected[0] = true;
            CardSelectionV1Observation selected = Ready(session.Read());
            True(selected.LegalActions.Contains("preview"), "range preview legal at min");
            Accepted(session.Apply(selected.DecisionId, "preview"));
            ranged.EnterPreview(new[] { 0 });
            CardSelectionV1Observation preview = Ready(session.Read());
            Accepted(session.Apply(preview.DecisionId, "confirm"));
            ranged.CompleteExact(new[] { 0 }, true);
            Resolved(session.Read());
        }

        Throws<ArgumentException>(() => new Fixture(CardSelectionV1Operation.Remove, 1, 1,
            CardSelectionV1CommitMode.PreviewConfirm,
            parentKind: CardSelectionV1ParentKind.Rest).Session(), "rest operation guard");
        Throws<ArgumentException>(() => new Fixture(CardSelectionV1Operation.Upgrade, 1, 2,
            CardSelectionV1CommitMode.PreviewConfirm,
            parentKind: CardSelectionV1ParentKind.Rest).Session(), "rest count guard");
        Throws<ArgumentException>(() => new Fixture(CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.ExplicitConfirm,
            parentKind: CardSelectionV1ParentKind.Rest).Session(), "rest mode guard");
        Pass();
    }

    private static void InitialAdmissionGuards()
    {
        foreach (CardSelectionV1TaskState state in new[] {
            CardSelectionV1TaskState.Succeeded,
            CardSelectionV1TaskState.Canceled,
            CardSelectionV1TaskState.Faulted })
        {
            var fixture = new Fixture(CardSelectionV1Operation.Add, 1, 1,
                CardSelectionV1CommitMode.AutoAtMax) { TaskState = state };
            if (state == CardSelectionV1TaskState.Succeeded)
                fixture.TaskResult = new[] { fixture.Models[0] };
            using var session = fixture.Session();
            Unsupported(session.Read());
            Equal(0, fixture.DispatchCount, "completed task admission dispatch");
        }
        foreach (Action<Fixture> corrupt in new Action<Fixture>[] {
            f => f.Selected[0] = true,
            f => f.PreviewOpen = true,
            f => f.PreviewIdentity = new object(),
            f => f.EffectCompletionObserved = true,
            f => f.SelectionSettled[0] = false })
        {
            var fixture = new Fixture(CardSelectionV1Operation.Add, 1, 1,
                CardSelectionV1CommitMode.AutoAtMax);
            corrupt(fixture);
            using var session = fixture.Session();
            Unsupported(session.Read());
        }
        Pass();
    }

    private static void DomainAndBoundGuards()
    {
        var partial = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax) { CompleteDomain = false };
        using (var session = partial.Session()) Unsupported(session.Read());

        var partialDeck = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax) { CompleteDeck = false };
        using (var session = partialDeck.Session()) Unsupported(session.Read());

        var hidden = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        hidden.Visible[0] = false;
        using (var session = hidden.Session()) Unsupported(session.Read());

        var countMismatch = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        countMismatch.CompleteDomainCount++;
        using (var session = countMismatch.Session()) Unsupported(session.Read());

        var expectedMismatch = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax, candidateCount: 7,
            expectedDomainCount: 8);
        using (var session = expectedMismatch.Session()) Unsupported(session.Read());

        var overflow = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax, candidateCount: 64);
        overflow.ExtraCandidate = true;
        using (var session = overflow.Session()) Unsupported(session.Read());
        Pass();
    }

    private static void StaleForeignAndRedraw()
    {
        foreach (Action<Fixture> mutate in new Action<Fixture>[] {
            f => f.RunIdentity = new object(),
            f => f.ParentReceiptIdentity = new object(),
            f => f.HolderIdentities[0] = new object(),
            f => f.Models[0] = new object(),
            f => f.MinSelect = 2,
            f => f.CompleteDomain = false,
            f => f.CompleteDeck = false,
            f => f.Enabled[0] = false })
        {
            var fixture = new Fixture(CardSelectionV1Operation.Add, 1, 1,
                CardSelectionV1CommitMode.AutoAtMax);
            using var session = fixture.Session();
            CardSelectionV1Observation ready = Ready(session.Read());
            mutate(fixture);
            CardSelectionV1ApplyFailure failure = Failure(session.Apply(ready.DecisionId, "select:0"));
            Equal("unsupported", failure.Outcome, "stale apply unsupported");
            Equal(0, fixture.DispatchCount, "no stale dispatch");
            Unsupported(session.Read());
        }
        Pass();
    }

    private static void UncertainKthDispatch()
    {
        var fixture = new Fixture(CardSelectionV1Operation.Add, 2, 2,
            CardSelectionV1CommitMode.AutoAtMax, candidateCount: 3);
        using var session = fixture.Session();
        CardSelectionV1Observation first = Ready(session.Read());
        Accepted(session.Apply(first.DecisionId, "select:0"));
        fixture.Selected[0] = true;
        CardSelectionV1Observation second = Ready(session.Read());
        fixture.ThrowOnSlot = 1;
        Equal("uncertain", Failure(session.Apply(second.DecisionId, "select:1")).Outcome,
            "second dispatch uncertain");
        Equal(2, fixture.DispatchCount, "two dispatch attempts");
        CardSelectionV1Observation unsupported = Unsupported(session.Read());
        Equal(1, unsupported.PriorResults.Count, "accepted prefix retained");
        Equal("selected", unsupported.PriorResults[0].Result, "prefix result");
        Equal("unsupported", Failure(session.Apply(second.DecisionId, "select:1")).Outcome,
            "no retry after uncertainty");
        Equal(2, fixture.DispatchCount, "no repeated dispatch");
        Pass();
    }

    private static void CompletionAndEffectBoundaries()
    {
        var beforeRemoval = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = beforeRemoval.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            beforeRemoval.Selected[0] = true;
            beforeRemoval.TaskState = CardSelectionV1TaskState.Succeeded;
            beforeRemoval.TaskResult = new[] { beforeRemoval.Models[0] };
            beforeRemoval.ApplyExactEffect(new[] { 0 });
            beforeRemoval.EffectCompletionObserved = false;
            Waiting(session.Read());
            beforeRemoval.SelectorTop = false;
            beforeRemoval.SelectorClosed = true;
            beforeRemoval.Phase = CardSelectionV1Phase.Submitted;
            beforeRemoval.EffectCompletionObserved = true;
            Resolved(session.Read());
        }

        var effectLate = new Fixture(CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = effectLate.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            effectLate.CompleteExact(new[] { 0 }, effectObserved: false);
            Waiting(session.Read());
            effectLate.EffectCompletionObserved = true;
            Resolved(session.Read());
        }

        var foreignAfterFull = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = foreignAfterFull.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            foreignAfterFull.CompleteExact(new[] { 0 }, effectObserved: false);
            Waiting(session.Read());
            foreignAfterFull.Deck.Add(new CardSelectionV1DeckCard(new object(), "Foreign", 0));
            foreignAfterFull.EffectCompletionObserved = true;
            Unsupported(session.Read());
        }

        foreach (CardSelectionV1TaskState bad in new[] {
            CardSelectionV1TaskState.Canceled, CardSelectionV1TaskState.Faulted })
        {
            var fixture = new Fixture(CardSelectionV1Operation.Remove, 1, 1,
                CardSelectionV1CommitMode.AutoAtMax);
            using var session = fixture.Session();
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            fixture.TaskState = bad;
            Unsupported(session.Read());
        }

        var wrong = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = wrong.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            wrong.Selected[0] = true;
            wrong.TaskState = CardSelectionV1TaskState.Succeeded;
            wrong.TaskResult = new[] { new object() };
            Unsupported(session.Read());
        }

        var partialDeckAfterDispatch = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = partialDeckAfterDispatch.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            partialDeckAfterDispatch.CompleteDeck = false;
            Unsupported(session.Read());
            Equal(1, partialDeckAfterDispatch.DispatchCount, "partial current deck no retry");
        }
        Pass();
    }

    private static void TransformWitnessBoundaries()
    {
        var partial = new Fixture(CardSelectionV1Operation.Transform, 2, 2,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = partial.Session())
        {
            SelectPrefix(session, partial, 0);
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:1"));
            partial.Selected[1] = true;
            partial.TaskState = CardSelectionV1TaskState.Succeeded;
            partial.TaskResult = new[] { partial.Models[0], partial.Models[1] };
            partial.SelectorTop = false;
            partial.SelectorClosed = true;
            partial.Phase = CardSelectionV1Phase.Submitted;
            partial.ApplyTransformPrefix(new[] { 0 });
            Waiting(session.Read());
            partial.ApplyExactEffect(new[] { 0, 1 });
            partial.EffectCompletionObserved = true;
            Resolved(session.Read());
        }

        var missingWitness = new Fixture(CardSelectionV1Operation.Transform, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = missingWitness.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            missingWitness.Selected[0] = true;
            missingWitness.TaskState = CardSelectionV1TaskState.Succeeded;
            missingWitness.TaskResult = new[] { missingWitness.Models[0] };
            missingWitness.SelectorTop = false;
            missingWitness.SelectorClosed = true;
            missingWitness.Phase = CardSelectionV1Phase.Submitted;
            missingWitness.Deck[0] = new CardSelectionV1DeckCard(new object(), "Mystery", 0);
            Unsupported(session.Read());
        }
        Pass();
    }

    private static void EffectPrefixAndSelectionMonotonicity()
    {
        foreach (CardSelectionV1Operation operation in new[] { CardSelectionV1Operation.Add, CardSelectionV1Operation.Remove,
            CardSelectionV1Operation.Upgrade, CardSelectionV1Operation.Transform })
        {
            var partial = new Fixture(operation, 2, 2,
                CardSelectionV1CommitMode.AutoAtMax);
            using var session = partial.Session();
            SelectPrefix(session, partial, 0);
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:1"));
            partial.Selected[1] = true;
            partial.TaskState = CardSelectionV1TaskState.Succeeded;
            partial.TaskResult = new[] { partial.Models[0], partial.Models[1] };
            partial.SelectorTop = false;
            partial.SelectorClosed = true;
            partial.Phase = CardSelectionV1Phase.Submitted;
            partial.ApplyEffectPrefix(new[] { 0 });
            Waiting(session.Read());
            partial.ApplyExactEffect(new[] { 0, 1 });
            partial.EffectCompletionObserved = true;
            Resolved(session.Read());
        }

        var regression = new Fixture(CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = regression.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            regression.CompleteExact(new[] { 0 }, effectObserved: false);
            Waiting(session.Read());
            regression.Deck.Clear();
            regression.Deck.AddRange(regression.BaselineDeck);
            Unsupported(session.Read());
        }

        var witnessRegression = new Fixture(CardSelectionV1Operation.Remove, 2, 2,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = witnessRegression.Session())
        {
            SelectPrefix(session, witnessRegression, 0);
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:1"));
            witnessRegression.Selected[1] = true;
            witnessRegression.TaskState = CardSelectionV1TaskState.Succeeded;
            witnessRegression.TaskResult = new[] { witnessRegression.Models[0], witnessRegression.Models[1] };
            witnessRegression.SelectorTop = false;
            witnessRegression.SelectorClosed = true;
            witnessRegression.Phase = CardSelectionV1Phase.Submitted;
            witnessRegression.ApplyEffectPrefix(new[] { 0 });
            witnessRegression.EffectCompletionObserved = true;
            Waiting(session.Read());
            witnessRegression.EffectCompletionObserved = false;
            Unsupported(session.Read());
        }

        var foreignSelection = new Fixture(CardSelectionV1Operation.Add, 1, 2,
            CardSelectionV1CommitMode.ExplicitConfirm, candidateCount: 3);
        using (var session = foreignSelection.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            foreignSelection.Selected[1] = true;
            Unsupported(session.Read());
            foreignSelection.Selected[1] = false;
            foreignSelection.Selected[0] = true;
            Unsupported(session.Read());
        }

        var directPreview = new Fixture(CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.PreviewConfirm,
            parentKind: CardSelectionV1ParentKind.Rest);
        using (var session = directPreview.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            directPreview.EnterPreview(new[] { 0 });
            CardSelectionV1Observation preview = Ready(session.Read());
            Equal("preview", preview.Phase, "preview refs reconcile without intermediate highlight");
        }
        Pass();
    }

    private static void TaskAndTransientBoundaries()
    {
        var transient = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax) { Phase = CardSelectionV1Phase.Transient };
        using (var session = transient.Session())
        {
            Waiting(session.Read());
            transient.Phase = CardSelectionV1Phase.Selecting;
            Ready(session.Read());
            transient.Phase = CardSelectionV1Phase.Transient;
            Waiting(session.Read());
        }

        var completedTransient = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax) {
                Phase = CardSelectionV1Phase.Transient,
                TaskState = CardSelectionV1TaskState.Succeeded
            };
        completedTransient.TaskResult = new[] { completedTransient.Models[0] };
        using (var session = completedTransient.Session()) Unsupported(session.Read());

        var malformedIncomplete = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        malformedIncomplete.TaskResult = new[] { malformedIncomplete.Models[0] };
        using (var session = malformedIncomplete.Session()) Unsupported(session.Read());

        var duplicateResult = new Fixture(CardSelectionV1Operation.Add, 2, 2,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = duplicateResult.Session())
        {
            SelectPrefix(session, duplicateResult, 0);
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:1"));
            duplicateResult.Selected[1] = true;
            duplicateResult.TaskState = CardSelectionV1TaskState.Succeeded;
            duplicateResult.TaskResult = new[] { duplicateResult.Models[0], duplicateResult.Models[0] };
            Unsupported(session.Read());
        }
        Pass();
    }

    private static void MaximumAcceptedSequence()
    {
        var fixture = new Fixture(CardSelectionV1Operation.Upgrade, 1, 8,
            CardSelectionV1CommitMode.PreviewConfirm, candidateCount: 8);
        using var session = fixture.Session();
        for (int slot = 0; slot < 8; slot++)
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:" + slot));
            fixture.Selected[slot] = true;
            Ready(session.Read());
        }
        CardSelectionV1Observation previewReady = Ready(session.Read());
        Accepted(session.Apply(previewReady.DecisionId, "preview"));
        fixture.EnterPreview(Enumerable.Range(0, 8).ToArray());
        CardSelectionV1Observation confirmReady = Ready(session.Read());
        Accepted(session.Apply(confirmReady.DecisionId, "confirm"));
        Equal(10, fixture.DispatchCount, "maximum accepted mutation count");
        fixture.CompleteExact(Enumerable.Range(0, 8).ToArray(), true);
        Resolved(session.Read());
        Pass();
    }

    private static void PendingBoundAndNoAdoption()
    {
        var timeout = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = timeout.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Accepted(session.Apply(ready.DecisionId, "select:0"));
            for (int index = 0; index < CardSelectionV1Limits.MaximumPendingReads; index++)
                Waiting(session.Read());
            Unsupported(session.Read());
            timeout.Selected[0] = true;
            timeout.CompleteExact(new[] { 0 }, true);
            Unsupported(session.Read());
        }

        var aba = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = aba.Session())
        {
            Ready(session.Read());
            aba.Status = CardSelectionV1SurfaceStatus.Missing;
            Unsupported(session.Read());
            aba.Status = CardSelectionV1SurfaceStatus.Available;
            Unsupported(session.Read());
        }
        Pass();
    }

    private static void ReentryOwnerAndDisposal()
    {
        var captureReentry = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = captureReentry.Session())
        {
            captureReentry.CaptureCallback = () => session.Read();
            Unsupported(session.Read());
            Equal(0, captureReentry.DispatchCount, "capture reentry no dispatch");
        }

        var applyReentry = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = applyReentry.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            applyReentry.DispatchCallback = () => session.Apply(ready.DecisionId, "select:0");
            Equal("uncertain", Failure(session.Apply(ready.DecisionId, "select:0")).Outcome,
                "dispatch reentry uncertain");
            Equal(1, applyReentry.DispatchCount, "reentry no second dispatch");
        }

        var offOwner = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = offOwner.Session())
        {
            ICardSelectionV1ReadValue? value = null;
            var thread = new Thread(() => value = session.Read());
            thread.Start(); thread.Join();
            Unsupported(value!);
            Equal(0, offOwner.CaptureCount, "off-owner no capture");
        }

        var disposed = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        var disposedSession = disposed.Session();
        disposedSession.Dispose();
        Unsupported(disposedSession.Read());
        Equal("unsupported", Failure(disposedSession.Apply(new string('a', 64), "select:0")).Outcome,
            "disposed apply");
        Equal(1, disposed.DisposeCount, "adapter disposed once");
        disposedSession.Dispose();
        Equal(1, disposed.DisposeCount, "idempotent dispose");

        var disposeFailure = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax) { ThrowOnDispose = true };
        var failedSession = disposeFailure.Session();
        Throws<InvalidOperationException>(() => failedSession.Dispose(), "dispose failure truthful");
        Throws<InvalidOperationException>(() => failedSession.Dispose(), "dispose failure stable");
        Pass();
    }

    private static void ImmutableCanonicalPublicSurface()
    {
        var fixtureA = new Fixture(CardSelectionV1Operation.Add, 1, 2,
            CardSelectionV1CommitMode.ExplicitConfirm, candidateCount: 2);
        var fixtureB = fixtureA.CloneWithSamePublicValues();
        using var firstSession = fixtureA.Session();
        using var secondSession = fixtureB.Session();
        CardSelectionV1Observation first = Ready(firstSession.Read());
        CardSelectionV1Observation second = Ready(secondSession.Read());
        Equal(first.DecisionId, second.DecisionId, "canonical identity independent of opaque refs");

        Throws<NotSupportedException>(() => ((IList<string>)first.LegalActions).Add("confirm"), "legal actions immutable");
        Throws<NotSupportedException>(() => ((IList<CardSelectionV1Candidate>)first.Candidates).Clear(), "candidates immutable");
        ExactProperties(typeof(CardSelectionV1Candidate), "Enabled", "Key", "Selected", "Slot", "UpgradeLevel", "Visible");
        ExactProperties(typeof(CardSelectionV1ActionResult), "ActionId", "DecisionId", "Result");
        ExactProperties(typeof(CardSelectionV1DispatchReceipt), "ActionId", "DecisionId", "Outcome", "ParentOrdinal", "SessionNonce", "Version");
        ExactProperties(typeof(CardSelectionV1ApplyFailure), "Outcome", "ParentOrdinal", "SessionNonce", "Version");
        ExactProperties(typeof(CardSelectionV1Observation), "Candidates", "CommitMode", "DecisionId", "Enchantment", "LegalActions", "MaxSelect", "MinSelect", "Operation", "ParentOrdinal", "Phase", "PriorResults", "SelectedSlots", "SessionNonce", "Status", "Version");
        ExactProperties(typeof(CardSelectionV1ResolvedResult), "Enchantment", "Operation", "ParentOrdinal", "Phase", "PriorResults", "SelectedCards", "SessionNonce", "Status", "Version");
        ExactProperties(typeof(CardSelectionV1EnchantmentEffect), "Amount", "Key");
        True(first.Enchantment is null, "legacy observations have no enchantment descriptor");
        foreach (Type type in new[] { typeof(CardSelectionV1EnchantmentEffect), typeof(CardSelectionV1Candidate), typeof(CardSelectionV1ActionResult), typeof(CardSelectionV1DispatchReceipt), typeof(CardSelectionV1ApplyFailure), typeof(CardSelectionV1Observation), typeof(CardSelectionV1ResolvedResult) })
            foreach (PropertyInfo property in type.GetProperties(BindingFlags.Instance | BindingFlags.Public))
                False(property.PropertyType == typeof(object), "no opaque public output property");
        Pass();
    }

    private static void BoundsAndMalformedCaptures()
    {
        foreach (string key in new[] { "", new string('A', 129), "bad-key" })
        {
            var fixture = new Fixture(CardSelectionV1Operation.Add, 1, 1,
                CardSelectionV1CommitMode.AutoAtMax);
            fixture.Keys[0] = key;
            using var session = fixture.Session();
            Unsupported(session.Read());
        }
        var key128 = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        key128.Keys[0] = new string('Z', 128);
        using (var session = key128.Session()) Ready(session.Read());

        foreach (Action<Fixture> corrupt in new Action<Fixture>[] {
            f => f.DuplicateModel = true,
            f => f.DuplicateHolder = true,
            f => f.DuplicateSlot = true,
            f => f.NullCandidate = true,
            f => f.NullDeckCard = true,
            f => f.SlotOverride = -1 })
        {
            var fixture = new Fixture(CardSelectionV1Operation.Upgrade, 1, 1,
                CardSelectionV1CommitMode.AutoAtMax, candidateCount: 2);
            corrupt(fixture);
            using var session = fixture.Session();
            Unsupported(session.Read());
        }

        var duplicateKeys = new Fixture(CardSelectionV1Operation.Upgrade, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax, candidateCount: 2);
        duplicateKeys.Keys[1] = duplicateKeys.Keys[0];
        using (var session = duplicateKeys.Session()) Ready(session.Read());

        var malformedAction = new Fixture(CardSelectionV1Operation.Add, 1, 1,
            CardSelectionV1CommitMode.AutoAtMax);
        using (var session = malformedAction.Session())
        {
            CardSelectionV1Observation ready = Ready(session.Read());
            Equal("rejected", Failure(session.Apply(ready.DecisionId, "select:00")).Outcome,
                "noncanonical action rejected");
            Equal(0, malformedAction.DispatchCount, "malformed action no dispatch");
        }
        Pass();
    }

    private static void SelectPrefix(CardSelectionV1Session session, Fixture fixture, int slot)
    {
        CardSelectionV1Observation ready = Ready(session.Read());
        Accepted(session.Apply(ready.DecisionId, "select:" + slot));
        fixture.Selected[slot] = true;
        Ready(session.Read());
    }

    private static CardSelectionV1Observation Ready(ICardSelectionV1ReadValue value)
    {
        var result = value as CardSelectionV1Observation ?? throw new InvalidOperationException("Expected observation.");
        Equal("ready", result.Status, "ready status");
        return result;
    }

    private static CardSelectionV1Observation Waiting(ICardSelectionV1ReadValue value)
    {
        var result = value as CardSelectionV1Observation ?? throw new InvalidOperationException("Expected waiting observation.");
        Equal("waiting", result.Status, "waiting status");
        return result;
    }

    private static CardSelectionV1Observation Unsupported(ICardSelectionV1ReadValue value)
    {
        var result = value as CardSelectionV1Observation ?? throw new InvalidOperationException("Expected unsupported observation.");
        Equal("unsupported", result.Status, "unsupported status");
        return result;
    }

    private static CardSelectionV1ResolvedResult Resolved(ICardSelectionV1ReadValue value) =>
        value as CardSelectionV1ResolvedResult ?? throw new InvalidOperationException("Expected resolved result.");

    private static CardSelectionV1DispatchReceipt Accepted(ICardSelectionV1ApplyValue value)
    {
        var result = value as CardSelectionV1DispatchReceipt ?? throw new InvalidOperationException("Expected accepted receipt.");
        Equal("accepted", result.Outcome, "accepted outcome");
        return result;
    }

    private static CardSelectionV1ApplyFailure Failure(ICardSelectionV1ApplyValue value) =>
        value as CardSelectionV1ApplyFailure ?? throw new InvalidOperationException("Expected apply failure.");

    private static string OperationName(CardSelectionV1Operation value) => value.ToString().ToLowerInvariant();

    private static void ExactProperties(Type type, params string[] names)
    {
        string[] actual = type.GetProperties(BindingFlags.Instance | BindingFlags.Public)
            .Select(p => p.Name).OrderBy(n => n, StringComparer.Ordinal).ToArray();
        string[] expected = names.OrderBy(n => n, StringComparer.Ordinal).ToArray();
        True(actual.SequenceEqual(expected), type.Name + " public property set");
    }

    private static void Pass() => _checks++;
    private static void True(bool value, string message)
    {
        if (!value) throw new InvalidOperationException(message);
    }
    private static void False(bool value, string message) => True(!value, message);
    private static void Equal<T>(T expected, T actual, string message)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException(message + ": expected " + expected + ", got " + actual);
    }
    private static void Same(object expected, object actual, string message)
    {
        if (!ReferenceEquals(expected, actual)) throw new InvalidOperationException(message);
    }
    private static void Throws<T>(Action action, string message) where T : Exception
    {
        try { action(); }
        catch (T) { return; }
        throw new InvalidOperationException(message);
    }

    private sealed class Fixture : ICardSelectionV1NativeAdapter
    {
        private readonly object _player = new();
        private readonly object _room = new();
        private readonly object _map = new();
        private readonly object _option = new();
        private readonly object _controller = new();
        private readonly object _screen = new();
        private readonly object _task = new();
        private readonly object _preview = new();
        private readonly object[] _cardNodes;
        private readonly Action[] _selectDispatches;
        private readonly Action _previewDispatch;
        private readonly Action _confirmDispatch;
        private readonly object _previewControlIdentity = new();
        private readonly object _confirmControlIdentity = new();
        private readonly CardSelectionV1ParentKind _parentKind;
        private readonly CardSelectionV1Operation _operation;
        private readonly CardSelectionV1CommitMode _commitMode;
        private readonly int _expectedDomainCount;
        private bool _capturing;

        public Fixture(
            CardSelectionV1Operation operation,
            int minSelect,
            int maxSelect,
            CardSelectionV1CommitMode commitMode,
            int? candidateCount = null,
            int expectedDomainCount = 0,
            CardSelectionV1ParentKind parentKind = CardSelectionV1ParentKind.Event)
        {
            _operation = operation;
            _commitMode = commitMode;
            _parentKind = parentKind;
            _expectedDomainCount = expectedDomainCount;
            MinSelect = minSelect;
            MaxSelect = maxSelect;
            int count = candidateCount ?? maxSelect;
            Models = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            HolderIdentities = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            _cardNodes = Enumerable.Range(0, count).Select(_ => new object()).ToArray();
            Keys = Enumerable.Range(0, count).Select(i => "Card_" + i).ToArray();
            Selected = new bool[count];
            Visible = Enumerable.Repeat(true, count).ToArray();
            Enabled = Enumerable.Repeat(true, count).ToArray();
            SelectionSettled = Enumerable.Repeat(true, count).ToArray();
            _selectDispatches = new Action[count];
            for (int index = 0; index < count; index++)
            {
                int slot = index;
                _selectDispatches[index] = () =>
                {
                    DispatchCount++;
                    DispatchCallback?.Invoke();
                    if (ThrowOnSlot == slot) throw new InvalidOperationException("dispatch canary");
                };
            }
            _previewDispatch = () => { DispatchCount++; DispatchCallback?.Invoke(); };
            _confirmDispatch = () => { DispatchCount++; DispatchCallback?.Invoke(); };
            RunIdentity = new object();
            ParentReceiptIdentity = new object();
            if (operation == CardSelectionV1Operation.Add)
            {
                Deck.Add(new CardSelectionV1DeckCard(new object(), "Base_A", 0));
                Deck.Add(new CardSelectionV1DeckCard(new object(), "Base_B", 1));
            }
            else
            {
                for (int index = 0; index < count; index++)
                    Deck.Add(new CardSelectionV1DeckCard(Models[index], Keys[index], index % 2));
                Deck.Add(new CardSelectionV1DeckCard(new object(), "Other", 0));
            }
            BaselineDeck = Deck.ToArray();
            CompleteDomainCount = count;
        }

        public object[] Models { get; }
        public object[] HolderIdentities { get; }
        public string[] Keys { get; }
        public bool[] Selected { get; }
        public bool[] Visible { get; }
        public bool[] Enabled { get; }
        public bool[] SelectionSettled { get; }
        public CardSelectionV1DeckCard[] BaselineDeck { get; }
        public List<CardSelectionV1DeckCard> Deck { get; } = new();
        public List<CardSelectionV1Replacement> Replacements { get; } = new();
        public object RunIdentity { get; set; }
        public object ParentReceiptIdentity { get; set; }
        public int MinSelect { get; set; }
        public int MaxSelect { get; set; }
        public CardSelectionV1SurfaceStatus Status { get; set; } = CardSelectionV1SurfaceStatus.Available;
        public CardSelectionV1Phase Phase { get; set; } = CardSelectionV1Phase.Selecting;
        public bool SelectorTop { get; set; } = true;
        public bool SelectorClosed { get; set; }
        public bool PreviewOpen { get; set; }
        public bool CompleteDomain { get; set; } = true;
        public int CompleteDomainCount { get; set; }
        public bool CompleteDeck { get; set; } = true;
        public CardSelectionV1TaskState TaskState { get; set; } = CardSelectionV1TaskState.Incomplete;
        public object[] TaskResult { get; set; } = Array.Empty<object>();
        public object[] PreviewOriginals { get; set; } = Array.Empty<object>();
        public object? PreviewIdentity { get; set; }
        public bool EffectCompletionObserved { get; set; }
        public bool ExtraCandidate { get; set; }
        public bool DuplicateModel { get; set; }
        public bool DuplicateHolder { get; set; }
        public bool DuplicateSlot { get; set; }
        public bool NullCandidate { get; set; }
        public bool NullDeckCard { get; set; }
        public int? SlotOverride { get; set; }
        public int ThrowOnSlot { get; set; } = -1;
        public bool ThrowOnDispose { get; set; }
        public Action? CaptureCallback { get; set; }
        public Action? DispatchCallback { get; set; }
        public int CaptureCount { get; private set; }
        public int DispatchCount { get; private set; }
        public int DisposeCount { get; private set; }

        public CardSelectionV1Session Session()
        {
            var context = new CardSelectionV1ParentContext(
                new string('a', 32), _parentKind, new string('b', 64), "parent:accept",
                ParentReceiptIdentity, RunIdentity, _player, _room, _map, _option, _controller,
                _operation, MinSelect, MaxSelect, _commitMode, _expectedDomainCount);
            return new CardSelectionV1Session(context, this);
        }

        public CardSelectionV1SurfaceCapture CaptureSurface()
        {
            CaptureCount++;
            if (!_capturing && CaptureCallback is not null)
            {
                _capturing = true;
                try { CaptureCallback(); }
                finally { _capturing = false; }
            }
            var candidates = new List<CardSelectionV1NativeCandidate>();
            for (int index = 0; index < Models.Length; index++)
            {
                object model = DuplicateModel && index == 1 ? Models[0] : Models[index];
                object holder = DuplicateHolder && index == 1 ? HolderIdentities[0] : HolderIdentities[index];
                int slot = SlotOverride ?? (DuplicateSlot && index == 1 ? 0 : index);
                candidates.Add(new CardSelectionV1NativeCandidate(
                    slot, Keys[index], holder, model, _cardNodes[index], index % 2,
                    Visible[index], Enabled[index], Selected[index], SelectionSettled[index],
                    _selectDispatches[index]));
            }
            if (NullCandidate) candidates[0] = null!;
            if (ExtraCandidate)
            {
                candidates.Add(new CardSelectionV1NativeCandidate(
                    63, "Overflow", new object(), new object(), new object(), 0,
                    true, true, false, true, () => { }));
            }
            IReadOnlyList<CardSelectionV1DeckCard> deck = Deck;
            if (NullDeckCard)
            {
                var copy = Deck.ToList();
                copy[0] = null!;
                deck = copy;
            }
            var previewControl = new CardSelectionV1NativeControl(
                _previewControlIdentity, true, true, _previewDispatch);
            var confirmControl = new CardSelectionV1NativeControl(
                _confirmControlIdentity, true, true, _confirmDispatch);
            return new CardSelectionV1SurfaceCapture(
                Status, ParentReceiptIdentity, RunIdentity, _player, _room, _map,
                _option, _controller, _screen, _task, PreviewIdentity,
                _parentKind, _operation, MinSelect, MaxSelect, _commitMode, Phase,
                SelectorTop, SelectorClosed, PreviewOpen, CompleteDomain,
                CompleteDomainCount, CompleteDeck, TaskState, EffectCompletionObserved,
                TaskResult, PreviewOriginals, candidates, deck, Replacements,
                previewControl, confirmControl);
        }

        public void EnterPreview(int[] slots)
        {
            Phase = CardSelectionV1Phase.Preview;
            SelectorTop = false;
            SelectorClosed = false;
            PreviewOpen = true;
            PreviewIdentity = _preview;
            PreviewOriginals = slots.Select(slot => Models[slot]).ToArray();
        }

        public void CompleteExact(int[] slots, bool effectObserved)
        {
            foreach (int slot in slots) Selected[slot] = true;
            TaskState = CardSelectionV1TaskState.Succeeded;
            TaskResult = slots.Reverse().Select(slot => Models[slot]).ToArray();
            SelectorTop = false;
            SelectorClosed = true;
            PreviewOpen = false;
            PreviewIdentity = null;
            PreviewOriginals = Array.Empty<object>();
            Phase = CardSelectionV1Phase.Submitted;
            ApplyExactEffect(slots);
            EffectCompletionObserved = effectObserved;
        }

        public void ApplyExactEffect(int[] slots)
        {
            switch (_operation)
            {
                case CardSelectionV1Operation.Add:
                    Deck.Clear();
                    Deck.Add(BaselineDeck[0]);
                    foreach (int slot in slots)
                        Deck.Add(new CardSelectionV1DeckCard(Models[slot], Keys[slot], slot % 2));
                    for (int index = 1; index < BaselineDeck.Length; index++) Deck.Add(BaselineDeck[index]);
                    break;
                case CardSelectionV1Operation.Remove:
                    Deck.Clear();
                    foreach (CardSelectionV1DeckCard card in BaselineDeck)
                        if (!slots.Any(slot => ReferenceEquals(Models[slot], card.ModelIdentity))) Deck.Add(card);
                    break;
                case CardSelectionV1Operation.Upgrade:
                    Deck.Clear();
                    foreach (CardSelectionV1DeckCard card in BaselineDeck)
                    {
                        bool selected = slots.Any(slot => ReferenceEquals(Models[slot], card.ModelIdentity));
                        Deck.Add(new CardSelectionV1DeckCard(card.ModelIdentity, card.StableKey,
                            card.UpgradeLevel + (selected ? 1 : 0)));
                    }
                    break;
                case CardSelectionV1Operation.Transform:
                    ApplyTransformPrefix(slots);
                    break;
            }
        }

        public void ApplyEffectPrefix(int[] slots)
        {
            switch (_operation)
            {
                case CardSelectionV1Operation.Add:
                    Deck.Clear();
                    Deck.Add(BaselineDeck[0]);
                    foreach (int slot in slots)
                        Deck.Add(new CardSelectionV1DeckCard(Models[slot], Keys[slot], slot % 2));
                    for (int index = 1; index < BaselineDeck.Length; index++) Deck.Add(BaselineDeck[index]);
                    break;
                case CardSelectionV1Operation.Remove:
                    Deck.Clear();
                    foreach (CardSelectionV1DeckCard card in BaselineDeck)
                        if (!slots.Any(slot => ReferenceEquals(Models[slot], card.ModelIdentity))) Deck.Add(card);
                    break;
                case CardSelectionV1Operation.Upgrade:
                    Deck.Clear();
                    foreach (CardSelectionV1DeckCard card in BaselineDeck)
                    {
                        bool selected = slots.Any(slot => ReferenceEquals(Models[slot], card.ModelIdentity));
                        Deck.Add(new CardSelectionV1DeckCard(card.ModelIdentity, card.StableKey,
                            card.UpgradeLevel + (selected ? 1 : 0)));
                    }
                    break;
                case CardSelectionV1Operation.Transform:
                    ApplyTransformPrefix(slots);
                    break;
            }
        }

        public void ApplyTransformPrefix(int[] slots)
        {
            Replacements.Clear();
            var byOriginal = new Dictionary<object, CardSelectionV1Replacement>(ReferenceEqualityComparer.Instance);
            foreach (int slot in slots)
            {
                var replacement = new CardSelectionV1Replacement(
                    Models[slot], new object(), "Replacement_" + slot, 0);
                Replacements.Add(replacement);
                byOriginal.Add(Models[slot], replacement);
            }
            Deck.Clear();
            foreach (CardSelectionV1DeckCard card in BaselineDeck)
            {
                if (byOriginal.TryGetValue(card.ModelIdentity, out CardSelectionV1Replacement? replacement))
                    Deck.Add(new CardSelectionV1DeckCard(replacement.ReplacementModelIdentity,
                        replacement.ReplacementStableKey, replacement.ReplacementUpgradeLevel));
                else Deck.Add(card);
            }
        }

        public Fixture CloneWithSamePublicValues()
        {
            var clone = new Fixture(_operation, MinSelect, MaxSelect, _commitMode,
                Models.Length, _expectedDomainCount, _parentKind);
            clone.RunIdentity = new object();
            clone.ParentReceiptIdentity = new object();
            for (int index = 0; index < Keys.Length; index++) clone.Keys[index] = Keys[index];
            return clone;
        }

        public void Dispose()
        {
            DisposeCount++;
            if (ThrowOnDispose) throw new InvalidOperationException("dispose canary");
        }
    }
}
