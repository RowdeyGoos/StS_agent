# Event card operations v1 functional contract

Draft 2026-09-06 against `920ec84` in23cf. Not yet accepted. The user selected
continued development toward all event support. Acceptance has two stages:
a row-free structural API and generic validation gate, followed by a separately
reviewed exact production caller-selection gate. This document alone enables
neither stage; each requires an explicit ledger disposition after R review.

## Objective and preservation

Create only `bridge/Sts2AgentBridge/successors/event_card_operations_v1` for the
next functional increment. Preserve all thirteen accepted successors, source
identities, frozen contracts and existing packages plus original48 byte-exact.
Keep one event parent and reuse the actual `CardSelectionV1Session` and item
session through child brokers. Select unchanged source files directly where
possible; any derived frozen file needs a checked, explicit source transformation
and independent review. This is not a general copy-and-edit fork of every layer.

Extend the accepted event controller with exact native event card callers.
The first production rows will be listed in a separate exact caller-selection
record only after callback, selection policy and effect-completion evidence is
accepted; that record does not mutate this structural contract. Generic card-engine support
or one reference to CardSelectCmd does not establish a working native caller.
Do not introduce a complete-event script per event. A small immutable registry
connects proven event options to shared card-selector mechanisms and exact typed
completion witnesses.

## Caller and policy registry

Every native row binds an exact event runtime type, stable option text key,
proved callback/callsite, selector runtime type, operation, minimum/maximum count,
commit mode, complete candidate-domain rule and effect-completion witness.
Bind actual event/player/option/button references before publishing the parent
decision; retain the same policy and factory through immediate stale recapture,
one reserved dispatch, accepted receipt and child admission. Do not infer numeric
rules from localized text, visible selection count or selector class alone.
Static evidence must trace the exact EventOption key construction through its
bound delegate target to the selector call. Co-occurrence in one event is not
sufficient. Require one unique registry row per exact runtime type and option
key; conflicting/duplicate rows fail the build, and duplicate matching runtime
options fail capture. No subclass or type-name fallback is accepted.

Each new card factory retains a complete bounded pre-dispatch deck snapshot and
concrete expected candidate count. For deck operations, compute that count from
the complete deck and exact proven eligibility rule, retaining exact eligible
original references. At admission, compare the deck and eligible references with
the retained snapshot. For addition, bind the statically proved generation
arguments and complete-domain rule before dispatch; generated original references
are bound once at the first proved complete selector admission, never from later
deck insertion. Where a public caller-owned list exists, require exact selector
and completion-task equality to that list. The selector verifies the expected
count and never supplies or retrofits it. Preserve admitted references for later
effect comparison.
This requirement applies to new caller rows; the frozen Cheese implementation
retains its separately accepted evidence and behavior.

Known card callers without implemented and accepted native adapters are explicitly
unsupported before dispatch. Their UI enabled state remains an observation fact;
a separate closed support classification controls agent legality. They never
fall through to ordinary item eligibility. The native classification is a closed enum: Proceed, OrdinaryItemEligible,
SupportedCardSelection or UnsupportedCardSelection. Public `child_policy` carries
the fixed `unsupported_card` marker for the last case; the native policy and
factory are both absent. Add a public `child_domain_count` scalar, 1..64 for a
supported card choice and zero for all other choices. The policy classification
and concrete domain count participate in structural identity and the decision
digest. An all-unsupported option set stops
without an action. Unknown nonclassified ordinary options retain the predecessor
ordinary policy and its stop boundaries; this is not a full-branch coverage claim.

The initial supported policy range retains at most8 selected cards and64 complete
candidates within the frozen child budget. Events may select multiple cards;
Smith remains the already accepted exactly-one rest behavior and is not broadened
by this event packet. Optional zero-card choices, arbitrary changing counts,
partial domains, scrolling and repeated stable-key option loops remain separate
gaps unless explicitly added to the final accepted rows and tests.

## Native child behavior

