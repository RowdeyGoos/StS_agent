# Documentation

Start with [AGENTS.md](../AGENTS.md), then read only the guide relevant to the task.
The top level contains current guidance. Completed Phase 0/1 work lives in the
[archive](archive/README.md); its procedures are historical, not session checklists.

## Current guides

| Topic | Read |
| --- | --- |
| Project overview and commands | [Project README](../README.md) |
| Session workflow and validation | [AGENTS](../AGENTS.md) |
| Current bridge support, failures and remaining work | [Status](STATUS.md) |
| Priorities | [Roadmap](../ROADMAP.md) |
| Architecture decisions | [Decisions](../DECISIONS.md) |
| Live bridge development and testing | [Live development](LIVE_DEVELOPMENT.md), [bridge commands](../bridge/Sts2AgentBridge/README.md) |
| Combat bridge selectors and host | [Combat choices](COMBAT_CHOICES.md) |
| Generic event semantics | [Contract reference](GENERIC_EVENTS.md) |
| Named event live evidence | [Caller evidence index](EVENT_COVERAGE.md) |
| Static native event census (historical gap labels) | [Research map and corrections](EVENT_INTERACTION_MAP.md) |
| Full-game headless implementation tasks | [Current implementation backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md) |
| Shared public contract, bridge adapter and Gymnasium delivery | [V1/full-run v2 contracts and producer mapping](AGENT_CONTRACT.md), [encoding and Gymnasium](AGENT_ENCODING.md), [delivery plan](AGENT_ENVIRONMENT.md) |
| Public trajectories, agent command, workers and training data | [Execution and data loading](AGENT_EXECUTION.md) |
| Combat/full-run objectives, imitation/PPO, combat search, distillation, reanalysis and paired evaluation | [Training guide](AGENT_TRAINING.md) |
| Combat-search redesign, maintained beliefs, prefix recovery and future bridge compatibility | [Search architecture plan](COMBAT_SEARCH_ARCHITECTURE.md) |
| Local experiment dashboard, learning curves, historical imports and checkpoint lineage | [Experiment tracking](EXPERIMENT_TRACKING.md) |
| Headless game logic and architecture | [Game engine](HEADLESS_ENGINE.md) |
| Agent-evaluation scope and information boundary | [Target](TARGET.md) |
| Delegated work, when needed | [Multi-agent guide](MULTI_AGENT_EXECUTION.md) |

## References and results

- Experimental combat search: [implementation and October 4 pilot](evidence/COMBAT_SEARCH_2026_10_04.md)
  records public-information/RNG checks, latency, learning integration and the
  campaign coverage limitation; search remains opt-in.
- Maintained-belief coverage: [October 4 Act 1 audit](evidence/COMBAT_BELIEF_COVERAGE_2026_10_04.md)
  records declared-start coverage, setup/turn selectors and shared identity checks.
- Direct conditional sampling: [October 4 performance experiment](evidence/COMBAT_DIRECT_SAMPLING_2026_10_04.md)
- Search learning and input compatibility: [October 4 verification](evidence/COMBAT_SEARCH_LEARNING_2026_10_04.md)
  records collection, distillation, reanalysis and checkpoint compatibility.
- Search benefit and critic diagnosis: [October 4 paired experiment](evidence/COMBAT_SEARCH_BENEFIT_2026_10_04.md)
  records 128 paired starts, serial timing and public-belief rollout audits;
  that starter-deck experiment found no changed win outcomes.
- Developed-deck search benchmark: [October 5 paired experiment](evidence/COMBAT_SEARCH_DEVELOPED_BENCHMARK_2026_10_05.md)
  records four developed inventories, calibration, challenge/control results and
  a follow-up diagnosis of the outcome-changing decisions.
- Rollout search and learning: [October 6 frozen study](evidence/COMBAT_SEARCH_LEARNING_2026_10_06.md)
  records cost-matched teachers, 480 training fights, three learning seeds and
  fresh confirmation. Search helped on the authored challenge population;
  distillation did not improve searched wins. Campaign/native gates remain open.
- Search strength diagnosis: [October 6 budget and learning ablations](evidence/COMBAT_SEARCH_STRENGTH_2026_10_06.md)
  records the search-cost curve, fixed-label training passes, exact action-value
  references, prior-sensitive selection and measured performance probes.
