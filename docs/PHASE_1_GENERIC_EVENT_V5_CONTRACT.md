# Generic event v5 and card transform v1 — implementation contract

2026-09-08. Proposed for independent implementation acceptance.
Root owns the final contract; A owns consumers; B owns native production; R reviews.
All 24 frozen predecessors, including generic_event_v4, remain unchanged.

## Established native evidence

Retained `/private/tmp/generic-transform-target-a/stdout.bin`, SHA256
`fe6402573e251c2229fe615c38f3d11fbf760ef3fccb5443cee83d6c6adc485e`,
proves Transform d__13 removes every selected original before inserting replacements
(IL382–422), applies ModifyCardBeingAddedToDeck to the proposed replacement
(IL804–831), inserts before awaiting AfterCardChangedPiles (IL973, IL1176), and
only subsequently appends that iteration's result (IL1314). The aggregate command
result therefore cannot alone identify every observable partial insertion.

The follow-up ordering capture, SHA256
`380a2ba0f7307fa8a615f112bd705ed37ef4428d8a23c5c7102d282aeecd3118`,
proves Deck=6, negative-index append, public result fields and the public static
ModifyCardBeingAddedToDeck boundary, plus %Before/%After public preview paths.
The request predicate is exactly `(int)card.Type != 6 && card.IsTransformable`;
no name is assigned to the excluded raw CardModel.Type value. The default factory
constructs CardTransformation(original). PileIndexSort compares pile type then
indices recorded during removal, ascending; equal indices have no stable tie-order
claim. Use actual observed insertion order, never selection order or reconstructed
baseline indices. AddInternal(-1,false) appends and synchronously notifies CardAdded
and ContentsChanged; validate after those callbacks before publishing insertion.
See the [ordering ledger](research/PHASE_1_GENERIC_TRANSFORM_ORDERING_ACCEPTANCE.md)
and [native evidence](research/PHASE_1_GENERIC_TRANSFORM_ORDERING_NATIVE_EVIDENCE.md).
Both exact captures were independently reviewed before selecting this contract.

## Successor composition and semantic versions

Create generic_event_v5, deriving generic orchestration from frozen G4. Existing
families instantiate the actual frozen CardSelectionV1Session, with unchanged
card_selection_v1 payloads, limits, native effect rules and Python parser.
Transform alone uses CardTransformV1Session and wire version card_transform_v1.
Do not re-enable the frozen engine's positional transform branch as native proof.

Transform admission is fixed min=max1..8, domain>max and domain<=64,
preview_confirm, Cancelable=false, with a complete baseline deck of at most512.
Both RequireManualConfirmation preference values are supported and bound unchanged;
neither implies an invented early-preview action. Constructor/context and capture
validation enforce the fixed bounds/mode/domain; host family validation enforces
the same public descriptor. Native admission independently binds cancellation and
manual preference facts, which clients cannot set. Exclude zero/optional selection,
variable minimum, selectorless auto-all/domain<=max, scrolling, custom and combat
paths. No unsupported native preference is hidden by constructing a valid context.

Source-link frozen CardSelectionV1Contracts.cs and CardSelectionV1Session.cs once
into the successor core assembly. Compile the separately named transform engine
there too: frozen DTO constructors are internal. Never create duplicate CLR
contracts in a second referenced assembly. Shared DTOs are internal data shapes;
their fixed Version property does not identify the transform engine's semantics.

Generic namespace: Sts2AgentBridge.Successors.GenericEventV5.
These exact facade signatures replace concrete child storage/factory return:

```csharp
public interface IGenericEventV5ChildSession : IDisposable
{
    string ContractVersion { get; }
    ICardSelectionV1ReadValue Read();
    ICardSelectionV1ApplyValue Apply(string? decisionId, string? actionId);
}
public sealed record GenericEventV5ChildRead(
    string ContractVersion, ICardSelectionV1ReadValue Value);
public sealed record GenericEventV5ChildApply(
    string ContractVersion, ICardSelectionV1ApplyValue Value);
// On IGenericEventV5NativeAdapter:
IGenericEventV5ChildSession CreateChild(object admissionIdentity);
// On IGenericEventV5Session:
GenericEventV5ChildRead ReadChild(string? parentDecisionId,
    string? parentActionId, int childOrdinal);
GenericEventV5ChildApply ApplyChild(string? parentDecisionId,
    string? parentActionId, int childOrdinal, string? decisionId, string? actionId);
```

