# Astra handoff — generic event support

## Active Potion Courier test — installed, awaiting manual setup

2026-09-08. A fresh installation of unchanged generic releasev6 is verified for
the user-authorized exploratory Potion Courier → Ransack test. The prior Cheese
instance remains closed. New installed-state SHA256:
`36db173d95bd97704415f33195b61af6d36d51cda5595e4376bbd1fe8d186d08`.
Frozen sources, unchanged429-file base, exact2-file overlay, protected metadata
and stopped/closed checks pass. No client invocation or credential-content read.
Manual Profile3/single-player setup: fresh Potion Courier initial choices,
Ransack second, at least one empty potion slot; leave options untouched and close
console/popups. Wait for user readiness, verify UI and require-running, then one
frozen invocation. Reward-screen behavior remains unconfirmed; only a completed
item child plus map handoff passes the intended gate. Read the [active test ledger](research/PHASE_1_GENERIC_EVENT_V6_POTION_COURIER_LIVE.md)
for exact invocation, new-instance authorization and required cleanup. Older
closed-campaign/no-setup statements below describe preserved earlier checkpoints.

Updated 2026-09-08 after extending the requested generic handler. Historical
attempts and cleanup remain in their linked acceptance ledgers and Git history.
The first live failure exposed a verified option-button lifetime mismatch.
The lifecycle correction and v2 release are accepted. Its live test progressed
beyond the immediate stop but exhausted pending reads before child admission;
full owned cleanup passed. Diagnostic v3 then identified prepare_candidates as
the last waiting stage in one live test and also completed full owned cleanup.

## Current generic release v6 — live continuation passed, campaign closed

2026-09-08. The user confirmed ready and root performed exactly one Search test.
CUA showed fresh Room Full of Cheese initial choices, HP62/80, Search cost14,
empty potion slots and no selector/console/popup. Require-running passed. The
frozen client resolved after2 parent actions and4 reads, ending at map_ready.
Post-test UI showed HP48/80, an additional cheese relic icon and the map.

This demonstrates Search→Proceed/map continuation in the G6 release. It does
**not** validate generic item selection: child_episodes,child actions and both
completion counters were zero; effects remained unverified. The desired item
child acceptance gate is still unmet. No child reward surface was exposed to the
controller in this invocation. The exact native reward-grant mechanism was not
inspected and is not established by this result. No retry or extra gameplay action
was attempted.

Normal UI quit,stopped/closed,code-first quarantine,exact four-file purge,429-file
clean-base verification and final stopped/closed checks all passed. The campaign
is closed; no installed overlay,credential or cleanup remains. Historical installed
and quarantine state hashes in the ledger must not be reused. No game setup is
needed now.

`generic_event_release_v6` remains frozen as successor27, source-linking the full
G6 gameplay closure unchanged. Both full offline gates and independent reviews
pass: complete G6 regressions,843 runtime assertions,30 socket/client scenarios,
128 verifier checks,56 production sources. The379392-byte DLL SHA256 is
`96723ba26f9f64a74cd0f1d8ae4217191a13410c5629a1feedc26a44f3890c2f`.
All26 predecessors and the original bridge remain unchanged.

Next, inspect retained event evidence to identify a parent choice demonstrably
opening an ordinary singleton reward screen before preparing another live test.
Visible relic gain alone is insufficient for selecting an item-handler fixture.
Any fresh campaign requires its own reviewed setup and identities; this closed
campaign supplies no reusable state or retry. Read the
[release contract](PHASE_1_GENERIC_EVENT_RELEASE_V6_CONTRACT.md) and
[acceptance ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V6_ACCEPTANCE.md).
No live item/transform or complete-run claim is made. The functional acceptance
snapshots below remain historical.

## Preserved generic v6 functional acceptance — 2026-09-08

