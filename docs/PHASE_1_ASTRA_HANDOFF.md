# Astra handoff — generic event handler

Updated 2026-09-08 after the successful direct card-16 live test and cleanup.
This is the current handoff. Historical attempts, artifact hashes and campaign
state belong in the linked acceptance ledgers, not the next operator's commands.

## Start here

- Authoritative checkout: `/Users/rowdeygoos/.codex/worktrees/23cf/StS_agent`.
- Branch: `codex/phase1-actor-ready-integration`. Check HEAD and user changes first.
- Implementation checkpoint: `6978943` (direct card-16 test); live result and
  cleanup checkpoint: `dc5dbfc`. Documentation updates follow these commits.
- Saved main at `/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent` is older;
  use its Python environment with the authoritative checkout as cwd.
- No test campaign is installed. Last checks: game stopped, bridge port closed,
  429 unchanged base-game files, zero overlays; all four test files removed.
- The original bridge and all 32 accepted successors are frozen. Implement the
  next change in a successor; do not edit frozen sources or identity manifests.

Read [AGENTS.md](../AGENTS.md), this handoff, the
[current plan](PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md), then the
[v10 acceptance ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md)
and [v10 contract](PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md).
For underlying semantics use the [G7 contract](PHASE_1_GENERIC_EVENT_V7_CONTRACT.md)
and [G7 ledger](research/PHASE_1_GENERIC_EVENT_V7_ACCEPTANCE.md).
The actor-ready/headless plans preserve completed work; they are not the active
event-development queue.

## What the latest test established

The user requested a simple direct click on one of cards 16–20, explicitly
removing our clipping/viewport proof requirements. In their same 20-card Aroma
of Chaos setup, v10 chose Let Go and dispatched `_GuiInput(select)` to native
holder slot15 (card16), without scrolling. The exact original appeared in the
preview, confirmation completed the transformation, and Proceed reached the map.

One invocation resolved: two parent and two child actions attempted, accepted
and reconciled; one completed card child; six reads; `map_ready`. The final UI
also showed the map. The final `effects=unverified` field belongs to the latest
parent action; it does not erase the cumulative verified card-child completion.

**Direct selection of an allocated off-screen card works in this setup.**
V7/v8/v9 stopped at our admission checks before trying card input; those failures
were not evidence that the native click could not work. V10 removed all geometry
reads. Do not restart clipping-parent diagnosis, impose a ten-card limit, or add
a visibility certificate to repeat this answered question.

V10 is a controlled test build: it deliberately exposes only slot15. General
selection of all eligible holders is the next implementation step. This test
covers fixed-one transformation, not live variable-count transformation or every
selector. Allocated off-screen holders and cards with no allocated holder remain
different cases; the latter may need scrolling/rebinding.

## Current capability and evidence

| Shared capability | Accepted evidence |
| --- | --- |
| Ordinary choices, sequential children, Proceed/map | Generic parent and host; bounded live event paths |
| Card rewards | Generic positive variable selection up to eight; Cheese/Gorge add-two live in release v5 |
| Removal | Generic positive variable selection up to eight; native/controller fixtures |
| Upgrade | Generic fixed counts 1–8 with exact preview mapping; native/controller fixtures; older Smith single-upgrade live |
| Transformation | G7 fixed and positive variable counts up to eight, exact preview and selected-only replacement journal; native/controller fixtures; release v10 fixed-one card16 live |
| Singleton potion/relic reward | G6/G7 shared handling and fixtures; Potion Courier/Ransack singleton potion live in release v6 |

Event names identify ownership and test cases; supported shared interactions do
not require a new production event-name registration. Choice strategy remains
in the replaceable host decision provider. Generic handling does not imply
all-event, all-branch or complete-run support. See the
[coverage matrix](research/PHASE_1_EVENT_COVERAGE_MATRIX.md).

## Next development step

Derive a successor that removes v10's `TestTargetSlot`/`TargetCard16` restriction
and exposes all legal, allocated holders through the existing action path.
Preserve complete domain binding, exact holder/model identity, native enabled
state, deferred-callback checks, exact preview and selected-only completion.
Keep the working direct input path free of viewport/fit checks. Establish which
other selector adapters still impose layout restrictions before extending them;
the live finding is specifically the transform adapter's path.

Use focused native and full-client tests for visible and off-screen targets,
missing/reassigned holders and existing confirmation modes. Reuse accepted
unchanged dependency evidence; do not repeat unrelated full matrices just to
answer the same click question. See the plan for remaining features and limits.
No new implementation or live setup was started by this documentation update.

## Code map

Paths below are relative to `bridge/Sts2AgentBridge/successors/`.

| Location | Purpose |
| --- | --- |
| `generic_event_v7/native/GenericEventV7Hooks.cs` and `GenericEventV7Binding.cs` | Owned native request/screen discovery and parent/child identity |
| `generic_event_v7/native/PinnedGenericEventV7NativeAdapter.cs` | Parent capture and child integration |
| `generic_event_v7/native/GenericEventV7TransformState.cs` | Authoritative transformation effect observations |
| `generic_event_v7/host/generic_event_host.py` and `card_transform_host.py` | Bounded orchestration and replaceable decisions |
| `generic_event_release_v10/gameplay/GenericEventV7TransformAdapter.cs` | Live-proven direct input; test-only slot15 mask and dispatch guard |
| `generic_event_release_v10/gameplay_tests/OffscreenFixtures.cs` and `integration/OffscreenSocketFixture.cs` | Direct-target native and socket cases |
| `generic_event_release_v10/production/Sts2AgentBridgeGenericEventV10.csproj` | Exact production source composition |
| `generic_event_release_v10/check.py`, `source_identity.json`, `derivation.json` | Accepted gate and frozen source closure |

## Validation and operations

V10's single frozen aggregate passed 21 direct-target assertions, six socket
cases, 386 verifier, 966 runtime, 23 transport and 13 client checks, plus release
and lifecycle checks. Independent review verified the 73 owned files, dependency
identities and four identical production builds. Exact hashes are in its ledger.
Frozen G7 regressions were retained as earlier evidence, explicitly not rerun.

Python: `/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python`.
SDK 9.0.303: `/private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet` (verify availability).
Pinned game: v0.107.1, Steam build23811903, macOS arm64; use the repository manifest.
Build in disposable snapshots, not frozen source directories. Documentation-only
changes need link/diff checks, not gameplay test suites or a game launch.

For a future live test, prepare the concrete build first and tell the user exactly
when to start the game. Profile3/manual launch is established. Keep user setup
brief and relevant. Do not reuse any closed campaign hash, credential or spent
client invocation. Normal quit and owned cleanup remain part of each campaign.
No profile/save/Cloud access or automatic launch is needed. Do not add permission
questions already answered by the user's event-development scope. Follow current
session delegation rules rather than historical requests embedded in old docs.