The facade tag is immutable and validated against the admission before use:
transform requires card_transform_v1; each other admitted operation requires
card_selection_v1. The old wrapper delegates Read/Apply/Dispose to the actual
frozen session. Failed disposal retains ownership for owner-thread retry.
A transform engine rejects every non-transform context at construction.

## Native witness API

Namespace: Sts2AgentBridge.Successors.CardTransformV1. Model identities remain
native-only objects; no indices, witness rows or command identities enter wire JSON.
Surface reuses candidate/deck/control shapes, not frozen transform effect logic.
Surface.Replacements must always be empty for transform; any entry is unsupported.
Only the new witnessed journal supplies replacement authority, never that legacy field.

```csharp
public enum CardTransformV1CommandState
{ NotStarted = 0, Running = 1, Succeeded = 2, Canceled = 3, Faulted = 4 }
public sealed record CardTransformV1Insertion(int Ordinal,
    object OriginalIdentity, object FinalIdentity, string FinalStableKey,
    int FinalUpgradeLevel);
public sealed record CardTransformV1CommandResult(
    bool Success, object FinalIdentity);
public sealed record CardTransformV1CommandWitness(object CommandIdentity,
    IReadOnlyList<object> OriginalIdentities, CardTransformV1CommandState State,
    bool AllOriginalsRemoved, IReadOnlyList<CardTransformV1Insertion> Insertions,
    IReadOnlyList<CardTransformV1CommandResult> CompletedResults);
public sealed record CardTransformV1EffectWitness(
    IReadOnlyList<CardTransformV1CommandWitness> Commands,
    IReadOnlyList<object> RemovedOriginals,
    IReadOnlyList<CardTransformV1Insertion> OrderedCommittedInsertions);
public sealed record CardTransformV1SurfaceCapture(
    CardSelectionV1SurfaceCapture Surface, CardTransformV1EffectWitness Effect);
public interface ICardTransformV1NativeAdapter : IDisposable
{
    CardTransformV1SurfaceCapture CaptureSurface();
}
// CardTransformV1Session implements IGenericEventV5ChildSession:
// public CardTransformV1Session(CardSelectionV1ParentContext context,
//     ICardTransformV1NativeAdapter adapter);
// public string ContractVersion => "card_transform_v1";
```

“Committed insertion” means its exact owned native insertion has occurred, not
that after-hooks, command or parent callback have completed. Publish the row no
later than an owner-frame capture can observe that inserted reference. A row
must originate from an independently proved observation edge, not a deck diff.
Each CommandIdentity is the exact bound collection-command task/invocation identity
under accepted parent/Confirm ownership. Admit 1..8 sequential disjoint batches,
including single-card wrappers delegating to the collection command; a wrapper is
not a second batch. No nested, concurrent, reused or overlapping command contributes.
Observing a method call grants no ownership. Initially all witness lists are empty.

Append a command only after the previous actually succeeded. Its nonempty original subset
is immutable, distinct, selected and disjoint from earlier batches. Cap commands
at8 and total originals/insertions at selected count. Identities never change/repeat;
states never regress. Completed records remain unchanged. Only the active final
command may advance its removal flag, insertion prefix and terminal state.
Snapshots may skip synchronous batches: accept contiguous new already-succeeded
records, or an old Running record becoming Succeeded followed by new records in
the same snapshot. Do not require an observed Running frame; validate each prefix
extension and predecessor success within that snapshot. A new active final record
may likewise be NotStarted or Running after its predecessor succeeded.
NotStarted: removal flag=false and empty insertion/result lists for that command.
Running: empty CompletedResults; insertion prefix may be full, but every insertion
requires that batch's complete removal flag. Succeeded: flag=true, exact full
batch insertion coverage and successful exact ordered CompletedResults required.
Canceled/Faulted: terminal, empty CompletedResults, retained witness prefixes;
return unsupported without child completion or any following batch.
Command result lists are snapshotted once after success into immutable bounded rows;
never repeatedly enumerate the native result or retain its mutable list as authority.
Failure forbids a subsequent batch. Copy lists defensively, bounding enumeration
by the relevant maximum+1. Native may certify a batch's removals at its first owned
Modify/Add callback from captured GetReplacement originals and exact deck subtraction,
without extra enumeration or an unproved removal hook. RemovedOriginals is a monotone,
duplicate-free union of exactly those command subsets with AllOriginalsRemoved=true.
Insertion originals are unique and belong to their command subset; finals are unique and disjoint
from baseline refs. Keys/levels meet frozen bounds and stay stable. Global ordinals
are contiguous from1; global insertions equal concatenated command insertion lists.
Published rows cannot shrink, reorder, mutate, remap or move between commands.
CompletedResults is empty until success, then matches the full command insertion
domain with successful final refs in the proved result order. Missing/extra/duplicate/
default/null results fail; nullable presence alone is not success evidence.