`generic_event_v6` is accepted and frozen as successor26. It adds direct singleton
potion/relic children through owned reward requests, post-generation screen
creation and exact collection invocations. The actual frozen item engine verifies
collection; the wrapper waits for collection, Offer and Chosen completion plus
screen closure and freshly revalidates effects within one shared 256-read budget.
Existing upgrade, removal, reward-card and transformation families are preserved.

Separate cumulative item/card counts survive Proceed and later failure. Item replay
keys include outer lineage, so identical successive relic offers remain valid.
Stale invocation contexts stop a later child without erasing earlier completion.
Event identities are test/ownership data, never production admission rows.

Independent review and both full offline gates pass: 3,199 native and 1,718
item assertions, 879 transformation assertions, 147 wire cases, 110 host tests
and 161 integrations, including 99 actual-native cases. All 25 predecessors
and the original bridge remain unchanged. Read the
[G6 contract](PHASE_1_GENERIC_EVENT_V6_CONTRACT.md) and
[acceptance ledger](research/PHASE_1_GENERIC_EVENT_V6_ACCEPTANCE.md) for exact evidence.

This is functional support, with no new release or live item/transform claim.
All live campaigns remain closed; no game setup is needed yet. Multiple-offer
item sets, optional/scrolling selectors, variable upgrade/transform minima and
custom/combat interactions remain open.

## Preserved generic v5 functional acceptance — 2026-09-08

`generic_event_v5` is accepted and frozen as successor25. Fixed-count transform1..8
uses native original/final command witnesses and exact surviving-original-plus-
append reconciliation, including per-card awaits and replacement substitution.
The new `card_transform_v1` engine/codec/parser is separate; earlier upgrade,
removal and reward families retain the actual frozen `card_selection_v1` engine.
Event names remain test/ownership data, never production admission rules.

Independent review and both full gates pass:2345 native assertions,879 transform
assertions,118 wire cases,95 host tests and124 integrations,64 through actual
native adapters/hooks. Mixed transformations followed by upgrade retain cumulative
completion through Proceed or later failure. The final native guard rechecks
replacement and preserved-card ownership after insertion callbacks and during
pending effects. All24 predecessors and original bridge remain unchanged.

Read the [G5 contract](PHASE_1_GENERIC_EVENT_V5_CONTRACT.md) and
[acceptance ledger](research/PHASE_1_GENERIC_EVENT_V5_ACCEPTANCE.md) for exact source
identities, review findings and evidence. This is functional support, with no new
release or live transformation claim. All live campaigns remain closed; no game
setup is needed. Next functional work is generic item children; optional/scrolling,
variable minima and custom/combat families remain explicit open scope.

## Preserved generic v4 functional acceptance — 2026-09-08

`generic_event_v4` is accepted and frozen as successor24. It adds shared native
fixed-count upgrade1..8 while preserving variable removal and reward modes.
Multi-preview clones are bound to their exact originals through scoped native
observations and one owned deferred-click ticket; retained controls and clone
generations reject replacement or reuse before Confirm. Event-name registration
is unnecessary. The frozen card core still proves exact selected-only +1 upgrades.

The v4 protocol adds `completed_card_children`, preserving fully verified child
completion through Proceed or later failure. `effects` keeps its last-parent-action
meaning. Independent review and both full offline gates passed:1,343 native
assertions,107 wire cases,86 host tests and96 integration scenarios,36 through
production native adapters with inert stubs. Four native builds match exactly.
Read the [v4 contract](PHASE_1_GENERIC_EVENT_V4_CONTRACT.md) and
[v4 ledger](research/PHASE_1_GENERIC_EVENT_V4_ACCEPTANCE.md) first for exact scope,
identities and evidence. This functional component is not an installable release
and has no multi-upgrade live claim.

