# Shared combat Search workflow — 2026-10-11

The Search-enabled CLI now defaults to `combat_belief_v1` for controlled fixtures,
verified Vantom starts and headless Act 1 campaigns. All three use the same public
belief, native simulation, collection, distillation and reanalysis path. Historical
model versions retain their identities. Search remains experimental and opt-in.

Usage belongs in the [training guide](../AGENT_TRAINING.md#one-search-learning-workflow).
The [architecture document](../COMBAT_SEARCH_ARCHITECTURE.md) describes the public
boundary and future bridge requirements.

## Behavior and safeguards

`sts_combat_anchor_v1` records public inventory, history and reveals, plus explicit
setup timing and the supported ruleset. Producer adapters distinguish a fresh
inventory before room entry from inventory after room entry. Normal engine rules
execute entry effects once. The ruleset retains the declared fixtures' smaller
potion pool and campaigns' Ironclad pool, including generated potions.

The CLI records planning receipts by default when building new combat corpora.
Collection samples training encounters and source fights uniformly, choosing
opening versus continuation equally when available. Repeated starts retain their
source case/fight/campaign identifiers and receive separate episode identifiers
and frozen planner seeds. Workers share loaded immutable weights within a process;
each fight owns its Search session. Tracking aggregates these seeded teachers by
the comparison arm and retains their individual configurations.

Missing or unsupported anchors produce explicit actor fallbacks. Their episodes
remain counted, but receive no unusable Search training supplement. Truncated
episodes keep unknown value labels. Reanalysis preserves original behavior and
outcome bytes and can normalize historical observed-prefix traces. PPO remains a
separate on-policy learner. The trace inspector accepts the new model identity.

## Original Vantom source verification

The historical corpus remains unchanged:

- Path: `runs/vantom-specialist-20261002/corpus/corpus.json`.
- SHA-256: `0b9f7cd09f6d63aa47f3110b3e7faca63039ea37e6b392e4ed0db5ebd63a9a9f`.
- Original public prefix manifest: `runs/vantom-search-training-20261008/prefixes-v3.json.gz`.
- New derivative: [search-source.json](../../runs/search-consolidation-20261011/source/search-source.json).
- New identity: `sts_verified_search_source_v1:c7e5ea49924aa9a5805c5e144145176c95de577b1fa5e1a16ced6186551ca81c`.

The explicit importer checks original artifact bindings, split reservations and
the historical producer's fresh-inventory certificate. It checks hidden lifetime
counts, empty card/relic instance data, native setup counters and the supported
potion pool. Public opening reconstruction must succeed under current rules.
Every continuation then matches an exact native replay from its original frozen
opening, including public observations and intermediate reveals. Actual snapshots
are used only by this audit and the episode runner; the planner receives public
anchors. The unchanged `CombatCorpus` implementation guard is not bypassed.

| Partition | Openings | Continuations | Source fights/campaigns |
| --- | ---: | ---: | ---: |
| Training | 101 | 567 | 101 |
| Validation | 42 | 225 | 42 |
| Total verified | 143 | 792 | 143 |

All **935 starts** passed. The importer took **559.07 seconds** and never opened
held-out test snapshots. Prefixes are processed one fight at a time and stored
compressed. The derivative is bound to the current implementation; executable
changes require a new verification run rather than editing historical hashes.
This establishes compatibility of these starts, not their winnability or complete
engine parity with the native game.

## Bounded integration checks

Both collection checks used the frozen round-three Vantom student,
`runs/vantom-search-round3-20261008/student/final.sts-model`, SHA-256
`7805954e02238a6928a3c15ce2b6d65e492f1743a3a1bb87054dc8ffa5d9c9b0`.
They used the installed commands with their new default model, two workers,
four simulations, depth eight, one belief particle and collection seed 11.
The Vantom check capped each fight at 16 decisions; the campaign-corpus check
capped it at eight. These budgets test integration and are not strength or
throughput benchmarks.

| Collection | Episodes | Opening / continuation | Decisions | Searched | Forced actions | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original Vantom source | 8 | 4 / 4 | 107 | 91 | 16 | 11.33 s |
| New campaign corpus | 8 | 5 / 3 | 55 | 44 | 11 | 3.92 s |

Neither collection had an unsupported-state fallback or search cutoff. All
eligible decisions were searched. Each dataset passed two distillation updates
and a two-episode reanalysis with its newly created smoke student. Vantom supplied
91 actor examples: 22 with completed value labels and 69 with unknown value.
The campaign corpus supplied 44 actor examples: six completed and 38 unknown.
Reanalysis refreshed 16 and six eligible targets respectively, preserving all
selected trajectory and outcome bytes. Distillation update times were 0.13 s
and 0.08 s; reanalysis took 4.09 s and 0.69 s. Smoke students were not promoted.

A bounded paired campaign run exercised both regions with the same fixed
noncombat controller: two campaigns per arm, 64 decisions per campaign, two
simulations. Search handled 56 of 67 combat choices; the other 11 were forced.
It completed five fights before the campaign decision cutoffs. A two-opening
paired Vantom CLI comparison also completed without failures, searching 15 of 16
combat choices with one forced action. These deliberately truncated checks do
not estimate Act 1 or Vantom win-rate improvement.

Public reports and their hashes are bound in
[acceptance.json](../../runs/search-consolidation-20261011/acceptance.json), SHA-256
`aee573583f1f4014e08b7b0f5591cde95e13b843629eacad75274a89eb5fd868`.
The eight new Vantom Search recordings also passed the trace inspector's
artifact and candidate validation.

## Validation and remaining limits

- Python compilation and diff checks passed.
- **494 affected regression tests passed in 210.81 s**, covering Search, beliefs,
  native construction/branching, data, workers, inspector and CLI integration.
- **26 additional tracking/checkpoint-view tests passed in 9.70 s**.
- One independent semantic review concluded with no remaining blockers; its
  focused regression run passed 14 tests in 18.07 s. It found and verified fixes
  for hidden lifetime state during import, fixture potion-pool mismatch, audit
  configuration attribution and per-episode tracking fragmentation.

Executable identity for the verification and integration reports:

- Build: `d6c6abd0b4de300af1c690be2224514a09ec98367195b9543465cae33e96acfc`.
- Headless rules: `a7aff887d75dc4de4e2691bb261c72886bdb863f47239dc7b025e71d008ee5cb`.
- Target: `sts2-v0.107.1-steam-23811903`.

Implementation and review wall times were not separately recorded. The available
validation and execution timings are reported above.

Event-owned fights and unsupported inventory history still fall back explicitly.
Finite-particle beliefs, existing latency limits and the campaign promotion gate
remain unchanged. A native bridge must still produce compatible ordered public
entry, reveal and lifecycle receipts. No bridge implementation or policy-strength
promotion is implied by this consolidation.
