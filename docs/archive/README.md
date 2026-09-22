# Historical documentation

This archive holds completed work and earlier designs. Dated statuses, proposed
next steps, one-shot approvals and validation procedures describe their original
context. Use [current guides](../README.md) and [AGENTS.md](../../AGENTS.md) for new
work. Consult an archived record only for a specific semantic or evidence question.

## Find a record

| Topic | Historical references |
| --- | --- |
| Headless implementation assessment and completed batches | [September 12–21 backlog](HEADLESS_FULL_GAME_IMPLEMENTATION_2026_09_21.md); [current tasks](../HEADLESS_FULL_GAME_IMPLEMENTATION.md) |
| Headless game-rule chronology and original reference analysis | [September 22 engine record](HEADLESS_ENGINE_2026_09_22.md); [current guide](../HEADLESS_ENGINE.md) |
| Earlier architecture and research plan | [Archived design](LONG_TERM_ARCHITECTURE_ROADMAP_2026_09_22.md); [current target](../TARGET.md) and [backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md) |
| Earlier architecture decisions | [Decision log](DECISIONS_2026_09_08.md) |
| Target and evaluation design | [Original charter](phase-0/PHASE_0_TARGET_CHARTER.md); [current target](../TARGET.md) owns the concise definition |
| Profile design and access history | [Fixture plan](phase-0/PHASE_0_PROFILE_FIXTURE_PLAN.md), [baseline request](phase-0/PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md), [stopped attempt](phase-0/research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md) |
| Initial bridge investigation | [Integration spike](phase-1/PHASE_1_INTEGRATION_SPIKE.md), [initial implementation](phase-1/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md) |
| Earlier live/headless integration | [Next increment](phase-1/research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md), [actor-ready results](phase-1/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md) |
| Room, shop and item semantics | [Room flows](phase-1/PHASE_1_ROOM_FLOWS_V1_CONTRACT.md), [shop map permission](phase-1/PHASE_1_SHOP_MAP_PERMISSION_V1_CONTRACT.md), [items](phase-1/PHASE_1_ITEM_V1_CONTRACT.md) |
| Card selection semantics | [Selection](phase-1/PHASE_1_CARD_SELECTION_V1_CONTRACT.md), [completion](phase-1/PHASE_1_CARD_SELECTION_COMPLETION_V1_CONTRACT.md) |
| Generic event semantics | [G7 contract](phase-1/PHASE_1_GENERIC_EVENT_V7_CONTRACT.md), [G7 results](phase-1/research/PHASE_1_GENERIC_EVENT_V7_ACCEPTANCE.md); earlier versions are in the same directories |
| Direct off-screen selection | [V10 contract](phase-1/PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md), [successful result](phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md) |
| Dated native event census and gap comparison | [September 10 research map](EVENT_INTERACTION_MAP_2026_09_10.md); [current research entry and corrections](../EVENT_INTERACTION_MAP.md) |
| Original release/source identities | [Bridge release history](../../bridge/Sts2AgentBridge/releases/history/README.md) |

`phase-0/` and `phase-1/` retain original filenames; each `research/` directory
contains the associated results, reviews and diagnostic records. Search these
directories when the index does not cover the specific question. Archived
versioned contracts remain useful references for their exact semantics, but their
release-copying and review procedures do not govern the current unified bridge.

## Original bytes and paths

The documentation was reorganized on 2026-09-08 from commit
`176882fe2016832d7dbafd355f76c42bb89cf1ae`. Archived document bodies and recorded
hashes are preserved; relative Markdown links were adjusted for navigation.
Those link edits can change a document's own byte hash. Use the original Git
blob whenever a historical contract binds exact document bytes; never repin a
historical hash to the relocated copy. For example:

```bash
git show 176882fe2016832d7dbafd355f76c42bb89cf1ae:docs/PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md
git show 176882fe2016832d7dbafd355f76c42bb89cf1ae:docs/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md
```

If a record names an earlier source commit, that exact revision remains the
authority for its artifact. The retired `verify_live_campaign_inputs.py` binds
the original R0a document paths and temporary campaign inputs; it belongs to
that historical checkout, not today's operational workflow. The current bridge
checker does not depend on these archived documentation paths.

The redundant Astra handoff was removed. Superseded status and coverage chronology
remain in Git at the commit above. The accepted headless JSON schema remains at
its [existing consumer path](../research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json)
as a historical contract fixture; its executable pipeline is retired.

## Retired simulator pipelines

On 2026-09-22 the old simulator wrappers, reduced backend and RL/search/training/
benchmark pipelines were removed without compatibility support. The current
engine and production bridge remain. These guides describe the retired system:

- [Combat context](legacy-simulator/PROJECT_CONTEXT.md), [agent flow](legacy-simulator/AGENT_FLOW.md)
- [Reduced actor](legacy-simulator/HEADLESS_ACTOR.md), [card representation](legacy-simulator/CARD_REPRESENTATION.md)
- [Experiment workflows](legacy-simulator/EXPERIMENT_WORKFLOWS.md), [benchmarks](legacy-simulator/BENCHMARKS.md), [benchmark suite](legacy-simulator/BENCHMARK_SUITE.md)
- [Old Ironclad scope](legacy-simulator/IRONCLAD_CARDS.md), [old Overgrowth pool](legacy-simulator/OVERGROWTH_HARD_V1.md)

The original guides, code, fixtures and removed reward-gold comparison tools are
available at commit `9d8d1c75069f9bfb04e161c25706343c5b63ea42`. Navigation links
were adjusted; recorded evidence hashes retain their original meaning. For exact
bytes, use `git show <revision>:<original-path>`. The retained native engine
comparisons and bridge release identities were not repinned.

The engine chronology and architecture plan archived on 2026-09-22 preserve the
bodies from `5389796666da9e2cefff30839612288ce7875ccf`, with archive labels and
relative links adjusted. Recorded hashes and evidence artifacts were not repinned.

The event research narrative was relocated on 2026-09-19 from
`cd3dc76:docs/EVENT_INTERACTION_MAP.md`. Its recorded hashes and comparison at
`4d3516f` remain unchanged; navigation links were rebased and a historical notice
was added. Use that Git blob for original document bytes. The accompanying
`docs/evidence/event_interactions_2026_09_09/` inventory/scanner artifacts were not
changed. Superseded status/coverage prose from this cleanup remains in `cd3dc76`.