All24 successors and the original bridge remain frozen. All generic live
campaigns are closed; no installed overlay, credential or cleanup remains.
No game setup is needed. The next transformation discovery passed its reviewed
single metadata capture: nine bodies, two types and1,395 instructions. It proves
all-original removal followed by per-card insertion/awaits and a hook that may
substitute the generated replacement. Multi-transform therefore needs a new
reconciliation path; the frozen constant-length positional validator is insufficient.
Read the [discovery ledger](research/PHASE_1_GENERIC_TRANSFORM_ACCEPTANCE.md) and
[native findings](research/PHASE_1_GENERIC_TRANSFORM_NATIVE_EVIDENCE.md) before
selecting that contract. Native transform implementation, final mapping witnesses,
remaining ordering facts, variable upgrade minima and item/optional/scrolling/custom/
combat families remain open.

## Preserved v5 live completion and clean teardown — 2026-09-08

The single `generic_event_release_v5` live test resolved Cheese/Gorge through
two card selections and Proceed/map. Both parent actions and both child actions
were attempted, accepted and reconciled; one child episode, four total attempts,
13 reads, final diagnostic `map_ready`. CUA confirmed initial untouched choices
and the final map; visible deck count increased from 15 to 17. This establishes
one bounded generic reward-addition live path, not all event branches or families.

The raw final summary retains `effects: unverified`: the frozen parent session
resets that field on Proceed after previously verifying the child effect. Child
resolution still requires the exact selected-original additions and completion
witness. This is a reporting limitation; do not silently relabel the raw field.
See the [v5 ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V5_ACCEPTANCE.md) for
exact result, source-based interpretation, visible corroboration and limits.

Normal quit, stopped/closed checks, code-first quarantine, exact four-file purge,
429-file clean base and final stopped/closed checks passed. All v1/v2/v3/v4/v5
campaigns are closed. No installed overlay, credential or cleanup remains; all
state identities below are historical and must not be reused. All 23 successors
and the original bridge remain frozen. No new game setup is needed. Next work can
clarify cumulative effect reporting and extend evidence to held-out shared callers
and remaining interaction families through a reviewed successor.

## Preserved v5 pre-live installation — 2026-09-08

`generic_event_release_v5` is accepted and frozen as successor 23. It repairs
v4's measured reward hitbox exact-type mismatch: the declared native clickable
control may be a live subclass, while the exact captured reference, liveness,
visibility, enabled state and all other ownership/selection checks remain.
The actual live subtype name is unknown. Diagnostic code 48 remains reserved;
all 78 wire mappings and the generic_event_v3 gameplay protocol are unchanged.

Independent review, both complete offline release gates, all 17 native-to-client
socket scenarios and all 100 verifier checks passed. A controlled subtype input
reproduces v4 code 48 and completes v5's two-card addition and Proceed/map path.
This is fixture evidence; generic reward-addition live success remains open.
Read the [v5 contract](PHASE_1_GENERIC_EVENT_RELEASE_V5_CONTRACT.md) and
[v5 acceptance ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V5_ACCEPTANCE.md)
first for exact identities, evidence and operational boundaries.

The fresh `GENERIC-EVENT-V5-SMOKE-V1` campaign is installed and metadata-validated;
its current installed state SHA256 is
`27ad96a07cb94509727aee99bc8eed4f6abc7d6291eb527a83716e52e15706ab`.
The exact two-file overlay and unchanged 429-file base passed verification.
Post-install checks confirmed game stopped and port closed (3 process/2 port
samples). Credential content has not been read, and no v5 client has run.
All v1/v2/v3/v4 campaigns remain closed; their state identities are historical.

Next user action: manually launch Profile 3, single-player, and set up a fresh
Room Full of Cheese at its initial choices with Gorge untouched; no open
selector, console, map or popup. After readiness, verify that UI and require-running,
then invoke the v5 client exactly once with the installed state above. No retry,
adoption or manual child selection after uncertainty. Capture the bounded summary;
then normal quit, stopped/closed, code-first quarantine, exact purge and clean-base
verification close the campaign. Do not launch automatically or access profile,
save or Cloud files. Repeated unmodded launch remains waived.

## Preserved v4 live result and clean teardown — 2026-09-08

