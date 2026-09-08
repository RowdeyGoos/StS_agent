# Generic event handler — current development plan

Updated 2026-09-08. Start with the [handoff](PHASE_1_ASTRA_HANDOFF.md).
This plan replaces the earlier discovery proposal and successive live setup
instructions. Exact historical contracts and results remain in their ledgers.

## Objective and implemented architecture

Handle standard interactions by the rules the game supplies, so another event
using the same interaction does not need a new event-name registration. Events
are representative and held-out tests; custom surfaces may need separate adapters.

The generic parent reserves the chosen option and pre-action deck. Owned native
request and screen-creation hooks then supply operation, counts, candidate
originals and task identity. This two-stage admission is implemented: it is no
longer an unresolved design task. The child adapter advertises legal actions;
the host decision provider chooses one. The handler rechecks identity before
native input, verifies preview/completion, and resumes the parent through Proceed.
A later unsupported child does not imply the parent choice had no effect.

Accepted G7 covers ordinary pages, card rewards, removal, fixed upgrades,
fixed/positive variable transformations and singleton potion/relic rewards.
Exact operation limits and confirmation rules remain in the
[G7 contract](PHASE_1_GENERIC_EVENT_V7_CONTRACT.md), inherited contracts and
[coverage matrix](research/PHASE_1_EVENT_COVERAGE_MATRIX.md).

## Latest result and immediate next increment

Release v10 successfully selected card16 (native slot15) in the user's 20-card
Aroma/Let Go setup without scrolling, verified the exact preview, confirmed the
transformation and reached the map. Cleanup is complete. The
[v10 ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md) owns the
result. All 32 successors are frozen; no successor beyond v10 is implemented.

V10's eligibility mask is deliberately restricted to card16 for this experiment.
The next increment should generalize that working path:

1. Derive a successor and remove both the fixed-slot eligibility mask and its
   dispatch guard. Advertise all eligible allocated holders using native order.
2. Preserve complete candidate coverage and holder/model/task ownership, native
   enabled state, deferred identity checks, original-set preview binding and
   selected-only transformation reconciliation. Do not infer model identity from
   matching card names or definitions.
3. Keep viewport, clipping-parent and complete-layout-fit requirements out of
   this direct transformation input path. They are not needed to select an
   allocated off-screen holder, as the live test demonstrated.
4. Validate actual adapter-to-client selection of different targets, including
   visible and off-screen holders, missing/disabled/reassigned targets, and
   fixed/variable preview completion. Scope new tests to the changed behavior;
   preserve or reuse accepted unchanged dependency evidence explicitly.
5. Prepare a fresh release only when a further live test answers a remaining
   behavior question. Give the user the exact setup after installation is ready.

The generalization is planned, not implemented by the documentation update.
Do not rerun the spent v10 client or ask for the old geometry setup again.

## What scrolling still means

A holder can exist outside the rendered viewport and accept direct input. That
is the case now demonstrated live. The grid may also reuse a limited set of
holders, leaving some source cards without an allocated holder. Selecting those
cards may require scrolling/rebinding or another supported native path. V10 does
not solve that second case and does not prove every deck size has full coverage.

Treat incomplete holder coverage as a separate feature. First use the working
complete, stable holder set. Inspect other selector families separately before
claiming they share the transform path's tested behavior. The former suggestion
to limit the deck to ten cards was a workaround for bridge admission, not a
native limit and not a current test prerequisite.

## Remaining shared features

| Work | Current boundary |
| --- | --- |
| All eligible transform holders | Next step; v10 remains fixed to card16 |
| Positive variable transformation live coverage | Implemented and tested offline; latest live event requested exactly one card |
| Variable-count upgrading | Fixed 1–8 supported; early completion needs its own native semantics |
| Optional/zero-card selection and cancellation | Not yet supported generically |
| Incomplete holder coverage | Scrolling/rebinding and stable identity still needed where cards are unallocated |
| Multiple-offer item reward sets | Singleton potion/relic paths supported; sets remain open |
| Custom/repeated interactions and event combat | Need bounded ownership, completion and resumption semantics |
| Broader live/held-out evidence | Existing successful paths do not certify every caller or branch |

Strategic option/card quality is separate from reliable interaction execution.
Do not resume one-event-at-a-time registrations as the default implementation
strategy. Existing Brain/Zen and preview research remains supporting evidence,
not a queue that takes precedence over the current holder generalization.

## Acceptance and handoff discipline

Exercise shared discovery under multiple event identities through actual native
adapters and host integration; a synthetic policy at the core alone is weaker
evidence. Report fixture, release and live evidence separately. Retain cumulative
child completion when a later parent action resets its latest-effects field.
Never retry an uncertain mutation merely to obtain a cleaner result.

For release work read the current successor contract and package guide; keep
frozen source/artifact identities and builds isolated. Use proportionate changed-
behavior validation and one clearly recorded release gate. Do not turn a simple
capability experiment into an unrelated geometry-proof project. Keep this plan
current; move historical attempts to their acceptance ledgers rather than
prepending contradictory readiness instructions.
