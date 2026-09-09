using System;
using System.Collections.Generic;
using System.Linq;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.CardTransformV2;

public sealed partial class CardTransformV2Session
{
    private static CardTransformV2EffectWitness EmptyJournal() => new(
        Array.Empty<CardTransformV2CommandWitness>(), Array.Empty<object>(), Array.Empty<CardTransformV2Insertion>());
    private CardTransformV2EffectWitness _captureJournal = EmptyJournal();
    private CardTransformV2EffectWitness _validatedJournal = EmptyJournal();

    private static T[] Bounded<T>(IReadOnlyList<T> source)
    {
        if (source is null) throw new InvalidOperationException("Missing transform journal collection.");
        var copy = new List<T>();
        foreach (T item in source)
        {
            if (copy.Count == 8 || item is null) throw new InvalidOperationException("Invalid transform journal collection.");
            copy.Add(item);
        }
        return copy.ToArray();
    }
    private CardSelectionV1SurfaceCapture CaptureTransform()
    {
        CardTransformV2SurfaceCapture capture = _adapter.CaptureSurface();
        if (capture is null || capture.Surface is null || capture.Effect is null || capture.Surface.Replacements.Count != 0)
            throw new InvalidOperationException("Invalid transform surface.");
        var commands = Bounded(capture.Effect.Commands).Select(c => new CardTransformV2CommandWitness(
            c.CommandIdentity, Bounded(c.OriginalIdentities), c.State, c.AllOriginalsRemoved,
            Bounded(c.Insertions), Bounded(c.CompletedResults))).ToArray();
        _captureJournal = new(commands, Bounded(capture.Effect.RemovedOriginals), Bounded(capture.Effect.OrderedCommittedInsertions));
        if (!_awaitingCommit && _pending?.Kind != ActionKind.Confirm &&
            (commands.Length != 0 || _captureJournal.RemovedOriginals.Count != 0 || _captureJournal.OrderedCommittedInsertions.Count != 0))
            throw new InvalidOperationException("Transform effects before Confirm.");
        return capture.Surface;
    }