`generic_event_release_v4` is accepted/frozen as successor22 and its one live
campaign is now closed. It opened the Cheese reward chooser, then stopped with
`candidate_hitbox_type`: the native clickable area failed the reward handler's
exact-runtime-type requirement. The concrete subtype name was not captured.
Parent attempts/accepts1,reconciled0,child episodes/actions0,reads258,effects
unverified. The reason is the last completed capture's diagnostic; later checks
and successful card additions remain unproven.

Normal quit,stopped/closed,code-first quarantine,exact four-file purge and429-file
clean-base verification passed. No campaign,overlay,credential or cleanup remains.
All v1/v2/v3/v4 state identities are historical and must not be reused. The
[v4 ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V4_ACCEPTANCE.md) owns exact
result and cleanup evidence. Keep the game closed. Next review a successor repair
of the hitbox exact-type assumption while preserving native contract compatibility,
liveness,identity/replacement rejection,ownership and remaining predicates. All22
successors remain frozen; no additional live setup is ready yet.

## Preserved v3 diagnostic result

`generic_event_release_v3` is accepted and frozen as successor21. Read its
[contract](PHASE_1_GENERIC_EVENT_RELEASE_V3_CONTRACT.md) and
[ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V3_ACCEPTANCE.md) first. Both full
offline aggregates passed, including instrumented745 assertions,168 diagnostic
assertions,373 runtime assertions,17 transport tests,15 socket scenarios and73
binary verifier checks. The74-file source manifest remains frozen.

Its one fresh live invocation accepted Gorge/opened the chooser, then stopped
after258reads with prepare_candidates, zero child episodes/actions and unverified
effects. The last completed capture reached offered-card validation; the exact
nested reference/identity/coherence/highlight/initial-state predicate is unknown.
Do not infer geometry, which is evaluated later, or treat this as proof of the
historical v2 cause. No retry or manual selection occurred.

Normal quit, stopped/closed, code-first quarantine, exact purge and429-file clean
base checks passed. GENERIC-EVENT-V3-SMOKE-V1 is closed, as are v1/v2. No campaign,
overlay, credential or cleanup remains. All v3 state identities in the ledger are
historical and must not be reused. Keep the game closed. Next inspect/reproduce
TryCreateBindings and its candidate-capture/initial-state subchecks in a reviewed
successor; add finer bounded diagnostics only if static evidence and inert tests
cannot establish the mismatch. Do not relax identity/ownership to proceed.

## Preserved v2 implementation and live result

`generic_event_release_v2` is accepted and frozen as the twentieth successor.
Read its [contract](PHASE_1_GENERIC_EVENT_RELEASE_V2_CONTRACT.md) and
[acceptance ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V2_ACCEPTANCE.md) first.
It packages the accepted [lifecycle correction](PHASE_1_GENERIC_EVENT_LIFECYCLE_V1_CONTRACT.md):
the game frees option buttons after ordinary choices, so strict button authority
ends at predispatch reservation and the reference becomes an opaque receipt.
Original-source fixtures reproduce the unsupported read;745 corrected native
assertions and73 cross-language cases (23 native) passed, preserving all550 old
assertions. Release verification,63 verifier checks and frozen aggregate passed.

The v2 live invocation accepted Gorge/opened the chooser, then stopped after258
reads with zero child episodes/actions and unverified effects. V1 stopped on read2.
The specific waiting predicate remains unknown; binding/task readiness and selector
preparation must be distinguished with bounded fixed reason codes before another
live campaign. Do not infer geometry or async ownership as the measured cause.
Normal quit,code-first quarantine,exact purge,429-file base and stopped/closed
checks passed. No campaign is active and no game setup is needed. The v2 ledger
owns the exact result and cleanup; neither campaign may be retried or adopted.

