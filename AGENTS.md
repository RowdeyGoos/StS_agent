# AGENTS.md

This file is the working guide for coding sessions in this repo.

Use it for:

- where to read first
- what not to break
- how to validate changes
- which docs to update when the project evolves

Do not treat this file as the full project description. For that, follow the reading order below.

## Current event-work entry point

For event coverage or a session handoff, begin with
[the Astra handoff](docs/PHASE_1_ASTRA_HANDOFF.md),
[current status](docs/PHASE_1_CURRENT_STATUS.md) and
[generic event handler plan](docs/PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md), then
follow the reading order below. The active integration checkout is the existing
23cf worktree named in the handoff; local main is older. The new
[generic successor contract](docs/PHASE_1_GENERIC_EVENT_V3_CONTRACT.md) and
[acceptance ledger](docs/research/PHASE_1_GENERIC_EVENT_V3_ACCEPTANCE.md) describe
shared upgrade-one, variable-count removal and reward-card addition discovery
with automatic or manual confirmation and no named caller entries. Other interaction
families remain open. Expand by authoritative shared family, using event names
as tests. Preserve all seventeen frozen successor trees, their contracts and
identities, plus the original bridge; new behavior belongs in a reviewed successor.

For the current live test, read the
[generic release v3 diagnostic contract](docs/PHASE_1_GENERIC_EVENT_RELEASE_V3_CONTRACT.md)
and [v3 ledger](docs/research/PHASE_1_GENERIC_EVENT_RELEASE_V3_ACCEPTANCE.md).
The release is accepted and frozen as successor21 and installed awaiting manual
launch at fresh Profile3 Cheese initial options, Gorge untouched. It reports
finite last-capture diagnostics without changing gameplay predicates or frozen
core/wire/host semantics. The v2 timeout cause is still unknown; only fixtures
have distinguished pending binding and selector preparation. Preserve all21
source identities. Use only v3 tools and its ledger's current installed state for
one invocation and subsequent cleanup. Both prior failed campaigns were purged;
their state identities are historical and must not be reused.

## Read This First

When starting a fresh session, read in this order:

1. [README.md](README.md)
2. [DECISIONS.md](DECISIONS.md)
3. [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)
4. [ROADMAP.md](ROADMAP.md)
5. [game/simulation/core.py](game/simulation/core.py)
6. [game/simulation/encoding.py](game/simulation/encoding.py)
7. [game/cli/train.py](game/cli/train.py)

For work on the full-game program, live integration, shared contracts, or
long-term agent architecture, also read:

1. [docs/LONG_TERM_ARCHITECTURE_ROADMAP.md](docs/LONG_TERM_ARCHITECTURE_ROADMAP.md)
2. [docs/PHASE_0_TARGET_CHARTER.md](docs/PHASE_0_TARGET_CHARTER.md)
3. [docs/PHASE_0_PROFILE_FIXTURE_PLAN.md](docs/PHASE_0_PROFILE_FIXTURE_PLAN.md)
4. [docs/PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md](docs/PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md)
   and its [sanitized result](docs/research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md)
   plus the approved
   [D1B sidecar scope](docs/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md)
   and its [sanitized result](docs/research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md)
   before any further profile-filesystem work. D1C was reviewed, deliberately
   unselected/skipped, and never executed; its fail-closed predicate is
   incorporated into the
   [baseline fingerprint request](docs/PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md).
   Its first approved invocation stopped before target-content access because
   the runner used the wrong fixed profile-component construction; see the
   [sanitized attempt-1 result](docs/research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md).
   No corrected rerun is currently authorized. No earlier approval authorizes
   it or a later copy, parse, Cloud, restore, or launch step
5. the active phase plan, currently
   [docs/PHASE_1_INTEGRATION_SPIKE.md](docs/PHASE_1_INTEGRATION_SPIKE.md)
6. [docs/PHASE_1_CURRENT_STATUS.md](docs/PHASE_1_CURRENT_STATUS.md)
   for the living `R0i` capability, evidence-level, residual, and next-target
   summary
7. [docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md](docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md)
   for the preserved elite-continuation and actor-ready headless dependency graph,
   exact ownership, acceptance gates, and stop boundaries, plus its
   [acceptance ledger](docs/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md)
   and, for actor representation/model work, the frozen
   [encoding schema](docs/research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json)
8. [docs/MULTI_AGENT_EXECUTION.md](docs/MULTI_AGENT_EXECUTION.md) before
   dispatching implementation or review work
9. [docs/PHASE_1_NEXT_INCREMENT_PLAN.md](docs/PHASE_1_NEXT_INCREMENT_PLAN.md)
   and its
   [acceptance ledger](docs/research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md) for
   the completed predecessor contracts and exact evidence
