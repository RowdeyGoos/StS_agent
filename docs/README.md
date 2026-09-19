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
| Reduced headless actor and datasets | [Headless actor](HEADLESS_ACTOR.md) |
| Headless assessment and full-game implementation tasks | [Headless full-game backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md) |
| Combat simulator | [Project context](PROJECT_CONTEXT.md) |
| Training, profiling and evaluation | [Experiment workflows](EXPERIMENT_WORKFLOWS.md), [benchmarks](BENCHMARKS.md), [benchmark suite](BENCHMARK_SUITE.md) |
| Full-game scope and research destination | [Target](TARGET.md), relevant sections of [long-term architecture](LONG_TERM_ARCHITECTURE_ROADMAP.md) |
| Delegated work, when needed | [Multi-agent guide](MULTI_AGENT_EXECUTION.md) |

## References and results

- Combat: [agent flow](AGENT_FLOW.md), [card representation](CARD_REPRESENTATION.md),
  [Ironclad cards](IRONCLAD_CARDS.md), [Overgrowth hard pool](OVERGROWTH_HARD_V1.md).
- Latest live results: [September 12–13 multi-case ledger](evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md)
  and [Crystal Sphere](evidence/CRYSTAL_SPHERE_LIVE_2026_09_12.md). Earlier supporting
  evidence: [September 9–10 combined batch](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md)
  and [September 8 unified smoke](evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md).
  Use [status](STATUS.md) for the current conclusion, not a ledger's first failed attempt.
- Build identity: [game manifest guide](../manifests/game-builds/README.md),
  [current bridge release](../bridge/Sts2AgentBridge/releases/current/README.md).
- Historical contracts, plans, reviews and results: [archive index](archive/README.md).
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
