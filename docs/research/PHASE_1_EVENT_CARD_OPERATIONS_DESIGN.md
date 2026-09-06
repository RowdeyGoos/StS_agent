# Event card operations: reusable native connection design

Date: 2026-09-06. Repository baseline: `920ec84` in the selected 23cf
integration checkout. This is a repository-only design input for the next
reviewed contract. It does not select a target caller, add a capability, or
authorize another target read. All thirteen accepted successor trees and old48
remain frozen.

## What the frozen components already provide

The frozen card-selection core is already operation-generic. Its public contract
contains `Add`, `Remove`, `Upgrade`, and `Transform`; explicit `minSelect` and
`maxSelect`; three commit modes; an exact complete-domain witness; a complete
bounded deck; task-selected original identities; operation-bound completion;
and explicit original-to-replacement witnesses. The limits are 64 candidates,
512 deck cards, eight selected cards, 256 reads per pending action, and ten
accepted selector actions. See:

- `card_selection_v1/core/CardSelectionV1Contracts.cs` lines 7-17, 20-39,
  72-125, and 223-330, SHA-256
  `e7c221ec1c5390d9a21c6097d3d41b78ee06ee722d5447a7fc5a54146ff9df06`;
- `card_selection_v1/core/CardSelectionV1Session.cs` lines 622-730 and 733-915,
  SHA-256
  `6621da8f4fc9e83d3ffd566005e639a86cf9e531475b982d90718b30c6be353e`.

The session binds every candidate slot/key/model/holder/card/delegate and the
completion task by reference, rejects incomplete domains and decks, and checks
operation-specific monotonic effects. Add admits only the selected offered
originals; remove admits only disappearance of selected originals; upgrade
admits only a one-level increase on selected originals; transform requires a
separate exact replacement witness for each selected original. This core can be
source-linked byte-for-byte into a successor. It needs no new operation branch.

The completion-fixed native adapter supplies a proven implementation for two
closed policies only: Cheese/GORGE add exactly two of eight and ordinary Smith
upgrade exactly one. It has a private two-value native policy enum and typed
Cheese/Smith parents, policy-specific readiness/domain checks, Smith-only preview
controls, Cheese/Smith-specific completion witnesses, and it always emits an
empty replacement list. See
`card_selection_completion_v1/native/PinnedCardSelectionV1NativeAdapter.cs`
lines 111-251, 275-353, 355-529 and its private policy at the end of the file,
SHA-256
`fe9c49f8f29e71247cf7d5ddab47b24a44e922c599f72c7a08c6b34ef8fa5798`.
It is therefore reusable unchanged for Cheese, but it is not a configurable
adapter for other callers.

The frozen event orchestrator already provides the correct parent/child
ownership model: policy and factory are attached before an option click,
reference-bound through the accepted receipt, claimed once against the first
matching foreground screen, guarded on every child operation, and followed by a
separate parent Proceed/map handoff. The card broker constructs the actual
frozen `CardSelectionV1Session`; it depends only on the policy's operation,
counts, mode, domain count, exact accepted context, and guarded native adapter.
`event_orchestrator_v1/brokers/EventOrchestratorV1ChildBrokers.cs`, SHA-256
`ad2490408e6b55d0f3c36ed996a61d41933b41340fb4bea14e74099c561ab7b5`,
can therefore be linked unchanged.

## Why the frozen event parent cannot merely load a registry

The policy surface is closed in several independent places:

1. `EventOrchestratorV1ChildPolicyKind` has only `ItemReward` and
   `CheeseGorgeAddTwo`, and the only card factory hard-codes add 2, auto-at-max,
   domain 8 (`core/EventOrchestratorV1Contracts.cs` lines 54-105).
2. The parent session accepts the Cheese policy only for the exact Cheese stable
   ID and forces every other non-Proceed option to the item policy. Its
   `ValidPolicy` and `PolicyName` switches reject any new value
   (`core/EventOrchestratorV1Session.cs` lines 514-539 and 608-617).
3. The native parent assigns Cheese only from the exact stable key and exact
   `RoomFullOfCheese` runtime type, otherwise assigning the item factory. Its
   child and foreground switches admit only a reward screen or Cheese's simple
   card screen (`native/PinnedEventOrchestratorV1NativeAdapter.cs` lines
   142-221 and 277-302).
4. The production factory exposes only `CreateItem` and `CreateCheese` and calls
   the typed Cheese constructor (`native/ProductionEventOrchestratorV1ChildFactories.cs`
   lines 12-29 and 75-124).
5. The wire validator and Python host have closed two-policy allowlists. The host
   also binds Cheese only to the Cheese option key.

