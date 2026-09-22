# Headless implementation backlog

Updated 2026-09-22. This document owns remaining headless assignments;
[the engine guide](HEADLESS_ENGINE.md) owns usage and supported gameplay.
The [original assessment and completed-batch chronology](archive/HEADLESS_FULL_GAME_IMPLEMENTATION_2026_09_21.md)
is historical. Its old “partial” and “remaining” labels are not current tasks.
Original HF identifiers are retained below for continuity.

## Current scope and completion

The independent `game/headless` engine implements all five solo characters,
A0–A10, either Act 1 region, Hive, Glory and the Architect ending on pinned build
0.107.1, with all content unlocked. Cards, powers, monsters, items, generation,
shops, rests, events and Ancient choices use shared game-owned rules and plain
serializable continuations. Gameplay does not depend on projections or encoders.

| Workstream | Current status | Evidence and ownership |
| --- | --- | --- |
| HF-01–10: scope, core state, commands, RNG, continuation and validation | Implemented game-engine foundation; public-contract expansion belongs to HF-44–47 | [Engine architecture and ownership](HEADLESS_ENGINE.md#ownership), [RNG](#hf-05--match-target-rng-algorithms-domains-and-consumption) |
| HF-11–18: combat, card lifecycle and reachable solo card families | Implemented catalogs/rules; interaction conformance remains bounded | [Cards and character rules](HEADLESS_ENGINE.md#playable-characters) |
| HF-19–23: encounters and monster lifecycle | All regional normal/elite/boss rosters implemented; 12 bosses covered by native campaigns | [Monster comparisons](evidence/native_focused_behavior_2026_09_20.md), [regional campaigns](evidence/headless_generated_route_2026_09_20.md#all-regional-bosses) |
| HF-24–27: relics and potions | Solo content, exclusive items, generation and shared hooks implemented | [Character items](evidence/playable_characters_2026_09_20.md), [item comparisons](evidence/native_item_status_2026_09_20.md) |
| HF-28–38: initialization, generation, rooms, rewards, acts and difficulty | Implemented for the declared profile through victory | [Ascensions](evidence/headless_ascensions_2026_09_20.md), [native character campaigns](evidence/native_character_campaigns_2026_09_21.md) |
| HF-39–43: events and Ancients | Full solo roster implemented; 9,376 native cases plus separate Architect ending coverage | [Event branch scope](evidence/native_event_branches_2026_09_20.md) |
| HF-52: playable characters | All five implemented; the four added characters have A0/A10 native victories | [Campaign evidence](evidence/native_character_campaigns_2026_09_21.md), [focused interaction audit](evidence/native_character_interactions_2026_09_21.md) |
| HF-44–47: public observations, encoding, datasets and operational adapters | Open for the complete game | Assignments below |
| HF-48: fidelity acceptance | Retained full campaigns and focused comparisons pass; ongoing discrepancy-driven work | [Acceptance task](#hf-48--accept-complete-run-fidelity-and-close-coverage-gaps) |
| HF-49–50: throughput and delivery | Test-overhead improvements landed; training/search workloads and full-game consumer delivery remain | Assignments below |

“Implemented” describes executable rules, not exhaustive native equivalence.
Boosted native campaigns are accepted; a normal-HP test-policy victory is not a
completion gate. Low-HP/death/revival rules need separate focused comparisons.
Multiplayer, alternate modes and progression-dependent unlock histories are
excluded. Native UI and on-disk saves are not simulated by Python JSON restoration.

### HF-05 — Match target RNG algorithms, domains and consumption

Native algorithms, stream ownership, generation and selected complete trajectories
are implemented and compared. The September 21 character audit corrected the
random-orb seed salt: native's `CombatOrbGeneration` property uses the
`CombatOrbs` enum name (`combat_orbs`). The engine keeps its existing logical
stream key while matching that native seed. New random-orb choices and suffixes
are compared directly; old private saves are rejected by combat/run v47/v68.

Further RNG work must start from a concrete caller, differing sequence or missing
mechanism probe. Broader seeds are evidence expansion, not a known missing RNG
implementation. Profile/lobby discovery and unlock history remain excluded.

## Next bounded implementation assignment

The four-character interaction audit is complete for its declared probes. It
corrected Gold-Plated Cables applying to direct passives and the random-orb seed
salt. Silent temporary Dexterity, Regent star-spend hooks and Necrobinder retained
cost modifiers match the recorded native cases. See the
[audit, exact checks and limits](evidence/native_character_interactions_2026_09_21.md).

The old simulator/reduced backend and its research pipelines were retired on
2026-09-22 by user request. They are not implementation starting points or
compatibility targets. Keep the current engine and production bridge independent.

**Next: HF-44, public full-run observations.** Implement one versioned read-only
adapter over the mature game engine. Start with states for all five characters
and a combat → reward → map sequence, including a nested card choice. Preserve
the independent rules layer; do not add projection work to individual cards.
Then carry the same decisions through HF-45–47. This audit does not implement
those external adapters or certify every character/item permutation.

## Open assignments

### HF-44 — Expose sufficient public run state and observable history

- **Implement:** define a versioned public adapter over `RunEngine` with visible deck
  instances/modifiers, relics/counters, potions, character resources, act/floor,
  ascension, map context, public pile information and pending decision candidates.
  Represent Stars/Forge, Osty and orbs without exposing hidden RNG or draw order.
  Distinguish unknown, absent and empty fields.
- **Acceptance:** publicly different inventories remain distinguishable; states
  differing only in hidden information produce identical observations. Reading
  observations changes neither game state nor RNG. Exercise all five characters,
  a nested combat choice and a combat/reward/map handoff.
- **Start:** `game/headless/run/engine.py`, `game/headless/core/actions.py` and
  `game/headless/run/actions.py`. Keep the adapter outside the game-rule package;
  the retained bridge wire codec is not a full-game headless contract.

### HF-45 — Encode public decisions without dropping legal choices

- **Depends on:** HF-44's versioned public view.
- **Implement:** build actor encoders and candidate scoring for every
  supported action/resource family using HF-44. Derive capacities and categorical
  vocabularies from reachable states rather than the retired fixed limits. Version
  the representation and checkpoints; keep private identifiers and seeds out of model features.
- **Acceptance:** every legal candidate survives encoding/collation, including
  duplicate cards, multi-selection, potions and event actions. Permutation and
  hidden-information checks pass. No legacy fixture compatibility is required.
- **Start:** HF-44's action schema and focused direct-engine scenarios.

### HF-46 — Carry full-run semantics through datasets and artifacts

- **Depends on:** HF-44/45.
- **Implement:** record trajectories, policy datasets and reports to
  retain the new decisions, build/rules identity, real victory/defeat and truncation.
  Preserve public history/private diagnostics separation, held-out splits and
  cancellation-safe publication. Never relabel structural fixtures as real runs.
- **Acceptance:** a recorded multi-act run round-trips through dataset and training
  loaders without losing candidates or changing its outcome. Unsupported artifact
  versions reject explicitly; retired artifacts have no compatibility requirement.
- **Start:** HF-44/45 outputs and the engine's game-owned command boundaries.

### HF-47 — Deliver full-game agent execution and CLI

- **Depends on:** HF-44–46 for the delivered adapter.
- **Implement:** add agent execution, bounded workers and recording around
  the full engine and HF-44–46 adapters. Reuse `sts-headless-play` for direct gameplay;
  add full-run configuration to the agent-facing path without another simulator.
  Include a public-only chooser for every legal decision family.
- **Acceptance:** a documented command resets, steps, records and terminates the
  supported scope; worker execution reproduces it. Budgets, cancellation, illegal
  actions and cleanup remain bounded. Pure headless commands do not import Torch
  or Gymnasium unnecessarily. Policy strength is a separate research question.

### HF-48 — Accept complete-run fidelity and close coverage gaps

- **Status:** selected native campaigns, complete declared event branches and
  focused item/monster/character interactions have retained evidence. No unresolved
  gameplay mismatch is identified by the September 21 character audit.
- **Ongoing work:** choose a concrete untested mechanism or observed mismatch,
  reproduce it natively, and add one focused regression after fixing it. Campaign
  inventories exercise a small portion of possible combinations; additional
  character-specific card/item compositions and low-HP boundaries remain useful.
- **Acceptance:** compare relevant legal decisions, resources, ordered effects,
  RNG consumption and JSON continuation. Record any canonical representation
  differences. Do not treat metadata checks as gameplay proof or repeat large
  seed × difficulty × inventory matrices without a distinct question.
- **Start:** existing `tools/native_combat_oracle` and `tests/headless` fixtures;
  preserve native isolation and original retained evidence identities.

### HF-49 — Measure and improve full-run/branching performance

- **Status:** measured test/catalog/restore overhead improvements are implemented;
  full training/search throughput is not established by pytest wall time.
- **Implement:** measure reset, step, observation/candidate creation, snapshot,
  restore, branching and worker throughput/memory on representative full-game
  workloads. Optimize measured bottlenecks through existing mechanisms.
- **Acceptance:** matched before/after workloads improve while native decisions,
  deterministic traces and worker isolation remain unchanged. Set throughput
  targets from actual training/search needs.

### HF-50 — Deliver a reproducible supported simulator package

- **Depends on:** the chosen HF-44–49 consumer milestone.
- **Implement:** reconcile headless integration with main, preserve concurrent
  bridge work, and validate clean installation of canonical packages/commands.
  Document supported build/content/settings and full-run examples without bundling
  game binaries or introducing a second package pipeline.
- **Acceptance:** a clean declared Python 3.10+ environment installs, resets,
  executes, records and restores the supported scope. Package/source identities
  and relevant integration evidence match the released behavior.

## Excluded and optional work

HF-51 (replace Python rules with a native backend) is an optional investigation,
not a completion dependency. HF-53 multiplayer and HF-54 alternate modes remain
excluded. Supporting later game builds requires an explicit new compatibility
scope; the present evidence applies to the pinned build. Arbitrary unlock/profile
histories are also outside this project scope. Strong policies and win-rate
optimization follow a usable agent interface; they are not game-rule acceptance.