Admit only the exact first eligible foreground screen following the retained
accepted parent option. Retain one initially incomplete selector-completion task,
exact holder/card-node/original-model bindings and the complete baseline deck.
No preselected or completed startup selector, late adoption, foreign overlay,
substituted parent, replaced screen or second task can be admitted. Each Read
and Apply retains the frozen immediate native recapture and owner-frame rules.

Shared adapters project ordinary selection, preview and confirmation accurately.
A preview that hides grid highlights must retain the reconciled selected set and
prove the exact original models through its native preview controls. Confirmation
must use the bound enabled native control. Completion-task publication alone is
not effect completion. Require exact returned originals, selector removal, the
operation-specific deck delta and a proved post-effect parent witness after the
awaited effect. Each row must name the exact public same-event post-await state
or callback witness. A changed parent projection alone is insufficient; a row
without a usable typed completion witness remains known-unsupported. Transformation additionally needs authoritative one-to-one
original/replacement references; do not manufacture mappings from similar cards,
deck positions or an otherwise plausible delta.

Card add/remove/upgrade/transform effects remain reconciled by the actual frozen
card session. Unrelated deck mutation, partial/reversed effects, early or lost
completion, count mismatch, cancellation or uncertain dispatch ends the event
without retry. A native path whose effects do not fit the frozen session needs a
separate reviewed successor; do not weaken reconciliation to accept it.

## Parent, wire and provider

Preserve the accepted orchestrator lineage, one active child, lifetime factory
and screen tombstones, permanently closed receipt admission window after parent
transition, resolved-child delivery before disposal/resumption, and exact final
Proceed/map handoff. A new child still needs another accepted parent option.
Keep12 parent actions,4 child episodes,52 total actions,2048 host reads and one
30-second monotonic budget; no reset between child episodes.

Use an explicit successor version and decision/action route pair for expanded
policy semantics. Preserve the frozen child payload versions and use their actual
strict validators. The outer parent policy must constrain each child operation,
counts, commit mode and domain before provider invocation or action. Validate
monotonic accepted/reconciled history, stable candidate identity, selected slots,
preview/confirm ordering and correlated final child result for every admitted
operation. Unknown policies or wrong parent/child lineage fail before mutation.

The existing deeply immutable provider API remains required. A deterministic
first-legal provider is explicit fixture policy, not a strategic event policy.
Do not invoke it twice for the same decision, accept a nonlegal result or issue
an action after a late return. Buffers remain bounded, owned and cleared; no
raw event/card text or live state is retained in summary/evidence files.

## Required gates

After R review, the coordinator may accept and freeze the row-free structural
contract/API and activate generic core, wire and host validation implementation.
Pure inert tests may use internal synthetic descriptors that are unavailable in
production metadata. This first stage does not enable production caller rows.
New production registry rows, card factories/adapters and supported-card policy
allowlists remain absent/fail-closed until accepted B evidence and a second exact
row-selection disposition. Existing frozen Cheese/item behavior is preserved.
Record the selected rows and their evidence hashes separately before native
implementation and complete functional acceptance. Assign exclusive ownership
for core/native, wire/host, aggregate and integration files in the living ledger
before writes.
Tests must execute the actual frozen card/item sessions and production adapter
code against inert target stubs, plus actual C# service to Python provider flows.
Cover every supported production row, multi-card counts, previews with cleared
highlights, delayed effects, wrong result models, stale publication, child cleanup,
unsupported known callers, ordinary/item/Cheese regressions and sequential children.

Independently review source and tests; run relevant full repository regression.
The aggregate checks all thirteen predecessor identities and old48, explicit
project closure, actual integration, and twice-built deterministic native artifacts
against only the two pinned references. Never execute target assemblies. Freeze
new sources only after the candidate aggregate passes; require the frozen gate.

Functional acceptance does not create a listener, bootstrap, installable package,
installation or live campaign. Release composition and live tests are separate.
No profile/save filesystem, Steam Cloud, retained live corpus, remote Git or
unrelated capabilities. No game setup is needed while these dependencies are open.