10. [docs/PHASE_1_PARALLEL_EXECUTION_PLAN.md](docs/PHASE_1_PARALLEL_EXECUTION_PLAN.md)
   for the completed foundational live/headless packet graph
11. [docs/PHASE_1_STATIC_AUDIT_SYNTHESIS.md](docs/PHASE_1_STATIC_AUDIT_SYNTHESIS.md)
12. [docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md](docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md)
   for the staged bridge boundary and live acceptance gates
13. [bridge/Sts2AgentBridge/README.md](bridge/Sts2AgentBridge/README.md)
   before bridge build, test, package, or verifier work
14. [docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md](docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md)
    for the exact initial repository artifact and detailed `R0a`/`R0b` results
15. [docs/PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md](docs/PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md)
    as the preserved first-campaign authorization boundary. It is not standing
    authorization for any new operator-config write, overlay change, launch,
    live probe, teardown, or rollback work

For delegated or parallel work, read
[docs/MULTI_AGENT_EXECUTION.md](docs/MULTI_AGENT_EXECUTION.md) before assigning
write ownership. These additional documents are not mandatory for an isolated
combat-prototype change unless that change affects a full-game contract or
program decision.

## Doc Roles

- `README.md`: user-facing overview, setup, and run commands
- `AGENTS.md`: session workflow and repo invariants
- `DECISIONS.md`: why important architecture and training choices were made
- `docs/PROJECT_CONTEXT.md`: current technical state of the simulator
- `ROADMAP.md`: likely next steps and current priorities
- `docs/LONG_TERM_ARCHITECTURE_ROADMAP.md`: strategic destination and phase order
- `docs/PHASE_0_TARGET_CHARTER.md`: initial benchmark target and open gates
- `docs/PHASE_0_PROFILE_FIXTURE_PLAN.md`: dedicated profile construction,
  privacy, reset, and validation plan
- `docs/PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md`: exact first
  metadata-only profile read scope; its approved hash is preserved and does not
  authorize broader follow-up work
- `docs/research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md`: sanitized D1
  local-boundary result, caveats, and historically redacted entries
- `docs/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md`: preserved exact
  approved D1B scope for testing the current shallow state against the
  statically predicted backup-sidecar pair
- `docs/research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md`: sanitized
  D1B current-projection pass, execution attempts, and strict limits
- `docs/research/PHASE_0_PROFILE_BACKUP_SIDECAR_RESULT_REVIEW.md`: independent
  hash-bound D1B execution-result, privacy, and gate-disposition review
- `docs/PHASE_0_PROFILE_RECOVERY_UNIT_METADATA_REQUEST.md`: preserved exact D1C
  metadata-only alternative; reviewed, deliberately unselected/skipped, and
  never executed
- `docs/research/PHASE_0_PROFILE_RECOVERY_UNIT_SCOPE_REVIEW.md`: independent
  hash-bound review of the preserved D1C alternative
- `docs/PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md`: current exact, frozen
  two-sample byte-fingerprint scope with the D1C fail-closed predicate as its
  mandatory pre-read gate; attempt 1 stopped and no corrected invocation is
  authorized
- `docs/research/PHASE_0_PROFILE_BASELINE_HASH_SCOPE_REVIEW.md`: independent
  exact-hash authorization, race/claim, canonicalization, and privacy review of
  the baseline-fingerprint request
- `docs/research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md`: sanitized
  fail-closed first-invocation result, implementation defect, and fresh-rerun
  approval boundary
- `docs/research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_REVIEW.md`: independent
  hash-bound execution-stage, static-path, privacy, and rerun-authorization
  review of attempt 1
- `docs/research/PHASE_0_PROFILE_BASELINE_HASH_CORRECTED_RUNNER_SYNTHETIC_VALIDATION.md`:
  disposable no-user-data validation of the corrected path binding, byte
  ceiling, result markers, canonicalization, and fail-closed cases
- `docs/research/PHASE_0_PROFILE_METADATA_RESULT_REVIEW.md`: independent
  historical hash-bound review of the sanitized D1 result and exact D1B scope
- `docs/PHASE_1_INTEGRATION_SPIKE.md`: current live/fast-backend evidence plan
- `docs/PHASE_1_CURRENT_STATUS.md`: living bridge progress, demonstrated versus
  fixture-only evidence, residuals, exclusions, and next bounded target
- `docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md`: preserved elite-continuation and
  actor-ready headless packets, dependencies, ownership, gates, and handoff