`generic_event_v3` extends shared discovery to reward-card additions1..8 with
variable limits, preserving upgrade-one and removal1..8. Read its
[contract](PHASE_1_GENERIC_EVENT_V3_CONTRACT.md),
[component guide](../bridge/Sts2AgentBridge/successors/generic_event_v3/README.md)
and [acceptance ledger](research/PHASE_1_GENERIC_EVENT_V3_ACCEPTANCE.md) first.
Owned request/creation calls establish exact offers and an immutable admission.
Reward modes are automatic submission at max or manual confirmation at min..max;
upgrade/removal retain their previews. Exact task sets, parent success and the
frozen card session reconcile the selected originals. Native sorting and monotonic
partial additions are supported. Event names are tests, never admission rows.

The scope remains bounded: these card families, ordinary pages and Proceed.
Transform, multi-upgrade, item children, optional/scroll/custom/combat families
remain open. Reward completion does not certify all Add hooks/animations or
unrelated effects. The new release composes this instrumentation; live
validation remains pending. Actual EventSynchronizer context preservation is still a live gate.
The same23cf worktree and integration branch remain authoritative.

## Start here

- Use `/Users/rowdeygoos/.codex/worktrees/23cf/StS_agent`.
- Branch: `codex/phase1-actor-ready-integration`.
- Frozen predecessor implementation: `b2ae0dd6577e7d44c208252f816e2266391c2ea5`
  (`Add shared event card policies and two native upgrade flows`). Documentation
  updates follow this commit. Verify current HEAD and user changes before work.
- The saved checkout `/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent` is older
  local main. Do not diagnose or edit against it. Its Python environment can be
  used with the integration checkout as the working directory.

Follow [AGENTS.md](../AGENTS.md), then read these immediate handoff documents:

1. [Generic event handler plan](PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md): the user's
   clarified objective, current limitation and next architecture work.
2. [Current status](PHASE_1_CURRENT_STATUS.md) and
   [coverage plan](PHASE_1_EVENT_COVERAGE_PLAN.md).
3. [Event-card acceptance](research/PHASE_1_EVENT_CARD_OPERATIONS_V1_ACCEPTANCE.md),
   especially final functional acceptance; its earlier sections are historical.
4. [Coverage matrix](research/PHASE_1_EVENT_COVERAGE_MATRIX.md) and
   [decisions](../DECISIONS.md), including the generic-discovery priority entry.
5. [Multi-agent guide](MULTI_AGENT_EXECUTION.md) before assigning parallel work.

The actor-ready plan and its ledger preserve completed headless/elite work;
they are not the current event implementation queue. Do not restart completed
packets or replay the old controller timeout to restore context.

## User intent and the misunderstanding to avoid

The user wants shared handlers that support events by their presented interaction,
not development that adds one event-name connection at a time. We acknowledged
that the latest implementation worked on both reusable mechanics and individual
event connections, and that its native card support still requires registration.

The new successor discovers upgrade-one, variable-count removal and reward additions automatically. The
next priority is extending authoritative discovery/admission to additional
interaction families, with events used as representative tests. Brain Leech/Zen Weaver
research remains useful, but adding those named rows is no longer the default
next assignment. Dedicated handlers may still be needed for custom interactions.

The existing frozen contract binds operation/count/domain before the parent
choice. Discovering a selector afterward cannot silently replace that contract.
The new successor resolves this timing/ownership issue with two-stage admission
and truthful accounting for effects of an already-dispatched parent action. Read
its contract and the [generic plan](PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md) before
extending it.

## What is implemented and what is demonstrated

| Capability | Current evidence and limits |
| --- | --- |
| Generic discovery successor | Shared fixed-upgrade1..8, removal1..8 and reward-add1..8 without event-name registration; v4 multi-upgrade native-to-Python fixtures and cumulative child evidence; v5 release Cheese/Gorge add-two resolved live |
| Preserved shared event flow | Functional parent composes ordinary choices, sequential item/card children and explicit Proceed/map handoff; immutable host decision-provider seam |
| Shared card mechanics | Add/remove/upgrade/transform, explicit min/max, confirmation, reference identity and exact effects; generic fixtures are not native all-event support |
| Exact native event rows | Cheese/Gorge add-two-of-eight; Aroma/Maintain Control and Sapphire/Eat upgrade-one from domain2..64 |
| New Aroma/Sapphire paths | Actual native/controller fixtures and reproducible compile-only builds; no installable release or live evidence |
| Previous live paths | Ordinary Smith upgrade-one, Cheese add-two, Dense Vegetation continuation, one shop card purchase/close/map, and bounded potion/relic acquisition in predecessor releases |
| Not implemented generically | Multiple-offer item sets, variable upgrade/transform minima, optional/scrolling selectors, repeated custom choices, event combat and custom/minigame surfaces |