Consequently, a policy-table-only change cannot create a real vertical slice.
The frozen session itself must be checked-derived; source-linking it unchanged
would reject every new card caller before dispatch. Mapping another event to the
Cheese stable ID or enum would falsify public identity and is not acceptable.

## Smallest complete successor boundary

Create a new sibling `successors/event_card_operations_v1` only after exact
caller evidence and a contract are accepted. Keep the public namespace
`Sts2AgentBridge.Successors.EventOrchestratorV1` inside the selected compile
closure, as the completion successor does for compatible frozen types. Give the
wire a distinct protocol/version and distinct routes, proposed as
`event_card_operations_v1` and:

- `GET /probe/event-card-operations-v1/public/decision`
- `POST /probe/event-card-operations-v1/public/action`

The candidate JSON grows by one scalar: `child_domain_count`. The existing
`child_policy` string carries an exact caller-policy ID, while the frozen child
payload reports operation, minimum, maximum and commit mode after admission.
The parent decision must bind the complete domain count observed before the
option click; the screen may verify this value but may not choose or retrofit it.
Non-card and known-unsupported candidates use zero. A new version and routes are
required because the policy allowlist, candidate schema and accepted behavior
change.

### Byte-identical source links

The following frozen implementation files can be source-linked unchanged and
verified by hash in the successor derivation manifest:

| File | SHA-256 | Reason it remains valid |
| --- | --- | --- |
| `card_selection_v1/core/CardSelectionV1Contracts.cs` | `e7c221ec1c5390d9a21c6097d3d41b78ee06ee722d5447a7fc5a54146ff9df06` | Already represents all four operations and explicit counts |
| `card_selection_v1/core/CardSelectionV1Session.cs` | `6621da8f4fc9e83d3ffd566005e639a86cf9e531475b982d90718b30c6be353e` | Already performs immutable selection and exact effect reconciliation |
| `card_selection_v1/native/CardSelectionV1NativeRules.cs` | `e85f8017e919b4f484da8f14df32687b68afe2ad4b8759968e02b52876647fa9` | Stable-key/highlight helpers are policy-independent |
| `event_orchestrator_v1/brokers/EventOrchestratorV1ChildBrokers.cs` | `ad2490408e6b55d0f3c36ed996a61d41933b41340fb4bea14e74099c561ab7b5` | Card broker consumes generic policy fields and actual frozen core |
| `event_orchestrator_v1/native/BoundEventItemV1NativeAdapter.cs` | `9de11ba1bda8daf34fa98b6bc77478a2bcff6b546c2ddae54bfcb7eff3656f07` | Existing item child remains separate and unchanged |
| `card_selection_completion_v1/native/PinnedCardSelectionV1NativeAdapter.cs` | `fe9c49f8f29e71247cf7d5ddab47b24a44e922c599f72c7a08c6b34ef8fa5798` | Retains the already proven Cheese path only |

Project files must bind these exact bytes and their existing pure dependencies.
The production assembly must include only one selected definition for every
fully qualified type.

### Checked derived files

The successor needs narrowly checked derivations of:

- `EventOrchestratorV1Contracts.cs`: add closed caller-policy enum values and
  private/static constructors whose operation, min/max, commit mode, expected
  domain count, public policy string and exact parent stable ID are immutable;
  add one closed native capability classification (`proceed`,
  `ordinary_item_eligible`, `supported_card_selection`,
  `unsupported_card_selection`) to the native candidate; the existing public
  `child_policy` string represents it without another JSON enum/string field,
  using the fixed `unsupported_card` marker only for the last case; add
  `ChildDomainCount` to native/public candidates, with 1..64 required only for
  supported card selection and zero otherwise;
- `EventCardOperationsV1PolicyCatalog.cs`: a separate authored production row
  table implementing the fixed structural `TryGet` API. The row-free stage
  contains only the previously accepted Cheese row. Later accepted caller rows
  change this file, never the frozen structural contracts. Tests use a private
  per-instance resolver or compile-time seam rather than replacing this static
  production table;
- `EventOrchestratorV1CanonicalEncoder.cs`: append `ChildDomainCount` after the
  child-policy string in both decision and structural candidate encodings;
- `EventOrchestratorV1Session.cs`: replace the Cheese-only stable-ID branch and
  two-value switches with a closed mapping from policy kind to the exact stable
  ID and descriptor fields; include the native capability classification in
  projection validation, map it to the fixed public policy marker already
  covered by the structural and decision digests, omit unsupported candidates
  from legal actions even when the native button remains enabled, and return
  the fixed unsupported state when an otherwise-actionable page has no supported
  option; preserve all reservation,
  child-window, tombstone, correlation, cleanup, and Proceed behavior
  byte-for-byte otherwise;