    private bool ValidateTransformJournal(CardSelectionV1SurfaceCapture capture, object[] selected, out bool complete)
    {
        complete = false;
        if (_bound is null || capture.Replacements.Count != 0) return false;
        var journal = _captureJournal;
        if (journal.Commands.Count > (selected.Length==0 && _context.AllowOptionalSelection ? 1 : selected.Length) || journal.Commands.Count < _validatedJournal.Commands.Count) return false;
        var identities = new HashSet<object>(ReferenceComparer.Instance);
        var originals = new HashSet<object>(ReferenceComparer.Instance);
        var removed = new HashSet<object>(ReferenceComparer.Instance);
        var insertedOriginals = new HashSet<object>(ReferenceComparer.Instance);
        var finals = new HashSet<object>(ReferenceComparer.Instance);
        var insertions = new List<CardTransformV2Insertion>();
        for (int i = 0; i < journal.Commands.Count; i++)
        {
            var c = journal.Commands[i];
            if (c.CommandIdentity is null || !identities.Add(c.CommandIdentity) || !Enum.IsDefined(c.State) ||
                c.OriginalIdentities.Count == 0 && !(_context.AllowOptionalSelection && selected.Length==0) || c.OriginalIdentities.Count > selected.Length ||
                i > 0 && journal.Commands[i-1].State != CardTransformV2CommandState.Succeeded) return false;
            var domain = new HashSet<object>(ReferenceComparer.Instance);
            foreach (object original in c.OriginalIdentities)
            {
                if (original is null || !ContainsReference(selected, original) || !originals.Add(original) || !domain.Add(original)) return false;
                if (c.AllOriginalsRemoved) removed.Add(original);
            }
            if (c.Insertions.Count > domain.Count || c.CompletedResults.Count > domain.Count ||
                c.Insertions.Count > 0 && !c.AllOriginalsRemoved) return false;
            if (c.State is CardTransformV2CommandState.Canceled or CardTransformV2CommandState.Faulted) return false;
            if (c.State == CardTransformV2CommandState.NotStarted &&
                (c.AllOriginalsRemoved || c.Insertions.Count != 0 || c.CompletedResults.Count != 0)) return false;
            if (c.State == CardTransformV2CommandState.Running && c.CompletedResults.Count != 0) return false;
            foreach (var row in c.Insertions)
            {
                if (row.OriginalIdentity is null || row.FinalIdentity is null || row.Ordinal != insertions.Count + 1 ||
                    !domain.Contains(row.OriginalIdentity) || !insertedOriginals.Add(row.OriginalIdentity) ||
                    !finals.Add(row.FinalIdentity) || FindDeckCard(_bound.BaselineDeck, row.FinalIdentity) is not null ||
                    !CardTransformV2Identity.IsStableKey(row.FinalStableKey) || row.FinalUpgradeLevel < 0) return false;
                insertions.Add(row);
            }
            if (c.State == CardTransformV2CommandState.Succeeded)
            {
                if (!c.AllOriginalsRemoved || c.Insertions.Count != domain.Count || c.CompletedResults.Count != domain.Count) return false;
                for (int j = 0; j < c.CompletedResults.Count; j++)
                    if (!c.CompletedResults[j].Success || !ReferenceEquals(c.CompletedResults[j].FinalIdentity, c.Insertions[j].FinalIdentity)) return false;
            }
            if (i < _validatedJournal.Commands.Count && !Advances(_validatedJournal.Commands[i], c)) return false;
        }
        if (originals.Count > selected.Length || insertions.Count > selected.Length ||
            journal.RemovedOriginals.Count != removed.Count || journal.OrderedCommittedInsertions.Count != insertions.Count) return false;
        var declaredRemoved = new HashSet<object>(ReferenceComparer.Instance);
        foreach (object original in journal.RemovedOriginals)
            if (original is null || !declaredRemoved.Add(original) || !removed.Contains(original)) return false;
        for (int i = 0; i < insertions.Count; i++)
            if (!SameInsertion(insertions[i], journal.OrderedCommittedInsertions[i])) return false;
        foreach (object original in _validatedJournal.RemovedOriginals)
            if (!removed.Contains(original)) return false;
        if (_validatedJournal.OrderedCommittedInsertions.Count > insertions.Count) return false;
        for (int i = 0; i < _validatedJournal.OrderedCommittedInsertions.Count; i++)
            if (!SameInsertion(_validatedJournal.OrderedCommittedInsertions[i], insertions[i])) return false;

        // The actual Deck path appends. Never reconstruct the old positional replacement deck.
        var expected = new List<CardSelectionV1DeckCard>();
        foreach (var before in _bound.BaselineDeck)
            if (!removed.Contains(before.ModelIdentity)) expected.Add(before);
        foreach (var row in insertions)
            expected.Add(new CardSelectionV1DeckCard(row.FinalIdentity, row.FinalStableKey, row.FinalUpgradeLevel));
        if (capture.Deck.Count != expected.Count) return false;
        for (int i = 0; i < expected.Count; i++)
            if (!SameDeckCard(capture.Deck[i], expected[i])) return false;
        complete = (selected.Length > 0 || _context.AllowOptionalSelection && journal.Commands.Count==1) && originals.Count == selected.Length && removed.Count == selected.Length &&
            insertions.Count == selected.Length && journal.Commands.All(c => c.State == CardTransformV2CommandState.Succeeded);
        _validatedJournal = journal;
        return true;
    }
    private static bool SameInsertion(CardTransformV2Insertion a, CardTransformV2Insertion b) =>
        a.Ordinal == b.Ordinal && ReferenceEquals(a.OriginalIdentity,b.OriginalIdentity) &&
        ReferenceEquals(a.FinalIdentity,b.FinalIdentity) && a.FinalStableKey == b.FinalStableKey && a.FinalUpgradeLevel == b.FinalUpgradeLevel;
    private static bool Advances(CardTransformV2CommandWitness before, CardTransformV2CommandWitness now)
    {
        if (!ReferenceEquals(before.CommandIdentity,now.CommandIdentity) || before.OriginalIdentities.Count != now.OriginalIdentities.Count ||
            before.AllOriginalsRemoved && !now.AllOriginalsRemoved || before.Insertions.Count > now.Insertions.Count ||
            before.State == CardTransformV2CommandState.Running && now.State == CardTransformV2CommandState.NotStarted ||
            before.State == CardTransformV2CommandState.Succeeded && now.State != CardTransformV2CommandState.Succeeded) return false;
        for (int i = 0; i < before.OriginalIdentities.Count; i++)
            if (!ReferenceEquals(before.OriginalIdentities[i],now.OriginalIdentities[i])) return false;
        for (int i = 0; i < before.Insertions.Count; i++)
            if (!SameInsertion(before.Insertions[i],now.Insertions[i])) return false;
        if (before.State == CardTransformV2CommandState.Succeeded)
        {
            if (before.Insertions.Count != now.Insertions.Count || before.CompletedResults.Count != now.CompletedResults.Count) return false;
            for (int i = 0; i < before.CompletedResults.Count; i++)
                if (before.CompletedResults[i].Success != now.CompletedResults[i].Success ||
                    !ReferenceEquals(before.CompletedResults[i].FinalIdentity,now.CompletedResults[i].FinalIdentity)) return false;
        }
        return true;
    }
}