Events may require multiple cards; ordinary rest-site Smith upgrades exactly one.
Do not collapse these requirements. No event has complete all-branch evidence;
the census contains 68 concrete types, including ancient/deprecated ones, without
proving runtime eligibility. Previous live results do not automatically validate
newly composed releases. Strategic event choice and natural discovery are separate.

## Verification and frozen artifacts

`generic_event_v3` is functionally accepted with independent source review,
production-native integrations, pinned compile-only native builds and a frozen
aggregate. Exact counts and identities are recorded in the
[v3 ledger](research/PHASE_1_GENERIC_EVENT_V3_ACCEPTANCE.md). All sixteen predecessor
identities remain unchanged. This gate does not provide release or live evidence.

`generic_event_v2` is functionally accepted:545 focused checks, including11
production-native integrations, independent source review and exact pinned
native compilation. Its32-file source identity, reproducibility and frozen gate
are recorded in the [v2 ledger](research/PHASE_1_GENERIC_EVENT_V2_ACCEPTANCE.md).
The following v1 and predecessor results preserve their own acceptance scope.

`generic_event_v1` is functionally accepted and frozen: 200 native assertions,
34 wire checks, 33 host tests and 20 integration checks, including four through
production native hooks to Python. Independent review and candidate/frozen
aggregate gates passed; four native builds matched byte for byte. Exact source,
contract, dependency and result identities are retained in the
[generic acceptance ledger](research/PHASE_1_GENERIC_EVENT_V1_ACCEPTANCE.md).
The real EventSynchronizer dispatch lifecycle remains a live-validation gate.

`event_card_operations_v1` is functionally accepted and frozen:

- 675 checks across 19 offline suites; independent review passed.
- 66-file manifest SHA-256:
  `8e5d4ef4701929f2543a09ac41875c4479b59bf98e37286685cc86cbb5df053d`.
- Source inventory SHA-256:
  `97735acc3534bbe1841032dd10a361567b3b6f90e008992b2ab2fd3718fd7967`.
- Final result: `/private/tmp/event-card-operations-root-frozen-a/result.json`,
  SHA `4ac1377eeb96c1e94c986002c983dadbf6d29ab722b122b3f3f456dc74490cd7`.
- Four matching Release native builds across candidate/frozen gates: 68,096 bytes,
  SHA `2773b2a2d197a9fee82dce8488a0c6752d6dc4db0b67f8eb90d20769438f9577`.
  Target assemblies were never executed by these checks.
- Repository regression: 1,300 passed plus one sandbox-only localhost socket-bind
  failure; the unchanged inert fixture passed separately with local permission.
  All 1,301 collected cases passed across those two runs, not one clean full run.

Preserve this component and its thirteen predecessors, plus `generic_event_v1`, `generic_event_v2` and `generic_event_v3`:
seventeen historical functional successors at that checkpoint; lifecycle and both
release successors brought that total to twenty; diagnostic release v3 brings the
current total to21, plus the original48-file bridge boundary. Do not edit frozen README,
source identity, contracts, API/schema or derivation files to implement the new
direction. Use a reviewed successor. Temporary outputs may disappear; the ledger
and repository identities are the retained reference, not permission to reconstruct
missing outputs or execute historical commands.

## Preserved predecessor code map

Under `bridge/Sts2AgentBridge/successors/event_card_operations_v1/`:

- `core/EventCardOperationsV1PolicyCatalog.cs`: the closed three-row catalog.
- `native/EventCardOperationNativeRegistry.cs`: named native classification.
- `native/EventCardOperationBinding.cs`: pre-dispatch row/domain/deck binding.
- `native/EventCardSelectionV1NativeAdapter.cs`: shared exact upgrade adapter.
- `native/PinnedEventOrchestratorV1NativeAdapter.cs` and
  `native/ProductionEventOrchestratorV1ChildFactories.cs`: parent/child ownership.
- `wire/`, `host/event_orchestrator_host.py`: public validation and closed policies.
- `native_tests/`, `native_card_tests/`, `integration_tests/`: actual-source
  composition and cross-language tests, useful successor controls.

The new generic successor source-links the actual frozen card session and
preserves its own explicit derivation/reuse manifest. The predecessor
`event_orchestrator_v1` brokers remain useful reference for other families. The [Brain/Zen result](research/PHASE_1_EVENT_CARD_FOLLOWUP_RESULT.md) and
[preview result](research/PHASE_1_EVENT_CARD_PREVIEW_RESULT.md) preserve remaining
static questions. Do not rerun their closed inspection invocations by default.

## Operational state and user preferences

GENERIC-EVENT-V3-SMOKE-V1 completed one failed invocation with prepare_candidates
and full owned cleanup. Game stopped,port closed,base verified,overlay absent.
No active campaign or credential remains. All three generic campaign identities
are historical and must not be reused. Preserve all22 frozen successors.
Next diagnose the candidate-binding/initial-candidate-state subchecks offline;
no new game setup is needed until a separately gated fresh release is ready.

The user has authorized continued event development, parallel work where useful,
and bounded live campaigns when needed; that explicit session authority persists.
The release contract supplies the current bounded campaign scope. Continue to
pass the appropriate release/preflight gates before using that authority; do not
inherit closed state or treat it as permission for unrelated capabilities. Ask
for additional authorization only if an actual new scope requires it. Give the
exact required game state when an installable test is ready, so the user can
prepare the intended interaction.
Profile 3 is the established live test profile. The user waived repeated unmodded
launch checks; retain other required quit/quarantine/purge/base/closed checks.
Use the appropriate current release's tools and ledger, not historical state
hashes or credentials. The v3 diagnostic release has completed its single invocation and cleanup; named
event-card functional components remain separate.

Use supported computer-use tools. The user offered
`steam://rungameid/2868840`, but the browser route was previously rejected by its
URL security policy. Do not bypass that rejection; manual launches worked.
Steam capture previously returned `-3811` while Finder and game capture worked.
That is separate from the historical `room_interaction_timeout`, which had no
accepted summary. Neither is established fixed by a new session. Retest capture
when relevant to live work; it is not a prerequisite for repository documentation.
Never reconstruct discarded responses or retry a historical uncertain action.

No profile/save filesystem access, Steam Cloud changes, retained live corpus,
remote Git operations or unrelated capability expansion. Local commits are fine;
preserve user changes. Do not fetch, push, reset or merge older main for this task.

## Local verification tools

- Python: `/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python`;
  use the 23cf checkout as cwd and verify module origins. The 23cf `.venv` is absent.
- SDK 9.0.303: `/private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet`.
- Pinned game: v0.107.1 / Steam build23811903 / macOS arm64; reference manifest
  `manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json`.
- The accepted offline checker is
  `bridge/Sts2AgentBridge/successors/generic_event_v3/check.py`; read its
  CLI and use a fresh `/private/tmp` scratch directory. It builds snapshots,
  verifies the two compile-only reference hashes and never executes target code.
- Coordinate a single SDK build lane across parallel agents; use offline package
  configuration and isolated outputs. Do not generate `obj`/`bin` in frozen trees.

Do not rerun the full functional gate for documentation-only edits. Verify links,
diff consistency and frozen identities, then leave a clear local checkpoint.
