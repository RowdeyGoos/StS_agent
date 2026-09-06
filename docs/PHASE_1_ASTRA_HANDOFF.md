# Astra handoff — generic event support

Updated 2026-09-06 after implementing the requested generic handler. Historical
attempts and cleanup remain in their linked acceptance ledgers and Git history.
This update includes offline implementation and validation; no live campaign
was started.

## Current implementation update

The requested handler is implemented in
`bridge/Sts2AgentBridge/successors/generic_event_v1`. Read its
[contract](PHASE_1_GENERIC_EVENT_V1_CONTRACT.md) and
[acceptance ledger](research/PHASE_1_GENERIC_EVENT_V1_ACCEPTANCE.md) first.
It discovers standard upgrade-one interactions across unregistered event types
using scoped shared-call instrumentation, retaining pre-dispatch context/deck
and exact request/selector/parent completion. It is a functional successor;
no release, installation or live campaign was created. The historical frozen
implementation identities below remain valid for their own components.

The scope remains explicit: generic single-upgrade native support, bounded
ordinary pages and Proceed; other count/operation/custom families still need
shared authoritative boundaries. The same23cf worktree remains authoritative.

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

The new successor discovers one standard interaction family automatically. The
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
| Generic discovery successor | Shared upgrade command/screen discovery without event-name registrations; production native/hook-to-Python inert fixtures; no release or live evidence |
| Preserved shared event flow | Functional parent composes ordinary choices, sequential item/card children and explicit Proceed/map handoff; immutable host decision-provider seam |
| Shared card mechanics | Add/remove/upgrade/transform, explicit min/max, confirmation, reference identity and exact effects; generic fixtures are not native all-event support |
| Exact native event rows | Cheese/Gorge add-two-of-eight; Aroma/Maintain Control and Sapphire/Eat upgrade-one from domain2..64 |
| New Aroma/Sapphire paths | Actual native/controller fixtures and reproducible compile-only builds; no installable release or live evidence |
| Previous live paths | Ordinary Smith upgrade-one, Cheese add-two, Dense Vegetation continuation, one shop card purchase/close/map, and bounded potion/relic acquisition in predecessor releases |
| Not implemented generically | Add/remove/transform/multi-upgrade discovery, item children, optional/scrolling selectors, repeated custom choices, event combat and custom/minigame surfaces |

Events may require multiple cards; ordinary rest-site Smith upgrades exactly one.
Do not collapse these requirements. No event has complete all-branch evidence;
the census contains 68 concrete types, including ancient/deprecated ones, without
proving runtime eligibility. Previous live results do not automatically validate
newly composed releases. Strategic event choice and natural discovery are separate.

## Verification and frozen artifacts

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

Preserve this component and its thirteen predecessors, plus `generic_event_v1`:
fifteen frozen successor trees total, plus the original 48-file bridge boundary. Do not edit frozen README,
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

No campaign was left active and no cleanup was pending at the last recorded
closure. This implementation performed no fresh game/process/install check;
verify current state before a later live operation. The latest development was
offline only. No game setup is needed for the next architecture work.

The user has authorized continued event development, parallel work where useful,
and bounded live campaigns when needed; that explicit session authority persists.
This implementation starts none. Prepare a concrete campaign scope and
pass the appropriate release/preflight gates before using that authority; do not
inherit closed state or treat it as permission for unrelated capabilities. Ask
for additional authorization only if an actual new scope requires it. Give the
exact required game state when an installable test is ready, so the user can
prepare the intended interaction.
Profile 3 is the established live test profile. The user waived repeated unmodded
launch checks; retain other required quit/quarantine/purge/base/closed checks.
Use the appropriate current release's tools and ledger, not historical state
hashes or credentials. No new event-card or generic-event release exists yet.

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
  `bridge/Sts2AgentBridge/successors/generic_event_v1/check.py`; read its
  CLI and use a fresh `/private/tmp` scratch directory. It builds snapshots,
  verifies the two compile-only reference hashes and never executes target code.
- Coordinate a single SDK build lane across parallel agents; use offline package
  configuration and isolated outputs. Do not generate `obj`/`bin` in frozen trees.

Do not rerun the full functional gate for documentation-only edits. Verify links,
diff consistency and frozen identities, then leave a clear local checkpoint.