## Effect state machine and exact ordering

Before Confirm, require the unchanged complete baseline deck and no effect witness.
After the sole Confirm dispatch, an unchanged baseline may remain waiting until
its bound command starts. Do not expose preview predictions as final replacements.

For baseline size N, selected count K, removed count R and inserted count J, require
exactly N−R+J current refs: baseline minus RemovedOriginals, plus exactly the J
witnessed final refs, once each. Unprocessed selected originals remain unchanged.
No unknown addition, unrelated removal or key/level mutation is allowed. Each
batch's full original subset must be witnessed absent before any of its insertions.
An inserted unknown ref is unsupported, not retroactively credited by later results;
published insertions must already be present. Partial removal without a proved
observable phase is not admitted. Faults after mutation earn no completion credit.

Require the exact baseline sequence minus cumulative RemovedOriginals, followed
by OrderedCommittedInsertions in their actual observed native order. This follows
from the proved negative-index append path for Deck. Surviving original references,
keys, levels and relative order are unchanged; committed final references, keys,
levels and order are unchanged. Later batches may remove still-unprocessed baseline
originals, but may not remove or reorder already inserted cards. Never normalize
or reorder a native snapshot to satisfy this rule.

A full deck while command/after-hooks are pending remains waiting. Resolve only
when command subsets cover selected originals exactly once, all K insertions and
exact command results are verified, every command and the owned parent callback
succeeded, selector closed, and request task returned exact selected originals. Keep the same run/player/room/map/admission identities.
An observed final reference/key/level or preserved unselected card changing after
publication is unsupported. Extra effects from native hooks are outside this
narrow contract; native execution remains authoritative and is never rewritten.

## Wire, Python and cumulative evidence

Exact G5 routes are /probe/generic-event-v5/public/decision and
/probe/generic-event-v5/public/action in service, host, schema and tests. Do not
inherit G4's retained v3 route literals through a namespace-only replacement.

Derive a child-only CardTransformV1WireCodec from the frozen codec; write literal
card_transform_v1 for observation, resolved, receipt and failure payloads. All
other JSON fields/order/action grammar remain the same. Never invoke the frozen
codec for transform or edit serialized bytes. Validate the tagged value against
the retained admission for every read/apply, including empty-operation failures.
A separate strict child parser derives from frozen Python parsing helpers and
accepts only card_transform_v1/transform; old families still use the exact frozen
parser. Wrong-family versions fail before a subsequent POST. No outer effect_contract
field is proposed: outer G5 plus exact operation→child-version binding is sufficient.

Resolved selected_cards continues to describe selected originals, not resulting
cards. RNG, replacement options, hidden future results and command witnesses are
never exposed. Preserve 12 parent attempts, 4 children, 10 child actions each,
52 total attempts, 2048 host reads and the 30-second host budget. Inherit frozen
MaximumPendingReads=256: each pending Reconcile increments before capture; the
257th returns unsupported without another native capture. Reset only on reserving
a new action before dispatch and on successful select/preview reconciliation, as
frozen. Insertion/command progress does not reset this counter. Initial missing/
transient publication retains frozen behavior and remains bounded by host limits. Preserve G4 history matching, no-retry behavior and completed_card_children
first-resolution credit, one-frame parent lag, cleanup-failure retention and
last-parent-action effects semantics across every mixed-family episode.

## Derivations, ownership and acceptance

A owns core/facade/transform_core/wire/host and focused tests after acceptance.
B owns native discovery/ownership/witness production/adapters/native fixtures.
R owns independent actual-native integration and review. Root owns scaffolding,
projects/checker/provenance/docs and final contract acceptance. Implementation ownership begins only after independent acceptance of this exact
contract. Build lanes remain serialized; this contract includes no live campaign.

Derive transform session/identity helpers from frozen card core with explicit
semantic deltas; domain-separate new decision hashing with card_transform_v1.
Derive generic core/wire/host from G4, preserving old-family source closure and
actual frozen-session execution. Record full origins/diffs and exact reused files.