- `PinnedEventOrchestratorV1NativeAdapter.cs`: resolve a card policy only from an
  exact `(event runtime type, option stable ID)` entry before dispatch, retain
  that exact descriptor/factory, generalize the expected-card-screen tombstone,
  and extend only the card screen/foreground cases selected by static evidence;
- `ProductionEventOrchestratorV1ChildFactories.cs`: retain Item and Cheese and
  add one common card factory that holds the exact closed caller binding and
  creates the reusable event-card native adapter only after accepted correlation
  and foreground validation;
- `EventOrchestratorV1WireCodec.cs`: emit `child_domain_count` immediately after
  `child_policy` in every parent candidate;
- `EventOrchestratorV1WireService.cs`: change the protocol routes and
  constructor/type binding required by the derived core, and replace the
  frozen Cheese-only `ValidateHistory` constants (`add`, `auto_at_max`,
  `2..2`, domain `8`, resolved selection `2`) with validation against the
  exact accepted parent option's closed catalog policy and bound
  `child_domain_count`. The service must capture that immutable policy at the
  parent receipt/correlation boundary; it must not infer a policy from child
  output. The existing wire validator remains an independent structural and
  history-prefix check;
- `EventOrchestratorV1WireValidation.cs`, `wire_schema.json`, and
  `host/event_orchestrator_host.py`: use the new version/routes and the exact
  closed policy-to-child-kind table, and accept `unsupported_card` only as a
  non-Proceed candidate with no legal action and no child admission. Preserve
  the new exact candidate key order and receipt/history/deadline/provider behavior.

`EventOrchestratorV1Session.cs` is deliberately in the derived list. Omitting it
is a hard design error because its current `ValidCapability`, `ValidPolicy`, and
`PolicyName` implementations reject a new policy even if every native and wire
file accepts it.

Every derived file needs an executable source-derivation manifest: exact frozen
origin hash, ordered unique replacements, exact result hash, and a reverse or
omission proof that changes are confined to the new version/routes and closed
policy cases.

## Reusable event-card native adapter

Add one native adapter for new event card callers rather than one copied
controller per event. It implements the existing
`ICardSelectionV1NativeAdapter` and feeds the byte-identical core. Its constructor
is private/internal; production exposes only closed, statically selected factory
entries. No production dependency injection or arbitrary descriptor loading is
needed.

The adapter has two layers:

1. A common selector engine, mechanically derived from the completion-fixed
   adapter, owns the exact parent/run/player/room/map/screen/task identities,
   bounded complete grid and deck copies, candidate highlight classification,
   one retained select dispatch per holder, optional retained preview/confirm
   controls, task snapshot, phase projection, and cleanup.
2. A closed caller binding supplies passive facts only: exact event runtime type
   and option key; exact screen family; operation and min/max; commit mode;
   complete-domain proof; preview/confirm binding if required; an
   operation-specific completion witness; and, only for transform, the exact
   original-to-replacement projection. The binding must not expose a generic
   click, card-pile command, RNG, reflection, profile, or save accessor.

The event parent constructs the policy and factory while publishing the option.
The factory retains the exact event, option, button, descriptor, policy, and an
immutable complete pre-effect deck snapshot. Remove, upgrade and transform rows
also retain the exact bounded eligible original references/count derived from
that deck before dispatch. Add rows instead retain the statically proved
generator/list rule and count, because their offered models may be created
inside the clicked callback. The first exact complete selector/task input binds
those newly generated add-model references once at admission; they are never
inferred from later deck insertion. In both cases, the evidence comes from the
exact option-construction -> option delegate -> selector-input dataflow selected
for the caller, not from a later guessed screen. The option page must have unique
runtime stable IDs, and the registry must have a unique `(exact event runtime
type, option stable ID)` row. Any duplicate fails the page before publication.
The factory
creates the child adapter only after the option dispatch has returned an accepted
receipt and the first matching foreground selector is observed. The child broker
continues to guard the same accepted event context and exact screen on every
read/apply. A changed parent, foreign overlay, changed screen, changed descriptor,
or a later matching screen after a closed window is terminal.

At creation, the current complete deck must equal the pre-effect deck. For
remove/upgrade/transform, the screen must reproduce the retained domain count
and exact eligible originals. For add, the first admitted complete screen/task
input must reproduce the retained generator/list count and becomes the sole
bound offered-reference set. The screen verifies the policy; it never chooses
the operation, cardinality, domain, or eligibility rule.