- `docs/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md`: preserved successor packet,
  integration, review, evidence, telemetry, and live-cleanup ledger
- `docs/research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json`: exact frozen
  `headless_encoding_v1` API, features, normalization, joins and fingerprint input
- `docs/PHASE_1_NEXT_INCREMENT_PLAN.md`: completed predecessor increment and
  preserved packet contracts; its research ledger owns exact acceptance results
- `docs/PHASE_1_PARALLEL_EXECUTION_PLAN.md`: completed foundational live/headless
  packet graph and preserved ownership/acceptance contracts
- `docs/PHASE_1_STATIC_AUDIT_SYNTHESIS.md`: preserved pre-implementation
  candidate shortlist and ordered gates
- `docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`: preserved initial project-owned
  live-bridge boundary, staged capabilities, and acceptance gates
- `bridge/Sts2AgentBridge/README.md`: implemented `R0i` build, contract,
  controllers, verifier, package, and operational-boundary guide
- `docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md`: preserved initial
  artifact identities and gate results plus detailed `R0a`/`R0b` live evidence
- `docs/PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md`: preserved exact approval-bound
  first live smoke, teardown, rollback, privacy, and claim boundary; historical,
  not reusable authorization
- `docs/MULTI_AGENT_EXECUTION.md`: parallel-development operating model
- `docs/PHASE_1_ASTRA_HANDOFF.md`: current integration checkout, evidence, user direction and operational state
- `docs/PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md`: active generic discovery/admission design and acceptance criteria; not an implemented contract
- `.codex`: ultra-short bootstrap note for fresh Codex sessions

## Core Working Assumptions

These assumptions describe the current combat research path. They are not the
end-state full-game contracts.

- `CombatEnv` is the main RL-facing environment.
- The structured observation is the source of truth for debugging and tests.
- `ObservationEncoder` is the RL representation layer.
- Multi-enemy combat uses stable enemy slots. Dead enemies stay in the encounter list so target indices and encoded slots do not shift.
- The discrete action space is fixed-size and relies on legal-action masking.
- Reward is intentionally shaped toward winning while preserving player HP.

## Invariants To Preserve

- Keep structured observations and encoded observations conceptually separate.
- Keep randomness explicit and seeded through the environment RNG or objects created from it.
- Avoid global state.
- Keep game state serializable and easy to inspect.
- Preserve compatibility with the simple single-enemy path unless there is a good reason to change it.
- Maintain Python `3.10+` compatibility unless the project requirement is intentionally raised.

## If You Change Observation Or Action Semantics

Observation changes usually require updates to:

- `game/simulation/core.py`
- `game/simulation/encoding.py`
- `game/simulation/action_features.py`
- heuristic logic in `game/agents/baselines.py`
- tests
- demo formatting in `game/cli/demo.py`

Action changes usually require updates to:

- `game/simulation/actions.py`
- `game/simulation/core.py`
- `game/simulation/encoding.py`
- `game/simulation/action_features.py`
- action-mask tests

## File Map

- `game/simulation/`: combat rules, mutable state, observations, encoding, and factories
- `game/agents/`: baselines, DQN-family agents, PPO, devices, and persistence
- `game/training/`: PPO worker infrastructure and semantic profiling
- `game/analysis/`: traces, rendering, brute-force search, regret, and uncertainty
- `game/cli/`: real command-line implementations
- `game/__init__.py`: stable symbol-level public API
- `configs/`: reusable training and sweep configurations
- `manifests/game-builds/`: sanitized immutable identities for pinned game builds
- `tests/simulation/`: combat and encoding coverage
- `tests/agents/`: model architecture and persistence coverage
- `tests/training/`: trainer, profiling, and worker coverage
- `tests/analysis/`: trace and oracle coverage
- `tests/cli/`: command configuration and sweep coverage

Use canonical subpackage paths. Do not reintroduce flat-module aliases or root
CLI wrappers; stale imports and commands should fail visibly instead of creating
a permanent second API surface.

## Common Validation Commands

Setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

Regression checks:

```bash
python3 -m compileall game tests
PYTHONPATH=. python3 -m pytest -q
```

Manual runs:

```bash
sts-demo
sts-train --policy compare --episodes 500 --eval-episodes 100
sts-train --policy heuristic --encounter-set overgrowth_easy --episodes 200
```

## When Editing

- Prefer minimal, explicit changes over clever abstraction.
- Keep the simulator readable as an RL research playground.
- Update docs when core assumptions change.
- Add or update a `DECISIONS.md` entry when you make a meaningful architecture or training-default choice.
- Update `ROADMAP.md` when priorities or likely next steps shift materially.