Tests must cover remove-all then one-insert await (old core rejects N−1), all
prefix lengths, reverse order, bulk/singleton/mixed batches, hook substitution,
command/result/default/failure mismatches, foreign/duplicate/reused refs, mutation
and regression of every retained witness, unknown insertions before results,
wrong ordering, overlapping/nested/reused commands, lost Confirm without retry,
pending full deck, inter-batch delays and delayed callback. Add exact descriptor
exclusions, nonempty legacy Replacements, skipped synchronous batches, all invalid
state/list combinations, and 256/257 pending-read behavior without progress resets.
Require actual native→real transform core→wire→Python completion, all old-family
regressions, cross-version rejection for every payload kind, and mixed families
with cumulative completion surviving Proceed, lost replies and later failure.

## Native observation, ownership and publication

## Admission and scope

Transform uses fixed min=max1..8, preview_confirm, domain>max and domain<=64,
Cancelable=false and a complete pre-parent-action deck<=512. Bind both values of
RequireManualConfirmation, comparison and all other existing preference fields.
The owned FromDeckForTransformation request and exact ShowScreen establish the
candidate originals and effective transformation-function identity. Never invoke
a predicate/factory/function/RNG or enumerate a lazy transformation input to learn
semantics. Mirror the captured predicate exactly: `(int)card.Type != 6 && card.IsTransformable`.
Do not infer an enum label for that raw CardModel.Type value.
Keep both exact request caller function (which may be null) and effective screen
function; a nonnull request function must be the same object at screen creation.
Optional, variable minima, automatic selectorless selection, scrolling, custom and
combat paths stay unsupported. Existing families keep their actual frozen core.

## Exact observational targets

Retain all nine G4 targets and cleanup rules. Add only six:

1. CardSelectCmd.FromDeckForTransformation(Player,CardSelectorPrefs,Func<CardModel,CardTransformation>) -> Task<IEnumerable<CardModel>>.
2. NDeckTransformSelectScreen.ShowScreen(IReadOnlyList<CardModel>,Func<CardModel,CardTransformation>,CardSelectorPrefs) -> NDeckTransformSelectScreen.
3. CardCmd.Transform(IEnumerable<CardTransformation>,Rng,CardPreviewStyle) -> Task<IEnumerable<CardPileAddResult>>.
4. CardTransformation.GetReplacement(Rng) -> CardModel (value-type instance method).
5. Hook.ModifyCardBeingAddedToDeck(IRunState,CardModel,List<AbstractModel>&) -> CardModel.
6. CardPile.AddInternal(CardModel,int,bool) -> void.

These are observations: originals always run, no argument/result replacement,
transpiler, private state read, reflection invocation or input-enumerable wrapping.
Require exact signatures/access/static/instance shape before installation and
exclusive exact owned patches throughout; all15 targets participate in foreign
patch detection, partial-install rollback and retryable owner-thread cleanup.
The pinned game-owned Harmony executes only with inert stubs in offline tests;
production/Godot/game references are compile-only. New GetReplacement/Modify/
AddInternal observers pass through existing upgrade/remove/add families. Journal
enforcement applies only to the current transform authorization; ordinary native
AddInternal calls for reward children do not acquire transform semantics.

## Preview and Confirm ownership

Bind exact native screen, grid geometry, complete holder/card/hitbox/highlight
surface and fresh selection task using existing rules. Before-preview holders
must display the exact selected originals through public holder/CardNode/Model
references. Bind the independently proved %Before/%After Control paths; do not
read private fields or treat an animated after-side option as a final result.
After the first complete before-side set, retain exact holder/card/model membership
and reject replacement or swaps. A partial first materialization may wait; a
complete bound set cannot lose members. The real child core reconciles each
selection against the original action receipt and selection/preview membership.

Confirm dispatch revalidates the actual preview and native confirm control, then
reserves one immutable effect authorization carrying exact selected originals,
admission/parent action and baseline. Dispatch the real native button once.
Reservation survives native task continuation and selector/option node retirement;
it does not authorize a later screen or create another parent receipt.

## Sequential command ownership and initial choices

Only a collection Transform call under the matching inherited Parent AsyncLocal
scope may consume this child's Confirm authorization. Each command gets a fresh
opaque invocation identity and binds its exact returned Task in the postfix.
Use a separate AsyncLocal command scope, restoring the caller scope idempotently
in postfix/finalizer; captured native continuations retain that command identity.
Allow1..8 sequential disjoint nonempty command batches covering selected originals
exactly once. A new batch requires the preceding task and exact results succeeded;
no nesting, parallel command, duplicate original, repeated command/task or stale
closed-generation callback is accepted. The single-card native wrapper delegates
to this observed collection method and does not need a second command hook.