The common selector engine may reuse the proven holder `_GuiInput` selection
path only where the selected screen exposes the same exact public grid/holder/
highlight contract. Confirmation is not generalized by name: every selected
screen must bind its exact public preview/confirm control and existing guarded
dispatch route. Complete-domain proof is caller-specific. Merely seeing all
currently displayed holders is insufficient when paging, scrolling, filtering,
or hidden eligible cards remain possible.

## Closed caller-policy record

Each production entry should be an authored, immutable record with these fields:

- exact caller policy enum and public policy string;
- exact event runtime type and exact option stable ID;
- exact selector screen type/family;
- `CardSelectionV1Operation`;
- `MinSelect` and `MaxSelect`, each 1..8, preserving a proven range when the
  caller permits one and exact equality when it requires a fixed count;
- `CardSelectionV1CommitMode`;
- expected complete-domain count or a separately reviewed bounded proof;
- exact preview/confirm strategy;
- exact post-task effect-completion strategy;
- transform replacement strategy, which is `none` for non-transform policies.

Each row also names the exact option-construction and delegate bodies carrying
the selector inputs, and the exact same-event post-await state used for
`EffectCompletionObserved`. A generic changed option projection, selector
closure, or event-finished guess is not a completion witness.

Policy lookup is an exact table, not reflection, string heuristics, type-name
patterns, or a screen-selected fallback. Duplicate event/option entries, two
policies for one option, mismatched policy/factory references, and unknown policy
values fail the build or the first projection. Unknown event options retain the
existing ordinary/item behavior and will stop if an unexpected card screen
appears; they must not be inferred as card-capable from the foreground screen.

The registry also needs negative rows. If an exact event runtime type and option
stable ID are known to open a card interaction but its native adapter is not yet
accepted, the native candidate uses the closed `unsupported_card_selection`
classification, retains its real visible/enabled state, and carries no policy or
factory. Its public candidate uses `child_policy:"unsupported_card"`; the
existing canonical encoder already includes that string in both decision and
structural digests. The session never advertises that action. It must not fall
through to the ordinary item factory. A mixed page can still advertise
independently supported choices; a page whose enabled choices are all known
unsupported returns the fixed unsupported observation before any click. A
classification change or A-B-A recapture invalidates the publication. This
negative classification is an authored exact registry entry, never an inference
from option text or a later foreground screen.

### Concrete structural API proposal

The structural contract can freeze before caller rows. The successor's derived
contracts keep existing type names and add only this closed surface:

```csharp
public static class EventOrchestratorV1Limits
{
    public const string Version = "event_card_operations_v1";
    public const string UnsupportedCardPolicy = "unsupported_card";
    public const int MaximumChildDomainCount = 64;
}

public enum EventOrchestratorV1CapabilityKind
{
    Proceed = 1,
    OrdinaryItemEligible = 2,
    SupportedCardSelection = 3,
    UnsupportedCardSelection = 4,
}

public sealed class EventOrchestratorV1NativeCandidate
{
    // Existing constructor arguments remain in their current order; these are
    // inserted immediately before childPolicy/childFactory.
    public EventOrchestratorV1CapabilityKind CapabilityKind { get; }
    public int ChildDomainCount { get; }
}

public sealed class EventOrchestratorV1Candidate
{
    // Existing public fields remain. This is serialized immediately after
    // child_policy and is covered by both canonical hashes.
    public int ChildDomainCount { get; }
}
```

The derived `EventOrchestratorV1ChildPolicyKind` adds one enum member per
accepted caller policy. Each matching named static constructor returns the
existing `EventOrchestratorV1ChildPolicy` with immutable child kind, operation,
fixed min/max, fixed commit mode, and the validated pre-dispatch domain count.
There is no public generic policy constructor and no provisional production
enum member. Structural fixtures may use an internal test-only policy factory;
it must be absent from production metadata.

The exact valid combinations are:

| Capability | Native enabled | Policy/factory | Public child_policy | child_domain_count | Legal |
| --- | --- | --- | --- | ---: | --- |
| Proceed | retained | both null | empty | 0 | enabled and otherwise valid |
| Ordinary item-eligible | retained | exact paired item values | `item_reward` | 0 | enabled and otherwise valid |
| Supported card selection | retained | exact paired caller values | fixed caller policy ID | 1..64 | enabled and otherwise valid |
| Unsupported card selection | retained | both null | `unsupported_card` | 0 | never |