- Search selection diagnosis: [October 7 action audit and controlled comparisons](evidence/COMBAT_SEARCH_SELECTION_2026_10_07.md)
  records public-belief action continuations, round-by-round selection evidence
  and fixed-budget value-weight/final-choice/horizon experiments.
- Vantom specialist versus search: [October 7 paired validation comparison](evidence/VANTOM_SPECIALIST_SEARCH_2026_10_07.md)
  records the frozen specialist with and without search on 42 catalog openings,
  with coverage, fallback, latency and paired uncertainty.
- Search throughput and encoding: [October 7 worker benchmark](evidence/SEARCH_WORKER_SCALING_2026_10_07.md)
  compares 4/8/12/16 workers with identical search work and records an exact-input
  compact-encoding prototype, latency, memory limits and optimization priorities.
- Production search inference: [October 8 optimization benchmark](evidence/SEARCH_INFERENCE_2026_10_08.md)
  records compact inference and sparse combat-channel extraction, exact input
  and search equivalence, and the combined effect with 16 workers.
- Search training speed: [October 8 follow-up benchmark](evidence/SEARCH_TRAINING_SPEED_2026_10_08.md)
  compares trajectory preparation, prepared public ownership, immutable content
  descriptions and exact-input prediction caching with fixed search work.
- Vantom search training: [October 8 coverage repair and 50k-decision study](evidence/VANTOM_SEARCH_TRAINING_2026_10_08.md)
  records public reveal conditioning, verified continuation prefixes, one frozen
  teacher round, and the matched comparison with the 250k PPO specialist.
- Vantom search round 2: [October 8 continuation to 100k decisions](evidence/VANTOM_SEARCH_ROUND2_2026_10_08.md)
  records another 50k fresh decisions with the first student as frozen teacher,
  exact weight continuation, and a matched six-arm validation comparison.
- Vantom search round 3: [October 8 continuation to 150k decisions](evidence/VANTOM_SEARCH_ROUND3_2026_10_08.md)
  records another 50k fresh decisions using the 100k student as frozen teacher,
  with unchanged settings and the matched six-arm validation comparison.
- Vantom sample reuse: [October 8 replay and selective reanalysis](evidence/VANTOM_SEARCH_REUSE_2026_10_08.md)
  compares matched extra training on saved targets with targets refreshed by the 150k teacher.
- Related agent architecture: [AlphaSpire comparison, October 4](evidence/ALPHASPIRE_COMPARISON_2026_10_04.md)
  records reported win rates, inspected search and learning mechanisms, differences
  from our current agent, and a proposed combat-search experiment.
- Retired simulator, actor and experiment guides: [archive](archive/README.md#retired-simulator-pipelines).
- Latest live results: [September 25–27 full-agent coverage](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md).
  Earlier results: [September 12–13 multi-case ledger](evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md)
  and [Crystal Sphere](evidence/CRYSTAL_SPHERE_LIVE_2026_09_12.md). Earlier supporting
  evidence: [September 9–10 combined batch](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md)
  and [September 8 unified smoke](evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md).
  Use [status](STATUS.md) for the current conclusion, not a ledger's first failed attempt.
- Build identity: [game manifest guide](../manifests/game-builds/README.md),
  [current bridge release](../bridge/Sts2AgentBridge/releases/current/README.md).
- Historical contracts, plans, reviews and results: [archive index](archive/README.md),
  including the [engine chronology](archive/HEADLESS_ENGINE_2026_09_22.md) and
  [earlier architecture plan](archive/LONG_TERM_ARCHITECTURE_ROADMAP_2026_09_22.md).
- Profile work: read the [user-data boundary](LIVE_DEVELOPMENT.md#user-data-boundary)
  only when that work is explicitly requested.

For a capability update, edit the relevant support row and remaining-work category
in status. For a live test, put setup, release binding, attempt chronology and exact
counts in the evidence ledger, then update the caller index. For a protocol change,
update the technical reference and schema. Keep CLI instructions in the bridge guide.
Do not append the same result to every document.

Update the guide that owns the changed fact. Keep substantial experiment results
in `evidence/` and link them from status. Routine checks belong in the change
summary; do not create a new plan, review ledger or handoff for every attempt.