GetReplacement entry/exit records the value's exact Original and returned initial
CardModel under the owned command. Observe public getters only; never call
GetReplacement or RNG from bridge code. Require selected, unprocessed original,
exact owner/run/deck facts, no duplicate call, nonnull distinct initial reference,
allowing the already removed prefix of this same synchronous command loop when
checking the actual deck against the command-start deck. Do not require the whole
baseline to remain present at every GetReplacement call. Require
stable key/nonnegative upgrade level and no baseline/earlier-generation reuse.
Originals are discovered only through the native calls; no second enumeration of
command arguments or caller functions occurs. The batch domain becomes immutable
at the first insertion-stage callback, when its removal loop has finished.

## Removal, final choice and actual insertion witnesses

At the first Modify callback, require the current real deck equals the command's
retained start deck minus exactly its observed original batch; other original and
already inserted refs/keys/levels/order must remain exact. This certifies the batch's
removal phase using the captured native ordering, without private locals or a
fabricated deck. Publish that immutable batch/removal evidence together with the
same atomic surface snapshot. A command fault before a complete batch is bound
stops unsupported and earns no effect credit; native mutations are not undone.

Each Modify prefix must consume one known initial card for its exact run/command.
The postfix binds its returned post-hook final card to that same original. Require
nonnull, exact owner/run and stable key/level, disjoint baseline/final refs, and
no earlier temporary-card generation reuse. The original's own initial reference
may remain its final reference; another original's initial reference may not.
Modifying callbacks may not nest or supply additional unowned mutations.

Each AddInternal call must match the exact player deck, pending final reference,
insertion arguments -1,false and current command. Recheck the
actual pre-insertion deck against the complete journal before entry. Postfix
verifies the exact expected real insertion and only then publishes its immutable
committed original/final/key/level row. A completed row is visible before the
owner's next frame can sample the added card. No later aggregate result may
retroactively justify an earlier unknown insertion. An exception or mutation in
this synchronous insertion is unsupported, never a synthetic successful row.

The final ordering rule is surviving baseline originals followed by actual appends.
AddInternal(-1,false) invokes CardAdded and ContentsChanged synchronously before
return; postfix must reject any extra mutation or exception from those callbacks.
Batch processing order is the actual observed insertion order; never zip native
results with selection order or invent a sort from the pre-command deck. Reject
changes to published references, levels, keys, row order or removal membership.
Bound total originals, insertions and result rows by selected count<=8. Bound
command count by8 and child episodes by4. Preserve parent-owned temporary-reference
tombstones across children: reject reuse of earlier upgrade-preview clones or
initial/final transform refs. At most64 distinct temporary references can arise
from four children of eight originals with one initial and one final per original;
retain existing clone bounds and add the necessary cross-family reuse guards.
These tombstones prohibit reuse as a newly produced clone/initial/final reference.
A previous transform final that is now an ordinary baseline card may be selected
normally for a later upgrade, removal or transformation child.

## Completion and public boundary

Bind each successful native command's actual finite List<CardPileAddResult>
result once into a defensive immutable snapshot, validate success=true and exact
final refs/count/order against its insertion rows, and freeze those results.
The reused Surface.Replacements collection stays empty for transform; only the
new transform journal can authorize a replacement mapping. No nullable/default result alone is success.
Require all selected originals covered by completed disjoint batches and exact
original selection/request task results. Only complete after selector closure,
all command tasks and owned parent effect callback success, and exact full current
deck/journal validation. Later batches or callbacks cannot reopen completion.

Public values describe original-card selection only. The separate card_transform_v1
codec/host parser identifies this new effect contract. No random future result,
replacement-option list, command identity, initial/discarded card or private game
state enters public observations. Preserve cumulative completed-child accounting,
shared attempt/read budgets, no automatic retry and conservative failure reporting.

## Required native acceptance

Exercise actual hooks and adapter with inert native command bodies reproducing
bulk and sequential batches, remove-all before insert, per-card asynchronous waits,
post-Modify substitution, actual AddInternal behavior and final result construction.
Include unrelated held-out event identities without a production allowlist row.
Cover wrong ownership/thread/generation, deferred setup, preview replacement,
lost Confirm, duplicate/foreign originals and final refs, nested/concurrent batches,
changed results, faults after removal/insertion, every journal regression, mutation
of a published card, and cross-family stale-reference reuse. Prove all old-family
regressions plus native->transform core->wire->Python and mixed-family completion.