Every other combination is invalid. If the page has at least one supported
legal action, unsupported candidates remain visible in the observation but are
not advertised. If native-enabled non-Proceed candidates exist and all are
classified unsupported, the parent emits its existing fixed unsupported value,
not waiting or ready. Native-disabled supported candidates may still yield the
existing waiting behavior. These rules avoid converting an unsupported card
caller into item authority while preserving the observed enabled fact.

## First useful vertical slice

After B's independently reviewed caller census supplies exact rows, select at
least one real, production-connected caller from each proven family:

- one add policy whose exact count/domain differs from Cheese or otherwise
  proves the generalized connection;
- one remove policy;
- one event upgrade policy;
- at least one selected policy with `MaxSelect > 1`, so this is not a renamed
  single-card controller.

A caller may satisfy two bullets, but the slice must execute add, remove and
upgrade through actual parent publication, actual generalized native factory,
the actual frozen card session, child completion, and parent continuation in
inert native fixtures. A registry that is never reached by the parent is not an
implementation.

Transform remains gated unless the static evidence supplies an authoritative
public original-to-replacement mapping. The already reported preview path retains
private original-to-result state; a visible preview alone does not establish the
`CardSelectionV1Replacement` identities required by the frozen core. Until a
bounded public projection is proven, keep transform absent from the production
policy table and cover it with an explicit unsupported fixture. Optional zero-card
selection also remains absent because the frozen core requires minimum at least
one. Repeated stable-option loops and partial/paged domains remain separate
contracts.

## Evidence required per caller

The caller census must establish, before implementation:

1. exact event type and option stable ID, plus the synchronous parent control
   path that opens the selector; the selected bodies must trace exact option-key
   construction through its delegate to the selector operation and input list;
2. exact operation and min/max cardinality, including whether confirmation is
   automatic, explicit, or preview-then-confirm;
3. exact screen type and public complete-domain proof, including scrolling,
   filtering and hidden-card exclusions;
4. exact candidate original identities returned by the retained completion task;
5. exact same-event caller completion point after its awaited deck mutation/hooks,
   not a generic parent structural change;
6. add/remove/upgrade deck semantics, or authoritative transform replacement
   identities;
7. exact return-to-event/Proceed behavior and the same-event guard.

Missing any one of these keeps that caller out of production. Similar UI or an
event name is not evidence.

## Focused acceptance matrix

Pure and inert-native tests should include:

- every selected policy's exact event/option/screen/operation/count/mode/domain
  tuple, with each field independently corrupted;
- pre-dispatch complete deck and eligible-reference/count retention followed by
  exact screen verification for deck operations; add generator/list count plus
  one-time binding of generated refs at first admission; changed deck/list/order/
  count, add refs inferred from later insertion, duplicate runtime option keys,
  duplicate registry rows, and a screen attempting to retrofit the policy;
- minimum and maximum count behavior, including at least one multi-card case and
  no early confirm/auto-commit;
- complete-domain false, partial page, hidden/offscreen candidate, reordered or
  replaced holder/model/screen, duplicate identities, and transient highlight;
- stale parent recapture before dispatch, policy/factory replacement, foreign
  foreground, factory/screen lifetime tombstones, A-B-A option identity, and no
  later screen adoption;
- known unsupported card option with its native enabled flag preserved but no
  legal action; mixed supported/unsupported choices; all-enabled-but-unsupported
  page; no item fallback; and interaction/support classification change or ABA;
- selection task incomplete/success/cancel/fault, overlay-close ordering, and
  completion-witness-before/after deck-effect ordering;
- exact add, remove and upgrade monotonic prefixes, plus foreign/extra/reordered/
  oversized deck changes;
- transform unsupported without replacement witnesses; if later selected,
  missing/duplicate/foreign/reordered replacement mappings;
- uncertain kth selection or confirmation with retained reservation and no
  retry; reentry and cleanup failure ownership;
- item and Cheese predecessor paths through the successor, followed by new
  card callers and final Proceed/map handoff;
- new-version wire/host policy allowlists, old-route rejection, wrong
  policy-kind/operation/count correlations, max body/history, provider once,
  deadline and action/read bounds.

Compile native code only against the exact pinned references and execute only
inert stubs/pure assemblies. Deterministic two-build identity, default-deny
verifier policy, project-closure/source-derivation gates, package/operations and
a later bounded live campaign remain separate acceptance stages.

## Current hard gaps

Exact caller rows are pending the independently reviewed static census. This
repository audit cannot name an eligible remove, event-upgrade, alternate-add,
or transform caller without that evidence. It also cannot prove screen-specific
complete domains, completion witnesses, or transform replacement accessors.
Those are the only facts that should determine which policy entries enter the
first successor; no generic adapter design can substitute for them.
